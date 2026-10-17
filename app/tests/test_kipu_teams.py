"""Kipu connector against the practice Kipu, Teams sign-in rules and signed links, end to end."""

import base64
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import types
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
_tmp = tempfile.mkdtemp()
os.environ["CAREBRIDGE_DB"] = os.path.join(_tmp, "test.db")  # never touch the real log
os.environ["LOCALAPPDATA"] = _tmp  # settings, link key: a throwaway folder
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"
os.environ["CAREBRIDGE_AUTH"] = "practice"

from carebridge import auth, intake, kipu, kipu_mock, rules, teams, tracker  # noqa: E402


def _packet() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Made-up referral for a test. Pt ambulates 150 ft with rolling walker.")
    return bytes(pdf.output())


def _seed() -> dict:
    """Made-up records for the practice Kipu: 4 in care at the practice sites, 2 referrals with a packet."""
    recs = {}
    for i in range(6):
        kid = f"K-{1001 + i}"
        in_care = i < 4
        recs[kid] = {"id": kid, "first_name": "Test", "last_name": f"Person{i + 1}", "dob": f"01/0{i + 1}/1960",
                     "status": "admitted" if in_care else "pre_admission",
                     "location_name": kipu_mock.SITES[i % len(kipu_mock.SITES)] if in_care else None,
                     "referral_source": "Practice Hospital", "care_team": [],
                     "documents": [] if in_care else [{"id": f"{kid}-referral", "name": f"{kid}-referral.pdf",
                                                       "content_type": "application/pdf",
                                                       "data": base64.b64encode(_packet()).decode()}]}
    return recs


kipu_mock.ensure_running().records.update(_seed())


def _report() -> dict:
    """A finished review with one blocker on page 1, built the way a live review is (quality_control)."""
    facts = [{"id": "F1", "page": 1, "topic": "adl", "statement": "s", "statement_es": "s", "quote": "q", "verify": "found"}]
    statuses = {rid: "met" for rid in rules.assessed_rule_ids()}
    statuses["ADL-1"] = "not_met"
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


def test_signature_matches_and_bad_secret_is_refused():
    c = kipu.client()
    assert c.get("census")["patients"]
    bad = kipu.Client(c.base, c.access_id, "wrong-secret", c.app_id)
    try:
        bad.get("census")
        raise AssertionError("bad signature accepted")
    except kipu.KipuError as e:
        assert "401" in str(e)


def test_census_and_pending():
    s = kipu.census()
    assert s["total"] == 4 and sum(s["by_site"].values()) == 4
    assert len(kipu.pending_referrals()) == 2


def test_returning_client_check_needs_all_three_identifiers():
    rec = next(r for r in kipu_mock.ensure_running().records.values() if r["status"] == "admitted")
    assert kipu.find_existing(rec["first_name"], rec["last_name"], rec["dob"])
    assert not kipu.find_existing(rec["first_name"], rec["last_name"], "01/01/1900")


def test_default_is_practice_kipu_never_live():
    old = os.environ.pop("CAREBRIDGE_KIPU_MODE")
    try:
        assert kipu.mode() == "mock"
    finally:
        os.environ["CAREBRIDGE_KIPU_MODE"] = old


def test_writes_are_off_until_turned_on():
    try:
        kipu.create_chart({"Referral number": "T-1"}, "Bea")
        raise AssertionError("wrote without kipu_write")
    except kipu.KipuError as e:
        assert "turned off" in str(e)


def test_only_clinical_role_can_deny_when_signed_in():
    t = tracker.Tracker()
    c = t.add({"case_no": "T-9"})
    try:
        t.act(c["id"], "denied", "Clinical line", "x", role="coordinator")  # a name can't grant the role
        raise AssertionError("coordinator denied")
    except ValueError:
        pass
    assert t.act(c["id"], "denied", "Rene", "ADL-2 p.6", role="clinical")["status"] == "denied"


def test_signed_in_handoff_goes_to_the_target_and_logs_the_actor():
    t = tracker.Tracker()
    c = t.add({"case_no": "T-10"})
    t.act(c["id"], "handoff", "Bea", "", role="coordinator", target="Dana")
    assert t.cards[c["id"]]["owner"] == "Dana"
    assert t.audit[-1]["who"] == "Bea" and "Dana" in t.audit[-1]["detail"]


def test_signed_links_are_tamper_proof_and_one_time():
    tok = auth.make_link_token("C-1", "denied", "rene.clinical@ihh.example.org")
    assert auth.read_link_token(tok)["a"] == "denied"
    body, sig = tok.split(".")
    assert auth.read_link_token(body + "." + sig[:-2] + "AA") is None
    assert auth.use_link_token(tok) and not auth.use_link_token(tok)
    assert auth.read_link_token(auth.make_link_token("C-1", "open", "x@y", hours=-1)) is None


def test_teams_card_has_no_names_and_links_are_personal():
    rep = _report()
    to = next(s for s in auth.staff() if s["role"] == "clinical")
    card = teams.review_card({"case_no": "DEMO-101"}, rep, to, "http://127.0.0.1:1")
    text = json.dumps(card)
    assert "PERSON" not in text.upper() and "1960" not in text
    for a in card["actions"]:
        data = auth.read_link_token(a["url"].rsplit("/go/", 1)[1])
        assert data["e"] == to["email"] and data["c"] == "DEMO-101"


def _serve():
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", webapp


def test_sign_in_sync_and_teams_link_end_to_end():
    base, webapp = _serve()
    jar = http.cookiejar.CookieJar()
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(path, data=None, form=False):
        body = None
        headers = {}
        if data is not None:
            body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        return web.open(urllib.request.Request(base + path, data=body, headers=headers))

    try:
        call("/api/queue")
        raise AssertionError("queue open without sign-in")
    except urllib.error.HTTPError as e:
        assert e.code == 401
    call("/auth/practice", {"email": "bea.coordinator@ihh.example.org", "next": "/"}, form=True)
    assert json.load(call("/api/me"))["role"] == "coordinator"
    added = json.load(call("/api/kipu/sync", {}))["added"]
    assert len(added) == 2
    cid = added[0]
    assert cid in webapp.PACKETS  # the referral's packet came over from Kipu
    rep = _report()
    webapp.REVIEWS[cid] = types.SimpleNamespace(report=rep, stage="done", progress=[], pages=None)
    webapp.TRACK.attach_review(cid, rep)
    card = json.load(call(f"/api/cards/{cid}/teams-card"))
    deny_url = next(a["url"] for a in card["card"]["actions"] if "no" in a["title"].lower())
    path = urllib.parse.urlparse(deny_url).path
    try:
        call(path, {"reason": "x"}, form=True)  # Bea is not the clinical reviewer
        raise AssertionError("someone else's link worked")
    except urllib.error.HTTPError as e:
        assert e.code == 403
    call("/auth/signout")
    call("/auth/practice", {"email": "rene.clinical@ihh.example.org", "next": "/"}, form=True)
    call(path, {"reason": "ADL-1 not met p.11"}, form=True)
    assert webapp.TRACK.cards[cid]["status"] == "denied"
    assert webapp.TRACK.cards[cid]["decision_reason"].endswith("(from Teams link)")
