# Intake workflow and the 2-hour clock

What IHH staff told our team on October 17, and what it means for the Challenge 1 build. Read
`docs/intake-context.md` first. This file adds to it and does not replace it.

How to read the labels:

- **(staff)**: an IHH staff member told us in the room. Not in the written documents.
- **unconfirmed**: we think so, but nobody at IHH has confirmed it yet.
- **placeholder**: a made-up number for illustration. Replace it with IHH's real number (section 9).

---

## 1. What IHH staff told us

- An LVN sends the referral form. **(staff)** Unconfirmed: whether the LVN works at the hospital or
  at IHH.
- IHH receives referrals **mainly by email**. **(staff)** The packets in this repo are faxed scans.
  How fax and email fit together is unconfirmed.
- The process is connected to **CIQ**. **(staff)** What CIQ is, and whether it can export or take
  in data, is unknown.
- **Two approvals, one after the other.** The first person (intake) approves, then the clinical
  team has to approve. **(staff)**
- **The overturn problem.** When intake approves and clinical does not, it causes a lot of issues.
  **(staff)**
- **2-hour turnaround.** **(staff)**, and the challenge page.
- **There are not enough people to reliably make 2 hours. Time is the main issue.** **(staff)**

### Where sources disagree

- IHH's older public page ([ifhomeless.org/recup](https://www.ifhomeless.org/recup)) says
  referrals are "confirmed within 30 minutes". The challenge page and staff say 2 hours. The 30
  minutes may mean confirming receipt, not deciding. Unconfirmed.
- `intake-context.md` section 6 proposes approve, deny or needs info. IHH's written process has only
  approve or deny (section 5, last bullet). The two-step flow staff described adds a third state in
  practice: intake approved, clinical pending.

---

## 2. What it changes about the build

**Headline: same team, every referral decided within 2 hours.**

The packet review pipeline in `intake-context.md` section 6 stays the core. Staff input adds three
things around it:

1. **A 2-hour clock and queue**, because time is the main issue (section 3).
2. **Intake and clinical reviewing in parallel**, so a first yes can't be overturned later
   (section 4).
3. **An email front door**, mocked, because that is how referrals arrive (section 5).

### Why minutes per referral is the lever (placeholder numbers)

Three referrals arrive at once and one person reviews them:

| Human time per referral | 1st done | 2nd done | 3rd done | 4th done |
|---|---|---|---|---|
| 40 min | 0:40 | 1:20 | 2:00 | **2:40, missed** |
| 10 min | 0:10 | 0:20 | 0:30 | 0:40 |

Most of the 2 hours goes to referrals waiting in line for a free person, not to the review itself.
Cut the minutes each referral takes and the line shrinks.

### Where the minutes go, and what the tool does about each

| Time sink | What the tool does | In the prototype |
|---|---|---|
| Reading 14 to 34 pages | Page pass and rule pass, then one screen: key facts and flags, each with page and quote | Core build |
| Waiting on missing documents | Checklist pass (DOC-1 to DOC-10) in the first minutes, then a draft "Received. Please also send: ..." | Draft only. Never sent |
| Typing into CIQ | A structured record ready to copy | JSON or CSV export. No CIQ connection |
| Two reviews in a row | Intake and clinical see the same summary at the same time | UI |
| "Any update?" calls from hospitals | A status a hospital could check: received, needs info, under clinical review, accepted, denied | Mock page |
| Starting from zero | A heads-up lane: the hospital flags a likely discharge a day or two ahead | Idea. Ask staff |
| Queue order | Sort by time left. Clean referrals go to a fast lane; likely denials go straight to clinical | UI |
| Nights and thin shifts | One shared queue across sites; a summary readable on a phone | Idea |

---

## 3. The 2-hour tracker

