from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.core.certus_strat_config import _SPECTRUM_COUNTER

class CertusStratWorkerMixin:
    def _request_stop(self) -> None:
        """Called by reset framework before stopping workers. Sets stop flag so worker loop exits when in a run."""

        if hasattr(self, "worker") and self.worker is not None and getattr(self.worker, "isRunning", lambda: False)():
            if hasattr(self.worker, "params") and isinstance(self.worker.params, dict):
                self.worker.params["stop_requested"] = True

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
        t = threading.Thread(target=self._warmup_numba_thread_runner, daemon=True)
        t.start()
        # Fallback: unlock UI after 60s even if JIT is still compiling
        self._jit_fallback_timer = QTimer(self)
        self._jit_fallback_timer.setSingleShot(True)
        self._jit_fallback_timer.timeout.connect(self._on_jit_fallback_timeout)
        self._jit_fallback_timer.start(60_000)

    def _warmup_numba_thread_runner(self) -> None:
        try:
            _log = logging.getLogger("CERTUS")
            dummy_wl, dummy_n, dummy_thick = (
                np.array([1000.0], dtype=np.float64),
                np.array([1.5], dtype=np.float64),
                np.array([100.0], dtype=np.float64),
            )

            _log.info("[JIT-WARMUP] step 1/5 – calculate_RT_vectorized_real_HL")
            _ = calculate_RT_vectorized_real_HL(dummy_wl, dummy_n, dummy_n, dummy_n, dummy_thick)

            _log.info("[JIT-WARMUP] step 2/5 – simulate_growth_kernel")
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

            dummy_cand = np.array([550.0], dtype=np.float64)
            dummy_thick_nom = np.array([100.0, 100.0], dtype=np.float64)
            dummy_complex = np.array([2.3 + 0.0j], dtype=np.complex128)

            _log.info("[JIT-WARMUP] step 3/5 – rank_nucleation_candidates_kernel")
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

            _log.info("[JIT-WARMUP] step 4/5 – find_nucleation_adaptive_kernel")
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

            _log.info("[JIT-WARMUP] step 5/5 – validate_wavelengths_batch")
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

            _log.info("[JIT-WARMUP] all kernels compiled OK")
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
        # Cancel fallback timer – JIT finished in time
        if hasattr(self, "_jit_fallback_timer") and self._jit_fallback_timer.isActive():
            self._jit_fallback_timer.stop()

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
        if hasattr(self, "_jit_fallback_timer") and self._jit_fallback_timer.isActive():
            self._jit_fallback_timer.stop()
        if hasattr(self, "status_label"):
            self.status_label.setText("JIT Init Error – running in fallback mode")
        self.run_step0_btn.setEnabled(True)
        self.run_step2_btn.setEnabled(True)
        self.run_full_btn.setEnabled(True)

    @pyqtSlot()
    def _on_jit_fallback_timeout(self) -> None:
        """Unlock UI if JIT warmup thread never responded (hung or very slow)."""
        self.logger.warning("⚠️ JIT warmup timeout – enabling UI in fallback mode")
        if hasattr(self, "status_label"):
            self.status_label.setText("Ready (JIT pending…)")
        self.run_step0_btn.setEnabled(True)
        self.run_step2_btn.setEnabled(True)
        self.run_full_btn.setEnabled(True)

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
            if self._thread_is_running_safe(active_thread):
                self.logger.debug("[STRAT-UI] Stopping active render thread...")
                active_thread.quit()
                if not active_thread.wait(timeout_ms):
                    self.logger.warning("[STRAT-UI] Active render thread did not stop within %sms.", timeout_ms)
                    active_thread.requestInterruption()
                    active_thread.wait(min(timeout_ms, 1000))
        except (RuntimeError, AttributeError):
            pass
        finally:
            if active_thread is not None and not self._thread_is_running_safe(active_thread):
                self._active_render_thread = None

    def _stop_worker_thread(self, timeout_ms: int = 10000) -> None:

        worker = getattr(self, "worker", None)
        if worker is None:
            return

        try:
            if hasattr(worker, "params") and isinstance(worker.params, dict):
                worker.params["stop_requested"] = True

            if self._thread_is_running_safe(worker):
                self.logger.debug("[STRAT-UI] Stopping worker thread id=%s...", id(worker))
                worker.quit()
                if not worker.wait(timeout_ms):
                    self.logger.warning("[STRAT-UI] Worker thread did not stop within %sms.", timeout_ms)
                    worker.requestInterruption()
                    worker.wait(min(timeout_ms, 1000))
        except (RuntimeError, AttributeError):
            pass
        finally:
            if worker is not None and not self._thread_is_running_safe(worker):
                self.worker = None

    def _thread_is_running_safe(self, candidate: QThread | None) -> bool:
        if candidate is None:
            return False
        try:
            return bool(candidate.isRunning())
        except RuntimeError:
            return False

    def _register_worker_thread(self, thread: QThread | None, label: str) -> None:

        if thread is None:
            return

        # Purge finished or already-deleted threads to avoid accumulation.
        # Qt may delete the C++ object before Python drops the wrapper, so every
        # access must tolerate RuntimeError.
        if hasattr(self, "_stopping_threads"):
            self._stopping_threads = [t for t in self._stopping_threads if self._thread_is_running_safe(t)]

        running = self._thread_is_running_safe(thread)

        self.logger.debug("[STRAT-UI] Register worker thread label=%s id=%s running=%s", label, id(thread), running)
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
                if self._thread_is_running_safe(thread):
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
                if self._thread_is_running_safe(thread):
                    self.logger.debug("[STRAT-UI] -> quitting worker thread id=%s", id(thread))
                    thread.quit()
            except (RuntimeError, AttributeError):
                continue
        deadline = time.time() + (timeout_ms / 1000.0)
        for thread in threads:
            try:
                remaining = max(0, int((deadline - time.time()) * 1000))
                if self._thread_is_running_safe(thread) and remaining > 0:
                    if not thread.wait(remaining):
                        self.logger.warning("[STRAT-UI] Worker thread did not stop in time id=%s", id(thread))
            except (RuntimeError, AttributeError):
                continue
        self._active_worker_threads = [t for t in self._active_worker_threads if self._thread_is_running_safe(t)]

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
            try:
                if self.worker.isRunning():
                    self.worker.quit()

                    if not self.worker.wait(2000):
                        self.logger.critical(
                            "Worker did not stop within 2s in run_workflow - skipping terminate() to avoid unsafe thread kill."
                        )
            except RuntimeError:
                # The underlying C++ object may have already been deleted.
                pass
            finally:
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
            # The log used to say "PREMIUM" for every non-fast mode, so a deep run was
            # journalled as premium. A run's log must name the mode it actually ran in.
            self.logger.info(
                "[MODE] %s active | robustness_num_runs=%s | n_screen_runs=%s | dp_top_k=%s "
                "| mining_candidates_limit=%s",
                exec_mode.upper(),
                params.get("robustness_num_runs"),
                params.get("n_screen_runs"),
                params.get("dp_top_k"),
                params.get("mining_candidates_limit"),
            )

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

        self.progress_bar.start()

        if task != StratTask.NOMINAL_ANALYSIS:
            self.status_label.setText("Running Phase 1 (prerequisite)...")

            self.logger.info("AUTO-RUNNING PHASE 1: Nominal Calculation (Prerequisite)")

        else:
            self.status_label.setText("Running Phase 1 (Nominal)...")

        # Ensure params is a dict for the IPC schema validation
        params_dict = params
        if hasattr(params, "model_dump"):
            params_dict = params.model_dump()
        elif hasattr(params, "__dict__") and not isinstance(params, dict):
            # In case it's a dataclass or other object without model_dump
            import dataclasses
            if dataclasses.is_dataclass(params):
                params_dict = dataclasses.asdict(params)
            else:
                params_dict = vars(params)
                
        self.worker = WorkerThread(
            step=task,
            params=params_dict,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger if task == StratTask.FULL_PIPELINE else None,
        )
        self._register_worker_thread(self.worker, f"STRAT-{task.name.lower()}")

        self.worker.signals.update_live_growth.connect(self.on_live_growth_update)

        self.worker.signals.update_stats.connect(self.on_stats_update)

        self.worker.signals.progress.connect(self.on_progress_update)
        self.worker.signals.plot.connect(self.on_plot_ready)
        self.worker.signals.finished.connect(self.on_workflow_finished)
        self.worker.signals.error.connect(self.on_workflow_error)

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

        self.progress_bar.stop(final_message="Done")

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

        self.progress_bar.stop(final_message="Error")

    def on_progress_update(self, value: int, message: str) -> None:

        self.progress_bar.update(iteration=value, max_iter=100, phase=message, progress_pct=value)

        self.status_label.setText(message)

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
            if self._thread_is_running_safe(t):
                active_pairs.append((t, w))

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
                if self._thread_is_running_safe(t) and remaining > 0:
                    if not t.wait(remaining):
                        self.logger.warning("[STRAT-UI] Thread id=%s did not stop in time, requesting interruption...", id(t))
                        t.requestInterruption()
                        t.wait(min(remaining, 1000))
            except RuntimeError:
                pass

        if main_worker is not None and not self._thread_is_running_safe(main_worker):
            self.worker = None
        if render_thread is not None and not self._thread_is_running_safe(render_thread):
            self._active_render_thread = None
        self._active_worker_threads = [t for t in getattr(self, "_active_worker_threads", []) if self._thread_is_running_safe(t)]

