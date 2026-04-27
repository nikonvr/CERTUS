"""Tests pour certus_re_worker_utils (sans Qt)."""



from types import SimpleNamespace



import numpy as np

import pytest



from certus_re_helpers import _parse_re_rmse_combined_from_progress_message

from certus_re_worker_utils import (

    RE_CORREC_NOMINAL_PCT,

    REResultsBuilder,

    p2_result_to_correc_tuple,

    re_build_finished_payload_re,

    re_enrich_results_ranking_fields,

    re_finalize_ranking_log_suffix,

    re_result_dict_stop_before_first_trf,

    re_finalize_progress_message_done,

    re_finalize_finished_main_log_line,

    re_finalize_rmse_milestone_log_line,

    re_build_p2_progress_plan,

    re_interpolate_progress_segment,

    re_live_plot_wls_and_dispersion_nk,

    re_nominal_indices_at_wls,

    re_objective_wls_grid,

    re_objective_wls_weight_log_trap,

    re_oblique_config_meta_from_wls,

    re_phase1_trf_runs_multistart,

    re_progress_pct_p1,

    re_ranking_combined_rmse,

    re_trf_bounds_scipy_tuples,

    re_trf_thickness_bounds,

    resolve_re_qwot_alphas,

    shake_sigmas_adaptive,

)





def test_resolve_uniform_when_schedule_off():

    cfg = {"re_qwot_penalty_weight": 0.07, "re_qwot_per_phase_schedule": False}

    a1, a2a, a2b, a3 = resolve_re_qwot_alphas(cfg, 0.1, 0.2)

    assert a1 == a2a == a2b == a3 == 0.07





def test_resolve_per_phase_defaults():

    cfg = {"re_qwot_penalty_weight": 0.05, "re_qwot_per_phase_schedule": True}

    a1, a2a, a2b, a3 = resolve_re_qwot_alphas(cfg, 0.1, 0.2)

    assert a1 == pytest.approx(0.15)

    assert a2a == pytest.approx(0.10)

    assert a2b == pytest.approx(0.05)

    assert a3 == pytest.approx(0.02)





def test_p2_result_to_correc_tuple_sub3():

    r = {

        "re_dH_knots": [0.0, 0.01],

        "re_dL_knots": [0.0, -0.01],

        "re_spline_lam_node2_nm": 2000.0,

        "re_sub_cauchy_a0": 1.5,

        "re_sub_cauchy_a1": 0.0,

        "re_sub_cauchy_a2": 0.0,

    }

    t = p2_result_to_correc_tuple(r, True)

    assert t[0] == "spline_sub3"

    assert len(t) == 7





def test_p2_result_to_correc_tuple_spline_branch():

    r = {

        "re_dH_knots": [0.0, 0.02],

        "re_dL_knots": [0.0, -0.02],

        "re_spline_lam_node2_nm": 1800.0,

        "re_sub_cauchy_a0": 1.5,

        "re_sub_cauchy_a1": 0.0,

        "re_sub_cauchy_a2": 0.0,

    }

    t = p2_result_to_correc_tuple(r, False)

    assert t[0] == "spline"

    assert len(t) == 4

    np.testing.assert_array_equal(t[1], np.array([0.0, 0.02], dtype=np.float64))

    np.testing.assert_array_equal(t[2], np.array([0.0, -0.02], dtype=np.float64))

    assert t[3] == pytest.approx(1800.0)





def test_shake_sigmas_adaptive():

    ep, sp = shake_sigmas_adaptive(0.5, base_ep_sigma_pct=1.5, base_spl_sigma=0.01, ref_norm=1.0)

    assert ep > 0 and sp > 0





def test_shake_sigmas_adaptive_clips_to_scale_max():

    ep, sp = shake_sigmas_adaptive(

        1e-30,

        base_ep_sigma_pct=1.0,

        base_spl_sigma=0.1,

        ref_norm=1.0,

        scale_min=0.5,

        scale_max=2.5,

    )

    assert ep == pytest.approx(2.5)

    assert sp == pytest.approx(0.25)





