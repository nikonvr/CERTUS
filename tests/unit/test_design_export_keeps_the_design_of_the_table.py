"""DESIGN's export does not put back a better evaluation of another structure.

Before saving, the export swapped its payload for the best evaluation seen and wrote that
evaluation's thicknesses into the table. When the final 5 nm rule had removed layers in between,
the best evaluation had more layers than the table: a bench run on 2026-10-23 ended with 30 rows and
32 thicknesses, an RMSE of 0.31 in the window, and a report that mixed the two designs
(reports/DESIGN_bs5050_2026-10-22/journal.md). Only an evaluation of the same layer count may be put back.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN export sync", main_windows_only=True)


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    app.ep_current = np.full(app.front_table.rowCount(), 80.0)
    app.last_result = {"rmse": 0.004, "ep": app.ep_current.copy()}
    return app


def test_a_better_evaluation_with_more_layers_is_not_put_back(design_app) -> None:
    rows = design_app.front_table.rowCount()
    design_app._best_eval_result = {"rmse": 0.0002, "ep": np.full(rows + 2, 50.0)}
    design_app._best_eval_rmse = 0.0002

    design_app.export_manager._sync_export_result_with_best_eval()

    assert design_app.front_table.rowCount() == rows
    assert len(design_app.ep_current) == rows
    assert np.all(design_app.ep_current == 80.0)


def test_a_better_evaluation_with_the_same_layers_is_put_back(design_app) -> None:
    rows = design_app.front_table.rowCount()
    design_app._best_eval_result = {"rmse": 0.0002, "ep": np.full(rows, 50.0)}
    design_app._best_eval_rmse = 0.0002

    design_app.export_manager._sync_export_result_with_best_eval()

    assert np.allclose(design_app.ep_current, 50.0)
