"""Fast oblique-incidence DESIGN kernels (numba): precomputed optical terms (ALG-08)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numba import njit, prange

from certus.domain.constants import TWO_PI
from certus.physics.certus_inputs import check_incidence_angle
from certus.physics.certus_oblique_substrate import oblique_exit_admittance
from certus.physics.certus_opt_tmm import reflection_amplitude_derivatives, reflection_amplitudes
from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM, apply_plate_loss
from certus.physics.gradient_oblique import compute_oblique_rt_and_grads_analytic
from certus.physics.gradient_utils import SMALL_EPSILON, reduce_per_wavelength


def precompute_oblique_optical_terms(
    *,
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
    has_back_calc: bool = False,
    n_back_T: np.ndarray | None = None,
    d_back: np.ndarray | None = None,
    substrate_thickness_nm: float = DEFAULT_SUBSTRATE_THICKNESS_NM,
) -> dict[str, Any]:
    """Precompute Snell angles, optical admittances `eta`, phase rates `beta`, and backside `(rb_prime, tb)`."""
    angle_f = float(check_incidence_angle(angle_deg))
    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)
    n_layers_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)
    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)

    n_wls, n_layers = n_layers_c128.shape
    theta0 = np.deg2rad(angle_f)
    sin_theta0 = float(np.sin(theta0))
    cos_theta0 = float(np.cos(theta0))
    absorbing_sub = bool(np.any(n_sub_c128.imag != 0.0))

    beta_c128 = np.zeros((n_wls, n_layers), dtype=np.complex128)
    eta_c128 = np.zeros((n_wls, n_layers), dtype=np.complex128)
    inv_eta_c128 = np.zeros((n_wls, n_layers), dtype=np.complex128)
    eta_inc_arr = np.zeros(n_wls, dtype=np.float64)
    eta_sub_arr = np.zeros(n_wls, dtype=np.complex128)
    t_gain_arr = np.zeros(n_wls, dtype=np.float64)
    valid_wl = np.ones(n_wls, dtype=np.bool_)

    # Backside reverse exit/inc admittances (Sub -> Stack -> Air)
    eta_inc_rev_arr = np.zeros(n_wls, dtype=np.float64)
    eta_exit_rev_arr = np.zeros(n_wls, dtype=np.float64)
    t_gain_rev_arr = np.zeros(n_wls, dtype=np.float64)
    valid_rev_wl = np.ones(n_wls, dtype=np.bool_)

    for i_wl in range(n_wls):
        wl = wls_f64[i_wl]
        n_sub_real = float(n_sub_c128[i_wl].real)
        if absorbing_sub:
            eta_sub_val, exit_ok = oblique_exit_admittance(n_sub_c128[i_wl], sin_theta0, bool(is_s_pol))
            if (not exit_ok) or ((not is_s_pol) and abs(cos_theta0) < SMALL_EPSILON):
                valid_wl[i_wl] = False
            else:
                eta_inc_val = cos_theta0 if is_s_pol else 1.0 / cos_theta0
                eta_inc_arr[i_wl] = eta_inc_val
                eta_sub_arr[i_wl] = eta_sub_val
                t_gain_arr[i_wl] = float(eta_sub_val.real) / eta_inc_val
        else:
            sin_theta_sub = (1.0 / max(n_sub_real, SMALL_EPSILON)) * sin_theta0
            if sin_theta_sub > 1.0:
                valid_wl[i_wl] = False
            else:
                cos_theta_sub = float(np.sqrt(1.0 - sin_theta_sub * sin_theta_sub))
                if is_s_pol:
                    eta_inc_val = cos_theta0
                    eta_sub_r = n_sub_real * cos_theta_sub
                else:
                    if abs(cos_theta0) < SMALL_EPSILON or abs(cos_theta_sub) < SMALL_EPSILON:
                        valid_wl[i_wl] = False
                        eta_inc_val = 1.0
                        eta_sub_r = 1.0
                    else:
                        eta_inc_val = 1.0 / cos_theta0
                        eta_sub_r = n_sub_real / cos_theta_sub
                eta_inc_arr[i_wl] = eta_inc_val
                eta_sub_arr[i_wl] = complex(eta_sub_r, 0.0)
                t_gain_arr[i_wl] = eta_sub_r / eta_inc_val

        # Reverse boundary admittances (Sub -> Stack -> Air)
        if n_sub_real < 1e-12:
            valid_rev_wl[i_wl] = False
        else:
            sin_inc_r = sin_theta0 / max(n_sub_real, SMALL_EPSILON)
            sin_exit_r = sin_theta0
            if sin_inc_r > 1.0 or sin_exit_r > 1.0:
                valid_rev_wl[i_wl] = False
            else:
                cos_inc_r = float(np.sqrt(max(0.0, 1.0 - sin_inc_r * sin_inc_r)))
                cos_exit_r = float(np.sqrt(max(0.0, 1.0 - sin_exit_r * sin_exit_r)))
                if is_s_pol:
                    e_inc_r = n_sub_real * cos_inc_r
                    e_exit_r = cos_exit_r
                else:
                    if abs(cos_inc_r) < SMALL_EPSILON or abs(cos_exit_r) < SMALL_EPSILON:
                        valid_rev_wl[i_wl] = False
                        e_inc_r = 1.0
                        e_exit_r = 1.0
                    else:
                        e_inc_r = n_sub_real / cos_inc_r
                        e_exit_r = 1.0 / cos_exit_r
                eta_inc_rev_arr[i_wl] = e_inc_r
                eta_exit_rev_arr[i_wl] = e_exit_r
                t_gain_rev_arr[i_wl] = e_exit_r / e_inc_r

        k0 = TWO_PI / max(wl, SMALL_EPSILON)
        for k in range(n_layers):
            n_layer = n_layers_c128[i_wl, k]
            if abs(n_layer) < SMALL_EPSILON:
                valid_wl[i_wl] = False
                valid_rev_wl[i_wl] = False
                break
            sin_l = sin_theta0 / n_layer
            cos_l = np.sqrt(1.0 - sin_l * sin_l)
            if is_s_pol:
                eta_l = n_layer * cos_l
            else:
                if abs(cos_l) < SMALL_EPSILON:
                    valid_wl[i_wl] = False
                    valid_rev_wl[i_wl] = False
                    break
                eta_l = n_layer / cos_l
            if abs(eta_l) < SMALL_EPSILON:
                valid_wl[i_wl] = False
                valid_rev_wl[i_wl] = False
                break
            beta_c128[i_wl, k] = k0 * n_layer * cos_l
            eta_c128[i_wl, k] = eta_l
            inv_eta_c128[i_wl, k] = 1.0 / eta_l

    rb_prime = np.zeros(n_wls, dtype=np.float64)
    tb = np.ones(n_wls, dtype=np.float64)
    if has_back_calc:
        if n_back_T is not None and d_back is not None and np.asarray(d_back).size > 0:
            n_back_c128 = np.asarray(n_back_T, dtype=np.complex128)
            d_back_f64 = np.asarray(d_back, dtype=np.float64)
            rb_p, tb_p, _, _ = compute_oblique_rt_and_grads_analytic(
                d_back_f64,
                n_back_c128,
                n_sub_c128,
                wls_f64,
                np.zeros(0, dtype=np.int64),
                angle_f,
                bool(is_s_pol),
                True,
            )
        else:
            rb_p, tb_p, _, _ = compute_oblique_rt_and_grads_analytic(
                np.zeros(0, dtype=np.float64),
                np.zeros((n_wls, 0), dtype=np.complex128),
                n_sub_c128,
                wls_f64,
                np.zeros(0, dtype=np.int64),
                angle_f,
                bool(is_s_pol),
                True,
            )
        rb_p, tb_p = apply_plate_loss(rb_p, tb_p, n_sub_c128, wls_f64, angle_f, substrate_thickness_nm)
        rb_prime = np.ascontiguousarray(rb_p, dtype=np.float64)
        tb = np.ascontiguousarray(tb_p, dtype=np.float64)

    return {
        "wls": wls_f64,
        "angle_deg": angle_f,
        "is_s_pol": bool(is_s_pol),
        "beta_c128": beta_c128,
        "eta_c128": eta_c128,
        "inv_eta_c128": inv_eta_c128,
        "eta_inc": eta_inc_arr,
        "eta_sub": eta_sub_arr,
        "t_gain": t_gain_arr,
        "valid_wl": valid_wl,
        "eta_inc_rev": eta_inc_rev_arr,
        "eta_exit_rev": eta_exit_rev_arr,
        "t_gain_rev": t_gain_rev_arr,
        "valid_rev_wl": valid_rev_wl,
        "rb_prime": rb_prime,
        "tb": tb,
    }


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _oblique_gradient_contrib_precomputed_kernel(
    ep: np.ndarray,
    beta_c128: np.ndarray,
    eta_c128: np.ndarray,
    inv_eta_c128: np.ndarray,
    eta_inc_arr: np.ndarray,
    eta_sub_arr: np.ndarray,
    t_gain_arr: np.ndarray,
    valid_wl: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    target_is_reflectance: bool,
) -> tuple[float, np.ndarray, float]:
    """Precomputed oblique front-only analytic gradient contribution kernel (ALG-08)."""
    n_wls = len(tgt_vals)
    n_layers = len(ep)
    n_vars = len(var_idx)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)
    err_per_wl = np.zeros(n_wls, dtype=np.float64)
    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    prefix_buf = np.zeros((n_wls, n_layers + 1, 4), dtype=np.complex128)
    suffix_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    L_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    sp_buf = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        if w <= 1e-12:
            continue

        if not valid_wl[i_wl]:
            y_val = 1.0 if target_is_reflectance else 0.0
            diff = y_val - tgt_vals[i_wl]
            err_per_wl[i_wl] = w * diff * diff
            weight_per_wl[i_wl] = w
            continue

        prefix = prefix_buf[i_wl]
        suffix = suffix_buf[i_wl]
        L_store = L_buf[i_wl]
        sp_row = sp_buf[i_wl]

        prefix[0, 0] = 1.0 + 0.0j
        prefix[0, 1] = 0.0 + 0.0j
        prefix[0, 2] = 0.0 + 0.0j
        prefix[0, 3] = 1.0 + 0.0j

        for k in range(n_layers):
            beta = beta_c128[i_wl, k]
            eta_layer = eta_c128[i_wl, k]
            inv_eta = inv_eta_c128[i_wl, k]
            phi = beta * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            sp_row[k] = sp
            l01 = 1j * sp * inv_eta
            l10 = 1j * eta_layer * sp

            L_store[k, 0] = cp
            L_store[k, 1] = l01
            L_store[k, 2] = l10
            L_store[k, 3] = cp

            p00 = prefix[k, 0]
            p01 = prefix[k, 1]
            p10 = prefix[k, 2]
            p11 = prefix[k, 3]

            prefix[k + 1, 0] = cp * p00 + l01 * p10
            prefix[k + 1, 1] = cp * p01 + l01 * p11
            prefix[k + 1, 2] = l10 * p00 + cp * p10
            prefix[k + 1, 3] = l10 * p01 + cp * p11

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
                l00 = L_store[k + 1, 0]
                l01 = L_store[k + 1, 1]
                l10 = L_store[k + 1, 2]
                l11 = L_store[k + 1, 3]
                suffix[k, 0] = s00 * l00 + s01 * l10
                suffix[k, 1] = s00 * l01 + s01 * l11
                suffix[k, 2] = s10 * l00 + s11 * l10
                suffix[k, 3] = s10 * l01 + s11 * l11

        eta_inc = eta_inc_arr[i_wl]
        eta_sub = eta_sub_arr[i_wl]
        t_gain = t_gain_arr[i_wl]

        m00 = prefix[n_layers, 0]
        m01 = prefix[n_layers, 1]
        m10 = prefix[n_layers, 2]
        m11 = prefix[n_layers, 3]

        denom, r, t = reflection_amplitudes(eta_inc, m00 + m01 * eta_sub, m10 + m11 * eta_sub)
        den_mag_sq = (denom.real * denom.real) + (denom.imag * denom.imag)

        if den_mag_sq < SMALL_EPSILON:
            y_val = 1.0 if target_is_reflectance else 0.0
            diff = y_val - tgt_vals[i_wl]
            err_per_wl[i_wl] = w * diff * diff
            weight_per_wl[i_wl] = w
            continue

        R_unclipped = (r * r.conjugate()).real
        T_unclipped = t_gain * (t * t.conjugate()).real
        R_val = max(0.0, min(1.0, R_unclipped))
        T_val = max(0.0, min(1.0, T_unclipped))

        y_val = R_val if target_is_reflectance else T_val
        diff = y_val - tgt_vals[i_wl]
        err_per_wl[i_wl] = w * diff * diff
        weight_per_wl[i_wl] = w

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
            s00 = suffix[k, 0]
            s01 = suffix[k, 1]
            s10 = suffix[k, 2]
            s11 = suffix[k, 3]

            eta_layer = eta_c128[i_wl, k]
            inv_eta = inv_eta_c128[i_wl, k]
            beta = beta_c128[i_wl, k]
            cp = L_store[k, 0]
            sp = sp_row[k]

            dcp = -sp * beta
            dsp = cp * beta
            dl01 = 1j * dsp * inv_eta
            dl10 = 1j * eta_layer * dsp

            t00 = dcp * p00 + dl01 * p10
            t01 = dcp * p01 + dl01 * p11
            t10 = dl10 * p00 + dcp * p10
            t11 = dl10 * p01 + dcp * p11

            dm00 = s00 * t00 + s01 * t10
            dm01 = s00 * t01 + s01 * t11
            dm10 = s10 * t00 + s11 * t10
            dm11 = s10 * t01 + s11 * t11

            dr, dt = reflection_amplitude_derivatives(
                eta_inc, dm00 + dm01 * eta_sub, dm10 + dm11 * eta_sub, denom, r, t
            )
            if target_is_reflectance:
                dy = 2.0 * (r.conjugate() * dr).real
            else:
                dy = t_gain * 2.0 * (t.conjugate() * dt).real

            grad_per_wl[i_wl, i_var] += w * diff * dy

    return reduce_per_wavelength(err_per_wl, weight_per_wl, grad_per_wl)


def compute_oblique_gradient_contrib_precomputed(
    ep: np.ndarray,
    pre: dict[str, Any],
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    target_is_reflectance: bool,
    var_idx: np.ndarray | None = None,
) -> tuple[float, np.ndarray, float]:
    """Wrapper for `_oblique_gradient_contrib_precomputed_kernel`."""
    ep_f64 = np.asarray(ep, dtype=np.float64)
    var_idx_arr = np.arange(len(ep_f64), dtype=np.int64) if var_idx is None else np.asarray(var_idx, dtype=np.int64)
    return _oblique_gradient_contrib_precomputed_kernel(
        ep_f64,
        pre["beta_c128"],
        pre["eta_c128"],
        pre["inv_eta_c128"],
        pre["eta_inc"],
        pre["eta_sub"],
        pre["t_gain"],
        pre["valid_wl"],
        np.asarray(tgt_vals, dtype=np.float64),
        np.asarray(tgt_weights, dtype=np.float64),
        var_idx_arr,
        bool(target_is_reflectance),
    )


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _oblique_backside_contrib_precomputed_kernel(
    ep: np.ndarray,
    beta_c128: np.ndarray,
    eta_c128: np.ndarray,
    inv_eta_c128: np.ndarray,
    eta_inc_arr: np.ndarray,
    eta_sub_arr: np.ndarray,
    t_gain_arr: np.ndarray,
    valid_wl: np.ndarray,
    eta_inc_rev_arr: np.ndarray,
    eta_exit_rev_arr: np.ndarray,
    t_gain_rev_arr: np.ndarray,
    valid_rev_wl: np.ndarray,
    rb_prime: np.ndarray,
    tb: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
    target_is_reflectance: bool,
) -> tuple[float, np.ndarray, float]:
    """Single-pass oblique backside cost and gradient kernel using transpose symmetry `M_rev[0,0]=M_fwd[1,1]`."""
    n_wls = len(tgt_vals)
    n_layers = len(ep)
    n_vars = len(var_idx)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)
    err_per_wl = np.zeros(n_wls, dtype=np.float64)
    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    prefix_buf = np.zeros((n_wls, n_layers + 1, 4), dtype=np.complex128)
    suffix_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    L_buf = np.zeros((n_wls, n_layers, 4), dtype=np.complex128)
    sp_buf = np.zeros((n_wls, n_layers), dtype=np.complex128)

    for i_wl in prange(n_wls):
        w = tgt_weights[i_wl]
        if w <= 1e-12:
            continue

        prefix = prefix_buf[i_wl]
        suffix = suffix_buf[i_wl]
        L_store = L_buf[i_wl]
        sp_row = sp_buf[i_wl]

        prefix[0, 0] = 1.0 + 0.0j
        prefix[0, 1] = 0.0 + 0.0j
        prefix[0, 2] = 0.0 + 0.0j
        prefix[0, 3] = 1.0 + 0.0j

        for k in range(n_layers):
            beta = beta_c128[i_wl, k]
            eta_layer = eta_c128[i_wl, k]
            inv_eta = inv_eta_c128[i_wl, k]
            phi = beta * ep[k]
            cp = np.cos(phi)
            sp = np.sin(phi)
            sp_row[k] = sp
            l01 = 1j * sp * inv_eta
            l10 = 1j * eta_layer * sp

            L_store[k, 0] = cp
            L_store[k, 1] = l01
            L_store[k, 2] = l10
            L_store[k, 3] = cp

            p00 = prefix[k, 0]
            p01 = prefix[k, 1]
            p10 = prefix[k, 2]
            p11 = prefix[k, 3]

            prefix[k + 1, 0] = cp * p00 + l01 * p10
            prefix[k + 1, 1] = cp * p01 + l01 * p11
            prefix[k + 1, 2] = l10 * p00 + cp * p10
            prefix[k + 1, 3] = l10 * p01 + cp * p11

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

        # Forward (Air -> Stack -> Sub)
        Rf = 1.0
        Tf = 0.0
        fwd_ok = False
        eta_inc_f = eta_inc_arr[i_wl]
        eta_sub_f = eta_sub_arr[i_wl]
        t_gain_f = t_gain_arr[i_wl]
        D_f = 1.0 + 0.0j
        r_f = 0.0 + 0.0j
        t_f = 0.0 + 0.0j
        if valid_wl[i_wl]:
            D_f, r_f, t_f = reflection_amplitudes(eta_inc_f, m00 + m01 * eta_sub_f, m10 + m11 * eta_sub_f)
            if (D_f.real * D_f.real + D_f.imag * D_f.imag) >= SMALL_EPSILON:
                fwd_ok = True
                Rf = max(0.0, min(1.0, (r_f * r_f.conjugate()).real))
                Tf = max(0.0, min(1.0, t_gain_f * (t_f * t_f.conjugate()).real))

        # Reverse (Sub -> Stack -> Air): M_rev = [[m11, m01], [m10, m00]]
        Rf_prime = 1.0
        T_front_rev = 0.0
        rev_ok = False
        eta_inc_r = eta_inc_rev_arr[i_wl]
        eta_exit_r = eta_exit_rev_arr[i_wl]
        t_gain_r = t_gain_rev_arr[i_wl]
        D_r = 1.0 + 0.0j
        r_r = 0.0 + 0.0j
        t_r = 0.0 + 0.0j
        if valid_rev_wl[i_wl]:
            D_r, r_r, t_r = reflection_amplitudes(eta_inc_r, m11 + m01 * eta_exit_r, m10 + m00 * eta_exit_r)
            if (D_r.real * D_r.real + D_r.imag * D_r.imag) >= SMALL_EPSILON:
                rev_ok = True
                Rf_prime = max(0.0, min(1.0, (r_r * r_r.conjugate()).real))
                T_front_rev = max(0.0, min(1.0, t_gain_r * (t_r * t_r.conjugate()).real))

        rb_i = rb_prime[i_wl]
        tb_i = tb[i_wl]
        D_inc = max(1.0 - Rf_prime * rb_i, 1e-12)
        D_inc2 = D_inc * D_inc

        if target_is_reflectance:
            y_val = Rf + (Tf * T_front_rev * rb_i) / D_inc
        else:
            y_val = (Tf * tb_i) / D_inc

        diff = y_val - tgt_vals[i_wl]
        err_per_wl[i_wl] = w * diff * diff
        weight_per_wl[i_wl] = w

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

            eta_layer = eta_c128[i_wl, k]
            inv_eta = inv_eta_c128[i_wl, k]
            beta = beta_c128[i_wl, k]
            cp = L_store[k, 0]
            sp = sp_row[k]

            dcp = -sp * beta
            dsp = cp * beta
            dl01 = 1j * dsp * inv_eta
            dl10 = 1j * eta_layer * dsp

            t00 = dcp * p00 + dl01 * p10
            t01 = dcp * p01 + dl01 * p11
            t10 = dl10 * p00 + dcp * p10
            t11 = dl10 * p01 + dcp * p11

            dm00 = s00 * t00 + s01 * t10
            dm01 = s00 * t01 + s01 * t11
            dm10 = s10 * t00 + s11 * t10
            dm11 = s10 * t01 + s11 * t11

            dRf_k = 0.0
            dTf_k = 0.0
            if fwd_ok:
                dr_f, dt_f = reflection_amplitude_derivatives(
                    eta_inc_f, dm00 + dm01 * eta_sub_f, dm10 + dm11 * eta_sub_f, D_f, r_f, t_f
                )
                dRf_k = 2.0 * (r_f.conjugate() * dr_f).real
                dTf_k = t_gain_f * 2.0 * (t_f.conjugate() * dt_f).real

            dRf_p_k = 0.0
            dTf_rev_k = 0.0
            if rev_ok:
                # Transpose symmetry of M_rev = [[m11, m01], [m10, m00]]
                dr_r, dt_r = reflection_amplitude_derivatives(
                    eta_inc_r, dm11 + dm01 * eta_exit_r, dm10 + dm00 * eta_exit_r, D_r, r_r, t_r
                )
                dRf_p_k = 2.0 * (r_r.conjugate() * dr_r).real
                dTf_rev_k = t_gain_r * 2.0 * (t_r.conjugate() * dt_r).real

            if target_is_reflectance:
                dy = dRf_k + (
                    (rb_i * (dTf_k * T_front_rev + Tf * dTf_rev_k)) / D_inc
                    + ((Tf * T_front_rev * (rb_i * rb_i)) * dRf_p_k / D_inc2)
                )
            else:
                dy = tb_i * (dTf_k / D_inc + (Tf * rb_i * dRf_p_k) / D_inc2)

            grad_per_wl[i_wl, iv] += w * diff * dy

    err_sum, grad_raw, weight_sum = reduce_per_wavelength(err_per_wl, weight_per_wl, grad_per_wl)

    return err_sum, grad_raw, weight_sum


def compute_oblique_backside_contrib_precomputed(
    ep: np.ndarray,
    pre: dict[str, Any],
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    target_is_reflectance: bool,
    var_idx: np.ndarray | None = None,
) -> tuple[float, np.ndarray, float]:
    """Wrapper for `_oblique_backside_contrib_precomputed_kernel`."""
    ep_f64 = np.asarray(ep, dtype=np.float64)
    var_idx_arr = np.arange(len(ep_f64), dtype=np.int64) if var_idx is None else np.asarray(var_idx, dtype=np.int64)
    return _oblique_backside_contrib_precomputed_kernel(
        ep_f64,
        pre["beta_c128"],
        pre["eta_c128"],
        pre["inv_eta_c128"],
        pre["eta_inc"],
        pre["eta_sub"],
        pre["t_gain"],
        pre["valid_wl"],
        pre["eta_inc_rev"],
        pre["eta_exit_rev"],
        pre["t_gain_rev"],
        pre["valid_rev_wl"],
        pre["rb_prime"],
        pre["tb"],
        np.asarray(tgt_vals, dtype=np.float64),
        np.asarray(tgt_weights, dtype=np.float64),
        var_idx_arr,
        bool(target_is_reflectance),
    )
