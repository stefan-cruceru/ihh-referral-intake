"""Server errors carry a stable code the screen turns into English or Spanish words, and opening the
Kipu page never reads live Kipu on its own."""

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
_tmp = tempfile.mkdtemp()
os.environ["CAREBRIDGE_DB"] = os.path.join(_tmp, "test.db")  # never touch the real log
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_KIPU_MODE"] = "mock"

from carebridge import gateway, kipu, tracker  # noqa: E402

STRINGS = json.loads((APP / "carebridge" / "web" / "strings.json").read_text(encoding="utf-8"))


def test_every_error_code_has_english_and_spanish_words():
    codes = {c for _, c in gateway.ERROR_CODES} | {"server", "ai", "bad_key"}
    for c in codes:
        s = STRINGS.get("err_" + c)
        assert s and s.get("en") and s.get("es"), c


def test_known_messages_get_a_code_and_keep_the_english():
    t = tracker.Tracker()
    c = t.add({"case_no": "T-1"})
    try:
        t.act(c["id"], "denied", "Bea", "x", role="coordinator")
        raise AssertionError("coordinator denied")
    except ValueError as e:
        msg = str(e)
    got = gateway.error(msg)
    assert got["code"] == "only_clinical_deny" and got["error"] == msg
    got = gateway.error("A clinical reviewer must read page(s) 3, 4 before this can be accepted.")
    assert got["code"] == "read_pages" and got["vars"] == {"pages": "3, 4"}
    assert gateway.error("not found") == {"error": "not found", "code": "not_found"}
    assert gateway.error("Something new") == {"error": "Something new"}  # no code: the English is the fallback


class _H:
    def __init__(self, path):
        self.path, self.headers, self.out = path, {}, None

    def _json(self, obj, code=200):
        self.out = obj


def test_live_kipu_is_read_only_after_a_click(monkeypatch):
    reads = []
    monkeypatch.setenv("CAREBRIDGE_KIPU_MODE", "live")
    monkeypatch.setattr(kipu, "census", lambda: reads.append("census") or {"total": 0, "by_site": {}})
    monkeypatch.setattr(kipu, "pending_referrals", lambda: reads.append("pending") or [])
    h = _H("/api/kipu/status")
    gateway._kipu(h, "GET", "/api/kipu/status", ["api", "kipu", "status"])
    assert reads == [] and "census" not in h.out and h.out["mode"] == "live"
    h = _H("/api/kipu/status?load=1")
    gateway._kipu(h, "GET", "/api/kipu/status", ["api", "kipu", "status"])
    assert reads == ["census", "pending"] and h.out["pending"] == 0
