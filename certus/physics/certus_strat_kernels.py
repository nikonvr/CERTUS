import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact




# [MONOLITHIC BLOCK] STRAT KERNELS


# DO NOT SPLIT - High performance growth simulation kernels


# =========================================================================================


# STRAT KERNELS


# =============================================================================


# --- 6.1 Extrema Detection ---


# --- MODIFIED (Opus 4.7b) --- Arrival AND start checks asymmetric on wavelength change.


# Macleod convention (+1j). Pre-multiply + Air->Sub.

@njit(cache=True, fastmath=True, nogil=True, inline='always', error_model="numpy")
def _calc_T_from_matrix(m00: complex, m01: complex, m10: complex, m11: complex, n_Sub: complex) -> float:
    denom = m00 + n_Sub * m11 + n_Sub * m01 + m10
    if abs(denom) > 1e-9:
        t = 2.0 / denom
        return n_Sub.real * (t.real**2 + t.imag**2)
    return 0.0

@njit(cache=True, fastmath=True, nogil=True, inline='always', error_model="numpy")
def _calc_T_added_layer(wl: float, n_layer: complex, d_nm: float, n_Sub: complex, m00: complex, m01: complex, m10: complex, m11: complex) -> float:
    phi = (TWO_PI / wl) * n_layer * d_nm
    cp, sp = np.cos(phi), np.sin(phi)
    son = (sp / n_layer) if abs(n_layer) > 1e-9 else 0.0
    ml00, ml01 = cp, +1j * son
    ml10, ml11 = +1j * n_layer * sp, cp
    mt00 = ml00 * m00 + ml01 * m10
    mt01 = ml00 * m01 + ml01 * m11
    mt10 = ml10 * m00 + ml11 * m10
    mt11 = ml10 * m01 + ml11 * m11
    return _calc_T_from_matrix(mt00, mt01, mt10, mt11, n_Sub)



@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def check_extrema_proximity(
    wl,
    n_current,
    n_previous,
    n_Sub,
    thickness_nominal,
    M_before,
    exclusion_width,
    check_start,
    wl_changed=False,
) -> bool:
    """

    Checks if wavelength is too close to a transmission extremum.

    ARRIVAL CHECK is asymmetric (Opus 4.7):

      - Forbidden zone BEFORE a turning point: 3 * exclusion_width  (wide)

      - Forbidden zone AFTER  a turning point: 1 * exclusion_width  (narrow)

    START CHECK (Opus 4.7b) - asymmetric only when wl_changed=True:

      - Symmetric +/-δe check always applied (unchanged behaviour)

      - If wl_changed: also reject if TP is AHEAD within [0, 3δe] (new wavelength

        starts with no prior monitoring info -> be more cautious before a TP)

    """

    m00, m01 = M_before[0, 0], M_before[0, 1]

    m10, m11 = M_before[1, 0], M_before[1, 1]

    if wl < 0.1:
        return False

    # Constants and Tolerance - always double precision

    TWO_PI_VAL = TWO_PI

    TOL = 1e-9

    if check_start:
        T_pres = _calc_T_from_matrix(m00, m01, m10, m11, n_Sub)
        T_fut = _calc_T_added_layer(wl, n_current, exclusion_width, n_Sub, m00, m01, m10, m11)
        
        n_prev_safe = n_previous if n_previous.real > 0.0 else n_current
        T_past = _calc_T_added_layer(wl, n_prev_safe, -exclusion_width, n_Sub, m00, m01, m10, m11)

        # Case 1 (symmetric +/-δe, always active): d=0 is at an extremum

        diff1, diff2 = T_pres - T_past, T_fut - T_pres

        if (diff1 > TOL and diff2 < -TOL) or (diff1 < -TOL and diff2 > TOL):
            return False

        # Case 2 (asymmetric, only when wl changed): TP is AHEAD within [δe, 3δe]

        # i.e., starting this layer on the new lambda would place us just before a TP

        if wl_changed:
            T_far = _calc_T_added_layer(wl, n_current, 3.0 * exclusion_width, n_Sub, m00, m01, m10, m11)

            # s_mid = T_fut - T_pres (already computed above)

            # s_right = T_far - T_fut (over 2δe, normed)

            s_mid_s = T_fut - T_pres

            s_right_s = (T_far - T_fut) / 2.0

            if (s_mid_s > TOL and s_right_s < -TOL) or (s_mid_s < -TOL and s_right_s > TOL):
                return False

    if thickness_nominal > exclusion_width:
        # --- ASYMMETRIC ARRIVAL CHECK (Opus 4.7) ---

        # Physical rationale: stopping just BEFORE a turning point is forbidden

        # (signal still evolving toward an unknown extremum -> imprecise cut-off).

        # Stopping just AFTER is safer (turning point already detected and passed).

        #

        # Forbidden zone around a turning point at d_tp:

        #   [d_tp - 3*exclusion_width,  d_tp + exclusion_width]

        # Equivalent: reject d_nom if a TP exists in [d_nom - δe, d_nom + 3δe].

        #

        # 4 sample points: [d-δe,  d,  d+δe,  d+3δe]

        #   s_left  = T[1]-T[0]           slope just before d  (width δe)

        #   s_mid   = T[2]-T[1]           slope just after  d  (width δe)

        #   s_right = (T[3]-T[2]) / 2.0   slope further ahead  (width 2δe, normed)

        #

        # Reject (return False) if:

        #   Case 1 - TP within δe of d on either side:     sign(s_left) != sign(s_mid)

        #   Case 2 - TP ahead of d within [d+δe, d+3δe]:  sign(s_mid)  != sign(s_right)

        points = np.array(
            [
                thickness_nominal - exclusion_width,
                thickness_nominal,
                thickness_nominal + exclusion_width,
                thickness_nominal + 3.0 * exclusion_width,
            ]
        )

        T_end = np.zeros(4)

        for k in range(4):
            T_end[k] = _calc_T_added_layer(wl, n_current, points[k], n_Sub, m00, m01, m10, m11)

        s_left = T_end[1] - T_end[0]

        s_mid = T_end[2] - T_end[1]

        s_right = (T_end[3] - T_end[2]) / 2.0

        TOL_E = 1e-9

        # Case 1: d is near an extremum (symmetric δe margin - preserves original behaviour)

        if (s_left > TOL_E and s_mid < -TOL_E) or (s_left < -TOL_E and s_mid > TOL_E):
            return False

        # Case 2: TP is AHEAD of d within [d+δe, d+3δe] -> d is approaching it -> reject

        if (s_mid > TOL_E and s_right < -TOL_E) or (s_mid < -TOL_E and s_right > TOL_E):
            return False

    return True


