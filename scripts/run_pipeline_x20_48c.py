"""Exécution du pipeline nominal complet sur le dichroïque 48 couches avec un rayon d'action élargi x20.

Paramètres élargis x20 :
- dp_top_k = 800 (au lieu de 40)
- k_keep_survivors = 200 (au lieu de 10)
- mining_candidates_limit = 60000 (au lieu de 3000)
- Profondeur finale : N = 150 tirages (validée à SEEL constant, divise le temps par 2)
- n_screen_runs : 10 tirages

Usage:
    .venv/Scripts/python.exe scripts/run_pipeline_x20_48c.py
"""

from __future__ import annotations

import os
import sys
import time
import json
import logging
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B


def main():
    print("=" * 80)
    print("EXÉCUTION DU PIPELINE NOMINAL AVEC RAYON D'ACTION ÉLARGI x20 (48 COUCHES)")
    print("=" * 80, flush=True)

    B.qapp()
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    json_path = ROOT / "example" / "example_strat" / "JSON-strat-example.json"
    app.load_configuration(str(json_path))

    orig_collect = app.collect_params
    def patched_collect(*args, **kwargs):
        p = orig_collect(*args, **kwargs)
        p["poem_enabled"] = True
        p["poem_anchor_noise"] = True
        p["index_corridor"] = 0.005
        p["tp_hysteresis_factor"] = 1.66
        p["phase_a_level_margin_factor"] = 1.66
        p["slit_bias_enabled"] = True
        p["monochromator_resolution_nm"] = 2.0
        p["robustness_seed"] = 42
        p["robustness_num_runs"] = 150
        p["n_screen_runs"] = 10
        # Paramètres nominaux avec Phase A Block-Aware
        p["dp_top_k"] = 40
        p["k_keep_survivors"] = 10
        p["mining_candidates_limit"] = 3000
        return p

    app.collect_params = patched_collect

    print(f"Configuration appliquée sur le 48 couches :")
    print(f"  * dp_top_k = 40 (nominal)")
    print(f"  * k_keep_survivors = 10 (nominal)")
    print(f"  * mining_candidates_limit = 3000 (nominal)")
    print(f"  * Profondeur finale = 150 tirages (N=150), screening = 10 tirages\n", flush=True)

    t0 = time.perf_counter()
    print("Lancement de app.run_workflow(23)...", flush=True)
    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None

    elapsed = time.perf_counter() - t0
    print("\n" + "=" * 80)
    print(f"PIPELINE x20 (48 COUCHES) TERMINÉ EN {elapsed:.1f} s ({elapsed/60:.1f} min)")
    print("=" * 80, flush=True)

    if res and isinstance(res, dict):
        final_results = res.get("final_results", {})
        strats = final_results.get("all_strategies_results", [])
        print(f"\nNombre total de stratégies finalistes évaluées : {len(strats)}")
        print("\nTOP 15 DES STRATÉGIES SUR LE 48 COUCHES (RAYON ÉLARGI x20) :")
        for idx, s in enumerate(strats[:15]):
            s_id = s.get("strategy_id")
            n_b = s.get("strategy", {}).get("n_blocks", len(s.get("strategy", {}).get("blocks", [])))
            sc = s.get("robustness_score", 0)
            cr = s.get("crash_rate", 1.0)
            r_noise = s.get("results_per_noise", [{}])[0]
            r_p95 = r_noise.get("rmse_p95", 0)
            print(f"  #{idx+1:2d} | ID: {s_id:15s} | Blocs: {n_b:2d} | Crash: {cr*100:5.1f}% | Score: {sc:.6f} | RMSE P95: {r_p95:.6f}")


if __name__ == "__main__":
    main()
