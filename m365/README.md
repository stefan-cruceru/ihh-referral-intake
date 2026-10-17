# Hospital referral intake in IHH's Microsoft 365

A build kit for IHH's IT team. Hospitals send a referral through one web form, with the documents
uploaded in the same form. The referral then shows up on the IHH dashboard, gets read, and the
person who sent it gets an email each time its status changes. Everything runs inside IHH's own
Microsoft 365 tenant, under IHH's Microsoft Business Associate Agreement (BAA).

**This is a plan and a set of templates, not a running service.** Nothing in this repo connects
to IHH's tenant, Kipu, or any hospital, and nothing here sends email (the event rules,
`CLAUDE.md`). IHH builds it in its own tenant with the steps below, then turns it on.

## The loop

```
 Hospital case manager / social worker
        |  1. fills in the referral form and uploads the packet (no sign-in, CAPTCHA)
        v
 Power Pages form  ──────────────>  Dataverse table "Referrals"  +  packet files
                                         |
        2. Power Automate: new referral  |  case code, 2-hour clock starts, owner assigned
           - Teams alert to the on-shift coordinator
           - "We got it" email to the submitter
                                         v
 3. Copilot Studio agent (Claude) reads the packet against IHH's admission criteria
    and writes the findings back to the referral row: suggested route, missing documents,
    page-cited flags. It never decides.
                                         |
 4. The dashboard shows every referral: status, the 2-hour clock, owner, who sent it,
    and a link to the patient's Kipu record once it exists. A person decides.
                                         |
 5. Power Automate: status changed  ──>  email to the submitter in their language
    (received, being reviewed, need more documents, escalated for clinical review,
    intake cleared but don't discharge yet, accepted, not accepted, closed)
```

## Files in this kit

| File | What it is |
| --- | --- |
| [intake-form.md](intake-form.md) | The hospital form: every field, in English and Spanish, and the upload settings |
| [referrals-table.md](referrals-table.md) | The Dataverse table behind the form and the dashboard, with every column and status |
| [flows.md](flows.md) | The Power Automate flows, step by step |
| [status-messages.json](status-messages.json) | The emails the submitter gets at each step, English and Spanish |
| [copilot-agent.md](copilot-agent.md) | The Copilot Studio agent that reads packets: instructions, knowledge, output |

## What is covered by IHH's Microsoft BAA

From Microsoft's HIPAA/HITECH page (in-scope services, checked October 17, 2026):

| Piece | Listed as in scope |
| --- | --- |
| Power Apps (Power Pages sites and Dataverse are part of Power Apps) | Yes, "Power Apps cloud service" |
| Power Automate | Yes |
| SharePoint Online, OneDrive for Business | Yes |
| Exchange Online (the status emails) | Yes |
| Microsoft Teams (coordinator alerts) | Yes |
| Microsoft Forms | Yes, but see below: it can't take uploads from hospitals |
| Microsoft Copilot, Copilot Chat | Yes |
| Copilot Studio | Microsoft's Copilot Studio compliance page lists HIPAA |
| **Claude models inside Copilot Studio** | **Unknown.** Anthropic has been a Microsoft subprocessor since January 2026 and inference runs outside Azure. We found no statement that this is under the BAA. Confirm with Microsoft before any real packet goes to it. Until then, use a Microsoft-hosted model for real patients. |

Sources: [Microsoft HIPAA/HITECH offering](https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech),
[Copilot Studio compliance](https://learn.microsoft.com/power-virtual-agents/admin-certification).
A BAA covers services, not setups: IHH still sets access, retention and audit (below).

## Why Power Pages and not Microsoft Forms

Microsoft Forms only allows a file upload question when the form is limited to people inside
IHH's own organization. With "Anyone can respond" the upload question is turned off, and guest
accounts get "access denied." There is no admin setting that changes this
([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5608206/file-upload-option-is-greyed-out-when-anyone-can-r)).
Hospitals are outside IHH, so a Forms upload can't work.

A Power Pages form can be open to anyone with the link, show a CAPTCHA, and take file
attachments in the same form, stored in IHH's Dataverse
([Power Pages basic forms](https://learn.microsoft.com/power-pages/configure/basic-forms)).

**Test this first.** Anonymous uploads need table permissions for anonymous users and the newer
file upload setting. Community posts report the attach button not showing until those are right.
Build the form, then submit a test referral with invented files before sharing the link.

**If Power Pages isn't an option** (licence or IT time): a Microsoft Form without the upload
question, plus a SharePoint "Request files" link for the documents. Outsiders can upload to that
folder but can't see anything in it. It needs "Anyone with the link" sharing allowed on that one
SharePoint site. The case code joins the two.

## Setup checklist for IHH IT

1. Confirm the Microsoft BAA is signed for the tenant (it comes with the Data Protection Addendum).
2. Create a Power Platform environment just for referrals, with Dataverse.
3. Build the `Referrals` table ([referrals-table.md](referrals-table.md)).
4. Build the Power Pages site and form ([intake-form.md](intake-form.md)). Turn on CAPTCHA.
   Give anonymous users **create only** on Referrals and attachments. Never read.
5. Build the flows ([flows.md](flows.md)) with a shared intake mailbox as the sender.
6. Build the Copilot Studio agent ([copilot-agent.md](copilot-agent.md)). Pick the model only
   after the BAA question above is answered.
7. Set retention on the table and attachments to IHH's records policy. Turn on Dataverse auditing.
8. Test end to end with invented packets only (the organizers' synthetic S01 to S10 work).
9. Share the form link with hospital case managers and social workers.

## Open questions for IHH

- **Kipu link.** What does a link to a client record in Kipu look like? The dashboard shows a
  Kipu ID and opens it only once IHH gives the link format. We don't guess it.
- **Who gets status emails.** Only the person who submitted, or also a hospital team mailbox?
- **The "no" email.** Does a hospital hear "not accepted" by email, or only by phone from the
  clinical line? The template is there; IHH decides whether the flow sends it.
- **Power Pages licence.** Anonymous users on Power Pages are licensed by capacity. Check the
  current price with IHH's Microsoft partner.
- **Claude under the BAA**, as above.
