"""After manual Smart Init (exact sigma + d), x0_warm must not overwrite thickness or n, L.



Spectra here stay in 400-800 nm: ``canonical_spline_sigma_knots`` returns K=12 (no IR extension),

so ``SPLINE_PWL_K_NODES`` and ``sk_out`` size coincide.

"""

from __future__ import annotations



import numpy as np

from certus_physics import clip_to_bounds

from certus_index_utils import _transmittance_absolute_from_nk



from certus_index_spline_core import (

    SPLINE_PWL_K_NODES,

    SPLINE_PWL_N_SEG,

    DataType,

    SplineOptConfig,

    bridge_sigma_knots_preserve_manual,

    build_sigma_knots,

    canonical_spline_sigma_knots,

    make_bounds_and_x0,

    rmse_at_spline_stage_x0_init,

)

from spline_objective import SplinePWLObjective

from spline_smart_init import (

    _build_smart_preview_grids,

    interp_n_L_pwlnk_to_sigmas,

    recalc_smart_init_spectral_preview,

)





def test_sk_exact_d_not_overwritten_by_x0_warm() -> None:

    lam = np.linspace(400.0, 800.0, 40)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.55 * np.ones_like(lam)

    k = 5

    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)

    ne = np.full(k, 1.65, dtype=np.float64)

    Le = np.full(k, -4.2, dtype=np.float64)

    d_manual = 2959.656987638



    warm = np.zeros(1 + 2 * k, dtype=np.float64)

    warm[0] = 999.0

    warm[1 : 1 + k] = 2.0

    warm[1 + k :] = -2.0



    cfg = SplineOptConfig(

        lam_nm=lam,

        t_exp=t_exp,

        r_exp=None,

        n_sub=n_sub,

        data_type=DataType.TRANSMISSION,

        n_seg=SPLINE_PWL_N_SEG,

        d_lo=500.0,

        d_hi=4000.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

        x0_warm=warm,

        smart_preview_exact_sigma_knots=sk.copy(),

        smart_preview_exact_n_L=(ne.copy(), Le.copy()),

        smart_preview_d_nm_override=float(d_manual),

    )

    _bounds, x0, sk_out = make_bounds_and_x0(cfg)

    assert int(np.asarray(sk_out).size) == SPLINE_PWL_K_NODES

    sk_bridge = bridge_sigma_knots_preserve_manual(

        sk,

        float(lam.min()),

        float(lam.max()),

        rmse_fit_lambda_nm=None,

    )

    assert np.allclose(sk_out, sk_bridge)

    o = np.argsort(sk)

    ne_i = np.interp(

        sk_out, sk[o], ne[o], left=float(ne[o[0]]), right=float(ne[o[-1]])

    )

    Le_i = np.interp(

        sk_out, sk[o], Le[o], left=float(Le[o[0]]), right=float(Le[o[-1]])

    )

    k_fix = SPLINE_PWL_K_NODES

    assert abs(float(x0[0]) - d_manual) < 1e-6, (x0[0], d_manual)

    assert not np.isclose(float(x0[0]), 999.0)

    assert np.allclose(x0[1 : 1 + k_fix], ne_i)

    assert np.allclose(x0[1 + k_fix : 1 + 2 * k_fix], Le_i)





def test_x0_warm_still_used_without_smart_init() -> None:

    lam = np.linspace(400.0, 800.0, 20)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.5 * np.ones_like(lam)

    k = SPLINE_PWL_K_NODES

    warm = np.zeros(1 + 2 * k, dtype=np.float64)

    warm[0] = 2500.0

    warm[1 : 1 + k] = 1.7

    warm[1 + k :] = -5.0



    cfg = SplineOptConfig(

        lam_nm=lam,

        t_exp=t_exp,

        r_exp=None,

        n_sub=n_sub,

        data_type=DataType.TRANSMISSION,

        n_seg=SPLINE_PWL_N_SEG,

        d_lo=100.0,

        d_hi=5000.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

        x0_warm=warm,

        sigma_knots_override=np.linspace(1 / 800, 1 / 400, 4),

    )

    _bounds, x0, _sk = make_bounds_and_x0(cfg)

    assert abs(float(x0[0]) - 2500.0) < 1e-9





