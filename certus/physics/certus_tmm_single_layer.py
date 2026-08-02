import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import (
    calculate_single_interface_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_T_absorbing,
)
from .certus_tmm_matrix import compute_complex_phase_components


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

    # Convention Macleod n̂ = n − ik : la partie imaginaire du déphasage est NÉGATIVE.
    # compute_complex_phase_components renvoie cos/sin(φr + i·φi) — soit le conjugué de
    # ce que sa docstring annonce. Les appelants obliques compensent en passant phi.imag
    # déjà signé ; ici n_film_imag arrive positif, d'où le signe explicite.
    # Validé contre tests/oracle/tmm_reference.py (cf. tests/oracle/test_tmm_oracle.py).
    phi_i = -k * n_film_imag * thickness_nm

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
