"""Tests unitaires : spline_objective — codecs sigma, interpolation, SplinePWLObjective."""

from __future__ import annotations

import numpy as np
import pytest

from certus.spline.certus_index_spline_core import (
    DataType,
    SplineOptConfig,
    canonical_spline_sigma_knots,
)
from certus.spline.spline_objective import (
    sigma_knots_encode,
    sigma_knots_decode,
    nk_from_x_pwlnk,
    build_segment_optimizer_x_vector,
    _spline_objective_lam_mask,
    _interpolate_along_sigma,
    build_spline_objective_masked_grid,
    spline_objective_mse_on_masked_grid,
    spectral_mse_rmse_masked_from_nk,
    decompose_spline_pwl_objective,
    SplinePWLObjective,
    objective_lam_mask_on_target_grid,
)


def _make_cfg(n_pts: int = 50, data_type: DataType = DataType.TRANSMISSION) -> SplineOptConfig:
    lam = np.linspace(400, 1000, n_pts)
    return SplineOptConfig(
        lam_nm=lam,
        t_exp=np.full_like(lam, 0.5),
        r_exp=None,
        n_sub=np.full_like(lam, 1.46),
        data_type=data_type,
        n_seg=8,
        d_lo=50.0,
        d_hi=500.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="SiO2",
        t_is_ratio=False,
    )


# ── sigma_knots_encode / decode roundtrip ──


class TestSigmaKnotsCodec:
    def test_encode_returns_correct_size(self) -> None:
        sk = np.linspace(0.001, 0.003, 8)
        enc = sigma_knots_encode(sk, 0.001, 0.003)
        assert enc.shape == (7,)  # K-1 log proportions

    def test_roundtrip_preserves_endpoints(self) -> None:
        s_lo, s_hi = 0.001, 0.003
        sk = np.linspace(s_lo, s_hi, 6)
        enc = sigma_knots_encode(sk, s_lo, s_hi)
        dec = sigma_knots_decode(enc, s_lo, s_hi)
        assert abs(float(dec[0]) - s_lo) < 1e-9
        assert abs(float(dec[-1]) - s_hi) < 1e-9

    def test_roundtrip_preserves_count(self) -> None:
        sk = np.linspace(0.001, 0.003, 10)
        enc = sigma_knots_encode(sk, 0.001, 0.003)
        dec = sigma_knots_decode(enc, 0.001, 0.003)
        assert dec.size == sk.size

    def test_roundtrip_monotonic(self) -> None:
        sk = np.linspace(0.001, 0.003, 8)
        enc = sigma_knots_encode(sk, 0.001, 0.003)
        dec = sigma_knots_decode(enc, 0.001, 0.003)
        assert np.all(np.diff(dec) > 0)

    def test_decode_with_work_dict(self) -> None:
        enc = np.zeros(5)
        work: dict = {}
        dec = sigma_knots_decode(enc, 0.001, 0.003, work=work)
        assert dec.size == 6
        assert "ww" in work

    def test_decode_reuse_output(self) -> None:
        enc = np.zeros(5)
        work: dict = {}
        dec1 = sigma_knots_decode(enc, 0.001, 0.003, work=work, reuse_output=True)
        assert dec1.size == 6

    def test_decode_extreme_values(self) -> None:
        enc = np.full(5, 20.0)  # Extreme positive
        dec = sigma_knots_decode(enc, 0.001, 0.003)
        assert np.all(np.isfinite(dec))

    def test_decode_negative_extreme(self) -> None:
        enc = np.full(5, -20.0)  # Extreme negative
        dec = sigma_knots_decode(enc, 0.001, 0.003)
        assert np.all(np.isfinite(dec))


# ── _interpolate_along_sigma ──


class TestInterpolateAlongSigma:
    def test_pwl_basic(self) -> None:
        sk = np.array([0.001, 0.002, 0.003])
        vals = np.array([1.5, 2.0, 1.8])
        sig = np.array([0.0015])
        result = _interpolate_along_sigma(sig, sk, vals, "pwl")
        assert result.shape == (1,)
        assert 1.5 < float(result[0]) < 2.0

    def test_smooth_needs_4_nodes(self) -> None:
        sk = np.linspace(0.001, 0.003, 5)
        vals = np.sin(sk * 1000)
        sig = np.linspace(0.001, 0.003, 20)
        result = _interpolate_along_sigma(sig, sk, vals, "smooth")
        assert result.shape == (20,)

    def test_too_few_nodes_raises(self) -> None:
        with pytest.raises(ValueError):
            _interpolate_along_sigma(np.array([0.001]), np.array([0.001]), np.array([1.5]), "pwl")


