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

from certus.spline.spline_profile_corridors import quick_pwlnk_refit_result_dict

try:
    from certus.spline.spline_pipeline import _snap_spline_visual_dict
except ImportError:
    def _snap_spline_visual_dict(result: dict[str, Any]) -> dict[str, Any]:
        return dict(result)

from certus.utils.certus_ux import OBJ
from certus.utils.certus_reset_framework import create_reset_button
from certus.utils.certus_data import load_spectrum_columns, read_data_file_robust
from certus.spline.spline_profile_corridors import _expand_corridor_envelope_with_reported_nk, enforce_min_k_corridor_half_width
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
        logger.debug("_apply_fixed_log_k_axis failed", exc_info=True)

# Helper structures originally defined in CERTUS_INDEX_SPLINE

class _RMSEPlotContext:
    d_plot: np.ndarray
    r_plot: np.ndarray
    kind_plot: np.ndarray
    status_plot: np.ndarray
    d_vis: np.ndarray
    r_vis: np.ndarray
    kind_vis: np.ndarray
    status_vis: np.ndarray
    d_s: np.ndarray
    r_s: np.ndarray
    m_rev: np.ndarray
    m_main: np.ndarray
    envelope_display: bool
    is_live_grid: bool
    i_best: int
    parab_fit: dict = field(default_factory=dict)
    curvature_label_spec: Any = None
    live_parab: bool = False
    d_best: float = 0.0
    rmse_best: float = 0.0
    rmse_thr: Any = None
    d_parab_arr: np.ndarray = field(default_factory=lambda: np.array([]))
    r_parab_arr: np.ndarray = field(default_factory=lambda: np.array([]))
    win_rb: float = 0.0
    delta_rb: float = 0.0
    i_parab_best: int = -1
    rb_ok: bool = False
    d_lo_rb: float = float("nan")
    d_hi_rb: float = float("nan")
    slope_b: float = float("nan")
    curv_b: float = float("nan")
    d_center: float = float("nan")
    bp_events: list = field(default_factory=list)
    bp_dir_left: int = 0
    bp_dir_right: int = 0

