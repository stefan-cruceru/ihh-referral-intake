"""The admin audit log: who did what, what was approved and every AI step, in a log nobody can edit."""

import csv
import http.cookiejar
import io
import json
import os
import sqlite3
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
_tmp = tempfile.mkdtemp()
os.environ["CAREBRIDGE_DB"] = os.path.join(_tmp, "test.db")  # never touch the real log
os.environ["LOCALAPPDATA"] = _tmp
os.environ["CAREBRIDGE_AUTH"] = "practice"

from carebridge import auth, intake, store, tracker  # noqa: E402


def test_decisions_and_ai_steps_are_logged_with_who_and_role():
    t = tracker.Tracker()
    c = t.add({"case_no": "AU-1", "owner": "Bea"})
    t.attach_review(c["id"], {"recommendation": {"code": "likely_yes", "blockers": [], "route_clinical": False, "odds": 90},
                              "model": "claude-opus-5-5", "cost": {"usd": 0.42}})
    review = intake.Review([], "p.pdf")
    review.on_log = lambda stage, msg: t.log(c["id"], "Claude", f"AI step: {stage}", msg, role="ai")
    review.log("Sorting 12 pages")
    t.act(c["id"], "accepted", "Bea", "all criteria met", role="coordinator")
    rows = store.read_audit(c["id"])
    by_what = {r["what"]: r for r in rows}
    assert by_what["accepted"]["who"] == "Bea" and by_what["accepted"]["role"] == "coordinator"
    assert by_what["accepted"]["detail"] == "all criteria met"
    assert by_what["AI step: queued"]["role"] == "ai" and "12 pages" in by_what["AI step: queued"]["detail"]
    assert "claude-opus-5-5" in by_what["flagged"]["detail"] and "$0.42" in by_what["flagged"]["detail"]
    # Restarting the demo clears the board, not the sealed log.
    t.reset()
    assert store.read_audit(c["id"])
    assert store.verify_audit()["ok"]


def test_the_database_refuses_to_change_or_remove_a_line():
    store.append_audit("AU-2", "Rene", "clinical", "denied", "page 4", practice=True)
    c = sqlite3.connect(store.db_path())
    for sql in ("UPDATE audit SET who = 'someone else'", "DELETE FROM audit"):
        with pytest.raises(sqlite3.DatabaseError, match="cannot be changed"):
            c.execute(sql)
    c.close()
    assert store.verify_audit()["ok"]


def test_editing_the_file_behind_the_apps_back_is_caught():
    store.append_audit("AU-3", "Bea", "coordinator", "accepted", "ok", practice=True)
    seq = store.read_audit("AU-3")[0]["seq"]
    c = sqlite3.connect(store.db_path())
    c.execute("DROP TRIGGER audit_no_update")  # someone with the file and a SQLite tool
    c.execute("UPDATE audit SET what = 'denied' WHERE seq = ?", (seq,))
    c.commit()
    c.close()
    try:
        check = store.verify_audit()
        assert not check["ok"] and check["broken_at"] == seq
    finally:
        # Put the line back for the other tests, and the trigger with it.
        c = sqlite3.connect(store.db_path())
        c.execute("UPDATE audit SET what = 'accepted' WHERE seq = ?", (seq,))
        c.commit()
        c.close()
        store._conn = None
        store.conn()
    assert store.verify_audit()["ok"]


def _serve():
    from carebridge import webapp

    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def _browser(base, email):
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path):
        try:
            r = web.open(base + path)
            return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    web.open(urllib.request.Request(base + "/auth/practice", data=urllib.parse.urlencode({"email": email, "next": "/"}).encode(),
                                    headers={"Content-Type": "application/x-www-form-urlencoded"}))
    return call


def test_only_admins_can_read_it_and_sign_ins_are_logged():
    auth.add_practice_person("Ida IT", "ida.it@ihh.example.org", "admin")
    base = _serve()
    lead, admin = _browser(base, "avery.lead@ihh.example.org"), _browser(base, "ida.it@ihh.example.org")
    assert lead("/api/audit-log")[0] == 403
    code, body = admin("/api/audit-log")
    got = json.loads(body)
    assert code == 200 and got["check"]["ok"]
    assert any(r["what"] == "signed in" and r["who"] == "Avery (lead)" and r["role"] == "lead" for r in got["rows"])
    code, csv = admin("/api/audit-log?format=csv")
    assert code == 200 and csv.decode("utf-8-sig").startswith("seq,t,case_no,who,role,what,detail,practice,hash")


def test_audit_csv_neutralizes_formulas_without_changing_the_log(monkeypatch, tmp_path):
    from carebridge import config, webapp

    monkeypatch.setenv("CAREBRIDGE_AUTH", "practice")
    monkeypatch.setenv("CAREBRIDGE_PRODUCTION", "0")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("CAREBRIDGE_DB", str(tmp_path / "audit-csv.db"))
    monkeypatch.delenv("CAREBRIDGE_TEAMS_TENANT", raising=False)
    monkeypatch.delenv("CAREBRIDGE_TEAMS_CLIENT_ID", raising=False)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    monkeypatch.setattr(auth, "_sessions", {})
    monkeypatch.setattr(store, "_conn", None)
    auth.add_practice_person("=1+1", "csv-test@example.org", "admin")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        admin = _browser(f"http://127.0.0.1:{srv.server_address[1]}", "csv-test@example.org")
        payloads = ("=1+1", "+1+1", "-1+1", "@SUM(1,1)", "\t=1+1", "\r=1+1", "\n=1+1")
        for value in payloads:
            store.append_audit(value, value, value, value, value, practice=True)
        before = store.read_audit()
        code, body = admin("/api/audit-log?format=csv")
        assert code == 200
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline="")))
        exported = {int(r["seq"]): r for r in rows}
        for original in before:
            row = exported[original["seq"]]
            for field in ("case_no", "who", "role", "what", "detail"):
                value = original[field] or ""
                expected = "'" + value if value and value[0] in "=+-@\t\r\n" else value
                assert row[field] == expected, (field, value, row[field])
            assert row["hash"] == original["hash"]
        assert any(r["who"] == "'=1+1" and r["what"] == "signed in" for r in rows)
        # Escaping belongs only to the spreadsheet export; evidence and its hashes remain exact.
        assert store.read_audit() == before
        code, body = admin("/api/audit-log")
        assert code == 200 and json.loads(body)["rows"] == before
        assert store.verify_audit()["ok"]
    finally:
        srv.shutdown()
        srv.server_close()
        if store._conn:
            store._conn.close()
