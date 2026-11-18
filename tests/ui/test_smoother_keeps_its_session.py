"""Chantier 18a: SMOOTHER stands on the suite's base window, so it follows the theme and keeps its session.

It was a bare QMainWindow with neither `_collect_config` nor `_apply_config`: a SMOOTHER cut by a crash or a power
failure lost the file it was smoothing and its settings, while every other window offered them back (U12 A). What it
saves: the source workbook, the smoothing level, the raw traces switch and the isolated curve.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from certus.ui.certus_base_app import CertusBaseApp


@pytest.fixture
def workbook(tmp_path):
    x = np.linspace(400.0, 800.0, 81)
    df = pd.DataFrame({"Wavelength": x, "T1": 0.8 + 0.01 * np.sin(x / 9.0), "T2": 0.6 + 0.01 * np.cos(x / 7.0)})
    path = tmp_path / "spectra.xlsx"
    df.to_excel(path, sheet_name="measurement", index=False)
    return path, df


def _smoother(qapp):
    from certus.ui.certus_curve_smoother import CurveSmootherGUI

    win = CurveSmootherGUI()
    qapp.processEvents()
    return win


def test_smoother_is_a_certus_window(qapp):
    win = _smoother(qapp)
    try:
        assert isinstance(win, CertusBaseApp)
        assert win._session_supported()
        assert win.windowTitle().startswith("CERTUS-SMOOTHER")
    finally:
        win.close()


def test_the_session_brings_back_the_file_and_the_settings(qapp, workbook, monkeypatch):
    path, df = workbook
    import certus.ui.certus_curve_smoother as mod

    monkeypatch.setattr(mod, "open_measurement_excel_interactive", lambda *_a, **_k: (df.copy(), str(path), str(path.parent)))
    first = _smoother(qapp)
    try:
        first.load_file()
        first.combo_mode.setCurrentText("High")
        first.chk_raw.setChecked(False)
        first.combo_isolate.setCurrentText("T2")
        saved = first._collect_config()
    finally:
        first.close()

    second = _smoother(qapp)
    try:
        second._session_apply(saved)
        assert second.file_path == str(path)
        assert second.df is not None
        assert list(second.df.columns) == ["Wavelength", "T1", "T2"]
        assert second.current_level == "High"
        assert not second.chk_raw.isChecked()
        assert second.combo_isolate.currentText() == "T2"
        assert second.btn_save.isEnabled()
    finally:
        second.close()


def test_a_session_whose_file_is_gone_keeps_the_settings_and_says_so(qapp, tmp_path):
    win = _smoother(qapp)
    try:
        win._session_apply({"source_file": str(tmp_path / "moved.xlsx"), "smoothing_level": "Low", "show_raw": True,
                            "isolated_curve": ""})
        assert win.df is None
        assert win.combo_mode.currentText() == "Low"
    finally:
        win.close()
