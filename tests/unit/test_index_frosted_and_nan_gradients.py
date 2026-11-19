"""Regression tests for C4 (frosted-glass normalization) and M2 (NaN & weight sum in INDEX gradients)."""

from __future__ import annotations

import numpy as np
import pytest

from certus.core._certus_physics_impl import (
    _compute_index_cost_gradient_kernel,
    _compute_ir_global_cost_gradient_kernel,
    calculate_bare_substrate_RT,
    calculate_reflection_array,
    calculate_RT_single_layer_backside_array,
    compute_mse_vectorized,
)
from certus.core.certus_index_objectives import (
    TLUObjective,
    _njit_ir_global_gradient_fused,
    _njit_ir_global_mse_fused,
)
from certus.utils.certus_index_utils import DataType


@pytest.mark.unit
def test_tlu_frosted_glass_normalized_gradient_matches_fd() -> None:
    wls = np.linspace(500.0, 1100.0, 12, dtype=np.float64)
    n_sub = np.full_like(wls, 1.52)
    params_true = np.array([145.0, 1.8, 35.0, 3.8, 1.5, 0.08, 2.1], dtype=np.float64)
    params_test = np.array([138.0, 1.9, 32.0, 3.6, 1.6, 0.09, 2.0], dtype=np.float64)

    base_obj = TLUObjective(
        wavelengths=wls,
        target_T=None,
        target_R=np.zeros_like(wls),
        n_substrate=n_sub,
        data_type=DataType.REFLECTION,
        thickness_bounds=(40.0, 400.0),
        use_normalized=True,
        is_frosted_glass=True,
    )
    # Build synthetic physical frosted targets using calculate_reflection_array evaluated via a different TLU state.
    # Evaluate true params through cost-free R helper by calling internal model at params_true:
    from certus.physics.certus_optical_models import epsilon1_TL_analytic, epsilon2_TLU_array, epsilon_to_nk

    e_grid = 1239.841984 / wls
    eps2 = epsilon2_TLU_array(e_grid, *params_true[1:4], params_true[4], params_true[5])
    eps1 = epsilon1_TL_analytic(e_grid, *params_true[1:5], params_true[6])
    n_true, k_true, _ = epsilon_to_nk(eps1, eps2, 1.0, 6.0, 5.0)
    r_target = calculate_reflection_array(wls, n_true, k_true, float(params_true[0]), n_sub)
    t_target = np.linspace(0.6, 0.9, len(wls), dtype=np.float64)

    obj = TLUObjective(
        wavelengths=wls,
        target_T=t_target,
        target_R=r_target + 0.03,
        n_substrate=n_sub,
        data_type=DataType.BOTH,
        thickness_bounds=(40.0, 400.0),
        use_normalized=True,
        weight_T=1.0,
        weight_R=1.0,
        is_frosted_glass=True,
    )
    assert base_obj.T_substrate[0] < 0.95  # Confirm T_sub != 1 so C4 would corrupt normalized frosted gradient
    grad = obj.gradient(params_test)

    eps = 1e-6
    fd = np.zeros_like(params_test)
    for idx in range(len(params_test)):
        p_plus = params_test.copy()
        p_minus = params_test.copy()
        p_plus[idx] += eps
        p_minus[idx] -= eps
        fd[idx] = (obj(p_plus) - obj(p_minus)) / (2.0 * eps)

    assert np.allclose(grad, fd, rtol=1e-4, atol=1e-5)


@pytest.mark.unit
def test_ir_global_fused_frosted_normalized_matches_fd() -> None:
    lam_nm = np.linspace(3000.0, 6000.0, 12, dtype=np.float64)
    lam_um = lam_nm / 1000.0
    n_sub = np.full_like(lam_nm, 1.52)
    t_sub = calculate_bare_substrate_RT(lam_nm, n_sub)
    w = np.linspace(0.5, 2.0, len(lam_nm), dtype=np.float64)
    p_sell = np.array([2.2, 0.12, 0.25, 0.05, 8.0], dtype=np.float64)
    p_k8 = np.array([0.2, -12.0, 0.15, -13.0, 0.05, 4.5, 0.6, 2.0], dtype=np.float64)
    d = 450.0
    t_exp = np.full_like(lam_nm, 0.5)
    r_exp = np.full_like(lam_nm, 0.18)
    k_sub = np.zeros(0, dtype=np.float64)

    def eval_cost(ps: np.ndarray, pk: np.ndarray) -> float:
        return float(
            _njit_ir_global_mse_fused(
                lam_nm, lam_um, n_sub, w, t_exp, r_exp, ps, pk, d,
                0.0, 1.0, False, True, True, False, k_sub, 0.0, True, t_sub,
            )
        )

    grad_out = np.zeros(13, dtype=np.float64)
    _njit_ir_global_gradient_fused(
        lam_nm, lam_um, n_sub, w, t_exp, r_exp, p_sell, p_k8, d,
        0.0, 1.0, False, True, True, False, k_sub, 0.0, True, t_sub, grad_out,
    )

    # Frosted cost with use_norm=True must match use_norm=False (never R/T_sub)
    cost_norm = eval_cost(p_sell, p_k8)
    cost_raw = float(
        _njit_ir_global_mse_fused(
            lam_nm, lam_um, n_sub, w, t_exp, r_exp, p_sell, p_k8, d,
            0.0, 1.0, False, True, True, False, k_sub, 0.0, False, t_sub,
        )
    )
    assert cost_norm == pytest.approx(cost_raw, rel=1e-12, abs=1e-12)

    eps = 1e-6
    fd = np.zeros(13, dtype=np.float64)
    for idx in range(5):
        p_up = p_sell.copy()
        p_dn = p_sell.copy()
        p_up[idx] += eps
        p_dn[idx] -= eps
        fd[idx] = (eval_cost(p_up, p_k8) - eval_cost(p_dn, p_k8)) / (2.0 * eps)
    for idx in range(8):
        k_up = p_k8.copy()
        k_dn = p_k8.copy()
        k_up[idx] += eps
        k_dn[idx] -= eps
        fd[5 + idx] = (eval_cost(p_sell, k_up) - eval_cost(p_sell, k_dn)) / (2.0 * eps)

    assert np.allclose(grad_out, fd, rtol=1e-4, atol=1e-6)


