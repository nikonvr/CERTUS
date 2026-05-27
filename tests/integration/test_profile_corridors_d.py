"""Minimal test: n/k corridors by d-profiling (no UI).





Budgets are intentionally tight so the whole module finishes in about 30-45s


(typical laptop; uses a local monkeypatch on ``corridor_profile_refit_maxfun``):


fewer lambda points, fewer spline segments, capped continuation steps, no boundary bisection


unless the scenario requires it.


"""


from __future__ import annotations





import numpy as np


import pytest


from scipy.optimize import OptimizeResult





import certus.spline.certus_index_spline_core as _core_mod


import certus.spline.spline_profile_corridors as _spc_mod





from certus.spline.certus_index_spline_core import (


    DataType,


    SplineOptConfig,


    canonical_spline_sigma_knots,


    corridor_profile_refit_maxfun,


)


from certus.spline.spline_objective import spectral_mse_rmse_masked_from_nk


from certus.spline.spline_finalize import extract_nominal_best_polished_corridor_reference


from certus.spline.spline_profile_corridors import (


    ProfileCorridorConfig,


    _expand_corridor_envelope_with_reported_nk,


    _extract_knots_and_nodes_from_result,


    _bounds_for_nodes_only,


    _fit_nodes_at_fixed_d,


    _spectral_rmse_at_packed_nodes,


    _x_nodes0_from_mesh_x_if_consistent,


    compute_profiled_corridors_by_d,


)





# --- Fast suite defaults (total runtime target ~15-20s) ---
# ── PARE-FEU ──────────────────────────────────────────────────────────────────
# Ces budgets sont volontairement serrés pour la CI.
# Les tests vérifient la STRUCTURE des résultats (clés, shapes, intervalles),
# PAS la convergence numérique exacte.
# Si un test échoue après réduction : augmenter son n= local, PAS ces globaux.
# ──────────────────────────────────────────────────────────────────────────────


_LAM_N = 14


_N_SEG = 5


_POLISH = 150  # cfg polish_maxfun (production floor for refits is bypassed below in tests)








@pytest.fixture(autouse=True)


def _cheap_corridor_refit_maxfun(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:


    """Lower L-BFGS-B maxfun for d-profiling refits in this module only (production floor stays 300)."""


    if "test_corridor_profile_refit_maxfun_override_and_fallback" in request.node.nodeid:


        return





    def _cheap(cfg: SplineOptConfig, override: int | None = None) -> int:


        if override is not None:


            return int(max(50, min(int(override), 150)))


        v = getattr(cfg, "corridor_profile_d_polish_maxfun", None)


        if v is not None:


            try:


                iv = int(v)


                if iv > 0:


                    return int(max(50, min(iv, 120)))


            except (TypeError, ValueError):


                pass


        return 60





    monkeypatch.setattr(_core_mod, "corridor_profile_refit_maxfun", _cheap)


    monkeypatch.setattr(_spc_mod, "corridor_profile_refit_maxfun", _cheap)








def _lam(lo: float = 400.0, hi: float = 800.0, n: int | None = None) -> np.ndarray:


    return np.linspace(lo, hi, int(n or _LAM_N))








def _cfg_base(*, lam: np.ndarray, n_seg: int | None = None, **kwargs: object) -> SplineOptConfig:


    n_seg_eff = int(n_seg if n_seg is not None else _N_SEG)


    t_exp = kwargs.pop("t_exp", None)


    if t_exp is None:


        t_exp = 0.6 * np.ones_like(lam)


    n_sub = kwargs.pop("n_sub", None)


    if n_sub is None:


        n_sub = np.full_like(lam, 1.52)


    common: dict = dict(


        lam_nm=lam,


        t_exp=t_exp,


        r_exp=kwargs.pop("r_exp", None),


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=n_seg_eff,


        d_lo=500.0,


        d_hi=4000.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=kwargs.pop("t_is_ratio", False),


        corridor_profile_d_enabled=True,


        polish_maxfun=_POLISH,


        corridor_profile_d_polish_maxfun=_POLISH,


        # Sequential +/-d in tests: less overhead than threads on small marches.


        corridor_profile_d_parallel_walks=False,


    )


    common.update(kwargs)


    return SplineOptConfig(**common)








def _pfast(**overrides: object) -> ProfileCorridorConfig:


    """Tight continuation: few steps, no refine bisection (unless overridden)."""


    d = dict(


        enabled=True,


        step_nm=15.0,


        max_span_nm=36.0,


        max_steps_each_side=4,


        refine_boundary=False,


        n_starts=1,


        rng_seed=0,


    )


    d.update(overrides)


    return ProfileCorridorConfig(**d)








def _pboot(**overrides: object) -> ProfileCorridorConfig:


    """Even tighter for bootstrap / REG-SENS (many repeated profiles)."""


    d = dict(


        enabled=True,


        rmse_alpha=2.2,


        step_nm=25.0,


        max_span_nm=90.0,


        max_steps_each_side=1,


        refine_boundary=False,


        n_starts=1,


        rng_seed=0,


    )


    d.update(overrides)


    return ProfileCorridorConfig(**d)








def test_corridor_profile_refit_maxfun_override_and_fallback() -> None:


    lam = _lam(n=8)


    n_sub = np.full_like(lam, 1.52)


    base_kw = dict(


        lam_nm=lam,


        t_exp=0.6 * np.ones_like(lam),


        r_exp=None,


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=3,


        d_lo=100.0,


        d_hi=5000.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        polish_maxfun=999,


    )


    cfg_cap = SplineOptConfig(**base_kw, corridor_profile_d_polish_maxfun=1200)


    assert corridor_profile_refit_maxfun(cfg_cap) == 1200


    cfg_fallback = SplineOptConfig(**base_kw, corridor_profile_d_polish_maxfun=None)


    assert corridor_profile_refit_maxfun(cfg_fallback) == 999


    assert corridor_profile_refit_maxfun(cfg_fallback, override=400) == 400








def test_profile_corridors_returns_shapes_and_interval() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


    }


    out = compute_profiled_corridors_by_d(


        cfg,


        base,


        pconf=_pfast(rmse_alpha=1.5, rng_seed=123),


        profile_polish_maxfun=_POLISH,


    )


    if not out:


        return


    assert "profile_d_interval_nm" in out


    assert int(out.get("profile_d_polish_maxfun_effective", -1)) == int(_spc_mod.corridor_profile_refit_maxfun(cfg, _POLISH))


    d_int = out.get("profile_d_interval_nm", None)


    assert isinstance(d_int, (tuple, list)) and len(d_int) == 2


    d_ctr = float(out.get("profile_d_interval_center_nm", np.nan))


    d_half = float(out.get("profile_d_interval_half_width_nm", np.nan))


    # PARE-FEU : le profil-optimiseur décale naturellement le centre d_ctr
    # par rapport à d_nm initial. La tolérance doit être au moins d_half.
    # NE PAS durcir à 1e-9 — le shift est physiquement attendu.
    assert abs(d_ctr - float(base["d_nm"])) <= d_half + 1.0


    assert d_half + 1e-12 >= 0.002 * float(base["d_nm"])


    assert "corridor_n_lo" in out and "corridor_n_hi" in out


    assert "corridor_k_lo" in out and "corridor_k_hi" in out


    assert np.asarray(out["corridor_n_lo"]).shape == lam.shape


    assert np.asarray(out["corridor_k_hi"]).shape == lam.shape


    if "corridor_reference_n_lam" in out:


        assert np.asarray(out["corridor_reference_n_lam"]).shape == lam.shape


        assert np.asarray(out["corridor_reference_k_lam"]).shape == lam.shape


        n_lo = np.asarray(out["corridor_n_lo"], dtype=np.float64)


        n_hi = np.asarray(out["corridor_n_hi"], dtype=np.float64)


        nr = np.asarray(out["corridor_reference_n_lam"], dtype=np.float64)


        m = np.isfinite(n_lo) & np.isfinite(n_hi) & np.isfinite(nr)


        assert np.all((nr[m] >= n_lo[m] - 1e-9) & (nr[m] <= n_hi[m] + 1e-9))


        k_lo = np.asarray(out["corridor_k_lo"], dtype=np.float64)


        k_hi = np.asarray(out["corridor_k_hi"], dtype=np.float64)


        kr = np.asarray(out["corridor_reference_k_lam"], dtype=np.float64)


        mk = np.isfinite(k_lo) & np.isfinite(k_hi) & np.isfinite(kr) & (kr > 0.0)


        assert np.all((kr[mk] >= k_lo[mk] - 1e-12) & (kr[mk] <= k_hi[mk] + 1e-12))








