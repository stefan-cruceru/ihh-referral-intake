"""Finding the right next door (Challenge 2), for IHH clients getting ready to leave care.

Claude only picks resource IDs from the sourced seed list and explains the fit. Every phone
number, address, hour and eligibility line shown comes from the seed file, never from Claude, so
nothing can be invented. Each card shows the date it was last checked and its source link.
"""

from . import llm, phi
from .paths import RESOURCES, SCENARIOS, load_json

S = llm.strict

NEEDS = ["shelter", "housing-navigation", "employment", "microenterprise", "family-reunification-travel",
         "id-documents", "benefits", "food", "transportation", "legal", "behavioral-health", "veterans",
         "phone-internet", "health-coverage", "hygiene-mail-storage", "other"]

PICK_SCHEMA = S({"type": "object", "properties": {
    "needs": {"type": "array", "items": {"type": "string", "enum": NEEDS}},
    "picks": {"type": "array", "items": {"type": "object", "properties": {
        "resource_id": {"type": "string"},
        "why": {"type": "string"},
        "first_step": {"type": "string"},
        "watch_out": {"type": "string"},
    }}},
    "plan_today": {"type": "string"},
    "ask_staff": {"type": "array", "items": {"type": "string"}},
}})

PICK_PROMPT = """You help a case manager at Illumination Health + Home (IHH) find next steps for a client who is
getting ready to leave recuperative care. You get the client's situation and a list of resources, each with an
ID. Pick up to 6 resources FROM THE LIST ONLY that fit the client's needs and constraints (language, mobility,
phone, ID, referral rules). Never mention a service, phone number, address, hour or rule that is not in the
list; the app shows those details itself. If nothing fits a need, say so in ask_staff.
Write in {lang}, so the client can follow it.
- why: one sentence on why this fits.
- first_step: the first concrete thing to do today, using only what the list says about how to access it.
- watch_out: referral-only, hours, documents to bring, or "" if nothing.
- plan_today: 2 to 3 short sentences.
- ask_staff: what a staff member must confirm or help with.
No medical, legal or immigration advice: point to staff. If immigration status comes up, do not ask about it.""" + llm.PLAIN


def catalog() -> list[dict]:
    return load_json(RESOURCES)["resources"]


def disclaimer() -> str:
    return load_json(RESOURCES)["disclaimer"]


def scenarios() -> list[dict]:
    return load_json(SCENARIOS)["scenarios"]


def _card(r: dict, why: str = "", first_step: str = "", watch_out: str = "") -> dict:
    keep = ["id", "name", "organization", "category", "description", "services", "eligibility", "how_to_access",
            "referral_required", "phone", "address", "city", "hours", "languages", "cost", "website",
            "source_url", "verified_date", "confidence", "notes"]
    card = {**{k: r.get(k) for k in keep}, "why": why, "first_step": first_step, "watch_out": watch_out}
    if {"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", [])):
        card["address"] = None  # never show where a survivor-serving program is
    return card


def safety_cards() -> list[dict]:
    by_id = {r["id"]: r for r in catalog()}
    return [_card(by_id[i]) for i in ("988-suicide-and-crisis-lifeline", "oc-links", "211-orange-county") if i in by_id]


# Programs only for a group: skipped by the no-AI match unless the situation names that group.
GROUP_WORDS = {
    "families": ["child", "children", "kids", "family with", "pregnant"], "youth": ["youth", "teen", "under 25"],
    "youth 12-21": ["youth", "teen"], "youth 18-24": ["youth", "under 25"], "veterans": ["veteran"],
    "women": ["woman", "women", "female", " she ", " her "], "survivors of domestic violence": ["abuse", "domestic violence"],
    "seniors": ["senior", "older"], "students": ["student"], "pregnant people": ["pregnant"],
}


