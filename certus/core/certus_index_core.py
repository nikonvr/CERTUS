from certus.core.certus_index_solvers import SubsetOptimTask
from pathlib import Path
from certus.core.certus_core import create_module_environment
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import scipy
import scipy.optimize

_env = create_module_environment(__file__, 'CERTUS_INDEX_CORE')
script_dir = _env['script_dir']

from numba import njit, prange
import logging
import numpy as np
import pandas as pd
from enum import Enum, auto
from typing import Any
from scipy.interpolate import CubicSpline

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    HC_EV_NM,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    OH_BAND_MAX,
    OH_BAND_MIN,
    PI,
    SMALL_EPSILON,
    T_SUB_MIN_R_NORM,
    T_SUB_MIN_T_NORM,
    SUBSTRATE_LIST,
    SUBSTRATES,
    SELLMEIER_COEFFS_BY_ID,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
    substrate_sellmeier_id,
    __version__,
    get_resource_path,
    get_safe_worker_count,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
)
from certus_physics import (
    PGlobalConfig,
    Sample,
    SingleLinkageClusterer,
    TLUParameters,
    _compute_index_cost_gradient_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_phase2_derivatives_kernel,
    _compute_ir_global_cost_gradient_kernel,
    calculate_single_interface_R,
    calculate_reflection_array,
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    calculate_transmission_single,
    clip_to_bounds,
    compute_mse_vectorized,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_n_frosted_glass_array,
    get_n_substrate_array_by_id,
    SplineBasisCache,
)
from certus.utils.certus_index_utils import (
    spectral_rmse_weights,
    sellmeier_2poles_eval_nj,
    sellmeier_2poles_eval,
    k_law_8p_eval,
    _deduce_knots_from_k8p,
    _ensure_strictly_increasing,
    _merge_closest_knot_pair,
    _sellmeier_residuals,
    fit_sellmeier_global,
    fit_k_global_8p,
    DataType,
    _detect_data_type_from_array,
    _detect_type_from_column_name,
    detect_data_type,
    analyze_loaded_data,
    normalize_index_config,
    calculate_index_rmse,
)

# Inner margin relative to the limits used in epsilon_to_nk (certus_core):
# avoids trajectories stuck exactly on the hard cut while keeping the full physical space
# (dielectrics through strongly absorbing high-index or light metalloid within the model box).
TLU_SOFT_EDGE_MARGIN = 0.05

# "Clear slab" prior (normalized T, BOTH): pushes away solutions where eps' is clamped to 1.0 in the
# TL model -> n~1 "air" with artificially low RMSE. Aligned with the current dielectric range (>=1.5).
TLU_PRIOR_TRANSPARENT_N_MIN_SOFT = 1.50

from .certus_index_config import (
    OptimizationConfig,
    OptimizationResults,
    substrateMode,
)

# ---------------------------------------------------------


# Install exception handler




@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _point_cost_kernel(
    n_val: float,
    k_val: float,
    wl: float,
    target_T: float,
    target_R: float,
    weight_T: float,
    weight_R: float,
    n_sub: float,
    T_sub: float,
    d: float,
    use_T: bool,
    use_R: bool,
    use_normalized: bool,
    is_frosted_glass: bool,
) -> float:
    """Compute normalized pointwise cost for one (n, k) candidate."""
    c_val = 0.0
    w_sum = 0.0

    if is_frosted_glass:
        Rc, _ = calculate_transmission_single(wl, n_val, k_val, d, n_sub + 0j)
        if use_R and not np.isnan(Rc) and not np.isnan(target_R):
            diff_r = Rc - target_R
            c_val += (diff_r * diff_r) * weight_R
            w_sum += weight_R
    else:
        Rc, Tc = calculate_transmission_single(wl, n_val, k_val, d, n_sub + 0j)
        if use_T:
            val_t = Tc
            if use_normalized:
                if T_sub > T_SUB_MIN_T_NORM:
                    val_t = val_t / T_sub
                else:
                    val_t = np.nan
            if not np.isnan(val_t) and not np.isnan(target_T):
                diff_t = val_t - target_T
                c_val += (diff_t * diff_t) * weight_T
                w_sum += weight_T
        if use_R:
            val_r = Rc
            if use_normalized:
                if T_sub > T_SUB_MIN_R_NORM:
                    val_r = val_r / T_sub
                else:
                    val_r = np.nan
            if not np.isnan(val_r) and not np.isnan(target_R):
                diff_r = val_r - target_R
                c_val += (diff_r * diff_r) * weight_R
                w_sum += weight_R

    if w_sum > SMALL_EPSILON:
        return c_val / w_sum
    return 1e12

