"""Referral packet review: sort pages, read them, apply the rules, then check Claude's own work.

Stages:
  1. sort    fast model: page type, rotation, blank, earlier stay, missed identifiers.
             Duplicates are caught locally with an image hash.
  2. read    main model on upright, non-blank pages: facts with page number and verbatim quote.
  3. rules   main model, text only: a status per rule ID citing fact IDs, checklist, conflicts.
  4. verify  main model looks at each cited page again and checks every quote is really there.
  5. qc      plain code: drop unverified evidence, force date rules to "can't tell", never auto-deny
             on HUMAN_ONLY rules, compute the two gates and the suggested route.

Claude never decides. The output is a review a coordinator reads, with a suggested route.
"""

import functools
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from . import config, llm, rules
from .pages import Page

PAGE_TYPES = [
    "ihh_referral_form", "fax_cover", "face_sheet", "authorization", "history_physical",
    "progress_note", "pt_ot", "nursing", "medication_list", "labs", "vitals", "imaging", "ecg",
    "consult", "psychiatry", "social_work", "wound", "orders", "discharge", "other", "blank",
]
TOPICS = [
    "housing", "adl", "mobility", "dme", "mental_health", "substance_use", "cognition", "medications",
    "diabetes", "infection", "isolation", "wound", "respiratory", "cardiac", "vitals", "labs", "imaging",
    "diagnosis", "behavior", "legal", "home_health", "hospice", "iv_access", "follow_up",
    "discharge_plan", "language", "other",
]
# Pages most likely to hold gate evidence are read first.
READ_ORDER = ["ihh_referral_form", "pt_ot", "nursing", "psychiatry", "history_physical", "progress_note",
              "consult", "social_work", "medication_list", "discharge", "orders", "wound", "vitals",
              "labs", "imaging", "ecg", "face_sheet", "authorization", "other", "fax_cover"]

STATUSES = ["met", "not_met", "cant_tell", "not_applicable"]

S = llm.strict

SORT_SCHEMA = S({"type": "object", "properties": {"pages": {"type": "array", "items": {"type": "object", "properties": {
    "page": {"type": "integer"},
    "page_type": {"type": "string", "enum": PAGE_TYPES},
    "rotation": {"type": "integer", "enum": [0, 90, 180, 270]},
    "mostly_redacted": {"type": "boolean"},
    "earlier_stay": {"type": "boolean"},
    "language": {"type": "string", "enum": ["en", "es", "other"]},
    "possible_unredacted_identifier": {"type": "boolean"},
}}}}})

READ_SCHEMA = S({"type": "object", "properties": {"pages": {"type": "array", "items": {"type": "object", "properties": {
    "page": {"type": "integer"},
    "summary": {"type": "string"},
    "facts": {"type": "array", "items": {"type": "object", "properties": {
        "topic": {"type": "string", "enum": TOPICS},
        "statement": {"type": "string"},
        "statement_es": {"type": "string"},
        "quote": {"type": "string"},
    }}},
}}}}})

RULES_SCHEMA = S({"type": "object", "properties": {
    "reason_for_referral": {"type": "string"},
    "reason_for_referral_es": {"type": "string"},
    "wheelchair_dependent": {"type": "string", "enum": ["yes", "no", "unknown"]},
    "preferred_language": {"type": "string"},
    "rules": {"type": "array", "items": {"type": "object", "properties": {
        "rule_id": {"type": "string"},
        "status": {"type": "string", "enum": STATUSES},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "explanation_es": {"type": "string"},
    }}},
    "diagnoses": {"type": "array", "items": {"type": "object", "properties": {
        "rule_id": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "explanation_es": {"type": "string"},
    }}},
    "checklist": {"type": "array", "items": {"type": "object", "properties": {
        "doc_id": {"type": "string"},
        "status": {"type": "string", "enum": ["present", "missing", "cant_tell"]},
        "pages": {"type": "array", "items": {"type": "integer"}},
    }}},
    "conflicts": {"type": "array", "items": {"type": "object", "properties": {
        "topic": {"type": "string"},
        "description": {"type": "string"},
        "description_es": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
    }}},
    "questions": {"type": "array", "items": {"type": "object", "properties": {
        "en": {"type": "string"}, "es": {"type": "string"},
        "rule_ids": {"type": "array", "items": {"type": "string"}},
    }}},
    "summary": {"type": "string"},
    "summary_es": {"type": "string"},
}})

VERIFY_SCHEMA = S({"type": "object", "properties": {"checks": {"type": "array", "items": {"type": "object", "properties": {
    "fact_id": {"type": "string"},
    "verdict": {"type": "string", "enum": ["found", "paraphrase", "not_found"]},
}}}}})

