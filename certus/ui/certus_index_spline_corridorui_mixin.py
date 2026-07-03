from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class CertusIndexSplineCorridorUIMixin:
    """CertusIndexSplineCorridorUIMixin."""

    def _schedule_corridor_auto_refine(
        self,
        seed: dict,
        *,
        rerun_corridor: bool,
        origin: str,
    ) -> bool:
        """Schedule a strict refinement chain after corridor improvement."""
        if not isinstance(seed, dict):
            return False
        self._corridor_auto_refine_plan = {
            "stage": "deep",
            "rerun_corridor": bool(rerun_corridor),
            "origin": str(origin or "corridor"),
        }
        if self.logger:
            self.logger.info(
                "AUTO-REFINE [%s] scheduled | chain=deep-polish -> [conditional-corridor-rerun] | rerun_corridor=%s",
                str(origin or "corridor"),
                "yes" if bool(rerun_corridor) else "no",
            )
        if self._start_curve_minimum_deep_refit(dict(seed)):
            return True
        self._corridor_auto_refine_plan = None
        return False

    def _continue_corridor_auto_refine_after_deep(self) -> bool:
        """Continue refinement chain when deep polish is done."""
        plan = self._corridor_auto_refine_plan
        if not isinstance(plan, dict) or str(plan.get("stage", "")) != "deep":
            return False
        seed_now = self._manual_postprocess_seed_result()
        if not isinstance(seed_now, dict):
            self._corridor_auto_refine_plan = None
            return False
        if bool(plan.get("rerun_corridor", False)):
            if self.logger:
                self.logger.info(
                    "AUTO-REFINE [%s] deep-polish done | rerunning corridor profiling.",
                    plan.get("origin", "corridor"),
                )
            self._corridor_auto_refine_plan = None
            return bool(self._start_deferred_corridor_worker(dict(seed_now)))
        self._corridor_auto_refine_plan = None
        return False

    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None:
        """Starts the gap healing worker after the grid, outside the ``finished`` handler (prevents ``_cleanup_thread``)."""
        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: a worker is already running.")
            return
        cfg = self._last_run_cfg
        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: no optimization config.")
            return
        self._stop_event = Event()
        self._worker = GenericWorker(
            _worker_corridor_rmse_healer,
            cfg,
            tasks,
            self._stop_event,
        )
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "rmse_heal"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_corridor_grid_busy(True)
        self._worker.start()

    @staticmethod
    def _interp_corridor_value(x: float, x_arr: np.ndarray, y_arr: np.ndarray) -> float:
        xa = np.asarray(x_arr, dtype=np.float64).ravel()
        ya = np.asarray(y_arr, dtype=np.float64).ravel()
        m = np.isfinite(xa) & np.isfinite(ya)
        if int(np.count_nonzero(m)) < 2:
            return float("nan")
        xs = xa[m]
        ys = ya[m]
        o = np.argsort(xs, kind="mergesort")
        xs = xs[o]
        ys = ys[o]
        return float(np.interp(float(x), xs, ys, left=np.nan, right=np.nan))

    def _k_corridor_crosshair_formatter(self, x: float, y_on_curve: float | None, y_mouse: float) -> str:
        lam = np.asarray(getattr(self, "_corridor_k_crosshair_lam", []), dtype=np.float64).ravel()
        k_nom = np.asarray(getattr(self, "_corridor_k_crosshair_nom", []), dtype=np.float64).ravel()
        k_min = np.asarray(getattr(self, "_corridor_k_crosshair_lo", []), dtype=np.float64).ravel()
        k_max = np.asarray(getattr(self, "_corridor_k_crosshair_hi", []), dtype=np.float64).ravel()
        kn = self._interp_corridor_value(x, lam, k_nom) if k_nom.size == lam.size else float("nan")
        k0 = self._interp_corridor_value(x, lam, k_min) if k_min.size == lam.size else float("nan")
        k1 = self._interp_corridor_value(x, lam, k_max) if k_max.size == lam.size else float("nan")
        if np.isfinite(k0) and np.isfinite(k1) and k1 < k0:
            k0, k1 = k1, k0
        kn_txt = f"{kn:.3e}" if np.isfinite(kn) and kn > 0.0 else "n/a"
        k0_txt = f"{k0:.3e}" if np.isfinite(k0) and k0 > 0.0 else "n/a"
        k1_txt = f"{k1:.3e}" if np.isfinite(k1) and k1 > 0.0 else "n/a"
        return f"lambda = {x:.2f} nm | k_min = {k0_txt} | k_nom = {kn_txt} | k_max = {k1_txt}"

    def _build_tab_corridor_rmse(self) -> QWidget:
        """Tab Corridor RMSE(d). Orchestrator."""
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)
        ctx_lay.setSpacing(6)
        self._build_corridor_labels(ctx_lay)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        rmse_section = CertusCard("1  Recalculate RMSE(d)")
        generate_section = CertusCard("2  Generate corridor n/k")
        self._build_corridor_tab_rmse_controls(rmse_section.body)
        self._build_corridor_tab_generate(generate_section.body)
        ctx_lay.addWidget(rmse_section)
        ctx_lay.addWidget(generate_section)

        self.plot_corridor_rmse_d = CertusScientificPlot(
            title="Corridor profile: RMSE(d)", y_label="RMSE", x_label="d (nm)"
        )
        self.plot_corridor_rmse_d.showGrid(x=True, y=True, alpha=0.25)
        self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_best_idx = -1
        self._corridor_rmse_center_nm = float("nan")
        self._corridor_rmse_grid_live_t0: float = float("nan")
        self._corridor_rmse_live_last_plot_ts: float = float("nan")
        self._corridor_rmse_live_plot_min_interval_s: float = 0.12
        self._corridor_rmse_robust_lo = float("nan")
        self._corridor_rmse_robust_hi = float("nan")
        self._corridor_rmse_robust_ok = False
        self._corridor_rmse_curve = self.plot_corridor_rmse_d.plot(
            [],
            [],
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
            name="RMSE(d)",
        )
        self._corridor_rmse_curve.setZValue(10)
        self._corridor_rmse_best_marker = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CertusTheme.SUCCESS, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self.plot_corridor_rmse_d.addItem(self._corridor_rmse_best_marker)

        self.sp_corridor_rmse_delta.valueChanged.connect(self._refresh_corridor_rmse_robust_view)
        self.sp_corridor_rmse_win.valueChanged.connect(self._refresh_corridor_rmse_robust_view)

        _scene = self.plot_corridor_rmse_d.plotItem.scene()
        if _scene is not None:
            _scene.sigMouseClicked.connect(self._on_corridor_rmse_plot_clicked)

        # Plot area on the LEFT
        lay.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_corridor_rmse_d), 1)

        self._apply_corridor_preset_auto_robust()
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        return panel

    def _refresh_corridor_rmse_robust_view(self) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE robust refresh failed", exc_info=True)

    def _set_corridor_grid_completed_badge(self) -> None:

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.stop(final_message="Done")

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            base = str(self.lbl_corridor_rmse_grid_progress.text() or "").strip()

            if "Final fit updated" not in base:
                self.lbl_corridor_rmse_grid_progress.setText(f"{base} | Final fit updated")

    def _update_corridor_rmse_state_bar(self, src: dict[str, Any] | None = None) -> None:

        if not hasattr(self, "lbl_corridor_rmse_state"):
            return

        if not isinstance(src, dict):
            src = self._corridor_profile_source_result()

        if not isinstance(src, dict):
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        src = normalize_corridor_live_payload(src)
        d_s = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        if d_s.size == 0:
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        has_manual = bool(src.get("manual_corridor_active", False))
        d_min = float(np.nanmin(d_s)) if np.any(np.isfinite(d_s)) else float("nan")
        d_max = float(np.nanmax(d_s)) if np.any(np.isfinite(d_s)) else float("nan")

        if has_manual:
            self.lbl_corridor_rmse_state.setText(
                f"Step 3/3: Corridor generated | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )
        else:
            self.lbl_corridor_rmse_state.setText(
                f"Step 2/3: Select an interval, then generate the corridor | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )

    def _corridor_profile_source_result(self) -> dict[str, Any] | None:

        for cand in (self._last_result, self._last_worker_result):
            if not isinstance(cand, dict):
                continue

            d_prof = np.asarray(cand.get("profile_d_values_nm", []), dtype=np.float64).ravel()

            r_prof = np.asarray(cand.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

            if d_prof.size > 0 and r_prof.size == d_prof.size:
                return cand

        return self._last_result

    def _set_corridor_rmse_view_centered(self, d_center: float, half_width_nm: float) -> None:

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        if not np.isfinite(d_center):
            return

        hw = float(max(0.0, half_width_nm))

        if not np.isfinite(hw):
            return

        hw_eff = float(max(hw, 0.5))

        pad = float(max(0.02 * (2.0 * hw_eff), 0.25))

        self.plot_corridor_rmse_d.plotItem.setXRange(
            float(d_center - hw_eff - pad), float(d_center + hw_eff + pad), padding=0.0
        )

    def _set_corridor_rmse_view_data_bounds(self, d_vals: np.ndarray, r_vals: np.ndarray) -> None:
        """Sets the scale of the RMSE(d) graph to the min/max bounds of the data."""

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        xd = np.asarray(d_vals, dtype=np.float64).ravel()

        yd = np.asarray(r_vals, dtype=np.float64).ravel()

        m = np.isfinite(xd) & np.isfinite(yd)

        xd = xd[m]

        yd = yd[m]

        if xd.size == 0 or yd.size == 0:
            return

        x_lo = float(np.min(xd))

        x_hi = float(np.max(xd))

        y_lo = float(np.min(yd))

        y_hi = float(np.max(yd))

        x_span = max(1e-12, x_hi - x_lo)

        y_span = max(1e-12, y_hi - y_lo)

        x_pad = max(0.25, 0.02 * x_span)

        y_pad = max(1e-8, 0.04 * y_span)

        self.plot_corridor_rmse_d.plotItem.setXRange(x_lo - x_pad, x_hi + x_pad, padding=0.0)

        self.plot_corridor_rmse_d.plotItem.setYRange(y_lo - y_pad, y_hi + y_pad, padding=0.0)

    def _on_corridor_rmse_lock_scale_toggled(self, _checked: bool) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE lock-scale refresh failed", exc_info=True)

    def _use_robust_corridor_interval(self) -> None:

        if not bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        float(d_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        if not (np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb >= d_lo_rb):
            return

        half = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        half = float(min(max(0.0, half), max_half))

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.setValue(int(round(half * scale)))
            # setValue does not emit valueChanged if unchanged: force visual sync
            # so vertical interval bars always reflect current robust bounds.
            self._on_corridor_manual_slider_changed(self.sl_corridor_manual_half.value())

    def _build_tab_data_corridor(self) -> QWidget:
        """Tab dedicated to detailed corridor uncertainty data."""
        # Sync context stack
        self._add_context_page(
            self._create_empty_context_widget(
                "Detailed corridor uncertainty table.\nIncludes nominal, center, and min/max bounds."
            )
        )

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()
        self.btn_copy_corridor = create_styled_button("Copier tableau Corridors", "secondary")
        self.btn_copy_corridor.setEnabled(False)
        self.btn_copy_corridor.clicked.connect(self._copy_corridor_to_clipboard)
        tb.addWidget(self.btn_copy_corridor)

        self.btn_export_corridor = create_styled_button("Export CSV Corridors...", "primary")
        self.btn_export_corridor.setEnabled(False)
        self.btn_export_corridor.clicked.connect(self._export_corridor_csv)
        tb.addWidget(self.btn_export_corridor)

        tb.addStretch(1)
        lay.addLayout(tb)

        self.table_corridor = ExcelTableWidget()
        self.table_corridor.setColumnCount(9)
        self.table_corridor.setHorizontalHeaderLabels(
            ["lambda (nm)", "n nominal", "k nominal", "n center", "k center", "n min", "n max", "k min", "k max"]
        )
        self.table_corridor.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table_corridor, 1)

        return panel

    def _copy_corridor_to_clipboard(self) -> None:
        if hasattr(self, "table_corridor"):
            t = self.table_corridor
            lines = []
            cols = t.columnCount()
            hdr = [t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(cols)]
            lines.append("\t".join(hdr))
            for r in range(t.rowCount()):
                row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(cols)]
                lines.append("\t".join(row))
            QApplication.clipboard().setText("\n".join(lines))

    def _export_corridor_csv(self) -> None:
        if not self._ensure_complete_manifest_for_secondary_export():
            return
        if not hasattr(self, "table_corridor"):
            return
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Export Corridor CSV", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [
                    self.table_corridor.horizontalHeaderItem(i).text() for i in range(self.table_corridor.columnCount())
                ]
                writer.writerow(headers)
                for r in range(self.table_corridor.rowCount()):
                    writer.writerow(
                        [
                            self.table_corridor.item(r, c).text() if self.table_corridor.item(r, c) else ""
                            for c in range(self.table_corridor.columnCount())
                        ]
                    )

    def _refresh_corridors_gui_state_labels(self) -> None:
        """Refresh corridor state badges for the post-optimization controls."""

        role = str(getattr(self, "_worker_role", "idle") or "idle")
        unlocked = isinstance(getattr(self, "_last_result", None), dict)

        if role == "rmse_grid":
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>calculation in progress...</b></span>'
        elif not unlocked:
            rich = (
                f'Corridors: <span style="color:{CertusTheme.TEXT_SUB};"><b>available after optimization</b></span>'
            )

        elif bool(
            self._last_result.get("profile_d_enabled", False)
            or self._last_result.get("profile_d_values_nm") is not None
        ):
            rich = f'Corridors: <span style="color:{CertusTheme.SUCCESS};"><b>already computed</b></span>'

        else:
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>ready to launch</b></span>'

        if hasattr(self, "lbl_corridors_run_state"):
            self.lbl_corridors_run_state.setText(rich)

        if hasattr(self, "lbl_corridors_state_adv"):
            self.lbl_corridors_state_adv.setText(rich)

        if hasattr(self, "lbl_corridors_tab_state"):
            self.lbl_corridors_tab_state.setText(rich)

    def _on_btn_corridor_clicked(self) -> None:

        seed = self._manual_postprocess_seed_result()
        if not isinstance(seed, dict):
            QMessageBox.information(
                self,
                "Corridors",
                "Run an optimization first to have a base result.",
            )
            return
        if self.logger:
            self.logger.info(
                "Corridors manual trigger | base=%s",
                "standard",
            )
        if not self._start_deferred_corridor_worker(seed):
            QMessageBox.warning(
                self,
                "Corridors",
                "Unable to start manual corridor calculation from the current result.",
            )

    def _sync_corridor_btn_from_chk(self) -> None:

        if not hasattr(self, "btn_corridor_toggle") or not hasattr(self, "chk_corridor_d"):
            return

    def _on_corridor_chk_state_changed(self, *_args) -> None:

        self._refresh_corridors_gui_state_labels()
