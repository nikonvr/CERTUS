"""Test that collect_params honors export_excel flag from loaded configuration."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from certus.ui.certus_strat_ui import CertusSTRATApp


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT export_excel config", main_windows_only=True)


@pytest.mark.unit
def test_collect_params_defaults_export_excel_to_true(qapp) -> None:
    window = CertusSTRATApp()
    window._loaded_config = {}
    assert window.collect_params()["export_excel"] is True


@pytest.mark.unit
@pytest.mark.parametrize("false_val", [False, "false"])
def test_collect_params_honors_export_excel_false(qapp, false_val) -> None:
    window = CertusSTRATApp()
    window._loaded_config = {"export_excel": false_val}
    assert window.collect_params()["export_excel"] is False


@pytest.mark.unit
@pytest.mark.parametrize("true_val", [True, "true"])
def test_collect_params_honors_export_excel_true(qapp, true_val) -> None:
    window = CertusSTRATApp()
    window._loaded_config = {"export_excel": true_val}
    assert window.collect_params()["export_excel"] is True
