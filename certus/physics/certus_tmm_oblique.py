import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import calculate_single_interface_R
from .certus_tmm_backside import _apply_exact_backside_generic, apply_exact_backside_combination
from .certus_tmm_matrix import compute_complex_phase_components, calc_spectrum_front


# =============================================================================


# OBLIQUE INCIDENCE CALCULATIONS (Full TMM Implementation)


# =============================================================================


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j) baked-in. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _calc_spectrum_oblique_parallel(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    d_layers: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Numba-parallelized oblique incidence calculation.

    is_s_pol: True for 's' polarization, False for 'p'.

    """

    n_wl = len(wls)

    n_layers_count = n_layers_T.shape[1] if n_layers_T.ndim > 1 else 0

    R = np.empty(n_wl, dtype=np.float64)

    T = np.empty(n_wl, dtype=np.float64)

    n0 = 1.0  # Air

    theta0_rad = np.deg2rad(angle_deg)

    sin_theta0 = np.sin(theta0_rad)

    cos_theta0 = np.cos(theta0_rad)

    for i in prange(n_wl):
        wl = wls[i]

        n_sub_val = n_sub[i]

        if n_layers_count == 0:
            # No layers - direct Fresnel

            n_sub_real = n_sub_val.real

            sin_theta_sub = (n0 / n_sub_real) * sin_theta0

            if sin_theta_sub > 1.0:
                R[i] = 1.0

                T[i] = 0.0

                continue

            cos_theta_sub = np.sqrt(1.0 - sin_theta_sub * sin_theta_sub)

            if is_s_pol:
                eta_inc = n0 * cos_theta0

                eta_sub = n_sub_real * cos_theta_sub

            else:
                eta_inc = n0 / cos_theta0

                eta_sub = n_sub_real / cos_theta_sub

            r = (eta_inc - eta_sub) / (eta_inc + eta_sub)

            R[i] = r * r

            T[i] = 1.0 - R[i]

            continue

        # TMM with layers

        # Use complex arithmetic for robustness (matches compute_TMM_single_point_k0_exact)

        M00 = complex(1.0, 0.0)

        M01 = complex(0.0, 0.0)

        M10 = complex(0.0, 0.0)

        M11 = complex(1.0, 0.0)

        k = TWO_PI / wl

        for j in range(n_layers_count):
            n_layer = n_layers_T[i, j]

            d = d_layers[j]

            if abs(n_layer) < SMALL_EPSILON:
                R[i] = 1.0

                T[i] = 0.0

                break

            # Snell's law

            sin_theta_layer = (n0 / n_layer) * sin_theta0

            cos_theta_layer_sq = 1.0 - sin_theta_layer * sin_theta_layer

            cos_theta_layer = np.sqrt(cos_theta_layer_sq)

            # Optical admittance

            if is_s_pol:
                eta_layer = n_layer * cos_theta_layer

            else:
                if abs(cos_theta_layer) < SMALL_EPSILON:
                    R[i] = 1.0

                    T[i] = 0.0

                    break

                eta_layer = n_layer / cos_theta_layer

            # Phase

            phi = k * n_layer * d * cos_theta_layer

            phi_r = phi.real

            phi_i = phi.imag

            # Stable complex trig

            cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag = compute_complex_phase_components(phi_r, phi_i)

            cp = complex(cos_phi_real, cos_phi_imag)

            sp = complex(sin_phi_real, sin_phi_imag)

            if abs(eta_layer) < SMALL_EPSILON:
                R[i] = 1.0

                T[i] = 0.0

                break

            # Macleod: L01 = i * sin / eta, L10 = i * eta * sin

            # Phase factor +1j

            L01 = 1j * sp / eta_layer

            L10 = 1j * eta_layer * sp

            # L00 = L11 = cp

            # Matrix multiply: L @ M

            # N00 = L00 M00 + L01 M10

            # N01 = L00 M01 + L01 M11

            # N10 = L10 M00 + L11 M10

            # N11 = L10 M01 + L11 M11

            t00 = cp * M00 + L01 * M10

            t01 = cp * M01 + L01 * M11

            t10 = L10 * M00 + cp * M10

            t11 = L10 * M01 + cp * M11

            M00, M01, M10, M11 = t00, t01, t10, t11

        else:
            # Completed layer loop - compute R, T

            n_sub_real = n_sub_val.real

            sin_theta_sub = (n0 / n_sub_real) * sin_theta0

            if sin_theta_sub > 1.0:
                R[i] = 1.0

                T[i] = 0.0

                continue

            cos_theta_sub = np.sqrt(1.0 - sin_theta_sub * sin_theta_sub)

            if is_s_pol:
                eta_sub = n_sub_real * cos_theta_sub

                eta_inc = n0 * cos_theta0

            else:
                eta_sub = n_sub_real / cos_theta_sub

                eta_inc = n0 / cos_theta0

            # [B]   [M00 M01] [1      ]

            # [C] = [M10 M11] [eta_sub]

            # Note: eta_inc, eta_sub are strictly real here (transparent incident/exit approximation for R/T calculation)

            # This matches standard behavior. Absorption in substrate handled by Backside Correction functions.

            B = M00 + M01 * eta_sub

            C = M10 + M11 * eta_sub

            denom = eta_inc * B + C

            denom_mag_sq = denom.real**2 + denom.imag**2

            if denom_mag_sq < SMALL_EPSILON:
                R[i] = 1.0

                T[i] = 0.0

                continue

            num = eta_inc * B - C

            r = num / denom

            R_val = (r * r.conjugate()).real

            R[i] = max(0.0, min(1.0, R_val))

            # Transmission

            # t = 2 * eta_inc / denom

            t = 2.0 * eta_inc / denom

            # T = (Re(eta_sub) / Re(eta_inc)) * |t|^2

            T_val = (eta_sub.real / eta_inc.real) * (t * t.conjugate()).real

            T[i] = max(0.0, min(1.0, T_val))

            continue

    return R, T


# --- LOCKED --- Wrapper oblique delegates to _calc_spectrum_oblique_parallel ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


def calc_spectrum_oblique_vectorized(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    d_layers: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    polarization: str,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Calculates R & T for wavelength array at oblique incidence.

    For angle=0, uses calc_spectrum_front for consistency.

    """

    # For normal incidence, use calc_spectrum_front

    if abs(angle_deg) < 1e-6:
        # calc_spectrum_front returns (T, R), but we need (R, T)

        T, R = calc_spectrum_front(wls, d_layers, n_layers_T, n_sub)

        return R, T

    # Convert polarization string to boolean for Numba

    is_s_pol = polarization.lower() == "s"

    # Ensure correct dtypes

    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)

    d_layers_f64 = np.ascontiguousarray(d_layers, dtype=np.float64)

    n_layers_T_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)

    return _calc_spectrum_oblique_parallel(wls_f64, n_layers_T_c128, d_layers_f64, n_sub_c128, angle_deg, is_s_pol)


