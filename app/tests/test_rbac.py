"""Who may do what: roles from IHH's Entra app roles (or the staff list), one permission table,
and the server refusing what a role may not do, whatever the screen shows."""

import base64
import http.cookiejar
import io
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
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"
os.environ["CAREBRIDGE_AUTH"] = "practice"

from carebridge import auth, store, teams  # noqa: E402

BEA = {"email": "bea.coordinator@ihh.example.org", "name": "Bea", "role": "coordinator"}
RENE = {"email": "rene.clinical@ihh.example.org", "name": "Rene (clinical reviewer)", "role": "clinical"}
AVERY = {"email": "avery.lead@ihh.example.org", "name": "Avery (lead)", "role": "lead"}
IT = {"email": "it@ihh.example.org", "name": "IT", "roles": ["admin"], "role": "admin"}


def test_entra_app_roles_map_to_our_roles():
    assert auth.roles_from_claims({}) is None  # IT has not set up app roles: staff list decides
    assert auth.roles_from_claims({"roles": ["CareBridge.Clinical", "CareBridge.Lead", "Something.Else"]}) == ["clinical", "lead"]
    assert auth.roles_from_claims({"roles": ["Something.Else"]}) == []
    assert auth.primary_role(["lead", "clinical"]) == "clinical"


def test_permission_table():
    assert not auth.can(BEA, "denied") and auth.can(RENE, "denied")
    assert auth.can(BEA, "accepted") and not auth.can(IT, "accepted") and not auth.can(IT, "denied")
    assert not auth.can(BEA, "people_edit") and auth.can(AVERY, "people_edit") and auth.can(IT, "people_edit")
    assert not auth.can(BEA, "settings") and not auth.can(AVERY, "api_key") and auth.can(IT, "api_key")
    assert not auth.can(RENE, "kipu_find") and auth.can(BEA, "kipu_find")
    assert not auth.can(BEA, "made_up_action")  # unknown actions are refused
    assert not auth.can(None, "accepted")
    assert auth.can(BEA, "demo")  # practice mode: anyone may restart the made-up demo
    # Someone who is both lead and clinical can deny, and tracker.act is told "clinical".
    both = {"name": "Sam", "role": "lead", "roles": ["lead", "clinical"]}
    assert auth.can(both, "denied") and auth.act_role(both) == "clinical"


def _id_token(claims: dict) -> str:
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b(claims)}.sig"


def _fake_sign_in(monkeypatch, extra: dict):
    monkeypatch.setenv("CAREBRIDGE_TEAMS_TENANT", "tenant-1")
    monkeypatch.setenv("CAREBRIDGE_TEAMS_CLIENT_ID", "client-1")
    url = teams.sign_in_url("http://127.0.0.1/auth/callback")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    claims = {"aud": "client-1", "tid": "tenant-1", "nonce": q["nonce"], "name": "Pat Reviewer",
              "preferred_username": "pat@ihh.example.org", **extra}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(teams.urllib.request, "urlopen", lambda req, timeout=0: R(json.dumps({"id_token": _id_token(claims)}).encode()))
    return teams.finish_sign_in("code", q["state"], "http://127.0.0.1/auth/callback")


def test_roles_come_from_the_entra_token(monkeypatch):
    person, _ = _fake_sign_in(monkeypatch, {"roles": ["CareBridge.Clinical"]})
    assert person["roles"] == ["clinical"] and person["from"] == "entra" and auth.can(person, "denied")


def test_signed_in_without_a_care_bridge_role_is_refused(monkeypatch):
    try:
        _fake_sign_in(monkeypatch, {"roles": ["Payroll.Viewer"]})
        raise AssertionError("signed in with no Care Bridge role")
    except PermissionError as e:
        assert "role" in str(e)


def test_no_roles_claim_falls_back_to_the_staff_list(monkeypatch):
    try:
        _fake_sign_in(monkeypatch, {})  # pat@ is not on the practice staff list
        raise AssertionError("signed in without a role or a staff-list entry")
    except PermissionError as e:
        assert "staff list" in str(e)


def _serve():
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", webapp


def _browser(base, email):
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, data=None):
        body, headers = None, {}
        if data is not None:
            body, headers = json.dumps(data).encode(), {"Content-Type": "application/json"}
        try:
            r = web.open(urllib.request.Request(base + path, data=body, headers=headers))
            return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    web.open(urllib.request.Request(base + "/auth/practice", data=urllib.parse.urlencode({"email": email, "next": "/"}).encode(),
                                    headers={"Content-Type": "application/x-www-form-urlencoded"}))
    return call


def test_the_server_refuses_what_a_role_may_not_do():
    base, webapp = _serve()
    bea, avery = _browser(base, BEA["email"]), _browser(base, AVERY["email"])
    assert bea("/api/notify/people", {"name": "Bea", "role": "lead"})[0] == 403  # can't promote herself
    assert bea("/api/settings", {"model": "x"})[0] == 403
    assert bea("/api/not-a-route", {})[0] == 403  # unlisted changes are refused
    assert avery("/api/notify/people", {"name": "Dana", "email": "dana@example.org"})[0] == 200
    me = bea("/api/me")[1]
    assert "people_edit" not in me["can"] and "accepted" not in me["can"] and "act:accepted" in me["can"]

    card = webapp.TRACK.add({"case_no": "RB-1", "owner": "Dana"})
    assert bea(f"/api/cards/{card['id']}/act", {"action": "denied", "reason": "x"})[0] == 403
    assert webapp.TRACK.cards[card["id"]]["status"] != "denied"

    # Alerts: only your own unless you are a lead, and the log names the signed-in person.
    from carebridge import notify

    notify.sync(webapp.TRACK)
    dana = next(r for r in notify.outbox(person="Dana"))
    assert bea(f"/api/notify/{dana['id']}/mark", {"status": "sent_by_person", "who": "Dana"})[0] == 403
    assert avery(f"/api/notify/{dana['id']}/mark", {"status": "sent_by_person", "who": "someone else"})[0] == 200
    assert store.get_notification(dana["id"])["done_by"] == "Avery (lead)"