@pytest.mark.unit
@pytest.mark.parametrize("use_normalized", [False, True])
def test_index_kernels_skip_nan_targets_and_match_weighted_mse_fd(use_normalized: bool) -> None:
    wls = np.linspace(500.0, 1000.0, 10, dtype=np.float64)
    n_base = np.full_like(wls, 1.95)
    k_base = np.full_like(wls, 0.08)
    n_sub = np.full_like(wls, 1.52)
    t_sub = calculate_bare_substrate_RT(wls, n_sub)
    d_base = 120.0
    weights = np.array([0.5, 2.0, 1.5, 3.0, 0.25, 4.0, 1.0, 2.5, 0.75, 1.25], dtype=np.float64)

    r_ref, t_ref = calculate_RT_single_layer_backside_array(wls, n_base, k_base, d_base, n_sub)
    if use_normalized:
        t_tgt = (t_ref / t_sub) + 0.04
        r_tgt = (r_ref / t_sub) - 0.03
    else:
        t_tgt = t_ref + 0.04
        r_tgt = r_ref - 0.03
    t_tgt[2] = np.nan
    r_tgt[5] = np.nan

    dn_dp = np.zeros((6, len(wls)), dtype=np.float64)
    dk_dp = np.zeros((6, len(wls)), dtype=np.float64)
    dn_dp[0, :] = np.linspace(0.6, 1.4, len(wls))
    dk_dp[1, :] = np.linspace(0.3, 1.1, len(wls))
    r_sub = np.zeros_like(t_sub)
    w_t, w_r = 0.6, 0.4

    def eval_weighted_mse(dd: float, pn: float, pk: float) -> float:
        r_c, t_c = calculate_RT_single_layer_backside_array(
            wls, n_base + pn * dn_dp[0], k_base + pk * dk_dp[1], d_base + dd, n_sub
        )
        t_v = t_c / t_sub if use_normalized else t_c
        r_v = r_c / t_sub if use_normalized else r_c
        mse_t, _ = compute_mse_vectorized(t_v, t_tgt, weights)
        mse_r, _ = compute_mse_vectorized(r_v, r_tgt, weights)
        return float(w_t * mse_t + w_r * mse_r)

    grad_fast = _compute_index_cost_gradient_kernel(
        wls, n_base, k_base, d_base, n_sub, t_tgt, r_tgt, weights,
        True, True, dn_dp, dk_dp, t_sub, r_sub, use_normalized, w_t, w_r,
    )
    grad_ir = _compute_ir_global_cost_gradient_kernel(
        wls, n_base, k_base, d_base, n_sub, t_tgt, r_tgt, weights,
        True, True, dn_dp[:1], dk_dp[1:2], t_sub, use_normalized, w_t, w_r,
        False, False, np.zeros(0, dtype=np.float64), 0.0, True,
    )

    assert np.all(np.isfinite(grad_fast))
    assert np.all(np.isfinite(grad_ir))

    eps = 1e-6
    fd_d = (eval_weighted_mse(eps, 0.0, 0.0) - eval_weighted_mse(-eps, 0.0, 0.0)) / (2.0 * eps)
    fd_n = (eval_weighted_mse(0.0, eps, 0.0) - eval_weighted_mse(0.0, -eps, 0.0)) / (2.0 * eps)
    fd_k = (eval_weighted_mse(0.0, 0.0, eps) - eval_weighted_mse(0.0, 0.0, -eps)) / (2.0 * eps)

    assert grad_fast[0] == pytest.approx(fd_d, rel=1e-5, abs=1e-6)
    assert grad_fast[1] == pytest.approx(fd_n, rel=1e-5, abs=1e-6)
    assert grad_fast[2] == pytest.approx(fd_k, rel=1e-5, abs=1e-6)
    assert grad_ir[0] == pytest.approx(fd_d, rel=1e-5, abs=1e-6)
    assert grad_ir[1] == pytest.approx(fd_n, rel=1e-5, abs=1e-6)
    assert grad_ir[2] == pytest.approx(fd_k, rel=1e-5, abs=1e-6)