def calc_spectrum_oblique_backside_vectorized(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    d_layers: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    polarization: str,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Oblique wrapper with incoherent backside (bare substrate).

    """

    # Single source of truth: delegate to full oblique exact with empty back stack.

    is_s_pol = polarization.lower() == "s"

    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)

    return calc_spectrum_full_oblique_exact(
        wls_f64,
        np.ascontiguousarray(d_layers, dtype=np.float64),
        np.ascontiguousarray(n_layers_T, dtype=np.complex128),
        np.zeros(0, dtype=np.float64),
        np.zeros((len(wls_f64), 0), dtype=np.complex128),
        np.ascontiguousarray(n_sub, dtype=np.complex128),
        float(angle_deg),
        is_s_pol,
    )


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _oblique_stack_rt_single(
    wl: float,
    n_layers_row: np.ndarray,
    d_layers: np.ndarray,
    sin_theta_air: float,
    cos_theta_air: float,
    n_inc_real: float,
    n_exit_real: float,
    is_s_pol: bool,
) -> tuple[float, float]:
    """Single-wavelength oblique R/T for one stack and fixed incident/exit media."""

    n_layers_count = len(d_layers)

    M00 = complex(1.0, 0.0)

    M01 = complex(0.0, 0.0)

    M10 = complex(0.0, 0.0)

    M11 = complex(1.0, 0.0)

    k = TWO_PI / wl

    for j in range(n_layers_count):
        n_layer = n_layers_row[j]

        if abs(n_layer) < SMALL_EPSILON:
            return 1.0, 0.0

        sin_theta_layer = sin_theta_air / n_layer

        cos_theta_layer = np.sqrt(1.0 - sin_theta_layer * sin_theta_layer)

        if is_s_pol:
            eta_layer = n_layer * cos_theta_layer

        else:
            if abs(cos_theta_layer) < SMALL_EPSILON:
                return 1.0, 0.0

            eta_layer = n_layer / cos_theta_layer

        if abs(eta_layer) < SMALL_EPSILON:
            return 1.0, 0.0

        phi = k * n_layer * d_layers[j] * cos_theta_layer

        cp = np.cos(phi)

        sp = np.sin(phi)

        L01 = 1j * sp / eta_layer

        L10 = 1j * eta_layer * sp

        t00 = cp * M00 + L01 * M10

        t01 = cp * M01 + L01 * M11

        t10 = L10 * M00 + cp * M10

        t11 = L10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    sin_exit = sin_theta_air / max(n_exit_real, SMALL_EPSILON)

    if sin_exit > 1.0:
        return 1.0, 0.0

    cos_exit = np.sqrt(1.0 - sin_exit * sin_exit)

    if is_s_pol:
        eta_inc = (
            n_inc_real * cos_theta_air
            if n_inc_real == 1.0
            else n_inc_real * np.sqrt(max(0.0, 1.0 - (sin_theta_air / max(n_inc_real, SMALL_EPSILON)) ** 2))
        )

        eta_exit = n_exit_real * cos_exit

    else:
        cos_inc = (
            cos_theta_air
            if n_inc_real == 1.0
            else np.sqrt(max(0.0, 1.0 - (sin_theta_air / max(n_inc_real, SMALL_EPSILON)) ** 2))
        )

        if abs(cos_inc) < SMALL_EPSILON or abs(cos_exit) < SMALL_EPSILON:
            return 1.0, 0.0

        eta_inc = n_inc_real / cos_inc

        eta_exit = n_exit_real / cos_exit

    B = M00 + M01 * eta_exit

    C = M10 + M11 * eta_exit

    denom = eta_inc * B + C

    den2 = denom.real * denom.real + denom.imag * denom.imag

    if den2 < SMALL_EPSILON:
        return 1.0, 0.0

    num = eta_inc * B - C

    r = num / denom

    t = 2.0 * eta_inc / denom

    R = (r * r.conjugate()).real

    T = (eta_exit / eta_inc) * (t * t.conjugate()).real

    if R < 0.0:
        R = 0.0

    elif R > 1.0:
        R = 1.0

    if T < 0.0:
        T = 0.0

    elif T > 1.0:
        T = 1.0

    return R, T


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def oblique_front_char_matrix_single(
    wl: float,
    n_layers_row: np.ndarray,
    d_layers: np.ndarray,
    sin_theta_air: float,
    cos_theta_air: float,
    is_s_pol: bool,
):
    """2×2 characteristic matrix (Macleod) of the battery alone, air interface -> last film.

    Same convention as `_calc_spectrum_oblique_parallel` / `_oblique_stack_rt_single`.

    The substrate does not intervene: we then fix η_sub to obtain R,T by admittance."""

    n_layers_count = len(d_layers)

    M00 = complex(1.0, 0.0)

    M01 = complex(0.0, 0.0)

    M10 = complex(0.0, 0.0)

    M11 = complex(1.0, 0.0)

    if n_layers_count == 0:
        return M00, M01, M10, M11

    k = TWO_PI / wl

    for j in range(n_layers_count):
        n_layer = n_layers_row[j]

        if abs(n_layer) < SMALL_EPSILON:
            return complex(1.0, 0.0), complex(0.0, 0.0), complex(0.0, 0.0), complex(1.0, 0.0)

        sin_theta_layer = sin_theta_air / n_layer

        cos_theta_layer_sq = 1.0 - sin_theta_layer * sin_theta_layer

        cos_theta_layer = np.sqrt(cos_theta_layer_sq)

        if is_s_pol:
            eta_layer = n_layer * cos_theta_layer

        else:
            if abs(cos_theta_layer) < SMALL_EPSILON:
                return complex(1.0, 0.0), complex(0.0, 0.0), complex(0.0, 0.0), complex(1.0, 0.0)

            eta_layer = n_layer / cos_theta_layer

        if abs(eta_layer) < SMALL_EPSILON:
            return complex(1.0, 0.0), complex(0.0, 0.0), complex(0.0, 0.0), complex(1.0, 0.0)

        phi = k * n_layer * d_layers[j] * cos_theta_layer

        phi_r = phi.real

        phi_i = phi.imag

        cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag = compute_complex_phase_components(phi_r, phi_i)

        cp = complex(cos_phi_real, cos_phi_imag)

        sp = complex(sin_phi_real, sin_phi_imag)

        L01 = 1j * sp / eta_layer

        L10 = 1j * eta_layer * sp

        t00 = cp * M00 + L01 * M10

        t01 = cp * M01 + L01 * M11

        t10 = L10 * M00 + cp * M10

        t11 = L10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    return M00, M01, M10, M11


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def oblique_front_rt_from_char_matrix_nsub_real(
    M00,
    M01,
    M10,
    M11,
    n_sub_real: float,
    sin_theta_air: float,
    cos_theta_air: float,
    is_s_pol: bool,
):
    """R, T in air incidence -> substrate from M (stack) and real n_sub (η_sub via Snell)."""

    n0 = 1.0

    if n_sub_real < SMALL_EPSILON:
        return 1.0, 0.0

    sin_theta_sub = (n0 / n_sub_real) * sin_theta_air

    if sin_theta_sub > 1.0:
        return 1.0, 0.0

    cos_theta_sub = np.sqrt(1.0 - sin_theta_sub * sin_theta_sub)

    if is_s_pol:
        eta_sub = n_sub_real * cos_theta_sub

        eta_inc = n0 * cos_theta_air

    else:
        if abs(cos_theta_sub) < SMALL_EPSILON:
            return 1.0, 0.0

        eta_sub = n_sub_real / cos_theta_sub

        eta_inc = n0 / cos_theta_air

    B = M00 + M01 * eta_sub

    C = M10 + M11 * eta_sub

    denom = eta_inc * B + C

    denom_mag_sq = denom.real * denom.real + denom.imag * denom.imag

    if denom_mag_sq < SMALL_EPSILON:
        return 1.0, 0.0

    num = eta_inc * B - C

    r = num / denom

    R_val = (r * r.conjugate()).real

    R_out = max(0.0, min(1.0, R_val))

    t = 2.0 * eta_inc / denom

    T_val = (eta_sub / eta_inc) * (t * t.conjugate()).real

    T_out = max(0.0, min(1.0, T_val))

    return R_out, T_out


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calc_spectrum_full_oblique_exact(
    wls: np.ndarray,
    d_front: np.ndarray,
    n_front: np.ndarray,
    d_back: np.ndarray,
    n_back: np.ndarray,
    n_sub: np.ndarray,
    angle_deg: float,
    is_s_pol: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Oblique exact incoherent combination for Front + Back stacks.

    """

    n_wls = len(wls)

    R_total = np.empty(n_wls, dtype=np.float64)

    T_total = np.empty(n_wls, dtype=np.float64)

    theta0_rad = np.deg2rad(angle_deg)

    sin_theta_air = np.sin(theta0_rad)

    cos_theta_air = np.cos(theta0_rad)

    d_front_rev = d_front[::-1].copy()

    d_back_rev = d_back[::-1].copy()

    for i in prange(n_wls):
        wl = wls[i]

        n_sub_real = n_sub[i].real

        if n_sub_real < 1e-12:
            R_total[i] = 1.0

            T_total[i] = 0.0

            continue

        # Forward: Air -> Front -> Sub

        Rf, Tf = _oblique_stack_rt_single(
            wl,
            n_front[i],
            d_front,
            sin_theta_air,
            cos_theta_air,
            1.0,
            n_sub_real,
            is_s_pol,
        )

        # Reverse front: Sub -> Front -> Air (for Rf' and T_front_rev)

        n_front_rev_i = n_front[i, ::-1].copy()

        Rf_prime, T_front_rev = _oblique_stack_rt_single(
            wl,
            n_front_rev_i,
            d_front_rev,
            sin_theta_air,
            cos_theta_air,
            n_sub_real,
            1.0,
            is_s_pol,
        )

        # Reverse back: Sub -> Back -> Air

        if len(d_back) > 0:
            n_back_rev_i = n_back[i, ::-1].copy()

            Rb_prime, Tb = _oblique_stack_rt_single(
                wl,
                n_back_rev_i,
                d_back_rev,
                sin_theta_air,
                cos_theta_air,
                n_sub_real,
                1.0,
                is_s_pol,
            )

        else:
            # Bare substrate interface as "back stack"

            sin_sub = sin_theta_air / n_sub_real

            if sin_sub > 1.0:
                Rb_prime = 1.0

                Tb = 0.0

            else:
                cos_sub = np.sqrt(1.0 - sin_sub * sin_sub)

                if is_s_pol:
                    eta_sub = n_sub_real * cos_sub

                    eta_air = 1.0 * cos_theta_air

                else:
                    if abs(cos_sub) < SMALL_EPSILON or abs(cos_theta_air) < SMALL_EPSILON:
                        Rb_prime = 1.0

                        Tb = 0.0

                        denom = 0.0

                        eta_sub = 0.0

                        eta_air = 0.0

                    else:
                        eta_sub = n_sub_real / cos_sub

                        eta_air = 1.0 / cos_theta_air

                denom = eta_sub + eta_air

                if abs(denom) < SMALL_EPSILON:
                    Rb_prime = 1.0

                    Tb = 0.0

                else:
                    rb = (eta_sub - eta_air) / denom

                    tb = 2.0 * eta_sub / denom

                    Rb_prime = (rb * rb.conjugate()).real

                    Tb = (eta_air / eta_sub) * (tb * tb.conjugate()).real

                    if Rb_prime < 0.0:
                        Rb_prime = 0.0

                    elif Rb_prime > 1.0:
                        Rb_prime = 1.0

                    if Tb < 0.0:
                        Tb = 0.0

                    elif Tb > 1.0:
                        Tb = 1.0

        denom = 1.0 - Rf_prime * Rb_prime

        if denom < 1e-12:
            denom = 1e-12

        Ttot = (Tf * Tb) / denom

        Rtot = Rf + (Tf * T_front_rev * Rb_prime) / denom

        if Ttot < 0.0:
            Ttot = 0.0

        elif Ttot > 1.0:
            Ttot = 1.0

        if Rtot < 0.0:
            Rtot = 0.0

        elif Rtot > 1.0:
            Rtot = 1.0

        T_total[i] = Ttot

        R_total[i] = Rtot

    return R_total, T_total


# --- LOCKED --- Exact incoherent backside combination ───


# Fabry-Perot intensity formula. DO NOT MODIFY without running tests.

