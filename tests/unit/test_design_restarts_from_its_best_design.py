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
    app.optimization_manager._true_rmse = lambda table, ep: rmse  # the RMSE the round reaches, measured on its design
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


def test_restart_tries_the_opposite_alternation_when_a_boundary_layer_sits_near_the_floor(design_app) -> None:
    """When layer 0 sits near the 5 nm floor on an H-first stack, the restart shifts it to L-first (N+1 -> N)."""
    design_app._design_optional_steps = {"restart_flip_alternation": True}  # optional step, off by default
    initial_mats = [layer.mat for layer in design_app._get_front_stack()]
    assert initial_mats[0] == "H"
    assert initial_mats[1] == "L"
    ep = np.full(len(initial_mats), 80.0)
    ep[0] = 5.2  # layer 0 (H on substrate) is pinned near the 5 nm floor
    design_app.ep_current = ep.copy()
    design_app._workflow_best_rmse = 0.005
    design_app.optimization_manager._true_rmse = lambda table, e: 0.005

    assert design_app.optimization_manager._restart_from_best()

    flipped_mats = [layer.mat for layer in design_app._get_front_stack()]
    assert len(flipped_mats) == len(initial_mats)
    assert flipped_mats[0] == "L"
    assert flipped_mats[1] == "H"
    # If the flipped round turns out worse, _restart_from_best restores the original H-first table and thicknesses.
    design_app.optimization_manager._true_rmse = lambda table, e: 0.008
    design_app._workflow_best_rmse = 0.008
    assert not design_app.optimization_manager._restart_from_best()
    restored_mats = [layer.mat for layer in design_app._get_front_stack()]
    assert restored_mats == initial_mats
    assert np.allclose(design_app.ep_current, ep)
