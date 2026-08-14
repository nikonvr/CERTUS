"""Constructeur séquentiel avant (Forward Block Builder) pour trouver une stratégie par blocs à 0.0% de crash sur le 35 couches.

Principe : Construit les blocs un par un de l'amont vers l'aval en exigeant 0.0% de crash à chaque étape.

Usage:
    .venv/Scripts/python.exe scripts/forward_block_builder_35c.py
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
)
from certus.core.certus_strat_robustness import (
    _test_strategy_robustness_task,
    _prepare_robustness_nominal_optics,
)
import bench_examples as B


def main():
    print("=" * 80)
    print("CONSTRUCTEUR SÉQUENTIEL AVANT : RECHERCHE DE BLOCS À 0% DE CRASH (35 COUCHES)")
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

    # Longueurs d'onde disponibles pour le scan
    scan_wls = [float(w) for w in range(450, 705, 5)]

    # Fonction d'évaluation d'un préfixe de blocs
    def eval_prefix(blocks, current_end):
        # Compléter avec des blocs d'une couche à 632 nm pour les couches restantes
        full_blocks = list(blocks)
        if current_end < num_layers:
            full_blocks.extend([
                {"start": j, "end": j + 1, "wavelength": 632.0, "num_layers": 1}
                for j in range(current_end, num_layers)
            ])
        
        strat = {
            "strategy_id": 8888,
            "n_blocks": len(full_blocks),
            "blocks": full_blocks,
            "origin": f"Prefix {current_end} layers",
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
        crash_by_l = res.get("crash_by_layer", {}).get("total", [0] * num_layers)
        # Nombre de runs ayant crashé sur les couches du préfixe
        sim_thick = np.array(res.get("results_per_noise", [{}])[0].get("thicknesses_all", []))
        if len(sim_thick) > 0:
            prefix_crashed = np.any(sim_thick[:, :current_end] > 1e5, axis=1)
            prefix_crash_count = int(np.count_nonzero(prefix_crashed))
        else:
            prefix_crash_count = 150
            
        r_noise = res.get("results_per_noise", [])
        rmse_p95 = r_noise[0].get("rmse_p95", float("nan")) if r_noise else float("nan")
        poem_count = res.get("poem_anchored_layers_count", 0)
        return prefix_crash_count, rmse_p95, poem_count, res

    # Algorithme Beam Search séquentiel :
    # Beam = liste de (current_end_layer, list_of_blocks, score)
    beam = [(0, [], 0.0)]
    BEAM_WIDTH = 5

    current_layer = 0
    step = 1

    print("\nDémarrage de la construction progressive par blocs...", flush=True)

    while beam and min(end for end, _, _ in beam) < num_layers:
        print(f"\n--- ÉTAPE {step} : Extension depuis les couches de fin {set(end for end, _, _ in beam)} ---", flush=True)
        next_beam_candidates = []

        for start_layer, prev_blocks, prev_score in beam:
            if start_layer >= num_layers:
                next_beam_candidates.append((start_layer, prev_blocks, prev_score))
                continue

            # Longueurs de blocs possibles : de 1 à 6 couches (ou jusqu'à num_layers)
            max_len = min(6, num_layers - start_layer)
            # Tester des tailles de blocs de 1 à max_len
            for blk_len in range(1, max_len + 1):
                end_layer = start_layer + blk_len
                
                for wl in scan_wls:
                    new_block = {"start": start_layer, "end": end_layer, "wavelength": wl, "num_layers": blk_len}
                    test_blocks = prev_blocks + [new_block]
                    
                    crash_cnt, rmse_p95, poem_c, res = eval_prefix(test_blocks, end_layer)
                    
                    if crash_cnt == 0:
                        # 0 crash sur tout le préfixe !
                        # Score : privilégier les blocs plus longs et les bons scores
                        score = len(test_blocks) * 1.0 - blk_len * 0.5
                        next_beam_candidates.append((end_layer, test_blocks, score))
                        print(f"  ✅ Bloc [{start_layer+1}..{end_layer}] ({blk_len} couches) @ {wl:.0f} nm -> 0 CRASH sur {end_layer}/35 couches !", flush=True)

        if not next_beam_candidates:
            print(f"⚠️ Aucun bloc n'a donné 0 crash à cette étape. Recherche du bloc au crash minimum...", flush=True)
            # Chercher le minimum de crash
            break

        # Trier et garder les meilleures extensions (les plus avancées dans le stack et les plus compactes)
        next_beam_candidates.sort(key=lambda x: (-x[0], len(x[1])))
        
        # Déduplication par end_layer
        seen_ends = set()
        beam = []
        for end_l, blks, sc in next_beam_candidates:
            sig = (end_l, tuple(b["wavelength"] for b in blks))
            if sig not in seen_ends:
                seen_ends.add(sig)
                beam.append((end_l, blks, sc))
            if len(beam) >= BEAM_WIDTH:
                break

        step += 1
        print(f"-> Fin d'étape {step-1} : {len(beam)} préfixes viables conservés (Avancement maximal : {max(e for e,_,_ in beam)}/35 couches)", flush=True)

    print("\n" + "=" * 80)
    print("BILAN FINAL DE LA RECHERCHE PAR BLOCS :")
    print("=" * 80)

    complete_strats = [item for item in beam if item[0] == num_layers]
    if complete_strats:
        print(f"\n🏆 TROUVÉ {len(complete_strats)} STRATÉGIES COMPLÈTES À 0% DE CRASH SUR LES 35 COUCHES !")
        for idx, (end_l, blks, sc) in enumerate(complete_strats):
            cr, rmse_p95, poem_c, _ = eval_prefix(blks, 35)
            wls_str = ", ".join(f"[{b['start']+1}..{b['end']}]: {b['wavelength']:.0f}nm" for b in blks)
            print(f"\n--- Stratégie #{idx+1} ({len(blks)} blocs) ---")
            print(f"  * Blocs : {wls_str}")
            print(f"  * Crash : {cr}/150 (0.0 %)")
            print(f"  * RMSE P95 : {rmse_p95:.4f}")
            print(f"  * POEM actif : {poem_c}/35")
    else:
        print(f"\nAvancement partiel maximal atteint : {max(e for e,_,_ in beam if beam)}/35 couches.")


if __name__ == "__main__":
    main()