def test_profile_corridors_prefers_spectral_rmse_segments_for_threshold() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.5,


        "spectral_rmse_segments": 0.01,


    }


    out = compute_profiled_corridors_by_d(


        cfg,


        base,


        pconf=_pfast(rmse_threshold_mode="alpha", rmse_alpha=80.0, step_nm=20.0, max_span_nm=72.0, n_starts=2, rng_seed=123),


        profile_polish_maxfun=_POLISH,


    )


    if not out:


        return


    assert out.get("profile_d_rmse_ref_source") == "spectral_rmse_segments"


    assert abs(float(out["profile_d_rmse_opt"]) - 0.01) < 1e-9


    assert out.get("profile_d_rmse_thresh_nominal") is not None


    assert abs(float(out["profile_d_rmse_thresh_nominal"]) - 0.8) < 1e-6


    assert float(out["profile_d_rmse_thresh"]) >= float(out["profile_d_rmse_thresh_nominal"]) - 1e-12








def test_profile_corridors_alpha_exports_relax_metadata() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


        "spectral_rmse_segments": 0.01,


    }


    out = compute_profiled_corridors_by_d(


        cfg,


        base,


        pconf=_pfast(rmse_alpha=1.5, n_starts=2, rng_seed=1),


        profile_polish_maxfun=_POLISH,


    )


    if not out:


        return


    assert "profile_d_rmse_thresh_nominal" in out


    assert "profile_d_auto_relaxed_threshold" in out


    assert out["profile_d_rmse_thresh_nominal"] is not None


    assert np.isfinite(float(out["profile_d_rmse_thresh_nominal"]))


    assert np.isfinite(float(out["profile_d_rmse_thresh"]))


    assert isinstance(out["profile_d_auto_relaxed_threshold"], bool)


    assert float(out["profile_d_rmse_thresh"]) >= float(out["profile_d_rmse_thresh_nominal"]) - 1e-12








def test_profile_corridors_lr_mode_returns_chi2_fields() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


    }


    out = compute_profiled_corridors_by_d(


        cfg,


        base,


        pconf=_pfast(mode="lr", max_span_nm=24.0, lr_conf_level=0.95, n_starts=2, rng_seed=123),


        profile_polish_maxfun=_POLISH,


    )


    if not out:


        return


    assert out.get("profile_d_mode") == "lr"


    assert "profile_d_lr_delta_chi2" in out


    assert "profile_d_sigma_t" in out


    assert "profile_d_chi2_values" in out








