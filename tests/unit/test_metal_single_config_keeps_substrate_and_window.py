"""A METAL SINGLE configuration must bring back its substrate and its wavelength window (audit 2026-11-15, M-L6e).

The substrate was not saved (a reload fell back to the default), and the saved lmin/lmax_filter were overwritten by
the full range of the target as soon as the configuration reloaded it: the fit ran on another substrate and another
window than the saved one, without a message.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TARGET = ROOT / "example" / "example_metal_single" / "Target_Titane_Simu_20nm.xlsx"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "METAL single config", main_windows_only=True)


def _window():
    from certus.ui.certus_metal_single_gui import CertusMetalSingleApp

    return CertusMetalSingleApp()


@pytest.mark.unit
def test_a_saved_configuration_brings_back_its_substrate_and_window(qapp) -> None:
    first = _window()
    try:
        assert first.load_target_file(str(TARGET))
        choices = [first.combo_substrate.itemText(i) for i in range(first.combo_substrate.count())]
        other = next(c for c in choices if c != first.combo_substrate.currentText())
        first.combo_substrate.setCurrentText(other)
        first.widgets["lmin_filter"].setText("450.0")
        first.widgets["lmax_filter"].setText("800.0")
        config = first._get_config_dict()
        config["target_file"] = str(TARGET)
    finally:
        first.close()

    second = _window()
    try:
        second._apply_config(config)
        assert second.combo_substrate.currentText() == other
        assert second.widgets["lmin_filter"].text() == "450.0"
        assert second.widgets["lmax_filter"].text() == "800.0"
    finally:
        second.close()
