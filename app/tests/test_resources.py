"""Help for clients without an API key: typed words still find sourced resources."""

import sys
from pathlib import Path

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
