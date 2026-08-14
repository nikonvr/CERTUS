"""Analyse pas-à-pas de la survie couche par couche pour identifier les blocs maximaux à 0% de crash.

Usage:
    .venv/Scripts/python.exe scripts/step_by_step_35c_solver.py
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from certus.core.certus_strat_config import (
    get_refractive_index,
    precompute_clues_and_matrices,
    arange_inclusive,
)
from certus.core.certus_strat_robustness import (
    _test_strategy_robustness_task,
    _prepare_robustness_nominal_optics,
)
import bench_examples as B


def main():
    print("=" * 80)
    print("CONSTRUCTION PAS-À-PAS DES BLOCS MAXIMAUX SANS PLANTAGE (35 COUCHES)")
    print("=" * 80, flush=True)

    B.qapp()
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    json_path = ROOT / "example" / "example_strat" / "JSON-strat-bandpass-3cav.json"
    app.load_configuration(str(json_path))

    params = app.collect_params()
    params["poem_enabled"] = True
    params["poem_anchor_noise"] = True
    params["index_corridor"] = 0.005
    params["tp_hysteresis_factor"] = 1.66
    params["phase_a_level_margin_factor"] = 1.66
    params["slit_bias_enabled"] = True
    params["monochromator_resolution_nm"] = 2.0
    params["robustness_seed"] = 42

    l0 = float(params["l0"])
    multipliers = [float(e) for e in params["stack_string"].split(",") if e.strip()]
    nH_at_l0 = get_refractive_index(params["nH_id"], l0)
    nL_at_l0 = get_refractive_index(params["nL_id"], l0)
    p_thick_nominal = [
        (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0))
        for i, m in enumerate(multipliers)
    ]
    params["p_thick_nominal"] = p_thick_nominal
    num_layers = len(p_thick_nominal)

    logger = logging.getLogger("certus_strat")
    logger.setLevel(logging.ERROR)
    for h in logger.handlers:
        h.setLevel(logging.ERROR)

    clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)
    opti_results = {"clues_at_wl": clues_at_wl}
    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params, p_thick_nominal, opti_results
    )
    full_dyn_grid = {i: {float(w): 0.1 for w in clues_at_wl.keys()} for i in range(num_layers)}
    noise_levels = [1.0]
    num_runs = 150

    # Testons comment construire un bloc sur le Miroir 1 (couches 0 à 4)
    # Quelle longueur d'onde permet de déposer les couches 0, 1, 2, 3, 4 d'un seul tenant ?
    print("\n--- TEST DU MIROIR 1 (Couches 1 à 5, HLHLH) ---", flush=True)
    scan_wls = [450, 470, 490, 510, 520, 530, 540, 550, 560, 580, 600, 620, 632, 650, 680, 700]

    for wl in scan_wls:
        # Test de la couche 1 à k (k = 1..5) sur la même longueur d'onde
        survivals = []
        for k in range(1, 6):
            strat = {
                "strategy_id": int(wl * 10 + k),
                "n_blocks": 1,
                "blocks": [{"start": 0, "end": k, "wavelength": float(wl), "num_layers": k}] + [
                    {"start": j, "end": j + 1, "wavelength": 632.0, "num_layers": 1} for j in range(k, 35)
                ],
                "origin": f"M1 (1..{k}) @ {wl}nm",
            }
            res = _test_strategy_robustness_task(
                strategy=strat,
                _strat_idx=0,
                noise_levels=noise_levels,
                num_runs=num_runs,
                p_thick_nominal=p_thick_nominal,
                clues_at_wl=clues_at_wl,
                params=params,
                wl_arr=wl_arr,
                nH_arr=nH_arr,
                nL_arr=nL_arr,
                nSub_arr=nSub_arr,
                T_nom=T_nom,
                full_dyn_grid=full_dyn_grid,
            )
            crash_by_l = res.get("crash_by_layer", {}).get("total", [0] * 35)
            # Crash sur les k premières couches
            crashes_in_block = sum(crash_by_l[:k])
            survivals.append(crashes_in_block)

        status_str = " -> ".join(f"L{idx+1}:{cnt}/{num_runs}" for idx, cnt in enumerate(survivals))
        is_clean = all(c == 0 for c in survivals)
        mark = "✅ 100% OK !" if is_clean else ("⚠️ Partiel" if survivals[-1] < 150 else "❌")
        print(f"  WL {wl:3.0f} nm | {mark:<12} | {status_str}", flush=True)


if __name__ == "__main__":
    main()
