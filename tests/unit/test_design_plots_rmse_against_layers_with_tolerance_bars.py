"""DESIGN plots the RMSE of its Pareto records against their layer count, with tolerance bars.

Bars: mean +/- 2 sigma of the RMSE when every layer gets a Gaussian thickness error whose 2 sigma is
0.1 % of it plus 0.2 nm (owner's request of 2026-10-23), from certus/core/certus_design_tolerance.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


def test_no_thickness_error_gives_no_spread() -> None:
    from certus.core.certus_design_tolerance import rmse_band

    band = rmse_band(lambda ep: float(np.sum((ep - 50.0) ** 2)) * 1e-6 + 1e-6, np.full(4, 52.0),
                     rel_2sigma=0.0, abs_2sigma_nm=0.0, draws=20)

    assert band.two_sigma == pytest.approx(0.0, abs=1e-15)
    assert band.mean == pytest.approx(band.nominal)


def test_the_same_design_gives_the_same_band() -> None:
    from certus.core.certus_design_tolerance import rmse_band

    def cost(ep):
        return float(np.sum((ep - 50.0) ** 2)) * 1e-6

    first = rmse_band(cost, np.full(6, 51.0), draws=50)
    second = rmse_band(cost, np.full(6, 51.0), draws=50)

    assert first == second
    assert first.two_sigma > 0.0


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN RMSE vs layers", main_windows_only=True)


def test_each_pareto_record_gets_a_point_and_a_bar(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    rows = app.front_table.rowCount()
    full = {"best_rmse": 0.3, "table_rmse": app._save_table_state(), "ep_rmse": np.full(rows, 70.0)}
    app.front_table.removeRow(rows - 1)
    app.front_table.removeRow(rows - 2)
    shorter = {"best_rmse": 0.31, "table_rmse": app._save_table_state(), "ep_rmse": np.full(rows - 2, 70.0)}
    app.pareto_history = {rows: full, rows - 2: shorter}

    app.plot_manager._refresh_pareto_table()

    x, y = app.rmse_layers_points.getData()
    assert list(x) == [rows - 2, rows]
    assert np.all(y > 0.0)
    assert np.all(np.asarray(app.rmse_layers_bars.opts["top"]) > 0.0)
