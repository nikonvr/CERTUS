import pytest
from pathlib import Path
import tempfile
import os
from certus.utils.certus_validation import PathValidator, NumericValidator, StringValidator

def test_path_validator_extensions():
    # Valid extension
    p = Path("clues.xlsx")
    assert PathValidator.validate_path(p, allowed_extensions=[".xlsx"]) == p.resolve()
    assert PathValidator.validate_path(p, allowed_extensions=["xlsx"]) == p.resolve()

    # Invalid extension
    with pytest.raises(ValueError, match="extension"):
        PathValidator.validate_path(p, allowed_extensions=[".json"])


def test_path_validator_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir).resolve()
        
        # Create a file inside base_dir
        safe_file = base / "safe.xlsx"
        safe_file.touch()

        # Valid safe file
        assert PathValidator.validate_path(safe_file, base_dir=base) == safe_file

        # Path traversal outside base_dir
        unsafe_file = base / ".." / "unsafe.xlsx"
        with pytest.raises(ValueError, match="traverse outside"):
            PathValidator.validate_path(unsafe_file, base_dir=base)


def test_numeric_validator_float():
    assert NumericValidator.validate_float(3.14) == 3.14
    assert NumericValidator.validate_float("3.14") == 3.14
    assert NumericValidator.validate_float(10, min_val=0, max_val=20) == 10.0

    with pytest.raises(ValueError, match="must be a valid number"):
        NumericValidator.validate_float("not-a-number")

    with pytest.raises(ValueError, match="must be at least"):
        NumericValidator.validate_float(5.0, min_val=10.0)

    with pytest.raises(ValueError, match="must be at most"):
        NumericValidator.validate_float(15.0, max_val=10.0)

    with pytest.raises(ValueError, match="cannot be infinite"):
        NumericValidator.validate_float(float("inf"))

    with pytest.raises(ValueError, match="cannot be NaN"):
        NumericValidator.validate_float(float("nan"), allow_nan=False)

    assert NumericValidator.validate_float(float("nan"), allow_nan=True) is not None


def test_numeric_validator_int():
    assert NumericValidator.validate_int(42) == 42
    assert NumericValidator.validate_int("42") == 42
    assert NumericValidator.validate_int(5.0) == 5

    with pytest.raises(ValueError, match="must be a valid integer"):
        NumericValidator.validate_int(3.14)

    with pytest.raises(ValueError, match="must be a valid integer"):
        NumericValidator.validate_int("not-an-int")

    with pytest.raises(ValueError, match="must be at least"):
        NumericValidator.validate_int(2, min_val=5)


def test_string_validator():
    assert StringValidator.validate_string("hello") == "hello"
    assert StringValidator.validate_string("a" * 10, max_len=10) == "a" * 10

    with pytest.raises(ValueError, match="too long"):
        StringValidator.validate_string("a" * 11, max_len=10)

    # Pattern validation
    pattern = r"^[a-zA-Z0-9_]+$"
    assert StringValidator.validate_string("valid_123", allowed_pattern=pattern) == "valid_123"

    with pytest.raises(ValueError, match="invalid characters"):
        StringValidator.validate_string("invalid-char!", allowed_pattern=pattern)
