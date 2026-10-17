"""Who is signed in, what their role allows, and signed one-time links for Teams cards.

Sign-in modes (setting `auth`, or CAREBRIDGE_AUTH):
  practice  default. Pick a made-up staff member on a local page styled like the Teams sign-in.
            Never calls Microsoft. For demos and training.
  teams     Sign in with the same Microsoft work account people use for Teams (Microsoft Entra ID).
            Needs IHH IT to register the app (tenant and client IDs). See teams.py.
  off       No sign-in (single-user laptop). Actions are not tied to a person.

Roles come from IHH's own Microsoft Entra ID when IT has set up app roles: the sign-in token carries
a `roles` claim (CareBridge.Coordinator, .Lead, .Clinical, .Admin), assigned to people or security
groups in Entra. So who may do what is managed where IHH already manages staff accounts. Without
app roles, IHH's staff list (staff.json) says what each person may do. PERMISSIONS below is the one
place that says which role may do which action; only the clinical role can deny a referral (IHH's rule).
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
# Entra app role values (the `value` field in the app registration) -> our roles.
ENTRA_ROLES = {"CareBridge.Coordinator": "coordinator", "CareBridge.Lead": "lead",
               "CareBridge.Clinical": "clinical", "CareBridge.Admin": "admin"}

_STAFF = ("coordinator", "lead", "clinical")
# Which roles may do what. Admin is IT: settings and people, never a clinical decision.
PERMISSIONS = {
    # the referral board
    "act:open": _STAFF, "act:info_sent": _STAFF, "act:hospital_replied": _STAFF, "act:chase_sent": _STAFF,
    "act:intake_cleared": _STAFF, "act:accepted": _STAFF, "act:withdrawn": _STAFF,
    "act:handoff": ("coordinator", "lead"), "act:patient_arrived": ("coordinator", "lead"),
    "act:denied": ("clinical",), "act:clinical_pickup": ("clinical",),
    "upload": ("coordinator", "lead"), "review": _STAFF, "teams_card": ("coordinator", "lead"),
    "demo": ("lead", "admin"),
    # Kipu
    "kipu_sync": ("coordinator", "lead"), "kipu_find": ("coordinator", "lead"),
    "kipu_write": ("coordinator", "lead"), "kipu_settings": ("lead", "admin"),
    # staff alerts
    "alert_mark": _STAFF + ("admin",), "alert_mark_any": ("lead", "admin"), "people_edit": ("lead", "admin"),
    # settings
    "settings": ("lead", "admin"), "api_key": ("admin",),
    # help for clients, practice, rules: anyone signed in
    "staff_tools": _STAFF + ("admin",),
}
# Practice mode is made-up data: anyone may restart the demo there.
PRACTICE_OPEN = {"demo"}
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
        return {"email": "", "name": "", "role": "admin", "roles": list(ROLES), "via": "off"}
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


def roles_of(person: dict | None) -> set[str]:
    if not person:
        return set()
    return set(person.get("roles") or []) | ({person["role"]} if person.get("role") else set())


def roles_from_claims(claims: dict) -> list[str] | None:
    """Our roles from an Entra ID token's `roles` claim. None when the claim is absent (IT has not
    assigned app roles), so the staff list decides instead. Unknown values are ignored."""
    if "roles" not in claims:
        return None
    return [ENTRA_ROLES[r] for r in claims.get("roles") or [] if r in ENTRA_ROLES]


def primary_role(roles: list[str]) -> str:
    """The one role shown next to a name. Clinical first, since it is the one that can deny."""
    return next((r for r in ("clinical", "lead", "coordinator", "admin") if r in roles), "")


def can(person: dict | None, action: str) -> bool:
    """May this person do this? `action` is a PERMISSIONS key; a bare tracker action like "denied" is
    read as "act:denied". Unknown actions are refused, so a new route must be added to the table."""
    if mode() == "off":
        return True
    if person is None:
        return False
    if action in PRACTICE_OPEN and mode() == "practice":
        return True
    key = action if action in PERMISSIONS else f"act:{action}"
    return bool(roles_of(person) & set(PERMISSIONS.get(key, ())))


def act_role(person: dict | None) -> str | None:
    """The role handed to tracker.act, which enforces "only clinical can deny" for every caller."""
    if person is None:
        return None
    return "clinical" if "clinical" in roles_of(person) else person.get("role")


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
