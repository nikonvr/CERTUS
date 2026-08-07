"""
CERTUS Gradient Optimization - Analytic Gradients Module

Extracted from certus_opt_gradients.py for better modularity.
Contains analytic gradient computation kernels for TMM optimization.
"""

import numpy as np
from numba import njit, prange
import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE
import certus.physics.certus_tmm_core as tmm_core

# ── TROIS SYMBOLES PERDUS A L'EXTRACTION, ET LE TROISIEME EST UN VRAI BUG ────────
#
# Ce module a ete extrait de `certus_opt_gradients.py` sans que ses imports suivent.
# 📏 `ruff --select F821` (masque par l'`extend-ignore` du pyproject) : `Target`,
# `Callable` et `cost_numba_fast` etaient tous les trois indefinis.
#
#   `Target` et `Callable` n'apparaissent que dans des ANNOTATIONS. Sur Python 3.14,
#   PEP 649 les evalue paresseusement, donc le module s'importait sans broncher — mais
#   `typing.get_type_hints()` sur ces fonctions echouait, et un retour a une evaluation
#   immediate aurait casse l'import.
#
#   🔴 `cost_numba_fast`, lui, est dans le CORPS de `make_cost_function` (ligne ~1181).
#   Toute fonction de cout construite par cet appel levait donc `NameError` a la
#   PREMIERE evaluation — et `make_cost_function` est une API publique, exportee dans
#   le `__all__` de `_certus_physics_impl` et re-exportee par `certus_opt_kernels`.
#
# `gradient_utils` n'importe que numpy/numba et `certus.core.certus_core` : pas de cycle.
from certus.physics.gradient_utils import cost_numba_fast

# ⚠️ `Target` sous TYPE_CHECKING, et ce n'est pas de la coquetterie : importer
# `certus_physics.structures` executerait d'abord le `__init__.py` du PAQUET
# `certus_physics`, qui importe `_certus_physics_impl`, qui importe
# `certus_opt_kernels`, qui importe CE module — cycle, et ImportError a froid.
# J'ai verifie les imports du module `structures` sans verifier ceux de son paquet ;
# c'est la meme erreur que de lire un critere sur la mauvaise source.
# `Target` n'apparait que dans une annotation, donc un import de typage suffit.
if TYPE_CHECKING:
    from certus_physics.structures import Target
