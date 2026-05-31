import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from certus.utils.errors import (
    validate_wavelength_range,
    validate_thickness,
    validate_refractive_index,
    validate_spectral_data,
    validate_parameter_range,
    CertusValidationError,
    get_error_message,
    format_validation_error,
    show_error,
    show_warning,
    show_validation_error,
    safe_ui_action,
)

def test_validate_wavelength_range():
    validate_wavelength_range(400.0, 700.0)

    with pytest.raises(CertusValidationError, match="Invalid values"):
        validate_wavelength_range(np.nan, 700.0)

    with pytest.raises(CertusValidationError, match="Invalid wavelength range"):
        validate_wavelength_range(800.0, 700.0)

    with pytest.raises(CertusValidationError, match="Minimum wavelength too low"):
        validate_wavelength_range(50.0, 700.0)

    with pytest.raises(CertusValidationError, match="Maximum wavelength too high"):
        validate_wavelength_range(400.0, 30000.0)

def test_validate_thickness():
    validate_thickness(100.0)
    validate_thickness(0.0, allow_zero=True)

    with pytest.raises(CertusValidationError, match="Invalid thickness value"):
        validate_thickness(np.nan)

    with pytest.raises(CertusValidationError, match="Negative thickness not allowed"):
        validate_thickness(-10.0)

    with pytest.raises(CertusValidationError, match="Zero thickness not allowed"):
        validate_thickness(0.0, allow_zero=False)

    with pytest.raises(CertusValidationError, match="Thickness too large"):
        validate_thickness(2000000.0)

def test_validate_refractive_index():
    validate_refractive_index(1.5)
    validate_refractive_index(1.5, 0.1)

    with pytest.raises(CertusValidationError, match="Invalid refractive index"):
        validate_refractive_index(np.nan)

    with pytest.raises(CertusValidationError, match="Negative refractive index"):
        validate_refractive_index(-1.0)

    with pytest.raises(CertusValidationError, match="Refractive index too low"):
        validate_refractive_index(0.5, allow_below_one=False)
    
    # Metamaterials allowed
    validate_refractive_index(0.5, allow_below_one=True)

    with pytest.raises(CertusValidationError, match="Refractive index too high"):
        validate_refractive_index(11.0)

    with pytest.raises(CertusValidationError, match="Invalid extinction coefficient"):
        validate_refractive_index(1.5, np.nan)

    with pytest.raises(CertusValidationError, match="Negative extinction coefficient"):
        validate_refractive_index(1.5, -0.1)

    with pytest.raises(CertusValidationError, match="Extinction coefficient very high"):
        validate_refractive_index(1.5, 25.0)

def test_validate_spectral_data():
    wls = np.array([400.0, 500.0, 600.0])
    vals = np.array([0.5, 0.6, 0.7])
    validate_spectral_data(wls, vals)

    with pytest.raises(CertusValidationError, match="Empty spectral data"):
        validate_spectral_data([], [])

    with pytest.raises(CertusValidationError, match="Mismatched data lengths"):
        validate_spectral_data(wls, [0.5, 0.6])

    with pytest.raises(CertusValidationError, match="Insufficient data points"):
        validate_spectral_data([400.0], [0.5])

    with pytest.raises(CertusValidationError, match="NaN values in wavelengths"):
        validate_spectral_data([400.0, np.nan], [0.5, 0.6])

    with pytest.raises(CertusValidationError, match="NaN values in values"):
        validate_spectral_data([400.0, 500.0], [0.5, np.nan])

    with pytest.raises(CertusValidationError, match="Wavelengths not sorted"):
        validate_spectral_data([500.0, 400.0], [0.5, 0.6])

    with pytest.raises(CertusValidationError, match="values out of bounds"):
        validate_spectral_data(wls, [0.5, 1.2, 0.7], check_bounds=True)

def test_validate_parameter_range():
    validate_parameter_range(5.0, 1.0, 10.0, "test")

    with pytest.raises(CertusValidationError, match="Invalid value for test"):
        validate_parameter_range(np.nan, 1.0, 10.0, "test")

    with pytest.raises(CertusValidationError, match="test too low"):
        validate_parameter_range(0.0, 1.0, 10.0, "test")

    with pytest.raises(CertusValidationError, match="test too high"):
        validate_parameter_range(11.0, 1.0, 10.0, "test")

def test_get_error_message():
    title, details, sugg = get_error_message("file_not_found", path="test.txt")
    assert title == "File not found"
    assert "test.txt" in details
    assert "Check the file path" in sugg

    # Fallback to generic
    title, details, sugg = get_error_message("unknown_code", details="custom error")
    assert title == "Unexpected error"
    assert "custom error" in details

def test_format_validation_error():
    err = CertusValidationError("Title", "Details", "Suggestion")
    msg = format_validation_error(err)
    assert "Title" in msg
    assert "Details" in msg
    assert "Suggestion" in msg

@patch('PyQt6.QtWidgets.QMessageBox')
def test_ui_helpers(mock_qmessagebox):
    mock_instance = MagicMock()
    mock_qmessagebox.return_value = mock_instance
    mock_qmessagebox.Icon = MagicMock()
    
    # Just verify they don't crash and call exec()
    show_error(None, "file_not_found", path="test.txt")
    mock_instance.exec.assert_called()

    show_warning(None, "Warn", "Msg", "Sug")
    mock_instance.exec.assert_called()

    err = CertusValidationError("Err", "Det", "Sug")
    show_validation_error(None, err)
    mock_instance.exec.assert_called()

def test_safe_ui_action_decorator():
    # Test that safe_ui_action catches numerical exceptions
    @safe_ui_action
    def faulty_func():
        raise ValueError("Intentional crash")
        
    # The decorator suppresses the exception
    result = faulty_func()
    assert result is None
