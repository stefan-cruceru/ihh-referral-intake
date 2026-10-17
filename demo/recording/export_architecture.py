"""Export the canonical architecture map as one offline HTML file with licensed assets."""
from pathlib import Path
import argparse
import base64
import html

REPO = Path(__file__).resolve().parents[2]


def export(output: Path) -> None:
    output = output.resolve()
    if output.is_relative_to(REPO):
        raise ValueError("Write generated exports to session scratch or the requested delivery folder.")
    source = (REPO / "docs/architecture.html").read_text(encoding="utf-8")
    assets = {
        "../app/carebridge/web/fonts/PublicSans-Variable.ttf":
            ("font/ttf", REPO / "app/carebridge/web/fonts/PublicSans-Variable.ttf"),
        "../campaign/logo/lamplight-logo.svg":
            ("image/svg+xml", REPO / "campaign/logo/lamplight-logo.svg"),
    }
    for reference, (mime, path) in assets.items():
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        embedded = f"data:{mime};base64,{encoded}"
        if reference in source:
            source = source.replace(reference, embedded)
        elif embedded not in source:
            raise ValueError(f"Canonical asset reference changed: {reference}")
    if 'data-license="Public Sans SIL Open Font License"' not in source:
        license_text = (REPO / "app/carebridge/web/fonts/OFL.txt").read_text(encoding="utf-8")
        source += '\n<pre hidden data-license="Public Sans SIL Open Font License">' + html.escape(license_text) + "</pre>\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output)