def test_shake_sigmas_adaptive_clips_to_scale_min():

    ep, sp = shake_sigmas_adaptive(

        1e9,

        base_ep_sigma_pct=2.0,

        base_spl_sigma=0.2,

        ref_norm=1.0,

        scale_min=0.5,

        scale_max=2.5,

    )

    assert ep == pytest.approx(1.0)

    assert sp == pytest.approx(0.1)





def test_re_ranking_combined_rmse_is_monotonic():

    r1 = re_ranking_combined_rmse(0.2, 0.2, 0.1)

    r2 = re_ranking_combined_rmse(0.3, 0.2, 0.1)

    r3 = re_ranking_combined_rmse(0.3, 0.3, 0.1)

    assert r1 > 0.0

    assert r2 >= r1

    assert r3 >= r2





def test_re_enrich_results_ranking_fields_nominal_correc():

    def _raw(ep, cor):

        assert cor[0] == RE_CORREC_NOMINAL_PCT[0]

        return 0.05



    results = [{"ep": [100.0], "rmse": 0.2}]

    re_enrich_results_ranking_fields(

        results, alpha_rank_ref=0.1, compute_qwot_rmse_raw=_raw

    )

    assert results[0]["re_rmse_qwot_raw"] == 0.05

    assert results[0]["re_ranking_alpha_ref"] == 0.1

    assert results[0]["re_ranking_score"] == pytest.approx(

        re_ranking_combined_rmse(0.2, 0.05, 0.1)

    )





def test_re_finalize_ranking_log_suffix_empty_without_score():

    assert re_finalize_ranking_log_suffix({"rmse": 0.1}, 0.5) == ""





def test_re_finalize_ranking_log_suffix_nonempty():

    s = re_finalize_ranking_log_suffix(

        {

            "re_ranking_score": 0.3,

            "re_ranking_alpha_ref": 0.1,

            "re_rmse_qwot_raw": 0.05,

        },

        0.99,

    )

    assert "0.300000" in s

    assert "QWOT_raw=0.050000" in s





def test_re_finalize_finished_main_and_milestone_log_lines():

    main = re_finalize_finished_main_log_line(

        1.25, 0.1, 0.2, 0.15, " | RMSE=0.300000 (classement, _ref=0.1, QWOT_raw=0.050000)", 3

    )

    assert "REWorker: finished in 1.25s" in main

    assert "(3 run(s))." in main

    ms = re_finalize_rmse_milestone_log_line([0.5], [0.4], [0.35])

    assert "initial0.500000" in ms and "after thickness0.400000" in ms and "final=0.350000" in ms





def test_re_finalize_progress_message_done():

    s_stop = re_finalize_progress_message_done(

        stopped_by_user=True,

        elapsed_s=99.0,

        best_sp=0.1,

        best_ot=0.2,

        best_combined=0.15,

    )

    assert "RE stopped" in s_stop and "RMSE_sp=0.10000" in s_stop

    s_fin = re_finalize_progress_message_done(

        stopped_by_user=False,

        elapsed_s=12.3,

        best_sp=0.1,

        best_ot=0.2,

        best_combined=0.15,

    )

    assert "RE finished in 12.3s" in s_fin and "RMSE_sp=0.10000" in s_fin





def test_re_result_dict_stop_before_first_trf():

    ep = np.array([10.0, 20.0], dtype=np.float64)

    d = re_result_dict_stop_before_first_trf(

        ep,

        rmse_initial_sp=0.1,

        rmse_initial_q=0.2,

        rmse_initial_u=0.15,

    )

    assert d["label"] == "initial (stop before first TRF iter)"

    assert d["nfev"] == 0 and d["success"] is False

    np.testing.assert_array_equal(d["ep"], ep)

    assert d["rmse"] == pytest.approx(0.1)

    assert d["rmse_qwot"] == pytest.approx(0.2)

    assert d["rmse_combined"] == pytest.approx(0.15)





