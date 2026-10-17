"""Kipu connector against the practice Kipu, Teams sign-in rules and signed links, end to end."""

import http.cookiejar
import json
import os
import sys
import tempfile
import threading
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

from carebridge import auth, kipu, kipu_mock, teams, tracker  # noqa: E402


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
    assert len(kipu.pending_referrals()) == 6


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


def test_signed_links_are_tamper_proof_and_one_time():
    tok = auth.make_link_token("C-1", "denied", "rene.clinical@ihh.example.org")
    assert auth.read_link_token(tok)["a"] == "denied"
    body, sig = tok.split(".")
    assert auth.read_link_token(body + "." + sig[:-2] + "AA") is None
    assert auth.use_link_token(tok) and not auth.use_link_token(tok)
    assert auth.read_link_token(auth.make_link_token("C-1", "open", "x@y", hours=-1)) is None


def test_teams_card_has_no_names_and_links_are_personal():
    from demo import synthetic

    rep = synthetic.sample_reports()["S06"]
    to = next(s for s in auth.staff() if s["role"] == "clinical")
    card = teams.review_card({"case_no": "DEMO-101"}, rep, to, "http://127.0.0.1:1")
    text = json.dumps(card)
    assert "HENSLEY" not in text.upper() and "LORRAINE" not in text.upper()
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
    assert len(added) == 6
    cid = added[0]
    assert webapp.TRACK.cards[cid].get("sample")  # practice patient got its practice review
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
