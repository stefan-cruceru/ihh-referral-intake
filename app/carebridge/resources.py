"""Finding the right next door (Challenge 2), for IHH clients getting ready to leave care.

Claude only picks resource IDs from the sourced seed list. Client guidance uses fixed English or
Spanish templates selected by the seed's access and referral fields, never model-written prose.
Phone numbers, addresses, hours and eligibility come from the seed, which staff must re-verify.
Each card shows the date it was last checked and its source link.
"""

import re

from . import config, llm, phi
from .paths import RESOURCES, SCENARIOS, load_json

S = llm.strict

NEEDS = ["shelter", "housing-navigation", "employment", "microenterprise", "family-reunification-travel",
         "id-documents", "benefits", "food", "transportation", "legal", "behavioral-health", "veterans",
         "phone-internet", "health-coverage", "hygiene-mail-storage", "other"]

PICK_SCHEMA = S({"type": "object", "properties": {
    "needs": {"type": "array", "items": {"type": "string", "enum": NEEDS}},
    "picks": {"type": "array", "items": {"type": "object", "properties": {
        "resource_id": {"type": "string"},
    }}},
}})

PICK_PROMPT = """You help a case manager at Illumination Health + Home (IHH) find next steps for a client who is
getting ready to leave recuperative care. You get the client's situation and a list of resources, each with an
ID. Pick up to 6 resources FROM THE LIST ONLY that fit the client's needs and constraints (language, mobility,
phone, ID, referral rules). Return only the need codes and ranked resource IDs. If no listed resource
fits, return an empty picks list. Do not write client advice or invent resource IDs. The app supplies
the source facts and fixed guidance separately. If immigration status comes up, do not ask about it."""


# A word blacklist cannot establish that arbitrary model prose contains no advice or invented
# facts. Only the templates below reach client guidance; all facts remain in source fields.
GUIDANCE = {
    "why": ("Review this option with staff to see whether it fits your needs.",
            "Revise esta opción con el personal para ver si responde a sus necesidades."),
    "phone": ("Ask staff to help you call and confirm access.",
              "Pida al personal ayuda para llamar y confirmar el acceso."),
    "walk-in": ("Ask staff where to go and whether you can walk in.",
                "Pregunte al personal adónde ir y si puede acudir sin cita."),
    "appointment": ("Ask staff to help you contact the service about an appointment.",
                    "Pida al personal ayuda para contactar al servicio y consultar sobre una cita."),
    "online": ("Ask staff to help check the service's website and application steps.",
               "Pida al personal ayuda para revisar el sitio web y los pasos de solicitud."),
    "referral-only": ("Ask staff to help arrange the required referral.",
                      "Pida al personal ayuda para tramitar el referido requerido."),
    "mixed": ("Ask staff to help you contact the service and confirm access.",
              "Pida al personal ayuda para contactar al servicio y confirmar el acceso."),
    "watch_out": ("Confirm availability, hours, eligibility and documents with staff before you go.",
                  "Confirme con el personal la disponibilidad, el horario, los requisitos y los documentos."),
    "plan": ("Review options with staff; confirm access, availability and eligibility.",
             "Revise las opciones con el personal; confirme el acceso, la disponibilidad y los requisitos."),
    "no_options": ("Ask staff to help find and verify another option.",
                   "Pida al personal ayuda para buscar y verificar otra opción."),
}


def _guidance(key: str, lang: str) -> str:
    return GUIDANCE[key][1 if lang == "es" else 0]


def client_guidance(source: dict, lang: str = "en") -> dict:
    """The caller must pass a canonical catalog record, never a browser/model-supplied record."""
    access = source.get("how_to_access")
    if source.get("referral_required") or access == "referral-only":
        access = "referral-only"
    if access not in {"phone", "walk-in", "appointment", "online", "referral-only", "mixed"}:
        access = "mixed"
    return {"why": _guidance("why", lang), "first_step": _guidance(access, lang),
            "watch_out": _guidance("watch_out", lang)}


def client_plan(lang: str = "en", has_resources: bool = True) -> str:
    return _guidance("plan" if has_resources else "no_options", lang)


def catalog() -> list[dict]:
    return load_json(RESOURCES)["resources"]


def disclaimer() -> str:
    return load_json(RESOURCES)["disclaimer"]


def scenarios() -> list[dict]:
    return load_json(SCENARIOS)["scenarios"]


def _card(r: dict, lang: str = "en") -> dict:
    keep = ["id", "name", "organization", "category", "description", "services", "eligibility", "how_to_access",
            "referral_required", "phone", "address", "city", "hours", "languages", "cost", "website",
            "source_url", "verified_date", "confidence", "notes"]
    card = {**{k: r.get(k) for k in keep}, **client_guidance(r, lang)}
    if {"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", [])):
        card["address"] = None  # never show where a survivor-serving program is
    return card


def safety_cards(lang: str = "en") -> list[dict]:
    by_id = {r["id"]: r for r in catalog()}
    return [_card(by_id[i], lang) for i in ("988-suicide-and-crisis-lifeline", "oc-links", "211-orange-county") if i in by_id]


