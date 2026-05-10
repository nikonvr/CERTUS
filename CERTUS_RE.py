# =============================================================================

# CERTUS REVERSE ENGINEERING MODULE

# Functional area: Post-deposition Analysis & Drift Correction

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-RE.py - Reverse Engineering & Drift Correction

=========================================================

"""

from __future__ import annotations

__version__ = "26_01"

# RE: +/-% thickness search radius for L-BFGS-B (no toolbar control; fixed default).

import copy

import functools


import logging

import multiprocessing

import os

from pathlib import Path


import sys

import time

import traceback






from typing import Any, Dict, List

import numpy as np

import pyqtgraph as pg

from certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
)

from certus_physics import (  # TMM, targets, RMSE (same bundle as `certus_re_helpers`)
    Layer,
    ObliqueTarget,
)

from certus_physics import (
    init_thickness,
    calc_spectrum_front_wrapper,
    calc_spectrum_full_exact_wrapper,
)

from certus_spectral_workers import EvalWorker, WarmupWorker

from certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)
from certus_ux import OBJ, build_premium_overrides
from certus_skeleton import install_skeleton, uninstall_skeleton

from certus_ui import (
    attach_excel_clipboard_context_menu,
    CertusBaseApp,
    CertusCard,
    CertusCollapsible,
    CertusScientificPlot,
    CertusStatusPill,
    CertusTheme,
    CertusThemeToggle,
    confirm_stop_with_timeout,
    create_flashy_grid,
    create_header_logo_widget,
    create_styled_button,
    create_top_actions_bar,
    EnhancedProgressWidget,
    enable_file_drop,
    ExcelTableWidget,
    FlashyCard,
    get_certus_last_dir,
    init_certus_app,
    install_standard_shortcuts,
    open_documentation,
    set_certus_last_dir,
    set_certus_window_icon,
    show_toast,
    WelcomeGuideWidget,
    wrap_scientific_plot_with_toolbar,
)

from certus_core import (
    CFG,
    certus_timestamp_display,
    certus_timestamp_file,
    create_module_environment,
    get_resource_path,
    setup_logging,
)

from certus_data import OPENPYXL_AVAILABLE


# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_RE")

script_dir = env["script_dir"]

# =============================================================================

# FURTHER IMPORTS

# =============================================================================

from certus_re_workers import REWorker

from certus_animations import fade_in

# RE helpers: explicit re-exports (ARCH-1; replaced the legacy for-loop that copied certus_re_helpers into globals()).

from certus_re_helpers import (
    ParsedREColumn,
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    RE_GUI_DEFAULT_RE_QWOT_ALPHA,
    RE_HL_DELTA_RE_REG_SQRT_W,
    RE_OPTIM_POINTS_PER_TARGET,
    RE_P4_BEAM_AP_BOUNDS_DEG,
    RE_P4_BEAM_N_KNOTS,
    RE_PHASE2_FD_MAX_WORKERS,
    RE_PHASE2_FD_PARALLEL,
    RE_PHASE2_ONESIDED_SPLINE_FD,
    RE_PHASE4_APERTURE_SCAN_POINTS,
    RE_PHASE4_TRF_MAX_NFEV,
    RE_RANKING_ALPHA_REF,
    RE_RE_DEADZONE_DELTA_RE_ABS,
    RE_RE_DEADZONE_QWOT_ABS,
    RE_SPEED_PRESETS,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    RE_SUB_CAUCHY_TUBE_DELTA,
    RE_THICKNESS_SEARCH_RADIUS_PCT,
    TabularMaterial,
    _RE_CANONICAL_SHEETS,
    _RE_FT_COL_MAT,
    _RE_FT_COL_N,
    _RE_FT_COL_NUM,
    _RE_FT_COL_QW,
    _RE_FT_COL_THICK,
    _parse_re_rmse_combined_from_progress_message,
    _re_calc_spectrum_for_config,
    _re_cell_str,
    _re_find_measurement_wavelength_column,
    _re_header_is_wavelength_label,
    _re_header_looks_like_spectrum_title,
    _re_index_column_map,
    _re_index_split_header_and_data,
    _re_measurement_values_are_percent,
    _re_p4_ap_staircase_polyline,
    _re_p4_kwargs_from_opt_result,
    _re_p4_sort_knot_pairs,
    _re_parse_design_metadata_row,
    _re_parse_design_qwot_rows,
    _re_qwot_rmse_abs_delta_at_l0,
    _re_resolve_re_workbook_sheets,
    _re_rmse_combined_spectral_qwot,
    _re_rmse_oblique_weighted,
    _re_sort_results_best_for_table_and_apply,
    format_re_drift_log_triplet_pct,
    format_re_spline_knots_log,
    parse_re_column_header,
    re_apply_re_index_model,
    re_delta_qwot_per_layer,
    re_drift_result_log_suffix,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    re_substrate_cauchy_n_re_from_theta,
)

# Configure GUI

# Conditional Excel Import (OPENPYXL_AVAILABLE used elsewhere in module)

# =============================================================================

# LOGGING CONFIGURATION

# =============================================================================

# Logger initialized in CertusREApp

# This ensures consistency with other CERTUS modules

# script_dir already set by bootstrap_app()

# =============================================================================

# AUTOMATIC PRECISION ADAPTATION

# =============================================================================

# Use wrappers if single precision enabled

# Wrappers enforce (d,n) consistency with CFG single-precision when enabled.

calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# =============================================================================

# WORKERS (REWorker below; warmup + spectral eval in certus_spectral_workers)

# =============================================================================

class CertusREApp(CertusBaseApp):
    """CERTUS application  reverse engineering (Excel measurements)."""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS_RE"

    APP_TITLE = "CERTUS  Reverse Engineering"

    DEFAULT_WIDTH = 1440

    DEFAULT_HEIGHT = 640

    MIN_WIDTH = 1020

    MIN_HEIGHT = 520

    def __init__(self):
        """Initialize CERTUS_RE (reverse engineering, Excel input, evaluation + REWorker)."""

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Shared state with base (tables, spectrum)

        self.target_widgets: List = []

        self.ep_current: np.ndarray | None = None

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

        # Oblique mode

        self.oblique_mode = False

        # Workers (RE: spectral evaluation + REWorker only)

        self.eval_worker: EvalWorker | None = None

        self._re_worker: REWorker | None = None

        self.warmup_worker: WarmupWorker | None = None

        self.accumulated_evals = 0

        self._re_nfev_cumulative = 0  # cumulative RE nfev for the Evals bar

        self._warmup_done = False

        self._re_loaded = False  # True after a successful load_reverse_engineering()

        self._re_workbook_path: str | None = None  # last loaded RE .xlsx (logs / worker cfg)

        self._re_mode_active = False  # True while a RE optimization is running

        self._re_tabular_H: TabularMaterial | None = None

        self._re_tabular_L: TabularMaterial | None = None

        self._re_tabular_Sub: TabularMaterial | None = None

        self._re_targets: list = []  # full ObliqueTarget list (not in widget) for RE

        self._re_meas_lambda_min_nm: float | None = None

        self._re_meas_lambda_max_nm: float | None = None

        self._re_opt_a_pct = 0.0

        self._re_opt_b_pct = 0.0

        self._re_opt_f_pct = 0.0

        self._re_spline_dH: np.ndarray | None = None

        self._re_spline_dL: np.ndarray | None = None

        self._re_spline_lam2_nm: float | None = None

        self._re_sub_cauchy_a0: float | None = None

        self._re_sub_cauchy_a1: float | None = None

        self._re_sub_cauchy_a2: float | None = None

        # n(lambda) preview during REWorker (corrected indices = same *correc* as live spectrum)

        self._re_nk_preview_dH: list[float] | None = None

        self._re_nk_preview_dL: list[float] | None = None

        self._re_nk_preview_lam2: float | None = None

        self._re_nk_preview_sub012: list[float] | None = None

        self._re_backside_summary_html: str = ""

        # Phase 4 (faisceau) : dernier best result applique  aligne RMSE / eval UI sur le fit P4.

        self._re_p4_display_beam_active: bool = False

        self._re_p4_display_ap_knots_deg: np.ndarray | None = None

        self._re_p4_display_ap_knots_nm: np.ndarray | None = None

        # Last RE results table snapshot (Run RE)  reopened via "Display results".

        self._re_last_results_snapshot: dict[str, Any] | None = None

        # After an RE Run: alpha QWOT phase 2b (aligns _compute_re_rmse with the worker).

        self._re_rmse_qwot_alpha_ref: float | None = None

        # Last alpha emitted live: change -> reset of the status bar best RMSE (comparable metric).

        self._re_last_live_alpha_qwot: float | None = None

        # RE Options (initialised before UI)

        self.cfg: dict[str, Any] = {}

        # Theme Application

        CertusTheme.apply_to_app(QApplication.instance())

        # UI Construction

        self._build_ui()

        self._setup_shortcuts()

        self._load_defaults()

        # Warmup JIT

        self.status_label.setText("Compiling JIT kernels...")

        self.warmup_worker = WarmupWorker()

        self.warmup_worker.finished.connect(self._on_warmup_done)

        self.warmup_worker.start()

    # =========================================================================

    # UI CONSTRUCTION

    # =========================================================================

    def _get_default_splitter_sizes(self) -> list[int]:
        """RE specific splitter sizes."""

        return [380, 1060]

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for RE."""

        substrate_type = ""

        substrate_index = "Load an RE file"

        if getattr(self, "_re_loaded", False):
            substrate_type = "Tabulaire (Excel RE)"

            sub = getattr(self, "_re_tabular_Sub", None)

            if sub is not None:
                l0 = float(self._stack_info_l0_nm())

                nk = sub.get_nk(np.array([l0], dtype=np.float64))

                substrate_index = f"n@lambda₀={float(nk[0].real):.3f}"

            else:
                substrate_index = "substrate (indices.xlsx)"

        return substrate_type, substrate_index

    def _stack_info_front_table_cols(self) -> tuple[int, int]:
        """Table RE 5 colonnes : Mat=1, QWOT=3."""

        return (_RE_FT_COL_MAT, _RE_FT_COL_QW)

    def _build_left_panel(self) -> QWidget:
        """Left panel: RE workflow, options, Excel data, display, actions."""

        left_panel = QWidget()

        left_panel.setMinimumWidth(300)

        left_panel.setObjectName("LeftPanel")

        left_layout = QVBoxLayout(left_panel)

        left_layout.setSpacing(0)

        left_layout.setContentsMargins(0, 0, 0, 0)

        header_widget = create_header_logo_widget(
            "RE",
            self.APP_TITLE,
            logo_width=176,
            module_name="CERTUS_RE",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_layout.addWidget(header_widget)

        action_bar = create_top_actions_bar(
            self,
            None,
            None,
            self.export_excel,
            self.open_help,
            action_tooltips={
                "Export": (
                    "Excel snapshot: materials, stack thicknesses, targets (oblique columns if RE/oblique), "
                    "and last evaluated spectrum (R+T columns per angle/pol when available). "
                    "For full target-vs-theory tables after a fit, use the dedicated RE export action if present."
                ),
                "Help": "Open pages/CERTUS_RE.html in the default browser (CERTUS-RE scientific datasheet).",
            },
        )

        left_layout.addWidget(action_bar)

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()

        scroll_layout = QVBoxLayout(scroll_content)

        scroll_layout.setContentsMargins(0, 0, 4, 0)

        scroll_layout.setSpacing(8)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Load workbook  2 Evaluate spectrum  3 Run RE  4 Inspect results")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        workflow_card.body.addWidget(workflow_hint)

        scroll_layout.addWidget(workflow_card)

        re_workflow_widget = self._build_re_workflow_group()

        re_options_widget = self._build_re_options_group()

        re_excel_widget = self._build_re_excel_data_group()

        display_widget = self._build_display_group()

        self._init_re_calc_param_widgets()

        refine_widget = self._build_refine_group()

        scroll_layout.addWidget(CertusCollapsible("1  RE workflow", re_workflow_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("2  Options", re_options_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("3  Excel data", re_excel_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("4  Display", display_widget, expanded=False))

        scroll_layout.addWidget(CertusCollapsible("5  Refinement", refine_widget, expanded=True))

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        left_layout.addWidget(scroll, 1)

        actions_wrap = CertusCard("Actions")

        actions_wrap.body.setContentsMargins(10, 8, 10, 10)

        actions_wrap.body.setSpacing(8)

        actions_wrap.body.addLayout(self._build_action_buttons())

        left_layout.addWidget(actions_wrap)

        fade_in(actions_wrap, duration_ms=200)

        return left_panel

    def _apply_theme(self):
        """Apply Certus theme dynamically"""

        self._apply_certus_compact_theme(
            plots=[
                getattr(self, "spectrum_plot", None),
                getattr(self, "profile_plot", None),
                getattr(self, "nk_plot", None),
            ]
        )

        self.setStyleSheet(self.styleSheet() + "\n" + build_premium_overrides())

    def _build_re_workflow_group(self) -> CertusCard:
        """Main RE steps: load Excel then optimize."""

        c = CertusCard("RE workflow")

        lay = c.body

        lay.setSpacing(10)

        hint = QLabel("<b>1</b> Load workbook &nbsp;&nbsp; <b>2</b> Evaluate spectrum &nbsp;&nbsp; <b>3</b> Run RE")

        hint.setWordWrap(True)

        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(hint)

        btn_lay = QHBoxLayout()

        btn_lay.setContentsMargins(0, 0, 0, 0)

        btn_lay.setSpacing(10)

        self.load_re_btn = QPushButton(" Load RE file (Excel)")
        self.load_re_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.load_re_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.load_re_btn.setToolTip("Select and load a previously saved R/E inversion file.")

        self.load_re_btn.clicked.connect(self.load_reverse_engineering)

        self.load_re_btn.setFixedHeight(32)

        btn_lay.addWidget(self.load_re_btn)

        self.launch_re_btn = QPushButton(" Run RE")
        self.launch_re_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.launch_re_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.launch_re_btn.setToolTip("Run the R/E inversion process on current targets.")

        self.launch_re_btn.clicked.connect(self.launch_re)

        self.launch_re_btn.setFixedHeight(32)

        self.launch_re_btn.setEnabled(False)

        btn_lay.addWidget(self.launch_re_btn)

        lay.addLayout(btn_lay)

        self.display_re_results_btn = QPushButton(" Display results")
        self.display_re_results_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.display_re_results_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.display_re_results_btn.setToolTip(
            "Reopen the results table from the last Run RE (QWOT, DeltaQWOT, splines DeltaRe, RMSE, exports...)."
        )

        self.display_re_results_btn.setEnabled(False)

        self.display_re_results_btn.clicked.connect(self._on_display_re_results_clicked)

        lay.addWidget(self.display_re_results_btn)

        return c

    def _build_re_options_group(self) -> CertusCard:
        """RE speed preset (Slow / Medium / Fast)  other hyperparameters are internal."""

        c = CertusCard("RE optimization")

        lay = c.body

        lay.setSpacing(8)

        hint = QLabel(
            "Modes below are left to right: <b>Slow</b> -> <b>Medium</b> -> <b>Fast</b>. "
            "<b>Slow</b> = larger budget (more multistarts, top-K, shakes, iterations) to seek a better minimum. "
            "<b>Medium</b> = settings validated on the optimal batch (exploration + iterations). "
            "<b>Fast</b> = fewer restarts / top-K / shakes and reduced iterations  quick run."
        )

        hint.setWordWrap(True)

        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(hint)

        row = QHBoxLayout()

        row.addWidget(QLabel("Mode :"))

        _re_speed_btn_group = QButtonGroup(self)

        self.re_speed_slow_radio = QRadioButton("Slow")

        self.re_speed_slow_radio.setToolTip("Multistarts ×4, top-K 5, shakes 8, increased P1/2a/2b iterations.")

        self.re_speed_medium_radio = QRadioButton("Medium")

        self.re_speed_medium_radio.setToolTip(
            "Matches optimal batch defaults (multistarts 2, top-K 3, shakes 4, maxiter 85/45/110)."
        )

        self.re_speed_fast_radio = QRadioButton("Fast")

        self.re_speed_fast_radio.setToolTip(
            "Single multistart, top-K 1, no shakes, reduced iterations  good for a first try."
        )

        self.re_speed_medium_radio.setChecked(True)

        for rb in (
            self.re_speed_slow_radio,
            self.re_speed_medium_radio,
            self.re_speed_fast_radio,
        ):
            _re_speed_btn_group.addButton(rb)

            row.addWidget(rb)

        row.addStretch()

        lay.addLayout(row)

        self.re_qwot_penalty_chk = QCheckBox("Enable QWOT penalty in objective (RMSE)")

        self.re_qwot_penalty_chk.setChecked(bool(self.cfg.get("re_enable_qwot_penalty", True)))

        self.re_qwot_penalty_chk.setToolTip(
            "ON: displayed RMSE_facade = sqrt(RMSE_sp2 + alpha·RMSE_QWOT2) (alpha varies by phase). "
            "Le solveur minimise TRF_RMS(r) (voir logs iter). OFF: RMSE_facade = RMSE_sp."
        )

        self.re_qwot_penalty_chk.stateChanged.connect(lambda s: self.cfg.update({"re_enable_qwot_penalty": bool(s)}))

        self.cfg["re_enable_qwot_penalty"] = bool(self.re_qwot_penalty_chk.isChecked())

        lay.addWidget(self.re_qwot_penalty_chk)

        # Pas d'input GUI pour ap : en P4 on travaille uniquement avec les paliers optimises.

        self.cfg["re_beam_aperture_deg"] = float(RE_GUI_DEFAULT_BEAM_APERTURE_DEG)

        return c

    def _build_re_excel_data_group(self) -> CertusCard:
        """Indices + lambda₀ / back face: all from the RE Excel file."""

        c = CertusCard("Data from Excel")

        lay = c.body

        lay.setSpacing(8)

        lbl_idx = QLabel("<b>Optical indices</b>  H, L and substrate:  index  sheet (n(lambda), k(lambda) tables).")

        lbl_idx.setWordWrap(True)

        lbl_idx.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(lbl_idx)

        sep = QFrame()

        sep.setFrameShape(QFrame.Shape.HLine)

        sep.setFrameShadow(QFrame.Shadow.Sunken)

        lay.addWidget(sep)

        sub = QLabel("<b>Design and measurement reference</b>")

        sub.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")

        lay.addWidget(sub)

        self._re_readout_lambda_lbl = QLabel()

        self._re_readout_lambda_lbl.setWordWrap(True)

        self._re_readout_lambda_lbl.setTextFormat(Qt.TextFormat.RichText)

        self._re_readout_lambda_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._re_readout_backside_lbl = QLabel()

        self._re_readout_backside_lbl.setWordWrap(True)

        self._re_readout_backside_lbl.setTextFormat(Qt.TextFormat.RichText)

        self._re_readout_backside_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        lay.addWidget(self._re_readout_lambda_lbl)

        lay.addWidget(self._re_readout_backside_lbl)

        fit_row = QHBoxLayout()

        fit_row.setContentsMargins(0, 0, 0, 0)

        fit_row.setSpacing(8)

        fit_row.addWidget(QLabel("RE fit lambda window:"))

        self.re_fit_lambda_min_spin = QDoubleSpinBox()

        self.re_fit_lambda_min_spin.setRange(200.0, 20000.0)

        self.re_fit_lambda_min_spin.setDecimals(1)

        self.re_fit_lambda_min_spin.setSingleStep(10.0)

        self.re_fit_lambda_min_spin.setSuffix(" nm")

        self.re_fit_lambda_min_spin.setToolTip("Ignore all RE measurement points with lambda below this minimum.")

        self.re_fit_lambda_min_spin.valueChanged.connect(self._on_re_fit_window_changed)

        fit_row.addWidget(self.re_fit_lambda_min_spin)

        fit_row.addWidget(QLabel("->"))

        self.re_fit_lambda_max_spin = QDoubleSpinBox()

        self.re_fit_lambda_max_spin.setRange(200.0, 20000.0)

        self.re_fit_lambda_max_spin.setDecimals(1)

        self.re_fit_lambda_max_spin.setSingleStep(10.0)

        self.re_fit_lambda_max_spin.setSuffix(" nm")

        self.re_fit_lambda_max_spin.setToolTip("Ignore all RE measurement points with lambda above this maximum.")

        self.re_fit_lambda_max_spin.valueChanged.connect(self._on_re_fit_window_changed)

        fit_row.addWidget(self.re_fit_lambda_max_spin)

        fit_row.addStretch()

        lay.addLayout(fit_row)

        self._clear_re_excel_readout_ui()

        return c

    def _clear_re_session_data(self) -> None:
        """Reset all RE session specific data (after file reset or JSON load)."""

        self._re_loaded = False

        self._re_workbook_path = None

        self._re_targets = []

        self._re_meas_lambda_min_nm = None

        self._re_meas_lambda_max_nm = None

        self._re_tabular_H = None

        self._re_tabular_L = None

        self._re_tabular_Sub = None

        self._re_spline_dH = None

        self._re_spline_dL = None

        self._re_spline_lam2_nm = None

        self._re_sub_cauchy_a0 = None

        self._re_sub_cauchy_a1 = None

        self._re_sub_cauchy_a2 = None

        self._re_opt_a_pct = 0.0

        self._re_opt_b_pct = 0.0

        self._re_opt_f_pct = 0.0

        self._re_clear_re_nk_preview()

        self._clear_re_excel_readout_ui()

        self._re_last_results_snapshot = None

        self._re_rmse_qwot_alpha_ref = None

        self._re_last_live_alpha_qwot = None

        self._sync_display_re_results_btn_state()

    def _clear_re_excel_readout_ui(self) -> None:
        """Placeholders + unlock lambda₀ and back face (outside RE session)."""

        if not hasattr(self, "_re_readout_lambda_lbl"):
            return

        self._re_readout_lambda_lbl.setText(
            f'<span style="color:{CertusTheme.TEXT_SUB};">'
            "<b>Reference lambda₀</b> :  (load an RE file; value read from the <b>design</b> sheet)"
            "</span>"
        )

        self._re_readout_backside_lbl.setText(
            f'<span style="color:{CertusTheme.TEXT_SUB};">'
            "<b>Substrate back face</b> :  (load an RE file; "
            "inferred from measurement column <b>headers</b>)"
            "</span>"
        )

        self._re_backside_summary_html = ""

        if hasattr(self, "re_fit_lambda_min_spin") and hasattr(self, "re_fit_lambda_max_spin"):
            _dlo, _dhi = self._re_default_target_lmin_lmax_nm()

            self.re_fit_lambda_min_spin.blockSignals(True)

            self.re_fit_lambda_max_spin.blockSignals(True)

            try:
                self.re_fit_lambda_min_spin.setValue(float(_dlo))

                self.re_fit_lambda_max_spin.setValue(float(_dhi))

            finally:
                self.re_fit_lambda_min_spin.blockSignals(False)

                self.re_fit_lambda_max_spin.blockSignals(False)

        if hasattr(self, "l0_spin"):
            self.l0_spin.setReadOnly(False)

            self.l0_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)

        if hasattr(self, "back_check"):
            self.back_check.setEnabled(True)

    def _apply_re_excel_readout_from_file(
        self,
        lambda_ref_nm: float,
        spectra_columns: list,
    ) -> None:
        """Update  Excel output  labels and lock synchronized fields."""

        if not hasattr(self, "_re_readout_lambda_lbl"):
            return

        lr = float(lambda_ref_nm)

        self._re_readout_lambda_lbl.setText(
            f"<b>Reference lambda₀ (Excel design sheet output)</b> : <b>{lr:.1f} nm</b>"
        )

        specs = [s for s, _ in spectra_columns]

        n = len(specs)

        n_with = sum(1 for s in specs if s.include_backside)

        if n == 0:
            html = "<b>Substrate back face (Excel header output)</b> : no measurement columns."

        elif n_with == 0:
            html = (
                f"<b>Substrate back face (inconsistent plate  Excel output)</b> : "
                f"<b>no</b> for all <b>{n}</b> column(s) (all without back face per headers)."
            )

        elif n_with == n:
            html = (
                f"<b>Substrate back face (inconsistent plate  Excel output)</b> : "
                f"<b>yes</b> for all <b>{n}</b> column(s) (all with back face per headers)."
            )

        else:
            parts = [
                "<b>Substrate back face (Excel output)</b> : <b>mixed</b>  "
                f"{n_with} column(s) <b>with</b> back face, {n - n_with} <b>without</b> :"
            ]

            for s in specs:
                parts.append(
                    f" <i>{s.raw_header}</i> : "
                    f"{'<b>with</b> back face' if s.include_backside else '<b>without</b> back face'}"
                )

            html = "<br>".join(parts)

        self._re_backside_summary_html = html

        self._re_readout_backside_lbl.setText(html)

        if hasattr(self, "l0_spin"):
            self.l0_spin.setReadOnly(True)

            self.l0_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

            self.l0_spin.setToolTip("Value fixed by the RE file <b>design</b> sheet  read-only.")

        if hasattr(self, "back_check"):
            self.back_check.setEnabled(False)

            self.back_check.setToolTip("State fixed by column headers on the RE <b>measurement</b> sheet  read-only.")

    def _on_re_fit_window_changed(self) -> None:
        """Update eval when RE lambda window changes."""

        if getattr(self, "_re_loaded", False):
            self._schedule_eval(True)

    def _re_current_fit_lambda_bounds_nm(self) -> tuple[float, float]:
        """Current GUI lambda bounds used to keep/discard RE measurement points."""

        lo = float(self.re_fit_lambda_min_spin.value() if hasattr(self, "re_fit_lambda_min_spin") else 200.0)

        hi = float(self.re_fit_lambda_max_spin.value() if hasattr(self, "re_fit_lambda_max_spin") else 20000.0)

        if hi < lo:
            lo, hi = hi, lo

        return lo, hi

    def _re_filter_targets_by_fit_window(self, tgts: list[ObliqueTarget]) -> list[ObliqueTarget]:
        """Keep only targets whose center wavelength is inside GUI lambda bounds."""

        if not tgts:
            return []

        lo, hi = self._re_current_fit_lambda_bounds_nm()

        out: list[ObliqueTarget] = []

        for t in tgts:
            wl_c = 0.5 * (float(t.lmin) + float(t.lmax))

            if lo <= wl_c <= hi:
                out.append(t)

        return out

    def _build_display_group(self) -> CertusCard:
        """Spectrum plot display options."""

        c = CertusCard("Display")

        lay = c.body

        self.auto_scale_y_check = QCheckBox("Auto Y scale (spectrum)")

        self.auto_scale_y_check.setChecked(True)

        self.auto_scale_y_check.setToolTip("Adjust spectrum Y axis to the range of displayed curves.")

        self.auto_scale_y_check.stateChanged.connect(self._on_update_spectrum_y_scale_signal)

        lay.addWidget(self.auto_scale_y_check)

        return c

    def _init_re_calc_param_widgets(self) -> None:
        """lambda0 and substrate back face: same fields as elsewhere, but hidden here

        (duplicate of "Data from Excel"  values read / locked from the workbook)."""

        if hasattr(self, "l0_spin"):
            return

        self.l0_spin = QDoubleSpinBox(self)

        self.l0_spin.setRange(200, 20000)

        self.l0_spin.setValue(CFG.DEFAULT_L0)

        self.l0_spin.setDecimals(1)

        self.l0_spin.setSuffix(" nm")

        self.l0_spin.valueChanged.connect(self._on_schedule_eval_signal)

        self.l0_spin.valueChanged.connect(self._on_l0_changed_refresh_front_table)

        self.l0_spin.valueChanged.connect(self._on_l0_changed_update_substrate_info)

        self.l0_spin.setToolTip(
            "lambda₀ (nm)  apres chargement RE, fixe par la feuille <b>design</b> (voir encadre Excel ci-dessus)."
        )

        self.l0_spin.setVisible(False)

        self.back_check = QCheckBox(self)

        self.back_check.setText("Substrate back face (Fresnel)")

        self.back_check.setToolTip(
            "Face arriere substrate  apres chargement RE, fixe par les en-tetes <b>measurement</b>."
        )

        self.back_check.stateChanged.connect(self._on_schedule_eval_instant_signal)

        self.back_check.setVisible(False)

    def _build_refine_group(self) -> CertusCard:
        """Options to refine or fix optical material indices during Reverse Engineering."""

        c = CertusCard("Index Refinement (Degrees of Freedom)")

        lay = c.body

        def _add_check(k: str, title: str, tooltip: str) -> QCheckBox:

            chk = QCheckBox(title)

            chk.setChecked(bool(self.cfg.get(k, False)))

            chk.setToolTip(tooltip)

            def _update_cfg_from_state(state: int, *, cfg_key=k) -> None:
                self.cfg.update({cfg_key: bool(state)})

            chk.stateChanged.connect(_update_cfg_from_state)

            lay.addWidget(chk)

            return chk

        self.sub_refine_check = _add_check(
            "re_phase2b_substrate_cauchy",
            "Refine Substrate Index (Cauchy)",
            "Refine substrate Cauchy parameters if a Cauchy model is available.",
        )

        self.h_refine_check = _add_check(
            "re_refine_h", "Refine Material 1 Index (H)", "Enable B-Spline refinement for the high-index material."
        )

        self.l_refine_check = _add_check(
            "re_refine_l", "Refine Material 2 Index (L)", "Enable B-Spline refinement for the low-index material."
        )

        return c

    def _on_schedule_eval_signal(self, *_args) -> None:

        self._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self._schedule_eval(True)

    def _on_update_spectrum_y_scale_signal(self, *_args) -> None:

        self._update_spectrum_y_scale()

    def _on_l0_changed_refresh_front_table(self, *_args) -> None:

        self._re_refresh_front_table_num_and_n()

    def _on_l0_changed_update_substrate_info(self, *_args) -> None:

        self._update_substrate_info()

    def _on_re_worker_error_cleanup(self, *_args) -> None:

        uninstall_skeleton(self.plot_tabs)

    def _build_action_buttons(self) -> QGridLayout:
        """Four actions in 2x2 grid."""

        g = QGridLayout()

        g.setHorizontalSpacing(8)

        g.setVerticalSpacing(8)

        # Evaluate

        self.eval_btn = QPushButton("EVALUATE")
        self.eval_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.eval_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.eval_btn.setToolTip("Compute RMSE and spectral curves for current stack (Ctrl+E)")

        self.eval_btn.setEnabled(False)

        self.eval_btn.clicked.connect(functools.partial(self._schedule_eval, True))

        g.addWidget(self.eval_btn, 0, 0)

        # Stop (evaluation or RE in progress)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName(OBJ.DANGER_BUTTON)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.stop_btn.setToolTip("Stop spectral evaluation or RE optimization in progress.")

        self.stop_btn.clicked.connect(self.stop_optim)

        g.addWidget(self.stop_btn, 0, 1)

        # Stack Info Button

        self.substrate_info_btn = QPushButton(" Stack Info")

        self.substrate_info_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.substrate_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.substrate_info_btn.setToolTip("Substrate summary and stack structure in QWOT in a separate window.")

        self.substrate_info_btn.clicked.connect(self._show_substrate_info_window)

        g.addWidget(self.substrate_info_btn, 1, 0)

        # Clear / Reset (use app's full reset: tables, state, plots, then _load_defaults)

        from certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self, use_app_reset=True)

        g.addWidget(self.clear_btn, 1, 1)

        g.setColumnStretch(0, 1)

        g.setColumnStretch(1, 1)

        return g

    def _trigger_post_undo_action(self):
        """RE specific post-undo action."""

        self._schedule_eval(True)

    def _show_substrate_info_window(self):
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

        self.substrate_info_window.setWindowTitle(" Stack information")

        self.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("Substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.substrate_type_label = QLabel("N/A")

        self.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.substrate_type_label, 0, 1)

        info_layout.addWidget(self.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Stack structure (QWOT)")

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

    def _build_right_panel(self):
        """Constructs right panel with visualization and tables"""

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)

        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Visualization Area

        self.viz_stack = QStackedWidget()

        self.viz_stack.addWidget(WelcomeGuideWidget("CERTUS_RE"))

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

        # Buttons to detach plots

        plot_header = QWidget()

        plot_header.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(6, 2, 6, 2)

        plot_header_layout.setSpacing(10)

        detach_btn = create_styled_button("⬡  Detach plot", "secondary")

        detach_btn.setToolTip("Open the current plot tab in a separate window.")

        detach_btn.clicked.connect(self.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_hint = QLabel(
            f'<span style="color:{CertusTheme.TEXT_SUB}; font-size:11px;">'
            "RE load, run, and optimization options: left panel."
            "</span>"
        )

        plot_hint.setWordWrap(True)

        plot_header_layout.addWidget(plot_hint, 1)

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.plot_tabs)

        self.plot_tabs.addTab(self.spectrum_plot, "Spectrum (T)")

        self.plot_tabs.addTab(self.profile_plot, "Index profile")

        self.plot_tabs.addTab(self.nk_plot, "n(lambda)")

        c1 = FlashyCard(
            "Excel workbook",
            "Measurement, design, and index sheets\nwith tabulated n(lambda), k(lambda)",
            icon="",
        )

        c2 = FlashyCard(
            "Spectral evaluation",
            "Target vs model display\nRMSE before RE optimization",
            icon="",
        )

        c3 = FlashyCard(
            "Reverse engineering",
            "Two-phase fit: thicknesses\nthen DeltaRe drift on H, L",
            icon="",
        )

        c4 = FlashyCard(
            "Reports",
            "Excel / HTML export\nstack and spectrum",
            icon="",
        )

        self.perf_tab = create_flashy_grid([c1, c2, c3, c4])

        self.plot_tabs.addTab(self.perf_tab, "Why CERTUS-RE?")

        v_lay.addWidget(plot_container)

        self.viz_stack.addWidget(viz_container)

        right_splitter.addWidget(self.viz_stack)

        # Table Area

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        bottom_splitter.addWidget(self._build_front_table_widget())

        bottom_splitter.addWidget(self._build_target_table_widget())

        bottom_splitter.setStretchFactor(0, 2)

        bottom_splitter.setStretchFactor(1, 3)

        bottom_splitter.setSizes([440, 560])

        right_splitter.addWidget(bottom_splitter)

        right_splitter.setSizes([620, 320])

        right_layout.addWidget(right_splitter)

        # Log Container

        self.log_container = self._build_log_container()

        self.log_container.setVisible(False)  # Start hidden

        right_layout.addWidget(self.log_container)

        return right_panel

    def _build_front_table_widget(self) -> QWidget:
        """Front stack table (loaded from Excel or edited manually)."""

        self.front_tabs = QTabWidget()

        self.front_tabs.setMaximumWidth(580)

        # Tab 1: Front Structure

        self.front_container = QWidget()

        f_lay = QVBoxLayout(self.front_container)

        f_head = QHBoxLayout()

        f_head.addWidget(QLabel("<b>Stack (front face)</b>"))

        self.layer_count_label = QLabel("0 layers")

        f_head.addStretch()

        self.detach_btn = QPushButton("Detach")

        self.detach_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.detach_btn.setToolTip("Open the front layer table in a separate floating window.")

        self.detach_btn.clicked.connect(self.detach_front_table)

        f_head.addWidget(self.detach_btn)

        f_head.addWidget(self.layer_count_label)

        f_lay.addLayout(f_head)

        self.front_table = ExcelTableWidget()

        self.front_table.setColumnCount(5)

        self.front_table.setRowCount(0)

        self.front_table.setHorizontalHeaderLabels(["#", "Mat", "n@lambda₀", "QWOT", "Thick(nm)"])

        header = self.front_table.horizontalHeader()

        self.front_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.front_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        for idx, width in enumerate((26, 52, 54, 72, 78)):
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

        # No Add/Remove/Undo here: reserved for CERTUS_DESIGN (stack edited via Excel / RE file).

        self.front_tabs.addTab(self.front_container, "Layers")

        return self.front_tabs

    def _build_target_table_widget(self) -> QWidget:
        """Constructs spectral targets table widget"""

        tgt_widget = QWidget()

        t_lay = QVBoxLayout(tgt_widget)

        t_lay.addWidget(QLabel("<b>Spectral targets</b>"))

        # Table with adaptive columns by mode

        self.target_table = ExcelTableWidget()

        self.target_table.setColumnCount(6)

        self.target_table.setRowCount(0)

        self._update_target_table_headers()

        self.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.target_table.setAlternatingRowColors(True)

        t_lay.addWidget(self.target_table)

        return tgt_widget

    def _update_target_table_headers(self):
        """RE oblique table without Val min/max (spectral targets are _re_targets points from the file)."""

        if getattr(self, "oblique_mode", False):
            self.target_table.setColumnCount(7)

            self.target_table.setHorizontalHeaderLabels(
                [
                    "Active",
                    "Angle()",
                    "Pol",
                    "Type",
                    "lambdamin",
                    "lambdamax",
                    "Weight",
                ]
            )

        else:
            super()._update_target_table_headers()

    def _build_status_bar(self):
        """Constructs status bar"""

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.best_rmse_label = QLabel("Best RMSE:  N/A")

        self.best_rmse_label.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-weight: bold; padding-left: 15px; padding-right: 15px;"
        )

        self.status_label = CertusStatusPill("Ready", "ready")

        self.stats_label = QLabel("Evals: 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.progress_widget = EnhancedProgressWidget()

        self.log_btn = QPushButton("Show Details")

        self.log_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.log_btn.setToolTip("Toggle log panel and detail view.")

        self.log_btn.setCheckable(True)

        self.log_btn.setChecked(False)

        self.log_btn.clicked.connect(self.toggle_logs)

        self.log_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")

        self.status_bar.addWidget(self.log_btn)

        self.status_bar.addWidget(self.status_label)

        self.status_bar.addPermanentWidget(self.stats_label)

        self.status_bar.addPermanentWidget(self.best_rmse_label)

        self.status_bar.addPermanentWidget(self.progress_widget)

    # =========================================================================

    # HELPERS UI

    # =========================================================================

    def _setup_shortcuts(self):
        """Configures keyboard shortcuts"""

        QShortcut(QKeySequence("Ctrl+E"), self, lambda: self._schedule_eval(True))

        install_standard_shortcuts(
            self,
            save=getattr(self, "save_config", None),
            load=getattr(self, "load_config", None),
            export=self.export_excel,
            run=self.run_eval,
            stop=self.stop_optim,
            help=self.open_help,
            extra={"Ctrl+L": self.toggle_logs},
        )

        def _on_re_drop(paths):
            if paths and hasattr(self, "load_reverse_engineering_from_path"):
                self.load_reverse_engineering_from_path(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_re_drop, extensions=("xlsx", "xls", "csv"))

    # =========================================================================

    # LAYER MANAGEMENT

    # =========================================================================

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox):
        """RE specific: no extra connections."""

        pass

    def _on_layer_added(self):
        """RE specific: no extra actions."""

        # RE layers are usually loaded from Excel, but manual add is now possible.

        pass

    def _on_layer_deleted(self):
        """RE specific: no extra actions."""

        pass

    def _update_layer_count(self):

        super()._update_layer_count()

        self._re_refresh_front_table_num_and_n()

    def _re_parse_thick_nm_from_table(self, row: int) -> float | None:
        """Read thickness (nm) shown in the Thick column."""

        it = self.front_table.item(row, _RE_FT_COL_THICK)

        if it is None:
            return None

        s = (it.text() or "").strip().replace(",", ".")

        if not s or s.upper() == "N/A":
            return None

        try:
            d = float(s)

        except ValueError:
            return None

        return d if np.isfinite(d) and d > 1e-9 else None

    def _re_n_from_qwot_and_thick(self, qwot: float, d_nm: float, l0: float) -> float | None:
        """n at lambda0 from QWOT = 4 n d / lambda0  =>  n = QWOT*lambda0 / (4d)."""

        if not np.isfinite(qwot) or not np.isfinite(d_nm) or not np.isfinite(l0) or abs(l0) < 1e-9 or d_nm < 1e-9:
            return None

        n_est = (float(qwot) * float(l0)) / (4.0 * float(d_nm))

        return n_est if np.isfinite(n_est) and n_est > 0 else None

    def _re_refresh_front_table_num_and_n(self) -> None:
        """Layer index (1...) and Re(n) at lambda0 (3 decimals) for each row."""

        if not hasattr(self, "front_table") or self.front_table.columnCount() < 5:
            return

        mats = self._get_materials()

        l0 = float(self.l0_spin.value()) if hasattr(self, "l0_spin") else float(getattr(self, "_re_lambda_ref", 500.0))

        wls = np.array([l0], dtype=np.float64)

        for r in range(self.front_table.rowCount()):
            num_it = self.front_table.item(r, _RE_FT_COL_NUM)

            if num_it is None:
                num_it = QTableWidgetItem()

                num_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                num_it.setFlags(num_it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.front_table.setItem(r, _RE_FT_COL_NUM, num_it)

            num_it.setText(str(r + 1))

            n_it = self.front_table.item(r, _RE_FT_COL_N)

            if n_it is None:
                n_it = QTableWidgetItem()

                n_it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                n_it.setFlags(n_it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.front_table.setItem(r, _RE_FT_COL_N, n_it)

            mat = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

            nr = float("nan")

            n_src = ""

            if mat and mats and mat in mats:
                try:
                    nk = mats[mat].get_nk(wls)

                    nr = float(np.real(np.asarray(nk, dtype=np.complex128).ravel()[0]))

                    n_src = "Tabulated n(lambda₀)"

                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
                    nr = float("nan")

            if not np.isfinite(nr):
                sb = self.front_table.cellWidget(r, _RE_FT_COL_QW)

                qw = float(sb.value()) if sb and hasattr(sb, "value") else float("nan")

                d_nm = self._re_parse_thick_nm_from_table(r)

                if d_nm is not None:
                    n_alt = self._re_n_from_qwot_and_thick(qw, d_nm, l0)

                    if n_alt is not None:
                        nr = float(n_alt)

                        n_src = "QWOT & thickness (n = QWOTlambda₀/(4d))"

            if np.isfinite(nr):
                n_it.setText(f"{nr:.3f}")

            else:
                n_it.setText("")

                n_src = ""

            tip = f"Layer #{r + 1}  lambda₀ = {l0:.1f} nm"

            if mat:
                tip += f"  material {mat}"

            if n_src:
                tip += f"  {n_src}"

            n_it.setToolTip(tip)

    def _merge_adjacent_layers(self):
        """Same logic as base class; Mat / QWOT columns at 1 and 3 (RE 5-column table)."""

        merged = False

        passes = 0

        c_m, c_q = _RE_FT_COL_MAT, _RE_FT_COL_QW

        while passes < 10:
            passes += 1

            found = False

            i = 1

            while i < self.front_table.rowCount():
                m_curr = self._safe_get_combo_text(i, c_m)

                m_prev = self._safe_get_combo_text(i - 1, c_m)

                if m_curr and m_prev and m_curr == m_prev:
                    try:
                        q_curr = self.front_table.cellWidget(i, c_q).value()

                        sp_prev = self.front_table.cellWidget(i - 1, c_q)

                        sp_prev.blockSignals(True)

                        sp_prev.setValue(sp_prev.value() + q_curr)

                        sp_prev.blockSignals(False)

                        self.front_table.removeRow(i)

                        merged = True

                        found = True

                        self.log(f"Merged adjacent layers ({m_curr})", "INFO")

                        continue

                    except (
                        ValueError,
                        TypeError,
                        RuntimeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        FileNotFoundError,
                    ) as e:
                        if hasattr(self, "logger") and self.logger:
                            self.logger.error(f"Merge error: {e}")

                i += 1

            if not found:
                break

        self._update_layer_count()

        if merged:
            self._schedule_eval()

    def _update_thickness_display(self):
        """Physical thickness: column Thick(nm) = index 4 (RE table)."""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        stack = self._get_front_stack()

        if stack and mats:
            ep = init_thickness(stack, l0, mats)

            if ep is not None:
                for r, d in enumerate(ep):
                    it = self.front_table.item(r, _RE_FT_COL_THICK)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_current = ep

                self._on_front_thickness_updated()

        self._re_refresh_front_table_num_and_n()

    def _update_qwot_from_ep(self, ep):
        """QWOT in column 3 (RE table)."""

        self.front_table.blockSignals(True)

        ep = np.asarray(ep, dtype=float).ravel()

        for r in range(min(len(ep), self.front_table.rowCount())):
            mat_name = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

            qw_val = self._ep_nm_to_qwot(ep[r], mat_name)

            sb = self.front_table.cellWidget(r, _RE_FT_COL_QW)

            if sb:
                sb.setValue(qw_val)

        self.front_table.blockSignals(False)

    def _add_front_row(self, mat: str, qwot: float, var: bool, del_checked: bool = False):
        """RE: no Var/Del columns (thicknesses driven by RE file / optimization)."""

        del var, del_checked

        row = self.front_table.rowCount()

        self.front_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._merge_adjacent_layers)

        self.front_table.setCellWidget(row, _RE_FT_COL_MAT, cb)

        sb = self._create_spin(qwot, dec=4)

        sb.valueChanged.connect(self._on_schedule_eval_signal)

        self._on_qwot_changed_connection(sb)

        self.front_table.setCellWidget(row, _RE_FT_COL_QW, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(row, _RE_FT_COL_THICK, it)

        self._update_layer_count()

    def _get_front_stack(self) -> list[Layer]:
        """RE: all front-table layers are active in the model (equivalent to Var=True)."""

        try:
            stack: list[Layer] = []

            for r in range(self.front_table.rowCount()):
                mat = self._safe_get_combo_text(r, _RE_FT_COL_MAT)

                if not mat:
                    continue

                qw = self.front_table.cellWidget(r, _RE_FT_COL_QW).value()

                stack.append(Layer(mat, qw, True))

            return stack

        except (AttributeError, ValueError, IndexError) as e:
            logging.debug(f"Could not get front stack: {e}")

            return []

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """RE specific plot info mapping."""

        if widget == self.spectrum_plot:
            return "spectrum", "Spectrum (T)"

        elif widget == self.profile_plot:
            return "profile", "Refractive Index Profile"

        elif widget == self.nk_plot:
            return "nk", "Dispersion n(lambda)"

        return None

    def _paste_from_excel(self):
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

                rows_data.append((mat, qwot))

            if not rows_data:
                self.log("No valid data to paste", "WARNING")

                return

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

            for i, (mat, qwot) in enumerate(rows_data):
                row = start_row + i

                if row >= self.front_table.rowCount():
                    self._add_front_row(mat, qwot, True)

                else:
                    cb = self._create_combo(mat)

                    cb.currentIndexChanged.connect(self._merge_adjacent_layers)

                    self.front_table.setCellWidget(row, _RE_FT_COL_MAT, cb)

                    sb = self._create_spin(qwot, dec=4)

                    sb.valueChanged.connect(self._on_schedule_eval_signal)

                    self.front_table.setCellWidget(row, _RE_FT_COL_QW, sb)

                    it = self.front_table.item(row, _RE_FT_COL_THICK)

                    if it is None:
                        it = QTableWidgetItem("N/A")

                        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        self.front_table.setItem(row, _RE_FT_COL_THICK, it)

                    else:
                        it.setText("N/A")

            self.front_table.blockSignals(False)

            self._update_layer_count()

            self._schedule_eval()

            self.log(f"{len(rows_data)} row(s) pasted from Excel", "SUCCESS")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.log(f"Paste error: {str(e)}", "ERROR")

            traceback.print_exc()

    # =========================================================================

    # TARGET MANAGEMENT

    # =========================================================================

    def _re_default_target_lmin_lmax_nm(self) -> tuple[float, float]:
        """Default lambda min/max for spectral targets, centered on lambda0 (no hard-coded fixed lambda pairs)."""

        l0 = float(self._stack_info_l0_nm())

        return (max(200.0, l0 - 100.0), min(20000.0, l0 + 200.0))

    def _re_fallback_plot_wavelengths_nm(self, n: int = 200) -> np.ndarray:
        """Lambda grid for RE plots when no target is active; span derived from lambda0."""

        lr = float(self._stack_info_l0_nm())

        lo = max(200.0, lr - 100.0)

        hi = min(20000.0, max(lr + 200.0, lr * 5.0))

        return np.linspace(lo, hi, int(n), dtype=np.float64)

    def add_target(self):
        """Adds spectral target"""

        r = self.target_table.rowCount()

        self.target_table.insertRow(r)

        col_idx = 0

        # Active Checkbox

        chk = QCheckBox()

        chk.setToolTip("Enable or disable this target.")

        chk.setChecked(True)

        chk.stateChanged.connect(self._schedule_eval)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.target_table.setCellWidget(r, col_idx, cw)

        col_idx += 1

        if self.oblique_mode:
            # Oblique: Ang, Pol, Type, lmin, lmax, Weight (no Val min/max: RE = _re_targets points)

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

            _tl0, _th0 = self._re_default_target_lmin_lmax_nm()

            for val, dec, tt in (
                (_tl0, 1, "Target wavelength range start (nm)."),
                (_th0, 1, "Target wavelength range end (nm)."),
            ):
                sb = self._create_spin(val, dec=dec, minv=200, maxv=20000)

                sb.setToolTip(tt)

                sb.valueChanged.connect(self._schedule_eval)

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

            w_sb = self._create_spin(1.0, dec=1, minv=0, maxv=100)

            w_sb.setToolTip(
                "Weight (manual row without RE file). With an RE file, the fit uses the spectral "
                "points from the workbook, not this column."
            )

            w_sb.valueChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, w_sb)

            col_idx += 1

        else:
            # Normal Mode: lmin, lmax, Tmin, Tmax, Weight

            _nl0, _nh0 = self._re_default_target_lmin_lmax_nm()

            defs = [_nl0, _nh0, 0.0, 0.5, 1.0]

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

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

    def _get_optim_wls(self) -> np.ndarray:
        """Single lambda grid for RMSE / spectral cost (union of active targets)."""

        if self.oblique_mode:
            tgts = self._get_oblique_tgts()

        else:
            tgts = self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            return np.array([])

        wls_list = []

        n_points = RE_OPTIM_POINTS_PER_TARGET

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

    # =========================================================================

    # GETTERS

    # =========================================================================

    def _get_materials(self) -> dict:
        """Tabular H/L/substrate materials after loading the RE Excel file only."""

        if not getattr(self, "_re_loaded", False):
            return {}

        try:
            result = {}

            for key, attr in (
                ("H", "_re_tabular_H"),
                ("L", "_re_tabular_L"),
                ("Substrate", "_re_tabular_Sub"),
            ):
                tab = getattr(self, attr, None)

                if tab is not None:
                    result[key] = tab

            return result

        except (AttributeError, KeyError) as e:
            logging.debug(f"Could not get materials: {e}")

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        # RE: files loaded -> measurement targets (even if oblique UI checkbox is off).

        if getattr(self, "_re_loaded", False) and self._re_targets:
            return self._re_filter_targets_by_fit_window([t for t in self._re_targets if t.on])

        if not self.oblique_mode:
            return []  # Else normal mode: _get_tgts()

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

                _dl0, _dh0 = self._re_default_target_lmin_lmax_nm()

                lmin = lmin_w.value() if lmin_w else _dl0

                lmax = lmax_w.value() if lmax_w else _dh0

                weight_w = self.target_table.cellWidget(r, 6)

                weight = weight_w.value() if weight_w else 1.0

                targets.append(
                    ObliqueTarget(
                        angle=angle,
                        pol=polarization,
                        target_type=target_type,
                        lmin=lmin,
                        lmax=lmax,
                        tmin=0.5,
                        tmax=0.5,
                        w=weight,
                        on=active,
                        include_backside=True,
                    )
                )

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug(f"Could not get oblique target row: {e}")

        return targets

    def _on_re_worker_progress(self, pct: int, msg: str):
        """Synchronizes REWorker progress -> LOGS panel + progress widget."""

        if not msg:
            return

        self.log(msg, "INFO")

        if getattr(self, "_re_mode_active", False):
            _rp = _parse_re_rmse_combined_from_progress_message(msg)

            if _rp is not None:
                self._apply_re_workflow_rmse_if_better(_rp)

        pw = getattr(self, "progress_widget", None)

        if pw is None:
            return

        try:
            pw.progress_bar.setValue(max(0, min(100, int(pct))))

            short = msg if len(msg) <= 160 else (msg[:157] + "...")

            pw.info_label.setText(short)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            pass

    def _apply_re_workflow_rmse_if_better(self, r: float) -> None:
        """Update _workflow_best_rmse (RE RMSE) and refresh the status bar."""

        if not self._is_valid_rmse_value(r):
            return

        rf = float(r)

        prev = float(getattr(self, "_workflow_best_rmse", float("inf")))

        if rf < prev - 1e-15:
            self._workflow_best_rmse = rf

            self._update_status_bar_stats()

    def _re_rmse_qwot_alpha_for_display(self) -> float:
        """alpha for √(sp²+alpha·QWOT²) : last RE run (phase 2b) if known, else speed preset."""

        r = getattr(self, "_re_rmse_qwot_alpha_ref", None)

        if r is not None:
            try:
                rf = float(r)

            except (TypeError, ValueError):
                rf = float("nan")

            if np.isfinite(rf) and rf >= 0.0:
                return rf

        return self._re_gui_qwot_penalty_weight()

    def _on_re_worker_result(self, data: object) -> None:
        """Update  Best RMSE  during RE (live emissions, previously not wired)."""

        if not getattr(self, "_re_mode_active", False):
            return

        if not isinstance(data, dict):
            return

        if data.get("type") != "intermediate":
            return

        al = data.get("alpha_qwot")

        if al is not None:
            try:
                al_f = float(al)

            except (TypeError, ValueError):
                al_f = float("nan")

            if np.isfinite(al_f):
                prev = getattr(self, "_re_last_live_alpha_qwot", None)

                if prev is not None and abs(al_f - float(prev)) > 1e-12:
                    self._workflow_best_rmse = float("inf")

                self._re_last_live_alpha_qwot = al_f

        rmse = data.get("rmse")

        if not self._is_valid_rmse_value(rmse):
            return

        self._apply_re_workflow_rmse_if_better(float(rmse))

        if "re_nk_preview_dH" in data:
            self._re_nk_preview_dH = data.get("re_nk_preview_dH")

            self._re_nk_preview_dL = data.get("re_nk_preview_dL")

            self._re_nk_preview_lam2 = data.get("re_nk_preview_lam2")

            self._re_nk_preview_sub012 = data.get("re_nk_preview_sub012")

            self._plot_nk()

    def _update_status_bar_stats(self):
        """Status bar: Evals (GUI evals + cumulative RE nfev) and best known RMSE."""

        if hasattr(self, "stats_label"):
            total = int(self.accumulated_evals) + int(getattr(self, "_re_nfev_cumulative", 0))

            self.stats_label.setText(f"Evals: {total}")

        if hasattr(self, "best_rmse_label"):
            be = float(getattr(self, "_best_eval_rmse", float("inf")))

            wf = float(getattr(self, "_workflow_best_rmse", float("inf")))

            # During RE: show best RMSE for *this* run (else min(eval, wf)

            # stuck on an old GUI eval better than the current iteration).

            if getattr(self, "_re_mode_active", False):
                if np.isfinite(wf) and wf < float("inf"):
                    self.best_rmse_label.setText(f"Best RMSE: {wf:.6f}")

                elif np.isfinite(be) and be < float("inf"):
                    self.best_rmse_label.setText(f"Best RMSE: {be:.6f}")

                else:
                    self.best_rmse_label.setText("Best RMSE:  N/A")

            else:
                candidates: list[float] = []

                if np.isfinite(be) and be < float("inf"):
                    candidates.append(be)

                if np.isfinite(wf) and wf < float("inf"):
                    candidates.append(wf)

                if candidates:
                    self.best_rmse_label.setText(f"Best RMSE: {min(candidates):.6f}")

                else:
                    self.best_rmse_label.setText("Best RMSE:  N/A")

    # =========================================================================

    # EVALUATION

    # =========================================================================

    def run_eval(self):
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

        cfg = spectrum_eval_build_worker_cfg(self, "re")

        if cfg is None:
            return

        spectrum_eval_start_worker(self, cfg, _eval_start)

    def _on_eval_finished(self, data: Dict, generation_id: int | None = None):
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

        self.accumulated_evals += 1

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

        if (rmse is None or not np.isfinite(rmse)) and oblique_mode and getattr(self, "_re_loaded", False):
            rmse = self._compute_re_rmse(
                float(getattr(self, "_re_opt_a_pct", 0.0)),
                float(getattr(self, "_re_opt_b_pct", 0.0)),
                float(getattr(self, "_re_opt_f_pct", 0.0)),
            )

            data_for_display["rmse"] = rmse

        if self._is_valid_rmse_value(data_for_display.get("rmse")):
            self._store_best_eval_snapshot(data_for_display)

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | {src_name} | RMSE grid: {n_total} lambda"

            else:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | RMSE grid: {n_total} lambda"

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            title = f"Spectrum ({self.front_table.rowCount()} layers) | RMSE grid: {n_total} lambda"

        if rmse is not None and np.isfinite(rmse) and rmse >= 0.0:
            title += f" - RMSE: {rmse:.6f}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self, res_vis=res_vis, oblique_mode=oblique_mode)

        self._plot_profile(
            data_for_display["ep"],
            self._get_front_stack(),
        )

        self._plot_nk()

        logging.info(f"[EVAL] _on_eval_finished complete in {(time.time() - _finish_start) * 1000:.1f}ms")

        self._update_status_bar_stats()

        _dt_ms = (time.time() - _finish_start) * 1000.0

        _tags: list[str] = []

        if oblique_mode:
            _tags.append("oblique")

        if self.back_check.isChecked():
            _tags.append("back face")

        _tag_s = f" ({', '.join(_tags)})" if _tags else ""

        if rmse is not None and np.isfinite(rmse) and rmse >= 0.0:
            self.log(
                f"Evaluation OK{_tag_s}  {_dt_ms:.0f} ms, RMSE grid {n_total} lambda, RMSE={rmse:.6f}",
                "SUCCESS",
            )

        else:
            self.log(
                f"Evaluation OK{_tag_s}  {_dt_ms:.0f} ms, RMSE grid {n_total} lambda.",
                "SUCCESS",
            )

        self._set_busy(False)

        logging.info("[EVAL] === Evaluation cycle complete, UI ready ===")

    def _plot_profile(
        self,
        ep: np.ndarray,
        stack: list[Layer],
    ):
        """Update n,k display in spectrum widget."""

        # ... logic ...

        """Refractive index profile (front side only  RE without rear coating)."""

        for plot_widget in self._get_plot_targets("profile", self.profile_plot):
            plot_widget.plotItem.clear()

            mats = self._get_materials()

            if "Substrate" not in mats:
                continue

            ns = mats["Substrate"].n4

            x, y = [0.0, 0.0], [ns, mats[stack[0].mat].n4] if stack else [ns, 1.0]

            if ep is not None and len(ep) > 0:
                cs = np.cumsum(ep)

                n_vals = [mats[l.mat].n4 for l in stack]

                # Protection against index out of bounds (oblique mode may have more thicknesses than layers)

                n_layers = min(len(ep) - 1, len(n_vals) - 1)

                for i in range(n_layers):
                    x.extend([cs[i], cs[i]])

                    y.extend([n_vals[i], n_vals[i + 1]])

                if n_vals:
                    x.extend([cs[-1], cs[-1], cs[-1] + max(50.0, 0.1 * cs[-1])])

                    y.extend([n_vals[-1], 1.0, 1.0])

            else:
                x, y = [0.0, 50.0], [ns, 1.0]

            plot_widget.plot(
                x,
                y,
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                fillLevel=0,
                brush=(30, 58, 138, 30),
            )

    def _re_clear_re_nk_preview(self) -> None:
        """Reset n(lambda) preview synchronized with the RE worker."""

        self._re_nk_preview_dH = None

        self._re_nk_preview_dL = None

        self._re_nk_preview_lam2 = None

        self._re_nk_preview_sub012 = None

    def _plot_nk(self):
        """n(lambda) curves. If RE loaded: extended range; dashed = corrected Re (DeltaRe splines or drift %)."""

        mats = self._get_materials()

        cols = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ACCENT,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.ERROR,
        ]

        re_loaded = getattr(self, "_re_loaded", False)

        re_busy = getattr(self, "_re_mode_active", False)

        if re_loaded and getattr(self, "_re_tabular_H", None) is not None:
            wf = np.asarray(self._re_tabular_H.wls_nm, dtype=np.float64)

            if wf.size >= 2:
                w_dense = np.linspace(float(wf[0]), float(wf[-1]), max(400, int(wf.size) * 4))

                w = np.unique(np.concatenate([wf, w_dense]))

            elif wf.size == 1:
                w = np.linspace(max(200.0, wf[0] - 200), wf[0] + 2000.0, 300)

            else:
                w = np.linspace(380.0, 5500.0, 600)

        elif re_loaded:
            w = np.linspace(380.0, 5500.0, 600)

        else:
            w = np.linspace(380.0, 1000.0, 400)

        a_gui = float(getattr(self, "_re_opt_a_pct", 0.0)) if re_loaded else 0.0

        b_gui = float(getattr(self, "_re_opt_b_pct", 0.0)) if re_loaded else 0.0

        _nksp = RE_SPLINE_N_KNOTS

        if re_busy:
            dH_st = getattr(self, "_re_nk_preview_dH", None)

            dL_st = getattr(self, "_re_nk_preview_dL", None)

            _lam2_pv = getattr(self, "_re_nk_preview_lam2", None)

            sub012_pv = getattr(self, "_re_nk_preview_sub012", None)

        else:
            dH_st = getattr(self, "_re_spline_dH", None)

            dL_st = getattr(self, "_re_spline_dL", None)

            _lam2_pv = getattr(self, "_re_spline_lam2_nm", None)

            sub012_pv = None

        use_sp = (
            re_loaded
            and dH_st is not None
            and dL_st is not None
            and len(np.asarray(dH_st).ravel()) == _nksp
            and len(np.asarray(dL_st).ravel()) == _nksp
        )

        if use_sp:
            dh_arr = np.asarray(dH_st, dtype=np.float64).ravel()

            dl_arr = np.asarray(dL_st, dtype=np.float64).ravel()

            show_renk_corr = re_loaded and (
                np.max(np.abs(dh_arr)) > 1e-12
                or np.max(np.abs(dl_arr)) > 1e-12
                or (sub012_pv is not None and len(sub012_pv) == 3 and max(abs(float(x)) for x in sub012_pv) > 1e-12)
            )

        else:
            show_renk_corr = re_loaded and (abs(a_gui) > 1e-12 or abs(b_gui) > 1e-12)

        for plot_widget in self._get_plot_targets("nk", self.nk_plot):
            plot_widget.plotItem.clear()

            for i, (k, m) in enumerate(mats.items()):
                n_nominal = m.get_nk(w).real

                plot_widget.plot(
                    w,
                    n_nominal,
                    pen=pg.mkPen(cols[i % len(cols)], width=2),
                    name=k,
                )

            if show_renk_corr:
                if use_sp:
                    _lam2_pl = float(_lam2_pv) if _lam2_pv is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

                    _kw_pl = re_knots_wavelengths(_lam2_pl)

                    _es_nk = self._re_envelope_scale_from_gui()

                    dHv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dH_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    dLv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dL_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            n_corr = m.get_nk(w).real + dHv

                        elif k == "L":
                            n_corr = m.get_nk(w).real + dLv

                        elif k == "Substrate":
                            lr = float(self.l0_spin.value())

                            if sub012_pv is not None and len(sub012_pv) == 3:
                                ths = np.asarray(sub012_pv, dtype=np.float64)

                            else:
                                _sa = getattr(self, "_re_sub_cauchy_a0", None)

                                _s1 = getattr(self, "_re_sub_cauchy_a1", None)

                                _s2 = getattr(self, "_re_sub_cauchy_a2", None)

                                if _sa is None or _s1 is None or _s2 is None:
                                    continue

                                ths = np.array(
                                    [float(_sa), float(_s1), float(_s2)],
                                    dtype=np.float64,
                                )

                            n_corr = re_substrate_cauchy_n_re_from_theta(w, lr, ths)

                        else:
                            continue

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

                else:
                    a_pct = a_gui

                    b_pct = b_gui

                    lambda_ref = float(self.l0_spin.value())

                    wls_drift_denom = max(5200.0 - lambda_ref, 1.0)

                    t = np.clip((w - lambda_ref) / wls_drift_denom, 0.0, None)

                    drift_factor = t**3

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            mult = 1.0 + (a_pct / 100.0) * drift_factor

                        elif k == "L":
                            mult = 1.0 + (b_pct / 100.0) * drift_factor

                        else:
                            continue

                        n_corr = m.get_nk(w).real * mult

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

    # =========================================================================

    # OPTIMIZATION

    # =========================================================================

    def stop_optim(self):
        """Stop spectral evaluation or the RE worker."""

        if not confirm_stop_with_timeout(self):
            return

        self._workflow_stopped = True

        self.log("Stop requested...", "WARNING")

        rw = getattr(self, "_re_worker", None)

        re_was_running = rw is not None and rw.isRunning()

        re_joined_ok = False

        if re_was_running:
            if hasattr(rw, "request_stop"):
                rw.request_stop()

            rw.requestInterruption()

            # Wait for cooperative finish: ``finished`` -> ``_on_re_done`` (best TRF known).

            re_joined_ok = rw.wait(300000)

            if not re_joined_ok:
                logging.critical(
                    "REWorker did not finish within timeout - skipping terminate() to avoid unsafe thread kill."
                )

                self.log("REWorker: stop timeout - skipping terminate() (see log).", "ERROR")

            self._re_worker = None

        if not re_joined_ok and getattr(self, "_re_mode_active", False):
            self._re_mode_active = False

            self._re_clear_re_nk_preview()

            self._plot_nk()

            if hasattr(self, "launch_re_btn"):
                self.launch_re_btn.setEnabled(True)

        if hasattr(self, "progress_widget") and (not re_was_running or not re_joined_ok):
            try:
                self.progress_widget.stop("Stopped by user")

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
                pass

        if self.eval_worker and self.eval_worker.isRunning():
            self.eval_worker.requestInterruption()

            self.eval_worker.wait(2000)

        self._force_idle()

        if not re_was_running or not re_joined_ok:
            self.log("Calculation stopped.", "WARNING")

    # =========================================================================

    # REVERSE ENGINEERING  LOAD & LAUNCH

    # =========================================================================

    def _reconstruct_lambda_list(self, raw: list) -> list:
        """Reconstruct a wavelength list from raw values, filling None gaps via step.

        Used by _parse_re_index and _parse_re_measurement.  The step is inferred

        from the first two cached (numeric) values found in *raw*.  If only one

        cached value exists the step defaults to 10 nm.

        """

        if not raw:
            return []

        first_val = None

        first_idx = 0

        step = None

        for i, v in enumerate(raw):
            if isinstance(v, (int, float)):
                if first_val is None:
                    first_val = float(v)

                    first_idx = i

                elif step is None:
                    step = float(v) - first_val

                    break

        if first_val is None:
            return []

        if step is None or abs(step) < 1e-9:
            step = 10.0

        result = []

        for i, v in enumerate(raw):
            if isinstance(v, (int, float)):
                result.append(float(v))

            else:
                result.append(first_val + (i - first_idx) * step)

        return result

    @staticmethod
    def _re_walk_up_indices_paths(start_dir: str | None, *, max_levels: int = 64) -> list[str]:
        """Common indices.xlsx locations in *start_dir* and each parent directory."""

        if not start_dir:
            return []

        d = Path(start_dir).resolve()

        out: list[str] = []

        for _ in range(max(1, int(max_levels))):
            out.append(str(d / "indices.xlsx"))

            out.append(str(d / "example" / "indices.xlsx"))

            out.append(str(d / "example" / "database_index" / "indices.xlsx"))

            parent = d.parent

            if parent == d:
                break

            d = parent

        return out

    def _re_indices_xlsx_candidate_paths(self, re_workbook_dir: str | None = None) -> list[str]:
        """Ordered search list for indices.xlsx with canonical DB-first policy."""

        cand: list[str] = []

        env = os.environ.get("CERTUS_INDICES_XLSX")

        if env:
            cand.append(str(Path(env.strip()).resolve()))

        root_app = Path(__file__).resolve().parent

        # Canonical location used by the whole CERTUS suite.

        cand.append(str(root_app / "example" / "database_index" / "indices.xlsx"))

        cand.extend(self._re_walk_up_indices_paths(re_workbook_dir))

        cand.append(str(Path(get_resource_path("indices.xlsx")).resolve()))

        cand.extend(self._re_walk_up_indices_paths(str(root_app)))

        try:
            cand.extend(self._re_walk_up_indices_paths(os.getcwd()))

        except (OSError, ValueError):
            pass

        seen: set[str] = set()

        out: list[str] = []

        for p in cand:
            ap = str(Path(p).resolve())

            if ap not in seen:
                seen.add(ap)

                out.append(ap)

        return out

    def _re_builtin_substrate_tabular(self, substrate_name: str, l0_ref: float) -> "TabularMaterial | None":
        """Last-resort tabular substrate when no indices.xlsx match (Silicon only)."""

        sub = substrate_name.lower().strip()

        if "sapphire" in sub:
            return None

        if "silicon" in sub or sub in ("si", "si-wafer") or sub.startswith("si ") or sub.startswith("si-"):
            from certus_physics.materials_data import SI_K_DATA, SI_N_DATA, SI_WAVELENGTH_NM

            return TabularMaterial(
                np.asarray(SI_WAVELENGTH_NM, dtype=np.float64),
                np.asarray(SI_N_DATA, dtype=np.float64),
                np.asarray(SI_K_DATA, dtype=np.float64),
                l0_ref=float(l0_ref),
            )

        return None

    def _load_re_substrate(
        self, substrate_name: str, l0_ref: float, *, re_workbook_dir: str | None = None
    ) -> "TabularMaterial | None":
        """Load substrate TabularMaterial from indices.xlsx by fuzzy-matching the sheet name."""

        import openpyxl as _opxl

        sub_lower = substrate_name.lower().strip()

        last_err: str | None = None

        for idx_path in self._re_indices_xlsx_candidate_paths(re_workbook_dir):
            if not Path(idx_path).is_file():
                continue

            try:
                wb = _opxl.load_workbook(idx_path, data_only=True)

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
                last_err = str(e)

                self.log(f"RE: could not open {idx_path}: {e}", "WARNING")

                continue

            matched = None

            for sh in wb.sheetnames:
                sh_lower = sh.lower()

                if (
                    sub_lower in sh_lower
                    or sh_lower.startswith(sub_lower)
                    or sh_lower.replace("-", " ").split()[0] in sub_lower
                    or (len(sub_lower) >= 3 and len(sh_lower) >= 3 and sub_lower[:3] == sh_lower[:3])
                ):
                    matched = sh

                    break

            if matched is None:
                self.log(
                    f"RE: substrate '{substrate_name}' not found in {idx_path!r} "
                    f"(sheets: {', '.join(wb.sheetnames[:8])}{'…' if len(wb.sheetnames) > 8 else ''}).",
                    "WARNING",
                )

                continue

            try:
                ws = wb[matched]

                rows = list(ws.iter_rows(values_only=True))

                data = [r for r in rows if r and isinstance(r[0], (int, float))]

                if not data:
                    self.log(f"RE: sheet {matched!r} in {idx_path!r} has no numeric rows.", "WARNING")

                    continue

                wls = np.array([float(r[0]) for r in data])

                n = np.array([float(r[1]) for r in data])

                k = np.array([float(r[2]) if len(r) > 2 and r[2] is not None else 0.0 for r in data])

                mat = TabularMaterial(wls, n, k, l0_ref=l0_ref)

                self._re_last_substrate_source_path = str(Path(idx_path).resolve())

                self._re_last_substrate_sheet = str(matched)

                self.log(
                    f"RE: substrate '{matched}' loaded from {idx_path}  n@{l0_ref:.0f}nm = {mat.n4:.4f}",
                    "INFO",
                )

                return mat

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
                last_err = str(e)

                self.log(f"RE: error reading substrate sheet in {idx_path}: {e}", "WARNING")

        fb = self._re_builtin_substrate_tabular(substrate_name, l0_ref)

        if fb is not None:
            self._re_last_substrate_source_path = "<builtin>"

            self._re_last_substrate_sheet = "silicon-stub/table"

            self.log(
                f"RE: indices.xlsx not usable ({last_err or 'no file matched'}); "
                f"using built-in Silicon (n,k) table for substrate '{substrate_name}'.",
                "WARNING",
            )

            self.log(
                f"RE: built-in substrate tabular  n@{l0_ref:.0f}nm = {fb.n4:.4f}",
                "INFO",
            )

            return fb

        self.log(
            "RE: could not load substrate: no indices.xlsx found "
            "(try CERTUS_INDICES_XLSX, place indices.xlsx in example/database_index/, "
            "or use a known substrate name with fallback data).",
            "WARNING",
        )

        return None

    def _parse_re_design(self, ws) -> tuple:
        """Parse 'design' sheet -> (lambda_ref_nm, substrate_name, qwot_list).

        Tolerant layout: lambda_ref and substrate anywhere on row 1; QWOT in the

        longest numeric column below (skips 1,2,3... row-index columns).

        """

        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            raise ValueError("'design' sheet is empty.")

        lambda_ref, substrate_name = _re_parse_design_metadata_row(tuple(rows[0]))

        qwot_list = _re_parse_design_qwot_rows(rows)

        if not qwot_list:
            raise ValueError("'design' sheet contains no QWOT values.")

        return lambda_ref, substrate_name, qwot_list

    def _parse_re_index(self, ws) -> tuple:
        """Parse 'index' sheet -> (wls, n1, k1, n2, k2) as numpy arrays.

        Accepts an optional header row (text labels). Column order may vary:

        wavelength is detected by header name or defaults to column A; the next

        four data columns (left-to-right) are n1,k1,n2,k2. Missing k columns

        default to zero; missing n to 1.5.

        """

        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            raise ValueError("'index' sheet is empty.")

        hdr, data_rows = _re_index_split_header_and_data(rows)

        if not data_rows:
            raise ValueError("'index' sheet has no data rows.")

        max_c = max((len(r) for r in data_rows if r), default=0)

        wl_i, i1, i2, i3, i4 = _re_index_column_map(hdr, max_c)

        compact: list[tuple] = []

        for row in data_rows:
            if not row or all(v is None for v in row):
                break

            compact.append(row)

        data_rows = compact

        n_rows = len(data_rows)

        if n_rows == 0:
            raise ValueError("'index' sheet: no numeric data found.")

        def _get(row: tuple, idx: int | None, default: float) -> float | None:

            if idx is None:
                return None

            if len(row) <= idx:
                return None

            v = row[idx]

            if v is None:
                return None

            try:
                return float(v)

            except (TypeError, ValueError):
                return None

        raw_wls: list = []

        for row in data_rows:
            raw_wls.append(_get(row, wl_i, 0.0))

        wls_arr = np.array(self._reconstruct_lambda_list(raw_wls))

        if len(wls_arr) == 0:
            raise ValueError("'index' sheet: could not reconstruct wavelength column.")

        n_rows = min(n_rows, len(wls_arr))

        def _col_arr(col_idx: int | None, default: float) -> np.ndarray:

            if col_idx is None:
                return np.full(n_rows, default, dtype=np.float64)

            out = np.empty(n_rows, dtype=np.float64)

            for i in range(n_rows):
                v = _get(data_rows[i], col_idx, default)

                out[i] = default if v is None else v

            return out

        n1 = _col_arr(i1, 1.5)

        k1 = _col_arr(i2, 0.0)

        n2 = _col_arr(i3, 1.5)

        k2 = _col_arr(i4, 0.0)

        return wls_arr[:n_rows], n1, k1, n2, k2

    def _parse_re_measurement(self, ws) -> tuple[np.ndarray, list[tuple[ParsedREColumn, np.ndarray]], list[str]]:
        """Parse the *measurement* sheet -> ``(wls, spectra_columns, user_warnings)``.

        ``spectra_columns``: list of ``(ParsedREColumn, ndarray)`` as **fractions**.

        The lambda column is found by header or heuristic; spectral labels via

        `parse_re_column_header` (`interpretation_notes` if uncertain).

        Values taken as **percent** if magnitudes exceed ~1.25.

        """

        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            raise ValueError("'measurement' sheet is empty.")

        header = rows[0]

        if not header:
            raise ValueError("'measurement' sheet: empty header row.")

        data_rows: list[tuple] = []

        for row in rows[1:]:
            if not row or all(v is None for v in row):
                break

            data_rows.append(row)

        n_rows = len(data_rows)

        if n_rows == 0:
            raise ValueError("'measurement' sheet: no numeric data found.")

        n_header_cols = len(header)

        header_user_notes: list[str] = []

        wl_col, wl_ambiguity = _re_find_measurement_wavelength_column(tuple(header), data_rows)

        if wl_ambiguity:
            header_user_notes.append(wl_ambiguity)

            self.log(f"RE measurement: {wl_ambiguity}", "WARNING")

        col_specs: list[tuple[int, ParsedREColumn]] = []

        for i in range(n_header_cols):
            if i == wl_col:
                continue

            h = header[i] if i < len(header) else None

            if h is None:
                continue

            hs = _re_cell_str(h)

            if not hs:
                continue

            if _re_header_is_wavelength_label(hs):
                continue

            # guard: never treat a wavelength label as a spectrum column

            hsl = hs.lower()

            if "wavelength" in hsl or "longueur" in hsl:
                continue

            try:
                spec = parse_re_column_header(str(h))

            except ValueError as e:
                if _re_header_looks_like_spectrum_title(hs):
                    self.log(f"RE measurement: skip column {i} ({hs!r}): {e}", "WARNING")

                continue

            col_specs.append((i, spec))

            for note in spec.interpretation_notes:
                msg = f"Spectral column {i} ( {spec.raw_header} ): {note}"

                header_user_notes.append(msg)

                self.log(f"RE measurement: {msg}", "WARNING")

        if not col_specs:
            raise ValueError("'measurement' sheet: no usable spectral column (need R/T-style headers).")

        wl_lbl = _re_cell_str(header[wl_col]) if wl_col < len(header) and header[wl_col] is not None else "?"

        self.log(
            f"RE measurement: lambda column index={wl_col} ({wl_lbl!r}), {len(col_specs)} spectral channel(s).",
            "INFO",
        )

        raw_wls: list = []

        for row in data_rows:
            if len(row) > wl_col:
                raw_wls.append(row[wl_col])

            else:
                raw_wls.append(None)

        wls_arr = np.array(self._reconstruct_lambda_list(raw_wls))

        if len(wls_arr) == 0:
            raise ValueError("'measurement' sheet: could not reconstruct wavelength column.")

        n_rows = min(n_rows, len(wls_arr))

        spectra_columns: list[tuple[ParsedREColumn, np.ndarray]] = []

        for col_idx, spec in col_specs:
            raw_nums: list[float] = []

            for i in range(n_rows):
                row = data_rows[i]

                if len(row) <= col_idx:
                    raw_nums.append(np.nan)

                    continue

                v = row[col_idx]

                raw_nums.append(float(v) if isinstance(v, (int, float)) else np.nan)

            use_pct = _re_measurement_values_are_percent(raw_nums)

            out: list[float] = []

            for x in raw_nums:
                if not np.isfinite(x):
                    out.append(np.nan)

                else:
                    out.append(x / 100.0 if use_pct else x)

            if use_pct:
                self.log(
                    f"RE measurement: column {col_idx} ({spec.raw_header}) interpreted as **percent** -> scale /100.",
                    "INFO",
                )

            spectra_columns.append((spec, np.asarray(out, dtype=np.float64)))

        return (
            np.asarray(wls_arr[:n_rows], dtype=np.float64),
            spectra_columns,
            header_user_notes,
        )

    def _re_automap_three_sheet_workbook(self, wb) -> dict[str, str]:
        """Infer measurement / design / index when the workbook has exactly three sheets.

        Tries all sheet permutations (six) and keeps the first that parses without error.

        Used when titles are generic (e.g. *Sheet1*, *Feuil1*) or synonyms collide.

        """

        from itertools import permutations

        names = list(wb.sheetnames)

        if len(names) != 3:
            return {}

        keys = ("measurement", "design", "index")

        for perm in permutations(names, 3):
            trial = dict(zip(keys, perm))

            try:
                _lambda_ref, _sub, qwot = self._parse_re_design(wb[trial["design"]])

                if not qwot:
                    continue

                wls_idx, *_rest = self._parse_re_index(wb[trial["index"]])

                if len(wls_idx) < 2:
                    continue

                wls_meas, specs, _warn = self._parse_re_measurement(wb[trial["measurement"]])

                if not specs or len(wls_meas) < 2:
                    continue

            except (ValueError, TypeError, KeyError):
                continue

            return trial

        return {}

    def _re_build_load_summary_text(
        self,
        *,
        file_path: str,
        workbook_sheetnames: list[str],
        sheet_map: dict[str, str],
        lambda_ref: float,
        substrate_name: str,
        qwot_list: list[float],
        wls_idx: np.ndarray,
        wls_meas: np.ndarray,
        spectra_columns: list[tuple[ParsedREColumn, np.ndarray]],
        header_warnings: list[str],
        need_back: bool,
    ) -> str:
        """Human-readable RE load summary (metadata only, no raw spectral arrays)."""

        lines: list[str] = []

        def _push(msg: str, *, suspicious: bool = False) -> None:

            lines.append(f"!! {msg}" if suspicious else msg)

        lines.append("RE workbook interpretation summary")

        lines.append("")

        _push(f"File: {Path(file_path).resolve()}")

        _push(f"Workbook sheets ({len(workbook_sheetnames)}): {', '.join(workbook_sheetnames)}")

        _push(
            "Resolved sheets: "
            f"measurement='{sheet_map.get('measurement', '?')}', "
            f"design='{sheet_map.get('design', '?')}', "
            f"index='{sheet_map.get('index', '?')}'"
        )

        lines.append("")

        lines.append("Design")

        _push(
            f"- lambda_ref: {float(lambda_ref):.3f} nm",
            suspicious=not (200.0 <= float(lambda_ref) <= 10000.0),
        )

        _push(f"- substrate (from workbook): '{substrate_name}'")

        _push(f"- layers (QWOT entries): {len(qwot_list)}", suspicious=len(qwot_list) <= 0)

        if len(qwot_list) > 0:
            q = np.asarray(qwot_list, dtype=np.float64).ravel()

            qv = q[np.isfinite(q)]

            if qv.size > 0:
                qmin = float(np.min(qv))

                qmax = float(np.max(qv))

                _push(
                    f"- QWOT range: [{qmin:.4f}, {qmax:.4f}]",
                    suspicious=(qmin <= 0.0 or qmax > 25.0),
                )

        lines.append("")

        lines.append("Index")

        _push(f"- points: {int(len(wls_idx))}", suspicious=int(len(wls_idx)) < 20)

        if len(wls_idx) > 0:
            wi = np.asarray(wls_idx, dtype=np.float64).ravel()

            wiv = wi[np.isfinite(wi)]

            if wiv.size > 0:
                wmin_i = float(np.min(wiv))

                wmax_i = float(np.max(wiv))

                _push(
                    f"- wavelength range: [{wmin_i:.1f}, {wmax_i:.1f}] nm",
                    suspicious=(wmax_i <= wmin_i or (wmax_i - wmin_i) < 50.0),
                )

        nH = float(getattr(self._re_tabular_H, "n4", np.nan))

        nL = float(getattr(self._re_tabular_L, "n4", np.nan))

        _push(
            f"- H/L n@lambda_ref: {nH:.4f} / {nL:.4f}",
            suspicious=(not (1.0 <= nH <= 5.0) or not (1.0 <= nL <= 5.0)),
        )

        if getattr(self, "_re_tabular_Sub", None) is not None:
            sub_n4 = float(getattr(self._re_tabular_Sub, "n4", np.nan))

            src = getattr(self, "_re_last_substrate_source_path", None)

            sh = getattr(self, "_re_last_substrate_sheet", None)

            if src and sh:
                _push(
                    f"- Substrate loaded: yes ({sh} from {src}), n@lambda_ref={sub_n4:.4f}",
                    suspicious=not np.isfinite(sub_n4),
                )

            else:
                _push(
                    f"- Substrate loaded: yes, n@lambda_ref={sub_n4:.4f}",
                    suspicious=not np.isfinite(sub_n4),
                )

        else:
            _push(
                "- Substrate loaded: no (RE cannot optimize without a substrate model)",
                suspicious=True,
            )

        lines.append("")

        lines.append("Measurement")

        _push(f"- channels: {len(spectra_columns)}", suspicious=len(spectra_columns) <= 0)

        _push(f"- backside model required: {'yes' if need_back else 'no'}")

        if len(wls_meas) > 0:
            wm = np.asarray(wls_meas, dtype=np.float64).ravel()

            wmv = wm[np.isfinite(wm)]

            if wmv.size > 0:
                wmin_m = float(np.min(wmv))

                wmax_m = float(np.max(wmv))

                _push(
                    f"- wavelength range: [{wmin_m:.1f}, {wmax_m:.1f}] nm",
                    suspicious=(wmax_m <= wmin_m or (wmax_m - wmin_m) < 50.0),
                )

                npts = int(np.sum(np.isfinite(np.concatenate([v for _, v in spectra_columns]))))

                _push(f"- active target points generated: {npts}", suspicious=npts < 20)

        for i, (spec, vals) in enumerate(spectra_columns, start=1):
            n_pts = int(np.sum(np.isfinite(vals)))

            _push(
                f"  {i}. {spec.raw_header} -> {spec.target_type}, angle={spec.angle_deg:.1f}, "
                f"pol={spec.pol}, back={'on' if spec.include_backside else 'off'}, points={n_pts}",
                suspicious=(n_pts < 5),
            )

            for note in spec.interpretation_notes:
                _push(f"     note: {note}", suspicious=True)

        lines.append("")

        lines.append("Warnings / inferred assumptions")

        if header_warnings:
            for w in header_warnings:
                _push(f"- {w}", suspicious=True)

        else:
            lines.append("- none")

        if self._re_meas_lambda_min_nm is not None and self._re_meas_lambda_max_nm is not None:
            lines.append("")

            _push(
                "Fit window initialized to measurement range: "
                f"[{float(self._re_meas_lambda_min_nm):.1f}, {float(self._re_meas_lambda_max_nm):.1f}] nm",
                suspicious=(float(self._re_meas_lambda_max_nm) <= float(self._re_meas_lambda_min_nm)),
            )

        return "\n".join(lines)

    def _re_show_load_summary_dialog(self, text: str) -> None:
        """Show non-modal summary dialog after RE file load."""

        import html

        from PyQt6.QtWidgets import QTextEdit

        dlg = QDialog(self)

        dlg.setWindowTitle("RE Load Summary")

        dlg.setMinimumSize(920, 640)

        lay = QVBoxLayout(dlg)

        info = QLabel("Parsed metadata and assumptions (spectral raw arrays intentionally omitted).")

        info.setWordWrap(True)

        lay.addWidget(info)

        box = QTextEdit()

        box.setReadOnly(True)

        html_lines: list[str] = []

        for ln in text.splitlines():
            if ln.startswith("!! "):
                html_lines.append(f"<b>{html.escape(ln[3:])}</b>")

            else:
                html_lines.append(html.escape(ln))

        box.setHtml("<pre style='font-family: Consolas, monospace;'>" + "\n".join(html_lines) + "</pre>")

        lay.addWidget(box, 1)

        row = QHBoxLayout()

        btn_copy = QPushButton("Copy summary")

        btn_copy.clicked.connect(functools.partial(QApplication.clipboard().setText, text))

        btn_close = QPushButton("Close")

        btn_close.clicked.connect(dlg.close)

        row.addWidget(btn_copy)

        row.addStretch()

        row.addWidget(btn_close)

        lay.addLayout(row)

        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        dlg.show()

    def load_reverse_engineering(self):
        """Load a reverse-engineering .xlsx file and configure the GUI.

        Parses three sheets (measurement / design / index), populates the

        front-table, material spinboxes and target-table, enables oblique mode,

        then activates the Run RE button.

        **Measurement**: any number of spectral columns; wavelength column is detected

        by header keywords (lambda, nm, ...) or by a monotonic numeric column. Values

        in **percent** (typical R/T > 1) are auto-scaled to fractions.

        Column titles are interpreted by :func:`parse_re_column_header` (R/T, angle,

        pol, noBK / back). If interpretation is ambiguous, a warning is logged

        and a dialog may summarize assumptions for the user.

        **Index / design** sheets tolerate column reordering (see module helpers

        ``_re_index_*`` / ``_re_parse_design_*``).

        Sheet names may use common aliases (*indices* -> *index*, etc.).  Design QWOT

        may appear as **multiple numeric columns per row** (e.g. H/L pairs), as in

        ``reverse_sample0.xlsx``.

        """

        if not OPENPYXL_AVAILABLE:
            self.log("openpyxl not installed.  Run:  pip install openpyxl", "ERROR")

            return

        f, _ = QFileDialog.getOpenFileName(self, "Load RE File", get_certus_last_dir(), "Excel (*.xlsx)")

        if not f:
            return

        self.load_reverse_engineering_from_path(f)

    def load_reverse_engineering_from_path(self, path: str) -> bool:
        """Load RE workbook from *path* (no dialog). Returns True on success."""

        if not OPENPYXL_AVAILABLE:
            self.log("openpyxl not installed.  Run:  pip install openpyxl", "ERROR")

            return False

        if not path or not Path(path).is_file():
            self.log(f"RE: file not found: {path!r}", "ERROR")

            return False

        set_certus_last_dir(path)

        try:
            _t_re = time.perf_counter()

            import openpyxl

            wb = openpyxl.load_workbook(path, data_only=True)

            self.log(f"RE: workbook opened in {time.perf_counter() - _t_re:.2f}s", "INFO")

            self._re_last_substrate_source_path = None

            self._re_last_substrate_sheet = None

            sheet_map = _re_resolve_re_workbook_sheets(list(wb.sheetnames))

            not_found = [s for s in _RE_CANONICAL_SHEETS if s not in sheet_map]

            duplicated = len(sheet_map) == 3 and len(set(sheet_map.values())) < 3

            if (not_found or duplicated) and len(wb.sheetnames) == 3:
                self.log(
                    "RE: sheet titles do not map cleanly to measurement/design/index; "
                    "trying content-based assignment (3 sheets).",
                    "WARNING",
                )

                auto_map = self._re_automap_three_sheet_workbook(wb)

                if len(auto_map) == 3:
                    sheet_map = auto_map

                    not_found = []

            if not_found:
                avail = ", ".join(repr(s) for s in wb.sheetnames)

                self.log(
                    f"RE file missing sheet(s): {', '.join(not_found)}  sheets present: {avail}",
                    "ERROR",
                )

                return False

            lambda_ref = substrate_name = qwot_list = None

            wls_idx = n1_arr = _k1 = n2_arr = _k2 = None

            wls_meas = spectra_columns = re_header_warnings = None

            parse_err: ValueError | None = None

            for _attempt in range(2):
                ws_meas = wb[sheet_map["measurement"]]

                ws_des = wb[sheet_map["design"]]

                ws_idx = wb[sheet_map["index"]]

                try:
                    _t = time.perf_counter()

                    lambda_ref, substrate_name, qwot_list = self._parse_re_design(ws_des)

                    self.log(
                        f"RE: design sheet read ({len(qwot_list)} QWOT) in {time.perf_counter() - _t:.2f}s",
                        "INFO",
                    )

                    _t = time.perf_counter()

                    wls_idx, n1_arr, _k1, n2_arr, _k2 = self._parse_re_index(ws_idx)

                    self.log(
                        f"RE: index sheet read ({len(wls_idx)} points) in {time.perf_counter() - _t:.2f}s",
                        "INFO",
                    )

                    _t = time.perf_counter()

                    wls_meas, spectra_columns, re_header_warnings = self._parse_re_measurement(ws_meas)

                    self.log(
                        f"RE: measurement sheet read ({len(wls_meas)} lambda, "
                        f"{len(spectra_columns)} channels) in "
                        f"{time.perf_counter() - _t:.2f}s",
                        "INFO",
                    )

                    parse_err = None

                    break

                except ValueError as e:
                    parse_err = e

                    if _attempt == 0 and len(wb.sheetnames) == 3:
                        auto_map = self._re_automap_three_sheet_workbook(wb)

                        if auto_map and auto_map != sheet_map:
                            self.log(
                                f"RE: parse error ({e}); retrying with content-based sheet assignment.",
                                "WARNING",
                            )

                            sheet_map = auto_map

                            continue

                    raise

            if parse_err is not None:
                raise parse_err

            assert (
                lambda_ref is not None
                and qwot_list is not None
                and wls_idx is not None
                and wls_meas is not None
                and spectra_columns is not None
                and re_header_warnings is not None
            )

            if re_header_warnings:
                try:
                    self.set_validation_status("OK")
                    for _w in re_header_warnings:
                        self.add_validation_warning(f"RE header inference: {_w}")
                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
                    self.logger.warning("RE validation status/warnings update skipped: %s", exc)

                if os.environ.get("CERTUS_RE_HEADLESS") == "1":
                    logging.warning(
                        "RE header warnings (headless): %s",
                        " | ".join(re_header_warnings),
                    )

                else:
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        "RE  column header interpretation",
                        "The file was loaded, but some settings were **inferred automatically**. "
                        "Please verify they match your intent:\n\n " + "\n\n ".join(re_header_warnings),
                    )
            else:
                try:
                    self.set_validation_status("OK")
                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
                    self.logger.warning("RE validation status update skipped: %s", exc)

            col_desc = ", ".join(
                f"{s.raw_header}->{s.target_type} ={s.angle_deg} pol={s.pol} "
                f"back={'on' if s.include_backside else 'off'}"
                for s, _ in spectra_columns
            )

            self.log(
                f"RE: {len(qwot_list)} layers, lambda_ref={lambda_ref} nm, "
                f"substrate='{substrate_name}', columns: {col_desc}",
                "INFO",
            )

            _wls_valid = np.asarray(wls_meas, dtype=np.float64)

            _wls_valid = _wls_valid[np.isfinite(_wls_valid)]

            if _wls_valid.size > 0:
                self._re_meas_lambda_min_nm = float(np.min(_wls_valid))

                self._re_meas_lambda_max_nm = float(np.max(_wls_valid))

            else:
                self._re_meas_lambda_min_nm = None

                self._re_meas_lambda_max_nm = None

            # Build TabularMaterial objects (linear interpolation, no Cauchy)

            self._re_tabular_H = TabularMaterial(wls_idx, n1_arr, _k1, l0_ref=lambda_ref)

            self._re_tabular_L = TabularMaterial(wls_idx, n2_arr, _k2, l0_ref=lambda_ref)

            n_H_ref = self._re_tabular_H.n4

            n_L_ref = self._re_tabular_L.n4

            self.log(
                f"RE: tabular indices  H: n@{lambda_ref:.0f}nm={n_H_ref:.4f} | L: n@{lambda_ref:.0f}nm={n_L_ref:.4f}",
                "INFO",
            )

            #  Populate GUI (bulk, signals blocked)

            self._re_p4_display_beam_active = False

            self._re_p4_display_ap_knots_deg = None

            self._re_p4_display_ap_knots_nm = None

            self.blockSignals(True)

            try:
                self.l0_spin.setValue(lambda_ref)

                self._re_tabular_Sub = self._load_re_substrate(
                    substrate_name,
                    lambda_ref,
                    re_workbook_dir=str(Path(path).resolve().parent),
                )

                # Front table  alternating H / L

                self.front_table.blockSignals(True)

                self.front_table.setRowCount(0)

                for i, qwot in enumerate(qwot_list):
                    mat = "H" if i % 2 == 0 else "L"

                    self._add_front_row(mat, qwot, True)

                self.front_table.blockSignals(False)

                self._update_layer_count()

                # Enable global backside UI if any channel uses a finite-plate model

                need_back = any(spec.include_backside for spec, _ in spectra_columns)

                self.back_check.setChecked(need_back)

                if need_back:
                    self.log("RE: backside calculation enabled (at least one column).", "INFO")

                else:
                    self.log(
                        "RE: all columns are front-only / noBK  backside calculation off.",
                        "INFO",
                    )

            finally:
                self.blockSignals(False)

            # Oblique mode  angle / pol / R|T per point (table = display per channel)

            self.oblique_mode = True

            self._update_target_table_headers()

            #  Build ObliqueTarget list (stored internally, not in widget)

            step = float(wls_meas[1] - wls_meas[0]) if len(wls_meas) >= 2 else 10.0

            half = step / 2.0

            self._re_targets = []

            self._re_target_col_groups = []

            for spec, vals in spectra_columns:
                group = []

                for wl, val in zip(wls_meas, vals):
                    if np.isnan(val):
                        continue

                    t = ObliqueTarget(
                        angle=float(spec.angle_deg),
                        pol=spec.pol,
                        target_type=spec.target_type,
                        lmin=max(1.0, float(wl) - half),
                        lmax=float(wl) + half,
                        tmin=float(val),
                        tmax=float(val),
                        w=1.0,
                        on=True,
                        include_backside=spec.include_backside,
                    )

                    self._re_targets.append(t)

                    group.append(t)

                self._re_target_col_groups.append(group)

            #  Populate target table: ONE display row per spectral column

            self.target_table.blockSignals(True)

            self.target_table.setRowCount(0)

            self.target_table.blockSignals(False)

            for i_col, (spec, _) in enumerate(spectra_columns):
                self.add_target()

                r = self.target_table.rowCount() - 1

                for col, value in [
                    (1, float(spec.angle_deg)),
                ]:
                    w = self.target_table.cellWidget(r, col)

                    if w:
                        w.setValue(value)

                for col, text in [
                    (2, spec.pol),
                    (3, spec.target_type),
                ]:
                    w = self.target_table.cellWidget(r, col)

                    if w:
                        w.setCurrentText(text)

                for col, value in [
                    (4, float(wls_meas[0])),
                    (5, float(wls_meas[-1])),
                    (6, 1.0),
                ]:
                    w = self.target_table.cellWidget(r, col)

                    if w:
                        w.setValue(value)

                cw = self.target_table.cellWidget(r, 0)

                if cw:
                    chk = cw.findChild(QCheckBox)

                    if chk:
                        chk.setChecked(True)

                        # Disconnect existing slot to prevent duplicate signals/default UI behavior breaking our override

                        try:
                            chk.stateChanged.disconnect()

                        except (TypeError, RuntimeError):
                            pass

                        def make_toggle(group_ref, checkbox):

                            def _toggle(*args):

                                is_on = checkbox.isChecked()

                                for tgt in group_ref:
                                    tgt.on = is_on

                                self._schedule_eval()

                            return _toggle

                        chk.stateChanged.connect(make_toggle(self._re_target_col_groups[i_col], chk))

                tip = f"{spec.raw_header}\nBackside (inconsistent plate): {'yes' if spec.include_backside else 'no'}"

                for c in range(1, 7):
                    w = self.target_table.cellWidget(r, c)

                    if w:
                        w.setToolTip(tip)

            n_pts = sum(int(np.sum(~np.isnan(v))) for _, v in spectra_columns)

            ch_summ = ", ".join(f"{int(np.sum(~np.isnan(v)))} pts ({s.raw_header})" for s, v in spectra_columns)

            self.log(
                f"RE: {n_pts} measurement points stored ({ch_summ}). 1 display row per channel.",
                "INFO",
            )

            self._re_loaded = True

            self._re_workbook_path = str(Path(path).resolve())

            if (
                self._re_meas_lambda_min_nm is not None
                and self._re_meas_lambda_max_nm is not None
                and hasattr(self, "re_fit_lambda_min_spin")
                and hasattr(self, "re_fit_lambda_max_spin")
            ):
                self.re_fit_lambda_min_spin.blockSignals(True)

                self.re_fit_lambda_max_spin.blockSignals(True)

                try:
                    self.re_fit_lambda_min_spin.setValue(float(self._re_meas_lambda_min_nm))

                    self.re_fit_lambda_max_spin.setValue(float(self._re_meas_lambda_max_nm))

                finally:
                    self.re_fit_lambda_min_spin.blockSignals(False)

                    self.re_fit_lambda_max_spin.blockSignals(False)

                self.log(
                    "RE: fit lambda window initialized from workbook measurement range "
                    f"[{float(self._re_meas_lambda_min_nm):.1f}, {float(self._re_meas_lambda_max_nm):.1f}] nm.",
                    "INFO",
                )

            self._apply_re_excel_readout_from_file(lambda_ref, spectra_columns)

            self._re_opt_a_pct = 0.0

            self._re_opt_b_pct = 0.0

            self._re_opt_f_pct = 0.0

            self._re_spline_dH = None

            self._re_spline_dL = None

            self._re_spline_lam2_nm = None

            self._re_sub_cauchy_a0 = None

            self._re_sub_cauchy_a1 = None

            self._re_sub_cauchy_a2 = None

            self._re_clear_re_nk_preview()

            self.launch_re_btn.setEnabled(True)

            self.eval_btn.setEnabled(True)

            self.accumulated_evals = 0

            self._re_nfev_cumulative = 0

            self._workflow_best_rmse = float("inf")

            self._best_eval_result = None

            self._best_eval_rmse = float("inf")

            self._update_status_bar_stats()

            if os.environ.get("CERTUS_RE_HEADLESS") != "1":
                try:
                    summary_txt = self._re_build_load_summary_text(
                        file_path=path,
                        workbook_sheetnames=list(wb.sheetnames),
                        sheet_map=dict(sheet_map),
                        lambda_ref=float(lambda_ref),
                        substrate_name=str(substrate_name),
                        qwot_list=list(qwot_list),
                        wls_idx=np.asarray(wls_idx, dtype=np.float64),
                        wls_meas=np.asarray(wls_meas, dtype=np.float64),
                        spectra_columns=list(spectra_columns),
                        header_warnings=list(re_header_warnings),
                        need_back=bool(need_back),
                    )

                    self._re_show_load_summary_dialog(summary_txt)

                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ) as e:
                    self.log(f"RE: could not open summary dialog: {e}", "WARNING")

                self._schedule_eval(True)

                # Deferred: compute initial RMSE after run_eval finishes painting

                # (run_eval is queued via QTimer(0ms) and would overwrite the title)

                def _show_initial_re_rmse():

                    init_rmse = self._compute_re_rmse(0.0, 0.0, 0.0)

                    if init_rmse is not None:
                        self._update_re_spectrum_title(init_rmse, suffix="(initial)")

                        self.log(f"RE initial RMSE: {init_rmse:.6f}", "INFO")

                QTimer.singleShot(200, _show_initial_re_rmse)

            self.log(
                f"RE: load finished in {time.perf_counter() - _t_re:.2f}s  click  Run RE  to run optimization.",
                "SUCCESS",
            )

            show_toast(self, f"Loaded: {Path(path).name}", "success")

            return True

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            self.log(f"RE load error:\n{traceback.format_exc()}", "ERROR")

            return False

    def _compute_re_rmse(self, a_pct=0.0, b_pct=0.0, f_pct=0.0):
        """RMSE of current design vs RE targets (same lambda grouping / backside as REWorker).

        Spectral weight Deltaln(lambda) trapezoidal per target point (same as RE TRF least-squares objective). Re drift percents and

        cubic lambda law match REWorker; Im(n) unchanged.

        """

        try:
            if not getattr(self, "_re_loaded", False):
                return None

            stack = self._get_front_stack()

            mats = self._get_materials()

            ep = (
                self.ep_current
                if getattr(self, "_use_exact_ep", False)
                else init_thickness(stack, self.l0_spin.value(), mats)
            )

            ep = np.asarray(ep, dtype=np.float64)

            # Use per-measurement-point RE targets (NOT widget summary rows)

            tgts = self._get_oblique_tgts()

            if not tgts:
                return None

            float_dtype = np.float64

            complex_dtype = np.complex128

            # Build wls grid from target centers (matching REWorker)

            tgt_centers = sorted({(t.lmin + t.lmax) / 2.0 for t in tgts if t.on})

            if not tgt_centers:
                return None

            wls = np.array(tgt_centers, dtype=float_dtype)

            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

            n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

            n_sub = np.ascontiguousarray(mats_nk["Substrate"])

            lambda_ref = float(self.l0_spin.value())

            is_H_arr = np.array([l.mat == "H" for l in stack], dtype=bool)

            is_L_arr = np.array([l.mat == "L" for l in stack], dtype=bool)

            dH_st = getattr(self, "_re_spline_dH", None)

            dL_st = getattr(self, "_re_spline_dL", None)

            lam2_rm = getattr(self, "_re_spline_lam2_nm", None)

            n_layers_nominal, n_sub = re_apply_re_index_model(
                n_layers_nominal,
                n_sub,
                is_H=is_H_arr,
                is_L=is_L_arr,
                wls_nm=wls,
                lambda_ref_nm=lambda_ref,
                a_pct=float(a_pct),
                b_pct=float(b_pct),
                f_pct=float(f_pct),
                spline_dH=dH_st,
                spline_dL=dL_st,
                spline_lam_node2_nm=lam2_rm,
                re_envelope_scale=self._re_envelope_scale_from_gui(),
                sub_cauchy_theta=self._re_current_sub_cauchy_theta(dH_st, dL_st),
            )

            n_layers_T = np.ascontiguousarray(n_layers_nominal.T)

            p4_kw = self._re_p4_display_beam_kwargs()

            r_sp = float(_re_rmse_oblique_weighted(ep, n_layers_T, n_sub, wls, tgts, **p4_kw))

            ep0_rm = getattr(self, "_re_initial_ep", None)

            if ep0_rm is None or len(np.asarray(ep0_rm).ravel()) != len(ep):
                ep0_rm = init_thickness(stack, self.l0_spin.value(), mats)

            ep0_rm = np.asarray(ep0_rm, dtype=np.float64).ravel()

            alpha_q = self._re_rmse_qwot_alpha_for_display()

            r_qw = _re_qwot_rmse_abs_delta_at_l0(
                ep,
                ep0_rm,
                stack,
                mats,
                lambda_ref,
                is_H_arr,
                is_L_arr,
                spline_dH=dH_st,
                spline_dL=dL_st,
                spline_lam2_nm=lam2_rm,
                re_envelope_scale=self._re_envelope_scale_from_gui(),
                deadzone_abs=RE_RE_DEADZONE_QWOT_ABS,
            )

            return _re_rmse_combined_spectral_qwot(r_sp, float(r_qw), alpha_q)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            logging.warning(f"_compute_re_rmse error: {e}")

            return None

    def _re_p4_display_beam_kwargs(self) -> Dict[str, Any]:
        """Optional phase 4 arguments for _re_calc / RMSE when the last 'best' RE is a beam run."""

        if not getattr(self, "_re_p4_display_beam_active", False):
            return {}

        ak = getattr(self, "_re_p4_display_ap_knots_deg", None)

        al = getattr(self, "_re_p4_display_ap_knots_nm", None)

        if ak is None or al is None:
            return {}

        ak = np.asarray(ak, dtype=np.float64).ravel()

        al = np.asarray(al, dtype=np.float64).ravel()

        n = int(min(ak.size, al.size))

        if n < 2:
            return {}

        ap = float(self.cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG))

        return {
            "phase4_average": True,
            "beam_aperture": ap,
            "beam_aperture_knots_deg": np.ascontiguousarray(ak[:n]),
            "beam_aperture_knots_lam_nm": np.ascontiguousarray(al[:n]),
        }

    def _re_current_sub_cauchy_theta(self, dH_st, dL_st) -> tuple[float, float, float] | None:

        if dH_st is not None and dL_st is not None and len(np.asarray(dH_st).ravel()) == int(RE_SPLINE_N_KNOTS):
            a0, a1, a2 = (
                getattr(self, "_re_sub_cauchy_a0", None),
                getattr(self, "_re_sub_cauchy_a1", None),
                getattr(self, "_re_sub_cauchy_a2", None),
            )

            if None not in (a0, a1, a2):
                return (float(a0), float(a1), float(a2))

        return None

    def _re_log_rmse_config_recap(
        self,
        *,
        re_rmse_initial: float | None,
        re_rmse_phase1: float | None,
        re_rmse_final: float | None,
        phase2_splines_done: bool,
    ) -> None:
        """Log RMSE milestones (start, phase 1 thicknesses, phase 2b splines + Cauchy substrate if done)."""

        def _fmt(v: float | None) -> str:

            if v is None:
                return ""

            try:
                vf = float(v)

                return f"{vf:.6f}" if np.isfinite(vf) else ""

            except (TypeError, ValueError):
                return ""

        alpha_q = self._re_rmse_qwot_alpha_for_display()

        logging.info(
            "RE  RMSE recap [ √(RMSE_sp2 + RMSE_QWOT2) ] (RMSE_QWOT = RMS |DeltaQ| absolute at lambda₀)   =%g",
            alpha_q,
        )

        logging.info(
            "  [0] Start  initial thicknesses, tabular H/L/sub indices (Excel) : %s",
            _fmt(re_rmse_initial),
        )

        logging.info(
            "  [1] Variable thicknesses (phase 1), tabular indices              : %s",
            _fmt(re_rmse_phase1),
        )

        if phase2_splines_done:
            logging.info(
                "  [2] + DeltaRe(H,L) splines + Cauchy substrate 3p (phase 2b, tube +/-%g): %s",
                RE_SUB_CAUCHY_TUBE_DELTA,
                _fmt(re_rmse_final),
            )

        else:
            logging.info(
                "  [2] + H/L indices (phase 2b)                                   : not completed  "
                "worker final RMSE = %s",
                _fmt(re_rmse_final),
            )

        if hasattr(self, "log"):
            self.log(
                f"RE RMSE recap: [0] {_fmt(re_rmse_initial)} | [1] {_fmt(re_rmse_phase1)} | [2] {_fmt(re_rmse_final)}",
                "INFO",
            )

    def _re_build_target_theory_rows(
        self,
        ep: np.ndarray,
        a_pct: float,
        b_pct: float,
        f_pct: float,
        *,
        spline_dH: np.ndarray | None = None,
        spline_dL: np.ndarray | None = None,
        spline_lam_node2_nm: float | None = None,
        re_envelope_scale: float = 1.0,
    ) -> list[dict[str, Any]]:
        """One row per RE point: target vs computed R/T (phase 2: DeltaRe splines if provided)."""

        stack = self._get_front_stack()

        mats = self._get_materials()

        ep = np.asarray(ep, dtype=np.float64).flatten()

        tgts_all = getattr(self, "_re_targets", [])

        tgts = self._re_filter_targets_by_fit_window([t for t in tgts_all if t.on and t.valid()])

        if not tgts:
            return []

        float_dtype = np.float64

        complex_dtype = np.complex128

        tgt_centers = sorted({(t.lmin + t.lmax) / 2.0 for t in tgts})

        wls = np.array(tgt_centers, dtype=float_dtype)

        mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

        n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

        n_sub = np.ascontiguousarray(mats_nk["Substrate"])

        lambda_ref = float(self.l0_spin.value())

        is_H = np.array([l.mat == "H" for l in stack], dtype=bool)

        is_L = np.array([l.mat == "L" for l in stack], dtype=bool)

        _sct0 = getattr(self, "_re_sub_cauchy_a0", None)

        _sub_bt = None

        if (
            spline_dH is not None
            and spline_dL is not None
            and len(np.asarray(spline_dH).ravel()) == int(RE_SPLINE_N_KNOTS)
            and _sct0 is not None
            and getattr(self, "_re_sub_cauchy_a1", None) is not None
            and getattr(self, "_re_sub_cauchy_a2", None) is not None
        ):
            _sub_bt = (
                float(_sct0),
                float(self._re_sub_cauchy_a1),
                float(self._re_sub_cauchy_a2),
            )

        n_layers_nominal, n_sub = re_apply_re_index_model(
            n_layers_nominal,
            n_sub,
            is_H=is_H,
            is_L=is_L,
            wls_nm=wls,
            lambda_ref_nm=lambda_ref,
            a_pct=a_pct,
            b_pct=b_pct,
            f_pct=f_pct,
            spline_dH=spline_dH,
            spline_dL=spline_dL,
            spline_lam_node2_nm=spline_lam_node2_nm,
            re_envelope_scale=re_envelope_scale,
            sub_cauchy_theta=_sub_bt,
        )

        n_layers_T = np.ascontiguousarray(n_layers_nominal.T)

        from collections import defaultdict

        config_groups = defaultdict(list)

        for tgt in tgts:
            config_groups[(tgt.angle, tgt.pol, tgt.include_backside)].append(tgt)

        out: list[dict[str, Any]] = []

        p4_kw = self._re_p4_display_beam_kwargs()

        for (angle, pol, include_backside), tgt_list in config_groups.items():
            R_c, T_c = _re_calc_spectrum_for_config(wls, n_layers_T, ep, n_sub, angle, pol, include_backside, **p4_kw)

            for tgt in tgt_list:
                wl_c = float((tgt.lmin + tgt.lmax) / 2.0)

                idx = int(np.argmin(np.abs(wls - wl_c)))

                if abs(float(wls[idx]) - wl_c) > 0.05:
                    continue

                tgt_val = float((tgt.tmin + tgt.tmax) / 2.0)

                theo = float(R_c[idx] if tgt.target_type == "R" else T_c[idx])

                out.append(
                    {
                        "lambda_nm": wl_c,
                        "angle_deg": float(tgt.angle),
                        "pol": str(tgt.pol),
                        "target_type": str(tgt.target_type),
                        "include_backside": bool(tgt.include_backside),
                        "weight": float(tgt.w),
                        "target": tgt_val,
                        "theory": theo,
                        "delta": theo - tgt_val,
                    }
                )

        out.sort(key=lambda r: (r["lambda_nm"], r["angle_deg"], r["pol"], r["target_type"]))

        return out

    def export_re_targets_vs_theory(
        self,
        ep: np.ndarray | None = None,
        a_pct: float | None = None,
        b_pct: float | None = None,
        f_pct: float | None = None,
        *,
        spline_dH: list | np.ndarray | None = None,
        spline_dL: list | np.ndarray | None = None,
        run_label: str = "best",
    ) -> None:
        """Excel export: targets vs theory (phase-2 Delta Re splines if spline_dH/L given)."""

        if not getattr(self, "_re_loaded", False):
            self.log("No RE file loaded.", "WARNING")

            return

        if ep is None:
            if self.ep_current is None:
                self.log("No thicknesses to export.", "WARNING")

                return

            ep_use = np.asarray(self.ep_current, dtype=np.float64).flatten()

        else:
            ep_use = np.asarray(ep, dtype=np.float64).flatten()

        a = float(self._re_opt_a_pct if a_pct is None else a_pct)

        b = float(self._re_opt_b_pct if b_pct is None else b_pct)

        f = float(self._re_opt_f_pct if f_pct is None else f_pct)

        stack_front = self._get_front_stack()

        qwot_sum_l0 = 0.0

        for i, layer in enumerate(stack_front):
            if i < len(ep_use):
                qwot_sum_l0 += float(self._ep_nm_to_qwot(float(ep_use[i]), layer.mat))

        sdh = np.asarray(spline_dH, dtype=np.float64).ravel() if spline_dH is not None else None

        sdl = np.asarray(spline_dL, dtype=np.float64).ravel() if spline_dL is not None else None

        lam2_ex = getattr(self, "_re_spline_lam2_nm", None)

        _esc = self._re_envelope_scale_from_gui()

        rows = self._re_build_target_theory_rows(
            ep_use,
            a,
            b,
            f,
            spline_dH=sdh,
            spline_dL=sdl,
            spline_lam_node2_nm=lam2_ex,
            re_envelope_scale=_esc,
        )

        if not rows:
            self.log("No rows to export (RE targets?).", "WARNING")

            return

        manifest_dict: dict[str, Any] = {}
        try:
            from certus_data import get_missing_manifest_fields
            from certus_metrology import ValidationStatus
            from certus_services import REFitService, REFitRequest

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
                getattr(self, "_loaded_config", {}).get("robustness_seed")
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
            svc = REFitService(runner=lambda _cfg: {"rows_count": len(rows), "run_label": str(run_label)})
            req = REFitRequest(
                config={
                    "module": "CERTUS_RE",
                    "export_kind": "targets_vs_theory",
                    "rows_count": int(len(rows)),
                },
                source_paths=[
                    p
                    for p in (
                        str(getattr(self, "_last_loaded_re_file", "") or "").strip(),
                        str(getattr(self, "_re_last_substrate_source_path", "") or "").strip(),
                    )
                    if p and p != "<builtin>"
                ],
                seed=seed_val,
                app_id="CERTUS_RE",
                app_version=__version__,
                warnings=list(getattr(self, "validation_warnings", []) or []),
                status=status_val,
            )
            manifest_dict = svc.fit(req).manifest.to_dict()
            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.log(
                    "Export blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
                    "ERROR",
                )
                return
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as exc:
            self.log(f"Manifest generation failed: {exc}", "WARNING")
            return

        if not OPENPYXL_AVAILABLE:
            self.log("openpyxl required for Excel export.", "WARNING")

            return

        default_name = f"RE_targets_vs_theory_{run_label}_{certus_timestamp_file()}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export RE  targets vs theoretical spectrum",
            str(Path(get_certus_last_dir() or ".") / default_name),
            "Excel (*.xlsx)",
        )

        if not path:
            return

        set_certus_last_dir(path)

        try:
            import openpyxl
            wb = openpyxl.Workbook()

            ws = wb.active

            ws.title = "Targets_vs_theory"

            hdr = [
                "lambda_nm",
                "theta_deg",
                "Pol",
                "R_or_T",
                "Backside",
                "Weight",
                "Target",
                "Theory",
                "Delta_theory_minus_target",
                "Sum_QWOT_at_lambda0",
                "drift_Re_H_%",
                "drift_Re_L_%",
                "drift_Re_sub_%",
            ]

            ws.append(hdr)

            for r in rows:
                ws.append(
                    [
                        round(r["lambda_nm"], 6),
                        r["angle_deg"],
                        r["pol"],
                        r["target_type"],
                        "yes" if r["include_backside"] else "no",
                        r["weight"],
                        r["target"],
                        r["theory"],
                        r["delta"],
                        round(qwot_sum_l0, 6),
                        a,
                        b,
                        f,
                    ]
                )

            meta = wb.create_sheet("Meta")

            meta.append(["CERTUS-RE export"])

            meta.append(["Generated", certus_timestamp_display()])

            meta.append(["lambda0_nm (drift reference)", float(self.l0_spin.value())])

            meta.append(["Sum_QWOT_at_lambda0 (final thicknesses, mat. n@lambda0)", qwot_sum_l0])

            _rmse_ex = self._compute_re_rmse(0.0, 0.0, 0.0)

            meta.append(["RMSE_1_over_sqrt_lambda", _rmse_ex if _rmse_ex is not None else ""])

            meta.append(["Thicknesses_nm", " ".join(f"{x:.4f}" for x in ep_use)])

            meta.append(["RE_envelope_scale", _esc])

            if sdh is not None and sdl is not None and lam2_ex is not None:
                meta.append(["RE_spline_lam_node2_nm", float(lam2_ex)])

            ws_m = wb.create_sheet("Manifest")
            ws_m.append(["Key", "Value"])
            for k, v in manifest_dict.items():
                ws_m.append([str(k), str(v)])

            wb.save(path)

            self.log(f"RE targets vs theory export: {Path(path).name}", "SUCCESS")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as ex:
            self.log(f"RE export error: {ex}", "ERROR")

            logging.exception("export_re_targets_vs_theory")

    def _re_init_plot_factors(self, wls, spline_dH, spline_dL):

        mats = self._get_materials()

        lam_ref = float(self.l0_spin.value())

        drift_factor = np.clip((wls - lam_ref) / max(5200.0 - lam_ref, 1.0), 0.0, None) ** 3

        use_sp = (
            spline_dH is not None
            and spline_dL is not None
            and len(np.asarray(spline_dH).ravel()) == int(RE_SPLINE_N_KNOTS)
            and len(np.asarray(spline_dL).ravel()) == int(RE_SPLINE_N_KNOTS)
        )

        return mats, drift_factor, use_sp

    def _show_re_drifted_indices_window(
        self,
        a_pct: float = 0.0,
        b_pct: float = 0.0,
        f_pct: float = 0.0,
        *,
        spline_dH: np.ndarray | None = None,
        spline_dL: np.ndarray | None = None,
        spline_lam_node2_nm: float | None = None,
        re_envelope_scale: float = 1.0,
        cauchy_a0: float | None = None,
        cauchy_a1: float | None = None,
        cauchy_a2: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Table of lambda vs Re before/after correction (DeltaRe splines or legacy drift %)."""

        host = parent if parent is not None else self

        w_parent = host if isinstance(host, QWidget) else self

        tgts = self._re_filter_targets_by_fit_window(
            [t for t in getattr(self, "_re_targets", []) if getattr(t, "on", True)]
        )

        if tgts:
            wls = np.array(
                sorted({(t.lmin + t.lmax) / 2.0 for t in tgts}),
                dtype=np.float64,
            )

        else:
            wls = self._re_fallback_plot_wavelengths_nm(200)

        mats, drift_factor, use_sp = self._re_init_plot_factors(wls, spline_dH, spline_dL)

        lambda_ref = float(self.l0_spin.value())

        series: list[tuple[str, list[str], list[np.ndarray]]] = []

        if use_sp:
            _lam2 = float(spline_lam_node2_nm) if spline_lam_node2_nm is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

            _knot_wl = re_knots_wavelengths(_lam2)

            dHv = re_interp_delta_knots_clamped(
                _knot_wl,
                np.asarray(spline_dH, dtype=np.float64),
                wls,
                envelope_scale=re_envelope_scale,
            )

            dLv = re_interp_delta_knots_clamped(
                _knot_wl,
                np.asarray(spline_dL, dtype=np.float64),
                wls,
                envelope_scale=re_envelope_scale,
            )

            if mats.get("H") is not None:
                nk = np.asarray(mats["H"].get_nk(wls), dtype=np.complex128)

                re0 = np.real(nk)

                series.append(("H", ["before", "after"], [re0, re0 + dHv]))

            if mats.get("L") is not None:
                nk = np.asarray(mats["L"].get_nk(wls), dtype=np.complex128)

                re0 = np.real(nk)

                series.append(("L", ["before", "after"], [re0, re0 + dLv]))

            if mats.get("Substrate") is not None:
                nk = np.asarray(mats["Substrate"].get_nk(wls), dtype=np.complex128)

                re0 = np.real(nk)

                if cauchy_a0 is not None and cauchy_a1 is not None and cauchy_a2 is not None:
                    x_sq = (lambda_ref / wls) ** 2

                    x_qu = (lambda_ref / wls) ** 4

                    A_mat = np.column_stack([np.ones_like(wls), x_sq, x_qu])

                    c_init, _, _, _ = np.linalg.lstsq(A_mat, re0, rcond=None)

                    re_cauchy_init = c_init[0] + c_init[1] * x_sq + c_init[2] * x_qu

                    re1 = float(cauchy_a0) + float(cauchy_a1) * x_sq + float(cauchy_a2) * x_qu

                    series.append(
                        ("Substrate", ["Loaded", "Cauchy Fit", "Cauchy Optimize"], [re0, re_cauchy_init, re1])
                    )

                else:
                    series.append(("Substrate", ["Loaded"], [re0]))

        else:
            channels: list[tuple[str, str, float]] = []

            if mats.get("H") is not None:
                channels.append(("H", "H", float(a_pct)))

            if mats.get("L") is not None:
                channels.append(("L", "L", float(b_pct)))

            if mats.get("Substrate") is not None:
                channels.append(("Substrate", "Substrate", float(f_pct)))

            for disp, key, pct in channels:
                nk = np.asarray(mats[key].get_nk(wls), dtype=np.complex128)

                re0 = np.real(nk)

                if key == "Substrate" and pct == 0.0:
                    series.append((disp, ["Loade"], [re0]))

                else:
                    re1 = re0 * (1.0 + (pct / 100.0) * drift_factor)

                    series.append((disp, ["before", "after"], [re0, re1]))

        if not series:
            self.log("No H / L / Substrate material to display indices.", "WARNING")

            return

        dlg = QDialog(w_parent)

        if use_sp:
            dlg.setWindowTitle(f"Indices Re(n)  DeltaRe(H,L) splines | lambda₀={lambda_ref:.0f} nm")

        else:
            dlg.setWindowTitle(
                f"Indices Re(n)  before / after drift % | lambda₀={lambda_ref:.0f} nm | "
                f"H={a_pct:+.3f}% L={b_pct:+.3f}% sub={f_pct:+.3f}%"
            )

        set_certus_window_icon(dlg)

        dlg.resize(920, min(650, 120 + 22 * len(wls)))

        lay = QVBoxLayout(dlg)

        lay.setContentsMargins(10, 10, 10, 10)

        if use_sp:
            lay.addWidget(
                QLabel(
                    "<b>Tabulated Re(n)</b> vs <b>Re + DeltaRe(lambda)</b> (linear interpolation on knots, "
                    "clamp |DeltaRe|(lambda) envelope). Substrate: dynamic Cauchy. <b>Im(n)</b> unchanged."
                )
            )

        else:
            lay.addWidget(
                QLabel(
                    "<b>Real part of indices</b>  after = Re × (1 + <i>p</i>% × <i>t</i>3), "
                    "<i>t</i> = max(0, (lambdalambda₀)/(5200lambda₀)). <b>Im(n)</b> unchanged."
                )
            )

        headers: list[str] = ["lambda_nm"]

        for disp, subheads, arrs in series:
            for sh in subheads:
                headers.append(f"Re({disp}) {sh}")

        nrows = len(wls)

        ncols = len(headers)

        tbl = ExcelTableWidget()

        tbl.setRowCount(nrows)

        tbl.setColumnCount(ncols)

        tbl.setHorizontalHeaderLabels(headers)

        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        tbl.setAlternatingRowColors(True)

        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for i, wl in enumerate(wls):
            tbl.setItem(i, 0, QTableWidgetItem(f"{float(wl):.4f}"))

            c = 1

            for disp, subheads, arrs in series:
                for col_idx, arr in enumerate(arrs):
                    it_a = QTableWidgetItem(f"{float(arr[i]):.6f}")

                    if col_idx > 0:
                        it_a.setForeground(QColor("#60a5fa"))

                    it_a.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    tbl.setItem(i, c, it_a)

                    c += 1

        lay.addWidget(tbl)

        btn_row = QHBoxLayout()

        copy_b = QPushButton(" Copy (TSV)")

        def _copy_tbl():

            lines = ["\t".join(headers)]

            for r in range(tbl.rowCount()):
                row = [tbl.item(r, cc).text() if tbl.item(r, cc) else "" for cc in range(tbl.columnCount())]

                lines.append("\t".join(row))

            QApplication.clipboard().setText("\n".join(lines))

            copy_b.setText(" Copied")

            QTimer.singleShot(1500, lambda: copy_b.setText(" Copy (TSV)"))

        copy_b.clicked.connect(_copy_tbl)

        close_b = QPushButton("Close")

        close_b.clicked.connect(dlg.close)

        btn_row.addWidget(copy_b)

        btn_row.addStretch()

        btn_row.addWidget(close_b)

        lay.addLayout(btn_row)

        dlg.show()

    def _update_re_spectrum_title(self, rmse=None, suffix=""):
        """Update spectrum plot title with RE RMSE."""

        n_layers = self.front_table.rowCount()

        title = f"RE Spectrum ({n_layers} layers)"

        if rmse is not None and np.isfinite(rmse):
            title += f"  RMSE: {rmse:.6f}"

        if suffix:
            title += f" {suffix}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

    def _re_speed_mode(self) -> str:
        """slow | medium | fast  default medium if speed UI is not built yet."""

        if not getattr(self, "re_speed_medium_radio", None):
            return "medium"

        if self.re_speed_slow_radio.isChecked():
            return "slow"

        if self.re_speed_fast_radio.isChecked():
            return "fast"

        return "medium"

    def _re_speed_preset(self) -> dict[str, Any]:

        return dict(RE_SPEED_PRESETS.get(self._re_speed_mode(), RE_SPEED_PRESETS["medium"]))

    def _re_gui_qwot_penalty_weight(self) -> float:
        """QWOT (phase 2b reference) for RMSE display / logs  follows speed preset."""

        if not bool(self.cfg.get("re_enable_qwot_penalty", True)):
            return 0.0

        try:
            return float(self._re_speed_preset()["re_qwot_penalty_weight"])

        except (KeyError, TypeError, ValueError):
            return float(RE_GUI_DEFAULT_RE_QWOT_ALPHA)

    def _re_envelope_scale_from_gui(self) -> float:
        """DeltaRe envelope factor (phase 2): read from speed preset."""

        try:
            return float(self._re_speed_preset()["re_envelope_scale"])

        except (KeyError, TypeError, ValueError):
            return 1.0

    def _re_spline_lam2_nm_from_result(self, r: dict) -> float:

        _kw = r.get("re_knots_nm")

        if _kw is not None and len(_kw) > 1:
            return float(np.asarray(_kw, dtype=np.float64).ravel()[1])

        _lv = r.get("re_spline_lam_node2_nm")

        if _lv is not None:
            return float(_lv)

        return float(RE_SPLINE_NODE2_DEFAULT_NM)

    def build_re_worker_cfg(self, overrides: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Build the `cfg` dict for :class:`REWorker` (same content as ``launch_re``).

        Returns ``None`` if the RE workbook is not loaded, there are no targets, or no initial ep0.

        *overrides* keys replace / extend cfg (shallow merge).

        """

        if not getattr(self, "_re_loaded", False):
            return None

        stack = self._get_front_stack()

        mats = self._get_materials()

        try:
            self._re_initial_ep = init_thickness(stack, self.l0_spin.value(), mats).copy()

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            self._re_initial_ep = None

        self._re_initial_stack = list(stack)

        self._re_sub_cauchy_a0 = None

        self._re_sub_cauchy_a1 = None

        self._re_sub_cauchy_a2 = None

        if self._re_initial_ep is None:
            return None

        re_tgts = self._get_oblique_tgts()

        if not re_tgts:
            return None

        wls_min = self._calculate_wls_min_with_margin(re_tgts)

        wls_max = self._calculate_wls_max_with_margin(re_tgts)

        lambda_ref = float(self.l0_spin.value())

        sp = self._re_speed_preset()

        cfg: dict[str, Any] = {
            "mats": mats,
            "stack": stack,
            "ep0": self._re_initial_ep,
            "l0": lambda_ref,
            "lambda_ref": lambda_ref,
            "re_workbook_path": getattr(self, "_re_workbook_path", None),
            "oblique_tgts": re_tgts,
            "wls_min": wls_min,
            "wls_max": wls_max,
            "back": self.back_check.isChecked(),
            "re_phase2_onesided_spline_fd": RE_PHASE2_ONESIDED_SPLINE_FD,
            "re_phase2_fd_parallel": RE_PHASE2_FD_PARALLEL,
            "re_phase2_fd_max_workers": RE_PHASE2_FD_MAX_WORKERS,
            "re_hl_delta_re_deadzone_abs": float(RE_RE_DEADZONE_DELTA_RE_ABS),
            "re_qwot_deadzone_abs": float(RE_RE_DEADZONE_QWOT_ABS),
        }

        cfg.update(sp)

        cfg.update(self.cfg)

        if not bool(cfg.get("re_enable_qwot_penalty", True)):
            cfg["re_qwot_penalty_weight"] = 0.0

            cfg["re_qwot_per_phase_schedule"] = False

            cfg["re_qwot_adaptive_init_scale"] = False

        if hasattr(self, "h_refine_check"):
            cfg["re_refine_h"] = bool(self.h_refine_check.isChecked())

            cfg["re_refine_l"] = bool(self.l_refine_check.isChecked())

            cfg["re_phase2b_substrate_cauchy"] = bool(self.sub_refine_check.isChecked())

        _knm = self.cfg.get("re_p4_beam_ap_knots_nm")

        if _knm is not None:
            cfg["re_p4_beam_ap_knots_nm"] = _knm

        if overrides:
            cfg.update(overrides)

        return cfg

    def _sync_display_re_results_btn_state(self) -> None:

        btn = getattr(self, "display_re_results_btn", None)

        if btn is None:
            return

        snap = getattr(self, "_re_last_results_snapshot", None)

        btn.setEnabled(bool(snap and snap.get("results")))

    def _on_display_re_results_clicked(self) -> None:

        snap = getattr(self, "_re_last_results_snapshot", None)

        if not snap or not snap.get("results"):
            self.log(
                "RE: no results table; run 'Run RE' first.",
                "WARNING",
            )

            return

        try:
            self._show_re_results_window(
                snap["results"],
                snap["ep0"],
                re_rmse_initial=snap.get("re_rmse_initial"),
                re_rmse_phase1=snap.get("re_rmse_phase1"),
                re_rmse_final=snap.get("re_rmse_final"),
                initial_stack=snap.get("initial_stack"),
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            self.log(
                "RE: impossible to open the results table.\n" + traceback.format_exc(),
                "ERROR",
            )

    def launch_re(self):
        """Lance REWorker : P1 epaisseurs, P2 splines DeltaRe (+substrate), P3 shakes, P4 faisceau (N paliers ap)."""

        if not self._re_loaded:
            self.log("No RE file loaded.  Use 'Load RE File' first.", "WARNING")

            return

        cfg = self.build_re_worker_cfg()

        if cfg is None:
            self.log(
                "No RE measurement targets found or initial thickness unavailable.",
                "ERROR",
            )

            return

        self._re_mode_active = True

        self._workflow_best_rmse = float("inf")

        self._re_last_live_alpha_qwot = None

        self._re_clear_re_nk_preview()

        self._set_busy(True)

        _Ksp = RE_SPLINE_N_KNOTS

        _es = float(cfg["re_envelope_scale"])

        _es_lbl = f"DeltaRe envelope ×{_es:g}"

        _hl = float(cfg.get("re_hl_delta_re_reg_sqrt_w", RE_HL_DELTA_RE_REG_SQRT_W))

        _dzre = float(cfg.get("re_hl_delta_re_deadzone_abs", RE_RE_DEADZONE_DELTA_RE_ABS))

        _dzqw = float(cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))

        _qw_on = bool(cfg.get("re_enable_qwot_penalty", True))

        _hl_lbl = f"DeltaRe H/L penalty √(w)={_hl:g} (outside +/-{_dzre:g}); " if _hl > 0.0 else ""

        _sub_on = bool(cfg.get("re_phase2b_substrate_cauchy", True))

        _sub_lbl = (
            f"+ Cauchy substrate (a0,a1,a2), tube +/-{RE_SUB_CAUCHY_TUBE_DELTA:g} vs n_tab(lambda)"
            if _sub_on
            else "+ fixed tabulated substrate indices (no Cauchy)"
        )

        _rad_pct = float(cfg.get("radius", RE_THICKNESS_SEARCH_RADIUS_PCT))

        _nt = len(cfg.get("oblique_tgts") or [])

        _nc = len(cfg.get("stack") or [])

        _wl0 = float(cfg.get("wls_min", 0.0))

        _wl1 = float(cfg.get("wls_max", 0.0))

        self.log(
            f"RE: P1P2  (1) TRF Deltaln(lambda) trap +/-{_rad_pct:g}% thicknesses only, tabulated indices; "
            f"(2) TRF joint: thicknesses + {2 * _Ksp + 1} param. (DeltaRe splines H/L + lambda₂) {_sub_lbl}; "
            f"{_es_lbl}; dead bands |DeltaRe|<={_dzre:g}, |DeltaQ|<={_dzqw:g}; "
            f"{_hl_lbl}"
            f"{_nt} targets, {_nc} layers, lambda [{_wl0:.0f}, {_wl1:.0f}] nm; "
            f"P3 shakes + P4 beam ap({int(RE_P4_BEAM_N_KNOTS)} lambda nodes, steps); "
            f"facade RMSE display={'√(sp2+alpha·QWOT2) (alpha per phase)' if _qw_on else 'RMSE_sp only'}; "
            f"TRF cost = TRF_RMS(res) over all vector r (iter logs).",
            "INFO",
        )

        _mode = self._re_speed_mode()

        _mode_lbl = {"slow": "Slow", "medium": "Medium", "fast": "Fast"}.get(_mode, _mode)

        _p1m = int(cfg.get("re_phase1_multistarts", 1))

        _tk = int(cfg.get("re_phase2_top_k", 1))

        _sh = int(cfg.get("re_phase3_shake_rounds", 0))

        _i1 = int(cfg.get("re_phase1_maxiter", 0))

        _i2a = int(cfg.get("re_phase2_spline_prefit_maxiter", 0))

        _i2b = int(cfg.get("re_phase2b_maxiter", 0))



        self.log(
            f"RE preset  {_mode_lbl}  : multistarts={_p1m}, top-K={_tk}, shakes={_sh}, "
            f"maxiter P1/2a/2b={_i1}/{_i2a}/{_i2b}.",
            "INFO",
        )

        self.log(
            (
                f"RE facade (logs / bar): RMSE_facade = √(RMSE_sp2 + alpha·RMSE_QWOT2), "
                f"QWOT penalty={'ON' if _qw_on else 'OFF'} (alpha phase varies; see worker). "
                f"Real TRF cost: TRF_RMS(r) in iteration logs."
                if _qw_on
                else "RE facade: QWOT penalty=OFF  RMSE_facade = RMSE_sp; TRF cost = TRF_RMS(r) (logs)."
            ),
            "INFO",
        )

        _fmin = float(cfg.get("wls_min", 0.0))

        _fmax = float(cfg.get("wls_max", 0.0))

        _ref_h = bool(cfg.get("re_refine_h", False))

        _ref_l = bool(cfg.get("re_refine_l", False))

        _ref_sub = bool(cfg.get("re_phase2b_substrate_cauchy", False))

        _p4_scan = int(cfg.get("re_phase4_aperture_scan_points", RE_PHASE4_APERTURE_SCAN_POINTS))

        _p4_nfev = int(cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))

        _p4_b = cfg.get("re_phase4_ap_bounds_deg", RE_P4_BEAM_AP_BOUNDS_DEG)

        _qw_on_ui = bool(cfg.get("re_enable_qwot_penalty", True))

        self.log(
            "RE facade  selection UI: "
            f"mode={_mode_lbl}, fit lambda=[{_fmin:.0f},{_fmax:.0f}]nm, "
            f"refine(H/L/sub)={_ref_h}/{_ref_l}/{_ref_sub}, "
            f"backside={'on' if bool(cfg.get('back', False)) else 'off'}, "
            f"QWOT_penalty={'on' if _qw_on_ui else 'off'}, "
            f"P4 scan_pts={_p4_scan}, P4 trf_nfev={_p4_nfev}, P4 ap_bounds={_p4_b}.",
            "INFO",
        )

        if hasattr(self, "progress_widget"):
            self.progress_widget.start()

        self._re_worker = REWorker(cfg)

        self._re_worker.signals.error.connect(self._on_error)

        self._re_worker.signals.error.connect(self._on_re_worker_error_cleanup)

        self._re_worker.signals.finished.connect(self._on_re_done)

        self._re_worker.signals.progress.connect(self._on_re_worker_progress)

        self._re_worker.signals.result.connect(self._on_re_worker_result)

        self._re_worker.start()
        install_skeleton(self.plot_tabs, label="Reverse Engineering in progress...")

    def _on_re_done(self, data: Dict):
        """Handle REWorker completion; show results dialog."""

        uninstall_skeleton(self.plot_tabs)
        self._re_mode_active = False

        self._re_clear_re_nk_preview()

        self._set_busy(False)

        if not data.get("ok"):
            self.log("RE optimization failed.", "ERROR")

            if hasattr(self, "progress_widget"):
                self.progress_widget.stop("RE failed")

            self._plot_nk()

            return

        if data.get("re_stopped_by_user"):
            self.log(
                "RE: stop requested; intermediate best result applied (same flow as normal finish).",
                "INFO",
            )

        results = data.get("results", [])

        _re_sort_results_best_for_table_and_apply(results)

        ep0 = np.asarray(data.get("ep0", []))

        if not results:
            self.log("RE: no results.", "WARNING")

            if hasattr(self, "progress_widget"):
                self.progress_widget.stop("RE: no result")

            self._plot_nk()

            return

        _a2b_done = data.get("re_qwot_alpha_phase2b")

        if _a2b_done is not None:
            try:
                self._re_rmse_qwot_alpha_ref = float(_a2b_done)

            except (TypeError, ValueError):
                self._re_rmse_qwot_alpha_ref = None

        else:
            self._re_rmse_qwot_alpha_ref = None

        ri = data.get("re_rmse_initial")

        r1 = data.get("re_rmse_phase1")

        rf = data.get("re_rmse_final")

        if results:
            rf = float(results[0].get("rmse_combined", results[0]["rmse"]))

        if ri is not None and r1 is not None and rf is not None and all(np.isfinite(float(x)) for x in (ri, r1, rf)):
            self.log(
                f"RE: RMSE milestones  initial={float(ri):.6f} | "
                f"phase 1 (thicknesses only)={float(r1):.6f} | worker end={float(rf):.6f}",
                "INFO",
            )

        _rk = results[0].get("re_ranking_score") if results else None

        _qwr = results[0].get("re_rmse_qwot_raw") if results else None

        _ar_ref = results[0].get("re_ranking_alpha_ref") if results else None

        if (
            _rk is not None
            and _qwr is not None
            and _ar_ref is not None
            and all(np.isfinite(float(x)) for x in (_rk, _qwr, _ar_ref))
        ):
            self.log(
                f"RE: RMSE_ranking (sqrt(sp2+alpha_ref·QWOT_raw2), inter-runs, alpha_ref={float(_ar_ref):g}) "
                f"= {float(_rk):.6f} | RMSE_sp={float(results[0]['rmse']):.6f} QWOT_raw={float(_qwr):.6f}",
                "INFO",
            )

        # Log summary

        for r in results:
            drift_sfx = re_drift_result_log_suffix(r)

            np1 = r.get("nfev_phase1")

            p1s = f" (phase1 nfev={np1})" if np1 is not None else ""

            _p2a = int(r.get("nfev_phase2_prefit", 0) or 0)

            p2as = f" phase2a_prefit nfev={_p2a}" if _p2a else ""

            _rcomb = float(r.get("rmse_combined", r["rmse"]))

            self.log(
                f"RE {r['label']:>18s}: RMSE_sp={r['rmse']:.6f} | RMSE_facade={_rcomb:.6f}{drift_sfx}  "
                f"({r['nfev']} phase2b evals{p1s}{p2as}, "
                f"{'converged' if r['success'] else 'max iter'})",
                "INFO",
            )

        # Apply best solution to front table

        best = results[0]

        ep_best = np.asarray(best["ep"]).flatten()

        self._workflow_best_rmse = best.get("rmse_combined", best["rmse"])

        _p1 = int(best.get("nfev_phase1", 0) or 0)

        _p2a = int(best.get("nfev_phase2_prefit", 0) or 0)

        _p2b = int(best.get("nfev", 0) or 0)

        self._re_nfev_cumulative += _p1 + _p2a + _p2b

        self._update_status_bar_stats()

        self._update_qwot_from_ep(ep_best)

        self._update_thickness_display()

        self.ep_current = ep_best.copy()

        self._use_exact_ep = True

        # Do not call run_eval immediately: it would set the UI to "Computing..."

        # and the (non-modal) results window often ended up behind other windows.

        _ak_b = best.get("re_p4_beam_ap_knots_deg")

        _anm_b = best.get("re_p4_beam_ap_knots_nm")

        if _ak_b is not None and _anm_b is not None:
            _aka = np.asarray(_ak_b, dtype=np.float64).ravel()

            _anma = np.asarray(_anm_b, dtype=np.float64).ravel()

            _np4 = int(min(_aka.size, _anma.size))

            if _np4 >= 2:
                self._re_p4_display_beam_active = True

                self._re_p4_display_ap_knots_deg = _aka[:_np4].copy()

                self._re_p4_display_ap_knots_nm = _anma[:_np4].copy()

            else:
                self._re_p4_display_beam_active = False

                self._re_p4_display_ap_knots_deg = None

                self._re_p4_display_ap_knots_nm = None

        else:
            self._re_p4_display_beam_active = False

            self._re_p4_display_ap_knots_deg = None

            self._re_p4_display_ap_knots_nm = None

        self._re_opt_a_pct = float(best.get("a", 0.0))

        self._re_opt_b_pct = float(best.get("b", 0.0))

        self._re_opt_f_pct = float(best.get("f", 0.0))

        if best.get("re_dH_knots") is not None and best.get("re_dL_knots") is not None:
            self._re_spline_dH = np.asarray(best["re_dH_knots"], dtype=np.float64).ravel()

            self._re_spline_dL = np.asarray(best["re_dL_knots"], dtype=np.float64).ravel()

            self._re_opt_a_pct = 0.0

            self._re_opt_b_pct = 0.0

            self._re_opt_f_pct = 0.0

            _kw_best = best.get("re_knots_nm")

            if _kw_best is not None and len(_kw_best) > 1:
                self._re_spline_lam2_nm = float(np.asarray(_kw_best, dtype=float)[1])

            else:
                _lv = best.get("re_spline_lam_node2_nm")

                self._re_spline_lam2_nm = float(_lv) if _lv is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

            _knots_log = np.asarray(
                _kw_best if _kw_best is not None else re_knots_wavelengths(self._re_spline_lam2_nm),
                dtype=np.float64,
            )

            _sfx = format_re_spline_knots_log(_knots_log, self._re_spline_dH, self._re_spline_dL)

            if best.get("re_sub_cauchy_a0") is not None:
                self._re_sub_cauchy_a0 = float(best["re_sub_cauchy_a0"])

                self._re_sub_cauchy_a1 = float(best["re_sub_cauchy_a1"])

                self._re_sub_cauchy_a2 = float(best["re_sub_cauchy_a2"])

                _sfx += (
                    f" | sub_Cauchy a0,a1,a2="
                    f"{self._re_sub_cauchy_a0:.5f},{self._re_sub_cauchy_a1:.5f},{self._re_sub_cauchy_a2:.5f}"
                )

            else:
                self._re_sub_cauchy_a0 = None

                self._re_sub_cauchy_a1 = None

                self._re_sub_cauchy_a2 = None

        else:
            self._re_spline_dH = None

            self._re_spline_dL = None

            self._re_spline_lam2_nm = None

            self._re_sub_cauchy_a0 = None

            self._re_sub_cauchy_a1 = None

            self._re_sub_cauchy_a2 = None

            a_best = float(best.get("a", 0.0))

            b_best = float(best.get("b", 0.0))

            f_best = float(best.get("f", 0.0))

            _sfx = format_re_drift_log_triplet_pct(a_best, b_best, f_best)

        _best_c = float(best.get("rmse_combined", best["rmse"]))

        self.log(
            f"RE: Best solution '{best['label']}' applied  "
            f"RMSE_sp={best['rmse']:.6f} | RMSE_facade={_best_c:.6f} ; {_sfx}",
            "SUCCESS",
        )

        self._plot_nk()

        try:
            self._re_last_results_snapshot = {
                "results": copy.deepcopy(results),
                "ep0": np.asarray(ep0, dtype=np.float64).copy(),
                "re_rmse_initial": ri,
                "re_rmse_phase1": r1,
                "re_rmse_final": rf,
                "re_qwot_alpha_phase2b": data.get("re_qwot_alpha_phase2b"),
                "initial_stack": copy.deepcopy(getattr(self, "_re_initial_stack", [])),
            }

            self._sync_display_re_results_btn_state()

            self._show_re_results_window(
                results,
                ep0,
                re_rmse_initial=data.get("re_rmse_initial"),
                re_rmse_phase1=data.get("re_rmse_phase1"),
                re_rmse_final=rf,
            )

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            self.log(
                "RE: the results window could not be displayed; detail:\n" + traceback.format_exc(),
                "ERROR",
            )

        self._re_log_rmse_config_recap(
            re_rmse_initial=ri,
            re_rmse_phase1=r1,
            re_rmse_final=rf,
            phase2_splines_done=best.get("re_dH_knots") is not None,
        )

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("RE stopped  best result" if data.get("re_stopped_by_user") else "RE completed")

        self._schedule_eval(True)

        def _show_final_re_title():

            final_rmse = self._compute_re_rmse(0.0, 0.0, 0.0)

            if final_rmse is not None:
                self._update_re_spectrum_title(
                    final_rmse,
                    suffix=(f"| {_sfx}"),
                )

        QTimer.singleShot(400, _show_final_re_title)

    def _show_re_results_window(
        self,
        results: list,
        ep0: np.ndarray,
        *,
        re_rmse_initial: float | None = None,
        re_rmse_phase1: float | None = None,
        re_rmse_final: float | None = None,
        initial_stack: list | None = None,
        announce_in_log: bool = True,
    ):
        """RE results dialog: QWOT @ lambda₀, Re index drifts (H, L, substrate), RMSE milestones."""

        _re_sort_results_best_for_table_and_apply(results)

        ep0 = np.asarray(ep0, dtype=np.float64).ravel()

        if ep0.size == 0 and results:
            ep0 = np.asarray(results[0].get("ep"), dtype=np.float64).ravel()

        if initial_stack is not None:
            initial_stack = list(initial_stack)

        else:
            initial_stack = getattr(self, "_re_initial_stack", [])

        n = int(ep0.size)

        n_runs = len(results)

        l0_ref = float(self.l0_spin.value())

        dlg = QDialog(self)

        dlg.setWindowTitle(f"RE Results (QWOT @ lambda₀={l0_ref:.0f} nm)")

        set_certus_window_icon(dlg)

        _n_rmse_rows = 0

        if re_rmse_initial is not None and re_rmse_phase1 is not None and re_rmse_final is not None:
            _n_rmse_rows = 3

        _n_spline_param_rows = 2 * RE_SPLINE_N_KNOTS

        _n_rank_row = 1 if results and results[0].get("re_ranking_score") is not None else 0

        dlg.resize(
            200 + n_runs * 180,
            min(
                100 + (n + _n_spline_param_rows + _n_rmse_rows + _n_rank_row) * 28 + 120,
                980,
            ),
        )

        layout = QVBoxLayout(dlg)

        layout.setContentsMargins(10, 10, 10, 10)

        layout.setSpacing(6)

        if _n_rmse_rows:
            _ri, _r1, _rf = re_rmse_initial, re_rmse_phase1, re_rmse_final

            layout.addWidget(
                QLabel(
                    "<b>RMSE (Deltaln(lambda) trapezoidal weighting, same as RE TRF / least-squares objective)</b><br>"
                    f"Initial (start thicknesses, nominal n): {_ri:.6f}<br>"
                    f"After thickness optimization (nominal n): {_r1:.6f}<br>"
                    f"Final (thicknesses + DeltaRe H/L splines, nominal substrate): {_rf:.6f}<br>"
                    "<i> = run with the lowest spectral RMSE (RMSE column of the summary below) ; "
                    "tie-break -> lowest RMSE. Solution applied at run end = same row.</i>"
                )
            )

        if results and results[0].get("re_ranking_score") is not None:
            _ar0 = float(results[0].get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

            layout.addWidget(
                QLabel(
                    "<b>RMSE (inter-run ranking)</b> = √(RMSE_sp2 + _refRMS(DeltaQ)2) "
                    f" <b>raw</b> QWOT (no dead band), _ref=<b>{_ar0:g}</b>. "
                    "At fixed _ref, lower = better sp / optical thickness trade-off."
                )
            )

        # Summary header

        summary_parts = []

        for i, r in enumerate(results):
            star = " " if i == 0 else ""

            _rk = r.get("re_ranking_score")

            _rk_s = f" &nbsp;|&nbsp; RMSE={float(_rk):.6f}" if _rk is not None else ""

            summary_parts.append(
                f"<b>{r['label']}</b>: RMSE={r['rmse']:.6f}{_rk_s}  "
                f"{re_drift_result_log_suffix(r)}  "
                f"({r['nfev']} evals){star}"
            )

        layout.addWidget(QLabel("<br>".join(summary_parts)))

        layout.addWidget(
            QLabel(
                "<i>QWOT / DeltaQWOT: 4n*ep/lambda₀ at lambda₀; initial tabulated n; "
                "final tabulated n + run DeltaRe splines H/L (aligned with TRF objective QWOT).</i>"
            )
        )

        # Table: Layer | Mat | Initial QWOT | Run1 Final | Run1 DeltaQ | ...

        n_cols = 3 + 2 * n_runs

        headers = ["#", "Mat", f"Initial QWOT@{l0_ref:.0f}nm"]

        for r in results:
            star = " " if r is results[0] else ""

            headers.append(f"{r['label']}{star} QWOT")

            headers.append("DeltaQWOT")

        n_total_rows = n + _n_spline_param_rows + _n_rmse_rows + _n_rank_row

        tbl = ExcelTableWidget()

        tbl.setRowCount(n_total_rows)

        tbl.setColumnCount(n_cols)

        tbl.setHorizontalHeaderLabels(headers)

        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        tbl.setAlternatingRowColors(True)

        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        _mats_tbl = self._get_materials()

        _lref_tbl = np.array([float(l0_ref)], dtype=np.float64)

        _esc_tbl = float(self._re_envelope_scale_from_gui())

        _kq_tbl = 4.0 / max(float(l0_ref), 1e-9)

        _nref_tbl = np.array(
            [
                float(
                    np.real(
                        np.asarray(
                            _mats_tbl[initial_stack[i].mat].get_nk(_lref_tbl),
                            dtype=np.complex128,
                        )[0]
                    )
                )
                for i in range(n)
            ],
            dtype=np.float64,
        )

        _is_h_tbl = np.array([initial_stack[i].mat == "H" for i in range(n)], dtype=bool)

        _is_l_tbl = np.array([initial_stack[i].mat == "L" for i in range(n)], dtype=bool)

        _run_n_corr_dq: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

        for r in results:
            _ep_r = np.asarray(r["ep"], dtype=np.float64).ravel()

            _lam2_r = self._re_spline_lam2_nm_from_result(r)

            _dh_r = r.get("re_dH_knots")

            _dl_r = r.get("re_dL_knots")

            _nc = re_n_corr_at_lambda_ref(
                _nref_tbl,
                _is_h_tbl,
                _is_l_tbl,
                _lref_tbl,
                _esc_tbl,
                spline_dH=_dh_r,
                spline_dL=_dl_r,
                spline_lam2_nm=_lam2_r,
            )

            _dq = re_delta_qwot_per_layer(
                _ep_r,
                ep0,
                _nref_tbl,
                _is_h_tbl,
                _is_l_tbl,
                float(l0_ref),
                _esc_tbl,
                _lref_tbl,
                spline_dH=_dh_r,
                spline_dL=_dl_r,
                spline_lam2_nm=_lam2_r,
            )

            _run_n_corr_dq.append((_nc, _dq, _ep_r))

        for i in range(n):
            ep_init = float(ep0[i])

            mat_name = initial_stack[i].mat if i < len(initial_stack) else "?"

            qw_init = _kq_tbl * float(_nref_tbl[i]) * ep_init

            tbl.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            tbl.setItem(i, 1, QTableWidgetItem(mat_name))

            tbl.setItem(i, 2, QTableWidgetItem(f"{qw_init:.4f}"))

            for j, r in enumerate(results):
                _nc_j, _dq_j, _ep_j = _run_n_corr_dq[j]

                ep_fin = float(_ep_j[i]) if i < _ep_j.size else float(r["ep"][i])

                qw_fin = _kq_tbl * float(_nc_j[i]) * ep_fin

                delta_q = float(_dq_j[i]) if i < _dq_j.size else (qw_fin - qw_init)

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                tbl.setItem(i, col_fin, QTableWidgetItem(f"{qw_fin:.4f}"))

                delta_item = QTableWidgetItem(f"{delta_q:+.4f}")

                if abs(delta_q) < 0.02:
                    delta_item.setForeground(QColor("#22c55e"))

                elif abs(delta_q) < 0.08:
                    delta_item.setForeground(QColor("#f59e0b"))

                else:
                    delta_item.setForeground(QColor("#ef4444"))

                tbl.setItem(i, col_d, delta_item)

            for col in range(n_cols):
                item = tbl.item(i, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        _knot_default = re_knots_wavelengths(RE_SPLINE_NODE2_DEFAULT_NM)

        _knot_display = np.asarray(results[0].get("re_knots_nm", _knot_default), dtype=float)

        _nk = RE_SPLINE_N_KNOTS

        for k in range(_nk):
            row_idx = n + k

            wl_k = float(_knot_display[k]) if k < len(_knot_display) else float(_knot_default[k])

            tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            label_item = QTableWidgetItem(f"DeltaRe(H) @ {wl_k:.0f} nm")

            label_item.setForeground(QColor("#60a5fa"))

            tbl.setItem(row_idx, 1, label_item)

            tbl.setItem(row_idx, 2, QTableWidgetItem("0"))

            for j, r in enumerate(results):
                dh = r.get("re_dH_knots", [0.0] * _nk)

                val = float(dh[k]) if k < len(dh) else 0.0

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                val_item = QTableWidgetItem(f"{val:+.5f}")

                val_item.setForeground(QColor("#60a5fa"))

                tbl.setItem(row_idx, col_fin, val_item)

                tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(n_cols):
                item = tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        for k in range(_nk):
            row_idx = n + _nk + k

            wl_k = float(_knot_display[k]) if k < len(_knot_display) else float(_knot_default[k])

            tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            label_item = QTableWidgetItem(f"DeltaRe(L) @ {wl_k:.0f} nm")

            label_item.setForeground(QColor("#34d399"))

            tbl.setItem(row_idx, 1, label_item)

            tbl.setItem(row_idx, 2, QTableWidgetItem("0"))

            for j, r in enumerate(results):
                dl = r.get("re_dL_knots", [0.0] * _nk)

                val = float(dl[k]) if k < len(dl) else 0.0

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                val_item = QTableWidgetItem(f"{val:+.5f}")

                val_item.setForeground(QColor("#34d399"))

                tbl.setItem(row_idx, col_fin, val_item)

                tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(n_cols):
                item = tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if _n_rmse_rows:

            def _fmt_rmse_cell(v: float) -> str:

                return f"{float(v):.6f}" if np.isfinite(v) else ""

            for kr, (rmse_lbl, rmse_v) in enumerate(
                [
                    ("RMSE initial (spectral Deltaln(lambda) trap + ×QWOT)  start thicknesses", re_rmse_initial),
                    ("RMSE after phase 1 (same definition)", re_rmse_phase1),
                    ("RMSE final (spectral + ×QWOT)  thicknesses + Re H/L splines", re_rmse_final),
                ]
            ):
                row_idx = n + _n_spline_param_rows + kr

                tbl.setItem(row_idx, 0, QTableWidgetItem(""))

                li = QTableWidgetItem(rmse_lbl)

                li.setForeground(QColor("#a78bfa"))

                tbl.setItem(row_idx, 1, li)

                tbl.setItem(row_idx, 2, QTableWidgetItem(""))

                rv = QTableWidgetItem(_fmt_rmse_cell(rmse_v))

                rv.setForeground(QColor("#a78bfa"))

                tbl.setItem(row_idx, 3, rv)

                tbl.setItem(row_idx, 4, QTableWidgetItem(""))

                for j in range(1, n_runs):
                    tbl.setItem(row_idx, 3 + 2 * j, QTableWidgetItem(""))

                    tbl.setItem(row_idx, 4 + 2 * j, QTableWidgetItem(""))

                for col in range(n_cols):
                    item = tbl.item(row_idx, col)

                    if item:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if _n_rank_row:
            row_idx = n + _n_spline_param_rows + _n_rmse_rows

            tbl.setItem(row_idx, 0, QTableWidgetItem(""))

            _ar_tbl = float(results[0].get("re_ranking_alpha_ref", RE_RANKING_ALPHA_REF))

            li = QTableWidgetItem(f"Ranking RMSE (√(sp2+_refQWOT_raw2), _ref={_ar_tbl:g})")

            li.setForeground(QColor("#f472b6"))

            tbl.setItem(row_idx, 1, li)

            tbl.setItem(row_idx, 2, QTableWidgetItem(""))

            for j, r in enumerate(results):
                rs = r.get("re_ranking_score")

                qrw = r.get("re_rmse_qwot_raw")

                col_fin = 3 + 2 * j

                col_d = 4 + 2 * j

                if rs is not None:
                    rv = QTableWidgetItem(f"{float(rs):.6f}")

                    rv.setForeground(QColor("#f472b6"))

                    rv.setToolTip(
                        f"RMSE_sp={float(r['rmse']):.6f}\n"
                        f"QWOT_raw (RMS |DeltaQ|)={float(qrw) if qrw is not None else 0.0:.6f}"
                    )

                    tbl.setItem(row_idx, col_fin, rv)

                else:
                    tbl.setItem(row_idx, col_fin, QTableWidgetItem(""))

                tbl.setItem(row_idx, col_d, QTableWidgetItem(""))

            for col in range(n_cols):
                item = tbl.item(row_idx, col)

                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(tbl)

        # Buttons

        btn_row = QHBoxLayout()

        export_tgt_btn = QPushButton(" Export cibles vs calcul (Excel)")

        export_tgt_btn.setToolTip(
            "One sheet per measurement point: target (RE file) vs computed R or T "
            "(thicknesses + DeltaRe H/L splines of the  solution)."
        )

        def _export_tgt_calc():

            best_r = results[0]

            ep_b = np.asarray(best_r["ep"], dtype=np.float64).flatten()

            a_b = float(best_r.get("a", 0.0))

            b_b = float(best_r.get("b", 0.0))

            f_b = float(best_r.get("f", 0.0))

            lbl = str(best_r.get("label", "best")).replace("/", "-").replace("\\", "-")[:48]

            sdh, sdl = best_r.get("re_dH_knots"), best_r.get("re_dL_knots")

            self.export_re_targets_vs_theory(
                ep_b,
                a_b,
                b_b,
                f_b,
                spline_dH=sdh,
                spline_dL=sdl,
                run_label=lbl,
            )

        export_tgt_btn.clicked.connect(_export_tgt_calc)

        idx_drift_btn = QPushButton(" Re indices (before / after correction)")

        idx_drift_btn.setToolTip("Tabulated Re vs after DeltaRe splines (H/L)  substrate unchanged.")

        def _open_idx():

            best_r = results[0]

            if best_r.get("re_dH_knots") is not None and best_r.get("re_dL_knots") is not None:
                _rkw = best_r.get("re_knots_nm")

                _lam_d = (
                    float(np.asarray(_rkw, dtype=float)[1])
                    if _rkw is not None and len(_rkw) > 1
                    else best_r.get("re_spline_lam_node2_nm")
                )

                self._show_re_drifted_indices_window(
                    spline_dH=np.asarray(best_r["re_dH_knots"], dtype=np.float64),
                    spline_dL=np.asarray(best_r["re_dL_knots"], dtype=np.float64),
                    spline_lam_node2_nm=_lam_d,
                    re_envelope_scale=self._re_envelope_scale_from_gui(),
                    cauchy_a0=best_r.get("re_sub_cauchy_a0"),
                    cauchy_a1=best_r.get("re_sub_cauchy_a1"),
                    cauchy_a2=best_r.get("re_sub_cauchy_a2"),
                    parent=dlg,
                )

            else:
                self._show_re_drifted_indices_window(
                    float(best_r.get("a", 0.0)),
                    float(best_r.get("b", 0.0)),
                    float(best_r.get("f", 0.0)),
                    parent=dlg,
                )

        idx_drift_btn.clicked.connect(_open_idx)

        overlay_plot_btn = QPushButton(" Overlay plot (targets vs theory)")

        overlay_plot_btn.setToolTip("Plot theoretical spectra overlaid on RE targets.")

        def _show_plot_overlay():

            best_r = results[0]

            self._show_re_target_plot_overlay(best_r, parent=dlg)

        overlay_plot_btn.clicked.connect(_show_plot_overlay)

        overlay_indices_btn = QPushButton(" Index plot (before/after)")

        overlay_indices_btn.setToolTip("Plot indices before and after RE correction.")

        def _show_indices_plot():

            self._show_re_indices_plot_overlay(results[0], parent=dlg)

        overlay_indices_btn.clicked.connect(_show_indices_plot)

        delta_qwot_btn = QPushButton(" Plot DeltaQWOT")

        delta_qwot_btn.setToolTip(
            "DeltaQWOT per layer: (4/lambda₀)(n_fin*ep_fin - n_init*ep_init) with n_fin = n_tab + run DeltaRe splines."
        )

        def _show_delta_qwot_plot():

            self._show_re_delta_qwot_plot(results[0], initial_stack, ep0, parent=dlg)

        delta_qwot_btn.clicked.connect(_show_delta_qwot_plot)

        beam_ap_plot_btn = QPushButton(" Beam ap(lambda)")

        beam_ap_plot_btn.setToolTip(
            "ap(lambda) in constant steps between lambda nodes (staircase steps), "
            "one curve per run (= best). The step ap values are not constrained to be monotonic."
        )

        def _plot_beam_aperture():

            self._show_re_p4_beam_aperture_plot(results, parent=dlg)

        beam_ap_plot_btn.clicked.connect(_plot_beam_aperture)

        copy_btn = QPushButton(" Copy to Clipboard")

        def _copy():

            lines = ["\t".join(headers)]

            for i in range(tbl.rowCount()):
                row_vals = [tbl.item(i, c).text() if tbl.item(i, c) else "" for c in range(n_cols)]

                lines.append("\t".join(row_vals))

            QApplication.clipboard().setText("\n".join(lines))

            copy_btn.setText(" Copied!")

            QTimer.singleShot(1500, lambda: copy_btn.setText(" Copy to Clipboard"))

        copy_btn.clicked.connect(_copy)

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(dlg.close)

        btn_row.addWidget(export_tgt_btn)

        btn_row.addWidget(idx_drift_btn)

        btn_row.addWidget(overlay_plot_btn)

        btn_row.addWidget(overlay_indices_btn)

        btn_row.addWidget(delta_qwot_btn)

        btn_row.addWidget(beam_ap_plot_btn)

        btn_row.addWidget(copy_btn)

        btn_row.addStretch()

        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)

        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        dlg.setMinimumSize(640, 420)

        if announce_in_log:
            self.log(
                "RE: results display; modal opening of 'RE Results' window "
                "(QWOT table, DeltaQWOT, DeltaRe splines, RMSE milestones, exports).",
                "INFO",
            )

        dlg.show()

        dlg.raise_()

        dlg.activateWindow()

        dlg.exec()

    def _show_re_p4_beam_aperture_plot(self, results: list, *, parent=None) -> None:
        """ap(lambda) staircase curve for each results entry with phase 4 nodes (RE Results table)."""

        runs: list[tuple[str, np.ndarray, np.ndarray]] = []

        for i, r in enumerate(results):
            ak = r.get("re_p4_beam_ap_knots_deg")

            nm = r.get("re_p4_beam_ap_knots_nm")

            if ak is None or nm is None:
                continue

            ak_a = np.asarray(ak, dtype=np.float64).ravel()

            nm_a = np.asarray(nm, dtype=np.float64).ravel()

            n = int(min(ak_a.size, nm_a.size))

            if n < 2:
                continue

            star = " " if i == 0 else ""

            runs.append(
                (
                    f"{r.get('label', f'run {i + 1}')}{star}",
                    nm_a[:n].copy(),
                    ak_a[:n].copy(),
                )
            )

        if not runs:
            QMessageBox.information(
                parent or self,
                "Beam width ap(lambda)",
                "No result row contains phase 4 data "
                "(re_p4_beam_ap_knots_deg / re_p4_beam_ap_knots_nm).\n\n"
                "Launch an RE optimization with phase 4 (beam).",
            )

            return

        w_lo: float | None = None

        w_hi: float | None = None

        tgts = self._re_filter_targets_by_fit_window(
            [t for t in getattr(self, "_re_targets", []) if getattr(t, "on", True)]
        )

        for t in tgts:
            if not t.valid():
                continue

            lo, hi = float(t.lmin), float(t.lmax)

            w_lo = lo if w_lo is None else min(w_lo, lo)

            w_hi = hi if w_hi is None else max(w_hi, hi)

        for _lbl, knm, _kap in runs:
            w_lo = float(np.min(knm)) if w_lo is None else min(w_lo, float(np.min(knm)))

            w_hi = float(np.max(knm)) if w_hi is None else max(w_hi, float(np.max(knm)))

        if w_lo is None or w_hi is None:
            w_lo, w_hi = 400.0, 2500.0

        pad = 0.03 * max(w_hi - w_lo, 1.0)

        w_lo_pad = float(max(1.0, w_lo - pad))

        w_hi_pad = float(w_hi + pad)

        dlg = QDialog(parent or self)

        dlg.setWindowTitle("RE  ap(lambda) (phase 4)")

        set_certus_window_icon(dlg)

        dlg.resize(820, 560)

        lay = QVBoxLayout(dlg)

        lay.setContentsMargins(10, 10, 10, 10)

        _cap_lines: list[str] = [
            "Values displayed = same coupling as phase 4 (TRF): lambda nodes in ascending order, "
            "ap constant per step between midpoint of consecutive lambda; circles = exact (lambdak, apk).",
        ]

        for _lbl, _knm, _kap in runs:
            _ks, _as = _re_p4_sort_knot_pairs(_knm, _kap)

            _pairs = "    ".join(f"lambda={float(lam):.0f} nm -> ap={float(apv):.2f}" for lam, apv in zip(_ks, _as))

            _cap_lines.append(f"{_lbl}: {_pairs}")

        _cap_lbl = QLabel("\n".join(_cap_lines))

        _cap_lbl.setWordWrap(True)

        _cap_lbl.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; padding-bottom: 6px;")

        lay.addWidget(_cap_lbl)

        pw = CertusScientificPlot(
            title="ap(lambda)  P4 steps (identical to TRF objective; nodes sorted by lambda, ap non-monotonic)"
        )

        pw.addLegend(offset=(10, 10))

        pw.setLabel("bottom", "Wavelength", units="nm")

        pw.setLabel("left", "ap", units="")

        pw.showGrid(x=True, y=True, alpha=0.3)

        pw.setXRange(w_lo_pad, w_hi_pad, padding=0.0)

        colors = list(getattr(CertusTheme, "CHART_COLORS", [])) or [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.DANGER,
        ]

        y_min, y_max = float("inf"), float("-inf")

        for idx, (lbl, knm, kap) in enumerate(runs):
            c = colors[idx % len(colors)]

            sx, sy = _re_p4_ap_staircase_polyline(knm, kap, w_lo_pad, w_hi_pad)

            y_min = min(y_min, float(np.nanmin(sy)))

            y_max = max(y_max, float(np.nanmax(sy)))

            line_pen = pg.mkPen(c, width=2.2)

            pw.plot(
                sx,
                sy,
                pen=line_pen,
                name=str(lbl)[:72],
            )

            k_s, a_s = _re_p4_sort_knot_pairs(knm, kap)

            if k_s.size >= 2:
                _cuts = np.array(
                    [0.5 * (k_s[i] + k_s[i + 1]) for i in range(k_s.size - 1)],
                    dtype=np.float64,
                )

                _cuts = _cuts[(_cuts >= w_lo_pad) & (_cuts <= w_hi_pad)]

                for _xc in _cuts:
                    pw.addItem(
                        pg.InfiniteLine(
                            pos=float(_xc),
                            angle=90,
                            pen=pg.mkPen(pg.mkColor(c), width=1, style=Qt.PenStyle.DotLine),
                            movable=False,
                        )
                    )

            sym_pen = pg.mkPen(pg.mkColor(c), width=1.2)

            pw.plot(
                k_s,
                a_s,
                pen=None,
                symbol="o",
                symbolSize=11,
                symbolBrush=pg.mkBrush(c),
                symbolPen=sym_pen,
                name=None,
            )

            if idx == 0:
                for _lam, _ap in zip(k_s, a_s):
                    _txt = pg.TextItem(
                        text=f"lambda={float(_lam):.0f}nm\nap={float(_ap):.2f}",
                        color=pg.mkColor(c),
                        anchor=(0.0, 1.0),
                    )

                    _txt.setPos(float(_lam), float(_ap))

                    pw.addItem(_txt)

        if np.isfinite(y_min) and np.isfinite(y_max):
            if y_max <= y_min:
                y_max = y_min + 0.1

            pad_y = 0.06 * max(y_max - y_min, 0.05)

            pw.setYRange(y_min - pad_y, y_max + pad_y)

        attach_excel_clipboard_context_menu(pw)

        lay.addWidget(wrap_scientific_plot_with_toolbar(dlg, pw))

        hb = QHBoxLayout()

        hb.addStretch()

        close_b = QPushButton("Close")

        close_b.clicked.connect(dlg.close)

        hb.addWidget(close_b)

        lay.addLayout(hb)

        dlg.exec()

    def _show_re_target_plot_overlay(self, best_r: dict, parent=None):
        """Continuous theory curves overlaid on RE experimental points (same idea as CERTUS_DESIGN)."""

        dlg = QDialog(parent or self)

        dlg.setWindowTitle(f"RE targets vs theory overlay ({best_r.get('label', 'best')})")

        set_certus_window_icon(dlg)

        dlg.resize(1000, 600)

        lay = QVBoxLayout(dlg)

        lay.setContentsMargins(10, 10, 10, 10)

        pw = CertusScientificPlot(title="Experimental targets vs theory")

        pw.addLegend(pos=(10, 10))

        pw.setLabel("bottom", "Wavelength", units="nm")

        pw.setLabel("left", "Reflectance / Transmittance")

        pw.showGrid(x=True, y=True, alpha=0.3)

        lay.addWidget(wrap_scientific_plot_with_toolbar(dlg, pw))

        attach_excel_clipboard_context_menu(pw)

        ep = np.asarray(best_r["ep"], dtype=np.float64).flatten()

        a_b = float(best_r.get("a", 0.0))

        b_b = float(best_r.get("b", 0.0))

        f_b = float(best_r.get("f", 0.0))

        sdh = best_r.get("re_dH_knots")

        sdl = best_r.get("re_dL_knots")

        lam2 = best_r.get("re_spline_lam_node2_nm")

        tgts_all = getattr(self, "_re_targets", [])

        tgts_active = self._re_filter_targets_by_fit_window([t for t in tgts_all if t.on and t.valid()])

        if not tgts_active:
            pw.setTitle("No valid target to display.")

            dlg.exec()

            return

        config_groups = {}

        min_w, max_w = 1e6, -1e6

        for t in tgts_active:
            wl_c = float((t.lmin + t.lmax) / 2.0)

            min_w = min(min_w, wl_c)

            max_w = max(max_w, wl_c)

            key = (float(t.angle), str(t.pol), bool(t.include_backside), str(t.target_type))

            if key not in config_groups:
                config_groups[key] = []

            config_groups[key].append((wl_c, float((t.tmin + t.tmax) / 2.0)))

        mar = (max_w - min_w) * 0.05

        if mar == 0:
            mar = 100.0

        wls_dense = np.linspace(max(200.0, min_w - mar), max_w + mar, 1000, dtype=np.float64)

        stack = self._get_front_stack()

        mats = self._get_materials()

        l0 = float(self.l0_spin.value())

        mats_nk = {k: m.get_nk(wls_dense) for k, m in mats.items()}

        n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=np.complex128)

        n_sub = np.ascontiguousarray(mats_nk["Substrate"])

        is_H = np.array([l.mat == "H" for l in stack], dtype=bool)

        is_L = np.array([l.mat == "L" for l in stack], dtype=bool)

        _sbd = best_r.get("re_sub_cauchy_a0")

        _sub_den = (
            (
                float(_sbd),
                float(best_r["re_sub_cauchy_a1"]),
                float(best_r["re_sub_cauchy_a2"]),
            )
            if _sbd is not None and sdh is not None
            else None
        )

        n_layers_corr, n_sub_corr = re_apply_re_index_model(
            n_layers_nominal,
            n_sub,
            is_H=is_H,
            is_L=is_L,
            wls_nm=wls_dense,
            lambda_ref_nm=l0,
            a_pct=a_b,
            b_pct=b_b,
            f_pct=f_b,
            spline_dH=np.asarray(sdh, dtype=np.float64) if sdh is not None else None,
            spline_dL=np.asarray(sdl, dtype=np.float64) if sdl is not None else None,
            spline_lam_node2_nm=lam2,
            re_envelope_scale=self._re_envelope_scale_from_gui(),
            sub_cauchy_theta=_sub_den,
        )

        n_layers_T = np.ascontiguousarray(n_layers_corr.T)

        _p4_ov = _re_p4_kwargs_from_opt_result(best_r, self.cfg)

        colors = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ERROR,
            CertusTheme.WARNING,
            CertusTheme.SUCCESS,
            CertusTheme.ACCENT,
        ]

        color_idx = 0

        for (ang, pol, inc_back, ttype), pts in config_groups.items():
            pts.sort(key=lambda x: x[0])

            wx = np.array([p[0] for p in pts])

            wy = np.array([p[1] for p in pts])

            lbl = f"{ttype} {ang} {pol}" + (" (Back)" if inc_back else "")

            col = colors[color_idx % len(colors)]

            color_idx += 1

            R_c, T_c = _re_calc_spectrum_for_config(
                wls_dense, n_layers_T, ep, n_sub_corr, float(ang), str(pol), bool(inc_back), **_p4_ov
            )

            theo = R_c if ttype == "R" else T_c

            pw.plot(
                wls_dense,
                theo,
                pen=pg.mkPen(col, width=2),
                name=f"Theory: {lbl}",
            )

            pw.plot(
                wx,
                wy,
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=pg.mkBrush(QColor(col).darker(110)),
                symbolPen=None,
                name=f"Targets: {lbl}",
            )

        dlg.exec()

    def _re_substrate_re_after_final(
        self,
        wls: np.ndarray,
        _re0_nominal: np.ndarray,
        fallback_re1: np.ndarray,
    ) -> np.ndarray:
        """Re(substrate) after correction: Cauchy 3p (a0,a1,a2) if present, else *fallback_re1*."""

        a0 = getattr(self, "_re_sub_cauchy_a0", None)

        a1 = getattr(self, "_re_sub_cauchy_a1", None)

        a2 = getattr(self, "_re_sub_cauchy_a2", None)

        if a0 is None or a1 is None or a2 is None:
            return np.asarray(fallback_re1, dtype=np.float64).copy()

        if not all(np.isfinite(float(x)) for x in (a0, a1, a2)):
            return np.asarray(fallback_re1, dtype=np.float64).copy()

        lr = float(self.l0_spin.value())

        th = np.array([float(a0), float(a1), float(a2)], dtype=np.float64)

        return re_substrate_cauchy_n_re_from_theta(wls, lr, th)

    def _show_re_indices_plot_overlay(self, best_r: dict, parent=None):
        """H, L and substrate indices: nominal vs final model (splines / drift %; substrate = Cauchy 3p if phase 2b)."""

        dlg = QDialog(parent or self)

        dlg.setWindowTitle(f"RE vs nominal indices overlay ({best_r.get('label', 'best')})")

        set_certus_window_icon(dlg)

        dlg.resize(1000, 600)

        lay = QVBoxLayout(dlg)

        lay.setContentsMargins(10, 10, 10, 10)

        pw = CertusScientificPlot(
            title="Re(n) indices  H/L: nominal vs splines or drift %; "
            "Substrate: nominal vs Cauchy 3p (a0,a1,a2); orange dotted = same model (ref.)"
        )

        pw.addLegend(pos=(10, 10))

        pw.setLabel("bottom", "Wavelength", units="nm")

        pw.setLabel("left", "Refractive index n")

        pw.showGrid(x=True, y=True, alpha=0.3)

        lay.addWidget(wrap_scientific_plot_with_toolbar(dlg, pw))

        attach_excel_clipboard_context_menu(pw)

        tgts_all = getattr(self, "_re_targets", [])

        tgts = self._re_filter_targets_by_fit_window(
            [t for t in tgts_all if getattr(t, "on", True) and (not hasattr(t, "valid") or t.valid())]
        )

        if tgts:
            wls = np.array(sorted({float((t.lmin + t.lmax) / 2.0) for t in tgts}), dtype=np.float64)

        else:
            wls = self._re_fallback_plot_wavelengths_nm(200)

        a_pct = float(best_r.get("a", 0.0))

        b_pct = float(best_r.get("b", 0.0))

        f_pct = float(best_r.get("f", 0.0))

        spline_dH = best_r.get("re_dH_knots")

        spline_dL = best_r.get("re_dL_knots")

        _rkw = best_r.get("re_knots_nm")

        _lam_d = (
            float(np.asarray(_rkw, dtype=float)[1])
            if _rkw is not None and len(_rkw) > 1
            else float(best_r.get("re_spline_lam_node2_nm", RE_SPLINE_NODE2_DEFAULT_NM))
        )

        mats, drift_factor, use_sp = self._re_init_plot_factors(wls, spline_dH, spline_dL)

        series = []

        _env = self._re_envelope_scale_from_gui()

        if use_sp:
            _knot_wl = re_knots_wavelengths(_lam_d)

            dHv = re_interp_delta_knots_clamped(
                _knot_wl,
                np.asarray(spline_dH, dtype=np.float64),
                wls,
                envelope_scale=_env,
            )

            dLv = re_interp_delta_knots_clamped(
                _knot_wl,
                np.asarray(spline_dL, dtype=np.float64),
                wls,
                envelope_scale=_env,
            )

            if mats.get("H") is not None:
                re0 = np.real(np.asarray(mats["H"].get_nk(wls), dtype=np.complex128))

                series.append(("H", re0, re0 + dHv))

            if mats.get("L") is not None:
                re0 = np.real(np.asarray(mats["L"].get_nk(wls), dtype=np.complex128))

                series.append(("L", re0, re0 + dLv))

            if mats.get("Substrate") is not None:
                re0_sub = np.real(np.asarray(mats["Substrate"].get_nk(wls), dtype=np.complex128))

                re1_sub = self._re_substrate_re_after_final(wls, re0_sub, re0_sub)

                series.append(("Substrate", re0_sub, re1_sub))

        else:
            channels: list[tuple[str, str, float]] = []

            if mats.get("H") is not None:
                channels.append(("H", "H", a_pct))

            if mats.get("L") is not None:
                channels.append(("L", "L", b_pct))

            for disp, mkey, pct in channels:
                re0 = np.real(np.asarray(mats[mkey].get_nk(wls), dtype=np.complex128))

                re1 = re0 * (1.0 + (pct / 100.0) * drift_factor)

                series.append((disp, re0, re1))

            if mats.get("Substrate") is not None:
                re0_sub = np.real(np.asarray(mats["Substrate"].get_nk(wls), dtype=np.complex128))

                re1_fb = re0_sub * (1.0 + (f_pct / 100.0) * drift_factor)

                re1_sub = self._re_substrate_re_after_final(wls, re0_sub, re1_fb)

                series.append(("Substrate", re0_sub, re1_sub))

        colors = {
            "H": CertusTheme.PRIMARY,
            "L": CertusTheme.SECONDARY,
            "Substrate": CertusTheme.WARNING,
        }

        for name, re0, re1 in series:
            col = colors.get(name, CertusTheme.PRIMARY)

            if not np.allclose(re0, re1, atol=1e-6):
                pw.plot(
                    wls,
                    re0,
                    pen=pg.mkPen(col, width=2, style=Qt.PenStyle.DashLine),
                    name=f"{name} (nominal)",
                )

                pw.plot(
                    wls,
                    re1,
                    pen=pg.mkPen(col, width=2),
                    name=f"{name} (RE  corrected)",
                )

            else:
                pw.plot(
                    wls,
                    re0,
                    pen=pg.mkPen(col, width=2, style=Qt.PenStyle.SolidLine),
                    name=f"{name} (unchanged)",
                )

        _ca0 = best_r.get("re_sub_cauchy_a0")

        _ca1 = best_r.get("re_sub_cauchy_a1")

        _ca2 = best_r.get("re_sub_cauchy_a2")

        if _ca0 is None or _ca1 is None or _ca2 is None:
            _ca0 = getattr(self, "_re_sub_cauchy_a0", None)

            _ca1 = getattr(self, "_re_sub_cauchy_a1", None)

            _ca2 = getattr(self, "_re_sub_cauchy_a2", None)

        if (
            _ca0 is not None
            and _ca1 is not None
            and _ca2 is not None
            and all(np.isfinite(float(x)) for x in (_ca0, _ca1, _ca2))
            and mats.get("Substrate") is not None
        ):
            try:
                wmn = float(np.min(wls))

                wmx = float(np.max(wls))

                w_den = np.linspace(wmn, wmx, max(200, int(len(wls)) * 5))

                lr = float(self.l0_spin.value())

                th = np.array([float(_ca0), float(_ca1), float(_ca2)], dtype=np.float64)

                n_cau = re_substrate_cauchy_n_re_from_theta(w_den, lr, th)

                pw.plot(
                    w_den,
                    n_cau,
                    pen=pg.mkPen("#fb923c", width=2, style=Qt.PenStyle.DotLine),
                    name="Substrate  Cauchy 3p (ref. lambda₀)",
                )

            except (
                ValueError,
                TypeError,
                RuntimeError,
                AttributeError,
                KeyError,
                IndexError,
                FileNotFoundError,
            ) as _e_cau:
                logging.debug("RE indices plot Cauchy 3p: %s", _e_cau)

        dlg.exec()

    def _show_re_delta_qwot_plot(self, best_r: dict, initial_stack: list, original_eps: np.ndarray, parent=None):
        """Histogramme DeltaQWOT = (4/lambda₀)(n_finep_fin  n_initep_init), n_fin inclut DeltaRe splines du run."""

        dlg = QDialog(parent or self)

        dlg.setWindowTitle(f"Delta QWOT histogram ({best_r.get('label', 'best')})")

        set_certus_window_icon(dlg)

        dlg.resize(800, 500)

        lay = QVBoxLayout(dlg)

        pw = CertusScientificPlot(
            title="Delta QWOT / layer (4/lambda₀)(n_fin*ep_fin - n_tab*ep_init)  n_fin with DeltaRe splines"
        )

        pw.setLabel("bottom", "Layer index (from Air)")

        pw.setLabel("left", "Delta QWOT")

        pw.showGrid(x=False, y=True, alpha=0.3)

        lay.addWidget(wrap_scientific_plot_with_toolbar(dlg, pw))

        x_vals = []

        y_vals = []

        colors = []

        brushes = []

        _l0p = float(self.l0_spin.value())

        _mats_p = self._get_materials()

        _lref_p = np.array([_l0p], dtype=np.float64)

        _esc_p = float(self._re_envelope_scale_from_gui())

        _ep0_p = np.asarray(original_eps, dtype=np.float64).ravel()

        _n_lay_p = len(initial_stack)

        _nref_p = np.array(
            [
                float(
                    np.real(
                        np.asarray(
                            _mats_p[initial_stack[i].mat].get_nk(_lref_p),
                            dtype=np.complex128,
                        )[0]
                    )
                )
                for i in range(_n_lay_p)
            ],
            dtype=np.float64,
        )

        _is_h_p = np.array([initial_stack[i].mat == "H" for i in range(_n_lay_p)], dtype=bool)

        _is_l_p = np.array([initial_stack[i].mat == "L" for i in range(_n_lay_p)], dtype=bool)

        _ep_fin_p = np.asarray(best_r["ep"], dtype=np.float64).ravel()

        _dq_hist = re_delta_qwot_per_layer(
            _ep_fin_p,
            _ep0_p,
            _nref_p,
            _is_h_p,
            _is_l_p,
            _l0p,
            _esc_p,
            _lref_p,
            spline_dH=best_r.get("re_dH_knots"),
            spline_dL=best_r.get("re_dL_knots"),
            spline_lam2_nm=self._re_spline_lam2_nm_from_result(best_r),
        )

        for i in range(_n_lay_p):
            delta_q = float(_dq_hist[i]) if i < _dq_hist.size else 0.0

            x_vals.append(i + 1)

            y_vals.append(delta_q)

            if abs(delta_q) < 0.02:
                col = QColor("#22c55e")

            elif abs(delta_q) < 0.08:
                col = QColor("#f59e0b")

            else:
                col = QColor("#ef4444")

            colors.append(pg.mkPen(col))

            brushes.append(pg.mkBrush(col))

        bg = pg.BarGraphItem(x=x_vals, height=y_vals, width=0.6, brushes=brushes, pens=colors)

        pw.addItem(bg)

        hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(QColor("#ffffff"), width=2, style=Qt.PenStyle.DashLine))

        pw.addItem(hline)

        attach_excel_clipboard_context_menu(pw)

        dlg.exec()

    # =========================================================================

    # SAUVEGARDE / CHARGEMENT

    # =========================================================================

    def open_help(self):
        """Open ``pages/CERTUS_RE.html`` in the default browser (via certus_ui.open_documentation)."""

        open_documentation("CERTUS_RE")

    def export_excel(self):
        """Excel snapshot: materials, stack, targets (oblique layout when RE / oblique), last spectrum."""

        if not OPENPYXL_AVAILABLE:
            self.log("openpyxl not installed. Run:  pip install openpyxl", "ERROR")

            return

        f, _ = QFileDialog.getSaveFileName(self, "CERTUS-RE  Export snapshot", get_certus_last_dir(), "Excel (*.xlsx)")

        if not f:
            return

        set_certus_last_dir(f)
        try:
            if not getattr(self, "validation_status", None):
                self.set_validation_status("OK")
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
            self.logger.warning("RE export preflight validation status skipped: %s", exc)

        try:
            import openpyxl
            wb = openpyxl.Workbook()

            ws = wb.active

            ws.title = "Configuration"

            ws.append(["CERTUS-RE", "CERTUS_SUITE_26_01"])

            ws.append([f"Generated:  {certus_timestamp_display()}"])

            ws.append([])

            ws.append(["MATERIALS"])

            _l0x = float(self.l0_spin.value())

            ws.append(["Name", f"Re(n)@lambda₀ ({_l0x:.1f} nm)"])

            for k, m in self._get_materials().items():
                ws.append([k, m.n4])

            ws.append([])

            ws.append(["FRONT STACK", f"L0 = {self.l0_spin.value()} nm"])

            ws.append(["#", "Material", "QWOT", "Thickness (nm)", "Variable"])

            ep = self.ep_current if self.ep_current is not None else []

            for i, l in enumerate(self._get_front_stack()):
                ws.append(
                    [
                        i + 1,
                        l.mat,
                        l.qwot,
                        ep[i] if i < len(ep) else 0,
                        "Yes" if l.var else "No",
                    ]
                )

            if len(ep) > 0:
                ws.append([])

                ws.append(["Total Thickness (nm)", float(np.sum(ep))])

            ws.append([])

            ws.append(["SPECTRAL TARGETS"])

            _ob_tgts = bool(self.oblique_mode) or bool(getattr(self, "_re_loaded", False))

            if _ob_tgts:
                ws.append(
                    [
                        "Active",
                        "Angle (deg)",
                        "Pol",
                        "Type",
                        "lambdamin (nm)",
                        "lambdamax (nm)",
                        "Target (R/T)",
                        "Weight",
                        "Backside",
                    ]
                )

                for t in self._get_oblique_tgts():
                    tv = 0.5 * (float(t.tmin) + float(t.tmax))

                    ws.append(
                        [
                            "Yes" if t.on else "No",
                            float(t.angle),
                            str(t.pol),
                            str(t.target_type),
                            t.lmin,
                            t.lmax,
                            tv,
                            t.w,
                            "Yes" if getattr(t, "include_backside", False) else "No",
                        ]
                    )

            else:
                ws.append(["Active", "lambdamin (nm)", "lambdamax (nm)", "Tmin", "Tmax", "Weight"])

                for t in self._get_tgts():
                    ws.append(["Yes" if t.on else "No", t.lmin, t.lmax, t.tmin, t.tmax, t.w])

            if self.last_result:
                lr = self.last_result

                spec_vis = lr.get("spectra_vis") or {}

                if lr.get("oblique_mode") and isinstance(spec_vis, dict) and len(spec_vis) > 0:
                    ws2 = wb.create_sheet("Spectrum")

                    wls = np.asarray(lr["vis"]["l"], dtype=float)

                    keys_sorted = sorted(spec_vis.keys(), key=lambda k: (float(k[0]), str(k[1])))

                    hdr: list[Any] = ["Wavelength (nm)"]

                    for ang, pol in keys_sorted:
                        hdr.append(f"R_{float(ang):g}deg_{pol}")

                        hdr.append(f"T_{float(ang):g}deg_{pol}")

                    ws2.append(hdr)

                    for i in range(int(wls.size)):
                        row: list[Any] = [float(wls[i])]

                        for ang, pol in keys_sorted:
                            ch = spec_vis[(ang, pol)]

                            row.append(float(ch["R"][i]))

                            row.append(float(ch["T"][i]))

                        ws2.append(row)

                else:
                    ws2 = wb.create_sheet("Spectrum")

                    ws2.append(["Wavelength (nm)", "Transmission"])

                    r = lr["vis"]

                    for i in range(len(r["l"])):
                        ws2.append([r["l"][i], r["Ts"][i]])

            manifest: dict[str, Any] | None = None
            try:
                from certus_metrology import ValidationStatus
                from certus_services import REFitService, REFitRequest
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                warnings_for_manifest = list(getattr(self, "validation_warnings", []) or [])
                svc = REFitService(runner=lambda _cfg: self.last_result or {})
                seed_val = None
                seed_sources = [
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("robustness_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("phase_a_seed")
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
                req = REFitRequest(
                    config={
                        "module": "CERTUS_RE",
                        "oblique_mode": bool(getattr(self, "oblique_mode", False)),
                        "re_loaded": bool(getattr(self, "_re_loaded", False)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "_last_loaded_re_file", "") or "").strip(),
                            str(getattr(self, "_re_last_substrate_source_path", "") or "").strip(),
                        )
                        if p and p != "<builtin>"
                    ],
                    seed=seed_val,
                    app_id="CERTUS_RE",
                    app_version=__version__,
                    warnings=warnings_for_manifest,
                    status=status_val,
                )
                manifest = svc.fit(req).manifest.to_dict()
                ws_m = wb.create_sheet("Manifest")
                ws_m.append(["Key", "Value"])
                for k, v in manifest.items():
                    ws_m.append([str(k), str(v)])
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, ImportError, OSError) as exc:
                self.logger.warning("RE manifest sheet export skipped: %s", exc)

            manifest_dict = manifest if isinstance(manifest, dict) else {}
            from certus_data import get_missing_manifest_fields
            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.log(
                    "Export blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
                    "ERROR",
                )
                return

            wb.save(f)

            self.log(f"Exported to:  {f}", "SUCCESS")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.log(f"Export error: {str(e)}", "ERROR")

    def closeEvent(self, event):
        """

        Handles application closure with proper cleanup of all workers.

        Ensures all QThread workers are properly stopped to avoid

        "QThread: Destroyed while thread is still running" warnings.

        """

        # Ensure all workers are stopped to avoid "QThread: Destroyed while thread is still running"

        workers = [
            getattr(self, "_re_worker", None),
            getattr(self, "eval_worker", None),
            getattr(self, "warmup_worker", None),
        ]

        for worker in workers:
            if worker and worker.isRunning():
                try:
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

    def _update_busy_ui(self, busy_now: bool):
        """Updates RE-specific button states."""

        re_ok = getattr(self, "_re_loaded", False)

        self.eval_btn.setEnabled(not busy_now and re_ok)

        self.load_re_btn.setEnabled(not busy_now)

        self.launch_re_btn.setEnabled(not busy_now and re_ok)

        self.stop_btn.setEnabled(busy_now)

    def reset_to_defaults(self):
        """Reset the application (tables, results, RE state, workers stopped)."""

        from certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

    def _load_defaults(self):
        """Loads default values"""

        self._re_mode_active = False

        self._re_nfev_cumulative = 0

        self._workflow_best_rmse = float("inf")

        self._clear_re_session_data()

        # Block signals to avoid massive re-evaluations during reset

        self.blockSignals(True)

        try:
            # Reset Global Parameters

            if hasattr(self, "l0_spin"):
                self.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self, "back_check"):
                self.back_check.setChecked(False)

            if hasattr(self, "auto_scale_y_check"):
                self.auto_scale_y_check.setChecked(True)

            self.cfg["re_beam_aperture_deg"] = float(RE_GUI_DEFAULT_BEAM_APERTURE_DEG)

            self.log("Default configuration loaded (CERTUS-RE).", "INFO")

            self._clear_re_excel_readout_ui()

        finally:
            self.blockSignals(False)

            # Force one final evaluation to show the default design

            self._schedule_eval(instant=True)

