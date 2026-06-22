#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Corridors and Export Module.
Contains ExcelExport, CorridorWorker, CorridorExport, CorridorGen, and CorridorControl Mixins.
"""

from __future__ import annotations
import csv
from dataclasses import dataclass, field, replace
import json
import logging
import math
import multiprocessing
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

import numpy as np
import pandas as pd
import pyqtgraph as pg

from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSignal, QEvent, QAbstractAnimation, QThread
from PyQt6.QtWidgets import (
    QApplication, QDialog, QMessageBox, QFileDialog, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QPushButton, QTableWidgetItem, QCheckBox, QDoubleSpinBox,
    QSpinBox, QComboBox, QDialogButtonBox, QFrame, QGridLayout, QProgressBar,
    QScrollArea, QSlider, QSplitter, QStackedWidget, QTabWidget
)
from PyQt6.QtGui import QFont, QCursor

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4
_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5
_CORRIDOR_K_TAB_MIN_HALF_WIDTH: float = 1e-4

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, __version__
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.ui.certus_ui import (
    GenericWorker,
    CertusTheme,
    attach_excel_clipboard_context_menu,
    create_styled_button,
    show_toast,
    CertusScientificPlot,
    CertusActionBar,
    CertusCard,
    CertusStepper,
    CertusCollapsible,
    CertusStatusPill,
    safe_ui_action,
    get_certus_last_dir,
    set_certus_last_dir,
    setup_pyqtgraph_defaults,
    CertusLogPanel,
    CertusThemeToggle,
    EnhancedProgressWidget,
    ExcelTableWidget,
    create_header_logo_widget,
)

from certus.spline.certus_index_spline_core import (
    log_index_spline_d_trace,
    _log_index_spline_best_config,
    SPLINE_PWL_K_NODES,
    SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS,
    SPLINE_PERF_PRESETS,
    DataType,
    SplineOptConfig,
    default_n_mono_band_nm_from_spectrum,
    normalize_spectrum_dataframe,
    gui_perf_preset_only,
    _to_fraction_T,
    ensure_lam_nm_array,
    prepare_exp_TR_for_fit,
    substrate_id_from_name,
    canonical_spline_sigma_knots,
    bridge_sigma_knots_preserve_manual,
    rmse_at_spline_stage_x0_init,
    _QS_SPLINE_ORG,
    _QS_SPLINE_APP,
    _QS_SPECTRUM_FIT_R,
    _QS_SPECTRUM_FIT_TREL,
    _QS_SPECTRUM_FIT_T,
    _QS_SPECTRUM_WR,
    _QS_SPECTRUM_WT,
    _QS_SPLINE_UNCERTAINTY_DEFAULTS_REV,
    _UNCERTAINTY_DEFAULTS_REV,
    _QS_MAIN_SPLITTER_LAYOUT_REV,
    _MAIN_SPLITTER_LAYOUT_REV,
    _QS_MAIN_SPLITTER_STATE,
    _QS_RIGHT_SPLITTER_STATE,
    SIO2_DEFAULT_D_HI_NM,
    SIO2_DEFAULT_D_LO_NM,
    reset_smart_init_preview_guard,
    allowed_substrate_names,
)

from certus.utils.certus_index_utils import (
    log_structured_json_event,
    _get_substrate_n_array_spline,
    _stretch_sig_to_px,
    _get_xv_spectral_coord,
    _d_from_slider_int,
    _slider_int_from_d_nm,
    _spectral_display_align,
    _lam_uniform_grid,
    _safe_int_from_mapping,
    _filter_rmse_peaks_iteratively,
)

from certus.spline.spline_objective import (
    _spline_objective_lam_mask,
    objective_lam_mask_on_target_grid,
    spectral_mse_rmse_masked_from_nk,
)

from certus.spline.spline_workers import (
    _pack_spline_stage_result,
    worker_auto_best_split_knot_refinement,
)

from certus.spline.spline_pipeline import (
    _sync_theoretical_tr_from_nk_dict,
    worker_run_corridor_profile_after_nl_choice,
    worker_spline_optimization,
)

from certus.spline.certus_corridor_utils import quick_pwlnk_refit_result_dict

try:
    from certus.spline.spline_pipeline import _snap_spline_visual_dict
except ImportError:
    def _snap_spline_visual_dict(result: dict[str, Any]) -> dict[str, Any]:
        return dict(result)

from certus.utils.certus_ux import OBJ
from certus.utils.certus_reset_framework import create_reset_button
from certus.utils.certus_data import load_spectrum_columns, read_data_file_robust, build_export_context, build_report_sections, export_optimization_report
from certus.spline.certus_corridor_utils import _expand_corridor_envelope_with_reported_nk, enforce_min_k_corridor_half_width
from certus.spline.certus_corridor_fitter import _fit_local_quadratic_rmse_profile
from certus.ui.certus_plot import sanitize_xy_for_plot, plot_widget_plot_finite, wrap_scientific_plot_with_toolbar
from certus.core.certus_design_tokens import slider_corridor_half_stylesheet

from certus.spline.spline_presets import (
    project_manual_material_preset,
)

from certus.spline.spline_smart_init import (
    build_smart_manual_sigma_knots_from_preview_grid,
    interp_n_L_pwlnk_to_sigmas,
    pick_best_manual_material_preset,
    recalc_smart_init_spectral_preview,
    smart_init_sweep_node_thickness_rmse,
)

from certus.ui.certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog

from certus.spline.certus_index_spline_smart_init import (
    SmartInitPayload,
    _SmartInitState,
    SmartInitState,
    SmartInitPreviewManager,
)

from certus.utils.certus_skeleton import install_skeleton, uninstall_skeleton
from certus.spline.certus_index_spline_excel_export import _RMSEPlotContext


def _interp_series_at_sigma_knots(
    lam_grid: np.ndarray, y_grid: np.ndarray, sigma_knots: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate a spectral series at sigma-knot wavelengths and return points sorted by lambda."""
    lam_g = np.asarray(lam_grid, dtype=np.float64).ravel()
    y_g = np.asarray(y_grid, dtype=np.float64).ravel()
    sig_k = np.asarray(sigma_knots, dtype=np.float64).ravel()

    m = np.isfinite(lam_g) & np.isfinite(y_g)
    if not np.any(m):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_f = lam_g[m]
    y_f = y_g[m]
    order_grid = np.argsort(lam_f, kind="mergesort")
    lam_f = lam_f[order_grid]
    y_f = y_f[order_grid]

    lam_k = 1.0 / np.maximum(sig_k, 1e-30)
    mk = np.isfinite(lam_k)
    if not np.any(mk):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_k = lam_k[mk]
    y_k = np.interp(lam_k, lam_f, y_f, left=y_f[0], right=y_f[-1])
    order_k = np.argsort(lam_k, kind="mergesort")
    return lam_k[order_k], y_k[order_k]

def _plot_spectrum_raw_scatter(
    plot_w: pg.PlotWidget,
    x: np.ndarray,
    y: np.ndarray,
    *,
    color: str,
    name: str,
    symbol_size: int = 5,
) -> None:
    """Raw spectral data: always in points (no line), CERTUS convention."""
    from certus.ui.certus_ui import sanitize_xy_for_plot
    xf, yf = sanitize_xy_for_plot(x, y)
    if xf.size == 0:
        return
    plot_w.plot(
        xf,
        yf,
        pen=None,
        symbol="o",
        symbolSize=int(symbol_size),
        symbolBrush=pg.mkBrush(color),
        symbolPen=pg.mkPen(color, width=0.6),
        name=name,
    )


def _apply_fixed_log_k_axis(plot_w: Any | None) -> None:
    """Force the CERTUS log-k axis convention locally in this module."""
    if plot_w is None:
        return
    try:
        ymin_log = np.log10(1e-6)
        ymax_log = np.log10(1e-2)
        plot_w.setLogMode(False, True)
        try:
            plot_w.plotItem.ctrl.logYCheck.setChecked(True)
        except (AttributeError, RuntimeError):
            pass
        plot_w.setYRange(ymin_log, ymax_log, padding=0)
    except (AttributeError, RuntimeError, TypeError):
        import logging
        logging.getLogger("CERTUS").debug("_apply_fixed_log_k_axis failed", exc_info=True)

# Helper structures originally defined in CERTUS_INDEX_SPLINE

