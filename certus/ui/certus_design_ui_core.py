from __future__ import annotations
from certus.ui.certus_design_common import *

class CoreManager:
    def __init__(self, ui):
        self.ui = ui
    def _get_default_splitter_sizes(self) -> list[int]:
        """DESIGN specific splitter sizes."""

        return [450, 1150]

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for DESIGN."""

        substrate_type = "Custom"

        substrate_index = "N/A"

        if hasattr(self.ui, "mat_widgets") and "Substrate" in self.ui.mat_widgets:
            w = self.ui.mat_widgets["Substrate"]

            substrate_type = w["preset"].currentText()

            n4 = w["n4"].value()

            n7 = w["n7"].value()

            substrate_index = f"n@400={n4:.3f}, n@700={n7:.3f}"

        return substrate_type, substrate_index

    def _show_substrate_info_window(self) -> None:
        """Display stack information in a separate window"""

        if getattr(self.ui, "substrate_info_window", None) and self.ui.substrate_info_window.isVisible():
            self.ui.substrate_info_window.raise_()

            self.ui.substrate_info_window.activateWindow()

            self.ui._update_substrate_info()

            return

        if getattr(self.ui, "substrate_info_window", None) and not self.ui.substrate_info_window.isVisible():
            self.ui.substrate_info_window.show()

            self.ui.substrate_info_window.raise_()

            self.ui.substrate_info_window.activateWindow()

            self.ui._update_substrate_info()

            return

        self.ui.substrate_info_window = QDialog(self)

        self.ui.substrate_info_window.setWindowTitle("🔬 Stack information")

        self.ui.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.ui.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.ui.substrate_type_label = QLabel("N/A")

        self.ui.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.ui.substrate_type_label, 0, 1)

        info_layout.addWidget(self.ui.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Structure (QWOT)")

        structure_layout = structure_card.body

        self.ui.structure_text = QTextEdit()

        self.ui.structure_text.setReadOnly(True)

        self.ui.structure_text.setMaximumHeight(200)

        structure_layout.addWidget(self.ui.structure_text)

        layout.addWidget(structure_card)

        btn_layout = QHBoxLayout()

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(self.ui.substrate_info_window.close)

        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.ui.substrate_info_window.setLayout(layout)

        self.ui.substrate_info_window.show()

        self.ui.substrate_info_window.raise_()

        self.ui.substrate_info_window.activateWindow()

        self.ui._update_substrate_info()

    def _toggle_oblique_mode(self, state: int) -> None:
        """Toggle oblique mode and update UI"""

        self.ui.oblique_mode = state == Qt.CheckState.Checked.value

        self.ui._update_target_table_headers()

        # Convert existing targets if needed

        if self.ui.oblique_mode:
            # Convert normal to oblique targets

            if hasattr(self.ui, "target_widgets") and len(self.ui.target_widgets) > 0:
                self.ui.oblique_targets = []

                for tgt in self.ui.target_widgets:
                    if isinstance(tgt, Target):
                        oblique_tgt = ObliqueTarget(
                            angle=0.0,
                            pol="s",
                            target_type="T",
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                            include_backside=True,
                        )

                        self.ui.oblique_targets.append(oblique_tgt)

        else:
            # Convert oblique to normal targets

            if len(self.ui.oblique_targets) > 0:
                self.ui.target_widgets = []

                for tgt in self.ui.oblique_targets:
                    if isinstance(tgt, ObliqueTarget):
                        normal_tgt = Target(
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                        )

                        self.ui.target_widgets.append(normal_tgt)

        # Reload table

        self._load_targets_to_table()

        self.ui._schedule_eval(True)

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self):
            self.ui.status_label.setText("Logs copied to clipboard.")

    def _apply_preset(self, name: str, n4_spin: QDoubleSpinBox, n7_spin: QDoubleSpinBox) -> None:
        """Applies Cauchy preset and updates spinbox states."""


        # Enable/disable spinboxes based on preset

        is_custom = name == "Custom"

        n4_spin.setReadOnly(not is_custom)

        n7_spin.setReadOnly(not is_custom)

        # Visual distinction for readonly state

        style = "" if is_custom else f"background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_SUB};"

        n4_spin.setStyleSheet(style)

        n7_spin.setStyleSheet(style)

    def _on_schedule_eval_signal(self, *_args) -> None:

        self.ui._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self.ui._schedule_eval(True)

    def _trigger_post_undo_action(self) -> None:
        """DESIGN specific post-undo action."""

        self.ui.run_optim("local")

    def _get_optim_wls(self) -> np.ndarray:
        """Calculates wavelengths for optimization"""

        if self.ui.oblique_mode:
            tgts = self._get_oblique_tgts()

        else:
            tgts = self.ui._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            return np.array([])

        wls_list = []

        n_points = self.ui.points_per_target_spin.value()

        for t in active:
            start = max(t.lmin, 1e-3)

            end = max(t.lmax, start + 1e-3)

            if n_points > 1:
                # Uniform grid in wavenumbers (1/lambda)

                sigma_min = 1.0 / end

                sigma_max = 1.0 / start

                # Linear grid in wavenumbers

                sigma_grid = np.linspace(sigma_min, sigma_max, n_points)

                # Convert back to wavelengths

                grid = 1.0 / sigma_grid

            else:
                grid = np.array([start])

            wls_list.append(grid)

        if wls_list:
            wls = np.unique(np.concatenate(wls_list))

        else:
            wls = np.array([])

        return wls

    def _update_optim_point_count(self, *args, **kwargs) -> None:
        """Updates optimization point counter"""

        wls = self._get_optim_wls()

        self.ui.npts_spin.setValue(len(wls))

    def _calculate_tikhonravov_points(self) -> int:
        """

        Calculates recommended points per target using Tikhonravov formula.

        Formula: N = 2 * L * delta_nu * margin

        Where:

        - L = total optical thickness in nm (Sum n_i * d_i)

        - delta_nu = spectral interval in wavenumbers (1/nm) = 1/l_min - 1/l_max

        - margin = 10 (safety factor)

        The product L * delta_nu is dimensionless. The factor 2 comes from Nyquist criterion.

        Returns

        -------

        int

            Recommended points per target

        """

        try:
            # Retrieve necessary data

            mats = self._get_materials()

            stack = self.ui._get_front_stack()

            # Use correct targets based on mode (normal or oblique)

            if self.ui.oblique_mode:
                tgts = self._get_oblique_tgts()

            else:
                tgts = self.ui._get_tgts()

            l0 = self.ui.l0_spin.value()

            if not stack or not mats:
                return 50  # Default

            # Calculate total optical thickness L

            # Use current thicknesses if available, else calc from QWOT

            if self.ui.ep_current is not None and len(self.ui.ep_current) == len(stack):
                ep = self.ui.ep_current

            else:
                ep = init_thickness(stack, l0, mats)

                if ep is None:
                    return 50

            # Find global spectral interval of active targets

            active_tgts = [t for t in tgts if t.valid()]

            if not active_tgts:
                return 50

            lambda_min = min(t.lmin for t in active_tgts)

            lambda_max = max(t.lmax for t in active_tgts)

            if lambda_max <= lambda_min or lambda_min < 1e-3:
                return 50

            # Calculate total optical thickness L = Sum(n_i * d_i) in nm

            # Use reference wavelength at center of spectral range

            wl_ref = (lambda_min + lambda_max) / 2.0  # nm

            L_total = 0.0

            for i, layer in enumerate(stack):
                if i >= len(ep):
                    continue

                mat = mats.get(layer.mat)

                if mat:
                    n_ref = mat.get_nk(np.array([wl_ref]))[0].real

                    L_total += n_ref * ep[i]

            if L_total < 1e-6:
                return 50

            # Convert spectral interval to wavenumbers (1/nm)

            nu_min = 1.0 / lambda_max  # Shorter wavelength = larger wavenumber

            nu_max = 1.0 / lambda_min  # Longer wavelength = smaller wavenumber

            delta_nu = nu_max - nu_min  # in 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * marge

            nu_min = 1.0 / lambda_max

            nu_max = 1.0 / lambda_min

            delta_nu = nu_max - nu_min  # in 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * margin

            # L_total(nm)*dn(1/nm) = dimensionless

            marge = 10.0

            N = 2.0 * L_total * delta_nu * marge

            # Round and clamp to reasonable limits

            N_int = int(np.ceil(N))

            N_int = max(10, min(5000, N_int))

            return N_int

        except (ValueError, TypeError) as e:
            logging.debug("[DESIGN.profile] could not calculate Tikhonravov point count | error=%s", e)

            return 50  # Default on error

    def _update_tikhonravov_points(self) -> None:
        """Automatically updates points count using Tikhonravov."""

        if getattr(self.ui, "_loading_config", False):
            self.ui.log("Tikhonravov update skipped during config load.", "INFO")
            return

        try:
            tikhon_points = self._calculate_tikhonravov_points()

            if tikhon_points > 0:
                current_val = self.ui.points_per_target_spin.value()

                # Update only if change significant

                if abs(tikhon_points - current_val) > max(5, current_val * 0.15):  # Threshold 15% or 5 points
                    self.ui.points_per_target_spin.blockSignals(True)

                    self.ui.points_per_target_spin.setValue(tikhon_points)

                    self.ui.points_per_target_spin.blockSignals(False)

                    self._update_optim_point_count()

                    self.ui.log(
                        f"Tikhonravov: Auto-updated points/target to {tikhon_points}",
                        "INFO",
                    )

        except (AttributeError, ValueError) as e:
            logging.debug("[DESIGN.profile] could not update Tikhonravov points | error=%s", e)

    def _get_materials(self) -> dict:
        """Retrieves configured materials."""

        try:
            result = {k: Material(w["n4"].value(), w["n7"].value()) for k, w in self.ui.mat_widgets.items()}

            return result

        except (AttributeError, KeyError) as e:
            logging.debug("[DESIGN.profile] could not get materials | error=%s", e)

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        if not self.ui.oblique_mode:
            return []  # Sinon mode normal : _get_tgts()

        targets = []

        for r in range(self.ui.target_table.rowCount()):
            try:
                cw = self.ui.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                active = chk.isChecked() if chk else False

                # Angle

                angle_w = self.ui.target_table.cellWidget(r, 1)

                angle = angle_w.value() if angle_w else 0.0

                # Polarisation

                pol_w = self.ui.target_table.cellWidget(r, 2)

                polarization = pol_w.currentText() if pol_w else "s"

                # Type

                type_w = self.ui.target_table.cellWidget(r, 3)

                target_type = type_w.currentText() if type_w else "T"

                # lambdamin, lambdamax

                lmin_w = self.ui.target_table.cellWidget(r, 4)

                lmax_w = self.ui.target_table.cellWidget(r, 5)

                lmin = lmin_w.value() if lmin_w else 400.0

                lmax = lmax_w.value() if lmax_w else 700.0

                # Val min, Val max

                vmin_w = self.ui.target_table.cellWidget(r, 6)

                vmax_w = self.ui.target_table.cellWidget(r, 7)

                val_min = vmin_w.value() if vmin_w else 0.0

                val_max = vmax_w.value() if vmax_w else 1.0

                # Weight

                weight_w = self.ui.target_table.cellWidget(r, 8)

                weight = weight_w.value() if weight_w else 1.0

                targets.append(
                    ObliqueTarget(
                        angle=angle,
                        pol=polarization,
                        target_type=target_type,
                        lmin=lmin,
                        lmax=lmax,
                        tmin=val_min,
                        tmax=val_max,
                        w=weight,
                        on=active,
                        include_backside=True,
                    )
                )

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug("[DESIGN.profile] could not get oblique target row | error=%s", e)

        return targets

    def _load_targets_to_table(self) -> None:
        """Loads targets into table from internal lists"""

        self.ui.target_table.setRowCount(0)

        if self.ui.oblique_mode:
            for tgt in self.ui.oblique_targets:
                self.ui.add_target()

                r = self.ui.target_table.rowCount() - 1

                # Active

                active_cb = self.ui.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # Angle

                angle_w = self.ui.target_table.cellWidget(r, 1)

                if angle_w:
                    angle_w.setValue(tgt.angle)

                # Pol

                pol_w = self.ui.target_table.cellWidget(r, 2)

                if pol_w:
                    pol_w.setCurrentText(tgt.pol)

                # Type

                type_w = self.ui.target_table.cellWidget(r, 3)

                if type_w:
                    type_w.setCurrentText(tgt.target_type)

                # lambdamin, lambdamax

                lmin_w = self.ui.target_table.cellWidget(r, 4)

                lmax_w = self.ui.target_table.cellWidget(r, 5)

                if lmin_w:
                    lmin_w.setValue(tgt.lmin)

                if lmax_w:
                    lmax_w.setValue(tgt.lmax)

                # Val min, Val max

                vmin_w = self.ui.target_table.cellWidget(r, 6)

                vmax_w = self.ui.target_table.cellWidget(r, 7)

                if vmin_w:
                    vmin_w.setValue(tgt.tmin)

                if vmax_w:
                    vmax_w.setValue(tgt.tmax)

                # Weight

                weight_w = self.ui.target_table.cellWidget(r, 8)

                if weight_w:
                    weight_w.setValue(tgt.w)

        else:
            for tgt in self.ui.target_widgets:
                self.ui.add_target()

                r = self.ui.target_table.rowCount() - 1

                # Active

                active_cb = self.ui.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # lambdamin, lambdamax, Tmin, Tmax, Weight

                for i, val in enumerate([tgt.lmin, tgt.lmax, tgt.tmin, tgt.tmax, tgt.w]):
                    w = self.ui.target_table.cellWidget(r, i + 1)

                    if w:
                        w.setValue(val)

    def _on_front_thickness_updated(self) -> None:
        """DESIGN specific: update Tikhonravov points."""

        QTimer.singleShot(150, self._update_tikhonravov_points)

    def _reset_run_optim_workflow_state(self, mode: str) -> None:
        """Reset workflow state and UI counters for a fresh optimization start."""

        self.ui.orchestrator._target_layer_count = self.ui.front_table.rowCount()

        self.ui._topology_stable = True

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
            if hasattr(self.ui.orchestrator, attr):
                delattr(self.ui.orchestrator, attr)
            if hasattr(self, attr):
                delattr(self, attr)

        self.ui._initial_cleared = False

        self.ui._clean_live_curves()

        self.ui.log(f"Starting {mode} optimization (PGLOBAL)...", "INFO")

        self.ui.stat_counters["EVAL"] = 0

        self.ui.accumulated_evals = 0

        self.ui.stat_counters["MINIMA"] = 0

        self.update_stats_display()

        self.ui.best_rmse_label.setText("Best RMSE: N/A")

        self.ui._workflow_best_rmse = float("inf")

        self.ui._best_eval_result = None

        self.ui._best_eval_rmse = float("inf")

        self.ui._workflow_stopped = False

        self.ui._decimation_done = False

        self.ui._export_pending = False

        self.ui._post_optim_start_time = None

        self.ui._stack_info_best_ep = None

        self.ui._stack_info_best_rmse = None

        self.ui._stack_info_last_update = 0.0

        from certus.core.certus_metrology import RunContext, CERTUS_VERSION
        
        self.ui._workflow_run_ctx = RunContext.create(app_id="certus_design", app_version=CERTUS_VERSION)

        self.ui._workflow_run_id = self.ui._workflow_run_ctx.run_id

        import time as _time

        self.ui._workflow_wall_start = _time.time()

        self.ui.mse_data = {"iterations": [], "errors": []}

        if self.ui.convergence_curve is not None:
            self.ui.convergence_curve.setData([], [])

    def _shutdown_previous_optim_worker(self) -> None:
        """Stop any running optimization worker before starting a new cycle."""

        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        if self.ui.optim_thread is not None:
            try:
                stop_qt_worker_thread_safely(
                    self.ui.optim_thread,
                    self.ui.optim_worker,
                    timeout_ms=2000,
                    logger=getattr(self.ui, "logger", None),
                )
            except RuntimeError:
                pass

        self.ui.optim_worker = None
        self.ui.optim_thread = None

    def _collect_run_optim_inputs(self) -> tuple:
        """Collect and validate inputs required by run_optim."""

        stack = self.ui._get_front_stack()

        if not [l for l in stack if l.var]:
            self.ui.log("No variable layers.", "WARNING")

            return None, None, None, None, None

        mats = self._get_materials()

        tgts = self._get_oblique_tgts() if self.ui.oblique_mode else self.ui._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            self.ui.log("No valid targets.", "WARNING")

            return None, None, None, None, None

        if getattr(self.ui, "_use_exact_ep", False) and self.ui.ep_current is not None and len(self.ui.ep_current) == len(stack):
            ep0 = self.ui.ep_current.copy()
            self.ui._use_exact_ep = False
        else:
            ep0 = init_thickness(stack, self.ui.l0_spin.value(), mats)

        wls = self._get_optim_wls()

        return stack, mats, active, ep0, wls

    def _initialize_run_optim_progress_state(self, cfg: dict, keep_history: bool) -> None:
        """Initialize progress counters and optional time budget for a run."""

        self.ui._optim_max_iter = 100

        self.ui._optim_current_iter = 0

        self.ui._optim_n_evals = 0

        _mode = cfg.get("mode", "global")
        
        # Resolve user-friendly phase name for UI feedback
        if _mode == "local":
            if getattr(self.ui, "_smart_decimation_step", 0) > 0:
                self.ui._optim_current_phase = f"DECIMATION (Step {self.ui._smart_decimation_step})"
            elif self.ui.orchestrator._is_in_needle_cycle():
                self.ui._optim_current_phase = f"NEEDLE POLISH (Iter {getattr(self.ui.orchestrator, '_needle_cycle_step', 1)})"
            elif getattr(self.ui.orchestrator, "_healing_phase", None) == "local":
                self.ui._optim_current_phase = "HEALING POLISH"
            else:
                self.ui._optim_current_phase = "LOCAL POLISH"
        elif _mode == "healing":
            self.ui._optim_current_phase = "HEALING GLOBAL"
        else:
            allow_growth = getattr(self.ui, "allow_growth_check", None)
            if allow_growth and allow_growth.isChecked():
                self.ui._optim_current_phase = "GLOBAL + NEEDLE SEED"
            else:
                self.ui._optim_current_phase = "GLOBAL SEARCH"

        if keep_history:
            return

        _n = len(cfg.get("ep0", []))

        _mode = cfg.get("mode", "global")

        allow_growth = getattr(self.ui, "allow_growth_check", None)

        _needle_coupled = allow_growth and allow_growth.isChecked() and _mode == "global"

        _global_time = 35.0 if _needle_coupled else 90.0

        if _needle_coupled:
            _post_budget = 60.0

        elif _n <= 10:
            _post_budget = 15.0

        elif _n <= 26:
            _post_budget = 15.0 + (_n - 10) * (60.0 - 15.0) / (26 - 10)

        else:
            _post_budget = 60.0 + (_n - 26) * (180.0 - 60.0) / (40 - 26)

        self.ui.progress_widget.set_time_budget(_global_time + _post_budget)

        self.ui.progress_widget.start()

    def _refresh_optim_target_scatter_foreground(self) -> None:
        """Ensure target scatter markers stay above live curves."""

        if self.ui.target_scatter is None:
            return

        self.ui.spectrum_plot.removeItem(self.ui.target_scatter)

        self.ui.spectrum_plot.addItem(self.ui.target_scatter)

    def _apply_qw_values_to_front_table(self, qw: list[float], *, debug_failures: bool = False) -> None:
        """Apply QW values to the front table thickness column safely."""
        self.ui.front_table.blockSignals(True)
        for r in range(self.ui.front_table.rowCount()):
            try:
                sb = self.ui.front_table.cellWidget(r, 1)
                if sb:
                    sb.setValue(qw[r] if r < len(qw) else 0.0)
            except (AttributeError, ValueError, IndexError) as e:
                if debug_failures:
                    logging.debug(f"Could not set qw value for row {r}: {e}")
        self.ui.front_table.blockSignals(False)

    def on_stats_update(self, type_str: str, count: int) -> None:
        """Updates statistics"""

        if type_str == "EVAL":
            self.ui.stat_counters["EVAL"] = count

        elif type_str == "MINIMA":
            self.ui.stat_counters["MINIMA"] = count

        self.update_stats_display()

    def update_stats_display(self) -> None:
        """Optimization counters: minimum, evaluations, best score (rainbow icon)."""

        minima_count = self.ui.stat_counters.get("MINIMA", 0)

        eval_count = self.ui.stat_counters.get("EVAL", 0)

        best_count = self.ui.stat_counters.get("BEST", 0)

        text = f"♟️ {minima_count} minima  | 🎲 {eval_count} evals  | 🌈️ {best_count}"

        self.ui.stats_label.setText(text)

    def _update_busy_ui(self, busy_now: bool) -> None:
        """Updates Design-specific button states."""

        for btn in [self.ui.local_btn, self.ui.global_btn, self.ui.color_btn, self.ui.eval_btn]:
            btn.setEnabled(not busy_now)

        self.ui.stop_btn.setEnabled(busy_now)

