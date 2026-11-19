"""TMM and normal-incidence cost kernels preserve float64 outputs when wavelengths have integer dtype (m1)."""

from __future__ import annotations

import numpy as np

from certus.physics.certus_tmm_matrix import calculate_RT_no_backside, calculate_RT_with_backside_fused
from certus.physics.gradient_utils import cost_numba_fast


def _sample_stack(n_wls: int):
    d = np.array([100.0, 80.0], dtype=np.float64)
    n_layers = np.tile(np.array([[2.3 + 0.0j, 1.46 + 0.0j]], dtype=np.complex128), (n_wls, 1))
    n_sub = np.full(n_wls, 1.52 + 0.0j, dtype=np.complex128)
    return d, n_layers, n_sub


def test_calculate_rt_with_backside_fused_preserves_float64_on_int_wavelengths() -> None:
    wls_i64 = np.array([450, 500, 550, 600, 650], dtype=np.int64)
    wls_f64 = wls_i64.astype(np.float64)
    d, n_layers, n_sub = _sample_stack(len(wls_i64))

    r_i, t_i = calculate_RT_with_backside_fused(d, n_layers, n_sub, wls_i64)
    r_f, t_f = calculate_RT_with_backside_fused(d, n_layers, n_sub, wls_f64)

    assert r_i.dtype == np.float64
    assert t_i.dtype == np.float64
    np.testing.assert_allclose(r_i, r_f, atol=1e-14, rtol=1e-14)
    np.testing.assert_allclose(t_i, t_f, atol=1e-14, rtol=1e-14)


def test_calculate_rt_no_backside_preserves_float64_on_int_wavelengths() -> None:
    wls_i64 = np.array([450, 500, 550, 600, 650], dtype=np.int64)
    wls_f64 = wls_i64.astype(np.float64)
    d, n_layers, n_sub = _sample_stack(len(wls_i64))

    r_i, t_i = calculate_RT_no_backside(d, n_layers, n_sub, wls_i64)
    r_f, t_f = calculate_RT_no_backside(d, n_layers, n_sub, wls_f64)

    assert r_i.dtype == np.float64
    assert t_i.dtype == np.float64
    np.testing.assert_allclose(r_i, r_f, atol=1e-14, rtol=1e-14)
    np.testing.assert_allclose(t_i, t_f, atol=1e-14, rtol=1e-14)


def test_cost_numba_fast_preserves_accuracy_on_int_wavelengths() -> None:
    wls_i64 = np.array([450, 500, 550, 600, 650], dtype=np.int64)
    wls_f64 = wls_i64.astype(np.float64)
    d, n_layers, n_sub = _sample_stack(len(wls_i64))
    tgt = np.full(len(wls_i64), 0.5, dtype=np.float64)
    weights = np.ones(len(wls_i64), dtype=np.float64)
    d_back = np.array([90.0], dtype=np.float64)
    n_back = np.full((len(wls_i64), 1), 1.46 + 0.0j, dtype=np.complex128)

    for has_back in (False, True):
        c_i = cost_numba_fast(d, n_layers, n_sub, wls_i64, tgt, weights, 5.0, has_back, n_back, d_back)
        c_f = cost_numba_fast(d, n_layers, n_sub, wls_f64, tgt, weights, 5.0, has_back, n_back, d_back)
        np.testing.assert_allclose(c_i, c_f, atol=1e-14, rtol=1e-14)