GROUND = """You are helping a recuperative care referral coordinator at Illumination Health + Home (IHH) review a
faxed hospital referral packet. The packets are de-identified: black boxes mean "removed for privacy",
never "missing". Dates are blacked out; times of day may remain.
Never invent facts. If the packet does not say it, it is unknown. A confident wrong answer is the worst outcome."""

SORT_PROMPT = GROUND + """

For each page image, label it. page is the number printed in the label before the image.
- rotation: degrees CLOCKWISE the page must be turned to read it upright (sideways = 90 or 270, upside down = 180).
- mostly_redacted: most of the content is blacked out.
- earlier_stay: the page is clearly from an earlier admission or older record.
- possible_unredacted_identifier: true ONLY if you can see a patient or clinician name, full date of birth,
  street address, phone number, medical record or account number that was NOT blacked out. Do not transcribe it."""

READ_PROMPT = GROUND + """

Read each page image carefully (pages are already turned upright) and extract every fact that could matter
for admission to recuperative care: housing, self-care (ADLs, bathing, toileting, transfers, walking distance,
assistance level, DME), cognition and orientation, mental health (suicidal ideation, hallucinations, psychosis,
aggression, conservatorship), substance use and withdrawal (CIWA), medications and who administers them,
insulin and glucose readings, infections, isolation, MRSA/COVID swabs, wounds and their location, IV lines,
oxygen, vitals, troponin, EF, ECG, imaging, diagnoses, home health, hospice, follow-up plans, preferred language.

For each fact:
- quote: copy the words EXACTLY as written on the page, in the page's own language, 3 to 25 words. Never fix
  spelling, never combine text from two places, never quote a black box. Handwriting you cannot read: skip it.
- statement: one plain English sentence saying what the quote shows. statement_es: the same in Spanish.
A redacted field is not a fact. A checkbox counts only if you can see it is marked.""" + llm.PLAIN

RULES_PROMPT = GROUND + """

You get IHH's rulebook and the facts extracted from one packet, each with an ID like F12, a page number and a
verbatim quote. Assess the packet against the rulebook.

Status is from IHH's point of view:
- met: the rule is satisfied (for an exclusion: the excluding condition is clearly absent; for a document: it is in the packet).
- not_met: the rule is a problem for admission (a must is not satisfied, an exclusion applies, a required document
  is absent, or a required arrangement is not confirmed).
- cant_tell: the facts do not settle it. Use this when evidence is thin, conflicting, or depends on dates or hours.
- not_applicable: the rule does not apply to this patient (e.g. diabetes rules for a patient without diabetes).
"Not in the packet" means unknown, never normal. Cite fact_ids for every met or not_met. Never cite a fact that
does not support the status. The chart beats the referral form: if the form says one thing and a PT/OT, nursing
or psychiatry note says another, report the conflict and use cant_tell or not_met, never silently pick the form.

Give a status for every rule ID in the list you are given. In diagnoses, list only by-body-system IDs
(INT-, OPH-, RSP-, MSK-, GI-, END-, GU-, CIR-, NEU-) that the facts show apply. In checklist give every DOC ID;
pages are the page numbers where that document is. A redacted field is not a missing document.
questions: what the coordinator should ask the hospital case manager, each tied to rule IDs.
summary: 3 to 5 plain sentences for the coordinator. Every *_es field is the same text in Spanish.
No medical advice. Do not recommend approve or deny; a person decides.""" + llm.PLAIN

VERIFY_PROMPT = """You are the quality-control step. For each numbered quote, look at the page image it claims to
come from and decide:
- found: the quote is on that page, word for word or with only trivial OCR differences.
- paraphrase: the meaning is on the page but the wording differs.
- not_found: it is not on that page.
Be strict. Judge only what you can see."""


class Review:
    """One referral packet moving through the stages."""

    def __init__(self, pages: list[Page], name: str, received_at: float | None = None):
        self.id = uuid.uuid4().hex[:10]
        self.name = name
        self.pages = pages
        self.received_at = received_at or time.time()
        self.stage = "queued"
        self.progress: list[str] = []
        self.error: str | None = None
        self.report: dict | None = None
        self.usage = llm.Usage()

    def log(self, msg: str):
        self.progress.append(msg)


def _batches(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]


def _page_content(pages: list[Page], upright: bool) -> list:
    content = []
    for p in pages:
        content.append({"type": "text", "text": f"Page {p.number}:"})
        content.append(llm.image_block(p.jpeg(upright=upright)))
    return content


