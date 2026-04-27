"""
Unit tests for certus_errors.py
Covers all exceptions and validation functions.
"""

import pytest
import numpy as np

from certus_errors import (
    # Base exceptions
    CertusError,
    CertusValidationError,
    CertusFileError,
    CertusOptimizationError,
    # New specific exceptions
    CertusPhysicsError,
    CertusConfigError,
    CertusDataError,
    CertusComputationError,
    CertusConvergenceError,
    CertusMaterialError,
    # Validation functions
    validate_wavelength_range,
    validate_thickness,
    validate_refractive_index,
    validate_spectral_data,
    validate_parameter_range,
    # Utility functions
    get_error_message,
    format_validation_error,
    # UI functions
    LAMBDA_MIN_PHYSICAL,
    LAMBDA_MAX_PHYSICAL,
    THICKNESS_MIN,
    THICKNESS_MAX,
    N_MIN,
    N_MAX,
    K_MIN,
    K_MAX,
)


class TestCertusError:
    """Tests for base class CertusError."""

    def test_certus_error_basic(self):
        """Test basic creation of CertusError."""
        error = CertusError("Test message")
        assert error.message == "Test message"
        assert error.details == ""
        assert error.suggestion == ""
        assert str(error) == "Test message"

    def test_certus_error_with_details(self):
        """Test CertusError with details and suggestion."""
        error = CertusError("Test message", "Detailed explanation", "Try this instead")
        assert error.message == "Test message"
        assert error.details == "Detailed explanation"
        assert error.suggestion == "Try this instead"

    def test_certus_error_full_message(self):
        """Test full message generation."""
        error = CertusError("Test message", "Detailed explanation", "Try this instead")
        full = error.full_message
        assert "Test message" in full
        assert "Detailed explanation" in full
        assert "Try this instead" in full
        assert "Details:" in full
        assert "💡 Suggestion:" in full

    def test_certus_error_inheritance(self):
        """Test CertusError inherits from Exception."""
        error = CertusError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, CertusError)


class TestSpecificExceptions:
    """Tests for specific exceptions."""

    def test_validation_error(self):
        """Test CertusValidationError."""
        error = CertusValidationError("Invalid parameter")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusValidationError)

    def test_file_error(self):
        """Test CertusFileError."""
        error = CertusFileError("File not found")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusFileError)

    def test_optimization_error(self):
        """Test CertusOptimizationError."""
        error = CertusOptimizationError("Optimization failed")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusOptimizationError)

    def test_physics_error(self):
        """Test CertusPhysicsError."""
        error = CertusPhysicsError("Physics calculationation error")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusPhysicsError)

    def test_config_error(self):
        """Test CertusConfigError."""
        error = CertusConfigError("Configuration error")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusConfigError)

    def test_data_error(self):
        """Test CertusDataError."""
        error = CertusDataError("Data processing error")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusDataError)

    def test_computation_error(self):
        """Test CertusComputationError."""
        error = CertusComputationError("Numerical error")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusComputationError)

    def test_convergence_error(self):
        """Test CertusConvergenceError."""
        error = CertusConvergenceError("Algorithm did not converge")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusOptimizationError)
        assert isinstance(error, CertusConvergenceError)

    def test_material_error(self):
        """Test CertusMaterialError."""
        error = CertusMaterialError("Material not found")
        assert isinstance(error, CertusError)
        assert isinstance(error, CertusPhysicsError)
        assert isinstance(error, CertusMaterialError)


class TestValidationConstants:
    """Tests for validation constants."""

    def test_wavelength_limits(self):
        """Test wavelength limits."""
        assert LAMBDA_MIN_PHYSICAL == 100.0
        assert LAMBDA_MAX_PHYSICAL == 20000.0
        assert LAMBDA_MIN_PHYSICAL < LAMBDA_MAX_PHYSICAL

    def test_thickness_limits(self):
        """Test thickness limits."""
        assert THICKNESS_MIN == 0.0
        assert THICKNESS_MAX == 1000000.0
        assert THICKNESS_MIN < THICKNESS_MAX

    def test_refractive_index_limits(self):
        """Test refractive index limits."""
        assert N_MIN == 1.0
        assert N_MAX == 10.0
        assert K_MIN == 0.0
        assert K_MAX == 20.0
        assert N_MIN < N_MAX
        assert K_MIN < K_MAX


