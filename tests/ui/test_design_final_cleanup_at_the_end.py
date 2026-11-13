"""At the end of an optimization DESIGN cleans its design: no thin layer, and a last polish (owner, 2026-11-13).

The 5 nm rule removed thin layers at once and did not re-optimize. The final cleanup
(certus/core/certus_design_final_cleanup.py) takes its place, automatic, on the window's own design: each layer
under the window's `Min. Layer` is removed or raised, the design polished. The 5 nm rule stays the fallback where
the cleanup cannot run (oblique incidence) or when a file turns it off (`final_cleanup: false`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN final cleanup", main_windows_only=True)


def _app_with(thicknesses_of=None):
    """The example in the window, with layers given a thickness: {row: nm}."""
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    app._update_thickness_display()
    ep = np.asarray(app.ep_current, dtype=float).copy()
    for row, nm in (thicknesses_of or {}).items():
        ep[row] = nm
    app._update_qwot_from_ep(ep)
    app._update_thickness_display()
    app.ep_current = ep.copy()
    app._use_exact_ep = True
    return app


def _rmse(app) -> float:
    manager = app.optimization_manager
    value = manager._true_rmse(manager._save_table_state(), app.ep_current)
    assert value is not None, "the example must be judged by the window (normal incidence, no back side)"
    return value


def test_the_example_has_what_these_tests_need(qapp) -> None:
    app = _app_with()
    assert app.front_table.rowCount() >= 5
    assert np.min(app.ep_current) >= 5.0, "the example must start without a thin layer"


def test_no_variable_layer_is_left_under_the_window_s_floor(qapp) -> None:
    app = _app_with({1: 2.0, 3: 1.2})
    rows = app.front_table.rowCount()

    removed = app.optimization_manager._final_cleanup()

    assert removed is not None
    assert app.front_table.rowCount() == rows - removed == len(app.ep_current)
    assert np.min(app.ep_current) >= 5.0
    assert app.orchestrator._target_layer_count == app.front_table.rowCount()


def test_the_rmse_it_leaves_is_the_design_s_own(qapp) -> None:
    """The workflow's best RMSE once named another design (a decimation step): here it is recomputed."""
    app = _app_with({1: 2.0})
    app.optimization_manager._final_cleanup()
    assert app._workflow_best_rmse == pytest.approx(_rmse(app), rel=1e-6)


def test_it_ends_no_worse_than_the_5_nm_rule(qapp) -> None:
    """Same design, same thin layer: the rule removes it and stops; the cleanup tries both ways and polishes."""
    by_rule = _app_with({1: 2.0})
    by_rule._design_optional_steps = {"final_cleanup": False}
    assert by_rule.optimization_manager._final_cleanup() is None
    by_rule.optimization_manager._apply_5nm_minimum()
    rule_rmse = _rmse(by_rule)

    cleaned = _app_with({1: 2.0})
    cleaned.optimization_manager._final_cleanup()

    assert _rmse(cleaned) <= rule_rmse


def test_a_design_without_a_thin_layer_is_only_polished(qapp) -> None:
    app = _app_with()
    rows, before = app.front_table.rowCount(), _rmse(app)
    assert app.optimization_manager._final_cleanup() == 0
    assert app.front_table.rowCount() == rows
    assert _rmse(app) <= before


def test_the_window_s_field_is_the_floor(qapp) -> None:
    app = _app_with()
    floor = float(np.min(app.ep_current)) + 3.0
    app.min_layer_spin.setValue(floor)
    app.optimization_manager._final_cleanup()
    assert np.min(app.ep_current) >= app.min_layer_spin.value()


def test_a_layer_the_operator_fixed_is_left_as_it_is(qapp) -> None:
    from PyQt6.QtWidgets import QCheckBox

    app = _app_with({1: 2.0})
    app.front_table.cellWidget(1, 3).findChild(QCheckBox).setChecked(False)
    app.ep_current[1] = 2.0
    app._use_exact_ep = True
    rows = app.front_table.rowCount()

    app.optimization_manager._final_cleanup()

    assert app.front_table.rowCount() == rows
    assert app.ep_current[1] == pytest.approx(2.0)


def test_oblique_incidence_keeps_the_5_nm_rule(qapp) -> None:
    app = _app_with({1: 2.0})
    app.oblique_mode = True
    assert app.optimization_manager._final_cleanup() is None
    assert app.ep_current[1] == pytest.approx(2.0), "nothing may change when the cleanup does not run"


def test_the_end_of_the_workflow_runs_the_cleanup_and_not_the_rule(qapp, monkeypatch) -> None:
    app = _app_with({1: 2.0})
    manager = app.optimization_manager
    app._decimation_done = True
    app._auto_restarts = 0
    calls: list[str] = []
    monkeypatch.setattr(manager, "_apply_5nm_minimum", lambda: calls.append("rule") or 0)
    cleanup = manager._final_cleanup
    monkeypatch.setattr(manager, "_final_cleanup", lambda: calls.append("cleanup") or cleanup())

    manager._finalize_completed_optimization_workflow()

    assert calls == ["cleanup"]
    assert np.min(app.ep_current) >= 5.0