# Words in a situation -> needs in the resource list, for the match without an API key. English and
# Spanish, since staff may type either. Plain substring match: a hint, never a decision.
NEED_WORDS = {
    "shelter": ["unhoused", "homeless", "sleeps outdoors", "shelter", " car ", "street", "sin hogar", "refugio",
                "duerme en la calle", "en su carro"],
    "housing-navigation": ["unhoused", "homeless", "housing", "sin hogar", "vivienda"],
    "id-documents": [" id ", "identification", "lost his id", "lost her id", "no id", "identificación", "identificacion"],
    "benefits": ["medi-cal", "calfresh", "benefits", "income", "general relief", "beneficios", "ingreso"],
    "food": ["food", "meals", "hungry", "diabetes", "glucose", "comida", "hambre"],
    "transportation": ["bus", "ride", "transport", "appointment", "follow-up", "follow up", "clinic", "transporte",
                       "cita", "clínica", "clinica"],
    "behavioral-health": ["depress", "anxiety", "psychiatr", "suicid", "alcohol", "substance", "detox", "ansiedad",
                          "psiquiatr", "drogas"],
    "phone-internet": ["no phone", "phone", "teléfono", "telefono"],
}


def needs_from_text(text: str) -> list[str]:
    low = f" {text.lower()} "
    return [n for n, words in NEED_WORDS.items() if any(w in low for w in words)]


def offline_match(needs: list[str], limit: int = 6, situation: str = "") -> list[dict]:
    """No-AI fallback: match by category and tags, leaving out programs for a group the situation
    doesn't mention (a families-only program for a single adult, for example)."""
    low = f" {situation.lower()} "

    def fits(r):
        pop = set(r.get("population") or [])
        if pop and not pop & {"anyone", "adults", "adults without children", "Medi-Cal members", "people with disabilities"}:
            return any(w in low for g in pop for w in GROUP_WORDS.get(g, []))
        return True

    # Round-robin across needs (best match for each need first), so one need can't fill every slot.
    pools = [[r for r in catalog() if need in {r["category"], *r.get("tags", [])} and fits(r)] for need in needs]
    picked: list[dict] = []
    for rank in range(2):
        for pool in pools:
            fresh = [r for r in pool if r["id"] not in {p["id"] for p in picked}]
            if len(fresh) > 0 and len(picked) < limit and rank < len(pool):
                picked.append(fresh[0])
    return [_card(r) for r in picked]


def find(situation: str, lang: str = "en", needs_hint: list[str] | None = None, use_ai: bool = True) -> dict:
    guard = phi.check(situation)
    if not guard["ok"]:
        return {"blocked": True, "phi": guard}
    danger = phi.in_danger(situation)
    result = {"blocked": False, "danger": danger, "safety": safety_cards() if danger else [],
              "disclaimer": disclaimer(), "ai": False}
    if not use_ai:
        # Without a key, typed words still find a match: the needs come from the words themselves.
        needs = needs_hint or needs_from_text(situation)
        result.update(needs=needs, cards=offline_match(needs, situation=situation), plan_today="", ask_staff=[])
        return result
    listing = "\n".join(
        f"{r['id']} | {r['category']} | {r['name']} | tags: {', '.join(r.get('tags', []))} | eligibility: {r.get('eligibility')} "
        f"| access: {r.get('how_to_access')} | referral required: {r.get('referral_required')} | languages: {', '.join(r.get('languages') or [])}"
        for r in catalog())
    usage = llm.Usage()
    res = llm.call_json(
        system=PICK_PROMPT.format(lang="Spanish" if lang == "es" else "English"),
        content=[{"type": "text", "text": f"RESOURCES\n{listing}\n\nCLIENT SITUATION\n{situation}"
                  + (f"\nNEEDS NAMED BY STAFF: {', '.join(needs_hint)}" if needs_hint else "")}],
        schema=PICK_SCHEMA, effort="medium", max_tokens=16000, usage=usage)
    by_id = {r["id"]: r for r in catalog()}
    cards, dropped = [], []
    for p in res["picks"]:
        r = by_id.get(p["resource_id"])
        if r is None:
            dropped.append(p["resource_id"])  # not in the sourced list: never shown
            continue
        cards.append(_card(r, p["why"], p["first_step"], p["watch_out"]))
    result.update(ai=True, needs=res["needs"], cards=cards, plan_today=res["plan_today"],
                  ask_staff=res["ask_staff"], dropped=dropped, cost=usage.as_dict())
    return result
