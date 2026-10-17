"""Practice lives in a side panel, not a top tab, and the Patients tab keeps its controls in one bar."""
import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "carebridge" / "web"
HTML = (WEB / "index.html").read_text(encoding="utf-8")
STRINGS = json.loads((WEB / "strings.json").read_text(encoding="utf-8"))


def test_practice_is_a_side_panel_not_a_tab():
    nav = HTML.split('<nav class="tabs"', 1)[1].split("</nav>", 1)[0]
    assert 'data-tab="staff"' not in nav and "profiles.html" not in nav
    assert 'id="tab-staff"' not in HTML
    panel = HTML.split('<aside id="practice"', 1)[1].split("</aside>", 1)[0]
    for el in ("jottings", "make-note", "explain-id", "explain", "start-demo"):
        assert f'id="{el}"' in panel, f"{el} should be in the practice panel"
    assert 'id="open-practice"' in HTML


def test_made_up_practice_bits_hide_in_production():
    panel = HTML.split('<aside id="practice"', 1)[1].split("</aside>", 1)[0]
    demo = panel.split('id="start-demo"', 1)[0].rsplit("<div", 1)[1]
    assert "practice-only" in demo


def test_board_controls_sit_in_one_bar():
    bar = HTML.split('<div class="board-bar">', 1)[1].split('<div id="queue"', 1)[0]
    for el in ("find-q", "find-filter", "stages", "me"):
        assert f'id="{el}"' in bar


def test_every_label_on_the_page_has_both_languages():
    for key in set(re.findall(r'data-i18n(?:-ph|-aria)?="([a-z0-9_]+)"', HTML)):
        assert STRINGS.get(key, {}).get("en") and STRINGS[key].get("es"), f"{key} needs en and es"
