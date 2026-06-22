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
from .certus_opt_tmm import *
from .certus_opt_gradients import *
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