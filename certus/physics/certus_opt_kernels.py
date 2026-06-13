SMALL_EPSILON = 1e-12
import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE
from dataclasses import dataclass
import certus.physics.certus_tmm_core as tmm_core
from certus.physics.certus_optical_models import (
    get_nk_from_spline, get_nk_cauchy_simple, get_nk_cauchy_wrapper,
    sellmeier_n_array, get_nk_cauchy, epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk
)
from scipy.interpolate import CubicSpline

# [MONOLITHIC BLOCK] TMM & OPTIMIZATION KERNELS


# DO NOT SPLIT - Core Transfer Matrix Method implementation


# =========================================================================================


# OPTIMIZATION KERNELS (NUMBA)


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_mse_vectorized(
    calc_values: np.ndarray, target_values: np.ndarray, weights: np.ndarray
) -> tuple[float, int]:

    n = len(calc_values)

    # Thread-local accumulators via parallel reduction

    partial_sq = np.empty(n, dtype=np.float64)

    partial_valid = np.empty(n, dtype=np.float64)

    partial_wsum = np.empty(n, dtype=np.float64)

    for i in prange(n):
        if weights[i] > 0 and np.isfinite(calc_values[i]) and np.isfinite(target_values[i]):
            diff = calc_values[i] - target_values[i]

            partial_sq[i] = diff * diff * weights[i]

            partial_valid[i] = 1.0

            partial_wsum[i] = weights[i]

        else:
            partial_sq[i] = 0.0

            partial_valid[i] = 0.0

            partial_wsum[i] = 0.0

    sum_sq = 0.0

    sum_w = 0.0

    count = 0

    for i in range(n):
        sum_sq += partial_sq[i]

        sum_w += partial_wsum[i]

        count += int(partial_valid[i])

    if count < 5 or sum_w <= 1e-18:
        return 1e12, count

    # Strict weighted average: makes the metric consistent with Deltaln(lambda)

    # even if the spectral grid is irregular.

    return sum_sq / sum_w, count


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def clip_to_bounds(x: np.ndarray, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:

    return np.minimum(np.maximum(x, lb), ub)


# --- LOCKED --- Validated by test_tmm_inline.py (test 5) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def cost_numba_fast(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
) -> float:

    # --- CRITICAL PHYSICS NOTE ---

    # This cost function optimizes TRANSMISSION (T) ONLY.

    # It compares T_calc vs Target Values (assumed to be T).

    # If has_back=True, it uses the EXACT incoherent backside formula:

    # T_total = (Tf * Tb) / (1 - Rf' * Rb')

    # DO NOT CHANGE THIS LOGIC without verifying target types.

    # -----------------------------

    # 1. Calc Optical Properties (T)

    if has_back:
        Rf, Tf, Rf_prime, Rb_prime, Tb = tmm_core.calc_spectrum_full_exact(wls, ep, n_layers_T, d_back, n_back_T, n_sub)

        # Exact incoherent: T = (Tf * Tb) / (1 - Rf' * Rb')

        n_wls = len(wls)

        T = np.empty(n_wls, dtype=wls.dtype)

        for i in prange(n_wls):
            d_val = 1.0 - Rf_prime[i] * Rb_prime[i]

            if d_val < 1e-12:
                d_val = 1e-12

            T[i] = (Tf[i] * Tb[i]) / d_val

    else:
        R, T = tmm_core.calculate_RT_no_backside(ep, n_layers_T, n_sub, wls)

    # 2. MSE

    mse, count = compute_mse_vectorized(T, tgt_vals, tgt_weights)

    if count == 0:
        return 1e12

    # 3. Vectorized penalty via parallel reduction

    n_ep = len(ep)

    penalty_arr = np.empty(n_ep, dtype=np.float64)

    for i in prange(n_ep):
        d_val = ep[i]

        if 1e-12 < d_val < min_d:
            gap = min_d - d_val

            penalty_arr[i] = gap * gap * 1e6

        else:
            penalty_arr[i] = 0.0

    penalty = 0.0

    for i in range(n_ep):
        penalty += penalty_arr[i]

    return mse + penalty


# [REMOVED 2026-02-11] run_coordinate_descent_RT - dead code duplicate.


# Active version lives in CERTUS_INDEX.py with proper parallelization.


# =============================================================================


# NEEDLE SCAN - CACHED FORWARD/BACKWARD PRODUCTS


# =============================================================================


# --- LOCKED --- Validated by test_needle_cached.py (8/8) ---


# Macleod convention (+1j), pre-multiply Air->Sub, index 0 = substrate.


# Complexity: O(N*W) precomputation + O(P*W) scan  (P = total positions)


# vs O(P*N*W) for the naive full-TMM-per-position approach.


