# The `Referrals` table (Dataverse)

One row per referral. The form creates it, the flows and the Copilot agent fill it in, and the
dashboard reads it. Patient pages stay as attachments on the row; columns hold contact details,
times, status and the reader's findings.

## Columns

| Column | Type | Set by | Notes |
| --- | --- | --- | --- |
| `case_code` | Text, unique | Flow 1 | e.g. `REF-2026-0412`. The only ID used in emails |
| `received_at` | Date/time | Form (created on) | The 2-hour clock starts here |
| `deadline_at` | Date/time | Flow 1 | `received_at` + 2 hours |
| `submitter_name`, `submitter_role`, `submitter_email`, `submitter_phone`, `submitter_lang` | Text / choice | Form | Who gets the status emails |
| `hospital`, `hospital_unit` | Choice / text | Form | |
| `expected_discharge` | Date/time | Form | Blank = not known yet |
| `reason_short`, `insurance` | Text / choice | Form | |
| `screen_m1` … `screen_m6` | Choice: yes, no, not_sure | Form | Rule IDs FORM-M1 to FORM-M6 |
| `docs_claimed` | Multi-choice DOC-1 … DOC-10 | Form | What the sender says they uploaded |
| `owner` | User | Flow 1, then people | Round-robin among on-shift coordinators |
| `status` | Choice, below | People and flows | Internal status. Drives the dashboard |
| `status_changed_at` | Date/time | Flow 2 | |
| `suggested_route` | Choice: likely_yes, needs_info, clinical_check, likely_no, security_hold | Copilot agent | A suggestion. Never a decision |
| `docs_missing` | Multi-choice DOC-1 … DOC-10 | Copilot agent, then people | What the reader didn't find in the pages |
| `findings_json` | Multiline text | Copilot agent | Flags with page numbers and quotes (format in [copilot-agent.md](copilot-agent.md)) |
| `decided_by`, `decided_at` | User / date-time | People | Only the clinical line can set `denied` |
| `withdraw_reason` | Choice: left_ama, other_facility, someones_home, hospital_couldnt_wait, no_reply, other | People | Same reasons as the app |
| `kipu_id` | Text | People | Filled after the client is created in Kipu. The dashboard links to it |
| `last_email_status` | Choice (same as status) | Flow 2 | Stops the same email going out twice |

## Status: what IHH sees, and what the hospital hears

The internal statuses are the app's (`app/carebridge/tracker.py`). The hospital gets fewer and
plainer ones, matching what IHH said it already tells hospitals (`docs/workflow-and-timing.md`):
an automatic receipt, "escalated for review and may be denied" while the clinical line looks,
and two steps for a yes ("Intake cleared. Do not discharge yet." then "Accepted. OK to
discharge."). The reader's suggestion alone never sends anything: a person sets the status.

| Internal status | Dashboard (EN / ES) | Email the submitter gets |
| --- | --- | --- |
| `received` | New / Nuevo | `received` |
| `reviewing` | Being checked / En revisión | `reviewing` |
| `needs_info` | Need more from hospital / Falta información | `needs_info` (lists `docs_missing`) |
| `clinical_check` | Clinical line checks / Revisa la línea clínica | `escalated` |
| `likely_no` | Maybe no: clinical line checks / Tal vez no | `escalated` (same email: it never says "likely no") |
| `intake_cleared` | Intake OK. Don't send the patient yet / Admisión OK | `intake_cleared` |
| `accepted` | Yes. OK to send the patient / Sí | `accepted` |
| `denied` | No | `not_accepted` (only if IHH turns it on; see README) |
| `withdrawn` | Lost / Perdido | `closed` |

## Stages: how the dashboard groups patients

Every status belongs to one stage. The dashboard shows one column per stage, oldest deadline on
top, and IHH builds one Dataverse view per stage so the same groups show in Power Apps too.
`patient_arrived` (yes/no) moves an accepted patient to "Arrived".

| Stage (EN / ES) | Statuses in it | What has to happen next |
| --- | --- | --- |
| 1. New / Nuevos | `received` | Assign and start reading |
| 2. Being read / En lectura | `reviewing` | Coordinator reads the findings |
| 3. Waiting on hospital / Esperando al hospital | `needs_info` | Hospital sends the missing documents |
| 4. Clinical review / Revisión clínica | `clinical_check`, `likely_no` | Clinical line decides |
| 5. Cleared, not final / Aprobado, no final | `intake_cleared` | Final yes from the clinical line |
| 6. Accepted, on the way / Aceptado, en camino | `accepted`, `patient_arrived` = no | Patient arrives |
| 7. Arrived / Llegó | `accepted`, `patient_arrived` = yes | Create the client in Kipu, add `kipu_id` |
| 8. Closed / Cerrados | `denied`, `withdrawn` | Nothing. Kept for the weekly report |

Add a `patient_arrived` column (yes/no, set by people) and a calculated `stage` column (choice,
the table above) so views and Power BI can group on it.

## Security

- Anonymous web role: Create only. Coordinators: read and update. Clinical line: the only role
  that can set `denied`.
- Turn on auditing for the table and its attachments.
- Retention on rows and attachments follows IHH's records policy.
