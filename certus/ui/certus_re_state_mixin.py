from __future__ import annotations
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_math import re_substrate_cauchy_n_re_from_theta
from certus.utils.certus_re_math import format_re_drift_log_triplet_pct
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_PHASE2_FD_MAX_WORKERS
from certus.utils.certus_re_config import RE_PHASE2_FD_PARALLEL
from certus.utils.certus_re_config import RE_PHASE2_ONESIDED_SPLINE_FD
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_config import RE_RE_DEADZONE_QWOT_ABS
from certus.utils.certus_re_config import RE_RE_DEADZONE_DELTA_RE_ABS
from certus.utils.certus_re_config import RE_HL_DELTA_RE_REG_SQRT_W
from certus.utils.certus_re_config import RE_SPEED_PRESETS
import logging
import copy
import time
import os
import functools
import multiprocessing
import traceback
from pathlib import Path
import sys
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg

from certus.core.certus_core import certus_timestamp_display, setup_logging, CFG, create_module_environment, NUMERICAL_FAULT_EXCEPTIONS, get_resource_path, certus_timestamp_file

from certus.ui.certus_qt_widgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox,
    QColor, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFont, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QKeySequence, QLabel, QMessageBox,
    QPushButton, QRadioButton, QScrollArea, QShortcut, QSplitter, QStackedWidget,
    QStatusBar, QTableWidgetItem, QTabWidget, QTextEdit, QTimer, Qt, QVBoxLayout,
    QWidget,
)

from certus_physics import Layer, ObliqueTarget, init_thickness, calc_spectrum_front_wrapper, calc_spectrum_full_exact_wrapper

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale, spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display, spectrum_eval_plot_curves,
    spectrum_eval_run_preamble, spectrum_eval_start_worker,
)

from certus.ui.certus_ui import (
    attach_excel_clipboard_context_menu, CertusBaseApp, CertusCard, CertusCollapsible,
    CertusScientificPlot, CertusStatusPill, CertusTheme, CertusThemeToggle,
    enable_file_drop, EnhancedProgressWidget, ExcelTableWidget, FlashyCard,
    get_certus_last_dir, install_standard_shortcuts, safe_ui_action,
    set_certus_last_dir, show_toast, WelcomeGuideWidget, create_flashy_grid,
    create_header_logo_widget, create_styled_button, create_styled_label,
    create_top_actions_bar, init_certus_app, set_certus_window_icon,
    install_skeleton_loader, remove_skeleton_loader, wrap_scientific_plot_with_toolbar,
    open_documentation, confirm_stop_with_timeout,
)

from certus.utils.certus_ux import build_premium_overrides
from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus.workers.certus_re_workers import REWorker
from certus.ui.certus_re_ui import CertusREResultsDialog