def test_re_build_finished_payload_re():

    ep0 = np.array([1.0, 2.0], dtype=np.float64)

    p = re_build_finished_payload_re(

        [{"rmse": 0.1, "re_ranking_score": 0.2}],

        ep0,

        [0.3],

        [0.25],

        [0.2],

        stopped_by_user=True,

        re_qwot_alphas=(0.15, 0.1, 0.05, 0.02),

    )

    assert p["ok"] is True

    assert p["re_stopped_by_user"] is True

    assert p["re_ranking_score"] == 0.2

    assert p["re_rmse_initial"] == pytest.approx(0.3)

    assert p["re_qwot_alpha_phase2b"] == pytest.approx(0.05)

    assert len(p["re_qwot_alphas"]) == 4

    p2 = re_build_finished_payload_re([], ep0, [1.0], [2.0], [3.0])

    assert p2["re_ranking_score"] is None

    assert "re_stopped_by_user" not in p2

    assert "re_qwot_alpha_phase2b" not in p2





def test_re_results_builder_matches_function_contract():

    ep0 = np.array([1.0, 2.0], dtype=np.float64)

    p = REResultsBuilder.build_finished_payload(

        results=[{"rmse": 0.1, "re_ranking_score": 0.2}],

        ep0=ep0,

        rmse_initial_milestone=[0.3],

        rmse_phase1_milestone=[0.25],

        rmse_final_milestone=[0.2],

        stopped_by_user=False,

        re_qwot_alphas=(0.15, 0.1, 0.05, 0.02),

    )

    assert p["ok"] is True

    assert p["re_ranking_score"] == pytest.approx(0.2)

    err = REResultsBuilder.build_error_payload(ep0.tolist())

    assert err == {"ok": False, "results": [], "ep0": [1.0, 2.0]}





def test_parse_re_rmse_combined_facade_patterns():

    assert _parse_re_rmse_combined_from_progress_message(

        "RE [DE->TRF] TRF iter ~3  RMSE_facade=0.012345 | TRF_RMS(r)=0.1"

    ) == pytest.approx(0.012345)

    assert _parse_re_rmse_combined_from_progress_message(

        "RE [phase 2b] TRF it ~5  RMSE_facade(curr)=0.02 | RMSE_facade(best)=0.019"

    ) == pytest.approx(0.02)





def test_re_enrich_results_ranking_fields_spline_sub3_correc():

    r = {

        "ep": [50.0],

        "rmse": 0.15,

        "re_dH_knots": [0.0, 0.01],

        "re_dL_knots": [0.0, -0.01],

        "re_spline_lam_node2_nm": 2000.0,

        "re_sub_cauchy_a0": 1.5,

        "re_sub_cauchy_a1": 0.0,

        "re_sub_cauchy_a2": 0.0,

    }

    seen = {}



    def _raw(ep, cor):

        seen["cor"] = cor[0]

        return 0.03



    re_enrich_results_ranking_fields(

        [r], alpha_rank_ref=0.2, compute_qwot_rmse_raw=_raw

    )

    assert seen["cor"] == "spline_sub3"

    assert r["re_ranking_score"] == pytest.approx(

        re_ranking_combined_rmse(0.15, 0.03, 0.2)

    )





def test_re_correc_nominal_pct_tuple():

    assert RE_CORREC_NOMINAL_PCT[0] == "pct"

    assert RE_CORREC_NOMINAL_PCT[1:] == (0.0, 0.0, 0.0)





def test_helpers_objective_variance_fractions_comb_matches_ranking():

    import certus_re_helpers as h



    for sp, qw, a in [(0.1, 0.2, 0.5), (1.0, 0.0, 0.3), (0.05, 0.05, 0.1)]:

        _f1, _f2, comb = h._re_objective_variance_fractions(sp, qw, a)

        assert comb == pytest.approx(re_ranking_combined_rmse(sp, qw, a))





def test_helpers_combined_rmse_matches_ranking():

    import certus_re_helpers as h



    for sp, qw, a in [

        (0.1, 0.2, 0.5),

        (1.0, 0.0, 0.3),

        (0.0, 0.5, 1.0),

        (-0.1, 0.2, 0.5),

    ]:

        r1 = re_ranking_combined_rmse(sp, qw, a)

        r2 = h._re_rmse_combined_spectral_qwot(sp, qw, a)

        assert r1 == pytest.approx(r2)





