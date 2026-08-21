"""Recherche par Beam Search / Essais-Erreurs de stratégies par blocs (K <= 10) à 0% de crash sur le 35 couches.

Ne modifie aucun critère physique, cherche les combinaisons qui passent tous les tests existants.

Usage:
    .venv/Scripts/python.exe scripts/solve_35c_by_blocks.py
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
import numpy as np

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    print("EXPLORATION DIRECTE ESSAI/ERREUR : STRATÉGIES PAR BLOCS POUR LE 35 COUCHES")
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

    # Chargeons les longueurs d'ondes de référence de Phase A
    import json
    obs_file = ROOT / "reports" / "STRAT_observability_20260814_102134.json"
    with open(obs_file, "r", encoding="utf-8") as f:
        obs_data = json.load(f)
    ref_wls = [float(l["best_wl"]) for l in obs_data["layers"]]

    # Grille de longueurs d'onde pour les essais
    scan_wls = sorted(list(clues_at_wl.keys()))  # 450 à 700 nm

    # Fonction pour évaluer une stratégie complète ou partielle
    def score_strat(blocks):
        strat = {
            "strategy_id": 1234,
            "n_blocks": len(blocks),
            "blocks": blocks,
            "origin": "Candidate",
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
        poem_count = res.get("poem_anchored_layers_count", 0)
        crash_by_l = res.get("crash_by_layer", {}).get("total", [0] * num_layers)
        return crash_rate, rmse_p95, poem_count, crash_by_l, res

    print("\n--- ÉTAPE 1 : FUSION PROGRESSIVE PAR ESSAI/ERREUR (Fusions de couches adjacentes) ---", flush=True)
    # Partons d'une base et fusionnons des blocs adjacents tant que le crash reste à 0 ou diminue
    # Testons d'abord des regroupements par blocs de 2, 3, 4 couches :
    
    # 1. Regroupement par paires (18 blocs)
    # 2. Regroupement par triplets (12 blocs)
    # 3. Regroupement physique (7 blocs)
    # 4. Regroupement glouton : trouver la longueur d'onde de bloc optimale pour chaque groupe

    candidates_to_test = []

    # Générons 1000 variantes de blocs variés
    rng = np.random.default_rng(2026)

    # Architectures de blocs cibles :
    # A. 7 blocs physiques
    part_7 = [(0, 5), (5, 6), (6, 17), (17, 18), (18, 29), (29, 30), (30, 35)]
    # B. 9 blocs (miroirs longs coupés)
    part_9 = [(0, 5), (5, 6), (6, 12), (12, 17), (17, 18), (18, 24), (24, 29), (29, 30), (30, 35)]
    # C. 12 blocs (miroirs en blocs de 3-4 couches)
    part_12 = [
        (0, 3), (3, 5), (5, 6),
        (6, 10), (10, 14), (14, 17), (17, 18),
        (18, 22), (22, 26), (26, 29), (29, 30),
        (30, 35)
    ]
    # D. 16 blocs (blocs de 2-3 couches)
    part_16 = [
        (0, 2), (2, 5), (5, 6),
        (6, 9), (9, 12), (12, 15), (15, 17), (17, 18),
        (18, 21), (21, 24), (24, 27), (27, 29), (29, 30),
        (30, 32), (32, 35)
    ]

    all_partitions = [
        ("16 BLOCS", part_16),
        ("12 BLOCS", part_12),
        ("9 BLOCS", part_9),
        ("7 BLOCS", part_7),
    ]

    working_strategies = []

    for part_label, partition in all_partitions:
        print(f"\nExploration sur partition {part_label} ({len(partition)} blocs)...", flush=True)
        
        # Test avec longueurs d'ondes issues de la Phase A (moyenne ou mode sur le bloc)
        blks_phase_a = []
        for s, e in partition:
            # WL majoritaire ou médiane de Phase A sur ce segment
            seg_wls = ref_wls[s:e]
            chosen_wl = float(seg_wls[0])  # première couche du bloc
            blks_phase_a.append({"start": s, "end": e, "wavelength": chosen_wl, "num_layers": e - s})
        
        cr, r_p95, poem_c, crash_by_l, _ = score_strat(blks_phase_a)
        print(f"  * {part_label} (Phase A WLs) -> Crash: {cr*100:5.1f}% | RMSE P95: {r_p95:.4f} | POEM: {poem_c}/35", flush=True)
        if cr == 0.0:
            working_strategies.append((part_label, blks_phase_a, r_p95, poem_c))

        # Recherche par tirages aléatoires guidés sur cette partition
        best_cr = cr
        best_strat = blks_phase_a
        for trial in range(120):
            blks = []
            for s, e in partition:
                # Tirage d'une longueur d'onde parmi les candidates fortes ou autour des WLs de Phase A
                if rng.random() < 0.5:
                    w = float(rng.choice(ref_wls[s:e]))
                else:
                    w = float(rng.choice([450, 460, 470, 480, 490, 500, 520, 540, 560, 580, 600, 632, 650]))
                blks.append({"start": s, "end": e, "wavelength": w, "num_layers": e - s})
            
            cr, r_p95, poem_c, crash_by_l, _ = score_strat(blks)
            if cr < best_cr:
                best_cr = cr
                best_strat = blks
                print(f"    [Progression {part_label} #{trial+1}] Crash: {cr*100:5.1f}% (RMSE: {r_p95:.4f}, POEM: {poem_c}/35)", flush=True)
            if cr == 0.0:
                print(f"    🎉 TROUVÉ ! {part_label} Tirage #{trial+1} : CRASH = 0.0%, RMSE P95 = {r_p95:.4f}, POEM = {poem_c}/35", flush=True)
                working_strategies.append((part_label, blks, r_p95, poem_c))

    print("\n" + "=" * 80)
    print("RÉSULTAT DES ESSAIS / ERREURS :")
    print("=" * 80)
    if working_strategies:
        working_strategies.sort(key=lambda x: x[2] if not np.isnan(x[2]) else 1e9)
        print(f"\n🏆 {len(working_strategies)} STRATÉGIES PAR BLOCS ONT FONCTIONNÉ AVEC 0% DE PLANTAGE !")
        for idx, (p_name, blks, r_p95, poem_c) in enumerate(working_strategies):
            wls_str = ", ".join(f"[{b['start']}-{b['end']}]: {b['wavelength']:.0f}nm" for b in blks)
            print(f"\n--- Stratégie #{idx+1} : {p_name} ({len(blks)} blocs) ---")
            print(f"  * Structure des blocs : {wls_str}")
            print(f"  * RMSE P95 : {r_p95:.4f}")
            print(f"  * POEM actif : {poem_c} couches sur 35")
    else:
        print("\nAucune stratégie n'a atteint 0% de crash dans cette première salve. Continuons l'exploration ciblée.")


if __name__ == "__main__":
    main()
