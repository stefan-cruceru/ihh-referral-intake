"""Staff alerts, per person, by Outlook email and Teams. Drafts only: nothing here sends anything.

Alerts go to IHH staff only (coordinators, the lead, the clinical line), never to patients or
hospitals: which referral to look at, what changed, and how urgent it is. Hospital-facing messages
stay in drafts.py.

Each person picks email, Teams or both, and English or Spanish. Every alert becomes a draft in the
local outbox: an Outlook .eml that opens ready to send (X-Unsent), and for Teams an Adaptive Card
plus a link that opens the chat with the message filled in. A person presses send. In a pilot,
IHH can feed the outbox to its own Power Automate flow inside its own Microsoft 365
(docs/notifications.md); this app never calls Outlook or Teams itself.

An alert carries the case number, hospital, status, minutes left and rule IDs. Never chart text,
quotes or anything about the patient: Teams and inboxes are not where the chart lives.
"""

import json
import time
from email.message import EmailMessage
from urllib.parse import quote

from . import store

CHANNELS = ("email", "teams", "both", "none")
ROLES = ("coordinator", "lead", "clinical")

# Urgency drives the subject tag, the card colour and the sort order in the outbox.
URGENCY = {"info": 0, "soon": 1, "urgent": 2}
TAG = {"en": {"info": "FYI", "soon": "Soon", "urgent": "URGENT"},
       "es": {"info": "Aviso", "soon": "Pronto", "urgent": "URGENTE"}}

# event: (urgency, English line, Spanish line). {case} {hospital} {left} {detail} are filled in.
EVENTS = {
    "assigned": ("info", "New referral {case} from {hospital} is yours. {left} min left on the 2-hour clock.",
                 "El referido nuevo {case} de {hospital} es suyo. Quedan {left} min del plazo de 2 horas."),
    "review_ready": ("soon", "Claude finished reading {case}: {detail}. Please check it now. {left} min left.",
                     "Claude terminó de leer {case}: {detail}. Revíselo ahora. Quedan {left} min."),
    "clinical": ("urgent", "{case} needs a clinical check: {detail}. Only a clinician can deny. {left} min left.",
                 "{case} necesita revisión clínica: {detail}. Solo un clínico puede negar. Quedan {left} min."),
    "lead_unopened": ("urgent", "{case} has not been opened and has {left} min left. Please reassign or open it.",
                      "{case} no se ha abierto y le quedan {left} min. Reasígnelo o ábralo."),
    "clinical_repage": ("urgent", "{case} is still waiting for the clinical line. {left} min left.",
                        "{case} sigue esperando la revisión clínica. Quedan {left} min."),
    "clock_30": ("urgent", "{case} has {left} min left on the 2-hour clock.",
                 "A {case} le quedan {left} min del plazo de 2 horas."),
    "more_time": ("urgent", "{case}: {left} min left. Send the hospital the \"more time\" draft so they don't discharge.",
                  "{case}: quedan {left} min. Envíe al hospital el borrador de \"más tiempo\" para que no den de alta."),
    "chase_nudge": ("soon", "{case}: the hospital has been quiet {detail} min. The follow-up draft is ready.",
                    "{case}: el hospital no responde hace {detail} min. El borrador de seguimiento está listo."),
    "chase_supervisor": ("urgent", "{case}: still no reply after {detail} min. The supervisor draft is ready.",
                         "{case}: sin respuesta después de {detail} min. El borrador para el supervisor está listo."),
    "hospital_replied": ("soon", "{case}: the hospital replied. Please look at what came in.",
                         "{case}: el hospital respondió. Revise lo que llegó."),
    "handoff": ("soon", "{case} was handed to you. {left} min left.",
                "Le pasaron {case}. Quedan {left} min."),
    "decided": ("info", "{case} closed: {detail}.", "{case} cerrado: {detail}."),
}

