from __future__ import annotations
from certus.ui.certus_index_spline_common import *
from certus.ui.certus_index_spline_managers_ui import Step4MeshOptimizerBuilder

class _ConfigBuilderMixin:
    """Mixin extracting _build_opt_config logic."""

class _MeshOptimizationMixin:
    """Mixin extracting _build_basic_step4_mesh_optimizer logic."""

    def _build_basic_step4_mesh_optimizer(self, parent_layout: "QVBoxLayout", style: str) -> None:
        Step4MeshOptimizerBuilder(self, parent_layout, style).build()
    def _build_opt_config(self, *, notify: bool = True) -> SplineOptConfig | None:

        if self.df is None:
            if notify:
                QMessageBox.warning(self, "Data", "Load a file first.")

            return None

        sub_name = str(self.cb_sub.currentData() or self.cb_sub.currentText())

        sid = substrate_id_from_name(sub_name)

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        # Align ``SplineOptConfig.n_seg`` with the actual mesh (12 or 14 sigma knots) **before** any worker:

        # same rule as ``make_bounds_and_x0`` (IR extension if max(lambda) > 4000 nm), plus optional Deltalambda/lambda? min (Advanced).

        _mesh_mdl = float(self.sp_mesh_min_dlam.value()) if hasattr(self, "sp_mesh_min_dlam") else 0.02

        _kmd_mesh: dict[str, float] = {}

        if _mesh_mdl > 0.0:
            _kmd_mesh["min_delta_lambda_over_lambda_mean"] = _mesh_mdl

        k_mesh_sigma = int(canonical_spline_sigma_knots(float(np.min(lam)), float(np.max(lam)), **_kmd_mesh).size)

        n_seg_mesh = max(1, k_mesh_sigma - 1)

        try:
            n_sub = _get_substrate_n_array_spline(sid, lam)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            if notify:
                QMessageBox.critical(self, "Substrate", str(e))

            return None

        has_t = "T" in self.df.columns

        has_r = "R" in self.df.columns

        use_t = self.chk_t.isChecked() and has_t

        use_r = self.chk_r.isChecked() and has_r

        if not use_t and not use_r:
            if notify:
                QMessageBox.warning(self, "Fit", "Enable at least T or R according to available columns.")

            return None

        if use_t and use_r:
            dt = DataType.BOTH

        elif use_r:
            dt = DataType.REFLECTION

        else:
            dt = DataType.TRANSMISSION

        t_raw = self.df["T"].to_numpy(dtype=np.float64) if has_t else None

        r_raw = self.df["R"].to_numpy(dtype=np.float64) if has_r else None

        t_is_ratio = bool(self.chk_trel.isChecked())

        t_exp, r_exp = prepare_exp_TR_for_fit(lam, n_sub, t_raw, r_raw, t_is_ratio=t_is_ratio)

        overlay = gui_perf_preset_only(str(self.cb_profilee.currentData() or "fast"))

        # Build config is used outside the manual auto-clean dialog context,
        # so no dialog-scoped tolerance variable is guaranteed here.
        auto_clean_tol_ui = float(getattr(self, "_auto_clean_ui_tolerance", 5e-5) or 5e-5)

        rmse_fit_lambda_nm: tuple[float, float] | None = None

        if getattr(self, "_rmse_fit_lambda_enabled", False):
            rl0 = float(self._rmse_fit_lambda_lo)

            rl1 = float(self._rmse_fit_lambda_hi)

            rmse_fit_lambda_nm = (min(rl0, rl1), max(rl0, rl1))

        _n_mono_band = default_n_mono_band_nm_from_spectrum(lam)

        d_lo_ui, d_hi_ui = self._get_thickness_bounds_nm()


        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=t_exp,
            r_exp=r_exp,
            n_sub=n_sub,
            data_type=dt,
            n_seg=int(n_seg_mesh),
            d_lo=float(d_lo_ui),
            d_hi=float(d_hi_ui),
            weight_t=float(self.w_t.value()) if use_t else 0.0,
            weight_r=float(self.w_r.value()) if use_r else 0.0,
            substrate_name=sub_name,
            t_is_ratio=t_is_ratio,
            pglobal_max_iter=0,
            polish_maxfun=int(overlay.get("polish_maxfun", 8000)),
            auto_clean_neighbor_pull_enabled=(
                bool(self.chk_auto_clean_neighbor_pull.isChecked())
                if hasattr(self, "chk_auto_clean_neighbor_pull")
                else True
            ),
            auto_clean_neighbor_pull_ratios=(
                tuple(
                    sorted(
                        {
                            float(self.sp_auto_clean_pull_r1.value()),
                            float(self.sp_auto_clean_pull_r2.value()),
                            float(self.sp_auto_clean_pull_r3.value()),
                        }
                    )
                )
                if (
                    hasattr(self, "sp_auto_clean_pull_r1")
                    and hasattr(self, "sp_auto_clean_pull_r2")
                    and hasattr(self, "sp_auto_clean_pull_r3")
                )
                else (0.10, 0.20, 0.30)
            ),
            auto_clean_neighbor_pull_local_refine_enabled=(
                bool(self.chk_auto_clean_neighbor_pull_local_refine.isChecked())
                if hasattr(self, "chk_auto_clean_neighbor_pull_local_refine")
                else False
            ),
            auto_clean_neighbor_pull_local_refine_rel_step=(
                float(self.sp_auto_clean_neighbor_pull_local_refine_step.value())
                if hasattr(self, "sp_auto_clean_neighbor_pull_local_refine_step")
                else 0.05
            ),
            # Fast-by-default advanced clean profile.
            auto_clean_top_n_sensitivity=(
                int(self.sp_auto_clean_top_n.value()) if hasattr(self, "sp_auto_clean_top_n") else 4
            ),
            auto_clean_candidate_prescreen_enabled=True,
            auto_clean_candidate_prescreen_maxfun=80,
            auto_clean_candidate_prescreen_margin_abs=max(5e-5, float(auto_clean_tol_ui) * 0.5),
            auto_clean_candidate_polish_maxfun=(
                int(self.sp_auto_clean_cand_maxfun.value()) if hasattr(self, "sp_auto_clean_cand_maxfun") else 700
            ),
            pglobal_max_feval=None,
            pglobal_max_time=None,
            pglobal_local_search_budget=None,
            pglobal_random_seed=(
                int(getattr(self, "sp_corr_seed", None).value())
                if hasattr(self, "sp_corr_seed") and int(getattr(self, "sp_corr_seed", None).value()) != 0
                else (
                    int(getattr(self, "sp_corr_boot_seed", None).value())
                    if hasattr(self, "sp_corr_boot_seed") and int(getattr(self, "sp_corr_boot_seed", None).value()) != 0
                    else None
                )
            ),
            spline_local_only=True,
            n_mono_band_nm=_n_mono_band,
            n_mono_continuous_penalty=0.008,
            n_lambda_rising_penalty_band_nm=_n_mono_band,
            n_lambda_rising_penalty_weight=3000.0,
            rmse_fit_lambda_nm=rmse_fit_lambda_nm,
            nk_profile_interp="smooth",
            corridor_profile_d_enabled=False,
            corridor_profile_d_mode=str(self.cb_corr_mode.currentData() or "abs_delta_adaptive")
            if hasattr(self, "cb_corr_mode")
            else "abs_delta_adaptive",
            corridor_profile_d_rmse_alpha=float(getattr(self, "sp_corr_alpha", None).value())
            if hasattr(self, "sp_corr_alpha")
            else 1.05,
            corridor_profile_d_rmse_abs_tolerance=float(getattr(self, "sp_corr_rmse_delta", None).value())
            if hasattr(self, "sp_corr_rmse_delta")
            else float(__import__("certus.ui.certus_index_spline_common", fromlist=["_DEFAULT_CORRIDOR_RMSE_DELTA"])._DEFAULT_CORRIDOR_RMSE_DELTA),
            corridor_scientific_nominal_enabled=(
                not hasattr(self, "chk_corr_scientific_nominal") or bool(self.chk_corr_scientific_nominal.isChecked())
            ),
            corridor_profile_d_parabola_half_window_pts=int(
                getattr(self, "_corridor_parabola_half_window_pts", 4) or 4
            ),
            corridor_profile_d_symmetric_center_mode=str(
                getattr(self, "_corridor_symmetric_center_mode", "parabola") or "parabola"
            ),
            corridor_profile_d_adaptive_rmse_ref_half_width_nm=float(
                getattr(self, "_corridor_adaptive_rmse_ref_half_width_nm", 1.5) or 1.5
            ),
            corridor_profile_d_adaptive_rmse_probe_steps_each_side=int(
                getattr(self, "_corridor_adaptive_rmse_probe_steps_each_side", 3) or 3
            ),
            corridor_profile_d_adaptive_rmse_noise_factor=float(
                getattr(self, "_corridor_adaptive_rmse_noise_factor", 3.0) or 3.0
            ),
            corridor_profile_d_adaptive_rmse_min=float(
                getattr(self, "_corridor_adaptive_rmse_min", _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)
                or _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN
            ),
            corridor_profile_d_step_nm=float(getattr(self, "sp_corr_step", None).value())
            if hasattr(self, "sp_corr_step")
            else 1.0,
            corridor_profile_d_max_span_nm=float(getattr(self, "sp_corr_span", None).value())
            if hasattr(self, "sp_corr_span")
            else 15.0,
            corridor_profile_d_polish_maxfun=(
                None
                if (hasattr(self, "sp_corr_prof_maxfun") and int(self.sp_corr_prof_maxfun.value()) <= 0)
                else int(self.sp_corr_prof_maxfun.value())
            )
            if hasattr(self, "sp_corr_prof_maxfun")
            else None,
            corridor_profile_d_lr_conf_level=float(getattr(self, "sp_corr_conf", None).value())
            if hasattr(self, "sp_corr_conf")
            else 0.95,
            corridor_profile_d_sigma_t=(
                None
                if (hasattr(self, "sp_corr_sigma") and float(self.sp_corr_sigma.value()) <= 0.0)
                else float(self.sp_corr_sigma.value())
            )
            if hasattr(self, "sp_corr_sigma")
            else None,
            corridor_profile_d_sigma_r=(
                None
                if (hasattr(self, "sp_corr_sigma") and float(self.sp_corr_sigma.value()) <= 0.0)
                else float(self.sp_corr_sigma.value())
            )
            if hasattr(self, "sp_corr_sigma")
            else None,
            corridor_profile_d_n_starts=int(getattr(self, "sp_corr_starts", None).value())
            if hasattr(self, "sp_corr_starts")
            else 1,
            corridor_profile_d_jitter_n=float(getattr(self, "sp_corr_jn", None).value())
            if hasattr(self, "sp_corr_jn")
            else 0.02,
            corridor_profile_d_jitter_L=float(getattr(self, "sp_corr_jL", None).value())
            if hasattr(self, "sp_corr_jL")
            else 0.15,
            corridor_profile_d_rng_seed=int(getattr(self, "sp_corr_seed", None).value())
            if hasattr(self, "sp_corr_seed")
            else 0,
            corridor_profile_d_sigma_hetero=bool(
                getattr(self, "chk_corr_sigma_hetero", None) and self.chk_corr_sigma_hetero.isChecked()
            )
            if hasattr(self, "chk_corr_sigma_hetero")
            else False,
            corridor_profile_d_sigma_hetero_scale=float(getattr(self, "sp_corr_hetero_scale", None).value())
            if hasattr(self, "sp_corr_hetero_scale")
            else 1.0,
            corridor_reg_sensitivity_enabled=bool(
                getattr(self, "chk_corr_reg_sens", None) and self.chk_corr_reg_sens.isChecked()
            ),
            corridor_reg_sensitivity_points=int(getattr(self, "sp_corr_reg_pts", None).value())
            if hasattr(self, "sp_corr_reg_pts")
            else 5,
            corridor_reg_sensitivity_decades=int(getattr(self, "sp_corr_reg_dec", None).value())
            if hasattr(self, "sp_corr_reg_dec")
            else 2,
            corridor_bootstrap_enabled=bool(getattr(self, "chk_corr_boot", None) and self.chk_corr_boot.isChecked()),
            corridor_bootstrap_n=int(getattr(self, "sp_corr_boot_n", None).value())
            if hasattr(self, "sp_corr_boot_n")
            else 40,
            corridor_bootstrap_seed=int(getattr(self, "sp_corr_boot_seed", None).value())
            if hasattr(self, "sp_corr_boot_seed")
            else 0,
            corridor_bootstrap_percentile=float(getattr(self, "sp_corr_boot_p", None).value())
            if hasattr(self, "sp_corr_boot_p")
            else 0.95,
            corridor_bootstrap_mode=str(getattr(self, "cb_corr_boot_mode", None).currentData() or "parametric")
            if hasattr(self, "cb_corr_boot_mode")
            else "parametric",
            corridor_bootstrap_block_len=int(getattr(self, "sp_corr_boot_block", None).value())
            if hasattr(self, "sp_corr_boot_block")
            else 1,
            corridor_bootstrap_quick_refit=bool(
                getattr(self, "chk_corr_boot_refit", None) and self.chk_corr_boot_refit.isChecked()
            )
            if hasattr(self, "chk_corr_boot_refit")
            else False,
            corridor_bootstrap_quick_refit_maxfun=int(getattr(self, "sp_corr_boot_maxfun", None).value())
            if hasattr(self, "sp_corr_boot_maxfun")
            else 4000,
            corridor_bootstrap_n_workers=int(getattr(self, "sp_corr_boot_workers", None).value())
            if hasattr(self, "sp_corr_boot_workers")
            else 1,
            spline_min_delta_lambda_over_lambda_mean=float(_mesh_mdl),
        )

        if rmse_fit_lambda_nm is not None:
            n_ok = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

            if n_ok < SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS:
                if notify:
                    QMessageBox.warning(
                        self,
                        "RMSE window",
                        f"Too few spectral points in the band ({n_ok} < {SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS}). "
                        "Widen the window or disable the limit.",
                    )

                return None

        return cfg