def test_re_objective_wls_weight_log_trap():

    wls = np.array([1.0, 4.0, 100.0])

    w = re_objective_wls_weight_log_trap(wls)

    # Weights for [1, 4, 100] using spectral_rmse_weights (trapezoidal ln lambda)

    assert w[0] == pytest.approx(0.60205999, rel=1e-5)

    assert w[1] == pytest.approx(1.0, rel=1e-5)

    assert w[2] == pytest.approx(1.3979400, rel=1e-5)

    w2 = re_objective_wls_weight_log_trap(np.array([0.25]))

    assert w2[0] == pytest.approx(1.0)





def test_re_objective_wls_grid_uses_target_centers_when_on():

    cfg = {"wls_min": 400.0, "wls_max": 800.0}

    tg = [

        SimpleNamespace(

            on=True,

            lmin=400.0,

            lmax=600.0,

            angle=0.0,

            pol="s",

            include_backside=False,

            target_type="T",

            tmin=0.0,

            tmax=1.0,

            w=1.0,

        ),

    ]

    wls, wmin, wmax = re_objective_wls_grid(cfg, tg)

    assert wmin == 400.0 and wmax == 800.0

    assert wls.size == 1

    assert float(wls[0]) == pytest.approx(500.0)





def test_re_objective_wls_grid_dense_when_no_active_targets():

    cfg = {"wls_min": 1000.0, "wls_max": 5200.0}

    tg = [SimpleNamespace(on=False, lmin=400.0, lmax=800.0)]

    wls, _, _ = re_objective_wls_grid(cfg, tg)

    assert wls.size >= 500





def test_re_oblique_config_meta_buckets():

    wls = np.array([400.0, 500.0, 600.0], dtype=np.float64)

    tg = [

        SimpleNamespace(

            on=True,

            lmin=400.0,

            lmax=500.0,

            angle=30.0,

            pol="p",

            include_backside=True,

            target_type="R",

            tmin=0.1,

            tmax=0.3,

            w=2.0,

        ),

    ]

    meta = re_oblique_config_meta_from_wls(wls, tg)

    assert len(meta) == 1

    assert meta[0]["angle"] == 30.0

    assert len(meta[0]["buckets"]) >= 1





def test_re_interpolate_progress_segment_endpoints():

    pl = {"a": 10.0, "b": 20.0}

    v0 = re_interpolate_progress_segment(pl, 0.0, 2.0, "a", "b", 0.0)

    v1 = re_interpolate_progress_segment(pl, 1.0, 2.0, "a", "b", 1.0)

    assert 10.0 <= v0 <= 20.0

    assert 10.0 <= v1 <= 20.0





def test_re_build_p2_progress_plan_keys():

    d = re_build_p2_progress_plan(

        3,

        re_top_k_cfg=2,

        re_p_setup=1.5,

        re_p_p1=27.5,

        re_n_sh_cfg=4,

        re_do_2a_cfg=True,

    )

    assert set(d) >= {"tk", "p2a_lo", "p2b_hi", "p3_lo", "p3_hi"}

    assert d["tk"] == 2





def test_re_progress_pct_p1_first_run():

    v = re_progress_pct_p1(0, 0.0, re_p_setup=1.5, re_p_p1=27.5, n_sched=1)

    assert v == pytest.approx(1.5)





def test_re_phase1_trf_runs_multistart_single():

    ep = np.array([100.0, 50.0])

    lb = np.array([90.0, 45.0])

    ub = np.array([110.0, 55.0])

    wt = np.ones(4, dtype=np.float64)

    runs = re_phase1_trf_runs_multistart(ep, wt, lb, ub, 1)

    assert len(runs) == 1

    assert runs[0][0] == "Deltalnlambda"

    np.testing.assert_array_equal(runs[0][1], wt)

    np.testing.assert_array_equal(runs[0][2], ep)





