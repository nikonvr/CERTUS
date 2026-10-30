"""DESIGN "Compare" tab of 2026-10-29: distance between two designs and RMSE barrier between them."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN compare tab", main_windows_only=True)


def _app_with_two_records():
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    rows = app.front_table.rowCount()
    full = {"best_rmse": 0.3, "table_rmse": app._save_table_state(), "ep_rmse": 60.0 + np.arange(rows, dtype=float)}
    app.front_table.removeRow(rows - 1)
    app.front_table.removeRow(rows - 2)
    shorter = {"best_rmse": 0.31, "table_rmse": app._save_table_state(),
               "ep_rmse": 60.0 + np.arange(rows - 2, dtype=float)}
    app.pareto_history = {rows: full, rows - 2: shorter}
    app.last_result = None
    return app, rows


def test_the_compare_tab_lists_the_pareto_records(qapp) -> None:
    from certus.ui.certus_design_ui_compare import refresh_design_lists

    app, rows = _app_with_two_records()
    assert any(app.plot_tabs.tabText(i) == "Compare" for i in range(app.plot_tabs.count()))
    refresh_design_lists(app)
    assert app.compare_a_combo.count() == 2
    assert {app.compare_a_combo.itemData(i) for i in range(2)} == {rows, rows - 2}
    assert app.compare_a_combo.currentData() != app.compare_b_combo.currentData()


def test_distance_between_a_record_and_itself_is_zero_and_two_records_are_apart(qapp) -> None:
    app, rows = _app_with_two_records()
    app.log = lambda msg, level="INFO": None
    # through the real signals: showing the tab fills the lists, the button computes the distance
    app.plot_tabs.setCurrentIndex(next(i for i in range(app.plot_tabs.count()) if app.plot_tabs.tabText(i) == "Compare"))
    assert app.compare_a_combo.count() == 2
    app.compare_a_combo.setCurrentIndex(app.compare_a_combo.findData(rows))
    app.compare_b_combo.setCurrentIndex(app.compare_b_combo.findData(rows))
    app.compare_distance_btn.click()
    assert app.compare_result_label.text().startswith("Distance A–B: 0.0 nm")
    app.compare_b_combo.setCurrentIndex(app.compare_b_combo.findData(rows - 2))
    app.compare_distance_btn.click()
    assert "Distance A–B: 0.0 nm" not in app.compare_result_label.text()
    assert len(app.compare_profile_a.getData()[1]) == rows
    assert len(app.compare_profile_b.getData()[1]) == rows - 2


def test_barrier_worker_result_is_drawn(qapp) -> None:
    from certus.core.certus_design_landscape import align_designs, aligned_path
    from certus.ui.certus_design_ui_compare import _selected, on_barrier_done, refresh_design_lists
    from certus.workers.certus_design_workers import BarrierWorker

    app, _rows = _app_with_two_records()
    app.log = lambda msg, level="INFO": None
    refresh_design_lists(app)
    a, b, n_of = _selected(app)
    path = aligned_path(a, b, align_designs(a, b), n_of)
    worker = BarrierWorker({"mats": app._get_materials(), "wls": np.asarray(app._get_optim_wls(), dtype=float),
                            "tgts": [t for t in app._get_tgts() if t.valid()], "materials": list(path.materials),
                            "ep_a": path.ep_a, "ep_b": path.ep_b, "images": 5, "iterations": 3})
    got = []
    worker.signals.finished.connect(got.append)
    worker.run()
    assert got
    assert got[0]["ok"]
    assert got[0]["iterations"] == 3
    on_barrier_done(app, got[0])
    assert "barrier of at most" in app.compare_result_label.text()
    assert len(app.compare_string_curve.getData()[1]) == got[0]["rmse_string"].size
