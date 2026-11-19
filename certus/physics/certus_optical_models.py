SMALL_EPSILON = 1e-12
from collections import OrderedDict
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numba import njit, prange
from scipy.interpolate import CubicSpline

from certus.domain.constants import PI

_FASTMATH_SAFE = {"nsz", "arcp", "contract", "afn", "reassoc"}

if TYPE_CHECKING:
    from threading import Lock


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

            d1 = w2 - C1
            if abs(d1) < SMALL_EPSILON:
                d1 = SMALL_EPSILON if d1 >= 0.0 else -SMALL_EPSILON
            d2 = w2 - C2
            if abs(d2) < SMALL_EPSILON:
                d2 = SMALL_EPSILON if d2 >= 0.0 else -SMALL_EPSILON
            d3 = w2 - C3
            if abs(d3) < SMALL_EPSILON:
                d3 = SMALL_EPSILON if d3 >= 0.0 else -SMALL_EPSILON
            n2 = 1.0 + B1 * w2 / d1 + B2 * w2 / d2 + B3 * w2 / d3

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
def _get_nk_cauchy_cached_readonly(n4: float, n7: float, wls_tuple: tuple[float, ...]) -> np.ndarray:
    wls_arr = np.array(wls_tuple, dtype=np.float64)
    arr = get_nk_cauchy(n4, n7, wls_arr)
    arr.setflags(write=False)
    return arr


def _get_nk_cauchy_cached(n4: float, n7: float, wls_tuple: tuple[float, ...]) -> np.ndarray:
    return _get_nk_cauchy_cached_readonly(n4, n7, wls_tuple).copy()


def get_nk_cauchy_wrapper(n4: float, n7: float, wls: np.ndarray) -> np.ndarray:
    """Cauchy index wrapper. Returns f64 (double precision)."""
    return _get_nk_cauchy_cached(float(n4), float(n7), tuple(wls.astype(np.float64)))


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def get_nk_cauchy_simple(wavelength_nm: np.ndarray, n_infini: float, A: float) -> np.ndarray:
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

        # The tail is anchored at E_edge = Eg + delta: switch there, where both parts are equal. Switching at Eg left a
        # jump of a factor 8000 and a dip on (Eg, Eg + delta] (audit 2026-11-15, L1-m6; D71).
        if E > E_edge:
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


@njit(cache=True, nogil=True, error_model="numpy", inline="always")
def _tl_log_terms(
    E: float,
    E_sq: float,
    Eg: float,
    Eg_sq: float,
    A: float,
    E0: float,
    C: float,
    zeta4: float,
    denom_log_norm: float,
) -> tuple[float, float]:
    """Return (term1, term2) of Tauc-Lorentz eps1 with continuous removable singularity at E == Eg."""
    pref = A * E0 * C / (PI * zeta4)
    if abs(Eg - E) < SMALL_EPSILON:
        sum_e = Eg + E
        if sum_e <= SMALL_EPSILON:
            return 0.0, 0.0
        term1 = pref * (E_sq + Eg_sq) / E * np.log(sum_e) if E > SMALL_EPSILON else 0.0
        term2 = 2.0 * pref * Eg * np.log(sum_e / denom_log_norm) if denom_log_norm > SMALL_EPSILON else 0.0
        return term1, term2
    term1 = 0.0
    if E > SMALL_EPSILON:
        term1 = -pref * (E_sq + Eg_sq) / E * np.log(np.abs((Eg - E) / (Eg + E)))
    term2 = 2.0 * pref * Eg * np.log(np.abs((Eg - E) * (Eg + E)) / denom_log_norm)
    return term1, term2


