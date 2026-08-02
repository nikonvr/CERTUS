import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12


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
