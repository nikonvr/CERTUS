"""Chantier 18b: SUBSTRATE stands on the suite's base window, so it follows the theme and keeps its session.

It was a bare QMainWindow with neither `_collect_config` nor `_apply_config`: a SUBSTRATE cut by a crash or a power
failure lost its workbook and its fit settings. What it saves: the source workbook, the fit window and the Sellmeier
settings. A result is not saved: the operator runs the fit again.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from certus.ui.certus_base_app import CertusBaseApp


@pytest.fixture
def workbook(tmp_path):
    x = np.linspace(400.0, 1100.0, 141)
    df = pd.DataFrame({"Wavelength": x, "T substrate nu": 0.92 - 0.00001 * (x - 400.0), "T filter": 0.5 + 0.0 * x})
    path = tmp_path / "substrate.xlsx"
    df.to_excel(path, sheet_name="measurement", index=False)
    return path, df


def _substrate(qapp):
    from certus.ui.certus_substrate_ui import SubstrateIndexGUI

    win = SubstrateIndexGUI()
    qapp.processEvents()
    return win


def test_substrate_is_a_certus_window(qapp):
    win = _substrate(qapp)
    try:
        assert isinstance(win, CertusBaseApp)
        assert win._session_supported()
        assert win.windowTitle().startswith("CERTUS-SUBSTRATE-INDEX")
    finally:
        win.close()


def test_the_session_brings_back_the_workbook_and_the_fit_settings(qapp, workbook, monkeypatch):
    path, df = workbook
    import certus.ui.certus_substrate_ui as mod

    monkeypatch.setattr(mod, "open_measurement_excel_interactive", lambda *_a, **_k: (df.copy(), str(path), str(path.parent)))
    first = _substrate(qapp)
    try:
        first.load_file()
        first.fit_lmin_spin.setValue(450.0)
        first.fit_lmax_spin.setValue(1000.0)
        first.sell_auto_chk.setChecked(False)
        first.sell_timeout_spin.setValue(12.0)
        first.sell_de_iter_spin.setValue(400)
        first.sell_ls_nfev_spin.setValue(5000)
        first.sell_log_l_chk.setChecked(True)
        saved = first._collect_config()
    finally:
        first.close()

    second = _substrate(qapp)
    try:
        second._session_apply(saved)
        assert second._last_loaded_measurement_path == str(path)
        assert list(second.df.columns) == ["Wavelength", "T substrate nu"]  # the same bare-substrate filter as a load
        assert second.btn_calc_n.isEnabled()
        assert second._get_fit_range_from_ui() == (450.0, 1000.0)
        assert not second.sell_auto_chk.isChecked()
        assert second.sell_timeout_spin.value() == 12.0
        assert second.sell_de_iter_spin.value() == 400
        assert second.sell_ls_nfev_spin.value() == 5000
        assert second.sell_log_l_chk.isChecked()
    finally:
        second.close()


def test_a_session_whose_workbook_is_gone_keeps_the_settings(qapp, tmp_path):
    win = _substrate(qapp)
    try:
        win._session_apply({"source_file": str(tmp_path / "moved.xlsx"), "fit_min_nm": 500.0, "fit_max_nm": 900.0,
                            "sellmeier_auto": False, "sellmeier_timeout_s": 5.0, "sellmeier_de_maxiter": 200,
                            "sellmeier_ls_max_nfev": 2000, "sellmeier_log_l1l2": False})
        assert win.df is None
        assert win.fit_lmin_spin.value() == 500.0
        assert not win.sell_auto_chk.isChecked()
    finally:
        win.close()