# --- MODIFIED (Opus 4.7c) --- Extrema Proximity Calculator (for Report)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_extrema_distances(
    wl: float,
    n_current: complex,
    n_Sub: complex,
    thickness_nominal: float,
    M_before: np.ndarray,
) -> tuple[float, float, float, float]:
    """

    Performs a mini-scan to find the exact distance (in nm) to the nearest

    transmission extrema (turning points) from d=0 (start) and d=thickness_nominal (end).

    Returns:

        (dist_prev_start, dist_next_start, dist_prev_end, dist_next_end)

        Positive distances mean the extremum is purely that far away (absolute distance).

        If no extremum is found within 200nm, returns 999.0 for that value.

    """

    m00, m01 = M_before[0, 0], M_before[0, 1]

    m10, m11 = M_before[1, 0], M_before[1, 1]

    if wl < 0.1:
        return 999.0, 999.0, 999.0, 999.0

    TWO_PI_VAL = TWO_PI

    # Scan around d=0 and d=thickness_nominal using two narrow windows instead of the whole layer

    # We need to scale scan range. OT = n * d. So physical d range corresponding to 16 OT is 16/n.

    # We will scan physically wide enough, then convert distance to OT.

    scan_ot = 16.0

    physical_scan_radius = scan_ot / float(abs(n_current)) if abs(n_current) > 1e-9 else 16.0

    step = 0.5

    # helper for one narrow window

    def scan_window(center):

        start_w = center - physical_scan_radius

        end_w = center + physical_scan_radius

        pts = int((end_w - start_w) / step) + 1

        d_arr = np.zeros(pts)

        T_arr = np.zeros(pts)

        for i in range(pts):
            d = start_w + i * step

            d_arr[i] = d

            T_arr[i] = _calc_T_added_layer(wl, n_current, d, n_Sub, m00, m01, m10, m11)

        return d_arr, T_arr

    extrema_d = []

    TOL = 1e-9

    # Window 1: Start (d=0)

    d_scan1, T_scan1 = scan_window(0.0)

    for i in range(1, len(d_scan1) - 1):
        s_left = T_scan1[i] - T_scan1[i - 1]

        s_right = T_scan1[i + 1] - T_scan1[i]

        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan1[i])

    # Window 2: End (d=thickness_nominal)

    d_scan2, T_scan2 = scan_window(thickness_nominal)

    for i in range(1, len(d_scan2) - 1):
        s_left = T_scan2[i] - T_scan2[i - 1]

        s_right = T_scan2[i + 1] - T_scan2[i]

        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan2[i])

    # Now find distances to 0.0 and to thickness_nominal IN OPTICAL THICKNESS

    n_real = float(n_current.real)

    dist_prev_start, dist_next_start = 999.0, 999.0

    dist_prev_end, dist_next_end = 999.0, 999.0

    for ed in extrema_d:
        # Convert physical diff to OT diff

        diff_start_ot = (ed - 0.0) * n_real

        if diff_start_ot <= 0:
            dist_prev_start = min(dist_prev_start, abs(diff_start_ot))

        if diff_start_ot >= 0:
            dist_next_start = min(dist_next_start, abs(diff_start_ot))

        # For End (d=thickness_nominal)

        diff_end_ot = (ed - thickness_nominal) * n_real

        if diff_end_ot <= 0:
            dist_prev_end = min(dist_prev_end, abs(diff_end_ot))

        if diff_end_ot >= 0:
            dist_next_end = min(dist_next_end, abs(diff_end_ot))

    return dist_prev_start, dist_next_start, dist_prev_end, dist_next_end


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def fit_parabola_vertex_3points(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:

    x1, x2, x3 = x[0], x[1], x[2]

    y1, y2, y3 = y[0], y[1], y[2]

    denom = (x1 - x2) * (x1 - x3) * (x2 - x3)

    if abs(denom) < 1e-12:
        return 0.0, 0.0, y1

    a = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom

    b = (x3 * x3 * (y1 - y2) + x2 * x2 * (y3 - y1) + x1 * x1 * (y2 - y3)) / denom

    c = (x2 * x3 * (x2 - x3) * y1 + x3 * x1 * (x3 - x1) * y2 + x1 * x2 * (x1 - x2) * y3) / denom

    return a, b, c


# ─── NUMBA GRAPH-PARTITIONING OPTIMIZATION PHASE B ───


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _compute_valid_blocks_kernel(
    layer_wls: np.ndarray,
    layer_costs: np.ndarray,
    valid_mask: np.ndarray,
    num_layers: int,
    top_k: int,
    max_W: int,
):

    block_costs = np.full((num_layers + 1, num_layers + 1, top_k), np.inf, dtype=np.float64)

    block_wls = np.full((num_layers + 1, num_layers + 1, top_k), -1.0, dtype=np.float64)

    block_counts = np.zeros((num_layers + 1, num_layers + 1), dtype=np.int32)

    for i in range(num_layers):
        for j in range(i + 1, num_layers + 1):
            bl_ok = True

            for l in range(i, j):
                has_any = False

                for w in range(max_W):
                    if valid_mask[l, w]:
                        has_any = True

                        break

                if not has_any:
                    bl_ok = False

                    break

            if not bl_ok:
                continue

            base_l = i

            min_count = 999999

            for l in range(i, j):
                c = 0

                for w in range(max_W):
                    if valid_mask[l, w]:
                        c += 1

                if c < min_count:
                    min_count = c

                    base_l = l

            temp_costs = np.zeros(max_W, dtype=np.float64)

            temp_wls = np.zeros(max_W, dtype=np.float64)

            temp_count = 0

            for base_w_idx in range(max_W):
                if not valid_mask[base_l, base_w_idx]:
                    continue

                wl = layer_wls[base_l, base_w_idx]

                total_cost = layer_costs[base_l, base_w_idx]

                is_valid = True

                for l in range(i, j):
                    if l == base_l:
                        continue

                    found = False

                    for w in range(max_W):
                        if valid_mask[l, w] and abs(layer_wls[l, w] - wl) < 1e-5:
                            total_cost += layer_costs[l, w]

                            found = True

                            break

                    if not found:
                        is_valid = False

                        break

                if is_valid:
                    temp_costs[temp_count] = total_cost

                    temp_wls[temp_count] = wl

                    temp_count += 1

            if temp_count > 0:
                for x in range(temp_count):
                    for y in range(x + 1, temp_count):
                        if temp_costs[y] < temp_costs[x]:
                            tc = temp_costs[x]

                            temp_costs[x] = temp_costs[y]

                            temp_costs[y] = tc

                            tw = temp_wls[x]

                            temp_wls[x] = temp_wls[y]

                            temp_wls[y] = tw

                take = min(temp_count, top_k)

                for k in range(take):
                    block_costs[i, j, k] = temp_costs[k]

                    block_wls[i, j, k] = temp_wls[k]

                block_counts[i, j] = take

    return block_costs, block_wls, block_counts


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _dp_kernel(
    block_costs: np.ndarray,
    block_wls: np.ndarray,
    block_counts: np.ndarray,
    n_blocks: int,
    num_layers: int,
    top_k: int,
):

    dp_costs = np.full((n_blocks + 1, num_layers + 1, top_k * 2), np.inf, dtype=np.float64)

    dp_paths_start = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)

    dp_paths_end = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)

    dp_paths_wl = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1.0, dtype=np.float64)

    dp_counts = np.zeros((n_blocks + 1, num_layers + 1), dtype=np.int32)

    dp_costs[0, 0, 0] = 0.0

    dp_counts[0, 0] = 1

    max_cands = top_k * 2

    temp_costs = np.zeros(max_cands, dtype=np.float64)

    temp_paths_start = np.full((max_cands, n_blocks), -1, dtype=np.int32)

    temp_paths_end = np.full((max_cands, n_blocks), -1, dtype=np.int32)

    temp_paths_wl = np.full((max_cands, n_blocks), -1.0, dtype=np.float64)

    for k in range(1, n_blocks + 1):
        for i in range(k, num_layers + 1):
            c_count = 0

            for j in range(k - 1, i):
                prev_count = dp_counts[k - 1, j]

                if prev_count == 0:
                    continue

                bl_count = block_counts[j, i]

                if bl_count == 0:
                    continue

                for p in range(prev_count):
                    prev_cost = dp_costs[k - 1, j, p]

                    for b in range(min(10, bl_count)):
                        total_cost = prev_cost + block_costs[j, i, b]

                        wl = block_wls[j, i, b]

                        if c_count == max_cands and total_cost >= temp_costs[max_cands - 1]:
                            continue

                        idx = c_count if c_count < max_cands else max_cands - 1

                        while idx > 0 and temp_costs[idx - 1] > total_cost:
                            if idx < max_cands:
                                temp_costs[idx] = temp_costs[idx - 1]

                                for _b in range(n_blocks):
                                    temp_paths_start[idx, _b] = temp_paths_start[idx - 1, _b]

                                    temp_paths_end[idx, _b] = temp_paths_end[idx - 1, _b]

                                    temp_paths_wl[idx, _b] = temp_paths_wl[idx - 1, _b]

                            idx -= 1

                        temp_costs[idx] = total_cost

                        for old_h in range(k - 1):
                            temp_paths_start[idx, old_h] = dp_paths_start[k - 1, j, p, old_h]

                            temp_paths_end[idx, old_h] = dp_paths_end[k - 1, j, p, old_h]

                            temp_paths_wl[idx, old_h] = dp_paths_wl[k - 1, j, p, old_h]

                        temp_paths_start[idx, k - 1] = j

                        temp_paths_end[idx, k - 1] = i

                        temp_paths_wl[idx, k - 1] = wl

                        if c_count < max_cands:
                            c_count += 1

            if c_count > 0:
                for t in range(c_count):
                    dp_costs[k, i, t] = temp_costs[t]

                    for _b in range(n_blocks):
                        dp_paths_start[k, i, t, _b] = temp_paths_start[t, _b]

                        dp_paths_end[k, i, t, _b] = temp_paths_end[t, _b]

                        dp_paths_wl[k, i, t, _b] = temp_paths_wl[t, _b]

                dp_counts[k, i] = c_count

    return dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _solve_quadratic_target(a: float, b: float, c: float, target_y: float, current_x: float) -> float:

    c_prime = c - target_y

    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            return -c_prime / b

        return current_x

    discriminant = b * b - 4.0 * a * c_prime

    if discriminant >= 0.0:
        sqrt_disc = np.sqrt(discriminant)

        sol1 = (-b + sqrt_disc) / (2.0 * a)

        sol2 = (-b - sqrt_disc) / (2.0 * a)

        if abs(sol1 - current_x) < abs(sol2 - current_x):
            return sol1

        return sol2

    else:
        return -b / (2.0 * a)


