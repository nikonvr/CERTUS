"""DESIGN restores a Pareto champion free of layers under 5 nm when `_pareto_champion_respects_5nm` is set.

Smart Pareto decimation restores the best record it saw, then the final 5 nm rule removes the thin
layers of that record without re-optimizing: a champion with a 4.2 nm layer fell from RMSE 0.000165
to 0.0239 on the 50/50 splitter 400-1200 nm (reports/DESIGN_bs5050_2026-10-22/journal.md).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN Pareto champion", main_windows_only=True)


@pytest.mark.parametrize(("option", "rows"), [(False, 26), (True, 24)])
def test_the_restored_champion_is_free_of_sub_5nm_layers_only_when_asked(qapp, option, rows) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    thin = np.full(26, 60.0)
    thin[5] = 4.2
    better_with_a_thin_layer = {"best_rmse": 0.000165, "table_rmse": app._save_table_state(), "ep_rmse": thin}
    app.front_table.removeRow(25)
    app.front_table.removeRow(24)
    compliant = {"best_rmse": 0.000187, "table_rmse": app._save_table_state(), "ep_rmse": np.full(24, 60.0)}
    app.pareto_history = {26: better_with_a_thin_layer, 24: compliant}
    app._pareto_champion_respects_5nm = option

    assert app.optimization_manager._restore_smart_decimation_best_overall()

    assert app.front_table.rowCount() == rows
    assert len(app.ep_current) == rows
