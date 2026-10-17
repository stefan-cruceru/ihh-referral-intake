"""Microsoft Teams: sign in with the Teams work account, and act on a referral from a Teams chat.

Sign-in (auth mode "teams") is Microsoft Entra ID's standard sign-in for an installed app: the
authorization-code flow with PKCE, no client secret, redirect to this app on localhost. IHH IT
registers the app once and gives two IDs (CAREBRIDGE_TEAMS_TENANT, CAREBRIDGE_TEAMS_CLIENT_ID).
The ID token comes straight from Microsoft's token endpoint over HTTPS, so it is read, not
re-verified. We check it is for our app and IHH's tenant. Roles come from the token's Entra app
roles when IT has assigned them (auth.roles_from_claims), otherwise from IHH's staff list.

Teams chat cards: the clinical reviewer is already pinged in Teams today. review_card() builds an
Adaptive Card for that chat. Its buttons are links back to this app, each signed for one person,
one action and one referral. Clicking one asks the person to sign in (with Teams in a pilot) and
confirm, so the Teams account is what authorizes the action. Nothing posts to Teams on its own:
the card is a draft a person pastes or a pilot's Power Automate flow posts.
"""

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request

from . import auth, config, notify

AUTHORITY = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
_pending: dict[str, dict] = {}  # state -> {verifier, nonce, next, t}


def settings() -> tuple[str | None, str | None]:
    s = config.load_settings()
    return (os.environ.get("CAREBRIDGE_TEAMS_TENANT") or s.get("teams_tenant"),
            os.environ.get("CAREBRIDGE_TEAMS_CLIENT_ID") or s.get("teams_client_id"))


def sign_in_url(redirect_uri: str, next_path: str = "/") -> str:
    tenant, client_id = settings()
    if not (tenant and client_id):
        raise RuntimeError("Teams sign-in needs IHH's tenant ID and the app's client ID (Settings).")
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state, nonce = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    _pending[state] = {"verifier": verifier, "nonce": nonce, "next": next_path, "t": time.time()}
    q = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "response_mode": "query",
         "scope": "openid profile email", "state": state, "nonce": nonce,
         "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"}
    return AUTHORITY.format(tenant=tenant) + "/authorize?" + urllib.parse.urlencode(q)


def finish_sign_in(code: str, state: str, redirect_uri: str) -> tuple[dict, str]:
    """Trade the code for an ID token, check it, and return (staff person, where to go next)."""
    p = _pending.pop(state, None)
    if not p or time.time() - p["t"] > 600:
        raise PermissionError("Sign-in took too long or did not start here. Try again.")
    tenant, client_id = settings()
    form = urllib.parse.urlencode({"client_id": client_id, "grant_type": "authorization_code", "code": code,
                                   "redirect_uri": redirect_uri, "code_verifier": p["verifier"],
                                   "scope": "openid profile email"}).encode()
    req = urllib.request.Request(AUTHORITY.format(tenant=tenant) + "/token", data=form,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        tok = json.loads(r.read())
    payload = tok["id_token"].split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    if claims.get("aud") != client_id or claims.get("tid") != tenant or claims.get("nonce") != p["nonce"]:
        raise PermissionError("That sign-in was not for this app.")
    email = claims.get("preferred_username") or claims.get("email") or ""
    roles = auth.roles_from_claims(claims)
    if roles is not None:
        # IHH's Entra app roles decide what this person may do.
        if not roles:
            raise PermissionError("You signed in, but IHH has not given you a Care Bridge role. Ask IT to assign one.")
        return {"email": email, "name": claims.get("name") or email, "role": auth.primary_role(roles),
                "roles": roles, "from": "entra"}, p["next"]
    person = auth.lookup(email)
    if not person:
        raise PermissionError("You signed in, but you are not on the referral team's staff list. Ask your lead.")
    return {**person, "roles": [person["role"]], "from": "staff_list"}, p["next"]


# ---- Teams chat cards -----------------------------------------------------------------------

def review_card(card: dict, report: dict, to: dict, base_url: str, lang: str = "en") -> dict:
    """An Adaptive Card for one person's Teams chat. No names or chart text: the case number, the
    suggested route, the gates and the rule IDs with page numbers. Details open in the app."""
    es = lang == "es"
    rec = report["recommendation"]
    route = {"likely_no": ("Looks like a no. Please check.", "Parece que no. Por favor revise."),
             "clinical_check": ("Please take a clinical look.", "Por favor haga una revisión clínica."),
             "needs_info": ("Needs more from the hospital.", "Falta información del hospital."),
             "likely_yes": ("Looks like a yes.", "Parece que sí.")}[rec["code"]][1 if es else 0]
    gate = {"met": ("Yes", "Sí"), "not_met": ("No", "No"), "cant_tell": ("Can't tell", "No se sabe"),
            "not_applicable": ("n/a", "n/a")}
    pages = {f["id"]: f["page"] for f in report["facts"]}
    flags = [f"{r['rule_id']} (p. {', '.join(str(pages[i]) for i in r['fact_ids'] if i in pages) or '-'})"
             for r in report["rules"] if r["rule_id"] in rec["blockers"] or r["rule_id"] in rec["human_review"]]

    def link(action):
        return f"{base_url.rstrip('/')}/go/{auth.make_link_token(card['case_no'], action, to['email'])}"

    # Start from the staff-alert card (notify.py) so every Teams card looks the same, then add the
    # gates, the rule IDs and the signed action buttons.
    urgency = "urgent" if rec["code"] in ("likely_no", "clinical_check") else "soon"
    out = notify.adaptive_card(route, urgency, lang, card["case_no"], link("open"))
    actions = out["actions"]
    if to.get("role") == "clinical":
        actions += [{"type": "Action.OpenUrl", "title": "I agree: say no" if not es else "Estoy de acuerdo: decir que no", "url": link("denied")},
                    {"type": "Action.OpenUrl", "title": "OK to say yes" if not es else "Se puede decir que sí", "url": link("accepted")}]
    actions.append({"type": "Action.OpenUrl", "title": "I have it" if not es else "Yo lo tengo", "url": link("clinical_pickup" if to.get("role") == "clinical" else "open")})
    out["body"][2:2] = [
        {"type": "FactSet", "facts": [
            {"title": "Puede cuidarse solo/a" if es else "Can care for themselves", "value": gate[report["gates"]["self_care"]["status"]][1 if es else 0]},
            {"title": "Tranquilo/a y seguro/a" if es else "Calm and safe", "value": gate[report["gates"]["behavior"]["status"]][1 if es else 0]},
            {"title": "Reglas" if es else "Rules", "value": ", ".join(flags) or "-"}]},
        {"type": "TextBlock", "text": ("Solo para " if es else "Only for ") + to["name"] +
         (". El enlace pide iniciar sesión con Teams." if es else ". The link asks you to sign in with Teams."),
         "isSubtle": True, "wrap": True, "size": "Small"},
    ]
    return out