def _ahash(img: Image.Image) -> int:
    small = img.resize((16, 16)).convert("L")
    px = list(small.getdata())
    avg = sum(px) / len(px)
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def find_duplicates(pages: list[Page]) -> dict[int, int]:
    """page -> earlier identical page, via a perceptual hash. Runs locally, no API call."""
    seen: dict[int, int] = {}
    dup = {}
    for p in pages:
        h = _ahash(p.image)
        match = next((n for hh, n in seen.items() if bin(hh ^ h).count("1") <= 6), None)
        if match:
            dup[p.number] = match
        else:
            seen[h] = p.number
    return dup


def run(review: Review, workers: int = 6) -> dict:
    pages = review.pages
    call = functools.partial(llm.call_json, usage=review.usage)
    by_num = {p.number: p for p in pages}
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        # 1. sort
        review.stage = "sort"
        review.log(f"Sorting {len(pages)} pages")
        dups = find_duplicates(pages)
        sorted_pages: dict[int, dict] = {}
        for res in pool.map(lambda b: call(system=SORT_PROMPT, content=_page_content(b, False),
                                                    schema=SORT_SCHEMA, model=config.fast_model(),
                                                    effort="low", max_tokens=8000),
                            _batches(pages, 8)):
            for item in res["pages"]:
                if item["page"] in by_num:
                    sorted_pages[item["page"]] = item
        for p in pages:
            meta = sorted_pages.setdefault(p.number, {"page": p.number, "page_type": "other", "rotation": 0,
                                                      "mostly_redacted": False, "earlier_stay": False,
                                                      "language": "en", "possible_unredacted_identifier": False})
            p.rotation = meta["rotation"]
            meta["duplicate_of"] = dups.get(p.number)
            meta["blank"] = meta["page_type"] == "blank"

        phi_pages = [n for n, m in sorted_pages.items() if m["possible_unredacted_identifier"]]
        if phi_pages:
            review.log(f"Possible identifier on page(s) {phi_pages}: stop and tell an organizer")

        # 2. read
        review.stage = "read"
        to_read = [p for p in pages if not sorted_pages[p.number]["blank"] and not sorted_pages[p.number]["duplicate_of"]]
        rank = {t: i for i, t in enumerate(READ_ORDER)}
        to_read.sort(key=lambda p: (rank.get(sorted_pages[p.number]["page_type"], 99), p.number))
        review.log(f"Reading {len(to_read)} pages (skipped {len(pages) - len(to_read)} blank or duplicate)")
        facts = []
        page_summaries = {}
        results = pool.map(lambda b: call(system=READ_PROMPT, content=_page_content(b, True),
                                                   schema=READ_SCHEMA, effort="medium", max_tokens=32000),
                           _batches(to_read, 4))
        for res in results:
            for pg in res["pages"]:
                if pg["page"] not in by_num:
                    continue
                page_summaries[pg["page"]] = pg["summary"]
                for f in pg["facts"]:
                    if f["quote"].strip():
                        facts.append({"page": pg["page"], **f})
        facts.sort(key=lambda f: f["page"])
        for i, f in enumerate(facts, 1):
            f["id"] = f"F{i}"
        review.log(f"Found {len(facts)} facts with quotes")

        # 3. rules
        review.stage = "rules"
        review.log("Checking the facts against IHH's criteria")
        fact_lines = "\n".join(
            f"{f['id']} [page {f['page']}, {sorted_pages[f['page']]['page_type']}"
            f"{', EARLIER STAY' if sorted_pages[f['page']]['earlier_stay'] else ''}] {f['topic']}: "
            f"{f['statement']} | quote: \"{f['quote']}\"" for f in facts)
        page_lines = "\n".join(f"page {n}: {m['page_type']}" + (" (redacted)" if m["mostly_redacted"] else "")
                               for n, m in sorted(sorted_pages.items()))
        assessed = rules.assessed_rule_ids()
        assessment = call(
            system=RULES_PROMPT,
            content=[{"type": "text", "text":
                      f"RULEBOOK\n{rules.rulebook_text()}\n\nRULE IDS TO ASSESS\n{', '.join(assessed)}\n\n"
                      f"DOC IDS\n{', '.join(rules.checklist_ids())}\n\nPAGES\n{page_lines}\n\nFACTS\n{fact_lines or '(none)'}"}],
            schema=RULES_SCHEMA, effort="high", max_tokens=64000)

        # 4. verify every quote that is cited anywhere
        review.stage = "verify"
        fact_by_id = {f["id"]: f for f in facts}
        cited = set()
        for r in assessment["rules"] + assessment["diagnoses"] + assessment["conflicts"]:
            cited.update(i for i in r["fact_ids"] if i in fact_by_id)
        review.log(f"Double-checking {len(cited)} cited quotes against the page images")
        by_page: dict[int, list] = {}
        for fid in sorted(cited, key=lambda x: int(x[1:])):
            by_page.setdefault(fact_by_id[fid]["page"], []).append(fact_by_id[fid])

        def verify(group):
            content = []
            for pnum, fs in group:
                content.append({"type": "text", "text": f"Page {pnum} quotes:\n" + "\n".join(f"{f['id']}: \"{f['quote']}\"" for f in fs)})
                content.append(llm.image_block(by_num[pnum].jpeg(upright=True)))
            return call(system=VERIFY_PROMPT, content=content, schema=VERIFY_SCHEMA,
                                 effort="low", max_tokens=8000)

        for f in facts:
            f["verify"] = "unchecked"
        for res in pool.map(verify, _batches(sorted(by_page.items()), 3)):
            for c in res["checks"]:
                if c["fact_id"] in fact_by_id:
                    fact_by_id[c["fact_id"]]["verify"] = c["verdict"]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # 5. qc
    review.stage = "qc"
    report = quality_control(assessment, facts, sorted_pages, page_summaries)
    report.update(id=review.id, packet=review.name, received_at=review.received_at, reviewed_at=time.time(),
                  model=config.model(), fast_model=config.fast_model(), cost=review.usage.as_dict())
    report["flags"]["phi_pages"] = phi_pages
    review.report = report
    review.stage = "done"
    review.log("Review ready")
    return report


