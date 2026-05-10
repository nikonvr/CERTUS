# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

from typing import Any
import logging
import multiprocessing

import functools

import os
from pathlib import Path

import sys

import traceback

import time

from certus_core import create_module_environment, setup_module_logging

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_INDEX")

script_dir = env["script_dir"]

# Legacy aliases or specific needs

# None required if refactoring is complete

import numpy as np

import pandas as pd

from numba import njit, prange

from enum import Enum, auto

class DataType(Enum):
    """Spectral data type"""

    TRANSMISSION = auto()

    REFLECTION = auto()

    BOTH = auto()

class substrateMode(Enum):
    """substrate mode"""

    STANDARD = auto()  # Classic transparent substrate

    FROSTED_GLASS = auto()  # Infinite substrate (reflection only)

def _log_loaded_spectrum_metadata(logger, filepath: str, df: pd.DataFrame) -> None:
    """Log canonical metadata for a newly loaded spectrum file."""
    fp_abs = Path(filepath).resolve()
    logger.info("-" * 60)
    logger.info("[FILE] Spectrum loaded: %s", fp_abs)
    logger.info("[FILE] Name: %s", Path(filepath).name)
    logger.info("[FILE] Dimensions: %d rows × %d columns", df.shape[0], df.shape[1])
    logger.info("-" * 60)

def _detected_data_type_label(data_type: DataType) -> str:
    """Return human-readable label for detected spectral data type."""
    type_labels = {
        DataType.TRANSMISSION: " Detected:  TRANSMISSION only",
        DataType.REFLECTION: " Detected:  REFLECTION only",
        DataType.BOTH: " Detected: TRANSMISSION + REFLECTION",
    }
    return type_labels[data_type]

def _update_lambda_bounds_from_target_data(
    target_data: pd.DataFrame,
    sb_lmin,
    sb_lmax,
    logger,
) -> tuple[float, float]:
    """Update lambda spinbox bounds from target data and log range."""
    lmin = float(target_data["lambda"].min())
    lmax = float(target_data["lambda"].max())
    sb_lmin.setValue(lmin)
    sb_lmax.setValue(lmax)
    logger.info(f"Spectral range: {lmin:.1f} - {lmax:.1f} nm")
    return lmin, lmax

def _source_type_label(data_type: DataType) -> str:
    """Return compact source-type label for load summary dialog."""
    return {
        DataType.TRANSMISSION: "Transmission",
        DataType.REFLECTION: "Reflection",
        DataType.BOTH: "Transmission + Reflection",
    }.get(data_type, "Unknown")

def _is_qt_offscreen_mode() -> bool:
    """Return True when Qt is running in offscreen mode."""
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"

def _update_loaded_file_label(lbl_file, filepath: str) -> str:
    """Update file label widget and return basename."""
    fname = Path(filepath).name
    lbl_file.setText(f" {fname}")
    lbl_file.setStyleSheet(f"color: {CertusTheme.SUCCESS}; font-weight: bold;")
    lbl_file.setToolTip(filepath)
    return fname

def _set_spectrum_plot_title(plot_spectrum, source_name: str) -> None:
    """Set standardized spectrum title from source name."""
    src_name = Path(source_name).stem
    plot_spectrum.plotItem.setTitle(f"Spectrum      {src_name}")

def _display_detected_data_type(lbl_data_type, logger, data_type: DataType) -> str:
    """Display and log detected source data type label."""
    type_label = _detected_data_type_label(data_type)
    lbl_data_type.setText(type_label)
    logger.info(f"Data analysis: {type_label}")
    return type_label

def _prepare_nk_plot_inputs(wls, sub_df, res, logger) -> tuple | None:
    """Prepare n/k arrays and optional IR mask metadata for plotting."""
    if "n_calc" not in sub_df.columns or "k_calc" not in sub_df.columns:
        logger.error(f"Missing n_calc or k_calc in sub_df. Columns: {list(sub_df.columns)}")
        return None

    n_values = sub_df["n_calc"].values.copy()
    k_values = sub_df["k_calc"].values.copy()
    method_str = res.optimization_stats.get("method", "")
    lambda_max_fit = getattr(res.config, "lambda_max_fit", None)
    tlu_mode = lambda_max_fit is not None and "Spline" not in method_str and res.tlu_params is not None

    if tlu_mode:
        ir_mask_ui = wls > lambda_max_fit
        n_values[ir_mask_ui] = np.nan
        k_values[ir_mask_ui] = np.nan

    if np.all(np.isnan(n_values)) or np.all(np.isnan(k_values)):
        logger.error(
            f"n_calc or k_calc are all NaN! n_valid={np.sum(~np.isnan(n_values))}, k_valid={np.sum(~np.isnan(k_values))}"
        )
        return None

    return n_values, k_values, method_str, lambda_max_fit, tlu_mode

# Import Modular Architecture

from certus_core import (
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
    __version__,
    get_resource_path,
    get_safe_worker_count,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
)

