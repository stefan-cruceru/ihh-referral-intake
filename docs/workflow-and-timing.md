# Intake workflow and the 2-hour clock

What IHH told our team on October 17, and what it means for the Challenge 1 build. Read
`docs/intake-context.md` first. This file adds to it and does not replace it.

How to read the labels:

- **(lead)**: from our recorded Q&A with IHH's referral lead, who also runs hospital outreach and
  oversees the referral team.
- **(staff)**: from an earlier, shorter conversation with IHH staff in the room.
- **unconfirmed**: we think so, but nobody at IHH has confirmed it yet.
- **placeholder**: a made-up number for illustration. Replace it with IHH's real number (section 12).

Business figures shared in the Q&A (rates, margins, budget) are kept out of this public repo on
purpose.

---

## 1. What IHH told us

### The number that matters

- **About half of all referrals end up withdrawn.** About half of those, so roughly **a quarter of
  all referrals**, are lost because the patient went to another placement or left the hospital
  against medical advice (AMA). IHH reads that as being too slow for the hospital. **(lead)**
- Winning that quarter back would fix their bed problem. Beds are below IHH's utilization target,
  partly because health plans now shorten stays. **(lead)**
- Withdrawals mostly stall in **"communication black holes"**: hospital case managers stop
  answering follow-ups. Today IHH handles this with regular check-ins, escalating to supervisors,
  and more training for case managers. **(lead)**

### How intake works today

- **Team:** a lead plus 3 coordinators, 4 people on staggered shifts. Referrals come in 24/7. After
  hours, the director, the lead and salaried staff cover. **(lead)**
- **Who takes a referral:** first come, first served. Whoever is at the fax picks it up and usually
  keeps it. **They want a clearer way to assign referrals.** **(lead)**
- **How referrals arrive:** PDFs, by **fax and by email**. Fax goes through a third-party e-fax
  service, and IHH is reviewing options for it. One main phone line plus individual extensions;
  hospital callbacks rotate through the main line. **(lead)**
- **The packet:** IHH's intake form, **filled out by the hospital case manager**, plus a checklist
  of supporting documents (nursing notes, PT/OT notes and so on). **(lead)**
- **The 2-hour clock starts when the packet arrives**, not when someone opens it. **(lead)**
- **Busiest times:** the start of the work week and around 4 PM. Weekends are quiet. **(lead)**
- **Where the 2 hours go:** mostly reviewing. The referrals that end up withdrawn are the ones that
  tend to get stuck waiting on the hospital. **(lead)**
- **Sites:** six, by the lead's count: three in Orange County (the largest), one in Riverside and a
  new children's recuperative care site in Los Angeles. The sixth wasn't named. The census has one
  tab per facility. **(lead)**

### Decision rules

- The full criteria are the ones in this repo. The two big ones: **(lead)**
  1. **Daily living (ADLs):** the patient must be independent: eat, use the toilet, move
     themselves, get out of bed. IHH isn't a licensed medical facility, so staff can't give
     hands-on care.
  2. **Psychiatric stability:** no active suicidal thoughts and no active psychosis.
  - Also excluded: certain medications and medical equipment IHH can't handle.
- **Why those two decide it: IHH has no Title 22 license.** Title 22 is the part of California's
  regulations that licenses health and care facilities. Without it, IHH can't give hands-on care or
  administer medications. So every referral has to be checked for two things before the patient can
  stay: **they can care for themselves, and they are behaviorally stable.** **(staff)** Section 5
  maps both gates to rule IDs.
- **Nobody is denied without a clinical second check.** Every possible "no" goes to the clinical
  line, staffed 24/7. Unconfirmed: whether an LVN staffs it. **(lead)**
- The criteria are reviewed yearly and rarely change. Updates come from IHH's own quality reviews
  or from DHCS. **(lead)**
- **How hospitals learn the criteria:** the lead trains hospital case managers and social workers
  in person (in-services) and leaves printed documentation. Coordinators answer questions after
  that. **(lead)**

### After a "yes": three manual steps

1. Create the client in **Kipu**, their electronic medical record, with the face sheet and referral
   information.
