"""
CERTUS Gradient Optimization - Metal Gradients Module

Extracted from certus_opt_gradients.py for better modularity.
Contains gradient computation for metallic (highly absorbing) layers.
"""

import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE
import certus.physics.certus_tmm_core as tmm_core
from certus.physics.gradient_utils import compute_mse_vectorized


def _compute_metal_tmm_gradient_kernel(
    l_array: np.ndarray,
    nM_complex_array: np.ndarray,
    eM: float,
    eL: float,
    nL_complex_array: np.ndarray,
    nSub_complex_array: np.ndarray,
    r_tgt_array: np.ndarray,
):
    """Computes Cost and Gradients w.r.t physical params and optical clues for Bilayer."""

    n_pts = len(l_array)

    n_pts_inv = 1.0 / n_pts

    grad_eM = 0.0

    grad_eL = 0.0

    # Sensitivities arrays

    dJ_dnM_r = np.zeros(n_pts, dtype=np.float64)

    dJ_dnM_i = np.zeros(n_pts, dtype=np.float64)

    dJ_dnL_r = np.zeros(n_pts, dtype=np.float64)

    mse = 0.0

    for i in prange(n_pts):
        wl = l_array[i]

        inv_wl = 1.0 / wl

        k0 = TWO_PI * inv_wl

        R_tgt = r_tgt_array[i]

        # --- FORWARD PASS ---

        nM = nM_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nM.imag > 0.0:
            nM = nM.real - 1j * nM.imag

        phiM_base = k0 * eM

        phiM = phiM_base * nM

        cM = np.cos(phiM)

        sM = np.sin(phiM)

        inv_nM = 1.0 / nM if abs(nM) > 1e-14 else 0j

        mM00 = cM

        mM01 = +1j * inv_nM * sM

        mM10 = +1j * nM * sM

        mM11 = cM

        nL = nL_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nL.imag > 0.0:
            nL = nL.real - 1j * nL.imag

        phiL_base = k0 * eL

        phiL = phiL_base * nL

        cL = np.cos(phiL)

        sL = np.sin(phiL)

        inv_nL = 1.0 / nL if abs(nL) > 1e-14 else 0j

        mL00 = cL

        mL01 = +1j * inv_nL * sL

        mL10 = +1j * nL * sL

        mL11 = cL

        nS = nSub_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nS.imag > 0.0:
            nS = nS.real - 1j * nS.imag

        # Total Matrix M_tot = M_M * M_L

        Mt00 = mM00 * mL00 + mM01 * mL10

        Mt01 = mM00 * mL01 + mM01 * mL11

        Mt10 = mM10 * mL00 + mM11 * mL10

        Mt11 = mM10 * mL01 + mM11 * mL11

        n0 = 1.0  # Air

        term1 = n0 * (Mt00 + nS * Mt01)

        term2 = Mt10 + nS * Mt11

        num = term1 - term2

        den = term1 + term2

        inv_den = 1.0 / den if abs(den) > 1e-20 else 0j

        r = num * inv_den

        R = np.abs(r) ** 2

        diff = R - R_tgt

        mse += diff * diff

        # --- BACKWARD PASS (Gradients) ---

        dJ_dR = 2.0 * diff * n_pts_inv

        grad_factor = 2.0 * np.conj(r) * inv_den

        W_A = n0 * (1.0 - r) * grad_factor

        W_B = -(1.0 + r) * grad_factor

        coef_Mt00 = dJ_dR * W_A

        coef_Mt01 = dJ_dR * W_A * nS

        coef_Mt10 = dJ_dR * W_B

        coef_Mt11 = dJ_dR * W_B * nS

        C_mM00 = coef_Mt00 * mL00 + coef_Mt01 * mL01

        C_mM01 = coef_Mt00 * mL10 + coef_Mt01 * mL11

        C_mM10 = coef_Mt10 * mL00 + coef_Mt11 * mL01

        C_mM11 = coef_Mt10 * mL10 + coef_Mt11 * mL11

        dphi_ddM = k0 * nM

        dphi_deM = dphi_ddM

        dmM00_de = -sM * dphi_deM

        dmM01_de = +1j * inv_nM * cM * dphi_deM

        dmM10_de = +1j * nM * cM * dphi_deM

        dmM11_de = -sM * dphi_deM

        grad_eM += np.real(C_mM00 * dmM00_de + C_mM01 * dmM01_de + C_mM10 * dmM10_de + C_mM11 * dmM11_de)

        dphi_dn = k0 * eM

        dmM00_dn = -sM * dphi_dn

        dmM01_dn = +1j * (-inv_nM * inv_nM * sM + inv_nM * cM * dphi_dn)

        dmM10_dn = +1j * (sM + nM * cM * dphi_dn)

        dmM11_dn = -sM * dphi_dn

        sens_nM = C_mM00 * dmM00_dn + C_mM01 * dmM01_dn + C_mM10 * dmM10_dn + C_mM11 * dmM11_dn

        dJ_dnM_r[i] = sens_nM.real

        dJ_dnM_i[i] = -sens_nM.imag

        C_mL00 = coef_Mt00 * mM00 + coef_Mt10 * mM10

        C_mL10 = coef_Mt00 * mM01 + coef_Mt10 * mM11

        C_mL01 = coef_Mt01 * mM00 + coef_Mt11 * mM10

        C_mL11 = coef_Mt01 * mM01 + coef_Mt11 * mM11

        dphi_deL = k0 * nL

        dmL00_de = -sL * dphi_deL

        dmL01_de = +1j * inv_nL * cL * dphi_deL

        dmL10_de = +1j * nL * cL * dphi_deL

        dmL11_de = -sL * dphi_deL

        grad_eL += np.real(C_mL00 * dmL00_de + C_mL01 * dmL01_de + C_mL10 * dmL10_de + C_mL11 * dmL11_de)

        dphi_dnL = k0 * eL

        dmL00_dn = -sL * dphi_dnL

        dmL01_dn = +1j * (-inv_nL * inv_nL * sL + inv_nL * cL * dphi_dnL)

        dmL10_dn = +1j * (sL + nL * cL * dphi_dnL)

        dmL11_dn = -sL * dphi_dnL

        sens_nL = C_mL00 * dmL00_dn + C_mL01 * dmL01_dn + C_mL10 * dmL10_dn + C_mL11 * dmL11_dn

        dJ_dnL_r[i] = sens_nL.real

    return mse * n_pts_inv, grad_eM, grad_eL, dJ_dnM_r, dJ_dnM_i, dJ_dnL_r


