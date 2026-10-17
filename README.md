# IHH Care Bridge

> For IHH's referral team, nurses and case managers: one app on your own computer that reads hospital
> referrals, keeps the 2-hour clock, follows up with hospitals, and helps clients find what's next.

**Team:** _to fill in_
**Members:** _to fill in_
**Challenge:** All three, as one tool. 1 Referral intake is the core. 2 Finding the right resource
and 3 Make AI approachable are built in.
**Built at:** Orange County | Claude Impact Lab, October 17, 2026, with Illumination Health + Home

## Resumen en español

**El problema.** Los hospitales mandan referidos de 14 a 34 páginas por fax. IHH promete responder
en 2 horas. Cerca de una cuarta parte de los referidos se pierden porque la respuesta llega tarde o
el hospital deja de contestar.

**Lo que hicimos.** Una app que funciona en la computadora de IHH. Pone un reloj de 2 horas cuando
llega un referido y le da un responsable. Lee las páginas y revisa primero dos cosas: si el paciente
puede cuidarse solo y si está tranquilo y seguro. Cada punto muestra la página y las palabras
exactas, y la app vuelve a revisar cada cita. Escribe borradores para el hospital, pero nunca envía
nada. Nunca dice sí o no: una persona decide, y solo la línea clínica puede decir que no. También
ayuda a buscar recursos para clientes y deja que el personal practique con ejemplos inventados.
Todo está en inglés y en español, en palabras sencillas.

**Cómo usarla.** Haga doble clic en `ihh-care-bridge.exe`. Se abre en el navegador. Haga clic en
"Practique con referidos inventados" para practicar sin clave.

## The problem

IHH's referral coordinators read 14 to 34 faxed pages per referral, by hand, against six pages of
rules, and promise hospitals an answer within 2 hours. About half of referrals end up withdrawn,
and about a quarter of all referrals go elsewhere or leave the hospital, mostly while IHH waits on a
quiet hospital. IHH told us fewer withdrawals is the number that matters most.

## What we built

One app, one closed loop, running on IHH's own machine:

1. **In.** A referral PDF lands in a watched inbox folder (or is dragged in). The 2-hour clock
   starts from when it arrived. It gets an owner right away, round-robin across who is on shift.
2. **Read.** Claude sorts the pages (type, sideways or upside down, blank, duplicate), turns them
   upright, reads them, and checks every rule in IHH's criteria by rule ID.
3. **Two gates first.** IHH has no Title 22 license, so "can take care of themselves" and "calm
   and safe" lead the screen, each with the page and the exact words.
4. **Check itself.** A second pass looks at each cited page again and checks the quote is really
   there. Then plain code drops anything unverified, forces date-based rules to "can't tell"
   (dates are blacked out), never auto-denies on the sex-offender rule, and records every change.
5. **Route.** Looks like yes / need more from the hospital / clinical line needs to look / looks
   like no. A likely no goes to the clinical line at the same time the coordinator sees it.
   **Only the clinical line can say no** (the app enforces it).
6. **Chase.** One message to the case manager listing everything missing. Reminder at 30 minutes,
   a note to their boss at 60, "we need more time" at 15 minutes left. All drafts. Nothing is sent.
7. **Hand off.** After a yes: the Kipu fields, the census row (CSV) and the site email, drafted.
8. **Track and learn.** A local log of outcomes (accepted, denied, withdrawn and why, whether the
   patient arrived, overrides with reasons), a weekly report, and an eval script that scores the
   reader against IHH's past decisions and shows the cost per packet.

Plus:

- **Help for clients** (Challenge 2). Describe the situation; Claude picks from the sourced list in
  `challenges/2-finding-the-right-resource/data/`. Phone numbers, hours and rules on screen come
  from that list, never from Claude. Danger words bring up 988, OC Links and 211 first.
- **A take-home PDF for the client.** One click makes a large-print "Your next steps / Sus próximos
  pasos" PDF: each step with what to do first, phone, address and hours (from the sourced list
  only), boxes to tick ("I called", "I went", "Done"), how to get there, what to bring, a line for
  the staff contact and space for notes. No name is printed; there is a blank line to write a first
  name by hand. Copilot can make the same PDF with the `make_client_handout` tool.
