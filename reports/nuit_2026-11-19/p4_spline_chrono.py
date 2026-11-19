"""Lot 4 (chantier 21): what do Smart Init and the free-knot stage cost in SPLINE, on TOTAL and TSIO2?

Threshold of docs/CHANTIERS_RESTANTS.md: a stage worth analytic derivatives takes more than 20 % of the run AND more
than 5 s. Per workbook of example/example_index_spline/, window configuration (`_build_opt_config`), current defaults:
- main run: `worker_spline_optimization`, with `guess_smart_x0_from_extrema` (Smart Init, Swanepoel) timed inside it;
- free-knot stage: since the pipeline dropped its legacy stage ([03/09]), it runs only as Auto-Best pass 2
  (`worker_auto_best_split_knot_refinement`, seeded with the main result), timed on its own.
One warm-up, then REPEATS rounds; medians. No other python process.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/nuit_2026-11-19/p4_spline_chrono.py [REPEATS]
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

import certus.spline.spline_smart_init as smart_init  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.spline.spline_workers import worker_auto_best_split_knot_refinement  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
smart = {"s": 0.0, "calls": 0}
_guess = smart_init.guess_smart_x0_from_extrema


def _timed_guess(*args, **kwargs):
    t0 = time.perf_counter()
    try:
        return _guess(*args, **kwargs)
    finally:
        smart["s"] += time.perf_counter() - t0
        smart["calls"] += 1


smart_init.guess_smart_x0_from_extrema = _timed_guess  # the SPLINE core imports it at call time


def quiet(*_a, **_k):
    return None


def one_round(cfg):
    smart["s"], smart["calls"] = 0.0, 0
    t0 = time.perf_counter()
    main = worker_spline_optimization(cfg, threading.Event(), progress_cb=quiet, live_cb=quiet)
    t_main = time.perf_counter() - t0
    t_smart, n_smart = smart["s"], smart["calls"]
    t0 = time.perf_counter()
    second = worker_auto_best_split_knot_refinement(dict(main), cfg, threading.Event(), quiet)
    t_free = time.perf_counter() - t0
    return t_main, t_smart, n_smart, t_free, main, second


print("workbook | main run s | Smart Init s (calls) | share of main | free-knot pass s | share of main+pass | RMSE main -> pass")
for path in sorted(Path("example/example_index_spline").glob("*.xlsx")):
    window = CertusIndexSplineApp()
    window._on_load(path=str(path.resolve()))
    cfg = window._build_opt_config(notify=False)
    one_round(cfg)
    rounds = [one_round(cfg) for _ in range(REPEATS)]
    t_main = statistics.median(r[0] for r in rounds)
    t_smart = statistics.median(r[1] for r in rounds)
    t_free = statistics.median(r[3] for r in rounds)
    main, second = rounds[-1][4], rounds[-1][5]
    rmse2 = f"{second['rmse']:.7f}" if isinstance(second, dict) and "rmse" in second else str(second)
    print(f"{path.name} | {t_main:.2f} | {t_smart:.3f} ({rounds[-1][2]}) | {100 * t_smart / t_main:.1f} % | {t_free:.2f} | "
          f"{100 * t_free / (t_main + t_free):.1f} % | {main['rmse']:.7f} -> {rmse2}", flush=True)
