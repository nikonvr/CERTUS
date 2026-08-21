"""Sonde directe pour tester la simulation Monte-Carlo du passe-bande 35 couches avec des blocs physiques.

Usage:
    .venv/Scripts/python.exe scripts/test_35c_blocks.py
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
    print("=" * 78)
    print("TEST PHYSIQUE DU PASSE-BANDE 35 COUCHES AVEC DES STRATÉGIES PAR BLOCS")
    print("=" * 78)

    B.qapp()
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    json_path = ROOT / "example" / "example_strat" / "JSON-strat-bandpass-3cav.json"
    print(f"Chargement de la configuration : {json_path.name}")
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
    print(f"Nombre de couches : {num_layers}, l0 = {l0:.2f} nm")

    logger = logging.getLogger("certus_strat")
    logger.setLevel(logging.WARNING)
    for h in logger.handlers:
        h.setLevel(logging.WARNING)
    logging.getLogger().setLevel(logging.WARNING)
    
    clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)

    opti_results = {"clues_at_wl": clues_at_wl}
    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params, p_thick_nominal, opti_results
    )

    full_dyn_grid = {i: {float(w): 0.1 for w in clues_at_wl.keys()} for i in range(num_layers)}
    noise_levels = [1.0]
    num_runs = 150

    strategies = []

    # 0. Stratégie Phase A (les 35 longueurs d'ondes individuelles optimisées par Phase A)
    import json
    obs_file = ROOT / "reports" / "STRAT_observability_20260814_102134.json"
    with open(obs_file, "r", encoding="utf-8") as f:
        obs_data = json.load(f)
    phase_a_wls = [float(l["best_wl"]) for l in obs_data["layers"]]
    
    strat_phase_a = {
        "strategy_id": 35999,
        "n_blocks": 35,
        "blocks": [{"start": i, "end": i + 1, "wavelength": phase_a_wls[i], "num_layers": 1} for i in range(35)],
        "origin": "35 BLOCS (Sélection optimale Phase A)",
    }
    strategies.append(strat_phase_a)

    # 1. Stratégie 35 blocs (1 couche par bloc, tous à 632 nm)
    strat_35 = {
        "strategy_id": 3500,
        "n_blocks": 35,
        "blocks": [{"start": i, "end": i + 1, "wavelength": 632.0, "num_layers": 1} for i in range(35)],
        "origin": "35 BLOCS (Chaque couche isolée @ 632 nm)",
    }
    strategies.append(strat_35)

    strategies = [strat_phase_a]

    print(f"\nÉvaluation de {len(strategies)} stratégies sous {num_runs} tirages Monte-Carlo (Seed={params['robustness_seed']})...\n", flush=True)
    print(f"{'STRATÉGIE':<52} | {'BLOCS':<5} | {'CRASH':<8} | {'RMSE MED':<10} | {'RMSE P95':<10} | {'POEM OK':<8}", flush=True)
    print("-" * 107, flush=True)

    results = []
    for st in strategies:
        res = _test_strategy_robustness_task(
            strategy=st,
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
        crash_rate = res.get("crash_rate", 0.0)
        # Extraire RMSE depuis results_per_noise
        r_noise = res.get("results_per_noise", [])
        if r_noise:
            rmse_med = r_noise[0].get("rmse_median", float("nan"))
            rmse_p95 = r_noise[0].get("rmse_p95", float("nan"))
        else:
            rmse_med = float("nan")
            rmse_p95 = float("nan")
            
        poem_count = res.get("poem_anchored_layers_count", 0)
        origin = st.get("origin", f"ID {st['strategy_id']}")

        results.append({
            "origin": origin,
            "n_blocks": st["n_blocks"],
            "crash_rate": crash_rate,
            "rmse_med": rmse_med,
            "rmse_p95": rmse_p95,
            "poem_count": poem_count,
            "res": res,
        })
        print(f"\n--- {origin} ---", flush=True)
        print(f"  Crash total : {crash_rate*100:.1f} %", flush=True)
        print(f"  Causes : {res.get('crash_causes')}", flush=True)
        print(f"  Couche critique : {res.get('critical_layer')}", flush=True)
        crash_by_l = res.get("crash_by_layer", {})
        for cause_name, l_counts in crash_by_l.items():
            arr = np.array(l_counts)
            if np.any(arr > 0):
                print(f"  Cause '{cause_name}' :", flush=True)
                for i, cnt in enumerate(arr):
                    if cnt > 0:
                        blk_wl = [b["wavelength"] for b in st["blocks"] if b["start"] <= i < b["end"]][0]
                        print(f"    Couche {i+1:2d} (d_nom={p_thick_nominal[i]:.1f}nm, lambda={blk_wl:.0f}nm) : {cnt}/{num_runs} crash ({cnt/num_runs*100:.1f}%)", flush=True)

    print("\n" + "=" * 78, flush=True)
    print("BILAN MESURÉ :", flush=True)
    print("=" * 78, flush=True)

    valid_results = [r for r in results if r["crash_rate"] == 0.0]
    if valid_results:
        valid_results.sort(key=lambda x: x["rmse_p95"] if not np.isnan(x["rmse_p95"]) else 1e9)
        print(f"\n✅ {len(valid_results)} stratégies ont un TAUX DE PLANTAGE STRICTEMENT NUL (0.0 %) :", flush=True)
        for r in valid_results:
            print(f"  * {r['origin']} -> RMSE P95 = {r['rmse_p95']:.4f} | POEM ancré = {r['poem_count']}/35", flush=True)
    else:
        print("\nAucune stratégie à crash_rate = 0 parmi les tests simples.", flush=True)
        # Afficher la meilleure stratégie (avec le plus bas crash rate)
        results.sort(key=lambda x: (x["crash_rate"], x["rmse_p95"] if not np.isnan(x["rmse_p95"]) else 1e9))
        print(f"\nStratégie la moins fragile : {results[0]['origin']} (Crash: {results[0]['crash_rate']*100:.1f}%)", flush=True)




if __name__ == "__main__":
    main()