def compute_metal_bilayer_gradient_analytic(
    x, num_knots, l_array, r_tgt_array, _min_knot_dist, nSub_complex_array=None
):
    """

    Wrapper calculating full gradient using Analytic TMM + FD Spline for Bilayer Metal.

    """

    grad = np.zeros_like(x)

    eM, eL, n_infini, A = x[0], x[1], x[2], x[3]

    offset = 4

    spline_knot_count = num_knots + 1

    n_knots = x[offset : offset + spline_knot_count]

    k_knots = x[offset + spline_knot_count : offset + 2 * spline_knot_count]

    lambda_internes = x[offset + 2 * spline_knot_count :]

    knot_l = np.concatenate(([l_array.min()], np.sort(lambda_internes), [l_array.max()]))

    p_spline_nk = np.concatenate((n_knots, k_knots))

    n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=False)

    nL_calc = get_nk_cauchy_simple(l_array, n_infini, A)

    if nSub_complex_array is None:
        # Note: Need get_nk_si available or passed. Assuming passed or available in scope.

        # Fallback to a default if not found? This should be passed.

        # Since get_nk_si is in materials_data.py, it's not here.

        # Caller MUST pass nSub_complex_array.

        pass

    nM_complex = n_calc - 1j * k_calc

    nL_complex = nL_calc + 0j

    mse, g_eM, g_eL, sens_nM_r, sens_nM_i, sens_nL_r = _compute_metal_tmm_gradient_kernel(
        l_array, nM_complex, eM, eL, nL_complex, nSub_complex_array, r_tgt_array
    )

    grad[0] = g_eM

    grad[1] = g_eL

    grad[2] = np.sum(sens_nL_r)  # n_inf

    grad[3] = np.sum(sens_nL_r / (l_array**2))  # A

    dJ_dn = sens_nM_r

    dJ_dk = -sens_nM_i

    basis = np.zeros((spline_knot_count, len(l_array)), dtype=np.float64)

    for i in range(spline_knot_count):
        unit_vals = np.zeros(spline_knot_count)

        unit_vals[i] = 1.0

        spline_basis = CubicSpline(knot_l, unit_vals, bc_type="natural", extrapolate=False)

        basis_vals = spline_basis(l_array)

        basis[i, :] = np.nan_to_num(basis_vals, nan=0.0)

    basis_n = basis

    basis_k = basis

    for i in range(spline_knot_count):
        grad[offset + i] = np.dot(dJ_dn, basis_n[i, :])

    for i in range(spline_knot_count):
        grad[offset + spline_knot_count + i] = np.dot(dJ_dk, basis_k[i, :])

    h_val = 1e-5

    curr_l_int = lambda_internes.copy()

    for i in range(len(lambda_internes)):
        orig = curr_l_int[i]

        curr_l_int[i] += h_val

        k_l_p = np.concatenate(([l_array.min()], np.sort(curr_l_int), [l_array.max()]))

        ns_p, ks_p = get_nk_from_spline(p_spline_nk, k_l_p, l_array, use_cache=False)

        curr_l_int[i] = orig

        dn_dp = (ns_p - n_calc) / h_val

        dk_dp = (ks_p - k_calc) / h_val

        grad[offset + 2 * num_knots + i] = np.dot(dJ_dn, dn_dp) + np.dot(dJ_dk, dk_dp)

    if eM < 1.0:
        grad[0] -= 1000.0 * (1.0 - eM)

    if eL < 1.0:
        grad[1] -= 1000.0 * (1.0 - eL)

    return mse, grad
