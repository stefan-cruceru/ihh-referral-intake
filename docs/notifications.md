# Staff alerts by Outlook and Teams

Team decision, October 17: each IHH staff member gets alerts about the referrals they need to look
at, by Outlook email, Teams or both, in English or Spanish. **Alerts go to IHH staff only**, never to
patients or hospitals. Hospital-facing messages are the drafts in `app/carebridge/drafts.py`.

**Nothing is sent by the app.** The event rules (`CLAUDE.md`) forbid code that sends email or
messages, and the closed loop (`docs/closed-loop.md`) allows no network call except the model. So
every alert is a draft in the local outbox, and a person presses send.

---

## 1. Who gets what

| Event | When | Who | Urgency |
|---|---|---|---|
| `assigned` | A referral lands | Its owner | FYI |
| `review_ready` | Claude finished reading it (likely yes or missing items) | Owner | Soon |
| `clinical` | Likely no, or a gate that can't be settled | Clinical line and owner | Urgent |
| `lead_unopened` | Unopened with 60 min left | Lead (on shift) | Urgent |
| `clinical_repage` | Clinical line hasn't picked up in 30 min | Clinical line and lead | Urgent |
| `clock_30` | 30 min left on the 2-hour clock | Owner | Urgent |
| `more_time` | 15 min left: send the hospital the "more time" draft | Owner | Urgent |
| `chase_nudge`, `chase_supervisor` | Hospital quiet 30 / 60 min after an info request | Owner | Soon / Urgent |
| `hospital_replied` | The hospital answered | Owner | Soon |
| `handoff` | The referral moved to a new owner | New owner | Soon |
| `decided` | Accepted, denied or withdrawn | Owner and lead | FYI |

Timings come from `tracker.py` (`LADDER`), which are still placeholders until IHH gives real numbers.
Each alert is drafted once per referral, event, person and channel.

## 2. What an alert says

Case number, hospital, status, minutes left and a link that opens the referral in the app. **No
chart text, quotes, names or anything else about the patient.** Teams and inboxes are not where the
chart lives. Addresses start empty and are never guessed. A draft with no address shows "unknown: add
this person's address under People".

## 3. What a person does with a draft

- **Outlook:** download the `.eml`. It opens in Outlook as a new message ready to send (`X-Unsent`),
  with high importance when urgent.
- **Teams:** click the link. Teams opens the chat with that person, the message already typed. Or
  copy the Adaptive Card JSON.
- Mark it "sent" or "not needed". It leaves the outbox and the log keeps who did it.

## 4. API (local only, like the rest of the app)

| Route | What |
|---|---|
| `GET /api/notify/people` | Everyone on the staff list with their channel, language and addresses |
| `POST /api/notify/people` | Save one person: `name`, `role` (coordinator, lead, clinical), `email`, `teams`, `channel` (email, teams, both, none), `lang` (en, es) |
| `GET /api/notify/outbox?person=&done=0` | Drafts, most urgent first |
| `GET /api/notify/<id>.eml` | The Outlook draft |
| `GET /api/notify/<id>/card.json` | The Teams Adaptive Card |
| `POST /api/notify/<id>/mark` | `status`: `sent_by_person`, `dismissed` or `draft`, plus `who` |

## 5. After the event: sending inside IHH's own Microsoft 365

If IHH wants alerts to send themselves, the step happens **inside IHH's tenant, set up by IHH's IT**,
not in this app. For example, a Power Automate flow reads the outbox (or a folder the app writes the
`.eml` and card files to) and posts with IHH's own Outlook and Teams connectors. Unknown: whether IHH's
Microsoft BAA and policies cover automated Teams posts about referrals. Confirm with IHH first.
