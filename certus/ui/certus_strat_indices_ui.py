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

class InteractiveIndicesWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, data_dict) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] InteractiveIndicesWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.nH = np.real(np.array(data_dict["nH"]))

        self.nL = np.real(np.array(data_dict["nL"]))

        self.setWindowTitle("Material Dispersion Check")

        self.resize(600, 400)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setStyleSheet(f"background: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(10, 5, 10, 5)

        lbl = QLabel("<b>Refractive Indices</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 13px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(15)

        def add_legend(color, text) -> None:

            l = QLabel()

            l.setFixedSize(10, 10)

            l.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

            t = QLabel(text)

            t.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            h_layout.addWidget(l)

            h_layout.addWidget(t)

            h_layout.addSpacing(10)

        add_legend(CertusTheme.PRIMARY, "High Index (H)")

        add_legend(CertusTheme.SECONDARY, "Low Index (L)")

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Refractive Index")


        self.plot_widget.addLegend = lambda *args, **kwargs: None

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.curve_H = self.plot_widget.plot(
            self.wavelengths,
            self.nH,
            pen=pg.mkPen(color=CertusTheme.PRIMARY, width=3),
            name="H",
        )

        self.curve_L = self.plot_widget.plot(
            self.wavelengths,
            self.nL,
            pen=pg.mkPen(color=CertusTheme.SECONDARY, width=3),
            name="L",
        )

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(self.wavelengths[0], self.wavelengths[-1], 0)

            all_n = np.concatenate([self.nH, self.nL])

            y_min, y_max = np.min(all_n), np.max(all_n)

            margin = (y_max - y_min) * 0.1

            self.plot_widget.setYRange(y_min - margin, y_max + margin)

        self.plot_widget.info_label.setVisible(False)

        self.plot_widget.vLine.setVisible(False)

        self.plot_widget.hLine.setVisible(False)

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen("#333", width=1, style=Qt.PenStyle.DashLine),
        )

        self.plot_widget.addItem(self.vLine)

        self.cursor_text = pg.TextItem(anchor=(0, 1), color=CertusTheme.TEXT_MAIN)

        font = CertusTheme.get_font(10)

        font.setBold(True)

        self.cursor_text.setFont(font)

        self.cursor_text.setZValue(100)

        self.plot_widget.addItem(self.cursor_text)

        self.proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.update_cursor,
        )

    def update_cursor(self, evt) -> None:

        pos = evt[0]

        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)

        x_mouse = mouse_point.x()

        if x_mouse < self.wavelengths[0] or x_mouse > self.wavelengths[-1]:
            return

        idx = np.searchsorted(self.wavelengths, x_mouse)

        if idx >= len(self.wavelengths):
            idx = len(self.wavelengths) - 1

        wl_val = self.wavelengths[idx]

        val_H = self.nH[idx]

        val_L = self.nL[idx]

        self.vLine.setPos(wl_val)

        content = f"lambda: {int(wl_val)} nm\nnH: {val_H:.3f}\nnL: {val_L:.3f}"

        self.cursor_text.setText(content)

        y_pos = mouse_point.y()

        if x_mouse > (self.wavelengths[-1] - self.wavelengths[0]) * 0.8 + self.wavelengths[0]:
            self.cursor_text.setAnchor((1, 1))

        else:
            self.cursor_text.setAnchor((0, 1))

        self.cursor_text.setPos(x_mouse, y_pos)