@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _optimize_point_kernel(
    n_start: float,
    k_start: float,
    wl: float,
    target_T: float,
    target_R: float,
    weight_T: float,
    weight_R: float,
    n_sub: float,
    T_sub: float,
    R_sub: float,
    d: float,
    use_T: bool,
    use_R: bool,
    use_normalized: bool,
    is_frosted_glass: bool,
) -> tuple[float, float, float]:
    """Coordinate descent for one wavelength point (n, k) within ±2% bounds."""
    delta_n = n_start * 0.02
    delta_k = max(k_start * 0.02, 0.0002)
    n_min = max(0.01, n_start - delta_n)
    n_max = n_start + delta_n
    k_min = max(0.0, k_start - delta_k)
    k_max = k_start + delta_k

    current_n = n_start
    current_k = k_start
    best_cost = _point_cost_kernel(
        current_n,
        current_k,
        wl,
        target_T,
        target_R,
        weight_T,
        weight_R,
        n_sub,
        T_sub,
        d,
        use_T,
        use_R,
        use_normalized,
        is_frosted_glass,
    )

    coarse_step = delta_n * 0.5
    steps = np.array([coarse_step, 0.01, 0.005, 0.001, 0.0001], dtype=np.float64)

    for step in steps:
        improved_n = True
        while improved_n:
            improved_n = False
            next_n = current_n + step
            if next_n <= n_max:
                c = _point_cost_kernel(
                    next_n,
                    current_k,
                    wl,
                    target_T,
                    target_R,
                    weight_T,
                    weight_R,
                    n_sub,
                    T_sub,
                    d,
                    use_T,
                    use_R,
                    use_normalized,
                    is_frosted_glass,
                )
                if c < best_cost:
                    best_cost = c
                    current_n = next_n
                    improved_n = True
                    continue
            next_n = current_n - step
            if next_n >= n_min:
                c = _point_cost_kernel(
                    next_n,
                    current_k,
                    wl,
                    target_T,
                    target_R,
                    weight_T,
                    weight_R,
                    n_sub,
                    T_sub,
                    d,
                    use_T,
                    use_R,
                    use_normalized,
                    is_frosted_glass,
                )
                if c < best_cost:
                    best_cost = c
                    current_n = next_n
                    improved_n = True
                    continue

        improved_k = True
        while improved_k:
            improved_k = False
            next_k = current_k + step
            if next_k <= k_max:
                c = _point_cost_kernel(
                    current_n,
                    next_k,
                    wl,
                    target_T,
                    target_R,
                    weight_T,
                    weight_R,
                    n_sub,
                    T_sub,
                    d,
                    use_T,
                    use_R,
                    use_normalized,
                    is_frosted_glass,
                )
                if c < best_cost:
                    best_cost = c
                    current_k = next_k
                    improved_k = True
                    continue
            next_k = current_k - step
            if next_k >= k_min:
                c = _point_cost_kernel(
                    current_n,
                    next_k,
                    wl,
                    target_T,
                    target_R,
                    weight_T,
                    weight_R,
                    n_sub,
                    T_sub,
                    d,
                    use_T,
                    use_R,
                    use_normalized,
                    is_frosted_glass,
                )
                if c < best_cost:
                    best_cost = c
                    current_k = next_k
                    improved_k = True
                    continue

    return current_n, current_k, best_cost

