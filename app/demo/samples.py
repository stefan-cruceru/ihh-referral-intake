"""Hand-written sample reviews of the three invented packets in packets.py.

These are examples written by the team, not Claude output. They let the app show a full review,
the queue and the drafts without an API key, and they are labeled "sample" everywhere. Each runs
through the real carebridge.intake.quality_control, so the gates, the checks and the route are
computed by the same code a live review uses.
"""

import time

from carebridge import intake, rules

from .packets import PACKETS

ES_NA = "No aplica a este paciente según el paquete."
EN_NA = "Does not apply to this patient based on the packet."


def _pages(pid, rotations):
    out = {}
    for i, p in enumerate(PACKETS[pid], 1):
        out[i] = {"page": i, "page_type": p["type"], "rotation": rotations.get(i, 0), "mostly_redacted": False,
                  "earlier_stay": False, "language": "en", "possible_unredacted_identifier": False,
                  "duplicate_of": None, "blank": False}
    return out


def _build(pid, facts, rule_map, diagnoses, checklist, conflicts, questions, extra, rotations=None):
    """facts: {key: (page, topic, statement, statement_es, quote)}; rule_map: {rule_id: (status, [keys], en, es)}."""
    keys = list(facts)
    ids = {k: f"F{i}" for i, k in enumerate(keys, 1)}
    fact_list = [{"id": ids[k], "page": v[0], "topic": v[1], "statement": v[2], "statement_es": v[3],
                  "quote": v[4], "verify": "found"} for k, v in facts.items()]
    rule_list = []
    for rid in rules.assessed_rule_ids():
        st, fk, en, es = rule_map.get(rid, ("not_applicable", [], EN_NA, ES_NA))
        rule_list.append({"rule_id": rid, "status": st, "fact_ids": [ids[k] for k in fk],
                          "explanation": en, "explanation_es": es})
    assessment = {
        **extra,
        "rules": rule_list,
        "diagnoses": [{"rule_id": d[0], "fact_ids": [ids[k] for k in d[1]], "explanation": d[2],
                       "explanation_es": d[3]} for d in diagnoses],
        "checklist": [{"doc_id": c[0], "status": c[1], "pages": c[2]} for c in checklist],
        "conflicts": [{"topic": c[0], "description": c[1], "description_es": c[2],
                       "fact_ids": [ids[k] for k in c[3]]} for c in conflicts],
        "questions": [{"en": q[0], "es": q[1], "rule_ids": q[2]} for q in questions],
    }
    sorted_pages = _pages(pid, rotations or {})
    summaries = {i: f"{p['type'].replace('_', ' ')}" for i, p in enumerate(PACKETS[pid], 1)}
    return fact_list, assessment, sorted_pages, summaries


# ---------------------------------------------------------------- D01
# Form says independent; PT and nursing say otherwise.
D01_FACTS = {
    "unhoused": (4, "housing", "Patient is experiencing homelessness and lives in his car.",
                 "El paciente no tiene vivienda y vive en su carro.",
                 "58 y/o male experiencing homelessness, lives in his car."),
    "form_walk": (2, "mobility", "The referral form checks that he walks 100 ft and transfers independently.",
                  "El formulario marca que camina 100 pies y se traslada sin ayuda.",
                  "[X] Ambulates 100 ft independently and transfers independently"),
    "form_adl": (2, "adl", "The referral form checks that he manages ADLs.",
                 "El formulario marca que maneja sus actividades diarias.", "[X] Able to manage ADLs"),
    "dx": (4, "diagnosis", "Uncomplicated cellulitis of the left lower leg.",
           "Celulitis sin complicaciones en la pierna izquierda.",
           "Assessment: cellulitis of left lower leg, uncomplicated"),
    "oral_abx": (4, "medications", "Switched to oral cephalexin.", "Cambió a cefalexina oral.",
                 "Plan: transition to oral cephalexin 500 mg four times daily"),
    "aox4": (6, "cognition", "Nursing documents alert and oriented x4.", "Enfermería documenta alerta y orientado x4.",
             "Alert and oriented x4"),
    "no_si": (4, "mental_health", "No history of suicidal ideation and no hallucinations.",
              "Sin antecedentes de ideación suicida ni alucinaciones.",
              "No history of suicidal ideation. No hallucinations."),
    "calm": (4, "behavior", "Calm and cooperative.", "Tranquilo y cooperativo.",
             "Psych: alert and oriented x4, calm and cooperative"),
    "no_etoh": (4, "substance_use", "Denies alcohol and drug use.", "Niega uso de alcohol y drogas.",
                "Social: denies alcohol use. No drug use."),
    "pt_40ft": (5, "mobility", "PT: walked only 40 ft, with a front-wheeled walker.",
                "Fisioterapia: caminó solo 40 pies con andadera de ruedas.",
                "Gait: ambulated 40 ft with front-wheeled walker"),
    "pt_assist": (5, "mobility", "PT: needs minimal assistance from one person to transfer.",
                  "Fisioterapia: necesita ayuda mínima de una persona para trasladarse.",
                  "Transfers: min assist x1 for transfers sit to stand"),
    "shower": (6, "adl", "Nursing: needs help showering.", "Enfermería: necesita ayuda para bañarse.",
               "Patient requires assistance with showering"),
    "toilet": (6, "adl", "Toilets independently with a bedside urinal.",
               "Va al baño sin ayuda con orinal junto a la cama.",
               "Toileting: independent with urinal at bedside"),
    "self_meds": (6, "medications", "Took his oral antibiotic without prompting.",
                  "Tomó su antibiótico oral sin que se lo recordaran.", "Took oral antibiotic without prompting"),
    "self_meds2": (8, "medications", "Discharge list says he self-administers all medications.",
                   "La lista de alta dice que se administra todos sus medicamentos.",
                   "Patient to self-administer all medications"),
    "vitals": (6, "vitals", "One set of vitals, within normal limits.", "Un juego de signos vitales, normales.",
               "Vitals: T 98.4  HR 82  BP 128/76  RR 16  SpO2 97% RA"),
    "mrsa": (7, "infection", "MRSA nares PCR negative.", "PCR nasal de MRSA negativo.", "MRSA nares PCR: NEGATIVE"),
    "covid": (7, "infection", "COVID PCR negative; collection date is redacted.",
              "PCR de COVID negativo; la fecha de toma está tachada.", "SARS-CoV-2 PCR: NEGATIVE"),
}

