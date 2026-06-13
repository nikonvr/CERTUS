from certus.core.certus_core import __version__, APP_SUITE_VERSION
import os
from pathlib import Path
import multiprocessing
import sys
import functools
from certus.core.certus_core import create_module_environment
import logging
import time
import traceback
import copy
from threading import Event
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg
from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QThread,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CFG,
    ensure_numpy_array,
    get_complex_dtype,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)
from certus.utils.errors import safe_ui_action
from certus.workers.certus_design_worker_utils import (
    build_pglobal_optimizer,
    build_pglobal_config_from_cfg,
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_post_optim_time_budget_seconds,
    optim_prepare_stack_nk_back,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    prepare_pglobal_inputs_from_state,
    prepare_pglobal_optimizer_runtime,
    run_coord_descent_5cycles,
    run_pglobal_restart_loop,
)
from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)
from certus_physics import (  # Cache & Utils; Gradient Logic (Analytic); Numba Functions
    Layer,
    Material,
    ObliqueTarget,
    PGlobalConfig,
    PGlobalOptimizer,
    Target,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_gradient_contrib_analytic,
    cost_numba_fast,
    delta_e_2000,
    init_thickness,
    lab_to_rgb,
    needle_scan_cached,
    prepare_targets_vectorized,
    xyz_from_spectrum,
    xyz_to_lab,
)
from certus.utils.certus_index_utils import spectral_rmse_weights
from certus.ui.certus_ui import (
    CertusTheme,
    CertusBaseApp,
    CertusScientificPlot,
    CertusThemeToggle,
    CertusCard,
    CertusCollapsible,
    CertusStatusPill,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    EnhancedProgressWidget,
    FlashyCard,
    WelcomeGuideWidget,
    WorkerSignals,
    certus_get_save_file_name,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    create_flashy_grid,
    create_header_logo_widget,
    create_top_actions_bar,
    get_export_config,
    init_certus_app,
    open_documentation,
    plot_widget_plot_finite,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker
from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)
from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)
from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *
from certus.ui.mixins.certus_design_plot_mixin import CertusDesignUIPlotMixin