class _CorridorWorkerMixin:
    """Mixin containing corridor worker callbacks and plot tab."""

    def _finish_corridor_rmse_d_grid_worker_done(self, result: object) -> None:
        """End of RMSE(d) grid worker: merge profile_d*, refresh UI, adopt the best global result. Not for solver dicts."""
        self._worker_role = "idle"

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._set_corridor_grid_busy(False)

        self._corridor_rmse_grid_live_t0 = float("nan")
        self._corridor_rmse_live_last_plot_ts = float("nan")

        if not isinstance(result, dict):
            self.lbl_status.setText("RMSE(d) grid: canceled or invalid result.")

            if self.logger:
                self.logger.warning("RMSE(d) grid worker finished without dict result.")

            return

        if self.logger:
            d_dbg = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            r_dbg = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            n_nan_d = int(np.sum(~np.isfinite(d_dbg))) if d_dbg.size else 0
            n_nan_r = int(np.sum(~np.isfinite(r_dbg))) if r_dbg.size else 0
            cov_req = _safe_int_from_mapping(result, "profile_d_manual_grid_requested_base_points", -1)
            cov_ret = _safe_int_from_mapping(result, "profile_d_manual_grid_returned_base_points", -1)
            cov_miss = _safe_int_from_mapping(result, "profile_d_manual_grid_missing_after_emergency", -1)
            cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
            self.logger.info(
                "GUI RMSE(d) regular grid done [order A:result-received] | points=%d | nan(d)=%d | nan(rmse)=%d | coverage requested/returned/missing=%d/%d/%d | complete=%s",
                int(d_dbg.size),
                int(n_nan_d),
                int(n_nan_r),
                int(cov_req),
                int(cov_ret),
                int(cov_miss),
                "yes" if cov_ok else "no",
            )
            if d_dbg.size and r_dbg.size == d_dbg.size:
                fg_c = np.isfinite(d_dbg) & np.isfinite(r_dbg)
                if np.any(fg_c):
                    df = d_dbg[fg_c]
                    rf = r_dbg[fg_c]
                    j_min = int(np.argmin(rf))
                    j_max = int(np.argmax(rf))
                    d0_seed = result.get("profile_d_manual_grid_d0_seed_nm")
                    d_nom_pack = result.get("profile_d_manual_grid_nominal_pack_d_nm")
                    d0_txt = f"{float(d0_seed):.6f}" if d0_seed is not None and np.isfinite(float(d0_seed)) else "n/a"
                    d_nom_txt = (
                        f"{float(d_nom_pack):.6f}"
                        if d_nom_pack is not None and np.isfinite(float(d_nom_pack))
                        else "n/a"
                    )
                    self.logger.info(
                        "GUI RMSE(d) regular grid done [order A-ext:curve-on-receive] | d_nm[min,max]=[%.6f,%.6f] | "
                        "rmse[min,max]=[%.8f,%.8f] | curve_min(d,rmse)=(%.6f,%.8f) | curve_max(d,rmse)=(%.6f,%.8f) | "
                        "visit_first_d_nm=%s | nominal_pack_d_nm=%s",
                        float(np.min(df)),
                        float(np.max(df)),
                        float(np.min(rf)),
                        float(np.max(rf)),
                        float(df[j_min]),
                        float(rf[j_min]),
                        float(df[j_max]),
                        float(rf[j_max]),
                        d0_txt,
                        d_nom_txt,
                    )

        # --- GAP HEALING LOGIC (UX) ---
        # 1. Identify what we have and remove peaks for baseline
        d_raw = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_raw = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        snapshots = result.get("profile_d_full_results", [])

        # Filter peaks iteratively to find the "trustworthy" monotonic baseline
        order = np.argsort(d_raw)
        df, rf = d_raw[order], r_raw[order]
        snap_f = [snapshots[i] for i in order] if len(snapshots) == len(d_raw) else []

        d_mono, r_mono = _filter_rmse_peaks_iteratively(df, rf)
        # Find indices of monotonic points in the sorted list
        mono_indices = []
        if len(snap_f) > 0:
            for dm in d_mono:
                idx = np.where(np.abs(df - dm) < 1e-9)[0]
                if idx.size > 0:
                    mono_indices.append(idx[0])

        # 2. Check for GAPS relative to requested grid
        requested = getattr(self, "_corridor_rmse_requested_grid", np.array([]))
        tasks = []
        if requested.size > 0 and len(snap_f) > 0 and len(mono_indices) > 0:
            for d_req in requested:
                # Is it missing?
                if not np.any(np.abs(d_mono - d_req) < 1e-4):
                    # FIND BEST NEIGHBOR in monotonic set
                    dist = np.abs(d_mono - d_req)
                    # We look for immediate neighbors (left/right)
                    # but actually any nearby monotonic point is a good seed.
                    # As requested: "best among left/right neighbors"
                    side_indices = np.where(dist < 2.1 * (requested[1] - requested[0] if requested.size > 1 else 1.0))[
                        0
                    ]
                    if side_indices.size > 0:
                        # Best among those nearby
                        best_side_sub_idx = side_indices[np.argmin(r_mono[side_indices])]
                        global_idx_in_snap_f = mono_indices[best_side_sub_idx]
                        seed_snap = snap_f[global_idx_in_snap_f]
                        tasks.append((float(d_req), seed_snap))

        if tasks and str(getattr(self, "_worker_role", "") or "") != "rmse_heal":
            if self.logger:
                self.logger.info("GUI RMSE(d) Grid Healing | Launching healer for %d gaps", len(tasks))
            heal_tasks = list(tasks)
            QTimer.singleShot(0, lambda t=heal_tasks: self._launch_corridor_rmse_gap_heal(t))
            return

        # Continuing finalization...
        upd = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        for k, v in result.items():
            if str(k).startswith("profile_d") or str(k).startswith("corridor_"):
                upd[k] = v

        self._last_result = upd

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        try:
            self._plot_corridor_rmse_tab(upd)

        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Corridor RMSE tab refresh after manual grid failed", exc_info=True)

        n_ok = int(np.asarray(upd.get("profile_d_values_nm", [])).size)

        n_tot = int(result.get("profile_d_manual_grid_total_points", n_ok))
        n_base_done = int(result.get("profile_d_manual_grid_base_done_points", min(n_ok, n_tot)) or min(n_ok, n_tot))
        n_extra_done = int(
            result.get("profile_d_manual_grid_extra_done_points", max(0, n_ok - n_tot)) or max(0, n_ok - n_tot)
        )

        self._set_corridor_grid_progress_ui(
            done=n_ok,
            total=n_tot,
            base_done=n_base_done,
            base_total=n_tot,
            extra_done=n_extra_done,
        )

        self._set_corridor_grid_completed_badge()

        n_bp = int(result.get("profile_d_manual_grid_breakpoint_count", 0))

        n_extra = int(result.get("profile_d_manual_grid_extra_points", 0))

        n_glob_runs = int(result.get("profile_d_manual_grid_global_opt_runs", 0))

        n_glob_imp = int(result.get("profile_d_manual_grid_global_opt_improved", 0))

        rmse_glob_best = float(result.get("profile_d_manual_grid_best_global_rmse", float("nan")))

        t_ms = float(result.get("profile_d_manual_grid_elapsed_ms", float("nan")))

        self.lbl_status.setText(
            f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | "
            f"global_opt={n_glob_runs}/{n_glob_imp} | {t_ms:.0f} ms"
            if np.isfinite(t_ms)
            else f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | global_opt={n_glob_runs}/{n_glob_imp}"
        )

        if self.logger:
            self.logger.info(
                "GUI RMSE(d) regular grid done | n_points=%d | breakpoints=%d | extra_points=%d | global_opt_runs=%d | global_opt_improved=%d | best_global_rmse=%s | elapsed_ms=%s",
                n_ok,
                int(n_bp),
                int(n_extra),
                int(n_glob_runs),
                int(n_glob_imp),
                f"{rmse_glob_best:.8f}" if np.isfinite(rmse_glob_best) else "n/a",
                f"{t_ms:.1f}" if np.isfinite(t_ms) else "n/a",
            )

        best_global_result = result.get("profile_d_manual_grid_best_global_result")
        curve_minimum_result = result.get("profile_d_manual_grid_curve_minimum_result")
        curve_beats = bool(result.get("profile_d_manual_grid_curve_beats_nominal", False))
        grid_cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
        delta_curve = float(result.get("profile_d_manual_grid_curve_vs_nominal_delta_rmse", float("nan")))

        rmse_best_global = (
            self._rmse_from_result_dict(best_global_result) if isinstance(best_global_result, dict) else float("nan")
        )
        rmse_curve = (
            self._rmse_from_result_dict(curve_minimum_result)
            if isinstance(curve_minimum_result, dict)
            else float("nan")
        )

        cand_global_ok = bool(
            int(n_glob_imp) > 0 and isinstance(best_global_result, dict) and np.isfinite(rmse_best_global)
        )
        cand_curve_ok = bool(curve_beats and isinstance(curve_minimum_result, dict) and np.isfinite(rmse_curve))

        if int(n_glob_imp) > 0 and (not cand_global_ok) and self.logger:
            self.logger.warning(
                "GUI RMSE(d) regular grid | global_opt_improved=%d but best_global_result missing/invalid rmse.",
                int(n_glob_imp),
            )

        chosen_seed: dict[str, Any] | None = None
        chosen_origin = ""
        chosen_log_tag = ""
        chosen_status = ""
        if cand_global_ok and cand_curve_ok:
            if rmse_curve < rmse_best_global:
                chosen_seed = dict(curve_minimum_result)
                chosen_origin = "corridor-profile-curve-minimum"
                chosen_log_tag = "order C2:corridor-curve-min-promoted-over-global-opt"
                chosen_status = "[INDEX_SPLINE.CORRIDORS] curve minimum promoted | auto-refine in progress"
            else:
                chosen_seed = dict(best_global_result)
                chosen_origin = "corridor-global-optimization-best"
                chosen_log_tag = "order C:corridor-global-opt-best-promoted"
                chosen_status = "[INDEX_SPLINE.CORRIDORS] new corridor minimum found via global optimization | auto-refine in progress"
        elif cand_global_ok:
            chosen_seed = dict(best_global_result)
            chosen_origin = "corridor-global-optimization-best"
            chosen_log_tag = "order C:corridor-global-opt-best-promoted"
            chosen_status = "[INDEX_SPLINE.CORRIDORS] new corridor minimum found via global optimization | auto-refine in progress"
        elif cand_curve_ok:
            chosen_seed = dict(curve_minimum_result)
            chosen_origin = "corridor-profile-curve-minimum"
            chosen_log_tag = "order B2:corridor-curve-min-promoted"
            chosen_status = "[INDEX_SPLINE.CORRIDORS] curve minimum promoted as nominal | auto-refine in progress"

        if isinstance(chosen_seed, dict):
            if not grid_cov_ok:
                if self.logger:
                    self.logger.error(
                        "[INDEX_SPLINE.CORRIDORS] adoption candidate rejected | reason=base-grid coverage incomplete"
                    )
                chosen_seed = None
            if self.logger:
                rmse_prev_upd = self._rmse_from_result_dict(upd)
                d_sel = chosen_seed.get("d_nm") if isinstance(chosen_seed, dict) else None
                d_sel_txt = (
                    f"{float(d_sel):.6f}" if isinstance(d_sel, (int, float)) and np.isfinite(float(d_sel)) else "n/a"
                )
                self.logger.info(
                    "[INDEX_SPLINE.CORRIDORS] adoption decision | candidate_origin=%s | d_selected_nm=%s | "
                    "rmse_before_adoption=%s | rmse_global_opt=%s | rmse_curve=%s | delta_curve_vs_pre_adoption=%s | "
                    "grid_coverage_complete=%s",
                    chosen_origin,
                    d_sel_txt,
                    (f"{rmse_prev_upd:.8f}" if np.isfinite(rmse_prev_upd) else "n/a"),
                    (f"{rmse_best_global:.8f}" if np.isfinite(rmse_best_global) else "n/a"),
                    (f"{rmse_curve:.8f}" if np.isfinite(rmse_curve) else "n/a"),
                    (f"{delta_curve:.3e}" if np.isfinite(delta_curve) else "n/a"),
                    "yes" if grid_cov_ok else "no",
                )

            if isinstance(chosen_seed, dict):
                self._merge_rmse_grid_promotion_into_nominal(
                    dict(chosen_seed),
                    adoption_log_tag=chosen_log_tag,
                )
                if isinstance(self._last_result, dict):
                    self._last_worker_result = dict(self._last_result)

                strict_snapshot = dict(chosen_seed)
                if strict_snapshot.get("x_seg_spline_sigma") is None and strict_snapshot.get("x") is not None:
                    strict_snapshot["x_seg_spline_sigma"] = (
                        np.asarray(strict_snapshot.get("x"), dtype=np.float64).ravel().copy()
                    )
                if strict_snapshot.get("x") is None and strict_snapshot.get("x_seg_spline_sigma") is not None:
                    strict_snapshot["x"] = (
                        np.asarray(strict_snapshot.get("x_seg_spline_sigma"), dtype=np.float64).ravel().copy()
                    )
                chosen_seed["gui_solver_snapshot_for_corridors"] = dict(strict_snapshot)

                self.lbl_status.setText(chosen_status)
                if self._schedule_corridor_auto_refine(
                    chosen_seed,
                    rerun_corridor=True,
                    origin=chosen_origin,
                ):
                    return
                if self.logger:
                    self.logger.warning(
                        "[INDEX_SPLINE.CORRIDORS] auto-refine chain failed to start | chosen_origin=%s",
                        chosen_origin,
                    )

        if self.logger:
            dv = np.asarray(upd.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            rv = np.asarray(upd.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            if dv.size and rv.size == dv.size:
                fg_z = np.isfinite(dv) & np.isfinite(rv)
                if np.any(fg_z):
                    dz = dv[fg_z]
                    rz = rv[fg_z]
                    jz = int(np.argmin(rz))
                    self.logger.info(
                        "[INDEX_SPLINE.CORRIDORS] post-merge curve | points=%d | rmse_min=%.8f | d=%.6f nm | "
                        "nominal_dict_d_nm=%s | nominal_dict_rmse=%s",
                        int(dz.size),
                        float(rz[jz]),
                        float(dz[jz]),
                        (
                            f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                            else "n/a"
                        ),
                        (
                            f"{self._rmse_from_result_dict(self._last_result):.8f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(self._rmse_from_result_dict(self._last_result))
                            else "n/a"
                        ),
                    )

        return

    def _on_worker_done(self, result: object) -> None:

        role = str(getattr(self, "_worker_role", "main") or "main")
        manual_pipeline_roles = (
            "manual_sigma_insert",
            "manual_autoshift",
            "manual_auto_add_one",
            "manual_auto_clean",
            "manual_repartition_log",
            "manual_repartition_sigma",
        )
        worker_obj = getattr(self, "_worker", None)
        worker_func = getattr(worker_obj, "func", None)
        worker_name = str(getattr(worker_func, "__name__", "?") or "?")
        manual_dlg = getattr(self, "_manual_knots_dialog", None)

        uninstall_skeleton(self.tabs_main)
        if role == "curve_min_deep":
            self._finish_curve_minimum_deep_worker_done(result)

            return

        if role == "rmse_heal":
            self._finish_rmse_heal_worker_done(result)
            return

        grid_fin = self._is_rmse_d_grid_worker_finalize_dict(result)

        if grid_fin or role == "rmse_grid":
            if grid_fin and role != "rmse_grid" and self.logger:
                op_id = result.get("op_id") if isinstance(result, dict) else None

                self.logger.warning(
                    "[INDEX_SPLINE.CORRIDORS] worker_done grid result | profile_d_status=%s | worker_role=%r | worker=%s | op_id=%s",
                    (result.get("profile_d_status") if isinstance(result, dict) else None),
                    role,
                    worker_name,
                    str(op_id) if op_id is not None else "n/a",
                )

            self._finish_corridor_rmse_d_grid_worker_done(result)
            return

        if not isinstance(result, dict):
            if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
                manual_dlg.set_runtime_busy(False)
                manual_dlg.append_runtime_log("Re-optimization finished without usable result.")

            self.lbl_status.setText("Canceled or no result (dict)")
            self._worker_role = "idle"
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

            if self.logger:
                if result is None:
                    self.logger.warning(
                        "[INDEX_SPLINE.GUI] worker finished without a result dictionary"
                        "Common causes: Stop button during calculation, thread closure/interruption, "
                        "or silent worker-side exception. Graphs are not updated since this signal."
                    )

                else:
                    self.logger.warning(
                        "[INDEX_SPLINE.GUI] worker returned %s instead of a result dictionary - result ignored",
                        type(result).__name__,
                    )

            self._refresh_post_optimization_option_controls()
            return

        if role not in ("rmse_grid", "corridors"):
            self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_best_idx = -1
            self._corridor_rmse_center_nm = float("nan")
            self._corridor_rmse_robust_lo = float("nan")
            self._corridor_rmse_robust_hi = float("nan")
            self._corridor_rmse_robust_ok = False
            if hasattr(self, "plot_corridor_rmse_d"):
                self.plot_corridor_rmse_d.clear()
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        if self.logger:
            op_id = result.get("op_id")

            role_ctx = role if worker_name == "?" else f"{role}|worker={worker_name}"

            op_id_ctx = str(op_id) if op_id is not None else "n/a"

            _wm = result.get("pipeline_best_rmse_watermark")

            _wms = result.get("pipeline_best_rmse_stage")

            _wm_hint = ""

            if _wm is not None and np.isfinite(float(_wm)):
                _wm_hint = f" | pipeline watermark (best RMSE seen during run): {_wm:.6f} (@ {_wms!s})"

            self.logger.info(
                "[INDEX_SPLINE.GUI] result dictionary received | rmse_current_nk=%.6f | "
                "d = %.4f nm | role = %s | worker = %s | op_id = %s%s",
                float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                float(result.get("d_nm", float("nan"))),
                role,
                worker_name,
                op_id_ctx,
                _wm_hint,
            )

            log_index_spline_d_trace(
                self.logger,
                f"[INDEX_SPLINE.GUI] worker result received | role={role_ctx} | op_id={op_id_ctx}",
                result.get("d_nm"),
                detail=("worker=" + worker_name),
            )

            split_mesh = self._result_uses_split_mesh(result)

            self.logger.info(
                "[INDEX_SPLINE.GUI] worker details | mse=%.6e | split=%s | continuous=%s | adaptive=%s",
                float(result.get("mse", float("nan"))),
                bool(split_mesh),
                bool(result.get("continuous_model")),
                bool(result.get("adaptive_mesh")),
            )

            log_structured_json_event(
                self.logger,
                "AUTO_BEST_JSON",
                "worker_done",
                role=role,
                worker=worker_name,
                op_id=op_id_ctx,
                mse=float(result.get("mse", float("nan"))),
                rmse=float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                rmse_convention="sqrt(max(mse,0))",
                d_nm=float(result.get("d_nm", float("nan"))),
                split=bool(split_mesh),
                continuous=bool(result.get("continuous_model")),
                adaptive=bool(result.get("adaptive_mesh")),
            )

        # Auto-Best: trigger a 2nd local pass (free split n/logk knots) after the 1st warm pass.

        if self._auto_best_two_stage_refine:
            cfg2 = self._build_opt_config()

            if cfg2 is not None:
                self._auto_best_second_stage_pending = {
                    "seed": dict(result),
                    "cfg": cfg2,
                }

                self._auto_best_two_stage_refine = False

                self.log(
                    "Auto-Best: launching local pass 2 (separated sigma knots for n and ln k, then polish).",
                    "INFO",
                )

                self.lbl_status.setText("Auto-Best pass 2: preparing...")

                QTimer.singleShot(0, self._start_auto_best_second_stage)

                return

            self._auto_best_two_stage_refine = False

        self._last_worker_result = dict(result)

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        display = result if role == "corridors" else self._display_result_prefer_best_live(result)

        self._last_result = display

        st = self._format_post_optimization_status(display, result)

        if display.get("adaptive_mesh"):
            st = "Adaptive mesh | " + st

        if display.get("auto_knot_stages") and "sigma_knots" in display:
            kfin = int(np.asarray(display["sigma_knots"], dtype=np.float64).size)

            kbest = display.get("auto_knots_K_best")

            if kbest is not None and int(kbest) != kfin:
                st = f"K retained={int(kbest)} (last K={kfin}) stages={len(display['auto_knot_stages'])} | " + st

            else:
                st = f"K={kfin} stages={len(display['auto_knot_stages'])} | " + st

        if display.get("gui_display_from_best_live"):
            st = "Meilleur RMSE (live) | " + st

        self.lbl_status.setText(st)

        if self.logger:
            self.logger.info("End optimization: %s", st)

            rmse_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )

            _log_index_spline_best_config(self.logger, display, rmse_fin, title="[END OPTIM  display / export]")

        # === SAFE-GUARD: Wrap entire final completion path to prevent silent app termination ===
        try:
            plot_source = f"fin_worker:{role}"
            if worker_name != "?":
                plot_source = f"{plot_source}|{worker_name}"
            self._plot_result(display, plot_source=plot_source)
        except Exception as e:
            import traceback

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _plot_result failed: %s\n%s", type(e).__name__, __import__('traceback').format_exc()
                )
            else:
                print(f"[CRASH GUARD] _plot_result failed: {e}", file=__import__("sys").stderr)

        try:
            self._refresh_data_table()
        except Exception as e:

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_data_table failed: %s\n%s",
                    type(e).__name__,
                    __import__('traceback').format_exc(),
                )

        if role in manual_pipeline_roles and self.logger:
            self.logger.info(
                "PIPELINE [05b/09] Manual pipeline stage completed (%s); proceeding to corridors only afterwards if requested.",
                role,
            )
        if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
            try:
                manual_dlg.set_runtime_busy(False)
                d_fin, rmse_fin = self._runtime_metrics_from_result_dict(display)
                rmse_txt = f"{float(rmse_fin):.6f}" if np.isfinite(rmse_fin) else "n/a"
                self._refresh_manual_dialog_preview(manual_dlg, display)
                # Important: for manual-local flows, keep the exact worker output mesh
                # (result) instead of the display snapshot (which may be overridden by
                # a stale best-live candidate at another K).
                sigma_before = np.asarray(getattr(manual_dlg, "_base_sigma_knots", []), dtype=np.float64).ravel()
                sigma_requested = manual_dlg.selected_sigma_knots()
                sigma_fin = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                if sigma_fin.size == 0:
                    sigma_fin = np.asarray(display.get("sigma_knots", []), dtype=np.float64).ravel()
                requested_summary = self._summarize_manual_mesh_change(sigma_before, sigma_requested)
                applied_summary = self._summarize_manual_mesh_change(sigma_before, sigma_fin)
                manual_dlg.append_runtime_log(
                    self._manual_mesh_change_log_line("Requested mesh", requested_summary)
                )
                same_requested_and_applied = requested_summary["after_sigma_knots"].size == applied_summary[
                    "after_sigma_knots"
                ].size and np.allclose(
                    requested_summary["after_sigma_knots"],
                    applied_summary["after_sigma_knots"],
                    rtol=1e-10,
                    atol=1e-12,
                )
                if not same_requested_and_applied:
                    manual_dlg.append_runtime_log(
                        "Worker returned a different mesh than requested; keeping the applied mesh below."
                    )
                manual_dlg.append_runtime_log(
                    self._manual_mesh_change_log_line("Applied mesh", applied_summary)
                )
                if sigma_fin.size:
                    manual_dlg.adopt_sigma_knots(sigma_fin)
                opt_delta_ns = result.get("substrate_n_offset")
                if opt_delta_ns is None:
                    opt_delta_ns = display.get("substrate_n_offset")
                if opt_delta_ns is not None:
                    manual_dlg.adopt_delta_ns(float(opt_delta_ns))
                manual_dlg.set_runtime_progress(100.0, "Re-optimisation terminee")
                manual_dlg.set_runtime_metrics(d_fin, rmse_fin)
                manual_dlg.append_runtime_log(f"Re-optimisation terminee | RMSE={rmse_txt}")
                if self.logger:
                    self.logger.info(
                        "[INDEX_SPLINE.GUI] manual pipeline applied mesh | role=%s | %s",
                        role,
                        self._manual_mesh_change_log_line("applied", applied_summary),
                    )
                # Stores the absolute best config for the 'Recall best RMSE' button.
                # We use `result` (raw from worker) and not `display`: `display` may be
                # the best live snapshot (e.g. K=14 initial during auto_clean), which
                # would point "Recall best" to an erroneous intermediate state.
                raw_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                raw_rmse = self._rmse_from_result_dict(result)
                if raw_sk.size and np.isfinite(raw_rmse):
                    manual_dlg.update_best_config(result, raw_sk)
            except Exception as e:

                if self.logger:
                    self.logger.exception(
                        "INDEX_SPLINE [CRASH GUARD] manual dialog finalization failed: %s\n%s",
                        type(e).__name__,
                        __import__('traceback').format_exc(),
                    )

        # --- Manual extra-knot dialog (must occur before any deferred corridors) ---
        if (
            role not in ((*manual_pipeline_roles, "corridors"))
            and self._can_offer_manual_extra_knots(result)
            and getattr(self, "_corridor_auto_refine_plan", None) is None
        ):
            if self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot stage available after optimization; this stage runs before deferred corridors."
                )

            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                open_manual_fn = getattr(self, "_open_manual_extra_knots_dialog", None)
                if callable(open_manual_fn):
                    open_manual_fn(result)
                    if self.logger:
                        self.logger.info(
                            "PIPELINE [05b/09] Manual extra-knot stage opened in keep-open mode; user closes dialog explicitly."
                        )
                else:
                    # Fallback for test doubles/legacy call paths without non-blocking dialog helper.
                    lambdas = self._prompt_manual_extra_knots(result)
                    if lambdas:
                        if self.logger:
                            self.logger.info(
                                "Manual extra-knot stage accepted; deferred corridors are postponed until manual insertion completes."
                            )
                        self._start_manual_sigma_insert_worker(result, lambdas)
                        return
            elif self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot dialog already open; keeping current session active."
                )

        self._worker_role = "idle"

        try:
            self._refresh_post_optimization_option_controls()
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_post_optimization_option_controls failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )

        self.lbl_status.setText(self._post_optimization_ready_status(st))

        try:
            self.export_excel(auto_export=True)
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] export_excel(auto_export=True) failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )
            else:
                print(f"[CRASH GUARD] export_excel failed: {e}", file=__import__("sys").stderr)

    def _plot_corridor_tab(
        self,
        r: dict,
        lam_s: np.ndarray,
        n_s: np.ndarray,
        k_s: np.ndarray,
        *,
        spectral_sort_order: np.ndarray | None = None,
    ) -> None:
        """n/k Corridors  tab: central curves + envelopes; auto-focus if bands present."""
        if r is None:
            return

        try:
            # Set log mode BEFORE clear() so _apply_sensible_empty_range uses log range
            if hasattr(self, "plot_k_corridor"):
                self.plot_k_corridor.setLogMode(y=True)
            self.plot_n_corridor.clear()
            self.plot_k_corridor.clear()
            # Re-apply log mode after clear() (clear() reinstalls crosshair/range)
            self.plot_k_corridor.setLogMode(y=True)
        except (AttributeError, RuntimeError):
            if self.logger:
                import traceback as _tb

                self.logger.warning("DIAG CORRIDOR PLOT: clear/logmode failed, returning early\n%s", _tb.format_exc())
            return

        nu = int(np.asarray(lam_s).size)
        spec_order = (
            np.asarray(spectral_sort_order, dtype=np.int64)
            if spectral_sort_order is not None
            else np.arange(nu, dtype=np.int64)
        )
        if spec_order.size != nu:
            spec_order = np.arange(nu, dtype=np.int64)

        # lam_s / n_s / k_s viennent de _spectral_display_align : d?j? co-lin?aires et tri?s par lambda.
        # spec_order is used only to reorder corridor bands stored as n_lam (raw order before sorting).
        lam_f = np.asarray(lam_s, dtype=np.float64).ravel()
        n_f = np.asarray(n_s, dtype=np.float64).ravel()
        k_f = np.asarray(k_s, dtype=np.float64).ravel()

        def _get_aligned(key: str) -> np.ndarray:
            val = np.asarray(r.get(key, []), dtype=np.float64).ravel()
            if val.size < nu:
                return np.full(nu, np.nan)
            val_u = val[:nu]
            return val_u[spec_order]

        # Pre-collection of data for dynamic y-axis scaling
        y_n_all = [n_f]
        y_k_all = [k_f]

        # DIAG CORRIDOR PLOT
        if self.logger:
            corr_keys = ["corridor_n_lo", "corridor_n_hi", "corridor_k_lo", "corridor_k_hi"]
            key_info = []
            for _ck in corr_keys:
                _raw = r.get(_ck)
                if _raw is None:
                    key_info.append(f"{_ck}=ABSENT")
                else:
                    _arr = np.asarray(_raw, dtype=np.float64).ravel()
                    _nfin = int(np.sum(np.isfinite(_arr)))
                    key_info.append(f"{_ck}:size={_arr.size}/fin={_nfin}")
            self.logger.debug(
                "DIAG CORRIDOR PLOT | nu=%d | spec_order_size=%d | %s",
                nu,
                int(spec_order.size),
                " | ".join(key_info),
            )

        # 1. Uncertainty Corridor (Profiling-based)
        n_lo = _get_aligned("corridor_n_lo")
        n_hi = _get_aligned("corridor_n_hi")
        k_lo = _get_aligned("corridor_k_lo")
        k_hi = _get_aligned("corridor_k_hi")

        has_profile = False
        if np.any(np.isfinite(n_lo)) and np.any(np.isfinite(n_hi)):
            has_profile = True
            y_n_all.extend([n_lo, n_hi])
            # Shaded background band (lowest layer)
            cln_f = pg.PlotCurveItem(lam_f, n_lo, pen=None)
            cun_f = pg.PlotCurveItem(lam_f, n_hi, pen=None)
            self.plot_n_corridor.addItem(pg.FillBetweenItem(cln_f, cun_f, brush=pg.mkBrush(0, 87, 255, 130)))

            # n_min / n_max DashLine + Glow (matching k style)
            p_nlo_glow = pg.mkPen((180, 220, 255, 180), width=4.5)
            p_nhi_glow = pg.mkPen((160, 200, 255, 180), width=4.5)
            p_nlo = pg.mkPen((0, 140, 255, 255), width=2.2, style=Qt.PenStyle.DashLine)
            p_nhi = pg.mkPen((0, 70, 255, 255), width=2.2, style=Qt.PenStyle.DashLine)

            self._add_curve(self.plot_n_corridor, lam_f, n_lo, None, "n_min_glow", pen=p_nlo_glow)
            self._add_curve(self.plot_n_corridor, lam_f, n_hi, None, "n_max_glow", pen=p_nhi_glow)
            self._add_curve(self.plot_n_corridor, lam_f, n_lo, None, "n_min", pen=p_nlo)
            self._add_curve(self.plot_n_corridor, lam_f, n_hi, None, "n_max", pen=p_nhi)

        k_min_pts = 0
        klf = np.full(nu, np.nan, dtype=np.float64)
        khf = np.full(nu, np.nan, dtype=np.float64)
        if np.any(np.isfinite(k_lo)) and np.any(np.isfinite(k_hi)):
            has_profile = True
            # Enforce statistical width floor globally for display
            k_lo_e, k_hi_e, k_min_pts = enforce_min_k_corridor_half_width(
                k_lo, k_hi, k_f, min_half_width=_CORRIDOR_K_TAB_MIN_HALF_WIDTH
            )
            y_k_all.extend([k_lo_e, k_hi_e])

            # Simple trace: k_min / k_max as dashed lines (same series as Data Corridor).
            klf = np.maximum(k_lo_e, 1e-15)
            khf = np.maximum(k_hi_e, 2e-15)
            # Visual highlight for k corridor bounds: glow plus dashed line on top.
            pen_kmin_glow = pg.mkPen((255, 235, 190, 220), width=5.0, style=Qt.PenStyle.SolidLine)
            pen_kmax_glow = pg.mkPen((255, 210, 200, 220), width=5.0, style=Qt.PenStyle.SolidLine)
            pen_kmin = pg.mkPen((255, 150, 0, 255), width=2.8, style=Qt.PenStyle.DashLine)
            pen_kmax = pg.mkPen((255, 40, 0, 255), width=2.8, style=Qt.PenStyle.DashLine)
            # Same pipeline as the nominal k curve (sanitize + widget log-axis consistency).
            lk_min = np.log10(np.maximum(klf, 1e-30))
            lk_max = np.log10(np.maximum(khf, 1e-30))
            self._add_curve(self.plot_k_corridor, lam_f, lk_min, "#ffe0b2", "k_min_glow", pen=pen_kmin_glow)
            self._add_curve(self.plot_k_corridor, lam_f, lk_max, "#ffd7d1", "k_max_glow", pen=pen_kmax_glow)
            self._add_curve(self.plot_k_corridor, lam_f, lk_min, "#ff8c00", "k_min", pen=pen_kmin)
            self._add_curve(self.plot_k_corridor, lam_f, lk_max, "#ff3c00", "k_max", pen=pen_kmax)

        # Data for the vertical crosshair label: k_min / k_nominal / k_max at cursor wavelength.
        self._corridor_k_crosshair_lam = np.asarray(lam_f, dtype=np.float64).copy()
        self._corridor_k_crosshair_nom = np.asarray(k_f, dtype=np.float64).copy()
        self._corridor_k_crosshair_lo = np.asarray(klf, dtype=np.float64).copy()
        self._corridor_k_crosshair_hi = np.asarray(khf, dtype=np.float64).copy()

        # 2. Filigree (all profile models)
        n_prof_all = np.asarray(r.get("profile_d_n_curves", []), dtype=np.float64)
        k_prof_all = np.asarray(r.get("profile_d_k_curves", []), dtype=np.float64)
        d_prof_all = np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        filigree_count = 0
        if n_prof_all.ndim == 2 and n_prof_all.shape[0] == d_prof_all.size and d_prof_all.size > 0:
            idx_all = np.flatnonzero(np.all(np.isfinite(n_prof_all[:, :nu]), axis=1))
            if idx_all.size > 0:
                n_show = int(min(7, idx_all.size))
                idx_pick = idx_all[np.unique(np.round(np.linspace(0, idx_all.size - 1, n_show)).astype(int))]
                for i in idx_pick:
                    nr = n_prof_all[i, :nu][spec_order]
                    plot_widget_plot_finite(self.plot_n_corridor, lam_f, nr, pen=pg.mkPen(0, 87, 255, 30, width=1), animate=False)
                    if k_prof_all.ndim == 2 and k_prof_all.shape[0] == d_prof_all.size:
                        kr = np.maximum(k_prof_all[i, :nu][spec_order], 1e-15)
                        plot_widget_plot_finite(self.plot_k_corridor, lam_f, kr, pen=pg.mkPen(255, 90, 0, 25, width=1), animate=False)
                filigree_count = idx_pick.size

        # 3. Bootstrap (optional)
        bn_lo = _get_aligned("boot_corridor_n_lo")
        bn_hi = _get_aligned("boot_corridor_n_hi")
        bk_lo = _get_aligned("boot_corridor_k_lo")
        bk_hi = _get_aligned("boot_corridor_k_hi")
        has_boot = False
        try:
            if (
                bn_lo.size == lam_s.size
                and bn_hi.size == lam_s.size
                and bk_lo.size == lam_s.size
                and bk_hi.size == lam_s.size
            ):
                has_boot = True
                y_n_all.extend([bn_lo, bn_hi])
                y_k_all.extend([bk_lo, bk_hi])
                pen_bn = pg.mkPen((0, 160, 80, 90), width=1, style=Qt.PenStyle.DashLine)
                cu_bn = pg.PlotCurveItem(lam_s, bn_hi, pen=pen_bn)
                cl_bn = pg.PlotCurveItem(lam_s, bn_lo, pen=pen_bn)
                self.plot_n_corridor.addItem(cu_bn)
                self.plot_n_corridor.addItem(cl_bn)
                self.plot_n_corridor.addItem(pg.FillBetweenItem(cl_bn, cu_bn, brush=pg.mkBrush(0, 160, 80, 28)))
                bk_lo_finite = np.where(np.isfinite(bk_lo) & (bk_lo > 1e-15), bk_lo, 1e-15)
                bk_hi_finite = np.where(np.isfinite(bk_hi) & (bk_hi > 2e-15), bk_hi, 2e-15)
                pen_bk = pg.mkPen((120, 0, 180, 120), width=1, style=Qt.PenStyle.DashLine)
                cu_bk = pg.PlotCurveItem(lam_s, bk_hi_finite, pen=pen_bk)
                cl_bk = pg.PlotCurveItem(lam_s, bk_lo_finite, pen=pen_bk)
                self.plot_k_corridor.addItem(cu_bk)
                self.plot_k_corridor.addItem(cl_bk)
                self.plot_k_corridor.addItem(pg.FillBetweenItem(cl_bk, cu_bk, brush=pg.mkBrush(120, 0, 180, 80)))
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Corridor bootstrap band plot failed", exc_info=True)

        # 4. Nominal curves (on top of bands / filigree)
        lk_f = np.log10(np.maximum(k_f, 1e-30))
        self._add_curve(self.plot_n_corridor, lam_f, n_f, "#0057ff", "n", pen=pg.mkPen("#0057ff", width=3))
        self._add_curve(self.plot_k_corridor, lam_f, lk_f, "#ff5a00", "k", pen=pg.mkPen("#ff5a00", width=3))

        seed_gate_kept_rate = float(r.get("profile_d_seed_gate_kept_rate", float("nan")))
        seed_gate_eval_count = int(r.get("profile_d_seed_gate_eval_count", 0))
        k_min_hw = _CORRIDOR_K_TAB_MIN_HALF_WIDTH

        # UI Updates
        d_nm = float(r.get("d_nm", float("nan")))
        d_txt = f"d = {d_nm:.1f} nm" if np.isfinite(d_nm) else "d = "

        try:
            self.plot_n_corridor.plotItem.setTitle(
                f"n(lambda) + corridors  {d_txt}", color=CertusTheme.PRIMARY, size="10pt"
            )

            self.plot_k_corridor.plotItem.setTitle(
                f"log10 k(lambda) + corridors  {d_txt}", color=CertusTheme.PRIMARY, size="10pt"
            )

            if has_profile:
                self.plot_k_corridor.setToolTip(
                    (
                        "Bold orange: k from the result dict (same as main tab). "
                        + "Shaded band: pointwise min/max in linear k over accepted d-refits, enlarged so the bold curve stays inside. "
                        + f"Filigree: {filigree_count} accepted refit curve(s) sampled from the corridor stack. "
                        + (
                            f"Seed gate: {100.0 * seed_gate_kept_rate:.1f}% of fixed-d refits kept the incoming seed ({seed_gate_eval_count} evaluations). A high value means the corridor, especially in k, may stay close to the nominal branch because alternative local refits did not beat the spectral seed. "
                            if np.isfinite(seed_gate_kept_rate) and seed_gate_eval_count > 0
                            else ""
                        )
                        + "Each accepted refit can still be spline-smooth; visible kinks in the shaded envelope simply mark where the active lower/upper branch switches between different accepted refits once viewed in log10(k). "
                        + (
                            f"A minimum linear-k corridor half-width of +/-{k_min_hw:.1e} is enforced around the reference k when needed "
                            f"(adjusted points: {k_min_pts}). "
                            if np.isfinite(k_min_hw) and k_min_hw > 0.0
                            else ""
                        )
                        + "Dashed orange (if shown): center-d refit when it differs from the bold line. "
                        + "Crosshair y follows the bold curve at the cursor lambda when possible."
                    )
                )

            else:
                self.plot_k_corridor.setToolTip("")

        except (AttributeError, RuntimeError):
            self.logger.debug("Corridor plot title set failed", exc_info=True)

        # Dynamic Y-axis limits (user request: ymin=floor, ymax=ceil for n; ymax=1e-2 for k)
        try:
            # n corridor scale
            yn_all_f = np.concatenate([np.asarray(arr).ravel() for arr in y_n_all])
            yn_all_f = yn_all_f[np.isfinite(yn_all_f)]
            if yn_all_f.size > 0:
                yn_min, yn_max = float(np.min(yn_all_f)), float(np.max(yn_all_f))
                if yn_max > yn_min:
                    # n: strictly bound by the data range
                    self.plot_n_corridor.setYRange(yn_min, yn_max, padding=0)
                else:
                    self.plot_n_corridor.autoRange()
            else:
                self.plot_n_corridor.autoRange()

            _apply_fixed_log_k_axis(self.plot_k_corridor)
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.plot_n_corridor.autoRange()
            _apply_fixed_log_k_axis(self.plot_k_corridor)

        if lam_s.size > 0:
            span_lo = float(np.nanmin(lam_s))

            span_hi = float(np.nanmax(lam_s))

            if np.isfinite(span_lo) and np.isfinite(span_hi) and span_hi > span_lo:
                pad = 0.02 * (span_hi - span_lo)

                self.plot_n_corridor.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

                self.plot_k_corridor.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

        if has_profile or has_boot:
            if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_corridor"):
                self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor))

    def _build_corridor_tab_rmse_controls(self, lay_rmse: "QVBoxLayout") -> None:
        lay_rmse.setSpacing(6)

        lbl_intro = QLabel("Step 1: recalculate the RMSE(d) grid, then generate the corridor from that result.")
        lbl_intro.setWordWrap(True)
        lbl_intro.setStyleSheet(CertusTheme.get_hint_text_style())
        lay_rmse.addWidget(lbl_intro)

        row_rob = QHBoxLayout()

        row_rob.addWidget(QLabel("Robust DeltaRMSE:"))

        self.sp_corridor_rmse_delta = QDoubleSpinBox()

        self.sp_corridor_rmse_delta.setDecimals(6)

        self.sp_corridor_rmse_delta.setRange(1e-6, 0.01)

        self.sp_corridor_rmse_delta.setSingleStep(1e-5)

        self.sp_corridor_rmse_delta.setValue(2e-4)

        self.sp_corridor_rmse_delta.setToolTip(
            "<b>Amplitude DeltaRMSE (Profilage Robuste)</b><br>"
            "Target RMSE increment above minimum (d*) to define robust interval (Purple).<br>"
            "A lower value narrows the interval; a higher value widens it."
        )

        row_rob.addWidget(self.sp_corridor_rmse_delta)

        row_rob.addWidget(QLabel("Local half-window (points):"))

        self.sp_corridor_rmse_win = QSpinBox()

        self.sp_corridor_rmse_win.setRange(2, 8)

        self.sp_corridor_rmse_win.setValue(4)

        self.sp_corridor_rmse_win.setToolTip(
            "<b>Demi-fen?tre locale (points)</b><br>"
            "Number of points on each side of d* used to fit the local parabola.<br>"
            "A wider window smooths numerical noise but can capture non-parabolic regions."
        )

        row_rob.addWidget(self.sp_corridor_rmse_win)

        row_rob.addStretch(1)

        row_grid = QHBoxLayout()

        row_grid.addWidget(QLabel("Recalc grid: Deltad (nm)"))

        self.sp_corridor_grid_d_step_nm = QDoubleSpinBox()

        self.sp_corridor_grid_d_step_nm.setDecimals(4)

        self.sp_corridor_grid_d_step_nm.setRange(1e-4, 500.0)

        self.sp_corridor_grid_d_step_nm.setSingleStep(0.05)

        self.sp_corridor_grid_d_step_nm.setToolTip(
            "<b>Sampling step (nm)</b><br>"
            "Fixed offset between each thickness d tested during regular scan.<br>"
            "<i>Tip:</i> A step of 0.1 to 0.5 nm is generally sufficient for a good definition of the parabola."
        )
        self.sp_corridor_grid_d_step_nm.setValue(0.5)

        row_grid.addWidget(self.sp_corridor_grid_d_step_nm)

        row_grid.addWidget(QLabel("Points"))

        self.sp_corridor_grid_n_points = QSpinBox()

        self.sp_corridor_grid_n_points.setRange(2, 999)

        self.sp_corridor_grid_n_points.setValue(11)

        self.sp_corridor_grid_n_points.setToolTip(
            "<b>Total points (Scan)</b><br>"
            "Defines the total grid span (2 to N points around d*).<br>"
            "Allows broadening the search area for RMSE(d)."
        )

        row_grid.addWidget(self.sp_corridor_grid_n_points)

        self.btn_corridor_rmse_grid_calc = create_styled_button("Recalculate RMSE(d)", "primary", parent=self)

        self.btn_corridor_rmse_grid_calc.setToolTip(
            "<b>Full recalculation of the RMSE(d) grid</b><br>"
            "Rerun the optimization (n, ln k) for each thickness in the regular grid.<br>"
            "Uses a <b>continuation (warmstart)</b> and <b>P0 re-pass</b> mechanism to guarantee "
            "the exploration of the optimal physical solution."
        )

        self.btn_corridor_rmse_grid_calc.clicked.connect(self._start_corridor_rmse_grid_recalc)

        row_grid.addWidget(self.btn_corridor_rmse_grid_calc)

        self.btn_corridor_rmse_export_data = create_styled_button("Export data", "secondary", parent=self)

        self.btn_corridor_rmse_export_data.setToolTip(
            "<b>Export data (clipboard)</b><br>"
            "Copies all numeric columns (d, RMSE, Parabola, Intervals, Breakpoints) to TSV format.<br>"
            "Directly pasteable into Excel or OriginPro for external analysis."
        )

        self.btn_corridor_rmse_export_data.clicked.connect(self._export_corridor_rmse_profile_clipboard)

        row_grid.addWidget(self.btn_corridor_rmse_export_data)

        self.btn_corridor_rmse_export_envelope_nk = create_styled_button(
            "Export enveloppe n/k",
            "secondary",
            parent=self,
        )

        self.btn_corridor_rmse_export_envelope_nk.setToolTip(
            "Export an Excel file (.xlsx) with two sheets (n, k), on lambda grids 2/5/10 nm, for RMSE(d) envelope points."
        )

        self.btn_corridor_rmse_export_envelope_nk.clicked.connect(self._export_corridor_rmse_envelope_nk_excel)

        row_grid.addWidget(self.btn_corridor_rmse_export_envelope_nk)

        self.btn_corridor_generate_from_grid = create_styled_button(
            "Generate corridor from full grid", "primary", parent=self
        )

        self.btn_corridor_generate_from_grid.setEnabled(False)

        self.btn_corridor_generate_from_grid.setToolTip(
            "Build corridor n/k directly from the full RMSE(d) grid currently displayed."
        )

        self.btn_corridor_generate_from_grid.clicked.connect(self._generate_corridor_from_current_grid)

        row_grid.addStretch(1)

        lay_rmse.addLayout(row_grid)

        lbl_generate = QLabel(
            "Step 2: generate the corridor from the full grid, a partial grid, or the automatic smart interval."
        )
        lbl_generate.setWordWrap(True)
        lbl_generate.setStyleSheet(CertusTheme.get_hint_text_style())
        lay_rmse.addWidget(lbl_generate)

        row_generate_grid = QHBoxLayout()
        row_generate_grid.addWidget(self.btn_corridor_generate_from_grid)

        row_generate_grid.addWidget(QLabel("Corridor delta d (+/- nm):"))

        self.sp_corridor_partial_delta_nm = QDoubleSpinBox()
        self.sp_corridor_partial_delta_nm.setDecimals(4)
        self.sp_corridor_partial_delta_nm.setRange(1e-4, 500.0)
        self.sp_corridor_partial_delta_nm.setSingleStep(0.05)
        self.sp_corridor_partial_delta_nm.setValue(2.0)
        self.sp_corridor_partial_delta_nm.setToolTip(
            "Half-width used by 'Generate corridor from partial grid'.\n"
            "Interval = [d_center - Deltad, d_center + Deltad], where d_center is the current RMSE(d) center "
            "(parabolic center if available, else best sampled d*)."
        )
        row_generate_grid.addWidget(self.sp_corridor_partial_delta_nm)

        self.btn_corridor_generate_from_partial_grid = create_styled_button(
            "Generate corridor from partial grid", "primary", parent=self
        )
        self.btn_corridor_generate_from_partial_grid.setEnabled(False)
        self.btn_corridor_generate_from_partial_grid.setToolTip(
            "Build corridor n/k from a partial RMSE(d) grid centered on current d*.\n"
            "The width is controlled by Corridor Delta d (+/- nm)."
        )
        self.btn_corridor_generate_from_partial_grid.clicked.connect(self._generate_corridor_from_partial_grid)
        row_generate_grid.addWidget(self.btn_corridor_generate_from_partial_grid)

        self.btn_corridor_generate_auto_smart_grid = create_styled_button(
            "Calculate auto smart corridor from this grid", "primary", parent=self
        )
        self.btn_corridor_generate_auto_smart_grid.setEnabled(False)
        self.btn_corridor_generate_auto_smart_grid.setToolTip(
            "Automatically derive the smart interval from current RMSE(d) grid, "
            "then generate and apply corridor n/k on that interval.\n"
            "Priority: Deltad code interval (orange lines), fallback: robust parabolic interval."
        )
        self.btn_corridor_generate_auto_smart_grid.clicked.connect(self._generate_corridor_auto_smart_from_current_grid)
        row_generate_grid.addWidget(self.btn_corridor_generate_auto_smart_grid)
        row_generate_grid.addStretch(1)

        lay_rmse.addLayout(row_generate_grid)

        row_grid_prog = QHBoxLayout()

        self.pb_corridor_rmse_grid = EnhancedProgressWidget(main_label="RMSE Grid Calculation")
        self.pb_corridor_rmse_grid.setToolTip(
            "<b>Scan progress</b><br>"
            "Real-time progression including continuation steps, "
            "P0 re-pass, and breakpoint detection."
        )

        row_grid_prog.addWidget(self.pb_corridor_rmse_grid, 1)

        self.lbl_corridor_rmse_grid_progress = QLabel("Grid idle.")

        self.lbl_corridor_rmse_grid_progress.setStyleSheet(CertusTheme.get_hint_text_style())

        row_grid_prog.addWidget(self.lbl_corridor_rmse_grid_progress)

        lay_rmse.addLayout(row_grid_prog)

        self.chk_corridor_rmse_show_advanced = QCheckBox("Show advanced settings")

        self.chk_corridor_rmse_show_advanced.setChecked(False)

        lay_rmse.addWidget(self.chk_corridor_rmse_show_advanced)

        self.w_corridor_rmse_advanced = QWidget()

        lay_adv = QVBoxLayout(self.w_corridor_rmse_advanced)

        lay_adv.setContentsMargins(0, 0, 0, 0)

        lay_adv.addLayout(row_rob)

        row_break = QHBoxLayout()

        row_break.addWidget(QLabel("Breakpoint lookback (points):"))

        self.sp_corridor_breakpoint_lookback = QSpinBox()

        self.sp_corridor_breakpoint_lookback.setRange(2, 50)

        self.sp_corridor_breakpoint_lookback.setValue(5)

        self.sp_corridor_breakpoint_lookback.setToolTip(
            "Declare a breakpoint if current RMSE is better than the best RMSE among the previous N points on the same side."
        )

        row_break.addWidget(self.sp_corridor_breakpoint_lookback)

        row_break.addStretch(1)

        lay_adv.addLayout(row_break)

        row_adv_toggles = QHBoxLayout()

        self.chk_corridor_rmse_live_parabola = QCheckBox("Live parabola/robust fit")

        self.chk_corridor_rmse_live_parabola.setChecked(True)

        self.chk_corridor_rmse_live_parabola.setToolTip(
            "If disabled during live grid calculation: update RMSE points only; parabola/robust interval are recomputed at completion."
        )

        row_adv_toggles.addWidget(self.chk_corridor_rmse_live_parabola)

        self.chk_corridor_rmse_lock_scale = QCheckBox("Lock scale")
        self.chk_corridor_rmse_lock_scale.setChecked(True)
        self.chk_corridor_rmse_lock_scale.setToolTip(
            "<b>Scale Stabilization (Live)</b><br>"
            "Maintains the chart axes on the min/max bounds of current data.<br>"
            "This avoids visual jumps (flicker) during live grid calculation."
        )

        self.chk_corridor_rmse_lock_scale.toggled.connect(self._on_corridor_rmse_lock_scale_toggled)

        row_adv_toggles.addWidget(self.chk_corridor_rmse_lock_scale)

        self.chk_corridor_rmse_envelope_only = QCheckBox("Lower envelope only (final)")
        self.chk_corridor_rmse_envelope_only.setChecked(False)
        self.chk_corridor_rmse_envelope_only.setToolTip(
            "<b>Lower Envelope (Profile Likelihood)</b><br>"
            "Once the calculation is finished, only keeps the best RMSE for each thickness d.<br>"
            "<i>Useful for:</i> hiding points converged to local minima (RMSE peaks) "
            "and keeping only the 'true' physical valley necessary for corridor calculation."
        )

        self.chk_corridor_rmse_envelope_only.toggled.connect(self._refresh_corridor_rmse_robust_view)

        row_adv_toggles.addWidget(self.chk_corridor_rmse_envelope_only)

        row_adv_toggles.addStretch(1)

        lay_adv.addLayout(row_adv_toggles)

        self.w_corridor_rmse_advanced.setVisible(False)

        self.chk_corridor_rmse_show_advanced.toggled.connect(self.w_corridor_rmse_advanced.setVisible)

        lay_rmse.addWidget(self.w_corridor_rmse_advanced)

    def _start_corridor_rmse_grid_recalc(self) -> None:
        """Recalculate RMSE(d) on a regular grid (refit n,L with fixed d) in a thread."""

        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.info("GUI RMSE(d) regular grid | request ignored: worker already running")

            QMessageBox.information(self, "Calculate", "A worker is already running (wait or Stop).")

            return

        cfg = self._last_run_cfg

        if cfg is None:
            cfg = self._build_opt_config(notify=False)

        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no optimization configuration available")

            QMessageBox.warning(self, "Calculate", "No optimization configuration available (run a fit first).")

            return

        base = self._corridor_profile_source_result()

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Fallback: some display snapshots (best-live merge / stripped payloads)
            # can miss solver mesh fields needed by RMSE(d) fixed-d refits.
            base_fallback_src = ""
            for src_name, cand in (
                ("corridor_rmse_base_snapshot", self._corridor_rmse_base_snapshot),
                ("last_worker_result", self._last_worker_result),
                ("last_result", self._last_result),
                ("best_live_result", self._best_live_result),
            ):
                if isinstance(cand, dict) and cand.get("sigma_knots") is not None:
                    base = dict(cand)
                    base_fallback_src = str(src_name)
                    break
            if base_fallback_src and self.logger:
                self.logger.info(
                    "GUI RMSE(d) regular grid | base snapshot fallback selected from %s",
                    base_fallback_src,
                )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Last chance: rebuild a valid solver snapshot on canonical mesh, silently.
            base_seed: dict[str, Any] = {}
            for cand in (self._last_worker_result, self._last_result, self._best_live_result):
                if isinstance(cand, dict):
                    base_seed = dict(cand)
                    break
            try:
                maxfun_recover = int(max(300, min(4000, int(getattr(cfg, "polish_maxfun", 1200) or 1200))))
                rebuilt = quick_pwlnk_refit_result_dict(cfg, base_seed, maxfun=maxfun_recover)
            except (TypeError, ValueError, RuntimeError, AttributeError):
                rebuilt = None
            if isinstance(rebuilt, dict) and rebuilt.get("sigma_knots") is not None:
                base = dict(rebuilt)
                self._corridor_rmse_base_snapshot = dict(rebuilt)
                if self.logger:
                    self.logger.info(
                        "GUI RMSE(d) regular grid | base snapshot auto-rebuilt (maxfun=%d, sigma_knots=%d)",
                        int(maxfun_recover),
                        int(np.asarray(base.get("sigma_knots", []), dtype=np.float64).size),
                    )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no corridor profile base in current result")

            # Keep the UX non-blocking: no popup for missing base, only status feedback.
            self.lbl_status.setText(
                "RMSE(d): base corridor unavailable (auto reconstruction impossible). Run a fit, then retry."
            )

            return

        self._corridor_rmse_base_snapshot = dict(base)

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size > 0 and r_s.size == d_s.size and 0 <= i_best < int(d_s.size):
            d_center = float(d_s[i_best])

        else:
            d_center = float(base.get("d_nm", float("nan")))

        if not np.isfinite(d_center):
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: cannot determine center d*")

            QMessageBox.warning(self, "Calculate", "Cannot determine center thickness d* for the grid.")

            return

        n_pts = int(self.sp_corridor_grid_n_points.value()) if hasattr(self, "sp_corridor_grid_n_points") else 11

        step = float(self.sp_corridor_grid_d_step_nm.value()) if hasattr(self, "sp_corridor_grid_d_step_nm") else 0.5

        break_lookback = (
            int(self.sp_corridor_breakpoint_lookback.value()) if hasattr(self, "sp_corridor_breakpoint_lookback") else 5
        )

        if n_pts < 2 or (not np.isfinite(step)) or step <= 0:
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid | aborted: invalid grid params n_pts=%s step=%s",
                    str(n_pts),
                    str(step),
                )

            QMessageBox.warning(self, "Calculate", "Invalid grid: need ?2 points and Deltad > 0.")

            return

        offs = (np.arange(n_pts, dtype=np.float64) - 0.5 * float(n_pts - 1)) * step

        d_grid = d_center + offs
        self._corridor_rmse_requested_grid = d_grid.copy()

        d_lo_grid = float(np.min(d_grid)) if d_grid.size else float("nan")

        d_hi_grid = float(np.max(d_grid)) if d_grid.size else float("nan")

        self.__class__._prepare_worker_restart(self)

        snap = dict(base)

        from certus.ui.certus_index_spline_ui import _worker_corridor_rmse_regular_grid
        self._worker = GenericWorker(
            _worker_corridor_rmse_regular_grid,
            cfg,
            snap,
            d_grid,
            self._stop_event,
            int(max(2, break_lookback)),
        )

        def _grid_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress_snapshot.emit(build_progress_snapshot(message=m, display_ratio=max(0.0, min(1.0, pv / 10000.0)), progress_ratio=max(0.0, min(1.0, pv / 10000.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='INDEX_SPLINE', phase='CORRIDORS', metadata={'pv': pv}))

        self._worker.kwargs["progress_cb"] = _grid_progress

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.kwargs["visit_anchor_nm"] = float(d_center)

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self._worker_role = "rmse_grid"

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._set_corridor_grid_busy(True)

        self._corridor_rmse_grid_live_t0 = float(time.perf_counter())
        self._corridor_rmse_live_last_plot_ts = float("nan")

        self._set_corridor_grid_progress_ui(done=0, total=int(max(1, d_grid.size)))

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText(
            f"RMSE(d) grid: {n_pts} points, Deltad={step:g} nm, break-lookback={int(max(2, break_lookback))} "
            f"(center d*?{d_center:.3f} nm)..."
        )

        if self.logger:
            bd_raw = base.get("d_nm")
            bd_txt = (
                f"{float(bd_raw):.6f}" if isinstance(bd_raw, (int, float)) and np.isfinite(float(bd_raw)) else "n/a"
            )
            br = self._rmse_from_result_dict(base)
            br_txt = f"{br:.8f}" if np.isfinite(br) else "n/a"
            sbv = base.get("spectral_rmse_best_value")
            sbv_txt = f"{float(sbv):.8f}" if sbv is not None and np.isfinite(float(sbv)) else "n/a"
            if (
                d_s.size > 0
                and r_s.size == d_s.size
                and 0 <= i_best < int(d_s.size)
                and np.isfinite(float(r_s[i_best]))
            ):
                center_src = f"rmse_tab_best_idx={i_best}"
                tab_d = f"{float(d_s[i_best]):.6f}"
                tab_r = f"{float(r_s[i_best]):.8f}"
            else:
                center_src = "base_dict_d_nm"
                tab_d = "n/a"
                tab_r = "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | start | center=%.6f nm | n_pts=%d | step=%.6f nm | d_range=[%.6f, %.6f] nm | "
                "base_d_nm=%s | base_rmse_dict=%s | spectral_rmse_best_value=%s | center_src=%s | tab(d,rmse)=(%s,%s)",
                float(d_center),
                int(n_pts),
                float(step),
                float(d_lo_grid),
                float(d_hi_grid),
                bd_txt,
                br_txt,
                sbv_txt,
                center_src,
                tab_d,
                tab_r,
            )

        # Auto-select the Corridor RMSE(d) tab to show live updates
        if hasattr(self, "_idx_tab_corridor_rmse") and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor_rmse))

        self._worker.start()

