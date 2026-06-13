# =============================================================================

# CERTUS DESIGN MODULE

# Functional area: Optical Synthesis & Optimization

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: only make small, reversible changes here until dedicated tests cover
# optimization workers, DTO/report contracts, and critical design workflows.
# Prefer extracting pure helpers before moving Qt classes or numerical kernels.
# Keep the design orchestration dense only where it is genuinely required.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-DESIGN.py - Optical Filter Design & Optimization

=========================================================

"""

from certus.core.certus_core import __version__, APP_SUITE_VERSION

import os
from pathlib import Path

import multiprocessing
import sys
import functools

from certus.core.certus_core import create_module_environment

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_DESIGN")

script_dir = env["script_dir"]

# =============================================================================

# IMPORTS SUIVANTS

# =============================================================================

import logging

import time

import traceback

import copy

from threading import Event

from typing import Any, List, Dict

import numpy as np

# pyqtgraph configured in certus_ui, imported locally for use

import pyqtgraph as pg

from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QThread,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

# Conditional SVG Import

# =============================================================================

# IMPORTS MODULAR ARCHITECTURE

# =============================================================================

# Import Modular Architecture

# --- 1. CORE (Config, Constants, Utils) ---

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CFG,
    ensure_numpy_array,
    get_complex_dtype,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)
from certus.utils.errors import safe_ui_action

from certus.workers.certus_design_worker_utils import (
    build_pglobal_optimizer,
    build_pglobal_config_from_cfg,
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_post_optim_time_budget_seconds,
    optim_prepare_stack_nk_back,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    prepare_pglobal_inputs_from_state,
    prepare_pglobal_optimizer_runtime,
    run_coord_descent_5cycles,
    run_pglobal_restart_loop,
)

# --- 4. DATA (IO, Reporting) ---

from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)

# --- 5. ERRORS (Validation, Messages) ---

# Direct import for warmup

# --- 2. PHYSICS (Models, TMM, Optimization) ---

from certus_physics import (  # Cache & Utils; Gradient Logic (Analytic); Numba Functions
    Layer,
    Material,
    ObliqueTarget,
    PGlobalConfig,
    PGlobalOptimizer,
    Target,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_gradient_contrib_analytic,
    cost_numba_fast,
    delta_e_2000,
    init_thickness,
    lab_to_rgb,
    needle_scan_cached,
    prepare_targets_vectorized,
    xyz_from_spectrum,
    xyz_to_lab,
)

from certus.utils.certus_index_utils import spectral_rmse_weights

# --- 3. UI (Theme, Widgets) ---

from certus.ui.certus_ui import (
    CertusTheme,
    CertusBaseApp,
    CertusScientificPlot,
    CertusThemeToggle,
    CertusCard,
    CertusCollapsible,
    CertusStatusPill,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    EnhancedProgressWidget,
    FlashyCard,
    WelcomeGuideWidget,
    WorkerSignals,
    certus_get_save_file_name,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    create_flashy_grid,
    create_header_logo_widget,
    create_top_actions_bar,
    get_export_config,
    init_certus_app,
    open_documentation,
    plot_widget_plot_finite,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)

# Configure GUI

# =============================================================================

# PGlobalConfig Methods (now provided by certus_physics.structures)

# =============================================================================

# Conditional Excel Import (OPENPYXL_AVAILABLE used elsewhere in module)

# =============================================================================

# LOGGING CONFIGURATION

# =============================================================================

# Logger initialized in CertusDesignApp

# This ensures consistency with other CERTUS modules

# script_dir already set by bootstrap_app()

# =============================================================================

# AUTOMATIC PRECISION ADAPTATION

# =============================================================================

# Use wrappers if single precision enabled

# Note: cost_numba_fast handles precision internally

# Wrappers enforce (d,n) consistency

from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)

calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full = calc_spectrum_full_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# =============================================================================

# DESIGN-SPECIFIC WORKERS

# =============================================================================


from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *

from certus.ui.mixins.certus_design_plot_mixin import CertusDesignUIPlotMixin
from certus.ui.certus_design_ui_layout import CertusDesignLayoutMixin
from certus.ui.certus_design_ui_state import CertusDesignStateMixin
from certus.ui.certus_design_ui_events import CertusDesignEventsMixin
from certus.ui.certus_design_ui_worker import CertusDesignWorkerMixin
from certus.ui.certus_design_ui_export import CertusDesignExportMixin
from certus.ui.certus_design_ui_optimization import CertusDesignOptimizationMixin
from certus.ui.certus_design_ui_core import CertusDesignCoreMixin


class CertusDesignApp(
    CertusDesignUIPlotMixin,
    CertusDesignLayoutMixin,
    CertusDesignStateMixin,
    CertusDesignEventsMixin,
    CertusDesignWorkerMixin,
    CertusDesignExportMixin,
    CertusDesignOptimizationMixin,
    CertusDesignCoreMixin,
    CertusBaseApp,
):
    """Main Application CERTUS-DESIGN"""

    optimization_finished_signal = pyqtSignal()

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-DESIGN"

    APP_TITLE = "Optical Filter Design & Optimization"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:
        """

        Initialize the CERTUS-DESIGN application.

        This method sets up the main application including:

        - Logger configuration and setup

        - Design-specific state initialization

        - Worker threads and state management

        - UI construction and theme application

        - JIT compilation warmup

        Args:

            self: CertusDesignApp instance

        Returns:

            None

        Notes:

            - Inherits from CertusBaseApp

            - Sets up design-specific widgets and workers

            - Initializes optimization and evaluation workers

            - Applies CERTUS theme and builds UI

            - Starts JIT warmup process

        """

        super().__init__()
        from certus.core.certus_design_orchestrator import DesignOrchestrator
        self.orchestrator = DesignOrchestrator(self)

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # DESIGN-specific state

        self.mat_widgets: dict[str, dict[str, Any]] = {}

        self.target_widgets: List = []

        self.ep_current: np.ndarray | None = None

        self.ep_back_current: np.ndarray | None = None

        self.last_result: Dict = {}

        self._best_eval_result: Dict | None = None

        self._best_eval_rmse: float = float("inf")

        self.target_scatter = None

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        self.detached_window = None

        self.eval_timer = None

        self._current_eval_generation = 0

        default_max_layers: int = int(getattr(CFG, "MAX_LAYERS", 50))
        self._original_target_count = default_max_layers

        self._target_layer_count = default_max_layers
        # Keep the configured target count until workflow logic explicitly updates it.

        self._overshoot_active = False

        self._overshoot_done = False

        # Oblique mode

        self.oblique_mode = False

        self.oblique_targets: list[ObliqueTarget] = []

        # Workers

        self.optim_worker: OptimWorker | None = None
        self.optim_thread: QThread | None = None

        self.eval_worker: EvalWorker | None = None

        self.col_worker: ColorWorker | None = None
        self.col_thread: QThread | None = None

        self.needle_worker: NeedleWorker | None = None
        self.needle_thread: QThread | None = None

        self.warmup_worker: WarmupWorker | None = None

        # Needle State

        # Keep the configured target count until workflow logic explicitly updates it.
        self._is_internal_restart = False

        self._topology_stable = True

        # Statistics (override base)

        self.stat_counters = {"EVAL": 0, "BEST": 0, "MINIMA": 0}

        self.accumulated_evals = 0

        self._warmup_done = False

        self._needle_recent_best_rmse = float("inf")

        self._needle_no_improve_rounds = 0

        # Balanced preset: favor good RMSE without excessive topology churn/time.

        self._needle_success_rel_threshold = 0.008

        self._needle_success_abs_floor = 3e-5

        self._needle_gate_no_improve_rounds = 3

        self._needle_pred_gain_rel_threshold = 0.003

        self._needle_pred_gain_abs_threshold = 2e-5

        self.pareto_history = {}  # N -> dict(rmse, mc_rmse, ep, table_state)

        # Theme Application

        CertusTheme.apply_to_app(QApplication.instance())

        # UI Construction

        self._build_ui()

        self._setup_shortcuts()

        self._load_defaults()

        # Warmup JIT (DESIGN uses its own WarmupWorker)

        self.status_label.setText("Compiling JIT kernels…")

        self.warmup_worker = WarmupWorker()

        self.warmup_worker.finished.connect(self._on_warmup_done)

        self.warmup_worker.start()

    # =========================================================================

    # UI CONSTRUCTION

    # =========================================================================

















    # =========================================================================

    # HELPERS UI

    # =========================================================================





    # =========================================================================

    # LAYER MANAGEMENT

    # =========================================================================






    def _add_back_row(self, mat: str, qwot: float) -> None:
        """Adds a row to back layer table"""

        row = self.back_table.rowCount()

        self.back_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._on_schedule_eval_signal)

        self.back_table.setCellWidget(row, 0, cb)

        sb = self._create_spin(qwot, dec=3)

        sb.valueChanged.connect(self._on_schedule_eval_signal)

        self.back_table.setCellWidget(row, 1, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.back_table.setItem(row, 2, it)









    # =========================================================================

    # TARGET MANAGEMENT

    # =========================================================================







    # =========================================================================

    # GETTERS

    # =========================================================================





    # =========================================================================

    # EVALUATION

    # =========================================================================





    # =========================================================================

    # OPTIMIZATION

    # =========================================================================

























    def _is_in_needle_cycle(self) -> bool:
        """Return True when post-optim workflow is inside Needle cycle states."""
        return hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]

















    # =====================================================================

    # PARETO DECIMATION: remove thinnest -> merge -> re-polish -> record -> loop

    # =====================================================================






















    # =========================================================================

    # HARD 5nm MINIMUM LAYER THICKNESS RULE

    # =========================================================================












    # =========================================================================

    # NEEDLE ALGORITHM

    # =========================================================================












    # =========================================================================

    # COLORIMETRY

    # =========================================================================



    # =========================================================================

    # SELF-EXPORT (Excel + HTML)

    # =========================================================================








    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # --- Lot C helpers ---













    # =========================================================================

    # UTILITAIRES

    # =========================================================================




# =============================================================================

# ENTRY POINT

# =============================================================================

