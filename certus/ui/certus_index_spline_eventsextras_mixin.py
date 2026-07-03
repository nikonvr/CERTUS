from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class CertusIndexSplineEventsExtrasMixin:
    """CertusIndexSplineEventsExtrasMixin."""

    def _warmup_numba(self) -> None:
        """UX consistency for warmup via background thread"""
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        import threading
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _warmup_numba_thread_runner(self) -> None:
        try:
            import time
            time.sleep(0.5)  # Minimal UI wait to display the toast and ensure base app is ready
            self.sig_numba_ready.emit()
        except Exception as e:
            from PyQt6.QtCore import QMetaObject, Qt
            self.logger.error(f" Numba warmup failed: {e}", exc_info=True)
            self.sig_numba_error.emit()

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("Ready (JIT Compiled)")
        self._on_numba_ready()  # Mark as ready
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("JIT Init Error")

    def _prog_reset_bar(self) -> None:

        anim = getattr(self, "_prog_anim", None)

        if anim is not None and anim.state() == QAbstractAnimation.State.Running:
            anim.stop()

        self.progress_widget.reset()

    def _cleanup_thread(self) -> None:

        worker = getattr(self, "_worker", None)

        if worker is None:
            return

        if worker.isRunning():
            try:
                if hasattr(worker, "stop"):
                    worker.stop()

            except (RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            # Short cooperative window (heavy RMSE grids can exceed 100 ms).
            for _ in range(80):
                if not worker.isRunning():
                    break

                worker.wait(50)

            if worker.isRunning() and self.logger:
                self.logger.warning("Worker thread still running after ~4s wait; queued deleteLater()")

        try:
            worker.deleteLater()

        except RuntimeError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self._worker = None

    def _prepare_worker_restart(self) -> None:
        """Stop current worker cooperatively before creating a new stop event."""
        prev_stop = getattr(self, "_stop_event", None)
        if isinstance(prev_stop, Event):
            prev_stop.set()
        self._cleanup_thread()
        self._stop_event = Event()

    @staticmethod
    def _rmse_from_result_dict(d: dict) -> float:
        """RMSE displayable for comparison (priority to  rmse  key, else ?MSE)."""

        r = d.get("rmse")

        if r is not None and np.isfinite(float(r)):
            return float(r)

        m = float(d.get("mse", float("nan")))

        if np.isfinite(m):
            return float(np.sqrt(max(m, 0.0)))

        return float("inf")

    @staticmethod
    def _runtime_metrics_from_result_dict(d: dict | None) -> tuple[float, float]:

        if not isinstance(d, dict):
            return float("nan"), float("nan")

        try:
            d_nm = float(d.get("d_nm", float("nan")))

        except (TypeError, ValueError):
            d_nm = float("nan")

        rmse = CertusIndexSplineApp._rmse_from_result_dict(d)

        if not np.isfinite(rmse):
            rmse = float("nan")

        return d_nm, rmse

    @staticmethod
    def _format_lambda_knots_for_log(lambda_knots_nm: Any, *, precision: int = 1, max_items: int = 6) -> str:
        from certus.spline.spline_pipeline_utils import _format_lambda_knots_nm_for_log
        return _format_lambda_knots_nm_for_log(lambda_knots_nm, precision=precision, max_items=max_items)

    @staticmethod
    def _strip_worker_final_fields_inconsistent_with_live_merge(merged: dict[str, Any]) -> None:
        """Removes fields from the **final** worker dict that no longer describe the displayed curves after merging

        with the best live snapshot (n_lam/k_lam/d/x come from the live one).

        Without this: corridors, bootstrap, reg scan, polish spline sigma (seg_spline_sigma), spectral RMSEs

        and ln_k_lam would remain aligned with the final solution - resulting in wrong Excel export / metadata."""

        _variant_nk = (
            "n_lam_seg_spline_sigma",
            "k_lam_seg_spline_sigma",
        )

        for k in list(merged.keys()):
            if k.startswith("profile_d_"):
                merged.pop(k, None)

            elif k.startswith("corridor_"):
                merged.pop(k, None)

            elif k.startswith("boot_"):
                merged.pop(k, None)

            elif k.startswith("reg_sens"):
                merged.pop(k, None)

            elif k.startswith("spectral_rmse_"):
                merged.pop(k, None)

        for k in _variant_nk:
            merged.pop(k, None)

        merged.pop("ln_k_lam", None)

        merged.pop("spectral_rmse", None)

        merged.pop("d_nm_seg_spline_sigma", None)

    def _on_worker_err(self, msg: str) -> None:
        role = str(getattr(self, "_worker_role", "") or "")
        manual_pipeline_roles = (
            "manual_sigma_insert",
            "manual_autoshift",
            "manual_auto_add_one",
            "manual_auto_clean",
            "manual_repartition_log",
            "manual_repartition_sigma",
        )
        manual_dlg = getattr(self, "_manual_knots_dialog", None)

        if str(getattr(self, "_worker_role", "") or "") == "rmse_grid":
            self._set_corridor_grid_busy(False)

            self._corridor_rmse_grid_live_t0 = float("nan")
            self._corridor_rmse_live_last_plot_ts = float("nan")

            self._worker_role = "idle"

        uninstall_skeleton(self.tabs_main)
        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        if isinstance(msg, tuple) and len(msg) == 3:
            s_msg = str(msg[1])

            logger.error(msg[2])

            if self.logger:
                self.logger.error("Optimization: %s", s_msg)

        else:
            s_msg = str(msg)

            logger.error(s_msg)

            if self.logger:
                self.logger.error("Optimization: %s", s_msg)

        if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
            manual_dlg.set_runtime_busy(False)
            manual_dlg.set_runtime_progress(100.0, "Error")
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                getattr(manual_dlg, "_base_sigma_knots", np.asarray([], dtype=np.float64)),
                manual_dlg.selected_sigma_knots(),
            )
            manual_dlg.append_runtime_log(
                CertusIndexSplineApp._manual_mesh_change_log_line("Mesh at failure", mesh_summary)
            )
            manual_dlg.append_runtime_log(f"Re-optimization error: {s_msg}")

        QMessageBox.critical(self, "Optimization error", s_msg)

        self._worker_role = "idle"
        self._corridor_auto_refine_plan = None

        self._refresh_post_optimization_option_controls()

    @staticmethod
    def _is_rmse_d_grid_worker_finalize_dict(r: object) -> bool:
        """True if ``r`` is the final dict from the RMSE(d) grid worker (not a full solver result)."""
        if not isinstance(r, dict):
            return False
        st = str(r.get("profile_d_status", ""))
        return st in {"manual_grid", "manual_grid_empty"}

    def _merge_rmse_grid_promotion_into_nominal(self, promoted: dict, *, adoption_log_tag: str) -> None:
        """Merges a promoted dict (global-opt or grid minimum) into ``_last_result`` and refreshes the UI."""
        prev_nominal = dict(self._last_result) if isinstance(self._last_result, dict) else {}
        merged_nominal = dict(prev_nominal)
        merged_nominal.update(promoted)
        if merged_nominal.get("lam_nm") is None:
            lam_prev = prev_nominal.get("lam_nm")
            if lam_prev is not None:
                merged_nominal["lam_nm"] = np.asarray(lam_prev, dtype=np.float64).ravel().copy()
            elif self.df is not None and "lambda" in self.df.columns:
                merged_nominal["lam_nm"] = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid [%s] | promoted result missing lam_nm; fallback applied.",
                    adoption_log_tag,
                )
        self._last_result = merged_nominal
        if self.logger:
            rmse_after_replace = self._rmse_from_result_dict(self._last_result)
            self.logger.info(
                "GUI RMSE(d) regular grid [%s] | nominal merged | rmse_after_replace=%s | d_nm=%s",
                adoption_log_tag,
                (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a"),
                (
                    f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                    if np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                    else "n/a"
                ),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: adoption grille RMSE(d) → nominal _last_result",
                self._last_result.get("d_nm"),
                detail=(
                    "tag="
                    + str(adoption_log_tag)
                    + " rmse="
                    + (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a")
                ),
            )
        try:
            self._plot_result(self._last_result, plot_source="promotion_grille_rmse")
            self._refresh_data_table()
        except (ValueError, TypeError, AttributeError, RuntimeError):
            logger.debug("Failed to refresh plot after RMSE grid promotion", exc_info=True)

    def _start_curve_minimum_deep_refit(self, seed: dict) -> bool:
        """Launches ``quick_pwlnk_refit_result_dict`` (L-BFGS-B on d + nodes) from the grid minimum seed."""
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Optimization", "A calculation is already in progress.")
            return False
        cfg = self._last_run_cfg
        if cfg is None:
            cfg = self._build_opt_config(notify=False)
        if cfg is None:
            QMessageBox.warning(
                self,
                "Optimization",
                "No optimization configuration available (run a fit first).",
            )
            return False
        cfg = self._cfg_with_result_substrate(cfg, seed)
        polish = int(getattr(cfg, "polish_maxfun", 10000) or 10000)
        deep_maxfun = int(max(4000, min(24000, int(round(1.5 * float(polish))))))
        CertusIndexSplineApp._prepare_worker_restart(self)
        self._worker = GenericWorker(
            _worker_curve_minimum_deep_refit,
            cfg,
            dict(seed),
            self._stop_event,
            deep_maxfun=deep_maxfun,
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "curve_min_deep"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._prog_ui_last = 0
        self._prog_reset_bar()
        sd = float(seed.get("d_nm", float("nan")))
        self.lbl_status.setText(
            f"Grid minimum? Deep L-BFGS-B polish (d+nodes, maxfun={deep_maxfun}) from d={sd:.3f} nm"
        )
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | start | deep_maxfun=%d | seed_d_nm=%s",
                deep_maxfun,
                (f"{sd:.6f}" if np.isfinite(sd) else "n/a"),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: polish profond depuis minimum grille RMSE(d)",
                seed.get("d_nm"),
                detail=f"deep_maxfun={deep_maxfun}",
            )
        self._worker.start()
        return True

    def _wire_worker_signals(self, progress_fn) -> None:
        """Wire the standard progress/live callbacks for a worker run."""
        self._worker.kwargs["progress_cb"] = progress_fn
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_live_update)

        def _manual_live_metrics(payload: object) -> None:
            if not isinstance(payload, dict):
                return
            dialog = getattr(self, "_manual_knots_dialog", None)
            if isinstance(dialog, ManualSigmaKnotDialog):
                d_live = float(payload.get("d_nm", float("nan")))
                rmse_live = float(payload.get("rmse", float("nan")))
                dialog.set_runtime_metrics(d_live, rmse_live)
                self._refresh_manual_dialog_preview(dialog, payload)

        self._worker.signals.live.connect(_manual_live_metrics)

    def _set_worker_running_state(self, running: bool) -> None:
        """Toggle UI controls between running/idle state."""
        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(running)
        self._refresh_post_optimization_option_controls()
        if running:
            self._prog_ui_last = 0
            self._prog_reset_bar()

    @staticmethod
    def _control_group_box_style() -> str:

        return (
            f"QGroupBox {{ font-weight: bold; border: 1px solid {CertusTheme.BORDER}; "
            f"border-radius: 6px; margin-top: 12px; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; "
            f"color: {CertusTheme.TEXT_MAIN}; }}"
        )

    def _update_persistent_nk_monitor(
        self, lam_arr: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray, d_nm: float | None = None
    ) -> None:

        mon = getattr(self, "_live_nk_monitor", None)

        if mon is None:
            return

        try:
            if hasattr(mon, "update_indices"):
                mon.update_indices(lam_arr, n_arr, k_arr, d_nm)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("_update_persistent_nk_monitor failed", exc_info=True)

    def _save_undo_state(self) -> None:
        """Store current state before computation in undo stack (Ctrl+Z via CertusBaseApp)."""

        if not hasattr(self, "undo_stack"):
            return

        d_lo_ui, d_hi_ui = self._get_thickness_bounds_nm()

        state = SplineState(
            result=dict(self._last_result) if self._last_result is not None else None,
            d_lo=float(d_lo_ui),
            d_hi=float(d_hi_ui),
            wt=self.w_t.value(),
            wr=self.w_r.value(),
        )

        self.undo_stack.append(state)

        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(True)

    def _get_thickness_bounds_nm(self) -> tuple[float, float]:

        d_nom = float(self.d_lo.value()) if hasattr(self, "d_lo") else float("nan")

        d_pm = float(self.d_hi.value()) if hasattr(self, "d_hi") else float("nan")

        if not np.isfinite(d_nom):
            d_nom = 0.5 * float(SIO2_DEFAULT_D_LO_NM + SIO2_DEFAULT_D_HI_NM)

        if not np.isfinite(d_pm):
            d_pm = 0.5 * float(abs(SIO2_DEFAULT_D_HI_NM - SIO2_DEFAULT_D_LO_NM))

        d_pm = max(0.1, float(abs(d_pm)))

        d_lo = max(1.0, float(d_nom - d_pm))

        d_hi = max(d_lo + 0.1, float(d_nom + d_pm))

        return float(d_lo), float(d_hi)

    def _set_thickness_bounds_ui(self, d_lo: float, d_hi: float) -> None:

        dlo = float(min(d_lo, d_hi))

        dhi = float(max(d_lo, d_hi))

        d_nom = 0.5 * (dlo + dhi)

        d_pm = max(0.1, 0.5 * (dhi - dlo))

        if hasattr(self, "d_lo"):
            self.d_lo.setValue(float(d_nom))

        if hasattr(self, "d_hi"):
            self.d_hi.setValue(float(d_pm))

    def _setup_logger(self, name: str) -> None:
        """Route core logs (CERTUS, CERTUS_INDEX_SPLINE) to the same GUI queue."""

        from certus.core.certus_core import QueueHandler

        super()._setup_logger(name)

        qh = next(
            (h for h in (self.logger.handlers or []) if isinstance(h, QueueHandler)),
            None,
        )

        if qh is None:
            return

        for ln in ("CERTUS", "CERTUS_INDEX_SPLINE"):
            lg = logging.getLogger(ln)

            if any(
                isinstance(h, QueueHandler) and getattr(h, "log_queue", None) is self.log_queue for h in lg.handlers
            ):
                continue

            lg.setLevel(logging.INFO)

            lg.addHandler(qh)

    def _create_empty_context_widget(self, message: str) -> QWidget:
        """Creates a waiting/info page for the contextual settings panel."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-style: italic; font-size: 11px;")
        lbl.setWordWrap(True)
        lay.addStretch(1)
        lay.addWidget(lbl)
        lay.addStretch(1)
        return w

    def _k_crosshair_formatter(self, x: float, y_on_curve: float | None, y_mouse: float) -> str:
        """Formats the cursor display for logarithmic scales of k."""
        # Priority to the interpolated value on the curve (already in physical k in our plots).
        y_val = y_on_curve if y_on_curve is not None else y_mouse
        k_val = float("nan")
        if y_val is not None and np.isfinite(float(y_val)):
            y_num = float(y_val)
            # Compat: if a log10 coordinate is provided (<=0), we convert back.
            k_val = y_num if y_num > 0.0 else float(10.0**y_num)
        if not np.isfinite(k_val):
            return f"x = {x:.2f}, k = n/a"
        return f"x = {x:.2f}, k = {k_val:.3e}"

    def _get_log_widget(self) -> Any | None:

        return getattr(self.log_panel, "log_text", None) if hasattr(self, "log_panel") else None

    def _restore_simple_auto_uncertainty_pref(self) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        v = s.value(_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY)

        if v is None:
            self._simple_auto_uncertainty = True

        else:
            self._simple_auto_uncertainty = bool(v)

    def _persist_simple_auto_uncertainty_pref(self) -> None:

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY, bool(getattr(self, "_simple_auto_uncertainty", True))
        )

    def _apply_sio2_default_fit_parameters(self) -> None:
        """Thickness bounds, RMSE lambda window and nk interpolation for thin SiO2 layers (cf. TSIO2 / sapphire logs)."""

        self._set_thickness_bounds_ui(float(SIO2_DEFAULT_D_LO_NM), float(SIO2_DEFAULT_D_HI_NM))

        self._rmse_fit_lambda_enabled = bool(SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED)

        self._rmse_fit_lambda_lo = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

        self._rmse_fit_lambda_lo_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

    def _update_epured_visibility(self) -> None:

        if not hasattr(self, "_stack_box4_adv"):
            return

        epure = bool(getattr(self, "_simple_auto_uncertainty", True))

        self._stack_box4_adv.setCurrentIndex(0 if epure else 1)

    def _build_tab_spectrum(self) -> QWidget:
        # Controls are moved to the context_stack on the right
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        row_axis = QHBoxLayout()
        row_axis.addWidget(QLabel("X Axis:"))
        self.cb_spectrum_xmode = QComboBox()
        self.cb_spectrum_xmode.addItem("Lambda (nm)", "lambda")
        self.cb_spectrum_xmode.addItem("Sigma (nm?1)", "sigma")
        self.cb_spectrum_xmode.addItem("Sigma2 (nm?2)", "sigma2")
        self.cb_spectrum_xmode.currentIndexChanged.connect(self._on_spectrum_x_mode_changed)
        row_axis.addWidget(self.cb_spectrum_xmode)
        row_axis.addStretch(1)
        ctx_lay.addLayout(row_axis)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_T = CertusScientificPlot(title="Spectrum", y_label="T, R or T/T_sub", x_label="lambda (nm)")
        self.plot_T.showGrid(x=True, y=True, alpha=0.25)
        self.plot_T._certus_context_menu_augment_fn = self._spectrum_plot_context_menu_augment
        self.plot_T._certus_crosshair_label_fn = self._spectrum_T_crosshair_formatter
        lay.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_T), 1)

        return panel

    @staticmethod
    def _robust_interval_from_local_quadratic(
        d_s: np.ndarray,
        r_s: np.ndarray,
        i_best: int,
        delta_rmse: float,
        half_window_pts: int,
    ) -> tuple[bool, float, float, float, float]:

        fit = _fit_local_quadratic_rmse_profile(
            d_s,
            r_s,
            i_best,
            half_window_pts,
            delta_rmse,
        )

        if not bool(fit.get("ok", False)):
            return False, float("nan"), float("nan"), float("nan"), float("nan")

        return (
            True,
            float(fit.get("d_lo", float("nan"))),
            float(fit.get("d_hi", float("nan"))),
            float(fit.get("slope_at_anchor", float("nan"))),
            float(fit.get("curvature", float("nan"))),
        )

    def _detach_current_plot(self) -> None:

        w = self.tabs_main.currentWidget()

        if w is None:
            return

        plots = w.findChildren(CertusScientificPlot)

        if not plots:
            QMessageBox.information(self, "Detach", "No scientific plot in this tab.")

            return

        tab_name = self.tabs_main.tabText(self.tabs_main.currentIndex())

        self.open_detached_certus_plot(plots[0], title=f"{self.APP_NAME}  {tab_name}")

    @staticmethod
    def _lam_uniform_grid_nm(lo_h: float, hi_h: float, step: float) -> np.ndarray:
        return _lam_uniform_grid(lo_h, hi_h, step)

    @staticmethod
    def _lam_piecewise_report_grid_nm(lo: float, hi: float) -> np.ndarray:
        """2 nm step on (lambda_min, 400), 5 nm on )400, 1200), 10 nm beyond (nm)."""

        if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
            return np.array([], dtype=np.float64)

        parts: list[np.ndarray] = []

        a, b = float(lo), float(min(hi, 400.0))

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 2.0))

        a, b = float(max(lo, 400.0)), float(min(hi, 1200.0))

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 5.0))

        a, b = float(max(lo, 1200.0)), float(hi)

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 10.0))

        if not parts:
            return np.array([0.5 * (lo + hi)], dtype=np.float64)

        return np.unique(np.concatenate(parts))

    @staticmethod
    def _fmt_n_data_tab(nv: float) -> str:

        if not np.isfinite(nv):
            return ""

        return f"{float(nv):.4f}"

    @staticmethod
    def _fmt_k_data_tab(kv: float) -> str:

        if not np.isfinite(kv) or kv < 0:
            return ""

        v = float(kv)

        if v == 0.0:
            return "0"

        return f"{v:.2e}"

    @staticmethod
    def _interp_preview_axis(xs: np.ndarray, ys: np.ndarray, xq: float) -> float:

        xs = np.asarray(xs, dtype=np.float64).ravel()

        ys = np.asarray(ys, dtype=np.float64).ravel()

        m = np.isfinite(xs) & np.isfinite(ys)

        if int(np.count_nonzero(m)) < 2:
            return float("nan")

        xv, yv = xs[m], ys[m]

        o = np.argsort(xv, kind="mergesort")

        xv, yv = xv[o], yv[o]

        xf = float(xq)

        if xf < float(xv[0]) or xf > float(xv[-1]):
            return float("nan")

        return float(np.interp(xf, xv, yv))

    @staticmethod
    def _vb_mid_y_plot(w: CertusScientificPlot) -> float:

        try:
            y0, y1 = w.plotItem.vb.viewRange()[1]

            return 0.5 * (float(y0) + float(y1))

        except NUMERICAL_FAULT_EXCEPTIONS:
            return 0.0

    def _apply_cell_style(self, item: QTableWidgetItem, val: float) -> None:
        """Standard styling logic for table items."""
        pass  # Reserved for future color-coding or specific formatting

    def _on_trel_plot_refresh(self) -> None:

        if self.df is None:
            return

        if hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        self._plot_data_raw()

    def _on_profilee_changed(self) -> None:

        key = str(self.cb_profilee.currentData() or "fast")

        pr = SPLINE_PERF_PRESETS.get(key, {})

        v = pr.get("pglobal_max_iter")

        if v is not None:
            self.sp_pg_iter.blockSignals(True)

            self.sp_pg_iter.setValue(int(v))

            self.sp_pg_iter.blockSignals(False)

    def _add_curve(
        self,
        widget: "pg.PlotWidget",
        x: np.ndarray,
        y: np.ndarray,
        color: str,
        name: str,
        is_scatter: bool = False,
        *,
        crosshair_primary: bool = False,
        pen: Any | None = None,
    ) -> bool:
        # UX: If displaying k on a LOG scale, we linearize the provided log10 data
        if widget in [
            getattr(self, "plot_k", None),
            getattr(self, "plot_k_corridor", None),
            getattr(self, "plot_k_nl", None),
        ]:
            y = 10.0**y

        xf, yf = sanitize_xy_for_plot(x, y)

        if xf.size == 0:
            return False

        if is_scatter:
            _plot_spectrum_raw_scatter(widget, xf, yf, color=color, name=name)

        else:
            p = pen if pen is not None else pg.mkPen(color, width=2)

            curve = plot_widget_plot_finite(widget, xf, yf, pen=p, name=name)

            if curve is not None and crosshair_primary:
                setattr(curve, "_certus_crosshair_primary", True)
                if hasattr(curve, "setZValue"):
                    try:
                        curve.setZValue(10)
                    except Exception:
                        pass

        return True

    def _plot_data_raw(self) -> None:

        if self.df is None:
            return

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        x_plot, x_lbl = self._transform_spectrum_x(lam)

        self.plot_T.clear()
        self._spectrum_clear_theory_probe()

        any_curve = False

        if "T" in self.df.columns:
            y_raw = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

            y = y_raw

            tlabel = "T/Tsub exp" if self.chk_trel.isChecked() else "T exp"

            if self._add_curve(self.plot_T, x_plot, y, CertusTheme.PRIMARY, tlabel, True):
                any_curve = True

        if "R" in self.df.columns:
            y_raw = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

            y = y_raw

            rlabel = "R/Tsub exp" if self.chk_trel.isChecked() else "R exp"

            if self._add_curve(self.plot_T, x_plot, y, CertusTheme.SECONDARY, rlabel, True):
                any_curve = True

        if any_curve:
            self.plot_T.autoRange()

        self._apply_spectrum_x_axis_label(x_lbl)

        self._apply_spectrum_plot_title(None)

        self._update_rmse_fit_region_overlay()

    def _remove_rmse_fit_region_overlay(self) -> None:

        items = getattr(self, "_rmse_fit_overlay_items", None) or []

        for ri in items:
            if ri is None:
                continue

            try:
                self.plot_T.removeItem(ri)

            except (AttributeError, RuntimeError):
                logger.debug("_remove_rmse_fit_region_overlay: removeItem failed", exc_info=True)

        self._rmse_fit_overlay_items = []

    def _sync_rmse_lambda_bounds_from_file(self) -> None:

        if self.df is None or "lambda" not in self.df.columns:
            return

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        lam = lam[np.isfinite(lam)]

        if lam.size == 0:
            return

        lo, hi = float(np.min(lam)), float(np.max(lam))

        self._rmse_fit_lambda_lo_default = lo

        self._rmse_fit_lambda_hi_default = hi

        if not self._rmse_fit_lambda_enabled:
            self._rmse_fit_lambda_lo = lo

            self._rmse_fit_lambda_hi = hi

    def _on_stop(self) -> None:

        self._stop_event.set()

        self.lbl_status.setText("Stop requested...")

    def _on_corr_mode_changed(self, _idx: int = 0) -> None:
        """Show alpha vs Delta RMSE spinboxes according to corridor mode (LR hides both thresholds)."""

        if not hasattr(self, "cb_corr_mode"):
            return

        m = str(self.cb_corr_mode.currentData() or "abs_delta_adaptive")

        show_alpha = m == "alpha"

        show_delta = m in ("abs_delta", "abs_delta_adaptive")

        if hasattr(self, "sp_corr_alpha"):
            self.sp_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "lbl_corr_alpha"):
            self.lbl_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "lbl_corr_rmse_delta"):
            self.lbl_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setVisible(show_delta)

    def _refresh_post_optimization_option_controls(self, *_args) -> None:

        unlocked = isinstance(getattr(self, "_last_result", None), dict)

        role = str(getattr(self, "_worker_role", "idle") or "idle")

        controls_enabled = bool(unlocked and role == "idle")

        if hasattr(self, "btn_corridor_toggle"):
            self.btn_corridor_toggle.setEnabled(controls_enabled)

        if hasattr(self, "btn_manual_knots_toggle"):
            self.btn_manual_knots_toggle.setEnabled(controls_enabled)

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.setEnabled(False)

        if hasattr(self, "_stepper"):
            if controls_enabled:
                self._stepper.set_step(6)
            elif getattr(self, "df", None) is not None:
                self._stepper.set_step(1)
            else:
                self._stepper.set_step(0)

        self._refresh_corridors_gui_state_labels()

    @staticmethod
    def _result_uses_split_mesh(result: dict | None) -> bool:

        if not isinstance(result, dict):
            return False
        if bool(result.get("split_knots_refine")):
            return True
        if "sigma_knots_n" in result or "sigma_knots_L" in result:
            return True
        x_encoding = str(result.get("x_encoding", "")).strip().lower()
        return x_encoding.startswith("split_")

    @staticmethod
    def _status_iteration_metric(
        display_dict: dict,
        fallback_dict: dict,
    ) -> tuple[str, int]:

        for key, label in (
            ("nit_total", "evals [global optimizer]"),
            ("nit_combined", "evals [global optimizer]"),
            ("nfev_lbfgsb", "evals [L-BFGS-B local-polish]"),
            ("nit_polish", "iters [cubic-spline-sigma-polish]"),
        ):
            raw = display_dict.get(key, fallback_dict.get(key, None))
            if raw is None:
                continue
            try:
                return label, max(0, int(raw))
            except (TypeError, ValueError):
                continue
        return "iters [cubic-spline-sigma-polish]", 0

    @staticmethod
    def _format_post_optimization_status(display: dict, fallback_result: dict | None = None) -> str:

        display_dict = display if isinstance(display, dict) else {}
        fallback_dict = fallback_result if isinstance(fallback_result, dict) else display_dict
        rmse_tag = (
            "RMSE (lambda band)" if display_dict.get("rmse_fit_lambda_nm") is not None else "RMSE (full spectrum)"
        )
        mse_value = float(display_dict.get("mse", 0.0))
        d_nm_value = float(display_dict.get("d_nm", float("nan")))
        d_01_txt = f"{float(d_nm_value):.1f}" if np.isfinite(float(d_nm_value)) else "n/a"
        iter_label, iter_value = CertusIndexSplineApp._status_iteration_metric(
            display_dict,
            fallback_dict,
        )
        return (
            f"{rmse_tag}  {np.sqrt(max(mse_value, 0.0)):.6f} | d={d_nm_value:.2f} nm "
            f"(d(0.1nm)={d_01_txt} nm) | "
            f"{iter_label}={iter_value}"
        )

    @staticmethod
    def _post_optimization_ready_status(base_status: str) -> str:

        status = str(base_status or "").strip()
        hint = "Available actions: Manual knots / Corridors"
        if not status:
            return hint
        if hint in status:
            return status
        return f"{status} | {hint}"

    def _rmse_fit_lambda_tuple_for_report(self) -> tuple[float, float] | None:
        """lambda window for display/export (result first, else GUI)."""

        rw = None

        if self._last_result is not None:
            rw = self._last_result.get("rmse_fit_lambda_nm")

        if rw is None and getattr(self, "_rmse_fit_lambda_enabled", False):
            rl0 = float(self._rmse_fit_lambda_lo)

            rl1 = float(self._rmse_fit_lambda_hi)

            rw = (min(rl0, rl1), max(rl0, rl1))

        return rw
