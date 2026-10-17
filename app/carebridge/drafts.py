"""Drafts a person checks and sends. Nothing here sends anything.

Built from templates plus the verified review, not free-written by Claude, so a draft can only
list what the review actually found. The English and Spanish drafts always carry the same rule
and document IDs (docs/bilingual.md section 2).
"""

import csv
import io
from datetime import datetime

from . import critical, rules

AI_NOTE = {
    "en": "Draft. Not sent. Check before sending.",
    "es": "Borrador traducido por IA. Revíselo antes de enviarlo.",
}
REMOVED = {"en": "removed for privacy", "es": "eliminado por privacidad"}
UNKNOWN = {"en": "unknown", "es": "desconocido"}

DOC_ES = {
    "DOC-1": "Formulario de referido de Illumination Health + Home",
    "DOC-2": "Hoja de datos demográficos del paciente",
    "DOC-3": "Formulario/LOA/autorización de CalOptima",
    "DOC-4": "Historia clínica y examen físico (H&P)",
    "DOC-5": "Notas de evolución actuales (si aplica)",
    "DOC-6": "Signos vitales actualizados (últimas 24 horas)",
    "DOC-7": "Lista de medicamentos",
    "DOC-8": "Notas de PT/OT o de enfermería",
    "DOC-9": "Cultivo de sangre o de herida (si aplica)",
    "DOC-10": "Suministro de 30 días de todos los medicamentos",
}


def _doc(did, lang):
    return DOC_ES[did] if lang == "es" else rules.all_rules()[did]["text"]


def _hhmm(ts):
    return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")


def missing_items(card: dict, report: dict, lang: str) -> dict:
    """One message to the case manager listing everything missing at once: documents, critical values
    nobody found, the review's questions and what the clinical reviewer asked for."""
    docs = [c["doc_id"] for c in report["checklist"] if c["status"] == "missing"]
    qs = [c["label"][lang] for c in critical.missing(report)]
    qs += [q[lang] for q in report["questions"]]
    qs += [a["text"] for a in card.get("clinical_asks") or []]
    cm = card.get("case_manager") or UNKNOWN[lang]
    case = card["case_no"]
    if lang == "es":
        lines = [f"Asunto: Referido {case}: falta información", "",
                 f"Hola {cm}:", "",
                 f"Recibimos el referido {case} a las {_hhmm(card['arrived_at'])}. Para poder darle una respuesta, necesitamos:"]
        lines += [f"  - {_doc(d, 'es')} ({d})" for d in docs]
        lines += [f"  - {q}" for q in qs]
        lines += ["", "Envíelo todo en un solo correo o fax si es posible, citando el número de referido.",
                  "Gracias,", "Equipo de referidos de IHH"]
    else:
        lines = [f"Subject: Referral {case}: information needed", "",
                 f"Hi {cm},", "",
                 f"We received referral {case} at {_hhmm(card['arrived_at'])}. To give you an answer we need:"]
        lines += [f"  - {_doc(d, 'en')} ({d})" for d in docs]
        lines += [f"  - {q}" for q in qs]
        lines += ["", "Please send everything in one email or fax if you can, quoting the referral number.",
                  "Thank you,", "IHH referral team"]
    return {"kind": "missing_items", "to": card.get("cm_email"), "doc_ids": docs, "text": "\n".join(lines), "note": AI_NOTE[lang]}


def chase(card: dict, step: str, lang: str) -> dict:
    """step: 'nudge' to the case manager or 'supervisor'."""
    case = card["case_no"]
    if step == "supervisor":
        who, to = card.get("supervisor") or UNKNOWN[lang], card.get("sup_email")
        text = (f"Asunto: Referido {case}: sin respuesta\n\nHola {who}:\n\nEnviamos una solicitud de información para el referido {case} "
                f"y aún no recibimos respuesta de {card.get('case_manager') or 'su equipo'}. El paciente puede perder la cama si no "
                f"respondemos a tiempo. ¿Puede ayudarnos a conseguir lo que falta?\n\nGracias,\nEquipo de referidos de IHH"
                if lang == "es" else
                f"Subject: Referral {case}: no reply yet\n\nHi {who},\n\nWe sent an information request for referral {case} and haven't "
                f"heard back from {card.get('case_manager') or 'your team'}. The patient could lose the bed if we can't answer in time. "
                f"Could you help us get the missing items?\n\nThank you,\nIHH referral team")
    else:
        who, to = card.get("case_manager") or UNKNOWN[lang], card.get("cm_email")
        text = (f"Asunto: Referido {case}: seguimiento\n\nHola {who}:\n\nSolo para dar seguimiento a nuestra solicitud anterior sobre "
                f"el referido {case}. En cuanto recibamos lo que falta, le damos una respuesta.\n\nGracias,\nEquipo de referidos de IHH"
                if lang == "es" else
                f"Subject: Referral {case}: following up\n\nHi {who},\n\nJust following up on our earlier request for referral {case}. "
                f"As soon as we have the missing items we can give you an answer.\n\nThank you,\nIHH referral team")
    return {"kind": f"chase_{step}", "to": to, "text": text, "note": AI_NOTE[lang]}


def more_time(card: dict, lang: str) -> dict:
    case = card["case_no"]
    text = (f"Asunto: Referido {case}: necesitamos un poco más de tiempo\n\nHola {card.get('case_manager') or ''}:\n\n"
            f"Seguimos revisando el referido {case}. Necesitamos un poco más de tiempo para darle una respuesta segura. "
            f"Por favor, no dé de alta al paciente hacia nuestro programa todavía.\n\nEquipo de referidos de IHH"
            if lang == "es" else
            f"Subject: Referral {case}: we need a little more time\n\nHi {card.get('case_manager') or ''},\n\n"
            f"We are still reviewing referral {case} and need a little more time to give you a safe answer. "
            f"Please don't discharge the patient to us yet.\n\nIHH referral team")
    return {"kind": "more_time", "to": card.get("cm_email"), "text": text, "note": AI_NOTE[lang]}