from certus.utils.certus_re_helpers import (
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    re_qwot_penalty_weight_from_preset,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    _RE_CANONICAL_SHEETS,
    _RE_FT_COL_MAT,
    _RE_FT_COL_N,
    _RE_FT_COL_NUM,
    _RE_FT_COL_QW,
    _RE_FT_COL_THICK,
    _parse_re_rmse_combined_from_progress_message,
    _re_calc_spectrum_for_config,
    _re_cell_str,
    _re_find_measurement_wavelength_column,
    _re_header_is_wavelength_label,
    _re_header_looks_like_spectrum_title,
    _re_index_column_map,
    _re_index_split_header_and_data,
    _re_measurement_values_are_percent,
    _re_p4_ap_staircase_polyline,
    _re_p4_kwargs_from_opt_result,
    _re_p4_sort_knot_pairs,
    _re_parse_design_metadata_row,
    _re_parse_design_qwot_rows,
    _re_qwot_rmse_abs_delta_at_l0,
    _re_resolve_re_workbook_sheets,
    _re_rmse_combined_spectral_qwot,
    _re_rmse_oblique_weighted,
    _re_sort_results_best_for_table_and_apply,
    format_re_spline_knots_log,
    parse_re_column_header,
    re_apply_re_index_model,
    re_delta_qwot_per_layer,
    re_drift_result_log_suffix,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    TabularMaterial,
    ParsedREColumn,
)
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class CertusREStateMixin:
    """CertusREStateMixin for CERTUS_RE."""

    def reset_to_defaults(self):
        """Reset the application (tables, results, RE state, workers stopped)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

    def _load_defaults(self):
        """Loads default values"""

        self._re_mode_active = False

        self._re_nfev_cumulative = 0

        self._workflow_best_rmse = float("inf")

        self._clear_re_session_data()

        # Block signals to avoid massive re-evaluations during reset

        self.blockSignals(True)

        try:
            # Reset Global Parameters

            if hasattr(self, "l0_spin"):
                self.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self, "back_check"):
                self.back_check.setChecked(False)

            if hasattr(self, "auto_scale_y_check"):
                self.auto_scale_y_check.setChecked(True)

            self.cfg["re_beam_aperture_deg"] = float(RE_GUI_DEFAULT_BEAM_APERTURE_DEG)

            self.log("Default configuration loaded (CERTUS-RE).", "INFO")

            self._clear_re_excel_readout_ui()

        finally:
            self.blockSignals(False)

            # Force one final evaluation to show the default design

            self._schedule_eval(instant=True)

    def _normalize_re_config(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Normalize legacy RE JSON payloads before applying them to the UI."""
        if not isinstance(cfg, dict):
            return {}
        out = dict(cfg)
        aliases = {
            # Substrate and film concepts are distinct in RE: keep substrate keys explicit.
            "substratee_choice": "substrate_choice",
            "lambda_ref_nm": "l0",
            "lambda0": "l0",
            "stack": "stack_string",
            "qwot": "stack_string",
        }
        for src, dst in aliases.items():
            if src in out and dst not in out:
                out[dst] = out[src]
        if "re_gui" in out and isinstance(out["re_gui"], dict):
            self._re_apply_gui_prefs_from_dict(out["re_gui"])
        for key in (
            "l0", "wl_step", "scan_wl_min", "scan_wl_max", "scan_wl_step",
            "dynamics_threshold", "min_transmission_floor", "min_spectral_resolution",
            "robustness_seed", "iter_divider_start", "iter_divider_end",
            "step0_sigma", "thickness_tolerance_nm", "consensus_num_seeds",
        ):
            if key in out and isinstance(out[key], str):
                try:
                    out[key] = float(str(out[key]).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        if isinstance(out.get("stack_string"), list):
            out["stack_string"] = ",".join(str(x) for x in out["stack_string"])
        return out

    def load_config(self, path: str) -> bool:
        """Load a CERTUS RE JSON configuration or Excel RE workbook path."""
        if not path:
            return False
        p = Path(path)
        if p.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
            return self.load_reverse_engineering_from_path(str(p))
        if not p.is_file():
            self.log(f"RE: config file not found: {path!r}", "ERROR")
            return False
        try:
            import json
            raw = json.loads(p.read_text(encoding="utf-8-sig"))
            cfg = self._normalize_re_config(raw if isinstance(raw, dict) else {})
            workbook_path = cfg.get("workbook_path") or cfg.get("re_workbook_path")
            if workbook_path and Path(str(workbook_path)).is_file():
                return self.load_reverse_engineering_from_path(str(workbook_path))
            if "l0" in cfg and hasattr(self, "l0_spin"):
                self.l0_spin.setValue(float(cfg["l0"]))
            if "re_gui" in raw and isinstance(raw["re_gui"], dict):
                self._re_apply_gui_prefs_from_dict(raw["re_gui"])
            self.log("RE JSON loaded and normalized.", "INFO")
            return True
        except Exception as e:
            self.log(f"RE JSON load error: {e}", "ERROR")
            return False

    def _clear_re_session_data(self) -> None:
        """Reset all RE session specific data (after file reset or JSON load)."""

        self._re_loaded = False

        self._re_workbook_path = None

        self._re_targets = []

        self._re_meas_lambda_min_nm = None

        self._re_meas_lambda_max_nm = None

        self._re_tabular_H = None

        self._re_tabular_L = None

        self._re_tabular_Sub = None

        self._re_spline_dH = None

        self._re_spline_dL = None

        self._re_spline_lam2_nm = None

        self._re_sub_cauchy_a0 = None

        self._re_sub_cauchy_a1 = None

        self._re_sub_cauchy_a2 = None

        self._re_opt_a_pct = 0.0

        self._re_opt_b_pct = 0.0

        self._re_opt_f_pct = 0.0

        self._re_clear_re_nk_preview()

        self._clear_re_excel_readout_ui()

        self._re_last_results_snapshot = None

        self._re_rmse_qwot_alpha_ref = None

        self._re_last_live_alpha_qwot = None

        self._re_loading_workbook = False

        self._use_exact_ep = False

        self._re_loaded_exact_ep = None

        self.ep_current = None
        self._best_eval_result = None
        self._best_eval_rmse = float("inf")
        self._workflow_best_rmse = float("inf")
        self._stack_info_best_ep = None
        self._stack_info_best_rmse = None
        if hasattr(self, "mse_data"):
            self.mse_data = {"iterations": [], "errors": []}

        self._sync_display_re_results_btn_state()

    def _clear_re_excel_readout_ui(self) -> None:
        """Placeholders + unlock lambda₀ and back face (outside RE session)."""

        if not hasattr(self, "_re_readout_lambda_lbl"):
            return

        self._re_readout_lambda_lbl.setText(
            f'<span style="color:{CertusTheme.TEXT_SUB};">'
            "<b>Reference lambda₀</b> :  (load an RE file; value read from the <b>design</b> sheet)"
            "</span>"
        )

        self._re_readout_backside_lbl.setText(
            f'<span style="color:{CertusTheme.TEXT_SUB};">'
            "<b>Substrate back face</b> :  (load an RE file; "
            "inferred from measurement column <b>headers</b>)"
            "</span>"
        )

        self._re_backside_summary_html = ""

        if hasattr(self, "re_fit_lambda_min_spin") and hasattr(self, "re_fit_lambda_max_spin"):
            _dlo, _dhi = self._re_default_target_lmin_lmax_nm()

            self.re_fit_lambda_min_spin.blockSignals(True)

            self.re_fit_lambda_max_spin.blockSignals(True)

            try:
                self.re_fit_lambda_min_spin.setValue(float(_dlo))

                self.re_fit_lambda_max_spin.setValue(float(_dhi))

            finally:
                self.re_fit_lambda_min_spin.blockSignals(False)

                self.re_fit_lambda_max_spin.blockSignals(False)

        if hasattr(self, "l0_spin"):
            self.l0_spin.setReadOnly(False)

            self.l0_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)

        if hasattr(self, "back_check"):
            self.back_check.setEnabled(True)

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for RE."""

        substrate_type = ""

        substrate_index = "Load an RE file"

        if getattr(self, "_re_loaded", False):
            substrate_type = "Tabulaire (Excel RE)"

            sub = getattr(self, "_re_tabular_Sub", None)

            if sub is not None:
                l0 = float(self._stack_info_l0_nm())

                nk = sub.get_nk(np.array([l0], dtype=np.float64))

                substrate_index = f"n@lambda₀={float(nk[0].real):.3f}"

            else:
                substrate_index = "substrate (indices.xlsx)"

        return substrate_type, substrate_index

    def _update_busy_ui(self, busy_now: bool):
        """Updates RE-specific button states."""

        re_ok = getattr(self, "_re_loaded", False)

        self.eval_btn.setEnabled(not busy_now and re_ok)

        self.load_re_btn.setEnabled(not busy_now)

        self.launch_re_btn.setEnabled(not busy_now and re_ok)

        self.stop_btn.setEnabled(busy_now)

    def _update_zoom_label(self, factor: float) -> None:
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"Zoom {int(round(factor * 100))}%")

    def _apply_ui_zoom(self, factor: float) -> None:
        factor = max(0.85, min(1.30, float(factor)))
        self._zoom_factor = factor
        base_pt = getattr(CertusTheme, "FONT_SIZE_BASE", 10)
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont("Segoe UI", max(9, round(base_pt * factor))))
        self._update_zoom_label(factor)
        try:
            show_toast(self, f"Zoom {int(round(factor * 100))}%", "info", duration_ms=1200)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            pass

    def _re_speed_mode(self) -> str:
        """slow | medium | fast  default medium if speed UI is not built yet."""

        if not getattr(self, "re_speed_medium_radio", None):
            return "medium"

        if self.re_speed_slow_radio.isChecked():
            return "slow"

        if self.re_speed_fast_radio.isChecked():
            return "fast"

        return "medium"

    def _re_speed_preset(self) -> dict[str, Any]:

        return dict(RE_SPEED_PRESETS.get(self._re_speed_mode(), RE_SPEED_PRESETS["medium"]))

    def _re_gui_qwot_penalty_weight(self) -> float:
        """QWOT (phase 2b reference) for RMSE display / logs  follows speed preset."""

        if not bool(self.cfg.get("re_enable_qwot_penalty", True)):
            return 0.0

        return re_qwot_penalty_weight_from_preset(
            speed_preset=self._re_speed_preset(),
            default=float(RE_GUI_DEFAULT_RE_QWOT_ALPHA),
        )

    def _re_envelope_scale_from_gui(self) -> float:
        """DeltaRe envelope factor (phase 2): read from speed preset."""

        try:
            return float(self._re_speed_preset()["re_envelope_scale"])

        except (KeyError, TypeError, ValueError):
            return 1.0

    def _sync_display_re_results_btn_state(self) -> None:

        btn = getattr(self, "display_re_results_btn", None)

        if btn is None:
            return

        snap = getattr(self, "_re_last_results_snapshot", None)

        btn.setEnabled(bool(snap and snap.get("results")))

    def _re_current_sub_cauchy_theta(self, dH_st, dL_st) -> tuple[float, float, float] | None:

        if dH_st is not None and dL_st is not None and len(np.asarray(dH_st).ravel()) == int(RE_SPLINE_N_KNOTS):
            a0, a1, a2 = (
                getattr(self, "_re_sub_cauchy_a0", None),
                getattr(self, "_re_sub_cauchy_a1", None),
                getattr(self, "_re_sub_cauchy_a2", None),
            )

            if None not in (a0, a1, a2):
                return (float(a0), float(a1), float(a2))

        return None

    def _show_substrate_info_window(self):
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

        self.substrate_info_window.setWindowTitle(" Stack information")

        self.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("Substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.substrate_type_label = QLabel("N/A")

        self.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.substrate_type_label, 0, 1)

        info_layout.addWidget(self.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Stack structure (QWOT)")

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

    def _re_apply_gui_prefs_from_dict(self, d: dict[str, Any]) -> None:
        """Restore RE speed preset and toggle prefs from a JSON ``re_gui`` block."""
        if not d:
            return
        try:
            if hasattr(self, "re_speed_slow_radio") and "re_speed_mode" in d:
                mode = str(d.get("re_speed_mode", "medium")).strip().lower()
                if mode == "slow":
                    self.re_speed_slow_radio.setChecked(True)
                elif mode == "fast":
                    self.re_speed_fast_radio.setChecked(True)
                else:
                    self.re_speed_medium_radio.setChecked(True)
            if hasattr(self, "sub_refine_check"):
                if "re_phase2b_substrate_cauchy" in d:
                    self.sub_refine_check.setChecked(bool(d["re_phase2b_substrate_cauchy"]))
                if "re_refine_h" in d:
                    self.h_refine_check.setChecked(bool(d["re_refine_h"]))
                if "re_refine_l" in d:
                    self.l_refine_check.setChecked(bool(d["re_refine_l"]))
            if hasattr(self, "re_qwot_penalty_chk") and "re_enable_qwot_penalty" in d:
                self.re_qwot_penalty_chk.setChecked(bool(d["re_enable_qwot_penalty"]))
        except (KeyError, ValueError, TypeError) as e:
            logging.warning("RE GUI prefs restore skipped: %s", e)

    def closeEvent(self, event):
        """

        Handles application closure with proper cleanup of all workers.

        Ensures all QThread workers are properly stopped to avoid

        "QThread: Destroyed while thread is still running" warnings.

        """

        # Ensure all workers are stopped to avoid "QThread: Destroyed while thread is still running"

        workers = [
            getattr(self, "_re_worker", None),
            getattr(self, "eval_worker", None),
            getattr(self, "warmup_worker", None),
        ]

        for worker in workers:
            if worker and worker.isRunning():
                try:
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

                    if hasattr(self, "logger") and self.logger:
                        self.logger.debug(f"Error stopping worker {type(worker).__name__}: {e}")

        # Call parent cleanup (stops base class workers)

        super().closeEvent(event)

    def _re_current_fit_lambda_bounds_nm(self) -> tuple[float, float]:
        """Current GUI lambda bounds used to keep/discard RE measurement points."""

        lo = float(self.re_fit_lambda_min_spin.value() if hasattr(self, "re_fit_lambda_min_spin") else 200.0)

        hi = float(self.re_fit_lambda_max_spin.value() if hasattr(self, "re_fit_lambda_max_spin") else 20000.0)

        if hi < lo:
            lo, hi = hi, lo

        return lo, hi

    def _re_filter_targets_by_fit_window(self, tgts: list[ObliqueTarget]) -> list[ObliqueTarget]:
        """Keep only targets whose center wavelength is inside GUI lambda bounds."""

        if not tgts:
            return []

        lo, hi = self._re_current_fit_lambda_bounds_nm()

        out: list[ObliqueTarget] = []

        for t in tgts:
            wl_c = 0.5 * (float(t.lmin) + float(t.lmax))

            if lo <= wl_c <= hi:
                out.append(t)

        return out

    def _re_default_target_lmin_lmax_nm(self) -> tuple[float, float]:
        """Default lambda min/max for spectral targets, centered on lambda0 (no hard-coded fixed lambda pairs)."""

        l0 = float(self._stack_info_l0_nm())

        return (max(200.0, l0 - 100.0), min(20000.0, l0 + 200.0))

    def _re_fallback_plot_wavelengths_nm(self, n: int = 200) -> np.ndarray:
        """Lambda grid for RE plots when no target is active; span derived from lambda0."""

        lr = float(self._stack_info_l0_nm())

        lo = max(200.0, lr - 100.0)

        hi = min(20000.0, max(lr + 200.0, lr * 5.0))

        return np.linspace(lo, hi, int(n), dtype=np.float64)

    def _remove_re_skeletons(self):
        if hasattr(self, "spectrum_plot") and self.spectrum_plot is not None:
            remove_skeleton_loader(self.spectrum_plot)
        if hasattr(self, "profile_plot") and self.profile_plot is not None:
            remove_skeleton_loader(self.profile_plot)
        if hasattr(self, "nk_plot") and self.nk_plot is not None:
            remove_skeleton_loader(self.nk_plot)

    def _trigger_post_undo_action(self):
        """RE specific post-undo action."""

        self._schedule_eval(True)
