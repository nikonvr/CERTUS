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

from certus.ui.certus_index_ui_utils import (
    _log_loaded_spectrum_metadata,
    _detected_data_type_label,
    _update_lambda_bounds_from_target_data,
    _source_type_label,
    _is_qt_offscreen_mode,
    _notify_user,
    _update_loaded_file_label,
    _set_spectrum_plot_title,
    _display_detected_data_type,
    _prepare_nk_plot_inputs,
)

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

from certus.ui.certus_index_ui_utils import KLogAxisItem

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





