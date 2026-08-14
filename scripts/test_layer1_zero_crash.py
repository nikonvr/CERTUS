"""Test fin de la couche 1 pour trouver les longueurs d'ondes où le crash est STRICTEMENT 0/150.

Usage:
    .venv/Scripts/python.exe scripts/test_layer1_zero_crash.py
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
    print("RECHERCHE DES LONGUEURS D'ONDES À 0 CRASH SUR LA COUCHE 1 (Nb2O5, 68.1 nm)")
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

    # Inspectons la couche 1 à 700 nm
    strat_700 = {
        "strategy_id": 700,
        "n_blocks": 35,
        "blocks": [{"start": 0, "end": 1, "wavelength": 700.0, "num_layers": 1}] + [
            {"start": j, "end": j + 1, "wavelength": 632.0, "num_layers": 1} for j in range(1, 35)
        ],
        "origin": "L1 @ 700nm",
    }
    res = _test_strategy_robustness_task(
        strategy=strat_700,
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
    print(f"Clés dans res : {list(res.keys())}", flush=True)
    r_noise = res.get("results_per_noise", [])
    print(f"Nombre d'éléments dans results_per_noise : {len(r_noise)}", flush=True)
    if r_noise:
        print(f"Clés dans results_per_noise[0] : {list(r_noise[0].keys())}", flush=True)
        sim_thick = np.array(r_noise[0].get("thicknesses_all"))
        if sim_thick is not None:
            crashed_idx = np.where(sim_thick[:, 0] > 1e5)[0]
            print(f"Indices des tirages en crash sur Layer 1 ({len(crashed_idx)}/{num_runs}) : {crashed_idx}", flush=True)
            print(f"Valeurs sim_thick des tirages en crash : {sim_thick[crashed_idx, 0]}", flush=True)
            causes = np.floor(sim_thick[crashed_idx, 0] / 1e6)
            print(f"Causes exactes (1=Unreachable, 2=TP_Miscount, 3=NonMonotonic) : {causes}", flush=True)


if __name__ == "__main__":
    main()
