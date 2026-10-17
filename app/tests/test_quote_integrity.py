"""A verified quote must preserve the chart's words, numbers, signs, and units."""

import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carebridge import intake, rules  # noqa: E402


@pytest.mark.parametrize("quote,transcript", [
    ("Dose 0.5 mg daily", "Dose 0.05 mg daily"),
    ("Dose 1.2 mg daily", "Dose 1.02 mg daily"),
    ("Patient can walk independently", "Patient cannot walk independently"),
    ("Patient has chest pain", "Patient has no chest pain"),
    ("Patient is alert", "Patient is not alert"),
    ("Dose -0.5 mg daily", "Dose 0.5 mg daily"),
    ("Dose +0.5 mg daily", "Dose -0.5 mg daily"),
    ("0.5 mg daily", "-0.5 mg daily"),
    ("0.5 mg daily", "- 0.5 mg daily"),
    ("Dose 5 mg daily", "Dose 5 mcg daily"),
    ("EF 35%", "EF 35"),
    ("EF 35", "EF 35%"),
    ("BP 128/76", "BP 128/67"),
    ("Patient can walk", "Patient can't walk"),
    ("walk", "walking"),
])
def test_quote_rejects_changed_clinical_content(quote, transcript):
    assert not intake.quote_in_text(quote, transcript)


@pytest.mark.parametrize("quote,transcript", [
    ("Dose 0.5 mg daily", "Nursing note: Dose 0.5 mg daily. Continue monitoring."),
    ("DOSE: 0.5 MG DAILY", "Dose 0.5 mg\ndaily."),
    ("Dose 1.02 mg daily", "Dose 1.02 mg daily"),
    ("Dose -0.5 mg daily", "Dose \u22120.5 mg daily"),
    ("Dose -0.5 mg daily", "Dose - 0.5 mg daily"),
    ("SpO2: 95%", "SpO2 95 %"),
    ("BP 128/76, HR 82", "BP 128 / 76 HR 82."),
    ("Patient can't walk", "Patient can\u2019t walk."),
    ("Patient cannot walk independently", "Note: Patient cannot walk independently."),
])
def test_quote_allows_exact_words_and_trivial_formatting(quote, transcript):
    assert intake.quote_in_text(quote, transcript)


@pytest.mark.parametrize("quote,transcript", [("", "Dose 0.5 mg"), ("dose", ""), ("...", "...")])
def test_empty_quote_or_page_is_unverified(quote, transcript):
    assert not intake.quote_in_text(quote, transcript)


@pytest.mark.parametrize("verdict", ["found", "paraphrase"])
@pytest.mark.parametrize("quote,source", [
    ("Dose 0.5 mg daily", "Dose 0.05 mg daily"),
    ("Patient can walk independently", "Patient cannot walk independently"),
])
def test_changed_quote_is_removed_from_gate_evidence_and_routes_to_clinical(verdict, quote, source):
    transcript = f"Patient awake. {source}"
    facts = [
        {"id": "F1", "page": 1, "topic": "adl", "statement": "Awake", "statement_es": "Despierto",
         "quote": "Patient awake", "verify": "found"},
        {"id": "F2", "page": 1, "topic": "adl", "statement": "Self-care", "statement_es": "Autocuidado",
         "quote": quote, "verify": verdict},
    ]
    assessment = {
        "reason_for_referral": "x", "reason_for_referral_es": "x", "wheelchair_dependent": "no",
        "preferred_language": "", "summary": "", "summary_es": "", "diagnoses": [], "conflicts": [],
        "questions": [],
        "rules": [{"rule_id": rid, "status": "met", "fact_ids": ["F2" if rid == "ADL-2" else "F1"],
                   "explanation": "", "explanation_es": ""} for rid in rules.assessed_rule_ids()],
        "checklist": [{"doc_id": did, "status": "present", "pages": [1]} for did in rules.checklist_ids()],
    }
    pages = {1: {"page": 1, "page_type": "ihh_referral_form", "rotation": 0, "mostly_redacted": False,
                 "earlier_stay": False, "language": "en", "possible_unredacted_identifier": False,
                 "duplicate_of": None, "blank": False}}
    text = {1: {"transcript": transcript, "second_transcript": transcript,
                "handwriting": "none", "ocr_confidence": 99}}

    matched = deepcopy(facts)
    matched[1]["quote"] = source
    clean = intake.quality_control(deepcopy(assessment), matched, pages, {}, deepcopy(text))
    assert clean["gates"]["self_care"]["status"] == "met"
    assert clean["recommendation"]["code"] != "clinical_check"

    report = intake.quality_control(assessment, facts, pages, {}, text)

    assert facts[1]["verify"] == "not_found" and facts[1]["model_verify"] == verdict
    rule = next(r for r in report["rules"] if r["rule_id"] == "ADL-2")
    assert rule["status"] == "cant_tell" and rule["fact_ids"] == []
    assert "evidence_unverified" in rule["notes"]
    assert {"rule_id": "ADL-2", "from": "met", "to": "cant_tell",
            "reason": "evidence_unverified"} in report["qc"]["downgrades"]
    assert report["gates"]["self_care"]["status"] == "cant_tell"
    assert report["recommendation"]["code"] == "clinical_check"
    assert report["recommendation"]["route_clinical"]
    if intake.numbers(quote):
        assert report["flags"]["unconfirmed_pages"] == [1]
        assert quote in report["pages"][0]["unconfirmed"]
    else:
        assert report["flags"]["unconfirmed_pages"] == []
