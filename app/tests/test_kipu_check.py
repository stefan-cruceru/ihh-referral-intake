"""Kipu readiness checked in the background: it checks what each Kipu step would send and never
writes to Kipu."""

import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
_tmp = tempfile.mkdtemp()
os.environ["CAREBRIDGE_DB"] = os.path.join(_tmp, "test.db")  # never touch the real log
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"

from carebridge import guard, kipu, kipu_check, tracker  # noqa: E402

PDF = (b"%PDF-1.4\n", "packet.pdf")
REPORT = {"reason_for_referral": "Leg cellulitis, oral antibiotics", "preferred_language": "English", "conditions": []}


def _card(**kw):
    return {"id": "REF-1", "case_no": "REF-1", "hospital": "Pacific Crest (invented)", "case_manager": "Pat, RN",
            "arrived_at": 0, "owner": "Bea", "staff_checks": {}, **kw}


def _state(res, key):
    return next(i["state"] for i in res["items"] if i["key"] == key)


def test_new_referral_waits_on_people_not_on_errors():
    res = kipu_check.check_card(_card(), None, PDF)
    assert res["status"] == "wait" and not [i for i in res["items"] if i["state"] == "fail"]
    assert _state(res, "decision") == "wait" and _state(res, "returning") == "wait"
    assert res["ready_steps"] == {"create_chart": True, "file_documents": False, "intake_note": False}


def test_decided_and_checked_referral_is_ready():
    card = _card(decision="accepted", security=guard.OK,
                 staff_checks={"returning_client": {"result": "new", "who": "Bea", "t": 0}})
    assert kipu_check.check_card(card, REPORT, PDF)["status"] == "ok"


def test_what_kipu_would_refuse_is_a_fail():
    assert _state(kipu_check.check_card(_card(hospital="unknown"), REPORT, PDF), "hospital") == "fail"
    assert _state(kipu_check.check_card(_card(kipu_id="K-9"), REPORT, PDF), "no_duplicate") == "fail"
    assert _state(kipu_check.check_card(_card(security=guard.HOLD), REPORT, PDF), "security") == "fail"
    assert _state(kipu_check.check_card(_card(), REPORT, (b"MZ\x90\x00", "packet.pdf")), "packet_type") == "fail"


def test_background_run_checks_every_card_and_never_writes(monkeypatch):
    def no_writes(*a, **k):
        raise AssertionError("the background check wrote to Kipu")

    monkeypatch.setattr(kipu.Client, "post", no_writes)
    track = tracker.Tracker()
    card = track.add(_card(id="REF-2", case_no="REF-2"))
    out = kipu_check.run_once(track, {"REF-2": PDF}, lambda cid: None)
    assert out["REF-2"]["writes"].startswith("none") and track.cards["REF-2"]["kipu_check"]
    assert kipu_check.CONNECTION["state"] == "ok"  # one signed read to practice Kipu got through
    assert kipu_check.summary(track)["count"]["wait"] == 1 and card["id"] == "REF-2"
