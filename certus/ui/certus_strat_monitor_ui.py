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
from certus.ui.certus_plot import CertusScientificPlot
from certus.ui.certus_ui import setup_pyqtgraph_defaults
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
from certus.ui.certus_plot import CertusScientificPlot
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

class LiveMonitorWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent=None) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] LiveMonitorWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.setWindowTitle("Phase B: Live Growth Monitor")

        self.resize(1200, 600)

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        # Simple main layout (no more Splitter)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        # -- Growth widget only --

        self.growth_widget = QWidget()

        growth_layout = QVBoxLayout(self.growth_widget)

        self.header_label = QLabel("Waiting for data...")

        self.header_label.setStyleSheet(
            f"background-color: {CertusTheme.PRIMARY}; color: white; padding: 10px; font-weight: bold; font-size: 14px;"
        )

        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        growth_layout.addWidget(self.header_label)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Optical Thickness vs Transmission",
            x_label="Physical Thickness (nm)",
            y_label="Transmission",
        )



        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        self.plot_widget.setYRange(0, 1.0, 0)

        growth_layout.addWidget(self.plot_widget)

        self.layout.addWidget(self.growth_widget)

        # Plot data

        self.layer_lines = []

        self.block_items = []

        self.curve_segments = []

        self.text_labels = []

        self.user_hidden = False

        self.colors = [
            "#d62728",
            "#2ca02c",
            "#1f77b4",
            "#ff7f0e",
            "#9467bd",
            "#17becf",
            "#e377c2",
            "#bcbd22",
            "#8c564b",
        ]

    def update_monitor(self, x, y, bounds, info_text, strategy_blocks) -> None:

        self.header_label.setText(info_text)

        # Clean Plot

        self.plot_widget.plotItem.clear()

        # Re-add layer lines (they were removed by clear())

        while len(self.layer_lines) < len(bounds):
            line = pg.InfiniteLine(
                angle=90,
                pen=pg.mkPen(color="#94a3b8", style=Qt.PenStyle.DashLine, width=1.5),
            )

            line.setZValue(5)

            self.layer_lines.append(line)

        for i, b in enumerate(bounds):
            if self.layer_lines[i] not in self.plot_widget.plotItem.items:
                self.plot_widget.addItem(self.layer_lines[i])

            self.layer_lines[i].setPos(b)

            self.layer_lines[i].show()

        # Reset collections since clear() removed everything

        self.block_items.clear()

        self.curve_segments.clear()

        self.text_labels.clear()

        # Drawing the strategy

        if strategy_blocks:
            x_arr = np.array(x, dtype=np.float64)

            y_arr = np.array(y, dtype=np.float64)

            # Clip x < 0 (digital artifact) to avoid erroneous trace on the left

            valid = x_arr >= 0.0

            x_arr = x_arr[valid]

            y_arr = y_arr[valid]

            for i, block in enumerate(strategy_blocks):
                wl = float(block["wavelength"])

                start_layer = block["start"]

                end_layer = block["end"]

                color = self.colors[i % len(self.colors)]

                if start_layer < len(bounds) and end_layer < len(bounds):
                    x_start = bounds[start_layer]

                    x_end = bounds[end_layer]

                    width = x_end - x_start

                    x_center = (x_start + x_end) / 2.0

                    mask = (x_arr >= x_start - 1e-3) & (x_arr <= x_end + 1e-3)

                    if np.any(mask):
                        segment = self.plot_widget.plot(
                            x_arr[mask],
                            y_arr[mask],
                            pen=pg.mkPen(color=color, width=2.5),
                        )

                        self.curve_segments.append(segment)

                    if i < len(strategy_blocks) - 1:
                        sep_line = pg.InfiniteLine(pos=x_end, angle=90, pen=pg.mkPen(color="#ef4444", width=2))

                        sep_line.setZValue(10)

                        self.plot_widget.addItem(sep_line)

                        self.block_items.append(sep_line)

                    label_text = f"{int(wl)}"

                    text_item = pg.TextItem(text=label_text, color=color, anchor=(0.5, 0.5))

                    font = CertusTheme.get_font()

                    font.setBold(True)

                    rotation = 0

                    if width < 50:
                        font.setPointSize(8)

                        rotation = -90

                    elif width < 150:
                        font.setPointSize(9)

                    else:
                        font.setPointSize(11)

                    text_item.setFont(font)

                    if rotation != 0:
                        text_item.setAngle(rotation)

                    is_staggered_low = i % 2 != 0

                    y_pos = 0.05 if is_staggered_low else 0.15

                    text_item.setPos(x_center, y_pos)

                    self.plot_widget.addItem(text_item)

                    self.text_labels.append(text_item)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] LiveMonitorWindow.closeEvent() user_hidden=True title='%s' id=%s geometry=%s visible=%s",
            self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )

        self.user_hidden = True

        self.hide()

        event.ignore()

