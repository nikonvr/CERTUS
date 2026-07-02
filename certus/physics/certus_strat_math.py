import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001


@njit(cache=True, fastmath=True, nogil=True, inline='always', error_model='numpy')
def _calc_T_from_matrix(m00: complex, m01: complex, m10: complex, m11: complex, n_Sub: complex) -> float:
    denom = m00 + n_Sub * m11 + n_Sub * m01 + m10
    if abs(denom) > 1e-09:
        t = 2.0 / denom
        return n_Sub.real * (t.real ** 2 + t.imag ** 2)
    return 0.0
@njit(cache=True, fastmath=True, nogil=True, inline='always', error_model='numpy')
def _calc_T_added_layer(wl: float, n_layer: complex, d_nm: float, n_Sub: complex, m00: complex, m01: complex, m10: complex, m11: complex) -> float:
    phi = TWO_PI / wl * n_layer * d_nm
    cp, sp = (np.cos(phi), np.sin(phi))
    son = sp / n_layer if abs(n_layer) > 1e-09 else 0.0
    ml00, ml01 = (cp, +1j * son)
    ml10, ml11 = (+1j * n_layer * sp, cp)
    mt00 = ml00 * m00 + ml01 * m10
    mt01 = ml00 * m01 + ml01 * m11
    mt10 = ml10 * m00 + ml11 * m10
    mt11 = ml10 * m01 + ml11 * m11
    return _calc_T_from_matrix(mt00, mt01, mt10, mt11, n_Sub)
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
def check_extrema_proximity(wl, n_current, n_previous, n_Sub, thickness_nominal, M_before, exclusion_width, check_start, wl_changed=False) -> bool:
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
    m00, m01 = (M_before[0, 0], M_before[0, 1])
    m10, m11 = (M_before[1, 0], M_before[1, 1])
    if wl < 0.1:
        return False
    TWO_PI_VAL = TWO_PI
    TOL = 1e-09
    if check_start:
        T_pres = _calc_T_from_matrix(m00, m01, m10, m11, n_Sub)
        T_fut = _calc_T_added_layer(wl, n_current, exclusion_width, n_Sub, m00, m01, m10, m11)
        n_prev_safe = n_previous if n_previous.real > 0.0 else n_current
        T_past = _calc_T_added_layer(wl, n_prev_safe, -exclusion_width, n_Sub, m00, m01, m10, m11)
        diff1, diff2 = (T_pres - T_past, T_fut - T_pres)
        if (diff1 > TOL and diff2 < -TOL) or (diff1 < -TOL and diff2 > TOL):
            return False
        if wl_changed:
            T_far = _calc_T_added_layer(wl, n_current, 3.0 * exclusion_width, n_Sub, m00, m01, m10, m11)
            s_mid_s = T_fut - T_pres
            s_right_s = (T_far - T_fut) / 2.0
            if (s_mid_s > TOL and s_right_s < -TOL) or (s_mid_s < -TOL and s_right_s > TOL):
                return False
    if thickness_nominal > exclusion_width:
        points = np.array([thickness_nominal - exclusion_width, thickness_nominal, thickness_nominal + exclusion_width, thickness_nominal + 3.0 * exclusion_width])
        T_end = np.zeros(4)
        for k in range(4):
            T_end[k] = _calc_T_added_layer(wl, n_current, points[k], n_Sub, m00, m01, m10, m11)
        s_left = T_end[1] - T_end[0]
        s_mid = T_end[2] - T_end[1]
        s_right = (T_end[3] - T_end[2]) / 2.0
        TOL_E = 1e-09
        if (s_left > TOL_E and s_mid < -TOL_E) or (s_left < -TOL_E and s_mid > TOL_E):
            return False
        if (s_mid > TOL_E and s_right < -TOL_E) or (s_mid < -TOL_E and s_right > TOL_E):
            return False
    return True
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
def calculate_extrema_distances(wl: float, n_current: complex, n_Sub: complex, thickness_nominal: float, M_before: np.ndarray) -> tuple[float, float, float, float]:
    """

    Performs a mini-scan to find the exact distance (in nm) to the nearest

    transmission extrema (turning points) from d=0 (start) and d=thickness_nominal (end).

    Returns:

        (dist_prev_start, dist_next_start, dist_prev_end, dist_next_end)

        Positive distances mean the extremum is purely that far away (absolute distance).

        If no extremum is found within 200nm, returns 999.0 for that value.

    """
    m00, m01 = (M_before[0, 0], M_before[0, 1])
    m10, m11 = (M_before[1, 0], M_before[1, 1])
    if wl < 0.1:
        return (999.0, 999.0, 999.0, 999.0)
    TWO_PI_VAL = TWO_PI
    scan_ot = 16.0
    physical_scan_radius = scan_ot / float(abs(n_current)) if abs(n_current) > 1e-09 else 16.0
    step = 0.5

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
        return (d_arr, T_arr)
    extrema_d = []
    TOL = 1e-09
    d_scan1, T_scan1 = scan_window(0.0)
    for i in range(1, len(d_scan1) - 1):
        s_left = T_scan1[i] - T_scan1[i - 1]
        s_right = T_scan1[i + 1] - T_scan1[i]
        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan1[i])
    d_scan2, T_scan2 = scan_window(thickness_nominal)
    for i in range(1, len(d_scan2) - 1):
        s_left = T_scan2[i] - T_scan2[i - 1]
        s_right = T_scan2[i + 1] - T_scan2[i]
        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan2[i])
    n_real = float(n_current.real)
    dist_prev_start, dist_next_start = (999.0, 999.0)
    dist_prev_end, dist_next_end = (999.0, 999.0)
    for ed in extrema_d:
        diff_start_ot = (ed - 0.0) * n_real
        if diff_start_ot <= 0:
            dist_prev_start = min(dist_prev_start, abs(diff_start_ot))
        if diff_start_ot >= 0:
            dist_next_start = min(dist_next_start, abs(diff_start_ot))
        diff_end_ot = (ed - thickness_nominal) * n_real
        if diff_end_ot <= 0:
            dist_prev_end = min(dist_prev_end, abs(diff_end_ot))
        if diff_end_ot >= 0:
            dist_next_end = min(dist_next_end, abs(diff_end_ot))
    return (dist_prev_start, dist_next_start, dist_prev_end, dist_next_end)
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
def fit_parabola_vertex_3points(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    x1, x2, x3 = (x[0], x[1], x[2])
    y1, y2, y3 = (y[0], y[1], y[2])
    denom = (x1 - x2) * (x1 - x3) * (x2 - x3)
    if abs(denom) < 1e-12:
        return (0.0, 0.0, y1)
    a = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom
    b = (x3 * x3 * (y1 - y2) + x2 * x2 * (y3 - y1) + x1 * x1 * (y2 - y3)) / denom
    c = (x2 * x3 * (x2 - x3) * y1 + x3 * x1 * (x3 - x1) * y2 + x1 * x2 * (x1 - x2) * y3) / denom
    return (a, b, c)
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
def _solve_quadratic_target(a: float, b: float, c: float, target_y: float, current_x: float) -> float:
    c_prime = c - target_y
    if abs(a) < 1e-09:
        if abs(b) > 1e-09:
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
@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model='numpy')
def check_extrema_proximity_batch(wls: np.ndarray, n_currents: np.ndarray, n_previouss: np.ndarray, n_Subs: np.ndarray, thickness_nominal: float, M_befores: np.ndarray, exclusion_width: float, check_start: bool, wl_changed_arr: np.ndarray) -> np.ndarray:
    """

    Parallel batch version of check_extrema_proximity.

    wl_changed_arr: boolean array (len = len(wls)).

        True  -> candidate wavelength differs from previous layer's -> asymmetric start check.

        False -> same wavelength, symmetric start check only.

    """
    n = len(wls)
    results = np.empty(n, dtype=np.bool_)
    for i in prange(n):
        results[i] = check_extrema_proximity(wls[i], n_currents[i], n_previouss[i], n_Subs[i], thickness_nominal, M_befores[i], exclusion_width, check_start, wl_changed_arr[i])
    return results
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
def _seeded_noise_sample(seed_base: int, group_idx: int, run_idx: int, elem_idx: int, gaussian: bool) -> np.float64:
    s = np.uint64(seed_base) + np.uint64(11400714819323198485) * np.uint64(group_idx + 1) + np.uint64(13787848793156543929) * np.uint64(run_idx + 1) + np.uint64(10723151780598845931) * np.uint64(elem_idx + 1)
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
        x = s + np.uint64(15183679468541472403) * np.uint64(k + 1)
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
@njit(cache=True, fastmath=True, nogil=True, error_model='numpy')
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
    return (H_ok, L_ok, Sub_ok)
