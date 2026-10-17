"""Three invented referral packets for demos and tests. No real patient, clinician or hospital.

Each packet is a list of pages. A page is a dict:
  type    page type label (matches carebridge.intake.PAGE_TYPES)
  rotate  0, 90 or 180: how the "fax" arrives (degrees the page is turned clockwise on the scanner)
  lines   text lines. "[[xxxx]]" draws a black redaction box as wide as the text inside it.
          A line starting with "~" is drawn in a handwriting-style font.

build(out_dir) renders each packet to an image-only PDF (no text layer), like a real e-fax.
Run: python packets.py OUTDIR
"""

import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1700, 2200
MARGIN = 120
LINE_H = 46

FORM_HEADER = "ILLUMINATION HEALTH + HOME  RECUPERATIVE CARE REFERRAL FORM  (RC0725-SH)"
FAX = "FAX  Harbor View Medical Center (invented)  ->  Recuperative Care Intake"


def _fax_cover(hospital, pages):
    return {"type": "fax_cover", "rotate": 0, "lines": [
        "FAX TRANSMITTAL", "",
        f"From: {hospital}",
        "To: Recuperative Care Intake",
        "Date: [[00/00/0000]]   Time: 15:52",
        f"Pages (including cover): {pages}",
        "Re: Recuperative care referral",
        "Contact: [[Case Manager Name]]  555-0142",
        "",
        "CONFIDENTIAL: This fax contains protected health information.",
    ]}


D01 = [
    _fax_cover("Harbor View Medical Center (invented)", 8),
    {"type": "ihh_referral_form", "rotate": 0, "lines": [
        FORM_HEADER, "",
        "Patient name: [[Xxxxxxx Xxxxxxxxx]]   DOB: [[00/00/0000]]   Age: 58",
        "Referring facility: Harbor View Medical Center (invented)",
        "Case manager: [[Xxxxx Xxxxxx]]   Phone: [[555-0000]]",
        "Preferred language: English",
        "Housing status: [X] Unhoused   [ ] At risk   [ ] Inadequate environment",
        "Primary diagnosis: Cellulitis of left lower leg",
        "",
        "SCREENING (all must be met):",
        "[X] Medically and psychiatrically stable",
        "[X] Patient is AAOx4",
        "[X] Able to manage ADLs",
        "[X] Able to self-administer medications",
        "[X] Ambulates 100 ft independently and transfers independently",
        "",
        "~ Pt is independent, ready for d/c today",
        "",
        "Staff use only:  Reviewed by ________  Approved ________",
    ]},
    {"type": "face_sheet", "rotate": 0, "lines": [
        "FACE SHEET", "",
        "Name: [[Xxxxxxx Xxxxxxxxx]]",
        "MRN: [[000000000]]     Account: [[0000000000]]",
        "DOB: [[00/00/0000]]    Sex: M",
        "Address: [[Xxxx Xxxxxxx Xx]]",
        "Payer: Medi-Cal managed care",
        "Admit date: [[00/00/0000]]",
        "Attending: [[Xx. Xxxxxx Xxxx]]",
    ]},
    {"type": "history_physical", "rotate": 90, "lines": [
        "HISTORY AND PHYSICAL", "",
        "Chief complaint: left leg redness and swelling x 5 days",
        "HPI: 58 y/o male experiencing homelessness, lives in his car.",
        "Presented with erythema of the left lower leg, no abscess on ultrasound.",
        "Assessment: cellulitis of left lower leg, uncomplicated",
        "Plan: transition to oral cephalexin 500 mg four times daily",
        "Psych: alert and oriented x4, calm and cooperative",
        "No history of suicidal ideation. No hallucinations.",
        "Social: denies alcohol use. No drug use.",
    ]},
    {"type": "pt_ot", "rotate": 180, "lines": [
        "PHYSICAL THERAPY EVALUATION", "",
        "Date: [[00/00/0000]]   Therapist: [[Xxxxx Xxxxx, PT]]",
        "Gait: ambulated 40 ft with front-wheeled walker",
        "Transfers: min assist x1 for transfers sit to stand",
        "Balance: fair, unsteady on turns",
        "Endurance: limited by leg pain",
        "~ Recommend continued PT, not safe for stairs",
        "Recommendation: home with assist or skilled facility",
    ]},
    {"type": "nursing", "rotate": 0, "lines": [
        "NURSING NOTE", "",
        "Time: 07:15",
        "Patient requires assistance with showering",
        "Toileting: independent with urinal at bedside",
        "Took oral antibiotic without prompting",
        "Alert and oriented x4",
        "Vitals: T 98.4  HR 82  BP 128/76  RR 16  SpO2 97% RA",
    ]},
    {"type": "labs", "rotate": 0, "lines": [
        "LABORATORY RESULTS", "",
        "Collected: [[00/00/0000]] 05:40",
        "WBC 8.1   Hgb 13.2   Plt 245",
        "MRSA nares PCR: NEGATIVE",
        "SARS-CoV-2 PCR: NEGATIVE   Collected [[00/00/0000]]",
        "Glucose 104",
    ]},
    {"type": "medication_list", "rotate": 0, "lines": [
        "DISCHARGE MEDICATION LIST", "",
        "cephalexin 500 mg PO four times daily x 7 days",
        "acetaminophen 650 mg PO every 6 hours as needed for pain",
        "Patient to self-administer all medications",
    ]},
]

