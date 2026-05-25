"""Focused tests for spline_objective numerical helpers."""
from __future__ import annotations

import numpy as np
import pytest

from certus_index_spline_core import DataType, SplineOptConfig
from spline_objective import (
    SplinePWLObjective,
    _cached_spectral_rmse_weights,
    build_segment_optimizer_x_vector,
    build_spline_objective_masked_grid,
    decompose_spline_pwl_objective,
    objective_lam_mask_on_target_grid,
    sigma_knots_decode,
    sigma_knots_encode,
    spline_pwl_analytic_grad_supported,
    spline_spectral_mse_from_xy_nk,
    _interpolate_along_sigma,
)


@pytest.fixture
def minimal_cfg() -> SplineOptConfig:
    lam = np.array([400.0, 500.0, 600.0, 700.0], dtype=np.float64)
    t_exp = np.array([0.2, 0.3, 0.4, 0.5], dtype=np.float64)
    n_sub = np.full_like(lam, 1.45)
    return SplineOptConfig(
        substrate_name="SiO2",
        weight_r=0.0,
        weight_t=1.0,
        d_hi=1800.0,
        d_lo=1600.0,
        n_seg=2,
        data_type=DataType.TRANSMISSION,
        n_sub=n_sub,
        r_exp=None,
        t_exp=t_exp,
        lam_nm=lam,
        rmse_fit_lambda_nm=(450.0, 650.0),
    )


def _make_x(k_nodes: int = 4) -> np.ndarray:
    return np.array([1700.0] + [1.5] * k_nodes + [np.log(0.02)] * k_nodes, dtype=np.float64)


def test_cached_weights_return_same_shape() -> None:
    lam = np.array([400.0, 500.0, 600.0], dtype=np.float64)
    w1 = _cached_spectral_rmse_weights(lam)
    w2 = _cached_spectral_rmse_weights(lam)
    assert w1.shape == lam.shape
    np.testing.assert_allclose(w1, w2)


def test_sigma_knots_roundtrip_basic() -> None:
    sk = np.array([0.001, 0.002, 0.003], dtype=np.float64)
    enc = sigma_knots_encode(sk, 0.001, 0.003)
    dec = sigma_knots_decode(enc, 0.001, 0.003)
    assert dec.shape == sk.shape
    assert np.all(np.diff(dec) >= 0.0)
    assert dec[0] >= 0.001
    assert dec[-1] == pytest.approx(0.003)


def test_interpolate_along_sigma_pwl_and_smooth() -> None:
    sig = np.array([0.001, 0.0015, 0.002, 0.0025], dtype=np.float64)
    sk = np.array([0.001, 0.0015, 0.002, 0.0025], dtype=np.float64)
    values = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    out_pwl = _interpolate_along_sigma(sig, sk, values, "pwl")
    out_smooth = _interpolate_along_sigma(sig, sk, values, "smooth")
    assert out_pwl.shape == sig.shape
    assert out_smooth.shape == sig.shape


def test_objective_mask_and_grid(minimal_cfg: SplineOptConfig) -> None:
    mask = objective_lam_mask_on_target_grid(minimal_cfg, minimal_cfg.lam_nm)
    assert mask.shape == minimal_cfg.lam_nm.shape
    grid = build_spline_objective_masked_grid(minimal_cfg)
    assert grid is not None
    lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = grid
    assert lam_f.size == sig_f.size == n_sub_f.size == w.size
    assert inv_npix == pytest.approx(1.0 / lam_f.size)
    assert t_exp_f is not None
    assert r_exp_f is None


def test_spectral_mse_and_decomposition(minimal_cfg: SplineOptConfig) -> None:
    x = _make_x(4)
    lam = minimal_cfg.lam_nm
    n_lam = np.full_like(lam, 1.55)
    k_lam = np.full_like(lam, 0.02)
    mse = spline_spectral_mse_from_xy_nk(minimal_cfg, lam, n_lam, k_lam, 1700.0)
    assert mse is not None
    mse_sp, pen, total = decompose_spline_pwl_objective(minimal_cfg, np.array([0.001, 0.002, 0.003, 0.004]), x)
    assert np.isfinite(mse_sp)
    assert np.isfinite(pen)
    assert np.isfinite(total)
    assert total == pytest.approx(mse_sp + pen)


def test_build_segment_optimizer_vector_roundtrip(minimal_cfg: SplineOptConfig) -> None:
    sk = np.array([0.001, 0.002, 0.003, 0.004], dtype=np.float64)
    x = _make_x(4)
    out = {"sigma_knots": sk, "x": x}
    rebuilt = build_segment_optimizer_x_vector(out, minimal_cfg)
    assert rebuilt is not None
    xb, sk_out = rebuilt
    assert xb.shape == x.shape
    assert sk_out.shape == sk.shape


def test_objective_class_and_gradient_support(minimal_cfg: SplineOptConfig) -> None:
    sk = np.array([0.001, 0.002, 0.003, 0.004], dtype=np.float64)
    obj = SplinePWLObjective(minimal_cfg, sk)
    x = _make_x(4)
    value = obj(x)
    assert np.isfinite(value)
    assert spline_pwl_analytic_grad_supported(minimal_cfg) in (True, False)
    grad = obj.analytic_gradient(x)
    assert grad is None or grad.shape == x.shape
