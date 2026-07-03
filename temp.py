import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import calculate_bare_substrate_R, calculate_bare_substrate_RT, calculate_single_interface_R

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # For a transparent substrate (Standard Mode), the reference measurement includes the backside!

    # Formula: R_total = 2*R_single / (1 + R_single) [assuming R_front=R_back, T=1-R]

    # THIS LOGIC IS VERIFIED AND CORRECT. DO NOT REVERT TO SINGLE INTERFACE REFLECTION.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns.real < 0:
            ns = complex(1.5, ns.imag)

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        # Standard substrate (Transparent) has backside reflection

        # R_total = R_single + (T_single^2 * R_back) / (1 - R_single * R_back)

        # Assuming identical interfaces: R_back = R_single, T_single = 1 - R_single

        # R_total = 2 * R_single / (1 + R_single)

        R[i] = 2.0 * R_single / (1.0 + R_single)

    return R


# ─── LOCKED ─── Substrate physics validated manually ───


# T_sub = (1-R)/(1+R). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_RT(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    n_pts = len(wavelengths)

    T = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        T[i] = (1.0 - R_single) / (1.0 + R_single)

    return T


# ─── LOCKED ─── Frosted glass physics validated manually ───


# Single-interface ONLY (no backside). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_single_interface_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # Frosted glass acts as an infinite substrate because the backside is roughened/absorbing.

    # There is NO specular backside reflection.

    # We MUST return single-interface reflection R = |(n0-ns)/(n0+ns)|^2 only.

    # DO NOT ADD BACKSIDE REFLECTION HERE.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns < 0:
            ns = 1.5

        r = (n0 - ns) / (n0 + ns)

        R[i] = r * r

    return R


# ─── LOCKED ─── Validated by test_tmm_coherence.py + test_gradient_vs_fd.py ───


# Macleod convention. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_complex_phase_components(phi_r: float, phi_i: float) -> tuple[float, float, float, float]:

    # Receives phi_r=k0*n*d, phi_i=k0*k*d (k>=0).

    # Returns cos/sin components equivalent to Macleod convention (n-ik phase).

    exp_pos = np.exp(-phi_i)

    exp_neg = np.exp(phi_i)

    cos_phi_r = np.cos(phi_r)

    sin_phi_r = np.sin(phi_r)

    cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0

    cos_phi_imag = sin_phi_r * (exp_pos - exp_neg) / 2.0

    sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0

    sin_phi_imag = cos_phi_r * (exp_neg - exp_pos) / 2.0

    return cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n-ik). DO NOT MODIFY without re-running the tests.

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # For a transparent substrate (Standard Mode), the reference measurement includes the backside!

    # Formula: R_total = 2*R_single / (1 + R_single) [assuming R_front=R_back, T=1-R]

    # THIS LOGIC IS VERIFIED AND CORRECT. DO NOT REVERT TO SINGLE INTERFACE REFLECTION.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns.real < 0:
            ns = complex(1.5, ns.imag)

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        # Standard substrate (Transparent) has backside reflection

        # R_total = R_single + (T_single^2 * R_back) / (1 - R_single * R_back)

        # Assuming identical interfaces: R_back = R_single, T_single = 1 - R_single

        # R_total = 2 * R_single / (1 + R_single)

        R[i] = 2.0 * R_single / (1.0 + R_single)

    return R


# ─── LOCKED ─── Substrate physics validated manually ───


# T_sub = (1-R)/(1+R). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_RT(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    n_pts = len(wavelengths)

    T = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        T[i] = (1.0 - R_single) / (1.0 + R_single)

    return T


# ─── LOCKED ─── Frosted glass physics validated manually ───


# Single-interface ONLY (no backside). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_single_interface_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # Frosted glass acts as an infinite substrate because the backside is roughened/absorbing.

    # There is NO specular backside reflection.

    # We MUST return single-interface reflection R = |(n0-ns)/(n0+ns)|^2 only.

    # DO NOT ADD BACKSIDE REFLECTION HERE.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns < 0:
            ns = 1.5

        r = (n0 - ns) / (n0 + ns)

        R[i] = r * r

    return R


# ─── LOCKED ─── Validated by test_tmm_coherence.py + test_gradient_vs_fd.py ───


