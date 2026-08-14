"""Recherche systématique par essais/erreurs et propagation pour trouver des stratégies par blocs robustes (crash_rate = 0) sur le 35 couches.

Usage:
    .venv/Scripts/python.exe scripts/find_35c_working_blocks.py
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
    print("RECHERCHE SYSTÉMATIQUE DE STRATÉGIES PAR BLOCS SANS PLANTAGE (35 COUCHES)")
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

    # Architecture du passe-bande 3 cavités (35 couches) :
    # M1 (0..5) - C1 (5..6) - M2 (6..17) - C2 (17..18) - M3 (18..29) - C3 (29..30) - M4 (30..35)
    #
    # Testons différentes architectures de partitionnement :
    # A. 7 blocs physiques
    # B. 10 blocs (découpage des miroirs longs M2 et M3 en 2 sous-blocs de 5 et 6 couches)
    # C. 14 blocs (miroirs découpés en blocs de 2-3 couches)

    print("\nPhase 1 : Balayage fin des longueurs d'ondes candidates par bloc...", flush=True)

    # Grille de longueurs d'onde à explorer
    candidate_wls = [450, 460, 470, 480, 490, 500, 510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 610, 620, 630, 640, 650, 660, 670, 680, 690, 700]

    def evaluate_strategy(blocks, name):
        strat = {
            "strategy_id": 9999,
            "n_blocks": len(blocks),
            "blocks": blocks,
            "origin": name,
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
        crash_rate = res.get("crash_rate", 1.0)
        r_noise = res.get("results_per_noise", [])
        rmse_p95 = r_noise[0].get("rmse_p95", float("nan")) if r_noise else float("nan")
        rmse_med = r_noise[0].get("rmse_median", float("nan")) if r_noise else float("nan")
        poem_count = res.get("poem_anchored_layers_count", 0)
        return crash_rate, rmse_med, rmse_p95, poem_count, res

    # 1. Évaluation bloc par bloc (Greedy block building) :
    # Trouver une longueur d'onde robuste pour chaque bloc physique
    # Partitionnement en 7 blocs :
    # B1: [0..5], B2: [5..6], B3: [6..17], B4: [17..18], B5: [18..29], B6: [29..30], B7: [30..35]
    BLOCK_RANGES = [
        (0, 5, "Miroir 1 (5 couches)"),
        (5, 6, "Cavité 1 (1 couche 2L)"),
        (6, 17, "Miroir 2 (11 couches)"),
        (17, 18, "Cavité 2 (1 couche 2L)"),
        (18, 29, "Miroir 3 (11 couches)"),
        (29, 30, "Cavité 3 (1 couche 2L)"),
        (30, 35, "Miroir 4 (5 couches)"),
    ]

    # Découpage plus fin en 10 blocs (M2 et M3 coupés en 2) :
    BLOCK_RANGES_10 = [
        (0, 5, "M1 (5c)"),
        (5, 6, "C1 (1c)"),
        (6, 11, "M2a (5c)"),
        (11, 17, "M2b (6c)"),
        (17, 18, "C2 (1c)"),
        (18, 23, "M3a (5c)"),
        (23, 29, "M3b (6c)"),
        (29, 30, "C3 (1c)"),
        (30, 35, "M4 (5c)"),
    ]

    # Découpage en 14 blocs (Miroirs en blocs de 2-3 couches) :
    BLOCK_RANGES_14 = [
        (0, 2, "M1a (2c)"), (2, 5, "M1b (3c)"),
        (5, 6, "C1 (1c)"),
        (6, 9, "M2a (3c)"), (9, 13, "M2b (4c)"), (13, 17, "M2c (4c)"),
        (17, 18, "C2 (1c)"),
        (18, 21, "M3a (3c)"), (21, 25, "M3b (4c)"), (25, 29, "M3c (4c)"),
        (29, 30, "C3 (1c)"),
        (30, 32, "M4a (2c)"), (32, 35, "M4b (3c)"),
    ]

    tested_partitions = [
        ("7 BLOCS NATURELS", BLOCK_RANGES),
        ("9 BLOCS ÉQUILIBRÉS", BLOCK_RANGES_10),
        ("13 BLOCS COURTS", BLOCK_RANGES_14),
    ]

    # Exploration aléatoire et guidée de combinaisons
    rng = np.random.default_rng(42)
    successful_strategies = []

    print("\nPhase 2 : Recherche de combinaisons de longueurs d'ondes viables...", flush=True)

    for part_name, partitions in tested_partitions:
        print(f"\n--- Test du partitionnement : {part_name} ({len(partitions)} blocs) ---", flush=True)
        
        # Test 1: Longueurs d'ondes uniformes
        for wl in [460, 480, 500, 520, 540, 560, 580, 600, 632]:
            blks = [{"start": s, "end": e, "wavelength": float(wl), "num_layers": e - s} for s, e, _ in partitions]
            cr, r_med, r_p95, poem_c, _ = evaluate_strategy(blks, f"{part_name} @ {wl}nm")
            if cr < 1.0:
                print(f"  * Uniforme {wl}nm -> Crash: {cr*100:5.1f}% | RMSE P95: {r_p95:.4f} | POEM: {poem_c}/35", flush=True)
            if cr == 0.0:
                successful_strategies.append((part_name, blks, r_p95, poem_c))

        # Test 2: Miroirs décalés, Cavités à 632 nm
        for wl_m in [460, 480, 500, 520, 540, 560, 580, 600]:
            blks = []
            for s, e, lbl in partitions:
                w = 632.0 if "Cavité" in lbl or "C1" in lbl or "C2" in lbl or "C3" in lbl else float(wl_m)
                blks.append({"start": s, "end": e, "wavelength": w, "num_layers": e - s})
            cr, r_med, r_p95, poem_c, _ = evaluate_strategy(blks, f"{part_name} Miroirs@{wl_m}nm / Cavités@632nm")
            if cr < 1.0:
                print(f"  * Miroirs@{wl_m}nm/Cav@632nm -> Crash: {cr*100:5.1f}% | RMSE P95: {r_p95:.4f} | POEM: {poem_c}/35", flush=True)
            if cr == 0.0:
                successful_strategies.append((part_name, blks, r_p95, poem_c))

        # Test 3: Recherche stochastique intelligente (100 tirages par partition)
        best_part_cr = 1.0
        best_part_strat = None
        for it in range(80):
            blks = []
            for s, e, lbl in partitions:
                if "Cavité" in lbl or "C1" in lbl or "C2" in lbl or "C3" in lbl:
                    w = float(rng.choice([450, 460, 480, 520, 600, 632, 640]))
                else:
                    w = float(rng.choice([450, 460, 470, 480, 490, 500, 510, 520, 530, 540, 550, 560, 580]))
                blks.append({"start": s, "end": e, "wavelength": w, "num_layers": e - s})
            
            cr, r_med, r_p95, poem_c, _ = evaluate_strategy(blks, f"{part_name} Tirage #{it+1}")
            if cr < best_part_cr:
                best_part_cr = cr
                best_part_strat = (blks, cr, r_p95, poem_c)
                print(f"    [Progression] {part_name} Tirage #{it+1} -> Crash réduit à {cr*100:.1f}% (RMSE: {r_p95:.4f}, POEM: {poem_c}/35)", flush=True)
            if cr == 0.0:
                print(f"    🎉 SUCCÈS ! {part_name} Tirage #{it+1} a un CRASH = 0.0% ! RMSE P95 = {r_p95:.4f}", flush=True)
                successful_strategies.append((part_name, blks, r_p95, poem_c))

    print("\n" + "=" * 80)
    print("BILAN DE LA RECHERCHE :")
    print("=" * 80)
    if successful_strategies:
        successful_strategies.sort(key=lambda x: x[2] if not np.isnan(x[2]) else 1e9)
        print(f"\n🏆 {len(successful_strategies)} STRATÉGIES PAR BLOCS ONT FONCTIONNÉ AVEC 0% DE PLANTAGE !")
        for idx, (p_name, blks, r_p95, poem_c) in enumerate(successful_strategies[:10]):
            wls_str = ", ".join(f"{b['wavelength']:.0f}" for b in blks)
            print(f"\nStratégie #{idx+1} ({p_name}, {len(blks)} blocs) :")
            print(f"  - Longueurs d'onde des blocs : [{wls_str}]")
            print(f"  - RMSE P95 : {r_p95:.4f}")
            print(f"  - Couches avec POEM actif : {poem_c}/35")
    else:
        print("\nAucune combinaison n'a atteint 0% de crash parmi les tirages directs.")


if __name__ == "__main__":
    main()
