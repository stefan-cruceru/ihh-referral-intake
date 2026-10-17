# Using IHH Care Bridge from Copilot

Care Bridge works three ways. Pick the one your team uses.

## 1. GitHub Copilot in VS Code

Run this once:

```
ihh-care-bridge.exe install
```

It copies the program to your user folder, adds a Start menu shortcut, adds Care Bridge to
VS Code's `mcp.json`, and adds two files Copilot Chat reads:

- the **IHH Care Bridge** agent (`%APPDATA%\Code\User\prompts\ihh-care-bridge.agent.md`)
- the **ihh-referral-intake** skill (`%USERPROFILE%\.copilot\skills\ihh-referral-intake\SKILL.md`)

Both come from [`vscode/`](vscode/). Restart VS Code after you install.

### Try it

1. Open Copilot Chat (Ctrl+Alt+I) and sign in to GitHub if it asks.
2. Open the agent dropdown under the chat box and pick **IHH Care Bridge**.
3. Type `/` and pick a command. A box opens with a pick list:

| Command | What it shows in the chat |
|---|---|
| `/mcp.ihh-care-bridge.check_referral` | The full check: suggested route, the two big checks, each flag with page and quote, missing documents, questions for the hospital |
| `/mcp.ihh-care-bridge.missing_documents` | What is missing, plus a DRAFT note to the case manager |
| `/mcp.ihh-care-bridge.practice_patients` | The 10 invented practice patients |
| `/mcp.ihh-care-bridge.explain_rule` | One rule word for word, in plain words, and any known gap |
| `/mcp.ihh-care-bridge.document_checklist` | DOC-1 to DOC-10 |
| `/mcp.ihh-care-bridge.client_next_steps` | Next steps in Orange County for a client |
| `/mcp.ihh-care-bridge.client_handout` | A large-print PDF for the client |
| `/mcp.ihh-care-bridge.progress_note` | A progress note draft from shift jottings |

Or just type in plain words, for example "check S06" or "what does MOB-4 say?".

A referral that came by email works too: save it as `.eml` (in Outlook, drag it to a folder) and
give Copilot the path. The email text becomes page 1 and each attachment follows, the same as in
the app.

The practice patients (S01 to S10) answer at once and need no API key. A real packet file needs a
Claude API key: run `ihh-care-bridge.exe set-key` once.

To add it by hand, put this in `%APPDATA%\Code\User\mcp.json`:

```json
{
  "servers": {
    "ihh-care-bridge": {
      "type": "stdio",
      "command": "C:\\Users\\YOU\\AppData\\Local\\Programs\\IHH Care Bridge\\ihh-care-bridge.exe",
      "args": ["mcp"]
    }
  }
}
```

Tools: check a referral packet (or a practice patient), list the practice patients, look up a rule, search the rules, the document checklist, find
client resources, and draft a progress note.

## 2. Claude Desktop

`ihh-care-bridge.exe install` also adds it to Claude Desktop if Claude Desktop is installed. By
hand, add the same `command` and `args` under `mcpServers` in
`%APPDATA%\Claude\claude_desktop_config.json`.

## 3. Microsoft 365 Copilot

Build the package:

```
python copilot/m365/make_package.py
```

That makes `copilot/m365/build/ihh-care-bridge-m365.zip`. IT uploads it in the Teams admin
center. For a test, a user with permission can use **Apps > Manage your apps > Upload an app**
in Teams.

**What it can and can't do:** The Microsoft 365 agent knows IHH's admission rules and how to
write about them. It does **not** run Care Bridge's packet checker, because it can't reach a
program on your computer. So it has no page-by-page quote check.

**For a pilot:** run the Care Bridge engine as a web service inside IHH's Microsoft setup, under
IHH's BAA, and point the agent at it. The app already answers MCP requests at `POST /mcp`, which
needs a signed-in person's token and checks their role for each tool
(see [docs/kipu-and-teams.md](../docs/kipu-and-teams.md#sign-in)). That connection is not built yet.

## Privacy

Use only de-identified or invented information until IHH has a BAA that covers the AI service.
Every message Care Bridge writes is a draft. A person checks it and sends it.