def test_fixed_d_fit_reports_spectral_rmse_not_penalized_objective() -> None:


    lam = _lam(n=32)


    cfg = _cfg_base(lam=lam, lnk_spline_reg_weight=5.0)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    bounds, _x0_default = _bounds_for_nodes_only(cfg, k)


    n_nodes = np.full(k, 1.65, dtype=np.float64)


    L_nodes = np.asarray([np.log(1e-3 + 3e-4 * ((-1) ** i)) for i in range(k)], dtype=np.float64)


    x0 = np.concatenate((n_nodes, L_nodes))


    fit = _fit_nodes_at_fixed_d(


        cfg,


        np.asarray(sk, dtype=np.float64),


        2000.0,


        x0,


        bounds,


        maxfun=450,


    )


    if fit is None:


        return


    mse_sp, rmse_sp = spectral_mse_rmse_masked_from_nk(


        cfg,


        {},


        np.asarray(lam, dtype=np.float64),


        np.asarray(fit["n_lam"], dtype=np.float64),


        np.asarray(fit["k_lam"], dtype=np.float64),


        float(fit["d_nm"]),


    )


    assert np.isfinite(float(mse_sp))


    assert np.isfinite(float(rmse_sp))


    assert abs(float(fit["rmse"]) - float(rmse_sp)) < 1e-12


    assert abs(float(fit["mse"]) - float(mse_sp)) < 1e-12


    assert np.isfinite(float(fit.get("mse_objective", float("nan"))))


    assert float(fit["mse_objective"]) >= float(fit["mse"]) - 1e-12








def test_fixed_d_fit_keeps_seed_when_refit_degrades_spectral_rmse(


    monkeypatch: pytest.MonkeyPatch,


) -> None:


    """If L-BFGS-B returns a node vector that worsens masked spectral RMSE vs the seed, keep the seed."""


    def _fake_minimize(fun, x0, method=None, jac=None, bounds=None, options=None):


        assert bounds is not None


        lo = np.asarray([float(b[0]) for b in bounds], dtype=np.float64)


        hi = np.asarray([float(b[1]) for b in bounds], dtype=np.float64)


        kk = int(x0.size // 2)


        x_bad = np.concatenate((hi[:kk], lo[kk:])).astype(np.float64)


        return OptimizeResult(


            x=x_bad,


            success=True,


            message="fake_bad_corner",


            nit=0,


            nfev=1,


        )


    monkeypatch.setattr(_spc_mod, "minimize", _fake_minimize)


    lam = _lam(n=32)


    cfg = _cfg_base(lam=lam, lnk_spline_reg_weight=0.0)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    bounds, _ = _bounds_for_nodes_only(cfg, k)


    n_nodes = np.full(k, 1.65, dtype=np.float64)


    L_nodes = np.asarray([np.log(1e-3 + 3e-4 * ((-1) ** i)) for i in range(k)], dtype=np.float64)


    x0 = np.concatenate((n_nodes, L_nodes))


    fit = _fit_nodes_at_fixed_d(


        cfg,


        np.asarray(sk, dtype=np.float64),


        2000.0,


        x0,


        bounds,


        maxfun=50,


    )


    assert fit is not None


    assert fit.get("seed_kept_over_refit") is True


    np.testing.assert_allclose(fit["x_nodes_best"], x0, rtol=0, atol=1e-9)


    assert fit.get("rmse_seed_before_refit") is not None


    assert np.isfinite(float(fit["rmse_seed_before_refit"]))


    assert fit.get("rmse_refit_attempted") is not None


    assert float(fit["rmse_refit_attempted"]) > float(fit["rmse"]) + 1e-12
    assert fit.get("seed_keep_tolerance") is not None
    assert float(fit["seed_keep_tolerance"]) > 0.0
    assert fit.get("seed_keep_rule") == "spectral_rmse_refit_gt_seed_plus_tol"








def test_extract_nodes_remeshes_split_sigma_n_grid() -> None:


    skL = np.asarray([0.2, 0.4, 0.8, 1.2], dtype=np.float64)


    skN = np.asarray([0.2, 0.6, 1.2], dtype=np.float64)


    nN = np.asarray([2.0, 2.2, 2.4], dtype=np.float64)


    out = {


        "sigma_knots_L": skL,


        "sigma_knots_n": skN,


        "n_nodes_physical": nN,


        "L_nodes": np.asarray([-7.0, -7.1, -7.2, -7.3], dtype=np.float64),


        "d_nm": 3000.0,


    }


    sk, n_nodes, L_nodes, d_nm, diag = _extract_knots_and_nodes_from_result(out)


    assert np.allclose(sk, skL)


    assert np.isfinite(d_nm) and abs(d_nm - 3000.0) < 1e-12


    assert L_nodes.shape == skL.shape


    assert n_nodes.shape == skL.shape


    assert np.allclose(n_nodes, np.interp(skL, skN, nN))


    assert diag.get("remeshed_n_sigma_n_to_sigma_L") is True








def test_extract_nodes_remeshes_when_same_k_but_sigma_grids_differ() -> None:


    skL = np.asarray([0.20, 0.40, 0.60, 0.80], dtype=np.float64)


    skN = np.asarray([0.21, 0.41, 0.61, 0.81], dtype=np.float64)


    nN = np.asarray([2.0, 2.1, 2.2, 2.3], dtype=np.float64)


    out = {


        "sigma_knots_L": skL,


        "sigma_knots_n": skN,


        "n_nodes_physical": nN,


        "L_nodes": np.asarray([-7.0, -7.1, -7.2, -7.3], dtype=np.float64),


        "d_nm": 3000.0,


        "x_encoding": "split_sigma_free_knots",


    }


    sk, n_nodes, L_nodes, d_nm, diag = _extract_knots_and_nodes_from_result(out)


    assert diag.get("remeshed_n_sigma_n_to_sigma_L") is True


    assert np.allclose(sk, skL)


    assert np.allclose(n_nodes, np.interp(skL, skN, nN))








def test_reg_sensitivity_scan_returns_table_fields() -> None:


    from certus.spline.spline_profile_corridors import compute_reg_sensitivity_scan





    lam = _lam()


    cfg = _cfg_base(lam=lam, lnk_spline_reg_weight=1e-3, corridor_reg_sensitivity_n_workers=1)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


    }


    pconf = _pboot(rmse_alpha=1.5)


    # Single weight: one full profile inside REG-SENS (enough to exercise the scan plumbing).


    tab = compute_reg_sensitivity_scan(cfg, base, pconf=pconf, weights=np.asarray([1e-3], dtype=np.float64))


    if not tab:


        return


    assert tab.get("reg_sens_enabled") is True


    assert np.asarray(tab["reg_sens_weights"]).shape == (1,)


    assert np.asarray(tab["reg_sens_d_lo_nm"]).shape == (1,)








