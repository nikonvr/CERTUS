SMALL_EPSILON = 1e-12
import numpy as np
from scipy.interpolate import CubicSpline

from numba import njit, float64, boolean, prange
import math
from functools import lru_cache
from threading import Lock
from certus.core.certus_core import PI


# [MONOLITHIC BLOCK] OPTICAL MODELS


# DO NOT SPLIT - Used by both TMM and Optimization kernels


# =========================================================================================


# =============================================================================


# OPTICAL MODELS


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def sellmeier_n_array(
    wls: np.ndarray,
    B1: float,
    C1: float,
    B2: float,
    C2: float,
    B3: float,
    C3: float,
    min_wl: float,
) -> np.ndarray:

    n = len(wls)

    res = np.empty(n, dtype=np.float64)

    for i in prange(n):
        wl = wls[i]

        if wl < min_wl:
            res[i] = 1.0

        else:
            w = wl / 1000.0

            w2 = w * w

            n2 = 1.0 + B1 * w2 / (w2 - C1) + B2 * w2 / (w2 - C2) + B3 * w2 / (w2 - C3)

            res[i] = np.sqrt(max(n2, 1.0))

    return res


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def get_nk_cauchy(n4: float, n7: float, wls: np.ndarray) -> np.ndarray:

    n_pts = len(wls)

    res = np.empty(n_pts, dtype=np.float64)

    inv_wl1sq = 1.0 / (400.0 * 400.0)

    inv_wl2sq = 1.0 / (700.0 * 700.0)

    denom = inv_wl1sq - inv_wl2sq

    B = (n4 - n7) / denom

    A = n4 - B * inv_wl1sq

    for i in prange(n_pts):
        wl = wls[i]

        if wl < 1.0:
            res[i] = A

        else:
            res[i] = A + B / (wl * wl)

    return res


@lru_cache(maxsize=1024)
def _get_nk_cauchy_cached(n4: float, n7: float, wls_tuple: tuple) -> np.ndarray:
    wls_arr = np.array(wls_tuple, dtype=np.float64)
    return get_nk_cauchy(n4, n7, wls_arr)


