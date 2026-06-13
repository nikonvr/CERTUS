from certus.core.certus_core import __version__, APP_SUITE_VERSION
import os
from pathlib import Path
import multiprocessing
import sys
import functools
from certus.core.certus_core import create_module_environment
import logging
import time
import traceback
import copy
from threading import Event
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg
from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QThread,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CFG,
    ensure_numpy_array,
    get_complex_dtype,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)
from certus.utils.errors import safe_ui_action
from certus.workers.certus_design_worker_utils import (
    build_pglobal_optimizer,
    build_pglobal_config_from_cfg,
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_post_optim_time_budget_seconds,
    optim_prepare_stack_nk_back,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    prepare_pglobal_inputs_from_state,
    prepare_pglobal_optimizer_runtime,
    run_coord_descent_5cycles,
    run_pglobal_restart_loop,
)
from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)
from certus_physics import (  # Cache & Utils; Gradient Logic (Analytic); Numba Functions
    Layer,
    Material,
    ObliqueTarget,
    PGlobalConfig,
    PGlobalOptimizer,
    Target,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_gradient_contrib_analytic,
    cost_numba_fast,
    delta_e_2000,
    init_thickness,
    lab_to_rgb,
    needle_scan_cached,
    prepare_targets_vectorized,
    xyz_from_spectrum,
    xyz_to_lab,
)
from certus.utils.certus_index_utils import spectral_rmse_weights
from certus.ui.certus_ui import (
    CertusTheme,
    CertusBaseApp,
    CertusScientificPlot,
    CertusThemeToggle,
    CertusCard,
    CertusCollapsible,
    CertusStatusPill,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    EnhancedProgressWidget,
    FlashyCard,
    WelcomeGuideWidget,
    WorkerSignals,
    certus_get_save_file_name,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    create_flashy_grid,
    create_header_logo_widget,
    create_top_actions_bar,
    get_export_config,
    init_certus_app,
    open_documentation,
    plot_widget_plot_finite,
)
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker
from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)
from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)
from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *
from certus.ui.mixins.certus_design_plot_mixin import CertusDesignUIPlotMixin

