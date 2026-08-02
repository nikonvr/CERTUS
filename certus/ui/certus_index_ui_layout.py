import os
import sys
from pathlib import Path
import logging
import time
import functools
from datetime import datetime
from typing import Any
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtSvgWidgets import QSvgWidget
from certus.core.certus_core import (
    get_resource_path,
    __version__,
    HC_EV_NM,
    N_MIN_LIMIT,
    N_MAX_LIMIT,
    K_MAX_LIMIT,
    SMALL_EPSILON,
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_LIST,
    certus_timestamp_display,
)
from certus.utils.certus_data import generate_html_report
from certus.ui.certus_ui import install_standard_shortcuts
from certus.utils.certus_index_utils import DataType, analyze_loaded_data, normalize_index_config
from certus_physics import (
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
    epsilon_to_nk,
    get_n_substrate_array_by_id,
    get_n_frosted_glass_array,
    calculate_RT_single_layer_backside_array,
    calculate_bare_substrate_RT,
    calculate_single_interface_R,
    calculate_bare_substrate_T_absorbing,
    calculate_bare_substrate_R_absorbing,
    calculate_RT_single_layer_absorbing_substrate_array,
)
from certus.utils.certus_index_utils import _get_substrate_n_array_index
from certus.core.certus_index_core import (
    OptimizationConfig,
    OptimizationResults,
    substrateMode,
    calculate_relative_R_normalization,
    _optimize_point_kernel,
    _optimize_all_points_batch,
    _SAPPHIRE_DATA_FILE,
    _SAPPHIRE_WLS,
    _SAPPHIRE_K,
    _SAPPHIRE_FILE_HAS_K_COLUMN,
    _SILICON_WLS,
    _SILICON_K,
)
from certus.workers.certus_index_workers import (
    IRGlobalModelWorker,
    OptimizationWorker,
    IndexBeamAnalysisWorker,
    _compute_RT_from_config,
    _index_live_spectrum_visibility,
    _spectrum_visibility_target_traces,
)
from certus.ui.certus_ui import (
    CertusBaseApp,
    CertusCard,
    CertusDashboardCard,
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    CertusThemeToggle,
    DetachedPlotWindow,
    EnhancedProgressWidget,
    ExcelTableWidget,
    FlashyCard,
    apply_certus_theme,
    clone_plot_widget,
    wrap_scientific_plot_with_toolbar,
    create_styled_button,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    stop_worker_and_thread,
    create_header_logo_widget,
    create_top_actions_bar,
    certus_get_open_file_name,
    get_export_config,
    init_certus_app,
    open_documentation,
    get_certus_last_dir,
    set_certus_last_dir,
    setup_gui_exception_handling,
    setup_module_logging,
    setup_pyqtgraph_defaults,
    show_toast,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.ui.certus_svg import SVG_AVAILABLE
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import QObject, QSettings, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

class ResultRecapWidget(QWidget):
    """UX-1: Modern Dashboard for optimization results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl_head = QLabel("OPTIMIZATION RESULTS")
        lbl_head.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: 800; letter-spacing: 2px; font-size: 13px;"
        )
        layout.addWidget(lbl_head)

        grid = QGridLayout()
        grid.setSpacing(12)

        self.card_d = CertusDashboardCard("Thickness", "layers", "nm")
        self.card_rmse = CertusDashboardCard("RMSE", "activity", "%")
        self.card_eg = CertusDashboardCard("Bandgap (Eg)", "sun", "eV")
        self.card_inf = CertusDashboardCard("Eps Inf", "circle", "")

        grid.addWidget(self.card_d, 0, 0)
        grid.addWidget(self.card_rmse, 0, 1)
        grid.addWidget(self.card_eg, 1, 0)
        grid.addWidget(self.card_inf, 1, 1)

        layout.addLayout(grid)

    def update_results(self, thickness, rmse, eg, eps_inf) -> None:
        d_status = "success" if thickness > 1 else "warning"
        d_msg = "Physical range" if thickness > 1 else "Unusually thin"
        self.card_d.update_value(f"{thickness:.2f}", d_status, d_msg)

        rmse_val = rmse * 100 if rmse < 1 else rmse
        r_status = "success" if rmse_val < 1.0 else "warning" if rmse_val < 3.0 else "danger"
        r_msg = "Excellent fit" if rmse_val < 1.0 else "Acceptable" if rmse_val < 3.0 else "High error"
        self.card_rmse.update_value(f"{rmse_val:.3f}", r_status, r_msg)

        eg_status = "info" if eg > 0 else "normal"
        self.card_eg.update_value(f"{eg:.2f}", eg_status, "Calculated")

        inf_status = "normal" if eps_inf > 1.0 else "warning"
        self.card_inf.update_value(f"{eps_inf:.2f}", inf_status, "Dielectric background")

        self.setVisible(True)

class CertusIndexLayoutMixin:
    def _apply_theme(self) -> None:
        """Apply Certus theme"""

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}
            """,
            plots=[
                getattr(self, "plot_spectrum", None),
                getattr(self, "plot_nk", None),
                getattr(self, "plot_convergence", None),
            ],
        )

        # Update Live Curves Pens

        try:
            if hasattr(self, "_live_curve_T"):
                self._live_curve_T.setPen(color=CertusTheme.SECONDARY, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_R"):
                self._live_curve_R.setPen(color=CertusTheme.ACCENT, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_n"):
                self._live_curve_n.setPen(color=CertusTheme.PRIMARY, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "_live_curve_k"):
                self._live_curve_k.setPen(color=CertusTheme.DANGER, width=2, style=Qt.PenStyle.DashLine)

            if hasattr(self, "convergence_curve"):
                self.convergence_curve.setPen(color=CertusTheme.ERROR, width=2)

        except (AttributeError, RuntimeError) as e:
            # Non-critical: convergence curve may not exist

            self.logger.debug("[INDEX.UI] convergence curve update skipped: %s", e)

            pass

        # Update Target Curves Symbols

        if hasattr(self, "plot_spectrum"):
            try:
                for item in self.plot_spectrum.getPlotItem().listDataItems():
                    if item.name() == "T data":
                        item.setSymbolBrush(CertusTheme.SUCCESS)

                    elif item.name() == "R data":
                        item.setSymbolBrush(CertusTheme.DANGER)

            except (AttributeError, RuntimeError) as e:
                # Non-critical: item may not have name or setSymbolBrush

                self.logger.debug("[INDEX.UI] target curve symbol update skipped: %s", e)

                pass

    def _build_ui(self) -> None:
        """Build user interface"""

        # Main Splitter instead of HBoxLayout

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.setCentralWidget(self.main_splitter)

        # === LEFT SIDE CONTAINER (Pinned Header + Scroll) ===

        left_container = QWidget()

        left_container.setMinimumWidth(280)

        left_container_layout = QVBoxLayout(left_container)

        left_container_layout.setContentsMargins(0, 0, 0, 0)

        left_container_layout.setSpacing(0)

        # 1. Standard Header (Pinned)

        header_widget = create_header_logo_widget(
            "CERTUS INDEX",
            "Material Database & Analysis",
            logo_width=180,
            module_name="CERTUS_INDEX",
        )

        left_container_layout.addWidget(header_widget)

        # 2. Action Bar (Pinned)

        action_bar = create_top_actions_bar(
            self,
            self.save_config,
            self.load_config,
            export_func=None,
            help_func=lambda: open_documentation("CERTUS_INDEX"),
        )

        left_container_layout.addWidget(action_bar)

        # 3. Scroll Area

        left_scroll = QScrollArea()

        left_scroll.setWidgetResizable(True)

        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel = QWidget()

        left_layout = QVBoxLayout(left_panel)

        left_layout.setContentsMargins(10, 10, 10, 10)

        left_layout.setSpacing(15)

        left_scroll.setWidget(left_panel)

        left_container_layout.addWidget(left_scroll)

        # Add container to splitter

        self.main_splitter.addWidget(left_container)

        # === CONTROLS CONTENT ===

        left_layout.addWidget(self._create_input_group())

        left_layout.addWidget(self._create_substrate_group())

        left_layout.addWidget(self._create_config_group())

        left_layout.addStretch()

        self.recap_widget = ResultRecapWidget()

        left_layout.addWidget(self.recap_widget)

        # Tabs
        self.tabs = QTabWidget()
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Buttons (Run/Stop/Beam)
        self._add_main_control_buttons(left_layout)

        # Note: Bean Analysis button removed natively (Uncertainty tab dropped)

        # Note: Export button removed - auto-export is active

        self.plot_spectrum = CertusScientificPlot(
            self, "Transmission / Reflection Spectrum", "T/R (%)", "Wavelength (nm)"
        )

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_spectrum), "Spectrum")

        self.plot_nk = CertusScientificPlot(self, "Optical Constants", "Index", "Wavelength (nm)")

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_nk), "n & k")

        # --- Convergence tab (UX-3: live RMSE feedback) ---

        self.plot_convergence = CertusScientificPlot(self, "Convergence — RMSE vs Iteration", "RMSE", "Iteration")

        self.plot_convergence.setBackground(None)

        self.plot_convergence.plotItem.showGrid(x=True, y=True, alpha=0.15)

        # Two curves: current-iteration RMSE and best-so-far envelope
        self._conv_curve_current = self.plot_convergence.plot(
            [],
            [],
            pen=pg.mkPen(color=CertusTheme.TEXT_SUB, width=1, style=Qt.PenStyle.DotLine),
            name="Current RMSE",
        )
        self._conv_curve_best = self.plot_convergence.plot(
            [],
            [],
            pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2),
            name="Best RMSE",
        )

        # State arrays (reset at each run start)
        self._conv_iterations: list[int] = []
        self._conv_rmse_current: list[float] = []
        self._conv_rmse_best: list[float] = []

        self.tabs.addTab(wrap_scientific_plot_with_toolbar(self, self.plot_convergence), "Convergence ↘")

        # Final equations tab

        self.eq_tab = QWidget()

        self.eq_tab_layout = QVBoxLayout(self.eq_tab)

        self.eq_tab_layout.setContentsMargins(20, 20, 20, 20)

        self.eq_tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lbl_final_eq = QLabel("Run optimization to see final equations.")

        self.lbl_final_eq.setStyleSheet("font-size: 11pt; color: #1e293b;")

        self.lbl_final_eq.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.lbl_final_eq.setWordWrap(True)

        self.eq_tab_layout.addWidget(self.lbl_final_eq)

        # ADD BUTTON HERE

        self.btn_copy_eq = create_styled_button(" Copy Equations", variant="secondary")

        self.btn_copy_eq.setToolTip("Copy the analytical equations to the clipboard as text")

        self.btn_copy_eq.clicked.connect(self._copy_eq_to_clipboard)

        self.btn_copy_eq.setEnabled(False)

        self.btn_copy_eq.setFixedWidth(200)

        self.eq_tab_layout.addWidget(self.btn_copy_eq)

        self.tabs.addTab(self.eq_tab, "Final Equations")

        # Detach plot button

        plot_header = QWidget()

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(5, 5, 5, 5)

        detach_btn = QPushButton(" Detach Plot")

        detach_btn.setToolTip("Detach current plot to separate window")

        detach_btn.clicked.connect(self.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_header_layout.addStretch()

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.tabs)

        self.perf_tab = QWidget()

        perf_layout = QGridLayout(self.perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "2-Stage Hybrid Engine",
            "TLU (UV-VIS) + PCHIP Spline (IR)\nContinuous transition at 2500 nm without breaking",
            icon="",
        )

        c2 = FlashyCard(
            "Ultra-Wide Spectrum",
            "From 200 to 6000+ nm in robust mode\nLimits non-physical drift in the IR",
            icon="",
        )

        c3 = FlashyCard(
            "Accelerated Physics Core",
            "Vectorized Numba kernels\nMatrix computation approaching C/C++ speeds",
            icon="",
        )

        c4 = FlashyCard(
            "Usable n,k Identification",
            "Strict physical constraints + equation export\nStable results for lab/production use",
            icon="",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

        self.tabs.addTab(self.perf_tab, "Why CERTUS?")

        # Spectrum Tab (0): visible by default to see T/R and n,k after optimization.
        self.tabs.setCurrentIndex(0)

        # Add plot container instead of tabs directly
        self.right_splitter.addWidget(plot_container)

        self._create_status_bar()

        log_widget = self._build_log_container()
        self.right_splitter.addWidget(log_widget)
        self.right_splitter.setSizes([800, 250])

        self.main_splitter.addWidget(self.right_splitter)
        self.main_splitter.setSizes([350, 700])  # Initial ratio

    def _add_main_control_buttons(self, left_layout: QVBoxLayout) -> None:
        """Create and add main control buttons to the left panel."""
        self.btn_run = QPushButton("START OPTIMIZATION")
        self.btn_run.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setToolTip("Start the global optimization process.")
        self.btn_run.clicked.connect(self.run_optimization)
        left_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("STOP Calculation")
        self.btn_stop.setObjectName(OBJ.DANGER_BUTTON)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setToolTip("Stop the current optimization safely.")
        self.btn_stop.clicked.connect(self.stop_optimization)
        self.btn_stop.setEnabled(False)
        left_layout.addWidget(self.btn_stop)

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)
        left_layout.addWidget(self.clear_btn)

        # --- Data tab: table + toolbar ---

        data_tab = QWidget()

        data_tab_layout = QVBoxLayout(data_tab)

        data_tab_layout.setContentsMargins(4, 4, 4, 4)

        data_tab_layout.setSpacing(4)

        # Toolbar row

        data_toolbar = QWidget()

        data_toolbar_layout = QHBoxLayout(data_toolbar)

        data_toolbar_layout.setContentsMargins(0, 0, 0, 0)

        data_toolbar_layout.setSpacing(6)

        self.btn_copy_nk = create_styled_button(" Copy n,k", variant="secondary")

        self.btn_copy_nk.setToolTip("Copy n and k values to clipboard (TSV format)")

        self.btn_copy_nk.clicked.connect(self._copy_nk_to_clipboard)

        self.btn_copy_nk.setEnabled(False)

        data_toolbar_layout.addWidget(self.btn_copy_nk)

        self.btn_copy_params = create_styled_button(" Copy Parameters", variant="secondary")

        self.btn_copy_params.setToolTip("Copy analytical parameters to clipboard")

        self.btn_copy_params.clicked.connect(self._copy_params_to_clipboard)

        self.btn_copy_params.setEnabled(False)

        data_toolbar_layout.addWidget(self.btn_copy_params)

        data_toolbar_layout.addStretch()

        data_tab_layout.addWidget(data_toolbar)

        # Tables row: Spectral Data (Left) + Model Parameters (Right)

        tables_container = QWidget()

        tables_layout = QHBoxLayout(tables_container)

        tables_layout.setContentsMargins(0, 0, 0, 0)

        tables_layout.setSpacing(10)

        # 1. Main spectral table

        self.table_res = ExcelTableWidget()

        tables_layout.addWidget(self.table_res, 3)  # Stretching 3:1

        # 2. Parameters table

        self.table_params = ExcelTableWidget()

        self.table_params.setColumnCount(2)

        self.table_params.setHorizontalHeaderLabels(["Parameter", "Value"])

        self.table_params.setFixedWidth(280)

        self.table_params.verticalHeader().setVisible(False)

        self.table_params.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        tables_layout.addWidget(self.table_params, 1)

        data_tab_layout.addWidget(tables_container)

        self.tabs.addTab(data_tab, "Data")

    def _build_log_container(self) -> QWidget:
        """Build log container with shared CertusLogPanel."""

        panel = CertusLogPanel(title="LOGS", visible=True)

        self.log_text = panel.log_text

        panel.copied.connect(functools.partial(self.lbl_status.setText, "Logs copied to clipboard!"))

        self._log_panel = panel

        return panel

    def _create_input_group(self) -> Any:

        c = CertusCard("Input Data")

        l = c.body

        self.btn_load = QPushButton(" Load Spectrum File")

        self.btn_load.setToolTip(
            "Load a CSV/Excel file with Transmission and/or Reflectance data.\n"
            "Expected columns: lambda (nm), T (%), R (%)  or any subset."
        )

        self.btn_load.clicked.connect(self.load_file)

        l.addWidget(self.btn_load)

        self.lbl_file = QLabel("No file loaded")

        self.lbl_file.setStyleSheet(f"font-style: italic; color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        l.addWidget(self.lbl_file)

        # Label to display detected data type

        self.lbl_data_type = QLabel("")

        self.lbl_data_type.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 11px;")

        l.addWidget(self.lbl_data_type)

        # Normalization options

        h_norm = QHBoxLayout()

        self.chk_normalized = QCheckBox("Normalized (T/T_sub, R/T_sub)")

        self.chk_normalized.setChecked(True)

        self.chk_normalized.setToolTip(
            "If checked, the measured T and R are normalized by reference to the bare substrate.\n"
            "Uncheck for absolute transmittance/reflectance data."
        )

        h_norm.addWidget(self.chk_normalized)

        l.addLayout(h_norm)

        return c

    def _create_substrate_group(self) -> Any:
        """Create substrate selection group with frosted glass option"""

        c = CertusCard("substrate")

        l = c.body

        self.rb_standard = QRadioButton("Standard (transparent substrate)")

        self.rb_standard.setToolTip(
            "Use for transparent substrates (SiO2, BK7, D263T, B270i).\nBoth T and R data are used for fitting."
        )

        self.rb_frosted_glass = QRadioButton("Frosted Glass (infinite substrate, R only)")

        self.rb_frosted_glass.setToolTip(
            "Use for opaque / frosted glass substrates where only reflectance (R) is measured.\n"
            "T data is ignored in this mode."
        )

        self.rb_standard.setChecked(True)

        self.substrate_mode_group = QButtonGroup(self)

        self.substrate_mode_group.addButton(self.rb_standard, 0)

        self.substrate_mode_group.addButton(self.rb_frosted_glass, 1)

        l.addWidget(self.rb_standard)

        l.addWidget(self.rb_frosted_glass)

        # substrate ComboBox (always enabled now)

        h_sub = QHBoxLayout()

        h_sub.addWidget(QLabel("Material:"))

        self.cb_sub = QComboBox()

        self.cb_sub.addItems(["SiO2", "N-BK7", "D263T", "Al2O3", "B270i", "Si"])

        self.cb_sub.setToolTip(
            "substrate material. Determines the dispersion model used for n_substrate(\u03bb).\n"
            "Al2O3: n(\u03bb) via Sellmeier equation (materials DB). "
            "Absorbing mode uses sapphire fresnel.xlsx only for k(\u03bb).\n"
            "Si (Silicon): absorbing mode auto from clues.xlsx."
        )

        h_sub.addWidget(self.cb_sub)

        l.addLayout(h_sub)

        # Connection for mode change

        self.rb_frosted_glass.toggled.connect(self._on_substrate_mode_changed)

        self.rb_standard.toggled.connect(self._on_substrate_mode_changed)

        # Info label for frosted glass

        self.lbl_frosted_info = QLabel("i Frosted: measures R or Rnu (1 side), never R/Tnu")

        self.lbl_frosted_info.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-style: italic;")

        self.lbl_frosted_info.setVisible(False)

        l.addWidget(self.lbl_frosted_info)

        #  Absorbing substrate section

        self.chk_absorbing_sub = QCheckBox("Absorbent substrate (k = 0)")

        self.chk_absorbing_sub.setChecked(False)

        self.chk_absorbing_sub.setToolTip(
            "Enable if the substrate has a non-negligible k(\u03bb) coefficient.\n"
            "Al2O3: n(\u03bb) remains equation-based; k(\u03bb) is available only if "
            "sapphire fresnel.xlsx contains a k column."
        )

        l.addWidget(self.chk_absorbing_sub)

        self._absorbing_sub_widget = QWidget()

        abs_layout = QVBoxLayout(self._absorbing_sub_widget)

        abs_layout.setContentsMargins(12, 2, 0, 2)

        abs_layout.setSpacing(4)

        # k_sub CSV import row

        h_ksub = QHBoxLayout()

        self.btn_import_ksub = QPushButton("Import k_sub (CSV lambda,k)")

        self.btn_import_ksub.setFixedHeight(24)

        self.btn_import_ksub.setToolTip(
            "Import a 2-column CSV file with substrate extinction coefficient:\nColumn 1: lambda (nm) | Column 2: k_sub"
        )

        self.lbl_ksub_file = QLabel("(no files)")

        self.lbl_ksub_file.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        h_ksub.addWidget(self.btn_import_ksub)

        h_ksub.addWidget(self.lbl_ksub_file, 1)

        abs_layout.addLayout(h_ksub)

        # substrate thickness row

        h_dthick = QHBoxLayout()

        h_dthick.addWidget(QLabel("Thickness sub. (mm):"))

        self.sb_sub_thickness_mm = QDoubleSpinBox()

        self.sb_sub_thickness_mm.setRange(0.0, 100.0)  # 0 = transparent substrate (k=0 everywhere)

        self.sb_sub_thickness_mm.setValue(1.0)

        self.sb_sub_thickness_mm.setDecimals(3)

        self.sb_sub_thickness_mm.setSingleStep(0.1)

        self.sb_sub_thickness_mm.setFixedWidth(90)

        self.sb_sub_thickness_mm.setToolTip(
            "Physical thickness of the substrate (mm). Used to model inconsistent absorption.\n"
            "Set to 0 to ignore substrate absorption (equivalent to k_sub = 0 everywhere)."
        )

        h_dthick.addWidget(self.sb_sub_thickness_mm)

        h_dthick.addStretch()

        abs_layout.addLayout(h_dthick)

        self._absorbing_sub_widget.setVisible(False)

        l.addWidget(self._absorbing_sub_widget)

        # Internal storage for loaded k_sub data (raw, before interpolation)

        self._ksub_raw_wls: np.ndarray | None = None

        self._ksub_raw_k: np.ndarray | None = None

        self.chk_absorbing_sub.toggled.connect(self._on_absorbing_sub_toggled)

        self.btn_import_ksub.clicked.connect(self._on_import_ksub)

        # Auto-configure absorbing substrate when substrate selection changes

        self.cb_sub.currentIndexChanged.connect(self._on_substrate_changed)

        return c

    def _create_config_group(self) -> Any:

        c = CertusCard("Configuration")

        l = QGridLayout()

        c.body.addLayout(l)

        l.setVerticalSpacing(8)

        l.addWidget(QLabel("Thickness (nm):"), 0, 0)

        h = QHBoxLayout()

        self.sb_dmin = QDoubleSpinBox()

        self.sb_dmin.setRange(3, 50000)

        self.sb_dmin.setValue(50)

        self.sb_dmin.setToolTip("Minimum film thickness to search (nm). Optimization will not go below this.")

        self.sb_dmax = QDoubleSpinBox()

        self.sb_dmax.setRange(3, 50000)

        self.sb_dmax.setValue(1000)

        self.sb_dmax.setToolTip("Maximum film thickness to search (nm). Optimization will not exceed this.")

        self.sb_dmin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_dmin.setDecimals(1)

        self.sb_dmax.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_dmax.setDecimals(1)

        h.addWidget(self.sb_dmin)

        h.addWidget(QLabel("-"))

        h.addWidget(self.sb_dmax)

        l.addLayout(h, 0, 1)

        l.addWidget(QLabel("lambda Range (nm):"), 1, 0)

        h2 = QHBoxLayout()

        self.sb_lmin = QDoubleSpinBox()

        self.sb_lmin.setRange(185, 5200)

        self.sb_lmin.setValue(300)

        self.sb_lmin.setToolTip("Start of the optimization wavelength range (nm).")

        self.sb_lmax = QDoubleSpinBox()

        self.sb_lmax.setRange(185, 5200)

        self.sb_lmax.setValue(900)

        self.sb_lmax.setToolTip("End of the optimization wavelength range (nm).")

        self.sb_lmin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_lmin.setDecimals(1)

        self.sb_lmax.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_lmax.setDecimals(1)

        h2.addWidget(self.sb_lmin)

        h2.addWidget(QLabel("-"))

        h2.addWidget(self.sb_lmax)

        l.addLayout(h2, 1, 1)

        # R/T Weights

        l.addWidget(QLabel("Weights (T/R):"), 2, 0)

        h_weights = QHBoxLayout()

        self.sb_weight_T = QDoubleSpinBox()

        self.sb_weight_T.setRange(0.0, 10.0)

        self.sb_weight_T.setValue(1.0)

        self.sb_weight_T.setDecimals(2)

        self.sb_weight_T.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_weight_T.setToolTip(
            "Relative weight given to Transmittance (T) in the cost function.\n"
            "Set to 0 to ignore T data during optimization."
        )

        self.sb_weight_R = QDoubleSpinBox()

        self.sb_weight_R.setRange(0.0, 10.0)

        self.sb_weight_R.setValue(1.0)

        self.sb_weight_R.setDecimals(2)

        self.sb_weight_R.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_weight_R.setToolTip(
            "Relative weight given to Reflectance (R) in the cost function.\n"
            "Set to 0 to ignore R data during optimization."
        )

        h_weights.addWidget(QLabel("T: "))

        h_weights.addWidget(self.sb_weight_T)

        h_weights.addWidget(QLabel("R: "))

        h_weights.addWidget(self.sb_weight_R)

        l.addLayout(h_weights, 2, 1)

        sep = QFrame()

        sep.setFrameShape(QFrame.Shape.HLine)

        sep.setStyleSheet(f"color: {CertusTheme.BORDER};")

        l.addWidget(sep, 3, 0, 1, 2)

        self.chk_exclude = QCheckBox("Exclude Data Range")

        self.chk_exclude.setToolTip(
            "Exclude a specific wavelength range from the cost function.\n"
            "Useful for masking saturated or noisy regions (e.g. laser line)."
        )

        self.chk_exclude.toggled.connect(self._toggle_exclude)

        l.addWidget(self.chk_exclude, 4, 0, 1, 2)

        h_ex = QHBoxLayout()

        self.sb_ex_min = QDoubleSpinBox()

        self.sb_ex_min.setRange(185, 5200)

        self.sb_ex_min.setValue(400)

        self.sb_ex_min.setToolTip("Start of the excluded wavelength range (nm).")

        self.sb_ex_max = QDoubleSpinBox()

        self.sb_ex_max.setRange(185, 5200)

        self.sb_ex_max.setValue(450)

        self.sb_ex_max.setToolTip("End of the excluded wavelength range (nm).")

        self.sb_ex_min.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_ex_min.setDecimals(1)

        self.sb_ex_max.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.sb_ex_max.setDecimals(1)

        self.sb_ex_min.setEnabled(False)

        self.sb_ex_max.setEnabled(False)

        h_ex.addWidget(self.sb_ex_min)

        h_ex.addWidget(QLabel("-"))

        h_ex.addWidget(self.sb_ex_max)

        l.addLayout(h_ex, 5, 0, 1, 2)

        self.sb_ex_min.valueChanged.connect(self._update_plot_exclusion)

        self.sb_ex_max.valueChanged.connect(self._update_plot_exclusion)

        # OH- band exclusion checkbox

        self.chk_oh_band = QCheckBox("Remove OH⁻ band (E-band)")

        self.chk_oh_band.setToolTip(
            "Automatically excludes 1360-1460 nm range.\n"
            "This corresponds to the E-band, the 2nd harmonic (overtone)\n"
            "of the OH⁻ stretching vibration in silica optical fibers.\n"
            "This absorption band can interfere with optical measurements."
        )

        self.chk_oh_band.toggled.connect(self._toggle_oh_band)

        l.addWidget(self.chk_oh_band, 6, 0, 1, 2)

        # High Precision Toggle

        self.chk_high_precision = QCheckBox("High Precision (Slower)")

        self.chk_high_precision.setToolTip(
            "Increases global search evaluations from 20k to 80k.\n"
            "Use this if the solution seems stuck in a local minimum."
        )

        self.chk_high_precision.setChecked(False)  # Default to Standard

        self._core_logger = logging.getLogger("CERTUS")

        l.addWidget(self.chk_high_precision, 7, 0, 1, 2)

        return c

    def _create_status_bar(self) -> None:

        sb = QStatusBar()

        self.setStatusBar(sb)

        sb.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        container = QWidget()

        l = QHBoxLayout(container)

        l.setContentsMargins(10, 0, 10, 0)

        self.lbl_status = QLabel("Initializing...")

        self.lbl_dice = QLabel(" 0")

        self.lbl_dice.setStyleSheet(f"font-weight: bold; color: {CertusTheme.INFO_TEXT};")

        self.progress_widget = EnhancedProgressWidget()

        self.lbl_zoom = QLabel("Zoom 100%")
        self.lbl_zoom.setStyleSheet(f"font-weight: 600; color: {CertusTheme.TEXT_SUB};")

        l.addWidget(self.lbl_status)

        l.addStretch()

        l.addWidget(self.lbl_zoom)

        l.addWidget(self.lbl_dice)

        l.addWidget(self.progress_widget)

        sb.addPermanentWidget(container, 1)

        # 'Show Details' button for toggling logs

        self.toggle_details_btn = QPushButton("Show Details")

        self.toggle_details_btn.setToolTip("Toggle optimization details log display.")

        self.toggle_details_btn.setCheckable(True)

        self.toggle_details_btn.setFixedWidth(100)

        self.toggle_details_btn.setStyleSheet(f"""

            QPushButton {{ background-color: {CertusTheme.SECONDARY}; color: white; border: 1px solid {CertusTheme.BORDER}; border-radius: 3px; padding: 2px; font-size: 11px; font-weight: bold; }}

            QPushButton:checked {{ background-color: {CertusTheme.PRIMARY}; }}

            QPushButton:hover {{ background-color: {CertusTheme.SURFACE_HOVER}; color: {CertusTheme.PRIMARY}; }}

        """)

        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        sb.addPermanentWidget(self.toggle_details_btn)

        # --- Theme Switcher ---

        # Discreetly added to status bar

        self.btn_theme = CertusThemeToggle(self)

        sb.addPermanentWidget(self.btn_theme)

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

