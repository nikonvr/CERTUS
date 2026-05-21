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
    sigma_knots_encode,
    sigma_knots_decode,
    build_segment_optimizer_x_vector,
    objective_lam_mask_on_target_grid,
    build_spline_objective_masked_grid,
    spline_objective_mse_on_masked_grid,
    spectral_mse_rmse_masked_from_nk,
    spline_spectral_mse_from_xy_nk,
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


# ─────────────────────────────────────────────────────────────────────
# Additional Coverage Boost for spline_objective.py
# ─────────────────────────────────────────────────────────────────────

import pytest

class TestSplineObjectiveCoverageBoost:
    def test_sigma_knots_codec(self):
        sk = np.array([400.0, 600.0, 800.0])
        encoded = sigma_knots_encode(sk, 400.0, 800.0)
        assert encoded.size == 2
        
        decoded = sigma_knots_decode(encoded, 400.0, 800.0)
        assert np.allclose(decoded, sk)

        # Non-finite / edge case decoding
        bad_encoded = np.array([float("nan"), float("inf")])
        decoded_fallback = sigma_knots_decode(bad_encoded, 400.0, 800.0)
        assert decoded_fallback[0] == 400.0
        assert decoded_fallback[-1] == 800.0

        # Decode with work reuse
        work = {}
        decoded_work = sigma_knots_decode(encoded, 400.0, 800.0, work=work, reuse_output=True)
        assert "ww" in work
        assert np.allclose(decoded_work, sk)

    def test_interpolate_along_sigma_errors(self):
        from spline_objective import _interpolate_along_sigma
        # Nodes < 2 should raise ValueError
        with pytest.raises(ValueError, match="at least 2 nodes required"):
            _interpolate_along_sigma(np.array([500.0]), np.array([500.0]), np.array([1.5]), "smooth")

    def test_build_segment_optimizer_x_vector(self):
        cfg = _minimal_transmission_cfg()
        
        # Valid reconstruction using raw x
        out_valid = {
            "sigma_knots": np.array([0.00125, 0.002]),
            "x": np.array([150.0, 2.0, 2.0, np.log(1e-8), np.log(1e-8)]),
        }
        x, sk = build_segment_optimizer_x_vector(out_valid, cfg)
        assert x.size == 5
        assert np.allclose(sk, out_valid["sigma_knots"])

        # Failures
        assert build_segment_optimizer_x_vector({"sigma_knots": np.array([])}, cfg) is None
        assert build_segment_optimizer_x_vector({"sigma_knots": np.array([1.0]), "n_nodes_physical": np.array([1.5, 1.6])}, cfg) is None
        assert build_segment_optimizer_x_vector({"sigma_knots": np.array([1.0, 2.0]), "n_nodes_physical": np.array([1.5]), "L_nodes": np.array([2.0, 3.0])}, cfg) is None
        assert build_segment_optimizer_x_vector({"sigma_knots": np.array([1.0, 2.0]), "n_nodes_physical": np.array([1.5, 1.6]), "L_nodes": np.array([2.0, 3.0]), "d_nm": float("nan")}, cfg) is None

    def test_objective_lam_mask_on_target_grid(self):
        cfg = _minimal_transmission_cfg()
        
        # Empty grids
        assert objective_lam_mask_on_target_grid(cfg, np.array([])).size == 0
        
        cfg_empty = replace(cfg, lam_nm=np.array([]), n_sub=np.array([]), t_exp=np.array([]))
        assert np.all(objective_lam_mask_on_target_grid(cfg_empty, np.array([500.0, 600.0])) == False)

        # Single source node
        cfg_single = replace(cfg, lam_nm=np.array([500.0]), n_sub=np.array([1.5]), t_exp=np.array([0.9]))
        mask = objective_lam_mask_on_target_grid(cfg_single, np.array([500.0, 600.0]))
        assert mask.shape == (2,)


    def test_build_spline_objective_masked_grid_empty(self):
        cfg = _minimal_transmission_cfg()
        cfg_empty = replace(cfg, lam_nm=np.array([]), n_sub=np.array([]), t_exp=np.array([]))
        assert build_spline_objective_masked_grid(cfg_empty) is None

    def test_spline_objective_mse_on_masked_grid_modes(self):
        cfg = _minimal_transmission_cfg()
        
        # Test reflection only
        cfg_ref = replace(cfg, data_type=DataType.REFLECTION, r_exp=np.full_like(cfg.t_exp, 0.05), weight_t=0.0, weight_r=1.0)
        grid = build_spline_objective_masked_grid(cfg_ref)
        assert grid is not None
        lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = grid
        
        n_l = np.full_like(lam_f, 2.0)
        k_l = np.full_like(lam_f, 1e-5)
        
        loss = spline_objective_mse_on_masked_grid(
            cfg_ref,
            lam_f=lam_f,
            n_sub_f=n_sub_f,
            w=w,
            inv_npix=inv_npix,
            t_exp_f=t_exp_f,
            r_exp_f=r_exp_f,
            n_l=n_l,
            k_l=k_l,
            d=150.0
        )
        assert np.isfinite(loss)

        # Test ratio mode
        cfg_ratio = replace(cfg, t_is_ratio=True)
        grid_ratio = build_spline_objective_masked_grid(cfg_ratio)
        assert grid_ratio is not None
        lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = grid_ratio
        
        loss_ratio = spline_objective_mse_on_masked_grid(
            cfg_ratio,
            lam_f=lam_f,
            n_sub_f=n_sub_f,
            w=w,
            inv_npix=inv_npix,
            t_exp_f=t_exp_f,
            r_exp_f=r_exp_f,
            n_l=n_l,
            k_l=k_l,
            d=150.0
        )
        assert np.isfinite(loss_ratio)

    def test_spectral_mse_rmse_masked_from_nk_mismatch(self):
        cfg = _minimal_transmission_cfg()
        # Invalid lengths
        mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, np.array([500.0]), np.array([2.0, 2.0]), np.array([1e-5]), 150.0)
        assert np.isnan(mse)
        assert np.isnan(rmse)

    def test_spline_spectral_mse_from_xy_nk_errors(self):
        cfg = _minimal_transmission_cfg()
        # Empty grid
        cfg_empty = replace(cfg, lam_nm=np.array([]), n_sub=np.array([]), t_exp=np.array([]))
        assert spline_spectral_mse_from_xy_nk(cfg_empty, np.array([500.0]), np.array([2.0]), np.array([1e-5]), 150.0) is None
        
        # Mismatched input dimensions
        assert spline_spectral_mse_from_xy_nk(cfg, np.array([500.0, 600.0]), np.array([2.0]), np.array([1e-5]), 150.0) is None

    def test_decompose_spline_pwl_objective_errors(self):
        cfg = _minimal_transmission_cfg()
        sk = np.array([0.00125, 0.002])
        # Incorrect x dimension
        mse, pen, tot = decompose_spline_pwl_objective(cfg, sk, np.array([150.0]))
        assert np.isnan(mse)
        assert np.isnan(pen)
        assert np.isnan(tot)

