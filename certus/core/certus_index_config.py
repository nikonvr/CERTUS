from certus.core.certus_core import create_module_environment
import scipy
import scipy.optimize

_env = create_module_environment(__file__, 'CERTUS_INDEX_CORE')
script_dir = _env['script_dir']

import numpy as np
import pandas as pd
from enum import Enum, auto

from certus.core.certus_core import (
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
    substrate_sellmeier_id,
)
from certus_physics import (
    TLUParameters,
)
from certus.utils.certus_index_utils import (
    DataType,
)
from typing import Any

class substrateMode(Enum):
    """substrate mode"""

    STANDARD = auto()  # Classic transparent substrate

    FROSTED_GLASS = auto()  # Infinite substrate (reflection only)


# Fast Phase 2 IR compromise (HPO over 7 XLSX files)  max_feval=200k, max_time=300s, sub 5k/45s/80
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
        "data_type",
        "dispersion_mode",
        "exclude_max",
        "exclude_min",
        "fixed_thickness",
        "high_precision",
        "k_sub_data",
        "lambda_max",
        "lambda_max_fit",
        "lambda_min",
        "min_knot_dist",
        "n_sub_data",
        "nk_max",
        "nk_min",
        "num_knots",
        "phase2_pglobal_overrides",
        "random_seed",
        "source_file",
        "substrate",
        "substrate_mode",
        "substrate_sellmeier_coeffs",
        "substrate_sellmeier_id",
        "substrate_thickness_nm",
        "target_data",
        "thickness_max",
        "thickness_min",
        "use_normalized",
        "weight_R",
        "weight_T",
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

        # The UI may swap min/max: normalise to keep the SciPy bounds valid

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
        "df_results",
        "execution_time",
        "final_mse",
        "k_8p_params",
        "k_T",
        "k_spline_knots_lambda_um",
        "k_spline_knots_values",
        "n_T",
        "optimal_thickness",
        "optimization_stats",
        "p_opt_T",
        "sellmeier_params",
        "tlu_params",
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
        sellmeier_params: Any = None,
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
