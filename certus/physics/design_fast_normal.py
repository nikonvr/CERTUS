"""Fast normal-incidence DESIGN kernels (numba): real `float64` path, cached backside (ALG-25, ALG-30)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit, prange

import certus.physics.certus_tmm_core as tmm_core
from certus.domain.constants import TWO_PI
from certus.physics.certus_opt_tmm import reflection_amplitude_derivatives, reflection_amplitudes
from certus.physics.gradient_utils import FASTMATH_SAFE, SMALL_EPSILON, compute_mse_vectorized


@njit(cache=True, fastmath=FASTMATH_SAFE, parallel=True, nogil=True, error_model="numpy")
def cost_lossless_front_fast(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
) -> float:
    """Fast front-only MSE cost for lossless/real-approximated dielectric stacks in normal incidence."""
    n_wls = len(k0_wls)
    n_layers = len(ep)
    sum_sq = 0.0
    sum_w = 0.0
    count = 0

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        t_tgt = tgt_vals[i_wl]
        if w <= 0.0 or not np.isfinite(t_tgt):
            continue

        k0 = k0_wls[i_wl]
        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers):
            nr = n_layers_real[i_wl, k]
            phi = k0 * nr * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr
            NAr = Ar * cp + Bi * m10i
            NBi = -Ar * m01i + Bi * cp
            NCi = Ci * cp - Dr * m10i
            NDr = Ci * m01i + Dr * cp
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        ns_r = n_sub_real[i_wl]
        dr = ns_r * Ar + Dr
        di = ns_r * Bi + Ci
        denom = dr * dr + di * di
        if denom < 1e-30:
            denom = 1e-30
        inv_den = 1.0 / denom
        tr = 2.0 * dr * inv_den
        ti = -2.0 * di * inv_den
        T_val = ns_r * (tr * tr + ti * ti)

        if np.isfinite(T_val):
            diff = T_val - t_tgt
            sum_sq += diff * diff * w
            sum_w += w
            count += 1

    if count < 5 or sum_w <= 1e-18:
        return 1e12
    return sum_sq / sum_w


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_gradient_lossless_front_kernel(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Analytic cost and gradient kernel for lossless/real-approximated normal-incidence stacks."""
    n_wls = len(k0_wls)
    n_layers = len(ep)
    n_vars = len(var_idx)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)
    err_per_wl = np.zeros(n_wls, dtype=np.float64)
    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    M_before_buf = np.empty((n_wls, n_layers + 1, 4), dtype=np.float64)
    M_after_buf = np.empty((n_wls, n_layers + 1, 4), dtype=np.float64)
    cp_buf = np.empty((n_wls, n_layers), dtype=np.float64)
    sp_buf = np.empty((n_wls, n_layers), dtype=np.float64)

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        if w <= 1e-12:
            continue

        M_before = M_before_buf[i_wl]
        M_after = M_after_buf[i_wl]
        cp_row = cp_buf[i_wl]
        sp_row = sp_buf[i_wl]

        k0 = k0_wls[i_wl]
        ns_r = n_sub_real[i_wl]

        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers):
            M_before[k + 1, 0] = Ar
            M_before[k + 1, 1] = Bi
            M_before[k + 1, 2] = Ci
            M_before[k + 1, 3] = Dr

            nr = n_layers_real[i_wl, k]
            phi = k0 * nr * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            cp_row[k] = cp
            sp_row[k] = sp

            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr

            NAr = Ar * cp + Bi * m10i
            NBi = -Ar * m01i + Bi * cp
            NCi = Ci * cp - Dr * m10i
            NDr = Ci * m01i + Dr * cp
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        M00r = Ar
        M01i = Bi
        M10i = Ci
        M11r = Dr

        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers - 1, -1, -1):
            M_after[k, 0] = Ar
            M_after[k, 1] = Bi
            M_after[k, 2] = Ci
            M_after[k, 3] = Dr

            nr = n_layers_real[i_wl, k]
            cp = cp_row[k]
            sp = sp_row[k]
            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr

            NAr = cp * Ar + m01i * Ci
            NBi = cp * Bi - m01i * Dr
            NCi = -m10i * Ar + cp * Ci
            NDr = m10i * Bi + cp * Dr
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        dr = ns_r * M00r + M11r
        di = ns_r * M01i + M10i
        denom = dr * dr + di * di
        if denom < 1e-30:
            denom = 1e-30
        inv_den = 1.0 / denom
        tr = 2.0 * dr * inv_den
        ti = -2.0 * di * inv_den
        T_val = ns_r * (tr * tr + ti * ti)

        diff = T_val - tgt_vals[i_wl]
        err_per_wl[i_wl] = diff * diff * w
        weight_per_wl[i_wl] = w

        for i_var in range(n_vars):
            k = var_idx[i_var]
            idx_b = k + 1
            Mb00r = M_before[idx_b, 0]
            Mb01i = M_before[idx_b, 1]
            Mb10i = M_before[idx_b, 2]
            Mb11r = M_before[idx_b, 3]

            Ma00r = M_after[k, 0]
            Ma01i = M_after[k, 1]
            Ma10i = M_after[k, 2]
            Ma11r = M_after[k, 3]

            nr = n_layers_real[i_wl, k]
            factor = k0 * nr
            cp = cp_row[k]
            sp = sp_row[k]

            dm00r = -factor * sp
            dm01i = -factor * cp * inv_n_layers_real[i_wl, k]
            dm10i = -factor * nr * cp

            t00r = Mb00r * dm00r - Mb01i * dm10i
            t01i = Mb00r * dm01i + Mb01i * dm00r
            t10i = Mb10i * dm00r + Mb11r * dm10i
            t11r = -Mb10i * dm01i + Mb11r * dm00r

            dM00r = t00r * Ma00r - t01i * Ma10i
            dM01i = t00r * Ma01i + t01i * Ma11r
            dM10i = t10i * Ma00r + t11r * Ma10i
            dM11r = -t10i * Ma01i + t11r * Ma11r

            ddr = ns_r * dM00r + dM11r
            ddi = ns_r * dM01i + dM10i
            d_denom = 2.0 * (dr * ddr + di * ddi)
            dtr = 2.0 * ddr * inv_den - tr * d_denom * inv_den
            dti = -2.0 * ddi * inv_den - ti * d_denom * inv_den
            dT_dk = ns_r * 2.0 * (tr * dtr + ti * dti)

            grad_per_wl[i_wl, i_var] = w * diff * dT_dk

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
        return 1e30, np.zeros(n_vars, dtype=np.float64)

    cost = err_sum / weight_sum
    grad *= 2.0 / weight_sum
    return cost, grad