@njit(cache=True, nogil=True, error_model="numpy")
def epsilon1_TL_overdamped_point(E: float, Eg: float, A: float, E0: float, C: float, eps_inf: float) -> float:
    """Unfloored eps1 of the Jellison-Modine closed form, valid for any C, written for C >= 2 E0.

    There alpha = sqrt(4 E0^2 - C^2) is imaginary: the terms in alpha are evaluated in complex arithmetic (principal
    branches) and their sum is real; Kramers-Kronig agrees to 3e-6 (tests/unit/test_tauc_lorentz_eps1_beyond_critical_damping.py).
    No fastmath: the caller tests the result with isfinite.
    """
    E0_sq = E0 * E0
    Eg_sq = Eg * Eg
    C_sq = C * C
    E_sq = E * E
    gamma_sq = E0_sq - C_sq / 2.0
    alpha = np.sqrt(complex(4.0 * E0_sq - C_sq, 0.0))
    zeta4 = max((E_sq - E0_sq) ** 2 + C_sq * E_sq, SMALL_EPSILON)
    al = (Eg_sq - E0_sq) * E_sq + Eg_sq * C_sq - E0_sq * (E0_sq + 3.0 * Eg_sq)
    aa = (E_sq - E0_sq) * (E0_sq + Eg_sq) + Eg_sq * C_sq
    denom_log_norm = np.sqrt((E0_sq - Eg_sq) ** 2 + C_sq * Eg_sq)
    term1, term2 = _tl_log_terms(E, E_sq, Eg, Eg_sq, A, E0, C, zeta4, denom_log_norm)
    term3 = (A * C * al) / (2.0 * PI * zeta4 * alpha * E0) * np.log((E0_sq + Eg_sq + alpha * Eg) / (E0_sq + Eg_sq - alpha * Eg))
    term4 = -(A * aa) / (PI * zeta4 * E0) * (PI - np.arctan((2.0 * Eg + alpha) / C) - np.arctan((2.0 * Eg - alpha) / C))
    term5 = (4.0 * A * E0 * Eg * (E_sq - gamma_sq)) / (PI * zeta4 * alpha) * (PI / 2.0 - np.arctan(2.0 * (Eg_sq - gamma_sq) / (alpha * C)))
    return eps_inf + term1 + term2 + (term3 + term4 + term5).real


@njit(cache=True, nogil=True, error_model="numpy")
def _epsilon1_TL_overdamped(E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float) -> np.ndarray:
    """epsilon1_TL_analytic for C >= 2 E0, with the same floor."""
    eps1_array = np.empty(len(E_array), dtype=np.float64)
    for i in range(len(E_array)):
        val = epsilon1_TL_overdamped_point(E_array[i], Eg, A, E0, C, eps_inf)
        eps1_array[i] = max(val, 1.0) if np.isfinite(val) else eps_inf
    return eps1_array


@njit(cache=True, nogil=True, error_model="numpy")
def epsilon1_gradient_overdamped(E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float) -> np.ndarray:
    """`gradient_analytic._compute_epsilon1_gradient_kernel` for C >= 2 E0: eps1 from the complex closed form, its
    derivatives in Eg, A, E0 and C by central differences (step 1e-6 of each), with the same floor."""
    n = len(E_array)
    result = np.zeros((7, n), dtype=np.float64)
    params = np.array([Eg, A, E0, C], dtype=np.float64)
    for i in range(n):
        E = E_array[i]
        val = epsilon1_TL_overdamped_point(E, Eg, A, E0, C, eps_inf)
        if not np.isfinite(val):
            result[0, i] = eps_inf
            result[6, i] = 1.0
        elif val < 1.0:
            result[0, i] = 1.0
        else:
            result[0, i] = val
            for k in range(4):
                h = 1e-6 * max(abs(params[k]), 1.0)
                up = params.copy()
                down = params.copy()
                up[k] += h
                down[k] -= h
                f_up = epsilon1_TL_overdamped_point(E, up[0], up[1], up[2], up[3], eps_inf)
                f_down = epsilon1_TL_overdamped_point(E, down[0], down[1], down[2], down[3], eps_inf)
                result[k + 1, i] = (f_up - f_down) / (2.0 * h)
            result[6, i] = 1.0
    return result


