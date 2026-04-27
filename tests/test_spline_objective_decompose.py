"""Cohérence ``decompose_spline_pwl_objective`` vs ``SplinePWLObjective``."""
from __future__ import annotations

import numpy as np

from certus_index_spline_core import DataType, SplineOptConfig
from spline_objective import SplinePWLObjective, decompose_spline_pwl_objective


def _cfg(**kwargs) -> SplineOptConfig:
    lam = np.linspace(400.0, 800.0, 40, dtype=np.float64)
    n_sub = np.full_like(lam, 1.52)
    base = dict(
        lam_nm=lam,
        t_exp=0.55 * np.ones_like(lam),
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=4,
        d_lo=100.0,
        d_hi=5000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
    )
    base.update(kwargs)
    return SplineOptConfig(**base)


def test_decompose_matches_spline_pwl_objective_call() -> None:
    cfg = _cfg()
    k = 5
    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)
    x = np.concatenate(
        ([250.0], np.linspace(1.45, 1.55, k), np.full(k, -12.0, dtype=np.float64))
    )
    obj = SplinePWLObjective(cfg, sk)
    total_obj = float(obj(x))
    msp, pen, tot = decompose_spline_pwl_objective(cfg, sk, x)
    assert np.isfinite(msp) and np.isfinite(pen) and np.isfinite(tot)
    assert abs(tot - (msp + pen)) < 1e-12
    assert abs(total_obj - tot) < 1e-9 * max(abs(total_obj), 1.0)


def test_decompose_matches_with_mono_band_and_rmse_window() -> None:
    cfg = _cfg(
        rmse_fit_lambda_nm=(500.0, 700.0),
        n_mono_band_nm=(500.0, 700.0),
    )
    k = 6
    sk = np.linspace(1.0 / 780.0, 1.0 / 420.0, k, dtype=np.float64)
    x = np.concatenate(
        ([300.0], np.linspace(1.42, 1.58, k), np.linspace(-14.0, -10.0, k))
    )
    obj = SplinePWLObjective(cfg, sk)
    total_obj = float(obj(x))
    msp, pen, tot = decompose_spline_pwl_objective(cfg, sk, x)
    assert abs(tot - (msp + pen)) < 1e-12
    assert abs(total_obj - tot) < 1e-9 * max(abs(total_obj), 1.0)