# Macleod convention. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_complex_phase_components(phi_r: float, phi_i: float) -> tuple[float, float, float, float]:

    # Receives phi_r=k0*n*d, phi_i=k0*k*d (k>=0).

    # Returns cos/sin components equivalent to Macleod convention (n-ik phase).

    exp_pos = np.exp(-phi_i)

    exp_neg = np.exp(phi_i)

    cos_phi_r = np.cos(phi_r)

    sin_phi_r = np.sin(phi_r)

    cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0

    cos_phi_imag = sin_phi_r * (exp_pos - exp_neg) / 2.0

    sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0

    sin_phi_imag = cos_phi_r * (exp_neg - exp_pos) / 2.0

    return cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n-ik). DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float,
) -> float:
    """Calculates front-surface reflectance for a single layer on substrate."""

    if not np.isfinite(n_sub) or n_sub < 1.0:
        return np.nan

    n0 = 1.0  # Air

    k = TWO_PI / wavelength

    phi_r = k * n_film_real * thickness_nm

    phi_i = k * n_film_imag * thickness_nm

    cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag = compute_complex_phase_components(phi_r, phi_i)

    n_mag_sq = n_film_real * n_film_real + n_film_imag * n_film_imag

    if n_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_n_r = n_film_real / n_mag_sq

    inv_n_i = n_film_imag / n_mag_sq

    # Macleod convention: +i * sin(phi) / n,  +i * n * sin(phi)

    M01_real = -(inv_n_r * sin_phi_imag + inv_n_i * sin_phi_real)

    M01_imag = inv_n_r * sin_phi_real - inv_n_i * sin_phi_imag

    M10_real = -(n_film_real * sin_phi_imag - n_film_imag * sin_phi_real)

    M10_imag = n_film_real * sin_phi_real + n_film_imag * sin_phi_imag

    term1_r = n0 * cos_phi_real

    term1_i = n0 * cos_phi_imag

    term2_r = n0 * n_sub * M01_real

    term2_i = n0 * n_sub * M01_imag

    term3_r = M10_real

    term3_i = M10_imag

    term4_r = n_sub * cos_phi_real

    term4_i = n_sub * cos_phi_imag

    denom_real = term1_r + term2_r + term3_r + term4_r

    denom_imag = term1_i + term2_i + term3_i + term4_i

    denom_mag_sq = denom_real * denom_real + denom_imag * denom_imag

    if denom_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_denom = 1.0 / denom_mag_sq

    num_real = term1_r + term2_r - term3_r - term4_r

    num_imag = term1_i + term2_i - term3_i - term4_i

    R_single = (num_real**2 + num_imag**2) * inv_denom

    return max(0.0, min(1.0, R_single))


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_reflection_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> np.ndarray:
    """Calculates front-surface reflectance array for a single layer on substrate."""

    n = len(wavelengths)

    res = np.empty(n, dtype=wavelengths.dtype)

    for i in prange(n):
        res[i] = calculate_reflection_single(wavelengths[i], n_array[i], k_array[i], thickness, n_substrate[i])

    return res


# =============================================================================


# FUSED MONOLAYER R+T WITH BACKSIDE (Opus 4.6 - INDEX hot path)


# =============================================================================


# ─── LOCKED ─── Validated by test_tmm_coherence.py + test_tmm_inline.py (test 0b) ───


# Macleod convention (+1j, n-ik) + incoherent backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_transmission_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> tuple[float, float]:
    """

    R_front + T_total (exact incoherent backside) for a single layer.

    Uses native complex arithmetic matching compute_TMM_generic convention.

    Returns:

        (R_front, T_total_with_backside)

    CRITICAL PHYSICS NOTE:

    This function explicitly INCLUDES incoherent backside reflection.

    It is designed for Standard Mode (Transparent substrate).

    DO NOT REMOVE THE BACKSIDE TERM.

    """

    if not np.isfinite(n_sub.real) or n_sub.real < 1.0:
        return np.nan, np.nan

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    ns = n_sub

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    # Layer matrix elements

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # M00 = M11 = cp

    # --- Forward: Air -> Film -> Sub ---

    # Air index = 1.0 (real)

    B = cp + M01 * ns

    C = M10 + cp * ns

    # Y = n0 * B + C = 1.0 * B + C

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    # r = (n0*B - C) / (n0*B + C)

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    # Transmittance into substrate (T_front)

    # T = 4 * Re(ns) * Re(n0) / |n0*B + C|^2

    # n0 = 1

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (for incoherent denominator) ---

    # Incident medium is Sub (ns), Exit is Air (1)

    # M_total = M_layer (same)

    # B' = M00 + M01 * n_exit = cp + M01

    # C' = M10 + M11 * n_exit = M10 + cp

    Bp = cp + M01

    Cp = M10 + cp

    # Y' = ns * B' + C'

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0
        T_prime = 0.0
    else:
        # r' = (ns*B' - C') / (ns*B' + C')

        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq
        
        # T' = 4 * Re(1) * Re(ns) / |Y'|^2 = 4 * ns.real / Yp_mag_sq
        T_prime = 4.0 * ns.real / Yp_mag_sq

    # --- Backside interface Sub|Air ---

    # r_b = (ns - 1) / (ns + 1)

    r_b_num = ns - 1.0

    r_b_den = ns + 1.0

    r_b = r_b_num / r_b_den

    R_sub = r_b.real * r_b.real + r_b.imag * r_b.imag

    # T_sub = 1 - R_sub (Assuming no absorption at interface itself, Fresnel)

    T_sub = 1.0 - R_sub

    # --- Exact incoherent combination ---

    # If substrate is absorbing, we should account for absorption in the substrate volume?

    # Standard formula T_total = T_front * T_back * exp(-alpha*d) / (1 - R_front_back * R_back * exp...)

    # Here we assume transparent substrate logic (exp terms = 1) but capable of handling n complex.

    # If thick absorbing substrate, T_total goes to 0 independently.

    # For now, keeping logic "incoherent sum" unmodified except for types.

    denom_incoh = 1.0 - R_prime * R_sub

    if abs(denom_incoh) < 1e-12:
        denom_incoh = 1e-12

    # T_total = (T_front * T_sub) / (1 - R' * R_sub)

    T_total = (T_front * T_sub) / denom_incoh

    # R_total = R_front + (T_front * T_prime * R_sub) / (1 - R' * R_sub)

    # T_prime = (4 Re(n0) Re(ns)) / |D'|^2.

    # D' is Y' = ns*B' + C'. D is Y = n0*B + C.

    # B' = cp + M01, C' = M10 + cp. B = cp + M01*ns, C = M10 + cp*ns.

    # For lossless films, |D|=|D'|. Absorption breaks this?

    # Let's verify T_prime calculate to be safe.

    # T_prime (Sub -> Air)

    # T' = 4 * Re(1) * Re(ns) / |Y'|^2 = 4 * ns.real / Yp_mag_sq

    T_prime = 4.0 * ns.real / Yp_mag_sq

    R_back_contribution = (T_front * T_prime * R_sub) / denom_incoh

    R_total = R_front + R_back_contribution

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total