def get_nk_cauchy_wrapper(n4: float, n7: float, wls: np.ndarray) -> np.ndarray:
    """Cauchy index wrapper. Returns f64 (double precision)."""
    return _get_nk_cauchy_cached(float(n4), float(n7), tuple(wls.astype(np.float64)))


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def get_nk_cauchy_simple(wavelength_nm, n_infini, A):
    """Cauchy dielectric model: n = n_inf + A/lambda^2 (Used in Metal Bilayer)"""

    return n_infini + A / (wavelength_nm**2)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def epsilon2_TLU_array(E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, Eu: float) -> np.ndarray:

    n = len(E_array)

    result = np.empty(n, dtype=np.float64)

    E0_sq = E0 * E0

    C_sq = C * C

    A_E0_C = A * E0 * C

    delta = 0.01

    E_edge = Eg + delta

    E_edge_sq = E_edge * E_edge

    num_edge = A_E0_C * delta * delta

    den_edge = E_edge * ((E_edge_sq - E0_sq) ** 2 + C_sq * E_edge_sq)

    eps2_at_edge = num_edge / den_edge if den_edge > SMALL_EPSILON else 0.0

    Eu_safe = max(Eu, 1e-6)

    for i in prange(n):
        E = E_array[i]

        if E > Eg:
            E_sq = E * E

            diff = E - Eg

            num = A_E0_C * diff * diff

            den = E * ((E_sq - E0_sq) ** 2 + C_sq * E_sq)

            result[i] = num / den if den > SMALL_EPSILON else 0.0

        else:
            if eps2_at_edge < SMALL_EPSILON:
                result[i] = 0.0

            else:
                arg = (E - Eg - delta) / Eu_safe
                arg_clamped = min(max(arg, -700.0), 700.0)
                result[i] = eps2_at_edge * np.exp(arg_clamped)

    return result


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def epsilon1_TL_analytic(E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float) -> np.ndarray:

    n = len(E_array)

    eps1_array = np.empty(n, dtype=np.float64)

    E0_sq = E0 * E0

    Eg_sq = Eg * Eg

    C_sq = C * C

    gamma_sq = E0_sq - C_sq / 2.0

    alpha = np.sqrt(max(4.0 * E0_sq - C_sq, 1e-12))

    denom_log_norm = np.sqrt((E0_sq - Eg_sq) ** 2 + C_sq * Eg_sq)

    A_E0_C = A * E0 * C

    two_A_E0_C_Eg = 2.0 * A_E0_C * Eg

    inv_PI = 1.0 / PI

    for i in prange(n):
        E = E_array[i]

        E_sq = E * E

        zeta4 = (E_sq - E0_sq) ** 2 + C_sq * E_sq

        if zeta4 < SMALL_EPSILON:
            zeta4 = SMALL_EPSILON

        inv_zeta4 = 1.0 / zeta4

        al = (Eg_sq - E0_sq) * E_sq + Eg_sq * C_sq - E0_sq * (E0_sq + 3.0 * Eg_sq)

        aa = (E_sq - E0_sq) * (E0_sq + Eg_sq) + Eg_sq * C_sq

        term1 = 0.0

        if E > SMALL_EPSILON:
            val_log1 = np.log(np.abs((Eg - E) / (Eg + E)))

            term1 = -A_E0_C * (E_sq + Eg_sq) * inv_PI * inv_zeta4 / E * val_log1

        val_log2 = np.log(np.abs((Eg - E) * (Eg + E)) / denom_log_norm)

        term2 = two_A_E0_C_Eg * inv_PI * inv_zeta4 * val_log2

        arg_log3_num = E0_sq + Eg_sq + alpha * Eg

        arg_log3_den = E0_sq + Eg_sq - alpha * Eg

        term3 = 0.0

        if arg_log3_den > SMALL_EPSILON and alpha > SMALL_EPSILON:
            term3 = (A * C * al) / (2.0 * PI * zeta4 * alpha * E0) * np.log(arg_log3_num / arg_log3_den)

        atan_arg1 = (2.0 * Eg + alpha) / C

        atan_arg2 = (2.0 * Eg - alpha) / C

        term4 = -(A * aa) * inv_PI * inv_zeta4 / E0 * (PI - np.arctan(atan_arg1) - np.arctan(atan_arg2))

        term5 = 0.0

        atan_arg3 = 2.0 * (Eg_sq - gamma_sq) / max(alpha * C, SMALL_EPSILON)

        if alpha > SMALL_EPSILON:
            term5 = (4.0 * A * E0 * Eg * (E_sq - gamma_sq)) / (PI * zeta4 * alpha) * (PI / 2.0 - np.arctan(atan_arg3))

        val = eps_inf + term1 + term2 + term3 + term4 + term5

        eps1_array[i] = max(val, 1.0) if np.isfinite(val) else eps_inf

    return eps1_array


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def epsilon_to_nk(
    eps1: np.ndarray, eps2: np.ndarray, n_min: float, n_max: float, k_max: float
) -> tuple[np.ndarray, np.ndarray, bool]:

    n_pts = len(eps1)

    n_arr = np.empty(n_pts, dtype=np.float64)

    k_arr = np.empty(n_pts, dtype=np.float64)

    is_valid = True

    for i in prange(n_pts):
        e1 = eps1[i]

        e2 = eps2[i]

        eps_mag = np.sqrt(e1 * e1 + e2 * e2)

        n_val = np.sqrt(max((eps_mag + e1) / 2.0, SMALL_EPSILON))

        k_val = np.sqrt(max((eps_mag - e1) / 2.0, 0.0))

        if n_val < n_min or n_val > n_max or k_val > k_max:
            is_valid = False

        n_arr[i] = n_val

        k_arr[i] = k_val

    return n_arr, k_arr, is_valid


# =============================================================================


# SPLINES (Moved from certus_physics.splines to avoid circular imports)


# =============================================================================


class SplineCache:
    """

    Cache for CubicSpline objects to avoid recreation on each call.

    Thread-safe via LRU cache on immutable tuple keys.

    Kept for backward compatibility; prefer SplineBasisCache for optimization loops.

    """

    _instance = None

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super(SplineCache, cls).__new__(cls)

        return cls._instance

    @lru_cache(maxsize=512)
    def _get_splines(self, knot_wl_tuple, n_values_tuple, k_values_tuple):

        knot_wl = np.array(knot_wl_tuple)

        n_vals = np.array(n_values_tuple)

        k_vals = np.array(k_values_tuple)

        spline_n = CubicSpline(knot_wl, n_vals, bc_type="natural", extrapolate=False)

        spline_k = CubicSpline(knot_wl, k_vals, bc_type="natural", extrapolate=False)

        return spline_n, spline_k

    def get_splines(self, knot_wavelengths, n_knot_values, k_knot_values):

        return self._get_splines(
            tuple(knot_wavelengths.round(6)),
            tuple(n_knot_values.round(6)),
            tuple(k_knot_values.round(6)),
        )

    def clear(self):

        self._get_splines.cache_clear()


