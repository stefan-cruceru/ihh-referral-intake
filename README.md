# Lamplight

> For IHH's referral team, nurses and case managers: one app on your own computer that reads hospital
> referrals, keeps the 2-hour clock, follows up with hospitals, and helps clients find what's next.

**Team:** Stefan Cruceru and Samantha Rubinchik
**Members:** Stefan Cruceru, Samantha Rubinchik
**Challenge:** All three, as one tool. 1 Referral intake is the core. 2 Finding the right resource
and 3 Make AI approachable are built in.
**Built at:** Orange County | Claude Impact Lab, October 17, 2026, with Illumination Health + Home
**Live demo:** https://stefan-cruceru.github.io/ihh-referral-intake/ (the video, the system map and these guides)

Lamplight follows the [In our language / En nuestro idioma](campaign/README.md) identity: a warm desk lamp, Public Sans, and people who make every decision. The program file, settings folder and tool names still say `ihh-care-bridge` (the app's old name) so nothing that is already installed breaks.

**The campaign is a draft.** The name "Lamplight", the posters and the letters in [campaign/](campaign/README.md)
are a proposal from our hackathon team. IHH has not approved them. The letters are drafts for IHH
leaders to change or throw out. They are not statements by IHH.

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
Todo está en inglés y en español, en palabras sencillas. El botón Pantalla permite un fondo
oscuro, colores para daltónicos y un modo fácil de ver con letras y botones más grandes. Si un paquete trae texto que intenta dar
órdenes a la IA, o un archivo con partes ocultas, la app aparta esas páginas y retiene el referido
para que una persona lo revise.

**Cómo usarla.** Primero hay que crear el programa: en la carpeta `app`, corra `.\build.ps1` (vea
"Try it" más abajo). Luego haga doble clic en `app\dist\ihh-care-bridge.exe`. Se abre en el
navegador. Para leer referidos, un administrador agrega la clave de la IA en Configuración.

**Conexiones apagadas.** Por defecto, la app solo se conecta al modelo de IA. Como decisión del
equipo, el código también trae una conexión con Kipu (el sistema de registros de IHH), el inicio de
sesión con Teams y un modo de producción para referidos reales. Todo viene apagado. Para usarlo,
IHH necesita el visto bueno de su equipo de TI y un BAA. Esto va más allá de la regla del evento de
hacer solo un prototipo.

## The problem

IHH's referral coordinators read 14 to 34 faxed pages per referral, by hand, against six pages of
rules, and promise hospitals an answer within 2 hours. About half of referrals end up withdrawn,
and about a quarter of all referrals go elsewhere or leave the hospital, mostly while IHH waits on a
quiet hospital. IHH told us fewer withdrawals is the number that matters most.

## What we built

One app, one closed loop, running on IHH's own machine:

1. **In.** A referral PDF lands in a watched inbox folder (fax, email or an Aidin PDF), is dragged
   in, or comes through the **hospital upload page** at `/send` (IHH's own QR-code plan). The
   2-hour clock starts from when it arrived, and the sender gets a receipt with a case code. It
   gets an owner right away, round-robin across who is on shift. A packet that comes in after
   8:30 PM is marked for the morning shift.
2. **Read.** Claude sorts the pages (type, sideways or upside down, blank, duplicate), turns them
   upright, reads them, and checks every rule in IHH's criteria by rule ID.
3. **Two gates first.** IHH has no Title 22 license, so "can take care of themselves" and "calm
   and safe" lead the screen, each with the page and the exact words.
4. **Check itself.** A second pass looks at each cited page again and checks the quote is really
   there. Then plain code drops anything unverified, forces date-based rules to "can't tell"
   (dates are blacked out), never auto-denies on the sex-offender rule, and records every change.
5. **Route.** Looks like yes / need more from the hospital / clinical line needs to look / looks
   like no. A likely no goes to the clinical line at the same time the coordinator sees it.
   **Only the clinical line can say no** (the app enforces it). The clinical reviewer works in the
   referral instead of a shared Excel sheet: notes with page numbers, a list of things to ask the
   hospital, and "my check is done". The board shows how long the clinical check takes.
6. **Chase.** One message to the case manager listing everything missing, including any
   **critical value nobody found** (for example, heart failure with no ejection fraction) and what
   the clinical reviewer asked for. Reminder at 30 minutes, a note to their boss at 60, "we need
   more time" at 15 minutes left. All drafts. Nothing is sent.
7. **Hand off.** After a yes: the Kipu fields, the census row (CSV) and the site email, drafted.
8. **Track and learn.** A local log of outcomes (accepted, denied, withdrawn and why, whether the
   patient arrived, overrides with reasons), a weekly report, and an eval script that scores the
   reader against IHH's past decisions and shows the cost per packet.

Plus:

- **Help for clients** (Challenge 2). Describe the situation; Claude picks from the sourced list in
  `challenges/2-finding-the-right-resource/data/`. Phone numbers, hours and rules on screen come
  from that list, never from Claude. Client guidance uses fixed English or Spanish templates based
  on the listed access and referral fields; generated or caller-supplied advice is not shown or
  printed. Staff must still confirm fit, availability and the source facts. Danger words bring up
  988, OC Links and 211 first.
- **A take-home PDF for the client.** One or two large-print pages, in color or black and white:
  "Your next steps / Sus próximos pasos". Each step shows what to do first, phone, address and hours
  (from the sourced list only), boxes to tick ("I called", "I went", "Done") and a notes box for
  staff to write in. The page ends with how to get there and what to bring.
  - **Client's name.** The handout is for the client, so staff can type their name to print on it.
    The name goes onto the page only: it is not saved, not logged, not sent to Claude, and not used
    in the file name.
  - **From Copilot.** Copilot can make the same PDF with the `make_client_handout` tool. It leaves
    a blank line for the name, because a Copilot chat leaves the computer.
- **Practice** (Challenge 3). Staff try it on invented examples: an LVN turns shift jottings into a
  note, and every sentence not in the jottings is marked. A coordinator asks what a rule means.
  They always see exactly what was sent and what it cost.
- **Plain language, English and Spanish.** One switch. Screens and Claude's writing aim at a
  4th-grade reading level. Quotes stay word for word.
- **First-run walkthrough.** Pick a language, pick your job, three short "how it works" and "keep
  it private" points, then it opens the right screen.
- **Display button (on every page).** Light is the default. Dark background, colorblind-safe
  colors (blue for yes, orange for no, plus ✓ ✕ ? marks so nothing depends on color), and an
  easy-to-see mode (bigger words and buttons, darker lines, no italics, nothing that moves). The
  choice is saved on that computer. There is also a "skip to the main part" link for keyboard users.
- **Copilot plugin.** The same exe is an MCP server for GitHub Copilot in VS Code and Claude
  Desktop. In Copilot Chat, pick **Lamplight** in the agent dropdown, or type `/` and pick
  a command such as `check_referral`, give it a packet file, and the whole check shows in the chat. There is also a Microsoft 365 Copilot agent package. See [copilot/README.md](copilot/README.md).
- **Kipu and Teams.** Referrals waiting in Kipu come onto the board with one click. The team's
  Kipu steps are one click each: check for a returning client, make the chart, file the packet,
  add the intake note. Each is started by a person. Staff sign in with their Teams account. The
  clinical reviewer gets a Teams card whose buttons only work for them, once, after signing in.
  The demo uses a practice Kipu and a practice sign-in. See [docs/kipu-and-teams.md](docs/kipu-and-teams.md).

**From the intake director's call** ([notes](docs/workflow-and-timing.md)): critical values are
never silent (found with the page and words, on a page to check, or not found and asked for); the
returning-client and background checks are steps a person ticks, and the tool never looks anyone up;
the receipt, reminders and "escalated" messages to the hospital carry no decision and no patient
detail, and stay drafts unless IHH agrees to send them on their own.

**Demo video:** [watch it on the demo site](https://stefan-cruceru.github.io/ihh-referral-intake/) (2 minutes, English and Spanish subtitles), or [download the MP4](demo/media/demo.mp4). System map: [docs/architecture.html](https://stefan-cruceru.github.io/ihh-referral-intake/architecture.html).

## How Claude is used

- **Built with Claude:** Claude Code wrote the app with our team, from the event repo, IHH's
  criteria and our notes from the Q&As with IHH (`docs/workflow-and-timing.md`,
  `docs/closed-loop.md`, `docs/bilingual.md`).
- **Inside the tool:** `claude-haiku-5-5` sorts pages; `claude-opus-5-5` reads pages, applies the
  rules and verifies quotes, with structured JSON output. Claude also picks client resources and
  drafts practice notes. Claude never decides; a person reads the evidence and decides.
- **What a person checks:** every flag links to its page. Every draft is a draft.
- **When a packet attacks the AI:** a packet is untrusted. `app/carebridge/guard.py` checks the
  file before it opens (real file type, size, PDF JavaScript and other active parts, hidden text),
  has the page sorter flag text written to an AI, and re-checks everything Claude writes. Pages
  that try to give orders are set aside and never read, and the referral goes on a security hold
  for a person.

## Where things are

| Folder | What it is |
|---|---|
| [`app/`](app) | The app itself: engine, server and screens (`app/carebridge`), tests, and the exe and Docker builds |
| [`demo/`](demo/README.md) | Everything for showing it: the made-up practice patients, the security test packet, the public demo site and the demo video |
| [`docs/`](docs) | How it works: the closed loop, workflow, Kipu and Teams, English and Spanish |
| [`copilot/`](copilot/README.md), [`m365/`](m365/README.md) | Copilot Chat agent and Microsoft 365 plan |
| [`campaign/`](campaign/README.md) | Draft staff rollout material (not approved by IHH) |
| [`challenges/`](challenges) | The event's criteria, resource seed data and role cards |

## Try it

Start each block from the repo root (the folder with this README).

**The exe (Windows, no install needed):**

```powershell
cd app
.\build.ps1                      # makes app\dist\ihh-care-bridge.exe
.\dist\ihh-care-bridge.exe       # opens the app in your browser
.\dist\ihh-care-bridge.exe install   # optional: Start menu + Copilot / Claude Desktop
cd ..                            # back to the repo root
```

**Try it first with practice patients (no key needed):** open the app, sign in as a made-up staff
member, and click **Practice** at the top. In the side panel, click **Practice with made-up
referrals** to fill the board, or **Practice patients** to send one of the ten made-up patients
(S01 to S10) yourself. Open any card to see each rule, the page it came from, and what is still
unknown. Every practice patient is invented, and the practice reviews come from the organizers'
answer key, so nothing leaves the computer. Real-referrals mode (`CAREBRIDGE_PRODUCTION=1`) hides
all of this. The patients live in [`demo/synthetic/`](demo/synthetic/README.md).

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
python -m pytest tests            # tests on the safety logic
cd ..                             # back to the repo root
```

**Docker (one command):** `.\start.ps1` on Windows or `./start.sh` on Mac or Linux. It builds the
container and opens http://localhost:8780 (this computer only). Add `ANTHROPIC_API_KEY` to `.env`
or in Settings to read packets. Stop with `.\start.ps1 -Stop` or `./start.sh stop`.
See [docs/run-with-docker.md](docs/run-with-docker.md).

**Packets:** download R01 to R11 into `challenges/1-referral-intake/packets/` (gitignored). Never
copy them anywhere in the repo.

**Score it:** `python app/eval_packets.py run`, then `python app/eval_packets.py score`. Run both from the repo root. The
first step never opens `challenges/1-referral-intake/eval/decisions.json`.

## What is real and what is mocked

| Part | Status |
|---|---|
| Page sort, read, rule pass, quote verifier, QC, routing | Working. Live runs need an API key |
| Two gates, bilingual flags, checklist, conflicts, questions | Working |
| Drafts (missing items, chase ladder, clinical, decision, handoffs) | Working. Templates filled from the review; never sent |
| 2-hour tracker, assignment, escalation alerts, peak warning | Working |
| Staff alerts by Outlook and Teams, per person, English or Spanish | Working: the Alerts and People tabs. Drafts in a local outbox (an Outlook `.eml`, a Teams chat link), and a person presses send. Nothing connects to Outlook or Teams. See [docs/notifications.md](docs/notifications.md) |
| Watched inbox folder | Working on a local folder. No real fax or email connection |
| Hospital upload page (`/send`) | Working as a local page with an instant receipt and status. In a pilot it would be hosted inside IHH's own Microsoft setup; how is open |
| Receipt, reminders, "escalated" to the hospital | Working, mocked: drafts by default; with the setting on they are marked "would be sent". Same texts as `m365/status-messages.json` |
| Critical values (EF, glucose, SpO2, wound, swab, dialysis chair) | Working, plain code over the review. The list is the team's starting set, not IHH policy |
| Clinical reviewer notes and turnaround | Working. Notes stay in memory; the log keeps only that a note was added |
| Overnight packets | Marked. Whether the 2 hours start on arrival or at the 7 AM shift is a setting until IHH answers |
| Client next-steps PDF | Working. Resources come only from the sourced list (Claude picks them when a key is set, otherwise matched by need) |
| Manual vs. tool comparison | Placeholder numbers (40 vs 10 minutes per referral) until IHH gives real ones |
| Outcome log and weekly report | Working, local SQLite. Practice runs are marked and can be left out |
| Client resources | Working. Sourced seed list from the event repo, checked 2026-10-13 |
| Staff practice | Working on invented examples |
| Voice notes for LVNs and MAs | Future feature, not built. Say quick jottings out loud after a visit; the same note helper turns them into a draft that points to what was said. Needs IHH's compliance review first, since it records audio about care |
| GitHub Copilot / Claude Desktop (MCP) | Working (stdio tested). Agent dropdown entry, `/` commands with pick lists, and a skill |
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
- Each page gets a read score from 0 to 100. Under 80, or no score at all, sends the page to a person,
  and a coordinator can't accept the referral until the clinical line has read it.
- The score is the AI's own guess, so each page is also read a second time, on its own. If the two reads
  don't have the same numbers, a person reads the page. Every quote with a number in it and every
  critical-value line (EF, glucose, SpO2...) is checked against the page image too. This catches a
  wrong number, not a wrong word: a misread drug name with the right dose can still get through. The
  second read about doubles the cost of reading a packet.
- The PHI guard catches patterns (dates, phone numbers, record numbers, addresses, "name:" fields).
  It does not catch a bare name typed on its own.
- The security check catches common ways of giving an AI orders, not every possible wording. The
  page sorter's own flag and the security hold are there for what the patterns miss.
- We would not trust it to decide. It points; a person decides.

## Next steps

- Run the eval on all 11 packets with IHH staff in the room, and tune the prompts on the misses.
- Get IHH's real numbers (minutes per referral, chase timings, withdrawal categories) to replace
  the placeholders.
- Pilot inside IHH's Microsoft setup: Claude through IHH's Azure under its BAA, Power Automate
  feeding the inbox folder, the engine reachable from the Microsoft 365 Copilot agent.
- A bilingual IHH staff member reviews the Spanish word list and draft templates.
- **Voice notes (future feature).** LVNs and medical assistants say their quick jottings about a visit out loud instead of typing them, and the same note helper turns them into a draft. Same rules as typed notes: no names, and the person reads every line before it goes in the chart. It needs IHH's compliance review first, and it should work alongside Kipu's transcription, which IHH is already rolling out.

## Data and privacy

This project uses only data from the event repo and public sources. It contains no real patient or
client information. By default, it does not connect to any Illumination Health + Home system.

**Built but off.** As a team choice, the repo also has code for:

- **Live Kipu** (IHH's record system), with `CAREBRIDGE_KIPU_MODE=live` (writes also need
  `CAREBRIDGE_KIPU_WRITE`), and **Teams sign-in** through Microsoft Entra ID, with
  `CAREBRIDGE_AUTH=teams`. See [docs/kipu-and-teams.md](docs/kipu-and-teams.md).
- **Production mode** for real referrals (`CAREBRIDGE_PRODUCTION=1`, in `app/carebridge/config.py`,
  added in PR #45). The production mode bullet below says what it changes.

All of these are off by default. Do not turn them on without IHH IT and a BAA. They go past the
event's "prototype only" rule in [CLAUDE.md](CLAUDE.md), which says not to connect to any IHH
system. We built them so IHH can pick them up after the event.


- Packet pages and reviews live only in the app's memory and are gone when it closes.
- The local log keeps case numbers, times, owners, routes, decisions and reasons. Never chart text.
- Typed text is checked for identifiers before it can reach the model, and blocked if it has any.
- The page sorter flags any identifier a redaction missed, and the app shows a STOP banner.
- Production mode (`CAREBRIDGE_PRODUCTION=1`, or `"production": true` in settings) is for IHH's own
  secure setup with real, named referrals. It turns off the practice tools, drops every "blacked out" note and the STOP banner for names on a page, and tells
  the model that names are expected but must stay out of facts and summaries. Referrals come in only
  by drag and drop, the watched inbox folder, email and the `/send` page. Typed text is still checked.
- Packets that try to give the AI orders, or carry active PDF content, are caught, isolated and put
  on a security hold. Executables and fake files are blocked and never opened.
- By default, the model endpoint is the only outside call. Live Kipu and Teams sign-in add calls
  to Kipu and Microsoft only if IHH turns them on. The model endpoint is one setting, so IHH can use an endpoint
  covered by its BAA.
- API keys stay in Windows Credential Manager or environment variables, never in git. In Docker, a key added in Settings goes in a file only the app can read, inside its data volume.

## License

[MIT](LICENSE)
