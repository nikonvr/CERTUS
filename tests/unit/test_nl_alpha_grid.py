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

