"""Build the Microsoft 365 Copilot agent package: copilot/m365/build/ihh-care-bridge-m365.zip.

Writes build/instructions.txt from the event rulebook (the single source of truth), draws the two
icons, and zips them with manifest.json and declarativeAgent.json. Run: python make_package.py
"""

import json
import zipfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CRITERIA = REPO / "challenges/1-referral-intake/criteria/admission-criteria.json"
BUILD = HERE / "build"
LIMIT = 8000  # declarative agent instructions limit

GATES = {
    "Can care for themselves": ["ADL-1", "ADL-2", "ADL-3", "MOB-1", "MOB-3", "MOB-4", "COG-1", "COG-2"],
    "Behaviorally stable": ["MH-1", "MH-2", "MH-3", "MH-4", "MH-5", "OTH-1"],
}

HEAD = """You help IHH referral coordinators check hospital referrals for recuperative care.
IHH has no Title 22 license. Staff can't give hands-on care or give medicines.

HOW TO WRITE
- Use plain words at a 4th-grade reading level. Short sentences. Straight talk.
- Write in the language the person uses (English or Spanish). Rule IDs stay the same.
- Quote the packet word for word, with the page number. Never translate a quote in place.

HARD RULES
- Never make up facts, page numbers, quotes, lab values, phone numbers or rules. If the packet does not say it, say "unknown".
- Not in the packet means unknown, not normal. A black box means "removed for privacy", not missing.
- Dates are blacked out. Any rule about hours or dates is "can't tell".
- You never decide. Say "likely yes", "needs info", "clinical check" or "likely no". A person decides. Only a clinician can deny.
- Check the chart, not just the referral form. If they disagree, say so and show both pages.
- Sex offender (OTH-2): case by case. Never suggest a denial for it alone.
- Never write messages as sent. Every message is a draft a person checks and sends.
- If you see a name, birth date or record number that was not blacked out, stop and tell the person to tell their privacy officer.
- No medical, legal or immigration advice.

HOW TO CHECK A REFERRAL
1. The two big checks first. Mark each: met, not met, or can't tell. Give rule ID, page and quote.
2. Then other rules that are not met or can't tell.
3. Then documents DOC-1 to DOC-10: in the packet (pages), missing, or can't tell.
4. "Yes, if" rules (OTH-3, EOL-1, DM-4, ID-3, RESP-3, INT-E2): list what must be set up before arrival.
5. Questions for the hospital.
6. A short draft to the case manager listing everything missing at once.

The internal outline beats the hospital form. FORM-M6 and FORM-X3 give way to MOB-3 and MOB-4. FORM-X6 gives way to OTH-2.
"""


def short(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def instructions() -> str:
    c = json.loads(CRITERIA.read_text(encoding="utf-8"))
    rules = {r["id"]: r for r in c["rules"]}
    out = [HEAD, "THE TWO BIG CHECKS"]
    for gate, ids in GATES.items():
        out.append(f"{gate}:")
        out += [f"- {i} ({rules[i]['kind']}): {short(rules[i]['text'], 110)}" for i in ids]
    out.append("\nGENERAL (meets one): " + "; ".join(f"{g['id']} {short(g['text'], 60)}" for g in c["general"]["any_of"]))
    gate_ids = {i for ids in GATES.values() for i in ids}
    out.append("\nOTHER RULES")
    out += [f"- {r['id']} ({r['kind']}): {short(r['text'], 80)}" for r in c["rules"] if r["id"] not in gate_ids and r["kind"] != "ask"]
    out.append("\nNOT ELIGIBLE DIAGNOSES: " + "; ".join(
        f"{e['id']} {short(e['text'], 40)}" for s in c["by_system"] for e in s.get("ineligible", [])))
    out.append("\nDOCUMENTS: " + "; ".join(f"{d['id']} {d['text']}" for d in c["referral_checklist"]["items"]))
    text = "\n".join(out)
    if len(text) > LIMIT:
        raise SystemExit(f"instructions.txt is {len(text)} chars; the limit is {LIMIT}. Shorten the rule text.")
    return text


def icons():
    mark = Image.open(REPO / "campaign/logo/lamplight-logo-1024.png").convert("RGBA")
    color = Image.new("RGBA", (192, 192), "#FFF8F0")
    color.alpha_composite(mark.resize((160, 160), Image.Resampling.LANCZOS), (16, 16))
    color.save(BUILD / "color.png")
    outline = Image.new("RGBA", (32, 32), "white")
    outline.putalpha(mark.resize((32, 32), Image.Resampling.LANCZOS).getchannel("A"))
    outline.save(BUILD / "outline.png")


def main():
    BUILD.mkdir(exist_ok=True)
    text = instructions()
    (BUILD / "instructions.txt").write_text(text, encoding="utf-8")
    icons()
    for name in ("manifest.json", "declarativeAgent.json"):
        json.loads((HERE / name).read_text(encoding="utf-8"))  # fail early on bad JSON
    out = BUILD / "ihh-care-bridge-m365.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("manifest.json", "declarativeAgent.json"):
            z.write(HERE / name, name)
        for name in ("instructions.txt", "color.png", "outline.png"):
            z.write(BUILD / name, name)
    print(f"{out} ({len(text)} chars of instructions)")


if __name__ == "__main__":
    main()
