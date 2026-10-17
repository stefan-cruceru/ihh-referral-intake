"""Try it safely (Challenge 3): staff see AI help with their own work, on invented examples.

Each practice shows exactly what was sent to the AI and what it cost. The note helper checks its
own draft: every sentence must point to words the staff member actually wrote, or it is flagged.
"""

from . import llm, phi, rules

S = llm.strict

NOTE_SCHEMA = S({"type": "object", "properties": {
    "sentences": {"type": "array", "items": {"type": "object", "properties": {
        "section": {"type": "string", "enum": ["observation", "client_reported", "action", "education", "follow_up"]},
        "text": {"type": "string"},
        "source": {"type": "string"},
    }}},
    "missing": {"type": "array", "items": {"type": "string"}},
}})

NOTE_PROMPT = """You help an LVN or medical assistant at a recuperative care site turn their own shift jottings into a
tidy progress note draft. Recuperative care staff monitor, teach, coordinate and document; they do not give
medications or make treatment decisions, so never write that staff administered medication or diagnosed anything.
Use ONLY what is in the jottings. For each sentence, source must be the exact words from the jottings it comes from
(copy them). Never add vitals, times, names or events that are not there. missing: things a note usually has
that the jottings don't say (e.g. client response to teaching), phrased as questions for the staff member.
Write the note in {lang}; source stays in the jottings' own words.""" + llm.PLAIN

EXPLAIN_PROMPT = """Explain one of IHH's recuperative care admission rules to a new referral coordinator in plain {lang}:
what it means, what to look for in a hospital packet (which kinds of pages), and one common trap. 4 to 6 short
sentences. Only use the rule text and the rulebook context given. If the rule is unclear in the source, say so.""" + llm.PLAIN

EXPLAIN_SCHEMA = S({"type": "object", "properties": {
    "plain": {"type": "string"}, "look_in": {"type": "array", "items": {"type": "string"}}, "trap": {"type": "string"}}})

# Invented practice examples. No real client.
EXAMPLES = {
    "note": {
        "en": "rounds 0900. client up in chair, says slept ok. BG 142 self-checked, I watched. "
              "reviewed glucometer steps again, did it right 2nd try. R foot dressing clean dry intact. "
              "says pain 3/10. reminded about clinic appt thurs, client has bus pass.",
        "es": "ronda 0900. cliente sentado en la silla, dice que durmió bien. glucosa 142, se la midió él, yo observé. "
              "repasamos pasos del glucómetro, lo hizo bien al 2o intento. vendaje pie der limpio seco intacto. "
              "dice dolor 3/10. le recordé cita en clínica jueves, tiene pase de autobús.",
    },
}


def note_draft(jottings: str, lang: str = "en") -> dict:
    guard = phi.check(jottings)
    if not guard["ok"]:
        return {"blocked": True, "phi": guard}
    usage = llm.Usage()
    res = llm.call_json(system=NOTE_PROMPT.format(lang="Spanish" if lang == "es" else "English"),
                        content=[{"type": "text", "text": f"JOTTINGS\n{jottings}"}],
                        schema=NOTE_SCHEMA, effort="low", max_tokens=8000, usage=usage)
    norm = " ".join(jottings.lower().split())
    for s in res["sentences"]:
        src = " ".join(s["source"].lower().split())
        s["supported"] = bool(src) and src in norm
    return {"blocked": False, "sent_to_ai": jottings, "sentences": res["sentences"], "missing": res["missing"],
            "unsupported": sum(1 for s in res["sentences"] if not s["supported"]), "cost": usage.as_dict()}


def explain_rule(rule_id: str, lang: str = "en") -> dict:
    r = rules.all_rules().get(rule_id.strip().upper())
    if not r:
        return {"error": "unknown rule"}
    gap = [t for rid, t in rules.GAPS if rid == r["id"]]
    usage = llm.Usage()
    sent = f"RULE {r['id']} [{r['kind']}, {r['section']}]: {r['text']}" + (f"\nKNOWN GAP: {gap[0]}" if gap else "")
    res = llm.call_json(system=EXPLAIN_PROMPT.format(lang="Spanish" if lang == "es" else "English"),
                        content=[{"type": "text", "text": sent}], schema=EXPLAIN_SCHEMA, effort="low",
                        max_tokens=4000, usage=usage)
    return {"rule": r, "gap": gap[0] if gap else None, "sent_to_ai": sent, **res, "cost": usage.as_dict()}
