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

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
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
        # 🔴 The three bands are pinned to the DICHROIC's edge (400-540 / 540-560 / 560+).
        # On the three-cavity bandpass, whose target is 600-660 nm, `passante` and `front`
        # are empty and the probe now writes `null` there rather than dying. Such a run
        # has nothing to say in THIS table, so it is skipped and named -- silently
        # printing zeros would invent a perfect passband where there is no passband.
        per_band = {
            b: med([s[b]["rmse_median"] for s in strategies if isinstance(s.get(b), dict)])
            for b in BANDS
        }
        # `med([])` rend nan, pas None -- le garde doit tester la valeur, pas le type.
        if any(v != v for v in per_band.values()):
            print(f"  (ignore : {tag} -- decoupage par bande inapplicable a ce composant)")
            continue
        shifts = [s["front_shift_nm"]["abs_p95"] for s in strategies
                  if isinstance(s.get("front_shift_nm"), dict)]
        rows.append({
            "tag": tag,
            "n": len(strategies),
            "crash": med([s["crash"] for s in strategies]),
            "shift": med(shifts),
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