@njit(cache=True, fastmath=True, nogil=True, parallel=True, error_model="numpy")
def _optimize_all_points_batch(
    n_start_arr,
    k_start_arr,
    wl_arr,
    T_targets,
    R_targets,
    weight_T,
    weight_R,
    n_sub_arr,
    T_sub_arr,
    R_sub_arr,
    d,
    use_T,
    use_R,
    use_normalized,
    is_frosted_glass,
    excluded_mask,
) -> tuple:
    """

    Batch-parallel per-lambda optimization using prange.

    Processes ALL wavelengths simultaneously on all CPU cores.

    Returns (n_final, k_final) arrays.

    """

    n_pts = len(wl_arr)

    n_final = np.empty(n_pts, dtype=np.float64)

    k_final = np.empty(n_pts, dtype=np.float64)

    for i in prange(n_pts):
        if excluded_mask[i]:
            n_final[i] = n_start_arr[i]

            k_final[i] = k_start_arr[i]

        else:
            ns_val = n_sub_arr[i].real

            ts_val = T_sub_arr[i] if not np.isnan(T_sub_arr[i]) else 1.0

            rs_val = R_sub_arr[i] if not np.isnan(R_sub_arr[i]) else 0.0

            nf, kf, _ = _optimize_point_kernel(
                n_start_arr[i],
                k_start_arr[i],
                wl_arr[i],
                T_targets[i],
                R_targets[i],
                weight_T,
                weight_R,
                ns_val,
                ts_val,
                rs_val,
                d,
                use_T,
                use_R,
                use_normalized,
                is_frosted_glass,
            )

            n_final[i] = nf

            k_final[i] = kf

    return n_final, k_final

def estimate_initial_params(
    wavelengths: np.ndarray, target_T: np.ndarray | None, n_substrate: np.ndarray
) -> np.ndarray:
    """

    Smart initialization of TLU parameters based on transmission spectrum analysis.

    Calibrated for a realistic dielectric start (n≈2, low k): ε∞≈4, Eg takes

    into account the max energy hν of the spectral window so that ε2 remains moderate

    across the entire range (cf. Urbach / TLU).

    """

    wls_a = np.asarray(wavelengths, dtype=np.float64)

    if wls_a.size == 0:
        return np.array([300.0, 5.5, 90.0, 7.0, 1.0, 0.35, 4.0], dtype=np.float64)

    min_wl = float(np.max([np.min(wls_a), 1.0]))

    E_max_scan = float(HC_EV_NM / min_wl)

    # Pure IR window: E_max_scan can be ~1 eV; without a floor, Eg drops ~1-2 eV and the TLU
    # produces non-physical dispersion (absurd n/k). Typical oxides SiO2/Al2O3: Eg >> hv(IR).

    EG_PHYS_MIN = 3.25

    d_init = 300.0

    eps_init = 4.0

    A_init = 90.0

    C_init = 1.0

    Eu_init = 0.22

    Eg_init = float(np.clip(max(E_max_scan + 0.45, EG_PHYS_MIN), 0.5, 9.5))

    E0_init = float(np.clip(max(Eg_init + 1.0, E_max_scan + 0.9, EG_PHYS_MIN + 1.1), 1.5, 10.0))

    if target_T is not None and len(target_T) > 10:
        T_sub_mean = np.mean(calculate_bare_substrate_RT(wavelengths, n_substrate))

        if T_sub_mean < 0.1:
            T_sub_mean = 0.92

        limit = 0.5 * T_sub_mean

        idx_trans = -1

        sorted_clues = np.argsort(wavelengths)

        wls_sorted = wavelengths[sorted_clues]

        T_sorted = target_T[sorted_clues]

        for i in range(len(wls_sorted)):
            if T_sorted[i] > limit:
                idx_trans = i

                break

        if idx_trans > 0:
            lambda_edge = wls_sorted[idx_trans]

            Eg_est = float(HC_EV_NM) / float(lambda_edge)

        else:
            min_lambda = float(np.min(wavelengths))

            if min_lambda > 10.0:
                Eg_est = (float(HC_EV_NM) / min_lambda) + 0.5

            else:
                Eg_est = E_max_scan + 0.3

        Eg_est_clamped = float(np.clip(Eg_est, 0.5, 9.5))

        Eg_init = float(np.clip(max(Eg_est_clamped, E_max_scan + 0.12, EG_PHYS_MIN), 0.5, 9.5))

        E0_init = float(np.clip(max(Eg_init + 0.55, E_max_scan + 0.85, EG_PHYS_MIN + 1.1), 1.5, 10.0))

    # Clear-slab spectrum (high normalized T): tightened Urbach tail + Eg well above hv_max -> tiny initial eps2 and k.

    if target_T is not None:
        _ts = np.asarray(target_T, dtype=np.float64)

        _ts = _ts[np.isfinite(_ts)]

        if _ts.size > 0:
            t_med = float(np.nanmedian(_ts))

            looks_normalized = bool(np.nanmax(_ts) <= 1.25)

            if looks_normalized and t_med >= 0.58:
                Eu_init = float(min(Eu_init, 0.10))

                Eg_init = float(np.clip(max(Eg_init, E_max_scan + 0.55), 0.5, 9.5))

                E0_init = float(np.clip(max(E0_init, Eg_init + 0.65), 1.5, 10.0))

    return np.array([d_init, Eg_init, A_init, E0_init, C_init, Eu_init, eps_init], dtype=np.float64)

