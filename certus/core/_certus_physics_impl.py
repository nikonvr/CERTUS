SMALL_EPSILON = 1e-12
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
    "get_nk_cauchy_simple",
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


except ImportError, ModuleNotFoundError:
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
                base.parents[1] / "certus_physics" / "structures.py"
                if len(base.parents) > 1
                else base / "certus_physics" / "structures.py",
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

_SUBSTRATE_CACHE = {}

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

    wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    try:
        wl_hash = hash(wavelengths_nm.tobytes())
    except Exception:
        wl_hash = id(wavelengths_nm)

    cache_key = (substrate_id, wl_hash)
    if cache_key in _SUBSTRATE_CACHE:
        return _SUBSTRATE_CACHE[cache_key]

    coeffs = SELLMEIER_COEFFS_BY_ID[substrate_id]
    min_lambda = SUBSTRATE_MIN_LAMBDA.get(substrate_id, 200.0)

    res = get_n_substrate_array_by_id_kernel(wavelengths_nm, *coeffs, min_lambda)

    if len(_SUBSTRATE_CACHE) > 1024:
        _SUBSTRATE_CACHE.clear()
    _SUBSTRATE_CACHE[cache_key] = res

    return res


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def get_n_frosted_glass_array(wavelengths_nm: np.ndarray) -> np.ndarray:
    """Calculate frosted glass refractive index for an array of wavelengths."""
    n = len(wavelengths_nm)
    result = np.empty(n, dtype=wavelengths_nm.dtype)
    for i in prange(n):
        result[i] = FROSTED_GLASS_CAUCHY_A + FROSTED_GLASS_CAUCHY_B / (wavelengths_nm[i] * wavelengths_nm[i])
    return result


# =========================================================================================

from certus.physics.certus_optical_models import (
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_nk_cauchy,
    get_nk_cauchy_wrapper,
    get_nk_cauchy_simple,
    sellmeier_n_array,
)


from certus.physics.certus_colorimetry import lab_to_rgb, xyz_from_spectrum, xyz_to_lab

from certus.physics.certus_colorimetry import (
    CIE_LAMBDA, D65_CIE_X, D65_CIE_Y, D65_CIE_Z, K_COLOR,
    _lab_f, _lab_f_inv, _gamma_correct_scalar, _xyz_from_spectrum_kernel,
    delta_e_2000
)

from certus.physics.certus_tmm_core import (
    apply_exact_backside_combination,
    calc_spectrum_front,
    calc_spectrum_full,
    calc_spectrum_full_exact,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    calculate_RT_single_layer_backside_array,
    calculate_RT_vectorized_real,
    calculate_RT_vectorized_real_HL,
    calculate_bare_substrate_RT,
    calculate_single_interface_R,
    calculate_transmission_single,
    oblique_front_char_matrix_single,
    oblique_front_rt_from_char_matrix_nsub_real,
)

from certus.physics.certus_tmm_core import (
    _apply_exact_backside_generic,
    _calc_spectrum_oblique_parallel,
    _oblique_stack_rt_single,
    _calculate_RT_HL_core,
)
from certus.physics.certus_tmm_core import _calculate_RT_absorbing_sub_single
from certus.physics.certus_opt_tmm import Material
from certus.physics.certus_opt_kernels import (
    MaterialDatabase,
    PGlobalOptimizer,
    SingleLinkageClusterer,
    arange_inclusive,
    calculate_RTRback_incoherent_vectorized,
    calculate_reflection_infinite_substrate_single,
    clip_to_bounds,
    compute_TMM_generic,
    compute_gradient_all_layers_analytic,
    compute_mse_vectorized,
    compute_oblique_gradient_contrib_analytic,
    compute_oblique_rt_and_grads_analytic,
    cost_numba_fast,
    make_cost_function,
    prepare_targets_vectorized,
    trim_worst_only,
    calculate_reflectance_bilayer_vectorized,
    compute_metal_bilayer_gradient_analytic,
)

from certus.physics.certus_opt_kernels import (
    _compute_epsilon2_gradient_kernel,
    _compute_epsilon1_gradient_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_single_layer_sensitivity_array,
    _compute_index_cost_gradient_kernel,
    _compute_gradient_analytic_kernel,
    _compute_oblique_gradient_contrib_kernel,
    _compute_oblique_rt_and_grads_kernel,
    _compute_metal_tmm_gradient_kernel,
)
from certus.physics.certus_opt_kernels import _compute_single_layer_sensitivity_kernel

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
        except TypeError, ValueError:
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

        except KeyError, ValueError, AttributeError:
            pass

    try:
        return float(material_id)

    except ValueError, TypeError:
        try:
            return complex(material_id)
        except ValueError, TypeError:
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

        except KeyError, ValueError, AttributeError:
            pass  # Fallback

    # Simple Parse for constants "1.45" passed as string

    try:
        val = float(material_id)

        return np.full(n, val, dtype=np.float64)

    except ValueError, TypeError:
        # Fallback to default if conversion fails

        pass

    return np.full(n, 1.5, dtype=np.float64)


# Note: calculate_RT_vectorized_real_HL is defined earlier (line ~950) with backside support


# =============================================================================


# =========================================================================================

from certus.physics.certus_strat_kernels import (
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    calculate_detailed_growth,
    check_extrema_proximity,
    compute_T_front_at_layer,
    compute_batch_rmse,
    compute_dynamics_kernel,
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    validate_backside_real_clues,
    validate_wavelengths_batch,
)

