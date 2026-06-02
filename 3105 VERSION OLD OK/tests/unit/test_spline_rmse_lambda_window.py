"""Fenêtre spectrale optionnelle pour le masque objectif RMSE (INDEX SPLINE)."""

from __future__ import annotations



import numpy as np

import pytest



from certus.spline.certus_index_spline_core import (

    DataType,

    SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS,

    SplineOptConfig,

    N_MONO_BAND_HI_CAP_NM,

    apply_rmse_fit_window_nk_nan_to_result,

    export_spline_result_jsonable,

    nan_nk_outside_rmse_lambda_window,

    snapshot_result_with_rmse_fit_meta,

    default_n_mono_band_nm_from_spectrum,

)

from certus.spline.spline_objective import (

    _spline_objective_lam_mask,

    build_spline_objective_masked_grid,

    objective_lam_mask_on_target_grid,

    spline_objective_mse_on_masked_grid,

)





def _minimal_cfg(**kwargs) -> SplineOptConfig:

    lam = np.linspace(400.0, 800.0, 40, dtype=np.float64)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.55 * np.ones_like(lam)

    base = dict(

        lam_nm=lam,

        t_exp=t_exp,

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





def test_lam_mask_window_reduces_points() -> None:

    cfg_full = _minimal_cfg()

    cfg_win = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    n_full = int(np.count_nonzero(_spline_objective_lam_mask(cfg_full)))

    n_win = int(np.count_nonzero(_spline_objective_lam_mask(cfg_win)))

    assert n_full > n_win

    assert n_win >= SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS





def test_lam_mask_reversed_tuple_same_as_ordered() -> None:

    cfg_a = _minimal_cfg(rmse_fit_lambda_nm=(600.0, 500.0))

    cfg_b = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    assert np.array_equal(_spline_objective_lam_mask(cfg_a), _spline_objective_lam_mask(cfg_b))





def test_lam_mask_disjoint_band_empty() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(50.0, 100.0))

    assert int(np.count_nonzero(_spline_objective_lam_mask(cfg))) == 0





def test_objective_lam_mask_on_target_grid_same_as_source() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    lam = np.asarray(cfg.lam_nm, dtype=np.float64)

    m0 = _spline_objective_lam_mask(cfg)

    m1 = objective_lam_mask_on_target_grid(cfg, lam)

    assert np.array_equal(m0, m1)





def test_objective_lam_mask_on_target_grid_subgrid() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    lam_full = np.asarray(cfg.lam_nm, dtype=np.float64)

    lam_sub = lam_full[::3]

    m_sub = objective_lam_mask_on_target_grid(cfg, lam_sub)

    assert np.array_equal(m_sub, _spline_objective_lam_mask(cfg)[::3])





def test_export_jsonable_includes_rmse_fit_lambda() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 650.0))

    o = snapshot_result_with_rmse_fit_meta(

        cfg,

        {

            "lam_nm": np.asarray(cfg.lam_nm),

            "n_lam": np.ones(40),

            "k_lam": np.ones(40) * 1e-3,

            "rmse": 0.01,

            "mse": 1e-4,

        },

    )

    js = export_spline_result_jsonable(o, full_arrays=False)

    assert js.get("rmse_fit_lambda_nm") == [500.0, 650.0]





def test_build_masked_grid_matches_mask_count() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    mg = build_spline_objective_masked_grid(cfg)

    assert mg is not None

    lam_f, _, _, _, _, _, _ = mg

    assert lam_f.size == int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

    assert lam_f.size < np.asarray(cfg.lam_nm).size





def test_smart_init_preview_grid_same_lambda_and_weights_as_objective() -> None:

    """Grille lambda masquée + poids quadrature : identiques entre preview Smart Init et objectif spline."""

    from certus.spline.spline_smart_init import _build_smart_preview_grids



    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 700.0))

    pg = _build_smart_preview_grids(cfg)

    assert pg is not None

    mg = build_spline_objective_masked_grid(cfg)

    assert mg is not None

    lam_f_obj, _sig_f, _ns, w_obj, inv_obj, _, _ = mg

    lam_prev = np.asarray(pg["lam_f"], dtype=np.float64).ravel()

    assert np.array_equal(lam_prev, lam_f_obj)

    w_prev = np.asarray(pg["w_t"], dtype=np.float64).ravel()

    assert np.array_equal(w_prev, w_obj)

    assert float(pg["inv_npix"]) == float(inv_obj)





