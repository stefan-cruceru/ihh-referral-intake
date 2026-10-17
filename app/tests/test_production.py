"""Production mode: IHH's secure setup with real referrals. No practice data, no "blacked out" wording,
and a name on a page is expected, not a stop. Referrals still come in by drag and drop and the inbox."""

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

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("CAREBRIDGE_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

from PIL import Image  # noqa: E402

from carebridge import auth, config, intake, llm, rules, store  # noqa: E402
from carebridge.pages import Page  # noqa: E402
from tests.test_core import all_met  # noqa: E402
from tests.test_queue import PAGES  # noqa: E402

STRINGS = json.loads((APP / "carebridge" / "web" / "strings.json").read_text(encoding="utf-8"))


def test_production_is_off_unless_asked(monkeypatch):
    monkeypatch.delenv("CAREBRIDGE_PRODUCTION", raising=False)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    assert not config.production()
    for on in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", on)
        assert config.production()
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
    monkeypatch.setattr(config, "load_settings", lambda: {"production": True})
    assert not config.production()  # the environment wins over settings
    monkeypatch.delenv("CAREBRIDGE_PRODUCTION")
    assert config.production()


def test_prompts_drop_the_blacked_out_wording_only_in_production(monkeypatch):
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
    assert intake._system(intake.READ_PROMPT) == intake.READ_PROMPT
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "1")
    for p in (intake.SORT_PROMPT, intake.READ_PROMPT, intake.SECOND_READ_PROMPT, intake.RULES_PROMPT):
        live = intake._system(p)
        assert "de-identified" not in live and "Dates are blacked out" not in live
        assert "may show the patient's name" in live


def test_a_visible_name_is_not_a_stop_in_production(monkeypatch):
    def fake(system, content, schema, **kw):
        nums = [int(x["text"].split()[1].rstrip(":")) for x in content if x["type"] == "text" and x["text"].startswith("Page ")]
        if "label it" in system:
            return {"pages": [{**PAGES[1], "page": n, "possible_unredacted_identifier": True,
                               "instructions_to_ai": False} for n in nums]}
        if "You are the second reader" in system:
            return {"pages": [{"page": n, "transcript": "Pt walks 150 ft"} for n in nums]}
        if "Read each page image" in system:
            return {"pages": [{"page": n, "summary": "s", "transcript": "Pt walks 150 ft", "handwriting": "none",
                               "ocr_confidence": 95, "facts": [{"topic": "adl", "statement": "s", "statement_es": "s",
                                                                "quote": "walks 150 ft"}]} for n in nums]}
        if "verdict" not in json.dumps(schema):
            return {"reason_for_referral": "x", "reason_for_referral_es": "x", "wheelchair_dependent": "no",
                    "preferred_language": "", "diagnoses": [], "conflicts": [], "questions": [], "summary": "",
                    "summary_es": "", "checklist": [{"doc_id": d, "status": "present", "pages": [1]} for d in rules.checklist_ids()],
                    "rules": [{"rule_id": r, "status": st, "fact_ids": ["F1"] if st in ("met", "not_met") else [],
                               "explanation": "", "explanation_es": ""} for r, st in all_met().items()]}
        return {"checks": [{"fact_id": "F1", "verdict": "found"}]}

    monkeypatch.setattr(llm, "call_json", fake)
    for on, stop in (("0", [1]), ("1", [])):
        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", on)
        rep = intake.run(intake.Review([Page(1, Image.new("L", (200, 260), 255))], "named.pdf"), workers=1)
        assert rep["flags"]["phi_pages"] == stop


def test_every_production_string_replaces_a_real_one_in_both_languages():
    prod = [k for k in STRINGS if k.endswith("_prod")]
    assert "drop_hint_prod" in prod and "queue_empty_prod" in prod
    for k in prod:
        assert k[:-5] in STRINGS, k
        assert STRINGS[k]["en"] and STRINGS[k]["es"], k
        assert not any(w in STRINGS[k]["en"].lower() for w in ("blacked out", "made-up", "practice")), k
        assert not any(w in STRINGS[k]["es"].lower() for w in ("tachad", "inventad", "práctica")), k


def test_server_has_no_practice_data_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("CAREBRIDGE_AUTH", "off")
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    token = auth.start_session({"email": "lead@example.org", "name": "Mock Teams lead", "role": "lead"}, "teams")

    def get(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Cookie": f"{auth.COOKIE}={token}"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"{}") if "json" in r.headers.get("Content-Type", "") else {}
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
        assert get("/api/scenarios")[1]["scenarios"]

        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "1")
        monkeypatch.setenv("CAREBRIDGE_TEAMS_TENANT", "mock-tenant")
        monkeypatch.setenv("CAREBRIDGE_TEAMS_CLIENT_ID", "mock-client")
        st = get("/api/state")[1]
        assert st["production"] is True and st["real_packets"] == []
        # The practice patients, the demo board and its fast clock were removed: the POSTs are not
        # listed routes, so they are refused, and the pages are not there.
        for path, body in (("/api/demo", {}), ("/api/clock", {"speed": 60})):
            assert get(path, body)[1]["error"] == "not_allowed", path
        for path in ("/api/profiles", "/api/profiles/S01", "/static/profiles.html"):
            assert get(path)[0] == 404, path
        assert get("/api/scenarios")[1] == {"scenarios": [], "examples": {}}
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.parametrize("asked", ["off", "practice", "teams"])
def test_production_requires_teams_even_before_it_setup(monkeypatch, asked):
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "1")
    monkeypatch.setenv("CAREBRIDGE_AUTH", asked)
    monkeypatch.delenv("CAREBRIDGE_TEAMS_TENANT", raising=False)
    monkeypatch.delenv("CAREBRIDGE_TEAMS_CLIENT_ID", raising=False)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    assert auth.mode() == "teams"
    assert auth.session(None) is None


