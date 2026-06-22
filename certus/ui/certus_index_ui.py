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

from certus.ui.certus_index_ui_layout import CertusIndexLayoutMixin
from certus.ui.certus_index_ui_state import CertusIndexStateMixin
from certus.ui.certus_index_ui_events import CertusIndexEventsMixin
from certus.ui.certus_index_ui_worker import CertusIndexWorkerMixin
from certus.ui.certus_index_ui_plot import CertusIndexPlotMixin
from certus.ui.certus_index_ui_export import CertusIndexExportMixin


class CertusIndexApp(CertusIndexLayoutMixin, CertusIndexStateMixin, CertusIndexEventsMixin, CertusIndexWorkerMixin, CertusIndexPlotMixin, CertusIndexExportMixin, CertusBaseApp):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
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































































    # =========================================================================

    # EXCEL EXPORT

    # =========================================================================









    # =========================================================================

    # SAVE / LOAD CONFIGURATION

    # =========================================================================

    # save_config / load_config are inherited from CertusBaseApp and driven by
    # the _collect_config / _apply_config / _post_*_config hooks below.







        # Model & Optim params are handled by PGLOBAL engine and not exposed in UI config anymore.





