"""The Access and roles page: practice accounts anyone can add, role changes only a lead or admin
can make (and only for practice people), the Microsoft sign-in explained until IT connects it."""

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
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"
os.environ["CAREBRIDGE_AUTH"] = "practice"

from carebridge import auth  # noqa: E402


def _serve():
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def _client(base):
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, data=None, form=False):
        body, headers = None, {}
        if data is not None:
            body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        return web.open(urllib.request.Request(base + path, data=body, headers=headers))

    return call


def _code(fn):
    try:
        fn()
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def test_roles_edit_is_lead_or_admin_only():
    assert set(auth.PERMISSIONS["roles_edit"]) == {"lead", "admin"}
    assert auth.PERMISSIONS["act:denied"] == ("clinical",)


def test_add_practice_person_checks_input():
    for name, email, role in (("", "x@ihh.example.org", "lead"), ("Pat", "not-an-email", "lead"),
                              ("Pat", "pat@ihh.example.org", "boss"), ("Bea", "bea.coordinator@ihh.example.org", "lead")):
        try:
            auth.add_practice_person(name, email, role)
            raise AssertionError(f"accepted {name!r} {email!r} {role!r}")
        except ValueError:
            pass


def test_sign_in_page_shows_microsoft_and_explains_it_until_connected():
    base = _serve()
    call = _client(base)
    page = call("/auth/signin").read().decode()
    assert "/auth/microsoft" in page and "Add a practice person" in page
    how = call("/auth/microsoft").read().decode()
    assert "login.microsoftonline.com" in how and "CareBridge.Clinical" in how


def test_create_a_practice_person_then_lead_changes_their_role():
    base = _serve()
    pat = _client(base)
    pat("/auth/practice/add", {"name": "Pat Practice", "email": "pat.practice@ihh.example.org", "role": "coordinator", "next": "/"}, form=True)
    me = json.load(pat("/api/me"))
    assert me["name"] == "Pat Practice" and me["role"] == "coordinator"
    # a coordinator can see the page but can't change roles, not even their own
    acc = json.load(pat("/api/access"))
    assert acc["can_edit"] is False and any(p["email"] == "pat.practice@ihh.example.org" for p in acc["people"])
    assert _code(lambda: pat("/api/access/people", {"email": "pat.practice@ihh.example.org", "role": "clinical"})) == 403
    # a lead can, and it applies to Pat's open session at once
    lead = _client(base)
    lead("/auth/practice", {"email": "avery.lead@ihh.example.org", "next": "/"}, form=True)
    assert json.load(lead("/api/access"))["can_edit"] is True
    lead("/api/access/people", {"email": "pat.practice@ihh.example.org", "role": "clinical"})
    me = json.load(pat("/api/me"))
    assert me["role"] == "clinical" and "act:denied" in me["can"]


def test_roles_come_from_entra_once_microsoft_is_connected():
    os.environ["CAREBRIDGE_TEAMS_TENANT"] = "00000000-0000-0000-0000-000000000000"
    os.environ["CAREBRIDGE_TEAMS_CLIENT_ID"] = "11111111-1111-1111-1111-111111111111"
    try:
        assert auth.mode() == "teams"
        for fn in (lambda: auth.set_role("bea.coordinator@ihh.example.org", "lead"),
                   lambda: auth.add_practice_person("Pat", "pat2@ihh.example.org", "lead")):
            try:
                fn()
                raise AssertionError("changed a role outside Entra")
            except PermissionError:
                pass
    finally:
        del os.environ["CAREBRIDGE_TEAMS_TENANT"], os.environ["CAREBRIDGE_TEAMS_CLIENT_ID"]