_spline_cache = SplineCache()


class SplineBasisCache:
    """

    High-performance spline evaluator using pre-computed basis matrices.

    Key insight: in an optimization loop, the knot *positions* (wavelengths)

    and the *target* wavelength grid are fixed. Only the knot *values* (n, k)

    change each iteration. By pre-computing the cubic spline basis matrix B

    (shape: n_targets x n_knots) once, each evaluation reduces to a fast

    matrix-vector product:  n_values = B @ n_knot_values.

    This is ~6-10x faster than constructing a new CubicSpline each call.

    Usage:

        basis = SplineBasisCache.get(knot_wavelengths, target_wavelengths)

        n_values = basis @ n_knot_values

        k_values = basis @ k_knot_values

    """

    _cache: dict = {}

    _lock = None  # Initialized lazily to avoid import-time threading overhead

    @classmethod
    def _get_lock(cls):

        if cls._lock is None:
            from threading import Lock

            cls._lock = Lock()

        return cls._lock

    @classmethod
    def get(cls, knot_wavelengths: np.ndarray, target_wavelengths: np.ndarray) -> np.ndarray:
        """

        Returns the pre-computed basis matrix B (n_targets x n_knots).

        Computes and caches it on first call for a given (knots, targets) pair.

        """

        key = (
            tuple(np.round(knot_wavelengths, 6)),
            tuple(np.round(target_wavelengths, 4)),
        )

        if key in cls._cache:
            return cls._cache[key]

        with cls._get_lock():
            # Double-checked locking
            if key in cls._cache:
                return cls._cache[key]

            # Safeguard against memory leak due to dynamic knots misuse
            if len(cls._cache) > 500:
                cls._cache.clear()

            n_knots = len(knot_wavelengths)

            n_targets = len(target_wavelengths)

            # Build basis matrix: evaluate each unit-vector spline at target points.

            # B[i, j] = value at target[i] of the spline that equals 1 at knot[j], 0 elsewhere.

            B = np.zeros((n_targets, n_knots), dtype=np.float64)

            unit_vals = np.zeros(n_knots, dtype=np.float64)

            for j in range(n_knots):
                unit_vals[:] = 0.0

                unit_vals[j] = 1.0

                basis_spline = CubicSpline(knot_wavelengths, unit_vals, bc_type="natural", extrapolate=True)

                col = basis_spline(target_wavelengths)

                np.nan_to_num(col, copy=False)

                B[:, j] = col

            cls._cache[key] = B

            return B

    @classmethod
    def clear(cls):

        with cls._get_lock():
            cls._cache.clear()


@lru_cache(maxsize=1024)
def _get_nk_from_spline_cached(
    p_spline_tuple: tuple, knot_wl_tuple: tuple, target_wl_tuple: tuple, use_cache: bool
) -> tuple[np.ndarray, np.ndarray]:
    p_spline_nk_values = np.array(p_spline_tuple)
    knot_wavelengths = np.array(knot_wl_tuple)
    target_lambda_array = np.array(target_wl_tuple)

    num_knots = len(knot_wavelengths)
    n_knot_values = p_spline_nk_values[:num_knots]
    k_knot_values = p_spline_nk_values[num_knots:]

    if use_cache:
        B = SplineBasisCache.get(knot_wavelengths, target_lambda_array)
        n_values = B @ n_knot_values
        k_values = B @ k_knot_values
    else:
        spline_n = CubicSpline(knot_wavelengths, n_knot_values, bc_type="natural", extrapolate=True)
        spline_k = CubicSpline(knot_wavelengths, k_knot_values, bc_type="natural", extrapolate=True)
        n_values = spline_n(target_lambda_array)
        k_values = spline_k(target_lambda_array)

    n_values = np.nan_to_num(np.clip(n_values, 0.0, 10.0))
    k_values = np.nan_to_num(np.clip(k_values, 0.0, 10.0))
    return n_values, k_values


def get_nk_from_spline(
    p_spline_nk_values: np.ndarray,
    knot_wavelengths: np.ndarray,
    target_lambda_array: np.ndarray,
    use_cache: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Interpolates n, k from spline knots using cubic spline.
    When use_cache=True (default), uses SplineBasisCache for fast matrix-vector evaluation.
    When use_cache=False, falls back to direct CubicSpline construction.
    """
    return _get_nk_from_spline_cached(
        tuple(p_spline_nk_values), tuple(knot_wavelengths), tuple(target_lambda_array), use_cache
    )


# =============================================================================
