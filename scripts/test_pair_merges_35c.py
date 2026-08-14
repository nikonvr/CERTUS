"""Test systématique de TOUTES les fusions possibles de 2 couches consécutives (2 par 2)
en partant de la meilleure stratégie historique (35 lambdas).

Pour chaque paire adjacente (i, i+1) parmi les 34 paires possibles :
  - Balaye TOUTES les longueurs d'onde lambda in [450..700] nm pour ce bloc de 2 couches.
  - Conserve les 33 autres couches à leurs longueurs d'onde historiques optimales.
  - Vérifie si une longueur d'onde donne STRICTEMENT 0 crash et mesure le SEEL et RMSE.

Usage:
    .venv/Scripts/python.exe scripts/test_pair_merges_35c.py
"""

from __future__ import annotations

import os
import sys
import time
import json
import logging
from pathlib import Path
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import certus_physics
from certus_physics import calculate_RT_batch_kernel
from certus.core.certus_strat_config import (
    get_refractive_index,
    get_refractive_clues_vectorized,
    precompute_clues_and_matrices,
)
from certus.core.certus_strat_robustness import (
    _test_strategy_robustness_task,
    _prepare_robustness_nominal_optics,
)
import bench_examples as B


def main():
    print("=" * 80)
    print("EXPLORATION SYSTÉMATIQUE DES FUSIONS 2 PAR 2 SUR LE 35 COUCHES")
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
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    params["p_thick_nominal"] = p_thick_nominal
    num_layers = len(p_thick_nominal)

    logger = logging.getLogger("test")
    logger.setLevel(logging.ERROR)
    clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)
    opti_results = {"clues_at_wl": clues_at_wl}
    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params, p_thick_nominal, opti_results
    )
    full_dyn_grid = {i: {float(w): 0.1 for w in clues_at_wl.keys()} for i in range(num_layers)}
    noise_levels = [1.0]
    num_runs = 150

    # Bande cible 600 - 660 nm
    target_wls = np.linspace(600.0, 660.0, 61)
    db_instance = params.get("materials_db_instance") or params.get("materials_db")
    nH_target = get_refractive_clues_vectorized(params["nH_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nL_target = get_refractive_clues_vectorized(params["nL_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nSub_target = get_refractive_clues_vectorized(params["nSub_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    _, T_target_nom_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, p_thick_nom_arr.reshape(1, -1))
    T_target_nom = np.asarray(T_target_nom_batch, dtype=np.float64)[0]

    # Charger les longueurs d'onde historiques
    obs_file = ROOT / "reports" / "STRAT_observability_20260814_102134.json"
    with open(obs_file, "r", encoding="utf-8") as f:
        obs_data = json.load(f)
    base_wls = [float(l["best_wl"]) for l in obs_data["layers"]][:num_layers]

    # Toutes les longueurs d'onde possibles pour le scan du bloc fusionné
    all_scan_wls = sorted(list(clues_at_wl.keys()))  # 450 à 700 nm par pas de 1 nm ou 5 nm

    def evaluate_strat(blocks):
        strat = {
            "strategy_id": 777,
            "n_blocks": len(blocks),
            "blocks": blocks,
            "origin": "Pair merge test",
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
        cr = res.get("crash_rate", 1.0)
        r_noise = res.get("results_per_noise", [])
        if r_noise and "thicknesses_all" in r_noise[0]:
            D = np.array(r_noise[0]["thicknesses_all"])
            survived = ~np.any(D > 1e5, axis=1)
            if np.any(survived):
                _, T_sim_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, D[survived])
                T_sim = np.asarray(T_sim_batch, dtype=np.float64)
                E_target = T_sim - T_target_nom[None, :]
                rmse_runs = np.sqrt(np.mean(E_target ** 2, axis=1))
                rmse_p95 = float(np.percentile(rmse_runs, 95))
                seel = float(rmse_p95 * 9.55)
            else:
                rmse_p95, seel = 1.0, 10.0
        else:
            rmse_p95, seel = 1.0, 10.0
        return cr, rmse_p95, seel, res

    print("\n--- TEST DE CHAQUE PAIRE DE COUCHES ADJACENTES (1..34) ---", flush=True)

    successful_merges = []

    # Pour chaque paire adjacente (pair_idx, pair_idx+1)
    for pair_idx in range(num_layers - 1):
        l_a = pair_idx + 1
        l_b = pair_idx + 2
        wl_a_base = base_wls[pair_idx]
        wl_b_base = base_wls[pair_idx + 1]

        print(f"\n🔍 Test de la Paire [{l_a}, {l_b}] (Base : {wl_a_base:.0f} nm & {wl_b_base:.0f} nm)...", flush=True)

        best_pair_cr = 1.0
        best_pair_rmse = 1e9
        best_pair_wl = None
        best_pair_seel = 1e9

        # Balayage de toutes les longueurs d'ondes pour cette paire
        # Échantillonnage par pas de 5 nm de 450 à 700 nm
        test_wls = [w for w in all_scan_wls if int(w) % 5 == 0 or w in (wl_a_base, wl_b_base)]

        for test_wl in test_wls:
            # Construire la stratégie avec la paire fusionnée
            blocks = []
            for i in range(num_layers):
                if i == pair_idx:
                    blocks.append({"start": pair_idx, "end": pair_idx + 2, "wavelength": float(test_wl), "num_layers": 2})
                elif i == pair_idx + 1:
                    continue  # Couche fusionnée avec la précédente
                else:
                    blocks.append({"start": i, "end": i + 1, "wavelength": float(base_wls[i]), "num_layers": 1})

            cr, rmse_p95, seel, _ = evaluate_strat(blocks)

            if cr < best_pair_cr or (cr == best_pair_cr and rmse_p95 < best_pair_rmse):
                best_pair_cr = cr
                best_pair_rmse = rmse_p95
                best_pair_seel = seel
                best_pair_wl = test_wl

            if cr == 0.0:
                print(f"  🎉 VICTOIRE ! Paire [{l_a}, {l_b}] fusionnée @ {test_wl:.0f} nm -> 0.0% CRASH ! (RMSE P95: {rmse_p95:.5f}, SEEL: {seel:.3f} nm)", flush=True)
                successful_merges.append({
                    "pair": (l_a, l_b),
                    "wavelength": test_wl,
                    "crash_rate": cr,
                    "rmse_p95": rmse_p95,
                    "seel_nm": seel,
                })

        if best_pair_cr == 0.0:
            print(f"  -> ✅ Résultat Paire [{l_a}, {l_b}] : FUSION RÉUSSIE @ {best_pair_wl:.0f} nm (0% Crash, SEEL: {best_pair_seel:.3f} nm)", flush=True)
        else:
            print(f"  -> ❌ Résultat Paire [{l_a}, {l_b}] : Meilleur crash = {best_pair_cr*100:.1f}% @ {best_pair_wl:.0f} nm (SEEL: {best_pair_seel:.3f} nm)", flush=True)

    print("\n" + "=" * 80)
    print("BILAN COMPLET DES FUSIONS 2 PAR 2 RÉUSSIES :")
    print("=" * 80)
    if successful_merges:
        print(f"\n🏆 {len(successful_merges)} PAIRES DE COUCHES PEUVENT ÊTRE FUSIONNÉES AVEC 0% DE CRASH !")
        successful_merges.sort(key=lambda x: x["rmse_p95"])
        for idx, item in enumerate(successful_merges):
            print(f"  #{idx+1} : Couches {item['pair'][0]} & {item['pair'][1]} fusionnées @ {item['wavelength']:.0f} nm -> Crash: 0.0%, RMSE P95: {item['rmse_p95']:.5f}, SEEL: {item['seel_nm']:.3f} nm")
    else:
        print("\nAucune paire n'a atteint 0% de crash isolément.")


if __name__ == "__main__":
    main()
