"""Score the reader against IHH's real decisions, and log what each packet cost.

Two steps on purpose, so the reviewer never sees the answers:
  1. python eval_packets.py run [R01 R02 ...]   reviews each packet; never opens decisions.json
  2. python eval_packets.py score               only now reads eval/decisions.json and compares

Results go to app/eval-results/ (gitignored). They hold routes, rule IDs and costs, never page
text or quotes, so nothing from a packet lands in git.
"""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OUT = HERE / "eval-results"
DECISIONS = HERE.parent / "challenges/1-referral-intake/eval/decisions.json"


def run(ids: list[str]):
    from carebridge import intake
    from carebridge.paths import packets_dir

    d = packets_dir()
    if not d:
        sys.exit("No packets folder. Download R01-R11 into challenges/1-referral-intake/packets/.")
    OUT.mkdir(exist_ok=True)
    files = [d / f"{i}.pdf" for i in ids] if ids else sorted(d.glob("R*.pdf"))
    for f in files:
        t0 = time.time()
        try:
            review = intake.review_file(f.read_bytes(), f.name)
            rep = intake.run(review)
        except Exception as e:
            print(f"{f.stem}: failed: {e}")
            continue
        slim = {
            "packet": f.stem, "seconds": round(time.time() - t0), "route": rep["recommendation"],
            "gates": {g: v["status"] for g, v in rep["gates"].items()},
            "not_met": [r["rule_id"] for r in rep["rules"] if r["status"] == "not_met"],
            "missing_docs": [c["doc_id"] for c in rep["checklist"] if c["status"] == "missing"],
            "ineligible_dx": [x["rule_id"] for x in rep["diagnoses"] if x["ineligible"]],
            "qc": rep["qc"], "cost": rep["cost"], "phi_pages": rep["flags"]["phi_pages"],
        }
        (OUT / f"{f.stem}.json").write_text(json.dumps(slim, indent=1))
        print(f"{f.stem}: {slim['route']['code']:15} gates {slim['gates']}  ${slim['cost']['usd']:.2f}  {slim['seconds']}s")


def _decision(v) -> str:
    s = json.dumps(v).lower()
    return "approved" if "approv" in s or "accept" in s else "denied" if "den" in s or "declin" in s else "unknown"


def score():
    truth_raw = json.loads(DECISIONS.read_text(encoding="utf-8"))["packets"]
    truth = {k: _decision(v) for k, v in truth_raw.items()} if isinstance(truth_raw, dict) else \
        {p.get("packet") or p.get("id"): _decision(p) for p in truth_raw}
    rows = []
    for f in sorted(OUT.glob("R*.json")):
        r = json.loads(f.read_text())
        code = r["route"]["code"]
        said = "denied" if code == "likely_no" else "approved" if code in ("likely_yes", "needs_info") else "clinical"
        rows.append((r["packet"], truth.get(r["packet"], "unknown"), code, said, r["cost"]["usd"]))
    print(f"{'packet':7} {'IHH':9} {'route':15} match")
    agree = clinical = 0
    for p, t, code, said, usd in rows:
        m = "-" if said == "clinical" else ("yes" if said == t else "NO")
        agree += m == "yes"
        clinical += said == "clinical"
        print(f"{p:7} {t:9} {code:15} {m}   ${usd:.2f}")
    n = len(rows)
    print(f"\n{agree}/{n - clinical} agree where the tool leaned one way; {clinical} sent to the clinical line.")
    print(f"Total cost ${sum(r[4] for r in rows):.2f}, average ${sum(r[4] for r in rows) / max(n, 1):.2f} per packet.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "score":
        score()
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        run(sys.argv[2:])
    else:
        print(__doc__)
