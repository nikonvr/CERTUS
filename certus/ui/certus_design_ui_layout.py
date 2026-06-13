from certus.core.certus_core import __version__, APP_SUITE_VERSION
import os
from pathlib import Path
import multiprocessing
import sys
import functools
from certus.core.certus_core import create_module_environment
import logging
import time
import traceback
import copy
from threading import Event
from typing import Any, List, Dict
import numpy as np
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
from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)
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
from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)
from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *
from certus.ui.mixins.certus_design_plot_mixin import CertusDesignUIPlotMixin

class CertusDesignLayoutMixin:
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

            combo.addItems(["Custom"])

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

