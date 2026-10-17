# A closed loop IHH runs itself

Team decision, October 17: **the solution is one self-contained loop that IHH runs in its own
environment.** No partner tools and no outside services. IHH's data stays on IHH's systems, and the
model call is the only thing that leaves.

---

## 1. The loop

One app, start to finish:

1. **In.** A referral lands as a fax PDF, an email, an Aidin export, or an upload through a
   hospital upload page (IHH's own QR-code plan), in a folder or inbox the app watches. The 2-hour
   clock starts on arrival, and the sender gets a receipt.
2. **Read.** Claude reads the packet: page pass, the two gates, the rule pass, the checklist, form
   vs. chart, then the verifier (`docs/intake-context.md` section 6). Staff do the returning-client
   check and the court background check by hand; the tool only shows them as checklist items.
3. **Route.** The referral gets an owner. A likely "no" goes to the clinical reviewer at the same
   time, who works in the app instead of a shared Excel sheet (`docs/workflow-and-timing.md`
   sections 3 and 5).
4. **Chase.** Missing items are drafted to the case manager on arrival, with reminders while it is
   pending and a chase ladder if they go quiet (section 4).
5. **Decide.** A person decides. Only a clinician can deny.
6. **Hand off.** The Kipu fields, census row and ops email are drafted in one click (section 7).
7. **Track.** The outcome is logged: accepted, declined or withdrawn, the withdrawal reason, and
   whether the patient arrived.
8. **Learn.** Overrides, withdrawal reasons and missed clocks feed a weekly report and the eval
   set, so IHH can re-test the reader on its own past referrals.

Then back to step 1. No step depends on a system outside IHH.

---

## 2. What "in IHH's environment" means

- **IHH's data stays on IHH's systems.** Packets, the queue, decisions, outcomes and logs live in
  one place IHH controls: a local database file and a folder on IHH's machine or its Microsoft 365
  storage. Nothing is stored anywhere else.
- **The model is the only outside call**, and only to an endpoint IHH has under a BAA. One setting
  picks it:
  - **Claude through IHH's own Microsoft Azure** (Microsoft Foundry), billed through IHH's
    Microsoft account. The Anthropic Python SDK has a client for it (`AnthropicFoundry`). Unknown:
    whether IHH's current Microsoft BAA covers it. Confirm with IHH.
  - **Anthropic's API**, under a BAA with Anthropic.
- **No connections needed to run it.** It does not plug into Kipu, Excel, Outlook or the e-fax
  service. A person copies drafts into Outlook, the census row is a CSV, and the Kipu fields are a
  list to copy. So it can run on day one without IT work. Power Automate can feed the watched inbox
  later, inside IHH's Microsoft setup (`docs/workflow-and-timing.md` section 8).
- **The upload page has to be reachable by hospitals,** so in a pilot it would be hosted inside
  IHH's own environment, for example its Microsoft setup, not on an outside service. How is open.
  In the prototype it is a local page.
- **No partner tools or third-party services.** No outside AI tools, analytics, trackers or hosted
  databases.
- **IHH owns it.** MIT license: IHH's code, prompts, word lists and eval. IHH can change it without
  us.
- **Everything people see is in English and Spanish** (`docs/bilingual.md`).

---

## 3. Rules for the build

- **One local store** for all state (for example a SQLite file). No cloud database, no hosted
  service.
- **No network calls except the model endpoint.** Turn off Streamlit's usage statistics in
  `.streamlit/config.toml`:

  ```toml
  [browser]
  gatherUsageStats = false
  ```

- **Logs stay local.** Nothing about a referral is sent anywhere except the model call that reads
  it.
- **Only a receipt and reminders could ever send themselves,** and only if IHH agrees. They carry
  no decision and no clinical detail. In the prototype they are mocked like everything else
  (`docs/workflow-and-timing.md`, "Where sources disagree").
- **The tool never looks anyone up.** No court, CRM or registry searches. Those stay with staff.
- **The model endpoint is one setting**, read from the environment, never hard-coded. API keys stay
  in environment variables, as today.
- **The outcome log** keeps, per referral: an internal case number, arrival time, owner, decision,
  who decided, decision time, outcome (accepted, declined, withdrawn), withdrawal reason, whether
  the patient arrived, and any override with its reason. Match IHH's own outcome and
  withdrawal-reason categories once we see them.
- **The eval runs locally.** In a pilot, IHH adds its own past decided referrals to the eval set on
  its own machine. They never leave.

---

## 4. What the prototype shows today

- A mock inbox folder runs the whole loop on R01 to R11 and on one unseen packet: in, read, route,
  chase, decide, hand off, track, learn.
- The outcome log and the weekly report fill from the demo run.
- The eval scores the reader against `eval/decisions.json` in a separate script.
- The model runs through Anthropic's API with the de-identified packets only. The Foundry setting
  is shown but not tested at the event.
