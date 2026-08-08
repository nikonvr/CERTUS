"""Oracle tests verifying analytic gradients against central finite differences (Lot B)."""

import numpy as np
import pytest

from certus.physics.gradient_oblique import (
    compute_gradient_all_layers_analytic,
    compute_oblique_gradient_contrib_analytic,
)
from certus.physics.gradient_metal import compute_metal_bilayer_gradient_analytic


def test_compute_gradient_all_layers_analytic_oracle():
    """Verify compute_gradient_all_layers_analytic against central finite differences."""
    ep = np.array([85.0, 115.0, 90.0, 120.0], dtype=np.float64)
    wls = np.array([450.0, 500.0, 550.0, 600.0, 650.0], dtype=np.float64)
    n_layers_T = np.array(
        [[2.35 + 0j, 1.48 + 0j, 2.35 + 0j, 1.48 + 0j] for _ in wls], dtype=np.complex128
    )
    n_sub = np.array([1.52 + 0j] * len(wls), dtype=np.complex128)
    n_back_T = np.array([[1.48 + 0j] * 4 for _ in wls], dtype=np.complex128)
    d_back = np.array([0.0], dtype=np.float64)

    # Non-uniform target values and weights
    tgt_vals = np.array([0.92, 0.85, 0.10, 0.05, 0.01], dtype=np.float64)
    tgt_weights = np.array([2.5, 1.0, 3.0, 4.0, 0.5], dtype=np.float64)

    cost, grad = compute_gradient_all_layers_analytic(
        ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, False, n_back_T, d_back
    )

    h = 1e-6
    fd_grad = np.zeros_like(grad)

    for i in range(len(ep)):
        ep_p = ep.copy()
        ep_p[i] += h
        cost_p, _ = compute_gradient_all_layers_analytic(
            ep_p, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, False, n_back_T, d_back
        )

        ep_m = ep.copy()
        ep_m[i] -= h
        cost_m, _ = compute_gradient_all_layers_analytic(
            ep_m, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 0.0, False, n_back_T, d_back
        )

        fd_grad[i] = (cost_p - cost_m) / (2.0 * h)

    rel_error = np.abs(grad - fd_grad) / (np.abs(grad) + 1e-7)
    assert np.all(rel_error < 1e-3), f"Analytic vs FD gradient mismatch: rel_error={rel_error}"


def test_compute_oblique_gradient_contrib_analytic_oracle():
    """Verify compute_oblique_gradient_contrib_analytic against central finite differences."""
    ep = np.array([70.0, 100.0, 65.0, 110.0], dtype=np.float64)
    wls = np.array([500.0, 550.0, 600.0], dtype=np.float64)
    n_layers_T = np.array(
        [[2.30 + 0j, 1.45 + 0j, 2.30 + 0j, 1.45 + 0j] for _ in wls], dtype=np.complex128
    )
    n_sub = np.array([1.52 + 0j] * len(wls), dtype=np.complex128)
    tgt_vals = np.array([0.80, 0.50, 0.20], dtype=np.float64)
    tgt_weights = np.array([1.5, 2.0, 0.8], dtype=np.float64)

    for is_s_pol in (True, False):
        for is_refl in (True, False):
            err_sum, grad_raw, weight_sum = compute_oblique_gradient_contrib_analytic(
                ep, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, is_s_pol, is_refl
            )
            cost = err_sum / weight_sum
            grad = (2.0 / weight_sum) * grad_raw

            h = 1e-6
            fd_grad = np.zeros_like(grad)
            for i in range(len(ep)):
                ep_p = ep.copy()
                ep_p[i] += h
                err_p, _, w_p = compute_oblique_gradient_contrib_analytic(
                    ep_p, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, is_s_pol, is_refl
                )
                c_p = err_p / w_p

                ep_m = ep.copy()
                ep_m[i] -= h
                err_m, _, w_m = compute_oblique_gradient_contrib_analytic(
                    ep_m, n_layers_T, n_sub, wls, tgt_vals, tgt_weights, 45.0, is_s_pol, is_refl
                )
                c_m = err_m / w_m

                fd_grad[i] = (c_p - c_m) / (2.0 * h)

            rel_error = np.abs(grad - fd_grad) / (np.abs(grad) + 1e-7)
            assert np.all(rel_error < 1e-3), (
                f"Oblique gradient mismatch (s_pol={is_s_pol}, refl={is_refl}): "
                f"rel_error={rel_error}"
            )


def test_compute_metal_tmm_gradient_kernel_oracle():
    """Verify _compute_metal_tmm_gradient_kernel (eM and eL gradients) against finite differences."""
    from certus.physics.gradient_metal import _compute_metal_tmm_gradient_kernel

    wls = np.array([450.0, 550.0, 650.0], dtype=np.float64)
    nM_complex = np.array([0.15 - 3.2j, 0.12 - 3.8j, 0.10 - 4.2j], dtype=np.complex128)
    eM = 25.0
    eL = 80.0
    nL_complex = np.array([1.48 + 0j, 1.46 + 0j, 1.45 + 0j], dtype=np.complex128)
    nSub_complex = np.array([1.52 + 0j, 1.52 + 0j, 1.52 + 0j], dtype=np.complex128)
    r_tgt = np.array([0.95, 0.90, 0.85], dtype=np.float64)

    mse, g_eM, g_eL, _, _, _ = _compute_metal_tmm_gradient_kernel(
        wls, nM_complex, eM, eL, nL_complex, nSub_complex, r_tgt
    )

    h = 1e-6
    mse_p_eM, _, _, _, _, _ = _compute_metal_tmm_gradient_kernel(
        wls, nM_complex, eM + h, eL, nL_complex, nSub_complex, r_tgt
    )
    mse_m_eM, _, _, _, _, _ = _compute_metal_tmm_gradient_kernel(
        wls, nM_complex, eM - h, eL, nL_complex, nSub_complex, r_tgt
    )
    fd_g_eM = (mse_p_eM - mse_m_eM) / (2.0 * h)

    mse_p_eL, _, _, _, _, _ = _compute_metal_tmm_gradient_kernel(
        wls, nM_complex, eM, eL + h, nL_complex, nSub_complex, r_tgt
    )
    mse_m_eL, _, _, _, _, _ = _compute_metal_tmm_gradient_kernel(
        wls, nM_complex, eM, eL - h, nL_complex, nSub_complex, r_tgt
    )
    fd_g_eL = (mse_p_eL - mse_m_eL) / (2.0 * h)

    rel_eM = abs(g_eM - fd_g_eM) / (abs(g_eM) + 1e-7)
    rel_eL = abs(g_eL - fd_g_eL) / (abs(g_eL) + 1e-7)

    assert rel_eM < 1e-3, f"Metal bilayer eM gradient mismatch: analytic={g_eM}, fd={fd_g_eM}"
    assert rel_eL < 1e-3, f"Metal bilayer eL gradient mismatch: analytic={g_eL}, fd={fd_g_eL}"