# --- 6.2 Growth Simulation ---


# --- LOCKED --- Validated by test_tmm_inline.py (test 2) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


# Non-monotonic handling modes (for simulate_growth_kernel)


NON_MONOTONIC_MODE_ATTENUATE = 0  # Divide error by factor (legacy behavior)


NON_MONOTONIC_MODE_REJECT = 1  # Reject candidate (return large error)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_growth_kernel(
    p_thick_nominal: np.ndarray,
    i_layer: int,
    prev_thicknesses_sim: np.ndarray,
    wl: float,
    n_H,
    n_L,
    n_Sub,  # float or complex (Numba multi-dispatch)
    probe_offset: float,
    noise_val_precalc: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
) -> tuple[float, float]:
    """

    Fast TMM Simulation for robustness heuristics.

    CRITICAL PHYSICS NOTE:

    This kernel calculates T_front (Internal Transmission) ONLY.

    It intentionally IGNORES backside reflection for computational speed in heuristics.

    Do not use for absolute photometric accuracy. Use calculate_detailed_growth for that.

    This is a RELATIVE control kernel: target extraction and inversion both use the

    same front-only model, so there is no absolute backside mismatch in this loop.

    Args:

        non_monotonic_mode: How to handle non-monotonic T(d) curves:

            0 (ATTENUATE): Divide error by non_monotonic_factor (legacy)

            1 (REJECT): Return large penalty to reject candidate

    """

    if wl < 0.1:
        return float(p_thick_nominal[i_layer]), 0.0

    # Numba infers precision from input dtypes automatically.

    TWO_PI_VAL = TWO_PI

    M_before_00 = 1.0 + 0j

    M_before_01 = 0.0 + 0j

    M_before_10 = 0.0 + 0j

    M_before_11 = 1.0 + 0j

    for j in range(i_layer):
        n_prev = n_H if (j % 2) == 0 else n_L

        th_prev = prev_thicknesses_sim[j]

        phi = (TWO_PI_VAL / wl) * n_prev * th_prev

        cp, sp = np.cos(phi), np.sin(phi)

        son = (sp / n_prev) if abs(n_prev) > 1e-9 else 0.0

        m01 = +1j * son

        m10 = +1j * n_prev * sp

        # TMM CONVENTION: Air->Sub. M_new = L_new @ M_old (pre-multiply)

        t00 = cp * M_before_00 + m01 * M_before_10

        t01 = cp * M_before_01 + m01 * M_before_11

        t10 = m10 * M_before_00 + cp * M_before_10

        t11 = m10 * M_before_01 + cp * M_before_11

        M_before_00, M_before_01, M_before_10, M_before_11 = t00, t01, t10, t11

    nominal_th = p_thick_nominal[i_layer]

    n_current = n_H if (i_layer % 2) == 0 else n_L

    is_non_monotonic = False

    # Check monotonicity & Target T

    # Zero-Allocation: Only compute the 5 points needed for monotonicity check
    T_mono = np.zeros(5, dtype=np.float64)

    if nominal_th > 1e-4:
        for k in range(5):
            th_frac = (k / 4.0) * nominal_th

            phi_c = (TWO_PI_VAL / wl) * n_current * th_frac

            cp_c, sp_c = np.cos(phi_c), np.sin(phi_c)

            son_c = (sp_c / n_current) if abs(n_current) > 1e-9 else 0.0

            # M_total = L_current @ M_before (pre-multiply)

            m01_c = +1j * son_c

            m10_c = +1j * n_current * sp_c

            a00 = cp_c * M_before_00 + m01_c * M_before_10

            a01 = cp_c * M_before_01 + m01_c * M_before_11

            a10 = m10_c * M_before_00 + cp_c * M_before_10

            a11 = m10_c * M_before_01 + cp_c * M_before_11

            # Air->Sub Transmission (n_inc=1, n_exit=n_Sub)

            denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

            if abs(denom) > 1e-9:
                T_mono[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)

        # Monotonicity check logic
        diffs = np.zeros(4, dtype=np.float64)
        for k in range(4):
            diffs[k] = T_mono[k+1] - T_mono[k]

        flips = 0
        current_sign = 0.0

        if diffs[0] > 1e-9:
            current_sign = 1.0
        elif diffs[0] < -1e-9:
            current_sign = -1.0

        for k in range(1, 4):
            next_sign = 0.0
            if diffs[k] > 1e-9:
                next_sign = 1.0
            elif diffs[k] < -1e-9:
                next_sign = -1.0

            if next_sign != 0.0:
                if current_sign != 0.0 and next_sign != current_sign:
                    flips += 1
                current_sign = next_sign

        if flips > 0:
            is_non_monotonic = True

    target_T_noisy = T_mono[4] + noise_val_precalc

    # Numerical solve via parabolic probe

    th_points = np.array([max(0.1, nominal_th - probe_offset), nominal_th, nominal_th + probe_offset])

    T_points = np.zeros(3)

    for k in range(3):
        d = th_points[k]

        phi = (TWO_PI_VAL / wl) * n_current * d

        cp, sp = np.cos(phi), np.sin(phi)

        son = (sp / n_current) if abs(n_current) > 1e-9 else 0.0

        m01 = +1j * son

        m10 = +1j * n_current * sp

        a00 = cp * M_before_00 + m01 * M_before_10

        a01 = cp * M_before_01 + m01 * M_before_11

        a10 = m10 * M_before_00 + cp * M_before_10

        a11 = m10 * M_before_01 + cp * M_before_11

        denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

        if abs(denom) > 1e-9:
            T_points[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)

    a_quad, b_quad, c_quad = fit_parabola_vertex_3points(th_points, T_points)

    calc_thick = _solve_quadratic_target(a_quad, b_quad, c_quad, target_T_noisy, nominal_th)

    error_raw = calc_thick - nominal_th

    dyn_encounter = 0.0

    if nominal_th > 1e-4:
        dyn_encounter = np.max(T_mono) - np.min(T_mono)

    # Non-monotonic handling

    if is_non_monotonic:
        if non_monotonic_mode == NON_MONOTONIC_MODE_REJECT:
            # Return nominal thickness with a large penalty error signal

            # The caller will see a very large error for this candidate

            return nominal_th + 1e6, dyn_encounter

        else:
            # Legacy: attenuate error by dividing

            gain = non_monotonic_factor

            return max(0.0, nominal_th + (error_raw / gain)), dyn_encounter

    return max(0.0, nominal_th + error_raw), dyn_encounter


