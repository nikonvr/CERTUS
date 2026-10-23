SMALL_EPSILON = 1e-12
import numpy as np
from numba import njit, prange

from certus.domain.constants import TWO_PI
from certus.physics.certus_opt_tmm import compute_RT_from_matrix


@njit(cache=True, fastmath=False, inline="never")
def _is_finite_scalar(x: float) -> bool:
    """Return True if x is finite (resists fastmath folding, ETAT D53)."""
    return np.isfinite(x)


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

            if _is_finite_scalar(T_val) and _is_finite_scalar(tgt_vals[w]):
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


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def needle_scan_cached_backside(
    wls: np.ndarray,  # (W,) float64
    n_layers_T: np.ndarray,  # (W, N) complex128 - layer clues
    n_needle_T: np.ndarray,  # (W, N) complex128 - needle material per layer
    n_sub: np.ndarray,  # (W,) complex128 - substrate
    ep: np.ndarray,  # (N,) float64 - current thicknesses
    tgt_vals: np.ndarray,  # (W,) float64 - target T values
    tgt_weights: np.ndarray,  # (W,) float64 - target weights
    step_nm: float,  # scan step (nm)
    probe_thickness: float,  # needle probe thickness (nm)
    scan_mask: np.ndarray,  # (N,) int64 - 1 = scan, 0 = skip
    rb_prime: np.ndarray,  # (W,) float64 - back stack R seen from the substrate (calc_spectrum_full_exact)
    tb: np.ndarray,  # (W,) float64 - back stack T seen from the substrate (calc_spectrum_full_exact)
) -> tuple:
    """Needle position scan with an incoherent back side, on cached matrix products.

    Same caching as needle_scan_cached: the products of the layers below and above each candidate are computed
    once, and a candidate costs the left part, the needle and the right part of its layer. The back side does
    not depend on the needle: the caller computes its reflectance and transmittance seen from the substrate once
    (calc_spectrum_full_exact). The front reflectance seen from the substrate comes from the same matrix: every
    layer matrix has equal diagonal terms, so the product in reverse order is the product with M00 and M11
    swapped. R and T come from the single source compute_RT_from_matrix; T_total = Tf * Tb / (1 - Rf_sub * Rb_sub)
    and the cost is the weighted MSE of cost_numba_fast, so the best candidate is the one of the uncached scan.

    Returns (best_layer, best_depth, best_cost); (-1, 0.0, 1e30) when no candidate exists.
    """
    N = len(ep)
    W = len(wls)
    k0 = TWO_PI / wls

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
            sp_i = 1j * np.sin(phi)
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
            R00[j, w] = r00 * cp + r01 * m10
            R01[j, w] = r00 * m01 + r01 * cp
            R10[j, w] = r10 * cp + r11 * m10
            R11[j, w] = r10 * m01 + r11 * cp

    total = 0
    for j in range(N):
        if scan_mask[j] == 0 or ep[j] < step_nm + 0.1:
            continue
        z = step_nm
        while z < ep[j] - 0.1:
            total += 1
            z += step_nm
    if total == 0:
        return np.int64(-1), 0.0, 1e30
    cand_layer = np.empty(total, dtype=np.int64)
    cand_z = np.empty(total, dtype=np.float64)
    idx = 0
    for j in range(N):
        if scan_mask[j] == 0 or ep[j] < step_nm + 0.1:
            continue
        z = step_nm
        while z < ep[j] - 0.1:
            cand_layer[idx] = j
            cand_z[idx] = z
            idx += 1
            z += step_nm
    total = idx

    costs = np.full(total, 1e30, dtype=np.float64)
    for c in prange(total):
        j = cand_layer[c]
        z = cand_z[c]
        d_right = ep[j] - z
        sum_sq = 0.0
        sum_w = 0.0
        count = 0
        for w in range(W):
            w_tgt = tgt_weights[w]
            if w_tgt <= 0.0:
                continue
            kk = k0[w]
            n_j = n_layers_T[w, j]
            n_ndl = n_needle_T[w, j]
            # left part of layer j, then the needle, then the right part, between the cached products
            phi = kk * n_j * z
            cp = np.cos(phi)
            sp = 1j * np.sin(phi)
            q01 = sp / n_j if abs(n_j) > 1e-12 else 0.0 + 0j
            q10 = sp * n_j
            t00 = cp * L00[j, w] + q01 * L10[j, w]
            t01 = cp * L01[j, w] + q01 * L11[j, w]
            t10 = q10 * L00[j, w] + cp * L10[j, w]
            t11 = q10 * L01[j, w] + cp * L11[j, w]
            phi = kk * n_ndl * probe_thickness
            cp = np.cos(phi)
            sp = 1j * np.sin(phi)
            q01 = sp / n_ndl if abs(n_ndl) > 1e-12 else 0.0 + 0j
            q10 = sp * n_ndl
            u00 = cp * t00 + q01 * t10
            u01 = cp * t01 + q01 * t11
            u10 = q10 * t00 + cp * t10
            u11 = q10 * t01 + cp * t11
            phi = kk * n_j * d_right
            cp = np.cos(phi)
            sp = 1j * np.sin(phi)
            q01 = sp / n_j if abs(n_j) > 1e-12 else 0.0 + 0j
            q10 = sp * n_j
            v00 = cp * u00 + q01 * u10
            v01 = cp * u01 + q01 * u11
            v10 = q10 * u00 + cp * u10
            v11 = q10 * u01 + cp * u11
            M00 = R00[j, w] * v00 + R01[j, w] * v10
            M01 = R00[j, w] * v01 + R01[j, w] * v11
            M10 = R10[j, w] * v00 + R11[j, w] * v10
            M11 = R10[j, w] * v01 + R11[j, w] * v11
            ns = n_sub[w]
            _rf, tf = compute_RT_from_matrix(M00, M01, M10, M11, 1.0 + 0j, ns)
            # Seen from inside, an absorbing substrate keeps the real part of its index, as in
            # calc_spectrum_full_exact (its losses are already in rb_prime and tb).
            ns_in = complex(ns.real, 0.0) if ns.imag != 0.0 else ns
            rf_sub, _t_sub = compute_RT_from_matrix(M11, M01, M10, M00, ns_in, 1.0 + 0j)
            denom = 1.0 - rf_sub * rb_prime[w]
            if denom < 1e-12:
                denom = 1e-12
            t_val = tf * tb[w] / denom
            if _is_finite_scalar(t_val) and _is_finite_scalar(tgt_vals[w]):
                diff = t_val - tgt_vals[w]
                sum_sq += diff * diff * w_tgt
                sum_w += w_tgt
                count += 1
        if count >= 5 and sum_w > 1e-18:
            costs[c] = sum_sq / sum_w

    best_idx = 0
    best_cost = costs[0]
    for c in range(1, total):
        if costs[c] < best_cost:
            best_cost = costs[c]
            best_idx = c
    return np.int64(cand_layer[best_idx]), cand_z[best_idx], best_cost