2. Add a row to the **Excel census**, which has one tab per facility.
3. Email the site's **operations distribution list**. **(lead)**

### Tools

- IHH runs on Microsoft. Every employee has **Copilot under a BAA**, so it is cleared for patient
  health information. **(lead)**
- Hospital contacts live mostly in Excel, not in a CRM. **(lead)**

### From the earlier conversation

- The clinical team approves after intake, and an intake yes that clinical then rejects causes
  real problems. **(staff)** See "Where sources disagree".
- There aren't enough people to reliably make 2 hours. Time is the main issue. **(staff)** The Q&A
  backs this up: 4 people, 24/7, with peaks.
- The process is "connected to CIQ". **(staff)** CIQ did not come up in the Q&A. Unknown what it
  is.

### What the written documents add

- **The 2-hour promise is printed on the form.** Form RC0725 says the decision goes back "within two
  hours of receiving the referral". The form also lists "online" as a way to send.
  (`challenges/1-referral-intake/criteria/referral-form-and-checklist.md`)
- **The coordinator's day** (role card). Missing items mean phone calls to hospital case managers.
  The reply is one of three: yes, no with a brief reason, or a list of what to send. Their worry is
  being blamed for a machine's mistake. (`challenges/3-staff-ai-confidence/roles.md`)
- **The form has nowhere to record a second check.** Its staff-only box has one "reviewed by" line,
  one "approved" line, and a date received with no time. The box is blank in all 11 packets, so
  decisions and reasons are recorded somewhere else, likely Kipu (unconfirmed).
  (`challenges/1-referral-intake/packets/README.md`)
- **Some cases go to clinical review by rule.** Patients straight out of neurosurgery are escalated
  to further clinical review. For children, a nurse visits the hospital to pre-screen.
  (`criteria/admission-criteria.md`, `criteria/childrens-admission-criteria.md`)
- **Six rules are a "yes, if".** OTH-3, EOL-1, DM-4, ID-3, RESP-3 and INT-E2 each need an
  arrangement confirmed before admission: home health, hospice, a glucose plan, an O2 tank ready
  the day before, or wound care.
- **The friction is documented.** In a 2024 study, California recuperative care staff described
  heavy burdens processing referrals, and hospital staff found some programs' eligibility rules
  onerous. (`docs/background.md`)

### Where sources disagree

- **Does clinical check the yeses too?** The earlier conversation said clinical approves after
  intake, and that overturned yeses cause problems. The Q&A said every possible *no* goes to the
  clinical line, and said nothing about yeses. Unknown: do approvals also get a clinical check?
  This decides whether the "do not discharge yet" status in section 5 is needed. Staff later
  explained that the self-care and behavioral gates must be checked for every referral (section 5).
  Whether a clinician does that check every time is still unconfirmed.
- **30 minutes or 2 hours.** IHH's older page ([ifhomeless.org/recup](https://www.ifhomeless.org/recup))
  says referrals are confirmed within 30 minutes. The current form and the lead say 2 hours. We use
  2 hours.
- **What the answer can be.** The written process has only approve or deny, with no "not yet"
  (criteria gaps table). The role card adds a third reply: a list of what to send.
  `intake-context.md` section 6 proposes "needs info".
- **Channels.** The form lists online, email and fax. The lead named fax and email. Whether
  "online" is still used is unknown.

---

## 2. What it changes about the build

**Pitch: "A quarter of referrals walk because we're too slow. Win them back and the beds fill."**

The biggest gain is **closing the follow-up gap with hospitals**, not only reading faster. The
packet review pipeline in `intake-context.md` section 6 stays the core. Around it:

1. **One front door** for fax and email, with the clock starting on arrival (section 6, mocked).
2. **Clear assignment**, instead of whoever is at the fax (section 3).
3. **Missing items caught on arrival**, and the follow-up to the case manager drafted right away,
   with a chase ladder when they go quiet (section 4).
4. **Likely "no" goes straight to the clinical line**, in parallel with the coordinator. Only a
   clinician can deny (section 5).
5. **One click after a "yes"** drafts all three handoffs: Kipu fields, census row, ops email
   (section 7).
