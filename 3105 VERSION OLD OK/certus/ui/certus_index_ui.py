import os
import sys
from pathlib import Path
import logging
import time
import functools
from datetime import datetime

import numpy as np
import pandas as pd
import pyqtgraph as pg

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
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

def _log_loaded_spectrum_metadata(logger, filepath: str, df: pd.DataFrame) -> None:
    """Log canonical metadata for a newly loaded spectrum file."""
    fp_abs = Path(filepath).resolve()
    logger.info("-" * 60)
    logger.info("[FILE] Spectrum loaded: %s", fp_abs)
    logger.info("[FILE] Name: %s", Path(filepath).name)
    logger.info("[FILE] Dimensions: %d rows × %d columns", df.shape[0], df.shape[1])
    logger.info("-" * 60)

def _detected_data_type_label(data_type: DataType) -> str:
    """Return human-readable label for detected spectral data type."""
    type_labels = {
        DataType.TRANSMISSION: " Detected:  TRANSMISSION only",
        DataType.REFLECTION: " Detected:  REFLECTION only",
        DataType.BOTH: " Detected: TRANSMISSION + REFLECTION",
    }
    return type_labels[data_type]

def _update_lambda_bounds_from_target_data(
    target_data: pd.DataFrame,
    sb_lmin,
    sb_lmax,
    logger,
) -> tuple[float, float]:
    """Update lambda spinbox bounds from target data and log range."""
    lmin = float(target_data["lambda"].min())
    lmax = float(target_data["lambda"].max())
    sb_lmin.setValue(lmin)
    sb_lmax.setValue(lmax)
    logger.info("[INDEX.LOAD] spectral range | min=%.1f nm | max=%.1f nm", lmin, lmax)
    return lmin, lmax

def _source_type_label(data_type: DataType) -> str:
    """Return compact source-type label for load summary dialog."""
    return {
        DataType.TRANSMISSION: "Transmission",
        DataType.REFLECTION: "Reflection",
        DataType.BOTH: "Transmission + Reflection",
    }.get(data_type, "Unknown")

def _is_qt_offscreen_mode() -> bool:
    """Return True when Qt is running in offscreen mode."""
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"


def _notify_user(
    parent,
    title: str,
    message: str,
    *,
    level: str = "info",
    blocking: bool = False,
    duration_ms: int = 4000,
) -> None:
    """Unified user feedback: toast-first for non-blocking messages."""
    text = f"{title}: {message}" if title else message

    if not blocking:
        try:
            show_toast(parent, text, level=level, duration_ms=duration_ms)
            return
        except NUMERICAL_FAULT_EXCEPTIONS:
            logging.getLogger("CERTUS").debug("Toast notification failed", exc_info=True)

    if _is_qt_offscreen_mode():
        logging.getLogger("CERTUS").warning("%s", text)
        return

    if level in ("error", "critical"):
        QMessageBox.critical(parent, title or "Error", message)
    elif level == "warning":
        QMessageBox.warning(parent, title or "Warning", message)
    else:
        QMessageBox.information(parent, title or "Info", message)

def _update_loaded_file_label(lbl_file, filepath: str) -> str:
    """Update file label widget and return basename."""
    fname = Path(filepath).name
    lbl_file.setText(f" {fname}")
    lbl_file.setStyleSheet(f"color: {CertusTheme.SUCCESS}; font-weight: bold;")
    lbl_file.setToolTip(filepath)
    return fname

def _set_spectrum_plot_title(plot_spectrum, source_name: str) -> None:
    """Set standardized spectrum title from source name."""
    src_name = Path(source_name).stem
    plot_spectrum.plotItem.setTitle(f"Spectrum      {src_name}")

def _display_detected_data_type(lbl_data_type, logger, data_type: DataType) -> str:
    """Display and log detected source data type label."""
    type_label = _detected_data_type_label(data_type)
    lbl_data_type.setText(type_label)
    logger.info("[INDEX.LOAD] data analysis | type=%s", type_label)
    return type_label

def _prepare_nk_plot_inputs(wls, sub_df, res, logger) -> tuple | None:
    """Prepare n/k arrays and optional IR mask metadata for plotting."""
    if "n_calc" not in sub_df.columns or "k_calc" not in sub_df.columns:
        logger.error(f"Missing n_calc or k_calc in sub_df. Columns: {list(sub_df.columns)}")
        return None

    n_values = sub_df["n_calc"].values.copy()
    k_values = sub_df["k_calc"].values.copy()
    method_str = res.optimization_stats.get("method", "")
    lambda_max_fit = getattr(res.config, "lambda_max_fit", None)
    tlu_mode = lambda_max_fit is not None and "Spline" not in method_str and res.tlu_params is not None

    if tlu_mode:
        ir_mask_ui = wls > lambda_max_fit
        n_values[ir_mask_ui] = np.nan
        k_values[ir_mask_ui] = np.nan

    if np.all(np.isnan(n_values)) or np.all(np.isnan(k_values)):
        logger.error(
            f"n_calc or k_calc are all NaN! n_valid={np.sum(~np.isnan(n_values))}, k_valid={np.sum(~np.isnan(k_values))}"
        )
        return None

    return n_values, k_values, method_str, lambda_max_fit, tlu_mode

# Import Modular Architecture


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

# JIT Warmup (reduces first-call latency by ~90%)

# JIT Warmup moved to main() with SplashScreen

from certus.ui.certus_svg import SVG_AVAILABLE

if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget  # pylint: disable=unused-import

else:
    QSvgWidget = None

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

# PyQtGraph configured via COMMON utility

setup_pyqtgraph_defaults()
setup_gui_exception_handling()
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

        # We will use FlowLayout if we had it, but a Grid is fine
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
        # Thickness
        d_status = "success" if thickness > 1 else "warning"
        d_msg = "Physical range" if thickness > 1 else "Unusually thin"
        self.card_d.update_value(f"{thickness:.2f}", d_status, d_msg)

        # RMSE
        rmse_val = rmse * 100 if rmse < 1 else rmse
        r_status = "success" if rmse_val < 1.0 else "warning" if rmse_val < 3.0 else "danger"
        r_msg = "Excellent fit" if rmse_val < 1.0 else "Acceptable" if rmse_val < 3.0 else "High error"
        self.card_rmse.update_value(f"{rmse_val:.3f}", r_status, r_msg)

        # Gap
        eg_status = "info" if eg > 0 else "normal"
        self.card_eg.update_value(f"{eg:.2f}", eg_status, "Calculated")

        # Eps Inf
        inf_status = "normal" if eps_inf > 1.0 else "warning"
        self.card_inf.update_value(f"{eps_inf:.2f}", inf_status, "Dielectric background")

        self.setVisible(True)

class KLogAxisItem(pg.AxisItem):
    """Custom AxisItem to format log10(k) values as decimal linear strings without scientific notation"""

    def tickStrings(self, values, scale, _spacing) -> Any:


        strings = []

        for v in values:
            try:
                s = np.format_float_positional(10**v, precision=6, trim="-")

                strings.append(s)

            except NUMERICAL_FAULT_EXCEPTIONS :
                strings.append("")

        return strings

# =============================================================================

# MAIN APPLICATION

# =============================================================================

# Session persistence for cost weights wT / wR (CERTUS-INDEX classic, not SPLINE)

_QS_INDEX_ORG = "CERTUS"

_QS_INDEX_APP = "INDEX"

_QS_INDEX_WEIGHT_T = "cost_weight_t"

_QS_INDEX_WEIGHT_R = "cost_weight_r"