# --- STRAT: transmission sensitivity for thickness-noise conversion ---


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_at_layer(
    wl: float,
    n_layer,
    n_Sub,
    M_before_00,
    M_before_01,
    M_before_10,
    M_before_11,
    d: float,
) -> float:
    """

    Compute front-side T at end of a single layer (same convention as simulate_growth_kernel).

    Used to compute dT/dd for converting thickness noise (nm) to transmission noise.

    """

    if wl < 0.1:
        return 0.0

    TWO_PI_VAL = TWO_PI

    phi = (TWO_PI_VAL / wl) * n_layer * d

    cp, sp = np.cos(phi), np.sin(phi)

    son = (sp / n_layer) if abs(n_layer) > 1e-9 else 0.0

    m01 = +1j * son

    m10 = +1j * n_layer * sp

    a00 = cp * M_before_00 + m01 * M_before_10

    a01 = cp * M_before_01 + m01 * M_before_11

    a10 = m10 * M_before_00 + cp * M_before_10

    a11 = m10 * M_before_01 + cp * M_before_11

    denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

    if abs(denom) > 1e-9:
        return float(4.0 * np.real(n_Sub) / (denom.real**2 + denom.imag**2))

    return 0.0


# --- 6.3 Validation Batch ---


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def validate_wavelengths_batch(
    candidate_wls,
    n_H_arr,
    n_L_arr,
    n_Sub_arr,
    runs_history,
    p_thick_nominal,
    i_layer,
    probe_offset,
    noise_values,
    non_monotonic_factor,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
):

    n_cands = len(candidate_wls)

    n_runs = runs_history.shape[0]

    results = np.zeros((n_cands, 2))

    # Zero-Allocation: Pre-allocate thread-local buffer outside the parallel loop
    error_buffer = np.empty((n_cands, n_runs), dtype=np.float64)

    for c_idx in prange(n_cands):
        wl = candidate_wls[c_idx]

        for r_idx in range(n_runs):
            prev_th = runs_history[r_idx, :i_layer]

            val, _ = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                prev_th,
                wl,
                n_H_arr[c_idx],
                n_L_arr[c_idx],
                n_Sub_arr[c_idx],
                probe_offset,
                noise_values[r_idx],
                non_monotonic_factor,
                non_monotonic_mode,
            )

            error_buffer[c_idx, r_idx] = np.abs(val - p_thick_nominal[i_layer])

        # P95-first policy: cost uses high-percentile absolute error
        # to keep margin cases in ranking decisions.
        p95 = np.percentile(error_buffer[c_idx, :], 95.0)
        results[c_idx, 0] = p95
        results[c_idx, 1] = np.std(error_buffer[c_idx, :])

    return results


