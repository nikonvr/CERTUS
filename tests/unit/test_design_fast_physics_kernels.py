"""Unit tests for the fast dielectric, backside (ALG-25), oblique precomputed (ALG-08), and Gauss-Newton (ALG-07) kernels in CERTUS_DESIGN."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_worker_utils import run_coord_descent_5cycles
from certus.physics.design_fast_kernels import (
    compute_gradient_backside_cached_fast,
    compute_gradient_lossless_backside_fast,
    compute_gradient_lossless_front_fast,
    compute_oblique_backside_contrib_precomputed,
    compute_oblique_gradient_contrib_precomputed,
    cost_lossless_backside_fast,
    cost_lossless_front_fast,
    gauss_newton_refine_normal,
    precompute_oblique_optical_terms,
    prepare_normal_fast_context,
)
from certus.physics.gradient_oblique import (
    compute_gradient_all_layers_analytic,
    compute_oblique_backside_bundle_analytic,
    compute_oblique_gradient_contrib_analytic,
)
from certus.physics.gradient_utils import cost_numba_fast


def test_lossless_front_fast_matches_reference_cost_and_gradient() -> None:
    rng = np.random.default_rng(42)
    wls = np.linspace(400.0, 1200.0, 121)
    n_layers = 18
    ep = rng.uniform(15.0, 140.0, size=n_layers)
    n_layers_T = np.empty((len(wls), n_layers), dtype=np.complex128)
    for k in range(n_layers):
        n_layers_T[:, k] = 2.35 if k % 2 == 0 else 1.45
    n_sub = np.full(len(wls), 1.52 + 0.0j, dtype=np.complex128)
    tgt_vals = np.full(len(wls), 0.5, dtype=np.float64)
    tgt_weights = rng.uniform(0.5, 1.5, size=len(wls))
    var_idx = np.array([0, 2, 3, 5, 8, 11, 14, 17], dtype=np.int64)
    n_back_empty = np.zeros((len(wls), 0), dtype=np.complex128)
    d_back_empty = np.zeros(0, dtype=np.float64)

    ctx = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        has_back_calc=False,
        n_back_T=n_back_empty,
        d_back=d_back_empty,
    )
    assert ctx["is_lossless_front"] is True

    ref_cost = cost_numba_fast(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.01, False, n_back_empty, d_back_empty
    )
    fast_cost = cost_lossless_front_fast(
        ep,
        ctx["n_layers_real"],
        ctx["inv_n_layers_real"],
        ctx["n_sub_real"],
        ctx["k0_wls"],
        tgt_vals,
        tgt_weights,
    )
    np.testing.assert_allclose(fast_cost, ref_cost, rtol=1e-14, atol=1e-15)

    ref_c_grad, ref_grad = compute_gradient_all_layers_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.01, False, n_back_empty, d_back_empty, var_idx
    )
    fast_c_grad, fast_grad = compute_gradient_lossless_front_fast(
        ep,
        ctx["n_layers_real"],
        ctx["inv_n_layers_real"],
        ctx["n_sub_real"],
        ctx["k0_wls"],
        tgt_vals,
        tgt_weights,
        var_idx,
        0.01,
    )
    np.testing.assert_allclose(fast_c_grad, ref_c_grad, rtol=1e-14, atol=1e-15)
    np.testing.assert_allclose(fast_grad, ref_grad, rtol=1e-13, atol=1e-14)


def test_backside_normal_fast_matches_reference_for_lossless_and_absorbing_stacks() -> None:
    rng = np.random.default_rng(107)
    wls = np.linspace(420.0, 980.0, 85)
    n_layers = 12
    ep = rng.uniform(20.0, 120.0, size=n_layers)
    n_layers_T = np.empty((len(wls), n_layers), dtype=np.complex128)
    for k in range(n_layers):
        n_layers_T[:, k] = 2.25 if k % 2 == 0 else 1.46
    n_sub = np.full(len(wls), 1.52 + 0.0j, dtype=np.complex128)
    d_back = np.array([85.0, 110.0, 65.0, 95.0], dtype=np.float64)
    n_back_T = np.empty((len(wls), len(d_back)), dtype=np.complex128)
    for k in range(len(d_back)):
        n_back_T[:, k] = 2.25 if k % 2 == 0 else 1.46
    tgt_vals = np.full(len(wls), 0.92, dtype=np.float64)
    tgt_weights = rng.uniform(0.3, 1.2, size=len(wls))
    var_idx = np.arange(n_layers, dtype=np.int64)

    # 1. Lossless front stack with backside AR stack
    ctx_lossless = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        has_back_calc=True,
        n_back_T=n_back_T,
        d_back=d_back,
    )
    ref_cost = cost_numba_fast(ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.01, True, n_back_T, d_back)
    fast_cost = cost_lossless_backside_fast(
        ep,
        ctx_lossless["n_layers_real"],
        ctx_lossless["inv_n_layers_real"],
        ctx_lossless["n_sub_real"],
        ctx_lossless["k0_wls"],
        ctx_lossless["rb_prime"],
        ctx_lossless["tb"],
        tgt_vals,
        tgt_weights,
    )
    np.testing.assert_allclose(fast_cost, ref_cost, rtol=1e-13, atol=1e-15)

    ref_cg, ref_grad = compute_gradient_all_layers_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.01, True, n_back_T, d_back, var_idx
    )
    fast_cg, fast_grad = compute_gradient_lossless_backside_fast(
        ep,
        ctx_lossless["n_layers_real"],
        ctx_lossless["inv_n_layers_real"],
        ctx_lossless["n_sub_real"],
        ctx_lossless["k0_wls"],
        ctx_lossless["rb_prime"],
        ctx_lossless["tb"],
        tgt_vals,
        tgt_weights,
        var_idx,
        0.01,
    )
    np.testing.assert_allclose(fast_cg, ref_cg, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(fast_grad, ref_grad, rtol=1e-12, atol=1e-14)

    # 2. Absorbing front stack with backside stack (single-pass transpose identity M_rev[0,0]=M_fwd[1,1])
    n_layers_abs = n_layers_T.copy()
    n_layers_abs[:, 1] -= 0.015j
    n_layers_abs[:, 4] -= 0.008j
    ctx_abs = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_abs,
        n_sub=n_sub - 1e-4j,
        has_back_calc=True,
        n_back_T=n_back_T,
        d_back=d_back,
    )
    assert ctx_abs["is_lossless_front"] is False
    ref_cg_abs, ref_grad_abs = compute_gradient_all_layers_analytic(
        ep, n_layers_abs, n_sub - 1e-4j, wls, tgt_vals, tgt_weights, 0.01, True, n_back_T, d_back, var_idx
    )
    fast_cg_abs, fast_grad_abs = compute_gradient_backside_cached_fast(
        ep,
        n_layers_abs,
        n_sub - 1e-4j,
        wls,
        ctx_abs["rb_prime"],
        ctx_abs["tb"],
        tgt_vals,
        tgt_weights,
        var_idx,
        0.01,
    )
    np.testing.assert_allclose(fast_cg_abs, ref_cg_abs, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(fast_grad_abs, ref_grad_abs, rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("is_s_pol", [True, False])
@pytest.mark.parametrize("is_reflectance", [True, False])
def test_oblique_precomputed_fast_matches_reference_front_and_backside(
    is_s_pol: bool, is_reflectance: bool
) -> None:
    rng = np.random.default_rng(2026)
    wls = np.linspace(450.0, 1050.0, 71)
    n_layers = 10
    ep = rng.uniform(18.0, 130.0, size=n_layers)
    n_layers_T = np.empty((len(wls), n_layers), dtype=np.complex128)
    for k in range(n_layers):
        n_layers_T[:, k] = (2.30 if k % 2 == 0 else 1.45) - (0.005j if k == 3 else 0.0j)
    n_sub = np.full(len(wls), 1.52 - 2e-5j, dtype=np.complex128)
    tgt_vals = rng.uniform(0.1, 0.9, size=len(wls))
    tgt_weights = rng.uniform(0.4, 1.1, size=len(wls))
    var_idx = np.array([0, 1, 3, 5, 7, 9], dtype=np.int64)
    angle_deg = 42.0

    pre = precompute_oblique_optical_terms(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        angle_deg=angle_deg,
        is_s_pol=is_s_pol,
    )
    ref_err, ref_grad, ref_w = compute_oblique_gradient_contrib_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, angle_deg, is_s_pol, is_reflectance, var_idx
    )
    fast_err, fast_grad, fast_w = compute_oblique_gradient_contrib_precomputed(
        ep, pre, tgt_vals, tgt_weights, is_reflectance, var_idx
    )
    np.testing.assert_allclose(fast_w, ref_w, rtol=1e-14, atol=1e-15)
    np.testing.assert_allclose(fast_err, ref_err, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(fast_grad, ref_grad, rtol=1e-12, atol=1e-14)

    # Backside oblique comparison
    d_back = np.array([75.0, 105.0], dtype=np.float64)
    n_back_T = np.column_stack([np.full(len(wls), 2.30 + 0j), np.full(len(wls), 1.45 + 0j)])
    pre_back = precompute_oblique_optical_terms(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        angle_deg=angle_deg,
        is_s_pol=is_s_pol,
        has_back_calc=True,
        n_back_T=n_back_T,
        d_back=d_back,
    )
    y_R, dy_R, y_T, dy_T = compute_oblique_backside_bundle_analytic(
        ep, n_layers_T, n_sub, wls, var_idx, angle_deg, is_s_pol, n_back_T, d_back
    )
    y_ref = y_R if is_reflectance else y_T
    dy_ref = dy_R if is_reflectance else dy_T
    diff_ref = y_ref - tgt_vals
    ref_b_err = float(np.sum(tgt_weights * diff_ref * diff_ref))
    ref_b_grad = np.sum(tgt_weights[:, None] * diff_ref[:, None] * dy_ref, axis=0)

    fast_b_err, fast_b_grad, fast_b_w = compute_oblique_backside_contrib_precomputed(
        ep, pre_back, tgt_vals, tgt_weights, is_reflectance, var_idx
    )
    np.testing.assert_allclose(fast_b_w, float(np.sum(tgt_weights)), rtol=1e-14, atol=1e-15)
    np.testing.assert_allclose(fast_b_err, ref_b_err, rtol=1e-13, atol=1e-15)
    np.testing.assert_allclose(fast_b_grad, ref_b_grad, rtol=1e-12, atol=1e-14)


def test_gauss_newton_refinement_converges_quadratic_and_respects_floor() -> None:
    wls = np.linspace(400.0, 1200.0, 161)
    n_layers = 14
    n_layers_T = np.empty((len(wls), n_layers), dtype=np.complex128)
    for k in range(n_layers):
        n_layers_T[:, k] = 2.35 if k % 2 == 0 else 1.45
    n_sub = np.full(len(wls), 1.52 + 0.0j, dtype=np.complex128)
    n_back_empty = np.zeros((len(wls), 0), dtype=np.complex128)
    d_back_empty = np.zeros(0, dtype=np.float64)

    # True target spectrum generated from a known stack, starting from a perturbed stack with a 5 nm floor
    ep_true = np.array([52.0, 95.0, 48.0, 160.0, 5.0, 145.0, 55.0, 88.0, 62.0, 110.0, 44.0, 92.0, 58.0, 82.0])
    ctx = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        has_back_calc=False,
        n_back_T=n_back_empty,
        d_back=d_back_empty,
    )
    from certus.physics.certus_tmm_matrix import calculate_RT_no_backside

    _r_true, tgt_vals = calculate_RT_no_backside(ep_true, n_layers_T, n_sub, wls)
    tgt_weights = np.ones(len(wls), dtype=np.float64)
    var_idx = np.arange(n_layers, dtype=np.int64)
    lower_bounds = np.full(n_layers, 5.0, dtype=np.float64)

    rng = np.random.default_rng(7)
    ep_start = np.maximum(5.0, ep_true + rng.normal(0.0, 2.5, size=n_layers))
    start_cost = cost_lossless_front_fast(
        ep_start,
        ctx["n_layers_real"],
        ctx["inv_n_layers_real"],
        ctx["n_sub_real"],
        ctx["k0_wls"],
        tgt_vals,
        tgt_weights,
    )

    ep_gn, cost_gn = gauss_newton_refine_normal(
        ep_start,
        ctx=ctx,
        tgt_vals=tgt_vals,
        tgt_weights=tgt_weights,
        var_idx=var_idx,
        lower_bounds=lower_bounds,
        max_iter=25,
    )
    assert cost_gn < start_cost * 1e-6
    assert np.all(ep_gn >= 5.0 - 1e-12)


def test_weak_extinction_below_1e4_uses_real_fast_search_then_exact_complex_final_refinement() -> None:
    wls = np.linspace(400.0, 900.0, 101)
    n_layers = 8
    n_layers_T = np.empty((len(wls), n_layers), dtype=np.complex128)
    for k in range(n_layers):
        # Weak dielectric extinction k = 5e-5 (< 1e-4 threshold)
        n_layers_T[:, k] = (2.35 - 5e-5j) if k % 2 == 0 else (1.45 - 1e-5j)
    n_sub = np.full(len(wls), 1.52 + 0.0j, dtype=np.complex128)
    n_back_empty = np.zeros((len(wls), 0), dtype=np.complex128)
    d_back_empty = np.zeros(0, dtype=np.float64)

    ctx_search = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        has_back_calc=False,
        n_back_T=n_back_empty,
        d_back=d_back_empty,
        k_real_threshold=1e-4,
    )
    assert ctx_search["use_real_approx"] is True
    assert ctx_search["has_weak_k"] is True
    assert ctx_search["is_strictly_lossless"] is False

    # Final refinement context uses strict k threshold so final polish runs on exact complex n - ik
    ctx_exact = prepare_normal_fast_context(
        wls=wls,
        n_layers_T=n_layers_T,
        n_sub=n_sub,
        has_back_calc=False,
        n_back_T=n_back_empty,
        d_back=d_back_empty,
        k_real_threshold=1e-14,
    )
    assert ctx_exact["use_real_approx"] is False