class CertusDesignWorkerMixin:
    def run_eval(self) -> None:
        """

        Runs spectral evaluation of the current design.

        This method performs complete spectral evaluation including:

        - JIT compilation warmup check

        - Material and stack validation

        - Target configuration setup

        - Worker thread initialization and execution

        - Result processing and visualization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs evaluation progress and timing

            - Handles both normal and oblique modes

            - Emits progress signals during execution

            - Updates UI components with results

        """

        _eval_start = time.time()

        if not spectrum_eval_run_preamble(self, self.run_eval):
            return

        cfg = spectrum_eval_build_worker_cfg(self, "design")

        if cfg is None:
            return

        spectrum_eval_start_worker(self, cfg, _eval_start)

    def _on_eval_finished(self, data: Dict, generation_id: int | None = None) -> None:
        """

        Callback after spectral evaluation completion.

        This method processes evaluation results including:

        - Result data storage and validation

        - Visualization data processing

        - Plot updates and UI refresh

        - Performance timing and logging

        Args:

            self: CertusDesign instance

            data: Evaluation result dictionary with spectral data

        Returns:

            None

        Notes:

            - Logs evaluation completion and timing

            - Handles both normal and oblique modes

            - Updates UI components with results

            - Stores results for subsequent operations

        """

        _finish_start = time.time()

        data_for_display = spectrum_eval_on_finished_prepare_display(self, data, generation_id)

        if data_for_display is None:
            return

        self.last_result = data_for_display

        # Self-export if pending (triggered by Case C or time budget completion)

        if getattr(self, "_export_pending", False):
            self._export_pending = False

            QTimer.singleShot(100, self.export_results)

        res_vis = data_for_display["vis"]

        res_optim = data_for_display["optimization"]

        oblique_mode = data_for_display.get("oblique_mode", False)

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        plot_targets = self._get_plot_targets("spectrum", self.spectrum_plot)

        spectrum_eval_plot_curves(
            self,
            data_for_display=data_for_display,
            plot_targets=plot_targets,
            res_vis=res_vis,
            res_optim=res_optim,
            oblique_mode=oblique_mode,
        )

        rmse = data_for_display.get("rmse")

        n_points = self.points_per_target_spin.value()

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | {src_name} | Points/Target: {n_points} ({n_total} total)"

            else:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        if optim_rmse_is_valid_for_log(rmse):
            title += f" - RMSE: {optim_rmse_display_string(rmse)}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self, res_vis=res_vis, oblique_mode=oblique_mode)

        self._plot_profile(
            data_for_display["ep"],
            self._get_front_stack(),
            data_for_display.get("ep_back"),
            self._get_back_stack(),
        )

        self._plot_nk()

        logging.info("[DESIGN._on_eval_finished] completed callback | elapsed_ms=%.1f", (time.time() - _finish_start) * 1000)

        self.log(
            f"Evaluation OK. RMSE: {optim_rmse_display_string(rmse)}"
            if optim_rmse_is_valid_for_log(rmse)
            else "Evaluation OK.",
            "SUCCESS",
        )

        self._set_busy(False)

        logging.info("[DESIGN._on_eval_finished] evaluation cycle complete | ui_ready=True")

        # Systematic Pareto update after any evaluation (manual edit or optimization)

        # data["ep"] and data["rmse"] are available from EvalWorker

        self._update_pareto_record(data_for_display.get("ep"), data_for_display.get("rmse"))

    @safe_ui_action
    def run_optim(self, mode: str, keep_history: bool = False, **kwargs) -> None:
        """

        Start an optimization cycle.

        logger = getattr(self, "logger", None)
        if logger:
            logger.info(
                "DESIGN run_optim enter | mode=%s | keep_history=%s | kwargs_keys=%s",
                mode,
                bool(keep_history),
                ",".join(sorted(map(str, kwargs.keys()))) if kwargs else "-",
            )

        Entry point for the hybrid design workflow. Three optimization modes

        are available, each with different search scope and bounds:

        - ``'global'``: Full PGLOBAL stochastic search over [0, 1.2×QWOT].

          Used for initial design exploration with HPO-tuned hyperparameters.

        - ``'healing'``: Restricted PGLOBAL search within +/-Deltad of current

          thicknesses, where Deltad = lambda₀/(10·n) per layer (~40% QWOT).

          Triggered automatically after smart_cleanup removes layers.

        - ``'local'``: Narrow L-BFGS-B refinement within +/-2 nm.

          Used for final polish and intra-needle-cycle optimization.

        The complete automated workflow is::

            Global PGLOBAL

            -> smart_cleanup (remove <1nm, merge adjacent)

            -> Healing (restricted global +/-Deltad + local polish)

            -> Needle insertion loop (Overshoot +20%)

            -> Prune thinnest layers back to target

            -> Final local polish

            -> Complete

        This method performs optimization including:

        - Mode-specific parameter setup and bounds

        - Target validation and configuration

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusDesign instance

            mode: Optimization mode: ``'global'``, ``'healing'``, or ``'local'``

            keep_history: If False (default), resets all workflow state for fresh start.

                       If True, preserves state for internal continuation.

        Returns:

            None

        Notes:

            - Logs optimization progress and results

            - Emits progress signals during execution

            - Handles different optimization modes automatically

            - Supports both fresh start and continuation modes

        """

        # Logging start

        active_mode = "oblique" if self.oblique_mode else "normal"
        active_targets = [t for t in (self._get_oblique_tgts() if self.oblique_mode else self._get_tgts()) if t.valid()]

        logging.info(
            "[DESIGN.start_optimization] starting optimization | mode=%s | keep_history=%s | active_targets=%d | samples_per_iter=%s | max_iterations=%s",
            mode,
            keep_history,
            len(active_targets),
            self.n100_spin.value(),
            self.global_cycles_spin.value(),
        )
        logging.info(
            "[DESIGN.start_optimization] incidence configuration | incidence=%s | active_targets=%d",
            active_mode,
            len(active_targets),
        )

        self._shutdown_previous_optim_worker()

        # INTERNAL RESTART MANAGEMENT

        self._is_internal_restart = keep_history

        # Guard: if user clicked STOP, refuse internal restarts

        if keep_history and getattr(self, "_workflow_stopped", False):
            self.log("Workflow stopped by user, ignoring internal restart.", "WARNING")

            self._set_busy(False)

            return

        if not keep_history:
            self._reset_run_optim_workflow_state(mode)

        else:
            self.log(f"Continuing optimization ({mode})...", "INFO")

        stack, mats, active, ep0, wls = self._collect_run_optim_inputs()
        if stack is None:
            return

        # Calculate limits with 20% margin for display

        wls_min = self._calculate_wls_min_with_margin(active)

        wls_max = self._calculate_wls_max_with_margin(active)

        # Configuration

        if mode == "local":
            cfg = {
                "mode": "local",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": CFG.MAX_FEVAL_LOCAL,
                "n100": 50,
                "max_iter": 10,
                "local_delta_nm": 2.0,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        elif mode == "healing":
            cfg = {
                "mode": "healing",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": 10000,
                "n100": 500,
                "max_iter": 8,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        else:
            pre_polish = False

            if hasattr(self, "pre_polish_check"):
                pre_polish = self.pre_polish_check.isChecked()

            # If needle growth is enabled, use ultra-fast global (just seed)

            # Needle will iterate and refine - no need for exhaustive global

            allow_growth = getattr(self, "allow_growth_check", None)

            needle_coupled = allow_growth and allow_growth.isChecked()

            if needle_coupled:
                g_max_feval = min(CFG.MAX_FEVAL_GLOBAL, 50000)

                g_n100 = min(self.n100_spin.value(), 1500)

                g_max_iter = min(self.global_cycles_spin.value(), 8)

                g_max_clusters = min(self.max_clusters_spin.value(), 5)

                self.log(
                    "Global+Needle: ultra-fast global (seed for needle iterations)",
                    "INFO",
                )

            else:
                g_max_feval = CFG.MAX_FEVAL_GLOBAL

                g_n100 = self.n100_spin.value()

                g_max_iter = self.global_cycles_spin.value()

                g_max_clusters = self.max_clusters_spin.value()

            cfg = {
                "mode": "global",
                "pre_polish": pre_polish,
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": g_max_feval,
                "n100": g_n100,
                "max_iter": g_max_iter,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "max_clusters": g_max_clusters,
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        # Start Worker

        self._set_busy(True)

        self._initialize_run_optim_progress_state(cfg, keep_history)

        if kwargs:
            cfg.update(kwargs)

        self.optim_worker = OptimWorker(cfg)

        # Carry best RMSE across internal restarts so GUI doesn't regress

        if keep_history and hasattr(self, "_workflow_best_rmse"):
            self.optim_worker.best_rmse_seen = self._workflow_best_rmse

        self.optim_thread = QThread()
        self.optim_worker.moveToThread(self.optim_thread)

        self.optim_thread.started.connect(self.optim_worker.run)

        self.optim_worker.signals.finished.connect(self.optim_thread.quit)
        self.optim_worker.signals.finished.connect(self._on_optim_done)
        self.optim_worker.signals.finished.connect(self.optim_worker.deleteLater)

        self.optim_worker.signals.error.connect(self.optim_thread.quit)
        self.optim_worker.signals.error.connect(self._on_error)
        self.optim_worker.signals.error.connect(self.optim_worker.deleteLater)

        self.optim_worker.signals.result.connect(self._on_intermediate_spectrum)

        self.optim_worker.signals.progress.connect(self._on_optim_progress)

        self.optim_worker.signals.update_stats.connect(self._on_stats_update)

        self.optim_thread.finished.connect(self.optim_thread.deleteLater)

        self.optim_thread.start()

    def _on_optim_progress(self, val: int, msg: str) -> None:
        """Callback for optimization progress update"""

        # val is PERCENTAGE (0-100) from OptimWorker

        # msg format: "Gen X | Evals: Y | Clusters: Z | Best: W"

        self._optim_current_iter = val

        # Extract "Gen X" for display

        gen_info = "Gen ?"

        if "Gen" in msg:
            try:
                gen_info = msg.split("|")[0].strip()

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

        # Update progress widget

        self.progress_widget.update(
            iteration=getattr(self, "_optim_current_iter", val),
            max_iter=getattr(self, "_optim_max_iter", 100),
            evals=getattr(self, "_optim_n_evals", 0),
            phase="PGLOBAL",
            extra_info=(f"{gen_info} | RMSE: {msg.split('Best:')[-1].strip()}" if "Best:" in msg else ""),
        )

        # Also update status label and log

        self.status_label.setText(msg)

        self.log(msg, "INFO")

    def _on_stats_update(self, stat_name: str, value: int) -> None:
        """Callback for stats update (MINIMA, EVAL, COLOR)"""

        if stat_name == "EVAL":
            self._optim_n_evals = value

            display_value = value + getattr(self, "accumulated_evals", 0)

            # Update progress widget with new eval count

            self.progress_widget.update(
                iteration=getattr(self, "_optim_current_iter", 0),
                max_iter=getattr(self, "_optim_max_iter", 100),
                evals=display_value,
                phase="PGLOBAL",
            )

        # Update stats label

        current = self.stats_label.text()

        if stat_name == "MINIMA":
            parts = current.split("|")

            if len(parts) >= 1:
                parts[0] = f"♟️ {value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "EVAL":
            display_value = value + getattr(self, "accumulated_evals", 0)

            parts = current.split("|")

            if len(parts) >= 2:
                parts[1] = f" 🎲 {display_value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "COLOR":
            parts = current.split("|")

            if len(parts) >= 3:
                parts[2] = f" 🌈️ {value}"

            self.stats_label.setText("|".join(parts))

    def _on_optim_done(self, d) -> None:
        return getattr(self, 'orchestrator', self)._on_optim_done(d)

    @safe_ui_action
    def run_colorimetry(self) -> None:
        """

        Start colorimetric analysis of the current design.

        This method performs color analysis including:

        - Color coordinate calculationation (CIE XYZ, LAB)

        - Monte Carlo simulation for color variation

        - Visualization of color properties

        - Analysis of color stability under thickness variations

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires previous evaluation results

            - Switches to color plot view

            - Uses Monte Carlo simulation for robustness

            - Emits progress updates during analysis

        """

        if not self.last_result:
            self.log("Please evaluate first.", "WARNING")

            return

        if self.viz_stack.currentIndex() == 0:
            self.viz_stack.setCurrentIndex(1)

        self.plot_tabs.setCurrentWidget(self.color_plot)

        self.log("Running colorimetric analysis...", "INFO")

        mats = self._get_materials()

        stack = self._get_front_stack()

        cfg = {
            "ep": self.last_result["ep"],
            "stack": stack,
            "mats": mats,
            "n": self.mc_n_spin.value(),
            "sigma": self.mc_sigma_spin.value(),
            "l0": self.l0_spin.value(),
        }

        self._set_busy(True)

        self.col_worker = ColorWorker(cfg)

        self.col_thread = QThread()
        self.col_worker.moveToThread(self.col_thread)

        self.col_thread.started.connect(self.col_worker.run)

        self.col_worker.signals.finished.connect(self.col_thread.quit)
        self.col_worker.signals.finished.connect(self._on_col_done)
        self.col_worker.signals.finished.connect(self.col_worker.deleteLater)

        self.col_worker.signals.error.connect(self.col_thread.quit)
        self.col_worker.signals.error.connect(self._on_error)
        self.col_worker.signals.error.connect(self.col_worker.deleteLater)

        self.col_thread.finished.connect(self.col_thread.deleteLater)

        self.col_thread.start()

    def _on_col_done(self, d: Dict) -> None:
        """Callback after colorimetric analysis"""

        if d["ok"]:
            nom = d["lab_nom"]

            labs = d["labs"]

            self.color_plot.plotItem.clear()

            plot_widget_plot_finite(
                self.color_plot,
                labs[:, 1],
                labs[:, 2],
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=(180, 180, 180, 100),
                animate=False,
            )

            plot_widget_plot_finite(
                self.color_plot,
                [nom[1]],
                [nom[2]],
                pen=None,
                symbol="star",
                symbolSize=18,
                symbolBrush=CertusTheme.ERROR,
                symbolPen="k",
                animate=False,
            )

            de = [delta_e_2000(nom, l) for l in labs]

            rgb = lab_to_rgb(nom)

            title = (
                f"L*={nom[0]:.1f} a*={nom[1]:.1f} b*={nom[2]:.1f} | "
                f"RGB({rgb[0]},{rgb[1]},{rgb[2]}) | "
                f"DeltaE*00:  μ={np.mean(de):.2f} sigma={np.std(de):.2f}"
            )

            self.color_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="10pt")

            self.log("[DESIGN.colorimetry] analysis complete | status=success", "SUCCESS")

        self._set_busy(False)

    def stop_optim(self) -> None:
        """Stop the current optimization and clean all workflow state.

        Terminates any running OptimWorker or NeedleWorker, then resets

        all internal state variables (overshoot, healing phase, needle

        cycle) to prevent stale state from interfering with subsequent

        optimizations.

        Sets _workflow_stopped flag to prevent pending QTimer callbacks

        from restarting the workflow after this method returns.

        """

        if not confirm_stop_with_timeout(self):
            return

        # CRITICAL: Set flag FIRST to block pending QTimer callbacks

        self._workflow_stopped = True

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped by user")

        self.log("Stopping optimization...", "WARNING")

        try:
            if self.optim_thread and self.optim_thread.isRunning():
                if self.optim_worker:
                    self.optim_worker.request_stop()
                self.optim_thread.quit()
        except RuntimeError:
            pass

        try:
            if self.needle_thread and self.needle_thread.isRunning():
                self.needle_thread.requestInterruption()
        except RuntimeError:
            pass

        self._force_idle()

        self._clean_live_curves()

        self._is_internal_restart = False

        # Clean ALL workflow state on user stop

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        self.log("Optimization stopped.", "WARNING")

        # If stale callbacks arrive later, they can still call _set_busy(False) safely.

        # We force UI idle here to avoid sticky "Computing..." state.

        self._force_idle()

