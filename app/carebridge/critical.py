"""Critical values are never silent (docs/workflow-and-timing.md, "What the intake director told us").

The intake director's worry: the review misses an ejection fraction, the patient is admitted and then
needs emergency care. So for each condition the packet shows, this names the number or record that
condition needs and says one of three things, with the page:

  found       a checked quote (verify found or paraphrase) has it
  on_page     only the typed page has it: Claude read it but nobody checked the quote, so look at the page
  not_found   nothing in the packet has it, so ask the hospital

Plain code over what the review already read: no model call and no clinical judgment. The list is the
team's starting set, not IHH policy. A clinician should add to it.
"""

import re

_NUM = r"\d"

# id: (what triggers it, what it needs, the need must carry a number, English, Spanish)
CHECKS = [
    ("ejection_fraction",
     r"heart failure|\bCHF\b|\bHF[rp]EF\b|cardiomyopathy",
     r"ejection fraction|\bL?V?EF\b",
     True, "Heart failure: the last ejection fraction (EF)",
     "Insuficiencia cardíaca: la última fracción de eyección (FE)"),
    ("glucose",
     r"diabet|\bT[12]DM\b|\bDM\s?[12I]|insulin|hyperglyc",
     r"glucose|finger ?sticks?|\bFSBG\b|\bPOC\s?(?:BG|glucose)\b|\bCBG\b|\bBG\b|blood sugar|\bA1C\b|HbA1c",
     True, "Diabetes: recent finger sticks or glucose readings",
     "Diabetes: medidas de glucosa recientes (piquetes en el dedo)"),
    ("oxygen",
     r"\boxygen\b|\bO2\b|nasal cannula|\bL/min\b|\bCOPD\b|hypox",
     r"\bSpO2\b|\bSaO2\b|O2 sat|pulse ox|\bsat(?:uration)?s?\b",
     True, "Oxygen: a recent oxygen level (SpO2)",
     "Oxígeno: un nivel de oxígeno reciente (SpO2)"),
    ("wound",
     r"\bwound|\bulcer\b|pressure injur|incision|\bdehiscence",
     r"\d\s?cm\b|stage\s?[1-4IV]|dressing|wound care|wound vac|\bNPWT\b",  # "3 cm", never "CM" (case manager)
     False, "Wound: size or stage, and the wound care plan",
     "Herida: tamaño o etapa, y el plan de cuidado de la herida"),
    ("isolation",
     r"\bMRSA\b|\bVRE\b|C\.?\s?diff|\bisolation\b|\bCOVID",
     r"\bswab\b|\bPCR\b|\bculture\b|not detected|\bdetected\b|negative|positive",
     False, "Infection: the swab or culture result",
     "Infección: el resultado del hisopado o cultivo"),
    ("dialysis",
     r"dialysis|\bESRD\b|\bHD\b",
     r"chair|outpatient dialysis|dialysis (?:center|unit|clinic|schedule)|\bM/?W/?F\b|\bT/?Th/?S",
     False, "Dialysis: the outpatient chair and schedule",
     "Diálisis: el centro y el horario de diálisis"),
]

_TRIGGER = {cid: re.compile(t, re.I) for cid, t, *_ in CHECKS}
_NEED = {cid: re.compile(n, re.I) for cid, _, n, *_ in CHECKS}
_NEEDS_NUMBER = {cid: num for cid, _, _, num, *_ in CHECKS}
LABELS = {cid: {"en": en, "es": es} for cid, _, _, _, en, es in CHECKS}


def _has_value(cid: str, text: str) -> bool:
    m = _NEED[cid].search(text or "")
    if not m:
        return False
    # "EF 25%" or "EF: 25-30" count; "EF not available" does not.
    return not _NEEDS_NUMBER[cid] or bool(re.search(_NUM, text[m.start():m.end() + 30]))


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def value_lines(text: str | None) -> list[str]:
    """Lines of a typed page that carry a critical value, so the image check can confirm each one."""
    return [ln[:200] for ln in _lines(text) if any(_has_value(cid, ln) for cid, *_ in CHECKS)]


def check(report: dict) -> list[dict]:
    """One row per critical item the packet's conditions call for. Never silent: every row says
    found, on_page or not_found, with the page and the words."""
    facts = report.get("facts") or []
    pages = [p for p in report.get("pages") or [] if not p.get("isolated")]
    words = " ".join([report.get("reason_for_referral") or ""]
                     + [f"{f.get('statement', '')} {f.get('quote', '')}" for f in facts]
                     + [f"{d.get('text', '')} {d.get('explanation', '')}" for d in report.get("diagnoses") or []])
    out = []
    for cid, *_ in CHECKS:
        why = _TRIGGER[cid].search(words)
        if not why:
            continue
        row = {"id": cid, "label": LABELS[cid], "because": why.group(0), "status": "not_found",
               "fact_ids": [], "page": None, "quote": None}
        hit = next((f for f in facts if f.get("verify") in ("found", "paraphrase") and _has_value(cid, f["quote"])), None)
        if hit:
            row.update(status="found", fact_ids=[hit["id"]], page=hit["page"], quote=hit["quote"])
        else:
            for p in pages:
                line = next((ln for ln in _lines(p.get("transcript")) if _has_value(cid, ln)), None)
                if line:
                    row.update(status="on_page", page=p["page"], quote=line[:200])
                    break
        out.append(row)
    return out


def of(report: dict | None) -> list[dict]:
    """The report's list, computed for older reports that were saved before this check existed."""
    if not report:
        return []
    if "critical" not in report:
        report["critical"] = check(report)
    return report["critical"]


def missing(report: dict | None) -> list[dict]:
    return [c for c in of(report) if c["status"] == "not_found"]