def test_existing_practice_credentials_are_rejected_when_teams_becomes_required(monkeypatch):
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
    monkeypatch.setenv("CAREBRIDGE_AUTH", "practice")
    monkeypatch.delenv("CAREBRIDGE_TEAMS_TENANT", raising=False)
    monkeypatch.delenv("CAREBRIDGE_TEAMS_CLIENT_ID", raising=False)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    person = {"email": "old@example.org", "name": "Old practice person", "role": "admin"}
    tokens = [auth.start_session(person, via) for via in ("practice", "off", "token")]
    for token in tokens:
        assert auth.session(f"{auth.COOKIE}={token}") and auth.bearer_session(f"Bearer {token}")
    monkeypatch.setenv("CAREBRIDGE_TEAMS_TENANT", "mock-tenant")
    monkeypatch.setenv("CAREBRIDGE_TEAMS_CLIENT_ID", "mock-client")
    for token in tokens:
        assert auth.session(f"{auth.COOKIE}={token}") is None
        assert auth.bearer_session(f"Bearer {token}") is None


@pytest.fixture()
def production_server(monkeypatch, tmp_path):
    from carebridge import webapp

    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "1")
    monkeypatch.setenv("CAREBRIDGE_AUTH", "practice")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("CAREBRIDGE_DB", str(tmp_path / "production-test.db"))
    monkeypatch.delenv("CAREBRIDGE_TEAMS_TENANT", raising=False)
    monkeypatch.delenv("CAREBRIDGE_TEAMS_CLIENT_ID", raising=False)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    monkeypatch.setattr(auth, "_sessions", {})
    monkeypatch.setattr(store, "_conn", None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def call(path, data=None, *, cookie=None, bearer=None, form=False):
        headers = {}
        body = None
        if data is not None:
            body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        if cookie:
            headers["Cookie"] = f"{auth.COOKIE}={cookie}"
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        request = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}" + path, data=body, headers=headers)
        try:
            response = opener.open(request)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read().decode("utf-8"), response.headers

    yield call
    srv.shutdown()
    srv.server_close()
    if store._conn:
        store._conn.close()


@pytest.mark.parametrize("path,data,lang", [
    ("/auth/signin", None, "en"),
    ("/auth/microsoft?lang=es", None, "es"),
    ("/auth/practice", {"email": "bea.coordinator@ihh.example.org"}, "en"),
    ("/auth/practice/add?lang=es", {"name": "Mock person", "email": "mock@example.org", "role": "admin"}, "es"),
])
def test_production_signin_without_it_setup_has_no_practice_fallback(production_server, path, data, lang):
    code, page, headers = production_server(path, data, form=True)
    assert code == 503
    assert 'action="/auth/practice' not in page and "bea.coordinator" not in page
    assert "Set-Cookie" not in headers or auth.COOKIE not in headers["Set-Cookie"]
    assert "IHH IT setup required" in page if lang == "en" else "Se requiere configuración de TI de IHH" in page


def test_a_broken_teams_configuration_never_shows_practice_forms(production_server, monkeypatch):
    from carebridge import teams

    monkeypatch.setenv("CAREBRIDGE_TEAMS_TENANT", "mock-tenant")
    monkeypatch.setenv("CAREBRIDGE_TEAMS_CLIENT_ID", "mock-client")
    monkeypatch.setattr(teams, "sign_in_url", lambda *args: (_ for _ in ()).throw(RuntimeError("mock setup failure")))
    code, page, _ = production_server("/auth/signin")
    assert code == 503 and "IHH IT setup required" in page
    assert 'action="/auth/practice' not in page


def test_production_rejects_old_credentials_and_preserves_teams_origin_for_mcp(production_server, monkeypatch):
    monkeypatch.setenv("CAREBRIDGE_TEAMS_TENANT", "mock-tenant")
    monkeypatch.setenv("CAREBRIDGE_TEAMS_CLIENT_ID", "mock-client")
    person = {"email": "mock@example.org", "name": "Mock coordinator", "role": "coordinator"}
    for via in ("practice", "off", "token"):
        old = auth.start_session(person, via)
        assert production_server("/api/me", cookie=old)[0] == 401
        assert production_server("/api/me/token", {}, bearer=old)[0] == 401
    signed_in = auth.start_session(person, "teams")
    assert production_server("/api/me", cookie=signed_in)[0] == 200
    code, body, _ = production_server("/api/me/token", {}, cookie=signed_in)
    assert code == 200
    token = json.loads(body)["token"]
    assert auth.bearer_session(f"Bearer {token}")["auth_origin"] == "teams"
    # Token-to-token minting also retains the verified sign-in origin.
    code, body, _ = production_server("/api/me/token", {}, bearer=token)
    assert code == 200
    assert auth.bearer_session("Bearer " + json.loads(body)["token"])["auth_origin"] == "teams"
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert production_server("/mcp", request, bearer=token)[0] == 200


def test_production_without_it_setup_refuses_existing_teams_session_and_synthetic_staff(production_server):
    signed_in = auth.start_session({"name": "Mock admin", "email": "admin@example.org", "role": "admin"}, "teams")
    assert production_server("/api/me", cookie=signed_in)[0] == 401
    assert auth.staff() == []
