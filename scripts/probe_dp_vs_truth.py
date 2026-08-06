"""LA mesure : le cout de la DP predit-il le vrai critere ?

La Phase B elimine la quasi-totalite de l'espace sur `total_cost` — une somme de
NANOMETRES d'erreur d'epaisseur produite par la programmation dynamique
(certus/physics/certus_strat_dp.py:61,118). Le vrai critere, lui, n'est calcule qu'au bout :
`robustness_score`, le pire P95 du RMSE spectral sur les niveaux de bruit
(certus/core/certus_strat_robustness.py:732).

Personne n'a jamais mesure si le premier predit le second. Or tout ce que la Phase B jette,
elle le jette sur le premier.

  rho eleve  -> l'elagage est inoffensif, les refontes de la fonction de cout sont du bruit.
  rho faible -> la DP comme FILTRE est une erreur de conception. Elle doit devenir un
                GENERATEUR de diversite, et le tri revenir au Monte-Carlo.

METHODE. On intercepte `run_final_simulation_block`, qui rend pour CHAQUE strategie minee son
`robustness_score` — avant toute coupe au top-k. C'est donc la population COMPLETE, sans
troncature de selection : une correlation calculee sur les seules survivantes serait
mecaniquement attenuee par restriction d'etendue.

`total_cost` n'est comparable qu'a nombre de blocs egal (la DP tourne par n_blocks) : le rho
est donc calcule PAR n_blocks, puis agrege. Le rho global sur la population melangee est
donne a titre indicatif seulement.

    .venv/Scripts/python.exe scripts/probe_dp_vs_truth.py

N'ecrit rien hors reports/. Ne modifie aucun comportement.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402

OUT = ROOT / "reports" / "probe_dp_vs_truth.json"
CAPTURED: list[dict] = []


def install_probe() -> None:
    import certus.workers.certus_strat_workers as W

    original = W.run_final_simulation_block

    def patched(*a, **kw):
        out = original(*a, **kw)
        num_runs = kw.get("num_runs")
        if num_runs is None and len(a) >= 3:
            num_runs = a[2]
        try:
            items = out.get("all_strategies_results") if isinstance(out, dict) else None
            if items:
                batch = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    strat = it.get("strategy") or {}
                    batch.append(
                        {
                            "total_cost": strat.get("total_cost"),
                            "avg_cost": strat.get("avg_cost"),
                            "base_cost": strat.get("avg_rmse_nominal"),
                            "n_blocks": strat.get("n_blocks"),
                            "origin": strat.get("origin"),
                            "strategy_id": strat.get("strategy_id"),
                            "robustness_score": it.get("robustness_score"),
                            "crash_rate": it.get("crash_rate"),
                        }
                    )
                CAPTURED.append({"num_runs": num_runs, "n": len(batch), "items": batch})
        except Exception as exc:  # noqa: BLE001 - une sonde ne doit jamais tuer le calcul
            B.emit(f"PROBE_CAPTURE_FAILED={exc!r}")
        return out

    W.run_final_simulation_block = patched
    B.emit("sonde installee sur run_final_simulation_block")


def analyse() -> dict:
    import numpy as np
    from scipy import stats

    def _clean(items):
        xs, ys = [], []
        for it in items:
            c, r = it.get("total_cost"), it.get("robustness_score")
            if c is None or r is None:
                continue
            c, r = float(c), float(r)
            if np.isfinite(c) and np.isfinite(r) and c > 0 and r > 0:
                xs.append(c)
                ys.append(r)
        return np.asarray(xs), np.asarray(ys)

    def _topk_overlap(xs, ys, k):
        """Des k que la DP garderait (cout croissant), combien sont dans le vrai top-k ?"""
        if len(xs) <= k:
            return None
        dp_keep = set(np.argsort(xs)[:k].tolist())
        true_best = set(np.argsort(ys)[:k].tolist())
        return len(dp_keep & true_best)

    per_group: list[dict] = []
    pooled_items: list[dict] = []

    for cap in CAPTURED:
        # on groupe par n_blocks : total_cost n'est pas comparable d'un n_blocks a l'autre
        by_nb: dict = {}
        for it in cap["items"]:
            by_nb.setdefault(it.get("n_blocks"), []).append(it)
        for nb, items in by_nb.items():
            xs, ys = _clean(items)
            if len(xs) < 5:
                continue
            rho, p_rho = stats.spearmanr(xs, ys)
            tau, p_tau = stats.kendalltau(xs, ys)
            per_group.append(
                {
                    "num_runs": cap["num_runs"],
                    "n_blocks": nb,
                    "n": int(len(xs)),
                    "spearman_rho": float(rho),
                    "spearman_p": float(p_rho),
                    "kendall_tau": float(tau),
                    "overlap_top10": _topk_overlap(xs, ys, 10),
                    "overlap_top5": _topk_overlap(xs, ys, 5),
                    "cost_range": [float(xs.min()), float(xs.max())],
                    "score_range": [float(ys.min()), float(ys.max())],
                }
            )
        pooled_items.extend(cap["items"])

    xs, ys = _clean(pooled_items)
    pooled = None
    if len(xs) >= 5:
        rho, p = stats.spearmanr(xs, ys)
        pooled = {
            "n": int(len(xs)),
            "spearman_rho": float(rho),
            "spearman_p": float(p),
            "note": "populations melangees (n_blocks differents) — indicatif seulement",
        }

    screening = [g for g in per_group if g["num_runs"] and g["num_runs"] <= 30]
    weights = [g["n"] for g in screening]
    rho_w = (
        sum(g["spearman_rho"] * g["n"] for g in screening) / sum(weights) if weights else None
    )
    ov = [g["overlap_top10"] for g in screening if g["overlap_top10"] is not None]

    return {
        "n_captures": len(CAPTURED),
        "per_group": sorted(per_group, key=lambda g: (g["num_runs"] or 0, g["n_blocks"] or 0)),
        "pooled": pooled,
        "screening_rho_pondere_par_n": rho_w,
        "screening_overlap_top10": {
            "n_groupes": len(ov),
            "min": min(ov) if ov else None,
            "median": sorted(ov)[len(ov) // 2] if ov else None,
            "max": max(ov) if ov else None,
            "mean": sum(ov) / len(ov) if ov else None,
        },
    }


def main() -> None:
    B.qapp()
    B.autoanswer_dialogs(True)
    install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")

    if not CAPTURED:
        B.emit("PROBE_JAMAIS_APPELEE")
        sys.stdout.flush()
        os._exit(0)

    r = analyse()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={OUT}")
    B.emit(f"CAPTURES={r['n_captures']}  GROUPES={len(r['per_group'])}")

    rw = r["screening_rho_pondere_par_n"]
    if rw is not None:
        B.emit(f"RHO_SPEARMAN_PONDERE={rw:.3f}   (screening, par n_blocks, non tronque)")
    if r["pooled"]:
        B.emit(f"RHO_POOLED={r['pooled']['spearman_rho']:.3f}  n={r['pooled']['n']}")
    o = r["screening_overlap_top10"]
    if o["median"] is not None:
        B.emit(
            "OVERLAP_TOP10 (des 10 gardees par cout, combien dans le vrai top 10) : "
            f"min={o['min']} median={o['median']} max={o['max']} mean={o['mean']:.1f}"
        )
    for g in r["per_group"][:14]:
        B.emit(
            f"  n_runs={g['num_runs']} n_blocks={g['n_blocks']:>2} n={g['n']:>4} "
            f"rho={g['spearman_rho']:+.3f} tau={g['kendall_tau']:+.3f} "
            f"top10={g['overlap_top10']}"
        )

    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