class _DataMixin:
    """Mixin containing data table and nk data preparation methods."""

    def _prepare_nk_data_tab_series(
        self, r: dict[str, Any]
    ) -> (
        tuple[
            np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
        ]
        | None
    ):
        """n/k series (and NL, envelopes) interpolated on piecewise lambda grid."""

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data tab n/k: missing lam_nm in result; fallback to experimental lambda grid.")
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()

        n_ = np.asarray(r["n_lam"], dtype=np.float64).ravel()

        k_ = np.asarray(r["k_lam"], dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_.size, k_.size))

        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")

        ls = lam[:m0][order]

        ns = n_[:m0][order]

        ks = k_[:m0][order]

        fg = np.isfinite(ls)

        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))

        hi = float(np.nanmax(ls[fg]))

        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)

        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, ns, left=np.nan, right=np.nan)

        k_g = np.interp(lam_g, ls, ks, left=np.nan, right=np.nan)

        m = m0

        lam_full = lam[:m0]

        n_lo_g = np.full_like(lam_g, np.nan)

        n_hi_g = np.full_like(lam_g, np.nan)

        k_lo_g = np.full_like(lam_g, np.nan)

        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(r.get("profile_d_enabled", False)) or bool(r.get("manual_corridor_active", False)):
            cn_lo = np.asarray(r.get("corridor_n_lo", []), dtype=np.float64).ravel()

            cn_hi = np.asarray(r.get("corridor_n_hi", []), dtype=np.float64).ravel()

            ck_lo = np.asarray(r.get("corridor_k_lo", []), dtype=np.float64).ravel()

            ck_hi = np.asarray(r.get("corridor_k_hi", []), dtype=np.float64).ravel()

            lsz = lam_full.size

            if cn_lo.size == lsz and cn_hi.size == lsz and ck_lo.size == lsz and ck_hi.size == lsz:
                n_lo_g = np.interp(lam_g, ls, cn_lo[:m][order], left=np.nan, right=np.nan)

                n_hi_g = np.interp(lam_g, ls, cn_hi[:m][order], left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, ls, ck_lo[:m][order], left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, ls, ck_hi[:m][order], left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots and Detailed Corridor Tab
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        return (lam_g, n_g, k_g, n_lo_g, n_hi_g, k_lo_g, k_hi_g)

    def _prepare_data_th_tab_series(
        self, r: dict[str, Any]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data TH: missing lam_nm in result; fallback to experimental lambda grid.")

        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        n_src = np.asarray(r.get("n_lam", []), dtype=np.float64).ravel()
        k_src = np.asarray(r.get("k_lam", []), dtype=np.float64).ravel()
        t_src = np.asarray(r.get("t_theo", []), dtype=np.float64).ravel()
        r_src = np.asarray(r.get("r_theo", []), dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_src.size, k_src.size))
        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")
        ls = lam[:m0][order]
        n_s = n_src[:m0][order]
        k_s = k_src[:m0][order]

        fg = np.isfinite(ls)
        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))
        hi = float(np.nanmax(ls[fg]))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, n_s, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, ls, k_s, left=np.nan, right=np.nan)

        t_g = np.full_like(lam_g, np.nan)
        if t_src.size >= m0:
            t_s = t_src[:m0][order]
            t_g = np.interp(lam_g, ls, t_s, left=np.nan, right=np.nan)

        r_g = np.full_like(lam_g, np.nan)
        if r_src.size >= m0:
            r_s = r_src[:m0][order]
            r_g = np.interp(lam_g, ls, r_s, left=np.nan, right=np.nan)

        ns_g = np.full_like(lam_g, np.nan)
        ns_src = np.asarray(r.get("n_sub_effective", []), dtype=np.float64).ravel()
        if ns_src.size >= m0:
            ns_s = ns_src[:m0][order]
            ns_g = np.interp(lam_g, ls, ns_s, left=np.nan, right=np.nan)
        else:
            try:
                sub_name = str(
                    r.get("substrate_name")
                    or getattr(self, "sub_name", "")
                    or (
                        self.cb_sub.currentData()
                        if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                        else ""
                    )
                )
                sid = substrate_id_from_name(sub_name)
                ns_raw = np.asarray(_get_substrate_n_array_spline(sid, lam_g), dtype=np.float64).ravel()
                if ns_raw.size == lam_g.size:
                    ns_g = ns_raw
            except NUMERICAL_FAULT_EXCEPTIONS:
                if self.logger:
                    self.self.logger.debug("Data TH substrate ns build failed", exc_info=True)
            except (TypeError, ValueError):
                if self.logger:
                    self.self.logger.debug("Data TH substrate lookup failed", exc_info=True)

        d_nm = float(r.get("d_nm", float("nan")))
        d_g = np.full_like(lam_g, d_nm, dtype=np.float64)

        return (lam_g, n_g, k_g, d_g, ns_g, t_g, r_g)

    def _baseline_substrate_n_for_result(
        self,
        result: dict,
        *,
        lam_override: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray] | None:

        lam_src = lam_override if lam_override is not None else result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        if lam.size == 0:
            return None

        sub_name = str(
            result.get("substrate_name")
            or getattr(self, "sub_name", "")
            or (
                self.cb_sub.currentData()
                if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                else ""
            )
        )
        sid = substrate_id_from_name(sub_name)
        n_sub = np.asarray(_get_substrate_n_array_spline(sid, lam), dtype=np.float64).ravel()
        if n_sub.size != lam.size:
            return None
        return lam.copy(), n_sub.copy()

    @staticmethod
    def _decorate_result_with_substrate_offset(
        result: dict,
        *,
        n_sub_base: np.ndarray,
        delta_ns: float,
    ) -> dict:

        out = dict(result)
        base = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()
        out["n_sub_base"] = base
        out["substrate_n_offset"] = float(delta_ns)
        out["n_sub_effective"] = base + float(delta_ns)
        return out

    @staticmethod
    def _cfg_with_result_substrate(cfg_base: SplineOptConfig, result: dict) -> SplineOptConfig:

        n_eff = np.asarray(result.get("n_sub_effective", []), dtype=np.float64).ravel()
        lam_cfg = np.asarray(getattr(cfg_base, "lam_nm", []), dtype=np.float64).ravel()
        if lam_cfg.size and n_eff.size == lam_cfg.size:
            n_base = np.asarray(result.get("n_sub_base", []), dtype=np.float64).ravel()
            if n_base.size != lam_cfg.size:
                n_base = n_eff.copy()
            return cfg_base.replace(
                n_sub=n_eff.copy(),
                substrate_n_base=n_base.copy(),
                substrate_n_offset=float(result.get("substrate_n_offset", 0.0)),
            )
        return cfg_base

    def _apply_manual_substrate_offset_preview(self, seed_result: dict, delta_ns: float) -> bool:

        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return False

        lam_preview = np.asarray(seed_result.get("lam_nm", getattr(cfg_base, "lam_nm", [])), dtype=np.float64).ravel()
        baseline_payload = self._baseline_substrate_n_for_result(seed_result, lam_override=lam_preview)
        if baseline_payload is None:
            return False
        _, n_sub_base = baseline_payload

        preview = self._decorate_result_with_substrate_offset(
            seed_result,
            n_sub_base=n_sub_base,
            delta_ns=float(delta_ns),
        )
        cfg_preview = cfg_base.replace(
            n_sub=np.asarray(preview["n_sub_effective"], dtype=np.float64).ravel().copy(),
            substrate_n_base=np.asarray(preview["n_sub_base"], dtype=np.float64).ravel().copy(),
            substrate_n_offset=float(delta_ns),
        )
        _sync_theoretical_tr_from_nk_dict(
            cfg_preview,
            preview,
            log=self.logger,
            reason="manual_delta_ns_preview",
        )
        try:
            mse_preview, rmse_preview = spectral_mse_rmse_masked_from_nk(
                cfg_preview,
                preview,
                np.asarray(preview.get("lam_nm", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("n_lam", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("k_lam", []), dtype=np.float64).ravel(),
                float(preview.get("d_nm", float("nan"))),
            )
            if np.isfinite(mse_preview):
                preview["mse"] = float(mse_preview)
            if np.isfinite(rmse_preview):
                preview["rmse"] = float(rmse_preview)
        except (TypeError, ValueError, RuntimeError):
            if self.logger:
                self.self.logger.debug("Manual delta-ns preview RMSE recompute failed", exc_info=True)

        self._last_worker_result = dict(preview)
        self._last_result = dict(preview)
        self._plot_result(preview, plot_source="manual_delta_ns_preview")
        self._refresh_data_table(result_override=preview)
        self.lbl_status.setText(
            self._post_optimization_ready_status(
                self._format_post_optimization_status(preview, preview)
            )
        )
        return True

    def _refresh_manual_dialog_preview(self, dialog: ManualSigmaKnotDialog | None, preview_result: dict | None) -> None:

        if not isinstance(dialog, ManualSigmaKnotDialog) or not isinstance(preview_result, dict):
            return
        lam_preview = np.asarray(preview_result.get("lam_nm", []), dtype=np.float64).ravel()
        y_preview = np.empty(0, dtype=np.float64)
        t_val = preview_result.get("t_theo")
        if t_val is not None:
            y_preview = np.asarray(t_val, dtype=np.float64).ravel()
        if y_preview.size == 0:
            r_val = preview_result.get("r_theo")
            if r_val is not None:
                y_preview = np.asarray(r_val, dtype=np.float64).ravel()
        dialog.update_model_preview(lam_preview, y_preview)
        d_preview, rmse_preview = self._runtime_metrics_from_result_dict(preview_result)
        dialog.set_runtime_metrics(d_preview, rmse_preview)

    def _copy_nk_to_clipboard(self) -> None:

        if self._last_result is None:
            QMessageBox.information(self, "Clipboard", "Run an optimization first.")

            return

        r = self._last_result

        ser = self._prepare_nk_data_tab_series(r)

        if ser is None:
            QMessageBox.information(self, "Clipboard", "Empty grid.")

            return

        (
            lam_g,
            n_g,
            k_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        hdr = "lambda_nm\tn\tn_envelope_min\tn_envelope_max\tk\tk_envelope_min\tk_envelope_max"

        lines = [hdr]

        m = int(lam_g.size)

        for i in range(m):
            row = f"{float(lam_g[i]):.4f}\t"

            row += self._fmt_n_data_tab(float(n_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_lo_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_hi_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_lo_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_hi_g[i]))

            lines.append(row)

        cb = QApplication.clipboard()

        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")

            return

        cb.setText("\n".join(lines))

        self.lbl_status.setText("Data table copied (TSV).")

        self.btn_copy_nk.setText(" Copied!")

        QTimer.singleShot(1800, lambda: self.btn_copy_nk.setText("Copy full table (TSV)"))

    def _copy_data_th_to_clipboard(self) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        if t.rowCount() <= 0 or t.columnCount() <= 0:
            QMessageBox.information(self, "Clipboard", "Data TH empty.")
            return

        headers = [
            t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(t.columnCount())
        ]
        lines = ["\t".join(headers)]

        for r in range(t.rowCount()):
            row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())]
            lines.append("\t".join(row))

        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText("\n".join(lines))
        self.lbl_status.setText("Data TH copied (TSV).")

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setText(" Copied!")
            QTimer.singleShot(
                1800,
                lambda: self.btn_copy_data_th.setText("Copy Data TH table (TSV)"),
            )

    def _on_data_preview_plot_mouse_moved(
        self,
        src: CertusScientificPlot,
        pos: Any,
        x: float,
        y: float,
        y_show: Any,
    ) -> None:
        """Synchronizes both previews (lambda) and tooltip with all interpolated n and k."""

        del pos, y_show

        s = getattr(self, "_data_preview_series", None)

        if not isinstance(s, dict):
            return

        pn = self.plot_data_preview_n

        pk = self.plot_data_preview_k

        lam = s.get("lam")

        if lam is None:
            return

        lam_a = np.asarray(lam, dtype=np.float64).ravel()

        def _fmt_nq(v: float) -> str:

            return self._fmt_n_data_tab(v) if np.isfinite(v) else "-"

        def _fmt_kq(v: float) -> str:

            if not np.isfinite(v) or v < 0:
                return "-"

            return self._fmt_k_data_tab(float(v))

        n_at = self._interp_preview_axis(lam_a, s["n"], x)

        nlo_at = self._interp_preview_axis(lam_a, s["n_lo"], x)

        nhi_at = self._interp_preview_axis(lam_a, s["n_hi"], x)

        k_at = self._interp_preview_axis(lam_a, s["k"], x)

        klo_at = self._interp_preview_axis(lam_a, s["k_lo"], x)

        khi_at = self._interp_preview_axis(lam_a, s["k_hi"], x)

        lam_txt = float(x)

        txt = (
            f"lambda = {lam_txt:.2f} nm\n"
            f"n={_fmt_nq(n_at)}  n_min={_fmt_nq(nlo_at)}  n_max={_fmt_nq(nhi_at)}\n"
            f"k={_fmt_kq(k_at)}  k_min={_fmt_kq(klo_at)}  k_max={_fmt_kq(khi_at)}"
        )

        k_floor = float(s.get("k_floor", 1e-30))

        if not (np.isfinite(k_floor) and k_floor > 0.0):
            k_floor = 1e-30

        pn.vLine.setPos(x)

        pk.vLine.setPos(x)

        pn.hLine.setVisible(False)

        pk.hLine.setVisible(False)

        for w in (pn, pk):
            try:
                xr = w.plotItem.vb.viewRange()[0]

                x_lo, x_hi = float(xr[0]), float(xr[1])

                span = x_hi - x_lo

                if span > 0 and x > x_lo + 0.78 * span:
                    w.info_label.setAnchor((1, 1))

                else:
                    w.info_label.setAnchor((0, 1))

            except NUMERICAL_FAULT_EXCEPTIONS:
                w.info_label.setAnchor((0, 1))

        pn.info_label.setText(txt)

        pk.info_label.setText(txt)

        if src is pn:
            pn_y = float(y)

            if np.isfinite(k_at) and float(k_at) > 0.0:
                pk_y = float(k_at)

            elif np.isfinite(k_at) and float(k_at) == 0.0:
                pk_y = k_floor

            else:
                pk_y = self._vb_mid_y_plot(pk)

        else:
            pk_y = float(y)

            pn_y = float(n_at) if np.isfinite(n_at) else self._vb_mid_y_plot(pn)

        pn.info_label.setPos(x, pn_y)

        pk.info_label.setPos(x, pk_y)

    def _refresh_data_table(self, result_override: dict | None = None) -> None:

        if not hasattr(self, "table_nk"):
            return

        t = self.table_nk

        t.setRowCount(0)

        result_eff = result_override if isinstance(result_override, dict) else self._last_result

        if result_eff is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=None)

            return

        ser = self._prepare_nk_data_tab_series(result_eff)

        if ser is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=result_eff)

            return

        (
            lam_g,
            n_g,
            k_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        t.setColumnCount(7)

        t.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n env min",
                "n env max",
                "k",
                "k env min",
                "k env max",
            ]
        )

        t.setRowCount(m)

        n_valid = 0

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))

            if np.isfinite(n_g[i]) and np.isfinite(k_g[i]) and float(k_g[i]) >= 0.0:
                n_valid += 1

            t.setItem(i, 1, _cell_n(float(n_g[i])))

            t.setItem(i, 2, _cell_n(float(n_lo_g[i])))

            t.setItem(i, 3, _cell_n(float(n_hi_g[i])))

            t.setItem(i, 4, _cell_k(float(k_g[i])))

            t.setItem(i, 5, _cell_k(float(k_lo_g[i])))

            t.setItem(i, 6, _cell_k(float(k_hi_g[i])))

        self.btn_copy_nk.setEnabled(m > 0 and n_valid > 0)

        self.btn_export_nk.setEnabled(m > 0 and n_valid > 0)

        self._refresh_data_preview_plots(ser=ser)
        self._refresh_data_th_table(result_eff=result_eff)
        self._refresh_corridor_table(result_eff)

    def _refresh_data_th_table(self, result_eff: dict | None) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        t.setRowCount(0)

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(False)

        if not isinstance(result_eff, dict):
            return

        ser = self._prepare_data_th_tab_series(result_eff)
        if ser is None:
            return

        lam_g, n_g, k_g, d_g, ns_g, t_g, r_g = ser

        m = int(lam_g.size)
        t.setColumnCount(7)
        t.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
        t.setRowCount(m)

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        def _cell_lin(x: float, fmt: str = ".6f") -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(f"{float(x):{fmt}}")

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))
            t.setItem(i, 1, _cell_n(float(n_g[i])))
            t.setItem(i, 2, _cell_k(float(k_g[i])))
            t.setItem(i, 3, _cell_lin(float(d_g[i]), ".4f"))
            t.setItem(i, 4, _cell_n(float(ns_g[i])))
            t.setItem(i, 5, _cell_lin(float(t_g[i])))
            t.setItem(i, 6, _cell_lin(float(r_g[i])))

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(m > 0)

