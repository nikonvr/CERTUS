"""Tests for the Data-Th tab clipboard copy functionality.

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠  CLIPBOARD Qt — ISOLATION INTER-TESTS :

   test_data_th_copy_clipboard_contains_headers_and_rows  utilise le
   clipboard SYSTÈME via QApplication.clipboard(). Ce clipboard est
   PARTAGÉ entre tous les tests Qt de la session.

   RÈGLES :
   1. TOUJOURS appeler  cb.clear()  AVANT d'écrire dans le clipboard,
      pour éviter les résidus d'un test antérieur.
   2. Si le clipboard est inaccessible (CI headless, session Qt corrompue),
      le test SKIP au lieu de FAIL (ne pas changer ce comportement).
   3. Ne pas dépendre de l'ORDRE d'exécution des tests pour ce test.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtWidgets import QTableWidgetItem

from CERTUS_INDEX_SPLINE import CertusIndexSplineApp


class _Btn:
    def __init__(self) -> None:
        self.enabled: bool | None = None
        self._text = ""

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)

    def setText(self, value: str) -> None:
        self._text = str(value)


def test_data_th_copy_clipboard_contains_headers_and_rows(qapp) -> None:
    app = SimpleNamespace(
        table_data_th=None,
        btn_copy_data_th=_Btn(),
        lbl_status=SimpleNamespace(setText=lambda _txt: None),
    )

    from certus_ui import ExcelTableWidget

    table = ExcelTableWidget()
    table.setColumnCount(7)
    table.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
    table.setRowCount(2)

    # Row 0
    table.setItem(0, 0, QTableWidgetItem("400.0000"))
    table.setItem(0, 1, QTableWidgetItem("1.6200"))
    table.setItem(0, 2, QTableWidgetItem("1.30e-04"))
    table.setItem(0, 3, QTableWidgetItem("212.5000"))
    table.setItem(0, 4, QTableWidgetItem("1.5200"))
    table.setItem(0, 5, QTableWidgetItem("0.750000"))
    table.setItem(0, 6, QTableWidgetItem("0.100000"))

    # Row 1
    table.setItem(1, 0, QTableWidgetItem("405.0000"))
    table.setItem(1, 1, QTableWidgetItem("1.6300"))
    table.setItem(1, 2, QTableWidgetItem("1.40e-04"))
    table.setItem(1, 3, QTableWidgetItem("212.5000"))
    table.setItem(1, 4, QTableWidgetItem("1.5200"))
    table.setItem(1, 5, QTableWidgetItem("0.748000"))
    table.setItem(1, 6, QTableWidgetItem("0.101000"))

    app.table_data_th = table

    # Clear clipboard before test to avoid stale state from other tests
    cb = qapp.clipboard()
    cb.clear()

    CertusIndexSplineApp._copy_data_th_to_clipboard(app)

    txt = cb.text()
    if not txt:
        pytest.skip("Clipboard not functional in this test environment")
    lines = txt.splitlines()

    assert lines[0] == "lambda (nm)\tn\tk\td (nm)\tns\tTth\tRth"
    assert lines[1].startswith("400.0000\t1.6200\t1.30e-04")
    assert lines[2].startswith("405.0000\t1.6300\t1.40e-04")


def test_refresh_data_th_table_enables_copy_button_for_non_empty_data() -> None:
    app = SimpleNamespace(
        df=None,
        logger=None,
        btn_copy_data_th=_Btn(),
    )
    app._lam_piecewise_report_grid_nm = CertusIndexSplineApp._lam_piecewise_report_grid_nm
    app._prepare_data_th_tab_series = lambda r: CertusIndexSplineApp._prepare_data_th_tab_series(app, r)
    app._fmt_n_data_tab = CertusIndexSplineApp._fmt_n_data_tab
    app._fmt_k_data_tab = CertusIndexSplineApp._fmt_k_data_tab

    from certus_ui import ExcelTableWidget

    table = ExcelTableWidget()
    app.table_data_th = table

    result = {
        "lam_nm": np.array([400.0, 405.0], dtype=np.float64),
        "n_lam": np.array([1.62, 1.63], dtype=np.float64),
        "k_lam": np.array([1.3e-4, 1.4e-4], dtype=np.float64),
        "t_theo": np.array([0.75, 0.748], dtype=np.float64),
        "r_theo": np.array([0.10, 0.101], dtype=np.float64),
        "d_nm": 212.5,
        "substrate_name": "Sapphire (Al2O3)",
    }

    CertusIndexSplineApp._refresh_data_th_table(app, result)

    assert app.btn_copy_data_th.enabled is True
    assert app.table_data_th.rowCount() > 0
