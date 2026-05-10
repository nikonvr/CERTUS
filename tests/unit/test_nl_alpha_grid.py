"""Grille alpha NL (INDEX SPLINE post-pass)."""

from __future__ import annotations



from types import SimpleNamespace



import numpy as np



from certus_index_spline_core import DataType, SplineOptConfig, canonical_spline_sigma_knots



from spline_nonlinear_alpha import (
    clear_nl_result_fields,

    ALPHA_NL_HI,

    ALPHA_NL_LO,

    ALPHA_NL_STEP,

    _pick_nl_start_x_and_mode,

    nl_alpha_grid_values,

    nl_alpha_scan_order_values,

    nonlinear_alpha_lbfgs_maxfun_per_step,

    nonlinear_alpha_second_pass_maxfun_effective,

)





def test_nl_alpha_grid_endpoints_and_count() -> None:

    g = nl_alpha_grid_values()

    assert g.size == int(round((ALPHA_NL_HI - ALPHA_NL_LO) / ALPHA_NL_STEP)) + 1

    assert abs(float(g[0]) - ALPHA_NL_LO) < 1e-9

    assert abs(float(g[-1]) - ALPHA_NL_HI) < 1e-9

    dg = np.diff(g)

    assert np.all(np.abs(dg - ALPHA_NL_STEP) < 1e-6)





def test_nl_alpha_slow_mode_matches_polish_maxfun() -> None:

    cfg = SimpleNamespace(polish_maxfun=5000, nonlinear_alpha_budget_mode="slow")

    mf, mode = nonlinear_alpha_lbfgs_maxfun_per_step(cfg)

    assert mode == "slow"

    expect = int(max(800, min(max(5000, round(5000 * 1.35)), 50_000)))

    assert mf == expect





def test_nl_alpha_fast_mode_shared_budget() -> None:

    cfg = SimpleNamespace(polish_maxfun=5000, nonlinear_alpha_budget_mode="fast")

    mf, mode = nonlinear_alpha_lbfgs_maxfun_per_step(cfg)

    assert mode == "fast"

    n_a = int(nl_alpha_scan_order_values().size)

    expect = int(max(400, min(5000 * 2 // max(n_a, 1), 10_000)))

    assert mf == expect





def test_nl_alpha_second_pass_maxfun_stricter_than_grid() -> None:

    cfg = SimpleNamespace(polish_maxfun=5000, nonlinear_alpha_second_pass_maxfun=None)

    mf_grid = 476

    mf2 = nonlinear_alpha_second_pass_maxfun_effective(cfg, mf_grid)

    assert mf2 > mf_grid

    assert mf2 >= int(round(5000 * 1.85))





def test_nl_alpha_scan_order_centered_on_one() -> None:

    g = nl_alpha_grid_values()

    s = nl_alpha_scan_order_values()

    assert np.array_equal(np.sort(s), np.sort(g))

    assert s.size == g.size

    idx0 = int(np.argmin(np.abs(g - 1.0)))

    assert abs(float(s[0]) - float(g[idx0])) < 1e-9

    for k in range(1, min(idx0, g.size - 1 - idx0) + 1):

        assert abs(float(s[2 * k - 1]) - float(g[idx0 - k])) < 1e-9

        assert abs(float(s[2 * k]) - float(g[idx0 + k])) < 1e-9





def _nl_cfg_min(lam: np.ndarray) -> SplineOptConfig:

    return SplineOptConfig(

        lam_nm=lam,

        t_exp=np.full_like(lam, 0.5),

        r_exp=None,

        n_sub=np.full_like(lam, 1.5),

        data_type=DataType.TRANSMISSION,

        n_seg=8,

        d_lo=50.0,

        d_hi=500.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

    )





def test_nl_alpha_pick_uses_canonical_sigma_when_stored_knots_mismatch_x_seg() -> None:

    """sigma_knots obsolète dans out : K(x_seg) aligné sur le maillage canonique lambda."""

    lam = np.linspace(400.0, 2000.0, 35)

    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))

    k = int(sk.size)

    d0 = 100.0

    x_seg = np.concatenate(

        (

            np.asarray([d0], dtype=np.float64),

            np.full(k, 2.0, dtype=np.float64),

            np.full(k, np.log(1e-3), dtype=np.float64),

        )

    )

    cfg = _nl_cfg_min(lam)

    out = {

        "sigma_knots": np.linspace(0.001, 0.002, 5, dtype=np.float64),

        "x_seg_spline_sigma": x_seg,

    }

    picked = _pick_nl_start_x_and_mode(cfg, out)

    assert picked is not None

    xb, skb, prof = picked

    assert prof == "smooth"

    np.testing.assert_allclose(xb, x_seg)

    assert int(skb.size) == k

    np.testing.assert_allclose(skb, sk)





def test_nl_alpha_pick_reconstructs_x_from_seg_nk_without_x_seg() -> None:

    lam = np.linspace(400.0, 2000.0, 42)

    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))

    k = int(sk.size)

    cfg = _nl_cfg_min(lam)

    d_seg = 120.0

    out = {

        "d_nm_seg_spline_sigma": d_seg,

        "n_lam_seg_spline_sigma": np.full_like(lam, 2.1),

        "k_lam_seg_spline_sigma": np.full_like(lam, 2e-3),

    }

    picked = _pick_nl_start_x_and_mode(cfg, out)

    assert picked is not None

    xb, skb, _prof = picked

    assert xb.size == 1 + 2 * k

    assert int(skb.size) == k

    assert abs(float(xb[0]) - d_seg) < 1e-9

    np.testing.assert_allclose(xb[1 : 1 + k], 2.1)

    np.testing.assert_allclose(xb[1 + k : 1 + 2 * k], np.log(2e-3))