ROUTE = {"en": {"likely_yes": "likely yes", "needs_info": "missing items", "clinical_check": "clinical check",
                "likely_no": "likely no", "security_hold": "security hold"},
         "es": {"likely_yes": "probable sí", "needs_info": "faltan documentos", "clinical_check": "revisión clínica",
                "likely_no": "probable no", "security_hold": "retención de seguridad"}}
OUTCOME = {"en": {"accepted": "accepted", "denied": "denied", "withdrawn": "withdrawn"},
           "es": {"accepted": "aceptado", "denied": "negado", "withdrawn": "retirado"}}
NOTE = {"en": "Draft from Lamplight. Not sent. No patient details: open the referral in the app.",
        "es": "Borrador de Lamplight. No enviado. Sin datos del paciente: abra el referido en la aplicación."}
OPEN = {"en": "Open referral", "es": "Abrir referido"}
NO_ADDRESS = {"en": "unknown: add this person's address under People",
              "es": "desconocido: agregue la dirección de esta persona en Personas"}


# ---- who gets what ----------------------------------------------------------------------------
def default_people(staff: list[dict]) -> list[dict]:
    """Everyone on the board's staff list and on the sign-in staff list (auth.staff()), one entry per
    name. Email and Teams come from the sign-in list: that address is the person's Microsoft work
    account, which is also their Teams sign-in. Someone only on the board starts with no address:
    we never guess one."""
    from . import auth

    accounts = {a["name"].lower(): a for a in auth.staff()}
    people = []
    for s in staff:
        a = accounts.pop(s["name"].lower(), {})
        email = a.get("email") or s.get("email", "")  # the practice board's made-up staff carry their own
        people.append({"name": s["name"], "role": s["role"], "email": email, "teams": email,
                       "channel": "both", "lang": "en"})
    for a in accounts.values():  # on the sign-in list but not on today's board, e.g. the clinical reviewer
        if a.get("role") in ROLES:
            people.append({"name": a["name"], "role": a["role"], "email": a.get("email", ""), "teams": a.get("email", ""),
                           "channel": "both", "lang": "en"})
    if not any(p["role"] == "clinical" for p in people):
        people.append({"name": "Clinical line", "role": "clinical", "email": "", "teams": "", "channel": "both", "lang": "en"})
    return people


def people(staff: list[dict] | None = None) -> list[dict]:
    """Everyone on the tracker's staff list, with whatever addresses and choices were saved for them."""
    merged = {p["name"]: p for p in default_people(staff or [])}
    merged.update({p["name"]: p for p in store.list_people()})
    return list(merged.values())


def save_person(p: dict) -> dict:
    name = (p.get("name") or "").strip()
    if not name:
        raise ValueError("A person needs a name.")
    row = {"name": name, "role": p.get("role") if p.get("role") in ROLES else "coordinator",
           "email": (p.get("email") or "").strip(), "teams": (p.get("teams") or "").strip(),
           "channel": p.get("channel") if p.get("channel") in CHANNELS else "both",
           "lang": "es" if p.get("lang") == "es" else "en"}
    store.save_person(row)
    return row


def _recipients(event: str, card: dict, everyone: list[dict], on_shift: set[str]) -> list[dict]:
    by_role = lambda r: [p for p in everyone if p["role"] == r and (p["role"] == "clinical" or p["name"] in on_shift)]
    owner = [p for p in everyone if p["name"] == card.get("owner")]
    if event in ("clinical",):
        return by_role("clinical") + owner
    if event == "clinical_repage":
        return by_role("clinical") + by_role("lead")
    if event == "lead_unopened":
        return by_role("lead")
    if event == "decided":
        return owner + [p for p in by_role("lead") if p not in owner]
    return owner


# ---- rendering --------------------------------------------------------------------------------
def _line(event: str, ctx: dict, lang: str) -> tuple[str, str]:
    urgency, en, es = EVENTS[event]
    return urgency, (es if lang == "es" else en).format(**ctx)


def _ctx(card: dict, lang: str, detail: str = "") -> dict:
    return {"case": card.get("case_no") or card["id"], "hospital": card.get("hospital") or ("desconocido" if lang == "es" else "unknown"),
            "left": max(0, card.get("left_min", 0)), "detail": detail}


