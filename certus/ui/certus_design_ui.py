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
    CAUCHY_PRESETS,
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

class CertusDesignApp(CertusBaseApp, CertusDesignUIPlotMixin):
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

    def _get_default_splitter_sizes(self) -> list[int]:
        """DESIGN specific splitter sizes."""

        return [450, 1150]

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for DESIGN."""

        substrate_type = "Custom"

        substrate_index = "N/A"

        if hasattr(self, "mat_widgets") and "Substrate" in self.mat_widgets:
            w = self.mat_widgets["Substrate"]

            substrate_type = w["preset"].currentText()

            n4 = w["n4"].value()

            n7 = w["n7"].value()

            substrate_index = f"n@400={n4:.3f}, n@700={n7:.3f}"

        return substrate_type, substrate_index

    def _build_left_panel(self) -> QWidget:
        """Constructs left control panel"""

        left_panel = QWidget()

        left_panel.setMinimumWidth(280)

        # Removed setFixedWidth to allow resizing via splitter

        left_panel.setObjectName("LeftPanel")

        left_layout = QVBoxLayout(left_panel)

        left_layout.setSpacing(0)

        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Standard Header

        header_widget = create_header_logo_widget(
            "DESIGN",
            self.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_DESIGN",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_layout.addWidget(header_widget)

        # 2. Action Bar (Shared)

        action_bar = create_top_actions_bar(self, self.save_config, self.load_config, self.export_excel, self.open_help)

        left_layout.addWidget(action_bar)

        # Scrollable area

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()

        scroll_layout = QVBoxLayout(scroll_content)

        scroll_layout.setContentsMargins(0, 0, 4, 0)

        scroll_layout.setSpacing(8)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Configure materials  2 Define stack  3 Set optimizer  4 Evaluate / Run")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        workflow_card.body.addWidget(workflow_hint)

        scroll_layout.addWidget(workflow_card)

        self.back_group = self._build_back_group()

        materials_widget = self._build_materials_group()

        params_widget = self._build_params_group()

        optim_widget = self._build_optim_group()

        scroll_layout.addWidget(CertusCollapsible("1  Materials", materials_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("2  Back-side structure", self.back_group, expanded=False))

        scroll_layout.addWidget(CertusCollapsible("3  Parameters", params_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("4  Optimization", optim_widget, expanded=True))

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        left_layout.addWidget(scroll)

        # Action buttons

        action_layout = self._build_action_buttons()

        # Add layout to a container first to apply margins if needed,

        # but action_buttons typically has its own margins.

        # Check action_buttons implementation if it returns a Layout or Widget.

        # It returns a layout. We need to wrap it in a widget or add layout.

        # In QLayout.addLayout, it adds to the layout.

        # Wrapper for bottom actions to add padding

        bottom_actions_widget = CertusCard("Actions")

        bottom_actions_widget.body.setContentsMargins(10, 8, 10, 10)

        bottom_actions_widget.body.addLayout(action_layout)

        left_layout.addWidget(bottom_actions_widget)

        self.back_group.setVisible(self.back_coat_check.isChecked())

        return left_panel

    def _apply_theme(self) -> None:
        """Apply Certus theme dynamically"""

        self._apply_certus_compact_theme(
            plots=[
                getattr(self, "spectrum_plot", None),
                getattr(self, "profile_plot", None),
                getattr(self, "nk_plot", None),
                getattr(self, "color_plot", None),
                getattr(self, "plot_convergence", None),
            ]
        )

    def _build_materials_group(self) -> CertusCard:
        """Constructs materials group"""

        mat_group = CertusCard("Materials")

        mat_grid = QGridLayout()

        mat_group.body.addLayout(mat_grid)

        headers = ["Material", "Preset", "n@400", "n@700"]

        for col, header in enumerate(headers):
            mat_grid.addWidget(QLabel(f"<b>{header}</b>"), 0, col)

        materials = list(CFG.MATERIALS)

        for i, mat_name in enumerate(materials):
            row = i + 1

            mat_grid.addWidget(QLabel(f"<b>{mat_name}</b>"), row, 0)

            combo = QComboBox()

            combo.setToolTip("Select the material preset or 'Custom'.")

            combo.addItems(CAUCHY_PRESETS.keys())

            combo.setCurrentText("Custom")

            n4_spin = self._create_spin(1.5, dec=3)

            n7_spin = self._create_spin(1.5, dec=3)

            for spin in [n4_spin, n7_spin]:
                spin.setRange(1.0, 4.0)

                spin.valueChanged.connect(self._on_schedule_eval_signal)

                spin.valueChanged.connect(self._on_tikhonravov_points_changed)

            combo.currentTextChanged.connect(lambda t, s4=n4_spin, s7=n7_spin: self._apply_preset(t, s4, s7))

            mat_grid.addWidget(combo, row, 1)

            mat_grid.addWidget(n4_spin, row, 2)

            mat_grid.addWidget(n7_spin, row, 3)

            self.mat_widgets[mat_name] = {"preset": combo, "n4": n4_spin, "n7": n7_spin}

            # Initialize spinbox states based on default preset

            self._apply_preset(combo.currentText(), n4_spin, n7_spin)

        return mat_group

    def _build_params_group(self) -> CertusCard:
        """Constructs parameters group"""

        param_group = CertusCard("Parameters")

        param_layout = param_group.body

        # Reference Lambda

        l0_lay = QHBoxLayout()

        self.l0_spin = QDoubleSpinBox()

        self.l0_spin.setRange(200, 20000)

        self.l0_spin.setValue(CFG.DEFAULT_L0)

        self.l0_spin.setDecimals(1)

        self.l0_spin.setSuffix(" nm")

        self.l0_spin.valueChanged.connect(self._on_schedule_eval_signal)

        self.l0_spin.valueChanged.connect(self._on_tikhonravov_points_changed)

        self.l0_spin.setToolTip("Reference wavelength lambda₀ (nm) for converting QWOT to physical thickness.")

        l0_lay.addWidget(QLabel("lambda₀ ref.:"))

        l0_lay.addWidget(self.l0_spin)

        param_layout.addLayout(l0_lay)

        # Backside options

        self.back_check = QCheckBox("substrate back face (Fresnel)")

        self.back_check.setToolTip("Include reflection from the untreated back face of the substrate.")

        self.back_check.stateChanged.connect(self._on_schedule_eval_instant_signal)

        param_layout.addWidget(self.back_check)

        self.back_coat_check = QCheckBox("Back-side stack")

        self.back_coat_check.setToolTip(
            "Show the back-side layer editor and include those layers in the calculation when checked."
        )

        self.back_coat_check.stateChanged.connect(self._toggle_back_stack)

        param_layout.addWidget(self.back_coat_check)

        # Oblique Mode

        self.oblique_check = QCheckBox("Oblique incidence mode")

        self.oblique_check.setToolTip("R/T targets with angle and s / p / average polarization per row.")

        self.oblique_check.stateChanged.connect(self._toggle_oblique_mode)

        param_layout.addWidget(self.oblique_check)

        # Auto Y Scale or Fixed (0-1)

        self.auto_scale_y_check = QCheckBox("Auto Y scale")

        self.auto_scale_y_check.setChecked(True)

        self.auto_scale_y_check.setToolTip("Fit the Y axis to the spectrum data on display.")

        self.auto_scale_y_check.stateChanged.connect(self._on_update_spectrum_y_scale_signal)

        param_layout.addWidget(self.auto_scale_y_check)

        # Deep Needle / Layer Growth

        self.allow_growth_check = QCheckBox("Topology growth (deep Needle)")

        self.allow_growth_check.setChecked(True)

        self.allow_growth_check.setToolTip("Allow thin-layer insertion during optimization (Needle mode).")

        param_layout.addWidget(self.allow_growth_check)

        # Pre-Polish

        self.pre_polish_check = QCheckBox("Local polish before PGLOBAL")

        self.pre_polish_check.setChecked(False)

        self.pre_polish_check.setToolTip("Run a local gradient polish before the multi-minima global phase.")

        param_layout.addWidget(self.pre_polish_check)

        return param_group

    def _build_back_group(self) -> CertusCard:
        """Constructs backside group"""

        back_group = CertusCard("Back-side structure")

        back_layout = back_group.body

        self.back_table = QTableWidget(0, 3)

        self.back_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)"])

        self.back_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.back_table.setAlternatingRowColors(True)

        self.back_table.setMaximumHeight(150)

        back_layout.addWidget(self.back_table)

        back_btns = QHBoxLayout()

        b_add = QPushButton("Add")

        b_add.setToolTip("Add a layer to the back-side stack.")

        b_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        b_add.clicked.connect(self.add_back_layer)

        b_del = QPushButton("Remove")

        b_del.setToolTip("Remove a layer from the back-side stack.")

        b_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        b_del.clicked.connect(self.del_back_layer)

        back_btns.addWidget(b_add)

        back_btns.addWidget(b_del)

        back_btns.addStretch()

        back_layout.addLayout(back_btns)

        return back_group

    def _build_optim_group(self) -> CertusCard:
        """Constructs optimization group"""

        opt_group = CertusCard("Optimization (PGLOBAL)")

        opt_grid = QGridLayout()

        opt_group.body.addLayout(opt_grid)

        opt_grid.setSpacing(8)

        row = 0

        # Samples per iteration

        self.n100_spin = QSpinBox()

        self.n100_spin.setRange(50, 500000)

        self.n100_spin.setValue(6000)

        self.n100_spin.setSingleStep(50)

        self.n100_spin.setToolTip(
            "Number of random starting points evaluated per global iteration.\n"
            "Higher values improve exploration but increase computation time."
        )

        opt_grid.addWidget(QLabel("Samples / Iter:"), row, 0)

        opt_grid.addWidget(self.n100_spin, row, 1)

        row += 1

        # Max clusters

        self.max_clusters_spin = QSpinBox()

        self.max_clusters_spin.setRange(5, 2500)

        self.max_clusters_spin.setValue(40)

        self.max_clusters_spin.setToolTip(
            "Maximum number of local minima (clusters) tracked simultaneously.\n"
            "Limits memory usage and ensures the best basins are retained."
        )

        opt_grid.addWidget(QLabel("Max Clusters:"), row, 0)

        opt_grid.addWidget(self.max_clusters_spin, row, 1)

        row += 1

        # Max iterations

        self.global_cycles_spin = QSpinBox()

        self.global_cycles_spin.setRange(1, 2500)

        self.global_cycles_spin.setValue(50)

        self.global_cycles_spin.setToolTip("Maximum number of global optimization cycles before auto-stopping.")

        opt_grid.addWidget(QLabel("Max Iterations:"), row, 0)

        opt_grid.addWidget(self.global_cycles_spin, row, 1)

        row += 1

        # Points per target

        self.points_per_target_spin = QSpinBox()

        self.points_per_target_spin.setRange(1, 5000)

        self.points_per_target_spin.setValue(50)

        self.points_per_target_spin.setToolTip(
            "Number of spectral evaluation points per target region.\n"
            "Higher values increase spectral accuracy but slow down evaluation."
        )

        self.points_per_target_spin.valueChanged.connect(self._update_optim_point_count)

        opt_grid.addWidget(QLabel("Points / Target:"), row, 0)

        opt_grid.addWidget(self.points_per_target_spin, row, 1)

        row += 1

        # Spectrum points (readonly)

        self.npts_spin = QSpinBox()

        self.npts_spin.setToolTip("Total number of spectrum points evaluated (read-only).")

        self.npts_spin.setRange(0, 50000)

        self.npts_spin.setReadOnly(True)

        self.npts_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        opt_grid.addWidget(QLabel("Spectrum Points:"), row, 0)

        opt_grid.addWidget(self.npts_spin, row, 1)

        row += 1

        # Monte Carlo section

        opt_grid.addWidget(QLabel("<b>MC ANALYSIS: </b>"), row, 0, 1, 2)

        row += 1

        self.mc_n_spin = QSpinBox()

        self.mc_n_spin.setToolTip("Number of Monte Carlo samples.")

        self.mc_n_spin.setRange(10, 5000)

        self.mc_n_spin.setValue(200)

        opt_grid.addWidget(QLabel("Samples:"), row, 0)

        opt_grid.addWidget(self.mc_n_spin, row, 1)

        row += 1

        self.mc_sigma_spin = QDoubleSpinBox()

        self.mc_sigma_spin.setRange(0.1, 20)

        self.mc_sigma_spin.setValue(2.0)

        self.mc_sigma_spin.setToolTip(
            "Standard deviation of the Gaussian thickness perturbation for Monte Carlo\n"
            "sensitivity analysis (nm). Simulates manufacturing thickness errors."
        )

        opt_grid.addWidget(QLabel("Sigma (nm):"), row, 0)

        opt_grid.addWidget(self.mc_sigma_spin, row, 1)

        return opt_group

    def _build_action_buttons(self) -> QVBoxLayout:
        """Constructs action buttons"""

        action_layout = QVBoxLayout()

        logger = getattr(self, "logger", None)
        if logger:
            logger.info("DESIGN UI: building action buttons | has_functools=%s", bool(getattr(functools, "partial", None)))

        # Evaluate

        primary_obj = "CertusPrimaryBtn"

        self.eval_btn = QPushButton("Evaluate (Ctrl+E)")

        self.eval_btn.setObjectName(primary_obj)

        self.eval_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.eval_btn.setToolTip("Compute the spectrum for the current stack (instant).")

        self.eval_btn.clicked.connect(functools.partial(self._schedule_eval, True))
        if logger:
            logger.info("DESIGN UI: connected eval button -> _schedule_eval(True)")

        action_layout.addWidget(self.eval_btn)

        # Local/Global optimization

        h_act = QHBoxLayout()

        self.local_btn = QPushButton("Polish local (+/-2 nm)")

        self.local_btn.setObjectName(primary_obj)

        self.local_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.local_btn.setToolTip(
            "Run a local gradient polish (L-BFGS) on the current design.\n"
            "Perturbs each layer by +/-2 nm and refines thickness values."
        )

        self.local_btn.clicked.connect(functools.partial(self.run_optim, "local"))

        self.global_btn = QPushButton("PGLOBAL (global)")

        self.global_btn.setObjectName(primary_obj)

        self.global_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))

        self.global_btn.setToolTip(
            "Run the full global PGLOBAL optimization:\n"
            "multi-start random sampling, single-linkage clustering, and local polish."
        )

        self.global_btn.clicked.connect(functools.partial(self.run_optim, "global"))

        h_act.addWidget(self.local_btn)

        h_act.addWidget(self.global_btn)

        action_layout.addLayout(h_act)

        # Remove thinnest layer + merge adjacents + local polish

        self.drop_thin_btn = QPushButton("▼ Drop thinnest layer")

        self.drop_thin_btn.setObjectName(primary_obj)

        self.drop_thin_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))

        self.drop_thin_btn.setToolTip(
            "Removes the thinnest layer, merges adjacent layers (except 1 and N), "
            "and runs a local polish to optimize the resulting design."
        )

        self.drop_thin_btn.clicked.connect(self._drop_thinnest_and_polish)

        action_layout.addWidget(self.drop_thin_btn)

        # Stop

        self.stop_btn = QPushButton("Stop")

        self.stop_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))

        self.stop_btn.setToolTip("Stop the running optimization and keep the best design found so far.")

        self.stop_btn.setStyleSheet(CertusTheme.get_danger_button_stylesheet())

        self.stop_btn.clicked.connect(self.stop_optim)

        self.stop_btn.setEnabled(False)

        action_layout.addWidget(self.stop_btn)

        # Colorimetry

        self.color_btn = QPushButton("Colorimetric analysis")

        self.color_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.color_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_CommandLink))

        self.color_btn.setToolTip(
            "Run a Monte Carlo colorimetric analysis on the current design.\n"
            "Shows CIE Lab a*b* distribution and DeltaE stability."
        )

        self.color_btn.clicked.connect(self.run_colorimetry)

        action_layout.addWidget(self.color_btn)

        # Stack Info Button

        self.substrate_info_btn = QPushButton("🔬 Stack info")

        self.substrate_info_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.substrate_info_btn.setToolTip(
            "substrate summary and stack structure in QWOT (best design if optimization is running)."
        )

        self.substrate_info_btn.clicked.connect(self._show_substrate_info_window)

        action_layout.addWidget(self.substrate_info_btn)

        # Update stack info when optimization completes

        self.optimization_finished_signal.connect(self._update_substrate_info)

        # Clear / Reset (use app's full reset: tables, state, plots, then _load_defaults)

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self, use_app_reset=True)

        action_layout.addWidget(self.clear_btn)

        return action_layout

    def _show_substrate_info_window(self) -> None:
        """Display stack information in a separate window"""

        if getattr(self, "substrate_info_window", None) and self.substrate_info_window.isVisible():
            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        if getattr(self, "substrate_info_window", None) and not self.substrate_info_window.isVisible():
            self.substrate_info_window.show()

            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        self.substrate_info_window = QDialog(self)

        self.substrate_info_window.setWindowTitle("🔬 Stack information")

        self.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.substrate_type_label = QLabel("N/A")

        self.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.substrate_type_label, 0, 1)

        info_layout.addWidget(self.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Structure (QWOT)")

        structure_layout = structure_card.body

        self.structure_text = QTextEdit()

        self.structure_text.setReadOnly(True)

        self.structure_text.setMaximumHeight(200)

        structure_layout.addWidget(self.structure_text)

        layout.addWidget(structure_card)

        btn_layout = QHBoxLayout()

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(self.substrate_info_window.close)

        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.substrate_info_window.setLayout(layout)

        self.substrate_info_window.show()

        self.substrate_info_window.raise_()

        self.substrate_info_window.activateWindow()

        self._update_substrate_info()

    def _build_right_panel(self) -> Any:
        """Constructs right panel with visualization and tables"""

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)

        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Visualization Area

        self.viz_stack = QStackedWidget()

        self.viz_stack.addWidget(WelcomeGuideWidget("CERTUS-DESIGN"))

        viz_container = QWidget()

        v_lay = QVBoxLayout(viz_container)

        self.plot_tabs = QTabWidget()

        # Y Label dynamically updated

        self.spectrum_plot = CertusScientificPlot(self, "Spectrum", "Transmission", "lambda (nm)")

        # Init X scale (def: 380-780nm)

        self.spectrum_plot.setXRange(200, 3000, 0)

        self.spectrum_plot.setYRange(0.0, 1.0, 0)

        self.profile_plot = CertusScientificPlot(self, "Refractive Index Profile", "n", "z (nm)")

        self.nk_plot = CertusScientificPlot(self, "Dispersion n(lambda)", "n", "lambda (nm)")

        self.color_plot = CertusScientificPlot(self, "CIE a*b* Diagram", "b*", "a*")

        # Buttons to detach plots

        plot_header = QWidget()

        plot_header.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(6, 2, 6, 2)

        detach_btn = QPushButton("🔗 Detach plot")

        detach_btn.setToolTip("Open the current plot tab in a separate window.")

        detach_btn.clicked.connect(self.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_header_layout.addStretch()

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.plot_tabs)

        self.plot_tabs.addTab(self.spectrum_plot, "Spectrum (T)")

        self.plot_tabs.addTab(self.profile_plot, "Profile")

        self.plot_tabs.addTab(self.nk_plot, "n(lambda)")

        self.plot_tabs.addTab(self.color_plot, "Color")

        # Convergence plot (like INDEX/METAL)

        self.plot_convergence = CertusScientificPlot(self, "Optimization Convergence", "RMSE", "Iteration")

        self.plot_convergence.showGrid(x=True, y=True)

        self.plot_convergence.setLogMode(y=True)

        self.convergence_curve = self.plot_convergence.plot([], [], pen=pg.mkPen(CertusTheme.ERROR, width=2))

        self.plot_tabs.addTab(self.plot_convergence, "Convergence")

        # Why CERTUS? tab (matching INDEX/METAL style)

        c1 = FlashyCard(
            "Global Optimization PGLOBAL",
            "Multi-start + real-time callback\nKeeps the best RMSE over the entire workflow",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Solution Topology",
            "Single-linkage clustering of minima\nAvoids missing design valleys",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Automatic Needle + Healing",
            "Variational layer insertion\nLocal refinement to converge cleanly",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Optical Performance + Color",
            "Spectrum, n(lambda) profile, CIE Lab\nDeltaE tracking for visual stability",
            icon="🔮",
        )

        self.perf_tab = create_flashy_grid([c1, c2, c3, c4])

        self.plot_tabs.addTab(self.perf_tab, "Why CERTUS?")

        v_lay.addWidget(plot_container)

        self.viz_stack.addWidget(viz_container)

        right_splitter.addWidget(self.viz_stack)

        # Table Area

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        bottom_splitter.addWidget(self._build_front_table_widget())

        bottom_splitter.addWidget(self._build_target_table_widget())

        right_splitter.addWidget(bottom_splitter)

        right_splitter.setSizes([600, 300])

        right_layout.addWidget(right_splitter)

        # Log Container

        self.log_container = self._build_log_container()

        self.log_container.setVisible(False)  # Start hidden

        right_layout.addWidget(self.log_container)

        return right_panel

    def _build_front_table_widget(self) -> QWidget:
        """Constructs front layer table widget (Now a TabWidget with Pareto History)"""

        self.front_tabs = QTabWidget()

        self.front_tabs.setMaximumWidth(460)

        # Tab 1: Front Structure

        self.front_container = QWidget()

        f_lay = QVBoxLayout(self.front_container)

        f_head = QHBoxLayout()

        f_head.addWidget(QLabel("<b>FRONT STRUCTURE</b>"))

        self.layer_count_label = QLabel("0 layers")

        f_head.addStretch()

        self.detach_btn = QPushButton("Detach")

        self.detach_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.detach_btn.setToolTip("Open the front layer table in a separate floating window.")

        self.detach_btn.clicked.connect(self.detach_front_table)

        f_head.addWidget(self.detach_btn)

        f_head.addWidget(self.layer_count_label)

        f_lay.addLayout(f_head)

        self.front_table = QTableWidget(0, 5)

        self.front_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)", "Var", "Del"])

        header = self.front_table.horizontalHeader()

        self.front_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.front_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        for idx, width in enumerate((55, 70, 80, 40, 40)):
            header.resizeSection(idx, width)

        self.front_table.verticalHeader().setVisible(False)

        self.front_table.setAlternatingRowColors(True)

        table_font = self.front_table.font()

        if table_font.pointSize() > 0:
            table_font.setPointSize(max(8, table_font.pointSize() - 1))

            self.front_table.setFont(table_font)

        f_lay.addWidget(self.front_table)

        # Install event filter for Excel copy/paste

        self.front_table.installEventFilter(self)

        # Manipulation Buttons

        f_btns = QHBoxLayout()

        btn_defs = [
            ("Add", self.add_front_layer, QStyle.StandardPixmap.SP_FileDialogNewFolder),
            ("Remove", self.del_front_layer, QStyle.StandardPixmap.SP_TrashIcon),
            ("Undo", self._undo, QStyle.StandardPixmap.SP_ArrowBack),
            ("Thin", self.remove_thinnest, QStyle.StandardPixmap.SP_ArrowDown),
            ("Reset", self.reset_qwot, QStyle.StandardPixmap.SP_BrowserReload),
        ]

        _btn_tooltips = {
            "Add": "Add a new layer below the current selection.",
            "Remove": "Remove the selected layer from the stack.",
            "Undo": "Undo the last change to the layer table.",
            "Thin": "Remove the thinnest layer (useful for topology simplification).",
            "Reset": "Reset all QWOT values to 1.0 (quarter-wave optical thickness).",
        }

        for txt, func, icon in btn_defs:
            b = QPushButton(txt)

            b.setIcon(self.style().standardIcon(icon))

            b.clicked.connect(func)

            b.setToolTip(_btn_tooltips.get(txt, ""))

            f_btns.addWidget(b)

        self.undo_btn = f_btns.itemAt(2).widget()

        self.undo_btn.setEnabled(False)

        f_lay.addLayout(f_btns)

        self.pareto_btn = QPushButton("🏆 Open Pareto Front")

        self.pareto_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.pareto_btn.setToolTip(
            "Open the Pareto Front window: trade-off between RMSE and number of layers N.\n"
            "Double-click a row to load the corresponding design."
        )

        self.pareto_btn.setStyleSheet("""

            QPushButton {

                background-color: #2b3a42;

                color: #e2e8f0;

                font-weight: bold;

                font-size: 14px;

                padding: 10px;

                border-radius: 5px;

                border: 1px solid #4a5568;

            }

            QPushButton:hover {

                background-color: #3f515d;

            }

        """)

        self.pareto_btn.clicked.connect(self._show_pareto_window)

        f_lay.addWidget(self.pareto_btn)

        self.front_tabs.addTab(self.front_container, "Structure")

        # Pareto chart will be created in a separate window

        self.pareto_table = QTableWidget(0, 8)

        self.pareto_table.setHorizontalHeaderLabels(
            ["N", "Best RMSE", "dₘᵢₙ(nm)", "Best MC +/-0.3nm", "dₘᵢₙ(nm)", "Best Fab", "dₘᵢₙ Fab", "RMSE/N"]
        )

        self.pareto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.pareto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.pareto_table.verticalHeader().setVisible(False)

        self.pareto_table.setAlternatingRowColors(True)

        font = self.pareto_table.font()

        font.setPointSize(max(8, font.pointSize() - 1))

        self.pareto_table.setFont(font)

        self.pareto_table.cellDoubleClicked.connect(self._load_pareto_design)

        # Pareto window will be created on demand

        self.pareto_window = None
        self._pareto_initialized = False

        return self.front_tabs

    def _build_target_table_widget(self) -> QWidget:
        """Constructs spectral targets table widget"""

        tgt_widget = QWidget()

        t_lay = QVBoxLayout(tgt_widget)

        t_lay.addWidget(QLabel("<b>SPECTRAL TARGETS</b>"))

        # Table with adaptive columns by mode

        self.target_table = QTableWidget(0, 6)

        self._update_target_table_headers()

        self.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.target_table.setAlternatingRowColors(True)

        t_lay.addWidget(self.target_table)

        t_btns = QHBoxLayout()

        bt_add = QPushButton("Add Target")

        bt_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        bt_add.setToolTip(
            "Add a new spectral target row (lambdamin, lambdamax, Tmin, Tmax, Weight).\n"
            "Double-click a cell to edit values directly."
        )

        bt_add.clicked.connect(self.add_target)

        bt_del = QPushButton("Remove")

        bt_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        bt_del.setToolTip("Remove the selected spectral target row.")

        bt_del.clicked.connect(self.del_target)

        t_btns.addWidget(bt_add)

        t_btns.addWidget(bt_del)

        t_lay.addLayout(t_btns)

        return tgt_widget

    def _toggle_oblique_mode(self, state: int) -> None:
        """Toggle oblique mode and update UI"""

        self.oblique_mode = state == Qt.CheckState.Checked.value

        self._update_target_table_headers()

        # Convert existing targets if needed

        if self.oblique_mode:
            # Convert normal to oblique targets

            if hasattr(self, "target_widgets") and len(self.target_widgets) > 0:
                self.oblique_targets = []

                for tgt in self.target_widgets:
                    if isinstance(tgt, Target):
                        oblique_tgt = ObliqueTarget(
                            angle=0.0,
                            pol="s",
                            target_type="T",
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                            include_backside=True,
                        )

                        self.oblique_targets.append(oblique_tgt)

        else:
            # Convert oblique to normal targets

            if len(self.oblique_targets) > 0:
                self.target_widgets = []

                for tgt in self.oblique_targets:
                    if isinstance(tgt, ObliqueTarget):
                        normal_tgt = Target(
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                        )

                        self.target_widgets.append(normal_tgt)

        # Reload table

        self._load_targets_to_table()

        self._schedule_eval(True)

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self):
            self.status_label.setText("Logs copied to clipboard.")

    def _build_status_bar(self) -> None:
        """Constructs status bar"""

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.best_rmse_label = QLabel("Best RMSE: N/A")

        self.best_rmse_label.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-weight: bold; padding-left: 15px; padding-right: 15px;"
        )

        self.status_label = CertusStatusPill("Ready", "ready")

        self.stats_label = QLabel("♟️ 0 minima  | 🎲 0 evals  | 🌈️ 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.zoom_label = QLabel("Zoom 100%")
        self.zoom_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding: 0 8px; }}"
        )

        self.progress_widget = EnhancedProgressWidget()

        self.log_btn = QPushButton("Logs")

        self.log_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.log_btn.setToolTip("Show or hide the log panel and optimization detail.")

        self.log_btn.setCheckable(True)

        self.log_btn.setChecked(False)

        self.log_btn.clicked.connect(self.toggle_logs)

        self.log_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")

        self.status_bar.addWidget(self.log_btn)

        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.zoom_label)

        self.status_bar.addPermanentWidget(self.stats_label)

        self.status_bar.addPermanentWidget(self.best_rmse_label)

        self.status_bar.addPermanentWidget(self.progress_widget)

    # =========================================================================

    # HELPERS UI

    # =========================================================================

    def _apply_preset(self, name: str, n4_spin: QDoubleSpinBox, n7_spin: QDoubleSpinBox) -> None:
        """Applies Cauchy preset and updates spinbox states."""

        if name in CAUCHY_PRESETS:
            vals = CAUCHY_PRESETS[name]

            if vals[0] > 0:
                n4_spin.setValue(vals[0])

                n7_spin.setValue(vals[1])

        # Enable/disable spinboxes based on preset

        is_custom = name == "Custom"

        n4_spin.setReadOnly(not is_custom)

        n7_spin.setReadOnly(not is_custom)

        # Visual distinction for readonly state

        style = "" if is_custom else f"background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_SUB};"

        n4_spin.setStyleSheet(style)

        n7_spin.setStyleSheet(style)

    def _setup_shortcuts(self) -> None:
        """Configures keyboard shortcuts"""

        QShortcut(QKeySequence("Ctrl+E"), self, lambda: self._schedule_eval(True))

        QShortcut(QKeySequence("Ctrl+O"), self, lambda: self.run_optim("local"))

        QShortcut(QKeySequence("Ctrl+G"), self, lambda: self.run_optim("global"))

        QShortcut(QKeySequence("Ctrl+S"), self, self.save_config)

        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)

        install_standard_shortcuts(
            self,
            run=lambda: self.run_optim("global"),
            stop=self.stop_optim,
            help=self.open_help,
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
            extra={"Ctrl+L": lambda: getattr(self, "toggle_logs", lambda: None)()},
        )

        def _on_spectrum_drop(paths) -> None:
            if paths and hasattr(self, "load_config"):
                self.load_config(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_spectrum_drop, extensions=("json", "csv", "xlsx", "xls"))

    def _toggle_back_stack(self, state: int) -> None:
        """Toggle backside group visibility"""

        self.back_group.setVisible(bool(state))

        self._schedule_eval(True)


    # =========================================================================

    # LAYER MANAGEMENT

    # =========================================================================

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox) -> None:
        """DESIGN specific: update Tikhonravov on QWOT change."""

        spinbox.valueChanged.connect(self._on_tikhonravov_points_changed)

    def _on_schedule_eval_signal(self, *_args) -> None:

        self._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self._schedule_eval(True)


    def _on_tikhonravov_points_changed(self, *_args) -> None:

        QTimer.singleShot(300, self._update_tikhonravov_points)

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

    def _on_layer_added(self) -> None:
        """DESIGN specific: update thickness display and points."""

        self._update_thickness_display()

        QTimer.singleShot(300, self._update_tikhonravov_points)

    def _on_layer_deleted(self) -> None:
        """DESIGN specific: update thickness display and run local optimization."""

        self._update_thickness_display()

        self.run_optim("local")

    def add_back_layer(self) -> None:
        """Adds back layer"""

        if self.back_table.rowCount() >= CFG.MAX_LAYERS:
            return

        mat = "H"

        if self.back_table.rowCount() > 0:
            prev = self._safe_get_combo_text(self.back_table.rowCount() - 1, 0, self.back_table)

            if prev:
                mat = "L" if prev == "H" else "H"

        self._add_back_row(mat, 1.0)

        self._schedule_eval()

    def del_back_layer(self) -> None:
        """Removes back layer"""

        r = self.back_table.currentRow()

        if r < 0 and self.back_table.rowCount() > 0:
            r = self.back_table.rowCount() - 1

        if r >= 0:
            self.back_table.removeRow(r)

            self._schedule_eval(True)

    def remove_thinnest(self) -> None:
        """Removes thinnest layer (identically to the left panel button).

        Rules:

        - Finds the thinnest layer in the entire stack (including boundaries).

        - If it's a boundary layer (first or last), no merge step.

        - If it's an interior layer, merges adjacent identical materials.

        - Ends with a local polish and Pareto record.

        """

        N = self.front_table.rowCount()

        if N <= 1:
            return

        # Get current thicknesses

        ep = self.ep_current

        if ep is None or len(ep) != N:
            # Fallback if display not up to date

            self._update_thickness_display()

            ep = self.ep_current

            if ep is None:
                return

        # Identify thinnest layer

        r = int(np.argmin(ep))

        is_boundary = r == 0 or r == N - 1

        self._save_undo_state()

        self.log(f"Remove layer {r + 1}: {ep[r]:.1f}nm", "INFO")

        self.front_table.removeRow(r)

        if not is_boundary:
            # Merging is only relevant when removing an interior layer

            # as it brings two previously separated layers together.

            self._merge_adjacent_layers()

        else:
            self._update_layer_count()

            self._update_thickness_display()

        # Update target count and run optimization

        self._target_layer_count = self.front_table.rowCount()

        self.run_optim("local", keep_history=True)

    def _trigger_post_undo_action(self) -> None:
        """DESIGN specific post-undo action."""

        self.run_optim("local")


    def _paste_from_excel(self) -> None:
        """Pastes data from Excel into layer table"""

        clipboard = QApplication.clipboard()

        text = clipboard.text()

        if not text:
            return

        try:
            # Excel parse (tabs/cols, newlines/rows)

            lines = text.strip().split("\n")

            rows_data = []

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Split columns (tabs or multiple spaces)

                cols = line.split("\t")

                if len(cols) < 2:  # If no tab, try with multiple spaces
                    cols = [c for c in line.split(" ") if c]

                if len(cols) < 2:
                    continue

                # Parse columns

                # Fmt: Mat, QWOT, [Thick], [Var]

                mat = cols[0].strip()

                qwot_str = cols[1].strip()

                # Check if material is valid

                materials = [m for m in CFG.MATERIALS if m != "Substrate"]

                if mat not in materials:
                    # Try to find match (case insensitive)

                    mat_lower = mat.lower()

                    mat_found = None

                    for m in materials:
                        if m.lower() == mat_lower:
                            mat_found = m

                            break

                    if mat_found:
                        mat = mat_found

                    else:
                        self.log(f"Invalid material ignored: {mat}", "WARNING")

                        continue

                # Parser QWOT

                try:
                    qwot = float(qwot_str.replace(",", "."))

                except ValueError:
                    self.log(f"Invalid QWOT value ignored: {qwot_str}", "WARNING")

                    continue

                # Parse Var (optional, col 3 or 4)

                var = True  # default

                if len(cols) >= 3:
                    var_str = cols[2].strip().lower()

                    # Accept various forms: 0/1, true/false, yes/no, etc.

                    if var_str in ["0", "false", "f", "non", "n", "no", ""]:
                        var = False

                    elif var_str in ["1", "true", "t", "oui", "o", "yes", "y"]:
                        var = True

                    # If number, use as thickness (legacy format)

                    else:
                        try:
                            float(var_str.replace(",", "."))

                            # Likely a thickness, so Var remains True

                        except ValueError:
                            # Neither number nor boolean, ignore

                            pass

                rows_data.append((mat, qwot, var))

            if not rows_data:
                self.log("No valid data to paste", "WARNING")

                return

            # Save state for undo

            self._save_undo_state()

            # Clear table or append depending on selection

            current_row = self.front_table.currentRow()

            if current_row >= 0:
                # Paste from selected row

                start_row = current_row

            else:
                # Clear table and paste from start

                self.front_table.blockSignals(True)

                self.front_table.setRowCount(0)

                self.front_table.blockSignals(False)

                start_row = 0

            # Add rows

            self.front_table.blockSignals(True)

            for i, (mat, qwot, var) in enumerate(rows_data):
                row = start_row + i

                if row >= self.front_table.rowCount():
                    self._add_front_row(mat, qwot, var)

                else:
                    # Replace existing row

                    # Mat

                    cb = self._create_combo(mat)

                    cb.currentIndexChanged.connect(self._merge_adjacent_layers)

                    self.front_table.setCellWidget(row, 0, cb)

                    # QWOT

                    sb = self._create_spin(qwot, dec=6)

                    sb.valueChanged.connect(self._on_schedule_eval_signal)

                    sb.valueChanged.connect(self._on_tikhonravov_points_changed)

                    self.front_table.setCellWidget(row, 1, sb)

                    # Var

                    chk = self.front_table.cellWidget(row, 3).findChild(QCheckBox)

                    if chk:
                        chk.setChecked(var)

                    del_cw = self.front_table.cellWidget(row, 4)

                    if del_cw:
                        del_chk = del_cw.findChild(QCheckBox)

                        if del_chk:
                            del_chk.setChecked(False)

            self.front_table.blockSignals(False)

            self._update_layer_count()

            self._schedule_eval()

            self.log(f"{len(rows_data)} row(s) pasted from Excel", "SUCCESS")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("[DESIGN.paste_from_excel] failed to paste from Excel | error=%s", e, exc_info=True)

    # =========================================================================

    # TARGET MANAGEMENT

    # =========================================================================

    def add_target(self) -> None:
        """Adds spectral target"""

        r = self.target_table.rowCount()

        self.target_table.insertRow(r)

        col_idx = 0

        # Active Checkbox

        chk = QCheckBox()

        chk.setToolTip("Enable or disable this target.")

        chk.setChecked(True)

        chk.stateChanged.connect(self._schedule_eval)

        chk.stateChanged.connect(self._update_optim_point_count)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.target_table.setCellWidget(r, col_idx, cw)

        col_idx += 1

        if self.oblique_mode:
            # Oblique: Ang, Pol, Type, lmin, lmax, Vmin, Vmax, W

            # Angle

            angle_sb = self._create_spin(0.0, dec=1, minv=0, maxv=90)

            angle_sb.setToolTip("Incident angle (degrees).")

            angle_sb.valueChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, angle_sb)

            col_idx += 1

            # Polarization

            pol_combo = QComboBox()

            pol_combo.setToolTip("Target polarization: s, p, or Avg (unpolarized average).")

            pol_combo.addItems(["s", "p", "Avg"])

            pol_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, pol_combo)

            col_idx += 1

            # Type (R or T)

            type_combo = QComboBox()

            type_combo.setToolTip("Target type: Reflectance (R) or Transmittance (T).")

            type_combo.addItems(["R", "T"])

            type_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, type_combo)

            col_idx += 1

            # lambdamin, lambdamax

            for val, dec in [(400.0, 1), (700.0, 1)]:
                sb = self._create_spin(val, dec=dec, minv=200, maxv=20000)

                tt = "Target wavelength range start (nm)." if val == 400.0 else "Target wavelength range end (nm)."

                sb.setToolTip(tt)

                sb.valueChanged.connect(self._schedule_eval)

                sb.valueChanged.connect(self._update_optim_point_count)

                sb.valueChanged.connect(lambda _checked=False: QTimer.singleShot(300, self._update_tikhonravov_points))

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

            # Val min, Val max, Weight

            for i, (val, dec, maxv) in enumerate([(0.0, 3, 1), (1.0, 3, 1), (1.0, 1, 100)]):
                sb = self._create_spin(val, dec=dec, minv=0, maxv=maxv)

                tts = ["Minimum target value.", "Maximum target value.", "Weight multiplier for this target."]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self._schedule_eval)

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        else:
            # Normal Mode: lmin, lmax, Tmin, Tmax, Weight

            defs = [400.0, 700.0, 0.0, 0.5, 1.0]

            decs = [1, 1, 3, 3, 1]

            ranges = [(200, 20000), (200, 20000), (0, 1), (0, 1), (0, 100)]

            for i, val in enumerate(defs):
                sb = self._create_spin(val, dec=decs[i], minv=ranges[i][0], maxv=ranges[i][1])

                tts = [
                    "Target wavelength range start (nm).",
                    "Target wavelength range end (nm).",
                    "Minimum target Transmittance (0-1).",
                    "Maximum target Transmittance (0-1).",
                    "Weight multiplier for this target.",
                ]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self._on_schedule_eval_signal)

                if i in [0, 1]:
                    sb.valueChanged.connect(self._update_optim_point_count)

                    sb.valueChanged.connect(lambda _checked=False: QTimer.singleShot(300, self._update_tikhonravov_points))

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        self._update_optim_point_count()

    def del_target(self) -> None:
        """Removes spectral target"""

        r = self.target_table.currentRow()

        if r >= 0:
            self.target_table.removeRow(r)

            self._schedule_eval()

            self._update_optim_point_count()

            QTimer.singleShot(200, self._update_tikhonravov_points)

    def _get_optim_wls(self) -> np.ndarray:
        """Calculates wavelengths for optimization"""

        if self.oblique_mode:
            tgts = self._get_oblique_tgts()

        else:
            tgts = self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            return np.array([])

        wls_list = []

        n_points = self.points_per_target_spin.value()

        for t in active:
            start = max(t.lmin, 1e-3)

            end = max(t.lmax, start + 1e-3)

            if n_points > 1:
                # Uniform grid in wavenumbers (1/lambda)

                sigma_min = 1.0 / end

                sigma_max = 1.0 / start

                # Linear grid in wavenumbers

                sigma_grid = np.linspace(sigma_min, sigma_max, n_points)

                # Convert back to wavelengths

                grid = 1.0 / sigma_grid

            else:
                grid = np.array([start])

            wls_list.append(grid)

        if wls_list:
            wls = np.unique(np.concatenate(wls_list))

        else:
            wls = np.array([])

        return wls

    def _update_optim_point_count(self) -> None:
        """Updates optimization point counter"""

        wls = self._get_optim_wls()

        self.npts_spin.setValue(len(wls))

    def _calculate_tikhonravov_points(self) -> int:
        """

        Calculates recommended points per target using Tikhonravov formula.

        Formula: N = 2 * L * delta_nu * margin

        Where:

        - L = total optical thickness in nm (Sum n_i * d_i)

        - delta_nu = spectral interval in wavenumbers (1/nm) = 1/l_min - 1/l_max

        - margin = 10 (safety factor)

        The product L * delta_nu is dimensionless. The factor 2 comes from Nyquist criterion.

        Returns

        -------

        int

            Recommended points per target

        """

        try:
            # Retrieve necessary data

            mats = self._get_materials()

            stack = self._get_front_stack()

            # Use correct targets based on mode (normal or oblique)

            if self.oblique_mode:
                tgts = self._get_oblique_tgts()

            else:
                tgts = self._get_tgts()

            l0 = self.l0_spin.value()

            if not stack or not mats:
                return 50  # Default

            # Calculate total optical thickness L

            # Use current thicknesses if available, else calc from QWOT

            if self.ep_current is not None and len(self.ep_current) == len(stack):
                ep = self.ep_current

            else:
                ep = init_thickness(stack, l0, mats)

                if ep is None:
                    return 50

            # Find global spectral interval of active targets

            active_tgts = [t for t in tgts if t.valid()]

            if not active_tgts:
                return 50

            lambda_min = min(t.lmin for t in active_tgts)

            lambda_max = max(t.lmax for t in active_tgts)

            if lambda_max <= lambda_min or lambda_min < 1e-3:
                return 50

            # Calculate total optical thickness L = Sum(n_i * d_i) in nm

            # Use reference wavelength at center of spectral range

            wl_ref = (lambda_min + lambda_max) / 2.0  # nm

            L_total = 0.0

            for i, layer in enumerate(stack):
                if i >= len(ep):
                    continue

                mat = mats.get(layer.mat)

                if mat:
                    n_ref = mat.get_nk(np.array([wl_ref]))[0].real

                    L_total += n_ref * ep[i]

            if L_total < 1e-6:
                return 50

            # Convert spectral interval to wavenumbers (1/nm)

            nu_min = 1.0 / lambda_max  # Plus petite longueur d'onde = plus grand nombre d'onde

            nu_max = 1.0 / lambda_min  # Plus grande longueur d'onde = plus petit nombre d'onde

            delta_nu = nu_max - nu_min  # en 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * marge

            nu_min = 1.0 / lambda_max

            nu_max = 1.0 / lambda_min

            delta_nu = nu_max - nu_min  # in 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * margin

            # L_total(nm)*dn(1/nm) = dimensionless

            marge = 10.0

            N = 2.0 * L_total * delta_nu * marge

            # Round and clamp to reasonable limits

            N_int = int(np.ceil(N))

            N_int = max(10, min(5000, N_int))

            return N_int

        except (ValueError, TypeError) as e:
            logging.debug("[DESIGN.profile] could not calculate Tikhonravov point count | error=%s", e)

            return 50  # Default on error

    def _update_tikhonravov_points(self) -> None:
        """Automatically updates points count using Tikhonravov."""

        try:
            tikhon_points = self._calculate_tikhonravov_points()

            if tikhon_points > 0:
                current_val = self.points_per_target_spin.value()

                # Update only if change significant

                if abs(tikhon_points - current_val) > max(5, current_val * 0.15):  # Threshold 15% or 5 points
                    self.points_per_target_spin.blockSignals(True)

                    self.points_per_target_spin.setValue(tikhon_points)

                    self.points_per_target_spin.blockSignals(False)

                    self._update_optim_point_count()

                    self.log(
                        f"Tikhonravov: Auto-updated points/target to {tikhon_points}",
                        "INFO",
                    )

        except (AttributeError, ValueError) as e:
            logging.debug("[DESIGN.profile] could not update Tikhonravov points | error=%s", e)

    # =========================================================================

    # GETTERS

    # =========================================================================

    def _get_materials(self) -> dict:
        """Retrieves configured materials."""

        try:
            result = {k: Material(w["n4"].value(), w["n7"].value()) for k, w in self.mat_widgets.items()}

            return result

        except (AttributeError, KeyError) as e:
            logging.debug("[DESIGN.profile] could not get materials | error=%s", e)

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        if not self.oblique_mode:
            return []  # Sinon mode normal : _get_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                active = chk.isChecked() if chk else False

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                angle = angle_w.value() if angle_w else 0.0

                # Polarisation

                pol_w = self.target_table.cellWidget(r, 2)

                polarization = pol_w.currentText() if pol_w else "s"

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                target_type = type_w.currentText() if type_w else "T"

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                lmin = lmin_w.value() if lmin_w else 400.0

                lmax = lmax_w.value() if lmax_w else 700.0

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                val_min = vmin_w.value() if vmin_w else 0.0

                val_max = vmax_w.value() if vmax_w else 1.0

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

                weight = weight_w.value() if weight_w else 1.0

                targets.append(
                    ObliqueTarget(
                        angle=angle,
                        pol=polarization,
                        target_type=target_type,
                        lmin=lmin,
                        lmax=lmax,
                        tmin=val_min,
                        tmax=val_max,
                        w=weight,
                        on=active,
                        include_backside=True,
                    )
                )

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug("[DESIGN.profile] could not get oblique target row | error=%s", e)

        return targets

    def _load_targets_to_table(self) -> None:
        """Loads targets into table from internal lists"""

        self.target_table.setRowCount(0)

        if self.oblique_mode:
            for tgt in self.oblique_targets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                if angle_w:
                    angle_w.setValue(tgt.angle)

                # Pol

                pol_w = self.target_table.cellWidget(r, 2)

                if pol_w:
                    pol_w.setCurrentText(tgt.pol)

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                if type_w:
                    type_w.setCurrentText(tgt.target_type)

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                if lmin_w:
                    lmin_w.setValue(tgt.lmin)

                if lmax_w:
                    lmax_w.setValue(tgt.lmax)

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                if vmin_w:
                    vmin_w.setValue(tgt.tmin)

                if vmax_w:
                    vmax_w.setValue(tgt.tmax)

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

                if weight_w:
                    weight_w.setValue(tgt.w)

        else:
            for tgt in self.target_widgets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # lambdamin, lambdamax, Tmin, Tmax, Weight

                for i, val in enumerate([tgt.lmin, tgt.lmax, tgt.tmin, tgt.tmax, tgt.w]):
                    w = self.target_table.cellWidget(r, i + 1)

                    if w:
                        w.setValue(val)

    def _on_front_thickness_updated(self) -> None:
        """DESIGN specific: update Tikhonravov points."""

        QTimer.singleShot(150, self._update_tikhonravov_points)

    # =========================================================================

    # EVALUATION

    # =========================================================================

    def run_eval(self) -> None:
        """

        Runs spectral evaluation of the current design.

        This method performs complete spectral evaluation including:

        - JIT compilation warmup check

        - Material and stack validation

        - Target configuration setup

        - Worker thread initialization and execution

        - Result processing and visualization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs evaluation progress and timing

            - Handles both normal and oblique modes

            - Emits progress signals during execution

            - Updates UI components with results

        """

        _eval_start = time.time()

        if not spectrum_eval_run_preamble(self, self.run_eval):
            return

        cfg = spectrum_eval_build_worker_cfg(self, "design")

        if cfg is None:
            return

        spectrum_eval_start_worker(self, cfg, _eval_start)

    def _on_eval_finished(self, data: Dict, generation_id: int | None = None) -> None:
        """

        Callback after spectral evaluation completion.

        This method processes evaluation results including:

        - Result data storage and validation

        - Visualization data processing

        - Plot updates and UI refresh

        - Performance timing and logging

        Args:

            self: CertusDesign instance

            data: Evaluation result dictionary with spectral data

        Returns:

            None

        Notes:

            - Logs evaluation completion and timing

            - Handles both normal and oblique modes

            - Updates UI components with results

            - Stores results for subsequent operations

        """

        _finish_start = time.time()

        data_for_display = spectrum_eval_on_finished_prepare_display(self, data, generation_id)

        if data_for_display is None:
            return

        self.last_result = data_for_display

        # Self-export if pending (triggered by Case C or time budget completion)

        if getattr(self, "_export_pending", False):
            self._export_pending = False

            QTimer.singleShot(100, self.export_results)

        res_vis = data_for_display["vis"]

        res_optim = data_for_display["optimization"]

        oblique_mode = data_for_display.get("oblique_mode", False)

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        plot_targets = self._get_plot_targets("spectrum", self.spectrum_plot)

        spectrum_eval_plot_curves(
            self,
            data_for_display=data_for_display,
            plot_targets=plot_targets,
            res_vis=res_vis,
            res_optim=res_optim,
            oblique_mode=oblique_mode,
        )

        rmse = data_for_display.get("rmse")

        n_points = self.points_per_target_spin.value()

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | {src_name} | Points/Target: {n_points} ({n_total} total)"

            else:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        if optim_rmse_is_valid_for_log(rmse):
            title += f" - RMSE: {optim_rmse_display_string(rmse)}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self, res_vis=res_vis, oblique_mode=oblique_mode)

        self._plot_profile(
            data_for_display["ep"],
            self._get_front_stack(),
            data_for_display.get("ep_back"),
            self._get_back_stack(),
        )

        self._plot_nk()

        logging.info("[DESIGN._on_eval_finished] completed callback | elapsed_ms=%.1f", (time.time() - _finish_start) * 1000)

        self.log(
            f"Evaluation OK. RMSE: {optim_rmse_display_string(rmse)}"
            if optim_rmse_is_valid_for_log(rmse)
            else "Evaluation OK.",
            "SUCCESS",
        )

        self._set_busy(False)

        logging.info("[DESIGN._on_eval_finished] evaluation cycle complete | ui_ready=True")

        # Systematic Pareto update after any evaluation (manual edit or optimization)

        # data["ep"] and data["rmse"] are available from EvalWorker

        self._update_pareto_record(data_for_display.get("ep"), data_for_display.get("rmse"))



    # =========================================================================

    # OPTIMIZATION

    # =========================================================================

    @safe_ui_action
    def run_optim(self, mode: str, keep_history: bool = False, **kwargs) -> None:
        """

        Start an optimization cycle.

        logger = getattr(self, "logger", None)
        if logger:
            logger.info(
                "DESIGN run_optim enter | mode=%s | keep_history=%s | kwargs_keys=%s",
                mode,
                bool(keep_history),
                ",".join(sorted(map(str, kwargs.keys()))) if kwargs else "-",
            )

        Entry point for the hybrid design workflow. Three optimization modes

        are available, each with different search scope and bounds:

        - ``'global'``: Full PGLOBAL stochastic search over [0, 1.2×QWOT].

          Used for initial design exploration with HPO-tuned hyperparameters.

        - ``'healing'``: Restricted PGLOBAL search within +/-Deltad of current

          thicknesses, where Deltad = lambda₀/(10·n) per layer (~40% QWOT).

          Triggered automatically after smart_cleanup removes layers.

        - ``'local'``: Narrow L-BFGS-B refinement within +/-2 nm.

          Used for final polish and intra-needle-cycle optimization.

        The complete automated workflow is::

            Global PGLOBAL

            -> smart_cleanup (remove <1nm, merge adjacent)

            -> Healing (restricted global +/-Deltad + local polish)

            -> Needle insertion loop (Overshoot +20%)

            -> Prune thinnest layers back to target

            -> Final local polish

            -> Complete

        This method performs optimization including:

        - Mode-specific parameter setup and bounds

        - Target validation and configuration

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusDesign instance

            mode: Optimization mode: ``'global'``, ``'healing'``, or ``'local'``

            keep_history: If False (default), resets all workflow state for fresh start.

                       If True, preserves state for internal continuation.

        Returns:

            None

        Notes:

            - Logs optimization progress and results

            - Emits progress signals during execution

            - Handles different optimization modes automatically

            - Supports both fresh start and continuation modes

        """

        # Logging start

        active_mode = "oblique" if self.oblique_mode else "normal"
        active_targets = [t for t in (self._get_oblique_tgts() if self.oblique_mode else self._get_tgts()) if t.valid()]

        logging.info(
            "[DESIGN.start_optimization] starting optimization | mode=%s | keep_history=%s | active_targets=%d | samples_per_iter=%s | max_iterations=%s",
            mode,
            keep_history,
            len(active_targets),
            self.n100_spin.value(),
            self.global_cycles_spin.value(),
        )
        logging.info(
            "[DESIGN.start_optimization] incidence configuration | incidence=%s | active_targets=%d",
            active_mode,
            len(active_targets),
        )

        self._shutdown_previous_optim_worker()

        # INTERNAL RESTART MANAGEMENT

        self._is_internal_restart = keep_history

        # Guard: if user clicked STOP, refuse internal restarts

        if keep_history and getattr(self, "_workflow_stopped", False):
            self.log("Workflow stopped by user, ignoring internal restart.", "WARNING")

            self._set_busy(False)

            return

        if not keep_history:
            self._reset_run_optim_workflow_state(mode)

        else:
            self.log(f"Continuing optimization ({mode})...", "INFO")

        stack, mats, active, ep0, wls = self._collect_run_optim_inputs()
        if stack is None:
            return

        # Calculate limits with 20% margin for display

        wls_min = self._calculate_wls_min_with_margin(active)

        wls_max = self._calculate_wls_max_with_margin(active)

        # Configuration

        if mode == "local":
            cfg = {
                "mode": "local",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": CFG.MAX_FEVAL_LOCAL,
                "n100": 50,
                "max_iter": 10,
                "local_delta_nm": 2.0,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        elif mode == "healing":
            cfg = {
                "mode": "healing",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": 10000,
                "n100": 500,
                "max_iter": 8,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        else:
            pre_polish = False

            if hasattr(self, "pre_polish_check"):
                pre_polish = self.pre_polish_check.isChecked()

            # If needle growth is enabled, use ultra-fast global (just seed)

            # Needle will iterate and refine - no need for exhaustive global

            allow_growth = getattr(self, "allow_growth_check", None)

            needle_coupled = allow_growth and allow_growth.isChecked()

            if needle_coupled:
                g_max_feval = min(CFG.MAX_FEVAL_GLOBAL, 50000)

                g_n100 = min(self.n100_spin.value(), 1500)

                g_max_iter = min(self.global_cycles_spin.value(), 8)

                g_max_clusters = min(self.max_clusters_spin.value(), 5)

                self.log(
                    "Global+Needle: ultra-fast global (seed for needle iterations)",
                    "INFO",
                )

            else:
                g_max_feval = CFG.MAX_FEVAL_GLOBAL

                g_n100 = self.n100_spin.value()

                g_max_iter = self.global_cycles_spin.value()

                g_max_clusters = self.max_clusters_spin.value()

            cfg = {
                "mode": "global",
                "pre_polish": pre_polish,
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": g_max_feval,
                "n100": g_n100,
                "max_iter": g_max_iter,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "max_clusters": g_max_clusters,
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        # Start Worker

        self._set_busy(True)

        self._initialize_run_optim_progress_state(cfg, keep_history)

        if kwargs:
            cfg.update(kwargs)

        self.optim_worker = OptimWorker(cfg)

        # Carry best RMSE across internal restarts so GUI doesn't regress

        if keep_history and hasattr(self, "_workflow_best_rmse"):
            self.optim_worker.best_rmse_seen = self._workflow_best_rmse

        self.optim_thread = QThread()
        self.optim_worker.moveToThread(self.optim_thread)

        self.optim_thread.started.connect(self.optim_worker.run)

        self.optim_worker.signals.finished.connect(self.optim_thread.quit)
        self.optim_worker.signals.finished.connect(self._on_optim_done)
        self.optim_worker.signals.finished.connect(self.optim_worker.deleteLater)

        self.optim_worker.signals.error.connect(self.optim_thread.quit)
        self.optim_worker.signals.error.connect(self._on_error)
        self.optim_worker.signals.error.connect(self.optim_worker.deleteLater)

        self.optim_worker.signals.result.connect(self._on_intermediate_spectrum)

        self.optim_worker.signals.progress.connect(self._on_optim_progress)

        self.optim_worker.signals.update_stats.connect(self._on_stats_update)

        self.optim_thread.finished.connect(self.optim_thread.deleteLater)

        self.optim_thread.start()

    def _reset_run_optim_workflow_state(self, mode: str) -> None:
        """Reset workflow state and UI counters for a fresh optimization start."""

        self._target_layer_count = self.front_table.rowCount()

        self._topology_stable = True

        self._overshoot_active = False

        self._overshoot_done = False

        self._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        self._initial_cleared = False

        self._clean_live_curves()

        self.log(f"Starting {mode} optimization (PGLOBAL)...", "INFO")

        self.stat_counters["EVAL"] = 0

        self.accumulated_evals = 0

        self.stat_counters["MINIMA"] = 0

        self.update_stats_display()

        self.best_rmse_label.setText("Best RMSE: N/A")

        self._workflow_best_rmse = float("inf")

        self._best_eval_result = None

        self._best_eval_rmse = float("inf")

        self._workflow_stopped = False

        self._decimation_done = False

        self._export_pending = False

        self._post_optim_start_time = None

        self._stack_info_best_ep = None

        self._stack_info_best_rmse = None

        self._stack_info_last_update = 0.0

        import time as _time

        self._workflow_wall_start = _time.time()

        self.mse_data = {"iterations": [], "errors": []}

        if self.convergence_curve is not None:
            self.convergence_curve.setData([], [])

    def _shutdown_previous_optim_worker(self) -> None:
        """Stop any running optimization worker before starting a new cycle."""

        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        if self.optim_thread is not None:
            try:
                stop_qt_worker_thread_safely(
                    self.optim_thread,
                    self.optim_worker,
                    timeout_ms=2000,
                    logger=getattr(self, "logger", None),
                )
            except RuntimeError:
                pass

        self.optim_worker = None
        self.optim_thread = None

    def _collect_run_optim_inputs(self) -> tuple:
        """Collect and validate inputs required by run_optim."""

        stack = self._get_front_stack()

        if not [l for l in stack if l.var]:
            self.log("No variable layers.", "WARNING")

            return None, None, None, None, None

        mats = self._get_materials()

        tgts = self._get_oblique_tgts() if self.oblique_mode else self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            self.log("No valid targets.", "WARNING")

            return None, None, None, None, None

        ep0 = init_thickness(stack, self.l0_spin.value(), mats)

        wls = self._get_optim_wls()

        return stack, mats, active, ep0, wls

    def _initialize_run_optim_progress_state(self, cfg: dict, keep_history: bool) -> None:
        """Initialize progress counters and optional time budget for a run."""

        self._optim_max_iter = 100

        self._optim_current_iter = 0

        self._optim_n_evals = 0

        if keep_history:
            return

        _n = len(cfg.get("ep0", []))

        _mode = cfg.get("mode", "global")

        allow_growth = getattr(self, "allow_growth_check", None)

        _needle_coupled = allow_growth and allow_growth.isChecked() and _mode == "global"

        _global_time = 35.0 if _needle_coupled else 90.0

        if _needle_coupled:
            _post_budget = 60.0

        elif _n <= 10:
            _post_budget = 15.0

        elif _n <= 26:
            _post_budget = 15.0 + (_n - 10) * (60.0 - 15.0) / (26 - 10)

        else:
            _post_budget = 60.0 + (_n - 26) * (180.0 - 60.0) / (40 - 26)

        self.progress_widget.set_time_budget(_global_time + _post_budget)

        self.progress_widget.start()

    def _on_optim_progress(self, val: int, msg: str) -> None:
        """Callback for optimization progress update"""

        # val is PERCENTAGE (0-100) from OptimWorker

        # msg format: "Gen X | Evals: Y | Clusters: Z | Best: W"

        self._optim_current_iter = val

        # Extract "Gen X" for display

        gen_info = "Gen ?"

        if "Gen" in msg:
            try:
                gen_info = msg.split("|")[0].strip()

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

        # Update progress widget

        self.progress_widget.update(
            iteration=getattr(self, "_optim_current_iter", val),
            max_iter=getattr(self, "_optim_max_iter", 100),
            evals=getattr(self, "_optim_n_evals", 0),
            phase="PGLOBAL",
            extra_info=(f"{gen_info} | RMSE: {msg.split('Best:')[-1].strip()}" if "Best:" in msg else ""),
        )

        # Also update status label and log

        self.status_label.setText(msg)

        self.log(msg, "INFO")

    def _on_stats_update(self, stat_name: str, value: int) -> None:
        """Callback for stats update (MINIMA, EVAL, COLOR)"""

        if stat_name == "EVAL":
            self._optim_n_evals = value

            display_value = value + getattr(self, "accumulated_evals", 0)

            # Update progress widget with new eval count

            self.progress_widget.update(
                iteration=getattr(self, "_optim_current_iter", 0),
                max_iter=getattr(self, "_optim_max_iter", 100),
                evals=display_value,
                phase="PGLOBAL",
            )

        # Update stats label

        current = self.stats_label.text()

        if stat_name == "MINIMA":
            parts = current.split("|")

            if len(parts) >= 1:
                parts[0] = f"♟️ {value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "EVAL":
            display_value = value + getattr(self, "accumulated_evals", 0)

            parts = current.split("|")

            if len(parts) >= 2:
                parts[1] = f" 🎲 {display_value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "COLOR":
            parts = current.split("|")

            if len(parts) >= 3:
                parts[2] = f" 🌈️ {value}"

            self.stats_label.setText("|".join(parts))



    def _refresh_optim_target_scatter_foreground(self) -> None:
        """Ensure target scatter markers stay above live curves."""

        if self.target_scatter is None:
            return

        self.spectrum_plot.removeItem(self.target_scatter)

        self.spectrum_plot.addItem(self.target_scatter)







    def _apply_qw_values_to_front_table(self, qw: list[float], *, debug_failures: bool = False) -> None:
        """Apply QW values to the front table thickness column safely."""
        self.front_table.blockSignals(True)
        for r in range(self.front_table.rowCount()):
            try:
                sb = self.front_table.cellWidget(r, 1)
                if sb:
                    sb.setValue(qw[r] if r < len(qw) else 0.0)
            except (AttributeError, ValueError, IndexError) as e:
                if debug_failures:
                    logging.debug(f"Could not set qw value for row {r}: {e}")
        self.front_table.blockSignals(False)

    def _handle_stopped_workflow_result(self, d: Dict) -> None:
        """Finalize UI and keep best result when workflow is manually stopped."""
        self._stack_info_best_ep = None
        self._stack_info_best_rmse = None
        self.log("Workflow stopped by user.", "WARNING")
        self._set_busy(False)

        if d.get("ok", False) and d.get("ep") is not None:
            final_ep = np.asarray(d["ep"]).flatten()
            stack = self._get_front_stack()
            mats = self._get_materials()
            l0 = self.l0_spin.value()
            qw = optim_qwot_values_from_ep_stack(final_ep, stack, mats, l0)
            self._apply_qw_values_to_front_table(qw)
            self.ep_current = final_ep.copy()
            self._update_thickness_display()
            rmse = d.get("rmse", float("inf"))
            if optim_rmse_is_valid_for_log(rmse):
                self._workflow_best_rmse = rmse
                self._update_pareto_record(self.ep_current, rmse)
            rmse_msg = optim_rmse_display_string(rmse)
            self.log(f"Best result kept (RMSE: {rmse_msg}).", "SUCCESS")

        if get_export_config() and self.last_result:
            self._export_pending = True
            QTimer.singleShot(100, self.export_results)

    def _finalize_if_post_optim_budget_exceeded(self) -> bool:
        """Finalize workflow early when post-optimization orchestration exceeds time budget."""

        if getattr(self, "_post_optim_start_time", None) is None:
            self._post_optim_start_time = time.time()

        _n_layers = self.front_table.rowCount()
        _budget = optim_post_optim_time_budget_seconds(_n_layers)
        _elapsed = time.time() - self._post_optim_start_time

        if not (
            _elapsed > _budget
            and (
                hasattr(self, "_needle_cycle_step")
                or getattr(self, "_healing_phase", None) is not None
                or getattr(self, "_overshoot_active", False)
            )
        ):
            return False

        self.log(
            f"Time budget exceeded ({_elapsed:.0f}s > {_budget:.0f}s for {_n_layers} layers). Finalizing.",
            "WARNING",
        )

        self._healing_phase = None
        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)
            self._overshoot_active = False

        if get_export_config():
            self._export_pending = True
        self._schedule_eval(True)
        self.log("Optimization complete (time budget). Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False
        return True

    def _track_and_apply_post_optim_result(self, d: Dict) -> None:
        """Track workflow RMSE state and apply optimized QW values to the table."""
        final_ep = d["ep"]
        rmse_before_cleanup = d.get("rmse", float("inf"))

        if rmse_before_cleanup < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_before_cleanup

        if rmse_before_cleanup is not None and np.isfinite(rmse_before_cleanup) and rmse_before_cleanup >= 0.0:
            prev_gate_rmse = getattr(self, "_needle_recent_best_rmse", float("inf"))
            if rmse_before_cleanup < prev_gate_rmse - 1e-9:
                self._needle_recent_best_rmse = rmse_before_cleanup
                self._needle_no_improve_rounds = 0
            else:
                self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)
        else:
            self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)

        stack = self._get_front_stack()
        mats = self._get_materials()
        l0 = self.l0_spin.value()

        # Keep n4 convention for round-trip consistency with initialization.
        qw = []
        for i, layer in enumerate(stack):
            d_val = final_ep[i] if i < len(final_ep) else 0.0
            mat_obj = mats.get(layer.mat)
            n_val = 1.45
            if mat_obj:
                if hasattr(mat_obj, "n4"):
                    n_val = mat_obj.n4
                elif isinstance(mat_obj, dict):
                    n_val = mat_obj.get("n4", 1.45)
            val = (4.0 * n_val * d_val) / l0 if abs(l0) > 1e-9 else 0.0
            qw.append(val)

        self._apply_qw_values_to_front_table(qw, debug_failures=True)
        self._update_thickness_display()

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _handle_needle_cycle_step3(self, d: Dict) -> bool:
        """Handle Needle step-3 post-optimization logic. Returns True if flow consumed."""
        if not (hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 3):
            return False

        rmse_after_cleanup = d.get("rmse", float("inf"))
        needle_successful = False

        if self._needle_merit_before is not None:
            ok_gain, delta_abs, delta_rel, abs_thresh, rel_thresh = self._needle_gain_is_significant(
                self._needle_merit_before, rmse_after_cleanup
            )
            if ok_gain:
                self.log(
                    f"Needle cycle successful: DeltaRMSE={delta_abs:.6g} ({delta_rel * 100:.2f}%, "
                    f"thresholds abs>={abs_thresh:.6g} or rel>={rel_thresh * 100:.2f}%)",
                    "SUCCESS",
                )
                needle_successful = True
            else:
                self.log(
                    f"Needle cycle: gain too small (DeltaRMSE={delta_abs:.6g}, {delta_rel * 100:.2f}%)",
                    "WARNING",
                )
        else:
            self.log("Needle cycle: no improvement. Aborting needle.", "WARNING")
            self._revert_to_checkpoint()
            return True

        delattr(self, "_needle_cycle_step")
        delattr(self, "_needle_merit_before")

        current_count_after_clean = self.front_table.rowCount()
        last_count = getattr(self, "_last_cycle_layer_count", 0)
        if not hasattr(self, "_needle_stagnation_count"):
            self._needle_stagnation_count = 0

        if current_count_after_clean <= last_count and not needle_successful:
            self._needle_stagnation_count += 1
            self.log(
                f"[DESIGN.needle] stagnation detected | cycle_without_growth={self._needle_stagnation_count}/3 | target_layers={self._target_layer_count}",
                "WARNING",
            )
        else:
            self._needle_stagnation_count = 0

        self._last_cycle_layer_count = current_count_after_clean
        if self._needle_stagnation_count >= 3:
            self.log(
                "[DESIGN.needle] aborted due to stagnation | reason=3 cycles without growth or merit | action=revert_to_checkpoint",
                "ERROR",
            )
            delattr(self, "_needle_stagnation_count")
            if hasattr(self, "_last_cycle_layer_count"):
                delattr(self, "_last_cycle_layer_count")
            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = self._original_target_count
                self._overshoot_active = False
            self._revert_to_checkpoint()
            return True

        if current_count_after_clean < self._target_layer_count and current_count_after_clean < CFG.MAX_LAYERS:
            self.log(
                f"[DESIGN.needle] growth continuing | current_layers={current_count_after_clean} | target_layers={self._target_layer_count} | action=queue_next_cycle",
                "INFO",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            QTimer.singleShot(100, self._start_needle_process)
            return True

        if current_count_after_clean >= self._target_layer_count:
            if getattr(self, "_overshoot_active", False):
                original = self._original_target_count
                self.log(
                    f"Overshoot complete ({current_count_after_clean} layers). Pruning to {original}...",
                    "SUCCESS",
                )
                pruned = self._prune_to_target(original)
                self._overshoot_active = False
                self._overshoot_done = True
                self._target_layer_count = original
                current_rmse = d.get("rmse", float("inf"))
                checkpoint = getattr(self, "_pre_needle_checkpoint", None)
                if checkpoint and current_rmse > checkpoint["rmse"] * 1.02:
                    self.log(
                        f"Overshoot+Prune degraded RMSE ({current_rmse:.6f} > {checkpoint['rmse']:.6f}). Reverting.",
                        "WARNING",
                    )
                    self._revert_to_checkpoint()
                    return True
                if pruned > 0:
                    self.log(f"Pruned {pruned} thinnest layers. Final polish...", "INFO")
                    self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
                    self._post_prune = True
                    QTimer.singleShot(50, functools.partial(self.run_optim, "local", keep_history=True))
                    return True

            self.log(
                f"Deep Needle: Target reached ({self.front_table.rowCount()} layers)",
                "SUCCESS",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            return False

        self.log("Deep Needle: MAX_LAYERS reached", "WARNING")
        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")
        return False

    def _maybe_start_needle_growth(self) -> bool:
        """Start Needle growth/exploration when deficit or stagnation criteria are met."""
        current_count = self.front_table.rowCount()
        allow_growth = self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True
        has_deficit = current_count < self._target_layer_count
        stagnating = getattr(self, "_needle_no_improve_rounds", 0) >= getattr(self, "_needle_gate_no_improve_rounds", 2)
        needs_exploration = (
            allow_growth
            and stagnating
            and not getattr(self, "_overshoot_done", False)
            and not getattr(self, "_overshoot_active", False)
        )
        needs_needle = has_deficit or needs_exploration

        if not (needs_needle and current_count < CFG.MAX_LAYERS):
            return False

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]:
            return False

        if not getattr(self, "_overshoot_active", False) and not getattr(self, "_overshoot_done", False):
            import math

            self._original_target_count = self._target_layer_count
            if self._target_layer_count < CFG.MAX_LAYERS:
                ratio = getattr(self, "_needle_overshoot_ratio", 0.30)
                extra_layers = max(int(math.ceil(self._target_layer_count * ratio)), 4)
                overshoot = min(self._target_layer_count + extra_layers, CFG.MAX_LAYERS)
                self._target_layer_count = overshoot
                self._overshoot_active = True
                self.log(
                    f"Deep Needle Exploration: temporarily growing to {overshoot} layers "
                    f"(Target: {self._original_target_count}, +{extra_layers} extra for flexibility)",
                    "INFO",
                )

        self._pre_needle_checkpoint = {
            "ep": (self.ep_current.copy() if self.ep_current is not None else None),
            "rmse": self._workflow_best_rmse,
            "table": self._save_table_state(),
        }
        self.log(
            f"Checkpoint saved (RMSE={self._workflow_best_rmse:.6f}, {current_count} layers)",
            "INFO",
        )

        deficit = self._target_layer_count - current_count
        self.log(f"Layer deficit ({deficit}). Starting iterative Needle...", "INFO")
        self._start_needle_process()
        return True

    def _handle_decimation_polish_completion(self, d: Dict) -> bool:
        """Route decimation polish completion and bypass standard workflow."""
        if not getattr(self, "_decimation_polishing", False):
            return False

        if "ep" in d:
            self.ep_current = d["ep"].copy()
        rmse = d.get("rmse", getattr(self, "_workflow_best_rmse", float("inf")))
        if rmse < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse
        self._update_thickness_display()
        self._on_decimation_polish_done()
        return True

    def _handle_smart_decimation_followup(self, d: Dict) -> bool:
        """Advance smart decimation polish passes when enabled."""
        if not hasattr(self, "_smart_decimation_step"):
            return False

        polish_pass = getattr(self, "_smart_decimation_polish_pass", 0)
        if polish_pass == 1:
            self._smart_decimation_polish_pass = 2
            self.run_optim("local", keep_history=True)
            return True

        self._smart_decimation_polish_pass = 0
        self._on_smart_decimation_optim_done(d)
        return True

    def _is_in_needle_cycle(self) -> bool:
        """Return True when post-optim workflow is inside Needle cycle states."""
        return hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]

    def _run_post_optim_cleanup(self, d: Dict) -> int:
        """Apply post-prune/cleanup hook and return removed layer count."""
        if getattr(self, "_post_prune", False):
            self._post_prune = False
            self.log(f"Post-prune polish done. RMSE={d.get('rmse', '?')}", "INFO")
            return 0

        if not self._is_in_needle_cycle():
            return self.smart_cleanup(update_target=False)
        return 0

    def _handle_healing_workflow(self, removed: int) -> bool:
        """Drive two-phase healing after cleanup-induced topology changes."""
        if removed > 0 and not self._is_in_needle_cycle():
            self.log(
                f"Smart cleanup removed {removed} layers. Healing (restricted global)...",
                "INFO",
            )
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            self._healing_phase = "global"
            QTimer.singleShot(50, functools.partial(self.run_optim, "healing", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "global":
            self._healing_phase = "local"
            self.log("Healing: local polish...", "INFO")
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "local":
            self._healing_phase = None
        return False

    def _finalize_completed_optimization_workflow(self) -> None:
        """Finalize stable workflow state and trigger final evaluation/export."""
        self._apply_5nm_minimum()  # Hard rule: no layer < 5nm in final design

        # Set export flag BEFORE scheduling eval (eval callback checks this flag)
        if get_export_config():
            self._export_pending = True

        # Force final Pareto update with best RMSE
        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)
        self.log("Optimization complete & Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False

        # PARETO DECIMATION: iteratively remove thinnest layer, re-polish, record
        if not getattr(self, "_decimation_done", False) and self.front_table.rowCount() > 4:
            self._decimation_done = True
            QTimer.singleShot(200, self._start_smart_pareto_decimation)

    def _on_optim_done(self, d) -> None:
        return getattr(self, 'orchestrator', self)._on_optim_done(d)













    # =====================================================================

    # PARETO DECIMATION: remove thinnest -> merge -> re-polish -> record -> loop

    # =====================================================================


    def _initialize_smart_decimation_session(self, n_start: int, n_min_target: int) -> None:
        """Initialize and checkpoint Smart Pareto Decimation session state."""
        # Checkpoint the initial best solution to restore at end
        self._smart_deci_origin_ep = self.ep_current.copy()
        self._smart_deci_origin_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        self._smart_deci_origin_table = self._save_table_state()
        self._smart_deci_origin_N = n_start

        self._smart_decimation_start_N = n_start
        self._smart_decimation_min_N = n_min_target
        self._smart_decimation_best_rmse = self._smart_deci_origin_rmse

    def _smart_decimation_remove_and_optimize(self) -> None:
        """One step of smart decimation: remove thinnest layer and re-optimize."""

        current_N = self.front_table.rowCount()

        if self._should_stop_smart_decimation_step(current_N):
            return

        self._smart_decimation_step += 1

        ep = self.ep_current

        if ep is None or len(ep) != current_N:
            self._finish_smart_decimation()

            return

        # Apply 5nm manufacturability filter before recording
        # (layers already < 5nm counted as candidates to remove first)
        thinnest_idx = self._select_smart_decimation_remove_index(ep)

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        rmse_before = getattr(self, "_workflow_best_rmse", float("inf"))

        self.log(
            f"📉 Step {self._smart_decimation_step}: N={current_N}->{current_N - 1}"
            f" | remove layer {thinnest_idx} ({thinnest_mat}, {thinnest_d:.1f}nm)"
            f" | RMSE={rmse_before:.6f}",
            "INFO",
        )

        # Remove the selected layer

        self.front_table.removeRow(thinnest_idx)
        self._apply_smart_decimation_post_removal_state()

        self.run_optim("local", keep_history=True)

    def _apply_smart_decimation_post_removal_state(self) -> None:
        """Apply state updates required after removing one layer during decimation."""
        self._merge_adjacent_layers()
        self._update_layer_count()

        # Rebuild ep_current from table after removal + merge.
        self._update_thickness_display()

        # Reset best RMSE for the new N so local search is unconstrained by old N.
        self._workflow_best_rmse = float("inf")

        # Use double local polish: pass 1 explores, pass 2 tightens convergence.
        self._smart_decimation_polish_pass = 1

    def _should_stop_smart_decimation_step(self, current_n: int) -> bool:
        """Return True when smart decimation should stop at the current step."""
        # Stopping condition: reached N/2 target
        if current_n <= self._smart_decimation_min_N:
            self._finish_smart_decimation()
            return True

        if self._smart_decimation_step >= 50:  # Safety limit
            self.log("Smart decimation: safety limit reached", "WARNING")
            self._finish_smart_decimation()
            return True

        return False

    def _select_smart_decimation_remove_index(self, ep: np.ndarray) -> int:
        """Pick layer index to remove, prioritizing sub-5nm layers."""
        sub5nm = [i for i, d in enumerate(ep) if d < 5.0]
        if sub5nm:
            # Prefer removing a sub-5nm layer over the generic thinnest
            return sub5nm[int(np.argmin([ep[i] for i in sub5nm]))]
        return int(np.argmin(ep))

    def _on_smart_decimation_optim_done(self, data) -> None:
        """Called after local optimization during smart decimation."""

        if not data or "rmse" not in data:
            self.log("Smart decimation: optimization failed", "ERROR")

            self._finish_smart_decimation()

            return

        rmse_after = data["rmse"]

        current_N = self.front_table.rowCount()

        ref_rmse = self._smart_deci_origin_rmse

        self._apply_smart_decimation_optim_result(data, rmse_after)

        # DEGRADATION GUARD: stop if RMSE > 2× initial reference
        if self._abort_on_smart_decimation_degradation(rmse_after, ref_rmse):
            return

        self._record_smart_decimation_candidate(current_N, rmse_after)

        # Continue to next step

        QTimer.singleShot(200, self._smart_decimation_remove_and_optimize)

    def _apply_smart_decimation_optim_result(self, data: Dict[str, Any], rmse_after: float) -> None:
        """Apply optimization payload and refresh best-RMSE tracking."""
        if "ep" in data:
            self.ep_current = data["ep"].copy()
            self._update_thickness_display()

        if rmse_after < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_after

    def _record_smart_decimation_candidate(self, current_n: int, rmse_after: float) -> None:
        """Record current design into Pareto and emit step log."""
        ep = self.ep_current
        has_sub5nm = (ep is not None) and np.any(ep < 5.0)

        # _update_pareto_record already enforces strictly-better updates.
        self._update_pareto_record(self.ep_current, rmse_after)
        self._log_smart_decimation_step_result(current_n, rmse_after, has_sub5nm)

    def _abort_on_smart_decimation_degradation(self, rmse_after: float, ref_rmse: float) -> bool:
        """Abort decimation when RMSE degrades beyond configured safety factor."""
        degradation_limit = 2.0
        if rmse_after <= ref_rmse * degradation_limit:
            return False

        self.log(
            f"   🛑 RMSE {rmse_after:.6f} > {degradation_limit}× ref ({ref_rmse:.6f}) - stopping decimation",
            "WARNING",
        )
        self._finish_smart_decimation()
        return True

    def _log_smart_decimation_step_result(
        self,
        current_n: int,
        rmse_after: float,
        has_sub5nm: bool,
    ) -> None:
        """Log per-step Smart Decimation outcome against current Pareto champion."""
        n_record = self.pareto_history.get(current_n, {})
        best_rmse_for_n = n_record.get("best_rmse", float("inf"))
        flag = " [sub5nm]" if has_sub5nm else ""

        if abs(rmse_after - best_rmse_for_n) < 1e-6:
            # This IS the new champion (we just set it)
            self.log(f"   ✅ N={current_n}: {rmse_after:.6f}{flag}", "SUCCESS")
            return

        self.log(
            f"   - N={current_n}: {rmse_after:.6f} (best={best_rmse_for_n:.6f}){flag}",
            "INFO",
        )

    def _restore_smart_decimation_origin(self, start_n: int) -> None:
        """Restore the checkpointed pre-decimation design when available."""
        origin_ep = getattr(self, "_smart_deci_origin_ep", None)
        origin_rmse = getattr(self, "_smart_deci_origin_rmse", float("inf"))
        origin_table = getattr(self, "_smart_deci_origin_table", None)

        if origin_ep is None or origin_table is None:
            return

        self._restore_table_state(origin_table)
        self.ep_current = origin_ep.copy()
        self._update_thickness_display()
        self._workflow_best_rmse = origin_rmse
        self._use_exact_ep = True
        self.log(
            f"↩️  Reverted to original best solution ({start_n} layers, RMSE={origin_rmse:.6f})",
            "INFO",
        )

    def _clear_smart_decimation_state(self) -> None:
        """Delete transient Smart Decimation runtime attributes."""
        attrs = (
            "_smart_decimation_start_N",
            "_smart_decimation_min_N",
            "_smart_decimation_current_N",
            "_smart_decimation_best_rmse",
            "_smart_decimation_step",
            "_smart_deci_origin_ep",
            "_smart_deci_origin_rmse",
            "_smart_deci_origin_table",
            "_smart_deci_origin_N",
            "_smart_decimation_polish_pass",
            "_smart_decimation_healing",
        )
        for attr in attrs:
            if hasattr(self, attr):
                delattr(self, attr)

    def _log_smart_decimation_completion(self, total_steps: int, start_n: int, end_n: int) -> None:
        """Log Smart Pareto Decimation completion summary."""
        pareto_count = len(self.pareto_history)
        self.log(
            f"🎯 Smart Pareto Decimation complete:"
            f" {total_steps} steps | {start_n}->{end_n} layers | {pareto_count} Pareto records",
            "SUCCESS",
        )

    def _finish_smart_decimation(self) -> None:
        """Clean up after smart decimation and REVERT to original best solution."""

        total_steps = getattr(self, "_smart_decimation_step", 0)

        start_N = getattr(self, "_smart_decimation_start_N", 0)

        # --- REVERT to original best solution ---
        self._restore_smart_decimation_origin(start_N)

        end_N = self.front_table.rowCount()
        self._log_smart_decimation_completion(total_steps, start_N, end_N)

        self._set_busy(False)

        # Cleanup decimation state
        self._clear_smart_decimation_state()

        self._finalize_smart_decimation_post_actions()

    def _finalize_smart_decimation_post_actions(self) -> None:
        """Run final UI/eval/export actions after decimation cleanup."""
        # Enforce hard 5nm rule on the final returned design in the UI
        self._apply_5nm_minimum()

        # Final eval with restored design
        self._schedule_eval(True)

        # Generate grouped Pareto report if auto-export enabled
        if get_export_config() and len(self.pareto_history) > 1:
            QTimer.singleShot(500, self._export_pareto_report)


    def _decimation_remove_and_polish(self) -> None:
        """One step of decimation: remove thinnest, merge, then local polish."""

        N = self.front_table.rowCount()

        ep = self.ep_current

        if N <= 4 or ep is None or len(ep) != N:
            self._finish_pareto_decimation()

            return

        # Find thinnest layer index

        thinnest_idx = int(np.argmin(ep))

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        self.log(
            f"▼ Decimation step {self._decimation_step + 1}: removing layer #{thinnest_idx + 1} "
            f"({thinnest_mat}, {thinnest_d:.2f} nm) from {N}-layer design",
            "INFO",
        )

        # Remove thinnest layer

        self.front_table.removeRow(thinnest_idx)

        self._merge_adjacent_layers()

        self._update_layer_count()

        new_N = self.front_table.rowCount()

        self._target_layer_count = new_N

        # Rebuild ep_current from remaining rows

        self._update_thickness_display()

        self._decimation_step += 1

        # Run a local polish to re-optimize

        self._decimation_polishing = True

        QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))

    def _on_decimation_polish_done(self) -> None:
        """Called after local polish during decimation to evaluate and continue."""

        N = self.front_table.rowCount()

        current_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        # Record in Pareto with current best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self.log(
            f"▼ Decimation: {N} layers -> RMSE={current_rmse:.5f} (ref={self._decimation_ref_rmse:.5f})",
            "INFO",
        )

        # Stop conditions:

        # 1. RMSE too degraded (3× reference)

        # 2. Too few layers

        # 3. Max 20 decimation steps (safety)

        if current_rmse > self._decimation_ref_rmse * 3.0 or N <= 4 or self._decimation_step >= 20:
            self._finish_pareto_decimation()

            return

        # Continue decimating

        QTimer.singleShot(100, self._decimation_remove_and_polish)


    @safe_ui_action
    def _drop_thinnest_and_polish(self) -> None:
        """GUI action: remove thinnest layer, merge if interior, local polish.

        Now identical to remove_thinnest for consistency.

        """

        self.remove_thinnest()

    # =========================================================================

    # HARD 5nm MINIMUM LAYER THICKNESS RULE

    # =========================================================================

    def _apply_5nm_minimum(self) -> None:
        """Enforce hard minimum layer thickness of 5nm on the current design.

        Removes all layers < 5nm, merges adjacent identical materials,

        and logs any changes. Called at every workflow exit point.

        This rule takes priority over all other optimisation considerations.

        """

        ep = self.ep_current

        if ep is None or len(ep) == 0:
            return

        MIN_FINAL_THICKNESS = 5.0  # nm - hard manufacturing limit

        thin_layers = [r for r, d in enumerate(ep) if d < MIN_FINAL_THICKNESS]

        if not thin_layers:
            return  # Nothing to do

        self.log(
            f"[5nm rule] Removing {len(thin_layers)} layers < {MIN_FINAL_THICKNESS}nm before finalisation",
            "WARNING",
        )

        # Remove in reverse order to keep clues valid

        for r in sorted(thin_layers, reverse=True):
            self.front_table.removeRow(r)

        self._merge_adjacent_layers()

        self._update_layer_count()

        self._update_thickness_display()

        # Update target layer count to new reality

        self._target_layer_count = self.front_table.rowCount()

        self.log(
            f"[5nm rule] Final design: {self._target_layer_count} layers, "
            f"d_min = {float(np.min(self.ep_current)):.2f}nm",
            "INFO",
        )

        # Record the clean manufacturable design in Pareto history

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _save_table_state(self) -> list:
        """Save front_table state (material + QWOT + var) for checkpoint."""

        state = []

        for r in range(self.front_table.rowCount()):
            mat = self._safe_get_combo_text(r, 0)

            qw = self.front_table.cellWidget(r, 1).value() if self.front_table.cellWidget(r, 1) else 1.0

            var = True

            cw = self.front_table.cellWidget(r, 3)

            if cw:
                cb = cw.findChild(QCheckBox)

                if cb:
                    var = cb.isChecked()

            del_checked = False

            del_cw = self.front_table.cellWidget(r, 4)

            if del_cw:
                del_cb = del_cw.findChild(QCheckBox)

                if del_cb:
                    del_checked = del_cb.isChecked()

            state.append({"mat": mat, "qw": qw, "var": var, "del": del_checked})

        return state

    def _restore_table_state(self, state: list) -> None:
        """Restore front_table from saved state (without recalculationating thicknesses)."""

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for item in state:
            self._add_front_row(item["mat"], item["qw"], item["var"], item.get("del", False))

        self.front_table.blockSignals(False)

        self._update_layer_count()

    def _revert_to_checkpoint(self) -> None:
        """Revert to pre-needle checkpoint if needle degraded the solution."""

        checkpoint = getattr(self, "_pre_needle_checkpoint", None)

        if not checkpoint:
            self.log("No checkpoint to revert to.", "WARNING")

            self._set_busy(False)

            return

        self.log(
            f"Reverting to checkpoint (RMSE={checkpoint['rmse']:.6f}, {len(checkpoint['table'])} layers)",
            "WARNING",
        )

        self._restore_table_state(checkpoint["table"])

        self._workflow_best_rmse = checkpoint["rmse"]

        # Clean all needle/overshoot state

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
            "_pre_needle_checkpoint",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._overshoot_done = True

        # Restore exact thicknesses: set QWOT from ep, then update display

        if checkpoint["ep"] is not None:
            self._update_qwot_from_ep(checkpoint["ep"])

            self._update_thickness_display()

            self.ep_current = checkpoint["ep"].copy()

            self._use_exact_ep = True

        self._apply_5nm_minimum()  # Hard rule before closing

        if get_export_config():
            self._export_pending = True  # Set BEFORE schedule_eval

        # Force final Pareto update with best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)

        self.log("Optimization complete (reverted to best). Structure stable.", "SUCCESS")

        self._set_busy(False)

        self._is_internal_restart = False

        if get_export_config():
            self._export_pending = True

    def smart_cleanup(self, update_target: bool = True) -> int:
        """

        Smart cleanup: merges identical adjacent materials and removes

        very thin layers (< 1.0 nm) which are likely artifacts.

        Parameters

        ----------

        update_target : bool, optional

            If True, updates self._target_layer_count to match new count.

            Set to False during Deep Needle loop to maintain high target.

        Returns

        -------

        int

            Number of layers removed

        """

        removed_count = 0

        changed = False

        # Step 1: Remove very thin layers dynamically based on RMSE

        # Smart threshold: When RMSE is very low (sharp design), remove only incredibly thin layers to preserve delicate structures.

        current_rmse = getattr(self, "_workflow_best_rmse", 1.0)

        multiplier = getattr(self, "_cleanup_threshold_multiplier", 150.0)

        threshold = max(0.05, min(1.0, current_rmse * multiplier))  # Adaptive threshold

        rows_to_remove = []

        ep_current = self.ep_current if self.ep_current is not None else []

        if len(ep_current) == self.front_table.rowCount():
            for r in range(len(ep_current) - 1, -1, -1):
                if ep_current[r] < threshold:
                    rows_to_remove.append(r)

        if rows_to_remove:
            self.log(f"Smart cleanup: removing {len(rows_to_remove)} layers < {threshold:.2f} nm (adaptive)", "INFO")

            for r in rows_to_remove:
                self.front_table.removeRow(r)

            removed_count += len(rows_to_remove)

            changed = True

        # Step 2: Merge identical adjacent materials

        # (uses _merge_adjacent_layers which already does this)

        pre_merge_count = self.front_table.rowCount()

        self._merge_adjacent_layers()

        post_merge_count = self.front_table.rowCount()

        merge_diff = pre_merge_count - post_merge_count

        if merge_diff > 0:
            removed_count += merge_diff

            changed = True

            self.log(f"Smart cleanup: merged {merge_diff} adjacent layers", "INFO")

        if changed:
            self._update_layer_count()

            self._update_thickness_display()

            if update_target:
                self._target_layer_count = self.front_table.rowCount()

        return removed_count

    def _prune_to_target(self, target_count: int) -> int:
        """

        Overshoot & Prune: remove thinnest layers to reach target count.

        After growing beyond the target via Needle, prune back by removing

        the thinnest layers first (they contribute least to the design).

        Removes ONE layer at a time, then merges adjacent identical materials

        and re-checks count. This is necessary because in H/L stacks,

        removing one layer makes its neighbours adjacent -> merge -> net -2.

        This method performs layer pruning including:

        - Identification of thinnest layers

        - Sequential layer removal

        - Adjacent material merging

        - Count verification and adjustment

        Args:

            self: CertusDesign instance

            target_count: Desired number of layers after pruning

        Returns:

            int: Total number of layers removed (including merges)

        Notes:

            - Used in Needle algorithm workflow

            - Handles H/L stack merging automatically

            - Updates UI components after pruning

            - Logs pruning operations

        """

        initial_count = self.front_table.rowCount()

        if initial_count <= target_count:
            return 0

        total_removed = 0

        while self.front_table.rowCount() > target_count:
            current_count = self.front_table.rowCount()

            ep = self.ep_current if self.ep_current is not None else np.array([])

            if len(ep) != current_count:
                self._update_thickness_display()

                ep = self.ep_current if self.ep_current is not None else np.array([])

                if len(ep) != current_count:
                    self.log("Prune: ep_current mismatch, stopping.", "WARNING")

                    break

            # Find the thinnest layer

            thinnest_idx = int(np.argmin(ep))

            self.log(f"  Prune: layer {thinnest_idx} ({ep[thinnest_idx]:.2f} nm)", "INFO")

            self.front_table.blockSignals(True)

            self.front_table.removeRow(thinnest_idx)

            self.front_table.blockSignals(False)

            # Merge adjacent identical materials (may remove additional layers)

            pre_merge = self.front_table.rowCount()

            self._merge_adjacent_layers()

            post_merge = self.front_table.rowCount()

            step_removed = 1 + (pre_merge - post_merge)

            total_removed += step_removed

            self._update_layer_count()

            self._update_thickness_display()

        final_count = self.front_table.rowCount()

        self.log(
            f"Overshoot & Prune: {initial_count} -> {final_count} layers "
            f"(removed {total_removed}, target was {target_count})",
            "SUCCESS",
        )

        return total_removed

    def stop_optim(self) -> None:
        """Stop the current optimization and clean all workflow state.

        Terminates any running OptimWorker or NeedleWorker, then resets

        all internal state variables (overshoot, healing phase, needle

        cycle) to prevent stale state from interfering with subsequent

        optimizations.

        Sets _workflow_stopped flag to prevent pending QTimer callbacks

        from restarting the workflow after this method returns.

        """

        if not confirm_stop_with_timeout(self):
            return

        # CRITICAL: Set flag FIRST to block pending QTimer callbacks

        self._workflow_stopped = True

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped by user")

        self.log("Stopping optimization...", "WARNING")

        try:
            if self.optim_thread and self.optim_thread.isRunning():
                if self.optim_worker:
                    self.optim_worker.request_stop()
                self.optim_thread.quit()
        except RuntimeError:
            pass

        try:
            if self.needle_thread and self.needle_thread.isRunning():
                self.needle_thread.requestInterruption()
        except RuntimeError:
            pass

        self._force_idle()

        self._clean_live_curves()

        self._is_internal_restart = False

        # Clean ALL workflow state on user stop

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        self.log("Optimization stopped.", "WARNING")

        # If stale callbacks arrive later, they can still call _set_busy(False) safely.

        # We force UI idle here to avoid sticky "Computing..." state.

        self._force_idle()

    def on_stats_update(self, type_str: str, count: int) -> None:
        """Updates statistics"""

        if type_str == "EVAL":
            self.stat_counters["EVAL"] = count

        elif type_str == "MINIMA":
            self.stat_counters["MINIMA"] = count

        self.update_stats_display()

    def update_stats_display(self) -> None:
        """Optimization counters: minimum, evaluations, best score (rainbow icon)."""

        minima_count = self.stat_counters.get("MINIMA", 0)

        eval_count = self.stat_counters.get("EVAL", 0)

        best_count = self.stat_counters.get("BEST", 0)

        text = f"♟️ {minima_count} minima  | 🎲 {eval_count} evals  | 🌈️ {best_count}"

        self.stats_label.setText(text)

    def _needle_thresholds(self, rmse_ref: float) -> tuple:
        """Adaptive thresholds for needle merit checks."""

        if rmse_ref is None or not np.isfinite(rmse_ref) or rmse_ref <= 0.0:
            return self._needle_success_rel_threshold, self._needle_success_abs_floor

        rel_thresh = 0.002 if rmse_ref < 0.01 else self._needle_success_rel_threshold

        abs_thresh = max(self._needle_success_abs_floor, rmse_ref * 5e-4)

        return rel_thresh, abs_thresh

    def _needle_gain_is_significant(self, rmse_before: float, rmse_after: float) -> tuple:
        """Return whether RMSE gain is meaningful for topology growth."""

        if (
            rmse_before is None
            or rmse_after is None
            or not np.isfinite(rmse_before)
            or not np.isfinite(rmse_after)
            or rmse_before <= 0.0
            or rmse_after >= rmse_before
        ):
            return False, 0.0, 0.0, 0.0, 0.0

        delta_abs = rmse_before - rmse_after

        delta_rel = delta_abs / max(rmse_before, 1e-12)

        rel_thresh, abs_thresh = self._needle_thresholds(rmse_before)

        ok = (delta_abs >= abs_thresh) or (delta_rel >= rel_thresh)

        return ok, delta_abs, delta_rel, abs_thresh, rel_thresh

    # =========================================================================

    # NEEDLE ALGORITHM

    # =========================================================================

    def _start_needle_process(self, ) -> None:
        return getattr(self, 'orchestrator', self)._start_needle_process()

    def _on_needle_found(self, res) -> None:
        return getattr(self, 'orchestrator', self)._on_needle_found(res)

    def _handle_needle_no_candidate(self, action, res) -> Any:
        return getattr(self, 'orchestrator', self)._handle_needle_no_candidate(action, res)

    def _handle_needle_no_candidate_below_target(self, action, res, current_count) -> tuple:
        return getattr(self, 'orchestrator', self)._handle_needle_no_candidate_below_target(action, res, current_count)

    def _abort_needle_after_failed_retries(self, ) -> None:
        return getattr(self, 'orchestrator', self)._abort_needle_after_failed_retries()

    def _maybe_prune_needle_overshoot(self, current_count) -> bool:
        return getattr(self, 'orchestrator', self)._maybe_prune_needle_overshoot(current_count)

    def _apply_needle_split_insertion(self, res) -> bool:
        return getattr(self, 'orchestrator', self)._apply_needle_split_insertion(res)

    def _insert_needle_split_row(self, idx, mat_needle, n_needle, l0) -> float:
        return getattr(self, 'orchestrator', self)._insert_needle_split_row(idx, mat_needle, n_needle, l0)

    def _insert_right_split_row(self, idx, mat_orig, qw_right, d_right) -> None:
        return getattr(self, 'orchestrator', self)._insert_right_split_row(idx, mat_orig, qw_right, d_right)

    def _clear_needle_cycle_state(self, ) -> None:
        return getattr(self, 'orchestrator', self)._clear_needle_cycle_state()

    def _clear_needle_search_state(self, keep_fail_count) -> None:
        return getattr(self, 'orchestrator', self)._clear_needle_search_state(keep_fail_count)

    # =========================================================================

    # COLORIMETRY

    # =========================================================================

    @safe_ui_action
    def run_colorimetry(self) -> None:
        """

        Start colorimetric analysis of the current design.

        This method performs color analysis including:

        - Color coordinate calculationation (CIE XYZ, LAB)

        - Monte Carlo simulation for color variation

        - Visualization of color properties

        - Analysis of color stability under thickness variations

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires previous evaluation results

            - Switches to color plot view

            - Uses Monte Carlo simulation for robustness

            - Emits progress updates during analysis

        """

        if not self.last_result:
            self.log("Please evaluate first.", "WARNING")

            return

        if self.viz_stack.currentIndex() == 0:
            self.viz_stack.setCurrentIndex(1)

        self.plot_tabs.setCurrentWidget(self.color_plot)

        self.log("Running colorimetric analysis...", "INFO")

        mats = self._get_materials()

        stack = self._get_front_stack()

        cfg = {
            "ep": self.last_result["ep"],
            "stack": stack,
            "mats": mats,
            "n": self.mc_n_spin.value(),
            "sigma": self.mc_sigma_spin.value(),
            "l0": self.l0_spin.value(),
        }

        self._set_busy(True)

        self.col_worker = ColorWorker(cfg)

        self.col_thread = QThread()
        self.col_worker.moveToThread(self.col_thread)

        self.col_thread.started.connect(self.col_worker.run)

        self.col_worker.signals.finished.connect(self.col_thread.quit)
        self.col_worker.signals.finished.connect(self._on_col_done)
        self.col_worker.signals.finished.connect(self.col_worker.deleteLater)

        self.col_worker.signals.error.connect(self.col_thread.quit)
        self.col_worker.signals.error.connect(self._on_error)
        self.col_worker.signals.error.connect(self.col_worker.deleteLater)

        self.col_thread.finished.connect(self.col_thread.deleteLater)

        self.col_thread.start()

    def _on_col_done(self, d: Dict) -> None:
        """Callback after colorimetric analysis"""

        if d["ok"]:
            nom = d["lab_nom"]

            labs = d["labs"]

            self.color_plot.plotItem.clear()

            plot_widget_plot_finite(
                self.color_plot,
                labs[:, 1],
                labs[:, 2],
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=(180, 180, 180, 100),
                animate=False,
            )

            plot_widget_plot_finite(
                self.color_plot,
                [nom[1]],
                [nom[2]],
                pen=None,
                symbol="star",
                symbolSize=18,
                symbolBrush=CertusTheme.ERROR,
                symbolPen="k",
                animate=False,
            )

            de = [delta_e_2000(nom, l) for l in labs]

            rgb = lab_to_rgb(nom)

            title = (
                f"L*={nom[0]:.1f} a*={nom[1]:.1f} b*={nom[2]:.1f} | "
                f"RGB({rgb[0]},{rgb[1]},{rgb[2]}) | "
                f"DeltaE*00:  μ={np.mean(de):.2f} sigma={np.std(de):.2f}"
            )

            self.color_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="10pt")

            self.log("[DESIGN.colorimetry] analysis complete | status=success", "SUCCESS")

        self._set_busy(False)

    # =========================================================================

    # SELF-EXPORT (Excel + HTML)

    # =========================================================================

    @safe_ui_action
    def export_results(self) -> None:

        self.log("[DESIGN.export_results] entered export flow", "DEBUG")

        """Self-exports results to reports folder (Excel + HTML).

        This method generates comprehensive reports including:

        - Excel spreadsheet with design parameters and results

        - HTML report with visualization and analysis

        - Timestamped filenames with RMSE values

        - Automatic folder creation and organization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires last_result to be available

            - Creates reports folder if needed

            - Generates both Excel and HTML formats

            - Includes RMSE value in filename"""

        if not self.last_result:
            self.log("[DESIGN.export_results] export skipped: no results available", "WARNING")

            return

        try:
            self._sync_export_result_with_best_eval()

            rmse_val, base_name, excel_path, html_path = self._prepare_export_paths()

            self.log("[DESIGN.export_results] saving reports (Excel + HTML)", "INFO")

            manifest_dict = self._build_export_manifest()

            if not self._is_export_manifest_complete(manifest_dict):
                return

            # 1. EXCEL EXPORT

            self._export_results_excel(manifest_dict, rmse_val, excel_path)

            # 2.HTML EXPORT
            self._export_results_html(manifest_dict, rmse_val, html_path)

            self.status_label.setText(f"✓ Saved: {base_name}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("Export error: %s", e, exc_info=True)

    def _export_results_excel(self, manifest_dict: dict[str, Any], rmse_val: float, excel_path: str) -> None:
        """Write the Excel report workbook when openpyxl is available."""

        if not OPENPYXL_AVAILABLE:
            self.log("[DESIGN._export_results_excel] Excel export skipped: openpyxl not available", "WARNING")

            return

        import openpyxl

        wb = openpyxl.Workbook()

        ws = wb.active

        ws.title = "Summary"

        ws.append(["CERTUS-DESIGN Report"])

        ws.append([f"Generated: {certus_timestamp_display()}"])

        ws.append([f"Best RMSE: {rmse_val:.6f}"])

        t_exec = f"{self.last_result.get('execution_time', 0):.2f}" if "execution_time" in self.last_result else "N/A"

        ws.append([f"Execution Time: {t_exec} s"])

        ws.append([f"Global Cycles: {self.global_cycles_spin.value()}"])

        ws.append([f"Population: {self.max_clusters_spin.value()}"])

        ws.append([])

        ws.append(["STACK CONFIGURATION"])

        ws.append(["#", "Material", "QWOT", "Thickness (nm)", "Variable"])

        ep = self.ep_current if self.ep_current is not None else []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0

            ws.append([i + 1, layer.mat, layer.qwot, f"{d:.2f}", "Yes" if layer.var else "No"])

        if len(ep) > 0:
            ws.append([])

            ws.append(["Total Thickness (nm)", f"{np.sum(ep):.2f}"])

        if "vis" in self.last_result:
            ws2 = wb.create_sheet("Spectrum")

            ws2.append(["Wavelength (nm)", "Transmission"])

            vis = self.last_result["vis"]

            for i in range(len(vis["l"])):
                ws2.append([vis["l"][i], vis["Ts"][i]])

        ws_m = wb.create_sheet("Manifest")

        ws_m.append(["Key", "Value"])

        for k, v in manifest_dict.items():
            ws_m.append([str(k), str(v)])

        wb.save(excel_path)

        self.log(f"Excel saved: {Path(excel_path).name}", "SUCCESS")

    def _export_results_html(self, manifest_dict: dict[str, Any], rmse_val: float, html_path: str) -> None:
        """Write the HTML report for design optimization results."""

        ep = self.ep_current if self.ep_current is not None else []

        stack_data = []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0.0

            stack_data.append(
                {
                    "#": i + 1,
                    "Material": layer.mat,
                    "Thickness (nm)": f"{d:.2f}",
                    "QWOT": f"{layer.qwot:.3f}",
                    "Optimized": "Yes" if layer.var else "No",
                }
            )

        sections = [
            {
                "title": "Design Optimization Summary",
                "type": "kv",
                "content": {
                    "Best RMSE": f"{rmse_val:.5f}",
                    "Total Layers": str(self.front_table.rowCount()),
                    "Total Thickness": (f"{np.sum(ep):.2f} nm" if len(ep) > 0 else "N/A"),
                    "Reference L0": f"{self.l0_spin.value()} nm",
                    "Targets Count": str(len(self._get_tgts())),
                    "Global Cycles": str(self.global_cycles_spin.value()),
                    "Cluster Pop": str(self.max_clusters_spin.value()),
                    "Execution Time": (
                        f"{self.last_result.get('execution_time', 0):.2f} s"
                        if "execution_time" in self.last_result
                        else "N/A"
                    ),
                },
            },
            {"title": "Layer Structure", "type": "table", "content": stack_data},
            {
                "title": "Run Manifest",
                "type": "table",
                "headers": ["Key", "Value"],
                "rows": [[str(k), str(v)] for k, v in manifest_dict.items()],
            },
        ]

        methodology_sections = [
            {
                "title": "Optimization Methodology",
                "type": "kv",
                "content": {
                    "Topology Search": "Needle Algorithm (Automatic Layer Insertion)",
                    "Global Search": "PGlobal (Stochastic Differential Evolution)",
                    "Local Refinement": "L-BFGS-B (Analytic Gradient)",
                    "Gradient Mode": "Analytic (Exact Derivatives)",
                    "Convergence": "High (Gradient-Assisted)",
                },
            },
            {
                "title": "Algorithm Details",
                "type": "text",
                "content": (
                    "The design process uses the <strong>Needle Algorithm</strong> to automatically find the optimal layer structure "
                    "by inserting infinitely thin layers at positions of maximum gradient sensitivity. This is coupled with a "
                    "<strong>Global/Local Hybrid Optimization</strong> strategy to refine thicknesses. The local refinement uses "
                    "<strong>Analytic Gradients</strong> to compute exact derivatives of the Tauc-Lorentz-Urbach model and "
                    "Transfer Matrix Method interactions, providing high-precision convergence without numerical noise."
                ),
            },
        ]

        all_sections = methodology_sections + sections

        figures = [self.spectrum_plot, self.profile_plot]

        if generate_html_report(html_path, "CERTUS-DESIGN Report", all_sections, figures):
            self.log(f"HTML saved: {Path(html_path).name}", "SUCCESS")

    def _build_export_manifest(self) -> dict[str, Any]:
        """Build a run manifest for report export."""

        manifest_dict: dict[str, Any] = {}

        try:
            status_txt = str(getattr(self, "validation_status", "OK") or "OK")

            try:
                status_val = ValidationStatus(status_txt)

            except ValueError:
                status_val = ValidationStatus.OK

            seed_val = None

            for _seed_candidate in (
                getattr(self, "run_seed", None),
                getattr(self, "random_seed", None),
                getattr(self, "_loaded_config", {}).get("seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
                getattr(self, "_loaded_config", {}).get("random_seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
            ):
                if _seed_candidate is None:
                    continue

                try:
                    seed_val = int(_seed_candidate)

                    break

                except (TypeError, ValueError):
                    continue

            svc = IndexFitService(runner=lambda _cfg: self.last_result or {})

            req = IndexFitRequest(
                config={
                    "module": "CERTUS_DESIGN",
                    "export_kind": "full_results",
                    "l0_nm": float(self.l0_spin.value()),
                    "layers_count": int(self.front_table.rowCount()),
                },
                source_paths=[
                    p
                    for p in (
                        str(getattr(self, "filename", "") or "").strip(),
                        str(getattr(self, "_last_config_file", "") or "").strip(),
                    )
                    if p
                ],
                seed=seed_val,
                app_id="CERTUS_DESIGN",
                app_version=__version__,
                warnings=list(getattr(self, "validation_warnings", []) or []),
                status=status_val,
            )

            manifest_dict = svc.fit(req).manifest.to_dict()

        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            self.log(f"Manifest generation failed: {exc}", "WARNING")

            manifest_dict = {}

        return manifest_dict

    def _is_export_manifest_complete(self, manifest_dict: dict[str, Any]) -> bool:
        """Validate mandatory manifest fields before writing reports."""

        from certus.utils.certus_data import get_missing_manifest_fields

        missing_manifest_fields = get_missing_manifest_fields(manifest_dict)

        if not missing_manifest_fields:
            return True

        self.log(
            "Export blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
            "ERROR",
        )

        return False

    def _sync_export_result_with_best_eval(self) -> None:
        """Keep export payload aligned with the best evaluation spectrum and thickness table."""

        curr_rmse = self.last_result.get("rmse")

        curr_rmse_valid = self._is_valid_rmse_value(curr_rmse)

        if not (
            self._best_eval_result is not None
            and self._is_valid_rmse_value(self._best_eval_rmse)
            and (not curr_rmse_valid or self._best_eval_rmse <= curr_rmse + 1e-12)
        ):
            return

        self.last_result = copy.deepcopy(self._best_eval_result)

        try:
            ep_best = np.asarray(self.last_result.get("ep", []), dtype=float).flatten()

            if ep_best.size > 0:
                self._update_qwot_from_ep(ep_best)

                self._update_thickness_display()

                self.ep_current = ep_best.copy()

                self._use_exact_ep = True

        except NUMERICAL_FAULT_EXCEPTIONS as _e_export_sync:
            logging.debug(f"[EXPORT] Best spectrum/table sync skipped:{_e_export_sync}")

    def _prepare_export_paths(self) -> tuple[float, str, str, str]:
        """Prepare export paths and base metadata for report generation."""

        reports_dir = get_resource_path("reports")

        os.makedirs(reports_dir, exist_ok=True)

        rmse_val = getattr(self, "_workflow_best_rmse", None)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = self.last_result.get("rmse", 0.0)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = float("inf")

        ts = certus_timestamp_file()

        try:
            src_name = ""

            if hasattr(self, "_last_config_file") and self._last_config_file:
                src_name = "_" + Path(self._last_config_file).stem

            base_name = f"Report_DESIGN{src_name}_{ts}_RMSE_{rmse_val:.5f}"

        except NUMERICAL_FAULT_EXCEPTIONS:
            base_name = f"Report_DESIGN_{ts}_RMSE_{rmse_val:.5f}"

        excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")

        html_path = str(Path(reports_dir) / f"{base_name}.html")

        return rmse_val, base_name, excel_path, html_path

    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # --- Lot C helpers ---

    def _pre_save_smart_cleanup(self) -> None:
        """Run the pre-save cleanup + heal step (idempotent)."""

        if self.front_table.rowCount() > 0:
            self.log("Final cleanup before save...", "INFO")

            removed = self.smart_cleanup()

            if removed > 0:
                self.log(
                    f"Final cleanup: removed {removed} layers. Optimizing...",
                    "INFO",
                )

                # Run fast local optimization to heal

                self._is_internal_restart = True

                # Note: Cannot wait for optimization here (async)

                self._schedule_eval(True)  # Update display

    def _post_save_config(self, filename: str) -> None:
        """UX feedback after a successful save."""

        self.log(f"Configuration saved:  {filename}", "SUCCESS")

        show_toast(self, f"Saved: {Path(filename).name}", "success")

    def _collect_config(self) -> dict:
        """Build the JSON-serialisable config dict from current UI state."""

        self._pre_save_smart_cleanup()

        cfg = {
            "version": APP_SUITE_VERSION,
            "l0": self.l0_spin.value(),
            "materials": {
                n: {
                    "n4": w["n4"].value(),
                    "n7": w["n7"].value(),
                    "preset": w["preset"].currentText(),
                }
                for n, w in self.mat_widgets.items()
            },
            "front": [{"mat": l.mat, "qw": l.qwot, "var": l.var} for l in self._get_front_stack()],
            "back_en": self.back_check.isChecked(),
            "back_coat": self.back_coat_check.isChecked(),
            "back": [{"mat": l.mat, "qw": l.qwot} for l in self._get_back_stack()],
            "targets": (
                [
                    {
                        "on": t.on,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "tmin": t.tmin,
                        "tmax": t.tmax,
                        "w": t.w,
                    }
                    for t in self._get_tgts()
                ]
                if not self.oblique_mode
                else [
                    {
                        "active": t.on,
                        "angle": t.angle,
                        "polarization": t.pol,
                        "target_type": t.target_type,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "val_min": t.tmin,
                        "val_max": t.tmax,
                        "weight": t.w,
                    }
                    for t in self._get_oblique_tgts()
                ]
            ),
            "oblique_mode": self.oblique_mode,
            "optimization": {
                "points_per_target": self.points_per_target_spin.value(),
                "n100": self.n100_spin.value(),
                "max_clusters": self.max_clusters_spin.value(),
                "max_iter": self.global_cycles_spin.value(),
                "mc_n": self.mc_n_spin.value(),
                "mc_sigma": self.mc_sigma_spin.value(),
                # Extra params
                "pre_polish": (self.pre_polish_check.isChecked() if hasattr(self, "pre_polish_check") else False),
                "allow_growth": (self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True),
                "auto_scale_y": (self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True),
            },
        }

        return cfg

    def _apply_config(self, c: dict) -> None:
        """Apply a parsed configuration dict to the UI (Lot C)."""

        self.log("Format Version: %s" % c.get("version", "Unknown"), "INFO")

        self._last_config_file = getattr(self, "_last_config_file", None)
        self.l0_spin.setValue(c.get("l0", 500))

        self._apply_material_config(c.get("materials", {}))

        self._apply_stack_rows(c.get("front", []), back=False)

        self.back_check.setChecked(c.get("back_en", False))
        self.back_coat_check.setChecked(c.get("back_coat", False))
        self._apply_stack_rows(c.get("back", []), back=True)

        oblique_mode = c.get("oblique_mode", False)
        self.log(f"[LOAD] Oblique mode: {oblique_mode}", "INFO")
        self.oblique_targets = []
        if hasattr(self, "oblique_check"):
            self.oblique_check.setChecked(oblique_mode)
        self.oblique_mode = oblique_mode

        self.log(f"[LOAD] Loading {len(c.get('targets', []))} targets...", "INFO")
        self._update_target_table_headers()
        self.target_table.setRowCount(0)
        self._apply_target_config(c.get("targets", []), oblique_mode)

        self._apply_optimization_config(c.get("optimization", {}))
        self._update_optim_point_count()
        self._schedule_eval(True)
        self._update_layer_count()

    def _apply_optimization_config(self, opt: dict) -> None:
        """Apply optimization controls from a config dict."""

        self.points_per_target_spin.setValue(opt.get("points_per_target", self.points_per_target_spin.value()))
        self.n100_spin.setValue(opt.get("n100", self.n100_spin.value()))
        self.max_clusters_spin.setValue(opt.get("max_clusters", self.max_clusters_spin.value()))
        self.global_cycles_spin.setValue(opt.get("max_iter", self.global_cycles_spin.value()))
        self.mc_n_spin.setValue(opt.get("mc_n", self.mc_n_spin.value()))
        self.mc_sigma_spin.setValue(opt.get("mc_sigma", self.mc_sigma_spin.value()))

        if hasattr(self, "pre_polish_check"):
            self.pre_polish_check.setChecked(opt.get("pre_polish", self.pre_polish_check.isChecked()))

        if hasattr(self, "allow_growth_check"):
            self.allow_growth_check.setChecked(opt.get("allow_growth", self.allow_growth_check.isChecked()))

        if hasattr(self, "auto_scale_y_check"):
            self.auto_scale_y_check.setChecked(opt.get("auto_scale_y", self.auto_scale_y_check.isChecked()))

    def _apply_material_config(self, materials: dict) -> None:
        """Apply saved material presets and custom n values."""

        for n, d in materials.items():
            if n not in self.mat_widgets:
                continue
            preset_name = d.get("preset", "Custom")
            self.mat_widgets[n]["preset"].setCurrentText(preset_name)
            if preset_name == "Custom":
                self.mat_widgets[n]["n4"].setValue(d.get("n4", 1.5))
                self.mat_widgets[n]["n7"].setValue(d.get("n7", 1.5))

    def _apply_target_config(self, targets: list[dict], oblique_mode: bool) -> None:
        """Apply target rows from a config dict."""

        for t in targets:
            self.add_target()
            r = self.target_table.rowCount() - 1
            active_cb = self.target_table.cellWidget(r, 0)
            if active_cb:
                active_cb.findChild(QCheckBox).setChecked(t.get("active", t.get("on", True)))

            if oblique_mode:
                widget_updates = [
                    (1, t.get("angle", 0.0)),
                    (2, t.get("polarization", "s")),
                    (3, t.get("target_type", "T")),
                    (4, t.get("lmin", 400)),
                    (5, t.get("lmax", 700)),
                    (6, t.get("val_min", t.get("tmin", 0.0))),
                    (7, t.get("val_max", t.get("tmax", 1.0))),
                    (8, t.get("weight", t.get("w", 1.0))),
                ]
                for idx, value in widget_updates:
                    w = self.target_table.cellWidget(r, idx)
                    if w is None:
                        continue
                    if hasattr(w, "setCurrentText"):
                        w.setCurrentText(value)
                    else:
                        w.setValue(value)
            else:
                for idx, value in enumerate([t.get("lmin", 400), t.get("lmax", 700), t.get("tmin", 0), t.get("tmax", 1), t.get("w", 1)], start=1):
                    w = self.target_table.cellWidget(r, idx)
                    if w:
                        w.setValue(value)

    def _apply_stack_rows(self, rows: list[dict], *, back: bool) -> None:
        """Apply front or back stack rows from a config dict."""

        add_row = self._add_back_row if back else self._add_front_row
        table = self.back_table if back else self.front_table
        table.blockSignals(True)
        table.setRowCount(0)
        for row in rows:
            if back:
                add_row(row["mat"], row["qw"])
            else:
                add_row(row["mat"], row["qw"], row["var"])
        table.blockSignals(False)

    def _post_load_config(self, filename: str, config: dict) -> None:
        """UX side-effects after a successful load (summary dialog, toast, ...)."""

        self._last_config_file = filename

        self.log(f"Configuration loaded:  {filename}", "SUCCESS")

        oblique_mode = bool(config.get("oblique_mode", False))

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            mats_cfg = config.get("materials", {})

            front_cfg = config.get("front", [])

            back_cfg = config.get("back", [])

            tgts_cfg = config.get("targets", [])

            l0_val = float(config.get("l0", self.l0_spin.value()))

            summary = build_summary_plain_text(
                "CERTUS DESIGN - Load Summary",
                [
                    f"File: {Path(filename).resolve()}",
                    "",
                    "General",
                    f"Version: {config.get('version', 'unknown')}",
                    (f"Reference wavelength l0: {l0_val:.2f} nm", not (100.0 <= l0_val <= 10000.0)),
                    "",
                    "Stack",
                    f"Materials declared: {len(mats_cfg)}",
                    (f"Front layers: {len(front_cfg)}", len(front_cfg) <= 0),
                    f"Back enabled: {'yes' if bool(config.get('back_en', False)) else 'no'}",
                    f"Back coating enabled: {'yes' if bool(config.get('back_coat', False)) else 'no'}",
                    (
                        f"Back layers: {len(back_cfg)}",
                        bool(config.get("back_coat", False)) and len(back_cfg) <= 0,
                    ),
                    f"Oblique mode: {'yes' if oblique_mode else 'no'}",
                    "",
                    "Targets",
                    (f"Targets loaded: {len(tgts_cfg)}", len(tgts_cfg) <= 0),
                ],
            )

            show_load_summary_dialog(self, "DESIGN Load Summary", summary)

        logging.info("[LOAD] Calling _schedule_eval (final)...")

        self._schedule_eval()

        self._apply_optimization_config(config.get("optimization", {}))
        self._update_optim_point_count()
        self._update_layer_count()

        _load_start = getattr(self, '_load_config_start_time', None)
        if _load_start is not None:
            self.log(f"[LOAD] === load_config complete in {(time.time() - _load_start) * 1000:.1f}ms ===", "INFO")

        self.log(f"Config loaded from {Path(filename).name}", "SUCCESS")

        show_toast(self, f"Loaded: {Path(filename).name}", "success")

    def open_help(self) -> None:
        """Opens HTML documentation"""

        open_documentation("CERTUS_DESIGN")

    def export_excel(self) -> None:
        """Exports design configuration and spectrum to Excel via build_standard_report."""
        import pandas as pd

        f = certus_get_save_file_name(self, "Export to Excel", "Excel (*.xlsx)")

        if not f:
            return

        try:
            # FINAL CLEANUP: Clean + Polish before export

            if self.front_table.rowCount() > 0:
                self.log("Final cleanup before export...", "INFO")

                removed = self.smart_cleanup()

                if removed > 0:
                    self.log(f"Final cleanup: removed {removed} layers.", "INFO")

                    self._is_internal_restart = True

                    self._schedule_eval(True)

            # --- Materials table ---

            mats = self._get_materials()

            df_mats = pd.DataFrame([{"Name": k, "n@400nm": m.n4, "n@700nm": m.n7} for k, m in mats.items()])

            # --- Front stack table ---

            ep = self.ep_current if self.ep_current is not None else []

            stack_rows = []

            for i, layer in enumerate(self._get_front_stack()):
                stack_rows.append(
                    {
                        "#": i + 1,
                        "Material": layer.mat,
                        "QWOT": layer.qwot,
                        "Thickness (nm)": ep[i] if i < len(ep) else 0,
                        "Variable": "Yes" if layer.var else "No",
                    }
                )

            df_stack = pd.DataFrame(stack_rows)

            if ep:
                df_stack = pd.concat(
                    [df_stack, pd.DataFrame([{"#": "TOTAL", "Thickness (nm)": float(np.sum(ep))}])],
                    ignore_index=True,
                )

            # --- Targets table ---

            df_targets = pd.DataFrame(
                [
                    {
                        "Active": "Yes" if t.on else "No",
                        "lambdamin (nm)": t.lmin,
                        "lambdamax (nm)": t.lmax,
                        "Tmin": t.tmin,
                        "Tmax": t.tmax,
                        "Weight": t.w,
                    }
                    for t in self._get_tgts()
                ]
            )

            # --- Summary kv ---

            summary_kv = {
                "Generated": certus_timestamp_display(),
                "CERTUS Suite": APP_SUITE_VERSION,
                "L0 (nm)": self.l0_spin.value(),
                "Total layers": len(stack_rows),
            }

            from certus.utils.certus_data import ReportSection, build_standard_report

            try:
                self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN validation status update skipped during export: %s", exc)
            run_manifest = None
            try:
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: self.last_result or {})
                seed_val = None
                seed_sources = [
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "cfg", {}).get("run_seed") if isinstance(getattr(self, "cfg", None), dict) else None,
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                ]
                for _seed_candidate in seed_sources:
                    if _seed_candidate is None:
                        continue
                    try:
                        seed_val = int(_seed_candidate)
                        break
                    except (TypeError, ValueError):
                        continue
                req = IndexFitRequest(
                    config={
                        "module": "CERTUS_DESIGN",
                        "l0_nm": float(self.l0_spin.value()),
                        "layers_count": int(len(stack_rows)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "filename", "") or "").strip(),
                            str(getattr(self, "_last_config_file", "") or "").strip(),
                        )
                        if p
                    ],
                    seed=seed_val,
                    app_id="CERTUS_DESIGN",
                    app_version=__version__,
                    warnings=list(getattr(self, "validation_warnings", []) or []),
                    status=status_val,
                )
                run_manifest = svc.fit(req).manifest
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN manifest generation failed: %s", exc)
                run_manifest = None

            sections = [
                ReportSection("Summary", kind="kv", content=summary_kv, sheet_name="Summary"),
                ReportSection("Materials", kind="table", content=df_mats, sheet_name="Materials"),
                ReportSection("Front Stack", kind="table", content=df_stack, sheet_name="Stack"),
                ReportSection("Spectral Targets", kind="table", content=df_targets, sheet_name="Targets"),
            ]

            if self.last_result:
                r = self.last_result["vis"]

                df_spectrum = pd.DataFrame({"Wavelength (nm)": r["l"], "Transmission": r["Ts"]})

                sections.append(ReportSection("Spectrum", kind="table", content=df_spectrum, sheet_name="Spectrum"))

            result = build_standard_report(
                sections,
                excel_path=f,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )

            if result.get("excel"):
                self.log(f"Exported to:  {f}", "SUCCESS")

            else:
                self.log("Export failed (build_standard_report error).", "ERROR")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Export error:{str(e)}", "ERROR")

    def closeEvent(self, event) -> None:
        """

        Handles application closure with proper cleanup of all workers.

        Ensures all QThread workers are properly stopped to avoid

        "QThread: Destroyed while thread is still running" warnings.

        """

        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        # Ensure all workers are stopped to avoid "QThread: Destroyed while thread is still running"

        threads_to_stop = []
        try:
            optim_t = getattr(self, "optim_thread", None)
            if optim_t is not None:
                threads_to_stop.append((optim_t, getattr(self, "optim_worker", None)))
        except RuntimeError:
            pass
        try:
            needle_t = getattr(self, "needle_thread", None)
            if needle_t is not None:
                threads_to_stop.append((needle_t, getattr(self, "needle_worker", None)))
        except RuntimeError:
            pass
        try:
            col_t = getattr(self, "col_thread", None)
            if col_t is not None:
                threads_to_stop.append((col_t, getattr(self, "col_worker", None)))
        except RuntimeError:
            pass

        for thread, worker in threads_to_stop:
            try:
                if thread is not None:
                    stop_qt_worker_thread_safely(
                        thread,
                        worker,
                        timeout_ms=2000,
                        logger=getattr(self, "logger", None),
                    )
            except (RuntimeError, AttributeError) as e:
                if hasattr(self, "logger") and self.logger:
                    self.logger.debug(f"Error stopping thread: {e}")

        workers = [
            getattr(self, "warmup_worker", None),
            getattr(self, "eval_worker", None),
        ]

        for worker in workers:
            try:
                if worker and worker.isRunning():
                    # Attempt cooperative stop

                    if hasattr(worker, "request_stop"):
                        worker.request_stop()

                    elif hasattr(worker, "requestInterruption"):
                        worker.requestInterruption()

                    # Wait for graceful shutdown (2000ms timeout)

                    if not worker.wait(2000):
                        logging.critical(
                            f"Worker {type(worker).__name__} did not stop within 2s in closeEvent - "
                            "skipping terminate() to avoid unsafe thread kill."
                        )

            except (RuntimeError, AttributeError) as e:
                # Non-critical: worker may already be destroyed

                if hasattr(self, "logger") and self.logger:
                    self.logger.debug(f"Error stopping worker {type(worker).__name__}: {e}")

        # Call parent cleanup (stops base class workers)

        super().closeEvent(event)

    # =========================================================================

    # UTILITAIRES

    # =========================================================================

    def _update_busy_ui(self, busy_now: bool) -> None:
        """Updates Design-specific button states."""

        for btn in [self.local_btn, self.global_btn, self.color_btn, self.eval_btn]:
            btn.setEnabled(not busy_now)

        self.stop_btn.setEnabled(busy_now)

    def reset_to_defaults(self) -> Any:
        """Resets the entire application to factory defaults (clean slate)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

    def _load_defaults(self) -> None:
        """Loads default values"""

        # Block signals to avoid massive re-evaluations during reset

        self.blockSignals(True)

        try:
            defaults = {
                "H": (2.35, 2.30),
                "L": (1.46, 1.46),
                "A": (2.05, 2.00),
                "B": (1.75, 1.73),
                "C": (1.60, 1.58),
                "Substrate": (1.52, 1.51),
            }

            for name, (n4, n7) in defaults.items():
                if name in self.mat_widgets:
                    self.mat_widgets[name]["n4"].setValue(n4)

                    self.mat_widgets[name]["n7"].setValue(n7)

                    self.mat_widgets[name]["preset"].setCurrentText("Custom")

            # Reset Global Parameters

            if hasattr(self, "l0_spin"):
                self.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self, "back_check"):
                self.back_check.setChecked(False)

            if hasattr(self, "back_coat_check"):
                self.back_coat_check.setChecked(False)

            if hasattr(self, "oblique_check"):
                self.oblique_check.setChecked(False)

            if hasattr(self, "auto_scale_y_check"):
                self.auto_scale_y_check.setChecked(True)

            if hasattr(self, "allow_growth_check"):
                self.allow_growth_check.setChecked(True)

            if hasattr(self, "pre_polish_check"):
                self.pre_polish_check.setChecked(False)

            # Add default layers

            for _ in range(4):
                self.add_front_layer()

            # Add default target

            self.add_target()

            # Default optimization parameters

            self.n100_spin.setValue(6000)

            self.max_clusters_spin.setValue(40)

            self.global_cycles_spin.setValue(50)

            if hasattr(self, "points_per_target_spin"):
                self.points_per_target_spin.setValue(50)

            # Default MC parameters

            if hasattr(self, "mc_n_spin"):
                self.mc_n_spin.setValue(200)

            if hasattr(self, "mc_sigma_spin"):
                self.mc_sigma_spin.setValue(2.0)

            # Update Tikhonravov points after loading defaults

            QTimer.singleShot(500, self._update_tikhonravov_points)

            self.log("Default configuration loaded with optimized PGLOBAL settings.", "INFO")

        finally:
            self.blockSignals(False)

            # Force one final evaluation to show the default design

            self._schedule_eval(instant=True)

# =============================================================================

# ENTRY POINT

# =============================================================================

