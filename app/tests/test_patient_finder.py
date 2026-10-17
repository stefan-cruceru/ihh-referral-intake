"""The Patients tab can be searched and filtered, and each card says which step the patient is on."""
import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "carebridge" / "web"


def test_search_and_filter_are_on_the_patients_tab():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    tab = html.split('id="tab-referrals"', 1)[1].split("</section>", 1)[0]
    assert 'id="find-q"' in tab and 'type="search"' in tab
    assert 'id="find-filter"' in tab


def test_every_filter_option_has_a_rule_and_both_languages():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    strings = json.loads((WEB / "strings.json").read_text(encoding="utf-8"))
    rules = js.split("const FILTERS = {", 1)[1].split("};", 1)[0]
    options = re.findall(r'<option value="([a-z_]+)" data-i18n="filter_\1">', html)
    assert {"all", "open", "late", "safety"} <= set(options)
    for v in options:
        assert re.search(rf"\b{v}:", rules), f"filter {v} has no rule in app.js"
    keys = {k for k in strings if k.startswith(("find_", "filter_"))} | {"where_step"}
    for k in keys:
        assert strings[k].get("en") and strings[k].get("es"), f"{k} needs en and es"


def test_cards_show_where_the_patient_is():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "${whereLine(c)}" in js
    assert "mine.filter(matches)" in js
