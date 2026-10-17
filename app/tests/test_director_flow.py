"""What the intake director's call changed (docs/workflow-and-timing.md, "What the intake director told us"):
critical values never silent, an upload page with a receipt, reminders, the clinical reviewer in the app,
staff-only checks and overnight packets."""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("CAREBRIDGE_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

import pytest  # noqa: E402

from carebridge import critical, drafts, hospital, rules, tracker  # noqa: E402
from tests.test_queue import _qc, all_met  # noqa: E402


def _report(facts, transcript=""):
    return {"facts": facts, "diagnoses": [], "reason_for_referral": "",
            "pages": [{"page": 3, "transcript": transcript}]}


def _fact(fid, page, quote, verify="found", statement=""):
    return {"id": fid, "page": page, "topic": "cardiac", "statement": statement, "statement_es": "", "quote": quote, "verify": verify}


# ---- critical values ------------------------------------------------------------------------

def test_heart_failure_without_ef_is_not_found():
    """The director's example: a missed ejection fraction must never be silent."""
    rep = _report([_fact("F1", 2, "Hx of CHF, on furosemide")])
    rows = critical.check(rep)
    ef = next(r for r in rows if r["id"] == "ejection_fraction")
    assert ef["status"] == "not_found" and ef["page"] is None


def test_ef_found_cites_page_and_words():
    rep = _report([_fact("F1", 2, "Hx of CHF"), _fact("F2", 5, "Echo: LVEF 25-30%")])
    ef = next(r for r in critical.check(rep) if r["id"] == "ejection_fraction")
    assert ef["status"] == "found" and ef["page"] == 5 and "LVEF 25-30%" in ef["quote"]


def test_ef_without_a_number_does_not_count():
    rep = _report([_fact("F1", 2, "CHF exacerbation"), _fact("F2", 4, "EF not available at this time")])
    assert next(r for r in critical.check(rep) if r["id"] == "ejection_fraction")["status"] == "not_found"


def test_unchecked_quote_is_not_found_but_typed_page_says_check_it():
    rep = _report([_fact("F1", 2, "heart failure"), _fact("F2", 5, "EF 35%", verify="not_found")],
                  transcript="Echo today\nEF 35% with mild MR")
    ef = next(r for r in critical.check(rep) if r["id"] == "ejection_fraction")
    assert ef["status"] == "on_page" and ef["page"] == 3


def test_no_condition_no_row():
    assert critical.check(_report([_fact("F1", 1, "ambulates 150 ft independently")])) == []


def test_missing_critical_value_is_never_a_quiet_yes(monkeypatch):
    from carebridge import intake

    real_route = intake.route
    yes = lambda *a, **k: {**real_route(*a, **k), "code": "likely_yes"}  # noqa: E731
    monkeypatch.setattr(intake, "route", yes)
    assert _qc(all_met())["recommendation"]["code"] == "likely_yes"
    monkeypatch.setattr(intake.critical, "check", lambda rep: [{"id": "ejection_fraction", "status": "not_found"}])
    rec = _qc(all_met())["recommendation"]
    assert rec["code"] == "needs_info" and rec["critical_missing"] == ["ejection_fraction"]


def test_missing_items_draft_asks_for_the_critical_value_and_the_reviewers_list():
    rep = _qc(all_met())
    rep["facts"].append(_fact("F9", 1, "Hx of CHF"))
    rep.pop("critical", None)
    card = {"case_no": "REF-001", "arrived_at": time.time(), "clinical_asks": [{"text": "Last 3 finger sticks"}]}
    text = drafts.missing_items(card, rep, "en")["text"]
    assert "ejection fraction" in text and "Last 3 finger sticks" in text
    assert "fracción de eyección" in drafts.missing_items(card, rep, "es")["text"]


# ---- tracker: clinical reviewer, staff checks, overnight -------------------------------------

def _tracker(arrived_at=None):
    t = tracker.Tracker()
    t.add({"id": "A", "case_no": "A", "hospital": "H"}, arrived_at=arrived_at)
    return t


def test_only_the_clinical_reviewer_writes_notes_and_turnaround_is_measured():
    t = _tracker()
    t.cards["A"]["clinical_sent_at"] = t.clock.now() - 25 * 60
    with pytest.raises(ValueError):
        t.act("A", "clinical_note", "Bea", "page 16 shows a heel wound", role="coordinator")
    t.act("A", "clinical_note", "Rene", "page 16 shows a heel wound", role="clinical")
    t.act("A", "clinical_ask", "Rene", "Wound care orders", role="clinical")
    t.act("A", "clinical_done", "Rene", "", role="clinical")
    v = t.view("A")
    assert v["clinical_notes"][0]["text"].startswith("page 16") and v["clinical_asks"][0]["text"] == "Wound care orders"
    assert v["clinical_min"] == 25
    assert t.report()["clinical"]["median_min"] == 25
    # The audit log keeps that a note was written, never the note.
    assert all("heel" not in a["detail"] for a in t.audit)


def test_staff_checks_keep_only_who_and_when():
    t = _tracker()
    t.act("A", "staff_check", "Bea", "background:look", role="coordinator")
    assert t.view("A")["staff_checks"]["background"]["result"] == "look"
    with pytest.raises(ValueError):
        t.act("A", "staff_check", "Bea", "background:felony on 3/2", role="coordinator")


def test_overnight_packet_clock_is_a_setting():
    night = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0).timestamp()
    t = _tracker(arrived_at=night)
    assert t.cards["A"]["overnight"]
    assert t.view("A")["deadline"] == night + 7200
    t.overnight_clock = "morning"
    morning = datetime.fromtimestamp(t.view("A")["clock_start"])
    assert (morning.hour, morning.minute) == tracker.MORNING_START and morning.timestamp() > night


