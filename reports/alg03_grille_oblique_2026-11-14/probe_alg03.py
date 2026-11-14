"""ALG-03 probe: does DESIGN's final refinement in oblique mode see the densified wavelength grid?

    python reports/alg03_grille_oblique_2026-11-14/probe_alg03.py [--out FILE.json]

Port of R03/R04 from reports/ARGON_contre_audit_2026-10-16/pass02.py.txt to the current code. The real OptimWorker.run
and its JIT optics run; only the global search is replaced by a fixed initial candidate (one 3000 nm layer on a 2-point
grid). For each mode it records the grid sizes seen by every cost and gradient call during the final refinement, the
RMSE the worker reports, and the RMSE of the same thicknesses recomputed directly on the densified grid.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "certus_alg03_jit"))

import numpy as np  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

APP = QApplication.instance() or QApplication([])


class Material:
    def __init__(self, n):
        self.n = n
        self.n4 = n

    def get_nk(self, wls):
        return np.full(len(wls), self.n, dtype=np.complex128)


def config(oblique):
    from certus_physics.structures import Layer, ObliqueTarget, Target
    return dict(mats={"H": Material(2.1), "Substrate": Material(1.52)},
                stack=[Layer("H", 1.0, True)], ep0=np.array([3000.0]), ep_back=np.array([]),
                wls=np.array([400.0, 700.0]), tgts=[Target(400.0, 700.0, 0.9, 0.9)],
                oblique_tgts=[ObliqueTarget(45.0, "S", 400.0, 700.0, 0.9, 0.9)],
                oblique_mode=oblique, l0=550.0, back=False, mode="global",
                pre_polish=False, local_delta_nm=2.0)


def worker_grid(oblique):
    from certus.core import certus_design_worker_utils as utils
    from certus.workers import certus_design_workers as mod
    worker = mod.OptimWorker(config(oblique))
    emitted, errors, grids, gradient_grids, cost_grids = [], [], [], [], []
    worker.signals.finished.connect(emitted.append)
    worker.signals.error.connect(errors.append)
    original_refine = mod.run_coord_descent_5cycles
    original_gradient = worker._get_gradient_analytic
    original_cost = worker._evaluate_thicknesses
    refining = []

    def size(kwargs):
        if oblique:
            return sum(len(c["wls_config"]) for c in worker._oblique_configs)
        return len(kwargs["wls"])

    def gradient(ep, **kwargs):
        if refining:
            gradient_grids.append(size(kwargs))
        return original_gradient(ep, **kwargs)

    def cost(ep, **kwargs):
        if refining:
            cost_grids.append(size(kwargs))
        return original_cost(ep, **kwargs)

    def refine(**kwargs):
        refining.append(True)
        grids.append({"local_wls": kwargs["wls"].copy(), "n_sub": kwargs["n_sub"].copy(),
                      "n_layers_T": kwargs["n_layers_T"].copy(), "tgt_vals": kwargs["tgt_vals"],
                      "tgt_weights": kwargs["tgt_weights"]})
        return original_refine(**kwargs)

    def candidate(**kwargs):
        ep = worker.cfg["ep0"].copy()
        return SimpleNamespace(x=ep, y=worker._objective_wrapper(ep))

    with patch.object(worker, "_run_pglobal_setup", return_value=(None, time.time())), \
         patch.object(mod, "run_pglobal_restart_loop", side_effect=candidate), \
         patch.object(mod, "run_coord_descent_5cycles", side_effect=refine), \
         patch.object(worker, "_get_gradient_analytic", side_effect=gradient), \
         patch.object(worker, "_evaluate_thicknesses", side_effect=cost):
        worker.run()
    if errors or len(emitted) != 1 or not grids:
        return {"error": [str(e)[:2000] for e in errors], "emitted": len(emitted), "refine_calls": len(grids)}
    g = grids[0]
    ep = np.asarray(emitted[0]["ep"], dtype=np.float64)
    if oblique:
        groups = utils.optim_oblique_group_targets_on_wavelengths(g["local_wls"], worker.cfg["oblique_tgts"])
        dense = utils.optim_oblique_configs_from_groups(groups, g["local_wls"], g["n_sub"], g["n_layers_T"])
        utils.optim_oblique_attach_local_positions(dense)
        for c in dense:
            c["sw_cfg"] = utils.optim_oblique_config_weights(c)
        with patch.object(worker, "_oblique_configs", dense):
            direct_cost = worker._compute_oblique_error(ep)
    else:
        from certus.physics.gradient_utils import cost_numba_fast
        direct_cost = cost_numba_fast(ep, g["n_layers_T"], g["n_sub"], g["local_wls"], g["tgt_vals"],
                                      g["tgt_weights"], 0.0, False, np.zeros((0, 0), dtype=np.complex128),
                                      np.array([]))
    return {"mode": "oblique" if oblique else "normal", "initial_points": 2,
            "refine_grid_points": len(g["local_wls"]),
            "gradient_grid_sizes": sorted(set(gradient_grids)), "cost_grid_sizes": sorted(set(cost_grids)),
            "final_ep": ep.tolist(), "reported_rmse": float(emitted[0]["rmse"]),
            "direct_dense_rmse": float(np.sqrt(direct_cost))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = {}
    for oblique in (True, False):
        try:
            result["oblique" if oblique else "normal"] = worker_grid(oblique)
        except Exception as exc:  # a probe reports, it does not stop at the first mode
            result["oblique" if oblique else "normal"] = {"exception": f"{type(exc).__name__}: {exc}"[:2000]}
    text = json.dumps(result, indent=2)
    print("ALG03=" + json.dumps(result))
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
