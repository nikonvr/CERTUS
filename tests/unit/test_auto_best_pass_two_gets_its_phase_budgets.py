"""Auto-Best pass 2 (free sigma knots for n and ln k) runs its first phase with the budgets it computed (2026-11-20).

Measured on 2026-11-20 (reports/nuit_2026-11-19/p4_spline_chrono.py): since the split of the SPLINE monolith
(`0b7f4f0d`), `_run_free_knot_stage` built its context with `phase_maxfun_list=[]` and computed the three phase budgets
in local variables it never handed over: the first L-BFGS-B phase raised `IndexError` in `phase_progress_bounds`, on
TOTAL and TSIO2, every time Auto-Best launched its second pass.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

ROOT = Path(__file__).resolve().parents[2]


class _FirstPhaseReached(Exception):
    pass


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it (tests/qt_lifecycle.py, D11 and D23)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "SPLINE Auto-Best pass 2", main_windows_only=True)


def test_the_first_phase_of_pass_two_sees_the_three_budgets(monkeypatch) -> None:
    from certus.spline import spline_workers
    from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    window = CertusIndexSplineApp()
    window._on_load(path=str(ROOT / "example" / "example_index_spline" / "TSIO2-1700-1.xlsx"))
    cfg = window._build_opt_config(notify=False)
    main = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a, **k: None, live_cb=lambda *a, **k: None)

    seen: dict = {}

    def first_phase(self, z0, options, phase_idx):
        seen["budgets"] = list(self.phase_maxfun_list)
        seen["bounds"] = self.phase_progress_bounds(phase_idx)
        seen["maxfun"] = options["maxfun"]
        raise _FirstPhaseReached

    monkeypatch.setattr(spline_workers.FreeKnotStageContext, "run_lbfgsb_phase_with_progress", first_phase)
    with pytest.raises(_FirstPhaseReached):
        spline_workers.worker_auto_best_split_knot_refinement(dict(main), cfg, threading.Event(), lambda *a, **k: None)

    expected = list(spline_workers._free_knot_phase_budgets(cfg, True)[3])
    assert seen["budgets"] == expected
    # A quarter of the former 10 000 / 20 000 / 40 000 (owner, 2026-11-20; reports/nuit_2026-11-19/p4_pass2_budgets.txt).
    assert expected == [2500, 5000, 10000]
    assert len(expected) == 3
    assert seen["maxfun"] == expected[0]
    assert seen["bounds"][0] == 0.0
    assert 0.0 < seen["bounds"][1] < 100.0
