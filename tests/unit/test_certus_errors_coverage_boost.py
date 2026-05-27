"""Additional coverage tests for certus_errors.py — validation branches and error helpers."""

import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.mark.unit
def test_validate_wavelength_range_happy_path():
    mod = importlib.import_module("certus.utils.errors")
    assert mod.validate_wavelength_range(400.0, 700.0) is None


@pytest.mark.unit
def test_validate_wavelength_range_rejects_non_finite():
    mod = importlib.import_module("certus.utils.errors")
    with pytest.raises(mod.CertusValidationError) as exc:
        mod.validate_wavelength_range(float("nan"), 700.0)
    assert "Invalid values" in exc.value.full_message


@pytest.mark.unit
def test_validate_wavelength_range_rejects_inverted_bounds():
    mod = importlib.import_module("certus.utils.errors")
    with pytest.raises(mod.CertusValidationError) as exc:
        mod.validate_wavelength_range(700.0, 400.0)
    assert "must be less than" in exc.value.full_message


@pytest.mark.unit
def test_validate_thickness_branches():
    mod = importlib.import_module("certus.utils.errors")
    assert mod.validate_thickness(10.0) is None
    with pytest.raises(mod.CertusValidationError):
        mod.validate_thickness(float("inf"))
    with pytest.raises(mod.CertusValidationError):
        mod.validate_thickness(-1.0)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_thickness(0.0, allow_zero=False)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_thickness(mod.THICKNESS_MAX + 1.0)


@pytest.mark.unit
def test_validate_refractive_index_branches():
    mod = importlib.import_module("certus.utils.errors")
    assert mod.validate_refractive_index(1.5, k=0.1) is None
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(float("nan"))
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(-1.0)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(0.5)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(mod.N_MAX + 1.0)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(1.5, k=float("inf"))
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(1.5, k=-0.1)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_refractive_index(1.5, k=mod.K_MAX + 1.0)


@pytest.mark.unit
def test_validate_spectral_data_branches():
    mod = importlib.import_module("certus.utils.errors")
    wl = np.array([400.0, 500.0, 600.0])
    vals = np.array([0.1, 0.2, 0.3])
    assert mod.validate_spectral_data(wl, vals) is None
    with pytest.raises(mod.CertusValidationError):
        mod.validate_spectral_data([], [])
    with pytest.raises(mod.CertusValidationError):
        mod.validate_spectral_data([400.0], [0.1], min_points=2)
    with pytest.raises(mod.CertusValidationError):
        mod.validate_spectral_data([400.0, 300.0], [0.1, 0.2])
    with pytest.raises(mod.CertusValidationError):
        mod.validate_spectral_data([400.0, 500.0], [0.1, 1.2])


@pytest.mark.unit
def test_validate_parameter_range_and_messages():
    mod = importlib.import_module("certus.utils.errors")
    assert mod.validate_parameter_range(5.0, 0.0, 10.0, "param") is None
    with pytest.raises(mod.CertusValidationError):
        mod.validate_parameter_range(float("nan"), 0.0, 10.0, "param")
    with pytest.raises(mod.CertusValidationError):
        mod.validate_parameter_range(-1.0, 0.0, 10.0, "param", "nm")
    with pytest.raises(mod.CertusValidationError):
        mod.validate_parameter_range(11.0, 0.0, 10.0, "param", "nm")


@pytest.mark.unit
def test_error_message_helpers():
    mod = importlib.import_module("certus.utils.errors")
    title, details, suggestion = mod.get_error_message("file_not_found", path="x.csv")
    assert title
    assert "x.csv" in details
    assert suggestion
    title2, details2, suggestion2 = mod.get_error_message("does_not_exist", details="boom")
    assert title2 == "Unexpected error"
    assert "boom" in details2
    assert suggestion2


@pytest.mark.unit
def test_show_helpers_use_qmessagebox(monkeypatch):
    mod = importlib.import_module("certus.utils.errors")
    calls = []
    
    class DummyQMessageBox:
        class Icon:
            Critical = "Critical"
            Warning = "Warning"
            Information = "Information"
        def __init__(self, parent=None):
            self.parent = parent
        def setIcon(self, icon):
            calls.append(("setIcon", icon))
        def setWindowTitle(self, title):
            calls.append(("setWindowTitle", title))
        def setText(self, text):
            calls.append(("setText", text))
        def setInformativeText(self, text):
            calls.append(("setInformativeText", text))
        def exec(self):
            calls.append("exec")

    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox", DummyQMessageBox)

    mod.show_error(None, "generic_error", details="boom")
    assert ("setIcon", "Critical") in calls
    assert "exec" in calls

    calls.clear()
    mod.show_warning(None, "Warn", "Message", "Hint")
    assert ("setIcon", "Warning") in calls
    assert "exec" in calls