def test_sol3_rmse_acceptance_requires_meaningful_gain() -> None:


    from spline_pipeline import _spl_rmse_improves_meaningfully


    assert not _spl_rmse_improves_meaningfully(0.01, 0.01)


    assert not _spl_rmse_improves_meaningfully(0.01, 0.0099999)


    assert _spl_rmse_improves_meaningfully(0.01, 0.009)


    assert not _spl_rmse_improves_meaningfully(float("nan"), 0.01)


def test_nl_clear_result_fields_removes_new_decision_keys() -> None:
    out = {
        "nl_alpha_selection_criterion": "mse_lbfgs_objectif",
        "nl_alpha_best_by_objective": 1.0,
        "nl_alpha_best_by_raw_rmse": 1.0005,
        "nl_alpha_best_by_scaled_rmse": 1.0,
        "nl_alpha_selection_diverges_from_raw_rmse": True,
        "nl_alpha_identifiability_thr_flat": 1e-4,
        "nl_alpha_identifiability_thr_budget_hits": 3,
        "unrelated_key": 42,
    }

    clear_nl_result_fields(out)

    assert "nl_alpha_selection_criterion" not in out
    assert "nl_alpha_best_by_objective" not in out
    assert "nl_alpha_best_by_raw_rmse" not in out
    assert "nl_alpha_best_by_scaled_rmse" not in out
    assert "nl_alpha_selection_diverges_from_raw_rmse" not in out
    assert "nl_alpha_identifiability_thr_flat" not in out
    assert "nl_alpha_identifiability_thr_budget_hits" not in out
    assert out.get("unrelated_key") == 42


# ── _interp_on_sigma_knots ──

from spline_nonlinear_alpha import (
    _interp_on_sigma_knots,
    _lbfgsb_exit_kind,
    _NLJointObjective,
    _cfg_get_first,
    nonlinear_alpha_lbfgs_maxfun_per_step_from_views,
    nonlinear_alpha_second_pass_maxfun_effective_from_views,
)


def test_interp_on_sigma_knots_basic() -> None:
    lam = np.linspace(400.0, 1000.0, 50)
    y = np.sin(lam / 100)
    sk = canonical_spline_sigma_knots(400, 1000)
    result = _interp_on_sigma_knots(lam, y, sk)
    assert result.shape == sk.shape
    assert np.all(np.isfinite(result))


def test_interp_on_sigma_knots_empty() -> None:
    result = _interp_on_sigma_knots(np.array([]), np.array([]), np.array([0.001, 0.002]))
    assert result.size == 0


# ── _lbfgsb_exit_kind ──