class CertusDesignCoreMixin:
    def _get_default_splitter_sizes(self) -> list[int]:
        """DESIGN specific splitter sizes."""

        return [450, 1150]

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for DESIGN."""

        substrate_type = "Custom"

        substrate_index = "N/A"

        if hasattr(self, "mat_widgets") and "Substrate" in self.mat_widgets:
            w = self.mat_widgets["Substrate"]

            substrate_type = w["preset"].currentText()

            n4 = w["n4"].value()

            n7 = w["n7"].value()

            substrate_index = f"n@400={n4:.3f}, n@700={n7:.3f}"

        return substrate_type, substrate_index

    def _show_substrate_info_window(self) -> None:
        """Display stack information in a separate window"""

        if getattr(self, "substrate_info_window", None) and self.substrate_info_window.isVisible():
            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        if getattr(self, "substrate_info_window", None) and not self.substrate_info_window.isVisible():
            self.substrate_info_window.show()

            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        self.substrate_info_window = QDialog(self)

        self.substrate_info_window.setWindowTitle("🔬 Stack information")

        self.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.substrate_type_label = QLabel("N/A")

        self.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.substrate_type_label, 0, 1)

        info_layout.addWidget(self.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Structure (QWOT)")

        structure_layout = structure_card.body

        self.structure_text = QTextEdit()

        self.structure_text.setReadOnly(True)

        self.structure_text.setMaximumHeight(200)

        structure_layout.addWidget(self.structure_text)

        layout.addWidget(structure_card)

        btn_layout = QHBoxLayout()

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(self.substrate_info_window.close)

        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.substrate_info_window.setLayout(layout)

        self.substrate_info_window.show()

        self.substrate_info_window.raise_()

        self.substrate_info_window.activateWindow()

        self._update_substrate_info()

    def _toggle_oblique_mode(self, state: int) -> None:
        """Toggle oblique mode and update UI"""

        self.oblique_mode = state == Qt.CheckState.Checked.value

        self._update_target_table_headers()

        # Convert existing targets if needed

        if self.oblique_mode:
            # Convert normal to oblique targets

            if hasattr(self, "target_widgets") and len(self.target_widgets) > 0:
                self.oblique_targets = []

                for tgt in self.target_widgets:
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

                        self.oblique_targets.append(oblique_tgt)

        else:
            # Convert oblique to normal targets

            if len(self.oblique_targets) > 0:
                self.target_widgets = []

                for tgt in self.oblique_targets:
                    if isinstance(tgt, ObliqueTarget):
                        normal_tgt = Target(
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                        )

                        self.target_widgets.append(normal_tgt)

        # Reload table

        self._load_targets_to_table()

        self._schedule_eval(True)

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self):
            self.status_label.setText("Logs copied to clipboard.")

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

        self._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self._schedule_eval(True)

    def _trigger_post_undo_action(self) -> None:
        """DESIGN specific post-undo action."""

        self.run_optim("local")

    def _get_optim_wls(self) -> np.ndarray:
        """Calculates wavelengths for optimization"""

        if self.oblique_mode:
            tgts = self._get_oblique_tgts()

        else:
            tgts = self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            return np.array([])

        wls_list = []

        n_points = self.points_per_target_spin.value()

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

    def _update_optim_point_count(self) -> None:
        """Updates optimization point counter"""

        wls = self._get_optim_wls()

        self.npts_spin.setValue(len(wls))

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

            stack = self._get_front_stack()

            # Use correct targets based on mode (normal or oblique)

            if self.oblique_mode:
                tgts = self._get_oblique_tgts()

            else:
                tgts = self._get_tgts()

            l0 = self.l0_spin.value()

            if not stack or not mats:
                return 50  # Default

            # Calculate total optical thickness L

            # Use current thicknesses if available, else calc from QWOT

            if self.ep_current is not None and len(self.ep_current) == len(stack):
                ep = self.ep_current

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

        try:
            tikhon_points = self._calculate_tikhonravov_points()

            if tikhon_points > 0:
                current_val = self.points_per_target_spin.value()

                # Update only if change significant

                if abs(tikhon_points - current_val) > max(5, current_val * 0.15):  # Threshold 15% or 5 points
                    self.points_per_target_spin.blockSignals(True)

                    self.points_per_target_spin.setValue(tikhon_points)

                    self.points_per_target_spin.blockSignals(False)

                    self._update_optim_point_count()

                    self.log(
                        f"Tikhonravov: Auto-updated points/target to {tikhon_points}",
                        "INFO",
                    )

        except (AttributeError, ValueError) as e:
            logging.debug("[DESIGN.profile] could not update Tikhonravov points | error=%s", e)

    def _get_materials(self) -> dict:
        """Retrieves configured materials."""

        try:
            result = {k: Material(w["n4"].value(), w["n7"].value()) for k, w in self.mat_widgets.items()}

            return result

        except (AttributeError, KeyError) as e:
            logging.debug("[DESIGN.profile] could not get materials | error=%s", e)

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        if not self.oblique_mode:
            return []  # Sinon mode normal : _get_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                active = chk.isChecked() if chk else False

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                angle = angle_w.value() if angle_w else 0.0

                # Polarisation

                pol_w = self.target_table.cellWidget(r, 2)

                polarization = pol_w.currentText() if pol_w else "s"

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                target_type = type_w.currentText() if type_w else "T"

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                lmin = lmin_w.value() if lmin_w else 400.0

                lmax = lmax_w.value() if lmax_w else 700.0

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                val_min = vmin_w.value() if vmin_w else 0.0

                val_max = vmax_w.value() if vmax_w else 1.0

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

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

        self.target_table.setRowCount(0)

        if self.oblique_mode:
            for tgt in self.oblique_targets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                if angle_w:
                    angle_w.setValue(tgt.angle)

                # Pol

                pol_w = self.target_table.cellWidget(r, 2)

                if pol_w:
                    pol_w.setCurrentText(tgt.pol)

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                if type_w:
                    type_w.setCurrentText(tgt.target_type)

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                if lmin_w:
                    lmin_w.setValue(tgt.lmin)

                if lmax_w:
                    lmax_w.setValue(tgt.lmax)

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                if vmin_w:
                    vmin_w.setValue(tgt.tmin)

                if vmax_w:
                    vmax_w.setValue(tgt.tmax)

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

                if weight_w:
                    weight_w.setValue(tgt.w)

        else:
            for tgt in self.target_widgets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # lambdamin, lambdamax, Tmin, Tmax, Weight

                for i, val in enumerate([tgt.lmin, tgt.lmax, tgt.tmin, tgt.tmax, tgt.w]):
                    w = self.target_table.cellWidget(r, i + 1)

                    if w:
                        w.setValue(val)

    def _on_front_thickness_updated(self) -> None:
        """DESIGN specific: update Tikhonravov points."""

        QTimer.singleShot(150, self._update_tikhonravov_points)

    def _reset_run_optim_workflow_state(self, mode: str) -> None:
        """Reset workflow state and UI counters for a fresh optimization start."""

        self._target_layer_count = self.front_table.rowCount()

        self._topology_stable = True

        self._overshoot_active = False

        self._overshoot_done = False

        self._healing_phase = None

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

        self._initial_cleared = False

        self._clean_live_curves()

        self.log(f"Starting {mode} optimization (PGLOBAL)...", "INFO")

        self.stat_counters["EVAL"] = 0

        self.accumulated_evals = 0

        self.stat_counters["MINIMA"] = 0

        self.update_stats_display()

        self.best_rmse_label.setText("Best RMSE: N/A")

        self._workflow_best_rmse = float("inf")

        self._best_eval_result = None

        self._best_eval_rmse = float("inf")

        self._workflow_stopped = False

        self._decimation_done = False

        self._export_pending = False

        self._post_optim_start_time = None

        self._stack_info_best_ep = None

        self._stack_info_best_rmse = None

        self._stack_info_last_update = 0.0

        import time as _time

        self._workflow_wall_start = _time.time()

        self.mse_data = {"iterations": [], "errors": []}

        if self.convergence_curve is not None:
            self.convergence_curve.setData([], [])

    def _shutdown_previous_optim_worker(self) -> None:
        """Stop any running optimization worker before starting a new cycle."""

        from certus.workers.certus_design_worker_utils import stop_qt_worker_thread_safely

        if self.optim_thread is not None:
            try:
                stop_qt_worker_thread_safely(
                    self.optim_thread,
                    self.optim_worker,
                    timeout_ms=2000,
                    logger=getattr(self, "logger", None),
                )
            except RuntimeError:
                pass

        self.optim_worker = None
        self.optim_thread = None

    def _collect_run_optim_inputs(self) -> tuple:
        """Collect and validate inputs required by run_optim."""

        stack = self._get_front_stack()

        if not [l for l in stack if l.var]:
            self.log("No variable layers.", "WARNING")

            return None, None, None, None, None

        mats = self._get_materials()

        tgts = self._get_oblique_tgts() if self.oblique_mode else self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            self.log("No valid targets.", "WARNING")

            return None, None, None, None, None

        ep0 = init_thickness(stack, self.l0_spin.value(), mats)

        wls = self._get_optim_wls()

        return stack, mats, active, ep0, wls

    def _initialize_run_optim_progress_state(self, cfg: dict, keep_history: bool) -> None:
        """Initialize progress counters and optional time budget for a run."""

        self._optim_max_iter = 100

        self._optim_current_iter = 0

        self._optim_n_evals = 0

        if keep_history:
            return

        _n = len(cfg.get("ep0", []))

        _mode = cfg.get("mode", "global")

        allow_growth = getattr(self, "allow_growth_check", None)

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

        self.progress_widget.set_time_budget(_global_time + _post_budget)

        self.progress_widget.start()

    def _refresh_optim_target_scatter_foreground(self) -> None:
        """Ensure target scatter markers stay above live curves."""

        if self.target_scatter is None:
            return

        self.spectrum_plot.removeItem(self.target_scatter)

        self.spectrum_plot.addItem(self.target_scatter)

    def _apply_qw_values_to_front_table(self, qw: list[float], *, debug_failures: bool = False) -> None:
        """Apply QW values to the front table thickness column safely."""
        self.front_table.blockSignals(True)
        for r in range(self.front_table.rowCount()):
            try:
                sb = self.front_table.cellWidget(r, 1)
                if sb:
                    sb.setValue(qw[r] if r < len(qw) else 0.0)
            except (AttributeError, ValueError, IndexError) as e:
                if debug_failures:
                    logging.debug(f"Could not set qw value for row {r}: {e}")
        self.front_table.blockSignals(False)

    def on_stats_update(self, type_str: str, count: int) -> None:
        """Updates statistics"""

        if type_str == "EVAL":
            self.stat_counters["EVAL"] = count

        elif type_str == "MINIMA":
            self.stat_counters["MINIMA"] = count

        self.update_stats_display()

    def update_stats_display(self) -> None:
        """Optimization counters: minimum, evaluations, best score (rainbow icon)."""

        minima_count = self.stat_counters.get("MINIMA", 0)

        eval_count = self.stat_counters.get("EVAL", 0)

        best_count = self.stat_counters.get("BEST", 0)

        text = f"♟️ {minima_count} minima  | 🎲 {eval_count} evals  | 🌈️ {best_count}"

        self.stats_label.setText(text)

    def _update_busy_ui(self, busy_now: bool) -> None:
        """Updates Design-specific button states."""

        for btn in [self.local_btn, self.global_btn, self.color_btn, self.eval_btn]:
            btn.setEnabled(not busy_now)

        self.stop_btn.setEnabled(busy_now)

