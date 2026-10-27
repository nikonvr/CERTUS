"""Bounded Gauss-Newton / Levenberg-Marquardt refinement on the residuals and their Jacobian (ALG-07)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit


@njit(cache=True, fastmath=False, nogil=True, error_model="numpy")
def _res_jac_lossless_normal_kernel(
    ep: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    has_back: bool,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    sqrt_norm_weights: np.ndarray,
    var_idx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Compute weighted residuals `r_m` and Jacobian `J_{m,i}` for normal-incidence Gauss-Newton polish (ALG-07)."""
    n_wls = len(k0_wls)
    n_layers = len(ep)
    n_vars = len(var_idx)

    res = np.zeros(n_wls, dtype=np.float64)
    jac = np.zeros((n_wls, n_vars), dtype=np.float64)
    M_before = np.empty((n_layers + 1, 4), dtype=np.float64)
    M_after = np.empty((n_layers + 1, 4), dtype=np.float64)
    cp_row = np.empty(n_layers, dtype=np.float64)
    sp_row = np.empty(n_layers, dtype=np.float64)
    cost = 0.0

    for i_wl in range(n_wls):
        sw = sqrt_norm_weights[i_wl]
        if sw <= 0.0:
            continue

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

        chain_scale = 1.0
        if has_back:
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
            T_val = (Tf * tb_i) / D_inc
            chain_scale = tb_i * (1.0 / D_inc - (Tf * rb_i) / (D_inc * D_inc))
        else:
            T_val = Tf

        r_m = sw * (T_val - tgt_vals[i_wl])
        res[i_wl] = r_m
        cost += r_m * r_m

        scale_m = sw * chain_scale
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

            jac[i_wl, i_var] = scale_m * dTf_dk

    return res, jac, cost


@njit(cache=True, fastmath=False, nogil=True, error_model="numpy")
def _cholesky_solve_lm(A: np.ndarray, b: np.ndarray, n: int) -> tuple[np.ndarray, bool]:
    """Pure-Numba SPD Cholesky solver `L L^T x = b`."""
    L = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1):
            s = A[i, j]
            for k in range(j):
                s -= L[i, k] * L[j, k]
            if i == j:
                if not (s > 1e-30):
                    return np.zeros(n, dtype=np.float64), False
                L[i, j] = np.sqrt(s)
            else:
                L[i, j] = s / L[j, j]
    y = np.empty(n, dtype=np.float64)
    for i in range(n):
        s = b[i]
        for k in range(i):
            s -= L[i, k] * y[k]
        y[i] = s / L[i, i]
    x = np.empty(n, dtype=np.float64)
    for i in range(n - 1, -1, -1):
        s = y[i]
        for k in range(i + 1, n):
            s -= L[k, i] * x[k]
        x[i] = s / L[i, i]
    return x, True