def test_lbfgsb_exit_kind_maxfun() -> None:
    assert _lbfgsb_exit_kind(False, "TOTAL NO. OF F AND G") == "budget_maxfun"


def test_lbfgsb_exit_kind_converged() -> None:
    assert _lbfgsb_exit_kind(True, "CONVERGED") == "converged"


def test_lbfgsb_exit_kind_other() -> None:
    assert _lbfgsb_exit_kind(False, "some random error") == "other_error"


# ── _cfg_get_first ──


def test_cfg_get_first_finds_first_match() -> None:
    ns = SimpleNamespace(a=10, b=20)
    assert _cfg_get_first(ns, "a", "b", default=0) == 10


def test_cfg_get_first_falls_to_default() -> None:
    ns = SimpleNamespace()
    assert _cfg_get_first(ns, "missing", default=42) == 42


# ── _NLJointObjective ──

from spline_objective import build_spline_objective_masked_grid


def test_nl_joint_objective_call() -> None:
    lam = np.linspace(400.0, 1000.0, 50)
    cfg = _nl_cfg_min(lam)
    sk = canonical_spline_sigma_knots(400.0, 1000.0)
    k = int(sk.size)

    grid = build_spline_objective_masked_grid(cfg)
    assert grid is not None
    lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = grid

    obj = _NLJointObjective(
        cfg, sk, lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f,
        "smooth", None,
        alpha_sigma_prior=0.0015,
        alpha_prior_weight=1.0,
    )

    x0 = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    z = np.concatenate(([1.0], x0))
    cost = obj(z)
    assert np.isfinite(cost)
    assert cost >= 0


def test_nl_joint_objective_unpack() -> None:
    lam = np.linspace(400.0, 1000.0, 50)
    cfg = _nl_cfg_min(lam)
    sk = canonical_spline_sigma_knots(400.0, 1000.0)
    k = int(sk.size)

    grid = build_spline_objective_masked_grid(cfg)
    lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = grid

    obj = _NLJointObjective(
        cfg, sk, lam_f, sig_f, n_sub_f, w, inv_npix, t_exp_f, r_exp_f,
        "smooth", None,
        alpha_sigma_prior=0.0015,
        alpha_prior_weight=1.0,
    )

    x0 = np.concatenate(([200.0], np.full(k, 2.0), np.full(k, np.log(1e-3))))
    z = np.concatenate(([1.002], x0))
    alpha, x_part = obj.unpack(z)
    assert abs(alpha - 1.002) < 1e-9
    assert x_part.size == x0.size


# ── view-based functions ──


def test_lbfgs_maxfun_per_step_from_views() -> None:
    from certus_index_spline_core import SplineNonlinearAlphaConfig, SplinePGlobalConfig
    alpha_v = SplineNonlinearAlphaConfig(nonlinear_alpha_budget_mode="slow")
    pg_v = SplinePGlobalConfig(polish_maxfun=5000)
    mf, mode = nonlinear_alpha_lbfgs_maxfun_per_step_from_views(alpha_v, pg_v)
    assert mode == "slow"
    assert mf >= 800


def test_second_pass_maxfun_effective_from_views() -> None:
    from certus_index_spline_core import SplineNonlinearAlphaConfig, SplinePGlobalConfig
    alpha_v = SplineNonlinearAlphaConfig()
    pg_v = SplinePGlobalConfig(polish_maxfun=5000)
    mf = nonlinear_alpha_second_pass_maxfun_effective_from_views(alpha_v, pg_v, 500)
    assert mf >= 5000


# ── _pick_nl_start_x_and_mode: edge cases ──


def test_pick_nl_start_x_returns_none_for_tiny_lam() -> None:
    lam = np.array([400.0])  # < 2 points
    cfg = _nl_cfg_min(np.linspace(400, 1000, 20))
    cfg2 = cfg.replace(lam_nm=lam)
    assert _pick_nl_start_x_and_mode(cfg2, {}) is None


def test_pick_nl_start_x_returns_none_missing_data() -> None:
    lam = np.linspace(400, 1000, 20)
    cfg = _nl_cfg_min(lam)
    out = {"sigma_knots": np.array([0.001, 0.002])}
    assert _pick_nl_start_x_and_mode(cfg, out) is None