# --- 6.3b Full Stack Robustness Simulation Batch (New Phase B Kernel) ---


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_stack_robustness_batch(
    p_thick_nominal: np.ndarray,
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    noise_matrix: np.ndarray,  # (n_runs, n_layers)
    probe_offset: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Simulates growth for the entire stack for multiple MCS runs in parallel.

    Returns: (simulated_thicknesses, average_dynamics_per_layer)

    """

    n_runs = noise_matrix.shape[0]

    n_layers = len(p_thick_nominal)

    results = np.empty((n_runs, n_layers), dtype=np.float64)

    all_dyns = np.empty((n_runs, n_layers), dtype=np.float64)

    # Zero-Allocation: pre-allocate memory for run stack tracking
    current_run_th_buffer = np.empty((n_runs, n_layers), dtype=np.float64)

    for r in prange(n_runs):
        for i_layer in range(n_layers):
            wl = layer_wavelengths[i_layer]

            n_H, n_L, n_Sub = n_H_vals[i_layer], n_L_vals[i_layer], n_Sub_vals[i_layer]

            noise_val = noise_matrix[r, i_layer]

            val, dyn = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                current_run_th_buffer[r, :i_layer],
                wl,
                n_H,
                n_L,
                n_Sub,
                probe_offset,
                noise_val,
                non_monotonic_factor,
                non_monotonic_mode,
            )

            current_run_th_buffer[r, i_layer] = val

            results[r, i_layer] = val

            all_dyns[r, i_layer] = dyn

    avg_dyns = np.zeros(n_layers, dtype=np.float64)

    for l in range(n_layers):
        sum_dyn = 0.0

        for r in range(n_runs):
            sum_dyn += all_dyns[r, l]

        avg_dyns[l] = sum_dyn / n_runs

    return results, avg_dyns


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_batch_rmse(
    sim_thick_batch: np.ndarray,
    wls: np.ndarray,
    nH_arr: np.ndarray,  # (n_wls, n_layers) or (n_wls,) depending on implementation needed
    nL_arr: np.ndarray,  # We probably need n_layers_all_wls structure or similar
    nSub_arr: np.ndarray,  # (n_wls,)
    T_target: np.ndarray,
    n_layers_flattened: np.ndarray,  # (n_wls, n_layers) - pre-computed n complex for all layers
) -> np.ndarray:
    """Computes RMSE for a batch of simulated thicknesses against a target T spectrum.

    Args:

        sim_thick_batch: (n_runs, n_layers)

        wls: (n_wls,)

        nSub_arr: (n_wls,)

        T_target: (n_wls,)

        n_layers_flattened: (n_wls, n_layers) complex array of refractive clues

                           This must be pre-assembled: [n0_w0, n1_w0...; n0_w1, n1_w1...]

    Returns:

        rmse_arr: (n_runs,)"""

    n_runs = sim_thick_batch.shape[0]

    n_wls = len(wls)

    rmse_arr = np.empty(n_runs, dtype=np.float64)

    # Pre-calculate k0

    k0_arr = TWO_PI / wls

    for r in prange(n_runs):
        thicknesses = sim_thick_batch[r]

        mse_sum = 0.0

        # Inner loop over wavelengths

        for i_wl in range(n_wls):
            Rf, Tf, Rb = compute_TMM_single_point_k0_exact(
                k0_arr[i_wl], thicknesses, n_layers_flattened[i_wl], nSub_arr[i_wl]
            )

            # Backside correction (exact incoherent combination) - Float64 logic

            ns_real = nSub_arr[i_wl].real

            r_sub = (ns_real - 1.0) / (ns_real + 1.0)

            R_sub_air = r_sub * r_sub

            T_sub_air = 1.0 - R_sub_air

            denom = 1.0 - Rb * R_sub_air

            if denom < 1e-12:
                denom = 1e-12

            T_total = (Tf * T_sub_air) / denom

            diff = T_total - T_target[i_wl]

            mse_sum += diff * diff

        rmse_arr[r] = np.sqrt(mse_sum / n_wls)

    return rmse_arr


# --- 6.4 Dynamic Calculation ---


# --- LOCKED --- Validated by test_tmm_inline.py (test 1, via cache) ───


# Macleod convention (+1j). Pre-multiply (L @ M). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def precompute_matrix_cache_kernel(
    all_wls: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    p_thick_nominal: np.ndarray,
    num_layers: int,
) -> np.ndarray:
    """Parallel computation of nominal transfer matrix cache.

    Supports complex refractive clues for nH and nL."""

    n_wls = len(all_wls)

    TWO_PI_LOCAL = 2.0 * np.pi

    cache = np.zeros((num_layers, n_wls, 2, 2), dtype=np.complex128)

    for wl_idx in prange(n_wls):
        wl = all_wls[wl_idx]

        inv_wl = TWO_PI_LOCAL / wl

        # Cumulative matrix (identity start)

        M00 = complex(1.0, 0.0)

        M01 = complex(0.0, 0.0)

        M10 = complex(0.0, 0.0)

        M11 = complex(1.0, 0.0)

        for i_layer in range(num_layers):
            n_layer = n_H_arr[wl_idx] if (i_layer % 2) == 0 else n_L_arr[wl_idx]

            thickness = p_thick_nominal[i_layer]

            phi = inv_wl * n_layer * thickness

            cp = np.cos(phi)

            isp = +1j * np.sin(phi)

            if abs(n_layer) > 1e-12:
                m01 = isp / n_layer

            else:
                m01 = 0.0j

            m10 = isp * n_layer

            # M_new = L @ M_old (aligned with reference verify_matrix_cache: index 0 = substrate)

            t00 = cp * M00 + m01 * M10

            t01 = cp * M01 + m01 * M11

            t10 = m10 * M00 + cp * M10

            t11 = m10 * M01 + cp * M11

            M00, M01, M10, M11 = t00, t01, t10, t11

            # Store cumulative

            cache[i_layer, wl_idx, 0, 0] = M00

            cache[i_layer, wl_idx, 0, 1] = M01

            cache[i_layer, wl_idx, 1, 0] = M10

            cache[i_layer, wl_idx, 1, 1] = M11

    return cache


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def prepare_dynamics_data_kernel(
    wls_array: np.ndarray,
    all_wls: np.ndarray,
    nominal_matrix_cache: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    n_Sub_arr: np.ndarray,
    i_layer: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Parallel preparation of data for dynamics calculation.

    """

    n = len(wls_array)

    n_layer_array = np.empty(n, dtype=np.complex128)

    n_sub_array = np.empty(n, dtype=np.complex128)

    M_before_stack = np.empty((n, 2, 2), dtype=np.complex128)

    for i in prange(n):
        wl = wls_array[i]

        # 1. Clues

        if (i_layer % 2) == 0:
            n_layer_array[i] = n_H_arr[i]

        else:
            n_layer_array[i] = n_L_arr[i]

        n_sub_array[i] = n_Sub_arr[i]

        # 2. Matrix Cache

        M_before_stack[i, 0, 0] = 1.0

        M_before_stack[i, 0, 1] = 0.0

        M_before_stack[i, 1, 0] = 0.0

        M_before_stack[i, 1, 1] = 1.0

        if i_layer > 0:
            # Fast Nearest Search

            idx = np.searchsorted(all_wls, wl)

            if idx >= len(all_wls):
                idx = len(all_wls) - 1

            elif idx > 0:
                diff_curr = abs(wl - all_wls[idx])

                diff_prev = abs(wl - all_wls[idx - 1])

                if diff_prev < diff_curr:
                    idx = idx - 1

            # Using complex matrix (Single Precision optimized)

            # nominal_matrix_cache shape: (n_layers, n_wls, 2, 2)

            M_before_stack[i, 0, 0] = nominal_matrix_cache[i_layer - 1, idx, 0, 0]

            M_before_stack[i, 0, 1] = nominal_matrix_cache[i_layer - 1, idx, 0, 1]

            M_before_stack[i, 1, 0] = nominal_matrix_cache[i_layer - 1, idx, 1, 0]

            M_before_stack[i, 1, 1] = nominal_matrix_cache[i_layer - 1, idx, 1, 1]

    return n_layer_array, n_sub_array, M_before_stack


# --- LOCKED --- Validated by test_tmm_inline.py (test 7, wrapper) ───


# DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def check_extrema_proximity_batch(
    wls: np.ndarray,
    n_currents: np.ndarray,
    n_previouss: np.ndarray,
    n_Subs: np.ndarray,
    thickness_nominal: float,
    M_befores: np.ndarray,
    exclusion_width: float,
    check_start: bool,
    wl_changed_arr: np.ndarray,
) -> np.ndarray:
    """

    Parallel batch version of check_extrema_proximity.

    wl_changed_arr: boolean array (len = len(wls)).

        True  -> candidate wavelength differs from previous layer's -> asymmetric start check.

        False -> same wavelength, symmetric start check only.

    """

    n = len(wls)

    results = np.empty(n, dtype=np.bool_)

    for i in prange(n):
        results[i] = check_extrema_proximity(
            wls[i],
            n_currents[i],
            n_previouss[i],
            n_Subs[i],
            thickness_nominal,
            M_befores[i],
            exclusion_width,
            check_start,
            wl_changed_arr[i],
        )

    return results


