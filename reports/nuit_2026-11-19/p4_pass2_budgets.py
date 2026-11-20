"""Lot 4, decision of the owner (2026-11-20): reduce the budgets of Auto-Best pass 2 (free knots). Which scale?

The three L-BFGS-B phases of `_run_free_knot_stage` get `_free_knot_phase_budgets`: mxf1 = 10 000 (`sol3_phase1_maxfun`),
mxf2 = max(16 000, 2 mxf1), mxf3 = max(40 000, 4 mxf1). Here all three are multiplied by SCALE, the main run is the
window's (current defaults), and pass 2 is timed with its RMSE and the cost evaluations it really used. Median of
REPEATS rounds; one warm-up. No other python process. Measured on `ce4adfba` with the former budgets; since `babd2f9a`
(a quarter) the same scales apply to the new ones.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/nuit_2026-11-19/p4_pass2_budgets.py [REPEATS]
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

from certus.spline import spline_workers  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
SCALES = (1.0, 0.5, 0.25, 0.1)
_budgets = spline_workers._free_knot_phase_budgets
_obj = spline_workers.FreeKnotStageContext.obj_tracked
state = {"scale": 1.0, "calls": 0}


def scaled_budgets(cfg, optimize_n):
    mxf1, mxf2, mxf3, _lst, _w = _budgets(cfg, optimize_n)
    s = state["scale"]
    m1, m2, m3 = (max(1, round(v * s)) for v in (mxf1, mxf2, mxf3))
    lst = [m1, m2] + ([m3] if optimize_n else [])
    return m1, m2, m3, lst, float(max(1, sum(lst)))


def counted(self, z):
    state["calls"] += 1
    return _obj(self, z)


spline_workers._free_knot_phase_budgets = scaled_budgets
spline_workers.FreeKnotStageContext.obj_tracked = counted


def quiet(*_a, **_k):
    return None


print("workbook | scale | budgets | pass 2 s (median) | evaluations | RMSE main -> pass 2")
for path in sorted(Path("example/example_index_spline").glob("*.xlsx")):
    window = CertusIndexSplineApp()
    window._on_load(path=str(path.resolve()))
    cfg = window._build_opt_config(notify=False)
    main = worker_spline_optimization(cfg, threading.Event(), progress_cb=quiet, live_cb=quiet)
    state["scale"] = 0.1
    spline_workers.worker_auto_best_split_knot_refinement(dict(main), cfg, threading.Event(), quiet)  # warm-up
    for scale in SCALES:
        state["scale"] = scale
        durations, out = [], None
        for _ in range(REPEATS):
            state["calls"] = 0
            t0 = time.perf_counter()
            out = spline_workers.worker_auto_best_split_knot_refinement(dict(main), cfg, threading.Event(), quiet)
            durations.append(time.perf_counter() - t0)
        budgets = scaled_budgets(cfg, True)[3]
        rmse = f"{out['rmse']:.7f}" if isinstance(out, dict) else str(out)
        print(f"{path.name} | {scale:g} | {budgets} | {statistics.median(durations):.2f} | {state['calls']} | "
              f"{main['rmse']:.7f} -> {rmse}", flush=True)
