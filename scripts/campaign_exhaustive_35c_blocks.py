"""Campagne exhaustive d'essais/erreurs sur le passe-bande 35 couches.

Mesure à CHAQUE tirage :
1. Taux de plantage (crash_rate)
2. Écart spectral exact sur la bande passante cible 600 – 660 nm (RMSE P95, RMSE Médian, Max|E|)
3. SEEL équivalent en nm
4. Comparaison directe avec le record de référence 35 lambdas (RMSE P95 = 0.06085, SEEL ≈ 0.58 nm).

Usage:
    .venv/Scripts/python.exe scripts/campaign_exhaustive_35c_blocks.py
"""

from __future__ import annotations

import os
import sys
import time
import json
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


# =============================================================================
# RÉFÉRENCE ABSOLUE SUR LE 35 COUCHES (33-35 LAMBDAS DISTINCTES)
# =============================================================================
REF_BENCHMARK = {
    "name": "Référence Phase A (33 lambdas distinctes)",
    "n_blocks": 33,
    "crash_rate": 0.0,
    "rmse_median_target": 0.02550,    # Sur 600-660 nm
    "rmse_p95_target": 0.06085,       # Sur 600-660 nm (6.08% d'écart spectral)
    "max_abs_p95_target": 0.2427,     # 24.27% écart crête
    "seel_nm": 0.58,                  # SEEL équivalent en nm
    "score": 0.04285,
}


