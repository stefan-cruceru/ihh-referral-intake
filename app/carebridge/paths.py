"""Where bundled data lives, in a source checkout and inside the frozen exe.

The event repo files stay the single source of truth: the exe bundles them at build time
instead of keeping copies in the app folder.
"""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BUNDLE = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    REPO = None
else:
    BUNDLE = Path(__file__).resolve().parent
    REPO = BUNDLE.parent.parent

WEB_DIR = BUNDLE / "web" if FROZEN else BUNDLE / "web"


def _data(rel_in_bundle: str, rel_in_repo: str) -> Path:
    if FROZEN:
        return BUNDLE / "data" / rel_in_bundle
    return REPO / rel_in_repo


CRITERIA = _data("admission-criteria.json", "challenges/1-referral-intake/criteria/admission-criteria.json")
RESOURCES = _data("oc-resources.seed.json", "challenges/2-finding-the-right-resource/data/oc-resources.seed.json")
SCENARIOS = _data("client-scenarios.json", "challenges/2-finding-the-right-resource/scenarios/client-scenarios.json")
DEMO_DIR = _data("demo", "app/demo")
# The Copilot Chat agent (the "IHH Care Bridge" choice in the agent dropdown) and its skill.
COPILOT_DIR = _data("copilot", "copilot/vscode")


def packets_dir() -> Path | None:
    """Folder with de-identified packets, read by path only. Never bundled into the exe."""
    env = os.environ.get("CAREBRIDGE_PACKETS")
    if env:
        return Path(env)
    if REPO is not None:
        p = REPO / "challenges/1-referral-intake/packets"
        return p if p.exists() else None
    return None


def user_dir() -> Path:
    """Per-user settings folder. Holds settings only: never packet pages or patient text."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    p = Path(base) / "IHH-Care-Bridge"
    p.mkdir(parents=True, exist_ok=True)
    return p


@lru_cache(maxsize=None)
def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
