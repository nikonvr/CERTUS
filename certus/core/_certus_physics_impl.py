"""


CERTUS Physics - Core Scientific Kernels


========================================


# =========================================================================================


# ARCHITECTURE: MONOLITHIC KERNEL COMPILATION


# This file consolidates all Numba JIT kernels to maximize compilation unit efficiency.


# DO NOT SPLIT - Cross-inlining and type inference depend on single-file visibility.


# =========================================================================================


Part of CERTUS Suite (Harmonized Architecture 2026)


Contains:


- Optical Models (Sellmeier, Tauc-Lorentz-Urbach, Cauchy)


- Transfer Matrix Method (TMM) - Single & Multilayer


- Gradient Calculations & Sensitivity Kernels


- Optimization Algorithms (Coordinate Descent, PGLOBAL, Cost Functions)


- Data Structures (Layer, Target, TLUParameters)


- Colorimetry (CIE 1931, Lab, DeltaE)


- STRAT Specific Kernels (Growth Simulation, Monitoring)


"""

__all__ = [
    # Data Structures
    "Layer",
    "Target",
    "ObliqueTarget",
    "TLUParameters",
    "Sample",
    "PGlobalConfig",
    "SELLMEIER_COEFFS_BY_ID",
    "SUBSTRATE_MIN_LAMBDA_BY_ID",
    # Optical Models
    "sellmeier_n_array",
    "get_nk_cauchy",
    "get_nk_cauchy_wrapper",
    "epsilon2_TLU_array",
    "epsilon1_TL_analytic",
    "epsilon_to_nk",
    "get_n_substrate_array_by_id",
    "get_n_frosted_glass_array",
    # TMM
    "calculate_RT_single_layer_backside_array",
    "calculate_bare_substrate_RT",
    "calculate_single_interface_R",
    "calculate_RT_vectorized_real",
    "calculate_RT_vectorized_real_HL",
    "calc_spectrum_front",
    "calc_spectrum_full",
    "calc_spectrum_full_exact",
    "calc_spectrum_oblique_vectorized",
    "calc_spectrum_oblique_backside_vectorized",
    "calc_spectrum_full_oblique_exact",
    "oblique_front_char_matrix_single",
    "oblique_front_rt_from_char_matrix_nsub_real",
    "compute_oblique_rt_and_grads_analytic",
    "compute_TMM_generic",
    "calculate_RTRback_incoherent_vectorized",
    "apply_exact_backside_combination",
    # Cost Functions
    "cost_numba_fast",
    "make_cost_function",
    "calc_rmse",
    "prepare_targets_vectorized",
    # Gradients
    "compute_gradient_all_layers_analytic",
    "compute_oblique_gradient_contrib_analytic",
    # Optimization
    "PGlobalOptimizer",
    "SingleLinkageClusterer",
    "clip_to_bounds",
    "compute_mse_vectorized",
    # Colorimetry
    "xyz_from_spectrum",
    "xyz_to_lab",
    "lab_to_rgb",
    "delta_e_2000",
    # STRAT Kernels
    "simulate_growth_kernel",
    "compute_dynamics_kernel",
    "calculate_detailed_growth",
    "check_extrema_proximity",
    "validate_wavelengths_batch",
    "trim_worst_only",
    "simulate_stack_robustness_batch",
    "compute_batch_rmse",
    "compute_T_front_at_layer",
    # Non-monotonic handling modes
    "NON_MONOTONIC_MODE_ATTENUATE",
    "NON_MONOTONIC_MODE_REJECT",
    # Backside Validation
    "validate_backside_real_clues",
    "K_MAX_LAYER_BACKSIDE",
    "K_MAX_SUBSTRATE_BACKSIDE",
    # Material Database
    "Material",
    "MaterialDatabase",
    "NKCache",
    # Utilities
    "init_thickness",
    "calc_qwot",
    "arange_inclusive",
    "warmup_physics",
    "get_refractive_index",
    "get_refractive_clues_vectorized",
]


import logging


# =============================================================================


# CRITICAL CONVENTION - DO NOT INVERT - ABSOLUTE LAW


# =============================================================================


# LAYER 1 = the layer closest to the substrate.


# In all arrays (thicknesses, n_layers, etc.):


#   index 0 = layer 1 = layer adjacent to the substrate.


#   index N-1 = last layer = incident side (air).


# All TMM kernels (compute_TMM_generic, compute_TMM_single_point_k0, etc.)


# follow this convention. Any modification must preserve it.


#


# ╔══════════════════════════════════════════════════════════════════════╗


# ║  COMPLEX INDEX: n̂ = n - ik  (k >= 0 for absorption)                ║


# ║  Python: complex(n, -k)  ->  NEGATIVE imaginary part               ║


# ║  FORBIDDEN: n + ik (positive imaginary part = unphysical gain)     ║


# ║  With n+ik: R+T > 1, results are WRONG, physically impossible.     ║


# ║  NEVER MODIFY THIS CONVENTION.                                     ║


# ╚══════════════════════════════════════════════════════════════════════╝


# =============================================================================


# PHYSICS MANIFESTO - READ BEFORE MODIFYING


# =============================================================================


# 1. STANDARD MODE (Transparent Substrate):


#    - Measurements ALWAYS include the substrate backside reflection.


#    - R_measured = R_front + (T_front * T_prime * R_back) / (1 - R_prime * R_back) [Incoherent]


#    - T_measured = (T_front * T_back) / (1 - R_prime * R_back)


#    - Note: R_prime = reflectance seen from substrate side, NOT R_front!


#    - Kernels: calculate_bare_substrate_RT, calculate_single_interface_R, calculate_RT_single_layer_backside_array


#


# 2. FROSTED/INFINITE MODE (Frosted Glass / Opaque):


#    - Backside is scattering/absorbing. No specular reflection returns.


#    - R_measured = R_front (Single Interface).


#    - Kernels: calculate_single_interface_R, calculate_single_interface_R


#


# 3. OPTICAL MONITORING (STRAT):


#    - "Real World" Signal (calculate_detailed_growth): INCLUDES Backside.


#    - "Heuristic" Simulation (simulate_growth_kernel): EXCLUDES Backside (Speed/Stability).


#


# 4. OPTIMIZATION (DESIGN):


#    - Normal Incidence: Uses cost_numba_fast (Backside aware).


#    - Oblique Incidence: Uses Front-Only (Backside usually spatially separated).


#


# DO NOT VIOLATE THESE LAWS. UNINTENDED REGRESSIONS WILL INVALIDATE CALCULATIONS.


# =============================================================================


#


# =============================================================================


# BACKSIDE VARIABLE NAMING CONVENTION - CRITICAL FOR CORRECT PHYSICS


# =============================================================================


# The incoherent cavity formulas require careful distinction between:


#


# FRONT-SIDE QUANTITIES (Air -> Stack -> Substrate):


#   R_front (Rf): Reflectance seen from incident medium (Air)


#   T_front (Tf): Transmittance into substrate


#


# BACK-SIDE QUANTITIES (Substrate -> Stack -> Air):


#   R_prime (Rp): Reflectance seen from substrate looking back at stack


#                 This is NOT the same as R_front in general!


#   T_prime (Tp): Transmittance from substrate back to air


#                 For lossless stacks: Tp ~ Tf (reciprocity)


#


# SUBSTRATE INTERFACE (Sub | Air):


#   R_sub, R_back, Rb: Fresnel reflectance at substrate/air interface


#   T_sub, T_back, Tb: Fresnel transmittance (= 1 - Rb for transparent)


#


# CORRECT FORMULA FOR TOTAL TRANSMISSION:


#   T_total = (Tf * Tb) / (1 - R_prime * Rb)


#             ^^^^^^^^      ^^^^^^^


#             Forward T     Cavity uses R_prime NOT R_front!


#


# WRONG (but sometimes seen as approximation):


#   T_total = (Tf * Tb) / (1 - Rf * Rb)  ← Only valid if Rf ~ R_prime


#


# In calculate_detailed_growth(), R_prime is computed correctly via


# the reverse matrix product (R-matrix for Sub->Air direction).


# =============================================================================


import numpy as np
from certus.utils.certus_db_helpers import (
    find_matching_sheets,
    merge_two_curves,
    merge_multiple_curves,
    MergedMaterialDict,
)
_SubProcessMaterialDB = MergedMaterialDict


import math


import os
from pathlib import Path


from collections import OrderedDict


from dataclasses import dataclass


from threading import Event, RLock


from typing import Any, Callable


from numba import njit, prange


from scipy.optimize import minimize


from scipy.interpolate import CubicSpline


from functools import lru_cache


# Import from Core


from certus.core.certus_core import (
    FROSTED_GLASS_CAUCHY_A,
    FROSTED_GLASS_CAUCHY_B,
    HC_EV_NM,
    N_SUPERSTRATE,
    OPENPYXL_AVAILABLE,
    PI,
    SMALL_EPSILON,
    SUBSTRATE_MIN_LAMBDA,
    TWO_PI,
    WL_DECIMALS,
    get_complex_dtype,
    NUMERICAL_FAULT_EXCEPTIONS,
)


# =============================================================================


# DATA STRUCTURES - Imported from structures module (Single Source of Truth)


#


# Why dynamic import + fallback paths:


#   certus_physics/__init__.py loads this module (_certus_physics_impl); a direct import


#   "from certus_physics.structures import ..." would create a circular dependency


#   (init -> impl -> structures via package). We therefore load the submodule


#   `certus_physics.structures` via importlib, with fallback on file paths for


#   PyInstaller (_MEIPASS, _internal, exe dir).


# =============================================================================


# Import structures submodule - handle both dev and frozen (PyInstaller) modes


import importlib.util


import sys


import importlib


# Try importing as module first (works in both dev and frozen mode if PyInstaller included it)


# This avoids circular import issues because we import the submodule directly


try:
    _structures_module = importlib.import_module("certus_physics.structures")


except (ImportError, ModuleNotFoundError):
    # Fallback: load from file path (dev mode or if import fails in frozen mode)

    _base_path = Path(__file__).resolve().parent

    # In frozen mode, try multiple locations where PyInstaller might put files

    _possible_bases = [_base_path]

    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            _possible_bases.append(Path(sys._MEIPASS))

        # Also try _internal directory (where PyInstaller puts bundled modules)

        _executable_dir = Path(sys.executable).resolve().parent
        _internal_path = _executable_dir / "_internal"

        if _internal_path.exists():
            _possible_bases.append(_internal_path)

        # Try directory of executable

        _possible_bases.append(_executable_dir)

    # Try multiple paths to find structures.py

    _possible_paths = []

    for base in _possible_bases:
        _possible_paths.extend(
            [
                base / "certus_physics" / "structures.py",
                base.parent / "certus_physics" / "structures.py",
                base.parents[1] / "certus_physics" / "structures.py" if len(base.parents) > 1 else base / "certus_physics" / "structures.py",
            ]
        )

    _structures_path = None

    for path in _possible_paths:
        abs_path = path.resolve(strict=False)

        if abs_path.exists():
            _structures_path = str(abs_path)

            break

    if _structures_path is None:
        raise ImportError(
            f"Cannot find certus_physics/structures.py. "
            f"Tried: {_possible_paths[:5]}. "
            f"Frozen: {getattr(sys, 'frozen', False)}, "
            f"MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}, "
            f"__file__: {__file__}"
        )

    # Load from file path

    _spec = importlib.util.spec_from_file_location("_certus_structures", _structures_path)

    if _spec is None or _spec.loader is None:
        raise ImportError(f"Cannot create spec for {_structures_path}")

    _structures_module = importlib.util.module_from_spec(_spec)

    _spec.loader.exec_module(_structures_module)


# Extract classes and constants


Layer = _structures_module.Layer


ObliqueTarget = _structures_module.ObliqueTarget


PGlobalConfig = _structures_module.PGlobalConfig


Sample = _structures_module.Sample


Target = _structures_module.Target


TLUParameters = _structures_module.TLUParameters


SELLMEIER_COEFFS_BY_ID = _structures_module.SELLMEIER_COEFFS_BY_ID


SUBSTRATE_MIN_LAMBDA_BY_ID = _structures_module.SUBSTRATE_MIN_LAMBDA_BY_ID


# Cleanup temporary variables


if "_spec" in locals():
    del _spec


del _structures_module


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def get_n_substrate_array_by_id_kernel(
    wavelengths_nm: np.ndarray,
    B1: float,
    C1: float,
    B2: float,
    C2: float,
    B3: float,
    C3: float,
    min_lambda: float,
) -> np.ndarray:

    n = len(wavelengths_nm)

    results = np.empty(n, dtype=wavelengths_nm.dtype)

    for i in prange(n):
        wl = wavelengths_nm[i]

        if wl < min_lambda:
            results[i] = np.nan

        else:
            l_um = wl / 1000.0

            l_sq = l_um * l_um

            n_sq = 1.0 + (B1 * l_sq / (l_sq - C1)) + (B2 * l_sq / (l_sq - C2)) + (B3 * l_sq / (l_sq - C3))

            results[i] = np.sqrt(max(n_sq, 1e-6))

    return results


