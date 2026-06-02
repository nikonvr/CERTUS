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
    _get_substrate_n_array_index,
    normalize_index_config,
    calculate_index_rmse,
)

class substrateMode(Enum):
    """substrate mode"""

    STANDARD = auto()  # Classic transparent substrate

    FROSTED_GLASS = auto()  # Infinite substrate (reflection only)


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