# DO NOT MODIFY without running test_needle_cached.py + test_tmm_inline.py.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def needle_scan_cached(
    wls: np.ndarray,  # (W,) float64
    n_layers_T: np.ndarray,  # (W, N) complex128 - layer clues
    n_needle_T: np.ndarray,  # (W, N) complex128  - needle material per layer
    n_sub: np.ndarray,  # (W,) complex128     - substrate
    ep: np.ndarray,  # (N,) float64        - current thicknesses
    tgt_vals: np.ndarray,  # (W,) float64        - target T values
    tgt_weights: np.ndarray,  # (W,) float64        - target weights
    step_nm: float,  # scan step (nm)
    probe_thickness: float,  # needle probe thickness (nm)
    scan_mask: np.ndarray,  # (N,) int64  - 1 = scan, 0 = skip
) -> tuple:
    """

    Optimized Needle position scan with forward/backward matrix caching.

    Instead of recomputing the full TMM (N+2 layers) for every candidate

    (layer, depth) pair, we:

      1. Precompute cumulative matrix products from both ends  - O(N·W).

      2. For each candidate position, compute only the 3 inner matrices

         (left, needle, right) and chain them with the cached products - O(W).

    Returns

    -------

    (best_layer, best_depth, best_cost) - int64, float64, float64

    Returns (-1, 0.0, 1e30) if no valid candidate is found.

    """

    N = len(ep)

    W = len(wls)

    # --- Precompute k0 = 2π/lambda ---

    k0 = TWO_PI / wls

    # ================================================================

    # Step 1 - Forward cumulative products L[j] (j = 0 … N)

    #   L[j] = M_{j-1} × … × M_0 (layers below j, substrate side)

    #   L[0] = Identity

    #   L[j+1] = M_j × L[j]         (pre-multiply)

    # ================================================================

    L00 = np.empty((N + 1, W), dtype=np.complex128)

    L01 = np.empty((N + 1, W), dtype=np.complex128)

    L10 = np.empty((N + 1, W), dtype=np.complex128)

    L11 = np.empty((N + 1, W), dtype=np.complex128)

    for w in range(W):
        L00[0, w] = 1.0 + 0j

        L01[0, w] = 0.0 + 0j

        L10[0, w] = 0.0 + 0j

        L11[0, w] = 1.0 + 0j

    for j in range(N):
        d_j = ep[j]

        for w in range(W):
            n_j = n_layers_T[w, j]

            phi = k0[w] * n_j * d_j

            cp = np.cos(phi)

            sp_i = 1j * np.sin(phi)  # +1j  Macleod

            m01 = sp_i / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            m10 = sp_i * n_j

            a00 = L00[j, w]

            a01 = L01[j, w]

            a10 = L10[j, w]

            a11 = L11[j, w]

            L00[j + 1, w] = cp * a00 + m01 * a10

            L01[j + 1, w] = cp * a01 + m01 * a11

            L10[j + 1, w] = m10 * a00 + cp * a10

            L11[j + 1, w] = m10 * a01 + cp * a11

    # ================================================================

    # Step 2 - Backward cumulative products R[j] (j = 0 … N-1)

    #   R[j] = M_{N-1} × … × M_{j+1} (layers above j, air side)

    #   R[N-1] = Identity

    #   R[j]   = R[j+1] × M_{j+1}

    # ================================================================

    R00 = np.empty((N, W), dtype=np.complex128)

    R01 = np.empty((N, W), dtype=np.complex128)

    R10 = np.empty((N, W), dtype=np.complex128)

    R11 = np.empty((N, W), dtype=np.complex128)

    for w in range(W):
        R00[N - 1, w] = 1.0 + 0j

        R01[N - 1, w] = 0.0 + 0j

        R10[N - 1, w] = 0.0 + 0j

        R11[N - 1, w] = 1.0 + 0j

    for j in range(N - 2, -1, -1):
        d_jp1 = ep[j + 1]

        for w in range(W):
            n_jp1 = n_layers_T[w, j + 1]

            phi = k0[w] * n_jp1 * d_jp1

            cp = np.cos(phi)

            sp_i = 1j * np.sin(phi)

            m01 = sp_i / n_jp1 if abs(n_jp1) > 1e-12 else 0.0 + 0j

            m10 = sp_i * n_jp1

            r00 = R00[j + 1, w]

            r01 = R01[j + 1, w]

            r10 = R10[j + 1, w]

            r11 = R11[j + 1, w]

            # R[j] = R[j+1] × M_{j+1}

            R00[j, w] = r00 * cp + r01 * m10

            R01[j, w] = r00 * m01 + r01 * cp

            R10[j, w] = r10 * cp + r11 * m10

            R11[j, w] = r10 * m01 + r11 * cp

    # ================================================================

    # Step 3 - Enumerate all (layer, z) candidates

    # ================================================================

    total = 0

    for j in range(N):
        if scan_mask[j] == 0:
            continue

        d_j = ep[j]

        if d_j < step_nm + 0.1:
            continue

        z = step_nm

        while z < d_j - 0.1:
            total += 1

            z += step_nm

    if total == 0:
        return np.int64(-1), 0.0, 1e30

    cand_layer = np.empty(total, dtype=np.int64)

    cand_z = np.empty(total, dtype=np.float64)

    idx = 0

    for j in range(N):
        if scan_mask[j] == 0:
            continue

        d_j = ep[j]

        if d_j < step_nm + 0.1:
            continue

        z = step_nm

        while z < d_j - 0.1:
            cand_layer[idx] = j

            cand_z[idx] = z

            idx += 1

            z += step_nm

    total = idx  # actual count

    # ================================================================

    # Step 4 - Evaluate all candidates in parallel (prange)

    #

    # For candidate c  at layer j, depth z:

    #   M_total = R[j] × M_right(d_j-z) × M_needle(probe) × M_left(z) × L[j]

    #   -> 4 matrix multiplications + R/T extraction per wavelength

    # ================================================================

    costs = np.full(total, 1e30, dtype=np.float64)

    for c in prange(total):
        j = cand_layer[c]

        z = cand_z[c]

        d_j = ep[j]

        d_right = d_j - z

        mse_sum = 0.0

        count = 0

        for w in range(W):
            w_tgt = tgt_weights[w]

            if w_tgt <= 0.0:
                continue

            kk = k0[w]

            n_j = n_layers_T[w, j]

            n_ndl = n_needle_T[w, j]

            ns = n_sub[w]

            # ── M_left(z, n_j) ──

            phi_l = kk * n_j * z

            cp_l = np.cos(phi_l)

            sp_l = 1j * np.sin(phi_l)

            ml01 = sp_l / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            ml10 = sp_l * n_j

            # T1 = M_left × L[j]

            a00 = L00[j, w]

            a01 = L01[j, w]

            a10 = L10[j, w]

            a11 = L11[j, w]

            t1_00 = cp_l * a00 + ml01 * a10

            t1_01 = cp_l * a01 + ml01 * a11

            t1_10 = ml10 * a00 + cp_l * a10

            t1_11 = ml10 * a01 + cp_l * a11

            # ── M_needle(probe, n_ndl) ──

            phi_n = kk * n_ndl * probe_thickness

            cp_n = np.cos(phi_n)

            sp_n = 1j * np.sin(phi_n)

            mn01 = sp_n / n_ndl if abs(n_ndl) > 1e-12 else 0.0 + 0j

            mn10 = sp_n * n_ndl

            # T2 = M_needle × T1

            t2_00 = cp_n * t1_00 + mn01 * t1_10

            t2_01 = cp_n * t1_01 + mn01 * t1_11

            t2_10 = mn10 * t1_00 + cp_n * t1_10

            t2_11 = mn10 * t1_01 + cp_n * t1_11

            # ── M_right(d_right, n_j) ──

            phi_r = kk * n_j * d_right

            cp_r = np.cos(phi_r)

            sp_r = 1j * np.sin(phi_r)

            mr01 = sp_r / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            mr10 = sp_r * n_j

            # T3 = M_right × T2

            t3_00 = cp_r * t2_00 + mr01 * t2_10

            t3_01 = cp_r * t2_01 + mr01 * t2_11

            t3_10 = mr10 * t2_00 + cp_r * t2_10

            t3_11 = mr10 * t2_01 + cp_r * t2_11

            # T4 = R[j] × T3  ->  M_total

            rr00 = R00[j, w]

            rr01 = R01[j, w]

            rr10 = R10[j, w]

            rr11 = R11[j, w]

            M00 = rr00 * t3_00 + rr01 * t3_10

            M01 = rr00 * t3_01 + rr01 * t3_11

            M10 = rr10 * t3_00 + rr11 * t3_10

            M11 = rr10 * t3_01 + rr11 * t3_11

            # ── Extract T  (Macleod:  n_inc = 1, n_exit = n_sub) ──

            B = M00 + M01 * ns

            C = M10 + M11 * ns

            Y = B + C  # n_inc * B + C  with n_inc = 1

            if abs(Y) < 1e-14:
                T_val = 0.0

            else:
                t_coeff = 2.0 / Y  # 2·n_inc / Y

                T_val = ns.real * (t_coeff.real * t_coeff.real + t_coeff.imag * t_coeff.imag)

                if T_val < 0.0:
                    T_val = 0.0

                r_coeff = (B - C) / Y

                R_val = r_coeff.real * r_coeff.real + r_coeff.imag * r_coeff.imag

                if R_val + T_val > 1.0:
                    T_val = 1.0 - R_val

                    if T_val < 0.0:
                        T_val = 0.0

            # ── Accumulate weighted MSE ──

            if np.isfinite(T_val) and np.isfinite(tgt_vals[w]):
                diff = T_val - tgt_vals[w]

                mse_sum += diff * diff * w_tgt

                count += 1

        if count >= 5:
            costs[c] = mse_sum / count

    # ================================================================

    # Step 5 - Find best candidate

    # ================================================================

    best_idx = 0

    best_cost = costs[0]

    for c in range(1, total):
        if costs[c] < best_cost:
            best_cost = costs[c]

            best_idx = c

    return np.int64(cand_layer[best_idx]), cand_z[best_idx], best_cost


# =============================================================================


# =========================================================================================

from certus.physics.certus_optimizers import *

# =============================================================================

from certus.physics.certus_colorimetry import *
from certus.physics.certus_colorimetry import _lab_f, _lab_f_inv, _gamma_correct_scalar, _xyz_from_spectrum_kernel
from certus.physics.certus_material_db import *
from certus.physics.certus_material_db import numba_interp_scalar, numba_interp_vectorized

# ADDITIONAL PHYSICS KERNELS


# =============================================================================


# --- LOCKED --- Validated by test_tmm_coherence.py + test_tmm_inline.py (tests 0, 0b, 5) ───


# Macleod convention: n̂ = n - ik. Single source generic TMM.


# DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_TMM_generic(
    k0: float,
    thicknesses: np.ndarray,
    n_layers_complex: np.ndarray,
    n_inc: complex,
    n_sub: complex,
) -> tuple[float, float]:
    """Generic TMM for n_inc -> layers -> n_sub.

    Returns (R, T) where T is power transmission into n_sub.

    CAPITAL AGREEMENT:

      - Layer 1 = layer closest to the substrate.

      - index 0 = layer 1 = adjacent to the substrate (EXIT).

      - index N-1 = incident rating (air).

      - M = L_{N-1} * ... * L_0 (pre-multiplication). DO NOT REVERSE.

      - Complex clues: n̂ = n - ik (imag <= 0 for absorption)."""

    M00 = 1.0 + 0.0j

    M01 = 0.0 + 0.0j

    M10 = 0.0 + 0.0j

    M11 = 1.0 + 0.0j

    I_VAL = +1j

    for i in range(len(thicknesses)):
        n_c = n_layers_complex[i]

        # -- SAFEGUARD n-ik: force Macleod convention --

        # If imag > 0 (non-physical gain), we silently correct.

        if n_c.imag > 0.0:
            n_c = n_c.real - 1j * n_c.imag  # n+ik -> n-ik

        phi = k0 * n_c * thicknesses[i]

        cp = np.cos(phi)

        isp = I_VAL * np.sin(phi)  # factor i*sin(phi) once

        if abs(n_c) > 1e-12:
            m01 = isp / n_c

        else:
            m01 = 0.0 + 0.0j

        m10 = isp * n_c

        # M_new = L @ M_old  (cp == L00 == L11, diagonal symmetry)

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    # Delegate to factored helper (single source of truth for R/T extraction)

    return compute_RT_from_matrix(M00, M01, M10, M11, n_inc, n_sub)


# --- LOCKED --- Validated by test_energy_conservation.py + test_tmm_coherence.py ───


# Single source R/T extraction. DO NOT MODIFY without running tests.


#


# ╔══════════════════════════════════════════════════════════════════════╗


# ║  FORMULA T - Macleod 4th ed. (semi-infinite substrate)                 ║


# ║                                                                      ║


# ║  T = Re(η_exit) / Re(η_inc) * |t|²                                 ║


# ║  t = 2·η_inc / (η_inc·B + C)                                       ║


# ║  R = |r|²,  r = (η_inc·B - C) / (η_inc·B + C)                     ║


# ║                                                                      ║


# ║  CONVENTION CRITIQUE: n̂ = n - ik  (k >= 0 for absorption)         ║


# ║  If n̂ = n + ik is used, R+T > 1 (non-physical gain).          ║


# ║  DO NOT REVERSE THE CONVENTION.                                     ║


# ╚══════════════════════════════════════════════════════════════════════╝


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_RT_from_matrix(
    M00: complex,
    M01: complex,
    M10: complex,
    M11: complex,
    n_inc: complex,
    n_exit: complex,
) -> tuple[float, float]:
    """Computes (R, T) from a 2x2 transfer matrix M and boundary media.

    REFERENCE: Macleod 4th ed., eq. 2.96 (semi-infinite substrate).

        R = |r|² where r = (η_inc·B - C) / (η_inc·B + C)

        T = Re(η_exit) / Re(η_inc) · |t|²

              where t = 2·η_inc / (η_inc·B + C)

        [B; C] = M · [1; η_exit]

    CONVENTION: Complex clues MUST follow n̂ = n - ik (k >= 0).

    With n̂ = n + ik, the formula yields R+T > 1 (non-physical gain).

    This is the SINGLE SOURCE OF TRUTH for the R/T extraction formula.

    All TMM functions should delegate to this.

    Args:

        M00, M01, M10, M11: Transfer matrix elements

        n_inc: Complex refractive index of incident medium (n - ik convention)

        n_exit: Complex refractive index of exit medium (n - ik convention)

    Returns:

        (R, T) - power reflectance and transmittance, R+T <= 1 for absorbing layers"""

    B = M00 + M01 * n_exit

    C = M10 + M11 * n_exit

    Y_sys = n_inc * B + C

    if abs(Y_sys) < 1e-14:
        return 0.0, 0.0

    r = (n_inc * B - C) / Y_sys

    R = abs(r) ** 2

    n_inc_real = n_inc.real

    if n_inc_real < 1e-9:
        T = 0.0

    else:
        # T = Re(η_exit) / Re(η_inc) · |t|²

        # |t|² = 4·|η_inc|² / |η_inc·B + C|²

        n_exit_real = n_exit.real

        abs_t_sq = (4.0 * abs(n_inc) ** 2) / (abs(Y_sys) ** 2)

        T = (n_exit_real / n_inc_real) * abs_t_sq

    T = max(0.0, T)

    return R, T


