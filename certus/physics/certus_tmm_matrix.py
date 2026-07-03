import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

from .certus_tmm_substrate import calculate_bare_substrate_R, calculate_bare_substrate_RT, calculate_single_interface_R


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

