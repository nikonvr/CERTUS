"""Test de regroupement spectral par clusters naturels autour de 462 nm sur le passe-bande 35 couches."""

from __future__ import annotations
import json
import logging
import numpy as np
from pathlib import Path
import bench_examples as B
import certus_physics
from certus_physics import calculate_RT_batch_kernel
from certus.core.certus_strat_config import get_refractive_index, get_refractive_clues_vectorized, precompute_clues_and_matrices
from certus.core.certus_strat_robustness import _test_strategy_robustness_task, _prepare_robustness_nominal_optics

ROOT = Path(__file__).resolve().parents[1]
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

logger = logging.getLogger("test")
logger.setLevel(logging.ERROR)
clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)
opti_results = {"clues_at_wl": clues_at_wl}
wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(params, p_thick_nominal, opti_results)
full_dyn_grid = {i: {float(w): 0.1 for w in clues_at_wl.keys()} for i in range(len(p_thick_nominal))}

target_wls = np.linspace(600.0, 660.0, 61)
db_instance = params.get("materials_db_instance") or params.get("materials_db")
nH_target = get_refractive_clues_vectorized(params["nH_id"], target_wls, db_instance=db_instance).astype(np.complex128)
nL_target = get_refractive_clues_vectorized(params["nL_id"], target_wls, db_instance=db_instance).astype(np.complex128)
nSub_target = get_refractive_clues_vectorized(params["nSub_id"], target_wls, db_instance=db_instance).astype(np.complex128)
_, T_target_nom_batch = calculate_RT_batch_kernel(target_wls, nH_target, nL_target, nSub_target, np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1))
T_target_nom = np.asarray(T_target_nom_batch, dtype=np.float64)[0]

# Regroupements progressifs à tester :
# 1. Regroupement des blocs 476nm et 461nm dans M2 et M3
# 2. M2 en 2 blocs (460nm), M3 en 2 blocs (460nm)

clusters_to_test = [
    ("CLUSTERS NATURELS (21 blocs)", [
        (0, 1, 491.0), (1, 2, 565.0), (2, 3, 450.0), (3, 4, 589.0), (4, 5, 490.0), # M1 (5)
        (5, 6, 639.0), # C1 (1)
        (6, 8, 458.0), (8, 11, 476.0), (11, 12, 452.0), (12, 15, 461.0), (15, 16, 476.0), (16, 17, 452.0), # M2 (6)
        (17, 18, 457.0), # C2 (1)
        (18, 21, 462.0), (21, 23, 451.0), (23, 25, 459.0), (25, 27, 467.0), (27, 28, 465.0), (28, 29, 456.0), # M3 (6)
        (29, 30, 454.0), # C3 (1)
        (30, 31, 461.0), (31, 33, 466.0), (33, 35, 455.0), # M4 (3)
    ]),
    ("CLUSTERS ÉLARGIS (15 blocs)", [
        (0, 2, 530.0), (2, 4, 520.0), (4, 5, 490.0), # M1 (3)
        (5, 6, 639.0), # C1 (1)
        (6, 11, 465.0), (11, 14, 460.0), (14, 17, 465.0), # M2 (3)
        (17, 18, 457.0), # C2 (1)
        (18, 23, 460.0), (23, 26, 460.0), (26, 29, 460.0), # M3 (3)
        (29, 30, 454.0), # C3 (1)
        (30, 33, 465.0), (33, 35, 455.0), # M4 (2)
    ]),
    ("CLUSTERS COMPACTS 462nm (10 blocs)", [
        (0, 3, 490.0), (3, 5, 520.0), # M1 (2)
        (5, 6, 639.0), # C1 (1)
        (6, 12, 462.0), (12, 17, 462.0), # M2 (2)
        (17, 18, 457.0), # C2 (1)
        (18, 24, 462.0), (24, 29, 462.0), # M3 (2)
        (29, 30, 454.0), # C3 (1)
        (30, 35, 462.0), # M4 (1)
    ]),
]

print("=" * 80)
print("TEST DES REGROUPEMENTS PAR CLUSTERS SPECTRAUX NATURELS (35 COUCHES)")
print("=" * 80)

for label, clist in clusters_to_test:
    blks = [{"start": s, "end": e, "wavelength": float(w), "num_layers": e - s} for s, e, w in clist]
    strat = {"strategy_id": 100, "n_blocks": len(blks), "blocks": blks, "origin": label}
    res = _test_strategy_robustness_task(
        strategy=strat, _strat_idx=0, noise_levels=[1.0], num_runs=150,
        p_thick_nominal=p_thick_nominal, clues_at_wl=clues_at_wl, params=params,
        wl_arr=wl_arr, nH_arr=nH_arr, nL_arr=nL_arr, nSub_arr=nSub_arr, T_nom=T_nom,
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

    print(f"\n--- {label} ({len(blks)} blocs) ---")
    print(f"  * Crash : {cr*100:5.1f} %")
    print(f"  * RMSE P95 (600-660nm) : {rmse_p95:.5f}")
    print(f"  * SEEL équivalent : {seel:.3f} nm")
    print(f"  * Crash par couche (total) : {res.get('crash_by_layer', {}).get('total')}")