# ─── LOCKED ─── Delegates to calculate_transmission_single (R′ at denominator) ───


# Former version erroneously used 1 - R_front·R_back instead of 1 - R′·R_sub (see file header).


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_reflection_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float,
) -> float:

    if not np.isfinite(n_sub) or n_sub < 1.0:
        return np.nan

    _rf, _t_tot = calculate_transmission_single(wavelength, n_film_real, n_film_imag, thickness_nm, complex(n_sub, 0.0))

    if not np.isfinite(_rf):
        return np.nan

    return max(0.0, min(1.0, _rf))


# ─── LOCKED ─── Vectorized wrapper of calculate_transmission_single ───


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_transmission_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> np.ndarray:

    n_pts = len(wavelengths)

    T_array = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        _r, T_array[i] = calculate_transmission_single(
            wavelengths[i], n_array[i], k_array[i], thickness, complex(n_substrate[i], 0.0)
        )

    return T_array


# ─── LOCKED ─── Vectorized wrapper of calculate_transmission_single ───


# Macleod convention (+1j, n-ik) + backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_backside_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Fused R_front + T_with_backside for monolayer over full spectrum.

    2x faster than separate  + .

    CRITICAL PHYSICS NOTE:

    This vectorized wrapper returns Standard Mode results (Transparent substrate).

    Measurements INCLUDE backside reflection.

    """

    n_pts = len(wavelengths)

    R_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    T_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        R_arr[i], T_arr[i] = calculate_transmission_single(
            wavelengths[i], n_array[i], k_array[i], thickness, complex(n_substrate[i], 0.0)
        )

    return R_arr, T_arr


# =============================================================================


# Batch single-layer TMM kernels for PGlobal evaluate_batch optimization.
# Fuses N spectra × n_pix TMM + MSE into one prange, eliminating N separate
# Python→Numba dispatches. ~20-30% faster than N sequential array calls.


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def batch_single_layer_T_mse(
    wavelengths,
    n_sub,
    w,
    inv_npix,
    t_exp,
    n_batch,
    k_batch,
    d_batch,
):
    """N spectra T-MSE in one prange(N). Each thread computes a full spectrum."""
    N = n_batch.shape[0]
    n_pix = wavelengths.shape[0]
    mse_out = np.empty(N, dtype=np.float64)
    for i in prange(N):
        acc = 0.0
        d_i = d_batch[i]
        for j in range(n_pix):
            _r, t_th = calculate_transmission_single(
                wavelengths[j], n_batch[i, j], k_batch[i, j], d_i, complex(n_sub[j], 0.0)
            )
            e = t_exp[j] - t_th
            acc += w[j] * e * e
        mse_out[i] = acc * inv_npix
    return mse_out


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def batch_single_layer_RT_mse(
    wavelengths,
    n_sub,
    w,
    inv_npix,
    t_exp,
    r_exp,
    n_batch,
    k_batch,
    d_batch,
    wt,
    wr,
):
    """N spectra fused R+T MSE in one prange(N)."""
    N = n_batch.shape[0]
    n_pix = wavelengths.shape[0]
    wsum = wt + wr
    mse_out = np.empty(N, dtype=np.float64)
    for i in prange(N):
        acc_t = 0.0
        acc_r = 0.0
        d_i = d_batch[i]
        for j in range(n_pix):
            r_th, t_th = calculate_transmission_single(
                wavelengths[j], n_batch[i, j], k_batch[i, j], d_i, complex(n_sub[j], 0.0)
            )
            e_t = t_exp[j] - t_th
            acc_t += w[j] * e_t * e_t
            e_r = r_exp[j] - r_th
            acc_r += w[j] * e_r * e_r
        mse_out[i] = (wt * acc_t + wr * acc_r) * inv_npix / wsum
    return mse_out


# =============================================================================


# ABSORBING SUBSTRATE - Beer-Lambert incoherent model


# =============================================================================


# Formulas (film + thick absorbing substrate of physical thickness D_nm):


#   alpha = 4π·k_sub / lambda_nm          (absorption coefficient, nm⁻¹)


#   att1 = exp(-alpha·D_nm)           (single-pass attenuation)


#   att2 = att1²                  (double-pass)


#   denom = 1 - R′_front · R_back · att2


#   R_total = R_front + T_front · T_prime · R_back · att2 / denom


#   T_total = T_front · T_back  · att1             / denom


#


# For the bare substrate reference (n_sub, k_sub arrays; symmetric interfaces):


#   R_f = |(1-ns)/(1+ns)|², T_f = 1 - R_f, R_b = R_f, T_b = T_f


#


# For film+substrate: R_front/T_front/R_prime come from the coherent TMM


# (same as ); backside is bare Fresnel.


# =============================================================================


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _calculate_RT_absorbing_sub_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub_real: float,
    k_sub: float,
    D_sub_nm: float,
) -> tuple[float, float]:
    """Scalar: R+T for one layer on absorbing substrate (Beer-Lambert incoherent)."""

    if not np.isfinite(n_sub_real) or n_sub_real < 1.0:
        return np.nan, np.nan

    ns = complex(n_sub_real, 0.0)  # substrate optical index (real part only for TMM)

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # --- Forward: Air -> Film -> Sub ---

    B = cp + M01 * ns

    C = M10 + cp * ns

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (R_prime for denom) ---

    Bp = cp + M01

    Cp = M10 + cp

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0

        T_prime = 0.0

    else:
        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq

        T_prime = 4.0 * ns.real / Yp_mag_sq

    # --- Backside interface Sub|Air (bare Fresnel, real ns for interface) ---

    r_b = (n_sub_real - 1.0) / (n_sub_real + 1.0)

    R_back = r_b * r_b

    T_back = 1.0 - R_back

    # --- Beer-Lambert attenuation through substrate bulk ---

    alpha = 4.0 * math.pi * k_sub / wavelength  # nm⁻¹

    att1 = math.exp(-alpha * D_sub_nm)  # single-pass

    att2 = att1 * att1  # double-pass

    denom = 1.0 - R_prime * R_back * att2

    if abs(denom) < 1e-12:
        denom = 1e-12

    R_total = R_front + (T_front * T_prime * R_back * att2) / denom

    T_total = (T_front * T_back * att1) / denom

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_absorbing_substrate_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
    k_substrate: np.ndarray,
    D_sub_nm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """

    R + T for a single film on an absorbing substrate (Beer-Lambert incoherent backside).

    Args:

        wavelengths   : wavelengths in nm

        n_array       : film refractive index

        k_array       : film extinction coefficient

        thickness     : film thickness in nm

        n_substrate  : substrate real refractive index (per wavelength)

        k_substrate  : substrate extinction coefficient (per wavelength)

        D_sub_nm      : physical substrate thickness in nm

    """

    n_pts = len(wavelengths)

    R_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    T_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        R_arr[i], T_arr[i] = _calculate_RT_absorbing_sub_single(
            wavelengths[i],
            n_array[i],
            k_array[i],
            thickness,
            n_substrate[i],
            k_substrate[i],
            D_sub_nm,
        )

    return R_arr, T_arr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_R_absorbing(
    wavelengths: np.ndarray,
    n_substrate: np.ndarray,
    k_substrate: np.ndarray,
    D_nm: float,
) -> np.ndarray:
    """

    Reference reflectance of a bare absorbing substrate - double face, with absorption.

    R_sub = R_f + T_f²·R_f·att2 / (1 - R_f²·att2). Used for R/Tnu when k_sub ≠ 0.

    """

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        ns = n_substrate[i]

        k_s = k_substrate[i]

        r = (1.0 - ns) / (1.0 + ns)

        R_f = r * r

        T_f = 1.0 - R_f

        alpha = 4.0 * math.pi * k_s / wavelengths[i]

        att2 = math.exp(-2.0 * alpha * D_nm)

        denom = 1.0 - R_f * R_f * att2

        if abs(denom) < 1e-12:
            denom = 1e-12

        R[i] = R_f + T_f * T_f * R_f * att2 / denom

    return R


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_T_absorbing(
    wavelengths: np.ndarray,
    n_substrate: np.ndarray,
    k_substrate: np.ndarray,
    D_nm: float,
) -> np.ndarray:
    """

    Reference transmittance of a bare absorbing substrate - double face, with absorption.

    T_sub = T_f² · att1 / (1 - R_f² · att2)

    Double face: two interfaces (air|substrate|air), att1 = exp(-alpha·D), att2 = att1².

    Used for T/Tnu normalization when substrate has k_sub ≠ 0.

    """

    n_pts = len(wavelengths)

    T = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        ns = n_substrate[i]

        k_s = k_substrate[i]

        r = (1.0 - ns) / (1.0 + ns)

        R_f = r * r

        T_f = 1.0 - R_f

        alpha = 4.0 * math.pi * k_s / wavelengths[i]

        att1 = math.exp(-alpha * D_nm)

        att2 = att1 * att1

        denom = 1.0 - R_f * R_f * att2

        if abs(denom) < 1e-12:
            denom = 1e-12

        T[i] = T_f * T_f * att1 / denom

    return T


# =============================================================================


# MULTILAYER TMM


# =============================================================================


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n̂ = n - ik). index 0 = substrate. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_TMM_single_point_k0(
    k0: float, thicknesses: np.ndarray, n_layers_complex: np.ndarray, n_sub: complex
) -> tuple[float, float]:
    """Computes R and T for a multilayer stack (k0 pre-computed variant).

    CAPITAL CONVENTION: index 0 = layer 1 = layer closest to the substrate.

    Complex clues: n̂ = n - ik (imag <= 0 for absorption)."""

    n0 = 1.0  # Air

    n_layers = len(thicknesses)

    M00 = 1.0 + 0j

    M01 = 0.0 + 0j

    M10 = 0.0 + 0j

    M11 = 1.0 + 0j

    I_VAL = +1j

    for i in range(n_layers):
        n_c = n_layers_complex[i]

        # ── GARDE-FOU n-ik ──

        if n_c.imag > 0.0:
            n_c = n_c.real - 1j * n_c.imag

        phi = k0 * n_c * thicknesses[i]

        cp = np.cos(phi)

        isp = I_VAL * np.sin(phi)

        m01 = isp / n_c if abs(n_c) > 1e-12 else 0.0 + 0j

        m10 = isp * n_c

        # Pre-multiplication: M_new = L @ M_old (index 0 = substrate side)

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    # Delegate to factored helper: Air(n0=1) -> Sub(n_sub)

    return compute_RT_from_matrix(M00, M01, M10, M11, complex(n0), n_sub)


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # For a transparent substrate (Standard Mode), the reference measurement includes the backside!

    # Formula: R_total = 2*R_single / (1 + R_single) [assuming R_front=R_back, T=1-R]

    # THIS LOGIC IS VERIFIED AND CORRECT. DO NOT REVERT TO SINGLE INTERFACE REFLECTION.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns.real < 0:
            ns = complex(1.5, ns.imag)

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        # Standard substrate (Transparent) has backside reflection

        # R_total = R_single + (T_single^2 * R_back) / (1 - R_single * R_back)

        # Assuming identical interfaces: R_back = R_single, T_single = 1 - R_single

        # R_total = 2 * R_single / (1 + R_single)

        R[i] = 2.0 * R_single / (1.0 + R_single)

    return R


# ─── LOCKED ─── Substrate physics validated manually ───


# T_sub = (1-R)/(1+R). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_RT(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    n_pts = len(wavelengths)

    T = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        r = (n0 - ns) / (n0 + ns)

        R_single = np.abs(r) ** 2

        T[i] = (1.0 - R_single) / (1.0 + R_single)

    return T


# ─── LOCKED ─── Frosted glass physics validated manually ───


# Single-interface ONLY (no backside). DO NOT MODIFY.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_single_interface_R(wavelengths: np.ndarray, n_substrate: np.ndarray) -> np.ndarray:

    # --- CRITICAL PHYSICS NOTE: ANTI-HALLUCINATION LOCK ---

    # Frosted glass acts as an infinite substrate because the backside is roughened/absorbing.

    # There is NO specular backside reflection.

    # We MUST return single-interface reflection R = |(n0-ns)/(n0+ns)|^2 only.

    # DO NOT ADD BACKSIDE REFLECTION HERE.

    # -----------------------------------------------------

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    n0 = 1.0  # Air

    for i in prange(n_pts):
        ns = n_substrate[i]

        if ns < 0:
            ns = 1.5

        r = (n0 - ns) / (n0 + ns)

        R[i] = r * r

    return R


# ─── LOCKED ─── Validated by test_tmm_coherence.py + test_gradient_vs_fd.py ───


# Macleod convention. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_complex_phase_components(phi_r: float, phi_i: float) -> tuple[float, float, float, float]:

    # Receives phi_r=k0*n*d, phi_i=k0*k*d (k>=0).

    # Returns cos/sin components equivalent to Macleod convention (n-ik phase).

    exp_pos = np.exp(-phi_i)

    exp_neg = np.exp(phi_i)

    cos_phi_r = np.cos(phi_r)

    sin_phi_r = np.sin(phi_r)

    cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0

    cos_phi_imag = sin_phi_r * (exp_pos - exp_neg) / 2.0

    sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0

    sin_phi_imag = cos_phi_r * (exp_neg - exp_pos) / 2.0

    return cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n-ik). DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float,
) -> float:
    """Calculates front-surface reflectance for a single layer on substrate."""

    if not np.isfinite(n_sub) or n_sub < 1.0:
        return np.nan

    n0 = 1.0  # Air

    k = TWO_PI / wavelength

    phi_r = k * n_film_real * thickness_nm

    phi_i = k * n_film_imag * thickness_nm

    cos_phi_real, cos_phi_imag, sin_phi_real, sin_phi_imag = compute_complex_phase_components(phi_r, phi_i)

    n_mag_sq = n_film_real * n_film_real + n_film_imag * n_film_imag

    if n_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_n_r = n_film_real / n_mag_sq

    inv_n_i = n_film_imag / n_mag_sq

    # Macleod convention: +i * sin(phi) / n,  +i * n * sin(phi)

    M01_real = -(inv_n_r * sin_phi_imag + inv_n_i * sin_phi_real)

    M01_imag = inv_n_r * sin_phi_real - inv_n_i * sin_phi_imag

    M10_real = -(n_film_real * sin_phi_imag - n_film_imag * sin_phi_real)

    M10_imag = n_film_real * sin_phi_real + n_film_imag * sin_phi_imag

    term1_r = n0 * cos_phi_real

    term1_i = n0 * cos_phi_imag

    term2_r = n0 * n_sub * M01_real

    term2_i = n0 * n_sub * M01_imag

    term3_r = M10_real

    term3_i = M10_imag

    term4_r = n_sub * cos_phi_real

    term4_i = n_sub * cos_phi_imag

    denom_real = term1_r + term2_r + term3_r + term4_r

    denom_imag = term1_i + term2_i + term3_i + term4_i

    denom_mag_sq = denom_real * denom_real + denom_imag * denom_imag

    if denom_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_denom = 1.0 / denom_mag_sq

    num_real = term1_r + term2_r - term3_r - term4_r

    num_imag = term1_i + term2_i - term3_i - term4_i

    R_single = (num_real**2 + num_imag**2) * inv_denom

    return max(0.0, min(1.0, R_single))


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_reflection_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> np.ndarray:
    """Calculates front-surface reflectance array for a single layer on substrate."""

    n = len(wavelengths)

    res = np.empty(n, dtype=wavelengths.dtype)

    for i in prange(n):
        res[i] = calculate_reflection_single(wavelengths[i], n_array[i], k_array[i], thickness, n_substrate[i])

    return res


# =============================================================================


# FUSED MONOLAYER R+T WITH BACKSIDE (Opus 4.6 - INDEX hot path)


# =============================================================================


# ─── LOCKED ─── Validated by test_tmm_coherence.py + test_tmm_inline.py (test 0b) ───


# Macleod convention (+1j, n-ik) + incoherent backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_transmission_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> tuple[float, float]:
    """

    R_front + T_total (exact incoherent backside) for a single layer.

    Uses native complex arithmetic matching compute_TMM_generic convention.

    Returns:

        (R_front, T_total_with_backside)

    CRITICAL PHYSICS NOTE:

    This function explicitly INCLUDES incoherent backside reflection.

    It is designed for Standard Mode (Transparent substrate).

    DO NOT REMOVE THE BACKSIDE TERM.

    """

    if not np.isfinite(n_sub.real) or n_sub.real < 1.0:
        return np.nan, np.nan

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    ns = n_sub

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    # Layer matrix elements

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # M00 = M11 = cp

    # --- Forward: Air -> Film -> Sub ---

    # Air index = 1.0 (real)

    B = cp + M01 * ns

    C = M10 + cp * ns

    # Y = n0 * B + C = 1.0 * B + C

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    # r = (n0*B - C) / (n0*B + C)

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    # Transmittance into substrate (T_front)

    # T = 4 * Re(ns) * Re(n0) / |n0*B + C|^2

    # n0 = 1

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (for incoherent denominator) ---

    # Incident medium is Sub (ns), Exit is Air (1)

    # M_total = M_layer (same)

    # B' = M00 + M01 * n_exit = cp + M01

    # C' = M10 + M11 * n_exit = M10 + cp

    Bp = cp + M01

    Cp = M10 + cp

    # Y' = ns * B' + C'

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0
        T_prime = 0.0
    else:
        # r' = (ns*B' - C') / (ns*B' + C')

        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq
        
        # T' = 4 * Re(1) * Re(ns) / |Y'|^2 = 4 * ns.real / Yp_mag_sq
        T_prime = 4.0 * ns.real / Yp_mag_sq

    # --- Backside interface Sub|Air ---

    # r_b = (ns - 1) / (ns + 1)

    r_b_num = ns - 1.0

    r_b_den = ns + 1.0

    r_b = r_b_num / r_b_den

    R_sub = r_b.real * r_b.real + r_b.imag * r_b.imag

    # T_sub = 1 - R_sub (Assuming no absorption at interface itself, Fresnel)

    T_sub = 1.0 - R_sub

    # --- Exact incoherent combination ---

    # If substrate is absorbing, we should account for absorption in the substrate volume?

    # Standard formula T_total = T_front * T_back * exp(-alpha*d) / (1 - R_front_back * R_back * exp...)

    # Here we assume transparent substrate logic (exp terms = 1) but capable of handling n complex.

    # If thick absorbing substrate, T_total goes to 0 independently.

    # For now, keeping logic "incoherent sum" unmodified except for types.

    denom_incoh = 1.0 - R_prime * R_sub

    if abs(denom_incoh) < 1e-12:
        denom_incoh = 1e-12

    # T_total = (T_front * T_sub) / (1 - R' * R_sub)

    T_total = (T_front * T_sub) / denom_incoh

    # R_total = R_front + (T_front * T_prime * R_sub) / (1 - R' * R_sub)

    # T_prime = (4 Re(n0) Re(ns)) / |D'|^2.

    # D' is Y' = ns*B' + C'. D is Y = n0*B + C.

    # B' = cp + M01, C' = M10 + cp. B = cp + M01*ns, C = M10 + cp*ns.

    # For lossless films, |D|=|D'|. Absorption breaks this?

    # Let's verify T_prime calculate to be safe.

    # T_prime (Sub -> Air)

    # T' = 4 * Re(1) * Re(ns) / |Y'|^2 = 4 * ns.real / Yp_mag_sq

    T_prime = 4.0 * ns.real / Yp_mag_sq

    R_back_contribution = (T_front * T_prime * R_sub) / denom_incoh

    R_total = R_front + R_back_contribution

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total


# ─── LOCKED ─── Delegates to calculate_transmission_single (R′ at denominator) ───


# Former version erroneously used 1 - R_front·R_back instead of 1 - R′·R_sub (see file header).


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_reflection_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: float,
) -> float:

    if not np.isfinite(n_sub) or n_sub < 1.0:
        return np.nan

    _rf, _t_tot = calculate_transmission_single(wavelength, n_film_real, n_film_imag, thickness_nm, complex(n_sub, 0.0))

    if not np.isfinite(_rf):
        return np.nan

    return max(0.0, min(1.0, _rf))


# ─── LOCKED ─── Vectorized wrapper of calculate_transmission_single ───


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_transmission_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> np.ndarray:

    n_pts = len(wavelengths)

    T_array = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        _r, T_array[i] = calculate_transmission_single(
            wavelengths[i], n_array[i], k_array[i], thickness, complex(n_substrate[i], 0.0)
        )

    return T_array


# ─── LOCKED ─── Vectorized wrapper of calculate_transmission_single ───


# Macleod convention (+1j, n-ik) + backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_backside_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Fused R_front + T_with_backside for monolayer over full spectrum.

    2x faster than separate  + .

    CRITICAL PHYSICS NOTE:

    This vectorized wrapper returns Standard Mode results (Transparent substrate).

    Measurements INCLUDE backside reflection.

    """

    n_pts = len(wavelengths)

    R_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    T_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        R_arr[i], T_arr[i] = calculate_transmission_single(
            wavelengths[i], n_array[i], k_array[i], thickness, complex(n_substrate[i], 0.0)
        )

    return R_arr, T_arr