def get_n_substrate_array_by_id(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:

    # ── GUARDRAIL ─────────────────────────────────────────────────────────────
    # Sapphire/Al2O3 (id=3) uses the ANALYTICAL 3-term Sellmeier LAW,
    # identical to all other substrates.
    #
    # HISTORY: until May 2026, id=3 used a tabulated interpolation
    # from example/sapphire fresnel.xlsx. This approach was abandoned
    # because:
    #   1. It created an external dependency (xlsx) for a physical calculation.
    #   2. It was not consistent with CERTUS_INDEX / CERTUS_INDEX_SPLINE
    #      which already forced the analytical Sellmeier.
    #   3. The Sellmeier law is more stable at the edges of the spectral range.
    #
    # DO NOT reintroduce tabulated branching here.
    # ──────────────────────────────────────────────────────────────────────────

    if substrate_id not in SELLMEIER_COEFFS_BY_ID:
        raise KeyError(f"Unknown substrate ID: {substrate_id}")

    coeffs = SELLMEIER_COEFFS_BY_ID[substrate_id]

    min_lambda = SUBSTRATE_MIN_LAMBDA.get(substrate_id, 200.0)

    wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    return get_n_substrate_array_by_id_kernel(wavelengths_nm, *coeffs, min_lambda)






# =========================================================================================


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


def get_nk_cauchy_wrapper(n4: float, n7: float, wls: np.ndarray) -> np.ndarray:
    """Cauchy index wrapper. Returns f64 (double precision)."""

    return get_nk_cauchy(float(n4), float(n7), wls.astype(np.float64))


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
                result[i] = eps2_at_edge * np.exp((E - Eg - delta) / Eu_safe)

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


def get_nk_from_spline(
    p_spline_nk_values: np.ndarray,
    knot_wavelengths: np.ndarray,
    target_lambda_array: np.ndarray,
    use_cache: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Interpolates n, k from spline knots using cubic spline.

    When use_cache=True (default), uses SplineBasisCache for fast matrix-vector

    evaluation (~6-10x faster than constructing a new CubicSpline each call).

    When use_cache=False, falls back to direct CubicSpline construction.

    """

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

    # Clip to physical/valid range (0-10)

    n_values = np.nan_to_num(np.clip(n_values, 0.0, 10.0))

    k_values = np.nan_to_num(np.clip(k_values, 0.0, 10.0))

    return n_values, k_values


# =============================================================================


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
        # Delegate to batch kernel (single run) for parity with calculate_RT_batch_kernel

        thick_2d = np.asarray(thicknesses, dtype=np.float64).reshape(1, -1)

        wls_f = np.asarray(wls, dtype=np.float64)

        nH_f = (
            np.asarray(nH, dtype=np.complex128)
            if np.issubdtype(nH.dtype, np.floating)
            else np.asarray(nH, dtype=np.complex128)
        )

        nL_f = (
            np.asarray(nL, dtype=np.complex128)
            if np.issubdtype(nL.dtype, np.floating)
            else np.asarray(nL, dtype=np.complex128)
        )

        nSub_f = np.asarray(nSub, dtype=np.complex128)

        R_batch, T_batch = calculate_RT_batch_kernel(wls_f, nH_f, nL_f, nSub_f, thick_2d)

        return R_batch[0], T_batch[0]

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


# [MONOLITHIC BLOCK] TMM & OPTIMIZATION KERNELS


# DO NOT SPLIT - Core Transfer Matrix Method implementation


# =========================================================================================


# OPTIMIZATION KERNELS (NUMBA)


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_mse_vectorized(
    calc_values: np.ndarray, target_values: np.ndarray, weights: np.ndarray
) -> tuple[float, int]:

    n = len(calc_values)

    # Thread-local accumulators via parallel reduction

    partial_sq = np.empty(n, dtype=np.float64)

    partial_valid = np.empty(n, dtype=np.float64)

    partial_wsum = np.empty(n, dtype=np.float64)

    for i in prange(n):
        if weights[i] > 0 and np.isfinite(calc_values[i]) and np.isfinite(target_values[i]):
            diff = calc_values[i] - target_values[i]

            partial_sq[i] = diff * diff * weights[i]

            partial_valid[i] = 1.0

            partial_wsum[i] = weights[i]

        else:
            partial_sq[i] = 0.0

            partial_valid[i] = 0.0

            partial_wsum[i] = 0.0

    sum_sq = 0.0

    sum_w = 0.0

    count = 0

    for i in range(n):
        sum_sq += partial_sq[i]

        sum_w += partial_wsum[i]

        count += int(partial_valid[i])

    if count < 5 or sum_w <= 1e-18:
        return 1e12, count

    # Strict weighted average: makes the metric consistent with Deltaln(lambda)

    # even if the spectral grid is irregular.

    return sum_sq / sum_w, count


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def clip_to_bounds(x: np.ndarray, lb: np.ndarray, ub: np.ndarray) -> np.ndarray:

    return np.minimum(np.maximum(x, lb), ub)


# --- LOCKED --- Validated by test_tmm_inline.py (test 5) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def cost_numba_fast(
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
) -> float:

    # --- CRITICAL PHYSICS NOTE ---

    # This cost function optimizes TRANSMISSION (T) ONLY.

    # It compares T_calc vs Target Values (assumed to be T).

    # If has_back=True, it uses the EXACT incoherent backside formula:

    # T_total = (Tf * Tb) / (1 - Rf' * Rb')

    # DO NOT CHANGE THIS LOGIC without verifying target types.

    # -----------------------------

    # 1. Calc Optical Properties (T)

    if has_back:
        Rf, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(wls, ep, n_layers_T, d_back, n_back_T, n_sub)

        # Exact incoherent: T = (Tf * Tb) / (1 - Rf' * Rb')

        n_wls = len(wls)

        T = np.empty(n_wls, dtype=wls.dtype)

        for i in prange(n_wls):
            d_val = 1.0 - Rf_prime[i] * Rb_prime[i]

            if d_val < 1e-12:
                d_val = 1e-12

            T[i] = (Tf[i] * Tb[i]) / d_val

    else:
        R, T = calculate_RT_no_backside(ep, n_layers_T, n_sub, wls)

    # 2. MSE

    mse, count = compute_mse_vectorized(T, tgt_vals, tgt_weights)

    if count == 0:
        return 1e12

    # 3. Vectorized penalty via parallel reduction

    n_ep = len(ep)

    penalty_arr = np.empty(n_ep, dtype=np.float64)

    for i in prange(n_ep):
        d_val = ep[i]

        if 1e-12 < d_val < min_d:
            gap = min_d - d_val

            penalty_arr[i] = gap * gap * 1e6

        else:
            penalty_arr[i] = 0.0

    penalty = 0.0

    for i in range(n_ep):
        penalty += penalty_arr[i]

    return mse + penalty


# [REMOVED 2026-02-11] run_coordinate_descent_RT - dead code duplicate.


# Active version lives in CERTUS_INDEX.py with proper parallelization.


# =============================================================================


# NEEDLE SCAN - CACHED FORWARD/BACKWARD PRODUCTS


# =============================================================================


# --- LOCKED --- Validated by test_needle_cached.py (8/8) ---


# Macleod convention (+1j), pre-multiply Air->Sub, index 0 = substrate.


# Complexity: O(N*W) precomputation + O(P*W) scan  (P = total positions)


# vs O(P*N*W) for the naive full-TMM-per-position approach.


# DO NOT MODIFY without running test_needle_cached.py + test_tmm_inline.py.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def needle_scan_cached(
    wls: np.ndarray,  # (W,) float64
    n_layers_T: np.ndarray,  # (W, N) complex128 - layer clues
    n_needle_T: np.ndarray,  # (W, N) complex128  - needle material per layer
    n_sub: np.ndarray,  # (W,) complex128     - substrate
    ep: np.ndarray,  # (N,) float64        - current thicknesses
    tgt_vals: np.ndarray,  # (W,) float64        - target T values
    tgt_weights: np.ndarray,  # (W,) float64        - target weights
    step_nm: float,  # scan step (nm)
    probe_thickness: float,  # needle probe thickness (nm)
    scan_mask: np.ndarray,  # (N,) int64  - 1 = scan, 0 = skip
) -> tuple:
    """

    Optimized Needle position scan with forward/backward matrix caching.

    Instead of recomputing the full TMM (N+2 layers) for every candidate

    (layer, depth) pair, we:

      1. Precompute cumulative matrix products from both ends  - O(N·W).

      2. For each candidate position, compute only the 3 inner matrices

         (left, needle, right) and chain them with the cached products - O(W).

    Returns

    -------

    (best_layer, best_depth, best_cost) - int64, float64, float64

    Returns (-1, 0.0, 1e30) if no valid candidate is found.

    """

    N = len(ep)

    W = len(wls)

    # --- Precompute k0 = 2π/lambda ---

    k0 = TWO_PI / wls

    # ================================================================

    # Step 1 - Forward cumulative products L[j] (j = 0 … N)

    #   L[j] = M_{j-1} × … × M_0 (layers below j, substrate side)

    #   L[0] = Identity

    #   L[j+1] = M_j × L[j]         (pre-multiply)

    # ================================================================

    L00 = np.empty((N + 1, W), dtype=np.complex128)

    L01 = np.empty((N + 1, W), dtype=np.complex128)

    L10 = np.empty((N + 1, W), dtype=np.complex128)

    L11 = np.empty((N + 1, W), dtype=np.complex128)

    for w in range(W):
        L00[0, w] = 1.0 + 0j

        L01[0, w] = 0.0 + 0j

        L10[0, w] = 0.0 + 0j

        L11[0, w] = 1.0 + 0j

    for j in range(N):
        d_j = ep[j]

        for w in range(W):
            n_j = n_layers_T[w, j]

            phi = k0[w] * n_j * d_j

            cp = np.cos(phi)

            sp_i = 1j * np.sin(phi)  # +1j  Macleod

            m01 = sp_i / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            m10 = sp_i * n_j

            a00 = L00[j, w]

            a01 = L01[j, w]

            a10 = L10[j, w]

            a11 = L11[j, w]

            L00[j + 1, w] = cp * a00 + m01 * a10

            L01[j + 1, w] = cp * a01 + m01 * a11

            L10[j + 1, w] = m10 * a00 + cp * a10

            L11[j + 1, w] = m10 * a01 + cp * a11

    # ================================================================

    # Step 2 - Backward cumulative products R[j] (j = 0 … N-1)

    #   R[j] = M_{N-1} × … × M_{j+1} (layers above j, air side)

    #   R[N-1] = Identity

    #   R[j]   = R[j+1] × M_{j+1}

    # ================================================================

    R00 = np.empty((N, W), dtype=np.complex128)

    R01 = np.empty((N, W), dtype=np.complex128)

    R10 = np.empty((N, W), dtype=np.complex128)

    R11 = np.empty((N, W), dtype=np.complex128)

    for w in range(W):
        R00[N - 1, w] = 1.0 + 0j

        R01[N - 1, w] = 0.0 + 0j

        R10[N - 1, w] = 0.0 + 0j

        R11[N - 1, w] = 1.0 + 0j

    for j in range(N - 2, -1, -1):
        d_jp1 = ep[j + 1]

        for w in range(W):
            n_jp1 = n_layers_T[w, j + 1]

            phi = k0[w] * n_jp1 * d_jp1

            cp = np.cos(phi)

            sp_i = 1j * np.sin(phi)

            m01 = sp_i / n_jp1 if abs(n_jp1) > 1e-12 else 0.0 + 0j

            m10 = sp_i * n_jp1

            r00 = R00[j + 1, w]

            r01 = R01[j + 1, w]

            r10 = R10[j + 1, w]

            r11 = R11[j + 1, w]

            # R[j] = R[j+1] × M_{j+1}

            R00[j, w] = r00 * cp + r01 * m10

            R01[j, w] = r00 * m01 + r01 * cp

            R10[j, w] = r10 * cp + r11 * m10

            R11[j, w] = r10 * m01 + r11 * cp

    # ================================================================

    # Step 3 - Enumerate all (layer, z) candidates

    # ================================================================

    total = 0

    for j in range(N):
        if scan_mask[j] == 0:
            continue

        d_j = ep[j]

        if d_j < step_nm + 0.1:
            continue

        z = step_nm

        while z < d_j - 0.1:
            total += 1

            z += step_nm

    if total == 0:
        return np.int64(-1), 0.0, 1e30

    cand_layer = np.empty(total, dtype=np.int64)

    cand_z = np.empty(total, dtype=np.float64)

    idx = 0

    for j in range(N):
        if scan_mask[j] == 0:
            continue

        d_j = ep[j]

        if d_j < step_nm + 0.1:
            continue

        z = step_nm

        while z < d_j - 0.1:
            cand_layer[idx] = j

            cand_z[idx] = z

            idx += 1

            z += step_nm

    total = idx  # actual count

    # ================================================================

    # Step 4 - Evaluate all candidates in parallel (prange)

    #

    # For candidate c  at layer j, depth z:

    #   M_total = R[j] × M_right(d_j-z) × M_needle(probe) × M_left(z) × L[j]

    #   -> 4 matrix multiplications + R/T extraction per wavelength

    # ================================================================

    costs = np.full(total, 1e30, dtype=np.float64)

    for c in prange(total):
        j = cand_layer[c]

        z = cand_z[c]

        d_j = ep[j]

        d_right = d_j - z

        mse_sum = 0.0

        count = 0

        for w in range(W):
            w_tgt = tgt_weights[w]

            if w_tgt <= 0.0:
                continue

            kk = k0[w]

            n_j = n_layers_T[w, j]

            n_ndl = n_needle_T[w, j]

            ns = n_sub[w]

            # ── M_left(z, n_j) ──

            phi_l = kk * n_j * z

            cp_l = np.cos(phi_l)

            sp_l = 1j * np.sin(phi_l)

            ml01 = sp_l / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            ml10 = sp_l * n_j

            # T1 = M_left × L[j]

            a00 = L00[j, w]

            a01 = L01[j, w]

            a10 = L10[j, w]

            a11 = L11[j, w]

            t1_00 = cp_l * a00 + ml01 * a10

            t1_01 = cp_l * a01 + ml01 * a11

            t1_10 = ml10 * a00 + cp_l * a10

            t1_11 = ml10 * a01 + cp_l * a11

            # ── M_needle(probe, n_ndl) ──

            phi_n = kk * n_ndl * probe_thickness

            cp_n = np.cos(phi_n)

            sp_n = 1j * np.sin(phi_n)

            mn01 = sp_n / n_ndl if abs(n_ndl) > 1e-12 else 0.0 + 0j

            mn10 = sp_n * n_ndl

            # T2 = M_needle × T1

            t2_00 = cp_n * t1_00 + mn01 * t1_10

            t2_01 = cp_n * t1_01 + mn01 * t1_11

            t2_10 = mn10 * t1_00 + cp_n * t1_10

            t2_11 = mn10 * t1_01 + cp_n * t1_11

            # ── M_right(d_right, n_j) ──

            phi_r = kk * n_j * d_right

            cp_r = np.cos(phi_r)

            sp_r = 1j * np.sin(phi_r)

            mr01 = sp_r / n_j if abs(n_j) > 1e-12 else 0.0 + 0j

            mr10 = sp_r * n_j

            # T3 = M_right × T2

            t3_00 = cp_r * t2_00 + mr01 * t2_10

            t3_01 = cp_r * t2_01 + mr01 * t2_11

            t3_10 = mr10 * t2_00 + cp_r * t2_10

            t3_11 = mr10 * t2_01 + cp_r * t2_11

            # T4 = R[j] × T3  ->  M_total

            rr00 = R00[j, w]

            rr01 = R01[j, w]

            rr10 = R10[j, w]

            rr11 = R11[j, w]

            M00 = rr00 * t3_00 + rr01 * t3_10

            M01 = rr00 * t3_01 + rr01 * t3_11

            M10 = rr10 * t3_00 + rr11 * t3_10

            M11 = rr10 * t3_01 + rr11 * t3_11

            # ── Extract T  (Macleod:  n_inc = 1, n_exit = n_sub) ──

            B = M00 + M01 * ns

            C = M10 + M11 * ns

            Y = B + C  # n_inc * B + C  with n_inc = 1

            if abs(Y) < 1e-14:
                T_val = 0.0

            else:
                t_coeff = 2.0 / Y  # 2·n_inc / Y

                T_val = ns.real * (t_coeff.real * t_coeff.real + t_coeff.imag * t_coeff.imag)

                if T_val < 0.0:
                    T_val = 0.0

                r_coeff = (B - C) / Y

                R_val = r_coeff.real * r_coeff.real + r_coeff.imag * r_coeff.imag

                if R_val + T_val > 1.0:
                    T_val = 1.0 - R_val

                    if T_val < 0.0:
                        T_val = 0.0

            # ── Accumulate weighted MSE ──

            if np.isfinite(T_val) and np.isfinite(tgt_vals[w]):
                diff = T_val - tgt_vals[w]

                mse_sum += diff * diff * w_tgt

                count += 1

        if count >= 5:
            costs[c] = mse_sum / count

    # ================================================================

    # Step 5 - Find best candidate

    # ================================================================

    best_idx = 0

    best_cost = costs[0]

    for c in range(1, total):
        if costs[c] < best_cost:
            best_cost = costs[c]

            best_idx = c

    return np.int64(cand_layer[best_idx]), cand_z[best_idx], best_cost


# =============================================================================


# =========================================================================================


# [MONOLITHIC BLOCK] PGLOBAL ALGORITHM


# DO NOT SPLIT - Tightly coupled with optimization kernels


# =========================================================================================


# OPTIMIZATION ALGORITHMS (PGLOBAL)


# =============================================================================


def get_lbfgsb_params(dim: int) -> dict:
    """L-BFGS-B tolerances - always tight (gradient computed in f64)."""

    return {"ftol": 1e-12, "gtol": 1e-12, "maxcor": min(50, max(20, dim + 5))}


class LBFGSBSearcher:
    """Local Search via L-BFGS-B (direct Fortran setulb for 2× less overhead)."""

    # Try to import the Fortran kernel once at class definition time.
    # Falls back to scipy.optimize.minimize if unavailable.
    try:
        from scipy.optimize._lbfgsb import setulb as _setulb
    except ImportError:
        _setulb = None

    def __init__(
        self,
        func: Callable,
        bounds: np.ndarray,
        config: PGlobalConfig | None = None,
        gradient_func: Callable | None = None,
    ):

        self.func = func

        # Pre-compute bounds list once (avoid O(dim) list creation per search)
        self._bounds_list = list(zip(bounds[:, 0], bounds[:, 1]))

        self.dim = len(bounds)

        self.config = config

        self.gradient_func = gradient_func

        # Pre-compute L-BFGS-B parameters (dimension-dependent, constant per searcher)
        self._lbfgsb_params = get_lbfgsb_params(self.dim)

        # Pre-compute Fortran-format bounds arrays (used by direct setulb path)
        self._low_bnd = np.ascontiguousarray(bounds[:, 0], dtype=np.float64)
        self._upper_bnd = np.ascontiguousarray(bounds[:, 1], dtype=np.float64)
        self._nbd = np.full(self.dim, 2, dtype=np.int32)  # 2 = both bounds

        # Pre-build combined fun+grad closure (probed once in __init__,
        # not per search call). Saves ~2 TMM evals per local search.
        self._objective_fn = func
        self._jac_arg = None

        if gradient_func is not None:
            _func = func
            _grad = gradient_func

            def _fun_and_grad(x):
                f = _func(x)
                g = _grad(x)
                if isinstance(g, tuple):
                    g = g[1]
                if g is None:
                    return f
                return f, g

            self._fun_and_grad = _fun_and_grad
            # Probe deferred to first search() call where x0 is available
            self._grad_probed = False
        else:
            self._fun_and_grad = None
            self._grad_probed = True  # nothing to probe

    def _probe_gradient(self, x0: np.ndarray):
        """One-time probe: does gradient_func work for the given x0?"""
        if self._grad_probed:
            return
        self._grad_probed = True
        if self._fun_and_grad is None:
            return
        try:
            _probe = self._fun_and_grad(x0)
            if isinstance(_probe, tuple) and len(_probe) == 2:
                self._objective_fn = self._fun_and_grad
                self._jac_arg = True
        except (ValueError, RuntimeError, TypeError):
            pass

    def _search_direct(
        self,
        x0: np.ndarray,
        max_feval: int,
        fun_and_grad: Callable,
    ) -> tuple[np.ndarray, float, int]:
        """Direct Fortran setulb call — bypasses scipy.optimize.minimize wrapper.

        Eliminates ScalarFunction, _prepare_bounds, and OptimizeResult overhead
        (~35us per function evaluation, measured 2× speedup vs minimize).
        """
        n = self.dim
        m = self._lbfgsb_params["maxcor"]
        ftol = self._lbfgsb_params["ftol"]
        gtol = self._lbfgsb_params["gtol"]

        x = np.array(x0, dtype=np.float64)
        f = np.float64(0.0)
        g = np.zeros(n, dtype=np.float64)

        factr = ftol / np.finfo(np.float64).eps

        wa = np.zeros(2 * m * n + 5 * n + 11 * m * m + 8 * m, dtype=np.float64)
        iwa = np.zeros(3 * n, dtype=np.int32)
        task = np.zeros(2, dtype=np.int32)
        ln_task = np.zeros(2, dtype=np.int32)
        lsave = np.zeros(4, dtype=np.int32)
        isave = np.zeros(44, dtype=np.int32)
        dsave = np.zeros(29, dtype=np.float64)

        nfev = 0
        maxiter = max(100, max_feval // (n + 1))
        maxls = 20

        _setulb = self._setulb
        while True:
            _setulb(
                m,
                x,
                self._low_bnd,
                self._upper_bnd,
                self._nbd,
                f,
                g,
                factr,
                gtol,
                wa,
                iwa,
                task,
                lsave,
                isave,
                dsave,
                maxls,
                ln_task,
            )
            if task[0] == 3:  # FG request — evaluate objective + gradient
                result = fun_and_grad(x)
                if isinstance(result, tuple):
                    fv, gv = result
                    f = np.float64(fv)
                    g[:] = np.asarray(gv, dtype=np.float64)
                else:
                    f = np.float64(result)
                    # FD gradient will be handled by setulb internally
                nfev += 1
                if nfev >= max_feval:
                    task[0] = 5
                    task[1] = 502
            elif task[0] == 1:  # NEW_X — new iteration completed
                if isave[29] >= maxiter:
                    task[0] = 5
                    task[1] = 504
            else:
                break

        return x.copy(), float(f), nfev

    def search(self, x0: np.ndarray, max_feval: int = 1000, callback: Callable = None) -> tuple[np.ndarray, float, int]:

        try:
            # Probe gradient on first call (needs x0 to test)
            self._probe_gradient(x0)

            # Fast path: direct Fortran setulb (bypasses scipy wrapper overhead).
            # Used when: gradient is available (jac=True) and no callback needed
            # (PGlobal never uses callback on local searches).
            if self._setulb is not None and self._jac_arg is True and callback is None:
                return self._search_direct(x0, max_feval, self._objective_fn)

            # Fallback: scipy.optimize.minimize (handles FD gradient, callbacks, etc.)
            options = {
                "ftol": self._lbfgsb_params["ftol"],
                "gtol": self._lbfgsb_params["gtol"],
                "maxcor": self._lbfgsb_params["maxcor"],
                "maxfun": max_feval,
                "maxiter": max(100, max_feval // (self.dim + 1)),
            }

            if "eps" in self._lbfgsb_params:
                options["eps"] = self._lbfgsb_params["eps"]

            min_callback = None

            if callback:

                def min_callback(xk):

                    callback(xk)

            res = minimize(
                self._objective_fn,
                x0,
                method="L-BFGS-B",
                bounds=self._bounds_list,
                options=options,
                jac=self._jac_arg,
                callback=min_callback,
            )

            return res.x, float(res.fun), int(res.nfev)

        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            return x0.copy(), float(self.func(x0)), 1


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_critical_distance(n: int, dim: int, alpha: float) -> float:

    # Exact MLSL / Csendes Critical Distance:

    # r_k = pi^(-1/2) * [ Gamma(1 + d/2) * m(S) * sigma * log(n)/n ]^(1/d)

    # Since we normalize the space to the unit hypercube [0, 1]^d, the measure m(S) = 1.

    # 1. Use log-gamma to prevent float64 overflow in high dimensions (dim > 170)

    log_gamma = math.lgamma(1.0 + dim / 2.0)

    # log_val = log_gamma + log(alpha) + log(log(n)) - log(n)

    # Taking the (1/d) power becomes division by dim in log space

    if n <= 1:
        n = 2  # prevent log(log(1)) error

    log_val = log_gamma + math.log(alpha) + math.log(max(1e-12, math.log(float(n)))) - math.log(float(n))

    rk = (1.0 / math.sqrt(PI)) * math.exp(log_val / dim)

    # 2. Heuristic Csendes cap: max normalized distance in unit hypercube is sqrt(dim).

    # We should not cluster across more than half the hypercube diagonal.

    max_rk = math.sqrt(float(dim)) * 0.5

    if rk > max_rk:
        rk = max_rk

    return float(rk)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def fast_clustering_kernel(
    x_batch: np.ndarray,
    y_batch: np.ndarray,
    seeds_x: np.ndarray,
    seeds_y: np.ndarray,
    dc: float,
    bounds_min: np.ndarray,
    bounds_ptp: np.ndarray,
) -> np.ndarray:

    # Note: x_batch MUST be sorted by y_batch ascending before calling!

    n_batch = len(x_batch)

    n_seeds = len(seeds_x)

    cluster_ids = np.full(n_batch, -1, dtype=np.int32)

    dc_sq = dc * dc

    for i in prange(n_batch):
        # Strict MLSL condition: x_i launches local search UNLESS there is a

        # point x_j (seed or intra-batch point) such that f(x_j) < f(x_i) AND

        # normalized_distance(x_i, x_j) < d_c.

        min_dist_sq = 1e30

        best_seed = -1

        # 1. Compare against PREVIOUS iterations' local minima / seeds

        for j in range(n_seeds):
            if seeds_y[j] < y_batch[i]:  # Gradient condition (f_j < f_i)
                dist_sq = 0.0

                for k in range(x_batch.shape[1]):
                    d = (x_batch[i, k] - seeds_x[j, k]) / bounds_ptp[k]

                    dist_sq += d * d

                if dist_sq < dc_sq and dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq

                    best_seed = j

        # 2. Compare against BETTER points in the SAME batch (indexes j < i)

        # Since batch is sorted ascending by y, any j < i automatically satisfies f(x_j) <= f(x_i)

        # This prevents redundant local searches from the same batch mapping to the same basin!

        for j in range(i):
            dist_sq = 0.0

            for k in range(x_batch.shape[1]):
                d = (x_batch[i, k] - x_batch[j, k]) / bounds_ptp[k]

                dist_sq += d * d

            if dist_sq < dc_sq and dist_sq < min_dist_sq:
                min_dist_sq = dist_sq

                best_seed = -2  # -2 means "clustered within same batch"

        cluster_ids[i] = best_seed

    return cluster_ids


class SingleLinkageClusterer:
    """Strict MLSL / Single-linkage clustering for PGLOBAL"""

    _INITIAL_BUF_CAP = 256

    def __init__(self, bounds: np.ndarray, config: PGlobalConfig):

        self.bounds = bounds

        self.dim = len(bounds)

        self.bounds_min = np.ascontiguousarray(bounds[:, 0])

        self.bounds_ptp = np.ascontiguousarray(bounds[:, 1] - bounds[:, 0])

        # Prevent division by zero if bounds are identical

        self.bounds_ptp = np.maximum(self.bounds_ptp, 1e-12)

        self.config = config

        self.clusters: list[dict] = []

        # Pre-allocated doubling buffers for seeds (amortized O(1) append)
        self._seeds_x_buf = np.empty((self._INITIAL_BUF_CAP, self.dim), dtype=np.float64)
        self._seeds_y_buf = np.empty(self._INITIAL_BUF_CAP, dtype=np.float64)
        self._seeds_count = 0

        # Pre-allocated doubling buffers for unique basins
        self._basins_x_buf = np.empty((64, self.dim), dtype=np.float64)
        self._basins_y_buf = np.empty(64, dtype=np.float64)
        self._basins_count = 0

        self.total_local_searches_started = 0

        self._lock = RLock()

    # ── Property views into pre-allocated buffers (zero-copy) ──────────

    @property
    def x_seeds_cache(self) -> np.ndarray:
        return self._seeds_x_buf[: self._seeds_count]

    @property
    def y_seeds_cache(self) -> np.ndarray:
        return self._seeds_y_buf[: self._seeds_count]

    @property
    def unique_basins_x(self) -> np.ndarray:
        return self._basins_x_buf[: self._basins_count]

    @property
    def unique_basins_y(self) -> np.ndarray:
        return self._basins_y_buf[: self._basins_count]

    def process_batch(
        self, x_batch: np.ndarray, y_batch: np.ndarray, n_total_samples: int
    ) -> tuple[np.ndarray, np.ndarray]:

        if len(x_batch) == 0:
            return np.zeros((0, self.dim)), np.zeros(0)

        # Standard MLSL: points must be processed sequentially in ascending order of objective!

        # This allows multiple local starts in the same batch mapping to the same basin to be filtered out perfectly.

        sort_idx = np.argsort(y_batch)

        s_x_batch = x_batch[sort_idx]

        s_y_batch = y_batch[sort_idx]

        with self._lock:
            dc = compute_critical_distance(max(n_total_samples, 2), self.dim, self.config.alpha)

            # cluster_ids returns -1 if point should launch local search

            # >=0 if it clustered to a previous seed, -2 if it clustered to a better point in THIS batch

            cluster_ids = fast_clustering_kernel(
                s_x_batch, s_y_batch, self.x_seeds_cache, self.y_seeds_cache, dc, self.bounds_min, self.bounds_ptp
            )

            mask_unclustered = cluster_ids == -1

            # The unclustered points become seeds for future batches

            unclustered_x = s_x_batch[mask_unclustered]

            unclustered_y = s_y_batch[mask_unclustered]

            if len(unclustered_x) > 0:
                self._append_to_seeds(unclustered_x, unclustered_y)

            return unclustered_x, unclustered_y

    def add_cluster_result(self, x_local: np.ndarray, y_local: float):
        """

        Registers a completed L-BFGS-B local search.

        Identifies if it converged to a NEW unique basin or a KNOWN one.

        """

        with self._lock:
            self.total_local_searches_started += 1

            # 1. Add as a seed point so that future batches map to this minimum

            self._append_to_seeds(np.atleast_2d(x_local), np.array([y_local]))

            self.clusters.append({"x": x_local.copy(), "y": y_local})

            # 2. Add to unique basins if it's new (vectorized distance check)

            is_new_basin = True

            if self._basins_count > 0:
                by = self._basins_y_buf[: self._basins_count]
                y_tol = 1e-6 * max(abs(y_local), 1e-8)
                y_close = np.abs(by - y_local) < y_tol
                if np.any(y_close):
                    bx = self._basins_x_buf[: self._basins_count][y_close]
                    dx = (x_local - bx) / self.bounds_ptp
                    if np.any(np.sum(dx * dx, axis=1) < 1e-4):
                        is_new_basin = False

            if is_new_basin:
                self._append_to_basins(np.atleast_1d(x_local), float(y_local))

    def get_bayesian_estimate(self) -> tuple[float, float]:
        """

        Returns (Expected_Total_Minima, Expected_Undiscovered_Minima)

        using the precise Boender, Rinnooy Kan (1987) Bayesian stopping rule.

        Expectation E(W|w, N) = w(N-1) / (N-w-2)  for N > w + 2

        """

        with self._lock:
            w = float(len(self.unique_basins_y))

            N = float(self.total_local_searches_started)

            if N <= w + 2 or w == 0:
                return float("inf"), float("inf")

            expected_total = (w * (N - 1)) / (N - w - 2)

            expected_undiscovered = expected_total - w

            return expected_total, expected_undiscovered

    def _append_to_seeds(self, x_array: np.ndarray, y_array: np.ndarray):
        """Amortized O(1) append into pre-allocated doubling buffer."""
        x_new = np.atleast_2d(x_array)
        y_new = np.asarray(y_array, dtype=np.float64).ravel()
        n_new = x_new.shape[0]
        needed = self._seeds_count + n_new
        if needed > self._seeds_x_buf.shape[0]:
            new_cap = max(needed, self._seeds_x_buf.shape[0] * 2)
            new_xb = np.empty((new_cap, self.dim), dtype=np.float64)
            new_yb = np.empty(new_cap, dtype=np.float64)
            new_xb[: self._seeds_count] = self._seeds_x_buf[: self._seeds_count]
            new_yb[: self._seeds_count] = self._seeds_y_buf[: self._seeds_count]
            self._seeds_x_buf = new_xb
            self._seeds_y_buf = new_yb
        self._seeds_x_buf[self._seeds_count : self._seeds_count + n_new] = x_new
        self._seeds_y_buf[self._seeds_count : self._seeds_count + n_new] = y_new
        self._seeds_count += n_new

    def _append_to_basins(self, x_local: np.ndarray, y_local: float):
        """Amortized O(1) append into pre-allocated doubling buffer."""
        needed = self._basins_count + 1
        if needed > self._basins_x_buf.shape[0]:
            new_cap = max(needed, self._basins_x_buf.shape[0] * 2)
            new_xb = np.empty((new_cap, self.dim), dtype=np.float64)
            new_yb = np.empty(new_cap, dtype=np.float64)
            new_xb[: self._basins_count] = self._basins_x_buf[: self._basins_count]
            new_yb[: self._basins_count] = self._basins_y_buf[: self._basins_count]
            self._basins_x_buf = new_xb
            self._basins_y_buf = new_yb
        self._basins_x_buf[self._basins_count] = x_local
        self._basins_y_buf[self._basins_count] = y_local
        self._basins_count += 1

    def get_best_minimum(self):

        with self._lock:
            if self._basins_count == 0:
                return None

            idx = int(np.argmin(self._basins_y_buf[: self._basins_count]))

            return self._basins_x_buf[idx].copy(), float(self._basins_y_buf[idx])

    def clear(self):

        with self._lock:
            self.clusters.clear()

            self._seeds_count = 0
            self._seeds_x_buf = np.empty((self._INITIAL_BUF_CAP, self.dim), dtype=np.float64)
            self._seeds_y_buf = np.empty(self._INITIAL_BUF_CAP, dtype=np.float64)

            self._basins_count = 0
            self._basins_x_buf = np.empty((64, self.dim), dtype=np.float64)
            self._basins_y_buf = np.empty(64, dtype=np.float64)

            self.total_local_searches_started = 0


class PGlobalOptimizer:
    """

    PGLOBAL Global Optimizer - Multi-start stochastic global optimization.

    Algorithm (per iteration):

        1. Adaptive Sampling   - Latin-hypercube-like uniform draws, ×2 on first iter

        2. Batch Evaluation     - ThreadPoolExecutor (Numba nogil -> true parallelism)

        3. Reduction            - Keep top-% by objective value (argpartition)

        4. Single-Linkage Clustering - Filter points near known basins

        5. Parallel Local Searches   - L-BFGS-B from each unclustered candidate

        6. Stagnation Detection      - Track relative improvement

    Thread-safety:

        - Steps 2 and 5 run in ThreadPoolExecutor (nogil objective).

        - Global state (n_evals, _best_ever, clusterer) is updated

          synchronously *between* parallel sections, never concurrently.

    """

    # ── Constants ──────────────────────────────────────────────────────

    _MIN_LOCAL_BUDGET: int = 50  # Don't launch L-BFGS-B below this

    _SEQUENTIAL_THRESHOLD: int = 8  # Batch size below which threads are overhead

    _HIGH_DIM_THRESHOLD: int = 15  # Dimension above which we tighten reduction

    def __init__(
        self,
        objective: Callable,
        bounds: np.ndarray,
        config: PGlobalConfig | None = None,
        stop_event: Event | None = None,
        log_clues: list[int] | None = None,
        x0: np.ndarray | None = None,
        gradient_func: Callable | None = None,
    ):

        self.objective = objective

        self.bounds = np.asarray(bounds, dtype=np.float64)

        self.dim = len(bounds)

        self.config = config or PGlobalConfig()

        self.clusterer = SingleLinkageClusterer(self.bounds, self.config)

        self._stop_event = stop_event

        self.n_evals = 0

        seed = getattr(self.config, "random_seed", None)
        self.rng = np.random.default_rng(None if seed is None else int(seed))

        # Phase 2: Quasi-Random Sequence (Sobol)

        try:
            from scipy.stats import qmc

            # Scramble prevents identical grids across restarts while keeping low-discrepancy

            self.qmc_engine = qmc.Sobol(d=self.dim, scramble=True, seed=self.rng)

        except ImportError:
            self.qmc_engine = None

        self.x0 = x0

        self.log_clues = log_clues or []

        self._best_ever: Sample | None = None

        self.gradient_func = gradient_func

        # Cached searcher — created once, reused across all local searches
        self._searcher: LBFGSBSearcher | None = None

        # Worker count - computed once, reused across iterations

        self._n_workers = self._resolve_worker_count()

        # Persistent thread pool - created lazily on first parallel call

        self._pool = None

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_worker_count() -> int:
        """Determine thread-pool size (safe for frozen executables)."""

        import sys

        if getattr(sys, "frozen", False):
            try:
                from certus.core.certus_core import get_safe_worker_count

                return get_safe_worker_count()

            except ImportError:
                return 1

        return max(1, (os.cpu_count() or 4) - 2)

    def _is_stopped(self) -> bool:

        return bool(self._stop_event and self._stop_event.is_set())

    def _generate_samples(self, n: int) -> np.ndarray:
        """Draw *n* samples within bounds using Sobol Quasi-Random Sequences."""

        if self.qmc_engine is not None:
            # Generate low-discrepancy samples in [0, 1)^d

            # Scipy QMC Sobol expects n to be a power of 2 for perfect balance properties.

            # To avoid the warning and keep balance, we generate the next power of 2 and slice.

            import math

            n_pow2 = 2 ** math.ceil(math.log2(n)) if n > 0 else 0

            unit_samples = self.qmc_engine.random(n_pow2)[:n]

            # Scale to physical bounds manually to avoid extra scipy calls overhead if needed,

            # though scipy.stats.qmc.scale is also fine. Manual scaling is fast and numba-friendly if extracted.

            bounds_min = self.bounds[:, 0]

            bounds_ptp = self.bounds[:, 1] - bounds_min

            return unit_samples * bounds_ptp + bounds_min

        else:
            # Fallback to pseudo-random uniform

            return self.rng.uniform(self.bounds[:, 0], self.bounds[:, 1], (n, self.dim))

    # ── Step 2: Batch Evaluation ──────────────────────────────────────

    def _evaluate_batch(self, X: np.ndarray) -> np.ndarray:
        """

        Evaluate objective on *X* (n_points × dim).

        Prefers the objective's own ``evaluate_batch`` (BLAS-batched interpolation),

        then ThreadPoolExecutor, then sequential loop.

        """

        n = len(X)

        # Fast path: batched evaluation (shared interpolation matrix → dgemm)
        _eb = getattr(self.objective, "evaluate_batch", None)
        if _eb is not None:
            try:
                return np.asarray(_eb(X), dtype=np.float64)
            except (ValueError, TypeError, RuntimeError):
                pass  # Fallback to per-point

        Y = np.empty(n, dtype=np.float64)

        if n <= self._SEQUENTIAL_THRESHOLD or self._n_workers <= 1:
            for i in range(n):
                Y[i] = self.objective(X[i])

        else:
            pool = self._get_pool()

            for i, val in enumerate(pool.map(self.objective, X)):
                Y[i] = val

        return Y

    # ── Step 5: Local Search Dispatch ─────────────────────────────────

    def _build_dispatch_tasks(
        self, cand_x: np.ndarray, cand_y: np.ndarray, iteration: int
    ) -> list[tuple[np.ndarray, int]]:
        """

        Select unclustered candidates and pair each with a L-BFGS-B budget.

        Returns:

            List of (x_start, budget) tuples ready for parallel dispatch.

        """

        idx_sorted = np.argsort(cand_y)

        # Dispatch proportional to config.max_active_clusters, enabling deep search of multiple basins

        base_dispatch = max(20, self.config.max_active_clusters)

        decay = 0.97**iteration

        n_dispatch = min(len(cand_y), max(5, int(base_dispatch * decay)))

        tasks: list[tuple[np.ndarray, int]] = []

        for k in range(n_dispatch):
            if self._is_stopped():
                break

            x_k = cand_x[idx_sorted[k]]

            # Top candidates (k=0) get 130% budget; bottom get 70%
            budget_factor = 0.7 + 0.6 * (1.0 - k / max(n_dispatch, 1))

            budget = int(self.config.local_search_budget * budget_factor)

            if budget >= self._MIN_LOCAL_BUDGET:
                tasks.append((x_k, budget))

        return tasks

    def _get_searcher(self) -> LBFGSBSearcher:
        """Return cached LBFGSBSearcher (bounds list + lbfgsb params computed once)."""
        if self._searcher is None:
            self._searcher = LBFGSBSearcher(self.objective, self.bounds, self.config, self.gradient_func)
        return self._searcher

    def _run_local_search(self, task: tuple[np.ndarray, int]) -> tuple[np.ndarray, float, int] | None:
        """Execute a single L-BFGS-B local search (designed to run in a thread)."""

        if self._is_stopped():
            return None

        x_start, budget = task

        try:
            x_opt, f_opt, n_ev = self._get_searcher().search(x_start, budget)

            return (x_opt, f_opt, n_ev)

        except (ValueError, RuntimeError):
            return None

    def _dispatch_and_collect(
        self,
        tasks: list[tuple[np.ndarray, int]],
        iteration: int,
        best_ever_y: float,
        stagnation_counter: int,
        callback: Callable | None,
    ) -> tuple[float, int]:
        """

        Run all local-search tasks in parallel, process results as they

        complete (as_completed) for better load balancing and earlier

        best-ever updates.

        Returns:

            Updated (best_ever_y, stagnation_counter).

        """

        from concurrent.futures import as_completed

        pool = self._get_pool()

        futures = {pool.submit(self._run_local_search, t): t for t in tasks}

        for future in as_completed(futures):
            if self._is_stopped():
                break

            try:
                res = future.result()
            except (ValueError, RuntimeError, TypeError, ArithmeticError):
                continue

            if res is None:
                continue

            x_opt, f_opt, local_evals = res

            self.n_evals += local_evals

            self.clusterer.add_cluster_result(x_opt, f_opt)

            if self._best_ever is None or f_opt < self._best_ever.y:
                self._best_ever = Sample(x_opt.copy(), f_opt, iteration)

                best_ever_y = f_opt

                stagnation_counter = 0

                if callback:
                    callback(self._best_ever)

        return best_ever_y, stagnation_counter

    # ── Main Loop ─────────────────────────────────────────────────────

    def _get_pool(self):
        """Return persistent thread pool, creating it lazily on first use."""

        if self._pool is None:
            from concurrent.futures import ThreadPoolExecutor

            self._pool = ThreadPoolExecutor(max_workers=self._n_workers)

        return self._pool

    def _shutdown_pool(self):
        """Shutdown the persistent thread pool if it exists."""

        if self._pool is not None:
            self._pool.shutdown(wait=False)

            self._pool = None

    def optimize(self, max_iter: int = 50, callback: Callable | None = None) -> Sample | None:
        """

        Run the PGLOBAL optimization loop.

        Args:

            max_iter: Maximum number of sampling iterations.

            callback: Optional ``callback(Sample)`` for progress reporting.

        Returns:

            Best :class:`Sample` found, or *None* if no feasible point exists.

        """

        import time

        best_ever_y = float("inf")

        stagnation_counter = 0

        last_best_y = float("inf")

        n_samples_iter = self.config.n_samples_per_iter

        start_time = time.time()

        for iteration in range(max_iter):
            # ── Termination checks ────────────────────────────────

            if self._is_stopped():
                break

            if self.n_evals >= self.config.max_feval:
                break

            if time.time() - start_time > self.config.max_time:
                break

            # ── 1. Adaptive Sampling ──────────────────────────────

            adaptive_factor = 1.0 + 0.5 * (1.0 - iteration / max_iter)

            current_n = int(n_samples_iter * adaptive_factor)

            if iteration == 0:
                current_n *= 2  # Bootstrap: double first batch

            # ── 2. Generation & Evaluation ────────────────────────

            X_batch = self._generate_samples(current_n)

            Y_batch = self._evaluate_batch(X_batch)

            self.n_evals += len(X_batch)

            # ── 3. Reduction ──────────────────────────────────────

            ratio = self.config.reduction_ratio

            if self.dim > self._HIGH_DIM_THRESHOLD:
                ratio = min(0.25, ratio * 1.5)

            n_keep = max(int(current_n * ratio), 10)

            if n_keep < len(Y_batch):
                idx_best = np.argpartition(Y_batch, n_keep)[:n_keep]

            else:
                idx_best = np.arange(len(Y_batch))

            X_reduced = X_batch[idx_best]

            Y_reduced = Y_batch[idx_best]

            # ── 4. Single-Linkage Clustering ──────────────────────

            cand_x, cand_y = self.clusterer.process_batch(X_reduced, Y_reduced, self.n_evals)

            # Progress callback (best-in-batch, pre-local-search)

            best_idx = np.argmin(Y_batch)

            f_best = Y_batch[best_idx]

            if f_best < best_ever_y and callback and iteration % 2 == 0:
                callback(Sample(X_batch[best_idx], f_best, iteration))

            # ── 5. Parallel Local Searches ────────────────────────

            if len(cand_y) > 0 and not self._is_stopped() and self.n_evals < self.config.max_feval:
                tasks = self._build_dispatch_tasks(cand_x, cand_y, iteration)

                if tasks:
                    best_ever_y, stagnation_counter = self._dispatch_and_collect(
                        tasks, iteration, best_ever_y, stagnation_counter, callback
                    )

            # ── 6. Bayesian Stopping Rule ─────────────────────────

            _exp_tot, expected_undiscovered = self.clusterer.get_bayesian_estimate()

            if expected_undiscovered <= 0.5:
                # We expect less than 0.5 unobserved local minima left! We can safely terminate global search.

                # In standard Bayesian statistics this equates to high confidence that all minima have been found.

                break

            # ── 7. Stagnation Detection ───────────────────────────

            if self._best_ever:
                curr_best = self._best_ever.y

                if abs(curr_best - last_best_y) < 1e-8 * max(abs(curr_best), 1e-10):
                    stagnation_counter += 1

                else:
                    stagnation_counter = 0

                last_best_y = curr_best

                # Heuristic fallback if Bayesian stopping doesn't trigger

                if stagnation_counter >= 8:
                    break

        self._shutdown_pool()

        return self._best_ever


# =============================================================================


# COLORIMETRY


# =============================================================================


CIE_LAMBDA = np.arange(380, 781, 5, dtype=np.float64)


CIE_X = np.array(
    [
        0.0014,
        0.0022,
        0.0042,
        0.0076,
        0.0143,
        0.0232,
        0.0435,
        0.0776,
        0.1344,
        0.2148,
        0.3230,
        0.4479,
        0.5970,
        0.7621,
        0.9163,
        1.0263,
        1.0622,
        1.0456,
        1.0026,
        0.9564,
        0.9154,
        0.8634,
        0.7889,
        0.6954,
        0.5945,
        0.4900,
        0.3856,
        0.2899,
        0.2091,
        0.1484,
        0.1041,
        0.0734,
        0.0514,
        0.0358,
        0.0249,
        0.0172,
        0.0117,
        0.0081,
        0.0058,
        0.0045,
        0.0036,
        0.0029,
        0.0024,
        0.0020,
        0.0017,
        0.0014,
        0.0011,
        0.0009,
        0.0007,
        0.0005,
        0.0004,
        0.0003,
        0.0002,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


CIE_Y = np.array(
    [
        0.0000,
        0.0001,
        0.0001,
        0.0002,
        0.0004,
        0.0006,
        0.0012,
        0.0022,
        0.0040,
        0.0073,
        0.0129,
        0.0230,
        0.0380,
        0.0600,
        0.0910,
        0.1390,
        0.2080,
        0.3230,
        0.5030,
        0.7100,
        0.8620,
        0.9540,
        0.9950,
        0.9950,
        0.9520,
        0.8700,
        0.7570,
        0.6310,
        0.5030,
        0.3810,
        0.2650,
        0.1750,
        0.1170,
        0.0782,
        0.0526,
        0.0353,
        0.0231,
        0.0154,
        0.0106,
        0.0074,
        0.0053,
        0.0039,
        0.0029,
        0.0021,
        0.0016,
        0.0012,
        0.0008,
        0.0006,
        0.0004,
        0.0003,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


CIE_Z = np.array(
    [
        0.0065,
        0.0105,
        0.0201,
        0.0362,
        0.0679,
        0.1102,
        0.2074,
        0.3713,
        0.6456,
        1.0391,
        1.5281,
        2.0561,
        2.5861,
        3.0781,
        3.4828,
        3.7008,
        3.6551,
        3.4481,
        3.1870,
        2.9080,
        2.6480,
        2.3481,
        1.9961,
        1.6361,
        1.2880,
        0.9693,
        0.6934,
        0.4692,
        0.3162,
        0.2120,
        0.1419,
        0.0954,
        0.0640,
        0.0426,
        0.0283,
        0.0188,
        0.0125,
        0.0084,
        0.0057,
        0.0041,
        0.0031,
        0.0023,
        0.0018,
        0.0014,
        0.0011,
        0.0009,
        0.0006,
        0.0005,
        0.0003,
        0.0002,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


D65 = np.array(
    [
        49.9755,
        52.3118,
        54.6482,
        68.7015,
        82.7549,
        87.1204,
        91.486,
        92.4589,
        93.4318,
        90.057,
        86.6823,
        95.7736,
        104.865,
        110.936,
        117.008,
        117.41,
        117.812,
        116.336,
        114.861,
        115.392,
        115.923,
        112.367,
        108.811,
        109.082,
        109.354,
        108.578,
        107.802,
        106.296,
        104.79,
        106.239,
        107.689,
        106.047,
        104.405,
        104.225,
        104.046,
        102.023,
        100.0,
        98.1671,
        96.3342,
        96.0611,
        95.788,
        92.2368,
        88.6856,
        89.3459,
        90.0062,
        89.8026,
        89.5991,
        88.6489,
        87.6987,
        85.4936,
        83.2886,
        83.4939,
        83.6992,
        81.863,
        80.0268,
        80.1207,
        80.2146,
        81.2462,
        82.2778,
        80.281,
        78.2842,
        74.0027,
        69.7213,
        70.6652,
        71.6091,
        72.979,
        74.349,
        67.9765,
        61.604,
        65.7448,
        69.8856,
        72.4863,
        75.087,
        69.3398,
        63.5927,
        55.0054,
        46.4182,
        56.6118,
        66.8054,
        65.0941,
        63.3828,
    ],
    dtype=np.float64,
)


XYZ_N = np.array([95.047, 100.0, 108.883], dtype=np.float64)


XYZ_TO_RGB = np.array(
    [
        [3.2404542, -1.5371385, -0.4985314],
        [-0.9692660, 1.8760108, 0.0415560],
        [0.0556434, -0.2040259, 1.0572252],
    ],
    dtype=np.float64,
)


D65_CIE_X = D65 * CIE_X


D65_CIE_Y = D65 * CIE_Y


D65_CIE_Z = D65 * CIE_Z


_denom_y = np.sum(D65_CIE_Y)


K_COLOR = 100.0 / _denom_y if _denom_y != 0 else 0.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _xyz_from_spectrum_kernel(
    R_interp: np.ndarray,
    D65_X: np.ndarray,
    D65_Y: np.ndarray,
    D65_Z: np.ndarray,
    k_color: float,
) -> tuple[float, float, float]:
    """JIT kernel for XYZ tristimulus computation."""

    X = 0.0

    Y = 0.0

    Z = 0.0

    for i in range(len(R_interp)):
        X += R_interp[i] * D65_X[i]

        Y += R_interp[i] * D65_Y[i]

        Z += R_interp[i] * D65_Z[i]

    return k_color * X, k_color * Y, k_color * Z


def xyz_from_spectrum(wls: np.ndarray, R: np.ndarray) -> np.ndarray:

    R_interp = np.interp(CIE_LAMBDA, wls, R)

    X, Y, Z = _xyz_from_spectrum_kernel(R_interp, D65_CIE_X, D65_CIE_Y, D65_CIE_Z, K_COLOR)

    return np.array([X, Y, Z])


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _lab_f(t: float) -> float:
    """CIE Lab f() function - JIT scalar."""

    delta = 6.0 / 29.0

    if t > delta * delta * delta:
        return t ** (1.0 / 3.0)

    return t / (3.0 * delta * delta) + 4.0 / 29.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _lab_f_inv(t: float) -> float:
    """CIE Lab f_inv() function - JIT scalar."""

    delta = 6.0 / 29.0

    if t > delta:
        return t * t * t

    return 3.0 * delta * delta * (t - 4.0 / 29.0)


def xyz_to_lab(xyz_val: np.ndarray) -> np.ndarray:

    xyz_norm = xyz_val / XYZ_N

    fx = _lab_f(xyz_norm[0])

    fy = _lab_f(xyz_norm[1])

    fz = _lab_f(xyz_norm[2])

    L = 116.0 * fy - 16.0

    a = 500.0 * (fx - fy)

    b = 200.0 * (fy - fz)

    return np.array([L, a, b])


def lab_to_xyz(lab_val: np.ndarray) -> np.ndarray:

    L, a, b = lab_val

    fy = (L + 16.0) / 116.0

    fx = a / 500.0 + fy

    fz = fy - b / 200.0

    xyz = XYZ_N * np.array([_lab_f_inv(fx), _lab_f_inv(fy), _lab_f_inv(fz)])

    return xyz


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _gamma_correct_scalar(c: float) -> float:
    """sRGB gamma correction - JIT scalar."""

    c_safe = max(c, 0.0)

    if c_safe <= 0.0031308:
        return 12.92 * c_safe

    return 1.055 * (c_safe ** (1.0 / 2.4)) - 0.055


def lab_to_rgb(lab_val: np.ndarray) -> np.ndarray:

    xyz = lab_to_xyz(lab_val)

    rgb_linear = XYZ_TO_RGB @ (xyz / 100.0)

    rgb_gamma = np.array(
        [
            _gamma_correct_scalar(rgb_linear[0]),
            _gamma_correct_scalar(rgb_linear[1]),
            _gamma_correct_scalar(rgb_linear[2]),
        ]
    )

    return np.clip(rgb_gamma * 255.0, 0.0, 255.0).astype(np.int32)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
    """CIE DeltaE 2000 - fully JIT-compiled."""

    L1 = lab1[0]

    a1 = lab1[1]

    b1 = lab1[2]

    L2 = lab2[0]

    a2 = lab2[1]

    b2 = lab2[2]

    C1 = np.sqrt(a1 * a1 + b1 * b1)

    C2 = np.sqrt(a2 * a2 + b2 * b2)

    C_avg = (C1 + C2) / 2.0

    C_avg7 = C_avg**7

    G = 0.5 * (1.0 - np.sqrt(C_avg7 / (C_avg7 + 25.0**7)))

    a1p = a1 * (1.0 + G)

    a2p = a2 * (1.0 + G)

    C1p = np.sqrt(a1p * a1p + b1 * b1)

    C2p = np.sqrt(a2p * a2p + b2 * b2)

    TWO_PI_VAL = 2.0 * np.pi

    h1p = np.arctan2(b1, a1p) % TWO_PI_VAL

    h2p = np.arctan2(b2, a2p) % TWO_PI_VAL

    dL = L2 - L1

    dC = C2p - C1p

    if C1p * C2p == 0.0:
        dh = 0.0

    else:
        diff = h2p - h1p

        if abs(diff) <= np.pi:
            dh = diff

        elif diff > np.pi:
            dh = diff - TWO_PI_VAL

        else:
            dh = diff + TWO_PI_VAL

    dH = 2.0 * np.sqrt(C1p * C2p) * np.sin(dh / 2.0)

    L_avg = (L1 + L2) / 2.0

    C_avgp = (C1p + C2p) / 2.0

    if C1p * C2p == 0.0:
        h_avgp = h1p + h2p

    else:
        if abs(h1p - h2p) <= np.pi:
            h_avgp = (h1p + h2p) / 2.0

        elif h1p + h2p < TWO_PI_VAL:
            h_avgp = (h1p + h2p + TWO_PI_VAL) / 2.0

        else:
            h_avgp = (h1p + h2p - TWO_PI_VAL) / 2.0

    T = (
        1.0
        - 0.17 * np.cos(h_avgp - np.pi / 6.0)
        + 0.24 * np.cos(2.0 * h_avgp)
        + 0.32 * np.cos(3.0 * h_avgp + np.pi / 30.0)
        - 0.20 * np.cos(4.0 * h_avgp - 63.0 * np.pi / 180.0)
    )

    L_avg_m50 = L_avg - 50.0

    SL = 1.0 + (0.015 * L_avg_m50 * L_avg_m50) / np.sqrt(20.0 + L_avg_m50 * L_avg_m50)

    SC = 1.0 + 0.045 * C_avgp

    SH = 1.0 + 0.015 * C_avgp * T

    C_avgp7 = C_avgp**7

    RC = 2.0 * np.sqrt(C_avgp7 / (C_avgp7 + 25.0**7))

    delta_theta = 30.0 * np.exp(-(((h_avgp * 180.0 / np.pi - 275.0) / 25.0) ** 2))

    RT = -RC * np.sin(2.0 * delta_theta * np.pi / 180.0)

    return np.sqrt((dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2 + RT * (dC / SC) * (dH / SH))


# =============================================================================


# =========================================================================================


# [MONOLITHIC BLOCK] MATERIAL DATABASE


# DO NOT SPLIT - Interpolation kernels required by all modules


# =========================================================================================


# INTERPOLATION UTILS & MATERIAL DATABASE


# =============================================================================


# OPENPYXL_AVAILABLE imported from certus.core.certus_core at top of file


CACHE_SIZE_MATERIAL_INDEX = 1000


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def numba_interp_scalar(x: float, xp: np.ndarray, fp: np.ndarray) -> float:
    """Optimized scalar linear interpolation."""

    n = len(xp)

    if n == 0:
        return np.nan

    if n == 1:
        return fp[0]

    if x <= xp[0]:
        slope = (fp[1] - fp[0]) / (xp[1] - xp[0])

        return fp[0] + slope * (x - xp[0])

    if x >= xp[-1]:
        slope = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])

        return fp[-1] + slope * (x - xp[-1])

    idx = np.searchsorted(xp, x)

    if idx == 0:
        return fp[0]

    x0, x1 = xp[idx - 1], xp[idx]

    y0, y1 = fp[idx - 1], fp[idx]

    t = (x - x0) / (x1 - x0)

    return y0 + t * (y1 - y0)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def numba_interp_vectorized(x_arr: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """Parallel vectorized linear interpolation"""

    n = len(x_arr)

    result = np.empty(n, dtype=np.float64)

    for i in prange(n):
        result[i] = numba_interp_scalar(x_arr[i], xp, fp)

    return result


class MaterialDatabase:
    """Thread-safe material DB with smart cache (Robust wrapper to prevent substrate/material cross-loading)"""

    def __init__(self, filepath: str = "clues.xlsx"):
        from certus.utils.certus_strat_db import RobustMaterialDatabase
        self._db = RobustMaterialDatabase(filepath)
        self._interpolation_cache = {}
        self._substrate_cache = {}
        self._computation_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def data(self) -> dict[str, dict[str, Any]]:
        return self._db.materials

    @property
    def _data(self):
        return self._db.materials

    @_data.setter
    def _data(self, value):
        self._db.materials = value

    def get_index(self, material_name: str, wavelength_nm: float) -> float:
        wl_rounded = round(wavelength_nm, 2)
        cache_key = (material_name, wl_rounded)
        if cache_key in self._interpolation_cache:
            return self._interpolation_cache[cache_key]

        # Standard get_index only returns real part (float) of layer material
        val = self._db.get_refractive_index(material_name, wavelength_nm)
        n_val = float(val.real)
        self._interpolation_cache[cache_key] = n_val
        return n_val

    def get_clues_vectorized(self, material_name: str, wavelengths: np.ndarray) -> np.ndarray:
        # Standard get_clues_vectorized only returns real parts (float) of layer material
        val = self._db.get_refractive_clues_vectorized(material_name, wavelengths)
        return val.real

    def clear_cache(self):
        self._interpolation_cache.clear()

    def get_material_list(self) -> list[str]:
        return list(self._db.materials.keys())

    def get_wavelength_range(self, material_name: str) -> tuple[float, float]:
        if material_name not in self._db.materials:
            raise ValueError(f"Material '{material_name}' not found")
        mat = self._db.materials[material_name]
        return float(mat["wl"][0]), float(mat["wl"][-1])

    @property
    def substrate_cache(self) -> dict:
        return self._substrate_cache

    def get_cached_computation(self, key: str, compute_func: Callable, *args, **kwargs):
        if key in self._computation_cache:
            self._cache_hits += 1
            return self._computation_cache[key]
        result = compute_func(*args, **kwargs)
        self._computation_cache[key] = result
        self._cache_misses += 1
        return result

    def get_cache_stats(self) -> dict:
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._computation_cache),
        }




# =============================================================================


# ADDITIONAL PHYSICS KERNELS


# =============================================================================


# --- LOCKED --- Validated by test_tmm_coherence.py + test_tmm_inline.py (tests 0, 0b, 5) ───


# Macleod convention: n̂ = n - ik. Single source generic TMM.


# DO NOT MODIFY without running tests.


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


# --- LOCKED --- Validated by test_energy_conservation.py + test_tmm_coherence.py ───


# Single source R/T extraction. DO NOT MODIFY without running tests.


#


# ╔══════════════════════════════════════════════════════════════════════╗


# ║  FORMULA T - Macleod 4th ed. (semi-infinite substrate)                 ║


# ║                                                                      ║


# ║  T = Re(η_exit) / Re(η_inc) * |t|²                                 ║


# ║  t = 2·η_inc / (η_inc·B + C)                                       ║


# ║  R = |r|²,  r = (η_inc·B - C) / (η_inc·B + C)                     ║


# ║                                                                      ║


# ║  CONVENTION CRITIQUE: n̂ = n - ik  (k >= 0 for absorption)         ║


# ║  If n̂ = n + ik is used, R+T > 1 (non-physical gain).          ║


# ║  DO NOT REVERSE THE CONVENTION.                                     ║


# ╚══════════════════════════════════════════════════════════════════════╝


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


# --- LOCKED --- Validated by test_tmm_inline.py (test 4) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


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


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j, n-ik). DO NOT MODIFY without running tests.


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





# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


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


# _calculate_reflection_single_gradient removed (Dead Code)


# --- LOCKED --- Validated by test_gradient_vs_fd.py (via _compute_tlu_derivatives_kernel) ───


# Tauc-Lorentz model ε₂ + analytic derivatives. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_epsilon2_gradient_kernel(
    E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, Eu: float
) -> np.ndarray:
    """Computes [eps2, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]"""

    n = len(E_array)

    result = np.zeros((7, n), dtype=np.float64)

    E0_sq = E0 * E0

    C_sq = C * C

    A_E0_C = A * E0 * C

    delta = 0.01

    E_edge = Eg + delta

    E_edge_sq = E_edge * E_edge

    term_E0 = E_edge_sq - E0_sq

    D_edge = term_E0 * term_E0 + C_sq * E_edge_sq

    inv_D_edge = 1.0 / D_edge

    num_edge = A_E0_C * delta * delta

    eps2_edge = (num_edge * inv_D_edge / E_edge) if E_edge > 1e-12 else 0.0

    dDedge_dEg = 4.0 * term_E0 * E_edge + 2.0 * C_sq * E_edge

    dDedge_dE0 = -4.0 * E0 * term_E0

    dDedge_dC = 2.0 * C * E_edge_sq

    if eps2_edge > 1e-12:
        d_eps2_edge_dEg = eps2_edge * (-dDedge_dEg * inv_D_edge - 1.0 / E_edge)

        d_eps2_edge_dA = eps2_edge * (1.0 / A)

        d_eps2_edge_dE0 = eps2_edge * (1.0 / E0 - dDedge_dE0 * inv_D_edge)

        d_eps2_edge_dC = eps2_edge * (1.0 / C - dDedge_dC * inv_D_edge)

    else:
        d_eps2_edge_dEg = 0.0

        d_eps2_edge_dA = 0.0

        d_eps2_edge_dE0 = 0.0

        d_eps2_edge_dC = 0.0

    Eu_safe = max(Eu, 1e-6)

    inv_Eu = 1.0 / Eu_safe

    for i in prange(n):
        E = E_array[i]

        if E > Eg:
            E_sq = E * E

            diff = E - Eg

            diff_sq = diff * diff

            term_E0_loc = E_sq - E0_sq

            D = term_E0_loc * term_E0_loc + C_sq * E_sq

            inv_D = 1.0 / D

            val = (A_E0_C * diff_sq) * inv_D / E

            result[0, i] = val

            if val > 1e-12:
                result[1, i] = val * (-2.0 / diff)

                result[2, i] = val / A

                dD_dE0 = -4.0 * E0 * term_E0_loc

                result[3, i] = val * (1.0 / E0 - dD_dE0 * inv_D)

                dD_dC = 2.0 * C * E_sq

                result[4, i] = val * (1.0 / C - dD_dC * inv_D)

        else:
            if eps2_edge < 1e-12:
                result[0, i] = 0.0

            else:
                arg = (E - Eg - delta) * inv_Eu

                exp_val = np.exp(arg)

                val = eps2_edge * exp_val

                result[0, i] = val

                result[1, i] = d_eps2_edge_dEg * exp_val + val * (-inv_Eu)

                result[2, i] = d_eps2_edge_dA * exp_val

                result[3, i] = d_eps2_edge_dE0 * exp_val

                result[4, i] = d_eps2_edge_dC * exp_val

                result[5, i] = val * (-arg * inv_Eu)

    return result


# --- LOCKED --- Validated by test_gradient_vs_fd.py (via _compute_tlu_derivatives_kernel) ───


# Kramers-Kronig ε₁ analytic + derivatives. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_epsilon1_gradient_kernel(
    E_array: np.ndarray, Eg: float, A: float, E0: float, C: float, eps_inf: float
) -> np.ndarray:
    """Computes [eps1, d/dEg, d/dA, d/dE0, d/dC, d/dEu, d/deps_inf]"""

    n = len(E_array)

    result = np.zeros((7, n), dtype=np.float64)

    E0_sq = E0 * E0

    Eg_sq = Eg * Eg

    C_sq = C * C

    gamma_sq = E0_sq - C_sq / 2.0

    alpha_sq = max(4.0 * E0_sq - C_sq, 1e-12)

    alpha = np.sqrt(alpha_sq)

    d_alpha_dE0 = (4.0 * E0 / alpha) if alpha > 1e-12 else 0.0

    d_alpha_dC = (-C / alpha) if alpha > 1e-12 else 0.0

    d_gamma2_dE0 = 2.0 * E0

    d_gamma2_dC = -C

    denom_log_norm_sq = (E0_sq - Eg_sq) ** 2 + C_sq * Eg_sq

    # If Eg or C are extremely small (>0 but subnormal), the sum of squares can
    # round to 0 and cause a division by zero on inv_denom_log_norm (see L-BFGS-B outside realistic bounds).
    denom_log_norm_sq = max(denom_log_norm_sq, 1e-120)

    denom_log_norm = np.sqrt(denom_log_norm_sq)

    inv_denom_log_norm = 1.0 / denom_log_norm

    d_DLN2_dEg = -4.0 * Eg * (E0_sq - Eg_sq) + 2.0 * Eg * C_sq

    d_DLN2_dE0 = 4.0 * E0 * (E0_sq - Eg_sq)

    d_DLN2_dC = 2.0 * C * Eg_sq

    d_DLN_dEg = 0.5 * inv_denom_log_norm * d_DLN2_dEg

    d_DLN_dE0 = 0.5 * inv_denom_log_norm * d_DLN2_dE0

    d_DLN_dC = 0.5 * inv_denom_log_norm * d_DLN2_dC

    A_E0_C = A * E0 * C

    two_A_E0_C_Eg = 2.0 * A_E0_C * Eg

    inv_PI = 1.0 / PI

    for i in prange(n):
        E = E_array[i]

        E_sq = E * E

        zeta4 = (E_sq - E0_sq) ** 2 + C_sq * E_sq

        zeta4 = max(zeta4, 1e-12)

        inv_zeta4 = 1.0 / zeta4

        d_zeta4_dE0 = -4.0 * E0 * (E_sq - E0_sq)

        d_zeta4_dC = 2.0 * C * E_sq

        diff_sq = Eg_sq - E_sq

        # Log1 / Log2 : singularities if E == Eg (diff_sq -> 0) or numerical quasi-degeneracy.

        _diff_eps = 1e-14

        # Log1

        val_log1 = 0.0

        d_log1_dEg = 0.0

        if E != Eg:
            arg_log1 = np.abs((Eg - E) / (Eg + E))

            val_log1 = np.log(arg_log1) if arg_log1 > 0 else -100.0

            if np.abs(diff_sq) > _diff_eps:
                d_log1_dEg = 2.0 * E / diff_sq

            else:
                d_log1_dEg = 0.0

        # Log2

        arg_log2 = np.abs(diff_sq)

        val_log2_part = np.log(arg_log2) if arg_log2 > 0 else -100.0

        val_log2 = val_log2_part - np.log(denom_log_norm)

        if np.abs(diff_sq) > _diff_eps:
            d_log2_dEg = 2.0 * Eg / diff_sq - d_DLN_dEg * inv_denom_log_norm

        else:
            d_log2_dEg = -d_DLN_dEg * inv_denom_log_norm

        d_log2_dE0 = -d_DLN_dE0 * inv_denom_log_norm

        d_log2_dC = -d_DLN_dC * inv_denom_log_norm

        # al, aa

        al = (Eg_sq - E0_sq) * E_sq + Eg_sq * C_sq - E0_sq * (E0_sq + 3.0 * Eg_sq)

        d_al_dEg = 2 * Eg * E_sq + 2 * Eg * C_sq - E0_sq * 6.0 * Eg

        d_al_dE0 = -2 * E0 * E_sq - (4.0 * E0**3 + 6.0 * E0 * Eg_sq)

        d_al_dC = Eg_sq * 2.0 * C

        aa = (E_sq - E0_sq) * (E0_sq + Eg_sq) + Eg_sq * C_sq

        d_aa_dEg = (E_sq - E0_sq) * 2.0 * Eg + 2.0 * Eg * C_sq

        d_aa_dE0 = (-2 * E0) * (E0_sq + Eg_sq) + (E_sq - E0_sq) * (2 * E0)

        d_aa_dC = Eg_sq * 2.0 * C

        # Term 1

        E_safe = max(E, 1e-18)

        K1 = -A_E0_C * inv_PI / E_safe

        T1 = K1 * (E_sq + Eg_sq) * inv_zeta4 * val_log1

        dT1_dA = T1 / A

        dT1_dEg = K1 * (2.0 * Eg * inv_zeta4 * val_log1 + (E_sq + Eg_sq) * inv_zeta4 * d_log1_dEg)

        dT1_dE0 = (K1 / E0) * (E_sq + Eg_sq) * inv_zeta4 * val_log1 + K1 * (E_sq + Eg_sq) * (
            -(inv_zeta4**2) * d_zeta4_dE0
        ) * val_log1

        dT1_dC = (K1 / C) * (E_sq + Eg_sq) * inv_zeta4 * val_log1 + K1 * (E_sq + Eg_sq) * (
            -(inv_zeta4**2) * d_zeta4_dC
        ) * val_log1

        # Term 2

        K2 = two_A_E0_C_Eg * inv_PI

        T2 = K2 * inv_zeta4 * val_log2

        dT2_dA = T2 / A

        dT2_dEg = (K2 / Eg) * inv_zeta4 * val_log2 + K2 * inv_zeta4 * d_log2_dEg

        dT2_dE0 = (
            (K2 / E0) * inv_zeta4 * val_log2
            + K2 * (-(inv_zeta4**2) * d_zeta4_dE0) * val_log2
            + K2 * inv_zeta4 * d_log2_dE0
        )

        dT2_dC = (
            (K2 / C) * inv_zeta4 * val_log2
            + K2 * (-(inv_zeta4**2) * d_zeta4_dC) * val_log2
            + K2 * inv_zeta4 * d_log2_dC
        )

        # Term 3

        T3 = 0.0

        dT3_dA = 0.0

        dT3_dEg = 0.0

        dT3_dE0 = 0.0

        dT3_dC = 0.0

        if alpha > 1e-12:
            arg3 = (E0_sq + Eg_sq + alpha * Eg) / (E0_sq + Eg_sq - alpha * Eg)

            val_log3 = np.log(arg3)

            pre = (A * C) / (2.0 * PI)

            denom_T3 = zeta4 * alpha * E0

            term_frac = al / denom_T3

            T3 = pre * term_frac * val_log3

            N3 = E0_sq + Eg_sq + alpha * Eg

            D3 = E0_sq + Eg_sq - alpha * Eg

            dN3_dEg = 2 * Eg + alpha

            dD3_dEg = 2 * Eg - alpha

            dN3_dE0 = 2 * E0 + d_alpha_dE0 * Eg

            dD3_dE0 = 2 * E0 - d_alpha_dE0 * Eg

            dN3_dC = d_alpha_dC * Eg

            dD3_dC = -d_alpha_dC * Eg

            d_log3_dEg = dN3_dEg / N3 - dD3_dEg / D3

            d_log3_dE0 = dN3_dE0 / N3 - dD3_dE0 / D3

            d_log3_dC = dN3_dC / N3 - dD3_dC / D3

            dT3_dA = T3 / A

            dT3_dEg = pre * (d_al_dEg / denom_T3) * val_log3 + pre * term_frac * d_log3_dEg

            d_denomT3_dE0 = d_zeta4_dE0 * alpha * E0 + zeta4 * d_alpha_dE0 * E0 + zeta4 * alpha

            d_term_frac_dE0 = (d_al_dE0 * denom_T3 - al * d_denomT3_dE0) / (denom_T3**2)

            dT3_dE0 = pre * d_term_frac_dE0 * val_log3 + pre * term_frac * d_log3_dE0

            d_denomT3_dC = d_zeta4_dC * alpha * E0 + zeta4 * d_alpha_dC * E0

            d_term_frac_dC = (d_al_dC * denom_T3 - al * d_denomT3_dC) / (denom_T3**2)

            dT3_dC = (T3 / C) + pre * d_term_frac_dC * val_log3 + pre * term_frac * d_log3_dC

        # Term 4

        atan1 = np.arctan((2 * Eg + alpha) / C)

        atan2 = np.arctan((2 * Eg - alpha) / C)

        sum_atan = PI - atan1 - atan2

        K4 = -A / (PI * E0)

        frac4 = aa * inv_zeta4

        T4 = K4 * frac4 * sum_atan

        u1 = (2 * Eg + alpha) / C

        u2 = (2 * Eg - alpha) / C

        fac1 = 1.0 / (1.0 + u1**2)

        fac2 = 1.0 / (1.0 + u2**2)

        du1_dEg = 2.0 / C

        du2_dEg = 2.0 / C

        du1_dE0 = d_alpha_dE0 / C

        du2_dE0 = -d_alpha_dE0 / C

        du1_dC = -(2 * Eg + alpha) / (C * C) + d_alpha_dC / C

        du2_dC = -(2 * Eg - alpha) / (C * C) - d_alpha_dC / C

        d_sum_atan_dEg = -(fac1 * du1_dEg + fac2 * du2_dEg)

        d_sum_atan_dE0 = -(fac1 * du1_dE0 + fac2 * du2_dE0)

        d_sum_atan_dC = -(fac1 * du1_dC + fac2 * du2_dC)

        dT4_dA = T4 / A

        dT4_dEg = K4 * (d_aa_dEg * inv_zeta4) * sum_atan + K4 * frac4 * d_sum_atan_dEg

        dK4_dE0 = -K4 / E0

        d_frac4_dE0 = d_aa_dE0 * inv_zeta4 + aa * (-(inv_zeta4**2) * d_zeta4_dE0)

        dT4_dE0 = dK4_dE0 * frac4 * sum_atan + K4 * d_frac4_dE0 * sum_atan + K4 * frac4 * d_sum_atan_dE0

        d_frac4_dC = d_aa_dC * inv_zeta4 + aa * (-(inv_zeta4**2) * d_zeta4_dC)

        dT4_dC = K4 * d_frac4_dC * sum_atan + K4 * frac4 * d_sum_atan_dC

        # Term 5

        T5 = 0.0

        dT5_dA = 0.0

        dT5_dEg = 0.0

        dT5_dE0 = 0.0

        dT5_dC = 0.0

        if alpha > 1e-12:
            arg5 = 2.0 * (Eg_sq - gamma_sq) / max(alpha * C, 1e-12)

            atan3 = np.arctan(arg5)

            brack5 = PI / 2.0 - atan3

            K5 = 4.0 * A * E0 * Eg / (PI * alpha)

            term5_mid = (E_sq - gamma_sq) * inv_zeta4

            T5 = K5 * term5_mid * brack5

            dnum_dEg = 4.0 * Eg

            dnum_dE0 = -2.0 * d_gamma2_dE0

            dnum_dC = -2.0 * d_gamma2_dC

            dden_dE0 = d_alpha_dE0 * C

            dden_dC = d_alpha_dC * C + alpha

            den_sq = (alpha * C) ** 2

            fac3 = 1.0 / (1.0 + arg5**2)

            d_arg5_dEg = (dnum_dEg * alpha * C) / den_sq

            d_arg5_dE0 = (dnum_dE0 * alpha * C - 2 * (Eg_sq - gamma_sq) * dden_dE0) / den_sq

            d_arg5_dC = (dnum_dC * alpha * C - 2 * (Eg_sq - gamma_sq) * dden_dC) / den_sq

            d_brack5_dEg = -fac3 * d_arg5_dEg

            d_brack5_dE0 = -fac3 * d_arg5_dE0

            d_brack5_dC = -fac3 * d_arg5_dC

            dT5_dA = T5 / A

            dK5_dEg = K5 / Eg

            dT5_dEg = dK5_dEg * term5_mid * brack5 + K5 * term5_mid * d_brack5_dEg

            d_K5_dE0 = K5 / E0 - K5 / alpha * d_alpha_dE0

            d_term5_mid_dE0 = (-d_gamma2_dE0 * inv_zeta4) + (E_sq - gamma_sq) * (-(inv_zeta4**2) * d_zeta4_dE0)

            dT5_dE0 = d_K5_dE0 * term5_mid * brack5 + K5 * d_term5_mid_dE0 * brack5 + K5 * term5_mid * d_brack5_dE0

            d_K5_dC = -K5 / alpha * d_alpha_dC

            d_term5_mid_dC = (-d_gamma2_dC * inv_zeta4) + (E_sq - gamma_sq) * (-(inv_zeta4**2) * d_zeta4_dC)

            dT5_dC = d_K5_dC * term5_mid * brack5 + K5 * d_term5_mid_dC * brack5 + K5 * term5_mid * d_brack5_dC

        result[0, i] = eps_inf + T1 + T2 + T3 + T4 + T5

        result[1, i] = dT1_dEg + dT2_dEg + dT3_dEg + dT4_dEg + dT5_dEg

        result[2, i] = dT1_dA + dT2_dA + dT3_dA + dT4_dA + dT5_dA

        result[3, i] = dT1_dE0 + dT2_dE0 + dT3_dE0 + dT4_dE0 + dT5_dE0

        result[4, i] = dT1_dC + dT2_dC + dT3_dC + dT4_dC + dT5_dC

        result[6, i] = 1.0  # deps_inf

    return result


# --- LOCKED --- Validated by test_gradient_vs_fd.py ───


# n,k assembly + full TLU derivatives. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_tlu_derivatives_kernel(
    E_array: np.ndarray,
    Eg: float,
    A: float,
    E0: float,
    C: float,
    Eu: float,
    eps_inf: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Computes n, k and their derivatives w.r.t parameters"""

    n_pts = len(E_array)

    res1 = _compute_epsilon1_gradient_kernel(E_array, Eg, A, E0, C, eps_inf)

    res2 = _compute_epsilon2_gradient_kernel(E_array, Eg, A, E0, C, Eu)

    n_arr = np.empty(n_pts, dtype=np.float64)

    k_arr = np.empty(n_pts, dtype=np.float64)

    dn_dp = np.zeros((6, n_pts), dtype=np.float64)

    dk_dp = np.zeros((6, n_pts), dtype=np.float64)

    for i in prange(n_pts):
        e1 = res1[0, i]

        e2 = res2[0, i]

        eps_mag = np.sqrt(e1 * e1 + e2 * e2)

        n_val = np.sqrt(max((eps_mag + e1) / 2.0, 1e-12))

        k_val = np.sqrt(max((eps_mag - e1) / 2.0, 0.0))

        n_arr[i] = n_val

        k_arr[i] = k_val

        denom = max(2.0 * (n_val * n_val + k_val * k_val), 1e-12)

        inv_denom = 1.0 / denom

        for p in range(6):
            de1 = res1[p + 1, i]

            de2 = res2[p + 1, i]

            dn = (n_val * de1 + k_val * de2) * inv_denom

            dk = (n_val * de2 - k_val * de1) * inv_denom

            dn_dp[p, i] = dn

            dk_dp[p, i] = dk

    return n_arr, k_arr, dn_dp, dk_dp


# --- LOCKED --- Validated by test_gradient_vs_fd.py (lossless + absorbing + metal + dispersif) ───


# Internal convention (-1j, n+ik) self-consistent. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _compute_single_layer_sensitivity_kernel(
    wavelength: float, nr: float, ni: float, d: float, ns: float
) -> tuple[float, float, float, float, float, float]:
    """Computes derivatives of T and R w.r.t film index (nr, ni=k>=0) and d.

    Internal convention: (-1j, n+ik) baked-in - self-consistent, R/T/gradients invariant.

    """

    k0 = TWO_PI / wavelength

    n0 = 1.0  # Air

    phi_r = k0 * nr * d

    phi_i = k0 * ni * d

    cr = np.cos(phi_r)

    sr = np.sin(phi_r)

    ch = np.cosh(phi_i)

    sh = np.sinh(phi_i)

    c_real = cr * ch

    c_imag = -sr * sh

    s_real = sr * ch

    s_imag = cr * sh

    fac = k0 * d

    dc_dnr_r = -s_real * fac

    dc_dnr_i = -s_imag * fac

    ds_dnr_r = c_real * fac

    ds_dnr_i = c_imag * fac

    dc_dni_r = s_imag * fac

    dc_dni_i = -s_real * fac

    ds_dni_r = -c_imag * fac

    ds_dni_i = c_real * fac

    n2 = nr * nr + ni * ni

    inv_n2 = 1.0 / max(n2, 1e-14)

    inv_n_r = nr * inv_n2

    inv_n_i = -ni * inv_n2

    dninv_dnr_r = (ni * ni - nr * nr) * inv_n2 * inv_n2

    dninv_dnr_i = 2.0 * nr * ni * inv_n2 * inv_n2

    dninv_dni_r = -2.0 * nr * ni * inv_n2 * inv_n2

    dninv_dni_i = (ni * ni - nr * nr) * inv_n2 * inv_n2

    def mul_c(r1, i1, r2, i2):

        return r1 * r2 - i1 * i2, r1 * i2 + i1 * r2

    def get_dM01(dsr, dsi, sr, si, invr, invi, dinvr, dinvi):

        # (ds_imag - i*ds_real) * (inv_n_r + i*inv_n_i) + (s_imag - i*s_real) * (dinvr + i*dinvi)

        t1r, t1i = mul_c(dsi, -dsr, invr, invi)

        t2r, t2i = mul_c(si, -sr, dinvr, dinvi)

        return t1r + t2r, t1i + t2i

    def get_dM10(dsr, dsi, sr, si, nr, ni, dnr, dni):

        # (ds_imag - i*ds_real) * (nr + i*ni) + (s_imag - i*s_real) * (dnr + i*dni)

        t1r, t1i = mul_c(dsi, -dsr, nr, ni)

        t2r, t2i = mul_c(si, -sr, dnr, dni)

        return t1r + t2r, t1i + t2i

    dM00_dnr_r, dM00_dnr_i = dc_dnr_r, dc_dnr_i

    dM11_dnr_r, dM11_dnr_i = dc_dnr_r, dc_dnr_i

    dM01_dnr_r, dM01_dnr_i = get_dM01(ds_dnr_r, ds_dnr_i, s_real, s_imag, inv_n_r, inv_n_i, dninv_dnr_r, dninv_dnr_i)

    dM10_dnr_r, dM10_dnr_i = get_dM10(ds_dnr_r, ds_dnr_i, s_real, s_imag, nr, ni, 1.0, 0.0)

    dM00_dni_r, dM00_dni_i = dc_dni_r, dc_dni_i

    dM11_dni_r, dM11_dni_i = dc_dni_r, dc_dni_i

    dM01_dni_r, dM01_dni_i = get_dM01(ds_dni_r, ds_dni_i, s_real, s_imag, inv_n_r, inv_n_i, dninv_dni_r, dninv_dni_i)

    dM10_dni_r, dM10_dni_i = get_dM10(ds_dni_r, ds_dni_i, s_real, s_imag, nr, ni, 0.0, 1.0)

    M00r, M00i = c_real, c_imag

    M01r, M01i = mul_c(s_imag, -s_real, inv_n_r, inv_n_i)

    M10r, M10i = mul_c(s_imag, -s_real, nr, ni)

    M11r, M11i = c_real, c_imag

    def compute_denom_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        pr = n0 * dm00r + n0 * ns * dm01r + dm10r + ns * dm11r

        pi = n0 * dm00i + n0 * ns * dm01i + dm10i + ns * dm11i

        return pr, pi

    dD_dnr_r, dD_dnr_i = compute_denom_deriv(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dD_dni_r, dD_dni_i = compute_denom_deriv(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    Dr = n0 * M00r + n0 * ns * M01r + M10r + ns * M11r

    Di = n0 * M00i + n0 * ns * M01i + M10i + ns * M11i

    magD2 = Dr * Dr + Di * Di

    inv_magD2 = 1.0 / max(magD2, 1e-20)

    T_val = 4.0 * n0 * ns * inv_magD2

    def calc_dT(dDr, dDi):

        re_DD = dDr * Dr + dDi * Di

        return -T_val * (2.0 * re_DD * inv_magD2)

    dT_dnr = calc_dT(dD_dnr_r, dD_dnr_i)

    dT_dni = calc_dT(dD_dni_r, dD_dni_i)

    Nr = n0 * M00r + n0 * ns * M01r - M10r - ns * M11r

    Ni = n0 * M00i + n0 * ns * M01i - M10i - ns * M11i

    magN2 = Nr * Nr + Ni * Ni

    R_val = magN2 * inv_magD2

    def compute_num_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        qr = n0 * dm00r + n0 * ns * dm01r - dm10r - ns * dm11r

        qi = n0 * dm00i + n0 * ns * dm01i - dm10i - ns * dm11i

        return qr, qi

    dN_dnr_r, dN_dnr_i = compute_num_deriv(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dN_dni_r, dN_dni_i = compute_num_deriv(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    def calc_dR(dNr, dNi, dDr, dDi):

        re_NN = dNr * Nr + dNi * Ni

        re_DD = dDr * Dr + dDi * Di

        return (2.0 * re_NN - R_val * 2.0 * re_DD) * inv_magD2

    dR_dnr = calc_dR(dN_dnr_r, dN_dnr_i, dD_dnr_r, dD_dnr_i)

    dR_dni = calc_dR(dN_dni_r, dN_dni_i, dD_dni_r, dD_dni_i)

    dcos_dd_r, dcos_dd_i = mul_c(-s_real, -s_imag, k0 * nr, k0 * ni)

    dsin_dd_r, dsin_dd_i = mul_c(c_real, c_imag, k0 * nr, k0 * ni)

    dm01_dd_r, dm01_dd_i = mul_c(dsin_dd_i, -dsin_dd_r, inv_n_r, inv_n_i)

    dm10_dd_r, dm10_dd_i = mul_c(dsin_dd_i, -dsin_dd_r, nr, ni)

    dD_dd_r, dD_dd_i = compute_denom_deriv(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    dN_dd_r, dN_dd_i = compute_num_deriv(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    dT_dd = calc_dT(dD_dd_r, dD_dd_i)

    dR_dd = calc_dR(dN_dd_r, dN_dd_i, dD_dd_r, dD_dd_i)

    r_b = (1.0 - ns) / (1.0 + ns)

    R_b = r_b * r_b

    T_b = 1.0 - R_b

    Nr_p = ns * M00r + ns * M01r - M10r - M11r

    Ni_p = ns * M00i + ns * M01i - M10i - M11i

    R_prime = (Nr_p * Nr_p + Ni_p * Ni_p) * inv_magD2

    def calc_dR_prime(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i):

        qrp = ns * dm00r + ns * dm01r - dm10r - dm11r

        qip = ns * dm00i + ns * dm01i - dm10i - dm11i

        re_NPN = qrp * Nr_p + qip * Ni_p

        dDDr, dDDi = compute_denom_deriv(dm00r, dm00i, dm01r, dm01i, dm10r, dm10i, dm11r, dm11i)

        re_DD = dDDr * Dr + dDDi * Di

        return (2.0 * re_NPN - R_prime * 2.0 * re_DD) * inv_magD2

    dR_p_dnr = calc_dR_prime(
        dM00_dnr_r,
        dM00_dnr_i,
        dM01_dnr_r,
        dM01_dnr_i,
        dM10_dnr_r,
        dM10_dnr_i,
        dM11_dnr_r,
        dM11_dnr_i,
    )

    dR_p_dni = calc_dR_prime(
        dM00_dni_r,
        dM00_dni_i,
        dM01_dni_r,
        dM01_dni_i,
        dM10_dni_r,
        dM10_dni_i,
        dM11_dni_r,
        dM11_dni_i,
    )

    dR_p_dd = calc_dR_prime(
        dcos_dd_r,
        dcos_dd_i,
        dm01_dd_r,
        dm01_dd_i,
        dm10_dd_r,
        dm10_dd_i,
        dcos_dd_r,
        dcos_dd_i,
    )

    denom_corr = 1.0 - R_prime * R_b

    inv_dc = 1.0 / denom_corr if abs(denom_corr) > 1e-12 else 0.0

    facT = T_b * inv_dc

    facTR = (T_val * T_b * R_b) * (inv_dc * inv_dc)

    dT_dnr_corr = facT * dT_dnr + facTR * dR_p_dnr

    dT_dni_corr = facT * dT_dni + facTR * dR_p_dni

    dT_dd_corr = facT * dT_dd + facTR * dR_p_dd

    facRR = (T_val * T_val * R_b * R_b) * (inv_dc * inv_dc)

    facRT = (2.0 * T_val * R_b) * inv_dc

    dR_dnr_corr = dR_dnr + facRT * dT_dnr + facRR * dR_p_dnr

    dR_dni_corr = dR_dni + facRT * dT_dni + facRR * dR_p_dni

    dR_dd_corr = dR_dd + facRT * dT_dd + facRR * dR_p_dd

    return dT_dnr_corr, dT_dni_corr, dR_dnr_corr, dR_dni_corr, dT_dd_corr, dR_dd_corr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_single_layer_sensitivity_array(
    wavelengths: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d: float,
    n_sub: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized wrapper: calls _compute_single_layer_sensitivity_kernel via prange.

    Returns six (n_pix,) arrays: dT_dn, dT_dk, dR_dn, dR_dk, dT_dd, dR_dd.
    Eliminates CPython→Numba dispatch overhead (one JIT entry instead of n_pix).
    """
    n = len(wavelengths)
    dTdn = np.empty(n, dtype=np.float64)
    dTdk = np.empty(n, dtype=np.float64)
    dRdn = np.empty(n, dtype=np.float64)
    dRdk = np.empty(n, dtype=np.float64)
    dTdd = np.empty(n, dtype=np.float64)
    dRdd = np.empty(n, dtype=np.float64)
    for i in prange(n):
        a, b, c, e, f, g = _compute_single_layer_sensitivity_kernel(wavelengths[i], n_arr[i], k_arr[i], d, n_sub[i])
        dTdn[i] = a
        dTdk[i] = b
        dRdn[i] = c
        dRdk[i] = e
        dTdd[i] = f
        dRdd[i] = g
    return dTdn, dTdk, dRdn, dRdk, dTdd, dRdd


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_index_cost_gradient_kernel(
    wls: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d: float,
    n_sub: np.ndarray,
    target_T: np.ndarray,
    target_R: np.ndarray,
    weights: np.ndarray,
    use_T: bool,
    use_R: bool,
    dn_dp: np.ndarray,
    dk_dp: np.ndarray,
    T_substrate: np.ndarray,
    _R_substrate: np.ndarray,
    use_normalized: bool,
    weight_T: float,
    weight_R: float,
) -> np.ndarray:
    """Computes gradient of MSE w.r.t parameters (race-free parallel reduction).

    Normalization: T_nu = T/T_sub, R_nu = R/T_sub. Guards: T_sub >= 1e-6 (T), >= 0.05 (R)

    match certus_core.T_SUB_MIN_T_NORM and T_SUB_MIN_R_NORM; literals kept here for Numba."""

    n_pts = len(wls)

    n_valid_T = 1

    n_valid_R = 1

    count_T = 0

    count_R = 0

    for i in range(n_pts):
        if weights[i] > 1e-12:
            if use_T:
                count_T += 1

            if use_R:
                count_R += 1

    if count_T > 0:
        n_valid_T = count_T

    if count_R > 0:
        n_valid_R = count_R

    # Per-wavelength gradient (avoid race condition on shared grad)

    grad_per_wl = np.zeros((n_pts, 7), dtype=np.float64)

    for i in prange(n_pts):
        wl = wls[i]

        if weights[i] < 1e-12:
            continue

        nr = n_arr[i]

        ni = k_arr[i]

        ns = n_sub[i]

        dTdn, dTdk, dRdn, dRdk, dTdd, dRdd = _compute_single_layer_sensitivity_kernel(wl, nr, ni, d, ns)

        w = weights[i]

        fac_T = 0.0

        fac_R = 0.0

        # Fused R+T single call (same values as cost)

        val_R, val_T = calculate_transmission_single(wl, nr, ni, d, ns)

        if use_T:
            if use_normalized:
                scale_T = 1.0 / max(T_substrate[i], 1e-6)

                diff_T = (val_T * scale_T) - target_T[i]

            else:
                scale_T = 1.0

                diff_T = val_T - target_T[i]

            fac_T = (2.0 * w * diff_T * weight_T / n_valid_T) * scale_T

        if use_R:
            if use_normalized:
                # Physics Guard: Avoid explosion when T -> 0

                if T_substrate[i] >= 0.05:
                    scale_R = 1.0 / T_substrate[i]

                else:
                    scale_R = 0.0  # Effectively ignore this point in gradient

                diff_R = (val_R * scale_R) - target_R[i]

            else:
                scale_R = 1.0

                diff_R = val_R - target_R[i]

            fac_R = (2.0 * w * diff_R * weight_R / n_valid_R) * scale_R

        grad_per_wl[i, 0] = (fac_T * dTdd + fac_R * dRdd) if use_T or use_R else 0.0

        for p in range(6):
            dnp = dn_dp[p, i]

            dkp = dk_dp[p, i]

            term = 0.0

            if use_T:
                term += fac_T * (dTdn * dnp + dTdk * dkp)

            if use_R:
                term += fac_R * (dRdn * dnp + dRdk * dkp)

            grad_per_wl[i, p + 1] = term

    # Reduction (sequential, fast for 7 params)

    grad = np.zeros(7, dtype=np.float64)

    for p in range(7):
        s = 0.0

        for i in range(n_pts):
            s += grad_per_wl[i, p]

        grad[p] = s

    return grad


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


def prepare_targets_vectorized(wls: np.ndarray, targets: list[Target]) -> tuple[np.ndarray, np.ndarray]:
    """

    Prepares target values and weights for optimization.

    Weights combine user target weight (tgt.w) with spectral quadrature

    Delta ln lambda (trapezoidal) for density-corrected broadband optimization.

    """

    from certus.utils.certus_index_utils import spectral_rmse_weights

    vals = np.zeros(len(wls), dtype=np.float64)

    weights = np.zeros(len(wls), dtype=np.float64)

    spec_w = spectral_rmse_weights(np.asarray(wls, dtype=np.float64))

    for t in targets:
        if not t.valid():
            continue

        mask = (wls >= t.lmin) & (wls <= t.lmax)

        if not np.any(mask):
            continue

        # Target linear interpolation

        denom = t.lmax - t.lmin

        if denom < 1e-9:
            denom = 1e-9

        slope = (t.tmax - t.tmin) / denom

        vals[mask] = t.tmin + slope * (wls[mask] - t.lmin)

        weights[mask] = t.w * spec_w[mask]

    return vals, weights


def make_cost_function(
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
) -> Callable[[np.ndarray], float]:
    """

    Factory that creates an optimized cost function with pre-converted arrays.

    All arrays in f64/c128 for double precision.

    """

    # TMM arrays: c128/f64 for full double precision

    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)

    n_layers_T_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)

    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)

    # Targets: f64

    tgt_vals_f64 = np.ascontiguousarray(tgt_vals, dtype=np.float64)

    tgt_weights_f64 = np.ascontiguousarray(tgt_weights, dtype=np.float64)

    if has_back:
        n_back_T_c128 = np.ascontiguousarray(n_back_T, dtype=np.complex128)

        d_back_f64 = np.ascontiguousarray(d_back, dtype=np.float64)

    else:
        n_back_T_c128 = np.zeros((len(wls), 0), dtype=np.complex128)

        d_back_f64 = np.zeros(0, dtype=np.float64)

    def cost_func(ep: np.ndarray) -> float:

        ep_f64 = np.ascontiguousarray(ep, dtype=np.float64)

        return cost_numba_fast(
            ep_f64,
            n_layers_T_c128,
            n_sub_c128,
            wls_f64,
            tgt_vals_f64,
            tgt_weights_f64,
            min_d,
            has_back,
            n_back_T_c128,
            d_back_f64,
        )

    return cost_func


# --- LOCKED --- Validated by test_gradient_vs_fd.py (dispersive + absorbent + mixed) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_gradient_analytic_kernel(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    var_idx: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    """

    Analytic gradient kernel for TMM (Opus 4.6 - parallelized over wavelengths).

    Each wavelength is independent (own forward/backward TMM pass).

    Per-wavelength gradient contributions are accumulated then reduced.

    """

    n_wls = len(wls)

    n_layers = len(ep)

    n_vars = len(var_idx)

    # Output arrays

    T_arr = np.empty(n_wls, dtype=np.float64)

    # Per-wavelength accumulators (avoid race conditions with prange)

    grad_per_wl = np.zeros((n_wls, n_vars), dtype=np.float64)

    err_per_wl = np.zeros(n_wls, dtype=np.float64)

    weight_per_wl = np.zeros(n_wls, dtype=np.float64)

    # Pre-allocated buffers for forward/backward passes to avoid heap allocation inside prange loop
    M_before_buf = np.zeros((n_wls, n_layers + 1, 8), dtype=np.float64)
    M_after_buf = np.zeros((n_wls, n_layers + 1, 8), dtype=np.float64)

    for i_wl in prange(n_wls):
        # Thread-local M_before / M_after (stack-allocated per iteration)

        M_before = M_before_buf[i_wl]

        M_after = M_after_buf[i_wl]

        wl = wls[i_wl]

        inv_wl = 1.0 / wl

        two_pi_inv_wl = TWO_PI * inv_wl

        n_s = n_sub[i_wl]

        ns_r = n_s.real

        ns_i = n_s.imag

        # === FORWARD PASS: Compute M_before[k] ===

        M_before[0, 0] = 1.0  # Re(M00)

        M_before[0, 1] = 0.0  # Im(M00)

        M_before[0, 2] = 0.0  # Re(M01)

        M_before[0, 3] = 0.0  # Im(M01)

        M_before[0, 4] = 0.0  # Re(M10)

        M_before[0, 5] = 0.0  # Im(M10)

        M_before[0, 6] = 1.0  # Re(M11)

        M_before[0, 7] = 0.0  # Im(M11)

        Ar, Ai = 1.0, 0.0

        Br, Bi = 0.0, 0.0

        Cr, Ci = 0.0, 0.0

        Dr, Di = 1.0, 0.0

        for k in range(n_layers):
            n_k = n_layers_T[i_wl, k]

            nr = n_k.real

            ni = n_k.imag

            d_k = ep[k]

            phi_base = two_pi_inv_wl * d_k

            if abs(ni) < 1e-14:
                phi = phi_base * nr

                cp = np.cos(phi)

                sp = np.sin(phi)

                inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                m01i = sp * inv_n

                m10i = sp * nr

                # M_before_new = M_before_old * L (Lossless)

                NAr = Ar * cp + Bi * m10i

                NAi = Ai * cp - Br * m10i

                NBr = Ai * m01i + Br * cp

                NBi = -Ar * m01i + Bi * cp

                NCr = Cr * cp + Di * m10i

                NCi = Ci * cp - Dr * m10i

                NDr = Ci * m01i + Dr * cp

                NDi = -Cr * m01i + Di * cp

            else:
                phr = phi_base * nr

                phi_img = phi_base * ni

                cr = np.cos(phr) * np.cosh(phi_img)

                ci = -np.sin(phr) * np.sinh(phi_img)

                sr = np.sin(phr) * np.cosh(phi_img)

                si = np.cos(phr) * np.sinh(phi_img)

                eta2 = nr * nr + ni * ni

                if eta2 < 1e-24:
                    eta2 = 1e-24

                inv_eta = 1.0 / eta2

                etr = nr * inv_eta

                eti = -ni * inv_eta

                m01r = sr * eti + si * etr

                m01i = si * eti - sr * etr

                m10r = nr * si + ni * sr

                m10i = ni * si - nr * sr

                # M_before_new = M_before_old * L (Absorbing)

                NAr = Ar * cr - Ai * ci + Br * m10r - Bi * m10i

                NAi = Ar * ci + Ai * cr + Br * m10i + Bi * m10r

                NBr = Ar * m01r - Ai * m01i + Br * cr - Bi * ci

                NBi = Ar * m01i + Ai * m01r + Br * ci + Bi * cr

                NCr = Cr * cr - Ci * ci + Dr * m10r - Di * m10i

                NCi = Cr * ci + Ci * cr + Dr * m10i + Di * m10r

                NDr = Cr * m01r - Ci * m01i + Dr * cr - Di * ci

                NDi = Cr * m01i + Ci * m01r + Dr * ci + Di * cr

            M_before[k + 1, 0] = Ar

            M_before[k + 1, 1] = Ai

            M_before[k + 1, 2] = Br

            M_before[k + 1, 3] = Bi

            M_before[k + 1, 4] = Cr

            M_before[k + 1, 5] = Ci

            M_before[k + 1, 6] = Dr

            M_before[k + 1, 7] = Di

            Ar, Ai, Br, Bi, Cr, Ci, Dr, Di = NAr, NAi, NBr, NBi, NCr, NCi, NDr, NDi

        M00r, M00i = Ar, Ai

        M01r, M01i = Br, Bi

        M10r, M10i = Cr, Ci

        M11r, M11i = Dr, Di

        # === BACKWARD PASS: Compute M_after[k] ===

        M_after[n_layers, 0] = 1.0

        M_after[n_layers, 1] = 0.0

        M_after[n_layers, 2] = 0.0

        M_after[n_layers, 3] = 0.0

        M_after[n_layers, 4] = 0.0

        M_after[n_layers, 5] = 0.0

        M_after[n_layers, 6] = 1.0

        M_after[n_layers, 7] = 0.0

        Ar, Ai = 1.0, 0.0

        Br, Bi = 0.0, 0.0

        Cr, Ci = 0.0, 0.0

        Dr, Di = 1.0, 0.0

        for k in range(n_layers - 1, -1, -1):
            M_after[k, 0] = Ar

            M_after[k, 1] = Ai

            M_after[k, 2] = Br

            M_after[k, 3] = Bi

            M_after[k, 4] = Cr

            M_after[k, 5] = Ci

            M_after[k, 6] = Dr

            M_after[k, 7] = Di

            n_k = n_layers_T[i_wl, k]

            nr = n_k.real

            ni = n_k.imag

            d_k = ep[k]

            phi_base = two_pi_inv_wl * d_k

            if abs(ni) < 1e-14:
                phi = phi_base * nr

                cp = np.cos(phi)

                sp = np.sin(phi)

                inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                m01i = sp * inv_n

                m10i = sp * nr

                # M_after_new = L * M_after_old (Lossless)

                # L = [[cp, -i m01i], [-i m10i, cp]]

                NAr = cp * Ar + m01i * Ci

                NAi = cp * Ai - m01i * Cr

                NBr = cp * Br + m01i * Di

                NBi = cp * Bi - m01i * Dr

                NCr = m10i * Ai + cp * Cr

                NCi = -m10i * Ar + cp * Ci

                NDr = m10i * Bi + cp * Dr

                NDi = -m10i * Br + cp * Di

            else:
                phr = phi_base * nr

                phi_img = phi_base * ni

                cr = np.cos(phr) * np.cosh(phi_img)

                ci = -np.sin(phr) * np.sinh(phi_img)

                sr = np.sin(phr) * np.cosh(phi_img)

                si = np.cos(phr) * np.sinh(phi_img)

                eta2 = nr * nr + ni * ni

                if eta2 < 1e-24:
                    eta2 = 1e-24

                inv_eta = 1.0 / eta2

                etr = nr * inv_eta

                eti = -ni * inv_eta

                m01r = sr * eti + si * etr

                m01i = si * eti - sr * etr

                m10r = nr * si + ni * sr

                m10i = ni * si - nr * sr

                # NAr = cr * Ar - ci * Ai + m01r * Cr - m01i * Ci

                NAr = cr * Ar - ci * Ai + m01r * Cr - m01i * Ci

                NAi = cr * Ai + ci * Ar + m01r * Ci + m01i * Cr

                NBr = cr * Br - ci * Bi + m01r * Dr - m01i * Di

                NBi = cr * Bi + ci * Br + m01r * Di + m01i * Dr

                NCr = m10r * Ar - m10i * Ai + cr * Cr - ci * Ci

                NCi = m10r * Ai + m10i * Ar + cr * Ci + ci * Cr

                NDr = m10r * Br - m10i * Bi + cr * Dr - ci * Di

                NDi = m10r * Bi + m10i * Br + cr * Di + ci * Dr

            Ar, Ai, Br, Bi, Cr, Ci, Dr, Di = NAr, NAi, NBr, NBi, NCr, NCi, NDr, NDi

        # Calculate T - Sub->Air convention: denom = n_sub*(M00+M01) + (M10+M11)

        dr = (ns_r * M00r - ns_i * M00i) + (ns_r * M01r - ns_i * M01i) + M10r + M11r

        di = (ns_r * M00i + ns_i * M00r) + (ns_r * M01i + ns_i * M01r) + M10i + M11i

        denom = dr * dr + di * di

        if denom < 1e-30:
            denom = 1e-30

        inv_den = 1.0 / denom

        tr = 2.0 * dr * inv_den

        ti = -2.0 * di * inv_den

        T_val = ns_r * (tr * tr + ti * ti)

        T_arr[i_wl] = T_val

        w = tgt_weights[i_wl]

        if w > 1e-12:
            diff = T_val - tgt_vals[i_wl]

            err_per_wl[i_wl] = diff * diff * w

            weight_per_wl[i_wl] = w

            # Compute gradients (per-wavelength accumulation)

            for i_var in range(n_vars):
                k = var_idx[i_var]

                idx_b = k + 1

                Mb00r = M_before[idx_b, 0] if idx_b <= n_layers else 0.0

                Mb00i = M_before[idx_b, 1] if idx_b <= n_layers else 0.0

                Mb01r = M_before[idx_b, 2] if idx_b <= n_layers else 0.0

                Mb01i = M_before[idx_b, 3] if idx_b <= n_layers else 0.0

                Mb10r = M_before[idx_b, 4] if idx_b <= n_layers else 0.0

                Mb10i = M_before[idx_b, 5] if idx_b <= n_layers else 0.0

                Mb11r = M_before[idx_b, 6] if idx_b <= n_layers else 0.0

                Mb11i = M_before[idx_b, 7] if idx_b <= n_layers else 0.0

                Ma00r = M_after[k, 0]

                Ma00i = M_after[k, 1]

                Ma01r = M_after[k, 2]

                Ma01i = M_after[k, 3]

                Ma10r = M_after[k, 4]

                Ma10i = M_after[k, 5]

                Ma11r = M_after[k, 6]

                Ma11i = M_after[k, 7]

                n_k = n_layers_T[i_wl, k]

                nr = n_k.real

                ni = n_k.imag

                d_k = ep[k]

                if abs(ni) < 1e-14:
                    factor = two_pi_inv_wl * nr

                    phi = factor * d_k

                    cp = np.cos(phi)

                    sp = np.sin(phi)

                    inv_n = 1.0 / nr if nr > 1e-14 else 0.0

                    dm00r = -factor * sp

                    dm00i = 0.0

                    dm01r = 0.0

                    dm01i = -factor * cp * inv_n

                    dm10r = 0.0

                    dm10i = -factor * nr * cp

                    dm11r = -factor * sp

                    dm11i = 0.0

                else:
                    # Closed-form derivative for absorbing media (no finite differences).

                    phi_base = two_pi_inv_wl * d_k

                    phr = phi_base * nr

                    phi_img = phi_base * ni

                    cr = np.cos(phr) * np.cosh(phi_img)

                    ci = -np.sin(phr) * np.sinh(phi_img)

                    sr = np.sin(phr) * np.cosh(phi_img)

                    si = np.cos(phr) * np.sinh(phi_img)

                    eta2 = nr * nr + ni * ni

                    if eta2 < 1e-24:
                        eta2 = 1e-24

                    inv_eta = 1.0 / eta2

                    etr = nr * inv_eta

                    eti = -ni * inv_eta

                    f_r = TWO_PI * nr * inv_wl

                    f_i = TWO_PI * ni * inv_wl

                    # d/d(d_k) of trigonometric-hyperbolic components

                    dcr = -sr * f_r + si * f_i

                    dci = -(si * f_r + sr * f_i)

                    dsr = cr * f_r - ci * f_i

                    dsi = ci * f_r + cr * f_i

                    dm00r = dcr

                    dm00i = dci

                    dm01r = dsr * eti + dsi * etr

                    dm01i = dsi * eti - dsr * etr

                    dm10r = nr * dsi + ni * dsr

                    dm10i = ni * dsi - nr * dsr

                    dm11r = dm00r

                    dm11i = dm00i

                # eM = Mb * dL * Ma

                # T = Mb * dL

                # eM = Mb * dL * Ma

                # T = Mb * dL

                t00r = Mb00r * dm00r - Mb00i * dm00i + Mb01r * dm10r - Mb01i * dm10i

                t00i = Mb00r * dm00i + Mb00i * dm00r + Mb01r * dm10i + Mb01i * dm10r

                t01r = Mb00r * dm01r - Mb00i * dm01i + Mb01r * dm11r - Mb01i * dm11i

                t01i = Mb00r * dm01i + Mb00i * dm01r + Mb01r * dm11i + Mb01i * dm11r

                t10r = Mb10r * dm00r - Mb10i * dm00i + Mb11r * dm10r - Mb11i * dm10i

                t10i = Mb10r * dm00i + Mb10i * dm00r + Mb11r * dm10i + Mb11i * dm10r

                t11r = Mb10r * dm01r - Mb10i * dm01i + Mb11r * dm11r - Mb11i * dm11i

                t11i = Mb10r * dm01i + Mb10i * dm01r + Mb11r * dm11i + Mb11i * dm11r

                dM00r = t00r * Ma00r - t00i * Ma00i + t01r * Ma10r - t01i * Ma10i

                dM00i = t00r * Ma00i + t00i * Ma00r + t01r * Ma10i + t01i * Ma10r

                dM01r = t00r * Ma01r - t00i * Ma01i + t01r * Ma11r - t01i * Ma11i

                dM01i = t00r * Ma01i + t00i * Ma01r + t01r * Ma11i + t01i * Ma11r

                dM10r = t10r * Ma00r - t10i * Ma00i + t11r * Ma10r - t11i * Ma10i

                dM10i = t10r * Ma00i + t10i * Ma00r + t11r * Ma10i + t11i * Ma10r

                dM11r = t10r * Ma01r - t10i * Ma01i + t11r * Ma11r - t11i * Ma11i

                dM11i = t10r * Ma01i + t10i * Ma01r + t11r * Ma11i + t11i * Ma11r

                ddr = (ns_r * dM00r - ns_i * dM00i) + (ns_r * dM01r - ns_i * dM01i) + dM10r + dM11r

                ddi = (ns_r * dM00i + ns_i * dM00r) + (ns_r * dM01i + ns_i * dM01r) + dM10i + dM11i

                d_denom = 2.0 * (dr * ddr + di * ddi)

                dtr = 2.0 * ddr * inv_den - tr * d_denom * inv_den

                dti = -2.0 * ddi * inv_den - ti * d_denom * inv_den

                dT_dk = ns_r * 2.0 * (tr * dtr + ti * dti)

                grad_per_wl[i_wl, i_var] += w * diff * dT_dk

    # === REDUCTION PHASE (sequential, fast) ===

    err_sum = 0.0

    weight_sum = 0.0

    for i in range(n_wls):
        err_sum += err_per_wl[i]

        weight_sum += weight_per_wl[i]

    grad = np.zeros(n_vars, dtype=np.float64)

    for v in range(n_vars):
        s = 0.0

        for i in range(n_wls):
            s += grad_per_wl[i, v]

        grad[v] = s

    if weight_sum < 1e-12:
        cost = 1e30

        grad[:] = 0.0

    else:
        cost = err_sum / weight_sum

        grad *= 2.0 / weight_sum

    return cost, grad, T_arr


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_oblique_gradient_contrib_kernel(
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

        T_unclipped = (eta_sub / eta_inc) * (t * t.conjugate()).real

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

                dy = (eta_sub / eta_inc) * 2.0 * (t.conjugate() * dt).real

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

    return _compute_oblique_gradient_contrib_kernel(
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


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_oblique_rt_and_grads_kernel(
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

        Tv = (eta_exit / eta_inc) * (t * t.conjugate()).real

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

            dT[i_wl, iv] = (eta_exit / eta_inc) * 2.0 * (t.conjugate() * dt).real

    return R_arr, T_arr, dR, dT


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

    return _compute_oblique_rt_and_grads_kernel(
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

    front = _compute_oblique_rt_and_grads_kernel(
        ep_f64,
        n_layers_c128,
        n_sub_c128,
        wls_f64,
        var_idx_i64,
        float(angle_deg),
        bool(is_s_pol),
        False,
    )

    reverse = _compute_oblique_rt_and_grads_kernel(
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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """

    Backside oblique bundle for one polarization.

    Returns y_R, dy_R, y_T, dy_T wrt front thickness variables.

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


# --- LOCKED --- Validated by test_gradient_vs_fd.py ───


# Multilayer analytic gradient wrapper. DO NOT MODIFY without running tests.


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

        _Rf0, _Tf0, _Rf_p0, Rb_prime, Tb = calc_spectrum_full_exact(
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


# --- LOCKED --- Validated by test_gradient_vs_fd.py (Ag dispersive + SiO2 + Si absorbent) ───


# Macleod convention (+1j). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_metal_tmm_gradient_kernel(
    l_array: np.ndarray,
    nM_complex_array: np.ndarray,
    eM: float,
    eL: float,
    nL_complex_array: np.ndarray,
    nSub_complex_array: np.ndarray,
    r_tgt_array: np.ndarray,
):
    """Computes Cost and Gradients w.r.t physical params and optical clues for Bilayer."""

    n_pts = len(l_array)

    n_pts_inv = 1.0 / n_pts


    grad_eM = 0.0

    grad_eL = 0.0

    # Sensitivities arrays

    dJ_dnM_r = np.zeros(n_pts, dtype=np.float64)

    dJ_dnM_i = np.zeros(n_pts, dtype=np.float64)

    dJ_dnL_r = np.zeros(n_pts, dtype=np.float64)

    mse = 0.0

    for i in prange(n_pts):
        wl = l_array[i]

        inv_wl = 1.0 / wl

        k0 = TWO_PI * inv_wl

        R_tgt = r_tgt_array[i]

        # --- FORWARD PASS ---

        nM = nM_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nM.imag > 0.0:
            nM = nM.real - 1j * nM.imag

        phiM_base = k0 * eM

        phiM = phiM_base * nM

        cM = np.cos(phiM)

        sM = np.sin(phiM)

        inv_nM = 1.0 / nM if abs(nM) > 1e-14 else 0j

        mM00 = cM

        mM01 = +1j * inv_nM * sM

        mM10 = +1j * nM * sM

        mM11 = cM

        nL = nL_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nL.imag > 0.0:
            nL = nL.real - 1j * nL.imag

        phiL_base = k0 * eL

        phiL = phiL_base * nL

        cL = np.cos(phiL)

        sL = np.sin(phiL)

        inv_nL = 1.0 / nL if abs(nL) > 1e-14 else 0j

        mL00 = cL

        mL01 = +1j * inv_nL * sL

        mL10 = +1j * nL * sL

        mL11 = cL

        nS = nSub_complex_array[i]

        # ── SAFEGUARD n-ik ──

        if nS.imag > 0.0:
            nS = nS.real - 1j * nS.imag

        # Total Matrix M_tot = M_M * M_L

        Mt00 = mM00 * mL00 + mM01 * mL10

        Mt01 = mM00 * mL01 + mM01 * mL11

        Mt10 = mM10 * mL00 + mM11 * mL10

        Mt11 = mM10 * mL01 + mM11 * mL11

        n0 = 1.0  # Air

        term1 = n0 * (Mt00 + nS * Mt01)

        term2 = Mt10 + nS * Mt11

        num = term1 - term2

        den = term1 + term2

        inv_den = 1.0 / den if abs(den) > 1e-20 else 0j

        r = num * inv_den

        R = np.abs(r) ** 2

        diff = R - R_tgt

        mse += diff * diff

        # --- BACKWARD PASS (Gradients) ---

        dJ_dR = 2.0 * diff * n_pts_inv

        grad_factor = 2.0 * np.conj(r) * inv_den

        W_A = n0 * (1.0 - r) * grad_factor

        W_B = -(1.0 + r) * grad_factor

        coef_Mt00 = dJ_dR * W_A

        coef_Mt01 = dJ_dR * W_A * nS

        coef_Mt10 = dJ_dR * W_B

        coef_Mt11 = dJ_dR * W_B * nS

        C_mM00 = coef_Mt00 * mL00 + coef_Mt01 * mL01

        C_mM01 = coef_Mt00 * mL10 + coef_Mt01 * mL11

        C_mM10 = coef_Mt10 * mL00 + coef_Mt11 * mL01

        C_mM11 = coef_Mt10 * mL10 + coef_Mt11 * mL11

        dphi_ddM = k0 * nM

        dphi_deM = dphi_ddM

        dmM00_de = -sM * dphi_deM

        dmM01_de = +1j * inv_nM * cM * dphi_deM

        dmM10_de = +1j * nM * cM * dphi_deM

        dmM11_de = -sM * dphi_deM

        grad_eM += np.real(C_mM00 * dmM00_de + C_mM01 * dmM01_de + C_mM10 * dmM10_de + C_mM11 * dmM11_de)

        dphi_dn = k0 * eM

        dmM00_dn = -sM * dphi_dn

        dmM01_dn = +1j * (-inv_nM * inv_nM * sM + inv_nM * cM * dphi_dn)

        dmM10_dn = +1j * (sM + nM * cM * dphi_dn)

        dmM11_dn = -sM * dphi_dn

        sens_nM = C_mM00 * dmM00_dn + C_mM01 * dmM01_dn + C_mM10 * dmM10_dn + C_mM11 * dmM11_dn

        dJ_dnM_r[i] = sens_nM.real

        dJ_dnM_i[i] = -sens_nM.imag

        C_mL00 = coef_Mt00 * mM00 + coef_Mt10 * mM10

        C_mL10 = coef_Mt00 * mM01 + coef_Mt10 * mM11

        C_mL01 = coef_Mt01 * mM00 + coef_Mt11 * mM10

        C_mL11 = coef_Mt01 * mM01 + coef_Mt11 * mM11

        dphi_deL = k0 * nL

        dmL00_de = -sL * dphi_deL

        dmL01_de = +1j * inv_nL * cL * dphi_deL

        dmL10_de = +1j * nL * cL * dphi_deL

        dmL11_de = -sL * dphi_deL

        grad_eL += np.real(C_mL00 * dmL00_de + C_mL01 * dmL01_de + C_mL10 * dmL10_de + C_mL11 * dmL11_de)

        dphi_dnL = k0 * eL

        dmL00_dn = -sL * dphi_dnL

        dmL01_dn = +1j * (-inv_nL * inv_nL * sL + inv_nL * cL * dphi_dnL)

        dmL10_dn = +1j * (sL + nL * cL * dphi_dnL)

        dmL11_dn = -sL * dphi_dnL

        sens_nL = C_mL00 * dmL00_dn + C_mL01 * dmL01_dn + C_mL10 * dmL10_dn + C_mL11 * dmL11_dn

        dJ_dnL_r[i] = sens_nL.real

    return mse * n_pts_inv, grad_eM, grad_eL, dJ_dnM_r, dJ_dnM_i, dJ_dnL_r


# --- LOCKED --- Validated by test_gradient_vs_fd.py (Ag + SiO2 + Si) ───


# Analytic gradient wrapper for metal bilayer. DO NOT MODIFY without running tests.


def compute_metal_bilayer_gradient_analytic(
    x, num_knots, l_array, r_tgt_array, _min_knot_dist, nSub_complex_array=None
):
    """

    Wrapper calculating full gradient using Analytic TMM + FD Spline for Bilayer Metal.

    """

    grad = np.zeros_like(x)

    eM, eL, n_infini, A = x[0], x[1], x[2], x[3]

    offset = 4

    n_knots = x[offset : offset + num_knots]

    k_knots = x[offset + num_knots : offset + 2 * num_knots]

    lambda_internes = x[offset + 2 * num_knots :]

    knot_l = np.concatenate(([l_array.min()], np.sort(lambda_internes), [l_array.max()]))

    p_spline_nk = np.concatenate((n_knots, k_knots))

    n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=False)

    nL_calc = get_nk_cauchy_simple(l_array, n_infini, A)

    if nSub_complex_array is None:
        # Note: Need get_nk_si available or passed. Assuming passed or available in scope.

        # Fallback to a default if not found? This should be passed.

        # Since get_nk_si is in materials_data.py, it's not here.

        # Caller MUST pass nSub_complex_array.

        pass

    nM_complex = n_calc - 1j * k_calc

    nL_complex = nL_calc + 0j

    mse, g_eM, g_eL, sens_nM_r, sens_nM_i, sens_nL_r = _compute_metal_tmm_gradient_kernel(
        l_array, nM_complex, eM, eL, nL_complex, nSub_complex_array, r_tgt_array
    )

    grad[0] = g_eM

    grad[1] = g_eL

    grad[2] = np.sum(sens_nL_r)  # n_inf

    grad[3] = np.sum(sens_nL_r / (l_array**2))  # A

    dJ_dn = sens_nM_r

    dJ_dk = -sens_nM_i

    basis = np.zeros((num_knots, len(l_array)), dtype=np.float64)

    for i in range(num_knots):
        unit_vals = np.zeros(num_knots)

        unit_vals[i] = 1.0

        spline_basis = CubicSpline(knot_l, unit_vals, bc_type="natural", extrapolate=False)

        basis_vals = spline_basis(l_array)

        basis[i, :] = np.nan_to_num(basis_vals, nan=0.0)

    basis_n = basis

    basis_k = basis

    for i in range(num_knots):
        grad[offset + i] = np.dot(dJ_dn, basis_n[i, :])

    for i in range(num_knots):
        grad[offset + num_knots + i] = np.dot(dJ_dk, basis_k[i, :])

    h_val = 1e-5

    curr_l_int = lambda_internes.copy()

    for i in range(len(lambda_internes)):
        orig = curr_l_int[i]

        curr_l_int[i] += h_val

        k_l_p = np.concatenate(([l_array.min()], np.sort(curr_l_int), [l_array.max()]))

        ns_p, ks_p = get_nk_from_spline(p_spline_nk, k_l_p, l_array, use_cache=False)

        curr_l_int[i] = orig

        dn_dp = (ns_p - n_calc) / h_val

        dk_dp = (ks_p - k_calc) / h_val

        grad[offset + 2 * num_knots + i] = np.dot(dJ_dn, dn_dp) + np.dot(dJ_dk, dk_dp)

    if eM < 1.0:
        grad[0] -= 1000.0 * (1.0 - eM)

    if eL < 1.0:
        grad[1] -= 1000.0 * (1.0 - eL)

    return mse, grad


# =============================================================================


# MATERIAL DATABASE UTILS


# =============================================================================


# MaterialDatabase stub removed (duplicate of line 1036 and unused)


class NKCache:
    """Global thread-safe LRU cache for Cauchy clues (Opus 4.6)"""

    _cache: OrderedDict = OrderedDict()

    _lock = RLock()

    _max_size = 100

    @classmethod
    def get(cls, mat_key, n4, n7, wls):

        if len(wls) == 0:
            return np.array([], dtype=np.complex128)

        step = float(wls[1] - wls[0]) if len(wls) > 1 else 0.0

        cache_key = (mat_key, n4, n7, len(wls), float(wls[0]), float(wls[-1]), step)

        with cls._lock:
            if cache_key in cls._cache:
                cls._cache.move_to_end(cache_key)

                return cls._cache[cache_key]

            val = get_nk_cauchy_wrapper(float(n4), float(n7), wls)

            dtype = get_complex_dtype()

            val_c = val.astype(dtype)

            cls._cache[cache_key] = val_c

            # LRU eviction: remove oldest entry (not clear-all)

            while len(cls._cache) > cls._max_size:
                cls._cache.popitem(last=False)

            return val_c


def get_refractive_index(material_id: Any, wavelength_nm: float, db_instance=None):

    if not isinstance(material_id, str):
        try:
            return float(material_id)
        except (TypeError, ValueError):
            return complex(material_id)

    # Try Database

    if db_instance is not None:
        try:
            if hasattr(db_instance, "get_refractive_index"):
                val = db_instance.get_refractive_index(material_id, wavelength_nm)
            else:
                val = db_instance.get_index(material_id, wavelength_nm)
            
            if isinstance(val, complex):
                if abs(val.imag) < 1e-9:
                    return val.real
                return val
            return float(val)

        except (KeyError, ValueError, AttributeError):
            pass

    try:
        return float(material_id)

    except (ValueError, TypeError):
        try:
            return complex(material_id)
        except (ValueError, TypeError):
            # Fallback to default refractive index
            return 1.5


def get_refractive_clues_vectorized(material_id: Any, wavelengths: np.ndarray, db_instance=None) -> np.ndarray:

    n = len(wavelengths)

    if not isinstance(material_id, str):
        return np.full(n, float(material_id), dtype=np.float64)

    # Try Database

    if db_instance is not None:
        try:
            # Use complex128 to assume ge@njit(cache=True, fastmath=True, error_model="numpy")

            res = np.empty(n, dtype=np.complex128)

            for i in range(n):
                # RobustMaterialDatabase uses get_refractive_index, standard might use get_index

                if hasattr(db_instance, "get_refractive_index"):
                    res[i] = db_instance.get_refractive_index(material_id, wavelengths[i])

                else:
                    res[i] = db_instance.get_index(material_id, wavelengths[i])

            return res

        except (KeyError, ValueError, AttributeError):
            pass  # Fallback

    # Simple Parse for constants "1.45" passed as string

    try:
        val = float(material_id)

        return np.full(n, val, dtype=np.float64)

    except (ValueError, TypeError):
        # Fallback to default if conversion fails

        pass

    return np.full(n, 1.5, dtype=np.float64)


# Note: calculate_RT_vectorized_real_HL is defined earlier (line ~950) with backside support


# =============================================================================


# =========================================================================================


# [MONOLITHIC BLOCK] STRAT KERNELS


# DO NOT SPLIT - High performance growth simulation kernels


# =========================================================================================


# STRAT KERNELS


# =============================================================================


# --- 6.1 Extrema Detection ---


# --- MODIFIED (Opus 4.7b) --- Arrival AND start checks asymmetric on wavelength change.


# Macleod convention (+1j). Pre-multiply + Air->Sub.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def check_extrema_proximity(
    wl,
    n_current,
    n_previous,
    n_Sub,
    thickness_nominal,
    M_before,
    exclusion_width,
    check_start,
    wl_changed=False,
) -> bool:
    """

    Checks if wavelength is too close to a transmission extremum.

    ARRIVAL CHECK is asymmetric (Opus 4.7):

      - Forbidden zone BEFORE a turning point: 3 * exclusion_width  (wide)

      - Forbidden zone AFTER  a turning point: 1 * exclusion_width  (narrow)

    START CHECK (Opus 4.7b) - asymmetric only when wl_changed=True:

      - Symmetric +/-δe check always applied (unchanged behaviour)

      - If wl_changed: also reject if TP is AHEAD within [0, 3δe] (new wavelength

        starts with no prior monitoring info -> be more cautious before a TP)

    """

    m00, m01 = M_before[0, 0], M_before[0, 1]

    m10, m11 = M_before[1, 0], M_before[1, 1]

    if wl < 0.1:
        return False

    # Constants and Tolerance - always double precision

    TWO_PI_VAL = TWO_PI

    TOL = 1e-9

    if check_start:
        denom_pres = m00 + n_Sub * m11 + n_Sub * m01 + m10

        T_pres = 0.0

        if abs(denom_pres) > 1e-9:
            t_pres = 2.0 / denom_pres

            T_pres = n_Sub.real * (t_pres.real**2 + t_pres.imag**2)

        phi_f = (TWO_PI_VAL / wl) * n_current * exclusion_width

        cp_f, sp_f = np.cos(phi_f), np.sin(phi_f)

        son_f = (sp_f / n_current) if abs(n_current) > 1e-9 else 0.0

        mf00, mf01 = cp_f, +1j * son_f

        mf10, mf11 = +1j * n_current * sp_f, cp_f

        M_future_00 = mf00 * m00 + mf01 * m10

        M_future_01 = mf00 * m01 + mf01 * m11

        M_future_10 = mf10 * m00 + mf11 * m10

        M_future_11 = mf10 * m01 + mf11 * m11

        denom_fut = M_future_00 + n_Sub * M_future_11 + n_Sub * M_future_01 + M_future_10

        T_fut = 0.0

        if abs(denom_fut) > 1e-9:
            t_fut = 2.0 / denom_fut

            T_fut = n_Sub.real * (t_fut.real**2 + t_fut.imag**2)

        n_prev_safe = n_previous if n_previous.real > 0.0 else n_current

        phi_p = (TWO_PI_VAL / wl) * n_prev_safe * (-exclusion_width)

        cp_p, sp_p = np.cos(phi_p), np.sin(phi_p)

        son_p = (sp_p / n_prev_safe) if abs(n_prev_safe) > 1e-9 else 0.0

        mp00, mp01 = cp_p, +1j * son_p

        mp10, mp11 = +1j * n_prev_safe * sp_p, cp_p

        M_past_00 = mp00 * m00 + mp01 * m10

        M_past_01 = mp00 * m01 + mp01 * m11

        M_past_10 = mp10 * m00 + mp11 * m10

        M_past_11 = mp10 * m01 + mp11 * m11

        denom_past = M_past_00 + n_Sub * M_past_11 + n_Sub * M_past_01 + M_past_10

        T_past = 0.0

        if abs(denom_past) > 1e-9:
            t_past = 2.0 / denom_past

            T_past = n_Sub.real * (t_past.real**2 + t_past.imag**2)

        # Case 1 (symmetric +/-δe, always active): d=0 is at an extremum

        diff1, diff2 = T_pres - T_past, T_fut - T_pres

        if (diff1 > TOL and diff2 < -TOL) or (diff1 < -TOL and diff2 > TOL):
            return False

        # Case 2 (asymmetric, only when wl changed): TP is AHEAD within [δe, 3δe]

        # i.e., starting this layer on the new lambda would place us just before a TP

        if wl_changed:
            phi_ff = (TWO_PI_VAL / wl) * n_current * (3.0 * exclusion_width)

            cp_ff, sp_ff = np.cos(phi_ff), np.sin(phi_ff)

            son_ff = (sp_ff / n_current) if abs(n_current) > 1e-9 else 0.0

            mff00, mff01 = cp_ff, +1j * son_ff

            mff10, mff11 = +1j * n_current * sp_ff, cp_ff

            M_far_00 = mff00 * m00 + mff01 * m10

            M_far_01 = mff00 * m01 + mff01 * m11

            M_far_10 = mff10 * m00 + mff11 * m10

            M_far_11 = mff10 * m01 + mff11 * m11

            denom_far = M_far_00 + n_Sub * M_far_11 + n_Sub * M_far_01 + M_far_10

            T_far = 0.0

            if abs(denom_far) > 1e-9:
                t_far = 2.0 / denom_far

                T_far = n_Sub.real * (t_far.real**2 + t_far.imag**2)

            # s_mid = T_fut - T_pres (already computed above)

            # s_right = T_far - T_fut (over 2δe, normed)

            s_mid_s = T_fut - T_pres

            s_right_s = (T_far - T_fut) / 2.0

            if (s_mid_s > TOL and s_right_s < -TOL) or (s_mid_s < -TOL and s_right_s > TOL):
                return False

    if thickness_nominal > exclusion_width:
        # --- ASYMMETRIC ARRIVAL CHECK (Opus 4.7) ---

        # Physical rationale: stopping just BEFORE a turning point is forbidden

        # (signal still evolving toward an unknown extremum -> imprecise cut-off).

        # Stopping just AFTER is safer (turning point already detected and passed).

        #

        # Forbidden zone around a turning point at d_tp:

        #   [d_tp - 3*exclusion_width,  d_tp + exclusion_width]

        # Equivalent: reject d_nom if a TP exists in [d_nom - δe, d_nom + 3δe].

        #

        # 4 sample points: [d-δe,  d,  d+δe,  d+3δe]

        #   s_left  = T[1]-T[0]           slope just before d  (width δe)

        #   s_mid   = T[2]-T[1]           slope just after  d  (width δe)

        #   s_right = (T[3]-T[2]) / 2.0   slope further ahead  (width 2δe, normed)

        #

        # Reject (return False) if:

        #   Case 1 - TP within δe of d on either side:     sign(s_left) != sign(s_mid)

        #   Case 2 - TP ahead of d within [d+δe, d+3δe]:  sign(s_mid)  != sign(s_right)

        points = np.array(
            [
                thickness_nominal - exclusion_width,
                thickness_nominal,
                thickness_nominal + exclusion_width,
                thickness_nominal + 3.0 * exclusion_width,
            ]
        )

        T_end = np.zeros(4)

        for k in range(4):
            d = points[k]

            phi = (TWO_PI_VAL / wl) * n_current * d

            cp, sp = np.cos(phi), np.sin(phi)

            son = (sp / n_current) if abs(n_current) > 1e-9 else 0.0

            ml00, ml01 = cp, +1j * son

            ml10, ml11 = +1j * n_current * sp, cp

            mt00 = ml00 * m00 + ml01 * m10

            mt01 = ml00 * m01 + ml01 * m11

            mt10 = ml10 * m00 + ml11 * m10

            mt11 = ml10 * m01 + ml11 * m11

            denom = mt00 + n_Sub * mt11 + n_Sub * mt01 + mt10

            if abs(denom) > 1e-9:
                t = 2.0 / denom

                T_end[k] = n_Sub.real * (t.real**2 + t.imag**2)

        s_left = T_end[1] - T_end[0]

        s_mid = T_end[2] - T_end[1]

        s_right = (T_end[3] - T_end[2]) / 2.0

        TOL_E = 1e-9

        # Case 1: d is near an extremum (symmetric δe margin - preserves original behaviour)

        if (s_left > TOL_E and s_mid < -TOL_E) or (s_left < -TOL_E and s_mid > TOL_E):
            return False

        # Case 2: TP is AHEAD of d within [d+δe, d+3δe] -> d is approaching it -> reject

        if (s_mid > TOL_E and s_right < -TOL_E) or (s_mid < -TOL_E and s_right > TOL_E):
            return False

    return True


# --- MODIFIED (Opus 4.7c) --- Extrema Proximity Calculator (for Report)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_extrema_distances(
    wl: float,
    n_current: complex,
    n_Sub: complex,
    thickness_nominal: float,
    M_before: np.ndarray,
) -> tuple[float, float, float, float]:
    """

    Performs a mini-scan to find the exact distance (in nm) to the nearest

    transmission extrema (turning points) from d=0 (start) and d=thickness_nominal (end).

    Returns:

        (dist_prev_start, dist_next_start, dist_prev_end, dist_next_end)

        Positive distances mean the extremum is purely that far away (absolute distance).

        If no extremum is found within 200nm, returns 999.0 for that value.

    """

    m00, m01 = M_before[0, 0], M_before[0, 1]

    m10, m11 = M_before[1, 0], M_before[1, 1]

    if wl < 0.1:
        return 999.0, 999.0, 999.0, 999.0

    TWO_PI_VAL = TWO_PI

    # Scan around d=0 and d=thickness_nominal using two narrow windows instead of the whole layer

    # We need to scale scan range. OT = n * d. So physical d range corresponding to 16 OT is 16/n.

    # We will scan physically wide enough, then convert distance to OT.

    scan_ot = 16.0

    physical_scan_radius = scan_ot / float(abs(n_current)) if abs(n_current) > 1e-9 else 16.0

    step = 0.5

    # helper for one narrow window

    def scan_window(center):

        start_w = center - physical_scan_radius

        end_w = center + physical_scan_radius

        pts = int((end_w - start_w) / step) + 1

        d_arr = np.zeros(pts)

        T_arr = np.zeros(pts)

        for i in range(pts):
            d = start_w + i * step

            d_arr[i] = d

            phi = (TWO_PI_VAL / wl) * n_current * d

            cp, sp = np.cos(phi), np.sin(phi)

            son = (sp / n_current) if abs(n_current) > 1e-9 else 0.0

            ml00, ml01 = cp, +1j * son

            ml10, ml11 = +1j * n_current * sp, cp

            mt00 = ml00 * m00 + ml01 * m10

            mt01 = ml00 * m01 + ml01 * m11

            mt10 = ml10 * m00 + ml11 * m10

            mt11 = ml10 * m01 + ml11 * m11

            denom = mt00 + n_Sub * mt11 + n_Sub * mt01 + mt10

            if abs(denom) > 1e-9:
                t = 2.0 / denom

                T_arr[i] = n_Sub.real * (t.real**2 + t.imag**2)

        return d_arr, T_arr

    extrema_d = []

    TOL = 1e-9

    # Window 1: Start (d=0)

    d_scan1, T_scan1 = scan_window(0.0)

    for i in range(1, len(d_scan1) - 1):
        s_left = T_scan1[i] - T_scan1[i - 1]

        s_right = T_scan1[i + 1] - T_scan1[i]

        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan1[i])

    # Window 2: End (d=thickness_nominal)

    d_scan2, T_scan2 = scan_window(thickness_nominal)

    for i in range(1, len(d_scan2) - 1):
        s_left = T_scan2[i] - T_scan2[i - 1]

        s_right = T_scan2[i + 1] - T_scan2[i]

        if (s_left > TOL and s_right < -TOL) or (s_left < -TOL and s_right > TOL):
            extrema_d.append(d_scan2[i])

    # Now find distances to 0.0 and to thickness_nominal IN OPTICAL THICKNESS

    n_real = float(n_current.real)

    dist_prev_start, dist_next_start = 999.0, 999.0

    dist_prev_end, dist_next_end = 999.0, 999.0

    for ed in extrema_d:
        # Convert physical diff to OT diff

        diff_start_ot = (ed - 0.0) * n_real

        if diff_start_ot <= 0:
            dist_prev_start = min(dist_prev_start, abs(diff_start_ot))

        if diff_start_ot >= 0:
            dist_next_start = min(dist_next_start, abs(diff_start_ot))

        # For End (d=thickness_nominal)

        diff_end_ot = (ed - thickness_nominal) * n_real

        if diff_end_ot <= 0:
            dist_prev_end = min(dist_prev_end, abs(diff_end_ot))

        if diff_end_ot >= 0:
            dist_next_end = min(dist_next_end, abs(diff_end_ot))

    return dist_prev_start, dist_next_start, dist_prev_end, dist_next_end


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def fit_parabola_vertex_3points(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:

    x1, x2, x3 = x[0], x[1], x[2]

    y1, y2, y3 = y[0], y[1], y[2]

    denom = (x1 - x2) * (x1 - x3) * (x2 - x3)

    if abs(denom) < 1e-12:
        return 0.0, 0.0, y1

    a = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / denom

    b = (x3 * x3 * (y1 - y2) + x2 * x2 * (y3 - y1) + x1 * x1 * (y2 - y3)) / denom

    c = (x2 * x3 * (x2 - x3) * y1 + x3 * x1 * (x3 - x1) * y2 + x1 * x2 * (x1 - x2) * y3) / denom

    return a, b, c


# ─── NUMBA GRAPH-PARTITIONING OPTIMIZATION PHASE B ───


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _compute_valid_blocks_kernel(
    layer_wls: np.ndarray,
    layer_costs: np.ndarray,
    valid_mask: np.ndarray,
    num_layers: int,
    top_k: int,
    max_W: int,
):

    block_costs = np.full((num_layers + 1, num_layers + 1, top_k), np.inf, dtype=np.float64)

    block_wls = np.full((num_layers + 1, num_layers + 1, top_k), -1.0, dtype=np.float64)

    block_counts = np.zeros((num_layers + 1, num_layers + 1), dtype=np.int32)

    for i in range(num_layers):
        for j in range(i + 1, num_layers + 1):
            bl_ok = True

            for l in range(i, j):
                has_any = False

                for w in range(max_W):
                    if valid_mask[l, w]:
                        has_any = True

                        break

                if not has_any:
                    bl_ok = False

                    break

            if not bl_ok:
                continue

            base_l = i

            min_count = 999999

            for l in range(i, j):
                c = 0

                for w in range(max_W):
                    if valid_mask[l, w]:
                        c += 1

                if c < min_count:
                    min_count = c

                    base_l = l

            temp_costs = np.zeros(max_W, dtype=np.float64)

            temp_wls = np.zeros(max_W, dtype=np.float64)

            temp_count = 0

            for base_w_idx in range(max_W):
                if not valid_mask[base_l, base_w_idx]:
                    continue

                wl = layer_wls[base_l, base_w_idx]

                total_cost = layer_costs[base_l, base_w_idx]

                is_valid = True

                for l in range(i, j):
                    if l == base_l:
                        continue

                    found = False

                    for w in range(max_W):
                        if valid_mask[l, w] and abs(layer_wls[l, w] - wl) < 1e-5:
                            total_cost += layer_costs[l, w]

                            found = True

                            break

                    if not found:
                        is_valid = False

                        break

                if is_valid:
                    temp_costs[temp_count] = total_cost

                    temp_wls[temp_count] = wl

                    temp_count += 1

            if temp_count > 0:
                for x in range(temp_count):
                    for y in range(x + 1, temp_count):
                        if temp_costs[y] < temp_costs[x]:
                            tc = temp_costs[x]

                            temp_costs[x] = temp_costs[y]

                            temp_costs[y] = tc

                            tw = temp_wls[x]

                            temp_wls[x] = temp_wls[y]

                            temp_wls[y] = tw

                take = min(temp_count, top_k)

                for k in range(take):
                    block_costs[i, j, k] = temp_costs[k]

                    block_wls[i, j, k] = temp_wls[k]

                block_counts[i, j] = take

    return block_costs, block_wls, block_counts


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _dp_kernel(
    block_costs: np.ndarray,
    block_wls: np.ndarray,
    block_counts: np.ndarray,
    n_blocks: int,
    num_layers: int,
    top_k: int,
):

    dp_costs = np.full((n_blocks + 1, num_layers + 1, top_k * 2), np.inf, dtype=np.float64)

    dp_paths_start = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)

    dp_paths_end = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)

    dp_paths_wl = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1.0, dtype=np.float64)

    dp_counts = np.zeros((n_blocks + 1, num_layers + 1), dtype=np.int32)

    dp_costs[0, 0, 0] = 0.0

    dp_counts[0, 0] = 1

    max_cands = top_k * 2

    temp_costs = np.zeros(max_cands, dtype=np.float64)

    temp_paths_start = np.full((max_cands, n_blocks), -1, dtype=np.int32)

    temp_paths_end = np.full((max_cands, n_blocks), -1, dtype=np.int32)

    temp_paths_wl = np.full((max_cands, n_blocks), -1.0, dtype=np.float64)

    for k in range(1, n_blocks + 1):
        for i in range(k, num_layers + 1):
            c_count = 0

            for j in range(k - 1, i):
                prev_count = dp_counts[k - 1, j]

                if prev_count == 0:
                    continue

                bl_count = block_counts[j, i]

                if bl_count == 0:
                    continue

                for p in range(prev_count):
                    prev_cost = dp_costs[k - 1, j, p]

                    for b in range(min(10, bl_count)):
                        total_cost = prev_cost + block_costs[j, i, b]

                        wl = block_wls[j, i, b]

                        if c_count == max_cands and total_cost >= temp_costs[max_cands - 1]:
                            continue

                        idx = c_count if c_count < max_cands else max_cands - 1

                        while idx > 0 and temp_costs[idx - 1] > total_cost:
                            if idx < max_cands:
                                temp_costs[idx] = temp_costs[idx - 1]

                                for _b in range(n_blocks):
                                    temp_paths_start[idx, _b] = temp_paths_start[idx - 1, _b]

                                    temp_paths_end[idx, _b] = temp_paths_end[idx - 1, _b]

                                    temp_paths_wl[idx, _b] = temp_paths_wl[idx - 1, _b]

                            idx -= 1

                        temp_costs[idx] = total_cost

                        for old_h in range(k - 1):
                            temp_paths_start[idx, old_h] = dp_paths_start[k - 1, j, p, old_h]

                            temp_paths_end[idx, old_h] = dp_paths_end[k - 1, j, p, old_h]

                            temp_paths_wl[idx, old_h] = dp_paths_wl[k - 1, j, p, old_h]

                        temp_paths_start[idx, k - 1] = j

                        temp_paths_end[idx, k - 1] = i

                        temp_paths_wl[idx, k - 1] = wl

                        if c_count < max_cands:
                            c_count += 1

            if c_count > 0:
                for t in range(c_count):
                    dp_costs[k, i, t] = temp_costs[t]

                    for _b in range(n_blocks):
                        dp_paths_start[k, i, t, _b] = temp_paths_start[t, _b]

                        dp_paths_end[k, i, t, _b] = temp_paths_end[t, _b]

                        dp_paths_wl[k, i, t, _b] = temp_paths_wl[t, _b]

                dp_counts[k, i] = c_count

    return dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _solve_quadratic_target(a: float, b: float, c: float, target_y: float, current_x: float) -> float:

    c_prime = c - target_y

    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            return -c_prime / b

        return current_x

    discriminant = b * b - 4.0 * a * c_prime

    if discriminant >= 0.0:
        sqrt_disc = np.sqrt(discriminant)

        sol1 = (-b + sqrt_disc) / (2.0 * a)

        sol2 = (-b - sqrt_disc) / (2.0 * a)

        if abs(sol1 - current_x) < abs(sol2 - current_x):
            return sol1

        return sol2

    else:
        return -b / (2.0 * a)


# --- 6.2 Growth Simulation ---


# --- LOCKED --- Validated by test_tmm_inline.py (test 2) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


# Non-monotonic handling modes (for simulate_growth_kernel)


NON_MONOTONIC_MODE_ATTENUATE = 0  # Divide error by factor (legacy behavior)


NON_MONOTONIC_MODE_REJECT = 1  # Reject candidate (return large error)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_growth_kernel(
    p_thick_nominal: np.ndarray,
    i_layer: int,
    prev_thicknesses_sim: np.ndarray,
    wl: float,
    n_H,
    n_L,
    n_Sub,  # float or complex (Numba multi-dispatch)
    probe_offset: float,
    noise_val_precalc: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
) -> tuple[float, float]:
    """

    Fast TMM Simulation for robustness heuristics.

    CRITICAL PHYSICS NOTE:

    This kernel calculates T_front (Internal Transmission) ONLY.

    It intentionally IGNORES backside reflection for computational speed in heuristics.

    Do not use for absolute photometric accuracy. Use calculate_detailed_growth for that.

    This is a RELATIVE control kernel: target extraction and inversion both use the

    same front-only model, so there is no absolute backside mismatch in this loop.

    Args:

        non_monotonic_mode: How to handle non-monotonic T(d) curves:

            0 (ATTENUATE): Divide error by non_monotonic_factor (legacy)

            1 (REJECT): Return large penalty to reject candidate

    """

    if wl < 0.1:
        return float(p_thick_nominal[i_layer]), 0.0

    # Numba infers precision from input dtypes automatically.

    TWO_PI_VAL = TWO_PI

    M_before_00 = 1.0 + 0j

    M_before_01 = 0.0 + 0j

    M_before_10 = 0.0 + 0j

    M_before_11 = 1.0 + 0j

    for j in range(i_layer):
        n_prev = n_H if (j % 2) == 0 else n_L

        th_prev = prev_thicknesses_sim[j]

        phi = (TWO_PI_VAL / wl) * n_prev * th_prev

        cp, sp = np.cos(phi), np.sin(phi)

        son = (sp / n_prev) if abs(n_prev) > 1e-9 else 0.0

        m01 = +1j * son

        m10 = +1j * n_prev * sp

        # TMM CONVENTION: Air->Sub. M_new = L_new @ M_old (pre-multiply)

        t00 = cp * M_before_00 + m01 * M_before_10

        t01 = cp * M_before_01 + m01 * M_before_11

        t10 = m10 * M_before_00 + cp * M_before_10

        t11 = m10 * M_before_01 + cp * M_before_11

        M_before_00, M_before_01, M_before_10, M_before_11 = t00, t01, t10, t11

    nominal_th = p_thick_nominal[i_layer]

    n_current = n_H if (i_layer % 2) == 0 else n_L

    is_non_monotonic = False

    # Check monotonicity & Target T

    # Zero-Allocation: Only compute the 5 points needed for monotonicity check
    T_mono = np.zeros(5, dtype=np.float64)

    if nominal_th > 1e-4:
        for k in range(5):
            th_frac = (k / 4.0) * nominal_th

            phi_c = (TWO_PI_VAL / wl) * n_current * th_frac

            cp_c, sp_c = np.cos(phi_c), np.sin(phi_c)

            son_c = (sp_c / n_current) if abs(n_current) > 1e-9 else 0.0

            # M_total = L_current @ M_before (pre-multiply)

            m01_c = +1j * son_c

            m10_c = +1j * n_current * sp_c

            a00 = cp_c * M_before_00 + m01_c * M_before_10

            a01 = cp_c * M_before_01 + m01_c * M_before_11

            a10 = m10_c * M_before_00 + cp_c * M_before_10

            a11 = m10_c * M_before_01 + cp_c * M_before_11

            # Air->Sub Transmission (n_inc=1, n_exit=n_Sub)

            denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

            if abs(denom) > 1e-9:
                T_mono[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)

        # Monotonicity check logic
        diffs = np.zeros(4, dtype=np.float64)
        for k in range(4):
            diffs[k] = T_mono[k+1] - T_mono[k]

        flips = 0
        current_sign = 0.0

        if diffs[0] > 1e-9:
            current_sign = 1.0
        elif diffs[0] < -1e-9:
            current_sign = -1.0

        for k in range(1, 4):
            next_sign = 0.0
            if diffs[k] > 1e-9:
                next_sign = 1.0
            elif diffs[k] < -1e-9:
                next_sign = -1.0

            if next_sign != 0.0:
                if current_sign != 0.0 and next_sign != current_sign:
                    flips += 1
                current_sign = next_sign

        if flips > 0:
            is_non_monotonic = True

    target_T_noisy = T_mono[4] + noise_val_precalc

    # Numerical solve via parabolic probe

    th_points = np.array([max(0.1, nominal_th - probe_offset), nominal_th, nominal_th + probe_offset])

    T_points = np.zeros(3)

    for k in range(3):
        d = th_points[k]

        phi = (TWO_PI_VAL / wl) * n_current * d

        cp, sp = np.cos(phi), np.sin(phi)

        son = (sp / n_current) if abs(n_current) > 1e-9 else 0.0

        m01 = +1j * son

        m10 = +1j * n_current * sp

        a00 = cp * M_before_00 + m01 * M_before_10

        a01 = cp * M_before_01 + m01 * M_before_11

        a10 = m10 * M_before_00 + cp * M_before_10

        a11 = m10 * M_before_01 + cp * M_before_11

        denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

        if abs(denom) > 1e-9:
            T_points[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)

    a_quad, b_quad, c_quad = fit_parabola_vertex_3points(th_points, T_points)

    calc_thick = _solve_quadratic_target(a_quad, b_quad, c_quad, target_T_noisy, nominal_th)

    error_raw = calc_thick - nominal_th

    dyn_encounter = 0.0

    if nominal_th > 1e-4:
        dyn_encounter = np.max(T_mono) - np.min(T_mono)

    # Non-monotonic handling

    if is_non_monotonic:
        if non_monotonic_mode == NON_MONOTONIC_MODE_REJECT:
            # Return nominal thickness with a large penalty error signal

            # The caller will see a very large error for this candidate

            return nominal_th + 1e6, dyn_encounter

        else:
            # Legacy: attenuate error by dividing

            gain = non_monotonic_factor

            return max(0.0, nominal_th + (error_raw / gain)), dyn_encounter

    return max(0.0, nominal_th + error_raw), dyn_encounter


# --- STRAT: transmission sensitivity for thickness-noise conversion ---


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_at_layer(
    wl: float,
    n_layer,
    n_Sub,
    M_before_00,
    M_before_01,
    M_before_10,
    M_before_11,
    d: float,
) -> float:
    """

    Compute front-side T at end of a single layer (same convention as simulate_growth_kernel).

    Used to compute dT/dd for converting thickness noise (nm) to transmission noise.

    """

    if wl < 0.1:
        return 0.0

    TWO_PI_VAL = TWO_PI

    phi = (TWO_PI_VAL / wl) * n_layer * d

    cp, sp = np.cos(phi), np.sin(phi)

    son = (sp / n_layer) if abs(n_layer) > 1e-9 else 0.0

    m01 = +1j * son

    m10 = +1j * n_layer * sp

    a00 = cp * M_before_00 + m01 * M_before_10

    a01 = cp * M_before_01 + m01 * M_before_11

    a10 = m10 * M_before_00 + cp * M_before_10

    a11 = m10 * M_before_01 + cp * M_before_11

    denom = a00 + n_Sub * a01 + a10 + n_Sub * a11

    if abs(denom) > 1e-9:
        return float(4.0 * np.real(n_Sub) / (denom.real**2 + denom.imag**2))

    return 0.0


# --- 6.3 Validation Batch ---


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def validate_wavelengths_batch(
    candidate_wls,
    n_H_arr,
    n_L_arr,
    n_Sub_arr,
    runs_history,
    p_thick_nominal,
    i_layer,
    probe_offset,
    noise_values,
    non_monotonic_factor,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
):

    n_cands = len(candidate_wls)

    n_runs = runs_history.shape[0]

    results = np.zeros((n_cands, 2))

    # Zero-Allocation: Pre-allocate thread-local buffer outside the parallel loop
    error_buffer = np.empty((n_cands, n_runs), dtype=np.float64)

    for c_idx in prange(n_cands):
        wl = candidate_wls[c_idx]

        for r_idx in range(n_runs):
            prev_th = runs_history[r_idx, :i_layer]

            val, _ = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                prev_th,
                wl,
                n_H_arr[c_idx],
                n_L_arr[c_idx],
                n_Sub_arr[c_idx],
                probe_offset,
                noise_values[r_idx],
                non_monotonic_factor,
                non_monotonic_mode,
            )

            error_buffer[c_idx, r_idx] = np.abs(val - p_thick_nominal[i_layer])

        # P95-first policy: cost uses high-percentile absolute error
        # to keep margin cases in ranking decisions.
        p95 = np.percentile(error_buffer[c_idx, :], 95.0)
        results[c_idx, 0] = p95
        results[c_idx, 1] = np.std(error_buffer[c_idx, :])

    return results


