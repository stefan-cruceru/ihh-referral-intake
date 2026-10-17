"""One local store for the outcome log and the audit trail (docs/closed-loop.md section 3).

A SQLite file on IHH's own machine. It holds case numbers, times, owners, routes, decisions,
outcomes and reasons. It never holds packet pages, quotes or anything else from the chart.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from .paths import user_dir

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

FIELDS = ["case_no", "channel", "arrived_at", "owner", "suggested_route", "status", "decision", "decided_by",
          "decided_at", "minutes", "withdraw_reason", "patient_arrived", "override", "override_reason",
          "review_usd", "practice"]

# The audit log: who did what, what was approved, and each step the AI took. Append-only and sealed
# (see _seal). Like the rest of this file it holds no packet text, quotes or clinical notes.
AUDIT_FIELDS = ["seq", "t", "case_no", "who", "role", "what", "detail", "practice"]

# Staff alerts (notify.py). Drafts only: the status says whether a person sent it, never the app.
NOTE_FIELDS = ["case_no", "card_id", "event", "person", "channel", "lang", "urgency", "to", "subject", "body",
               "card", "teams_link", "ready", "practice", "ctx"]


def db_path() -> Path:
    return Path(os.environ.get("CAREBRIDGE_DB") or user_dir() / "outcomes.db")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(db_path(), check_same_thread=False)
        _conn.execute(f"CREATE TABLE IF NOT EXISTS outcomes ({', '.join(f + ' PRIMARY KEY' if f == 'case_no' else f for f in FIELDS)})")
        _conn.execute(f"CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, {', '.join(AUDIT_FIELDS[1:])}, prev TEXT, hash TEXT)")
        # Append-only: the database itself refuses to change or remove a row, whoever asks.
        for op in ("UPDATE", "DELETE"):
            _conn.execute(f"CREATE TRIGGER IF NOT EXISTS audit_no_{op.lower()} BEFORE {op} ON audit "
                          "BEGIN SELECT RAISE(ABORT, 'the audit log cannot be changed'); END")
        _conn.execute("CREATE TABLE IF NOT EXISTS people (name TEXT PRIMARY KEY, role TEXT, email TEXT, teams TEXT, channel TEXT, lang TEXT)")
        text_cols = ", ".join(f'"{n}" TEXT' for n in NOTE_FIELDS if n not in ("ready", "practice"))
        _conn.execute(f"CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, key TEXT UNIQUE, t REAL, {text_cols}, "
                      "ready INTEGER, practice INTEGER, status TEXT DEFAULT 'draft', done_by TEXT, done_at REAL)")
        _conn.commit()
    return _conn


def save_card(card: dict) -> None:
    row = {f: card.get(f) for f in FIELDS}
    row["practice"] = 1 if card.get("practice") else 0
    with _lock:
        c = conn()
        c.execute(f"INSERT OR REPLACE INTO outcomes ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                  [row[f] for f in FIELDS])
        c.commit()


def _audit_key() -> bytes:
    f = db_path().with_name("audit.key")
    if not f.is_file():
        f.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    return f.read_bytes()


def _seal(prev: str, row: dict) -> str:
    """Link each present row to its predecessor with an HMAC. Changes break subsequent seals;
    deleting a suffix leaves a valid prefix, so this does not prove the log is complete."""
    body = json.dumps([prev] + [row[f] for f in AUDIT_FIELDS], separators=(",", ":"), ensure_ascii=False)
    return hmac.new(_audit_key(), body.encode(), hashlib.sha256).hexdigest()


def append_audit(case_no: str | None, who: str, role: str | None, what: str, detail: str, practice: bool,
                 t: float | None = None) -> None:
    """Add one line to the audit log. There is no function to change or remove one."""
    with _lock:
        c = conn()
        last = c.execute("SELECT seq, hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        row = {"seq": (last[0] + 1) if last else 1, "t": t or time.time(), "case_no": case_no, "who": who or "",
               "role": role or "", "what": what, "detail": detail or "", "practice": 1 if practice else 0}
        prev = last[1] if last else ""
        c.execute(f"INSERT INTO audit ({', '.join(AUDIT_FIELDS)}, prev, hash) VALUES ({', '.join('?' * (len(AUDIT_FIELDS) + 2))})",
                  [row[f] for f in AUDIT_FIELDS] + [prev, _seal(prev, row)])
        c.commit()


def read_audit(case_no: str | None = None, include_practice: bool = True, limit: int = 1000) -> list[dict]:
    q, args = "SELECT * FROM audit WHERE (practice = 0 OR ?)", [1 if include_practice else 0]
    if case_no:
        q, args = q + " AND case_no = ?", args + [case_no]
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(q + " ORDER BY seq DESC LIMIT ?", args + [limit])]
        c.row_factory = None
    for r in rows:
        r["practice"] = bool(r["practice"])
    return rows


def verify_audit() -> dict:
    """Check seals of stored rows; `broken_at` is the first mismatch. No trusted external head is
    recorded, so removal of a valid suffix or the entire log cannot be detected here."""
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY seq")]
        c.row_factory = None
    prev = ""
    for i, r in enumerate(rows, 1):
        if r["seq"] != i or r["prev"] != prev or not hmac.compare_digest(r["hash"] or "", _seal(prev, r)):
            return {"ok": False, "rows": len(rows), "broken_at": r["seq"]}
        prev = r["hash"]
    return {"ok": True, "rows": len(rows), "broken_at": None}


def weekly_report(days: int = 7, include_practice: bool = False) -> dict:
    """Share answered within 2 hours, withdrawals and why, overrides, cost: what IHH asked to see."""
    since = time.time() - days * 86400
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM outcomes WHERE arrived_at >= ? AND (practice = 0 OR ?)", (since, 1 if include_practice else 0))]
        c.row_factory = None
    decided = [r for r in rows if r["decision"] in ("accepted", "denied")]
    withdrawn = [r for r in rows if r["status"] == "withdrawn"]
    reasons: dict[str, int] = {}
    for r in withdrawn:
        reasons[r["withdraw_reason"] or "unknown"] = reasons.get(r["withdraw_reason"] or "unknown", 0) + 1
    accepted = [r for r in rows if r["decision"] == "accepted"]
    return {
        "days": days, "referrals": len(rows), "decided": len(decided),
        "within_2h": sum(1 for r in decided if (r["minutes"] or 0) <= 120),
        "withdrawn": len(withdrawn), "withdraw_reasons": reasons,
        "accepted": len(accepted), "arrived": sum(1 for r in accepted if r["patient_arrived"] == 1),
        "overrides": [{"case_no": r["case_no"], "route": r["suggested_route"], "decision": r["decision"],
                       "reason": r["override_reason"]} for r in rows if r["override"]],
        "review_usd": round(sum(r["review_usd"] or 0 for r in rows), 2),
    }


def list_people() -> list[dict]:
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM people ORDER BY role, name")]
        c.row_factory = None
    return rows


def save_person(p: dict) -> None:
    with _lock:
        c = conn()
        c.execute("INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?)",
                  (p["name"], p["role"], p["email"], p["teams"], p["channel"], p["lang"]))
        c.commit()


def add_notification(key: str, row: dict) -> bool:
    """False when this alert was already drafted."""
    vals = [json.dumps(row[f]) if f in ("card", "ctx") and row.get(f) else row.get(f) for f in NOTE_FIELDS]
    vals[NOTE_FIELDS.index("ready")] = 1 if row.get("ready") else 0
    vals[NOTE_FIELDS.index("practice")] = 1 if row.get("practice") else 0
    cols = ", ".join(f'"{f}"' for f in NOTE_FIELDS)
    with _lock:
        c = conn()
        cur = c.execute(f"INSERT OR IGNORE INTO notifications (key, t, {cols}) VALUES (?, ?, {', '.join('?' * len(NOTE_FIELDS))})",
                        [key, time.time(), *vals])
        c.commit()
        return cur.rowcount == 1


def list_notifications(person: str | None, include_done: bool, include_practice: bool) -> list[dict]:
    q, args = "SELECT * FROM notifications WHERE (practice = 0 OR ?)", [1 if include_practice else 0]
    if person:
        q, args = q + " AND person = ?", args + [person]
    if not include_done:
        q += " AND status = 'draft'"
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(q + " ORDER BY t DESC LIMIT 500", args)]
        c.row_factory = None
    for r in rows:
        r["ready"], r["practice"] = bool(r["ready"]), bool(r["practice"])
    return rows


def get_notification(nid: int) -> dict | None:
    with _lock:
        c = conn()
        c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM notifications WHERE id = ?", (nid,)).fetchone()
        c.row_factory = None
    return dict(r) if r else None


def mark_notification(nid: int, status: str, who: str, t: float) -> None:
    with _lock:
        c = conn()
        c.execute("UPDATE notifications SET status = ?, done_by = ?, done_at = ? WHERE id = ?", (status, who, t, nid))
        c.commit()
