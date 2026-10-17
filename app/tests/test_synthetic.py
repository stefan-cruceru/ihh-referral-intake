"""The synthetic practice patients load, and the app's routes agree with the organizers' answers."""

import os
import re
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


def test_spanish_covers_the_practice_sources_and_preserves_numeric_values():
    keys = synthetic.answer_key().values()
    source = {p["diagnosis"] for p in synthetic.profiles()}
    source.update(synthetic._no_verdict(p["summary"]) for p in keys)
    source.update(f["why"] for p in keys for f in p["findings"])
    source.update(c["what"] for p in keys for c in p["contradictions"])
    source.update(q for p in keys for q in p["follow_up"])
    translations = synthetic._translations()
    assert set(translations) == source
    for original, spanish in translations.items():
        assert spanish and spanish != original, original
        assert re.findall(r"\d+(?:\.\d+)?", spanish) == re.findall(r"\d+(?:\.\d+)?", original), original


def test_every_practice_review_has_spanish_narrative():
    for pid, rep in synthetic.sample_reports().items():
        assert rep["reason_for_referral_es"] != rep["reason_for_referral"], pid
        assert rep["summary_es"] != rep["summary"], pid
        assert rep["summary_es"].endswith(synthetic.TRANSLATION_NOTE_ES), pid
        for group, field in (("facts", "statement"), ("rules", "explanation"),
                             ("diagnoses", "explanation"), ("conflicts", "description")):
            for item in rep[group]:
                assert item[field + "_es"] != item[field], (pid, group, item)
        for question in rep["questions"]:
            assert question["en"] != question["es"], (pid, question)


def test_translation_changes_no_evidence_or_review_results(monkeypatch):
    def without_spanish(value):
        if isinstance(value, dict):
            return {k: without_spanish(v) for k, v in value.items() if not k.endswith("_es") and k != "es"}
        if isinstance(value, list):
            return [without_spanish(v) for v in value]
        return value

    translated = {pid: synthetic._report(pid) for pid in synthetic.answer_key()}
    monkeypatch.setattr(synthetic, "_spanish", lambda text: text)
    for pid, report in translated.items():
        # Includes every original quote, fact ID, page, DOC/rule ID, status, gate, flag and route.
        assert without_spanish(report) == without_spanish(synthetic._report(pid)), pid
