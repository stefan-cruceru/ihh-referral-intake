"""Only catalog facts and fixed guidance may reach client cards or a printed plan."""

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carebridge import handout, llm, resources  # noqa: E402


POISON = {
    "en": ["Start insulin today.", "Double your insulin tonight.", "Open Monday morning.",
           "Only people over 65 qualify.", "Go to 999 Invented Street.", "Call 714-555-0199."],
    "es": ["Empiece la insulina hoy.", "Duplique la insulina esta noche.", "Abre el lunes por la mañana.",
           "Solo califican mayores de 65 años.", "Vaya a 999 Invented Street.", "Llame al 714-555-0199."],
}


def _seed():
    return next(r for r in resources.catalog() if r.get("phone") and r.get("hours")
                and not ({"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", []))))


def _pdf_text(data):
    doc = pdfium.PdfDocument(data)
    return " ".join(page.get_textpage().get_text_range() for page in doc)


def test_handout_uses_canonical_address_despite_caller_override():
    source = next(r for r in resources.catalog() if r.get("address") and r.get("phone")
                  and not ({"survivors", "domestic-violence", "confidential-location"} & set(r.get("tags", []))))
    text = _pdf_text(handout.build([{"resource_id": source["id"], "address": "999 Invented Street",
                                    "first_step": "Go to 999 Invented Street."}]))
    assert source["address"] in text
    assert "999 Invented Street" not in text


@pytest.mark.parametrize("lang", ["en", "es"])
def test_poisoned_model_cannot_supply_client_guidance_or_facts(monkeypatch, lang):
    source = _seed()
    poison = " ".join(POISON[lang])
    monkeypatch.setattr(llm, "call_json", lambda **kw: {
        "needs": ["shelter"],
        "picks": [{"resource_id": source["id"], "why": poison, "first_step": poison, "watch_out": poison},
                  {"resource_id": "invented-service", "why": poison, "first_step": poison, "watch_out": poison}],
        "plan_today": poison, "ask_staff": [poison],
    })

    got = resources.find("Needs shelter", lang=lang, use_ai=True)
    assert got["dropped"] == ["invented-service"]
    assert [c["id"] for c in got["cards"]] == [source["id"]]
    card = got["cards"][0]
    for field in ("phone", "hours", "eligibility", "source_url", "verified_date"):
        assert card[field] == source[field]
    shown = json.dumps(got, ensure_ascii=False)
    for unsafe in POISON[lang]:
        assert unsafe not in shown
    guidance = " ".join([card["why"], card["first_step"], card["watch_out"], got["plan_today"], *got["ask_staff"]])
    assert ("personal" if lang == "es" else "staff") in guidance
    assert got["plan_today"] and got["ask_staff"]
    assert ("Ask staff" if lang == "es" else "Pida al personal") not in guidance


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("style", ["color", "bw"])
def test_handout_rederives_guidance_even_for_known_id_with_forged_fields(lang, style):
    source = _seed()
    poison = " ".join(POISON[lang])
    item = {"resource_id": source["id"], "why": poison, "first_step": poison, "watch_out": poison,
            "phone": "714-555-0199", "hours": POISON[lang][2], "eligibility": POISON[lang][3]}
    text = _pdf_text(handout.build([item, {"resource_id": "invented-service", "why": poison}],
                                   plan_today=poison, lang=lang, style=style, client_name="María Example"))
    assert "María Example" in text  # The print-only name behavior is preserved.
    assert source["name"] in text and source["phone"] in text
    assert source["verified_date"] in text
    assert handout._safe(source["hours"]) in text.replace("\r\n", " ").replace("\n", " ")
    for unsafe in POISON[lang]:
        assert handout._safe(unsafe) not in text
    assert "invented-service" not in text
    assert ("personal" if lang == "es" else "staff") in text


@pytest.mark.parametrize("access,referral,en,es", [
    ("phone", False, "call", "llamar"),
    ("walk-in", False, "walk in", "sin cita"),
    ("appointment", False, "appointment", "cita"),
    ("online", False, "website", "sitio web"),
    ("mixed", False, "contact", "contactar"),
    ("unknown", False, "contact", "contactar"),
    ("phone", True, "referral", "referido"),
    ("referral-only", False, "referral", "referido"),
])
def test_offline_guidance_uses_canonical_access_and_selected_language(monkeypatch, access, referral, en, es):
    source = {**_seed(), "category": "shelter", "how_to_access": access, "referral_required": referral}
    monkeypatch.setattr(resources, "catalog", lambda: [source])
    for lang, word in (("en", en), ("es", es)):
        got = resources.find("Needs shelter", lang=lang, needs_hint=["shelter"], use_ai=False)
        card = got["cards"][0]
        assert word in card["first_step"].lower()
        assert card["phone"] == source["phone"]
        assert got["plan_today"]