class _ExcelExportMixin:
    """Excel Export Area."""

    def export_excel(self, auto_export: bool = False) -> None:
        """Delegates Excel export to SplineReportBuilder."""
        if self._last_result is None:
            if auto_export:
                return
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Error", "No result to export.")
            return
        try:
            warnings_local: list[str] = []
            corr_enabled = bool(getattr(self, "chk_corridor_d", None) and self.chk_corridor_d.isChecked())
            boot_enabled = bool(getattr(self, "chk_corr_boot", None) and self.chk_corr_boot.isChecked())
            corr_seed = int(getattr(self, "sp_corr_seed", None).value()) if hasattr(self, "sp_corr_seed") else 0
            boot_seed = (
                int(getattr(self, "sp_corr_boot_seed", None).value()) if hasattr(self, "sp_corr_boot_seed") else 0
            )
            if corr_enabled and corr_seed == 0:
                warnings_local.append("Spline corridor profiling enabled without an explicit RNG seed.")
            if boot_enabled and boot_seed == 0:
                warnings_local.append("Spline bootstrap enabled without an explicit RNG seed.")
            if warnings_local:
                self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                for msg in warnings_local:
                    self.add_validation_warning(msg)
            else:
                self.set_validation_status("OK")
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            self.logger.warning("INDEX_SPLINE export validation status update skipped: %s", exc)

        try:
            svc = IndexFitService(runner=lambda _cfg: self._last_result)
            status_txt = str(getattr(self, "validation_status", "OK") or "OK")
            try:
                status_val = ValidationStatus(status_txt)
            except ValueError:
                status_val = ValidationStatus.OK
            warnings_for_manifest = list(getattr(self, "validation_warnings", []) or [])
            req = IndexFitRequest(
                config=self._build_opt_config(notify=False),
                source_paths=[str(getattr(self, "_last_spectrum_path", "") or "")],
                seed=(int(getattr(self, "sp_corr_seed", None).value()) if hasattr(self, "sp_corr_seed") else None),
                app_id="CERTUS_INDEX_SPLINE",
                app_version=__version__,
                warnings=warnings_for_manifest,
                status=status_val,
            )
            svc_resp = svc.fit(req)
            self._last_result["run_manifest"] = svc_resp.manifest.to_dict()
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            self.logger.warning("INDEX_SPLINE manifest generation skipped: %s", exc)

        from certus.utils.certus_data import validate_manifest_for_export

        manifest_dict = self._last_result.get("run_manifest") if isinstance(self._last_result, dict) else None
        ok_manifest, missing_manifest_fields = validate_manifest_for_export(
            manifest_dict if isinstance(manifest_dict, dict) else None,
            auto=auto_export,
            logger=self.logger,
            module_name="INDEX_SPLINE",
        )
        if not ok_manifest:
            missing_txt = ", ".join(missing_manifest_fields)
            if not auto_export:
                QMessageBox.warning(
                    self,
                    "Export blocked",
                    "Export blocked: incomplete manifest. Missing fields: " + missing_txt,
                )
            return

        summary_dict = {
            "Module": "INDEX_SPLINE",
            "RMSE": float(
                self._last_result.get("rmse", np.sqrt(max(float(self._last_result.get("mse", 0.0)), 0.0)))
            ) if isinstance(self._last_result, dict) else float("nan"),
            "d_nm": float(self._last_result.get("d_nm", float("nan"))) if isinstance(self._last_result, dict) else float("nan"),
            "Spectrum": str(getattr(self, "_last_spectrum_path", "") or ""),
            "Substrate": str(self.cb_sub.currentData() or self.cb_sub.currentText()),
            "T_is_ratio": bool(self.chk_trel.isChecked()),
        }
        solution_rows = []
        if isinstance(self._last_result, dict):
            for key in ("d_nm", "mse", "rmse", "x_encoding", "K_sigma", "n_seg_mesh"):
                if key in self._last_result:
                    solution_rows.append({"Parameter": key, "Value": str(self._last_result.get(key))})
        solution_df = pd.DataFrame(solution_rows or [{"Parameter": "status", "Value": "no solution fields"}])
        spectra_df = self.df if isinstance(getattr(self, "df", None), pd.DataFrame) else pd.DataFrame()
        manifest_dict = self._last_result.get("run_manifest") if isinstance(self._last_result, dict) else None
        extra_sheets = {}
        if isinstance(manifest_dict, dict):
            extra_sheets["Manifest"] = pd.DataFrame([
                {"Parameter": k, "Value": str(v)} for k, v in manifest_dict.items()
            ])
        report_ctx = build_export_context(
            module_name="INDEX_SPLINE",
            title="CERTUS Index Spline Report",
            rmse=float(summary_dict["RMSE"]),
            subtitle=f"Spectrum={Path(getattr(self, '_last_spectrum_path', '') or '').name}",
            app_name="CERTUS-INDEX-SPLINE",
            run_manifest=manifest_dict if isinstance(manifest_dict, dict) else None,
            warnings=list(getattr(self, "validation_warnings", []) or []),
            status=str(getattr(self, "validation_status", "OK") or "OK"),
        )
        sections = build_report_sections(
            summary_dict=summary_dict,
            solution_df=solution_df,
            spectra_df=spectra_df,
            manifest=manifest_dict if isinstance(manifest_dict, dict) else None,
            extra_sheets=extra_sheets or None,
        )
        self.logger.debug(
            "INDEX_SPLINE export context prepared | title=%s | sections=%d | subtitle=%s",
            report_ctx.title,
            len(sections),
            report_ctx.subtitle,
        )
        excel_path, html_path = export_optimization_report(
            reports_dir=str(Path(getattr(self, "_last_spectrum_path", "") or ".").parent / "reports"),
            module_name="INDEX_SPLINE",
            rmse=float(summary_dict["RMSE"]),
            summary_dict=summary_dict,
            solution_df=solution_df,
            spectra_df=spectra_df,
            plots=None,
            extra_sheets=extra_sheets or None,
            logger=self.logger,
        )
        if self.logger:
            self.logger.info(
                "[INDEX_SPLINE.export_excel] completed export | excel=%s | html=%s | auto=%s | spectrum=%s",
                excel_path,
                html_path,
                auto_export,
                getattr(self, "_last_spectrum_path", ""),
            )

    def _prep_rmse_plot_data(self, src: dict) -> "_RMSEPlotContext | None":
        """Tab  Corridor RMSE(d) : profile points + best sampled thickness marker."""

        if not hasattr(self, "plot_corridor_rmse_d"):
            return None

        try:
            self.plot_corridor_rmse_d.clear()

        except (AttributeError, RuntimeError):
            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            return None

        d_prof = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        rmse_prof = np.asarray(src.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        point_kind_prof = np.asarray(src.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
        point_status_prof = np.asarray(
            src.get("profile_d_manual_grid_point_status_code", []),
            dtype=np.int32,
        ).ravel()

        if (d_prof.size == 0 or rmse_prof.size != d_prof.size) and self._corridor_profile_source_result() is not None:
            src = self._corridor_profile_source_result() or src

            d_prof = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()

            rmse_prof = np.asarray(src.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            point_kind_prof = np.asarray(src.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
            point_status_prof = np.asarray(
                src.get("profile_d_manual_grid_point_status_code", []),
                dtype=np.int32,
            ).ravel()

        if d_prof.size == 0 or rmse_prof.size != d_prof.size:
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available for this run.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            if hasattr(self, "btn_corridor_generate_from_grid"):
                self.btn_corridor_generate_from_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_from_partial_grid"):
                self.btn_corridor_generate_from_partial_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
                self.btn_corridor_generate_auto_smart_grid.setEnabled(False)

            self._reset_corridor_manual_controls()

            self._update_corridor_rmse_state_bar(None)

            return None

        m = np.isfinite(d_prof) & np.isfinite(rmse_prof)

        d_prof = d_prof[m]

        rmse_prof = rmse_prof[m]
        if point_kind_prof.size == m.size:
            point_kind_prof = point_kind_prof[m]
        else:
            point_kind_prof = np.zeros(d_prof.size, dtype=np.int32)
        if point_status_prof.size == m.size:
            point_status_prof = point_status_prof[m]
        else:
            point_status_prof = np.zeros(d_prof.size, dtype=np.int32)

        if d_prof.size == 0:
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No finite corridor RMSE profile points.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            if hasattr(self, "btn_corridor_generate_from_grid"):
                self.btn_corridor_generate_from_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_from_partial_grid"):
                self.btn_corridor_generate_from_partial_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
                self.btn_corridor_generate_auto_smart_grid.setEnabled(False)

            self._reset_corridor_manual_controls()

            self._update_corridor_rmse_state_bar(None)

            return None

        order = np.argsort(d_prof)

        d_s = d_prof[order]

        r_s = rmse_prof[order]
        kind_s = point_kind_prof[order]
        status_s = point_status_prof[order]

        is_live_grid = str(src.get("profile_d_status", "")) == "manual_grid_live"
        if is_live_grid:
            # In live mode, display raw points as they arrive.
            d_plot = d_s.copy()
            r_plot = r_s.copy()
            kind_plot = kind_s.copy()
            status_plot = status_s.copy()
        else:
            # Finalized data: iterative RMSE peak filtering.
            d_plot, r_plot, k_plot, s_plot = _filter_rmse_peaks_iteratively(
                d_s.copy(), r_s.copy(), kind_s.copy(), status_s.copy()
            )
            kind_plot = k_plot
            status_plot = s_plot

        self._corridor_rmse_d_vals = d_plot.copy()
        self._corridor_rmse_vals = r_plot.copy()

        env_pref = bool(
            hasattr(self, "chk_corridor_rmse_envelope_only") and self.chk_corridor_rmse_envelope_only.isChecked()
        )

        # The lower envelope filter is often too aggressive for local parabolic wings.
        # We only apply it if explicitly requested AND we have finished a run.
        envelope_display = bool(env_pref and not is_live_grid and d_plot.size > 0)

        # Reduced tolerance to avoid masking the wings of the parabola (max 0.1nm)
        raw_step = (
            float(self.sp_corridor_grid_d_step_nm.value()) if hasattr(self, "sp_corridor_grid_d_step_nm") else 0.5
        )
        tol_nm = min(0.1, 0.2 * raw_step)

        if envelope_display:
            env_m = _rmse_d_lower_envelope_mask(d_plot, r_plot, tol_nm)

            d_vis = d_plot[env_m]

            r_vis = r_plot[env_m]

            kind_vis = kind_plot[env_m]
            status_vis = status_plot[env_m]

            o2 = np.argsort(d_vis)

            d_vis = d_vis[o2]

            r_vis = r_vis[o2]

            kind_vis = kind_vis[o2]
            status_vis = status_vis[o2]

        else:
            d_vis = d_plot

            r_vis = r_plot

            kind_vis = kind_plot
            status_vis = status_plot

        if hasattr(self, "btn_corridor_generate_from_grid"):
            self.btn_corridor_generate_from_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )
        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            self.btn_corridor_generate_from_partial_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )
        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            self.btn_corridor_generate_auto_smart_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )

        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev
        i_best = int(np.argmin(r_plot)) if r_plot.size > 0 else 0

        return _RMSEPlotContext(
            d_plot=d_plot,
            r_plot=r_plot,
            kind_plot=kind_plot,
            status_plot=status_plot,
            d_vis=d_vis,
            r_vis=r_vis,
            kind_vis=kind_vis,
            status_vis=status_vis,
            d_s=d_s,
            r_s=r_s,
            m_rev=m_rev,
            m_main=m_main,
            envelope_display=envelope_display,
            is_live_grid=is_live_grid,
            i_best=i_best,
        )

    def _plot_rmse_data_scatter(self, src: dict, ctx: "_RMSEPlotContext") -> None:
        d_plot = ctx.d_plot
        r_plot = ctx.r_plot
        d_vis = ctx.d_vis
        r_vis = ctx.r_vis
        kind_vis = ctx.kind_vis
        status_vis = ctx.status_vis
        m_rev = ctx.m_rev
        m_main = ctx.m_main
        i_best = ctx.i_best
        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev

        # Scatter brut : TOUS les points sans liaison visuelle (conform?ment au paradigme scatter)
        self.plot_corridor_rmse_d.addItem(
            pg.ScatterPlotItem(
                d_vis[m_main],
                r_vis[m_main],
                pen=pg.mkPen(CertusTheme.PRIMARY, width=0),
                brush=pg.mkBrush(0, 87, 255, 160),
                size=5,
                symbol="o",
                name="RMSE(d)",
            )
        )

        if np.any(m_rev):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_rev],
                    r_vis[m_rev],
                    pen=pg.mkPen(255, 140, 0, 180),
                    brush=pg.mkBrush(255, 140, 0, 160),
                    size=8,
                    symbol="t",
                    name="RMSE(d) reprise cassure",
                )
            )

        # Overlay fallback points so users can immediately see where strict Deltad
        # sampling used non-standard evaluation paths.
        m_fb_seed = np.asarray(status_vis == 1, dtype=bool)
        m_fb_obj = np.asarray(status_vis == 2, dtype=bool)
        m_fb_emg = np.asarray(status_vis == 3, dtype=bool)
        if np.any(m_fb_seed):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_seed],
                    r_vis[m_fb_seed],
                    pen=pg.mkPen("#ff8c00", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=10,
                    symbol="x",
                    name="Fallback seed",
                )
            )
        if np.any(m_fb_obj):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_obj],
                    r_vis[m_fb_obj],
                    pen=pg.mkPen("#c2185b", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=11,
                    symbol="d",
                    name="Fallback objectif",
                )
            )
        if np.any(m_fb_emg):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_emg],
                    r_vis[m_fb_emg],
                    pen=pg.mkPen("#6a1b9a", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=12,
                    symbol="s",
                    name="Fallback urgence",
                )
            )

        bp_events = src.get("profile_d_manual_grid_breakpoint_events", [])
        bp_d_vals: list[float] = []
        bp_r_vals: list[float] = []
        bp_d_prevn: list[float] = []
        bp_r_prevn: list[float] = []
        bp_d_parab: list[float] = []
        bp_r_parab: list[float] = []
        bp_dir_left = 0
        bp_dir_right = 0
        if isinstance(bp_events, list) and d_plot.size > 0:
            for ev in bp_events:
                if not isinstance(ev, dict):
                    continue
                d_b = float(ev.get("d_break_nm", float("nan")))
                if not np.isfinite(d_b):
                    continue
                i_b = int(np.argmin(np.abs(d_plot - d_b)))
                bp_d_vals.append(float(d_plot[i_b]))
                bp_r_vals.append(float(r_plot[i_b]))
                trg_prevn = bool(float(ev.get("trigger_prevN", 0.0)) > 0.5)
                trg_parab = bool(float(ev.get("trigger_parabola", 0.0)) > 0.5)
                if trg_parab:
                    bp_d_parab.append(float(d_plot[i_b]))
                    bp_r_parab.append(float(r_plot[i_b]))
                elif trg_prevn:
                    bp_d_prevn.append(float(d_plot[i_b]))
                    bp_r_prevn.append(float(r_plot[i_b]))
                dir_s = float(ev.get("branch_dir_sign", float("nan")))
                if np.isfinite(dir_s):
                    if dir_s > 0:
                        bp_dir_right += 1
                    elif dir_s < 0:
                        bp_dir_left += 1
        if bp_d_vals:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_vals, dtype=np.float64),
                    np.asarray(bp_r_vals, dtype=np.float64),
                    pen=pg.mkPen("#9b111e", width=3),
                    brush=pg.mkBrush(255, 236, 139, 180),
                    size=13,
                    symbol="o",
                    name="Breakpoints",
                )
            )
        if bp_d_prevn:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_prevn, dtype=np.float64),
                    np.asarray(bp_r_prevn, dtype=np.float64),
                    pen=pg.mkPen("#9b111e", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=11,
                    symbol="d",
                    name="Breakpoint prevN",
                )
            )
        if bp_d_parab:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_parab, dtype=np.float64),
                    np.asarray(bp_r_parab, dtype=np.float64),
                    pen=pg.mkPen("#7a3cff", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=12,
                    symbol="t",
                    name="Breakpoint parabola",
                )
            )

        i_best = int(np.argmin(r_plot))

        self._corridor_rmse_best_idx = i_best

        d_best = float(d_plot[i_best])

        rmse_best = float(r_plot[i_best])

        delta_rb = float(self.sp_corridor_rmse_delta.value()) if hasattr(self, "sp_corridor_rmse_delta") else 2e-4

        win_rb = int(self.sp_corridor_rmse_win.value()) if hasattr(self, "sp_corridor_rmse_win") else 3

        live_parab = (
            not hasattr(self, "chk_corridor_rmse_live_parabola") or self.chk_corridor_rmse_live_parabola.isChecked()
        )
        curvature_label_spec: tuple[float, float, float] | None = None

        # --- Min-RMSE par d unique pour le fit parabolique (profile likelihood correcte) ---
        # Pour absorber les doublons flottants (ex. d_opt ins?r? 2? par le walk),
        # on regroupe ? 1e-6 nm puis on conserve le RMSE minimal par d.
        _d_rounded = np.round(d_plot, decimals=6)
        _d_parab_list: list[float] = []
        _r_parab_list: list[float] = []
        for _dv in np.unique(_d_rounded):
            _m = _d_rounded == _dv
            _best = int(np.argmin(r_plot[_m]))
            _d_parab_list.append(float(d_plot[_m][_best]))
            _r_parab_list.append(float(r_plot[_m][_best]))
        d_parab_arr = np.asarray(_d_parab_list, dtype=np.float64)
        r_parab_arr = np.asarray(_r_parab_list, dtype=np.float64)

        i_parab_best = int(np.argmin(r_parab_arr)) if r_parab_arr.size > 0 else int(i_best)

        parab_half_window_pts = int(max(int(win_rb), int(max(1, d_parab_arr.size))))
        parab_fit = (
            _fit_local_quadratic_rmse_profile(
                d_parab_arr,
                r_parab_arr,
                i_parab_best,
                parab_half_window_pts,
                delta_rb,
            )
            if live_parab
            else {"ok": False}
        )

        d_center = float(parab_fit.get("d_center", float("nan"))) if bool(parab_fit.get("ok", False)) else float(d_best)

        self._corridor_rmse_center_nm = float(d_center)

        self.plot_corridor_rmse_d.addItem(
            pg.InfiniteLine(
                pos=d_best,
                angle=90,
                movable=False,
                pen=pg.mkPen("#17a673", width=2, style=Qt.PenStyle.DashLine),
            )
        )

        self.plot_corridor_rmse_d.addItem(
            pg.ScatterPlotItem(
                [d_best],
                [rmse_best],
                pen=pg.mkPen("#0a5f42", width=1),
                brush=pg.mkBrush("#20c997"),
                size=10,
                symbol="o",
            )
        )

        rmse_thr = src.get("profile_d_rmse_thresh")

        if rmse_thr is not None and np.isfinite(float(rmse_thr)):
            thr = float(rmse_thr)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(
                    pos=thr,
                    angle=0,
                    movable=False,
                    pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DashLine),
                )
            )

        if live_parab:
            rb_ok, d_lo_rb, d_hi_rb, slope_b, _curv_b = self._robust_interval_from_local_quadratic(
                d_parab_arr,
                r_parab_arr,
                i_parab_best,
                delta_rb,
                parab_half_window_pts,
            )

        else:
            rb_ok, d_lo_rb, d_hi_rb, slope_b, _curv_b = False, float("nan"), float("nan"), float("nan"), float("nan")

        if bool(parab_fit.get("ok", False)):
            win_lo, win_hi = parab_fit.get("window_nm", (float(np.min(d_parab_arr)), float(np.max(d_parab_arr))))
            d_center_fit = float(parab_fit.get("d_center", d_center))
            lo_w = float(win_lo)
            hi_w = float(win_hi)
            half_span = float("nan")
            if np.isfinite(d_center_fit) and np.isfinite(lo_w) and np.isfinite(hi_w) and hi_w > lo_w:
                left = float(d_center_fit - lo_w)
                right = float(hi_w - d_center_fit)
                # Symmetric display around the parabola center (visual quasi-symmetry guaranteed).
                if left > 0.0 and right > 0.0:
                    half_span = float(min(left, right))
                else:
                    half_span = 0.5 * float(hi_w - lo_w)
            if not np.isfinite(half_span) or half_span <= 0.0:
                half_span = max(1e-6, 0.5 * float(np.ptp(d_parab_arr)) if d_parab_arr.size > 1 else 1e-3)
            d_par = np.linspace(
                float(d_center_fit - half_span),
                float(d_center_fit + half_span),
                200,
                dtype=np.float64,
            )

            c2, c1, c0 = parab_fit.get("coeffs", (float("nan"), float("nan"), float("nan")))

            x_par = d_par - float(parab_fit.get("anchor_nm", d_best))

            r_par = float(c2) * x_par * x_par + float(c1) * x_par + float(c0)

            self._add_curve(
                self.plot_corridor_rmse_d,
                d_par,
                r_par,
                "#7a3cff",
                "Local parabolic fit",
                pen=pg.mkPen("#7a3cff", width=2, style=Qt.PenStyle.DashLine),
            )

            # c2 = coefficient quadratique (RMSE = c2x^2+c1x+c0, x = d ? anchor) ; sommet en d_center.
            if np.isfinite(c2) and c2 > 0 and np.isfinite(c1) and np.isfinite(c0):
                d_v = float(parab_fit.get("d_center", float("nan")))
                r_v = float(c0) - float(c1) ** 2 / (4.0 * float(c2))
                if np.isfinite(d_v) and np.isfinite(r_v):
                    curvature_label_spec = (float(c2), d_v, r_v)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(
                    pos=float(d_center),
                    angle=90,
                    movable=False,
                    pen=pg.mkPen("#7a3cff", width=1, style=Qt.PenStyle.DotLine),
                )
            )

        ctx.parab_fit = parab_fit
        ctx.curvature_label_spec = curvature_label_spec
        ctx.live_parab = live_parab
        ctx.d_best = d_best
        ctx.rmse_best = rmse_best
        ctx.rmse_thr = rmse_thr
        ctx.d_parab_arr = d_parab_arr
        ctx.r_parab_arr = r_parab_arr
        ctx.win_rb = win_rb
        ctx.delta_rb = delta_rb
        ctx.i_parab_best = i_parab_best
        ctx.rb_ok = bool(rb_ok)
        ctx.d_lo_rb = float(d_lo_rb)
        ctx.d_hi_rb = float(d_hi_rb)
        ctx.slope_b = float(slope_b)
        ctx.curv_b = float(_curv_b)
        ctx.d_center = float(d_center) if bool(parab_fit.get("ok", False)) else float(d_best)
        ctx.bp_events = bp_events if isinstance(bp_events, list) else []
        ctx.bp_dir_left = int(bp_dir_left)
        ctx.bp_dir_right = int(bp_dir_right)

    def _plot_corridor_rmse_tab(self, src: dict) -> None:
        """Tab corridor RMSE(d). Orchestrator."""
        if not hasattr(self, "plot_corridor_rmse_d"):
            return
        ctx = self._prep_rmse_plot_data(src)
        if ctx is None:
            return
        self._plot_rmse_data_scatter(src, ctx)
        d_plot = ctx.d_plot
        r_plot = ctx.r_plot
        d_vis = ctx.d_vis
        r_vis = ctx.r_vis
        i_best = ctx.i_best
        parab_fit = ctx.parab_fit
        curvature_label_spec = ctx.curvature_label_spec
        envelope_display = ctx.envelope_display
        is_live_grid = ctx.is_live_grid
        live_parab = ctx.live_parab
        d_best = ctx.d_best
        rmse_best = ctx.rmse_best
        rmse_thr = ctx.rmse_thr
        d_parab_arr = ctx.d_parab_arr
        r_parab_arr = ctx.r_parab_arr
        win_rb = ctx.win_rb
        delta_rb = ctx.delta_rb

        rb_ok = ctx.rb_ok
        d_lo_rb = ctx.d_lo_rb
        d_hi_rb = ctx.d_hi_rb
        slope_b = ctx.slope_b
        _curv_b = ctx.curv_b
        d_center = ctx.d_center
        bp_events = ctx.bp_events
        bp_dir_left = ctx.bp_dir_left
        bp_dir_right = ctx.bp_dir_right

        self._corridor_rmse_robust_ok = bool(rb_ok)

        self._corridor_rmse_robust_lo = float(d_lo_rb)

        self._corridor_rmse_robust_hi = float(d_hi_rb)

        # --- Smart Deltad: automatic interval from profiling code (profile_d_interval_nm) ---
        _int_nm = src.get("profile_d_interval_nm", None)
        _int_ok = (
            isinstance(_int_nm, (tuple, list))
            and len(_int_nm) == 2
            and np.isfinite(float(_int_nm[0]))
            and np.isfinite(float(_int_nm[1]))
        )

        # Fallback: if the interval is not provided (e.g. simple grid),
        # Try to calculate it locally from the points and RMSE threshold.
        if not _int_ok and rmse_thr is not None and np.isfinite(float(rmse_thr)) and d_plot.size > 1:
            thr = float(rmse_thr)
            # On cherche les points d'intersection (simple scan lin?aire sur l'enveloppe basse)
            # Note: d_parab_arr est tri? et contient l'enveloppe min-per-d
            if d_parab_arr.size > 2:
                try:
                    _m_below = r_parab_arr <= thr
                    if np.any(_m_below):
                        _d_below = d_parab_arr[_m_below]
                        _int_nm = (float(np.min(_d_below)), float(np.max(_d_below)))
                        _int_ok = True
                except (ValueError, TypeError, AttributeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        if _int_ok:
            _d_int_lo = float(_int_nm[0])
            _d_int_hi = float(_int_nm[1])
            _pen_int = pg.mkPen("#ff8c00", width=3, style=Qt.PenStyle.SolidLine)
            _line_int_lo = pg.InfiniteLine(pos=_d_int_lo, angle=90, movable=False, pen=_pen_int)
            _line_int_hi = pg.InfiniteLine(pos=_d_int_hi, angle=90, movable=False, pen=_pen_int)
            _line_int_lo.setToolTip(f"Smart interval low-bound: {_d_int_lo:.3f} nm")
            _line_int_hi.setToolTip(f"Smart interval high-bound: {_d_int_hi:.3f} nm")

            # Labels sur les lignes intelligentes
            _d_int_adap = src.get("profile_d_rmse_abs_tolerance_adaptive", False)
            _int_label_base = "Deltad auto" + (" (adapt.)" if _d_int_adap else "")
            _label_lo = pg.TextItem(
                text=f"{_int_label_base}\n{_d_int_lo:.3f} nm",
                color="#ff8c00",
                anchor=(0.5, 1.0),
            )
            _label_hi = pg.TextItem(
                text=f"{_int_label_base}\n{_d_int_hi:.3f} nm",
                color="#ff8c00",
                anchor=(0.5, 1.0),
            )
            self.plot_corridor_rmse_d.addItem(_line_int_lo)
            self.plot_corridor_rmse_d.addItem(_line_int_hi)

            # Position the TextItems slightly above the minimum.
            _r_range = float(np.max(r_plot) - np.min(r_plot)) if r_plot.size > 1 else 1e-4
            _r_label = float(np.nanmin(r_plot)) + 0.05 * _r_range
            _label_lo.setPos(_d_int_lo, _r_label)
            _label_hi.setPos(_d_int_hi, _r_label)
            self.plot_corridor_rmse_d.addItem(_label_lo)
            self.plot_corridor_rmse_d.addItem(_label_hi)
            self._corridor_rmse_smart_interval = (_d_int_lo, _d_int_hi)
        else:
            self._corridor_rmse_smart_interval = None

        # --- Local robust interval (user-configurable) ---
        if rb_ok:
            pen_rb = pg.mkPen("#7a3cff", width=1, style=Qt.PenStyle.DashLine)
            self.plot_corridor_rmse_d.addItem(pg.InfiniteLine(pos=float(d_lo_rb), angle=90, movable=False, pen=pen_rb))
            self.plot_corridor_rmse_d.addItem(pg.InfiniteLine(pos=float(d_hi_rb), angle=90, movable=False, pen=pen_rb))

        self._corridor_rmse_parab_export = dict(parab_fit)

        self._corridor_rmse_robust_export = {
            "ok": bool(rb_ok),
            "d_lo": float(d_lo_rb),
            "d_hi": float(d_hi_rb),
            "slope": float(slope_b),
            "curvature": float(_curv_b),
            "delta_rmse_setting": float(delta_rb),
            "half_window_pts": int(win_rb),
        }

        self._sync_corridor_manual_controls(d_plot, i_best)

        d_lo_man = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))

        d_hi_man = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))

        if np.isfinite(d_lo_man) and np.isfinite(d_hi_man) and d_hi_man >= d_lo_man:
            pen_man = pg.mkPen("#ff4d4f", width=1, style=Qt.PenStyle.DashLine)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(pos=float(d_lo_man), angle=90, movable=False, pen=pen_man)
            )

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(pos=float(d_hi_man), angle=90, movable=False, pen=pen_man)
            )

        if hasattr(self, "lbl_corridor_rmse_summary"):
            _grid_note = ""

            if str(src.get("profile_d_status", "")) == "manual_grid":
                _grid_note = " | manual grid (re-run)"

                n_bp = int(src.get("profile_d_manual_grid_breakpoint_count", 0))

                n_extra = int(src.get("profile_d_manual_grid_extra_points", 0))

                if n_bp > 0 or n_extra > 0:
                    _grid_note += f" | breakpoints detected={n_bp} | points extra={n_extra}"
                if isinstance(bp_events, list) and bp_events:
                    n_prevn = int(
                        sum(1 for ev in bp_events if isinstance(ev, dict) and float(ev.get("trigger_prevN", 0.0)) > 0.5)
                    )
                    n_parab = int(
                        sum(
                            1
                            for ev in bp_events
                            if isinstance(ev, dict) and float(ev.get("trigger_parabola", 0.0)) > 0.5
                        )
                    )
                    _grid_note += f" | causes(prevN={n_prevn}, parabola={n_parab})"
                    _grid_note += f" | direction(chosen left={int(bp_dir_left)}, right={int(bp_dir_right)})"

            _env_note = ""

            if envelope_display:
                _env_note = f" | plot: lower envelope ({int(d_vis.size)}/{int(d_plot.size)} pts)"

            _smart_note = ""
            if getattr(self, "_corridor_rmse_smart_interval", None) is not None:
                _s_lo, _s_hi = self._corridor_rmse_smart_interval
                _smart_note = f" | Deltad code ? [{_s_lo:.3f}, {_s_hi:.3f}] nm"

            txt = (
                (
                    f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {rmse_best:.6f} | "
                    f"samples = {int(d_plot.size)}"
                )
                + _env_note
                + _grid_note
                + _smart_note
            )

            if rb_ok:
                txt += (
                    f" | robust Delta={delta_rb:.6f} -> interval ? [{float(d_lo_rb):.3f}, {float(d_hi_rb):.3f}] nm"
                    f" | slope@d*?{float(slope_b):+.2e} /nm"
                )

                if bool(parab_fit.get("ok", False)):
                    txt += f" | parabola center?{float(d_center):.3f} nm"

            else:
                txt += " | robust interval unavailable (insufficient local convex fit)"

            if np.isfinite(d_lo_man) and np.isfinite(d_hi_man):
                man_state = "active" if bool(getattr(self, "_corridor_rmse_manual_active", False)) else "preview"

                txt += f" | manual {man_state} ? [{float(d_lo_man):.3f}, {float(d_hi_man):.3f}] nm"

                if bool(src.get("manual_corridor_active", False)):
                    txt += f" ({int(src.get('manual_corridor_selected_count', 0))} profiled points)"

                    d_sel_rng = src.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))

                    if (
                        isinstance(d_sel_rng, (tuple, list))
                        and len(d_sel_rng) >= 2
                        and np.isfinite(float(d_sel_rng[0]))
                        and np.isfinite(float(d_sel_rng[1]))
                    ):
                        txt += f" | sampled in [{float(d_sel_rng[0]):.3f}, {float(d_sel_rng[1]):.3f}] nm"

            if is_live_grid and not live_parab:
                txt += " | live preview: points only (parabola/robust fit paused)"

            self.lbl_corridor_rmse_summary.setText(txt)
        if hasattr(self, "lbl_corridor_rmse_robust_compact"):
            if rb_ok and np.isfinite(float(d_lo_rb)) and np.isfinite(float(d_hi_rb)):
                d_mid_rb = 0.5 * float(d_lo_rb + d_hi_rb)
                d_half_rb = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))
                self.lbl_corridor_rmse_robust_compact.setText(
                    f"Robust interval: {d_mid_rb:.2f}nm +/- {d_half_rb:.1f}nm"
                )
            else:
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        try:
            self.plot_corridor_rmse_d.plotItem.setTitle(
                f"Corridor profile RMSE(d) ? best d* = {d_best:.3f} nm (RMSE {rmse_best:.6f})",
                color=CertusTheme.PRIMARY,
                size="10pt",
            )

        except (AttributeError, RuntimeError):
            logger.debug("Corridor RMSE(d) title set failed", exc_info=True)

        lock_scale = bool(
            hasattr(self, "chk_corridor_rmse_lock_scale") and self.chk_corridor_rmse_lock_scale.isChecked()
        )

        if is_live_grid:
            # Live mode must always remain visible even if a stale/locked viewport
            # exists from a previous run. Force bounds on current finite data.
            self._set_corridor_rmse_view_data_bounds(
                d_plot,
                r_plot,
            )
        elif lock_scale:
            self._set_corridor_rmse_view_data_bounds(
                d_vis if envelope_display else d_plot,
                r_vis if envelope_display else r_plot,
            )

        elif np.isfinite(d_lo_man) and np.isfinite(d_hi_man) and d_hi_man >= d_lo_man:
            self._set_corridor_rmse_view_centered(float(d_center), 0.5 * float(max(0.0, d_hi_man - d_lo_man)))

        else:
            self.plot_corridor_rmse_d.autoRange()

        if curvature_label_spec is not None:
            c2_l, d_vl, r_vl = curvature_label_spec
            c2_disp = float(abs(c2_l))
            if not np.isfinite(c2_disp) or c2_disp <= 0.0:
                c2_disp = float("nan")
            r_span_src = r_vis if envelope_display else r_plot
            span_r = (
                float(np.nanmax(r_span_src) - np.nanmin(r_span_src))
                if r_span_src.size > 1
                else max(1e-6, abs(float(r_vl)) * 0.05 if np.isfinite(r_vl) else 1e-4)
            )
            dy = max(1e-6, 0.035 * span_r)
            if np.isfinite(c2_disp):
                label_a = pg.TextItem(
                    text=f"Curvature a = {c2_disp:.4e} nm?^2",
                    color="#7a3cff",
                    anchor=(0.5, 1),
                    fill=pg.mkColor(255, 255, 255, 220),
                )
                label_a.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                label_a.setPos(d_vl, r_vl + dy)
                self.plot_corridor_rmse_d.addItem(label_a, ignoreBounds=True)

        self._update_corridor_rmse_state_bar(src)

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
            logger.debug("Corridor RMSE tab refresh after manual grid failed", exc_info=True)

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
                manual_dlg.append_runtime_log("Re-optimisation terminee sans resultat exploitable.")

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

        # Auto-Best: declencher une 2e passe locale (knots libres split n/logk) after la 1ere passe warm.

        if self._auto_best_two_stage_refine:
            cfg2 = self._build_opt_config()

            if cfg2 is not None:
                self._auto_best_second_stage_pending = {
                    "seed": dict(result),
                    "cfg": cfg2,
                }

                self._auto_best_two_stage_refine = False

                self.log(
                    "Auto-Best: launching local pass 2 (knots sigma separes pour n et ln k, puis polish).",
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

            _log_index_spline_best_config(self.logger, display, rmse_fin, title="[FIN OPTIM  affichage / export]")

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
            logger.debug("Corridor bootstrap band plot failed", exc_info=True)

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
            logger.debug("Corridor plot title set failed", exc_info=True)

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
        lbl_intro.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
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
            "Une fen?tre plus large lisse les bruits num?riques mais peut capturer des zones non-paraboliques."
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
            "Utilise un m?canisme de <b>continuation (warmstart)</b> et de <b>P0 re-pass</b> pour garantir "
            "l'exploration de la solution optimale physique."
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
        lbl_generate.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
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

        self.pb_corridor_rmse_grid = QProgressBar()
        self.pb_corridor_rmse_grid.setToolTip(
            "<b>Scan progress</b><br>"
            "Real-time progression including continuation steps, "
            "P0 re-pass, and breakpoint detection."
        )
        self.pb_corridor_rmse_grid.setRange(0, 1000)

        self.pb_corridor_rmse_grid.setValue(0)

        self.pb_corridor_rmse_grid.setFormat("Grid %p%")

        self.pb_corridor_rmse_grid.setEnabled(False)

        row_grid_prog.addWidget(self.pb_corridor_rmse_grid, 1)

        self.lbl_corridor_rmse_grid_progress = QLabel("Grid idle.")

        self.lbl_corridor_rmse_grid_progress.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

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
                "RMSE(d): base corridor indisponible (reconstruction auto impossible). Lance un fit, puis r?essaie."
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

            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

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

class _PlotMixin:
    """Mixin containing plot methods for n/k tabs and data preview."""

    def _refresh_data_preview_plots(
        self,
        ser: tuple[np.ndarray, ...] | None = None,
    ) -> None:
        """Data mini-graphs: all n / all k, table grid, synchronized lambda."""

        if not hasattr(self, "plot_data_preview_n") or not hasattr(self, "plot_data_preview_k"):
            return

        pn = self.plot_data_preview_n

        pk = self.plot_data_preview_k

        pn.clear()

        pk.clear()

        pn._certus_crosshair_label_fn = None

        pk._certus_crosshair_label_fn = None

        pn._certus_crosshair_vertical_only = False

        pk._certus_crosshair_vertical_only = False

        self._data_preview_series = None

        if ser is None:
            pn._apply_sensible_empty_range()

            pk._apply_sensible_empty_range()

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        lam = np.asarray(lam_g, dtype=np.float64).ravel()

        nv = np.asarray(n_g, dtype=np.float64).ravel()

        kv = np.asarray(k_g, dtype=np.float64).ravel()

        n_nl_v = np.asarray(n_nl_g, dtype=np.float64).ravel()

        k_nl_v = np.asarray(k_nl_g, dtype=np.float64).ravel()

        n_lo_v = np.asarray(n_lo_g, dtype=np.float64).ravel()

        n_hi_v = np.asarray(n_hi_g, dtype=np.float64).ravel()

        k_lo_v = np.asarray(k_lo_g, dtype=np.float64).ravel()

        k_hi_v = np.asarray(k_hi_g, dtype=np.float64).ravel()

        mk = np.isfinite(lam) & np.isfinite(kv) & (kv > 0.0)

        kk = kv[mk]

        k_pos = kk[kk > 0.0]

        k_floor = float(np.nanmin(k_pos)) if k_pos.size > 0 else 1e-30

        self._data_preview_series = {
            "lam": lam.copy(),
            "n": nv.copy(),
            "n_nl": n_nl_v.copy(),
            "n_lo": n_lo_v.copy(),
            "n_hi": n_hi_v.copy(),
            "k": kv.copy(),
            "k_nl": k_nl_v.copy(),
            "k_lo": k_lo_v.copy(),
            "k_hi": k_hi_v.copy(),
            "k_floor": k_floor,
        }

        def _add_legend(plot: CertusScientificPlot) -> None:

            try:
                plot.addLegend(offset=(8, 8))

            except NUMERICAL_FAULT_EXCEPTIONS :
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # --- n preview : enveloppe puis courbes ---
        y_n_all = [nv]
        if np.any(np.isfinite(n_nl_v)):
            y_n_all.append(n_nl_v)

        m_n_env = np.isfinite(n_lo_v) & np.isfinite(n_hi_v) & (n_hi_v >= n_lo_v)

        if np.any(m_n_env):
            y_n_all.extend([n_lo_v, n_hi_v])
            le = lam[m_n_env]
            ylo = n_lo_v[m_n_env]
            yhi = n_hi_v[m_n_env]
            o = np.argsort(le, kind="mergesort")
            le, ylo, yhi = le[o], ylo[o], yhi[o]
            if le.size >= 2:
                # Shaded background band
                cl_f = pg.PlotCurveItem(le, ylo, pen=None)
                cu_f = pg.PlotCurveItem(le, yhi, pen=None)
                pn.addItem(pg.FillBetweenItem(cl_f, cu_f, brush=pg.mkBrush(0, 87, 255, 40)))

                # Dashed bounds + Glow (matching main corridor style)
                p_lo_glow = pg.mkPen((180, 220, 255, 140), width=4.0)
                p_hi_glow = pg.mkPen((160, 200, 255, 140), width=4.0)
                p_lo = pg.mkPen((0, 140, 255, 200), width=1.8, style=Qt.PenStyle.DashLine)
                p_hi = pg.mkPen((0, 70, 255, 200), width=1.8, style=Qt.PenStyle.DashLine)
                pn.plot(le, ylo, pen=p_lo_glow)
                pn.plot(le, yhi, pen=p_hi_glow)
                pn.plot(le, ylo, pen=p_lo)
                pn.plot(le, yhi, pen=p_hi)

        if np.any(np.isfinite(n_nl_v)):
            xnl, ynl = sanitize_xy_for_plot(lam, n_nl_v)

            if xnl.size >= 2:
                plot_widget_plot_finite(
                    pn,
                    xnl,
                    ynl,
                    pen=pg.mkPen("#0a8f5a", width=1.6),
                    name="n_alpha",
                )

        xn, yn = sanitize_xy_for_plot(lam, nv)

        if xn.size >= 2:
            c_n = plot_widget_plot_finite(pn, xn, yn, pen=pg.mkPen("#0057ff", width=2.4), name="n")

            if c_n is not None:
                setattr(c_n, "_certus_crosshair_primary", True)

        # --- k preview : enveloppe (k>0) puis courbes ---
        y_k_all = [kv]
        if np.any(np.isfinite(k_nl_v)):
            y_k_all.append(k_nl_v)

        m_k_env = np.isfinite(k_lo_v) & np.isfinite(k_hi_v) & (k_lo_v > 0.0) & (k_hi_v > 0.0) & (k_hi_v >= k_lo_v)

        if np.any(m_k_env):
            y_k_all.extend([k_lo_v, k_hi_v])
            lek = lam[m_k_env]
            ylok = k_lo_v[m_k_env]
            yhik = k_hi_v[m_k_env]
            ok = np.argsort(lek, kind="mergesort")
            lek, ylok, yhik = lek[ok], ylok[ok], yhik[ok]
            if lek.size >= 2:
                # Shaded background band
                clk_f = pg.PlotCurveItem(lek, ylok, pen=None)
                cuk_f = pg.PlotCurveItem(lek, yhik, pen=None)
                pk.addItem(pg.FillBetweenItem(clk_f, cuk_f, brush=pg.mkBrush(255, 160, 40, 35)))

                # Dashed bounds + Glow (matching main corridor style)
                p_klo_glow = pg.mkPen((255, 235, 190, 180), width=4.0)
                p_khi_glow = pg.mkPen((255, 210, 200, 180), width=4.0)
                p_klo = pg.mkPen((255, 150, 0, 230), width=1.8, style=Qt.PenStyle.DashLine)
                p_khi = pg.mkPen((255, 40, 0, 230), width=1.8, style=Qt.PenStyle.DashLine)
                pk.plot(lek, ylok, pen=p_klo_glow)
                pk.plot(lek, yhik, pen=p_khi_glow)
                pk.plot(lek, ylok, pen=p_klo)
                pk.plot(lek, yhik, pen=p_khi)

        if np.any(np.isfinite(k_nl_v) & (k_nl_v > 0.0)):
            knlp = np.where(np.isfinite(k_nl_v) & (k_nl_v > 0.0), k_nl_v, np.nan)

            xknl, yknl = sanitize_xy_for_plot(lam, knlp)

            if xknl.size >= 2:
                plot_widget_plot_finite(
                    pk,
                    xknl,
                    yknl,
                    pen=pg.mkPen("#0a8f5a", width=1.6),
                    name="k_alpha",
                )

        kk_plot = np.where(np.isfinite(kv) & (kv > 0.0), kv, np.nan)

        xk, yk = sanitize_xy_for_plot(lam, kk_plot)

        if xk.size >= 2:
            c_k = plot_widget_plot_finite(pk, xk, yk, pen=pg.mkPen("#f59e0b", width=2.4), name="k")

            if c_k is not None:
                setattr(c_k, "_certus_crosshair_primary", True)

        pn.setLogMode(False, False)

        _apply_fixed_log_k_axis(pk)

        _add_legend(pn)

        _add_legend(pk)

        pn._certus_mouse_moved_hook = self._on_data_preview_plot_mouse_moved

        pk._certus_mouse_moved_hook = self._on_data_preview_plot_mouse_moved

        # Perform dynamic Y-scaling (user request: floor=min, fixed ymax k=1e-2)
        try:
            # n preview
            yn_all_f = np.concatenate([np.asarray(arr).ravel() for arr in y_n_all])
            yn_all_f = yn_all_f[np.isfinite(yn_all_f)]
            if yn_all_f.size > 0:
                yn_min, yn_max = float(np.min(yn_all_f)), float(np.max(yn_all_f))
                if yn_max > yn_min:
                    pn.setYRange(yn_min, yn_max, padding=0)
                else:
                    pn.autoRange()
            else:
                pn.autoRange()

            _apply_fixed_log_k_axis(pk)
        except NUMERICAL_FAULT_EXCEPTIONS:
            pn.autoRange()
            _apply_fixed_log_k_axis(pk)

class _UIBuilderMixin:
    """Mixin containing UI-construction tab methods."""

    def _build_ui(self) -> None:

        setup_pyqtgraph_defaults()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        hdr_w = create_header_logo_widget(
            title_text="INDEX-SPLINE",
            subtitle_text=self.APP_TITLE,
            module_name="CERTUS_INDEX_SPLINE",
        )
        # Inject theme toggle on the right of the header
        self._theme_toggle = CertusThemeToggle(hdr_w)
        hdr_w.layout().addWidget(self._theme_toggle)
        outer.addWidget(hdr_w)

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(6)
        outer.addLayout(root_layout, 1)

        # ── Left sidebar ─────────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setMinimumWidth(280)
        self.left_scroll = left_scroll

        left_inner = QWidget()
        left_inner.setMinimumWidth(280)
        left_lay = QVBoxLayout(left_inner)
        left_lay.setContentsMargins(0, 2, 2, 2)
        left_lay.setSpacing(2)

        # ── Stepper card ─────────────────────────────────────────────────────
        stepper_card = CertusCard("Workflow guide")
        stepper_card.body.setContentsMargins(8, 4, 8, 6)
        stepper_card.body.setSpacing(3)
        self._stepper = CertusStepper(
            [
                "Load spectrum",
                "Substrate (n) & layer thickness",
                "Fit targets (T / R)",
                "Mesh & optimizer",
                "Run",
                "Manual nodes",
                "Corridors & RMSE(d)",
            ],
            columns=2,
        )
        self._stepper.step_activated.connect(self._on_stepper_activated)
        self._stepper.set_step(0)
        stepper_card.body.addWidget(self._stepper)
        self.stepper_card = stepper_card
        left_lay.addWidget(stepper_card)

        # ── File card ─────────────────────────────────────────────────────────
        file_card = CertusCard("1  Spectrum")
        file_card.body.setContentsMargins(8, 4, 8, 6)
        file_card.body.setSpacing(4)
        self.lbl_file = QLabel("(no file loaded)")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_file.setToolTip("Path of the last loaded file.")
        self.btn_load = create_styled_button("Load spectrum…", "secondary")
        self.btn_load.setToolTip(
            "Step 1: open a file containing at least lambda and transmission T. "
            "In Basic, enable T/Tsub if T already is T_film/T_bare_sub ratio (often in %)."
        )
        self.btn_load.clicked.connect(self._on_load)
        file_card.body.addWidget(self.btn_load)
        file_card.body.addWidget(self.lbl_file)
        self.file_card = file_card
        left_lay.addWidget(file_card)

        # ── Parameters card (collapsible) ─────────────────────────────────────
        # ctrl_tabs kept as QTabWidget for full backward compat with all mixins
        self.ctrl_tabs = QTabWidget()
        self.ctrl_tabs.setDocumentMode(True)
        self.ctrl_tabs.setToolTip("Steps 2-4 in order: substrate, targets, mesh.")
        self.ctrl_tabs.addTab(self._build_controls_basic_panel(), "Basic (2 → 4)")
        self.params_collapsible = CertusCollapsible("2-4  Parameters", self.ctrl_tabs, expanded=False)
        self.params_collapsible._hdr.setStyleSheet(
            f"QPushButton {{ background: {CertusTheme.SURFACE_HOVER}; border: none; "
            f"border-radius: 6px; padding: 4px 8px; font-weight: 600; font-size: 11px; "
            f"color: {CertusTheme.TEXT_MAIN}; text-align: left; }}"
            f"QPushButton:hover {{ background: {CertusTheme.BORDER}; }}"
        )
        left_lay.addWidget(self.params_collapsible)

        # ── Action bar (Run / Stop / toggles) ────────────────────────────────
        action_card = CertusCard("5  Run, manual nodes, corridors")
        action_card.body.setContentsMargins(8, 4, 8, 6)
        action_card.body.setSpacing(4)

        self.btn_run = QPushButton("▶  Run Optimization")
        self.btn_run.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setMinimumHeight(26)
        self.btn_run.setToolTip("Start global optimization (Smart Init).")
        self.btn_run.clicked.connect(self._on_run)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName(OBJ.DANGER_BUTTON)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(26)
        self.btn_stop.setToolTip("Stop and keep best result found so far.")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)

        run_row = QHBoxLayout()
        run_row.setSpacing(4)
        run_row.addWidget(self.btn_run, 2)
        run_row.addWidget(self.btn_stop, 1)
        action_card.body.addLayout(run_row)

        # Post-run actions: Manual nodes first (dominant), then corridors.
        post_row = QHBoxLayout()
        post_row.setSpacing(4)

        self.btn_manual_knots_toggle = QPushButton("◆  Manual knots")
        self.btn_manual_knots_toggle.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_manual_knots_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manual_knots_toggle.setMinimumHeight(26)
        self.btn_manual_knots_toggle.setToolTip(
            "Priority action after optimization: automatic removal + manual knot insertion."
        )
        self.btn_manual_knots_toggle.clicked.connect(self._on_btn_manual_knots_clicked)

        self.btn_corridor_toggle = QPushButton("◈  Corridors / RMSE(d)")
        self.btn_corridor_toggle.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_corridor_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_corridor_toggle.setMinimumHeight(26)
        self.btn_corridor_toggle.setToolTip(
            "Priority action: launches corridors and RMSE(d) workflow from the latest optimized result."
        )
        self.btn_corridor_toggle.clicked.connect(self._on_btn_corridor_clicked)

        self.lbl_corridors_run_state = QLabel()
        self.lbl_corridors_run_state.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_corridors_run_state.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")
        self.lbl_corridors_run_state.setToolTip(
            "Indicates if manual corridor calculation is available or already computed for the current result."
        )

        post_row.addWidget(self.btn_manual_knots_toggle, 2)
        post_row.addWidget(self.btn_corridor_toggle, 1)
        action_card.body.addLayout(post_row)

        self.lbl_postprocess_hint = QLabel("Recommended flow: Run -> Manual knots -> Corridors / RMSE(d)")
        self.lbl_postprocess_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        action_card.body.addWidget(self.lbl_postprocess_hint)
        action_card.body.addWidget(self.lbl_corridors_run_state)

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.stateChanged.connect(self._on_corridor_chk_state_changed)

        # Progress + status
        self.progress_widget = EnhancedProgressWidget(main_label="Optimization")
        action_card.body.addWidget(self.progress_widget)
        self.prog = self.progress_widget

        self.lbl_status = CertusStatusPill("Ready", "ready")
        self.lbl_status.setToolTip("Last action or error; details in the Log tab.")
        action_card.body.addWidget(self.lbl_status)

        reset_btn = create_reset_button(self, use_app_reset=True)
        reset_btn.setToolTip("Clear all and return to first-launch state: no spectrum, no result, default controls.")
        action_card.body.addWidget(reset_btn)

        self.action_card = action_card
        left_lay.addWidget(action_card)
        left_lay.addStretch(1)
        left_scroll.setWidget(left_inner)

        # ── Log panel ─────────────────────────────────────────────────────────
        self.log_panel = CertusLogPanel(title="LOG")
        self.log_panel.setMinimumHeight(140)
        self.log_text = self.log_panel.log_text
        self.widgets["log_text"] = self.log_text

        # ── Context stack (tab-specific settings) ─────────────────────────────
        self.context_stack = QStackedWidget()
        scroll_ctx = QScrollArea()
        scroll_ctx.setWidgetResizable(True)
        scroll_ctx.setFrameShape(QFrame.Shape.NoFrame)
        scroll_ctx.setWidget(self.context_stack)
        scroll_ctx.setStyleSheet("background: transparent;")

        aux_tabs = QTabWidget()
        aux_tabs.setDocumentMode(True)
        aux_tabs.addTab(scroll_ctx, "Context")
        aux_tabs.addTab(self.log_panel, "Logs")
        aux_tabs.setToolTip("Additional controls and runtime logs for the current workflow tab.")

        # ── Right panel: resizable sidebar stack ──────────────────────────────
        info_panel = QSplitter(Qt.Orientation.Vertical)
        info_panel.setChildrenCollapsible(False)
        info_panel.setHandleWidth(14)
        info_panel.setObjectName("indexSplineInfoSplit")
        info_panel.setStyleSheet(
            "#indexSplineInfoSplit::handle { background-color: #7a8798; }"
            "#indexSplineInfoSplit::handle:hover { background-color: #4f9cff; }"
        )
        info_panel.setMinimumWidth(left_scroll.minimumWidth())
        info_panel.addWidget(left_scroll)
        info_panel.addWidget(aux_tabs)
        info_panel.setStretchFactor(0, 8)
        info_panel.setStretchFactor(1, 2)
        info_panel.setSizes([720, 180])
        self.info_split = info_panel

        # ── Plots panel ───────────────────────────────────────────────────────
        plots_panel = self._build_plot_tabs_panel()
        self.tabs_main.currentChanged.connect(self._sync_context_panel_to_current_tab)

        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.setChildrenCollapsible(False)
        self.main_split.setHandleWidth(14)
        self.main_split.setObjectName("indexSplineMainSplit")
        self.main_split.setStyleSheet(
            "#indexSplineMainSplit::handle { background-color: #7a8798; }"
            "#indexSplineMainSplit::handle:hover { background-color: #4f9cff; }"
        )
        # UX: keep inputs on the left and plots on the right for a natural flow.
        self.main_split.addWidget(info_panel)
        self.main_split.addWidget(plots_panel)
        # setCollapsible needs existing widget indices — never call before addWidget.
        nc = int(self.main_split.count())
        if nc >= 1:
            self.main_split.setCollapsible(0, True)
        if nc >= 2:
            self.main_split.setCollapsible(1, True)
        # Default with a visibly wider workflow pane so the RMSE(d) tab stays closer to a square plot.
        self.main_split.setStretchFactor(0, 3)
        self.main_split.setStretchFactor(1, 2)
        self.main_split.setSizes([960, 640])
        self._enforce_main_splitter_ratio_bounds(persist=False)
        self.main_split.splitterMoved.connect(self._on_main_splitter_moved)
        self.info_split.splitterMoved.connect(self._persist_splitter_states)

        root_layout.addWidget(self.main_split)

        self._sync_context_panel_to_current_tab()

        self._refresh_corridors_gui_state_labels()
        self._refresh_post_optimization_option_controls()

    def _on_stepper_activated(self, step_index: int) -> None:

        idx = int(max(0, min(step_index, 6)))
        if hasattr(self, "_stepper"):
            self._stepper.set_step(idx)

        if idx == 0:
            self._reveal_sidebar_widget(getattr(self, "file_card", None))
            if hasattr(self, "tabs_main"):
                self.tabs_main.setCurrentIndex(0)

        if idx == 0 and hasattr(self, "btn_load"):
            self.btn_load.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx in (1, 2, 3) and hasattr(self, "params_collapsible"):
            self.params_collapsible.set_expanded(True)
            self._reveal_sidebar_widget(self.params_collapsible)

        if idx == 1 and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        if idx == 1 and hasattr(self, "cb_sub"):
            self.cb_sub.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 2 and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        if idx == 2 and hasattr(self, "chk_t"):
            self.chk_t.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 3 and hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_indices"):
            self.tabs_main.setCurrentIndex(int(self._idx_tab_indices))

        if idx == 3 and hasattr(self, "cb_profilee"):
            self.cb_profilee.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 4:
            self._reveal_sidebar_widget(getattr(self, "action_card", None))

        if idx == 4 and hasattr(self, "btn_run"):
            self.btn_run.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 5:
            self._reveal_sidebar_widget(getattr(self, "action_card", None))
            if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_indices"):
                self.tabs_main.setCurrentIndex(int(self._idx_tab_indices))

        if idx == 5 and hasattr(self, "btn_manual_knots_toggle"):
            self.btn_manual_knots_toggle.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self._reveal_sidebar_widget(getattr(self, "action_card", None))
        if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_corridor_rmse"):
            try:
                self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor_rmse))
            except (TypeError, ValueError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        if hasattr(self, "btn_corridor_toggle"):
            self.btn_corridor_toggle.setFocus(Qt.FocusReason.OtherFocusReason)

    def _reveal_sidebar_widget(self, widget: QWidget | None) -> None:

        if not isinstance(widget, QWidget):
            return
        scroll = getattr(self, "left_scroll", None)
        if isinstance(scroll, QScrollArea):
            scroll.ensureWidgetVisible(widget, 0, 24)

    def _build_basic_step3_spectral_targets(self, parent_layout: "QVBoxLayout", style: str) -> None:
        box3 = CertusCard("3  What to fit on the spectrum (T, T/Tsub, R)")

        box3.setStyleSheet(style)
        box3.body.setContentsMargins(6, 4, 6, 4)
        box3.body.setSpacing(4)

        box3.setToolTip(
            "Step 3: define what the T column represents. Checked = T_film/T_bare_sub ratio "
            "(and R/T_bare_sub if R), often in % (100 = ratio 1). Unchecked = absolute T and R. "
            "wT / wR weight RMSE when both channels are active."
        )

        g3 = QGridLayout()
        g3.setContentsMargins(0, 0, 0, 0)
        g3.setHorizontalSpacing(6)
        g3.setVerticalSpacing(4)

        box3.body.addLayout(g3)

        parent_layout.addWidget(box3)

        r3 = 0

        self.chk_t = QCheckBox("Fit transmission T")

        self.chk_t.setChecked(True)

        self.chk_t.setToolTip("Include file T column in objective. Disable only when fitting R only.")

        g3.addWidget(self.chk_t, r3, 0, 1, 2)

        r3 += 1

        self.chk_trel = QCheckBox("T = T_film / T_substrate (ratio, e.g. % -> fraction)")

        self.chk_trel.setChecked(True)

        self.chk_trel.setToolTip(
            "Checked (usual case): T column is T_film / bare-substrate T ratio (backside included), same for R. "
            "Often provided in percent (100 = ratio 1). Fit compares against ratio model without dividing by T_sub again. "
            "Unchecked: columns are absolute transmission/reflection (or %). "
            "RMSE objective uses ln lambda weighting and optional mixed T/R loss."
        )

        self.chk_trel.toggled.connect(self._on_trel_plot_refresh)

        g3.addWidget(self.chk_trel, r3, 0, 1, 2)

        r3 += 1

        self.chk_r = QCheckBox("Fit reflection R (if R column exists)")

        self.chk_r.setToolTip("Requires an R column; combines T and R if both are enabled and wR > 0.")

        g3.addWidget(self.chk_r, r3, 0, 1, 2)

        r3 += 1

        lb_w = QLabel("Weights in MSE:")

        lb_w.setToolTip("wT and wR weight T and R errors respectively (mixed mode). Use wR = 0 for T-only fitting.")

        g3.addWidget(lb_w, r3, 0)

        self.w_t = QDoubleSpinBox()

        self.w_t.setRange(0.0, 100.0)

        self.w_t.setValue(1.0)

        self.w_t.setToolTip("Relative weight of T error in global RMSE.")

        self.w_r = QDoubleSpinBox()

        self.w_r.setRange(0.0, 100.0)

        self.w_r.setValue(1.0)

        self.w_r.setToolTip("Relative weight of R error. Set to 0 to ignore R in fitting.")

        h_w = QHBoxLayout()
        h_w.setSpacing(4)

        h_w.addWidget(QLabel("wT"))

        h_w.addWidget(self.w_t)

        h_w.addWidget(QLabel("wR"))

        h_w.addWidget(self.w_r)

        hw = QWidget()

        hw.setLayout(h_w)

        g3.addWidget(hw, r3, 1)

        parent_layout.addWidget(box3)

        btn_rmse_win = create_styled_button("Spectral RMSE window (lambda)...", "secondary")

        btn_rmse_win.setToolTip(
            "Limits the wavelengths used in the optimization MSE/RMSE. "
            "The displayed spectrum remains complete; only points in the band count for the adjustment."
        )

        btn_rmse_win.clicked.connect(self._on_rmse_fit_window_dialog)

        parent_layout.addWidget(btn_rmse_win)

    def _build_corridor_tab_generate(self, lay_generate: "QVBoxLayout") -> None:
        lay_generate.setSpacing(6)

        lbl_manual = QLabel("Alternative path: define a manual interval around d* and generate a corridor directly.")
        lbl_manual.setWordWrap(True)
        lbl_manual.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay_generate.addWidget(lbl_manual)

        row_manual = QHBoxLayout()

        row_manual.addWidget(QLabel("Manual centered corridor (+/- nm):"))

        self.sl_corridor_manual_half = QSlider(Qt.Orientation.Horizontal)

        self.sl_corridor_manual_half.setRange(0, 1)

        self.sl_corridor_manual_half.setValue(0)

        self.sl_corridor_manual_half.setSingleStep(1)

        self.sl_corridor_manual_half.setPageStep(5)

        self.sl_corridor_manual_half.setTickPosition(QSlider.TickPosition.TicksBelow)

        self.sl_corridor_manual_half.setEnabled(False)

        self.sl_corridor_manual_half.setToolTip(
            "<b>Cursor: Manual Width (±Δd)</b><br>"
            "Set the corridor width manually to generate the n, k, and L envelopes.<br>"
            "The generated corridor will be [d* - Δd, d* + Δd]."
        )

        self.sl_corridor_manual_half.setStyleSheet(slider_corridor_half_stylesheet())

        self.sl_corridor_manual_half.valueChanged.connect(self._on_corridor_manual_slider_changed)

        row_manual.addWidget(self.sl_corridor_manual_half, 1)

        self.lbl_corridor_manual_half = QLabel("+/-0.00 nm")

        self.lbl_corridor_manual_half.setMinimumWidth(90)

        row_manual.addWidget(self.lbl_corridor_manual_half)

        self.btn_corridor_manual_robust = create_styled_button("Use robust interval", "secondary", parent=self)

        self.btn_corridor_manual_robust.setEnabled(False)

        self.btn_corridor_manual_robust.setToolTip(
            "<b>Synchronize with Robust Interval</b><br>"
            "Automatically aligns the manual slider to the width calculated by the parabola (purple/orange).<br>"
            "Use this to restart from the smart suggestion before manual fine-tuning."
        )

        self.btn_corridor_manual_robust.clicked.connect(self._use_robust_corridor_interval)

        row_manual.addWidget(self.btn_corridor_manual_robust)

        self.btn_generate_manual_corridor = create_styled_button(
            "Generate corridor from selected interval", "primary", parent=self
        )

        self.btn_generate_manual_corridor.setEnabled(False)

        self.btn_generate_manual_corridor.setToolTip(
            "<b>Generate visual n/k/L corridor</b><br>"
            "Reconstruct and display the uncertainty envelopes on the Indices tab "
            "as corridors surrounding the nominal model."
        )

        self.btn_generate_manual_corridor.clicked.connect(self._apply_manual_corridor_selection)

        row_manual.addWidget(self.btn_generate_manual_corridor)

        lay_generate.addLayout(row_manual)

        row_manual_meta = QHBoxLayout()

        self.lbl_corridor_manual_dmin = QLabel("d_min: -")

        self.lbl_corridor_manual_dcenter = QLabel("d*: -")

        self.lbl_corridor_manual_dmax = QLabel("d_max: -")

        self.lbl_corridor_manual_interval = QLabel("Manual interval: -")

        for _lab in (
            self.lbl_corridor_manual_dmin,
            self.lbl_corridor_manual_dcenter,
            self.lbl_corridor_manual_dmax,
            self.lbl_corridor_manual_interval,
        ):
            _lab.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        row_manual_meta.addWidget(self.lbl_corridor_manual_dmin)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dcenter)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dmax)
        row_manual_meta.addStretch(1)
        row_manual_meta.addWidget(self.lbl_corridor_manual_interval)
        lay_generate.addLayout(row_manual_meta)

    def _build_tab_data(self) -> QWidget:

        # Contr?les d?plac?s ? droite
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()

        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()

        self.btn_copy_nk = create_styled_button("Copy full table (TSV)", "secondary")

        self.btn_copy_nk.setEnabled(False)

        self.btn_copy_nk.setToolTip("All columns (lambda, n?, k?) - Excel paste")

        self.btn_copy_nk.clicked.connect(self._copy_nk_to_clipboard)

        tb.addWidget(self.btn_copy_nk)

        self.btn_export_nk = create_styled_button("Export CSV...", "primary")

        self.btn_export_nk.setEnabled(False)

        self.btn_export_nk.clicked.connect(self._export_nk_csv)

        tb.addWidget(self.btn_export_nk)

        tb.addStretch(1)

        ctx_lay.addLayout(tb)

        spl_prev = QSplitter(Qt.Orientation.Horizontal)

        self.plot_data_preview_n = CertusScientificPlot(
            title="n preview",
            y_label="n",
            x_label="lambda (nm)",
        )

        self.plot_data_preview_n.showGrid(x=True, y=True, alpha=0.25)

        self.plot_data_preview_k = CertusScientificPlot(
            title="k preview",
            y_label="k",
            x_label="lambda (nm)",
        )

        self.plot_data_preview_k.showGrid(x=True, y=True, alpha=0.25)

        _apply_fixed_log_k_axis(self.plot_data_preview_k)

        spl_prev.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_data_preview_n))

        spl_prev.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_data_preview_k))

        spl_prev.setStretchFactor(0, 1)

        spl_prev.setStretchFactor(1, 1)

        lay.addWidget(spl_prev, 1)

        self.table_nk = ExcelTableWidget()

        self.table_nk.setColumnCount(9)

        self.table_nk.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n_alpha",
                "n env min",
                "n env max",
                "k",
                "k_alpha",
                "k env min",
                "k env max",
            ]
        )

        self.table_nk.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)

        self.table_nk.horizontalHeader().setStretchLastSection(True)

        self.table_nk.setToolTip(
            "lambda grid by spectral region: 2 nm step (<=400 nm), 5 nm (400-1200 nm), "
            "10 nm beyond; n, k and envelopes interpolated from result mesh. "
            "n_alpha / k_alpha: nonlinear indices if available. "
            "Envelopes: corridor bounds (d profiling). "
            "Previews: all n (or k) curves, envelope band if corridor; synchronized lambda cursor. "
            "Ctrl+C: copy selection (TSV) -> Excel."
        )

        lay.addWidget(self.table_nk, 2)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)
        # Sync for Log and CERTUS tabs

        return panel

    def _build_tab_data_th(self) -> QWidget:
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()
        self.btn_copy_data_th = create_styled_button("Copy Data TH table (TSV)", "secondary")
        self.btn_copy_data_th.setEnabled(False)
        self.btn_copy_data_th.setToolTip("Copie toutes les colonnes de Data TH (TSV) vers le clipboard.")
        self.btn_copy_data_th.clicked.connect(self._copy_data_th_to_clipboard)
        tb.addWidget(self.btn_copy_data_th)
        tb.addStretch(1)
        lay.addLayout(tb)

        hint = QLabel(
            "Theoretical table on a piecewise lambda grid: 2 nm (<=400), 5 nm (400-1200), 10 nm (>1200). "
            "Colonnes: lambda, n, k, d, ns, Tth, Rth."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(hint)

        self.table_data_th = ExcelTableWidget()
        self.table_data_th.setColumnCount(7)
        self.table_data_th.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
        self.table_data_th.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        self.table_data_th.horizontalHeader().setStretchLastSection(True)
        self.table_data_th.setToolTip(
            "Theoretical grid aligned on reporting lambda mesh. Refreshed from best-live snapshot during optimization."
        )
        lay.addWidget(self.table_data_th, 1)

        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        return panel

    def _build_basic_step2_substrate_thickness(self, parent_layout: "QVBoxLayout", style: str) -> None:
        box2 = CertusCard("2  Substrate n(lambda) & layer thickness d (nm)")

        box2.setStyleSheet(style)
        box2.body.setContentsMargins(6, 4, 6, 4)
        box2.body.setSpacing(4)

        box2.setToolTip(
            "Step 2: set substrate optical index n_sub(lambda) and single-layer thickness bounds. "
            "This must be physically consistent before running the fit."
        )

        g2 = QGridLayout()
        g2.setContentsMargins(0, 0, 0, 0)
        g2.setHorizontalSpacing(6)
        g2.setVerticalSpacing(4)

        box2.body.addLayout(g2)

        parent_layout.addWidget(box2)

        r = 0

        row_d = QHBoxLayout()
        row_d.setSpacing(6)

        lb_dnom = QLabel("d_nominal (nm) :")

        lb_dnom.setToolTip("Nominal layer thickness around which search bounds are built.")

        row_d.addWidget(lb_dnom)

        self.d_lo = QDoubleSpinBox()

        self.d_lo.setRange(1.0, 50000.0)

        self.d_lo.setValue(0.5 * float(SIO2_DEFAULT_D_LO_NM + SIO2_DEFAULT_D_HI_NM))

        self.d_lo.setToolTip("Nominal thickness d0 (nm). Effective bounds are d0 +/- Delta.")

        row_d.addWidget(self.d_lo)

        lb_dpm = QLabel("+/- (nm) :")

        lb_dpm.setToolTip("Half-width Delta (nm) around d_nominal used for optimization bounds.")

        row_d.addWidget(lb_dpm)

        self.d_hi = QDoubleSpinBox()

        self.d_hi.setRange(0.1, 25000.0)

        self.d_hi.setValue(0.5 * float(SIO2_DEFAULT_D_HI_NM - SIO2_DEFAULT_D_LO_NM))

        self.d_hi.setToolTip("Half-width Delta (nm): optimization bounds are [d_nominal - Delta, d_nominal + Delta].")

        row_d.addWidget(self.d_hi)

        row_d.addStretch(1)

        g2.addLayout(row_d, r, 0, 1, 2)

        r += 1

        lb_sub = QLabel("Substrate :")

        lb_sub.setToolTip("Bare substrate material used to compute T_sub and the multilayer model (CERTUS list).")

        g2.addWidget(lb_sub, r, 0)

        self.cb_sub = QComboBox()

        for name in allowed_substrate_names():
            self.cb_sub.addItem(name, name)

        # Default: Sapphire (Al2O3)

        idx_sapphire = self.cb_sub.findText("Sapphire (Al2O3)", Qt.MatchFlag.MatchContains)

        if idx_sapphire >= 0:
            self.cb_sub.setCurrentIndex(idx_sapphire)

        self.cb_sub.setToolTip("Select the same substrate used for measurement (internal tabulated dispersion).")

        g2.addWidget(self.cb_sub, r, 1)

        g2.setColumnStretch(1, 1)

        parent_layout.addWidget(box2)

    def _build_plot_tabs_panel(self) -> QWidget:
        """Right panel (Swanepoel type): detach bar + graphical tabs."""

        self.tabs_main = QTabWidget()
        self._tab_context_widgets: dict[QWidget, QWidget] = {}
        self._pending_context_page: QWidget | None = None

        self._add_plot_tab(self._build_tab_spectrum(), "Spectrum T / R")

        self._idx_tab_indices = self._add_plot_tab(self._build_tab_indices(), "n & k")

        self._tab_corridor_panel = self._build_tab_corridor()

        self._idx_tab_corridor = self._add_plot_tab(self._tab_corridor_panel, "Corridors n/k")

        self._tab_corridor_rmse_panel = self._build_tab_corridor_rmse()

        self._idx_tab_corridor_rmse = self._add_plot_tab(self._tab_corridor_rmse_panel, "Corridor RMSE(d)")

        self._add_plot_tab(self._build_tab_data(), "Data")
        self._add_plot_tab(self._build_tab_data_th(), "Data TH")
        self._add_plot_tab(self._build_tab_data_corridor(), "Data Corridor")

        self._add_plot_tab(
            self._build_tab_log(),
            "Log",
            context_widget=self._add_context_page(
                self._create_empty_context_widget("Optimization log and real-time computation diagnostics.")
            ),
        )

        self._add_plot_tab(
            self._build_tab_why(),
            "CERTUS",
            context_widget=self._add_context_page(
                self._create_empty_context_widget("Scientific references and methodology for the Spline model.")
            ),
        )

        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(6, 2, 6, 2)
        detach_btn = create_styled_button("⬡  Detach plot", "secondary")
        detach_btn.setFixedHeight(24)
        detach_btn.setToolTip("Clone the first plot of the active tab into a floating window (Ctrl+Shift+D on plot).")
        detach_btn.clicked.connect(self._detach_current_plot)
        hl.addWidget(detach_btn)
        hl.addStretch(1)

        out = QWidget()
        vl = QVBoxLayout(out)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(hdr)
        vl.addWidget(self.tabs_main, 1)
        return out

    def _add_context_page(self, widget: QWidget) -> QWidget:

        self.context_stack.addWidget(widget)
        self._pending_context_page = widget
        return widget

    def _consume_pending_context_page(self) -> QWidget | None:

        page = getattr(self, "_pending_context_page", None)
        self._pending_context_page = None
        return page if isinstance(page, QWidget) else None

    def _add_plot_tab(
        self,
        tab_widget: QWidget,
        label: str,
        *,
        context_widget: QWidget | None = None,
    ) -> int:

        idx = self.tabs_main.addTab(tab_widget, label)
        ctx = context_widget if context_widget is not None else self._consume_pending_context_page()
        if isinstance(ctx, QWidget):
            self._tab_context_widgets[tab_widget] = ctx
        return idx

    def _sync_context_panel_to_current_tab(self, *_args) -> None:

        if not hasattr(self, "tabs_main") or not hasattr(self, "context_stack"):
            return
        current_tab = self.tabs_main.currentWidget()
        if not isinstance(current_tab, QWidget):
            return
        ctx = getattr(self, "_tab_context_widgets", {}).get(current_tab)
        if isinstance(ctx, QWidget):
            self.context_stack.setCurrentWidget(ctx)

    def _build_corridor_labels(self, ctx_lay: "QVBoxLayout") -> None:
        """Tab for corridor profile RMSE as a function of thickness d."""

        panel = QWidget()

        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        _INTELLIGENT_DD_TOOLTIP = (
            "<b>Intelligent Deltad (automatic interval)</b><br>"
            "Two <b>orange</b> lines indicate the interval [d_lo, d_hi] calculated "
            "automatically by the profiling code (<tt>profile_d_interval_nm</tt>).<br><br>"
            "<b>Scientific Principle:</b><br>"
            "The algorithm explores the <i>profile likelihood</i> (minimal RMSE at each thickness d) "
            "and fits a local parabola: <b>RMSE ? c2?(d-d*)^2 + RMSE*</b>.<br><br>"
            "<b>Curvature &harr; Width Link:</b><br>"
            "The curvature <b>c2</b> represents the <b>sensitivity</b> of the fit to thickness:<br>"
            "&bull; A <b>high curvature</b> (narrow valley) means the RMSE increases quickly if d deviates from d* : "
            "the solution is well localized, the corridor is <b>tight</b>.<br>"
            "&bull; A <b>low curvature</b> (flat valley) means many thicknesses yield a nearly identical fit : "
            "the uncertainty is large, the corridor is <b>wide</b>.<br><br>"
            "<b>Final Calculation:</b><br>"
            "&bull; The excursion is <b>Deltad = &radic;(DeltaRMSE / c2)</b>, thus inversely proportional to the square root of the curvature.<br>"
            "&bull; <b>DeltaRMSE</b> is estimated dynamically from the residual noise (MAD) and geometric criteria.<br>"
            "&bull; A floor of <b>&plusmn;0.2% of d</b> is always applied for robustness."
        )

        hint = QLabel(
            "<b>RMSE(d) corridor profile</b> at all points calculated during profiling. "
            "Raw scatter (unconnected). The <b>parabola</b> is fitted to the min-RMSE envelope by thickness.<br>"
            "<span style='color:#ff8c00;'>&#9646;</span> = Smart Deltad (automatic interval) | "
            "<span style='color:#7a3cff;'>&#9646;</span> = local robust interval | "
            "<span style='color:#ff4d4f;'>&#9646;</span> = manual selection."
        )

        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        ctx_lay.addWidget(hint)

        self.lbl_corridor_rmse_summary = QLabel("No corridor RMSE profile available yet.")
        self.lbl_corridor_rmse_summary.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridor_rmse_summary.setToolTip(
            "<b>Final quality summary</b><br>"
            "Displays the globally optimized thickness d* found on the grid "
            "as well as the RMSE corresponding to the absolute minimum."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_summary)
        self.lbl_corridor_rmse_robust_compact = QLabel("Robust interval: -")
        self.lbl_corridor_rmse_robust_compact.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridor_rmse_robust_compact.setToolTip(
            "<b>Robust interval (compact format)</b><br>"
            "Displays the center and half-width in the form "
            "<code>xxx.xx nm +/- xxx.nm</code>."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_robust_compact)

        self.lbl_corridor_rmse_state = QLabel("Step 1/3: Recalculate RMSE(d) to start.")
        self.lbl_corridor_rmse_state.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_corridor_rmse_state.setToolTip(
            "<b>Progress / Diagnostic</b><br>"
            "Displays the current pipeline step (Calculation, Fit, or Export) "
            "and any alert messages related to convergence."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_state)

    def _build_tab_corridor(self) -> QWidget:
        # Controls and help moved to the right
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        hint = QLabel(
            "<b>Acceptance envelope (profiling in d)</b> - n(lambda) and k(lambda) bands after optimization. "
            "Calculation starts from the <b>best polished spectral RMSE</b> ('best RMSE' + RMSE_ref+Delta default): "
            "the displayed reference curve is the scientific nominal, and the envelope groups models whose "
            "masked RMSE remains <= RMSE<sub>best</sub> + Delta. This is not a Bayesian confidence interval."
            "<br><br>"
            "<b>Automatic</b> execution at the end of the run if 'Corridors n/k -> Enable' is checked. "
            "Opened by itself when corridors or bootstrap are available."
            "<br><br>"
            "<b>log10 k:</b> the <b>bold</b> orange curve follows the main optimization result ('n &amp; log10 k' tab). "
            "Shaded area = min/max of linear <i>k</i> from refits accepted at various <i>d</i> "
            "(without corrective widening in scientific mode). The <b>dashed</b> orange curve appears only if a central refit "
            "differs significantly from the bold curve. <b>Crosshair:</b> the value follows the bold curve at the cursor lambda."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        ctx_lay.addWidget(hint)

        self.lbl_corridors_tab_state = QLabel()
        self.lbl_corridors_tab_state.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_corridors_tab_state.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridors_tab_state.setToolTip("Corridor option state in the UI for the next optimization run.")
        ctx_lay.addWidget(self.lbl_corridors_tab_state)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_n_corridor = CertusScientificPlot(title="n(lambda) + corridors", y_label="n", x_label="lambda (nm)")

        self.plot_n_corridor.showGrid(x=True, y=True, alpha=0.25)

        self.plot_k_corridor = CertusScientificPlot(title="k(lambda) + corridors", y_label="k", x_label="lambda (nm)")

        self.plot_k_corridor.showGrid(x=True, y=True, alpha=0.25)
        _apply_fixed_log_k_axis(self.plot_k_corridor)
        self.plot_k_corridor._certus_crosshair_label_fn = self._k_corridor_crosshair_formatter
        self.plot_k_corridor._certus_crosshair_vertical_only = True

        spl = QSplitter(Qt.Orientation.Vertical)

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_n_corridor))

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_k_corridor))

        spl.setStretchFactor(0, 1)

        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        return panel

