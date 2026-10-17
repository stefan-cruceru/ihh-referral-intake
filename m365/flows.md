# Power Automate flows

Four cloud flows in the referrals environment. All use Dataverse and Office 365 connectors only.
Emails go out from a shared IHH intake mailbox, so replies land with the team, not one person.
Templates come from [status-messages.json](status-messages.json); `{…}` fields come from the
referral row.

## Flow 1: New referral

**Trigger:** Dataverse, when a row is added to `Referrals`.

1. Set `case_code` = `REF-` + year + `-` + a 4-digit running number (use an autonumber column).
2. Set `deadline_at` = `received_at` + 2 hours, and `status` = `received`.
3. Pick the owner: the on-shift coordinator with the fewest open referrals (a small `Staff`
   table with name, role, shift). Set `owner`.
4. Teams: post an adaptive card to the owner and the intake channel: case code, hospital,
   deadline, a link to the dashboard row. No patient details in the card.
5. Run flow 4 (send the `received` email).

## Flow 2: Status changed

**Trigger:** Dataverse, when `status` changes on a row.

1. Set `status_changed_at` = now.
2. Map the internal status to the email (table in [referrals-table.md](referrals-table.md)).
   If there's no email for it, or it's the same as `last_email_status`, stop.
3. `denied` sends `not_accepted` only if IHH turns that branch on (open question in the README).
4. Run flow 4 with that email key.

## Flow 3: Read the packet

**Trigger:** Flow 1 finished, or a coordinator clicks "Read again" on the dashboard.

1. Set `status` = `reviewing`. Flow 2 sends the "being reviewed" email.
2. Get the row's attachments.
3. Call the Copilot Studio agent ([copilot-agent.md](copilot-agent.md)) with the files and the
   case code.
4. Write back `suggested_route`, `docs_missing` and `findings_json`.
5. If the route is `needs_info`, set `status` = `needs_info` (flow 2 sends the documents list).
   If it's `clinical_check` or `likely_no`, set that status and post a Teams alert to the
   clinical line at the same time as the coordinator. Flow 2 sends the hospital the
   "escalated for clinical review" email, the same for both, never "likely no". If it's `security_hold`, set
   `clinical_check`, alert the owner, and do not let the agent use those pages.
6. On any error, leave `status` = `reviewing` and alert the owner. A person reads it by hand.

## Flow 4: Send a status email

**Input:** row id, email key.

1. Pick the template by `submitter_lang` (default English).
2. Fill in `{case_code}`, `{submitter_name}`, `{hospital}`, `{deadline_local}`. For
   `needs_info`, `{docs_list}` = the names of `docs_missing` in that language.
3. Send from the shared intake mailbox to `submitter_email`. Subject and body from the template.
4. Set `last_email_status`.

Staff alerts (coordinator, lead, clinical line) are a separate set of drafts, documented in
[docs/notifications.md section 5](../docs/notifications.md#5-after-the-event-sending-inside-ihhs-own-microsoft-365).
In the prototype every message, to staff or to a hospital, is a draft a person sends.

**Never in an email:** the patient's name, birth date, record numbers, diagnoses, or the
reader's findings. The case code is how both sides refer to the patient.

## Chasing (optional, later)

A scheduled flow every 15 minutes: for each referral in `needs_info` with no new upload, remind
the submitter at 30 minutes and alert the owner at 60, as in `docs/workflow-and-timing.md`
section 4. New uploads from the hospital come through the same form with the case code typed in
a "Case code (if adding documents)" field, which flow 1 attaches to the existing row.

## Feeding the Care Bridge dashboard

While IHH runs the local Care Bridge app, flow 1 can also save the packet into the app's watched
inbox folder (a OneDrive or SharePoint folder synced to that PC), with the form's details next
to it as `<same name>.json`:

```json
{"case_code": "REF-2026-0412", "hospital": "…", "submitter_name": "…", "submitter_role": "…",
 "submitter_email": "…", "submitter_phone": "…", "submitter_lang": "en"}
```

Write the `.json` first, then the packet. The dashboard shows the referral under its case code,
with who sent it and how to reach them. Missing fields show as unknown.