D01_RULES = {
    "GEN-1": ("met", ["unhoused"], "Experiencing homelessness and admitted for an infection.",
              "Sin vivienda e internado por una infección."),
    "GEN-2": ("cant_tell", [], "Not stated.", "No se indica."),
    "GEN-3": ("cant_tell", [], "Not stated.", "No se indica."),
    "ADL-1": ("not_met", ["shower"], "Nursing says he needs help showering, so not all ADLs are independent.",
              "Enfermería dice que necesita ayuda para bañarse; no todas sus actividades son independientes."),
    "ADL-2": ("not_met", ["shower"], "Needs assistance with showering.", "Necesita ayuda para bañarse."),
    "ADL-3": ("met", ["toilet"], "Toilets independently.", "Va al baño sin ayuda."),
    "MOB-1": ("cant_tell", ["pt_40ft"], "Uses a walker; independent use is not shown.",
              "Usa andadera; no se muestra que la use sin ayuda."),
    "MOB-2": ("met", ["pt_40ft"], "PT evaluation is in the packet.", "La evaluación de fisioterapia está en el paquete."),
    "MOB-3": ("not_met", ["pt_40ft", "pt_assist"], "PT: 40 ft with walker and min assist for transfers, short of 100 ft at modified independence.",
              "Fisioterapia: 40 pies con andadera y ayuda mínima; no llega a 100 pies con independencia modificada."),
    "MOB-4": ("not_applicable", [], "Not wheelchair-dependent.", "No depende de silla de ruedas."),
    "MH-1": ("met", ["calm"], "Calm and cooperative.", "Tranquilo y cooperativo."),
    "MH-2": ("met", ["no_si"], "No suicidal ideation documented.", "Sin ideación suicida documentada."),
    "MH-3": ("met", ["no_si"], "No hallucinations.", "Sin alucinaciones."),
    "MH-4": ("not_applicable", ["no_etoh"], "Denies alcohol use.", "Niega uso de alcohol."),
    "MH-5": ("cant_tell", [], "Conservatorship or FSP history is not mentioned.", "No se menciona tutela ni FSP."),
    "COG-1": ("met", ["self_meds", "self_meds2"], "Takes his own medications.", "Toma sus propios medicamentos."),
    "COG-2": ("met", ["aox4"], "AOx4.", "Orientado x4."),
    "OTH-1": ("met", ["calm"], "Calm and cooperative.", "Tranquilo y cooperativo."),
    "OTH-2": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "OTH-4": ("met", ["mrsa"], "No isolation; MRSA negative.", "Sin aislamiento; MRSA negativo."),
    "INF-1": ("met", ["mrsa"], "MRSA swab negative.", "Prueba de MRSA negativa."),
    "INF-2": ("met", ["covid"], "COVID negative, but the date is redacted.", "COVID negativo, pero la fecha está tachada."),
    "ID-1": ("not_met", ["vitals"], "Only one set of vitals, not the last 5.", "Solo un juego de signos vitales, no los últimos 5."),
    "ID-2": ("met", ["self_meds"], "Takes oral antibiotics on his own.", "Toma antibióticos orales por su cuenta."),
    "ID-3": ("not_applicable", ["oral_abx"], "On oral antibiotics, not IV.", "Antibióticos orales, no intravenosos."),
    "FORM-M1": ("met", ["unhoused"], "Unhoused.", "Sin vivienda."),
    "FORM-M2": ("met", ["calm"], "Stable.", "Estable."),
    "FORM-M3": ("met", ["aox4"], "AOx4.", "Orientado x4."),
    "FORM-M4": ("not_met", ["form_adl", "shower"], "Form says yes; nursing says he needs help showering.",
                "El formulario dice que sí; enfermería dice que necesita ayuda para bañarse."),
    "FORM-M5": ("met", ["self_meds2"], "Self-administers.", "Se administra sus medicamentos."),
    "FORM-M6": ("not_met", ["form_walk", "pt_40ft"], "Form says 100 ft; PT says 40 ft with walker.",
                "El formulario dice 100 pies; fisioterapia dice 40 pies con andadera."),
    "FORM-X1": ("met", ["aox4"], "No cognitive impairment noted.", "Sin deterioro cognitivo."),
    "FORM-X2": ("not_met", ["shower"], "Needs help with bathing.", "Necesita ayuda para bañarse."),
    "FORM-X3": ("not_met", ["pt_assist"], "Needs assist to transfer.", "Necesita ayuda para trasladarse."),
    "FORM-X4": ("met", ["mrsa"], "MRSA negative.", "MRSA negativo."),
    "FORM-X5": ("not_applicable", ["no_etoh"], "No substance use.", "Sin uso de sustancias."),
    "FORM-X6": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "FORM-X7": ("met", ["calm"], "Calm and cooperative.", "Tranquilo y cooperativo."),
}


