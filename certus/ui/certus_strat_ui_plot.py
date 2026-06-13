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

class CertusStratPlotMixin:
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

            params = self.collect_params()
            growth_data = simulate_detailed_growth_for_ui(
                {"strategy": strategy},
                live_data,
                params,
            )
            x = np.array(growth_data["x"])
            y = np.array(growth_data["y"])
            bounds = np.array(growth_data["boundaries"])
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
                try:
                    params_boot = self.collect_params()
                    self.opti_results = rebuild_visualization_context(params_boot, self.logger)

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

