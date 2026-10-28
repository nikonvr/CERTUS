"""DESIGN robust tools of 2026-10-27: residual of the cost, spectral Monte Carlo and Robust N buttons."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN robust tools", main_windows_only=True)


def _app():
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def test_residual_norm_is_the_design_cost(qapp) -> None:
    from certus.core.certus_design_tolerance import design_cost_function, design_residual_function

    app = _app()
    mats, stack = app._get_materials(), app._get_front_stack()
    wls, tgts = np.asarray(app._get_optim_wls(), dtype=float), [t for t in app._get_tgts() if t.valid()]
    ep = np.full(len(stack), 80.0) + np.arange(len(stack))
    r = design_residual_function(mats, stack, wls, tgts)(ep)
    assert float(r @ r) == pytest.approx(design_cost_function(mats, stack, wls, tgts)(ep), rel=1e-10)


def test_robust_n_recommends_a_layer_count(qapp) -> None:
    app = _app()
    rows = app.front_table.rowCount()
    full = {"best_rmse": 0.3, "table_rmse": app._save_table_state(), "ep_rmse": np.full(rows, 70.0)}
    app.front_table.removeRow(rows - 1)
    app.front_table.removeRow(rows - 2)
    shorter = {"best_rmse": 0.31, "table_rmse": app._save_table_state(), "ep_rmse": np.full(rows - 2, 70.0)}
    app.pareto_history = {rows: full, rows - 2: shorter}
    app.mc_sigma_ot_spin.setValue(0.5)
    logged = []
    app.log = lambda msg, level="INFO": logged.append(msg)
    app.run_robust_n()
    assert sum("recommended" in m for m in logged) == 1
    assert any(f"N={rows}:" in m for m in logged)
    assert any(f"N={rows - 2}:" in m for m in logged)


def test_spectral_mc_widgets_default_to_no_extra_error(qapp) -> None:
    app = _app()
    assert app.mc_sigma_rel_spin.value() == 0.0
    assert app.mc_sigma_ot_spin.value() == 0.0
    assert app.mc_rmse_threshold_spin.value() == 0.0
