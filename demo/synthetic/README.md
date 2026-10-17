# Practice patients (synthetic)

**Everything here is invented.** These are the 10 synthetic referral packets the event organizers
wrote before IHH shared its de-identified packets (event repo commit `d613aea`, MIT license). No
patient, clinician, hospital, phone number, email or record number is real. Every page carries a
footer that says so. Names and record numbers are visible on purpose, so staff can practice.

| Folder | What it is |
|---|---|
| `S01/` … `S10/` | `packet.pdf` (image-only fax, as a coordinator gets it) and `text/pNN.txt`, the exact text of each page |
| `profiles.json` | One profile per patient: made-up demographics, hospital, case manager, dates, the hospital's note, and which document is on which page |
| `answer-key.json` | The organizers' reading of each packet: decision, findings with pages, missing documents, follow-up, contradictions |
| `translations.es.json` | Bundled AI translations of the practice review wording; pending review by bilingual IHH staff |
| `__init__.py` | Turns each answer key into a practice review through the app's own `quality_control()`, quoting real lines from the page text |

Where the app uses them:

- **Practice patients page** (`/static/profiles.html`): each profile, its documents, its pages, the
  practice review, and "Put this patient on the referral board".
- **Practice with made-up referrals** (the Practice panel): the 4 PM burst is S06, S01, S09, S05 and S04 (`../inbox.json`).

The organizers' answers approve S01 to S04. The app shows those four as "need more from the
hospital", because it always treats rules that depend on a date as "can't tell" (real packets have
dates blacked out). The practice page shows the organizers' answer next to the app's route.

Practice summaries, referral reasons, findings, explanations, conflicts and questions have Spanish
translations. Evidence quotes stay exactly as written on the source page. Rule IDs, document IDs,
values, dates, page numbers and outcomes do not change with the language. Spanish summaries label
the translations as AI-generated and pending review by bilingual IHH staff before any pilot. No
external service or model call is needed to load them. When the English source wording changes,
update its translation in the same change; missing translations fail the tests instead of silently
showing English in a Spanish field.
