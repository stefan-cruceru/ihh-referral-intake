"""Per-user install: no admin rights needed.

Copies the exe to %LOCALAPPDATA%\\Programs\\IHH Care Bridge, adds a Start menu shortcut, and
registers the MCP server with GitHub Copilot in VS Code and with Claude Desktop when they are
installed. Existing config files are backed up before they are changed.
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
SHORTCUT = APPDATA / "Microsoft/Windows/Start Menu/Programs/IHH Care Bridge.lnk"
VSCODE_MCP = APPDATA / "Code/User/mcp.json"
CLAUDE_DESKTOP = APPDATA / "Claude/claude_desktop_config.json"


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


def install() -> int:
    if not getattr(sys, "frozen", False):
        print("install works from the built exe. From source, see the README for the MCP config.")
        return 1
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    exe = TARGET_DIR / f"{NAME}.exe"
    if Path(sys.executable).resolve() != exe.resolve():
        shutil.copy2(sys.executable, exe)
    print(f"Installed to {exe}")

    SHORTCUT.parent.mkdir(parents=True, exist_ok=True)
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{SHORTCUT}');"
          f"$s.TargetPath='{exe}';$s.WorkingDirectory='{TARGET_DIR}';$s.Description='IHH Care Bridge';$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    print("Start menu shortcut:", "added" if r.returncode == 0 else "could not be added")

    entry = {"command": str(exe), "args": ["mcp"]}
    print("GitHub Copilot (VS Code):", _edit_json(VSCODE_MCP, lambda d: d.setdefault("servers", {}).__setitem__(NAME, {"type": "stdio", **entry})))
    print("Claude Desktop:", _edit_json(CLAUDE_DESKTOP, lambda d: d.setdefault("mcpServers", {}).__setitem__(NAME, entry)))
    print("\nDone. Open IHH Care Bridge from the Start menu. In VS Code, Copilot Chat (Agent mode) now lists its tools.")
    return 0


def uninstall() -> int:
    def drop(key):
        return lambda d: d.get(key, {}).pop(NAME, None)

    if VSCODE_MCP.exists():
        _edit_json(VSCODE_MCP, drop("servers"))
    if CLAUDE_DESKTOP.exists():
        _edit_json(CLAUDE_DESKTOP, drop("mcpServers"))
    SHORTCUT.unlink(missing_ok=True)
    print(f"Unregistered. Delete {TARGET_DIR} to remove the program.")
    return 0