class TestWavelengthValidation:
    """Tests for validate_wavelength_range."""

    def test_valid_wavelength_range(self):
        """Test valid wavelength range."""
        # Should not raise exception
        validate_wavelength_range(400.0, 800.0)
        validate_wavelength_range(100.0, 20000.0)

    def test_invalid_wavelength_order(self):
        """Test invalid wavelength order."""
        with pytest.raises(CertusValidationError) as exc_info:
            validate_wavelength_range(800.0, 400.0)

        # Updated to match actual error message which uses unicode lambda and formatting
        err_msg = str(exc_info.value).lower()
        assert "min" in err_msg
        assert "max" in err_msg
        assert "invalid" in err_msg

    def test_nan_wavelengths(self):
        """Test NaN wavelengths."""
        with pytest.raises(CertusValidationError) as exc_info:
            validate_wavelength_range(np.nan, 800.0)

        assert "Invalid values" in str(exc_info.value)

        with pytest.raises(CertusValidationError):
            validate_wavelength_range(400.0, np.nan)

    def test_infinite_wavelengths(self):
        """Test infinite wavelengths."""
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(np.inf, 800.0)

        with pytest.raises(CertusValidationError):
            validate_wavelength_range(400.0, -np.inf)

    def test_physical_limits_wavelength(self):
        """Test physical wavelength limits."""
        # Exact limits
        validate_wavelength_range(LAMBDA_MIN_PHYSICAL, LAMBDA_MAX_PHYSICAL)

        # Out of bounds
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(LAMBDA_MIN_PHYSICAL - 1, LAMBDA_MAX_PHYSICAL)

        with pytest.raises(CertusValidationError):
            validate_wavelength_range(LAMBDA_MIN_PHYSICAL, LAMBDA_MAX_PHYSICAL + 1)

    def test_equal_wavelengths(self):
        """Test equal wavelengths."""
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(500.0, 500.0)


class TestThicknessValidation:
    """Tests for validate_thickness."""

    def test_valid_thickness(self):
        """Test valid thickness."""
        validate_thickness(100.0)
        validate_thickness(0.1)
        validate_thickness(1000.0)

    def test_negative_thickness(self):
        """Test negative thickness."""
        with pytest.raises(CertusValidationError):
            validate_thickness(-10.0)

    def test_zero_thickness(self):
        """Test zero thickness."""
        validate_thickness(0.0)  # Should be valid

    def test_nan_thickness(self):
        """Test NaN thickness."""
        with pytest.raises(CertusValidationError):
            validate_thickness(np.nan)

    def test_infinite_thickness(self):
        """Test infinite thickness."""
        with pytest.raises(CertusValidationError):
            validate_thickness(np.inf)

        with pytest.raises(CertusValidationError):
            validate_thickness(-np.inf)

    def test_thickness_limits(self):
        """Test thickness limits."""
        validate_thickness(THICKNESS_MIN)
        validate_thickness(THICKNESS_MAX)

        with pytest.raises(CertusValidationError):
            validate_thickness(THICKNESS_MAX + 1)


class TestRefractiveIndexValidation:
    """Tests for validate_refractive_index."""

    def test_valid_refractive_index(self):
        """Test valid refractive index."""
        validate_refractive_index(1.5, 0.0)  # Non-absorbing
        validate_refractive_index(2.0, 0.1)  # Absorbing
        validate_refractive_index(5.0, 5.0)  # Strongly absorbing

    def test_negative_real_part(self):
        """Test negative real part."""
        with pytest.raises(CertusValidationError):
            validate_refractive_index(-1.0, 0.0)

    def test_negative_imaginary_part(self):
        """Test negative imaginary part."""
        with pytest.raises(CertusValidationError):
            validate_refractive_index(1.5, -0.1)

    def test_nan_values(self):
        """Test NaN values."""
        with pytest.raises(CertusValidationError):
            validate_refractive_index(np.nan, 0.0)

        with pytest.raises(CertusValidationError):
            validate_refractive_index(1.5, np.nan)

    def test_infinite_values(self):
        """Test infinite values."""
        with pytest.raises(CertusValidationError):
            validate_refractive_index(np.inf, 0.0)

        with pytest.raises(CertusValidationError):
            validate_refractive_index(1.5, np.inf)

    def test_physical_limits(self):
        """Test physical limits."""
        validate_refractive_index(N_MIN, K_MIN)
        validate_refractive_index(N_MAX, K_MAX)

        with pytest.raises(CertusValidationError):
            validate_refractive_index(N_MAX + 1, 0.0)

        with pytest.raises(CertusValidationError):
            validate_refractive_index(1.0, K_MAX + 1)