def test_re_phase1_trf_runs_multistart_lhs_stays_in_bounds():

    ep = np.array([100.0, 50.0])

    lb = np.array([90.0, 45.0])

    ub = np.array([110.0, 55.0])

    wt = np.ones(3, dtype=np.float64)

    runs = re_phase1_trf_runs_multistart(ep, wt, lb, ub, 5, lhs_seed=7)

    assert len(runs) == 5

    assert runs[1][0] == "Deltalnlambda (LHS #2)"

    for _lbl, wti, xv in runs:

        np.testing.assert_array_equal(wti, wt)

        assert np.all(xv >= lb - 1e-9) and np.all(xv <= ub + 1e-9)





def test_re_trf_bounds_scipy_tuples_matches_arrays():

    lb = np.array([1.0, 2.0])

    ub = np.array([3.0, 4.0])

    t = re_trf_bounds_scipy_tuples(lb, ub)

    assert t == [(1.0, 3.0), (2.0, 4.0)]





def test_re_trf_bounds_scipy_tuples_length_mismatch_raises():

    with pytest.raises(ValueError, match="same length"):

        re_trf_bounds_scipy_tuples(np.array([1.0]), np.array([2.0, 3.0]))





def test_re_trf_thickness_bounds_pm_10pct():

    ep = np.array([100.0, 50.0])

    lb, ub = re_trf_thickness_bounds(ep, 10.0)

    assert lb[0] == pytest.approx(90.0) and ub[0] == pytest.approx(110.0)

    assert lb[1] == pytest.approx(45.0) and ub[1] == pytest.approx(55.0)





def test_re_trf_thickness_bounds_clamps_lower_to_zero():

    # radius > 100 % -> (1 - pct) < 0 -> borne basse forcée à 0

    lb, ub = re_trf_thickness_bounds(np.array([10.0]), 150.0)

    assert lb[0] == pytest.approx(0.0)

    assert ub[0] == pytest.approx(25.0)





def test_re_live_plot_wls_and_dispersion_shapes():

    class _Mat:

        def get_nk(self, wls_arr):

            w = np.asarray(wls_arr)

            return np.ones(w.shape, dtype=np.complex128) * (1.5 + 0j)



    class _Lay:

        def __init__(self, m):

            self.mat = m



    mats = {"H": _Mat(), "Substrate": _Mat()}

    stack = [_Lay("H")]

    wls, n_sub, n_lay = re_live_plot_wls_and_dispersion_nk(

        mats, stack, 400.0, 800.0, n_points=50

    )

    assert wls.size == 50

    assert n_sub.shape[0] == 50

    assert n_lay.shape == (1, 50)





def test_re_nominal_indices_at_wls_shapes():

    class _Mat:

        def get_nk(self, wls_arr):

            n = np.ones(np.asarray(wls_arr).shape, dtype=np.complex128) * (1.52 + 0.1j)

            return n



    class _Lay:

        def __init__(self, name):

            self.mat = name



    mats = {"H": _Mat(), "L": _Mat(), "Substrate": _Mat()}

    stack = [_Lay("H"), _Lay("L")]

    wls = np.linspace(400.0, 800.0, 50)

    n_lay, n_sub, is_h, is_l, n_ref, _lref = re_nominal_indices_at_wls(

        mats, stack, wls, lambda_ref=550.0

    )

    assert n_lay.shape == (2, wls.size)

    assert n_sub.shape[0] == wls.size

    assert is_h.tolist() == [True, False]

    assert n_ref.size == 2





def test_resolve_re_qwot_alphas_adaptive_clamps():

    cfg = {

        "re_qwot_penalty_weight": 0.05,

        "re_qwot_per_phase_schedule": True,

        "re_qwot_adaptive_init_scale": True,

    }

    a1, a2a, a2b, a3 = resolve_re_qwot_alphas(cfg, rmse_sp_init=10.0, rmse_qwot_init=0.01)

    assert 0.02 <= a1 <= 0.5

    assert 0.02 <= a2a <= 0.5

    assert 0.01 <= a2b <= 0.5

    assert 0.005 <= a3 <= 0.3