def d01():
    return _build(
        "D01", D01_FACTS, D01_RULES,
        diagnoses=[("INT-E1", ["dx", "oral_abx"], "Uncomplicated cellulitis on oral antibiotics.",
                    "Celulitis sin complicaciones con antibióticos orales.")],
        checklist=[("DOC-1", "present", [2]), ("DOC-2", "present", [3]), ("DOC-3", "missing", []),
                   ("DOC-4", "present", [4]), ("DOC-5", "cant_tell", []), ("DOC-6", "present", [6]),
                   ("DOC-7", "present", [8]), ("DOC-8", "present", [5, 6]), ("DOC-9", "cant_tell", []),
                   ("DOC-10", "missing", [])],
        conflicts=[("mobility", "The referral form says he walks 100 ft and transfers independently. The PT evaluation says 40 ft with a walker and min assist to transfer.",
                    "El formulario dice que camina 100 pies y se traslada sin ayuda. Fisioterapia dice 40 pies con andadera y ayuda mínima.",
                    ["form_walk", "pt_40ft", "pt_assist"]),
                   ("adl", "The form says he manages ADLs. Nursing says he needs help showering.",
                    "El formulario dice que maneja sus actividades diarias. Enfermería dice que necesita ayuda para bañarse.",
                    ["form_adl", "shower"])],
        questions=[("Has PT re-evaluated walking distance and transfers since the 40 ft note?",
                    "¿Fisioterapia volvió a evaluar la distancia y los traslados después de la nota de 40 pies?", ["MOB-3", "FORM-M6"]),
                   ("Can he shower on his own with a shower chair?", "¿Puede bañarse solo con silla de baño?", ["ADL-2"]),
                   ("Please send the last 5 sets of vitals and the CalOptima authorization.",
                    "Por favor envíe los últimos 5 juegos de signos vitales y la autorización de CalOptima.", ["ID-1", "DOC-3"])],
        extra={"reason_for_referral": "Uncomplicated left leg cellulitis, finishing oral antibiotics.",
               "reason_for_referral_es": "Celulitis de la pierna izquierda sin complicaciones; termina antibióticos orales.",
               "wheelchair_dependent": "no", "preferred_language": "English",
               "summary": "58-year-old man living in his car, treated for uncomplicated cellulitis and now on oral antibiotics. The referral form says he is independent, but the PT evaluation (page 5) shows 40 ft with a walker and min assist to transfer, and nursing (page 6) says he needs help showering. Self-care is the deciding question. MRSA and COVID are negative; the COVID date is redacted.",
               "summary_es": "Hombre de 58 años que vive en su carro, tratado por celulitis sin complicaciones y ahora con antibióticos orales. El formulario dice que es independiente, pero fisioterapia (página 5) indica 40 pies con andadera y ayuda mínima, y enfermería (página 6) dice que necesita ayuda para bañarse. El autocuidado es la pregunta decisiva. MRSA y COVID negativos; la fecha de COVID está tachada."},
        rotations={4: 270, 5: 180})