def test_day_packet_is_not_overnight():
    noon = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()
    assert not _tracker(arrived_at=noon).cards["A"]["overnight"]


# ---- what the hospital hears ---------------------------------------------------------------

def test_receipt_reminder_and_escalated_carry_no_clinical_detail():
    t = _tracker()
    t.cards["A"].update(case_manager="Pat, social worker", cm_email="pat@hospital.example.org")
    hospital.sync(t)
    assert [m["kind"] for m in t.cards["A"]["hospital_messages"]] == ["received"]
    hospital.sync(t)  # once only
    assert len(t.cards["A"]["hospital_messages"]) == 1
    t.act("A", "info_sent", "Bea")
    t.cards["A"]["info_requested_at"] -= 31 * 60
    t.cards["A"]["clinical_sent_at"] = t.clock.now()
    hospital.sync(t)
    kinds = [m["kind"] for m in t.cards["A"]["hospital_messages"]]
    assert "reminder" in kinds and "escalated" in kinds
    for m in t.cards["A"]["hospital_messages"]:
        assert m["mode"] == "draft"  # off unless IHH agrees
        assert "A" in m["subject"]
    t.act("A", "hospital_replied", "Bea")
    before = len(t.cards["A"]["hospital_messages"])
    t.cards["A"]["info_requested_at"] -= 120 * 60
    hospital.sync(t)
    assert len(t.cards["A"]["hospital_messages"]) == before


# ---- the upload page, end to end over HTTP -------------------------------------------------

@pytest.fixture()
def server():
    from carebridge import webapp

    webapp.TRACK.reset()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _pdf() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 260), "white").save(buf, "PDF")
    return buf.getvalue()


def _post(url, data, headers=None):
    req = urllib.request.Request(url, data=data, method="POST", headers=headers or {})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def test_upload_page_gives_a_receipt_and_a_status_without_sign_in(server, monkeypatch):
    from carebridge import auth, webapp

    monkeypatch.setattr(auth, "mode", lambda: "practice")  # sign-in on: the page still works
    monkeypatch.setattr(webapp.config, "get_api_key", lambda: None)
    status, html = _get(server + "/send")
    assert status == 200 and b"/send/upload" in html
    docs = json.loads(_get(server + "/send/checklist")[1])["docs"]
    assert [d["id"] for d in docs] == rules.checklist_ids()
    got = _post(server + "/send/upload?name=Pat&email=pat%40h.example.org&facility=St%20Example&source=snf&lang=es",
                _pdf(), {"X-Filename": "referral.pdf"})
    case = got["case_code"]
    assert "Recibimos" in got["receipt"]["body"] and case in got["receipt"]["subject"]
    card = webapp.TRACK.cards[case]
    assert card["channel"] == "upload_page" and card["source"] == "snf" and card["cm_lang"] == "es"
    st = json.loads(_get(f"{server}/send/status?case={case}&key={got['key']}")[1])
    assert st["status"] == "received"
    with pytest.raises(urllib.error.HTTPError):
        _get(f"{server}/send/status?case={case}&key=wrong")
    # More papers need the key from the receipt, and they stop the reminders on the first referral.
    more = _post(f"{server}/send/upload?case_code={case}&key={got['key']}&name=Pat", _pdf(), {"X-Filename": "more.pdf"})
    assert more["case_code"] == f"{case}-M1" and webapp.TRACK.cards[case]["hospital_replied_at"]
    stranger = _post(f"{server}/send/upload?case_code={case}&name=X", _pdf(), {"X-Filename": "x.pdf"})
    assert not stranger["case_code"].startswith(case)