def quality_control(assessment: dict, facts: list[dict], sorted_pages: dict, page_summaries: dict) -> dict:
    """Plain-code checks on Claude's assessment. Every downgrade is recorded so people can see it."""
    all_r = rules.all_rules()
    fact_by_id = {f["id"]: f for f in facts}
    good = {fid for fid, f in fact_by_id.items() if f.get("verify") in ("found", "paraphrase")}
    downgrades = []

    def keep_ids(ids):
        return [i for i in ids if i in good]

    by_id = {}
    for r in assessment["rules"]:
        if r["rule_id"] in all_r and r["rule_id"] not in by_id:
            by_id[r["rule_id"]] = r
    out_rules = []
    for rid in rules.assessed_rule_ids():
        meta = all_r[rid]
        r = by_id.get(rid) or {"rule_id": rid, "status": "cant_tell", "fact_ids": [],
                               "explanation": "Not assessed.", "explanation_es": "No evaluado."}
        status = r["status"]
        notes = []
        cited = [i for i in r["fact_ids"] if i in fact_by_id]
        kept = keep_ids(cited)
        # A missing document has no page to quote, so "not met" on a document rule stands on its own.
        absent_doc = meta["kind"] == "document" and status == "not_met" and not cited
        if status in ("met", "not_met") and not kept and not absent_doc:
            notes.append("evidence_unverified" if cited else "no_evidence")
            downgrades.append({"rule_id": rid, "from": status, "to": "cant_tell", "reason": notes[-1]})
            status = "cant_tell"
        if rid in rules.DATE_RULES and status == "met":
            notes.append("date_redacted")
            downgrades.append({"rule_id": rid, "from": "met", "to": "cant_tell", "reason": "date_redacted"})
            status = "cant_tell"
        if rid in rules.HUMAN_ONLY and status == "not_met":
            notes.append("human_decision")
        out_rules.append({
            "rule_id": rid, "kind": meta["kind"], "section": meta["section"], "text": meta["text"],
            "superseded_by": meta.get("superseded_by"), "gate": rules.gate_of(rid), "status": status,
            "fact_ids": kept, "explanation": r["explanation"], "explanation_es": r["explanation_es"],
            "notes": notes,
        })

    diagnoses = []
    for d in assessment["diagnoses"]:
        meta = all_r.get(d["rule_id"])
        if not meta or meta["group"] not in ("eligible", "ineligible"):
            continue
        kept = keep_ids(d["fact_ids"])
        diagnoses.append({"rule_id": d["rule_id"], "kind": meta["kind"], "section": meta["section"],
                          "text": meta["text"], "ineligible": meta["group"] == "ineligible",
                          "verified": bool(kept), "fact_ids": kept or [i for i in d["fact_ids"] if i in fact_by_id],
                          "explanation": d["explanation"], "explanation_es": d["explanation_es"]})

    page_nums = set(sorted_pages)
    checklist = []
    given = {c["doc_id"]: c for c in assessment["checklist"]}
    for did in rules.checklist_ids():
        c = given.get(did) or {"doc_id": did, "status": "cant_tell", "pages": []}
        pages = [p for p in c["pages"] if p in page_nums]
        status = c["status"]
        if status == "present" and not pages:
            status = "cant_tell"
        if status == "missing" and pages:
            status = "cant_tell"
        notes = ["date_redacted"] if did in rules.DATE_RULES and status == "present" else []
        checklist.append({"doc_id": did, "text": all_r[did]["text"], "status": status, "pages": pages, "notes": notes})
    if not any(m["page_type"] == "ihh_referral_form" for m in sorted_pages.values()):
        checklist[0]["status"] = "missing"

    conflicts = [{**c, "fact_ids": [i for i in c["fact_ids"] if i in fact_by_id]} for c in assessment["conflicts"]]

    gates = {}
    status_of = {r["rule_id"]: r for r in out_rules}
    for g, ids in rules.GATES.items():
        considered = [status_of[i] for i in ids if i in status_of and not status_of[i]["superseded_by"]]
        if any(r["status"] == "not_met" and "human_decision" not in r["notes"] for r in considered):
            gs = "not_met"
        # The form screen only restates what the case manager wrote; the core chart rules decide "can't tell".
        elif any(r["status"] == "cant_tell" for r in considered if r["rule_id"] in rules.GATE_CORE[g]):
            gs = "cant_tell"
        else:
            gs = "met"
        gates[g] = {"status": gs, "rule_ids": ids}

    conditions = [r for r in out_rules if r["rule_id"] in rules.CONDITIONAL and r["status"] != "not_applicable"]
    conditions += [d for d in diagnoses if d["rule_id"] in rules.CONDITIONAL]

    recommendation = route(out_rules, diagnoses, checklist, gates)
    return {
        "pages": [{**sorted_pages[n], "summary": page_summaries.get(n, "")} for n in sorted(sorted_pages)],
        "facts": facts,
        "reason_for_referral": assessment["reason_for_referral"],
        "reason_for_referral_es": assessment["reason_for_referral_es"],
        "wheelchair_dependent": assessment["wheelchair_dependent"],
        "preferred_language": assessment["preferred_language"] or "unknown",
        "gates": gates,
        "rules": out_rules,
        "diagnoses": diagnoses,
        "checklist": checklist,
        "conflicts": conflicts,
        "conditions": [{"rule_id": c["rule_id"], "text": c["text"], "status": c.get("status", "cant_tell")} for c in conditions],
        "questions": assessment["questions"],
        "summary": assessment["summary"],
        "summary_es": assessment["summary_es"],
        "recommendation": recommendation,
        "flags": {"no_referral_form": checklist[0]["status"] == "missing"},
        "qc": {"facts": len(facts),
               "verified": sum(1 for f in facts if f["verify"] == "found"),
               "paraphrase": sum(1 for f in facts if f["verify"] == "paraphrase"),
               "not_found": sum(1 for f in facts if f["verify"] == "not_found"),
               "downgrades": downgrades},
    }