# ---------------------------------------------------------------- D02
D02_FACTS = {
    "unhoused": (5, "housing", "Unhoused.", "Sin vivienda.", "47 y/o female, unhoused, presented with acute appendicitis"),
    "surgery": (5, "diagnosis", "Uncomplicated laparoscopic appendectomy.", "Apendicectomía laparoscópica sin complicaciones.",
                "Underwent laparoscopic appendectomy, uncomplicated"),
    "dm": (5, "diabetes", "Type 2 diabetes on insulin glargine.", "Diabetes tipo 2 con insulina glargina.",
           "PMH: type 2 diabetes on insulin glargine"),
    "psych": (5, "mental_health", "AOx4, no suicidal ideation, no hallucinations, mood stable.",
              "Orientada x4, sin ideación suicida, sin alucinaciones, ánimo estable.",
              "Psych: AOx4, no SI, no hallucinations, mood stable"),
    "conserv": (5, "legal", "No conservatorship and no history of aggression.", "Sin tutela y sin antecedentes de agresión.",
                "No conservatorship. No history of aggressive behavior."),
    "no_etoh": (5, "substance_use", "No alcohol or drug use.", "Sin uso de alcohol ni drogas.", "No alcohol or drug use reported"),
    "walk": (6, "mobility", "Walked 300 ft independently without a device.", "Caminó 300 pies sin ayuda y sin aparato.",
             "Ambulated 300 ft independently without device"),
    "transfer": (6, "mobility", "Transfers independently.", "Se traslada sin ayuda.", "Transfers independent"),
    "shower": (6, "adl", "Showers independently with a shower chair.", "Se baña sola con silla de baño.",
               "Showers independently using shower chair"),
    "toilet": (6, "adl", "Toilets independently.", "Va al baño sin ayuda.", "Toileting independent"),
    "insulin": (7, "diabetes", "Self-administers insulin with correct technique.", "Se aplica la insulina con técnica correcta.",
                "Patient self-administers insulin glargine with correct technique"),
    "glucometer": (7, "diabetes", "Uses the glucometer independently.", "Usa el glucómetro sin ayuda.",
                   "Demonstrated glucometer use independently"),
    "glucose5": (7, "diabetes", "Five glucose readings, trending down: 248 to 138.", "Cinco glucosas en descenso: 248 a 138.",
                 "Fingerstick glucose: 248, 211, 176, 152, 138"),
    "incision": (7, "wound", "Incision clean, dry and intact.", "Incisión limpia, seca e intacta.",
                 "Incision clean, dry and intact, 3 port sites"),
    "vitals": (7, "vitals", "One set of vitals, normal.", "Un juego de signos vitales, normales.",
               "Vitals: T 98.6  HR 76  BP 122/78  SpO2 98% RA"),
    "hh": (9, "home_health", "Home health referral for wound check and diabetes follow-up.",
           "Referencia a salud en el hogar para revisar la herida y seguimiento de diabetes.",
           "Home health referral: wound check and diabetes follow-up"),
    "hh_pending": (9, "home_health", "Home health start of care is still pending.", "El inicio de salud en el hogar está pendiente.",
                   "start of care pending"),
    "swabs": (9, "infection", "MRSA and COVID negative.", "MRSA y COVID negativos.",
              "MRSA screen: negative     COVID-19 PCR: negative"),
    "followup": (9, "follow_up", "Surgery clinic follow-up in 7 to 10 days.", "Seguimiento en clínica de cirugía en 7 a 10 días.",
                 "Follow up with surgery clinic in 7-10 days"),
    "lang": (2, "language", "Preferred language is Spanish.", "Idioma preferido: español.", "Preferred language: Spanish"),
}

