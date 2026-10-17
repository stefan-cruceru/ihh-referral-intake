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
    "act:clinical_note": ("clinical",), "act:clinical_ask": ("clinical",), "act:clinical_done": ("clinical",),
    # The returning-client and background checks: a person does them outside the tool and ticks them here.
    "act:staff_check": ("coordinator", "lead"),
    "act:viewing": _STAFF + ("admin",), "act:leave": _STAFF + ("admin",), "act:claim": _STAFF,
    "act:kipu_id": ("coordinator", "lead"),
    "upload": ("coordinator", "lead"), "review": _STAFF, "teams_card": ("coordinator", "lead"),
    "demo": ("lead", "admin"),
    # Kipu
    "kipu_sync": ("coordinator", "lead"), "kipu_find": ("coordinator", "lead"),
    "kipu_write": ("coordinator", "lead"), "kipu_settings": ("lead", "admin"),
    # staff alerts
    "alert_mark": _STAFF + ("admin",), "alert_mark_any": ("lead", "admin"), "people_edit": ("lead", "admin"),
    # settings, and who has which role (practice people only; with Entra, roles are changed in Entra)
    "settings": ("lead", "admin"), "api_key": ("admin",), "roles_edit": ("lead", "admin"),
    # the sealed audit log: who did what, what was approved, every AI step. Read-only for everyone.
    "audit_view": ("admin",),
    # a personal token so an agent (Microsoft 365 Copilot) can call /mcp as the person who made it
    "mcp_token": _STAFF + ("admin",),
    # help for clients, practice, rules: anyone signed in
    "staff_tools": _STAFF + ("admin",),
}
# What each MCP tool needs over HTTP (/mcp). Tools not listed need "staff_tools".
MCP_TOOLS = {"review_referral_packet": "review"}

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


def microsoft_configured() -> bool:
    """IHH IT has registered the app in Entra (tenant and client IDs are set). Same keys as teams.py."""
    s = config.load_settings()
    return bool((os.environ.get("CAREBRIDGE_TEAMS_TENANT") or s.get("teams_tenant")) and
                (os.environ.get("CAREBRIDGE_TEAMS_CLIENT_ID") or s.get("teams_client_id")))


def mode() -> str:
    """Once IHH's Microsoft sign-in is set up, it is the only way in: practice sign-in (pick anyone,
    even a made-up clinician) and no sign-in are refused, whatever a setting says. Without it, the
    practice sign-in is the default and "off" is allowed for a single-user laptop. Production
    always requires Teams, including while IT has not finished configuring it."""
    if config.production() or microsoft_configured():
        return "teams"
    m = os.environ.get("CAREBRIDGE_AUTH") or config.load_settings().get("auth") or "practice"
    return m if m in ("practice", "off") else "practice"


def staff() -> list[dict]:
    """IHH's staff list (email, name, role). Practice mode uses the invented list, plus the people
    added on the sign-in page and any role changes made on the Access page."""
    f = user_dir() / "staff.json"
    m = mode()
    if m == "teams" or (m != "practice" and f.is_file()):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
    extra = _practice_extra()
    people = PRACTICE_STAFF + extra["added"]
    return [{**p, "role": extra["roles"].get(p["email"].lower(), p["role"])} for p in people]


# ---- practice people: made-up accounts anyone can add on the sign-in page --------------------

def _practice_file():
    return user_dir() / "practice-staff.json"


def _practice_extra() -> dict:
    try:
        d = json.loads(_practice_file().read_text(encoding="utf-8"))
        return {"added": list(d.get("added") or []), "roles": dict(d.get("roles") or {})}
    except (OSError, ValueError):
        return {"added": [], "roles": {}}


def _save_practice_extra(d: dict) -> None:
    _practice_file().write_text(json.dumps(d, indent=1), encoding="utf-8")


def add_practice_person(name: str, email: str, role: str) -> dict:
    """A made-up account for practice. With IHH's Microsoft sign-in, accounts come from Entra instead."""
    if mode() != "practice":
        raise PermissionError("Accounts come from IHH's Microsoft sign-in. Add people in Microsoft Entra.")
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name or len(name) > 60:
        raise ValueError("Type a name (up to 60 letters).")
    if "@" not in email or " " in email or len(email) > 120:
        raise ValueError("Type a work email, like name@ihh.example.org.")
    if role not in ROLES:
        raise ValueError("Pick a role.")
    if lookup(email):
        raise ValueError("Someone already uses that email.")
    with _lock:
        d = _practice_extra()
        person = {"email": email, "name": name, "role": role}
        d["added"].append(person)
        _save_practice_extra(d)
    return person


def set_role(email: str, role: str) -> dict:
    """Change a practice person's role. It applies at once, also to anyone signed in as them."""
    if mode() != "practice":
        raise PermissionError("Roles come from IHH's Microsoft Entra app roles. Change them in Entra.")
    if role not in ROLES:
        raise ValueError("Pick a role.")
    who = lookup(email)
    if not who:
        raise ValueError("No one with that email.")
    with _lock:
        d = _practice_extra()
        d["roles"][who["email"].lower()] = role
        _save_practice_extra(d)
        for s in _sessions.values():
            if (s.get("email") or "").lower() == who["email"].lower():
                s["role"], s["roles"] = role, [role]
    return {**who, "role": role}


def lookup(email: str) -> dict | None:
    e = (email or "").strip().lower()
    return next((s for s in staff() if s["email"].lower() == e), None)


# ---- sessions --------------------------------------------------------------------------------

def start_session(person: dict, via: str) -> str:
    token = secrets.token_urlsafe(32)
    # A personal MCP token inherits the server-recorded sign-in origin. A practice session can
    # never claim Teams origin, even if its person dictionary happens to contain that field.
    origin = (person.get("auth_origin") or person.get("via") or via) if via == "token" else via
    with _lock:
        _sessions[token] = {**person, "via": via, "auth_origin": origin, "exp": time.time() + SESSION_HOURS * 3600}
    return token


def _current_session(s: dict | None) -> dict | None:
    if not s or s["exp"] <= time.time():
        return None
    if mode() == "teams" and (not microsoft_configured() or (s.get("auth_origin") or s.get("via")) != "teams"):
        return None
    return s


def session(cookie_header: str | None) -> dict | None:
    if mode() == "off":
        return {"email": "", "name": "", "role": "admin", "roles": list(ROLES), "via": "off"}
    token = _cookie(cookie_header)
    return _current_session(_sessions.get(token) if token else None)


def bearer_session(authorization: str | None) -> dict | None:
    """A session from "Authorization: Bearer <token>", for agents calling /mcp. The token is one a
    signed-in person made (/api/me/token), so it carries their identity and roles."""
    kind, _, token = (authorization or "").partition(" ")
    if kind.lower() != "bearer" or not token:
        return None
    return _current_session(_sessions.get(token.strip()))


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
