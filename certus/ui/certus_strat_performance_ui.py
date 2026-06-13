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
from certus.ui.certus_plot import CertusScientificPlot
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

class StrategySpectralPerformanceWindow(CertusWindowSpyMixin, QMainWindow):
    """Detail window showing spectral transmission curves for a single strategy.

    Lifecycle
    ---------
    Instantiated on demand from :meth:`CertusStratApp.on_strategy_visualization_requested`
    when the user double-clicks a row in ``StrategiesTableWindow``.  The window
    is stored in ``self.transmission_windows`` to prevent garbage collection
    (if removed from that list the C++ peer is destroyed and Qt will crash on
    the next paint event).

    Critical invariant — ``db_instance`` resolution
    ------------------------------------------------
    ``params`` is a dict assembled by the worker **before** the thread starts;
    it may or may not carry ``'materials_db_instance'`` or ``'materials_db'``
    keys depending on which code path populated it.
    **Always** resolve the material database with the three-level fallback::

        db_instance = (
            params.get('materials_db_instance')
            or params.get('materials_db')
            or APP_CONTEXT.get('materials_db')
        )

    Omitting any level caused flat transmission curves in
    :meth:`_calculate_and_plot` (bug fixed 2026-05-27).
    """

    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategySpectralPerformanceWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        strategy_id = strategy_result["strategy"]["strategy_id"]

        self.setWindowTitle(f"Spectral Performance - Strategy #{strategy_id}")

        self.resize(800, 600)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 8, 15, 8)

        lbl = QLabel(f"<b>Spectral Robustness Analysis</b> (Strategy #{strategy_id})")

        lbl.setStyleSheet(f"color: {CertusTheme.CHART_PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Final Spectral Distribution",
            x_label="Wavelength (nm)",
            y_label="Transmission",
        )


        self.plot_widget.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._calculate_and_plot(strategy_result, opti_results, params)

    def _calculate_and_plot(self, strategy_result, opti_results, params) -> None:
        try:
            wl_min = float(params.get("wavelength_min", 380.0))
            wl_max = float(params.get("wavelength_max", 1000.0))

            data = simulate_spectral_distribution_for_ui(strategy_result, opti_results, params)
            if not data:
                return

            wls = np.array(data["wls"])
            T_nom = np.array(data["T_nom"])
            mean = np.array(data["mean"])
            p5 = np.array(data["p5"])
            p95 = np.array(data["p95"])

            c_up = pg.PlotCurveItem(x=wls, y=p95, pen=None)
            c_down = pg.PlotCurveItem(x=wls, y=p5, pen=None)
            fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(14, 165, 233, 50))
            fill.setZValue(-10)
            self.plot_widget.addItem(fill)

            self.plot_widget.plot(
                wls,
                mean,
                pen=pg.mkPen(
                    color=CertusTheme.CHART_SECONDARY,
                    width=2,
                    style=Qt.PenStyle.DashLine,
                ),
                name="Mean MC",
            )

            self.plot_widget.plot(
                wls,
                T_nom,
                pen=pg.mkPen(color=CertusTheme.CHART_DANGER, width=2.5),
                name="Nominal Target",
            )

            self.plot_widget.setXRange(wl_min, wl_max)
            self.plot_widget.setYRange(0, 1.0)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Error plotting spectral performance: {e}")