D02_RULES = {
    "GEN-1": ("met", ["unhoused", "surgery"], "Unhoused and recovering from surgery.", "Sin vivienda y recuperándose de cirugía."),
    "GEN-2": ("cant_tell", [], "Not stated.", "No se indica."),
    "GEN-3": ("cant_tell", [], "Not stated.", "No se indica."),
    "ADL-1": ("met", ["shower", "toilet", "transfer"], "Independent with ADLs per therapy.", "Independiente en actividades diarias según terapia."),
    "ADL-2": ("met", ["shower"], "Showers independently with a chair.", "Se baña sola con silla."),
    "ADL-3": ("met", ["toilet"], "Toilets independently.", "Va al baño sin ayuda."),
    "MOB-1": ("not_applicable", ["walk"], "No device used.", "No usa aparato."),
    "MOB-2": ("met", ["walk"], "Therapy note in the packet.", "Nota de terapia en el paquete."),
    "MOB-3": ("met", ["walk"], "Walked 300 ft independently.", "Caminó 300 pies sin ayuda."),
    "MOB-4": ("not_applicable", [], "Not wheelchair-dependent.", "No depende de silla de ruedas."),
    "MH-1": ("met", ["psych"], "Mood stable.", "Ánimo estable."),
    "MH-2": ("met", ["psych"], "No SI.", "Sin ideación suicida."),
    "MH-3": ("met", ["psych"], "No hallucinations.", "Sin alucinaciones."),
    "MH-4": ("not_applicable", ["no_etoh"], "No alcohol use.", "Sin uso de alcohol."),
    "MH-5": ("met", ["conserv"], "No conservatorship.", "Sin tutela."),
    "COG-1": ("met", ["insulin"], "Self-administers insulin.", "Se aplica la insulina."),
    "COG-2": ("met", ["psych"], "AOx4.", "Orientada x4."),
    "OTH-1": ("met", ["conserv"], "No history of aggression.", "Sin antecedentes de agresión."),
    "OTH-2": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "OTH-4": ("met", ["swabs"], "No isolation; swabs negative.", "Sin aislamiento; pruebas negativas."),
    "INF-1": ("met", ["swabs"], "MRSA negative.", "MRSA negativo."),
    "INF-2": ("met", ["swabs"], "COVID negative; date not shown.", "COVID negativo; sin fecha."),
    "DM-1": ("met", ["glucose5"], "Five readings, improving.", "Cinco lecturas, mejorando."),
    "DM-2": ("not_applicable", [], "Inpatient, not from the ED.", "Hospitalizada, no viene de urgencias."),
    "DM-3": ("met", ["dm"], "Insulin is an existing regimen, but dates are redacted.", "La insulina es un tratamiento previo, pero las fechas están tachadas."),
    "DM-4": ("not_applicable", [], "Inpatient, not from the ED.", "Hospitalizada, no viene de urgencias."),
    "DM-5": ("met", ["glucometer"], "Uses glucometer independently.", "Usa el glucómetro sola."),
    "DM-6": ("met", ["insulin"], "Correct insulin technique.", "Técnica correcta de insulina."),
    "DM-Q1": ("met", ["insulin"], "Insulin glargine.", "Insulina glargina."),
    "DM-Q2": ("cant_tell", [], "Oral medications are on the list on page 8.", "Medicamentos orales en la página 8."),
    "DM-Q3": ("cant_tell", [], "No A1C in the packet.", "No hay A1C en el paquete."),
    "ID-1": ("not_applicable", [], "Not an infection referral.", "No es una referencia por infección."),
    "OTH-3": ("not_applicable", [], "No IV access.", "Sin acceso intravenoso."),
    "FORM-M1": ("met", ["unhoused"], "Unhoused.", "Sin vivienda."),
    "FORM-M2": ("met", ["psych"], "Stable.", "Estable."),
    "FORM-M3": ("met", ["psych"], "AOx4.", "Orientada x4."),
    "FORM-M4": ("met", ["shower", "toilet"], "Manages ADLs.", "Maneja sus actividades diarias."),
    "FORM-M5": ("met", ["insulin"], "Self-administers.", "Se administra sus medicamentos."),
    "FORM-M6": ("met", ["walk", "transfer"], "300 ft, transfers independent.", "300 pies, se traslada sola."),
    "FORM-X1": ("met", ["psych"], "No cognitive impairment.", "Sin deterioro cognitivo."),
    "FORM-X2": ("met", ["shower"], "Performs ADLs.", "Realiza sus actividades diarias."),
    "FORM-X3": ("met", ["walk"], "Walks and transfers independently.", "Camina y se traslada sola."),
    "FORM-X4": ("met", ["swabs"], "No active MRSA, TB or C. diff noted.", "Sin MRSA, TB ni C. diff activos."),
    "FORM-X5": ("not_applicable", ["no_etoh"], "No substance use.", "Sin uso de sustancias."),
    "FORM-X6": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "FORM-X7": ("met", ["conserv"], "No aggression.", "Sin agresión."),
}


