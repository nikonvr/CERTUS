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
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    arange_inclusive,
    calculate_detailed_growth,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    calculate_extrema_distances,
    compute_batch_rmse,
    compute_T_front_at_layer,
    find_nucleation_adaptive_kernel,
    get_refractive_index,
    get_refractive_clues_vectorized,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    update_run_states_kernel,
    validate_wavelengths_batch,
    validate_backside_real_clues,
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
)


class CertusWindowSpyMixin:
    def showEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.showEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.hideEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.closeEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        super().closeEvent(event)

    def moveEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.moveEvent() title='%s' id=%s old_pos=%s new_pos=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.oldPos(), event.pos()
        )
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.resizeEvent() title='%s' id=%s old_size=%s new_size=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.oldSize(), event.size()
        )
        super().resizeEvent(event)

    def changeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.changeEvent() title='%s' id=%s event_type=%s state=%s active=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.type(), self.windowState(), self.isActiveWindow()
        )
        super().changeEvent(event)

    def focusInEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.focusInEvent() title='%s' id=%s reason=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.reason()
        )
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.focusOutEvent() title='%s' id=%s reason=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.reason()
        )
        super().focusOutEvent(event)

class StrategiesTableWindow(CertusWindowSpyMixin, QMainWindow):
    strategy_selected = pyqtSignal(int, object)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategiesTableWindow.closeEvent() title='%s' id=%s geometry=%s visible=%s selected_row=%s rows=%s",
            self.windowTitle(), id(self), self.geometry(), self.isVisible(),
            getattr(self, "selected_row", -1),
            self.table.rowCount() if hasattr(self, "table") else "n/a",
        )
        super().closeEvent(event)

    def __init__(
        self,
        parent,
        strategies_results: list[dict[str, Any]],
        p_thick_nominal: list[float],
        include_secondary_rmse_stats: bool = False,
    ) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategiesTableWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.p_thick_nominal = np.array(p_thick_nominal, dtype=np.float64)

        self.strategies_results = strategies_results

        self.include_secondary_rmse_stats = bool(include_secondary_rmse_stats)

        self._details_dialogs: list[Any] = []

        self.selected_row = -1

        self.setWindowTitle("Dual-Objective Strategies Comparison (+ SEEL Colors)")

        screen = QApplication.primaryScreen().availableGeometry()

        w_win = min(1800, int(screen.width() * 0.95))

        h_win = min(800, int(screen.height() * 0.85))

        self.resize(w_win, h_win)

        self.move((screen.width() - w_win) // 2, (screen.height() - h_win) // 2)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        logo_container = QWidget()

        logo_layout = QHBoxLayout(logo_container)

        logo_layout.setContentsMargins(5, 5, 0, 0)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            logo_layout.addWidget(mini_logo)

        else:
            lbl_fallback = QLabel("CERTUS")

            lbl_fallback.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 14px;")

            logo_layout.addWidget(lbl_fallback)

        logo_layout.addStretch()

        layout.addWidget(logo_container)

        title_label = QLabel("All Strategies Robustness Test - Detailed Breakdown")

        title_label.setStyleSheet(
            f"font-size: 17px; font-weight: 800; padding: 10px 10px 6px 10px; color: {CertusTheme.TEXT_MAIN};"
        )

        layout.addWidget(title_label)

        self.origin_summary_label = QLabel("Origins: -")

        self.origin_summary_label.setStyleSheet(
            f"font-size: 12px; color: {CertusTheme.TEXT_SUB}; padding: 2px 10px 8px 10px;"
        )

        layout.addWidget(self.origin_summary_label)

        self.table = ExcelTableWidget()

        self.table.cellClicked.connect(self.on_cell_clicked)

        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.update_data(strategies_results)

        layout.addWidget(self.table)

        button_layout = QHBoxLayout()

        save_strat_btn = create_styled_button("Save Selected Strategy (JSON)", variant="success")

        save_strat_btn.setToolTip(
            "Save the currently selected strategy row as a JSON file.\n"
            "Click a row first to select it, then click this button."
        )

        save_strat_btn.clicked.connect(self.save_current_strategy)

        button_layout.addWidget(save_strat_btn)

        export_btn = create_styled_button("Export to CSV", variant="secondary")

        export_btn.setToolTip("Export the full strategies table to a CSV file (all rows and columns).")

        export_btn.clicked.connect(self.handle_export_csv)

        close_btn = create_styled_button("Close", variant="secondary")

        close_btn.setToolTip("Close this strategies comparison window.")

        close_btn.clicked.connect(self.close)

        button_layout.addWidget(export_btn)

        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _calculate_worst_layers(self, strategy_result, top_k=10) -> Any:

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            if not results_per_noise:
                return ["No Res"] * top_k

            target_res = results_per_noise[0]

            for r in results_per_noise:
                if abs(r.get("noise_level", 0) - 1.0) < 0.1:
                    target_res = r

                    break

            thicknesses_all = target_res.get("thicknesses_all", [])

            if not thicknesses_all:
                return ["No Data"] * top_k

            min_len = min(len(row) for row in thicknesses_all)

            if min_len == 0:
                return ["Empty"] * top_k

            clean_data = [row[:min_len] for row in thicknesses_all]

            sim_matrix = np.array(clean_data, dtype=np.float64)

            nom_arr = self.p_thick_nominal

            if nom_arr is None or len(nom_arr) == 0:
                return [f"Ref:0 vs Sim:{min_len}"] + ["-"] * (top_k - 1)

            common_layers = min(sim_matrix.shape[1], len(nom_arr))

            if common_layers == 0:
                return ["0 Layers"] * top_k

            sim_matrix_sliced = sim_matrix[:, :common_layers]

            nom_arr_sliced = nom_arr[:common_layers]

            abs_errors = np.abs(sim_matrix_sliced - nom_arr_sliced)

            p95_errors = np.percentile(abs_errors, 95, axis=0)

            layer_stats = []

            for i, err in enumerate(p95_errors):
                layer_stats.append((i + 1, err))

            layer_stats.sort(key=lambda x: x[1], reverse=True)

            output = []

            for i in range(top_k):
                if i < len(layer_stats):
                    l_idx, err_val = layer_stats[i]

                    output.append(f"L{l_idx} {err_val:.2f}nm")

                else:
                    output.append("")

            return output

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            return [str(e)[:15]] * top_k

    def _populate_table_row(
        self, row: int, result: dict[str, Any], strat: dict[str, Any], max_blocks: int, _rmse_to_seel: Any
    ) -> None:
        """Helper method to populate a single row in the strategies table."""
        # 0: Rank
        rank_item = NumericTableWidgetItem(str(row + 1))
        rank_item.setData(Qt.ItemDataRole.UserRole, result)
        rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if row == 0:
            rank_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 0, rank_item)

        # 1: ID
        id_item = NumericTableWidgetItem(str(strat["strategy_id"]))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, id_item)

        # 2: Origin
        origin = strat.get("origin", "unknown").upper()
        display_text = origin.split("(")[0].strip()
        origin_item = QTableWidgetItem(display_text)
        origin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if any(x in origin for x in ["SMART", "DEEP", "MERGE", "HYBRID"]):
            origin_item.setBackground(QColor(CertusTheme.INFO_BG))
            origin_item.setForeground(QColor(CertusTheme.INFO_TEXT))
            origin_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
            origin_item.setToolTip(f"✨ {origin}")
        else:
            origin_item.setForeground(QColor(80, 80, 80))
            origin_item.setToolTip(origin)
        self.table.setItem(row, 2, origin_item)

        # 3: Min Res
        min_res = result.get("min_resolution", 999.0)
        res_val_str = f"{min_res:.2f}" if min_res < 100 else ">100"
        res_item = NumericTableWidgetItem(res_val_str)
        res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if min_res < 0.5:
            res_item.setBackground(QColor(CertusTheme.DANGER_BG))
        elif min_res < 1.5:
            res_item.setBackground(QColor(CertusTheme.WARNING_BG))
        else:
            res_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        limiting = result.get("limiting_layer", "?")
        res_item.setToolTip(f"Limiting Factor: Layer #{limiting}")
        self.table.setItem(row, 3, res_item)

        # 4 & 5: Ranks
        th_rank = strat.get("thickness_rank", None)
        self.table.setItem(row, 4, NumericTableWidgetItem(str(th_rank) if th_rank is not None else "N/A (non calcule)"))
        sp_rank = strat.get("spectral_rank", None)
        self.table.setItem(row, 5, NumericTableWidgetItem(str(sp_rank) if sp_rank is not None else "N/A (non calcule)"))

        # 6 & 7: Blocks / Changes
        self.table.setItem(row, 6, NumericTableWidgetItem(str(strat["n_blocks"])))
        actual_changes = strat["n_blocks"] - 1
        violated = strat.get("constraint_violated", False)
        changes_item = NumericTableWidgetItem(str(actual_changes))
        if violated:
            changes_item.setText(f"{actual_changes} (⚠️)")
            changes_item.setBackground(QColor(CertusTheme.DANGER_BG))
        self.table.setItem(row, 7, changes_item)

        # 8: Unique Lambda
        self.table.setItem(row, 8, NumericTableWidgetItem(str(result["num_unique_wavelengths"])))

        # 9: Robust Score
        score_item = NumericTableWidgetItem(f"{result['robustness_score']:.6f}")
        if row == 0:
            score_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 9, score_item)

        # 10: Symmetry Score [0..100]
        sym_score = strat.get("symmetry_score_pct", result.get("symmetry_score_pct", None))
        if sym_score is None:
            sym_score = _compute_strategy_symmetry_score_percent(
                strat.get("theoretical_layer_profile", []), SYM_DEFAULT_EXTREMA_WINDOW_OT
            )
        try:
            sym_score_f = float(sym_score)
        except (TypeError, ValueError):
            sym_score_f = 0.0
        sym_score_f = max(0.0, min(100.0, sym_score_f))
        sym_item = NumericTableWidgetItem(f"{sym_score_f:.1f}")
        sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        sym_item.setToolTip("Layer-by-layer symmetry score (0-100). 100 = perfect symmetry across the entire stack.")
        if sym_score_f >= 80.0:
            sym_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
            sym_item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
            sym_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
        elif sym_score_f >= 50.0:
            sym_item.setBackground(QColor(CertusTheme.WARNING_BG))
            sym_item.setForeground(QColor(CertusTheme.WARNING_TEXT))
        else:
            sym_item.setBackground(QColor(CertusTheme.DANGER_BG))
            sym_item.setForeground(QColor(CertusTheme.DANGER_TEXT))
        self.table.setItem(row, 10, sym_item)

        # 11: Comp. Factor
        comp_factor_str = "-"
        noise_results = result.get("results_per_noise", [])
        res_1x = next((r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1), None)
        if res_1x:
            try:
                th_data = res_1x.get("thicknesses_all", [])
                if th_data and self.p_thick_nominal is not None:
                    mat_sim = np.array(th_data)
                    limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))
                    diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])
                    avg_phys_err = np.mean(diffs)
                    rmse_val = res_1x.get("rmse_p95", res_1x.get("rmse_mean", 0.0))
                    seel_val = _rmse_to_seel(rmse_val)
                    if seel_val and seel_val > 1e-9:
                        ratio = avg_phys_err / seel_val
                        comp_factor_str = f"{ratio:.2f}"
            except (ValueError, TypeError, ZeroDivisionError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        comp_item = NumericTableWidgetItem(comp_factor_str)
        comp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        comp_item.setToolTip("Compensation Factor = Avg Phys Error / SEEL @ 1.0x Noise")
        if comp_factor_str != "-":
            val = float(comp_factor_str)
            if val > 1.5:
                comp_item.setForeground(QColor(CertusTheme.SUCCESS))
                comp_item.setFont(CertusTheme.get_font(weight=QFont.Weight.Bold))
            elif val < 0.8:
                comp_item.setForeground(QColor(CertusTheme.DANGER))
        self.table.setItem(row, 11, comp_item)

        # 12: Median extrema count per layer (theoretical)
        ext_counts = []
        for p in strat.get("theoretical_layer_profile", []):
            try:
                ext_counts.append(int(p.get("extrema_count", 0)))
            except (TypeError, ValueError):
                continue
        if ext_counts:
            ext_p50 = float(np.percentile(np.array(ext_counts, dtype=np.float64), 50))
            ext_item = NumericTableWidgetItem(f"{ext_p50:.1f}")
        else:
            ext_item = NumericTableWidgetItem("N/A")
        ext_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_item.setToolTip("Number of extrema computed on the theoretical noiseless curve")
        self.table.setItem(row, 12, ext_item)

        # 13, 14, 15: SEEL Columns
        for col_idx, noise_idx in enumerate([0, 1, 2]):
            target_col = 13 + col_idx
            if noise_idx < len(noise_results):
                rmse_val = noise_results[noise_idx].get("rmse_p95", noise_results[noise_idx]["rmse_mean"])
                seel_val = _rmse_to_seel(rmse_val)
                if seel_val is not None:
                    item_txt = f"{seel_val:.3f} nm"
                    item = NumericTableWidgetItem(item_txt)
                    item.setToolTip(f"Raw RMSE P95: {rmse_val:.6f}")
                    if seel_val < 0.3:
                        item.setBackground(QColor(CertusTheme.SUCCESS_BG))
                        item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif seel_val < 1.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    elif seel_val < 2.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    else:
                        item.setBackground(QColor(CertusTheme.DANGER_BG))
                        item.setForeground(QColor(CertusTheme.DANGER_TEXT))
                    self.table.setItem(row, target_col, item)
                else:
                    self.table.setItem(row, target_col, NumericTableWidgetItem(f"R:{rmse_val:.5f}"))
            else:
                self.table.setItem(row, target_col, QTableWidgetItem("N/A"))

        # Blocks
        start_col_blocks = 16
        blocks = strat.get("blocks", [])
        for b_idx in range(max_blocks):
            col_idx = start_col_blocks + b_idx
            if b_idx < len(blocks):
                block = blocks[b_idx]
                wl = block["wavelength"]
                l_start = block["start"] + 1
                l_end = block["end"]
                text_desc = f"{wl:.0f}nm (L{l_start}->L{l_end})"
                block_item = QTableWidgetItem(text_desc)
                block_item.setToolTip(f"Block #{b_idx + 1}\nWavelength: {wl}nm\nLayers: {l_start} to {l_end}")
                self.table.setItem(row, col_idx, block_item)
            else:
                self.table.setItem(row, col_idx, QTableWidgetItem(""))

        # Worst Layers
        start_col_errors = start_col_blocks + max_blocks
        worst_layers = self._calculate_worst_layers(result, top_k=10)
        for err_idx, text_val in enumerate(worst_layers):
            item = QTableWidgetItem(text_val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if "nm" in text_val:
                try:
                    val_part = text_val.split()[1].replace("nm", "")
                    val = float(val_part)
                    if val > 2.0:
                        item.setForeground(QColor(CertusTheme.DANGER))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif val > 1.0:
                        item.setForeground(QColor(CertusTheme.WARNING))
                except (ValueError, IndexError, AttributeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
            self.table.setItem(row, start_col_errors + err_idx, item)

    def update_data(self, strategies_results: list[dict[str, Any]]) -> float | None:
        """

        Update the strategies table with new results.

        This method updates the display table with optimization results including:

        - Strategy performance metrics

        - Layer thickness information

        - Error statistics and rankings

        - Table refresh and sorting

        Args:

            self: StrategiesTable instance

            strategies_results: List of strategy result dictionaries with performance data

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling for data processing

            - Updates table UI components

            - Handles large datasets efficiently

        """

        self.strategies_results = strategies_results

        self.table.setUpdatesEnabled(False)

        self.table.setSortingEnabled(False)

        # Internal helper for SEEL

        seel_data = APP_CONTEXT.get("seel_data")

        def _rmse_to_seel(rmse_val) -> float | None:

            if seel_data and "fit_alpha" in seel_data and "fit_k" in seel_data:
                alpha = seel_data["fit_alpha"]

                k = seel_data["fit_k"]

                return float(k * (rmse_val**alpha))

            if seel_data and "avg_rmse" in seel_data:
                seel_x = np.array(seel_data["avg_rmse"])

                seel_y = np.array(seel_data["sigmas"])

                idx = np.argsort(seel_x)

                return float(np.interp(rmse_val, seel_x[idx], seel_y[idx]))

            return None

        try:
            self.table.clearContents()

            self.table.setRowCount(len(strategies_results))

            origin_counts: dict[str, int] = {}

            for res in strategies_results:
                origin_raw = str(res.get("strategy", {}).get("origin", "UNKNOWN")).upper()

                origin_key = origin_raw.split("(")[0].strip() if origin_raw else "UNKNOWN"

                origin_counts[origin_key] = origin_counts.get(origin_key, 0) + 1

            if origin_counts:
                items = sorted(origin_counts.items(), key=lambda kv: (-kv[1], kv[0]))

                summary = " | ".join([f"{k}: {v}" for k, v in items])

                self.origin_summary_label.setText(f"Origins ({len(strategies_results)}): {summary}")

            else:
                self.origin_summary_label.setText("Origins: -")

            max_blocks = 0

            has_th_rank = False

            has_sp_rank = False

            for res in strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

                strat_local = res.get("strategy", {})

                if strat_local.get("thickness_rank", None) is not None:
                    has_th_rank = True

                if strat_local.get("spectral_rank", None) is not None:
                    has_sp_rank = True

            # --- HEADER DEFINITION (Modified) ---

            # Metric updated: Complexity out, Comp.Factor in

            base_headers = [
                "Rank",
                "ID",
                "Origin",
                "Min Res (nm)",
                "Th Rank",
                "Sp Rank",
                "Blocks",
                "Changes",
                "Unique lambda",
                "Robust Score",
                "Sym Score",
                "Comp. Factor",
                "Next",
            ]

            noise_headers = ["SEEL (0.5x)", "SEEL (1.0x)", "SEEL (2.0x)"]

            block_headers = [f"Block {i + 1}" for i in range(max_blocks)]

            error_headers = [f"Worst #{i + 1} (P95)" for i in range(10)]

            all_headers = base_headers + noise_headers + block_headers + error_headers

            self.table.setColumnCount(len(all_headers))

            self.table.setHorizontalHeaderLabels(all_headers)

            # --- HEADER TOOLTIPS ---

            _header_tips = {
                "Rank": "Global robustness ranking (1 = best). Sorted by Robust Score.",
                "ID": "Internal strategy identifier assigned during the Dynamic Programming search.",
                "Origin": "Algorithm that generated this strategy: DP (Dynamic Programming), "
                "SMART (elite candidate), HYBRID, MERGE, DEEP, etc.",
                "Min Res (nm)": "Minimum optical thickness resolution across all layers and blocks "
                "(nm). Low values = harder to hit the turning point precisely. "
                "<1.5 nm -> warning, <0.5 nm -> critical.",
                "Th Rank": "Thickness-based DP rank: strategies with smaller total thickness "
                "cost get a lower rank (hidden if not computed).",
                "Sp Rank": "Spectral-sensitivity DP rank: strategies with more stable spectral "
                "response near turning points get a lower rank (hidden if not computed).",
                "Blocks": "Number of monochromatic monitoring blocks. Each block = one "
                "monitoring wavelength covering one or more consecutive layers.",
                "Changes": "Number of wavelength changes (= Blocks - 1). ⚠️ if the maximum "
                "allowed changes constraint is violated.",
                "Unique lambda": "Number of distinct monitoring wavelengths used across all blocks.",
                "Robust Score": "Monte Carlo robustness score: mean RMSE of the final stack over "
                "many simulated depositions with Gaussian thickness noise. "
                "Lower = more robust. Primary sort key.",
                "Sym Score": "SYM (Symmetry) score: rewards strategies whose layer turning points "
                "are positioned far from optical extrema (local T maxima/minima), "
                "reducing sensitivity to deposition errors.",
                "Comp. Factor": "Complexity factor: composite metric balancing the number of blocks, "
                "wavelength changes, and optical sensitivity.",
                "Next": "Button to inspect this strategy in detail (spectral performance, "
                "layer-by-layer profile, extrema proximity).",
            }

            # SEEL columns

            for i, lbl in enumerate(noise_headers):
                level = ["0.5×", "1.0×", "2.0×"][i]

                _header_tips[lbl] = (
                    f"SEEL estimate at noise level {level}: equivalent production yield (%) "
                    f"predicted from the robustness RMSE via the SEEL calibration curve. "
                    f"Higher = better yield."
                )

            # Block columns

            for i in range(max_blocks):
                _header_tips[f"Block {i + 1}"] = (
                    f"Monitoring wavelength (nm) for block {i + 1}, covering the layer range "
                    f"[start … end]. Click the row to see the full block definition."
                )

            # Worst-layer columns

            for i in range(10):
                _header_tips[f"Worst #{i + 1} (P95)"] = (
                    f"Layer with the #{i + 1} highest thickness error at the 95th percentile "
                    f"across Monte Carlo simulations (noise level 1.0×). "
                    f"Format: L<index> <P95 error in nm>."
                )

            for col, label in enumerate(all_headers):
                tip = _header_tips.get(label)

                if tip:
                    item = self.table.horizontalHeaderItem(col)

                    if item:
                        item.setToolTip(tip)

            # --- END HEADER TOOLTIPS ---

            # Auto-hide row columns if no value is calculated.

            self.table.setColumnHidden(4, not has_th_rank)

            self.table.setColumnHidden(5, not has_sp_rank)

            for row, result in enumerate(strategies_results):
                strat = result["strategy"]
                self._populate_table_row(row, result, strat, max_blocks, _rmse_to_seel)

            # PERFORMANCE — single call replaces per-column loop
            # BUG HISTORY: earlier versions called
            #   for c in range(self.table.columnCount()):
            #       self.table.resizeColumnToContents(c)
            # on a table with 30-50+ columns.  Each call forces a full
            # layout pass, freezing the UI for ~1 s on large datasets.
            # RULE: always use the single ``resizeColumnsToContents()`` call;
            # it performs one layout pass for all columns at once.
            # DO NOT revert to the per-column loop.
            self.table.resizeColumnsToContents()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.getLogger("ThinFilm").error(f"Table update error: {e}")

            logging.getLogger("ThinFilm").error(traceback.format_exc())

        finally:
            self.table.setSortingEnabled(True)

            self.table.setUpdatesEnabled(True)

    def on_cell_clicked(self, row: int, col: int) -> Any:

        self.table.clearSelection()

        rank_item = self.table.item(row, 0)

        if not rank_item:
            return

        strategy_result = rank_item.data(Qt.ItemDataRole.UserRole)

        if not strategy_result and 0 <= row < len(self.strategies_results):
            # Fallback when Qt item user-data is unexpectedly missing after sorting/refresh.

            strategy_result = self.strategies_results[row]

        if not strategy_result:
            # Last fallback by strategy ID lookup from table column 1.

            id_item = self.table.item(row, 1)

            sid = str(id_item.text()).strip() if id_item else ""

            if sid:
                for res in self.strategies_results:
                    if str(res.get("strategy", {}).get("strategy_id", "")).strip() == sid:
                        strategy_result = res

                        break

        if strategy_result:
            self.strategy_selected.emit(row, strategy_result)

            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)

                if item:
                    item.setSelected(True)

            # --- POPUP EXTRA: THEORETICAL PROFILE BY LAYER ---

            strat = strategy_result.get("strategy", {})

            extrema_distances = strat.get("extrema_distances", [])

            theo_profile = strat.get("theoretical_layer_profile", [])

            if extrema_distances or theo_profile:
                msg = "Theoretical no-noise per-layer profile\n"

                msg += "Fields: Tinit, Textrema[], Tfinal, and distances to extrema (nm)\n\n"

                n_layers = max(len(extrema_distances), len(theo_profile))

                for i_layer in range(n_layers):
                    dists = extrema_distances[i_layer] if i_layer < len(extrema_distances) else {}

                    prof = theo_profile[i_layer] if i_layer < len(theo_profile) else {}

                    msg += f"--- Layer {i_layer + 1} ---\n"

                    # Distances to generic 15nm limit rule

                    def fmt_dist(v, sign="") -> Any:

                        return f"{sign}{v:.1f}nm (OT)" if v <= 15.0 else "not critical"

                    # Start (d=0)

                    msg += f"  Start (d=0): Prev Extrema @ {fmt_dist(dists.get('prev_start', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_start', 999), '+')}\n"

                    # End (d=d_nom)

                    msg += f"  End (d=nom): Prev Extrema @ {fmt_dist(dists.get('prev_end', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_end', 999), '+')}\n"

                    try:
                        t_init = prof.get("Tinit", None)

                        t_final = prof.get("Tfinal", None)

                        if t_init is not None:
                            msg += f"  Tinit:  {float(t_init) * 100:.3f}%\n"

                        if t_final is not None:
                            msg += f"  Tfinal: {float(t_final) * 100:.3f}%\n"

                        near_type = str(prof.get("nearest_end_type", "between"))

                        near_dist = float(prof.get("nearest_end_dist_nm", np.nan))

                        tf_class = str(prof.get("tfinal_class", "between"))

                        if np.isfinite(near_dist):
                            msg += f"  Tfinal class: {tf_class} (nearest {near_type}, d={near_dist:.2f}nm)\n"

                    except (TypeError, ValueError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    extrema_list = prof.get("Textrema", [])

                    if extrema_list:
                        msg += "  Textrema:\n"

                        max_show = 12

                        for e_idx, e in enumerate(extrema_list[:max_show], 1):
                            e_type = str(e.get("type", "?"))

                            e_d = float(e.get("d_nm", np.nan))

                            e_t = float(e.get("T", np.nan))

                            msg += f"    {e_idx:02d}. {e_type} @ d={e_d:.2f}nm -> T={e_t * 100:.3f}%\n"

                        if len(extrema_list) > max_show:
                            msg += f"    ... {len(extrema_list) - max_show} more extrema\n"

                    else:
                        msg += "  Textrema: none detected on [0, d_nom]\n"

                    msg += "\n"

                # We use a custom QDialog with QTextEdit for scrollable text if there are many layers

                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

                dlg = QDialog(self)

                dlg.setWindowTitle(f"Extrema Proximity - Strategy {strat.get('strategy_id', 'Unknown')}")

                dlg.resize(400, 500)

                dlg_layout = QVBoxLayout(dlg)

                txt_edit = QTextEdit()

                txt_edit.setReadOnly(True)

                txt_edit.setText(msg)

                # Use a monospaced font for better alignment

                font = txt_edit.font()

                font.setFamily("Consolas")

                txt_edit.setFont(font)

                dlg_layout.addWidget(txt_edit)

                btn = QPushButton("Close")

                btn.setToolTip("Close the proximity extrema dialog.")

                btn.clicked.connect(dlg.accept)

                dlg_layout.addWidget(btn)

                # Non-modal popup so strategy monitoring windows can open immediately.

                dlg.setModal(False)

                dlg.show()

                dlg.raise_()

                dlg.activateWindow()

                self._details_dialogs.append(dlg)

                def _remove_details_dialog(*_args, dialog=dlg) -> None:
                    if dialog in self._details_dialogs:
                        self._details_dialogs.remove(dialog)

                dlg.finished.connect(_remove_details_dialog)

    def save_current_strategy(self) -> None:

        current_row = self.table.currentRow()

        if current_row < 0:
            logging.getLogger("ThinFilm").warning("No strategy selected to save.")

            return

        rank_item = self.table.item(current_row, 0)

        if not rank_item:
            return

        result_obj = rank_item.data(Qt.ItemDataRole.UserRole)

        if not result_obj or "strategy" not in result_obj:
            return

        strategy_data = result_obj["strategy"]

        strat_id = strategy_data.get("strategy_id", "unknown")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Strategy #{strat_id}",
            str(Path(get_certus_last_dir() or ".") / f"strategy_{strat_id}.json"),
            "JSON Files (*.json)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(strategy_data, f, indent=4, default=numpy_encoder)

                logging.getLogger("ThinFilm").info(f"✓ Strategy #{strat_id} saved to {filename}")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error saving strategy: {e}")

    def handle_export_csv(self) -> None:

        max_blocks = 0

        if self.strategies_results:
            for res in self.strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

        self.export_csv(self.strategies_results, max_blocks)

    def export_csv(self, strategies_results, max_blocks) -> None:


        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Strategies Results",
            str(Path(get_certus_last_dir() or ".") / "strategies_stats.csv"),
            "CSV Files (*.csv)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                data = []

                for rank, result in enumerate(strategies_results, 1):
                    strat = result["strategy"]

                    noise_results = result.get("results_per_noise", [])

                    origin = strat.get("origin", "unknown")

                    # Calc Comp.Factor (matches update_data)

                    comp_factor = ""

                    res_1x = next(
                        (r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1),
                        None,
                    )

                    if res_1x and self.p_thick_nominal is not None:
                        try:
                            th_data = res_1x.get("thicknesses_all", [])

                            if th_data:
                                mat_sim = np.array(th_data)

                                limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))

                                diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])

                                avg_phys_err = np.mean(diffs)

                                seel_data = APP_CONTEXT.get("seel_data")

                                rmse_val = res_1x.get("rmse_p95", res_1x["rmse_mean"])

                                seel_val = None

                                if seel_data and "fit_alpha" in seel_data:
                                    seel_val = seel_data["fit_k"] * (rmse_val ** seel_data["fit_alpha"])

                                if seel_val and seel_val > 1e-9:
                                    comp_factor = f"{avg_phys_err / seel_val:.4f}"

                        except (KeyError, TypeError, ZeroDivisionError):
                            # Skip if calculation fails

                            pass

                    row = {
                        "Rank": rank,
                        "Strategy_ID": strat["strategy_id"],
                        "Origin": origin.upper(),
                        "Min_Resolution_nm": result.get("min_resolution", ""),
                        "Limiting_Layer": result.get("limiting_layer", ""),
                        "Thickness_Rank": strat.get("thickness_rank", ""),
                        "Spectral_Rank": strat.get("spectral_rank", ""),
                        "Blocks": strat["n_blocks"],
                        "Wavelength_Changes": strat["n_blocks"] - 1,
                        "Unique_Wavelengths": result.get("num_unique_wavelengths", 0),
                        # “Complexity” REMOVED
                        "Robustness_Score": f"{result['robustness_score']:.6f}",
                        "Symmetry_Score_0_100": f"{float(strat.get('symmetry_score_pct', result.get('symmetry_score_pct', 0.0))):.1f}",
                        "Compensation_Error_Factor": comp_factor,
                    }

                    for idx, noise_res in enumerate(noise_results):
                        row[f"Noise_{idx}_Level_%"] = noise_res["noise_level"]

                        row[f"Noise_{idx}_RMSE_P95"] = f"{noise_res.get('rmse_p95', noise_res['rmse_mean']):.6f}"

                        if self.include_secondary_rmse_stats:
                            row[f"Noise_{idx}_RMSE_Mean"] = f"{noise_res['rmse_mean']:.6f}"

                            row[f"Noise_{idx}_RMSE_Std"] = f"{noise_res['rmse_std']:.6f}"

                    blocks = strat.get("blocks", [])

                    for i in range(max_blocks):
                        key = f"Block_{i + 1}"

                        if i < len(blocks):
                            b = blocks[i]

                            row[key] = f"{b['wavelength']:.0f}nm (L{b['start'] + 1}->L{b['end']})"

                        else:
                            row[key] = ""

                    worst_layers = self._calculate_worst_layers(result, top_k=10)

                    for i, txt in enumerate(worst_layers):
                        row[f"Worst_Err_P95_{i + 1}"] = txt

                    data.append(row)

                # to_csv_robust: handles commas

                to_csv_robust(pd.DataFrame(data), filename, index=False)

                logging.getLogger("ThinFilm").info(f"✓ Strategies results exported to '{filename}'")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error exporting CSV: {e}")

# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# === GUI CLASSES (RECONSTITUTION STYLE VERSION D) ===

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

        act_copy.setToolTip("Ctrl+Shift+C - TSV pour Excel")

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

        # Axe Y (Gauche)

        ay = plot.getAxis("left")

        ay.setTickFont(font_axis)

        ay.setWidth(40)

        ay.setGrid(150)

        custom_ticks_y = generate_custom_log_ticks(min_y, max_y)

        if custom_ticks_y:
            ay.setTicks(custom_ticks_y)

        # Axe X (Bas)

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

        # Courbe de tendance

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

class InteractiveHeatmapWindow(QWidget):  # <--- Changement ici: QWidget au lieu de QMainWindow
    def __init__(self, parent, raw_data_thickness) -> Any:

        super().__init__(parent)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = CertusScientificPlot(self, "Design Heatmap", "Wavelength (nm)", "Layer Number")

        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Ajout du widget au layout

        attach_excel_clipboard_context_menu(self.plot_widget)

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        if not raw_data_thickness:
            return

        self.layers = sorted(raw_data_thickness.keys())

        self.num_layers = len(self.layers)

        all_wls = set()

        for res_list in raw_data_thickness.values():
            for item in res_list:
                all_wls.add(item["wl"])

        self.sorted_wls = sorted(list(all_wls))

        if not self.sorted_wls:
            return

        wl_map = {wl: i for i, wl in enumerate(self.sorted_wls)}

        max_layer_idx = max(self.layers) if self.layers else 0
        grid = np.full((max_layer_idx + 1, len(self.sorted_wls)), np.nan, dtype=np.float64)

        path_x, path_y = [], []

        for l_idx in self.layers:
            items = raw_data_thickness.get(l_idx, [])

            if items:
                for item in items:
                    w_idx = wl_map.get(item["wl"])

                    if w_idx is not None:
                        grid[l_idx, w_idx] = item["cost"]

                best = min(items, key=lambda x: x["cost"])

                path_x.append(l_idx + 0.5)

                path_y.append(best["wl"])

        max_val = 1.0
        if np.any(np.isfinite(grid)):
            max_val = float(np.nanmax(grid))
        grid_filled = np.nan_to_num(grid, nan=max_val)

        valid_mask = np.isfinite(grid) & (grid > 0)

        if valid_mask.any():
            log_vals = np.log10(grid[valid_mask])

            vmin, vmax = np.percentile(log_vals, 2), np.percentile(log_vals, 98)

            denom = vmax - vmin if vmax != vmin else 1.0

            grid_norm = np.clip((np.log10(grid_filled) - vmin) / denom, 0, 1)

        else:
            grid_norm = np.zeros_like(grid)

        self.img_item = pg.ImageItem(grid_norm)

        # Palette de couleurs (Magma-ish)

        pos = np.linspace(0, 1, 5)

        color = np.array(
            [
                [15, 23, 42, 255],
                [60, 20, 80, 255],
                [180, 40, 80, 255],
                [250, 140, 50, 255],
                [252, 250, 230, 255],
            ],
            dtype=np.ubyte,
        )

        cmap = pg.ColorMap(pos, color)

        self.img_item.setLookupTable(cmap.getLookupTable(0.0, 1.0, 256))

        y0 = self.sorted_wls[0]

        y_range = self.sorted_wls[-1] - y0

        y_scale = y_range / len(self.sorted_wls) if len(self.sorted_wls) > 0 else 1.0

        tr = QTransform()

        tr.translate(0, y0)

        tr.scale(1, y_scale)

        self.img_item.setTransform(tr)

        self.plot_widget.addItem(self.img_item)

        if path_x:
            # Step Plot Construction

            step_x, step_y = [], []

            step_x.append(path_x[0])

            step_y.append(path_y[0])

            for i in range(1, len(path_x)):
                step_x.append(path_x[i])

                step_y.append(path_y[i - 1])

                step_x.append(path_x[i])

                step_y.append(path_y[i])

            self.plot_widget.plot(step_x, step_y, pen=pg.mkPen("c", width=3), name="Optimal Strategy")

        self.plot_widget.setXRange(0, self.num_layers)

        self.plot_widget.setYRange(y0, self.sorted_wls[-1])

        def _heatmap_clipboard_df() -> Any:

            rows = []

            for lk in self.layers:
                for j, wl in enumerate(self.sorted_wls):
                    v = float(grid[lk, j])

                    if np.isfinite(v):
                        rows.append(
                            {
                                "layer_key": int(lk),
                                "wavelength_nm": float(wl),
                                "cost": v,
                            }
                        )

            if not rows:
                return None

            return pd.DataFrame(rows)

        self.plot_widget._certus_clipboard_df_provider = _heatmap_clipboard_df

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

            if "detailed_growth_data" not in strategy_result:
                from certus.core.certus_strat_core import _IdxWrapper

                num_layers = len(p_thick_nominal)

                p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)

                # [FIX 2026] Complex clues for coherent detailed growth (absorption in TMM)

                layer_wls = np.zeros(num_layers, dtype=np.float64)

                nH_arr = np.zeros(num_layers, dtype=np.complex128)

                nL_arr = np.zeros(num_layers, dtype=np.complex128)

                nSub_arr = np.zeros(num_layers, dtype=np.complex128)

                clues_db = _IdxWrapper(opti_results.get("clues_at_wl", {}))

                # [FIX 2026-03] Pass materials_db_instance to resolve dispersive materials

                # at monitoring wavelengths not in clues_db (e.g. 490nm when scan is 1200-1700nm)

                # SAFETY — three-level material database fallback
                # Same contract as StrategySpectralPerformanceWindow._calculate_and_plot.
                # See that class's docstring for full explanation.
                db_instance = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")

                # Compute a safe substrate fallback from the known IR wavelengths

                _nSub_fallback = complex(1.52)

                if opti_results.get("clues_at_wl"):
                    all_wls = opti_results.get("all_wls", [])
                    for w in all_wls:
                        first_idx = clues_db[w]
                        if first_idx and isinstance(first_idx, dict):
                            _nSub_fallback = complex(first_idx.get("substrate", 1.52))
                            break

                if _nSub_fallback.real < 1.001:
                    _nSub_fallback = complex(1.52)

                for block in blocks:
                    wl = float(block["wavelength"])

                    if wl not in clues_db:
                        n_h = get_refractive_index(params["nH_id"], wl, db_instance)

                        n_l = get_refractive_index(params["nL_id"], wl, db_instance)

                        n_sub = get_refractive_index(params["nSub_id"], wl, db_instance)

                        idx_data = {"H": n_h, "L": n_l, "substrate": n_sub}

                    else:
                        idx_data = clues_db[wl]

                    if not isinstance(idx_data, dict):
                        n_h = get_refractive_index(params["nH_id"], wl, db_instance)

                        n_l = get_refractive_index(params["nL_id"], wl, db_instance)

                        n_sub = get_refractive_index(params["nSub_id"], wl, db_instance)

                        idx_data = {"H": n_h, "L": n_l, "substrate": n_sub}

                    for layer_idx in range(block["start"], block["end"]):
                        if layer_idx < num_layers:
                            layer_wls[layer_idx] = wl

                            nH_arr[layer_idx] = idx_data.get("H", complex(2.3))

                            nL_arr[layer_idx] = idx_data.get("L", complex(1.45))

                            n_sub_val = complex(idx_data.get("substrate", _nSub_fallback))

                            # [FIX 2026-03] Guard: n_sub < 1.001 is physically impossible

                            # (vacuum/air) and causes T=1.0. Use fallback from IR data.

                            if n_sub_val.real < 1.001:
                                logging.warning(
                                    f"[Growth] n_sub={n_sub_val:.4f} at {wl}nm is unphysical "
                                    f"(should be >=1.4 for glass). "
                                    f"Substituting with IR-range value {_nSub_fallback:.4f}."
                                )

                                n_sub_val = _nSub_fallback

                            nSub_arr[layer_idx] = n_sub_val

                steps_per_layer = np.full(num_layers, 50, dtype=np.int32)

                x_pts, y_pts, bounds = calculate_detailed_growth(
                    num_layers,
                    p_thick_arr,
                    layer_wls,
                    nH_arr,
                    nL_arr,
                    nSub_arr,
                    steps_per_layer,
                )

                data = {"x": x_pts, "y": y_pts, "boundaries": bounds}

            else:
                data = strategy_result["detailed_growth_data"]

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
            results_list = strategy_result.get("results_per_noise", [])

            target_res = None

            for res in results_list:
                if abs(res.get("noise_level", 0) - 2.0) < 0.1:
                    target_res = res

                    break

            if not target_res and results_list:
                target_res = results_list[0]

            if not target_res:
                return

            thicknesses_all = target_res.get("thicknesses_all", [])

            p_thick_nominal = opti_results["p_thick_nominal"]

            wl_min = float(params["wl_range"][0])

            wl_max = float(params["wl_range"][1])

            wl_step = float(params["wl_step"])

            wls = arange_inclusive(wl_min, wl_max, wl_step)

            nH_id = params["nH_id"]

            nL_id = params["nL_id"]

            nSub_id = params["nSub_id"]

            # SAFETY — three-level material database fallback
            # ------------------------------------------------------------------
            # BUG HISTORY: When only params.get("materials_db_instance") was
            # used, db_instance was None in most runtime paths because the worker
            # serialises params before moving to a thread and the key is not always
            # present.  The result: get_refractive_clues_vectorized fell back to
            # a constant-index stub → perfectly flat T(λ) curves in this window.
            # RULE: Always resolve in this exact order:
            #   1. params["materials_db_instance"]  (set by some code paths)
            #   2. params["materials_db"]            (set by other code paths)
            #   3. APP_CONTEXT["materials_db"]       (global singleton, always set at startup)
            # DO NOT collapse to a single key without updating the worker that
            # populates params — both keys exist in different call sites.
            # ------------------------------------------------------------------
            db_instance = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
            # GUARD RAIL — Ensure materials database is loaded to prevent silent flat T(λ) curve generation.
            assert db_instance is not None, (
                "CERTUS-STRAT-E-DB-MISSING: Materials database instance is completely missing from params and APP_CONTEXT. "
                "Verify that the worker thread correctly serializes/deserializes the materials database or that "
                "APP_CONTEXT['materials_db'] is initialized on startup."
            )

            nH_arr = get_refractive_clues_vectorized(nH_id, wls, db_instance).astype(np.complex128)

            nL_arr = get_refractive_clues_vectorized(nL_id, wls, db_instance).astype(np.complex128)

            nSub_arr = get_refractive_clues_vectorized(nSub_id, wls, db_instance).astype(np.complex128)

            _, T_clean_batch = calculate_RT_batch_kernel(
                wls,
                nH_arr,
                nL_arr,
                nSub_arr,
                np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1),
            )

            T_nom = T_clean_batch[0]

            T_sim_list = []

            for p_sim in thicknesses_all:
                if len(p_sim) == len(p_thick_nominal):
                    p_arr = np.array(p_sim, dtype=np.float64).reshape(1, -1)

                    _, T_val_batch = calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, p_arr)

                    T_sim_list.append(T_val_batch[0])

            if not T_sim_list:
                return

            arr_sim = np.array(T_sim_list)

            mean = np.mean(arr_sim, axis=0)

            p5 = np.percentile(arr_sim, 5, axis=0)

            p95 = np.percentile(arr_sim, 95, axis=0)

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

class JsonViewerWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, title: str, data: Any) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] JsonViewerWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.setWindowTitle(f"Viewer: {title}")

        self.setGeometry(300, 300, 300, 750)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        header_widget = QWidget()

        header_widget.setStyleSheet(
            f"background-color: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};"
        )

        header_layout = QHBoxLayout(header_widget)

        header_layout.setContentsMargins(10, 5, 10, 5)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            header_layout.addWidget(mini_logo)

        else:
            lbl = QLabel("CERTUS")

            lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 16px;")

            header_layout.addWidget(lbl)

        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        self.text_edit = QTextEdit()

        self.text_edit.setReadOnly(True)

        self.text_edit.setStyleSheet(
            f""" QTextEdit {{ background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_MAIN}; font-family: {CertusTheme.FONT_FAMILY}; font-size: 10pt; border: none; padding: 10px; }} """
        )

        try:
            pretty_json = json.dumps(data, indent=4, ensure_ascii=False, default=numpy_encoder)

            self.text_edit.setText(pretty_json)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.text_edit.setText(f"Error parsing JSON data: {e}")

        main_layout.addWidget(self.text_edit)

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

class InteractiveSpectrumWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, data_dict, sigma=None) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] InteractiveSpectrumWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.T_nominal = np.array(data_dict["T_nominal"])

        self.T_simulations = data_dict.get("T_simulations", [])

        title = "Monte Carlo Analysis" + (f" (Input Noise sigma={sigma} nm)" if sigma else "")

        self.setWindowTitle(title)

        self.resize(600, 375)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 10, 15, 10)

        lbl = QLabel("<b>Monte Carlo Reliability Analysis</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(20)

        legend_widget = QWidget()

        legend_layout = QHBoxLayout(legend_widget)

        legend_layout.setContentsMargins(0, 0, 0, 0)

        legend_layout.setSpacing(15)

        def add_legend_item(color, text) -> None:

            lbl_color = QLabel()

            lbl_color.setFixedSize(12, 12)

            lbl_color.setStyleSheet(
                f"background-color: {color}; border-radius: 2px; border: 1px solid {CertusTheme.BORDER};"
            )

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            legend_layout.addWidget(lbl_color)

            legend_layout.addWidget(lbl_txt)

        add_legend_item(CertusTheme.CHART_DANGER, "Nominal Target")

        add_legend_item(CertusTheme.CHART_SECONDARY, "Mean Run")

        add_legend_item("rgba(14, 165, 233, 0.4)", "+/- 1sigma")

        h_layout.addWidget(legend_widget)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Transmission")

        self.plot_widget.addLegend = lambda *args, **kwargs: None



        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._plot_data()

    def _plot_data(self) -> None:

        if self.T_simulations and len(self.T_simulations) > 1:
            arr_sim = np.array(self.T_simulations)

            mean = np.mean(arr_sim, axis=0)

            std = np.std(arr_sim, axis=0)

            self._add_corridor(mean, std, 2.0, (14, 165, 233, 50))

            self._add_corridor(mean, std, 1.0, (14, 165, 233, 100))

            mean_curve = self.plot_widget.plot(
                self.wavelengths,
                mean,
                pen=pg.mkPen(color="#0ea5e9", width=2, style=Qt.PenStyle.DashLine),
            )

            mean_curve.setZValue(10)

        curve_nom = self.plot_widget.plot(self.wavelengths, self.T_nominal, pen=pg.mkPen(color="#d62728", width=3))

        curve_nom.setZValue(20)

        self.plot_widget.add_curve_for_tracking(curve_nom, "Nominal")

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(float(self.wavelengths[0]), float(self.wavelengths[-1]), 0)

            self.plot_widget.setYRange(-0.05, 1.05)

    def _add_corridor(self, mean, std, factor, color_tuple) -> None:

        upper = mean + factor * std

        lower = mean - factor * std

        c_up = pg.PlotCurveItem(x=self.wavelengths, y=upper, pen=None)

        c_down = pg.PlotCurveItem(x=self.wavelengths, y=lower, pen=None)

        self.plot_widget.addItem(c_up)

        self.plot_widget.addItem(c_down)

        fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(color_tuple))

        fill.setZValue(-10)

        self.plot_widget.addItem(fill)

class PopOutWindow(CertusWindowSpyMixin, QMainWindow):
    closed_signal = pyqtSignal()

    def closeEvent(self, event) -> None:
        self.closed_signal.emit()
        self.takeCentralWidget()
        super().closeEvent(event)

    def __init__(self, widget_to_host, parent=None, title="Detached Window") -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] PopOutWindow created id=%s parent=%s title='%s'",
            id(self), id(parent) if parent else None, title
        )

        set_certus_window_icon(self)

        self.setWindowTitle(title)

        self.setCentralWidget(widget_to_host)

        self.resize(600, 600)

        self.setStyleSheet(f"QMainWindow {{ background-color: {CertusTheme.SURFACE}; }} QWidget {{ font-size: 10pt; }}")

