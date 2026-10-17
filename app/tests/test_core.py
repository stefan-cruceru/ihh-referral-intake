"""Checks on the parts that keep people safe: QC downgrades, routing, PHI guard, drafts, MCP."""

import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ["CAREBRIDGE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")  # never touch the real log

from carebridge import drafts, intake, mcp, phi, rules, tracker  # noqa: E402


def _base(statuses: dict, facts=None, verify="found"):
    facts = facts or [{"id": "F1", "page": 1, "topic": "adl", "statement": "s", "statement_es": "s", "quote": "q", "verify": verify}]
    assessment = {
        "reason_for_referral": "x", "reason_for_referral_es": "x", "wheelchair_dependent": "no", "preferred_language": "",
        "rules": [{"rule_id": rid, "status": st, "fact_ids": ["F1"] if st in ("met", "not_met") else [],
                   "explanation": "", "explanation_es": ""} for rid, st in statuses.items()],
        "diagnoses": [], "checklist": [{"doc_id": d, "status": "present", "pages": [1]} for d in rules.checklist_ids()],
        "conflicts": [], "questions": [], "summary": "", "summary_es": "",
    }
    pages = {1: {"page": 1, "page_type": "ihh_referral_form", "rotation": 0, "mostly_redacted": False, "earlier_stay": False,
                 "language": "en", "possible_unredacted_identifier": False, "duplicate_of": None, "blank": False}}
    return intake.quality_control(assessment, facts, pages, {})


def all_met(**over):
    s = {rid: "met" for rid in rules.assessed_rule_ids()}
    s.update(over)
    return s


def test_unverified_quote_downgrades_to_cant_tell():
    rep = _base(all_met(**{"ADL-1": "not_met"}), verify="not_found")
    adl = next(r for r in rep["rules"] if r["rule_id"] == "ADL-1")
    assert adl["status"] == "cant_tell" and "evidence_unverified" in adl["notes"]
    assert rep["recommendation"]["code"] != "likely_no"


def test_date_rules_never_met():
    rep = _base(all_met())
    for rid in rules.DATE_RULES & set(rules.assessed_rule_ids()):
        assert next(r for r in rep["rules"] if r["rule_id"] == rid)["status"] == "cant_tell"


def test_sex_offender_never_auto_denies():
    rep = _base(all_met(**{"OTH-2": "not_met", "FORM-X6": "not_met"}))
    assert rep["recommendation"]["code"] == "clinical_check"
    assert not rep["recommendation"]["blockers"]


def test_verified_gate_failure_routes_to_clinical():
    rep = _base(all_met(**{"ADL-2": "not_met"}))
    assert rep["gates"]["self_care"]["status"] == "not_met"
    assert rep["recommendation"]["code"] == "likely_no" and rep["recommendation"]["route_clinical"]


def test_superseded_form_rule_is_not_a_blocker():
    rep = _base(all_met(**{"FORM-M6": "not_met"}))
    assert "FORM-M6" not in rep["recommendation"]["blockers"]


def test_phi_guard_blocks_identifiers():
    assert not phi.check("DOB 3/4/1961, MRN 1234567, call 714-555-0101")["ok"]
    assert phi.check("62, uses a walker, lost his ID, leaves Friday")["ok"]


def test_drafts_list_same_docs_in_both_languages():
    rep = _base(all_met())
    rep["checklist"][2]["status"] = "missing"
    card = {"case_no": "T-1", "arrived_at": 0, "case_manager": "CM", "cm_email": "cm@example.org"}
    en, es = drafts.missing_items(card, rep, "en"), drafts.missing_items(card, rep, "es")
    assert en["doc_ids"] == es["doc_ids"] == ["DOC-3"]


def test_only_clinical_line_can_deny():
    t = tracker.Tracker()
    c = t.add({"case_no": "T-2"})
    try:
        t.act(c["id"], "denied", "Coordinator 1", "ADL-2")
        raise AssertionError("coordinator was allowed to deny")
    except ValueError:
        pass
    assert t.act(c["id"], "denied", "Clinical line", "ADL-2 p.6", role="clinical")["status"] == "denied"


def test_mcp_stdio_handshake():
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_admission_rules", "arguments": {"query": "wheelchair"}}}]
    out = subprocess.run([sys.executable, "-m", "carebridge", "mcp"], cwd=APP, capture_output=True, timeout=60,
                         input="\n".join(json.dumps(m) for m in msgs).encode())
    lines = [json.loads(x) for x in out.stdout.decode().splitlines()]
    assert [x["id"] for x in lines] == [1, 2, 3]
    assert len(lines[1]["result"]["tools"]) == len(mcp.TOOLS)
    assert "MOB-4" in lines[2]["result"]["content"][0]["text"]


def test_mcp_prompts_and_pick_lists():
    # What Copilot Chat's "/" menu shows, and the pick list behind the rule box.
    prompts = {p["name"] for p in mcp.handle({"id": 1, "method": "prompts/list"})["result"]["prompts"]}
    assert prompts >= {"check_referral", "explain_rule"} and "practice_patients" not in prompts
    tools = {t["name"] for t in mcp.handle({"id": 2, "method": "tools/list"})["result"]["tools"]}
    assert "list_practice_patients" not in tools
    assert mcp.complete("rule_id", "mob") == ["MOB-1", "MOB-2", "MOB-3", "MOB-4"]
    text = mcp.get_prompt("check_referral", {"patient": "C:/packets/fax-1.pdf"})["messages"][0]["content"]["text"]
    assert 'path "C:/packets/fax-1.pdf"' in text
    assert mcp.call_tool("review_referral_packet", {}).startswith("Give the full path")
    assert mcp.call_tool("review_referral_packet", {"path": "C:/Windows/win.ini"}).startswith("Blocked")
