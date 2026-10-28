"""Second-order robust RMSE of DESIGN (Tikhonravov et al., SPIE 4829, 2003, Eq. 5 with alpha = sigma)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_tolerance import error_alpha, second_order_robust_rmse, spectral_monte_carlo


def test_exact_for_a_linear_residual():
    # r(d) = A d - b: E|r(d + e)|^2 = |r(d)|^2 + sum_i alpha_i^2 |A_i|^2 exactly
    rng = np.random.default_rng(0)
    a, b, d = rng.standard_normal((30, 4)), rng.standard_normal(30), rng.uniform(50, 150, 4)
    alpha = np.array([0.5, 1.0, 0.2, 0.0])
    nominal, robust = second_order_robust_rmse(lambda x: a @ x - b, d, alpha)
    assert nominal == pytest.approx(np.linalg.norm(a @ d - b))
    assert robust ** 2 == pytest.approx(nominal ** 2 + float(np.sum(alpha ** 2 * np.sum(a ** 2, axis=0))), rel=1e-9)


def test_zero_error_gives_the_nominal_rmse():
    nominal, robust = second_order_robust_rmse(lambda x: np.sin(x / 50.0), np.array([60.0, 90.0]), np.zeros(2))
    assert robust == nominal


def test_agrees_with_monte_carlo_on_a_smooth_residual():
    def residual(x):
        return 1e-2 * np.array([np.sin(x[0] / 40.0) - 0.3, np.cos(x[1] / 55.0) * np.sin(x[0] / 70.0), x[1] / 400.0])

    d, n = np.array([80.0, 120.0]), np.array([2.35, 1.45])
    alpha = error_alpha(d, n, 0.3, 0.005, 0.5)
    _nominal, robust = second_order_robust_rmse(residual, d, alpha)
    mc = spectral_monte_carlo(lambda x: float(residual(x) @ residual(x)), d, n_real=n, sigma_abs_nm=0.3,
                              sigma_rel=0.005, sigma_ot_nm=0.5, draws=20000, seed=2)
    assert robust == pytest.approx(mc.rms, rel=0.02)


def test_error_alpha_combines_the_three_sources():
    alpha = error_alpha(np.array([100.0, 50.0]), np.array([2.0, 1.25]), 0.3, 0.01, 0.5)
    assert alpha == pytest.approx(np.sqrt(0.09 + np.array([1.0, 0.25]) + np.array([0.0625, 0.16])))