D02 = [
    _fax_cover("Mesa Ridge Hospital (invented)", 9),
    {"type": "ihh_referral_form", "rotate": 0, "lines": [
        FORM_HEADER, "",
        "Patient name: [[Xxxxx Xxxxxxx]]   DOB: [[00/00/0000]]   Age: 47",
        "Referring facility: Mesa Ridge Hospital (invented)",
        "Case manager: [[Xxxxxx Xxxx]]   Phone: [[555-0000]]",
        "Preferred language: Spanish",
        "Housing status: [X] Unhoused   [ ] At risk   [ ] Inadequate environment",
        "Primary diagnosis: s/p laparoscopic appendectomy",
        "",
        "SCREENING (all must be met):",
        "[X] Medically and psychiatrically stable",
        "[X] Patient is AAOx4",
        "[X] Able to manage ADLs",
        "[X] Able to self-administer medications",
        "[X] Ambulates 100 ft independently and transfers independently",
        "",
        "~ Home health ordered for wound check",
    ]},
    {"type": "authorization", "rotate": 0, "lines": [
        "CALAIM COMMUNITY SUPPORTS AUTHORIZATION REQUEST", "",
        "Service requested: Recuperative care",
        "Member ID: [[XXXXXXXXX]]",
        "Requested days: 30",
        "Requesting provider: Mesa Ridge Hospital (invented)",
    ]},
    {"type": "face_sheet", "rotate": 0, "lines": [
        "FACE SHEET", "",
        "Name: [[Xxxxx Xxxxxxx]]",
        "MRN: [[000000000]]",
        "Language: Spanish",
        "Payer: Medi-Cal managed care",
    ]},
    {"type": "history_physical", "rotate": 0, "lines": [
        "HISTORY AND PHYSICAL", "",
        "47 y/o female, unhoused, presented with acute appendicitis",
        "Underwent laparoscopic appendectomy, uncomplicated",
        "PMH: type 2 diabetes on insulin glargine",
        "Psych: AOx4, no SI, no hallucinations, mood stable",
        "No conservatorship. No history of aggressive behavior.",
        "No alcohol or drug use reported",
    ]},
    {"type": "pt_ot", "rotate": 0, "lines": [
        "OCCUPATIONAL / PHYSICAL THERAPY NOTE", "",
        "Ambulated 300 ft independently without device",
        "Transfers independent",
        "Showers independently using shower chair",
        "Toileting independent",
        "Discharge recommendation: no further therapy needs",
    ]},
    {"type": "nursing", "rotate": 0, "lines": [
        "NURSING NOTE / DIABETES EDUCATION", "",
        "Patient self-administers insulin glargine with correct technique",
        "Demonstrated glucometer use independently",
        "Fingerstick glucose: 248, 211, 176, 152, 138",
        "Incision clean, dry and intact, 3 port sites",
        "Vitals: T 98.6  HR 76  BP 122/78  SpO2 98% RA",
    ]},
    {"type": "medication_list", "rotate": 0, "lines": [
        "DISCHARGE MEDICATION LIST", "",
        "insulin glargine 18 units subcutaneous at bedtime",
        "metformin 500 mg PO twice daily",
        "acetaminophen 650 mg PO every 6 hours as needed",
    ]},
    {"type": "orders", "rotate": 0, "lines": [
        "DISCHARGE ORDERS", "",
        "Home health referral: wound check and diabetes follow-up",
        "Home health agency: [[Xxxxxxx Xxxx Xxxxxx]]  start of care pending",
        "Follow up with surgery clinic in 7-10 days",
        "MRSA screen: negative     COVID-19 PCR: negative",
    ]},
]