from certus_data import (
    generate_html_report,
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
    calculate_bare_substrate_RT,
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

from certus_index_utils import spectral_rmse_weights

def _get_substrate_n_array_index(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Return substrate n(lambda), forcing Sapphire (id=3) to equation-based Sellmeier."""

    sid = int(substrate_id)

    wl_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    if sid != 3:
        return get_n_substrate_array_by_id(sid, wl_nm)

    coeffs = SELLMEIER_COEFFS_BY_ID.get(3)

    if coeffs is None or len(coeffs) != 6:
        raise KeyError("Missing Sellmeier coefficients for Sapphire (id=3).")

    B1, C1, B2, C2, B3, C3 = (float(v) for v in coeffs)

    wl_um = wl_nm / 1000.0

    wl_sq = wl_um * wl_um

    with np.errstate(divide="ignore", invalid="ignore"):
        n_sq = 1.0 + (B1 * wl_sq) / (wl_sq - C1) + (B2 * wl_sq) / (wl_sq - C2) + (B3 * wl_sq) / (wl_sq - C3)

    n = np.sqrt(np.maximum(n_sq, 1.0e-6))

    min_lambda_nm = float(SUBSTRATES.get("Sapphire (Al2O3)", {}).get("min_lambda", 230.0))

    n = np.where(wl_nm < min_lambda_nm, np.nan, n)

    return n.astype(np.float64)

@njit(cache=True, fastmath=True)
def sellmeier_2poles_eval_nj(params, wl_um) -> np.ndarray:
    """

    Numba-compatible Sellmeier 2-poles model with constant A.

    params = [A, B1, L1, B2, L2] where Ci = Li^2

    n^2 = A + sum [ (Bi * wl^2) / (wl^2 - Ci) ]

    """

    A, B1, L1, B2, L2 = params

    term1 = (B1 * wl_um**2) / (wl_um**2 - L1**2)

    term2 = (B2 * wl_um**2) / (wl_um**2 - L2**2)

    val = A + term1 + term2

    return np.sqrt(np.maximum(val, 1e-6))

@njit(cache=True, fastmath=True)
def k_law_8p_eval(L_um, p) -> Any:
    """

    Numba-compatible 8-parameter empirical model for extinction coefficient k(lambda).

    k(L) = 1e-6 + exp(p[0]*L + p[1]) + exp(p[2]*L + p[3]) + p[4]*exp(-|(L-p[5])/p[6]|^p[7])

    p[4]=amp, p[5]=center (m), p[6]=width (m), p[7]=beta (shape exponent:

    1=Laplace, 2=Gaussian, >2=Super-Gaussian). Beta is clipped to [1, 8] to match flat_bounds.

    Exponential arguments are soft-saturated (tanh) to avoid overflow while keeping k(L) smooth (no kink at clip boundaries).

    """

    # Soft saturation to avoid overflow: smooth transition instead of hard clip so dk/dlambda is continuous (no "kink" or "break")

    _lo, _hi = -25.0, 5.0

    _mid = 0.5 * (_lo + _hi)

    _scale = 2.0

    x1 = p[0] * L_um + p[1]

    x2 = p[2] * L_um + p[3]

    e1_arg = _mid + (0.5 * (_hi - _lo)) * np.tanh((x1 - _mid) / _scale)

    e2_arg = _mid + (0.5 * (_hi - _lo)) * np.tanh((x2 - _mid) / _scale)

    base1 = np.exp(e1_arg)

    base2 = np.exp(e2_arg)

    # Super-Gaussian peak: ensure width and exponent are positive and within bounds

    amp, center, width, exponent = p[4], p[5], p[6], p[7]

    w_safe = max(width, 1e-9)

    # Manual scalar clip (Numba type inference issue with np.clip on scalar)

    beta = max(min(exponent, 8.0), 1.0)

    # abs() required for non-integer exponents

    arg = np.abs((L_um - center) / w_safe)

    gauss = amp * np.exp(-(arg**beta))

    return 1e-6 + base1 + base2 + gauss

def _deduce_knots_from_k8p(wl_um, p_k8, num_knots=8, min_knot_dist_um=0.05) -> Any:
    """Deduce the positions of the knots for the spline k from the curve k 8p.

    Reasoning in log k: curvature of log(k_ref), cumulative equidistribution.

    Returns knot_lambda_um (array of length num_knots), edges = wl_um.min/max."""

    k_ref = k_law_8p_eval(wl_um, p_k8)

    log_k_ref = np.log(np.maximum(k_ref, SMALL_EPSILON))

    n_pts = len(wl_um)

    if n_pts < 4 or num_knots < 3:
        return np.linspace(wl_um.min(), wl_um.max(), max(3, num_knots))

    # Curvature |d2(log k)/dlambda2| by central finite differences

    dlam = np.diff(wl_um)

    dlogk = np.diff(log_k_ref)

    dlogk_dlam = np.zeros_like(wl_um, dtype=np.float64)

    dlogk_dlam[0] = dlogk[0] / dlam[0] if dlam[0] > 1e-10 else 0.0

    dlogk_dlam[-1] = dlogk[-1] / dlam[-1] if dlam[-1] > 1e-10 else 0.0

    dlogk_dlam[1:-1] = (log_k_ref[2:] - log_k_ref[:-2]) / (wl_um[2:] - wl_um[:-2])

    curv = np.zeros(n_pts, dtype=np.float64)

    curv[1:-1] = np.abs((dlogk_dlam[2:] - dlogk_dlam[:-2]) / (wl_um[2:] - wl_um[:-2] + 1e-20))

    cum = np.zeros(n_pts + 1, dtype=np.float64)

    cum[1:] = np.cumsum(np.maximum(curv, 0.0))

    total = cum[-1]

    if total < 1e-20:
        return np.linspace(wl_um.min(), wl_um.max(), num_knots)

    # Equidistribution of cumulative curvature: N-2 internal nodes.
    # Uses np.searchsorted (O(N log N)) to place knots at equal-curvature intervals
    # instead of iterating per-knot (O(N*M) in the original loop).

    knot_lam = np.empty(num_knots, dtype=np.float64)

    knot_lam[0] = wl_um.min()

    knot_lam[-1] = wl_um.max()

    t_vals = np.arange(1, num_knots - 1, dtype=np.float64) / float(num_knots - 1)

    targets = t_vals * total

    # Vectorized knot placement: find insertion points for all targets at once.
    idx = np.searchsorted(cum[1:], targets)  # O(K log N)

    idx = np.clip(idx, 0, n_pts - 1)  # guard: clamp to valid range

    knot_lam[1 : num_knots - 1] = wl_um[idx]

    knot_lam = np.sort(knot_lam)

    # Enforcer min_knot_dist

    for _ in range(10):
        bad = np.where(np.diff(knot_lam) < min_knot_dist_um)[0]

        if len(bad) == 0:
            break

        for i in bad:
            mid = (knot_lam[i] + knot_lam[i + 1]) * 0.5

            knot_lam[i] = mid - min_knot_dist_um * 0.5

            knot_lam[i + 1] = mid + min_knot_dist_um * 0.5

        knot_lam[0] = wl_um.min()

        knot_lam[-1] = wl_um.max()

        knot_lam = np.sort(knot_lam)

    return _ensure_strictly_increasing(knot_lam, min_gap=min_knot_dist_um * 0.5)

def _ensure_strictly_increasing(knot_lam: np.ndarray, min_gap: float = 1e-10) -> np.ndarray:
    """Guarantee a knot array is strictly increasing (CubicSpline requires strict growth).

    Algorithm (vectorized prefix-scan, O(N)):
        Subtracts a linear floor, applies ``np.maximum.accumulate``, then restores.
        See ``_enforce_sigma_min_sep`` for detailed description of the technique.

    Guards:
        - Returns input unchanged if fewer than 2 knots.
        - Post-condition: np.all(np.diff(out) >= min_gap - 1e-15).
    """
    # --- Input validation ---
    out = np.asarray(knot_lam, dtype=np.float64).copy()

    if out.size < 2:
        return out

    # --- Vectorized prefix-scan (O(N), no Python loop) ---
    floor = np.arange(out.size, dtype=np.float64) * min_gap

    shifted = out - floor

    shifted = np.maximum.accumulate(shifted)

    out = shifted + floor

    return out

def _merge_closest_knot_pair(knot_lam_um: np.ndarray, log_k_values: np.ndarray) -> tuple:
    """Reduced by one node by merging the closest pair of consecutive nodes.

    Returns (knot_lam_new, log_k_new) of length n-1."""

    n = len(knot_lam_um)

    if n <= 2:
        return knot_lam_um.copy(), log_k_values.copy()

    gaps = np.diff(knot_lam_um)

    i_merge = int(np.argmin(gaps))

    lam_new = np.concatenate(
        [
            knot_lam_um[:i_merge],
            [(knot_lam_um[i_merge] + knot_lam_um[i_merge + 1]) * 0.5],
            knot_lam_um[i_merge + 2 :],
        ]
    )

    log_k_new = np.concatenate(
        [
            log_k_values[:i_merge],
            [(log_k_values[i_merge] + log_k_values[i_merge + 1]) * 0.5],
            log_k_values[i_merge + 2 :],
        ]
    )

    return lam_new, log_k_new

class IRGlobalObjective:
    """Refinement objective for Phase 2 (>2500nm) using 13-parameter global model."""

    def __init__(self, wls, target_T, target_R, n_sub, T_sub, R_sub, thickness, n_tlu_ref, config) -> None:

        self.wls = wls.astype(np.float64)

        self.wl_um = (wls / 1000.0).astype(np.float64)

        self.target_T = target_T.astype(np.float64) if target_T is not None else None

        self.target_R = target_R.astype(np.float64) if target_R is not None else None

        self.n_sub = n_sub.astype(np.float64)

        self.T_sub = T_sub.astype(np.float64)

        self.R_sub = R_sub.astype(np.float64)

        self.thickness = float(thickness)

        self.n_tlu_ref = n_tlu_ref.astype(np.float64)

        self.is_frosted = config.is_frosted_glass

        self.data_type = config.data_type

        self.use_norm = config.use_normalized

        self.weight_T = config.weight_T

        self.weight_R = config.weight_R

        # Absorbing substrate: required for correct R/T physics in _compute_cost

        _k = getattr(config, "k_sub_data", None)

        _D = getattr(config, "substrate_thickness_nm", None)

        self._k_sub = _k.astype(np.float64) if _k is not None else None

        self._D_sub = float(_D) if _D is not None else None

        self._abs_sub = config.has_absorbing_substrate

        # Use unified Log-Lambda weighting for broadband optimization.

        # This compensates for sampling density and gives equal weights per octave.

        self.spec_w = spectral_rmse_weights(self.wls, weight_space="log")

        self._inv_T_sub = np.where(self.T_sub > SMALL_EPSILON, 1.0 / self.T_sub, np.nan)

        # Apply Exclusion and Range Masks

        mask = np.ones_like(self.wls, dtype=bool)

        # 1. Lambda Range

        mask &= (self.wls >= config.lambda_min) & (self.wls <= config.lambda_max)

        # 2. Exclude Range

        if config.exclude_min is not None and config.exclude_max is not None:
            mask &= ~((self.wls >= config.exclude_min) & (self.wls <= config.exclude_max))

        self.spec_w[~mask] = 0.0

        # Normalize weights so mean of ACTIVE points is 1

        if np.any(mask):
            self.spec_w /= np.mean(self.spec_w[mask])

        # Fast-rejection constants for guards in __call__

        self.ir_limit = 2500.0

        self._mask_vis = self.wls <= self.ir_limit

        # Relaxed n_tol for global Phase 2 so Sobol can find feasible starting points

        self.n_tol = 0.20

        # k_max: 0.02 for true IR (>=2500 nm); relaxed for VIS/near-IR-only data

        self.k_max_guard = 0.02 if np.max(self.wls) >= 2500.0 else 0.15

        # VIS subset: used for early continuity check before full n/k/RT computation

        self._wl_um_vis = self.wl_um[self._mask_vis]

        self._n_tlu_ref_vis = self.n_tlu_ref[self._mask_vis]

        # Wavelength range (m) for Sellmeier pole singularity pre-check

        self._wl_um_min = float(self.wl_um.min())

        self._wl_um_max = float(self.wl_um.max())

        # Optional constraint for T-only / R-only sub-fits (set after main R+T search)

        self.n_ref_global = None

        self.n_ref_tol = 0.05

        self._cache_version = 0

        self._cache = None

    def invalidate_cache(self) -> None:

        self._cache_version += 1

        self._cache = None

    def _get_cached(self, p: np.ndarray) -> Any:

        c = self._cache

        if c is None:
            return None

        if c["version"] != self._cache_version:
            return None

        if c["x"].shape != p.shape:
            return None

        if not np.array_equal(c["x"], p):
            return None

        return c

    def _set_cached(self, p: np.ndarray, cost=None, grad=None, n=None, k=None) -> None:

        c = self._cache

        if c is None or c["version"] != self._cache_version or c["x"].shape != p.shape or not np.array_equal(c["x"], p):
            c = {
                "version": self._cache_version,
                "x": p.copy(),
                "cost": None,
                "grad": None,
                "n": None,
                "k": None,
            }

        if cost is not None:
            c["cost"] = float(cost)

        if grad is not None:
            c["grad"] = np.asarray(grad, dtype=np.float64).copy()

        if n is not None:
            c["n"] = np.asarray(n, dtype=np.float64).copy()

        if k is not None:
            c["k"] = np.asarray(k, dtype=np.float64).copy()

        self._cache = c

    def __call__(self, p) -> Any:

        cached = self._get_cached(p)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        # p = [sellmeier_5, k_law_8]

        # 0. Scalar pre-check: Sellmeier pole singularity

        # L1=p[2], L2=p[4] (m). If either pole lies inside the spectral range,

        # n diverges (NaN/Inf). Skip full vectorized call (~34% of random L2 draws rejected).

        L1, L2 = p[2], p[4]

        if (self._wl_um_min < L1 < self._wl_um_max) or (self._wl_um_min < L2 < self._wl_um_max):
            return 1e12

        # 1. VIS-only Sellmeier to check continuity with Phase 1 before full computation

        n_vis = sellmeier_2poles_eval_nj(p[:5], self._wl_um_vis)

        if np.any(np.abs(n_vis - self._n_tlu_ref_vis) > self.n_tol):
            return 1e12

        # 2. Full Sellmeier and k over full wavelength grid

        n = sellmeier_2poles_eval_nj(p[:5], self.wl_um)

        k = k_law_8p_eval(self.wl_um, p[5:])

        # 3. Physical bounds: n in [1.2, 4.0], k <= k_max. NaN guard for fastmath edge cases.

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max_guard + 1e-6):
            return 1e12

        # 4. Optional reference guard for T-only / R-only sub-fits

        if self.n_ref_global is not None:
            if np.any(np.abs(n - self.n_ref_global) > self.n_ref_tol):
                return 1e12

        cost = self._compute_cost(n, k)

        self._set_cached(p, cost=cost, n=n, k=k)

        return cost

    def _compute_cost(self, n, k) -> Any:

        if self.is_frosted:
            R_c = calculate_single_interface_R(self.wls, n, k, self.thickness, self.n_sub)

            # Frosted: single-face R (absolute or relative). Never R/Tnu.

            R_val = R_c

            mse_r, n_r = compute_mse_vectorized(R_val, self.target_R, self.spec_w)

            return mse_r if n_r >= 5 else 1e9

        else:
            # substrate: absorbing (k_sub != 0, IR e.g. Sapphire) or transparent.

            # When _abs_sub: T and R use Beer-Lambert in substrate; required for IR > 2500 nm.

            if self._abs_sub:
                R_c, T_c = calculate_RT_single_layer_absorbing_substrate_array(
                    self.wls, n, k, self.thickness, self.n_sub, self._k_sub, self._D_sub
                )

            else:
                R_c, T_c = calculate_RT_single_layer_backside_array(self.wls, n, k, self.thickness, self.n_sub)

            cost = 0.0

            total_w = 0.0

            if self.target_T is not None and self.data_type in (DataType.TRANSMISSION, DataType.BOTH):
                T_val = T_c

                if self.use_norm:
                    T_val = T_val * self._inv_T_sub

                mse_t, n_t = compute_mse_vectorized(T_val, self.target_T, self.spec_w)

                if n_t >= 5:
                    cost += mse_t * self.weight_T

                    total_w += self.weight_T

            if self.target_R is not None and self.data_type in (DataType.REFLECTION, DataType.BOTH):
                R_val = R_c

                if self.use_norm:
                    R_val = R_val * self._inv_T_sub

                mse_r, n_r = compute_mse_vectorized(R_val, self.target_R, self.spec_w)

                if n_r >= 5:
                    cost += mse_r * self.weight_R

                    total_w += self.weight_R

            return cost / total_w if total_w > 0 else 1e9

    def gradient(self, p) -> Any:

        cached = self._get_cached(p)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        # 0. Pre-check: skip computation if out of bounds/poles

        L1, L2 = p[2], p[4]

        if (self._wl_um_min < L1 < self._wl_um_max) or (self._wl_um_min < L2 < self._wl_um_max):
            raise ValueError("Pole in computation range")

        # Numba kernel computes n/k and Jacobians together; avoid duplicate n/k evals.

        n, k, dn_dp, dk_dp = _compute_phase2_derivatives_kernel(self.wl_um, p)

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max_guard + 1e-6):
            raise ValueError("Out of bounds")

        if self.n_ref_global is not None:
            if np.any(np.abs(n - self.n_ref_global) > self.n_ref_tol):
                raise ValueError("n_ref_global constraint violated")

        use_T = self.target_T is not None and self.data_type in (DataType.TRANSMISSION, DataType.BOTH)

        use_R = self.target_R is not None and self.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.is_frosted:
            use_T = False

            use_R = self.target_R is not None

        wT_actual = self.weight_T if use_T else 0.0

        wR_actual = self.weight_R if use_R else 0.0

        # Avoid division by zero in total weight normalization

        total_w = wT_actual + wR_actual if (use_T or use_R) else 1e-9

        wT_actual /= total_w

        wR_actual /= total_w

        # Dummy arrays if None

        tgt_T = self.target_T if self.target_T is not None else np.zeros(0)

        tgt_R = self.target_R if self.target_R is not None else np.zeros(0)

        k_sub_v = self._k_sub if self._k_sub is not None else np.zeros(0)

        D_sub_v = self._D_sub if self._D_sub is not None else 0.0

        grad = _compute_ir_global_cost_gradient_kernel(
            self.wls,
            n,
            k,
            self.thickness,
            self.n_sub,
            tgt_T,
            tgt_R,
            self.spec_w,
            use_T,
            use_R,
            dn_dp,
            dk_dp,
            self.T_sub,
            self.use_norm,
            wT_actual,
            wR_actual,
            self.is_frosted,
            self._abs_sub,
            k_sub_v,
            D_sub_v,
        )

        self._set_cached(p, grad=grad, n=n, k=k)

        return grad

def _phase23_cached_get(cache: dict[str, object] | None, x: np.ndarray) -> dict[str, object] | None:
    """Shared cache access for Phase23 objective wrappers."""
    c = cache
    if c is None:
        return None
    if c["x"].shape != x.shape:
        return None
    if not np.array_equal(c["x"], x):
        return None
    return c

def _phase23_cached_set(
    cache: dict[str, object] | None,
    x: np.ndarray,
    *,
    cost: float | None = None,
    grad: np.ndarray | None = None,
) -> dict[str, object]:
    """Shared cache write for Phase23 objective wrappers."""
    c = cache
    if c is None or c["x"].shape != x.shape or not np.array_equal(c["x"], x):
        c = {"x": x.copy(), "cost": None, "grad": None}

    if cost is not None:
        c["cost"] = float(cost)

    if grad is not None:
        c["grad"] = np.asarray(grad, dtype=np.float64).copy()

    return c

class Phase23SplineObjective:
    """Objective Phase 2.3: n (Sellmeier 5p, tight bounds) + k spline in log k.

    x = [p_sell(5), log_k_knot_values(num_knots)].

    k(lambda) = exp(clip(B @ log_k_knots, log(k_min), log(k_max)))."""

    def __init__(self, base_obj: IRGlobalObjective, knot_lambda_um: np.ndarray, k_max: float) -> None:

        self.obj = base_obj

        self.knot_lambda_um = np.asarray(knot_lambda_um, dtype=np.float64)

        self.num_knots = len(self.knot_lambda_um)

        self.k_max = float(k_max)

        self._log_k_lo = np.log(1e-9)

        self._log_k_hi = np.log(max(self.k_max, 1e-9))

        self._B = SplineBasisCache.get(self.knot_lambda_um, base_obj.wl_um)

        self._p_dummy_8 = np.zeros(8, dtype=np.float64)

        self._cache = None

    def _get_cached(self, x: np.ndarray) -> Any:
        return _phase23_cached_get(self._cache, x)

    def _set_cached(self, x: np.ndarray, cost=None, grad=None) -> None:
        self._cache = _phase23_cached_set(self._cache, x, cost=cost, grad=grad)

    def __call__(self, x: np.ndarray) -> float:

        cached = self._get_cached(x)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        L1, L2 = p_sell[2], p_sell[4]

        if (self.obj._wl_um_min < L1 < self.obj._wl_um_max) or (self.obj._wl_um_min < L2 < self.obj._wl_um_max):
            return 1e12

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return 1e12

        n = sellmeier_2poles_eval_nj(p_sell, self.obj.wl_um)

        log_k = self._B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max + 1e-6):
            return 1e12

        if self.obj.n_ref_global is not None and np.any(np.abs(n - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return 1e12

        cost = self.obj._compute_cost(n, k)

        self._set_cached(x, cost=cost)

        return cost

    def gradient(self, x: np.ndarray) -> np.ndarray:

        cached = self._get_cached(x)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        log_k = self._B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        p_full = np.concatenate([p_sell, self._p_dummy_8])

        n_arr, _, dn_dp, _ = _compute_phase2_derivatives_kernel(self.obj.wl_um, p_full)

        dn_dp = dn_dp[:, :]

        dk_dp = (k[:, np.newaxis] * self._B).T

        use_T = self.obj.target_T is not None and self.obj.data_type in (DataType.TRANSMISSION, DataType.BOTH)

        use_R = self.obj.target_R is not None and self.obj.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.obj.is_frosted:
            use_T, use_R = False, self.obj.target_R is not None

        wT = self.obj.weight_T if use_T else 0.0

        wR = self.obj.weight_R if use_R else 0.0

        total_w = wT + wR if (use_T or use_R) else 1e-9

        wT /= total_w

        wR /= total_w

        tgt_T = self.obj.target_T if self.obj.target_T is not None else np.zeros(0)

        tgt_R = self.obj.target_R if self.obj.target_R is not None else np.zeros(0)

        k_sub_v = self.obj._k_sub if self.obj._k_sub is not None else np.zeros(0)

        D_sub_v = self.obj._D_sub if self.obj._D_sub is not None else 0.0

        grad = _compute_ir_global_cost_gradient_kernel(
            self.obj.wls,
            n_arr,
            k,
            self.obj.thickness,
            self.obj.n_sub,
            tgt_T,
            tgt_R,
            self.obj.spec_w,
            use_T,
            use_R,
            dn_dp,
            dk_dp,
            self.obj.T_sub,
            self.obj.use_norm,
            wT,
            wR,
            self.obj.is_frosted,
            self.obj._abs_sub,
            k_sub_v,
            D_sub_v,
        )

        self._set_cached(x, grad=grad)

        return grad

class Phase23Pass2SplineObjective:
    """Objective Phase 2.3 Pass 2: n (Sellmeier 5p) + k spline in log k + internal positions of the nodes.

    x = [p_sell (5), log_k_knot_values (num_knots), internal_lambda (num_knots-2)].

    knot_lam = [wl_min, sort(internal_lambda), wl_max]. Lambda gradient by finite differences."""

    def __init__(
        self,
        base_obj: IRGlobalObjective,
        num_knots: int,
        wl_min_um: float,
        wl_max_um: float,
        k_max: float,
        min_knot_dist_um: float,
    ) -> None:

        self.obj = base_obj

        self.num_knots = num_knots

        self.n_internes = num_knots - 2

        self.wl_min = float(wl_min_um)

        self.wl_max = float(wl_max_um)

        self.k_max = float(k_max)

        self.min_knot_dist = float(min_knot_dist_um)

        self._log_k_lo = np.log(1e-9)

        self._log_k_hi = np.log(max(self.k_max, 1e-9))

        self._p_dummy_8 = np.zeros(8, dtype=np.float64)

        self._fd_eps = max(1e-7 * (wl_max_um - wl_min_um), 1e-8)

        self._cache = None

    def _get_cached(self, x: np.ndarray) -> Any:
        return _phase23_cached_get(self._cache, x)

    def _set_cached(self, x: np.ndarray, cost=None, grad=None) -> None:
        self._cache = _phase23_cached_set(self._cache, x, cost=cost, grad=grad)

    def _knot_lam_from_x(self, x: np.ndarray) -> np.ndarray:

        lam_int = np.sort(x[5 + self.num_knots : 5 + self.num_knots + self.n_internes].copy())

        knot_lam = np.concatenate([[self.wl_min], lam_int, [self.wl_max]])

        knot_lam = _ensure_strictly_increasing(knot_lam, min_gap=1e-9)

        knot_lam[0] = self.wl_min

        knot_lam[-1] = self.wl_max

        if knot_lam[1] <= knot_lam[0]:
            knot_lam[1] = knot_lam[0] + 1e-9

        if len(knot_lam) > 2 and knot_lam[-2] >= knot_lam[-1]:
            knot_lam[-2] = knot_lam[-1] - 1e-9

        return knot_lam

    def __call__(self, x: np.ndarray) -> float:

        cached = self._get_cached(x)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        knot_lam = self._knot_lam_from_x(x)

        L1, L2 = p_sell[2], p_sell[4]

        if (self.obj._wl_um_min < L1 < self.obj._wl_um_max) or (self.obj._wl_um_min < L2 < self.obj._wl_um_max):
            return 1e12

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return 1e12

        n = sellmeier_2poles_eval_nj(p_sell, self.obj.wl_um)

        B = SplineBasisCache.get(knot_lam, self.obj.wl_um)

        log_k = B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        if not np.all(np.isfinite(n)) or np.any(n < 1.199) or np.any(n > 4.001) or np.any(k > self.k_max + 1e-6):
            return 1e12

        if self.obj.n_ref_global is not None and np.any(np.abs(n - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return 1e12

        cost = self.obj._compute_cost(n, k)

        self._set_cached(x, cost=cost)

        return cost

    def gradient(self, x: np.ndarray) -> np.ndarray:

        cached = self._get_cached(x)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        p_sell = x[:5]

        log_k_knot = x[5 : 5 + self.num_knots]

        knot_lam = self._knot_lam_from_x(x)

        # Invariants for all lambda-knot FD probes in this gradient call.

        n_vis = sellmeier_2poles_eval_nj(p_sell, self.obj._wl_um_vis)

        if np.any(np.abs(n_vis - self.obj._n_tlu_ref_vis) > self.obj.n_tol):
            return np.zeros_like(x, dtype=np.float64)

        B = SplineBasisCache.get(knot_lam, self.obj.wl_um)

        log_k = B @ log_k_knot

        log_k_c = np.clip(log_k, self._log_k_lo, self._log_k_hi)

        k = np.exp(log_k_c)

        p_full = np.concatenate([p_sell, self._p_dummy_8])

        n_arr, _, dn_dp, _ = _compute_phase2_derivatives_kernel(self.obj.wl_um, p_full)

        if not np.all(np.isfinite(n_arr)) or np.any(n_arr < 1.199) or np.any(n_arr > 4.001):
            return np.zeros_like(x, dtype=np.float64)

        if self.obj.n_ref_global is not None and np.any(np.abs(n_arr - self.obj.n_ref_global) > self.obj.n_ref_tol):
            return np.zeros_like(x, dtype=np.float64)

        dn_dp = dn_dp[:, :]

        dk_dp = (k[:, np.newaxis] * B).T

        use_T = self.obj.target_T is not None and self.obj.data_type in (DataType.TRANSMISSION, DataType.BOTH)

        use_R = self.obj.target_R is not None and self.obj.data_type in (DataType.REFLECTION, DataType.BOTH)

        if self.obj.is_frosted:
            use_T, use_R = False, self.obj.target_R is not None

        wT = self.obj.weight_T if use_T else 0.0

        wR = self.obj.weight_R if use_R else 0.0

        total_w = wT + wR if (use_T or use_R) else 1e-9

        wT /= total_w

        wR /= total_w

        tgt_T = self.obj.target_T if self.obj.target_T is not None else np.zeros(0)

        tgt_R = self.obj.target_R if self.obj.target_R is not None else np.zeros(0)

        k_sub_v = self.obj._k_sub if self.obj._k_sub is not None else np.zeros(0)

        D_sub_v = self.obj._D_sub if self.obj._D_sub is not None else 0.0

        grad_sell_logk = _compute_ir_global_cost_gradient_kernel(
            self.obj.wls,
            n_arr,
            k,
            self.obj.thickness,
            self.obj.n_sub,
            tgt_T,
            tgt_R,
            self.obj.spec_w,
            use_T,
            use_R,
            dn_dp,
            dk_dp,
            self.obj.T_sub,
            self.obj.use_norm,
            wT,
            wR,
            self.obj.is_frosted,
            self.obj._abs_sub,
            k_sub_v,
            D_sub_v,
        )

        grad_lambda = np.zeros(self.n_internes, dtype=np.float64)

        x_plus = x.copy()

        x_minus = x.copy()

        def _cost_fixed_n_for_knot(knot_lam_local: np.ndarray) -> float:

            B_local = SplineBasisCache.get(knot_lam_local, self.obj.wl_um)

            log_k_local = B_local @ log_k_knot

            log_k_local_c = np.clip(log_k_local, self._log_k_lo, self._log_k_hi)

            k_local = np.exp(log_k_local_c)

            if np.any(k_local > self.k_max + 1e-6) or not np.all(np.isfinite(k_local)):
                return 1e12

            return self.obj._compute_cost(n_arr, k_local)

        for i in range(self.n_internes):
            idx = 5 + self.num_knots + i

            x_plus[idx] = x[idx] + self._fd_eps

            x_minus[idx] = x[idx] - self._fd_eps

            knot_plus = self._knot_lam_from_x(x_plus)

            knot_minus = self._knot_lam_from_x(x_minus)

            c_plus = _cost_fixed_n_for_knot(knot_plus)

            c_minus = _cost_fixed_n_for_knot(knot_minus)

            if np.isfinite(c_plus) and np.isfinite(c_minus):
                grad_lambda[i] = (c_plus - c_minus) / (2.0 * self._fd_eps)

            x_plus[idx] = x[idx]

            x_minus[idx] = x[idx]

        grad_full = np.concatenate([grad_sell_logk, grad_lambda])

        self._set_cached(x, grad=grad_full)

        return grad_full

def sellmeier_2poles_eval(params, wl_um) -> Any:
    """

    params = [A, B1, L1, B2, L2] where Ci = Li^2

    n^2 = A + sum [ (Bi * wl^2) / (wl^2 - Ci) ]

    """

    return sellmeier_2poles_eval_nj(params, wl_um)

def _sellmeier_residuals(params, wl_um, n_exp) -> Any:

    return (sellmeier_2poles_eval(params, wl_um) - n_exp) * 1000

def fit_sellmeier_global(
    wls_nm: np.ndarray, n_exp: np.ndarray, material: str = "other", valid_mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """

    Robust 3-pole Sellmeier fit using differential_evolution to find the global minimum,

    followed by a least_squares polish.

    Returns (n_fit_array, params_array)

    """

    from scipy.optimize import differential_evolution, least_squares

    import logging

    wl_um = wls_nm / 1000.0

    wl_fit = wl_um

    n_fit = n_exp

    if valid_mask is not None:
        wl_fit = wl_um[valid_mask]

        n_fit = n_exp[valid_mask]

    # A, B1, L1, B2, L2

    b_bounds = [(1.0, 10.0), (0.0, 10.0), (0.01, 0.5), (0.0, 10.0), (0.05, 0.8)]

    if str(material).lower() == "sio2":
        # A, B1, L1, B2, L2

        b_bounds = [(1.4, 1.5), (0.0, 2.0), (0.01, 0.15), (0.0, 2.0), (0.05, 0.25)]

    def cost_func(p) -> np.ndarray:

        res = _sellmeier_residuals(p, wl_fit, n_fit)

        # Soft-L1 like cost to ignore outliers/noise

        return np.sum(np.log1p(res**2))

    try:
        # 1. Global Search (differential_evolution)

        res_global = differential_evolution(
            cost_func,
            bounds=b_bounds,
            strategy="best1bin",
            maxiter=1000,
            popsize=15,
            mutation=(0.5, 1.0),
            recombination=0.7,
            seed=42,  # Reproducibility
            polish=False,  # We polish manually with robust loss below
        )

        # 2. Local Polish (least_squares with soft_l1)

        # We reformat bounds for least_squares: (lower_array, upper_array)

        ls_bounds = ([b[0] for b in b_bounds], [b[1] for b in b_bounds])

        res_local = least_squares(
            _sellmeier_residuals, res_global.x, bounds=ls_bounds, args=(wl_fit, n_fit), loss="soft_l1", f_scale=0.1
        )

        return sellmeier_2poles_eval(res_local.x, wl_um), res_local.x

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
        logging.getLogger(__name__).warning(f"Sellmeier fit failed: {e}. Falling back to raw spline n.")

        return n_exp, None

def fit_k_global_8p(
    wls_nm: np.ndarray, k_exp: np.ndarray, valid_mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray | None]:
    """

    Fit k with a robust 8-parameter empirical law (Exponential baselines + 1 Super-Gaussian):

    k(L) = 1e-6 + exp(P1*L + P0) + exp(P3*L + P2) + P4*exp(-abs((L-P5)/P6)**P7)

    """

    from scipy.optimize import least_squares

    L_um = wls_nm / 1000.0

    mask = (k_exp > 1e-8) & (L_um >= 0.8)

    if valid_mask is not None:
        mask &= valid_mask

    if np.sum(mask) < 8:
        return k_exp, None

    L_fit = L_um[mask]

    k_fit = k_exp[mask]

    def obj_func(p, L, k_target) -> Any:

        fit = k_law_8p_eval(L, p)

        return np.log10(fit + 1e-9) - np.log10(k_target + 1e-9)

    # [slope1, pos1, slope2, pos2, amp, center, width, beta]

    p0 = [1.0, -10.0, 0.1, -15.0, 1e-4, 2.8, 0.2, 2.0]

    bounds = ([-20.0, -40.0, -20.0, -40.0, 0.0, 1.0, 0.01, 1.0], [20.0, 5.0, 20.0, 5.0, 1.0, 20.0, 5.0, 6.0])

    try:
        res = least_squares(obj_func, p0, bounds=bounds, args=(L_fit, k_fit), loss="soft_l1")

        k_smooth = k_law_8p_eval(L_um, res.x)

        # Prevent k from exploding on the left side too much if not fitted properly

        k_smooth = np.where(L_um <= 1.0, k_exp, k_smooth)

        return k_smooth, res.x

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
        logging.getLogger(__name__).warning(f"k 8-param fit failed: {e}")

        return k_exp, None

# ---------------------------------------------------------

from certus_ui import (
    CertusBaseApp,
    CertusCard,
    CertusDashboardCard,
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    CertusThemeToggle,
    DetachedPlotWindow,
    EnhancedProgressWidget,
    ExcelTableWidget,
    FlashyCard,
    apply_certus_theme,
    clone_plot_widget,
    wrap_scientific_plot_with_toolbar,
    create_styled_button,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    stop_worker_and_thread,
    create_header_logo_widget,
    create_top_actions_bar,
    certus_get_open_file_name,
    get_export_config,
    init_certus_app,
    open_documentation,
    set_certus_last_dir,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
)
from certus_metrology import ValidationStatus
from certus_services import IndexFitRequest, IndexFitService

from certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus_ux import build_premium_overrides, OBJ

# JIT Warmup (reduces first-call latency by ~90%)

# JIT Warmup moved to main() with SplashScreen

from certus_svg import SVG_AVAILABLE

if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget  # pylint: disable=unused-import

else:
    QSvgWidget = None

from concurrent.futures import ThreadPoolExecutor, as_completed

from threading import Event

import pyqtgraph as pg

import scipy.optimize

from PyQt6.QtCore import QObject, QSettings, Qt, QThread, QTimer, pyqtSignal, pyqtSlot

from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# PyQtGraph configured via COMMON utility

setup_pyqtgraph_defaults()

# Install exception handler

setup_gui_exception_handling()

def detect_data_type(data: np.ndarray, threshold: float = 0.80) -> str:
    """Detect if data represents transmission or reflection via statistical analysis.

    Heuristics:

    - Transmission typically has high values (>80% for most of spectrum)

    - Reflection typically has low values (<20% for uncoated substrates)

    - High-reflectance mirrors can have R > 95% - use physical constraints

    Returns 'T' or 'R'"""

    data_copy = data.copy()

    # Normalize if in percentage format

    if np.nanmax(data_copy) > 1.5:
        data_copy = data_copy / 100.0

    valid_data = data_copy[np.isfinite(data_copy)]

    if len(valid_data) == 0:
        return "T"  # Default to T if no valid data

    mean_val = np.nanmean(valid_data)

    max_val = np.nanmax(valid_data)

    # High mean (>50%) strongly suggests transmission

    if mean_val > 0.50:
        return "T"

    # Low mean + low max strongly suggests reflection

    if mean_val < 0.20 and max_val < 0.30:
        return "R"

    # >10% of points above threshold suggests T

    n_above_threshold = np.sum(valid_data > threshold)

    ratio_above = n_above_threshold / len(valid_data)

    if ratio_above > 0.10:
        return "T"

    # Max > 95% typically transmission

    if max_val > 0.95:
        return "T"

    return "R"

def _detect_type_from_column_name(col_name: str) -> str:
    """Detect data type from column header name.

    Returns 'T', 'R', or 'unknown'."""

    if col_name is None:
        return "unknown"

    name_lower = str(col_name).lower().strip()

    # Transmission patterns (incl. Tnu, T_nu = normalized T)

    t_patterns = ["t", "trans", "transmission", "%t", "t%", "t(%)", "tnu", "t_nu"]

    for pat in t_patterns:
        if name_lower == pat or name_lower.startswith(pat + " ") or name_lower.startswith(pat + "("):
            return "T"

    # Reflection patterns (incl. Rnu, R_nu = normalized R)

    r_patterns = ["r", "refl", "reflection", "%r", "r%", "r(%)", "rnu", "r_nu"]

    for pat in r_patterns:
        if name_lower == pat or name_lower.startswith(pat + " ") or name_lower.startswith(pat + "("):
            return "R"

    return "unknown"

def analyze_loaded_data(df: pd.DataFrame) -> tuple[DataType, dict[str, np.ndarray]]:
    """Analyze a loaded DataFrame to detect data type.

    Detection priority:

    1. Column header names (if present: 'T', 'R', 'Trans', 'Refl', etc.)

    2. Statistical analysis of data distribution

    Returns (DataType, {'lambda': array, 'T': array or None, 'R': array or None})"""

    result = {
        "lambda": df.iloc[:, 0].to_numpy().astype(np.float64),
        "T": None,
        "R": None,
    }

    n_cols = len(df.columns)

    col_names = list(df.columns)

    if n_cols == 2:
        col2_data = df.iloc[:, 1].to_numpy().astype(np.float64)

        # Try column name first

        col2_header_type = _detect_type_from_column_name(col_names[1])

        if col2_header_type != "unknown":
            col2_type = col2_header_type

        else:
            col2_type = detect_data_type(col2_data)

        if col2_type == "T":
            result["T"] = col2_data

            return DataType.TRANSMISSION, result

        else:
            result["R"] = col2_data

            return DataType.REFLECTION, result

    elif n_cols >= 3:
        col2_data = df.iloc[:, 1].to_numpy().astype(np.float64)

        col3_data = df.iloc[:, 2].to_numpy().astype(np.float64)

        # Try column names first

        col2_header_type = _detect_type_from_column_name(col_names[1])

        col3_header_type = _detect_type_from_column_name(col_names[2])

        # If both headers detected, use them

        if col2_header_type != "unknown" and col3_header_type != "unknown":
            if col2_header_type == "T":
                result["T"] = col2_data

            else:
                result["R"] = col2_data

            if col3_header_type == "T":
                result["T"] = col3_data

            else:
                result["R"] = col3_data

            if result["T"] is not None and result["R"] is not None:
                return DataType.BOTH, result

            elif result["T"] is not None:
                return DataType.TRANSMISSION, result

            else:
                return DataType.REFLECTION, result

        # Fall back to statistical detection

        col2_type = col2_header_type if col2_header_type != "unknown" else detect_data_type(col2_data)

        col3_type = col3_header_type if col3_header_type != "unknown" else detect_data_type(col3_data)

        # Conflict or Ambiguity Resolution

        if col2_type == col3_type:
            # Both look like T or both look like R

            # User Rule: "The column with larger values corresponds to T"

            # User Hint: "Zoom towards IR" -> substrate usually transparent in IR

            # Use 95th percentile to robustly estimate "Max" without noise

            val2 = np.nanpercentile(col2_data, 95)

            val3 = np.nanpercentile(col3_data, 95)

            # If values are extremely close (e.g. difference < 5%), look at the IR/End of spectrum

            if abs(val2 - val3) < 0.05:
                # Assume sorted wavelengths? usually yes. Take last 20% points

                n_pts = len(col2_data)

                start_idx = int(0.8 * n_pts)

                val2_ir = np.nanmean(col2_data[start_idx:])

                val3_ir = np.nanmean(col3_data[start_idx:])

                # If IR distinct, use that

                if abs(val2_ir - val3_ir) > 0.02:
                    val2 = val2_ir

                    val3 = val3_ir

            if val2 > val3:
                result["T"] = col2_data

                result["R"] = col3_data

            else:
                result["R"] = col2_data

                result["T"] = col3_data

            return DataType.BOTH, result

        if col2_type == "T":
            result["T"] = col2_data

            result["R"] = col3_data

        else:
            result["R"] = col2_data

            result["T"] = col3_data

        return DataType.BOTH, result

    result["T"] = df.iloc[:, 1].to_numpy().astype(np.float64) if n_cols > 1 else np.array([])

    return DataType.TRANSMISSION, result

@njit(cache=True, fastmath=True, nogil=True)
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

@njit(cache=True, fastmath=True, nogil=True)
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

@njit(cache=True, fastmath=True, nogil=True, parallel=True)
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

    Calibré pour un départ diélectrique réaliste (n≈2, k faible) : ε∞≈4, Eg tient

    compte de l'énergie max hν de la fenêtre spectrale afin que ε2 reste modérée

    dans toute la plage (cf. Urbach / TLU).

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

# Loaded once at import time. Used AUTOMATICALLY when substrate = Al2O3.

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

    _SAPPHIRE_K = (
        _df_sap[_k_col].to_numpy(dtype=np.float64)
        if _k_col is not None
        else np.zeros_like(_SAPPHIRE_WLS, dtype=np.float64)
    )

    _SAPPHIRE_FILE_HAS_K_COLUMN = _k_col is not None

except NUMERICAL_FAULT_EXCEPTIONS as _e_sap:
    _SAPPHIRE_FILE_HAS_K_COLUMN = False

    import warnings

    warnings.warn(
        f"[CERTUS INDEX] ATTENTION : impossible de load example/sapphire fresnel.xlsx "
        f"({_e_sap}). Al2O3 absorbent substrate mode will be disabled.",
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
        f"[CERTUS INDEX] ATTENTION : impossible de load Si depuis clues.xlsx "
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

class OptimizationConfig:
    """Configuration for INDEX optimization - Supports R, T, R+T, Frosted Glass, TLU and Spline modes"""

    __slots__ = [
        "target_data",
        "data_type",
        "substrate",
        "substrate_mode",
        "thickness_min",
        "thickness_max",
        "lambda_min",
        "lambda_max",
        "exclude_min",
        "exclude_max",
        "source_file",
        "use_normalized",
        "weight_T",
        "weight_R",
        "high_precision",
        "dispersion_mode",
        "num_knots",
        "nk_min",
        "nk_max",
        "min_knot_dist",
        "fixed_thickness",
        "lambda_max_fit",
        "phase2_pglobal_overrides",
        "k_sub_data",
        "substrate_thickness_nm",
        "n_sub_data",
        "random_seed",
    ]

    def __init__(
        self,
        target_data: pd.DataFrame,
        data_type: DataType,
        substrate: str,
        thickness_min: float,
        thickness_max: float,
        lambda_min: float,
        lambda_max: float,
        exclude_min: float | None = None,
        exclude_max: float | None = None,
        source_file: str = "",
        use_normalized: bool = True,
        weight_T: float = 1.0,
        weight_R: float = 1.0,
        substrate_mode: substrateMode = substrateMode.STANDARD,
        high_precision: bool = False,
        dispersion_mode: str = "TLU",
        num_knots: int = 6,
        nk_min: float = 0.0,
        nk_max: float = 10.0,
        min_knot_dist: float = 20.0,
        fixed_thickness: float | None = None,
        lambda_max_fit: float | None = None,
        phase2_pglobal_overrides: dict | None = None,
        k_sub_data: np.ndarray | None = None,
        substrate_thickness_nm: float | None = None,
        n_sub_data: np.ndarray | None = None,
        random_seed: int | None = None,
    ) -> None:

        self.target_data = target_data

        self.data_type = data_type

        self.substrate = substrate

        self.substrate_mode = substrate_mode

        # UI peut inverser min/max : normaliser pour des bounds SciPy valides

        self.thickness_min = float(min(thickness_min, thickness_max))

        self.thickness_max = float(max(thickness_min, thickness_max))

        self.lambda_min = float(min(lambda_min, lambda_max))

        self.lambda_max = float(max(lambda_min, lambda_max))

        self.exclude_min = exclude_min

        self.exclude_max = exclude_max

        self.source_file = source_file

        self.use_normalized = use_normalized

        self.weight_T = weight_T

        self.weight_R = weight_R

        self.high_precision = high_precision

        # Spline mode fields

        self.dispersion_mode = dispersion_mode  # "TLU" or "SPLINE"

        self.num_knots = num_knots

        self.nk_min = nk_min

        self.nk_max = nk_max

        self.min_knot_dist = min_knot_dist

        self.fixed_thickness = fixed_thickness  # Fixed thickness for spline mode

        self.lambda_max_fit = lambda_max_fit  # Optional max wavelength specifically for fitting, ignores data beyond this but keeps it in target_data

        self.phase2_pglobal_overrides = (
            phase2_pglobal_overrides if phase2_pglobal_overrides is not None else dict(PHASE2_IR_PGLOBAL_OVERRIDES_FAST)
        )  # Optional: override Phase 2 IR PGlobal; default = compromis rapide HPO

        self.k_sub_data = (
            k_sub_data  # Optional: k_sub per wavelength (same grid as target_data); None = transparent substrate
        )

        self.substrate_thickness_nm = (
            substrate_thickness_nm  # Physical substrate thickness in nm; required when k_sub_data is set
        )

        self.n_sub_data = (
            n_sub_data  # Optional: n_sub from file (e.g. example/sapphire fresnel.xlsx); when set, overrides Sellmeier
        )
        self.random_seed = int(random_seed) if random_seed is not None else None

    @property
    def is_frosted_glass(self) -> bool:

        return self.substrate_mode == substrateMode.FROSTED_GLASS

    @property
    def has_absorbing_substrate(self) -> bool:

        return (
            self.k_sub_data is not None
            and self.substrate_thickness_nm is not None
            and self.substrate_thickness_nm > 0
            and not self.is_frosted_glass
        )

class OptimizationResults:
    """Results of INDEX optimization"""

    __slots__ = [
        "config",
        "optimal_thickness",
        "final_mse",
        "df_results",
        "tlu_params",
        "optimization_stats",
        "execution_time",
        "sellmeier_params",
        "k_8p_params",
        "p_opt_T",
        "n_T",
        "k_T",
        "k_spline_knots_lambda_um",
        "k_spline_knots_values",
    ]

    def __init__(
        self,
        config: OptimizationConfig,
        optimal_thickness: float,
        final_mse: float,
        df_results: pd.DataFrame,
        tlu_params: TLUParameters | None = None,
        optimization_stats: dict | None = None,
        execution_time: float = 0.0,
        sellmeier_params=None,
    ) -> None:

        self.config = config

        self.optimal_thickness = optimal_thickness

        self.final_mse = final_mse

        self.df_results = df_results

        self.tlu_params = tlu_params

        self.optimization_stats = optimization_stats or {}

        self.execution_time = execution_time

        self.sellmeier_params = sellmeier_params

        self.k_8p_params = None

        self.p_opt_T = None

        self.n_T = None

        self.k_T = None

        self.k_spline_knots_lambda_um = None

        self.k_spline_knots_values = None

    @property
    def thickness(self) -> float:
        """Alias for backward compatibility"""

        return self.optimal_thickness

# Inner margin relative to the limits used in epsilon_to_nk (certus_core):
# avoids trajectories stuck exactly on the hard cut while keeping the full physical space
# (dielectrics through strongly absorbing high-index or light metalloid within the model box).
TLU_SOFT_EDGE_MARGIN = 0.05

# "Clear slab" prior (normalized T, BOTH): pushes away solutions where eps' is clamped to 1.0 in the
# TL model -> n~1 "air" with artificially low RMSE. Aligned with the current dielectric range (>=1.5).
TLU_PRIOR_TRANSPARENT_N_MIN_SOFT = 1.50

class TLUObjective:
    """Objective function for TLU optimization - Supports frosted glass"""

    def __init__(
        self,
        wavelengths: np.ndarray,
        target_T: np.ndarray | None,
        target_R: np.ndarray | None,
        n_substrate: np.ndarray,
        data_type: DataType,
        thickness_bounds: tuple,
        use_normalized: bool = True,
        weight_T: float = 1.0,
        weight_R: float = 1.0,
        exclude_range: tuple | None = None,
        is_frosted_glass: bool = False,
        lambda_max_fit: float | None = None,
        has_absorbing_substrate: bool = False,
        k_sub_data: np.ndarray | None = None,
        substrate_thickness_nm: float | None = None,
    ) -> None:

        self.wavelengths = wavelengths.astype(np.float64)

        self.n_substrate = n_substrate.astype(np.float64)

        self.data_type = data_type

        self.thickness_bounds = thickness_bounds

        self.use_normalized = use_normalized

        self.weight_T = weight_T

        self.weight_R = weight_R

        self.is_frosted_glass = is_frosted_glass

        self.E_array = (HC_EV_NM / self.wavelengths).astype(np.float64)

        self.target_T = target_T.astype(np.float64) if target_T is not None else None

        self.target_R = target_R.astype(np.float64) if target_R is not None else None

        self.has_absorbing_substrate = has_absorbing_substrate

        self.k_sub_data = k_sub_data.astype(np.float64) if k_sub_data is not None else None

        self.substrate_thickness_nm = float(substrate_thickness_nm) if substrate_thickness_nm is not None else None

        # References for normalization

        self.T_substrate = calculate_bare_substrate_RT(self.wavelengths, self.n_substrate)

        self._inv_T_sub = np.where(self.T_substrate > SMALL_EPSILON, 1.0 / self.T_substrate, np.nan)

        if is_frosted_glass:
            self.R_substrate = calculate_single_interface_R(self.wavelengths, self.n_substrate)

        else:
            self.R_substrate = (
                calculate_bare_substrate_RT,
                calculate_single_interface_R(self.wavelengths, self.n_substrate),
            )

        # Use unified Log-Lambda weighting for broadband optimization.

        # This compensates for sampling density and gives equal weights per octave.

        self.weights = spectral_rmse_weights(self.wavelengths, weight_space="log")

        if exclude_range:
            ex_min, ex_max = exclude_range

            mask = (self.wavelengths >= ex_min) & (self.wavelengths <= ex_max)

            self.weights[mask] = 0.0

        if lambda_max_fit is not None:
            mask_fit = self.wavelengths > lambda_max_fit

            self.weights[mask_fit] = 0.0

        # Normalize weights so mean of ACTIVE points is 1

        active_mask = self.weights > 1e-12

        if np.any(active_mask):
            self.weights /= np.mean(self.weights[active_mask])

        self.n_evals = 0

        self.best_value = np.inf

        self.best_params = None

        self._cache = None

        # Eg (eV): if Eg << hv over part of the window, the TLU becomes inconsistent (wild n/k).
        # Lower bound = max photon on grid + small margin (sub-gap model usable across the full fit).

        _eg_lo = float(max(0.5, min(9.5, float(np.max(self.E_array)) + 0.05)))

        _e0_lo = float(max(1.5, _eg_lo + 0.35))

        self.param_bounds = np.array(
            [
                [_eg_lo, 10.0],  # Eg
                [10.0, 2000.0],  # A
                [_e0_lo, 10.0],  # E0 > Eg en pratique
                [0.1, 10.0],  # C
                [0.01, 3.0],  # Eu
                [1.4, 10.0],  # eps_inf
            ],
            dtype=np.float64,
        )

        # If T data shows a highly transparent slab (T/Tsub or normalized T), the scan must not
        # start with giant k: soft ceiling on max(k) well below K_MAX_LIMIT.

        self._k_soft_ceiling = float(K_MAX_LIMIT) - float(TLU_SOFT_EDGE_MARGIN)

        self._prior_transparent_low_k = False

        if (
            target_T is not None
            and self.use_normalized
            and self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
            and not self.is_frosted_glass
        ):
            wm = self.weights > 1e-12

            if np.any(wm):
                tt = np.asarray(target_T)[wm]

                ww = self.weights[wm]

                mask = np.isfinite(tt) & (ww > 1e-15)

                if np.any(mask):
                    w_med = float(np.nanmedian(tt[mask]))

                    if w_med >= 0.58:
                        self._prior_transparent_low_k = True

                        self._k_soft_ceiling = min(self._k_soft_ceiling, 3e-3)

        # WARNING log budget in __call__ ("why does k explode" analysis) without flooding 20k evals.

        self._tlu_explode_logs_left = 20

    def format_diag_line(self, params: np.ndarray) -> str:
        """Human-readable line: n, k_max @lambda, k ceilings, TLU (Eg, Eu, ...), eps2, E>Eg fraction."""

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size < 7:
            return "diag: params incomplets"

        d = float(p[0])

        Eg, A, E0, C, Eu, eps_inf = [float(p[i]) for i in range(1, 7)]

        eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        ik = int(np.argmax(k_calc))

        kmax = float(k_calc[ik])

        wl_k = float(self.wavelengths[ik])

        n_lo = float(np.min(n_calc))

        n_hi = float(np.max(n_calc))

        emax = float(np.max(self.E_array))

        eg_frac = float(np.mean(self.E_array > Eg))

        eps2_max = float(np.max(eps2))

        eps2_at_kmax = float(eps2[ik])

        k_ceil = float(getattr(self, "_k_soft_ceiling", float(K_MAX_LIMIT)))

        _pri = bool(getattr(self, "_prior_transparent_low_k", False))

        return (
            f"n∈[{n_lo:.3f},{n_hi:.3f}] k_max={kmax:.4g} @λ={wl_k:.0f}nm "
            f"k_ceiling={k_ceil:.4g}(prior_T={_pri}) "
            f"d={d:.1f}nm Eg={Eg:.4f} Eu={Eu:.4f} E0={E0:.4f} "
            f"frac(E>Eg)={eg_frac:.2f} eps2_max={eps2_max:.4g} eps2@kmax={eps2_at_kmax:.4g} hν_max={emax:.4f}eV"
        )

    def format_k_line(self, params: np.ndarray) -> str:
        """Short string centered on k(lambda) for Phase 1 PGLOBAL logs."""

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size < 7:
            return "k: params incomplets"

        Eg, A, E0, C, Eu, eps_inf = [float(p[i]) for i in range(1, 7)]

        eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        ik = int(np.argmax(k_calc))

        k_min = float(np.min(k_calc))

        k_med = float(np.median(k_calc))

        k_max = float(np.max(k_calc))

        wl_k = float(self.wavelengths[ik])

        ik_lo = int(np.argmin(k_calc))

        wl_lo = float(self.wavelengths[ik_lo])

        k_ceil = float(getattr(self, "_k_soft_ceiling", float(K_MAX_LIMIT)))

        return (
            f"k_min={k_min:.4g} k_med={k_med:.4g} k_max={k_max:.4g} | λ(k_max)={wl_k:.0f} nm λ(k_min)={wl_lo:.0f} nm "
            f"| k_ceiling_soft={k_ceil:.4g}"
        )

    def get_bounds(self) -> np.ndarray:

        thickness_bound = np.array([[self.thickness_bounds[0], self.thickness_bounds[1]]], dtype=np.float64)

        return np.vstack([thickness_bound, self.param_bounds])

    def _get_cached(self, params: np.ndarray) -> Any:

        c = self._cache

        if c is None:
            return None

        if c["x"].shape != params.shape:
            return None

        if not np.array_equal(c["x"], params):
            return None

        return c

    def _set_cached(self, params: np.ndarray, cost=None, grad=None) -> None:

        c = self._cache

        if c is None or c["x"].shape != params.shape or not np.array_equal(c["x"], params):
            c = {"x": params.copy(), "cost": None, "grad": None}

        if cost is not None:
            c["cost"] = float(cost)

        if grad is not None:
            c["grad"] = np.asarray(grad, dtype=np.float64).copy()

        self._cache = c

    def gradient(self, params: np.ndarray) -> np.ndarray:
        """Computes analytic gradient of the objective function."""

        cached = self._get_cached(params)

        if cached is not None and cached["grad"] is not None:
            return cached["grad"]

        # Unpack parameters

        thickness = params[0]

        Eg, A, E0, C, Eu, eps_inf = params[1:7]

        grad = np.zeros(7, dtype=np.float64)

        # --- Penalty Gradients ---

        # Thickness bounds

        if thickness < self.thickness_bounds[0]:
            # P = 1000 * (min - t)^2 -> dP/dt = -2000 * (min - t)

            grad[0] += -2000.0 * (self.thickness_bounds[0] - thickness)

        elif thickness > self.thickness_bounds[1]:
            # P = 1000 * (t - max)^2 -> dP/dt = 2000 * (t - max)

            grad[0] += 2000.0 * (thickness - self.thickness_bounds[1])

        # E0 vs Eg constraint

        # if E0 <= Eg: P = 100 * (Eg - E0 + 0.1)^2

        # dP/dEg = 200 * (Eg - E0 + 0.1)

        # dP/dE0 = -200 * (Eg - E0 + 0.1)

        if E0 <= Eg:
            term = 200.0 * (Eg - E0 + 0.1)

            grad[1] += term  # Eg is params[1]

            grad[3] -= term  # E0 is params[3]

        elif E0 - Eg < 0.3:
            # P = 10 * (0.3 - (E0 - Eg))^2 = 10 * (0.3 - E0 + Eg)^2

            # dP/dEg = 20 * (0.3 - E0 + Eg)

            # dP/dE0 = -20 * (0.3 - E0 + Eg)

            term = 20.0 * (0.3 - E0 + Eg)

            grad[1] += term

            grad[3] -= term

        # Positivity constraints (soft barrier?)

        # TLUObjective returns 1e12 + penalty if invalid.

        # Analytic gradient near 0 might be problematic but we assume valid region for local polish.

        if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
            # Return zero gradient or steep gradient?

            # Zero is safer to avoid exploding optimizers if they step out

            grad0 = np.zeros(7)

            self._set_cached(params, grad=grad0)

            return grad0

        # --- Cost Gradient ---

        # 1. Compute Material Derivatives (dn/dp, dk/dp)

        # Kernel returns dMSE/[Eg, A, E0, C, Eu, eps_inf]

        n_calc, k_calc, dn_dp, dk_dp = _compute_tlu_derivatives_kernel(self.E_array, Eg, A, E0, C, Eu, eps_inf)

        # --- Physical Penalty Gradients ---

        _m = float(TLU_SOFT_EDGE_MARGIN)

        _n_lo = float(N_MIN_LIMIT) + _m

        _n_hi = float(N_MAX_LIMIT) - _m

        _k_hi = float(K_MAX_LIMIT) - _m

        _k_hi_eff = float(min(_k_hi, getattr(self, "_k_soft_ceiling", _k_hi)))

        _pk = float(3500.0 if getattr(self, "_prior_transparent_low_k", False) else 1000.0)

        _n_lo_eff = float(_n_lo)

        if getattr(self, "_prior_transparent_low_k", False):
            _n_lo_eff = max(_n_lo_eff, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

        idx_n_min = np.argmin(n_calc)

        n_min = n_calc[idx_n_min]

        if n_min < _n_lo_eff:
            dPd_n = -2000.0 * (_n_lo_eff - n_min)

            grad[1:7] += dPd_n * dn_dp[:, idx_n_min]

        idx_n_max = np.argmax(n_calc)

        n_max = n_calc[idx_n_max]

        if n_max > _n_hi:
            dPd_n = 2000.0 * (n_max - _n_hi)

            grad[1:7] += dPd_n * dn_dp[:, idx_n_max]

        idx_k_max = np.argmax(k_calc)

        k_peak = k_calc[idx_k_max]

        if k_peak > _k_hi_eff:
            dPd_k = 2.0 * _pk * (k_peak - _k_hi_eff)

            grad[1:7] += dPd_k * dk_dp[:, idx_k_max]

        # 2. Compute Total MSE Gradient (dMSE/d_thickness, dMSE/d_params)

        use_T = (
            self.data_type in (DataType.TRANSMISSION, DataType.BOTH)
            and self.target_T is not None
            and not self.is_frosted_glass
        )

        use_R = self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None

        target_T_arr = self.target_T if self.target_T is not None else np.zeros_like(self.wavelengths)

        target_R_arr = self.target_R if self.target_R is not None else np.zeros_like(self.wavelengths)

        # Normalize data type weights to match __call__ scaling

        total_dt_weight = (self.weight_T if use_T else 0.0) + (self.weight_R if use_R else 0.0)

        wT_norm = self.weight_T / total_dt_weight if total_dt_weight > 0 else 0.0

        wR_norm = self.weight_R / total_dt_weight if total_dt_weight > 0 else 0.0

        # Call kernel with full normalization support

        if self.has_absorbing_substrate:
            # Use the more general IR global gradient kernel which supports absorption

            mse_grad = _compute_ir_global_cost_gradient_kernel(
                self.wavelengths,
                n_calc,
                k_calc,
                thickness,
                self.n_substrate,
                target_T_arr,
                target_R_arr,
                self.weights,
                use_T,
                use_R,
                dn_dp,
                dk_dp,
                self.T_substrate,
                self.use_normalized,
                wT_norm,
                wR_norm,
                self.is_frosted_glass,
                True,  # has_absorbing_substrate
                self.k_sub_data,
                self.substrate_thickness_nm,
            )

        else:
            # Use specialized fast kernel for transparent substrates

            mse_grad = _compute_index_cost_gradient_kernel(
                self.wavelengths,
                n_calc,
                k_calc,
                thickness,
                self.n_substrate,
                target_T_arr,
                target_R_arr,
                self.weights,
                use_T,
                use_R,
                dn_dp,
                dk_dp,
                self.T_substrate,
                self.R_substrate,
                self.use_normalized,
                wT_norm,
                wR_norm,
            )

        grad += mse_grad

        self._set_cached(params, grad=grad)

        return grad

    def __call__(self, params: np.ndarray) -> float:

        cached = self._get_cached(params)

        if cached is not None and cached["cost"] is not None:
            return cached["cost"]

        self.n_evals += 1

        try:
            thickness = params[0]

            Eg, A, E0, C, Eu, eps_inf = params[1:7]

            penalty = 0.0

            if thickness < self.thickness_bounds[0]:
                penalty += 1000 * (self.thickness_bounds[0] - thickness) ** 2

            elif thickness > self.thickness_bounds[1]:
                penalty += 1000 * (thickness - self.thickness_bounds[1]) ** 2

            if E0 <= Eg:
                penalty += 100 * (Eg - E0 + 0.1) ** 2

            elif E0 - Eg < 0.3:
                penalty += 10 * (0.3 - (E0 - Eg)) ** 2

            if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
                return 1e12 + penalty

            eps2 = epsilon2_TLU_array(self.E_array, Eg, A, E0, C, Eu)

            eps1 = epsilon1_TL_analytic(self.E_array, Eg, A, E0, C, eps_inf)

            n_calc, k_calc, is_valid = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

            if not is_valid:
                return 1e12 + penalty

            # --- Physical Constraints (Soft Penalty) ---

            # Matches the same global bounds as epsilon_to_nk, with a slight inner margin:

            # compatible with all material types within [N_MIN,N_MAX], k up to K_MAX_LIMIT.

            _m = float(TLU_SOFT_EDGE_MARGIN)

            _n_lo = float(N_MIN_LIMIT) + _m

            _n_hi = float(N_MAX_LIMIT) - _m

            _k_hi = float(K_MAX_LIMIT) - _m

            _k_hi_eff = float(min(_k_hi, getattr(self, "_k_soft_ceiling", _k_hi)))

            _pk = float(3500.0 if getattr(self, "_prior_transparent_low_k", False) else 1000.0)

            _n_lo_eff = float(_n_lo)

            if getattr(self, "_prior_transparent_low_k", False):
                _n_lo_eff = max(_n_lo_eff, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

            n_min = np.min(n_calc)

            n_max = np.max(n_calc)

            k_peak = np.max(k_calc)

            if n_min < _n_lo_eff:
                penalty += 1000.0 * (_n_lo_eff - n_min) ** 2

            if n_max > _n_hi:
                penalty += 1000.0 * (n_max - _n_hi) ** 2

            if k_peak > _k_hi_eff:
                penalty += _pk * (k_peak - _k_hi_eff) ** 2

            _ex_left = int(getattr(self, "_tlu_explode_logs_left", 0))

            if k_peak > _k_hi_eff and _ex_left > 0:
                self._tlu_explode_logs_left = _ex_left - 1

                _ik2 = int(np.argmax(k_calc))

                _egf = float(np.mean(self.E_array > Eg))

                _e2m = float(np.max(eps2))

                _e2k = float(eps2[_ik2])

                logging.getLogger("CertusIndex").warning(
                    "TLU k_pen | reste %d logs | eval#%d | k_max=%.6g k_lim=%.4g p=%.0f "
                    "| Eg=%.4f Eu=%.4f E0=%.4f | frac(E>Eg)=%.2f eps2_max=%.4g eps2@kmax=%.4g | pén_k=%.4g",
                    int(self._tlu_explode_logs_left),
                    int(self.n_evals),
                    float(k_peak),
                    float(_k_hi_eff),
                    _pk,
                    float(Eg),
                    float(Eu),
                    float(E0),
                    _egf,
                    _e2m,
                    _e2k,
                    float(_pk * (k_peak - _k_hi_eff) ** 2) if k_peak > _k_hi_eff else 0.0,
                )

            total_mse = 0.0

            total_weight = 0.0

            if self.is_frosted_glass:
                if self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None:
                    R_calc = calculate_single_interface_R(self.wavelengths, n_calc, k_calc, thickness, self.n_substrate)

                    # Frosted = 1 face: R or Rnu only. Never R/Tnu.

                    R_val = R_calc

                    mse_R, n_valid_R = compute_mse_vectorized(R_val, self.target_R, self.weights)

                    if n_valid_R >= 5:
                        total_mse += mse_R * self.weight_R

                        total_weight += self.weight_R

            else:
                if self.has_absorbing_substrate:
                    R_calc, T_calc = calculate_RT_single_layer_absorbing_substrate_array(
                        self.wavelengths,
                        n_calc,
                        k_calc,
                        thickness,
                        self.n_substrate,
                        self.k_sub_data,
                        self.substrate_thickness_nm,
                    )

                else:
                    R_calc, T_calc = calculate_RT_single_layer_backside_array(
                        self.wavelengths, n_calc, k_calc, thickness, self.n_substrate
                    )

                if self.data_type in (DataType.TRANSMISSION, DataType.BOTH) and self.target_T is not None:
                    if self.use_normalized:
                        T_val = T_calc * self._inv_T_sub

                    else:
                        T_val = T_calc

                    mse_T, n_valid_T = compute_mse_vectorized(T_val, self.target_T, self.weights)

                    if n_valid_T >= 5:
                        total_mse += mse_T * self.weight_T

                        total_weight += self.weight_T

                if self.data_type in (DataType.REFLECTION, DataType.BOTH) and self.target_R is not None:
                    if self.use_normalized:
                        R_val = R_calc * self._inv_T_sub

                    else:
                        R_val = R_calc

                    mse_R, n_valid_R = compute_mse_vectorized(R_val, self.target_R, self.weights)

                    if n_valid_R >= 5:
                        total_mse += mse_R * self.weight_R

                        total_weight += self.weight_R

            if total_weight < SMALL_EPSILON:
                return 1e12 + penalty

            mse = total_mse / total_weight

            total = mse + penalty

            if total < self.best_value:
                self.best_value = total

                self.best_params = params.copy()

            self._set_cached(params, cost=total)

            return total

        except NUMERICAL_FAULT_EXCEPTIONS:
            # Critical: objective function errors fall back to large penalty

            return 1e12

class GradientSearcher:
    """L-BFGS-B local search using Analytic Gradient"""

    def __init__(
        self,
        func,
        bounds: np.ndarray,
        config: PGlobalConfig,
        stop_event: Event | None = None,
        monitor_callback=None,
    ) -> None:

        self.func = func

        self.bounds = bounds

        self.lb = bounds[:, 0]

        self.ub = bounds[:, 1]

        self.dim = len(bounds)

        self.config = config

        self.stop_event = stop_event

        self.monitor_callback = monitor_callback

    def search(self, x0: np.ndarray, max_feval: int = 1500) -> tuple:
        """Run L-BFGS-B from x0"""

        if self.stop_event and self.stop_event.is_set():
            return x0, float(self.func(x0)), 0

        # Ensure x0 is within bounds

        x0 = clip_to_bounds(x0.copy(), self.lb, self.ub)

        # Scipy L-BFGS-B wrapper

        # func should be TLUObjective object which has .gradient() method,

        # OR func is a wrapper. In PGlobalOptimizerINDEX init: self.objective = objective

        # which is the TLUObjective instance.

        # But wait, self.func passed here is self.objective.

        # Check if self.func has gradient method.

        obj_instance = self.func

        # Verify if obj_instance has gradient method, else fallback?

        # In CERTUS_INDEX logic, 'objective' passed to PGlobalOptimizerINDEX is TLUObjective instance.

        # It has __call__ and gradient(x).

        try:
            # Check if gradient exists, else use numerical approximation

            jac = getattr(obj_instance, "gradient", None)

            res = scipy.optimize.minimize(
                obj_instance,
                x0,
                method="L-BFGS-B",
                jac=jac,
                bounds=[(l, u) for l, u in zip(self.lb, self.ub)],
                options={
                    "ftol": 1e-9,
                    "gtol": 1e-9,
                    "maxfun": max_feval,
                    "maxiter": max_feval // 2,  # Heuristic
                },
                callback=self.monitor_callback,
            )

            return res.x, res.fun, res.nfev

        except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
            # Fallback if gradient fails (e.g. numerical singularity, ZeroDivisionError in TLU kernel).

            # Aligned with CERTUS_INDEX OLD.py: do not let the exception propagate -> Phase 1 PGLOBAL continues.

            logging.debug(f"Gradient optimization failed, using fallback: {e}")

            val = float(obj_instance(x0))

            return x0, val, 1

def _numba_set_threads_clamped(n: int) -> int:
    """Numba impose set_num_threads dans [1, 31] (sinon ValueError, ex. Python 3.14 / grosse machine)."""

    return max(1, min(31, int(n)))

class PGlobalOptimizerINDEX:
    """PGLOBAL optimizer adapted for INDEX"""

    def __init__(
        self,
        objective,
        bounds: np.ndarray,
        n_workers: int = None,
        config: PGlobalConfig | None = None,
        log_clues: list | None = None,
        stop_event: Event | None = None,
    ) -> None:

        self.objective = objective

        self.bounds = np.asarray(bounds, dtype=np.float64)

        self.dim = len(bounds)

        self.lb = self.bounds[:, 0]

        self.ub = self.bounds[:, 1]

        self.config = config or PGlobalConfig()

        # Safe worker count (frozen: 1)

        self.n_workers = n_workers if n_workers is not None else get_safe_worker_count()

        self.clusterer = SingleLinkageClusterer(self.bounds, self.config)

        self._all_samples: list = []

        self.n_evals = 0

        self._n_total_samples = 0

        self.log_clues = log_clues or []

        self.stop_event = stop_event

        self._executor: ThreadPoolExecutor | None = None

        self.sampling_method = "sobol"
        self.random_seed = getattr(self.config, "random_seed", None)
        self._rng = np.random.default_rng(None if self.random_seed is None else int(self.random_seed))

        try:
            from scipy.stats.qmc import Sobol

            self._qmc_engine = Sobol(
                d=self.dim,
                scramble=True,
                seed=None if self.random_seed is None else int(self.random_seed),
            )

        except ImportError:
            self._qmc_engine = None

            self.sampling_method = "uniform"

    def _unit_to_physical(self, unit: np.ndarray, n: int) -> np.ndarray:

        X = np.empty((n, self.dim))

        for i in range(self.dim):
            if i in self.log_clues:
                log_lb = np.log10(max(self.lb[i], 1e-9))

                log_ub = np.log10(self.ub[i])

                X[:, i] = np.power(10, log_lb + unit[:, i] * (log_ub - log_lb))

            else:
                X[:, i] = self.lb[i] + unit[:, i] * (self.ub[i] - self.lb[i])

        return X

    def _sample_uniform(self, n: int) -> list:

        if self.stop_event and self.stop_event.is_set():
            return []

        method = getattr(self, "sampling_method", "uniform")

        X = None

        if method == "sobol" and self._qmc_engine is not None:
            try:
                import math

                n_pow2 = 2 ** math.ceil(math.log2(n)) if n > 0 else 0

                unit = self._qmc_engine.random(n_pow2)[:n]

                X = self._unit_to_physical(unit, n)

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                method = "uniform"

        elif method == "halton":
            try:
                from scipy.stats.qmc import Halton

                sampler = Halton(d=self.dim, scramble=True)

                unit = sampler.random(n)

                X = self._unit_to_physical(unit, n)

            except ImportError:
                method = "uniform"

        elif method == "lhs":
            try:
                from scipy.stats.qmc import LatinHypercube

                sampler = LatinHypercube(d=self.dim)

                unit = sampler.random(n)

                X = self._unit_to_physical(unit, n)

            except ImportError:
                method = "uniform"

        if method == "uniform" or X is None:
            unit = self._rng.uniform(0.0, 1.0, size=(n, self.dim))

            X = self._unit_to_physical(unit, n)

        samples = []

        # Parallel Execution if executor is available

        if self._executor:
            try:
                # Map objective over X in parallel

                # TLUObjective releases GIL in Numba, allowing true parallelism

                results = self._executor.map(self.objective, X)

                for i, y in enumerate(results):
                    if self.stop_event and self.stop_event.is_set():
                        break

                    y_val = float(y)

                    samples.append(Sample(x=X[i].copy(), y=y_val if np.isfinite(y_val) else np.inf))

            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.error(f"Parallel sampling failed: {e}")

                return []

        # Sequential Fallback

        else:
            for x in X:
                if self.stop_event and self.stop_event.is_set():
                    break

                y = float(self.objective(x))

                samples.append(Sample(x=x.copy(), y=y if np.isfinite(y) else np.inf))

        self.n_evals += len(samples)

        self._n_total_samples += len(samples)

        return samples

    def optimize(self, max_iter: int = 30, callback=None, x0: np.ndarray | None = None) -> Sample | None:

        start_time = time.time()

        best_ever: Sample | None = None

        # Inject initial guess if provided

        if x0 is not None:
            try:
                y0 = float(self.objective(x0))

                s0 = Sample(x=x0.copy(), y=y0)

                self._all_samples.append(s0)

                best_ever = s0

                self.n_evals += 1

                if callback:
                    callback(best_ever)

            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.debug(f"Failed to evaluate initial guess x0: {e}")

        # Limit Numba threads when using ThreadPoolExecutor to avoid CPU oversubscription

        _numba_restore = None

        if self.n_workers > 1:
            import numba

            nb_cores = _get_cpu_count()

            try:
                _numba_restore = int(numba.get_num_threads())

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                _numba_restore = _numba_set_threads_clamped(nb_cores)

            # nb_cores // n_workers peut depasser 31 ; restauration utilisait nb_cores brut -> ValueError

            numba.set_num_threads(_numba_set_threads_clamped(max(1, nb_cores // self.n_workers)))

            self._executor = ThreadPoolExecutor(max_workers=self.n_workers)

        else:
            self._executor = None

        try:
            for iteration in range(max_iter):
                if self.stop_event and self.stop_event.is_set():
                    break

                if time.time() - start_time > self.config.max_time:
                    break

                if self.n_evals >= self.config.max_feval:
                    break

                n_samples = self.config.n_samples_per_iter

                if iteration == 0:
                    n_samples = int(n_samples * 1.5)

                new_samples = self._sample_uniform(n_samples)

                if not new_samples:
                    break

                self._all_samples.extend(new_samples)

                self._all_samples.sort(key=lambda s: s.y)

                n_keep = max(
                    int(len(self._all_samples) * self.config.reduction_ratio),
                    self.n_workers * 2,
                )

                active_samples = self._all_samples[:n_keep]

                x_batch = np.array([s.x for s in active_samples])

                y_batch = np.array([s.y for s in active_samples])

                cand_x, cand_y = self.clusterer.process_batch(x_batch, y_batch, self._n_total_samples)

                n_dispatch = min(len(cand_y), self.n_workers)

                # Regular callback for UI updates at EACH iteration

                if callback and len(self._all_samples) > 0:
                    # Use best sample so far for progress display

                    best_so_far = self._all_samples[0]  # Already sorted by y

                    if best_ever is None or best_so_far.y <= best_ever.y:
                        callback(best_so_far)

                    else:
                        callback(best_ever)

                # --- SEQUENTIAL MODE (Safe for Frozen) ---

                if self.n_workers <= 1 and n_dispatch > 0:
                    idx_sorted = np.argsort(cand_y)[:n_dispatch]

                    for idx in idx_sorted:
                        if self.stop_event and self.stop_event.is_set():
                            break

                        x_start = cand_x[idx]

                        # Define monitor callback for live updates inside L-BFGS-B

                        monitor = None

                        if callback:
                            def monitor(xk):
                                return callback(Sample(xk, self.objective(xk)))

                        searcher = GradientSearcher(
                            self.objective,
                            self.bounds,
                            self.config,
                            self.stop_event,
                            monitor_callback=monitor,
                        )

                        budget = min(
                            self.config.local_search_budget,
                            self.config.max_feval - self.n_evals,
                        )

                        # Direct call without executor

                        try:
                            x_opt, f_opt, n_ev = searcher.search(x_start, budget)

                            self.n_evals += n_ev

                            self.clusterer.add_cluster_result(x_opt, f_opt)

                            if best_ever is None or f_opt < best_ever.y:
                                best_ever = Sample(x=x_opt, y=f_opt)

                                if callback:
                                    callback(best_ever)

                        except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                            # Aligned with OLD: a failed local search must not stop PGLOBAL.

                            logging.error(
                                f"Local search error (sequential PGLOBAL): {e}",
                                exc_info=True,
                            )

                            pass

                # --- PARALLEL MODE ---

                elif n_dispatch > 0 and self._executor:
                    idx_sorted = np.argsort(cand_y)[:n_dispatch]

                    futures = {}

                    for idx in idx_sorted:
                        if self.stop_event and self.stop_event.is_set():
                            break

                        x_start = cand_x[idx]

                        # No monitor in parallel mode: callbacks must only be called from

                        # the thread that owns the Qt objects (QThread of IRGlobalModelWorker).

                        # UI updates happen via the per-iteration callback above.

                        searcher = GradientSearcher(
                            self.objective,
                            self.bounds,
                            self.config,
                            self.stop_event,
                            monitor_callback=None,
                        )

                        budget = min(
                            self.config.local_search_budget,
                            self.config.max_feval - self.n_evals,
                        )

                        futures[self._executor.submit(searcher.search, x_start, budget)] = x_start

                    for future in as_completed(futures):
                        if self.stop_event and self.stop_event.is_set():
                            break

                        try:
                            x_opt, f_opt, n_ev = future.result(timeout=60)

                            self.n_evals += n_ev

                            self.clusterer.add_cluster_result(x_opt, f_opt)

                            if best_ever is None or f_opt < best_ever.y:
                                best_ever = Sample(x=x_opt, y=f_opt)

                                if callback:
                                    callback(best_ever)

                        except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                            # Aligned with OLD: L-BFGS-B futures (gradient) may raise ZeroDivisionError, etc.

                            logging.error(
                                f"Local search error (parallel PGLOBAL): {e}",
                                exc_info=True,
                            )

                            pass

                if len(self._all_samples) > n_keep * 2:
                    self._all_samples = self._all_samples[:n_keep]

        finally:
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)

                self._executor = None

            # Restore Numba thread count after parallel sampling

            if _numba_restore is not None:

                numba.set_num_threads(_numba_set_threads_clamped(_numba_restore))

        best_cluster = self.clusterer.get_best_minimum()

        if best_cluster:
            x_best, y_best = best_cluster

            if best_ever is None or y_best < best_ever.y:
                best_ever = Sample(x=x_best, y=y_best)

        # Return true best: may be a Sobol sample never refined by L-BFGS-B

        if self._all_samples:
            self._all_samples.sort(key=lambda s: s.y)

            best_sample = self._all_samples[0]

            if best_ever is None or best_sample.y < best_ever.y:
                best_ever = best_sample

        return best_ever

    def cleanup(self) -> None:

        self.clusterer.clear()

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

class IRPGlobalCallback:
    def __init__(
        self, worker, opt_instance, obj, c, l_full, thickness, n_sub_full, title="IR Global Search", emit_plot=True
    ) -> None:

        self.worker = worker

        self.opt_instance = opt_instance

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self.title = title

        self.emit_plot = emit_plot

        self.state = [float("inf"), None, 0.0, float("inf"), 0.0, float("inf")]

    def __call__(self, sample) -> None:

        if sample.y < self.state[0]:
            self.state[0], self.state[1] = sample.y, sample.x

        now = time.time()

        if now - self.state[2] < 2.0:
            return

        self.state[2] = now

        self.worker.evals_update.emit(self.opt_instance.n_evals)

        if not self.emit_plot:
            self.worker.progress.emit(90, self.title, self.state[0])

            return

        self.worker.best_params = self.state[1]

        self.worker.best_mse = self.state[0]

        rmse = np.sqrt(self.state[0])

        improved_for_plot = rmse < (self.state[5] * 0.998)

        heartbeat_plot = (now - self.state[4]) >= 10.0

        if not improved_for_plot and not heartbeat_plot:
            self.worker.progress.emit(90, self.title, self.state[0])

            return

        n = sellmeier_2poles_eval_nj(self.state[1][:5], self.obj.wl_um)

        k = k_law_8p_eval(self.obj.wl_um, self.state[1][5:])

        Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

        T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

        # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE :

        # En mode relatif (use_normalized), R relatif (R_v) = R_calc / T_substrat_nu.

        # Ne pas corriger cette formule, elle correspond a l'etalonnage physique du spectrometre local.

        R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

        T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

        if self.c.is_frosted_glass:
            T_v = np.full_like(self.l_full, np.nan)

        _st, _sr = _index_live_spectrum_visibility(self.c)

        plot_data = {
            "n": n,
            "k": k,
            "wls": self.l_full,
            "R_calc": R_v,
            "T_calc": T_v,
            "is_frosted_glass": self.c.is_frosted_glass,
            "live_show_T": _st,
            "live_show_R": _sr,
            "mse": self.state[0],
        }

        self.state[5] = min(self.state[5], rmse)

        if rmse < self.state[3] or (now - self.state[4]) >= 10.0:
            if rmse < self.state[3]:
                self.state[3] = rmse

            self.state[4] = now

            self.worker.logger.info(f"  [PGLOBAL] Evals: {self.opt_instance.n_evals:6d} | RMSE: {rmse:.6f}")

        self.worker.progress.emit(int(self.opt_instance.n_evals / 300), self.title, plot_data)

class IRStage2Callback:
    def __init__(self, worker, obj, c, l_full, thickness, n_sub_full) -> None:

        self.worker = worker

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self._last_plot = 0.0

    def __call__(self, xk) -> None:

        if time.time() - self._last_plot < 1.5:
            return

        self._last_plot = time.time()

        try:
            n = sellmeier_2poles_eval_nj(xk[:5], self.obj.wl_um)

            k = k_law_8p_eval(self.obj.wl_um, xk[5:])

            Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

            T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

            # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE : R_v = R_calc / T_substrat_nu

            R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

            T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

            if self.c.is_frosted_glass:
                T_v = np.full_like(self.l_full, np.nan)

            _st, _sr = _index_live_spectrum_visibility(self.c)

            self.worker.progress.emit(
                91,
                "Stage 2 polish",
                {
                    "n": n,
                    "k": k,
                    "wls": self.l_full,
                    "R_calc": R_v,
                    "T_calc": T_v,
                    "is_frosted_glass": self.c.is_frosted_glass,
                    "live_show_T": _st,
                    "live_show_R": _sr,
                    "mse": None,
                },
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

class IRSplineCallback:
    def __init__(
        self,
        worker,
        obj,
        c,
        l_full,
        thickness,
        n_sub_full,
        title,
        phase23_obj=None,
        knot_lam=None,
        n_k=None,
        lk_lo=None,
        lk_hi=None,
        t0=None,
    ) -> None:

        self.worker = worker

        self.obj = obj

        self.c = c

        self.l_full = l_full

        self.thickness = thickness

        self.n_sub_full = n_sub_full

        self.title = title

        self.phase23_obj = phase23_obj

        self.knot_lam = knot_lam

        self.n_k = n_k

        self.lk_lo = lk_lo

        self.lk_hi = lk_hi

        self.t0 = t0

        self._last_plot = 0.0

    def get_plot_data(self, xk) -> dict | None:

        try:
            knot_lam_local = self.knot_lam

            if self.phase23_obj:
                knot_lam_local = self.phase23_obj._knot_lam_from_x(xk)

            n = sellmeier_2poles_eval_nj(xk[:5], self.obj.wl_um)

            B = SplineBasisCache.get(knot_lam_local, self.obj.wl_um)

            k = np.exp(np.clip(B @ xk[5 : 5 + self.n_k], self.lk_lo, self.lk_hi))

            Rc, Tc, T_sub_c = _compute_RT_from_config(self.c, self.l_full, n, k, self.thickness, self.n_sub_full)

            T_sub_norm = np.where(T_sub_c > 1e-9, T_sub_c, 1.0)

            # [SAFEGUARD] PROTOCOLE EXPERIMENTAL SPECIFIQUE : R_v = R_calc / T_substrat_nu

            R_v = Rc / T_sub_norm if self.c.use_normalized else Rc

            T_v = Tc / T_sub_norm if self.c.use_normalized else Tc

            if self.c.is_frosted_glass:
                T_v = np.full_like(self.l_full, np.nan)

            _st, _sr = _index_live_spectrum_visibility(self.c)

            return {
                "n": n,
                "k": k,
                "wls": self.l_full,
                "R_calc": R_v,
                "T_calc": T_v,
                "is_frosted_glass": self.c.is_frosted_glass,
                "live_show_T": _st,
                "live_show_R": _sr,
                "mse": None,
            }

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            return None

    def __call__(self, xk) -> bool:

        if time.time() - self._last_plot >= 1.5:
            self._last_plot = time.time()

            pd = self.get_plot_data(xk)

            if pd is not None:
                self.worker.progress.emit(99, self.title, pd)

        if self.t0 is not None:
            return (time.time() - self.t0) >= 10.0

class IRGlobalModelWorker(QObject):
    """

    Refined IR extension pipeline (>2500nm) using PGLOBAL with Sellmeier+EmpiricalK models.

    Replaces the legacy Spline-based approach.

    """

    finished = pyqtSignal(object)

    error = pyqtSignal(str)

    progress = pyqtSignal(int, str, object)

    evals_update = pyqtSignal(int)

    curve_update = pyqtSignal(object)  # best-so-far params (aligned with OptimizationWorker)

    def __init__(self, config: OptimizationConfig, tlu_results: OptimizationResults, logger=None) -> None:

        super().__init__()

        self.config = config

        self.tlu_results = tlu_results

        self.logger = logger or logging.getLogger("CertusIndex")

        self._stop_event = Event()

        self.best_mse = np.inf

        self.best_params = None

    def stop(self) -> None:

        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:

        return self._stop_event.is_set()

    def _prepare_ir_phase2_inputs(self) -> tuple:
        """Prepare full-spectrum inputs and objective for IR Phase 2 global model."""

        c = self.config

        tlu = self.tlu_results

        thickness = tlu.optimal_thickness

        l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

        sub_id = SUBSTRATES[c.substrate]["id"]

        n_sub_full = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)

        # Absorbing substrate: Al2O3 or user-provided k_sub.
        _k_sub_full = c.k_sub_data

        _D_sub = c.substrate_thickness_nm

        if c.is_frosted_glass:
            T_sub_full = np.ones_like(l_full)

            R_sub_full = calculate_single_interface_R(l_full, n_sub_full)

        elif c.has_absorbing_substrate:
            T_sub_full = calculate_bare_substrate_RT(l_full, n_sub_full, _k_sub_full, _D_sub)

            R_sub_full = calculate_bare_substrate_RT(l_full, n_sub_full, _k_sub_full, _D_sub)

        else:
            T_sub_full = calculate_bare_substrate_RT(l_full, n_sub_full)

            R_sub_full = calculate_bare_substrate_RT, calculate_single_interface_R(l_full, n_sub_full)

        target_T = c.target_data["T"].to_numpy(dtype=np.float64) if "T" in c.target_data.columns else None

        target_R = c.target_data["R"].to_numpy(dtype=np.float64) if "R" in c.target_data.columns else None

        df_tlu = tlu.df_results

        n_tlu_ref = np.interp(l_full, df_tlu["lambda"].values, df_tlu["n_calc"].values)

        obj = IRGlobalObjective(
            l_full,
            target_T,
            target_R,
            n_sub_full,
            T_sub_full,
            R_sub_full,
            thickness,
            n_tlu_ref,
            c,
        )

        return l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness

    def _run_ir_stage0_to_stage2(
        self,
        c: OptimizationConfig,
        l_full: np.ndarray,
        n_sub_full: np.ndarray,
        df_tlu: pd.DataFrame,
        n_tlu_ref: np.ndarray,
        obj: IRGlobalObjective,
        thickness: float,
    ) -> tuple | None:
        """Run warm start + PGlobal + final L-BFGS-B polish and return best sample + optimizer."""

        flat_bounds = np.array(
            [
                [1.0, 16.0],
                [0.0, 20.0],
                [0.001, 1.0],
                [0.0, 20.0],
                [0.01, 20.0],
                [-40.0, 40.0],
                [-100.0, 80.0],
                [-40.0, 40.0],
                [-100.0, 80.0],
                [1e-10, 0.1],
                [0.5, 12.0],
                [0.005, 5.0],
                [1.0, 8.0],
            ],
            dtype=np.float64,
        )

        log_clues = [0, 1, 2, 3, 4, 9, 10, 11]

        self.logger.info("-" * 65)

        self.logger.info("PHASE 2/2: GLOBAL IR MODEL REFINEMENT (PGLOBAL)")

        self.logger.info("  Sellmeier 2-Poles (5p) + Empirical k (8p) = 13 dimensions")

        self.logger.info(f"  d fixed = {thickness:.2f} nm | n VIS continuity guard +/-0.20 of TLU")

        self.logger.info("-" * 65)

        x0_polished = None

        y0_polished = np.inf

        try:
            _, params_sell = fit_sellmeier_global(l_full, n_tlu_ref)

            k_tlu_ref = None

            if "k_calc" in df_tlu.columns:
                k_raw = np.interp(l_full, df_tlu["lambda"].values, df_tlu["k_calc"].values)

                k_tlu_ref = np.clip(k_raw, 1e-9, None)

            params_k8 = None

            if k_tlu_ref is not None:
                _, params_k8 = fit_k_global_8p(l_full, k_tlu_ref)

            if params_sell is not None:
                if params_k8 is None:
                    _k_candidates = [
                        np.array([0.5, -15.0, 0.1, -20.0, 1e-6, 5.0, 1.0, 2.0]),
                        np.array([8.0, -20.0, 0.5, -25.0, 1e-5, 4.0, 0.5, 2.0]),
                        np.array([3.0, -18.0, 0.2, -22.0, 1e-4, 3.5, 0.8, 2.0]),
                        np.array([12.0, -22.0, 1.0, -28.0, 2e-5, 5.0, 1.5, 2.0]),
                        np.array([0.1, -30.0, 0.1, -30.0, 5e-4, 4.5, 0.3, 2.0]),
                    ]

                    _best_k_y = np.inf

                    _best_k_p = None

                    for _kp in _k_candidates:
                        _x_try = np.clip(np.concatenate([params_sell, _kp]), flat_bounds[:, 0], flat_bounds[:, 1])

                        _y_try = float(obj(_x_try))

                        if _y_try < _best_k_y:
                            _best_k_y = _y_try

                            _best_k_p = _kp

                    params_k8 = _best_k_p

                    self.logger.info(
                        f"  > Warm start: Sellmeier OK | k_8p best candidate RMSE = {np.sqrt(_best_k_y):.6f}"
                    )

                else:
                    self.logger.info("  > Warm start: Sellmeier OK | k_8p OK")

                x0_raw = np.concatenate([params_sell, params_k8])

                x0_clamped = np.clip(x0_raw, flat_bounds[:, 0], flat_bounds[:, 1])

                self.logger.info("  > Stage 0: L-BFGS-B polish from Phase 1 warm start...")

                res_s0 = scipy.optimize.minimize(
                    obj,
                    x0_clamped,
                    method="L-BFGS-B",
                    bounds=list(zip(flat_bounds[:, 0], flat_bounds[:, 1])),
                    options={"maxiter": 3000, "ftol": 1e-15, "gtol": 1e-10},
                )

                if np.isfinite(res_s0.fun) and res_s0.fun < 1e11:
                    x0_polished = res_s0.x

                    y0_polished = float(res_s0.fun)

                    self.logger.info(f"  > Stage 0 done: RMSE = {np.sqrt(y0_polished):.6f} ({res_s0.nit} iters)")

                else:
                    y_raw = float(obj(x0_clamped))

                    if np.isfinite(y_raw) and y_raw < 1e11:
                        x0_polished = x0_clamped

                        y0_polished = y_raw

                        self.logger.info(
                            f"  > Stage 0 polish rejected, using raw warm start: RMSE = {np.sqrt(y0_polished):.6f}"
                        )

                    else:
                        self.logger.info("  > Stage 0: warm start lands in rejected region, PGlobal starts cold")

            else:
                self.logger.info("  > Warm start: Sellmeier fit failed, PGlobal starts cold")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _e_ws:
            self.logger.warning(f"  > Warm start exception: {_e_ws}  PGlobal starts cold")

        pg_bounds = flat_bounds.copy()

        if x0_polished is not None and np.isfinite(y0_polished):
            self.logger.info(f"  > PGlobal: full bounds | warm seed RMSE = {np.sqrt(y0_polished):.6f}")

        else:
            self.logger.info("  > PGlobal: full bounds | cold start")

        pg_conf = PGlobalConfig.for_dimension(13).with_overrides(
            max_feval=150000,
            max_time=480.0,
            max_active_clusters=100,
            n_samples_per_iter=3000,
            convergence_tol=1e-10,
        )
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))

        overrides = getattr(c, "phase2_pglobal_overrides", None) or {}

        for k, v in overrides.items():
            if hasattr(pg_conf, k):
                pg_conf = pg_conf.with_overrides(**{k: v})

        self.logger.info(
            f"  > PGlobal: Sobol+Clustering | =0.008 | pop={pg_conf.n_samples_per_iter} | max_feval={pg_conf.max_feval}"
        )

        self.logger.info("-" * 65)

        optimizer = PGlobalOptimizerINDEX(
            obj, pg_bounds, config=pg_conf, log_clues=log_clues, stop_event=self._stop_event
        )

        best_y_so_far = y0_polished if np.isfinite(y0_polished) else float("inf")

        best_x_so_far = x0_polished.copy() if x0_polished is not None else None

        pg_callback = IRPGlobalCallback(
            self, optimizer, obj, c, l_full, thickness, n_sub_full, "IR Global Search", True
        )

        if np.isfinite(best_y_so_far) and best_x_so_far is not None:
            from certus_physics import Sample as _Sample

            pg_callback(_Sample(x=best_x_so_far, y=best_y_so_far))

        res_pg = optimizer.optimize(callback=pg_callback, x0=x0_polished)

        if res_pg is None or (np.isfinite(y0_polished) and y0_polished < getattr(res_pg, "y", np.inf)):
            if x0_polished is not None and np.isfinite(y0_polished):
                self.logger.info("  > PGlobal did not improve on Stage 0  keeping Stage 0 result")

                res_pg = _Sample(x=x0_polished, y=y0_polished)

            elif res_pg is None:
                self.error.emit("IR optimization returned no feasible solution.")

                return None

        try:
            self.logger.info("  > Stage 2: final L-BFGS-B polish from PGlobal result...")

            _stage2_cb = IRStage2Callback(self, obj, c, l_full, thickness, n_sub_full)

            res_s2 = scipy.optimize.minimize(
                obj,
                res_pg.x,
                method="L-BFGS-B",
                bounds=list(zip(flat_bounds[:, 0], flat_bounds[:, 1])),
                options={"maxiter": 5000, "ftol": 1e-16, "gtol": 1e-11},
                callback=_stage2_cb,
            )

            if np.isfinite(res_s2.fun) and res_s2.fun < res_pg.y:

                _improv = (1.0 - res_s2.fun / res_pg.y) * 100.0

                self.logger.info(
                    f"  > Stage 2 polish: {np.sqrt(res_pg.y):.6f} -> {np.sqrt(res_s2.fun):.6f}"
                    f"  ({_improv:.1f} % MSE reduction, {res_s2.nit} iters)"
                )

                res_pg = _Sample(x=res_s2.x, y=float(res_s2.fun))

            else:
                self.logger.info("  > Stage 2 polish: no improvement (PGlobal already at local min)")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _e_s2:
            self.logger.warning(f"  > Stage 2 polish failed: {_e_s2}")

        self.best_mse = res_pg.y

        return res_pg, optimizer

    def _run_phase21_refinement(
        self,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        target_T: np.ndarray | None,
        k_spline_knots_lambda_um: np.ndarray | None,
        k_spline_knots_values: np.ndarray | None,
        p_opt_final: np.ndarray,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """Run final 90%T/10%R refinement when spline-k result is available."""

        if c.is_frosted_glass or target_T is None or k_spline_knots_lambda_um is None or k_spline_knots_values is None:
            return None, None, None

        w_T_orig = obj.weight_T

        w_R_orig = obj.weight_R

        obj.weight_T = 0.9

        obj.weight_R = 0.1

        obj.invalidate_cache()

        self.logger.info("PHASE 2.1: 90% T / 10% R refinement from Phase 2.3 result...")

        self.progress.emit(99, "Phase 2.1 (90% T)", None)

        try:
            n_k = len(k_spline_knots_lambda_um)

            log_k_21 = np.log(np.clip(k_spline_knots_values, 1e-9, obj.k_max_guard))

            x0_21 = np.concatenate([p_opt_final[:5].copy(), log_k_21])

            rel = 0.05

            ps = p_opt_final[:5]

            bounds_sell_21 = [
                (max(1.0, ps[0] * (1 - rel)), min(16.0, ps[0] * (1 + rel))),
                (max(0.0, ps[1] * (1 - rel)), min(20.0, ps[1] * (1 + rel))),
                (max(0.001, ps[2] * (1 - rel)), min(1.0, ps[2] * (1 + rel))),
                (max(0.0, ps[3] * (1 - rel)), min(20.0, ps[3] * (1 + rel))),
                (max(0.01, ps[4] * (1 - rel)), min(20.0, ps[4] * (1 + rel))),
            ]

            log_k_lo = np.log(1e-9)

            log_k_hi = np.log(max(obj.k_max_guard, 1e-9))

            bounds_21 = bounds_sell_21 + [(log_k_lo, log_k_hi)] * n_k

            phase23_T = Phase23SplineObjective(obj, k_spline_knots_lambda_um, obj.k_max_guard)

            _cb_21 = IRSplineCallback(
                self,
                obj,
                c,
                l_full,
                thickness,
                n_sub_full,
                "Phase 2.1 (90% T)",
                knot_lam=k_spline_knots_lambda_um,
                n_k=n_k,
                lk_lo=log_k_lo,
                lk_hi=log_k_hi,
            )

            r21 = scipy.optimize.minimize(
                phase23_T,
                x0_21,
                method="L-BFGS-B",
                jac=phase23_T.gradient,
                bounds=bounds_21,
                options={"maxiter": 1500, "ftol": 1e-14, "gtol": 1e-9},
                callback=_cb_21,
            )

            if np.isfinite(r21.fun) and r21.fun < 1e10:
                n_T = sellmeier_2poles_eval_nj(r21.x[:5], obj.wl_um)

                B_T = SplineBasisCache.get(k_spline_knots_lambda_um, obj.wl_um)

                k_T = np.exp(np.clip(B_T @ r21.x[5 : 5 + n_k], log_k_lo, log_k_hi))

                p_opt_T = np.concatenate([r21.x[:5], res_pg.x[5:]])

                self.logger.info(f"  Phase 2.1 done: RMSE_T = {np.sqrt(r21.fun):.6f}")

                return n_T, k_T, p_opt_T

            return None, None, None

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _e21:
            self.logger.warning(f"  Phase 2.1 failed: {_e21}")

            return None, None, None

        finally:
            obj.weight_T = w_T_orig

            obj.weight_R = w_R_orig

            obj.invalidate_cache()

    def _run_phase23_knot_reduction(
        self,
        *,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
        log_k_lo: float,
        log_k_hi: float,
        lam_min: float,
        lam_max: float,
        min_knot_dist_um: float,
        initial_best_n: int,
        initial_best_mse: float,
        initial_best_knot_lam: np.ndarray,
        initial_best_log_k: np.ndarray,
        initial_best_p_sell: np.ndarray,
        n_final: np.ndarray,
        k_final: np.ndarray,
        p_opt_final: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """Reduce spline knot count while constraining RMSE degradation."""

        RMSE_RATIO_MAX = 1.10

        MIN_KNOTS = 4

        best_n = int(initial_best_n)

        best_mse_red = float(initial_best_mse)

        best_knot_lam = initial_best_knot_lam.copy()

        best_log_k = initial_best_log_k.copy()

        best_p_sell = initial_best_p_sell.copy()

        n_out = n_final

        k_out = k_final

        p_out = p_opt_final

        while best_n > MIN_KNOTS:
            knot_lam_try, log_k_try = _merge_closest_knot_pair(best_knot_lam, best_log_k)

            knot_lam_try = _ensure_strictly_increasing(knot_lam_try, min_gap=1e-9)

            n_k_try = len(knot_lam_try)

            rel = 0.10

            ps0 = best_p_sell

            bounds_sell_try = [
                (max(1.0, ps0[0] * (1 - rel)), min(16.0, ps0[0] * (1 + rel))),
                (max(0.0, ps0[1] * (1 - rel)), min(20.0, ps0[1] * (1 + rel))),
                (max(0.001, ps0[2] * (1 - rel)), min(1.0, ps0[2] * (1 + rel))),
                (max(0.0, ps0[3] * (1 - rel)), min(20.0, ps0[3] * (1 + rel))),
                (max(0.01, ps0[4] * (1 - rel)), min(20.0, ps0[4] * (1 + rel))),
            ]

            bounds_log_k_try = [(log_k_lo, log_k_hi)] * n_k_try

            x0_p1_try = np.concatenate([best_p_sell, log_k_try])

            bounds_p1_try = bounds_sell_try + bounds_log_k_try

            phase23_try = Phase23SplineObjective(obj, knot_lam_try, obj.k_max_guard)

            t0_red = time.time()

            best_x_red = x0_p1_try.copy()

            best_fun_red = np.inf

            while True:
                _cb_red_p1 = IRSplineCallback(
                    self,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    f"Knot reduction {best_n}->{n_k_try}",
                    knot_lam=knot_lam_try,
                    n_k=n_k_try,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                    t0=t0_red,
                )

                r1_try = scipy.optimize.minimize(
                    phase23_try,
                    best_x_red,
                    method="L-BFGS-B",
                    jac=phase23_try.gradient,
                    bounds=bounds_p1_try,
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_red_p1,
                )

                if np.isfinite(r1_try.fun) and r1_try.fun < best_fun_red:
                    best_fun_red = r1_try.fun

                    best_x_red = r1_try.x.copy()

                if time.time() - t0_red >= 2.0:
                    break

            if not np.isfinite(best_fun_red) or best_fun_red > RMSE_RATIO_MAX**2 * best_mse_red:
                self.logger.info(
                    f"  Knot reduction: {best_n} -> {n_k_try} rejected (loss > 10% RMSE), keeping {best_n} knots"
                )

                break

            bounds_lam_try = [(lam_min + min_knot_dist_um, lam_max - min_knot_dist_um) for _ in range(n_k_try - 2)]

            x0_p2_try = np.concatenate([best_x_red[:5], best_x_red[5 : 5 + n_k_try], knot_lam_try[1:-1]])

            bounds_p2_try = bounds_sell_try + bounds_log_k_try + bounds_lam_try

            phase23_p2_try = Phase23Pass2SplineObjective(
                obj, n_k_try, lam_min, lam_max, obj.k_max_guard, min_knot_dist_um
            )

            _cb_red_p2 = IRSplineCallback(
                self,
                obj,
                c,
                l_full,
                thickness,
                n_sub_full,
                f"Knot reduction {best_n}->{n_k_try}",
                phase23_obj=phase23_p2_try,
                n_k=n_k_try,
                lk_lo=log_k_lo,
                lk_hi=log_k_hi,
            )

            try:
                r2_try = scipy.optimize.minimize(
                    phase23_p2_try,
                    x0_p2_try,
                    method="L-BFGS-B",
                    jac=phase23_p2_try.gradient,
                    bounds=bounds_p2_try,
                    options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_red_p2,
                )

                if np.isfinite(r2_try.fun) and r2_try.fun <= RMSE_RATIO_MAX**2 * best_mse_red:
                    best_mse_red = r2_try.fun

                    best_n = n_k_try

                    best_knot_lam = phase23_p2_try._knot_lam_from_x(r2_try.x)

                    best_log_k = r2_try.x[5 : 5 + n_k_try].copy()

                    best_p_sell = r2_try.x[:5].copy()

                    self.best_mse = r2_try.fun

                    n_out = sellmeier_2poles_eval_nj(r2_try.x[:5], obj.wl_um)

                    B_red = SplineBasisCache.get(best_knot_lam, obj.wl_um)

                    k_out = np.exp(np.clip(B_red @ best_log_k, log_k_lo, log_k_hi))

                    p_out = np.concatenate([r2_try.x[:5], res_pg.x[5:]])

                    self.logger.info(
                        f"  Knot reduction: {best_n + 1} -> {best_n} OK (RMSE {np.sqrt(best_mse_red):.6f}, < 10% loss)"
                    )

                else:
                    self.logger.info(
                        f"  Knot reduction: {best_n} -> {n_k_try} rejected (loss > 10% RMSE), keeping {best_n} knots"
                    )

                    break

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _ered:
                self.logger.warning(f"  Knot reduction failed: {_ered}, keeping {best_n} knots")

                break

        return n_out, k_out, p_out, best_knot_lam, best_log_k, best_mse_red

    def _run_phase23_spline_refinement(
        self,
        c: OptimizationConfig,
        obj: IRGlobalObjective,
        res_pg,
        l_full: np.ndarray,
        thickness: float,
        n_sub_full: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
        """Run Phase 2.3 spline refinement and return final n/k/model params and spline knots."""

        n_final = sellmeier_2poles_eval_nj(res_pg.x[:5], obj.wl_um)

        k_final = k_law_8p_eval(obj.wl_um, res_pg.x[5:])

        p_opt_final = res_pg.x

        k_spline_knots_lambda_um = None

        k_spline_knots_values = None

        rmse_before_23 = np.sqrt(res_pg.y)

        try:
            num_knots = 8

            knot_lam_um = _deduce_knots_from_k8p(obj.wl_um, res_pg.x[5:], num_knots=num_knots, min_knot_dist_um=0.05)

            k_at_knots = k_law_8p_eval(knot_lam_um, res_pg.x[5:])

            log_k_lo = np.log(1e-9)

            log_k_hi = np.log(max(obj.k_max_guard, 1e-9))

            log_k_knot0 = np.log(np.clip(k_at_knots, 1e-9, obj.k_max_guard))

            rel = 0.10

            p_sell0 = res_pg.x[:5].copy()

            bounds_sell = [
                (max(1.0, p_sell0[0] * (1 - rel)), min(16.0, p_sell0[0] * (1 + rel))),
                (max(0.0, p_sell0[1] * (1 - rel)), min(20.0, p_sell0[1] * (1 + rel))),
                (max(0.001, p_sell0[2] * (1 - rel)), min(1.0, p_sell0[2] * (1 + rel))),
                (max(0.0, p_sell0[3] * (1 - rel)), min(20.0, p_sell0[3] * (1 + rel))),
                (max(0.01, p_sell0[4] * (1 - rel)), min(20.0, p_sell0[4] * (1 + rel))),
            ]

            bounds_log_k = [(log_k_lo, log_k_hi)] * num_knots

            bounds_23 = bounds_sell + bounds_log_k

            x0_23 = np.concatenate([res_pg.x[:5].copy(), log_k_knot0])

            phase23_obj = Phase23SplineObjective(obj, knot_lam_um, obj.k_max_guard)

            self.logger.info("PHASE 2.3: spline k (log k) + n variable (tight bounds)...")

            self.progress.emit(98, "Phase 2.3 spline k", None)

            t0_p1 = time.time()

            best_x_23 = x0_23.copy()

            best_fun_23 = np.inf

            while True:
                _cb_p1 = IRSplineCallback(
                    self,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    "Phase 2.3 spline k",
                    knot_lam=knot_lam_um,
                    n_k=num_knots,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                    t0=t0_p1,
                )

                r23 = scipy.optimize.minimize(
                    phase23_obj,
                    best_x_23,
                    method="L-BFGS-B",
                    jac=phase23_obj.gradient,
                    bounds=bounds_23,
                    options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-9},
                    callback=_cb_p1,
                )

                if np.isfinite(r23.fun) and r23.fun < best_fun_23:
                    best_fun_23 = r23.fun

                    best_x_23 = r23.x.copy()

                elapsed_p1 = time.time() - t0_p1

                if elapsed_p1 >= 2.0:
                    break

            r23 = type("_R23", (), {"fun": best_fun_23, "x": best_x_23})()

            if np.isfinite(r23.fun) and r23.fun < 1e10:
                self.best_mse = r23.fun

                n_final = sellmeier_2poles_eval_nj(r23.x[:5], obj.wl_um)

                B = SplineBasisCache.get(knot_lam_um, obj.wl_um)

                log_k = B @ r23.x[5 : 5 + num_knots]

                k_final = np.exp(np.clip(log_k, log_k_lo, log_k_hi))

                p_opt_final = np.concatenate([r23.x[:5], res_pg.x[5:]])

                k_spline_knots_lambda_um = knot_lam_um.copy()

                k_spline_knots_values = np.exp(np.clip(r23.x[5 : 5 + num_knots], log_k_lo, log_k_hi))

                self.logger.info(
                    f"  Phase 2.3 Pass 1 done: RMSE {np.sqrt(r23.fun):.6f} (before: {rmse_before_23:.6f}) [{elapsed_p1:.1f} s]"
                )

                min_knot_dist_um = 0.05

                lam_min = float(obj.wl_um.min())

                lam_max = float(obj.wl_um.max())

                bounds_lambda = [(lam_min + min_knot_dist_um, lam_max - min_knot_dist_um) for _ in range(num_knots - 2)]

                bounds_23_pass2 = bounds_sell + bounds_log_k + bounds_lambda

                lambda_internes0 = knot_lam_um[1:-1].copy()

                x0_pass2 = np.concatenate([r23.x[:5], r23.x[5 : 5 + num_knots], lambda_internes0])

                phase23_pass2 = Phase23Pass2SplineObjective(
                    obj, num_knots, lam_min, lam_max, obj.k_max_guard, min_knot_dist_um
                )

                self.logger.info("  Phase 2.3 Pass 2: knot positions + values...")

                self.progress.emit(99, "Phase 2.3 Pass 2", None)

                _cb_p2 = IRSplineCallback(
                    self,
                    obj,
                    c,
                    l_full,
                    thickness,
                    n_sub_full,
                    "Phase 2.3 Pass 2",
                    phase23_obj=phase23_pass2,
                    n_k=num_knots,
                    lk_lo=log_k_lo,
                    lk_hi=log_k_hi,
                )

                try:
                    r23p2 = scipy.optimize.minimize(
                        phase23_pass2,
                        x0_pass2,
                        method="L-BFGS-B",
                        jac=phase23_pass2.gradient,
                        bounds=bounds_23_pass2,
                        options={"maxiter": 2000, "ftol": 1e-14, "gtol": 1e-9},
                        callback=_cb_p2,
                    )

                    if np.isfinite(r23p2.fun) and r23p2.fun < 1e10 and r23p2.fun <= r23.fun:
                        self.best_mse = r23p2.fun

                        knot_lam_p2 = phase23_pass2._knot_lam_from_x(r23p2.x)

                        n_final = sellmeier_2poles_eval_nj(r23p2.x[:5], obj.wl_um)

                        B_p2 = SplineBasisCache.get(knot_lam_p2, obj.wl_um)

                        log_k_p2 = B_p2 @ r23p2.x[5 : 5 + num_knots]

                        k_final = np.exp(np.clip(log_k_p2, log_k_lo, log_k_hi))

                        p_opt_final = np.concatenate([r23p2.x[:5], res_pg.x[5:]])

                        k_spline_knots_lambda_um = knot_lam_p2.copy()

                        k_spline_knots_values = np.exp(np.clip(r23p2.x[5 : 5 + num_knots], log_k_lo, log_k_hi))

                        self.logger.info(f"  Phase 2.3 Pass 2 done: RMSE {np.sqrt(r23p2.fun):.6f}")

                    else:
                        self.logger.info("  Phase 2.3 Pass 2: no improvement, keeping Pass 1 result")

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _ep2:
                    self.logger.warning(f"  Phase 2.3 Pass 2 failed: {_ep2}, keeping Pass 1 result")

                n_final, k_final, p_opt_final, best_knot_lam, best_log_k, _ = self._run_phase23_knot_reduction(
                    c=c,
                    obj=obj,
                    res_pg=res_pg,
                    l_full=l_full,
                    thickness=thickness,
                    n_sub_full=n_sub_full,
                    log_k_lo=log_k_lo,
                    log_k_hi=log_k_hi,
                    lam_min=lam_min,
                    lam_max=lam_max,
                    min_knot_dist_um=min_knot_dist_um,
                    initial_best_n=num_knots,
                    initial_best_mse=self.best_mse,
                    initial_best_knot_lam=k_spline_knots_lambda_um,
                    initial_best_log_k=np.log(np.clip(k_spline_knots_values, 1e-9, obj.k_max_guard)),
                    initial_best_p_sell=p_opt_final[:5],
                    n_final=n_final,
                    k_final=k_final,
                    p_opt_final=p_opt_final,
                )
                k_spline_knots_lambda_um = best_knot_lam.copy()
                k_spline_knots_values = np.exp(np.clip(best_log_k, log_k_lo, log_k_hi))

            else:
                self.logger.warning("  Phase 2.3: no improvement, keeping 8p (k_8p) result")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as _e23:
            self.logger.warning(f"  Phase 2.3 failed: {_e23}")

        return n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values

    def run(self) -> None:

        try:

            start_time = time.time()

            c = self.config

            l_full, n_sub_full, target_T, target_R, df_tlu, n_tlu_ref, obj, thickness = self._prepare_ir_phase2_inputs()

            stage02 = self._run_ir_stage0_to_stage2(
                c,
                l_full,
                n_sub_full,
                df_tlu,
                n_tlu_ref,
                obj,
                thickness,
            )
            if stage02 is None:
                return
            res_pg, optimizer = stage02

            duration = time.time() - start_time

            rmse_final = np.sqrt(res_pg.y)

            self.logger.info("-" * 65)

            self.logger.info(f"PHASE 2 SUCCESSFUL ({duration:.1f} s)")

            self.logger.info(f"  > Final IR RMSE: {rmse_final:.6f}")

            self.logger.info(f"  > Total Evals: {optimizer.n_evals}")

            self.logger.info("-" * 65)

            # ---------- Phase 2 flow ----------

            # Stage 0: warm start (Sellmeier + k_8p from Phase 1) + L-BFGS-B polish

            # Stage 1: PGlobal global search (13 params: Sellmeier 5p + k 8p)

            # Stage 2: L-BFGS-B polish from PGlobal result

            # Phase 2.3: replace k_8p by spline in log(k); n stays Sellmeier with tight bounds

            #   Pass 1: optimize p_sell + log_k at fixed knot positions (210 s)

            #   Pass 2: optimize knot positions + values

            #   Knot reduction: try N-1, N-2, ... knots while RMSE loss < 10%

            # Phase 2.1 (last): 90% T / 10% R refinement from Phase 2.3 result (spline + Sellmeier)

            # ----------

            n_final, k_final, p_opt_final, k_spline_knots_lambda_um, k_spline_knots_values = (
                self._run_phase23_spline_refinement(
                    c,
                    obj,
                    res_pg,
                    l_full,
                    thickness,
                    n_sub_full,
                )
            )

            n_T, k_T, p_opt_T = self._run_phase21_refinement(
                c,
                obj,
                target_T,
                k_spline_knots_lambda_um,
                k_spline_knots_values,
                p_opt_final,
                res_pg,
                l_full,
                thickness,
                n_sub_full,
            )

            # Package results; delta_n / delta_k = gap between 50-50 and 90% T curves

            results = self._package_results(
                n_final,
                k_final,
                thickness,
                l_full,
                p_opt_final,
                n_T,
                k_T,
                p_opt_T,
                k_spline_knots_lambda_um=k_spline_knots_lambda_um,
                k_spline_knots_values=k_spline_knots_values,
            )

            results.execution_time = duration  # Phase 2 total duration

            self.progress.emit(100, "Done (IR Refined)", None)

            self.finished.emit(results)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"IR Global optimization error: {e}", exc_info=True)

            self.error.emit(str(e))

    def _package_results(
        self,
        n,
        k,
        thickness,
        l_full,
        p_opt,
        n_T=None,
        k_T=None,
        p_T=None,
        k_spline_knots_lambda_um=None,
        k_spline_knots_values=None,
    ) -> Any:

        c = self.config

        sub_id = SUBSTRATES[c.substrate]["id"]

        n_sub = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)

        Rc, Tc, Ts = _compute_RT_from_config(c, l_full, n, k, thickness, n_sub)

        with np.errstate(divide="ignore", invalid="ignore"):
            T_s_safe = np.where(Ts > 1e-9, Ts, 1.0)

            T_norm = Tc / T_s_safe

            R_norm = Rc / T_s_safe

        df = pd.DataFrame(
            {
                "lambda": l_full,
                "n_calc": n,
                "k_calc": k,
                "T_calc (%)": Tc * 100,
                "T_norm_calc (%)": T_norm * 100,
                "R_calc (%)": Rc * 100,
                "R_norm_calc (%)": R_norm * 100,
            }
        )

        if "T" in c.target_data.columns:
            df["T_target"] = c.target_data["T"].to_numpy()

        if "R" in c.target_data.columns:
            df["R_target"] = c.target_data["R"].to_numpy()

        if n_T is not None:
            df["n_fit_T_only"] = n_T

            df["k_fit_T_only"] = k_T

        # delta_n = 2 * |n_50 - n_T|, delta_k = 2 * |k_50 - k_T| (gap between 50-50 and 90% T curves)

        n_rt = n

        if n_T is not None:
            df["delta_n"] = 2.0 * np.abs(n_rt - n_T)

            df["delta_k"] = 2.0 * np.abs(k - k_T) if k_T is not None else 0.0

        else:
            df["delta_n"] = 0.0

            df["delta_k"] = 0.0

        results = OptimizationResults(
            config=c,
            optimal_thickness=thickness,
            final_mse=self.best_mse,
            df_results=df,
            tlu_params=None,
            optimization_stats={"method": "PGLOBAL Global Refinement (Sellmeier+k8p)", "final_cost": self.best_mse},
            execution_time=0.0,
            sellmeier_params=p_opt[:5],
        )

        results.k_8p_params = p_opt[5:]

        results.n_T, results.k_T, results.p_opt_T = n_T, k_T, p_T

        results.k_spline_knots_lambda_um = k_spline_knots_lambda_um

        results.k_spline_knots_values = k_spline_knots_values

        return results

def _compute_RT_from_config(c, l_full, n, k, thickness, n_sub) -> tuple:
    """

    Single source of truth for R/T calculation.

    Returns (Rc, Tc, Ts) where:

      - Rc, Tc: physical (absolute) reflection and transmission.

      - Ts: substrate transmission (for normalized form T/Ts, R/Ts when use_normalized).

    Branches: frosted_glass | absorbing_substrate | standard.

    """

    _k_sub = getattr(c, "k_sub_data", None)

    _D_sub = getattr(c, "substrate_thickness_nm", None)

    nan_arr = np.full_like(l_full, np.nan)

    if c.is_frosted_glass:
        Rc = calculate_single_interface_R(l_full, n, k, thickness, n_sub)

        return Rc, nan_arr, nan_arr

    elif getattr(c, "has_absorbing_substrate", False):
        Rc, Tc = calculate_RT_single_layer_absorbing_substrate_array(l_full, n, k, thickness, n_sub, _k_sub, _D_sub)

        Ts = calculate_bare_substrate_RT(l_full, n_sub, _k_sub, _D_sub)

        return Rc, Tc, Ts

    else:
        Rc, Tc = calculate_RT_single_layer_backside_array(l_full, n, k, thickness, n_sub)

        Ts = calculate_bare_substrate_RT(l_full, n_sub)

        return Rc, Tc, Ts

def _spectrum_visibility_target_traces(data_type: DataType, is_frosted_glass: bool) -> tuple[bool, bool]:
    """

    Indicates which T and R curves to display, aligned with TLUObjective

    and _update_spectrum_plot : T only if TRANSMISSION or BOTH (not frosted) ;

    R if REFLECTION, BOTH, or frosted substrate (R only).

    """

    show_t = (not is_frosted_glass) and data_type in (DataType.TRANSMISSION, DataType.BOTH)

    show_r = is_frosted_glass or data_type in (DataType.REFLECTION, DataType.BOTH)

    return show_t, show_r

def _index_live_spectrum_visibility(c: OptimizationConfig) -> tuple[bool, bool]:
    """Live visibility INDEX (TLU / IR) : same logic as targets used in the cost."""

    return _spectrum_visibility_target_traces(c.data_type, c.is_frosted_glass)

class Phase1Callback:
    def __init__(self, worker, max_evals) -> None:

        self.worker = worker

        self.max_evals = max_evals

        self._last_status_emit = 0.0

    def __call__(self, s) -> None:

        if self.worker.is_stopped:
            return

        if not np.isfinite(s.y):
            return

        improved = (not np.isfinite(self.worker.best_mse)) or (s.y < self.worker.best_mse)

        if improved:
            self.worker.best_mse = s.y

            self.worker.best_params = s.x.copy()

            rmse = np.sqrt(s.y)

            _tlu_ex = ""

            _o1 = getattr(self.worker, "_phase1_obj", None)

            if _o1 is None:
                _opt = getattr(self.worker, "_optimizer", None)

                if _opt is not None:
                    _o1 = getattr(_opt, "objective", None)

            if _o1 is not None:
                try:
                    _tlu_ex = " | " + _o1.format_diag_line(s.x)

                except (ValueError, TypeError, RuntimeError, AttributeError) as _e_tlu:
                    _tlu_ex = f" | diag_tlu_err={_e_tlu}"

            _k_inline = ""

            if _o1 is not None:
                try:
                    _k_inline = " | " + _o1.format_k_line(s.x)

                except (ValueError, TypeError, RuntimeError, AttributeError):
                    _k_inline = ""

            self.worker.logger.info(
                f"  Best RMSE: {rmse:.6f} | Evaluations: {self.worker._optimizer.n_evals} | Thickness: {s.x[0]:.2f} nm{_tlu_ex}{_k_inline}"
            )

            if _o1 is None:
                if not getattr(self.worker, "_warned_phase1_missing_obj", False):
                    self.worker.logger.warning(
                        "Phase1 TLU diag/k indisponible (ni _phase1_obj ni _optimizer.objective) — "
                        "exécutez CERTUS_INDEX.py à jour (ex. dossier 1904)."
                    )

                    self.worker._warned_phase1_missing_obj = True

            self.worker._try_active_update(s.x, s.y, force=True)

        now = time.time()

        if improved or (now - self._last_status_emit >= 2.0):
            self._last_status_emit = now

            progress = min(60, int(60 * self.worker._optimizer.n_evals / self.max_evals))

            self.worker.progress.emit(progress, "Global Search...", self.worker.best_mse)

class Phase2PolishCallback:
    def __init__(self, worker) -> None:

        self.worker = worker

        self.polish_iters = 0

    def __call__(self, xk) -> None:

        self.polish_iters += 1

        if self.worker.is_stopped:
            raise StopIteration

        prog_polish = min(75, 60 + int(15 * self.polish_iters / 200))

        self.worker.progress.emit(prog_polish, f"Polish {self.polish_iters}", None)

        self.worker._try_active_update(xk, self.worker.best_mse, force=False)

class SubsetOptimTask:
    def __init__(self, worker, wls, n_sub, target_T, target_R, exclude_range) -> None:

        self.worker = worker

        self.wls = wls

        self.n_sub = n_sub

        self.target_T = target_T

        self.target_R = target_R

        self.exclude_range = exclude_range

    def __call__(self, offset) -> Any:

        return self.worker._run_subset_optim(
            slice(offset, None, 3), self.wls, self.n_sub, self.target_T, self.target_R, self.exclude_range
        )

class OptimizationWorker(QObject):
    """Worker thread for optimization to keep UI responsive"""

    # Progress: (percentage, status_text)

    # Plus an optional trailing extra_info parameter for passing RMSE or live curves

    progress = pyqtSignal(int, str, object)

    finished = pyqtSignal(object)

    error = pyqtSignal(str)

    evals_update = pyqtSignal(int)

    curve_update = pyqtSignal(object)  # Best-so-far params for live plot

    def __init__(self, config: OptimizationConfig, logger=None) -> None:

        super().__init__()

        self.config = config

        self.best_mse = np.inf

        self.best_params = None

        self._stop_event = Event()

        self._optimizer: PGlobalOptimizerINDEX | None = None

        self.logger = logger or logging.getLogger("CertusIndex")

        self.last_plot_update_time = 0.0

        self.last_status_update_time = 0.0

        self.min_plot_interval = 1.0  # Max 1 FPS (User request)

        self.thickness_initial = config.fixed_thickness  # Seed if available

    def _try_active_update(self, params, mse, force=False) -> None:
        """

        Live trace refresh (throttle).

        Always emit the **best** known parameter set (`best_params`), not the current iteration:

        e.g. during L-BFGS-B polish, ``params`` might be a sub-optimal xk while ``mse`` is capped

        at the global best - the live plot must stay on the best-so-far.

        """

        now = time.time()

        should_update = False

        if force:
            # Even for improvements, respect min_plot_interval for refreshing the heavy plot

            if now - self.last_plot_update_time > self.min_plot_interval:
                should_update = True

        else:
            if now - self.last_plot_update_time > 5.0:
                should_update = True

        if should_update:
            # Strict filter: show if <= best known

            # Allow some floating point tolerance or strict inequality

            if mse <= self.best_mse:
                # Update best if strictly better (already done in main loop but good to track here too)

                if mse < self.best_mse:
                    self.best_mse = mse

                    self.best_params = np.asarray(params, dtype=np.float64).copy()

                # Live = always the curve of the best candidate to date (not arbitrary ``params``).

                if self.best_params is not None:
                    self.curve_update.emit(np.asarray(self.best_params, dtype=np.float64).copy())

                    self.last_plot_update_time = now

    def _emit_live_best_snapshot(self) -> None:
        """

        Push live trace on current ``best_params`` **without throttle**.

        Essential after L-BFGS-B / Nelder : the last polish ``callback`` might be from

        before the last iteration; otherwise the UI stays on the old best (e.g. PGLOBAL)

        while the log already shows the polish RMSE.

        """

        if self.best_params is not None:
            self.curve_update.emit(np.asarray(self.best_params, dtype=np.float64).copy())

    def _run_subset_optim(self, clues_slice, wls, n_sub, target_T, target_R, exclude_range) -> Any:


        c = self.config

        wls_sub = wls[clues_slice]

        n_sub_sub = n_sub[clues_slice]

        target_T_sub = target_T[clues_slice] if target_T is not None else None

        target_R_sub = target_R[clues_slice] if target_R is not None else None

        obj_sub = TLUObjective(
            wls_sub,
            target_T_sub,
            target_R_sub,
            n_sub_sub,
            c.data_type,
            (c.thickness_min, c.thickness_max),
            use_normalized=c.use_normalized,
            weight_T=c.weight_T,
            weight_R=c.weight_R,
            exclude_range=exclude_range,
            is_frosted_glass=c.is_frosted_glass,
        )

        res_sub = scipy.optimize.minimize(
            obj_sub,
            self.best_params,
            method="L-BFGS-B",
            jac=obj_sub.gradient,
            bounds=[(lb, ub) for lb, ub in obj_sub.get_bounds()],
            options={"ftol": SMALL_EPSILON, "gtol": SMALL_EPSILON, "maxiter": 500},
        )

        _bs = obj_sub.get_bounds()

        _lbs = _bs[:, 0]

        _ubs = _bs[:, 1]

        res_polish = scipy.optimize.minimize(
            obj_sub,
            res_sub.x,
            method="Nelder-Mead",
            options={"xatol": 1e-8, "fatol": SMALL_EPSILON, "maxiter": 300},
        )

        x_clip_s = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lbs, _ubs)

        mse_clip_s = float(obj_sub(x_clip_s))

        if float(res_sub.fun) <= mse_clip_s:
            return res_sub.x

        return x_clip_s

    def stop(self) -> None:

        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:

        return self._stop_event.is_set()

    def _finalize_if_stopped(self, params_list: list | None = None) -> bool:
        """Emit partial results and cleanup when stop was requested."""

        if not self.is_stopped:
            return False

        if self.best_params is not None:
            thickness = self.best_params[0]

            tlu_params = TLUParameters.from_array(self.best_params[1:7])

            results = self._package_results(thickness, tlu_params, params_list=params_list)

            self.finished.emit(results)

        self._cleanup()

        return True

    def _prepare_run_inputs(
        self,
        c: OptimizationConfig,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray | None,
        np.ndarray | None,
        tuple[float, float] | None,
        TLUObjective,
    ]:

        self.logger.info("=" * 80)

        self.logger.info("CERTUS INDEX - OPTIMIZATION STARTED")

        self.logger.info("=" * 80)

        _src = (getattr(c, "source_file", None) or "").strip()

        if _src:
            self.logger.info("[FILE] Measured Spectrum (input): %s", Path(_src).resolve())

        else:
            self.logger.warning("[FILE] Measured Spectrum: source path not provided")

        _subn = getattr(c, "substrate", "")

        if _subn == "Sapphire (Al2O3)":
            self.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) "
                "| k file: %s | k column in xlsx: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )

        elif _subn == "Silicon (Si)":
            _clues = get_resource_path("clues.xlsx")

            self.logger.info("[FILE] Substrate Si (n,k): %s", Path(_clues).resolve())

        if self.thickness_initial is None:
            self.thickness_initial = (c.thickness_min + c.thickness_max) / 2.0

        # Filter data - use lambda_max_fit if set (two-stage pipeline restricts TLU to UV-VIS)

        _lmf = getattr(c, "lambda_max_fit", None)

        effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))

        mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)

        wls = c.target_data.loc[mask, "lambda"].to_numpy()

        if len(wls) == 0:
            self.logger.error(
                "No spectral points in [%.1f, %.1f] nm found in the loaded data. "
                "If you are in IR only (lambda_min >= 2200), do not cut at 2200 nm; "
                "widen lambda_min towards UV or let the range cover < 2200 nm.",
                c.lambda_min,
                effective_lambda_max,
            )

            raise ValueError("Wavelength window empty for optimization (check min/max lambda or exclusion range).")

        self.logger.info(
            f"Wavelength range: {c.lambda_min:.1f} - {effective_lambda_max:.1f} nm"
            + (
                f" (TLU fit restricted from {c.lambda_max:.1f} nm)"
                if _lmf is not None and effective_lambda_max < c.lambda_max
                else ""
            )
        )

        self.logger.info(f"Number of data points: {len(wls)}")

        sub_id = SUBSTRATES[c.substrate]["id"]

        if c.n_sub_data is not None:
            l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

            n_sub = np.interp(wls, l_full, c.n_sub_data, left=c.n_sub_data[0], right=c.n_sub_data[-1]).astype(
                np.float64
            )

        else:
            n_sub = _get_substrate_n_array_index(sub_id, wls)

        self.logger.info(f"substrate: {c.substrate}")

        if c.is_frosted_glass:
            self.logger.info("Mode: Frosted Glass (Reflection only)")

        else:
            self.logger.info(f"Data type: {c.data_type.name}")

        target_T = None

        target_R = None

        if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
            if "T" in c.target_data.columns:
                target_T = c.target_data.loc[mask, "T"].to_numpy()

        if c.data_type in (DataType.REFLECTION, DataType.BOTH):
            if "R" in c.target_data.columns:
                target_R = c.target_data.loc[mask, "R"].to_numpy()

        # Filter valid values

        valid = np.isfinite(n_sub)

        if target_T is not None:
            valid &= np.isfinite(target_T)

        if target_R is not None:
            valid &= np.isfinite(target_R)

        wls = wls[valid]

        n_sub = n_sub[valid]

        if target_T is not None:
            target_T = target_T[valid]

        if target_R is not None:
            target_R = target_R[valid]

        exclude_range = None

        if c.exclude_min is not None and c.exclude_max is not None:
            exclude_range = (c.exclude_min, c.exclude_max)

        obj = TLUObjective(
            wls,
            target_T,
            target_R,
            n_sub,
            c.data_type,
            (c.thickness_min, c.thickness_max),
            use_normalized=c.use_normalized,
            weight_T=c.weight_T,
            weight_R=c.weight_R,
            exclude_range=exclude_range,
            is_frosted_glass=c.is_frosted_glass,
            has_absorbing_substrate=c.has_absorbing_substrate,
            k_sub_data=c.k_sub_data,
            substrate_thickness_nm=c.substrate_thickness_nm,
        )

        return wls, n_sub, target_T, target_R, exclude_range, obj

    def _run_phase5_final_optimization(self, obj: TLUObjective, params_list: list[np.ndarray]) -> None:
        """Run final full-grid refinement and update best solution if improved."""

        self.progress.emit(92, "Final ultimate optimization...", None)

        self.logger.info("\n--- PHASE 5: Final Ultimate Optimization (full grid) ---")

        try:
            if len(params_list) == 3:
                avg_params = np.mean(params_list, axis=0)

            else:
                avg_params = self.best_params

            _bf5 = obj.get_bounds()

            _lb5 = _bf5[:, 0]

            _ub5 = _bf5[:, 1]

            avg_params = clip_to_bounds(np.asarray(avg_params, dtype=np.float64).ravel(), _lb5, _ub5)

            # Phase 5a: L-BFGS-B with extreme precision

            res_final = scipy.optimize.minimize(
                obj,
                avg_params,
                method="L-BFGS-B",
                jac=obj.gradient,
                bounds=[(lb, ub) for lb, ub in obj.get_bounds()],
                options={"ftol": 1e-14, "gtol": 1e-14, "maxiter": 1000},
            )

            # Phase 5b: Nelder-Mead (no SciPy bounds) -> mandatory projection into the box.

            res_polish = scipy.optimize.minimize(
                obj,
                res_final.x,
                method="Nelder-Mead",
                options={"xatol": 1e-9, "fatol": 1e-14, "maxiter": 500},
            )

            x_nm_clip = clip_to_bounds(np.asarray(res_polish.x, dtype=np.float64).ravel(), _lb5, _ub5)

            mse_nm_clip = float(obj(x_nm_clip))

            if float(res_final.fun) <= mse_nm_clip:
                final_params, final_mse = res_final.x, float(res_final.fun)

            else:
                final_params, final_mse = x_nm_clip, mse_nm_clip

            if final_mse < self.best_mse:
                self.best_mse = final_mse

                self.best_params = final_params

                self.logger.info(f" Final optimization improved RMSE: {np.sqrt(final_mse):.6f}")

                self._emit_live_best_snapshot()

            else:
                self.logger.info(f" Final optimization complete (RMSE unchanged: {np.sqrt(self.best_mse):.6f})")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.warning(f"Final optimization failed: {e}")

    def _run_phase1_global_search(
        self,
        c: OptimizationConfig,
        obj: TLUObjective,
        wls: np.ndarray,
        target_T: np.ndarray | None,
        n_sub: np.ndarray,
    ) -> bool:
        """Run Phase 1 (PGLOBAL) and initialize best_params/best_mse.

        Returns True when execution should stop early (stop requested and finalized).
        """

        if c.high_precision:
            max_evals = 80000

            self.logger.info("High Precision Mode Enabled (80k evals)")

        else:
            max_evals = 20000

            self.logger.info("Standard Precision Mode (20k evals)")

        max_time = 240.0

        self.logger.info("\n--- PHASE 1: PGLOBAL Global Search ---")

        self.logger.info(f"Thickness range: {c.thickness_min:.1f} - {c.thickness_max:.1f} nm")

        self.logger.info(f"Max evaluations: {max_evals}")

        self.progress.emit(5, "Global Search...", None)

        pg_conf = PGlobalConfig.for_index(max_feval=max_evals, max_time=max_time)
        if getattr(c, "random_seed", None) is not None:
            pg_conf = pg_conf.with_overrides(random_seed=int(c.random_seed))

        # Constrain local search (limit evals). PGlobalConfig is frozen.
        pg_conf = pg_conf.replace(local_search_budget=1500)

        self._optimizer = PGlobalOptimizerINDEX(
            obj,
            obj.get_bounds(),
            config=pg_conf,
            log_clues=[2, 5],
            stop_event=self._stop_event,
        )

        phase1_cb = Phase1Callback(self, max_evals)

        self._phase1_obj = obj

        smart_x0 = estimate_initial_params(wls, target_T, n_sub)

        smart_x0[0] = float(self.thickness_initial)

        _bnds = obj.get_bounds()

        for _i in range(7):
            smart_x0[_i] = float(np.clip(smart_x0[_i], _bnds[_i, 0], _bnds[_i, 1]))

        self.logger.info(
            "TLU warm start | d=%.1f nm  Eg=%.3f eV  A=%.2f  E0=%.3f  C=%.3f  Eu=%.3f  eps_inf=%.3f",
            smart_x0[0],
            smart_x0[1],
            smart_x0[2],
            smart_x0[3],
            smart_x0[4],
            smart_x0[5],
            smart_x0[6],
        )

        try:
            self.logger.info("TLU diag [warm start] | %s", obj.format_diag_line(smart_x0))

        except (ValueError, TypeError, RuntimeError, AttributeError) as _e_d0:
            self.logger.debug("TLU diag warm skip: %s", _e_d0)

        try:
            self.logger.info("TLU k [warm start / Phase1] | %s", obj.format_k_line(smart_x0))

        except (ValueError, TypeError, RuntimeError, AttributeError) as _e_k0:
            self.logger.debug("TLU k warm skip: %s", _e_k0)

        try:
            _y_ws = float(obj(smart_x0))

            if np.isfinite(_y_ws):
                self.best_mse = _y_ws

                self.best_params = smart_x0.copy()

                self.logger.info(
                    "TLU warm-start preview | RMSE = %.6f (traces avant 1er lot PGlobal)",
                    float(np.sqrt(max(0.0, _y_ws))),
                )

                self._emit_live_best_snapshot()

        except (ValueError, TypeError, RuntimeError, AttributeError) as _e_ws:
            self.logger.debug("TLU warm-start preview skipped: %s", _e_ws)

        # No x0 injected into PGLOBAL; warm start remains diagnostics + UI baseline.
        best = self._optimizer.optimize(max_iter=30, callback=phase1_cb)

        if best:
            rmse_best = np.sqrt(best.y)

            self.logger.info(
                f" PGLOBAL Pass 1 complete | Final RMSE: {rmse_best:.6f} | Total evals: {self._optimizer.n_evals}"
            )

        else:
            self.logger.warning(" PGLOBAL Pass 1 did not find a solution")

        if self._finalize_if_stopped():
            return True

        if best:
            self.best_params = best.x

            self.best_mse = best.y

            self._emit_live_best_snapshot()

        else:
            # Prefer best_params captured by callback over mid-range smart init fallback.
            if self.best_params is not None and np.isfinite(self.best_mse):
                self.logger.info(
                    f"Using callback-captured best params as fallback "
                    f"(RMSE={np.sqrt(self.best_mse):.6f}, d={self.best_params[0]:.2f} nm)"
                )

                self._emit_live_best_snapshot()

            else:
                self.logger.info("Using Smart Initialization for fallback parameters...")

                smart_init = estimate_initial_params(wls, target_T, n_sub)

                smart_init[0] = (c.thickness_min + c.thickness_max) / 2

                self.best_params = smart_init

                self._emit_live_best_snapshot()

        return False

    def run(self) -> None:

        try:

            start_time = time.time()

            c = self.config

            wls, n_sub, target_T, target_R, exclude_range, obj = self._prepare_run_inputs(c)

            _setup_n_lo = float(N_MIN_LIMIT) + float(TLU_SOFT_EDGE_MARGIN)

            if getattr(obj, "_prior_transparent_low_k", False):
                _setup_n_lo = max(_setup_n_lo, float(TLU_PRIOR_TRANSPARENT_N_MIN_SOFT))

            self.logger.info(
                "TLU setup Phase1 | Eg_min(bounds)=%.4f eV | k_soft_ceiling=%.5g | prior_lame_claire(T)=%s | "
                "budget_logs_k_pen=%d | hν_max=%.4f eV | n_lo_soft=%.3f",
                float(obj.param_bounds[0, 0]),
                float(getattr(obj, "_k_soft_ceiling", float("nan"))),
                getattr(obj, "_prior_transparent_low_k", False),
                int(getattr(obj, "_tlu_explode_logs_left", 0)),
                float(np.max(HC_EV_NM / np.maximum(wls, 1.0))),
                _setup_n_lo,
            )

            # === Phase 1: PGLOBAL ===

            if self._run_phase1_global_search(c, obj, wls, target_T, n_sub):
                return

            # === Phase 2: L-BFGS-B Polish ===

            self.logger.info("\n--- PHASE 2: L-BFGS-B Local Polish ---")

            self.progress.emit(60, "Polish...", None)

            # Callback to update display during Polish

            phase2_cb = Phase2PolishCallback(self)

            res = scipy.optimize.minimize(
                obj,
                self.best_params,
                method="L-BFGS-B",
                jac=obj.gradient,
                bounds=[(lb, ub) for lb, ub in obj.get_bounds()],
                callback=phase2_cb,
                options={"ftol": SMALL_EPSILON, "gtol": SMALL_EPSILON, "maxiter": 2000},
            )

            self.evals_update.emit(obj.n_evals)

            if res.fun < self.best_mse:
                self.best_mse = res.fun

                self.best_params = res.x

                rmse_polish = np.sqrt(res.fun)

                self.logger.info(f" Polish complete | RMSE: {rmse_polish:.6f} | Evals: {obj.n_evals}")

                self._emit_live_best_snapshot()

            else:
                rmse_current = np.sqrt(self.best_mse)

                self.logger.info(f" Polish complete | RMSE: {rmse_current:.6f} (unchanged)")

            # === Phase 3: L-BFGS-B Local Polish (remplace Coordinate Descent) ===

            if not self.is_stopped:
                self.logger.info("\n--- PHASE 3: L-BFGS-B Local Polish ---")

                self.progress.emit(75, "Fine tuning...", None)

                try:
                    exclude_range_p3 = (c.exclude_min, c.exclude_max) if c.exclude_min is not None else None

                    obj_p3 = TLUObjective(
                        wls,
                        target_T,
                        target_R,
                        n_sub,
                        c.data_type,
                        (c.thickness_min, c.thickness_max),
                        use_normalized=c.use_normalized,
                        weight_T=c.weight_T,
                        weight_R=c.weight_R,
                        exclude_range=exclude_range_p3,
                        is_frosted_glass=c.is_frosted_glass,
                    )

                    x0_p3 = self.best_params.copy()

                    # Bounds +/-5% around current solution, intersected with TLU global bounds

                    _fb = obj_p3.get_bounds()

                    bounds_p3 = []

                    for _ip in range(7):
                        _v = float(x0_p3[_ip])

                        _lo = max(float(_fb[_ip, 0]), _v * 0.95)

                        _hi = min(float(_fb[_ip, 1]), _v * 1.05)

                        if _lo > _hi:
                            _lo, _hi = float(_fb[_ip, 0]), float(_fb[_ip, 1])

                        bounds_p3.append((_lo, _hi))

                    res_p3 = scipy.optimize.minimize(
                        obj_p3,
                        x0_p3,
                        method="L-BFGS-B",
                        jac=obj_p3.gradient,
                        bounds=bounds_p3,
                        options={
                            "ftol": 1e-14,
                            "gtol": 1e-10,
                            "maxiter": 500,
                        },
                    )

                    if res_p3.fun < self.best_mse:
                        self.best_mse = res_p3.fun

                        self.best_params = res_p3.x

                        self.logger.info(f" Polish improved RMSE: {np.sqrt(res_p3.fun):.6f}")

                        self._emit_live_best_snapshot()

                    else:
                        self.logger.info("Polish did not improve solution (converged).")

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                    self.logger.warning(f"Phase 3 polish failed: {e}")

            if self._finalize_if_stopped():
                return

            # === Phase 4: Residual Uncertainty (3-way Split) ===

            self.progress.emit(90, "Uncertainty (3-way split)...", None)

            # We perform 3 additional local optimizations on subsets of data

            # (mod 3 clues) to estimate sensitivity to sampling.

            # Delta_n = max deviation across all 3 pairs.

            params_list = []  # Will hold 3 param arrays (3-way split)

            if not self.is_stopped:
                try:
                    # os/sys : imports module (pas de import local ici : sinon UnboundLocalError sur os en tete de run())

                    from concurrent.futures import ThreadPoolExecutor

                    n_workers = min(3, get_safe_worker_count())

                    task_runner = SubsetOptimTask(self, wls, n_sub, target_T, target_R, exclude_range)

                    with ThreadPoolExecutor(max_workers=n_workers) as executor:
                        params_list = list(executor.map(task_runner, range(3)))

                    self.progress.emit(100, "Uncertainty calculation done.", None)

                    self.logger.info(" Residual uncertainty calculated (3-way split).")

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                    self.logger.warning(f"Residual uncertainty calc failed: {e}")

            # === Phase 5: Final Ultimate Optimization (full grid) ===

            if not self.is_stopped:
                self._run_phase5_final_optimization(obj, params_list)

            if self._finalize_if_stopped(params_list=params_list):
                return

            self.progress.emit(95, "Packaging results...", None)

            # Filet anti-Nelder hors bornes (ex. sous-spectres Phase 4) -> Eg ~ 0.03 eV dans le rapport.

            if self.best_params is not None:
                _b_fix = obj.get_bounds()

                _xp = clip_to_bounds(
                    np.asarray(self.best_params, dtype=np.float64).ravel(),
                    _b_fix[:, 0],
                    _b_fix[:, 1],
                )

                if float(np.max(np.abs(_xp - np.asarray(self.best_params, dtype=np.float64).ravel()))) > 1e-8:
                    self.logger.warning(
                        "TLU: best_params projetés dans les bornes avant bilan (Nelder ou moyenne sous-spectres)."
                    )

                    self.best_params = _xp

                    self.best_mse = float(obj(_xp))

            thickness_initial = getattr(self, "thickness_initial", None)

            if thickness_initial is None:
                if hasattr(self, "tlu_results"):
                    thickness_initial = self.tlu_results.optimal_thickness

                else:
                    thickness_initial = self.best_params[0]

                    self.logger.warning("OptimizationWorker: thickness_initial not set  variation will be 0.")

            thickness_optimized = self.best_params[0]

            thickness_variation = ((thickness_optimized - thickness_initial) / thickness_initial) * 100

            self.thickness_variation = thickness_variation

            tlu_params = TLUParameters.from_array(self.best_params[1:7])

            rmse_final = np.sqrt(self.best_mse)

            self.logger.info("\n OPTIMIZATION COMPLETE")

            self.logger.info(f"Final RMSE: {rmse_final:.6f}")

            self.logger.info(f"Initial thickness: {thickness_initial:.4f} nm")

            self.logger.info(f"Optimized thickness: {thickness_optimized:.4f} nm")

            self.logger.info(f"Thickness variation: {thickness_variation:+.2f}%")

            self.logger.info(
                f"TLU Parameters: Eg={tlu_params.Eg:.3f} eV, A={tlu_params.A:.3f}, E0={tlu_params.E0:.3f} eV"
            )

            self.logger.info("=" * 80)

            # Package results

            results = self._package_results(thickness_optimized, tlu_params, params_list=params_list)

            self.progress.emit(100, "Done", None)

            self._cleanup()

            self.execution_time = time.time() - start_time

            try:
                status_val = (
                    ValidationStatus.WARNING_DATA_NORMALIZED
                    if bool(getattr(c, "use_normalized", False))
                    else ValidationStatus.OK
                )
                warnings_list = (
                    ["Input data normalized before optimization."] if bool(getattr(c, "use_normalized", False)) else []
                )
                svc = IndexFitService(runner=lambda _cfg: results)
                svc_resp = svc.fit(
                    IndexFitRequest(
                        config=c,
                        source_paths=[str(getattr(c, "source_file", "") or "")],
                        seed=getattr(c, "random_seed", None),
                        app_id="CERTUS_INDEX",
                        app_version=__version__,
                        warnings=warnings_list,
                        status=status_val,
                    )
                )
                stats = dict(getattr(results, "optimization_stats", {}) or {})
                stats["run_manifest"] = svc_resp.manifest.to_dict()
                results.optimization_stats = stats
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as _e_manifest:
                self.logger.debug("IndexFitService manifest wiring skipped: %s", _e_manifest)

            self.finished.emit(results)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f" Optimization error: {e}")

            self.logger.error(traceback.format_exc())

            self._cleanup()

            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")

    def _cleanup(self) -> None:

        if self._optimizer:
            self._optimizer.cleanup()

            self._optimizer = None

    def _package_results(
        self,
        thickness: float,
        tlu_params: TLUParameters,
        params_list: list | None = None,
    ) -> OptimizationResults:
        """Package optimization results. params_list contains 3 param arrays for uncertainty."""

        c = self.config

        l_full = c.target_data["lambda"].to_numpy()

        E_full = HC_EV_NM / l_full

        if c.is_frosted_glass:
            n_sub = get_n_frosted_glass_array(l_full)

        else:
            sub_id = SUBSTRATES[c.substrate]["id"]

            n_sub = c.n_sub_data if c.n_sub_data is not None else _get_substrate_n_array_index(sub_id, l_full)

        eps2 = epsilon2_TLU_array(
            E_full,
            tlu_params.Eg,
            tlu_params.A,
            tlu_params.E0,
            tlu_params.C,
            tlu_params.Eu,
        )

        eps1 = epsilon1_TL_analytic(
            E_full,
            tlu_params.Eg,
            tlu_params.A,
            tlu_params.E0,
            tlu_params.C,
            tlu_params.eps_inf,
        )

        n_calc, k_calc, _ = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)

        # Use shared source of truth for R/T calculation

        R_calc, T_calc, T_sub = _compute_RT_from_config(c, l_full, n_calc, k_calc, thickness, n_sub)

        with np.errstate(divide="ignore", invalid="ignore"):
            T_sub_safe = np.where(T_sub > SMALL_EPSILON, T_sub, 1.0)

            T_norm_calc = np.where(T_sub > SMALL_EPSILON, T_calc / T_sub_safe, np.nan)

            T_norm_calc = np.maximum(T_norm_calc, 0.0)

            if c.is_frosted_glass:
                R_norm_calc = R_calc.copy()

            else:
                R_norm_calc = calculate_relative_R_normalization(R_calc, T_sub)

        # --- Residual Uncertainty Calculation (3-way split, max deviation) ---

        delta_n_res = np.zeros_like(l_full)

        delta_k_res = np.zeros_like(l_full)

        if params_list and len(params_list) >= 2:
            n_arrays = []

            k_arrays = []

            for p in params_list:
                tlu_sub = TLUParameters.from_array(p[1:7])

                e2_s = epsilon2_TLU_array(E_full, tlu_sub.Eg, tlu_sub.A, tlu_sub.E0, tlu_sub.C, tlu_sub.Eu)

                e1_s = epsilon1_TL_analytic(E_full, tlu_sub.Eg, tlu_sub.A, tlu_sub.E0, tlu_sub.C, tlu_sub.eps_inf)

                n_s, k_s, _ = epsilon_to_nk(e1_s, e2_s, 0.5, 15.0, 15.0)

                n_arrays.append(n_s)

                k_arrays.append(k_s)

            for i in range(len(n_arrays)):
                for j in range(i + 1, len(n_arrays)):
                    delta_n_res = np.maximum(delta_n_res, np.abs(n_arrays[i] - n_arrays[j]))

                    delta_k_res = np.maximum(delta_k_res, np.abs(k_arrays[i] - k_arrays[j]))

        df_data = {
            "lambda": l_full,
            "n_calc": n_calc,
            "k_calc": k_calc,
            "delta_n_res": delta_n_res,
            "delta_k_res": delta_k_res,
            "alpha_cm-1": 4.0 * PI * k_calc / (l_full * 1e-7),
            "T_calc (%)": T_calc * 100,
            "T_norm_calc (%)": T_norm_calc * 100,
            "R_calc (%)": R_calc * 100,
            "R_norm_calc (%)": R_norm_calc * 100,
        }

        if "T" in c.target_data.columns:
            df_data["T_target"] = c.target_data["T"].to_numpy()

        if "R" in c.target_data.columns:
            df_data["R_target"] = c.target_data["R"].to_numpy()

        df = pd.DataFrame(df_data)

        # --- RECALCULATE RMSE ON FINAL DATA ---

        weights_recalc = np.ones_like(l_full, dtype=np.float64)

        out_of_range = (l_full < c.lambda_min) | (l_full > c.lambda_max)

        weights_recalc[out_of_range] = 0.0

        if c.exclude_min is not None and c.exclude_max is not None:
            exc_mask = (l_full >= c.exclude_min) & (l_full <= c.exclude_max)

            weights_recalc[exc_mask] = 0.0

        lambda_max_fit = getattr(c, "lambda_max_fit", None)

        if lambda_max_fit is not None:
            weights_recalc[l_full > lambda_max_fit] = 0.0

        total_mse_recalc = 0.0

        total_weight_recalc = 0.0

        if "T" in c.target_data.columns and not c.is_frosted_glass:
            target_T = c.target_data["T"].to_numpy()

            val_T = T_norm_calc if c.use_normalized else T_calc

            mse_t, n_t = compute_mse_vectorized(val_T, target_T, weights_recalc)

            if n_t >= 5:
                total_mse_recalc += mse_t * c.weight_T

                total_weight_recalc += c.weight_T

        if "R" in c.target_data.columns:
            target_R = c.target_data["R"].to_numpy()

            val_R = R_norm_calc if c.use_normalized else R_calc

            mse_r, n_r = compute_mse_vectorized(val_R, target_R, weights_recalc)

            if n_r >= 5:
                total_mse_recalc += mse_r * c.weight_R

                total_weight_recalc += c.weight_R

        final_mse_recalc = self.best_mse

        if total_weight_recalc > 1e-9:
            final_mse_recalc = total_mse_recalc / total_weight_recalc

        # ``final_mse`` exposed to the UI / exports = same metric as the cost function (log-lambda weights, etc.),

        # i.e. ``self.best_mse``, to match the "Final RMSE" log lines. The uniform recalculation

        # above may differ (often lower) - we keep it for diagnostic purposes only.

        if np.isfinite(self.best_mse) and float(self.best_mse) < 1e99:
            final_mse_canonical = float(self.best_mse)

        else:
            final_mse_canonical = float(final_mse_recalc)

        stats = {
            "method": "PGLOBAL + L-BFGS-B + DeepRefine",
            "data_type": c.data_type.name,
            "substrate_mode": c.substrate_mode.name,
            "thickness_variation_pct": getattr(self, "thickness_variation", 0.0),
            "mse_uniform_grid_recalc": float(final_mse_recalc),
        }

        return OptimizationResults(
            config=c,
            optimal_thickness=thickness,
            final_mse=final_mse_canonical,
            df_results=df,
            tlu_params=tlu_params,
            optimization_stats=stats,
            execution_time=getattr(self, "execution_time", 0.0),
        )

class IndexBeamAnalysisWorker(QObject):
    """

    Worker for Beam Analysis (Index Determination).

    Scans thickness +/- 1nm and re-optimizes index parameters.

    """

    finished = pyqtSignal(list)

    progress = pyqtSignal(int, int)

    error = pyqtSignal(str)

    def __init__(
        self,
        start_params: np.ndarray,
        config: OptimizationConfig,  # Re-using config for data/weights/types
        scan_range_nm: float = 1.0,
        step_nm: float = 0.1,
    ) -> None:

        super().__init__()

        self.start_params = start_params

        self.config = config

        self.scan_range = scan_range_nm

        self.step = step_nm

        self.is_running = True

    def stop(self) -> None:

        self.is_running = False

    @pyqtSlot()
    def run(self) -> None:

        try:
            c = self.config

            # Prepare Data Args for Kernel (Same as OptimizationWorker setup)

            # Filter data

            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= c.lambda_max)

            wls = c.target_data.loc[mask, "lambda"].to_numpy()  # float64 default

            sub_id = SUBSTRATES[c.substrate]["id"]

            if c.n_sub_data is not None:
                l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

                n_sub = np.interp(wls, l_full, c.n_sub_data, left=c.n_sub_data[0], right=c.n_sub_data[-1]).astype(
                    np.float64
                )

            else:
                n_sub = _get_substrate_n_array_index(sub_id, wls)

            target_T = np.zeros_like(wls)

            target_R = np.zeros_like(wls)

            use_T = False

            use_R = False

            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()

                    use_T = True

            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()

                    use_R = True

            if not use_T and not use_R:
                self.error.emit("No valid target data for beam analysis.")

                return

            # Replace NaNs

            target_T = np.nan_to_num(target_T, nan=0.0)

            target_R = np.nan_to_num(target_R, nan=0.0)

            n_sub = np.nan_to_num(n_sub, nan=1.5)

            # --- Beam Analysis Scan (Factorized) ---

            self.error.emit("certus_thickness_scanner module is missing; Beam Analysis is currently disabled.")

            return

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(traceback.format_exc())

            self.error.emit(str(e))

# =============================================================================

# LOGGING SYSTEM - Using COMMON utilities

# =============================================================================

# QueueHandler and setup_gui_logger are imported from certus_core

# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# =============================================================================

# UI COMPONENTS SPECIFIC TO INDEX

# =============================================================================

class ResultRecapWidget(QWidget):
    """UX-1: Modern Dashboard for optimization results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl_head = QLabel("OPTIMIZATION RESULTS")
        lbl_head.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: 800; letter-spacing: 2px; font-size: 13px;"
        )
        layout.addWidget(lbl_head)

        # We will use FlowLayout if we had it, but a Grid is fine
        grid = QGridLayout()
        grid.setSpacing(12)

        self.card_d = CertusDashboardCard("Thickness", "layers", "nm")
        self.card_rmse = CertusDashboardCard("RMSE", "activity", "%")
        self.card_eg = CertusDashboardCard("Bandgap (Eg)", "sun", "eV")
        self.card_inf = CertusDashboardCard("Eps Inf", "circle", "")

        grid.addWidget(self.card_d, 0, 0)
        grid.addWidget(self.card_rmse, 0, 1)
        grid.addWidget(self.card_eg, 1, 0)
        grid.addWidget(self.card_inf, 1, 1)

        layout.addLayout(grid)

    def update_results(self, thickness, rmse, eg, eps_inf) -> None:
        # Thickness
        d_status = "success" if thickness > 1 else "warning"
        d_msg = "Physical range" if thickness > 1 else "Unusually thin"
        self.card_d.update_value(f"{thickness:.2f}", d_status, d_msg)

        # RMSE
        rmse_val = rmse * 100 if rmse < 1 else rmse
        r_status = "success" if rmse_val < 1.0 else "warning" if rmse_val < 3.0 else "danger"
        r_msg = "Excellent fit" if rmse_val < 1.0 else "Acceptable" if rmse_val < 3.0 else "High error"
        self.card_rmse.update_value(f"{rmse_val:.3f}", r_status, r_msg)

        # Gap
        eg_status = "info" if eg > 0 else "normal"
        self.card_eg.update_value(f"{eg:.2f}", eg_status, "Calculated")

        # Eps Inf
        inf_status = "normal" if eps_inf > 1.0 else "warning"
        self.card_inf.update_value(f"{eps_inf:.2f}", inf_status, "Dielectric background")

        self.setVisible(True)

class KLogAxisItem(pg.AxisItem):
    """Custom AxisItem to format log10(k) values as decimal linear strings without scientific notation"""

    def tickStrings(self, values, scale, _spacing) -> Any:


        strings = []

        for v in values:
            try:
                s = np.format_float_positional(10**v, precision=6, trim="-")

                strings.append(s)

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                strings.append("")

        return strings

# =============================================================================

# MAIN APPLICATION

# =============================================================================

# Session persistence for cost weights wT / wR (CERTUS-INDEX classic, not SPLINE)

_QS_INDEX_ORG = "CERTUS"

_QS_INDEX_APP = "INDEX"

_QS_INDEX_WEIGHT_T = "cost_weight_t"

_QS_INDEX_WEIGHT_R = "cost_weight_r"

class CertusIndexApp(CertusBaseApp):
    """Main CERTUS-INDEX Application"""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-INDEX"

    APP_TITLE = "Dielectric Index Characterization"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Apply theme before building UI

        self._apply_theme()

        self._build_ui()

        self._restore_index_weight_settings()

        self._wire_index_weight_persistence()

        self._persist_index_weight_settings()

        # INDEX-specific state

        self._worker: OptimizationWorker | None = None

        self._thread: QThread | None = None

        self._worker2 = None

        self._thread2: QThread | None = None

        self._beam_worker: IndexBeamAnalysisWorker | None = None

        self._beam_thread: QThread | None = None

        self.target_data: pd.DataFrame | None = None

        self.data_type: DataType = DataType.TRANSMISSION

        self.substrate_mode: substrateMode = substrateMode.STANDARD

        self.exclude_region = None

        self.latest_results: OptimizationResults | None = None

        self.source_file_path = ""

        self.optimization_running = False

        self._executor = None

        self._vb_k = None

        # Convergence tracking data

        self.mse_data = {"iterations": [], "errors": []}

        self._last_progress_ui_update = 0.0

        self._last_phase_name = ""

        # Finalize (starts timers, triggers warmup)

        self._finalize_init()

    def _load_defaults(self) -> None:
        """Load default values for CERTUS-INDEX"""

        # Reset file selection

        self.source_file_path = ""

        self.target_data = None

        self.latest_results = None

        # Reset data type and substrate mode

        self.data_type = DataType.TRANSMISSION

        self.substrate_mode = substrateMode.STANDARD

        self.exclude_region = None

        self._vb_k = None

        # Reset UI elements to defaults

        if hasattr(self, "cb_data_type"):
            self.cb_data_type.setCurrentIndex(0)  # Transmission

        if hasattr(self, "cb_substrate_mode"):
            self.cb_substrate_mode.setCurrentIndex(0)  # Standard

        if hasattr(self, "lbl_file"):
            self.lbl_file.setText("(no file selected)")

        if hasattr(self, "lbl_final_eq"):
            self.lbl_final_eq.setText("Run optimization to see final equations.")

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(False)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        if hasattr(self, "btn_copy_params"):
            self.btn_copy_params.setEnabled(False)

        if hasattr(self, "table_res"):
            self.table_res.clearContents()

            self.table_res.setRowCount(0)

            self.table_res.setColumnCount(0)

        if hasattr(self, "table_params"):
            self.table_params.clearContents()

            self.table_params.setRowCount(0)

            self.table_params.setColumnCount(2)

            self.table_params.setHorizontalHeaderLabels(["Parameter", "Value"])

        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)

        if hasattr(self, "recap_widget"):
            self.recap_widget.setVisible(False)

        # Reset convergence tracking

        self.mse_data = {"iterations": [], "errors": []}

        self.optimization_running = False

        if hasattr(self, "rb_standard"):
            self.rb_standard.setChecked(True)

        if hasattr(self, "_on_substrate_mode_changed"):
            self._on_substrate_mode_changed()

        if hasattr(self, "_persist_index_weight_settings"):
            self._persist_index_weight_settings()

    def _restore_index_weight_settings(self) -> None:
        """Reads wT / wR from QSettings (session)."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = QSettings(_QS_INDEX_ORG, _QS_INDEX_APP)

        self.sb_weight_T.blockSignals(True)

        self.sb_weight_R.blockSignals(True)

        try:
            wt = s.value(_QS_INDEX_WEIGHT_T)

            if wt is not None:
                self.sb_weight_T.setValue(float(wt))

            wr = s.value(_QS_INDEX_WEIGHT_R)

            if wr is not None:
                self.sb_weight_R.setValue(float(wr))

        finally:
            self.sb_weight_T.blockSignals(False)

            self.sb_weight_R.blockSignals(False)

    def _persist_index_weight_settings(self) -> None:
        """Saves wT / wR for the next launch."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = QSettings(_QS_INDEX_ORG, _QS_INDEX_APP)

        s.setValue(_QS_INDEX_WEIGHT_T, float(self.sb_weight_T.value()))

        s.setValue(_QS_INDEX_WEIGHT_R, float(self.sb_weight_R.value()))

    def _wire_index_weight_persistence(self) -> None:

        self.sb_weight_T.valueChanged.connect(self._persist_index_weight_settings)

        self.sb_weight_R.valueChanged.connect(self._persist_index_weight_settings)

    def _warmup_numba(self) -> None:
        """JIT precompilation"""

        try:
            wls = np.array([500.0, 600.0], dtype=np.float64)

            get_n_substrate_array_by_id(0, wls)

            get_n_frosted_glass_array(wls)

            n_test = np.array([1.5, 1.5])

            k_test = np.array([0.0, 0.0])


            calculate_RT_single_layer_backside_array(wls, n_test, k_test, 100.0, n_test)

            calculate_single_interface_R(wls, n_test, k_test, 100.0, n_test)

            calculate_bare_substrate_RT(wls, n_test)

            calculate_single_interface_R(wls, n_test)

            # Absorbing substrate kernels (sapphire / user k_sub)

            k_sub_test = np.array([1e-4, 1e-4])

            calculate_bare_substrate_RT(wls, n_test, k_sub_test, 1.0e6)

            calculate_bare_substrate_RT(wls, n_test, k_sub_test, 1.0e6)

            calculate_RT_single_layer_absorbing_substrate_array(wls, n_test, k_test, 100.0, n_test, k_sub_test, 1.0e6)

            # Warmup per-lambda kernels (scalar + batch)

            _optimize_point_kernel(
                1.5,
                0.0,
                500.0,
                0.9,
                0.1,
                1.0,
                1.0,
                1.5,
                0.92,
                0.08,
                100.0,
                True,
                True,
                True,
                False,
            )

            _optimize_all_points_batch(
                np.array([1.5, 1.5]),
                np.array([0.0, 0.0]),
                wls,
                np.array([0.9, 0.9]),
                np.array([0.1, 0.1]),
                1.0,
                1.0,
                n_test,
                np.array([0.92, 0.92]),
                np.array([0.08, 0.08]),
                100.0,
                True,
                True,
                True,
                False,
                np.array([False, False]),
            )

            self.lbl_status.setText("Ready (JIT Compiled)")

            self._on_numba_ready()  # Mark as ready

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.lbl_status.setText("JIT Init Error")

            self.logger.error(f" Numba warmup failed: {e}", exc_info=True)

    def _apply_theme(self) -> None:
        """Apply Certus theme"""

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}
            """,
            plots=[
                getattr(self, "plot_spectrum", None),
                getattr(self, "plot_nk", None),
                getattr(self, "plot_convergence", None),
            ],
        )

        # Update Live Curves Pens

        try:
            if hasattr(self, "_live_curve_T"):
                self._live_curve_T.setPen(color=CertusTheme.SECONDARY, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_R"):
                self._live_curve_R.setPen(color=CertusTheme.ACCENT, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_n"):
                self._live_curve_n.setPen(color=CertusTheme.PRIMARY, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_k"):
                self._live_curve_k.setPen(color=CertusTheme.DANGER, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "convergence_curve"):
                self.convergence_curve.setPen(color=CertusTheme.ERROR, width=2)

        except (AttributeError, RuntimeError) as e:
            # Non-critical: convergence curve may not exist

            logging.debug(f"Could not update convergence curve: {e}")

            pass

        # Update Target Curves Symbols

        if hasattr(self, "plot_spectrum"):
            try:
                for item in self.plot_spectrum.getPlotItem().listDataItems():
                    if item.name() == "T data":
                        item.setSymbolBrush(CertusTheme.SUCCESS)

                    elif item.name() == "R data":
                        item.setSymbolBrush(CertusTheme.DANGER)

            except (AttributeError, RuntimeError) as e:
                # Non-critical: item may not have name or setSymbolBrush

                logging.debug(f"Could not update target curve symbols: {e}")

                pass

    def _build_ui(self) -> None:
        """Build user interface"""

        # Main Splitter instead of HBoxLayout

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.setCentralWidget(self.main_splitter)

        # === LEFT SIDE CONTAINER (Pinned Header + Scroll) ===

        left_container = QWidget()

        left_container.setMinimumWidth(280)

        left_container_layout = QVBoxLayout(left_container)

        left_container_layout.setContentsMargins(0, 0, 0, 0)

        left_container_layout.setSpacing(0)

        # 1. Standard Header (Pinned)

        header_widget = create_header_logo_widget(
            "CERTUS INDEX",
            "Material Database & Analysis",
            logo_width=180,
            module_name="CERTUS_INDEX",
        )

        left_container_layout.addWidget(header_widget)

        # 2. Action Bar (Pinned)

        action_bar = create_top_actions_bar(
            self,
            self.save_config,
            self.load_config,
            export_func=None,
            help_func=lambda: open_documentation("CERTUS_INDEX"),
        )

        left_container_layout.addWidget(action_bar)

        # 3. Scroll Area

        left_scroll = QScrollArea()

        left_scroll.setWidgetResizable(True)

        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel = QWidget()

        left_layout = QVBoxLayout(left_panel)

        left_layout.setContentsMargins(10, 10, 10, 10)

        left_layout.setSpacing(15)

        left_scroll.setWidget(left_panel)

        left_container_layout.addWidget(left_scroll)

        # Add container to splitter

        self.main_splitter.addWidget(left_container)

        # === CONTROLS CONTENT ===

        left_layout.addWidget(self._create_input_group())

        left_layout.addWidget(self._create_substrate_group())

        left_layout.addWidget(self._create_config_group())

        left_layout.addStretch()

        self.recap_widget = ResultRecapWidget()

        left_layout.addWidget(self.recap_widget)

        # Tabs
        self.tabs = QTabWidget()
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Buttons (Run/Stop/Beam)
        self._add_main_control_buttons(left_layout)

        # Note: Bean Analysis button removed natively (Uncertainty tab dropped)

        # Note: Export button removed - auto-export is active

        self.plot_spectrum = CertusScientificPlot(
            self, "Transmission / Reflection Spectrum", "T/R (%)", "Wavelength (nm)"
        )

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_spectrum), "Spectrum")

        self.plot_nk = CertusScientificPlot(self, "Optical Constants", "Index", "Wavelength (nm)")

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_nk), "n & k")

        # --- Convergence tab (UX-3: live RMSE feedback) ---

        self.plot_convergence = CertusScientificPlot(self, "Convergence — RMSE vs Iteration", "RMSE", "Iteration")

        self.plot_convergence.setBackground(None)

        self.plot_convergence.plotItem.showGrid(x=True, y=True, alpha=0.15)

        # Two curves: current-iteration RMSE and best-so-far envelope
        self._conv_curve_current = self.plot_convergence.plot(
            [],
            [],
            pen=pg.mkPen(color=CertusTheme.TEXT_SUB, width=1, style=Qt.PenStyle.DotLine),
            name="Current RMSE",
        )
        self._conv_curve_best = self.plot_convergence.plot(
            [],
            [],
            pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2),
            name="Best RMSE",
        )

        # State arrays (reset at each run start)
        self._conv_iterations: list[int] = []
        self._conv_rmse_current: list[float] = []
        self._conv_rmse_best: list[float] = []

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_convergence), "Convergence ↘")

        # Final equations tab

        self.eq_tab = QWidget()

        self.eq_tab_layout = QVBoxLayout(self.eq_tab)

        self.eq_tab_layout.setContentsMargins(20, 20, 20, 20)

        self.eq_tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lbl_final_eq = QLabel("Run optimization to see final equations.")

        self.lbl_final_eq.setStyleSheet("font-size: 11pt; color: #1e293b;")

        self.lbl_final_eq.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.lbl_final_eq.setWordWrap(True)

        self.eq_tab_layout.addWidget(self.lbl_final_eq)

        # ADD BUTTON HERE

        self.btn_copy_eq = create_styled_button(" Copy Equations", variant="secondary")

        self.btn_copy_eq.setToolTip("Copy the analytical equations to the clipboard as text")

        self.btn_copy_eq.clicked.connect(self._copy_eq_to_clipboard)

        self.btn_copy_eq.setEnabled(False)

        self.btn_copy_eq.setFixedWidth(200)

        self.eq_tab_layout.addWidget(self.btn_copy_eq)

        self.tabs.addTab(self.eq_tab, "Final Equations")

        # Detach plot button

        plot_header = QWidget()

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(5, 5, 5, 5)

        detach_btn = QPushButton(" Detach Plot")

        detach_btn.setToolTip("Detach current plot to separate window")

        detach_btn.clicked.connect(self.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_header_layout.addStretch()

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.tabs)

        self.perf_tab = QWidget()

        perf_layout = QGridLayout(self.perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "2-Stage Hybrid Engine",
            "TLU (UV-VIS) + PCHIP Spline (IR)\nContinuous transition at 2500 nm without breaking",
            icon="",
        )

        c2 = FlashyCard(
            "Ultra-Wide Spectrum",
            "From 200 to 6000+ nm in robust mode\nLimits non-physical drift in the IR",
            icon="",
        )

        c3 = FlashyCard(
            "Accelerated Physics Core",
            "Vectorized Numba kernels\nMatrix computation approaching C/C++ speeds",
            icon="",
        )

        c4 = FlashyCard(
            "Usable n,k Identification",
            "Strict physical constraints + equation export\nStable results for lab/production use",
            icon="",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

        self.tabs.addTab(self.perf_tab, "Why CERTUS?")

        # Spectrum Tab (0): visible by default to see T/R and n,k after optimization.
        self.tabs.setCurrentIndex(0)

        # Add plot container instead of tabs directly
        self.right_splitter.addWidget(plot_container)

        self._create_status_bar()

        log_widget = self._build_log_container()
        self.right_splitter.addWidget(log_widget)
        self.right_splitter.setSizes([800, 250])

        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setSizes([350, 700])  # Initial ratio

    def _add_main_control_buttons(self, left_layout: QVBoxLayout) -> None:
        """Create and add main control buttons to the left panel."""
        self.btn_run = QPushButton("START OPTIMIZATION")
        self.btn_run.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setToolTip("Start the global optimization process.")
        self.btn_run.clicked.connect(self.run_optimization)
        left_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("STOP Calculation")
        self.btn_stop.setObjectName(OBJ.DANGER_BUTTON)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setToolTip("Stop the current optimization safely.")
        self.btn_stop.clicked.connect(self.stop_optimization)
        self.btn_stop.setEnabled(False)
        left_layout.addWidget(self.btn_stop)

        from certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)
        left_layout.addWidget(self.clear_btn)

        # --- Data tab: table + toolbar ---

        data_tab = QWidget()

        data_tab_layout = QVBoxLayout(data_tab)

        data_tab_layout.setContentsMargins(4, 4, 4, 4)

        data_tab_layout.setSpacing(4)

        # Toolbar row

        data_toolbar = QWidget()

        data_toolbar_layout = QHBoxLayout(data_toolbar)

        data_toolbar_layout.setContentsMargins(0, 0, 0, 0)

        data_toolbar_layout.setSpacing(6)

        self.btn_copy_nk = create_styled_button(" Copy n,k", variant="secondary")

        self.btn_copy_nk.setToolTip("Copy n and k values to clipboard (TSV format)")

        self.btn_copy_nk.clicked.connect(self._copy_nk_to_clipboard)

        self.btn_copy_nk.setEnabled(False)

        data_toolbar_layout.addWidget(self.btn_copy_nk)

        self.btn_copy_params = create_styled_button(" Copy Parameters", variant="secondary")

        self.btn_copy_params.setToolTip("Copy analytical parameters to clipboard")

        self.btn_copy_params.clicked.connect(self._copy_params_to_clipboard)

        self.btn_copy_params.setEnabled(False)

        data_toolbar_layout.addWidget(self.btn_copy_params)

        data_toolbar_layout.addStretch()

        data_tab_layout.addWidget(data_toolbar)

        # Tables row: Spectral Data (Left) + Model Parameters (Right)

        tables_container = QWidget()

        tables_layout = QHBoxLayout(tables_container)

        tables_layout.setContentsMargins(0, 0, 0, 0)

        tables_layout.setSpacing(10)

        # 1. Main spectral table

        self.table_res = ExcelTableWidget()

        tables_layout.addWidget(self.table_res, 3)  # Stretching 3:1

        # 2. Parameters table

        self.table_params = ExcelTableWidget()

        self.table_params.setColumnCount(2)

        self.table_params.setHorizontalHeaderLabels(["Parameter", "Value"])

        self.table_params.setFixedWidth(280)

        self.table_params.verticalHeader().setVisible(False)

        self.table_params.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        tables_layout.addWidget(self.table_params, 1)

        data_tab_layout.addWidget(tables_container)

        self.tabs.addTab(data_tab, "Data")

    def _build_log_container(self) -> QWidget:
        """Build log container with shared CertusLogPanel."""

        panel = CertusLogPanel(title="LOGS", visible=True)

        self.log_text = panel.log_text

        panel.copied.connect(functools.partial(self.lbl_status.setText, "Logs copied to clipboard!"))

        self._log_panel = panel

        return panel

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        copy_app_logs_to_clipboard(self)

        self.lbl_status.setText("Logs copied to clipboard!")

    def _create_input_group(self) -> Any:

        c = CertusCard("Input Data")

        l = c.body

        self.btn_load = QPushButton(" Load Spectrum File")

        self.btn_load.setToolTip(
            "Load a CSV/Excel file with Transmission and/or Reflectance data.\n"
            "Expected columns: lambda (nm), T (%), R (%)  or any subset."
        )

        self.btn_load.clicked.connect(self.load_file)

        l.addWidget(self.btn_load)

        self.lbl_file = QLabel("No file loaded")

        self.lbl_file.setStyleSheet(f"font-style: italic; color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        l.addWidget(self.lbl_file)

        # Label to display detected data type

        self.lbl_data_type = QLabel("")

        self.lbl_data_type.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 11px;")

        l.addWidget(self.lbl_data_type)

        # Normalization options

        h_norm = QHBoxLayout()

        self.chk_normalized = QCheckBox("Normalized (T/T_sub, R/T_sub)")

        self.chk_normalized.setChecked(True)

        self.chk_normalized.setToolTip(
            "If checked, the measured T and R are normalized by reference to the bare substrate.\n"
            "Uncheck for absolute transmittance/reflectance data."
        )

        h_norm.addWidget(self.chk_normalized)

        l.addLayout(h_norm)

        return c

    def _create_substrate_group(self) -> Any:
        """Create substrate selection group with frosted glass option"""

        c = CertusCard("substrate")

        l = c.body

        self.rb_standard = QRadioButton("Standard (transparent substrate)")

        self.rb_standard.setToolTip(
            "Use for transparent substrates (SiO2, BK7, D263T, B270i).\nBoth T and R data are used for fitting."
        )

        self.rb_frosted_glass = QRadioButton("Frosted Glass (infinite substrate, R only)")

        self.rb_frosted_glass.setToolTip(
            "Use for opaque / frosted glass substrates where only reflectance (R) is measured.\n"
            "T data is ignored in this mode."
        )

        self.rb_standard.setChecked(True)

        self.substrate_mode_group = QButtonGroup(self)

        self.substrate_mode_group.addButton(self.rb_standard, 0)

        self.substrate_mode_group.addButton(self.rb_frosted_glass, 1)

        l.addWidget(self.rb_standard)

        l.addWidget(self.rb_frosted_glass)

        # substrate ComboBox (always enabled now)

        h_sub = QHBoxLayout()

        h_sub.addWidget(QLabel("Material:"))

        self.cb_sub = QComboBox()

        self.cb_sub.addItems(["SiO2", "N-BK7", "D263T", "Al2O3", "B270i", "Si"])

        self.cb_sub.setToolTip(
            "substrate material. Determines the dispersion model used for n_substrate(\u03bb).\n"
            "Al2O3: n(\u03bb) via Sellmeier equation (materials DB). "
            "Absorbing mode uses sapphire fresnel.xlsx only for k(\u03bb).\n"
            "Si (Silicon): absorbing mode auto from clues.xlsx."
        )

        h_sub.addWidget(self.cb_sub)

        l.addLayout(h_sub)

        # Connection for mode change

        self.rb_frosted_glass.toggled.connect(self._on_substrate_mode_changed)

        self.rb_standard.toggled.connect(self._on_substrate_mode_changed)

        # Info label for frosted glass

        self.lbl_frosted_info = QLabel("i Frosted: measures R or Rnu (1 side), never R/Tnu")

        self.lbl_frosted_info.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-style: italic;")

        self.lbl_frosted_info.setVisible(False)

        l.addWidget(self.lbl_frosted_info)

        #  Absorbing substrate section

        self.chk_absorbing_sub = QCheckBox("Absorbent substrate (k = 0)")

        self.chk_absorbing_sub.setChecked(False)

        self.chk_absorbing_sub.setToolTip(
            "Enable if the substrate has a non-negligible k(\u03bb) coefficient.\n"
            "Al2O3: n(\u03bb) remains equation-based; k(\u03bb) is available only if "
            "sapphire fresnel.xlsx contains a k column."
        )

        l.addWidget(self.chk_absorbing_sub)

        self._absorbing_sub_widget = QWidget()

        abs_layout = QVBoxLayout(self._absorbing_sub_widget)

        abs_layout.setContentsMargins(12, 2, 0, 2)

        abs_layout.setSpacing(4)

        # k_sub CSV import row

        h_ksub = QHBoxLayout()

        self.btn_import_ksub = QPushButton("Import k_sub (CSV lambda,k)")

        self.btn_import_ksub.setFixedHeight(24)

        self.btn_import_ksub.setToolTip(
            "Import a 2-column CSV file with substrate extinction coefficient:\nColumn 1: lambda (nm) | Column 2: k_sub"
        )

        self.lbl_ksub_file = QLabel("(no files)")

        self.lbl_ksub_file.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        h_ksub.addWidget(self.btn_import_ksub)

        h_ksub.addWidget(self.lbl_ksub_file, 1)

        abs_layout.addLayout(h_ksub)

        # substrate thickness row

        h_dthick = QHBoxLayout()

        h_dthick.addWidget(QLabel("Thickness sub. (mm):"))

        self.sb_sub_thickness_mm = QDoubleSpinBox()

        self.sb_sub_thickness_mm.setRange(0.0, 100.0)  # 0 = transparent substrate (k=0 everywhere)

        self.sb_sub_thickness_mm.setValue(1.0)

        self.sb_sub_thickness_mm.setDecimals(3)

        self.sb_sub_thickness_mm.setSingleStep(0.1)

        self.sb_sub_thickness_mm.setFixedWidth(90)

        self.sb_sub_thickness_mm.setToolTip(
            "Physical thickness of the substrate (mm). Used to model inconsistent absorption.\n"
            "Set to 0 to ignore substrate absorption (equivalent to k_sub = 0 everywhere)."
        )

        h_dthick.addWidget(self.sb_sub_thickness_mm)

        h_dthick.addStretch()

        abs_layout.addLayout(h_dthick)

        self._absorbing_sub_widget.setVisible(False)

        l.addWidget(self._absorbing_sub_widget)

        # Internal storage for loaded k_sub data (raw, before interpolation)

        self._ksub_raw_wls: np.ndarray | None = None

        self._ksub_raw_k: np.ndarray | None = None

        self.chk_absorbing_sub.toggled.connect(self._on_absorbing_sub_toggled)

        self.btn_import_ksub.clicked.connect(self._on_import_ksub)

        # Auto-configure absorbing substrate when substrate selection changes

        self.cb_sub.currentIndexChanged.connect(self._on_substrate_changed)

        return c

    def _on_substrate_mode_changed(self) -> None:
        """Handle substrate mode change"""

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        # Show/hide info label

        self.lbl_frosted_info.setVisible(is_frosted_glass)

        # Frosted: disable norm, force reflection only

        if is_frosted_glass:
            # Uncheck and disable normalization

            self.chk_normalized.setChecked(False)

            self.chk_normalized.setEnabled(False)

            # Force reflection weights

            self.sb_weight_T.setValue(0.0)

            self.sb_weight_T.setEnabled(False)

            self.sb_weight_R.setValue(1.0)

        else:
            # Re-enable normalization

            self.chk_normalized.setEnabled(True)

            self.chk_normalized.setChecked(True)

            # Re-enable T weight

            self.sb_weight_T.setEnabled(True)

            self.sb_weight_T.setValue(1.0)

        self._persist_index_weight_settings()

    def _on_substrate_changed(self, index: int) -> None:
        """When Al2O3 or Si is selected: auto-configure absorbing mode (locked) if k(lambda) is available.

        Sapphire without k column in xlsx: transparent substrate only (no absorption).

        For any other substrate: restore manual mode."""

        sub_name = SUBSTRATE_LIST[index] if 0 <= index < len(SUBSTRATE_LIST) else ""

        is_sapphire = sub_name == "Sapphire (Al2O3)"

        is_silicon = sub_name == "Silicon (Si)"

        if is_sapphire:
            if _SAPPHIRE_WLS is not None:
                self._absorbing_sub_widget.setVisible(True)

                self.btn_import_ksub.setEnabled(False)

                self._ksub_raw_wls = _SAPPHIRE_WLS

                self._ksub_raw_k = _SAPPHIRE_K

                if _SAPPHIRE_FILE_HAS_K_COLUMN:
                    self.chk_absorbing_sub.setChecked(True)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(1.0)

                    self.sb_sub_thickness_mm.setEnabled(True)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx (auto, colonne k)")

                else:
                    self.chk_absorbing_sub.setChecked(False)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(0.0)

                    self.sb_sub_thickness_mm.setEnabled(False)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx  no k column: transparent only")

            else:
                # File not found  warn but don't block

                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx NOT FOUND")

        elif is_silicon:
            if _SILICON_WLS is not None:
                # Auto-activate and lock absorbing mode

                self.chk_absorbing_sub.setChecked(True)

                self.chk_absorbing_sub.setEnabled(False)

                self._absorbing_sub_widget.setVisible(True)

                self.sb_sub_thickness_mm.setValue(0.5)

                self.sb_sub_thickness_mm.setEnabled(True)

                # Show info; disable manual CSV import (data is built-in from clues.xlsx)

                self.lbl_ksub_file.setText("clues.xlsx -> Si-substrate (auto)")

                self.btn_import_ksub.setEnabled(False)

                # Store silicon k internally (will be interpolated to target grid in _on_run)

                self._ksub_raw_wls = _SILICON_WLS

                self._ksub_raw_k = _SILICON_K

            else:
                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("clues.xlsx Si-substrate NOT FOUND")

        else:
            # Other substrates: restore manual control

            self.chk_absorbing_sub.setChecked(False)

            self.chk_absorbing_sub.setEnabled(True)

            self._absorbing_sub_widget.setVisible(False)

            self.sb_sub_thickness_mm.setValue(1.0)

            self.sb_sub_thickness_mm.setEnabled(True)

            self.btn_import_ksub.setEnabled(True)

            if self._ksub_raw_wls is _SAPPHIRE_WLS or self._ksub_raw_wls is _SILICON_WLS:
                # Clear built-in data so other substrates start clean

                self._ksub_raw_wls = None

                self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(no files)")

    def _on_absorbing_sub_toggled(self, checked: bool) -> None:

        self._absorbing_sub_widget.setVisible(checked)

    def _on_import_ksub(self) -> None:

        path = certus_get_open_file_name(self, "Import k_sub substrate", "CSV (*.csv);;All (*)")

        if not path:
            return

        set_certus_last_dir(path)

        try:
            df_k = pd.read_csv(path, comment="#")

            # Accept first two numeric columns regardless of header names

            cols = df_k.select_dtypes(include=[np.number]).columns

            if len(cols) < 2:
                raise ValueError("The CSV must contain at least 2 numeric columns (lambda, k).")

            self._ksub_raw_wls = df_k[cols[0]].to_numpy(dtype=np.float64)

            self._ksub_raw_k = df_k[cols[1]].to_numpy(dtype=np.float64)

            self.lbl_ksub_file.setText(Path(path).name)

            self.logger.info(
                "[FILE] k_sub imported: %s (%d points)",
                Path(path).resolve(),
                len(self._ksub_raw_wls),
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            QMessageBox.warning(self, "k_sub Error", str(e))

            self._ksub_raw_wls = None

            self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(error)")

    def _auto_detect_from_file(self, filepath: str) -> None:
        """Auto-detect substrate from filename and pre-estimate thickness

        from the spectrum (oscillation counting). Updates GUI widgets accordingly."""

        fname = Path(filepath).name.lower()

        #  1. substrate detection from filename

        SUBSTRATE_KEYWORDS = {
            "SiO2": [
                "fusedsilica",
                "fused_silica",
                "silica_glass",
            ],
            "N-BK7": [
                "bk7",
                "nbk7",
                "n-bk7",
                "borosilicate",
                "glass",
                "bk",
                "pyrex",
            ],
            "D263T": ["d263", "d263t", "schott", "d263teco"],
            "Al2O3": [
                "sapphire",
                "saphir",
                "al2o3",
                "alumina",
                "alumine",
                "corundum",
                "ruby",
            ],
            "B270i": ["b270", "b270i", "soda", "sodalime"],
            "Si": [
                "silicon",
                "silicium",
                "si_sub",
                "wafer",
            ],
        }

        detected_substrate = None

        for sub_name, keywords in SUBSTRATE_KEYWORDS.items():
            for kw in keywords:
                if kw in fname:
                    detected_substrate = sub_name

                    break

            if detected_substrate:
                break

        if detected_substrate:
            idx = self.cb_sub.findText(detected_substrate)

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

                self.logger.info(f"   Auto-detected substrate: {detected_substrate}")

        #  2. Pre-estimate thickness from spectrum

        self._estimated_thickness_nm = None

        if not hasattr(self, "target_data") or self.target_data is None:
            return

        try:
            from scipy.signal import find_peaks

            wls = self.target_data["lambda"].to_numpy()

            # Use T if available, otherwise R

            if "T" in self.target_data.columns:
                signal = self.target_data["T"].to_numpy()

            elif "R" in self.target_data.columns:
                signal = self.target_data["R"].to_numpy()

            else:
                return

            valid = np.isfinite(signal) & np.isfinite(wls) & (wls > 0)

            wls = wls[valid]

            signal = signal[valid]

            if len(wls) < 16:
                return

            lmin, lmax = wls.min(), wls.max()

            # Approx n from detected substrate

            n_approx = 2.0

            sub_text = self.cb_sub.currentText() if hasattr(self, "cb_sub") else ""

            if "SiO2" in sub_text or "fused" in sub_text.lower():
                n_approx = 1.5

            elif "Al2O3" in sub_text or "sapphire" in sub_text.lower():
                n_approx = 2.1

            elif "Si" in sub_text and "SiO2" not in sub_text:
                n_approx = 3.5

            #  Method 1: FFT on uniformly sampled 1/lambda axis

            d_fft = None

            try:
                # Resample signal on uniform 1/lambda grid (Fabry-Perot fringes are periodic in 1/lambda)

                inv_wls = 1.0 / wls  # nm^-1, but wls in nm -> values ~1e-3

                inv_sorted_idx = np.argsort(inv_wls)

                inv_wls_s = inv_wls[inv_sorted_idx]

                sig_s = signal[inv_sorted_idx]

                N_fft = 4096

                inv_uniform = np.linspace(inv_wls_s[0], inv_wls_s[-1], N_fft)

                sig_uniform = np.interp(inv_uniform, inv_wls_s, sig_s)

                # Detrend

                sig_uniform -= np.polyval(np.polyfit(inv_uniform, sig_uniform, 3), inv_uniform)

                fft_amp = np.abs(np.fft.rfft(sig_uniform))

                freqs = np.fft.rfftfreq(N_fft, d=(inv_uniform[1] - inv_uniform[0]))  # in nm

                # Ignore DC and very low freqs (below 200 nm optical path)

                freq_mask = freqs > (1.0 / (2.0 * n_approx * lmax) * 0.5)

                if freq_mask.sum() > 2:
                    dominant_freq_idx = np.argmax(fft_amp[freq_mask])

                    dominant_freqs = freqs[freq_mask]

                    dominant_freq = dominant_freqs[dominant_freq_idx]  # in nm (= 2*n*d)

                    if dominant_freq > 0:
                        d_fft = dominant_freq / (2.0 * n_approx)

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e_fft:
                self.logger.debug(f"FFT thickness estimate failed: {e_fft}")

            #  Method 2: Peak/valley counting (robust to low-contrast fringes)

            d_peaks = None

            try:
                # Detrend signal with a polynomial fit to remove baseline drift

                poly_coef = np.polyfit(wls, signal, 3)

                sig_detrended = signal - np.polyval(poly_coef, wls)

                # Adaptive prominence: 10% of signal range

                sig_range = np.nanmax(sig_detrended) - np.nanmin(sig_detrended)

                prominence = max(sig_range * 0.10, 1e-4)

                min_dist_pts = max(3, len(wls) // 50)

                peaks, _ = find_peaks(sig_detrended, prominence=prominence, distance=min_dist_pts)

                valleys, _ = find_peaks(-sig_detrended, prominence=prominence, distance=min_dist_pts)

                n_extrema = len(peaks) + len(valleys)

                if n_extrema >= 2:
                    # Each fringe = 1 peak + 1 valley -> n_oscillations = n_extrema / 2

                    n_osc = n_extrema / 2.0

                    inv_range = 1.0 / lmin - 1.0 / lmax

                    if inv_range > 0:
                        d_peaks = n_osc / (2.0 * n_approx * inv_range)

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e_pk:
                self.logger.debug(f"Peak-count thickness estimate failed: {e_pk}")

            # -- Choose best estimate: FFT is primary (robust to noise & low contrast)

            d_estimate = None

            method_str = ""

            if d_fft is not None:
                d_estimate = d_fft

                if d_peaks is not None:
                    method_str = f"FFT, n\u2248{n_approx} (peaks check: {d_peaks:.0f} nm)"

                else:
                    method_str = f"FFT, n\u2248{n_approx}"

            elif d_peaks is not None:
                d_estimate = d_peaks

                method_str = f"peaks ({len(peaks)}up+{len(valleys)}dn), n\u2248{n_approx}"

            if d_estimate is not None and d_estimate > 5.0:
                d_estimate = max(10.0, d_estimate)

                self._estimated_thickness_nm = float(d_estimate)

                # Margins: -50% / +100%

                d_min = max(3.0, d_estimate * 0.50)

                d_max = d_estimate * 2.0

                # Round to clean values

                step = 50.0 if d_estimate > 500 else 10.0

                d_min = round(d_min / step) * step

                d_max = round(d_max / step) * step

                d_max = max(d_max, d_min + step * 2)

                # Clamp to physical spinbox ranges

                d_min = max(3.0, min(d_min, 49000.0))

                d_max = max(d_min + 10.0, min(d_max, 50000.0))

                self.sb_dmin.setValue(d_min)

                self.sb_dmax.setValue(d_max)

                self.logger.info(
                    f"   Estimated thickness: ~{d_estimate:.0f} nm "
                    f"({method_str}) "
                    f"-> range [{d_min:.0f}, {d_max:.0f}] nm"
                )

            else:
                self.logger.info("   No oscillations detected -> thickness not estimated")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.debug(f"Auto-detect thickness failed:{e}")

    def _create_config_group(self) -> Any:

        c = CertusCard("Configuration")

        l = QGridLayout()

        c.body.addLayout(l)

        l.setVerticalSpacing(8)

        l.addWidget(QLabel("Thickness (nm):"), 0, 0)

        h = QHBoxLayout()

        self.sb_dmin = QDoubleSpinBox()

        self.sb_dmin.setRange(3, 50000)

        self.sb_dmin.setValue(50)

        self.sb_dmin.setToolTip("Minimum film thickness to search (nm). Optimization will not go below this.")

        self.sb_dmax = QDoubleSpinBox()

        self.sb_dmax.setRange(3, 50000)

        self.sb_dmax.setValue(1000)

        self.sb_dmax.setToolTip("Maximum film thickness to search (nm). Optimization will not exceed this.")

        self.sb_dmin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_dmin.setDecimals(1)

        self.sb_dmax.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_dmax.setDecimals(1)

        h.addWidget(self.sb_dmin)

        h.addWidget(QLabel("-"))

        h.addWidget(self.sb_dmax)

        l.addLayout(h, 0, 1)

        l.addWidget(QLabel("lambda Range (nm):"), 1, 0)

        h2 = QHBoxLayout()

        self.sb_lmin = QDoubleSpinBox()

        self.sb_lmin.setRange(185, 5200)

        self.sb_lmin.setValue(300)

        self.sb_lmin.setToolTip("Start of the optimization wavelength range (nm).")

        self.sb_lmax = QDoubleSpinBox()

        self.sb_lmax.setRange(185, 5200)

        self.sb_lmax.setValue(900)

        self.sb_lmax.setToolTip("End of the optimization wavelength range (nm).")

        self.sb_lmin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_lmin.setDecimals(1)

        self.sb_lmax.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_lmax.setDecimals(1)

        h2.addWidget(self.sb_lmin)

        h2.addWidget(QLabel("-"))

        h2.addWidget(self.sb_lmax)

        l.addLayout(h2, 1, 1)

        # R/T Weights

        l.addWidget(QLabel("Weights (T/R):"), 2, 0)

        h_weights = QHBoxLayout()

        self.sb_weight_T = QDoubleSpinBox()

        self.sb_weight_T.setRange(0.0, 10.0)

        self.sb_weight_T.setValue(1.0)

        self.sb_weight_T.setDecimals(2)

        self.sb_weight_T.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_weight_T.setToolTip(
            "Relative weight given to Transmittance (T) in the cost function.\n"
            "Set to 0 to ignore T data during optimization."
        )

        self.sb_weight_R = QDoubleSpinBox()

        self.sb_weight_R.setRange(0.0, 10.0)

        self.sb_weight_R.setValue(1.0)

        self.sb_weight_R.setDecimals(2)

        self.sb_weight_R.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_weight_R.setToolTip(
            "Relative weight given to Reflectance (R) in the cost function.\n"
            "Set to 0 to ignore R data during optimization."
        )

        h_weights.addWidget(QLabel("T: "))

        h_weights.addWidget(self.sb_weight_T)

        h_weights.addWidget(QLabel("R: "))

        h_weights.addWidget(self.sb_weight_R)

        l.addLayout(h_weights, 2, 1)

        sep = QFrame()

        sep.setFrameShape(QFrame.Shape.HLine)

        sep.setStyleSheet(f"color: {CertusTheme.BORDER};")

        l.addWidget(sep, 3, 0, 1, 2)

        self.chk_exclude = QCheckBox("Exclude Data Range")

        self.chk_exclude.setToolTip(
            "Exclude a specific wavelength range from the cost function.\n"
            "Useful for masking saturated or noisy regions (e.g. laser line)."
        )

        self.chk_exclude.toggled.connect(self._toggle_exclude)

        l.addWidget(self.chk_exclude, 4, 0, 1, 2)

        h_ex = QHBoxLayout()

        self.sb_ex_min = QDoubleSpinBox()

        self.sb_ex_min.setRange(185, 5200)

        self.sb_ex_min.setValue(400)

        self.sb_ex_min.setToolTip("Start of the excluded wavelength range (nm).")

        self.sb_ex_max = QDoubleSpinBox()

        self.sb_ex_max.setRange(185, 5200)

        self.sb_ex_max.setValue(450)

        self.sb_ex_max.setToolTip("End of the excluded wavelength range (nm).")

        self.sb_ex_min.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_ex_min.setDecimals(1)

        self.sb_ex_max.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_ex_max.setDecimals(1)

        self.sb_ex_min.setEnabled(False)

        self.sb_ex_max.setEnabled(False)

        h_ex.addWidget(self.sb_ex_min)

        h_ex.addWidget(QLabel("-"))

        h_ex.addWidget(self.sb_ex_max)

        l.addLayout(h_ex, 5, 0, 1, 2)

        self.sb_ex_min.valueChanged.connect(self._update_plot_exclusion)

        self.sb_ex_max.valueChanged.connect(self._update_plot_exclusion)

        # OH- band exclusion checkbox

        self.chk_oh_band = QCheckBox("Remove OH⁻ band (E-band)")

        self.chk_oh_band.setToolTip(
            "Automatically excludes 1360-1460 nm range.\n"
            "This corresponds to the E-band, the 2nd harmonic (overtone)\n"
            "of the OH⁻ stretching vibration in silica optical fibers.\n"
            "This absorption band can interfere with optical measurements."
        )

        self.chk_oh_band.toggled.connect(self._toggle_oh_band)

        l.addWidget(self.chk_oh_band, 6, 0, 1, 2)

        # High Precision Toggle

        self.chk_high_precision = QCheckBox("High Precision (Slower)")

        self.chk_high_precision.setToolTip(
            "Increases global search evaluations from 20k to 80k.\n"
            "Use this if the solution seems stuck in a local minimum."
        )

        self.chk_high_precision.setChecked(False)  # Default to Standard

        l.addWidget(self.chk_high_precision, 7, 0, 1, 2)

        return c

    def _toggle_exclude(self, checked) -> None:

        self.sb_ex_min.setEnabled(checked and not self.chk_oh_band.isChecked())

        self.sb_ex_max.setEnabled(checked and not self.chk_oh_band.isChecked())

        # If exclude is unchecked, also uncheck OH band for coherence

        if not checked and self.chk_oh_band.isChecked():
            self.chk_oh_band.blockSignals(True)

            self.chk_oh_band.setChecked(False)

            self.chk_oh_band.blockSignals(False)

        self._update_plot_exclusion()

    def _update_plot_exclusion(self) -> None:

        if self.exclude_region is not None:
            try:
                self.plot_spectrum.removeItem(self.exclude_region)

            except (AttributeError, RuntimeError) as e:
                # Non-critical: exclude_region may not exist or already removed

                logging.debug(f"Could not remove exclude region: {e}")

                pass

            self.exclude_region = None

        if self.chk_exclude.isChecked():
            min_v = self.sb_ex_min.value()

            max_v = self.sb_ex_max.value()

            if max_v > min_v:
                self.exclude_region = pg.LinearRegionItem(
                    [min_v, max_v], brush=pg.mkBrush(255, 0, 0, 50), movable=False
                )

                self.plot_spectrum.addItem(self.exclude_region)

    def _toggle_oh_band(self, checked) -> None:
        """Toggle OH- band exclusion (1360-1460 nm E-band)."""

        if checked:
            # Set the exclude region to OH- band

            self.chk_exclude.setChecked(True)

            self.sb_ex_min.setValue(OH_BAND_MIN)

            self.sb_ex_max.setValue(OH_BAND_MAX)

            self.sb_ex_min.setEnabled(False)

            self.sb_ex_max.setEnabled(False)

        else:
            # Re-enable manual control

            self.sb_ex_min.setEnabled(self.chk_exclude.isChecked())

            self.sb_ex_max.setEnabled(self.chk_exclude.isChecked())

    def _create_status_bar(self) -> None:

        sb = QStatusBar()

        self.setStatusBar(sb)

        sb.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        container = QWidget()

        l = QHBoxLayout(container)

        l.setContentsMargins(10, 0, 10, 0)

        self.lbl_status = QLabel("Initializing...")

        self.lbl_dice = QLabel(" 0")

        self.lbl_dice.setStyleSheet(f"font-weight: bold; color: {CertusTheme.INFO_TEXT};")

        self.progress_widget = EnhancedProgressWidget()

        l.addWidget(self.lbl_status)

        l.addStretch()

        l.addWidget(self.lbl_dice)

        l.addWidget(self.progress_widget)

        sb.addPermanentWidget(container, 1)

        # 'Show Details' button for toggling logs

        self.toggle_details_btn = QPushButton("Show Details")

        self.toggle_details_btn.setToolTip("Toggle optimization details log display.")

        self.toggle_details_btn.setCheckable(True)

        self.toggle_details_btn.setFixedWidth(100)

        self.toggle_details_btn.setStyleSheet(f"""

            QPushButton {{ background-color: {CertusTheme.SECONDARY}; color: white; border: 1px solid {CertusTheme.BORDER}; border-radius: 3px; padding: 2px; font-size: 11px; font-weight: bold; }}

            QPushButton:checked {{ background-color: {CertusTheme.PRIMARY}; }}

            QPushButton:hover {{ background-color: {CertusTheme.SURFACE_HOVER}; color: {CertusTheme.PRIMARY}; }}

        """)

        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        sb.addPermanentWidget(self.toggle_details_btn)

        # --- Theme Switcher ---

        # Discreetly added to status bar

        self.btn_theme = CertusThemeToggle(self)

        sb.addPermanentWidget(self.btn_theme)

    def load_file(self, filepath=None) -> None:

        if filepath is None or isinstance(filepath, bool):
            from certus_ui import certus_get_open_file_name, DATA_FILE_FILTER

            filepath = certus_get_open_file_name(self, "Open", DATA_FILE_FILTER)

            if not filepath:
                return

        if not filepath:
            return

        try:
            from certus_data import load_spectrum_columns

            # Use the unified standard to load and clean (sort, normalize %, nm, etc.)

            res = load_spectrum_columns(filepath, column_roles={})

            df = res.dataframe

            # Automatic data type analysis (uses original headers preserved by column_roles={})

            self.data_type, parsed_data = analyze_loaded_data(df)

            # Rebuild DataFrame with standard named columns

            self.target_data = pd.DataFrame({"lambda": parsed_data["lambda"]})

            if parsed_data["T"] is not None:
                self.target_data["T"] = parsed_data["T"]

            if parsed_data["R"] is not None:
                self.target_data["R"] = parsed_data["R"]

            # Display filename and detected type

            fname = _update_loaded_file_label(self.lbl_file, filepath)

            self.source_file_path = filepath

            # FIX: Update Plot Title immediately on load

            _set_spectrum_plot_title(self.plot_spectrum, fname)

            # Log file loading details (absolute path for traceability)
            _log_loaded_spectrum_metadata(self.logger, filepath, df)

            # Display detected data type
            _display_detected_data_type(
                self.lbl_data_type,
                self.logger,
                self.data_type,
            )

            # Update lambda bounds
            lmin, lmax = _update_lambda_bounds_from_target_data(
                self.target_data,
                self.sb_lmin,
                self.sb_lmax,
                self.logger,
            )

            if not _is_qt_offscreen_mode():
                src_type = _source_type_label(self.data_type)

                n_rows = int(len(self.target_data))

                has_t = "T" in self.target_data.columns

                has_r = "R" in self.target_data.columns

                summary = build_summary_plain_text(
                    "CERTUS INDEX - Load Summary",
                    [
                        f"File: {Path(filepath).resolve()}",
                        "",
                        "General",
                        (f"Rows: {n_rows}", n_rows <= 0),
                        (f"Detected type: {src_type}", src_type == "Unknown"),
                        "",
                        "Data",
                        (f"Wavelength range: [{float(lmin):.1f}, {float(lmax):.1f}] nm", (float(lmax) <= float(lmin))),
                        f"Columns kept: {', '.join(self.target_data.columns.astype(str).tolist())}",
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if has_t else 'no'}",
                            not has_t and self.data_type != DataType.REFLECTION,
                        ),
                        (
                            f"Reflection column present: {'yes' if has_r else 'no'}",
                            not has_r and self.data_type != DataType.TRANSMISSION,
                        ),
                        (
                            "Potential unit conversion applied (% -> fraction): "
                            f"{'yes' if ((parsed_data['T'] is not None and np.nanmax(parsed_data['T']) > 1.5) or (parsed_data['R'] is not None and np.nanmax(parsed_data['R']) > 1.5)) else 'no'}",
                            False,
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX Load Summary", summary)

            # Display preview - clear() deletes everything

            # Force cleanup of internal structures

            self.plot_spectrum.plotItem.clear()

            try:
                # Clean internal structures

                self.plot_spectrum._tracked_curves = []

                self.plot_spectrum.curve_points = {}

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                # Ignore errors after clear()

                self.logger.warning(f"cleanup after clear() failed: {e}")

            wls = self.target_data["lambda"].values

            _is_frost = self.rb_frosted_glass.isChecked()

            _preview_t, _preview_r = _spectrum_visibility_target_traces(self.data_type, _is_frost)

            if _preview_t and "T" in self.target_data.columns:
                c_t = self.plot_spectrum.plot(
                    wls,
                    self.target_data["T"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=3,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_t, "T", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    logging.debug(f"Could not add tracked curve for T: {e}")

                    pass

            if _preview_r and "R" in self.target_data.columns:
                c_r = self.plot_spectrum.plot(
                    wls,
                    self.target_data["R"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=3,
                    symbolBrush=CertusTheme.DANGER,
                    name="R data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_r, "R", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    logging.debug(f"Could not add tracked curve for R: {e}")

                    pass

            self.tabs.setCurrentIndex(0)

            # --- DYNAMIC SMOOTHING WITH AUTO-CLOSING DIALOG ---
            self._apply_dynamic_ir_smoothing(
                wls=wls,
                preview_t=_preview_t,
                preview_r=_preview_r,
            )
            # --- END DYNAMIC SMOOTHING ---

            # Auto-detect substrate and pre-estimate thickness

            self._auto_detect_from_file(filepath)

            # Reset results

            self.latest_results = None

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            # Do not show error for tracking issues (non-critical)

            error_msg = str(e)

            if "add_tracked_curve" in error_msg.lower() or "tracking" in error_msg.lower():
                # Non-critical tracking error - log only

                self.logger.debug(f"Non-critical tracking error during file load: {e}")

            else:
                # Critical error - show user

                QMessageBox.critical(self, "Load Error", error_msg)

                self.logger.error("File load error", exc_info=True)

    def _apply_dynamic_ir_smoothing(
        self,
        *,
        wls: np.ndarray,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Apply optional IR denoising and let user keep raw vs smoothed traces."""
        try:
            from scipy.signal import savgol_filter

            raw_data = self.target_data.copy()
            smoothed_data = self.target_data.copy()
            smoothed_any = False
            cols_ir_smooth: list[str] = []

            if "T" in self.target_data.columns and preview_t:
                cols_ir_smooth.append("T")
            if "R" in self.target_data.columns and preview_r:
                cols_ir_smooth.append("R")

            for col in cols_ir_smooth:
                y = self.target_data[col].values
                y_smooth1 = savgol_filter(y, window_length=11, polyorder=2)
                y_smooth2 = savgol_filter(y, window_length=51, polyorder=2)
                y_final = np.copy(y)
                mask_transition = (wls >= 4000) & (wls <= 5200)
                mask_heavy = wls > 5200
                if np.any(mask_transition) or np.any(mask_heavy):
                    smoothed_any = True
                    if np.any(mask_transition):
                        weights = (wls[mask_transition] - 4000) / (5200 - 4000)
                        y_final[mask_transition] = (1 - weights) * y_smooth1[mask_transition] + weights * y_smooth2[
                            mask_transition
                        ]
                    if np.any(mask_heavy):
                        y_final[mask_heavy] = y_smooth2[mask_heavy]
                    smoothed_data[col] = y_final

            if not smoothed_any:
                return

            self._plot_raw_and_smoothed_preview(
                wls=wls,
                raw_data=raw_data,
                smoothed_data=smoothed_data,
                preview_t=preview_t,
                preview_r=preview_r,
            )
            keep_raw = self._ask_keep_raw_or_smoothed()
            self.target_data = raw_data if keep_raw else smoothed_data
            self._redraw_target_preview(wls, preview_t, preview_r)
        except ImportError:
            self.logger.warning("scipy.signal not available for smoothing")
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.warning(f"Failed to apply smoothing: {e}")

    def _ask_keep_raw_or_smoothed(self) -> bool:
        """Return True when user explicitly keeps raw traces."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Noise Filtering")
        msg_box.setText(
            "IR Noise detected in 4000-5200nm band.\n"
            "Do you want to keep the smoothed response or the raw response?\n\n"
            "If no selection is made, the smoothed response will be kept after 5 seconds."
        )
        btn_smooth = msg_box.addButton(
            "Keep Smoothed",
            QMessageBox.ButtonRole.AcceptRole,
        )
        btn_raw = msg_box.addButton("Keep Raw", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_smooth)

        timer = QTimer(msg_box)
        timer.timeout.connect(msg_box.accept)
        timer.start(5000)
        msg_box.exec()
        timer.stop()
        return msg_box.clickedButton() == btn_raw

    def _plot_raw_and_smoothed_preview(
        self,
        *,
        wls: np.ndarray,
        raw_data: pd.DataFrame,
        smoothed_data: pd.DataFrame,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Draw temporary raw+smoothed overlay before user selection."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()

        if preview_t and "T" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["T"].values * 100,
                pen=pg.mkPen(color=(40, 167, 69, 100), width=1),
                symbol="o",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(40, 167, 69, 100)),
                name="T data (Raw)",
            )
        if preview_r and "R" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["R"].values * 100,
                pen=pg.mkPen(color=(220, 53, 69, 100), width=1),
                symbol="s",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(220, 53, 69, 100)),
                name="R data (Raw)",
            )
        if preview_t and "T" in smoothed_data.columns:
            c_t_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["T"].values * 100,
                pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                name="T data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_t_sm, "T")
        if preview_r and "R" in smoothed_data.columns:
            c_r_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["R"].values * 100,
                pen=pg.mkPen(CertusTheme.DANGER, width=3),
                name="R data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_r_sm, "R")

    def _redraw_target_preview(self, wls: np.ndarray, preview_t: bool, preview_r: bool) -> None:
        """Redraw target traces from current `self.target_data`."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()
        if preview_t and "T" in self.target_data.columns:
            c_t = self.plot_spectrum.plot(
                wls,
                self.target_data["T"].values * 100,
                pen=None,
                symbol="o",
                symbolSize=3,
                symbolBrush=CertusTheme.SUCCESS,
                name="T data",
            )
            self._try_add_spectrum_tracked_curve(c_t, "T")
        if preview_r and "R" in self.target_data.columns:
            c_r = self.plot_spectrum.plot(
                wls,
                self.target_data["R"].values * 100,
                pen=None,
                symbol="s",
                symbolSize=3,
                symbolBrush=CertusTheme.DANGER,
                name="R data",
            )
            self._try_add_spectrum_tracked_curve(c_r, "R")

    def _try_add_spectrum_tracked_curve(self, curve, key: str) -> None:
        """Best-effort tracked-curve registration for spectrum traces."""
        try:
            self.plot_spectrum.add_tracked_curve(curve, key, "%")
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _clear_plot_tracking_state(self) -> None:
        """Best-effort cleanup of internal plot tracking structures."""
        try:
            self.plot_spectrum._tracked_curves = []
            self.plot_spectrum.curve_points = {}
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _reset_optimization_progress_state(self, config: OptimizationConfig) -> None:
        """Reset progress and convergence widgets before launching the worker thread."""

        self.progress_widget.start()

        self._total_iterations = 0

        self._best_rmse_display = float("inf")

        # Reset convergence chart (UX-3)
        self._conv_iterations.clear()
        self._conv_rmse_current.clear()
        self._conv_rmse_best.clear()
        if hasattr(self, "_conv_curve_current"):
            self._conv_curve_current.setData([], [])
        if hasattr(self, "_conv_curve_best"):
            self._conv_curve_best.setData([], [])

        # Real evaluation tracking for accurate ETA
        self._current_n_evals = 0
        self._max_evals = 80000 if config.high_precision else 20000

    def _configure_and_start_optimization_worker(self, config: OptimizationConfig) -> None:
        """Instantiate/connect the optimization worker and start the thread."""

        self._thread = QThread()

        # Two-stage TLU (lambda<=2200) + IR spline only if the user window contains lambda < 2200 nm.
        # Otherwise (e.g., fit only 3500-5200 nm): a single stage over the entire range avoids 0 points.
        use_two_stage = config.lambda_max > 2500.0 and config.lambda_min < 2200.0

        if use_two_stage:
            self.logger.info(
                "Spectrum > 2500 nm detected: launching automatic two-stage TLU + Spline pipeline "
                "(TLU band up to 2200 nm)."
            )
            config.lambda_max_fit = 2200.0
        elif config.lambda_max > 2500.0:
            self.logger.info(
                "Spectrum > 2500 nm but lambda_min >= 2200 nm: single-stage optimization on the "
                "selected range (no separate UV TLU band)."
            )
        else:
            self.logger.info("Spectrum <= 2500 nm: standard TLU-only pipeline.")

        self._index_tlu_live_ctx = self._make_index_tlu_live_ctx(config)
        self._worker = OptimizationWorker(config, logger=self.logger)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.evals_update.connect(self._on_evals_update)
        self._worker.curve_update.connect(self._on_curve_update)
        self._worker.error.connect(self._on_error)

        if use_two_stage:
            # Connect to custom handler for Phase 2
            self._worker.finished.connect(self._on_tlu_constrained_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
        else:
            self._worker.finished.connect(self._on_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

        def _abort_run_optimization(self, title: str, message: str, *, critical: bool = False) -> None:
            """Abort run setup with a user-visible message and reset primary buttons."""

            if critical:
                QMessageBox.critical(self, title, message)
            else:
                QMessageBox.warning(self, title, message)
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

        def _resolve_substrate_absorption_inputs(
            self,
            *,
            substrate_name: str,
            wls_target: np.ndarray,
        ) -> tuple[np.ndarray | None, float | None, np.ndarray | None] | None:
            """Resolve (k_sub, substrate_thickness_nm, n_sub_data) for the selected substrate mode.

            Returns ``None`` when setup must be aborted (message already shown to the user).
            """

            k_sub_interp: np.ndarray | None = None
            sub_thickness_nm: float | None = None
            n_sub_data: np.ndarray | None = None

            is_sapphire = substrate_name == "Sapphire (Al2O3)"
            is_silicon = substrate_name == "Silicon (Si)"

            if is_sapphire:
                thickness_mm = self.sb_sub_thickness_mm.value()
                if not _SAPPHIRE_FILE_HAS_K_COLUMN:
                    if thickness_mm > 0.0 or self.chk_absorbing_sub.isChecked():
                        self._abort_run_optimization(
                            "Sapphire without k column",
                            "example/sapphire fresnel.xlsx does not contain a k(lambda) column.\n"
                            "Absorbing substrate mode is unavailable.\n"
                            "Add a k column to the file, or use thickness = 0 mm.",
                            critical=True,
                        )
                        return None
                    self.logger.info(
                        "[SAPPHIRE] n(lambda) from Sellmeier equation; no k column -> transparent substrate (k=0)."
                    )
                    return None, None, None

                if thickness_mm > 0:
                    if _SAPPHIRE_WLS is None:
                        self._abort_run_optimization(
                            "Sapphire k source missing",
                            "example/sapphire fresnel.xlsx not found.\n"
                            "n(lambda) uses Sellmeier, but absorbing mode requires k(lambda) from file.",
                            critical=True,
                        )
                        return None
                    k_sub_interp = _get_sapphire_k_on_grid(wls_target)
                    if k_sub_interp is None or not np.all(np.isfinite(k_sub_interp)):
                        self._abort_run_optimization(
                            "Sapphire data invalid",
                            "example/sapphire fresnel.xlsx is present but invalid for k(lambda).\n"
                            "Calculation aborted to avoid drift on Al2O3.",
                            critical=True,
                        )
                        return None
                    sub_thickness_nm = thickness_mm * 1e6
                    self.logger.info(
                        f"[SAPPHIRE] Self-absorbent substrate: thickness={thickness_mm:.3f} mm "
                        f"| k_sub(max)={k_sub_interp.max():.4g}"
                    )
                else:
                    self.logger.info(
                        "[SAPPHIRE] n(lambda) from Sellmeier equation; thickness = 0 -> transparent substrate (k=0)."
                    )

                return k_sub_interp, sub_thickness_nm, None

            if is_silicon:
                if _SILICON_WLS is not None:
                    n_sub_data = _get_silicon_n_on_grid(wls_target)
                    thickness_mm = self.sb_sub_thickness_mm.value()
                    if thickness_mm > 0:
                        k_sub_interp = _get_silicon_k_on_grid(wls_target)
                        sub_thickness_nm = thickness_mm * 1e6
                        self.logger.info(
                            f"[SILICON] Self-absorbent substrate: thickness={thickness_mm:.3f} mm "
                            f"| k_sub(max)={k_sub_interp.max():.4g}"
                        )
                    else:
                        self.logger.info("[SILICON] Thickness = 0 -> transparent substrate (k=0 everywhere).")
                else:
                    self.logger.warning(
                        "[SILICON] clues.xlsx If-substrate not found  transparent mode used (degraded)."
                    )
                return k_sub_interp, sub_thickness_nm, n_sub_data

            if self.chk_absorbing_sub.isChecked():
                if self._ksub_raw_wls is None or self._ksub_raw_k is None:
                    self._abort_run_optimization(
                        "k_sub missing",
                        "Absorbing substrate enabled but no k_sub file loaded.\n"
                        "Please import a CSV (lambda, k) or disable the option.",
                        critical=False,
                    )
                    return None

                thickness_mm = self.sb_sub_thickness_mm.value()
                if thickness_mm <= 0:
                    self.logger.info("Absorbent substrate: thickness = 0 -> transparent substrate (k=0 everywhere).")
                else:
                    k_sub_interp = np.interp(
                        wls_target,
                        self._ksub_raw_wls,
                        self._ksub_raw_k,
                        left=0.0,
                        right=0.0,
                    ).astype(np.float64)
                    sub_thickness_nm = thickness_mm * 1e6
                    self.logger.info(
                        f"Absorbent substrate (manual): thickness={thickness_mm:.3f} mm "
                        f"| k_sub max={k_sub_interp.max():.4g}"
                    )

            return k_sub_interp, sub_thickness_nm, n_sub_data

    def run_optimization(self) -> None:
        """

        Run the index optimization process.

        This method initiates the optimization workflow including:

        - Data validation and mode checking

        - Parameter configuration and setup

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusIndex instance

        Returns:

            None

        Notes:

            - Requires loaded target spectrum data

            - Supports both normal and frosted glass modes

            - Validates data requirements for selected mode

            - Emits progress signals during optimization

        """

        if self.target_data is None:
            QMessageBox.warning(self, "No Data", "Please load a spectrum first.")

            return

        # Check for frosted glass mode

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        if is_frosted_glass:
            # Frosted glass requires reflection data

            if "R" not in self.target_data.columns:
                QMessageBox.warning(
                    self,
                    "Data Error",
                    "Frosted Glass mode requires reflection (R) data.\n"
                    "Please load a file with reflection measurements.",
                )

                return

            # Force data_type to REFLECTION for frosted glass

            effective_data_type = DataType.REFLECTION

        else:
            effective_data_type = self.data_type

        self._cleanup_worker()

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        self.lbl_status.setText(" Optimization running...")

        self.recap_widget.setVisible(False)

        self.tabs.setCurrentIndex(0)

        # substrate - always use selected material (with bounds check)

        sub_idx = self.cb_sub.currentIndex()

        if sub_idx < 0 or sub_idx >= len(SUBSTRATE_LIST):
            self.logger.error(f"Invalid substrate index: {sub_idx}")

            QMessageBox.critical(self, "Error", "Invalid substrate selection.")

            self.btn_run.setEnabled(True)

            self.btn_stop.setEnabled(False)

            return

        full_sub_name = SUBSTRATE_LIST[sub_idx]

        substrate_name = full_sub_name

        substrate_mode = substrateMode.FROSTED_GLASS if is_frosted_glass else substrateMode.STANDARD

        ex_min, ex_max = None, None

        if self.chk_exclude.isChecked():
            ex_min = self.sb_ex_min.value()

            ex_max = self.sb_ex_max.value()

            if ex_min >= ex_max:
                QMessageBox.warning(self, "Warning", "Invalid exclusion range. Ignored.")

                ex_min, ex_max = None, None

        # Absorbing substrate inputs (Sapphire/Si/manual k_sub)
        wls_target = self.target_data["lambda"].to_numpy(dtype=np.float64)
        substrate_inputs = self._resolve_substrate_absorption_inputs(
            substrate_name=substrate_name,
            wls_target=wls_target,
        )
        if substrate_inputs is None:
            return
        k_sub_interp, sub_thickness_nm, n_sub_data = substrate_inputs

        _d_fft_seed = getattr(self, "_estimated_thickness_nm", None)

        _fixed_thickness_seed = None

        if _d_fft_seed is not None:
            _d_lo = float(min(self.sb_dmin.value(), self.sb_dmax.value()))

            _d_hi = float(max(self.sb_dmin.value(), self.sb_dmax.value()))

            _fixed_thickness_seed = float(np.clip(float(_d_fft_seed), _d_lo, _d_hi))

        config = OptimizationConfig(
            target_data=self.target_data,
            data_type=effective_data_type,
            substrate=substrate_name,
            substrate_mode=substrate_mode,
            thickness_min=self.sb_dmin.value(),
            thickness_max=self.sb_dmax.value(),
            lambda_min=self.sb_lmin.value(),
            lambda_max=self.sb_lmax.value(),
            exclude_min=ex_min,
            exclude_max=ex_max,
            source_file=self.source_file_path,
            use_normalized=self.chk_normalized.isChecked(),
            weight_T=self.sb_weight_T.value() if not is_frosted_glass else 0.0,
            weight_R=self.sb_weight_R.value(),
            high_precision=self.chk_high_precision.isChecked(),
            fixed_thickness=_fixed_thickness_seed,
            k_sub_data=k_sub_interp,
            substrate_thickness_nm=sub_thickness_nm,
            n_sub_data=n_sub_data,
        )

        # Start progress widget timing

        self.logger.info("=" * 60)

        self.logger.info("STARTING OPTIMIZATION")

        if self.source_file_path:
            self.logger.info(
                "[FILE] Measured Spectrum: %s",
                Path(self.source_file_path).resolve(),
            )

        else:
            self.logger.warning("[FILE] Measured Spectrum: path not specified")

        if substrate_name == "Sapphire (Al2O3)":
            self.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) "
                "| k file: %s | k column: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )

        elif substrate_name == "Silicon (Si)":
            self.logger.info(
                "[FILE] Substrate Si (clues.xlsx): %s",
                Path(get_resource_path("clues.xlsx")).resolve(),
            )

        self.logger.info("=" * 60)

        self.logger.info(f"substrate: {substrate_name} (Mode: {substrate_mode.name})")

        self.logger.info(f"Thickness Range: {config.thickness_min} - {config.thickness_max} nm")

        self.logger.info(f"Wavelength Range: {config.lambda_min} - {config.lambda_max} nm")

        if config.exclude_min and config.exclude_max:
            self.logger.info(f"Excluded Region: {config.exclude_min} - {config.exclude_max} nm")

        self.logger.info("=" * 50)

        self._reset_optimization_progress_state(config)
        self._configure_and_start_optimization_worker(config)

    def stop_optimization(self) -> None:
        """Stop optimization - best solution will be saved by the worker"""

        # confirm_stop_with_timeout is imported from certus_ui

        if not confirm_stop_with_timeout(self):
            return

        # Ensure UI reflects stopped state immediately

        self.lbl_status.setText(" Stopping...")
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped")

        self.btn_stop.setEnabled(False)

        ok_main = stop_worker_and_thread(
            self._worker,
            self._thread,
            timeout_ms=3000,
            logger=self.logger,
            label="Thread",
        )
        if not ok_main:
            self.lbl_status.setText(" Stop timeout (thread may still finish)")

        stop_worker_and_thread(
            getattr(self, "_worker2", None),
            getattr(self, "_thread2", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Thread2",
        )

        # Also stop beam analysis worker if running

        stop_worker_and_thread(
            getattr(self, "_beam_worker", None),
            getattr(self, "_beam_thread", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Beam thread",
        )

        self.lbl_status.setText(" Stopping...")

    def _cleanup_worker(self) -> None:

        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    if self._worker:
                        self._worker.stop()

                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                # Qt object has already been deleted

                pass

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    if hasattr(self, "_worker2") and self._worker2:
                        self._worker2.stop()

                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_thread_finished(self) -> None:

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_evals_update(self, n_evals: int) -> None:
        """Update evaluation count for progress widget ETA."""

        self._current_n_evals = n_evals

        self.lbl_dice.setText(f" {n_evals:,}")

    def _make_index_tlu_live_ctx(self, c: OptimizationConfig) -> dict | None:
        """lambda / n_sub grid identical to OptimizationWorker.run (TLU) for live, like Metal Bilayer."""

        try:
            _lmf = getattr(c, "lambda_max_fit", None)

            effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))

            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)

            wls = c.target_data.loc[mask, "lambda"].to_numpy(dtype=np.float64)

            if wls.size == 0:
                return None

            sub_id = SUBSTRATES[c.substrate]["id"]

            if c.n_sub_data is not None:
                l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

                n_sub = np.interp(
                    wls,
                    l_full,
                    c.n_sub_data,
                    left=c.n_sub_data[0],
                    right=c.n_sub_data[-1],
                ).astype(np.float64)

            else:
                n_sub = _get_substrate_n_array_index(sub_id, wls)

            target_T = None

            target_R = None

            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()

            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()

            valid = np.isfinite(n_sub)

            if target_T is not None:
                valid &= np.isfinite(target_T)

            if target_R is not None:
                valid &= np.isfinite(target_R)

            wls = wls[valid]

            n_sub = n_sub[valid]

            if wls.size == 0:
                return None

            return {
                "config": c,
                "wls": wls,
                "n_sub": n_sub,
                "k_sub": getattr(c, "k_sub_data", None),
                "D_sub": getattr(c, "substrate_thickness_nm", None),
            }

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning("TLU live context build failed: %s", e)

            return None

    def _index_tlu_live_payload_from_params(self, params: np.ndarray) -> dict | None:
        """n,k + R,T from TLU vector (7 param.) - aligned with TLUObjective.__call__."""

        ctx = getattr(self, "_index_tlu_live_ctx", None)

        if ctx is None:
            return None

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size != 7:
            return None

        c = ctx["config"]

        wls = ctx["wls"]

        n_sub = ctx["n_sub"]

        thickness = float(p[0])

        Eg, A, E0, C, Eu, eps_inf = (float(p[i]) for i in range(1, 7))

        if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
            return None

        E_arr = HC_EV_NM / wls

        eps2 = epsilon2_TLU_array(E_arr, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(E_arr, Eg, A, E0, C, Eu)

        n_calc, k_calc, is_valid = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        if not is_valid:
            return None

        # Use shared source of truth for R/T calculation

        R_calc, T_calc, T_sub_ref = _compute_RT_from_config(c, wls, n_calc, k_calc, thickness, n_sub)

        # Apply normalization scaling based on user configuration

        if not c.is_frosted_glass and getattr(c, "use_normalized", False):
            with np.errstate(divide="ignore", invalid="ignore"):
                # Safety for T_sub -> 0

                Ts_safe = np.where(T_sub_ref > SMALL_EPSILON, T_sub_ref, 1.0)

                T_plot = np.where(T_sub_ref > SMALL_EPSILON, T_calc / Ts_safe, np.nan)

                T_plot = np.maximum(T_plot, 0.0)

            R_plot = calculate_relative_R_normalization(R_calc, T_sub_ref)

        else:
            T_plot, R_plot = T_calc, R_calc

        _st, _sr = _index_live_spectrum_visibility(c)

        return {
            "wls": wls,
            "n": n_calc,
            "k": k_calc,
            "R_calc": R_plot,
            "T_calc": T_plot,
            "is_frosted_glass": bool(c.is_frosted_glass),
            "live_show_T": _st,
            "live_show_R": _sr,
            "mse": None,
        }

    def _apply_index_live_plot_payload(self, extra_info: dict) -> None:
        """Live plot n,k + spectrum (same logic as Spline pipeline / progress dict)."""

        wls = extra_info["wls"]

        n_c = extra_info["n"]

        k_c = extra_info["k"]

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

        c_n = self.plot_nk.plot(wls, n_c, pen=pg.mkPen(color="#3b82f6", width=3), name="n (Live)")

        self.plot_nk.add_tracked_curve(c_n, "n (Live)")

        if not hasattr(self, "_vb_k") or self._vb_k is None:
            pi = self.plot_nk.plotItem

            self._vb_k = pg.ViewBox()

            pi.scene().addItem(self._vb_k)

            ax_k = KLogAxisItem("right")

            ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

            pi.layout.addItem(ax_k, 2, 3)

            ax_k.linkToView(self._vb_k)

            self._vb_k.setXLink(pi)

            pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

        else:
            self._vb_k.clear()

        self._vb_k.setLogMode(False, False)

        self._vb_k.setYRange(-6.5, -2.0, padding=0)

        self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        if self.plot_nk.plotItem.vb.sceneBoundingRect().isValid():
            self._vb_k.setGeometry(self.plot_nk.plotItem.vb.sceneBoundingRect())

        k_plot = np.where(
            np.isfinite(k_c) & (k_c >= 1e-8),
            np.log10(np.maximum(k_c, 1e-7)),
            -7.0,
        )

        c_k = pg.PlotCurveItem(
            wls,
            k_plot,
            pen=pg.mkPen(color="#f59e0b", width=3),
            name="log10(k) (Live)",
        )

        self._vb_k.addItem(c_k)

        self.plot_nk.add_tracked_curve(c_k, "log10(k) (Live)")

        if "R_calc" in extra_info or "T_calc" in extra_info:
            show_t = extra_info.get("live_show_T", True)

            show_r = extra_info.get("live_show_R", True)

            Rc = extra_info.get("R_calc")

            Tc = extra_info.get("T_calc")

            for item in list(self.plot_spectrum.plotItem.items):
                item_name = getattr(item, "name", lambda: "")()

                if item_name in [
                    "R (Live)",
                    "T (Live)",
                    "R Fit",
                    "T Fit",
                    "R (Live Spline)",
                    "T (Live Spline)",
                ]:
                    self.plot_spectrum.plotItem.removeItem(item)

            try:
                self.plot_spectrum.remove_tracked_curve("R (Live)")

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            try:
                self.plot_spectrum.remove_tracked_curve("T (Live)")

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            if show_r and Rc is not None:
                c_r = pg.PlotCurveItem(
                    wls,
                    np.asarray(Rc) * 100,
                    pen=pg.mkPen(color="#ef4444", width=3),
                    name="R (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_r, "R (Live)")

                self.plot_spectrum.plotItem.addItem(c_r)

            if show_t and Tc is not None:
                c_t = pg.PlotCurveItem(
                    wls,
                    np.asarray(Tc) * 100,
                    pen=pg.mkPen(color="#10b981", width=3),
                    name="T (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_t, "T (Live)")

                self.plot_spectrum.plotItem.addItem(c_t)

        try:
            self.plot_spectrum.getPlotItem().vb.autoRange()

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            self.plot_nk.getPlotItem().vb.autoRange()

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.tabs.setCurrentIndex(0)

    def _on_progress(self, step: int, phase: str, extra_info=None) -> None:

        # Throttle UI updates (plots, labels, tables) to avoid GUI flooding

        now = time.time()

        # Always update if phase changes, otherwise check 2.0s interval

        phase_changed = self._last_phase_name != phase

        self._last_phase_name = phase

        if not phase_changed and (now - self._last_progress_ui_update < 2.0):
            return

        self._last_progress_ui_update = now

        rmse_val = 0.0

        rmse_str = ""

        is_numeric_msg = False

        if isinstance(extra_info, dict) and "n" in extra_info and "k" in extra_info and "wls" in extra_info:
            try:
                self._apply_index_live_plot_payload(extra_info)

                wls = extra_info["wls"]

                n_c = extra_info["n"]

                k_c = extra_info["k"]

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                self.logger.error(f"Error plotting live progress: {e}", exc_info=True)

                wls = extra_info.get("wls", np.array([]))

                n_c = extra_info.get("n", np.array([]))

                k_c = extra_info.get("k", np.array([]))

            # Live Update of Data Tab & Clipboard Support

            try:
                if getattr(self, "latest_results", None) is not None:
                    # Update background DataFrame so Copy works

                    live_df = pd.DataFrame({"lambda": wls, "n_calc": n_c, "k_calc": k_c})

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        live_df["R_calc (%)"] = extra_info["R_calc"] * 100

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        live_df["T_calc (%)"] = extra_info["T_calc"] * 100

                    self.latest_results.df_results = live_df

                    self.table_res.setRowCount(len(wls))

                    src_name_base = Path(self.latest_results.config.source_file).stem

                    d_val = (
                        int(round(self.latest_results.thickness))
                        if hasattr(self.latest_results, "thickness") and self.latest_results.thickness
                        else 0
                    )

                    n_colname = f"n_{src_name_base}_{d_val}"

                    k_colname = f"k_{src_name_base}_{d_val}"

                    cols = ["lambda (nm)", n_colname, k_colname]

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        cols.append("T (%)")

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        cols.append("R (%)")

                    self.table_res.setColumnCount(len(cols))

                    self.table_res.setHorizontalHeaderLabels(cols)

                    for i in range(len(wls)):
                        self.table_res.setItem(i, 0, QTableWidgetItem(f"{wls[i]:.1f}"))

                        self.table_res.setItem(i, 1, QTableWidgetItem(f"{n_c[i]:.4f}"))

                        self.table_res.setItem(i, 2, QTableWidgetItem(f"{k_c[i]:.6f}"))

                        col_idx = 3

                        if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['T_calc'][i] * 100:.2f}"))

                            col_idx += 1

                        if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['R_calc'][i] * 100:.2f}"))

                            col_idx += 1

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                self.logger.error(f"Live data table update error: {e}", exc_info=True)

            if isinstance(extra_info, dict) and "mse" in extra_info:
                val = extra_info["mse"]

                if val is not None:
                    rmse_val = np.sqrt(val)

                    if rmse_val < self._best_rmse_display:
                        self._best_rmse_display = rmse_val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                else:
                    self.lbl_status.setText(f"{phase}")

            else:
                self.lbl_status.setText(f"{phase}")

            # Still update the progress bar even with dict data

            n_evals = getattr(self, "_current_n_evals", 0)

            self.progress_widget.update(step, 100, n_evals, phase, "")

            return

        elif isinstance(extra_info, float):
            # It's a numerical MSE

            rmse_val = np.sqrt(extra_info)

            if rmse_val < self._best_rmse_display:
                self._best_rmse_display = rmse_val

            rmse_str = f"RMSE: {rmse_val:.5f}"

            self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

            is_numeric_msg = True

        elif isinstance(extra_info, str):
            # Try to parse string message if it contains numerical info

            if "Total Data RMSE" in extra_info:
                try:
                    val_str = extra_info.split()[-1]

                    val = float(val_str)

                    if val < self._best_rmse_display:
                        self._best_rmse_display = val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                    rmse_val = val

                    rmse_str = f"RMSE: {val:.5f}"

                    is_numeric_msg = True

                except ValueError:
                    self.lbl_status.setText(f"{phase} | {extra_info}")

                    rmse_str = extra_info

            else:
                self.lbl_status.setText(f"{phase} | {extra_info}")

                rmse_str = extra_info

        else:
            self.lbl_status.setText(f"{phase}")

            rmse_str = str(extra_info) if extra_info else ""

        if is_numeric_msg and rmse_val > 0:
            self._total_iterations += 1

            # --- UX-3: update convergence chart ---
            if hasattr(self, "_conv_iterations"):
                self._conv_iterations.append(self._total_iterations)
                self._conv_rmse_current.append(rmse_val)
                self._conv_rmse_best.append(self._best_rmse_display)
                xs = self._conv_iterations
                self._conv_curve_current.setData(xs, self._conv_rmse_current)
                self._conv_curve_best.setData(xs, self._conv_rmse_best)

        n_evals = getattr(self, "_current_n_evals", 0)

        self.progress_widget.update(
            iteration=step,
            max_iter=100,
            evals=n_evals,
            phase=phase,
            extra_info=rmse_str,
        )

    def _on_error(self, error_msg: str) -> None:

        self.lbl_status.setText(" Error")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Error")

        # Quit orphaned thread (error signal does NOT trigger thread.quit)

        if hasattr(self, "_thread") and self._thread is not None:
            try:
                if self._thread.isRunning():
                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread cleanup warning: {e}")

            finally:
                self._thread = None

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread2 cleanup warning: {e}")

            finally:
                self._thread2 = None

        self._worker = None

        self._worker2 = None

        self._thread = None

        self._thread2 = None

        self.optimization_running = False

        self.logger.error(f"Worker Error: {error_msg}")

    def _on_curve_update(self, params) -> None:
        """Live TLU : equivalent Metal Bilayer ``progress`` -> ``update_plots`` (best parameter set)."""

        try:
            p = np.asarray(params, dtype=np.float64).ravel()

            if p.size != 7:
                return

            payload = self._index_tlu_live_payload_from_params(p)

            if payload is None:
                return

            self._apply_index_live_plot_payload(payload)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.debug("curve_update: %s", e, exc_info=True)

    def _update_spectrum_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the T/R spectrum plot (data + fit)."""

        self.plot_spectrum.clear()

        self.plot_spectrum.clear_tracking()

        self._update_plot_exclusion()

        try:
            _set_spectrum_plot_title(self.plot_spectrum, res.config.source_file)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # Display target data

        if "T_target" in sub_df.columns and not res.config.is_frosted_glass:
            try:
                c_tgt_t = self.plot_spectrum.plot(
                    wls,
                    sub_df["T_target"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=4,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_t, "T Target", "%")

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                self.logger.error(f"Error displaying T target: {e}", exc_info=True)

        if "R_target" in sub_df.columns:
            try:
                c_tgt_r = self.plot_spectrum.plot(
                    wls,
                    sub_df["R_target"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=4,
                    symbolBrush=CertusTheme.DANGER,
                    name="R Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_r, "R Target", "%")

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                self.logger.error(f"Error displaying R target: {e}", exc_info=True)

        # Display fits

        use_normalized = res.config.use_normalized

        # Transmission (not for frosted glass)

        if not res.config.is_frosted_glass and res.config.data_type in (
            DataType.TRANSMISSION,
            DataType.BOTH,
        ):
            col_T = "T_norm_calc (%)" if use_normalized else "T_calc (%)"

            if col_T in sub_df.columns:
                try:
                    c_fit_t = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_T].values,
                        pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                        name="T Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_t, "T Fit", "%")

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                    self.logger.error(f"Error displaying T fit: {e}", exc_info=True)

        # Reflection

        if res.config.data_type in (DataType.REFLECTION, DataType.BOTH) or res.config.is_frosted_glass:
            col_R = "R_norm_calc (%)" if use_normalized else "R_calc (%)"

            if col_R in sub_df.columns:
                try:
                    c_fit_r = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_R].values,
                        pen=pg.mkPen(CertusTheme.DANGER, width=3),
                        name="R Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_r, "R Fit", "%")

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                    self.logger.error(f"Error displaying R fit: {e}", exc_info=True)

    def _update_nk_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the n & k plot (left axis n, right axis log k)."""

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        try:
            src_name = Path(res.config.source_file).stem

            title_text = f"Optical Constants      {src_name}      thickness = {res.optimal_thickness:.2f} nm"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title_text = f"Optical Constants      thickness = {res.optimal_thickness:.2f} nm"

        self.plot_nk.plotItem.setTitle(title_text)

        prepared = _prepare_nk_plot_inputs(wls, sub_df, res, self.logger)
        if prepared is None:
            return
        n_values, k_values, method_str, lambda_max_fit, tlu_mode = prepared

        try:
            # k curve refs for legend

            c_k_main = None

            c_kt = None

            c_kr = None

            # --- Primary axis (left): n ---

            # Label left axis explicitly

            self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

            if "n_calc_005" in sub_df.columns:
                n1 = sub_df["n_calc_005"].values.copy()

                n2 = sub_df["n_calc_0025"].values.copy()

                n3 = sub_df["n_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    n1[ir_mask_ui] = np.nan

                    n2[ir_mask_ui] = np.nan

                    n3[ir_mask_ui] = np.nan

                self.plot_nk.plot(wls, n1, pen=pg.mkPen(color="#93c5fd", width=2), name="n (tol=0.005)")

                self.plot_nk.plot(wls, n2, pen=pg.mkPen(color="#3b82f6", width=2), name="n (tol=0.0025)")

                c_n3 = self.plot_nk.plot(wls, n3, pen=pg.mkPen(color="#1e3a8a", width=3), name="n (tol=0.001)")

                self.plot_nk.add_tracked_curve(c_n3, "n")

                self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            else:
                c_n = self.plot_nk.plot(wls, n_values, pen=pg.mkPen(CertusTheme.PRIMARY, width=3), name="n (R+T)")

                self.plot_nk.add_tracked_curve(c_n, "n (R+T)")

                if "n_center" in sub_df.columns and "n_hi" in sub_df.columns and "n_lo" in sub_df.columns:
                    n_cen = sub_df["n_center"].values.copy()

                    if tlu_mode:
                        n_cen[ir_mask_ui] = np.nan

                    c_nc = self.plot_nk.plot(
                        wls,
                        n_cen,
                        pen=pg.mkPen(color=CertusTheme.SUCCESS, width=2, style=Qt.PenStyle.DashLine),
                        name="n (center)",
                    )

                    self.plot_nk.add_tracked_curve(c_nc, "n (center)")

                    n_err_center = sub_df["n_raw"].values if "n_raw" in sub_df.columns else n_values

                    top_n = sub_df["n_hi"].values - n_err_center

                    bot_n = n_err_center - sub_df["n_lo"].values

                    top_n = np.where(np.isfinite(top_n), top_n, 0)

                    bot_n = np.where(np.isfinite(bot_n), bot_n, 0)

                    if "n_hi_2" in sub_df.columns and "n_lo_2" in sub_df.columns:
                        top_n2 = sub_df["n_hi_2"].values - n_err_center

                        bot_n2 = n_err_center - sub_df["n_lo_2"].values

                        top_n2 = np.where(np.isfinite(top_n2), top_n2, 0)

                        bot_n2 = np.where(np.isfinite(bot_n2), bot_n2, 0)

                        err_n2 = pg.ErrorBarItem(
                            x=wls,
                            y=n_err_center,
                            top=top_n2,
                            bottom=bot_n2,
                            beam=0.5,
                            pen=pg.mkPen(color=(30, 136, 229, 80), width=3),
                        )

                        self.plot_nk.plotItem.addItem(err_n2)

                    err_n = pg.ErrorBarItem(
                        x=wls,
                        y=n_err_center,
                        top=top_n,
                        bottom=bot_n,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.PRIMARY, width=1),
                    )

                    self.plot_nk.plotItem.addItem(err_n)

                    if "n_raw" in sub_df.columns:
                        # Plot the raw bisection cloud as a translucent scattered layer underneath the clean Line

                        c_raw = self.plot_nk.plot(
                            wls,
                            n_err_center,
                            pen=pg.mkPen(color=(30, 136, 229, 120), width=1, style=Qt.PenStyle.DotLine),
                            name="n (Raw point-by-point)",
                        )

                        self.plot_nk.add_tracked_curve(c_raw, "n (Raw)")

                # --- EXTRA FITS: Visualization ---

                if "n_fit_T_only" in sub_df.columns:
                    c_nt = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_T_only"].values,
                        pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% T)",
                    )

                    self.plot_nk.add_tracked_curve(c_nt, "n (90% T)")

                if "n_fit_R_only" in sub_df.columns:
                    c_nr = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_R_only"].values,
                        pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% R)",
                    )

                    self.plot_nk.add_tracked_curve(c_nr, "n (90% R)")

            # Legend n (left axis)

            self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            # --- Secondary axis (right, log scale): k ---

            pi = self.plot_nk.plotItem

            # Create or reuse secondary ViewBox

            if not hasattr(self, "_vb_k") or self._vb_k is None:
                self._vb_k = pg.ViewBox()

                pi.scene().addItem(self._vb_k)

                ax_k = KLogAxisItem("right")

                ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

                pi.layout.addItem(ax_k, 2, 3)

                ax_k.linkToView(self._vb_k)

                self._vb_k.setXLink(pi)

                self._ax_k = ax_k

                # Geometry sync on resize (connected once only)

                pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

            else:
                self._vb_k.clear()

            # Do NOT use pyqtgraph's internal setLogMode, it silently drops curves if any single point causes a math domain error during rendering.

            # Instead, we will feed it raw log10() values into a linear ViewBox.

            self._vb_k.setLogMode(False, False)

            self._vb_k.setYRange(-6.5, -2.0, padding=0)

            self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

            self._vb_k.setGeometry(pi.vb.sceneBoundingRect())

            # Plot k  use a tiny floor so k0 regions (VIS) stay connected on log scale

            # pyqtgraph's ViewBox with setLogMode(Y=True) applies log10 internally,

            # so we must NOT pass NaN for k=0; instead we floor at 1e-7.

            if "k_calc_005" in sub_df.columns:
                k1 = sub_df["k_calc_005"].values.copy()

                k2 = sub_df["k_calc_0025"].values.copy()

                k3 = sub_df["k_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    k1[ir_mask_ui] = np.nan

                    k2[ir_mask_ui] = np.nan

                    k3[ir_mask_ui] = np.nan

                k1_p = np.where(np.isfinite(k1) & (k1 >= 1e-8), np.log10(np.maximum(k1, 1e-7)), -7.0)

                k2_p = np.where(np.isfinite(k2) & (k2 >= 1e-8), np.log10(np.maximum(k2, 1e-7)), -7.0)

                k3_p = np.where(np.isfinite(k3) & (k3 >= 1e-8), np.log10(np.maximum(k3, 1e-7)), -7.0)

                c_k1 = pg.PlotCurveItem(wls, k1_p, pen=pg.mkPen(color="#fcd34d", width=2), name="log10(k) (tol=0.005)")

                c_k2 = pg.PlotCurveItem(wls, k2_p, pen=pg.mkPen(color="#f59e0b", width=2), name="log10(k) (tol=0.0025)")

                c_k3 = pg.PlotCurveItem(wls, k3_p, pen=pg.mkPen(color="#b45309", width=3), name="log10(k) (tol=0.001)")

                self._vb_k.addItem(c_k1)

                self._vb_k.addItem(c_k2)

                self._vb_k.addItem(c_k3)

                self.plot_nk.add_tracked_curve(c_k3, "log10(k)")

            else:
                k_plot = np.where(
                    np.isfinite(k_values) & (k_values >= 1e-8), np.log10(np.maximum(k_values, 1e-7)), -7.0
                )

                c_k = pg.PlotCurveItem(wls, k_plot, pen=pg.mkPen(CertusTheme.WARNING, width=3), name="k (R+T)")

                self._vb_k.addItem(c_k)

                self.plot_nk.add_tracked_curve(c_k, "log10(k)")

                c_k_main = c_k

                if "k_center" in sub_df.columns and "k_hi" in sub_df.columns and "k_lo" in sub_df.columns:
                    kc = sub_df["k_center"].values.copy()

                    if tlu_mode:
                        kc[ir_mask_ui] = np.nan

                    kc_plot = np.where(np.isfinite(kc) & (kc >= 0), np.maximum(kc, 1e-7), np.nan)

                    c_kc = pg.PlotCurveItem(
                        wls,
                        kc_plot,
                        pen=pg.mkPen(color=CertusTheme.WARNING, width=2, style=Qt.PenStyle.DashLine),
                        name="k (center)",
                    )

                    self._vb_k.addItem(c_kc)

                    self.plot_nk.add_tracked_curve(c_kc, "log10(k) (center)")

                    k_err_center = sub_df["k_raw"].values if "k_raw" in sub_df.columns else k_plot

                    k_err_center_plot = np.where(
                        np.isfinite(k_err_center) & (k_err_center >= 0), np.maximum(k_err_center, 1e-7), np.nan
                    )

                    top_k = sub_df["k_hi"].values - k_err_center_plot

                    bot_k = k_err_center_plot - sub_df["k_lo"].values

                    top_k = np.where(np.isfinite(top_k), top_k, 0)

                    bot_k = np.where(np.isfinite(bot_k), bot_k, 0)

                    if "k_hi_2" in sub_df.columns and "k_lo_2" in sub_df.columns:
                        top_k2 = sub_df["k_hi_2"].values - k_err_center_plot

                        bot_k2 = k_err_center_plot - sub_df["k_lo_2"].values

                        top_k2 = np.where(np.isfinite(top_k2), top_k2, 0)

                        bot_k2 = np.where(np.isfinite(bot_k2), bot_k2, 0)

                        err_k2 = pg.ErrorBarItem(
                            x=wls,
                            y=k_err_center_plot,
                            top=top_k2,
                            bottom=bot_k2,
                            beam=0.5,
                            pen=pg.mkPen(color=(255, 179, 0, 80), width=3),
                        )

                        self._vb_k.addItem(err_k2)

                    err_k = pg.ErrorBarItem(
                        x=wls,
                        y=k_err_center_plot,
                        top=top_k,
                        bottom=bot_k,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.WARNING, width=1),
                    )

                    self._vb_k.addItem(err_k)

            # --- EXTRA FITS: k Visualization ---

            if "k_fit_T_only" in sub_df.columns:
                kt = sub_df["k_fit_T_only"].values

                kt_p = np.where(np.isfinite(kt) & (kt >= 1e-8), np.log10(np.maximum(kt, 1e-7)), -7.0)

                c_kt = pg.PlotCurveItem(
                    wls, kt_p, pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine), name="k (90% T)"
                )

                self._vb_k.addItem(c_kt)

                self.plot_nk.add_tracked_curve(c_kt, "log10(k) (90% T)")

            if "k_fit_R_only" in sub_df.columns:
                kr = sub_df["k_fit_R_only"].values

                kr_p = np.where(np.isfinite(kr) & (kr >= 1e-8), np.log10(np.maximum(kr, 1e-7)), -7.0)

                c_kr = pg.PlotCurveItem(
                    wls, kr_p, pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine), name="k (90% R)"
                )

                self._vb_k.addItem(c_kr)

                self.plot_nk.add_tracked_curve(c_kr, "log10(k) (90% R)")

            if "k_raw" in sub_df.columns:
                c_k_raw = pg.PlotCurveItem(
                    wls,
                    k_err_center_plot,
                    pen=pg.mkPen(color=(255, 179, 0, 120), width=1, style=Qt.PenStyle.DotLine),
                    name="k (Raw point-by-point)",
                )

                self._vb_k.addItem(c_k_raw)

                self.plot_nk.add_tracked_curve(c_k_raw, "log10(k) (Raw)")

            # Legend k (right axis)

            if c_k_main is not None or c_kt is not None or c_kr is not None:
                leg_k = pg.LegendItem(offset=(10, 120), labelTextSize="9pt")

                leg_k.setParentItem(self.plot_nk.plotItem)

                if c_k_main is not None:
                    leg_k.addItem(c_k_main, "k (R+T)")

                if c_kt is not None:
                    leg_k.addItem(c_kt, "k (90% T)")

                if c_kr is not None:
                    leg_k.addItem(c_kr, "k (90% R)")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Error displaying n/k: {e}", exc_info=True)

            self.logger.error(traceback.format_exc())

    def _update_model_text(self, res: OptimizationResults) -> None:

        # Update data table

        try:
            if hasattr(self, "lbl_final_eq"):
                eq_html = "<h2>Final Analytical Optical Model</h2><br>"

                eq_html += f"<b>Optimal Thickness :</b> {res.optimal_thickness:.7f} nm<br><br>"

                eq_html += "<table width='100%'><tr><td valign='top' width='50%'>"

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    eq_html += "<b>Refractive Index (Sellmeier 2-poles + A)</b><br>"

                    eq_html += (
                        "<i>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2)</i> (lambda in m)<br>"
                    )

                    eq_html += "<ul>"

                    eq_html += f"<li><b>A</b> = {sp[0]:.6f}</li>"

                    eq_html += f"<li><b>B1</b> = {sp[1]:.7e}  <b>C1</b> = {sp[2] ** 2:.7e} m2</li>"

                    eq_html += f"<li><b>B2</b> = {sp[3]:.7e}  <b>C2</b> = {sp[4] ** 2:.7e} m2</li>"

                    eq_html += "</ul>"

                eq_html += "</td><td valign='top' width='50%'>"

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    eq_html += "<b>Extinction Coefficient (Generalized Exp + Gaussian 8-params)</b><br>"

                    eq_html += "<i>k(lambda) = 1e-6 + exp(P1lambda + P2) + exp(P3lambda + P4) + P5exp(-| (lambda-P6)/P7 | ^ P8)</i> (lambda in m)<br>"

                    eq_html += "<ul>"

                    eq_html += "<li><b>P1-P4</b> (Exponentials)</li>"

                    eq_html += f"<li><b>P5</b> (Amp) = {kp[4]:.7e}</li>"

                    eq_html += f"<li><b>P6</b> (Center) = {kp[5]:.7e}</li>"

                    eq_html += f"<li><b>P7</b> (Width) = {kp[6]:.7e}</li>"

                    eq_html += f"<li><b>P8 (Beta Shape)</b> = {kp[7]:.4f}</li>"

                    eq_html += "</ul>"

                    if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                        eq_html += f"<br><i>k refined by spline (log k) Phase 2.3 {len(res.k_spline_knots_lambda_um)} knots</i>"

                eq_html += "</td></tr></table>"

                self.lbl_final_eq.setText(eq_html)

            # Update independent parameters table (16 parameters list)

            try:
                params_rows = []

                # 1. Sellmeier

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    params_rows.extend(
                        [
                            ("A (Constant)", f"{sp[0]:.6f}"),
                            ("B1", f"{sp[1]:.6f}"),
                            ("C1 (m2)", f"{sp[2] ** 2:.6f}"),
                            ("B2", f"{sp[3]:.6f}"),
                            ("C2 (m2)", f"{sp[4] ** 2:.6f}"),
                        ]
                    )

                # 2. k-law (8 params)

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    names = [
                        "P1 (Slope1)",
                        "P2 (Pos1)",
                        "P3 (Slope2)",
                        "P4 (Pos2)",
                        "P5 (Amp)",
                        "P6 (Center)",
                        "P7 (Width)",
                        "P8 (Beta Exponent)",
                    ]

                    for idx, val in enumerate(kp):
                        p_name = names[idx] if idx < len(names) else f"P{idx + 1}"

                        params_rows.append((p_name, f"{val:.6e}"))

                self.table_params.setRowCount(len(params_rows))

                for i, (p_name, p_val) in enumerate(params_rows):
                    item_name = QTableWidgetItem(p_name)

                    item_name.setBackground(pg.mkColor(CertusTheme.SURFACE))

                    self.table_params.setItem(i, 0, item_name)

                    self.table_params.setItem(i, 1, QTableWidgetItem(p_val))

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
                self.logger.error(f"Error updating params table: {e}")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Error updating model text: {e}", exc_info=True)

        self.btn_copy_nk.setEnabled(True)

        self.btn_copy_params.setEnabled(True)

    def _update_data_table(self, sub_df, res: OptimizationResults) -> None:

        try:
            self.table_res.setRowCount(len(sub_df))

            has_T_tgt = "T_target" in sub_df.columns

            has_R_tgt = "R_target" in sub_df.columns

            src_name_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_colname = f"n_{src_name_base}_{d_val}"

            k_colname = f"k_{src_name_base}_{d_val}"

            if res.config.is_frosted_glass:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

            else:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("T (%)")

                if "n_fit_T_only" in sub_df.columns:
                    cols.extend(["n (T-only)", "k (T-only)"])

                if has_T_tgt:
                    cols.append("T Exp (%)")

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['T_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_T_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_T_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_T_only']:.6f}"))

                        col_idx += 1

                    if has_T_tgt:
                        val_t = row_data["T_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_t:.2f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Error updating data table: {e}", exc_info=True)

    def _display_results(self, res: OptimizationResults) -> None:
        """Update UI graphs and table with results"""

        try:
            df = res.df_results

            if df.empty:
                self.logger.error("df_results is empty!")

                return

            # Verify required columns

            required_cols = ["lambda", "n_calc", "k_calc"]

            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                self.logger.error(f"Missing columns in df_results: {missing_cols}")

                self.logger.error(f"Available columns: {list(df.columns)}")

                return

            mask = (df["lambda"] >= res.config.lambda_min) & (df["lambda"] <= res.config.lambda_max)

            sub_df = df[mask]

            if sub_df.empty:
                self.logger.error(
                    f"sub_df is empty after filtering! lambda_min={res.config.lambda_min}, lambda_max={res.config.lambda_max}"
                )

                return

            wls = sub_df["lambda"].values

            if len(wls) == 0:
                self.logger.error("wls is empty!")

                return

            self._update_spectrum_plot(wls, sub_df, res)

            self._update_nk_plot(wls, sub_df, res)

            self._update_model_text(res)

            self._update_data_table(sub_df, res)

            self.tabs.setCurrentIndex(0)

            try:
                self.plot_spectrum.getPlotItem().vb.autoRange()

                self.plot_nk.getPlotItem().vb.autoRange()

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Error in _display_results: {e}", exc_info=True)

            self.logger.error(traceback.format_exc())

            QMessageBox.warning(
                self,
                "Display Error",
                f"Error displaying results: {e}\n\nCheck logs for details.",
            )

    def _copy_nk_to_clipboard(self) -> None:
        """Copy the full n,k table (lambda, n, k, ) to the clipboard as tab-separated text."""

        if self.latest_results is None or self.latest_results.df_results is None:
            QMessageBox.warning(self, "No Data", "No results available to copy.")

            return

        df = self.latest_results.df_results

        required = ["lambda", "n_calc", "k_calc"]

        if not all(c in df.columns for c in required):
            QMessageBox.warning(self, "No Data", "Result table does not contain n,k data.")

            return

        try:
            res = self.latest_results

            src_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_col = f"n_{src_base}_{d_val}"

            k_col = f"k_{src_base}_{d_val}"

            header = f"lambda (nm)\t{n_col}\t{k_col}"

            if "delta_n" in df.columns:
                header += "\tdelta_n\tdelta_k"

            if "n_fit_T_only" in df.columns:
                header += "\tn (T-only)\tk (T-only)"

            if "n_fit_R_only" in df.columns:
                header += "\tn (R-only)\tk (R-only)"

            lines = [header]

            for _, row in df.iterrows():
                row_str = f"{row['lambda']:.1f}\t{row['n_calc']:.6f}\t{row['k_calc']:.9f}"

                if "delta_n" in df.columns:
                    row_str += f"\t{row['delta_n']:.6f}\t{row['delta_k']:.9f}"

                if "n_fit_T_only" in df.columns:
                    row_str += f"\t{row['n_fit_T_only']:.6f}\t{row['k_fit_T_only']:.9f}"

                if "n_fit_R_only" in df.columns:
                    row_str += f"\t{row['n_fit_R_only']:.6f}\t{row['k_fit_R_only']:.9f}"

                lines.append(row_str)

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("n,k table copied!")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Copy error: {e}")

    def _copy_params_to_clipboard(self) -> None:
        """Copy the 16 global model parameters to the clipboard."""

        if self.table_params.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No parameters available to copy.")

            return

        try:
            lines = ["Parameter\tValue"]

            for i in range(self.table_params.rowCount()):
                p = self.table_params.item(i, 0).text()

                v = self.table_params.item(i, 1).text()

                lines.append(f"{p}\t{v}")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("Model parameters copied!")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as e:
            self.logger.error(f"Copy error: {e}")

    def _copy_eq_to_clipboard(self) -> None:
        """Copy the final analytical equations to the clipboard as text."""

        if self.latest_results is None:
            QMessageBox.warning(self, "No Data", "No results available to copy.")

            return

        try:
            res = self.latest_results

            lines = ["Final Analytical Optical Model", "=" * 40]

            lines.append(f"Optimal Thickness : {res.optimal_thickness:.7f} nm\n")

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                lines.append("Refractive Index (Sellmeier 2-poles + A)")

                lines.append("n^2 = A + (B1*L^2)/(L^2 - C1) + (B2*L^2)/(L^2 - C2)  with L in m")

                lines.append(f"A = {sp[0]:.6f}")

                lines.append(f"B1 = {sp[1]:.7e}")

                lines.append(f"C1 = {sp[2] ** 2:.7e} m^2")

                lines.append(f"B2 = {sp[3]:.7e}")

                lines.append(f"C2 = {sp[4] ** 2:.7e} m^2\n")

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                lines.append("Extinction Coefficient (Generalized Exp + Super-Gauss 8-params)")

                lines.append("k(L) = 1e-6 + exp(P1*L + P2) + exp(P3*L + P4) + P5*exp(-abs((L-P6)/P7)^P8)  with L in m")

                for idx, val in enumerate(kp):
                    lines.append(f"P{idx + 1} = {val:.7e}")

                if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                    lines.append("k refined by Phase 2.3 spline (log k)")

                    lines.append(f"Knots (m): {res.k_spline_knots_lambda_um.tolist()}")

                    lines.append(f"k at knots: {res.k_spline_knots_values.tolist()}")

                lines.append("")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText(" Equations copied to clipboard")

            self.logger.info("Final equations copied to clipboard.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Copy equations failed: {e}", exc_info=True)

            QMessageBox.critical(self, "Copy Error", str(e))

    def _on_finished(self, res: OptimizationResults) -> None:

        # Stop progress widget and show completion

        mode_str = "Frosted Glass" if res.config.is_frosted_glass else res.config.data_type.name

        self.progress_widget.stop(f"Done ({mode_str})")

        # Status message adapted to mode

        self.lbl_status.setText(f" Done ({mode_str})")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        # Enable Copy n,k

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(True)

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(True)

        # Button states are now entirely automated based on wavelength, no Refine buttons.

        # Save results for export

        self.latest_results = res

        # PHASE 5: Sellmeier refit + k reopt. Skip when result already from Phase 2 global model.

        try:
            method = (res.optimization_stats or {}).get("method", "")

            skip_phase5_overwrite = "PGLOBAL" in method or "Sellmeier+k" in method

            if skip_phase5_overwrite:
                self.logger.info("Phase 5: skipped (global Sellmeier+k; keeping n/k as-is)")

            else:
                self.lbl_status.setText(" Phase 5: Global Sellmeier fit for n & k re-optimization...")

                df = res.df_results

                if "lambda" in df.columns and "n_calc" in df.columns and "k_calc" in df.columns:
                    wls = df["lambda"].values

                    n_exp = df["n_calc"].values

                    k_cal = df["k_calc"].values

                    # 1. Global Sellmeier 2-poles fit on calculated n

                    n_spline = n_exp.copy()

                    n_target = n_exp.copy()

                    # Blend TLU with Spline for wls < 2500 nm to find the ideal compromise

                    if res.tlu_params is not None:
                        try:
                            from certus_physics import epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk

                            tlu = res.tlu_params

                            E_wls = HC_EV_NM / wls

                            e2_w = epsilon2_TLU_array(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.Eu)

                            e1_w = epsilon1_TL_analytic(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf)

                            n_tlu, _, _ = epsilon_to_nk(e1_w, e2_w, 0.5, 15.0, 15.0)

                            mask_2500 = wls < 2500.0

                            n_target[mask_2500] = (n_spline[mask_2500] + n_tlu[mask_2500]) / 2.0

                        except NUMERICAL_FAULT_EXCEPTIONS as e:
                            self.logger.warning(f"Could not compute TLU compromise: {e}")

                    # Mask out the exclude range if it exists

                    valid_mask = np.ones_like(wls, dtype=bool)

                    ex_min = res.config.exclude_min

                    ex_max = res.config.exclude_max

                    if ex_min is not None and ex_max is not None and ex_min > 0 and ex_max > ex_min:
                        valid_mask &= ~((wls >= ex_min) & (wls <= ex_max))

                    n_fit_global, params_n = fit_sellmeier_global(
                        wls, n_exp, material=res.config.substrate, valid_mask=valid_mask
                    )

                    if params_n is not None:
                        # 2. Re-optimize / smooth k using the 8-parameter empirical law

                        k_smooth, params_k = fit_k_global_8p(wls, k_cal, valid_mask=valid_mask)

                        if params_k is not None:
                            setattr(res, "k_8p_params", params_k)

                        # 3. Update dataframe with perfectly smooth n & newly re-optimized k

                        df["n_calc"] = n_fit_global

                        if params_k is not None:
                            df["k_calc"] = k_smooth

                        # Save Sellmeier parameters to res object to export them

                        setattr(res, "sellmeier_params", params_n)

                        self.logger.info("Phase 5: Sellmeier & K reoptimization successful")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Phase 5 failed (n Sellmeier / k reopt) : {e}", exc_info=True)

            # Safe Fallback: Original res is unchanged and will be exported normally.

        # =====================================================================

        # Convert final_mse to RMSE

        final_rmse = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Update summary (safe for Spline where tlu_params is None)

        eg_val = res.tlu_params.Eg if res.tlu_params else 0.0

        eps_val = res.tlu_params.eps_inf if res.tlu_params else 0.0

        self.recap_widget.update_results(res.optimal_thickness, final_rmse, eg_val, eps_val)

        # Update graphs (target + fit according to use_normalized) BEFORE HTML export:

        # generate_html_report performs a grab() of the widget; if the export precedes this plot,

        # the Visual Analysis section shows an obsolete state (e.g., live curves only, old T/Tsub mode).

        self._display_results(res)

        # AUTO EXPORT (Excel + HTML ; the PNG capture must reflect the spectrum above)

        self.export_results()

    def _on_tlu_constrained_finished(self, tlu_res: OptimizationResults) -> None:

        # Check if user requested stop during Phase 1

        if self._worker is not None and self._worker.is_stopped:
            self._on_finished(tlu_res)

            return

        # Show the TLU curve and results before asking the question

        final_rmse_tlu = np.sqrt(tlu_res.final_mse) if tlu_res.final_mse >= 0 else 0.0

        eg_val = tlu_res.tlu_params.Eg if tlu_res.tlu_params else 0.0

        eps_val = tlu_res.tlu_params.eps_inf if tlu_res.tlu_params else 0.0

        self.recap_widget.update_results(tlu_res.optimal_thickness, final_rmse_tlu, eg_val, eps_val)

        self._display_results(tlu_res)

        # Force Qt to redraw the GUI immediately before crashing with popup

        # Request validation before launching the IR phase which is cumbersome

        msg_box = QMessageBox(self)

        msg_box.setIcon(QMessageBox.Icon.Question)

        msg_box.setWindowTitle("Phase 1 Completed (TLU)")

        msg_box.setText(
            f"Phase 1 (UV-VIS) completed successfully.\n"
            f"Fixed thickness: {tlu_res.optimal_thickness:.2f} nm.\n\n"
            f"All properties (n, k, thickness) below 2500 nm are now strictly FIXED.\n"
            f"Do you want to launch the Global IR Model extension (> 2500 nm)?"
        )

        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)

        msg_box.setDefaultButton(yes_btn)

        QTimer.singleShot(5000, yes_btn.click)

        reply = msg_box.exec()

        if reply == int(QMessageBox.StandardButton.No) or reply == QMessageBox.StandardButton.No:
            self.logger.info("IR extension canceled by user. Conservation of the complete TLU model.")

            self._on_finished(tlu_res)

            return

        self.lbl_status.setText(" Phase 2/2: Global Model Refinement IR (> 2500 nm)...")

        # Restore full wavelength range (TLU was fitted on <= 2200 nm only)

        tlu_res.config.lambda_max_fit = None

        if self.target_data is not None:
            tlu_res.config.target_data = self.target_data.copy()

            tlu_res.config.lambda_min = float(self.target_data["lambda"].min())

            tlu_res.config.lambda_max = float(self.target_data["lambda"].max())

            self.logger.info(
                f"  Phase 2: full-range data "
                f"[{tlu_res.config.lambda_min:.0f}, {tlu_res.config.lambda_max:.0f}] nm "
                f"({len(self.target_data)} pts)"
            )

        self._best_rmse_display = 1e12

        self._total_iterations = 0

        self._worker2 = IRGlobalModelWorker(tlu_res.config, tlu_res, logger=self.logger)

        # Removed live visualization logic

        # Re-connect to standard UI handlers

        self._worker2.finished.connect(self._on_finished)

        self._worker2.error.connect(self._on_error)

        self._worker2.progress.connect(self._on_progress)

        self._worker2.evals_update.connect(self._on_evals_update)

        self._worker2.curve_update.connect(self._on_curve_update)

        self._thread2 = QThread()

        self._worker2.moveToThread(self._thread2)

        self._thread2.started.connect(self._worker2.run)

        self._worker2.finished.connect(self._thread2.quit)

        self._worker2.finished.connect(self._worker2.deleteLater)

        self._thread2.finished.connect(self._thread2.deleteLater)

        self._thread2.finished.connect(self._on_thread_finished)

        self._thread2.start()

    # =========================================================================

    # EXCEL EXPORT

    # =========================================================================

    def _build_uncertainty_content(self, df: pd.DataFrame) -> dict[str, str]:
        """Build uncertainty metrics for HTML export from available delta columns."""

        uncertainty_content: dict[str, str] = {}

        if "delta_n_res" in df.columns:
            dn = df["delta_n_res"].values

            uncertainty_content["Deltan Max (3-way)"] = f"{np.max(dn):.4f}"

            uncertainty_content["Deltan Mean (3-way)"] = f"{np.mean(dn):.4f}"

            uncertainty_content["Deltan Min (3-way)"] = f"{np.min(dn[dn > 0]):.4f}" if np.any(dn > 0) else "0.0000"

        if "delta_k_res" in df.columns:
            dk = df["delta_k_res"].values

            uncertainty_content["Deltak Max (3-way)"] = f"{np.max(dk):.4f}"

            uncertainty_content["Deltak Mean (3-way)"] = f"{np.mean(dk):.4f}"

        if "delta_n" in df.columns and "delta_k" in df.columns:
            uncertainty_content["Deltan Max (50-50 vs 90% T)"] = f"{np.max(df['delta_n'].values):.4f}"

            uncertainty_content["Deltan Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_n'].values):.4f}"

            uncertainty_content["Deltak Max (50-50 vs 90% T)"] = f"{np.max(df['delta_k'].values):.4f}"

            uncertainty_content["Deltak Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_k'].values):.4f}"

        if not uncertainty_content:
            uncertainty_content["Status"] = "Not calculated"

        return uncertainty_content

    def _export_results_html(self, res: OptimizationResults, rmse_val: float, html_path: str) -> None:
        """Export INDEX HTML report; logs errors internally to preserve legacy flow."""

        try:
            # Prepare Dispersion Table

            if res.tlu_params:
                disp_data = [
                    {
                        "Parameter": "Eg",
                        "Value": f"{res.tlu_params.Eg:.4f}",
                        "Unit": "eV",
                    },
                    {
                        "Parameter": "eps_inf",
                        "Value": f"{res.tlu_params.eps_inf:.4f}",
                        "Unit": "-",
                    },
                    {"Parameter": "A", "Value": f"{res.tlu_params.A:.4f}", "Unit": "-"},
                    {"Parameter": "C", "Value": f"{res.tlu_params.C:.4f}", "Unit": "-"},
                    {
                        "Parameter": "E0",
                        "Value": f"{res.tlu_params.E0:.4f}",
                        "Unit": "eV",
                    },
                ]

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                disp_data = [
                    {
                        "Parameter": "Mode",
                        "Value": "IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement",
                        "Unit": "-",
                    },
                    {"Parameter": "Thickness (nm)", "Value": f"{res.optimal_thickness:.4f}", "Unit": "nm"},
                ]

                if not is_phase2_ir:
                    disp_data.append(
                        {
                            "Parameter": "Knots",
                            "Value": f"{res.optimization_stats.get('num_knots', 'N/A')}",
                            "Unit": "-",
                        }
                    )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                disp_data.extend(
                    [
                        {"Parameter": "Sellmeier A (Const)", "Value": f"{sp[0]:.6f}", "Unit": "-"},
                        {"Parameter": "Sellmeier B1", "Value": f"{sp[1]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C1", "Value": f"{sp[2] ** 2:.8e}", "Unit": "m2"},
                        {"Parameter": "Sellmeier B2", "Value": f"{sp[3]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C2", "Value": f"{sp[4] ** 2:.8e}", "Unit": "m2"},
                    ]
                )

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    disp_data.append({"Parameter": name, "Value": f"{val:.8e}", "Unit": "-"})

            # Uncertainty statistics from delta_n_res/delta_k_res (3-way) or delta_n/delta_k (50-50 vs 90% T)
            uncertainty_content = self._build_uncertainty_content(res.df_results)

            sections = [
                {
                    "title": "Optimization Methodology",
                    "type": "kv",
                    "content": {
                        "Algorithm": "Hybrid (PGlobal + L-BFGS-B)",
                        "Gradient Mode": "Analytic (Exact Derivatives)",
                        "Speedup": "~200x vs Finite Difference",
                        "Precision": "Machine Precision (Float64)",
                        "Convergence": "High (Jacobian-Assisted)",
                    },
                },
                {
                    "title": "Algorithm Details",
                    "type": "text",
                    "content": (
                        "The optimization employs a robust three-stage strategy: "
                        "1. <strong>PGlobal (Global Search)</strong>: Uses a stochastic differential evolution approach to find the global minimum region. "
                        "2. <strong>L-BFGS-B (Local Polish)</strong>: Uses the <strong>Analytic Gradient</strong> to refine the solution with high precision. "
                        "3. <strong>Coordinate Descent (Fine Tuning)</strong>: A final local descent step to escape narrow local minima. "
                        "4. <strong>Physical Accuracy</strong>: Rigorously accounts for <strong>Incoherent Backside Reflection</strong> in the substrate for both Transmission and Reflection (T = T_single * T_back / (1 - R_single*R_back)). "
                        "The analytic gradient computes the exact derivatives of the Tauc-Lorentz-Urbach model and Transfer Matrix Method interactions (including backside effects) using the chain rule, "
                        "eliminating numerical noise and providing significant performance improvements over traditional finite-difference methods."
                    ),
                },
                {
                    "title": "Optimization Summary",
                    "type": "kv",
                    "content": {
                        "Date": certus_timestamp_display(),
                        "Source File": Path(res.config.source_file).name,
                        "Final RMSE": f"{rmse_val:.6f}",
                        "Execution Time": f"{res.execution_time:.2f} s",
                        "Model": "IR Global Model (Sellmeier + k 8p)"
                        if (
                            res.tlu_params is None
                            and (
                                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
                            )
                        )
                        else "Tauc-Lorentz-Urbach",
                        "substrate": res.config.substrate,
                    },
                },
                {
                    "title": "Dispersion Parameters",
                    "type": "table",
                    "content": disp_data,
                },
                {
                    "title": "Uncertainty Analysis",
                    "type": "kv",
                    "content": uncertainty_content,
                },
            ]

            # --- 3. Add Beam Analysis Section (if available) ---

            if hasattr(self, "last_beam_results") and self.last_beam_results:
                beam_table = []

                # Sort by MSE

                sorted_beam = sorted(self.last_beam_results, key=lambda x: x["mse"])

                # Take top 20 or all

                for b in sorted_beam[:20]:
                    beam_table.append(
                        {
                            "Thickness (nm)": f"{b['d']:.2f}",
                            "MSE": f"{b['mse']:.2e}",
                            "Status": "Best" if b == sorted_beam[0] else "",
                        }
                    )

                sections.append(
                    {
                        "title": "Beam Analysis (Thickness Scan)",
                        "type": "table",
                        "content": beam_table,
                    }
                )

                # Add explainer

                sections.append(
                    {
                        "title": "Beam Analysis Details",
                        "type": "text",
                        "content": (
                            f"Beam Analysis scanned <strong>{len(self.last_beam_results)}</strong> thickness values. "
                            "The table above shows the best solutions found. "
                            "This technique validates the global minimum by ensuring no better solution exists at other thicknesses."
                        ),
                    }
                )

            # --- 4. Add Physical Model Section ---

            _is_phase2_ir = res.tlu_params is None and (
                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
            )

            if _is_phase2_ir:
                sections.append(
                    {
                        "title": "Physical Model: Sellmeier 2-pole + k 8-parameter",
                        "type": "kv",
                        "content": {
                            "n(lambda)": "Sellmeier 2-pole: n2 = A + B₁lambda2/(lambda2-L₁2) + B₂lambda2/(lambda2-L₂2)",
                            "k(lambda)": "Empirical: exponentials + super-Gaussian peak (soft-saturated)",
                            "Range": "Full spectrum (Phase 2/2 IR Global Model)",
                        },
                    }
                )

            else:
                sections.append(
                    {
                        "title": "Physical Model: Tauc-Lorentz-Urbach",
                        "type": "kv",
                        "content": {
                            "Formula": "2(E) = AE0C(E-Eg)2 / [(E2-E02)2 + C2E2]  (1/E)",
                            "Urbach Tail": "Exponential tail below Eg (extends absorption)",
                            "Eg": "Band Gap Energy (eV)",
                            "eps_inf": "High-frequency dielectric constant",
                            "A": "Amplitude (Strength of oscillator)",
                            "E0": "Peak Energy (eV)",
                            "C": "Broadening (eV)",
                        },
                    }
                )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                _method = (res.optimization_stats or {}).get("method", "")

                _skip_phase5 = "PGLOBAL" in _method or "Sellmeier+k" in _method

                if not _skip_phase5:
                    sections.append(
                        {
                            "title": "Phase 5: Sellmeier Smooth Fit (n)",
                            "type": "text",
                            "content": (
                                "At the end of the optimization, <strong>n</strong> is strictly fitted to a 3-pole <strong>Sellmeier Law</strong> over the entire spectrum "
                                "to guarantee perfectly smooth and physical values: <br/>"
                                "<code>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2) + (B3lambda2) / (lambda2 - C3)</code><br/>"
                                "The extinction coefficient <strong>k</strong> is then re-optimized point-by-point to perfectly match experimental (R,T) targets with the fixed Sellmeier <strong>n</strong>."
                            ),
                        }
                    )

            figures = [self.plot_spectrum, self.plot_nk]

            if hasattr(self, "plot_delta_n"):
                figures.append(self.plot_delta_n)

            if generate_html_report(html_path, "CERTUS-INDEX Report", sections, figures):
                self.logger.info(f"HTML report saved: {html_path}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"HTML export failed:{e}", exc_info=True)

    def export_results(self) -> None:
        """Standardized Auto-Export (Excel + HTML)"""

        if not get_export_config():
            return

        if not self.latest_results:
            return

        res = self.latest_results

        # Calculate RMSE for filename

        rmse_val = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Generate Filenames

        try:
            reports_dir = get_resource_path("reports")

            os.makedirs(reports_dir, exist_ok=True)

            ts = certus_timestamp_file()

            try:
                src_name = Path(res.config.source_file).stem

                base_filename = f"Report_INDEX_{src_name}_{ts}_RMSE_{rmse_val:.5f}"

            except NUMERICAL_FAULT_EXCEPTIONS:
                base_filename = f"Report_INDEX_{ts}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(reports_dir) / (base_filename + ".xlsx"))

            html_path = str(Path(reports_dir) / (base_filename + ".html"))

            self.lbl_status.setText("Saving Reports...")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Filename generation error: {e}")

            return

        # --- 1. EXCEL EXPORT ---

        try:
            tlu = res.tlu_params

            if tlu:
                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Eg": [f"{tlu.Eg:.4f}"],
                    "eps_inf": [f"{tlu.eps_inf:.4f}"],
                    "A": [f"{tlu.A:.4f}"],
                    "C": [f"{tlu.C:.4f}"],
                    "E0": [f"{tlu.E0:.4f}"],
                }

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Mode": ["IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement"],
                    "Thickness (nm)": [f"{res.optimal_thickness:.4f}"],
                    "Thickness Variation (%)": [f"{getattr(res, 'thickness_variation', 0):+.2f}"],
                }

                if not is_phase2_ir:
                    summary_data["Knots"] = [getattr(res, "num_knots", "N/A")]

            summary_data["Substrate (material)"] = [res.config.substrate]

            if res.config.substrate == "Sapphire (Al2O3)":
                summary_data["Sapphire n(lambda) source"] = ["Sellmeier equation (materials_v1.json, id=3)"]

                summary_data["Sapphire k column in file"] = ["yes" if _SAPPHIRE_FILE_HAS_K_COLUMN else "no"]

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                summary_data["Sellmeier_A"] = [f"{sp[0]:.6f}"]

                summary_data["Sellmeier_B1"] = [f"{sp[1]:.8e}"]

                summary_data["Sellmeier_C1"] = [f"{sp[2] ** 2:.8e}"]

                summary_data["Sellmeier_B2"] = [f"{sp[3]:.8e}"]

                summary_data["Sellmeier_C2"] = [f"{sp[4] ** 2:.8e}"]

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    summary_data[name] = [f"{val:.8e}"]

            df_summary = pd.DataFrame(summary_data)

            df_data = res.df_results.copy()

            from certus_data import ReportSection, build_standard_report

            try:
                if bool(getattr(res.config, "use_normalized", False)):
                    self.set_validation_status("WARNING_DATA_NORMALIZED")
                    self.add_validation_warning("Input data normalized before optimization/export.")
                else:
                    self.set_validation_status("OK")
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
                self.logger.warning("INDEX validation status update skipped during export: %s", exc)

            run_manifest = None
            try:
                run_manifest = (res.optimization_stats or {}).get("run_manifest")
            except (TypeError, AttributeError):
                run_manifest = None

            report_result = build_standard_report(
                [
                    ReportSection("Summary", kind="table", content=df_summary, sheet_name="Summary"),
                    ReportSection("Data", kind="table", content=df_data, sheet_name="Data"),
                ],
                excel_path=excel_path,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )
            if report_result.get("excel"):
                self.logger.info(f"Excel report saved: {excel_path}")
            else:
                self.logger.error("Excel export blocked/failed: missing or incomplete run manifest.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Excel export failed:{e}", exc_info=True)

        # --- 2. HTML EXPORT ---
        self._export_results_html(res, rmse_val, html_path)

        self.lbl_status.setText(f" Saved: {base_filename}")

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

    def detach_current_plot(self) -> None:
        """Detach current plot or data table in a separate window"""

        current_widget = self.tabs.currentWidget()

        if current_widget is None:
            return

        current_index = self.tabs.currentIndex()

        # 1. OPTION : TAB SPECTRUM (Index 0)

        if current_index == 0:
            plot_name = "spectrum"

            plot_title = "Transmission / Reflection Spectrum"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            detached_plot_copy = clone_plot_widget(self.plot_spectrum)

            if detached_plot_copy:
                detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

                detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

                self.detached_plot_windows[plot_name] = detached_window

                detached_window.show()

        # 2. OPTION : TAB N_K (Index 1) -> Split into two windows!

        elif current_index == 1:
            screen = QApplication.primaryScreen().availableGeometry()

            win_w = screen.width() // 2 - 10

            win_h = screen.height() - 100

            # Detach N (Left Axis)

            if "nk_n" not in self.detached_plot_windows or not self.detached_plot_windows["nk_n"].isVisible():
                n_clone = clone_plot_widget(self.plot_nk, title_override="Refractive Index n")

                win_n = DetachedPlotWindow(n_clone, parent=self, title="Refractive Index n")

                win_n.closed_signal.connect(functools.partial(self.reattach_plot, "nk_n"))

                self.detached_plot_windows["nk_n"] = win_n

                win_n.setGeometry(screen.x(), screen.y() + 40, win_w, win_h)

                win_n.show()

                n_clone.setLabel("left", "Refractive Index n", color=CertusTheme.PRIMARY)

            else:
                self.detached_plot_windows["nk_n"].raise_()

            # Detach K (Right Axis)

            if "nk_k" not in self.detached_plot_windows or not self.detached_plot_windows["nk_k"].isVisible():
                k_clone = CertusScientificPlot(
                    None,
                    title="Extinction Coefficient k",
                    y_label="k",
                    x_label="lambda (nm)",
                    axisItems={"left": KLogAxisItem(orientation="left")},
                )

                if hasattr(self, "_vb_k"):
                    for item in self._vb_k.addedItems:
                        if isinstance(item, pg.PlotCurveItem):
                            x, y = item.getData()

                            if x is not None and y is not None:
                                pen = item.opts.get("pen", pg.mkPen("y"))

                                k_clone.plot(x, y, pen=pen, name=item.name())

                win_k = DetachedPlotWindow(k_clone, parent=self, title="Extinction Coefficient k")

                win_k.closed_signal.connect(functools.partial(self.reattach_plot, "nk_k"))

                self.detached_plot_windows["nk_k"] = win_k

                win_k.setGeometry(screen.x() + win_w + 20, screen.y() + 40, win_w, win_h)

                win_k.show()

                k_clone.setYRange(-6.0, -2.0, padding=0)

            else:
                self.detached_plot_windows["nk_k"].raise_()

        # 3. OPTION : TAB DATA (Index 3)

        elif current_index == 3 or self.tabs.tabText(current_index) == "Data":
            plot_name = "data_table"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            # Create a detached table (Excel-like with copy support)

            table_copy = ExcelTableWidget()

            table_copy.setColumnCount(self.table_res.columnCount())

            table_copy.setRowCount(self.table_res.rowCount())

            # Copy headers

            labels = []

            for i in range(self.table_res.columnCount()):
                item = self.table_res.horizontalHeaderItem(i)

                labels.append(item.text() if item else f"C{i}")

            table_copy.setHorizontalHeaderLabels(labels)

            # Copy content

            try:
                for r in range(self.table_res.rowCount()):
                    for c in range(self.table_res.columnCount()):
                        item = self.table_res.item(r, c)

                        if item:
                            table_copy.setItem(r, c, QTableWidgetItem(item.text()))

            except NUMERICAL_FAULT_EXCEPTIONS:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            win_data = DetachedPlotWindow(table_copy, parent=self, title="Result Data Table")

            # Apply some extra styling to the detached table to make it fit

            table_copy.setStyleSheet(f"background: {CertusTheme.SURFACE}; border: none;")

            win_data.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = win_data

            win_data.resize(900, 700)

            win_data.show()

    def reattach_plot(self, plot_name: str) -> None:
        """Reattach a detached plot"""

        if plot_name not in self.detached_plot_windows:
            return

        detached_window = self.detached_plot_windows[plot_name]

        detached_window.deleteLater()

        del self.detached_plot_windows[plot_name]

    def on_toggle_details(self, checked) -> None:
        """Show/Hide log"""

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

        if hasattr(self, "right_splitter"):
            if checked:
                self.right_splitter.setSizes([600, 200])

            else:
                self.right_splitter.setSizes([1000, 0])

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""

        # Shutdown ThreadPoolExecutor if exists

        if hasattr(self, "_executor") and self._executor is not None:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                if hasattr(self, "logger") and self.logger:
                    self.logger.warning(f"Error shutting down executor: {e}")

            finally:
                self._executor = None

        # Cleanup optimization worker and thread

        self._cleanup_worker()

        # Cleanup beam worker and thread

        if getattr(self, "_beam_worker", None):
            self._beam_worker.stop()

        beam_thread = getattr(self, "_beam_thread", None)

        if beam_thread is not None and beam_thread.isRunning():
            beam_thread.quit()

            if not beam_thread.wait(2000):
                self.logger.critical(
                    "Beam thread did not stop within 2s in closeEvent - skipping terminate() to avoid unsafe thread kill."
                )

        try:
            self.killTimer(self._log_timer_id)

        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.logger.info("Application closed.")

        super().closeEvent(event)

    # =========================================================================

    # SAVE / LOAD CONFIGURATION

    # =========================================================================

    # save_config / load_config are inherited from CertusBaseApp and driven by
    # the _collect_config / _apply_config / _post_*_config hooks below.

    def _get_config_file_filter(self) -> str:

        return "JSON (*.json)"

    def _collect_config(self) -> dict:
        """Serialize the CERTUS_INDEX widget state to a JSON-ready dict."""

        params_values = []

        if hasattr(self, "input_params"):
            params_values = [s.value() for s in self.input_params]

        opt_block = {}

        if hasattr(self, "input_max_feval"):
            opt_block["max_feval"] = int(self.input_max_feval.value())

        return {
            "version": __version__,
            "substrate": self.cb_sub.currentText() if hasattr(self, "cb_sub") else "",
            "frosted": self.rb_frosted_glass.isChecked() if hasattr(self, "rb_frosted_glass") else False,
            "data_type": self.cb_data_type.currentText() if hasattr(self, "cb_data_type") else "",
            "file_loaded": getattr(self, "source_file_path", None),
            "thickness_min": self.sb_dmin.value() if hasattr(self, "sb_dmin") else 50.0,
            "thickness_max": self.sb_dmax.value() if hasattr(self, "sb_dmax") else 1000.0,
            "normalized": self.chk_normalized.isChecked() if hasattr(self, "chk_normalized") else True,
            "exclude_oh": self.chk_exclude.isChecked() if hasattr(self, "chk_exclude") else False,
            "exclude_min": self.sb_ex_min.value() if hasattr(self, "sb_ex_min") else None,
            "exclude_max": self.sb_ex_max.value() if hasattr(self, "sb_ex_max") else None,
            "model_type": (self.model_combo.currentText() if hasattr(self, "model_combo") else "TLU"),
            "params": params_values,
            "optimization": opt_block,
            "weight_T": float(self.sb_weight_T.value()) if hasattr(self, "sb_weight_T") else 1.0,
            "weight_R": float(self.sb_weight_R.value()) if hasattr(self, "sb_weight_R") else 1.0,
        }

    def _apply_config(self, cfg: dict) -> None:
        """Restore CERTUS_INDEX widget state from a loaded config dict.

        Note: the measured spectrum file referenced by ``file_loaded`` is
        intentionally NOT auto-loaded to avoid broken paths when sharing
        configs across machines.
        """

        sub = cfg.get("substrate")

        if sub and hasattr(self, "cb_sub"):
            idx = self.cb_sub.findText(str(sub))

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

        if cfg.get("frosted", False):
            self.rb_frosted_glass.setChecked(True)

        else:
            self.rb_standard.setChecked(True)

        self.sb_dmin.setValue(cfg.get("thickness_min", 10.0))

        self.sb_dmax.setValue(cfg.get("thickness_max", 1000.0))

        self.chk_normalized.setChecked(cfg.get("normalized", False))

        self.chk_exclude.setChecked(cfg.get("exclude_oh", False))

        if not cfg.get("frosted", False):
            wt = cfg.get("weight_T")

            if wt is not None and hasattr(self, "sb_weight_T"):
                self.sb_weight_T.setValue(float(wt))

            wr = cfg.get("weight_R")

            if wr is not None and hasattr(self, "sb_weight_R"):
                self.sb_weight_R.setValue(float(wr))

            self._persist_index_weight_settings()

        # Model & Optim params are handled by PGLOBAL engine and not exposed in UI config anymore.

    def _post_save_config(self, filename: str) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Saved: {Path(filename).name}")

        QMessageBox.information(self, "Saved", f"Configuration saved to {Path(filename).name}")

    def _post_load_config(self, filename: str, config: dict) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Loaded: {Path(filename).name}")

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Configure logging with centralized helper

    setup_module_logging("CERTUS_INDEX", log_file="certus_index.log")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-INDEX", app=app)

    # --- SPLASH SCREEN ---

    from PyQt6.QtGui import QPixmap

    from PyQt6.QtWidgets import QSplashScreen

    # Create simple splash if no image

    splash_pix = QPixmap(get_resource_path("certus.svg"))

    if splash_pix.isNull():
        splash_pix = QPixmap(get_resource_path("certus.ico"))

    if splash_pix.isNull():
        splash_pix = QPixmap(400, 200)

        splash_pix.fill(Qt.GlobalColor.white)

    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)

    splash.show()

    splash.showMessage(
        "Initializing Physics Engine...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    # Wait for background JIT warmup (launched by bootstrap_app)

    logging.info("Waiting for JIT Warmup...")

    from certus_core import wait_warmup

    wait_warmup()

    splash.showMessage(
        "Starting User Interface...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    w = CertusIndexApp()

    w.show()

    splash.finish(w)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            # Try load_config first (JSON), fallback to load_file (CSV/Excel)

            if f.lower().endswith(".json"):
                QTimer.singleShot(100, lambda: w.load_config(f))

            else:
                QTimer.singleShot(100, lambda: w.load_file(f))

    sys.exit(app.exec())