class _CorridorGenMixin:
    """Mixin containing corridor generation, application and table refresh methods."""

    def _on_corridor_rmse_grid_live_update(self, payload: object) -> None:
        """Display the RMSE(d) curve live during grid recalculation."""

        worker_role = str(getattr(self, "_worker_role", "") or "")
        if worker_role not in {"rmse_grid", "corridors"}:
            return

        if not isinstance(payload, dict):
            return

        d_live = np.asarray(payload.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        r_live = np.asarray(payload.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

        if d_live.size == 0 or r_live.size != d_live.size:
            return

        cur = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        upd = dict(cur)

        upd["profile_d_values_nm"] = d_live

        upd["profile_d_rmse_values"] = r_live

        k_live = np.asarray(payload.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
        if k_live.size == d_live.size:
            upd["profile_d_manual_grid_point_kind"] = k_live
        st_live = np.asarray(
            payload.get("profile_d_manual_grid_point_status_code", []),
            dtype=np.int32,
        ).ravel()
        if st_live.size == d_live.size:
            upd["profile_d_manual_grid_point_status_code"] = st_live

        upd["profile_d_status"] = str(payload.get("profile_d_status", "manual_grid_live"))

        upd["profile_d_manual_grid_progress"] = float(payload.get("profile_d_manual_grid_progress", float("nan")))

        upd["profile_d_manual_grid_done_points"] = int(payload.get("profile_d_manual_grid_done_points", d_live.size))

        upd["profile_d_manual_grid_total_points"] = int(payload.get("profile_d_manual_grid_total_points", d_live.size))
        upd["profile_d_manual_grid_base_done_points"] = int(
            payload.get("profile_d_manual_grid_base_done_points", upd["profile_d_manual_grid_done_points"])
        )
        upd["profile_d_manual_grid_extra_done_points"] = int(payload.get("profile_d_manual_grid_extra_done_points", 0))

        if "profile_d_manual_grid_breakpoint_events" in payload:
            upd["profile_d_manual_grid_breakpoint_events"] = payload.get("profile_d_manual_grid_breakpoint_events")

        self._last_result = upd

        n_done_payload = int(upd.get("profile_d_manual_grid_done_points", d_live.size))
        n_tot = int(upd.get("profile_d_manual_grid_total_points", d_live.size))
        p_live = float(upd.get("profile_d_manual_grid_progress", float("nan")))
        if np.isfinite(p_live):
            n_done = int(max(0, min(n_tot, round(float(p_live) * float(max(1, n_tot))))))
            n_done = max(n_done, min(1, n_done_payload))
        else:
            n_done = n_done_payload
        n_base_done = int(upd.get("profile_d_manual_grid_base_done_points", n_done))
        n_extra_done = int(upd.get("profile_d_manual_grid_extra_done_points", max(0, n_done - n_tot)))

        d_cur = float(payload.get("profile_d_manual_grid_current_d_nm", float("nan")))

        if worker_role == "rmse_grid":
            self._set_corridor_grid_progress_ui(
                done=n_done,
                total=n_tot,
                base_done=n_base_done,
                base_total=n_tot,
                extra_done=n_extra_done,
                current_d_nm=(d_cur if np.isfinite(d_cur) else None),
            )

        now_ts = float(time.perf_counter())
        last_ts = float(getattr(self, "_corridor_rmse_live_last_plot_ts", float("nan")))
        min_dt = float(getattr(self, "_corridor_rmse_live_plot_min_interval_s", 0.12) or 0.12)
        should_plot = (
            n_done <= 1 or n_done >= n_tot or (not np.isfinite(last_ts)) or ((now_ts - last_ts) >= max(0.02, min_dt))
        )
        if should_plot:
            try:
                self._plot_corridor_rmse_tab(upd)
                # Hard safety net: if live payload has finite points but plot pipeline
                # produced no visible data items, draw a minimal scatter fallback.
                if hasattr(self, "plot_corridor_rmse_d"):
                    plot_item = getattr(self.plot_corridor_rmse_d, "plotItem", None)
                    data_items = []
                    if plot_item is not None and hasattr(plot_item, "listDataItems"):
                        try:
                            data_items = list(plot_item.listDataItems())
                        except (TypeError, ValueError, RuntimeError, AttributeError):
                            data_items = []
                    if len(data_items) == 0:
                        m_live = np.isfinite(d_live) & np.isfinite(r_live)
                        if np.any(m_live):
                            d_fb = np.asarray(d_live[m_live], dtype=np.float64).ravel()
                            r_fb = np.asarray(r_live[m_live], dtype=np.float64).ravel()
                            self.plot_corridor_rmse_d.addItem(
                                pg.ScatterPlotItem(
                                    d_fb,
                                    r_fb,
                                    pen=pg.mkPen(CertusTheme.PRIMARY, width=0),
                                    brush=pg.mkBrush(0, 87, 255, 160),
                                    size=5,
                                    symbol="o",
                                    name="RMSE(d) live",
                                )
                            )
                            self._set_corridor_rmse_view_data_bounds(d_fb, r_fb)
                self._corridor_rmse_live_last_plot_ts = now_ts

            except NUMERICAL_FAULT_EXCEPTIONS:
                self.logger.debug("RMSE(d) live plot update failed", exc_info=True)

        if self.logger and (n_done <= 1 or n_done >= n_tot or (n_done % 5 == 0)):
            r_at_cur = float("nan")
            if np.isfinite(d_cur) and d_live.size and r_live.size == d_live.size:
                fg_l = np.isfinite(d_live) & np.isfinite(r_live)
                if np.any(fg_l):
                    dl = d_live[fg_l]
                    rl = r_live[fg_l]
                    j_nearest = int(np.argmin(np.abs(dl - float(d_cur))))
                    r_at_cur = float(rl[j_nearest])
            r_cur_txt = f"{r_at_cur:.8f}" if np.isfinite(r_at_cur) else "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | live | pts=%d | base %d/%d | extra_done=%d | current_d_nm=%s | rmse_at_nearest_curve_pt=%s",
                int(n_done),
                int(n_base_done),
                int(n_tot),
                int(n_extra_done),
                (f"{float(d_cur):.6f}" if np.isfinite(d_cur) else "n/a"),
                r_cur_txt,
            )

    def _build_manual_corridor_payload(
        self,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo_nm: float,
        d_hi_nm: float,
    ) -> dict[str, Any] | None:

        d_vals = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)

        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)

        if d_vals.size == 0 or n_curves.ndim != 2 or k_curves.ndim != 2:
            return None

        if n_curves.shape[0] != d_vals.size or k_curves.shape[0] != d_vals.size:
            return None

        if n_curves.shape[1] == 0 or k_curves.shape[1] != n_curves.shape[1]:
            return None

        d_lo = float(min(d_lo_nm, d_hi_nm))

        d_hi = float(max(d_lo_nm, d_hi_nm))

        sel = np.isfinite(d_vals) & (d_vals >= d_lo - 1e-12) & (d_vals <= d_hi + 1e-12)

        if not np.any(sel):
            i_near = int(np.argmin(np.abs(d_vals - 0.5 * (d_lo + d_hi))))

            sel = np.zeros_like(d_vals, dtype=bool)

            sel[i_near] = True

        n_pick = np.asarray(n_curves[sel, :], dtype=np.float64)

        k_pick = np.asarray(k_curves[sel, :], dtype=np.float64)

        if n_pick.ndim != 2 or k_pick.ndim != 2 or n_pick.shape[0] == 0:
            return None

        n_lo = np.nanmin(n_pick, axis=0)

        n_hi = np.nanmax(n_pick, axis=0)

        k_lo = np.nanmin(k_pick, axis=0)

        k_hi = np.nanmax(k_pick, axis=0)

        ref_n = np.asarray(source.get("corridor_reference_n_lam", display.get("n_lam", [])), dtype=np.float64).ravel()

        ref_k = np.asarray(source.get("corridor_reference_k_lam", display.get("k_lam", [])), dtype=np.float64).ravel()

        if ref_n.size == n_lo.size and ref_k.size == k_lo.size:
            n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
                n_lo,
                n_hi,
                k_lo,
                k_hi,
                ref_n,
                ref_k,
            )
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(ref_k, dtype=np.float64),
                min_half_width=1e-4,
            )
        else:
            k_ref_eff = 0.5 * (np.asarray(k_lo, dtype=np.float64) + np.asarray(k_hi, dtype=np.float64))
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(k_ref_eff, dtype=np.float64),
                min_half_width=1e-4,
            )

        d_sel = np.asarray(d_vals[sel], dtype=np.float64)

        if int(k_min_changed) > 0 and self.logger:
            self.logger.info(
                "GUI corridor payload | k-min-width enforced | half_width=1.0e-4 | adjusted_points=%d",
                int(k_min_changed),
            )

        return {
            "profile_d_enabled": True,
            "corridor_n_lo": np.asarray(n_lo, dtype=np.float64),
            "corridor_n_hi": np.asarray(n_hi, dtype=np.float64),
            "corridor_k_lo": np.asarray(k_lo, dtype=np.float64),
            "corridor_k_hi": np.asarray(k_hi, dtype=np.float64),
            "corridor_k_min_half_width": float(1e-4),
            "corridor_k_min_half_width_enforced_points": int(k_min_changed),
            "corridor_reference_n_lam": np.asarray(ref_n, dtype=np.float64),
            "corridor_reference_k_lam": np.asarray(ref_k, dtype=np.float64),
            "manual_corridor_active": True,
            "manual_corridor_interval_nm": (float(d_lo), float(d_hi)),
            "manual_corridor_selected_d_range_nm": (float(np.nanmin(d_sel)), float(np.nanmax(d_sel))),
            "manual_corridor_selected_count": int(d_sel.size),
        }

    def _apply_corridor_payload_from_interval(
        self,
        *,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo: float,
        d_hi: float,
        status_prefix: str,
    ) -> bool:

        payload = self._build_manual_corridor_payload(source, display, d_lo, d_hi)

        if payload is None:
            if self.logger:
                self.logger.warning(
                    "GUI corridor regenerate | failed payload build | requested_interval=[%.6f, %.6f] nm",
                    float(min(d_lo, d_hi)),
                    float(max(d_lo, d_hi)),
                )

            return False

        updated = dict(display)

        for k, v in source.items():
            if k.startswith("profile_d_") and k not in updated:
                updated[k] = v

        updated.update(payload)

        self._corridor_rmse_manual_active = True

        self._corridor_rmse_manual_lo = float(payload["manual_corridor_interval_nm"][0])

        self._corridor_rmse_manual_hi = float(payload["manual_corridor_interval_nm"][1])

        self._last_result = updated

        self._plot_result(updated, plot_source="corridor_rmse_manual")

        self._refresh_data_table()

        self._update_corridor_rmse_state_bar(updated)

        self.lbl_status.setText(
            f"{status_prefix} [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
        )

        if self.logger:
            self.logger.info(
                "GUI corridor regenerated | status_prefix=%s | requested_interval=[%.6f, %.6f] nm | selected_points=%d | sampled_selected_range=[%.6f, %.6f] nm",
                str(status_prefix),
                float(self._corridor_rmse_manual_lo),
                float(self._corridor_rmse_manual_hi),
                int(payload.get("manual_corridor_selected_count", 0)),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[0]),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[1]),
            )

        return True

    def _generate_corridor_from_partial_grid(self) -> None:
        """Generate n/k corridor from a centered partial RMSE(d) interval."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        r_s = r_s[m]
        if d_s.size == 0 or r_s.size != d_s.size:
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: empty finite RMSE(d) grid")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No valid finite RMSE(d) points are available.",
            )
            return

        d_best = float(d_s[int(np.argmin(r_s))])
        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))
        if not np.isfinite(d_center):
            d_center = d_best

        half = (
            float(self.sp_corridor_partial_delta_nm.value()) if hasattr(self, "sp_corridor_partial_delta_nm") else 2.0
        )
        if (not np.isfinite(half)) or half <= 0.0:
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Invalid Corridor Deltad: please set a positive finite value.",
            )
            return

        d_lo = float(d_center - half)
        d_hi = float(d_center + half)
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))
        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Partial interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(partial-grid) | request | center=%.6f nm | half=%.6f nm | clipped_interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from partial RMSE(d) grid on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Unable to generate n/k corridor from the selected partial grid interval.",
            )

    def _generate_corridor_auto_smart_from_current_grid(self) -> None:
        """Auto-compute and apply smart corridor interval from current RMSE(d) grid."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(auto-smart) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        # Ensure smart/robust interval state is up-to-date with current grid.
        try:
            self._refresh_corridor_rmse_robust_view()
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Auto-smart corridor: robust refresh failed", exc_info=True)

        d_lo = float("nan")
        d_hi = float("nan")
        interval_source = "none"

        smart_int = getattr(self, "_corridor_rmse_smart_interval", None)
        if (
            isinstance(smart_int, (tuple, list))
            and len(smart_int) >= 2
            and np.isfinite(float(smart_int[0]))
            and np.isfinite(float(smart_int[1]))
        ):
            d_lo = float(min(float(smart_int[0]), float(smart_int[1])))
            d_hi = float(max(float(smart_int[0]), float(smart_int[1])))
            interval_source = "smart_code_interval"
        elif bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))
            d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))
            if np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb > d_lo_rb:
                d_lo = float(d_lo_rb)
                d_hi = float(d_hi_rb)
                interval_source = "robust_parabolic_interval"

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        if d_s.size == 0:
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No valid finite RMSE(d) points are available.",
            )
            return
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))

        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval unavailable for current grid (no smart/robust interval found).",
            )
            return

        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(auto-smart) | request | source=%s | interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                str(interval_source),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix=f"auto smart corridor generated ({interval_source}) on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | failed | source=%s | interval=[%.6f, %.6f] nm",
                    str(interval_source),
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Unable to generate n/k corridor from auto smart interval.",
            )
            return

        # Keep interval highlighted explicitly as active manual interval (red lines)
        # in addition to smart/robust guide lines already shown on RMSE(d) chart.
        try:
            self._refresh_corridor_rmse_robust_view()
        except NUMERICAL_FAULT_EXCEPTIONS :
            self.logger.debug("Auto-smart corridor: post-apply robust refresh failed", exc_info=True)

    def _apply_manual_corridor_selection(self) -> None:

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: no corridor profile source/display")

            QMessageBox.information(self, "Generate corridor", "No corridor profile is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: invalid RMSE(d) profile or best index")

            QMessageBox.information(self, "Generate corridor", "No valid RMSE(d) profile is available.")

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        half = self._corridor_manual_half_width_nm()

        d_lo = float(d_center - half)

        d_hi = float(d_center + half)

        if self.logger:
            self.logger.info(
                "GUI generate corridor(manual) | request | center=%.6f nm | half=%.6f nm | interval=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="Manual corridor regenerated on",
        )

        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(manual) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )

            QMessageBox.warning(self, "Generate corridor", "Unable to rebuild a manual corridor from this interval.")

    def _refresh_corridor_table(self, result: dict) -> None:
        """Populates the detailed data corridor table with smart interpolation."""
        if not hasattr(self, "table_corridor"):
            return

        t = self.table_corridor
        t.setRowCount(0)

        lam_src = result.get("lam_nm")
        n_src = result.get("n_lam")
        k_src = result.get("k_lam")

        if lam_src is None or n_src is None or k_src is None:
            self.btn_copy_corridor.setEnabled(False)
            self.btn_export_corridor.setEnabled(False)
            return

        lam = np.asarray(lam_src, dtype=np.float64).ravel()
        n_nom = np.asarray(n_src, dtype=np.float64).ravel()
        k_nom = np.asarray(k_src, dtype=np.float64).ravel()

        if not lam.size:
            return

        # Smart grid generation
        lo, hi = float(np.nanmin(lam)), float(np.nanmax(lam))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if not lam_g.size:
            return

        # Nominal interpolation
        n_g = np.interp(lam_g, lam, n_nom, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, lam, k_nom, left=np.nan, right=np.nan)

        # Corridor interpolation
        n_lo_g = np.full_like(lam_g, np.nan)
        n_hi_g = np.full_like(lam_g, np.nan)
        k_lo_g = np.full_like(lam_g, np.nan)
        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(result.get("profile_d_enabled", False)) or bool(result.get("manual_corridor_active", False)):
            cn_lo = np.asarray(result.get("corridor_n_lo", []), dtype=np.float64).ravel()
            cn_hi = np.asarray(result.get("corridor_n_hi", []), dtype=np.float64).ravel()
            ck_lo = np.asarray(result.get("corridor_k_lo", []), dtype=np.float64).ravel()
            ck_hi = np.asarray(result.get("corridor_k_hi", []), dtype=np.float64).ravel()

            if cn_lo.size == lam.size:
                n_lo_g = np.interp(lam_g, lam, cn_lo, left=np.nan, right=np.nan)
                n_hi_g = np.interp(lam_g, lam, cn_hi, left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, lam, ck_lo, left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, lam, ck_hi, left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        # Center of corridor (midpoint)
        n_ctr_g = 0.5 * (n_lo_g + n_hi_g)
        k_ctr_g = 0.5 * (k_lo_g + k_hi_g)

        m = int(lam_g.size)
        t.setRowCount(m)

        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt

        def _cell(val: float, fmt: str = ".4f") -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):{fmt}}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        def _cell_sci(val: float) -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):.2e}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        for i in range(m):
            t.setItem(i, 0, _cell(float(lam_g[i]), ".1f"))
            t.setItem(i, 1, _cell(float(n_g[i])))
            t.setItem(i, 2, _cell_sci(float(k_g[i])))
            t.setItem(i, 3, _cell(float(n_ctr_g[i])))
            t.setItem(i, 4, _cell_sci(float(k_ctr_g[i])))
            t.setItem(i, 5, _cell(float(n_lo_g[i])))
            t.setItem(i, 6, _cell(float(n_hi_g[i])))
            t.setItem(i, 7, _cell_sci(float(k_lo_g[i])))
            t.setItem(i, 8, _cell_sci(float(k_hi_g[i])))

        self.btn_copy_corridor.setEnabled(True)
        self.btn_export_corridor.setEnabled(True)

