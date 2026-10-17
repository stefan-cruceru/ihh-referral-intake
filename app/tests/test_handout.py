"""The client's take-home PDF: one or two pages, color and black-and-white, only sourced resources."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pypdfium2 as pdfium  # noqa: E402

from carebridge import handout, resources  # noqa: E402

LONG = "Ask staff to help you call and set it up today, and bring this paper with you when you go."


def _items(n):
    ids = [r["id"] for r in resources.catalog()][:n]
    return [{"resource_id": i, "why": LONG, "first_step": LONG, "watch_out": LONG} for i in ids]


def _pages(pdf: bytes) -> int:
    return len(pdfium.PdfDocument(pdf))


def test_never_more_than_two_pages():
    for style in ("color", "bw"):
        for lang in ("en", "es"):
            for n in range(1, 8):
                pages = _pages(handout.build(_items(n), LONG, lang, True, style))
                assert 1 <= pages <= 2, (style, lang, n, pages)


def test_only_sourced_resources_are_printed():
    pdf = handout.build([{"resource_id": "made-up-place", "why": "x", "first_step": "x", "watch_out": ""}], "", "en")
    text = pdfium.PdfDocument(pdf)[0].get_textpage().get_text_range()
    assert "Step" not in text or "made-up" not in text
    assert "Notes from staff" not in text  # no step was printed, so no notes box


def test_each_step_has_a_notes_box_in_both_styles():
    for style in ("color", "bw"):
        doc = pdfium.PdfDocument(handout.build(_items(2), "", "en", False, style))
        text = "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
        assert text.count("Notes from staff") == 2, style
