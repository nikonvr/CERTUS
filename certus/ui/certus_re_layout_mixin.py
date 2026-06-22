from __future__ import annotations
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_math import re_substrate_cauchy_n_re_from_theta
from certus.utils.certus_re_math import format_re_drift_log_triplet_pct
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_PHASE2_FD_MAX_WORKERS
from certus.utils.certus_re_config import RE_PHASE2_FD_PARALLEL
from certus.utils.certus_re_config import RE_PHASE2_ONESIDED_SPLINE_FD
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_config import RE_RE_DEADZONE_QWOT_ABS
from certus.utils.certus_re_config import RE_RE_DEADZONE_DELTA_RE_ABS
from certus.utils.certus_re_config import RE_HL_DELTA_RE_REG_SQRT_W
import logging
import copy
import time
import os
import functools
import multiprocessing
import traceback
from pathlib import Path
import sys
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg

from certus.core.certus_core import certus_timestamp_display, setup_logging, CFG, create_module_environment, NUMERICAL_FAULT_EXCEPTIONS, get_resource_path, certus_timestamp_file

from certus.ui.certus_qt_widgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox,
    QColor, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFont, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QKeySequence, QLabel, QMessageBox,
    QPushButton, QRadioButton, QScrollArea, QShortcut, QSplitter, QStackedWidget,
    QStatusBar, QTableWidgetItem, QTabWidget, QTextEdit, QTimer, Qt, QVBoxLayout,
    QWidget,
)

from certus_physics import Layer, ObliqueTarget, init_thickness, calc_spectrum_front_wrapper, calc_spectrum_full_exact_wrapper

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale, spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display, spectrum_eval_plot_curves,
    spectrum_eval_run_preamble, spectrum_eval_start_worker,
)

from certus.ui.certus_ui import (
    attach_excel_clipboard_context_menu, CertusBaseApp, CertusCard, CertusCollapsible,
    CertusScientificPlot, CertusStatusPill, CertusTheme, CertusThemeToggle,
    enable_file_drop, EnhancedProgressWidget, ExcelTableWidget, FlashyCard,
    get_certus_last_dir, install_standard_shortcuts, safe_ui_action,
    set_certus_last_dir, show_toast, WelcomeGuideWidget, create_flashy_grid,
    create_header_logo_widget, create_styled_button, create_styled_label,
    create_top_actions_bar, init_certus_app, set_certus_window_icon,
    install_skeleton_loader, remove_skeleton_loader, wrap_scientific_plot_with_toolbar,
    open_documentation, confirm_stop_with_timeout,
)

from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus.workers.certus_re_workers import REWorker
from certus.ui.certus_re_ui import CertusREResultsDialog