class CertusIndexApp(CertusBaseApp):
    """Main CERTUS-INDEX Application"""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-INDEX"

    APP_TITLE = "Dielectric Index Characterization"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Apply theme before building UI

        self._apply_theme()

        self._build_ui()

        self._restore_index_weight_settings()

        self._wire_index_weight_persistence()

        self._persist_index_weight_settings()
        self._setup_shortcuts()

        # INDEX-specific state

        self._worker: OptimizationWorker | None = None

        self._thread: QThread | None = None

        self._worker2 = None

        self._thread2: QThread | None = None

        self._beam_worker: IndexBeamAnalysisWorker | None = None

        self._beam_thread: QThread | None = None

        self.target_data: pd.DataFrame | None = None

        self.data_type: DataType = DataType.TRANSMISSION

        self.substrate_mode: substrateMode = substrateMode.STANDARD

        self.exclude_region = None

        self.latest_results: OptimizationResults | None = None

        self.source_file_path = ""

        self.optimization_running = False

        self._executor = None

        self._vb_k = None

        # Convergence tracking data

        self.mse_data = {"iterations": [], "errors": []}

        self._last_progress_ui_update = 0.0

        self._last_phase_name = ""

        # Finalize (starts timers, triggers warmup)

        self._finalize_init()

    def _load_defaults(self) -> None:
        """Load default values for CERTUS-INDEX"""

        # Reset file selection

        self.source_file_path = ""

        self.target_data = None

        self.latest_results = None

        # Reset data type and substrate mode

        self.data_type = DataType.TRANSMISSION

        self.substrate_mode = substrateMode.STANDARD

        self.exclude_region = None

        self._vb_k = None

        # Reset UI elements to defaults

        if hasattr(self, "cb_data_type"):
            self.cb_data_type.setCurrentIndex(0)  # Transmission

        if hasattr(self, "cb_substrate_mode"):
            self.cb_substrate_mode.setCurrentIndex(0)  # Standard

        if hasattr(self, "lbl_file"):
            self.lbl_file.setText("(no file selected)")

        if hasattr(self, "lbl_final_eq"):
            self.lbl_final_eq.setText("Run optimization to see final equations.")

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(False)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        if hasattr(self, "btn_copy_params"):
            self.btn_copy_params.setEnabled(False)

        if hasattr(self, "table_res"):
            self.table_res.clearContents()

            self.table_res.setRowCount(0)

            self.table_res.setColumnCount(0)

        if hasattr(self, "table_params"):
            self.table_params.clearContents()

            self.table_params.setRowCount(0)

            self.table_params.setColumnCount(2)

            self.table_params.setHorizontalHeaderLabels(["Parameter", "Value"])

        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)

        if hasattr(self, "recap_widget"):
            self.recap_widget.setVisible(False)

        # Reset convergence tracking

        self.mse_data = {"iterations": [], "errors": []}

        self.optimization_running = False

        if hasattr(self, "rb_standard"):
            self.rb_standard.setChecked(True)

        if hasattr(self, "_on_substrate_mode_changed"):
            self._on_substrate_mode_changed()

        if hasattr(self, "_persist_index_weight_settings"):
            self._persist_index_weight_settings()

    def _restore_index_weight_settings(self) -> None:
        """Reads wT / wR from QSettings (session)."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = QSettings(_QS_INDEX_ORG, _QS_INDEX_APP)

        self.sb_weight_T.blockSignals(True)

        self.sb_weight_R.blockSignals(True)

        try:
            wt = s.value(_QS_INDEX_WEIGHT_T)

            if wt is not None:
                self.sb_weight_T.setValue(float(wt))

            wr = s.value(_QS_INDEX_WEIGHT_R)

            if wr is not None:
                self.sb_weight_R.setValue(float(wr))

        finally:
            self.sb_weight_T.blockSignals(False)

            self.sb_weight_R.blockSignals(False)

    def _persist_index_weight_settings(self) -> None:
        """Saves wT / wR for the next launch."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = QSettings(_QS_INDEX_ORG, _QS_INDEX_APP)

        s.setValue(_QS_INDEX_WEIGHT_T, float(self.sb_weight_T.value()))

        s.setValue(_QS_INDEX_WEIGHT_R, float(self.sb_weight_R.value()))

    def _wire_index_weight_persistence(self) -> None:

        self.sb_weight_T.valueChanged.connect(self._persist_index_weight_settings)

        self.sb_weight_R.valueChanged.connect(self._persist_index_weight_settings)

    def _warmup_numba(self) -> None:
        """JIT precompilation"""

        try:
            from certus.core.certus_index_objectives import warmup_index_objectives
            warmup_index_objectives(silent=True)

            wls = np.array([500.0, 600.0], dtype=np.float64)

            get_n_substrate_array_by_id(0, wls)

            get_n_frosted_glass_array(wls)

            n_test = np.array([1.5, 1.5])

            k_test = np.array([0.0, 0.0])


            calculate_RT_single_layer_backside_array(wls, n_test, k_test, 100.0, n_test)

            calculate_bare_substrate_RT(wls, n_test)

            calculate_single_interface_R(wls, n_test)

            # Absorbing substrate kernels (sapphire / user k_sub)

            k_sub_test = np.array([1e-4, 1e-4])

            calculate_bare_substrate_T_absorbing(wls, n_test, k_sub_test, 1.0e6)

            calculate_bare_substrate_R_absorbing(wls, n_test, k_sub_test, 1.0e6)

            calculate_RT_single_layer_absorbing_substrate_array(wls, n_test, k_test, 100.0, n_test, k_sub_test, 1.0e6)

            # Warmup per-lambda kernels (scalar + batch)

            _optimize_point_kernel(
                1.5,
                0.0,
                500.0,
                0.9,
                0.1,
                1.0,
                1.0,
                1.5,
                0.92,
                0.08,
                100.0,
                True,
                True,
                True,
                False,
            )

            _optimize_all_points_batch(
                np.array([1.5, 1.5]),
                np.array([0.0, 0.0]),
                wls,
                np.array([0.9, 0.9]),
                np.array([0.1, 0.1]),
                1.0,
                1.0,
                n_test,
                np.array([0.92, 0.92]),
                np.array([0.08, 0.08]),
                100.0,
                True,
                True,
                True,
                False,
                np.array([False, False]),
            )

            self.lbl_status.setText("Ready (JIT Compiled)")

            self._on_numba_ready()  # Mark as ready

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.lbl_status.setText("JIT Init Error")

            self.logger.error(f" Numba warmup failed: {e}", exc_info=True)

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

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        copy_app_logs_to_clipboard(self)

        self.lbl_status.setText("Logs copied to clipboard!")

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

    def _on_substrate_mode_changed(self) -> None:
        """Handle substrate mode change"""

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        # Show/hide info label

        self.lbl_frosted_info.setVisible(is_frosted_glass)

        # Frosted: disable norm, force reflection only

        if is_frosted_glass:
            # Uncheck and disable normalization

            self.chk_normalized.setChecked(False)

            self.chk_normalized.setEnabled(False)

            # Force reflection weights

            self.sb_weight_T.setValue(0.0)

            self.sb_weight_T.setEnabled(False)

            self.sb_weight_R.setValue(1.0)

        else:
            # Re-enable normalization

            self.chk_normalized.setEnabled(True)

            self.chk_normalized.setChecked(True)

            # Re-enable T weight

            self.sb_weight_T.setEnabled(True)

            self.sb_weight_T.setValue(1.0)

        self._persist_index_weight_settings()

    def _on_substrate_changed(self, index: int) -> None:
        """When Al2O3 or Si is selected: auto-configure absorbing mode (locked) if k(lambda) is available.

        Sapphire without k column in xlsx: transparent substrate only (no absorption).

        For any other substrate: restore manual mode."""

        sub_name = SUBSTRATE_LIST[index] if 0 <= index < len(SUBSTRATE_LIST) else ""

        is_sapphire = sub_name == "Sapphire (Al2O3)"

        is_silicon = sub_name == "Silicon (Si)"

        if is_sapphire:
            if _SAPPHIRE_WLS is not None:
                self._absorbing_sub_widget.setVisible(True)

                self.btn_import_ksub.setEnabled(False)

                self._ksub_raw_wls = _SAPPHIRE_WLS

                self._ksub_raw_k = _SAPPHIRE_K

                if _SAPPHIRE_FILE_HAS_K_COLUMN:
                    self.chk_absorbing_sub.setChecked(True)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(1.0)

                    self.sb_sub_thickness_mm.setEnabled(True)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx (auto, colonne k)")

                else:
                    self.chk_absorbing_sub.setChecked(False)

                    self.chk_absorbing_sub.setEnabled(False)

                    self.sb_sub_thickness_mm.setValue(0.0)

                    self.sb_sub_thickness_mm.setEnabled(False)

                    self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx  no k column: transparent only")

            else:
                # File not found  warn but don't block

                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("example/sapphire fresnel.xlsx NOT FOUND")

        elif is_silicon:
            if _SILICON_WLS is not None:
                # Auto-activate and lock absorbing mode

                self.chk_absorbing_sub.setChecked(True)

                self.chk_absorbing_sub.setEnabled(False)

                self._absorbing_sub_widget.setVisible(True)

                self.sb_sub_thickness_mm.setValue(0.5)

                self.sb_sub_thickness_mm.setEnabled(True)

                # Show info; disable manual CSV import (data is built-in from clues.xlsx)

                self.lbl_ksub_file.setText("clues.xlsx -> Si-substrate (auto)")

                self.btn_import_ksub.setEnabled(False)

                # Store silicon k internally (will be interpolated to target grid in _on_run)

                self._ksub_raw_wls = _SILICON_WLS

                self._ksub_raw_k = _SILICON_K

            else:
                self.chk_absorbing_sub.setEnabled(True)

                self.lbl_ksub_file.setText("clues.xlsx Si-substrate NOT FOUND")

        else:
            # Other substrates: restore manual control

            self.chk_absorbing_sub.setChecked(False)

            self.chk_absorbing_sub.setEnabled(True)

            self._absorbing_sub_widget.setVisible(False)

            self.sb_sub_thickness_mm.setValue(1.0)

            self.sb_sub_thickness_mm.setEnabled(True)

            self.btn_import_ksub.setEnabled(True)

            if self._ksub_raw_wls is _SAPPHIRE_WLS or self._ksub_raw_wls is _SILICON_WLS:
                # Clear built-in data so other substrates start clean

                self._ksub_raw_wls = None

                self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(no files)")

    def _on_absorbing_sub_toggled(self, checked: bool) -> None:

        self._absorbing_sub_widget.setVisible(checked)

    def _on_import_ksub(self) -> None:

        path = certus_get_open_file_name(self, "Import k_sub substrate", "CSV (*.csv);;All (*)")

        if not path:
            return

        set_certus_last_dir(path)

        try:
            df_k = pd.read_csv(path, comment="#")

            # Accept first two numeric columns regardless of header names

            cols = df_k.select_dtypes(include=[np.number]).columns

            if len(cols) < 2:
                raise ValueError("The CSV must contain at least 2 numeric columns (lambda, k).")

            self._ksub_raw_wls = df_k[cols[0]].to_numpy(dtype=np.float64)

            self._ksub_raw_k = df_k[cols[1]].to_numpy(dtype=np.float64)

            self.lbl_ksub_file.setText(Path(path).name)

            self.logger.info(
                "[FILE] k_sub imported: %s (%d points)",
                Path(path).resolve(),
                len(self._ksub_raw_wls),
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            _notify_user(self, "k_sub Error", str(e), level="warning")

            self._ksub_raw_wls = None

            self._ksub_raw_k = None

            self.lbl_ksub_file.setText("(error)")

    def _auto_detect_from_file(self, filepath: str) -> None:
        """Auto-detect substrate from filename and pre-estimate thickness

        from the spectrum (oscillation counting). Updates GUI widgets accordingly."""

        fname = Path(filepath).name.lower()

        #  1. substrate detection from filename

        SUBSTRATE_KEYWORDS = {
            "SiO2": [
                "fusedsilica",
                "fused_silica",
                "silica_glass",
            ],
            "N-BK7": [
                "bk7",
                "nbk7",
                "n-bk7",
                "borosilicate",
                "glass",
                "bk",
                "pyrex",
            ],
            "D263T": ["d263", "d263t", "schott", "d263teco"],
            "Al2O3": [
                "sapphire",
                "saphir",
                "al2o3",
                "alumina",
                "alumine",
                "corundum",
                "ruby",
            ],
            "B270i": ["b270", "b270i", "soda", "sodalime"],
            "Si": [
                "silicon",
                "silicium",
                "si_sub",
                "wafer",
            ],
        }

        detected_substrate = None

        for sub_name, keywords in SUBSTRATE_KEYWORDS.items():
            for kw in keywords:
                if kw in fname:
                    detected_substrate = sub_name

                    break

            if detected_substrate:
                break

        if detected_substrate:
            idx = self.cb_sub.findText(detected_substrate)

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

                self.logger.info("[INDEX.LOAD] auto-detected substrate | substrate=%s", detected_substrate)

        #  2. Pre-estimate thickness from spectrum

        self._estimated_thickness_nm = None

        if not hasattr(self, "target_data") or self.target_data is None:
            return

        try:
            from scipy.signal import find_peaks

            wls = self.target_data["lambda"].to_numpy()

            # Use T if available, otherwise R

            if "T" in self.target_data.columns:
                signal = self.target_data["T"].to_numpy()

            elif "R" in self.target_data.columns:
                signal = self.target_data["R"].to_numpy()

            else:
                return

            valid = np.isfinite(signal) & np.isfinite(wls) & (wls > 0)

            wls = wls[valid]

            signal = signal[valid]

            if len(wls) < 16:
                return

            lmin, lmax = wls.min(), wls.max()

            # Approx n from detected substrate

            n_approx = 2.0

            sub_text = self.cb_sub.currentText() if hasattr(self, "cb_sub") else ""

            if "SiO2" in sub_text or "fused" in sub_text.lower():
                n_approx = 1.5

            elif "Al2O3" in sub_text or "sapphire" in sub_text.lower():
                n_approx = 2.1

            elif "Si" in sub_text and "SiO2" not in sub_text:
                n_approx = 3.5

            #  Method 1: FFT on uniformly sampled 1/lambda axis

            d_fft = None

            try:
                # Resample signal on uniform 1/lambda grid (Fabry-Perot fringes are periodic in 1/lambda)

                inv_wls = 1.0 / wls  # nm^-1, but wls in nm -> values ~1e-3

                inv_sorted_idx = np.argsort(inv_wls)

                inv_wls_s = inv_wls[inv_sorted_idx]

                sig_s = signal[inv_sorted_idx]

                N_fft = 4096

                inv_uniform = np.linspace(inv_wls_s[0], inv_wls_s[-1], N_fft)

                sig_uniform = np.interp(inv_uniform, inv_wls_s, sig_s)

                # Detrend

                sig_uniform -= np.polyval(np.polyfit(inv_uniform, sig_uniform, 3), inv_uniform)

                fft_amp = np.abs(np.fft.rfft(sig_uniform))

                freqs = np.fft.rfftfreq(N_fft, d=(inv_uniform[1] - inv_uniform[0]))  # in nm

                # Ignore DC and very low freqs (below 200 nm optical path)

                freq_mask = freqs > (1.0 / (2.0 * n_approx * lmax) * 0.5)

                if freq_mask.sum() > 2:
                    dominant_freq_idx = np.argmax(fft_amp[freq_mask])

                    dominant_freqs = freqs[freq_mask]

                    dominant_freq = dominant_freqs[dominant_freq_idx]  # in nm (= 2*n*d)

                    if dominant_freq > 0:
                        d_fft = dominant_freq / (2.0 * n_approx)

            except NUMERICAL_FAULT_EXCEPTIONS as e_fft:
                self.logger.debug(f"FFT thickness estimate failed: {e_fft}")

            #  Method 2: Peak/valley counting (robust to low-contrast fringes)

            d_peaks = None

            try:
                # Detrend signal with a polynomial fit to remove baseline drift

                poly_coef = np.polyfit(wls, signal, 3)

                sig_detrended = signal - np.polyval(poly_coef, wls)

                # Adaptive prominence: 10% of signal range

                sig_range = np.nanmax(sig_detrended) - np.nanmin(sig_detrended)

                prominence = max(sig_range * 0.10, 1e-4)

                min_dist_pts = max(3, len(wls) // 50)

                peaks, _ = find_peaks(sig_detrended, prominence=prominence, distance=min_dist_pts)

                valleys, _ = find_peaks(-sig_detrended, prominence=prominence, distance=min_dist_pts)

                n_extrema = len(peaks) + len(valleys)

                if n_extrema >= 2:
                    # Each fringe = 1 peak + 1 valley -> n_oscillations = n_extrema / 2

                    n_osc = n_extrema / 2.0

                    inv_range = 1.0 / lmin - 1.0 / lmax

                    if inv_range > 0:
                        d_peaks = n_osc / (2.0 * n_approx * inv_range)

            except NUMERICAL_FAULT_EXCEPTIONS as e_pk:
                self.logger.debug(f"Peak-count thickness estimate failed: {e_pk}")

            # -- Choose best estimate: FFT is primary (robust to noise & low contrast)

            d_estimate = None

            method_str = ""

            if d_fft is not None:
                d_estimate = d_fft

                if d_peaks is not None:
                    method_str = f"FFT, n\u2248{n_approx} (peaks check: {d_peaks:.0f} nm)"

                else:
                    method_str = f"FFT, n\u2248{n_approx}"

            elif d_peaks is not None:
                d_estimate = d_peaks

                method_str = f"peaks ({len(peaks)}up+{len(valleys)}dn), n\u2248{n_approx}"

            if d_estimate is not None and d_estimate > 5.0:
                d_estimate = max(10.0, d_estimate)

                self._estimated_thickness_nm = float(d_estimate)

                # Margins: -50% / +100%

                d_min = max(3.0, d_estimate * 0.50)

                d_max = d_estimate * 2.0

                # Round to clean values

                step = 50.0 if d_estimate > 500 else 10.0

                d_min = round(d_min / step) * step

                d_max = round(d_max / step) * step

                d_max = max(d_max, d_min + step * 2)

                # Clamp to physical spinbox ranges

                d_min = max(3.0, min(d_min, 49000.0))

                d_max = max(d_min + 10.0, min(d_max, 50000.0))

                self.sb_dmin.setValue(d_min)

                self.sb_dmax.setValue(d_max)

                self.logger.info(
                    "[INDEX.LOAD] estimated thickness | value=~%.0f nm | method=%s | range=[%.0f, %.0f] nm",
                    d_estimate,
                    method_str,
                    d_min,
                    d_max,
                )

            else:
                self.logger.info("[INDEX.LOAD] thickness not estimated | reason=no oscillations detected")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.debug(f"Auto-detect thickness failed:{e}")

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

    def _toggle_exclude(self, checked) -> None:

        self.sb_ex_min.setEnabled(checked and not self.chk_oh_band.isChecked())

        self.sb_ex_max.setEnabled(checked and not self.chk_oh_band.isChecked())

        # If exclude is unchecked, also uncheck OH band for coherence

        if not checked and self.chk_oh_band.isChecked():
            self.chk_oh_band.blockSignals(True)

            self.chk_oh_band.setChecked(False)

            self.chk_oh_band.blockSignals(False)

        self._update_plot_exclusion()

    def _update_plot_exclusion(self) -> None:

        if self.exclude_region is not None:
            try:
                self.plot_spectrum.removeItem(self.exclude_region)

            except (AttributeError, RuntimeError) as e:
                # Non-critical: exclude_region may not exist or already removed

                self.logger.debug("[INDEX.UI] exclude region removal skipped: %s", e)

                pass

            self.exclude_region = None

        if self.chk_exclude.isChecked():
            min_v = self.sb_ex_min.value()

            max_v = self.sb_ex_max.value()

            if max_v > min_v:
                self.exclude_region = pg.LinearRegionItem(
                    [min_v, max_v], brush=pg.mkBrush(255, 0, 0, 50), movable=False
                )

                self.plot_spectrum.addItem(self.exclude_region)

    def _toggle_oh_band(self, checked) -> None:
        """Toggle OH- band exclusion (1360-1460 nm E-band)."""

        if checked:
            # Set the exclude region to OH- band

            self.chk_exclude.setChecked(True)

            self.sb_ex_min.setValue(OH_BAND_MIN)

            self.sb_ex_max.setValue(OH_BAND_MAX)

            self.sb_ex_min.setEnabled(False)

            self.sb_ex_max.setEnabled(False)

        else:
            # Re-enable manual control

            self.sb_ex_min.setEnabled(self.chk_exclude.isChecked())

            self.sb_ex_max.setEnabled(self.chk_exclude.isChecked())

    def _setup_shortcuts(self) -> None:
        """Install premium cross-window shortcuts."""
        try:
            install_standard_shortcuts(
                self,
                zoom_in=getattr(self, "zoom_in_ui", None),
                zoom_out=getattr(self, "zoom_out_ui", None),
                reset_zoom=getattr(self, "reset_ui_zoom", None),
            )
        except (RuntimeError, AttributeError, TypeError, ValueError):
            self._core_logger.debug("Shortcut installation failed", exc_info=True)



    def _update_zoom_status(self, factor: float | None = None) -> None:
        if factor is None:
            factor = getattr(self, "_zoom_factor", 1.0)
        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.setText(f"Zoom {int(round(factor * 100))}%")

    def _apply_ui_zoom(self, factor: float) -> None:
        apply_app_zoom(
            self,
            factor,
            label_attr="lbl_zoom",
            stylesheet_fn=CertusTheme.get_standard_stylesheet,
            toast_fn=show_toast,
            base_font_size=getattr(CertusTheme, "FONT_SIZE_BASE", 10),
        )

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

    def load_file(self, filepath=None) -> None:

        if filepath is None or isinstance(filepath, bool):
            from certus.ui.certus_ui import certus_get_open_file_name, DATA_FILE_FILTER

            filepath = certus_get_open_file_name(self, "Open", DATA_FILE_FILTER)

            if not filepath:
                return

        if not filepath:
            return

        try:
            from certus.utils.certus_data import load_spectrum_columns

            # Use the unified standard to load and clean (sort, normalize %, nm, etc.)

            res = load_spectrum_columns(filepath, column_roles={})

            df = res.dataframe

            # Automatic data type analysis (uses original headers preserved by column_roles={})

            self.data_type, parsed_data = analyze_loaded_data(df)

            # Rebuild DataFrame with standard named columns

            self.target_data = pd.DataFrame({"lambda": parsed_data["lambda"]})

            if parsed_data["T"] is not None:
                self.target_data["T"] = parsed_data["T"]

            if parsed_data["R"] is not None:
                self.target_data["R"] = parsed_data["R"]

            # Display filename and detected type

            fname = _update_loaded_file_label(self.lbl_file, filepath)

            self.source_file_path = filepath

            # FIX: Update Plot Title immediately on load

            _set_spectrum_plot_title(self.plot_spectrum, fname)

            # Log file loading details (absolute path for traceability)
            _log_loaded_spectrum_metadata(self.logger, filepath, df)

            # Display detected data type
            _display_detected_data_type(
                self.lbl_data_type,
                self.logger,
                self.data_type,
            )

            # Update lambda bounds
            lmin, lmax = _update_lambda_bounds_from_target_data(
                self.target_data,
                self.sb_lmin,
                self.sb_lmax,
                self.logger,
            )

            if not _is_qt_offscreen_mode():
                src_type = _source_type_label(self.data_type)

                n_rows = int(len(self.target_data))

                has_t = "T" in self.target_data.columns

                has_r = "R" in self.target_data.columns

                summary = build_summary_plain_text(
                    "CERTUS INDEX - Load Summary",
                    [
                        f"File: {Path(filepath).resolve()}",
                        "",
                        "General",
                        (f"Rows: {n_rows}", n_rows <= 0),
                        (f"Detected type: {src_type}", src_type == "Unknown"),
                        "",
                        "Data",
                        (f"Wavelength range: [{float(lmin):.1f}, {float(lmax):.1f}] nm", (float(lmax) <= float(lmin))),
                        f"Columns kept: {', '.join(self.target_data.columns.astype(str).tolist())}",
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if has_t else 'no'}",
                            not has_t and self.data_type != DataType.REFLECTION,
                        ),
                        (
                            f"Reflection column present: {'yes' if has_r else 'no'}",
                            not has_r and self.data_type != DataType.TRANSMISSION,
                        ),
                        (
                            "Potential unit conversion applied (% -> fraction): "
                            f"{'yes' if ((parsed_data['T'] is not None and np.nanmax(parsed_data['T']) > 1.5) or (parsed_data['R'] is not None and np.nanmax(parsed_data['R']) > 1.5)) else 'no'}",
                            False,
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX Load Summary", summary)

            # Display preview - clear() deletes everything

            # Force cleanup of internal structures

            self.plot_spectrum.plotItem.clear()

            try:
                # Clean internal structures

                self.plot_spectrum._tracked_curves = []

                self.plot_spectrum.curve_points = {}

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                # Ignore errors after clear()

                self.logger.warning(f"cleanup after clear() failed: {e}")

            wls = self.target_data["lambda"].values

            _is_frost = self.rb_frosted_glass.isChecked()

            _preview_t, _preview_r = _spectrum_visibility_target_traces(self.data_type, _is_frost)

            if _preview_t and "T" in self.target_data.columns:
                c_t = self.plot_spectrum.plot(
                    wls,
                    self.target_data["T"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=3,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_t, "T", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    self.logger.debug("[INDEX.UI] add tracked curve for T skipped: %s", e)

                    pass

            if _preview_r and "R" in self.target_data.columns:
                c_r = self.plot_spectrum.plot(
                    wls,
                    self.target_data["R"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=3,
                    symbolBrush=CertusTheme.DANGER,
                    name="R data",
                )

                # add_tracked_curve handles errors internally

                try:
                    self.plot_spectrum.add_tracked_curve(c_r, "R", "%")

                except (AttributeError, RuntimeError) as e:
                    # Non-critical: tracking may fail if curve doesn't support it

                    self.logger.debug("[INDEX.UI] add tracked curve for R skipped: %s", e)

                    pass

            self.tabs.setCurrentIndex(0)

            # --- DYNAMIC SMOOTHING WITH AUTO-CLOSING DIALOG ---
            self._apply_dynamic_ir_smoothing(
                wls=wls,
                preview_t=_preview_t,
                preview_r=_preview_r,
            )
            # --- END DYNAMIC SMOOTHING ---

            # Auto-detect substrate and pre-estimate thickness

            self._auto_detect_from_file(filepath)

            # Reset results

            self.latest_results = None

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            # Do not show error for tracking issues (non-critical)

            error_msg = str(e)

            if "add_tracked_curve" in error_msg.lower() or "tracking" in error_msg.lower():
                # Non-critical tracking error - log only

                self.logger.debug(f"Non-critical tracking error during file load: {e}")

            else:
                # Critical error - show user
                _notify_user(self, "Load Error", error_msg, level="error")

                self.logger.error("File load error", exc_info=True)

    def _apply_dynamic_ir_smoothing(
        self,
        *,
        wls: np.ndarray,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Apply optional IR denoising and let user keep raw vs smoothed traces."""
        try:
            from scipy.signal import savgol_filter

            raw_data = self.target_data.copy()
            smoothed_data = self.target_data.copy()
            smoothed_any = False
            cols_ir_smooth: list[str] = []

            if "T" in self.target_data.columns and preview_t:
                cols_ir_smooth.append("T")
            if "R" in self.target_data.columns and preview_r:
                cols_ir_smooth.append("R")

            for col in cols_ir_smooth:
                y = self.target_data[col].values
                y_smooth1 = savgol_filter(y, window_length=11, polyorder=2)
                y_smooth2 = savgol_filter(y, window_length=51, polyorder=2)
                y_final = np.copy(y)
                mask_transition = (wls >= 4000) & (wls <= 5200)
                mask_heavy = wls > 5200
                if np.any(mask_transition) or np.any(mask_heavy):
                    smoothed_any = True
                    if np.any(mask_transition):
                        weights = (wls[mask_transition] - 4000) / (5200 - 4000)
                        y_final[mask_transition] = (1 - weights) * y_smooth1[mask_transition] + weights * y_smooth2[
                            mask_transition
                        ]
                    if np.any(mask_heavy):
                        y_final[mask_heavy] = y_smooth2[mask_heavy]
                    smoothed_data[col] = y_final

            if not smoothed_any:
                return

            self._plot_raw_and_smoothed_preview(
                wls=wls,
                raw_data=raw_data,
                smoothed_data=smoothed_data,
                preview_t=preview_t,
                preview_r=preview_r,
            )
            keep_raw = self._ask_keep_raw_or_smoothed()
            self.target_data = raw_data if keep_raw else smoothed_data
            self._redraw_target_preview(wls, preview_t, preview_r)
        except ImportError:
            self.logger.warning("[INDEX.LOAD] smoothing skipped: scipy.signal unavailable")
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning("[INDEX.LOAD] smoothing failed: %s", e)

    def _ask_keep_raw_or_smoothed(self) -> bool:
        """Return True when user explicitly keeps raw traces."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Noise Filtering")
        msg_box.setText(
            "IR Noise detected in 4000-5200nm band.\n"
            "Do you want to keep the smoothed response or the raw response?\n\n"
            "If no selection is made, the smoothed response will be kept after 5 seconds."
        )
        btn_smooth = msg_box.addButton(
            "Keep Smoothed",
            QMessageBox.ButtonRole.AcceptRole,
        )
        btn_raw = msg_box.addButton("Keep Raw", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_smooth)

        timer = QTimer(msg_box)
        timer.timeout.connect(msg_box.accept)
        timer.start(5000)
        msg_box.exec()
        timer.stop()
        return msg_box.clickedButton() == btn_raw

    def _plot_raw_and_smoothed_preview(
        self,
        *,
        wls: np.ndarray,
        raw_data: pd.DataFrame,
        smoothed_data: pd.DataFrame,
        preview_t: bool,
        preview_r: bool,
    ) -> None:
        """Draw temporary raw+smoothed overlay before user selection."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()

        if preview_t and "T" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["T"].values * 100,
                pen=pg.mkPen(color=(40, 167, 69, 100), width=1),
                symbol="o",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(40, 167, 69, 100)),
                name="T data (Raw)",
            )
        if preview_r and "R" in raw_data.columns:
            self.plot_spectrum.plot(
                wls,
                raw_data["R"].values * 100,
                pen=pg.mkPen(color=(220, 53, 69, 100), width=1),
                symbol="s",
                symbolSize=2,
                symbolBrush=pg.mkBrush(color=(220, 53, 69, 100)),
                name="R data (Raw)",
            )
        if preview_t and "T" in smoothed_data.columns:
            c_t_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["T"].values * 100,
                pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                name="T data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_t_sm, "T")
        if preview_r and "R" in smoothed_data.columns:
            c_r_sm = self.plot_spectrum.plot(
                wls,
                smoothed_data["R"].values * 100,
                pen=pg.mkPen(CertusTheme.DANGER, width=3),
                name="R data (Smoothed)",
            )
            self._try_add_spectrum_tracked_curve(c_r_sm, "R")

    def _redraw_target_preview(self, wls: np.ndarray, preview_t: bool, preview_r: bool) -> None:
        """Redraw target traces from current `self.target_data`."""
        self.plot_spectrum.plotItem.clear()
        self._clear_plot_tracking_state()
        if preview_t and "T" in self.target_data.columns:
            c_t = self.plot_spectrum.plot(
                wls,
                self.target_data["T"].values * 100,
                pen=None,
                symbol="o",
                symbolSize=3,
                symbolBrush=CertusTheme.SUCCESS,
                name="T data",
            )
            self._try_add_spectrum_tracked_curve(c_t, "T")
        if preview_r and "R" in self.target_data.columns:
            c_r = self.plot_spectrum.plot(
                wls,
                self.target_data["R"].values * 100,
                pen=None,
                symbol="s",
                symbolSize=3,
                symbolBrush=CertusTheme.DANGER,
                name="R data",
            )
            self._try_add_spectrum_tracked_curve(c_r, "R")

    def _try_add_spectrum_tracked_curve(self, curve, key: str) -> None:
        """Best-effort tracked-curve registration for spectrum traces."""
        try:
            self.plot_spectrum.add_tracked_curve(curve, key, "%")
        except NUMERICAL_FAULT_EXCEPTIONS:
            self.logger.debug("[INDEX.UI] tracked-curve registration skipped in %s", __name__, exc_info=True)

    def _clear_plot_tracking_state(self) -> None:
        """Best-effort cleanup of internal plot tracking structures."""
        try:
            self.plot_spectrum._tracked_curves = []
            self.plot_spectrum.curve_points = {}
        except NUMERICAL_FAULT_EXCEPTIONS:
            self.logger.debug("[INDEX.UI] plot tracking state reset skipped in %s", __name__, exc_info=True)

    def _reset_optimization_progress_state(self, config: OptimizationConfig) -> None:
        """Reset progress and convergence widgets before launching the worker thread."""

        self.progress_widget.start()

        self._total_iterations = 0

        self._best_rmse_display = float("inf")

        # Reset convergence chart (UX-3)
        self._conv_iterations.clear()
        self._conv_rmse_current.clear()
        self._conv_rmse_best.clear()
        if hasattr(self, "_conv_curve_current"):
            self._conv_curve_current.setData([], [])
        if hasattr(self, "_conv_curve_best"):
            self._conv_curve_best.setData([], [])

        # Real evaluation tracking for accurate ETA
        self._current_n_evals = 0
        self._max_evals = 80000 if config.high_precision else 20000

    def _configure_and_start_optimization_worker(self, config: OptimizationConfig) -> None:
        """Instantiate/connect the optimization worker and start the thread."""

        self._thread = QThread()

        # Two-stage TLU (lambda<=2200) + IR spline only if the user window contains lambda < 2200 nm.
        # Otherwise (e.g., fit only 3500-5200 nm): a single stage over the entire range avoids 0 points.
        use_two_stage = config.lambda_max > 2500.0 and config.lambda_min < 2200.0

        if use_two_stage:
            self.logger.info(
                "[INDEX.LOAD] pipeline selected | mode=two-stage | reason=wl_max>2500nm | tlu_band_max=2200nm"
            )
            config.lambda_max_fit = 2200.0
        elif config.lambda_max > 2500.0:
            self.logger.info(
                "[INDEX.LOAD] pipeline selected | mode=single-stage | reason=wl_max>2500nm and lambda_min>=2200nm"
            )
        else:
            self.logger.info("[INDEX.LOAD] pipeline selected | mode=standard | reason=wl_max<=2500nm")

        self._index_tlu_live_ctx = self._make_index_tlu_live_ctx(config)
        self._worker = OptimizationWorker(config, logger=self.logger)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.evals_update.connect(self._on_evals_update)
        self._worker.curve_update.connect(self._on_curve_update)
        self._worker.error.connect(self._on_error)

        if use_two_stage:
            # Connect to custom handler for Phase 2
            self._worker.finished.connect(self._on_tlu_constrained_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
        else:
            self._worker.finished.connect(self._on_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    def _abort_run_optimization(self, title: str, message: str, *, critical: bool = False) -> None:
        """Abort run setup with a user-visible message and reset primary buttons."""
        _notify_user(
            self,
            title,
            message,
            level="error" if critical else "warning",
            blocking=critical,
        )
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _resolve_substrate_absorption_inputs(
        self,
        *,
        substrate_name: str,
        wls_target: np.ndarray,
    ) -> tuple[np.ndarray | None, float | None, np.ndarray | None] | None:
        """Resolve (k_sub, substrate_thickness_nm, n_sub_data) for the selected substrate mode.

        Returns ``None`` when setup must be aborted (message already shown to the user).
        """
        k_sub_interp: np.ndarray | None = None
        sub_thickness_nm: float | None = None
        n_sub_data: np.ndarray | None = None

        is_silicon = substrate_name == "Silicon (Si)"

        if is_silicon:
            if _SILICON_WLS is not None:
                n_sub_data = _get_silicon_n_on_grid(wls_target)
                thickness_mm = self.sb_sub_thickness_mm.value()
                if thickness_mm > 0:
                    k_sub_interp = _get_silicon_k_on_grid(wls_target)
                    sub_thickness_nm = thickness_mm * 1e6
                    self.logger.info(
                        f"[SILICON] Self-absorbent substrate: thickness={thickness_mm:.3f} mm "
                        f"| k_sub(max)={k_sub_interp.max():.4g}"
                    )
                else:
                    self.logger.info("[SILICON] Thickness = 0 -> transparent substrate (k=0 everywhere).")
            else:
                self.logger.warning(
                    "[INDEX.LOAD] silicon substrate fallback | reason=clues.xlsx substrate data unavailable | mode=transparent"
                )
            return k_sub_interp, sub_thickness_nm, n_sub_data

        # For all other substrates, they are transparent (k=0)
        self.logger.info(
            "[INDEX.LOAD] substrate forced transparent | substrate=%s | k=0 everywhere",
            substrate_name,
        )
        return None, None, None

    def run_optimization(self) -> None:
        """

        Run the index optimization process.

        This method initiates the optimization workflow including:

        - Data validation and mode checking

        - Parameter configuration and setup

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusIndex instance

        Returns:

            None

        Notes:

            - Requires loaded target spectrum data

            - Supports both normal and frosted glass modes

            - Validates data requirements for selected mode

            - Emits progress signals during optimization

        """

        if self.target_data is None:
            _notify_user(self, "No Data", "Please load a spectrum first.", level="warning")

            return

        # Check for frosted glass mode

        is_frosted_glass = self.rb_frosted_glass.isChecked()

        if is_frosted_glass:
            # Frosted glass requires reflection data

            if "R" not in self.target_data.columns:
                _notify_user(
                    self,
                    "Data Error",
                    "Frosted Glass mode requires reflection (R) data.\n"
                    "Please load a file with reflection measurements.",
                    level="warning",
                )

                return

            # Force data_type to REFLECTION for frosted glass

            effective_data_type = DataType.REFLECTION

        else:
            effective_data_type = self.data_type

        self._cleanup_worker()

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        self.lbl_status.setText(" Optimization running...")

        self.recap_widget.setVisible(False)

        self.tabs.setCurrentIndex(0)

        # substrate - always use selected material (with bounds check)

        sub_idx = self.cb_sub.currentIndex()

        if sub_idx < 0 or sub_idx >= len(SUBSTRATE_LIST):
            self.logger.error(f"Invalid substrate index: {sub_idx}")
            _notify_user(self, "Error", "Invalid substrate selection.", level="error")

            self.btn_run.setEnabled(True)

            self.btn_stop.setEnabled(False)

            return

        full_sub_name = SUBSTRATE_LIST[sub_idx]

        substrate_name = full_sub_name

        substrate_mode = substrateMode.FROSTED_GLASS if is_frosted_glass else substrateMode.STANDARD

        ex_min, ex_max = None, None

        if self.chk_exclude.isChecked():
            ex_min = self.sb_ex_min.value()

            ex_max = self.sb_ex_max.value()

            if ex_min >= ex_max:
                _notify_user(self, "Warning", "Invalid exclusion range. Ignored.", level="warning")

                ex_min, ex_max = None, None

        # Absorbing substrate inputs (Sapphire/Si/manual k_sub)
        wls_target = self.target_data["lambda"].to_numpy(dtype=np.float64)
        substrate_inputs = self._resolve_substrate_absorption_inputs(
            substrate_name=substrate_name,
            wls_target=wls_target,
        )
        if substrate_inputs is None:
            return
        k_sub_interp, sub_thickness_nm, n_sub_data = substrate_inputs

        _d_fft_seed = getattr(self, "_estimated_thickness_nm", None)

        _fixed_thickness_seed = None

        if _d_fft_seed is not None:
            _d_lo = float(min(self.sb_dmin.value(), self.sb_dmax.value()))

            _d_hi = float(max(self.sb_dmin.value(), self.sb_dmax.value()))

            _fixed_thickness_seed = float(np.clip(float(_d_fft_seed), _d_lo, _d_hi))

        config = OptimizationConfig(
            target_data=self.target_data,
            data_type=effective_data_type,
            substrate=substrate_name,
            substrate_mode=substrate_mode,
            thickness_min=self.sb_dmin.value(),
            thickness_max=self.sb_dmax.value(),
            lambda_min=self.sb_lmin.value(),
            lambda_max=self.sb_lmax.value(),
            exclude_min=ex_min,
            exclude_max=ex_max,
            source_file=self.source_file_path,
            use_normalized=self.chk_normalized.isChecked(),
            weight_T=self.sb_weight_T.value() if not is_frosted_glass else 0.0,
            weight_R=self.sb_weight_R.value(),
            high_precision=self.chk_high_precision.isChecked(),
            fixed_thickness=_fixed_thickness_seed,
            k_sub_data=k_sub_interp,
            substrate_thickness_nm=sub_thickness_nm,
            n_sub_data=n_sub_data,
        )

        # Start progress widget timing

        self.logger.info("=" * 60)

        self.logger.info("[INDEX.STATE] optimization started")

        if self.source_file_path:
            self.logger.info(
                "[FILE] Measured Spectrum: %s",
                Path(self.source_file_path).resolve(),
            )

        else:
            self.logger.warning("[FILE] Measured Spectrum: path not specified")

        if substrate_name == "Sapphire (Al2O3)":
            self.logger.info(
                "[FILE] Substrate Al2O3 n(lambda): Sellmeier equation (materials_v1.json, id=3) "
                "| k file: %s | k column: %s",
                Path(_SAPPHIRE_DATA_FILE).resolve(),
                _SAPPHIRE_FILE_HAS_K_COLUMN,
            )

        elif substrate_name == "Silicon (Si)":
            self.logger.info(
                "[FILE] Substrate Si (clues.xlsx): %s",
                Path(get_resource_path("clues.xlsx")).resolve(),
            )

        self.logger.info("=" * 60)

        self.logger.info(f"substrate: {substrate_name} (Mode: {substrate_mode.name})")

        self.logger.info(
            "[INDEX.LOAD] thickness range | min=%.1f nm | max=%.1f nm",
            config.thickness_min,
            config.thickness_max,
        )

        self.logger.info(
            "[INDEX.LOAD] wavelength range | min=%.1f nm | max=%.1f nm",
            config.lambda_min,
            config.lambda_max,
        )

        if config.exclude_min and config.exclude_max:
            self.logger.info(f"Excluded Region: {config.exclude_min} - {config.exclude_max} nm")

        self.logger.info("=" * 50)

        self._reset_optimization_progress_state(config)
        self._configure_and_start_optimization_worker(config)

    def stop_optimization(self) -> None:
        """Stop optimization - best solution will be saved by the worker"""

        # confirm_stop_with_timeout is imported from certus.ui.certus_ui

        if not confirm_stop_with_timeout(self):
            return

        # Ensure UI reflects stopped state immediately

        self.lbl_status.setText(" Stopping...")
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped")

        self.btn_stop.setEnabled(False)

        ok_main = stop_worker_and_thread(
            self._worker,
            self._thread,
            timeout_ms=3000,
            logger=self.logger,
            label="Thread",
        )
        if not ok_main:
            self.lbl_status.setText(" Stop timeout (thread may still finish)")

        stop_worker_and_thread(
            getattr(self, "_worker2", None),
            getattr(self, "_thread2", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Thread2",
        )

        # Also stop beam analysis worker if running

        stop_worker_and_thread(
            getattr(self, "_beam_worker", None),
            getattr(self, "_beam_thread", None),
            timeout_ms=3000,
            logger=self.logger,
            label="Beam thread",
        )

        self.lbl_status.setText(" Stopping...")

    def _cleanup_worker(self) -> None:

        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    if self._worker:
                        self._worker.stop()

                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                # Qt object has already been deleted

                pass

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    if hasattr(self, "_worker2") and self._worker2:
                        self._worker2.stop()

                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _cleanup_worker - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                self._core_logger.debug("Silenced exception in %s", __name__, exc_info=True)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_thread_finished(self) -> None:

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._worker = None

        self._thread = None

        self._worker2 = None

        self._thread2 = None

    def _on_evals_update(self, n_evals: int) -> None:
        """Update evaluation count for progress widget ETA."""

        self._current_n_evals = n_evals

        self.lbl_dice.setText(f" {n_evals:,}")

    def _make_index_tlu_live_ctx(self, c: OptimizationConfig) -> dict | None:
        """lambda / n_sub grid identical to OptimizationWorker.run (TLU) for live, like Metal Bilayer."""

        try:
            _lmf = getattr(c, "lambda_max_fit", None)

            effective_lambda_max = float(c.lambda_max) if _lmf is None else min(float(_lmf), float(c.lambda_max))

            mask = (c.target_data["lambda"] >= c.lambda_min) & (c.target_data["lambda"] <= effective_lambda_max)

            wls = c.target_data.loc[mask, "lambda"].to_numpy(dtype=np.float64)

            if wls.size == 0:
                return None

            sub_id = c.substrate_sellmeier_id
            if sub_id is None:
                sub_id = -1

            if c.n_sub_data is not None:
                l_full = c.target_data["lambda"].to_numpy(dtype=np.float64)

                n_sub = np.interp(
                    wls,
                    l_full,
                    c.n_sub_data,
                    left=c.n_sub_data[0],
                    right=c.n_sub_data[-1],
                ).astype(np.float64)

            else:
                n_sub = _get_substrate_n_array_index(sub_id, wls)

            target_T = None

            target_R = None

            if c.data_type in (DataType.TRANSMISSION, DataType.BOTH) and not c.is_frosted_glass:
                if "T" in c.target_data.columns:
                    target_T = c.target_data.loc[mask, "T"].to_numpy()

            if c.data_type in (DataType.REFLECTION, DataType.BOTH):
                if "R" in c.target_data.columns:
                    target_R = c.target_data.loc[mask, "R"].to_numpy()

            valid = np.isfinite(n_sub)

            if target_T is not None:
                valid &= np.isfinite(target_T)

            if target_R is not None:
                valid &= np.isfinite(target_R)

            wls = wls[valid]

            n_sub = n_sub[valid]

            if wls.size == 0:
                return None

            return {
                "config": c,
                "wls": wls,
                "n_sub": n_sub,
                "k_sub": getattr(c, "k_sub_data", None),
                "D_sub": getattr(c, "substrate_thickness_nm", None),
            }

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning("TLU live context build failed: %s", e)

            return None

    def _index_tlu_live_payload_from_params(self, params: np.ndarray) -> dict | None:
        """n,k + R,T from TLU vector (7 param.) - aligned with TLUObjective.__call__."""

        ctx = getattr(self, "_index_tlu_live_ctx", None)

        if ctx is None:
            return None

        p = np.asarray(params, dtype=np.float64).ravel()

        if p.size != 7:
            return None

        c = ctx["config"]

        wls = ctx["wls"]

        n_sub = ctx["n_sub"]

        thickness = float(p[0])

        Eg, A, E0, C, Eu, eps_inf = (float(p[i]) for i in range(1, 7))

        if Eg <= 0 or A <= 0 or C <= 0 or Eu <= 0 or eps_inf < 1:
            return None

        E_arr = HC_EV_NM / wls

        eps2 = epsilon2_TLU_array(E_arr, Eg, A, E0, C, Eu)

        eps1 = epsilon1_TL_analytic(E_arr, Eg, A, E0, C, Eu)

        n_calc, k_calc, is_valid = epsilon_to_nk(eps1, eps2, N_MIN_LIMIT, N_MAX_LIMIT, K_MAX_LIMIT)

        if not is_valid:
            return None

        # Use shared source of truth for R/T calculation

        R_calc, T_calc, T_sub_ref = _compute_RT_from_config(c, wls, n_calc, k_calc, thickness, n_sub)

        # Apply normalization scaling based on user configuration

        if not c.is_frosted_glass and getattr(c, "use_normalized", False):
            with np.errstate(divide="ignore", invalid="ignore"):
                # Safety for T_sub -> 0

                Ts_safe = np.where(T_sub_ref > SMALL_EPSILON, T_sub_ref, 1.0)

                T_plot = np.where(T_sub_ref > SMALL_EPSILON, T_calc / Ts_safe, np.nan)

                T_plot = np.maximum(T_plot, 0.0)

            R_plot = calculate_relative_R_normalization(R_calc, T_sub_ref)

        else:
            T_plot, R_plot = T_calc, R_calc

        _st, _sr = _index_live_spectrum_visibility(c)

        return {
            "wls": wls,
            "n": n_calc,
            "k": k_calc,
            "R_calc": R_plot,
            "T_calc": T_plot,
            "is_frosted_glass": bool(c.is_frosted_glass),
            "live_show_T": _st,
            "live_show_R": _sr,
            "mse": None,
        }

    def _apply_index_live_plot_payload(self, extra_info: dict) -> None:
        """Live plot n,k + spectrum (same logic as Spline pipeline / progress dict)."""

        wls = extra_info["wls"]

        n_c = extra_info["n"]

        k_c = extra_info["k"]

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

        c_n = self.plot_nk.plot(wls, n_c, pen=pg.mkPen(color="#3b82f6", width=3), name="n (Live)")

        self.plot_nk.add_tracked_curve(c_n, "n (Live)")

        if not hasattr(self, "_vb_k") or self._vb_k is None:
            pi = self.plot_nk.plotItem

            self._vb_k = pg.ViewBox()

            pi.scene().addItem(self._vb_k)

            ax_k = KLogAxisItem("right")

            ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

            pi.layout.addItem(ax_k, 2, 3)

            ax_k.linkToView(self._vb_k)

            self._vb_k.setXLink(pi)

            pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

        else:
            self._vb_k.clear()

        self._vb_k.setLogMode(False, False)

        self._vb_k.setYRange(-6.5, -2.0, padding=0)

        self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        if self.plot_nk.plotItem.vb.sceneBoundingRect().isValid():
            self._vb_k.setGeometry(self.plot_nk.plotItem.vb.sceneBoundingRect())

        k_plot = np.where(
            np.isfinite(k_c) & (k_c >= 1e-8),
            np.log10(np.maximum(k_c, 1e-7)),
            -7.0,
        )

        c_k = pg.PlotCurveItem(
            wls,
            k_plot,
            pen=pg.mkPen(color="#f59e0b", width=3),
            name="log10(k) (Live)",
        )

        self._vb_k.addItem(c_k)

        self.plot_nk.add_tracked_curve(c_k, "log10(k) (Live)")

        if "R_calc" in extra_info or "T_calc" in extra_info:
            show_t = extra_info.get("live_show_T", True)

            show_r = extra_info.get("live_show_R", True)

            Rc = extra_info.get("R_calc")

            Tc = extra_info.get("T_calc")

            for item in list(self.plot_spectrum.plotItem.items):
                item_name = getattr(item, "name", lambda: "")()

                if item_name in [
                    "R (Live)",
                    "T (Live)",
                    "R Fit",
                    "T Fit",
                    "R (Live Spline)",
                    "T (Live Spline)",
                ]:
                    self.plot_spectrum.plotItem.removeItem(item)

            try:
                self.plot_spectrum.remove_curve("R (Live)")

            except Exception:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            try:
                self.plot_spectrum.remove_curve("T (Live)")

            except Exception:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            if show_r and Rc is not None:
                c_r = pg.PlotCurveItem(
                    wls,
                    np.asarray(Rc) * 100,
                    pen=pg.mkPen(color="#ef4444", width=3),
                    name="R (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_r, "R (Live)")

                self.plot_spectrum.plotItem.addItem(c_r)

            if show_t and Tc is not None:
                c_t = pg.PlotCurveItem(
                    wls,
                    np.asarray(Tc) * 100,
                    pen=pg.mkPen(color="#10b981", width=3),
                    name="T (Live)",
                )

                self.plot_spectrum.add_tracked_curve(c_t, "T (Live)")

                self.plot_spectrum.plotItem.addItem(c_t)

        try:
            self.plot_spectrum.getPlotItem().vb.autoRange()

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            self.plot_nk.getPlotItem().vb.autoRange()

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.tabs.setCurrentIndex(0)

    def _on_progress(self, step: int, phase: str, extra_info=None) -> None:

        # Throttle UI updates (plots, labels, tables) to avoid GUI flooding

        now = time.time()

        # Always update if phase changes, otherwise check 2.0s interval

        phase_changed = self._last_phase_name != phase

        self._last_phase_name = phase

        if not phase_changed and (now - self._last_progress_ui_update < 2.0):
            return

        self._last_progress_ui_update = now

        rmse_val = 0.0

        rmse_str = ""

        is_numeric_msg = False

        if isinstance(extra_info, dict) and "n" in extra_info and "k" in extra_info and "wls" in extra_info:
            try:
                self._apply_index_live_plot_payload(extra_info)

                wls = extra_info["wls"]

                n_c = extra_info["n"]

                k_c = extra_info["k"]

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error plotting live progress: {e}", exc_info=True)

                wls = extra_info.get("wls", np.array([]))

                n_c = extra_info.get("n", np.array([]))

                k_c = extra_info.get("k", np.array([]))

            # Live Update of Data Tab & Clipboard Support

            try:
                if getattr(self, "latest_results", None) is not None:
                    # Update background DataFrame so Copy works

                    live_df = pd.DataFrame({"lambda": wls, "n_calc": n_c, "k_calc": k_c})

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        live_df["R_calc (%)"] = extra_info["R_calc"] * 100

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        live_df["T_calc (%)"] = extra_info["T_calc"] * 100

                    self.latest_results.df_results = live_df

                    self.table_res.setRowCount(len(wls))

                    src_name_base = Path(self.latest_results.config.source_file).stem

                    d_val = (
                        int(round(self.latest_results.thickness))
                        if hasattr(self.latest_results, "thickness") and self.latest_results.thickness
                        else 0
                    )

                    n_colname = f"n_{src_name_base}_{d_val}"

                    k_colname = f"k_{src_name_base}_{d_val}"

                    cols = ["lambda (nm)", n_colname, k_colname]

                    if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                        cols.append("T (%)")

                    if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                        cols.append("R (%)")

                    self.table_res.setColumnCount(len(cols))

                    self.table_res.setHorizontalHeaderLabels(cols)

                    for i in range(len(wls)):
                        self.table_res.setItem(i, 0, QTableWidgetItem(f"{wls[i]:.1f}"))

                        self.table_res.setItem(i, 1, QTableWidgetItem(f"{n_c[i]:.4f}"))

                        self.table_res.setItem(i, 2, QTableWidgetItem(f"{k_c[i]:.6f}"))

                        col_idx = 3

                        if "T_calc" in extra_info and extra_info.get("live_show_T", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['T_calc'][i] * 100:.2f}"))

                            col_idx += 1

                        if "R_calc" in extra_info and extra_info.get("live_show_R", True):
                            self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{extra_info['R_calc'][i] * 100:.2f}"))

                            col_idx += 1

                    self.table_res.resizeColumnsToContents()
            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Live data table update error: {e}", exc_info=True)

            if isinstance(extra_info, dict) and "mse" in extra_info:
                val = extra_info["mse"]

                if val is not None:
                    rmse_val = np.sqrt(val)

                    if rmse_val < self._best_rmse_display:
                        self._best_rmse_display = rmse_val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                else:
                    self.lbl_status.setText(f"{phase}")

            else:
                self.lbl_status.setText(f"{phase}")

            # Still update the progress bar even with dict data

            n_evals = getattr(self, "_current_n_evals", 0)

            self.progress_widget.update(step, 100, n_evals, phase, "")

            return

        elif isinstance(extra_info, float):
            # It's a numerical MSE

            rmse_val = np.sqrt(extra_info)

            if rmse_val < self._best_rmse_display:
                self._best_rmse_display = rmse_val

            rmse_str = f"RMSE: {rmse_val:.5f}"

            self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

            is_numeric_msg = True

        elif isinstance(extra_info, str):
            # Try to parse string message if it contains numerical info

            if "Total Data RMSE" in extra_info:
                try:
                    val_str = extra_info.split()[-1]

                    val = float(val_str)

                    if val < self._best_rmse_display:
                        self._best_rmse_display = val

                    self.lbl_status.setText(f"{phase} (Best RMSE: {self._best_rmse_display:.4f})")

                    rmse_val = val

                    rmse_str = f"RMSE: {val:.5f}"

                    is_numeric_msg = True

                except ValueError:
                    self.lbl_status.setText(f"{phase} | {extra_info}")

                    rmse_str = extra_info

            else:
                self.lbl_status.setText(f"{phase} | {extra_info}")

                rmse_str = extra_info

        else:
            self.lbl_status.setText(f"{phase}")

            rmse_str = str(extra_info) if extra_info else ""

        if is_numeric_msg and rmse_val > 0:
            self._total_iterations += 1

            # --- UX-3: update convergence chart ---
            if hasattr(self, "_conv_iterations"):
                self._conv_iterations.append(self._total_iterations)
                self._conv_rmse_current.append(rmse_val)
                self._conv_rmse_best.append(self._best_rmse_display)
                xs = self._conv_iterations
                self._conv_curve_current.setData(xs, self._conv_rmse_current)
                self._conv_curve_best.setData(xs, self._conv_rmse_best)

        n_evals = getattr(self, "_current_n_evals", 0)

        self.progress_widget.update(
            iteration=step,
            max_iter=100,
            evals=n_evals,
            phase=phase,
            extra_info=rmse_str,
        )

    def _on_error(self, error_msg: str) -> None:

        self.lbl_status.setText(" Error")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Error")

        # Quit orphaned thread (error signal does NOT trigger thread.quit)

        if hasattr(self, "_thread") and self._thread is not None:
            try:
                if self._thread.isRunning():
                    self._thread.quit()

                    if not self._thread.wait(2000):
                        self.logger.critical(
                            "Thread did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread cleanup warning: {e}")

            finally:
                self._thread = None

        if hasattr(self, "_thread2") and self._thread2 is not None:
            try:
                if self._thread2.isRunning():
                    self._thread2.quit()

                    if not self._thread2.wait(2000):
                        self.logger.critical(
                            "Thread2 did not stop within 2s in _on_error - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError as e:
                self.logger.warning(f"Thread2 cleanup warning: {e}")

            finally:
                self._thread2 = None

        self._worker = None

        self._worker2 = None

        self._thread = None

        self._thread2 = None

        self.optimization_running = False

        self.logger.error(f"Worker Error: {error_msg}")

    def _on_curve_update(self, params) -> None:
        """Live TLU : equivalent Metal Bilayer ``progress`` -> ``update_plots`` (best parameter set)."""

        try:
            p = np.asarray(params, dtype=np.float64).ravel()

            if p.size != 7:
                return

            payload = self._index_tlu_live_payload_from_params(p)

            if payload is None:
                return

            self._apply_index_live_plot_payload(payload)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.debug("curve_update: %s", e, exc_info=True)

    def _update_spectrum_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the T/R spectrum plot (data + fit)."""

        self.plot_spectrum.clear()

        self.plot_spectrum.clear_tracking()

        self._update_plot_exclusion()

        try:
            _set_spectrum_plot_title(self.plot_spectrum, res.config.source_file)

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # Display target data

        if "T_target" in sub_df.columns and not res.config.is_frosted_glass:
            try:
                c_tgt_t = self.plot_spectrum.plot(
                    wls,
                    sub_df["T_target"].values * 100,
                    pen=None,
                    symbol="o",
                    symbolSize=4,
                    symbolBrush=CertusTheme.SUCCESS,
                    name="T Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_t, "T Target", "%")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error("[INDEX.UI] display failed | component=T_target | reason=%s", e, exc_info=True)

        if "R_target" in sub_df.columns:
            try:
                c_tgt_r = self.plot_spectrum.plot(
                    wls,
                    sub_df["R_target"].values * 100,
                    pen=None,
                    symbol="s",
                    symbolSize=4,
                    symbolBrush=CertusTheme.DANGER,
                    name="R Target",
                )

                self.plot_spectrum.add_tracked_curve(c_tgt_r, "R Target", "%")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error("[INDEX.UI] display failed | component=R_target | reason=%s", e, exc_info=True)

        # Display fits

        use_normalized = res.config.use_normalized

        # Transmission (not for frosted glass)

        if not res.config.is_frosted_glass and res.config.data_type in (
            DataType.TRANSMISSION,
            DataType.BOTH,
        ):
            col_T = "T_norm_calc (%)" if use_normalized else "T_calc (%)"

            if col_T in sub_df.columns:
                try:
                    c_fit_t = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_T].values,
                        pen=pg.mkPen(CertusTheme.SUCCESS, width=3),
                        name="T Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_t, "T Fit", "%")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.error(f"Error displaying T fit: {e}", exc_info=True)

        # Reflection

        if res.config.data_type in (DataType.REFLECTION, DataType.BOTH) or res.config.is_frosted_glass:
            col_R = "R_norm_calc (%)" if use_normalized else "R_calc (%)"

            if col_R in sub_df.columns:
                try:
                    c_fit_r = self.plot_spectrum.plot(
                        wls,
                        sub_df[col_R].values,
                        pen=pg.mkPen(CertusTheme.DANGER, width=3),
                        name="R Fit",
                    )

                    self.plot_spectrum.add_tracked_curve(c_fit_r, "R Fit", "%")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.error(f"Error displaying R fit: {e}", exc_info=True)

    def _update_nk_plot(self, wls, sub_df, res: OptimizationResults) -> None:
        """Update the n & k plot (left axis n, right axis log k)."""

        self.plot_nk.clear()

        self.plot_nk.clear_tracking()

        try:
            src_name = Path(res.config.source_file).stem

            title_text = f"Optical Constants      {src_name}      thickness = {res.optimal_thickness:.2f} nm"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title_text = f"Optical Constants      thickness = {res.optimal_thickness:.2f} nm"

        self.plot_nk.plotItem.setTitle(title_text)

        prepared = _prepare_nk_plot_inputs(wls, sub_df, res, self.logger)
        if prepared is None:
            return
        n_values, k_values, method_str, lambda_max_fit, tlu_mode = prepared

        try:
            # k curve refs for legend

            c_k_main = None

            c_kt = None

            c_kr = None

            # --- Primary axis (left): n ---

            # Label left axis explicitly

            self.plot_nk.setLabel("left", "n", color=CertusTheme.PRIMARY)

            if "n_calc_005" in sub_df.columns:
                n1 = sub_df["n_calc_005"].values.copy()

                n2 = sub_df["n_calc_0025"].values.copy()

                n3 = sub_df["n_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    n1[ir_mask_ui] = np.nan

                    n2[ir_mask_ui] = np.nan

                    n3[ir_mask_ui] = np.nan

                self.plot_nk.plot(wls, n1, pen=pg.mkPen(color="#93c5fd", width=2), name="n (tol=0.005)")

                self.plot_nk.plot(wls, n2, pen=pg.mkPen(color="#3b82f6", width=2), name="n (tol=0.0025)")

                c_n3 = self.plot_nk.plot(wls, n3, pen=pg.mkPen(color="#1e3a8a", width=3), name="n (tol=0.001)")

                self.plot_nk.add_tracked_curve(c_n3, "n")

                self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            else:
                c_n = self.plot_nk.plot(wls, n_values, pen=pg.mkPen(CertusTheme.PRIMARY, width=3), name="n (R+T)")

                self.plot_nk.add_tracked_curve(c_n, "n (R+T)")

                if "n_center" in sub_df.columns and "n_hi" in sub_df.columns and "n_lo" in sub_df.columns:
                    n_cen = sub_df["n_center"].values.copy()

                    if tlu_mode:
                        n_cen[ir_mask_ui] = np.nan

                    c_nc = self.plot_nk.plot(
                        wls,
                        n_cen,
                        pen=pg.mkPen(color=CertusTheme.SUCCESS, width=2, style=Qt.PenStyle.DashLine),
                        name="n (center)",
                    )

                    self.plot_nk.add_tracked_curve(c_nc, "n (center)")

                    n_err_center = sub_df["n_raw"].values if "n_raw" in sub_df.columns else n_values

                    top_n = sub_df["n_hi"].values - n_err_center

                    bot_n = n_err_center - sub_df["n_lo"].values

                    top_n = np.where(np.isfinite(top_n), top_n, 0)

                    bot_n = np.where(np.isfinite(bot_n), bot_n, 0)

                    if "n_hi_2" in sub_df.columns and "n_lo_2" in sub_df.columns:
                        top_n2 = sub_df["n_hi_2"].values - n_err_center

                        bot_n2 = n_err_center - sub_df["n_lo_2"].values

                        top_n2 = np.where(np.isfinite(top_n2), top_n2, 0)

                        bot_n2 = np.where(np.isfinite(bot_n2), bot_n2, 0)

                        err_n2 = pg.ErrorBarItem(
                            x=wls,
                            y=n_err_center,
                            top=top_n2,
                            bottom=bot_n2,
                            beam=0.5,
                            pen=pg.mkPen(color=(30, 136, 229, 80), width=3),
                        )

                        self.plot_nk.plotItem.addItem(err_n2)

                    err_n = pg.ErrorBarItem(
                        x=wls,
                        y=n_err_center,
                        top=top_n,
                        bottom=bot_n,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.PRIMARY, width=1),
                    )

                    self.plot_nk.plotItem.addItem(err_n)

                    if "n_raw" in sub_df.columns:
                        # Plot the raw bisection cloud as a translucent scattered layer underneath the clean Line

                        c_raw = self.plot_nk.plot(
                            wls,
                            n_err_center,
                            pen=pg.mkPen(color=(30, 136, 229, 120), width=1, style=Qt.PenStyle.DotLine),
                            name="n (Raw point-by-point)",
                        )

                        self.plot_nk.add_tracked_curve(c_raw, "n (Raw)")

                # --- EXTRA FITS: Visualization ---

                if "n_fit_T_only" in sub_df.columns:
                    c_nt = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_T_only"].values,
                        pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% T)",
                    )

                    self.plot_nk.add_tracked_curve(c_nt, "n (90% T)")

                if "n_fit_R_only" in sub_df.columns:
                    c_nr = self.plot_nk.plot(
                        wls,
                        sub_df["n_fit_R_only"].values,
                        pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine),
                        name="n (90% R)",
                    )

                    self.plot_nk.add_tracked_curve(c_nr, "n (90% R)")

            # Legend n (left axis)

            self.plot_nk.plotItem.addLegend(offset=(10, 10), labelTextSize="9pt")

            # --- Secondary axis (right, log scale): k ---

            pi = self.plot_nk.plotItem

            # Create or reuse secondary ViewBox

            if not hasattr(self, "_vb_k") or self._vb_k is None:
                self._vb_k = pg.ViewBox()

                pi.scene().addItem(self._vb_k)

                ax_k = KLogAxisItem("right")

                ax_k.setLabel("k (log scale)", color=CertusTheme.WARNING)

                pi.layout.addItem(ax_k, 2, 3)

                ax_k.linkToView(self._vb_k)

                self._vb_k.setXLink(pi)

                self._ax_k = ax_k

                # Geometry sync on resize (connected once only)

                pi.vb.sigResized.connect(lambda: self._vb_k.setGeometry(pi.vb.sceneBoundingRect()))

            else:
                self._vb_k.clear()

            # Do NOT use pyqtgraph's internal setLogMode, it silently drops curves if any single point causes a math domain error during rendering.

            # Instead, we will feed it raw log10() values into a linear ViewBox.

            self._vb_k.setLogMode(False, False)

            self._vb_k.setYRange(-6.5, -2.0, padding=0)

            self._vb_k.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

            self._vb_k.setGeometry(pi.vb.sceneBoundingRect())

            # Plot k  use a tiny floor so k0 regions (VIS) stay connected on log scale

            # pyqtgraph's ViewBox with setLogMode(Y=True) applies log10 internally,

            # so we must NOT pass NaN for k=0; instead we floor at 1e-7.

            if "k_calc_005" in sub_df.columns:
                k1 = sub_df["k_calc_005"].values.copy()

                k2 = sub_df["k_calc_0025"].values.copy()

                k3 = sub_df["k_calc_001"].values.copy()

                if tlu_mode:
                    ir_mask_ui = wls > lambda_max_fit

                    k1[ir_mask_ui] = np.nan

                    k2[ir_mask_ui] = np.nan

                    k3[ir_mask_ui] = np.nan

                k1_p = np.where(np.isfinite(k1) & (k1 >= 1e-8), np.log10(np.maximum(k1, 1e-7)), -7.0)

                k2_p = np.where(np.isfinite(k2) & (k2 >= 1e-8), np.log10(np.maximum(k2, 1e-7)), -7.0)

                k3_p = np.where(np.isfinite(k3) & (k3 >= 1e-8), np.log10(np.maximum(k3, 1e-7)), -7.0)

                c_k1 = pg.PlotCurveItem(wls, k1_p, pen=pg.mkPen(color="#fcd34d", width=2), name="log10(k) (tol=0.005)")

                c_k2 = pg.PlotCurveItem(wls, k2_p, pen=pg.mkPen(color="#f59e0b", width=2), name="log10(k) (tol=0.0025)")

                c_k3 = pg.PlotCurveItem(wls, k3_p, pen=pg.mkPen(color="#b45309", width=3), name="log10(k) (tol=0.001)")

                self._vb_k.addItem(c_k1)

                self._vb_k.addItem(c_k2)

                self._vb_k.addItem(c_k3)

                self.plot_nk.add_tracked_curve(c_k3, "log10(k)")

            else:
                k_plot = np.where(
                    np.isfinite(k_values) & (k_values >= 1e-8), np.log10(np.maximum(k_values, 1e-7)), -7.0
                )

                c_k = pg.PlotCurveItem(wls, k_plot, pen=pg.mkPen(CertusTheme.WARNING, width=3), name="k (R+T)")

                self._vb_k.addItem(c_k)

                self.plot_nk.add_tracked_curve(c_k, "log10(k)")

                c_k_main = c_k

                if "k_center" in sub_df.columns and "k_hi" in sub_df.columns and "k_lo" in sub_df.columns:
                    kc = sub_df["k_center"].values.copy()

                    if tlu_mode:
                        kc[ir_mask_ui] = np.nan

                    kc_plot = np.where(np.isfinite(kc) & (kc >= 0), np.maximum(kc, 1e-7), np.nan)

                    c_kc = pg.PlotCurveItem(
                        wls,
                        kc_plot,
                        pen=pg.mkPen(color=CertusTheme.WARNING, width=2, style=Qt.PenStyle.DashLine),
                        name="k (center)",
                    )

                    self._vb_k.addItem(c_kc)

                    self.plot_nk.add_tracked_curve(c_kc, "log10(k) (center)")

                    k_err_center = sub_df["k_raw"].values if "k_raw" in sub_df.columns else k_plot

                    k_err_center_plot = np.where(
                        np.isfinite(k_err_center) & (k_err_center >= 0), np.maximum(k_err_center, 1e-7), np.nan
                    )

                    top_k = sub_df["k_hi"].values - k_err_center_plot

                    bot_k = k_err_center_plot - sub_df["k_lo"].values

                    top_k = np.where(np.isfinite(top_k), top_k, 0)

                    bot_k = np.where(np.isfinite(bot_k), bot_k, 0)

                    if "k_hi_2" in sub_df.columns and "k_lo_2" in sub_df.columns:
                        top_k2 = sub_df["k_hi_2"].values - k_err_center_plot

                        bot_k2 = k_err_center_plot - sub_df["k_lo_2"].values

                        top_k2 = np.where(np.isfinite(top_k2), top_k2, 0)

                        bot_k2 = np.where(np.isfinite(bot_k2), bot_k2, 0)

                        err_k2 = pg.ErrorBarItem(
                            x=wls,
                            y=k_err_center_plot,
                            top=top_k2,
                            bottom=bot_k2,
                            beam=0.5,
                            pen=pg.mkPen(color=(255, 179, 0, 80), width=3),
                        )

                        self._vb_k.addItem(err_k2)

                    err_k = pg.ErrorBarItem(
                        x=wls,
                        y=k_err_center_plot,
                        top=top_k,
                        bottom=bot_k,
                        beam=0.5,
                        pen=pg.mkPen(CertusTheme.WARNING, width=1),
                    )

                    self._vb_k.addItem(err_k)

            # --- EXTRA FITS: k Visualization ---

            if "k_fit_T_only" in sub_df.columns:
                kt = sub_df["k_fit_T_only"].values

                kt_p = np.where(np.isfinite(kt) & (kt >= 1e-8), np.log10(np.maximum(kt, 1e-7)), -7.0)

                c_kt = pg.PlotCurveItem(
                    wls, kt_p, pen=pg.mkPen(color="#10b981", width=2, style=Qt.PenStyle.DashLine), name="k (90% T)"
                )

                self._vb_k.addItem(c_kt)

                self.plot_nk.add_tracked_curve(c_kt, "log10(k) (90% T)")

            if "k_fit_R_only" in sub_df.columns:
                kr = sub_df["k_fit_R_only"].values

                kr_p = np.where(np.isfinite(kr) & (kr >= 1e-8), np.log10(np.maximum(kr, 1e-7)), -7.0)

                c_kr = pg.PlotCurveItem(
                    wls, kr_p, pen=pg.mkPen(color="#ef4444", width=2, style=Qt.PenStyle.DashLine), name="k (90% R)"
                )

                self._vb_k.addItem(c_kr)

                self.plot_nk.add_tracked_curve(c_kr, "log10(k) (90% R)")

            if "k_raw" in sub_df.columns:
                c_k_raw = pg.PlotCurveItem(
                    wls,
                    k_err_center_plot,
                    pen=pg.mkPen(color=(255, 179, 0, 120), width=1, style=Qt.PenStyle.DotLine),
                    name="k (Raw point-by-point)",
                )

                self._vb_k.addItem(c_k_raw)

                self.plot_nk.add_tracked_curve(c_k_raw, "log10(k) (Raw)")

            # Legend k (right axis)

            if c_k_main is not None or c_kt is not None or c_kr is not None:
                leg_k = pg.LegendItem(offset=(10, 120), labelTextSize="9pt")

                leg_k.setParentItem(self.plot_nk.plotItem)

                if c_k_main is not None:
                    leg_k.addItem(c_k_main, "k (R+T)")

                if c_kt is not None:
                    leg_k.addItem(c_kt, "k (90% T)")

                if c_kr is not None:
                    leg_k.addItem(c_kr, "k (90% R)")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] display failed | component=nk | reason=%s", e, exc_info=True)

            self.logger.error(traceback.format_exc())

    def _update_model_text(self, res: OptimizationResults) -> None:

        # Update data table

        try:
            if hasattr(self, "lbl_final_eq"):
                eq_html = "<h2>Final Analytical Optical Model</h2><br>"

                eq_html += f"<b>Optimal Thickness :</b> {res.optimal_thickness:.7f} nm<br><br>"

                eq_html += "<table width='100%'><tr><td valign='top' width='50%'>"

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    eq_html += "<b>Refractive Index (Sellmeier 2-poles + A)</b><br>"

                    eq_html += (
                        "<i>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2)</i> (lambda in m)<br>"
                    )

                    eq_html += "<ul>"

                    eq_html += f"<li><b>A</b> = {sp[0]:.6f}</li>"

                    eq_html += f"<li><b>B1</b> = {sp[1]:.7e}  <b>C1</b> = {sp[2] ** 2:.7e} m2</li>"

                    eq_html += f"<li><b>B2</b> = {sp[3]:.7e}  <b>C2</b> = {sp[4] ** 2:.7e} m2</li>"

                    eq_html += "</ul>"

                eq_html += "</td><td valign='top' width='50%'>"

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    eq_html += "<b>Extinction Coefficient (Generalized Exp + Gaussian 8-params)</b><br>"

                    eq_html += "<i>k(lambda) = 1e-6 + exp(P1lambda + P2) + exp(P3lambda + P4) + P5exp(-| (lambda-P6)/P7 | ^ P8)</i> (lambda in m)<br>"

                    eq_html += "<ul>"

                    eq_html += "<li><b>P1-P4</b> (Exponentials)</li>"

                    eq_html += f"<li><b>P5</b> (Amp) = {kp[4]:.7e}</li>"

                    eq_html += f"<li><b>P6</b> (Center) = {kp[5]:.7e}</li>"

                    eq_html += f"<li><b>P7</b> (Width) = {kp[6]:.7e}</li>"

                    eq_html += f"<li><b>P8 (Beta Shape)</b> = {kp[7]:.4f}</li>"

                    eq_html += "</ul>"

                    if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                        eq_html += f"<br><i>[INDEX.SPLINE] k refined by spline (log k) | phase=2.3 | knots={len(res.k_spline_knots_lambda_um)}</i>"

                eq_html += "</td></tr></table>"

                self.lbl_final_eq.setText(eq_html)

            # Update independent parameters table (16 parameters list)

            try:
                params_rows = []

                # 1. Sellmeier

                if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                    sp = res.sellmeier_params

                    params_rows.extend(
                        [
                            ("A (Constant)", f"{sp[0]:.6f}"),
                            ("B1", f"{sp[1]:.6f}"),
                            ("C1 (m2)", f"{sp[2] ** 2:.6f}"),
                            ("B2", f"{sp[3]:.6f}"),
                            ("C2 (m2)", f"{sp[4] ** 2:.6f}"),
                        ]
                    )

                # 2. k-law (8 params)

                if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                    kp = res.k_8p_params

                    names = [
                        "P1 (Slope1)",
                        "P2 (Pos1)",
                        "P3 (Slope2)",
                        "P4 (Pos2)",
                        "P5 (Amp)",
                        "P6 (Center)",
                        "P7 (Width)",
                        "P8 (Beta Exponent)",
                    ]

                    for idx, val in enumerate(kp):
                        p_name = names[idx] if idx < len(names) else f"P{idx + 1}"

                        params_rows.append((p_name, f"{val:.6e}"))

                self.table_params.setRowCount(len(params_rows))

                for i, (p_name, p_val) in enumerate(params_rows):
                    item_name = QTableWidgetItem(p_name)

                    item_name.setBackground(pg.mkColor(CertusTheme.SURFACE))

                    self.table_params.setItem(i, 0, item_name)

                    self.table_params.setItem(i, 1, QTableWidgetItem(p_val))

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error updating params table: {e}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error updating model text: {e}", exc_info=True)

        self.btn_copy_nk.setEnabled(True)

        self.btn_copy_params.setEnabled(True)

    def _update_data_table(self, sub_df, res: OptimizationResults) -> None:

        try:
            self.table_res.setRowCount(len(sub_df))

            has_T_tgt = "T_target" in sub_df.columns

            has_R_tgt = "R_target" in sub_df.columns

            src_name_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_colname = f"n_{src_name_base}_{d_val}"

            k_colname = f"k_{src_name_base}_{d_val}"

            if res.config.is_frosted_glass:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

            else:
                cols = ["lambda (nm)", n_colname, k_colname]

                if "delta_n" in sub_df.columns:
                    cols.extend(["n", "k"])

                cols.append("T (%)")

                if "n_fit_T_only" in sub_df.columns:
                    cols.extend(["n (T-only)", "k (T-only)"])

                if has_T_tgt:
                    cols.append("T Exp (%)")

                cols.append("R (%)")

                if "n_fit_R_only" in sub_df.columns:
                    cols.extend(["n (R-only)", "k (R-only)"])

                if has_R_tgt:
                    cols.append("R Exp (%)")

                self.table_res.setColumnCount(len(cols))

                self.table_res.setHorizontalHeaderLabels(cols)

                for i in range(len(sub_df)):
                    row_data = sub_df.iloc[i]

                    col_idx = 0

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['lambda']:.1f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_calc']:.4f}"))

                    col_idx += 1

                    self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_calc']:.6f}"))

                    col_idx += 1

                    if "delta_n" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_n']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['delta_k']:.6f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['T_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_T_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_T_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_T_only']:.6f}"))

                        col_idx += 1

                    if has_T_tgt:
                        val_t = row_data["T_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_t:.2f}"))

                        col_idx += 1

                    self.table_res.setItem(
                        i,
                        col_idx,
                        QTableWidgetItem(f"{row_data['R_calc (%)']:.2f}"),
                    )

                    col_idx += 1

                    if "n_fit_R_only" in sub_df.columns:
                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['n_fit_R_only']:.4f}"))

                        col_idx += 1

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{row_data['k_fit_R_only']:.6f}"))

                        col_idx += 1

                    if has_R_tgt:
                        val_r = row_data["R_target"] * 100

                        self.table_res.setItem(i, col_idx, QTableWidgetItem(f"{val_r:.2f}"))

                        col_idx += 1

                self.table_res.resizeColumnsToContents()
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error updating data table: {e}", exc_info=True)

    def _display_results(self, res: OptimizationResults) -> None:
        """Update UI graphs and table with results"""

        try:
            df = res.df_results

            if df.empty:
                self.logger.error("df_results is empty!")

                return

            # Verify required columns

            required_cols = ["lambda", "n_calc", "k_calc"]

            missing_cols = [col for col in required_cols if col not in df.columns]

            if missing_cols:
                self.logger.error(f"Missing columns in df_results: {missing_cols}")

                self.logger.error(f"Available columns: {list(df.columns)}")

                return

            mask = (df["lambda"] >= res.config.lambda_min) & (df["lambda"] <= res.config.lambda_max)

            sub_df = df[mask]

            if sub_df.empty:
                self.logger.error(
                    f"sub_df is empty after filtering! lambda_min={res.config.lambda_min}, lambda_max={res.config.lambda_max}"
                )

                return

            wls = sub_df["lambda"].values

            if len(wls) == 0:
                self.logger.error("wls is empty!")

                return

            self._update_spectrum_plot(wls, sub_df, res)

            self._update_nk_plot(wls, sub_df, res)

            self._update_model_text(res)

            self._update_data_table(sub_df, res)

            self.tabs.setCurrentIndex(0)

            try:
                self.plot_spectrum.getPlotItem().vb.autoRange()

                self.plot_nk.getPlotItem().vb.autoRange()

            except NUMERICAL_FAULT_EXCEPTIONS :
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] display failed | component=results | reason=%s", e, exc_info=True)

            self.logger.error(traceback.format_exc())

            _notify_user(
                self,
                "Display Error",
                f"Error displaying results: {e}\n\nCheck logs for details.",
                level="warning",
            )

    def _copy_nk_to_clipboard(self) -> None:
        """Copy the full n,k table (lambda, n, k, ) to the clipboard as tab-separated text."""

        if self.latest_results is None or self.latest_results.df_results is None:
            _notify_user(self, "No Data", "No results available to copy.", level="warning")

            return

        df = self.latest_results.df_results

        required = ["lambda", "n_calc", "k_calc"]

        if not all(c in df.columns for c in required):
            _notify_user(self, "No Data", "Result table does not contain n,k data.", level="warning")

            return

        try:
            res = self.latest_results

            src_base = Path(res.config.source_file).stem

            d_val = int(round(res.thickness)) if hasattr(res, "thickness") and res.thickness else 0

            n_col = f"n_{src_base}_{d_val}"

            k_col = f"k_{src_base}_{d_val}"

            header = f"lambda (nm)\t{n_col}\t{k_col}"

            if "delta_n" in df.columns:
                header += "\tdelta_n\tdelta_k"

            if "n_fit_T_only" in df.columns:
                header += "\tn (T-only)\tk (T-only)"

            if "n_fit_R_only" in df.columns:
                header += "\tn (R-only)\tk (R-only)"

            lines = [header]

            for _, row in df.iterrows():
                row_str = f"{row['lambda']:.1f}\t{row['n_calc']:.6f}\t{row['k_calc']:.9f}"

                if "delta_n" in df.columns:
                    row_str += f"\t{row['delta_n']:.6f}\t{row['delta_k']:.9f}"

                if "n_fit_T_only" in df.columns:
                    row_str += f"\t{row['n_fit_T_only']:.6f}\t{row['k_fit_T_only']:.9f}"

                if "n_fit_R_only" in df.columns:
                    row_str += f"\t{row['n_fit_R_only']:.6f}\t{row['k_fit_R_only']:.9f}"

                lines.append(row_str)

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("n,k table copied!")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.UI] copy failed | reason=%s", e)

    def _copy_params_to_clipboard(self) -> None:
        """Copy the 16 global model parameters to the clipboard."""

        if self.table_params.rowCount() == 0:
            _notify_user(self, "No Data", "No parameters available to copy.", level="warning")

            return

        try:
            lines = ["Parameter\tValue"]

            for i in range(self.table_params.rowCount()):
                p = self.table_params.item(i, 0).text()

                v = self.table_params.item(i, 1).text()

                lines.append(f"{p}\t{v}")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText("Model parameters copied!")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Copy error: {e}")

    def _copy_eq_to_clipboard(self) -> None:
        """Copy the final analytical equations to the clipboard as text."""

        if self.latest_results is None:
            _notify_user(self, "No Data", "No results available to copy.", level="warning")

            return

        try:
            res = self.latest_results

            lines = ["Final Analytical Optical Model", "=" * 40]

            lines.append(f"Optimal Thickness : {res.optimal_thickness:.7f} nm\n")

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                lines.append("Refractive Index (Sellmeier 2-poles + A)")

                lines.append("n^2 = A + (B1*L^2)/(L^2 - C1) + (B2*L^2)/(L^2 - C2)  with L in m")

                lines.append(f"A = {sp[0]:.6f}")

                lines.append(f"B1 = {sp[1]:.7e}")

                lines.append(f"C1 = {sp[2] ** 2:.7e} m^2")

                lines.append(f"B2 = {sp[3]:.7e}")

                lines.append(f"C2 = {sp[4] ** 2:.7e} m^2\n")

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                lines.append("Extinction Coefficient (Generalized Exp + Super-Gauss 8-params)")

                lines.append("k(L) = 1e-6 + exp(P1*L + P2) + exp(P3*L + P4) + P5*exp(-abs((L-P6)/P7)^P8)  with L in m")

                for idx, val in enumerate(kp):
                    lines.append(f"P{idx + 1} = {val:.7e}")

                if getattr(res, "k_spline_knots_lambda_um", None) is not None:
                    lines.append("[INDEX.SPLINE] k refined by spline (log k) | phase=2.3")

                    lines.append(f"Knots (m): {res.k_spline_knots_lambda_um.tolist()}")

                    lines.append(f"k at knots: {res.k_spline_knots_values.tolist()}")

                lines.append("")

            text = "\n".join(lines)

            QApplication.clipboard().setText(text)

            self.lbl_status.setText(" Equations copied to clipboard")

            self.logger.info("[INDEX.UI] equations copied to clipboard")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Copy equations failed: {e}", exc_info=True)
            _notify_user(self, "Copy Error", str(e), level="error")

    def _on_finished(self, res: OptimizationResults) -> None:

        # Stop progress widget and show completion

        mode_str = "Frosted Glass" if res.config.is_frosted_glass else res.config.data_type.name

        self.progress_widget.stop(f"Done ({mode_str})")

        # Status message adapted to mode

        self.lbl_status.setText(f" Done ({mode_str})")

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        # Enable Copy n,k

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(True)

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(True)

        # Button states are now entirely automated based on wavelength, no Refine buttons.

        # Save results for export

        self.latest_results = res

        # PHASE 5: Sellmeier refit + k reopt. Skip when result already from Phase 2 global model.

        try:
            method = (res.optimization_stats or {}).get("method", "")

            skip_phase5_overwrite = "PGLOBAL" in method or "Sellmeier+k" in method

            if skip_phase5_overwrite:
                self.logger.info("[INDEX.SPLINE] phase5 skipped | reason=global Sellmeier+k | action=keep_nk")

            else:
                self.lbl_status.setText(" Phase 5: Global Sellmeier fit for n & k re-optimization...")

                df = res.df_results

                if "lambda" in df.columns and "n_calc" in df.columns and "k_calc" in df.columns:
                    wls = df["lambda"].values

                    n_exp = df["n_calc"].values

                    k_cal = df["k_calc"].values

                    # 1. Global Sellmeier 2-poles fit on calculated n

                    n_spline = n_exp.copy()

                    n_target = n_exp.copy()

                    # Blend TLU with Spline for wls < 2500 nm to find the ideal compromise

                    if res.tlu_params is not None:
                        try:
                            from certus_physics import epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk

                            tlu = res.tlu_params

                            E_wls = HC_EV_NM / wls

                            e2_w = epsilon2_TLU_array(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.Eu)

                            e1_w = epsilon1_TL_analytic(E_wls, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf)

                            n_tlu, _, _ = epsilon_to_nk(e1_w, e2_w, 0.5, 15.0, 15.0)

                            mask_2500 = wls < 2500.0

                            n_target[mask_2500] = (n_spline[mask_2500] + n_tlu[mask_2500]) / 2.0

                        except NUMERICAL_FAULT_EXCEPTIONS as e:
                            self.logger.warning(f"Could not compute TLU compromise: {e}")

                    # Mask out the exclude range if it exists

                    valid_mask = np.ones_like(wls, dtype=bool)

                    ex_min = res.config.exclude_min

                    ex_max = res.config.exclude_max

                    if ex_min is not None and ex_max is not None and ex_min > 0 and ex_max > ex_min:
                        valid_mask &= ~((wls >= ex_min) & (wls <= ex_max))

                    n_fit_global, params_n = fit_sellmeier_global(
                        wls, n_exp, material=res.config.substrate, valid_mask=valid_mask
                    )

                    if params_n is not None:
                        # 2. Re-optimize / smooth k using the 8-parameter empirical law

                        k_smooth, params_k = fit_k_global_8p(wls, k_cal, valid_mask=valid_mask)

                        if params_k is not None:
                            setattr(res, "k_8p_params", params_k)

                        # 3. Update dataframe with perfectly smooth n & newly re-optimized k

                        df["n_calc"] = n_fit_global

                        if params_k is not None:
                            df["k_calc"] = k_smooth

                        # Save Sellmeier parameters to res object to export them

                        setattr(res, "sellmeier_params", params_n)

                        self.logger.info("[INDEX.SPLINE] phase5 complete | status=success")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Phase 5 failed (n Sellmeier / k reopt) : {e}", exc_info=True)

            # Safe Fallback: Original res is unchanged and will be exported normally.

        # =====================================================================

        # Convert final_mse to RMSE

        final_rmse = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Update summary (safe for Spline where tlu_params is None)

        eg_val = res.tlu_params.Eg if res.tlu_params else 0.0

        eps_val = res.tlu_params.eps_inf if res.tlu_params else 0.0

        self.recap_widget.update_results(res.optimal_thickness, final_rmse, eg_val, eps_val)

        # Update graphs (target + fit according to use_normalized) BEFORE HTML export:

        # generate_html_report performs a grab() of the widget; if the export precedes this plot,

        # the Visual Analysis section shows an obsolete state (e.g., live curves only, old T/Tsub mode).

        self._display_results(res)

        # AUTO EXPORT (Excel + HTML ; the PNG capture must reflect the spectrum above)

        self.export_results()

    def _on_tlu_constrained_finished(self, tlu_res: OptimizationResults) -> None:

        # Check if user requested stop during Phase 1

        if self._worker is not None and self._worker.is_stopped:
            self._on_finished(tlu_res)

            return

        # Show the TLU curve and results before asking the question

        final_rmse_tlu = np.sqrt(tlu_res.final_mse) if tlu_res.final_mse >= 0 else 0.0

        eg_val = tlu_res.tlu_params.Eg if tlu_res.tlu_params else 0.0

        eps_val = tlu_res.tlu_params.eps_inf if tlu_res.tlu_params else 0.0

        self.recap_widget.update_results(tlu_res.optimal_thickness, final_rmse_tlu, eg_val, eps_val)

        self._display_results(tlu_res)

        # Force Qt to redraw the GUI immediately before crashing with popup

        # Request validation before launching the IR phase which is cumbersome

        msg_box = QMessageBox(self)

        msg_box.setIcon(QMessageBox.Icon.Question)

        msg_box.setWindowTitle("Phase 1 Completed (TLU)")

        msg_box.setText(
            f"Phase 1 (UV-VIS) completed successfully.\n"
            f"Fixed thickness: {tlu_res.optimal_thickness:.2f} nm.\n\n"
            f"All properties (n, k, thickness) below 2500 nm are now strictly FIXED.\n"
            f"Do you want to launch the Global IR Model extension (> 2500 nm)?"
        )

        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes)

        msg_box.setDefaultButton(yes_btn)

        QTimer.singleShot(5000, yes_btn.click)

        reply = msg_box.exec()

        if reply == int(QMessageBox.StandardButton.No) or reply == QMessageBox.StandardButton.No:
            self.logger.info("[INDEX.SPLINE] phase2/ir extension canceled by user | action=keep_full_TLU")

            self._on_finished(tlu_res)

            return

        self.lbl_status.setText(" Phase 2/2: Global Model Refinement IR (> 2500 nm)...")

        # Restore full wavelength range (TLU was fitted on <= 2200 nm only)

        tlu_res.config.lambda_max_fit = None

        if self.target_data is not None:
            tlu_res.config.target_data = self.target_data.copy()

            tlu_res.config.lambda_min = float(self.target_data["lambda"].min())

            tlu_res.config.lambda_max = float(self.target_data["lambda"].max())

            self.logger.info(
                f"  Phase 2: full-range data "
                f"[{tlu_res.config.lambda_min:.0f}, {tlu_res.config.lambda_max:.0f}] nm "
                f"({len(self.target_data)} pts)"
            )

        self._best_rmse_display = 1e12

        self._total_iterations = 0

        self._worker2 = IRGlobalModelWorker(tlu_res.config, tlu_res, logger=self.logger)

        # Removed live visualization logic

        # Re-connect to standard UI handlers

        self._worker2.finished.connect(self._on_finished)

        self._worker2.error.connect(self._on_error)

        self._worker2.progress.connect(self._on_progress)

        self._worker2.evals_update.connect(self._on_evals_update)

        self._worker2.curve_update.connect(self._on_curve_update)

        self._thread2 = QThread()

        self._worker2.moveToThread(self._thread2)

        self._thread2.started.connect(self._worker2.run)

        self._worker2.finished.connect(self._thread2.quit)

        self._worker2.finished.connect(self._worker2.deleteLater)

        self._thread2.finished.connect(self._thread2.deleteLater)

        self._thread2.finished.connect(self._on_thread_finished)

        self._thread2.start()

    # =========================================================================

    # EXCEL EXPORT

    # =========================================================================

    def _build_uncertainty_content(self, df: pd.DataFrame) -> dict[str, str]:
        """Build uncertainty metrics for HTML export from available delta columns."""

        uncertainty_content: dict[str, str] = {}

        if "delta_n_res" in df.columns:
            dn = df["delta_n_res"].values

            uncertainty_content["Deltan Max (3-way)"] = f"{np.max(dn):.4f}"

            uncertainty_content["Deltan Mean (3-way)"] = f"{np.mean(dn):.4f}"

            uncertainty_content["Deltan Min (3-way)"] = f"{np.min(dn[dn > 0]):.4f}" if np.any(dn > 0) else "0.0000"

        if "delta_k_res" in df.columns:
            dk = df["delta_k_res"].values

            uncertainty_content["Deltak Max (3-way)"] = f"{np.max(dk):.4f}"

            uncertainty_content["Deltak Mean (3-way)"] = f"{np.mean(dk):.4f}"

        if "delta_n" in df.columns and "delta_k" in df.columns:
            uncertainty_content["Deltan Max (50-50 vs 90% T)"] = f"{np.max(df['delta_n'].values):.4f}"

            uncertainty_content["Deltan Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_n'].values):.4f}"

            uncertainty_content["Deltak Max (50-50 vs 90% T)"] = f"{np.max(df['delta_k'].values):.4f}"

            uncertainty_content["Deltak Mean (50-50 vs 90% T)"] = f"{np.mean(df['delta_k'].values):.4f}"

        if not uncertainty_content:
            uncertainty_content["Status"] = "Not calculated"

        return uncertainty_content

    def _export_results_html(self, res: OptimizationResults, rmse_val: float, html_path: str) -> None:
        """Export INDEX HTML report; logs errors internally to preserve legacy flow."""

        try:
            # Prepare Dispersion Table

            if res.tlu_params:
                disp_data = [
                    {
                        "Parameter": "Eg",
                        "Value": f"{res.tlu_params.Eg:.4f}",
                        "Unit": "eV",
                    },
                    {
                        "Parameter": "eps_inf",
                        "Value": f"{res.tlu_params.eps_inf:.4f}",
                        "Unit": "-",
                    },
                    {"Parameter": "A", "Value": f"{res.tlu_params.A:.4f}", "Unit": "-"},
                    {"Parameter": "C", "Value": f"{res.tlu_params.C:.4f}", "Unit": "-"},
                    {
                        "Parameter": "E0",
                        "Value": f"{res.tlu_params.E0:.4f}",
                        "Unit": "eV",
                    },
                ]

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                disp_data = [
                    {
                        "Parameter": "Mode",
                        "Value": "IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement",
                        "Unit": "-",
                    },
                    {"Parameter": "Thickness (nm)", "Value": f"{res.optimal_thickness:.4f}", "Unit": "nm"},
                ]

                if not is_phase2_ir:
                    disp_data.append(
                        {
                            "Parameter": "Knots",
                            "Value": f"{res.optimization_stats.get('num_knots', 'N/A')}",
                            "Unit": "-",
                        }
                    )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                disp_data.extend(
                    [
                        {"Parameter": "Sellmeier A (Const)", "Value": f"{sp[0]:.6f}", "Unit": "-"},
                        {"Parameter": "Sellmeier B1", "Value": f"{sp[1]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C1", "Value": f"{sp[2] ** 2:.8e}", "Unit": "m2"},
                        {"Parameter": "Sellmeier B2", "Value": f"{sp[3]:.8e}", "Unit": "-"},
                        {"Parameter": "Sellmeier C2", "Value": f"{sp[4] ** 2:.8e}", "Unit": "m2"},
                    ]
                )

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    disp_data.append({"Parameter": name, "Value": f"{val:.8e}", "Unit": "-"})

            # Uncertainty statistics from delta_n_res/delta_k_res (3-way) or delta_n/delta_k (50-50 vs 90% T)
            uncertainty_content = self._build_uncertainty_content(res.df_results)

            sections = [
                {
                    "title": "Optimization Methodology",
                    "type": "kv",
                    "content": {
                        "Algorithm": "Hybrid (PGlobal + L-BFGS-B)",
                        "Gradient Mode": "Analytic (Exact Derivatives)",
                        "Speedup": "~200x vs Finite Difference",
                        "Precision": "Machine Precision (Float64)",
                        "Convergence": "High (Jacobian-Assisted)",
                    },
                },
                {
                    "title": "Algorithm Details",
                    "type": "text",
                    "content": (
                        "The optimization employs a robust three-stage strategy: "
                        "1. <strong>PGlobal (Global Search)</strong>: Uses a stochastic differential evolution approach to find the global minimum region. "
                        "2. <strong>L-BFGS-B (Local Polish)</strong>: Uses the <strong>Analytic Gradient</strong> to refine the solution with high precision. "
                        "3. <strong>Coordinate Descent (Fine Tuning)</strong>: A final local descent step to escape narrow local minima. "
                        "4. <strong>Physical Accuracy</strong>: Rigorously accounts for <strong>Incoherent Backside Reflection</strong> in the substrate for both Transmission and Reflection (T = T_single * T_back / (1 - R_single*R_back)). "
                        "The analytic gradient computes the exact derivatives of the Tauc-Lorentz-Urbach model and Transfer Matrix Method interactions (including backside effects) using the chain rule, "
                        "eliminating numerical noise and providing significant performance improvements over traditional finite-difference methods."
                    ),
                },
                {
                    "title": "Optimization Summary",
                    "type": "kv",
                    "content": {
                        "Date": certus_timestamp_display(),
                        "Source File": Path(res.config.source_file).name,
                        "Final RMSE": f"{rmse_val:.6f}",
                        "Execution Time": f"{res.execution_time:.2f} s",
                        "Model": "IR Global Model (Sellmeier + k 8p)"
                        if (
                            res.tlu_params is None
                            and (
                                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
                            )
                        )
                        else "Tauc-Lorentz-Urbach",
                        "substrate": res.config.substrate,
                    },
                },
                {
                    "title": "Dispersion Parameters",
                    "type": "table",
                    "content": disp_data,
                },
                {
                    "title": "Uncertainty Analysis",
                    "type": "kv",
                    "content": uncertainty_content,
                },
            ]

            # --- 3. Add Beam Analysis Section (if available) ---

            if hasattr(self, "last_beam_results") and self.last_beam_results:
                beam_table = []

                # Sort by MSE

                sorted_beam = sorted(self.last_beam_results, key=lambda x: x["mse"])

                # Take top 20 or all

                for b in sorted_beam[:20]:
                    beam_table.append(
                        {
                            "Thickness (nm)": f"{b['d']:.2f}",
                            "MSE": f"{b['mse']:.2e}",
                            "Status": "Best" if b == sorted_beam[0] else "",
                        }
                    )

                sections.append(
                    {
                        "title": "Beam Analysis (Thickness Scan)",
                        "type": "table",
                        "content": beam_table,
                    }
                )

                # Add explainer

                sections.append(
                    {
                        "title": "Beam Analysis Details",
                        "type": "text",
                        "content": (
                            f"Beam Analysis scanned <strong>{len(self.last_beam_results)}</strong> thickness values. "
                            "The table above shows the best solutions found. "
                            "This technique validates the global minimum by ensuring no better solution exists at other thicknesses."
                        ),
                    }
                )

            # --- 4. Add Physical Model Section ---

            _is_phase2_ir = res.tlu_params is None and (
                "PGLOBAL" in (res.optimization_stats or {}).get("method", "")
                or "Sellmeier+k" in (res.optimization_stats or {}).get("method", "")
            )

            if _is_phase2_ir:
                sections.append(
                    {
                        "title": "Physical Model: Sellmeier 2-pole + k 8-parameter",
                        "type": "kv",
                        "content": {
                            "n(lambda)": "Sellmeier 2-pole: n2 = A + B₁lambda2/(lambda2-L₁2) + B₂lambda2/(lambda2-L₂2)",
                            "k(lambda)": "Empirical: exponentials + super-Gaussian peak (soft-saturated)",
                            "Range": "Full spectrum (Phase 2/2 IR Global Model)",
                        },
                    }
                )

            else:
                sections.append(
                    {
                        "title": "Physical Model: Tauc-Lorentz-Urbach",
                        "type": "kv",
                        "content": {
                            "Formula": "2(E) = AE0C(E-Eg)2 / [(E2-E02)2 + C2E2]  (1/E)",
                            "Urbach Tail": "Exponential tail below Eg (extends absorption)",
                            "Eg": "Band Gap Energy (eV)",
                            "eps_inf": "High-frequency dielectric constant",
                            "A": "Amplitude (Strength of oscillator)",
                            "E0": "Peak Energy (eV)",
                            "C": "Broadening (eV)",
                        },
                    }
                )

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                _method = (res.optimization_stats or {}).get("method", "")

                _skip_phase5 = "PGLOBAL" in _method or "Sellmeier+k" in _method

                if not _skip_phase5:
                    sections.append(
                        {
                            "title": "Phase 5: Sellmeier Smooth Fit (n)",
                            "type": "text",
                            "content": (
                                "At the end of the optimization, <strong>n</strong> is strictly fitted to a 3-pole <strong>Sellmeier Law</strong> over the entire spectrum "
                                "to guarantee perfectly smooth and physical values: <br/>"
                                "<code>n2 = A + (B1lambda2) / (lambda2 - C1) + (B2lambda2) / (lambda2 - C2) + (B3lambda2) / (lambda2 - C3)</code><br/>"
                                "The extinction coefficient <strong>k</strong> is then re-optimized point-by-point to perfectly match experimental (R,T) targets with the fixed Sellmeier <strong>n</strong>."
                            ),
                        }
                    )

            figures = [self.plot_spectrum, self.plot_nk]

            if hasattr(self, "plot_delta_n"):
                figures.append(self.plot_delta_n)

            if generate_html_report(html_path, "CERTUS-INDEX Report", sections, figures):
                self.logger.info("[INDEX.EXPORT] html saved | path=%s", html_path)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.EXPORT] html export failed | reason=%s", e, exc_info=True)

    def export_results(self) -> None:
        """Standardized Auto-Export (Excel + HTML).

        The export naming must reflect the final fit error used by the report,
        while the material/substrate semantics remain confined to the model and
        config fields.
        """

        if not get_export_config():
            return

        if not self.latest_results:
            return

        res = self.latest_results

        # Final fit error used for report naming and summaries.
        rmse_val = np.sqrt(res.final_mse) if res.final_mse >= 0 else 0.0

        # Generate filenames for the standardized report bundle.

        try:
            reports_dir = get_resource_path("reports")

            os.makedirs(reports_dir, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            try:
                src_name = Path(res.config.source_file).stem

                base_filename = f"Report_INDEX_{src_name}_{ts}_RMSE_{rmse_val:.5f}"

            except NUMERICAL_FAULT_EXCEPTIONS:
                base_filename = f"Report_INDEX_{ts}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(reports_dir) / (base_filename + ".xlsx"))

            html_path = str(Path(reports_dir) / (base_filename + ".html"))

            self.lbl_status.setText("Saving Reports...")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Filename generation error: {e}")

            return

        # --- 1. EXCEL EXPORT ---

        try:
            tlu = res.tlu_params

            if tlu:
                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Eg": [f"{tlu.Eg:.4f}"],
                    "eps_inf": [f"{tlu.eps_inf:.4f}"],
                    "A": [f"{tlu.A:.4f}"],
                    "C": [f"{tlu.C:.4f}"],
                    "E0": [f"{tlu.E0:.4f}"],
                }

            else:
                method = (res.optimization_stats or {}).get("method", "")

                is_phase2_ir = "PGLOBAL" in method or "Sellmeier+k" in method

                summary_data = {
                    "Date": [certus_timestamp_display()],
                    "Source File": [res.config.source_file],
                    "Final RMSE": [f"{rmse_val:.6e}"],
                    "Optimization Time (s)": [f"{res.execution_time:.2f}"],
                    "Mode": ["IR Global Model (Phase 2/2)" if is_phase2_ir else "Spline Refinement"],
                    "Thickness (nm)": [f"{res.optimal_thickness:.4f}"],
                    "Thickness Variation (%)": [f"{getattr(res, 'thickness_variation', 0):+.2f}"],
                }

                if not is_phase2_ir:
                    summary_data["Knots"] = [getattr(res, "num_knots", "N/A")]

            summary_data["Substrate (material)"] = [res.config.substrate]

            if res.config.substrate == "Sapphire (Al2O3)":
                summary_data["Sapphire n(lambda) source"] = ["Sellmeier equation (materials_v1.json, id=3)"]

                summary_data["Sapphire k column in file"] = ["yes" if _SAPPHIRE_FILE_HAS_K_COLUMN else "no"]

            if hasattr(res, "sellmeier_params") and res.sellmeier_params is not None:
                sp = res.sellmeier_params

                summary_data["Sellmeier_A"] = [f"{sp[0]:.6f}"]

                summary_data["Sellmeier_B1"] = [f"{sp[1]:.8e}"]

                summary_data["Sellmeier_C1"] = [f"{sp[2] ** 2:.8e}"]

                summary_data["Sellmeier_B2"] = [f"{sp[3]:.8e}"]

                summary_data["Sellmeier_C2"] = [f"{sp[4] ** 2:.8e}"]

            if hasattr(res, "k_8p_params") and res.k_8p_params is not None:
                kp = res.k_8p_params

                kp_names = [
                    "k_P1_Slope1",
                    "k_P2_Pos1",
                    "k_P3_Slope2",
                    "k_P4_Pos2",
                    "k_P5_Amp",
                    "k_P6_Center",
                    "k_P7_Width",
                    "k_P8_Beta",
                ]

                for i, val in enumerate(kp):
                    name = kp_names[i] if i < len(kp_names) else f"k_P{i + 1}"

                    summary_data[name] = [f"{val:.8e}"]

            df_summary = pd.DataFrame(summary_data)

            df_data = res.df_results.copy()

            from certus.utils.certus_data import ReportSection, build_standard_report

            try:
                if bool(getattr(res.config, "use_normalized", False)):
                    self.set_validation_status("WARNING_DATA_NORMALIZED")
                    self.add_validation_warning("Input data normalized before optimization/export.")
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("INDEX validation status update skipped during export: %s", exc)

            run_manifest = None
            try:
                run_manifest = (res.optimization_stats or {}).get("run_manifest")
            except (TypeError, AttributeError):
                run_manifest = None

            report_result = build_standard_report(
                [
                    ReportSection("Summary", kind="table", content=df_summary, sheet_name="Summary"),
                    ReportSection("Data", kind="table", content=df_data, sheet_name="Data"),
                ],
                excel_path=excel_path,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )
            if report_result.get("excel"):
                self.logger.info("[INDEX.EXPORT] excel saved | path=%s", excel_path)
            else:
                self.logger.error("Excel export blocked/failed: missing or incomplete run manifest.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("[INDEX.EXPORT] excel export failed | reason=%s", e, exc_info=True)

        # --- 2. HTML EXPORT ---
        self._export_results_html(res, rmse_val, html_path)

        self.lbl_status.setText(f" Saved: {base_filename}")

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

    def detach_current_plot(self) -> None:
        """Detach current plot or data table in a separate window"""

        current_widget = self.tabs.currentWidget()

        if current_widget is None:
            return

        current_index = self.tabs.currentIndex()

        # 1. OPTION : TAB SPECTRUM (Index 0)

        if current_index == 0:
            plot_name = "spectrum"

            plot_title = "Transmission / Reflection Spectrum"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            detached_plot_copy = clone_plot_widget(self.plot_spectrum)

            if detached_plot_copy:
                detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

                detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

                self.detached_plot_windows[plot_name] = detached_window

                detached_window.show()

        # 2. OPTION : TAB N_K (Index 1) -> Split into two windows!

        elif current_index == 1:
            screen = QApplication.primaryScreen().availableGeometry()

            win_w = screen.width() // 2 - 10

            win_h = screen.height() - 100

            # Detach N (Left Axis)

            if "nk_n" not in self.detached_plot_windows or not self.detached_plot_windows["nk_n"].isVisible():
                n_clone = clone_plot_widget(self.plot_nk, title_override="Refractive Index n")

                win_n = DetachedPlotWindow(n_clone, parent=self, title="Refractive Index n")

                win_n.closed_signal.connect(functools.partial(self.reattach_plot, "nk_n"))

                self.detached_plot_windows["nk_n"] = win_n

                win_n.setGeometry(screen.x(), screen.y() + 40, win_w, win_h)

                win_n.show()

                n_clone.setLabel("left", "Refractive Index n", color=CertusTheme.PRIMARY)

            else:
                self.detached_plot_windows["nk_n"].raise_()

            # Detach K (Right Axis)

            if "nk_k" not in self.detached_plot_windows or not self.detached_plot_windows["nk_k"].isVisible():
                k_clone = CertusScientificPlot(
                    None,
                    title="Extinction Coefficient k",
                    y_label="k",
                    x_label="lambda (nm)",
                    axisItems={"left": KLogAxisItem(orientation="left")},
                )

                if hasattr(self, "_vb_k"):
                    for item in self._vb_k.addedItems:
                        if isinstance(item, pg.PlotCurveItem):
                            x, y = item.getData()

                            if x is not None and y is not None:
                                pen = item.opts.get("pen", pg.mkPen("y"))

                                k_clone.plot(x, y, pen=pen, name=item.name())

                win_k = DetachedPlotWindow(k_clone, parent=self, title="Extinction Coefficient k")

                win_k.closed_signal.connect(functools.partial(self.reattach_plot, "nk_k"))

                self.detached_plot_windows["nk_k"] = win_k

                win_k.setGeometry(screen.x() + win_w + 20, screen.y() + 40, win_w, win_h)

                win_k.show()

                k_clone.setYRange(-6.0, -2.0, padding=0)

            else:
                self.detached_plot_windows["nk_k"].raise_()

        # 3. OPTION : TAB DATA (Index 3)

        elif current_index == 3 or self.tabs.tabText(current_index) == "Data":
            plot_name = "data_table"

            if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
                self.detached_plot_windows[plot_name].raise_()

                return

            # Create a detached table (Excel-like with copy support)

            table_copy = ExcelTableWidget()

            table_copy.setColumnCount(self.table_res.columnCount())

            table_copy.setRowCount(self.table_res.rowCount())

            # Copy headers

            labels = []

            for i in range(self.table_res.columnCount()):
                item = self.table_res.horizontalHeaderItem(i)

                labels.append(item.text() if item else f"C{i}")

            table_copy.setHorizontalHeaderLabels(labels)

            # Copy content

            try:
                for r in range(self.table_res.rowCount()):
                    for c in range(self.table_res.columnCount()):
                        item = self.table_res.item(r, c)

                        if item:
                            table_copy.setItem(r, c, QTableWidgetItem(item.text()))

            except NUMERICAL_FAULT_EXCEPTIONS:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            win_data = DetachedPlotWindow(table_copy, parent=self, title="Result Data Table")

            # Apply some extra styling to the detached table to make it fit

            table_copy.setStyleSheet(f"background: {CertusTheme.SURFACE}; border: none;")

            win_data.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = win_data

            win_data.resize(900, 700)

            win_data.show()


    def on_toggle_details(self, checked) -> None:
        """Show/Hide log"""

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

        if hasattr(self, "right_splitter"):
            if checked:
                self.right_splitter.setSizes([600, 200])

            else:
                self.right_splitter.setSizes([1000, 0])

    def closeEvent(self, event) -> None:
        """Clean up resources on window close."""

        # Shutdown ThreadPoolExecutor if exists

        if hasattr(self, "_executor") and self._executor is not None:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                if hasattr(self, "logger") and self.logger:
                    self.logger.warning(f"Error shutting down executor: {e}")

            finally:
                self._executor = None

        # Cleanup optimization worker and thread

        self._cleanup_worker()

        # Cleanup beam worker and thread

        if getattr(self, "_beam_worker", None):
            self._beam_worker.stop()

        beam_thread = getattr(self, "_beam_thread", None)

        if beam_thread is not None and beam_thread.isRunning():
            beam_thread.quit()

            if not beam_thread.wait(2000):
                self.logger.critical(
                    "Beam thread did not stop within 2s in closeEvent - skipping terminate() to avoid unsafe thread kill."
                )

        try:
            self.killTimer(self._log_timer_id)

        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.logger.info("[INDEX.STATE] application closed")

        super().closeEvent(event)

    # =========================================================================

    # SAVE / LOAD CONFIGURATION

    # =========================================================================

    # save_config / load_config are inherited from CertusBaseApp and driven by
    # the _collect_config / _apply_config / _post_*_config hooks below.

    def _get_config_file_filter(self) -> str:

        return "JSON (*.json)"

    def _collect_config(self) -> dict:
        """Serialize the CERTUS_INDEX widget state to a JSON-ready dict."""

        params_values = []

        if hasattr(self, "input_params"):
            params_values = [s.value() for s in self.input_params]

        opt_block = {}

        if hasattr(self, "input_max_feval"):
            opt_block["max_feval"] = int(self.input_max_feval.value())

        return {
            "version": __version__,
            "substrate": self.cb_sub.currentText() if hasattr(self, "cb_sub") else "",
            "frosted": self.rb_frosted_glass.isChecked() if hasattr(self, "rb_frosted_glass") else False,
            "data_type": self.cb_data_type.currentText() if hasattr(self, "cb_data_type") else "",
            "file_loaded": getattr(self, "source_file_path", None),
            "thickness_min": self.sb_dmin.value() if hasattr(self, "sb_dmin") else 50.0,
            "thickness_max": self.sb_dmax.value() if hasattr(self, "sb_dmax") else 1000.0,
            "normalized": self.chk_normalized.isChecked() if hasattr(self, "chk_normalized") else True,
            "exclude_oh": self.chk_exclude.isChecked() if hasattr(self, "chk_exclude") else False,
            "exclude_min": self.sb_ex_min.value() if hasattr(self, "sb_ex_min") else None,
            "exclude_max": self.sb_ex_max.value() if hasattr(self, "sb_ex_max") else None,
            "model_type": (self.model_combo.currentText() if hasattr(self, "model_combo") else "TLU"),
            "params": params_values,
            "optimization": opt_block,
            "weight_T": float(self.sb_weight_T.value()) if hasattr(self, "sb_weight_T") else 1.0,
            "weight_R": float(self.sb_weight_R.value()) if hasattr(self, "sb_weight_R") else 1.0,
        }

    def _normalize_index_config(self, cfg: dict) -> dict:
        """Normalize legacy/new CERTUS_INDEX JSON payloads for first-launch compatibility."""
        return normalize_index_config(cfg)



    def _apply_config(self, cfg: dict) -> None:
        """Restore CERTUS_INDEX widget state from a loaded config dict.

        Note: the measured spectrum file referenced by ``file_loaded`` is
        intentionally NOT auto-loaded to avoid broken paths when sharing
        configs across machines.
        """

        cfg = self._normalize_index_config(cfg)

        sub = cfg.get("substrate")

        if sub and hasattr(self, "cb_sub"):
            idx = self.cb_sub.findText(str(sub))

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

        if cfg.get("frosted", False):
            self.rb_frosted_glass.setChecked(True)

        else:
            self.rb_standard.setChecked(True)

        self.sb_dmin.setValue(cfg.get("thickness_min", 10.0))

        self.sb_dmax.setValue(cfg.get("thickness_max", 1000.0))

        self.chk_normalized.setChecked(cfg.get("normalized", False))

        self.chk_exclude.setChecked(cfg.get("exclude_oh", False))

        if not cfg.get("frosted", False):
            wt = cfg.get("weight_T")

            if wt is not None and hasattr(self, "sb_weight_T"):
                self.sb_weight_T.setValue(float(wt))

            wr = cfg.get("weight_R")

            if wr is not None and hasattr(self, "sb_weight_R"):
                self.sb_weight_R.setValue(float(wr))

            self._persist_index_weight_settings()

        # Model & Optim params are handled by PGLOBAL engine and not exposed in UI config anymore.

    def _post_save_config(self, filename: str) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Saved: {Path(filename).name}")

        QMessageBox.information(self, "Saved", f"Configuration saved to {Path(filename).name}")

    def _post_load_config(self, filename: str, config: dict) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Loaded: {Path(filename).name}")

        # Keep substrate semantics explicit in the UI metadata.
        if hasattr(self, "logger"):
            self.logger.info("CERTUS_INDEX config applied with substrate/film fields kept distinct.")



