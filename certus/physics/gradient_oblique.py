"""
CERTUS Gradient Optimization - Oblique Gradients Module

Extracted from certus_opt_gradients.py for better modularity.
Contains gradient computation for oblique (non-normal) incidence angles.
"""

import numpy as np
from certus.physics.certus_oblique_substrate import oblique_exit_admittance
from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM, apply_plate_loss
from numba import njit, prange
import certus.physics.certus_tmm_core as tmm_core
from certus.core.certus_core import TWO_PI
from certus.physics.gradient_utils import compute_mse_vectorized, SMALL_EPSILON
from .gradient_analytic import _compute_gradient_analytic_kernel


def _pick_kernel(plain, absorbing, n_sub_c128):
    """The kernel that reads a substrate that absorbs anywhere in the band, else the one that always ran."""

    return absorbing if np.any(n_sub_c128.imag != 0.0) else plain

def _make_oblique_gradient_contrib_kernel(absorbing_substrate: bool):
    """Build the analytic oblique kernel of the front-only objective, for one kind of substrate.

    `absorbing_substrate` is a compile-time constant: Numba drops the branch it rules out BEFORE typing,
    so the kernel for a substrate without absorption is exactly the one that ran before the absorbing
    one existed (the same operations on the same types, bit for bit, which the C1 rule requires), and
    both come from one source. `n_sub` is read as complex (`n - ik`) in the absorbing kernel.
    """

    @njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
    def kernel(
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

            if absorbing_substrate:
                # An absorbing substrate: complex exit admittance, as in the spectrum kernel. The thickness
                # derivatives below depend on it only through `eta_sub`, which enters B and C.
                eta_sub, exit_ok = oblique_exit_admittance(n_sub[i_wl], sin_theta0, is_s_pol)

                if (not exit_ok) or ((not is_s_pol) and abs(cos_theta0) < SMALL_EPSILON):
                    y_val = 1.0 if target_is_reflectance else 0.0

                    diff = y_val - tgt_vals[i_wl]

                    err_per_wl[i_wl] = w * diff * diff

                    weight_per_wl[i_wl] = w

                    continue

                eta_inc = n0 * cos_theta0 if is_s_pol else n0 / cos_theta0

                # The flux that enters the substrate: the real part of its admittance.
                t_gain = eta_sub.real / eta_inc

            else:
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

                t_gain = eta_sub / eta_inc

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

            T_unclipped = t_gain * (t * t.conjugate()).real

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

                    dy = t_gain * 2.0 * (t.conjugate() * dt).real

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

    return kernel


_compute_oblique_gradient_contrib_kernel = _make_oblique_gradient_contrib_kernel(False)

_compute_oblique_gradient_contrib_kernel_absorbing = _make_oblique_gradient_contrib_kernel(True)

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

    # A substrate without absorption keeps the kernel that always ran; one that absorbs anywhere in the band
    # takes the kernel that reads its complex admittance.
    kernel = _pick_kernel(
        _compute_oblique_gradient_contrib_kernel, _compute_oblique_gradient_contrib_kernel_absorbing, n_sub_c128
    )

    return kernel(
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


def _make_oblique_rt_and_grads_kernel(absorbing_substrate: bool):
    """Build the oblique R/T + analytic dR, dT kernel, for one kind of substrate.

    Same device as `_make_oblique_gradient_contrib_kernel`: `absorbing_substrate` is a compile-time
    constant, the kernel for a substrate without absorption is the one that always ran (C1), and the
    absorbing one reads the complex exit admittance in the forward direction (air -> stack -> substrate).
    """

    @njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
    def kernel(
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

            if absorbing_substrate and (not reverse):
                # Air -> stack -> a substrate that absorbs: its admittance is complex (a complex angle) and
                # what enters it is `Re(eta_exit)`. Total internal reflection at a real interface does not
                # exist for it: the shortcuts below are for the real substrate. Sub -> stack -> Air keeps
                # the real part (the plate model, `certus_substrate_absorption`, carries the loss).
                eta_exit, exit_ok = oblique_exit_admittance(n_sub[i_wl], sin_theta_air, is_s_pol)

                cos_inc = np.sqrt(max(0.0, 1.0 - sin_theta_air * sin_theta_air))

                if (not exit_ok) or ((not is_s_pol) and abs(cos_inc) < SMALL_EPSILON):
                    R_arr[i_wl] = 1.0

                    T_arr[i_wl] = 0.0

                    continue

                eta_inc = n_inc * cos_inc if is_s_pol else n_inc / cos_inc

            else:
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

            # The flux that enters the exit medium: `Re(eta_exit)` when it absorbs, `eta_exit` when it does not.
            if absorbing_substrate:
                t_gain = eta_exit.real / eta_inc

            else:
                t_gain = eta_exit / eta_inc

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

            Tv = t_gain * (t * t.conjugate()).real

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

                dT[i_wl, iv] = t_gain * 2.0 * (t.conjugate() * dt).real

        return R_arr, T_arr, dR, dT

    return kernel


_compute_oblique_rt_and_grads_kernel = _make_oblique_rt_and_grads_kernel(False)

_compute_oblique_rt_and_grads_kernel_absorbing = _make_oblique_rt_and_grads_kernel(True)


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

    kernel = _pick_kernel(
        _compute_oblique_rt_and_grads_kernel, _compute_oblique_rt_and_grads_kernel_absorbing, n_sub_c128
    )

    return kernel(
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

    kernel = _pick_kernel(
        _compute_oblique_rt_and_grads_kernel, _compute_oblique_rt_and_grads_kernel_absorbing, n_sub_c128
    )

    front = kernel(
        ep_f64,
        n_layers_c128,
        n_sub_c128,
        wls_f64,
        var_idx_i64,
        float(angle_deg),
        bool(is_s_pol),
        False,
    )

    reverse = kernel(
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
    substrate_thickness_nm: float = DEFAULT_SUBSTRATE_THICKNESS_NM,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Backside oblique bundle for one polarization.

    Returns y_R, dy_R, y_T, dy_T wrt front thickness variables.

    A substrate that absorbs is a plate of thickness `substrate_thickness_nm`: the back-side quantities are
    seen through its loss (`apply_plate_loss`), and the combination below is the one of a plate without loss.

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

    Rb_prime, Tb = apply_plate_loss(Rb_prime, Tb, n_sub_c128, wls_f64, angle_deg, substrate_thickness_nm)

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