def clinical_handoff(card: dict, report: dict, lang: str) -> dict:
    """What the clinical line sees for a likely no or a gate that can't be settled."""
    rec = report["recommendation"]
    facts = {f["id"]: f for f in report["facts"]}
    lines = [f"{'Referido' if lang == 'es' else 'Referral'} {card['case_no']} · {card.get('hospital', '')}",
             ("Probable rechazo: enviado a revisión clínica" if rec["code"] == "likely_no" else "En revisión clínica")
             if lang == "es" else
             ("Likely no: sent to the clinical line" if rec["code"] == "likely_no" else "Clinical check"), ""]
    for r in report["rules"]:
        if r["rule_id"] in rec["blockers"] + rec["human_review"] or (r["gate"] and r["status"] == "cant_tell" and r["rule_id"] in rules.GATE_CORE[r["gate"]]):
            lines.append(f"{r['rule_id']} [{r['status']}] {r['text']}")
            for fid in r["fact_ids"]:
                f = facts[fid]
                lines.append(f"    p.{f['page']}: \"{f['quote']}\"")
    for d in report["diagnoses"]:
        if d["rule_id"] in rec["blockers"]:
            lines.append(f"{d['rule_id']} [ineligible] {d['text']}")
            for fid in d["fact_ids"]:
                lines.append(f"    p.{facts[fid]['page']}: \"{facts[fid]['quote']}\"")
    lines += ["", "Solo un clínico puede negar un referido." if lang == "es" else "Only a clinician can deny a referral."]
    return {"kind": "clinical", "to": "clinical line", "text": "\n".join(lines), "note": AI_NOTE[lang]}


def decision_reply(card: dict, report: dict, decision: str, reason: str, lang: str) -> dict:
    case = card["case_no"]
    if decision == "accepted":
        text = (f"Asunto: Referido {case}: aceptado\n\nAceptado según la información recibida a las {_hhmm(card['arrived_at'])}. "
                f"Ya puede dar de alta al paciente. Avísenos de cualquier cambio antes del traslado.\n"
                if lang == "es" else
                f"Subject: Referral {case}: accepted\n\nAccepted based on information received at {_hhmm(card['arrived_at'])}. "
                f"OK to discharge. Please report any change before transport.\n")
        conds = report.get("conditions") or []
        if conds:
            text += ("\nAntes de la llegada, confirme:\n" if lang == "es" else "\nBefore arrival, please confirm:\n")
            text += "\n".join(f"  - {c['rule_id']}: {c['text']}" for c in conds)
    elif decision == "intake_cleared":
        text = (f"Asunto: Referido {case}\n\nAdmisión preliminar aprobada. Todavía no dé de alta al paciente: falta la revisión clínica."
                if lang == "es" else
                f"Subject: Referral {case}\n\nIntake cleared. Do not discharge yet: the clinical check is still open.")
    else:
        text = (f"Asunto: Referido {case}: no podemos aceptarlo\n\nDespués de la revisión clínica no podemos aceptar este referido. "
                f"Motivo: {reason}\n"
                if lang == "es" else
                f"Subject: Referral {case}: we can't accept this referral\n\nAfter clinical review we can't accept this referral. "
                f"Reason: {reason}\n")
    return {"kind": f"decision_{decision}", "to": card.get("cm_email"), "text": text, "note": AI_NOTE[lang]}


def handoffs(card: dict, report: dict | None, lang: str) -> dict:
    """The three manual steps after a yes: Kipu fields, census row, ops email. Drafts only."""
    reason = (report or {}).get("reason_for_referral_es" if lang == "es" else "reason_for_referral") or UNKNOWN[lang]
    pref = (report or {}).get("preferred_language") or UNKNOWN[lang]
    site = card.get("site") or "Orange County"
    kipu = [
        ("Patient name", REMOVED[lang]), ("Date of birth", REMOVED[lang]),
        ("Referral number", card["case_no"]), ("Referring hospital", card.get("hospital") or UNKNOWN[lang]),
        ("Case manager", card.get("case_manager") or UNKNOWN[lang]), ("Reason for referral", reason),
        ("Preferred language", pref), ("Site", site),
        ("Conditions before arrival", "; ".join(c["rule_id"] for c in (report or {}).get("conditions", [])) or "none"),
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Referral", "Received", "Hospital", "Reason", "Preferred language", "Owner", "Status"])
    w.writerow([card["case_no"], _hhmm(card["arrived_at"]), card.get("hospital", ""), reason, pref, card.get("owner", ""), "Accepted"])
    ops = (f"Asunto: Nuevo ingreso aceptado: {card['case_no']}\n\nEquipo de operaciones de {site}:\n\nAceptamos el referido {card['case_no']} "
           f"de {card.get('hospital', '')}.\nMotivo: {reason}\nIdioma preferido: {pref}\nResponsable: {card.get('owner', '')}\n"
           if lang == "es" else
           f"Subject: New admission accepted: {card['case_no']}\n\n{site} operations team,\n\nWe accepted referral {card['case_no']} "
           f"from {card.get('hospital', '')}.\nReason: {reason}\nPreferred language: {pref}\nOwner: {card.get('owner', '')}\n")
    return {"kipu_fields": kipu, "census_tab": site, "census_csv": buf.getvalue(), "ops_email": ops, "note": AI_NOTE[lang]}
