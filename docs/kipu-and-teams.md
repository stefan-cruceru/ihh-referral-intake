# Kipu and Teams

How Lamplight works with IHH's Kipu and signs staff in with their Teams account. Today it runs
against a **practice Kipu** with made-up patients and a **practice sign-in**. Nothing touches
IHH's real Kipu or Microsoft until IHH IT turns it on.

> **Event rule.** The event's "prototype only" rule (`CLAUDE.md`) says not to connect to any IHH
> system. Our team chose to build the live Kipu connector and Teams sign-in anyway. This goes past
> that rule. Both are off by default (`CAREBRIDGE_KIPU_MODE` and `CAREBRIDGE_AUTH`), and need IHH IT
> and a BAA before anyone turns them on. In the demo the app only talks to the practice Kipu on
> this computer.

## What it does

The intake director's steps today, and what Lamplight does for each:

| Step today | In Lamplight | Who starts it |
|---|---|---|
| A referral comes in | **Pull referrals from Kipu**: each referral waiting in Kipu becomes a card with its timer, owner and packet. Fax, email and upload still work too | A person (button) |
| Check Kipu: has this person been with IHH before? | **Check Kipu**: first name, last name and birth date must all match. A person confirms the match | A person |
| Make a chart if new | **Make chart**, from the Kipu fields the review drafted | A person |
| File the referral documents in the chart | **File packet** | A person |
| Ping the clinical reviewer on Teams | **Teams card**: a card for the reviewer's chat. Its buttons only work for that person, once, after they sign in with Teams | A person sends it |
| Record the decision | **Add intake note** after a person decides: route, gates, rule IDs, missing papers | A person |
| See who is where | Census by site from Kipu | Automatic, read only |

The tool never looks anyone up on its own, never writes to Kipu on its own, and never posts to
Teams on its own.

## Sign-in

| Mode | What happens |
|---|---|
| `practice` (default before IT sets up Microsoft) | Pick a made-up staff member. Looks like a Teams sign-in. Never calls Microsoft |
| `teams` | Sign in with the Microsoft work account people use for Teams (Microsoft Entra ID) |
| `off` | No sign-in, for a single-user laptop with no Microsoft set up |

**Once IT sets the tenant and client IDs, Microsoft sign-in is the only way in.** `practice` and
`off` are refused whatever the setting says, since practice sign-in lets anyone pick a made-up
clinician. There is no switch in the app to turn sign-in off.

**Agents and MCP.** Copilot in VS Code and Claude Desktop start Lamplight on the same computer
(stdio) and run as the Windows user who started them. An agent that calls the app over the network
(`POST /mcp`, for example a Microsoft 365 Copilot agent in a pilot) must sign in. A signed-in
person makes a personal token (`POST /api/me/token`), and the agent sends it as
`Authorization: Bearer <token>`. Each tool then follows that person's role: a packet review needs a
referral-team role. Tokens last as long as a sign-in (12 hours) and end when the app restarts.
A pilot that wants agents to sign in with Entra directly needs Entra-issued access tokens checked
against Microsoft's signing keys. Not built.

Microsoft says **who** you are. **What you may do** comes from IHH's own Microsoft Entra ID: IT
gives each person (or a security group) a Lamplight app role, and the role arrives in the sign-in
token. If IT has not set up app roles yet, IHH's staff list decides instead. Only the `clinical`
role can say no to a referral. The app checks the role on the server for every action, not the
person's name and not what the screen shows.

### Who may do what

The table lives in one place, `PERMISSIONS` in `app/carebridge/auth.py`.

| Action | Coordinator | Lead | Clinical | Admin (IT) |
|---|---|---|---|---|
| Work a referral: open, take it, request info, log replies, chase, say yes, withdrawn | ✓ | ✓ | ✓ | |
| **Say no** (deny), "I have it" for a clinical check | | | ✓ | |
| Hand a referral to someone else, record that the patient arrived, link its Kipu chart | ✓ | ✓ | | |
| Add a packet, make a Teams card | ✓ | ✓ | | |
| Run a review | ✓ | ✓ | ✓ | |
| Kipu: pull referrals, returning-client check, make a chart, file papers | ✓ | ✓ | | |
| Kipu settings, people and alert settings, app settings | | ✓ | | ✓ |
| Mark someone else's alert as sent | | ✓ | | ✓ |
| Claude API key | | | | ✓ |

