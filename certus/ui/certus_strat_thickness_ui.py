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

class TransmissionVsThicknessWindow(CertusWindowSpyMixin, QMainWindow):
    """Interactive analysis window: T(λ) vs cumulative thickness for a single strategy.

    Lifecycle — same rules as ``StrategySpectralPerformanceWindow``
    ---------------------------------------------------------------
    Stored in ``CertusStratApp.transmission_windows`` to prevent garbage
    collection.  Removing it from that list while the window is open causes
    Qt to destroy the C++ peer and crash on the next repaint.

    Deferred drawing — ``QTimer.singleShot(0, ...)``
    -------------------------------------------------
    The heavy ``_draw_complete_graph`` call is deferred to the next
    event-loop turn via ``QTimer.singleShot(0, …)``.
    BUG HISTORY: calling it directly in ``__init__`` during rapid Phase-B
    window creation (multiple windows opened in quick succession) triggered
    re-entrant ``QPainter`` state, producing ``QPainter::begin`` warnings
    and occasional black plots.
    RULE: keep this deferral.  Do NOT move the draw call back into
    ``__init__`` even if it appears to work during light testing.

    ``db_instance`` resolution — same 3-level fallback as
    ``StrategySpectralPerformanceWindow``
    -------------------------------------------------------
    See :class:`StrategySpectralPerformanceWindow` for the full rationale.
    Always use::

        db_instance = (
            params.get('materials_db_instance')
            or params.get('materials_db')
            or APP_CONTEXT.get('materials_db')
        )
    """

    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] TransmissionVsThicknessWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        strategy = strategy_result["strategy"]

        self.setWindowTitle(f"Interactive Analysis - Strategy #{strategy['strategy_id']}")

        self.setGeometry(150, 150, 1450, 950)

        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] Opening TransmissionVsThicknessWindow for strategy #%s",
            strategy.get("strategy_id", "unknown"),
        )

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 5, 15, 5)

        lbl_title = QLabel(f"<b>STRATEGY #{strategy['strategy_id']}</b>")

        lbl_title.setStyleSheet(f"font-size: 16px; color: {CertusTheme.CHART_PRIMARY};")

        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Transmission vs Cumulative Thickness",
            x_label="Cumulative Thickness (nm)",
            y_label="Transmission",
        )

        self.plot_widget.plotItem.setYRange(-0.05, 1.15)

        self.plot_widget.plotItem.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.plotItem

        self.p2 = pg.ViewBox()

        self.p1.scene().addItem(self.p2)

        self.p1.getAxis("right").linkToView(self.p2)

        self.p2.setXLink(self.p1)

        self.p1.getAxis("right").setLabel("Avg Error (nm)", color=CertusTheme.CHART_PURPLE)

        self.p1.getAxis("right").show()

        self.p1.vb.sigResized.connect(self.update_views)

        # Defer the heavy draw work to the next event-loop turn.
        # This avoids re-entrant paint/painter state during rapid Phase B window creation.
        QTimer.singleShot(0, lambda: self._draw_complete_graph(strategy_result, opti_results, params))

        self.update_views()

    def update_views(self) -> None:

        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)

    def _draw_complete_graph(self, strategy_result, opti_results, params) -> Any:
        try:
            strategy = strategy_result["strategy"]

            blocks = strategy["blocks"]

            p_thick_nominal = opti_results["p_thick_nominal"]

            data = simulate_detailed_growth_for_ui(strategy_result, opti_results, params)

            x_detailed = np.array(data["x"])

            y_detailed = np.array(data["y"])

            boundaries = np.array(data["boundaries"])

            for i in range(len(boundaries) - 1):
                start, end = boundaries[i], boundaries[i + 1]

                center = (start + end) / 2

                is_H = i % 2 == 0

                color = QColor(255, 240, 240) if is_H else QColor(240, 248, 255)

                rect = pg.QtWidgets.QGraphicsRectItem(start, -0.2, end - start, 2.0)

                rect.setBrush(pg.mkBrush(color))

                rect.setPen(pg.mkPen(None))

                rect.setZValue(-20)

                self.p1.addItem(rect)

                line = pg.InfiniteLine(
                    pos=end,
                    angle=90,
                    pen=pg.mkPen(color=(200, 200, 200), style=Qt.PenStyle.DashLine),
                )

                line.setZValue(-15)

                self.p1.addItem(line)

                text_l = pg.TextItem(f"L{i + 1}", color=(80, 80, 80), anchor=(0.5, 0))

                font = CertusTheme.get_font(weight=QFont.Weight.Bold)

                font.setPointSize(10)

                text_l.setFont(font)

                text_l.setPos(center, 1.08)

                text_l.setZValue(10)

                self.p1.addItem(text_l)

            layer_stats = self._extract_layer_errors(strategy_result, p_thick_nominal)

            bar_x, bar_h, bar_w = [], [], []

            max_err = 0.0

            for i, stats in enumerate(layer_stats):
                if stats:
                    start, end = boundaries[i], boundaries[i + 1]

                    bar_x.append((start + end) / 2)

                    bar_h.append(stats["mean"])

                    bar_w.append((end - start) * 0.7)

                    if stats["mean"] > max_err:
                        max_err = stats["mean"]

            if bar_x:
                bars = pg.BarGraphItem(
                    x=bar_x,
                    height=bar_h,
                    width=bar_w,
                    brush=pg.mkBrush(128, 0, 128, 60),
                    pen=pg.mkPen("purple", width=1),
                )

                self.p2.addItem(bars)

                self.p2.setYRange(0, max_err * 3.0 if max_err > 0 else 1.0)

            colors = CertusTheme.CHART_COLORS

            block_start_clues = {b["start"] for b in blocks}

            for idx, block in enumerate(blocks):
                wl = block["wavelength"]

                b_start, b_end = boundaries[block["start"]], boundaries[block["end"]]

                mask = (x_detailed >= b_start - 1e-3) & (x_detailed <= b_end + 1e-3)

                pen_color = colors[idx % len(colors)]

                curve_item = self.p1.plot(
                    x_detailed[mask],
                    y_detailed[mask],
                    pen=pg.mkPen(color=pen_color, width=3),
                    name=f"{wl:.0f}nm",
                )

                if curve_item is not None:
                    self.plot_widget.add_curve_for_tracking(curve_item, f"{wl:.0f}nm")

                for l in range(block["start"], block["end"]):
                    l_start_thick = boundaries[l]

                    l_end_thick = boundaries[l + 1]

                    if l in block_start_clues and l > 0:
                        idx_start = np.searchsorted(x_detailed, l_start_thick)

                        idx_start = min(idx_start, len(y_detailed) - 1)

                        t_start_val = y_detailed[idx_start]

                        txt_start = pg.TextItem(
                            f"{t_start_val:.1%}",
                            color=CertusTheme.CHART_PRIMARY,
                            anchor=(0.5, 1),
                        )

                        txt_start.setPos(l_start_thick, t_start_val + 0.02)

                        font_s = CertusTheme.get_font(9, QFont.Weight.Bold)

                        txt_start.setFont(font_s)

                        txt_start.setZValue(25)

                        self.p1.addItem(txt_start)

                        scatter = pg.ScatterPlotItem(
                            [l_start_thick],
                            [t_start_val],
                            size=8,
                            brush=pg.mkBrush(CertusTheme.CHART_PRIMARY),
                            pen=pg.mkPen(None),
                        )

                        scatter.setZValue(25)

                        self.p1.addItem(scatter)

                    center = (l_start_thick + l_end_thick) / 2

                    txt_wl = pg.TextItem(f"{wl:.0f}", color=pen_color, anchor=(0.5, 0))

                    txt_wl.setPos(center, 1.03)

                    self.p1.addItem(txt_wl)

                    # --- EXTREMA DISTANCES IN HEADER ---

                    ext_dists = strategy.get("extrema_distances", [])

                    if l < len(ext_dists):
                        d = ext_dists[l]

                        p_s = d.get("prev_start", 999.0)

                        n_s = d.get("next_start", 999.0)

                        p_e = d.get("prev_end", 999.0)

                        n_e = d.get("next_end", 999.0)

                        if p_s < n_s:
                            val_s = p_s

                            sign_s = "-"

                        else:
                            val_s = n_s

                            sign_s = "" if n_s > 15.0 else "+"

                        if p_e < n_e:
                            val_e = p_e

                            sign_e = "-"

                        else:
                            val_e = n_e

                            sign_e = "" if n_e > 15.0 else "+"

                        def _fmt_ot(v, sign) -> Any:
                            return "NC" if v > 15.0 else f"{sign}{v:.1f}"

                        label_start = _fmt_ot(val_s, sign_s)

                        label_end = _fmt_ot(val_e, sign_e)

                        # Color: red if critical (<15), grey if NC

                        color_s = (200, 0, 0) if val_s <= 15.0 else (140, 140, 140)

                        color_e = (200, 0, 0) if val_e <= 15.0 else (140, 140, 140)

                        txt_ext = pg.TextItem(
                            f"{label_start}|{label_end}",
                            color=(max(color_s[0], color_e[0]), min(color_s[1], color_e[1]), min(color_s[2], color_e[2])),
                            anchor=(0.5, 0),
                        )

                        font_ext = CertusTheme.get_font(7, QFont.Weight.Normal)

                        txt_ext.setFont(font_ext)

                        txt_ext.setPos(center, 0.97)

                        txt_ext.setZValue(12)

                        self.p1.addItem(txt_ext)

                    idx_end = np.searchsorted(x_detailed, l_end_thick)

                    idx_end = min(idx_end, len(y_detailed) - 1)

                    t_val = y_detailed[idx_end]

                    arrow = pg.ArrowItem(
                        pos=(l_end_thick, t_val),
                        angle=180,
                        tipAngle=30,
                        baseAngle=20,
                        headLen=15,
                        pen={"color": "k", "width": 1},
                        brush="k",
                    )

                    arrow.setZValue(20)

                    self.p1.addItem(arrow)

                    txt_pct = pg.TextItem(f"{t_val:.1%}", color="black", anchor=(0, 0.5))

                    txt_pct.setPos(l_end_thick + 2, t_val)

                    txt_pct.fill = pg.mkBrush(255, 255, 255, 150)

                    txt_pct.setZValue(20)

                    self.p1.addItem(txt_pct)
        except Exception as e:
            logging.getLogger("CERTUS").error(f"[STRAT-UI] Error drawing complete graph: {e}", exc_info=True)

    def _extract_layer_errors(self, strategy_result, p_thick_nominal) -> Any:

        num_layers = len(p_thick_nominal)

        layer_stats = [None] * num_layers

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            target_idx = 1 if len(results_per_noise) > 1 else 0

            if results_per_noise:
                target_result = results_per_noise[target_idx]

                thicknesses_all = target_result.get("thicknesses_all", [])

                if thicknesses_all:
                    for i_layer in range(num_layers):
                        errors = []

                        for run_stack in thicknesses_all:
                            if len(run_stack) > i_layer:
                                err = abs(run_stack[i_layer] - p_thick_nominal[i_layer])

                                errors.append(err)

                        if errors:
                            layer_stats[i_layer] = {
                                "mean": float(np.mean(errors)),
                                "std": float(np.std(errors)),
                            }

        except (ValueError, TypeError, IndexError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        return layer_stats

