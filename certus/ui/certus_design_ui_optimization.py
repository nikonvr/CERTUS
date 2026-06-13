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

class CertusDesignOptimizationMixin:
    def _handle_stopped_workflow_result(self, d: Dict) -> None:
        """Finalize UI and keep best result when workflow is manually stopped."""
        self._stack_info_best_ep = None
        self._stack_info_best_rmse = None
        self.log("Workflow stopped by user.", "WARNING")
        self._set_busy(False)

        if d.get("ok", False) and d.get("ep") is not None:
            final_ep = np.asarray(d["ep"]).flatten()
            stack = self._get_front_stack()
            mats = self._get_materials()
            l0 = self.l0_spin.value()
            qw = optim_qwot_values_from_ep_stack(final_ep, stack, mats, l0)
            self._apply_qw_values_to_front_table(qw)
            self.ep_current = final_ep.copy()
            self._update_thickness_display()
            rmse = d.get("rmse", float("inf"))
            if optim_rmse_is_valid_for_log(rmse):
                self._workflow_best_rmse = rmse
                self._update_pareto_record(self.ep_current, rmse)
            rmse_msg = optim_rmse_display_string(rmse)
            self.log(f"Best result kept (RMSE: {rmse_msg}).", "SUCCESS")

        if get_export_config() and self.last_result:
            self._export_pending = True
            QTimer.singleShot(100, self.export_results)

    def _finalize_if_post_optim_budget_exceeded(self) -> bool:
        """Finalize workflow early when post-optimization orchestration exceeds time budget."""

        if getattr(self, "_post_optim_start_time", None) is None:
            self._post_optim_start_time = time.time()

        _n_layers = self.front_table.rowCount()
        _budget = optim_post_optim_time_budget_seconds(_n_layers)
        _elapsed = time.time() - self._post_optim_start_time

        if not (
            _elapsed > _budget
            and (
                hasattr(self, "_needle_cycle_step")
                or getattr(self, "_healing_phase", None) is not None
                or getattr(self, "_overshoot_active", False)
            )
        ):
            return False

        self.log(
            f"Time budget exceeded ({_elapsed:.0f}s > {_budget:.0f}s for {_n_layers} layers). Finalizing.",
            "WARNING",
        )

        self._healing_phase = None
        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)
            self._overshoot_active = False

        if get_export_config():
            self._export_pending = True
        self._schedule_eval(True)
        self.log("Optimization complete (time budget). Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False
        return True

    def _track_and_apply_post_optim_result(self, d: Dict) -> None:
        """Track workflow RMSE state and apply optimized QW values to the table."""
        final_ep = d["ep"]
        rmse_before_cleanup = d.get("rmse", float("inf"))

        if rmse_before_cleanup < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_before_cleanup

        if rmse_before_cleanup is not None and np.isfinite(rmse_before_cleanup) and rmse_before_cleanup >= 0.0:
            prev_gate_rmse = getattr(self, "_needle_recent_best_rmse", float("inf"))
            if rmse_before_cleanup < prev_gate_rmse - 1e-9:
                self._needle_recent_best_rmse = rmse_before_cleanup
                self._needle_no_improve_rounds = 0
            else:
                self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)
        else:
            self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)

        stack = self._get_front_stack()
        mats = self._get_materials()
        l0 = self.l0_spin.value()

        # Keep n4 convention for round-trip consistency with initialization.
        qw = []
        for i, layer in enumerate(stack):
            d_val = final_ep[i] if i < len(final_ep) else 0.0
            mat_obj = mats.get(layer.mat)
            n_val = 1.45
            if mat_obj:
                if hasattr(mat_obj, "n4"):
                    n_val = mat_obj.n4
                elif isinstance(mat_obj, dict):
                    n_val = mat_obj.get("n4", 1.45)
            val = (4.0 * n_val * d_val) / l0 if abs(l0) > 1e-9 else 0.0
            qw.append(val)

        self._apply_qw_values_to_front_table(qw, debug_failures=True)
        self._update_thickness_display()

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _handle_needle_cycle_step3(self, d: Dict) -> bool:
        """Handle Needle step-3 post-optimization logic. Returns True if flow consumed."""
        if not (hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 3):
            return False

        rmse_after_cleanup = d.get("rmse", float("inf"))
        needle_successful = False

        if self._needle_merit_before is not None:
            ok_gain, delta_abs, delta_rel, abs_thresh, rel_thresh = self._needle_gain_is_significant(
                self._needle_merit_before, rmse_after_cleanup
            )
            if ok_gain:
                self.log(
                    f"Needle cycle successful: DeltaRMSE={delta_abs:.6g} ({delta_rel * 100:.2f}%, "
                    f"thresholds abs>={abs_thresh:.6g} or rel>={rel_thresh * 100:.2f}%)",
                    "SUCCESS",
                )
                needle_successful = True
            else:
                self.log(
                    f"Needle cycle: gain too small (DeltaRMSE={delta_abs:.6g}, {delta_rel * 100:.2f}%)",
                    "WARNING",
                )
        else:
            self.log("Needle cycle: no improvement. Aborting needle.", "WARNING")
            self._revert_to_checkpoint()
            return True

        delattr(self, "_needle_cycle_step")
        delattr(self, "_needle_merit_before")

        current_count_after_clean = self.front_table.rowCount()
        last_count = getattr(self, "_last_cycle_layer_count", 0)
        if not hasattr(self, "_needle_stagnation_count"):
            self._needle_stagnation_count = 0

        if current_count_after_clean <= last_count and not needle_successful:
            self._needle_stagnation_count += 1
            self.log(
                f"[DESIGN.needle] stagnation detected | cycle_without_growth={self._needle_stagnation_count}/3 | target_layers={self._target_layer_count}",
                "WARNING",
            )
        else:
            self._needle_stagnation_count = 0

        self._last_cycle_layer_count = current_count_after_clean
        if self._needle_stagnation_count >= 3:
            self.log(
                "[DESIGN.needle] aborted due to stagnation | reason=3 cycles without growth or merit | action=revert_to_checkpoint",
                "ERROR",
            )
            delattr(self, "_needle_stagnation_count")
            if hasattr(self, "_last_cycle_layer_count"):
                delattr(self, "_last_cycle_layer_count")
            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = self._original_target_count
                self._overshoot_active = False
            self._revert_to_checkpoint()
            return True

        if current_count_after_clean < self._target_layer_count and current_count_after_clean < CFG.MAX_LAYERS:
            self.log(
                f"[DESIGN.needle] growth continuing | current_layers={current_count_after_clean} | target_layers={self._target_layer_count} | action=queue_next_cycle",
                "INFO",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            QTimer.singleShot(100, self._start_needle_process)
            return True

        if current_count_after_clean >= self._target_layer_count:
            if getattr(self, "_overshoot_active", False):
                original = self._original_target_count
                self.log(
                    f"Overshoot complete ({current_count_after_clean} layers). Pruning to {original}...",
                    "SUCCESS",
                )
                pruned = self._prune_to_target(original)
                self._overshoot_active = False
                self._overshoot_done = True
                self._target_layer_count = original
                current_rmse = d.get("rmse", float("inf"))
                checkpoint = getattr(self, "_pre_needle_checkpoint", None)
                if checkpoint and current_rmse > checkpoint["rmse"] * 1.02:
                    self.log(
                        f"Overshoot+Prune degraded RMSE ({current_rmse:.6f} > {checkpoint['rmse']:.6f}). Reverting.",
                        "WARNING",
                    )
                    self._revert_to_checkpoint()
                    return True
                if pruned > 0:
                    self.log(f"Pruned {pruned} thinnest layers. Final polish...", "INFO")
                    self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
                    self._post_prune = True
                    QTimer.singleShot(50, functools.partial(self.run_optim, "local", keep_history=True))
                    return True

            self.log(
                f"Deep Needle: Target reached ({self.front_table.rowCount()} layers)",
                "SUCCESS",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            return False

        self.log("Deep Needle: MAX_LAYERS reached", "WARNING")
        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")
        return False

    def _maybe_start_needle_growth(self) -> bool:
        """Start Needle growth/exploration when deficit or stagnation criteria are met."""
        current_count = self.front_table.rowCount()
        allow_growth = self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True
        has_deficit = current_count < self._target_layer_count
        stagnating = getattr(self, "_needle_no_improve_rounds", 0) >= getattr(self, "_needle_gate_no_improve_rounds", 2)
        needs_exploration = (
            allow_growth
            and stagnating
            and not getattr(self, "_overshoot_done", False)
            and not getattr(self, "_overshoot_active", False)
        )
        needs_needle = has_deficit or needs_exploration

        if not (needs_needle and current_count < CFG.MAX_LAYERS):
            return False

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]:
            return False

        if not getattr(self, "_overshoot_active", False) and not getattr(self, "_overshoot_done", False):
            import math

            self._original_target_count = self._target_layer_count
            if self._target_layer_count < CFG.MAX_LAYERS:
                ratio = getattr(self, "_needle_overshoot_ratio", 0.30)
                extra_layers = max(int(math.ceil(self._target_layer_count * ratio)), 4)
                overshoot = min(self._target_layer_count + extra_layers, CFG.MAX_LAYERS)
                self._target_layer_count = overshoot
                self._overshoot_active = True
                self.log(
                    f"Deep Needle Exploration: temporarily growing to {overshoot} layers "
                    f"(Target: {self._original_target_count}, +{extra_layers} extra for flexibility)",
                    "INFO",
                )

        self._pre_needle_checkpoint = {
            "ep": (self.ep_current.copy() if self.ep_current is not None else None),
            "rmse": self._workflow_best_rmse,
            "table": self._save_table_state(),
        }
        self.log(
            f"Checkpoint saved (RMSE={self._workflow_best_rmse:.6f}, {current_count} layers)",
            "INFO",
        )

        deficit = self._target_layer_count - current_count
        self.log(f"Layer deficit ({deficit}). Starting iterative Needle...", "INFO")
        self._start_needle_process()
        return True

    def _handle_decimation_polish_completion(self, d: Dict) -> bool:
        """Route decimation polish completion and bypass standard workflow."""
        if not getattr(self, "_decimation_polishing", False):
            return False

        if "ep" in d:
            self.ep_current = d["ep"].copy()
        rmse = d.get("rmse", getattr(self, "_workflow_best_rmse", float("inf")))
        if rmse < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse
        self._update_thickness_display()
        self._on_decimation_polish_done()
        return True

    def _handle_smart_decimation_followup(self, d: Dict) -> bool:
        """Advance smart decimation polish passes when enabled."""
        if not hasattr(self, "_smart_decimation_step"):
            return False

        polish_pass = getattr(self, "_smart_decimation_polish_pass", 0)
        if polish_pass == 1:
            self._smart_decimation_polish_pass = 2
            self.run_optim("local", keep_history=True)
            return True

        self._smart_decimation_polish_pass = 0
        self._on_smart_decimation_optim_done(d)
        return True

    def _run_post_optim_cleanup(self, d: Dict) -> int:
        """Apply post-prune/cleanup hook and return removed layer count."""
        if getattr(self, "_post_prune", False):
            self._post_prune = False
            self.log(f"Post-prune polish done. RMSE={d.get('rmse', '?')}", "INFO")
            return 0

        if not self._is_in_needle_cycle():
            return self.smart_cleanup(update_target=False)
        return 0

    def _handle_healing_workflow(self, removed: int) -> bool:
        """Drive two-phase healing after cleanup-induced topology changes."""
        if removed > 0 and not self._is_in_needle_cycle():
            self.log(
                f"Smart cleanup removed {removed} layers. Healing (restricted global)...",
                "INFO",
            )
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            self._healing_phase = "global"
            QTimer.singleShot(50, functools.partial(self.run_optim, "healing", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "global":
            self._healing_phase = "local"
            self.log("Healing: local polish...", "INFO")
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "local":
            self._healing_phase = None
        return False

    def _finalize_completed_optimization_workflow(self) -> None:
        """Finalize stable workflow state and trigger final evaluation/export."""
        self._apply_5nm_minimum()  # Hard rule: no layer < 5nm in final design

        # Set export flag BEFORE scheduling eval (eval callback checks this flag)
        if get_export_config():
            self._export_pending = True

        # Force final Pareto update with best RMSE
        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)
        self.log("Optimization complete & Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False

        # PARETO DECIMATION: iteratively remove thinnest layer, re-polish, record
        if not getattr(self, "_decimation_done", False) and self.front_table.rowCount() > 4:
            self._decimation_done = True
            QTimer.singleShot(200, self._start_smart_pareto_decimation)

    def _initialize_smart_decimation_session(self, n_start: int, n_min_target: int) -> None:
        """Initialize and checkpoint Smart Pareto Decimation session state."""
        # Checkpoint the initial best solution to restore at end
        self._smart_deci_origin_ep = self.ep_current.copy()
        self._smart_deci_origin_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        self._smart_deci_origin_table = self._save_table_state()
        self._smart_deci_origin_N = n_start

        self._smart_decimation_start_N = n_start
        self._smart_decimation_min_N = n_min_target
        self._smart_decimation_best_rmse = self._smart_deci_origin_rmse

    def _smart_decimation_remove_and_optimize(self) -> None:
        """One step of smart decimation: remove thinnest layer and re-optimize."""

        current_N = self.front_table.rowCount()

        if self._should_stop_smart_decimation_step(current_N):
            return

        self._smart_decimation_step += 1

        ep = self.ep_current

        if ep is None or len(ep) != current_N:
            self._finish_smart_decimation()

            return

        # Apply 5nm manufacturability filter before recording
        # (layers already < 5nm counted as candidates to remove first)
        thinnest_idx = self._select_smart_decimation_remove_index(ep)

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        rmse_before = getattr(self, "_workflow_best_rmse", float("inf"))

        self.log(
            f"📉 Step {self._smart_decimation_step}: N={current_N}->{current_N - 1}"
            f" | remove layer {thinnest_idx} ({thinnest_mat}, {thinnest_d:.1f}nm)"
            f" | RMSE={rmse_before:.6f}",
            "INFO",
        )

        # Remove the selected layer

        self.front_table.removeRow(thinnest_idx)
        self._apply_smart_decimation_post_removal_state()

        self.run_optim("local", keep_history=True)

    def _apply_smart_decimation_post_removal_state(self) -> None:
        """Apply state updates required after removing one layer during decimation."""
        self._merge_adjacent_layers()
        self._update_layer_count()

        # Rebuild ep_current from table after removal + merge.
        self._update_thickness_display()

        # Reset best RMSE for the new N so local search is unconstrained by old N.
        self._workflow_best_rmse = float("inf")

        # Use double local polish: pass 1 explores, pass 2 tightens convergence.
        self._smart_decimation_polish_pass = 1

    def _should_stop_smart_decimation_step(self, current_n: int) -> bool:
        """Return True when smart decimation should stop at the current step."""
        # Stopping condition: reached N/2 target
        if current_n <= self._smart_decimation_min_N:
            self._finish_smart_decimation()
            return True

        if self._smart_decimation_step >= 50:  # Safety limit
            self.log("Smart decimation: safety limit reached", "WARNING")
            self._finish_smart_decimation()
            return True

        return False

    def _select_smart_decimation_remove_index(self, ep: np.ndarray) -> int:
        """Pick layer index to remove, prioritizing sub-5nm layers."""
        sub5nm = [i for i, d in enumerate(ep) if d < 5.0]
        if sub5nm:
            # Prefer removing a sub-5nm layer over the generic thinnest
            return sub5nm[int(np.argmin([ep[i] for i in sub5nm]))]
        return int(np.argmin(ep))

    def _on_smart_decimation_optim_done(self, data) -> None:
        """Called after local optimization during smart decimation."""

        if not data or "rmse" not in data:
            self.log("Smart decimation: optimization failed", "ERROR")

            self._finish_smart_decimation()

            return

        rmse_after = data["rmse"]

        current_N = self.front_table.rowCount()

        ref_rmse = self._smart_deci_origin_rmse

        self._apply_smart_decimation_optim_result(data, rmse_after)

        # DEGRADATION GUARD: stop if RMSE > 2× initial reference
        if self._abort_on_smart_decimation_degradation(rmse_after, ref_rmse):
            return

        self._record_smart_decimation_candidate(current_N, rmse_after)

        # Continue to next step

        QTimer.singleShot(200, self._smart_decimation_remove_and_optimize)

    def _apply_smart_decimation_optim_result(self, data: Dict[str, Any], rmse_after: float) -> None:
        """Apply optimization payload and refresh best-RMSE tracking."""
        if "ep" in data:
            self.ep_current = data["ep"].copy()
            self._update_thickness_display()

        if rmse_after < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_after

    def _record_smart_decimation_candidate(self, current_n: int, rmse_after: float) -> None:
        """Record current design into Pareto and emit step log."""
        ep = self.ep_current
        has_sub5nm = (ep is not None) and np.any(ep < 5.0)

        # _update_pareto_record already enforces strictly-better updates.
        self._update_pareto_record(self.ep_current, rmse_after)
        self._log_smart_decimation_step_result(current_n, rmse_after, has_sub5nm)

    def _abort_on_smart_decimation_degradation(self, rmse_after: float, ref_rmse: float) -> bool:
        """Abort decimation when RMSE degrades beyond configured safety factor."""
        degradation_limit = 2.0
        if rmse_after <= ref_rmse * degradation_limit:
            return False

        self.log(
            f"   🛑 RMSE {rmse_after:.6f} > {degradation_limit}× ref ({ref_rmse:.6f}) - stopping decimation",
            "WARNING",
        )
        self._finish_smart_decimation()
        return True

    def _log_smart_decimation_step_result(
        self,
        current_n: int,
        rmse_after: float,
        has_sub5nm: bool,
    ) -> None:
        """Log per-step Smart Decimation outcome against current Pareto champion."""
        n_record = self.pareto_history.get(current_n, {})
        best_rmse_for_n = n_record.get("best_rmse", float("inf"))
        flag = " [sub5nm]" if has_sub5nm else ""

        if abs(rmse_after - best_rmse_for_n) < 1e-6:
            # This IS the new champion (we just set it)
            self.log(f"   ✅ N={current_n}: {rmse_after:.6f}{flag}", "SUCCESS")
            return

        self.log(
            f"   - N={current_n}: {rmse_after:.6f} (best={best_rmse_for_n:.6f}){flag}",
            "INFO",
        )

    def _restore_smart_decimation_origin(self, start_n: int) -> None:
        """Restore the checkpointed pre-decimation design when available."""
        origin_ep = getattr(self, "_smart_deci_origin_ep", None)
        origin_rmse = getattr(self, "_smart_deci_origin_rmse", float("inf"))
        origin_table = getattr(self, "_smart_deci_origin_table", None)

        if origin_ep is None or origin_table is None:
            return

        self._restore_table_state(origin_table)
        self.ep_current = origin_ep.copy()
        self._update_thickness_display()
        self._workflow_best_rmse = origin_rmse
        self._use_exact_ep = True
        self.log(
            f"↩️  Reverted to original best solution ({start_n} layers, RMSE={origin_rmse:.6f})",
            "INFO",
        )

    def _clear_smart_decimation_state(self) -> None:
        """Delete transient Smart Decimation runtime attributes."""
        attrs = (
            "_smart_decimation_start_N",
            "_smart_decimation_min_N",
            "_smart_decimation_current_N",
            "_smart_decimation_best_rmse",
            "_smart_decimation_step",
            "_smart_deci_origin_ep",
            "_smart_deci_origin_rmse",
            "_smart_deci_origin_table",
            "_smart_deci_origin_N",
            "_smart_decimation_polish_pass",
            "_smart_decimation_healing",
        )
        for attr in attrs:
            if hasattr(self, attr):
                delattr(self, attr)

    def _log_smart_decimation_completion(self, total_steps: int, start_n: int, end_n: int) -> None:
        """Log Smart Pareto Decimation completion summary."""
        pareto_count = len(self.pareto_history)
        self.log(
            f"🎯 Smart Pareto Decimation complete:"
            f" {total_steps} steps | {start_n}->{end_n} layers | {pareto_count} Pareto records",
            "SUCCESS",
        )

    def _finish_smart_decimation(self) -> None:
        """Clean up after smart decimation and REVERT to original best solution."""

        total_steps = getattr(self, "_smart_decimation_step", 0)

        start_N = getattr(self, "_smart_decimation_start_N", 0)

        # --- REVERT to original best solution ---
        self._restore_smart_decimation_origin(start_N)

        end_N = self.front_table.rowCount()
        self._log_smart_decimation_completion(total_steps, start_N, end_N)

        self._set_busy(False)

        # Cleanup decimation state
        self._clear_smart_decimation_state()

        self._finalize_smart_decimation_post_actions()

    def _finalize_smart_decimation_post_actions(self) -> None:
        """Run final UI/eval/export actions after decimation cleanup."""
        # Enforce hard 5nm rule on the final returned design in the UI
        self._apply_5nm_minimum()

        # Final eval with restored design
        self._schedule_eval(True)

        # Generate grouped Pareto report if auto-export enabled
        if get_export_config() and len(self.pareto_history) > 1:
            QTimer.singleShot(500, self._export_pareto_report)

    def _decimation_remove_and_polish(self) -> None:
        """One step of decimation: remove thinnest, merge, then local polish."""

        N = self.front_table.rowCount()

        ep = self.ep_current

        if N <= 4 or ep is None or len(ep) != N:
            self._finish_pareto_decimation()

            return

        # Find thinnest layer index

        thinnest_idx = int(np.argmin(ep))

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        self.log(
            f"▼ Decimation step {self._decimation_step + 1}: removing layer #{thinnest_idx + 1} "
            f"({thinnest_mat}, {thinnest_d:.2f} nm) from {N}-layer design",
            "INFO",
        )

        # Remove thinnest layer

        self.front_table.removeRow(thinnest_idx)

        self._merge_adjacent_layers()

        self._update_layer_count()

        new_N = self.front_table.rowCount()

        self._target_layer_count = new_N

        # Rebuild ep_current from remaining rows

        self._update_thickness_display()

        self._decimation_step += 1

        # Run a local polish to re-optimize

        self._decimation_polishing = True

        QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))

    def _on_decimation_polish_done(self) -> None:
        """Called after local polish during decimation to evaluate and continue."""

        N = self.front_table.rowCount()

        current_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        # Record in Pareto with current best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self.log(
            f"▼ Decimation: {N} layers -> RMSE={current_rmse:.5f} (ref={self._decimation_ref_rmse:.5f})",
            "INFO",
        )

        # Stop conditions:

        # 1. RMSE too degraded (3× reference)

        # 2. Too few layers

        # 3. Max 20 decimation steps (safety)

        if current_rmse > self._decimation_ref_rmse * 3.0 or N <= 4 or self._decimation_step >= 20:
            self._finish_pareto_decimation()

            return

        # Continue decimating

        QTimer.singleShot(100, self._decimation_remove_and_polish)

    @safe_ui_action
    def _drop_thinnest_and_polish(self) -> None:
        """GUI action: remove thinnest layer, merge if interior, local polish.

        Now identical to remove_thinnest for consistency.

        """

        self.remove_thinnest()

    def _apply_5nm_minimum(self) -> None:
        """Enforce hard minimum layer thickness of 5nm on the current design.

        Removes all layers < 5nm, merges adjacent identical materials,

        and logs any changes. Called at every workflow exit point.

        This rule takes priority over all other optimisation considerations.

        """

        ep = self.ep_current

        if ep is None or len(ep) == 0:
            return

        MIN_FINAL_THICKNESS = 5.0  # nm - hard manufacturing limit

        thin_layers = [r for r, d in enumerate(ep) if d < MIN_FINAL_THICKNESS]

        if not thin_layers:
            return  # Nothing to do

        self.log(
            f"[5nm rule] Removing {len(thin_layers)} layers < {MIN_FINAL_THICKNESS}nm before finalisation",
            "WARNING",
        )

        # Remove in reverse order to keep clues valid

        for r in sorted(thin_layers, reverse=True):
            self.front_table.removeRow(r)

        self._merge_adjacent_layers()

        self._update_layer_count()

        self._update_thickness_display()

        # Update target layer count to new reality

        self._target_layer_count = self.front_table.rowCount()

        self.log(
            f"[5nm rule] Final design: {self._target_layer_count} layers, "
            f"d_min = {float(np.min(self.ep_current)):.2f}nm",
            "INFO",
        )

        # Record the clean manufacturable design in Pareto history

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _save_table_state(self) -> list:
        """Save front_table state (material + QWOT + var) for checkpoint."""

        state = []

        for r in range(self.front_table.rowCount()):
            mat = self._safe_get_combo_text(r, 0)

            qw = self.front_table.cellWidget(r, 1).value() if self.front_table.cellWidget(r, 1) else 1.0

            var = True

            cw = self.front_table.cellWidget(r, 3)

            if cw:
                cb = cw.findChild(QCheckBox)

                if cb:
                    var = cb.isChecked()

            del_checked = False

            del_cw = self.front_table.cellWidget(r, 4)

            if del_cw:
                del_cb = del_cw.findChild(QCheckBox)

                if del_cb:
                    del_checked = del_cb.isChecked()

            state.append({"mat": mat, "qw": qw, "var": var, "del": del_checked})

        return state

    def _restore_table_state(self, state: list) -> None:
        """Restore front_table from saved state (without recalculationating thicknesses)."""

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for item in state:
            self._add_front_row(item["mat"], item["qw"], item["var"], item.get("del", False))

        self.front_table.blockSignals(False)

        self._update_layer_count()

    def _revert_to_checkpoint(self) -> None:
        """Revert to pre-needle checkpoint if needle degraded the solution."""

        checkpoint = getattr(self, "_pre_needle_checkpoint", None)

        if not checkpoint:
            self.log("No checkpoint to revert to.", "WARNING")

            self._set_busy(False)

            return

        self.log(
            f"Reverting to checkpoint (RMSE={checkpoint['rmse']:.6f}, {len(checkpoint['table'])} layers)",
            "WARNING",
        )

        self._restore_table_state(checkpoint["table"])

        self._workflow_best_rmse = checkpoint["rmse"]

        # Clean all needle/overshoot state

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
            "_pre_needle_checkpoint",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._overshoot_done = True

        # Restore exact thicknesses: set QWOT from ep, then update display

        if checkpoint["ep"] is not None:
            self._update_qwot_from_ep(checkpoint["ep"])

            self._update_thickness_display()

            self.ep_current = checkpoint["ep"].copy()

            self._use_exact_ep = True

        self._apply_5nm_minimum()  # Hard rule before closing

        if get_export_config():
            self._export_pending = True  # Set BEFORE schedule_eval

        # Force final Pareto update with best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)

        self.log("Optimization complete (reverted to best). Structure stable.", "SUCCESS")

        self._set_busy(False)

        self._is_internal_restart = False

        if get_export_config():
            self._export_pending = True

    def smart_cleanup(self, update_target: bool = True) -> int:
        """

        Smart cleanup: merges identical adjacent materials and removes

        very thin layers (< 1.0 nm) which are likely artifacts.

        Parameters

        ----------

        update_target : bool, optional

            If True, updates self._target_layer_count to match new count.

            Set to False during Deep Needle loop to maintain high target.

        Returns

        -------

        int

            Number of layers removed

        """

        removed_count = 0

        changed = False

        # Step 1: Remove very thin layers dynamically based on RMSE

        # Smart threshold: When RMSE is very low (sharp design), remove only incredibly thin layers to preserve delicate structures.

        current_rmse = getattr(self, "_workflow_best_rmse", 1.0)

        multiplier = getattr(self, "_cleanup_threshold_multiplier", 150.0)

        threshold = max(0.05, min(1.0, current_rmse * multiplier))  # Adaptive threshold

        rows_to_remove = []

        ep_current = self.ep_current if self.ep_current is not None else []

        if len(ep_current) == self.front_table.rowCount():
            for r in range(len(ep_current) - 1, -1, -1):
                if ep_current[r] < threshold:
                    rows_to_remove.append(r)

        if rows_to_remove:
            self.log(f"Smart cleanup: removing {len(rows_to_remove)} layers < {threshold:.2f} nm (adaptive)", "INFO")

            for r in rows_to_remove:
                self.front_table.removeRow(r)

            removed_count += len(rows_to_remove)

            changed = True

        # Step 2: Merge identical adjacent materials

        # (uses _merge_adjacent_layers which already does this)

        pre_merge_count = self.front_table.rowCount()

        self._merge_adjacent_layers()

        post_merge_count = self.front_table.rowCount()

        merge_diff = pre_merge_count - post_merge_count

        if merge_diff > 0:
            removed_count += merge_diff

            changed = True

            self.log(f"Smart cleanup: merged {merge_diff} adjacent layers", "INFO")

        if changed:
            self._update_layer_count()

            self._update_thickness_display()

            if update_target:
                self._target_layer_count = self.front_table.rowCount()

        return removed_count

    def _prune_to_target(self, target_count: int) -> int:
        """

        Overshoot & Prune: remove thinnest layers to reach target count.

        After growing beyond the target via Needle, prune back by removing

        the thinnest layers first (they contribute least to the design).

        Removes ONE layer at a time, then merges adjacent identical materials

        and re-checks count. This is necessary because in H/L stacks,

        removing one layer makes its neighbours adjacent -> merge -> net -2.

        This method performs layer pruning including:

        - Identification of thinnest layers

        - Sequential layer removal

        - Adjacent material merging

        - Count verification and adjustment

        Args:

            self: CertusDesign instance

            target_count: Desired number of layers after pruning

        Returns:

            int: Total number of layers removed (including merges)

        Notes:

            - Used in Needle algorithm workflow

            - Handles H/L stack merging automatically

            - Updates UI components after pruning

            - Logs pruning operations

        """

        initial_count = self.front_table.rowCount()

        if initial_count <= target_count:
            return 0

        total_removed = 0

        while self.front_table.rowCount() > target_count:
            current_count = self.front_table.rowCount()

            ep = self.ep_current if self.ep_current is not None else np.array([])

            if len(ep) != current_count:
                self._update_thickness_display()

                ep = self.ep_current if self.ep_current is not None else np.array([])

                if len(ep) != current_count:
                    self.log("Prune: ep_current mismatch, stopping.", "WARNING")

                    break

            # Find the thinnest layer

            thinnest_idx = int(np.argmin(ep))

            self.log(f"  Prune: layer {thinnest_idx} ({ep[thinnest_idx]:.2f} nm)", "INFO")

            self.front_table.blockSignals(True)

            self.front_table.removeRow(thinnest_idx)

            self.front_table.blockSignals(False)

            # Merge adjacent identical materials (may remove additional layers)

            pre_merge = self.front_table.rowCount()

            self._merge_adjacent_layers()

            post_merge = self.front_table.rowCount()

            step_removed = 1 + (pre_merge - post_merge)

            total_removed += step_removed

            self._update_layer_count()

            self._update_thickness_display()

        final_count = self.front_table.rowCount()

        self.log(
            f"Overshoot & Prune: {initial_count} -> {final_count} layers "
            f"(removed {total_removed}, target was {target_count})",
            "SUCCESS",
        )

        return total_removed

    def _needle_thresholds(self, rmse_ref: float) -> tuple:
        """Adaptive thresholds for needle merit checks."""

        if rmse_ref is None or not np.isfinite(rmse_ref) or rmse_ref <= 0.0:
            return self._needle_success_rel_threshold, self._needle_success_abs_floor

        rel_thresh = 0.002 if rmse_ref < 0.01 else self._needle_success_rel_threshold

        abs_thresh = max(self._needle_success_abs_floor, rmse_ref * 5e-4)

        return rel_thresh, abs_thresh

    def _needle_gain_is_significant(self, rmse_before: float, rmse_after: float) -> tuple:
        """Return whether RMSE gain is meaningful for topology growth."""

        if (
            rmse_before is None
            or rmse_after is None
            or not np.isfinite(rmse_before)
            or not np.isfinite(rmse_after)
            or rmse_before <= 0.0
            or rmse_after >= rmse_before
        ):
            return False, 0.0, 0.0, 0.0, 0.0

        delta_abs = rmse_before - rmse_after

        delta_rel = delta_abs / max(rmse_before, 1e-12)

        rel_thresh, abs_thresh = self._needle_thresholds(rmse_before)

        ok = (delta_abs >= abs_thresh) or (delta_rel >= rel_thresh)

        return ok, delta_abs, delta_rel, abs_thresh, rel_thresh

    def _start_needle_process(self, ) -> None:
        return getattr(self, 'orchestrator', self)._start_needle_process()

    def _on_needle_found(self, res) -> None:
        return getattr(self, 'orchestrator', self)._on_needle_found(res)

    def _handle_needle_no_candidate(self, action, res) -> Any:
        return getattr(self, 'orchestrator', self)._handle_needle_no_candidate(action, res)

    def _handle_needle_no_candidate_below_target(self, action, res, current_count) -> tuple:
        return getattr(self, 'orchestrator', self)._handle_needle_no_candidate_below_target(action, res, current_count)

    def _abort_needle_after_failed_retries(self, ) -> None:
        return getattr(self, 'orchestrator', self)._abort_needle_after_failed_retries()

    def _maybe_prune_needle_overshoot(self, current_count) -> bool:
        return getattr(self, 'orchestrator', self)._maybe_prune_needle_overshoot(current_count)

    def _apply_needle_split_insertion(self, res) -> bool:
        return getattr(self, 'orchestrator', self)._apply_needle_split_insertion(res)

    def _insert_needle_split_row(self, idx, mat_needle, n_needle, l0) -> float:
        return getattr(self, 'orchestrator', self)._insert_needle_split_row(idx, mat_needle, n_needle, l0)

    def _insert_right_split_row(self, idx, mat_orig, qw_right, d_right) -> None:
        return getattr(self, 'orchestrator', self)._insert_right_split_row(idx, mat_orig, qw_right, d_right)

    def _clear_needle_cycle_state(self, ) -> None:
        return getattr(self, 'orchestrator', self)._clear_needle_cycle_state()

    def _clear_needle_search_state(self, keep_fail_count) -> None:
        return getattr(self, 'orchestrator', self)._clear_needle_search_state(keep_fail_count)