D03 = [
    _fax_cover("Coastline Community Hospital (invented)", 7),
    {"type": "face_sheet", "rotate": 0, "lines": [
        "FACE SHEET", "",
        "Name: [[Xxxxxxx Xxxxx]]",
        "MRN: [[000000000]]",
        "DOB: [[00/00/0000]]",
        "Language: English",
        "Payer: Medi-Cal managed care",
    ]},
    {"type": "history_physical", "rotate": 0, "lines": [
        "HISTORY AND PHYSICAL", "",
        "36 y/o male, sleeping outdoors, admitted with community-acquired pneumonia",
        "Chest x-ray: right lower lobe infiltrate",
        "Treated with IV ceftriaxone, now on oral amoxicillin-clavulanate",
        "History of major depressive disorder",
        "Ambulating independently in hallway",
    ]},
    {"type": "psychiatry", "rotate": 0, "lines": [
        "PSYCHIATRY CONSULT", "",
        "Reason for consult: depressed mood, statements of hopelessness",
        "Patient endorses passive suicidal ideation, no plan",
        "Denies auditory or visual hallucinations",
        "Recommend: continue sertraline, safety planning, outpatient follow-up",
        "~ Re-evaluate prior to discharge",
    ]},
    {"type": "progress_note", "rotate": 0, "lines": [
        "PROGRESS NOTE", "",
        "Time: 10:30",
        "Afebrile, breathing comfortably on room air",
        "Patient denies SI today, mood improved",
        "Independent with ADLs per nursing",
        "Plan: discharge when placement found",
    ]},
    {"type": "nursing", "rotate": 0, "lines": [
        "NURSING FLOWSHEET", "",
        "Vitals: T 98.9  HR 88  BP 118/72  RR 18  SpO2 95% RA",
        "Takes medications independently",
        "Alert and oriented x4",
    ]},
    {"type": "medication_list", "rotate": 0, "lines": [
        "MEDICATION LIST", "",
        "amoxicillin-clavulanate 875 mg PO twice daily",
        "sertraline 50 mg PO daily",
    ]},
]

PACKETS = {"D01": D01, "D02": D02, "D03": D03}

_REDACT = re.compile(r"\[\[(.*?)\]\]")


def _font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def render_page(page: dict, rng: random.Random) -> Image.Image:
    typed = _font(["cour.ttf", "consola.ttf", "DejaVuSansMono.ttf"], 30)
    bold = _font(["courbd.ttf", "consolab.ttf", "DejaVuSansMono-Bold.ttf"], 32)
    hand = _font(["Inkfree.ttf", "segoepr.ttf", "comic.ttf", "DejaVuSans-Oblique.ttf"], 40)
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((MARGIN, 50), FAX, font=_font(["cour.ttf", "DejaVuSansMono.ttf"], 22), fill=90)
    y = 140
    for i, line in enumerate(page["lines"]):
        font = hand if line.startswith("~") else (bold if i == 0 else typed)
        text = line[1:].strip() if line.startswith("~") else line
        x = MARGIN + (rng.randint(-4, 10) if line.startswith("~") else 0)
        pos = 0
        for m in _REDACT.finditer(text):
            seg = text[pos:m.start()]
            d.text((x, y), seg, font=font, fill=20)
            x += d.textlength(seg, font=font)
            wbox = d.textlength(m.group(1), font=font)
            d.rectangle([x, y - 4, x + wbox, y + 34], fill=0)
            x += wbox
            pos = m.end()
        d.text((x, y), text[pos:], font=font, fill=30 if line.startswith("~") else 20)
        y += LINE_H + (10 if line.startswith("~") else 0)
    # Fax look: slight skew, speckle, soft blur.
    img = img.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, fillcolor=255)
    px = img.load()
    for _ in range(4000):
        px[rng.randrange(W), rng.randrange(H)] = rng.choice((0, 60, 120))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    if page.get("rotate"):
        img = img.rotate(-page["rotate"], expand=True, fillcolor=255)
    return img


def build(out_dir) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for pid, pages in PACKETS.items():
        rng = random.Random(pid)
        imgs = [render_page(p, rng) for p in pages]
        path = out / f"{pid}.pdf"
        imgs[0].save(path, "PDF", resolution=200, save_all=True, append_images=imgs[1:])
        written.append(path)
    return written


if __name__ == "__main__":
    for p in build(sys.argv[1] if len(sys.argv) > 1 else "."):
        print(p)