from certus.utils.certus_re_helpers import (
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    re_qwot_penalty_weight_from_preset,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
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
    format_re_spline_knots_log,
    parse_re_column_header,
    re_apply_re_index_model,
    re_delta_qwot_per_layer,
    re_drift_result_log_suffix,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    TabularMaterial,
    ParsedREColumn,
)
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class CertusRELayoutMixin:
    """CertusRELayoutMixin for CERTUS_RE."""

    def _get_default_splitter_sizes(self) -> list[int]:
        """RE specific splitter sizes."""

        return [380, 1060]

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

        scroll_layout.setSpacing(12)

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

        actions_wrap = CertusCard("Actions")

        actions_wrap.body.setContentsMargins(10, 8, 10, 10)

        actions_wrap.body.setSpacing(12)

        actions_wrap.body.addLayout(self._build_action_buttons())

        scroll_layout.addWidget(actions_wrap)

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        left_layout.addWidget(scroll, 1)

        try:
            from certus.ui.certus_animations import fade_in

            fade_in(actions_wrap, duration_ms=200)
        except ImportError:
            pass

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

        lay.setSpacing(12)

        hint = QLabel("<b>1</b> Load workbook &nbsp;&nbsp; <b>2</b> Evaluate spectrum &nbsp;&nbsp; <b>3</b> Run RE")

        hint.setWordWrap(True)

        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(hint)

        btn_lay = QHBoxLayout()

        btn_lay.setContentsMargins(0, 0, 0, 0)

        btn_lay.setSpacing(12)

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

        lay.setSpacing(12)

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
            "The solver minimizes TRF_RMS(r) (see iter logs). OFF: RMSE_facade = RMSE_sp."
        )

        self.re_qwot_penalty_chk.stateChanged.connect(lambda s: self.cfg.update({"re_enable_qwot_penalty": bool(s)}))

        self.cfg["re_enable_qwot_penalty"] = bool(self.re_qwot_penalty_chk.isChecked())

        lay.addWidget(self.re_qwot_penalty_chk)

        # No GUI input for ap: in P4 we work only with the optimized plateaus.

        self.cfg["re_beam_aperture_deg"] = float(RE_GUI_DEFAULT_BEAM_APERTURE_DEG)

        return c

    def _build_re_excel_data_group(self) -> CertusCard:
        """Indices + lambda₀ / back face: all from the RE Excel file."""

        c = CertusCard("Data from Excel")

        lay = c.body

        lay.setSpacing(12)

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

        fit_row.setSpacing(12)

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
            "lambda₀ (nm) after loading RE, fixed by the <b>design</b> sheet (see Excel box above)."
        )

        self.l0_spin.setVisible(False)

        self.back_check = QCheckBox(self)

        self.back_check.setText("Substrate back face (Fresnel)")

        self.back_check.setToolTip(
            "Back side substrate after RE loading, fixed by <b>measurement</b> headers."
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

    def _build_action_buttons(self) -> QGridLayout:
        """Four actions in 2x2 grid."""

        g = QGridLayout()

        g.setHorizontalSpacing(12)

        g.setVerticalSpacing(12)

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

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self, use_app_reset=True)

        g.addWidget(self.clear_btn, 1, 1)

        g.setColumnStretch(0, 1)

        g.setColumnStretch(1, 1)

        return g

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

        self.spectrum_plot.plotItem.enableAutoRange(y=True)

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

        # Show spectral window by default
        self.viz_stack.setCurrentIndex(1)

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

    def _build_status_bar(self):
        """Constructs status bar"""

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.best_rmse_label = QLabel("Best RMSE:  N/A")

        self.best_rmse_label.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-weight: bold; padding-left: 15px; padding-right: 15px;"
        )

        self.zoom_label = QLabel("Zoom 100%")
        self.zoom_label.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding-left: 10px; padding-right: 10px;"
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

        self.status_bar.addPermanentWidget(self.zoom_label)

        self.status_bar.addPermanentWidget(self.stats_label)

        self.status_bar.addPermanentWidget(self.best_rmse_label)

        self.status_bar.addPermanentWidget(self.progress_widget)

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
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
            extra={"Ctrl+L": self.toggle_logs},
        )
        self._zoom_factor = getattr(self, "_zoom_factor", 1.0)
        self._update_zoom_label(self._zoom_factor)
        self._update_zoom_label(self._zoom_factor)

        def _on_re_drop(paths):
            if paths and hasattr(self, "load_reverse_engineering_from_path"):
                self.load_reverse_engineering_from_path(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_re_drop, extensions=("xlsx", "xls", "csv"))

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
        """DeltaQWOT Histogram = (4/lambda₀)(n_finep_fin  n_initep_init), n_fin includes DeltaRe splines of the run."""

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
        dlg = CertusREResultsDialog(
            self,
            results,
            ep0,
            re_rmse_initial=re_rmse_initial,
            re_rmse_phase1=re_rmse_phase1,
            re_rmse_final=re_rmse_final,
            initial_stack=initial_stack,
            announce_in_log=announce_in_log
        )
        dlg.exec()