# =============================================================================

# SAPPHIRE SUBSTRATE  tabulated nk data (example/sapphire fresnel.xlsx)

# Loaded once at import time. Used AUTOMATICALLY when substrate resolves to the canonical
# sapphire substrate label.

# Default physical thickness: 1 mm = 1e6 nm.

# DO NOT MODIFY OR BYPASS THIS BLOCK.

# =============================================================================

_SAPPHIRE_DATA_FILE = str(Path(script_dir) / "example" / "sapphire fresnel.xlsx")

_SAPPHIRE_WLS: np.ndarray | None = None

_SAPPHIRE_N: np.ndarray | None = None

_SAPPHIRE_K: np.ndarray | None = None

# True seulement si le xlsx contient une colonne k explicite (sinon k=0 partout, pas d'absorption reelle).

_SAPPHIRE_FILE_HAS_K_COLUMN: bool = False

_SAPPHIRE_DEFAULT_THICKNESS_NM: float = 1.0e6  # 1 mm in nm  DO NOT CHANGE

try:
    _df_sap = pd.read_excel(_SAPPHIRE_DATA_FILE, header=0, engine="openpyxl")

    _df_sap.columns = _df_sap.columns.astype(str).str.strip().str.lower()

    _wl_col = next((c for c in _df_sap.columns if ("wl" in c) or ("wave" in c) or ("lambda" in c)), _df_sap.columns[0])

    _n_col = next((c for c in _df_sap.columns if c == "n" or c.startswith("n_") or c == "n_sub"), None)

    _k_col = next((c for c in _df_sap.columns if c == "k" or c.startswith("k_") or c == "k_sub"), None)

    _rnu_col = next((c for c in _df_sap.columns if ("r bare" in c) or ("rnu" in c)), None)

    _df_sap = _df_sap.sort_values(by=_wl_col)

    if _n_col is None and _rnu_col is not None:
        _df_sap = _df_sap.dropna(subset=[_wl_col, _rnu_col])

    else:
        _n_col = _n_col or _df_sap.columns[1]

        _df_sap = _df_sap.dropna(subset=[_wl_col, _n_col])

    _SAPPHIRE_WLS = _df_sap[_wl_col].to_numpy(dtype=np.float64)

    if _n_col is None and _rnu_col is not None:
        _r2f = _df_sap[_rnu_col].to_numpy(dtype=np.float64)

        _rfrac = np.clip(_r2f / 100.0 if np.nanmax(_r2f) > 2.0 else _r2f, 1.0e-6, 0.999999)

        _disc = np.maximum(2.0 * _rfrac - _rfrac * _rfrac, 0.0)

        _SAPPHIRE_N = (1.0 + np.sqrt(_disc)) / np.maximum(1.0 - _rfrac, 1.0e-9)

    else:
        _SAPPHIRE_N = _df_sap[_n_col].to_numpy(dtype=np.float64)

    _SAPPHIRE_K = np.zeros_like(_SAPPHIRE_WLS, dtype=np.float64)

    _SAPPHIRE_FILE_HAS_K_COLUMN = False

except (FileNotFoundError, OSError, *NUMERICAL_FAULT_EXCEPTIONS) as _e_sap:
    _SAPPHIRE_FILE_HAS_K_COLUMN = False

    import warnings

    warnings.warn(
        f"[CERTUS INDEX] Sapphire substrate reference unavailable: example/sapphire fresnel.xlsx "
        f"({_e_sap}). Transparent substrate fallback will be used.",
        stacklevel=1,
    )

