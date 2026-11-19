"""Analytic Tauc-Lorentz epsilon1 gradient is continuous at E == Eg and finite when A == 0 (M1 grad)."""

from __future__ import annotations

import numpy as np

from certus.physics.certus_optical_models import epsilon1_TL_analytic
from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel


def test_epsilon1_gradient_matches_finite_differences_at_bandgap() -> None:
    eg, a, e0, c, eps_inf = 3.0, 80.0, 4.2, 1.5, 2.0
    e_arr = np.array([eg - 1e-4, eg, eg + 1e-4], dtype=np.float64)

    res = _compute_epsilon1_gradient_kernel(e_arr, eg, a, e0, c, eps_inf)
    eps1_ref = epsilon1_TL_analytic(e_arr, eg, a, e0, c, eps_inf)

    assert np.all(np.isfinite(res))
    np.testing.assert_allclose(res[0], eps1_ref, atol=1e-12, rtol=1e-12)
    # Smooth across E == Eg
    assert abs(res[0, 1] - 0.5 * (res[0, 0] + res[0, 2])) < 1e-6

    e_single = np.array([eg], dtype=np.float64)
    params = [eg, a, e0, c, eps_inf]
    grad_indices = [1, 2, 3, 4, 6]
    for p_idx, g_idx in enumerate(grad_indices):
        h = 1e-6
        up = list(params)
        dn = list(params)
        up[p_idx] += h
        dn[p_idx] -= h
        fd = (epsilon1_TL_analytic(e_single, *up)[0] - epsilon1_TL_analytic(e_single, *dn)[0]) / (2.0 * h)
        np.testing.assert_allclose(res[g_idx, 1], fd, rtol=1e-5, atol=1e-5)


def test_epsilon1_gradient_is_finite_and_accurate_at_zero_amplitude() -> None:
    eg, a, e0, c, eps_inf = 3.0, 0.0, 4.2, 1.5, 2.0
    e_arr = np.array([2.5, 3.0, 3.5], dtype=np.float64)

    res = _compute_epsilon1_gradient_kernel(e_arr, eg, a, e0, c, eps_inf)

    assert np.all(np.isfinite(res))
    np.testing.assert_allclose(res[0], np.full(3, eps_inf), atol=1e-14)
    h = 1e-6
    fd_da = (epsilon1_TL_analytic(e_arr, eg, h, e0, c, eps_inf) - epsilon1_TL_analytic(e_arr, eg, 0.0, e0, c, eps_inf)) / h
    np.testing.assert_allclose(res[2], fd_da, rtol=1e-6, atol=1e-6)
