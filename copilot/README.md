# Using IHH Care Bridge from Copilot

Care Bridge works three ways. Pick the one your team uses.

## 1. GitHub Copilot in VS Code

Run this once:

```
ihh-care-bridge.exe install
```

It copies the program to your user folder, adds a Start menu shortcut, and adds Care Bridge to
VS Code's `mcp.json`. Open Copilot Chat, switch to **Agent** mode, and its tools show up.

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

Tools: check a referral packet, look up a rule, search the rules, the document checklist, find
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
IHH's BAA, and point the agent at it. The app already answers MCP requests at `POST /mcp`. That
connection is not built yet.

## Privacy

Use only de-identified or invented information until IHH has a BAA that covers the AI service.
Every message Care Bridge writes is a draft. A person checks it and sends it.