# --- LOCKED --- Validated by test_tmm_inline.py (test 4) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RTRback_incoherent_vectorized(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_substrate_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Calculates R (Front), T, and Rback (Back) for a film on a THICK INCOHERENT substrate.

    """

    n = len(wls)

    R_total = np.empty(n, dtype=np.float64)

    T_total = np.empty(n, dtype=np.float64)

    Rback_total = np.empty(n, dtype=np.float64)

    k0_arr = TWO_PI / wls

    for i in prange(n):
        ns = n_substrate_all_wls[i]  # Complex substrate index

        n_inc_front = 1.0 + 0j

        n_layers = n_layers_all_wls[i]  # Array of complex clues for stack

        # 1. Front Coherent (Air -> Stack -> substrate)

        Rf_coh, Tf_coh = compute_TMM_generic(k0_arr[i], thicknesses, n_layers, n_inc_front, ns)

        if abs(ns.imag) > 1e-8:
            # Absorbing substrate (Infinite): No Backside Reflection

            T_total[i] = 0.0

            R_total[i] = Rf_coh

            Rback_total[i] = 0.0  # Or should it be R_sub (air-sub) only?

            # Convention: Rback is measured from Back (Air->Sub).

            # If sub is absorbing infinite, light sees Air->Sub interface, absorbs, nothing returns from front stack.

            # So Rback = R(Air->Sub)

            # Fresnel Air -> Sub

            n_air = 1.0

            r_as = (n_air - ns) / (n_air + ns)

            Rback_total[i] = abs(r_as) ** 2

            continue

        # 2. Back Coherent Internal (substrate -> Stack -> Air)

        # For back incidence, light comes from substrate.

        # Order of layers is reversed relative to beam.

        # Incident medium = ns, Exit medium = Air (n=1)

        # Reverse layers

        n_layers_rev = n_layers[::-1]  # Numba supports this

        thicknesses_rev = thicknesses[::-1]

        Rb_coh, Tb_coh = compute_TMM_generic(k0_arr[i], thicknesses_rev, n_layers_rev, ns, n_inc_front)

        # 3. substrate Backside Reflection (substrate -> Air)

        # Using Fresnel normal incidence for substrate-air interface

        # r = (ns - 1)/(ns + 1)

        if abs(ns + 1.0) > 1e-12:
            r_sub = (ns - 1.0) / (ns + 1.0)

            R_sub = abs(r_sub) ** 2

        else:
            R_sub = 0.0

        # 4. Incoherent Combination

        # Denom D = 1 - Rb_coh * R_sub

        denom = 1.0 - Rb_coh * R_sub

        if denom < 1e-9:
            denom = 1e-9

        # T_total = (Tf_coh * (1 - R_sub)) / D

        T_total[i] = (Tf_coh * (1.0 - R_sub)) / denom

        # R_total (Front Measured)

        # R = Rf_coh + (Tf_coh^2 * R_sub) / D ?

        # Standard: R_tot = R_front + (T_front * T_back * R_back_interface) / (1 - R_back_stack * R_back_interface)

        # T_front = Tf_coh, T_back = Tb_coh. reciprocity Tf=Tb in power?

        # Yes T_front = T_back usually.

        # Here we use Tf_coh * Tb_coh just to be safe or Tf_coh^2.

        R_total[i] = Rf_coh + (Tf_coh * Tb_coh * R_sub) / denom

        # Rback_total (Back Measured)

        # Light incident from Air (Back) -> substrate -> Stack -> Air (Front)

        # Interface 1: Air->substrate (R_sub)

        # Interface 2: substrate->Stack (Rb_coh)

        # R_back_tot = R_sub + ( (1-R_sub)*(1-R_sub) * Rb_coh ) / (1 - R_sub * Rb_coh)

        # Note R of Air->substrate is same as substrate->Air (R_sub)

        Rback_total[i] = R_sub + ((1.0 - R_sub) ** 2 * Rb_coh) / denom

    return R_total, T_total, Rback_total


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n-ik). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_reflection_infinite_substrate_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> float:
    """

    Calculate reflection for a thin film on INFINITE substrate (Frosted Glass).

    CRITICAL PHYSICS NOTE:

    Infinite substrate assumption = NO BACKSIDE REFLECTION.

    R = Front Surface Reflection Only.

    Any backside terms here would be physically invalid for rough/absorbing backsides.

    DO NOT ADD BACKSIDE TERMS.

    """

    if not np.isfinite(n_sub.real) or n_sub.real < 1.0:
        return np.nan

    n0 = N_SUPERSTRATE  # Air

    k = TWO_PI / wavelength

    # Complex phase in the film

    phi_r = k * n_film_real * thickness_nm

    phi_i = k * n_film_imag * thickness_nm

    # Complex exponential

    exp_pos = np.exp(-phi_i)

    exp_neg = np.exp(phi_i)

    cos_phi_r = np.cos(phi_r)

    sin_phi_r = np.sin(phi_r)

    cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0

    cos_phi_imag = sin_phi_r * (exp_neg - exp_pos) / 2.0

    sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0

    sin_phi_imag = cos_phi_r * (exp_pos - exp_neg) / 2.0

    # Inverse of complex film index

    n_mag_sq = n_film_real * n_film_real + n_film_imag * n_film_imag

    if n_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_n_r = n_film_real / n_mag_sq

    inv_n_i = n_film_imag / n_mag_sq

    # Transfer matrix elements (Macleod: -i * sin / n,  -i * n * sin)

    M00_real = cos_phi_real

    M00_imag = cos_phi_imag

    M01_real = inv_n_r * sin_phi_imag + inv_n_i * sin_phi_real

    M01_imag = -(inv_n_r * sin_phi_real - inv_n_i * sin_phi_imag)

    M10_real = n_film_real * sin_phi_imag + n_film_imag * sin_phi_real

    M10_imag = -(n_film_real * sin_phi_real - n_film_imag * sin_phi_imag)

    M11_real = cos_phi_real

    M11_imag = cos_phi_imag

    # substrate complex index

    ns_r = n_sub.real

    ns_i = n_sub.imag

    # Term n_sub * M01

    nsM01_r = ns_r * M01_real - ns_i * M01_imag

    nsM01_i = ns_r * M01_imag + ns_i * M01_real

    # Term n_sub * M11

    nsM11_r = ns_r * M11_real - ns_i * M11_imag

    nsM11_i = ns_r * M11_imag + ns_i * M11_real

    # Denominator: n0*B + C where B = M00+ns*M01, C = M10+ns*M11

    # B = M00 + nsM01

    B_r = M00_real + nsM01_r

    B_i = M00_imag + nsM01_i

    # C = M10 + nsM11

    C_r = M10_real + nsM11_r

    C_i = M10_imag + nsM11_i

    # Denom = n0 * B + C

    denom_real = n0 * B_r + C_r

    denom_imag = n0 * B_i + C_i

    denom_mag_sq = denom_real * denom_real + denom_imag * denom_imag

    if denom_mag_sq < SMALL_EPSILON:
        return np.nan

    # Numerator: n0*B - C (standard Macleod)

    num_r_real = n0 * B_r - C_r

    num_r_imag = n0 * B_i - C_i

    # Amplitude reflection coefficient

    r_real = (num_r_real * denom_real + num_r_imag * denom_imag) / denom_mag_sq

    r_imag = (num_r_imag * denom_real - num_r_real * denom_imag) / denom_mag_sq

    # Reflectance (intensity)

    R = r_real * r_real + r_imag * r_imag

    return max(0.0, min(1.0, R))





# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_reflectance_bilayer_vectorized(
    l_array, nM_complex_array, eM_phys, eL_phys, nL_complex_array, nSub_complex_array
):
    """

    Calculate reflectance for Metal|SiO2|Si structure using scalarized TMM.

    Structure: Air | Metal (eM) | SiO2 (eL) | Si (substrate)

    CRITICAL PHYSICS NOTE:

    Assumes Opaque/Infinite substrate behavior (Front Surface Only).

    This is specific to Metal Bilayer monitoring on typically absorbing or rough wafers.

    """

    n_pts = len(l_array)

    n0 = 1.0  # Air

    R_out = np.empty(n_pts, dtype=np.float64)

    for i in prange(n_pts):
        wl = l_array[i]

        k0 = TWO_PI / wl

        # Metal layer matrix: L00=L11=cM (diagonal symmetry)

        nM = nM_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nM.imag > 0.0:
            nM = nM.real - 1j * nM.imag

        phiM = k0 * nM * eM_phys

        cM = np.cos(phiM)

        ispM = +1j * np.sin(phiM)

        m01_M = ispM / nM if abs(nM) > 1e-14 else 0j

        m10_M = ispM * nM

        # SiO2 layer matrix: L00=L11=cL (diagonal symmetry)

        nL = nL_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nL.imag > 0.0:
            nL = nL.real - 1j * nL.imag

        phiL = k0 * nL * eL_phys

        cL = np.cos(phiL)

        ispL = +1j * np.sin(phiL)

        m01_L = ispL / nL if abs(nL) > 1e-14 else 0j

        m10_L = ispL * nL

        # Combined matrix M_total = M_metal * M_sio2 (cM,cL on diagonals)

        Mt00 = cM * cL + m01_M * m10_L

        Mt01 = cM * m01_L + m01_M * cL

        Mt10 = m10_M * cL + cM * m10_L

        Mt11 = m10_M * m01_L + cM * cL

        # Reflection coefficient

        nS = nSub_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nS.imag > 0.0:
            nS = nS.real - 1j * nS.imag

        term1 = n0 * (Mt00 + nS * Mt01)

        term2 = Mt10 + nS * Mt11

        num = term1 - term2

        den = term1 + term2

        r = num / den if abs(den) > 1e-20 else 0j

        R = (r.real * r.real) + (r.imag * r.imag)  # |r|^2

        if R < 0.0:
            R = 0.0

        elif R > 1.0:
            R = 1.0

        R_out[i] = R

    return R_out


@dataclass(slots=True)
class Material:
    """Material with Cauchy model (slots=True for reduced RAM)"""

    n4: float  # n @ 400nm

    n7: float  # n @ 700nm

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        """Calculates n(lambda) via Cauchy model with precision support"""

        wls_arr = np.asarray(wls, dtype=np.float64)

        # Use wrapper handling precision

        n_real = get_nk_cauchy_wrapper(float(self.n4), float(self.n7), wls_arr)

        # Convert to complex with configured precision

        complex_dtype = get_complex_dtype()

        return n_real.astype(complex_dtype)

    def get_n_at_wavelength(self, wl: float) -> float:
        """Returns n at specific wavelength"""

        result = self.get_nk(np.array([wl], dtype=np.float64))

        return float(result[0].real)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def get_n_frosted_glass_array(wavelengths_nm: np.ndarray) -> np.ndarray:
    """Calculate frosted glass refractive index for an array of wavelengths."""

    n = len(wavelengths_nm)

    result = np.empty(n, dtype=wavelengths_nm.dtype)

    for i in prange(n):
        result[i] = FROSTED_GLASS_CAUCHY_A + FROSTED_GLASS_CAUCHY_B / (wavelengths_nm[i] * wavelengths_nm[i])

    return result


# _calculate_reflection_single_gradient removed (Dead Code)


# --- LOCKED --- Validated by test_gradient_vs_fd.py (via _compute_tlu_derivatives_kernel) ───


# Tauc-Lorentz model ε₂ + analytic derivatives. DO NOT MODIFY without running tests.


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

                exp_val = np.exp(arg)

                val = eps2_edge * exp_val

                result[0, i] = val

                result[1, i] = d_eps2_edge_dEg * exp_val + val * (-inv_Eu)

                result[2, i] = d_eps2_edge_dA * exp_val

                result[3, i] = d_eps2_edge_dE0 * exp_val

                result[4, i] = d_eps2_edge_dC * exp_val

                result[5, i] = val * (-arg * inv_Eu)

    return result


# --- LOCKED --- Validated by test_gradient_vs_fd.py (via _compute_tlu_derivatives_kernel) ───


# Kramers-Kronig ε₁ analytic + derivatives. DO NOT MODIFY without running tests.


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


# --- LOCKED --- Validated by test_gradient_vs_fd.py ───


# n,k assembly + full TLU derivatives. DO NOT MODIFY without running tests.


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


# --- LOCKED --- Validated by test_gradient_vs_fd.py (lossless + absorbing + metal + dispersif) ───


# Internal convention (-1j, n+ik) self-consistent. DO NOT MODIFY without running tests.


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


# Macleod convention (+1j). DO NOT MODIFY without running tests.


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

    n_valid_T = 1

    n_valid_R = 1

    count_T = 0

    count_R = 0

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


def arange_inclusive(start: float, stop: float, step: float, decimals: int = WL_DECIMALS) -> np.ndarray:
    """

    Generates array with stop INCLUDED (unlike np.arange).

    """

    if step <= 0:
        raise ValueError("Step must be positive")

    n = int(np.floor((stop - start) / step + 1e-9)) + 1

    arr = np.linspace(start, start + (n - 1) * step, n, dtype=np.float64)

    arr = np.round(arr, decimals)

    # Ensure stop is included

    stop_rounded = round(stop, decimals)

    return arr[arr <= stop_rounded + 10 ** (-decimals - 1)]


def trim_worst_only(data: np.ndarray, trim_percent: int = 10) -> np.ndarray:
    """

    Removes X% worst values (for robust stats).

    """

    if len(data) == 0:
        return data

    sorted_data = np.sort(data)

    n = len(sorted_data)

    trim_count = int(n * trim_percent / 100)

    if trim_count > 0 and trim_count < n:
        return sorted_data[:-trim_count]

    return sorted_data


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


# --- LOCKED --- Validated by test_gradient_vs_fd.py (dispersive + absorbent + mixed) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


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


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_oblique_gradient_contrib_kernel(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    target_is_reflectance: bool,
) -> tuple[float, np.ndarray, float]:
    """

    Analytic oblique contribution kernel (front-only).

    Returns unnormalized sums:

        err_sum = Σ w * (y - tgt)^2

        grad_raw = Σ w * (y - tgt) * dy/dd

        weight_sum = Σ w

    so caller can aggregate several target groups then apply global normalization.

    """

    n_wls = len(wls)

    n_layers = len(ep)

    n_vars = len(var_idx)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)

    err_per_wl = np.zeros(n_wls, dtype=np.float64)

    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    n0 = 1.0

    theta0_rad = np.deg2rad(angle_deg)

    sin_theta0 = np.sin(theta0_rad)

    cos_theta0 = np.cos(theta0_rad)

    for i_wl in prange(n_wls):
        wl = wls[i_wl]

        n_sub_real = n_sub[i_wl].real

        w = tgt_weights[i_wl]

        if w <= 1e-12:
            continue

        sin_theta_sub = (n0 / max(n_sub_real, SMALL_EPSILON)) * sin_theta0

        if sin_theta_sub > 1.0:
            y_val = 1.0 if target_is_reflectance else 0.0

            diff = y_val - tgt_vals[i_wl]

            err_per_wl[i_wl] = w * diff * diff

            weight_per_wl[i_wl] = w

            continue

        cos_theta_sub = np.sqrt(1.0 - sin_theta_sub * sin_theta_sub)

        if is_s_pol:
            eta_inc = n0 * cos_theta0

            eta_sub = n_sub_real * cos_theta_sub

        else:
            if abs(cos_theta0) < SMALL_EPSILON or abs(cos_theta_sub) < SMALL_EPSILON:
                y_val = 1.0 if target_is_reflectance else 0.0

                diff = y_val - tgt_vals[i_wl]

                err_per_wl[i_wl] = w * diff * diff

                weight_per_wl[i_wl] = w

                continue

            eta_inc = n0 / cos_theta0

            eta_sub = n_sub_real / cos_theta_sub

        # Prefix products: P[k] = L_{k-1} ... L_0, P[0]=I

        prefix = np.zeros((n_layers + 1, 4), dtype=np.complex128)

        prefix[0, 0] = 1.0 + 0.0j

        prefix[0, 3] = 1.0 + 0.0j

        # Layer matrices and per-layer optical terms (for derivatives)

        L_store = np.zeros((n_layers, 4), dtype=np.complex128)

        eta_store = np.zeros(n_layers, dtype=np.complex128)

        beta_store = np.zeros(n_layers, dtype=np.complex128)

        valid = True

        k0 = TWO_PI / max(wl, SMALL_EPSILON)

        for k in range(n_layers):
            n_layer = n_layers_T[i_wl, k]

            if abs(n_layer) < SMALL_EPSILON:
                valid = False

                break

            sin_theta_layer = (n0 / n_layer) * sin_theta0

            cos_theta_layer = np.sqrt(1.0 - sin_theta_layer * sin_theta_layer)

            if is_s_pol:
                eta_layer = n_layer * cos_theta_layer

            else:
                if abs(cos_theta_layer) < SMALL_EPSILON:
                    valid = False

                    break

                eta_layer = n_layer / cos_theta_layer

            if abs(eta_layer) < SMALL_EPSILON:
                valid = False

                break

            beta = k0 * n_layer * cos_theta_layer

            phi = beta * ep[k]

            cp = np.cos(phi)

            sp = np.sin(phi)

            l01 = 1j * sp / eta_layer

            l10 = 1j * eta_layer * sp

            L_store[k, 0] = cp

            L_store[k, 1] = l01

            L_store[k, 2] = l10

            L_store[k, 3] = cp

            eta_store[k] = eta_layer

            beta_store[k] = beta

            p00 = prefix[k, 0]

            p01 = prefix[k, 1]

            p10 = prefix[k, 2]

            p11 = prefix[k, 3]

            prefix[k + 1, 0] = cp * p00 + l01 * p10

            prefix[k + 1, 1] = cp * p01 + l01 * p11

            prefix[k + 1, 2] = l10 * p00 + cp * p10

            prefix[k + 1, 3] = l10 * p01 + cp * p11

        if not valid:
            y_val = 1.0 if target_is_reflectance else 0.0

            diff = y_val - tgt_vals[i_wl]

            err_per_wl[i_wl] = w * diff * diff

            weight_per_wl[i_wl] = w

            continue

        # Suffix products: S[k] = L_{n-1} ... L_{k+1}; S[n-1]=I

        suffix = np.zeros((n_layers, 4), dtype=np.complex128)

        if n_layers > 0:
            suffix[n_layers - 1, 0] = 1.0 + 0.0j

            suffix[n_layers - 1, 3] = 1.0 + 0.0j

            for k in range(n_layers - 2, -1, -1):
                s00 = suffix[k + 1, 0]

                s01 = suffix[k + 1, 1]

                s10 = suffix[k + 1, 2]

                s11 = suffix[k + 1, 3]

                l00 = L_store[k + 1, 0]

                l01 = L_store[k + 1, 1]

                l10 = L_store[k + 1, 2]

                l11 = L_store[k + 1, 3]

                suffix[k, 0] = s00 * l00 + s01 * l10

                suffix[k, 1] = s00 * l01 + s01 * l11

                suffix[k, 2] = s10 * l00 + s11 * l10

                suffix[k, 3] = s10 * l01 + s11 * l11

        m00 = prefix[n_layers, 0]

        m01 = prefix[n_layers, 1]

        m10 = prefix[n_layers, 2]

        m11 = prefix[n_layers, 3]

        B = m00 + m01 * eta_sub

        C = m10 + m11 * eta_sub

        denom = eta_inc * B + C

        den2 = denom * denom

        den_mag_sq = (denom.real * denom.real) + (denom.imag * denom.imag)

        if den_mag_sq < SMALL_EPSILON:
            y_val = 1.0 if target_is_reflectance else 0.0

            diff = y_val - tgt_vals[i_wl]

            err_per_wl[i_wl] = w * diff * diff

            weight_per_wl[i_wl] = w

            continue

        num = eta_inc * B - C

        r = num / denom

        t = 2.0 * eta_inc / denom

        R_unclipped = (r * r.conjugate()).real

        T_unclipped = (eta_sub / eta_inc) * (t * t.conjugate()).real

        R_val = max(0.0, min(1.0, R_unclipped))

        T_val = max(0.0, min(1.0, T_unclipped))

        y_val = R_val if target_is_reflectance else T_val

        diff = y_val - tgt_vals[i_wl]

        err_per_wl[i_wl] = w * diff * diff

        weight_per_wl[i_wl] = w

        # If clamped, keep stable behavior and null derivative at this point.

        if (target_is_reflectance and (R_val != R_unclipped)) or (
            (not target_is_reflectance) and (T_val != T_unclipped)
        ):
            continue

        for i_var in range(n_vars):
            k = var_idx[i_var]

            p00 = prefix[k, 0]

            p01 = prefix[k, 1]

            p10 = prefix[k, 2]

            p11 = prefix[k, 3]

            if k == n_layers - 1:
                s00 = 1.0 + 0.0j

                s01 = 0.0 + 0.0j

                s10 = 0.0 + 0.0j

                s11 = 1.0 + 0.0j

            else:
                s00 = suffix[k, 0]

                s01 = suffix[k, 1]

                s10 = suffix[k, 2]

                s11 = suffix[k, 3]

            eta_layer = eta_store[k]

            beta = beta_store[k]

            phi = beta * ep[k]

            cp = np.cos(phi)

            sp = np.sin(phi)

            dcp = -sp * beta

            dsp = cp * beta

            dl01 = 1j * dsp / eta_layer

            dl10 = 1j * eta_layer * dsp

            # tmp = dL @ P

            t00 = dcp * p00 + dl01 * p10

            t01 = dcp * p01 + dl01 * p11

            t10 = dl10 * p00 + dcp * p10

            t11 = dl10 * p01 + dcp * p11

            # dM = S @ tmp

            dm00 = s00 * t00 + s01 * t10

            dm01 = s00 * t01 + s01 * t11

            dm10 = s10 * t00 + s11 * t10

            dm11 = s10 * t01 + s11 * t11

            dB = dm00 + dm01 * eta_sub

            dC = dm10 + dm11 * eta_sub

            dden = eta_inc * dB + dC

            if target_is_reflectance:
                dnum = eta_inc * dB - dC

                dr = (dnum * denom - num * dden) / den2

                dy = 2.0 * (r.conjugate() * dr).real

            else:
                dt = -(2.0 * eta_inc) * dden / den2

                dy = (eta_sub / eta_inc) * 2.0 * (t.conjugate() * dt).real

            grad_per_wl[i_wl, i_var] += w * diff * dy

    err_sum = 0.0

    weight_sum = 0.0

    for i in range(n_wls):
        err_sum += err_per_wl[i]

        weight_sum += weight_per_wl[i]

    grad_raw = np.zeros(n_vars, dtype=np.float64)

    for v in range(n_vars):
        s = 0.0

        for i in range(n_wls):
            s += grad_per_wl[i, v]

        grad_raw[v] = s

    return err_sum, grad_raw, weight_sum


def compute_oblique_gradient_contrib_analytic(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    target_is_reflectance: bool,
    var_idx: np.ndarray | None = None,
) -> tuple[float, np.ndarray, float]:
    """

    Wrapper for oblique analytic gradient contribution (front-only).

    Returns unnormalized (err_sum, grad_raw, weight_sum).

    """

    if var_idx is None:
        var_idx_arr = np.arange(len(ep), dtype=np.int64)

    else:
        var_idx_arr = np.asarray(var_idx, dtype=np.int64)

    ep_f64 = np.asarray(ep, dtype=np.float64)

    wls_f64 = np.asarray(wls, dtype=np.float64)

    tgt_vals_f64 = np.asarray(tgt_vals, dtype=np.float64)

    tgt_weights_f64 = np.asarray(tgt_weights, dtype=np.float64)

    n_layers_T_c128 = np.asarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

    return _compute_oblique_gradient_contrib_kernel(
        ep_f64,
        n_layers_T_c128,
        n_sub_c128,
        wls_f64,
        tgt_vals_f64,
        tgt_weights_f64,
        var_idx_arr,
        float(angle_deg),
        bool(is_s_pol),
        bool(target_is_reflectance),
    )


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_oblique_rt_and_grads_kernel(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    var_idx: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    reverse: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Compute oblique R/T and analytic dR,dT wrt selected thickness variables.

    reverse=False: Air -> Stack -> Sub

    reverse=True : Sub -> Stack(reversed) -> Air

    """

    n_wls = len(wls)

    n_layers = len(ep)

    n_vars = len(var_idx)

    R_arr = np.empty(n_wls, dtype=np.float64)

    T_arr = np.empty(n_wls, dtype=np.float64)

    dR = np.zeros((n_wls, n_vars), dtype=np.float64)

    dT = np.zeros((n_wls, n_vars), dtype=np.float64)

    n_air = 1.0

    theta0 = np.deg2rad(angle_deg)

    sin_theta_air = np.sin(theta0)

    np.cos(theta0)

    for i_wl in prange(n_wls):
        wl = wls[i_wl]

        n_sub_real = n_sub[i_wl].real

        if n_sub_real < 1e-12:
            R_arr[i_wl] = 1.0

            T_arr[i_wl] = 0.0

            continue

        if reverse:
            n_inc = n_sub_real

            n_exit = n_air

        else:
            n_inc = n_air

            n_exit = n_sub_real

        # Prefix products P[k] = L_{k-1}...L_0, P[0]=I

        prefix = np.zeros((n_layers + 1, 4), dtype=np.complex128)

        prefix[0, 0] = 1.0 + 0.0j

        prefix[0, 3] = 1.0 + 0.0j

        Lm = np.zeros((n_layers, 4), dtype=np.complex128)

        beta = np.zeros(n_layers, dtype=np.complex128)

        eta = np.zeros(n_layers, dtype=np.complex128)

        d_eff = np.zeros(n_layers, dtype=np.float64)

        valid = True

        k0 = TWO_PI / max(wl, SMALL_EPSILON)

        for j in range(n_layers):
            if reverse:
                n_layer = n_layers_T[i_wl, n_layers - 1 - j]

            else:
                n_layer = n_layers_T[i_wl, j]

            if abs(n_layer) < SMALL_EPSILON:
                valid = False

                break

            sin_l = sin_theta_air / n_layer

            cos_l = np.sqrt(1.0 - sin_l * sin_l)

            if is_s_pol:
                eta_l = n_layer * cos_l

            else:
                if abs(cos_l) < SMALL_EPSILON:
                    valid = False

                    break

                eta_l = n_layer / cos_l

            if abs(eta_l) < SMALL_EPSILON:
                valid = False

                break

            beta_j = k0 * n_layer * cos_l

            d_j = ep[n_layers - 1 - j] if reverse else ep[j]

            phi = beta_j * d_j

            cp = np.cos(phi)

            sp = np.sin(phi)

            l01 = 1j * sp / eta_l

            l10 = 1j * eta_l * sp

            Lm[j, 0] = cp

            Lm[j, 1] = l01

            Lm[j, 2] = l10

            Lm[j, 3] = cp

            beta[j] = beta_j

            eta[j] = eta_l

            d_eff[j] = d_j

            p00 = prefix[j, 0]

            p01 = prefix[j, 1]

            p10 = prefix[j, 2]

            p11 = prefix[j, 3]

            prefix[j + 1, 0] = cp * p00 + l01 * p10

            prefix[j + 1, 1] = cp * p01 + l01 * p11

            prefix[j + 1, 2] = l10 * p00 + cp * p10

            prefix[j + 1, 3] = l10 * p01 + cp * p11

        if not valid:
            R_arr[i_wl] = 1.0

            T_arr[i_wl] = 0.0

            continue

        # Suffix products S[k] = L_{n-1}...L_{k+1}

        suffix = np.zeros((n_layers, 4), dtype=np.complex128)

        if n_layers > 0:
            suffix[n_layers - 1, 0] = 1.0 + 0.0j

            suffix[n_layers - 1, 3] = 1.0 + 0.0j

            for k in range(n_layers - 2, -1, -1):
                s00 = suffix[k + 1, 0]

                s01 = suffix[k + 1, 1]

                s10 = suffix[k + 1, 2]

                s11 = suffix[k + 1, 3]

                l00 = Lm[k + 1, 0]

                l01 = Lm[k + 1, 1]

                l10 = Lm[k + 1, 2]

                l11 = Lm[k + 1, 3]

                suffix[k, 0] = s00 * l00 + s01 * l10

                suffix[k, 1] = s00 * l01 + s01 * l11

                suffix[k, 2] = s10 * l00 + s11 * l10

                suffix[k, 3] = s10 * l01 + s11 * l11

        # Admittances at incidence/exit

        sin_inc = sin_theta_air / max(n_inc, SMALL_EPSILON)

        if sin_inc > 1.0:
            R_arr[i_wl] = 1.0

            T_arr[i_wl] = 0.0

            continue

        cos_inc = np.sqrt(max(0.0, 1.0 - sin_inc * sin_inc))

        sin_exit = sin_theta_air / max(n_exit, SMALL_EPSILON)

        if sin_exit > 1.0:
            R_arr[i_wl] = 1.0

            T_arr[i_wl] = 0.0

            continue

        cos_exit = np.sqrt(max(0.0, 1.0 - sin_exit * sin_exit))

        if is_s_pol:
            eta_inc = n_inc * cos_inc

            eta_exit = n_exit * cos_exit

        else:
            if abs(cos_inc) < SMALL_EPSILON or abs(cos_exit) < SMALL_EPSILON:
                R_arr[i_wl] = 1.0

                T_arr[i_wl] = 0.0

                continue

            eta_inc = n_inc / cos_inc

            eta_exit = n_exit / cos_exit

        m00 = prefix[n_layers, 0]

        m01 = prefix[n_layers, 1]

        m10 = prefix[n_layers, 2]

        m11 = prefix[n_layers, 3]

        B = m00 + m01 * eta_exit

        C = m10 + m11 * eta_exit

        D = eta_inc * B + C

        D2 = D * D

        Dmag2 = D.real * D.real + D.imag * D.imag

        if Dmag2 < SMALL_EPSILON:
            R_arr[i_wl] = 1.0

            T_arr[i_wl] = 0.0

            continue

        N = eta_inc * B - C

        r = N / D

        t = (2.0 * eta_inc) / D

        Rv = (r * r.conjugate()).real

        Tv = (eta_exit / eta_inc) * (t * t.conjugate()).real

        if Rv < 0.0:
            Rv = 0.0

        elif Rv > 1.0:
            Rv = 1.0

        if Tv < 0.0:
            Tv = 0.0

        elif Tv > 1.0:
            Tv = 1.0

        R_arr[i_wl] = Rv

        T_arr[i_wl] = Tv

        # Derivatives for selected vars

        for iv in range(n_vars):
            k_orig = var_idx[iv]

            if k_orig < 0 or k_orig >= n_layers:
                continue

            k = (n_layers - 1 - k_orig) if reverse else k_orig

            p00 = prefix[k, 0]

            p01 = prefix[k, 1]

            p10 = prefix[k, 2]

            p11 = prefix[k, 3]

            if k == n_layers - 1:
                s00 = 1.0 + 0.0j

                s01 = 0.0 + 0.0j

                s10 = 0.0 + 0.0j

                s11 = 1.0 + 0.0j

            else:
                s00 = suffix[k, 0]

                s01 = suffix[k, 1]

                s10 = suffix[k, 2]

                s11 = suffix[k, 3]

            phi = beta[k] * d_eff[k]

            cp = np.cos(phi)

            sp = np.sin(phi)

            dcp = -sp * beta[k]

            dsp = cp * beta[k]

            dl01 = 1j * dsp / eta[k]

            dl10 = 1j * eta[k] * dsp

            # tmp = dL @ P

            t00 = dcp * p00 + dl01 * p10

            t01 = dcp * p01 + dl01 * p11

            t10 = dl10 * p00 + dcp * p10

            t11 = dl10 * p01 + dcp * p11

            # dM = S @ tmp

            dm00 = s00 * t00 + s01 * t10

            dm01 = s00 * t01 + s01 * t11

            dm10 = s10 * t00 + s11 * t10

            dm11 = s10 * t01 + s11 * t11

            dB = dm00 + dm01 * eta_exit

            dC = dm10 + dm11 * eta_exit

            dN = eta_inc * dB - dC

            dD = eta_inc * dB + dC

            dr = (dN * D - N * dD) / D2

            dt = -(2.0 * eta_inc) * dD / D2

            dR[i_wl, iv] = 2.0 * (r.conjugate() * dr).real

            dT[i_wl, iv] = (eta_exit / eta_inc) * 2.0 * (t.conjugate() * dt).real

    return R_arr, T_arr, dR, dT


