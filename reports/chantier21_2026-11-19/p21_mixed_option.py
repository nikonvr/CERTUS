"""Chantier 21 : l'option `spline_polish_fd_prefix_maxfun` reproduit-elle la sonde, et combien coute-t-elle ?

Pour chaque classeur d'`example/example_index_spline/`, configuration de la fenetre, trois reglages :
- defaut : rien d'allume (differences finies) ;
- AN : `spline_mono_analytic_gradient` ;
- AN + prefixe : `spline_mono_analytic_gradient` et `spline_polish_fd_prefix_maxfun` = PREFIX.
Un calcul de chauffe, puis REPEATS tours alternes chronometres autour de `worker_spline_optimization` ; une derniere passe
compte les evaluations de cout. RMSE et d du dernier tour, mediane et extremes des durees.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-19/p21_mixed_option.py [REPEATS]
"""
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import certus_physics  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
certus_physics.warmup_physics()

from certus.spline import spline_objective  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

PREFIX = 3000
REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
SETTINGS = {
    "defaut": {},
    "AN": {"spline_mono_analytic_gradient": True},
    "AN + prefixe": {"spline_mono_analytic_gradient": True, "spline_polish_fd_prefix_maxfun": PREFIX},
}


def run(base, name):
    cfg = base.replace(**SETTINGS[name])
    t0 = time.perf_counter()
    r = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None,
                                   live_cb=lambda *a, **k: None)
    return time.perf_counter() - t0, r


for path in sorted(Path("example/example_index_spline").glob("*.xlsx")):
    spline_app = CertusIndexSplineApp()
    spline_app._on_load(path=str(path.resolve()))
    base = spline_app._build_opt_config(notify=False)
    print(f"{path.name} : prefixe {PREFIX}, {REPEATS} tours", flush=True)
    run(base, "defaut")
    durations = {name: [] for name in SETTINGS}
    results = {}
    for _ in range(REPEATS):
        for name in SETTINGS:
            dt, results[name] = run(base, name)
            durations[name].append(dt)
    counts = {}
    _call = spline_objective.SplinePWLObjective.__call__
    n = {"cost": 0}

    def _counted(self, xv, _call=_call, n=n):
        n["cost"] += 1
        return _call(self, xv)

    spline_objective.SplinePWLObjective.__call__ = _counted
    for name in SETTINGS:
        n["cost"] = 0
        run(base, name)
        counts[name] = n["cost"]
    spline_objective.SplinePWLObjective.__call__ = _call
    for name in SETTINGS:
        d, r = durations[name], results[name]
        print(f"  {name:13s} : mediane {statistics.median(d):6.2f} s (min {min(d):.2f}, max {max(d):.2f}), "
              f"{counts[name]:6d} couts, RMSE={r['rmse']:.7f} d={r['d_nm']:.2f} nm", flush=True)
