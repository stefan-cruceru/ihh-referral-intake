"""Per-user install: no admin rights needed.

Copies the exe to %LOCALAPPDATA%\\Programs\\IHH Care Bridge, adds a "Lamplight" Start menu shortcut, and
registers the MCP server with GitHub Copilot in VS Code and with Claude Desktop when they are
installed. For Copilot it also adds the "Lamplight" agent (it shows in Copilot Chat's agent
dropdown) and the ihh-referral-intake skill. Existing config files are backed up before they are
changed.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

NAME = "ihh-care-bridge"
APPDATA = Path(os.environ.get("APPDATA", Path.home()))
LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home()))
TARGET_DIR = LOCAL / "Programs" / "IHH Care Bridge"
SHORTCUT = APPDATA / "Microsoft/Windows/Start Menu/Programs/Lamplight.lnk"
# Before the rename to Lamplight. Install and uninstall remove it so nobody sees two shortcuts.
OLD_SHORTCUT = APPDATA / "Microsoft/Windows/Start Menu/Programs/IHH Care Bridge.lnk"
VSCODE_MCP = APPDATA / "Code/User/mcp.json"
CLAUDE_DESKTOP = APPDATA / "Claude/claude_desktop_config.json"
VSCODE_AGENT = APPDATA / "Code/User/prompts/ihh-care-bridge.agent.md"
COPILOT_SKILL = Path.home() / ".copilot/skills/ihh-referral-intake"


def _edit_json(path: Path, update) -> str:
    if not path.parent.exists():
        return "skipped (not installed)"
    data = {}
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError:
            return f"skipped ({path.name} is not plain JSON; add it by hand, see the README)"
    update(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return "registered"


def install_copilot_files() -> str:
    """The agent and the skill: plain files Copilot Chat reads from the user's folders."""
    from .paths import COPILOT_DIR

    if not VSCODE_AGENT.parent.parent.exists():
        return "skipped (VS Code not installed)"
    VSCODE_AGENT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(COPILOT_DIR / VSCODE_AGENT.name, VSCODE_AGENT)
    COPILOT_SKILL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(COPILOT_DIR / "skills" / COPILOT_SKILL.name / "SKILL.md", COPILOT_SKILL / "SKILL.md")
    return "added (pick Lamplight in Copilot Chat's agent dropdown)"


def install() -> int:
    print("Prototype from a one-day event. Do not install at IHH without IHH IT and compliance sign-off.\n")
    if not getattr(sys, "frozen", False):
        print("install works from the built exe. From source, see the README for the MCP config.")
        return 1
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    exe = TARGET_DIR / f"{NAME}.exe"
    if Path(sys.executable).resolve() != exe.resolve():
        shutil.copy2(sys.executable, exe)
    print(f"Installed to {exe}")

    SHORTCUT.parent.mkdir(parents=True, exist_ok=True)
    OLD_SHORTCUT.unlink(missing_ok=True)
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{SHORTCUT}');"
          f"$s.TargetPath='{exe}';$s.WorkingDirectory='{TARGET_DIR}';$s.Description='Lamplight';$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    print("Start menu shortcut:", "added" if r.returncode == 0 else "could not be added")

    entry = {"command": str(exe), "args": ["mcp"]}
    print("GitHub Copilot (VS Code):", _edit_json(VSCODE_MCP, lambda d: d.setdefault("servers", {}).__setitem__(NAME, {"type": "stdio", **entry})))
    print("Copilot agent and skill:", install_copilot_files())
    print("Claude Desktop:", _edit_json(CLAUDE_DESKTOP, lambda d: d.setdefault("mcpServers", {}).__setitem__(NAME, entry)))
    print("\nDone. Open Lamplight from the Start menu. In VS Code, open Copilot Chat and pick\n"
          "Lamplight in the agent dropdown, or type / to see its commands.")
    return 0


def uninstall() -> int:
    def drop(key):
        return lambda d: d.get(key, {}).pop(NAME, None)

    if VSCODE_MCP.exists():
        _edit_json(VSCODE_MCP, drop("servers"))
    if CLAUDE_DESKTOP.exists():
        _edit_json(CLAUDE_DESKTOP, drop("mcpServers"))
    VSCODE_AGENT.unlink(missing_ok=True)
    shutil.rmtree(COPILOT_SKILL, ignore_errors=True)
    SHORTCUT.unlink(missing_ok=True)
    OLD_SHORTCUT.unlink(missing_ok=True)
    print(f"Unregistered. Delete {TARGET_DIR} to remove the program.")
    return 0
