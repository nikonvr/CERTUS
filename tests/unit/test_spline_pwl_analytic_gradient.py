"""Analytic gradient SplinePWLObjective vs finite differences (reduced sample)."""

from __future__ import annotations

import numpy as np
from scipy.optimize import approx_fprime

from certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots
from spline_objective import (
    SplinePWLObjective,
    spline_pwl_analytic_grad_supported,
)


def test_spline_pwl_analytic_grad_matches_fd_transmission() -> None:
    lam = np.linspace(500.0, 700.0, 24)
    n_sub = np.full_like(lam, 1.52)
    t_exp = 0.55 * np.ones_like(lam)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=11,
        d_lo=100.0,
        d_hi=5000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
        n_lambda_rising_penalty_weight=0.0,
        n_lambda_rising_penalty_band_nm=None,
        nk_profile_interp="pwl",
    )
    assert spline_pwl_analytic_grad_supported(cfg)
    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))
    k = int(sk.size)
    rng = np.random.default_rng(0)
    x = np.concatenate(
        (
            rng.uniform(800.0, 1200.0, size=1),
            rng.uniform(1.55, 1.75, size=k),
            rng.uniform(np.log(1e-3), np.log(0.02), size=k),
        )
    )
    obj = SplinePWLObjective(cfg, sk)
    g = obj.analytic_gradient(x)
    assert g is not None

    def fun(z: np.ndarray) -> float:
        return float(obj(np.asarray(z, dtype=np.float64)))

    eps = np.sqrt(np.finfo(float).eps) * (1.0 + np.maximum(np.abs(x), 1.0))
    g_fd = approx_fprime(x, fun, epsilon=eps)
    np.testing.assert_allclose(g, g_fd, rtol=5e-4, atol=5e-4)


def test_spline_pwl_analytic_grad_unsupported_when_t_is_ratio() -> None:
    lam = np.linspace(500.0, 700.0, 12)
    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=np.ones_like(lam) * 0.5,
        r_exp=None,
        n_sub=np.ones_like(lam) * 1.52,
        data_type=DataType.TRANSMISSION,
        n_seg=11,
        d_lo=100.0,
        d_hi=5000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=True,
    )
    assert not spline_pwl_analytic_grad_supported(cfg)