def render(person: dict, event: str, card: dict, detail_by_lang: dict, app_url: str) -> list[dict]:
    """One draft per channel the person wants. Returns rows for the outbox."""
    lang = person["lang"]
    urgency, line = _line(event, _ctx(card, lang, detail_by_lang.get(lang, "")), lang)
    case = card.get("case_no") or card["id"]
    subject = f"[{TAG[lang][urgency]}] {line.split('. ')[0].rstrip('.')}"  # every line already names the case
    link = f"{app_url.rstrip('/')}/#card={quote(card['id'])}"
    body = f"{line}\n\n{OPEN[lang]}: {link}\n\n{NOTE[lang]}"
    channels = {"both": ["email", "teams"], "email": ["email"], "teams": ["teams"], "none": []}[person["channel"]]
    # What the alert was about, kept so a waiting draft can be redrawn when the person's address or
    # language changes. Only the fields above: still nothing about the patient.
    ctx = {"card": {k: card.get(k) for k in ("id", "case_no", "hospital", "left_min", "practice")}, "detail": detail_by_lang}
    out = []
    for ch in channels:
        row = {"case_no": case, "card_id": card["id"], "event": event, "person": person["name"], "channel": ch,
               "lang": lang, "urgency": urgency, "subject": subject, "body": body, "practice": bool(card.get("practice")),
               "ctx": ctx}
        if ch == "email":
            row["to"] = person["email"] or NO_ADDRESS[lang]
            row["ready"] = bool(person["email"])
        else:
            row["to"] = person["teams"] or NO_ADDRESS[lang]
            row["ready"] = bool(person["teams"])
            row["card"] = adaptive_card(line, urgency, lang, case, link)
            # Opens Teams on the right chat with the text filled in; the person presses send.
            row["teams_link"] = (f"https://teams.microsoft.com/l/chat/0/0?users={quote(person['teams'])}"
                                 f"&message={quote(subject + chr(10) + line + chr(10) + link)}") if person["teams"] else None
        out.append(row)
    return out


def adaptive_card(line: str, urgency: str, lang: str, case: str, link: str) -> dict:
    """Adaptive Card 1.5, the format Teams (and Power Automate's 'post card') accepts."""
    color = {"info": "Default", "soon": "Warning", "urgent": "Attention"}[urgency]
    return {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.5",
        "body": [
            {"type": "TextBlock", "text": f"{TAG[lang][urgency]} · {case}", "weight": "Bolder", "color": color, "size": "Medium"},
            {"type": "TextBlock", "text": line, "wrap": True},
            {"type": "TextBlock", "text": NOTE[lang], "wrap": True, "isSubtle": True, "size": "Small"},
        ],
        "actions": [{"type": "Action.OpenUrl", "title": OPEN[lang], "url": link}],
    }


def eml(row: dict) -> bytes:
    """An Outlook draft: double-click opens it ready to send, because of X-Unsent."""
    m = EmailMessage()
    m["To"] = row["to"] if row.get("ready") else ""
    m["Subject"] = row["subject"]
    m["X-Unsent"] = "1"
    if row["urgency"] == "urgent":
        m["Importance"] = "High"
        m["X-Priority"] = "1"
    m.set_content(row["body"])
    return bytes(m)


# ---- turning tracker state into alerts --------------------------------------------------------
_cursor = {"audit": 0}


def clear_practice() -> None:
    """A new practice run starts with no practice alerts, and reads the tracker's audit from the top."""
    store.clear_practice_notifications()
    _cursor["audit"] = 0
# The address staff open the app at, for the "Open referral" link. The web app updates it from the
# browser's own Host header, so it is right inside Docker too.
APP_URL = "http://127.0.0.1/"


