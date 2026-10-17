"""IHH's admission criteria, loaded from challenges/1-referral-intake/criteria/admission-criteria.json.

Everything the engine decides is keyed by the rule IDs in that file.
"""

from functools import lru_cache

from .paths import CRITERIA, load_json

# The two gates come first because IHH has no Title 22 license: staff can't give hands-on care or
# administer medications (docs/workflow-and-timing.md section 5).
GATES = {
    "self_care": ["ADL-1", "ADL-2", "ADL-3", "MOB-1", "MOB-3", "MOB-4", "COG-1", "COG-2",
                  "FORM-M3", "FORM-M4", "FORM-M5", "FORM-M6", "FORM-X1", "FORM-X2", "FORM-X3"],
    "behavior": ["MH-1", "MH-2", "MH-3", "MH-4", "MH-5", "OTH-1", "FORM-M2", "FORM-X5", "FORM-X7"],
}

# The rules a chart normally speaks to. Only these make a gate "can't tell"; rarely documented
# ones (MH-5 conservatorship, MH-4 hours since alcohol) become questions for the hospital instead.
GATE_CORE = {
    "self_care": {"ADL-1", "ADL-2", "ADL-3", "MOB-1", "MOB-3", "MOB-4", "COG-1", "COG-2"},
    "behavior": {"MH-1", "MH-2", "MH-3", "OTH-1"},
}

# Rules that turn on a date or a count of hours. Dates are redacted in every packet, so "met" can
# never be confirmed from the packet alone.
DATE_RULES = {"MH-4", "DM-3", "DM-4", "INF-2", "CARD-1", "CARD-6", "DOC-6"}

# "Yes, if": the arrangement has to be confirmed before admission.
CONDITIONAL = {"OTH-3", "EOL-1", "DM-4", "ID-3", "RESP-3", "INT-E2"}

# Never auto-deny on these. They go to a person (OTH-2 wins over FORM-X6; NEU-X6 escalates).
HUMAN_ONLY = {"OTH-2", "FORM-X6", "NEU-X6"}

# Where the written rules run out (criteria/admission-criteria.md, "Places where the written rules
# are unclear"). Shown to people, never resolved silently.
GAPS = [
    ("OTH-2", "Sex offender: case by case. Never auto-deny."),
    ("RSP-E5", "The O2 '94% or greater with physician explanation' rule has no stated practical meaning."),
    ("DM-Q3", "The A1C sentence is cut off in the source."),
    ("MH-5", "'FSP' is undefined. Probably Full Service Partnership."),
    ("DM-3", "The insulin '<24 h' rule doesn't say when the clock starts. Dates are redacted anyway."),
    ("END-X3", "Unclear whether DKA that has resolved still excludes."),
    ("GI-X3", "Unclear whether the C. diff exclusion ends when isolation lifts or when treatment ends."),
    ("CARD-2", "Troponin after a heart attack: CARD-2 wants negatives, CIR-E7 says history of MI is eligible."),
    ("INF-2", "The COVID swab may be more than 24 h old by the time the patient arrives."),
    ("INT-X2", "'Complicated large abscess' is undefined."),
    ("INT-E2", "The hard-to-reach wound list has a missing item; the sacrum is not named."),
    ("OTH-3", "The home health threshold varies: 'established', 'ordered', 'coordinated', 'scheduled'."),
]


@lru_cache(maxsize=1)
def criteria() -> dict:
    return load_json(CRITERIA)


@lru_cache(maxsize=1)
def all_rules() -> dict[str, dict]:
    """Every rule with an ID, flattened: id -> {id, kind, text, section, group, superseded_by}."""
    c = criteria()
    out: dict[str, dict] = {}
    for g in c["general"]["any_of"]:
        out[g["id"]] = {**g, "kind": "must", "section": "General entry (any one)", "group": "general"}
    for r in c["rules"]:
        out[r["id"]] = {**r, "group": "rules"}
    for sysd in c["by_system"]:
        for e in sysd.get("eligible", []):
            out[e["id"]] = {**e, "kind": e.get("kind", "eligible"), "section": sysd["system"], "group": "eligible"}
        for e in sysd.get("ineligible", []):
            out[e["id"]] = {**e, "kind": "ineligible", "section": sysd["system"], "group": "ineligible"}
    screen = c["referral_form_screen"]
    for r in screen["must_meet_all"]:
        out[r["id"]] = {**r, "kind": "must", "section": "Hospital referral form", "group": "form"}
    for r in screen["not_eligible_if"]:
        out[r["id"]] = {**r, "kind": "exclude", "section": "Hospital referral form", "group": "form"}
    for d in c["referral_checklist"]["items"]:
        out[d["id"]] = {**d, "kind": "document", "section": "Documents to send", "group": "checklist"}
    return out


def assessed_rule_ids() -> list[str]:
    """Rules the rule pass must give a status for (diagnoses and checklist are separate lists)."""
    return [k for k, v in all_rules().items() if v["group"] in ("general", "rules", "form")]


def checklist_ids() -> list[str]:
    return [d["id"] for d in criteria()["referral_checklist"]["items"]]


def gate_of(rule_id: str) -> str | None:
    for g, ids in GATES.items():
        if rule_id in ids:
            return g
    return None


def rulebook_text() -> str:
    """The rulebook as compact text for prompts."""
    c = criteria()
    lines = [f"PRECEDENCE: {c['precedence']}", "", "KINDS: " + "; ".join(f"{k} = {v}" for k, v in c["kinds"].items()), ""]
    section = None
    for rid, r in all_rules().items():
        if r["section"] != section:
            section = r["section"]
            lines.append(f"## {section}")
        extra = f" (superseded by {r['superseded_by']})" if r.get("superseded_by") else ""
        lines.append(f"{rid} [{r['kind']}]{extra}: {r['text']}")
    lines += ["", "KNOWN GAPS IN THE WRITTEN RULES (flag, never resolve silently):"]
    lines += [f"- {rid}: {txt}" for rid, txt in GAPS]
    return "\n".join(lines)


def search(query: str, limit: int = 15) -> list[dict]:
    q = query.lower().split()
    scored = []
    for rid, r in all_rules().items():
        hay = f"{rid} {r['section']} {r['text']}".lower()
        score = sum(hay.count(w) for w in q)
        if rid.lower() == query.lower().strip():
            score += 100
        if score:
            scored.append((score, rid))
    scored.sort(key=lambda x: -x[0])
    return [all_rules()[rid] for _, rid in scored[:limit]]