def _get_sapphire_k_on_grid(wavelengths_nm: np.ndarray) -> np.ndarray | None:
    """Interpolate sapphire k on any wavelength grid. Returns None if data unavailable."""

    if _SAPPHIRE_WLS is None or _SAPPHIRE_K is None:
        return None

    return np.interp(wavelengths_nm, _SAPPHIRE_WLS, _SAPPHIRE_K, left=0.0, right=0.0).astype(np.float64)


# =============================================================================

# SILICON SUBSTRATE  tabulated nk data from clues.xlsx -> Si-substrate

# Single Source of Truth: clues.xlsx is the authoritative reference.

# Loaded once at import time. Used AUTOMATICALLY when substrate = Silicon (Si).

# =============================================================================

_SILICON_WLS: np.ndarray | None = None

_SILICON_N: np.ndarray | None = None

_SILICON_K: np.ndarray | None = None

try:
    from certus_physics.materials_data import SI_WAVELENGTH_NM, SI_N_DATA, SI_K_DATA

    _SILICON_WLS = SI_WAVELENGTH_NM

    _SILICON_N = SI_N_DATA

    _SILICON_K = SI_K_DATA

except NUMERICAL_FAULT_EXCEPTIONS as _e_si:

    warnings.warn(
        f"[CERTUS INDEX] Silicon substrate reference unavailable: clues.xlsx "
        f"({_e_si}). Silicon substrate mode will be disabled.",
        stacklevel=1,
    )

def _get_silicon_k_on_grid(wavelengths_nm: np.ndarray) -> np.ndarray | None:
    """Interpolate silicon k on any wavelength grid. Returns None if data unavailable."""

    if _SILICON_WLS is None or _SILICON_K is None:
        return None

    return np.interp(wavelengths_nm, _SILICON_WLS, _SILICON_K, left=0.0, right=0.0).astype(np.float64)

def _get_silicon_n_on_grid(wavelengths_nm: np.ndarray) -> np.ndarray | None:
    """Interpolate silicon n on any wavelength grid. Returns None if data unavailable."""

    if _SILICON_WLS is None or _SILICON_N is None:
        return None

    return np.interp(
        wavelengths_nm,
        _SILICON_WLS,
        _SILICON_N,
        left=_SILICON_N[0],
        right=_SILICON_N[-1],
    ).astype(np.float64)

# Compromis rapide Phase 2 IR (HPO 7 fichiers XLSX)  max_feval=200k, max_time=300s, sub 5k/45s/80

PHASE2_IR_PGLOBAL_OVERRIDES_FAST = {
    "max_feval": 200000,
    "max_time": 300.0,
    "n_samples_per_iter": 2000,
    "max_active_clusters": 150,
    "convergence_tol": 1e-09,
    "sub_max_feval": 5000,
    "sub_max_time": 45.0,
    "sub_n_samples_per_iter": 80,
}






# =============================================================================

# PHYSICS UTILITIES - NORMALIZATION PROTECTION

# =============================================================================

def calculate_relative_R_normalization(R_abs: np.ndarray, T_sub: np.ndarray) -> np.ndarray:
    """

    Computes Relative Reflection according to User Convention.

    FORMULA: R_rel = R_absolute / T_substrate (2 faces)

    CRITICAL CONVENTION NOTE:

    -------------------------

    The user explicitly defines Relative R as the absolute reflection divided by

    the TRANSMISSION of the bare substrate (2 faces).

    Reason: The measurement baseline is often T_substrate (~92% for glass/sapphire).

    Dividing by R_substrate (~8%) would yield R_rel ~ 400%, which is wrong.

    Dividing by T_substrate yields R_rel ~ 32%, which matches the physical expectation for the coating.

    DO NOT CHANGE THIS TO DIVISION BY R_SUBSTRATE.

    """

    with np.errstate(divide="ignore", invalid="ignore"):
        # Safety for T_sub -> 0

        T_sub_safe = np.where(T_sub > T_SUB_MIN_R_NORM, T_sub, np.nan)

        R_norm = R_abs / T_sub_safe

        # If T_sub is too small (absorbing region), R_norm is undefined (NaN)

        # We replace NaNs with 0.0 or keep them based on context?

        # For plotting/optimization, we usually mask them or set to 0.

        return np.nan_to_num(R_norm, nan=0.0)

