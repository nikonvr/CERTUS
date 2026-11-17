"""Chantier 21 : l'ecart allumee/eteinte (d 1667 contre 1699 nm) vient-il du budget des differences finies ?

Option eteinte, budgets L-BFGS-B (`pglobal.polish_maxfun`, `stage_mandatory_local_maxfun`) par defaut puis x5 ; option
allumee au budget par defaut. Pour chacun : duree, evaluations de cout, RMSE, d, n et k a 600 et 1000 nm, NaN dans n_lam.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_budget_check.py
"""
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(".").resolve()))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import certus_physics  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
certus_physics.warmup_physics()

from certus.spline import spline_objective  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

spline_app = CertusIndexSplineApp()
spline_app._on_load(path=str(Path("example/example_index_spline/TSIO2-1700-1.xlsx").resolve()))
base = spline_app._build_opt_config(notify=False)
pm0 = int(base.pglobal.polish_maxfun)
sm0 = int(getattr(base, "stage_mandatory_local_maxfun", 0) or 0)
print(f"budgets par defaut : polish_maxfun={pm0} stage_mandatory_local_maxfun={sm0}")

counts = {"cost": 0}
_call = spline_objective.SplinePWLObjective.__call__


def _counted_call(self, xv):
    counts["cost"] += 1
    return _call(self, xv)


spline_objective.SplinePWLObjective.__call__ = _counted_call


def run(on: bool, factor: int) -> None:
    cfg = base.replace(spline_mono_analytic_gradient=on)
    cfg.pglobal.polish_maxfun = pm0 * factor
    if sm0:
        cfg.stage_mandatory_local_maxfun = sm0 * factor
    counts["cost"] = 0
    t0 = time.perf_counter()
    r = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None,
                                   live_cb=lambda *a, **k: None)
    dt = time.perf_counter() - t0
    lam = np.asarray(r["lam_nm"], float)
    n = np.asarray(r["n_lam"], float)
    k = np.asarray(r["k_lam"], float)
    at = {w: int(np.argmin(np.abs(lam - w))) for w in (600.0, 1000.0)}
    print(f"option={'allumee' if on else 'eteinte'} budget x{factor} : {dt:.2f} s, {counts['cost']} couts, "
          f"RMSE={r['rmse']:.10f} d={r['d_nm']:.4f} nm, n600={n[at[600.0]]:.5f} n1000={n[at[1000.0]]:.5f} "
          f"k600={k[at[600.0]]:.3e} | NaN n_lam {int(np.isnan(n).sum())}/{n.size}, k_lam {int(np.isnan(k).sum())}")


run(False, 1)  # Numba warm-up, also the reference
run(False, 1)
run(True, 1)
run(False, 5)
