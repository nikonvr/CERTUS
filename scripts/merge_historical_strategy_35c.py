"""Regroupement progressif (Bottom-Up Smart Merge) à partir de la stratégie historique à 35 lambdas.

Principe :
1. Part de la stratégie gagnante à 35 lambdas (0% crash, RMSE P95 = 0.06085).
2. Tente à chaque étape de fusionner 2 blocs adjacents en testant la longueur d'onde optimale du groupe.
3. Ne conserve la fusion QUE si le taux de plantage reste STRICTEMENT à 0.0%.
4. Mesure l'évolution du SEEL et de l'écart spectral à chaque réduction de bloc (35 -> 34 -> ... -> K).

Usage:
    .venv/Scripts/python.exe scripts/merge_historical_strategy_35c.py
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


REF_BENCHMARK = {
    "name": "Référence Phase A (33-35 lambdas)",
    "n_blocks": 33,
    "crash_rate": 0.0,
    "rmse_p95_target": 0.06085,
    "seel_nm": 0.58,
}


def main():
    print("=" * 80)
    print("REGROUPEMENT PROGRESSIF À PARTIR DE LA STRATÉGIE HISTORIQUE DU 35 COUCHES")
    print(f"RÉFÉRENCE INITIALE : Crash = 0.0% | RMSE P95 (600-660nm) = {REF_BENCHMARK['rmse_p95_target']:.5f} | SEEL = {REF_BENCHMARK['seel_nm']:.2f} nm")
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

    # Bande cible 600 - 660 nm
    target_wls = np.linspace(600.0, 660.0, 61)
    db_instance = params.get("materials_db_instance") or params.get("materials_db")
    nH_target = get_refractive_clues_vectorized(params["nH_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nL_target = get_refractive_clues_vectorized(params["nL_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    nSub_target = get_refractive_clues_vectorized(params["nSub_id"], target_wls, db_instance=db_instance).astype(np.complex128)
    _, T_target_nom_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, p_thick_nom_arr.reshape(1, -1))
    T_target_nom = np.asarray(T_target_nom_batch, dtype=np.float64)[0]

    # Charger la stratégie historique issue du rapport d'observabilité
    obs_file = ROOT / "reports" / "STRAT_observability_20260814_102134.json"
    with open(obs_file, "r", encoding="utf-8") as f:
        obs_data = json.load(f)
    historical_wls = [float(l["best_wl"]) for l in obs_data["layers"]]

    def evaluate_blocks(blocks):
        strat = {
            "strategy_id": 9999,
            "n_blocks": len(blocks),
            "blocks": blocks,
            "origin": f"Merged {len(blocks)} blocks",
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
        poem_c = res.get("poem_anchored_layers_count", 0)

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
                seel_nm = float(rmse_p95_target * 9.55)
            else:
                rmse_p95_target = 1.0
                rmse_med_target = 1.0
                seel_nm = 10.0
        else:
            rmse_p95_target = 1.0
            rmse_med_target = 1.0
            seel_nm = 10.0

        return cr, rmse_med_target, rmse_p95_target, seel_nm, poem_c, res

    # 1. État initial : 35 blocs individuels avec les lambdas historiques
    current_blocks = [
        {"start": i, "end": i + 1, "wavelength": float(historical_wls[i]), "num_layers": 1}
        for i in range(num_layers)
    ]

    print("\n--- TEST DU POINT DE DÉPART (35 blocs individuels) ---", flush=True)
    cr, rmse_med, rmse_p95, seel_nm, poem_c, _ = evaluate_blocks(current_blocks)
    print(f"Point de départ (35 blocs) -> Crash: {cr*100:.1f}% | RMSE P95 (600-660nm): {rmse_p95:.5f} | SEEL: {seel_nm:.3f} nm | POEM: {poem_c}/35", flush=True)

    history = [{
        "n_blocks": len(current_blocks),
        "blocks": list(current_blocks),
        "crash_rate": cr,
        "rmse_p95": rmse_p95,
        "seel_nm": seel_nm,
        "poem_count": poem_c,
    }]

    # 2. Boucle de fusion gloutonne : à chaque étape, tester la fusion de chaque paire de blocs adjacents (i, i+1)
    # avec différentes options de longueurs d'onde (wl_i, wl_{i+1}, moyenne, ou balayage local).
    # Choisir la fusion qui conserve 0% de crash avec le meilleur score SEEL.

    step = 1
    while len(current_blocks) > 1:
        print(f"\n{'='*70}\nÉTAPE {step} : Tentative de fusion ({len(current_blocks)} blocs -> {len(current_blocks)-1} blocs)\n{'='*70}", flush=True)
        best_merge_candidate = None
        best_merge_score = (1.0, 1e9)  # (crash_rate, rmse_p95)

        for i in range(len(current_blocks) - 1):
            b1 = current_blocks[i]
            b2 = current_blocks[i + 1]

            # Longueurs d'onde candidates pour le bloc fusionné :
            wl_cands = [b1["wavelength"], b2["wavelength"], round((b1["wavelength"] + b2["wavelength"]) / 2.0)]
            # Ajouter les longueurs d'ondes de scan proches
            wl_cands.extend([b1["wavelength"] - 5.0, b1["wavelength"] + 5.0, b2["wavelength"] - 5.0, b2["wavelength"] + 5.0])
            wl_cands = sorted(list(set(w for w in wl_cands if 450 <= w <= 700)))

            for test_wl in wl_cands:
                merged_block = {
                    "start": b1["start"],
                    "end": b2["end"],
                    "wavelength": float(test_wl),
                    "num_layers": b1["num_layers"] + b2["num_layers"],
                }
                test_blocks = current_blocks[:i] + [merged_block] + current_blocks[i + 2:]

                cr_m, med_m, p95_m, seel_m, poem_m, _ = evaluate_blocks(test_blocks)

                if cr_m == 0.0:
                    print(f"  ✅ Fusion possible Blocs {i+1} & {i+2} (Couches {merged_block['start']+1}..{merged_block['end']}) @ {test_wl:.0f} nm -> 0% CRASH ! (RMSE: {p95_m:.5f}, SEEL: {seel_m:.3f} nm)", flush=True)

                if (cr_m < best_merge_score[0]) or (cr_m == best_merge_score[0] and p95_m < best_merge_score[1]):
                    best_merge_score = (cr_m, p95_m)
                    best_merge_candidate = (test_blocks, cr_m, med_m, p95_m, seel_m, poem_m, i, test_wl)

        if best_merge_candidate is None or best_merge_candidate[1] > 0.0:
            print(f"\n⚠️ Aucune fusion directe à 0% de crash n'a été trouvée depuis cet état ({len(current_blocks)} blocs).", flush=True)
            if best_merge_candidate:
                print(f"   Meilleure fusion partielle : Crash = {best_merge_candidate[1]*100:.1f}%, RMSE = {best_merge_candidate[3]:.5f}")
            break

        # Appliquer la meilleure fusion
        current_blocks, cr_cur, med_cur, p95_cur, seel_cur, poem_cur, merged_idx, chosen_wl = best_merge_candidate
        print(f"\n🎯 FUSION RETENUE #{step} : {len(current_blocks)+1} -> {len(current_blocks)} BLOCS !")
        print(f"  * Blocs fusionnés : #{merged_idx+1} et #{merged_idx+2} @ {chosen_wl:.0f} nm")
        print(f"  * Crash : {cr_cur*100:.1f}% | RMSE P95 (600-660nm) : {p95_cur:.5f} | SEEL : {seel_cur:.3f} nm | POEM : {poem_cur}/35", flush=True)

        history.append({
            "n_blocks": len(current_blocks),
            "blocks": list(current_blocks),
            "crash_rate": cr_cur,
            "rmse_p95": p95_cur,
            "seel_nm": seel_cur,
            "poem_count": poem_cur,
        })
        step += 1

    # Rapport final
    out_file = ROOT / "reports" / "regroupement_historique_35c.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print("\n" + "=" * 80)
    print("BILAN DU REGROUPEMENT PROGRESSIF DEPUIS LA STRATÉGIE HISTORIQUE :")
    print("=" * 80)
    for h in history:
        vs_ref = "🏆 BATTU !" if (h["crash_rate"] == 0.0 and h["rmse_p95"] < REF_BENCHMARK["rmse_p95_target"]) else f"écart {(h['rmse_p95']/REF_BENCHMARK['rmse_p95_target']):.2f}x"
        print(f"  * {h['n_blocks']:2d} BLOCS -> Crash: {h['crash_rate']*100:4.1f}% | RMSE P95: {h['rmse_p95']:.5f} | SEEL: {h['seel_nm']:.3f} nm | POEM: {h['poem_count']:2d}/35 | {vs_ref}")


if __name__ == "__main__":
    main()
