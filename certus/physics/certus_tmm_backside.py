import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import calculate_bare_substrate_R_absorbing, calculate_bare_substrate_T_absorbing, calculate_bare_substrate_R, calculate_bare_substrate_RT


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Exact incoherent backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _apply_exact_backside_generic(
    R_front: np.ndarray,
    T_front: np.ndarray,
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_sub_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Exact incoherent backside for generic multilayer (no back coating).

    Computes R' (Sub -> Stack -> Air) via compute_TMM_generic with reversed arrays.

    TMM convention: L_0 = adjacent to EXIT medium -> reverse for Sub->Air direction.

    """

    n = len(wls)

    R_total = np.empty(n, dtype=R_front.dtype)

    T_total = np.empty(n, dtype=T_front.dtype)

    d_rev = thicknesses[::-1].copy()

    for i in prange(n):
        k0 = TWO_PI / wls[i]

        n_s = n_sub_all_wls[i]

        # Check for absorbing substrate (infinite thickness assumption)

        if abs(n_s.imag) > 1e-8:
            # Absorbing substrate: Light doesn't reach back interface / doesn't return

            R_total[i] = R_front[i]

            T_total[i] = 0.0

            continue

        n_air = complex(1.0)

        # R' = Sub -> Stack -> Air (reversed arrays, swapped media)

        n_rev_i = n_layers_all_wls[i, ::-1].copy() if n_layers_all_wls.ndim > 1 else n_layers_all_wls[i : i + 1]

        R_prime, _ = compute_TMM_generic(k0, d_rev, n_rev_i, n_s, n_air)

        # Uncoated back: substrate/Air interface

        n_s_real = np.real(n_s)

        r_b = (n_s_real - 1.0) / (n_s_real + 1.0)

        R_sub = r_b * r_b

        T_sub = 1.0 - R_sub

        # Exact incoherent combination

        D = 1.0 - R_prime * R_sub

        if D < 1e-12:
            D = 1e-12

        T_total[i] = (T_front[i] * T_sub) / D

        R_total[i] = R_front[i] + (T_front[i] * T_front[i] * R_sub) / D

        # Clamp

        if T_total[i] < 0.0:
            T_total[i] = 0.0

        elif T_total[i] > 1.0:
            T_total[i] = 1.0

        if R_total[i] < 0.0:
            R_total[i] = 0.0

        elif R_total[i] > 1.0:
            R_total[i] = 1.0

    return R_total, T_total


# --- LOCKED --- Exact incoherent backside combination ───


# Fabry-Perot intensity formula. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def apply_exact_backside_combination(
    Rf: np.ndarray, Tf: np.ndarray, Rb_stack: np.ndarray, n_sub: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """

    Combines Front Stack properties with Backside Interface (Air) using EXACT incoherent formula.

    CRITICAL PHYSICS NOTE:

    This function implements the Incoherent Cavity Model.

    Reflectance R = R_front + (T_front^2 * R_back) / (1 - R_front_mirror * R_back_mirror)

    Transmission T = (T_front * T_back) / (1 - R_front_mirror * R_back_mirror)

    DO NOT SIMPLIFY TO R_front + R_back.

    Args:

        Rf: Front stack reflection (Air -> Stack -> Sub)

        Tf: Front stack transmission (Air -> Stack -> Sub)

        Rb_stack: Front stack reflection FROM SUBSTRATE (Sub -> Stack -> Air)

        n_sub: substrate refractive index

    Returns:

        R_total, T_total

    NOTE: Assumes REAL substrate index (Non-absorbing). Forces np.real(n_sub).

    """

    n = len(Rf)

    R_total = np.empty(n, dtype=Rf.dtype)

    T_total = np.empty(n, dtype=Tf.dtype)

    for i in prange(n):
        n_s = np.real(n_sub[i])

        # 1. Back Interface (substrate | Air) Reflection

        # r = (ns - 1)/(ns + 1)

        r_back = (n_s - 1.0) / (n_s + 1.0)

        R_sub_air = r_back * r_back

        T_sub_air = 1.0 - R_sub_air

        # 2. Incoherent Cavity Formula

        # Cavity is the substrate.

        # Front Mirror: Stack (Reflectance Rb_stack looking from substrate)

        # Back Mirror: Sub/Air Interface (Reflectance R_sub_air looking from substrate)

        # Denominator = 1 - R_back_mirror * R_front_mirror

        denom = 1.0 - R_sub_air * Rb_stack[i]

        if denom < 1e-12:
            denom = 1e-12

        # T_total = T_front_stack * T_back_interface / denom

        T_total[i] = (Tf[i] * T_sub_air) / denom

        # R_total = R_front_stack + (T_front_stack^2 * R_back_interface) / denom

        R_total[i] = Rf[i] + (Tf[i] * Tf[i] * R_sub_air) / denom

        # Clamp

        if T_total[i] < 0.0:
            T_total[i] = 0.0

        elif T_total[i] > 1.0:
            T_total[i] = 1.0

        if R_total[i] < 0.0:
            R_total[i] = 0.0

        elif R_total[i] > 1.0:
            R_total[i] = 1.0

    return R_total, T_total


# --- LOCKED --- Validated by test_tmm_coherence.py (test_analytical_hlh, test_vectorized_vs_reference) ───


# Macleod convention (+1j). Delegates to calculate_RT_no_backside. DO NOT MODIFY without running tests.

