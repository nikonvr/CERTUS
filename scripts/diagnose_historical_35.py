"""Diagnostique où crashe la stratégie à 35 lambdas."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import bench_examples as B
from certus.core.certus_strat_config import get_refractive_index, precompute_clues_and_matrices
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

import logging
logger = logging.getLogger("test")
logger.setLevel(logging.ERROR)
clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)
opti_results = {"clues_at_wl": clues_at_wl}
wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(params, p_thick_nominal, opti_results)
full_dyn_grid = {i: {float(w): 0.1 for w in clues_at_wl.keys()} for i in range(len(p_thick_nominal))}

with open(ROOT / "reports" / "STRAT_observability_20260814_102134.json", "r") as f:
    obs = json.load(f)
wls = [float(l["best_wl"]) for l in obs["layers"]][:len(p_thick_nominal)]
print(f"Nombre de couches chargées : {len(wls)} / {len(p_thick_nominal)}")

blocks = [{"start": i, "end": i+1, "wavelength": w, "num_layers": 1} for i, w in enumerate(wls)]
strat = {"strategy_id": 1, "n_blocks": 35, "blocks": blocks, "origin": "Obs"}

res = _test_strategy_robustness_task(
    strategy=strat, _strat_idx=0, noise_levels=[1.0], num_runs=150,
    p_thick_nominal=p_thick_nominal, clues_at_wl=clues_at_wl, params=params,
    wl_arr=wl_arr, nH_arr=nH_arr, nL_arr=nL_arr, nSub_arr=nSub_arr, T_nom=T_nom,
    full_dyn_grid=full_dyn_grid,
)
print("Crash rate :", res.get("crash_rate"))
print("Crash by layer :", res.get("crash_by_layer"))
print("Crash causes :", res.get("crash_causes"))