def _detail(event: str, card: dict, a: dict | None) -> dict:
    if event in ("review_ready", "clinical"):
        code = card.get("suggested_route") or ""
        return {lg: ROUTE[lg].get(code, code) for lg in ("en", "es")}
    if event == "decided":
        return {lg: OUTCOME[lg].get(card.get("status"), card.get("status") or "") for lg in ("en", "es")}
    if event in ("chase_nudge", "chase_supervisor"):
        return {lg: str(card.get("hospital_silent_min") or "") for lg in ("en", "es")}
    return {}


AUDIT_EVENTS = {"received": "assigned", "flagged": "review_ready", "sent to clinical line": "clinical",
                "hospital_replied": "hospital_replied", "handoff": "handoff",
                "accepted": "decided", "denied": "decided", "withdrawn": "decided"}


def sync(track, app_url: str | None = None) -> int:
    """Read what happened since the last call and what the clock says now; add new drafts.

    Safe to call on every queue refresh: each (referral, event, person, channel) is drafted once,
    except a hand-off, which is drafted again for each new owner."""
    app_url = app_url or APP_URL
    everyone = people(track.staff)
    on_shift = {s["name"] for s in track.staff if s["on_shift"]}
    todo: list[tuple[str, str, dict | None]] = []
    audit = track.audit
    if _cursor["audit"] > len(audit):  # tracker was reset
        _cursor["audit"] = 0
    for a in audit[_cursor["audit"]:]:
        ev = AUDIT_EVENTS.get(a["what"])
        if ev and a["card"] in track.cards:
            todo.append((a["card"], ev, a))
    _cursor["audit"] = len(audit)
    for cid in list(track.cards):
        v = track.view(cid)
        for al in v["alerts"]:
            if al["code"] in EVENTS:
                todo.append((cid, al["code"], None))
        if v["color"] == "red" and not any(al["code"] == "more_time" for al in v["alerts"]):
            todo.append((cid, "clock_30", None))  # at 15 min the "more time" alert says it already
    added = 0
    for cid, ev, a in todo:
        card = track.view(cid)
        if ev == "review_ready" and card.get("suggested_route") in ("likely_no", "clinical_check", "security_hold"):
            continue  # the clinical alert covers it
        for person in _recipients(ev, card, everyone, on_shift):
            for row in render(person, ev, card, _detail(ev, card, a), app_url):
                key = f"{row['card_id']}|{ev}|{row['person']}|{row['channel']}"
                if ev == "handoff":
                    key += f"|{card.get('owner')}"
                if store.add_notification(key, row):
                    added += 1
    return added


def _fresh(r: dict, now: dict) -> dict:
    """A draft still waiting follows the person's current address and language."""
    for k in ("card", "ctx"):
        if isinstance(r.get(k), str):
            r[k] = json.loads(r[k])
    if r["status"] == "draft" and r.get("ctx") and r["person"] in now:
        fresh = render({**now[r["person"]], "channel": r["channel"]}, r["event"], r["ctx"]["card"], r["ctx"]["detail"], APP_URL)
        if fresh:
            r.update({k: fresh[0].get(k) for k in ("lang", "subject", "body", "to", "ready", "card", "teams_link")})
    r.pop("ctx", None)
    return r


def outbox(person: str | None = None, include_done: bool = False, include_practice: bool = True,
           staff: list[dict] | None = None) -> list[dict]:
    now = {p["name"]: p for p in people(staff)}
    rows = [_fresh(r, now) for r in store.list_notifications(person, include_done, include_practice)]
    return sorted(rows, key=lambda r: (r["status"] != "draft", -URGENCY[r["urgency"]], -r["t"]))


def get(nid: int, staff: list[dict] | None = None) -> dict | None:
    r = store.get_notification(nid)
    return _fresh(r, {p["name"]: p for p in people(staff)}) if r else None


def mark(nid: int, status: str, who: str = "") -> None:
    """A person says they sent it (copied into Outlook or Teams) or that it is not needed."""
    if status not in ("sent_by_person", "dismissed", "draft"):
        raise ValueError(f"unknown status {status}")
    store.mark_notification(nid, status, who, time.time())
