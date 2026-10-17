"""Settings and the Claude API key.

The key is asked for once and kept in Windows Credential Manager (via keyring), never in the
exe, the repo or a plain file. ANTHROPIC_API_KEY in the environment wins when set.
"""

import json
import os

from .paths import user_dir

SERVICE = "ihh-care-bridge"
KEY_NAME = "anthropic-api-key"

DEFAULT_MODEL = "claude-opus-5-5"
# Page sorting (type, rotation, blank) is a light task; it runs on the fast model so the
# careful reading pass gets upright, sorted pages sooner.
DEFAULT_FAST_MODEL = "claude-haiku-5-5"


def _settings_path():
    return user_dir() / "settings.json"


def load_settings() -> dict:
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(updates: dict) -> dict:
    s = load_settings()
    s.update(updates)
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    return s


def model() -> str:
    return os.environ.get("CAREBRIDGE_MODEL") or load_settings().get("model") or DEFAULT_MODEL


def fast_model() -> str:
    return os.environ.get("CAREBRIDGE_FAST_MODEL") or load_settings().get("fast_model") or DEFAULT_FAST_MODEL


def provider() -> str:
    """'anthropic' (default) or 'foundry' (Claude in IHH's Microsoft Azure)."""
    p = os.environ.get("CAREBRIDGE_PROVIDER") or load_settings().get("provider") or "anthropic"
    return p if p in ("anthropic", "foundry") else "anthropic"


def foundry_resource() -> str | None:
    return os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE") or load_settings().get("foundry_resource")


def inbox_dir() -> str | None:
    """Folder the app watches for new referral PDFs (fax or email attachments saved there)."""
    return os.environ.get("CAREBRIDGE_INBOX") or load_settings().get("inbox_dir")


def get_api_key() -> str | None:
    env = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") if provider() == "foundry" else None
    if env:
        return env
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    try:
        import keyring

        return keyring.get_password(SERVICE, KEY_NAME)
    except Exception:
        return None


def set_api_key(key: str) -> None:
    import keyring

    keyring.set_password(SERVICE, KEY_NAME, key.strip())


def clear_api_key() -> None:
    try:
        import keyring

        keyring.delete_password(SERVICE, KEY_NAME)
    except Exception:
        pass
