"""Display choices (dark, colorblind-safe, easy to see) reach every page, in both languages."""
import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "carebridge" / "web"
APP = Path(__file__).resolve().parents[1] / "carebridge"


def test_every_page_loads_display_js_in_head():
    pages = sorted(WEB.glob("*.html"))
    assert pages
    for page in pages:
        head = page.read_text(encoding="utf-8").split("</head>", 1)[0]
        assert '<script src="/static/display.js"></script>' in head, f"{page.name} must load display.js in <head>"


def test_server_rendered_pages_load_display_js():
    # The gateway's sign-in and notice pages are built in Python, not from web/*.html.
    assert "/static/display.js" in (APP / "gateway.py").read_text(encoding="utf-8")


def test_display_strings_exist_in_english_and_spanish():
    strings = json.loads((WEB / "strings.json").read_text(encoding="utf-8"))
    src = (WEB / "display.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'"((?:disp|skip)_[a-z_]+)"', src)) | {"close", "ob_display", "ob_display_btn"}
    assert {"disp_title", "disp_dark", "disp_cvd", "disp_easy", "skip_main"} <= keys
    for k in keys:
        assert strings.get(k, {}).get("en") and strings[k].get("es"), f"{k} needs en and es"


def test_light_is_the_default_and_dark_is_opt_in():
    src = (WEB / "display.js").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    assert 'theme: "light"' in src
    # Dark must never follow the computer's setting (many desk PCs run dark mode).
    assert "prefers-color-scheme" not in src + css
