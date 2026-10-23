"""DESIGN starts its workflow again from its final design while that design improves.

One memetic run ends between RMSE 0.000147 and 0.0004 on the 50/50 splitter 400-1200 nm; restarting from the
result went 0.000189 -> 0.000149 -> 0.000148 -> 0.000148 (reports/DESIGN_bs5050_2026-10-22/journal.md).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN restart", main_windows_only=True)


@pytest.fixture
def design_app(qapp, monkeypatch):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    app.ep_current = np.full(app.front_table.rowCount(), 80.0)
    app._scheduled = []
    monkeypatch.setattr(app.orchestrator, "_schedule_task", lambda delay, func: app._scheduled.append(func))
    return app


def _finish_round(app, rmse: float, thickness: float) -> bool:
    app.ep_current = np.full(app.front_table.rowCount(), thickness)
    app._workflow_best_rmse = rmse
    return app.optimization_manager._restart_from_best()


def _restarts(app) -> list:
    return [f for f in app._scheduled if "_restart_from_best" in getattr(f, "__qualname__", "")]


def test_the_workflow_restarts_while_it_improves_then_keeps_its_best_round(design_app) -> None:
    assert _finish_round(design_app, 0.000189, 80.0)
    assert _finish_round(design_app, 0.000149, 81.0)
    assert not _finish_round(design_app, 0.000150, 82.0)  # worse: no new round, the best is put back

    assert len(_restarts(design_app)) == 2
    assert design_app._workflow_best_rmse == 0.000149
    assert np.all(design_app.ep_current == 81.0)


def test_a_gain_under_one_percent_ends_the_rounds(design_app) -> None:
    assert _finish_round(design_app, 0.000149, 80.0)
    assert not _finish_round(design_app, 0.000148, 81.0)

    assert np.all(design_app.ep_current == 81.0)  # better, kept even though the rounds stop


def test_no_restart_when_turned_off(design_app) -> None:
    design_app._auto_restarts = 0

    assert not _finish_round(design_app, 0.000189, 80.0)
    assert _restarts(design_app) == []