def d02():
    return _build(
        "D02", D02_FACTS, D02_RULES,
        diagnoses=[("GI-E1", ["surgery"], "Recovering from abdominal surgery.", "Recuperándose de cirugía abdominal."),
                   ("END-E1", ["glucose5"], "Diabetes stabilizing on 5 readings.", "Diabetes estabilizándose en 5 lecturas."),
                   ("INT-E2", ["hh", "hh_pending"], "Wound check by home health; start of care still pending.",
                    "Revisión de herida por salud en el hogar; inicio pendiente.")],
        checklist=[("DOC-1", "present", [2]), ("DOC-2", "present", [4]), ("DOC-3", "present", [3]),
                   ("DOC-4", "present", [5]), ("DOC-5", "cant_tell", []), ("DOC-6", "present", [7]),
                   ("DOC-7", "present", [8]), ("DOC-8", "present", [6, 7]), ("DOC-9", "cant_tell", []),
                   ("DOC-10", "missing", [])],
        conflicts=[],
        questions=[("Has the home health agency confirmed a start-of-care date for the wound check?",
                    "¿La agencia de salud en el hogar confirmó la fecha de inicio para revisar la herida?", ["INT-E2"]),
                   ("Will she leave with a 30-day supply of insulin, metformin and supplies?",
                    "¿Saldrá con 30 días de insulina, metformina y suministros?", ["DOC-10"])],
        extra={"reason_for_referral": "Recovering from laparoscopic appendectomy; insulin-dependent diabetes.",
               "reason_for_referral_es": "Recuperación de apendicectomía laparoscópica; diabetes con insulina.",
               "wheelchair_dependent": "no", "preferred_language": "Spanish",
               "summary": "47-year-old woman, unhoused, recovering from an uncomplicated laparoscopic appendectomy. Therapy shows she walks 300 ft, showers and toilets on her own, and she gives her own insulin. Glucose is coming down over five readings. Open items: home health for the wound check is ordered but start of care is pending (INT-E2), and the 30-day medication supply is not mentioned. Preferred language is Spanish.",
               "summary_es": "Mujer de 47 años, sin vivienda, recuperándose de una apendicectomía laparoscópica sin complicaciones. Terapia muestra que camina 300 pies, se baña y va al baño sola, y se aplica su insulina. La glucosa baja en cinco lecturas. Pendientes: salud en el hogar para la herida está ordenada pero el inicio está pendiente (INT-E2), y no se menciona el suministro de 30 días. Idioma preferido: español."})


# ---------------------------------------------------------------- D03
D03_FACTS = {
    "outdoors": (3, "housing", "Sleeping outdoors.", "Duerme a la intemperie.",
                 "36 y/o male, sleeping outdoors, admitted with community-acquired pneumonia"),
    "cxr": (3, "imaging", "Right lower lobe infiltrate on chest x-ray.", "Infiltrado en lóbulo inferior derecho en radiografía.",
            "Chest x-ray: right lower lobe infiltrate"),
    "oral_abx": (3, "medications", "Now on oral amoxicillin-clavulanate.", "Ahora con amoxicilina-clavulanato oral.",
                 "Treated with IV ceftriaxone, now on oral amoxicillin-clavulanate"),
    "mdd": (3, "mental_health", "History of major depressive disorder.", "Antecedente de trastorno depresivo mayor.",
            "History of major depressive disorder"),
    "walk": (3, "mobility", "Walking independently in the hallway (distance not stated).",
             "Camina sin ayuda en el pasillo (sin distancia indicada).", "Ambulating independently in hallway"),
    "si": (4, "mental_health", "Psychiatry: passive suicidal ideation, no plan.", "Psiquiatría: ideación suicida pasiva, sin plan.",
           "Patient endorses passive suicidal ideation, no plan"),
    "no_ah": (4, "mental_health", "No hallucinations.", "Sin alucinaciones.", "Denies auditory or visual hallucinations"),
    "reeval": (4, "mental_health", "Psychiatry asks for re-evaluation before discharge.",
               "Psiquiatría pide reevaluar antes del alta.", "Re-evaluate prior to discharge"),
    "denies_si": (5, "mental_health", "Progress note: denies SI today.", "Nota de evolución: niega ideación suicida hoy.",
                  "Patient denies SI today, mood improved"),
    "adl": (5, "adl", "Independent with ADLs per nursing.", "Independiente en actividades diarias según enfermería.",
            "Independent with ADLs per nursing"),
    "self_meds": (6, "medications", "Takes medications independently.", "Toma sus medicamentos sin ayuda.",
                  "Takes medications independently"),
    "aox4": (6, "cognition", "AOx4.", "Orientado x4.", "Alert and oriented x4"),
    "spo2": (6, "vitals", "SpO2 95% on room air.", "SpO2 95% al aire ambiente.",
             "Vitals: T 98.9  HR 88  BP 118/72  RR 18  SpO2 95% RA"),
    "afebrile": (5, "respiratory", "Afebrile, breathing comfortably on room air.", "Sin fiebre, respira bien al aire ambiente.",
                 "Afebrile, breathing comfortably on room air"),
}