Someone with two roles (for example lead and clinical) can do what either role allows. An action
that is not in the table is refused, so a new feature has to be added to it on purpose.

## Turning it on at IHH (for IT)

1. **Approvals first.** IHH compliance agrees, and a BAA covers this tool and the AI service.
2. **Kipu keys.** Ask Kipu for API access for this integration. They issue three values. Set them
   as environment variables on the machine or container (never in a file in git):
   `KIPU_ACCESS_ID`, `KIPU_SECRET_KEY`, `KIPU_APP_ID`. Optional: `KIPU_BASE_URL`.
3. **Confirm with Kipu** the items marked UNCONFIRMED in `app/carebridge/kipu.py`:
   - which status IHH uses for a referral that isn't admitted yet,
   - how to attach a document to an existing chart.
   Public Kipu clients don't show these.
4. **Teams sign-in.** In Entra ID, register an app named Lamplight ("mobile and desktop", redirect
   `http://localhost:<port>/auth/callback` or the pilot's own address). Then set
   `CAREBRIDGE_TEAMS_TENANT` and `CAREBRIDGE_TEAMS_CLIENT_ID`, and `CAREBRIDGE_AUTH=teams`.
5. **Roles in Entra (recommended).** In the app registration, open **App roles** and create four,
   allowed for **Users/Groups**, with these exact values:
   `CareBridge.Coordinator`, `CareBridge.Lead`, `CareBridge.Clinical`, `CareBridge.Admin`.
   These keep the app's old name on purpose: the app looks for these exact words.
   Then in **Enterprise applications → Lamplight → Users and groups**, assign people or security
   groups to a role. Turn on **Assignment required** so only assigned staff can sign in.
   - The `roles` claim only appears in the token after someone is assigned a role. Someone who
     signs in with no Lamplight role is refused.
   - Assigning a whole group may need an Entra ID P1 or P2 licence. Confirm with IHH IT.
   - Changing someone's role in Entra takes effect at their next sign-in (sessions last 12 hours).
6. **Staff list (only without app roles).** Put IHH's list in `staff.json` in the app's settings folder:
   `[{"email": "...", "name": "...", "role": "coordinator|lead|clinical|admin"}]`.
7. **Turn on Kipu.** A lead picks **IHH's live Kipu** on the Kipu and Teams page. Writing stays
   off until they tick "Allow writing to Kipu".

## What we know and don't know about Kipu's API

We used Kipu's public client libraries, not Kipu's own documentation:

- Requests are signed (HMAC-SHA1, "APIAuth") and the app ID goes in the query string.
- The paths are `/api/patients/census`, `/api/patients/latest`, `/api/patients/{id}`,
  `/api/patients/{id}/care_team`, `POST /api/patients` and `POST /api/patients/{id}/patient_evaluations`.

The practice Kipu checks signatures the same way, so a wrong key fails there too. Check everything
against Kipu's documentation before a pilot.

## Kipu readiness, checked in the background

Every few seconds, `kipu_check.py` builds what each Kipu step would send for every referral on
the board (the chart, the packet, the intake note) and checks it against what Kipu needs:

- **Chart:** referral number, referring hospital and contact known, reason for referral filled
  in, the returning-client check done, no chart linked yet. Name and birth date are blacked out
  in every packet; the person making the chart types them in Kipu.
- **Packet:** on file, really a PDF or image (by its first bytes) within the security scan's size
  limit, and the security scan passed.
- **Intake note:** the packet was read, a person decided, only the clinical line said no, and the
  note carries rule IDs and pages only.

Each referral is **ready**, **waiting on a person**, or **to fix**. It shows as a chip on the board,
a checklist in the open referral, and a table with a log on the Kipu and Teams page. In practice
mode it also sends one signed, read-only request to the practice Kipu to show the signed connection
works. It never writes, and it never calls live Kipu: every write is still one click by a person.
