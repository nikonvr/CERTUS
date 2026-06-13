# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# P1 boundary: safe edits should first target small pure helpers, typing, logging,
# and UX labels. Keep numerical kernels and workflow orchestration stable unless
# a dedicated extraction/test plan exists.

# =========================================================================================

from typing import Any
import functools
import logging
import os
import time
from pathlib import Path

import multiprocessing
import sys
import traceback

from certus.core.certus_core import create_module_environment

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
from certus.core.certus_index_core import (
    substrateMode,
    OptimizationConfig,
    OptimizationResults,
    IRGlobalObjective,
    Phase23SplineObjective,
    Phase23Pass2SplineObjective,
    TLUObjective,
    GradientSearcher,
    PGlobalOptimizerINDEX,
    SubsetOptimTask,
    calculate_relative_R_normalization,
    _optimize_point_kernel,
    _optimize_all_points_batch,
)
from certus.workers.certus_index_workers import IRPGlobalCallback, IRStage2Callback, IRSplineCallback, IRGlobalModelWorker, Phase1Callback, Phase2PolishCallback, OptimizationWorker, IndexBeamAnalysisWorker
from certus.ui.certus_index_ui import (
    CertusIndexApp,
    _detected_data_type_label,
    _source_type_label,
    _prepare_nk_plot_inputs,
    _update_lambda_bounds_from_target_data,
    _set_spectrum_plot_title,
    _update_loaded_file_label,
)



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
    __version__,
    get_resource_path,
    get_safe_worker_count,
    _get_cpu_count,
    certus_timestamp_display,
    certus_timestamp_file,
)

from certus.utils.certus_data import (
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

from certus.core.certus_core import CertusFacadeModule
import certus.core.certus_index_core as certus_index_core
import certus.workers.certus_index_workers as certus_index_workers
import certus.ui.certus_index_ui as certus_index_ui
import certus.utils.certus_index_utils as certus_index_utils

sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_index_core,
    certus_index_workers,
    certus_index_ui,
    certus_index_utils
])

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Configure logging with centralized helper
    from certus.core.certus_core import setup_module_logging
    setup_module_logging("CERTUS_INDEX", log_file="certus_index.log")

    import warnings
    warnings.filterwarnings("once", category=UserWarning)
    warnings.filterwarnings("ignore", message="First-class function type feature is experimental")

    # Reduce console noise from the deepest optimizer warnings without hiding real failures.
    warnings.filterwarnings("once", message=r"\[CERTUS INDEX\] .* substrate reference unavailable: .*", category=UserWarning)

    # High DPI scaling (Must be set BEFORE creating QApplication)
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON
    from certus.ui.certus_ui import init_certus_app
    init_certus_app("CERTUS-INDEX", app=app)

    # --- SPLASH SCREEN ---
    from certus.ui.certus_splash import create_splash
    splash = create_splash("Initializing Physics Engine...")


    # Wait for background JIT warmup (launched by bootstrap_app)

    logging.info("Waiting for JIT Warmup...")

    from certus.core.certus_core import wait_warmup

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
