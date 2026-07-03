from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class CertusIndexSplineManualMeshMixin:
    """CertusIndexSplineManualMeshMixin."""

    @staticmethod
    def _sorted_finite_sigma_knots(sigma_knots: Any) -> np.ndarray:
        from certus.spline.spline_pipeline_utils import _sorted_finite_sigma_knots_for_log
        return _sorted_finite_sigma_knots_for_log(sigma_knots)

    @staticmethod
    def _sigma_knots_to_lambda_nm(sigma_knots: Any) -> np.ndarray:
        from certus.spline.spline_pipeline_utils import _sigma_knots_to_lambda_nm_for_log
        return _sigma_knots_to_lambda_nm_for_log(sigma_knots)

    @staticmethod
    def _sigma_knot_difference_with_tolerance(source_sigma_knots: Any, reference_sigma_knots: Any) -> np.ndarray:
        from certus.spline.spline_pipeline_utils import _sigma_knot_difference_with_tolerance_for_log
        return _sigma_knot_difference_with_tolerance_for_log(source_sigma_knots, reference_sigma_knots)

    @staticmethod
    def _summarize_manual_mesh_change(before_sigma_knots: Any, after_sigma_knots: Any) -> dict[str, Any]:
        from certus.spline.spline_pipeline_utils import _sigma_mesh_change_summary_for_log
        return _sigma_mesh_change_summary_for_log(before_sigma_knots, after_sigma_knots)

    @staticmethod
    def _manual_mesh_change_log_line(label: str, summary: dict[str, Any]) -> str:

        k_before = int(summary.get("k_before", 0))

        k_after = int(summary.get("k_after", 0))

        delta_k = int(summary.get("delta_k", 0))

        before_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("before_lambda_knots_nm"))

        after_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("after_lambda_knots_nm"))

        removed_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("removed_lambda_knots_nm"))

        added_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("added_lambda_knots_nm"))

        removed_count = int(np.asarray(summary.get("removed_lambda_knots_nm", []), dtype=np.float64).size)

        added_count = int(np.asarray(summary.get("added_lambda_knots_nm", []), dtype=np.float64).size)

        return (
            f"{str(label).strip()} | K {k_before}->{k_after} (Delta {delta_k:+d}) | "
            f"before={before_txt} | after={after_txt} | removed={removed_count} {removed_txt} | "
            f"added={added_count} {added_txt}"
        )

    def _can_offer_manual_extra_knots(self, result: dict) -> bool:
        """True if conditions allow proposing manual extra knot placement."""
        if not isinstance(result, dict):
            return False
        sk = result.get("sigma_knots")
        if sk is None:
            if self.logger:
                self.logger.info("Manual nodes: result missing 'sigma_knots'.")
            return False
        sk_a = np.asarray(sk, dtype=np.float64).ravel()
        if sk_a.size < 2:
            if self.logger:
                self.logger.info(f"Manual nodes: sigma_knots size ({sk_a.size}) < 2.")
            return False
        if "sigma_knots_n" in result or "sigma_knots_L" in result:
            if self.logger:
                self.logger.info(
                    "Manual nodes: result has split n/k meshes (sigma_knots_n/L present). "
                    "Manual insertion is not supported in uncoupled mode (Auto-Best / split-knot mode)."
                )
            return False
        lam_src = result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        lam_a = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        if lam_a.size == 0:
            if self.logger:
                self.logger.info("Manual nodes: lam_nm source is empty.")
            return False
        rmse = float(result.get("rmse", float("inf")))
        if not np.isfinite(rmse):
            if self.logger:
                self.logger.info("Manual nodes: result RMSE is not finite.")
            return False
        return True

    def _prompt_manual_extra_knots(self, result: dict) -> tuple[list[float], float] | None:
        """Show the manual extra-knot placement dialog and return (lambda positions, delta_ns) on Go."""
        lam_model = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        # Try T first, fallback to R
        y_model = np.empty(0, dtype=np.float64)
        y_label_str = "T"
        t_val = result.get("t_theo")
        if t_val is not None:
            y_model = np.asarray(t_val, dtype=np.float64).ravel()
            y_label_str = "T/Tsub" if bool(result.get("t_is_ratio", False)) else "T"
        
        if y_model.size == 0:
            r_val = result.get("r_theo")
            if r_val is not None:
                y_model = np.asarray(r_val, dtype=np.float64).ravel()
                y_label_str = "R/Rsub" if bool(result.get("r_is_ratio", False)) else "R"

        lam_measurement = np.empty(0, dtype=np.float64)
        y_measurement = np.empty(0, dtype=np.float64)
        
        if self.df is not None and "lambda" in self.df.columns:
            if "T" in self.df.columns and result.get("t_theo") is not None and len(result.get("t_theo")) > 0:
                lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
                y_measurement = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))
            elif "R" in self.df.columns and result.get("r_theo") is not None and len(result.get("r_theo")) > 0:
                lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
                y_measurement = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

        dlg = ManualSigmaKnotDialog(
            sigma_knots=np.asarray(result.get("sigma_knots", []), dtype=np.float64),
            lam_model_nm=lam_model,
            y_model=y_model,
            lam_measurement_nm=lam_measurement,
            y_measurement=y_measurement,
            y_label=y_label_str,
            initial_delta_ns=0.0,
            parent=self,
        )

        def _on_delta_preview(delta_ns: float) -> None:
            if not self._apply_manual_substrate_offset_preview(result, float(delta_ns)):
                QMessageBox.warning(
                    self,
                    "Delta ns",
                    "Failed to apply delta ns to the current curve.",
                )
                return
            self._refresh_manual_dialog_preview(dlg, self._manual_postprocess_seed_result())

        dlg.delta_preview_requested.connect(_on_delta_preview)
        res_code = dlg.exec()
        if res_code != int(QDialog.DialogCode.Accepted):
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual extra-knot dialog skipped.")
            return None

        selected_lambda_knots_nm = dlg.selected_lambda_knots()
        delta_ns = dlg.substrate_delta_ns()

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: manual extra-knot dialog | count=%d | delta_ns=%+.6f",
                len(selected_lambda_knots_nm),
                float(delta_ns),
            )
        return selected_lambda_knots_nm, delta_ns

    def _open_manual_extra_knots_dialog(self, result: dict) -> None:
        """Open a non-blocking manual-knot dialog that stays open on local apply."""
        lam_model = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        # Try T first, fallback to R
        y_model = np.empty(0, dtype=np.float64)
        y_label_str = "T"
        t_val = result.get("t_theo")
        if t_val is not None:
            y_model = np.asarray(t_val, dtype=np.float64).ravel()
            y_label_str = "T/Tsub" if bool(result.get("t_is_ratio", False)) else "T"
        
        if y_model.size == 0:
            r_val = result.get("r_theo")
            if r_val is not None:
                y_model = np.asarray(r_val, dtype=np.float64).ravel()
                y_label_str = "R/Rsub" if bool(result.get("r_is_ratio", False)) else "R"

        lam_measurement = np.empty(0, dtype=np.float64)
        y_measurement = np.empty(0, dtype=np.float64)
        
        if self.df is not None and "lambda" in self.df.columns:
            if "T" in self.df.columns and result.get("t_theo") is not None and len(result.get("t_theo")) > 0:
                lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
                y_measurement = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))
            elif "R" in self.df.columns and result.get("r_theo") is not None and len(result.get("r_theo")) > 0:
                lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
                y_measurement = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

        if self.logger:
            self.logger.info(
                "MANUAL_DIALOG_DIAG: lam_model=%d y_model=%d lam_meas=%d y_meas=%d | "
                "df=%s df_cols=%s | t_theo_in_result=%s r_theo_in_result=%s | "
                "t_theo_len=%d r_theo_len=%d | result_keys_sample=%s",
                lam_model.size, y_model.size,
                lam_measurement.size, y_measurement.size,
                self.df is not None,
                list(self.df.columns) if self.df is not None else "None",
                result.get("t_theo") is not None,
                result.get("r_theo") is not None,
                len(result.get("t_theo")) if result.get("t_theo") is not None else 0,
                len(result.get("r_theo")) if result.get("r_theo") is not None else 0,
                sorted(result.keys())[:20],
            )
        dlg = ManualSigmaKnotDialog(
            sigma_knots=np.asarray(result.get("sigma_knots", []), dtype=np.float64),
            lam_model_nm=lam_model,
            y_model=y_model,
            lam_measurement_nm=lam_measurement,
            y_measurement=y_measurement,
            y_label=y_label_str,
            initial_delta_ns=0.0,
            keep_open_on_local_apply=True,
            parent=self,
        )

        def _on_local_apply(selected_lambda_knots_nm: list[float], delta_ns: float) -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: no usable current result.")
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "No usable current result to restart optimization.",
                )
                return
            if selected_lambda_knots_nm:
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.clear_runtime_log()
                    self._manual_knots_dialog.set_runtime_progress(0.0, "Starting local re-optimization")
                    d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                    self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                    mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                        getattr(
                            dlg,
                            "_base_sigma_knots",
                            np.asarray(seed_current.get("sigma_knots", []), dtype=np.float64).ravel(),
                        ),
                        np.sort(
                            1.0 / np.maximum(np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel(), 1e-30)
                        ),
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        f"Forced re-optimization (delta ns included) | delta ns={float(delta_ns):+.6f}"
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        CertusIndexSplineApp._manual_mesh_change_log_line("Requested mesh", mesh_summary)
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        f"Local re-optimization launched | active knots: {len(selected_lambda_knots_nm)} | delta ns={float(delta_ns):+.6f}"
                    )
                    if self.logger:
                        self.logger.info(
                            "INDEX_SPLINE GUI: manual local re-optimization request | %s | delta_ns=%+.6f",
                            CertusIndexSplineApp._manual_mesh_change_log_line("requested", mesh_summary),
                            float(delta_ns),
                        )
                self._start_manual_sigma_insert_worker(seed_current, selected_lambda_knots_nm, float(delta_ns))

        def _on_autoshift() -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                QMessageBox.information(
                    self,
                    "Autoshift",
                    "No usable current result to start autoshift.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting autoshift delta ns")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(
                    "Automatic Brent search for best substrate shift in [-0.01, 0.01]..."
                )
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            self._start_manual_autoshift_worker(seed_current, selected_lambda_knots_nm)

        def _on_auto_repartition(mode: str) -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "No usable current result to restart optimization.",
                )
                return
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            if len(selected_lambda_knots_nm) < 2:
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "At least two active knots are required for automatic repartition.",
                )
                return
            delta_ns = dlg.substrate_delta_ns()
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                mode_label = "log(sigma)" if str(mode).strip().lower() == "log" else "sigma"
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, f"Starting auto repartition {mode_label}")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                target_sigma_knots = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(
                    selected_lambda_knots_nm,
                    mode=mode,
                )
                mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                    np.sort(1.0 / np.maximum(np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel(), 1e-30)),
                    target_sigma_knots,
                )
                self._manual_knots_dialog.append_runtime_log(
                    f"Automatic repartition {mode_label} launched | active knots: {len(selected_lambda_knots_nm)} | delta ns={float(delta_ns):+.6f}"
                )
                self._manual_knots_dialog.append_runtime_log(
                    CertusIndexSplineApp._manual_mesh_change_log_line("Requested repartition", mesh_summary)
                )
                if self.logger:
                    self.logger.info(
                        "INDEX_SPLINE GUI: manual auto repartition request | mode=%s | %s | delta_ns=%+.6f",
                        str(mode),
                        CertusIndexSplineApp._manual_mesh_change_log_line("requested", mesh_summary),
                        float(delta_ns),
                    )
            self._start_manual_sigma_repartition_worker(
                seed_current, selected_lambda_knots_nm, float(delta_ns), mode=mode
            )

        def _on_delta_preview(delta_ns: float) -> None:
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                return
            if not self._apply_manual_substrate_offset_preview(seed_current, float(delta_ns)):
                return
            self._refresh_manual_dialog_preview(dlg, self._manual_postprocess_seed_result())

        def _on_auto_clean(tolerance: float) -> None:
            # NaN = signal "read value from GUI widget".
            try:
                _tol_in = float(tolerance)
            except (TypeError, ValueError):
                _tol_in = float("nan")
            if not np.isfinite(_tol_in):
                if hasattr(self, "sp_auto_clean_tol"):
                    tolerance = float(self.sp_auto_clean_tol.value())
                else:
                    tolerance = 5.0e-5
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: auto_clean refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: auto_clean refused because no usable seed result")
                QMessageBox.information(
                    self,
                    "Advanced clean",
                    "No usable current result to start cleaning.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting clean...")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(f"Advanced iterative clean (tolerance: +{tolerance})...")
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            delta_ns = dlg.substrate_delta_ns()
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: launching auto_clean | tolerance=+%.5f | seed_rmse=%.8f | seed_d=%.4f | K_selected=%d | delta_ns=%+.6f",
                    float(tolerance),
                    float(CertusIndexSplineApp._rmse_from_result_dict(seed_current)),
                    float(seed_current.get("d_nm", float("nan"))),
                    int(len(selected_lambda_knots_nm)),
                    float(delta_ns),
                )
            self._start_manual_auto_clean_worker(seed_current, selected_lambda_knots_nm, float(delta_ns), tolerance)

        def _on_auto_add_one() -> None:
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: auto_add_one refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: auto_add_one refused because no usable seed result")
                QMessageBox.information(
                    self,
                    "Auto add one",
                    "No usable current result to start auto insertion.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting auto add one...")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(
                    "Auto add one: testing all mid-gap insertion candidates..."
                )
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            delta_ns = dlg.substrate_delta_ns()
            self._start_manual_auto_add_one_worker(seed_current, selected_lambda_knots_nm, float(delta_ns))

        def _on_recall_best() -> None:
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: recall best refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: an optimization is already running.")
                return
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: recall best requested but no active manual dialog")
                return
            best = dlg_ref.get_best_config()
            if best is None:
                if self.logger:
                    self.logger.info("INDEX_SPLINE GUI: recall best requested but no best snapshot available yet")
                return
            best_result, best_sk = best
            rmse_best = float(best_result.get("rmse", float("nan")))
            K_best = int(best_sk.size)
            # Direct memory restoration — no re-polish to avoid contamination
            # from _best_live_result or intermediate display snapshots.
            dlg_ref.clear_runtime_log()
            dlg_ref.append_runtime_log(f"Recall best config: RMSE={rmse_best:.8f} | K={K_best}")
            dlg_ref.set_runtime_progress(100.0, f"Best config restored (K={K_best})")
            d_best, r_best = CertusIndexSplineApp._runtime_metrics_from_result_dict(best_result)
            dlg_ref.set_runtime_metrics(d_best, r_best)
            dlg_ref.adopt_sigma_knots(best_sk)
            opt_delta_ns = best_result.get("substrate_n_offset")
            if opt_delta_ns is not None:
                dlg_ref.adopt_delta_ns(float(opt_delta_ns))
            # Update graphs and current GUI state (no worker needed)
            self._last_result = best_result
            self._last_worker_result = dict(best_result)
            self._plot_result(best_result, plot_source="recall_best")
            self._refresh_manual_dialog_preview(dlg_ref, best_result)
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: recall best config | RMSE=%.8f | K=%d | d=%.4f nm",
                    rmse_best,
                    K_best,
                    float(best_result.get("d_nm", float("nan"))),
                )

        def _on_dialog_finished(_result_code: int) -> None:
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if dlg_ref is dlg:
                self._manual_knots_dialog = None
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual knots dialog closed")

        dlg.local_apply_requested.connect(_on_local_apply)
        dlg.auto_shift_requested.connect(_on_autoshift)
        dlg.auto_repartition_log_requested.connect(lambda: _on_auto_repartition("log"))
        dlg.auto_repartition_sigma_requested.connect(lambda: _on_auto_repartition("sigma"))
        dlg.auto_clean_requested.connect(_on_auto_clean)
        dlg.auto_add_one_requested.connect(_on_auto_add_one)

        def _on_recall_best_for_k(k: int) -> None:
            """Recall the best config for a specific knot count K."""
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: an optimization is already running.")
                return
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                return
            best = dlg_ref.get_best_config_for_k(k)
            if best is None:
                if self.logger:
                    self.logger.info("INDEX_SPLINE GUI: recall best for K=%d requested but no snapshot available", k)
                return
            best_result, best_sk = best
            rmse_best = float(best_result.get("rmse", float("nan")))
            K_best = int(best_sk.size)
            dlg_ref.clear_runtime_log()
            dlg_ref.append_runtime_log(f"Recall best config for K={K_best}: RMSE={rmse_best:.8f}")
            dlg_ref.set_runtime_progress(100.0, f"Best config restored (K={K_best})")
            d_best, r_best = CertusIndexSplineApp._runtime_metrics_from_result_dict(best_result)
            dlg_ref.set_runtime_metrics(d_best, r_best)
            dlg_ref.adopt_sigma_knots(best_sk)
            opt_delta_ns = best_result.get("substrate_n_offset")
            if opt_delta_ns is not None:
                dlg_ref.adopt_delta_ns(float(opt_delta_ns))
            self._last_result = best_result
            self._last_worker_result = dict(best_result)
            self._plot_result(best_result, plot_source=f"recall_best_k{K_best}")
            self._refresh_manual_dialog_preview(dlg_ref, best_result)
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: recall best config for K=%d | RMSE=%.8f | d=%.4f nm",
                    K_best,
                    rmse_best,
                    float(best_result.get("d_nm", float("nan"))),
                )

        dlg.recall_best_requested.connect(_on_recall_best)
        dlg.recall_best_for_k_requested.connect(_on_recall_best_for_k)
        dlg.stop_requested.connect(self._on_stop)
        dlg.delta_preview_requested.connect(_on_delta_preview)
        dlg.finished.connect(_on_dialog_finished)
        self._manual_knots_dialog = dlg
        dlg.clear_runtime_log()
        seed_d, seed_rmse = CertusIndexSplineApp._runtime_metrics_from_result_dict(result)
        # Initialize per-K best tracking with the current solution at dialog open
        seed_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        dlg.update_best_config(result, seed_sk)
        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: manual dialog opened with initial best snapshot | RMSE=%.8f | K=%d",
                float(CertusIndexSplineApp._rmse_from_result_dict(result)),
                int(seed_sk.size),
            )
        dlg.set_runtime_metrics(seed_d, seed_rmse)
        dlg.set_runtime_progress(100.0, "Ready")
        dlg.append_runtime_log("Ready. Current solution is ready for manual adjustment.")
        dlg.show()

    def _start_manual_sigma_insert_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float = 0.0
    ) -> None:
        """Launch manual sigma node tuning worker after user placement."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            if self.logger:
                self.logger.warning("INDEX_SPLINE GUI: manual extra knots - no config available, abort.")
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size == 0:
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual extra knots - empty selection, skip launch.")
            return
        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))
        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        # Tighten the acceptance reference: if a polished RMSE (e.g. cubic-spline sigma)
        # was computed for the current result and is better than the solver dict RMSE,
        # inject it as the effective reference so that direct K→K+n insertion is only
        # accepted when the new mesh does not degrade vs the polished baseline.
        _gb_polished = seed_payload.get("spectral_rmse_global_best_value") or seed_payload.get(
            "spectral_rmse_polished_value"
        )
        if _gb_polished is not None:
            try:
                _gb_f = float(_gb_polished)
                _dict_rmse = float(seed_payload.get("rmse", float("inf")))
                if np.isfinite(_gb_f) and _gb_f < _dict_rmse:
                    seed_payload = dict(seed_payload)
                    seed_payload["rmse"] = _gb_f
                    if self.logger:
                        self.logger.info(
                            "INDEX_SPLINE GUI: manual insert: tightening RMSE reference to polished value %.8f (dict was %.8f)",
                            _gb_f,
                            _dict_rmse,
                        )
            except (TypeError, ValueError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_manual_sigma_insert,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            force_reopt=True,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f"[{float(p):6.2f}%] {str(m)}", display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': pv}))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_sigma_insert"
        if hasattr(self, "_stepper"):
            self._stepper.set_step(5)
        if self.logger:
            K_cur = int(np.asarray(result.get("sigma_knots", []), dtype=np.float64).size)
            rr = float(result.get("rmse", float("nan")))
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel(),
                target_sigma_knots,
            )
            self.logger.info(
                "INDEX_SPLINE GUI: launching manual node tuning worker | K=%d | K_target=%d | rmse=%.8f",
                K_cur,
                int(target_sigma_knots.size),
                rr if np.isfinite(rr) else float("nan"),
            )
            self.logger.info(
                "INDEX_SPLINE GUI: manual node tuning worker mesh summary | %s",
                CertusIndexSplineApp._manual_mesh_change_log_line("target", mesh_summary),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: worker knot insertion (d seed)",
                result.get("d_nm"),
                detail=(
                    f"K_sigma={K_cur} sigma_knots_added={int(target_sigma_knots.size)} delta_ns={float(delta_ns):+.6f}"
                ),
            )
        self._set_worker_running_state(True)
        self.lbl_status.setText("Manual knots: local re-optimization in progress...")
        install_skeleton(self.tabs_main, label="Manual knots...")
        self._worker.start()

    @staticmethod
    def _build_manual_repartition_target_sigma_knots(selected_lambda_knots_nm: list[float], *, mode: str) -> np.ndarray:
        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        selected_lam = selected_lam[np.isfinite(selected_lam) & (selected_lam > 0.0)]
        if selected_lam.size < 2:
            return np.empty(0, dtype=np.float64)
        sigma_active = np.unique(np.sort(1.0 / np.maximum(selected_lam, 1e-30)))
        if sigma_active.size < 2:
            return np.empty(0, dtype=np.float64)
        sigma_lo = float(np.min(sigma_active))
        sigma_hi = float(np.max(sigma_active))
        k_target = int(sigma_active.size)
        if str(mode).strip().lower() == "log":
            return np.exp(np.linspace(np.log(max(sigma_lo, 1e-30)), np.log(max(sigma_hi, 1e-30)), k_target)).astype(
                np.float64
            )
        return np.linspace(sigma_lo, sigma_hi, k_target, dtype=np.float64)

    def _start_manual_sigma_repartition_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float, *, mode: str
    ) -> None:
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        target_sigma_knots = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(
            selected_lambda_knots_nm,
            mode=mode,
        )
        if target_sigma_knots.size < 2:
            return

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_manual_sigma_insert,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            force_reopt=True,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f"[{float(p):6.2f}%] {str(m)}", display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': pv}))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = f"manual_repartition_{str(mode).strip().lower()}"
        if self.logger:
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel(),
                target_sigma_knots,
            )
            self.logger.info(
                "INDEX_SPLINE GUI: launching manual repartition worker | mode=%s | K_target=%d | delta_ns=%+.6f",
                str(mode),
                int(target_sigma_knots.size),
                float(delta_ns),
            )
            self.logger.info(
                "INDEX_SPLINE GUI: manual repartition worker mesh summary | mode=%s | %s",
                str(mode),
                CertusIndexSplineApp._manual_mesh_change_log_line("target", mesh_summary),
            )
        self._set_worker_running_state(True)
        mode_label = "log(sigma)" if str(mode).strip().lower() == "log" else "sigma"
        self.lbl_status.setText(f"Manual knots: auto repartition {mode_label} in progress...")
        install_skeleton(self.tabs_main, label=f"Auto repartition {mode_label}...")
        self._worker.start()

    def _start_manual_autoshift_worker(self, result: dict, selected_lambda_knots_nm: list[float]) -> None:
        """Launch autoshift worker to find optimal delta_ns."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            if self.logger:
                self.logger.warning("INDEX_SPLINE GUI: autoshift - no config available, abort.")
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size == 0:
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: autoshift - empty selection, skip launch.")
            return
        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload["n_sub_base"] = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_autoshift_delta_ns,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=f"[{float(p):6.2f}%] {str(m)}", display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': pv}))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_autoshift"
        if self.logger:
            K_cur = int(np.asarray(result.get("sigma_knots", []), dtype=np.float64).size)
            self.logger.info(
                "INDEX_SPLINE GUI: launching autoshift worker | K=%d | K_target=%d",
                K_cur,
                int(target_sigma_knots.size),
            )
        self._set_worker_running_state(True)
        self.lbl_status.setText("Autoshift: searching for delta ns...")
        install_skeleton(self.tabs_main, label="Autoshift delta ns...")
        self._worker.start()

    def _start_manual_auto_add_one_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float
    ) -> None:
        """Launch auto-add-one worker to test all mid-gap insertions and keep the best."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size < 2:
            return

        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))
        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
                auto_add_one_candidate_maxfun=240,
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_auto_add_one_knot,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            if p < 0:
                self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=str(m), display_ratio=None, progress_ratio=None, eta_seconds=None, confidence=0.0, state=StepState.ERROR, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': -1}))
            else:
                pv = int(round(float(np.clip(p, 0.0, 100.0)) * 100.0))
                self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=str(m), display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': pv}))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_auto_add_one"

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: launching auto_add_one worker | K_target=%d | delta_ns=%+.6f",
                int(target_sigma_knots.size),
                float(delta_ns),
            )

        self._set_worker_running_state(True)
        self.lbl_status.setText("Auto add one: testing all mid-gap insertions...")
        install_skeleton(self.tabs_main, label="Auto add one...")
        self._worker.start()

    def _start_manual_auto_clean_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float, tolerance: float
    ) -> None:
        """Launch auto-clean worker to iteratively remove least sensitive knots."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size <= 2:
            return

        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_auto_clean_knots,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            tolerance=tolerance,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            if p < 0:
                self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=str(m), display_ratio=None, progress_ratio=None, eta_seconds=None, confidence=0.0, state=StepState.ERROR, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': -1}))
            else:
                pv = int(round(float(np.clip(p, 0.0, 100.0)) * 100.0))
                self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=str(m), display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='MANUAL_MESH', metadata={'pv': pv}))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_auto_clean"

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: launching auto_clean worker | K_target=%d", int(target_sigma_knots.size)
            )

        self._set_worker_running_state(True)
        self.lbl_status.setText("Advanced cleaning: iterative knot removal in progress...")
        install_skeleton(self.tabs_main, label="Advanced cleaning...")
        self._worker.start()

    def _corridor_manual_half_width_nm(self) -> float:

        if not hasattr(self, "sl_corridor_manual_half"):
            return 0.0

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        return float(self.sl_corridor_manual_half.value()) / float(scale)

    def _set_corridor_manual_interval_preview(self, d_best: float, half_width_nm: float) -> None:

        hw = float(max(0.0, half_width_nm))

        self._corridor_rmse_manual_lo = float(d_best - hw)

        self._corridor_rmse_manual_hi = float(d_best + hw)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText(f"+/-{hw:.2f} nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText(
                f"Manual interval: [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
            )

    def _set_corridor_manual_bounds_labels(self, d_min: float, d_best: float, d_max: float) -> None:

        if hasattr(self, "lbl_corridor_manual_dmin"):
            self.lbl_corridor_manual_dmin.setText(f"d_min: {d_min:.2f} nm" if np.isfinite(d_min) else "d_min: -")

        if hasattr(self, "lbl_corridor_manual_dcenter"):
            self.lbl_corridor_manual_dcenter.setText(f"d*: {d_best:.2f} nm" if np.isfinite(d_best) else "d*: -")

        if hasattr(self, "lbl_corridor_manual_dmax"):
            self.lbl_corridor_manual_dmax.setText(f"d_max: {d_max:.2f} nm" if np.isfinite(d_max) else "d_max: -")

    def _corridor_manual_max_half_width_nm(self, d_s: np.ndarray) -> float:

        d_arr = np.asarray(d_s, dtype=np.float64).ravel()

        if d_arr.size == 0:
            return 0.0

        d_span = float(max(np.nanmax(d_arr) - np.nanmin(d_arr), 0.0)) if np.any(np.isfinite(d_arr)) else 0.0

        robust_half = 0.0

        if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
            robust_half = 0.5 * float(max(0.0, self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

        cur_half = self._corridor_manual_half_width_nm()

        step_half = float(np.nanmedian(np.abs(np.diff(d_arr)))) if d_arr.size >= 2 else 0.0

        return float(max(d_span, robust_half, cur_half, step_half, 0.0))

    def _reset_corridor_manual_controls(self) -> None:

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.blockSignals(True)

            self.sl_corridor_manual_half.setRange(0, 1)

            self.sl_corridor_manual_half.setValue(0)

            self.sl_corridor_manual_half.setEnabled(False)

            self.sl_corridor_manual_half.blockSignals(False)

        if hasattr(self, "btn_generate_manual_corridor"):
            self.btn_generate_manual_corridor.setEnabled(False)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(False)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText("+/-0.00 nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText("Manual interval: -")

        self._set_corridor_manual_bounds_labels(float("nan"), float("nan"), float("nan"))

    def _on_corridor_manual_slider_changed(self, _value: int) -> None:

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = float(d_s[i_best])

        self._set_corridor_manual_interval_preview(d_center, self._corridor_manual_half_width_nm())

        src = self._corridor_profile_source_result()

        if src is not None:
            try:
                self._plot_corridor_rmse_tab(src)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Manual corridor slider refresh failed", exc_info=True)

    def _manual_postprocess_seed_result(self) -> dict | None:

        base = getattr(self, "_last_worker_result", None)
        if isinstance(base, dict):
            return base
        base = getattr(self, "_last_result", None)
        if isinstance(base, dict):
            return base
        return None

    def _on_btn_manual_knots_clicked(self) -> None:

        seed = self._manual_postprocess_seed_result()
        if not isinstance(seed, dict):
            if self.logger:
                self.logger.info("Manual nodes: action requested but no base result is available.")
            QMessageBox.information(
                self,
                "Manual knots",
                "Run an optimization first to have a base result.",
            )
            return
        if not self._can_offer_manual_extra_knots(seed):
            QMessageBox.information(
                self,
                "Manual knots",
                "The current result does not allow adding more manual knots.",
            )
            return
        self._open_manual_extra_knots_dialog(seed)
