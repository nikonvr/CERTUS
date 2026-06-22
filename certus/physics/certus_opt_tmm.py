SMALL_EPSILON = 1e-12
import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE, get_complex_dtype, FROSTED_GLASS_CAUCHY_A, FROSTED_GLASS_CAUCHY_B
from dataclasses import dataclass
import certus.physics.certus_tmm_core as tmm_core
from certus.physics.certus_optical_models import (
    get_nk_from_spline, get_nk_cauchy_simple, get_nk_cauchy_wrapper,
    sellmeier_n_array, get_nk_cauchy, epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk
)
from scipy.interpolate import CubicSpline

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def clip_to_bounds(x: np.ndarray, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:
    out = np.empty_like(x)
    for i in range(len(x)):
        v = x[i]
        if v < lb[i]:
            out[i] = lb[i]
        elif v > ub[i]:
            out[i] = ub[i]
        else:
            out[i] = v
    return out

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_TMM_generic(
    k0: float,
    thicknesses: np.ndarray,
    n_layers_complex: np.ndarray,
    n_inc: complex,
    n_sub: complex,
) -> tuple[float, float]:
    """Generic TMM for n_inc -> layers -> n_sub.

    Returns (R, T) where T is power transmission into n_sub.

    CAPITAL AGREEMENT:

      - Layer 1 = layer closest to the substrate.

      - index 0 = layer 1 = adjacent to the substrate (EXIT).

      - index N-1 = incident rating (air).

      - M = L_{N-1} * ... * L_0 (pre-multiplication). DO NOT REVERSE.

      - Complex clues: n̂ = n - ik (imag <= 0 for absorption)."""

    M00 = 1.0 + 0.0j

    M01 = 0.0 + 0.0j

    M10 = 0.0 + 0.0j

    M11 = 1.0 + 0.0j

    I_VAL = +1j

    for i in range(len(thicknesses)):
        n_c = n_layers_complex[i]

        # -- SAFEGUARD n-ik: force Macleod convention --

        # If imag > 0 (non-physical gain), we silently correct.

        if n_c.imag > 0.0:
            n_c = n_c.real - 1j * n_c.imag  # n+ik -> n-ik

        phi = k0 * n_c * thicknesses[i]

        cp = np.cos(phi)

        isp = I_VAL * np.sin(phi)  # factor i*sin(phi) once

        if abs(n_c) > 1e-12:
            m01 = isp / n_c

        else:
            m01 = 0.0 + 0.0j

        m10 = isp * n_c

        # M_new = L @ M_old  (cp == L00 == L11, diagonal symmetry)

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    # Delegate to factored helper (single source of truth for R/T extraction)

    return compute_RT_from_matrix(M00, M01, M10, M11, n_inc, n_sub)

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_RT_from_matrix(
    M00: complex,
    M01: complex,
    M10: complex,
    M11: complex,
    n_inc: complex,
    n_exit: complex,
) -> tuple[float, float]:
    """Computes (R, T) from a 2x2 transfer matrix M and boundary media.

    REFERENCE: Macleod 4th ed., eq. 2.96 (semi-infinite substrate).

        R = |r|² where r = (η_inc·B - C) / (η_inc·B + C)

        T = Re(η_exit) / Re(η_inc) · |t|²

              where t = 2·η_inc / (η_inc·B + C)

        [B; C] = M · [1; η_exit]

    CONVENTION: Complex clues MUST follow n̂ = n - ik (k >= 0).

    With n̂ = n + ik, the formula yields R+T > 1 (non-physical gain).

    This is the SINGLE SOURCE OF TRUTH for the R/T extraction formula.

    All TMM functions should delegate to this.

    Args:

        M00, M01, M10, M11: Transfer matrix elements

        n_inc: Complex refractive index of incident medium (n - ik convention)

        n_exit: Complex refractive index of exit medium (n - ik convention)

    Returns:

        (R, T) - power reflectance and transmittance, R+T <= 1 for absorbing layers"""

    B = M00 + M01 * n_exit

    C = M10 + M11 * n_exit

    Y_sys = n_inc * B + C

    if abs(Y_sys) < 1e-14:
        return 0.0, 0.0

    r = (n_inc * B - C) / Y_sys

    R = abs(r) ** 2

    n_inc_real = n_inc.real

    if n_inc_real < 1e-9:
        T = 0.0

    else:
        # T = Re(η_exit) / Re(η_inc) · |t|²

        # |t|² = 4·|η_inc|² / |η_inc·B + C|²

        n_exit_real = n_exit.real

        abs_t_sq = (4.0 * abs(n_inc) ** 2) / (abs(Y_sys) ** 2)

        T = (n_exit_real / n_inc_real) * abs_t_sq

    T = max(0.0, T)

    return R, T

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RTRback_incoherent_vectorized(
    thicknesses: np.ndarray,
    n_layers_all_wls: np.ndarray,
    n_substrate_all_wls: np.ndarray,
    wls: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Calculates R (Front), T, and Rback (Back) for a film on a THICK INCOHERENT substrate.

    """

    n = len(wls)

    R_total = np.empty(n, dtype=np.float64)

    T_total = np.empty(n, dtype=np.float64)

    Rback_total = np.empty(n, dtype=np.float64)

    k0_arr = TWO_PI / wls

    for i in prange(n):
        ns = n_substrate_all_wls[i]  # Complex substrate index

        n_inc_front = 1.0 + 0j

        n_layers = n_layers_all_wls[i]  # Array of complex clues for stack

        # 1. Front Coherent (Air -> Stack -> substrate)

        Rf_coh, Tf_coh = compute_TMM_generic(k0_arr[i], thicknesses, n_layers, n_inc_front, ns)

        if abs(ns.imag) > 1e-8:
            # Absorbing substrate (Infinite): No Backside Reflection

            T_total[i] = 0.0

            R_total[i] = Rf_coh

            Rback_total[i] = 0.0  # Or should it be R_sub (air-sub) only?

            # Convention: Rback is measured from Back (Air->Sub).

            # If sub is absorbing infinite, light sees Air->Sub interface, absorbs, nothing returns from front stack.

            # So Rback = R(Air->Sub)

            # Fresnel Air -> Sub

            n_air = 1.0

            r_as = (n_air - ns) / (n_air + ns)

            Rback_total[i] = abs(r_as) ** 2

            continue

        # 2. Back Coherent Internal (substrate -> Stack -> Air)

        # For back incidence, light comes from substrate.

        # Order of layers is reversed relative to beam.

        # Incident medium = ns, Exit medium = Air (n=1)

        # Reverse layers

        n_layers_rev = n_layers[::-1]  # Numba supports this

        thicknesses_rev = thicknesses[::-1]

        Rb_coh, Tb_coh = compute_TMM_generic(k0_arr[i], thicknesses_rev, n_layers_rev, ns, n_inc_front)

        # 3. substrate Backside Reflection (substrate -> Air)

        # Using Fresnel normal incidence for substrate-air interface

        # r = (ns - 1)/(ns + 1)

        if abs(ns + 1.0) > 1e-12:
            r_sub = (ns - 1.0) / (ns + 1.0)

            R_sub = abs(r_sub) ** 2

        else:
            R_sub = 0.0

        # 4. Incoherent Combination

        # Denom D = 1 - Rb_coh * R_sub

        denom = 1.0 - Rb_coh * R_sub

        if denom < 1e-9:
            denom = 1e-9

        # T_total = (Tf_coh * (1 - R_sub)) / D

        T_total[i] = (Tf_coh * (1.0 - R_sub)) / denom

        # R_total (Front Measured)

        # R = Rf_coh + (Tf_coh^2 * R_sub) / D ?

        # Standard: R_tot = R_front + (T_front * T_back * R_back_interface) / (1 - R_back_stack * R_back_interface)

        # T_front = Tf_coh, T_back = Tb_coh. reciprocity Tf=Tb in power?

        # Yes T_front = T_back usually.

        # Here we use Tf_coh * Tb_coh just to be safe or Tf_coh^2.

        R_total[i] = Rf_coh + (Tf_coh * Tb_coh * R_sub) / denom

        # Rback_total (Back Measured)

        # Light incident from Air (Back) -> substrate -> Stack -> Air (Front)

        # Interface 1: Air->substrate (R_sub)

        # Interface 2: substrate->Stack (Rb_coh)

        # R_back_tot = R_sub + ( (1-R_sub)*(1-R_sub) * Rb_coh ) / (1 - R_sub * Rb_coh)

        # Note R of Air->substrate is same as substrate->Air (R_sub)

        Rback_total[i] = R_sub + ((1.0 - R_sub) ** 2 * Rb_coh) / denom

    return R_total, T_total, Rback_total

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_reflection_infinite_substrate_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> float:
    """

    Calculate reflection for a thin film on INFINITE substrate (Frosted Glass).

    CRITICAL PHYSICS NOTE:

    Infinite substrate assumption = NO BACKSIDE REFLECTION.

    R = Front Surface Reflection Only.

    Any backside terms here would be physically invalid for rough/absorbing backsides.

    DO NOT ADD BACKSIDE TERMS.

    """

    if not np.isfinite(n_sub.real) or n_sub.real < 1.0:
        return np.nan

    n0 = N_SUPERSTRATE  # Air

    k = TWO_PI / wavelength

    # Complex phase in the film

    phi_r = k * n_film_real * thickness_nm

    phi_i = k * n_film_imag * thickness_nm

    # Complex exponential

    exp_pos = np.exp(-phi_i)

    exp_neg = np.exp(phi_i)

    cos_phi_r = np.cos(phi_r)

    sin_phi_r = np.sin(phi_r)

    cos_phi_real = cos_phi_r * (exp_pos + exp_neg) / 2.0

    cos_phi_imag = sin_phi_r * (exp_neg - exp_pos) / 2.0

    sin_phi_real = sin_phi_r * (exp_pos + exp_neg) / 2.0

    sin_phi_imag = cos_phi_r * (exp_pos - exp_neg) / 2.0

    # Inverse of complex film index

    n_mag_sq = n_film_real * n_film_real + n_film_imag * n_film_imag

    if n_mag_sq < SMALL_EPSILON:
        return np.nan

    inv_n_r = n_film_real / n_mag_sq

    inv_n_i = n_film_imag / n_mag_sq

    # Transfer matrix elements (Macleod: -i * sin / n,  -i * n * sin)

    M00_real = cos_phi_real

    M00_imag = cos_phi_imag

    M01_real = inv_n_r * sin_phi_imag + inv_n_i * sin_phi_real

    M01_imag = -(inv_n_r * sin_phi_real - inv_n_i * sin_phi_imag)

    M10_real = n_film_real * sin_phi_imag + n_film_imag * sin_phi_real

    M10_imag = -(n_film_real * sin_phi_real - n_film_imag * sin_phi_imag)

    M11_real = cos_phi_real

    M11_imag = cos_phi_imag

    # substrate complex index

    ns_r = n_sub.real

    ns_i = n_sub.imag

    # Term n_sub * M01

    nsM01_r = ns_r * M01_real - ns_i * M01_imag

    nsM01_i = ns_r * M01_imag + ns_i * M01_real

    # Term n_sub * M11

    nsM11_r = ns_r * M11_real - ns_i * M11_imag

    nsM11_i = ns_r * M11_imag + ns_i * M11_real

    # Denominator: n0*B + C where B = M00+ns*M01, C = M10+ns*M11

    # B = M00 + nsM01

    B_r = M00_real + nsM01_r

    B_i = M00_imag + nsM01_i

    # C = M10 + nsM11

    C_r = M10_real + nsM11_r

    C_i = M10_imag + nsM11_i

    # Denom = n0 * B + C

    denom_real = n0 * B_r + C_r

    denom_imag = n0 * B_i + C_i

    denom_mag_sq = denom_real * denom_real + denom_imag * denom_imag

    if denom_mag_sq < SMALL_EPSILON:
        return np.nan

    # Numerator: n0*B - C (standard Macleod)

    num_r_real = n0 * B_r - C_r

    num_r_imag = n0 * B_i - C_i

    # Amplitude reflection coefficient

    r_real = (num_r_real * denom_real + num_r_imag * denom_imag) / denom_mag_sq

    r_imag = (num_r_imag * denom_real - num_r_real * denom_imag) / denom_mag_sq

    # Reflectance (intensity)

    R = r_real * r_real + r_imag * r_imag

    return max(0.0, min(1.0, R))

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_reflectance_bilayer_vectorized(
    l_array, nM_complex_array, eM_phys, eL_phys, nL_complex_array, nSub_complex_array
):
    """

    Calculate reflectance for Metal|SiO2|Si structure using scalarized TMM.

    Structure: Air | Metal (eM) | SiO2 (eL) | Si (substrate)

    CRITICAL PHYSICS NOTE:

    Assumes Opaque/Infinite substrate behavior (Front Surface Only).

    This is specific to Metal Bilayer monitoring on typically absorbing or rough wafers.

    """

    n_pts = len(l_array)

    n0 = 1.0  # Air

    R_out = np.empty(n_pts, dtype=np.float64)

    for i in prange(n_pts):
        wl = l_array[i]

        k0 = TWO_PI / wl

        # Metal layer matrix: L00=L11=cM (diagonal symmetry)

        nM = nM_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nM.imag > 0.0:
            nM = nM.real - 1j * nM.imag

        phiM = k0 * nM * eM_phys

        cM = np.cos(phiM)

        ispM = +1j * np.sin(phiM)

        m01_M = ispM / nM if abs(nM) > 1e-14 else 0j

        m10_M = ispM * nM

        # SiO2 layer matrix: L00=L11=cL (diagonal symmetry)

        nL = nL_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nL.imag > 0.0:
            nL = nL.real - 1j * nL.imag

        phiL = k0 * nL * eL_phys

        cL = np.cos(phiL)

        ispL = +1j * np.sin(phiL)

        m01_L = ispL / nL if abs(nL) > 1e-14 else 0j

        m10_L = ispL * nL

        # Combined matrix M_total = M_metal * M_sio2 (cM,cL on diagonals)

        Mt00 = cM * cL + m01_M * m10_L

        Mt01 = cM * m01_L + m01_M * cL

        Mt10 = m10_M * cL + cM * m10_L

        Mt11 = m10_M * m01_L + cM * cL

        # Reflection coefficient

        nS = nSub_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nS.imag > 0.0:
            nS = nS.real - 1j * nS.imag

        term1 = n0 * (Mt00 + nS * Mt01)

        term2 = Mt10 + nS * Mt11

        num = term1 - term2

        den = term1 + term2

        r = num / den if abs(den) > 1e-20 else 0j

        R = (r.real * r.real) + (r.imag * r.imag)  # |r|^2

        if R < 0.0:
            R = 0.0

        elif R > 1.0:
            R = 1.0

        R_out[i] = R

    return R_out

@dataclass(slots=True)
class Material:
    """Material with Cauchy model (slots=True for reduced RAM)"""

    n4: float  # n @ 400nm

    n7: float  # n @ 700nm

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        """Calculates n(lambda) via Cauchy model with precision support"""

        wls_arr = np.asarray(wls, dtype=np.float64)

        # Use wrapper handling precision

        n_real = get_nk_cauchy_wrapper(float(self.n4), float(self.n7), wls_arr)

        # Convert to complex with configured precision

        complex_dtype = get_complex_dtype()

        return n_real.astype(complex_dtype)

    def get_n_at_wavelength(self, wl: float) -> float:
        """Returns n at specific wavelength"""

        result = self.get_nk(np.array([wl], dtype=np.float64))

        return float(result[0].real)

@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def get_n_frosted_glass_array(wavelengths_nm: np.ndarray) -> np.ndarray:
    """Calculate frosted glass refractive index for an array of wavelengths."""

    n = len(wavelengths_nm)

    result = np.empty(n, dtype=wavelengths_nm.dtype)

    for i in prange(n):
        result[i] = FROSTED_GLASS_CAUCHY_A + FROSTED_GLASS_CAUCHY_B / (wavelengths_nm[i] * wavelengths_nm[i])

    return result

def arange_inclusive(start: float, stop: float, step: float, decimals: int = WL_DECIMALS) -> np.ndarray:
    """

    Generates array with stop INCLUDED (unlike np.arange).

    """

    if step <= 0:
        raise ValueError("Step must be positive")

    n = int(np.floor((stop - start) / step + 1e-9)) + 1

    arr = np.linspace(start, start + (n - 1) * step, n, dtype=np.float64)

    arr = np.round(arr, decimals)

    # Ensure stop is included

    stop_rounded = round(stop, decimals)

    return arr[arr <= stop_rounded + 10 ** (-decimals - 1)]

def trim_worst_only(data: np.ndarray, trim_percent: int = 10) -> np.ndarray:
    """

    Removes X% worst values (for robust stats).

    """

    if len(data) == 0:
        return data

    sorted_data = np.sort(data)

    n = len(sorted_data)

    trim_count = int(n * trim_percent / 100)

    if trim_count > 0 and trim_count < n:
        return sorted_data[:-trim_count]

    return sorted_data