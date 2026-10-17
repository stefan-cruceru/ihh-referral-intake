"""The organizers' synthetic patients S01-S10, shown as patient profiles and as practice reviews.

Everything here is invented (see README.md). The practice review for each patient is built from
the organizers' answer key, run through the app's own quality_control(), so routes, gates and
drafts come out exactly as a live review would show them. Each quote is a real line from that
page's text, picked to match the answer key's reason.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRANSLATION_NOTE_ES = "Traducción por IA; pendiente de revisión por personal bilingüe de IHH."

# Answer-key document types -> referral checklist IDs.
DOC_OF = {"form": "DOC-1", "face": "DOC-2", "auth": "DOC-3", "hp": "DOC-4", "progress": "DOC-5",
          "vitals": "DOC-6", "meds": "DOC-7", "ptot": "DOC-8", "nursing": "DOC-8", "labs": "DOC-9"}
TYPE_OF = {"form": "ihh_referral_form", "cover": "fax_cover", "face": "face_sheet", "auth": "authorization",
           "hp": "history_physical", "progress": "progress_note", "ptot": "pt_ot", "nursing": "nursing",
           "vitals": "vitals", "labs": "labs", "imaging": "imaging", "meds": "medication_list",
           "cm": "social_work", "consult": "consult"}
STATUS = {"met": "met", "not_met": "not_met", "unknown": "cant_tell"}


@lru_cache(maxsize=1)
def profiles() -> list[dict]:
    return json.loads((HERE / "profiles.json").read_text(encoding="utf-8"))["profiles"]


@lru_cache(maxsize=1)
def answer_key() -> dict:
    return {p["packet_id"]: p for p in json.loads((HERE / "answer-key.json").read_text(encoding="utf-8"))["packets"]}


@lru_cache(maxsize=1)
def _translations() -> dict[str, str]:
    return json.loads((HERE / "translations.es.json").read_text(encoding="utf-8"))


def _spanish(text: str) -> str:
    # Keyed by the original wording so an edited answer cannot silently reuse a stale translation.
    # These practice translations are bundled, not fetched from a model or external service.
    return _translations()[text]


def packet_path(pid: str) -> Path | None:
    p = HERE / pid / "packet.pdf"
    return p if p.is_file() else None


def page_text(pid: str, page: int) -> str:
    f = HERE / pid / "text" / f"p{page:02d}.txt"
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def _best_line(text: str, why: str) -> str | None:
    want = _words(why)
    best, score = None, 0
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8 or "synthetic" in line.lower():
            continue
        s = len(want & _words(line))
        if s > score:
            best, score = line, s
    if best and len(best) > 160:
        best = best[:157].rsplit(" ", 1)[0]
    return best


def _no_verdict(summary: str) -> str:
    return re.sub(r"^(Approve|Deny)( for now)?\.\s+", "", summary)


def _report(pid: str) -> dict:
    from carebridge import intake, rules

    key = answer_key()[pid]
    all_r = rules.all_rules()
    facts, by_rule = [], {}
    for f in key["findings"]:
        ids = []
        for pg in f["pages"]:
            q = _best_line(page_text(pid, pg), f["why"])
            if q:
                fid = f"F{len(facts) + 1}"
                facts.append({"id": fid, "page": pg, "topic": "other", "statement": f["why"], "statement_es": _spanish(f["why"]),
                              "quote": q, "verify": "found"})
                ids.append(fid)
        by_rule[f["rule"]] = (f, ids)

    assessed, diagnoses = [], []
    for rid, (f, ids) in by_rule.items():
        meta = all_r.get(rid)
        if not meta:
            continue
        if meta["group"] in ("eligible", "ineligible"):
            if meta["group"] == "eligible" and f["status"] == "met" or meta["group"] == "ineligible" and f["status"] != "met":
                diagnoses.append({"rule_id": rid, "fact_ids": ids, "explanation": f["why"], "explanation_es": _spanish(f["why"])})
        else:
            assessed.append({"rule_id": rid, "status": STATUS[f["status"]], "fact_ids": ids,
                             "explanation": f["why"], "explanation_es": _spanish(f["why"])})
    listed = {r["rule_id"] for r in assessed}
    for rid in rules.assessed_rule_ids():
        if rid not in listed:
            assessed.append({"rule_id": rid, "status": "not_applicable", "fact_ids": [],
                             "explanation": "Not listed in the organizers' answer key for this patient.",
                             "explanation_es": "No aparece en la clave de respuestas de los organizadores para este paciente."})

    pages_of: dict[str, list[int]] = {}
    for m in key["page_map"]:
        if m["document"] in DOC_OF:
            pages_of.setdefault(DOC_OF[m["document"]], []).append(m["page"])
    checklist = [{"doc_id": d, "status": "missing" if d in key["missing_documents"] else ("present" if pages_of.get(d) else "cant_tell"),
                  "pages": [] if d in key["missing_documents"] else pages_of.get(d, [])} for d in rules.checklist_ids()]
    conflicts = [{"topic": ", ".join(c["documents"]), "description": c["what"], "description_es": _spanish(c["what"]), "fact_ids": []}
                 for c in key["contradictions"]]
    sorted_pages = {m["page"]: {"page": m["page"], "page_type": TYPE_OF.get(m["document"], "other"), "rotation": 0,
                                "mostly_redacted": False, "earlier_stay": False, "language": "en",
                                "possible_unredacted_identifier": False, "duplicate_of": None, "blank": False}
                    for m in key["page_map"]}
    prof = next(p for p in profiles() if p["id"] == pid)
    assessment = {
        "reason_for_referral": prof["diagnosis"], "reason_for_referral_es": _spanish(prof["diagnosis"]),
        "wheelchair_dependent": "unknown", "preferred_language": prof["patient"].get("language") or "",
        "rules": assessed, "diagnoses": diagnoses, "checklist": checklist, "conflicts": conflicts,
        "questions": [{"en": q, "es": _spanish(q), "rule_ids": []} for q in key["follow_up"]],
        # The key's summary opens with the organizers' verdict ("Deny."). The review only points
        # things out, so the verdict stays in answer_key_decision, shown on the practice page's reveal.
        "summary": _no_verdict(key["summary"]),
        "summary_es": _spanish(_no_verdict(key["summary"])) + "\n\n" + TRANSLATION_NOTE_ES,
    }
    # The organizers' typed text of each page, so the viewer and the critical-value check can read it.
    # A person typed it, so it is read for sure (100), and it stands in for both reads.
    typed = {m["page"]: {"transcript": page_text(pid, m["page"]), "handwriting": "none", "ocr_confidence": 100,
                         "second_transcript": page_text(pid, m["page"])} for m in key["page_map"]}
    rep = intake.quality_control(assessment, facts, sorted_pages, {m["page"]: m["title"] for m in key["page_map"]}, typed)
    rep.update(id=f"sample-{pid}", packet=f"{pid}.pdf", received_at=None, reviewed_at=None, model="organizers' answer key",
               fast_model="", sample=True, synthetic=True, answer_key_decision=key["decision"])
    rep["flags"]["phi_pages"] = []
    return rep


def client_situation(pid: str) -> tuple[str, list[str]]:
    """What the client needs after discharge, from the profile, with dates and names left out so the
    PHI guard lets it through. Returns (situation text, needs for the offline match)."""
    p = next(x for x in profiles() if x["id"] == pid)
    story = re.sub(r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", "soon", p["story"])
    # The diagnosis can carry a surgery date too ("fixation 08/18/2026"), which the guard rightly blocks.
    diagnosis = re.sub(r"\s*\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", "", p["diagnosis"])
    text = (f"{p['patient']['age']} years old. Speaks {p['patient']['language']}. {p['patient']['insurance']}. "
            f"In the hospital for: {diagnosis}. {story}")
    from carebridge import resources

    return text, resources.needs_from_text(text) or ["shelter", "benefits"]


@lru_cache(maxsize=1)
def sample_reports() -> dict:
    return {p["id"]: _report(p["id"]) for p in profiles()}