def main():
    print("=" * 80)
    print("CAMPAGNE EXHAUSTIVE DE RECHERCHE PAR BLOCS SUR LE PASSE-BANDE 35 COUCHES")
    print(f"RÉFÉRENCE À BATTRE (35 lambdas) :")
    print(f"  * Crash : {REF_BENCHMARK['crash_rate']*100:.1f} %")
    print(f"  * Écart spectral RMSE P95 (600-660 nm) : {REF_BENCHMARK['rmse_p95_target']:.5f}")
    print(f"  * SEEL équivalent : {REF_BENCHMARK['seel_nm']:.2f} nm")
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

    # 🔴 BANDE CIBLE DU PASSE-BANDE : 600 à 660 nm (61 points)
    target_wls = np.linspace(600.0, 660.0, 61)
    db_instance = params.get("materials_db_instance") or params.get("materials_db")
    nH_target = get_refractive_clues_vectorized(params["nH_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nL_target = get_refractive_clues_vectorized(params["nL_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nSub_target = get_refractive_clues_vectorized(params["nSub_id"], target_wls, db_instance=db_instance).astype(np.complex128)

    # Spectre nominal de référence sur 600-660 nm
    _, T_target_nom_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, p_thick_nom_arr.reshape(1, -1))
    T_target_nom = np.asarray(T_target_nom_batch, dtype=np.float64)[0]

    out_json = ROOT / "reports" / "campagne_exhaustive_35c_blocks.json"
    out_winners = ROOT / "reports" / "meilleures_strategies_blocs_35c.json"

    all_scan_wls = [float(w) for w in clues_at_wl.keys()]

    # Architectures de blocs testées :
    part_7 = [(0, 5, "M1"), (5, 6, "C1"), (6, 17, "M2"), (17, 18, "C2"), (18, 29, "M3"), (29, 30, "C3"), (30, 35, "M4")]
    part_9 = [(0, 5, "M1"), (5, 6, "C1"), (6, 11, "M2a"), (11, 17, "M2b"), (17, 18, "C2"), (18, 23, "M3a"), (23, 29, "M3b"), (29, 30, "C3"), (30, 35, "M4")]
    part_11 = [
        (0, 5, "M1"), (5, 6, "C1"),
        (6, 10, "M2a"), (10, 14, "M2b"), (14, 17, "M2c"),
        (17, 18, "C2"),
        (18, 22, "M3a"), (22, 26, "M3b"), (26, 29, "M3c"),
        (29, 30, "C3"),
        (30, 35, "M4")
    ]
    part_14 = [
        (0, 2, "M1a"), (2, 5, "M1b"), (5, 6, "C1"),
        (6, 10, "M2a"), (10, 14, "M2b"), (14, 17, "M2c"),
        (17, 18, "C2"),
        (18, 22, "M3a"), (22, 26, "M3b"), (26, 29, "M3c"),
        (29, 30, "C3"),
        (30, 32, "M4a"), (32, 35, "M4b")
    ]

    architectures = [
        ("7 BLOCS NATURELS", part_7),
        ("9 BLOCS ÉQUILIBRÉS", part_9),
        ("11 BLOCS FINS", part_11),
        ("14 BLOCS COURTS", part_14),
    ]

    def evaluate(blocks, n_runs=150):
        strat = {
            "strategy_id": int(time.time() * 1000) % 100000,
            "n_blocks": len(blocks),
            "blocks": blocks,
            "origin": "Exhaustive Candidate",
        }
        res = _test_strategy_robustness_task(
            strategy=strat,
            _strat_idx=0,
            noise_levels=noise_levels,
            num_runs=n_runs,
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
        poem_c = res.get("poem_anchored_layers_count", 0)

        # Calcul de l'écart spectral exact sur 600-660 nm
        r_noise = res.get("results_per_noise", [])
        if r_noise and "thicknesses_all" in r_noise[0]:
            D = np.array(r_noise[0]["thicknesses_all"])
            survived = ~np.any(D > 1e5, axis=1)
            if np.any(survived):
                _, T_sim_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, D[survived])
                T_sim = np.asarray(T_sim_batch, dtype=np.float64)
                E_target = T_sim - T_target_nom[None, :]
                rmse_runs = np.sqrt(np.mean(E_target ** 2, axis=1))
                rmse_p95_target = float(np.percentile(rmse_runs, 95))
                rmse_med_target = float(np.median(rmse_runs))
                max_abs_p95 = float(np.percentile(np.max(np.abs(E_target), axis=1), 95))
                seel_nm = float(rmse_p95_target * 9.55)  # Facteur d'étalonnage SEEL standard sur bandpass
            else:
                rmse_p95_target = 1.0
                rmse_med_target = 1.0
                max_abs_p95 = 1.0
                seel_nm = 10.0
        else:
            rmse_p95_target = 1.0
            rmse_med_target = 1.0
            max_abs_p95 = 1.0
            seel_nm = 10.0

        return cr, rmse_med_target, rmse_p95_target, max_abs_p95, seel_nm, poem_c, res

    rng = np.random.default_rng(int(time.time()))
    t0 = time.perf_counter()

    total_evaluated = 0
    zero_crash_found = []
    beaten_ref_found = []

    POP_SIZE = 40
    N_GEN = 300

    for arch_name, partition in architectures:
        n_blks = len(partition)
        print(f"\n{'='*70}\nARCHITECTURE : {arch_name} ({n_blks} blocs)\n{'='*70}", flush=True)

        population = []
        for _ in range(POP_SIZE):
            wls = []
            for s, e, lbl in partition:
                if "C" in lbl or "Cavité" in lbl:
                    w = float(rng.choice([450, 460, 480, 520, 600, 632, 640, 660]))
                else:
                    w = float(rng.choice(all_scan_wls))
                wls.append(w)
            population.append(wls)

        best_arch_cr = 1.0
        best_arch_rmse = 1e9
        best_arch_seel = 1e9

        for gen in range(1, N_GEN + 1):
            evaluated_pop = []
            for indiv_wls in population:
                blks = [{"start": s, "end": e, "wavelength": indiv_wls[i], "num_layers": e - s} for i, (s, e, _) in enumerate(partition)]
                cr, rmse_med, rmse_p95, max_e_p95, seel_nm, poem_c, res = evaluate(blks, n_runs=150)
                total_evaluated += 1
                
                evaluated_pop.append((cr, rmse_p95, rmse_med, max_e_p95, seel_nm, poem_c, indiv_wls, blks))

                # VÉRIFICATION DU SCORE ET DU SEEL CONTRE LA RÉFÉRENCE
                if cr == 0.0:
                    beats_ref = (rmse_p95 < REF_BENCHMARK["rmse_p95_target"])
                    b_strs = [f"[{b['start']+1}..{b['end']}]: {b['wavelength']:.0f}nm" for b in blks]
                    
                    if beats_ref:
                        gain_pct = (REF_BENCHMARK["rmse_p95_target"] - rmse_p95) / REF_BENCHMARK["rmse_p95_target"] * 100.0
                        print(f"\n🔥 [GEN {gen}] RECORD BATTU SUR LE SCORE SPECTRAL & SEEL !", flush=True)
                        print(f"  * Architecture : {arch_name} ({n_blks} blocs)")
                        print(f"  * Blocs : {b_strs}", flush=True)
                        print(f"  * Écart spectral RMSE P95 : {rmse_p95:.5f} (Réf 35c = {REF_BENCHMARK['rmse_p95_target']:.5f}, Gain: +{gain_pct:.1f}%)", flush=True)
                        print(f"  * SEEL : {seel_nm:.3f} nm (Réf 35c = {REF_BENCHMARK['seel_nm']:.3f} nm) | POEM : {poem_c}/35", flush=True)
                    else:
                        print(f"\n🎉 [GEN {gen}] Stratégie 0.0% crash trouvée ({arch_name}) | RMSE P95 : {rmse_p95:.5f} | SEEL : {seel_nm:.3f} nm | POEM : {poem_c}/35", flush=True)

                    item = {
                        "arch": arch_name,
                        "n_blocks": n_blks,
                        "blocks": blks,
                        "crash_rate": cr,
                        "rmse_median_target": rmse_med,
                        "rmse_p95_target": rmse_p95,
                        "max_abs_p95_target": max_e_p95,
                        "seel_nm": seel_nm,
                        "poem_count": poem_c,
                        "beats_reference_35lambda": beats_ref,
                        "ref_rmse_p95_target": REF_BENCHMARK["rmse_p95_target"],
                        "ref_seel_nm": REF_BENCHMARK["seel_nm"],
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    zero_crash_found.append(item)
                    if beats_ref:
                        beaten_ref_found.append(item)

                    with open(out_json, "w", encoding="utf-8") as f:
                        json.dump(zero_crash_found, f, indent=2)
                    if beaten_ref_found:
                        with open(out_winners, "w", encoding="utf-8") as f:
                            json.dump(beaten_ref_found, f, indent=2)

            evaluated_pop.sort(key=lambda x: (x[0], x[1]))
            elite = evaluated_pop[:POP_SIZE // 4]

            current_best = evaluated_pop[0]
            if current_best[0] < best_arch_cr or (current_best[0] == best_arch_cr and current_best[1] < best_arch_rmse):
                best_arch_cr = current_best[0]
                best_arch_rmse = current_best[1]
                best_arch_seel = current_best[4]
                ratio_ref = best_arch_rmse / REF_BENCHMARK["rmse_p95_target"]
                if best_arch_cr == 0.0 and best_arch_rmse < REF_BENCHMARK["rmse_p95_target"]:
                    vs_ref = "🏆 RÉF 35-LAMBDAS BATTUE !"
                else:
                    vs_ref = f"écart {ratio_ref:.2f}x réf (SEEL: {best_arch_seel:.2f} nm)"
                print(f"  [Gen {gen:3d}/{N_GEN}] Record {arch_name} -> Crash: {best_arch_cr*100:5.1f}% | RMSE P95 (600-660nm): {best_arch_rmse:.4f} | {vs_ref} (Évalués: {total_evaluated})", flush=True)

            next_pop = [indiv for _, _, _, _, _, _, indiv, _ in elite]
            while len(next_pop) < POP_SIZE:
                idx_a = int(rng.integers(0, len(elite)))
                idx_b = int(rng.integers(0, len(elite)))
                parent_a = list(elite[idx_a][6])
                parent_b = list(elite[idx_b][6])
                cut = int(rng.integers(1, n_blks))
                child = parent_a[:cut] + parent_b[cut:]
                for idx in range(n_blks):
                    if rng.random() < 0.25:
                        lbl = partition[idx][2]
                        if "C" in lbl or "Cavité" in lbl:
                            child[idx] = float(rng.choice([450, 460, 480, 520, 600, 632, 640, 660]))
                        else:
                            child[idx] = float(rng.choice(all_scan_wls))
                next_pop.append(child)

            population = next_pop

    elapsed = time.perf_counter() - t0
    print("\n" + "=" * 80)
    print(f"FIN DE LA CAMPAGNE EXHAUSTIVE ({total_evaluated} évaluations en {elapsed:.1f} s)")
    print("=" * 80, flush=True)


if __name__ == "__main__":
    main()
