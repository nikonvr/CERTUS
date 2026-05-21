"""Tests for certus_errors.py — validation functions.

Covers:
- validate_wavelength_range (6 error paths + 1 happy)
- validate_thickness (5 error paths + 1 happy)
- validate_refractive_index (7 error paths + 1 happy)
- validate_spectral_data (7 error paths + 1 happy)
- validate_parameter_range (3 error paths + 1 happy)
- get_error_message (known + unknown code)
- format_validation_error
- Exception hierarchy
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus_errors import (
    CertusComputationError,
    CertusConvergenceError,
    CertusDataError,
    CertusError,
    CertusFileError,
    CertusMaterialError,
    CertusValidationError,
    CertusDomainError,
    PhysicsConvergenceError,
    ConfigurationCorruptionError,
    CertusConfigError,
    format_validation_error,
    get_error_message,
    validate_parameter_range,
    validate_refractive_index,
    validate_spectral_data,
    validate_thickness,
    validate_wavelength_range,
    safe_ui_action,
    show_error,
    show_warning,
    show_validation_error,
)


# ─────────────────────────────────────────────────────────────────────
# Exception hierarchy
# ─────────────────────────────────────────────────────────────────────


class TestExceptionHierarchy:
    def test_validation_error_is_certus_error(self):
        assert issubclass(CertusValidationError, CertusError)

    def test_file_error_is_certus_error(self):
        assert issubclass(CertusFileError, CertusError)

    def test_data_error_is_certus_error(self):
        assert issubclass(CertusDataError, CertusError)

    def test_computation_error_is_certus_error(self):
        assert issubclass(CertusComputationError, CertusError)

    def test_convergence_error_hierarchy(self):
        from certus_core import CertusOptimizationError
        assert issubclass(CertusConvergenceError, CertusOptimizationError)

    def test_material_error_hierarchy(self):
        from certus_core import CertusPhysicsError
        assert issubclass(CertusMaterialError, CertusPhysicsError)

    def test_domain_error_hierarchy(self):
        assert issubclass(CertusDomainError, CertusError)

    def test_physics_convergence_error_hierarchy(self):
        assert issubclass(PhysicsConvergenceError, CertusDomainError)
        assert issubclass(PhysicsConvergenceError, CertusConvergenceError)

    def test_configuration_corruption_error_hierarchy(self):
        assert issubclass(ConfigurationCorruptionError, CertusDomainError)
        assert issubclass(ConfigurationCorruptionError, CertusConfigError)


# ─────────────────────────────────────────────────────────────────────
# validate_wavelength_range
# ─────────────────────────────────────────────────────────────────────


class TestValidateWavelengthRange:
    def test_valid_range(self):
        validate_wavelength_range(400.0, 800.0)  # Should not raise

    def test_nan_raises(self):
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(float("nan"), 800.0)

    def test_inf_raises(self):
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(400.0, float("inf"))

    def test_min_ge_max_raises(self):
        with pytest.raises(CertusValidationError, match="Invalid wavelength range"):
            validate_wavelength_range(800.0, 400.0)

    def test_equal_min_max_raises(self):
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(500.0, 500.0)

    def test_below_physical_limit_raises(self):
        with pytest.raises(CertusValidationError, match="too low"):
            validate_wavelength_range(50.0, 800.0)

    def test_above_physical_limit_raises(self):
        with pytest.raises(CertusValidationError, match="too high"):
            validate_wavelength_range(400.0, 25000.0)

    def test_negative_raises(self):
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(-100.0, 800.0)


# ─────────────────────────────────────────────────────────────────────
# validate_thickness
# ─────────────────────────────────────────────────────────────────────


class TestValidateThickness:
    def test_valid_thickness(self):
        validate_thickness(100.0)

    def test_zero_allowed(self):
        validate_thickness(0.0, allow_zero=True)

    def test_zero_not_allowed(self):
        with pytest.raises(CertusValidationError, match="Zero thickness"):
            validate_thickness(0.0, allow_zero=False)

    def test_nan_raises(self):
        with pytest.raises(CertusValidationError, match="Invalid"):
            validate_thickness(float("nan"))

    def test_negative_raises(self):
        with pytest.raises(CertusValidationError, match="Negative"):
            validate_thickness(-5.0)

    def test_too_large_raises(self):
        with pytest.raises(CertusValidationError, match="too large"):
            validate_thickness(2_000_000.0)

    def test_custom_max(self):
        with pytest.raises(CertusValidationError):
            validate_thickness(500.0, max_thickness=200.0)


# ─────────────────────────────────────────────────────────────────────
# validate_refractive_index
# ─────────────────────────────────────────────────────────────────────


class TestValidateRefractiveIndex:
    def test_valid_index(self):
        validate_refractive_index(2.3)

    def test_valid_with_k(self):
        validate_refractive_index(2.3, k=0.01)

    def test_nan_raises(self):
        with pytest.raises(CertusValidationError, match="Invalid"):
            validate_refractive_index(float("nan"))

    def test_negative_raises(self):
        with pytest.raises(CertusValidationError, match="Negative"):
            validate_refractive_index(-1.0)

    def test_below_one_raises(self):
        with pytest.raises(CertusValidationError, match="too low"):
            validate_refractive_index(0.5)

    def test_below_one_allowed(self):
        validate_refractive_index(0.5, allow_below_one=True)

    def test_too_high_raises(self):
        with pytest.raises(CertusValidationError, match="too high"):
            validate_refractive_index(15.0)

    def test_k_nan_raises(self):
        with pytest.raises(CertusValidationError, match="Invalid extinction"):
            validate_refractive_index(2.3, k=float("nan"))

    def test_k_negative_raises(self):
        with pytest.raises(CertusValidationError, match="Negative extinction"):
            validate_refractive_index(2.3, k=-0.1)

    def test_k_too_high_raises(self):
        with pytest.raises(CertusValidationError, match="very high"):
            validate_refractive_index(2.3, k=25.0)


# ─────────────────────────────────────────────────────────────────────
# validate_spectral_data
# ─────────────────────────────────────────────────────────────────────


class TestValidateSpectralData:
    def test_valid_data(self):
        wl = np.array([400.0, 500.0, 600.0])
        val = np.array([0.1, 0.5, 0.9])
        validate_spectral_data(wl, val)

    def test_empty_raises(self):
        with pytest.raises(CertusValidationError, match="Empty"):
            validate_spectral_data([], [])

    def test_mismatched_lengths(self):
        with pytest.raises(CertusValidationError, match="Mismatched"):
            validate_spectral_data([400, 500], [0.1])

    def test_insufficient_points(self):
        with pytest.raises(CertusValidationError, match="Insufficient"):
            validate_spectral_data([400.0], [0.1], min_points=2)

    def test_nan_wavelengths(self):
        with pytest.raises(CertusValidationError, match="NaN.*wavelengths"):
            validate_spectral_data([400.0, float("nan")], [0.1, 0.2])

    def test_nan_values(self):
        with pytest.raises(CertusValidationError, match="NaN"):
            validate_spectral_data([400.0, 500.0], [0.1, float("nan")])

    def test_unsorted_raises(self):
        with pytest.raises(CertusValidationError, match="not sorted"):
            validate_spectral_data([500.0, 400.0], [0.1, 0.2])

    def test_out_of_bounds(self):
        with pytest.raises(CertusValidationError, match="out of bounds"):
            validate_spectral_data([400.0, 500.0], [0.1, 1.5])

    def test_no_bounds_check(self):
        validate_spectral_data([400.0, 500.0], [0.1, 1.5], check_bounds=False)


# ─────────────────────────────────────────────────────────────────────
# validate_parameter_range
# ─────────────────────────────────────────────────────────────────────


class TestValidateParameterRange:
    def test_valid(self):
        validate_parameter_range(5.0, 0.0, 10.0, "test")

    def test_nan_raises(self):
        with pytest.raises(CertusValidationError, match="Invalid"):
            validate_parameter_range(float("nan"), 0.0, 10.0, "test")

    def test_below_min_raises(self):
        with pytest.raises(CertusValidationError, match="too low"):
            validate_parameter_range(-1.0, 0.0, 10.0, "test")

    def test_above_max_raises(self):
        with pytest.raises(CertusValidationError, match="too high"):
            validate_parameter_range(15.0, 0.0, 10.0, "test")

    def test_unit_in_message(self):
        with pytest.raises(CertusValidationError, match="nm"):
            validate_parameter_range(-1.0, 0.0, 10.0, "thickness", unit="nm")


# ─────────────────────────────────────────────────────────────────────
# get_error_message & format_validation_error
# ─────────────────────────────────────────────────────────────────────


class TestErrorMessages:
    def test_known_code(self):
        title, details, suggestion = get_error_message("file_not_found", path="/test.csv")
        assert "not found" in title.lower()
        assert "/test.csv" in details

    def test_unknown_code_falls_back(self):
        title, details, suggestion = get_error_message("nonexistent_code")
        assert "unexpected" in title.lower()

    def test_format_kwargs_missing(self):
        title, details, suggestion = get_error_message("file_not_found")
        assert isinstance(details, str)

    def test_format_validation_error(self):
        try:
            validate_wavelength_range(800.0, 400.0)
        except CertusValidationError as e:
            msg = format_validation_error(e)
            assert isinstance(msg, str)
            assert len(msg) > 0


# ─────────────────────────────────────────────────────────────────────
# UI helpers & safe_ui_action
# ─────────────────────────────────────────────────────────────────────


class TestUIHelpers:
    def test_show_error(self, monkeypatch):
        calls = []
        class DummyQMessageBox:
            Icon = None
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

        # Mock the QMessageBox Icon enum subclass
        class DummyIcon:
            Critical = "Critical"
            Warning = "Warning"
            Information = "Information"
        DummyQMessageBox.Icon = DummyIcon

        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox", DummyQMessageBox)
        show_error(None, "file_not_found", path="test.csv")
        assert ("setIcon", "Critical") in calls
        assert any(c[0] == "setWindowTitle" for c in calls)
        assert any(c[0] == "setText" for c in calls)
        assert any(c[0] == "setInformativeText" for c in calls)
        assert "exec" in calls

    def test_show_warning(self, monkeypatch):
        calls = []
        class DummyQMessageBox:
            Icon = None
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

        class DummyIcon:
            Critical = "Critical"
            Warning = "Warning"
            Information = "Information"
        DummyQMessageBox.Icon = DummyIcon

        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox", DummyQMessageBox)
        show_warning(None, "My Title", "My message", "My suggestion")
        assert ("setIcon", "Warning") in calls
        assert ("setWindowTitle", "My Title") in calls
        assert ("setText", "My message") in calls
        assert ("setInformativeText", "💡 My suggestion") in calls
        assert "exec" in calls

    def test_show_validation_error(self, monkeypatch):
        calls = []
        class DummyQMessageBox:
            Icon = None
            def __init__(self, parent=None):
                self.parent = parent
            def setIcon(self, icon):
                calls.append(("setIcon", icon))
            def setWindowTitle(self, title):
                calls.append(("setWindowTitle", title))
            def setText(self, text):
                calls.append(("setText", text))
            def setDetailedText(self, text):
                calls.append(("setDetailedText", text))
            def setInformativeText(self, text):
                calls.append(("setInformativeText", text))
            def exec(self):
                calls.append("exec")

        class DummyIcon:
            Critical = "Critical"
            Warning = "Warning"
            Information = "Information"
        DummyQMessageBox.Icon = DummyIcon

        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox", DummyQMessageBox)
        err = CertusValidationError("msg", details="det", suggestion="sug")
        show_validation_error(None, err)
        assert ("setIcon", "Warning") in calls
        assert ("setWindowTitle", "Validation Error") in calls
        assert ("setText", "msg") in calls
        assert ("setDetailedText", "det") in calls
        assert ("setInformativeText", "💡 sug") in calls
        assert "exec" in calls


class TestSafeUIAction:
    def test_safe_ui_action_success(self):
        @safe_ui_action
        def dummy_func(a, b):
            return a + b
        assert dummy_func(2, 3) == 5

    def test_safe_ui_action_exception_caught(self):
        @safe_ui_action
        def dummy_func():
            raise ValueError("Something went wrong")
        
        # Should not raise, should return None
        assert dummy_func() is None

    def test_safe_ui_action_certus_validation_error(self):
        @safe_ui_action
        def dummy_func():
            raise CertusValidationError("Validation failed")
        assert dummy_func() is None

    def test_safe_ui_action_certus_domain_error(self):
        @safe_ui_action
        def dummy_func():
            raise CertusDomainError("Domain failed")
        assert dummy_func() is None

    def test_safe_ui_action_unexpected_exception(self):
        @safe_ui_action
        def dummy_func():
            raise ZeroDivisionError("division by zero")
        assert dummy_func() is None

    def test_safe_ui_action_extra_arguments(self):
        calls = []

        class Dummy:
            @safe_ui_action
            def slot(self):
                calls.append("called")

        d = Dummy()
        # Simulated PyQt clicked call with extra boolean checked argument
        d.slot(False)
        assert calls == ["called"]


