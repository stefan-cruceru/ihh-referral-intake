"""PHI guard for anything a person types.

Typed text is checked before it can reach the Claude API. Clear identifiers (SSN, phone, email,
full dates, record numbers, street addresses, "name:" fields) are blocked, not silently scrubbed:
the person sees what was caught and rewrites it. This prototype is for de-identified and invented
data only (docs/ground-rules.md); a pilot needs a BAA with every vendor that sees PHI.
Text that tries to give the AI orders ("ignore your instructions") is blocked the same way (guard.py).
"""

import re

from . import guard

PATTERNS = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("date", re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:\d{2}|\d{4})\b")),
    ("date", re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2},? \d{4}\b", re.I)),
    ("dob", re.compile(r"\b(?:dob|d\.o\.b\.|date of birth|fecha de nacimiento)\b", re.I)),
    ("record_number", re.compile(r"\b(?:mrn|medical record|acct|account|member id|cin|medi-?cal id)\s*(?:#|no\.?|number)?\s*[:#]?\s*[A-Z0-9-]{5,}\b", re.I)),
    ("long_number", re.compile(r"\b\d{8,}\b")),
    ("address", re.compile(r"\b\d{2,6}\s+(?:[NSEW]\.?\s+)?[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s(?:st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|ln|lane|way|ct|court|pl|place)\b\.?", re.I)),
    ("name_field", re.compile(r"\b(?:patient name|pt name|name|nombre)\s*[:=]\s*\S+", re.I)),
]

# Words that mean someone may be in danger. They switch the resource finder into safety mode.
DANGER = re.compile(
    r"\b(?:suicid\w*|kill (?:my|him|her)self|end my life|hurt (?:my|him|her)self|overdos\w*|"
    r"abus\w*|beat(?:s|ing)? me|hits? me|domestic violence|unsafe at home|afraid (?:of|to go)|"
    r"matar(?:me)?|suicid\w*|me pega|violencia dom[eé]stica|peligro)\b", re.I)


def scan(text: str) -> list[dict]:
    hits = []
    for kind, pat in PATTERNS:
        for m in pat.finditer(text or ""):
            hits.append({"kind": kind, "start": m.start(), "end": m.end()})
    hits.sort(key=lambda h: h["start"])
    return hits


def check(text: str) -> dict:
    """{'ok': bool, 'hits': [...], 'masked': text with hits blacked out for display}."""
    hits = scan(text)
    masked = list(text or "")
    for h in hits:
        for i in range(h["start"], h["end"]):
            if masked[i] not in " \n":
                masked[i] = "█"
    kinds = [{"kind": h["kind"]} for h in hits] + guard.check_typed(text)["hits"]
    return {"ok": not kinds, "hits": kinds, "masked": "".join(masked)}


def in_danger(text: str) -> bool:
    return bool(DANGER.search(text or ""))