def route(out_rules, diagnoses, checklist, gates) -> dict:
    """Suggested route. Only a clinician can deny; nothing here is a decision."""
    blockers = [r["rule_id"] for r in out_rules
                if r["status"] == "not_met" and r["kind"] in ("must", "exclude")
                and not r["superseded_by"] and "human_decision" not in r["notes"]]
    blockers += [d["rule_id"] for d in diagnoses if d["ineligible"] and d["verified"] and d["rule_id"] not in rules.HUMAN_ONLY]
    human = [r["rule_id"] for r in out_rules if "human_decision" in r["notes"]]
    human += [d["rule_id"] for d in diagnoses if d["rule_id"] in rules.HUMAN_ONLY]
    missing_docs = [c["doc_id"] for c in checklist if c["status"] == "missing"]
    open_items = [r["rule_id"] for r in out_rules
                  if r["status"] in ("not_met", "cant_tell") and r["kind"] in ("document", "conditional")]
    gate_unclear = [g for g, v in gates.items() if v["status"] == "cant_tell"]

    if blockers:
        code = "likely_no"
    elif gate_unclear or human:
        code = "clinical_check"
    elif missing_docs or open_items:
        code = "needs_info"
    else:
        code = "likely_yes"
    return {"code": code, "blockers": blockers, "human_review": human, "missing_docs": missing_docs,
            "open_items": open_items, "gate_unclear": gate_unclear,
            "route_clinical": code in ("likely_no", "clinical_check")}