@njit(cache=True, fastmath=False, nogil=True, error_model="numpy")
def _gauss_newton_refine_lossless_kernel(
    ep_init: np.ndarray,
    n_layers_real: np.ndarray,
    inv_n_layers_real: np.ndarray,
    n_sub_real: np.ndarray,
    k0_wls: np.ndarray,
    has_back: bool,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    sqrt_norm_weights: np.ndarray,
    var_idx: np.ndarray,
    lower_bounds: np.ndarray,
    max_iter: int,
) -> tuple[np.ndarray, float]:
    """Box-constrained damped Gauss-Newton / Levenberg-Marquardt refinement in Numba (ALG-07)."""
    n_vars = len(var_idx)
    n_wls = len(k0_wls)
    ep = ep_init.copy()
    for iv in range(n_vars):
        k = var_idx[iv]
        if ep[k] < lower_bounds[iv]:
            ep[k] = lower_bounds[iv]

    res, jac, cost = _res_jac_lossless_normal_kernel(
        ep,
        n_layers_real,
        inv_n_layers_real,
        n_sub_real,
        k0_wls,
        has_back,
        rb_prime,
        tb,
        tgt_vals,
        sqrt_norm_weights,
        var_idx,
    )
    lam = 1e-5
    jtj = np.empty((n_vars, n_vars), dtype=np.float64)
    jtr = np.empty(n_vars, dtype=np.float64)
    neg_jtr = np.empty(n_vars, dtype=np.float64)
    A = np.empty((n_vars, n_vars), dtype=np.float64)

    for _ in range(max_iter):
        for i in range(n_vars):
            sr = 0.0
            for m in range(n_wls):
                sr += jac[m, i] * res[m]
            jtr[i] = sr
            for j in range(i, n_vars):
                sjj = 0.0
                for m in range(n_wls):
                    sjj += jac[m, i] * jac[m, j]
                jtj[i, j] = sjj
                jtj[j, i] = sjj

        gnorm = 0.0
        for i in range(n_vars):
            k = var_idx[i]
            if ep[k] <= lower_bounds[i] + 1e-12 and jtr[i] > 0.0:
                jtr[i] = 0.0
                for j in range(n_vars):
                    jtj[i, j] = 0.0
                    jtj[j, i] = 0.0
                jtj[i, i] = 1.0
            abs_g = abs(jtr[i])
            if abs_g > gnorm:
                gnorm = abs_g
            neg_jtr[i] = -jtr[i]

        if gnorm < 1e-14:
            break

        accepted = False
        for _sub in range(8):
            for i in range(n_vars):
                for j in range(n_vars):
                    A[i, j] = jtj[i, j]
                diag_i = A[i, i]
                if diag_i < 1e-12:
                    diag_i = 1e-12
                A[i, i] += lam * diag_i + 1e-15

            step, ok = _cholesky_solve_lm(A, neg_jtr, n_vars)
            if not ok:
                lam *= 10.0
                continue

            ep_cand = ep.copy()
            step_norm = 0.0
            for i in range(n_vars):
                k = var_idx[i]
                v = ep[k] + step[i]
                if v < lower_bounds[i]:
                    v = lower_bounds[i]
                diff = abs(v - ep[k])
                if diff > step_norm:
                    step_norm = diff
                ep_cand[k] = v

            if step_norm < 1e-12:
                accepted = False
                break

            res_cand, jac_cand, cost_cand = _res_jac_lossless_normal_kernel(
                ep_cand,
                n_layers_real,
                inv_n_layers_real,
                n_sub_real,
                k0_wls,
                has_back,
                rb_prime,
                tb,
                tgt_vals,
                sqrt_norm_weights,
                var_idx,
            )
            if cost_cand < cost:
                ep = ep_cand
                res = res_cand
                jac = jac_cand
                cost = cost_cand
                lam = max(lam * 0.3, 1e-14)
                accepted = True
                break
            lam *= 8.0
            if lam > 1e8:
                break

        if not accepted:
            break

    return ep, cost


def gauss_newton_refine_normal(
    ep: np.ndarray,
    *,
    ctx: dict[str, Any],
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    lower_bounds: np.ndarray,
    max_iter: int = 25,
) -> tuple[np.ndarray, float]:
    """Run damped Gauss-Newton / Levenberg-Marquardt refinement on a normal-incidence lossless stack."""
    ep_f64 = np.asarray(ep, dtype=np.float64).copy()
    var_idx_arr = np.asarray(var_idx, dtype=np.int64)
    lb_arr = np.asarray(lower_bounds, dtype=np.float64)
    tgt_vals_f64 = np.asarray(tgt_vals, dtype=np.float64)
    tgt_w_f64 = np.asarray(tgt_weights, dtype=np.float64)

    valid = (tgt_w_f64 > 0.0) & np.isfinite(tgt_vals_f64)
    w_sum = float(np.sum(tgt_w_f64[valid]))
    if int(np.sum(valid)) < 5 or w_sum <= 1e-18 or len(var_idx_arr) == 0:
        return ep_f64, 1e12

    sqrt_norm_w = np.zeros(len(tgt_w_f64), dtype=np.float64)
    sqrt_norm_w[valid] = np.sqrt(tgt_w_f64[valid] / w_sum)

    return _gauss_newton_refine_lossless_kernel(
        ep_f64,
        ctx["n_layers_real"],
        ctx["inv_n_layers_real"],
        ctx["n_sub_real"],
        ctx["k0_wls"],
        bool(ctx["has_back_calc"]),
        ctx["rb_prime"],
        ctx["tb"],
        tgt_vals_f64,
        sqrt_norm_w,
        var_idx_arr,
        lb_arr,
        int(max_iter),
    )