# =============================================================================


# Batch single-layer TMM kernels for PGlobal evaluate_batch optimization.
# Fuses N spectra × n_pix TMM + MSE into one prange, eliminating N separate
# Python→Numba dispatches. ~20-30% faster than N sequential array calls.


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def batch_single_layer_T_mse(
    wavelengths,
    n_sub,
    w,
    inv_npix,
    t_exp,
    n_batch,
    k_batch,
    d_batch,
):
    """N spectra T-MSE in one prange(N). Each thread computes a full spectrum."""
    N = n_batch.shape[0]
    n_pix = wavelengths.shape[0]
    mse_out = np.empty(N, dtype=np.float64)
    for i in prange(N):
        acc = 0.0
        d_i = d_batch[i]
        for j in range(n_pix):
            _r, t_th = calculate_transmission_single(
                wavelengths[j], n_batch[i, j], k_batch[i, j], d_i, complex(n_sub[j], 0.0)
            )
            e = t_exp[j] - t_th
            acc += w[j] * e * e
        mse_out[i] = acc * inv_npix
    return mse_out


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def batch_single_layer_RT_mse(
    wavelengths,
    n_sub,
    w,
    inv_npix,
    t_exp,
    r_exp,
    n_batch,
    k_batch,
    d_batch,
    wt,
    wr,
):
    """N spectra fused R+T MSE in one prange(N)."""
    N = n_batch.shape[0]
    n_pix = wavelengths.shape[0]
    wsum = wt + wr
    mse_out = np.empty(N, dtype=np.float64)
    for i in prange(N):
        acc_t = 0.0
        acc_r = 0.0
        d_i = d_batch[i]
        for j in range(n_pix):
            r_th, t_th = calculate_transmission_single(
                wavelengths[j], n_batch[i, j], k_batch[i, j], d_i, complex(n_sub[j], 0.0)
            )
            e_t = t_exp[j] - t_th
            acc_t += w[j] * e_t * e_t
            e_r = r_exp[j] - r_th
            acc_r += w[j] * e_r * e_r
        mse_out[i] = (wt * acc_t + wr * acc_r) * inv_npix / wsum
    return mse_out


