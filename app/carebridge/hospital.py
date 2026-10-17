"""What the hospital hears while it waits: a receipt, a reminder while documents are pending, and
"escalated for review" while the clinical reviewer looks.

The intake director asked for an automatic receipt and reminders to the social worker. These three carry
no decision and no clinical detail, only the case code and where things stand, so they are the only
messages that could ever go out on their own, and only if IHH agrees (docs/closed-loop.md section 3).
The list of missing items, every request for records and every decision stay drafts a person sends.

In the prototype nothing is sent. With "send status messages on their own" off (the default), each one is
a draft. With it on, it is marked "would be sent" and logged, so the demo shows the timing.
The texts are the Microsoft 365 kit's (m365/status-messages.json), so both say the same thing.
"""

from datetime import datetime
from functools import lru_cache

from . import config
from .paths import STATUS_MESSAGES, load_json

KINDS = ("received", "reminder", "escalated")
REMINDER_EVERY_MIN = 30  # placeholder, like the chase ladder (tracker.LADDER)
REMINDER_MAX = 3


@lru_cache(maxsize=1)
def templates() -> dict:
    return load_json(STATUS_MESSAGES)


def auto() -> bool:
    return bool(config.load_settings().get("auto_hospital_messages"))


def _deadline(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")


def render(kind: str, card: dict, lang: str = "en") -> dict:
    """One status message for the person who sent the referral. Only the case code and the status:
    nothing from the packet."""
    lang = lang if lang in ("en", "es") else "en"
    tpl = templates()[kind][lang]
    fields = {"case_code": card["case_no"],
              "submitter_name": card.get("case_manager") or ("equipo del hospital" if lang == "es" else "hospital team"),
              "hospital": card.get("hospital") if card.get("hospital") not in (None, "", "unknown") else
              ("su centro" if lang == "es" else "your facility"),
              "deadline_local": _deadline(card.get("deadline") or card["arrived_at"] + 7200)}
    fill = lambda s: s.format(**fields)  # noqa: E731
    return {"kind": kind, "lang": lang, "to": card.get("cm_email"), "subject": fill(tpl["subject"]), "body": fill(tpl["body"])}


def due(view: dict, now: float) -> list[str]:
    """Which status messages this referral should have by now and doesn't."""
    sent = view.get("hospital_messages") or []
    kinds = [m["kind"] for m in sent]
    out = []
    if view["status"] in ("accepted", "denied", "withdrawn"):
        return out
    if "received" not in kinds:
        out.append("received")
    if view.get("clinical_sent_at") and "escalated" not in kinds:
        out.append("escalated")
    if view.get("info_requested_at") and not view.get("hospital_replied_at"):
        reminders = [m["t"] for m in sent if m["kind"] == "reminder" and m["t"] >= view["info_requested_at"]]
        last = max(reminders, default=view["info_requested_at"])
        if len(reminders) < REMINDER_MAX and (now - last) / 60 >= REMINDER_EVERY_MIN:
            out.append("reminder")
    return out


def sync(track) -> int:
    """Add each due message to the referral, once. Safe to call on every tick."""
    added = 0
    now = track.clock.now()
    mode = "would_send" if auto() else "draft"
    for cid in list(track.cards):
        card = track.cards[cid]
        view = track.view(cid)
        for kind in due(view, now):
            msg = render(kind, view, card.get("cm_lang") or "en")
            card.setdefault("hospital_messages", []).append({**msg, "t": now, "mode": mode})
            track.log(cid, "system", f"hospital {kind}", "would be sent (practice: not sent)" if mode == "would_send" else "draft ready")
            added += 1
    return added