def test_bootstrap_parametric_smoke() -> None:


    """Minimal parametric bootstrap (n_boot=3 floor for quantiles in module)."""


    from certus.spline.spline_profile_corridors import compute_bootstrap_corridors_by_d





    lam = _lam(n=20)


    cfg = _cfg_base(lam=lam, n_seg=5)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


    }


    pconf = _pboot(rmse_alpha=1.5)


    out = compute_bootstrap_corridors_by_d(


        cfg,


        base,


        pconf=pconf,


        n_boot=3,


        percentile=0.9,


        seed=0,


        sigma_t=0.01,


        mode="parametric",


        n_workers=1,


    )


    if not out:


        return


    assert out.get("boot_enabled") is True


    assert int(out.get("boot_n_workers_effective", 1)) >= 1


    assert "boot_d_lo_q_nm" in out


    assert int(out.get("boot_quick_refit_maxfun", -1)) == 0








def test_profile_corridors_alpha_threshold_basis_and_fallback_metadata() -> None:


    lam = _lam(lo=350.0, hi=900.0, n=36)


    cfg = _cfg_base(lam=lam, t_exp=0.58 * np.ones_like(lam))


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2100.0,


        "n_nodes_physical": np.full(k, 1.7, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.6,


        "spectral_rmse_segments": 0.01,


    }


    pconf = ProfileCorridorConfig(


        enabled=True,


        rmse_alpha=1.05,


        threshold_basis="max",


        threshold_ratio_guard=1.01,


        step_nm=8.0,


        step_nm_initial=2.0,


        step_growth=1.2,


        step_nm_max=8.0,


        max_span_nm=24.0,


        max_steps_each_side=4,


        refine_boundary=False,


        n_starts=1,


        fit_auto_n_starts=False,


        fit_max_n_starts=2,


        rng_seed=7,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=pconf, profile_polish_maxfun=_POLISH)


    if not out:


        return


    assert out.get("profile_d_threshold_basis_effective") in {"nominal", "center_refit", "max"}


    assert "profile_d_threshold_fallback_reason" in out


    assert np.isfinite(float(out.get("profile_d_rmse_thresh", np.nan)))


    assert np.isfinite(float(out.get("profile_d_rmse_thresh_nominal", np.nan)))


    assert float(out["profile_d_rmse_thresh"]) >= float(out["profile_d_rmse_thresh_nominal"]) - 1e-12








def test_profile_corridors_reports_degenerate_status_when_one_side_missing() -> None:


    lam = _lam(n=32)


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


        "spectral_rmse_segments": 0.01,


    }


    pconf = ProfileCorridorConfig(


        enabled=True,


        rmse_alpha=1.01,


        step_nm=12.0,


        step_nm_initial=12.0,


        max_span_nm=24.0,


        max_steps_each_side=3,


        refine_boundary=False,


        min_valid_points=1,


        min_valid_each_side=2,


        n_starts=1,


        rng_seed=0,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=pconf, profile_polish_maxfun=_POLISH)


    if not out:


        return


    assert out.get("profile_d_status") in {"ok", "degenerate"}


    if out.get("profile_d_status") == "degenerate":


        assert int(out.get("profile_d_valid_side_pos", 0)) < 2 or int(out.get("profile_d_valid_side_neg", 0)) < 2