class _SmartInitDialogMixin:
    """Mixin extracting _show_smart_init_preview_dialog logic."""

    def _show_smart_init_preview_dialog(self, payload) -> bool:
        logger.info(
            "[INDEX_SPLINE.SMART_INIT] show requested | payload_type=%s | payload_d=%.6f | wait_event=%s",
            type(payload).__name__,
            float(getattr(payload, "d_best_nm", float("nan"))),
            getattr(self, "_preview_wait_event", None) is not None,
        )
        try:
            from certus.spline.certus_index_spline_smart_init import SmartInitPreviewManager
            manager = SmartInitPreviewManager(self, payload)
            logger.info(
                "[INDEX_SPLINE.SMART_INIT] dialog constructed | dlg_visible=%s | aux_visible=%s | main_visible=%s | k_n=%d | d=%.6f",
                bool(getattr(manager.dlg, "isVisible", lambda: False)()),
                bool(getattr(manager, "aux_dlg", None) is not None and getattr(manager.aux_dlg, "isVisible", lambda: False)()),
                bool(getattr(manager, "pw", None) is not None),
                int(getattr(manager, "k_n", 0)),
                float(getattr(manager, "preview_d_nm", float("nan"))),
            )
            code = manager.dlg.exec()
            accepted = bool(code == QDialog.DialogCode.Accepted)
            logger.info(
                "[INDEX_SPLINE.SMART_INIT] exec done | code=%s | accepted=%s | preview_ret=%s | preview_result=%s | wait_event=%s",
                int(code),
                accepted,
                getattr(self, "_preview_ret", None) is not None,
                bool(getattr(self, "_preview_result", False)),
                getattr(self, "_preview_wait_event", None) is not None,
            )
            return accepted and bool(getattr(self, "_preview_result", False))
        except Exception:
            logger.exception("[INDEX_SPLINE.SMART_INIT] dialog failed to open; aborting preview stage safely")
            return False

    def _build_smart_init_aux_dialog(
        self, parent_dlg: QDialog
    ) -> tuple[QDialog, pg.PlotCurveItem, pg.PlotCurveItem, Any, Any]:
        """Extracted from _show_smart_init_preview_dialog: builds the auxiliary n(lambda) / ln k(lambda) profile dialog."""

        aux_dlg = QDialog(parent_dlg)

        aux_dlg.setWindowTitle("Optical Profiles  n(lambda) and ln k(lambda)")

        aux_dlg.setMinimumWidth(500)

        aux_dlg.setMinimumHeight(500)

        aux_lay = QVBoxLayout(aux_dlg)

        pw_nk = CertusScientificPlot()

        pw_nk.showGrid(x=True, y=True, alpha=0.3)

        pw_nk.setLabel("bottom", "lambda (nm)")

        pw_nk.addLegend()

        attach_excel_clipboard_context_menu(pw_nk)

        aux_lay.addWidget(wrap_scientific_plot_with_toolbar(aux_dlg, pw_nk))

        # Curves for n and ln k
        curve_n = pg.PlotCurveItem(
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2), name="n(lambda)"
        )
        pw_nk.addItem(curve_n)

        # Secondary Y-axis for ln k

        main_vb = pw_nk.plotItem.vb

        p_extra = pg.ViewBox()

        pw_nk.scene().addItem(p_extra)

        pw_nk.getAxis("right").linkToView(p_extra)

        p_extra.setXLink(main_vb)

        curve_pk = pg.PlotCurveItem(
            pen=pg.mkPen(CertusTheme.ACCENT, width=2, style=Qt.PenStyle.DashLine), name="ln k(lambda)"
        )

        # Clipboard / CSV export: always k, never ln k (see certus_ui _export_y_values_for_item).

        curve_pk._certus_export_y_as_exp_k = True

        curve_pk._certus_export_name_override = "k"

        p_extra.addItem(curve_pk)

        def _get_clipboard_df():
            from certus.ui.certus_index_spline_ui import _smart_init_pw_nk_clipboard_df
            return _smart_init_pw_nk_clipboard_df(curve_n, curve_pk)
        pw_nk._certus_clipboard_df_provider = _get_clipboard_df

        def update_aux_layout() -> None:

            p_extra.setGeometry(main_vb.sceneBoundingRect())

        main_vb.sigResized.connect(update_aux_layout)

        return aux_dlg, curve_n, curve_pk, main_vb, p_extra

    def _build_smart_init_main_plot(
        self, y_lab: str
    ) -> tuple[CertusScientificPlot, pg.PlotDataItem, pg.PlotDataItem, pg.PlotDataItem]:
        """Extracted from _show_smart_init_preview_dialog: builds the main measurement vs theory plot."""

        pw = CertusScientificPlot()

        pw.setMinimumHeight(300)

        pw.showGrid(x=True, y=True, alpha=0.35)

        pw.setLabel("bottom", "sigma2 = 1/lambda2 (nm?2)")

        pw.setLabel("left", y_lab)

        pw.addLegend()

        curve_exp = pw.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush(CertusTheme.ACCENT),
            name="Measurement",
        )

        curve_theo = pw.plot(
            [],
            [],
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
            name="Theoretical (PWL n, ln k | d = slider)",
        )

        knot_markers = pw.plot(
            [],
            [],
            pen=None,
            symbol="s",
            symbolSize=9,
            symbolBrush=pg.mkBrush("#c97800"),
            name="T at knots",
        )

        return pw, curve_exp, curve_theo, knot_markers

    def _on_progress(self, v: int, msg: str) -> None:
        raw = int(v)
        if raw < 0:
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                if msg:
                    self._manual_knots_dialog.append_runtime_log(msg)
            return
        if raw < self._prog_ui_last:
            return
        self._prog_ui_last = raw

        st = msg
        # Surface a 0.1 nm thickness hint in live status without replacing
        # the existing detailed values emitted by workers.
        d_hint = float("nan")
        live_best = getattr(self, "_best_live_result", None)
        if isinstance(live_best, dict):
            try:
                d_hint = float(live_best.get("d_nm", float("nan")))
            except (TypeError, ValueError):
                d_hint = float("nan")
        if not np.isfinite(d_hint):
            last_res = getattr(self, "_last_result", None)
            if isinstance(last_res, dict):
                try:
                    d_hint = float(last_res.get("d_nm", float("nan")))
                except (TypeError, ValueError):
                    d_hint = float("nan")
        if np.isfinite(d_hint):
            st = f"{st} | d(0.1nm)~{float(d_hint):.1f} nm"
        if np.isfinite(self._best_live_rmse) and self._best_live_rmse < 1e90:
            st = f"{msg} | best displayed RMSE={self._best_live_rmse:.6f}"
            if np.isfinite(d_hint):
                st = f"{st} | d(0.1nm)~{float(d_hint):.1f} nm"
        self.lbl_status.setText(st)

        # Update the main progress bar smoothly via EnhancedProgressWidget
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                raw,
                10000,
                0,
                msg,
                "",
                animate=(str(getattr(self, "_worker_role", "") or "") != "manual_auto_clean"),
            )

        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            pct = float(raw) / 100.0
            self._manual_knots_dialog.set_runtime_progress(pct, msg)
            if msg:
                self._manual_knots_dialog.append_runtime_log(msg)

        if self.logger and (raw <= 800 or raw >= 9800 or raw >= self._log_prog_last + 700 or self._log_prog_last < 0):
            self._log_prog_last = raw

    def _display_result_prefer_best_live(self, result: dict) -> dict:
        """

        If a live snapshot recorded strictly better RMSE than the worker?s final dict,

        merge: plots / Data / Excel use that best snapshot while keeping metadata

        present only in the final result (keys missing from live).

        """

        rmse_fin = self._rmse_from_result_dict(result)

        live = self._best_live_result

        if live is None or not isinstance(live, dict):
            return result

        rmse_live = self._rmse_from_result_dict(live)

        if not (np.isfinite(rmse_live) and np.isfinite(rmse_fin)):
            return result

        tol = max(1e-12, 1e-10 * max(abs(rmse_fin), 1.0))

        if rmse_live + tol >= rmse_fin:
            return result

        snap = _snap_spline_visual_dict(live)

        merged = dict(result)

        for k, v in snap.items():
            merged[k] = v

        self._strip_worker_final_fields_inconsistent_with_live_merge(merged)

        merged["gui_display_from_best_live"] = True

        merged["gui_worker_raw_rmse"] = float(rmse_fin)

        merged["gui_best_live_rmse"] = float(rmse_live)

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: spectrum / indices / Data / export aligned on the **best** live "
                "snapshot (RMSE=%.8f) - final worker dict had RMSE=%.8f. "
                "Removing inconsistent keys (corridors, bootstrap, reg_sens, polish spline sigma variants, "
                "spectral_rmse_*, residual ln_k_lam).",
                rmse_live,
                rmse_fin,
            )

        return merged

    def _smart_init_preview_hook(self, payload: dict | SmartInitPayload) -> bool:

        if isinstance(payload, dict):
            payload = SmartInitPayload.from_dict(payload)

        """Called from the worker (QThread) after n_init/L_init logs; UI must run on the GUI thread."""

        app = QApplication.instance()

        logger.info(
            "Smart Init hook enter | payload_type=%s | app_present=%s | gui_thread=%s | current_is_gui=%s",
            type(payload).__name__,
            bool(app is not None),
            type(app.thread()).__name__ if app is not None else "n/a",
            bool(app is not None and QThread.currentThread() == app.thread()),
        )

        if app is None:
            logger.error("Smart Init hook: QApplication missing, cannot pause safely.")
            return False

        self._preview_ret = None

        if QThread.currentThread() == app.thread():
            logger.info("Smart Init hook: already on GUI thread -> direct dialog call")

            return self._show_smart_init_preview_dialog(payload)

        # Thread worker -> GUI: explicitly request preview via Qt signal.

        self._preview_payload = payload

        self._preview_result = False

        self._preview_wait_event = Event()

        logger.info(
            "Smart Init hook: emitting smart_preview_requested | payload_type=%s | has_wait_event=%s",
            type(payload).__name__,
            self._preview_wait_event is not None,
        )

        self.smart_preview_requested.emit(payload)

        # Increased timeout to 10 minutes (600s) to allow time for manual tuning

        ok = self._preview_wait_event.wait(timeout=600.0)

        logger.info(
            "Smart Init hook: wait finished | ok=%s | preview_result=%s | has_preview_ret=%s",
            bool(ok),
            bool(getattr(self, "_preview_result", True)),
            getattr(self, "_preview_ret", None) is not None,
        )

        # PyQt safety: retrieve the muted state from the main thread via instance variable.

        ret_tuple = getattr(self, "_preview_ret", None)

        if ret_tuple is not None:
            logger.info("Smart Init hook: preview returned manual values to worker")

            cfg = payload.cfg

            if cfg is not None:
                sk, ne, Le, d_nm, rmse = ret_tuple

                cfg.smart_preview_exact_sigma_knots = sk

                cfg.smart_preview_exact_n_L = (ne, Le)

                cfg.smart_preview_d_nm_override = d_nm

                cfg.smart_preview_accepted_rmse = rmse

                # Signal to the calculation engine that a manual injection is available

                cfg.smart_init_manual_force_restart = True

            self._preview_ret = None

        if not ok:
            logger.error("Smart Init preview: GUI timeout (600s), aborting optimization safely.")
            return False

        if ret_tuple is not None:
            return True

        return bool(getattr(self, "_preview_result", False))

class _UIMixin:
    """UI Area."""

