"""Help for clients without an API key: typed words still find sourced resources."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carebridge import resources  # noqa: E402


def test_typed_situation_finds_resources_without_a_key():
    got = resources.find("Unhoused, needs shelter and food after discharge", "en", None, use_ai=False)
    assert {"shelter", "food"} <= set(got["needs"])
    assert got["cards"]


def test_spanish_words_count_too():
    assert {"shelter", "food"} <= set(resources.needs_from_text("Está sin hogar y no tiene comida"))


def test_care_is_not_a_car():
    assert "shelter" not in resources.needs_from_text("Needs recuperative care after surgery")


def test_staff_picked_needs_win():
    got = resources.find("Unhoused, needs shelter", "en", ["transportation"], use_ai=False)
    assert got["needs"] == ["transportation"]


@pytest.mark.parametrize("situation,need", [
    ("I need a job after discharge", "employment"),
    ("Necesito trabajo", "employment"),
    ("Help getting home to family", "family-reunification-travel"),
    ("Necesito regresar a casa con mi familia", "family-reunification-travel"),
    ("Need a small loan for my business", "microenterprise"),
    ("Necesito un microcrédito para mi negocio", "microenterprise"),
])
def test_core_discharge_needs_find_sourced_resources_offline(situation, need):
    got = resources.find(situation, needs_hint=None, use_ai=False)
    assert need in got["needs"]
    assert got["cards"], (situation, need)
    assert any(card["category"] == need or need in next(r for r in resources.catalog() if r["id"] == card["id"]).get("tags", [])
               for card in got["cards"])


def test_business_and_paperwork_do_not_match_short_words():
    assert "transportation" not in resources.needs_from_text("Need a small loan for my business")
    assert "employment" not in resources.needs_from_text("Help with hospital paperwork")
    assert "transportation" in resources.needs_from_text("I need the bus.")
    assert "transportation" in resources.needs_from_text("Bus-pass needed")