class _CorridorExportMixin:
    """Mixin containing corridor and nk export methods."""

    def _ensure_complete_manifest_for_secondary_export(self) -> bool:

        from certus.utils.certus_data import get_missing_manifest_fields

        result = getattr(self, "_last_result", None)
        manifest_dict = result.get("run_manifest") if isinstance(result, dict) else None
        missing_manifest_fields = get_missing_manifest_fields(
            manifest_dict if isinstance(manifest_dict, dict) else None
        )
        if not missing_manifest_fields:
            return True

        msg = "Export blocked: incomplete manifest (" + ", ".join(missing_manifest_fields) + ")"
        if hasattr(self, "logger"):
            self.logger.error("INDEX_SPLINE secondary export blocked: %s", msg)
        QMessageBox.warning(self, "Export blocked", msg)
        return False

    def _export_corridor_rmse_profile_clipboard(self) -> None:
        """Clipboard: RMSE(d) data, local parabolic fit, robust interval."""

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        if d_s.size == 0 or r_s.size != d_s.size:
            QMessageBox.information(self, "Export data", "No RMSE(d) curve in memory.")

            return

        lines: list[str] = []

        lines.append("# CERTUS INDEX-SPLINE ? Corridor RMSE(d) export")

        lines.append("# section: profile_points")

        lines.append("d_nm\tRMSE")

        for di, ri in zip(d_s.tolist(), r_s.tolist()):
            lines.append(f"{float(di):.8f}\t{float(ri):.10f}")

        par = getattr(self, "_corridor_rmse_parab_export", None)

        if isinstance(par, dict) and bool(par.get("ok", False)):
            lines.append("# section: local_parabolic_fit (x = d - anchor_nm)")

            lines.append("anchor_nm\tc2\tc1\tc0\td_center_nm\td_lo_fit_nm\td_hi_fit_nm")

            c2, c1, c0 = par.get("coeffs", (float("nan"),) * 3)

            wlo, whi = par.get("window_nm", (float("nan"), float("nan")))

            lines.append(
                f"{float(par.get('anchor_nm', float('nan'))):.8f}\t{float(c2):.10e}\t{float(c1):.10e}\t{float(c0):.10e}\t"
                f"{float(par.get('d_center', float('nan'))):.8f}\t{float(wlo):.8f}\t{float(whi):.8f}"
            )

        else:
            lines.append("# section: local_parabolic_fit")

            lines.append("# (unavailable ? need ?5 local points for convex quadratic fit)")

        rb = getattr(self, "_corridor_rmse_robust_export", None)

        if isinstance(rb, dict) and bool(rb.get("ok", False)):
            lines.append("# section: robust_interval (from local quadratic + Delta RMSE)")

            lines.append("d_lo_nm\td_hi_nm\tslope_at_dstar_per_nm\tcurvature_c2")

            lines.append(
                f"{float(rb.get('d_lo', float('nan'))):.8f}\t{float(rb.get('d_hi', float('nan'))):.8f}\t"
                f"{float(rb.get('slope', float('nan'))):.10e}\t{float(rb.get('curvature', float('nan'))):.10e}"
            )

        else:
            lines.append("# section: robust_interval")
            lines.append("# (unavailable)")

        # Intelligent interval (automatic from code outcome)
        src = self._corridor_profile_source_result() or {}
        _int_nm = src.get("profile_d_interval_nm", None) if isinstance(src, dict) else None
        if isinstance(_int_nm, (tuple, list)) and len(_int_nm) == 2:
            lines.append("# section: intelligent_interval (automatic code outcome)")
            lines.append("d_lo_auto_nm\td_hi_auto_nm")
            lines.append(f"{float(_int_nm[0]):.8f}\t{float(_int_nm[1]):.8f}")
        else:
            lines.append("# section: intelligent_interval")
            lines.append("# (unavailable)")

        # Manual interval (user selection)
        d_lo_man = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))
        d_hi_man = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))
        if np.isfinite(d_lo_man) and np.isfinite(d_hi_man):
            lines.append("# section: manual_interval (user selection)")
            lines.append("d_lo_manual_nm\td_hi_manual_nm\tactive_status")
            _status = "ACTIVE" if bool(getattr(self, "_corridor_rmse_manual_active", False)) else "PREVIEW"
            lines.append(f"{d_lo_man:.8f}\t{d_hi_man:.8f}\t{_status}")
        else:
            lines.append("# section: manual_interval")
            lines.append("# (not set)")

        # Breakpoint events (diagnostic)
        bp_ev = src.get("profile_d_manual_grid_breakpoint_events", []) if isinstance(src, dict) else []
        if isinstance(bp_ev, list) and bp_ev:
            lines.append("# section: breakpoint_events")
            lines.append("d_nm\ttrigger\tbranch_dir")
            for ev in bp_ev:
                if not isinstance(ev, dict):
                    continue
                _db = float(ev.get("d_break_nm", float("nan")))
                _tr = "parabola" if float(ev.get("trigger_parabola", 0)) > 0.5 else "prevN"
                _dir = "right" if float(ev.get("branch_dir_sign", 0)) > 0 else "left"
                lines.append(f"{_db:.8f}\t{_tr}\t{_dir}")
        else:
            lines.append("# section: breakpoint_events")
            lines.append("# (none detected)")

        txt = "\n".join(lines) + "\n"

        cb = QApplication.clipboard()

        if cb is None:
            QMessageBox.warning(self, "Export data", "Clipboard unavailable.")

            return

        cb.setText(txt)

        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("RMSE(d) profile + parabola + robust interval copied to clipboard (TSV).")

    def _export_corridor_rmse_envelope_nk_excel(self) -> None:
        """Excel Export: 2 sheets (n, k) for RMSE(d) envelope points, on 2/5/10 nm grids."""
        if not self._ensure_complete_manifest_for_secondary_export():
            return

        source = self._corridor_profile_source_result()

        display = self._last_result if isinstance(self._last_result, dict) else {}

        if not isinstance(source, dict):
            QMessageBox.information(self, "Export enveloppe n/k", "No RMSE(d) source data available.")

            return

        d_vals = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        r_vals = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)

        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)

        if d_vals.size == 0 or r_vals.size != d_vals.size or n_curves.ndim != 2 or k_curves.ndim != 2:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "No valid RMSE(d)/n/k grid in memory.",
            )

            return

        if n_curves.shape[0] != d_vals.size or k_curves.shape != n_curves.shape or n_curves.shape[1] == 0:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "n/k curves are not aligned with RMSE(d) points.",
            )

            return

        lam_ref = np.asarray(source.get("lam_nm", display.get("lam_nm", [])), dtype=np.float64).ravel()

        if lam_ref.size != n_curves.shape[1]:
            alt_lam = np.asarray(display.get("lam_nm", []), dtype=np.float64).ravel()

            lam_ref = alt_lam if alt_lam.size == n_curves.shape[1] else lam_ref

        if lam_ref.size != n_curves.shape[1]:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "Wavelength axis is unavailable or mismatched.",
            )

            return

        m = np.isfinite(d_vals) & np.isfinite(r_vals)

        if not np.any(m):
            QMessageBox.information(self, "Export enveloppe n/k", "No finite RMSE(d) points available.")

            return

        d_work = d_vals[m]

        r_work = r_vals[m]

        n_work = np.asarray(n_curves[m, :], dtype=np.float64)

        k_work = np.asarray(k_curves[m, :], dtype=np.float64)

        o_d = np.argsort(d_work)

        d_work = d_work[o_d]

        r_work = r_work[o_d]

        n_work = n_work[o_d, :]

        k_work = k_work[o_d, :]

        step_hint = (
            float(self.sp_corridor_grid_d_step_nm.value())
            if hasattr(self, "sp_corridor_grid_d_step_nm")
            else float("nan")
        )

        tol_nm = 0.55 * step_hint if np.isfinite(step_hint) and step_hint > 0.0 else float("nan")

        env_mask = _rmse_d_lower_envelope_mask(d_work, r_work, tol_nm)

        if not np.any(env_mask):
            QMessageBox.information(self, "Export enveloppe n/k", "No envelope points selected.")

            return

        d_env = d_work[env_mask]

        r_env = r_work[env_mask]

        n_env = n_work[env_mask, :]

        k_env = k_work[env_mask, :]

        ok_lam = np.isfinite(lam_ref)

        if int(np.sum(ok_lam)) < 2:
            QMessageBox.information(self, "Export enveloppe n/k", "Not enough finite wavelength points.")

            return

        lam_use = np.asarray(lam_ref[ok_lam], dtype=np.float64)

        n_env = np.asarray(n_env[:, ok_lam], dtype=np.float64)

        k_env = np.asarray(k_env[:, ok_lam], dtype=np.float64)

        o_lam = np.argsort(lam_use)

        lam_use = lam_use[o_lam]

        n_env = n_env[:, o_lam]

        k_env = k_env[:, o_lam]

        lam_min = float(np.nanmin(lam_use))

        lam_max = float(np.nanmax(lam_use))

        if not np.isfinite(lam_min) or not np.isfinite(lam_max) or lam_max <= lam_min:
            QMessageBox.information(self, "Export enveloppe n/k", "Invalid wavelength interval.")

            return

        ts = time.strftime("%Y%m%d_%H%M%S")

        out_default = str(Path.cwd() / f"RMSEd_envelope_nk_{ts}.xlsx")

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export n/k envelope (Excel)",
            out_default,
            "Excel Workbook (*.xlsx);;All Files (*.*)",
        )

        if not out_path:
            return

        if not out_path.lower().endswith(".xlsx"):
            out_path += ".xlsx"

        grid_steps = (2.0, 5.0, 10.0)
        lam_grids: dict[float, np.ndarray] = {}
        lam_parts: list[np.ndarray] = []
        for grid_step in grid_steps:
            start = float(np.ceil(lam_min / grid_step) * grid_step)
            stop = float(np.floor(lam_max / grid_step) * grid_step)
            if stop < start:
                lam_grid = np.asarray([lam_min, lam_max], dtype=np.float64)
            else:
                n_pts = int(np.floor((stop - start) / grid_step + 0.5)) + 1
                lam_grid = start + grid_step * np.arange(max(1, n_pts), dtype=np.float64)
            lam_grids[float(grid_step)] = np.asarray(lam_grid, dtype=np.float64)
            lam_parts.append(np.asarray(lam_grid, dtype=np.float64))

        lam_master = np.unique(np.concatenate(lam_parts)) if lam_parts else np.array([], dtype=np.float64)
        lam_master = np.asarray(np.sort(lam_master), dtype=np.float64)

        if lam_master.size == 0:
            QMessageBox.information(self, "Export enveloppe n/k", "No lambda grid available for export.")
            return

        idx_map = {round(float(v), 9): int(i) for i, v in enumerate(lam_master.tolist())}

        cols_n: dict[str, np.ndarray] = {"lambda_nm": lam_master.copy()}
        cols_k: dict[str, np.ndarray] = {"lambda_nm": lam_master.copy()}
        hdr_d: list[object] = ["lambda_nm"]
        hdr_rmse: list[object] = ["-"]

        for i in range(int(d_env.size)):
            for grid_step in grid_steps:
                lam_grid = lam_grids[float(grid_step)]
                n_interp = np.interp(lam_grid, lam_use, n_env[i, :], left=np.nan, right=np.nan)
                k_interp = np.interp(lam_grid, lam_use, k_env[i, :], left=np.nan, right=np.nan)

                col_n = np.full(lam_master.shape, np.nan, dtype=np.float64)
                col_k = np.full(lam_master.shape, np.nan, dtype=np.float64)
                for j, lam_v in enumerate(lam_grid):
                    pos = idx_map.get(round(float(lam_v), 9))
                    if pos is not None:
                        col_n[pos] = float(n_interp[j])
                        col_k[pos] = float(k_interp[j])

                col_name = f"p{i + 1:03d}_s{int(grid_step)}nm"
                cols_n[col_name] = col_n
                cols_k[col_name] = col_k
                hdr_d.append(f"{float(d_env[i]):.3f} @ {int(grid_step)}nm")
                hdr_rmse.append(float(r_env[i]))

        df_n = pd.DataFrame(cols_n)
        df_k = pd.DataFrame(cols_k)

        if df_n.empty or df_k.empty:
            QMessageBox.information(self, "Export enveloppe n/k", "No data to export.")

            return

        try:
            with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
                df_n.to_excel(writer, sheet_name="n", index=False, header=False, startrow=2)
                df_k.to_excel(writer, sheet_name="k", index=False, header=False, startrow=2)

                for sh_name in ("n", "k"):
                    ws = writer.sheets[sh_name]
                    # 2-line header:
                    #   row 1 -> d_nm
                    #   row 2 -> RMSE
                    for col_idx, (v_d, v_r) in enumerate(zip(hdr_d, hdr_rmse), start=1):
                        ws.cell(row=1, column=col_idx, value=v_d)
                        ws.cell(row=2, column=col_idx, value=v_r)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            QMessageBox.warning(
                self,
                "Export enveloppe n/k",
                f"Unable to write Excel file.\n{type(exc).__name__}: {exc}",
            )
            return

        if hasattr(self, "lbl_status"):
            self.lbl_status.setText(f"RMSE(d) envelope n/k exported: {out_path}")

        if self.logger:
            self.logger.info(
                "GUI RMSE(d) envelope n/k export (xlsx) | path=%s | envelope_points=%d | lambda_range=[%.6f, %.6f] nm | sheets=[n,k] | grids=[2,5,10] nm",
                str(out_path),
                int(d_env.size),
                float(lam_min),
                float(lam_max),
            )

    def _export_nk_csv(self) -> None:
        if not self._ensure_complete_manifest_for_secondary_export():
            return

        if self._last_result is None:
            QMessageBox.warning(self, "Export", "No result to export.")

            return

        start_dir = get_certus_last_dir()

        if not start_dir or not Path(start_dir).is_dir():
            start_dir = str(_SCRIPT_DIR)

        suggested = str(Path(start_dir) / "certus_index_spline_nk.csv")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export indices",
            suggested,
            "CSV (*.csv);;All (*.*)",
        )

        if not path:
            return

        ser = self._prepare_nk_data_tab_series(self._last_result)

        if ser is None:
            QMessageBox.warning(self, "Export", "Empty grid.")

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("lambda_nm,n,n_alpha,n_envelope_min,n_envelope_max,k,k_alpha,k_envelope_min,k_envelope_max\n")

                for i in range(m):
                    line = f"{float(lam_g[i]):.4f},"

                    line += self._fmt_n_data_tab(float(n_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_nl_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_lo_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_hi_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_nl_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_lo_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_hi_g[i])) + "\n"

                    fh.write(line)

            set_certus_last_dir(path)

            self.lbl_status.setText(f"CSV saved: {path}")

        except OSError as e:
            QMessageBox.critical(self, "Export", str(e))

