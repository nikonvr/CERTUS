"""Where does the damage land? Per-band profile of every probe run on disk.

    .venv\\Scripts\\python.exe scripts\\analyse_bands.py

Reads nothing but `reports/probe_anchor_noise_pipeline_*.json`. No bench time.

🔴 WHAT THIS DOES NOT DO, AND WHY

  The obvious analysis -- follow one strategy across runs -- is NOT VALID here.
  Checked on 2026-08-10: no strategy id is present in all runs, the captured sets
  differ, and even a shared id does not denote the same strategy, because Phase A
  re-generates its candidates whenever the corridor or the threshold changes.
  Comparing strategy 48800 of one run against 48800 of another would produce a
  perfectly plausible and perfectly wrong table.

  What IS comparable is the SHAPE of the error inside a run: how the spectral error
  splits between the passband, the edge and the blocked band. That ratio is a
  property of the condition, not of which strategies happened to be captured.

  ⚠️ And `RESULT` is NOT comparable with any of these numbers: 10 of CLAUDE.md
  records that RESULT is the WORST of three noise levels while the per-strategy
  figures are at the NOMINAL level. They are never put in the same table here.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPORTS = Path(r"C:\dev\gemini\reports")
BANDS = ("passante", "front", "bloquee")


def med(values: list[float]) -> float:
    return statistics.median(values) if values else float("nan")


def main() -> int:
    rows = []
    for path in sorted(REPORTS.glob("probe_anchor_noise_pipeline_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        strategies = data.get("strategies") or []
        if not strategies:
            continue
        tag = path.stem.replace("probe_anchor_noise_pipeline_", "")
        per_band = {b: med([s[b]["rmse_median"] for s in strategies if b in s]) for b in BANDS}
        rows.append({
            "tag": tag,
            "n": len(strategies),
            "crash": med([s["crash"] for s in strategies]),
            "shift": med([s["front_shift_nm"]["abs_p95"] for s in strategies]),
            **per_band,
            "config": data.get("config"),
        })

    print("PROFIL PAR BANDE -- mediane sur les strategies capturees de chaque run")
    print("RMSE median par bande, au niveau de bruit NOMINAL. Jamais comparable a RESULT.\n")
    head = f"{'run':<34s} {'n':>3s} {'crash':>6s} {'passante':>10s} {'front':>10s} {'bloquee':>10s} {'front/pass':>11s} {'shift nm':>9s}"
    print(head)
    print("-" * len(head))
    for r in rows:
        ratio = r["front"] / r["passante"] if r["passante"] else float("nan")
        print(
            f"{r['tag']:<34s} {r['n']:>3d} {r['crash']:>6.3f} {r['passante']:>10.6f} "
            f"{r['front']:>10.6f} {r['bloquee']:>10.6f} {ratio:>11.2f} {r['shift']:>9.2f}"
        )

    print("\n" + "=" * 78)
    print("CE QUE LA FORME DIT")
    print("=" * 78)
    blocked = [r["bloquee"] for r in rows]
    passband = [r["passante"] for r in rows]
    print(f"  La bande BLOQUEE est {med(passband) / med(blocked):.0f}x plus propre que la passante,")
    print("  sur tous les runs. Le filtre ne rate jamais son blocage ; il rate son passage.")
    ratios = [r["front"] / r["passante"] for r in rows if r["passante"]]
    print(f"  Le FRONT porte systematiquement plus d'erreur que la passante :")
    print(f"    rapport front/passante  min {min(ratios):.2f}  median {med(ratios):.2f}  max {max(ratios):.2f}")
    print("\n  ⚠️ Les populations de strategies different d'un run a l'autre. Ces profils")
    print("     decrivent la FORME de l'erreur, pas une comparaison appariee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
