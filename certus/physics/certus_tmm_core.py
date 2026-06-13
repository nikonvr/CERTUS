SMALL_EPSILON = 1e-12
import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_kernels import compute_TMM_generic, compute_RT_from_matrix, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI


# OPTICAL CALCULATIONS (TMM)


# =============================================================================


# ─── LOCKED ─── Substrate physics validated manually ───


# Incoherent backside formula R_total = 2R/(1+R). DO NOT MODIFY.


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


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_TMM_single_point_k0_exact(
    k0: float, thicknesses: np.ndarray, n_layers_complex: np.ndarray, n_sub: complex
) -> tuple[float, float, float]:
    """

    Computes Rf (Air->Sub), Tf, and Rb (Sub->Air) for a multilayer stack.

    CAPITAL CONVENTION: index 0 = layer 1 = layer closest to the substrate.

    Rb = stack reflectance seen from the substrate. Exact incoherent backside.

    """

    n0 = 1.0  # Air

    n_layers = len(thicknesses)

    I_VAL = +1j

    # Forward Air->Sub: M = L_{N-1} ... L_0 (index 0 = substrate side)

    M00 = complex(1, 0)

    M01 = complex(0, 0)

    M10 = complex(0, 0)

    M11 = complex(1, 0)

    # Backward Sub->Air: Mb = L_0 ... L_{N-1} (meme ordre physique, sens inverse)

    Mb00 = complex(1, 0)

    Mb01 = complex(0, 0)

    Mb10 = complex(0, 0)

    Mb11 = complex(1, 0)

    for i in range(n_layers):
        nc = n_layers_complex[i]

        # ── GARDE-FOU n-ik ──

        if nc.imag > 0.0:
            nc = nc.real - 1j * nc.imag

        phi = k0 * nc * thicknesses[i]

        cp = np.cos(phi)

        isp = I_VAL * np.sin(phi)

        m01 = isp / nc if abs(nc) > 1e-12 else 0.0j

        m10 = isp * nc

        # Forward: M_new = L @ M_old (index 0 = substrate side)

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        # Backward: Mb_new = Mb_old @ L (Sub->Air, L_0 substrate side)

        tb00 = Mb00 * cp + Mb01 * m10

        tb01 = Mb00 * m01 + Mb01 * cp

        tb10 = Mb10 * cp + Mb11 * m10

        tb11 = Mb10 * m01 + Mb11 * cp

        M00, M01, M10, M11 = t00, t01, t10, t11

        Mb00, Mb01, Mb10, Mb11 = tb00, tb01, tb10, tb11

    # --- Front (Air -> Sub): delegate to helper ---

    n_air = complex(n0)

    Rf, Tf = compute_RT_from_matrix(M00, M01, M10, M11, n_air, n_sub)

    # --- Back Reflection (Sub -> Air): delegate to helper ---

    Rb, _ = compute_RT_from_matrix(Mb00, Mb01, Mb10, Mb11, n_sub, n_air)

    return Rf, Tf, Rb


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Exact incoherent backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _apply_exact_backside_generic(
    R_front: np.ndarray,
    T_front: np.ndarray,
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_sub_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Exact incoherent backside for generic multilayer (no back coating).

    Computes R' (Sub -> Stack -> Air) via compute_TMM_generic with reversed arrays.

    TMM convention: L_0 = adjacent to EXIT medium -> reverse for Sub->Air direction.

    """

    n = len(wls)

    R_total = np.empty(n, dtype=R_front.dtype)

    T_total = np.empty(n, dtype=T_front.dtype)

    d_rev = thicknesses[::-1].copy()

    for i in prange(n):
        k0 = TWO_PI / wls[i]

        n_s = n_sub_all_wls[i]

        # Check for absorbing substrate (infinite thickness assumption)

        if abs(n_s.imag) > 1e-8:
            # Absorbing substrate: Light doesn't reach back interface / doesn't return

            R_total[i] = R_front[i]

            T_total[i] = 0.0

            continue

        n_air = complex(1.0)

        # R' = Sub -> Stack -> Air (reversed arrays, swapped media)

        n_rev_i = n_layers_all_wls[i, ::-1].copy() if n_layers_all_wls.ndim > 1 else n_layers_all_wls[i : i + 1]

        R_prime, _ = compute_TMM_generic(k0, d_rev, n_rev_i, n_s, n_air)

        # Uncoated back: substrate/Air interface

        n_s_real = np.real(n_s)

        r_b = (n_s_real - 1.0) / (n_s_real + 1.0)

        R_sub = r_b * r_b

        T_sub = 1.0 - R_sub

        # Exact incoherent combination

        D = 1.0 - R_prime * R_sub

        if D < 1e-12:
            D = 1e-12

        T_total[i] = (T_front[i] * T_sub) / D

        R_total[i] = R_front[i] + (T_front[i] * T_front[i] * R_sub) / D

        # Clamp

        if T_total[i] < 0.0:
            T_total[i] = 0.0

        elif T_total[i] > 1.0:
            T_total[i] = 1.0

        if R_total[i] < 0.0:
            R_total[i] = 0.0

        elif R_total[i] > 1.0:
            R_total[i] = 1.0

    return R_total, T_total


# ─── LOCKED ─── Validated by test_tmm_coherence.py (test_multilayer_cross_comparison) ───


# Macleod convention (+1j). Generic multilayer wrapper with backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_with_backside_fused(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_sub_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate R/T for multilayer stack WITH EXACT backside correction in a single pass."""
    n_wls = len(wls)
    k0_arr = TWO_PI / wls
    R_total = np.empty(n_wls, dtype=wls.dtype)
    T_total = np.empty(n_wls, dtype=wls.dtype)
    d_rev = thicknesses[::-1].copy()

    for i in prange(n_wls):
        k0 = k0_arr[i]
        n_s = n_sub_all_wls[i]
        n_air = complex(1.0)

        # 1. Front calculation (Air -> Stack -> Sub)
        Rf, Tf = compute_TMM_single_point_k0(k0, thicknesses, n_layers_all_wls[i], n_s)

        # 2. Backside correction
        if abs(n_s.imag) > 1e-8:
            # Absorbing substrate: Light doesn't reach back interface / doesn't return
            R_total[i] = Rf
            T_total[i] = 0.0
            continue

        # R' = Sub -> Stack -> Air (reversed arrays, swapped media)
        n_rev_i = n_layers_all_wls[i, ::-1].copy() if n_layers_all_wls.ndim > 1 else n_layers_all_wls[i : i + 1]
        R_prime, _ = compute_TMM_generic(k0, d_rev, n_rev_i, n_s, n_air)

        # Uncoated back: substrate/Air interface
        n_s_real = np.real(n_s)
        r_b = (n_s_real - 1.0) / (n_s_real + 1.0)
        R_sub = r_b * r_b
        T_sub = 1.0 - R_sub

        # Exact incoherent combination
        D = 1.0 - R_prime * R_sub
        if D < 1e-12:
            D = 1e-12

        T_tot = (Tf * T_sub) / D
        R_tot = Rf + (Tf * Tf * R_sub) / D

        # Clamp
        if T_tot < 0.0:
            T_tot = 0.0
        elif T_tot > 1.0:
            T_tot = 1.0

        if R_tot < 0.0:
            R_tot = 0.0
        elif R_tot > 1.0:
            R_tot = 1.0

        T_total[i] = T_tot
        R_total[i] = R_tot

    return R_total, T_total


def calculate_RT_vectorized_real(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,  # (n_wls, n_layers) complex
    n_substrate_all_wls: np.ndarray,  # (n_wls,) complex
    wls: np.ndarray,
    with_backside: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate R/T for multilayer stack with optional EXACT backside correction.

    Args:
        thicknesses: Layer thicknesses array (index 0 = substrate-side)
        n_layers_all_wls: Complex refractive clues (n_wls, n_layers)
        n_substrate_all_wls: substrate complex refractive clues (n_wls,)
        wls: Wavelength array
        with_backside: Apply incoherent backside correction (default True)

    Returns:
        R, T arrays"""

    if with_backside:
        return calculate_RT_with_backside_fused(thicknesses, n_layers_all_wls, n_substrate_all_wls, wls)
    else:
        return calculate_RT_no_backside(thicknesses, n_layers_all_wls, n_substrate_all_wls, wls)


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). index 0 = substrate. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_no_backside(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_substrate_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Calculate R/T WITHOUT backside correction.

    Output dtype matches input wls dtype (f32 in -> f32 out).

    """

    n_wls = len(wls)

    k0_arr = TWO_PI / wls

    R_arr = np.empty(n_wls, dtype=wls.dtype)

    T_arr = np.empty(n_wls, dtype=wls.dtype)

    for i in prange(n_wls):
        R, T = compute_TMM_single_point_k0(k0_arr[i], thicknesses, n_layers_all_wls[i], n_substrate_all_wls[i])

        R_arr[i] = R

        T_arr[i] = T

    return R_arr, T_arr


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). Front-only (no backside). DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calc_spectrum_front(
    wls: np.ndarray, d_layers: np.ndarray, n_layers: np.ndarray, n_sub: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """

    Calculates front R/T (vectorized) - NO backside correction.

    CRITICAL PHYSICS NOTE:

    This function INTENTIONALLY returns Front-Only spectrum.

    Used for:

    - Oblique mode (handled separately)

    - Single-interface components

    - Frosted glass Front

    DO NOT ADD BACKSIDE REFLECTION HERE.

    """

    # Use no_backside version to match OLD behavior

    R, T = calculate_RT_no_backside(d_layers, n_layers, n_sub, wls)

    # OLD returns (T, R), so we return (T, R) for compatibility

    return T, R


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). Front+Back without backside (caller handles it). DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calc_spectrum_full(
    wls: np.ndarray,
    d_front: np.ndarray,
    n_front: np.ndarray,
    d_back: np.ndarray,
    n_back: np.ndarray,
    n_sub: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Calculates Front/Back R/T WITHOUT backside correction.

    Caller must apply incoherent formula: T = (Tf*Tb)/(1-Rf*Rb)

    """

    # Front side (no backside correction - caller handles it)

    Rf, Tf = calculate_RT_no_backside(d_front, n_front, n_sub, wls)

    # Back side (no backside correction)

    Rb, Tb = calculate_RT_no_backside(d_back, n_back, n_sub, wls)

    return Rf, Tf, Rb, Tb


# ─── LOCKED ─── Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). Full-stack reference + exact backside. DO NOT MODIFY without re-running the tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calc_spectrum_full_exact(
    wls: np.ndarray,
    d_front: np.ndarray,
    n_front: np.ndarray,
    d_back: np.ndarray,
    n_back: np.ndarray,
    n_sub: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Exact inconsistent backside calculation for Front + Back stacks.

    CRITICAL PHYSICS NOTE:

    This is the REFERENCE IMPLEMENTATION for full-stack physics with backside.

    It computes the exact incoherent interaction (Fabry-Perot intensity summation).

    T_total = (Tf * Tb) / (1 - Rf' * Rb')

    DO NOT MODIFY THIS LOGIC.

    IMPORTANT AGREEMENT:

    Layer clues [0, 1, ..., N-1] correspond to physical layers starting FROM THE SUBSTRATE.

    Index 0 is ALWAYS the layer adjacent to the substrate.

    Index N-1 is always the layer adjacent to the Air.

    Returns:

        Rf: Front stack R (Air -> Front -> Sub)

        Tf: Front stack T (Air -> Front -> Sub)

        Rf_prime: Front stack R from substrate side (Sub -> Front -> Air)

        Rb_prime: Back stack R from substrate side (Sub -> Back -> Air)

        Tb: Back stack T from substrate side (Sub -> Back -> Air)

    Caller uses exact formula:

        denom = 1 - Rf_prime * Rb_prime

        T_total = (Tf * Tb) / denom"""

    n_wls = len(wls)

    # --- Air-incidence: front only ---

    Rf, Tf = calculate_RT_no_backside(d_front, n_front, n_sub, wls)

    # --- substrate-incidence calculations ---

    # TMM convention: L_0 = adjacent to EXIT medium.

    # Forward (Air->Sub): L_0 = sub-side -> correct with original arrays.

    # Reverse (Sub->Air): EXIT = air, so L_0 must be air-side -> REVERSE arrays.

    d_front_rev = d_front[::-1].copy()

    d_back_rev = d_back[::-1].copy()

    Rf_prime = np.empty(n_wls, dtype=np.float64)

    Rb_prime = np.empty(n_wls, dtype=np.float64)

    Tb = np.empty(n_wls, dtype=np.float64)

    for i in prange(n_wls):
        k0 = TWO_PI / wls[i]

        n_s = n_sub[i]

        n_air = complex(1.0)

        # Front reversed: Sub -> Front -> Air

        n_front_rev_i = n_front[i, ::-1].copy() if n_front.ndim > 1 else n_front[i : i + 1]

        Rf_p, _ = compute_TMM_generic(k0, d_front_rev, n_front_rev_i, n_s, n_air)

        Rf_prime[i] = Rf_p

        # Back reversed: Sub -> Back -> Air (R and T)

        n_back_rev_i = n_back[i, ::-1].copy() if n_back.ndim > 1 else n_back[i : i + 1]

        Rb_p, Tb_i = compute_TMM_generic(k0, d_back_rev, n_back_rev_i, n_s, n_air)

        Rb_prime[i] = Rb_p

        Tb[i] = Tb_i

    return Rf, Tf, Rf_prime, Rb_prime, Tb


# Wrappers


# Wrappers ensuring (n, d) usage from App matches (d, n) in Kernel


def calc_spectrum_front_wrapper(wls, n, d, ns):
    """Refactored wrapper: accepts (wls, n, d, ns) -> calls kernel (wls, d, n, ns)"""

    return calc_spectrum_front(wls, d, n, ns)


def calc_spectrum_full_wrapper(wls, nf, df, ns, nb, db):
    """Refactored wrapper: accepts (wls, n_f, d_f, n_sub, n_b, d_b) -> calls kernel"""

    # Kernel expects: (wls, d_front, n_front, d_back, n_back, n_sub)

    return calc_spectrum_full(wls, df, nf, db, nb, ns)


def calc_spectrum_full_exact_wrapper(wls, nf, df, ns, nb, db):
    """Exact wrapper: accepts (wls, n_f, d_f, n_sub, n_b, d_b) -> calls exact kernel"""

    # Kernel expects: (wls, d_front, n_front, d_back, n_back, n_sub)

    return calc_spectrum_full_exact(wls, df, nf, db, nb, ns)


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


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def apply_exact_backside_combination(
    Rf: np.ndarray, Tf: np.ndarray, Rb_stack: np.ndarray, n_sub: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """

    Combines Front Stack properties with Backside Interface (Air) using EXACT incoherent formula.

    CRITICAL PHYSICS NOTE:

    This function implements the Incoherent Cavity Model.

    Reflectance R = R_front + (T_front^2 * R_back) / (1 - R_front_mirror * R_back_mirror)

    Transmission T = (T_front * T_back) / (1 - R_front_mirror * R_back_mirror)

    DO NOT SIMPLIFY TO R_front + R_back.

    Args:

        Rf: Front stack reflection (Air -> Stack -> Sub)

        Tf: Front stack transmission (Air -> Stack -> Sub)

        Rb_stack: Front stack reflection FROM SUBSTRATE (Sub -> Stack -> Air)

        n_sub: substrate refractive index

    Returns:

        R_total, T_total

    NOTE: Assumes REAL substrate index (Non-absorbing). Forces np.real(n_sub).

    """

    n = len(Rf)

    R_total = np.empty(n, dtype=Rf.dtype)

    T_total = np.empty(n, dtype=Tf.dtype)

    for i in prange(n):
        n_s = np.real(n_sub[i])

        # 1. Back Interface (substrate | Air) Reflection

        # r = (ns - 1)/(ns + 1)

        r_back = (n_s - 1.0) / (n_s + 1.0)

        R_sub_air = r_back * r_back

        T_sub_air = 1.0 - R_sub_air

        # 2. Incoherent Cavity Formula

        # Cavity is the substrate.

        # Front Mirror: Stack (Reflectance Rb_stack looking from substrate)

        # Back Mirror: Sub/Air Interface (Reflectance R_sub_air looking from substrate)

        # Denominator = 1 - R_back_mirror * R_front_mirror

        denom = 1.0 - R_sub_air * Rb_stack[i]

        if denom < 1e-12:
            denom = 1e-12

        # T_total = T_front_stack * T_back_interface / denom

        T_total[i] = (Tf[i] * T_sub_air) / denom

        # R_total = R_front_stack + (T_front_stack^2 * R_back_interface) / denom

        R_total[i] = Rf[i] + (Tf[i] * Tf[i] * R_sub_air) / denom

        # Clamp

        if T_total[i] < 0.0:
            T_total[i] = 0.0

        elif T_total[i] > 1.0:
            T_total[i] = 1.0

        if R_total[i] < 0.0:
            R_total[i] = 0.0

        elif R_total[i] > 1.0:
            R_total[i] = 1.0

    return R_total, T_total


# --- LOCKED --- Validated by test_tmm_coherence.py (test_analytical_hlh, test_vectorized_vs_reference) ───


# Macleod convention (+1j). Delegates to calculate_RT_no_backside. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _calculate_RT_HL_core(
    wls: np.ndarray,
    nH: np.ndarray,
    nL: np.ndarray,
    nSub: np.ndarray,
    thicknesses: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Core TMM calculationation for alternating H/L stacks (front surface only).

    Index array dtype matches input nH dtype (f32 -> c64, f64 -> c128)."""

    n_wls = len(wls)

    n_layers = len(thicknesses)

    # Always use double precision (complex128)

    n_layers_complex = np.empty((n_wls, n_layers), dtype=np.complex128)

    # Parallel index array construction

    for i in prange(n_wls):
        valH = nH[i]

        valL = nL[i]

        for j in range(n_layers):
            if j % 2 == 0:
                n_layers_complex[i, j] = valH

            else:
                n_layers_complex[i, j] = valL

    return calculate_RT_no_backside(thicknesses, n_layers_complex, nSub, wls)


# --- LOCKED --- Validated by test_tmm_coherence.py (test_vectorized_vs_reference) ───


# Macleod convention (+1j). HL wrapper with backside. DO NOT MODIFY without running tests.


def calculate_RT_vectorized_real_HL(
    wls: np.ndarray,
    nH: np.ndarray,
    nL: np.ndarray,
    nSub: np.ndarray,
    thicknesses: np.ndarray,
    with_backside: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Wrapper for alternating H/L stacks with optional backside correction.

    Assumes layer 0 is H, layer 1 is L, etc.

    Args:

        wls: Wavelength array

        nH: High index material n(lambda)

        nL: Low index material n(lambda)

        nSub: substrate n(lambda)

        thicknesses: Layer thicknesses

                     IMPORTANT: Index 0 is the layer AGAINST THE SUBSTRATE.

                     This function assumes alternating H/L layers starting with H at index 0 (sub-side).

        with_backside: If True, apply incoherent backside correction (default True)

    Returns:

        R, T arrays

    CRITICAL PHYSICS NOTE:

    This function controls the Strategy Engines view of the world.

    - with_backside=True: Standard mode (Glass Plate). Uses exact incoherent sum.

    - with_backside=False: Optimized mode or Special substrates. Front only.

    DO NOT CHANGE THE DEFAULT OR LOGIC BRANCHING.

    """

    if with_backside:
        n_layers = len(thicknesses)
        n_layers_all_wls = np.empty((len(wls), n_layers), dtype=np.complex128)
        for i in range(n_layers):
            if i % 2 == 0:
                n_layers_all_wls[:, i] = nH
            else:
                n_layers_all_wls[:, i] = nL
        nSub_f = np.asarray(nSub, dtype=np.complex128)
        return calculate_RT_with_backside_fused(thicknesses, n_layers_all_wls, nSub_f, wls)

    else:
        # Front surface calculationation only

        Rf, Tf = _calculate_RT_HL_core(wls, nH, nL, nSub, thicknesses)

        return Rf, Tf


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Incoherent HL backside. DO NOT MODIFY without running tests.


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). index 0 = substrate. DO NOT MODIFY without running tests.


# =============================================================================


# =========================================================================================
