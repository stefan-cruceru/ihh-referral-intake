"""The synthetic practice patients load, and the app's routes agree with the organizers' answers."""

import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("CAREBRIDGE_DB", os.path.join(tempfile.mkdtemp(), "test.db"))  # never touch the real log

from demo import synthetic  # noqa: E402


def test_ten_profiles_each_with_a_packet():
    profs = synthetic.profiles()
    assert [p["id"] for p in profs] == [f"S{i:02d}" for i in range(1, 11)]
    for p in profs:
        assert synthetic.packet_path(p["id"]).read_bytes()[:5] == b"%PDF-"
        assert len(p["documents"]) == p["pages"]


def test_quotes_are_real_lines_from_the_cited_page():
    for pid, rep in synthetic.sample_reports().items():
        for f in rep["facts"]:
            assert f["quote"] in synthetic.page_text(pid, f["page"]), (pid, f["page"], f["quote"])


def test_denials_and_needs_info_match_the_answer_key():
    reps = synthetic.sample_reports()
    for pid, key in synthetic.answer_key().items():
        code = reps[pid]["recommendation"]["code"]
        if key["decision"] == "deny":
            assert code == "likely_no", pid
        elif key["decision"] == "needs_info":
            assert code in ("needs_info", "clinical_check"), pid
        else:  # approve: the app may still ask for date-based items (dates are redacted in real packets)
            assert code in ("likely_yes", "needs_info"), pid
            assert not reps[pid]["recommendation"]["blockers"], pid


def test_demo_inbox_points_at_synthetic_patients():
    import json

    inbox = json.loads((APP / "demo" / "inbox.json").read_text(encoding="utf-8"))
    ids = {p["id"] for p in synthetic.profiles()}
    assert all(r["packet"] in ids for r in inbox["referrals"])