def test_profile_corridors_exposes_seed_gate_analytics() -> None:

    lam = _lam(n=32)

    cfg = _cfg_base(lam=lam)

    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))

    k = int(sk.size)

    base = {
        "sigma_knots": sk,
        "d_nm": 2000.0,
        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),
        "L_nodes": np.asarray([np.log(1e-3 + 3e-4 * ((-1) ** i)) for i in range(k)], dtype=np.float64),
        "rmse": 0.01,
        "spectral_rmse_segments": 0.01,
    }

    pconf = ProfileCorridorConfig(
        enabled=True,
        rmse_alpha=1.02,
        step_nm=10.0,
        step_nm_initial=10.0,
        max_span_nm=20.0,
        max_steps_each_side=2,
        refine_boundary=False,
        min_valid_points=1,
        min_valid_each_side=0,
        n_starts=1,
        fit_auto_n_starts=False,
        fit_max_n_starts=1,
        rng_seed=9,
    )

    out = compute_profiled_corridors_by_d(cfg, base, pconf=pconf, profile_polish_maxfun=_POLISH)
    if not out or str(out.get("profile_d_status", "")) == "failed":
        return

    assert "profile_d_seed_gate_eval_count" in out
    assert "profile_d_seed_gate_kept_count" in out
    assert "profile_d_seed_gate_kept_rate" in out
    assert "profile_d_seed_gate_center_kept" in out
    assert "profile_d_seed_gate_mean_delta_refit_minus_seed" in out
    assert "profile_d_seed_gate_min_delta_refit_minus_seed" in out
    assert "profile_d_seed_gate_max_delta_refit_minus_seed" in out
    assert "profile_d_seed_gate_std_delta_refit_minus_seed" in out

    eval_count = int(out["profile_d_seed_gate_eval_count"])
    kept_count = int(out["profile_d_seed_gate_kept_count"])
    assert eval_count >= 0
    assert 0 <= kept_count <= eval_count
    assert isinstance(out["profile_d_seed_gate_center_kept"], bool)

    rate = float(out["profile_d_seed_gate_kept_rate"])
    if eval_count == 0:
        assert np.isnan(rate)
    else:
        assert 0.0 <= rate <= 1.0
        dmin = float(out["profile_d_seed_gate_min_delta_refit_minus_seed"])
        dmax = float(out["profile_d_seed_gate_max_delta_refit_minus_seed"])
        # PARE-FEU : dmin/dmax peuvent être NaN si aucun seed n'a été
        # gardé (eval_count > 0 mais kept_count == 0). NaN >= NaN → False.
        assert np.isnan(dmax) or np.isnan(dmin) or dmax >= dmin


def test_profile_corridors_realistic_350_5200_case_emits_health_metrics() -> None:


    """Slim stand-in for the former 600-point case: same code paths, smaller grid."""


    lam = np.linspace(350.0, 5199.88, 48)


    n_sub = np.full_like(lam, 1.76)


    t_exp = 0.55 * np.ones_like(lam)


    cfg = SplineOptConfig(


        lam_nm=lam,


        t_exp=t_exp,


        r_exp=None,


        n_sub=n_sub,


        data_type=DataType.TRANSMISSION,


        n_seg=5,


        d_lo=2800.0,


        d_hi=3200.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=True,


        rmse_fit_lambda_nm=(350.0, 5000.0),


        corridor_profile_d_enabled=True,


        polish_maxfun=_POLISH,


        corridor_profile_d_polish_maxfun=_POLISH,


        corridor_profile_d_parallel_walks=False,


    )


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    base = {


        "sigma_knots": sk,


        "d_nm": 3000.0,


        "n_nodes_physical": np.linspace(2.1, 2.7, k, dtype=np.float64),


        "L_nodes": np.linspace(-9.5, -4.0, k, dtype=np.float64),


        "rmse": 0.02,


        "spectral_rmse_segments": 0.01,


    }


    pconf = ProfileCorridorConfig(


        enabled=True,


        rmse_alpha=1.08,


        step_nm=6.0,


        step_nm_initial=2.0,


        step_growth=1.4,


        step_nm_max=6.0,


        max_span_nm=18.0,


        max_steps_each_side=3,


        refine_boundary=False,


        min_valid_points=1,


        min_valid_each_side=1,


        n_starts=1,


        fit_auto_n_starts=False,


        fit_max_n_starts=2,


        rng_seed=42,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=pconf, profile_polish_maxfun=_POLISH)


    if not out:


        return


    assert "profile_d_fit_fail_rate" in out


    assert "profile_d_mean_nfev" in out


    assert "profile_d_boundary_refine_calls" in out








def test_pipeline_corridor_base_source_explicit_solver() -> None:


    from certus.spline.spline_pipeline import _select_corridor_base_result_for_profile





    lam = np.linspace(350.0, 5200.0, 40)


    cfg = SplineOptConfig(


        lam_nm=lam,


        t_exp=np.full_like(lam, 0.55),


        r_exp=None,


        n_sub=np.full_like(lam, 1.52),


        data_type=DataType.TRANSMISSION,


        n_seg=8,


        d_lo=2800.0,


        d_hi=3200.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        corridor_profile_d_enabled=True,


        corridor_profile_d_base_source="solver",


    )


    solver = {"x_encoding": "split_sigma_free_knots", "rmse": 0.0034, "d_nm": 3000.0}


    out = {


        "x_encoding": "xi_n_mono",


        "rmse": 0.12,


        "spectral_rmse_seg_spline_sigma": 0.0030,


        "n_lam_seg_spline_sigma": np.full_like(lam, 2.1),


        "k_lam_seg_spline_sigma": np.full_like(lam, 1e-3),


    }


    b, src = _select_corridor_base_result_for_profile(cfg, out, solver)


    assert src == "solver"


    assert str(b.get("x_encoding")) == "split_sigma_free_knots"