def compute_gradient_lossless_front_fast(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    min_d: float = 0.0,
) -> tuple[float, np.ndarray]:
    """Wrapper adding the minimum-thickness penalty to `_compute_gradient_lossless_front_kernel`."""
    cost, grad = _compute_gradient_lossless_front_kernel(
        ep, n_layers_real, inv_n_layers_real, n_sub_real, k0_wls, tgt_vals, tgt_weights, var_idx
    )
    penalty = 0.0
    for i in range(len(ep)):
        if 1e-12 < ep[i] < min_d:
            diff = min_d - ep[i]
            penalty += diff * diff * 1e6
    return cost + penalty, grad


@njit(cache=True, fastmath=FASTMATH_SAFE, parallel=True, nogil=True, error_model="numpy")
def cost_lossless_backside_fast(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
) -> float:
    """Fast backside-corrected MSE cost for lossless/real-approximated front stacks (ALG-25)."""
    n_wls = len(k0_wls)
    n_layers = len(ep)
    sum_sq = 0.0
    sum_w = 0.0
    count = 0

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        t_tgt = tgt_vals[i_wl]
        if w <= 0.0 or not np.isfinite(t_tgt):
            continue

        k0 = k0_wls[i_wl]
        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers):
            nr = n_layers_real[i_wl, k]
            phi = k0 * nr * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr
            NAr = Ar * cp + Bi * m10i
            NBi = -Ar * m01i + Bi * cp
            NCi = Ci * cp - Dr * m10i
            NDr = Ci * m01i + Dr * cp
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        ns_r = n_sub_real[i_wl]
        dr = ns_r * Ar + Dr
        di = ns_r * Bi + Ci
        denom = dr * dr + di * di
        if denom < 1e-30:
            denom = 1e-30
        inv_den = 1.0 / denom
        tr = 2.0 * dr * inv_den
        ti = -2.0 * di * inv_den
        Tf = ns_r * (tr * tr + ti * ti)
        if Tf < 0.0:
            Tf = 0.0
        elif Tf > 1.0:
            Tf = 1.0
        Rf_prime = 1.0 - Tf

        d_val = 1.0 - Rf_prime * rb_prime[i_wl]
        if d_val < 1e-12:
            d_val = 1e-12
        T_tot = (Tf * tb[i_wl]) / d_val

        if np.isfinite(T_tot):
            diff = T_tot - t_tgt
            sum_sq += diff * diff * w
            sum_w += w
            count += 1

    if count < 5 or sum_w <= 1e-18:
        return 1e12
    return sum_sq / sum_w


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_gradient_lossless_backside_kernel(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Single-pass analytic cost and gradient kernel for lossless front stack with backside (ALG-25)."""
    n_wls = len(k0_wls)
    n_layers = len(ep)
    n_vars = len(var_idx)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)
    err_per_wl = np.zeros(n_wls, dtype=np.float64)
    weight_per_wl = np.zeros(n_wls, dtype=np.float64)
    valid_count = 0

    M_before_buf = np.empty((n_wls, n_layers + 1, 4), dtype=np.float64)
    M_after_buf = np.empty((n_wls, n_layers + 1, 4), dtype=np.float64)
    cp_buf = np.empty((n_wls, n_layers), dtype=np.float64)
    sp_buf = np.empty((n_wls, n_layers), dtype=np.float64)

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        t_tgt = tgt_vals[i_wl]
        if w <= 0.0 or not np.isfinite(t_tgt):
            continue

        M_before = M_before_buf[i_wl]
        M_after = M_after_buf[i_wl]
        cp_row = cp_buf[i_wl]
        sp_row = sp_buf[i_wl]

        k0 = k0_wls[i_wl]
        ns_r = n_sub_real[i_wl]

        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers):
            M_before[k + 1, 0] = Ar
            M_before[k + 1, 1] = Bi
            M_before[k + 1, 2] = Ci
            M_before[k + 1, 3] = Dr

            nr = n_layers_real[i_wl, k]
            phi = k0 * nr * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            cp_row[k] = cp
            sp_row[k] = sp

            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr

            NAr = Ar * cp + Bi * m10i
            NBi = -Ar * m01i + Bi * cp
            NCi = Ci * cp - Dr * m10i
            NDr = Ci * m01i + Dr * cp
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        M00r = Ar
        M01i = Bi
        M10i = Ci
        M11r = Dr

        Ar = 1.0
        Bi = 0.0
        Ci = 0.0
        Dr = 1.0

        for k in range(n_layers - 1, -1, -1):
            M_after[k, 0] = Ar
            M_after[k, 1] = Bi
            M_after[k, 2] = Ci
            M_after[k, 3] = Dr

            nr = n_layers_real[i_wl, k]
            cp = cp_row[k]
            sp = sp_row[k]
            m01i = sp * inv_n_layers_real[i_wl, k]
            m10i = sp * nr

            NAr = cp * Ar + m01i * Ci
            NBi = cp * Bi - m01i * Dr
            NCi = -m10i * Ar + cp * Ci
            NDr = m10i * Bi + cp * Dr
            Ar, Bi, Ci, Dr = NAr, NBi, NCi, NDr

        dr = ns_r * M00r + M11r
        di = ns_r * M01i + M10i
        denom = dr * dr + di * di
        if denom < 1e-30:
            denom = 1e-30
        inv_den = 1.0 / denom
        tr = 2.0 * dr * inv_den
        ti = -2.0 * di * inv_den
        Tf = ns_r * (tr * tr + ti * ti)
        if Tf < 0.0:
            Tf = 0.0
        elif Tf > 1.0:
            Tf = 1.0
        Rf_prime = 1.0 - Tf

        rb_i = rb_prime[i_wl]
        tb_i = tb[i_wl]
        D_inc = 1.0 - Rf_prime * rb_i
        if D_inc < 1e-12:
            D_inc = 1e-12
        T_tot = (Tf * tb_i) / D_inc

        diff = T_tot - t_tgt
        err_per_wl[i_wl] = diff * diff * w
        weight_per_wl[i_wl] = w
        valid_count += 1

        # Chain rule: dT_tot / dTf = tb * (1 / D_inc - Tf * rb / D_inc^2) since dRf_prime = -dTf
        chain_scale = tb_i * (1.0 / D_inc - (Tf * rb_i) / (D_inc * D_inc))

        for i_var in range(n_vars):
            k = var_idx[i_var]
            idx_b = k + 1
            Mb00r = M_before[idx_b, 0]
            Mb01i = M_before[idx_b, 1]
            Mb10i = M_before[idx_b, 2]
            Mb11r = M_before[idx_b, 3]

            Ma00r = M_after[k, 0]
            Ma01i = M_after[k, 1]
            Ma10i = M_after[k, 2]
            Ma11r = M_after[k, 3]

            nr = n_layers_real[i_wl, k]
            factor = k0 * nr
            cp = cp_row[k]
            sp = sp_row[k]

            dm00r = -factor * sp
            dm01i = -factor * cp * inv_n_layers_real[i_wl, k]
            dm10i = -factor * nr * cp

            t00r = Mb00r * dm00r - Mb01i * dm10i
            t01i = Mb00r * dm01i + Mb01i * dm00r
            t10i = Mb10i * dm00r + Mb11r * dm10i
            t11r = -Mb10i * dm01i + Mb11r * dm00r

            dM00r = t00r * Ma00r - t01i * Ma10i
            dM01i = t00r * Ma01i + t01i * Ma11r
            dM10i = t10i * Ma00r + t11r * Ma10i
            dM11r = -t10i * Ma01i + t11r * Ma11r

            ddr = ns_r * dM00r + dM11r
            ddi = ns_r * dM01i + dM10i
            d_denom = 2.0 * (dr * ddr + di * ddi)
            dtr = 2.0 * ddr * inv_den - tr * d_denom * inv_den
            dti = -2.0 * ddi * inv_den - ti * d_denom * inv_den
            dTf_dk = ns_r * 2.0 * (tr * dtr + ti * dti)

            grad_per_wl[i_wl, i_var] = w * diff * (chain_scale * dTf_dk)

    err_sum = 0.0
    weight_sum = 0.0
    for i in range(n_wls):
        err_sum += err_per_wl[i]
        weight_sum += weight_per_wl[i]

    if valid_count < 5 or weight_sum <= 1e-18:
        return 1e12, np.zeros(n_vars, dtype=np.float64)

    grad = np.zeros(n_vars, dtype=np.float64)
    for v in range(n_vars):
        s = 0.0
        for i in range(n_wls):
            s += grad_per_wl[i, v]
        grad[v] = s

    cost = err_sum / weight_sum
    grad *= 2.0 / weight_sum
    return cost, grad


def compute_gradient_lossless_backside_fast(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    min_d: float = 0.0,
) -> tuple[float, np.ndarray]:
    """Wrapper adding minimum-thickness penalty and gradient to `_compute_gradient_lossless_backside_kernel`."""
    ep_f64 = np.asarray(ep, dtype=np.float64)
    var_idx_arr = np.asarray(var_idx, dtype=np.int64)
    mse, grad = _compute_gradient_lossless_backside_kernel(
        ep_f64, n_layers_real, inv_n_layers_real, n_sub_real, k0_wls, rb_prime, tb, tgt_vals, tgt_weights, var_idx_arr
    )
    if mse >= 1e12:
        return mse, grad

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


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _normal_front_and_reverse_rt_grads_single_pass_kernel(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    var_idx: np.ndarray,
    absorbing_substrate: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute both forward `(Tf, dTf)` and reverse `(Rf_prime, dRf_prime)` in a single TMM pass at 0 deg.

    Uses the exact characteristic matrix transpose symmetry `M_rev = [[M11, M01], [M10, M00]]` and
    `dM_rev = [[dM11, dM01], [dM10, dM00]]`, cutting work in half compared to calling the oblique kernel twice.
    """
    n_wls = len(wls)
    n_layers = len(ep)
    n_vars = len(var_idx)

    Tf_arr = np.empty(n_wls, dtype=np.float64)
    Rf_prime_arr = np.empty(n_wls, dtype=np.float64)
    dTf = np.zeros((n_wls, n_vars), dtype=np.float64)
    dRf_prime = np.zeros((n_wls, n_vars), dtype=np.float64)

    prefix_buf = np.zeros((n_wls, n_layers + 1, 4), dtype=np.complex128)
    suffix_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    Lm_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    beta_buf = np.zeros((n_wls, n_layers), dtype=np.complex128)
    eta_buf = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i_wl in prange(n_wls):
        wl = wls[i_wl]
        n_sub_real = n_sub[i_wl].real
        if n_sub_real < 1e-12:
            Tf_arr[i_wl] = 0.0
            Rf_prime_arr[i_wl] = 1.0
            continue

        prefix = prefix_buf[i_wl]
        suffix = suffix_buf[i_wl]
        Lm = Lm_buf[i_wl]
        beta = beta_buf[i_wl]
        eta = eta_buf[i_wl]

        prefix[0, 0] = 1.0 + 0.0j
        prefix[0, 1] = 0.0 + 0.0j
        prefix[0, 2] = 0.0 + 0.0j
        prefix[0, 3] = 1.0 + 0.0j

        valid = True
        k0 = TWO_PI / max(wl, SMALL_EPSILON)

        for j in range(n_layers):
            n_layer = n_layers_T[i_wl, j]
            if abs(n_layer) < SMALL_EPSILON:
                valid = False
                break
            beta_j = k0 * n_layer
            phi = beta_j * ep[j]
            cp = np.cos(phi)
            sp = np.sin(phi)
            l01 = 1j * sp / n_layer
            l10 = 1j * n_layer * sp

            Lm[j, 0] = cp
            Lm[j, 1] = l01
            Lm[j, 2] = l10
            Lm[j, 3] = cp
            beta[j] = beta_j
            eta[j] = n_layer

            p00 = prefix[j, 0]
            p01 = prefix[j, 1]
            p10 = prefix[j, 2]
            p11 = prefix[j, 3]

            prefix[j + 1, 0] = cp * p00 + l01 * p10
            prefix[j + 1, 1] = cp * p01 + l01 * p11
            prefix[j + 1, 2] = l10 * p00 + cp * p10
            prefix[j + 1, 3] = l10 * p01 + cp * p11

        if not valid:
            Tf_arr[i_wl] = 0.0
            Rf_prime_arr[i_wl] = 1.0
            continue

        if n_layers > 0:
            suffix[n_layers - 1, 0] = 1.0 + 0.0j
            suffix[n_layers - 1, 1] = 0.0 + 0.0j
            suffix[n_layers - 1, 2] = 0.0 + 0.0j
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

        m00 = prefix[n_layers, 0]
        m01 = prefix[n_layers, 1]
        m10 = prefix[n_layers, 2]
        m11 = prefix[n_layers, 3]

        # 1. Forward (Air -> Stack -> Sub): eta_inc = 1.0, eta_exit = n_sub (or n_sub.real)
        eta_exit_fwd = n_sub[i_wl] if absorbing_substrate else complex(n_sub_real, 0.0)
        t_gain_fwd = n_sub_real
        eta_air = complex(1.0, 0.0)
        eta_sub_rev = complex(n_sub_real, 0.0)
        D_f, _r_f, t_f = reflection_amplitudes(eta_air, m00 + m01 * eta_exit_fwd, m10 + m11 * eta_exit_fwd)
        D_f_mag2 = D_f.real * D_f.real + D_f.imag * D_f.imag

        # 2. Reverse (Sub -> Stack -> Air): M_rev = [[m11, m01], [m10, m00]], eta_inc = n_sub_real, eta_exit = 1.0
        D_r, r_rev, t_rev = reflection_amplitudes(eta_sub_rev, m11 + m01, m10 + m00)
        D_r_mag2 = D_r.real * D_r.real + D_r.imag * D_r.imag

        if D_f_mag2 < SMALL_EPSILON or D_r_mag2 < SMALL_EPSILON:
            Tf_arr[i_wl] = 0.0
            Rf_prime_arr[i_wl] = 1.0
            continue

        Tv = t_gain_fwd * (t_f * t_f.conjugate()).real
        if Tv < 0.0:
            Tv = 0.0
        elif Tv > 1.0:
            Tv = 1.0
        Tf_arr[i_wl] = Tv

        Rv_prime = (r_rev * r_rev.conjugate()).real
        if Rv_prime < 0.0:
            Rv_prime = 0.0
        elif Rv_prime > 1.0:
            Rv_prime = 1.0
        Rf_prime_arr[i_wl] = Rv_prime

        for iv in range(n_vars):
            k = var_idx[iv]
            if k < 0 or k >= n_layers:
                continue
            p00 = prefix[k, 0]
            p01 = prefix[k, 1]
            p10 = prefix[k, 2]
            p11 = prefix[k, 3]
            s00 = suffix[k, 0]
            s01 = suffix[k, 1]
            s10 = suffix[k, 2]
            s11 = suffix[k, 3]

            cp = Lm[k, 0]
            # l01 = i * sp / eta[k] => i * beta * cp / eta[k] for dl01, and dcp = -sp * beta = i * beta * l01 * eta[k]
            # Using exact phi = beta[k] * ep[k] sin/cos:
            sp = -1j * Lm[k, 1] * eta[k]
            dcp = -sp * beta[k]
            dsp = cp * beta[k]
            dl01 = 1j * dsp / eta[k]
            dl10 = 1j * eta[k] * dsp

            t00 = dcp * p00 + dl01 * p10
            t01 = dcp * p01 + dl01 * p11
            t10 = dl10 * p00 + dcp * p10
            t11 = dl10 * p01 + dcp * p11

            dm00 = s00 * t00 + s01 * t10
            dm01 = s00 * t01 + s01 * t11
            dm10 = s10 * t00 + s11 * t10
            dm11 = s10 * t01 + s11 * t11

            # Forward derivative dTf
            _dr_f, dt_f = reflection_amplitude_derivatives(
                eta_air, dm00 + dm01 * eta_exit_fwd, dm10 + dm11 * eta_exit_fwd, D_f, _r_f, t_f
            )
            dTf[i_wl, iv] = t_gain_fwd * 2.0 * (t_f.conjugate() * dt_f).real

            # Reverse derivative dRf_prime (using M_rev swap dm00 <-> dm11)
            dr_rev, _dt_rev = reflection_amplitude_derivatives(eta_sub_rev, dm11 + dm01, dm10 + dm00, D_r, r_rev, t_rev)
            dRf_prime[i_wl, iv] = 2.0 * (r_rev.conjugate() * dr_rev).real

    return Tf_arr, dTf, Rf_prime_arr, dRf_prime


def compute_gradient_backside_cached_fast(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    min_d: float = 0.0,
) -> tuple[float, np.ndarray]:
    """Single-pass normal-incidence backside cost and gradient with cached `(rb_prime, tb)` (ALG-25)."""
    ep_f64 = np.asarray(ep, dtype=np.float64)
    wls_f64 = np.asarray(wls, dtype=np.float64)
    tgt_vals_f64 = np.asarray(tgt_vals, dtype=np.float64)
    tgt_weights_f64 = np.asarray(tgt_weights, dtype=np.float64)
    n_layers_c128 = np.asarray(n_layers_T, dtype=np.complex128)
    n_sub_c128 = np.asarray(n_sub, dtype=np.complex128)
    var_idx_arr = np.asarray(var_idx, dtype=np.int64)

    absorbing_sub = bool(np.any(n_sub_c128.imag != 0.0))
    Tf, dTf, Rf_prime, dRf_prime = _normal_front_and_reverse_rt_grads_single_pass_kernel(
        ep_f64, n_layers_c128, n_sub_c128, wls_f64, var_idx_arr, absorbing_sub
    )

    D = np.maximum(1.0 - Rf_prime * rb_prime, 1e-12)
    D2 = D * D
    T_total = (Tf * tb) / D

    mse, count = compute_mse_vectorized(T_total, tgt_vals_f64, tgt_weights_f64)
    if count == 0:
        return 1e12, np.zeros(len(var_idx_arr), dtype=np.float64)

    dy = tb[:, None] * (dTf / D[:, None] + (Tf[:, None] * rb_prime[:, None] * dRf_prime) / D2[:, None])
    valid = (tgt_weights_f64 > 0.0) & np.isfinite(T_total) & np.isfinite(tgt_vals_f64)
    diff_w = (T_total - tgt_vals_f64) * tgt_weights_f64
    diff_w[~valid] = 0.0
    weight_sum = float(np.sum(tgt_weights_f64[valid]))
    grad = (2.0 / max(weight_sum, 1e-18)) * np.sum(diff_w[:, None] * dy, axis=0)

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


def prepare_normal_fast_context(
    *,
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    has_back_calc: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
    k_real_threshold: float = 1e-4,
) -> dict[str, Any]:
    """Precompute wavelength-dependent optical constants and backside arrays for normal-incidence optimization.

    During exhaustive global search (`k_real_threshold=1e-4`), stacks with weak extinction (`|k| <= 1e-4`) and
    non-absorbing substrate are routed through the pure-real `float64` kernels (`use_real_approx=True`), and
    switched back to exact complex arithmetic (`k_real_threshold=1e-14`) for final local refinement.
    """
    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)
    n_layers_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)
    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)
    d_back_f64 = np.ascontiguousarray(d_back, dtype=np.float64) if d_back is not None else np.zeros(0, dtype=np.float64)
    n_back_c128 = (
        np.ascontiguousarray(n_back_T, dtype=np.complex128)
        if n_back_T is not None and np.asarray(n_back_T).size > 0
        else np.zeros((len(wls_f64), 0), dtype=np.complex128)
    )

    max_k_layers = float(np.max(np.abs(n_layers_c128.imag))) if n_layers_c128.size > 0 else 0.0
    max_k_sub = float(np.max(np.abs(n_sub_c128.imag))) if n_sub_c128.size > 0 else 0.0

    is_strictly_lossless = bool(max_k_layers < 1e-14 and max_k_sub < 1e-14)
    use_real_approx = bool(max_k_layers <= k_real_threshold and max_k_sub < 1e-14)
    has_weak_k = bool(use_real_approx and not is_strictly_lossless)

    n_layers_real = np.ascontiguousarray(n_layers_c128.real, dtype=np.float64)
    inv_n_layers_real = np.ascontiguousarray(
        np.where(n_layers_real > 1e-14, 1.0 / np.maximum(n_layers_real, 1e-14), 0.0),
        dtype=np.float64,
    )
    n_sub_real = np.ascontiguousarray(n_sub_c128.real, dtype=np.float64)
    k0_wls = np.ascontiguousarray(TWO_PI / np.maximum(wls_f64, SMALL_EPSILON), dtype=np.float64)

    rb_prime = np.zeros(len(wls_f64), dtype=np.float64)
    tb = np.ones(len(wls_f64), dtype=np.float64)
    if has_back_calc:
        _rf0, _tf0, _rfp0, rb_p, tb_p = tmm_core.calc_spectrum_full_exact(
            wls_f64,
            np.zeros(0, dtype=np.float64),
            np.zeros((len(wls_f64), 0), dtype=np.complex128),
            d_back_f64,
            n_back_c128,
            n_sub_c128,
        )
        rb_prime = np.ascontiguousarray(rb_p, dtype=np.float64)
        tb = np.ascontiguousarray(tb_p, dtype=np.float64)

    return {
        "wls": wls_f64,
        "k0_wls": k0_wls,
        "n_layers_T": n_layers_c128,
        "n_sub": n_sub_c128,
        "n_layers_real": n_layers_real,
        "inv_n_layers_real": inv_n_layers_real,
        "n_sub_real": n_sub_real,
        "is_strictly_lossless": is_strictly_lossless,
        "use_real_approx": use_real_approx,
        "has_weak_k": has_weak_k,
        "is_lossless_front": use_real_approx,
        "has_back_calc": bool(has_back_calc),
        "has_back_with_stack": bool(has_back_calc and len(d_back_f64) > 0),
        "n_back_T": n_back_c128,
        "d_back": d_back_f64,
        "rb_prime": rb_prime,
        "tb": tb,
    }