def test_rmse_smart_init_matches_stage_first_cost() -> None:

    """Same MSE as the 1st obj(x0_init) of the stage for an identical Smart Init config."""

    lam = np.linspace(400.0, 800.0, 40)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.55 * np.ones_like(lam)

    k = 5

    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)

    ne = np.full(k, 1.65, dtype=np.float64)

    Le = np.full(k, -4.2, dtype=np.float64)

    d_manual = 2959.656987638



    def _mk() -> SplineOptConfig:

        return SplineOptConfig(

            lam_nm=lam,

            t_exp=t_exp,

            r_exp=None,

            n_sub=n_sub,

            data_type=DataType.TRANSMISSION,

            n_seg=SPLINE_PWL_N_SEG,

            d_lo=500.0,

            d_hi=4000.0,

            weight_t=1.0,

            weight_r=0.0,

            substrate_name="Test",

            t_is_ratio=False,

            smart_preview_exact_sigma_knots=sk.copy(),

            smart_preview_exact_n_L=(ne.copy(), Le.copy()),

            smart_preview_d_nm_override=float(d_manual),

        )



    cfg_rmse = _mk()

    cfg_stage = _mk()

    sk_canon = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))

    o = np.argsort(sk)

    ne_i = np.interp(

        sk_canon, sk[o], ne[o], left=float(ne[o[0]]), right=float(ne[o[-1]])

    )

    Le_i = np.interp(

        sk_canon, sk[o], Le[o], left=float(Le[o[0]]), right=float(Le[o[-1]])

    )

    m_prev, _ = rmse_at_spline_stage_x0_init(

        cfg_rmse, sk_canon, ne_i, Le_i, float(d_manual)

    )

    bounds, x0, sk_o = make_bounds_and_x0(cfg_stage)

    x0_init = clip_to_bounds(

        np.asarray(x0, dtype=np.float64).copy(), bounds[:, 0], bounds[:, 1]

    )

    m_stage = float(SplinePWLObjective(cfg_stage, sk_o)(x0_init))

    assert abs(m_prev - m_stage) < 1e-9





def test_recalc_preview_preserves_thickness_when_d_nm_fixed() -> None:

    """GUI ``do_recalc`` behavior: with ``d_nm_fixed``, ``d_best_nm`` does not re-optimize thickness."""

    lam = np.linspace(400.0, 800.0, 40, dtype=np.float64)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.55 * np.ones_like(lam)

    cfg = SplineOptConfig(

        lam_nm=lam,

        t_exp=t_exp,

        r_exp=None,

        n_sub=n_sub,

        data_type=DataType.TRANSMISSION,

        n_seg=4,

        d_lo=500.0,

        d_hi=4000.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

    )

    grids = _build_smart_preview_grids(cfg)

    assert grids is not None

    k = 5

    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)

    ne = np.full(k, 1.65, dtype=np.float64)

    Le = np.full(k, -4.2, dtype=np.float64)

    d_manual = 2222.875

    out = recalc_smart_init_spectral_preview(

        cfg, sk, ne, Le, grids, d_nm_fixed=float(d_manual), relax_n_mono=False

    )

    assert out is not None

    d_clip = float(np.clip(float(d_manual), float(cfg.d_lo), float(cfg.d_hi)))

    assert abs(float(out["d_best_nm"]) - d_clip) < 1e-9





def test_smart_init_sweep_starts_from_current_thickness() -> None:

    """The auto node sweep uses ``d_nm_current`` as RMSE reference and start point for ``d``."""

    lam = np.linspace(400.0, 800.0, 40, dtype=np.float64)

    n_sub = np.full_like(lam, 1.52)

    t_exp = 0.55 * np.ones_like(lam)

    cfg = SplineOptConfig(

        lam_nm=lam,

        t_exp=t_exp,

        r_exp=None,

        n_sub=n_sub,

        data_type=DataType.TRANSMISSION,

        n_seg=4,

        d_lo=500.0,

        d_hi=4000.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

    )

    k = 5

    sk = np.linspace(1.0 / 800.0, 1.0 / 400.0, k, dtype=np.float64)

    ne = np.full(k, 1.65, dtype=np.float64)

    Le = np.full(k, -4.2, dtype=np.float64)

    d0 = 2800.0

    from spline_smart_init import smart_init_sweep_node_thickness_rmse



    out = smart_init_sweep_node_thickness_rmse(

        cfg,

        sk,

        ne,

        Le,

        row=2,

        is_ln_k=False,

        d_lo=float(cfg.d_lo),

        d_hi=float(cfg.d_hi),

        L_lo=-20.0,

        L_hi=2.0,

        time_budget_s=0.15,

        grid_d=8,

        grid_param=8,

        d_nm_current=float(d0),

        relax_n_mono=False,

    )

    assert np.isfinite(float(out["d_nm"]))

    assert float(cfg.d_lo) <= float(out["d_nm"]) <= float(cfg.d_hi)





