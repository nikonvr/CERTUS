"""Contract tests for METAL bilayer spline validation."""

from __future__ import annotations

from importlib import util
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = util.spec_from_file_location("certus_metal_bilayer", _ROOT / "certus_metal_bilayer.py")
assert _SPEC and _SPEC.loader is not None
_mod = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)
_validate_bilayer_spline_state = _mod._validate_bilayer_spline_state


def test_validate_bilayer_spline_state_accepts_consistent_state() -> None:
    n_knots = np.array([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    k_knots = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    lambda_internes = np.array([410.0, 500.0, 610.0, 720.0])

    knot_l, internals = _validate_bilayer_spline_state(
        n_knots,
        k_knots,
        lambda_internes,
        350.0,
        880.0,
        expected_knot_count=6,
    )

    assert knot_l.size == 6
    assert internals.size == 4
    assert np.all(np.diff(knot_l) > 0)


def test_validate_bilayer_spline_state_rejects_mismatched_coeff_count() -> None:
    n_knots = np.array([1.0, 1.1, 1.2, 1.3, 1.4])
    k_knots = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    lambda_internes = np.array([410.0, 500.0, 610.0, 720.0])

    with pytest.raises(ValueError, match="Invalid spline coefficient state"):
        _validate_bilayer_spline_state(
            n_knots,
            k_knots,
            lambda_internes,
            350.0,
            880.0,
            expected_knot_count=6,
        )


def test_validate_bilayer_spline_state_rejects_invalid_interval() -> None:
    n_knots = np.array([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    k_knots = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    lambda_internes = np.array([410.0, 500.0, 610.0, 720.0])

    with pytest.raises(ValueError, match="Invalid wavelength interval"):
        _validate_bilayer_spline_state(
            n_knots,
            k_knots,
            lambda_internes,
            500.0,
            500.0,
            expected_knot_count=6,
        )
