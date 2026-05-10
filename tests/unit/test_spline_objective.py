"""Objectif spline PWL : cohérence sur un cas transmission simple."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from certus_index_spline_core import DataType, SplineOptConfig

from certus_index_utils import _transmittance_absolute_from_nk

from spline_objective import (
    SplinePWLObjective,
    decompose_spline_pwl_objective,
    nk_from_x_pwlnk,
    physical_nodes_to_x_slice_n,
)


def _minimal_transmission_cfg() -> SplineOptConfig:
    lam = np.linspace(500.0, 800.0, 24, dtype=np.float64)
    n_sub = np.full_like(lam, 1.52)
    n_film = 2.0
    k_film = 1e-8
    d_nm = 150.0
    n_l = np.full_like(lam, n_film)
    k_l = np.full_like(lam, k_film)
    t_exp = _transmittance_absolute_from_nk(lam, n_l, k_l, d_nm, n_sub)
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=1,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Test",
        t_is_ratio=False,
    )


def test_spline_pwl_objective_near_zero_on_matching_transmission() -> None:
    cfg = _minimal_transmission_cfg()
    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    sig = 1.0 / np.maximum(lam, 1e-9)
    s_lo, s_hi = float(np.min(sig)), float(np.max(sig))
    sk = np.array([s_lo, s_hi], dtype=np.float64)
    K = int(sk.size)
    nn = np.array([2.0, 2.0], dtype=np.float64)
    LL = np.full(K, np.log(1e-8), dtype=np.float64)
    d = 150.0
    x_n = physical_nodes_to_x_slice_n(nn, sk, cfg.n_mono_band_nm)
    xv = np.concatenate(([d], x_n, LL))
    obj = SplinePWLObjective(cfg, sk)
    cost = float(obj(xv))
    assert np.isfinite(cost)
    assert cost < 1e-6
    n_l2, k_l2 = nk_from_x_pwlnk(
        xv,
        lam,
        sk,
        float(cfg.k_clip_lo),
        float(cfg.k_clip_hi),
        sig_pre=sig,
        n_mono_band_nm=cfg.n_mono_band_nm,
        profile_interp=cfg.nk_profile_interp,
    )
    t_th = _transmittance_absolute_from_nk(lam, n_l2, k_l2, d, np.asarray(cfg.n_sub))
    rel = float(np.max(np.abs(t_th - np.asarray(cfg.t_exp))) / (np.max(np.abs(cfg.t_exp)) + 1e-12))
    assert rel < 5e-5


def test_pure_spectral_objective_zeros_penalty_and_matches_decompose() -> None:
    cfg = _minimal_transmission_cfg()
    lam = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
    sig = 1.0 / np.maximum(lam, 1e-9)
    s_lo, s_hi = float(np.min(sig)), float(np.max(sig))
    sk = np.array([s_lo, s_hi], dtype=np.float64)
    K = int(sk.size)
    nn = np.array([2.0, 2.0], dtype=np.float64)
    LL = np.full(K, np.log(1e-8), dtype=np.float64)
    d = 150.0
    x_n = physical_nodes_to_x_slice_n(nn, sk, cfg.n_mono_band_nm)
    xv = np.concatenate(([d], x_n, LL))
    mse_sp, pen, tot = decompose_spline_pwl_objective(cfg, sk, xv)
    assert np.isfinite(mse_sp)
    cfg_pure = cfg.replace(spline_pure_spectral_objective=True)
    mse2, pen2, tot2 = decompose_spline_pwl_objective(cfg_pure, sk, xv)
    assert pen2 == 0.0
    assert tot2 == mse2 == mse_sp
    assert float(SplinePWLObjective(cfg_pure, sk)(xv)) == float(mse2)
