"""Who is signed in, what their role allows, and signed one-time links for Teams cards.

Sign-in modes (setting `auth`, or CAREBRIDGE_AUTH):
  practice  default. Pick a made-up staff member on a local page styled like the Teams sign-in.
            Never calls Microsoft. For demos and training.
  teams     Sign in with the same Microsoft work account people use for Teams (Microsoft Entra ID).
            Needs IHH IT to register the app (tenant and client IDs). See teams.py.
  off       No sign-in (single-user laptop). Actions are not tied to a person.

Roles come from IHH's staff list, not from the sign-in: Microsoft says who you are, the staff list
says what you may do. Only the clinical role can deny a referral (IHH's rule).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

from . import config
from .paths import user_dir

ROLES = ("coordinator", "lead", "clinical", "admin")
SESSION_HOURS = 12
COOKIE = "cb_session"

# Invented staff for practice mode. A pilot replaces this with IHH's list (Settings or staff.json).
PRACTICE_STAFF = [
    {"email": "avery.lead@ihh.example.org", "name": "Avery (lead)", "role": "lead"},
    {"email": "bea.coordinator@ihh.example.org", "name": "Bea", "role": "coordinator"},
    {"email": "carlos.coordinator@ihh.example.org", "name": "Carlos", "role": "coordinator"},
    {"email": "dana.coordinator@ihh.example.org", "name": "Dana", "role": "coordinator"},
    {"email": "rene.clinical@ihh.example.org", "name": "Rene (clinical reviewer)", "role": "clinical"},
]

_sessions: dict[str, dict] = {}
_used_links: set[str] = set()
_lock = threading.Lock()


def mode() -> str:
    m = os.environ.get("CAREBRIDGE_AUTH") or config.load_settings().get("auth") or "practice"
    return m if m in ("practice", "teams", "off") else "practice"


def staff() -> list[dict]:
    """IHH's staff list (email, name, role). Practice mode uses the invented list."""
    f = user_dir() / "staff.json"
    if mode() != "practice" and f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return []
    return PRACTICE_STAFF


def lookup(email: str) -> dict | None:
    e = (email or "").strip().lower()
    return next((s for s in staff() if s["email"].lower() == e), None)


# ---- sessions --------------------------------------------------------------------------------

def start_session(person: dict, via: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {**person, "via": via, "exp": time.time() + SESSION_HOURS * 3600}
    return token


def session(cookie_header: str | None) -> dict | None:
    if mode() == "off":
        return {"email": "", "name": "", "role": "admin", "via": "off"}
    token = _cookie(cookie_header)
    s = _sessions.get(token) if token else None
    if s and s["exp"] > time.time():
        return s
    return None


def end_session(cookie_header: str | None) -> None:
    token = _cookie(cookie_header)
    with _lock:
        _sessions.pop(token, None)


def _cookie(header: str | None) -> str | None:
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None


def set_cookie(token: str) -> str:
    return f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_HOURS * 3600}"


def clear_cookie() -> str:
    return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def can(person: dict | None, action: str) -> bool:
    if person is None:
        return False
    if action == "denied":
        return person.get("role") in ("clinical",)
    return True


# ---- signed one-time links (used by Teams cards) ---------------------------------------------

def _key() -> bytes:
    f = user_dir() / "link.key"
    if not f.is_file():
        f.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    return f.read_bytes()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_link_token(case: str, action: str, email: str, hours: float = 24) -> str:
    """A link only `email` can use, once, for one action on one referral, before it expires."""
    body = _b64(json.dumps({"c": case, "a": action, "e": email.lower(), "x": int(time.time() + hours * 3600),
                            "n": secrets.token_hex(4)}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_link_token(token: str) -> dict | None:
    body, _, sig = token.partition(".")
    want = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, want):
        return None
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if data["x"] < time.time():
        return None
    return data


def use_link_token(token: str) -> bool:
    """Mark a link used. Opening a referral is not one-time; actions are."""
    with _lock:
        if token in _used_links:
            return False
        _used_links.add(token)
        return True
