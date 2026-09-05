from __future__ import annotations
from certus.ui.certus_design_common import *


class WorkerManager:
    def __init__(self, ui):
        self.ui = ui

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

        if not spectrum_eval_run_preamble(self.ui, self.run_eval):
            return

        cfg = spectrum_eval_build_worker_cfg(self.ui, "design")

        if cfg is None:
            return

        spectrum_eval_start_worker(self.ui, cfg, _eval_start)

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

        data_for_display = spectrum_eval_on_finished_prepare_display(self.ui, data, generation_id)

        if data_for_display is None:
            return

        self.ui.last_result = data_for_display

        # Self-export if pending (triggered by Case C or time budget completion)

        if getattr(self, "_export_pending", False):
            self.ui._export_pending = False

            self.ui.orchestrator.schedule_export_results()

        res_vis = data_for_display["vis"]

        res_optim = data_for_display["optimization"]

        oblique_mode = data_for_display.get("oblique_mode", False)

        self.ui._live_curve = None

        self.ui._live_points = None

        self.ui._initial_cleared = False

        plot_targets = self.ui._get_plot_targets("spectrum", self.ui.spectrum_plot)

        spectrum_eval_plot_curves(
            self.ui,
            data_for_display=data_for_display,
            plot_targets=plot_targets,
            res_vis=res_vis,
            res_optim=res_optim,
            oblique_mode=oblique_mode,
        )

        rmse = data_for_display.get("rmse")

        n_points = self.ui.points_per_target_spin.value()

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self.ui._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.ui.front_table.rowCount()} layers) | {src_name} | Points/Target: {n_points} ({n_total} total)"

            else:
                title = (
                    f"Spectrum ({self.ui.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"
                )

        except NUMERICAL_FAULT_EXCEPTIONS:
            title = f"Spectrum ({self.ui.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        if optim_rmse_is_valid_for_log(rmse):
            title += f" - RMSE: {optim_rmse_display_string(rmse)}"

        self.ui.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self.ui, res_vis=res_vis, oblique_mode=oblique_mode)

        self.ui._plot_profile(
            data_for_display["ep"],
            self.ui._get_front_stack(),
            data_for_display.get("ep_back", np.zeros(0)),
            self.ui._get_back_stack(),
        )

        self.ui._plot_nk()

        logging.info(
            "[DESIGN._on_eval_finished] completed callback | elapsed_ms=%.1f", (time.time() - _finish_start) * 1000
        )

        self.ui.log(
            f"Evaluation OK. RMSE: {optim_rmse_display_string(rmse)}"
            if optim_rmse_is_valid_for_log(rmse)
            else "Evaluation OK.",
            "SUCCESS",
        )

        self.ui._set_busy(False)

        logging.info("[DESIGN._on_eval_finished] evaluation cycle complete | ui_ready=True")

        # Systematic Pareto update after any evaluation (manual edit or optimization)
        # data["ep"] and data["rmse"] are available from EvalWorker
        self.ui._update_pareto_record(data_for_display.get("ep"), data_for_display.get("rmse"))

        # Also update workflow best RMSE so the label doesn't become out-of-sync
        if optim_rmse_is_valid_for_log(rmse):
            workflow_best = getattr(self.ui, "_workflow_best_rmse", float("inf"))
            if rmse < workflow_best:
                self.ui._workflow_best_rmse = rmse
                if hasattr(self.ui, "best_rmse_label"):
                    self.ui.best_rmse_label.setText(f"Best RMSE: {rmse:.6f}")

        self._refresh_synthesis_kpis(rmse, data_for_display.get("ep"))

    def _refresh_synthesis_kpis(self, rmse, ep) -> None:
        """Push the freshly evaluated figures into the Synthesis tab banner."""
        banner = getattr(self.ui, "kpi_banner", None)
        if banner is None:
            return
        try:
            valid = optim_rmse_is_valid_for_log(rmse)
            banner.set_value(
                "rmse",
                optim_rmse_display_string(rmse) if valid else PLACEHOLDER,
                "good" if valid else "neutral",
            )
            banner.set_value("layers", str(self.ui.front_table.rowCount()))
            total_nm = float(np.sum(ep)) if ep is not None and len(ep) else 0.0
            banner.set_value("thickness", f"{total_nm:.1f} nm" if total_nm else PLACEHOLDER)
            best = getattr(self.ui, "_workflow_best_rmse", float("inf"))
            banner.set_value("best", f"{best:.6f}" if best != float("inf") else PLACEHOLDER)
            banner.set_value("status", "Evaluated" if valid else "No valid RMSE", "good" if valid else "warn")
        except (*NUMERICAL_FAULT_EXCEPTIONS, AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

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

        active_mode = "oblique" if self.ui.oblique_mode else "normal"
        active_targets = [
            t for t in (self.ui._get_oblique_tgts() if self.ui.oblique_mode else self.ui._get_tgts()) if t.valid()
        ]

        logging.info(
            "[DESIGN.start_optimization] starting optimization | mode=%s | keep_history=%s | active_targets=%d | samples_per_iter=%s | max_iterations=%s",
            mode,
            keep_history,
            len(active_targets),
            self.ui.n100_spin.value(),
            self.ui.global_cycles_spin.value(),
        )
        logging.info(
            "[DESIGN.start_optimization] incidence configuration | incidence=%s | active_targets=%d",
            active_mode,
            len(active_targets),
        )

        self.ui._shutdown_previous_optim_worker()

        # INTERNAL RESTART MANAGEMENT

        self.ui._is_internal_restart = keep_history

        # Guard: if user clicked STOP, refuse internal restarts

        if keep_history and getattr(self, "_workflow_stopped", False):
            self.ui.log("Workflow stopped by user, ignoring internal restart.", "WARNING")

            self.ui._set_busy(False)

            return

        if not keep_history:
            self.ui._reset_run_optim_workflow_state(mode)

        else:
            self.ui.log(f"Continuing optimization ({mode})...", "INFO")
            if getattr(self.ui.orchestrator, "_healing_phase", None) is None and not hasattr(
                self.ui.orchestrator, "_needle_cycle_step"
            ):
                self.ui._post_optim_start_time = None

        stack, mats, active, ep0, wls = self.ui._collect_run_optim_inputs()
        if stack is None:
            return

        # Calculate limits with 20% margin for display

        wls_min = self.ui._calculate_wls_min_with_margin(active)

        wls_max = self.ui._calculate_wls_max_with_margin(active)

        # Configuration

        if mode == "local":
            cfg = {
                "mode": "local",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.ui.oblique_mode else [],
                "oblique_mode": self.ui.oblique_mode,
                "oblique_tgts": active if self.ui.oblique_mode else [],
                "l0": self.ui.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": CFG.MAX_FEVAL_LOCAL,
                "n100": 50,
                "max_iter": 100,
                "local_delta_nm": 10.0,
                "use_back_coat": self.ui.back_coat_check.isChecked(),
                "back": self.ui.back_check.isChecked(),
                "ep_back": (self.ui.ep_back_current if self.ui.ep_back_current is not None else []),
                "stack_back": self.ui._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.ui.oblique_mode else None),
            }

        elif mode == "healing":
            cfg = {
                "mode": "healing",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.ui.oblique_mode else [],
                "oblique_mode": self.ui.oblique_mode,
                "oblique_tgts": active if self.ui.oblique_mode else [],
                "l0": self.ui.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": 10000,
                "n100": 500,
                "max_iter": 8,
                "use_back_coat": self.ui.back_coat_check.isChecked(),
                "back": self.ui.back_check.isChecked(),
                "ep_back": (self.ui.ep_back_current if self.ui.ep_back_current is not None else []),
                "stack_back": self.ui._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.ui.oblique_mode else None),
                "run_id": getattr(self, "_workflow_run_id", None),
                "run_context": getattr(self, "_workflow_run_ctx", None),
            }

        else:
            pre_polish = False

            if hasattr(self, "pre_polish_check"):
                pre_polish = self.ui.pre_polish_check.isChecked()

            # If needle growth is enabled, use ultra-fast global (just seed)

            # Needle will iterate and refine - no need for exhaustive global

            allow_growth = getattr(self, "allow_growth_check", None)

            needle_coupled = allow_growth and allow_growth.isChecked()

            if needle_coupled:
                g_max_feval = min(CFG.MAX_FEVAL_GLOBAL, 50000)

                g_n100 = min(self.ui.n100_spin.value(), 1500)

                g_max_iter = min(self.ui.global_cycles_spin.value(), 8)

                g_max_clusters = min(self.ui.max_clusters_spin.value(), 5)

                self.ui.log(
                    "Global+Needle: ultra-fast global (seed for needle iterations)",
                    "INFO",
                )

            else:
                g_max_feval = CFG.MAX_FEVAL_GLOBAL

                g_n100 = self.ui.n100_spin.value()

                g_max_iter = self.ui.global_cycles_spin.value()

                g_max_clusters = self.ui.max_clusters_spin.value()

            cfg = {
                "mode": "global",
                "pre_polish": pre_polish,
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.ui.oblique_mode else [],
                "oblique_mode": self.ui.oblique_mode,
                "oblique_tgts": active if self.ui.oblique_mode else [],
                "l0": self.ui.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": g_max_feval,
                "n100": g_n100,
                "max_iter": g_max_iter,
                "use_back_coat": self.ui.back_coat_check.isChecked(),
                "back": self.ui.back_check.isChecked(),
                "ep_back": (self.ui.ep_back_current if self.ui.ep_back_current is not None else []),
                "stack_back": self.ui._get_back_stack(),
                "max_clusters": g_max_clusters,
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.ui.oblique_mode else None),
                "run_id": getattr(self, "_workflow_run_id", None),
                "run_context": getattr(self, "_workflow_run_ctx", None),
            }

        # Start Worker

        self.ui._set_busy(True)

        self.ui._initialize_run_optim_progress_state(cfg, keep_history)

        if kwargs:
            cfg.update(kwargs)

        self.ui.optim_worker = OptimWorker(cfg)

        # Carry best RMSE across internal restarts so GUI doesn't regress

        if keep_history and hasattr(self, "_workflow_best_rmse"):
            self.ui.optim_worker.best_rmse_seen = self.ui._workflow_best_rmse

        self.ui.optim_thread = QThread()
        self.ui.optim_worker.moveToThread(self.ui.optim_thread)

        self.ui.optim_thread.started.connect(self.ui.optim_worker.run)

        self.ui.optim_worker.signals.finished.connect(self.ui.optim_thread.quit)
        self.ui.optim_worker.signals.finished.connect(self._on_optim_done)
        self.ui.optim_worker.signals.finished.connect(self.ui.optim_worker.deleteLater)

        self.ui.optim_worker.signals.error.connect(self.ui.optim_thread.quit)
        self.ui.optim_worker.signals.error.connect(self.ui._on_error)
        self.ui.optim_worker.signals.error.connect(self.ui.optim_worker.deleteLater)

        self.ui.optim_worker.signals.result.connect(self.ui._on_intermediate_spectrum)

        self.ui.optim_worker.signals.progress.connect(self._on_optim_progress)

        self.ui.optim_worker.signals.update_stats.connect(self._on_stats_update)

        self.ui.optim_thread.finished.connect(self.ui.optim_thread.deleteLater)

        self.ui.optim_thread.start()

    def _on_optim_progress(self, val: int, msg: str) -> None:
        """Callback for optimization progress update"""

        # val is PERCENTAGE (0-100) from OptimWorker

        # msg format: "Gen X | Evals: Y | Clusters: Z | Best: W"

        self.ui._optim_current_iter = val

        # Extract "Gen X" for display

        gen_info = "Gen ?"

        if "Gen" in msg:
            try:
                gen_info = msg.split("|")[0].strip()

            except NUMERICAL_FAULT_EXCEPTIONS:
                pass

        # Update progress widget

        self.ui.progress_widget.update(
            iteration=getattr(self, "_optim_current_iter", val),
            max_iter=getattr(self, "_optim_max_iter", 100),
            evals=getattr(self, "_optim_n_evals", 0),
            phase=getattr(self, "_optim_current_phase", "OPTIMIZATION"),
            extra_info=(f"{gen_info} | RMSE: {msg.split('Best:')[-1].strip()}" if "Best:" in msg else ""),
        )

        # Also update status label and log

        self.ui.status_label.setText(msg)

        self.ui.log(msg, "INFO")

    def _on_stats_update(self, stat_name: str, value: int) -> None:
        """Callback for stats update (MINIMA, EVAL, COLOR)"""

        if stat_name == "EVAL":
            self.ui._optim_n_evals = value

            display_value = value + getattr(self, "accumulated_evals", 0)

            # Update progress widget with new eval count

            self.ui.progress_widget.update(
                iteration=getattr(self, "_optim_current_iter", 0),
                max_iter=getattr(self, "_optim_max_iter", 100),
                evals=display_value,
                phase=getattr(self, "_optim_current_phase", "OPTIMIZATION"),
            )

        # Update stats label

        current = self.ui.stats_label.text()

        if stat_name == "MINIMA":
            parts = current.split("|")

            if len(parts) >= 1:
                parts[0] = f"♟️ {value} "

            self.ui.stats_label.setText("|".join(parts))

        elif stat_name == "EVAL":
            display_value = value + getattr(self, "accumulated_evals", 0)

            parts = current.split("|")

            if len(parts) >= 2:
                parts[1] = f" 🎲 {display_value} "

            self.ui.stats_label.setText("|".join(parts))

        elif stat_name == "COLOR":
            parts = current.split("|")

            if len(parts) >= 3:
                parts[2] = f" 🌈️ {value}"

            self.ui.stats_label.setText("|".join(parts))

    def _on_optim_done(self, d) -> None:
        return getattr(self.ui, "orchestrator", self.ui)._on_optim_done(d)

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

        if not self.ui.last_result:
            self.ui.log("Please evaluate first.", "WARNING")

            return

        if self.ui.viz_stack.currentIndex() == 0:
            self.ui.viz_stack.setCurrentIndex(1)

        self.ui.plot_tabs.setCurrentWidget(self.ui.color_plot)

        self.ui.log("Running colorimetric analysis...", "INFO")

        mats = self.ui._get_materials()

        stack = self.ui._get_front_stack()

        cfg = {
            "ep": self.ui.last_result["ep"],
            "stack": stack,
            "mats": mats,
            "n": self.ui.mc_n_spin.value(),
            "sigma": self.ui.mc_sigma_spin.value(),
            "l0": self.ui.l0_spin.value(),
            "run_id": getattr(self, "_workflow_run_id", None),
            "run_context": getattr(self, "_workflow_run_ctx", None),
        }
        if hasattr(self, "progress_widget"):
            self.ui.progress_widget.start(phase="COLORIMETRY")

        self.ui._set_busy(True)

        self.ui.col_worker = ColorWorker(cfg)

        self.ui.col_thread = QThread()
        self.ui.col_worker.moveToThread(self.ui.col_thread)

        self.ui.col_thread.started.connect(self.ui.col_worker.run)

        self.ui.col_worker.signals.finished.connect(self.ui.col_thread.quit)
        self.ui.col_worker.signals.finished.connect(self._on_col_done)
        self.ui.col_worker.signals.finished.connect(self.ui.col_worker.deleteLater)

        self.ui.col_worker.signals.error.connect(self.ui.col_thread.quit)
        self.ui.col_worker.signals.error.connect(self.ui._on_error)
        self.ui.col_worker.signals.error.connect(self.ui.col_worker.deleteLater)

        self.ui.col_worker.signals.progress.connect(self._on_col_progress)

        self.ui.col_thread.finished.connect(self.ui.col_thread.deleteLater)

        self.ui.col_thread.start()

    def _on_needle_progress(self, val: int, msg: str) -> None:
        """Callback for needle progress update"""
        if hasattr(self, "progress_widget"):
            self.ui.progress_widget.update(
                iteration=val,
                max_iter=100,
                evals=0,
                phase="NEEDLE SCAN",
                extra_info=msg,
            )
        if hasattr(self, "status_label"):
            self.ui.status_label.setText(msg)

    def _on_col_progress(self, val: int, msg: str) -> None:
        """Callback for colorimetric progress update"""
        if hasattr(self, "progress_widget"):
            self.ui.progress_widget.update(
                iteration=val,
                max_iter=100,
                evals=0,
                phase="COLORIMETRY",
                extra_info=msg,
            )
        if hasattr(self, "status_label"):
            self.ui.status_label.setText(msg)

    def _on_col_done(self, d: Dict) -> None:
        """Callback after colorimetric analysis"""

        if hasattr(self, "progress_widget"):
            self.ui.progress_widget.stop("Done")

        if d["ok"]:
            nom = d["lab_nom"]

            labs = d["labs"]

            self.ui.color_plot.plotItem.clear()

            plot_widget_plot_finite(
                self.ui.color_plot,
                labs[:, 1],
                labs[:, 2],
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=(180, 180, 180, 100),
                animate=False,
            )

            plot_widget_plot_finite(
                self.ui.color_plot,
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

            self.ui.color_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="10pt")

            self.ui.log("[DESIGN.colorimetry] analysis complete | status=success", "SUCCESS")

        self.ui._set_busy(False)

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

        self.ui._workflow_stopped = True

        if hasattr(self, "progress_widget"):
            self.ui.progress_widget.stop("Cancelled")

        self.ui.log("Stopping optimization...", "WARNING")

        try:
            if self.ui.optim_thread and self.ui.optim_thread.isRunning():
                if self.ui.optim_worker:
                    self.ui.optim_worker.request_stop()
                self.ui.optim_thread.quit()
        except RuntimeError:
            pass

        try:
            if self.ui.needle_thread and self.ui.needle_thread.isRunning():
                self.ui.needle_thread.requestInterruption()
        except RuntimeError:
            pass

        self.ui._force_idle()

        self.ui._clean_live_curves()

        self.ui._is_internal_restart = False

        # Clean ALL workflow state on user stop

        if getattr(self.ui.orchestrator, "_overshoot_active", False):
            self.ui._target_layer_count = getattr(
                self.ui.orchestrator, "_original_target_count", self.ui._target_layer_count
            )

            self.ui.orchestrator._overshoot_active = False

        self.ui.orchestrator._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_best_cost",
            "_needle_ep_backup",
            "_needle_layer_count_target",
            "_needle_layers_to_insert",
        ):
            if hasattr(self.ui.orchestrator, attr):
                setattr(self.ui.orchestrator, attr, None)

        self.ui.orchestrator._needle_retries_left = 3
        self.ui.log("Optimization stopped and state cleared.", "WARNING")

    def stop_all(self) -> None:
        """Stop all active workers. Required by CertusBaseApp._stop_all_workers()"""
        try:
            self.ui._workflow_stopped = True
            if self.ui.optim_thread and self.ui.optim_thread.isRunning():
                if self.ui.optim_worker:
                    self.ui.optim_worker.request_stop()
                self.ui.optim_thread.quit()
        except Exception:
            pass
        try:
            if self.ui.needle_thread and self.ui.needle_thread.isRunning():
                self.ui.needle_thread.requestInterruption()
        except Exception:
            pass

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

        self.ui.log("Optimization stopped.", "WARNING")

        # If stale callbacks arrive later, they can still call _set_busy(False) safely.

        # We force UI idle here to avoid sticky "Computing..." state.

        self.ui._force_idle()
