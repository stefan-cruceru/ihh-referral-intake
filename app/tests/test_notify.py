"""Staff alerts: right person, right channel and language, drafted once, never patient text."""

import email
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ["CAREBRIDGE_DB"] = os.path.join(tempfile.mkdtemp(), "notify.db")  # never touch the real log

from carebridge import notify, store, tracker  # noqa: E402


def _setup():
    store._conn = None
    os.environ["CAREBRIDGE_DB"] = os.path.join(tempfile.mkdtemp(), "notify.db")
    notify._cursor["audit"] = 0
    t = tracker.Tracker()
    notify.save_person({"name": "Coordinator 1", "role": "coordinator", "email": "c1@example.org", "teams": "c1@example.org",
                        "channel": "both", "lang": "es"})
    notify.save_person({"name": "Coordinator 2", "role": "coordinator", "email": "c2@example.org", "channel": "email"})
    notify.save_person({"name": "Lead", "role": "lead", "teams": "lead@example.org", "channel": "teams"})
    notify.save_person({"name": "Clinical line", "role": "clinical", "channel": "both"})  # no address yet
    return t


def test_new_referral_alerts_only_its_owner_per_their_channels():
    t = _setup()
    t.add({"case_no": "T-1", "hospital": "Test Hospital", "owner": "Coordinator 1"})
    notify.sync(t)
    rows = notify.outbox()
    assert {(r["person"], r["channel"]) for r in rows} == {("Coordinator 1", "email"), ("Coordinator 1", "teams")}
    assert all(r["lang"] == "es" and "T-1" in r["subject"] for r in rows)
    teams = next(r for r in rows if r["channel"] == "teams")
    assert teams["card"]["type"] == "AdaptiveCard" and teams["teams_link"].startswith("https://teams.microsoft.com/l/chat/")


def test_each_alert_is_drafted_once():
    t = _setup()
    t.add({"case_no": "T-2", "owner": "Coordinator 2"})
    notify.sync(t)
    notify.sync(t)
    assert len(notify.outbox()) == 1


def test_likely_no_goes_to_clinical_line_marked_urgent_and_flags_missing_address():
    t = _setup()
    c = t.add({"case_no": "T-3", "owner": "Coordinator 2"})
    t.attach_review(c["id"], {"recommendation": {"code": "likely_no", "blockers": ["ADL-2"], "route_clinical": True}})
    notify.sync(t)
    clin = [r for r in notify.outbox() if r["person"] == "Clinical line"]
    assert clin and all(r["urgency"] == "urgent" and not r["ready"] for r in clin)
    assert all("unknown" in r["to"] for r in clin)  # never a guessed address


def test_clock_and_unopened_alerts_reach_the_lead():
    t = _setup()
    c = t.add({"case_no": "T-4", "owner": "Coordinator 1"}, arrived_at=t.clock.now() - 100 * 60)  # 20 min left
    notify.sync(t)
    events = {(r["person"], r["event"]) for r in notify.outbox()}
    assert ("Lead", "lead_unopened") in events and ("Coordinator 1", "clock_30") in events


def test_no_patient_text_and_eml_opens_as_a_draft():
    t = _setup()
    t.add({"case_no": "T-5", "owner": "Coordinator 2", "body": "chart text that must not leak", "case_manager": "CM Name"})
    notify.sync(t)
    row = notify.outbox()[0]
    assert "chart text" not in row["body"] and "CM Name" not in row["body"]
    m = email.message_from_bytes(notify.eml(row))
    assert m["X-Unsent"] == "1" and m["To"] == "c2@example.org"


def test_marking_sent_takes_it_out_of_the_outbox():
    t = _setup()
    t.add({"case_no": "T-6", "owner": "Coordinator 2"})
    notify.sync(t)
    notify.mark(notify.outbox()[0]["id"], "sent_by_person", "Coordinator 2")
    assert notify.outbox() == [] and len(notify.outbox(include_done=True)) == 1


def test_waiting_draft_follows_a_newly_saved_address_and_language():
    t = _setup()
    t.add({"case_no": "T-7", "owner": "Clinical line"})
    notify.sync(t)
    before = next(r for r in notify.outbox() if r["channel"] == "email")
    assert not before["ready"] and before["lang"] == "en"
    notify.save_person({"name": "Clinical line", "role": "clinical", "email": "clin@example.org", "channel": "email", "lang": "es"})
    after = notify.get(before["id"])
    assert after["ready"] and after["to"] == "clin@example.org" and after["lang"] == "es"
    assert email.message_from_bytes(notify.eml(after))["To"] == "clin@example.org"


def test_addresses_come_from_the_sign_in_staff_list():
    from carebridge import auth

    t = _setup()
    t.staff = [{"name": "Bea", "role": "coordinator", "on_shift": True}, {"name": "Nobody Listed", "role": "coordinator", "on_shift": True}]
    everyone = {p["name"]: p for p in notify.people(t.staff)}
    bea = next(a for a in auth.staff() if a["name"] == "Bea")
    assert everyone["Bea"]["email"] == everyone["Bea"]["teams"] == bea["email"]
    assert everyone["Nobody Listed"]["email"] == ""  # not on the sign-in list: no guessed address
    reviewer = next(a for a in auth.staff() if a["role"] == "clinical")  # not on the board, still alerted
    assert everyone[reviewer["name"]]["email"] == reviewer["email"]


def test_fifteen_minute_alert_replaces_the_thirty_minute_one():
    t = _setup()
    t.add({"case_no": "T-8", "owner": "Coordinator 2"}, arrived_at=t.clock.now() - 110 * 60)  # 10 min left
    notify.sync(t)
    events = {r["event"] for r in notify.outbox(person="Coordinator 2")}
    assert "more_time" in events and "clock_30" not in events


def test_a_new_practice_run_drops_last_runs_practice_alerts_only():
    t = _setup()
    t.add({"id": "REAL-1", "case_no": "REAL-1", "hospital": "Test Hospital", "owner": "Coordinator 1"})
    t.add({"id": "S01-1", "case_no": "S01-1", "hospital": "Test Hospital", "owner": "Coordinator 1", "practice": True})
    notify.sync(t)
    notify.clear_practice()
    t.reset()
    subjects = [r["subject"] for r in notify.outbox()]
    assert any("REAL-1" in s for s in subjects)  # the real alert stays
    assert not any("S01-1" in s for s in subjects)  # the practice one is gone
    t.add({"id": "S01-1", "case_no": "S01-1", "hospital": "Test Hospital", "owner": "Coordinator 1", "practice": True})
    notify.sync(t)
    assert any("S01-1" in r["subject"] for r in notify.outbox())  # drafted again for the new run


def test_practice_board_staff_bring_their_own_address():
    _setup()
    staff = [{"name": "Carlos", "role": "coordinator", "on_shift": True, "email": "carlos@example.org"}]
    carlos = next(p for p in notify.people(staff) if p["name"] == "Carlos")
    assert carlos["email"] == carlos["teams"] == "carlos@example.org"