# ── nk_from_x_pwlnk ──


class TestNkFromXPwlnk:
    def test_basic_output_shape(self) -> None:
        lam = np.linspace(400, 1000, 30)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        n_l, k_l = nk_from_x_pwlnk(x, lam, sk, 1e-8, 10.0)
        assert n_l.shape == lam.shape
        assert k_l.shape == lam.shape

    def test_n_clipped_to_limits(self) -> None:
        lam = np.linspace(400, 1000, 20)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 0.01), np.full(k, np.log(1e-3))))
        n_l, _ = nk_from_x_pwlnk(x, lam, sk, 1e-8, 10.0)
        assert np.all(n_l >= 0.01)  # N_MIN_LIMIT

    def test_k_clipped(self) -> None:
        lam = np.linspace(400, 1000, 20)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(100.0))))
        _, k_l = nk_from_x_pwlnk(x, lam, sk, 1e-8, 10.0)
        assert np.all(k_l <= 10.0)

    def test_with_sig_pre(self) -> None:
        lam = np.linspace(400, 1000, 20)
        sig = 1.0 / lam
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        n_l, k_l = nk_from_x_pwlnk(x, lam, sk, 1e-8, 10.0, sig_pre=sig)
        assert n_l.shape == lam.shape


# ── _spline_objective_lam_mask ──


class TestSplineObjectiveLamMask:
    def test_all_finite(self) -> None:
        cfg = _make_cfg(50)
        mask = _spline_objective_lam_mask(cfg)
        assert mask.dtype == bool
        assert np.all(mask)

    def test_nan_in_t_exp(self) -> None:
        cfg = _make_cfg(50)
        t = np.array(cfg.t_exp, copy=True)
        t[10] = np.nan
        cfg2 = cfg.replace(t_exp=t)
        mask = _spline_objective_lam_mask(cfg2)
        assert not mask[10]


# ── objective_lam_mask_on_target_grid ──


class TestObjectiveLamMaskOnTargetGrid:
    def test_same_grid_returns_identical(self) -> None:
        cfg = _make_cfg(50)
        lam = np.asarray(cfg.lam_nm)
        mask = objective_lam_mask_on_target_grid(cfg, lam)
        assert mask.shape == lam.shape

    def test_empty_target(self) -> None:
        cfg = _make_cfg(50)
        mask = objective_lam_mask_on_target_grid(cfg, np.array([]))
        assert mask.size == 0


# ── build_spline_objective_masked_grid ──


class TestBuildSplineObjectiveMaskedGrid:
    def test_returns_tuple(self) -> None:
        cfg = _make_cfg(50)
        result = build_spline_objective_masked_grid(cfg)
        assert result is not None
        lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = result
        assert lam_f.size > 0
        assert sig_f.size == lam_f.size
        assert w.size == lam_f.size
        assert inv_npix > 0


# ── SplinePWLObjective ──


