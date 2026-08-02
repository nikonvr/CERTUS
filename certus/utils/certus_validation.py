from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import os

class PathValidator:
    """Validator for file paths to prevent Path Traversal and check extensions."""

    @staticmethod
    def validate_path(
        path_str: str | Path,
        base_dir: str | Path | None = None,
        allowed_extensions: list[str] | None = None,
    ) -> Path:
        """Resolves and validates a file path.

        Raises ValueError if path traversal is detected or extension is not allowed.
        """
        if not path_str:
            raise ValueError("Path string cannot be empty.")

        path = Path(path_str)
        try:
            resolved_path = path.resolve()
        except Exception as e:
            raise ValueError(f"Invalid path representation: {e}")

        # Check allowed extensions
        if allowed_extensions is not None:
            suffix = resolved_path.suffix.lower()
            # Normalize extension formats (e.g., 'xlsx' -> '.xlsx')
            normalized_extensions = [
                ext if ext.startswith(".") else f".{ext}"
                for ext in allowed_extensions
            ]
            if suffix not in [ext.lower() for ext in normalized_extensions]:
                raise ValueError(
                    f"File extension '{suffix}' is not allowed. Allowed: {allowed_extensions}"
                )

        # Check for Path Traversal
        if base_dir is not None:
            try:
                resolved_base = Path(base_dir).resolve()
            except Exception as e:
                raise ValueError(f"Invalid base directory representation: {e}")

            # Check if resolved path is sub-path of base_dir
            # Using commonpath is extremely robust to determine directory containment
            try:
                common = Path(os.path.commonpath([str(resolved_base), str(resolved_path)]))
            except Exception as e:
                raise ValueError(f"Failed to check path traversal: {e}")

            if common != resolved_base:
                raise ValueError(
                    f"Access denied: path '{resolved_path}' attempts to traverse outside '{resolved_base}'"
                )

        return resolved_path


class NumericValidator:
    """Validator for numerical inputs to prevent out-of-bounds errors or NaN crashes."""

    @staticmethod
    def validate_float(
        value: Any,
        min_val: float | None = None,
        max_val: float | None = None,
        allow_nan: bool = False,
        name: str = "value",
    ) -> float:
        """Validates that a value is or can be cast to float, checking bounds and NaN/Inf."""
        try:
            f_val = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a valid number.")

        import math
        if math.isnan(f_val):
            if not allow_nan:
                raise ValueError(f"{name} cannot be NaN.")
            return f_val

        if math.isinf(f_val):
            raise ValueError(f"{name} cannot be infinite.")

        if min_val is not None and f_val < min_val:
            raise ValueError(f"{name} ({f_val}) must be at least {min_val}.")

        if max_val is not None and f_val > max_val:
            raise ValueError(f"{name} ({f_val}) must be at most {max_val}.")

        return f_val

    @staticmethod
    def validate_int(
        value: Any,
        min_val: int | None = None,
        max_val: int | None = None,
        name: str = "value",
    ) -> int:
        """Validates that a value is or can be cast to int, checking bounds."""
        try:
            # We convert to float first in case value is '3.0'
            f_val = float(value)
            if not f_val.is_integer():
                raise ValueError()
            i_val = int(f_val)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a valid integer.")

        if min_val is not None and i_val < min_val:
            raise ValueError(f"{name} ({i_val}) must be at least {min_val}.")

        if max_val is not None and i_val > max_val:
            raise ValueError(f"{name} ({i_val}) must be at most {max_val}.")

        return i_val


class StringValidator:
    """Validator for string inputs to prevent SQL-like injection or buffer overflow crashes."""

    @staticmethod
    def validate_string(
        value: Any,
        max_len: int | None = 256,
        allowed_pattern: str | None = None,
        name: str = "value",
    ) -> str:
        """Validates and sanitizes a string input."""
        if value is None:
            raise ValueError(f"{name} cannot be None.")

        s_val = str(value)

        if max_len is not None and len(s_val) > max_len:
            raise ValueError(
                f"{name} is too long ({len(s_val)} chars). Maximum allowed is {max_len}."
            )

        if allowed_pattern is not None:
            if not re.match(allowed_pattern, s_val):
                raise ValueError(
                    f"{name} contains invalid characters or does not match pattern."
                )

        return s_val
