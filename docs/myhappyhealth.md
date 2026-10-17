# Working alongside My Happy Health

Team decision, October 17: **our solution complements My Happy Health, a free AI health service
IHH supports. We do not duplicate it or compete with it.**

---

## 1. What My Happy Health is

From its public site, [myhappy.health](https://myhappy.health), checked October 17:

- A free, not-for-profit, voice-first AI health companion in about 30 languages, Spanish included.
- **For individuals.** Talk through symptoms. Upload a lab report, X-ray, CT, MRI or prescription
  and get it explained in plain language. Preventive care plans, mental-health support and
  rehabilitation guidance. There are also quick calculators for field staff (BMI, blood pressure,
  eGFR, A1C).
- IHH's CEO is quoted on the site, describing it as a 24/7 starting point for people without
  immediate access to care.
- It is educational only, not a diagnosis. **Its privacy policy says it is not a HIPAA-covered
  entity or business associate.** It sends prompts to outside AI model providers.
- We found no public developer API.

---

## 2. The split

| | My Happy Health | Our solution |
|---|---|---|
| Who uses it | The client, on their own phone | IHH staff: coordinators and the clinical line. Hospital case managers get drafts |
| Data | What a person chooses to share about themselves | Referral packets with patient information, under IHH's BAA path |
| Job | Explain health information in plain language | Decide every referral within 2 hours: rules check, missing items, hospital follow-up, handoffs |
| Languages | About 30 | English and Spanish (`docs/bilingual.md`) |
| Output | Education | Decision support. A person decides |

**Two rules follow from this:**

1. **We don't build anything that explains health information to clients.** That is My Happy
   Health's job. If the platform includes Challenge 2 (resources at discharge), health questions
   point to My Happy Health, and our tool covers shelter, work, microloans and travel home.
2. **Referral packets and patient information never go to My Happy Health.** Its policy says it is
   not a business associate, so IHH would need a BAA first. A client can choose to use it with their
   own papers. Staff never upload a client's records for them.

---

## 3. Where they meet: after a "yes"

The referral form records the patient's **preferred language**. When a referral is accepted:

- The drafted ops email to the site (`docs/workflow-and-timing.md` section 7) adds one line: "At
  intake, offer My Happy Health in [preferred language], for help understanding discharge papers
  and prescriptions."
- Site staff decide whether to offer it. The client decides whether to use it.
- **In the prototype** this is one line in a draft. There is no connection to My Happy Health, and
  nothing is sent.

Recuperative care is recovery after a hospital stay, so its rehabilitation guidance, prescription
explanations and mental-health support fit the stay itself.

---

## 4. Where they meet: staff comfort with AI

IHH wants frontline staff comfortable with AI before rolling out more tools, starting with
non-patient tasks (`docs/workflow-and-timing.md`, "Staff and AI"). My Happy Health is a free,
low-stakes example of AI that helps without replacing anyone. Training material in our platform can
point to it, using no patient information.

---

## 5. If IHH later wants a partner to read referral packets

- A BAA comes first.
- **Our packet reader is swappable.** The rule pass takes structured facts (fact, page, verbatim
  quote). Any reader that returns that JSON, ours or a partner's, feeds the same review card, the
  same verifier and the same eval on R01 to R11. So IHH could compare readers on the same packets
  and the same scoring.
- The workflow around the reader stays the same: the 2-hour clock, assignment, the follow-up chase,
  the clinical line and the handoffs. That workflow is where withdrawals are won or lost.