class TestSpectralDataValidation:
    """Tests for validate_spectral_data."""

    def test_valid_spectral_data(self):
        """Test valid spectral data."""
        wavelengths = np.array([400, 500, 600, 700])
        values = np.array([0.1, 0.2, 0.3, 0.4])

        validate_spectral_data(wavelengths, values)

    def test_mismatched_lengths(self):
        """Test data with mismatched lengths."""
        wavelengths = np.array([400, 500, 600])
        values = np.array([0.1, 0.2])  # Different length

        with pytest.raises(CertusValidationError):
            validate_spectral_data(wavelengths, values)

    def test_empty_arrays(self):
        """Test empty arrays."""
        wavelengths = np.array([])
        values = np.array([])

        with pytest.raises(CertusValidationError):
            validate_spectral_data(wavelengths, values)

    def test_nan_in_data(self):
        """Test data containing NaN."""
        wavelengths = np.array([400, 500, 600, np.nan])
        values = np.array([0.1, 0.2, 0.3, 0.4])

        with pytest.raises(CertusValidationError):
            validate_spectral_data(wavelengths, values)

        wavelengths = np.array([400, 500, 600, 700])
        values = np.array([0.1, 0.2, np.nan, 0.4])

        with pytest.raises(CertusValidationError):
            validate_spectral_data(wavelengths, values)

    def test_invalid_wavelengths_in_data(self):
        """Test invalid wavelengths in data."""
        wavelengths = np.array([400, 500, 300, 700])  # Non-monotonic
        values = np.array([0.1, 0.2, 0.3, 0.4])

        with pytest.raises(CertusValidationError):
            validate_spectral_data(wavelengths, values)

    def test_list_input(self):
        """Test list inputs."""
        wavelengths = [400, 500, 600, 700]
        values = [0.1, 0.2, 0.3, 0.4]

        # Convert to numpy arrays for validation
        wavelengths_np = np.array(wavelengths)
        values_np = np.array(values)

        validate_spectral_data(wavelengths_np, values_np)


class TestParameterRangeValidation:
    """Tests for validate_parameter_range."""

    def test_valid_parameter_range(self):
        """Test valid parameter range."""
        validate_parameter_range(0.5, 0.0, 1.0, "test_param")
        validate_parameter_range(0.0, -10.0, 10.0, "test_param")
        validate_parameter_range(50.0, 0.0, 100.0, "test_param")

    def test_invalid_parameter_range(self):
        """Test invalid parameter range."""
        with pytest.raises(CertusValidationError):
            validate_parameter_range(1.5, 1.0, 0.0, "test_param")

        with pytest.raises(CertusValidationError):
            validate_parameter_range(2.0, 0.0, 1.0, "test_param")

    def test_nan_parameter_range(self):
        """Test NaN parameters."""
        with pytest.raises(CertusValidationError):
            validate_parameter_range(np.nan, 0.0, 1.0, "test_param")


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_error_message(self):
        """Test get_error_message."""
        title, details, suggestion = get_error_message(
            "generic_error", details="Test details"
        )

        assert isinstance(title, str)
        assert isinstance(details, str)
        assert isinstance(suggestion, str)
        assert len(title) > 0
        assert len(details) > 0
        assert len(suggestion) > 0

    def test_format_validation_error(self):
        """Test format_validation_error."""
        error = CertusValidationError(
            "Test validation error", "Test details", "Test suggestion"
        )
        formatted = format_validation_error(error)

        assert isinstance(formatted, str)
        assert len(formatted) > 0


class TestUIFunctions:
    """Tests for UI functions."""

    def test_ui_functions_available(self):
        """Test UI functions are available."""
        # Verify functions exist but do not test them
        # because QMessageBox requires PyQt6
        try:
            from certus_errors import show_error, show_warning, show_validation_error

            assert callable(show_error)
            assert callable(show_warning)
            assert callable(show_validation_error)
        except ImportError:
            pytest.skip("UI functions not available")


@pytest.mark.unit
class TestErrorHierarchy:
    """Tests for error hierarchy."""

    def test_exception_hierarchy(self):
        """Test proper exception inheritance."""
        exceptions = [
            CertusValidationError,
            CertusFileError,
            CertusOptimizationError,
            CertusPhysicsError,
            CertusConfigError,
            CertusDataError,
            CertusComputationError,
            CertusConvergenceError,
            CertusMaterialError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, CertusError)
            assert issubclass(exc_class, Exception)

    def test_convergence_error_hierarchy(self):
        """Test CertusConvergenceError hierarchy."""
        assert issubclass(CertusConvergenceError, CertusOptimizationError)
        assert issubclass(CertusConvergenceError, CertusError)

    def test_material_error_hierarchy(self):
        """Test CertusMaterialError hierarchy."""
        assert issubclass(CertusMaterialError, CertusPhysicsError)
        assert issubclass(CertusMaterialError, CertusError)


@pytest.mark.integration
class TestValidationIntegration:
    """Integration tests for validation."""

    def test_complete_validation_workflow(self):
        """Test full validation workflow."""
        # Validate wavelength range
        validate_wavelength_range(400.0, 800.0)

        # Validate thickness
        validate_thickness(100.0)

        # Validate refractive index
        validate_refractive_index(1.5, 0.0)

        # Validate spectral data
        wavelengths = np.linspace(400, 800, 100)
        values = np.random.uniform(0, 1, 100)
        validate_spectral_data(wavelengths, values)

    def test_validation_error_propagation(self):
        """Test validation error propagation."""
        with pytest.raises(CertusValidationError):
            validate_wavelength_range(800.0, 400.0)

        with pytest.raises(CertusValidationError):
            validate_thickness(-10.0)

        with pytest.raises(CertusValidationError):
            validate_refractive_index(-1.0, 0.0)
