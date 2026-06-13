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
from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
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

class CertusScientificPlot(pg.PlotWidget):
    def __init__(self, parent=None, title="", y_label="", x_label="") -> None:

        super().__init__(parent)

        self.setDownsampling(mode="peak")

        self.setClipToView(True)

        self.showGrid(x=True, y=True, alpha=0.15)



        self.plotItem.setTitle(title, color=CertusTheme.CHART_PRIMARY, size="12pt")

        self.plotItem.setLabels(left=y_label, bottom=x_label)

        axis_pen = pg.mkPen(color="k", width=1)

        self.getAxis("bottom").setPen(axis_pen)

        self.getAxis("left").setPen(axis_pen)

        self.getAxis("bottom").setTextPen("k")

        self.getAxis("left").setTextPen("k")

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=1, style=Qt.PenStyle.DashLine),
        )

        self.hLine = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=1, style=Qt.PenStyle.DashLine),
        )

        self.addItem(self.vLine)

        self.addItem(self.hLine)

        self.info_label = pg.TextItem(anchor=(0, 1), color=CertusTheme.CHART_PRIMARY)

        self.addItem(self.info_label)

        self.proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse_move)

        self._tracked_curves = []

        self._copy_excel_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)

        self._copy_excel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._copy_excel_shortcut.activated.connect(self._on_copy_excel_clipboard)

    def _on_copy_excel_clipboard(self) -> None:

        self._copy_excel_tsv(show_message=True)

    def _copy_excel_tsv(self, show_message: bool = True) -> None:

        ok = copy_plot_to_clipboard_excel(self)

        if not show_message:
            return

        parent = self.window() or None
        show_copy_excel_feedback(parent, ok)

    def add_curve_for_tracking(self, curve_item, name) -> None:

        self._tracked_curves.append({"curve": curve_item, "name": name})

    def on_mouse_move(self, evt) -> None:

        pos = evt[0]

        if self.sceneBoundingRect().contains(pos):
            mouse_point = self.plotItem.vb.mapSceneToView(pos)

            x_mouse = mouse_point.x()

            y_mouse = mouse_point.y()

            self.vLine.setPos(x_mouse)

            self.hLine.setPos(y_mouse)

            info_text = [f"x = {x_mouse:.2f}"]

            for item in self._tracked_curves:
                curve = item["curve"]

                x_data, y_data = curve.xData, curve.yData

                if x_data is not None and len(x_data) > 1:
                    if x_mouse < x_data[0] or x_mouse > x_data[-1]:
                        continue

                    idx = np.searchsorted(x_data, x_mouse)

                    if 0 < idx < len(x_data):
                        x0, x1 = x_data[idx - 1], x_data[idx]

                        y0, y1 = y_data[idx - 1], y_data[idx]

                        if x1 != x0:
                            y_val = y0 + (y1 - y0) * (x_mouse - x0) / (x1 - x0)

                            info_text.append(f"{item['name']}: {y_val:.4f}")

            self.info_label.setText("\n".join(info_text))

            self.info_label.setPos(x_mouse, y_mouse)

    def get_toolbar(self, parent_widget) -> Any:

        toolbar = QToolBar(parent_widget)

        toolbar.setStyleSheet(
            f"QToolBar {{ background: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER}; spacing: 5px; }} QToolButton {{ padding: 4px; border-radius:3px; }} QToolButton:hover {{ background-color: {CertusTheme.SURFACE_HOVER}; }}"
        )

        act_reset = QAction("⟲ Reset", parent_widget)

        act_reset.triggered.connect(self.plotItem.autoRange)

        toolbar.addAction(act_reset)

        toolbar.addSeparator()

        act_mode = QAction("✋ Pan/Box", parent_widget)

        act_mode.setCheckable(True)

        act_mode.toggled.connect(self._toggle_mode)

        toolbar.addAction(act_mode)

        toolbar.addSeparator()

        # New Export Menu

        export_btn = QToolButton()

        export_btn.setText("💾 Export")

        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(export_btn)

        act_png = QAction("🖼️ PNG (Image)", parent_widget)

        act_png.triggered.connect(self._export_png)

        menu.addAction(act_png)

        act_svg = QAction("✏️ SVG (Vector)", parent_widget)

        act_svg.triggered.connect(self._export_svg)

        menu.addAction(act_svg)

        act_csv = QAction("📊 CSV (Data)", parent_widget)

        act_csv.triggered.connect(self._export_csv)

        menu.addAction(act_csv)

        act_copy = QAction(CERTUS_UI_STRINGS["copy_excel_tsv"], parent_widget)

        act_copy.setToolTip("Ctrl+Shift+C - TSV for Excel")

        act_copy.triggered.connect(self._on_copy_excel_clipboard)

        menu.addAction(act_copy)

        export_btn.setMenu(menu)

        toolbar.addWidget(export_btn)

        return toolbar

    def _toggle_mode(self, checked) -> None:

        if checked:
            self.plotItem.vb.setMouseMode(pg.ViewBox.PanMode)

        else:
            self.plotItem.vb.setMouseMode(pg.ViewBox.RectMode)

    def _export_png(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "Export Graph", str(Path(get_certus_last_dir() or ".") / "plot.png"), "PNG Image (*.png)"
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                exporter = ImageExporter(self.plotItem)

                opts = get_export_settings()

                exporter.parameters()["width"] = opts.get("width", 1920)

                if opts.get("height"):
                    exporter.parameters()["height"] = opts["height"]

                exporter.export(filename)

                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.error(f"Export Error:{e}")

                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"PNG : {e}",
                )

    def _export_svg(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "SVG export", str(Path(get_certus_last_dir() or ".") / "plot.svg"), "SVG Files (*.svg)"
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                exporter = SVGExporter(self.plotItem)

                exporter.export(filename)

                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.error(f"Export Error:{e}")

                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"SVG : {e}",
                )

    def _export_csv(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "Export Data", str(Path(get_certus_last_dir() or ".") / "plot_data.csv"), "CSV Files (*.csv)"
        )

        if not filename:
            return

        set_certus_last_dir(filename)

        try:
            df = plot_dataframe_from_widget(self)

            if df is None or df.empty:
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    CERTUS_UI_STRINGS["no_data"],
                )

                return

            to_csv_robust(df, filename, index=False)

            QMessageBox.information(
                self.window() or None,
                CERTUS_UI_STRINGS["export"],
                f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Export Error:{e}")

            QMessageBox.warning(
                self.window() or None,
                CERTUS_UI_STRINGS["export_failed"],
                f"CSV : {e}",
            )

class UniversalPlotWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, data_obj, plot_type) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] UniversalPlotWindow created (plot_type=%s, id=%s, parent=%s)",
            plot_type, id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.setWindowTitle("Data Visualization")

        self.resize(1000, 700)

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        if plot_type == "stack_visual":
            self._init_stack_plot(data_obj)

        elif plot_type == "sensitivity_popup":
            self._init_sensitivity_plot(data_obj)

        elif plot_type == "seel_analysis_plot":
            self._init_seel_plot(data_obj)

        elif plot_type == "block_assignments":
            self._init_strategies_plot(data_obj)

        elif plot_type == "robustness_popout":
            self._init_robustness_plot(data_obj)

        elif plot_type == "pyqtgraph_heatmap":
            self._init_heatmap(data_obj)

        else:
            self.layout.addWidget(QLabel(f"Unknown plot type: {plot_type}"))

    def _init_stack_plot(self, data) -> Any:

        self.setWindowTitle("Stack Design Structure")

        p_thick = data.get("p_thick", [])

        multipliers = data.get("multipliers", [])

        if multipliers is None:
            multipliers = [1.0] * len(p_thick)

        if len(multipliers) < len(p_thick):
            multipliers.extend([1.0] * (len(p_thick) - len(multipliers)))

        num_layers = len(p_thick)

        plot = CertusScientificPlot(self, "Stack Design Structure", "Layer Number", "Physical Thickness (nm)")

        plot.showGrid(y=True, x=True, alpha=0.3)

        COLOR_H = QColor(CertusTheme.CHART_PRIMARY)

        COLOR_L = QColor(CertusTheme.CHART_SECONDARY)

        max_thick = max(p_thick) if p_thick else 100.0

        for i in range(num_layers):
            thickness = p_thick[i]

            multiplier = multipliers[i]

            is_H = i % 2 == 0

            bar = QGraphicsRectItem(0, i + 0.1, thickness, 0.8)

            col = COLOR_H if is_H else COLOR_L

            bar.setBrush(pg.mkBrush(col))

            bar.setPen(pg.mkPen("k", width=1))

            plot.addItem(bar)

            label_text = f"{'H' if is_H else 'L'}{i + 1}: {thickness:.1f}nm ({multiplier:.2f}Q)"

            txt = pg.TextItem(label_text, color=CertusTheme.TEXT_SUB, anchor=(0, 0.5))

            txt.setPos(thickness + (max_thick * 0.02), i + 0.5)

            plot.addItem(txt)

        plot.setYRange(0, num_layers + 1)

        plot.setXRange(0, max_thick * 1.3)

        plot.invertY(True)

        def _stack_clipboard_df() -> Any:

            rows = []

            for i in range(num_layers):
                thickness = float(p_thick[i])

                multiplier = float(multipliers[i])

                is_h = i % 2 == 0

                rows.append(
                    {
                        "layer_from_air": i + 1,
                        "material": "H" if is_h else "L",
                        "thickness_nm": thickness,
                        "Q_multiplier": multiplier,
                    }
                )

            return pd.DataFrame(rows)

        plot._certus_clipboard_df_provider = _stack_clipboard_df

        attach_excel_clipboard_context_menu(plot)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_sensitivity_plot(self, data) -> None:

        self.setWindowTitle("Sensitivity Analysis Dashboard")

        wl = data["wavelengths"]

        T_nom = data["T_nominal"]

        envelopes = data["envelopes"]

        sigmas = sorted(envelopes.keys())

        if sigmas:
            sigma_str = ", ".join([str(s) for s in sigmas])

            title = f"Sensitivity Analysis (Noise sigma = {sigma_str} nm)"

        else:
            title = "Sensitivity Analysis"

        plot = CertusScientificPlot(self, title, "Transmission", "Wavelength (nm)")

        nom_curve = plot.plot(
            wl,
            T_nom,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2),
            name="Nominal Target",
        )

        plot.add_curve_for_tracking(nom_curve, "Nominal")

        colors = {
            2.0: (200, 200, 200, 60),
            1.0: (14, 165, 233, 70),
            0.5: (30, 58, 138, 90),
        }

        for sigma in sorted(envelopes.keys(), reverse=True):
            env = envelopes[sigma]

            p5 = env["p5"]

            p95 = env["p95"]

            c_upper = pg.PlotCurveItem(x=wl, y=p95, pen=None)

            c_lower = pg.PlotCurveItem(x=wl, y=p5, pen=None)

            fill_color = colors.get(sigma, (100, 100, 100, 50))

            fill = pg.FillBetweenItem(c_upper, c_lower, brush=pg.mkBrush(fill_color))

            plot.addItem(c_upper)

            plot.addItem(c_lower)

            plot.addItem(fill)

        plot.setYRange(0, 1.05)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_seel_plot(self, data) -> list | None:

        self.setWindowTitle("Statistical Equivalent Error per Layer Analysis")

        self.resize(500, 350)

        sigmas = np.array(data["sigmas"], dtype=np.float64)

        rmses = np.array(data["avg_rmse"], dtype=np.float64)

        # Keep only finite positive values for log-domain plotting.

        valid_mask = np.isfinite(sigmas) & np.isfinite(rmses) & (sigmas > 0.0) & (rmses > 0.0)

        if np.any(valid_mask):
            sigmas = sigmas[valid_mask]

            rmses = rmses[valid_mask]

        else:
            # Defensive fallback to avoid NaN/inf transforms in pyqtgraph.

            sigmas = np.array([1e-3, 1e-2], dtype=np.float64)

            rmses = np.array([1e-3, 1e-2], dtype=np.float64)

        fit_k = data.get("fit_k", 1.0)

        fit_alpha = data.get("fit_alpha", 1.0)

        plot = CertusScientificPlot(
            self,
            "Statistical Equivalent Error per Layer Analysis",
            "SEEL Sigma (nm)",
            "Spectral RMSE",
        )

        plot.setLogMode(x=True, y=True)

        # POLICE REDUITE (6pt)

        font_axis = CertusTheme.get_font(6)

        # --- Helper to generate ticks 1, 2, 3, 4, 5 ---

        def generate_custom_log_ticks(min_val, max_val) -> list | None:

            if min_val <= 0 or max_val <= 0:
                return None

            start_exp = int(np.floor(np.log10(min_val)))

            end_exp = int(np.ceil(np.log10(max_val)))

            major_ticks = []

            for exp in range(start_exp, end_exp + 1):
                base = 10**exp

                # Keep columns 1-5, ignore 6-9

                multipliers = [1, 2, 3, 4, 5]

                for m in multipliers:
                    val = m * base

                    # 20% safety margin for display

                    if val >= min_val * 0.8 and val <= max_val * 1.2:
                        pos_log = np.log10(val)

                        label = f"{val:.10g}"

                        major_ticks.append((pos_log, label))

            return [major_ticks, []]

        # Calculate boundaries

        min_x, max_x = (np.min(rmses), np.max(rmses)) if len(rmses) > 0 else (0.001, 1.0)

        min_y, max_y = (np.min(sigmas), np.max(sigmas)) if len(sigmas) > 0 else (0.01, 10.0)

        # Y-Axis (Left)

        ay = plot.getAxis("left")

        ay.setTickFont(font_axis)

        ay.setWidth(40)

        ay.setGrid(150)

        custom_ticks_y = generate_custom_log_ticks(min_y, max_y)

        if custom_ticks_y:
            ay.setTicks(custom_ticks_y)

        # X-Axis (Bottom)

        ax = plot.getAxis("bottom")

        ax.setTickFont(font_axis)

        ax.setHeight(30)

        custom_ticks_x = generate_custom_log_ticks(min_x, max_x)

        if custom_ticks_x:
            ax.setTicks(custom_ticks_x)

        plot.showGrid(x=True, y=True, alpha=0.4)

        # Data: use averages per sigma for consistency with the fit

        sigma_averages = []

        sigma_values = []

        for sigma in np.unique(sigmas):
            mask = sigmas == sigma

            sigma_averages.append(np.mean(rmses[mask]))

            sigma_values.append(sigma)

        plot.plot(
            sigma_averages,
            sigma_values,
            symbol="o",
            symbolSize=5,
            pen=None,
            symbolBrush=CertusTheme.CHART_PRIMARY,
            name="Simulations",
        )

        # Trend curve

        if len(rmses) > 0:
            x_min = float(np.min(rmses))

            x_max = float(np.max(rmses))

            if np.isfinite(x_min) and np.isfinite(x_max) and x_min > 0.0 and x_max > x_min:
                x_fit = np.logspace(np.log10(x_min), np.log10(x_max), 100)

                y_fit = fit_k * (x_fit**fit_alpha)

                y_fit = np.asarray(y_fit, dtype=np.float64)

                fit_mask = np.isfinite(x_fit) & np.isfinite(y_fit) & (y_fit > 0.0)

                if np.any(fit_mask):
                    plot.plot(
                        x_fit[fit_mask],
                        y_fit[fit_mask],
                        pen=pg.mkPen(CertusTheme.CHART_SECONDARY, style=Qt.PenStyle.DotLine, width=2),
                    )

            txt = pg.TextItem(
                f"sigma = {fit_k:.4g}·RMSE^{fit_alpha:.2f}",
                color=CertusTheme.CHART_SECONDARY,
                anchor=(0, 1),
            )

            font_eq = CertusTheme.get_font(9, QFont.Weight.Bold)

            txt.setFont(font_eq)

            txt_x = float(np.min(rmses))

            txt_y = float(np.max(sigmas))

            if np.isfinite(txt_x) and np.isfinite(txt_y) and txt_x > 0.0 and txt_y > 0.0:
                # In log mode, place text using positive data-space coordinates.

                txt.setPos(txt_x, txt_y)

                plot.addItem(txt)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_strategies_plot(self, data) -> None:

        self.setWindowTitle("Optimization Landscape & Strategies")

        strategies = data.get("strategies", [])

        heatmap_data = data.get("heatmap_data")

        win = InteractiveHeatmapWindow(self, heatmap_data if heatmap_data else {})

        plot = win.plot_widget

        colors = CertusTheme.CHART_COLORS

        if strategies:
            best_overall = min(strategies, key=lambda x: x["robustness_score"])

            for idx, res in enumerate(strategies):
                strat = res["strategy"]

                blocks = sorted(strat["blocks"], key=lambda b: b["start"])

                x_vals = []

                y_vals = []

                points_x = []

                points_y = []

                for block in blocks:
                    wl = float(block["wavelength"])

                    start = block["start"]

                    end = block["end"]

                    points_x.extend([start, end])

                    points_y.extend([wl, wl])

                    x_vals.append((start + end) / 2.0)

                    y_vals.append(wl)

                is_winner = res == best_overall

                width = 4 if is_winner else 2

                col = colors[idx % len(colors)]

                pen = pg.mkPen(color=QColor(col), width=width)

                if not is_winner:
                    pen.setStyle(Qt.PenStyle.DashLine)

                plot.plot(points_x, points_y, pen=pen, name=f"Strat {strat['strategy_id']}")

                scatter = pg.ScatterPlotItem(x=x_vals, y=y_vals, size=8, brush=pg.mkBrush(col), pen=pg.mkPen("k"))

                plot.addItem(scatter)

        self.central_widget = win

        self.setCentralWidget(win)

    def _init_robustness_plot(self, data) -> None:

        self.setWindowTitle("Robustness Analysis (Step 3)")

        nominal = data.get("nominal", {})

        best_noise = data.get("best_noise", {})

        wl = nominal.get("wavelengths", [])

        T_nom = nominal.get("T_spectral_nominal", [])

        plot = CertusScientificPlot(self, "Monte Carlo Distribution", "Transmission", "Wavelength (nm)")

        T_all_list = best_noise.get("T_spectral_all", [])
        if T_all_list and len(wl) > 0:
            T_all = np.array(T_all_list)
            # Plot a few individual sample lines in light grey
            num_samples_to_plot = min(10, len(T_all))
            sample_indices = np.linspace(0, len(T_all) - 1, num_samples_to_plot, dtype=int)
            for s_idx in sample_indices:
                plot.plot(
                    wl,
                    T_all[s_idx],
                    pen=pg.mkPen((200, 200, 200, 80), width=1),
                )
            
            # Plot the 5%-95% envelope
            p5 = np.percentile(T_all, 5, axis=0)
            p95 = np.percentile(T_all, 95, axis=0)
            
            c_upper = pg.PlotCurveItem(x=wl, y=p95, pen=None)
            c_lower = pg.PlotCurveItem(x=wl, y=p5, pen=None)
            fill = pg.FillBetweenItem(c_upper, c_lower, brush=pg.mkBrush(14, 165, 233, 70))
            
            plot.addItem(c_upper)
            plot.addItem(c_lower)
            plot.addItem(fill)

        if len(wl) > 0:
            nom_c = plot.plot(
                wl,
                T_nom,
                pen=pg.mkPen(CertusTheme.CHART_DANGER, width=3),
                name="Nominal Target",
            )

            plot.add_curve_for_tracking(nom_c, "Nominal")

            plot.setXRange(wl[0], wl[-1])

            plot.setYRange(0, 1.05)

        rmse = best_noise.get("rmse_p95", best_noise.get("rmse_mean", 0.0))

        noise = best_noise.get("noise_level", 0.0)

        info = pg.TextItem(
            f"Noise: {noise}%\nRMSE P95: {rmse:.5f}",
            color=CertusTheme.CHART_PRIMARY,
            anchor=(0, 0),
        )

        if len(wl) > 0:
            info.setPos(wl[0], 1.0)

        plot.addItem(info)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_heatmap(self, data) -> None:

        win = InteractiveHeatmapWindow(self, data)

        self.central_widget = win

        self.setCentralWidget(win)

