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
from PyQt6.QtCore import QPointF

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


# from certus.core.certus_design_core import *  # Unused
from certus.workers.certus_design_workers import ColorWorker, NeedleWorker, OptimWorker


from certus.ui.certus_design_ui_plot import PlotManager
from certus.ui.certus_design_ui_layout import LayoutManager
from certus.ui.certus_design_ui_state import StateManager
from certus.ui.certus_design_ui_events import EventsManager
from certus.ui.certus_design_ui_worker import WorkerManager
from certus.ui.certus_design_ui_export import ExportManager
from certus.ui.certus_design_ui_optimization import OptimizationManager
from certus.ui.certus_design_ui_core import CoreManager
from certus.ui.certus_design_ui_layout import LayoutManager


class CertusDesignApp(
    
    
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
        self.export_manager = ExportManager(self)
        self.optimization_manager = OptimizationManager(self)
        self.core_manager = CoreManager(self)
        self.worker_manager = WorkerManager(self)
        self.events_manager = EventsManager(self)
        self.state_manager = StateManager(self)
        self.plot_manager = PlotManager(self)
        self.layout_manager = LayoutManager(self)

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
        self.orchestrator._original_target_count = default_max_layers

        self.orchestrator._target_layer_count = default_max_layers
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


    @safe_ui_action
    def export_results(self) -> None:
        self.export_manager.export_results()

    @safe_ui_action
    def export_excel(self) -> None:
        self.export_manager.export_excel()

    # WorkerManager Proxies
    def run_eval(self) -> None:
        self.worker_manager.run_eval()

    def _on_eval_finished(self, data: dict, generation_id: int | None = None) -> None:
        self.worker_manager._on_eval_finished(data, generation_id)

    def run_optim(self, mode: str, keep_history: bool = False, **kwargs) -> None:
        self.worker_manager.run_optim(mode, keep_history, **kwargs)

    def run_colorimetry(self) -> None:
        self.worker_manager.run_colorimetry()

    def stop_optim(self) -> None:
        self.worker_manager.stop_optim()

    # EventsManager Proxies
    def add_target(self) -> None:
        self.events_manager.add_target()

    def del_target(self) -> None:
        self.events_manager.del_target()

    def add_back_layer(self) -> None:
        self.events_manager.add_back_layer()

    def del_back_layer(self) -> None:
        self.events_manager.del_back_layer()

    def remove_thinnest(self) -> None:
        self.events_manager.remove_thinnest()

    def open_help(self) -> None:
        self.events_manager.open_help()

    def closeEvent(self, event) -> None:
        self.events_manager.closeEvent(event)
        super().closeEvent(event)

    def _on_qwot_changed_connection(self, spinbox) -> None:
        self.events_manager._on_qwot_changed_connection(spinbox)

    def _on_layer_added(self) -> None:
        self.events_manager._on_layer_added()

    def _on_layer_deleted(self) -> None:
        self.events_manager._on_layer_deleted()

    def _paste_from_excel(self) -> None:
        self.events_manager._paste_from_excel()

    def _setup_shortcuts(self) -> None:
        self.events_manager._setup_shortcuts()

    def _on_tikhonravov_points_changed(self, *args) -> None:
        self.events_manager._on_tikhonravov_points_changed(*args)

    def _on_schedule_eval_signal(self, *args) -> None:
        self.events_manager._on_schedule_eval_signal(*args)

    def _toggle_back_stack(self, state: int) -> None:
        self.events_manager._toggle_back_stack(state)



    # PlotManager Proxies
    def init_plot_elements(self) -> None:
        self.plot_manager.init_plot_elements()

    def update_plot(self, R: np.ndarray, R_back: np.ndarray | None = None) -> None:
        self.plot_manager.update_plot(R, R_back)

    def _update_pareto_plot(self) -> None:
        self.plot_manager._update_pareto_plot()

    def update_target_scatter(self) -> None:
        self.plot_manager.update_target_scatter()

    def _update_scatter(self, plot_item, x_data, y_data, w_data, is_active, brush_active, brush_inactive, is_oblique=False):
        return self.plot_manager._update_scatter(plot_item, x_data, y_data, w_data, is_active, brush_active, brush_inactive, is_oblique)

    def update_envelope_plot(self, env_top: np.ndarray, env_bot: np.ndarray) -> None:
        self.plot_manager.update_envelope_plot(env_top, env_bot)

    def toggle_oblique_targets_display(self, show: bool) -> None:
        self.plot_manager.toggle_oblique_targets_display(show)

    def _update_target_oblique_lines(self) -> None:
        self.plot_manager._update_target_oblique_lines()

    def reset_target_scatter(self) -> None:
        self.plot_manager.reset_target_scatter()

    def draw_crosshair(self, p: QPointF, plot_item: pg.PlotItem, v_line: pg.InfiniteLine, h_line: pg.InfiniteLine, label: pg.TextItem, label_format: str) -> None:
        self.plot_manager.draw_crosshair(p, plot_item, v_line, h_line, label, label_format)

    def update_color_display(self, L: float, a: float, b: float) -> None:
        self.plot_manager.update_color_display(L, a, b)

    def _on_update_spectrum_y_scale_signal(self, *args) -> None:
        self.plot_manager._on_update_spectrum_y_scale_signal(*args)

    def _show_pareto_window(self) -> None:
        self.plot_manager._show_pareto_window()

    def _load_pareto_design(self, row: int, col: int) -> None:
        self.plot_manager._load_pareto_design(row, col)

    def _show_pareto_context_menu(self, pos) -> None:
        self.plot_manager._show_pareto_context_menu(pos)

    def _clear_pareto(self) -> None:
        self.plot_manager._clear_pareto()

    def _export_pareto_report(self) -> None:
        self.plot_manager._export_pareto_report()

    def _refresh_pareto_table(self) -> None:
        self.plot_manager._refresh_pareto_table()

    def _start_smart_pareto_decimation(self) -> None:
        """Smart Pareto Decimation: start from best solution and iteratively remove thinnest layers."""
        N_start = self.front_table.rowCount()
        if N_start <= 4 or self.ep_current is None:
            self.log("Smart Pareto Decimation: skip (too few layers or no design)", "INFO")
            if getattr(self, "_is_busy", False):
                self._set_busy(False)
            return

        N_min_target = max(4, int(N_start / 2))
        self._initialize_smart_decimation_session(N_start, N_min_target)
        self.log(
            f"🎯 Smart Pareto Decimation: {N_start} -> {N_min_target} layers"
            f" | RMSE ref={self._smart_deci_origin_rmse:.6f}",
            "INFO",
        )

        self._set_busy(True)
        self._smart_decimation_step = 0
        self.orchestrator.schedule_smart_decimation_remove_and_optimize()

    def _on_intermediate_spectrum(self, data: dict) -> None:
        self.plot_manager._on_intermediate_spectrum(data)

    def _update_pareto_record(self, current_ep=None, current_rmse=None) -> None:
        self.plot_manager._update_pareto_record(current_ep, current_rmse)

    def _plot_profile(self, ep: np.ndarray, stack: list, ep_back: np.ndarray, stack_back: list) -> None:
        self.plot_manager._plot_profile(ep, stack, ep_back, stack_back)

    def _plot_nk(self) -> None:
        self.plot_manager._plot_nk()

    # StateManager Proxies
    def _load_defaults(self) -> None:
        self.state_manager._load_defaults()

    def _pre_save_smart_cleanup(self) -> None:
        self.state_manager._pre_save_smart_cleanup()

    def _post_save_config(self, filename: str) -> None:
        self.state_manager._post_save_config(filename)

    def _collect_config(self) -> dict:
        return self.state_manager._collect_config()

    def _apply_config(self, c: dict) -> None:
        self.state_manager._apply_config(c)

    def _apply_optimization_config(self, opt: dict) -> None:
        self.state_manager._apply_optimization_config(opt)

    def _apply_material_config(self, materials: dict) -> None:
        self.state_manager._apply_material_config(materials)

    def _apply_target_config(self, targets: list[dict], oblique_mode: bool) -> None:
        self.state_manager._apply_target_config(targets, oblique_mode)

    def _apply_stack_rows(self, rows: list[dict], *, back: bool) -> None:
        self.state_manager._apply_stack_rows(rows, back=back)

    def _post_load_config(self, filename: str, config: dict) -> None:
        self.state_manager._post_load_config(filename, config)

    def reset_to_defaults(self):
        return self.state_manager.reset_to_defaults()

    # LayoutManager Proxies
    def _build_left_panel(self):
        return self.layout_manager._build_left_panel()

    def _build_right_panel(self):
        return self.layout_manager._build_right_panel()

    def _build_status_bar(self) -> None:
        self.layout_manager._build_status_bar()

    def _apply_theme(self) -> None:
        self.layout_manager._apply_theme()

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


    # --- OptimizationManager Proxies ---
    def _handle_stopped_workflow_result(self, *args, **kwargs):
        return self.optimization_manager._handle_stopped_workflow_result(*args, **kwargs)

    def _finalize_if_post_optim_budget_exceeded(self, *args, **kwargs):
        return self.optimization_manager._finalize_if_post_optim_budget_exceeded(*args, **kwargs)

    def _track_and_apply_post_optim_result(self, *args, **kwargs):
        return self.optimization_manager._track_and_apply_post_optim_result(*args, **kwargs)

    def _run_post_optim_cleanup(self, *args, **kwargs):
        return self.optimization_manager._run_post_optim_cleanup(*args, **kwargs)

    def _finalize_completed_optimization_workflow(self, *args, **kwargs):
        return self.optimization_manager._finalize_completed_optimization_workflow(*args, **kwargs)

    def _initialize_smart_decimation_session(self, *args, **kwargs):
        return self.optimization_manager._initialize_smart_decimation_session(*args, **kwargs)

    def _smart_decimation_remove_and_optimize(self, *args, **kwargs):
        return self.optimization_manager._smart_decimation_remove_and_optimize(*args, **kwargs)

    def _apply_smart_decimation_post_removal_state(self, *args, **kwargs):
        return self.optimization_manager._apply_smart_decimation_post_removal_state(*args, **kwargs)

    def _should_stop_smart_decimation_step(self, *args, **kwargs):
        return self.optimization_manager._should_stop_smart_decimation_step(*args, **kwargs)

    def _select_smart_decimation_remove_index(self, *args, **kwargs):
        return self.optimization_manager._select_smart_decimation_remove_index(*args, **kwargs)

    def _on_smart_decimation_optim_done(self, *args, **kwargs):
        return self.optimization_manager._on_smart_decimation_optim_done(*args, **kwargs)

    def _apply_smart_decimation_optim_result(self, *args, **kwargs):
        return self.optimization_manager._apply_smart_decimation_optim_result(*args, **kwargs)

    def _record_smart_decimation_candidate(self, *args, **kwargs):
        return self.optimization_manager._record_smart_decimation_candidate(*args, **kwargs)

    def _abort_on_smart_decimation_degradation(self, *args, **kwargs):
        return self.optimization_manager._abort_on_smart_decimation_degradation(*args, **kwargs)

    def _log_smart_decimation_step_result(self, *args, **kwargs):
        return self.optimization_manager._log_smart_decimation_step_result(*args, **kwargs)

    def _restore_smart_decimation_origin(self, *args, **kwargs):
        return self.optimization_manager._restore_smart_decimation_origin(*args, **kwargs)

    def _clear_smart_decimation_state(self, *args, **kwargs):
        return self.optimization_manager._clear_smart_decimation_state(*args, **kwargs)

    def _log_smart_decimation_completion(self, *args, **kwargs):
        return self.optimization_manager._log_smart_decimation_completion(*args, **kwargs)

    def _finish_smart_decimation(self, *args, **kwargs):
        return self.optimization_manager._finish_smart_decimation(*args, **kwargs)

    def _finalize_smart_decimation_post_actions(self, *args, **kwargs):
        return self.optimization_manager._finalize_smart_decimation_post_actions(*args, **kwargs)

    def _decimation_remove_and_polish(self, *args, **kwargs):
        return self.optimization_manager._decimation_remove_and_polish(*args, **kwargs)

    def _on_decimation_polish_done(self, *args, **kwargs):
        return self.optimization_manager._on_decimation_polish_done(*args, **kwargs)

    def _drop_thinnest_and_polish(self, *args, **kwargs):
        return self.optimization_manager._drop_thinnest_and_polish(*args, **kwargs)

    def _apply_5nm_minimum(self, *args, **kwargs):
        return self.optimization_manager._apply_5nm_minimum(*args, **kwargs)

    def _save_table_state(self, *args, **kwargs):
        return self.optimization_manager._save_table_state(*args, **kwargs)

    def _restore_table_state(self, *args, **kwargs):
        return self.optimization_manager._restore_table_state(*args, **kwargs)

    def _revert_to_checkpoint(self, *args, **kwargs):
        return self.optimization_manager._revert_to_checkpoint(*args, **kwargs)

    def smart_cleanup(self, *args, **kwargs):
        return self.optimization_manager.smart_cleanup(*args, **kwargs)

    def _prune_to_target(self, *args, **kwargs):
        return self.optimization_manager._prune_to_target(*args, **kwargs)

    def _needle_thresholds(self, *args, **kwargs):
        return self.optimization_manager._needle_thresholds(*args, **kwargs)

    def _needle_gain_is_significant(self, *args, **kwargs):
        return self.optimization_manager._needle_gain_is_significant(*args, **kwargs)

    def _start_needle_process(self, *args, **kwargs):
        return self.optimization_manager._start_needle_process(*args, **kwargs)

    def _on_needle_found(self, *args, **kwargs):
        return self.optimization_manager._on_needle_found(*args, **kwargs)

    def _handle_needle_no_candidate(self, *args, **kwargs):
        return self.optimization_manager._handle_needle_no_candidate(*args, **kwargs)

    def _handle_needle_no_candidate_below_target(self, *args, **kwargs):
        return self.optimization_manager._handle_needle_no_candidate_below_target(*args, **kwargs)

    def _abort_needle_after_failed_retries(self, *args, **kwargs):
        return self.optimization_manager._abort_needle_after_failed_retries(*args, **kwargs)

    def _maybe_prune_needle_overshoot(self, *args, **kwargs):
        return self.optimization_manager._maybe_prune_needle_overshoot(*args, **kwargs)

    def _apply_needle_split_insertion(self, *args, **kwargs):
        return self.optimization_manager._apply_needle_split_insertion(*args, **kwargs)

    def _insert_needle_split_row(self, *args, **kwargs):
        return self.optimization_manager._insert_needle_split_row(*args, **kwargs)

    def _insert_right_split_row(self, *args, **kwargs):
        return self.optimization_manager._insert_right_split_row(*args, **kwargs)

    def _clear_needle_cycle_state(self, *args, **kwargs):
        return self.optimization_manager._clear_needle_cycle_state(*args, **kwargs)

    def _clear_needle_search_state(self, *args, **kwargs):
        return self.optimization_manager._clear_needle_search_state(*args, **kwargs)


    # --- CoreManager Proxies ---
    def _get_default_splitter_sizes(self, *args, **kwargs):
        return self.core_manager._get_default_splitter_sizes(*args, **kwargs)

    def _get_substrate_info_display(self, *args, **kwargs):
        return self.core_manager._get_substrate_info_display(*args, **kwargs)

    def _show_substrate_info_window(self, *args, **kwargs):
        return self.core_manager._show_substrate_info_window(*args, **kwargs)

    def _toggle_oblique_mode(self, *args, **kwargs):
        return self.core_manager._toggle_oblique_mode(*args, **kwargs)

    def copy_logs_to_clipboard(self, *args, **kwargs):
        return self.core_manager.copy_logs_to_clipboard(*args, **kwargs)

    def _apply_preset(self, *args, **kwargs):
        return self.core_manager._apply_preset(*args, **kwargs)

    def _on_schedule_eval_signal(self, *args, **kwargs):
        return self.core_manager._on_schedule_eval_signal(*args, **kwargs)

    def _on_schedule_eval_instant_signal(self, *args, **kwargs):
        return self.core_manager._on_schedule_eval_instant_signal(*args, **kwargs)

    def _trigger_post_undo_action(self, *args, **kwargs):
        return self.core_manager._trigger_post_undo_action(*args, **kwargs)

    def _get_optim_wls(self, *args, **kwargs):
        return self.core_manager._get_optim_wls(*args, **kwargs)

    def _update_optim_point_count(self, *args, **kwargs):
        return self.core_manager._update_optim_point_count(*args, **kwargs)

    def _calculate_tikhonravov_points(self, *args, **kwargs):
        return self.core_manager._calculate_tikhonravov_points(*args, **kwargs)

    def _update_tikhonravov_points(self, *args, **kwargs):
        return self.core_manager._update_tikhonravov_points(*args, **kwargs)

    def _get_materials(self, *args, **kwargs):
        return self.core_manager._get_materials(*args, **kwargs)

    def _get_oblique_tgts(self, *args, **kwargs):
        return self.core_manager._get_oblique_tgts(*args, **kwargs)

    def _load_targets_to_table(self, *args, **kwargs):
        return self.core_manager._load_targets_to_table(*args, **kwargs)

    def _on_front_thickness_updated(self, *args, **kwargs):
        return self.core_manager._on_front_thickness_updated(*args, **kwargs)

    def _reset_run_optim_workflow_state(self, *args, **kwargs):
        return self.core_manager._reset_run_optim_workflow_state(*args, **kwargs)

    def _shutdown_previous_optim_worker(self, *args, **kwargs):
        return self.core_manager._shutdown_previous_optim_worker(*args, **kwargs)

    def _collect_run_optim_inputs(self, *args, **kwargs):
        return self.core_manager._collect_run_optim_inputs(*args, **kwargs)

    def _initialize_run_optim_progress_state(self, *args, **kwargs):
        return self.core_manager._initialize_run_optim_progress_state(*args, **kwargs)

    def _refresh_optim_target_scatter_foreground(self, *args, **kwargs):
        return self.core_manager._refresh_optim_target_scatter_foreground(*args, **kwargs)

    def _apply_qw_values_to_front_table(self, *args, **kwargs):
        return self.core_manager._apply_qw_values_to_front_table(*args, **kwargs)

    def on_stats_update(self, *args, **kwargs):
        return self.core_manager.on_stats_update(*args, **kwargs)

    def update_stats_display(self, *args, **kwargs):
        return self.core_manager.update_stats_display(*args, **kwargs)

    def _update_busy_ui(self, *args, **kwargs):
        return self.core_manager._update_busy_ui(*args, **kwargs)