# --- LOCKED --- Validated by test_tmm_inline.py (test 1) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores):
    """

    Compute TMM dynamics: peak-to-peak range of T(d) over layer growth.

    For each wavelength, T(d) is evaluated at thickness steps from 0 to

    nominal thickness. The dynamics metric is T_max - T_min (not endpoint

    delta). Returns dynamics, t_init, t_final, t_min (min T over growth).

    Precision adapts to input dtypes via Numba JIT.

    """

    n_wls = wls.shape[0]

    n_steps = thicknesses.shape[0]

    dynamics = np.empty(n_wls, dtype=np.float64)

    t_init = np.empty(n_wls, dtype=np.float64)

    t_final = np.empty(n_wls, dtype=np.float64)

    t_min = np.empty(n_wls, dtype=np.float64)

    I_VAL = +1j

    for wl_idx in prange(n_wls):
        wl = wls[wl_idx]

        n_layer = n_layers[wl_idx]

        n_sub = n_subs[wl_idx]

        M_before_00 = M_befores[wl_idx, 0, 0]

        M_before_01 = M_befores[wl_idx, 0, 1]

        M_before_10 = M_befores[wl_idx, 1, 0]

        M_before_11 = M_befores[wl_idx, 1, 1]

        T_min_val = 2.0

        T_max = -1.0

        T_start = 0.0

        T_end = 0.0

        for step_idx in range(n_steps):
            thickness = thicknesses[step_idx]

            if wl < 0.1:
                T_current = 0.0

            else:
                phi = (TWO_PI / wl) * n_layer * thickness

                cp, sp = np.cos(phi), np.sin(phi)

                son = (sp / n_layer) if abs(n_layer) > 1e-9 else 0.0

                m01 = I_VAL * son

                m10 = I_VAL * n_layer * sp

                # L @ M_before (pre-multiply: new layer on air side)

                a00 = cp * M_before_00 + m01 * M_before_10

                a01 = cp * M_before_01 + m01 * M_before_11

                a10 = m10 * M_before_00 + cp * M_before_10

                a11 = m10 * M_before_01 + cp * M_before_11

                # Air->Sub formula (n_inc=1, n_exit=n_sub)

                denom = a00 + n_sub * a01 + a10 + n_sub * a11

                if abs(denom) > 1e-9:
                    T_current = 4.0 * np.real(n_sub) / (denom.real**2 + denom.imag**2)

                else:
                    T_current = 0.0

            if step_idx == 0:
                T_start = T_current

            if step_idx == n_steps - 1:
                T_end = T_current

            if T_current < T_min_val:
                T_min_val = T_current

            if T_current > T_max:
                T_max = T_current

        dynamics[wl_idx] = T_max - T_min_val

        t_init[wl_idx] = T_start

        t_final[wl_idx] = T_end

        t_min[wl_idx] = T_min_val

    return dynamics, t_init, t_final, t_min


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). index 0 = substrate. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _calculate_RT_HL_single_point(wl, nH, nL, n_s, thicknesses):
    """Single wavelength, single run TMM for HL stacks.

    CONVENTION: index 0 = layer 1 = substrate side (aligned with compute_TMM_single_point_k0_exact).

    j=0 -> nH, j=1 -> nL => Sub | nH(thicknesses[0]) | nL(thicknesses[1]) | Air."""

    k0 = TWO_PI / wl

    n_layers = len(thicknesses)

    I_VAL = +1j

    # Forward Air->Sub: M = L_{n-1} @ ... @ L_0 (pre-multiply, index 0 = substrate side)

    M00 = 1.0 + 0j

    M01 = 0.0 + 0j

    M10 = 0.0 + 0j

    M11 = 1.0 + 0j

    for j in range(n_layers):
        d = thicknesses[j]

        n_l = nH if j % 2 == 0 else nL

        phi = k0 * n_l * d

        cp = np.cos(phi)

        sp = np.sin(phi)

        son = (sp / n_l) if abs(n_l) > 1e-12 else 0.0j

        m01 = I_VAL * son

        m10 = I_VAL * n_l * sp

        # M_new = L @ M_old

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    # --- Front (Air -> Sub): delegate to helper ---

    n_air = complex(1.0)

    R_front, T_front = compute_RT_from_matrix(M00, M01, M10, M11, n_air, n_s)

    # --- BACK REFLECTION (Sub -> Air) ---

    # Mp = L_0 @ ... @ L_{n-1} (Sub->Air, post-multiply)

    Mp00 = 1.0 + 0j

    Mp01 = 0.0 + 0j

    Mp10 = 0.0 + 0j

    Mp11 = 1.0 + 0j

    for j in range(n_layers):
        d = thicknesses[j]

        n_l = nH if j % 2 == 0 else nL

        phi = k0 * n_l * d

        cp = np.cos(phi)

        sp = np.sin(phi)

        son = (sp / n_l) if abs(n_l) > 1e-12 else 0.0j

        m01 = I_VAL * son

        m10 = I_VAL * n_l * sp

        # Mp_new = Mp_old @ L

        t00 = Mp00 * cp + Mp01 * m10

        t01 = Mp00 * m01 + Mp01 * cp

        t10 = Mp10 * cp + Mp11 * m10

        t11 = Mp10 * m01 + Mp11 * cp

        Mp00, Mp01, Mp10, Mp11 = t00, t01, t10, t11

    # Back reflection: Sub -> Air, delegate to helper

    R_prime, _ = compute_RT_from_matrix(Mp00, Mp01, Mp10, Mp11, n_s, n_air)

    # --- Backside Interface (Sub|Air) ---

    nsr = n_s.real

    r_sub = (nsr - 1.0) / (nsr + 1.0)

    R_sub = r_sub * r_sub

    T_sub = 1.0 - R_sub

    # --- Combined result ---

    denom = 1.0 - R_prime * R_sub

    if denom < 1e-12:
        denom = 1e-12

    T_total = (T_front * T_sub) / denom

    R_total = R_front + (T_front * T_front * R_sub) / denom

    return R_total, T_total


# --- LOCKED --- Validated by test_tmm_coherence.py (via calculate_RT_vectorized_real_HL) ───


