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

class CertusStratEventsMixin:
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

    def timerEvent(self, event) -> None:
        log_timer_id = getattr(self, "_log_timer_id", -1)
        plot_timer_id = getattr(self, "plot_timer", -1)

        if event.timerId() == log_timer_id:
            self._process_log_queue()

        elif event.timerId() == plot_timer_id:
            self.process_plot_queue()

        else:
            super().timerEvent(event)

    def on_toggle_details(self, checked) -> None:

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

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

    def _on_material_mode_changed(self, prefix, label) -> None:
        """Enable/disable widgets based on Custom vs Dispersive selection."""

        is_custom = self.widgets[f"{prefix}_type_custom"].isChecked()

        self.widgets[f"n{label}_r"].setEnabled(is_custom)

        self.widgets[f"{prefix}_material_file"].setEnabled(not is_custom)

    def _on_substrate_choice_changed(self, text) -> None:
        """Enable custom index field only when 'Custom' substrate is selected."""

        is_custom = text == "Custom"

        self.widgets["nSub_custom"].setEnabled(is_custom)

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

