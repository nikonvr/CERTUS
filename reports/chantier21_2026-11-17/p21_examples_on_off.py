"""Chantier 21 : l'option allumee contre eteinte sur chaque exemple d'INDEX SPLINE, puis eteinte a budget x5.

Pour chaque classeur de `example/example_index_spline/` : configuration de la fenetre, un calcul eteint (chauffe Numba,
aussi la reference), un allume, un eteint aux budgets L-BFGS-B x5. Duree, evaluations de cout, RMSE, d, n a 1000 nm et
n(1000)*d (epaisseur optique), NaN dans n_lam.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_examples_on_off.py
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

counts = {"cost": 0}
_call = spline_objective.SplinePWLObjective.__call__


def _counted_call(self, xv):
    counts["cost"] += 1
    return _call(self, xv)


spline_objective.SplinePWLObjective.__call__ = _counted_call


def run(base, on: bool, factor: int) -> None:
    cfg = base.replace(spline_mono_analytic_gradient=on)
    cfg.pglobal.polish_maxfun = int(base.pglobal.polish_maxfun) * factor
    sm0 = int(getattr(base, "stage_mandatory_local_maxfun", 0) or 0)
    if sm0:
        cfg.stage_mandatory_local_maxfun = sm0 * factor
    counts["cost"] = 0
    t0 = time.perf_counter()
    r = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None,
                                   live_cb=lambda *a, **k: None)
    dt = time.perf_counter() - t0
    lam = np.asarray(r["lam_nm"], float)
    n = np.asarray(r["n_lam"], float)
    i = int(np.argmin(np.abs(lam - 1000.0)))
    print(f"  option={'allumee' if on else 'eteinte'} budget x{factor} : {dt:.2f} s, {counts['cost']} couts, "
          f"RMSE={r['rmse']:.7f} d={r['d_nm']:.2f} nm, n(1000)={n[i]:.5f} n*d={n[i] * r['d_nm']:.1f} nm "
          f"| NaN n_lam {int(np.isnan(n).sum())}/{n.size}", flush=True)


for path in sorted(Path("example/example_index_spline").glob("*.xlsx")):
    spline_app = CertusIndexSplineApp()
    spline_app._on_load(path=str(path.resolve()))
    base = spline_app._build_opt_config(notify=False)
    print(f"{path.name} : n_seg={base.n_seg} d=[{base.d_lo:.0f}, {base.d_hi:.0f}] data_type={base.data_type} "
          f"n_mono_band_nm={base.n_mono_band_nm} polish_maxfun={base.pglobal.polish_maxfun}", flush=True)
    run(base, False, 1)
    run(base, True, 1)
    run(base, False, 5)
