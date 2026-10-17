# Intake context: Challenge 1 working brief

Reference for any Claude session that works on our Challenge 1 (referral intake) build. Read this
first, then `CLAUDE.md`. It condenses the event repo. When this file and a source file disagree,
the source file wins: `CLAUDE.md`, `docs/ground-rules.md`, and
`challenges/1-referral-intake/criteria/*`. When the written rules and IHH staff in the room
disagree, IHH staff win.

Written October 17, 2026, the day of the event.

---

## 1. The event in one paragraph

**Orange County | Claude Impact Lab**: a one-day hackathon on Saturday, October 17, 2026, at
EvoNexus Irvine, with **Illumination Health + Home (IHH)**. IHH is a Santa Ana nonprofit that
provides recuperative care, housing and case management for people experiencing homelessness. It
was called Illumination Foundation until 2025, so older documents say "IF". Teams of up to 4
people each pick one of three challenges. We are on **Challenge 1: Referral intake**. Everything we
build is open source (MIT) and donated to IHH.

| Time | What |
|---|---|
| 9:30 AM | Build starts. Only work done after this counts |
| **4:00 PM** | **Submission due:** a public GitHub repo with a README, plus the form at https://claudesocal.com/oc-impact-lab#submit |
| 4:30 to 5:30 PM | Finalist demos over the Meet call (https://meet.google.com/ajf-fryh-age), sharing a screen |
| 5:30 PM | Judges rank the finalists |
| 5:45 PM | Winners announced |

**Judging** (finalists scored 1 to 5 in each area):

| Weight | Area | The question |
|---|---|---|
| 40% | Day-one impact | Is it ready to use, and would it help IHH on day one? |
| 35% | Product and idea | Could the coordinator use it without help? Is it a creative, useful way in? |
| 25% | Demo clarity | Are the problem, the user and the outcome obvious? |

- **Judges may hand us a packet our tool has not seen and ask us to run it live.** The pipeline
  must work on any packet, not just R01 to R11.
- Slides without a working demo do not place.
- Anything built on real patient information is disqualified.

---

## 2. Rules that do not bend

1. **No identifiable patient information.**
   - The packets are real referrals with every identifier blacked out.
   - Read them by path. **Never copy them into the repo**, post them, or try to identify anyone.
   - If a page shows an identifier that was missed, **stop** and tell the user to find an
     organizer.
   - If anyone pastes something that looks like a real person's health or personal information,
     stop. Say what you noticed and do not process it.
2. **Prototype only.**
   - Nothing connects to, reads from or writes to IHH systems.
   - Nothing sends email, texts or faxes. Draft messages; never send them.
3. **Quality control.** AI makes mistakes. The tool must catch its own mistakes.
4. **Never invent facts.** That includes page numbers, quotes, lab values, phone numbers, hours and
   rules. If the source does not say, the answer is **"unknown"**. A confident wrong answer is the
   worst outcome.
5. **No medical, legal or immigration advice** in anything client-facing.
6. **No secrets in git.** API keys go in environment variables. `.env` is gitignored.
7. **Be straight in the demo.** Show what works, say what is mocked, and say where it gets things
   wrong.

---

## 3. The problem

> How might we help a coordinator say yes in minutes, so a patient doesn't leave the hospital for
> the street?

- **Users:**
  - IHH's **referral coordinator**.
  - The patient who is ready for discharge but too sick to recover on the street.
- **Today:**
  - Each referral is **14 to 34 faxed pages**: scans that are crooked, sideways, upside down,
    handwritten in places and out of order.
  - The coordinator reads every page by hand against six pages of criteria.
- **Time pressure:**
  - Hospitals send the same referral to several providers.
  - IHH promises an approve or deny answer **within 2 hours**, with a brief explanation if denied.
  - A slow answer means the patient may be discharged to the street.
- **Why it's hard:**
  - The referral form is one person's summary and can be wrong. **The deciding fact is often deep
    in the chart** and can contradict the form.
  - "Not in the packet" means unknown, not normal.
  - IHH's two rule documents disagree in places, and some cases fall in the gaps between them.

### Background a non-clinician needs

- **Recuperative care**, also called medical respite, is a bed, meals and health monitoring for
  people experiencing homelessness who are too sick for the street but don't need a hospital.
  - It is **not** a hospital and **not** a nursing home.
  - **Staff cannot administer medications**, so clients must self-manage: take their own meds,
    bathe, and walk 100 ft.
- California law (HSC 1262.5) requires hospitals to have a discharge plan for homeless patients.
  The referral packet is that hand-off.
- In Orange County, Medi-Cal plan CalOptima pays for stays as a CalAIM "Community Support". A stay
  is auto-authorized for 30 days and can be renewed in 30-day increments, up to 90 days.
- Terms (ADLs, AOx4, DME, CIWA-Ar, PICC, H&P, MAR and others) are explained in `docs/glossary.md`.

---

## 4. What's in the repo for Challenge 1

All paths are relative to `challenges/1-referral-intake/`.

| Path | What it is | How to use it |
|---|---|---|
| `packets/R01.pdf` to `R11.pdf` | 11 real de-identified packets, 282 pages in all. Image-only, 200 dpi, no text layer | **Not in git.** Download from https://drive.google.com/drive/folders/1ISmUtoNCTW3NJNqCQJHJzb6C319RgrXM ("Download all") and move the 11 PDFs into `packets/`. Gitignored. Read by path only |
| `criteria/admission-criteria.json` | **The machine-readable rulebook** with stable rule IDs | The engine's source of truth |
| `criteria/admission-criteria.md` | The same outline in IHH's wording, plus the table of unclear points | Show to humans; cite IDs from the JSON |
| `criteria/referral-form-and-checklist.md` | The hospital-facing form RC0725-SH: its screening rules and the 10-document checklist | |
| `criteria/childrens-admission-criteria.md` | Under-18 rules | Optional. No children's packets exist |
| `criteria/source/*.pdf` | The original IHH PDFs | |
| `eval/decisions.json` | IHH's real outcome per packet: **7 approved, 4 denied**, with no reasons recorded | **Scoring only.** Never feed it to the reviewing model or read it while reviewing a packet |

### What's in each packet

| Packet | Pages | Notable |
|---|---|---|
| R01 | 34 | Authorization pages out of order; 19 pages of sideways medication records; PT evaluation upside down |
| R02 | 22 | Full set: nursing note, labs, imaging, medication list, H&P |
| R03 | 23 | **No IHH referral form**; cardiac catheterization report and ECG |
| R04 | 18 | Includes an older record scanned sideways |
| R05 | 14 | Nursing flowsheets |
| R06 | 30 | IHH referral form is the **last** page |
| R07 | 30 | OT and PT evaluations; 10 pages of progress notes; social work notes |
| R08 | 29 | PT evaluation, nursing notes, physician orders, labs |
| R09 | 30 | Face sheet twice; IHH referral form last |
| R10 | 21 | **No IHH referral form**; psychiatry consult |
| R11 | 31 | Wound notes; labs and vitals scanned sideways |

The packets README says only R10 has no referral form. Its own page listing for R03 also shows
none. Check R03 when the packets are downloaded.

### Packet facts to handle

- **Black box = "removed for privacy".** Never report a redacted field as a missing document.
- **Dates are blacked out**; times of day remain. Any rule that turns on a date or a count of hours
  is **"can't tell from this packet"**. That includes 24 h on insulin, 72 h after alcohol, a COVID
  swab within 24 h, and BP stable for 24 h.
- Pages can be duplicated, near-blank, from an earlier stay, rotated, or out of order.
- Charts contradict themselves: age, living situation and medication plan can differ from page to
  page. Surface the conflict; do not pick a side silently.

---

## 5. The rulebook: `criteria/admission-criteria.json`

Top-level keys: `title`, `source`, `precedence`, `kinds`, `general`, `rules` (48),
`by_system` (9 systems), `referral_checklist`, `referral_form_screen`.

### What each `kind` means

| kind | Meaning |
|---|---|
| `must` | The patient has to meet this |
| `exclude` | Not eligible if this is true |
| `document` | Something the hospital must send |
| `conditional` | Allowed only if the stated arrangement is confirmed before admission (home health, hospice, O2 tank and so on) |
| `ask` | A question IHH wants answered. Not pass or fail on its own |
| `note` | Context |
| `eligible` / `ineligible` | Used in `by_system`: a diagnosis that is generally accepted or rejected |

### Which document wins

- **The internal outline (Nov 2023) beats the hospital referral form (RC0725, 2025).**
- Settled conflicts:
  - **Sex offender:** FORM-X6 says not eligible; OTH-2 says case by case, with violent offenses
    likely denied. **Flag for the coordinator; never auto-deny.**
  - **Wheelchair users:** FORM-M6 and FORM-X3 ask for walking 100 ft. MOB-3 and MOB-4 win: a
    wheelchair-dependent patient who transfers independently and uses the chair independently is
    eligible.
- Where the outline is silent, the form's exclusion applies: **tuberculosis** and **refusing
  detox** (FORM-X4, FORM-X5).

### General entry (meets at least one)

- GEN-1: Homeless or at risk, and too ill or frail to recover
- GEN-2: Lives alone with no formal supports, and too ill or frail to recover
- GEN-3: At risk of hospitalization or re-hospitalization

### Core rules (`rules`)

| ID | kind | Short form |
|---|---|---|
| ADL-1 | must | All ADLs independently, including hygiene |
| ADL-2 | must | Bathes independently, gathering supplies and transferring to the shower. A seated shower is OK |
| ADL-3 | must | Toilets independently or changes briefs independently |
| MOB-1 | must | Uses any DME independently |
| MOB-2 | document | PT/OT notes sent |
| MOB-3 | must | Walks at least 100 ft at modified independence (rests OK) if not wheelchair-dependent |
| MOB-4 | must | Wheelchair-dependent: transfers independently |
| MH-1 | must | Mentally stable on medications |
| MH-2 | exclude | Suicidal ideation |
| MH-3 | exclude | Command auditory or visual hallucinations |
| MH-4 | must | Acute alcohol intoxication: held at least 72 h, no withdrawal (CIWA-Ar < 8) |
| MH-5 | exclude | Conservatorship or FSP, now or in the past |
| COG-1 | must | Can self-administer medications (confirm insulin) and receive education |
| COG-2 | must | AOx4 |
| OTH-1 | exclude | Verbally or physically aggressive |
| OTH-2 | note | Registered sex offender: case by case, violent offenses likely denied |
| OTH-3 | conditional | IV access: OK if home health is established. No time limit |
| OTH-4 | exclude | On isolation, unless cleared before admission |
| EOL-1 | conditional | Hospice is eligible if hospice services are arranged before admission and everyone knows staff can't give meds |
| INF-1 | document | Negative MRSA swab before admission, if coming from inpatient |
| INF-2 | document | Negative COVID swab within 24 h of admission, if coming from inpatient |
| DM-1 | document | Inpatient: 5 consecutive glucose readings showing improvement and stabilization |
| DM-2 | must | From the ED: documented not in DKA |
| DM-3 | exclude | Insulin regimen started less than 24 h before admission |
| DM-4 | conditional | Poorly controlled diabetic from the ED: PCP follow-up in 5 to 7 days, no hypoglycemia in the past week, and a written glucose plan |
| DM-5 | must | Understands the glucometer |
| DM-6 | must | Understands insulin administration, if applicable |
| DM-Q1 to Q3 | ask | Insulin or pump? Oral medications? Last A1C (not limiting)? |
| ID-1 | document | Last 5 sets of vitals. Ineligible if they show sepsis (continued fever, high heart rate, low BP) |
| ID-2 | must | Can take oral antibiotics independently |
| ID-3 | conditional | IV antibiotics: home health ordered before admission |
| ID-Q1 to Q3 | ask | Infection location? Cultures and results? On isolation? |
| RESP-1 | document | Chest imaging, when available |
| RESP-2 | document | Last 5 sets of vitals. O2 sat stable and at the patient's baseline (COPD may run low) |
| RESP-3 | conditional | O2 needed: the hospital orders it and the tank is ready the day before arrival |
| RESP-4 | document | Respiratory therapy notes |
| RESP-Q1, Q2 | ask | Breathing treatments? Antibiotics? |
| CARD-1 | document | Last 5 sets of vitals; BP stable on oral meds for at least 24 h |
| CARD-2 | document | Troponin: at least 3 consecutive results, at least 2 negative |
| CARD-3 | document | EKG sent |
| CARD-4 | must | Atrial fibrillation: self-manages anticoagulation and understands INR labs |
| CARD-5 | exclude | EF at least 25% is OK if it is the patient's baseline. Ineligible if on chemotherapy, or straight after a heart attack with a lowered EF |
| CARD-6 | exclude | IV antihypertensives within 24 h |

### Diagnoses by body system (`by_system`)

E = eligible, X = ineligible. A conditional E means the stated arrangement must be in place.

- **Integumentary (skin and wounds):**
  - E1: uncomplicated skin infection, cellulitis or abscess on oral antibiotics.
  - E2 (conditional): wound care coordinated with home health, timed to dressing changes.
    Hard-to-reach wounds (coccyx, back of thighs, back, perineum) always need at least one wound
    care visit.
  - E3 (conditional): IV antibiotics with home health.
  - E4: uncomplicated wounds.
  - E5 (conditional): post-surgical incision, with suture or staple removal scheduled.
  - E6 (conditional): stage 1 to 3 pressure ulcers, wound care scheduled.
  - E7 (conditional): third-degree burns under 15% of the body.
  - X1: skin graft needed. X2: complicated large abscess. X3: burns with inhalation injury.
- **Ophthalmology:**
  - E1 to E7: uncomplicated eye infection; post-op glaucoma; uncomplicated cataract with lens;
    diabetic retinopathy; diabetic macular edema; post-op vitreous hemorrhage; post-op retinal
    detachment.
- **Respiratory:**
  - E1 to E7: pneumonia; bronchitis; COPD without continuous O2; asthma; O2 baseline at least 94%
    with physician explanation; mature tracheostomy that the patient self-cares for; CPAP.
  - X1 to X5: pneumothorax; hemothorax; trach with ventilator; **pulmonary embolism**; BiPAP.
- **Musculoskeletal:**
  - E1: closed fractures. E2 (conditional): PT scheduled. E3: rheumatoid arthritis. E4:
    non-elective hip or knee replacement after a SNF stay.
  - X1 to X5: open fracture; **osteomyelitis**; external fixator; straight after an amputation
    with wounds; jaw wiring.
- **GI:**
  - E1 to E7: post-abdominal surgery; uncomplicated hernia; diverticulitis; uncomplicated IBD;
    chronic ascites; GERD; non-surgical bowel obstruction.
  - X1: **decompensated cirrhosis** (ascites, varices, encephalopathy, jaundice). X2: straight
    after a bleeding ulcer or varices. X3: **C. diff**.
- **Endocrine:**
  - E1: diabetes stabilizing on at least 5 readings. E2: thyroid disease on treatment. E3: s/p
    thyroidectomy.
  - X1: immediately s/p parathyroidectomy. X2: alcoholic ketoacidosis. X3: **DKA**.
- **GU:**
  - E1 to E4: UTI; post-infectious glomerulonephritis; laparoscopic gynecologic surgery for a
    non-cancerous condition; kidney stones.
  - E5 (conditional): self-catheterizes. E6 (conditional): indwelling catheter the patient empties,
    with removal follow-up scheduled. E7 (conditional): dialysis schedule established.
  - X1: intermittent catheterization that staff must perform.
- **Circulatory:**
  - E1 to E4: post angiogram; catheterization or stent; pacemaker or ICD; stable untreated high BP
    (SBP < 170, DBP < 100, no symptoms, PCP follow-up).
  - E5 (conditional): post CABG or valve surgery, with stable BP, normal Hgb/Hct, normal EF, no
    arrhythmia, and home health and surgical follow-up scheduled.
  - E6: high BP controlled on oral medication. E7: history of heart attack; straight after one,
    only with a normal EF.
  - X1: unstable arrhythmia. X2: high BP that needs IV medication, has symptoms, or doesn't respond
    to oral medication.
- **Neurology:**
  - E1 to E4: alcohol withdrawal seizure after detox; carpal or cubital tunnel release; mild TBI
    with intact ADLs; radiculopathy after an injection or decompression.
  - X1 to X6: **stroke with residual deficit**; new seizure with deficit; moderate or severe TBI;
    cervical or lumbar fusion; **dementia**; immediately s/p neurosurgery (escalate to review).

### Hospital-form screening (`referral_form_screen`)

- **Must meet all:**
  - FORM-M1: unhoused, at risk, or inadequate housing.
  - FORM-M2: medically and psychiatrically stable.
  - FORM-M3: AAOx4.
  - FORM-M4: manages ADLs.
  - FORM-M5: self-administers medications.
  - FORM-M6: walks 100 ft with or without DME and transfers independently. Overridden by
    MOB-3 and MOB-4.
- **Not eligible if:**
  - FORM-X1: cognitive impairment such as dementia or Alzheimer's.
  - FORM-X2: unable to do ADLs.
  - FORM-X3: can't transfer, walk 100 ft, or use DME independently. Overridden by MOB-3 and MOB-4.
  - FORM-X4: active infection (MRSA, **TB**, C. diff) not cleared by a doctor or infectious
    disease specialist.
  - FORM-X5: **refuses detox or abstinence**.
  - FORM-X6: registered sex offender. Overridden by OTH-2.
  - FORM-X7: aggressive behavior.

### Documents the hospital should send (`referral_checklist`)

| ID | Document |
|---|---|
| DOC-1 | IHH referral form |
| DOC-2 | Demographic page (face sheet) |
| DOC-3 | CalOptima form, LOA or authorization |
| DOC-4 | H&P (history and physical) |
| DOC-5 | Current progress notes (if needed) |
| DOC-6 | Updated vitals (last 24 h) |
| DOC-7 | Medication list |
| DOC-8 | PT/OT or nursing notes |
| DOC-9 | Blood or wound culture (if needed) |
| DOC-10 | 30-day supply of all medications |

DOC-10 is a physical supply of medication, not a page. The tool can only check whether the packet
mentions it.

### Where the written rules run out: flag these, don't guess

- Sex offender: case by case. Never auto-deny.
- The O2 "94% or greater with physician explanation" rule has no stated practical meaning.
- The A1C sentence is cut off in the source.
- "FSP" is undefined. It is probably Full Service Partnership.
- The insulin "less than 24 h" rule doesn't say whether the clock starts at the first dose or when
  doses stop changing. Dates are redacted anyway.
- DKA: it's unclear whether DKA that has resolved still excludes.
- C. diff: it's unclear whether the exclusion ends when isolation lifts or when treatment ends.
- Troponin after a heart attack: CARD-2 wants negative troponins, but CIR-E7 says a history of
  heart attack is eligible.
- The COVID swab may be more than 24 h old by the time the patient arrives.
- "Complicated large abscess" is undefined.
- The hard-to-reach wound list has a missing item, and the sacrum is not named.
- The home health threshold varies by rule: "established", "ordered", "coordinated", "coordinated
  and scheduled".
- The outcomes are only approve or deny. There is no "not yet, re-refer when ready".

---

## 6. Agreed design direction (proposed; confirm with the team)

**Output per packet:** a coordinator-facing review, not an autonomous decision. The human decides.

1. **Ingest.** Render each PDF page to an image (pypdfium2 or PyMuPDF) and keep packets outside the
   repo or in the gitignored `packets/` folder.
2. **Page pass (Claude vision).** For each page, record:
   - The page type: referral form, face sheet, authorization, H&P, progress note, PT/OT, nursing,
     MAR or medication list, labs, vitals, imaging, ECG, consult, social work, fax cover, blank, or
     earlier stay.
   - The rotation.
   - Whether the page is mostly redacted.
   - Extracted facts, each with **page number and a short verbatim quote**.
3. **Rule pass.** For every relevant rule ID, give a status of **met / not met / can't tell /
   not applicable**, with evidence (page and quote) and any conflict found. Date or hour rules
   default to "can't tell".
4. **Checklist pass.** Mark DOC-1 to DOC-10 as present (with pages), missing, or not determinable.
   A redacted field is not a missing document.
5. **Form vs. chart.** Flag every place where the IHH referral form says one thing and the chart
   says another.
6. **Verifier (the quality-control step).** A second pass checks that each quote really appears on
   the cited page. Anything it can't verify is dropped or marked "unverified".
7. **Recommendation:** approve, deny, or **needs info**, with the top reasons as rule IDs plus
   evidence, open questions for the hospital, and the gaps that need a coordinator's judgment.
   Include a **draft** reply to the hospital that is never sent.
8. **Eval harness:** run R01 to R11 and compare with `eval/decisions.json` in a separate script
   that the reviewer never sees. Report accuracy and misses in the README.

**Language:** every screen and every draft works in English and Spanish, with one switch. Statuses
stay language-free codes in the data, and quotes stay word for word. See `docs/bilingual.md`.

**Stack (proposed):** Python, the Anthropic SDK (vision; model `claude-opus-5-5` or
`claude-sonnet-5-5`), Streamlit for the UI, and `ANTHROPIC_API_KEY` from the environment. Event
credits are $100 per person, API only, claimed with a Console Org ID.

---

## 7. Before submitting (4:00 PM)

- [ ] Our own **public** repo with an MIT `LICENSE`.
- [ ] README follows `templates/TEAM-README.md`: problem, what we built, how Claude is used, how to
      run it, real vs. mocked, where it gets things wrong, next steps, data and privacy.
- [ ] **No packet PDFs, page images or extracted packet text in the repo or its history.** Check
      cached outputs and screenshots too.
- [ ] No API keys in the repo or its history.
- [ ] Someone outside the team can run it from the README.
- [ ] Every screen and draft works in English and Spanish, and the README has a short Spanish
      summary (`docs/bilingual.md`).
- [ ] An optional 2-minute screen recording, linked in the README.
- [ ] The submission form is filled in.
- [ ] The demo works on an **unseen packet**.

## 8. Open items

- Packets are not downloaded yet. Someone needs to pull them from Drive.
- Team repo: this folder is a clone of `travcjohnson/claude-impact-lab-oc` with `origin` pointing
  at the template. We need our own public repo and must repoint `origin`.
- Confirm the stack and the team split.
- IHH's answers from our Q&A with their referral lead, the build design and the questions still
  open: `docs/workflow-and-timing.md`. Section 11 lists what is answered and what is still open.