@njit(cache=True, fastmath=_FASTMATH_SAFE, parallel=True, nogil=True, error_model="numpy")
def epsilon1_TL_analytic(E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float) -> np.ndarray:

    if 4.0 * E0 * E0 - C * C < 1e-12:
        # Overdamped (C >= 2 E0): alpha is imaginary; the clamp below would give a wrong eps1 (ETAT section 5).
        return _epsilon1_TL_overdamped(E_array, Eg, A, E0, C, eps_inf)

    n = len(E_array)

    eps1_array = np.empty(n, dtype=np.float64)

    E0_sq = E0 * E0

    Eg_sq = Eg * Eg

    C_sq = C * C

    gamma_sq = E0_sq - C_sq / 2.0

    alpha = np.sqrt(max(4.0 * E0_sq - C_sq, 1e-12))

    denom_log_norm = np.sqrt((E0_sq - Eg_sq) ** 2 + C_sq * Eg_sq)

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

        term1, term2 = _tl_log_terms(E, E_sq, Eg, Eg_sq, A, E0, C, zeta4, denom_log_norm)

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


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy", inline="always")
def extinction_from_epsilon(e1: float, e2: float, eps_mag: float, n_val: float) -> float:
    """k of the complex index whose square is e1 + i.e2, without the cancellation of sqrt((|eps| - e1) / 2).

    Where e1 > 0, 2nk = e2 gives k = |e2| / (2n): exact however small e2 is. The difference |eps| - e1, taken the other way, is
    pure rounding below e2 ~ 1e-7 (D71): k came back as 0 or as a few per mille off. Where e1 <= 0 there is no cancellation and the
    difference stays.
    """
    if e1 > 0.0:
        return abs(e2) / (2.0 * n_val)
    return np.sqrt(max((eps_mag - e1) / 2.0, 0.0))


@njit(cache=True, parallel=True, nogil=True, error_model="numpy")
def epsilon_to_nk(
    eps1: np.ndarray, eps2: np.ndarray, n_min: float, n_max: float, k_max: float
) -> tuple[np.ndarray, np.ndarray, bool]:

    n_pts = len(eps1)

    n_arr = np.empty(n_pts, dtype=np.float64)

    k_arr = np.empty(n_pts, dtype=np.float64)

    invalid_count = 0

    for i in prange(n_pts):
        e1 = eps1[i]
        e2 = eps2[i]

        if not np.isfinite(e1) or not np.isfinite(e2):
            invalid_count += 1
            n_arr[i] = np.nan
            k_arr[i] = np.nan
        else:
            eps_mag = np.sqrt(e1 * e1 + e2 * e2)
            n_val = np.sqrt(max((eps_mag + e1) / 2.0, SMALL_EPSILON))
            k_val = extinction_from_epsilon(e1, e2, eps_mag, n_val)
            if not np.isfinite(n_val) or not np.isfinite(k_val) or n_val < n_min or n_val > n_max or k_val > k_max:
                invalid_count += 1
            n_arr[i] = n_val
            k_arr[i] = k_val

    return n_arr, k_arr, invalid_count == 0


# =============================================================================


# SPLINES (Moved from certus_physics.splines to avoid circular imports)


# =============================================================================


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

    _cache: ClassVar[OrderedDict] = OrderedDict()

    # Cache bound. Beyond this, we evict the oldest USED entry (LRU),
    #and not the entire cache — see comment in get().
    _MAX_ENTRIES = 512

    _lock = None  # Initialized lazily to avoid import-time threading overhead

    @classmethod
    def _get_lock(cls) -> Lock:

        if cls._lock is None:
            from threading import Lock

            cls._lock = Lock()

        return cls._lock

    @classmethod
    def get(
        cls,
        knot_wavelengths: np.ndarray,
        target_wavelengths: np.ndarray,
        extrapolate: bool = True,
    ) -> np.ndarray:
        """Basis matrix B (n_targets x n_knots), computed then cached.

        Args:
            knot_wavelengths: knot positions.
            target_wavelengths: evaluation grid.
            extrapolate: behavior outside knot domain.

        Returns:
            Basis matrix. Shared object — do not modify in place.
        """

        # Key built with .tobytes() rather than tuple().
        #
        # np.asarray(..., float64) is necessary: float32 and float64 callers
        # would produce different bytes for identical values.
        # ROUNDING IS INTENTIONAL AND MUST NOT BE REFINED.
        key = (
            np.round(np.asarray(knot_wavelengths, dtype=np.float64), 6).tobytes(),
            np.round(np.asarray(target_wavelengths, dtype=np.float64), 4).tobytes(),
            bool(extrapolate),
        )

        # HOT path, without lock: dict.get is atomic under the GIL.
        #
        # move_to_end notes the recency. It is a single C call, also atomic
        # under the GIL; this avoids taking the lock on a cache hit,
        # which would make a reader wait behind an ongoing construction (~1 ms)
        # in another thread.
        cached = cls._cache.get(key)
        if cached is not None:
            try:
                cls._cache.move_to_end(key)
            except KeyError:  # evicted in the meantime: no consequence
                pass
            return cached

        with cls._get_lock():
            # Double-checked locking
            cached = cls._cache.get(key)
            if cached is not None:
                cls._cache.move_to_end(key)
                return cached

            n_knots = len(knot_wavelengths)

            n_targets = len(target_wavelengths)

            # Build basis matrix: evaluate each unit-vector spline at target points.

            # B[i, j] = value at target[i] of the spline that equals 1 at knot[j], 0 elsewhere.

            B = np.zeros((n_targets, n_knots), dtype=np.float64)

            unit_vals = np.zeros(n_knots, dtype=np.float64)

            for j in range(n_knots):
                unit_vals[:] = 0.0

                unit_vals[j] = 1.0

                basis_spline = CubicSpline(
                    knot_wavelengths, unit_vals, bc_type="natural", extrapolate=extrapolate
                )

                col = basis_spline(target_wavelengths)

                np.nan_to_num(col, copy=False, nan=0.0)

                B[:, j] = col

            cls._cache[key] = B

            # Bounded LRU eviction, and NOT a total flush.
            #
            # The old safeguard did `if len(_cache) > 500: _cache.clear()`. The
            # cost of a flush is not the freed space but the lost locality:
            # the currently hot entries left with the cold ones, and a finite
            # difference step that was just used had to be reconstructed.
            # Measurement on the real example example/example_metal_single, cache forced to
            # use_cache=True : 46,872 calls, 5,489 distinct matrices, 11 flushes,
            # 5,557 constructions — that is 68 reconstructions due to flushing.
            # popitem(last=False) removes the oldest USED entry; the bounding remains
            # the same, the temporal locality is preserved.
            while len(cls._cache) > cls._MAX_ENTRIES:
                cls._cache.popitem(last=False)

            return B

    @classmethod
    def clear(cls) -> None:

        with cls._get_lock():
            cls._cache.clear()


