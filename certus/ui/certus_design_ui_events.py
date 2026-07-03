from __future__ import annotations
from certus.ui.certus_design_common import *

class EventsManager:
    def __init__(self, ui):
        self.ui = ui
    def _setup_shortcuts(self) -> None:
        """Register application-wide keyboard shortcuts."""

        QShortcut(QKeySequence("Ctrl+E"), self.ui, lambda: self.ui._schedule_eval(True))

        QShortcut(QKeySequence("Ctrl+O"), self.ui, lambda: self.ui.run_optim("local"))

        QShortcut(QKeySequence("Ctrl+G"), self.ui, lambda: self.ui.run_optim("global"))

        QShortcut(QKeySequence("Ctrl+S"), self.ui, self.ui.save_config)

        QShortcut(QKeySequence("Ctrl+Z"), self.ui, self.ui._undo)

        install_standard_shortcuts(
            self.ui,
            run=lambda: self.ui.run_optim("global"),
            stop=self.ui.stop_optim,
            help=self.open_help,
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
            extra={"Ctrl+L": lambda: getattr(self, "toggle_logs", lambda: None)()},
        )

        def _on_spectrum_drop(paths) -> None:
            if paths and hasattr(self, "load_config"):
                self.ui.load_config(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self.ui, _on_spectrum_drop, extensions=("json", "csv", "xlsx", "xls"))

    def _toggle_back_stack(self, state: int) -> None:
        """Toggle backside group visibility"""

        self.ui.back_group.setVisible(bool(state))

        self.ui._schedule_eval(True)

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox) -> None:
        """DESIGN specific: update Tikhonravov on QWOT change."""

        spinbox.valueChanged.connect(self._on_tikhonravov_points_changed)

    def _on_tikhonravov_points_changed(self, *_args) -> None:

        self.ui.orchestrator.schedule_update_tikhonravov_points(300)

    def _on_layer_added(self) -> None:
        """DESIGN specific: update thickness display and points."""

        self.ui._update_thickness_display()

        self.ui.orchestrator.schedule_update_tikhonravov_points(300)

    def _on_layer_deleted(self) -> None:
        """DESIGN specific: update thickness display and run local optimization."""

        self.ui._update_thickness_display()

        self.ui.run_optim("local")

    def add_back_layer(self) -> None:
        """Adds back layer"""

        if self.ui.back_table.rowCount() >= CFG.MAX_LAYERS:
            return

        mat = "H"

        if self.ui.back_table.rowCount() > 0:
            prev = self.ui._safe_get_combo_text(self.ui.back_table.rowCount() - 1, 0, self.ui.back_table)

            if prev:
                mat = "L" if prev == "H" else "H"

        self.ui._add_back_row(mat, 1.0)

        self.ui._schedule_eval()

    def del_back_layer(self) -> None:
        """Removes back layer"""

        r = self.ui.back_table.currentRow()

        if r < 0 and self.ui.back_table.rowCount() > 0:
            r = self.ui.back_table.rowCount() - 1

        if r >= 0:
            self.ui.back_table.removeRow(r)

            self.ui._schedule_eval(True)

    def remove_thinnest(self) -> None:
        """Removes thinnest layer (identically to the left panel button).

        Rules:

        - Finds the thinnest layer in the entire stack (including boundaries).

        - If it's a boundary layer (first or last), no merge step.

        - If it's an interior layer, merges adjacent identical materials.

        - Ends with a local polish and Pareto record.

        """

        N = self.ui.front_table.rowCount()

        if N <= 1:
            return

        # Get current thicknesses

        ep = self.ui.ep_current

        if ep is None or len(ep) != N:
            # Fallback if display not up to date

            self.ui._update_thickness_display()

            ep = self.ui.ep_current

            if ep is None:
                return

        # Identify thinnest layer

        r = int(np.argmin(ep))

        is_boundary = r == 0 or r == N - 1

        self.ui._save_undo_state()

        self.ui.log(f"Remove layer {r + 1}: {ep[r]:.1f}nm", "INFO")

        self.ui.front_table.removeRow(r)

        if not is_boundary:
            # Merging is only relevant when removing an interior layer

            # as it brings two previously separated layers together.

            self.ui._merge_adjacent_layers()

        else:
            self.ui._update_layer_count()

            self.ui._update_thickness_display()

        # Update target count and run optimization
        self.ui._workflow_best_rmse = float("inf")
        self.ui.orchestrator._target_layer_count = self.ui.front_table.rowCount()

        self.ui.run_optim("local", keep_history=True)

    def _paste_from_excel(self) -> None:
        """Pastes data from Excel into layer table"""

        clipboard = QApplication.clipboard()

        text = clipboard.text()

        if not text:
            return

        try:
            # Excel parse (tabs/cols, newlines/rows)

            lines = text.strip().split("\n")

            rows_data = []

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Split columns (tabs or multiple spaces)

                cols = line.split("\t")

                if len(cols) < 2:  # If no tab, try with multiple spaces
                    cols = [c for c in line.split(" ") if c]

                if len(cols) < 2:
                    continue

                # Parse columns

                # Fmt: Mat, QWOT, [Thick], [Var]

                mat = cols[0].strip()

                qwot_str = cols[1].strip()

                # Check if material is valid

                materials = [m for m in CFG.MATERIALS if m != "Substrate"]

                if mat not in materials:
                    # Try to find match (case insensitive)

                    mat_lower = mat.lower()

                    mat_found = None

                    for m in materials:
                        if m.lower() == mat_lower:
                            mat_found = m

                            break

                    if mat_found:
                        mat = mat_found

                    else:
                        self.ui.log(f"Invalid material ignored: {mat}", "WARNING")

                        continue

                # Parser QWOT

                try:
                    qwot = float(qwot_str.replace(",", "."))

                except ValueError:
                    self.ui.log(f"Invalid QWOT value ignored: {qwot_str}", "WARNING")

                    continue

                # Parse Var (optional, col 3 or 4)

                var = True  # default

                if len(cols) >= 3:
                    var_str = cols[2].strip().lower()

                    # Accept various forms: 0/1, true/false, yes/no, etc.

                    if var_str in ["0", "false", "f", "non", "n", "no", ""]:
                        var = False

                    elif var_str in ["1", "true", "t", "oui", "o", "yes", "y"]:
                        var = True

                    # If number, use as thickness (legacy format)

                    else:
                        try:
                            float(var_str.replace(",", "."))

                            # Likely a thickness, so Var remains True

                        except ValueError:
                            # Neither number nor boolean, ignore

                            pass

                rows_data.append((mat, qwot, var))

            if not rows_data:
                self.ui.log("No valid data to paste", "WARNING")

                return

            # Save state for undo

            self.ui._save_undo_state()

            # Clear table or append depending on selection

            current_row = self.ui.front_table.currentRow()

            if current_row >= 0:
                # Paste from selected row

                start_row = current_row

            else:
                # Clear table and paste from start

                self.ui.front_table.blockSignals(True)

                self.ui.front_table.setRowCount(0)

                self.ui.front_table.blockSignals(False)

                start_row = 0

            # Add rows

            self.ui.front_table.blockSignals(True)

            for i, (mat, qwot, var) in enumerate(rows_data):
                row = start_row + i

                if row >= self.ui.front_table.rowCount():
                    self.ui._add_front_row(mat, qwot, var)

                else:
                    # Replace existing row

                    # Mat

                    cb = self.ui._create_combo(mat)

                    cb.currentIndexChanged.connect(self.ui._merge_adjacent_layers)

                    self.ui.front_table.setCellWidget(row, 0, cb)

                    # QWOT

                    sb = self.ui._create_spin(qwot, dec=6)

                    sb.valueChanged.connect(self.ui._on_schedule_eval_signal)

                    sb.valueChanged.connect(self._on_tikhonravov_points_changed)

                    self.ui.front_table.setCellWidget(row, 1, sb)

                    # Var

                    chk = self.ui.front_table.cellWidget(row, 3).findChild(QCheckBox)

                    if chk:
                        chk.setChecked(var)

                    del_cw = self.ui.front_table.cellWidget(row, 4)

                    if del_cw:
                        del_chk = del_cw.findChild(QCheckBox)

                        if del_chk:
                            del_chk.setChecked(False)

            self.ui.front_table.blockSignals(False)

            self.ui._update_layer_count()

            self.ui._schedule_eval()

            self.ui.log(f"{len(rows_data)} row(s) pasted from Excel", "SUCCESS")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("[DESIGN.paste_from_excel] failed to paste from Excel | error=%s", e, exc_info=True)

    def add_target(self) -> None:
        """Adds spectral target"""

        r = self.ui.target_table.rowCount()

        self.ui.target_table.insertRow(r)

        col_idx = 0

        # Active Checkbox

        chk = QCheckBox()

        chk.setToolTip("Enable or disable this target.")

        chk.setChecked(True)

        chk.stateChanged.connect(self.ui._schedule_eval)

        chk.stateChanged.connect(self.ui._update_optim_point_count)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.ui.target_table.setCellWidget(r, col_idx, cw)

        col_idx += 1

        if self.ui.oblique_mode:
            # Oblique: Ang, Pol, Type, lmin, lmax, Vmin, Vmax, W

            # Angle

            angle_sb = self.ui._create_spin(0.0, dec=1, minv=0, maxv=90)

            angle_sb.setToolTip("Incident angle (degrees).")

            angle_sb.valueChanged.connect(self.ui._schedule_eval)

            self.ui.target_table.setCellWidget(r, col_idx, angle_sb)

            col_idx += 1

            # Polarization

            pol_combo = QComboBox()

            pol_combo.setToolTip("Target polarization: s, p, or Avg (unpolarized average).")

            pol_combo.addItems(["s", "p", "Avg"])

            pol_combo.currentTextChanged.connect(self.ui._schedule_eval)

            self.ui.target_table.setCellWidget(r, col_idx, pol_combo)

            col_idx += 1

            # Type (R or T)

            type_combo = QComboBox()

            type_combo.setToolTip("Target type: Reflectance (R) or Transmittance (T).")

            type_combo.addItems(["R", "T"])

            type_combo.currentTextChanged.connect(self.ui._schedule_eval)

            self.ui.target_table.setCellWidget(r, col_idx, type_combo)

            col_idx += 1

            # lambdamin, lambdamax

            for val, dec in [(400.0, 1), (700.0, 1)]:
                sb = self.ui._create_spin(val, dec=dec, minv=200, maxv=20000)

                tt = "Target wavelength range start (nm)." if val == 400.0 else "Target wavelength range end (nm)."

                sb.setToolTip(tt)

                sb.valueChanged.connect(self.ui._schedule_eval)

                sb.valueChanged.connect(self.ui._update_optim_point_count)

                sb.valueChanged.connect(lambda _checked=False: self.ui.orchestrator.schedule_update_tikhonravov_points(300))

                self.ui.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

            # Val min, Val max, Weight

            for i, (val, dec, maxv) in enumerate([(0.0, 3, 1), (1.0, 3, 1), (1.0, 1, 100)]):
                sb = self.ui._create_spin(val, dec=dec, minv=0, maxv=maxv)

                tts = ["Minimum target value.", "Maximum target value.", "Weight multiplier for this target."]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self.ui._schedule_eval)

                self.ui.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        else:
            # Normal Mode: lmin, lmax, Tmin, Tmax, Weight

            defs = [400.0, 700.0, 0.0, 0.5, 1.0]

            decs = [1, 1, 3, 3, 1]

            ranges = [(200, 20000), (200, 20000), (0, 1), (0, 1), (0, 100)]

            for i, val in enumerate(defs):
                sb = self.ui._create_spin(val, dec=decs[i], minv=ranges[i][0], maxv=ranges[i][1])

                tts = [
                    "Target wavelength range start (nm).",
                    "Target wavelength range end (nm).",
                    "Minimum target Transmittance (0-1).",
                    "Maximum target Transmittance (0-1).",
                    "Weight multiplier for this target.",
                ]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self.ui._on_schedule_eval_signal)

                if i in [0, 1]:
                    sb.valueChanged.connect(self.ui._update_optim_point_count)

                    sb.valueChanged.connect(lambda _checked=False: self.ui.orchestrator.schedule_update_tikhonravov_points(300))

                self.ui.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        self.ui._update_optim_point_count()

    def del_target(self) -> None:
        """Removes spectral target"""

        r = self.ui.target_table.currentRow()

        if r >= 0:
            self.ui.target_table.removeRow(r)

            self.ui._schedule_eval()

            self.ui._update_optim_point_count()

            self.ui.orchestrator.schedule_update_tikhonravov_points(200)

    def open_help(self) -> None:
        """Opens HTML documentation"""

        open_documentation("CERTUS_DESIGN")

    def closeEvent(self, event) -> None:
        """

        Handles application closure with proper cleanup of all workers.

        Ensures all QThread workers are properly stopped to avoid

        "QThread: Destroyed while thread is still running" warnings.

        """

        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        # Ensure all workers are stopped to avoid "QThread: Destroyed while thread is still running"

        threads_to_stop = []
        try:
            optim_t = getattr(self, "optim_thread", None)
            if optim_t is not None:
                threads_to_stop.append((optim_t, getattr(self, "optim_worker", None)))
        except RuntimeError:
            pass
        try:
            needle_t = getattr(self, "needle_thread", None)
            if needle_t is not None:
                threads_to_stop.append((needle_t, getattr(self, "needle_worker", None)))
        except RuntimeError:
            pass
        try:
            col_t = getattr(self, "col_thread", None)
            if col_t is not None:
                threads_to_stop.append((col_t, getattr(self, "col_worker", None)))
        except RuntimeError:
            pass

        for thread, worker in threads_to_stop:
            try:
                if thread is not None:
                    stop_qt_worker_thread_safely(
                        thread,
                        worker,
                        timeout_ms=2000,
                        logger=getattr(self, "logger", None),
                    )
            except (RuntimeError, AttributeError) as e:
                if hasattr(self, "logger") and self.ui.logger:
                    self.ui.logger.debug(f"Error stopping thread: {e}")

        workers = [
            getattr(self, "warmup_worker", None),
            getattr(self, "eval_worker", None),
        ]

        for worker in workers:
            try:
                if worker and worker.isRunning():
                    # Attempt cooperative stop

                    if hasattr(worker, "request_stop"):
                        worker.request_stop()

                    elif hasattr(worker, "requestInterruption"):
                        worker.requestInterruption()

                    # Wait for graceful shutdown (2000ms timeout)

                    if not worker.wait(2000):
                        logging.critical(
                            f"Worker {type(worker).__name__} did not stop within 2s in closeEvent - "
                            "skipping terminate() to avoid unsafe thread kill."
                        )

            except (RuntimeError, AttributeError) as e:
                # Non-critical: worker may already be destroyed

                if hasattr(self, "logger") and self.ui.logger:
                    self.ui.logger.debug(f"Error stopping worker {type(worker).__name__}: {e}")

        # Call parent cleanup (stops base class workers)
        pass

