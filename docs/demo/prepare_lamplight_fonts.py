"""Prepare Public Sans for browser artwork and offline Pillow/libass rendering.

The canonical application variable font remains untouched.  Its default axis is
100 (Thin), so create explicit 400/700 static faces for the video compositor.
"""
from pathlib import Path
import argparse

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def prepare(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for weight, style, filename in (
        (400, "Regular", "lamplight-public-sans.ttf"),
        (700, "Bold", "lamplight-public-sans-bold.ttf"),
    ):
        font = instantiateVariableFont(TTFont(source), {"wght": weight}, inplace=True)
        names = {1: "Public Sans", 2: style, 4: f"Public Sans {style}",
                 6: f"PublicSans-{style}", 16: "Public Sans", 17: style}
        for name_id, value in names.items():
            font["name"].removeNames(nameID=name_id)
            font["name"].setName(value, name_id, 3, 1, 0x409)
        font["OS/2"].usWeightClass = weight
        font["OS/2"].fsSelection &= ~((1 << 5) | (1 << 6))
        font["OS/2"].fsSelection |= (1 << 5) if weight >= 700 else (1 << 6)
        font["head"].macStyle = 1 if weight >= 700 else 0
        target = destination / filename
        font.save(target)
        print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?",
                        default=Path(__file__).resolve().parents[2] / "app/carebridge/web/fonts/PublicSans-Variable.ttf")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.destination)