class _RunMixin:
    """Mixin containing optimization run logic, live update and result plotting."""

    @safe_ui_action
    def _on_run(self) -> None:

        # Reinitialisation de la securite retour de dialog

        self._preview_ret = None

        cfg = self._build_opt_config()

        if cfg is None:
            return

        cfg.gui_run_pglobal_opt_in = False

        cfg.spline_local_only = True

        if hasattr(self, "_stepper"):
            self._stepper.set_step(4)

        if self.logger:
            self.logger.info("RUN local policy | spline_local_only=True")

        t_run_cfg = time.perf_counter()

        if self.logger:
            self.logger.info(
                "RUN config | n_seg=%s d=[%.2f,%.2f] wt=%.3f wr=%.3f profile=%s nk_interp=%s local_only=%s polish=%s mono=%s n_lambda_rise_slack=%.4f",
                int(cfg.n_seg),
                float(cfg.d_lo),
                float(cfg.d_hi),
                float(cfg.weight_t),
                float(cfg.weight_r),
                str(self.cb_profilee.currentData() or "fast"),
                str(cfg.nk_profile_interp),
                bool(cfg.spline_local_only),
                int(cfg.polish_maxfun),
                cfg.n_mono_band_nm,
                float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0),
            )

            log_structured_json_event(
                self.logger,
                "AUTO_BEST_JSON",
                "run_config",
                n_seg=int(cfg.n_seg),
                d_lo=float(cfg.d_lo),
                d_hi=float(cfg.d_hi),
                wt=float(cfg.weight_t),
                wr=float(cfg.weight_r),
                profile=str(self.cb_profilee.currentData() or "fast"),
                nk_profile_interp=str(cfg.nk_profile_interp),
                pg_iter=int(cfg.pglobal_max_iter),
                pg_feval=cfg.pglobal_max_feval,
                pg_time=cfg.pglobal_max_time,
                pg_local=cfg.pglobal_local_search_budget,
                polish=int(cfg.polish_maxfun),
                n_mono_band=cfg.n_mono_band_nm,
                n_lambda_rising_slack=float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0),
            )

        # Toujours forcer le mode Smart Init en "Auto-Best"

        if getattr(self, "_auto_best_force_smart_init", True):
            if self.logger:
                self.logger.info("Auto-Best: Smart Init dialog interception active.")

        self._save_undo_state()

        self.__class__._prepare_worker_restart(self)

        reset_smart_init_preview_guard(cfg)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_worker_result = None

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        self._log_prog_last = -1

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        self._log_optimization_header(cfg)

        cfg_run = cfg.replace(smart_init_preview_hook=self._smart_init_preview_hook)

        if self.logger:
            self.logger.info(
                "RUN SmartInit hook | cfg_run.smart_init_preview_hook=%s | preview_shown=%s | thread=%s",
                "set" if getattr(cfg_run, "smart_init_preview_hook", None) is not None else "none",
                bool(getattr(cfg_run, "smart_init_preview_shown", False)),
                type(QThread.currentThread()).__name__,
            )

        setattr(
            cfg_run,
            "gui_defer_corridor_profile_after_nl",
            bool(getattr(self, "chk_corridor_d", None) and self.chk_corridor_d.isChecked()),
        )

        self._last_run_cfg = cfg_run

        # CRITICAL: dataclasses.replace() does NOT copy dynamic attributes.

        # On les transfere manuallement pour que le worker voie l'injection manualle.

        for _attr in (
            "smart_preview_node_override",
            "smart_preview_exact_sigma_knots",
            "smart_preview_exact_n_L",
            "smart_preview_d_nm_override",
            "smart_preview_accepted_rmse",
            "spline_local_only",
            "smart_init_manual_force_restart",
            "gui_run_pglobal_opt_in",
        ):
            if hasattr(cfg, _attr):
                setattr(cfg_run, _attr, getattr(cfg, _attr))

        if self.logger:
            log_index_spline_d_trace(
                self.logger,
                "GUI: launching main worker (before SOL2)",
                None,
                detail=f"d bornes exploration cfg [{float(cfg_run.d_lo):.4f}, {float(cfg_run.d_hi):.4f}] nm",
            )

        self._worker = GenericWorker(worker_spline_optimization, cfg_run, self._stop_event)

        self._worker_role = "main"

        self._worker.kwargs["progress_cb"] = self._worker.signals.progress.emit

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.live.connect(self._on_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        # live_cb / _on_live_update : une seule connexion (?vite double _plot_result ? UI qui ? g?le ?).

        if self.logger:
            self.logger.info(
                "RUN dispatch worker=%s prep_elapsed=%.3fs",
                getattr(self._worker.func, "__name__", "?"),
                time.perf_counter() - t_run_cfg,
            )

        # one-shot gate: force smart init by default next time too (or rely on the fact it's permanent for auto-best)

        self._auto_best_force_smart_init = True

        self._worker.start()
        install_skeleton(self.tabs_main, label="Optimizing Spline Model...")

    def _on_live_update(self, result: dict) -> None:
        """Refresh during calculation: graphs = always the best RMSE snapshot (copied arrays)."""

        if not isinstance(result, dict):
            return

        if "lam_nm" not in result:
            if "profile_d_values_nm" in result:
                self._on_corridor_rmse_grid_live_update(result)

            return

        current_rmse = self._rmse_from_result_dict(result)

        prev_best_rmse = float(self._best_live_rmse)

        had_prior_best_snapshot = self._best_live_result is not None

        improved = False

        if np.isfinite(current_rmse) and (self._best_live_result is None or current_rmse < self._best_live_rmse):
            self._best_live_rmse = current_rmse

            self._best_live_result = _snap_spline_visual_dict(result)

            improved = True

        to_plot = self._best_live_result if self._best_live_result is not None else _snap_spline_visual_dict(result)

        now = time.monotonic()

        remind = (now - self._last_live_log_mono) >= self._LIVE_LOG_REMINDER_S

        if self.logger and self._best_live_result is not None and np.isfinite(self._best_live_rmse):
            if improved:
                self._last_live_log_mono = now

                abs_gain = float(prev_best_rmse - float(current_rmse))

                if not had_prior_best_snapshot or not np.isfinite(prev_best_rmse):
                    log_best_detail = True

                else:
                    min_step = max(
                        float(self._LIVE_BEST_DETAIL_MIN_ABS),
                        float(self._LIVE_BEST_DETAIL_MIN_REL) * max(float(prev_best_rmse), 1e-12),
                    )

                    log_best_detail = bool(
                        abs_gain >= min_step
                        or (now - float(self._live_best_detail_log_mono))
                        >= float(self._LIVE_BEST_DETAIL_MIN_INTERVAL_S)
                    )

                if log_best_detail:
                    self._live_best_detail_log_mono = now

                    _log_index_spline_best_config(
                        self.logger,
                        self._best_live_result,
                        float(self._best_live_rmse),
                        title="[BEST RMSE  live run record]",
                    )

            elif remind:
                self._last_live_log_mono = now

                sk = self._best_live_result.get("sigma_knots")

                k_sigma = int(np.asarray(sk, dtype=np.float64).size) if sk is not None else 0

                d_nm = float(self._best_live_result.get("d_nm", float("nan")))

                self.logger.info(
                    "[BEST DISPLAYED] reminder (~%.0f s) RMSE=%.6f | d_nm=%.2f | K_sigma=%d (detail: last record above)",
                    float(self._LIVE_LOG_REMINDER_S),
                    float(self._best_live_rmse),
                    d_nm,
                    k_sigma,
                )

        self._plot_result(to_plot, plot_source="live")

        self._refresh_data_table(result_override=to_plot)

        try:
            lam_u = np.asarray(to_plot.get("lam_nm", []), dtype=np.float64).ravel()

            n_u = np.asarray(to_plot.get("n_lam", []), dtype=np.float64).ravel()

            k_u = np.asarray(to_plot.get("k_lam", []), dtype=np.float64).ravel()

            if lam_u.size and n_u.size == lam_u.size and k_u.size == lam_u.size:
                self._update_persistent_nk_monitor(lam_u, n_u, k_u, float(to_plot.get("d_nm", float("nan"))))

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("nk monitor update in _on_live_update failed", exc_info=True)

    def _start_auto_best_second_stage(self) -> None:

        pend = self._auto_best_second_stage_pending

        self._auto_best_second_stage_pending = None

        if not isinstance(pend, dict):
            return

        seed = pend.get("seed")

        cfg2 = pend.get("cfg")

        if not isinstance(seed, dict) or cfg2 is None:
            return

        if self.logger:
            self.logger.info(
                "AUTO_BEST stage2 start | seed_rmse=%.6f seed_d=%.4f",
                float(np.sqrt(max(float(seed.get("mse", 0.0)), 0.0))),
                float(seed.get("d_nm", float("nan"))),
            )

        self.__class__._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._log_prog_last = -1

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        self._worker = GenericWorker(
            worker_auto_best_split_knot_refinement,
            seed,
            cfg2,
            self._stop_event,
        )

        _wsig_ab = self._worker.signals

        def _ab_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            _wsig_ab.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _ab_progress

        self._worker_role = "auto_best"

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self._worker.signals.live.connect(self._on_live_update)

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self._worker.start()

    def _plot_result(self, r: dict, *, plot_source: str = "maj") -> None:

        lam0_src = r.get("lam_nm")
        if lam0_src is None and self.df is not None and "lambda" in self.df.columns:
            lam0_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("_plot_result: missing lam_nm in result; fallback to experimental lambda grid.")
        lam0 = np.asarray(lam0_src if lam0_src is not None else [], dtype=np.float64).ravel()
        if lam0.size == 0:
            self.lbl_status.setText("Aucun lambda disponible pour tracer le resultat.")
            if self.logger:
                self.logger.error("_plot_result aborted: lam_nm unavailable after fallback.")
            self._spectrum_clear_theory_probe()
            return

        tt0 = np.asarray(r["t_theo"], dtype=np.float64).ravel()

        n0 = np.asarray(r["n_lam"], dtype=np.float64).ravel()

        k0 = np.asarray(r["k_lam"], dtype=np.float64).ravel()

        lam_exp: np.ndarray | None = None

        if self.df is not None and "lambda" in self.df.columns:
            lam_exp = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        plot_r_model = (
            r.get("r_theo") is not None
            and self.df is not None
            and "R" in self.df.columns
            and lam_exp is not None
            and lam_exp.size > 0
        )

        if plot_r_model:
            rt0 = np.asarray(r["r_theo"], dtype=np.float64).ravel()

            lam_s, pack, order = _spectral_display_align(lam0, tt0, n0, k0, rt0)

            tt_s, n_s, k_s, rt_s = pack[0], pack[1], pack[2], pack[3]

        else:
            lam_s, pack, order = _spectral_display_align(lam0, tt0, n0, k0)

            tt_s, n_s, k_s = pack[0], pack[1], pack[2]

            rt_s = None

        x_mod, x_lbl = self._transform_spectrum_x(lam_s)

        self._spectrum_theory_probe_lam_nm = np.asarray(lam_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_n = np.asarray(n_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_k = np.asarray(k_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_tt = np.asarray(tt_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_rt = np.asarray(rt_s, dtype=np.float64).ravel().copy() if rt_s is not None else None
        self._spectrum_theory_probe_d_nm = float(r.get("d_nm", float("nan")))

        self.plot_T.clear()

        self.plot_n.clear()

        self.plot_k.clear()

        x_exp: np.ndarray | None = None

        if lam_exp is not None and lam_exp.size:
            x_exp, _ = self._transform_spectrum_x(lam_exp)

        if self.df is not None and "T" in self.df.columns and lam_exp is not None and lam_exp.size:
            ye_raw = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

            ye = ye_raw

            ne = "T/Tsub exp" if bool(r.get("t_is_ratio", False)) else "T exp"

            self._add_curve(self.plot_T, x_exp, ye, CertusTheme.TEXT_SUB, ne, True)

        nm = "T/Tsub model" if bool(r.get("t_is_ratio", False)) else "T model"

        self._add_curve(self.plot_T, x_mod, tt_s, CertusTheme.PRIMARY, nm)

        sigma_knots = np.asarray(r.get("sigma_knots", []), dtype=np.float64).ravel()
        if sigma_knots.size:
            lam_k_t, tt_k = _interp_series_at_sigma_knots(lam_s, tt_s, sigma_knots)
            if lam_k_t.size:
                x_k_t, _ = self._transform_spectrum_x(lam_k_t)
                _plot_spectrum_raw_scatter(
                    self.plot_T,
                    x_k_t,
                    tt_k,
                    color=CertusTheme.PRIMARY,
                    name="T model knots",
                    symbol_size=11,
                )

        if plot_r_model and rt_s is not None:
            ye_raw = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

            ye = ye_raw

            r_ne = "R/Tsub exp" if bool(r.get("t_is_ratio", False)) else "R exp"

            self._add_curve(self.plot_T, x_exp, ye, "#888888", r_ne, True)

            r_nm = "R/Tsub model" if bool(r.get("t_is_ratio", False)) else "R model"

            self._add_curve(self.plot_T, x_mod, rt_s, CertusTheme.SECONDARY, r_nm)

            if sigma_knots.size:
                lam_k_r, rt_k = _interp_series_at_sigma_knots(lam_s, rt_s, sigma_knots)
                if lam_k_r.size:
                    x_k_r, _ = self._transform_spectrum_x(lam_k_r)
                    _plot_spectrum_raw_scatter(
                        self.plot_T,
                        x_k_r,
                        rt_k,
                        color=CertusTheme.SECONDARY,
                        name="R model knots",
                        symbol_size=11,
                    )

        lk = np.full(k_s.shape, np.nan, dtype=np.float64)

        mk = np.isfinite(k_s) & (k_s >= 0.0)

        lk[mk] = np.log10(np.maximum(k_s[mk], 1e-30))

        self._add_curve(self.plot_n, lam_s, n_s, "#0057ff", "n", crosshair_primary=True)

        self._add_curve(self.plot_k, lam_s, lk, "#ff5a00", "k", crosshair_primary=True)

        self._plot_corridor_tab(r, lam_s, n_s, k_s, spectral_sort_order=order)

        self._plot_corridor_rmse_tab(r)

        d_nm = float(r.get("d_nm", float("nan")))

        d_txt = f"d = {d_nm:.1f} nm" if np.isfinite(d_nm) else "d = "

        try:
            self.plot_n.plotItem.setTitle(f"n(lambda)  {d_txt}", color=CertusTheme.PRIMARY, size="10pt")

            self.plot_k.plotItem.setTitle(f"k(lambda)  {d_txt}", color=CertusTheme.PRIMARY, size="10pt")

        except (AttributeError, RuntimeError):
            logger.debug("Index plot title set failed", exc_info=True)

        self.plot_T.autoRange()

        self._apply_spectrum_x_axis_label(x_lbl)

        y_spec = tt_s if rt_s is None else np.concatenate([tt_s, rt_s])
        _add_spectrum_thickness_badge(self.plot_T, x_mod, y_spec, d_nm)

        self.plot_n.autoRange()

        _apply_fixed_log_k_axis(self.plot_k)

        if lam0.size > 0:
            span_lo = float(np.nanmin(lam0))

            span_hi = float(np.nanmax(lam0))

            if np.isfinite(span_lo) and np.isfinite(span_hi) and span_hi > span_lo:
                pad = 0.02 * (span_hi - span_lo)

                self.plot_n.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

                self.plot_k.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

        self._apply_spectrum_plot_title(r)

        self._update_rmse_fit_region_overlay()

        _log_tgt = self.logger if self.logger is not None else logger
        try:
            _rm_log = float(r.get("rmse", float("nan")))
            if not np.isfinite(_rm_log):
                _rm_log = float(np.sqrt(max(float(r.get("mse", 0.0)), 0.0)))
        except (TypeError, ValueError):
            _rm_log = float("nan")
        _rm_s = f"{_rm_log:.8f}" if np.isfinite(_rm_log) else "n/a"
        _d_log = float(d_nm)
        _d_s = f"{_d_log:.4f}" if np.isfinite(_d_log) else "n/a"
        _corridor_pts = int(np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64).size)
        _msg = (
            f"[INDEX_SPLINE.GRAPHS] {plot_source} | spectral T/R+n,k (+ corridor/NL tabs when available) "
            f"| lam_pts={int(lam_s.size)} exp_pts={str(int(lam_exp.size)) if lam_exp is not None and lam_exp.size else '0'} abs={x_lbl} | d_nm={_d_s} rmse={_rm_s} | R_couche={bool(plot_r_model)} K_sigma={int(sigma_knots.size)} | profil_corridoir_d={_corridor_pts}pts"
        )
        if plot_source == "live":
            _log_tgt.debug("%s", _msg)
        else:
            _log_tgt.info("%s", _msg)

        # Auto-refresh corridor RMSE profile window if open
        win = getattr(self, "_corridor_rmse_profile_win", None)
        if win is not None and win.isVisible():
            d_prof = np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64)
            r_prof = np.asarray(r.get("profile_d_rmse_values", []), dtype=np.float64)
            if d_prof.size > 0 and r_prof.size == d_prof.size:
                rmse_thresh = r.get("profile_d_rmse_thresh")
                win.update_profile(d_prof, r_prof, rmse_thresh)

    def _log_optimization_header(self, cfg: SplineOptConfig) -> None:
        """Startup INFO block (CERTUS_INDEX+ detail: context + displayed RMSE reminder)."""

        if not self.logger:
            return

        lam = np.asarray(cfg.lam_nm, dtype=np.float64)

        npt = int(lam.size)

        if npt:
            l0, l1 = float(np.nanmin(lam)), float(np.nanmax(lam))

        else:
            l0 = l1 = float("nan")

        path_hint = getattr(self, "_last_spectrum_path", "").strip() or (
            str(self.lbl_file.text()).strip() if hasattr(self, "lbl_file") else ""
        )

        dt_name = cfg.data_type.name if hasattr(cfg.data_type, "name") else str(cfg.data_type)

        self.logger.info("[INDEX_SPLINE.STATE] optimization started")

        self.logger.info("[INDEX_SPLINE.LOAD] spectrum path=%s", path_hint or "(unknown path)")

        self.logger.info(
            "[INDEX_SPLINE.LOAD] substrate=%s | lambda=[%g, %g] nm | points=%d | substrate_normalized_t=%s",
            cfg.substrate_name,
            l0,
            l1,
            npt,
            cfg.t_is_ratio,
        )

        self.logger.info(
            "[INDEX_SPLINE.CONFIG] target=%s | weight_t=%.4g | weight_r=%.4g | spectral_quadrature=ln_lambda_trapezoids",
            dt_name,
            cfg.weight_t,
            cfg.weight_r,
        )

        self.logger.info(
            "[INDEX_SPLINE.CONFIG] thickness_range=[%.2f, %.2f] nm | sigma_segments=%d",
            cfg.d_lo,
            cfg.d_hi,
            cfg.n_seg,
        )

        if cfg.n_mono_band_nm is not None:
            a, b = float(cfg.n_mono_band_nm[0]), float(cfg.n_mono_band_nm[1])

            self.logger.info(
                "[INDEX_SPLINE.CONFIG] monotonic_n_band=[%.0f, %.0f] nm | continuous_penalty_weight=%.4g",
                min(a, b),
                max(a, b),
                float(cfg.n_mono_continuous_penalty),
            )

        else:
            self.logger.info("[INDEX_SPLINE.CONFIG] monotonic_n_constraint=disabled")

        w_nlam = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)

        band_nlam = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)

        if w_nlam > 0.0 and band_nlam is not None:
            b0, b1 = float(band_nlam[0]), float(band_nlam[1])

            self.logger.info(
                "[INDEX_SPLINE.CONFIG] rising_n_constraint_band=[%.0f, %.0f] nm | penalty_weight=%.4g",
                min(b0, b1),
                max(b0, b1),
                w_nlam,
            )

        else:
            self.logger.info("[INDEX_SPLINE.CONFIG] rising_n_penalty=disabled")

        n_fit = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

        if cfg.rmse_fit_lambda_nm is not None:
            rl0, rl1 = float(cfg.rmse_fit_lambda_nm[0]), float(cfg.rmse_fit_lambda_nm[1])

            self.logger.info(
                "[INDEX_SPLINE.CONFIG] rmse_fit_band=[%.4g, %.4g] nm | objective_points=%d",
                min(rl0, rl1),
                max(rl0, rl1),
                n_fit,
            )

        else:
            self.logger.info("[INDEX_SPLINE.CONFIG] rmse_fit_band=full_spectrum | objective_points=%d", n_fit)

        self.logger.info("[INDEX_SPLINE.CONFIG] local_optimizer=lbfgsb | polish_maxfun=%d", cfg.polish_maxfun)

        self.logger.info("[INDEX_SPLINE.CONFIG] substrate_delta_n_refinement=disabled (nominal_substrate)")

        prof = str(self.cb_profilee.currentData() or "fast") if hasattr(self, "cb_profilee") else "fast"

        self.logger.info("GUI performance profile: %s", prof)

        self.logger.info("Auto-Ksigma: disabled (K fixed to n_seg+1 initial knots)")

        self.logger.info(
            "[Reminder] During optimization, live snapshots follow the best RMSE seen at that moment. "
            "At the end, rmse/mse in the dict may reflect final indices (cubic spline polish in sigma) "
            "- compare to pipeline_best_rmse_watermark if needed. Curves on screen = n_lam/k_lam from final dict."
        )

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

        n_nl_g = np.full_like(lam_g, np.nan)

        k_nl_g = np.full_like(lam_g, np.nan)

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

        return (lam_g, n_g, k_g, n_nl_g, k_nl_g, n_lo_g, n_hi_g, k_lo_g, k_hi_g)

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
                    self.logger.debug("Data TH substrate ns build failed", exc_info=True)
            except (TypeError, ValueError):
                if self.logger:
                    self.logger.debug("Data TH substrate lookup failed", exc_info=True)

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
                self.logger.debug("Manual delta-ns preview RMSE recompute failed", exc_info=True)

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
        y_preview = np.asarray(preview_result.get("t_theo", []), dtype=np.float64).ravel()
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
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        hdr = "lambda_nm\tn\tn_alpha\tn_envelope_min\tn_envelope_max\tk\tk_alpha\tk_envelope_min\tk_envelope_max"

        lines = [hdr]

        m = int(lam_g.size)

        for i in range(m):
            row = f"{float(lam_g[i]):.4f}\t"

            row += self._fmt_n_data_tab(float(n_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_nl_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_lo_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_hi_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_nl_g[i])) + "\t"

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

        nnl_at = self._interp_preview_axis(lam_a, s["n_nl"], x)

        nlo_at = self._interp_preview_axis(lam_a, s["n_lo"], x)

        nhi_at = self._interp_preview_axis(lam_a, s["n_hi"], x)

        k_at = self._interp_preview_axis(lam_a, s["k"], x)

        knl_at = self._interp_preview_axis(lam_a, s["k_nl"], x)

        klo_at = self._interp_preview_axis(lam_a, s["k_lo"], x)

        khi_at = self._interp_preview_axis(lam_a, s["k_hi"], x)

        lam_txt = float(x)

        txt = (
            f"lambda = {lam_txt:.2f} nm\n"
            f"n={_fmt_nq(n_at)}  n_alpha={_fmt_nq(nnl_at)}  n_min={_fmt_nq(nlo_at)}  n_max={_fmt_nq(nhi_at)}\n"
            f"k={_fmt_kq(k_at)}  k_alpha={_fmt_kq(knl_at)}  k_min={_fmt_kq(klo_at)}  k_max={_fmt_kq(khi_at)}"
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
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        t.setColumnCount(9)

        t.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n_alpha",
                "n env min",
                "n env max",
                "k",
                "k_alpha",
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

            t.setItem(i, 2, _cell_n(float(n_nl_g[i])))

            t.setItem(i, 3, _cell_n(float(n_lo_g[i])))

            t.setItem(i, 4, _cell_n(float(n_hi_g[i])))

            t.setItem(i, 5, _cell_k(float(k_g[i])))

            t.setItem(i, 6, _cell_k(float(k_nl_g[i])))

            t.setItem(i, 7, _cell_k(float(k_lo_g[i])))

            t.setItem(i, 8, _cell_k(float(k_hi_g[i])))

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
                logger.debug("RMSE(d) live plot update failed", exc_info=True)

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
            logger.debug("Auto-smart corridor: robust refresh failed", exc_info=True)

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
            logger.debug("Auto-smart corridor: post-apply robust refresh failed", exc_info=True)

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

class _SettingsMixin:
    """Mixin containing defaults reset, loading and uncertainty settings methods."""

    def _apply_default_square_plot_split(self) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            return

        total = int(max(0, sizes[0]) + max(0, sizes[1]))
        if total <= 0:
            total = int(max(0, spl.width()))
        if total <= 0:
            return

        panel_h = int(max(0, spl.height()))
        if panel_h <= 0:
            panel_h = int(round(0.58 * float(total)))

        # Keep the right panel width near the visible height so the active plot
        # starts close to a square aspect by default.
        target_right = int(round(0.88 * float(panel_h)))
        target_right = int(
            min(
                max(target_right, int(round(0.20 * float(total)))),
                int(round(0.95 * float(total))),
            )
        )
        target_left = int(max(1, total - target_right))

        self._main_splitter_clamp_guard = True
        try:
            spl.setSizes([target_left, target_right])
        finally:
            self._main_splitter_clamp_guard = False

        self._enforce_main_splitter_ratio_bounds(persist=False)

    def _on_main_splitter_moved(self, *_args) -> None:

        self._enforce_main_splitter_ratio_bounds(persist=True)

    def _enforce_main_splitter_ratio_bounds(self, *, persist: bool = True) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            if persist:
                self._persist_splitter_states()
            return

        if bool(getattr(self, "_main_splitter_clamp_guard", False)):
            if persist:
                self._persist_splitter_states()
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            if persist:
                self._persist_splitter_states()
            return

        left = int(max(0, sizes[0]))
        right = int(max(0, sizes[1]))
        total = int(left + right)
        if total <= 0:
            if persist:
                self._persist_splitter_states()
            return

        min_left = max(1, int(round(0.05 * total)))
        max_left = max(min_left, int(round(0.95 * total)))
        clamped_left = int(min(max(left, min_left), max_left))

        if clamped_left != left:
            self._main_splitter_clamp_guard = True
            try:
                spl.moveSplitter(int(clamped_left), 0)
            finally:
                self._main_splitter_clamp_guard = False

        if persist:
            self._persist_splitter_states()

    def _restore_splitter_states(self) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            v_rev_raw = s.value(_QS_MAIN_SPLITTER_LAYOUT_REV, 0)
            v_rev = int(v_rev_raw or 0)
        except (TypeError, ValueError):
            v_rev = 0

        try:
            if hasattr(self, "main_split") and v_rev == int(_MAIN_SPLITTER_LAYOUT_REV):
                v_main = s.value(_QS_MAIN_SPLITTER_STATE)
                if v_main is not None:
                    self.main_split.restoreState(v_main)
                else:
                    QTimer.singleShot(0, self._apply_default_square_plot_split)
                self._enforce_main_splitter_ratio_bounds(persist=False)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            v_right = s.value(_QS_RIGHT_SPLITTER_STATE)
            if v_right is not None and hasattr(self, "info_split"):
                self.info_split.restoreState(v_right)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _persist_splitter_states(self, *_args) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        if hasattr(self, "main_split"):
            s.setValue(_QS_MAIN_SPLITTER_STATE, self.main_split.saveState())
            s.setValue(_QS_MAIN_SPLITTER_LAYOUT_REV, int(_MAIN_SPLITTER_LAYOUT_REV))

        if hasattr(self, "info_split"):
            s.setValue(_QS_RIGHT_SPLITTER_STATE, self.info_split.saveState())

    def _maybe_apply_uncertainty_defaults_migrated(self) -> None:
        """Applies automatic uncertainty defaults once (migration / new install)."""

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            rev = int(s.value(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, 0) or 0)

        except (TypeError, ValueError):
            rev = 0

        if rev < _UNCERTAINTY_DEFAULTS_REV:
            if rev < 5:
                self._apply_recommended_uncertainty_and_perf_defaults()

                self._apply_sio2_default_fit_parameters()

                if hasattr(self, "chk_trel"):
                    self.chk_trel.setChecked(True)

            if rev < 9 and hasattr(self, "cb_corr_mode"):
                self.cb_corr_mode.blockSignals(True)

                try:
                    iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                    if iq >= 0:
                        self.cb_corr_mode.setCurrentIndex(int(iq))

                finally:
                    self.cb_corr_mode.blockSignals(False)

                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._on_corr_mode_changed()

            if rev < 11 and hasattr(self, "cb_corr_mode"):
                self._apply_corridor_preset_auto_robust()

            if rev < 12:
                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

                if hasattr(self, "_on_corr_mode_changed"):
                    self._on_corr_mode_changed()

                if hasattr(self, "_refresh_corridors_gui_state_labels"):
                    self._refresh_corridors_gui_state_labels()

            s.setValue(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, int(_UNCERTAINTY_DEFAULTS_REV))

    def _apply_recommended_uncertainty_and_perf_defaults(self) -> None:
        """Speed-oriented defaults: Fast profile, n/k corridors enabled (accelerated refits); optional bootstrap / reg. scan."""

        if not hasattr(self, "cb_profilee"):
            return

        self.cb_profilee.blockSignals(True)

        try:
            iq = self.cb_profilee.findData("fast")

            if iq >= 0:
                self.cb_profilee.setCurrentIndex(int(iq))

        finally:
            self.cb_profilee.blockSignals(False)

        self._on_profilee_changed()

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.setChecked(True)

        if hasattr(self, "cb_corr_mode"):
            ia = self.cb_corr_mode.findData("abs_delta_adaptive")

            if ia >= 0:
                self.cb_corr_mode.setCurrentIndex(int(ia))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "chk_corr_sigma_hetero"):
            self.chk_corr_sigma_hetero.setChecked(False)

        if hasattr(self, "sp_corr_hetero_scale"):
            self.sp_corr_hetero_scale.setValue(1.0)

        if hasattr(self, "sp_corr_sigma"):
            self.sp_corr_sigma.setValue(0.0)

        if hasattr(self, "sp_corr_starts"):
            self.sp_corr_starts.setValue(1)

        if hasattr(self, "chk_corr_reg_sens"):
            self.chk_corr_reg_sens.setChecked(False)

        if hasattr(self, "chk_corr_boot"):
            self.chk_corr_boot.setChecked(False)

        if hasattr(self, "sp_corr_boot_n"):
            self.sp_corr_boot_n.setValue(40)

        self._refresh_corridors_gui_state_labels()

        if hasattr(self, "sp_corr_boot_p"):
            self.sp_corr_boot_p.setValue(0.95)

        if hasattr(self, "chk_corr_boot_refit"):
            self.chk_corr_boot_refit.setChecked(False)

        if hasattr(self, "sp_corr_boot_maxfun"):
            self.sp_corr_boot_maxfun.setValue(4000)

        if hasattr(self, "sp_corr_boot_workers"):
            self.sp_corr_boot_workers.setValue(1)

        if hasattr(self, "sp_corr_span"):
            self.sp_corr_span.setValue(15.0)

        if hasattr(self, "sp_corr_prof_maxfun"):
            self.sp_corr_prof_maxfun.setValue(2500)

        if hasattr(self, "cb_corr_boot_mode"):
            ip = self.cb_corr_boot_mode.findData("parametric")

            if ip >= 0:
                self.cb_corr_boot_mode.setCurrentIndex(int(ip))

        if hasattr(self, "cb_corr_mode"):
            self._apply_corridor_preset_auto_robust()

    def reset_to_defaults(self) -> None:
        """Reinitialisation complete (bouton Clear / Reset CERTUS)."""

        from certus.utils.certus_reset_framework import reset_app_to_defaults

        reset_app_to_defaults(self)

    @safe_ui_action
    def _on_load(self, path: str | None = None) -> None:

        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Spectrum",
                self._spectrum_open_dialog_start_path(),
                "Data (*.csv *.xlsx *.xls);;All (*.*)",
            )

        if not path:
            return

        try:
            raw = read_data_file_robust(path)

            self.df = normalize_spectrum_dataframe(raw)

            if self.df is None or "lambda" not in self.df.columns:
                raise ValueError("Invalid wavelength or spectrum column after normalization.")

            self._persist_last_spectrum_path(path)

            self.lbl_file.setText(path)

            if hasattr(self, "tabs_main"):
                self.tabs_main.setCurrentIndex(0)

            self._sync_rmse_lambda_bounds_from_file()

            self._plot_data_raw()

            self.lbl_status.setText(f"Loaded: {len(self.df)} points")

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                lam = np.asarray(self.df.get("lambda", []), dtype=np.float64).ravel()

                lam_f = lam[np.isfinite(lam)]

                lmin = float(np.min(lam_f)) if lam_f.size else float("nan")

                lmax = float(np.max(lam_f)) if lam_f.size else float("nan")

                cols = [str(c) for c in self.df.columns]

                summary = build_summary_plain_text(
                    "CERTUS INDEX SPLINE - Load Summary",
                    [
                        f"File: {Path(path).resolve(strict=False)}",
                        "",
                        "General",
                        (f"Rows: {int(len(self.df))}", int(len(self.df)) <= 0),
                        "",
                        "Data",
                        f"Columns: {', '.join(cols)}",
                        (
                            f"Wavelength range: [{lmin:.1f}, {lmax:.1f}] nm",
                            not (np.isfinite(lmin) and np.isfinite(lmax) and lmax > lmin),
                        ),
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if any(c.lower().startswith('t') for c in cols) else 'no'}",
                            not any(c.lower().startswith("t") for c in cols),
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX SPLINE Load Summary", summary)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            QMessageBox.critical(self, "Loading", str(e))

            logger.exception("load")

    def _update_rmse_fit_region_overlay(self) -> None:

        self._remove_rmse_fit_region_overlay()

        if not getattr(self, "_rmse_fit_lambda_enabled", False):
            return

        span = self._spectrum_plot_lambda_span_nm()

        if span is None:
            return

        lam_file_lo, lam_file_hi = span

        if not (np.isfinite(lam_file_lo) and np.isfinite(lam_file_hi)):
            return

        if lam_file_lo > lam_file_hi:
            lam_file_lo, lam_file_hi = lam_file_hi, lam_file_lo

        wlo = float(self._rmse_fit_lambda_lo)

        whi = float(self._rmse_fit_lambda_hi)

        if not (np.isfinite(wlo) and np.isfinite(whi)):
            return

        lam_win_lo, lam_win_hi = min(wlo, whi), max(wlo, whi)

        def _x_span_lam(la: float, lb: float) -> tuple[float, float] | None:

            if not (np.isfinite(la) and np.isfinite(lb)):
                return None

            if la > lb:
                la, lb = lb, la

            if lb - la <= 0.0:
                return None

            try:
                xv, _ = self._transform_spectrum_x(np.array([la, lb], dtype=np.float64))

            except (TypeError, ValueError, RuntimeError):
                return None

            return float(np.min(xv)), float(np.max(xv))

        eps_lam = max(1e-6, 1e-9 * max(abs(lam_file_hi), 1.0))

        eps_x = max(1e-12, 1e-15 * max(abs(lam_file_lo), abs(lam_file_hi), 1.0))

        def _add_region(xa: float, xb: float, *, brush, z: float) -> None:

            lo_x, hi_x = (xa, xb) if xa <= xb else (xb, xa)

            if hi_x - lo_x <= eps_x:
                return

            reg = pg.LinearRegionItem(values=(lo_x, hi_x), movable=False, brush=brush)

            reg.setZValue(z)

            self.plot_T.addItem(reg)

            self._rmse_fit_overlay_items.append(reg)

        gray_brush = pg.mkBrush(120, 120, 120, 85)

        # Excludes lambda < window (within file envelope) - correct if sigma/sigma^2 (nonlinear in lambda on axis)

        if lam_win_lo > lam_file_lo + eps_lam:
            la, lb = lam_file_lo, min(lam_file_hi, lam_win_lo)

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        # Exclude lambda > window

        if lam_win_hi < lam_file_hi - eps_lam:
            la, lb = max(lam_file_lo, lam_win_hi), lam_file_hi

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        x_active = _x_span_lam(lam_win_lo, lam_win_hi)

        if x_active is not None:
            xa, xb = x_active

            if xb - xa > eps_x:
                reg_active = pg.LinearRegionItem(
                    values=(xa, xb),
                    movable=False,
                    brush=pg.mkBrush(0, 120, 215, 40),
                )

                reg_active.setZValue(-5.0)

                self.plot_T.addItem(reg_active)

                self._rmse_fit_overlay_items.append(reg_active)

    def _on_rmse_fit_window_dialog(self) -> None:

        dlg = QDialog(self)

        dlg.setWindowTitle("Spectral RMSE Window")

        lay = QVBoxLayout(dlg)

        chk = QCheckBox("Limit optimization MSE/RMSE to a lambda band (nm)")

        chk.setChecked(self._rmse_fit_lambda_enabled)

        chk.setToolTip(
            "If checked: only experimental points in [lambda_min, lambda_max] enter the spectral loss. "
            "Plots always use the full loaded file."
        )

        lay.addWidget(chk)

        g = QGridLayout()

        lb_lo = QLabel("lambda_min (nm)")

        lb_hi = QLabel("lambda_max (nm)")

        sp_lo = QDoubleSpinBox()

        sp_hi = QDoubleSpinBox()

        for sp in (sp_lo, sp_hi):
            sp.setRange(200.0, 20000.0)

            sp.setDecimals(4)

            sp.setSingleStep(1.0)

        sp_lo.setValue(float(self._rmse_fit_lambda_lo))

        sp_hi.setValue(float(self._rmse_fit_lambda_hi))

        sp_lo.setToolTip("Lower bound (nm) of the RMSE band.")

        sp_hi.setToolTip("Upper bound (nm) of the RMSE band.")

        g.addWidget(lb_lo, 0, 0)

        g.addWidget(sp_lo, 0, 1)

        g.addWidget(lb_hi, 1, 0)

        g.addWidget(sp_hi, 1, 1)

        lay.addLayout(g)

        btn_reset = QPushButton("Reset")

        btn_reset.setToolTip("Reset lambda_min / lambda_max to [min file, max file] of the loaded spectrum.")

        lay.addWidget(btn_reset)

        def _apply_enable(en: bool) -> None:

            sp_lo.setEnabled(en)

            sp_hi.setEnabled(en)

            btn_reset.setEnabled(en)

        def _do_reset() -> None:

            sp_lo.setValue(float(self._rmse_fit_lambda_lo_default))

            sp_hi.setValue(float(self._rmse_fit_lambda_hi_default))

        chk.toggled.connect(_apply_enable)

        _apply_enable(chk.isChecked())

        btn_reset.clicked.connect(_do_reset)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._rmse_fit_lambda_enabled = chk.isChecked()

        self._rmse_fit_lambda_lo = float(sp_lo.value())

        self._rmse_fit_lambda_hi = float(sp_hi.value())

        if self._last_result is not None:
            self._plot_result(self._last_result, plot_source="fenetre_rmse_fit_lambda")

        elif self.df is not None:
            self._plot_data_raw()

        else:
            self._update_rmse_fit_region_overlay()

    def _restore_spectrum_fit_settings(self) -> None:
        """Reads step 3 from QSettings (T, T/Tsub ratio, R, wT, wR)."""

        if not hasattr(self, "chk_t"):
            return

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        widgets = (
            self.chk_t,
            self.chk_trel,
            self.chk_r,
            self.w_t,
            self.w_r,
        )

        for w in widgets:
            w.blockSignals(True)

        try:
            vt = s.value(_QS_SPECTRUM_FIT_T)

            if vt is not None:
                self.chk_t.setChecked(bool(vt))

            vrel = s.value(_QS_SPECTRUM_FIT_TREL)

            if vrel is not None:
                self.chk_trel.setChecked(bool(vrel))

            vr = s.value(_QS_SPECTRUM_FIT_R)

            if vr is not None:
                self.chk_r.setChecked(bool(vr))

            wtv = s.value(_QS_SPECTRUM_WT)

            if wtv is not None:
                self.w_t.setValue(float(wtv))

            wrv = s.value(_QS_SPECTRUM_WR)

            if wrv is not None:
                self.w_r.setValue(float(wrv))

        finally:
            for w in widgets:
                w.blockSignals(False)

    def _open_advanced_settings_dialog(self) -> None:

        lay_page = getattr(self, "_box4_full_adv_layout", None)

        if not hasattr(self, "_w_full_adv") or lay_page is None:
            return

        dlg = QDialog(self)

        dlg.setWindowTitle("Advanced settings - INDEX-SPLINE")

        dlg.resize(560, 620)

        outer = QVBoxLayout(dlg)

        chk = QCheckBox("Simplified Basic panel (recommended): hide advanced budgets and uncertainty details")

        chk.setChecked(bool(getattr(self, "_simple_auto_uncertainty", True)))

        chk.setToolTip(
            "Unchecked: after OK, controls stay visible in step 4. "
            "Checked: summary only in the panel; settings remain available here."
        )

        outer.addWidget(chk)

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        host = QWidget()

        host_lay = QVBoxLayout(host)

        host_lay.setContentsMargins(0, 0, 0, 0)

        lay_page.removeWidget(self._w_full_adv)

        host_lay.addWidget(self._w_full_adv)

        scroll.setWidget(host)

        outer.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        outer.addWidget(bb)

        code = dlg.exec()

        host_lay.removeWidget(self._w_full_adv)

        lay_page.addWidget(self._w_full_adv)

        self._w_full_adv.show()

        if code == QDialog.DialogCode.Accepted:
            self._simple_auto_uncertainty = chk.isChecked()

            self._persist_simple_auto_uncertainty_pref()

        self._update_epured_visibility()

class _CorridorControlMixin:
    """Mixin containing corridor RMSE grid control, display and worker management."""

    def _start_deferred_corridor_worker(self, result: dict) -> bool:

        cfg_base = self._last_run_cfg

        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)

        if cfg_base is None:
            return False

        self.__class__._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        cfg_corr = self._cfg_with_result_substrate(cfg_base, result).replace()

        setattr(cfg_corr, "gui_defer_corridor_profile_after_nl", False)
        # Manual "Corridors" action must execute profiling now, regardless of the main run checkbox state.
        setattr(cfg_corr, "corridor_profile_d_enabled", True)

        # --- Resync solver snapshot if manual dialog changed the mesh (K) ---
        _snap = result.get("gui_solver_snapshot_for_corridors")
        _snap_k = 0
        if isinstance(_snap, dict):
            _snap_sk = np.asarray(_snap.get("sigma_knots", []), dtype=np.float64).ravel()
            _snap_k = int(_snap_sk.size)
        _cur_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        _cur_k = int(_cur_sk.size)
        if _cur_k >= 2 and _cur_k != _snap_k:
            fresh_snap = dict(result)
            for _key in ("x", "x_seg_spline_sigma", "n_nodes_physical", "L_nodes",
                         "sigma_knots", "d_nm", "n_lam", "k_lam", "rmse", "mse"):
                if _key in result:
                    val = result[_key]
                    if isinstance(val, np.ndarray):
                        fresh_snap[_key] = val.copy()
                    else:
                        fresh_snap[_key] = val
            result["gui_solver_snapshot_for_corridors"] = fresh_snap
            if self.logger:
                self.logger.info(
                    "[INDEX_SPLINE.CORRIDORS] solver snapshot resynced to current mesh | k_snap=%d -> k_current=%d",
                    _snap_k, _cur_k,
                )


        self._worker = GenericWorker(
            worker_run_corridor_profile_after_nl_choice, cfg_corr, dict(result), self._stop_event
        )

        def _corr_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _corr_progress
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        source_stage = str(getattr(self, "_worker_role", "main") or "main")

        self._worker_role = "corridors"

        if hasattr(self, "_stepper"):
            self._stepper.set_step(6)

        if self.logger:
            rd = result.get("d_nm")
            rd_txt = f"{float(rd):.6f}" if isinstance(rd, (int, float)) and np.isfinite(float(rd)) else "n/a"
            rr = self._rmse_from_result_dict(result)
            rr_txt = f"{rr:.8f}" if np.isfinite(rr) else "n/a"
            self.logger.info(
                "[INDEX_SPLINE.CORRIDORS] launching deferred corridor worker | after_stage=%s | seed_d_nm=%s | seed_rmse_dict=%s",
                source_stage,
                rd_txt,
                rr_txt,
            )
            log_index_spline_d_trace(
                self.logger,
                "[INDEX_SPLINE.CORRIDORS] deferred corridor launch trace | seed=last_result",
                result.get("d_nm"),
                detail=f"after_stage={source_stage} rmse_dict={rr_txt}",
            )

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText("Corridors: calculation in progress...")

        self._worker.start()

        return True

    def _finish_curve_minimum_deep_worker_done(self, result: object) -> None:
        """Fin du polish profond depuis le minimum RMSE(d) : retour a l'etat post-optimisation sans lancement automatique."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not isinstance(result, dict):
            self.lbl_status.setText("Polish profond (minimum grille) : annule ou echec.")
            if self.logger:
                self.logger.warning(
                    "GUI curve-min deep refit | finished without dict (type=%s)",
                    type(result).__name__,
                )
            QMessageBox.warning(
                self,
                "Polish profond",
                "Le polish L-BFGS-B depuis le minimum de grille n'a pas renvoye de resultat valide "
                "(interruption ou echec numerique). Le nominal n'a pas ete modifie.",
            )
            self._refresh_post_optimization_option_controls()
            return
        for _rk in list(result.keys()):
            if str(_rk).startswith("profile_d"):
                del result[_rk]

        # Restore corridor and profile_d keys from the preceding corridor worker output.
        # The deep polish (L-BFGS-B on d+nodes) does not recompute corridor envelopes;
        # they were computed by the corridor worker and are stored in _last_result.
        # Safety: _display_result_prefer_best_live (called below) will NOT strip them
        # because _best_live_result is None during deep polish (no live callbacks).
        prev = self._last_result if isinstance(self._last_result, dict) else {}
        _lam_result = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_prev = np.asarray(prev.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_ok = _lam_result.size > 0 and _lam_result.size == _lam_prev.size
        _n_restored = 0
        if _lam_ok:
            for _pk in list(prev.keys()):
                if (
                    str(_pk).startswith("corridor_")
                    or str(_pk).startswith("profile_d_")
                    or _pk == "profile_d_enabled"
                ) and _pk not in result:
                    val = prev[_pk]
                    result[_pk] = val.copy() if isinstance(val, np.ndarray) else val
                    _n_restored += 1
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | corridor data restoration from _last_result | "
                "lam_ok=%s (result=%d, prev=%d) | keys_restored=%d",
                "yes" if _lam_ok else "NO",
                int(_lam_result.size),
                int(_lam_prev.size),
                int(_n_restored),
            )

        self._last_worker_result = dict(result)
        self._corridor_rmse_manual_active = False
        self._corridor_rmse_manual_lo = float("nan")
        self._corridor_rmse_manual_hi = float("nan")

        display = self._display_result_prefer_best_live(result)
        self._last_result = display

        st = self._format_post_optimization_status(display, result)
        status_text = "Apres minimum grille (polish profond) | " + st
        self.lbl_status.setText(status_text)

        if self.logger:
            rm_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )
            self.logger.info(
                "GUI curve-min deep refit | done | rmse=%.8f | d_nm=%.6f",
                rm_fin,
                float(display.get("d_nm", float("nan"))),
            )
            if np.isfinite(rm_fin):
                _log_index_spline_best_config(self.logger, display, rm_fin, title="[FIN polish min grille]")

        self._plot_result(display, plot_source="polish_grille_profond")
        self._refresh_data_table()

        _cont_after_deep = getattr(self, "_continue_corridor_auto_refine_after_deep", None)
        if callable(_cont_after_deep) and bool(_cont_after_deep()):
            return

        self._refresh_post_optimization_option_controls()
        self.lbl_status.setText(self._post_optimization_ready_status(status_text))
        self.export_excel(auto_export=True)

    def _finish_rmse_heal_worker_done(self, healed_list: object) -> None:
        """Merge healed points into the main result and refresh."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_corridor_grid_busy(False)

        if not isinstance(healed_list, list) or not healed_list:
            dr = self._last_result if isinstance(self._last_result, dict) else {}
            self._finish_corridor_rmse_d_grid_worker_done(dr)
            return

        # Get baseline from last result
        base = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        d_main = list(np.asarray(base.get("profile_d_values_nm", []), dtype=np.float64).ravel())
        r_main = list(np.asarray(base.get("profile_d_rmse_values", []), dtype=np.float64).ravel())
        s_main = list(base.get("profile_d_full_results", []))

        added = 0
        for item in healed_list:
            if not isinstance(item, dict):
                continue
            dv = item.get("profile_d_val_nm")
            if dv is None:
                continue

            # Replace or add
            match = -1
            for i, d_ex in enumerate(d_main):
                if np.abs(d_ex - dv) < 1e-4:
                    match = i
                    break

            rm = float(np.sqrt(max(float(item.get("mse", 0.0)), 0.0)))
            if match >= 0:
                # Only replace if better!
                if rm < r_main[match] - 1e-15:
                    r_main[match] = rm
                    s_main[match] = item
                    added += 1
            else:
                d_main.append(dv)
                r_main.append(rm)
                s_main.append(item)
                added += 1

        if self.logger:
            self.logger.info("GUI RMSE(d) Grid Healing | Integrated %d improved/healed points", added)

        base["profile_d_values_nm"] = np.array(d_main, dtype=np.float64)
        base["profile_d_rmse_values"] = np.array(r_main, dtype=np.float64)
        base["profile_d_full_results"] = s_main
        base["profile_d_manual_grid_coverage_complete"] = True  # We healed!

        # Finally trigger the standard finalization
        self._finish_corridor_rmse_d_grid_worker_done(base)

    def _apply_corridor_preset_auto_robust(self) -> None:
        """Preset 'Auto robust corridor': local adaptive Delta, symmetry on parabola, stable parameters."""

        if hasattr(self, "cb_corr_mode"):
            self.cb_corr_mode.blockSignals(True)

            try:
                iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                if iq >= 0:
                    self.cb_corr_mode.setCurrentIndex(int(iq))

            finally:
                self.cb_corr_mode.blockSignals(False)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "sp_corridor_rmse_win"):
            self.sp_corridor_rmse_win.setValue(4)

        if hasattr(self, "sp_corridor_rmse_delta"):
            self.sp_corridor_rmse_delta.setValue(2e-4)

        self._corridor_parabola_half_window_pts = 4

        self._corridor_symmetric_center_mode = "parabola"

        self._corridor_adaptive_rmse_ref_half_width_nm = 1.5

        self._corridor_adaptive_rmse_probe_steps_each_side = 3

        self._corridor_adaptive_rmse_noise_factor = 3.0

        self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

        if hasattr(self, "_on_corr_mode_changed"):
            self._on_corr_mode_changed()

        if hasattr(self, "_refresh_corridor_rmse_robust_view"):
            try:
                self._refresh_corridor_rmse_robust_view()

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Corridor RMSE robust refresh after preset failed", exc_info=True)

        if hasattr(self, "_refresh_corridors_gui_state_labels"):
            self._refresh_corridors_gui_state_labels()

    def _set_corridor_grid_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_corridor_rmse_grid_calc"):
            self.btn_corridor_rmse_grid_calc.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_d_step_nm"):
            self.sp_corridor_grid_d_step_nm.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_n_points"):
            self.sp_corridor_grid_n_points.setEnabled(not busy)

        if hasattr(self, "sp_corridor_breakpoint_lookback"):
            self.sp_corridor_breakpoint_lookback.setEnabled(not busy)

        if hasattr(self, "chk_corridor_rmse_envelope_only"):
            self.chk_corridor_rmse_envelope_only.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_data"):
            self.btn_corridor_rmse_export_data.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_envelope_nk"):
            self.btn_corridor_rmse_export_envelope_nk.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "sp_corridor_partial_delta_nm"):
            self.sp_corridor_partial_delta_nm.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_partial_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_auto_smart_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setEnabled(bool(busy))

            if busy:
                self.pb_corridor_rmse_grid.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {CertusTheme.PRIMARY}; }}"
                )
            else:
                self.pb_corridor_rmse_grid.setStyleSheet("")

    def _set_corridor_grid_progress_ui(
        self,
        *,
        done: int,
        total: int,
        base_done: int | None = None,
        base_total: int | None = None,
        extra_done: int | None = None,
        current_d_nm: float | None = None,
    ) -> None:

        tot = max(1, int(total))
        dn = int(max(0, min(done, tot)))
        frac = float(dn) / float(tot)

        # UX-8: Sub-progress injection
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                iteration=self._prog_ui_last,
                max_iter=10000,
                evals=0,
                phase=f"RMSE(d) Grid: {dn}/{tot}",
                extra_info="",
                sub_iteration=dn,
                max_sub_iter=tot,
            )

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setValue(int(round(1000.0 * frac)))

        t0 = float(getattr(self, "_corridor_rmse_grid_live_t0", float("nan")))

        eta_txt = ""

        if np.isfinite(t0) and dn > 0:
            dt = max(0.0, time.perf_counter() - t0)

            avg = dt / float(dn)

            eta = max(0.0, float(tot - dn) * avg)

            eta_txt = f" | avg {avg:.2f}s/pt | ETA {eta:.1f}s"

        d_txt = ""

        if current_d_nm is not None and np.isfinite(float(current_d_nm)):
            d_txt = f" | d={float(current_d_nm):.3f} nm"

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            if base_done is not None and base_total is not None:
                btot = max(1, int(base_total))
                bdn = int(max(0, min(int(base_done), btot)))
                xdn = int(max(0, int(extra_done or 0)))
                bfrac = 100.0 * float(bdn) / float(btot)
                self.lbl_corridor_rmse_grid_progress.setText(
                    f"Grid {bdn}/{btot} ({bfrac:.1f}%) + extra {xdn}{d_txt}{eta_txt}"
                )
            else:
                self.lbl_corridor_rmse_grid_progress.setText(f"Grid {dn}/{tot} ({100.0 * frac:.1f}%){d_txt}{eta_txt}")

    def _sync_corridor_manual_controls(self, d_s: np.ndarray, i_best: int) -> None:

        if (
            not hasattr(self, "sl_corridor_manual_half")
            or not hasattr(self, "btn_generate_manual_corridor")
            or d_s.size == 0
            or i_best < 0
            or i_best >= int(d_s.size)
        ):
            self._reset_corridor_manual_controls()

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        man_active = bool(getattr(self, "_corridor_rmse_manual_active", False))
        man_lo = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))
        man_hi = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))
        has_manual_interval = man_active and np.isfinite(man_lo) and np.isfinite(man_hi) and man_hi >= man_lo
        if has_manual_interval:
            # Preserve the effective manual interval currently applied/generated,
            # instead of recomputing preview solely from the previous slider state.
            d_center = 0.5 * float(man_lo + man_hi)

        self._set_corridor_manual_bounds_labels(float(d_s[0]), d_best, float(d_s[-1]))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_steps = max(1, int(round(max_half * scale)))

        cur_half = self._corridor_manual_half_width_nm()
        if has_manual_interval:
            cur_half = 0.5 * float(max(0.0, man_hi - man_lo))

        if not np.isfinite(cur_half) or cur_half <= 0.0:
            if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
                cur_half = 0.5 * max(0.0, float(self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

            elif d_s.size >= 2:
                cur_half = max(float(np.nanmedian(np.abs(np.diff(d_s)))), 0.0)

            else:
                cur_half = 0.0

        cur_half = float(min(max(cur_half, 0.0), max_half))

        self.sl_corridor_manual_half.blockSignals(True)

        self.sl_corridor_manual_half.setRange(0, max_steps)

        self.sl_corridor_manual_half.setTickInterval(max(1, max_steps // 8))

        self.sl_corridor_manual_half.setValue(int(round(cur_half * scale)))

        self.sl_corridor_manual_half.setEnabled(max_steps > 0)

        self.sl_corridor_manual_half.blockSignals(False)

        self.btn_generate_manual_corridor.setEnabled(True)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(bool(self._corridor_rmse_robust_ok))

        self._set_corridor_manual_interval_preview(d_center, cur_half)

    def _generate_corridor_from_current_grid(self) -> None:
        """Generate n/k corridor from all currently available RMSE(d) grid points."""

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: no RMSE(d) grid in memory")

            QMessageBox.information(self, "Generate corridor (grid)", "No RMSE(d) grid is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        if d_s.size == 0:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: RMSE(d) grid empty")

            QMessageBox.information(self, "Generate corridor (grid)", "No valid RMSE(d) points are available.")

            return

        # Guard against partial live updates: d-values can be present while
        # n/k profile curves are still being filled by the worker.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_s.size
            and k_curves.shape[0] == d_s.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_s.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_lo = float(np.nanmin(d_s))

        d_hi = float(np.nanmax(d_s))

        if self.logger:
            self.logger.info(
                "GUI generate corridor(grid) | request | grid_points=%d | d_range=[%.6f, %.6f] nm",
                int(d_s.size),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from RMSE(d) grid on",
        )

        if not ok:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | failed for current RMSE(d) grid")

            QMessageBox.warning(
                self,
                "Generate corridor (grid)",
                "Unable to generate n/k corridor from the current RMSE(d) grid.",
            )

    def _on_corridor_rmse_plot_clicked(self, ev: Any) -> None:

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        if d_s.size == 0 or r_s.size != d_s.size:
            return

        try:
            vb = self.plot_corridor_rmse_d.plotItem.vb

            p = vb.mapSceneToView(ev.scenePos())

            x = float(p.x())

        except NUMERICAL_FAULT_EXCEPTIONS:
            return

        if not np.isfinite(x):
            return

        i_sel = int(np.argmin(np.abs(d_s - x)))

        d_sel = float(d_s[i_sel])

        r_sel = float(r_s[i_sel])

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if i_best < 0 or i_best >= d_s.size:
            i_best = int(np.argmin(r_s))

        d_best = float(d_s[i_best])

        r_best = float(r_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        rb_ok = bool(getattr(self, "_corridor_rmse_robust_ok", False))

        if hasattr(self, "lbl_corridor_rmse_summary"):
            tail = (
                f" | robust interval ? [{d_lo_rb:.3f}, {d_hi_rb:.3f}] nm"
                if rb_ok and np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb)
                else ""
            )

            self.lbl_corridor_rmse_summary.setText(
                f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {r_best:.6f} | "
                f"selected: d = {d_sel:.3f} nm, RMSE = {r_sel:.6f}, DeltaRMSE = {r_sel - r_best:+.6e}{tail}"
            )
