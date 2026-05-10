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
    format_validation_error,
    get_error_message,
    validate_parameter_range,
    validate_refractive_index,
    validate_spectral_data,
    validate_thickness,
    validate_wavelength_range,
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