def compute_oblique_rt_and_grads_analytic(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    var_idx: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    reverse: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Python wrapper for oblique R/T + analytic dR,dT kernel."""

    ep_f64 = np.asarray(ep, dtype=np.float64)

    n_layers_c128 = np.asarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

    wls_f64 = np.asarray(wls, dtype=np.float64)

    var_idx_i64 = np.asarray(var_idx, dtype=np.int64)

    return _compute_oblique_rt_and_grads_kernel(
        ep_f64,
        n_layers_c128,
        n_sub_c128,
        wls_f64,
        var_idx_i64,
        float(angle_deg),
        bool(is_s_pol),
        bool(reverse),
    )


def compute_oblique_rt_pair_and_grads_analytic(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    var_idx: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
) -> tuple[
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
]:
    """

    Compute oblique front and reverse responses in one wrapper.

    Returns (front, reverse) where each item is (R, T, dR, dT).

    """

    ep_f64 = np.asarray(ep, dtype=np.float64)

    n_layers_c128 = np.asarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

    wls_f64 = np.asarray(wls, dtype=np.float64)

    var_idx_i64 = np.asarray(var_idx, dtype=np.int64)

    front = _compute_oblique_rt_and_grads_kernel(
        ep_f64,
        n_layers_c128,
        n_sub_c128,
        wls_f64,
        var_idx_i64,
        float(angle_deg),
        bool(is_s_pol),
        False,
    )

    reverse = _compute_oblique_rt_and_grads_kernel(
        ep_f64,
        n_layers_c128,
        n_sub_c128,
        wls_f64,
        var_idx_i64,
        float(angle_deg),
        bool(is_s_pol),
        True,
    )

    return front, reverse


def compute_oblique_backside_bundle_analytic(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    var_idx: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    n_back_T: np.ndarray | None = None,
    d_back: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Backside oblique bundle for one polarization.

    Returns y_R, dy_R, y_T, dy_T wrt front thickness variables.

    """

    ep_f64 = np.asarray(ep, dtype=np.float64)

    n_layers_c128 = np.asarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

    wls_f64 = np.asarray(wls, dtype=np.float64)

    var_idx_i64 = np.asarray(var_idx, dtype=np.int64)

    (Rf, Tf, dRf, dTf), (Rf_prime, T_front_rev, dRf_prime, dT_front_rev) = compute_oblique_rt_pair_and_grads_analytic(
        ep_f64, n_layers_c128, n_sub_c128, wls_f64, var_idx_i64, angle_deg, is_s_pol
    )

    if n_back_T is not None and d_back is not None and np.asarray(d_back).size > 0:
        n_back_c128 = np.asarray(n_back_T, dtype=np.complex128)

        d_back_f64 = np.asarray(d_back, dtype=np.float64)

        Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(
            d_back_f64,
            n_back_c128,
            n_sub_c128,
            wls_f64,
            np.zeros(0, dtype=np.int64),
            angle_deg,
            is_s_pol,
            True,
        )

    else:
        Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(
            np.zeros(0, dtype=np.float64),
            np.zeros((len(wls_f64), 0), dtype=np.complex128),
            n_sub_c128,
            wls_f64,
            np.zeros(0, dtype=np.int64),
            angle_deg,
            is_s_pol,
            True,
        )

    D = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)

    D2 = D * D

    y_R = Rf + (Tf * T_front_rev * Rb_prime) / D

    dy_R = dRf + (
        (Rb_prime[:, None] * (dTf * T_front_rev[:, None] + Tf[:, None] * dT_front_rev)) / D[:, None]
        + ((Tf * T_front_rev * (Rb_prime * Rb_prime))[:, None] * dRf_prime / D2[:, None])
    )

    y_T = (Tf * Tb) / D

    dy_T = Tb[:, None] * (dTf / D[:, None] + (Tf[:, None] * Rb_prime[:, None] * dRf_prime) / D2[:, None])

    return y_R, dy_R, y_T, dy_T