# --- 6.3b Full Stack Robustness Simulation Batch (New Phase B Kernel) ---


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_stack_robustness_batch(
    p_thick_nominal: np.ndarray,
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    noise_matrix: np.ndarray,  # (n_runs, n_layers)
    probe_offset: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
) -> tuple[np.ndarray, np.ndarray]:
    """

    Simulates growth for the entire stack for multiple MCS runs in parallel.

    Returns: (simulated_thicknesses, average_dynamics_per_layer)

    """

    n_runs = noise_matrix.shape[0]

    n_layers = len(p_thick_nominal)

    results = np.empty((n_runs, n_layers), dtype=np.float64)

    all_dyns = np.empty((n_runs, n_layers), dtype=np.float64)

    # Zero-Allocation: pre-allocate memory for run stack tracking
    current_run_th_buffer = np.empty((n_runs, n_layers), dtype=np.float64)

    for r in prange(n_runs):
        for i_layer in range(n_layers):
            wl = layer_wavelengths[i_layer]

            n_H, n_L, n_Sub = n_H_vals[i_layer], n_L_vals[i_layer], n_Sub_vals[i_layer]

            noise_val = noise_matrix[r, i_layer]

            val, dyn = simulate_growth_kernel(
                p_thick_nominal,
                i_layer,
                current_run_th_buffer[r, :i_layer],
                wl,
                n_H,
                n_L,
                n_Sub,
                probe_offset,
                noise_val,
                non_monotonic_factor,
                non_monotonic_mode,
            )

            current_run_th_buffer[r, i_layer] = val

            results[r, i_layer] = val

            all_dyns[r, i_layer] = dyn

    avg_dyns = np.zeros(n_layers, dtype=np.float64)

    for l in range(n_layers):
        sum_dyn = 0.0

        for r in range(n_runs):
            sum_dyn += all_dyns[r, l]

        avg_dyns[l] = sum_dyn / n_runs

    return results, avg_dyns