- **Practice** (Challenge 3). Staff try it on invented examples: an LVN turns shift jottings into a
  note, and every sentence not in the jottings is marked. A coordinator asks what a rule means.
  They always see exactly what was sent and what it cost.
- **Plain language, English and Spanish.** One switch. Screens and Claude's writing aim at a
  4th-grade reading level. Quotes stay word for word.
- **First-run walkthrough.** Pick a language, pick your job, three short "how it works" and "keep
  it private" points, then it opens the right screen.
- **Copilot plugin.** The same exe is an MCP server for GitHub Copilot in VS Code and Claude
  Desktop, and there is a Microsoft 365 Copilot agent package. See [copilot/README.md](copilot/README.md).
- **Kipu and Teams.** Referrals waiting in Kipu come onto the board with one click. The team's
  Kipu steps are one click each: check for a returning client, make the chart, file the packet,
  add the intake note. Each is started by a person. Staff sign in with their Teams account. The
  clinical reviewer gets a Teams card whose buttons only work for them, once, after signing in.
  The demo uses a practice Kipu and a practice sign-in. See [docs/kipu-and-teams.md](docs/kipu-and-teams.md).

**Demo video:** _to add_

## How Claude is used

- **Built with Claude:** Claude Code wrote the app with our team, from the event repo, IHH's
  criteria and our notes from the Q&As with IHH (`docs/workflow-and-timing.md`,
  `docs/closed-loop.md`, `docs/bilingual.md`).
- **Inside the tool:** `claude-haiku-5-5` sorts pages; `claude-opus-5-5` reads pages, applies the
  rules and verifies quotes, with structured JSON output. Claude also picks client resources and
  drafts practice notes. Claude never decides; a person reads the evidence and decides.
- **What a person checks:** every flag links to its page. Every draft is a draft.

## Try it

**The exe (Windows, no install needed):**

```powershell
cd app
.\build.ps1                      # makes app\dist\ihh-care-bridge.exe
.\dist\ihh-care-bridge.exe       # opens the app in your browser
.\dist\ihh-care-bridge.exe install   # optional: Start menu + Copilot / Claude Desktop
```

Click **Practice with made-up referrals** to run the 4 PM demo with the synthetic practice
patients. No key needed. Open **Practice patients** to see each made-up patient's profile, their
faxed pages, what the app points out, the organizers' answer, and a printable next-steps PDF made
for that patient.
To read real (de-identified) packets, an admin adds a Claude API key in Settings (saved in Windows
Credential Manager) or sets `ANTHROPIC_API_KEY`. For Claude in IHH's Azure, pick Foundry in
Settings, or set `CAREBRIDGE_PROVIDER=foundry`, `ANTHROPIC_FOUNDRY_RESOURCE` and
`ANTHROPIC_FOUNDRY_API_KEY`.

**From source (Python 3.12):**

```bash
cd app
pip install -r requirements.txt
python -m carebridge              # the app
python -m carebridge mcp          # MCP server on stdio
python -m pytest tests            # tests on the safety logic and the practice patients
```

**Docker (one command):** `.\start.ps1` on Windows or `./start.sh` on Mac or Linux. It builds the
container and opens http://localhost:8780 (this computer only). Add `ANTHROPIC_API_KEY` to `.env`
or in Settings to read packets; the demo works without it. Stop with `.\start.ps1 -Stop` or `./start.sh stop`.
See [docs/run-with-docker.md](docs/run-with-docker.md).

**Packets:** download R01 to R11 into `challenges/1-referral-intake/packets/` (gitignored). The
practice demo never needs them: it uses the organizers' 10 synthetic patients in
`app/demo/synthetic/`.

**Score it:** `python app/eval_packets.py run`, then `python app/eval_packets.py score`. The
first step never opens `eval/decisions.json`.

## What is real and what is mocked