# Macleod convention (+1j). Batch TMM HL + backside exact. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, thicknesses_batch):
    """

    Parallel loop over 'num_runs', where each run is a full TMM spectral calculation.

    thicknesses_batch: (num_runs, num_layers)

    """

    n_runs = thicknesses_batch.shape[0]

    n_wls = wls.shape[0]

    R_batch = np.empty((n_runs, n_wls), dtype=np.float64)

    T_batch = np.empty((n_runs, n_wls), dtype=np.float64)

    for r in prange(n_runs):
        thicknesses = thicknesses_batch[r]

        for wl_idx in range(n_wls):
            r_val, t_val = _calculate_RT_HL_single_point(
                wls[wl_idx],
                nH_arr[wl_idx],
                nL_arr[wl_idx],
                nSub_arr[wl_idx],
                thicknesses,
            )

            R_batch[r, wl_idx] = r_val

            T_batch[r, wl_idx] = t_val

    return R_batch, T_batch


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def rank_nucleation_candidates_kernel(
    candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_vals: np.ndarray,  # (n_cand,) complex
    nL_vals: np.ndarray,  # (n_cand,) complex
    nSub_vals: np.ndarray,  # (n_cand,) complex
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    mc_runs: int,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel to rank candidate wavelengths for nucleation search.

    Replaces the sequential 'pre-ranking' loop in find_robust_nucleation_wavelength_adaptive.

    NOTE (Numba/runtime):

    Random sampling is generated inside the jitted kernel for performance.

    This is not an independent physics model: STRAT passes `use_gaussian=True`

    in production, and this kernel follows that policy.

    """

    n_cand = len(candidates)

    scores = np.zeros(n_cand, dtype=np.float64)

    for i in prange(n_cand):
        wl = candidates[i]

        nH = nH_vals[i]

        nL = nL_vals[i]

        nSub = nSub_vals[i]

        cumulative_sq_error = 0.0

        for run_idx in range(mc_runs):
            # Configurable noise distribution (STRAT uses gaussian-only).

            noise_vec = np.zeros(min_size, dtype=np.float64)
            for j in range(min_size):
                raw_j = _seeded_noise_sample(
                    seed_base=seed_base,
                    group_idx=i,
                    run_idx=run_idx,
                    elem_idx=j,
                    gaussian=use_gaussian,
                )
                noise_vec[j] = raw_j * noise_pct

            current_stack = np.zeros(min_size, dtype=np.float64)

            for j in range(min_size):
                th, _ = simulate_growth_kernel(
                    p_thick_nominal,
                    j,
                    current_stack[:j],
                    wl,
                    nH,
                    nL,
                    nSub,
                    offset_val,
                    noise_vec[j],
                    factor_val,
                    non_monotonic_mode,
                )

                current_stack[j] = th

                cumulative_sq_error += (th - p_thick_nominal[j]) ** 2

        scores[i] = np.sqrt(cumulative_sq_error / (mc_runs * min_size))

    return scores


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _seeded_noise_sample(seed_base: int, group_idx: int, run_idx: int, elem_idx: int, gaussian: bool) -> np.float64:
    s = (
        np.uint64(seed_base)
        + np.uint64(0x9E3779B97F4A7C15) * np.uint64(group_idx + 1)
        + np.uint64(0xBF58476D1CE4E5B9) * np.uint64(run_idx + 1)
        + np.uint64(0x94D049BB133111EB) * np.uint64(elem_idx + 1)
    )
    if not gaussian:
        x = s
        x ^= x >> np.uint64(12)
        x ^= x << np.uint64(25)
        x ^= x >> np.uint64(27)
        x = x * np.uint64(2685821657736338717)
        u = (x >> np.uint64(11)) * (1.0 / 9007199254740992.0)
        return 2.0 * u - 1.0

    acc = 0.0
    for k in range(12):
        x = s + np.uint64(0xD2B74407B1CE6E93) * np.uint64(k + 1)
        x ^= x >> np.uint64(12)
        x ^= x << np.uint64(25)
        x ^= x >> np.uint64(27)
        x = x * np.uint64(2685821657736338717)
        acc += (x >> np.uint64(11)) * (1.0 / 9007199254740992.0)
    z = (acc - 6.0) / 3.0
    if z < -1.0:
        return -1.0
    if z > 1.0:
        return 1.0
    return z


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def find_nucleation_adaptive_kernel(
    valid_candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    max_size: int,
    mc_runs: int,
    degradation_threshold: float,
    max_rmse_per_layer: float,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel for adaptive nucleation Search.

    Optimizes the triple loop (candidates x sizes x mc_runs).

    NOTE (Numba/runtime):

    Noise generation is in-kernel by design for performance and to avoid Python

    allocation overhead in inner loops. STRAT production calls enforce gaussian mode.

    """

    n_cand = len(valid_candidates)

    results_size = np.zeros(n_cand, dtype=np.int32)

    results_rmse = np.zeros(n_cand, dtype=np.float64)

    for i_cand in prange(n_cand):
        nH = nH_arr[i_cand]

        nL = nL_arr[i_cand]

        nSub = nSub_arr[i_cand]

        wl = valid_candidates[i_cand]

        prev_rmse_metric = 0.0

        last_valid_size = 0

        final_rmse = 0.0

        rmse_floor = 0.05

        for size in range(min_size, max_size + 1):
            cumulative_sq_error = 0.0

            for run_idx in range(mc_runs):
                # Configurable noise distribution (STRAT uses gaussian-only).

                noise_vec = np.zeros(size, dtype=np.float64)
                for i in range(size):
                    raw_i = _seeded_noise_sample(
                        seed_base=seed_base,
                        group_idx=i_cand + size,
                        run_idx=run_idx,
                        elem_idx=i,
                        gaussian=use_gaussian,
                    )
                    noise_vec[i] = raw_i * noise_pct

                current_stack = np.zeros(size, dtype=np.float64)

                for i in range(size):
                    th, _ = simulate_growth_kernel(
                        p_thick_nominal,
                        i,
                        current_stack[:i],
                        wl,
                        nH,
                        nL,
                        nSub,
                        offset_val,
                        noise_vec[i],
                        factor_val,
                        non_monotonic_mode,
                    )

                    current_stack[i] = th

                    cumulative_sq_error += (th - p_thick_nominal[i]) ** 2

            rmse_total = np.sqrt(cumulative_sq_error / (mc_runs * size))

            if rmse_total > max_rmse_per_layer:
                break

            if size > min_size:
                ratio = rmse_total / max(prev_rmse_metric, rmse_floor)

                if ratio > degradation_threshold:
                    break

            last_valid_size = size

            prev_rmse_metric = rmse_total

            final_rmse = rmse_total

        results_size[i_cand] = last_valid_size

        results_rmse[i_cand] = final_rmse

    return results_size, results_rmse


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def update_run_states_kernel(
    p_thick_nom_arr: np.ndarray,
    i_layer: int,
    prev_stacks: np.ndarray,  # (num_runs, i_layer)
    best_wl: float,
    nH,  # float or complex (Numba multi-dispatch)
    nL,  # float or complex
    nSub,  # float or complex
    offset_val: float,
    noise_values: np.ndarray,  # (num_runs,)
    factor_val: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
):
    """Parallel update of simulation states for next layer."""

    num_runs = prev_stacks.shape[0]

    updates = np.empty(num_runs, dtype=np.float64)

    for r in prange(num_runs):
        updates[r], _ = simulate_growth_kernel(
            p_thick_nom_arr,
            i_layer,
            prev_stacks[r],
            best_wl,
            nH,
            nL,
            nSub,
            offset_val,
            noise_values[r],
            factor_val,
            non_monotonic_mode,
        )

    return updates


# =============================================================================


# BACKSIDE CORRECTION VALIDITY (Opus 4.6)


# =============================================================================


# The incoherent backside formula T = Tf*Tb/(1-Rp*Rb) is an approximation


# (where Rp = R_prime = stack reflectance seen from substrate side)


# valid ONLY when all refractive clues are effectively real.


# Thresholds (from thin-film optics practice):


#   - Layer materials (H, L): |Im(n)| < K_MAX_LAYER_BACKSIDE  (absorption < 0.1%)


#   - substrate:              |Im(n)| < K_MAX_SUBSTRATE_BACKSIDE (absorption < 0.001%)


K_MAX_LAYER_BACKSIDE: float = 0.001


K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def validate_backside_real_clues(n_H_imag: float, n_L_imag: float, n_Sub_imag: float) -> tuple[bool, bool, bool]:
    """Validates that refractive clues are real enough for incoherent

    backside correction to be physically valid.

    Args:

        n_H_imag: |Im(n_H)| at a representative wavelength

        n_L_imag: |Im(n_L)| at a representative wavelength

        n_Sub_imag: |Im(n_Sub)| at a representative wavelength

    Returns:

        (H_ok, L_ok, Sub_ok) - True if index is real enough for backside approx."""

    H_ok = abs(n_H_imag) < K_MAX_LAYER_BACKSIDE

    L_ok = abs(n_L_imag) < K_MAX_LAYER_BACKSIDE

    Sub_ok = abs(n_Sub_imag) < K_MAX_SUBSTRATE_BACKSIDE

    return H_ok, L_ok, Sub_ok


# --- LOCKED --- Validated by test_tmm_inline.py (test 3) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_detailed_growth(
    num_layers,
    p_thick_nominal,
    layer_wavelengths,
    n_H_arr,
    n_L_arr,
    n_Sub_arr,
    steps_per_layer_arr,
):
    """

    Detailed growth simulation with exact physics.

    CRITICAL PHYSICS NOTE:

    This function computes T_total including INCOHERENT BACKSIDE reflection.

    T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

    Matches the "Real World" signal seen by the monitor.

    The expression is intentionally expanded inline (instead of routing through

    compute_RT_from_matrix) for step-wise growth performance. Keep formulas aligned.

    """

    if num_layers == 0:
        return np.zeros(1), np.zeros(1), np.zeros(1)

    total_steps = np.sum(steps_per_layer_arr)

    total_points = total_steps + num_layers + 1

    x_points = np.empty(total_points)

    y_points = np.empty(total_points)

    layer_boundaries = np.empty(num_layers + 1)

    current_idx = 0

    cumulative_thick = 0.0

    layer_boundaries[0] = 0.0

    # Dual matrix tracking:

    #   F = forward (Air->Sub, pre-multiply L @ F) -> for T extraction

    #   R = reverse (Sub->Air, post-multiply R @ L) -> for backside R extraction

    F00 = 1.0 + 0j

    F01 = 0.0 + 0j

    F10 = 0.0 + 0j

    F11 = 1.0 + 0j

    R00 = 1.0 + 0j

    R01 = 0.0 + 0j

    R10 = 0.0 + 0j

    R11 = 1.0 + 0j

    prev_wl = -1.0

    for i_layer in range(num_layers):
        target_th = p_thick_nominal[i_layer]

        current_wl = layer_wavelengths[i_layer]

        if current_wl < 0.1:
            current_wl = 1500.0

        n_l_target = n_H_arr[i_layer] if (i_layer % 2) == 0 else n_L_arr[i_layer]

        n_s = n_Sub_arr[i_layer]

        nsr = n_s.real

        # Incoherent backside (Air|Sub)

        R_ext = ((nsr - 1.0) / (nsr + 1.0)) ** 2

        T_ext = 1.0 - R_ext

        # Sync before starting layer (wavelength change -> rebuild both matrices)

        if i_layer > 0 and abs(current_wl - prev_wl) > 1e-3:
            F00 = 1.0 + 0j

            F01 = 0.0 + 0j

            F10 = 0.0 + 0j

            F11 = 1.0 + 0j

            R00 = 1.0 + 0j

            R01 = 0.0 + 0j

            R10 = 0.0 + 0j

            R11 = 1.0 + 0j

            k0 = TWO_PI / current_wl

            for j in range(i_layer):
                dj = p_thick_nominal[j]

                # [FIX 2026] Use n at CURRENT monitoring wl, not layer j's block wl

                nj = n_H_arr[i_layer] if (j % 2) == 0 else n_L_arr[i_layer]

                phi = k0 * nj * dj

                cp = np.cos(phi)

                isp = +1j * np.sin(phi)

                mj01 = isp / nj if abs(nj) > 1e-9 else 0.0j

                mj10 = isp * nj

                # Forward: F = L @ F (pre-multiply, Air->Sub)

                t00 = cp * F00 + mj01 * F10

                t01 = cp * F01 + mj01 * F11

                t10 = mj10 * F00 + cp * F10

                t11 = mj10 * F01 + cp * F11

                F00, F01, F10, F11 = t00, t01, t10, t11

                # Reverse: R = R @ L (post-multiply, Sub->Air)

                t00 = R00 * cp + R01 * mj10

                t01 = R00 * mj01 + R01 * cp

                t10 = R10 * cp + R11 * mj10

                t11 = R10 * mj01 + R11 * cp

                R00, R01, R10, R11 = t00, t01, t10, t11

        k0_curr = TWO_PI / current_wl

        # Calculate T_start:

        # - Tf from forward matrix F (Air->Sub)

        # - "Rf" here is legacy naming and corresponds to R_prime-like reverse reflectance

        #   extracted from reverse matrix R (Sub->Air) for incoherent backside denominator.

        denom_f = F00 + n_s * F01 + F10 + n_s * F11  # Air->Sub: B+C, n_inc=1

        denom_r = n_s * R00 + n_s * R01 + R10 + R11  # Sub->Air: n_sub*(M00+M01)+(M10+M11)

        if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
            Tf = (4.0 * nsr) / (denom_f.real**2 + denom_f.imag**2)

            num_r = n_s * R00 + n_s * R01 - R10 - R11

            Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)

            T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

        else:
            T_val = 0.0

        x_points[current_idx] = cumulative_thick

        y_points[current_idx] = T_val

        current_idx += 1

        steps = steps_per_layer_arr[i_layer]

        step_sz = target_th / steps

        for s in range(1, steps + 1):
            d_partial = step_sz * s

            phi = k0_curr * n_l_target * d_partial

            cp = np.cos(phi)

            isp = +1j * np.sin(phi)

            mj01 = isp / n_l_target if abs(n_l_target) > 1e-9 else 0.0j

            mj10 = isp * n_l_target

            # Forward total: ft = L @ F (pre-multiply, for T)

            ft00 = cp * F00 + mj01 * F10

            ft01 = cp * F01 + mj01 * F11

            ft10 = mj10 * F00 + cp * F10

            ft11 = mj10 * F01 + cp * F11

            # Reverse total: rt = R @ L (post-multiply, for R_backside)

            rt00 = R00 * cp + R01 * mj10

            rt01 = R00 * mj01 + R01 * cp

            rt10 = R10 * cp + R11 * mj10

            rt11 = R10 * mj01 + R11 * cp

            # T from forward (Air->Sub) + R from reverse (Sub->Air)

            denom_f = ft00 + n_s * ft01 + ft10 + n_s * ft11

            denom_r = n_s * rt00 + n_s * rt01 + rt10 + rt11

            if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
                Tf = (4.0 * nsr) / (denom_f.real**2 + denom_f.imag**2)

                num_r = n_s * rt00 + n_s * rt01 - rt10 - rt11

                Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)

                val = (Tf * T_ext) / (1.0 - Rf * R_ext)

            else:
                val = 0.0

            x_points[current_idx] = cumulative_thick + d_partial

            y_points[current_idx] = val

            current_idx += 1

        # Advance both matrices with full layer

        phi_full = k0_curr * n_l_target * target_th

        cp = np.cos(phi_full)

        isp = +1j * np.sin(phi_full)

        mf01 = isp / n_l_target if abs(n_l_target) > 1e-9 else 0.0j

        mf10 = isp * n_l_target

        # Forward: F = L_full @ F (pre-multiply)

        t00 = cp * F00 + mf01 * F10

        t01 = cp * F01 + mf01 * F11

        t10 = mf10 * F00 + cp * F10

        t11 = mf10 * F01 + cp * F11

        F00, F01, F10, F11 = t00, t01, t10, t11

        # Reverse: R = R @ L_full (post-multiply)

        t00 = R00 * cp + R01 * mf10

        t01 = R00 * mf01 + R01 * cp

        t10 = R10 * cp + R11 * mf10

        t11 = R10 * mf01 + R11 * cp

        R00, R01, R10, R11 = t00, t01, t10, t11

        cumulative_thick += target_th

        layer_boundaries[i_layer + 1] = cumulative_thick

        prev_wl = current_wl

    return x_points[:current_idx], y_points[:current_idx], layer_boundaries


# =============================================================================