D03_RULES = {
    "GEN-1": ("met", ["outdoors"], "Sleeping outdoors, admitted for pneumonia.", "Duerme afuera, internado por neumonía."),
    "GEN-2": ("cant_tell", [], "Not stated.", "No se indica."),
    "GEN-3": ("cant_tell", [], "Not stated.", "No se indica."),
    "ADL-1": ("met", ["adl"], "Independent with ADLs per nursing.", "Independiente según enfermería."),
    "ADL-2": ("cant_tell", [], "Bathing is not described.", "No se describe el baño."),
    "ADL-3": ("cant_tell", [], "Toileting is not described.", "No se describe el uso del baño."),
    "MOB-1": ("not_applicable", [], "No device mentioned.", "No se menciona aparato."),
    "MOB-2": ("not_met", [], "No PT/OT notes in the packet.", "No hay notas de fisioterapia en el paquete."),
    "MOB-3": ("cant_tell", ["walk"], "Walks in the hallway; 100 ft is not documented.", "Camina en el pasillo; no se documentan 100 pies."),
    "MOB-4": ("not_applicable", [], "Not wheelchair-dependent.", "No depende de silla de ruedas."),
    "MH-1": ("cant_tell", ["mdd", "denies_si"], "Mood improved, but psychiatry asked for re-evaluation.", "Ánimo mejor, pero psiquiatría pidió reevaluar."),
    "MH-2": ("cant_tell", ["si", "denies_si"], "Psychiatry documents passive SI; a later note says he denies SI. Conflict.",
             "Psiquiatría documenta ideación pasiva; una nota posterior dice que la niega. Conflicto."),
    "MH-3": ("met", ["no_ah"], "No hallucinations.", "Sin alucinaciones."),
    "MH-4": ("cant_tell", [], "Alcohol use not mentioned.", "No se menciona alcohol."),
    "MH-5": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "COG-1": ("met", ["self_meds"], "Takes medications independently.", "Toma sus medicamentos solo."),
    "COG-2": ("met", ["aox4"], "AOx4.", "Orientado x4."),
    "OTH-1": ("cant_tell", [], "Behavior toward others not described.", "No se describe su conducta con otros."),
    "OTH-2": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "OTH-4": ("cant_tell", [], "Isolation status not stated.", "No se indica aislamiento."),
    "INF-1": ("not_met", [], "No MRSA swab in the packet.", "No hay prueba de MRSA."),
    "INF-2": ("not_met", [], "No COVID swab in the packet.", "No hay prueba de COVID."),
    "ID-1": ("not_met", ["spo2"], "Only one set of vitals.", "Solo un juego de signos vitales."),
    "ID-2": ("met", ["oral_abx", "self_meds"], "On oral antibiotics, takes meds independently.", "Antibiótico oral, toma sus medicamentos solo."),
    "ID-3": ("not_applicable", ["oral_abx"], "IV antibiotics finished.", "Terminó antibióticos intravenosos."),
    "RESP-1": ("met", ["cxr"], "Chest x-ray result reported.", "Resultado de radiografía reportado."),
    "RESP-2": ("cant_tell", ["spo2"], "One SpO2 of 95%; baseline and 5 sets not shown.", "Una SpO2 de 95%; sin línea base ni 5 juegos."),
    "RESP-3": ("not_applicable", ["afebrile"], "On room air.", "Al aire ambiente."),
    "RESP-4": ("cant_tell", [], "No respiratory therapy notes.", "Sin notas de terapia respiratoria."),
    "FORM-M1": ("met", ["outdoors"], "Unhoused.", "Sin vivienda."),
    "FORM-M2": ("cant_tell", ["si", "denies_si"], "Psychiatric stability unclear.", "Estabilidad psiquiátrica no clara."),
    "FORM-M3": ("met", ["aox4"], "AOx4.", "Orientado x4."),
    "FORM-M4": ("met", ["adl"], "Independent with ADLs.", "Independiente."),
    "FORM-M5": ("met", ["self_meds"], "Self-administers.", "Se administra sus medicamentos."),
    "FORM-M6": ("cant_tell", ["walk"], "Distance not documented.", "Distancia no documentada."),
    "FORM-X1": ("met", ["aox4"], "No cognitive impairment.", "Sin deterioro cognitivo."),
    "FORM-X2": ("met", ["adl"], "Performs ADLs.", "Realiza actividades diarias."),
    "FORM-X3": ("cant_tell", ["walk"], "Not documented.", "No documentado."),
    "FORM-X4": ("cant_tell", [], "No MRSA/TB/C. diff results.", "Sin resultados de MRSA/TB/C. diff."),
    "FORM-X5": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "FORM-X6": ("cant_tell", [], "Not mentioned.", "No se menciona."),
    "FORM-X7": ("cant_tell", [], "Not described.", "No se describe."),
}


