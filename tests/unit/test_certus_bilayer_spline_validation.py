"""Regression tests for bilayer spline validation."""

from __future__ import annotations

import numpy as np
import pytest

from CERTUS_METAL_BILAYER import _validate_bilayer_spline_state


def test_validate_bilayer_spline_state_accepts_coherent_state() -> None:
    min_l, max_l = 350.0, 880.0
    expected_knot_count = 6
    n_knots = np.linspace(1.0, 2.0, expected_knot_count)
    k_knots = np.linspace(0.1, 0.6, expected_knot_count)
    lambda_internes = np.linspace(min_l, max_l, expected_knot_count)[1:-1]

    knot_l, internal = _validate_bilayer_spline_state(
        n_knots=n_knots,
        k_knots=k_knots,
        lambda_internes=lambda_internes,
        min_l=min_l,
        max_l=max_l,
        expected_knot_count=expected_knot_count,
    )

    assert knot_l.size == expected_knot_count
    assert internal.size == expected_knot_count - 2
    assert np.all(np.diff(knot_l) > 0)


def test_validate_bilayer_spline_state_rejects_incoherent_coefficients() -> None:
    min_l, max_l = 350.0, 880.0
    expected_knot_count = 6
    n_knots = np.linspace(1.0, 2.0, expected_knot_count - 1)
    k_knots = np.linspace(0.1, 0.6, expected_knot_count)
    lambda_internes = np.linspace(min_l, max_l, expected_knot_count)[1:-1]

    with pytest.raises(ValueError, match="Invalid spline coefficient state"):
        _validate_bilayer_spline_state(
            n_knots=n_knots,
            k_knots=k_knots,
            lambda_internes=lambda_internes,
            min_l=min_l,
            max_l=max_l,
            expected_knot_count=expected_knot_count,
        )
