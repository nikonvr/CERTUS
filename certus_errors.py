"""

CERTUS Errors - Error handling and parameter validation

=======================================================

Centralized module for:

- User-friendly error messages

- Parameter validation

- Custom exceptions


Usage:

    from certus_errors import (

        validate_wavelength_range,

        validate_thickness,

        show_error,

        CertusValidationError,

    )

"""

from typing import List, Union

import functools
import logging

import numpy as np


from certus_core import (
    ensure_numpy_arrays,
    CertusError,
    CertusOptimizationError,
    CertusPhysicsError,
    CertusConfigError,
)

# ---------------------------------------------------------------------------
# Broad-except tuple used across many UI modules.  Centralised here so that
# every call site can ``except NUMERICAL_FAULT_EXCEPTIONS`` instead of
# repeating 7 exception types.
# ---------------------------------------------------------------------------
NUMERICAL_FAULT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
    RuntimeError,
    AttributeError,
    KeyError,
    IndexError,
    FileNotFoundError,
)

_safe_logger = logging.getLogger("CERTUS")


def safe_ui_action(func):
    """Decorator that wraps a UI action with the standard broad-except guard.

    Catches ``NUMERICAL_FAULT_EXCEPTIONS`` and logs them via the CERTUS
    logger instead of crashing the application.  The decorated function
    returns ``None`` on failure.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NUMERICAL_FAULT_EXCEPTIONS:
            _safe_logger.exception("safe_ui_action caught exception in %s", func.__qualname__)

    return wrapper


__all__ = [
    # Exceptions
    "CertusError",
    "CertusValidationError",
    "CertusFileError",
    "CertusOptimizationError",
    "CertusPhysicsError",
    "CertusConfigError",
    "CertusDataError",
    "CertusComputationError",
    "CertusConvergenceError",
    "CertusMaterialError",
    # Validation functions
    "validate_wavelength_range",
    "validate_thickness",
    "validate_refractive_index",
    "validate_spectral_data",
    "validate_parameter_range",
    # Error messages
    "get_error_message",
    "format_validation_error",
    # UI helpers
    "show_error",
    "show_warning",
    "show_validation_error",
]


# =============================================================================

# PHYSICAL CONSTANTS (for validation)

# =============================================================================


# Wavelength limits (nm)

LAMBDA_MIN_PHYSICAL = 100.0  # UV extreme

LAMBDA_MAX_PHYSICAL = 20000.0  # Mid-IR


# Thickness limits (nm)

THICKNESS_MIN = 0.0

THICKNESS_MAX = 1000000.0  # 1mm


# Refractive index limits

N_MIN = 1.0  # Air/vacuum

N_MAX = 10.0  # Extreme materials

K_MIN = 0.0  # Non-absorbing

K_MAX = 20.0  # Highly absorbing metals


# =============================================================================

# EXCEPTIONS (extensions - base classes imported from certus_core)

# =============================================================================


class CertusValidationError(CertusError):
    """Exception for parameter validation errors."""

    pass


class CertusFileError(CertusError):
    """Exception for file I/O errors."""

    pass


class CertusDataError(CertusError):
    """Exception for data processing errors."""

    pass


class CertusComputationError(CertusError):
    """Exception for numerical computation errors."""

    pass


class CertusConvergenceError(CertusOptimizationError):
    """Exception for optimization convergence failures."""

    pass


class CertusMaterialError(CertusPhysicsError):
    """Exception for material database errors."""

    pass


# =============================================================================

# VALIDATION FUNCTIONS

# =============================================================================


def validate_wavelength_range(lambda_min: float, lambda_max: float, context: str = "spectral range") -> None:
    """

    Validate a wavelength range.

    Args:

        lambda_min: Minimum wavelength (nm)

        lambda_max: Maximum wavelength (nm)

        context: Context string for error messages

    Raises:

        CertusValidationError: If the range is invalid

    """

    if not np.isfinite(lambda_min) or not np.isfinite(lambda_max):
        raise CertusValidationError(
            f"Invalid values for {context}",
            f"lambda_min={lambda_min}, lambda_max={lambda_max}",
            "Ensure both values are finite numbers.",
        )

    if lambda_min >= lambda_max:
        raise CertusValidationError(
            "Invalid wavelength range",
            f"lambda_min ({lambda_min:.1f} nm) must be less than lambda_max ({lambda_max:.1f} nm)",
            "Swap the min and max values.",
        )

    if lambda_min < LAMBDA_MIN_PHYSICAL:
        raise CertusValidationError(
            "Minimum wavelength too low",
            f"lambda_min = {lambda_min:.1f} nm is below the physical limit ({LAMBDA_MIN_PHYSICAL} nm)",
            f"Use a value >= {LAMBDA_MIN_PHYSICAL} nm.",
        )

    if lambda_max > LAMBDA_MAX_PHYSICAL:
        raise CertusValidationError(
            "Maximum wavelength too high",
            f"lambda_max = {lambda_max:.1f} nm exceeds the physical limit ({LAMBDA_MAX_PHYSICAL} nm)",
            f"Use a value <= {LAMBDA_MAX_PHYSICAL} nm.",
        )

    if lambda_min < 0 or lambda_max < 0:
        raise CertusValidationError(
            "Negative wavelength",
            f"Wavelengths must be positive (lambda_min={lambda_min}, lambda_max={lambda_max})",
            "Use positive values.",
        )


def validate_thickness(
    thickness: float,
    allow_zero: bool = True,
    max_thickness: float = THICKNESS_MAX,
    context: str = "thickness",
) -> None:
    """

    Validate a layer thickness.

    Args:

        thickness: Thickness in nm

        allow_zero: If True, zero thickness is accepted

        max_thickness: Maximum allowed thickness

        context: Context string for error messages

    Raises:

        CertusValidationError: If the thickness is invalid

    """

    if not np.isfinite(thickness):
        raise CertusValidationError(
            "Invalid thickness value",
            f"{context} = {thickness}",
            "Enter a valid numeric value.",
        )

    if thickness < 0:
        raise CertusValidationError(
            "Negative thickness not allowed",
            f"{context} = {thickness:.2f} nm",
            "Thickness must be zero or positive.",
        )

    if not allow_zero and thickness == 0:
        raise CertusValidationError(
            "Zero thickness not allowed",
            f"{context} = 0 nm",
            "Enter a thickness > 0 nm.",
        )

    if thickness > max_thickness:
        raise CertusValidationError(
            "Thickness too large",
            f"{context} = {thickness:.1f} nm exceeds the limit ({max_thickness:.0f} nm = {max_thickness / 1000:.0f} µm)",
            f"Use a thickness <= {max_thickness:.0f} nm.",
        )


def validate_refractive_index(
    n: float,
    k: float | None = None,
    allow_below_one: bool = False,
    context: str = "refractive index",
) -> None:
    """

    Validate a refractive index.

    Args:

        n: Real part of the index

        k: Imaginary part (extinction coefficient), optional

        allow_below_one: If True, n < 1 is allowed (metamaterials)

        context: Context string for error messages

    Raises:

        CertusValidationError: If the index is invalid

    """

    if not np.isfinite(n):
        raise CertusValidationError(
            "Invalid refractive index",
            f"{context}: n = {n}",
            "Enter a valid numeric value.",
        )

    if n < 0:
        raise CertusValidationError(
            "Negative refractive index",
            f"{context}: n = {n:.3f}",
            "The refractive index must be positive.",
        )

    if not allow_below_one and n < N_MIN:
        raise CertusValidationError(
            "Refractive index too low",
            f"{context}: n = {n:.3f} < 1.0",
            "Refractive index is typically >= 1.0 (except metamaterials).",
        )

    if n > N_MAX:
        raise CertusValidationError(
            "Refractive index too high",
            f"{context}: n = {n:.3f} > {N_MAX}",
            f"Typical range: 1.0 (air) to {N_MAX} (extreme materials).",
        )

    if k is not None:
        if not np.isfinite(k):
            raise CertusValidationError(
                "Invalid extinction coefficient",
                f"{context}: k = {k}",
                "Enter a valid numeric value.",
            )

        if k < K_MIN:
            raise CertusValidationError(
                "Negative extinction coefficient",
                f"{context}: k = {k:.3f}",
                "The extinction coefficient must be >= 0.",
            )

        if k > K_MAX:
            raise CertusValidationError(
                "Extinction coefficient very high",
                f"{context}: k = {k:.3f}",
                f"Typical range: 0 (dielectric) to ~{K_MAX} (metals).",
            )


def validate_spectral_data(
    wavelengths: Union[np.ndarray, List[float]],
    values: Union[np.ndarray, List[float]],
    value_name: str = "values",
    min_points: int = 2,
    check_bounds: bool = True,
    value_min: float = 0.0,
    value_max: float = 1.0,
) -> None:
    """

    Validate spectral data (lambda, R/T/etc.).

    Args:

        wavelengths: Wavelength array

        values: Value array (R, T, etc.)

        value_name: Name used in error messages

        min_points: Minimum number of required points

        check_bounds: If True, verify values are within [value_min, value_max]

        value_min, value_max: Allowed value bounds

    Raises:

        CertusValidationError: If the data is invalid

    """

    wavelengths, values = ensure_numpy_arrays(wavelengths, values)

    if len(wavelengths) == 0 or len(values) == 0:
        raise CertusValidationError(
            "Empty spectral data",
            "The file contains no valid data.",
            "Check the file format and try again.",
        )

    if len(wavelengths) != len(values):
        raise CertusValidationError(
            "Mismatched data lengths",
            f"Wavelengths: {len(wavelengths)} points, {value_name}: {len(values)} points",
            "Ensure the file has the same number of values per column.",
        )

    if len(wavelengths) < min_points:
        raise CertusValidationError(
            "Insufficient data points",
            f"Only {len(wavelengths)} points; minimum required: {min_points}",
            f"Provide at least {min_points} data points.",
        )

    if np.any(np.isnan(wavelengths)):
        nan_count = int(np.sum(np.isnan(wavelengths)))

        raise CertusValidationError(
            "NaN values in wavelengths",
            f"{nan_count} NaN values detected",
            "Clean the data or replace missing values.",
        )

    if np.any(np.isnan(values)):
        nan_count = int(np.sum(np.isnan(values)))

        raise CertusValidationError(
            f"NaN values in {value_name}",
            f"{nan_count} NaN values detected",
            "Clean the data or replace missing values.",
        )

    if not np.all(np.diff(wavelengths) > 0):
        raise CertusValidationError(
            "Wavelengths not sorted",
            "Data must be sorted by ascending wavelength",
            "Sort the data before import or enable automatic sorting.",
        )

    if check_bounds:
        out_of_bounds = (values < value_min) | (values > value_max)

        if np.any(out_of_bounds):
            n_out = int(np.sum(out_of_bounds))

            val_range = f"[{np.min(values):.3f}, {np.max(values):.3f}]"

            raise CertusValidationError(
                f"{value_name} values out of bounds",
                f"{n_out} values outside [{value_min}, {value_max}]. Actual range: {val_range}",
                f"{value_name} values must be between {value_min} and {value_max}. "
                "If data is in percent (0-100%), enable automatic normalization.",
            )


def validate_parameter_range(value: float, min_val: float, max_val: float, param_name: str, unit: str = "") -> None:
    """

    Validate that a parameter is within a given range.

    Args:

        value: Value to validate

        min_val: Minimum allowed value

        max_val: Maximum allowed value

        param_name: Parameter name for error messages

        unit: Unit string (optional)

    Raises:

        CertusValidationError: If the value is out of range

    """

    if not np.isfinite(value):
        raise CertusValidationError(
            f"Invalid value for {param_name}",
            f"{param_name} = {value}",
            "Enter a valid numeric value.",
        )

    unit_str = f" {unit}" if unit else ""

    if value < min_val:
        raise CertusValidationError(
            f"{param_name} too low",
            f"{param_name} = {value:.4g}{unit_str} < minimum ({min_val:.4g}{unit_str})",
            f"Use a value >= {min_val:.4g}{unit_str}.",
        )

    if value > max_val:
        raise CertusValidationError(
            f"{param_name} too high",
            f"{param_name} = {value:.4g}{unit_str} > maximum ({max_val:.4g}{unit_str})",
            f"Use a value <= {max_val:.4g}{unit_str}.",
        )


# =============================================================================

# ERROR MESSAGE TEMPLATES

# =============================================================================


ERROR_MESSAGES = {
    # File errors
    "file_not_found": (
        "File not found",
        "The file '{path}' does not exist.",
        "Check the file path or select a different file.",
    ),
    "file_permission": (
        "Permission denied",
        "Cannot access file '{path}'.",
        "Check file permissions or close any application that may be using it.",
    ),
    "file_format": (
        "Unrecognized file format",
        "The file '{path}' is not in a supported format.",
        "Supported formats: CSV, TXT, XLSX, XLS.",
    ),
    "file_empty": (
        "Empty file",
        "The file '{path}' contains no data.",
        "Ensure the file contains valid data.",
    ),
    "file_corrupt": (
        "Corrupted file",
        "Cannot read file '{path}'.",
        "The file may be corrupted. Try a different version or recreate the file.",
    ),
    # Optimization errors
    "optim_no_data": (
        "Missing data",
        "No data has been loaded for optimization.",
        "Load a spectral data file before starting the optimization.",
    ),
    "optim_no_convergence": (
        "Optimization did not converge",
        "The algorithm did not converge after {iterations} iterations.",
        "Try increasing the number of iterations or adjusting the parameter bounds.",
    ),
    "optim_invalid_bounds": (
        "Invalid parameter bounds",
        "The min/max bounds for '{param}' are invalid.",
        "Ensure min < max and that the values are physically realistic.",
    ),
    # Generic errors
    "generic_error": (
        "Unexpected error",
        "{details}",
        "If the problem persists, check the logs or contact support.",
    ),
}


def get_error_message(error_code: str, **kwargs) -> tuple[str, str, str]:
    """

    Retrieve a formatted error message.

    Args:

        error_code: Error code key

        **kwargs: Format variables

    Returns:

        Tuple (title, details, suggestion)

    """

    if error_code not in ERROR_MESSAGES:
        error_code = "generic_error"

    title, details, suggestion = ERROR_MESSAGES[error_code]

    try:
        details = details.format(**kwargs)

    except KeyError:
        pass

    return title, details, suggestion


def format_validation_error(error: CertusValidationError) -> str:
    """

    Format a validation error for display.

    Args:

        error: CertusValidationError exception

    Returns:

        Formatted message for user display

    """

    return error.full_message


# =============================================================================

# UI HELPERS (PyQt6)

# =============================================================================


def show_error(parent, error_code: str, **kwargs) -> None:
    """

    Show an error dialog.

    Args:

        parent: Qt parent widget

        error_code: Error code key

        **kwargs: Format variables

    """

    from PyQt6.QtWidgets import QMessageBox

    title, details, suggestion = get_error_message(error_code, **kwargs)

    msg = QMessageBox(parent)

    msg.setIcon(QMessageBox.Icon.Critical)

    msg.setWindowTitle(title)

    msg.setText(details)

    if suggestion:
        msg.setInformativeText(f"💡 {suggestion}")

    msg.exec()


def show_warning(parent, title: str, message: str, suggestion: str = "") -> None:
    """

    Show a warning dialog.

    Args:

        parent: Qt parent widget

        title: Warning title

        message: Detailed message

        suggestion: Optional suggestion

    """

    from PyQt6.QtWidgets import QMessageBox

    msg = QMessageBox(parent)

    msg.setIcon(QMessageBox.Icon.Warning)

    msg.setWindowTitle(title)

    msg.setText(message)

    if suggestion:
        msg.setInformativeText(f"💡 {suggestion}")

    msg.exec()


def show_validation_error(parent, error: CertusValidationError) -> None:
    """

    Show a validation error dialog.

    Args:

        parent: Qt parent widget

        error: CertusValidationError exception

    """

    from PyQt6.QtWidgets import QMessageBox

    msg = QMessageBox(parent)

    msg.setIcon(QMessageBox.Icon.Warning)

    msg.setWindowTitle("Validation Error")

    msg.setText(error.message)

    if error.details:
        msg.setDetailedText(error.details)

    if error.suggestion:
        msg.setInformativeText(f"💡 {error.suggestion}")

    msg.exec()
