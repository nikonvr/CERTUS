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
from certus.utils.certus_re_config import RE_THICKNESS_SEARCH_RADIUS_PCT
from certus.utils.certus_re_config import RE_SUB_CAUCHY_TUBE_DELTA
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


class CertusREWorkersMixin:
    """CertusREWorkersMixin for CERTUS_RE."""

    def _on_schedule_eval_signal(self, *_args) -> None:

        self._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self._schedule_eval(True)

    def run_eval(self):
        """

        Runs spectral evaluation of the current design.

        This method performs complete spectral evaluation including:

        - JIT compilation warmup check

        - Material and stack validation

        - Target configuration setup

        - Worker thread initialization and execution

        - Result processing and visualization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs evaluation progress and timing

            - Handles both normal and oblique modes

            - Emits progress signals during execution

            - Updates UI components with results

        """

        _eval_start = time.time()

        if not spectrum_eval_run_preamble(self, self.run_eval):
            return

        cfg = spectrum_eval_build_worker_cfg(self, "re")

        if cfg is None:
            return

        spectrum_eval_start_worker(self, cfg, _eval_start)

    def _on_eval_finished(self, data: Dict, generation_id: int | None = None):
        """

        Callback after spectral evaluation completion.

        This method processes evaluation results including:

        - Result data storage and validation

        - Visualization data processing

        - Plot updates and UI refresh

        - Performance timing and logging

        Args:

            self: CertusDesign instance

            data: Evaluation result dictionary with spectral data

        Returns:

            None

        Notes:

            - Logs evaluation completion and timing

            - Handles both normal and oblique modes

            - Updates UI components with results

            - Stores results for subsequent operations

        """

        _finish_start = time.time()

        data_for_display = spectrum_eval_on_finished_prepare_display(self, data, generation_id)

        if data_for_display is None:
            return

        self.last_result = data_for_display

        self.accumulated_evals += 1

        res_vis = data_for_display["vis"]

        res_optim = data_for_display["optimization"]

        oblique_mode = data_for_display.get("oblique_mode", False)

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        plot_targets = self._get_plot_targets("spectrum", self.spectrum_plot)

        spectrum_eval_plot_curves(
            self,
            data_for_display=data_for_display,
            plot_targets=plot_targets,
            res_vis=res_vis,
            res_optim=res_optim,
            oblique_mode=oblique_mode,
        )

        rmse = data_for_display.get("rmse")

        if (rmse is None or not np.isfinite(rmse)) and oblique_mode and getattr(self, "_re_loaded", False):
            rmse = self._compute_re_rmse(
                float(getattr(self, "_re_opt_a_pct", 0.0)),
                float(getattr(self, "_re_opt_b_pct", 0.0)),
                float(getattr(self, "_re_opt_f_pct", 0.0)),
            )

            data_for_display["rmse"] = rmse

        if self._is_valid_rmse_value(data_for_display.get("rmse")):
            self._store_best_eval_snapshot(data_for_display)

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | {src_name} | RMSE grid: {n_total} lambda"

            else:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | RMSE grid: {n_total} lambda"

        except NUMERICAL_FAULT_EXCEPTIONS :
            title = f"Spectrum ({self.front_table.rowCount()} layers) | RMSE grid: {n_total} lambda"

        if rmse is not None and np.isfinite(rmse) and rmse >= 0.0:
            title += f" - RMSE: {rmse:.6f}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self, res_vis=res_vis, oblique_mode=oblique_mode)

        self._plot_profile(
            data_for_display["ep"],
            self._get_front_stack(),
        )

        self._plot_nk()

        logging.info(f"[EVAL] _on_eval_finished complete in {(time.time() - _finish_start) * 1000:.1f}ms")

        self._update_status_bar_stats()

        _dt_ms = (time.time() - _finish_start) * 1000.0

        _tags: list[str] = []

        if oblique_mode:
            _tags.append("oblique")

        if self.back_check.isChecked():
            _tags.append("back face")

        _tag_s = f" ({', '.join(_tags)})" if _tags else ""

        if rmse is not None and np.isfinite(rmse) and rmse >= 0.0:
            self.log(
                f"Evaluation OK{_tag_s}  {_dt_ms:.0f} ms, RMSE grid {n_total} lambda, RMSE={rmse:.6f}",
                "SUCCESS",
            )

        else:
            self.log(
                f"Evaluation OK{_tag_s}  {_dt_ms:.0f} ms, RMSE grid {n_total} lambda.",
                "SUCCESS",
            )

        self._set_busy(False)

        logging.info("[EVAL] === Evaluation cycle complete, UI ready ===")

    @safe_ui_action
    def launch_re(self):
        """Lance REWorker : P1 epaisseurs, P2 splines DeltaRe (+substrate), P3 shakes, P4 faisceau (N paliers ap)."""

        if not self._re_loaded:
            self.log("No RE file loaded.  Use 'Load RE File' first.", "WARNING")

            return

        cfg = self.build_re_worker_cfg()

        if cfg is None:
            self.log(
                "No RE measurement targets found or initial thickness unavailable.",
                "ERROR",
            )

            return

        self._re_mode_active = True

        self._workflow_best_rmse = float("inf")

        self._re_last_live_alpha_qwot = None

        self._re_clear_re_nk_preview()

        self._set_busy(True)

        _Ksp = RE_SPLINE_N_KNOTS

        _es = float(cfg["re_envelope_scale"])

        _es_lbl = f"DeltaRe envelope ×{_es:g}"

        _hl = float(cfg.get("re_hl_delta_re_reg_sqrt_w", RE_HL_DELTA_RE_REG_SQRT_W))

        _dzre = float(cfg.get("re_hl_delta_re_deadzone_abs", RE_RE_DEADZONE_DELTA_RE_ABS))

        _dzqw = float(cfg.get("re_qwot_deadzone_abs", RE_RE_DEADZONE_QWOT_ABS))

        _qw_on = bool(cfg.get("re_enable_qwot_penalty", True))

        _hl_lbl = f"DeltaRe H/L penalty √(w)={_hl:g} (outside +/-{_dzre:g}); " if _hl > 0.0 else ""

        _sub_on = bool(cfg.get("re_phase2b_substrate_cauchy", True))

        _sub_lbl = (
            f"+ Cauchy substrate (a0,a1,a2), tube +/-{RE_SUB_CAUCHY_TUBE_DELTA:g} vs n_tab(lambda)"
            if _sub_on
            else "+ fixed tabulated substrate indices (no Cauchy)"
        )

        _rad_pct = float(cfg.get("radius", RE_THICKNESS_SEARCH_RADIUS_PCT))

        _nt = len(cfg.get("oblique_tgts") or [])

        _nc = len(cfg.get("stack") or [])

        _wl0 = float(cfg.get("wls_min", 0.0))

        _wl1 = float(cfg.get("wls_max", 0.0))

        self.log(
            f"RE: P1P2  (1) TRF Deltaln(lambda) trap +/-{_rad_pct:g}% thicknesses only, tabulated indices; "
            f"(2) TRF joint: thicknesses + {2 * _Ksp + 1} param. (DeltaRe splines H/L + lambda₂) {_sub_lbl}; "
            f"{_es_lbl}; dead bands |DeltaRe|<={_dzre:g}, |DeltaQ|<={_dzqw:g}; "
            f"{_hl_lbl}"
            f"{_nt} targets, {_nc} layers, lambda [{_wl0:.0f}, {_wl1:.0f}] nm; "
            f"P3 shakes + P4 beam ap({int(RE_P4_BEAM_N_KNOTS)} lambda nodes, steps); "
            f"facade RMSE display={'√(sp2+alpha·QWOT2) (alpha per phase)' if _qw_on else 'RMSE_sp only'}; "
            f"TRF cost = TRF_RMS(res) over all vector r (iter logs).",
            "INFO",
        )

        _mode = self._re_speed_mode()

        _mode_lbl = {"slow": "Slow", "medium": "Medium", "fast": "Fast"}.get(_mode, _mode)

        _p1m = int(cfg.get("re_phase1_multistarts", 1))

        _tk = int(cfg.get("re_phase2_top_k", 1))

        _sh = int(cfg.get("re_phase3_shake_rounds", 0))

        _i1 = int(cfg.get("re_phase1_maxiter", 0))

        _i2a = int(cfg.get("re_phase2_spline_prefit_maxiter", 0))

        _i2b = int(cfg.get("re_phase2b_maxiter", 0))



        self.log(
            f"RE preset  {_mode_lbl}  : multistarts={_p1m}, top-K={_tk}, shakes={_sh}, "
            f"maxiter P1/2a/2b={_i1}/{_i2a}/{_i2b}.",
            "INFO",
        )

        self.log(
            (
                f"RE facade (logs / bar): RMSE_facade = √(RMSE_sp2 + alpha·RMSE_QWOT2), "
                f"QWOT penalty={'ON' if _qw_on else 'OFF'} (alpha phase varies; see worker). "
                f"Real TRF cost: TRF_RMS(r) in iteration logs."
                if _qw_on
                else "RE facade: QWOT penalty=OFF  RMSE_facade = RMSE_sp; TRF cost = TRF_RMS(r) (logs)."
            ),
            "INFO",
        )

        _fmin = float(cfg.get("wls_min", 0.0))

        _fmax = float(cfg.get("wls_max", 0.0))

        _ref_h = bool(cfg.get("re_refine_h", False))

        _ref_l = bool(cfg.get("re_refine_l", False))

        _ref_sub = bool(cfg.get("re_phase2b_substrate_cauchy", False))

        _p4_scan = int(cfg.get("re_phase4_aperture_scan_points", RE_PHASE4_APERTURE_SCAN_POINTS))

        _p4_nfev = int(cfg.get("re_phase4_trf_max_nfev", RE_PHASE4_TRF_MAX_NFEV))

        _p4_b = cfg.get("re_phase4_ap_bounds_deg", RE_P4_BEAM_AP_BOUNDS_DEG)

        _qw_on_ui = bool(cfg.get("re_enable_qwot_penalty", True))

        _fit_min = self.re_fit_lambda_min_spin.value() if hasattr(self, "re_fit_lambda_min_spin") else _fmin
        _fit_max = self.re_fit_lambda_max_spin.value() if hasattr(self, "re_fit_lambda_max_spin") else _fmax

        self.log(
            "RE facade  selection UI: "
            f"mode={_mode_lbl}, fit lambda=[{_fit_min:.0f},{_fit_max:.0f}]nm (display=[{_fmin:.0f},{_fmax:.0f}]nm), "
            f"refine(H/L/sub)={_ref_h}/{_ref_l}/{_ref_sub}, "
            f"backside={'on' if bool(cfg.get('back', False)) else 'off'}, "
            f"QWOT_penalty={'on' if _qw_on_ui else 'off'}, "
            f"P4 scan_pts={_p4_scan}, P4 trf_nfev={_p4_nfev}, P4 ap_bounds={_p4_b}.",
            "INFO",
        )

        if hasattr(self, "progress_widget"):
            self.progress_widget.start()

        self.log("[DBG-UI] Creating REWorker...", "INFO")
        self._re_worker = REWorker(cfg)
        self.log("[DBG-UI] Connecting REWorker signals...", "INFO")

        self._re_worker.signals.error.connect(self._on_error)

        self._re_worker.signals.finished.connect(self._on_re_done)

        self._re_worker.signals.progress.connect(self._on_re_worker_progress)

        self._re_worker.signals.result.connect(self._on_re_worker_result)

        self.log("[DBG-UI] Calling worker.start()...", "INFO")
        self._re_worker.start()
        self.log("[DBG-UI] worker.start() returned — thread launched", "INFO")

    def stop_optim(self):
        """Stop spectral evaluation or the RE worker."""

        if not confirm_stop_with_timeout(self):
            return

        self._remove_re_skeletons()

        self._workflow_stopped = True

        self.log("Stop requested...", "WARNING")

        rw = getattr(self, "_re_worker", None)

        re_was_running = rw is not None and rw.isRunning()

        re_joined_ok = False

        if re_was_running:
            if hasattr(rw, "request_stop"):
                rw.request_stop()

            rw.requestInterruption()

            # Wait for cooperative finish: ``finished`` -> ``_on_re_done`` (best TRF known).

            re_joined_ok = rw.wait(300000)

            if not re_joined_ok:
                logging.critical(
                    "REWorker did not finish within timeout - skipping terminate() to avoid unsafe thread kill."
                )

                self.log("REWorker: stop timeout - skipping terminate() (see log).", "ERROR")

            self._re_worker = None

        if not re_joined_ok and getattr(self, "_re_mode_active", False):
            self._re_mode_active = False

            self._re_clear_re_nk_preview()

            self._plot_nk()

            if hasattr(self, "launch_re_btn"):
                self.launch_re_btn.setEnabled(True)

        if hasattr(self, "progress_widget") and (not re_was_running or not re_joined_ok):
            try:
                self.progress_widget.stop("Cancelled")

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

        if self.eval_worker and self.eval_worker.isRunning():
            self.eval_worker.requestInterruption()

            self.eval_worker.wait(2000)

        self._force_idle()

        if not re_was_running or not re_joined_ok:
            self.log("Calculation stopped.", "WARNING")

    def _on_re_worker_progress(self, pct: int, msg: str):
        """Synchronizes REWorker progress -> LOGS panel + progress widget."""

        if not msg:
            return

        self.log(msg, "INFO")

        if getattr(self, "_re_mode_active", False):
            _rp = _parse_re_rmse_combined_from_progress_message(msg)

            if _rp is not None:
                self._apply_re_workflow_rmse_if_better(_rp)

        pw = getattr(self, "progress_widget", None)

        if pw is None:
            return

        try:
            pw.progress_bar.setValue(max(0, min(100, int(pct))))

            short = msg if len(msg) <= 160 else (msg[:157] + "...")

            pw.info_label.setText(short)

        except NUMERICAL_FAULT_EXCEPTIONS :
            pass

    def _on_re_worker_result(self, data: object) -> None:
        """Update  Best RMSE  during RE (live emissions, previously not wired)."""

        if not getattr(self, "_re_mode_active", False):
            return

        if not isinstance(data, dict):
            return

        if data.get("type") != "intermediate":
            return

        al = data.get("alpha_qwot")
        if al is not None:
            try:
                al_f = float(al)
            except (TypeError, ValueError):
                al_f = float("nan")

            if np.isfinite(al_f):
                prev = getattr(self, "_re_last_live_alpha_qwot", None)
                if prev is not None and abs(al_f - float(prev)) > 1e-12:
                    self._workflow_best_rmse = float("inf")
                self._re_last_live_alpha_qwot = al_f

        rmse = data.get("rmse")
        if not self._is_valid_rmse_value(rmse):
            return

        self._apply_re_workflow_rmse_if_better(float(rmse))

        if "ep" in data:
            self.ep_current = data["ep"]
            if hasattr(self, "_update_index_profile_plot"):
                self._update_index_profile_plot()

        spectra_display = data.get("spectra_display")
        if spectra_display is not None:
            res_vis = {"l": data.get("wls", []), "Ts": data.get("Ts", [])}
            data_for_display = {"spectra_vis": spectra_display}
            plot_targets = self._get_plot_targets("spectrum", self.spectrum_plot)
            oblique_mode = data.get("oblique_mode", False)
            spectrum_eval_plot_curves(
                self,
                data_for_display=data_for_display,
                plot_targets=plot_targets,
                res_vis=res_vis,
                res_optim={"l": [], "Ts": []},
                oblique_mode=oblique_mode,
            )

        if "re_nk_preview_dH" in data:
            self._re_nk_preview_dH = data.get("re_nk_preview_dH")
            self._re_nk_preview_dL = data.get("re_nk_preview_dL")
            self._re_nk_preview_lam2 = data.get("re_nk_preview_lam2")
            self._re_nk_preview_sub012 = data.get("re_nk_preview_sub012")
            self._plot_nk()

    def _on_re_done(self, data: Dict):
        """Handle REWorker completion; show results dialog."""
        self._remove_re_skeletons()
        self._re_mode_active = False

        self._re_clear_re_nk_preview()

        self._set_busy(False)

        if not data.get("ok"):
            self.log("RE optimization failed.", "ERROR")

            if hasattr(self, "progress_widget"):
                self.progress_widget.stop("Error: RE failed")

            self._plot_nk()

            return

        if data.get("re_stopped_by_user"):
            self.log(
                "RE: stop requested; intermediate best result applied (same flow as normal finish).",
                "INFO",
            )

        results = data.get("results", [])

        _re_sort_results_best_for_table_and_apply(results)

        ep0 = np.asarray(data.get("ep0", []))

        if not results:
            self.log("RE: no results.", "WARNING")

            if hasattr(self, "progress_widget"):
                self.progress_widget.stop("Error: No result")

            self._plot_nk()

            return

        _a2b_done = data.get("re_qwot_alpha_phase2b")

        if _a2b_done is not None:
            try:
                self._re_rmse_qwot_alpha_ref = float(_a2b_done)

            except (TypeError, ValueError):
                self._re_rmse_qwot_alpha_ref = None

        else:
            self._re_rmse_qwot_alpha_ref = None

        ri = data.get("re_rmse_initial")

        r1 = data.get("re_rmse_phase1")

        rf = data.get("re_rmse_final")

        if results:
            rf = float(results[0].get("rmse_combined", results[0]["rmse"]))

        if ri is not None and r1 is not None and rf is not None and all(np.isfinite(float(x)) for x in (ri, r1, rf)):
            self.log(
                f"RE: RMSE milestones  initial={float(ri):.6f} | "
                f"phase 1 (thicknesses only)={float(r1):.6f} | worker end={float(rf):.6f}",
                "INFO",
            )

        _rk = results[0].get("re_ranking_score") if results else None

        _qwr = results[0].get("re_rmse_qwot_raw") if results else None

        _ar_ref = results[0].get("re_ranking_alpha_ref") if results else None

        if (
            _rk is not None
            and _qwr is not None
            and _ar_ref is not None
            and all(np.isfinite(float(x)) for x in (_rk, _qwr, _ar_ref))
        ):
            self.log(
                f"RE: RMSE_ranking (sqrt(sp2+alpha_ref·QWOT_raw2), inter-runs, alpha_ref={float(_ar_ref):g}) "
                f"= {float(_rk):.6f} | RMSE_sp={float(results[0]['rmse']):.6f} QWOT_raw={float(_qwr):.6f}",
                "INFO",
            )

        # Log summary

        for r in results:
            drift_sfx = re_drift_result_log_suffix(r)

            np1 = r.get("nfev_phase1")

            p1s = f" (phase1 nfev={np1})" if np1 is not None else ""

            _p2a = int(r.get("nfev_phase2_prefit", 0) or 0)

            p2as = f" phase2a_prefit nfev={_p2a}" if _p2a else ""

            _rcomb = float(r.get("rmse_combined", r["rmse"]))

            self.log(
                f"RE {r['label']:>18s}: RMSE_sp={r['rmse']:.6f} | RMSE_facade={_rcomb:.6f}{drift_sfx}  "
                f"({r['nfev']} phase2b evals{p1s}{p2as}, "
                f"{'converged' if r['success'] else 'max iter'})",
                "INFO",
            )

        # Apply best solution to front table

        best = results[0]

        ep_best = np.asarray(best["ep"]).flatten()

        self._workflow_best_rmse = best.get("rmse_combined", best["rmse"])

        _p1 = int(best.get("nfev_phase1", 0) or 0)

        _p2a = int(best.get("nfev_phase2_prefit", 0) or 0)

        _p2b = int(best.get("nfev", 0) or 0)

        self._re_nfev_cumulative += _p1 + _p2a + _p2b

        self._update_status_bar_stats()

        self._update_qwot_from_ep(ep_best)

        self._update_thickness_display()

        self.ep_current = ep_best.copy()

        self._use_exact_ep = True

        # Do not call run_eval immediately: it would set the UI to "Computing..."

        # and the (non-modal) results window often ended up behind other windows.

        _ak_b = best.get("re_p4_beam_ap_knots_deg")

        _anm_b = best.get("re_p4_beam_ap_knots_nm")

        if _ak_b is not None and _anm_b is not None:
            _aka = np.asarray(_ak_b, dtype=np.float64).ravel()

            _anma = np.asarray(_anm_b, dtype=np.float64).ravel()

            _np4 = int(min(_aka.size, _anma.size))

            if _np4 >= 2:
                self._re_p4_display_beam_active = True

                self._re_p4_display_ap_knots_deg = _aka[:_np4].copy()

                self._re_p4_display_ap_knots_nm = _anma[:_np4].copy()

            else:
                self._re_p4_display_beam_active = False

                self._re_p4_display_ap_knots_deg = None

                self._re_p4_display_ap_knots_nm = None

        else:
            self._re_p4_display_beam_active = False

            self._re_p4_display_ap_knots_deg = None

            self._re_p4_display_ap_knots_nm = None

        self._re_opt_a_pct = float(best.get("a", 0.0))

        self._re_opt_b_pct = float(best.get("b", 0.0))

        self._re_opt_f_pct = float(best.get("f", 0.0))

        if best.get("re_dH_knots") is not None and best.get("re_dL_knots") is not None:
            self._re_spline_dH = np.asarray(best["re_dH_knots"], dtype=np.float64).ravel()

            self._re_spline_dL = np.asarray(best["re_dL_knots"], dtype=np.float64).ravel()

            self._re_opt_a_pct = 0.0

            self._re_opt_b_pct = 0.0

            self._re_opt_f_pct = 0.0

            _kw_best = best.get("re_knots_nm")

            if _kw_best is not None and len(_kw_best) > 1:
                self._re_spline_lam2_nm = float(np.asarray(_kw_best, dtype=float)[1])

            else:
                _lv = best.get("re_spline_lam_node2_nm")

                self._re_spline_lam2_nm = float(_lv) if _lv is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

            _knots_log = np.asarray(
                _kw_best if _kw_best is not None else re_knots_wavelengths(self._re_spline_lam2_nm),
                dtype=np.float64,
            )

            _sfx = format_re_spline_knots_log(_knots_log, self._re_spline_dH, self._re_spline_dL)

            if best.get("re_sub_cauchy_a0") is not None:
                self._re_sub_cauchy_a0 = float(best["re_sub_cauchy_a0"])

                self._re_sub_cauchy_a1 = float(best["re_sub_cauchy_a1"])

                self._re_sub_cauchy_a2 = float(best["re_sub_cauchy_a2"])

                _sfx += (
                    f" | sub_Cauchy a0,a1,a2="
                    f"{self._re_sub_cauchy_a0:.5f},{self._re_sub_cauchy_a1:.5f},{self._re_sub_cauchy_a2:.5f}"
                )

            else:
                self._re_sub_cauchy_a0 = None

                self._re_sub_cauchy_a1 = None

                self._re_sub_cauchy_a2 = None

        else:
            self._re_spline_dH = None

            self._re_spline_dL = None

            self._re_spline_lam2_nm = None

            self._re_sub_cauchy_a0 = None

            self._re_sub_cauchy_a1 = None

            self._re_sub_cauchy_a2 = None

            a_best = float(best.get("a", 0.0))

            b_best = float(best.get("b", 0.0))

            f_best = float(best.get("f", 0.0))

            _sfx = format_re_drift_log_triplet_pct(a_best, b_best, f_best)

        _best_c = float(best.get("rmse_combined", best["rmse"]))

        self.log(
            f"RE: Best solution '{best['label']}' applied  "
            f"RMSE_sp={best['rmse']:.6f} | RMSE_facade={_best_c:.6f} ; {_sfx}",
            "SUCCESS",
        )

        self._plot_nk()

        try:
            self._re_last_results_snapshot = {
                "results": copy.deepcopy(results),
                "ep0": np.asarray(ep0, dtype=np.float64).copy(),
                "re_rmse_initial": ri,
                "re_rmse_phase1": r1,
                "re_rmse_final": rf,
                "re_qwot_alpha_phase2b": data.get("re_qwot_alpha_phase2b"),
                "initial_stack": copy.deepcopy(getattr(self, "_re_initial_stack", [])),
            }

            self._sync_display_re_results_btn_state()

            self._show_re_results_window(
                results,
                ep0,
                re_rmse_initial=data.get("re_rmse_initial"),
                re_rmse_phase1=data.get("re_rmse_phase1"),
                re_rmse_final=rf,
            )

        except NUMERICAL_FAULT_EXCEPTIONS :
            self.log(
                "RE: the results window could not be displayed; detail:\n" + traceback.format_exc(),
                "ERROR",
            )

        self._re_log_rmse_config_recap(
            re_rmse_initial=ri,
            re_rmse_phase1=r1,
            re_rmse_final=rf,
            phase2_splines_done=best.get("re_dH_knots") is not None,
        )

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Cancelled" if data.get("re_stopped_by_user") else "Done")

        self._schedule_eval(True)

        def _show_final_re_title():

            final_rmse = self._compute_re_rmse(0.0, 0.0, 0.0)

            if final_rmse is not None:
                self._update_re_spectrum_title(
                    final_rmse,
                    suffix=(f"| {_sfx}"),
                )

        QTimer.singleShot(400, _show_final_re_title)

    def _compute_re_rmse(self, a_pct=0.0, b_pct=0.0, f_pct=0.0):
        """RMSE of current design vs RE targets (same lambda grouping / backside as REWorker)."""
        try:
            if not getattr(self, "_re_loaded", False):
                return None

            stack = self._get_front_stack()
            mats = self._get_materials()
            ep = getattr(self, "_re_loaded_exact_ep", None)
            if ep is None:
                ep = self.ep_current if getattr(self, "_use_exact_ep", False) else init_thickness(stack, self.l0_spin.value(), mats)
            ep = np.asarray(ep, dtype=np.float64)
            tgts = self._get_oblique_tgts()
            if not tgts:
                return None
            tgts = [t for t in tgts if t.on]
            if not tgts:
                return None

            wls = np.array(sorted({(t.lmin + t.lmax) / 2.0 for t in tgts}), dtype=np.float64)
            if wls.size == 0:
                return None

            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
            n_layers_nominal = np.array([mats_nk[l.mat] for l in stack], dtype=np.complex128)
            n_sub = np.ascontiguousarray(mats_nk["Substrate"])
            lambda_ref = float(self.l0_spin.value())
            is_H_arr = np.array([l.mat == "H" for l in stack], dtype=bool)
            is_L_arr = np.array([l.mat == "L" for l in stack], dtype=bool)
            dH_st = getattr(self, "_re_spline_dH", None)
            dL_st = getattr(self, "_re_spline_dL", None)
            lam2_rm = getattr(self, "_re_spline_lam2_nm", None)

            n_layers_nominal, n_sub = re_apply_re_index_model(
                n_layers_nominal,
                n_sub,
                is_H=is_H_arr,
                is_L=is_L_arr,
                wls_nm=wls,
                lambda_ref_nm=lambda_ref,
                a_pct=float(a_pct),
                b_pct=float(b_pct),
                f_pct=float(f_pct),
                spline_dH=dH_st,
                spline_dL=dL_st,
                spline_lam_node2_nm=lam2_rm,
                re_envelope_scale=self._re_envelope_scale_from_gui(),
                sub_cauchy_theta=self._re_current_sub_cauchy_theta(dH_st, dL_st),
            )

            n_layers_T = np.ascontiguousarray(n_layers_nominal.T)
            r_sp = float(_re_rmse_oblique_weighted(ep, n_layers_T, n_sub, wls, tgts, **self._re_p4_display_beam_kwargs()))
            ep0_rm = getattr(self, "_re_initial_ep", None)
            if ep0_rm is None or len(np.asarray(ep0_rm).ravel()) != len(ep):
                ep0_rm = init_thickness(stack, self.l0_spin.value(), mats)
            ep0_rm = np.asarray(ep0_rm, dtype=np.float64).ravel()
            alpha_q = self._re_rmse_qwot_alpha_for_display()
            r_qw = _re_qwot_rmse_abs_delta_at_l0(
                ep,
                ep0_rm,
                stack,
                mats,
                lambda_ref,
                is_H_arr,
                is_L_arr,
                spline_dH=dH_st,
                spline_dL=dL_st,
                spline_lam2_nm=lam2_rm,
                re_envelope_scale=self._re_envelope_scale_from_gui(),
                deadzone_abs=RE_RE_DEADZONE_QWOT_ABS,
            )
            return _re_rmse_combined_spectral_qwot(r_sp, float(r_qw), alpha_q)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.warning(f"_compute_re_rmse error: {e}")
            return None

    def build_re_worker_cfg(self, overrides: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Build the `cfg` dict for :class:`REWorker` (same content as ``launch_re``).

        Returns ``None`` if the RE workbook is not loaded, there are no targets, or no initial ep0.

        *overrides* keys replace / extend cfg (shallow merge).

        """

        if not getattr(self, "_re_loaded", False):
            return None

        stack = self._get_front_stack()

        mats = self._get_materials()

        try:
            self._re_initial_ep = init_thickness(stack, self.l0_spin.value(), mats).copy()

        except NUMERICAL_FAULT_EXCEPTIONS :
            self._re_initial_ep = None

        self._re_initial_stack = list(stack)

        self._re_sub_cauchy_a0 = None

        self._re_sub_cauchy_a1 = None

        self._re_sub_cauchy_a2 = None

        if self._re_initial_ep is None:
            return None

        re_tgts = self._get_oblique_tgts()

        if not re_tgts:
            return None

        wls_min = self._calculate_wls_min_with_margin(re_tgts)

        wls_max = self._calculate_wls_max_with_margin(re_tgts)

        lambda_ref = float(self.l0_spin.value())

        sp = self._re_speed_preset()

        cfg: dict[str, Any] = {
            "mats": mats,
            "stack": stack,
            "ep0": self._re_initial_ep,
            "l0": lambda_ref,
            "lambda_ref": lambda_ref,
            "re_workbook_path": getattr(self, "_re_workbook_path", None),
            "oblique_tgts": re_tgts,
            "wls_min": wls_min,
            "wls_max": wls_max,
            "back": self.back_check.isChecked(),
            "re_phase2_onesided_spline_fd": RE_PHASE2_ONESIDED_SPLINE_FD,
            "re_phase2_fd_parallel": RE_PHASE2_FD_PARALLEL,
            "re_phase2_fd_max_workers": RE_PHASE2_FD_MAX_WORKERS,
            "re_hl_delta_re_deadzone_abs": float(RE_RE_DEADZONE_DELTA_RE_ABS),
            "re_qwot_deadzone_abs": float(RE_RE_DEADZONE_QWOT_ABS),
        }

        cfg.update(sp)

        cfg.update(self.cfg)

        if not bool(cfg.get("re_enable_qwot_penalty", True)):
            cfg["re_qwot_penalty_weight"] = 0.0

            cfg["re_qwot_per_phase_schedule"] = False

            cfg["re_qwot_adaptive_init_scale"] = False

        if hasattr(self, "h_refine_check"):
            cfg["re_refine_h"] = bool(self.h_refine_check.isChecked())

            cfg["re_refine_l"] = bool(self.l_refine_check.isChecked())

            cfg["re_phase2b_substrate_cauchy"] = bool(self.sub_refine_check.isChecked())

        _knm = self.cfg.get("re_p4_beam_ap_knots_nm")

        if _knm is not None:
            cfg["re_p4_beam_ap_knots_nm"] = _knm

        if overrides:
            cfg.update(overrides)

        return cfg

    def _set_workflow_best_rmse(self, value: float) -> None:
        """Set the workflow best RMSE and refresh the status bar."""
        self._workflow_best_rmse = float(value)
        self._update_status_bar_stats()

    def _apply_re_workflow_rmse_if_better(self, r: float) -> None:
        """Update _workflow_best_rmse (RE RMSE) and refresh the status bar."""

        if not self._is_valid_rmse_value(r):
            return

        rf = float(r)
        prev = float(getattr(self, "_workflow_best_rmse", float("inf")))

        if rf < prev - 1e-15:
            self._set_workflow_best_rmse(rf)

    def _re_rmse_qwot_alpha_for_display(self) -> float:
        """alpha for √(sp²+alpha·QWOT²) : last RE run (phase 2b) if known, else speed preset."""

        r = getattr(self, "_re_rmse_qwot_alpha_ref", None)

        if r is not None:
            try:
                rf = float(r)

            except (TypeError, ValueError):
                rf = float("nan")

            if np.isfinite(rf) and rf >= 0.0:
                return rf

        return self._re_gui_qwot_penalty_weight()

    def _update_status_bar_stats(self):
        """Status bar: Evals (GUI evals + cumulative RE nfev) and best known RMSE."""

        if hasattr(self, "stats_label"):
            total = int(self.accumulated_evals) + int(getattr(self, "_re_nfev_cumulative", 0))

            self.stats_label.setText(f"Evals: {total}")

        if hasattr(self, "best_rmse_label"):
            self.best_rmse_label.setText(self._best_rmse_label_text())

    def _best_rmse_label_text(self) -> str:
        """Compute the best RMSE label text from current state."""
        be = float(getattr(self, "_best_eval_rmse", float("inf")))
        wf = float(getattr(self, "_workflow_best_rmse", float("inf")))

        if getattr(self, "_re_mode_active", False):
            if np.isfinite(wf) and wf < float("inf"):
                return f"Best RMSE: {wf:.6f}"
            if np.isfinite(be) and be < float("inf"):
                return f"Best RMSE: {be:.6f}"
            return "Best RMSE:  N/A"

        candidates: list[float] = []
        if np.isfinite(be) and be < float("inf"):
            candidates.append(be)
        if np.isfinite(wf) and wf < float("inf"):
            candidates.append(wf)
        if candidates:
            return f"Best RMSE: {min(candidates):.6f}"
        return "Best RMSE:  N/A"

    def _on_re_fit_window_changed(self) -> None:
        """Update eval when RE lambda window changes."""

        if getattr(self, "_re_loaded", False):
            self._schedule_eval(True)

    def _on_target_group_toggled(self, group_ref: list, checkbox: QCheckBox, *args) -> None:
        is_on = checkbox.isChecked()
        for tgt in group_ref:
            tgt.on = is_on
        self._schedule_eval()

    def _re_log_rmse_config_recap(
        self,
        *,
        re_rmse_initial: float | None,
        re_rmse_phase1: float | None,
        re_rmse_final: float | None,
        phase2_splines_done: bool,
    ) -> None:
        """Log RMSE milestones (start, phase 1 thicknesses, phase 2b splines + Cauchy substrate if done)."""

        alpha_q = self._re_rmse_qwot_alpha_for_display()

        logging.info(
            "RE  RMSE recap [ √(RMSE_sp2 + RMSE_QWOT2) ] (RMSE_QWOT = RMS |DeltaQ| absolute at lambda₀)   =%g",
            alpha_q,
        )

        logging.info(
            "  [0] Start  initial thicknesses, tabular H/L/sub indices (Excel) : %s",
            self._re_format_rmse_value(re_rmse_initial),
        )

        logging.info(
            "  [1] Variable thicknesses (phase 1), tabular indices              : %s",
            self._re_format_rmse_value(re_rmse_phase1),
        )

        if phase2_splines_done:
            logging.info(
                "  [2] + DeltaRe(H,L) splines + Cauchy substrate 3p (phase 2b, tube +/-%g): %s",
                RE_SUB_CAUCHY_TUBE_DELTA,
                self._re_format_rmse_value(re_rmse_final),
            )

        else:
            logging.info(
                "  [2] + H/L indices (phase 2b)                                   : not completed  "
                "worker final RMSE = %s",
                self._re_format_rmse_value(re_rmse_final),
            )

        if hasattr(self, "log"):
            self.log(
                f"RE RMSE recap: [0] {self._re_format_rmse_value(re_rmse_initial)} | [1] {self._re_format_rmse_value(re_rmse_phase1)} | [2] {self._re_format_rmse_value(re_rmse_final)}",
                "INFO",
            )

    def _on_display_re_results_clicked(self) -> None:

        snap = getattr(self, "_re_last_results_snapshot", None)

        if not snap or not snap.get("results"):
            self.log(
                "RE: no results table; run 'Run RE' first.",
                "WARNING",
            )

            return

        try:
            self._show_re_results_window(
                snap["results"],
                snap["ep0"],
                re_rmse_initial=snap.get("re_rmse_initial"),
                re_rmse_phase1=snap.get("re_rmse_phase1"),
                re_rmse_final=snap.get("re_rmse_final"),
                initial_stack=snap.get("initial_stack"),
            )

        except NUMERICAL_FAULT_EXCEPTIONS :
            self.log(
                "RE: impossible to open the results table.\n" + traceback.format_exc(),
                "ERROR",
            )

    def _re_p4_display_beam_kwargs(self) -> Dict[str, Any]:
        """Optional phase 4 arguments for _re_calc / RMSE when the last 'best' RE is a beam run."""

        if not getattr(self, "_re_p4_display_beam_active", False):
            return {}

        ak = getattr(self, "_re_p4_display_ap_knots_deg", None)

        al = getattr(self, "_re_p4_display_ap_knots_nm", None)

        if ak is None or al is None:
            return {}

        ak = np.asarray(ak, dtype=np.float64).ravel()

        al = np.asarray(al, dtype=np.float64).ravel()

        n = int(min(ak.size, al.size))

        if n < 2:
            return {}

        ap = float(self.cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG))

        return {
            "phase4_average": True,
            "beam_aperture": ap,
            "beam_aperture_knots_deg": np.ascontiguousarray(ak[:n]),
            "beam_aperture_knots_lam_nm": np.ascontiguousarray(al[:n]),
        }

    def _re_substrate_re_after_final(
        self,
        wls: np.ndarray,
        _re0_nominal: np.ndarray,
        fallback_re1: np.ndarray,
    ) -> np.ndarray:
        """Re(substrate) after correction: Cauchy 3p (a0,a1,a2) if present, else *fallback_re1*."""

        a0 = getattr(self, "_re_sub_cauchy_a0", None)

        a1 = getattr(self, "_re_sub_cauchy_a1", None)

        a2 = getattr(self, "_re_sub_cauchy_a2", None)

        if a0 is None or a1 is None or a2 is None:
            return np.asarray(fallback_re1, dtype=np.float64).copy()

        if not all(np.isfinite(float(x)) for x in (a0, a1, a2)):
            return np.asarray(fallback_re1, dtype=np.float64).copy()

        lr = float(self.l0_spin.value())

        th = np.array([float(a0), float(a1), float(a2)], dtype=np.float64)

        return re_substrate_cauchy_n_re_from_theta(wls, lr, th)

    def open_help(self):
        """Open ``pages/CERTUS_RE.html`` in the default browser (via certus_ui.open_documentation)."""

        open_documentation("CERTUS_RE")