# --- LOCKED --- Validated by test_gradient_vs_fd.py ───


# Multilayer analytic gradient wrapper. DO NOT MODIFY without running tests.


def compute_gradient_all_layers_analytic(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
    var_idx: np.ndarray | None = None,
) -> tuple[float, np.ndarray]:
    """

    Calculates cost and analytic gradient for multilayer stack.

    """

    # Determines variable clues

    if var_idx is None:
        var_idx_arr = np.arange(len(ep), dtype=np.int64)

    else:
        var_idx_arr = np.asarray(var_idx, dtype=np.int64)

    # Backside (normal incidence): full analytic chain using oblique kernel at 0 deg.

    # This keeps one derivative source of truth with the oblique implementation.

    if has_back and len(d_back) > 0:
        ep_f64 = np.asarray(ep, dtype=np.float64)

        wls_f64 = np.asarray(wls, dtype=np.float64)

        tgt_vals_f64 = np.asarray(tgt_vals, dtype=np.float64)

        tgt_weights_f64 = np.asarray(tgt_weights, dtype=np.float64)

        n_layers_T_c128 = np.asarray(n_layers_T, dtype=np.complex128)

        n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

        n_back_T_c128 = np.asarray(n_back_T, dtype=np.complex128)

        d_back_f64 = np.asarray(d_back, dtype=np.float64)

        # Front stack (air->sub) and reverse front stack (sub->air = Rf_prime path).

        _Rf, Tf, _dRf, dTf = compute_oblique_rt_and_grads_analytic(
            ep_f64, n_layers_T_c128, n_sub_c128, wls_f64, var_idx_arr, 0.0, True, False
        )

        Rf_prime, _T_front_rev, dRf_prime, _dT_front_rev = compute_oblique_rt_and_grads_analytic(
            ep_f64, n_layers_T_c128, n_sub_c128, wls_f64, var_idx_arr, 0.0, True, True
        )

        # Back stack response is fixed for this optimization variable set.

        _Rf0, _Tf0, _Rf_p0, Rb_prime, Tb = tmm_core.calc_spectrum_full_exact(
            wls_f64, ep_f64, n_layers_T_c128, d_back_f64, n_back_T_c128, n_sub_c128
        )

        D = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)

        D2 = D * D

        T_total = (Tf * Tb) / D

        mse, count = compute_mse_vectorized(T_total, tgt_vals_f64, tgt_weights_f64)

        if count == 0:
            return 1e12, np.zeros(len(var_idx_arr), dtype=np.float64)

        dy = Tb[:, None] * (dTf / D[:, None] + (Tf[:, None] * Rb_prime[:, None] * dRf_prime) / D2[:, None])

        valid = (tgt_weights_f64 > 0.0) & np.isfinite(T_total) & np.isfinite(tgt_vals_f64)

        diff_w = (T_total - tgt_vals_f64) * tgt_weights_f64

        diff_w[~valid] = 0.0

        grad = (2.0 / max(count, 1)) * np.sum(diff_w[:, None] * dy, axis=0)

        # Keep penalty and its analytic derivative consistent with cost_numba_fast.

        min_d_f = float(min_d)

        penalty = 0.0

        for d_val in ep_f64:
            if 1e-12 < d_val < min_d_f:
                gap = min_d_f - d_val

                penalty += gap * gap * 1e6

        grad_penalty = np.zeros(len(var_idx_arr), dtype=np.float64)

        for i, v_idx in enumerate(var_idx_arr):
            d_val = ep_f64[v_idx]

            if 1e-12 < d_val < min_d_f:
                grad_penalty[i] = -2e6 * (min_d_f - d_val)

        return mse + penalty, grad + grad_penalty

    # Front-only: use analytic gradient kernel

    ep_f64 = np.asarray(ep, dtype=np.float64)

    wls_f64 = np.asarray(wls, dtype=np.float64)

    tgt_vals_f64 = np.asarray(tgt_vals, dtype=np.float64)

    tgt_weights_f64 = np.asarray(tgt_weights, dtype=np.float64)

    n_layers_T_c128 = np.asarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)

    cost, grad, _ = _compute_gradient_analytic_kernel(
        ep_f64,
        n_layers_T_c128,
        n_sub_c128,
        wls_f64,
        tgt_vals_f64,
        tgt_weights_f64,
        var_idx_arr,
    )

    # Add penalty for min thickness violation

    penalty = 0.0

    for i in range(len(ep)):
        if ep[i] > 1e-12 and ep[i] < min_d:
            diff = min_d - ep[i]

            penalty += diff * diff * 1e6

    cost += penalty

    return cost, grad


# --- LOCKED --- Validated by test_gradient_vs_fd.py (Ag dispersive + SiO2 + Si absorbent) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
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


# --- LOCKED --- Validated by test_gradient_vs_fd.py (Ag + SiO2 + Si) ───


# Analytic gradient wrapper for metal bilayer. DO NOT MODIFY without running tests.


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


# =============================================================================