6. **English and Spanish throughout:** every screen, status and draft, with one switch
   (`docs/bilingual.md`).

**Judging constraint:** features that need IHH's live systems to mean anything do not place
(`docs/judging.md`). Everything here has to run on its own, with a mock inbox and packets read by
path. Section 8 covers how it could plug into IHH's Microsoft setup later.

### Why minutes per referral matter (placeholder numbers)

Monday around 4 PM, three referrals arrive at once and one coordinator is on:

| Human time per referral | 1st done | 2nd done | 3rd done | 4th done |
|---|---|---|---|---|
| 40 min | 0:40 | 1:20 | 2:00 | **2:40, missed** |
| 10 min | 0:10 | 0:20 | 0:30 | 0:40 |

Most of the 2 hours goes to referrals waiting in line for a free person, not to the review itself.
Cut the minutes each referral takes and the line shrinks. Then the chase ladder keeps the hospital
from going quiet while IHH waits.

### Where the minutes go, and what the tool does about each

| Time sink | What the tool does | In the prototype |
|---|---|---|
| Deciding who takes it | Assigns each referral to an on-shift coordinator; after hours, to the on-call list | UI |
| Reading 14 to 34 pages | Page pass and rule pass, then one screen: key facts and flags, each with page and quote | Core build |
| Missing documents | Checklist pass (DOC-1 to DOC-10) on arrival, then a draft to the case manager listing everything missing at once | Draft only. Never sent |
| Case managers who go quiet | A chase ladder: timed nudges, then a draft to the case manager's supervisor | Drafts and timers. Never sent |
| Waiting for a clinical check on a likely "no" | Flags the likely no with rule IDs and evidence, and routes it to the clinical line at once | UI |
| Three handoffs after a "yes" | Drafts the Kipu fields, the census row and the ops email in one click | Export and drafts. No Kipu or Excel connection |
| "Any update?" calls | A status a hospital could check: received, needs info, clinical check, accepted, denied | Mock page |

---

## 3. The 2-hour tracker

- **The clock starts on arrival**, from the fax or email timestamp, not when someone opens it.
  Confirmed by the lead.
- **Assignment.** Each referral gets an owner the moment it arrives: round-robin across on-shift
  coordinators, or the on-call list after hours. Everyone can see who owns what. A referral can be
  handed off with a click.