def test_bridge_mesh_reduces_manual_to_worker_rmse_jump_with_ir_extension() -> None:

    """When K must go from 12 to 14 (IR), the 'preserve then add' bridge must limit RMSE degradation."""

    lam = np.linspace(350.0, 5199.88, 900, dtype=np.float64)

    n_sub = np.full_like(lam, 1.52)

    d0 = 3000.0



    lam_lo = float(lam.min())

    lam_hi = float(lam.max())

    # K=12 base mesh (log sigma uniform), same as canonical before IR extension - not an obsolete manual grid.

    sk_src = np.asarray(

        build_sigma_knots(lam_lo, lam_hi, SPLINE_PWL_N_SEG), dtype=np.float64

    ).ravel()

    k_src = int(sk_src.size)

    n_src = np.linspace(2.13, 2.72, k_src, dtype=np.float64)

    L_src = np.linspace(-10.2, -4.0, k_src, dtype=np.float64)

    x_src = np.concatenate(([d0], n_src, L_src))



    # Génère une cible parfaitement cohérente avec le modèle source.

    from spline_objective import nk_from_x_pwlnk

    n_l, k_l = nk_from_x_pwlnk(

        x_src, lam, sk_src, 1e-30, 10.0, n_mono_band_nm=None, profile_interp="pwl"

    )

    t_exp = _transmittance_absolute_from_nk(lam, n_l, k_l, float(d0), n_sub)



    cfg = SplineOptConfig(

        lam_nm=lam,

        t_exp=t_exp,

        r_exp=None,

        n_sub=n_sub,

        data_type=DataType.TRANSMISSION,

        n_seg=13,  # worker K=14

        d_lo=2800.0,

        d_hi=3200.0,

        weight_t=1.0,

        weight_r=0.0,

        substrate_name="Test",

        t_is_ratio=False,

        rmse_fit_lambda_nm=(350.0, 5000.0),

        spline_min_delta_lambda_over_lambda_mean=0.0,

    )



    # Preview reference (K=12).

    _m_src, rm_src = rmse_at_spline_stage_x0_init(cfg, sk_src, n_src, L_src, d0, relax_n_mono=False)



    # Old path: complete canonical remesh.

    sk_old = canonical_spline_sigma_knots(lam_lo, lam_hi)

    n_old, L_old = interp_n_L_pwlnk_to_sigmas(sk_src, n_src, L_src, sk_old)

    _m_old, rm_old = rmse_at_spline_stage_x0_init(cfg, sk_old, n_old, L_old, d0, relax_n_mono=False)



    # New path: preservation of manual nodes + addition.

    sk_new = bridge_sigma_knots_preserve_manual(

        sk_src,

        lam_lo,

        lam_hi,

        rmse_fit_lambda_nm=(350.0, 5000.0),

    )

    n_new, L_new = interp_n_L_pwlnk_to_sigmas(sk_src, n_src, L_src, sk_new)

    _m_new, rm_new = rmse_at_spline_stage_x0_init(cfg, sk_new, n_new, L_new, d0, relax_n_mono=False)



    assert int(sk_old.size) == int(sk_new.size) == 14

    assert rm_new <= rm_old + 1e-12

    # Relative preview->worker jump is significantly reduced.

    assert (rm_new / max(rm_src, 1e-12)) <= (rm_old / max(rm_src, 1e-12))





def test_interp_n_L_pwlnk_snaps_exact_sigma_no_float_drift() -> None:

    """Target sigma equal to a source node take back n and L **bit-exact** (no floating interpolation)."""

    sk = np.array([0.003, 0.002], dtype=np.float64)

    n = np.array([2.2, 2.1], dtype=np.float64)

    L = np.array([-6.0, -5.0], dtype=np.float64)

    tgt = np.array([0.0018, 0.002, 0.0026, 0.0032], dtype=np.float64)

    n2, L2 = interp_n_L_pwlnk_to_sigmas(sk, n, L, tgt)

    assert n2[1] == 2.1 and L2[1] == -5.0