def test_spline_objective_mse_on_masked_grid_finite() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(500.0, 600.0))

    mg = build_spline_objective_masked_grid(cfg)

    assert mg is not None

    lam_f, _, n_sub_f, w, inv_npix, t_exp_f, r_exp_f = mg

    n_l = np.ones_like(lam_f) * 1.5

    k_l = np.ones_like(lam_f) * 1e-3

    m = spline_objective_mse_on_masked_grid(

        cfg,

        lam_f=lam_f,

        n_sub_f=n_sub_f,

        w=w,

        inv_npix=inv_npix,

        t_exp_f=t_exp_f,

        r_exp_f=r_exp_f,

        n_l=n_l,

        k_l=k_l,

        d=2000.0,

    )

    assert np.isfinite(m) and m < 1e30





def test_snapshot_result_sets_rmse_fit_lambda_key() -> None:

    cfg = _minimal_cfg(rmse_fit_lambda_nm=(510.0, 590.0))

    o = snapshot_result_with_rmse_fit_meta(

        cfg,

        {

            "lam_nm": np.asarray(cfg.lam_nm),

            "n_lam": np.ones(40),

            "k_lam": np.ones(40) * 1e-3,

            "rmse": 0.01,

        },

    )

    assert o.get("rmse_fit_lambda_nm") == (510.0, 590.0)





def test_nan_nk_outside_rmse_window() -> None:

    lam = np.linspace(400.0, 800.0, 9, dtype=np.float64)

    n_ = np.ones_like(lam) * 1.5

    k_ = np.ones_like(lam) * 1e-3

    n2, k2 = nan_nk_outside_rmse_lambda_window(lam, n_, k_, (500.0, 600.0))

    assert np.all(np.isfinite(n2[(lam >= 500) & (lam <= 600)]))

    assert np.all(np.isnan(n2[lam < 500]))

    assert np.all(np.isnan(n2[lam > 600]))

    assert np.all(np.isnan(k2[lam < 500]))





def test_apply_rmse_fit_window_nk_to_result_dict() -> None:

    lam = np.array([400.0, 500.0, 600.0])

    out = {

        "lam_nm": lam,

        "n_lam": np.ones(3) * 2.0,

        "k_lam": np.ones(3) * 1e-3,

        "corridor_reference_n_lam": np.array([1.9, 2.0, 2.1]),

        "corridor_reference_k_lam": np.array([1e-3, 2e-3, 3e-3]),

    }

    apply_rmse_fit_window_nk_nan_to_result(out, (480.0, 550.0))

    assert np.isfinite(out["n_lam"][1])

    assert np.isnan(out["n_lam"][0]) and np.isnan(out["n_lam"][2])

    assert np.isnan(out["corridor_reference_n_lam"][0]) and np.isnan(out["corridor_reference_n_lam"][2])

    assert np.isfinite(out["corridor_reference_n_lam"][1])

    assert np.isnan(out["corridor_reference_k_lam"][0]) and np.isfinite(out["corridor_reference_k_lam"][1])





def test_cfg_rmse_window_and_n_lambda_penalty_fields() -> None:

    lam = np.linspace(400.0, 800.0, 10)

    t_exp = np.ones_like(lam) * 0.5

    n_sub = np.full_like(lam, 1.5)

    cfg = _minimal_cfg(

        lam_nm=lam,

        t_exp=t_exp,

        n_sub=n_sub,

        rmse_fit_lambda_nm=(450.0, 700.0),

    )

    assert cfg.rmse_fit_lambda_nm == (450.0, 700.0)

    assert getattr(cfg, "n_lambda_rising_penalty_band_nm", None) is not None

    assert float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0) >= 0.0





def test_default_n_mono_band_caps_at_2000_and_follows_spectrum() -> None:

    lam_short = np.linspace(400.0, 1500.0, 20)

    b = default_n_mono_band_nm_from_spectrum(lam_short)

    assert b is not None

    assert b[0] == pytest.approx(400.0) and b[1] == pytest.approx(1500.0)

    lam_long = np.linspace(500.0, 8000.0, 50)

    b2 = default_n_mono_band_nm_from_spectrum(lam_long)

    assert b2 is not None

    assert b2[0] == pytest.approx(500.0) and b2[1] == pytest.approx(N_MONO_BAND_HI_CAP_NM)

    assert default_n_mono_band_nm_from_spectrum(np.array([2500.0, 3000.0])) is None

