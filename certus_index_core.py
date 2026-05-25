from pathlib import Path
from certus_core import create_module_environment
import time
import os
from concurrent.futures import ThreadPoolExecutor

_env = create_module_environment(__file__, 'CERTUS_INDEX_CORE')
script_dir = _env['script_dir']

from numba import njit, prange
import logging
import numpy as np
import pandas as pd
from enum import Enum, auto
from typing import Any

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
from certus_index_utils import (
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
    _get_substrate_n_array_index,
    normalize_index_config,
    calculate_index_rmse,
)

class substrateMode(Enum):
    """substrate mode"""

    STANDARD = auto()  # Classic transparent substrate

    FROSTED_GLASS = auto()  # Infinite substrate (reflection only)


class OptimizationConfig:
    """Configuration for INDEX optimization - Supports R, T, R+T, Frosted Glass, TLU and Spline modes"""

    __slots__ = [
        "target_data",
        "data_type",
        "substrate",
        "substrate_sellmeier_id",
        "substrate_sellmeier_coeffs",
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

        self.substrate = canonicalize_substrate_label(substrate) or str(substrate)
        self.substrate_sellmeier_id = substrate_sellmeier_id(self.substrate)
        self.substrate_sellmeier_coeffs = substrate_sellmeier_coeffs(self.substrate)

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

        # 3. Substrate transmission safety mask (only when use_norm is True)

        if self.use_norm:
            if self.data_type == DataType.TRANSMISSION:
                mask &= (self.T_sub > T_SUB_MIN_T_NORM)
            elif self.data_type == DataType.REFLECTION:
                mask &= (self.T_sub > T_SUB_MIN_R_NORM)
            else:  # DataType.BOTH
                mask &= (self.T_sub > T_SUB_MIN_R_NORM)

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
            R_c = calculate_reflection_array(self.wls, n, k, self.thickness, self.n_sub)

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

        from scipy.interpolate import CubicSpline
        spline = CubicSpline(knot_lam, log_k_knot, bc_type="natural", extrapolate=True)
        log_k = spline(self.obj.wl_um)

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

            from scipy.interpolate import CubicSpline
            spline_local = CubicSpline(knot_lam_local, log_k_knot, bc_type="natural", extrapolate=True)
            log_k_local = spline_local(self.obj.wl_um)

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

        return grad_full

# ---------------------------------------------------------


# Install exception handler




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
        f"[CERTUS INDEX] ATTENTION : impossible de load example/sapphire fresnel.xlsx "
        f"({_e_sap}). Canonical sapphire absorbing substrate mode will be disabled.",
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
            # Use the more general IR global gradient kernel which supports absorption.
            # _compute_ir_global_cost_gradient_kernel returns a vector of size
            # (1 + dn_dp.shape[0] + dk_dp.shape[0]) when compute_thickness_gradient=True.
            # For TLU, dn_dp and dk_dp SHARE the same 6 parameters [Eg, A, E0, C, Eu, eps_inf].
            # mse_grad_raw layout: [thickness, dn0..dn5, dk0..dk5] (size 1 + 6 + 6 = 13)
            # We accumulate into grad[0:7] = [thickness, Eg, A, E0, C, Eu, eps_inf].

            mse_grad_raw = _compute_ir_global_cost_gradient_kernel(
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
                True,  # compute_thickness_gradient
            )

            # Map result back to (7,) TLU gradient vector.
            mse_grad = np.zeros(7, dtype=np.float64)
            mse_grad[0] = mse_grad_raw[0]
            mse_grad[1:7] += mse_grad_raw[1:7]
            mse_grad[1:7] += mse_grad_raw[7:13]

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
                    "event=tlu_k_penalty eval=%d remaining_logs=%d k_max=%.6g k_limit=%.4g penalty_power=%.0f Eg=%.4f Eu=%.4f E0=%.4f frac_E_gt_Eg=%.2f eps2_max=%.4g eps2_at_kmax=%.4g penalty=%.4g",
                    int(self.n_evals),
                    int(self._tlu_explode_logs_left),
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
                    R_calc = calculate_reflection_array(self.wavelengths, n_calc, k_calc, thickness, self.n_substrate)

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

            logging.debug("event=index_gradient_opt status=fallback reason=%s", e)

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

            except NUMERICAL_FAULT_EXCEPTIONS :
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
                logging.error("event=pglobal_sampling status=failed mode=parallel reason=%s", e)

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

    def _should_stop_optimization(self, start_time: float, iteration: int) -> bool:
        """Return True when the main optimize loop should stop."""
        if self.stop_event and self.stop_event.is_set():
            return True
        if time.time() - start_time > self.config.max_time:
            return True
        if self.n_evals >= self.config.max_feval:
            return True
        return False

    def _make_monitor_callback(self, callback):
        """Wrap the live callback for sequential local search."""
        if not callback:
            return None

        def monitor(xk):
            return callback(Sample(xk, self.objective(xk)))

        return monitor

    def _local_search_budget(self) -> int:
        """Budget remaining for a local refinement step."""
        return min(self.config.local_search_budget, self.config.max_feval - self.n_evals)

    def _prepare_iteration_batches(self, n_samples: int):
        """Sample, sort and reduce the active set for one optimize iteration."""
        new_samples = self._sample_uniform(n_samples)
        if not new_samples:
            return None

        self._all_samples.extend(new_samples)
        self._all_samples.sort(key=lambda s: s.y)

        n_keep = max(int(len(self._all_samples) * self.config.reduction_ratio), self.n_workers * 2)
        active_samples = self._all_samples[:n_keep]
        x_batch = np.array([s.x for s in active_samples])
        y_batch = np.array([s.y for s in active_samples])
        cand_x, cand_y = self.clusterer.process_batch(x_batch, y_batch, self._n_total_samples)
        return n_keep, cand_x, cand_y

    def _callback_best_so_far(self, callback, best_ever):
        """Emit the best sample available for iteration progress."""
        if callback and len(self._all_samples) > 0:
            best_so_far = self._all_samples[0]
            callback(best_so_far if best_ever is None or best_so_far.y <= best_ever.y else best_ever)

    def _run_sequential_local_search(self, cand_x, cand_y, n_dispatch: int, callback, best_ever):
        """Run local search sequentially for the best candidates."""
        idx_sorted = np.argsort(cand_y)[:n_dispatch]
        for idx in idx_sorted:
            if self.stop_event and self.stop_event.is_set():
                break
            x_start = cand_x[idx]
            searcher = GradientSearcher(
                self.objective,
                self.bounds,
                self.config,
                self.stop_event,
                monitor_callback=self._make_monitor_callback(callback),
            )
            try:
                x_opt, f_opt, n_ev = searcher.search(x_start, self._local_search_budget())
                self.n_evals += n_ev
                self.clusterer.add_cluster_result(x_opt, f_opt)
                if best_ever is None or f_opt < best_ever.y:
                    best_ever = Sample(x=x_opt, y=f_opt)
                    if callback:
                        callback(best_ever)
            except (ValueError, TypeError, RuntimeError, ArithmeticError, OverflowError) as e:
                logging.error("event=pglobal_local_search status=failed mode=sequential reason=%s", e, exc_info=True)
        return best_ever

    def _run_parallel_local_search(self, cand_x, cand_y, n_dispatch: int, callback, best_ever):
        """Run local search in the executor for the best candidates."""
        idx_sorted = np.argsort(cand_y)[:n_dispatch]
        futures = {}
        for idx in idx_sorted:
            if self.stop_event and self.stop_event.is_set():
                break
            x_start = cand_x[idx]
            searcher = GradientSearcher(
                self.objective,
                self.bounds,
                self.config,
                self.stop_event,
                monitor_callback=None,
            )
            futures[self._executor.submit(searcher.search, x_start, self._local_search_budget())] = x_start
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
                logging.error("event=pglobal_local_search status=failed mode=parallel reason=%s", e, exc_info=True)
        return best_ever

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
                logging.debug("event=index_initial_guess status=failed reason=%s", e)

        # Limit Numba threads when using ThreadPoolExecutor to avoid CPU oversubscription

        _numba_restore = None

        if self.n_workers > 1:
            import numba

            nb_cores = _get_cpu_count()

            try:
                _numba_restore = int(numba.get_num_threads())

            except NUMERICAL_FAULT_EXCEPTIONS :
                _numba_restore = _numba_set_threads_clamped(nb_cores)

            # nb_cores // n_workers peut depasser 31 ; restauration utilisait nb_cores brut -> ValueError

            numba.set_num_threads(_numba_set_threads_clamped(max(1, nb_cores // self.n_workers)))

            self._executor = ThreadPoolExecutor(max_workers=self.n_workers)

        else:
            self._executor = None

        try:
            for iteration in range(max_iter):
                if self._should_stop_optimization(start_time, iteration):
                    break

                n_samples = self.config.n_samples_per_iter
                if iteration == 0:
                    n_samples = int(n_samples * 1.5)

                prepared = self._prepare_iteration_batches(n_samples)
                if not prepared:
                    break
                n_keep, cand_x, cand_y = prepared
                n_dispatch = min(len(cand_y), self.n_workers)

                self._callback_best_so_far(callback, best_ever)

                if self.n_workers <= 1 and n_dispatch > 0:
                    best_ever = self._run_sequential_local_search(cand_x, cand_y, n_dispatch, callback, best_ever)
                elif n_dispatch > 0 and self._executor:
                    best_ever = self._run_parallel_local_search(cand_x, cand_y, n_dispatch, callback, best_ever)

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