def _compute_nk_from_spline(
    p_spline_nk_values: np.ndarray,
    knot_wavelengths: np.ndarray,
    target_lambda_array: np.ndarray,
    use_cache: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Core computation, on ARRAYS. No conversion, no hashing."""
    num_knots = len(knot_wavelengths)
    n_knot_values = p_spline_nk_values[:num_knots]
    k_knot_values = p_spline_nk_values[num_knots:]

    if use_cache:
        basis = SplineBasisCache.get(knot_wavelengths, target_lambda_array)
        n_values = basis @ n_knot_values
        k_values = basis @ k_knot_values
    else:
        spline_n = CubicSpline(knot_wavelengths, n_knot_values, bc_type="natural", extrapolate=True)
        spline_k = CubicSpline(knot_wavelengths, k_knot_values, bc_type="natural", extrapolate=True)
        n_values = spline_n(target_lambda_array)
        k_values = spline_k(target_lambda_array)

    n_values = np.nan_to_num(np.clip(n_values, 0.0, 10.0))
    k_values = np.nan_to_num(np.clip(k_values, 0.0, 10.0))
    return n_values, k_values


@lru_cache(maxsize=1024)
def _get_nk_from_spline_keyed(
    p_key: bytes, knot_key: bytes, target_key: bytes, use_cache: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Memoized variant. Key in BYTES, and not in Python tuples.

    The old version took three tuples and immediately reconverted them into
    arrays: the full path was array -> tuple -> hash -> array, paid
    on vectors of several hundred points.
    """
    return _compute_nk_from_spline(
        np.frombuffer(p_key, dtype=np.float64),
        np.frombuffer(knot_key, dtype=np.float64),
        np.frombuffer(target_key, dtype=np.float64),
        use_cache,
    )


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
    p_arr = np.ascontiguousarray(p_spline_nk_values, dtype=np.float64)
    knot_arr = np.ascontiguousarray(knot_wavelengths, dtype=np.float64)
    target_arr = np.ascontiguousarray(target_lambda_array, dtype=np.float64)

    # BOTH paths go through memoization: `use_cache` does not choose whether to
    # memoize, but which evaluation method to employ — pre-computed basis matrix,
    # or direct construction of a CubicSpline. This parameter is therefore
    # part of the key.
    #
    # The key is in BYTES and not in Python tuples. The old version did
    # array -> tuple -> element-by-element hashing -> array, on vectors of
    # several hundred points; .tobytes() hashes a single memory block.
    return _get_nk_from_spline_keyed(
        p_arr.tobytes(), knot_arr.tobytes(), target_arr.tobytes(), bool(use_cache)
    )


# =============================================================================
