"""The thickness uncertainties and the parameter budget of the retained RE result reach the user.

    THE RESULTS TABLE: a last column gives one sigma per layer of the retained run, n/a for a combination of thicknesses
        the spectra do not constrain; without uncertainties the table keeps its columns
    THE SNAPSHOT EXPORT: a sigma(d) column beside the thicknesses and the parameter budget below them, but only while the
        stack holds the thicknesses of the retained result -- once they are edited, the bars no longer describe them
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from certus.ui.certus_re_ui import CertusREResultsDialog

SIGMA_HEADER = "sigma(d) nm, retained run"


class _Layer:
    def __init__(self, mat: str) -> None:
        self.mat = mat


def _dialog(monkeypatch, result: dict) -> CertusREResultsDialog:
    material = MagicMock()
    material.get_nk.return_value = np.array([2.0 + 0j], dtype=np.complex128)
    app = MagicMock()
    app.l0_spin.value.return_value = 500.0
    app._get_materials.return_value = {"H": material, "L": material}
    app._re_envelope_scale_from_gui.return_value = 1.0
    app._re_spline_lam2_nm_from_result.return_value = 2000.0
    app._re_initial_stack = [_Layer("H"), _Layer("L")]
    monkeypatch.setattr(CertusREResultsDialog, "exec", MagicMock())
    monkeypatch.setattr(CertusREResultsDialog, "show", MagicMock())
    return CertusREResultsDialog(app, [result], ep0=np.array([100.0, 150.0]), announce_in_log=False)


def _result(**extra) -> dict:
    out = {
        "label": "Run 1",
        "rmse": 0.001,
        "nfev": 10,
        "ep": np.array([101.0, 149.0]),
        "re_dH_knots": np.zeros(5),
        "re_dL_knots": np.zeros(5),
        "re_knots_nm": np.array([400.0, 600.0, 800.0, 1000.0, 1200.0]),
    }
    out.update(extra)
    return out


def test_the_table_gives_one_sigma_per_layer_of_the_retained_run(qapp, monkeypatch):
    dlg = _dialog(monkeypatch, _result(thickness_uncertainty={"sigma_nm": [0.4321, float("nan")]}))
    try:
        col = dlg.headers.index(SIGMA_HEADER)
        assert col == dlg.n_cols - 1
        assert dlg.tbl.item(0, col).text() == "0.432"
        assert dlg.tbl.item(1, col).text() == "n/a"
    finally:
        dlg.deleteLater()


def test_without_uncertainties_the_table_keeps_its_columns(qapp, monkeypatch):
    dlg = _dialog(monkeypatch, _result())
    try:
        assert SIGMA_HEADER not in dlg.headers
        assert dlg.n_cols == 3 + 2
    finally:
        dlg.deleteLater()


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    yield win
    win.close()


def _export(win, monkeypatch, tmp_path):
    import openpyxl

    import certus.ui.certus_re_excel_mixin as mixin

    path = tmp_path / "snapshot.xlsx"

    class _Dialog:
        @staticmethod
        def getSaveFileName(*_args, **_kwargs):
            return str(path), "Excel (*.xlsx)"

    monkeypatch.setattr(mixin, "QFileDialog", _Dialog)
    win.export_excel()
    rows = [[c for c in row] for row in openpyxl.load_workbook(path).worksheets[0].iter_rows(values_only=True)]
    return rows


def _retained(win, ep):
    win._re_retained_report = {
        "ep": np.asarray(ep, dtype=np.float64).copy(),
        "thickness_uncertainty": {"sigma_nm": [0.25] * (len(ep) - 1) + [float("nan")]},
        "parameter_budget": {
            "blocks": [{"name": "layer thicknesses", "count": len(ep), "status": "released"}],
            "n_free_parameters": len(ep),
            "n_data_points": 1200,
            "points_per_free_parameter": 1200 / len(ep),
        },
    }


def test_the_export_carries_sigma_and_the_budget_of_the_retained_result(re_window, monkeypatch, tmp_path):
    win = re_window
    win.load_reverse_engineering_from_path("example/example_RE/reverse_sample.xlsx")
    n = len(win._get_front_stack())
    win.ep_current = np.linspace(100.0, 200.0, n)
    _retained(win, win.ep_current)
    rows = _export(win, monkeypatch, tmp_path)
    h = next(i for i, r in enumerate(rows) if r and r[0] == "#")
    assert rows[h][5] == "sigma(d) (nm), 1 sigma, data rows only"
    layer_rows = rows[h + 1 : h + 1 + n]
    assert [r[0] for r in layer_rows] == list(range(1, n + 1))
    assert [r[5] for r in layer_rows] == [0.25] * (n - 1) + ["n/a"]
    labels = [r[0] for r in rows if r]
    assert "PARAMETER BUDGET (retained RE result)" in labels
    assert next(r for r in rows if r and r[0] == "Data points")[1] == 1200


def test_the_export_omits_them_once_the_thicknesses_are_edited(re_window, monkeypatch, tmp_path):
    win = re_window
    win.load_reverse_engineering_from_path("example/example_RE/reverse_sample.xlsx")
    n = len(win._get_front_stack())
    win.ep_current = np.linspace(100.0, 200.0, n)
    _retained(win, win.ep_current)
    win.ep_current = win.ep_current + 1.0
    rows = _export(win, monkeypatch, tmp_path)
    header = next(r for r in rows if r and r[0] == "#")
    assert "sigma(d) (nm), 1 sigma, data rows only" not in header
    assert "PARAMETER BUDGET (retained RE result)" not in [r[0] for r in rows if r]