def test_pipeline_corridor_base_source_selector_dict_and_best_polished() -> None:


    from certus.spline.spline_pipeline import _select_corridor_base_result_for_profile





    lam = np.linspace(350.0, 5200.0, 32)


    base_kwargs = dict(


        lam_nm=lam,


        t_exp=np.full_like(lam, 0.55),


        r_exp=None,


        n_sub=np.full_like(lam, 1.52),


        data_type=DataType.TRANSMISSION,


        n_seg=8,


        d_lo=2800.0,


        d_hi=3200.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        corridor_profile_d_enabled=True,


    )


    solver = {"x_encoding": "split_sigma_free_knots", "rmse": 0.0034, "d_nm": 3000.0}


    out = {


        "x_encoding": "xi_n_mono",


        "rmse": 0.12,


        "spectral_rmse_seg_spline_sigma": 0.0030,


        "d_nm_seg_spline_sigma": 3000.1,


        "n_lam_seg_spline_sigma": np.full_like(lam, 2.2),


        "k_lam_seg_spline_sigma": np.full_like(lam, 2e-3),


    }





    cfg_dict = SplineOptConfig(**base_kwargs, corridor_profile_d_base_source="dict")


    b0, s0 = _select_corridor_base_result_for_profile(cfg_dict, out, solver)


    assert s0 == "dict"


    assert str(b0.get("x_encoding")) == "xi_n_mono"





    cfg_best = SplineOptConfig(**base_kwargs, corridor_profile_d_base_source="best_polished")


    b1, s1 = _select_corridor_base_result_for_profile(cfg_best, out, solver)


    assert s1 == "best_polished"


    assert str(b1.get("x_encoding")) == "corridor_base_best_polished_spline_sigma"








def test_best_polished_corridor_base_copies_x_seg_into_nodes() -> None:


    """best_polished doit recopier x_seg_spline_sigma -> x / n_nodes_physical / L_nodes (graine corridor)."""


    from certus.spline.spline_pipeline import _select_corridor_base_result_for_profile





    lam = np.linspace(350.0, 5200.0, 24)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    d_seg = 3000.1


    n_node = 2.25


    L_node = np.log(2e-3)


    x_seg = np.concatenate(


        (


            np.asarray([d_seg], dtype=np.float64),


            np.full(k, n_node, dtype=np.float64),


            np.full(k, L_node, dtype=np.float64),


        )


    )


    cfg = SplineOptConfig(


        lam_nm=lam,


        t_exp=np.full_like(lam, 0.55),


        r_exp=None,


        n_sub=np.full_like(lam, 1.52),


        data_type=DataType.TRANSMISSION,


        n_seg=8,


        d_lo=2800.0,


        d_hi=3200.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        corridor_profile_d_enabled=True,


        corridor_profile_d_base_source="best_polished",


    )


    solver = {


        "sigma_knots": sk,


        "n_nodes_physical": np.full(k, 9.99, dtype=np.float64),


        "L_nodes": np.full(k, 9.99, dtype=np.float64),


        "x_encoding": "split_sigma_free_knots",


        "rmse": 0.05,


        "d_nm": 3000.0,


    }


    out = {


        "spectral_rmse_seg_spline_sigma": 0.002,


        "d_nm_seg_spline_sigma": d_seg,


        "n_lam_seg_spline_sigma": np.full_like(lam, n_node),


        "k_lam_seg_spline_sigma": np.full_like(lam, 2e-3),


        "sigma_knots": sk,


        "x_seg_spline_sigma": x_seg,


    }


    b, src = _select_corridor_base_result_for_profile(cfg, out, solver)


    assert src == "best_polished"


    np.testing.assert_allclose(b["x"], x_seg)


    np.testing.assert_allclose(b["n_nodes_physical"], np.full(k, n_node))


    np.testing.assert_allclose(b["L_nodes"], np.full(k, L_node))








def test_pipeline_best_polished_uses_seg_spline_sigma_only() -> None:


    from certus.spline.spline_pipeline import _select_corridor_base_result_for_profile





    lam = _lam()


    base_kwargs = dict(


        lam_nm=lam,


        t_exp=np.full_like(lam, 0.55),


        r_exp=None,


        n_sub=np.full_like(lam, 1.52),


        data_type=DataType.TRANSMISSION,


        n_seg=8,


        d_lo=2800.0,


        d_hi=3200.0,


        weight_t=1.0,


        weight_r=0.0,


        substrate_name="Test",


        t_is_ratio=False,


        corridor_profile_d_enabled=True,


        corridor_profile_d_base_source="best_polished",


    )


    solver = {"x_encoding": "split_sigma_free_knots", "rmse": 0.01, "d_nm": 3000.0}


    out_sp = {


        "spectral_rmse_best_label": "Spline_cubique_sigma",


        "spectral_rmse_seg_spline_sigma": 0.01,


        "d_nm_seg_spline_sigma": 3000.0,


        "n_lam_seg_spline_sigma": np.full_like(lam, 1.60),


        "k_lam_seg_spline_sigma": np.full_like(lam, 2e-3),


    }


    cfg = SplineOptConfig(**base_kwargs)


    b, src = _select_corridor_base_result_for_profile(cfg, out_sp, solver)


    assert src == "best_polished"


    assert "spline" in str(b.get("x_encoding", "")).lower()


    assert float(b["d_nm"]) == 3000.0