from certus.physics.certus_optical_models import (
    get_nk_from_spline,
    get_nk_cauchy_simple,
    get_nk_cauchy_wrapper,
    sellmeier_n_array,
    get_nk_cauchy,
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
    epsilon_to_nk,
)
from scipy.interpolate import CubicSpline
from certus.physics.gradient_utils import compute_mse_vectorized


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_epsilon2_gradient_kernel(
    E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, Eu: float
) -> np.ndarray:
    """Computes [eps2, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]"""

    n = len(E_array)

    result = np.zeros((7, n), dtype=np.float64)

    E0_sq = E0 * E0

    C_sq = C * C

    A_E0_C = A * E0 * C

    delta = 0.01

    E_edge = Eg + delta

    E_edge_sq = E_edge * E_edge

    term_E0 = E_edge_sq - E0_sq

    D_edge = term_E0 * term_E0 + C_sq * E_edge_sq

    inv_D_edge = 1.0 / D_edge

    num_edge = A_E0_C * delta * delta

    eps2_edge = (num_edge * inv_D_edge / E_edge) if E_edge > 1e-12 else 0.0

    dDedge_dEg = 4.0 * term_E0 * E_edge + 2.0 * C_sq * E_edge

    dDedge_dE0 = -4.0 * E0 * term_E0

    dDedge_dC = 2.0 * C * E_edge_sq

    if eps2_edge > 1e-12:
        d_eps2_edge_dEg = eps2_edge * (-dDedge_dEg * inv_D_edge - 1.0 / E_edge)

        d_eps2_edge_dA = eps2_edge * (1.0 / A)

        d_eps2_edge_dE0 = eps2_edge * (1.0 / E0 - dDedge_dE0 * inv_D_edge)

        d_eps2_edge_dC = eps2_edge * (1.0 / C - dDedge_dC * inv_D_edge)

    else:
        d_eps2_edge_dEg = 0.0

        d_eps2_edge_dA = 0.0

        d_eps2_edge_dE0 = 0.0

        d_eps2_edge_dC = 0.0

    Eu_safe = max(Eu, 1e-6)

    inv_Eu = 1.0 / Eu_safe

    for i in prange(n):
        E = E_array[i]

        if E > Eg:
            E_sq = E * E

            diff = E - Eg

            diff_sq = diff * diff

            term_E0_loc = E_sq - E0_sq

            D = term_E0_loc * term_E0_loc + C_sq * E_sq

            inv_D = 1.0 / D

            val = (A_E0_C * diff_sq) * inv_D / E

            result[0, i] = val

            if val > 1e-12:
                result[1, i] = val * (-2.0 / diff)

                result[2, i] = val / A

                dD_dE0 = -4.0 * E0 * term_E0_loc

                result[3, i] = val * (1.0 / E0 - dD_dE0 * inv_D)

                dD_dC = 2.0 * C * E_sq

                result[4, i] = val * (1.0 / C - dD_dC * inv_D)

        else:
            if eps2_edge < 1e-12:
                result[0, i] = 0.0

            else:
                arg = (E - Eg - delta) * inv_Eu

                # Clamp to prevent exponential overflow/underflow
                arg_clamped = min(max(arg, -700.0), 700.0)

                exp_val = np.exp(arg_clamped)

                val = eps2_edge * exp_val

                result[0, i] = val

                result[1, i] = d_eps2_edge_dEg * exp_val + val * (-inv_Eu)

                result[2, i] = d_eps2_edge_dA * exp_val

                result[3, i] = d_eps2_edge_dE0 * exp_val

                result[4, i] = d_eps2_edge_dC * exp_val

                result[5, i] = val * (-arg * inv_Eu)

    return result


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_epsilon1_gradient_kernel(
    E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float
) -> np.ndarray:
    """Computes [eps1, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]"""

    n = len(E_array)

    result = np.zeros((7, n), dtype=np.float64)

    E0_sq = E0 * E0

    Eg_sq = Eg * Eg

    C_sq = C * C

    gamma_sq = E0_sq - C_sq / 2.0

    alpha_sq = max(4.0 * E0_sq - C_sq, 1e-12)

    alpha = np.sqrt(alpha_sq)

    d_alpha_dE0 = (4.0 * E0 / alpha) if alpha > 1e-12 else 0.0

    d_alpha_dC = (-C / alpha) if alpha > 1e-12 else 0.0

    d_gamma2_dE0 = 2.0 * E0

    d_gamma2_dC = -C

    denom_log_norm_sq = (E0_sq - Eg_sq) ** 2 + C_sq * Eg_sq

    # If Eg or C are extremely small (>0 but subnormal), the sum of squares can
    # round to 0 and cause a division by zero on inv_denom_log_norm (see L-BFGS-B outside realistic bounds).
    denom_log_norm_sq = max(denom_log_norm_sq, 1e-120)

    denom_log_norm = np.sqrt(denom_log_norm_sq)

    inv_denom_log_norm = 1.0 / denom_log_norm

    d_DLN2_dEg = -4.0 * Eg * (E0_sq - Eg_sq) + 2.0 * Eg * C_sq

    d_DLN2_dE0 = 4.0 * E0 * (E0_sq - Eg_sq)

    d_DLN2_dC = 2.0 * C * Eg_sq

    d_DLN_dEg = 0.5 * inv_denom_log_norm * d_DLN2_dEg

    d_DLN_dE0 = 0.5 * inv_denom_log_norm * d_DLN2_dE0

    d_DLN_dC = 0.5 * inv_denom_log_norm * d_DLN2_dC

    A_E0_C = A * E0 * C

    two_A_E0_C_Eg = 2.0 * A_E0_C * Eg

    inv_PI = 1.0 / PI

    for i in prange(n):
        E = E_array[i]

        E_sq = E * E

        zeta4 = (E_sq - E0_sq) ** 2 + C_sq * E_sq

        zeta4 = max(zeta4, 1e-12)

        inv_zeta4 = 1.0 / zeta4

        d_zeta4_dE0 = -4.0 * E0 * (E_sq - E0_sq)

        d_zeta4_dC = 2.0 * C * E_sq

        diff_sq = Eg_sq - E_sq

        # Log1 / Log2 : singularities if E == Eg (diff_sq -> 0) or numerical quasi-degeneracy.

        _diff_eps = 1e-14

        # Log1

        val_log1 = 0.0

        d_log1_dEg = 0.0

        if E != Eg:
            arg_log1 = np.abs((Eg - E) / (Eg + E))

            val_log1 = np.log(arg_log1) if arg_log1 > 0 else -100.0

            if np.abs(diff_sq) > _diff_eps:
                d_log1_dEg = 2.0 * E / diff_sq

            else:
                d_log1_dEg = 0.0

        # Log2

        arg_log2 = np.abs(diff_sq)

        val_log2_part = np.log(arg_log2) if arg_log2 > 0 else -100.0

        val_log2 = val_log2_part - np.log(denom_log_norm)

        if np.abs(diff_sq) > _diff_eps:
            d_log2_dEg = 2.0 * Eg / diff_sq - d_DLN_dEg * inv_denom_log_norm

        else:
            d_log2_dEg = -d_DLN_dEg * inv_denom_log_norm

        d_log2_dE0 = -d_DLN_dE0 * inv_denom_log_norm

        d_log2_dC = -d_DLN_dC * inv_denom_log_norm

        # al, aa

        al = (Eg_sq - E0_sq) * E_sq + Eg_sq * C_sq - E0_sq * (E0_sq + 3.0 * Eg_sq)

        d_al_dEg = 2 * Eg * E_sq + 2 * Eg * C_sq - E0_sq * 6.0 * Eg

        d_al_dE0 = -2 * E0 * E_sq - (4.0 * E0**3 + 6.0 * E0 * Eg_sq)

        d_al_dC = Eg_sq * 2.0 * C

        aa = (E_sq - E0_sq) * (E0_sq + Eg_sq) + Eg_sq * C_sq

        d_aa_dEg = (E_sq - E0_sq) * 2.0 * Eg + 2.0 * Eg * C_sq

        d_aa_dE0 = (-2 * E0) * (E0_sq + Eg_sq) + (E_sq - E0_sq) * (2 * E0)

        d_aa_dC = Eg_sq * 2.0 * C

        # Term 1

        E_safe = max(E, 1e-18)

        K1 = -A_E0_C * inv_PI / E_safe

        T1 = K1 * (E_sq + Eg_sq) * inv_zeta4 * val_log1

        dT1_dA = T1 / A

        dT1_dEg = K1 * (2.0 * Eg * inv_zeta4 * val_log1 + (E_sq + Eg_sq) * inv_zeta4 * d_log1_dEg)

        dT1_dE0 = (K1 / E0) * (E_sq + Eg_sq) * inv_zeta4 * val_log1 + K1 * (E_sq + Eg_sq) * (
            -(inv_zeta4**2) * d_zeta4_dE0
        ) * val_log1

        dT1_dC = (K1 / C) * (E_sq + Eg_sq) * inv_zeta4 * val_log1 + K1 * (E_sq + Eg_sq) * (
            -(inv_zeta4**2) * d_zeta4_dC
        ) * val_log1

        # Term 2

        K2 = two_A_E0_C_Eg * inv_PI

        T2 = K2 * inv_zeta4 * val_log2

        dT2_dA = T2 / A

        dT2_dEg = (K2 / Eg) * inv_zeta4 * val_log2 + K2 * inv_zeta4 * d_log2_dEg

        dT2_dE0 = (
            (K2 / E0) * inv_zeta4 * val_log2
            + K2 * (-(inv_zeta4**2) * d_zeta4_dE0) * val_log2
            + K2 * inv_zeta4 * d_log2_dE0
        )

        dT2_dC = (
            (K2 / C) * inv_zeta4 * val_log2
            + K2 * (-(inv_zeta4**2) * d_zeta4_dC) * val_log2
            + K2 * inv_zeta4 * d_log2_dC
        )

        # Term 3

        T3 = 0.0

        dT3_dA = 0.0

        dT3_dEg = 0.0

        dT3_dE0 = 0.0

        dT3_dC = 0.0

        if alpha > 1e-12:
            arg3 = (E0_sq + Eg_sq + alpha * Eg) / (E0_sq + Eg_sq - alpha * Eg)

            val_log3 = np.log(arg3)

            pre = (A * C) / (2.0 * PI)

            denom_T3 = zeta4 * alpha * E0

            term_frac = al / denom_T3

            T3 = pre * term_frac * val_log3

            N3 = E0_sq + Eg_sq + alpha * Eg

            D3 = E0_sq + Eg_sq - alpha * Eg

            dN3_dEg = 2 * Eg + alpha

            dD3_dEg = 2 * Eg - alpha

            dN3_dE0 = 2 * E0 + d_alpha_dE0 * Eg

            dD3_dE0 = 2 * E0 - d_alpha_dE0 * Eg

            dN3_dC = d_alpha_dC * Eg

            dD3_dC = -d_alpha_dC * Eg

            d_log3_dEg = dN3_dEg / N3 - dD3_dEg / D3

            d_log3_dE0 = dN3_dE0 / N3 - dD3_dE0 / D3

            d_log3_dC = dN3_dC / N3 - dD3_dC / D3

            dT3_dA = T3 / A

            dT3_dEg = pre * (d_al_dEg / denom_T3) * val_log3 + pre * term_frac * d_log3_dEg

            d_denomT3_dE0 = d_zeta4_dE0 * alpha * E0 + zeta4 * d_alpha_dE0 * E0 + zeta4 * alpha

            d_term_frac_dE0 = (d_al_dE0 * denom_T3 - al * d_denomT3_dE0) / (denom_T3**2)

            dT3_dE0 = pre * d_term_frac_dE0 * val_log3 + pre * term_frac * d_log3_dE0

            d_denomT3_dC = d_zeta4_dC * alpha * E0 + zeta4 * d_alpha_dC * E0

            d_term_frac_dC = (d_al_dC * denom_T3 - al * d_denomT3_dC) / (denom_T3**2)

            dT3_dC = (T3 / C) + pre * d_term_frac_dC * val_log3 + pre * term_frac * d_log3_dC

        # Term 4

        atan1 = np.arctan((2 * Eg + alpha) / C)

        atan2 = np.arctan((2 * Eg - alpha) / C)

        sum_atan = PI - atan1 - atan2

        K4 = -A / (PI * E0)

        frac4 = aa * inv_zeta4

        T4 = K4 * frac4 * sum_atan

        u1 = (2 * Eg + alpha) / C

        u2 = (2 * Eg - alpha) / C

        fac1 = 1.0 / (1.0 + u1**2)

        fac2 = 1.0 / (1.0 + u2**2)

        du1_dEg = 2.0 / C

        du2_dEg = 2.0 / C

        du1_dE0 = d_alpha_dE0 / C

        du2_dE0 = -d_alpha_dE0 / C

        du1_dC = -(2 * Eg + alpha) / (C * C) + d_alpha_dC / C

        du2_dC = -(2 * Eg - alpha) / (C * C) - d_alpha_dC / C

        d_sum_atan_dEg = -(fac1 * du1_dEg + fac2 * du2_dEg)

        d_sum_atan_dE0 = -(fac1 * du1_dE0 + fac2 * du2_dE0)

        d_sum_atan_dC = -(fac1 * du1_dC + fac2 * du2_dC)

        dT4_dA = T4 / A

        dT4_dEg = K4 * (d_aa_dEg * inv_zeta4) * sum_atan + K4 * frac4 * d_sum_atan_dEg

        dK4_dE0 = -K4 / E0

        d_frac4_dE0 = d_aa_dE0 * inv_zeta4 + aa * (-(inv_zeta4**2) * d_zeta4_dE0)

        dT4_dE0 = dK4_dE0 * frac4 * sum_atan + K4 * d_frac4_dE0 * sum_atan + K4 * frac4 * d_sum_atan_dE0

        d_frac4_dC = d_aa_dC * inv_zeta4 + aa * (-(inv_zeta4**2) * d_zeta4_dC)

        dT4_dC = K4 * d_frac4_dC * sum_atan + K4 * frac4 * d_sum_atan_dC

        # Term 5

        T5 = 0.0

        dT5_dA = 0.0

        dT5_dEg = 0.0

        dT5_dE0 = 0.0

        dT5_dC = 0.0

        if alpha > 1e-12:
            arg5 = 2.0 * (Eg_sq - gamma_sq) / max(alpha * C, 1e-12)

            atan3 = np.arctan(arg5)

            brack5 = PI / 2.0 - atan3

            K5 = 4.0 * A * E0 * Eg / (PI * alpha)

            term5_mid = (E_sq - gamma_sq) * inv_zeta4

            T5 = K5 * term5_mid * brack5

            dnum_dEg = 4.0 * Eg

            dnum_dE0 = -2.0 * d_gamma2_dE0

            dnum_dC = -2.0 * d_gamma2_dC

            dden_dE0 = d_alpha_dE0 * C

            dden_dC = d_alpha_dC * C + alpha

            den_sq = (alpha * C) ** 2

            fac3 = 1.0 / (1.0 + arg5**2)

            d_arg5_dEg = (dnum_dEg * alpha * C) / den_sq

            d_arg5_dE0 = (dnum_dE0 * alpha * C - 2 * (Eg_sq - gamma_sq) * dden_dE0) / den_sq

            d_arg5_dC = (dnum_dC * alpha * C - 2 * (Eg_sq - gamma_sq) * dden_dC) / den_sq

            d_brack5_dEg = -fac3 * d_arg5_dEg

            d_brack5_dE0 = -fac3 * d_arg5_dE0

            d_brack5_dC = -fac3 * d_arg5_dC

            dT5_dA = T5 / A

            dK5_dEg = K5 / Eg

            dT5_dEg = dK5_dEg * term5_mid * brack5 + K5 * term5_mid * d_brack5_dEg

            d_K5_dE0 = K5 / E0 - K5 / alpha * d_alpha_dE0

            d_term5_mid_dE0 = (-d_gamma2_dE0 * inv_zeta4) + (E_sq - gamma_sq) * (-(inv_zeta4**2) * d_zeta4_dE0)

            dT5_dE0 = d_K5_dE0 * term5_mid * brack5 + K5 * d_term5_mid_dE0 * brack5 + K5 * term5_mid * d_brack5_dE0

            d_K5_dC = -K5 / alpha * d_alpha_dC

            d_term5_mid_dC = (-d_gamma2_dC * inv_zeta4) + (E_sq - gamma_sq) * (-(inv_zeta4**2) * d_zeta4_dC)

            dT5_dC = d_K5_dC * term5_mid * brack5 + K5 * d_term5_mid_dC * brack5 + K5 * term5_mid * d_brack5_dC

        result[0, i] = eps_inf + T1 + T2 + T3 + T4 + T5

        result[1, i] = dT1_dEg + dT2_dEg + dT3_dEg + dT4_dEg + dT5_dEg

        result[2, i] = dT1_dA + dT2_dA + dT3_dA + dT4_dA + dT5_dA

        result[3, i] = dT1_dE0 + dT2_dE0 + dT3_dE0 + dT4_dE0 + dT5_dE0

        result[4, i] = dT1_dC + dT2_dC + dT3_dC + dT4_dC + dT5_dC

        result[6, i] = 1.0  # deps_inf

    return result


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_tlu_derivatives_kernel(
    E_array: np.ndarray,
    Eg: float,
    A: float,
    E0: float,
    C: float,
    Eu: float,
    eps_inf: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Computes n, k and their derivatives w.r.t parameters"""

    n_pts = len(E_array)

    res1 = _compute_epsilon1_gradient_kernel(E_array, Eg, A, E0, C, eps_inf)

    res2 = _compute_epsilon2_gradient_kernel(E_array, Eg, A, E0, C, Eu)

    n_arr = np.empty(n_pts, dtype=np.float64)

    k_arr = np.empty(n_pts, dtype=np.float64)

    dn_dp = np.zeros((6, n_pts), dtype=np.float64)

    dk_dp = np.zeros((6, n_pts), dtype=np.float64)

    for i in prange(n_pts):
        e1 = res1[0, i]

        e2 = res2[0, i]

        eps_mag = np.sqrt(e1 * e1 + e2 * e2)

        n_val = np.sqrt(max((eps_mag + e1) / 2.0, 1e-12))

        k_val = np.sqrt(max((eps_mag - e1) / 2.0, 0.0))

        n_arr[i] = n_val

        k_arr[i] = k_val

        denom = max(2.0 * (n_val * n_val + k_val * k_val), 1e-12)

        inv_denom = 1.0 / denom

        for p in range(6):
            de1 = res1[p + 1, i]

            de2 = res2[p + 1, i]

            dn = (n_val * de1 + k_val * de2) * inv_denom

            dk = (n_val * de2 - k_val * de1) * inv_denom

            dn_dp[p, i] = dn

            dk_dp[p, i] = dk

    return n_arr, k_arr, dn_dp, dk_dp


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _compute_single_layer_sensitivity_kernel(
    wavelength: float, nr: float, ni: float, d: float, ns: float
) -> tuple[float, float, float, float, float, float]:
    """Computes derivatives of T and R w.r.t film index (nr, ni=k>=0) and d.

    Internal convention: (-1j, n+ik) baked-in - self-consistent, R/T/gradients invariant.

    """

    k0 = TWO_PI / wavelength

    n0 = 1.0  # Air

    phi_r = k0 * nr * d

    phi_i = k0 * ni * d

    cr = np.cos(phi_r)

    sr = np.sin(phi_r)

    ch = np.cosh(phi_i)

    sh = np.sinh(phi_i)

    c_real = cr * ch

    c_imag = -sr * sh

    s_real = sr * ch

    s_imag = cr * sh

    fac = k0 * d

    dc_dnr_r = -s_real * fac

    dc_dnr_i = -s_imag * fac

    ds_dnr_r = c_real * fac

    ds_dnr_i = c_imag * fac

    dc_dni_r = s_imag * fac

    dc_dni_i = -s_real * fac

    ds_dni_r = -c_imag * fac

    ds_dni_i = c_real * fac

    n2 = nr * nr + ni * ni

    inv_n2 = 1.0 / max(n2, 1e-14)

    inv_n_r = nr * inv_n2

    inv_n_i = -ni * inv_n2

    dninv_dnr_r = (ni * ni - nr * nr) * inv_n2 * inv_n2

    dninv_dnr_i = 2.0 * nr * ni * inv_n2 * inv_n2

    dninv_dni_r = -2.0 * nr * ni * inv_n2 * inv_n2

    dninv_dni_i = (ni * ni - nr * nr) * inv_n2 * inv_n2

    def mul_c(r1, i1, r2, i2):

        return r1 * r2 - i1 * i2, r1 * i2 + i1 * r2

    def get_dM01(dsr, dsi, sr, si, invr, invi, dinvr, dinvi):

        # (ds_imag - i*ds_real) * (inv_n_r + i*inv_n_i) + (s_imag - i*s_real) * (dinvr + i*dinvi)

        t1r, t1i = mul_c(dsi, -dsr, invr, invi)

        t2r, t2i = mul_c(si, -sr, dinvr, dinvi)

        return t1r + t2r, t1i + t2i

    def get_dM10(dsr, dsi, sr, si, nr, ni, dnr, dni):

        # (ds_imag - i*ds_real) * (nr + i*ni) + (s_imag - i*s_real) * (dnr + i*dni)

        t1r, t1i = mul_c(dsi, -dsr, nr, ni)

        t2r, t2i = mul_c(si, -sr, dnr, dni)

        return t1r + t2r, t1i + t2i

    dM00_dnr_r, dM00_dnr_i = dc_dnr_r, dc_dnr_i

    dM11_dnr_r, dM11_dnr_i = dc_dnr_r, dc_dnr_i

    dM01_dnr_r, dM01_dnr_i = get_dM01(ds_dnr_r, ds_dnr_i, s_real, s_imag, inv_n_r, inv_n_i, dninv_dnr_r, dninv_dnr_i)

    dM10_dnr_r, dM10_dnr_i = get_dM10(ds_dnr_r, ds_dnr_i, s_real, s_imag, nr, ni, 1.0, 0.0)

    dM00_dni_r, dM00_dni_i = dc_dni_r, dc_dni_i

    dM11_dni_r, dM11_dni_i = dc_dni_r, dc_dni_i

    dM01_dni_r, dM01_dni_i = get_dM01(ds_dni_r, ds_dni_i, s_real, s_imag, inv_n_r, inv_n_i, dninv_dni_r, dninv_dni_i)

    dM10_dni_r, dM10_dni_i = get_dM10(ds_dni_r, ds_dni_i, s_real, s_imag, nr, ni, 0.0, 1.0)

    M00r, M00i = c_real, c_imag

    M01r, M01i = mul_c(s_imag, -s_real, inv_n_r, inv_n_i)

    M10r, M10i = mul_c(s_imag, -s_real, nr, ni)

    M11r, M11i = c_real, c_imag

    def compute_denom_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        pr = n0 * dm00r + n0 * ns * dm01r + dm10r + ns * dm11r

        pi = n0 * dm00i + n0 * ns * dm01i + dm10i + ns * dm11i

        return pr, pi

    dD_dnr_r, dD_dnr_i = compute_denom_deriv(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dD_dni_r, dD_dni_i = compute_denom_deriv(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    Dr = n0 * M00r + n0 * ns * M01r + M10r + ns * M11r

    Di = n0 * M00i + n0 * ns * M01i + M10i + ns * M11i

    magD2 = Dr * Dr + Di * Di

    inv_magD2 = 1.0 / max(magD2, 1e-20)

    T_val = 4.0 * n0 * ns * inv_magD2

    def calc_dT(dDr, dDi):

        re_DD = dDr * Dr + dDi * Di

        return -T_val * (2.0 * re_DD * inv_magD2)

    dT_dnr = calc_dT(dD_dnr_r, dD_dnr_i)

    dT_dni = calc_dT(dD_dni_r, dD_dni_i)

    Nr = n0 * M00r + n0 * ns * M01r - M10r - ns * M11r

    Ni = n0 * M00i + n0 * ns * M01i - M10i - ns * M11i

    magN2 = Nr * Nr + Ni * Ni

    R_val = magN2 * inv_magD2

    def compute_num_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        qr = n0 * dm00r + n0 * ns * dm01r - dm10r - ns * dm11r

        qi = n0 * dm00i + n0 * ns * dm01i - dm10i - ns * dm11i

        return qr, qi

    dN_dnr_r, dN_dnr_i = compute_num_deriv(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dN_dni_r, dN_dni_i = compute_num_deriv(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    def calc_dR(dNr, dNi, dDr, dDi):

        re_NN = dNr * Nr + dNi * Ni

        re_DD = dDr * Dr + dDi * Di

        return (2.0 * re_NN - R_val * 2.0 * re_DD) * inv_magD2

    dR_dnr = calc_dR(dN_dnr_r, dN_dnr_i, dD_dnr_r, dD_dnr_i)

    dR_dni = calc_dR(dN_dni_r, dN_dni_i, dD_dni_r, dD_dni_i)

    dcos_dd_r, dcos_dd_i = mul_c(-s_real, -s_imag, k0 * nr, k0 * ni)

    dsin_dd_r, dsin_dd_i = mul_c(c_real, c_imag, k0 * nr, k0 * ni)

    dm01_dd_r, dm01_dd_i = mul_c(dsin_dd_i, -dsin_dd_r, inv_n_r, inv_n_i)

    dm10_dd_r, dm10_dd_i = mul_c(dsin_dd_i, -dsin_dd_r, nr, ni)

    dD_dd_r, dD_dd_i = compute_denom_deriv(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    dN_dd_r, dN_dd_i = compute_num_deriv(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    dT_dd = calc_dT(dD_dd_r, dD_dd_i)

    dR_dd = calc_dR(dN_dd_r, dN_dd_i, dD_dd_r, dD_dd_i)

    r_b = (1.0 - ns) / (1.0 + ns)

    R_b = r_b * r_b

    T_b = 1.0 - R_b

    Nr_p = ns * M00r + ns * M01r - M10r - M11r

    Ni_p = ns * M00i + ns * M01i - M10i - M11i

    R_prime = (Nr_p * Nr_p + Ni_p * Ni_p) * inv_magD2

    def calc_dR_prime(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        qrp = ns * dm00r + ns * dm01r - dm10r - dm11r

        qip = ns * dm00i + ns * dm01i - dm10i - dm11i

        re_NPN = qrp * Nr_p + qip * Ni_p

        dDDr, dDDi = compute_denom_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i)

        re_DD = dDDr * Dr + dDDi * Di

        return (2.0 * re_NPN - R_prime * 2.0 * re_DD) * inv_magD2

    dR_p_dnr = calc_dR_prime(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dR_p_dni = calc_dR_prime(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    dR_p_dd = calc_dR_prime(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    denom_corr = 1.0 - R_prime * R_b

    inv_dc = 1.0 / denom_corr if abs(denom_corr) > 1e-12 else 0.0

    facT = T_b * inv_dc

    facTR = (T_val * T_b * R_b) * (inv_dc * inv_dc)

    dT_dnr_corr = facT * dT_dnr + facTR * dR_p_dnr

    dT_dni_corr = facT * dT_dni + facTR * dR_p_dni

    dT_dd_corr = facT * dT_dd + facTR * dR_p_dd

    facRR = (T_val * T_val * R_b * R_b) * (inv_dc * inv_dc)

    facRT = (2.0 * T_val * R_b) * inv_dc

    dR_dnr_corr = dR_dnr + facRT * dT_dnr + facRR * dR_p_dnr

    dR_dni_corr = dR_dni + facRT * dT_dni + facRR * dR_p_dni

    dR_dd_corr = dR_dd + facRT * dT_dd + facRR * dR_p_dd

    return dT_dnr_corr, dT_dni_corr, dR_dnr_corr, dR_dni_corr, dT_dd_corr, dR_dd_corr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_single_layer_sensitivity_array(
    wavelengths: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d: float,
    n_sub: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized wrapper: calls _compute_single_layer_sensitivity_kernel via prange.

    Returns six (n_pix,) arrays: dT_dn, dT_dk, dR_dn, dR_dk, dT_dd, dR_dd.
    Eliminates CPython→Numba dispatch overhead (one JIT entry instead of n_pix).
    """
    n = len(wavelengths)
    dTdn = np.empty(n, dtype=np.float64)
    dTdk = np.empty(n, dtype=np.float64)
    dRdn = np.empty(n, dtype=np.float64)
    dRdk = np.empty(n, dtype=np.float64)
    dTdd = np.empty(n, dtype=np.float64)
    dRdd = np.empty(n, dtype=np.float64)
    for i in prange(n):
        a, b, c, e, f, g = _compute_single_layer_sensitivity_kernel(wavelengths[i], n_arr[i], k_arr[i], d, n_sub[i])
        dTdn[i] = a
        dTdk[i] = b
        dRdn[i] = c
        dRdk[i] = e
        dTdd[i] = f
        dRdd[i] = g
    return dTdn, dTdk, dRdn, dRdk, dTdd, dRdd


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_index_cost_gradient_kernel(
    wls: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d: float,
    n_sub: np.ndarray,
    target_T: np.ndarray,
    target_R: np.ndarray,
    weights: np.ndarray,
    use_T: bool,
    use_R: bool,
    dn_dp: np.ndarray,
    dk_dp: np.ndarray,
    T_substrate: np.ndarray,
    _R_substrate: np.ndarray,
    use_normalized: bool,
    weight_T: float,
    weight_R: float,
) -> np.ndarray:
    """Computes gradient of MSE w.r.t parameters (race-free parallel reduction).

    Normalization: T_nu = T/T_sub, R_nu = R/T_sub. Guards: T_sub >= 1e-6 (T), >= 0.05 (R)

    match certus_core.T_SUB_MIN_T_NORM and T_SUB_MIN_R_NORM; literals kept here for Numba."""

    n_pts = len(wls)
    count_T = 0
    n_valid_T = 1
    count_R = 0
    n_valid_R = 1

    for i in range(n_pts):
        if weights[i] > 1e-12:
            if use_T:
                count_T += 1

            if use_R:
                count_R += 1

    if count_T > 0:
        n_valid_T = count_T

    if count_R > 0:
        n_valid_R = count_R

    # Per-wavelength gradient (avoid race condition on shared grad)

    grad_per_wl = np.zeros((n_pts, 7), dtype=np.float64)

    for i in prange(n_pts):
        wl = wls[i]

        if weights[i] < 1e-12:
            continue

        nr = n_arr[i]

        ni = k_arr[i]

        ns = n_sub[i]

        dTdn, dTdk, dRdn, dRdk, dTdd, dRdd = _compute_single_layer_sensitivity_kernel(wl, nr, ni, d, ns)

        w = weights[i]

        fac_T = 0.0

        fac_R = 0.0

        # Fused R+T single call (same values as cost)

        val_R, val_T = tmm_core.calculate_transmission_single(wl, nr, ni, d, ns)

        if use_T:
            if use_normalized:
                scale_T = 1.0 / max(T_substrate[i], 1e-6)

                diff_T = (val_T * scale_T) - target_T[i]

            else:
                scale_T = 1.0

                diff_T = val_T - target_T[i]

            fac_T = (2.0 * w * diff_T * weight_T / n_valid_T) * scale_T

        if use_R:
            if use_normalized:
                # Physics Guard: Avoid explosion when T -> 0

                if T_substrate[i] >= 0.05:
                    scale_R = 1.0 / T_substrate[i]

                else:
                    scale_R = 0.0  # Effectively ignore this point in gradient

                diff_R = (val_R * scale_R) - target_R[i]

            else:
                scale_R = 1.0

                diff_R = val_R - target_R[i]

            fac_R = (2.0 * w * diff_R * weight_R / n_valid_R) * scale_R

        grad_per_wl[i, 0] = (fac_T * dTdd + fac_R * dRdd) if use_T or use_R else 0.0

        for p in range(6):
            dnp = dn_dp[p, i]

            dkp = dk_dp[p, i]

            term = 0.0

            if use_T:
                term += fac_T * (dTdn * dnp + dTdk * dkp)

            if use_R:
                term += fac_R * (dRdn * dnp + dRdk * dkp)

            grad_per_wl[i, p + 1] = term

    # Reduction (sequential, fast for 7 params)

    grad = np.zeros(7, dtype=np.float64)

    for p in range(7):
        s = 0.0

        for i in range(n_pts):
            s += grad_per_wl[i, p]

        grad[p] = s

    return grad


def prepare_targets_vectorized(wls: np.ndarray, targets: list[Target]) -> tuple[np.ndarray, np.ndarray]:
    """

    Prepares target values and weights for optimization.

    Weights combine user target weight (tgt.w) with spectral quadrature

    Delta ln lambda (trapezoidal) for density-corrected broadband optimization.

    """

    from certus.utils.certus_index_utils import spectral_rmse_weights

    vals = np.zeros(len(wls), dtype=np.float64)

    weights = np.zeros(len(wls), dtype=np.float64)

    spec_w = spectral_rmse_weights(np.asarray(wls, dtype=np.float64))

    for t in targets:
        if not t.valid():
            continue

        mask = (wls >= t.lmin) & (wls <= t.lmax)

        if not np.any(mask):
            continue

        # Target linear interpolation

        denom = t.lmax - t.lmin

        if denom < 1e-9:
            denom = 1e-9

        slope = (t.tmax - t.tmin) / denom

        vals[mask] = t.tmin + slope * (wls[mask] - t.lmin)

        weights[mask] = t.w * spec_w[mask]

    return vals, weights


def make_cost_function(
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
) -> Callable[[np.ndarray], float]:
    """

    Factory that creates an optimized cost function with pre-converted arrays.

    All arrays in f64/c128 for double precision.

    """

    # TMM arrays: c128/f64 for full double precision

    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)

    n_layers_T_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)

    # Targets: f64

    tgt_vals_f64 = np.ascontiguousarray(tgt_vals, dtype=np.float64)

    tgt_weights_f64 = np.ascontiguousarray(tgt_weights, dtype=np.float64)

    if has_back:
        n_back_T_c128 = np.ascontiguousarray(n_back_T, dtype=np.complex128)

        d_back_f64 = np.ascontiguousarray(d_back, dtype=np.float64)

    else:
        n_back_T_c128 = np.zeros((len(wls), 0), dtype=np.complex128)

        d_back_f64 = np.zeros(0, dtype=np.float64)

    def cost_func(ep: np.ndarray) -> float:

        ep_f64 = np.ascontiguousarray(ep, dtype=np.float64)

        return cost_numba_fast(
            ep_f64,
            n_layers_T_c128,
            n_sub_c128,
            wls_f64,
            tgt_vals_f64,
            tgt_weights_f64,
            min_d,
            has_back,
            n_back_T_c128,
            d_back_f64,
        )

    return cost_func


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_gradient_analytic_kernel(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    """

    Analytic gradient kernel for TMM (Opus 4.6 - parallelized over wavelengths).

    Each wavelength is independent (own forward/backward TMM pass).

    Per-wavelength gradient contributions are accumulated then reduced.

    """

    n_wls = len(wls)

    n_layers = len(ep)

    n_vars = len(var_idx)

    # Output arrays

    T_arr = np.empty(n_wls, dtype=np.float64)

    # Per-wavelength accumulators (avoid race conditions with prange)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)

    err_per_wl = np.zeros(n_wls, dtype=np.float64)

    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    # Pre-allocated buffers for forward/backward passes to avoid heap allocation inside prange loop
    M_before_buf = np.zeros((n_wls, n_layers + 1, 8), dtype=np.float64)
    M_after_buf = np.zeros((n_wls, n_layers + 1, 8), dtype=np.float64)

    for i_wl in prange(n_wls):
        # Thread-local M_before / M_after (stack-allocated per iteration)

        M_before = M_before_buf[i_wl]

        M_after = M_after_buf[i_wl]

        wl = wls[i_wl]

        inv_wl = 1.0 / wl

        two_pi_inv_wl = TWO_PI * inv_wl

        n_s = n_sub[i_wl]

        ns_r = n_s.real

        ns_i = n_s.imag

        # === FORWARD PASS: Compute M_before[k] ===

        M_before[0, 0] = 1.0  # Re(M00)

        M_before[0, 1] = 0.0  # Im(M00)

        M_before[0, 2] = 0.0  # Re(M01)

        M_before[0, 3] = 0.0  # Im(M01)

        M_before[0, 4] = 0.0  # Re(M10)

        M_before[0, 5] = 0.0  # Im(M10)

        M_before[0, 6] = 1.0  # Re(M11)

        M_before[0, 7] = 0.0  # Im(M11)

        Ar, Ai = 1.0, 0.0

        Br, Bi = 0.0, 0.0

        Cr, Ci = 0.0, 0.0

        Dr, Di = 1.0, 0.0

        for k in range(n_layers):
            n_k = n_layers_T[i_wl, k]

            nr = n_k.real

            ni = n_k.imag

            d_k = ep[k]

            phi_base = two_pi_inv_wl * d_k

            if abs(ni) < 1e-14:
                phi = phi_base * nr

                cp = np.cos(phi)

                sp = np.sin(phi)

                inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                m01i = sp * inv_n

                m10i = sp * nr

                # M_before_new = M_before_old * L (Lossless)

                NAr = Ar * cp + Bi * m10i

                NAi = Ai * cp - Br * m10i

                NBr = Ai * m01i + Br * cp

                NBi = -Ar * m01i + Bi * cp

                NCr = Cr * cp + Di * m10i

                NCi = Ci * cp - Dr * m10i

                NDr = Ci * m01i + Dr * cp

                NDi = -Cr * m01i + Di * cp

            else:
                phr = phi_base * nr

                phi_img = phi_base * ni

                cr = np.cos(phr) * np.cosh(phi_img)

                ci = -np.sin(phr) * np.sinh(phi_img)

                sr = np.sin(phr) * np.cosh(phi_img)

                si = np.cos(phr) * np.sinh(phi_img)

                eta2 = nr * nr + ni * ni

                if eta2 < 1e-24:
                    eta2 = 1e-24

                inv_eta = 1.0 / eta2

                etr = nr * inv_eta

                eti = -ni * inv_eta

                m01r = sr * eti + si * etr

                m01i = si * eti - sr * etr

                m10r = nr * si + ni * sr

                m10i = ni * si - nr * sr

                # M_before_new = M_before_old * L (Absorbing)

                NAr = Ar * cr - Ai * ci + Br * m10r - Bi * m10i

                NAi = Ar * ci + Ai * cr + Br * m10i + Bi * m10r

                NBr = Ar * m01r - Ai * m01i + Br * cr - Bi * ci

                NBi = Ar * m01i + Ai * m01r + Br * ci + Bi * cr

                NCr = Cr * cr - Ci * ci + Dr * m10r - Di * m10i

                NCi = Cr * ci + Ci * cr + Dr * m10i + Di * m10r

                NDr = Cr * m01r - Ci * m01i + Dr * cr - Di * ci

                NDi = Cr * m01i + Ci * m01r + Dr * ci + Di * cr

            M_before[k + 1, 0] = Ar

            M_before[k + 1, 1] = Ai

            M_before[k + 1, 2] = Br

            M_before[k + 1, 3] = Bi

            M_before[k + 1, 4] = Cr

            M_before[k + 1, 5] = Ci

            M_before[k + 1, 6] = Dr

            M_before[k + 1, 7] = Di

            Ar, Ai, Br, Bi, Cr, Ci, Dr, Di = NAr, NAi, NBr, NBi, NCr, NCi, NDr, NDi

        M00r, M00i = Ar, Ai

        M01r, M01i = Br, Bi

        M10r, M10i = Cr, Ci

        M11r, M11i = Dr, Di

        # === BACKWARD PASS: Compute M_after[k] ===

        M_after[n_layers, 0] = 1.0

        M_after[n_layers, 1] = 0.0

        M_after[n_layers, 2] = 0.0

        M_after[n_layers, 3] = 0.0

        M_after[n_layers, 4] = 0.0

        M_after[n_layers, 5] = 0.0

        M_after[n_layers, 6] = 1.0

        M_after[n_layers, 7] = 0.0

        Ar, Ai = 1.0, 0.0

        Br, Bi = 0.0, 0.0

        Cr, Ci = 0.0, 0.0

        Dr, Di = 1.0, 0.0

        for k in range(n_layers - 1, -1, -1):
            M_after[k, 0] = Ar

            M_after[k, 1] = Ai

            M_after[k, 2] = Br

            M_after[k, 3] = Bi

            M_after[k, 4] = Cr

            M_after[k, 5] = Ci

            M_after[k, 6] = Dr

            M_after[k, 7] = Di

            n_k = n_layers_T[i_wl, k]

            nr = n_k.real

            ni = n_k.imag

            d_k = ep[k]

            phi_base = two_pi_inv_wl * d_k

            if abs(ni) < 1e-14:
                phi = phi_base * nr

                cp = np.cos(phi)

                sp = np.sin(phi)

                inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                m01i = sp * inv_n

                m10i = sp * nr

                # M_after_new = L * M_after_old (Lossless)

                # L = [[cp, -i m01i], [-i m10i, cp]]

                NAr = cp * Ar + m01i * Ci

                NAi = cp * Ai - m01i * Cr

                NBr = cp * Br + m01i * Di

                NBi = cp * Bi - m01i * Dr

                NCr = m10i * Ai + cp * Cr

                NCi = -m10i * Ar + cp * Ci

                NDr = m10i * Bi + cp * Dr

                NDi = -m10i * Br + cp * Di

            else:
                phr = phi_base * nr

                phi_img = phi_base * ni

                cr = np.cos(phr) * np.cosh(phi_img)

                ci = -np.sin(phr) * np.sinh(phi_img)

                sr = np.sin(phr) * np.cosh(phi_img)

                si = np.cos(phr) * np.sinh(phi_img)

                eta2 = nr * nr + ni * ni

                if eta2 < 1e-24:
                    eta2 = 1e-24

                inv_eta = 1.0 / eta2

                etr = nr * inv_eta

                eti = -ni * inv_eta

                m01r = sr * eti + si * etr

                m01i = si * eti - sr * etr

                m10r = nr * si + ni * sr

                m10i = ni * si - nr * sr

                # NAr = cr * Ar - ci * Ai + m01r * Cr - m01i * Ci

                NAr = cr * Ar - ci * Ai + m01r * Cr - m01i * Ci

                NAi = cr * Ai + ci * Ar + m01r * Ci + m01i * Cr

                NBr = cr * Br - ci * Bi + m01r * Dr - m01i * Di

                NBi = cr * Bi + ci * Br + m01r * Di + m01i * Dr

                NCr = m10r * Ar - m10i * Ai + cr * Cr - ci * Ci

                NCi = m10r * Ai + m10i * Ar + cr * Ci + ci * Cr

                NDr = m10r * Br - m10i * Bi + cr * Dr - ci * Di

                NDi = m10r * Bi + m10i * Br + cr * Di + ci * Dr

            Ar, Ai, Br, Bi, Cr, Ci, Dr, Di = NAr, NAi, NBr, NBi, NCr, NCi, NDr, NDi

        # Calculate T - Sub->Air convention: denom = n_sub*(M00+M01) + (M10+M11)

        dr = (ns_r * M00r - ns_i * M00i) + (ns_r * M01r - ns_i * M01i) + M10r + M11r

        di = (ns_r * M00i + ns_i * M00r) + (ns_r * M01i + ns_i * M01r) + M10i + M11i

        denom = dr * dr + di * di

        if denom < 1e-30:
            denom = 1e-30

        inv_den = 1.0 / denom

        tr = 2.0 * dr * inv_den

        ti = -2.0 * di * inv_den

        T_val = ns_r * (tr * tr + ti * ti)

        T_arr[i_wl] = T_val

        w = tgt_weights[i_wl]

        if w > 1e-12:
            diff = T_val - tgt_vals[i_wl]

            err_per_wl[i_wl] = diff * diff * w

            weight_per_wl[i_wl] = w

            # Compute gradients (per-wavelength accumulation)

            for i_var in range(n_vars):
                k = var_idx[i_var]

                idx_b = k + 1

                Mb00r = M_before[idx_b, 0] if idx_b <= n_layers else 0.0

                Mb00i = M_before[idx_b, 1] if idx_b <= n_layers else 0.0

                Mb01r = M_before[idx_b, 2] if idx_b <= n_layers else 0.0

                Mb01i = M_before[idx_b, 3] if idx_b <= n_layers else 0.0

                Mb10r = M_before[idx_b, 4] if idx_b <= n_layers else 0.0

                Mb10i = M_before[idx_b, 5] if idx_b <= n_layers else 0.0

                Mb11r = M_before[idx_b, 6] if idx_b <= n_layers else 0.0

                Mb11i = M_before[idx_b, 7] if idx_b <= n_layers else 0.0

                Ma00r = M_after[k, 0]

                Ma00i = M_after[k, 1]

                Ma01r = M_after[k, 2]

                Ma01i = M_after[k, 3]

                Ma10r = M_after[k, 4]

                Ma10i = M_after[k, 5]

                Ma11r = M_after[k, 6]

                Ma11i = M_after[k, 7]

                n_k = n_layers_T[i_wl, k]

                nr = n_k.real

                ni = n_k.imag

                d_k = ep[k]

                if abs(ni) < 1e-14:
                    factor = two_pi_inv_wl * nr

                    phi = factor * d_k

                    cp = np.cos(phi)

                    sp = np.sin(phi)

                    inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                    dm00r = -factor * sp

                    dm00i = 0.0

                    dm01r = 0.0

                    dm01i = -factor * cp * inv_n

                    dm10r = 0.0

                    dm10i = -factor * nr * cp

                    dm11r = -factor * sp

                    dm11i = 0.0

                else:
                    # Closed-form derivative for absorbing media (no finite differences).

                    phi_base = two_pi_inv_wl * d_k

                    phr = phi_base * nr

                    phi_img = phi_base * ni

                    cr = np.cos(phr) * np.cosh(phi_img)

                    ci = -np.sin(phr) * np.sinh(phi_img)

                    sr = np.sin(phr) * np.cosh(phi_img)

                    si = np.cos(phr) * np.sinh(phi_img)

                    eta2 = nr * nr + ni * ni

                    if eta2 < 1e-24:
                        eta2 = 1e-24

                    inv_eta = 1.0 / eta2

                    etr = nr * inv_eta

                    eti = -ni * inv_eta

                    f_r = TWO_PI * nr * inv_wl

                    f_i = TWO_PI * ni * inv_wl

                    # d/d(d_k) of trigonometric-hyperbolic components

                    dcr = -sr * f_r + si * f_i

                    dci = -(si * f_r + sr * f_i)

                    dsr = cr * f_r - ci * f_i

                    dsi = ci * f_r + cr * f_i

                    dm00r = dcr

                    dm00i = dci

                    dm01r = dsr * eti + dsi * etr

                    dm01i = dsi * eti - dsr * etr

                    dm10r = nr * dsi + ni * dsr

                    dm10i = ni * dsi - nr * dsr

                    dm11r = dm00r

                    dm11i = dm00i

                # eM = Mb * dL * Ma

                # T = Mb * dL

                # eM = Mb * dL * Ma

                # T = Mb * dL

                t00r = Mb00r * dm00r - Mb00i * dm00i + Mb01r * dm10r - Mb01i * dm10i

                t00i = Mb00r * dm00i + Mb00i * dm00r + Mb01r * dm10i + Mb01i * dm10r

                t01r = Mb00r * dm01r - Mb00i * dm01i + Mb01r * dm11r - Mb01i * dm11i

                t01i = Mb00r * dm01i + Mb00i * dm01r + Mb01r * dm11i + Mb01i * dm11r

                t10r = Mb10r * dm00r - Mb10i * dm00i + Mb11r * dm10r - Mb11i * dm10i

                t10i = Mb10r * dm00i + Mb10i * dm00r + Mb11r * dm10i + Mb11i * dm10r

                t11r = Mb10r * dm01r - Mb10i * dm01i + Mb11r * dm11r - Mb11i * dm11i

                t11i = Mb10r * dm01i + Mb10i * dm01r + Mb11r * dm11i + Mb11i * dm11r

                dM00r = t00r * Ma00r - t00i * Ma00i + t01r * Ma10r - t01i * Ma10i

                dM00i = t00r * Ma00i + t00i * Ma00r + t01r * Ma10i + t01i * Ma10r

                dM01r = t00r * Ma01r - t00i * Ma01i + t01r * Ma11r - t01i * Ma11i

                dM01i = t00r * Ma01i + t00i * Ma01r + t01r * Ma11i + t01i * Ma11r

                dM10r = t10r * Ma00r - t10i * Ma00i + t11r * Ma10r - t11i * Ma10i

                dM10i = t10r * Ma00i + t10i * Ma00r + t11r * Ma10i + t11i * Ma10r

                dM11r = t10r * Ma01r - t10i * Ma01i + t11r * Ma11r - t11i * Ma11i

                dM11i = t10r * Ma01i + t10i * Ma01r + t11r * Ma11i + t11i * Ma11r

                ddr = (ns_r * dM00r - ns_i * dM00i) + (ns_r * dM01r - ns_i * dM01i) + dM10r + dM11r

                ddi = (ns_r * dM00i + ns_i * dM00r) + (ns_r * dM01i + ns_i * dM01r) + dM10i + dM11i

                d_denom = 2.0 * (dr * ddr + di * ddi)

                dtr = 2.0 * ddr * inv_den - tr * d_denom * inv_den

                dti = -2.0 * ddi * inv_den - ti * d_denom * inv_den

                dT_dk = ns_r * 2.0 * (tr * dtr + ti * dti)

                grad_per_wl[i_wl, i_var] += w * diff * dT_dk

    # === REDUCTION PHASE (sequential, fast) ===

    err_sum = 0.0

    weight_sum = 0.0

    for i in range(n_wls):
        err_sum += err_per_wl[i]

        weight_sum += weight_per_wl[i]

    grad = np.zeros(n_vars, dtype=np.float64)

    for v in range(n_vars):
        s = 0.0

        for i in range(n_wls):
            s += grad_per_wl[i, v]

        grad[v] = s

    if weight_sum < 1e-12:
        cost = 1e30

        grad[:] = 0.0

    else:
        cost = err_sum / weight_sum

        grad *= 2.0 / weight_sum

    return cost, grad, T_arr