# Programs only for a group: skipped by the no-AI match unless the situation names that group.
GROUP_WORDS = {
    "families": ["child", "children", "kids", "family with", "pregnant"], "youth": ["youth", "teen", "under 25"],
    "youth 12-21": ["youth", "teen"], "youth 18-24": ["youth", "under 25"], "veterans": ["veteran"],
    "women": ["woman", "women", "female", " she ", " her "], "survivors of domestic violence": ["abuse", "domestic violence"],
    "seniors": ["senior", "older"], "students": ["student"], "pregnant people": ["pregnant"],
}


# Words in a situation -> needs in the resource list, for the match without an API key. English and
# Spanish, since staff may type either. A hint, never a decision. Spaces around short words
# keep "bus" out of "business" and "work" out of "paperwork"; punctuation is normalized below.
NEED_WORDS = {
    "shelter": ["unhoused", "homeless", "sleeps outdoors", "shelter", " car ", "street", "sin hogar", "refugio",
                "duerme en la calle", "en su carro"],
    "housing-navigation": ["unhoused", "homeless", "housing", "sin hogar", "vivienda"],
    "employment": [" job ", " jobs ", " work ", "employment", "career", "resume", "résumé", "trabajo", "empleo",
                   "trabajar", "curriculum", "currículum"],
    "microenterprise": ["microloan", "micro loan", "small loan", "business", "self employed", "microcrédito",
                        "microcredito", "microempresa", "emprendimiento", "negocio", "préstamo pequeño",
                        "prestamo pequeño", "pequeño préstamo", "pequeno prestamo"],
    "family-reunification-travel": ["home to family", "home with family", "return to family", "reunite", "family reunif",
                                    "travel home", "getting home", "get home", "volver con", "regresar con",
                                    "reunificación", "reunificacion", "viajar a casa", "volver a casa", "regresar a casa"],
    "id-documents": [" id ", "identification", "lost his id", "lost her id", "no id", "identificación", "identificacion"],
    "benefits": ["medi-cal", "calfresh", "benefits", "income", "general relief", "beneficios", "ingreso"],
    "food": ["food", "meals", "hungry", "diabetes", "glucose", "comida", "hambre"],
    "transportation": [" bus ", "ride", "transport", "appointment", "follow-up", "follow up", "clinic", "transporte",
                       "cita", "clínica", "clinica"],
    "behavioral-health": ["depress", "anxiety", "psychiatr", "suicid", "alcohol", "substance", "detox", "ansiedad",
                          "psiquiatr", "drogas"],
    "phone-internet": ["no phone", "phone", "teléfono", "telefono"],
}


def needs_from_text(text: str) -> list[str]:
    def normalize(value):
        return re.sub(r"[\W_]+", " ", value.lower())

    low = f" {normalize(text)} "
    return [n for n, words in NEED_WORDS.items() if any(normalize(w) in low for w in words)]


def offline_match(needs: list[str], limit: int = 6, situation: str = "", lang: str = "en") -> list[dict]:
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
    return [_card(r, lang) for r in picked]


def find(situation: str, lang: str = "en", needs_hint: list[str] | None = None, use_ai: bool = True) -> dict:
    guard = phi.check(situation)
    if not guard["ok"]:
        return {"blocked": True, "phi": guard}
    # Only known need codes go to the model next to the situation, never free text from the request.
    needs_hint = [n for n in (needs_hint or []) if n in NEEDS] or None
    danger = phi.in_danger(situation)
    result = {"blocked": False, "danger": danger, "safety": safety_cards(lang) if danger else [],
              "disclaimer": disclaimer(), "ai": False}
    if not use_ai:
        # Without a key, typed words still find a match: the needs come from the words themselves.
        needs = needs_hint or needs_from_text(situation)
        cards = offline_match(needs, situation=situation, lang=lang)
        result.update(needs=needs, cards=cards, plan_today=client_plan(lang, bool(cards)),
                      ask_staff=[_guidance("watch_out", lang)])
        return result
    listing = "\n".join(
        f"{r['id']} | {r['category']} | {r['name']} | tags: {', '.join(r.get('tags', []))} | eligibility: {r.get('eligibility')} "
        f"| access: {r.get('how_to_access')} | referral required: {r.get('referral_required')} | languages: {', '.join(r.get('languages') or [])}"
        for r in catalog())
    usage = llm.Usage()
    res = llm.call_json(
        system=PICK_PROMPT,
        content=[{"type": "text", "text": f"RESOURCES\n{listing}\n\nCLIENT SITUATION\n{situation}"
                  + (f"\nNEEDS NAMED BY STAFF: {', '.join(needs_hint)}" if needs_hint else "")}],
        schema=PICK_SCHEMA, model=config.side_model(), effort="medium", max_tokens=16000, usage=usage)
    by_id = {r["id"]: r for r in catalog()}
    cards, dropped = [], []
    for p in res["picks"]:
        r = by_id.get(p["resource_id"])
        if r is None:
            dropped.append(p["resource_id"])  # not in the sourced list: never shown
            continue
        if len(cards) < 6 and r["id"] not in {c["id"] for c in cards}:
            cards.append(_card(r, lang))
    result.update(ai=True, needs=[n for n in res["needs"] if n in NEEDS], cards=cards,
                  plan_today=client_plan(lang, bool(cards)), ask_staff=[_guidance("watch_out", lang)],
                  dropped=dropped, cost=usage.as_dict())
    return result
