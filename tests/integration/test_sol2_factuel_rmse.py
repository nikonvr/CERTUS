"""Cohérence RMSE « Keep » Smart Init vs 1er coût SOL2 ; contraste smooth/PWL (diagnostic saut dialogue/worker)."""


from __future__ import annotations





import numpy as np


import pytest


from certus_physics import clip_to_bounds





from certus_index_spline_core import (


    DataType,


    SplineOptConfig,


    bridge_sigma_knots_preserve_manual,


    build_sigma_knots,


    canonical_spline_sigma_knots,


    make_bounds_and_x0,


    rmse_at_spline_stage_x0_init,


    SPLINE_PWL_N_SEG,


)


from spline_objective import SplinePWLObjective, decompose_spline_pwl_objective


from spline_smart_init import interp_n_L_pwlnk_to_sigmas








def test_rmse_keep_worker_mesh_matches_sol2_first_cost_ir_extended() -> None:


    """K dialogue = 12 (base fichier) -> bridge K=14 si lambda_max > seuil IR : même RMSE que ``obj(x0 clip)``."""


    lam = np.linspace(350.0, 5200.0, 160, dtype=np.float64)


    n_sub = np.full_like(lam, 1.52)


    t_exp = 0.55 * np.ones_like(lam)


    lam_min, lam_max = float(lam.min()), float(lam.max())


    sk12 = build_sigma_knots(lam_min, lam_max, SPLINE_PWL_N_SEG)


    sk_worker = bridge_sigma_knots_preserve_manual(sk12, lam_min, lam_max, rmse_fit_lambda_nm=None)


    assert int(sk_worker.size) >= 12





    k12 = int(sk12.size)


    rng = np.random.default_rng(42)


    ne = 1.65 + 0.02 * rng.standard_normal(k12)


    Le = -4.2 + 0.1 * rng.standard_normal(k12)


    d_manual = 1750.0





    ne_w, Le_w = interp_n_L_pwlnk_to_sigmas(sk12, ne, Le, sk_worker)





    cfg_rmse = SplineOptConfig(


        lam_nm=lam,


        t_exp=t_exp,


        r_exp=None,


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=int(sk_worker.size) - 1,


        d_lo=500.0,


        d_hi=4000.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        nk_profile_interp="pwl",


    )


    m_gui, rm_gui = rmse_at_spline_stage_x0_init(


        cfg_rmse, sk_worker, ne_w, Le_w, float(d_manual), relax_n_mono=False


    )





    cfg_stage = SplineOptConfig(


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


        nk_profile_interp="pwl",


        smart_preview_exact_sigma_knots=sk12.copy(),


        smart_preview_exact_n_L=(ne.copy(), Le.copy()),


        smart_preview_d_nm_override=float(d_manual),


        smart_preview_accepted_rmse=float(rm_gui),


    )


    bounds, x0, sk_out = make_bounds_and_x0(cfg_stage)


    assert int(sk_out.size) == int(sk_worker.size)


    assert np.allclose(np.sort(sk_out), np.sort(sk_worker))


    x0_init = clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), bounds[:, 0], bounds[:, 1])


    m_stage = float(SplinePWLObjective(cfg_stage, sk_out)(x0_init))





    assert abs(m_gui - m_stage) < 1e-8


    assert abs(float(np.sqrt(max(m_gui, 0.0))) - float(np.sqrt(max(m_stage, 0.0)))) < 1e-8








@pytest.mark.parametrize("nk_mode", ["pwl", "smooth"])


def test_decompose_tot_matches_objective_call(nk_mode: str) -> None:


    """``decompose_spline_pwl_objective`` total = ``SplinePWLObjective`` (même cfg, x, sk)."""


    lam = np.linspace(400.0, 2400.0, 80, dtype=np.float64)


    n_sub = np.full_like(lam, 1.52)


    t_exp = 0.5 * np.ones_like(lam)


    lam_min, lam_max = float(lam.min()), float(lam.max())


    sk = canonical_spline_sigma_knots(lam_min, lam_max)


    k = int(sk.size)


    ne = np.full(k, 1.65)


    Le = np.full(k, -4.0)





    cfg = SplineOptConfig(


        lam_nm=lam,


        t_exp=t_exp,


        r_exp=None,


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=k - 1,


        d_lo=100.0,


        d_hi=5000.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        nk_profile_interp=nk_mode,


    )


    bounds, x0, _ = make_bounds_and_x0(


        SplineOptConfig(


            lam_nm=lam,


            t_exp=t_exp,


            r_exp=None,


            n_sub=n_sub,


            data_type=DataType.TRANSMISSION,


            n_seg=k - 1,


            d_lo=100.0,


            d_hi=5000.0,


            weight_t=1.0,


            weight_r=0.0,


            substrate_name="Test",


            t_is_ratio=False,


            nk_profile_interp=nk_mode,


            smart_preview_exact_sigma_knots=sk.copy(),


            smart_preview_exact_n_L=(ne.copy(), Le.copy()),


            smart_preview_d_nm_override=1200.0,


        )


    )


    x0c = clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), bounds[:, 0], bounds[:, 1])


    obj = SplinePWLObjective(cfg, sk)


    m_obj = float(obj(x0c))


    _msp, _pen, tot = decompose_spline_pwl_objective(cfg, sk, x0c)


    assert abs(m_obj - float(tot)) < 1e-7








def test_smooth_profile_can_raise_rmse_vs_pwl_same_nodes() -> None:


    """Avec K>=4, le profil cubique diffère de la PWL : les deux RMSE sur le même x ne sont pas forcément égales."""


    lam = np.linspace(350.0, 5200.0, 160, dtype=np.float64)


    n_sub = np.full_like(lam, 1.52)


    t_exp = 0.55 * np.ones_like(lam)


    lam_min, lam_max = float(lam.min()), float(lam.max())


    sk = canonical_spline_sigma_knots(lam_min, lam_max)


    k = int(sk.size)


    rng = np.random.default_rng(7)


    ne = 1.65 + 0.03 * rng.standard_normal(k)


    Le = -4.2 + 0.15 * rng.standard_normal(k)





    from dataclasses import replace





    cfg_base = SplineOptConfig(


        lam_nm=lam,


        t_exp=t_exp,


        r_exp=None,


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=k - 1,


        d_lo=500.0,


        d_hi=4000.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        nk_profile_interp="smooth",


    )


    bounds, x0, _ = make_bounds_and_x0(


        SplineOptConfig(


            lam_nm=lam,


            t_exp=t_exp,


            r_exp=None,


            n_sub=n_sub,


            data_type=DataType.TRANSMISSION,


            n_seg=k - 1,


            d_lo=500.0,


            d_hi=4000.0,


            weight_t=1.0,


            weight_r=0.0,


            substrate_name="Test",


            t_is_ratio=False,


            nk_profile_interp="smooth",


            smart_preview_exact_sigma_knots=sk.copy(),


            smart_preview_exact_n_L=(ne.copy(), Le.copy()),


            smart_preview_d_nm_override=1750.0,


        )


    )


    x0c = clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), bounds[:, 0], bounds[:, 1])


    _, _, tot_s = decompose_spline_pwl_objective(cfg_base, sk, x0c)


    _, _, tot_p = decompose_spline_pwl_objective(cfg_base.replace(nk_profile_interp="pwl"), sk, x0c)


    assert tot_s > 0 and tot_p > 0


    rel = abs(float(tot_s) - float(tot_p)) / max(float(tot_p), 1e-30)


    assert rel > 1e-6, "attendu : smooth vs pwl diffèrent sur ce tirage aléatoire"


