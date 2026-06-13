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

class CertusDesignStateMixin:
    def _load_defaults(self) -> None:
        """Loads default values"""

        # Block signals to avoid massive re-evaluations during reset

        self.blockSignals(True)

        try:
            defaults = {
                "H": (2.35, 2.30),
                "L": (1.46, 1.46),
                "A": (2.05, 2.00),
                "B": (1.75, 1.73),
                "C": (1.60, 1.58),
                "Substrate": (1.52, 1.51),
            }

            for name, (n4, n7) in defaults.items():
                if name in self.mat_widgets:
                    self.mat_widgets[name]["n4"].setValue(n4)

                    self.mat_widgets[name]["n7"].setValue(n7)

                    self.mat_widgets[name]["preset"].setCurrentText("Custom")

            # Reset Global Parameters

            if hasattr(self, "l0_spin"):
                self.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self, "back_check"):
                self.back_check.setChecked(False)

            if hasattr(self, "back_coat_check"):
                self.back_coat_check.setChecked(False)

            if hasattr(self, "oblique_check"):
                self.oblique_check.setChecked(False)

            if hasattr(self, "auto_scale_y_check"):
                self.auto_scale_y_check.setChecked(True)

            if hasattr(self, "allow_growth_check"):
                self.allow_growth_check.setChecked(True)

            if hasattr(self, "pre_polish_check"):
                self.pre_polish_check.setChecked(False)

            # Add default layers

            for _ in range(4):
                self.add_front_layer()

            # Add default target

            self.add_target()

            # Default optimization parameters

            self.n100_spin.setValue(6000)

            self.max_clusters_spin.setValue(40)

            self.global_cycles_spin.setValue(50)

            if hasattr(self, "points_per_target_spin"):
                self.points_per_target_spin.setValue(50)

            # Default MC parameters

            if hasattr(self, "mc_n_spin"):
                self.mc_n_spin.setValue(200)

            if hasattr(self, "mc_sigma_spin"):
                self.mc_sigma_spin.setValue(2.0)

            # Update Tikhonravov points after loading defaults

            QTimer.singleShot(500, self._update_tikhonravov_points)

            self.log("Default configuration loaded with optimized PGLOBAL settings.", "INFO")

        finally:
            self.blockSignals(False)

            # Force one final evaluation to show the default design

            self._schedule_eval(instant=True)

    def _pre_save_smart_cleanup(self) -> None:
        """Run the pre-save cleanup + heal step (idempotent)."""

        if self.front_table.rowCount() > 0:
            self.log("Final cleanup before save...", "INFO")

            removed = self.smart_cleanup()

            if removed > 0:
                self.log(
                    f"Final cleanup: removed {removed} layers. Optimizing...",
                    "INFO",
                )

                # Run fast local optimization to heal

                self._is_internal_restart = True

                # Note: Cannot wait for optimization here (async)

                self._schedule_eval(True)  # Update display

    def _post_save_config(self, filename: str) -> None:
        """UX feedback after a successful save."""

        self.log(f"Configuration saved:  {filename}", "SUCCESS")

        show_toast(self, f"Saved: {Path(filename).name}", "success")

    def _collect_config(self) -> dict:
        """Build the JSON-serialisable config dict from current UI state."""

        self._pre_save_smart_cleanup()

        cfg = {
            "version": APP_SUITE_VERSION,
            "l0": self.l0_spin.value(),
            "materials": {
                n: {
                    "n4": w["n4"].value(),
                    "n7": w["n7"].value(),
                    "preset": w["preset"].currentText(),
                }
                for n, w in self.mat_widgets.items()
            },
            "front": [{"mat": l.mat, "qw": l.qwot, "var": l.var} for l in self._get_front_stack()],
            "back_en": self.back_check.isChecked(),
            "back_coat": self.back_coat_check.isChecked(),
            "back": [{"mat": l.mat, "qw": l.qwot} for l in self._get_back_stack()],
            "targets": (
                [
                    {
                        "on": t.on,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "tmin": t.tmin,
                        "tmax": t.tmax,
                        "w": t.w,
                    }
                    for t in self._get_tgts()
                ]
                if not self.oblique_mode
                else [
                    {
                        "active": t.on,
                        "angle": t.angle,
                        "polarization": t.pol,
                        "target_type": t.target_type,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "val_min": t.tmin,
                        "val_max": t.tmax,
                        "weight": t.w,
                    }
                    for t in self._get_oblique_tgts()
                ]
            ),
            "oblique_mode": self.oblique_mode,
            "optimization": {
                "points_per_target": self.points_per_target_spin.value(),
                "n100": self.n100_spin.value(),
                "max_clusters": self.max_clusters_spin.value(),
                "max_iter": self.global_cycles_spin.value(),
                "mc_n": self.mc_n_spin.value(),
                "mc_sigma": self.mc_sigma_spin.value(),
                # Extra params
                "pre_polish": (self.pre_polish_check.isChecked() if hasattr(self, "pre_polish_check") else False),
                "allow_growth": (self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True),
                "auto_scale_y": (self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True),
            },
        }

        return cfg

    def _apply_config(self, c: dict) -> None:
        """Apply a parsed configuration dict to the UI (Lot C)."""

        self.log("Format Version: %s" % c.get("version", "Unknown"), "INFO")

        self._last_config_file = getattr(self, "_last_config_file", None)
        self.l0_spin.setValue(c.get("l0", 500))

        self._apply_material_config(c.get("materials", {}))

        self._apply_stack_rows(c.get("front", []), back=False)

        self.back_check.setChecked(c.get("back_en", False))
        self.back_coat_check.setChecked(c.get("back_coat", False))
        self._apply_stack_rows(c.get("back", []), back=True)

        oblique_mode = c.get("oblique_mode", False)
        self.log(f"[LOAD] Oblique mode: {oblique_mode}", "INFO")
        self.oblique_targets = []
        if hasattr(self, "oblique_check"):
            self.oblique_check.setChecked(oblique_mode)
        self.oblique_mode = oblique_mode

        self.log(f"[LOAD] Loading {len(c.get('targets', []))} targets...", "INFO")
        self._update_target_table_headers()
        self.target_table.setRowCount(0)
        self._apply_target_config(c.get("targets", []), oblique_mode)

        self._apply_optimization_config(c.get("optimization", {}))
        self._update_optim_point_count()
        self._schedule_eval(True)
        self._update_layer_count()

    def _apply_optimization_config(self, opt: dict) -> None:
        """Apply optimization controls from a config dict."""

        self.points_per_target_spin.setValue(opt.get("points_per_target", self.points_per_target_spin.value()))
        self.n100_spin.setValue(opt.get("n100", self.n100_spin.value()))
        self.max_clusters_spin.setValue(opt.get("max_clusters", self.max_clusters_spin.value()))
        self.global_cycles_spin.setValue(opt.get("max_iter", self.global_cycles_spin.value()))
        self.mc_n_spin.setValue(opt.get("mc_n", self.mc_n_spin.value()))
        self.mc_sigma_spin.setValue(opt.get("mc_sigma", self.mc_sigma_spin.value()))

        if hasattr(self, "pre_polish_check"):
            self.pre_polish_check.setChecked(opt.get("pre_polish", self.pre_polish_check.isChecked()))

        if hasattr(self, "allow_growth_check"):
            self.allow_growth_check.setChecked(opt.get("allow_growth", self.allow_growth_check.isChecked()))

        if hasattr(self, "auto_scale_y_check"):
            self.auto_scale_y_check.setChecked(opt.get("auto_scale_y", self.auto_scale_y_check.isChecked()))

    def _apply_material_config(self, materials: dict) -> None:
        """Apply saved material presets and custom n values."""

        for n, d in materials.items():
            if n not in self.mat_widgets:
                continue
            preset_name = d.get("preset", "Custom")
            self.mat_widgets[n]["preset"].setCurrentText(preset_name)
            if preset_name == "Custom":
                self.mat_widgets[n]["n4"].setValue(d.get("n4", 1.5))
                self.mat_widgets[n]["n7"].setValue(d.get("n7", 1.5))

    def _apply_target_config(self, targets: list[dict], oblique_mode: bool) -> None:
        """Apply target rows from a config dict."""

        for t in targets:
            self.add_target()
            r = self.target_table.rowCount() - 1
            active_cb = self.target_table.cellWidget(r, 0)
            if active_cb:
                active_cb.findChild(QCheckBox).setChecked(t.get("active", t.get("on", True)))

            if oblique_mode:
                widget_updates = [
                    (1, t.get("angle", 0.0)),
                    (2, t.get("polarization", "s")),
                    (3, t.get("target_type", "T")),
                    (4, t.get("lmin", 400)),
                    (5, t.get("lmax", 700)),
                    (6, t.get("val_min", t.get("tmin", 0.0))),
                    (7, t.get("val_max", t.get("tmax", 1.0))),
                    (8, t.get("weight", t.get("w", 1.0))),
                ]
                for idx, value in widget_updates:
                    w = self.target_table.cellWidget(r, idx)
                    if w is None:
                        continue
                    if hasattr(w, "setCurrentText"):
                        w.setCurrentText(value)
                    else:
                        w.setValue(value)
            else:
                for idx, value in enumerate([t.get("lmin", 400), t.get("lmax", 700), t.get("tmin", 0), t.get("tmax", 1), t.get("w", 1)], start=1):
                    w = self.target_table.cellWidget(r, idx)
                    if w:
                        w.setValue(value)

    def _apply_stack_rows(self, rows: list[dict], *, back: bool) -> None:
        """Apply front or back stack rows from a config dict."""

        add_row = self._add_back_row if back else self._add_front_row
        table = self.back_table if back else self.front_table
        table.blockSignals(True)
        table.setRowCount(0)
        for row in rows:
            if back:
                add_row(row["mat"], row["qw"])
            else:
                add_row(row["mat"], row["qw"], row["var"])
        table.blockSignals(False)

    def _post_load_config(self, filename: str, config: dict) -> None:
        """UX side-effects after a successful load (summary dialog, toast, ...)."""

        self._last_config_file = filename

        self.log(f"Configuration loaded:  {filename}", "SUCCESS")

        oblique_mode = bool(config.get("oblique_mode", False))

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            mats_cfg = config.get("materials", {})

            front_cfg = config.get("front", [])

            back_cfg = config.get("back", [])

            tgts_cfg = config.get("targets", [])

            l0_val = float(config.get("l0", self.l0_spin.value()))

            summary = build_summary_plain_text(
                "CERTUS DESIGN - Load Summary",
                [
                    f"File: {Path(filename).resolve()}",
                    "",
                    "General",
                    f"Version: {config.get('version', 'unknown')}",
                    (f"Reference wavelength l0: {l0_val:.2f} nm", not (100.0 <= l0_val <= 10000.0)),
                    "",
                    "Stack",
                    f"Materials declared: {len(mats_cfg)}",
                    (f"Front layers: {len(front_cfg)}", len(front_cfg) <= 0),
                    f"Back enabled: {'yes' if bool(config.get('back_en', False)) else 'no'}",
                    f"Back coating enabled: {'yes' if bool(config.get('back_coat', False)) else 'no'}",
                    (
                        f"Back layers: {len(back_cfg)}",
                        bool(config.get("back_coat", False)) and len(back_cfg) <= 0,
                    ),
                    f"Oblique mode: {'yes' if oblique_mode else 'no'}",
                    "",
                    "Targets",
                    (f"Targets loaded: {len(tgts_cfg)}", len(tgts_cfg) <= 0),
                ],
            )

            show_load_summary_dialog(self, "DESIGN Load Summary", summary)

        logging.info("[LOAD] Calling _schedule_eval (final)...")

        self._schedule_eval()

        self._apply_optimization_config(config.get("optimization", {}))
        self._update_optim_point_count()
        self._update_layer_count()

        _load_start = getattr(self, '_load_config_start_time', None)
        if _load_start is not None:
            self.log(f"[LOAD] === load_config complete in {(time.time() - _load_start) * 1000:.1f}ms ===", "INFO")

        self.log(f"Config loaded from {Path(filename).name}", "SUCCESS")

        show_toast(self, f"Loaded: {Path(filename).name}", "success")

    def reset_to_defaults(self) -> Any:
        """Resets the entire application to factory defaults (clean slate)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

