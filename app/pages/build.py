"""Builds the public GitHub Pages site: python app/pages/build.py [out_dir]  (default _site/).

  index.html          the landing page: demo video, architecture, docs, campaign
  app/                the working app, run in the browser by sw.js (see README.md here)
  carebridge.zip      the Lamplight source and practice data the app reads, laid out as in the repo
  architecture.html   docs/architecture.html, the system map
  media/              docs/media: the demo video, its cover and subtitles
  docs/*.html         the repo's Markdown docs, rendered
  campaign/           the staff campaign

No packets: R01-R11 are never in git, and only the synthetic S01-S10 patients ship.
Needs `pip install markdown`.
"""

import html
import re
import shutil
import sys
import zipfile
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GITHUB = "https://github.com/stefan-cruceru/ihh-referral-intake/blob/main/"
# The code, plus every data file paths.py names with _data(..., "<repo path>"), so a new one ships too.
INCLUDE = ["app/carebridge", "app/pages/bridge.py", "challenges", "m365", "copilot"]
DATA = re.findall(r'_data\(\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)', (REPO / "app/carebridge/paths.py").read_text(encoding="utf-8"))
SKIP_DIRS = {"__pycache__", "packets"}
# Rendered docs, in the order the landing page lists them: (repo path, page name).
DOCS = [("README.md", "readme"), ("docs/closed-loop.md", "closed-loop"), ("docs/workflow-and-timing.md", "workflow-and-timing"),
        ("docs/kipu-and-teams.md", "kipu-and-teams"), ("docs/notifications.md", "notifications"), ("docs/bilingual.md", "bilingual"),
        ("copilot/README.md", "copilot"), ("m365/README.md", "m365"),
        ("docs/run-with-docker.md", "run-with-docker"),
        ("challenges/1-referral-intake/README.md", "challenge-1"), ("challenges/2-finding-the-right-resource/README.md", "challenge-2"),
        ("challenges/3-staff-ai-confidence/README.md", "challenge-3"), ("campaign/README.md", "campaign"), ("docs/glossary.md", "glossary")]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="../campaign/logo/lamplight-logo.svg">
