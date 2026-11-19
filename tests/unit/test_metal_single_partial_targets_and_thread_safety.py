"""Regression tests for C5 (independent T and Rback targets in METAL SINGLE MSE)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.metal.certus_metal_single_physics import (
    _single_RTRback_mse,
    calculate_RTRback_incoherent_vectorized,
    get_nk_from_spline,
)


def _make_single_metal_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object], float, int]:
    l_array = np.linspace(450.0, 750.0, 11, dtype=np.float64)
    n_sub = np.full_like(l_array, 1.52 + 0j, dtype=np.complex128)
    num_knots = 3
    precomputed = {
        "min_lambda": float(l_array[0]),
        "max_lambda": float(l_array[-1]),
        "nSub_complex_array": n_sub,
    }
    e_m = 25.0
    # x = [n_knots (3), k_knots (3), lambda_internes (1)] with eM_fixed=e_m
    x = np.array([0.25, 0.20, 0.18, 2.5, 3.0, 3.5, 600.0], dtype=np.float64)
    return l_array, n_sub, x, precomputed, e_m, num_knots


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["R+T", "R+Rback"])
def test_single_rtrback_mse_includes_partial_targets_independently(mode: str) -> None:
    l_array, n_sub, x, precomputed, e_m, num_knots = _make_single_metal_fixture()
    r_tgt = np.full_like(l_array, 0.5)
    t_tgt = np.full_like(l_array, 0.2) if mode == "R+T" else None
    rb_tgt = np.full_like(l_array, 0.6) if mode == "R+Rback" else None

    baseline_r_only = _single_RTRback_mse(
        x, l_array, r_tgt, num_knots, 10.0, n_sub, precomputed, eM_fixed=e_m, t_tgt=None, rb_tgt=None
    )
    partial = _single_RTRback_mse(
        x, l_array, r_tgt, num_knots, 10.0, n_sub, precomputed, eM_fixed=e_m, t_tgt=t_tgt, rb_tgt=rb_tgt
    )

    if mode == "R+T":
        t_shifted = t_tgt + 0.35
        shifted = _single_RTRback_mse(
            x, l_array, r_tgt, num_knots, 10.0, n_sub, precomputed, eM_fixed=e_m, t_tgt=t_shifted, rb_tgt=None
        )
    else:
        rb_shifted = rb_tgt + 0.35
        shifted = _single_RTRback_mse(
            x, l_array, r_tgt, num_knots, 10.0, n_sub, precomputed, eM_fixed=e_m, t_tgt=None, rb_tgt=rb_shifted
        )

    assert partial != pytest.approx(baseline_r_only, rel=1e-6, abs=1e-6)
    assert shifted != pytest.approx(partial, rel=1e-6, abs=1e-6)


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["R+T", "R+Rback"])
def test_single_rtrback_mse_matches_analytical_two_curve_average(mode: str) -> None:
    l_array, n_sub, x, precomputed, e_m, num_knots = _make_single_metal_fixture()
    knot_l = np.array([float(l_array[0]), float(x[-1]), float(l_array[-1])], dtype=np.float64)
    n_calc, k_calc = get_nk_from_spline(x[: 2 * num_knots], knot_l, l_array, use_cache=False)
    wiggle = 1e-2 * float(np.sum(np.diff(n_calc, n=2) ** 2) + np.sum(np.diff(k_calc, n=2) ** 2))
    r_calc, t_calc, rb_calc = calculate_RTRback_incoherent_vectorized(
        np.array([e_m], dtype=np.float64), (n_calc - 1j * k_calc).reshape(-1, 1), n_sub, l_array
    )

    r_tgt = np.full_like(l_array, 0.5)
    other_tgt = np.full_like(l_array, 0.25)
    t_tgt = other_tgt if mode == "R+T" else None
    rb_tgt = other_tgt if mode == "R+Rback" else None

    val = _single_RTRback_mse(
        x, l_array, r_tgt, num_knots, 10.0, n_sub, precomputed, eM_fixed=e_m, t_tgt=t_tgt, rb_tgt=rb_tgt
    )
    other_calc = t_calc if mode == "R+T" else rb_calc
    expected = 0.5 * (float(np.mean((r_calc - r_tgt) ** 2)) + float(np.mean((other_calc - other_tgt) ** 2))) + wiggle
    assert val == pytest.approx(expected, rel=1e-12, abs=1e-12)