- **The clock starts at the email's received time**, not when someone opens it.
- **Each stage gets a time budget** (placeholder; tune with IHH's numbers):

  | Stage | Done by |
  |---|---|
  | Claude reads, flags and checks documents | 0:05 |
  | Intake and clinical review, in parallel | 1:15 |
  | Hospital answers open questions | 1:30 |
  | Decision sent | 1:45, leaving a 15-minute buffer |

- **The queue is sorted by time left**, not by arrival. Green: over 60 minutes left. Yellow: 30 to
  60. Red: under 30.
- **Escalation ladder:**
  - 60 minutes left and clinical hasn't opened it: alert the on-call clinician.
  - 30 minutes left: alert the clinical lead.
  - 15 minutes left: a person tells the hospital it needs more time, and why.
- **It never auto-approves to beat the clock.** A late, correct answer beats an on-time wrong one.
- **Early warning.** With N referrals waiting and M reviewers on shift, flag which ones will miss
  before they miss.
- **Report.** Share decided within 2 hours, which stage eats the time, and the overturn count.
- Open question: does the clock pause while IHH waits on the hospital?

---

## 4. One yes: stop the overturn

- Intake and clinical review the same summary in parallel. **Only one "Accepted" goes to the
  hospital, after both have signed.**
- Two different status messages:
  - "Intake cleared. Do not discharge yet."
  - "Accepted. OK to discharge."
  Only clinical can send the second.
- Claude checks the clinical rules (`rules` and `by_system` in `admission-criteria.json`) before
  intake decides, so intake sees the likely clinical problems first.
- The form vs. chart check (`intake-context.md` section 6, step 5) is the main overturn catcher.
  Example: the form says "independent", the PT note says "needs assist".
- Every overturn reason gets logged so the checks improve. In the prototype this is a field on the
  decision.

---

## 5. The email front door (mocked)

- **Demo:** a fake inbox with invented referral emails. No real inbox. Nothing is sent.
- Each email opens a card, with the clock started from its received time. Each mock email points at
  a packet by path; packets never go in the repo.
- Follow-up emails attach to the right card. In a real pilot that needs two identifiers (name and
  date of birth), and a person confirms when the match is uncertain. In our demo the identifiers are
  blacked out, so cards match on an invented case number in the subject line.
- A reviewer claims a card, so everyone sees who owns it.
- The original email stays untouched as the record.

**Demo script:**

1. A burst of 5 referrals arrives at 2:00 PM. Run it twice on a fast-forward clock
   (1 second = 1 minute).
   - **Manual:** one reviewer, 40 minutes each (placeholder). Cards turn yellow, then red. Two miss.
   - **With the tool:** same reviewer. All five are decided in time.
2. Run one **unseen** packet live through the pipeline. Judges may hand us one.

---

## 6. Gaps we may be missing

- **The first yes works like a discharge order.** California law (HSC 1262.5, from SB 1152) makes
  hospitals log each homeless patient's post-discharge destination. If the hospital acts on
  intake's yes and clinical then says no, the patient can be left with nowhere to go.
- **The form goes stale.** It is filled out hours before transport. A new fever, a fall or IV
  medications can change the answer. Consider a short reconfirm before transport.
- **Nights and weekends.** If clinical isn't available, intake may approve alone to make the clock.
  That may be where overturns cluster. Unconfirmed.
- **The clock rewards saying yes**, if intake is measured on speed alone.
- **A denial needs a next step.** The hospital still has to discharge the patient somewhere.
  Challenge 2 (finding the right resource) is the natural hand-off.
- **Payment.** In Orange County, CalOptima auto-authorizes 30 days (`intake-context.md` section 3).
  How it works for LA and Riverside referrals is unknown.
- **Hospitals send the same referral to several providers**, so a slow answer can lose the patient
  to another provider or to the street.

---

## 7. Liability guardrails for a pilot

A design checklist, not legal advice. IHH's counsel should review it.

- **Claude never approves or denies.** It flags. A named, licensed person decides.
- **Two status messages** (section 4). Only clinical can send "Accepted".
- **Conditional acceptance wording:** "Accepted based on information received at [time]. Report
  any change before transport."
- **A written referral agreement with hospitals:** accurate form, changes reported, 30-day
  medication supply in hand (DOC-10), no discharge before "Accepted". For IHH's counsel to draft.
- **Audit log:** what came in, what Claude flagged, who decided and why, with timestamps.
- **Every flag cites a page and a quote**, checked by the verifier step. That builds trust. Letting
  the clinician check the basis for each flag is also the test FDA uses to keep clinical decision
  support software outside medical device rules.
- **Denials cite a rule ID and evidence, never a category label** such as disability, psychiatric
  history or substance use. Track denials by category to catch bias.
- **Privacy.** A real deployment needs a HIPAA-compliant setup with a business associate agreement
  (BAA) from every vendor that touches patient information, including the email system and the AI
  provider. The prototype uses only the de-identified packets and invented emails.
- **Nothing Claude writes goes to a patient without review.** California's AB 3030 adds disclaimer
  rules for AI-generated patient messages about clinical information.

---

## 8. Questions for IHH staff

**Ask these first:**

1. When intake approves, what exactly does the hospital hear? Do they start the discharge on it?
2. When clinical overturns a yes, what happens to that patient?
3. When does the 2-hour clock start, and does it pause while you wait on the hospital?

**Time and staffing**

- How many minutes does one referral take a person, start to finish? Which step is the longest?
- How many referrals come in on a busy day, and when do they cluster (time of day, day of week)?
- How many reviewers are on each shift, intake and clinical, including nights?
- How much of the 2 hours is spent waiting on the hospital for missing information?
- How many "any update?" calls do you get a day?
- When you miss 2 hours, does the hospital send the patient somewhere else?

**Workflow**

- How often does clinical overturn intake, and what are the top 3 to 5 reasons?
- Who counts as clinical (RN, NP, MD), and are they available nights and weekends?
- Is the LVN who sends the form at the hospital or at IHH?
- What happens when a patient arrives in different shape than the form described?
- Do hospitals ever give a heads-up before a referral?

**Data**

- What is CIQ? Can it export, send alerts or take data in (API, CSV, email)?
- Outlook or Gmail? One shared inbox, or one per site or county? How many people watch it,
  including overnight?
- Does the referral come as a PDF form, a scan, or typed into the email body?
- After the email, does someone retype it into CIQ?

**Payment and risk**

- How does payment authorization work for LA and Riverside referrals?
- Is there a written agreement with referring hospitals today?
- What would your compliance team need before AI touches referrals?

**Success**

- In three months, what number would tell you this worked?

---

## 9. Numbers we still need

Fill these in as staff answer. They replace every placeholder above.

| Number | Answer |
|---|---|
| Minutes one referral takes a person, start to finish, and the longest step | |
| Referrals on a busy day, and when they cluster | |
| Reviewers per shift: intake and clinical, day and night | |
| Time spent waiting on hospitals for missing documents | |
| How often clinical overturns intake | |
| What happens when 2 hours is missed | |

---

## Sources

- [IHH: recuperative care centers](https://illuminationhealthhome.org/service/housing-services/emergency-housing/recuperative-care-centers/)
- [ifhomeless.org/recup](https://www.ifhomeless.org/recup) (older IHH page; "confirmed within 30 minutes")
- [AFS Law: SB 1152 and hospitals discharging homeless patients](https://www.afslaw.com/perspectives/health-care-counsel-blog/california-increases-hospitals-obligations-when-discharging)
- [CDPH All Facilities Letter 19-01 (SB 1152)](https://calhospital.org/wp-content/uploads/2019/01/afl-19-01.pdf)
