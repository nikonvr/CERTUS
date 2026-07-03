from __future__ import annotations
from certus.ui.certus_field_common import *

class CertusFieldWorkersMixin:
    """CertusFieldWorkersMixin."""



    def on_worker_finished(self, result):
        action = getattr(self.worker, "request", None) and self.worker.request.action
        synthesis_was_active = getattr(self, "_synthesis_active", False)

        # If standard execution (not synthesis) or worker failed, we reset running and enable buttons
        if not getattr(self, "_synthesis_active", False) or not result.success:
            self._is_running = False
            self.btn_calc.setEnabled(True)
            self.btn_opt.setEnabled(True)
            self.btn_mc.setEnabled(True)
            self._synthesis_active = False
            self._last_field_plot_refresh_ts = 0.0
            self._pending_field_plot_data = None
            self._pending_field_plot_msg = None
            self._field_opt_started_ts = None
            if hasattr(self, "field_opt_status"):
                self.field_opt_status.setText("Ready")
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

        if not result.success:
            if hasattr(self, "progress_widget"):
                self.progress_widget.stop(f"Error: {result.message}")

        if result.success:
            if hasattr(self, "status_label"):
                self.status_label.setText(result.message)

            if result.pareto_solutions and len(result.pareto_solutions) > 1:
                self.logger.info("--- Top Solutions (Pareto Multi-Start) ---")
                for i, s in enumerate(result.pareto_solutions):
                    self.logger.info(f"Solution {i+1}: Cost = {s['cost']:.4f}, QWOT Sum = {s['qwot_sum']:.4f}")

            plot_data = self._build_plot_data(result)
            if getattr(result, 'z_coords_mc', None) and getattr(result, 'E2_mc_runs', None):
                for target in self._get_plot_targets("field_profile", self.plot_widget):
                    target.update_mc_plot(result.z_coords_mc, result.E2_mc_runs, result.lambda_calcs)
                if plot_data.z_coords and plot_data.E2_values_list:
                    self._refresh_result_views(plot_data, clear_first=False)
            elif plot_data.z_coords and plot_data.E2_values_list:
                self._refresh_result_views(plot_data)

            if result.opt_emp_factors:
                self._skip_auto_calc = True
                self._is_updating_table = True
                try:
                    opt_types = getattr(result, "opt_layer_types", None)
                    if opt_types is not None or len(result.opt_emp_factors) != self.table_layers.rowCount():
                        FieldStackService.load_stack(self.table_layers, result.opt_emp_factors, opt_types)
                    else:
                        for r, q in enumerate(result.opt_emp_factors):
                            if self.table_layers.item(r, 1) is not None:
                                self.table_layers.item(r, 1).setText(f"{q:.4f}")
                finally:
                    self._is_updating_table = False
                self._update_thicknesses()
                
                # Record to Pareto history
                opt_t = opt_types if opt_types is not None else [i % 2 for i in range(len(result.opt_emp_factors))]
                cost_v = self._compute_cost(result.opt_emp_factors, opt_t)
                self._update_pareto_record(result.opt_emp_factors, cost_v)

                if hasattr(self, 'auto_calc_timer'):
                    self.auto_calc_timer.stop()
                QTimer.singleShot(500, lambda: setattr(self, "_skip_auto_calc", False))

            if not self._synthesis_active:
                if hasattr(self, "progress_widget"):
                    self.progress_widget.stop("Done" if result.success else f"Error: {result.message}")
                if action == "optimize" and result.pareto_solutions and len(result.pareto_solutions) > 1:
                    self._show_pareto_window()
                    self._pareto_cleanup_pending = True

                if action == "optimize":
                    if self._cleanup_thin_layers_and_reoptimize(source="optimization"):
                        return

            # Synthesis state machine
            if getattr(self, "_synthesis_active", False):
                if action == "optimize":
                    # Step A: Cleanup
                    removed = self.smart_cleanup(self.table_layers)
                    if removed > 0:
                        self.logger.info(f"[Synthesis] Smart cleanup removed {removed} layer(s).")
                    
                    # Read current stack from table
                    emp_factors = []
                    layer_types = []
                    for r in range(self.table_layers.rowCount()):
                        qwot_item = self.table_layers.item(r, 1)
                        if qwot_item is not None:
                            emp_factors.append(self._safe_float_from_item(qwot_item, 0.0))
                            layer_types.append(0 if self._normalize_layer_material(r) == "H" else 1)
                    
                    cost = self._compute_cost(emp_factors, layer_types)
                    self._update_pareto_record(emp_factors, cost)
                    self.logger.info(f"[Synthesis] Optimized cost after cleanup: {cost:.6f} (best seen: {self._synthesis_best_cost:.6f})")
                    
                    if cost < self._synthesis_best_cost - 1e-5:
                        # Improved! Update checkpoint
                        self._synthesis_best_cost = cost
                        self._synthesis_checkpoint = {
                            "emp_factors": emp_factors,
                            "layer_types": layer_types,
                            "cost": cost
                        }
                        
                        if len(emp_factors) >= 100:
                            self.logger.info(f"[Synthesis] Max layer count (100) reached. Stopping synthesis.")
                            self._synthesis_active = False
                            self._is_running = False
                            self.btn_calc.setEnabled(True)
                            self.btn_opt.setEnabled(True)
                            self.btn_mc.setEnabled(True)
                            if hasattr(self, "progress_widget"):
                                self.progress_widget.stop("Error: Max layers reached")
                        else:
                            # Start needle search
                            self.btn_calc.setEnabled(False)
                            self.btn_opt.setEnabled(False)
                            self.btn_mc.setEnabled(False)
                            try:
                                params = self._get_params()
                                self._start_worker(FieldWorkerRequest(action="needle", params=params))
                            except ValueError as e:
                                self._revert_to_synthesis_checkpoint()
                                self._synthesis_active = False
                                self._is_running = False
                                self.btn_calc.setEnabled(True)
                                self.btn_opt.setEnabled(True)
                                self.btn_mc.setEnabled(True)
                                if hasattr(self, "progress_widget"):
                                    self.progress_widget.stop("Error: Failed to get parameters")
                    else:
                        # Did not improve significantly
                        self.logger.info("[Synthesis] Cost did not improve significantly. Reverting to last best checkpoint and finishing.")
                        self._revert_to_synthesis_checkpoint()
                        self._synthesis_active = False
                        self._is_running = False
                        self.btn_calc.setEnabled(True)
                        self.btn_opt.setEnabled(True)
                        self.btn_mc.setEnabled(True)
                        if hasattr(self, "progress_widget"):
                            self.progress_widget.stop("Error: Stagnation")
                        
                elif action == "needle":
                    # Step B: Evaluate needle results
                    inserted = len(result.opt_emp_factors or []) > len(self._synthesis_checkpoint.get("emp_factors", []))
                    if inserted:
                        self.logger.info(f"[Synthesis] Needle found insertion. Growth to {len(result.opt_emp_factors)} layers. Running optimization...")
                        self.btn_calc.setEnabled(False)
                        self.btn_opt.setEnabled(False)
                        self.btn_mc.setEnabled(False)
                        try:
                            params = self._get_params()
                            params.global_opt = False  # Local refinement after needle split
                            params.synthesis_mode = True
                            self._start_worker(FieldWorkerRequest(action="optimize", params=params))
                        except ValueError as e:
                            self._revert_to_synthesis_checkpoint()
                            self._synthesis_active = False
                            self._is_running = False
                            self.btn_calc.setEnabled(True)
                            self.btn_opt.setEnabled(True)
                            self.btn_mc.setEnabled(True)
                            if hasattr(self, "progress_widget"):
                                self.progress_widget.stop("Error: Failed to get parameters")
                    else:
                        self.logger.info("[Synthesis] Needle did not find any beneficial insertion. Reverting and finishing.")
                        self._revert_to_synthesis_checkpoint()
                        self._synthesis_active = False
                        self._is_running = False
                        self.btn_calc.setEnabled(True)
                        self.btn_opt.setEnabled(True)
                        self.btn_mc.setEnabled(True)
                        if hasattr(self, "progress_widget"):
                            self.progress_widget.stop("Error: No needle insertion found")
        else:
            if hasattr(self, "field_opt_status"):
                self.field_opt_status.setText("Failed")
            show_toast(self, f"Failed: {result.message}", "error")
            self._last_field_plot_refresh_ts = 0.0
            self._pending_field_plot_data = None
            self._pending_field_plot_msg = None
            self._field_opt_started_ts = None
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

        if result.success and synthesis_was_active and not self._synthesis_active:
            if len(self.pareto_history) > 1:
                self._show_pareto_window()

    @pyqtSlot(tuple)
    def on_worker_error(self, err_tuple):
        exc_type, exc_val, exc_trace = err_tuple
        if getattr(self, "_synthesis_active", False):
            self._revert_to_synthesis_checkpoint()
            self._synthesis_active = False
        self._is_running = False
        self.btn_calc.setEnabled(True)
        self.btn_opt.setEnabled(True)
        self.btn_mc.setEnabled(True)
        if hasattr(self, "progress_widget"):
            self.progress_widget.stop(f"Error: {exc_val}")
        if hasattr(self, "field_opt_status"):
            self.field_opt_status.setText("Error")
        show_toast(self, f"Fatal error: {exc_val}", "error")
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        if self.logger:
            self.logger.error(f"Worker Error: {exc_val}\n{''.join(traceback.format_exception(exc_type, exc_val, exc_trace))}")

    def _start_worker(self, request: FieldWorkerRequest):
        if request.action != "optimize":
            self._initial_field_data = None
            self._initial_spectral_data = None

        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            return

        self.worker = FieldWorkerThread(request)
        self.worker.signals.finished.connect(self.on_worker_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.progress.connect(self.on_worker_progress)
        self.worker.signals.plot.connect(self.on_worker_plot)

        self._last_field_plot_refresh_ts = 0.0
        self._pending_field_plot_data = None
        self._pending_field_plot_msg = None
        self._field_opt_started_ts = __import__("time").monotonic()

        if hasattr(self, "progress_widget"):
            self.progress_widget.start()
        if hasattr(self, "field_opt_status"):
            mode = "PGLOBAL" if getattr(request.params, "global_opt", False) else "LOCAL"
            self.field_opt_status.setText(f"{mode} optimization running…  Gen —  Best —  Eval —  Time 0s")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        self.worker.start()

    @pyqtSlot(int, str)
    def on_worker_progress(self, progress, message):
        self.logger.info(f"[{progress}%] {message}")
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(progress, 100, phase=message)
        if hasattr(self, "field_opt_status"):
            elapsed = 0
            if hasattr(self, "_field_opt_started_ts"):
                elapsed = int(max(0.0, __import__("time").monotonic() - float(self._field_opt_started_ts)))
            self.field_opt_status.setText(f"{message} | Time {elapsed}s")