# =============================================================================

# ENTRY POINT

# =============================================================================

def main():
    """Main entry point"""

    # Change working directory to script/exe directory (script_dir set by bootstrap_app)

    try:
        os.chdir(script_dir)

    except (OSError, FileNotFoundError) as e:
        logging.debug(f"Could not change working directory: {e}")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    CertusTheme.apply_to_app(app, dark_mode=False)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS_RE", app=app)

    # --- SPLASH SCREEN ---

    from PyQt6.QtGui import QPixmap

    from PyQt6.QtWidgets import QSplashScreen

    splash_pix = QPixmap(get_resource_path("certus.svg"))

    if splash_pix.isNull():
        splash_pix = QPixmap(get_resource_path("certus.ico"))

    if splash_pix.isNull():
        splash_pix = QPixmap(400, 200)

        splash_pix.fill(Qt.GlobalColor.white)

    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)

    splash.show()

    splash.showMessage(
        "Initializing CERTUS  Reverse Engineering...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    # Setup logging with centralized helper

    setup_logging(log_file="certus_re.log")

    splash.showMessage(
        "Loading default configuration...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    win = CertusREApp()

    win.show()

    splash.finish(win)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_config(f))

    sys.exit(app.exec())

if __name__ == "__main__":
    # CRITICAL for Nuitka/PyInstaller: Must be FIRST in __main__

    multiprocessing.freeze_support()

    main()
