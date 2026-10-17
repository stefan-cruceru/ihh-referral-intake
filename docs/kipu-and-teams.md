# Kipu and Teams

How Care Bridge works with IHH's Kipu and signs staff in with their Teams account. Today it runs
against a **practice Kipu** with made-up patients and a **practice sign-in**. Nothing touches
IHH's real Kipu or Microsoft until IHH IT turns it on.

> **Event rule.** The event says not to connect to any IHH system. Our user chose to build the
> connector anyway, switched off, so IHH can turn it on after the event. In the demo it only talks
> to the practice Kipu on this computer.

## What it does

The intake director's steps today, and what Care Bridge does for each:

| Step today | In Care Bridge | Who starts it |
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
| `practice` (default) | Pick a made-up staff member. Looks like a Teams sign-in. Never calls Microsoft |
| `teams` | Sign in with the Microsoft work account people use for Teams (Microsoft Entra ID) |
| `off` | No sign-in, for a single-user laptop |

Microsoft says **who** you are. IHH's staff list says **what you may do**. Only the `clinical`
role can say no to a referral. The app checks this, not the person's name.

## Turning it on at IHH (for IT)

1. **Approvals first.** IHH compliance agrees, and a BAA covers this tool and the AI service.
2. **Kipu keys.** Ask Kipu for API access for this integration. They issue three values. Set them
   as environment variables on the machine or container (never in a file in git):
   `KIPU_ACCESS_ID`, `KIPU_SECRET_KEY`, `KIPU_APP_ID`. Optional: `KIPU_BASE_URL`.
3. **Confirm with Kipu** the items marked UNCONFIRMED in `app/carebridge/kipu.py`:
   - which status IHH uses for a referral that isn't admitted yet,
   - how to attach a document to an existing chart.
   Public Kipu clients don't show these.
4. **Teams sign-in.** In Entra ID, register an app ("mobile and desktop", redirect
   `http://localhost:<port>/auth/callback` or the pilot's own address). Then set
   `CAREBRIDGE_TEAMS_TENANT` and `CAREBRIDGE_TEAMS_CLIENT_ID`, and `CAREBRIDGE_AUTH=teams`.
5. **Staff list.** Put IHH's list in `staff.json` in the app's settings folder:
   `[{"email": "...", "name": "...", "role": "coordinator|lead|clinical|admin"}]`.
6. **Turn on Kipu.** A lead picks **IHH's live Kipu** on the Kipu and Teams page. Writing stays
   off until they tick "Allow writing to Kipu".

## What we know and don't know about Kipu's API

We used Kipu's public client libraries, not Kipu's own documentation:

- Requests are signed (HMAC-SHA1, "APIAuth") and the app ID goes in the query string.
- The paths are `/api/patients/census`, `/api/patients/latest`, `/api/patients/{id}`,
  `/api/patients/{id}/care_team`, `POST /api/patients` and `POST /api/patients/{id}/patient_evaluations`.

The practice Kipu checks signatures the same way, so a wrong key fails there too. Check everything
against Kipu's documentation before a pilot.