class TestSplinePWLObjective:
    def test_call_returns_finite(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        cost = obj(x)
        assert np.isfinite(cost)
        assert cost >= 0

    def test_call_deterministic(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        c1 = obj(x)
        c2 = obj(x)
        assert c1 == c2


# ── decompose_spline_pwl_objective ──


class TestDecomposeSplinePwlObjective:
    def test_returns_three_floats(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        mse_sp, pen, tot = decompose_spline_pwl_objective(cfg, sk, x)
        assert np.isfinite(mse_sp)
        assert np.isfinite(pen)
        assert abs(tot - (mse_sp + pen)) < 1e-12

    def test_wrong_x_size_returns_nan(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        mse_sp, pen, tot = decompose_spline_pwl_objective(cfg, sk, np.array([1.0, 2.0]))
        assert np.isnan(mse_sp)


# ── spectral_mse_rmse_masked_from_nk ──


class TestSpectralMseRmseMaskedFromNk:
    def test_returns_finite(self) -> None:
        cfg = _make_cfg(50)
        lam = np.asarray(cfg.lam_nm)
        n_l = np.full_like(lam, 2.0)
        k_l = np.full_like(lam, 1e-3)
        mse, rmse = spectral_mse_rmse_masked_from_nk(cfg, {}, lam, n_l, k_l, 200.0)
        assert np.isfinite(mse)
        assert np.isfinite(rmse)
        assert rmse >= 0
        assert abs(rmse - np.sqrt(max(mse, 0))) < 1e-10


# ── build_segment_optimizer_x_vector ──


class TestBuildSegmentOptimizerXVector:
    def test_returns_none_for_bad_sk(self) -> None:
        cfg = _make_cfg()
        result = build_segment_optimizer_x_vector({"sigma_knots": np.array([0.001])}, cfg)
        assert result is None

    def test_from_x_field(self) -> None:
        cfg = _make_cfg()
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        result = build_segment_optimizer_x_vector({"sigma_knots": sk, "x": x}, cfg)
        assert result is not None
        xb, sk_out = result
        np.testing.assert_allclose(xb, x)

    def test_from_nodes(self) -> None:
        cfg = _make_cfg()
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        out = {
            "sigma_knots": sk,
            "n_nodes_physical": np.full(k, 2.0),
            "L_nodes": np.full(k, np.log(1e-3)),
            "d_nm": 200.0,
        }
        result = build_segment_optimizer_x_vector(out, cfg)
        assert result is not None
        xb, sk_out = result
        assert xb.size == 1 + 2 * k


# ── SplinePWLObjective: cost_and_grad ──


class TestSplinePWLObjectiveCostAndGrad:
    def test_cost_and_grad_cost_matches_call(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        cost_call = obj(x)
        cost_cag, grad = obj.cost_and_grad(x)
        assert abs(cost_call - cost_cag) < 1e-12

    def test_grad_returns_array(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        _, grad = obj.cost_and_grad(x)
        assert isinstance(grad, np.ndarray)
        assert grad.shape == x.shape


# ── SplinePWLObjective: evaluate_batch ──


class TestSplinePWLObjectiveEvaluateBatch:
    def test_batch_single_matches_call(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        cost_single = obj(x)
        Y = obj.evaluate_batch(x.reshape(1, -1))
        assert Y.shape == (1,)
        assert abs(float(Y[0]) - cost_single) < 1e-8

    def test_batch_multiple(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        rng = np.random.default_rng(42)
        X = np.empty((5, 1 + 2 * k))
        for i in range(5):
            X[i] = np.concatenate(([150.0 + 50 * i], np.full(k, 1.5 + 0.1 * i), np.full(k, np.log(1e-3 + 1e-4 * i))))
        Y = obj.evaluate_batch(X)
        assert Y.shape == (5,)
        assert np.all(np.isfinite(Y))

    def test_batch_empty(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        Y = obj.evaluate_batch(np.empty((0, 1 + 2 * k)))
        assert Y.shape == (0,)


# ── SplinePWLObjective: _fast_nk ──


class TestSplinePWLObjectiveFastNk:
    def test_fast_nk_returns_triple(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        n_l, k_l, n_n = obj._fast_nk(x)
        assert n_l.shape == (obj.n_pix,)
        assert k_l.shape == (obj.n_pix,)
        assert n_n.shape == (k,)


# ── SplinePWLObjective: caching behaviour ──


class TestSplinePWLObjectiveCaching:
    def test_cached_result_reused(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        c1 = obj(x)
        # second call should use cache
        c2 = obj(x)
        assert c1 == c2

    def test_different_x_gives_different_cost(self) -> None:
        cfg = _make_cfg(50)
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x1 = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        x2 = np.concatenate(([300.0], np.full(k, 1.5), np.full(k, np.log(1e-2))))
        c1 = obj(x1)
        c2 = obj(x2)
        assert c1 != c2


# ── spline_spectral_mse_from_xy_nk ──


class TestSplineSpectralMseFromXyNk:
    def test_returns_finite(self) -> None:
        from certus.spline.spline_objective import spline_spectral_mse_from_xy_nk
        cfg = _make_cfg(50)
        lam = np.asarray(cfg.lam_nm)
        n_l = np.full_like(lam, 2.0)
        k_l = np.full_like(lam, 1e-3)
        mse = spline_spectral_mse_from_xy_nk(cfg, lam, n_l, k_l, 200.0)
        assert mse is not None
        assert np.isfinite(mse)

    def test_size_mismatch_returns_none(self) -> None:
        from certus.spline.spline_objective import spline_spectral_mse_from_xy_nk
        cfg = _make_cfg(50)
        lam = np.asarray(cfg.lam_nm)
        n_l = np.full(10, 2.0)  # wrong size
        k_l = np.full_like(lam, 1e-3)
        mse = spline_spectral_mse_from_xy_nk(cfg, lam, n_l, k_l, 200.0)
        assert mse is None


# ── objective_lam_mask_on_target_grid: different grid ──


class TestObjectiveLamMaskInterpolated:
    def test_different_grid_interpolates(self) -> None:
        cfg = _make_cfg(50)
        lam_target = np.linspace(450, 950, 30)
        mask = objective_lam_mask_on_target_grid(cfg, lam_target)
        assert mask.shape == (30,)
        assert mask.dtype == bool


class TestSplineObjectiveCoverageBoostExtra:
    def test_decode_edge_cases_and_work_dictionary_sizes(self) -> None:
        work = {
            "ww": np.array([1.0]),
            "ds": np.array([1.0]),
            "c": np.array([1.0]),
            "sk": np.array([1.0, 2.0]),
        }
        enc = np.array([0.1, 0.2, 0.3])
        dec = sigma_knots_decode(enc, 0.001, 0.003, work=work)
        assert dec.size == 4
        
        dec2 = sigma_knots_decode(enc, 0.001, 0.003, eps_s=None)
        assert dec2.size == 4
        
        dec3 = sigma_knots_decode(np.array([0.1]), 0.001, 0.003)
        assert dec3.size == 2

    def test_evaluate_batch_hybrid_fused_with_penalty(self) -> None:
        lam = np.linspace(400, 1000, 20)
        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=np.full_like(lam, 0.5),
            r_exp=np.full_like(lam, 0.2),
            n_sub=np.full_like(lam, 1.46),
            data_type=DataType.BOTH,
            n_seg=4,
            d_lo=50.0,
            d_hi=500.0,
            weight_t=0.5,
            weight_r=0.5,
            substrate_name="SiO2",
            t_is_ratio=False,
            n_lambda_penalty=1e-4,
        )
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        Y = obj.evaluate_batch(x.reshape(1, -1))
        assert Y.shape == (1,)

    def test_evaluate_batch_ratio_unfused(self) -> None:
        lam = np.linspace(400, 1000, 20)
        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=np.full_like(lam, 0.5),
            r_exp=None,
            n_sub=np.full_like(lam, 1.46),
            data_type=DataType.TRANSMISSION,
            n_seg=4,
            d_lo=50.0,
            d_hi=500.0,
            weight_t=1.0,
            weight_r=0.0,
            substrate_name="SiO2",
            t_is_ratio=True,
        )
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        Y = obj.evaluate_batch(x.reshape(1, -1))
        assert Y.shape == (1,)

    def test_objective_non_finite_mse_fallback(self) -> None:
        lam = np.linspace(400, 1000, 20)
        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=np.full_like(lam, 0.5),
            r_exp=None,
            n_sub=np.full_like(lam, 1.46),
            data_type=DataType.TRANSMISSION,
            n_seg=4,
            d_lo=50.0,
            d_hi=500.0,
            weight_t=np.nan,
            weight_r=0.0,
            substrate_name="SiO2",
            t_is_ratio=False,
        )
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        cost = obj(x)
        assert cost == 1e30

    def test_cost_and_grad_none_grad_fallback(self) -> None:
        lam = np.linspace(400, 1000, 20)
        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=np.full_like(lam, 0.5),
            r_exp=None,
            n_sub=np.full_like(lam, 1.46),
            data_type=DataType.TRANSMISSION,
            n_seg=4,
            d_lo=50.0,
            d_hi=500.0,
            weight_t=1.0,
            weight_r=0.0,
            substrate_name="SiO2",
            t_is_ratio=True,
        )
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        x = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
        cost, grad = obj.cost_and_grad(x)
        assert cost > 0
        assert np.array_equal(grad, np.zeros(x.size))

    def test_fast_penalty_grad_active_violations(self) -> None:
        lam = np.linspace(400, 1000, 20)
        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=np.full_like(lam, 0.5),
            r_exp=None,
            n_sub=np.full_like(lam, 1.46),
            data_type=DataType.TRANSMISSION,
            n_seg=4,
            d_lo=50.0,
            d_hi=500.0,
            weight_t=1.0,
            weight_r=0.0,
            substrate_name="SiO2",
            t_is_ratio=False,
            n_lambda_penalty=1.0,
        )
        sk = canonical_spline_sigma_knots(400, 1000)
        k = int(sk.size)
        obj = SplinePWLObjective(cfg, sk)
        # Decrease n nodes with wavelength to violate rising penalty
        n_vals = np.linspace(3.0, 1.1, k)
        x = np.concatenate(([200.0], n_vals, np.full(k, np.log(1e-3))))
        
        cost = obj(x)
        grad = obj.analytic_gradient(x)
        assert cost > 0
        assert grad.size == x.size