| Part | Status |
|---|---|
| Page sort, read, rule pass, quote verifier, QC, routing | Working. Live runs need an API key |
| Two gates, bilingual flags, checklist, conflicts, questions | Working |
| Drafts (missing items, chase ladder, clinical, decision, handoffs) | Working. Templates filled from the review; never sent |
| 2-hour tracker, assignment, escalation alerts, peak warning | Working |
| Staff alerts by Outlook and Teams, per person, English or Spanish | Working: the Alerts and People tabs. Drafts in a local outbox (an Outlook `.eml`, a Teams chat link), and a person presses send. Nothing connects to Outlook or Teams. See [docs/notifications.md](docs/notifications.md) |
| Watched inbox folder | Working on a local folder. No real fax or email connection |
| Monday 4 PM demo and practice patients | The organizers' 10 synthetic patients (S01-S10): invented people with realistic faxed packets. Practice reviews come from the organizers' answer key, run through the app's own checks |
| Per-patient next-steps PDF | Working. Needs come from the patient's story; resources come only from the sourced list (Claude picks them when a key is set, otherwise matched by need) |
| Manual vs. tool comparison | Placeholder numbers (40 vs 10 minutes per referral) until IHH gives real ones |
| Outcome log and weekly report | Working, local SQLite. Practice runs are marked and can be left out |
| Client resources | Working. Sourced seed list from the event repo, checked 2026-10-13 |
| Staff practice | Working on invented examples |
| GitHub Copilot / Claude Desktop (MCP) | Working (stdio tested) |
| Microsoft 365 Copilot agent | Package builds; not yet validated or uploaded in a tenant. Knows the rules, does not run the packet checker |
| Azure Foundry endpoint | Setting is there; not tested at the event |
| Kipu connector | Working against the practice Kipu (signed requests, made-up patients). Live Kipu is built but off; it needs IHH IT, a BAA and Kipu's keys. Two Kipu paths are unconfirmed (see the doc) |
| Teams sign-in and Teams approval cards | Practice sign-in working, and it is the default. Real Teams (Entra ID) sign-in is built but untested: it needs IHH IT to register the app. Cards are drafts a person posts |
| Excel census, Outlook | Not connected on purpose: copy-ready drafts only |

## Where it gets things wrong

- _To fill in from the eval run on R01 to R11._
- Rules that depend on hours (insulin under 24 h, 72 h after alcohol, COVID swab within 24 h) are
  always "can't tell", because dates are blacked out.
- Absence rules (conservatorship, aggression) are rarely written in a chart. They become questions
  for the hospital, not answers.
- Handwriting the page reader can't read is skipped, not guessed. That can miss a fact.
- The PHI guard catches patterns (dates, phone numbers, record numbers, addresses, "name:" fields).
  It does not catch a bare name typed on its own.
- We would not trust it to decide. It points; a person decides.

## Next steps

- Run the eval on all 11 packets with IHH staff in the room, and tune the prompts on the misses.
- Get IHH's real numbers (minutes per referral, chase timings, withdrawal categories) to replace
  the placeholders.
- Pilot inside IHH's Microsoft setup: Claude through IHH's Azure under its BAA, Power Automate
  feeding the inbox folder, the engine reachable from the Microsoft 365 Copilot agent.
- A bilingual IHH staff member reviews the Spanish word list and draft templates.

## Data and privacy

This project uses only data from the event repo and public sources. It contains no real patient or
client information. It does not connect to any Illumination Health + Home system.

- Packet pages and reviews live only in the app's memory and are gone when it closes.
- The local log keeps case numbers, times, owners, routes, decisions and reasons. Never chart text.
- Typed text is checked for identifiers before it can reach the model, and blocked if it has any.
- The page sorter flags any identifier a redaction missed, and the app shows a STOP banner.
- The model endpoint is the only outside call. It is one setting, so IHH can use an endpoint
  covered by its BAA.
- API keys stay in Windows Credential Manager or environment variables, never in git. In Docker, a key added in Settings goes in a file only the app can read, inside its data volume.

## License

[MIT](LICENSE)