@njit(parallel=True, cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_batch_rmse(
    sim_thick_batch: np.ndarray,
    wls: np.ndarray,
    nH_arr: np.ndarray,  # (n_wls, n_layers) or (n_wls,) depending on implementation needed
    nL_arr: np.ndarray,  # We probably need n_layers_all_wls structure or similar
    nSub_arr: np.ndarray,  # (n_wls,)
    T_target: np.ndarray,
    n_layers_flattened: np.ndarray,  # (n_wls, n_layers) - pre-computed n complex for all layers
) -> np.ndarray:
    """Computes RMSE for a batch of simulated thicknesses against a target T spectrum.

    Args:

        sim_thick_batch: (n_runs, n_layers)

        wls: (n_wls,)

        nSub_arr: (n_wls,)

        T_target: (n_wls,)

        n_layers_flattened: (n_wls, n_layers) complex array of refractive clues

                           This must be pre-assembled: [n0_w0, n1_w0...; n0_w1, n1_w1...]

    Returns:

        rmse_arr: (n_runs,)"""

    n_runs = sim_thick_batch.shape[0]

    n_wls = len(wls)

    rmse_arr = np.empty(n_runs, dtype=np.float64)

    # Pre-calculate k0

    k0_arr = TWO_PI / wls

    for r in prange(n_runs):
        thicknesses = sim_thick_batch[r]

        mse_sum = 0.0

        # Inner loop over wavelengths

        for i_wl in range(n_wls):
            Rf, Tf, Rb = compute_TMM_single_point_k0_exact(
                k0_arr[i_wl], thicknesses, n_layers_flattened[i_wl], nSub_arr[i_wl]
            )

            # Backside correction (exact incoherent combination) - Float64 logic

            ns_real = nSub_arr[i_wl].real

            r_sub = (ns_real - 1.0) / (ns_real + 1.0)

            R_sub_air = r_sub * r_sub

            T_sub_air = 1.0 - R_sub_air

            denom = 1.0 - Rb * R_sub_air

            if denom < 1e-12:
                denom = 1e-12

            T_total = (Tf * T_sub_air) / denom

            diff = T_total - T_target[i_wl]

            mse_sum += diff * diff

        rmse_arr[r] = np.sqrt(mse_sum / n_wls)

    return rmse_arr


# --- 6.4 Dynamic Calculation ---


# --- LOCKED --- Validated by test_tmm_inline.py (test 1, via cache) ───


# Macleod convention (+1j). Pre-multiply (L @ M). DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def precompute_matrix_cache_kernel(
    all_wls: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    p_thick_nominal: np.ndarray,
    num_layers: int,
) -> np.ndarray:
    """Parallel computation of nominal transfer matrix cache.

    Supports complex refractive clues for nH and nL."""

    n_wls = len(all_wls)

    TWO_PI_LOCAL = 2.0 * np.pi

    cache = np.zeros((num_layers, n_wls, 2, 2), dtype=np.complex128)

    for wl_idx in prange(n_wls):
        wl = all_wls[wl_idx]

        inv_wl = TWO_PI_LOCAL / wl

        # Cumulative matrix (identity start)

        M00 = complex(1.0, 0.0)

        M01 = complex(0.0, 0.0)

        M10 = complex(0.0, 0.0)

        M11 = complex(1.0, 0.0)

        for i_layer in range(num_layers):
            n_layer = n_H_arr[wl_idx] if (i_layer % 2) == 0 else n_L_arr[wl_idx]

            thickness = p_thick_nominal[i_layer]

            phi = inv_wl * n_layer * thickness

            cp = np.cos(phi)

            isp = +1j * np.sin(phi)

            if abs(n_layer) > 1e-12:
                m01 = isp / n_layer

            else:
                m01 = 0.0j

            m10 = isp * n_layer

            # M_new = L @ M_old (aligned with reference verify_matrix_cache: index 0 = substrate)

            t00 = cp * M00 + m01 * M10

            t01 = cp * M01 + m01 * M11

            t10 = m10 * M00 + cp * M10

            t11 = m10 * M01 + cp * M11

            M00, M01, M10, M11 = t00, t01, t10, t11

            # Store cumulative

            cache[i_layer, wl_idx, 0, 0] = M00

            cache[i_layer, wl_idx, 0, 1] = M01

            cache[i_layer, wl_idx, 1, 0] = M10

            cache[i_layer, wl_idx, 1, 1] = M11

    return cache


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def prepare_dynamics_data_kernel(
    wls_array: np.ndarray,
    all_wls: np.ndarray,
    nominal_matrix_cache: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    n_Sub_arr: np.ndarray,
    i_layer: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Parallel preparation of data for dynamics calculation.

    """

    n = len(wls_array)

    n_layer_array = np.empty(n, dtype=np.complex128)

    n_sub_array = np.empty(n, dtype=np.complex128)

    M_before_stack = np.empty((n, 2, 2), dtype=np.complex128)

    for i in prange(n):
        wl = wls_array[i]

        # 1. Clues

        if (i_layer % 2) == 0:
            n_layer_array[i] = n_H_arr[i]

        else:
            n_layer_array[i] = n_L_arr[i]

        n_sub_array[i] = n_Sub_arr[i]

        # 2. Matrix Cache

        M_before_stack[i, 0, 0] = 1.0

        M_before_stack[i, 0, 1] = 0.0

        M_before_stack[i, 1, 0] = 0.0

        M_before_stack[i, 1, 1] = 1.0

        if i_layer > 0:
            # Fast Nearest Search

            idx = np.searchsorted(all_wls, wl)

            if idx >= len(all_wls):
                idx = len(all_wls) - 1

            elif idx > 0:
                diff_curr = abs(wl - all_wls[idx])

                diff_prev = abs(wl - all_wls[idx - 1])

                if diff_prev < diff_curr:
                    idx = idx - 1

            # Using complex matrix (Single Precision optimized)

            # nominal_matrix_cache shape: (n_layers, n_wls, 2, 2)

            M_before_stack[i, 0, 0] = nominal_matrix_cache[i_layer - 1, idx, 0, 0]

            M_before_stack[i, 0, 1] = nominal_matrix_cache[i_layer - 1, idx, 0, 1]

            M_before_stack[i, 1, 0] = nominal_matrix_cache[i_layer - 1, idx, 1, 0]

            M_before_stack[i, 1, 1] = nominal_matrix_cache[i_layer - 1, idx, 1, 1]

    return n_layer_array, n_sub_array, M_before_stack


# --- LOCKED --- Validated by test_tmm_inline.py (test 7, wrapper) ───


# DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def check_extrema_proximity_batch(
    wls: np.ndarray,
    n_currents: np.ndarray,
    n_previouss: np.ndarray,
    n_Subs: np.ndarray,
    thickness_nominal: float,
    M_befores: np.ndarray,
    exclusion_width: float,
    check_start: bool,
    wl_changed_arr: np.ndarray,
) -> np.ndarray:
    """

    Parallel batch version of check_extrema_proximity.

    wl_changed_arr: boolean array (len = len(wls)).

        True  -> candidate wavelength differs from previous layer's -> asymmetric start check.

        False -> same wavelength, symmetric start check only.

    """

    n = len(wls)

    results = np.empty(n, dtype=np.bool_)

    for i in prange(n):
        results[i] = check_extrema_proximity(
            wls[i],
            n_currents[i],
            n_previouss[i],
            n_Subs[i],
            thickness_nominal,
            M_befores[i],
            exclusion_width,
            check_start,
            wl_changed_arr[i],
        )

    return results


# --- LOCKED --- Validated by test_tmm_inline.py (test 1) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores):
    """

    Compute TMM dynamics: peak-to-peak range of T(d) over layer growth.

    For each wavelength, T(d) is evaluated at thickness steps from 0 to

    nominal thickness. The dynamics metric is T_max - T_min (not endpoint

    delta). Returns dynamics, t_init, t_final, t_min (min T over growth).

    Precision adapts to input dtypes via Numba JIT.

    """

    n_wls = wls.shape[0]

    n_steps = thicknesses.shape[0]

    dynamics = np.empty(n_wls, dtype=np.float64)

    t_init = np.empty(n_wls, dtype=np.float64)

    t_final = np.empty(n_wls, dtype=np.float64)

    t_min = np.empty(n_wls, dtype=np.float64)

    I_VAL = +1j

    for wl_idx in prange(n_wls):
        wl = wls[wl_idx]

        n_layer = n_layers[wl_idx]

        n_sub = n_subs[wl_idx]

        M_before_00 = M_befores[wl_idx, 0, 0]

        M_before_01 = M_befores[wl_idx, 0, 1]

        M_before_10 = M_befores[wl_idx, 1, 0]

        M_before_11 = M_befores[wl_idx, 1, 1]

        T_min_val = 2.0

        T_max = -1.0

        T_start = 0.0

        T_end = 0.0

        for step_idx in range(n_steps):
            thickness = thicknesses[step_idx]

            if wl < 0.1:
                T_current = 0.0

            else:
                phi = (TWO_PI / wl) * n_layer * thickness

                cp, sp = np.cos(phi), np.sin(phi)

                son = (sp / n_layer) if abs(n_layer) > 1e-9 else 0.0

                m01 = I_VAL * son

                m10 = I_VAL * n_layer * sp

                # L @ M_before (pre-multiply: new layer on air side)

                a00 = cp * M_before_00 + m01 * M_before_10

                a01 = cp * M_before_01 + m01 * M_before_11

                a10 = m10 * M_before_00 + cp * M_before_10

                a11 = m10 * M_before_01 + cp * M_before_11

                # Air->Sub formula (n_inc=1, n_exit=n_sub)

                denom = a00 + n_sub * a01 + a10 + n_sub * a11

                if abs(denom) > 1e-9:
                    T_current = 4.0 * np.real(n_sub) / (denom.real**2 + denom.imag**2)

                else:
                    T_current = 0.0

            if step_idx == 0:
                T_start = T_current

            if step_idx == n_steps - 1:
                T_end = T_current

            if T_current < T_min_val:
                T_min_val = T_current

            if T_current > T_max:
                T_max = T_current

        dynamics[wl_idx] = T_max - T_min_val

        t_init[wl_idx] = T_start

        t_final[wl_idx] = T_end

        t_min[wl_idx] = T_min_val

    return dynamics, t_init, t_final, t_min


# --- LOCKED --- Validated by test_tmm_coherence.py ───


# Macleod convention (+1j). index 0 = substrate. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _calculate_RT_HL_single_point(wl, nH, nL, n_s, thicknesses):
    """Single wavelength, single run TMM for HL stacks.

    CONVENTION: index 0 = layer 1 = substrate side (aligned with compute_TMM_single_point_k0_exact).

    j=0 -> nH, j=1 -> nL => Sub | nH(thicknesses[0]) | nL(thicknesses[1]) | Air."""

    k0 = TWO_PI / wl

    n_layers = len(thicknesses)

    I_VAL = +1j

    # Forward Air->Sub: M = L_{n-1} @ ... @ L_0 (pre-multiply, index 0 = substrate side)

    M00 = 1.0 + 0j

    M01 = 0.0 + 0j

    M10 = 0.0 + 0j

    M11 = 1.0 + 0j

    for j in range(n_layers):
        d = thicknesses[j]

        n_l = nH if j % 2 == 0 else nL

        phi = k0 * n_l * d

        cp = np.cos(phi)

        sp = np.sin(phi)

        son = (sp / n_l) if abs(n_l) > 1e-12 else 0.0j

        m01 = I_VAL * son

        m10 = I_VAL * n_l * sp

        # M_new = L @ M_old

        t00 = cp * M00 + m01 * M10

        t01 = cp * M01 + m01 * M11

        t10 = m10 * M00 + cp * M10

        t11 = m10 * M01 + cp * M11

        M00, M01, M10, M11 = t00, t01, t10, t11

    # --- Front (Air -> Sub): delegate to helper ---

    n_air = complex(1.0)

    R_front, T_front = compute_RT_from_matrix(M00, M01, M10, M11, n_air, n_s)

    # --- BACK REFLECTION (Sub -> Air) ---

    # Mp = L_0 @ ... @ L_{n-1} (Sub->Air, post-multiply)

    Mp00 = 1.0 + 0j

    Mp01 = 0.0 + 0j

    Mp10 = 0.0 + 0j

    Mp11 = 1.0 + 0j

    for j in range(n_layers):
        d = thicknesses[j]

        n_l = nH if j % 2 == 0 else nL

        phi = k0 * n_l * d

        cp = np.cos(phi)

        sp = np.sin(phi)

        son = (sp / n_l) if abs(n_l) > 1e-12 else 0.0j

        m01 = I_VAL * son

        m10 = I_VAL * n_l * sp

        # Mp_new = Mp_old @ L

        t00 = Mp00 * cp + Mp01 * m10

        t01 = Mp00 * m01 + Mp01 * cp

        t10 = Mp10 * cp + Mp11 * m10

        t11 = Mp10 * m01 + Mp11 * cp

        Mp00, Mp01, Mp10, Mp11 = t00, t01, t10, t11

    # Back reflection: Sub -> Air, delegate to helper

    R_prime, _ = compute_RT_from_matrix(Mp00, Mp01, Mp10, Mp11, n_s, n_air)

    # --- Backside Interface (Sub|Air) ---

    nsr = n_s.real

    r_sub = (nsr - 1.0) / (nsr + 1.0)

    R_sub = r_sub * r_sub

    T_sub = 1.0 - R_sub

    # --- Combined result ---

    denom = 1.0 - R_prime * R_sub

    if denom < 1e-12:
        denom = 1e-12

    T_total = (T_front * T_sub) / denom

    R_total = R_front + (T_front * T_front * R_sub) / denom

    return R_total, T_total


# --- LOCKED --- Validated by test_tmm_coherence.py (via calculate_RT_vectorized_real_HL) ───


# Macleod convention (+1j). Batch TMM HL + backside exact. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, thicknesses_batch):
    """

    Parallel loop over 'num_runs', where each run is a full TMM spectral calculation.

    thicknesses_batch: (num_runs, num_layers)

    """

    n_runs = thicknesses_batch.shape[0]

    n_wls = wls.shape[0]

    R_batch = np.empty((n_runs, n_wls), dtype=np.float64)

    T_batch = np.empty((n_runs, n_wls), dtype=np.float64)

    for r in prange(n_runs):
        thicknesses = thicknesses_batch[r]

        for wl_idx in range(n_wls):
            r_val, t_val = _calculate_RT_HL_single_point(
                wls[wl_idx],
                nH_arr[wl_idx],
                nL_arr[wl_idx],
                nSub_arr[wl_idx],
                thicknesses,
            )

            R_batch[r, wl_idx] = r_val

            T_batch[r, wl_idx] = t_val

    return R_batch, T_batch


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def rank_nucleation_candidates_kernel(
    candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_vals: np.ndarray,  # (n_cand,) complex
    nL_vals: np.ndarray,  # (n_cand,) complex
    nSub_vals: np.ndarray,  # (n_cand,) complex
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    mc_runs: int,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel to rank candidate wavelengths for nucleation search.

    Replaces the sequential 'pre-ranking' loop in find_robust_nucleation_wavelength_adaptive.

    NOTE (Numba/runtime):

    Random sampling is generated inside the jitted kernel for performance.

    This is not an independent physics model: STRAT passes `use_gaussian=True`

    in production, and this kernel follows that policy.

    """

    n_cand = len(candidates)

    scores = np.zeros(n_cand, dtype=np.float64)

    for i in prange(n_cand):
        wl = candidates[i]

        nH = nH_vals[i]

        nL = nL_vals[i]

        nSub = nSub_vals[i]

        cumulative_sq_error = 0.0

        for run_idx in range(mc_runs):
            # Configurable noise distribution (STRAT uses gaussian-only).

            noise_vec = np.zeros(min_size, dtype=np.float64)
            for j in range(min_size):
                raw_j = _seeded_noise_sample(
                    seed_base=seed_base,
                    group_idx=i,
                    run_idx=run_idx,
                    elem_idx=j,
                    gaussian=use_gaussian,
                )
                noise_vec[j] = raw_j * noise_pct

            current_stack = np.zeros(min_size, dtype=np.float64)

            for j in range(min_size):
                th, _ = simulate_growth_kernel(
                    p_thick_nominal,
                    j,
                    current_stack[:j],
                    wl,
                    nH,
                    nL,
                    nSub,
                    offset_val,
                    noise_vec[j],
                    factor_val,
                    non_monotonic_mode,
                )

                current_stack[j] = th

                cumulative_sq_error += (th - p_thick_nominal[j]) ** 2

        scores[i] = np.sqrt(cumulative_sq_error / (mc_runs * min_size))

    return scores


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _seeded_noise_sample(seed_base: int, group_idx: int, run_idx: int, elem_idx: int, gaussian: bool) -> np.float64:
    s = (
        np.uint64(seed_base)
        + np.uint64(0x9E3779B97F4A7C15) * np.uint64(group_idx + 1)
        + np.uint64(0xBF58476D1CE4E5B9) * np.uint64(run_idx + 1)
        + np.uint64(0x94D049BB133111EB) * np.uint64(elem_idx + 1)
    )
    if not gaussian:
        x = s
        x ^= x >> np.uint64(12)
        x ^= x << np.uint64(25)
        x ^= x >> np.uint64(27)
        x = x * np.uint64(2685821657736338717)
        u = (x >> np.uint64(11)) * (1.0 / 9007199254740992.0)
        return 2.0 * u - 1.0

    acc = 0.0
    for k in range(12):
        x = s + np.uint64(0xD2B74407B1CE6E93) * np.uint64(k + 1)
        x ^= x >> np.uint64(12)
        x ^= x << np.uint64(25)
        x ^= x >> np.uint64(27)
        x = x * np.uint64(2685821657736338717)
        acc += (x >> np.uint64(11)) * (1.0 / 9007199254740992.0)
    z = (acc - 6.0) / 3.0
    if z < -1.0:
        return -1.0
    if z > 1.0:
        return 1.0
    return z


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def find_nucleation_adaptive_kernel(
    valid_candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    max_size: int,
    mc_runs: int,
    degradation_threshold: float,
    max_rmse_per_layer: float,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel for adaptive nucleation Search.

    Optimizes the triple loop (candidates x sizes x mc_runs).

    NOTE (Numba/runtime):

    Noise generation is in-kernel by design for performance and to avoid Python

    allocation overhead in inner loops. STRAT production calls enforce gaussian mode.

    """

    n_cand = len(valid_candidates)

    results_size = np.zeros(n_cand, dtype=np.int32)

    results_rmse = np.zeros(n_cand, dtype=np.float64)

    for i_cand in prange(n_cand):
        nH = nH_arr[i_cand]

        nL = nL_arr[i_cand]

        nSub = nSub_arr[i_cand]

        wl = valid_candidates[i_cand]

        prev_rmse_metric = 0.0

        last_valid_size = 0

        final_rmse = 0.0

        rmse_floor = 0.05

        for size in range(min_size, max_size + 1):
            cumulative_sq_error = 0.0

            for run_idx in range(mc_runs):
                # Configurable noise distribution (STRAT uses gaussian-only).

                noise_vec = np.zeros(size, dtype=np.float64)
                for i in range(size):
                    raw_i = _seeded_noise_sample(
                        seed_base=seed_base,
                        group_idx=i_cand + size,
                        run_idx=run_idx,
                        elem_idx=i,
                        gaussian=use_gaussian,
                    )
                    noise_vec[i] = raw_i * noise_pct

                current_stack = np.zeros(size, dtype=np.float64)

                for i in range(size):
                    th, _ = simulate_growth_kernel(
                        p_thick_nominal,
                        i,
                        current_stack[:i],
                        wl,
                        nH,
                        nL,
                        nSub,
                        offset_val,
                        noise_vec[i],
                        factor_val,
                        non_monotonic_mode,
                    )

                    current_stack[i] = th

                    cumulative_sq_error += (th - p_thick_nominal[i]) ** 2

            rmse_total = np.sqrt(cumulative_sq_error / (mc_runs * size))

            if rmse_total > max_rmse_per_layer:
                break

            if size > min_size:
                ratio = rmse_total / max(prev_rmse_metric, rmse_floor)

                if ratio > degradation_threshold:
                    break

            last_valid_size = size

            prev_rmse_metric = rmse_total

            final_rmse = rmse_total

        results_size[i_cand] = last_valid_size

        results_rmse[i_cand] = final_rmse

    return results_size, results_rmse


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def update_run_states_kernel(
    p_thick_nom_arr: np.ndarray,
    i_layer: int,
    prev_stacks: np.ndarray,  # (num_runs, i_layer)
    best_wl: float,
    nH,  # float or complex (Numba multi-dispatch)
    nL,  # float or complex
    nSub,  # float or complex
    offset_val: float,
    noise_values: np.ndarray,  # (num_runs,)
    factor_val: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
):
    """Parallel update of simulation states for next layer."""

    num_runs = prev_stacks.shape[0]

    updates = np.empty(num_runs, dtype=np.float64)

    for r in prange(num_runs):
        updates[r], _ = simulate_growth_kernel(
            p_thick_nom_arr,
            i_layer,
            prev_stacks[r],
            best_wl,
            nH,
            nL,
            nSub,
            offset_val,
            noise_values[r],
            factor_val,
            non_monotonic_mode,
        )

    return updates


# =============================================================================


# BACKSIDE CORRECTION VALIDITY (Opus 4.6)


# =============================================================================


# The incoherent backside formula T = Tf*Tb/(1-Rp*Rb) is an approximation


# (where Rp = R_prime = stack reflectance seen from substrate side)


# valid ONLY when all refractive clues are effectively real.


# Thresholds (from thin-film optics practice):


#   - Layer materials (H, L): |Im(n)| < K_MAX_LAYER_BACKSIDE  (absorption < 0.1%)


#   - substrate:              |Im(n)| < K_MAX_SUBSTRATE_BACKSIDE (absorption < 0.001%)


K_MAX_LAYER_BACKSIDE: float = 0.001


K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def validate_backside_real_clues(n_H_imag: float, n_L_imag: float, n_Sub_imag: float) -> tuple[bool, bool, bool]:
    """Validates that refractive clues are real enough for incoherent

    backside correction to be physically valid.

    Args:

        n_H_imag: |Im(n_H)| at a representative wavelength

        n_L_imag: |Im(n_L)| at a representative wavelength

        n_Sub_imag: |Im(n_Sub)| at a representative wavelength

    Returns:

        (H_ok, L_ok, Sub_ok) - True if index is real enough for backside approx."""

    H_ok = abs(n_H_imag) < K_MAX_LAYER_BACKSIDE

    L_ok = abs(n_L_imag) < K_MAX_LAYER_BACKSIDE

    Sub_ok = abs(n_Sub_imag) < K_MAX_SUBSTRATE_BACKSIDE

    return H_ok, L_ok, Sub_ok


# --- LOCKED --- Validated by test_tmm_inline.py (test 3) ───


# Macleod convention (+1j). Pre-multiply + Air->Sub. DO NOT MODIFY without running tests.


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_detailed_growth(
    num_layers,
    p_thick_nominal,
    layer_wavelengths,
    n_H_arr,
    n_L_arr,
    n_Sub_arr,
    steps_per_layer_arr,
):
    """

    Detailed growth simulation with exact physics.

    CRITICAL PHYSICS NOTE:

    This function computes T_total including INCOHERENT BACKSIDE reflection.

    T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

    Matches the "Real World" signal seen by the monitor.

    The expression is intentionally expanded inline (instead of routing through

    compute_RT_from_matrix) for step-wise growth performance. Keep formulas aligned.

    """

    if num_layers == 0:
        return np.zeros(1), np.zeros(1), np.zeros(1)

    total_steps = np.sum(steps_per_layer_arr)

    total_points = total_steps + num_layers + 1

    x_points = np.empty(total_points)

    y_points = np.empty(total_points)

    layer_boundaries = np.empty(num_layers + 1)

    current_idx = 0

    cumulative_thick = 0.0

    layer_boundaries[0] = 0.0

    # Dual matrix tracking:

    #   F = forward (Air->Sub, pre-multiply L @ F) -> for T extraction

    #   R = reverse (Sub->Air, post-multiply R @ L) -> for backside R extraction

    F00 = 1.0 + 0j

    F01 = 0.0 + 0j

    F10 = 0.0 + 0j

    F11 = 1.0 + 0j

    R00 = 1.0 + 0j

    R01 = 0.0 + 0j

    R10 = 0.0 + 0j

    R11 = 1.0 + 0j

    prev_wl = -1.0

    for i_layer in range(num_layers):
        target_th = p_thick_nominal[i_layer]

        current_wl = layer_wavelengths[i_layer]

        if current_wl < 0.1:
            current_wl = 1500.0

        n_l_target = n_H_arr[i_layer] if (i_layer % 2) == 0 else n_L_arr[i_layer]

        n_s = n_Sub_arr[i_layer]

        nsr = n_s.real

        # Incoherent backside (Air|Sub)

        R_ext = ((nsr - 1.0) / (nsr + 1.0)) ** 2

        T_ext = 1.0 - R_ext

        # Sync before starting layer (wavelength change -> rebuild both matrices)

        if i_layer > 0 and abs(current_wl - prev_wl) > 1e-3:
            F00 = 1.0 + 0j

            F01 = 0.0 + 0j

            F10 = 0.0 + 0j

            F11 = 1.0 + 0j

            R00 = 1.0 + 0j

            R01 = 0.0 + 0j

            R10 = 0.0 + 0j

            R11 = 1.0 + 0j

            k0 = TWO_PI / current_wl

            for j in range(i_layer):
                dj = p_thick_nominal[j]

                # [FIX 2026] Use n at CURRENT monitoring wl, not layer j's block wl

                nj = n_H_arr[i_layer] if (j % 2) == 0 else n_L_arr[i_layer]

                phi = k0 * nj * dj

                cp = np.cos(phi)

                isp = +1j * np.sin(phi)

                mj01 = isp / nj if abs(nj) > 1e-9 else 0.0j

                mj10 = isp * nj

                # Forward: F = L @ F (pre-multiply, Air->Sub)

                t00 = cp * F00 + mj01 * F10

                t01 = cp * F01 + mj01 * F11

                t10 = mj10 * F00 + cp * F10

                t11 = mj10 * F01 + cp * F11

                F00, F01, F10, F11 = t00, t01, t10, t11

                # Reverse: R = R @ L (post-multiply, Sub->Air)

                t00 = R00 * cp + R01 * mj10

                t01 = R00 * mj01 + R01 * cp

                t10 = R10 * cp + R11 * mj10

                t11 = R10 * mj01 + R11 * cp

                R00, R01, R10, R11 = t00, t01, t10, t11

        k0_curr = TWO_PI / current_wl

        # Calculate T_start:

        # - Tf from forward matrix F (Air->Sub)

        # - "Rf" here is legacy naming and corresponds to R_prime-like reverse reflectance

        #   extracted from reverse matrix R (Sub->Air) for incoherent backside denominator.

        denom_f = F00 + n_s * F01 + F10 + n_s * F11  # Air->Sub: B+C, n_inc=1

        denom_r = n_s * R00 + n_s * R01 + R10 + R11  # Sub->Air: n_sub*(M00+M01)+(M10+M11)

        if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
            Tf = (4.0 * nsr) / (denom_f.real**2 + denom_f.imag**2)

            num_r = n_s * R00 + n_s * R01 - R10 - R11

            Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)

            T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

        else:
            T_val = 0.0

        x_points[current_idx] = cumulative_thick

        y_points[current_idx] = T_val

        current_idx += 1

        steps = steps_per_layer_arr[i_layer]

        step_sz = target_th / steps

        for s in range(1, steps + 1):
            d_partial = step_sz * s

            phi = k0_curr * n_l_target * d_partial

            cp = np.cos(phi)

            isp = +1j * np.sin(phi)

            mj01 = isp / n_l_target if abs(n_l_target) > 1e-9 else 0.0j

            mj10 = isp * n_l_target

            # Forward total: ft = L @ F (pre-multiply, for T)

            ft00 = cp * F00 + mj01 * F10

            ft01 = cp * F01 + mj01 * F11

            ft10 = mj10 * F00 + cp * F10

            ft11 = mj10 * F01 + cp * F11

            # Reverse total: rt = R @ L (post-multiply, for R_backside)

            rt00 = R00 * cp + R01 * mj10

            rt01 = R00 * mj01 + R01 * cp

            rt10 = R10 * cp + R11 * mj10

            rt11 = R10 * mj01 + R11 * cp

            # T from forward (Air->Sub) + R from reverse (Sub->Air)

            denom_f = ft00 + n_s * ft01 + ft10 + n_s * ft11

            denom_r = n_s * rt00 + n_s * rt01 + rt10 + rt11

            if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
                Tf = (4.0 * nsr) / (denom_f.real**2 + denom_f.imag**2)

                num_r = n_s * rt00 + n_s * rt01 - rt10 - rt11

                Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)

                val = (Tf * T_ext) / (1.0 - Rf * R_ext)

            else:
                val = 0.0

            x_points[current_idx] = cumulative_thick + d_partial

            y_points[current_idx] = val

            current_idx += 1

        # Advance both matrices with full layer

        phi_full = k0_curr * n_l_target * target_th

        cp = np.cos(phi_full)

        isp = +1j * np.sin(phi_full)

        mf01 = isp / n_l_target if abs(n_l_target) > 1e-9 else 0.0j

        mf10 = isp * n_l_target

        # Forward: F = L_full @ F (pre-multiply)

        t00 = cp * F00 + mf01 * F10

        t01 = cp * F01 + mf01 * F11

        t10 = mf10 * F00 + cp * F10

        t11 = mf10 * F01 + cp * F11

        F00, F01, F10, F11 = t00, t01, t10, t11

        # Reverse: R = R @ L_full (post-multiply)

        t00 = R00 * cp + R01 * mf10

        t01 = R00 * mf01 + R01 * cp

        t10 = R10 * cp + R11 * mf10

        t11 = R10 * mf01 + R11 * cp

        R00, R01, R10, R11 = t00, t01, t10, t11

        cumulative_thick += target_th

        layer_boundaries[i_layer + 1] = cumulative_thick

        prev_wl = current_wl

    return x_points[:current_idx], y_points[:current_idx], layer_boundaries


# =============================================================================


# EXPORTS


# =============================================================================


# =============================================================================


# RESTORED UTILITIES


# =============================================================================


def init_thickness(n4_or_stack, l0: float, qw_or_mats) -> any:
    """Calculate physical thickness (Scalar or List)"""

    # 1. Scalar Mode (n4, l0, qw)

    if isinstance(n4_or_stack, (float, int)):
        n4 = float(n4_or_stack)

        qw = float(qw_or_mats)

        if abs(n4) < 1e-9:
            return 0.0

        return (qw * l0) / (4.0 * n4)

    # 2. Stack Mode (stack_list, l0, mats_dict)

    elif isinstance(n4_or_stack, list):
        stack = n4_or_stack

        mats = qw_or_mats

        ep = []

        for lay in stack:
            # Duck-type access to Layer object

            mat_key = getattr(lay, "mat", None)

            qw_val = getattr(lay, "qwot", 0.0)

            # Resolve n4

            n_val = 1.5

            if mat_key and hasattr(mats, "get"):
                m_obj = mats.get(mat_key)

                if hasattr(m_obj, "n4"):
                    n_val = m_obj.n4

                elif isinstance(m_obj, dict):
                    n_val = m_obj.get("n4", 1.5)

            if abs(n_val) < 1e-9:
                d = 0.0

            else:
                d = (qw_val * l0) / (4.0 * n_val)

            ep.append(d)

        return ep

    return 0.0


def calc_qwot(n4: float, l0: float, d: float) -> float:
    """Calculate QWOT from physical thickness"""

    if abs(l0) < 1e-9:
        return 0.0

    return (4.0 * n4 * d) / l0


def calc_rmse(Ts: np.ndarray, wls: np.ndarray, targets: list[Target]) -> tuple[float, float]:
    """Calculate RMSE against targets (spectral quadrature Delta ln lambda)."""

    from certus.utils.certus_index_utils import spectral_rmse_weights

    total_sse = 0.0

    total_weights = 0.0

    spec_w = spectral_rmse_weights(np.asarray(wls, dtype=np.float64))

    for t in targets:
        if not t.valid():
            continue

        mask = (wls >= t.lmin) & (wls <= t.lmax)

        if not np.any(mask):
            continue

        segment_T = Ts[mask]

        sw = spec_w[mask]

        target_val = (t.tmin + t.tmax) / 2.0

        sse = np.sum(sw * (segment_T - target_val) ** 2) * t.w

        total_sse += sse

        total_weights += np.sum(sw) * t.w

    if total_weights < 1e-12:
        return 0.0, 0.0

    mse = total_sse / total_weights

    return np.sqrt(mse), mse


# =============================================================================


# JIT WARMUP (Performance Optimization)


# =============================================================================


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_phase2_derivatives_kernel(
    wl_um_array: np.ndarray, p: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Computes analytical gradients for Sellmeier and empirical k law w.r.t parameters."""

    n_pts = len(wl_um_array)

    n_arr = np.empty(n_pts, dtype=np.float64)

    k_arr = np.empty(n_pts, dtype=np.float64)

    dn_dp = np.zeros((5, n_pts), dtype=np.float64)

    dk_dp = np.zeros((8, n_pts), dtype=np.float64)

    A, B1, L1, B2, L2 = p[0], p[1], p[2], p[3], p[4]

    _lo, _hi = -25.0, 5.0

    _mid = 0.5 * (_lo + _hi)

    _scale = 2.0

    half_diff = 0.5 * (_hi - _lo)

    amp, center, width, exponent = p[9], p[10], p[11], p[12]

    w_safe = max(width, 1e-9)

    beta = max(min(exponent, 8.0), 1.0)

    for i in prange(n_pts):
        wl = wl_um_array[i]

        wl_sq = wl * wl

        denom1 = wl_sq - L1 * L1
        if abs(denom1) < 1e-15:
            denom1 = 1e-15 if denom1 >= 0 else -1e-15

        denom2 = wl_sq - L2 * L2
        if abs(denom2) < 1e-15:
            denom2 = 1e-15 if denom2 >= 0 else -1e-15

        term1 = (B1 * wl_sq) / denom1

        term2 = (B2 * wl_sq) / denom2

        n_sq = A + term1 + term2

        n_val = np.sqrt(max(n_sq, 1e-6))

        n_arr[i] = n_val

        inv_2n = 0.5 / n_val if n_sq > 1e-6 else 0.0

        dn_dp[0, i] = inv_2n * 1.0

        dn_dp[1, i] = inv_2n * (wl_sq / denom1)

        dn_dp[2, i] = inv_2n * (term1 * 2.0 * L1 / denom1)

        dn_dp[3, i] = inv_2n * (wl_sq / denom2)

        dn_dp[4, i] = inv_2n * (term2 * 2.0 * L2 / denom2)

        x1 = p[5] * wl + p[6]

        x2 = p[7] * wl + p[8]

        y1 = (x1 - _mid) / _scale

        y2 = (x2 - _mid) / _scale

        t1 = np.tanh(y1)

        t2 = np.tanh(y2)

        e1_arg = _mid + half_diff * t1

        e2_arg = _mid + half_diff * t2

        base1 = np.exp(e1_arg)

        base2 = np.exp(e2_arg)

        arg = abs((wl - center) / w_safe)

        arg_beta = arg**beta

        gauss = amp * np.exp(-arg_beta)

        k_val = 1e-6 + base1 + base2 + gauss

        k_arr[i] = k_val

        d_e1_dx1 = half_diff * (1.0 - t1 * t1) / _scale

        dk_dp[0, i] = base1 * d_e1_dx1 * wl

        dk_dp[1, i] = base1 * d_e1_dx1 * 1.0

        d_e2_dx2 = half_diff * (1.0 - t2 * t2) / _scale

        dk_dp[2, i] = base2 * d_e2_dx2 * wl

        dk_dp[3, i] = base2 * d_e2_dx2 * 1.0

        dk_dp[4, i] = np.exp(-arg_beta)

        if arg > 0:
            sgn = -1.0 if wl > center else 1.0

            if wl == center:
                sgn = 0.0

            d_arg_dc = sgn / w_safe

            dk_dp[5, i] = -gauss * beta * (arg ** (beta - 1.0)) * d_arg_dc

            d_arg_dw = -arg / w_safe

            dk_dp[6, i] = -gauss * beta * (arg ** (beta - 1.0)) * d_arg_dw

            if arg > 1e-12:
                dk_dp[7, i] = -gauss * arg_beta * np.log(arg)

            else:
                dk_dp[7, i] = 0.0

        else:
            dk_dp[5, i] = 0.0

            dk_dp[6, i] = 0.0

            dk_dp[7, i] = 0.0

    return n_arr, k_arr, dn_dp, dk_dp


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def _compute_ir_global_cost_gradient_kernel(
    wls: np.ndarray,
    n_arr: np.ndarray,
    k_arr: np.ndarray,
    d: float,
    n_sub: np.ndarray,
    target_T: np.ndarray,
    target_R: np.ndarray,
    weights: np.ndarray,
    use_T: bool,
    use_R: bool,
    dn_dp: np.ndarray,
    dk_dp: np.ndarray,
    T_substrate: np.ndarray,
    use_normalized: bool,
    weight_T: float,
    weight_R: float,
    is_frosted_glass: bool,
    has_absorbing_substrate: bool,
    k_sub_full: np.ndarray,
    D_sub_nm: float,
    compute_thickness_gradient: bool = False,
) -> np.ndarray:
    """Gradient of IR global cost w.r.t. parameters.
    Returns:
        If compute_thickness_gradient is False: size (dn_dp.shape[0] + dk_dp.shape[0])
        If compute_thickness_gradient is True: size (1 + dn_dp.shape[0] + dk_dp.shape[0]), where [0] is dMSE/d(thickness)
    """

    n_pts = len(wls)
    n_valid_T = 1
    n_valid_R = 1
    count_T = 0
    count_R = 0

    for i in range(n_pts):
        if weights[i] > 1e-12:
            if use_T:
                count_T += 1
            if use_R:
                count_R += 1

    if count_T > 0:
        n_valid_T = count_T
    if count_R > 0:
        n_valid_R = count_R

    n_n = dn_dp.shape[0]
    n_k = dk_dp.shape[0]
    n_total = n_n + n_k
    offset = 0
    if compute_thickness_gradient:
        n_total += 1
        offset = 1

    grad_per_wl = np.zeros((n_pts, n_total), dtype=np.float64)

    DELTA = 1e-7

    for i in prange(n_pts):
        wl = wls[i]
        w = weights[i]

        if w < 1e-12:
            continue

        nr = n_arr[i]
        ni = k_arr[i]
        ns = n_sub[i]

        dTdn, dTdk, dRdn, dRdk = 0.0, 0.0, 0.0, 0.0
        dTdd, dRdd = 0.0, 0.0

        if is_frosted_glass:
            ns_cmplx = ns + 0j
            val_R = calculate_reflection_infinite_substrate_single(wl, nr, ni, d, ns_cmplx)
            val_T = np.nan

            vR_up_n = calculate_reflection_infinite_substrate_single(wl, nr + DELTA, ni, d, ns_cmplx)
            vR_dn_n = calculate_reflection_infinite_substrate_single(wl, nr - DELTA, ni, d, ns_cmplx)
            dRdn = (vR_up_n - vR_dn_n) / (2.0 * DELTA)

            vR_up_k = calculate_reflection_infinite_substrate_single(wl, nr, ni + DELTA, d, ns_cmplx)
            if ni < DELTA:
                dRdk = (vR_up_k - val_R) / DELTA
            else:
                vR_dn_k = calculate_reflection_infinite_substrate_single(wl, nr, ni - DELTA, d, ns_cmplx)
                dRdk = (vR_up_k - vR_dn_k) / (2.0 * DELTA)

            if compute_thickness_gradient:
                vR_up_d = calculate_reflection_infinite_substrate_single(wl, nr, ni, d + DELTA, ns_cmplx)
                vR_dn_d = calculate_reflection_infinite_substrate_single(wl, nr, ni, d - DELTA, ns_cmplx)
                dRdd = (vR_up_d - vR_dn_d) / (2.0 * DELTA)

        elif has_absorbing_substrate:
            ks = k_sub_full[i]
            val_R, val_T = _calculate_RT_absorbing_sub_single(wl, nr, ni, d, ns, ks, D_sub_nm)

            vR_up_n, vT_up_n = _calculate_RT_absorbing_sub_single(wl, nr + DELTA, ni, d, ns, ks, D_sub_nm)
            vR_dn_n, vT_dn_n = _calculate_RT_absorbing_sub_single(wl, nr - DELTA, ni, d, ns, ks, D_sub_nm)
            dRdn = (vR_up_n - vR_dn_n) / (2.0 * DELTA)
            dTdn = (vT_up_n - vT_dn_n) / (2.0 * DELTA)

            vR_up_k, vT_up_k = _calculate_RT_absorbing_sub_single(wl, nr, ni + DELTA, d, ns, ks, D_sub_nm)
            if ni < DELTA:
                dRdk = (vR_up_k - val_R) / DELTA
                dTdk = (vT_up_k - val_T) / DELTA
            else:
                vR_dn_k, vT_dn_k = _calculate_RT_absorbing_sub_single(wl, nr, ni - DELTA, d, ns, ks, D_sub_nm)
                dRdk = (vR_up_k - vR_dn_k) / (2.0 * DELTA)
                dTdk = (vT_up_k - vT_dn_k) / (2.0 * DELTA)

            if compute_thickness_gradient:
                vR_up_d, vT_up_d = _calculate_RT_absorbing_sub_single(wl, nr, ni, d + DELTA, ns, ks, D_sub_nm)
                vR_dn_d, vT_dn_d = _calculate_RT_absorbing_sub_single(wl, nr, ni, d - DELTA, ns, ks, D_sub_nm)
                dRdd = (vR_up_d - vR_dn_d) / (2.0 * DELTA)
                dTdd = (vT_up_d - vT_dn_d) / (2.0 * DELTA)

        else:
            ns_cmplx = ns + 0j
            val_R, val_T = calculate_transmission_single(wl, nr, ni, d, ns_cmplx)

            dTdn_corr, dTdk_corr, dRdn_corr, dRdk_corr, dTdd_corr, dRdd_corr = _compute_single_layer_sensitivity_kernel(
                wl, nr, ni, d, ns
            )
            dTdn = dTdn_corr
            dTdk = dTdk_corr
            dRdn = dRdn_corr
            dRdk = dRdk_corr
            dTdd = dTdd_corr
            dRdd = dRdd_corr

        fac_T = 0.0
        fac_R = 0.0

        if use_T:
            if use_normalized:
                scale_T = 1.0 / max(T_substrate[i], 1e-6)
                diff_T = (val_T * scale_T) - target_T[i]
            else:
                scale_T = 1.0
                diff_T = val_T - target_T[i]
            fac_T = (2.0 * w * diff_T * weight_T / n_valid_T) * scale_T

        if use_R:
            if use_normalized:
                if T_substrate[i] >= 0.05:
                    scale_R = 1.0 / T_substrate[i]
                else:
                    scale_R = 0.0
                diff_R = (val_R * scale_R) - target_R[i]
            else:
                scale_R = 1.0
                diff_R = val_R - target_R[i]
            fac_R = (2.0 * w * diff_R * weight_R / n_valid_R) * scale_R

        if compute_thickness_gradient:
            grad_per_wl[i, 0] = (fac_T * dTdd + fac_R * dRdd) if (use_T or use_R) else 0.0

        for p in range(n_n):
            dnp = dn_dp[p, i]
            term = 0.0
            if use_T:
                term += fac_T * dTdn * dnp
            if use_R:
                term += fac_R * dRdn * dnp
            grad_per_wl[i, offset + p] = term

        for p in range(n_k):
            dkp = dk_dp[p, i]
            term = 0.0
            if use_T:
                term += fac_T * dTdk * dkp
            if use_R:
                term += fac_R * dRdk * dkp
            grad_per_wl[i, offset + n_n + p] = term

    grad = np.zeros(n_total, dtype=np.float64)
    for p in range(n_total):
        s = 0.0
        for i in range(n_pts):
            s += grad_per_wl[i, p]
        grad[p] = s

    return grad


def warmup_physics(silent: bool = True) -> None:
    """

    Pre-compiles critical Numba kernels to eliminate first-call JIT latency.

    Call once at application startup for optimal user experience.

    Args:

        silent: If True, suppresses any logging/output during warmup.

    """

    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Minimal test arrays (10 points, single layer)

        wls = np.linspace(400.0, 800.0, 10, dtype=np.float64)

        n_complex = np.ones((10, 1), dtype=np.complex128) * (1.5 + 0.001j)

        n_sub = np.ones(10, dtype=np.complex128) * 1.52

        thicknesses = np.array([100.0], dtype=np.float64)

        # Warm TMM core

        try:
            calculate_RT_vectorized_real(thicknesses, n_complex, n_sub, wls)

        except (RuntimeError, ValueError):
            pass

        # Warm single-layer T/R and fused R+T (INDEX hot path)

        try:
            n_real = np.full(10, 1.5, dtype=np.float64)

            k_real = np.full(10, 0.001, dtype=np.float64)

            n_sub_real = np.full(10, 1.52, dtype=np.float64)



            calculate_RT_single_layer_backside_array(wls, n_real, k_real, 100.0, n_sub_real)

        except (RuntimeError, ValueError):
            pass

        # Warm TLU epsilon

        try:
            E_arr = HC_EV_NM / wls

            epsilon2_TLU_array(E_arr, 3.5, 200.0, 4.5, 1.5, 0.05)

            epsilon1_TL_analytic(E_arr, 3.5, 200.0, 4.5, 1.5, 2.0)

        except (RuntimeError, ValueError):
            pass

        # Warm Cauchy

        try:
            get_nk_cauchy(2.35, 2.29, wls)

        except (RuntimeError, ValueError):
            pass

        # Warm MSE

        try:
            target = np.full(10, 0.9, dtype=np.float64)

            weights = np.ones(10, dtype=np.float64)

            compute_mse_vectorized(n_real, target, weights)

        except (RuntimeError, ValueError):
            pass

        # Warm colorimetry JIT kernels

        try:
            _lab_f(0.5)

            _lab_f_inv(0.5)

            _gamma_correct_scalar(0.5)

            R_test = np.full(10, 0.5, dtype=np.float64)

            R_interp = np.interp(CIE_LAMBDA, wls, R_test)

            _xyz_from_spectrum_kernel(R_interp, D65_CIE_X, D65_CIE_Y, D65_CIE_Z, K_COLOR)

            lab1 = np.array([50.0, 25.0, 10.0])

            lab2 = np.array([55.0, 20.0, 15.0])

            delta_e_2000(lab1, lab2)

        except (RuntimeError, ValueError):
            pass

    if not silent:
        logging.getLogger("CERTUS").debug("Physics JIT warmup complete")
