"""
CERTUS DESIGN ORCHESTRATOR

Handles the complex multi-stage topology synthesis loop (Needle -> Optim -> Phase2 -> Cleanup)
headless, decoupled from the UI.
"""
from typing import Any, Dict
import functools
import logging

import numpy as np

from certus.core.certus_core import CFG, get_complex_dtype, get_export_config, get_float_dtype
from certus.utils.certus_logging import get_structured_logger
from certus.workers.certus_design_workers_dto import ColorWorkerRequest, NeedleWorkerRequest, OptimWorkerRequest
from certus.workers.certus_design_workers import NeedleWorker, OptimWorker

class DesignOrchestrator:
    """
    Headless State Machine for Optical Synthesis.
    
    Manages NeedleWorker, OptimWorker, Phase2Worker.
    Receives events from workers, makes architectural decisions (insert, stop, prune),
    and emits generalized events to the UI/Script listener.
    """
    
    def __init__(self, ui_instance):
        self.ui = ui_instance
        self.is_running = False

        # References to current active workers
        self.current_needle_worker = None
        self.current_optim_worker = None

        # State management for specific orchestration flows
        self._healing_phase = None
        self._overshoot_active = False
        self._overshoot_done = False
        self._original_target_count = None
        self._target_layer_count = None

        logging.info("[ORCHESTRATOR] DesignOrchestrator initialized.")

    def start_synthesis(self, initial_cfg: Dict[str, Any]):
        """Entry point to kickstart the autonomous synthesis loop."""
        self.is_running = True
        logging.info("[ORCHESTRATOR] Synthesis loop started.")
        self.ui.log("Synthesis orchestration is not yet wired into the UI flow.", "ERROR")

    def abort(self):
        """Forcefully stops any running synthesis loop."""
        self.is_running = False
        logging.info("[ORCHESTRATOR] Synthesis loop aborted.")

    def _schedule_task(self, delay_ms: int, func) -> None:
        if hasattr(self.ui, "schedule_task"):
            self.ui.schedule_task(delay_ms, func)
        else:
            # Headless / Synchronous fallback
            func()



    # ================= EXTRACTED METHODS =================

    def _is_in_needle_cycle(self) -> bool:
        """Return True when post-optim workflow is inside Needle cycle states."""
        return hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]

    def _on_optim_done(self, d: Dict) -> None:
        """Central callback after any optimization completes.

        This is the main state machine driving the hybrid design workflow.

        It is called after every optimization (global, healing, or local)

        and decides the next action based on the current workflow state.

        Decision flow (executed in order):

        1. **QW update**: Write optimized thicknesses back to the GUI table.

        2. **Needle step transition**: If in needle cycle step 1, record RMSE

           and transition to step 2 (cleanup phase).

        3. **Smart cleanup**: Remove layers < 1 nm and merge adjacent identical

           materials (skipped during needle cycle to avoid interference).

           Uses ``update_target=False`` to preserve the original layer count

           target so the Needle can grow back removed layers.

        4. **Healing trigger**: If cleanup removed layers (and not in needle

           cycle), start the two-phase healing sequence:

           - Phase 1 (``'healing'``): Restricted PGLOBAL within +/-Deltad = lambda₀/(10·n)

             to explore nearby basins after topology change.

           - Phase 2 (``'local'``): L-BFGS-B polish to guarantee precise

             convergence (never skipped).

        5. **Needle cycle management** (steps 2->3): Cleanup after needle

           insertion, evaluate RMSE improvement (>1% threshold), check

           stagnation (3 cycles without progress -> abort).

        6. **Case B - Layer deficit**: If current count < target, activate

           Overshoot & Prune on first deficit (+20% extra layers via Needle,

           then prune thinnest back to original target).

        7. **Case C - Complete**: Target reached, export results.

        This method performs workflow management including:

        - Result processing and GUI updates

        - State machine transitions

        - Needle cycle management

        - Healing sequence coordination

        - Progress tracking and logging

        Args:

            self: CertusDesign instance

            d: Optimization result dictionary

        Returns:

            None

        Notes:

            - Logs workflow transitions and decisions

            - Handles complex state machine logic

            - Manages needle insertion cycles

            - Coordinates healing and cleanup phases"""

        self.ui.progress_widget.stop("Done")

        self.ui._clean_live_curves()

        self.ui._initial_cleared = False
        
        print("DEBUG: _on_optim_done ENTERED. d.ok =", d.get("ok", False))

        if getattr(self, "_workflow_stopped", False):
            self.ui._handle_stopped_workflow_result(d)

            return

        if not d.get("ok", False):
            error_msg = d.get("error", "Unknown reason.")
            self.ui.log(f"Optimization stopped or failed: {error_msg}", "ERROR")
            print("DEBUG: _on_optim_done ERROR:", error_msg)
            
            # UX: Guided error message
            if hasattr(self.ui, "show_error_dialog"):
                self.ui.show_error_dialog(
                    "Optimization Failed",
                    f"The optimization process could not complete successfully.\n\n"
                    f"Reason: {error_msg}\n\n"
                    f"Please verify your target curves and initial design."
                )
            
            self.ui._set_busy(False)
            return

        self.ui._stack_info_best_ep = None

        self.ui._stack_info_best_rmse = None

        self._schedule_task(50, self.ui.optimization_finished_signal.emit)

        # PARETO DECIMATION: if we are polishing after decimation, route to decimation handler
        if self._handle_decimation_polish_completion(d):
            return

        # TIME BUDGET for post-optimization workflow (cleanup/healing/needle)
        if self.ui._finalize_if_post_optim_budget_exceeded():
            return

        # Track best RMSE and refresh table/QW state.
        self.ui._track_and_apply_post_optim_result(d)

        # Check if we're in smart decimation mode
        if self._handle_smart_decimation_followup(d):
            return

        # Needle loop management: Needle -> Optim -> Evaluate

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 1:
            # Step 1 done: Optim after Needle insertion

            # _needle_merit_before was set to pre-needle RMSE in _start_needle_process

            self._needle_cycle_step = 2  # Proceed to step 2 (skip cleanup) then 3

        # POST-OPTIM HOOK: Smart cleanup (only if not in Needle cycle and not post-prune)

        # update_target=False: preserve original target so Needle can grow back

        removed = self.ui._run_post_optim_cleanup(d)

        self.ui.front_table.rowCount()

        # HEALING: If cleanup removed layers, restricted global + local polish

        # But only if not in Needle cycle

        if self._handle_healing_workflow(removed):
            return

        # If in Needle cycle and step==2, skip cleanup and go to evaluation

        # (cleanup during needle causes add-remove loop -> stagnation)

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 2:
            self._needle_cycle_step = 3

        if self._handle_needle_cycle_step3(d):
            return

        # Case B: Layer deficit OR Needle Exploration requested
        if self._maybe_start_needle_growth():
            return

        self.ui._finalize_completed_optimization_workflow()

    def _handle_healing_workflow(self, removed: int) -> bool:
        """Drive two-phase healing after cleanup-induced topology changes."""
        if removed > 0 and not getattr(self.ui, "_is_in_needle_cycle", lambda: False)():
            self.ui.log(
                f"Smart cleanup removed {removed} layers. Healing (restricted global)...",
                "INFO",
            )
            self.ui.accumulated_evals += getattr(self.ui, "_optim_n_evals", 0)
            self._healing_phase = "global"
            self._schedule_task(50, functools.partial(self.ui.run_optim, "healing", keep_history=True))
            return True

        if self._healing_phase == "global":
            self._healing_phase = "local"
            _wf = getattr(self.ui, "_workflow_best_rmse", float("inf"))
            self.ui.log(
                f"[HEALING] global→local | {self.ui.front_table.rowCount()}L | workflow_best={_wf:.6f}",
                "INFO",
            )
            self.ui.log("Healing: local polish...", "INFO")
            self.ui.accumulated_evals += getattr(self.ui, "_optim_n_evals", 0)
            self._schedule_task(50, lambda: self.ui.run_optim("local", keep_history=True))
            return True

        if self._healing_phase == "local":
            self._healing_phase = None
        return False

    def _handle_needle_cycle_step3(self, d: dict) -> bool:
        """Handle Needle step-3 post-optimization logic. Returns True if flow consumed."""
        if not (hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 3):
            return False

        rmse_after_cleanup = d.get("rmse", float("inf"))
        needle_successful = False
        _wf = getattr(self.ui, "_workflow_best_rmse", float("inf"))
        self.ui.log(
            f"[NEEDLE.step3] post-optim | merit_before={getattr(self, '_needle_merit_before', '?')} "
            f"| rmse_after={rmse_after_cleanup:.6f} | workflow_best={_wf:.6f} "
            f"| n={self.ui.front_table.rowCount()}L",
            "INFO",
        )

        if getattr(self, "_needle_merit_before", None) is not None:
            ok_gain, delta_abs, delta_rel, abs_thresh, rel_thresh = self.ui._needle_gain_is_significant(
                self._needle_merit_before, rmse_after_cleanup
            )
            if ok_gain:
                self.ui.log(
                    f"Needle cycle successful: DeltaRMSE={delta_abs:.6g} ({delta_rel * 100:.2f}%, "
                    f"thresholds abs>={abs_thresh:.6g} or rel>={rel_thresh * 100:.2f}%)",
                    "SUCCESS",
                )
                needle_successful = True
            else:
                self.ui.log(
                    f"Needle cycle: gain too small (DeltaRMSE={delta_abs:.6g}, {delta_rel * 100:.2f}%)",
                    "WARNING",
                )
        else:
            self.ui.log("Needle cycle: no improvement. Aborting needle.", "WARNING")
            self.ui._revert_to_checkpoint()
            return True

        if hasattr(self, "_needle_cycle_step"):
            delattr(self, "_needle_cycle_step")
        if hasattr(self, "_needle_merit_before"):
            delattr(self, "_needle_merit_before")

        current_count_after_clean = self.ui.front_table.rowCount()
        last_count = getattr(self, "_last_cycle_layer_count", 0)
        if not hasattr(self, "_needle_stagnation_count"):
            self._needle_stagnation_count = 0

        if current_count_after_clean <= last_count and not needle_successful:
            self._needle_stagnation_count += 1
            self.ui.log(
                f"[DESIGN.needle] stagnation detected | cycle_without_growth={self._needle_stagnation_count}/3 | target_layers={self._target_layer_count}",
                "WARNING",
            )
        else:
            self._needle_stagnation_count = 0

        self._last_cycle_layer_count = current_count_after_clean
        if self._needle_stagnation_count >= 3:
            self.ui.log(
                "[DESIGN.needle] aborted due to stagnation | reason=3 cycles without growth or merit | action=revert_to_checkpoint",
                "ERROR",
            )
            delattr(self, "_needle_stagnation_count")
            if hasattr(self, "_last_cycle_layer_count"):
                delattr(self, "_last_cycle_layer_count")
            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)
                self._overshoot_active = False
            self.ui._revert_to_checkpoint()
            return True

        if current_count_after_clean < self._target_layer_count and current_count_after_clean < CFG.MAX_LAYERS:
            self.ui.log(
                f"[DESIGN.needle] growth continuing | current_layers={current_count_after_clean} | target_layers={self._target_layer_count} | action=queue_next_cycle",
                "INFO",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            self._schedule_task(100, self._start_needle_process)
            return True

        if current_count_after_clean >= self._target_layer_count:
            if getattr(self, "_overshoot_active", False):
                original = getattr(self, "_original_target_count", self._target_layer_count)
                self.ui.log(
                    f"Overshoot complete ({current_count_after_clean} layers). Pruning to {original}...",
                    "SUCCESS",
                )
                self.ui._prune_to_target(original)
                self._overshoot_active = False
                self._overshoot_done = True
                self._target_layer_count = original
                current_rmse = d.get("rmse", float("inf"))
                checkpoint = getattr(self.ui, "_pre_needle_checkpoint", None)
                if checkpoint and current_rmse > checkpoint["rmse"] * 1.02:
                    self.ui.log(
                        f"Overshoot+Prune degraded RMSE ({current_rmse:.6f} > {checkpoint['rmse']:.6f}). Reverting.",
                        "WARNING",
                    )
                    self.ui._revert_to_checkpoint()
                    return True
                pruned = current_count_after_clean - original
                if pruned > 0:
                    self.ui.log(f"Pruned {pruned} thinnest layers. Final polish...", "INFO")
                    self.ui.accumulated_evals += getattr(self.ui, "_optim_n_evals", 0)
                    self.ui._post_prune = True
                    self._schedule_task(50, functools.partial(self.ui.run_optim, "local", keep_history=True))
                    return True

            self.ui.log(
                f"Deep Needle: Target reached ({self.ui.front_table.rowCount()} layers)",
                "SUCCESS",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            return False

        self.ui.log("Deep Needle: MAX_LAYERS reached", "WARNING")
        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")
        return False

    def _maybe_start_needle_growth(self) -> bool:
        """Start Needle growth/exploration when deficit or stagnation criteria are met."""
        import math
        current_count = self.ui.front_table.rowCount()
        allow_growth = self.ui.allow_growth_check.isChecked() if hasattr(self.ui, "allow_growth_check") else True
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
            self._original_target_count = self._target_layer_count
            if self._target_layer_count < CFG.MAX_LAYERS:
                ratio = getattr(self.ui, "_needle_overshoot_ratio", 0.30)
                extra_layers = max(int(math.ceil(self._target_layer_count * ratio)), 4)
                overshoot = min(self._target_layer_count + extra_layers, CFG.MAX_LAYERS)
                self._target_layer_count = overshoot
                self._overshoot_active = True
                self.ui.log(
                    f"Deep Needle Exploration: temporarily growing to {overshoot} layers "
                    f"(Target: {self._original_target_count}, +{extra_layers} extra for flexibility)",
                    "INFO",
                )

        self.ui._pre_needle_checkpoint = {
            "ep": (self.ui.ep_current.copy() if getattr(self.ui, "ep_current", None) is not None else None),
            "rmse": getattr(self.ui, "_workflow_best_rmse", float("inf")),
            "table": self.ui._save_table_state(),
        }
        _cp_rmse = getattr(self.ui, "_workflow_best_rmse", float("inf"))
        _ep = getattr(self.ui, "ep_current", None)
        _ep_hash = f"{float(sum(_ep)):.4f}" if _ep is not None and len(_ep) > 0 else "?"
        self.ui.log(
            f"Checkpoint saved (RMSE={_cp_rmse:.6f}, {current_count} layers, ep_sum={_ep_hash})",
            "INFO",
        )

        deficit = self._target_layer_count - current_count
        self.ui.log(f"Layer deficit ({deficit}). Starting iterative Needle...", "INFO")
        self._start_needle_process()
        return True

    def _handle_decimation_polish_completion(self, d: Dict) -> bool:
        """Route decimation polish completion and bypass standard workflow."""
        if not getattr(self.ui, "_decimation_polishing", False):
            return False

        if "ep" in d:
            self.ui.ep_current = d["ep"].copy()
        rmse = d.get("rmse", getattr(self.ui, "_workflow_best_rmse", float("inf")))
        if rmse < getattr(self.ui, "_workflow_best_rmse", float("inf")):
            self.ui._workflow_best_rmse = rmse
        self.ui._update_thickness_display()
        self.ui._on_decimation_polish_done()
        return True

    def _handle_smart_decimation_followup(self, d: Dict) -> bool:
        """Advance smart decimation polish passes when enabled."""
        if not hasattr(self.ui, "_smart_decimation_step"):
            return False

        polish_pass = getattr(self.ui, "_smart_decimation_polish_pass", 0)
        if polish_pass == 1:
            self.ui._smart_decimation_polish_pass = 2
            self.ui.run_optim("local", keep_history=True)
            return True

        self.ui._smart_decimation_polish_pass = 0
        self.ui._on_smart_decimation_optim_done(d)
        return True

    def _start_needle_process(self) -> None:
        """

        Start one Needle insertion cycle.

        The Needle method (Tikhonravov) scans the topological derivative P(z)

        across the optical thickness of the stack. Where P(z) is strongly

        negative, inserting a zero-thickness layer of the alternate material

        decreases the merit function.

        This method is called iteratively by the Deep Needle loop in

        ``_on_optim_done`` until the target layer count is reached or

        stagnation is detected.

        Workflow per call:

        1. Initialize stagnation counters (first call only).

        2. Preventive merge of adjacent identical materials.

           If any merged, run local polish first (``keep_history=True``).

        3. Build NeedleWorker configuration (stack, materials, targets).

        4. Start NeedleWorker -> emits ``_on_needle_found`` on completion.

        The growth cycle per insertion is:

        ``Needle -> Optim (step 1) -> Cleanup (step 2) -> Evaluate (step 3)``

        During the Overshoot phase, the target is temporarily set +20% above

        the user's original target to enrich the design space before pruning.

        This method performs needle insertion including:

        - Stagnation counter initialization

        - Material merging and cleanup

        - Worker thread configuration

        - Progress monitoring and error handling

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs needle insertion progress

            - Handles workflow stop requests

            - Emits progress signals during execution

            - Supports both normal and overshoot modes

        """

        # GUARD: If user clicked STOP, do not start needle

        if getattr(self, "_workflow_stopped", False):
            self.ui.log("Workflow stopped, skipping needle.", "WARNING")

            self.ui._set_busy(False)

            return

        # New Needle cycle initialization

        if not hasattr(self, "_needle_cycle_step") or self._needle_cycle_step not in [
            1,
            2,
            3,
        ]:
            # Keep fail counter across retries so it can reach abort threshold.

            # Only initialize once when missing.

            if not hasattr(self, "_needle_fail_count"):
                self._needle_fail_count = 0

            if not hasattr(self, "_needle_excluded_layers"):
                self._needle_excluded_layers = set()

            if not hasattr(self, "_needle_last_rejected_candidate"):
                self._needle_last_rejected_candidate = None

            if not hasattr(self, "_needle_exploratory_used"):
                self._needle_exploratory_used = False

            # Set merit BEFORE needle to the current best RMSE

            self._needle_merit_before = self.ui._workflow_best_rmse

            # STAGNATION GUARD: Init counters

            if not hasattr(self, "_needle_stagnation_count"):
                self._needle_stagnation_count = 0

            if not hasattr(self, "_last_cycle_layer_count"):
                self._last_cycle_layer_count = self.ui.front_table.rowCount()

            # DEEP NEEDLE LOGIC: If starting from stable state, we want to grow.

            # Set target explicitly to MAX_LAYERS to enable "Deep Needle" loop

            current_count = self.ui.front_table.rowCount()

            # Check UI Option

            allow_growth = True

            if hasattr(self, "allow_growth_check"):
                allow_growth = self.ui.allow_growth_check.isChecked()

            if allow_growth and self._target_layer_count <= current_count:
                # User likely clicked "Needle" manually to grow structure. Let overshoot logic handle it.
                pass

        # PREVENTIVE CLEANUP: Light clean before Needle (merge only, no deletion)

        # Only merge adjacent layers, avoid deleting thin layers

        # to avoid disturbing current optimization

        pre_merge_count = self.ui.front_table.rowCount()

        self.ui._merge_adjacent_layers()

        post_merge_count = self.ui.front_table.rowCount()

        merge_diff = pre_merge_count - post_merge_count

        if merge_diff > 0:
            self.ui.log(
                f"Preventive merge before Needle: merged {merge_diff} adjacent layers",
                "INFO",
            )

            self.ui._update_layer_count()
            self.ui._update_thickness_display()

            # The stack has degraded due to merging. The old RMSE is invalid.
            self.ui._workflow_best_rmse = float("inf")
            if hasattr(self, "_needle_merit_before"):
                self._needle_merit_before = float("inf")

            # If layers merged, restart light optimization (keep_history to preserve target)
            self.ui.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            self._schedule_task(50, lambda: self.ui.run_optim("local", keep_history=True))
            return

        mats = self.ui._get_materials()

        stack = self.ui._get_front_stack()

        wls = self.ui._get_optim_wls()

        if len(wls) == 0:
            wls = np.linspace(CFG.WL_DEFAULT_MIN, CFG.WL_DEFAULT_MAX, CFG.WL_DEFAULT_POINTS)

        # Backside configuration for Needle

        back_enabled = self.ui.back_check.isChecked()

        use_back_coat = self.ui.back_coat_check.isChecked()

        stack_back = self.ui._get_back_stack()

        ep_back = self.ui.ep_back_current if self.ui.ep_back_current is not None else np.array([])

        has_back_stack = use_back_coat and len(stack_back) > 0

        float_dtype = get_float_dtype()

        complex_dtype = get_complex_dtype()

        n_back_T = np.zeros((len(wls), 0), dtype=complex_dtype)

        d_back = np.zeros(0, dtype=float_dtype)

        if has_back_stack:
            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

            n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)

            n_back_T = np.ascontiguousarray(n_back.T)

            d_back = np.ascontiguousarray(ep_back, dtype=float_dtype)

        # NeedleWorker expects 'has_back' key for calculationation activation

        has_back_calc = back_enabled

        ep_curr = self.ui.ep_current if self.ui.ep_current is not None else np.array([])

        # Retrieve targets based on mode (normal or oblique)

        if self.ui.oblique_mode:
            tgts_needle = self.ui._get_oblique_tgts()

        else:
            tgts_needle = self.ui._get_tgts()

        cfg = {
            "stack": stack,
            "mats": mats,
            "l0": self.ui.l0_spin.value(),
            "wls": wls,
            "tgts": tgts_needle,
            "ep": ep_curr,
            "has_back": has_back_calc,
            "n_back_T": n_back_T,
            "d_back": d_back,
            "oblique_mode": self.ui.oblique_mode,  # Pass oblique mode
            "oblique_tgts": (self.ui._get_oblique_tgts() if self.ui.oblique_mode else []),  # Pass oblique targets
            "excluded_layers": sorted(getattr(self, "_needle_excluded_layers", set())),
            "run_id": getattr(self.ui, "_workflow_run_id", None),
            "run_context": getattr(self.ui, "_workflow_run_ctx", None),
        }
        if hasattr(self.ui, "progress_widget"):
            self.ui.progress_widget.start(phase="NEEDLE SCAN")

        # Delegate UI threading
        if hasattr(self.ui, "start_needle_worker"):
            self.ui.start_needle_worker(cfg, self._on_needle_found)
        else:
            self.ui.log("UI doesn't support start_needle_worker", "ERROR")

    def schedule_refresh_pareto_table(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(0, self.ui._refresh_pareto_table)

    def schedule_update_substrate_info(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(0, self.ui._update_substrate_info)

    def schedule_update_tikhonravov_points(self, delay_ms: int = 300) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(delay_ms, self.ui._update_tikhonravov_points)

    def schedule_export_results(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(100, self.ui.export_results)

    def schedule_smart_pareto_decimation(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(200, self.ui._start_smart_pareto_decimation)

    def schedule_smart_decimation_remove_and_optimize(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(200, self.ui._smart_decimation_remove_and_optimize)

    def schedule_export_pareto_report(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(500, self.ui._export_pareto_report)

    def schedule_local_optim_keep_history(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(50, lambda: self.ui.run_optim("local", keep_history=True))

    def schedule_decimation_remove_and_polish(self) -> None:
        if hasattr(self.ui, "schedule_task"):
            self._schedule_task(100, self.ui._decimation_remove_and_polish)

    def _on_needle_found(self, res: Dict) -> None:
        if hasattr(self.ui, "progress_widget"):
            self.ui.progress_widget.stop("Done")
        """

        Callback after NeedleWorker completes a topological scan.

        Handles the result of a Needle insertion search and drives

        the iterative growth loop.

        This method processes needle insertion results including:

        - Action determination and handling

        - Layer insertion and splitting

        - Target layer management

        - Workflow state coordination

        Possible actions (``res['action']``):

        - ``'empty_init'``: Stack is empty, add a seed layer.

        - ``'max_layers_reached'``: Cannot add more layers (CFG.MAX_LAYERS).

        - ``'none'``: No beneficial insertion found.

          - If below target: retry up to 3 times, then abort.

          - If at/above target and Overshoot active: trigger prune.

          - If at/above target and no Overshoot: stop (target reached).

        - ``'split'``: Insert a needle layer by splitting an existing layer

          at the optimal depth. Creates 3 rows (left + needle + right),

          then starts the Needle cycle: step 1 -> optimization -> step 2 -> cleanup

          -> step 3 -> evaluate.

        All abort paths clean up overshoot state to prevent dangling flags.

        Args:

            self: CertusDesign instance

            res: NeedleWorker result dictionary with action and data

        Returns:

            None

        Notes:

            - Logs needle insertion progress and decisions

            - Handles workflow stop requests

            - Manages overshoot and target layer states

            - Coordinates needle cycle transitions

        """

        # GUARD: If user clicked STOP, do not process needle result

        if getattr(self, "_workflow_stopped", False):
            self.ui.log("Workflow stopped, ignoring needle result.", "WARNING")

            self.ui._set_busy(False)

            return

        action = res.get("action", "none")

        if action == "empty_init":
            self.ui.log("Needle:  Empty stack, adding seed layer.", "INFO")

            self.ui.add_front_layer()

            self.ui.run_optim("local")

            return

        if action == "max_layers_reached":
            self.ui.log("Needle: MAX_LAYERS reached. Stopping iterative Needle.", "WARNING")

            # Stop iterative loop

            self._clear_needle_cycle_state()

            # Clean overshoot state

            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = self._original_target_count

                self._overshoot_active = False

            self.ui._set_busy(False)

            return

        if action == "split":
            pred_cost = res.get("cost")

            workflow_best = getattr(self.ui, "_workflow_best_rmse", float("inf"))

            if (
                pred_cost is not None
                and np.isfinite(pred_cost)
                and pred_cost >= 0.0
                and pred_cost < 1e20
                and workflow_best is not None
                and np.isfinite(workflow_best)
                and workflow_best > 0.0
            ):
                pred_rmse = float(np.sqrt(pred_cost))

                pred_gain_abs = workflow_best - pred_rmse

                pred_gain_rel = pred_gain_abs / max(workflow_best, 1e-12)

                min_abs = getattr(self, "_needle_pred_gain_abs_threshold", 1e-5)

                min_rel = getattr(self, "_needle_pred_gain_rel_threshold", 0.002)

                allow_growth = True
                if hasattr(self.ui, "allow_growth_check"):
                    allow_growth = self.ui.allow_growth_check.isChecked()

                if not allow_growth and pred_gain_abs < min_abs and pred_gain_rel < min_rel:
                    self.ui.log(
                        f"Needle: insertion skipped (predicted gain too small, "
                        f"DeltaRMSE={pred_gain_abs:.3g}, {pred_gain_rel * 100:.2f}%)",
                        "WARNING",
                    )

                    self._needle_last_rejected_candidate = dict(res) if res is not None else None

                    if res is not None and "layer_idx" in res:
                        if not hasattr(self, "_needle_excluded_layers"):
                            self._needle_excluded_layers = set()

                        self._needle_excluded_layers.add(int(res["layer_idx"]))

                    action = "none"

        if action == "none" or res is None:
            action, res, handled = self._handle_needle_no_candidate(action, res)

            if handled:
                return

        if action == "split":
            self._needle_fail_count = 0

            self._clear_needle_search_state(keep_fail_count=True)

            if not self._apply_needle_split_insertion(res):
                return

    def _handle_needle_no_candidate(self, action: str, res: Dict) -> Any:
        """Handle "none" needle actions including retries, aborts, and overshoot prune."""

        current_count = self.ui.front_table.rowCount()

        if current_count < self._target_layer_count:
            return self._handle_needle_no_candidate_below_target(action, res, current_count)

        if self._maybe_prune_needle_overshoot(current_count):
            return action, res, True

        self.ui.log("Needle: No beneficial insertion found. Target reached.", "INFO")

        self._clear_needle_search_state()

        self._clear_needle_cycle_state()

        self.ui._set_busy(False)

        return action, res, True

    def _handle_needle_no_candidate_below_target(self, action: str, res: Dict, current_count: int) -> tuple:
        """Handle retries and abort for needle no-candidate results below target count."""

        self.ui.log(
            f"Needle: No beneficial insertion found. Current: {current_count}, Target: {self._target_layer_count}",
            "WARNING",
        )

        if not hasattr(self, "_needle_fail_count"):
            self._needle_fail_count = 0

        self._needle_fail_count += 1

        if self._needle_fail_count >= 3:
            exploratory_candidate = getattr(self, "_needle_last_rejected_candidate", None)

            if exploratory_candidate is not None and not getattr(self, "_needle_exploratory_used", False):
                self._needle_exploratory_used = True

                self._needle_fail_count = 0

                if hasattr(self, "_needle_excluded_layers") and "layer_idx" in exploratory_candidate:
                    self._needle_excluded_layers.discard(int(exploratory_candidate["layer_idx"]))

                self.ui.log(
                    "Needle: launching one exploratory insertion after 3 filtered retries.",
                    "WARNING",
                )

                action = "split"

                res = exploratory_candidate

            else:
                self._abort_needle_after_failed_retries()

                return action, res, True

        if action == "none" or res is None:
            self.ui.log(
                f"Needle: Retrying... (attempt {self._needle_fail_count}/3)",
                "INFO",
            )

            self._schedule_task(200, self._start_needle_process)

            return action, res, True

        return action, res, False

    def _abort_needle_after_failed_retries(self) -> None:
        """Abort iterative needle workflow after repeated no-candidate failures."""

        self.ui.log(
            "Needle: Too many failed attempts. Stopping iterative Needle.",
            "WARNING",
        )

        delattr(self, "_needle_fail_count")

        self._clear_needle_cycle_state()

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = self._original_target_count

            self._overshoot_active = False

        checkpoint = getattr(self, "_pre_needle_checkpoint", None)

        if checkpoint is not None:
            self.ui.log("Needle: reverting to checkpoint.", "WARNING")

            self.ui._revert_to_checkpoint()

            return

        if get_export_config():
            self.ui._export_pending = True

        self.ui._schedule_eval(True)

        self.ui.log("Needle: aborted after retries. Finalizing current structure.", "WARNING")

        self.ui._set_busy(False)

    def _maybe_prune_needle_overshoot(self, current_count: int) -> bool:
        """Prune overshoot layers and restart local optimization when needed."""

        if not getattr(self, "_overshoot_active", False):
            return False

        allow_growth = True
        if hasattr(self.ui, "allow_growth_check"):
            allow_growth = self.ui.allow_growth_check.isChecked()

        if allow_growth:
            self.ui.log(
                f"Needle: Overshoot target reached ({current_count} layers). Keeping new target as allow_growth is enabled.",
                "SUCCESS",
            )
            self._overshoot_active = False
            self._overshoot_done = False
            self._target_layer_count = CFG.MAX_LAYERS
            self._original_target_count = CFG.MAX_LAYERS
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            self._clear_needle_cycle_state()
            return False

        original = self._original_target_count

        self.ui.log(
            f"Needle: Overshoot target reached ({current_count} layers). Pruning to {original}...",
            "SUCCESS",
        )

        pruned = self.ui._prune_to_target(original)

        self._overshoot_active = False

        self._overshoot_done = True

        self._target_layer_count = original

        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")

        self._clear_needle_cycle_state()

        if pruned > 0:
            # CRITICAL: The structure has changed (layers removed). 
            # The previous best RMSE is no longer valid for this new structure.
            # Reset workflow best RMSE so the local polish can correctly report its new baseline.
            self.ui._workflow_best_rmse = float("inf")
            self.ui._best_eval_rmse = float("inf")

            self.ui.accumulated_evals += getattr(self, "_optim_n_evals", 0)

            self._schedule_task(50, lambda: self.ui.run_optim("local", keep_history=True))

            return True

        return False

    def _apply_needle_split_insertion(self, res: Dict) -> bool:
        """Apply a split insertion candidate and launch the local refinement cycle."""

        idx = res["layer_idx"]

        depth = res["depth"]

        mat_needle = res["needle_mat"]

        mat_orig = self.ui._safe_get_combo_text(idx, 0)

        if not mat_orig:
            return False

        self.ui.log(
            f"Needle: Splitting layer {idx} ({mat_orig}) at {depth:.1f}nm with {mat_needle}",
            "SUCCESS",
        )

        self.ui.front_table.blockSignals(True)

        l0 = self.ui.l0_spin.value()

        mats = self.ui._get_materials()

        n_orig = mats[mat_orig].n4

        n_needle = mats[mat_needle].n4

        qw_left = (4.0 * n_orig * depth) / l0

        self.ui.front_table.cellWidget(idx, 1).setValue(qw_left)

        self.ui.front_table.item(idx, 2).setText(f"{depth:.1f}")

        target_needle_nm = self.ui._insert_needle_split_row(idx, mat_needle, n_needle, l0)

        total_orig_thick = self.ui.ep_current[idx]

        d_right = max(0.0, total_orig_thick - depth)

        qw_right = (4.0 * n_orig * d_right) / l0

        self.ui._insert_right_split_row(idx, mat_orig, qw_right, d_right)

        self.ui.front_table.blockSignals(False)

        self.ui._update_layer_count()

        float_dtype = get_float_dtype()

        new_block = np.array([depth, target_needle_nm, d_right], dtype=float_dtype)

        self.ui.ep_current = np.concatenate([self.ui.ep_current[:idx], new_block, self.ui.ep_current[idx + 1 :]])

        if hasattr(self, "_optim_n_evals"):
            self.ui.accumulated_evals += self.ui._optim_n_evals

        self._needle_cycle_step = 1

        self.ui.run_optim("local", keep_history=True)

        return True



    def _clear_needle_cycle_state(self) -> None:
        """Clear state attributes used by the current needle optimization cycle."""

        for attr in ("_needle_cycle_step", "_needle_merit_before"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _clear_needle_search_state(self, keep_fail_count: bool = False) -> None:
        """Clear temporary needle search attributes.

        Args:
            keep_fail_count: Preserve ``_needle_fail_count`` when caller just reset it.
        """

        attrs = [
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ]

        if not keep_fail_count:
            attrs.insert(0, "_needle_fail_count")

        for attr in attrs:
            if hasattr(self, attr):
                delattr(self, attr)