<style>
  :root {{ --bg: #fff8f0; --panel: #fffdf9; --ink: #3b2b22; --muted: #715d50; --line: #dfd0bf; --brand: #3b2b22; --lamp: #e39235; --link: #a0461f; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.6 "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif; }}
  nav {{ max-width: 820px; margin: 0 auto; padding: 20px 16px 0; font-size: 15px; }}
  main {{ max-width: 820px; margin: 0 auto; padding: 8px 16px 64px; overflow-wrap: anywhere; }}
  a {{ color: var(--link); }}
  h1, h2, h3 {{ line-height: 1.25; }}
  table {{ border-collapse: collapse; display: block; overflow-x: auto; font-size: 15px; }}
  th, td {{ border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: var(--panel); }}
  code {{ background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; font-size: .9em; }}
  pre {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow-x: auto; }}
  pre code {{ border: 0; padding: 0; }}
  blockquote {{ border-left: 4px solid var(--lamp); margin: 0; padding: 4px 16px; color: var(--muted); }}
  .src {{ color: var(--muted); font-size: 14px; }}
</style>
</head>
<body>
<nav><a href="../">← Lamplight demo</a></nav>
<main>
{body}
<p class="src">Source: <a href="{source}">{path}</a></p>
</main>
</body>
</html>
"""


def _zip_app(out: Path) -> None:
    seen = set()
    with zipfile.ZipFile(out / "carebridge.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for rel in dict.fromkeys(INCLUDE + DATA):
            src = REPO / rel
            if not src.exists():
                raise SystemExit(f"paths.py names {rel}, which is not in the repo")
            files = [src] if src.is_file() else [p for p in src.rglob("*") if p.is_file()]
            for p in files:
                parts = p.relative_to(REPO).parts
                name = "/".join(parts)
                if SKIP_DIRS & set(parts) or p.suffix == ".pyc" or name in seen:
                    continue
                seen.add(name)
                z.write(p, name)


def _link(href: str, here: str, pages: dict) -> str:
    """A link in a doc: to another rendered doc when there is one, otherwise to the file on GitHub."""
    if re.match(r"^[a-z]+:|^#", href):
        return href
    path, _, frag = href.partition("#")
    target = (Path(here).parent / path).as_posix()
    while "/../" in f"/{target}":
        target = re.sub(r"(^|/)[^/]+/\.\./", r"\1", target, count=1)
    target = target.removeprefix("./")
    if target in pages:
        return pages[target] + ".html" + (f"#{frag}" if frag else "")
    if target == "docs/architecture.html":
        return "../architecture.html"
    return GITHUB + target + (f"#{frag}" if frag else "")


def _render_docs(out: Path) -> list[dict]:
    (out / "docs").mkdir()
    pages = {rel: name for rel, name in DOCS if (REPO / rel).is_file()}
    listed = []
    for rel, name in DOCS:
        if rel not in pages:
            continue
        text = (REPO / rel).read_text(encoding="utf-8")
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")), name)
        title = "Project overview" if rel == "README.md" else title  # its heading is just the app's name
        body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
        body = re.sub(r'href="([^"]+)"', lambda m: f'href="{html.escape(_link(html.unescape(m.group(1)), rel, pages))}"', body)
        (out / "docs" / f"{name}.html").write_text(
            PAGE.format(title=html.escape(title), body=body, source=GITHUB + rel, path=rel), encoding="utf-8")
        listed.append({"title": title, "href": f"docs/{name}.html", "path": rel})
    return listed


# Words the print file names spell in lower case.
FIX = {"lvns": "LVNs", "ihh": "IHH", "faq": "FAQ:", "someones": "someone's"}
PHRASES = {"after hours": "after-hours", "in service": "in-service", "kit go first": "kit: go first", "card in their": "card: in their"}
GROUPS = [("poster", "Posters"), ("letter", "Letters"), ("", "Handouts and cards")]
TILE = '<a class="kit" href="campaign/print/{href}"><span>{name}</span><small>{size}</small></a>'


def _print_kit() -> str:
    """The campaign's print kit as tiles: the "Print today" bundles first, then posters, letters, the rest."""
    today, groups = [], {k: [] for k, _ in GROUPS}
    for p in sorted((REPO / "campaign/print").glob("*.pdf")):
        href = html.escape(p.name.replace(" ", "%20"))
        if not re.match(r"\d+-", p.name):  # "Print today - handouts (letter, double-sided).pdf"
            name, _, size = p.stem.partition(" - ")[2].partition(" (")
            today.append(TILE.format(href=href, name=html.escape(name.capitalize()), size=html.escape(size.rstrip(")"))))
            continue
        stem = re.sub(r"^\d+-", "", p.stem)
        m = re.search(r"-(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$", stem)
        size = f"{m.group(1)} × {m.group(2)} in" if m else ""
        stem = stem[: m.start()] if m else stem
        kind = next(k for k, _ in GROUPS if not k or stem.startswith(k + "-"))
        name = " ".join(FIX.get(w, w) for w in (stem[len(kind) + 1:] if kind else stem).split("-"))
        for a, b in PHRASES.items():
            name = name.replace(a, b)
        groups[kind].append(TILE.format(href=href, name=html.escape(name[:1].upper() + name[1:]), size=size))
    out = ['<h3>Print today</h3><div class="kits today">' + "".join(today) + "</div>"] if today else []
    out += [f'<h3>{label}</h3><div class="kits">' + "".join(groups[k]) + "</div>" for k, label in GROUPS if groups[k]]
    return "\n".join(out)


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(HERE / "sw.js", out / "sw.js")
    (out / ".nojekyll").write_text("")
    _zip_app(out)
    shutil.copy2(REPO / "docs/architecture.html", out / "architecture.html")
    shutil.copytree(REPO / "docs/media", out / "media")
    shutil.copytree(REPO / "campaign", out / "campaign", ignore=shutil.ignore_patterns("README.md"))
    docs = _render_docs(out)
    items = "\n".join(f'      <li><a href="{d["href"]}">{html.escape(d["title"])}</a> <span class="path">{d["path"]}</span></li>'
                      for d in docs)
    prints = _print_kit()
    page = (HERE / "index.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(page.replace("<!--DOCS-->", items).replace("<!--PRINTS-->", prints), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "_site"))