from certus.physics.certus_strat_kernels import (
    _compute_valid_blocks_kernel,
    _dp_kernel,
    _solve_quadratic_target,
    _calculate_RT_HL_single_point,
    _seeded_noise_sample,
)


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

        except RuntimeError, ValueError:
            pass

        # Warm single-layer T/R and fused R+T (INDEX hot path)

        try:
            n_real = np.full(10, 1.5, dtype=np.float64)

            k_real = np.full(10, 0.001, dtype=np.float64)

            n_sub_real = np.full(10, 1.52, dtype=np.float64)

            calculate_RT_single_layer_backside_array(wls, n_real, k_real, 100.0, n_sub_real)

        except RuntimeError, ValueError:
            pass

        # Warm TLU epsilon

        try:
            E_arr = HC_EV_NM / wls

            epsilon2_TLU_array(E_arr, 3.5, 200.0, 4.5, 1.5, 0.05)

            epsilon1_TL_analytic(E_arr, 3.5, 200.0, 4.5, 1.5, 2.0)

        except RuntimeError, ValueError:
            pass

        # Warm Cauchy

        try:
            get_nk_cauchy(2.35, 2.29, wls)

        except RuntimeError, ValueError:
            pass

        # Warm MSE

        try:
            target = np.full(10, 0.9, dtype=np.float64)

            weights = np.ones(10, dtype=np.float64)

            compute_mse_vectorized(n_real, target, weights)

        except RuntimeError, ValueError:
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

        except RuntimeError, ValueError:
            pass

    if not silent:
        logging.getLogger("CERTUS").debug("Physics JIT warmup complete")


# --- AUTO-PATCHED IMPORTS ---
from certus.physics.certus_optical_models import (SplineBasisCache, get_nk_from_spline)
from certus.physics.certus_optimizers import (compute_critical_distance, fast_clustering_kernel)
from certus.physics.certus_opt_needle import (needle_scan_cached)
from certus.physics.certus_strat_batch import (precompute_matrix_cache_kernel, calculate_RT_batch_kernel)
from certus.physics.certus_strat_growth import (prepare_dynamics_data_kernel, update_run_states_kernel)
from certus.physics.certus_strat_math import (calculate_extrema_distances, check_extrema_proximity_batch)
from certus.physics.certus_strat_nucleation import (rank_nucleation_candidates_kernel, find_nucleation_adaptive_kernel)
from certus.physics.certus_tmm_substrate import (calculate_bare_substrate_R, calculate_bare_substrate_R_absorbing, calculate_bare_substrate_T_absorbing)
from certus.physics.certus_tmm_single_layer import (calculate_reflection_array, batch_single_layer_T_mse, batch_single_layer_RT_mse, calculate_RT_single_layer_absorbing_substrate_array)
from certus.physics.certus_tmm_matrix import (calc_spectrum_front_wrapper, calc_spectrum_full_wrapper, calc_spectrum_full_exact_wrapper)
from certus.physics.certus_opt_gradients import compute_oblique_backside_bundle_analytic

__all__.extend([
    'SplineBasisCache',
    'get_nk_from_spline',
    'compute_critical_distance',
    'fast_clustering_kernel',
    'compute_oblique_backside_bundle_analytic',
    'needle_scan_cached',
    'precompute_matrix_cache_kernel',
    'calculate_RT_batch_kernel',
    'prepare_dynamics_data_kernel',
    'update_run_states_kernel',
    'calculate_extrema_distances',
    'check_extrema_proximity_batch',
    'rank_nucleation_candidates_kernel',
    'find_nucleation_adaptive_kernel',
    'calculate_bare_substrate_R',
    'calculate_reflection_array',
    'batch_single_layer_T_mse',
    'batch_single_layer_RT_mse',
    'calculate_RT_single_layer_absorbing_substrate_array',
    'calculate_bare_substrate_R_absorbing',
    'calculate_bare_substrate_T_absorbing',
    'calc_spectrum_front_wrapper',
    'calc_spectrum_full_wrapper',
    'calc_spectrum_full_exact_wrapper'
])

from certus.physics.certus_tmm_matrix import (
    compute_TMM_single_point_k0_exact,
    compute_complex_phase_components,
    compute_TMM_single_point_k0,
    calculate_RT_with_backside_fused,
    calculate_RT_vectorized_real,
    calculate_RT_no_backside,
    calc_spectrum_front,
    calc_spectrum_full,
    calc_spectrum_full_exact
)
from certus.physics.certus_tmm_single_layer import (
    calculate_RT_single_layer_single,
    calculate_reflection_single,
    calculate_transmission_single,
    calculate_transmission_array
)
from certus.physics.certus_tmm_backside import (
    _apply_exact_backside_generic,
    apply_exact_backside_combination
)
from certus.physics.certus_opt_tmm import compute_RT_from_matrix

__all__.extend([
    'compute_RT_from_matrix',
    'compute_TMM_single_point_k0_exact',
    'calculate_RT_single_layer_single',
    'compute_complex_phase_components',
    'compute_TMM_single_point_k0',
    'calculate_reflection_single',
    'calculate_transmission_single',
    'calculate_RT_with_backside_fused',
    'calculate_RT_vectorized_real',
    'calculate_RT_no_backside',
    'calc_spectrum_front',
    'calc_spectrum_full',
    'calc_spectrum_full_exact',
    '_apply_exact_backside_generic',
    'apply_exact_backside_combination',
    'calculate_transmission_array'
])