- **Each stage gets a time budget** (placeholder; tune with IHH's numbers):

  | Stage | Done by |
  |---|---|
  | Claude reads, flags and checks documents; missing-items draft ready | 0:05 |
  | Coordinator review; a likely "no" is already with the clinical line | 1:00 |
  | Hospital answers open questions | 1:30 |
  | Decision sent | 1:45, leaving a 15-minute buffer |

- **The queue is sorted by time left**, not by arrival. Green: over 60 minutes left. Yellow: 30 to
  60. Red: under 30.
- **Escalation ladder:**
  - 60 minutes left and nobody has opened it: alert the lead.
  - A likely "no" the clinical line hasn't picked up in 30 minutes: alert the clinical line again,
    then the lead.
  - 15 minutes left: a person tells the hospital it needs more time, and why.
- **It never auto-approves or auto-denies to beat the clock.** A late, correct answer beats an
  on-time wrong one.
- **Peak warning.** Busiest at the start of the week and around 4 PM. With N referrals waiting and M
  people on shift, flag which ones will miss before they miss.
- **Report.** Share decided within 2 hours, which stage eats the time, withdrawals and their
  reasons.
- Open question: does the clock pause while IHH waits on the hospital?

---

## 4. Closing the follow-up gap

This is where the lost quarter goes.

- **On arrival:** the checklist pass lists every missing item. Claude drafts one message to the case
  manager with everything at once.
- **Chase ladder** (placeholder timings; IHH already escalates to supervisors by hand):
  - No reply in 30 minutes: draft a nudge.
  - No reply in 60 minutes: draft a message to the case manager's supervisor, from IHH's contact
    list.
  - Each step is a draft a person sends. Nothing is sent automatically.
- **Withdrawal risk.** Each card shows how long the hospital has been silent. Long silence near a
  peak marks the referral most likely to walk.
- **Contacts.** Hospital contacts live in Excel today. The prototype reads an invented contact
  sheet. A pilot would read IHH's.
- **Learn why they walk.** When a referral is withdrawn, record the reason (another placement, AMA,
  no reply) so the report shows where the quarter goes.

---

## 5. The two gates and the clinical check

### The two gates come first

Because IHH has no Title 22 license, two checks decide whether a patient can stay. The review screen
leads with them, above everything else, each marked met, not met or can't tell, with page and quote:

| Gate | Rule IDs (`admission-criteria.json`) | What the chart has to show |
|---|---|---|
| **Can care for themselves** | ADL-1, ADL-2, ADL-3, MOB-1, MOB-3, MOB-4, COG-1, COG-2; form FORM-M3 to M6, FORM-X1 to X3 | Bathes, toilets and moves without hands-on help; uses any DME alone; takes their own medications; fully oriented |
| **Behaviorally stable** | MH-1, MH-2, MH-3, MH-4, MH-5, OTH-1; form FORM-M2, FORM-X5, FORM-X7 | Stable on medications; no suicidal thoughts; no command hallucinations; not in alcohol withdrawal; no conservatorship; not aggressive |

- The evidence for these usually sits deep in the chart: PT/OT evaluations and nursing notes for
  self-care, psychiatry consults and progress notes for behavior. The form-vs-chart check matters
  most here.
- Everything else (infection, diabetes, cardiac, wounds, missing documents) sits below the gates.
- A "not met" or "can't tell" on either gate makes the referral a likely "no" and sends it to the
  clinical line.

### The clinical check

- **IHH's rule: nobody is denied without a clinician.** The tool can flag a likely "no", but only
  the clinical line can deny.
- A likely "no" goes to the clinical line **at the same time** the coordinator sees it, with the
  rule IDs (`rules` and `by_system` in `admission-criteria.json`), the evidence and the quotes. No
  waiting for one review to finish before the next starts.
- The form vs. chart check (`intake-context.md` section 6, step 5) catches cases where the form
  looks fine and the chart doesn't. Example: the form says "independent", the PT note says "needs
  assist". That matters most for the two big rules: ADLs and psychiatric stability.
- **If yeses also get a clinical check** (unknown, see section 1), use two status messages so a
  hospital never discharges on a half-approval:
  - "Intake cleared. Do not discharge yet."
  - "Accepted. OK to discharge."
  Only clinical can send the second.
- Every clinical override gets a logged reason, so the checks improve. In the prototype this is a
  field on the decision.

---

## 6. The front door (mocked)

- **Demo:** a fake inbox with invented referral emails and e-fax PDFs. No real inbox, no real fax.
  Nothing is sent.
- Each arrival opens a card, with the clock started from its timestamp and an owner assigned. Each
  mock arrival points at a packet by path; packets never go in the repo.
- Follow-up emails attach to the right card. In a real pilot that needs two identifiers (name and
  date of birth), and a person confirms when the match is uncertain. In our demo the identifiers are
  blacked out, so cards match on an invented case number in the subject line.
- The original email or fax stays untouched as the record.

**Demo script:**

1. **Monday, 4:00 PM, the busiest hour.** A burst of 5 referrals arrives. Run it twice on a
   fast-forward clock (1 second = 1 minute).
   - **Manual:** first come, first served, 40 minutes each (placeholder). Cards turn yellow, then
     red. Two miss, and one hospital goes quiet and withdraws.
   - **With the tool:** auto-assigned, missing-items drafts ready on arrival, the likely "no" already
     with the clinical line, the chase ladder nudging the quiet hospital. All five are decided in
     time.
2. Click "Accept" on one and show the three handoff drafts: Kipu fields, census row, ops email.
3. Flip the switch to **Español** and show the same card and the hospital draft in Spanish.
4. Run one **unseen** packet live through the pipeline. Judges may hand us one.

---

## 7. After a "yes": three handoffs in one click

| Handoff today | What the tool drafts | In the prototype |
|---|---|---|
| Create the client in Kipu from the face sheet and referral info | The Kipu fields, filled from the packet, with page references | A field list on screen. Redacted fields show "removed for privacy" |
| Add a row to the Excel census, one tab per facility | The census row for the right facility tab | A CSV row |
| Email the site's operations list | The ops email | A draft. Never sent |

A coordinator checks each draft before anything is entered or sent.

---

## 8. A pilot path inside IHH's Microsoft setup (after the event)

The team proposed this in the Q&A. It is not part of today's build, which must run on its own.

- IHH already runs Microsoft 365, with Copilot under a BAA for every employee.
- Power Automate could watch the referral inbox and start the review chain when a packet lands.
- The review could run on Claude models selected inside Microsoft's Copilot tools. Confirm what
  IHH's setup allows.
- The same flows could prepare the Kipu, census and ops-email drafts for a coordinator to approve.
- The e-fax service is being reviewed. A replacement that delivers faxes as PDFs to the same inbox
  would give one front door.

---

## 9. Gaps we may be missing

- **A yes is often a "yes, if".** The six conditional rules (OTH-3, EOL-1, DM-4, ID-3, RESP-3,
  INT-E2) need home health, hospice, an O2 tank or wound care confirmed before admission. Show each
  condition as an open item on the card with its own deadline. RESP-3's O2 tank, for example, has
  to be ready the day before arrival.
- **The first yes works like a discharge order.** California law (HSC 1262.5, from SB 1152) makes
  hospitals identify a post-discharge destination for each homeless patient (`docs/background.md`)
  and keep a log of it (AFS Law summary, in Sources). If anything about a yes changes later, the
  patient can be left with nowhere to go.
- **The form goes stale.** It is filled out hours before transport. A new fever, a fall or IV
  medications can change the answer. The criteria flag one case already: a COVID swab that was
  negative at referral can be more than 24 hours old on arrival (INF-2). Consider a short reconfirm
  before transport.
- **After hours.** The director, the lead and salaried staff cover nights. How fast the clinical
  line answers at 2 AM is unknown.
- **The clock rewards saying yes**, if coordinators are measured on speed alone.
- **A denial needs a next step.** The hospital still has to discharge the patient somewhere.
  Challenge 2 (finding the right resource) is the natural hand-off.
- **Payment.** In Orange County, CalOptima auto-authorizes 30 days (`intake-context.md` section 3).
  How it works for LA and Riverside referrals is unknown.

---

## 10. Liability guardrails for a pilot

A design checklist, not legal advice. IHH's counsel should review it.

- **Claude never approves or denies.** It flags. A named person decides, and **only a clinician can
  deny** (IHH's own rule).
- **Nothing is sent automatically.** Every message to a hospital, supervisor or site team is a draft
  a person sends.
- **Conditional acceptance wording:** "Accepted based on information received at [time]. Report
  any change before transport."
- **A written referral agreement with hospitals:** accurate form, changes reported, 30-day
  medication supply in hand (DOC-10), timely replies to follow-ups. For IHH's counsel to draft.
- **Audit log:** what came in, what Claude flagged, who decided and why, with timestamps.
- **Protect the coordinator too.** The role card says coordinators worry about being blamed for a
  machine's mistake. The log should show what the tool flagged, what the person saw and what they
  decided, so responsibility is clear and fair.
- **Every flag cites a page and a quote**, checked by the verifier step. That builds trust. Letting
  the clinician check the basis for each flag is also the test FDA uses to keep clinical decision
  support software outside medical device rules.
- **Denials cite a rule ID and evidence, never a category label** such as disability, psychiatric
  history or substance use. Track denials by category to catch bias.
- **Privacy.** IHH's Copilot is under a BAA. Any other vendor that touches patient information,
  including a new e-fax service, needs its own. The prototype uses only the de-identified packets
  and invented data.
- **Nothing Claude writes goes to a patient without review.** California's AB 3030 adds disclaimer
  rules for AI-generated patient messages about clinical information.

---

## 11. Questions

### Answered in the Q&A

| Question | Answer |
|---|---|
| When does the 2-hour clock start? | On arrival, not when opened |
| Who fills out the form? | The hospital case manager |
| How do referrals arrive? | PDFs by fax (third-party e-fax) and email |
| Who reviews, and when? | A lead plus 3 coordinators, staggered, 24/7; director, lead and salaried staff after hours |
| Who takes each referral? | First come, first served. They want clearer assignment |
| When is it busiest? | Start of the week and around 4 PM. Weekends are quiet |
| What happens when IHH is slow? | About half of referrals are withdrawn; about a quarter of all go elsewhere or leave AMA |
| Do denials get a clinical check? | Yes. Every possible "no" goes to the 24/7 clinical line |
| What happens after a yes? | Kipu record, Excel census row, ops email, all by hand |
| What tools do they use? | Microsoft 365, Copilot under a BAA, Kipu, Excel |
| Where do the 2 hours go? | Mostly reviewing. Referrals that end up withdrawn tend to be stuck waiting on the hospital |
| How do hospitals learn the criteria? | In-person trainings (in-services) for case managers and social workers, plus printed documentation |

### Still open, most important first

1. **Does a clinician check the two gates (self-care and behavior) on every referral, or only on
   possible denials?** Staff said both gates must be checked for anyone to qualify (no Title 22
   license). The Q&A said possible "no"s go to the clinical line. If every referral gets the
   clinical check, approvals need it too, and the status messages in section 5 apply.
2. **How many minutes does one referral take, and which step is longest?** It replaces every
   placeholder in the capacity math.
3. **When a case manager goes quiet, how long do you wait before following up, and who do you
   escalate to?** This sets the chase ladder in section 4.
4. **When a hospital withdraws, do you hear why?** Is it tracked anywhere?
5. **If you could have one thing on Monday, what would it be?** Judges weight IHH's day-one view
   most.

**Also open**

- "About 150" came up without a unit. Monthly referrals, beds, or something else?
- What is CIQ? It did not come up in the Q&A.
- Which is the sixth site? The lead named three in Orange County, one in Riverside and the
  children's site in Los Angeles.
- Who staffs the clinical line (an LVN?), and how fast does it answer, day and night?
- Does the e-fax service deliver into the same inbox as email, or into a portal?
- Is the arrival time recorded anywhere a tool could read (e-fax or email timestamp)?
- Does the clock pause while IHH waits on the hospital?
- How often is the reply "send us X" rather than yes or no?
- For the "yes, if" rules, who confirms the arrangement, and is the yes given before or after?
- When a packet arrives without the IHH form (like R03 and R10), do you review it or send it back?
- What fields does the hospital contact sheet have: case manager, supervisor, phone, email?
- For LA and Riverside referrals, which plan pays, and does it auto-authorize like CalOptima?
- In three months, what number would tell you this worked?

---

## 12. Numbers

| Number | Answer |
|---|---|
| Referral team | Lead plus 3 coordinators, staggered shifts, 24/7 **(lead)** |
| Busiest times | Start of the week, around 4 PM; weekends quiet **(lead)** |
| Withdrawn referrals | About half **(lead, estimate)** |
| Lost to another placement or AMA | About a quarter of all referrals **(lead, estimate)** |
| Minutes per referral, start to finish, and the longest step | Unknown |
| Referrals per day or month | Unknown ("about 150" was said without a unit) |
| Time spent waiting on hospitals for missing documents | Unknown; the lead said most of the 2 hours is reviewing **(lead)** |
| How often the clinical line overrides the coordinator | Unknown |
| How often the reply is "send us X" | Unknown |

---

## Sources

- [IHH: recuperative care centers](https://illuminationhealthhome.org/service/housing-services/emergency-housing/recuperative-care-centers/)
- [ifhomeless.org/recup](https://www.ifhomeless.org/recup) (older IHH page; "confirmed within 30 minutes")
- [AFS Law: SB 1152 and hospitals discharging homeless patients](https://www.afslaw.com/perspectives/health-care-counsel-blog/california-increases-hospitals-obligations-when-discharging)
- [CDPH All Facilities Letter 19-01 (SB 1152)](https://calhospital.org/wp-content/uploads/2019/01/afl-19-01.pdf)
