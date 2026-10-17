"""Production mode: IHH's secure setup with real referrals. No practice data, no "blacked out" wording,
and a name on a page is expected, not a stop. Referrals still come in by drag and drop and the inbox."""

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("CAREBRIDGE_DB", os.path.join(tempfile.mkdtemp(), "test.db"))

from PIL import Image  # noqa: E402

from carebridge import config, intake, llm, rules  # noqa: E402
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
    for p in (intake.SORT_PROMPT, intake.READ_PROMPT, intake.RULES_PROMPT):
        live = intake._system(p)
        assert "de-identified" not in live and "Dates are blacked out" not in live
        assert "may show the patient's name" in live


def test_a_visible_name_is_not_a_stop_in_production(monkeypatch):
    def fake(system, content, schema, **kw):
        nums = [int(x["text"].split()[1].rstrip(":")) for x in content if x["type"] == "text" and x["text"].startswith("Page ")]
        if "label it" in system:
            return {"pages": [{**PAGES[1], "page": n, "possible_unredacted_identifier": True,
                               "instructions_to_ai": False} for n in nums]}
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

    def get(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"{}") if "json" in r.headers.get("Content-Type", "") else {}
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
        assert get("/api/profiles")[0] == 200
        assert get("/api/scenarios")[1]["scenarios"]

        monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "1")
        st = get("/api/state")[1]
        assert st["production"] is True and st["real_packets"] == []
        for path, body in (("/api/demo", {}), ("/api/clock", {"speed": 60}), ("/api/profiles", None),
                           ("/api/profiles/S01", None), ("/static/profiles.html", None)):
            assert get(path, body) == (404, {"error": "practice_off"}), path
        assert get("/api/scenarios")[1] == {"scenarios": [], "examples": {}}
    finally:
        srv.shutdown()
