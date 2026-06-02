"""B.23 — Coverage-driven tests for `compute_oblique_gradient_contrib_analytic`.

Targets the 184 missed lines (out of 432 LOC, 57.4% baseline coverage) of the
oblique-incidence DESIGN gradient kernel. Existing
`tests/test_gradient_vs_fd.py:test_design_oblique_gradient` covers the
`is_s_pol=True, target_is_reflectance=False, angle=45deg` happy path; this
file targets the under-exercised branches:

1. **TIR (Total Internal Reflection):** `sin_theta_sub > 1.0` — y_val forced
   to 1.0 (R-target) or 0.0 (T-target).
2. **Polarization swap:** `is_s_pol=False` (p-pol) — different Fresnel coeff.
3. **Target swap:** `target_is_reflectance=True` — gradient sign flips, error
   metric on R(λ) instead of T(λ).
4. **Per-wavelength weight masking:** `tgt_weights[i] <= 1e-12` skips that λ
   (uses the `if w <= 1e-12: continue` early-out).
5. **Single-wavelength degenerate input.**
6. **`var_idx=None` default path** (wrapper rebuilds `arange(n_layers)`).

Each test verifies the contract:
- Output triple `(err_sum, grad_raw, weight_sum)` has correct shapes/types.
- All values are finite (no NaN/Inf leaks).
- `err_sum >= 0`, `weight_sum >= 0`.
- TIR branch yields finite, bounded outputs.
- Determinism: identical inputs → identical outputs.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core._certus_physics_impl import compute_oblique_gradient_contrib_analytic


def _build_simple_oblique_stack(n_layers: int = 3, n_wls: int = 4):
    """Minimal dispersive non-absorbing stack suitable for oblique analytic tests."""
    ep = np.linspace(80.0, 120.0, n_layers, dtype=np.float64)
    wls = np.linspace(450.0, 700.0, n_wls, dtype=np.float64)
    n_layers_T = np.zeros((n_wls, n_layers), dtype=np.complex128)
    for i, wl in enumerate(wls):
        for j in range(n_layers):
            base = 2.3 if (j % 2 == 0) else 1.45
            disp = 0.02 * (550.0 / wl - 1.0)
            n_layers_T[i, j] = complex(base + disp, 0.0)
    n_sub = np.array([complex(1.52)] * n_wls, dtype=np.complex128)
    tgt_vals = np.full(n_wls, 0.5, dtype=np.float64)
    tgt_weights = np.ones(n_wls, dtype=np.float64)
    var_idx = np.arange(n_layers, dtype=np.int64)
    return ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx


def _check_triple_finite(err_sum, grad_raw, weight_sum, n_vars):
    assert np.isfinite(err_sum), f"err_sum must be finite, got {err_sum}"
    assert np.isfinite(weight_sum), f"weight_sum must be finite, got {weight_sum}"
    assert err_sum >= 0.0
    assert weight_sum >= 0.0
    assert grad_raw.shape == (n_vars,)
    assert np.all(np.isfinite(grad_raw))


def test_tir_branch_reflectance_target():
    """At angle > critical, sin_theta_sub > 1 -> y forced to 1.0 for R-target."""
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx = _build_simple_oblique_stack()
    # Substrate index 1.52, n0 = 1.0 -> critical angle ~41.1deg from substrate side,
    # but the kernel uses (n0 / n_sub) * sin(theta0). For the kernel's TIR branch
    # to fire, we need sin_theta_sub > 1, i.e. n0 * sin(theta0) > n_sub.
    # That requires n0 > n_sub OR theta0 -> 90deg with low n_sub.
    # Force TIR by lowering n_sub below n0:
    n_sub_low = np.array([complex(0.5)] * len(wls), dtype=np.complex128)
    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub_low, wls, tgt_vals, tgt_weights,
        85.0, True, True, var_idx,
    )
    _check_triple_finite(err_sum, grad_raw, weight_sum, len(var_idx))
    # In TIR + R-target, every λ sees diff = 1.0 - tgt[i] = 0.5 -> err = w * 0.25.
    expected_err = np.sum(tgt_weights * (1.0 - tgt_vals) ** 2)
    assert err_sum == pytest.approx(expected_err, rel=1e-9)


def test_tir_branch_transmittance_target():
    """At angle > critical, sin_theta_sub > 1 -> y forced to 0.0 for T-target."""
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx = _build_simple_oblique_stack()
    n_sub_low = np.array([complex(0.5)] * len(wls), dtype=np.complex128)
    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub_low, wls, tgt_vals, tgt_weights,
        85.0, True, False, var_idx,
    )
    _check_triple_finite(err_sum, grad_raw, weight_sum, len(var_idx))
    # In TIR + T-target, every λ sees diff = 0.0 - tgt[i] = -0.5 -> err = w * 0.25.
    expected_err = np.sum(tgt_weights * (0.0 - tgt_vals) ** 2)
    assert err_sum == pytest.approx(expected_err, rel=1e-9)


def test_p_polarization_path():
    """is_s_pol=False must take the p-polarization Fresnel branch and yield
    finite, non-trivially different output from s-polarization.
    """
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx = _build_simple_oblique_stack()
    err_s, grad_s, w_s = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, True, False, var_idx,
    )
    err_p, grad_p, w_p = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, False, False, var_idx,
    )
    _check_triple_finite(err_s, grad_s, w_s, len(var_idx))
    _check_triple_finite(err_p, grad_p, w_p, len(var_idx))
    # Weight sums must be identical (same tgt_weights).
    assert w_s == pytest.approx(w_p)
    # s and p paths should not be bit-identical at 45deg (Fresnel breaks symmetry).
    assert not np.allclose(grad_s, grad_p, atol=1e-12)


def test_reflectance_target_changes_output_vs_transmittance():
    """target_is_reflectance=True vs False must produce different outputs.

    Note: with tgt=0.5 and a non-absorbing stack (R+T=1) the err_sum is the
    same by symmetry ((T-0.5)^2 == (R-0.5)^2). Use an asymmetric target so
    the symmetry is broken and outputs are actually distinguishable.
    """
    ep, n_layers_T, n_sub, wls, _, tgt_weights, var_idx = _build_simple_oblique_stack()
    asym_tgt = np.full(len(wls), 0.3, dtype=np.float64)  # break R<->T symmetry
    err_t, grad_t, w_t = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, asym_tgt, tgt_weights, 30.0, True, False, var_idx,
    )
    err_r, grad_r, w_r = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, asym_tgt, tgt_weights, 30.0, True, True, var_idx,
    )
    _check_triple_finite(err_t, grad_t, w_t, len(var_idx))
    _check_triple_finite(err_r, grad_r, w_r, len(var_idx))
    assert w_t == pytest.approx(w_r)
    # Asymmetric target -> err_sum and gradient must both differ between R and T paths.
    assert not np.isclose(err_t, err_r, atol=1e-9)
    assert not np.allclose(grad_t, grad_r, atol=1e-9)


def test_zero_weight_wavelength_is_skipped():
    """Wavelengths with weight <= 1e-12 must be excluded from sums."""
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx = _build_simple_oblique_stack()
    # Mask out the middle two wavelengths.
    masked_w = tgt_weights.copy()
    masked_w[1] = 0.0
    masked_w[2] = 0.0
    err_full, _, w_full = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 30.0, True, False, var_idx,
    )
    err_mask, _, w_mask = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, masked_w, 30.0, True, False, var_idx,
    )
    # weight_sum drops by exactly the masked weights.
    assert w_mask == pytest.approx(w_full - 2.0, abs=1e-12)
    # err_sum strictly less than (or equal to) the unmasked err.
    assert err_mask <= err_full + 1e-12


def test_all_zero_weights_yield_zero_sums():
    """tgt_weights all zero -> err_sum = 0, weight_sum = 0, grad_raw all zero."""
    ep, n_layers_T, n_sub, wls, tgt_vals, _, var_idx = _build_simple_oblique_stack()
    zero_w = np.zeros(len(wls), dtype=np.float64)
    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, zero_w, 30.0, True, False, var_idx,
    )
    assert err_sum == 0.0
    assert weight_sum == 0.0
    np.testing.assert_array_equal(grad_raw, np.zeros_like(grad_raw))


def test_single_wavelength_oblique_kernel():
    """The wavelength loop must handle n_wls == 1 correctly."""
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, var_idx = _build_simple_oblique_stack(
        n_layers=3, n_wls=1
    )
    err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, True, False, var_idx,
    )
    _check_triple_finite(err_sum, grad_raw, weight_sum, len(var_idx))
    assert weight_sum == pytest.approx(1.0)


def test_var_idx_none_default_path_uses_all_layers():
    """Wrapper must default var_idx to arange(n_layers) when None is passed."""
    ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, _ = _build_simple_oblique_stack()
    err_a, grad_a, w_a = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, True, False, None,
    )
    err_b, grad_b, w_b = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights,
        45.0, True, False, np.arange(len(ep), dtype=np.int64),
    )
    assert err_a == pytest.approx(err_b, rel=1e-12)
    assert w_a == pytest.approx(w_b, rel=1e-12)
    np.testing.assert_allclose(grad_a, grad_b, atol=1e-12)


def test_oblique_kernel_is_deterministic():
    """Repeated calls with identical inputs yield identical outputs."""
    args = _build_simple_oblique_stack()
    out_a = compute_oblique_gradient_contrib_analytic(
        *args[:6], 30.0, True, False, args[6],
    )
    out_b = compute_oblique_gradient_contrib_analytic(
        *args[:6], 30.0, True, False, args[6],
    )
    assert out_a[0] == out_b[0]
    np.testing.assert_array_equal(out_a[1], out_b[1])
    assert out_a[2] == out_b[2]
