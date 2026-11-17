"""Chantier 21 : duree de SPLINE avec et sans `spline_mono_analytic_gradient`, meme exemple, meme processus.

Configuration de la fenetre INDEX SPLINE (`tests/headless/test_spline.py`, `TSIO2-1700-1.xlsx`, n_seg=13, mode local).
Un premier calcul (option eteinte) chauffe Numba et n'est pas compte ; puis REPEATS paires eteinte/allumee alternees,
chronometrees autour de `worker_spline_optimization` seul. Une derniere paire compte les evaluations de cout et de
gradient de `SplinePWLObjective` (compteurs poses apres le chronometrage, hors des durees).

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_gradient_on_off.py
"""
import statistics
import sys
import threading
import time
from pathlib import Path

import numpy as np

REPEATS = 5

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
print(f"n_seg={base.n_seg} d=[{base.d_lo:.0f}, {base.d_hi:.0f}] local_only={base.spline_local_only} "
      f"n_mono_band_nm={base.n_mono_band_nm} option par defaut={base.spline_mono_analytic_gradient}")


def run(on: bool) -> tuple[float, dict]:
    cfg = base.replace(spline_mono_analytic_gradient=on)
    t0 = time.perf_counter()
    res = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None,
                                     live_cb=lambda *a, **k: None)
    return time.perf_counter() - t0, res


run(False)  # Numba warm-up, not counted

durations = {False: [], True: []}
results = {}
for _ in range(REPEATS):
    for on in (False, True):
        dt, res = run(on)
        durations[on].append(dt)
        results[on] = res

for on in (False, True):
    d = durations[on]
    r = results[on]
    print(f"option={'allumee' if on else 'eteinte'} : mediane {statistics.median(d):.3f} s, min {min(d):.3f}, "
          f"max {max(d):.3f} ({' '.join(f'{x:.3f}' for x in d)}) | RMSE={r['rmse']:.10f} d={r['d_nm']:.6f} nm "
          f"nit_polish={r.get('nit_polish')}")

off, on_ = results[False], results[True]
print(f"ecart allumee - eteinte : RMSE {on_['rmse'] - off['rmse']:+.3e}, d {on_['d_nm'] - off['d_nm']:+.4f} nm, "
      f"max|dn| {np.max(np.abs(np.asarray(on_['n_lam']) - np.asarray(off['n_lam']))):.3e}, "
      f"max|dk| {np.max(np.abs(np.asarray(on_['k_lam']) - np.asarray(off['k_lam']))):.3e}")

# Counted pass, outside the timings.
counts = {"cost": 0, "grad": 0}
_call = spline_objective.SplinePWLObjective.__call__
_grad = spline_objective.SplinePWLObjective.analytic_gradient


def _counted_call(self, xv):
    counts["cost"] += 1
    return _call(self, xv)


def _counted_grad(self, xv):
    counts["grad"] += 1
    return _grad(self, xv)


spline_objective.SplinePWLObjective.__call__ = _counted_call
spline_objective.SplinePWLObjective.analytic_gradient = _counted_grad
for on in (False, True):
    counts.update(cost=0, grad=0)
    run(on)
    print(f"option={'allumee' if on else 'eteinte'} : {counts['cost']} evaluations de cout, "
          f"{counts['grad']} gradients analytiques")