# =============================================================================


# ABSORBING SUBSTRATE - Beer-Lambert incoherent model


# =============================================================================


# Formulas (film + thick absorbing substrate of physical thickness D_nm):


#   alpha = 4π·k_sub / lambda_nm          (absorption coefficient, nm⁻¹)


#   att1 = exp(-alpha·D_nm)           (single-pass attenuation)


#   att2 = att1²                  (double-pass)


#   denom = 1 - R′_front · R_back · att2


#   R_total = R_front + T_front · T_prime · R_back · att2 / denom


#   T_total = T_front · T_back  · att1             / denom


#


# For the bare substrate reference (n_sub, k_sub arrays; symmetric interfaces):


#   R_f = |(1-ns)/(1+ns)|², T_f = 1 - R_f, R_b = R_f, T_b = T_f


#


# For film+substrate: R_front/T_front/R_prime come from the coherent TMM


# (same as ); backside is bare Fresnel.


# =============================================================================


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _calculate_RT_absorbing_sub_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub_real: float,
    k_sub: float,
    D_sub_nm: float,
) -> tuple[float, float]:
    """Scalar: R+T for one layer on absorbing substrate (Beer-Lambert incoherent)."""

    if not np.isfinite(n_sub_real) or n_sub_real < 1.0:
        return np.nan, np.nan

    ns = complex(n_sub_real, 0.0)  # substrate optical index (real part only for TMM)

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # --- Forward: Air -> Film -> Sub ---

    B = cp + M01 * ns

    C = M10 + cp * ns

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (R_prime for denom) ---

    Bp = cp + M01

    Cp = M10 + cp

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0

        T_prime = 0.0

    else:
        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq

        T_prime = 4.0 * ns.real / Yp_mag_sq

    # --- Backside interface Sub|Air (bare Fresnel, real ns for interface) ---

    r_b = (n_sub_real - 1.0) / (n_sub_real + 1.0)

    R_back = r_b * r_b

    T_back = 1.0 - R_back

    # --- Beer-Lambert attenuation through substrate bulk ---

    alpha = 4.0 * math.pi * k_sub / wavelength  # nm⁻¹

    att1 = math.exp(-alpha * D_sub_nm)  # single-pass

    att2 = att1 * att1  # double-pass

    denom = 1.0 - R_prime * R_back * att2

    if abs(denom) < 1e-12:
        denom = 1e-12

    R_total = R_front + (T_front * T_prime * R_back * att2) / denom

    T_total = (T_front * T_back * att1) / denom

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_single_layer_absorbing_substrate_array(
    wavelengths: np.ndarray,
    n_array: np.ndarray,
    k_array: np.ndarray,
    thickness: float,
    n_substrate: np.ndarray,
    k_substrate: np.ndarray,
    D_sub_nm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """

    R + T for a single film on an absorbing substrate (Beer-Lambert incoherent backside).

    Args:

        wavelengths   : wavelengths in nm

        n_array       : film refractive index

        k_array       : film extinction coefficient

        thickness     : film thickness in nm

        n_substrate  : substrate real refractive index (per wavelength)

        k_substrate  : substrate extinction coefficient (per wavelength)

        D_sub_nm      : physical substrate thickness in nm

    """

    n_pts = len(wavelengths)

    R_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    T_arr = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        R_arr[i], T_arr[i] = _calculate_RT_absorbing_sub_single(
            wavelengths[i],
            n_array[i],
            k_array[i],
            thickness,
            n_substrate[i],
            k_substrate[i],
            D_sub_nm,
        )

    return R_arr, T_arr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_bare_substrate_R_absorbing(
    wavelengths: np.ndarray,
    n_substrate: np.ndarray,
    k_substrate: np.ndarray,
    D_nm: float,
) -> np.ndarray:
    """

    Reference reflectance of a bare absorbing substrate - double face, with absorption.

    R_sub = R_f + T_f²·R_f·att2 / (1 - R_f²·att2). Used for R/Tnu when k_sub ≠ 0.

    """

    n_pts = len(wavelengths)

    R = np.empty(n_pts, dtype=wavelengths.dtype)

    for i in prange(n_pts):
        ns = n_substrate[i]

        k_s = k_substrate[i]

        r = (1.0 - ns) / (1.0 + ns)

        R_f = r * r

        T_f = 1.0 - R_f

        alpha = 4.0 * math.pi * k_s / wavelengths[i]

        att2 = math.exp(-2.0 * alpha * D_nm)

        denom = 1.0 - R_f * R_f * att2

        if abs(denom) < 1e-12:
            denom = 1e-12