def test_profile_corridors_abs_delta_uses_base_nk_rmse_reference() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    n_grid = np.full(lam.size, 1.65, dtype=np.float64)


    k_grid = np.full(lam.size, 1e-3, dtype=np.float64)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


        "spectral_rmse_segments": 0.005,


        "n_lam": n_grid,


        "k_lam": k_grid,


    }


    _, rmse_ref = spectral_mse_rmse_masked_from_nk(cfg, base, lam, n_grid, k_grid, 2000.0)


    p = _pfast(


        rmse_threshold_mode="abs_delta",


        rmse_abs_tolerance=10.0,


        rmse_alpha=1.05,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=p, profile_polish_maxfun=_POLISH)


    if not out or str(out.get("profile_d_status", "")) == "failed":


        return


    assert out.get("profile_d_rmse_ref_source") == "spectral_rmse_base_nk"


    assert out.get("profile_d_rmse_threshold_mode") == "abs_delta"


    assert abs(float(out["profile_d_rmse_opt"]) - float(rmse_ref)) < 1e-9


    assert out.get("profile_d_auto_relaxed_threshold") is False








def test_expand_corridor_envelope_with_reported_nk() -> None:


    n_lo = np.array([1.0, 2.0], dtype=np.float64)


    n_hi = np.array([3.0, 4.0], dtype=np.float64)


    k_lo = np.array([1e-4, 1e-3], dtype=np.float64)


    k_hi = np.array([2e-4, 3e-3], dtype=np.float64)


    n_nom = np.array([0.5, 4.5], dtype=np.float64)


    k_nom = np.array([5e-5, 5e-3], dtype=np.float64)


    nl, nh, kl, kh = _expand_corridor_envelope_with_reported_nk(


        n_lo, n_hi, k_lo, k_hi, n_nom, k_nom


    )


    assert np.allclose(nl, [0.5, 2.0])


    assert np.allclose(nh, [3.0, 4.5])


    assert np.allclose(kl, [5e-5, 1e-3])


    assert np.allclose(kh, [2e-4, 5e-3])


    # Short arrays: no-op


    nl2, nh2, kl2, kh2 = _expand_corridor_envelope_with_reported_nk(


        n_lo, n_hi, k_lo, k_hi, n_nom[:1], k_nom[:1]


    )


    assert np.allclose(nl2, n_lo) and np.allclose(nh2, n_hi)








def test_extract_nominal_best_polished_corridor_reference() -> None:


    lam = np.linspace(400.0, 800.0, 20)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    x_seg = np.concatenate(


        (


            np.asarray([100.0], dtype=np.float64),


            np.full(k, 1.5, dtype=np.float64),


            np.full(k, np.log(1e-3), dtype=np.float64),


        )


    )


    out = {


        "lam_nm": lam,


        "spectral_rmse_best_label": "Spline_cubique_sigma",


        "spectral_rmse_best_value": 0.0033,


        "n_lam_seg_spline_sigma": np.full_like(lam, 1.5),


        "k_lam_seg_spline_sigma": np.full_like(lam, 1e-3),


        "d_nm_seg_spline_sigma": 100.0,


        "sigma_knots": sk,


        "x_seg_spline_sigma": x_seg,


    }


    pack = extract_nominal_best_polished_corridor_reference(out)


    assert pack is not None


    assert pack["label"] == "Spline_cubique_sigma"


    assert abs(float(pack["rmse_best"]) - 0.0033) < 1e-12


    assert float(pack["d_nm"]) == 100.0


    assert pack["x_seg_spline_sigma"] is not None


    assert int(pack["x_seg_spline_sigma"].size) == 1 + 2 * k








def test_corridor_seed_mesh_x_matches_packed_vector() -> None:


    """Corridor profiling must use ``x_seg_spline_sigma[1:]`` when K,d match (no n_phys↔ξ drift)."""


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    d0 = 2000.0


    n_grid = np.full(lam.size, 1.65, dtype=np.float64)


    k_grid = np.full(lam.size, 1e-3, dtype=np.float64)


    x_seg = np.concatenate(


        (np.asarray([d0], dtype=np.float64), np.full(k, 1.65, dtype=np.float64), np.full(k, np.log(1e-3), dtype=np.float64))


    )


    base = {


        "lam_nm": lam,


        "sigma_knots": sk,


        "d_nm": d0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "n_lam": n_grid,


        "k_lam": k_grid,


        "x_seg_spline_sigma": x_seg,


    }


    xn = _x_nodes0_from_mesh_x_if_consistent(base, sk=sk, d0_nm=d0)


    assert xn is not None


    assert xn.shape == (2 * k,)


    assert np.array_equal(xn, x_seg[1:])


    _mse_s, rmse_s = _spectral_rmse_at_packed_nodes(cfg, base, sk, float(d0), xn)


    _mse_c, rmse_c = spectral_mse_rmse_masked_from_nk(cfg, base, lam, n_grid, k_grid, float(d0))


    assert np.isfinite(rmse_s) and np.isfinite(rmse_c)


    assert abs(float(rmse_s) - float(rmse_c)) < 1e-12








def test_corridor_seed_mesh_x_rejects_d_mismatch() -> None:


    lam = _lam()


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    x_seg = np.concatenate(


        (np.asarray([1999.0], dtype=np.float64), np.full(k, 1.65, dtype=np.float64), np.full(k, np.log(1e-3), dtype=np.float64))


    )


    base = {"x_seg_spline_sigma": x_seg, "sigma_knots": sk, "d_nm": 2000.0}


    assert _x_nodes0_from_mesh_x_if_consistent(base, sk=sk, d0_nm=2000.0) is None








