# =============================================================================
# CERTUS STRAT - PyQt6 User Interface components and application
# =============================================================================
import sys
import os
import functools
from pathlib import Path
import concurrent.futures
import multiprocessing

import ctypes

import hashlib

import io

import json

import logging

import queue

import threading

import time

import traceback

from collections import deque

from typing import Any, Dict
from dataclasses import dataclass

import numpy as np

import pandas as pd
from pydantic import ValidationError

import pyqtgraph as pg

from pyqtgraph.exporters import ImageExporter, SVGExporter

from certus.ui.certus_ui import setup_pyqtgraph_defaults

# Conditional import of Svg for the logo

try:
    from PyQt6.QtSvgWidgets import QSvgWidget

except ImportError:
    QSvgWidget = None

from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)

from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTransform,
)

from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsRectItem,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Import access config

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_MAPPING,
    get_export_config,
    get_resource_path,
    get_safe_worker_count,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
    __version__,
)

from certus.utils.certus_data import (
    OPENPYXL_AVAILABLE,
    PerformanceMonitor,
    SharedArrayManager,
    SharedArrayWorker,
    SharedIndicesManager,
    SharedIndicesWorker,
    TimingLogger,
    generate_html_report,
    get_missing_manifest_fields,
    numpy_encoder,
    to_csv_robust,
    to_excel_robust,
)

from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    calculate_RT_vectorized_real_HL,
    compute_batch_rmse,
    find_nucleation_adaptive_kernel,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    update_run_states_kernel,
    validate_wavelengths_batch,
)

# Import context system (replaces global variables)

from certus.utils.certus_strat_context import (
    StratContext,
    get_context,
    SYM_MISSING_DISTANCE,
    FAST_AUTO_BLOCKS_DIVIDER_PRESETS,
    _clamp01,
    _compute_local_extrema_symmetry_score,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_contractual,
    _compute_blocks_range_for_params,
    _validate_strategy_blocks_contract,
    _augment_solution_cost_with_sym,
    _origin_family,
    _parse_origin_priority_map,
    _origin_priority_from_map,
    _apply_family_diversity,
    _blocks_signature,
    _strategy_signature,
    _strategy_id_sort_token,
    _extract_rmse_p95_for_noise,
    _dedupe_preserve_order_int,
    _default_consensus_seeds,
    _resolve_consensus_top_k,
    _resolve_consensus_num_seeds,
    _resolve_consensus_seed_stride,
    _resolve_consensus_num_runs,
)

# Robust db clues (fixed xlsx)

from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO
from certus.core.certus_strat_core import (
    APP_CONTEXT,
    _compute_strategy_symmetry_score_percent,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    SYM_DEFAULT_SCORING_MODE,
    _SPECTRUM_COUNTER,
    PlotCache,
    precompute_clues_and_matrices,
    set_robust_material_db,
)

from certus.ui.certus_ui import (
    CERTUS_UI_STRINGS,
    CertusBaseApp,
    CertusLogPanel,
    CertusTheme,
    CertusThemeToggle,
    CertusCard,
    CertusStatusPill,
    ExcelTableWidget,
    FlashyCard,
    NumericTableWidgetItem,
    apply_certus_theme,
    attach_excel_clipboard_context_menu,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    copy_plot_to_clipboard_excel,
    create_header_logo_widget,
    create_top_actions_bar,
    get_certus_last_dir,
    get_export_settings,
    init_certus_app,
    open_documentation,
    open_file_explorer,
    plot_dataframe_from_widget,
    set_certus_last_dir,
    set_certus_window_icon,
    create_styled_button,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    safe_ui_action,
)
from certus.ui.certus_ui_shared import apply_app_zoom
from certus.utils.certus_export import show_copy_excel_feedback

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.workers.certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
from certus.workers.certus_strat_workers import (
    _resolve_strat_indices_db_path,
    WorkerThread,
    PlotRenderWorker,
    StratTask,
)
import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import (
    StratStrategyService,
    calculate_nominal_properties,
    calculate_RT_normal_real,
    calculate_dynamics_ULTIMATE,
    _select_candidates_phase_a,
    _validate_candidates_phase_a as _service_validate_candidates_phase_a,
    compute_probe_offset_nm_from_ratio,
    generate_noise_array,
    NOISE_DISTRIBUTION_GAUSSIAN,
    select_best_strat_result,
    extract_best_rmse,
    rebuild_visualization_context,
    simulate_detailed_growth_for_ui,
    simulate_spectral_distribution_for_ui,
)


from certus.ui.certus_strat_mixins_ui import CertusWindowSpyMixin
from certus.ui.certus_strat_table_ui import StrategiesTableWindow
from certus.ui.certus_strat_plots_ui import CertusScientificPlot, UniversalPlotWindow
from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
from certus.ui.certus_strat_thickness_ui import TransmissionVsThicknessWindow
from certus.ui.certus_strat_performance_ui import StrategySpectralPerformanceWindow
from certus.ui.certus_strat_json_ui import JsonViewerWindow
from certus.ui.certus_strat_indices_ui import InteractiveIndicesWindow
from certus.ui.certus_strat_spectrum_ui import InteractiveSpectrumWindow
from certus.ui.certus_strat_popout_ui import PopOutWindow
from certus.ui.certus_strat_monitor_ui import LiveMonitorWindow
from certus.ui.certus_strat_welcome_ui import WelcomeGuideWidget



# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# === GUI CLASSES (RECONSTITUTION STYLE VERSION D) ===










# QueueHandler and setup_gui_logger are imported from certus.ui.certus_ui

# === OPTIMIZATION: LiveMonitor with Convergence Plot ===


from certus.ui.certus_strat_ui_layout import CertusStratLayoutMixin
from certus.ui.certus_strat_ui_state import CertusStratStateMixin
from certus.ui.certus_strat_ui_events import CertusStratEventsMixin
from certus.ui.certus_strat_ui_worker import CertusStratWorkerMixin
from certus.ui.certus_strat_ui_plot import CertusStratPlotMixin
from certus.ui.certus_strat_ui_export import CertusStratExportMixin


class CertusStratApp(CertusBaseApp, CertusWindowSpyMixin, CertusStratLayoutMixin, CertusStratStateMixin, CertusStratEventsMixin, CertusStratWorkerMixin, CertusStratPlotMixin, CertusStratExportMixin):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
    """Main CERTUS-STRAT Application"""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-STRAT"

    APP_TITLE = "Predictive Monitoring Strategy"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:

        super().__init__()

        # --- Cache & Async Init ---

        self._plot_cache = PlotCache()
        self._cache_lock = threading.Lock()

        self._rendering_plots = set()

        self._active_render_thread = None

        self._active_worker_threads: list[QThread] = []

        self._stopping_threads: list[QThread] = []

        # STRAT-specific state

        self.plot_queue: queue.Queue = queue.Queue()

        self.plot_windows: list[UniversalPlotWindow] = []

        self.strategies_table_window: StrategiesTableWindow | None = None

        self.transmission_windows: list[TransmissionVsThicknessWindow] = []

        self.json_windows: list[JsonViewerWindow] = []

        self._floating_stack_window = None

        self.heatmap_window = None

        self.clues_window = None

        self.stack_visual_window = None

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        self.timing_logger = TimingLogger(self.logger)

        # Materials database

        self.materials_db = MaterialDatabase(_resolve_strat_indices_db_path())

        APP_CONTEXT["materials_db"] = self.materials_db

        self.material_list = list(self.materials_db.data.keys()) if self.materials_db.data else []

        self.opti_results: dict[str, Any] | None = None

        self.undo_stack = deque(maxlen=5)

        self.live_monitor_window = None
        self._live_strategy_popups: list[QMessageBox] = []

        # Build UI

        self._build_gui()

        self._apply_theme()

        self.set_default_values()

        self._init_widget_states()

        # STRAT uses two timers: log + plot

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        self.plot_timer = self.startTimer(200)

        # Disable buttons until warmup completes

        self.run_step0_btn.setEnabled(False)

        self.run_step2_btn.setEnabled(False)

        self.run_full_btn.setEnabled(False)

        self.status_label.setText("System warming up (compiling JIT)...")

        # Warmup in background thread

        threading.Thread(target=self._warmup_numba, daemon=True).start()

        # Post-init setup

        QTimer.singleShot(100, lambda: self._init_undo_shortcut())

        QTimer.singleShot(0, self.apply_default_layout)











































































    # === OPTIMIZATION: Hashed & Async Plot Update ===






    # ===============================================





# Backward-compatible alias kept for existing callers/tests.
CertusSTRATApp = CertusStratApp

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # NOTE: We do NOT touch SystemConfig.setup_numba_cache() here

    # because it's already done at the top of the file and at COMMON import.

    # Calling startup logging helper is OK because it doesn't touch Numba.

    setup_module_logging("STRAT", log_file="strat.log")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Application creation (MUST be done before theme)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-STRAT", app=app)

    # --- SPLASH SCREEN ---

    from certus.ui.certus_splash import create_splash

    splash = create_splash("Initializing CERTUS STRAT...")


    # ROBUST MATERIAL DATABASE FIX: canonical indices.xlsx in example/database_index

    # with legacy fallback to clues.xlsx for compatibility.

    clues_file = _resolve_strat_indices_db_path()

    logging.info(f"[ROBUST DB] Checking material DB at:{clues_file}")

    splash.showMessage(
        "Loading Material Database...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    if Path(clues_file).exists():
        try:
            robust_db = RobustMaterialDatabase(clues_file)

            APP_CONTEXT["materials_db"] = robust_db

            set_robust_material_db(robust_db)  # Set global reference for priority access

            logging.info(f"[ROBUST DB] ✓ Activated with {len(robust_db.materials)} materials")

        except (ValueError, RuntimeError, AttributeError, KeyError, FileNotFoundError) as e:
            logging.warning(f"[ROBUST DB] ✗ Failed to load: {e}")

            splash.showMessage(
                f"DB Error: {e}",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                Qt.GlobalColor.red,
            )

            logging.warning("[ROBUST DB] Continuing startup without splash delay loop.")

    else:
        logging.warning("[ROBUST DB] ✗ File not found, using fallback")

    # Windows AppUserModelID configuration (optional)

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("certus.strat.2.0")

    except (OSError, AttributeError, ImportError):
        # Windows-specific API, may fail on other platforms or if unavailable

        pass

    splash.showMessage(
        "Starting User Interface...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    # Launch

    win = CertusStratApp()

    win.show()

    splash.finish(win)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_configuration(f))

    sys.exit(app.exec())