def d03():
    return _build(
        "D03", D03_FACTS, D03_RULES,
        diagnoses=[("RSP-E1", ["cxr", "oral_abx"], "Pneumonia on oral antibiotics.", "Neumonía con antibióticos orales.")],
        checklist=[("DOC-1", "missing", []), ("DOC-2", "present", [2]), ("DOC-3", "missing", []),
                   ("DOC-4", "present", [3]), ("DOC-5", "present", [5]), ("DOC-6", "present", [6]),
                   ("DOC-7", "present", [7]), ("DOC-8", "present", [6]), ("DOC-9", "cant_tell", []),
                   ("DOC-10", "missing", [])],
        conflicts=[("mental_health", "Psychiatry consult documents passive suicidal ideation and asks for re-evaluation before discharge. A later progress note says he denies SI. No re-evaluation is in the packet.",
                    "La consulta de psiquiatría documenta ideación suicida pasiva y pide reevaluar antes del alta. Una nota posterior dice que la niega. No hay reevaluación en el paquete.",
                    ["si", "reeval", "denies_si"])],
        questions=[("Has psychiatry re-evaluated him before discharge, as the consult asked? Please send that note.",
                    "¿Psiquiatría lo reevaluó antes del alta, como pidió la consulta? Por favor envíe esa nota.", ["MH-2", "MH-1"]),
                   ("Please send the IHH referral form, PT/OT notes, MRSA and COVID swab results, and the last 5 sets of vitals.",
                    "Por favor envíe el formulario de referencia, notas de fisioterapia, resultados de MRSA y COVID y los últimos 5 signos vitales.",
                    ["DOC-1", "MOB-2", "INF-1", "INF-2", "ID-1"])],
        extra={"reason_for_referral": "Community-acquired pneumonia, finishing oral antibiotics.",
               "reason_for_referral_es": "Neumonía adquirida en la comunidad; termina antibióticos orales.",
               "wheelchair_dependent": "no", "preferred_language": "English",
               "summary": "36-year-old man sleeping outdoors, treated for pneumonia and now on oral antibiotics. There is no IHH referral form. Psychiatry (page 4) documents passive suicidal ideation and asks for re-evaluation before discharge; a later progress note (page 5) says he denies SI. The behavioral gate can't be settled from this packet and needs the clinical line. PT/OT notes and MRSA/COVID swabs are missing.",
               "summary_es": "Hombre de 36 años que duerme afuera, tratado por neumonía y ahora con antibióticos orales. No hay formulario de referencia. Psiquiatría (página 4) documenta ideación suicida pasiva y pide reevaluar antes del alta; una nota posterior (página 5) dice que la niega. La conducta no se puede determinar con este paquete y requiere revisión clínica. Faltan notas de fisioterapia y pruebas de MRSA/COVID."})


BUILDERS = {"D01": d01, "D02": d02, "D03": d03}
EXPECTED = {"D01": "likely_no", "D02": "needs_info", "D03": "clinical_check"}


def sample_reports() -> dict:
    out = {}
    now = time.time()
    for pid, fn in BUILDERS.items():
        facts, assessment, sorted_pages, summaries = fn()
        report = intake.quality_control(assessment, facts, sorted_pages, summaries)
        report.update(id=f"sample-{pid}", packet=f"{pid}.pdf", received_at=now, reviewed_at=now,
                      model="sample (hand-written)", fast_model="sample (hand-written)", sample=True)
        report["flags"]["phi_pages"] = []
        out[pid] = report
    return out


def check():
    """Every quote must be drawn on its page, and each route must match the scenario."""
    import re

    redact = re.compile(r"\[\[.*?\]\]")
    for pid, fn in BUILDERS.items():
        facts = fn()[0]
        for f in facts:
            page = PACKETS[pid][f["page"] - 1]
            lines = [redact.sub("", ln.lstrip("~").strip()) for ln in page["lines"]]
            assert any(f["quote"] in ln for ln in lines), (pid, f["id"], f["quote"])
    reports = sample_reports()
    for pid, rep in reports.items():
        assert rep["recommendation"]["code"] == EXPECTED[pid], (pid, rep["recommendation"])
    return reports


if __name__ == "__main__":
    for pid, rep in check().items():
        r = rep["recommendation"]
        print(pid, r["code"], "gates:", {g: v["status"] for g, v in rep["gates"].items()},
              "blockers:", r["blockers"], "missing:", r["missing_docs"], "downgrades:",
              [(d["rule_id"], d["reason"]) for d in rep["qc"]["downgrades"]])