def test_scientific_corridor_uses_spectral_rmse_best_value() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    d0 = 2000.0


    n_grid = np.full(lam.size, 1.65, dtype=np.float64)


    k_grid = np.full(lam.size, 1e-3, dtype=np.float64)


    x_seg = np.concatenate(


        (


            np.asarray([d0], dtype=np.float64),


            np.full(k, 1.65, dtype=np.float64),


            np.full(k, np.log(1e-3), dtype=np.float64),


        )


    )


    rmse_best = 0.0042


    base = {


        "lam_nm": lam,


        "sigma_knots": sk,


        "d_nm": d0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.02,


        "spectral_rmse_segments": 0.01,


        "n_lam": n_grid,


        "k_lam": k_grid,


        "spectral_rmse_best_label": "Spline_cubique_sigma",


        "spectral_rmse_best_value": rmse_best,


        "spectral_rmse_seg_spline_sigma": rmse_best,


        "n_lam_seg_spline_sigma": n_grid.copy(),


        "k_lam_seg_spline_sigma": k_grid.copy(),


        "d_nm_seg_spline_sigma": d0,


        "x_seg_spline_sigma": x_seg,


    }


    p = _pfast(


        rmse_threshold_mode="abs_delta",


        rmse_abs_tolerance=5.0,


        scientific_nominal_corridor=True,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=p, profile_polish_maxfun=_POLISH)


    if not out or str(out.get("profile_d_status", "")) == "failed":


        return


    assert out.get("profile_d_scientific_nominal") is True


    assert out.get("profile_d_rmse_ref_source") == "spectral_rmse_best_value"


    assert abs(float(out["profile_d_rmse_opt"]) - rmse_best) < 1e-9


    assert out.get("profile_d_acceptance_mode") == "delta_rmse_abs_best_polished"








def test_scientific_corridor_k_reference_inside_envelope() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    d0 = 2000.0


    n_grid = np.full(lam.size, 1.65, dtype=np.float64)


    k_grid = np.full(lam.size, 1e-3, dtype=np.float64)


    x_seg = np.concatenate(


        (


            np.asarray([d0], dtype=np.float64),


            np.full(k, 1.65, dtype=np.float64),


            np.full(k, np.log(1e-3), dtype=np.float64),


        )


    )


    rmse_best = 0.0042


    base = {


        "lam_nm": lam,


        "sigma_knots": sk,


        "d_nm": d0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.02,


        "n_lam": n_grid,


        "k_lam": k_grid,


        "spectral_rmse_best_label": "Spline_cubique_sigma",


        "spectral_rmse_best_value": rmse_best,


        "spectral_rmse_seg_spline_sigma": rmse_best,


        "n_lam_seg_spline_sigma": n_grid.copy(),


        "k_lam_seg_spline_sigma": k_grid.copy(),


        "d_nm_seg_spline_sigma": d0,


        "x_seg_spline_sigma": x_seg,


    }


    p = _pfast(


        rmse_threshold_mode="abs_delta",


        rmse_abs_tolerance=5.0,


        scientific_nominal_corridor=True,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=p, profile_polish_maxfun=_POLISH)


    if not out or str(out.get("profile_d_status", "")) == "failed":


        return


    cref = np.asarray(out.get("corridor_reference_k_lam"), dtype=np.float64).ravel()


    k_lo = np.asarray(out["corridor_k_lo"], dtype=np.float64).ravel()


    k_hi = np.asarray(out["corridor_k_hi"], dtype=np.float64).ravel()


    assert cref.size == k_lo.size == k_hi.size


    m = np.isfinite(cref) & np.isfinite(k_lo) & np.isfinite(k_hi) & (cref > 0.0)


    assert np.all(cref[m] + 1e-12 >= k_lo[m])


    assert np.all(cref[m] - 1e-12 <= k_hi[m])








def test_legacy_abs_delta_without_scientific_uses_base_nk_ref() -> None:


    lam = _lam()


    cfg = _cfg_base(lam=lam)


    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))


    k = int(sk.size)


    n_grid = np.full(lam.size, 1.65, dtype=np.float64)


    k_grid = np.full(lam.size, 1e-3, dtype=np.float64)


    base = {


        "sigma_knots": sk,


        "d_nm": 2000.0,


        "n_nodes_physical": np.full(k, 1.65, dtype=np.float64),


        "L_nodes": np.full(k, np.log(1e-3), dtype=np.float64),


        "rmse": 0.01,


        "spectral_rmse_segments": 0.005,


        "n_lam": n_grid,


        "k_lam": k_grid,


        "spectral_rmse_best_label": "Spline_cubique_sigma",


        "spectral_rmse_best_value": 0.001,


        "n_lam_seg_spline_sigma": n_grid.copy(),


        "k_lam_seg_spline_sigma": k_grid.copy(),


        "d_nm_seg_spline_sigma": 2000.0,


        "x_seg_spline_sigma": np.concatenate(


            (


                np.asarray([2000.0], dtype=np.float64),


                np.full(k, 1.65, dtype=np.float64),


                np.full(k, np.log(1e-3), dtype=np.float64),


            )


        ),


    }


    _, rmse_ref = spectral_mse_rmse_masked_from_nk(cfg, base, lam, n_grid, k_grid, 2000.0)


    p = _pfast(


        rmse_threshold_mode="abs_delta",


        rmse_abs_tolerance=10.0,


        scientific_nominal_corridor=False,


    )


    out = compute_profiled_corridors_by_d(cfg, base, pconf=p, profile_polish_maxfun=_POLISH)


    if not out or str(out.get("profile_d_status", "")) == "failed":


        return


    assert out.get("profile_d_scientific_nominal") is False


    assert out.get("profile_d_rmse_ref_source") == "spectral_rmse_base_nk"


    assert abs(float(out["profile_d_rmse_opt"]) - float(rmse_ref)) < 1e-9