# QueueHandler and setup_gui_logger are imported from certus.ui.certus_ui

# === OPTIMIZATION: LiveMonitor with Convergence Plot ===

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

        # Layout principal simple (plus de Splitter)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        # -- Widget de croissance uniquement --

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

class WelcomeGuideWidget(QWidget):
    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"""
            QWidget {{ font-family: 'Segoe UI', sans-serif; }}

            QScrollArea, QWidget#ContentContainer {{ background: {CertusTheme.BACKGROUND}; border: none; }}

            QScrollBar:vertical {{ width: 10px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {CertusTheme.BORDER}; border-radius: 5px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            .step-card {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 16px;
            }}
            .step-number {{ font-size: 34px; font-weight: 900; opacity: 0.20; }}
            .step-title {{ color: {CertusTheme.TEXT_MAIN}; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }}
            .step-desc {{ color: {CertusTheme.TEXT_SUB}; font-size: 11px; line-height: 1.35; }}

            .mission-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 14px; }}
            .dash-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px; }}
            .dash-header {{ color: {CertusTheme.PRIMARY}; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid {CertusTheme.BORDER}; padding-bottom: 6px; margin-bottom: 8px; }}

        """)

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_container = QWidget()

        self.content_container.setObjectName("ContentContainer")

        main_layout = QVBoxLayout(self.content_container)

        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.content_container)

        outer_layout.addWidget(self.scroll_area)

        content_wrapper = QWidget()

        content_wrapper.setStyleSheet("background-color: transparent;")

        content_layout = QVBoxLayout(content_wrapper)

        content_layout.setContentsMargins(8, 14, 8, 10)

        content_layout.setSpacing(14)

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(10)

        cards_layout.addWidget(
            self._create_step_card(
                "01",
                "DESIGN",
                "Define optical stack,\nmaterials & target.",
                CertusTheme.SECONDARY,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "02",
                "OPTIMIZE",
                "Hybrid algorithm for\nstable monitoring.",
                CertusTheme.ACCENT,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "03",
                "VALIDATE",
                "Monte Carlo sims to\nensure robustness.",
                CertusTheme.SUCCESS,
            )
        )

        content_layout.addLayout(cards_layout)

        mission_frame = QFrame()

        mission_frame.setProperty("class", "mission-frame")

        mission_layout = QGridLayout(mission_frame)

        mission_layout.setContentsMargins(14, 14, 14, 14)

        points = [
            (
                "🎯",
                "<b>Precision Targeting:</b> Identify exact wavelengths to cancel errors.",
            ),
            ("🧬", "<b>Hybrid Intelligence:</b> DP engine finds global minimuum."),
            (
                "🛡️",
                "<b>Robustness First:</b> Validation via thousands of Monte Carlo sims.",
            ),
            (
                "⚡",
                "<b>Real-Time Physics:</b> JIT engine simulating layer growth in ms.",
            ),
            (
                "📉",
                "<b>Zero-Bias Strategy:</b> Eliminate empiricism with proven paths.",
            ),
            (
                "📈",
                "<b>Yield Assurance:</b> Turn theoretical robustness into production gains.",
            ),
        ]

        for i, (icon, text) in enumerate(points):
            item_widget = QWidget()

            item_layout = QHBoxLayout(item_widget)

            item_layout.setContentsMargins(0, 0, 0, 0)

            lbl_ico = QLabel(icon)

            lbl_ico.setStyleSheet("font-size: 20px; background: transparent;")

            lbl_ico.setFixedWidth(25)

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; background: transparent;")

            lbl_txt.setTextFormat(Qt.TextFormat.RichText)

            lbl_txt.setWordWrap(True)

            item_layout.addWidget(lbl_ico)

            item_layout.addWidget(lbl_txt)

            mission_layout.addWidget(item_widget, i // 2, i % 2)

        content_layout.addWidget(mission_frame)

        dash_frame = QFrame()

        dash_frame.setProperty("class", "dash-frame")

        shadow_dash = QGraphicsDropShadowEffect()

        shadow_dash.setBlurRadius(15)

        shadow_dash.setColor(QColor(0, 0, 0, 10))

        shadow_dash.setOffset(0, 2)

        dash_frame.setGraphicsEffect(shadow_dash)

        dash_layout = QHBoxLayout(dash_frame)

        dash_layout.setContentsMargins(12, 12, 12, 12)

        dash_layout.setSpacing(12)

        # Get approximate total CPU count

        from certus.core.certus_core import _get_cpu_count

        cpu_count = _get_cpu_count()

        try:
            mat_count = len(APP_CONTEXT.get("materials_db").data) if APP_CONTEXT.get("materials_db") else 0

        except (AttributeError, TypeError):
            mat_count = 0

        sys_layout = QVBoxLayout()

        sys_head = QLabel("SYSTEM READINESS")

        sys_head.setProperty("class", "dash-header")

        sys_layout.addWidget(sys_head)

        sys_layout.addLayout(self._create_status_row("⚡", "HPC Active", f"<b>{cpu_count} Threads</b>"))

        sys_layout.addLayout(self._create_status_row("📚", "Database", f"<b>{mat_count} Materials</b>"))

        sys_layout.addLayout(self._create_status_row("🚀", "JIT Engine", "<b>Compiled & Ready</b>"))

        sys_layout.addStretch()

        cap_layout = QVBoxLayout()

        cap_head = QLabel("CORE CAPABILITIES")

        cap_head.setProperty("class", "dash-header")

        cap_layout.addWidget(cap_head)

        cap_layout.addLayout(self._create_status_row("✓", "Hybrid Exploration", "DP + hybridization"))

        cap_layout.addLayout(self._create_status_row("✓", "Simulation", "Adaptive Nucleation"))

        cap_layout.addLayout(self._create_status_row("✓", "Analysis", "Yield & Robustness"))

        cap_layout.addStretch()

        dash_layout.addLayout(sys_layout)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.VLine)

        line.setStyleSheet(f"color: {CertusTheme.SURFACE_HOVER};")

        dash_layout.addWidget(line)

        dash_layout.addLayout(cap_layout)

        content_layout.addWidget(dash_frame)

        main_layout.addWidget(content_wrapper)

        main_layout.addStretch()

    def _create_step_card(self, number, title, desc, accent_color) -> Any:

        card = QFrame()

        card.setProperty("class", "step-card")

        card.setStyleSheet(
            f".step-card {{ border-bottom: 4px solid {accent_color}; padding: 10px 12px; }}"
        )

        card.setMinimumWidth(160)

        card.setMaximumWidth(220)

        card.setMinimumHeight(130)

        shadow = QGraphicsDropShadowEffect()

        shadow.setBlurRadius(18)

        shadow.setColor(QColor(0, 0, 0, 16))

        shadow.setOffset(0, 6)

        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)

        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.setSpacing(2)

        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_num = QLabel(number)

        lbl_num.setProperty("class", "step-number")

        lbl_num.setStyleSheet(f"color: {accent_color}; background: transparent;")

        lbl_title = QLabel(title)

        lbl_title.setProperty("class", "step-title")

        lbl_title.setStyleSheet("background: transparent;")

        lbl_desc = QLabel(desc)

        lbl_desc.setProperty("class", "step-desc")

        lbl_desc.setStyleSheet("background: transparent;")

        vbox.addWidget(lbl_num)

        vbox.addWidget(lbl_title)

        vbox.addWidget(lbl_desc)

        return card

    def _create_status_row(self, icon, label, value) -> Any:

        row = QHBoxLayout()

        row.setSpacing(15)

        lbl_icon = QLabel(icon)

        lbl_icon.setFixedSize(24, 24)

        lbl_icon.setStyleSheet(
            f"background-color: {CertusTheme.INFO_BG}; color: {CertusTheme.SECONDARY}; border-radius: 4px; font-weight: bold; font-size: 14px;"
        )

        if icon == "✓":
            lbl_icon.setStyleSheet(
                f"background-color: {CertusTheme.SUCCESS_BG}; color: {CertusTheme.SUCCESS}; border-radius: 4px; font-weight: bold; font-size: 14px;"
            )

        lbl_text = QLabel(label)

        lbl_text.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 13px; font-weight: 500; background: transparent;"
        )

        lbl_val = QLabel(value)

        lbl_val.setTextFormat(Qt.TextFormat.RichText)

        lbl_val.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 13px; background: transparent;")

        row.addWidget(lbl_icon)

        row.addWidget(lbl_text)

        row.addStretch()

        row.addWidget(lbl_val)

        return row

