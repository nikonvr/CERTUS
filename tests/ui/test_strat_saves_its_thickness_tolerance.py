"""STRAT saves its thickness tolerance (audit 2026-11-15, M-L6d).

``thickness_tolerance_nm`` is a visible field read by the computation (empty: photometric noise; a value: noise in nm)
but it was not saved: a reloaded configuration changed the noise convention of phase B without a word.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest


@pytest.fixture
def strat(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    try:
        yield win
    finally:
        win.close()


@pytest.mark.parametrize("typed", ["1.5", ""])
def test_the_thickness_tolerance_survives_a_saved_configuration(strat, typed: str) -> None:
    strat.widgets["thickness_tolerance_nm"].setText(typed)
    config = strat._collect_config()
    assert config.get("thickness_tolerance_nm") == typed

    strat.widgets["thickness_tolerance_nm"].setText("9")
    strat.populate_gui_from_config(config)
    assert strat.widgets["thickness_tolerance_nm"].text() == typed