class CertusStratApp(CertusBaseApp):
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

    def _request_stop(self) -> None:
        """Called by reset framework before stopping workers. Sets stop flag so worker loop exits when in a run."""

        if hasattr(self, "worker") and self.worker is not None and getattr(self.worker, "isRunning", lambda: False)():
            if hasattr(self.worker, "params") and isinstance(self.worker.params, dict):
                self.worker.params["stop_requested"] = True

    def _load_defaults(self) -> None:
        """Load default values for CERTUS-STRAT"""

        # Reset workflow state

        self.opti_results = None

        self.undo_stack.clear()

        # Reset materials database

        if hasattr(self, "materials_db"):
            self.materials_db.clear_cache()

        # Reset stack table

        if hasattr(self, "widgets") and "stack_table" in self.widgets:
            self.widgets["stack_table"].setRowCount(0)

        # Reset material selections

        if hasattr(self, "widgets"):
            default_materials = {"substrate_choice": "Custom", "nSub_custom": "1.73", "l0": "550.0"}

            for widget_name, default_value in default_materials.items():
                if widget_name in self.widgets:
                    if hasattr(self.widgets[widget_name], "setCurrentText"):
                        self.widgets[widget_name].setCurrentText(default_value)

                    elif hasattr(self.widgets[widget_name], "setText"):
                        self.widgets[widget_name].setText(default_value)

        # Close all auxiliary windows

        self.close_all_auxiliary_windows()

        # Kill existing log timer before creating a new one (prevents timer leak)

        if getattr(self, "_log_timer_id", None) is not None:
            self.killTimer(self._log_timer_id)

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        self._init_global_shortcuts()

    def apply_default_layout(self) -> None:

        main_splitter = self.centralWidget()

        if isinstance(main_splitter, QSplitter):
            total_width = self.width()

            main_splitter.setSizes([int(total_width / 2), int(total_width / 2)])

    def _init_global_shortcuts(self) -> None:
        """Global UX Hotkeys (Pro 2026 Theme)."""

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_configuration)

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_configuration)

        run_opti = QShortcut(QKeySequence("F5"), self)

        run_opti.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        run_opti_alt = QShortcut(QKeySequence("Ctrl+R"), self)

        run_opti_alt.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        QShortcut(QKeySequence("Esc"), self).activated.connect(self.close_all_auxiliary_windows)

        install_standard_shortcuts(
            self,
            help=lambda: open_documentation("CERTUS_STRAT"),
            toggle_logs=lambda: self.toggle_details_btn.setChecked(not self.toggle_details_btn.isChecked()),
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
        )

        def _on_config_drop(paths) -> None:
            if paths and hasattr(self, "load_configuration"):
                self.load_configuration(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_config_drop, extensions=("json",))

    def _apply_theme(self) -> None:

        font = CertusTheme.get_font(9)

        QApplication.instance().setFont(font)

        QApplication.instance().setStyle("Fusion")

        # Propagate theme to auxiliary windows if open

        if hasattr(self, "live_monitor_window") and self.live_monitor_window and self.live_monitor_window.isVisible():
            # Force style refresh for live monitor

            self.live_monitor_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

            # If it has plots, ideally update them too - generic refresh

            self.live_monitor_window.style().unpolish(self.live_monitor_window)

            self.live_monitor_window.style().polish(self.live_monitor_window)

        if hasattr(self, "results_window") and self.results_window and self.results_window.isVisible():
            self.results_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

        # Apply theme with STRAT-specific overrides

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}

            /* Labels are slightly subtler in STRAT */

            QLabel {{ color: {CertusTheme.TEXT_SUB}; font-weight: 500; }}

            /* STRAT buttons - wider padding, secondary hover */

            QPushButton {{ padding: 6px 16px; }}

            QPushButton:hover {{ border-color: {CertusTheme.SECONDARY}; }}

            QPushButton:pressed {{ background-color: {CertusTheme.BACKGROUND}; padding-top: 7px; }}

            /* Special RUN FULL Button Gradient */

            QPushButton[text^="RUN FULL"] {{ 

                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {CertusTheme.PRIMARY}, stop:1 #2563eb); 

                color: white; border: none; font-size: 13px; padding: 12px; border-radius: 8px; 

            }}

            QPushButton[text^="RUN FULL"]:hover {{ 

                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 {CertusTheme.SECONDARY}); 

                border: 1px solid #bfdbfe; 

            }}

            QPushButton[text^="RUN FULL"]:disabled {{ 

                background-color: {CertusTheme.TEXT_DISABLED}; color: {CertusTheme.BORDER}; 

            }}

            /* GroupBox harmonized with CertusCard */

            QGroupBox {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; margin-top: 14px; padding: 10px 10px 8px 10px; font-weight: 600; color: {CertusTheme.TEXT_MAIN}; }}

            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 6px; color: {CertusTheme.PRIMARY}; background: {CertusTheme.SURFACE}; }}

            /* Tabs STRAT specific */

            QTabWidget::pane {{ border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; background: {CertusTheme.SURFACE}; top: -1px; }}

            QTabBar::tab {{ background: transparent; border: none; border-bottom: 3px solid transparent; padding: 10px 20px; margin-right: 4px; color: {CertusTheme.TEXT_SUB}; font-weight: 600; }}

            QTabBar::tab:selected {{ color: {CertusTheme.PRIMARY}; border-bottom: 3px solid {CertusTheme.PRIMARY}; background: rgba(30, 58, 138, 0.04); border-top-left-radius: 6px; border-top-right-radius: 6px; }}

            QTabBar::tab:hover:!selected {{ color: {CertusTheme.TEXT_MAIN}; background: rgba(0,0,0,0.02); }}

        """,
        )

    def timerEvent(self, event) -> None:
        log_timer_id = getattr(self, "_log_timer_id", -1)
        plot_timer_id = getattr(self, "plot_timer", -1)

        if event.timerId() == log_timer_id:
            self._process_log_queue()

        elif event.timerId() == plot_timer_id:
            self.process_plot_queue()

        else:
            super().timerEvent(event)

    def on_stats_update(self, counter_type: str, increment: int) -> None:

        if counter_type in self.stat_counters:
            self.stat_counters[counter_type] += increment

            self.update_stats_display()

    def _warmup_numba(self) -> None:
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        import threading
        if hasattr(self, "status_label"):
            self.status_label.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _warmup_numba_thread_runner(self) -> None:
        try:
            dummy_wl, dummy_n, dummy_thick = (
                np.array([1000.0], dtype=np.float64),
                np.array([1.5], dtype=np.float64),
                np.array([100.0], dtype=np.float64),
            )

            _ = calculate_RT_vectorized_real_HL(dummy_wl, dummy_n, dummy_n, dummy_n, dummy_thick)

            _ = simulate_growth_kernel(
                dummy_thick,
                0,
                np.array([0.0], dtype=np.float64),
                1000.0,
                2.3,
                1.45,
                1.52,
                80.0,
                0.0,
                1.0,
                NON_MONOTONIC_MODE_ATTENUATE,
            )

            # Heavier optimization JIT kernels warmup
            dummy_cand = np.array([550.0], dtype=np.float64)
            dummy_thick_nom = np.array([100.0, 100.0], dtype=np.float64)
            dummy_complex = np.array([2.3 + 0.0j], dtype=np.complex128)

            _ = rank_nucleation_candidates_kernel(
                dummy_cand,
                dummy_thick_nom,
                dummy_complex,
                dummy_complex,
                dummy_complex,
                0.01,
                80.0,
                2.0,
                2,
                1,
                True,
                NON_MONOTONIC_MODE_ATTENUATE,
                0,
            )

            _ = find_nucleation_adaptive_kernel(
                dummy_cand,
                dummy_thick_nom,
                dummy_complex,
                dummy_complex,
                dummy_complex,
                0.01,
                80.0,
                2.0,
                2,
                2,
                1,
                1.4,
                1.5,
                True,
                NON_MONOTONIC_MODE_ATTENUATE,
                0,
            )

            dummy_history = np.zeros((1, 2), dtype=np.float64)
            dummy_noise = np.array([0.0], dtype=np.float64)

            _ = validate_wavelengths_batch(
                dummy_cand,
                dummy_complex,
                dummy_complex,
                dummy_complex,
                dummy_history,
                dummy_thick_nom,
                0,
                80.0,
                dummy_noise,
                2.0,
                NON_MONOTONIC_MODE_ATTENUATE,
            )

            self.numba_ready = True
            self.sig_numba_ready.emit()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning(f"Numba warmup warning: {e}")
            self.numba_ready = True
            self.sig_numba_ready.emit()

        except Exception as e:
            self.logger.error(f"Numba warmup failed: {e}", exc_info=True)
            self.sig_numba_error.emit()

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:

        self.logger.info("✅ System Ready (Numba JIT Compiled)")

        self.status_label.setText("Ready.")

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)

        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText("JIT Init Error")


    def on_toggle_details(self, checked) -> None:

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

    def update_stats_display(self) -> None:
        from certus.ui.certus_ui import format_count_kmg

        self.stats_label.setText(
            f"♟️ {format_count_kmg(self.stat_counters['MS'])}  | 🎲 {format_count_kmg(self.stat_counters['MCS'])}  |  🌈️ {format_count_kmg(self.stat_counters['SP'])}"
        )

    def _stop_active_render_thread(self, timeout_ms: int = 5000) -> None:

        active_thread = getattr(self, "_active_render_thread", None)
        if active_thread is None:
            return

        try:
            if active_thread.isRunning():
                self.logger.debug("[STRAT-UI] Stopping active render thread...")
                active_thread.quit()
                if not active_thread.wait(timeout_ms):
                    self.logger.warning("[STRAT-UI] Active render thread did not stop within %sms.", timeout_ms)
                    active_thread.requestInterruption()
                    active_thread.wait(min(timeout_ms, 1000))
        except (RuntimeError, AttributeError):
            pass
        finally:
            if active_thread is not None and not active_thread.isRunning():
                self._active_render_thread = None

    def _stop_worker_thread(self, timeout_ms: int = 10000) -> None:

        worker = getattr(self, "worker", None)
        if worker is None:
            return

        try:
            if hasattr(worker, "params") and isinstance(worker.params, dict):
                worker.params["stop_requested"] = True

            if worker.isRunning():
                self.logger.debug("[STRAT-UI] Stopping worker thread id=%s...", id(worker))
                worker.quit()
                if not worker.wait(timeout_ms):
                    self.logger.warning("[STRAT-UI] Worker thread did not stop within %sms.", timeout_ms)
                    worker.requestInterruption()
                    worker.wait(min(timeout_ms, 1000))
        except (RuntimeError, AttributeError):
            pass
        finally:
            if worker is not None and not worker.isRunning():
                self.worker = None

    def _register_worker_thread(self, thread: QThread | None, label: str) -> None:

        if thread is None:
            return

        # Purge finished threads to avoid accumulation
        if hasattr(self, "_stopping_threads"):
            self._stopping_threads = [t for t in self._stopping_threads if t is not None and t.isRunning()]

        self.logger.debug("[STRAT-UI] Register worker thread label=%s id=%s running=%s", label, id(thread), thread.isRunning())
        self._active_worker_threads.append(thread)
        thread.finished.connect(lambda: self._unregister_worker_thread(thread, label))

    def _unregister_worker_thread(self, thread: QThread | None, label: str = "unknown") -> None:
        self.logger.info("[DEBUG-UI] _unregister_worker_thread called for %s", label)
        # NOTE: No QMessageBox here — this slot is connected to QThread.finished
        # which is emitted from the finishing thread. Calling any GUI widget
        # from a non-GUI thread crashes PyQt6 immediately.

        try:
            if thread in self._active_worker_threads:
                self._active_worker_threads.remove(thread)
                self.logger.debug("[STRAT-UI] Unregister worker thread label=%s id=%s", label, id(thread))
            if thread is not None:
                if not hasattr(self, "_stopping_threads"):
                    self._stopping_threads = []
                self._stopping_threads.append(thread)
                thread.deleteLater()
        except (RuntimeError, AttributeError, ValueError):
            pass

    def _stop_all_worker_threads(self, timeout_ms: int = 5000) -> None:

        threads = list(getattr(self, "_active_worker_threads", []))
        if not threads:
            return

        self.logger.debug("[STRAT-UI] Stopping %d worker threads...", len(threads))
        for thread in threads:
            try:
                if thread is not None and thread.isRunning():
                    self.logger.debug("[STRAT-UI] -> quitting worker thread id=%s", id(thread))
                    thread.quit()
            except (RuntimeError, AttributeError):
                continue
        deadline = time.time() + (timeout_ms / 1000.0)
        for thread in threads:
            try:
                remaining = max(0, int((deadline - time.time()) * 1000))
                if thread is not None and thread.isRunning() and remaining > 0:
                    if not thread.wait(remaining):
                        self.logger.warning("[STRAT-UI] Worker thread did not stop in time id=%s", id(thread))
            except (RuntimeError, AttributeError):
                continue
        self._active_worker_threads = [t for t in self._active_worker_threads if t is not None and t.isRunning()]

    def close_all_auxiliary_windows(self) -> None:

        self.logger.debug(
            "[STRAT-UI] Closing all auxiliary windows (plot=%d, transmission=%d, json=%d, spectrum=%d, table=%s, live=%s, heatmap=%s, stack=%s, worker_threads=%d)",
            len(getattr(self, "plot_windows", [])),
            len(getattr(self, "transmission_windows", [])),
            len(getattr(self, "json_windows", [])),
            len(getattr(self, "interactive_spectrum_windows", [])),
            bool(getattr(self, "strategies_table_window", None)),
            bool(getattr(self, "live_monitor_window", None)),
            bool(getattr(self, "heatmap_window", None)),
            bool(getattr(self, "stack_visual_window", None)),
            len(getattr(self, "_active_worker_threads", [])),
        )

        lists_to_close = [
            self.plot_windows,
            self.transmission_windows,
            self.json_windows,
            getattr(self, "interactive_spectrum_windows", []),
        ]

        for win_list in lists_to_close:
            for win in win_list[:]:
                try:
                    win.close()

                except (RuntimeError, AttributeError):
                    # Window may already be closed or destroyed

                    pass

            del win_list[:]

        for attr_name in [
            "strategies_table_window",
            "live_monitor_window",
            "heatmap_window",
            "stack_visual_window",
            "_floating_stack_window",
        ]:
            win = getattr(self, attr_name, None)

            if win:
                try:
                    win.close()
                except (RuntimeError, AttributeError):
                    pass

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self) and hasattr(self, "status_label"):
            self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"])

    def _build_log_container(self) -> QWidget:
        """Build log container with Copy button (uses shared CertusLogPanel)."""

        panel = CertusLogPanel(title="LOGS", visible=False)

        self.log_text = panel.log_text

        self._log_panel = panel

        return panel

    def _build_gui(self) -> None:

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_split = main_splitter

        self.setCentralWidget(main_splitter)

        left_panel_widget = QWidget()

        left_panel_layout = QVBoxLayout(left_panel_widget)

        left_panel_widget.setMinimumWidth(280)

        # Removed MaximumWidth to allow resizing via splitter

        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        left_panel_layout.setSpacing(0)

        # 1. Standard Header (Pinned)

        header_widget = create_header_logo_widget(
            "STRAT",
            self.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_STRAT",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_panel_layout.addWidget(header_widget)

        # 2. Action Bar (Pinned)

        # Note: No export function passed as it's not standard in STRAT top bar yet.

        action_bar = create_top_actions_bar(
            self,
            self.save_configuration,
            self.load_configuration,
            export_func=None,
            help_func=lambda: open_documentation("CERTUS_STRAT"),
        )

        left_panel_layout.addWidget(action_bar)

        # 3. Scroll Area

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        left_panel_layout.addWidget(scroll_area)

        main_splitter.addWidget(left_panel_widget)

        controls_widget = QWidget()

        scroll_area.setWidget(controls_widget)

        controls_layout = QVBoxLayout(controls_widget)

        controls_layout.setSpacing(8)

        controls_layout.setContentsMargins(0, 0, 4, 0)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Build stack · 2 Configure optimization · 3 Run workflow · 4 Inspect strategies")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; line-height: 1.4; padding: 2px 0 4px 0;"
        )

        workflow_card.body.addWidget(workflow_hint)

        controls_layout.addWidget(workflow_card)

        self.tabs = QTabWidget()

        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tabs_card = CertusCard("Controls")

        tabs_card.body.setContentsMargins(0, 0, 0, 0)

        tabs_card.body.addWidget(self.tabs)

        controls_layout.addWidget(tabs_card)

        self._create_design_tab()

        self._create_optimization_tab()

        self._create_advanced_tab()

        self._create_why_certus_tab()

        controls_layout.addStretch()

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        main_splitter.addWidget(right_splitter)

        self.plot_stack = QStackedWidget()

        self.welcome_widget = WelcomeGuideWidget()

        self.plot_stack.addWidget(self.welcome_widget)

        self.main_plot_widget = QLabel()

        self.main_plot_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_plot_widget.setScaledContents(True)

        self.main_plot_widget.setStyleSheet(f"background-color: {CertusTheme.SURFACE};")

        self.plot_stack.addWidget(self.main_plot_widget)

        right_splitter.addWidget(self.plot_stack)

        log_widget = self._build_log_container()

        right_splitter.addWidget(log_widget)

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.status_bar.setSizeGripEnabled(False)

        self.zoom_label = QLabel("Zoom 100%")
        self.zoom_label.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding: 0 8px;"
        )

        self.toggle_details_btn = QPushButton("Show Details")

        self.toggle_details_btn.setCheckable(True)

        self.toggle_details_btn.setFixedWidth(118)

        self.toggle_details_btn.setToolTip("Show/hide the computation log panel below the plot area.")

        self.toggle_details_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {CertusTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 7px 12px;
                font-size: 11px;
                font-weight: 700;
            }}

            QPushButton:checked {{ background-color: {CertusTheme.SECONDARY}; }}
            QPushButton:hover {{ background-color: {CertusTheme.INFO}; }}
        """)

        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        self.status_bar.addWidget(self.toggle_details_btn)
        self.status_bar.addPermanentWidget(self.zoom_label)

        self.status_label = CertusStatusPill("Ready.", "ready")

        self.status_bar.addWidget(self.status_label, 1)

        self.stats_label = QLabel("♟️ 0  | 🎲 0  |  🌈️ 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: 700; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.stats_label.setToolTip(
            "♟️ Mining Strategies evaluated  |  🎲 Monte Carlo Simulations run  |  🌈 Spectral points processed"
        )

        self.status_bar.addPermanentWidget(self.stats_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setFixedWidth(200)

        self.progress_bar.setFixedHeight(14)

        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        self.status_bar.addPermanentWidget(self.progress_bar)

        if getattr(self, "_log_panel", None):
            self._log_panel.copied.connect(lambda: self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"]))



    def _update_zoom_label(self, factor: float) -> None:
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"Zoom {int(round(factor * 100))}%")

    def _apply_ui_zoom(self, factor: float) -> None:
        apply_app_zoom(
            self,
            factor,
            label_attr="zoom_label",
            stylesheet_fn=None,
            toast_fn=show_toast,
            base_font_size=getattr(CertusTheme, "FONT_SIZE_BASE", 10),
        )

    def _create_design_tab(self) -> None:

        design_tab = QWidget()

        self.tabs.addTab(design_tab, "Design")

        self.design_layout = QVBoxLayout(design_tab)

        self.design_layout.setSpacing(8)

        self.design_layout.setContentsMargins(5, 8, 5, 5)

        materials_container = CertusCard("Material Refractive Indices")

        materials_layout = QHBoxLayout()

        materials_layout.setSpacing(10)

        materials_layout.setContentsMargins(5, 12, 5, 5)

        materials_container.body.addLayout(materials_layout)

        layout_h = QVBoxLayout()

        self._create_material_group(layout_h, "High-Index (H)", "h", "H", _is_compact=True)

        layout_l = QVBoxLayout()

        self._create_material_group(layout_l, "Low-Index (L)", "l", "L", _is_compact=True)

        materials_layout.addLayout(layout_h, 1)

        materials_layout.addLayout(layout_l, 1)

        self.design_layout.addWidget(materials_container)

        top_settings_widget = QWidget()

        top_settings_layout = QHBoxLayout(top_settings_widget)

        top_settings_layout.setContentsMargins(0, 5, 0, 5)

        top_settings_layout.setSpacing(10)

        gb_sub = CertusCard("substrate_Base Wavelength")

        gb_sub_layout = QHBoxLayout()

        gb_sub_layout.setContentsMargins(10, 15, 10, 8)

        gb_sub.body.addLayout(gb_sub_layout)

        gb_sub_layout.setSpacing(10)

        lbl_sub = QLabel("substrate:")

        self.widgets["substrate_choice"] = QComboBox()

        self.widgets["substrate_choice"].addItems(["Custom"] + list(SUBSTRATE_MAPPING.keys()))

        self.widgets["substrate_choice"].setMinimumWidth(100)

        self.widgets["substrate_choice"].setToolTip(
            "substrate material. 'Custom' lets you enter a fixed real index below.\n"
            "Predefined substrates fill the index field automatically."
        )

        self.widgets["substrate_choice"].currentTextChanged.connect(self._on_substrate_choice_changed)

        lbl_idx = QLabel("Index:")

        self.widgets["nSub_custom"] = QLineEdit()

        self.widgets["nSub_custom"].setPlaceholderText("1.73")

        self.widgets["nSub_custom"].setFixedWidth(50)

        self.widgets["nSub_custom"].setToolTip(
            "Real part of the substrate refractive index (used when substrate = Custom)."
        )

        gb_sub_layout.addWidget(lbl_sub)

        gb_sub_layout.addWidget(self.widgets["substrate_choice"])

        gb_sub_layout.addWidget(lbl_idx)

        gb_sub_layout.addWidget(self.widgets["nSub_custom"])

        gb_lam = CertusCard("Reference")

        gb_lam_layout = QHBoxLayout()

        gb_lam_layout.setContentsMargins(10, 15, 10, 8)

        gb_lam.body.addLayout(gb_lam_layout)

        lbl_l0 = QLabel("Center lambda₀ (nm):")

        lbl_l0.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {CertusTheme.INFO_TEXT};")

        self.widgets["l0"] = QLineEdit()

        self.widgets["l0"].setFixedWidth(70)

        self.widgets["l0"].setStyleSheet(
            f"font-weight: bold; background-color: {CertusTheme.WARNING_BG}; border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; color: {CertusTheme.TEXT_MAIN};"
        )

        self.widgets["l0"].setToolTip(
            "Reference (center) wavelength lambda₀ in nanometres.\n"
            "Used as the nucleation anchor and to convert optical thicknesses (QWOT = lambda₀/4n).\n"
            "Also used as the nucleation wavelength for the first monochromatic monitoring block."
        )

        gb_lam_layout.addWidget(lbl_l0)

        gb_lam_layout.addWidget(self.widgets["l0"])

        top_settings_layout.addWidget(gb_sub)

        top_settings_layout.addWidget(gb_lam)

        self.design_layout.addWidget(top_settings_widget)

        self.stack_group = CertusCard("Stack Control & Workflow")

        cockpit_layout = QHBoxLayout()

        self.stack_group.body.addLayout(cockpit_layout)

        cockpit_layout.setContentsMargins(5, 15, 5, 5)

        cockpit_layout.setSpacing(80)

        tools_widget = QWidget()

        tools_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tools_grid = QGridLayout(tools_widget)

        tools_grid.setContentsMargins(0, 0, 0, 0)

        tools_grid.setSpacing(8)

        tools_grid.setColumnStretch(0, 1)

        tools_grid.setColumnStretch(1, 1)

        btn_style = f"QPushButton {{ border-radius: 6px; border: 1px solid {CertusTheme.BORDER}; background: {CertusTheme.SURFACE}; font-size: 11px; font-weight: 600; color: {CertusTheme.TEXT_MAIN}; padding: 5px 10px; text-align: left; }} QPushButton:hover {{ background: {CertusTheme.SURFACE_HOVER}; border-color: {CertusTheme.SECONDARY}; }}"

        def set_std_icon(btn, pixmap_enum) -> None:

            btn.setIcon(self.style().standardIcon(pixmap_enum))

        self.add_btn = QPushButton("Add Layer")

        self.add_btn.setFixedHeight(32)

        self.add_btn.setStyleSheet(
            btn_style
            + f"color: {CertusTheme.SUCCESS_TEXT}; border-color: {CertusTheme.SUCCESS_BG}; background: {CertusTheme.SUCCESS_BG};"
        )

        set_std_icon(self.add_btn, QStyle.StandardPixmap.SP_FileDialogNewFolder)

        self.add_btn.setToolTip("Add a new layer at the bottom of the stack table.")

        self.add_btn.clicked.connect(self.add_layer)

        self.remove_btn = QPushButton("Remove Layer")

        self.remove_btn.setFixedHeight(32)

        self.remove_btn.setStyleSheet(
            btn_style
            + f"color: {CertusTheme.DANGER_TEXT}; border-color: {CertusTheme.DANGER_BG}; background: {CertusTheme.DANGER_BG};"
        )

        set_std_icon(self.remove_btn, QStyle.StandardPixmap.SP_TrashIcon)

        self.remove_btn.setToolTip("Remove the last (bottom) layer from the stack table.")

        self.remove_btn.clicked.connect(self.remove_layer)

        tools_grid.addWidget(self.add_btn, 0, 0)

        tools_grid.addWidget(self.remove_btn, 0, 1)

        btn_save = QPushButton("Save Config")

        btn_save.setFixedHeight(30)

        btn_save.setStyleSheet(btn_style)

        set_std_icon(btn_save, QStyle.StandardPixmap.SP_DialogSaveButton)

        btn_save.setToolTip("Save the current stack & all parameters to a JSON config file (Ctrl+S).")

        btn_save.clicked.connect(self.save_configuration)

        btn_load = QPushButton("Load Config")

        btn_load.setFixedHeight(30)

        btn_load.setStyleSheet(btn_style)

        set_std_icon(btn_load, QStyle.StandardPixmap.SP_DialogOpenButton)

        btn_load.setToolTip("Load a previously saved JSON config file, restoring stack & parameters (Ctrl+O).")

        btn_load.clicked.connect(self.load_configuration)

        tools_grid.addWidget(btn_save, 1, 0)

        tools_grid.addWidget(btn_load, 1, 1)

        self.load_strat_btn = QPushButton("Import Strat.")

        self.load_strat_btn.setFixedHeight(30)

        self.load_strat_btn.setStyleSheet(btn_style)

        set_std_icon(self.load_strat_btn, QStyle.StandardPixmap.SP_ArrowDown)

        self.load_strat_btn.setToolTip(
            "Import an external strategies JSON file generated by a previous CERTUS-STRAT run.\n"
            "Allows direct comparison of strategies without re-running the full workflow."
        )

        self.load_strat_btn.clicked.connect(self.load_external_strategies)

        self.detach_btn = QPushButton("Pop-Out")

        self.detach_btn.setFixedHeight(30)

        self.detach_btn.setStyleSheet(btn_style)

        set_std_icon(self.detach_btn, QStyle.StandardPixmap.SP_TitleBarNormalButton)

        self.detach_btn.setToolTip("Detach the Stack Definition table into its own floating window for easier editing.")

        self.detach_btn.clicked.connect(self.detach_stack_window)

        tools_grid.addWidget(self.load_strat_btn, 2, 0)

        tools_grid.addWidget(self.detach_btn, 2, 1)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.HLine)

        line.setStyleSheet(f"color:{CertusTheme.BORDER};")

        tools_grid.addWidget(line, 3, 0, 1, 2)

        self.run_step0_btn = QPushButton("Step 1 (Nominal)")
        self.run_step0_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step0_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step0_btn, QStyle.StandardPixmap.SP_ComputerIcon)

        self.run_step0_btn.setToolTip(
            "Step 0: Computes the basic optical response of the nominal layer stack without exploration."
        )

        self.run_step0_btn.clicked.connect(functools.partial(self.run_workflow, 0))

        tools_grid.addWidget(self.run_step0_btn, 4, 0)

        self.run_step2_btn = QPushButton("Step 2 (Opti)")
        self.run_step2_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step2_btn, QStyle.StandardPixmap.SP_BrowserReload)

        self.run_step2_btn.setToolTip(
            "Step 2: Launches the primary DP Optimization kernel based on the Target Spectrum."
        )

        self.run_step2_btn.clicked.connect(functools.partial(self.run_workflow, 2))

        tools_grid.addWidget(self.run_step2_btn, 4, 1)

        self.run_step3_btn = QPushButton("Step 3 (Rob)")
        self.run_step3_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step3_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step3_btn, QStyle.StandardPixmap.SP_DialogApplyButton)

        self.run_step3_btn.setEnabled(False)

        self.run_step3_btn.setToolTip(
            "Step 3: Simulates thousands of robust Monte-Carlo growth scenarios for yield estimation."
        )

        self.run_step3_btn.clicked.connect(functools.partial(self.run_workflow, 3))

        tools_grid.addWidget(self.run_step3_btn, 5, 0)

        self.stop_step2_btn = QPushButton("STOP Calculation")
        self.stop_step2_btn.setObjectName(OBJ.DANGER_BUTTON)
        self.stop_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.stop_step2_btn, QStyle.StandardPixmap.SP_MediaStop)

        self.stop_step2_btn.setToolTip(
            "Gracefully interrupt the running optimization.\n"
            "The engine will finish its current block and then proceed directly to Step 3 (robustness test)."
        )

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.stop_step2_btn.clicked.connect(self.request_stop_optimization)

        tools_grid.addWidget(self.stop_step2_btn, 5, 1)

        self.run_full_btn = QPushButton(" RUN FULL WORKFLOW")
        self.run_full_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_full_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.run_full_btn.setFixedHeight(42)

        set_std_icon(self.run_full_btn, QStyle.StandardPixmap.SP_MediaPlay)

        self.run_full_btn.setToolTip(
            "Run the complete workflow in one click:\n"
            "Step 2 (DP Strategy Search) -> Step 3 (Monte Carlo Robustness Validation).\n"
            "Equivalent to pressing Step 2 then Step 3 sequentially."
        )

        self.run_full_btn.clicked.connect(functools.partial(self.run_workflow, 23))

        tools_grid.addWidget(self.run_full_btn, 6, 0, 1, 2)

        # Clear / Reset button

        from certus.utils.certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)

        self.clear_btn.setFixedHeight(32)

        tools_grid.addWidget(self.clear_btn, 7, 0, 1, 2)

        tools_grid.setRowStretch(8, 1)

        cockpit_layout.addWidget(tools_widget)

        self.widgets["stack_table"] = ExcelTableWidget()

        self.widgets["stack_table"].setColumnCount(3)

        self.widgets["stack_table"].setHorizontalHeaderLabels(["#", "Mat.", "Mult."])

        self.widgets["stack_table"].setFixedWidth(200)

        # Column header tooltips

        _stack_col_tips = {
            0: "Layer index (1 = topmost). Read-only.",
            1: "Material type: H (high-index) or L (low-index).",
            2: "Thickness multiplier relative to QWOT (lambda₀/4n). E.g. 1.0 = 1 QWOT, 0.5 = half-wave.",
        }



        for _col, _tip in _stack_col_tips.items():
            _item = self.widgets["stack_table"].horizontalHeaderItem(_col)

            if _item:
                _item.setToolTip(_tip)

        self.widgets["stack_table"].verticalHeader().setDefaultSectionSize(22)

        h_header = self.widgets["stack_table"].horizontalHeader()

        h_header.resizeSection(0, 25)

        h_header.resizeSection(1, 35)

        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.widgets["stack_table"].setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.widgets["stack_table"].setMinimumHeight(200)

        # Connect cellChanged to save state before modification

        self.widgets["stack_table"].cellChanged.connect(self._on_stack_table_changed)

        cockpit_layout.addWidget(self.widgets["stack_table"])

        self.design_layout.addWidget(self.stack_group)

    def request_stop_optimization(self) -> None:

        # confirm_stop_with_timeout is imported from certus.ui.certus_ui

        if not confirm_stop_with_timeout(self):
            return

        if hasattr(self, "worker") and self.worker.isRunning():
            self.logger.warning(
                "⚡ USER REQUEST: Stopping Optimization Loop... Finishing current block and proceeding to Step 3."
            )

            self.worker.params["stop_requested"] = True

        self.stop_step2_btn.setText("Stopping...")

        self.stop_step2_btn.setEnabled(False)

    def _create_optimization_tab(self) -> None:

        opt_tab = QWidget()

        self.tabs.addTab(opt_tab, "Strategy Loop")

        opt_layout = QVBoxLayout(opt_tab)

        opt_layout.setSpacing(5)

        opt_layout.setContentsMargins(5, 5, 5, 5)

        scan_group = CertusCard("Spectral Scanning Range")

        scan_layout = scan_group.body

        self._create_line_edits(
            scan_layout,
            [
                ("wl_range_start", "Spectral Range Start (nm):"),
                ("wl_range_end", "Spectral Range End (nm):"),
                (
                    "wl_step",
                    "Spectral Step (nm):",
                ),
                ("extrema_exclusion_ratio", "Extrema Exclusion Ratio (1:X):"),
            ],
        )

        opt_layout.addWidget(scan_group)

        # Spectral Scanning tooltips

        _tips_scan = {
            "wl_range_start": "Start of the optical simulation wavelength range (nm). Must be within the available dispersive data range for H and L materials.",
            "wl_range_end": "End of the optical simulation wavelength range (nm).",
            "wl_step": "Spectral step (nm) used to build the simulation grid. Smaller = more precise but slower.",
            "extrema_exclusion_ratio": "Ratio 1:X - exclude 1 in X extremum from monitoring candidates to avoid crowded regions near turning points.",
        }

        for _k, _tip in _tips_scan.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        filter_group = CertusCard("Candidate Filtering")

        filter_layout = filter_group.body

        self._create_line_edits(
            filter_layout,
            [
                ("scan_wl_min", "Candidate lambda Min (nm):"),
                ("scan_wl_max", "Candidate lambda Max (nm):"),
                ("scan_wl_step", "Candidate lambda Step (nm):"),
                ("dynamics_threshold", "Dynamics Threshold:"),
                ("min_transmission_floor", "Min Transmission Floor (0-1, e.g. 0.10):"),
                ("min_spectral_resolution", "Min Spectral Resolution (nm):"),
            ],
        )

        opt_layout.addWidget(filter_group)

        # Candidate Filtering tooltips

        _tips_filter = {
            "scan_wl_min": "Minimum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_max": "Maximum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_step": "Step (nm) between candidate monitoring wavelengths during the DP scan.",
            "dynamics_threshold": "Minimum peak-to-valley transmission dynamics required for a candidate wavelength to be retained (unitless, 0-1).",
            "min_transmission_floor": "Minimum absolute transmission T required at a candidate wavelength (0-1). Excludes opaque regions.",
            "min_spectral_resolution": "Minimum allowed spectral resolution (nm) at a candidate wavelength. Below this, the optical signal is too noisy to be usable.",
        }

        for _k, _tip in _tips_filter.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        loop_group = CertusCard("Iteration Parameters (Nb Layers / X)")

        loop_layout = loop_group.body

        self._create_line_edits(
            loop_layout,
            [
                ("iter_divider_start", "Start Divider (Low Complexity) [N / X]:"),
                ("iter_divider_end", "End Divider (High Complexity) [N / X]:"),
                ("screening_mc_runs", "Screening MC Runs (Pre-selection):"),
                ("screening_keep_top_k", "Keep Top K Strategies per Config:"),
                ("mc_runs_block", "MC Runs per layer test (Phase A):"),
                ("strategy_phase_timeout", "Max Time per Iteration (sec):"),
            ],
        )

        opt_layout.addWidget(loop_group)

        # Iteration Parameters tooltips

        _tips_loop = {
            "iter_divider_start": "Low-complexity limit: the search starts with stacks of N/X layers per block iteration (X = this value). Lower X = finer search.",
            "iter_divider_end": "High-complexity limit: as stacks grow large, divides the iteration count. Higher X = faster but coarser.",
            "screening_mc_runs": "Number of Monte Carlo runs for the pre-selection screening phase. More = better filtering but slower.",
            "screening_keep_top_k": "Number of top strategies retained per configuration after screening before deep evaluation.",
            "mc_runs_block": "Monte Carlo runs per candidate block test in Phase A. Drives early robustness estimation.",
            "strategy_phase_timeout": "Maximum wall-clock time (seconds) allowed per iteration. The engine cancels the current pass if exceeded.",
        }

        for _k, _tip in _tips_loop.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sim_group = CertusCard("Simulation Parameters")

        sim_layout = sim_group.body

        self._create_line_edits(
            sim_layout,
            [
                ("thickness_tolerance_nm", "Thickness Tolerance (+/- nm):"),
                (
                    "trigger_tolerance",
                    "Trigger Tolerance (noise) %:",
                ),  # Kept for backward compat / relative
                ("mse_tolerance_limit_pct", "MSE Filtering Tolerance (Best +/- %):"),
                ("non_monotonic_error_factor", "Non-Monotonic Error Gain Factor:"),
                (
                    "wavelength_change_penalty",
                    "Penalty on Wavelength Change (x factor):",
                ),
            ],
        )

        # Noise distribution selector

        noise_dist_layout = QHBoxLayout()

        noise_dist_layout.addWidget(QLabel("Noise Distribution:"))

        self.widgets["noise_distribution"] = QComboBox()

        self.widgets["noise_distribution"].addItems(["gaussian"])

        self.widgets["noise_distribution"].setCurrentText("gaussian")

        self.widgets["noise_distribution"].setEnabled(False)

        self.widgets["noise_distribution"].setToolTip("Gaussian-only policy enabled for STRAT.")

        noise_dist_layout.addWidget(self.widgets["noise_distribution"])

        noise_dist_layout.addStretch()

        sim_layout.addLayout(noise_dist_layout)

        # Non-monotonic mode selector

        nm_mode_layout = QHBoxLayout()

        nm_mode_layout.addWidget(QLabel("Non-Monotonic Mode:"))

        self.widgets["non_monotonic_mode"] = QComboBox()

        self.widgets["non_monotonic_mode"].addItems(["attenuate", "reject"])

        self.widgets["non_monotonic_mode"].setToolTip(
            "attenuate: Divide error by factor (legacy)\nreject: Penalize non-monotonic zones (stricter)"
        )

        nm_mode_layout.addWidget(self.widgets["non_monotonic_mode"])

        nm_mode_layout.addStretch()

        sim_layout.addLayout(nm_mode_layout)

        opt_layout.addWidget(sim_group)

        # Simulation Parameters tooltips

        _tips_sim = {
            "thickness_tolerance_nm": "Gaussian noise standard deviation (+/- nm) applied to each layer thickness during Monte Carlo simulations.",
            "trigger_tolerance": "Relative trigger tolerance (% of thickness) used to define the optical trigger acceptance window.",
            "mse_tolerance_limit_pct": "MSE filtering tolerance: retain candidates within Best MSE × (1 + this %). Filters out poor strategies early.",
            "non_monotonic_error_factor": "Penalty multiplier applied to the RMSE when the growth curve is non-monotonic in the monitoring window.",
            "wavelength_change_penalty": "Cost multiplier applied each time the monitoring wavelength changes between consecutive blocks. Rewards single-wavelength strategies.",
        }

        for _k, _tip in _tips_sim.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # Reports Group

        report_group = CertusCard("Reports & Data")

        report_layout = QHBoxLayout()

        report_group.body.addLayout(report_layout)

        self.btn_open_reports = QPushButton("📂 Open Reports Folder")

        self.btn_open_reports.setToolTip("Open the folder containing HTML/Excel reports")

        self.btn_open_reports.clicked.connect(lambda: open_file_explorer(get_resource_path("reports")))

        report_layout.addWidget(self.btn_open_reports)

        opt_layout.addWidget(report_group)

        opt_layout.addStretch()

    def detach_stack_window(self) -> None:

        if self._floating_stack_window is not None:
            return

        self.detach_btn.setVisible(False)

        table = self.widgets["stack_table"]

        table.setMinimumWidth(0)

        table.setMaximumWidth(16777215)

        table.setMinimumHeight(0)

        table.setMaximumHeight(16777215)

        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._floating_stack_window = PopOutWindow(self.stack_group, self, "Stack Definition Manager")

        self._floating_stack_window.resize(600, 800)

        self._floating_stack_window.closed_signal.connect(self.reattach_stack_window)

        self._floating_stack_window.show()

    def reattach_stack_window(self) -> None:

        count = self.design_layout.count()

        self.design_layout.insertWidget(count - 1, self.stack_group)

        table = self.widgets["stack_table"]

        table.setMinimumHeight(115)

        table.setMaximumHeight(150)

        table.setFixedWidth(230)

        table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.detach_btn.setVisible(True)

        self._floating_stack_window = None

    def _create_advanced_tab(self) -> None:

        adv_tab = QWidget()

        self.tabs.addTab(adv_tab, "Advanced")

        adv_layout = QVBoxLayout(adv_tab)

        adv_layout.setSpacing(5)

        adv_layout.setContentsMargins(5, 5, 5, 5)

        robust_group = CertusCard("Robustness Test (Step 3)")

        robust_layout = robust_group.body

        self._create_line_edits(
            robust_layout,
            [
                ("robustness_noise_factors", "Noise Factors (e.g., 0.5,1,2):"),
                ("robustness_num_runs", "Number of Runs (Validation):"),
            ],
        )

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("Execution Mode:"))

        self.widgets["execution_mode"] = QComboBox()

        self.widgets["execution_mode"].addItems(["premium", "fast"])

        self.widgets["execution_mode"].setCurrentText("premium")

        self.widgets["execution_mode"].setToolTip(
            "premium: maximum quality\nfast: ~4x faster with reduced MC/consensus/elite budget"
        )

        mode_layout.addWidget(self.widgets["execution_mode"])

        mode_layout.addStretch()

        robust_layout.addLayout(mode_layout)

        adv_layout.addWidget(robust_group)

        # Robustness tooltips

        _tips_robust = {
            "robustness_noise_factors": "Comma-separated noise factor values (e.g. 0.5,1,2) applied as multipliers on the base thickness noise sigma during final validation runs.",
            "robustness_num_runs": "Number of Monte Carlo simulations in the final robustness validation (Step 3). More = more reliable RMSE/P95 statistics.",
        }

        for _k, _tip in _tips_robust.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        engine_group = CertusCard("Deep Search Engine & Hybridization")

        engine_layout = engine_group.body

        self._create_line_edits(
            engine_layout,
            [
                ("nucleation_mc_runs", "Smart Nucleation MC Runs:"),
                ("mining_candidates_limit", "Mining DP Candidates Limit:"),
                ("n_screen_runs", "Screening Runs (Phase B):"),
                ("k_keep_survivors", "Keep K Survivors per Block:"),
                ("top_k_parents", "Hybridization: Top K Parents:"),
                ("max_fusions_per_parent", "Hybridization: Max Fusions/Parent:"),
            ],
        )

        adv_layout.addWidget(engine_group)

        # Deep Search Engine tooltips

        _tips_engine = {
            "nucleation_mc_runs": "MC runs used by the Smart Nucleation phase to evaluate the first-block quality before committing to a wavelength.",
            "mining_candidates_limit": "Maximum number of DP candidate strategies extracted from the cost map during Phase A mining.",
            "n_screen_runs": "MC runs per candidate in Phase B (screening). More = better pre-ranking but slower.",
            "k_keep_survivors": "Number of top-K candidates kept after each Phase B screening pass before deep evaluation.",
            "top_k_parents": "Hybridization: number of parent strategies combined to generate hybrid offspring.",
            "max_fusions_per_parent": "Hybridization: maximum number of hybrid offspring generated per parent pair.",
        }

        for _k, _tip in _tips_engine.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        limits_group = CertusCard("Physical Limits & Search Depth")

        limits_layout = limits_group.body

        self._create_line_edits(
            limits_layout,
            [
                ("phase_a_scan_limit", "Phase A: Scan Depth (Candidates):"),
                ("phase_a_keep_limit", "Phase A: Max Retained Candidates:"),
                ("nucleation_max_rmse", "Nucleation: Max RMSE (nm):"),
                ("nucleation_degradation", "Nucleation: Degradation Thresh. (Ratio):"),
                ("step0_sigma", "Step 1: Preview Noise Sigma (nm):"),
            ],
        )

        adv_layout.addWidget(limits_group)

        # Physical Limits tooltips

        _tips_limits = {
            "phase_a_scan_limit": "Phase A: maximum number of candidate wavelengths evaluated per block iteration.",
            "phase_a_keep_limit": "Phase A: maximum number of candidates retained after scanning before Phase B screening.",
            "nucleation_max_rmse": "Nucleation: maximum acceptable RMSE (nm) for a nucleation wavelength to be accepted.",
            "nucleation_degradation": "Nucleation: if the RMSE degrades by more than this ratio vs. the reference, the nucleation attempt is rejected.",
            "step0_sigma": "Step 1 (Nominal preview): Gaussian sigma (nm) applied to simulate a quick noise preview without full Monte Carlo.",
        }

        for _k, _tip in _tips_limits.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sym_group = CertusCard("SYM Strategy Controls")

        sym_layout = sym_group.body

        self._create_line_edits(
            sym_layout,
            [
                ("sym_enable", "Enable SYM (0/1):"),
                ("sym_weight", "SYM Weight:"),
                ("sym_same_wl_bonus", "SYM Same-WL Bonus:"),
                ("sym_extrema_window", "SYM Extrema Window (OT nm):"),
                ("sym_continuity_weight", "SYM Continuity Weight:"),
                ("sym_adaptive_same_wl", "SYM Adaptive Same-WL (0/1):"),
                ("sym_allow_hybrid", "SYM Allow Hybrid Double-Score (0/1):"),
                ("sym_prefer_on_tie", "SYM Prefer on Tie (0/1):"),
                ("sym_tie_epsilon", "SYM Tie Epsilon Abs:"),
                ("sym_tie_epsilon_rel", "SYM Tie Epsilon Rel:"),
            ],
        )

        # SYM advanced field tooltips

        _tips_sym = {
            "sym_weight": "Global weight applied to the SYM score when combining it with the RMSE score. Higher = more symmetric strategies favored.",
            "sym_same_wl_bonus": "Bonus awarded when two consecutive blocks use the same monitoring wavelength.",
            "sym_extrema_window": "Optical thickness window (nm) around extrema within which candidate points qualify for SYM scoring.",
            "sym_continuity_weight": "Weight applied to reward monotonically continuous growth curves in the SYM metric.",
            "sym_adaptive_same_wl": "Enable (1) adaptive same-wavelength bonus that scales with observability quality.",
            "sym_allow_hybrid": "Allow (1) the same strategy to accumulate both a SYM score and an RMSE score simultaneously (double-score mode).",
            "sym_prefer_on_tie": "On tied RMSE score (within epsilon), prefer (1) the strategy with the better SYM score.",
            "sym_tie_epsilon": "Absolute RMSE tolerance below which two strategies are considered tied (to trigger SYM tie-break).",
            "sym_tie_epsilon_rel": "Relative RMSE tolerance (fraction of the best RMSE) for tie-breaking.",
        }

        for _k, _tip in _tips_sym.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # SYM est une strategie supplementaire obligatoire: toujours activee.

        if "sym_enable" in self.widgets:
            self.widgets["sym_enable"].setText("1")

            self.widgets["sym_enable"].setReadOnly(True)

            self.widgets["sym_enable"].setToolTip("Always active (supplementary strategy)")

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("SYM Scoring Mode:"))

        self.widgets["sym_scoring_mode"] = QComboBox()

        self.widgets["sym_scoring_mode"].addItems(["post", "pre", "hybrid"])

        self.widgets["sym_scoring_mode"].setCurrentText(SYM_DEFAULT_SCORING_MODE)

        self.widgets["sym_scoring_mode"].setToolTip(
            "post: SYM score is applied after ranking by RMSE (default).\n"
            "pre: SYM score influences block selection during DP search.\n"
            "hybrid: SYM score applied both during and after search."
        )

        mode_layout.addWidget(self.widgets["sym_scoring_mode"])

        mode_layout.addStretch()

        sym_layout.addLayout(mode_layout)

        adv_layout.addWidget(sym_group)

        adv_layout.addStretch()

    def _create_why_certus_tab(self) -> None:
        """Creates Why CERTUS? tab with FlashyCards matching INDEX/METAL/DESIGN style"""

        perf_tab = QWidget()

        self.tabs.addTab(perf_tab, "Why CERTUS?")

        perf_layout = QGridLayout(perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "High-Rate Monte Carlo",
            "Simulation of deposition dispersions\nRapid evaluation of real-world robustness",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Error Compensation",
            "Auto-compensated wavelengths\nMaintains performance under perturbations",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Dynamic Programming",
            "Block selection by global cost\nStructured, scalable, and traceable search",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Robust Statistical Validation",
            "Multi-noise stress tests + RMSE scoring\nReliable ranking of manufacturable strategies",
            icon="🔮",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

    def _create_material_group(self, parent_layout, title, prefix, label, _is_compact=False) -> None:

        group = CertusCard(title)

        layout = group.body

        layout.setSpacing(2)

        layout.setContentsMargins(4, 12, 4, 4)

        radio_layout = QHBoxLayout()

        self.widgets[f"{prefix}_type_custom"] = QRadioButton("Custom (Constant)")

        self.widgets[f"{prefix}_type_custom"].setChecked(True)  # Default to Custom mode

        self.widgets[f"{prefix}_type_file"] = QRadioButton("Dispersive (File)")

        grp = QButtonGroup(self)

        grp.addButton(self.widgets[f"{prefix}_type_custom"])

        grp.addButton(self.widgets[f"{prefix}_type_file"])

        grp.setExclusive(True)

        radio_layout.addWidget(self.widgets[f"{prefix}_type_custom"])

        radio_layout.addWidget(self.widgets[f"{prefix}_type_file"])

        radio_layout.addStretch()

        layout.addLayout(radio_layout)

        combined_layout = QHBoxLayout()

        self.widgets[f"n{label}_r"] = QLineEdit()

        self.widgets[f"n{label}_r"].setPlaceholderText("e.g. 2.3")

        self.widgets[f"n{label}_r"].setFixedWidth(50)

        self.widgets[f"n{label}_r"].setToolTip(
            "Fixed real part of the refractive index n (constant, wavelength-independent).\n"
            "Active only in 'Custom' mode."
        )

        combined_layout.addWidget(QLabel("n (real):"))

        combined_layout.addWidget(self.widgets[f"n{label}_r"])

        combined_layout.addSpacing(10)

        self.widgets[f"{prefix}_material_file"] = QComboBox()

        self.widgets[f"{prefix}_material_file"].addItems(self.material_list)

        self.widgets[f"{prefix}_material_file"].setToolTip(
            "Dispersive material file from the clues database (wavelength-dependent n & k).\n"
            "Active only in 'Dispersive (File)' mode."
        )

        combined_layout.addWidget(QLabel("Material File:"))

        combined_layout.addWidget(self.widgets[f"{prefix}_material_file"], 1)

        layout.addLayout(combined_layout)

        # Connect toggle signals to enable/disable widgets

        self.widgets[f"{prefix}_type_custom"].toggled.connect(
            lambda checked, p=prefix, l=label: self._on_material_mode_changed(p, l)
        )

        parent_layout.addWidget(group)

    def _on_material_mode_changed(self, prefix, label) -> None:
        """Enable/disable widgets based on Custom vs Dispersive selection."""

        is_custom = self.widgets[f"{prefix}_type_custom"].isChecked()

        self.widgets[f"n{label}_r"].setEnabled(is_custom)

        self.widgets[f"{prefix}_material_file"].setEnabled(not is_custom)

    def _on_substrate_choice_changed(self, text) -> None:
        """Enable custom index field only when 'Custom' substrate is selected."""

        is_custom = text == "Custom"

        self.widgets["nSub_custom"].setEnabled(is_custom)

    def _extract_stack_multipliers(self, config: dict[str, Any]) -> list[float]:
        """Return normalized stack multipliers from multiple legacy JSON shapes."""
        raw = config.get("stack_multipliers")
        if raw is None:
            raw = config.get("stack_string")
        if raw is None:
            raw = config.get("stack")
        if raw is None:
            return []
        if isinstance(raw, str):
            tokens = [t.strip() for t in raw.replace("[", "").replace("]", "").split(",") if t.strip()]
            out: list[float] = []
            for tok in tokens:
                try:
                    out.append(float(tok))
                except (TypeError, ValueError):
                    continue
            return out
        if isinstance(raw, (list, tuple)):
            out = []
            for val in raw:
                try:
                    out.append(float(val))
                except (TypeError, ValueError):
                    continue
            return out
        return []


    def _init_widget_states(self) -> None:
        """Initialize enable/disable states for all mode-dependent widgets."""

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

    def _create_line_edits(self, layout, items, columns=2) -> None:

        grid = QGridLayout()

        grid.setHorizontalSpacing(5)

        grid.setVerticalSpacing(2)

        rows = (len(items) + columns - 1) // columns

        for idx, (key, label_text) in enumerate(items):
            col_block = idx // rows

            row = idx % rows

            lbl = QLabel(label_text)

            edit = QLineEdit()

            self.widgets[key] = edit

            grid.addWidget(lbl, row, col_block * 2)

            grid.addWidget(edit, row, col_block * 2 + 1)

        for c in range(columns):
            grid.setColumnStretch(c * 2 + 1, 1)

        layout.addLayout(grid)

    def _init_undo_shortcut(self) -> None:
        """Initializes the UNDO shortcut after the interface is ready"""

        try:
            undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)

            undo_shortcut.activated.connect(self._undo_stack_table)

        except (RuntimeError, TypeError, AttributeError) as e:
            self.logger.warning(f"Could not initialize UNDO shortcut: {e}")

    def _on_stack_table_changed(self, row, col) -> None:
        """Callback called when a cell in stack_table is modified"""

        # Save state only if it is the Multiplier column (col 2)

        if col == 2:
            self._save_undo_state()

    def _save_undo_state(self) -> None:
        """Save current state of stack_table for undo"""

        # Verify undo_stack exists (might not be initialized at start)

        if not hasattr(self, "undo_stack"):
            self.undo_stack = deque(maxlen=5)

        table = self.widgets.get("stack_table")

        if table is None:
            return

        state = []

        for row in range(table.rowCount()):
            mult_item = table.item(row, 2)

            mult_val = mult_item.text() if mult_item else "1.0"

            state.append(mult_val)

        if state:
            self.undo_stack.append(state.copy())

    def _undo_stack_table(self) -> None:
        """Undo the last modification of the stack_table"""

        # Verify that undo_stack existe

        if not hasattr(self, "undo_stack") or not self.undo_stack:
            self.logger.warning("No undo state available")

            return

        state = self.undo_stack.pop()

        table = self.widgets.get("stack_table")

        if table is None:
            return

        table.blockSignals(True)

        # Adjust number of rows if necessary (without saving to undo_stack)

        while table.rowCount() < len(state):
            row = table.rowCount()

            table.insertRow(row)

            item_num = QTableWidgetItem(str(row + 1))

            item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, item_num)

            type_str = "H" if row % 2 == 0 else "L"

            item_type = QTableWidgetItem(type_str)

            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 1, item_type)

            table.setItem(row, 2, QTableWidgetItem("1.0"))

        while table.rowCount() > len(state):
            table.removeRow(table.rowCount() - 1)

        # Restore values

        for row, mult_val in enumerate(state):
            mult_item = table.item(row, 2)

            if mult_item:
                mult_item.setText(str(mult_val))

        table.blockSignals(False)

        self.logger.info(f"Undo: Restored {len(state)} layers")

    def add_layer(self) -> None:

        self._save_undo_state()

        table = self.widgets["stack_table"]

        row = table.rowCount()

        table.insertRow(row)

        item_num = QTableWidgetItem(str(row + 1))

        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 0, item_num)

        type_str = "H" if row % 2 == 0 else "L"

        item_type = QTableWidgetItem(type_str)

        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 1, item_type)

        table.setItem(row, 2, QTableWidgetItem("1.0"))

    def remove_layer(self) -> None:

        table = self.widgets["stack_table"]

        if table.rowCount() > 0:
            self._save_undo_state()

            table.removeRow(table.rowCount() - 1)

    def set_default_values(self) -> None:

        stack_string = "0.376863,0.544274,0.525625,2.014363,1.404237,1.260913,2.108868,1.619996,1.661556,1.051359,1.410965,0.96871,1.000151,0.812025,0.723532,0.679077,0.749945,0.697612,0.590237,0.654072,0.756165,0.854369,0.892505,1.147616,0.196934,0.801568,0.692039,0.793093,0.732264,0.62781,0.700873,0.742287,0.74316,0.161261,1.028982,1.563076,0.726649,0.325847,0.844091,0.496665,0.585217,0.149928,0.54806,0.302789,0.439372,1.355508"

        multipliers = [m.strip() for m in stack_string.split(",")]

        defaults = {
            "h_type_custom": True,
            "l_type_custom": True,
            "nH_r": "2.3",
            "nL_r": "1.45",
            "substrate_choice": "Custom",
            "nSub_custom": "1.73",
            "l0": "1500.0",
            "stack_multipliers": multipliers,
            "wl_range_start": "1200.0",
            "wl_range_end": "1700.0",
            "wl_step": "0.2",
            "scan_wl_min": "1200.0",
            "scan_wl_max": "1700.0",
            "scan_wl_step": "2.0",
            "dynamics_threshold": "0.025",
            "min_transmission_floor": "0.10",
            "min_spectral_resolution": "1.0",
            "iter_divider_start": "10",
            "iter_divider_end": "3",
            "screening_mc_runs": "20",
            "screening_keep_top_k": "5",
            "mc_runs_block": "100",
            "strategy_phase_timeout": "120",
            "trigger_tolerance": "0.1",
            "noise_distribution": "gaussian",
            "non_monotonic_mode": "attenuate",
            "sim_thickness_probe_offset_ratio": "80.0",
            "robustness_noise_factors": "0.5,1,2",
            "robustness_num_runs": "150",
            "execution_mode": "premium",
            "non_monotonic_error_factor": "2.0",
            "wavelength_change_penalty": "1.2",
            "force_first_layer_same_wl": False,
            "extrema_exclusion_ratio": "60.0",
            "nucleation_mc_runs": "40",
            "mining_candidates_limit": "3000",
            "n_screen_runs": "25",
            "k_keep_survivors": "10",
            "top_k_parents": "20",
            "max_fusions_per_parent": "5",
            "phase_a_scan_limit": "300",
            "phase_a_keep_limit": "50",
            "nucleation_max_rmse": "1.5",
            "nucleation_degradation": "1.4",
            "step0_sigma": "1.0",
            "sym_enable": "1",
            "sym_weight": f"{SYM_DEFAULT_WEIGHT}",
            "sym_same_wl_bonus": f"{SYM_DEFAULT_SAME_WL_BONUS}",
            "sym_extrema_window": f"{SYM_DEFAULT_EXTREMA_WINDOW_OT}",
            "sym_continuity_weight": f"{SYM_DEFAULT_CONTINUITY_WEIGHT}",
            "sym_adaptive_same_wl": "1",
            "sym_allow_hybrid": "0",
            "sym_prefer_on_tie": "1",
            "sym_tie_epsilon": f"{SYM_DEFAULT_TIE_EPS_ABS}",
            "sym_tie_epsilon_rel": f"{SYM_DEFAULT_TIE_EPS_REL}",
            "sym_scoring_mode": SYM_DEFAULT_SCORING_MODE,
            "show_plots": True,
            "export_excel": True,
        }

        self.populate_gui_from_config(defaults)

    def populate_gui_from_config(self, config: dict[str, Any]) -> None:
        """Populate GUI widgets from configuration dictionary.

        Order is critical:

        1. Set radio button states (determines which widgets will be enabled)

        2. Set ALL widget values first (including potentially disabled ones)

        3. Apply enable/disable states LAST

        """

        # Historical aliases from older example JSON payloads.
        if isinstance(config, dict):
            if "substratee_choice" in config and config.get("substrate_choice") is None:
                config["substrate_choice"] = config.get("substratee_choice")
            if "substrate_choice" in config and config.get("substratee_choice") is None:
                config["substratee_choice"] = config.get("substrate_choice")

            # Map Silice config value to standard SiO2 combo item
            if config.get("substrate_choice") == "Silice":
                config["substrate_choice"] = "SiO2"
                config["substratee_choice"] = "SiO2"

        # Step 1: Set radio button states

        self.widgets["h_type_custom"].setChecked(bool(config.get("h_type_custom", True)))

        self.widgets["h_type_file"].setChecked(not config.get("h_type_custom", True))

        self.widgets["l_type_custom"].setChecked(bool(config.get("l_type_custom", True)))

        self.widgets["l_type_file"].setChecked(not config.get("l_type_custom", True))

        # Step 2: Set ALL widget values (before enabling/disabling)

        for key, widget in self.widgets.items():
            if isinstance(widget, QLineEdit) and key in config:
                widget.setText(str(config[key]))

        for combo_key in [
            "h_material_file",
            "l_material_file",
            "substrate_choice",
            "noise_distribution",
            "non_monotonic_mode",
            "sym_scoring_mode",
            "execution_mode",
        ]:
            if combo_key in self.widgets and combo_key in config and config[combo_key]:
                idx = self.widgets[combo_key].findText(str(config[combo_key]))

                if idx >= 0:
                    self.widgets[combo_key].setCurrentIndex(idx)

        # Step 3: Apply enable/disable states LAST

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

        # Step 4: Handle stack table

        stack_mults = None

        if "stack_multipliers" in config:
            raw_mults = config["stack_multipliers"]

            if isinstance(raw_mults, list):
                stack_mults = []

                for i, val in enumerate(raw_mults):
                    try:
                        stack_mults.append(float(val))

                    except (ValueError, TypeError):
                        stack_mults.append(1.0)

        elif "stack_string" in config:
            try:
                stack_mults = [float(m.strip()) for m in str(config["stack_string"]).split(",") if m.strip()]

            except (ValueError, TypeError):
                stack_mults = None

        if stack_mults:
            try:
                table = self.widgets.get("stack_table")

                if table:
                    table.setEnabled(True)

                    table.setRowCount(0)

                    for i, m in enumerate(stack_mults):
                        table.insertRow(i)

                        item_num = QTableWidgetItem(str(i + 1))

                        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 0, item_num)

                        item_type = QTableWidgetItem("H" if i % 2 == 0 else "L")

                        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 1, item_type)

                        table.setItem(i, 2, QTableWidgetItem(f"{float(m):.6f}"))

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error populating table: {e}")

    @safe_ui_action
    def save_configuration(self) -> None:
        """Save current GUI configuration to a JSON file.

        Only saves relevant data based on selected modes:

        - If Custom mode: saves index value (nH_r/nL_r)

        - If Dispersive mode: saves material file selection

        - substrate custom index only saved if 'Custom' substrate selected

        """

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not filename:
            return

        set_certus_last_dir(filename)

        try:
            config = {
                "h_type_custom": self.widgets["h_type_custom"].isChecked(),
                "l_type_custom": self.widgets["l_type_custom"].isChecked(),
                "substrate_choice": self.widgets["substrate_choice"].currentText(),
                "l0": self.widgets["l0"].text(),
            }

            # Save only relevant H-index data

            if self.widgets["h_type_custom"].isChecked():
                config["nH_r"] = self.widgets["nH_r"].text()

            else:
                config["h_material_file"] = self.widgets["h_material_file"].currentText()

            # Save only relevant L-index data

            if self.widgets["l_type_custom"].isChecked():
                config["nL_r"] = self.widgets["nL_r"].text()

            else:
                config["l_material_file"] = self.widgets["l_material_file"].currentText()

            # Save custom substrate only if "Custom" is selected

            if self.widgets["substrate_choice"].currentText() == "Custom":
                config["nSub_custom"] = self.widgets["nSub_custom"].text()

            table = self.widgets["stack_table"]

            stack_multipliers = []

            for row in range(table.rowCount()):
                item = table.item(row, 2)

                if item:
                    try:
                        stack_multipliers.append(float(item.text()))

                    except ValueError:
                        stack_multipliers.append(1.0)

            config["stack_multipliers"] = stack_multipliers

            for key in [
                "wl_range_start",
                "wl_range_end",
                "wl_step",
                "scan_wl_min",
                "scan_wl_max",
                "scan_wl_step",
                "dynamics_threshold",
                "min_transmission_floor",
                "min_spectral_resolution",
                "mc_runs_block",
                "iter_divider_start",
                "iter_divider_end",
                "strategy_phase_timeout",
                "screening_mc_runs",
                "screening_keep_top_k",
                "trigger_tolerance",
                "sim_thickness_probe_offset_ratio",
                "non_monotonic_error_factor",
                "wavelength_change_penalty",
                "extrema_exclusion_ratio",
                "robustness_noise_factors",
                "robustness_num_runs",
                "nucleation_mc_runs",
                "mining_candidates_limit",
                "n_screen_runs",
                "k_keep_survivors",
                "top_k_parents",
                "max_fusions_per_parent",
                "phase_a_scan_limit",
                "phase_a_keep_limit",
                "nucleation_max_rmse",
                "nucleation_degradation",
                "step0_sigma",
                "sym_enable",
                "sym_weight",
                "sym_same_wl_bonus",
                "sym_extrema_window",
                "sym_continuity_weight",
                "sym_adaptive_same_wl",
                "sym_allow_hybrid",
                "sym_prefer_on_tie",
                "sym_tie_epsilon",
                "sym_tie_epsilon_rel",
            ]:
                if key in self.widgets:
                    config[key] = self.widgets[key].text()

            # Save ComboBox values

            if "noise_distribution" in self.widgets:
                config["noise_distribution"] = self.widgets["noise_distribution"].currentText()

            if "non_monotonic_mode" in self.widgets:
                config["non_monotonic_mode"] = self.widgets["non_monotonic_mode"].currentText()

            if "sym_scoring_mode" in self.widgets:
                config["sym_scoring_mode"] = self.widgets["sym_scoring_mode"].currentText()

            if "execution_mode" in self.widgets:
                config["execution_mode"] = self.widgets["execution_mode"].currentText()

            config["show_plots"] = True

            config["export_excel"] = True

            config["force_first_layer_same_wl"] = True

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.logger.info("Configuration saved: %s", filename)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error saving: {e}")

    @safe_ui_action
    def load_configuration(self, filename=None) -> None:
        """Load configuration from a JSON file and populate the GUI.

        Handles both new format (stack_multipliers list) and legacy format (stack_string).

        Opens a JSON viewer window for inspection after loading.

        Args:

            filename: Optional path to JSON file. If None, opens file dialog.

        """

        if filename is None or isinstance(filename, bool):
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", get_certus_last_dir(), "JSON Files (*.json)"
            )

        if not filename:
            return

        set_certus_last_dir(filename)

        self._last_config_file = filename

        try:
            with open(filename, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise ValueError("Configuration JSON must be an object/dictionary.")
            try:
                validated = StratConfigDTO.model_validate(config)
                config = validated.model_dump(mode="python", exclude_none=False)
            except ValidationError as e:
                msg = f"Invalid STRAT configuration: {e}"
                self.logger.error(msg)
                QMessageBox.critical(self, "Invalid configuration", msg)
                return

            self._loaded_config = dict(config)

            if "stack_string" in config and "stack_multipliers" not in config:
                try:
                    config["stack_multipliers"] = [
                        float(m) for m in str(config["stack_string"]).split(",") if m.strip()
                    ]

                except (ValueError, TypeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            self.populate_gui_from_config(config)

            short_name = Path(filename).name

            viewer = JsonViewerWindow(self, f"Config - {short_name}", config)

            viewer.show()

            viewer.raise_()

            viewer.activateWindow()

            if not hasattr(self, "json_windows"):
                self.json_windows = []

            self.json_windows.append(viewer)

            self.logger.info("=" * 60)
            self.logger.info("CONFIGURATION LOADED: %s", short_name)
            self.logger.info("=" * 60)

            for key in sorted(config.keys()):
                val = config[key]
                if isinstance(val, list) and len(val) > 10:
                    val_str = f"{val[:3]} ... ({len(val)} items) ...  {val[-3:]}"
                else:
                    val_str = str(val)

                self.logger.info("  %-35s: %s", key, val_str)

            self.logger.info("=" * 60)

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                blocks = config.get("blocks") or [] if isinstance(config, dict) else []

                strat_id = str(config.get("strategy_id", "")).strip()

                n_blocks = int(config.get("n_blocks") or len(blocks)) if isinstance(config, dict) else 0

                # Two formats: (1) GUI session via save_configuration - no strategy_id/blocks;

                # (2) export mined strategy / external JSON - strategy_id + blocks required.

                is_session_cfg = isinstance(config, dict) and (
                    "stack_multipliers" in config or "h_material_file" in config
                )

                sub_label = "UNKNOWN"

                if isinstance(config, dict):
                    sub_label = str(config.get("substrate_choice", "UNKNOWN")).strip() or "UNKNOWN"

                summary_lines: list = [
                    f"SUBSTRATE: {sub_label}",
                    "FACES: ONE FACE (NO BACKSIDE)",
                    "",
                    f"File: {Path(filename).resolve()}",
                    "",
                ]

                if is_session_cfg and not (strat_id and isinstance(blocks, list) and len(blocks) > 0):
                    n_lay = len(config.get("stack_multipliers") or []) if isinstance(config, dict) else 0

                    summary_lines.extend(
                        [
                            "Format: GUI session (save_configuration)",
                            "  -> Material parameters, stack (multipliers), execution options.",
                            "  -> The strategy_id / blocks keys are not part of this format (normal).",
                            "  -> To load mined strategies: 'external strategies' menu / dedicated JSON.",
                            "",
                            "Structure (session)",
                            f"  stack_multipliers count (layers): {n_lay}",
                            "",
                            "Embedded Strategy",
                            "  (not present - this file is not a mined strategy export)",
                        ]
                    )

                else:
                    summary_lines.extend(
                        [
                            "General",
                            f"Strategy ID: {strat_id or '(missing)'}",
                            "",
                            "Structure",
                            (f"n_blocks: {n_blocks}", n_blocks <= 0),
                            (
                                f"blocks entries: {len(blocks) if isinstance(blocks, list) else 0}",
                                not isinstance(blocks, list) or len(blocks) == 0,
                            ),
                            "",
                            "Compatibility checks",
                            f"Keys in JSON: {len(config.keys()) if isinstance(config, dict) else 0}",
                            (
                                f"Contains required keys (strategy_id, blocks): {'yes' if ('strategy_id' in config and 'blocks' in config) else 'no'}",
                                not ("strategy_id" in config and "blocks" in config),
                            ),
                        ]
                    )

                summary = build_summary_plain_text("CERTUS STRAT - Config Summary", summary_lines)

                show_load_summary_dialog(self, "STRAT Load Summary", summary)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error loading: {e}\n{traceback.format_exc()}")

    def load_external_strategies(self) -> None:

        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Strategy Files", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not files:
            return

        set_certus_last_dir(files[0])

        loaded_strategies = []

        REQUIRED_KEYS = {"strategy_id", "blocks"}

        table = self.widgets.get("stack_table")

        expected_layers = table.rowCount() if table is not None else 0

        expected_layers = max(0, int(expected_layers))

        seen_ids: set[str] = set()

        try:
            for f_path in files:
                with open(f_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)

                    except json.JSONDecodeError:
                        continue

                    def validate_and_add(item) -> None:

                        if not (isinstance(item, dict) and all(k in item for k in REQUIRED_KEYS)):
                            return

                        strat_id = str(item.get("strategy_id", "")).strip()

                        if not strat_id:
                            return

                        if strat_id in seen_ids:
                            return

                        item_norm = dict(item)

                        if "n_blocks" not in item_norm:
                            item_norm["n_blocks"] = len(item_norm.get("blocks", []))

                        # Strong schema + contract validation before running Step 33

                        expected_n = item_norm.get("n_blocks", len(item_norm.get("blocks", [])))

                        if expected_layers > 0:
                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm, expected_layers, expected_n_blocks=expected_n
                            )

                            if not ok:
                                return

                        else:
                            # If no expected layer count is available, still hard-validate block typing.

                            max_end = 0

                            for blk in item_norm.get("blocks", []):
                                if isinstance(blk, dict):
                                    try:
                                        max_end = max(max_end, int(blk.get("end", 0)))

                                    except (TypeError, ValueError):
                                        logging.getLogger("CERTUS").debug(
                                            "Silenced exception in %s", __name__, exc_info=True
                                        )

                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm,
                                num_layers=max(max_end, 1),
                                expected_n_blocks=expected_n,
                            )

                            if not ok:
                                return

                        loaded_strategies.append(item_norm)

                        seen_ids.add(strat_id)

                    if isinstance(data, list):
                        for item in data:
                            validate_and_add(item)

                    else:
                        validate_and_add(data)

            if not loaded_strategies:
                self.logger.warning("No valid strategy found.")

                return

            self.logger.info("Loaded %d valid strategies.", len(loaded_strategies))

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error parsing strategy files: {e}")

            return

        params = self.collect_params()

        if self.opti_results is None:
            self.logger.info("Initializing context for external strategies (Matrices & Indices)...")

            try:
                nominal_results, _ = calculate_nominal_properties(params)

                p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

                clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                    params, p_thick_nominal, self.logger
                )

                self.opti_results = {
                    "p_thick_nominal": p_thick_nominal,
                    "clues_at_wl": clues_at_wl,
                    "nominal_matrix_cache": nominal_matrix_cache,
                    "all_wls": all_wls,
                    "p_thick_nominal": p_thick_nominal,
                }

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Failed to initialize context: {e}")

                return

        params["loaded_strategies"] = loaded_strategies

        self.progress_bar.setValue(0)

        self.status_label.setText("Simulating Loaded Strategies...")

        for btn in [
            self.run_step0_btn,
            self.run_step2_btn,
            self.run_step3_btn,
            self.run_full_btn,
            self.load_strat_btn,
        ]:
            btn.setEnabled(False)

        self.worker = WorkerThread(
            step=StratTask.EXTERNAL_EVALUATION,
            params=params,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger,
        )
        self._register_worker_thread(self.worker, "STRAT-external-evaluation")

        self.worker.signals.finished.connect(self.on_workflow_finished)

        self.worker.signals.error.connect(self.on_workflow_error)

        self.worker.signals.progress.connect(self.on_progress_update)

        self.worker.signals.plot.connect(self.on_plot_ready)

        self.worker.signals.excel_ready.connect(self.on_excel_ready)

        try:
            self.worker.signals.show_strategies_table.disconnect(self.on_show_strategies_table)
        except (TypeError, RuntimeError):
            pass
        self.worker.signals.show_strategies_table.connect(self.on_show_strategies_table)

        self.worker.start()

    def _get_float_safe(self, widget_name, default=0.0) -> Any:

        if widget_name not in self.widgets:
            return default

        text = self.widgets[widget_name].text().strip()

        if not text:
            return default

        try:
            return float(text)

        except ValueError:
            return default

    def collect_params(self) -> dict[str, Any]:
        """Collect all GUI parameters into a dictionary for workflow execution.

        Intelligently resolves material clues:

        - Custom mode: uses constant float value from nH_r/nL_r field

        - Dispersive mode: uses material name string for database lookup

        Returns:

            Dict containing all parameters for the simulation workflow."""

        # Resolve H-index: either constant float or material name

        if self.widgets["h_type_custom"].isChecked():
            nH_id = float(self._get_float_safe("nH_r", 2.3))

        else:
            txt = self.widgets["h_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No H-material file selected. Reverting to Custom value (2.3).")

                nH_id = float(self._get_float_safe("nH_r", 2.3))

            else:
                nH_id = txt

        if self.widgets["l_type_custom"].isChecked():
            nL_id = float(self._get_float_safe("nL_r", 1.45))

        else:
            txt = self.widgets["l_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No L-material file selected. Reverting to Custom value (1.45).")

                nL_id = float(self._get_float_safe("nL_r", 1.45))

            else:
                nL_id = txt

        sub_choice = self.widgets["substrate_choice"].currentText()

        material_aliases = {
            "H800-Nb": "H800-Nb",
            "H800 Nb": "H800-Nb",
            "H800_Nb": "H800-Nb",
            "H800-SiO2": "H800-SiO2",
            "H800 SiO2": "H800-SiO2",
            "H800_SiO2": "H800-SiO2",
            "Silice": "SiO2",
        }

        if sub_choice == "Custom" or not sub_choice:
            nSub_id = self._get_float_safe("nSub_custom", 1.73)

        else:
            nSub_id = sub_choice

        table = self.widgets["stack_table"]

        multipliers = [float(table.item(r, 2).text()) for r in range(table.rowCount()) if table.item(r, 2)]

        stack_string = ",".join(map(str, multipliers))

        try:
            noise_str = self.widgets["robustness_noise_factors"].text().strip().replace("[", "").replace("]", "")

            noise_factors = [float(x.strip()) for x in noise_str.split(",") if x.strip()]

        except (ValueError, TypeError):
            noise_factors = [0.5, 1.0, 2.0]

        nH_id = material_aliases.get(str(nH_id).strip(), nH_id)
        nL_id = material_aliases.get(str(nL_id).strip(), nL_id)
        if str(nSub_id).strip() in {"Silice", "SiO2", "H800-SiO2", "H800 SiO2", "H800_SiO2"}:
            nSub_id = "SiO2"
        elif str(nSub_id).strip() in {"Sapphire", "Sapphire (Al2O3)"}:
            nSub_id = "Sapphire (Al2O3)"

        params_out = {
            "nH_id": nH_id,
            "nL_id": nL_id,
            "nSub_id": nSub_id,
            "substrate_choice": sub_choice,
            "l0": self._get_float_safe("l0", 1500.0),
            "stack_string": stack_string,
            "wl_range": (
                self._get_float_safe("wl_range_start", 1200.0),
                self._get_float_safe("wl_range_end", 1700.0),
            ),
            "wl_step": self._get_float_safe("wl_step", 0.2),
            "scan_wl_min": self._get_float_safe("scan_wl_min", 1200.0),
            "scan_wl_max": self._get_float_safe("scan_wl_max", 1700.0),
            "scan_wl_step": self._get_float_safe("scan_wl_step", 2.0),
            "dynamics_threshold": self._get_float_safe("dynamics_threshold", 0.025),
            "min_transmission_floor": self._get_float_safe("min_transmission_floor", 0.10),
            "strict_min_transmission_floor": True,
            "enforce_best_strategy_tmin_check": True,
            "min_spectral_resolution": self._get_float_safe("min_spectral_resolution", 1.0),
            "mc_runs_block": int(self._get_float_safe("mc_runs_block", 100)),
            "iter_divider_start": self._get_float_safe("iter_divider_start", 10.0),
            "iter_divider_end": self._get_float_safe("iter_divider_end", 3.0),
            "screening_mc_runs": int(self._get_float_safe("screening_mc_runs", 20)),
            "screening_keep_top_k": int(self._get_float_safe("screening_keep_top_k", 5)),
            "strategy_phase_timeout": self._get_float_safe("strategy_phase_timeout", 120.0),
            "reality_sim_params": {
                "trigger_tolerance": self._get_float_safe("trigger_tolerance", 0.1),
                "noise_distribution": NOISE_DISTRIBUTION_GAUSSIAN,
            },
            "thickness_tolerance_nm": self._get_float_safe("thickness_tolerance_nm", 1.0),
            "mse_tolerance_limit_pct": self._get_float_safe("mse_tolerance_limit_pct", 30.0),
            # Legacy/Fallback if needed (hidden from GUI by default now if we remove it, but user might have it in old logical flow)
            "sim_thickness_probe_offset_ratio": 80.0,  # Hardcoded fallback or self._get_float_safe("sim_thickness_probe_offset_ratio", 80.0),
            "non_monotonic_error_factor": self._get_float_safe("non_monotonic_error_factor", 2.0),
            "non_monotonic_mode": NON_MONOTONIC_MODE_REJECT
            if self.widgets.get("non_monotonic_mode") and self.widgets["non_monotonic_mode"].currentText() == "reject"
            else NON_MONOTONIC_MODE_ATTENUATE,
            "wavelength_change_penalty": self._get_float_safe("wavelength_change_penalty", 1.2),
            "robustness_noise_factors": noise_factors,
            "robustness_num_runs": int(self._get_float_safe("robustness_num_runs", 150)),
            "nucleation_mc_runs": int(self._get_float_safe("nucleation_mc_runs", 40)),
            "mining_candidates_limit": int(self._get_float_safe("mining_candidates_limit", 3000)),
            "n_screen_runs": int(self._get_float_safe("n_screen_runs", 25)),
            "k_keep_survivors": int(self._get_float_safe("k_keep_survivors", 10)),
            "top_k_parents": int(self._get_float_safe("top_k_parents", 20)),
            "max_fusions_per_parent": int(self._get_float_safe("max_fusions_per_parent", 5)),
            "phase_a_scan_limit": int(self._get_float_safe("phase_a_scan_limit", 300)),
            "phase_a_keep_limit": int(self._get_float_safe("phase_a_keep_limit", 50)),
            "nucleation_max_rmse": self._get_float_safe("nucleation_max_rmse", 1.5),
            "nucleation_degradation": self._get_float_safe("nucleation_degradation", 1.4),
            "step0_sigma": self._get_float_safe("step0_sigma", 1.0),
            "show_plots": True,
            "export_excel": True,
            "extrema_exclusion_ratio": self._get_float_safe("extrema_exclusion_ratio", 60.0),
            "logger": self.logger,
            "materials_db": self.materials_db,
            "force_first_layer_same_wl": True,
            "include_secondary_rmse_stats": bool(self._get_float_safe("include_secondary_rmse_stats", 0)),
            "keep_full_mc_top_k": int(self._get_float_safe("keep_full_mc_top_k", 30)),
            "robustness_seed": int(self._get_float_safe("robustness_seed", 42)),
            "phase_a_seed": int(self._get_float_safe("phase_a_seed", self._get_float_safe("robustness_seed", 42))),
            "sym_enable": True,
            "sym_weight": self._get_float_safe("sym_weight", SYM_DEFAULT_WEIGHT),
            "sym_same_wl_bonus": self._get_float_safe("sym_same_wl_bonus", SYM_DEFAULT_SAME_WL_BONUS),
            "sym_extrema_window": self._get_float_safe("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT),
            "sym_continuity_weight": self._get_float_safe("sym_continuity_weight", SYM_DEFAULT_CONTINUITY_WEIGHT),
            "sym_adaptive_same_wl": bool(self._get_float_safe("sym_adaptive_same_wl", 1.0) > 0.5),
            "sym_allow_hybrid": bool(self._get_float_safe("sym_allow_hybrid", 0.0) > 0.5),
            "sym_prefer_on_tie": bool(self._get_float_safe("sym_prefer_on_tie", 1.0) > 0.5),
            "sym_tie_epsilon": self._get_float_safe("sym_tie_epsilon", SYM_DEFAULT_TIE_EPS_ABS),
            "sym_tie_epsilon_rel": self._get_float_safe("sym_tie_epsilon_rel", SYM_DEFAULT_TIE_EPS_REL),
            "sym_scoring_mode": (
                self.widgets["sym_scoring_mode"].currentText()
                if self.widgets.get("sym_scoring_mode")
                else SYM_DEFAULT_SCORING_MODE
            ),
            "enable_consensus_ranking": bool(self._get_float_safe("enable_consensus_ranking", 1.0) > 0.5),
            "consensus_num_seeds": int(self._get_float_safe("consensus_num_seeds", 3)),
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "consensus_seed_stride": int(self._get_float_safe("consensus_seed_stride", 1)),
            "consensus_top_k": int(self._get_float_safe("consensus_top_k", 12)),
            "consensus_num_runs": int(self._get_float_safe("consensus_num_runs", 150)),
            "consensus_std_weight": self._get_float_safe("consensus_std_weight", 0.35),
            "consensus_score_mode": "mean_std",
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "execution_mode": (
                self.widgets["execution_mode"].currentText().strip().lower()
                if self.widgets.get("execution_mode")
                else "premium"
            ),
            "fast_auto_blocks": True,
        }

        if params_out.get("execution_mode", "premium") == "fast":
            # Fast profile: ~4x lower compute budget for interactive iteration.

            params_out["mc_runs_block"] = max(25, int(params_out["mc_runs_block"] / 4))

            params_out["n_screen_runs"] = max(6, int(params_out["n_screen_runs"] / 4))

            params_out["screening_mc_runs"] = max(6, int(params_out["screening_mc_runs"] / 3))

            params_out["nucleation_mc_runs"] = max(30, int(params_out["nucleation_mc_runs"] / 3))

            params_out["robustness_num_runs"] = max(40, int(params_out["robustness_num_runs"] / 4))

            params_out["consensus_num_runs"] = max(40, int(params_out["consensus_num_runs"] / 4))

            params_out["consensus_num_seeds"] = min(
                int(params_out.get("consensus_num_seeds", 3)),
                2,
            )

            params_out["consensus_top_k"] = max(12, int(params_out.get("consensus_top_k", 12) / 2))

            params_out["elite_rounds"] = 1

            params_out["elite_max_candidates"] = 60

            params_out["elite_max_full_evals"] = 16

            params_out["keep_full_mc_top_k"] = max(10, int(params_out["keep_full_mc_top_k"] / 2))

        return params_out

    def run_workflow(self, step: int | StratTask) -> None:
        """Launch a workflow task in a background WorkerThread.

        Accepts either a legacy integer (0, 2, 3, 23) or a ``StratTask`` enum
        member.  Integer values are normalised to ``StratTask`` immediately so
        that all internal comparisons use the semantic enum — **never** raw
        magic numbers.

        Call sites (button connections) continue to pass integers for
        backwards compatibility; the conversion here is the single source
        of truth for the mapping.
        """
        self._reports_exported = False

        # -- Normalise the step argument to a StratTask enum member.
        # Legacy integers (0, 2, 3, 23) are still accepted from button
        # connections; the WorkerThread constructor also handles them, but
        # we convert early so every branch below uses the semantic name.
        _INT_TO_TASK = {
            0: StratTask.NOMINAL_ANALYSIS,
            2: StratTask.STRATEGY_SEARCH,
            3: StratTask.ROBUSTNESS_EVALUATION,
            23: StratTask.FULL_PIPELINE,
            33: StratTask.EXTERNAL_EVALUATION,
        }
        if not isinstance(step, StratTask):
            task = _INT_TO_TASK.get(step, StratTask.NOMINAL_ANALYSIS)
        else:
            task = step

        # CLEANUP PREVIOUS WORKER

        if hasattr(self, "worker") and self.worker is not None:
            if self.worker.isRunning():
                self.worker.quit()

                if not self.worker.wait(2000):
                    self.logger.critical(
                        "Worker did not stop within 2s in run_workflow - skipping terminate() to avoid unsafe thread kill."
                    )

            self.worker = None

        try:
            params = self.collect_params()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error collecting parameters: {e}")

            return

        exec_mode = str(params.get("execution_mode", "premium")).lower()

        if exec_mode == "fast":
            self.logger.info(
                "[MODE] FAST active | robustness_num_runs=%s | consensus_num_runs=%s | n_screen_runs=%s | mc_runs_block=%s | elite_rounds=%s | fast_auto_blocks=%s",
                params.get("robustness_num_runs"),
                params.get("consensus_num_runs"),
                params.get("n_screen_runs"),
                params.get("mc_runs_block"),
                params.get("elite_rounds", 1),
                params.get("fast_auto_blocks", True),
            )

        else:
            self.logger.info("[MODE] PREMIUM active")

        self.logger.info("=" * 80)
        self.logger.info("STARTING WORKFLOW: %s (%s)", task.name, task.value)
        self.logger.info("=" * 80)

        # New run: allow live monitor to re-open normally (unless user closes again).

        if getattr(self, "live_monitor_window", None) is not None:
            try:
                self.live_monitor_window.user_hidden = False

            except (RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        for btn in [
            self.run_step0_btn,
            self.run_step2_btn,
            self.run_step3_btn,
            self.run_full_btn,
            self.load_strat_btn,
        ]:
            btn.setEnabled(False)

        # Enable "Stop & Proceed" only for tasks that run the optimisation engine.
        if task in (StratTask.STRATEGY_SEARCH, StratTask.FULL_PIPELINE):
            self.stop_step2_btn.setEnabled(True)

            self.stop_step2_btn.setText("⏩ Stop & Proceed")

            params["stop_requested"] = False

        else:
            self.stop_step2_btn.setEnabled(False)

        self.progress_bar.setValue(0)

        if task != StratTask.NOMINAL_ANALYSIS:
            self.status_label.setText("Running Phase 1 (prerequisite)...")

            self.logger.info("AUTO-RUNNING PHASE 1: Nominal Calculation (Prerequisite)")

        else:
            self.status_label.setText("Running Phase 1 (Nominal)...")

        self.worker = WorkerThread(
            step=task,
            params=params,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger if task == StratTask.FULL_PIPELINE else None,
        )
        self._register_worker_thread(self.worker, f"STRAT-{task.name.lower()}")

        self.worker.signals.update_live_growth.connect(self.on_live_growth_update)

        self.worker.signals.update_stats.connect(self.on_stats_update)

        self.worker.signals.finished.connect(self.on_workflow_finished)

        self.worker.signals.error.connect(self.on_workflow_error)

        self.worker.signals.progress.connect(self.on_progress_update)

        self.worker.signals.plot.connect(self.on_plot_ready)

        self.worker.signals.excel_ready.connect(self.on_excel_ready)

        try:
            self.worker.signals.show_strategies_table.disconnect(self.on_show_strategies_table)
        except (TypeError, RuntimeError):
            pass
        self.worker.signals.show_strategies_table.connect(self.on_show_strategies_table)

        _SPECTRUM_COUNTER.set_signal(self.worker.signals)

        _SPECTRUM_COUNTER.reset()

        self.worker.start()

    def on_workflow_finished(self, results) -> None:
        self.logger.info("[DEBUG-UI] on_workflow_finished started. Results keys: %s", list(results.keys()) if isinstance(results, dict) else "not a dict")

        if "opti_results" in results:
            self.opti_results = results["opti_results"]

            self.run_step3_btn.setEnabled(True)

        if "final_results" in results:
            self.final_results = results["final_results"]

            self.logger.info("Step 3 complete.")

            try:
                final_strategies = list((self.final_results or {}).get("all_strategies_results", []) or [])
                if not final_strategies:
                    raise RuntimeError("CERTUS-STRAT-E-FINAL-TABLE-MISSING: no strategies available for final ranking display")
                self.logger.debug(
                    "[STRAT-UI] Forcing final ranking table display: count=%d",
                    len(final_strategies),
                )
                self.on_show_strategies_table(final_strategies)
                if not (self.strategies_table_window and self.strategies_table_window.isVisible()):
                    raise RuntimeError("CERTUS-STRAT-E-FINAL-TABLE-NOT-VISIBLE: final ranking table failed to show")
            except Exception as exc:
                self.logger.error("[STRAT-UI] Final ranking table display failed: %s", exc, exc_info=True)
                QMessageBox.critical(
                    self,
                    "CERTUS-STRAT Final Ranking Error",
                    f"The final ranking table could not be displayed.\n\nError code: {exc}",
                )
                raise

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        if self.opti_results:
            self.run_step3_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)

        self.load_strat_btn.setEnabled(True)

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.stop_step2_btn.setText("⏩ Stop & Proceed")

        self.status_label.setText("Complete")

        self.progress_bar.setValue(100)

        # Self-export (Excel + HTML) if enabled via HUB

        if get_export_config() and self.opti_results:
            self.logger.info("[DEBUG-UI] Scheduling auto-export results in 500ms.")
            QTimer.singleShot(500, self._auto_export_results)
        else:
            self.logger.info("[DEBUG-UI] Auto-export not scheduled (config=%s, opti_results=%s).", get_export_config(), bool(self.opti_results))

    def on_workflow_error(self, exc_info) -> None:

        exc_type, exc_value, exc_tb = exc_info

        self.logger.error(f"Workflow error:\n{''.join(traceback.format_exception(exc_type, exc_value, exc_tb))}")

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        if self.opti_results:
            self.run_step3_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)

        self.load_strat_btn.setEnabled(True)

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.status_label.setText("Error occurred")

        self.progress_bar.setValue(0)

    def on_progress_update(self, value: int, message: str) -> None:

        self.progress_bar.setValue(value)

        self.status_label.setText(message)

    def on_plot_ready(self, fig: Any, fig_type: str) -> None:
        self.logger.debug(
            "[SPY-PLOT-READY] on_plot_ready entered: fig_type=%s | fig_id=%s | thread=%s",
            fig_type, id(fig), QThread.currentThread().objectName() or str(id(QThread.currentThread()))
        )

        if fig_type == "pyqtgraph_heatmap":
            try:
                if hasattr(self, "heatmap_window") and self.heatmap_window:
                    self.logger.debug("[SPY-PLOT-READY] Closing existing heatmap window.")
                    self.heatmap_window.close()

                self.logger.debug(
                    "[STRAT-UI] on_plot_ready(heatmap) fig_type=%s queue_size=%d plot_windows=%d",
                    fig_type,
                    self.plot_queue.qsize() if hasattr(self.plot_queue, "qsize") else -1,
                    len(self.plot_windows),
                )

                self.heatmap_window = InteractiveHeatmapWindow(self, fig)

                # Keep a strong reference before show(): the heatmap may be emitted
                # from a worker path where the event loop turn matters.
                self.plot_windows.append(self.heatmap_window)
                self.logger.debug("[STRAT-UI] heatmap_window stored id=%s plot_windows=%d", id(self.heatmap_window), len(self.plot_windows))

                self.heatmap_window.show()

                self.heatmap_window.raise_()

                self.heatmap_window.activateWindow()

                return

            except (RuntimeError, AttributeError) as e:
                self.logger.warning("[STRAT-UI] heatmap immediate creation failed: %s", e, exc_info=True)
                # Fallback to standard queue if immediate creation is not possible.

                pass

        self.logger.debug("[SPY-PLOT-READY] Putting plot into queue: fig_type=%s | queue_size_before=%d", fig_type, self.plot_queue.qsize())
        self.plot_queue.put((fig, fig_type))

    def _resolve_manifest_seed(self, seed_container: Any) -> int | None:
        if not isinstance(seed_container, dict):
            return None
        for _k in (
            "seed",
            "random_seed",
            "robustness_seed",
            "phase_a_seed",
            "ensemble_seed",
        ):
            _v = seed_container.get(_k)
            if _v is None:
                continue
            try:
                return int(_v)
            except (TypeError, ValueError):
                continue
        return None

    def _manifest_source_paths(self) -> list[str]:
        paths: list[str] = []
        cfg_path = str(getattr(self, "_last_config_file", "") or "").strip()
        if cfg_path:
            paths.append(cfg_path)
        try:
            db_path = str(_resolve_strat_indices_db_path() or "").strip()
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            db_path = ""
        if db_path:
            paths.append(db_path)
        return list(dict.fromkeys(paths))

    def on_excel_ready(self, excel_data: io.BytesIO, metadata: Dict) -> Any:
        """Handle automatic export (Excel + HTML)"""
        self.logger.debug("[DEBUG-UI] on_excel_ready entered.")

        try:
            try:
                params_for_status = metadata.get("params", {}) if isinstance(metadata, dict) else {}
                if params_for_status.get("seed") is None and params_for_status.get("random_seed") is None:
                    self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                    self.add_validation_warning(
                        "STRAT run uses stochastic stages without explicit seed in exported params."
                    )
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("Validation status update skipped during export: %s", exc)

            report_dir = get_resource_path("reports")

            os.makedirs(report_dir, exist_ok=True)

            rmse_val = float(metadata.get("rmse", metadata.get("rmse_p95", metadata.get("rmse_mean", 0.0))))

            timestamp = certus_timestamp_file()

            try:
                src_name = ""

                if hasattr(self, "_last_config_file") and self._last_config_file:
                    src_name = "_" + Path(self._last_config_file).stem

                base_name = f"Report_STRAT{src_name}_{timestamp}_RMSE_{rmse_val:.5f}"

            except (ValueError, TypeError, AttributeError):
                base_name = f"Report_STRAT_{timestamp}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")

            html_path = str(Path(report_dir) / f"{base_name}.html")

            manifest_payload_source: dict[str, Any] = self.opti_results or {}
            try:
                params_for_manifest = self.collect_params()
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: manifest_payload_source)
                manifest_dict = svc.fit({
                    "config": {"module": "CERTUS_STRAT", "params": params_for_manifest},
                    "source_paths": self._manifest_source_paths(),
                    "seed": self._resolve_manifest_seed(params_for_manifest),
                    "app_id": "CERTUS_STRAT",
                    "app_version": __version__,
                    "warnings": list(getattr(self, "validation_warnings", []) or []),
                    "status": status_val.value if isinstance(status_val, ValidationStatus) else str(status_val),
                }).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT manifest generation failed: %s", exc)
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.logger.error(
                    "STRAT export blocked: incomplete manifest (missing: %s)",
                    ", ".join(missing_manifest_fields),
                )
                if hasattr(self, "status_label"):
                    self.status_label.setText("Export blocked: incomplete manifest")
                return

            # 1. Save Excel
            self.logger.info("[DEBUG-UI] Saving Excel report...")

            with open(excel_path, "wb") as f:
                f.write(excel_data.getvalue())
            if manifest_dict:
                try:
                    import openpyxl

                    wb_m = openpyxl.load_workbook(excel_path)
                    if "Manifest" in wb_m.sheetnames:
                        del wb_m["Manifest"]
                    ws_m = wb_m.create_sheet("Manifest")
                    ws_m.append(["Key", "Value"])
                    for k, v in manifest_dict.items():
                        ws_m.append([str(k), str(v)])
                    wb_m.save(excel_path)
                except (ImportError, OSError, ValueError, TypeError, RuntimeError) as exc:
                    self.logger.warning("STRAT manifest Excel sheet injection skipped: %s", exc)
                try:
                    manifest_path = str(Path(report_dir) / f"{base_name}.manifest.json")
                    with open(manifest_path, "w", encoding="utf-8") as mf:
                        json.dump(manifest_dict, mf, ensure_ascii=False, indent=2)
                except (OSError, ValueError, TypeError) as exc:
                    self.logger.warning("STRAT manifest JSON write skipped: %s", exc)

            self.logger.info("✅ Excel report saved: %s", excel_path)

            # 2. Generate HTML Report
            self.logger.info("[DEBUG-UI] Saving HTML report...")

            # Gather plots from GUI if available

            figures = []

            if hasattr(self, "plot_stack"):
                figures.append(self.plot_stack)

            if hasattr(self, "plot_spectrum"):
                figures.append(self.plot_spectrum)

            # Create sections

            params = metadata.get("params", {})

            sections = [
                {
                    "title": "Strategy Optimization Summary",
                    "type": "kv",
                    "content": {
                        "Strategies Found": str(metadata.get("strategies_count", 0)),
                        "Best RMSE": f"{rmse_val:.5f}",
                        "Wavelength Range": f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                        "Target Layers": f"{params.get('n_target_layers', '?')}",
                    },
                }
            ]

            # Insert Methodology and Details before Summary

            methodology_sections = [
                {
                    "title": "Monitoring Methodology",
                    "type": "kv",
                    "content": {
                        "Strategy Search": "Hybrid (Dynamic Programming + Stochastic)",
                        "Monitoring Type": "Monochromatic Optical Monitoring (Single Wave/Block)",
                        "Error Compensation": "Active (Real-time Re-optimization)",
                        "Simulation Engine": "Monte Carlo (Robustness Validation)",
                    },
                },
                {
                    "title": "Simulation Details",
                    "type": "text",
                    "content": (
                        "The strategy generation uses a <strong>Hybrid Dynamic Programming</strong> approach to find the optimal layer cutting sequence. "
                        "It simulates <strong>Monochromatic Optical Monitoring</strong> (Turning/Trigger Points) with real-time error compensation, ensuring that "
                        "the designed strategy is robust against deposition errors. The final validation is performed using a "
                        "<strong>Monte Carlo</strong> engine to estimate production yield."
                    ),
                },
            ]

            all_sections = methodology_sections + sections

            if generate_html_report(html_path, "CERTUS-STRAT Report", all_sections, figures):
                self.logger.info("✅ HTML report saved: %s", html_path)
                self._reports_exported = True

            self.status_label.setText(f"✓ Saved: {base_name}")
            self.logger.info("[DEBUG-UI] on_excel_ready completed successfully.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error("❌ Error during auto-export: %s", e, exc_info=True)

    def _write_export_excel(
        self,
        strats: list,
        rmse_val: float,
        excel_path: str,
        report_dir: str,
        manifest_dict: dict,
        base_name: str,
    ) -> None:
        """Build the auto-export Excel workbook (Summary + Top Strategies + Best
        Structure + Layer Extrema + optional Manifest sheet) and write it to
        ``excel_path``. Also persist the manifest as a side-car JSON next to it
        under ``report_dir``. Behavior is preserved bit-for-bit from the legacy
        inline implementation."""
        params = self.collect_params()

        t_exec = f"{self.opti_results.get('execution_time', 0):.2f}" if "execution_time" in self.opti_results else "N/A"

        n_cores = str(get_safe_worker_count())

        n_iter = "N/A"

        df_summary = pd.DataFrame(
            {
                "Parameter": [
                    "Date",
                    "High Index (H)",
                    "Low Index (L)",
                    "substrate",
                    "Target Layers",
                    "Scan Range",
                    "Nucleation WL",
                    "Execution Time (s)",
                    "Processors",
                    "Iterations",
                    "Best RMSE",
                ],
                "Value": [
                    certus_timestamp_display(),
                    params.get("nH", "N/A"),
                    params.get("nL", "N/A"),
                    params.get("substrate", "N/A"),
                    str(params.get("n_target_layers", "N/A")),
                    f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                    f"{params.get('l0', 'N/A')} nm",
                    t_exec,
                    n_cores,
                    n_iter,
                    f"{rmse_val:.6f}",
                ],
            }
        )

        strategies_data = []
        for s in strats[:20]:
            if not isinstance(s, dict):
                continue
            strat = s.get("strategy", {})
            if not isinstance(strat, dict):
                continue
            strategies_data.append(
                {
                    "ID": strat.get("strategy_id", ""),
                    "RMSE": s.get("rmse", 0),
                    "Robustness": s.get("robustness_score", 0),
                    "Blocks": strat.get("n_blocks", 0),
                    "Blocks Def": str(strat.get("blocks", [])),
                }
            )

        df_strategies = pd.DataFrame(strategies_data)
        df_structure = pd.DataFrame()
        df_extrema = pd.DataFrame()

        if strats and isinstance(strats[0], dict) and isinstance(strats[0].get("strategy"), dict):
            best = strats[0]["strategy"]
            blocks = best["blocks"]

            struct_data = []
            for i, b in enumerate(blocks):
                struct_data.append(
                    {
                        "Block #": i + 1,
                        "Monitoring WL": b.get("wavelength", 0),
                        "Layer Start Index": b["start"],
                        "Layer End Index": b["end"],
                    }
                )
            df_structure = pd.DataFrame(struct_data)

            ext_data = []
            for i, dists in enumerate(best.get("extrema_distances", [])):
                layer_prof = {}
                if i < len(best.get("theoretical_layer_profile", [])):
                    layer_prof = best["theoretical_layer_profile"][i]

                def fmt(v) -> Any:
                    if v > 15.0:
                        return "not critical"
                    return f"{v:.1f}"

                extrema_items = layer_prof.get("Textrema", [])
                extrema_summary = ", ".join(
                    [
                        f"{e.get('type', '?')}@{float(e.get('d_nm', 0.0)):.1f}nm:{float(e.get('T', 0.0)) * 100:.2f}%"
                        for e in extrema_items[:8]
                    ]
                )
                if len(extrema_items) > 8:
                    extrema_summary += f", ... +{len(extrema_items) - 8}"
                ext_data.append(
                    {
                        "Layer": i + 1,
                        "Tinit (%)": f"{float(layer_prof.get('Tinit', np.nan)) * 100:.3f}" if layer_prof else "",
                        "Tfinal (%)": f"{float(layer_prof.get('Tfinal', np.nan)) * 100:.3f}" if layer_prof else "",
                        "Textrema (summary)": extrema_summary,
                        "Start - Prev Extremum (OT nm)": fmt(dists.get("prev_start", 999.0)),
                        "Start - Next Extremum (OT nm)": fmt(dists.get("next_start", 999.0)),
                        "End - Prev Extremum (OT nm)": fmt(dists.get("prev_end", 999.0)),
                        "End - Next Extremum (OT nm)": fmt(dists.get("next_end", 999.0)),
                    }
                )
            if ext_data:
                df_extrema = pd.DataFrame(ext_data)

        if OPENPYXL_AVAILABLE:
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                df_summary.to_excel(writer, sheet_name="Summary", index=False)
                if not df_strategies.empty:
                    df_strategies.to_excel(writer, sheet_name="Top_Strategies", index=False)
                if not df_structure.empty:
                    df_structure.to_excel(writer, sheet_name="Best_Structure", index=False)
                if not df_extrema.empty:
                    df_extrema.to_excel(writer, sheet_name="Layer_Extrema", index=False)
                if manifest_dict:
                    pd.DataFrame([{"Key": str(k), "Value": str(v)} for k, v in manifest_dict.items()]).to_excel(
                        writer, sheet_name="Manifest", index=False
                    )
            self.logger.info(f"✅ Rich Excel saved: {Path(excel_path).name}")
        else:
            to_excel_robust(df_summary, excel_path)
            self.logger.info(f"✅ Simple Excel saved (openpyxl missing): {Path(excel_path).name}")

        if manifest_dict:
            try:
                manifest_path = str(Path(report_dir) / f"{base_name}.manifest.json")
                with open(manifest_path, "w", encoding="utf-8") as mf:
                    json.dump(manifest_dict, mf, ensure_ascii=False, indent=2)
            except (OSError, ValueError, TypeError) as exc:
                self.logger.warning("STRAT manifest JSON write skipped: %s", exc)

    def _write_export_html(
        self,
        strats: list,
        rmse_val: float,
        html_path: str,
    ) -> None:
        """Build the auto-export HTML report (overview, methodology, top
        strategies and inline figures) and write it to ``html_path``. Behavior
        is preserved bit-for-bit from the legacy inline implementation."""
        params = self.collect_params()

        sections = [
            {
                "title": "Strategy Optimization Summary",
                "type": "kv",
                "content": {
                    "Best RMSE": f"{rmse_val:.5f}",
                    "Target Layers": str(params.get("n_target_layers", "N/A")),
                    "Wavelength Range": f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                    "Nucleation WL": f"{params.get('l0', 'N/A')} nm",
                    "High Index Material": params.get("nH", "N/A"),
                    "Low Index Material": params.get("nL", "N/A"),
                    "substrate": params.get("substrate", "N/A"),
                    "Execution Time": (
                        f"{self.opti_results.get('execution_time', 0):.2f} s"
                        if "execution_time" in self.opti_results
                        else "N/A"
                    ),
                    "Processors": str(get_safe_worker_count()),
                    "Iterations": "N/A",
                },
            }
        ]

        methodology_sections = [
            {
                "title": "Monitoring Methodology",
                "type": "kv",
                "content": {
                    "Strategy Search": "Hybrid (Dynamic Programming + Stochastic)",
                    "Monitoring Type": "Monochromatic Optical Monitoring (Single Wave/Block)",
                    "Error Compensation": "Active (Real-time Re-optimization)",
                    "Simulation Engine": "Monte Carlo (Robustness Validation)",
                },
            },
            {
                "title": "Simulation Details",
                "type": "text",
                "content": (
                    "The strategy generation uses a <strong>Hybrid Dynamic Programming</strong> approach to find the optimal layer cutting sequence. "
                    "It simulates <strong>Monochromatic Optical Monitoring</strong> (Turning/Trigger Points) with real-time error compensation, ensuring that "
                    "the designed strategy is robust against deposition errors. The final validation is performed using a "
                    "<strong>Monte Carlo</strong> engine to estimate production yield."
                ),
            },
        ]

        all_sections = methodology_sections + sections

        if strats:
            top_strategies = strats[:10]
            table_data = []
            for s in top_strategies:
                strat = s.get("strategy", {})
                if not isinstance(strat, dict):
                    continue
                blocks_fmt = ", ".join([f"{b['start']:.0f}-{b['end']:.0f}" for b in strat.get("blocks", [])[:3]])
                if len(strat.get("blocks", [])) > 3:
                    blocks_fmt += "..."
                table_data.append(
                    {
                        "ID": strat["strategy_id"],
                        "Blocks Count": strat.get("n_blocks", 0),
                        "Structure (nm)": blocks_fmt,
                        "RMSE Score": f"{float(s.get('rmse_p95', s.get('rmse_mean', s.get('rmse', 0.0)))):.5f}",
                        "Robustness": f"{float(s.get('robustness_score', 0.0)):.5f}",
                    }
                )
            if table_data:
                all_sections.append(
                    {
                        "title": "Top Performing Strategies",
                        "type": "table",
                        "content": table_data,
                    }
                )

        figures = []
        if hasattr(self, "plot_stack") and self.plot_stack:
            figures.append(self.plot_stack)
        if hasattr(self, "plot_spectrum") and self.plot_spectrum:
            figures.append(self.plot_spectrum)

        if generate_html_report(html_path, "CERTUS-STRAT Report", all_sections, figures):
            self.logger.info(f"✅ HTML saved: {Path(html_path).name}")

    def _auto_export_results(self) -> Any:
        """Self-export results without worker signal"""
        self.logger.info("[DEBUG-UI] _auto_export_results started.")

        if getattr(self, "_reports_exported", False):
            self.logger.info("Reports already exported via excel_ready signal - skipping duplicate self-export.")
            return

        if not self.opti_results:
            self.logger.warning("[DEBUG-UI] self.opti_results is empty/None in _auto_export_results. Aborting.")
            return

        try:
            try:
                params_for_status = self.collect_params()
                if params_for_status.get("seed") is None and params_for_status.get("random_seed") is None:
                    self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                    self.add_validation_warning("STRAT auto-export run uses stochastic stages without explicit seed.")
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT auto-export validation status update skipped: %s", exc)

            report_dir = get_resource_path("reports")

            os.makedirs(report_dir, exist_ok=True)

            # Get RMSE from the actual best-ranked strategy/result.
            # Older payloads may keep placeholder 0.0 in the first item, so we must
            # search for the first finite positive score instead of blindly using index 0.
            # The RMSE used for export naming must stay an error metric, not a robustness score.

            strats = []

            if hasattr(self, "final_results") and isinstance(self.final_results, dict):
                strats = list(self.final_results.get("all_strategies_results", []))

            if not strats and "strategies_results" in self.opti_results:
                strats = list(self.opti_results.get("strategies_results", []))

            rmse_val = extract_best_rmse(strats)

            timestamp = certus_timestamp_file()

            try:
                src_name = ""

                if hasattr(self, "_last_config_file") and self._last_config_file:
                    src_name = "_" + Path(self._last_config_file).stem

                base_name = f"Report_STRAT{src_name}_{timestamp}_RMSE_{rmse_val:.5f}"

            except (ValueError, TypeError, AttributeError):
                base_name = f"Report_STRAT_{timestamp}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")

            html_path = str(Path(report_dir) / f"{base_name}.html")

            self.logger.info("Saving reports...")

            manifest_dict: dict[str, Any] = {}
            try:
                params_for_manifest = self.collect_params()
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: self.opti_results or {})
                manifest_dict = svc.fit({
                    "config": {"module": "CERTUS_STRAT", "params": params_for_manifest},
                    "source_paths": self._manifest_source_paths(),
                    "seed": self._resolve_manifest_seed(params_for_manifest),
                    "app_id": "CERTUS_STRAT",
                    "app_version": __version__,
                    "warnings": list(getattr(self, "validation_warnings", []) or []),
                    "status": status_val.value if isinstance(status_val, ValidationStatus) else str(status_val),
                }).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT auto-export manifest generation failed: %s", exc)
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.logger.error(
                    "STRAT auto-export blocked: incomplete manifest (missing: %s)",
                    ", ".join(missing_manifest_fields),
                )
                if hasattr(self, "status_label"):
                    self.status_label.setText("Export blocked: incomplete manifest")
                return

            # 1. EXCEL EXPORT

            try:
                self.logger.info("[DEBUG-UI] Writing Excel report...")
                self._write_export_excel(strats, rmse_val, excel_path, report_dir, manifest_dict, base_name)
                self.logger.info("[DEBUG-UI] Excel report written successfully.")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Excel export failed:{e}")

            # 2. HTML EXPORT

            try:
                self.logger.info("[DEBUG-UI] Writing HTML report...")
                self._write_export_html(strats, rmse_val, html_path)
                self.logger.info("[DEBUG-UI] HTML report written successfully.")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"HTML export failed:{e}", exc_info=True)

            self.status_label.setText(f"✓ Saved: {base_name}")
            self.logger.info("[DEBUG-UI] _auto_export_results completed.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"❌ Self-export error:{e}", exc_info=True)

    def on_show_strategies_table(self, strategies_results: list[dict[str, Any]]) -> None:

        self.logger.info(
            "[STRAT-UI] on_show_strategies_table called: count=%d refreshing=%s current_window=%s visible=%s worker_running=%s worker_alive=%s",
            len(strategies_results),
            getattr(self, "_strategies_table_refreshing", False),
            bool(getattr(self, "strategies_table_window", None)),
            bool(getattr(self, "strategies_table_window", None) and self.strategies_table_window.isVisible()),
            bool(getattr(self, "worker", None) and self.worker.isRunning()),
            bool(getattr(self, "worker", None)),
        )

        if getattr(self, "_strategies_table_refreshing", False):
            self.logger.info("[STRAT-UI] Ignoring table refresh because a refresh is already in progress.")
            return

        self._strategies_table_refreshing = True
        try:
            current_p_thick = []

            include_secondary_rmse_stats = False

            try:
                include_secondary_rmse_stats = bool(self.collect_params().get("include_secondary_rmse_stats", False))

            except (KeyError, TypeError, ValueError):
                include_secondary_rmse_stats = False

            if self.opti_results and "p_thick_nominal" in self.opti_results:
                current_p_thick = self.opti_results["p_thick_nominal"]

            if not current_p_thick:
                try:
                    params = self.collect_params()

                    nominal_res, _ = calculate_nominal_properties(params)

                    current_p_thick = nominal_res["physical_thicknesses_nominal"]

                except (KeyError, TypeError, ValueError):
                    current_p_thick = []

            if self.strategies_table_window and self.strategies_table_window.isVisible():
                self.strategies_table_window.p_thick_nominal = np.array(current_p_thick, dtype=np.float64)

                self.strategies_table_window.include_secondary_rmse_stats = include_secondary_rmse_stats

                self.strategies_table_window.update_data(strategies_results)

            else:
                if self.strategies_table_window:
                    self.strategies_table_window.close()

                self.strategies_table_window = StrategiesTableWindow(
                    self,
                    strategies_results,
                    current_p_thick,
                    include_secondary_rmse_stats=include_secondary_rmse_stats,
                )

                self.strategies_table_window.strategy_selected.connect(self.on_strategy_visualization_requested)

                self.logger.info("[STRAT-UI] StrategiesTableWindow created and connected; show() now.")
                self.strategies_table_window.show()
        finally:
            self._strategies_table_refreshing = False

    def on_strategy_visualization_requested(self, row_idx: int, strategy_result: dict[str, Any]) -> None:
        # SAFETY — worker.isRunning() guard
        # -----------------------------------------------------------------------
        # BUG HISTORY: Calling worker.isRunning() without a try/except crashed the
        # app with RuntimeError when the underlying C++ QThread object had already
        # been destroyed by Qt's garbage collector, even though the Python reference
        # was still alive.
        # RULE: Always wrap QThread / QObject attribute access in try/except
        # RuntimeError when the object lifetime is managed by Qt (not Python).
        # DO NOT simplify this to a plain `if worker is not None` check — it is
        # insufficient because the C++ peer can be deleted while the Python wrapper
        # still exists.
        # -----------------------------------------------------------------------
        worker = getattr(self, "worker", None)
        worker_running = False
        if worker is not None:
            try:
                worker_running = worker.isRunning()
            except RuntimeError:
                worker_running = False

        self.logger.info(
            "[STRAT-UI] on_strategy_visualization_requested row=%s strategy_id=%s current_windows=%d plot_windows=%d worker_running=%s worker_alive=%s",
            row_idx,
            strategy_result.get("strategy", {}).get("strategy_id", "unknown"),
            len(self.transmission_windows),
            len(self.plot_windows),
            worker_running,
            bool(worker),
        )

        try:
            strategy = strategy_result["strategy"]

            if not self.opti_results:
                # Rebuild a minimal context so detail windows remain available

                # even after a workflow error that occurred after table emission.

                try:
                    params_boot = self.collect_params()

                    nominal_results, _ = calculate_nominal_properties(params_boot)

                    p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

                    clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                        params_boot, p_thick_nominal, self.logger
                    )

                    self.opti_results = {
                        "p_thick_nominal": p_thick_nominal,
                        "clues_at_wl": clues_at_wl,
                        "nominal_matrix_cache": nominal_matrix_cache,
                        "all_wls": all_wls,
                    }

                    self.logger.info("ℹ️ Visualization context rebuilt after workflow error.")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.warning(f"Cannot visualize - opti_results is empty ({e})")

                    return

            self.logger.info(
                f"\n{'=' * 80}\nVISUALIZING STRATEGY #{strategy['strategy_id']} (Rank {row_idx + 1})\n{'=' * 80}"
            )
            self.logger.info(
                "[STRAT-UI] transmission_windows(before_cleanup)=%d strategy_has_results=%s detailed_growth=%s",
                len(self.transmission_windows),
                bool(strategy_result.get("results_per_noise")),
                "detailed_growth_data" in strategy_result,
            )

            # Robust cleanup of stale Qt window references before opening new detail windows.

            alive_windows = []

            for w in self.transmission_windows:
                try:
                    if w is not None and w.isVisible():
                        alive_windows.append(w)

                except RuntimeError:
                    continue

            self.transmission_windows = alive_windows

            try:
                params = self.collect_params()

                trans_win = TransmissionVsThicknessWindow(self, strategy_result, self.opti_results, params)

                self.transmission_windows.append(trans_win)

                self.logger.info(
                    "[STRAT-UI] Growth window instance created id=%s parent=%s list_size=%d plot_windows=%d",
                    id(trans_win),
                    type(trans_win.parent()).__name__ if trans_win.parent() else None,
                    len(self.transmission_windows),
                    len(self.plot_windows),
                )

                trans_win.show()

                trans_win.move(100, 100)

                self.logger.info("✓ Growth window opened")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"✗ Failed to open growth window: {e}", exc_info=True)

            try:
                params = self.collect_params()

                spec_win = StrategySpectralPerformanceWindow(self, strategy_result, self.opti_results, params)

                self.transmission_windows.append(spec_win)

                self.logger.info(
                    "[STRAT-UI] Spectral window instance created id=%s parent=%s list_size=%d plot_windows=%d",
                    id(spec_win),
                    type(spec_win.parent()).__name__ if spec_win.parent() else None,
                    len(self.transmission_windows),
                    len(self.plot_windows),
                )

                spec_win.show()

                spec_win.move(150, 150)

                self.logger.info("✓ Spectral window opened")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"✗ Failed to open spectral window: {e}", exc_info=True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error in visualization: {e}", exc_info=True)

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

    def process_plot_queue(self) -> None:

        plot_queue = self.plot_queue

        if plot_queue is None:
            return

        if plot_queue.qsize() == 0:
            return

        self.logger.info("[SPY-PROCESS-QUEUE] process_plot_queue starting. Queue size=%d", plot_queue.qsize())
        try:
            while True:
                try:
                    data_obj, fig_type = plot_queue.get_nowait()
                    self.logger.info("[SPY-PROCESS-QUEUE] Retrieved plot from queue: fig_type=%s | fig_id=%s", fig_type, id(data_obj))

                except queue.Empty:
                    break

                if fig_type == "clues_check_plot":
                    try:
                        if hasattr(self, "clues_window") and self.clues_window:
                            self.clues_window.close()

                        self.logger.info(
                            "[STRAT-UI] process_plot_queue(clues) plot_windows=%d queue_size=%d",
                            len(self.plot_windows),
                            plot_queue.qsize() if hasattr(plot_queue, "qsize") else -1,
                        )

                        self.clues_window = InteractiveIndicesWindow(self, data_obj)

                        self.plot_windows.append(self.clues_window)
                        self.clues_window.show()
                        self.logger.info("[STRAT-UI] clues_window opened id=%s plot_windows=%d", id(self.clues_window), len(self.plot_windows))

                    except (RuntimeError, AttributeError) as e:
                        logging.getLogger("CERTUS").warning("[STRAT-UI] clues plot creation failed: %s", e, exc_info=True)

                    continue

                if fig_type == "pyqtgraph_heatmap":
                    try:
                        if hasattr(self, "heatmap_window") and self.heatmap_window:
                            self.heatmap_window.close()

                        self.logger.info(
                            "[STRAT-UI] process_plot_queue(heatmap) plot_windows=%d queue_size=%d",
                            len(self.plot_windows),
                            plot_queue.qsize() if hasattr(plot_queue, "qsize") else -1,
                        )

                        self.heatmap_window = UniversalPlotWindow(self, data_obj, "pyqtgraph_heatmap")

                        self.plot_windows.append(self.heatmap_window)
                        self.heatmap_window.show()
                        self.logger.info("[STRAT-UI] heatmap_window opened id=%s plot_windows=%d", id(self.heatmap_window), len(self.plot_windows))

                    except (RuntimeError, AttributeError) as e:
                        logging.getLogger("CERTUS").warning("[STRAT-UI] heatmap plot creation failed: %s", e, exc_info=True)

                    continue

                if fig_type == "main_spectral_interactive":
                    try:
                        win = InteractiveSpectrumWindow(self, data_obj, sigma=data_obj.get("sigma", None))

                        win.show()

                        if not hasattr(self, "interactive_spectrum_windows"):
                            self.interactive_spectrum_windows = []

                        self.interactive_spectrum_windows.append(win)

                    except (RuntimeError, AttributeError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    continue

                if fig_type == "main_spectral":
                    self.update_main_plot(data_obj)

                elif fig_type == "stack_visual":
                    self.update_stack_plot(data_obj)

                else:
                    self.logger.info(
                        "[STRAT-UI] process_plot_queue(%s) plot_windows=%d queue_size=%d",
                        fig_type,
                        len(self.plot_windows),
                        plot_queue.qsize() if hasattr(plot_queue, "qsize") else -1,
                    )
                    plot_win = UniversalPlotWindow(self, data_obj, fig_type)

                    # Keep a strong reference so the window survives the event loop turn
                    # that follows the queued plot emission from Phase B.
                    self.plot_windows.append(plot_win)
                    self.logger.info("[STRAT-UI] queued plot window stored type=%s id=%s plot_windows=%d", fig_type, id(plot_win), len(self.plot_windows))

                    plot_win.show()

                    plot_win.raise_()

                    plot_win.activateWindow()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error processing plot queue: {e}", exc_info=True)

    # === OPTIMIZATION: Hashed & Async Plot Update ===

    def _compute_fig_hash(self, fig: Any) -> str:

        try:
            return self._plot_cache.get_hash(fig)

        except (TypeError, AttributeError):
            return str(time.time())

    def update_main_plot(self, fig: Any, force_render: bool = False) -> None:

        try:
            target_w = max(100, self.main_plot_widget.width())

            target_h = max(100, self.main_plot_widget.height())

            plot_hash = self._compute_fig_hash(fig)

            active_thread = getattr(self, "_active_render_thread", None)
            is_active_running = active_thread.isRunning() if active_thread else False
            self.logger.info(
                "[STRAT-UI] update_main_plot(hash=%s force=%s size=%dx%d active_thread=%s running=%s rendering=%d)",
                str(plot_hash)[:32],
                force_render,
                target_w,
                target_h,
                id(active_thread) if active_thread else "None",
                is_active_running,
                len(getattr(self, "_rendering_plots", set())),
            )

            # 1. Check Cache

            with self._cache_lock:
                cached_pix = self._plot_cache.get(plot_hash)

                if cached_pix and not force_render:
                    self.logger.info("[STRAT-UI] update_main_plot cache hit -> applying cached pixmap.")
                    self._apply_pixmap(cached_pix)

                    return

                if plot_hash in self._rendering_plots:
                    self.logger.info("[STRAT-UI] update_main_plot already rendering -> skipped.")
                    return  # Already rendering

            # 2. Async Render

            self._rendering_plots.add(plot_hash)
            self.logger.info("[STRAT-UI] update_main_plot starting async render (hash=%s).", str(plot_hash)[:32])

            # Start Worker Thread

            thread = QThread(self)

            worker = PlotRenderWorker(fig, target_w, target_h, plot_hash)

            worker.moveToThread(thread)

            thread.started.connect(worker.run)

            worker.finished.connect(self._on_render_complete)

            worker.finished.connect(thread.quit)

            worker.finished.connect(worker.deleteLater)

            thread.finished.connect(lambda: self._on_render_thread_finished(thread, plot_hash))

            # Keep ref to prevent GC while the async render is running

            self._active_render_thread = thread

            thread.start()
            self.logger.info("[STRAT-UI] update_main_plot thread started (running=%s).", thread.isRunning())

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Plot Dispatch Error: {e}", exc_info=True)

    def _on_render_thread_finished(self, thread: QThread, plot_hash: Any) -> None:
        self.logger.info("[STRAT-UI] render thread finished hash=%s", str(plot_hash)[:32])
        if getattr(self, "_active_render_thread", None) == thread:
            self._active_render_thread = None
        if not hasattr(self, "_stopping_threads"):
            self._stopping_threads = []
        self._stopping_threads.append(thread)
        thread.deleteLater()

    @pyqtSlot(bytes, str)
    def _on_render_complete(self, png_bytes, plot_hash) -> None:

        try:
            self.logger.info("[STRAT-UI] _on_render_complete(hash=%s bytes=%d)", str(plot_hash)[:32], len(png_bytes))
            pix = QPixmap()

            pix.loadFromData(png_bytes)

            with self._cache_lock:
                self._plot_cache.put(plot_hash, pix)

                self._rendering_plots.discard(plot_hash)

            self._apply_pixmap(pix)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error applying render: {e}", exc_info=True)

            with self._cache_lock:
                self._rendering_plots.discard(plot_hash)

    def _apply_pixmap(self, pixmap) -> None:

        self.logger.info("[STRAT-UI] _apply_pixmap(size=%dx%d)", pixmap.width(), pixmap.height())
        self.main_plot_widget.setPixmap(pixmap)

        self.main_plot_widget.setScaledContents(True)

        if self.plot_stack.currentWidget() != self.main_plot_widget:
            self.plot_stack.setCurrentWidget(self.main_plot_widget)

    # ===============================================

    def update_stack_plot(self, fig) -> None:

        if hasattr(self, "stack_visual_window") and self.stack_visual_window:
            self.stack_visual_window.close()

        try:
            # Replaced dedicated StackStructureWindow with UniversalPlotWindow for consistency

            self.stack_visual_window = UniversalPlotWindow(self, fig, "stack_visual")

            self.stack_visual_window.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Failed to update stack plot: {e}")

    @pyqtSlot(dict)
    def on_live_growth_update(self, live_data) -> None:
        self.logger.info(f"[DEBUG-UI] on_live_growth_update received live_data! Keys: {list(live_data.keys()) if live_data else []}")
        try:
            if not isinstance(live_data, dict):
                raise ValueError("CERTUS-STRAT-E-LIVE-DATA: live_data must be a dict")

            block_number = live_data.get("block_number", live_data.get("n_blk", "?"))
            best_strategy = live_data.get("best_strategy", live_data.get("strategy"))
            best_score = live_data.get("best_robustness_score", live_data.get("robustness_score"))
            status = live_data.get("status", "ok")

            if best_strategy is None:
                raise ValueError(
                    f"CERTUS-STRAT-E-LIVE-STRATEGY-MISSING: block={block_number} status={status}"
                )
            if best_score is None:
                raise ValueError(f"CERTUS-STRAT-E-LIVE-SCORE-MISSING: block={block_number} status={status}")

            self.logger.info(f"[STRAT-UI] Block {block_number}: best strategy ready. Robustness score: {float(best_score):.6f}")

            if self.live_monitor_window is None:
                self.live_monitor_window = LiveMonitorWindow(None)  # No parent to avoid sub-window rendering
                set_certus_window_icon(self.live_monitor_window)

            # Respect explicit user close: do not auto-reopen during current run.
            if getattr(self.live_monitor_window, "user_hidden", False):
                return

            if not self.live_monitor_window.isVisible():
                self.live_monitor_window.show()
                self.live_monitor_window.raise_()
                self.live_monitor_window.activateWindow()

            strategy = best_strategy
            blocks = strategy.get("blocks", [])

            p_thick_nominal = np.array(live_data["p_thick_nominal"], dtype=np.float64)
            clues_db = live_data["clues_at_wl"]
            num_layers = len(p_thick_nominal)
            layer_wls = np.zeros(num_layers, dtype=np.float64)

            # [FIX 2026] Complex clues for coherent detailed growth (absorption in TMM)
            nH_arr = np.zeros(num_layers, dtype=np.complex128)
            nL_arr = np.zeros(num_layers, dtype=np.complex128)
            nSub_arr = np.zeros(num_layers, dtype=np.complex128)

            # Fallback values
            default_idx = {
                "H": complex(2.3),
                "L": complex(1.45),
                "substrate": complex(1.52),
            }

            for block in blocks:
                wl = float(block["wavelength"])
                # We try to get data (can be a dict or a worker)
                try:
                    idx_data = clues_db[wl]
                except (KeyError, TypeError):
                    idx_data = default_idx
                # COMMON.SharedIndicesWorker returns "substrate" as standard key
                n_s = idx_data.get("substrate", default_idx["substrate"])
                for l in range(block["start"], block["end"]):
                    if l < num_layers:
                        layer_wls[l] = wl
                        nH_arr[l] = idx_data.get("H", default_idx["H"])
                        nL_arr[l] = idx_data.get("L", default_idx["L"])
                        n_s_val = complex(n_s)
                        # [FIX 2026-03] Guard: n_sub < 1.001 is physically impossible
                        if n_s_val.real < 1.001:
                            logging.warning(
                                f"[Live] n_sub={n_s_val:.4f} at {wl}nm - using fallback {default_idx['substrate']}"
                            )
                            n_s_val = default_idx["substrate"]
                        nSub_arr[l] = n_s_val

            steps = np.full(num_layers, 30, dtype=np.int32)
            x, y, bounds = calculate_detailed_growth(
                num_layers, p_thick_nominal, layer_wls, nH_arr, nL_arr, nSub_arr, steps
            )
            score = float(best_score)

            self.live_monitor_window.update_monitor(
                x,
                y,
                bounds,
                f"LIVE MONITORING: {strategy.get('n_blocks')} BLOCKS | Robustness: {score:.5f}",
                blocks,
            )

        except Exception as e:
            self.logger.error(f"[GUI] Error in on_live_growth_update: {e}", exc_info=True)
            QMessageBox.critical(self, "CERTUS-STRAT Live Strategy Error", f"A live strategy popup/update failed.\n\n{e}")

    def _stop_all_threads_parallel(self, timeout_ms: int = 10000) -> None:
        """Stop main worker, active render thread, and auxiliary threads in parallel."""
        thread_worker_pairs = []

        main_worker = getattr(self, "worker", None)
        if main_worker is not None:
            thread_worker_pairs.append((main_worker, main_worker))
            try:
                if hasattr(main_worker, "params") and isinstance(main_worker.params, dict):
                    main_worker.params["stop_requested"] = True
            except (RuntimeError, AttributeError):
                pass

        render_thread = getattr(self, "_active_render_thread", None)
        if render_thread is not None:
            thread_worker_pairs.append((render_thread, None))

        for thread in getattr(self, "_active_worker_threads", []):
            if thread is not None:
                thread_worker_pairs.append((thread, None))

        active_pairs = []
        for t, w in thread_worker_pairs:
            try:
                if t.isRunning():
                    active_pairs.append((t, w))
            except RuntimeError:
                pass

        if not active_pairs:
            return

        self.logger.debug("[STRAT-UI] Stopping %d active threads in parallel...", len(active_pairs))

        for t, w in active_pairs:
            try:
                t.quit()
            except RuntimeError:
                pass

        deadline = time.time() + (timeout_ms / 1000.0)
        for t, w in active_pairs:
            try:
                remaining = max(0, int((deadline - time.time()) * 1000))
                if t.isRunning() and remaining > 0:
                    if not t.wait(remaining):
                        self.logger.warning("[STRAT-UI] Thread id=%s did not stop in time, requesting interruption...", id(t))
                        t.requestInterruption()
                        t.wait(min(remaining, 1000))
            except RuntimeError:
                pass

        if main_worker is not None and not main_worker.isRunning():
            self.worker = None
        if render_thread is not None and not render_thread.isRunning():
            self._active_render_thread = None
        self._active_worker_threads = [t for t in getattr(self, "_active_worker_threads", []) if t is not None and t.isRunning()]

    def closeEvent(self, event) -> None:

        try:
            # Stop all running computation/render threads in parallel to avoid sequential timeouts on exit
            self._stop_all_threads_parallel(timeout_ms=10000)

            if getattr(self, "_log_timer_id", None) is not None:
                self.killTimer(self._log_timer_id)

            if getattr(self, "plot_timer", None) is not None:
                self.killTimer(self.plot_timer)

            self.close_all_auxiliary_windows()

            if hasattr(self, "materials_db"):
                self.materials_db.clear_cache()

            self.logger.info("Application closed.")

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        finally:
            event.accept()

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
