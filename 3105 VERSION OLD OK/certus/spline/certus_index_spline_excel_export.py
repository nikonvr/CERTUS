# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Excel Export Module.
Contains _RMSEPlotContext and _ExcelExportMixin.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyqtgraph as pg

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, __version__
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_data import (
    build_export_context,
    build_report_sections,
    export_optimization_report,
    validate_manifest_for_export,
)
from certus.ui.certus_ui import CertusTheme
from certus.utils.certus_index_utils import (
    _rmse_d_lower_envelope_mask,
    _filter_rmse_peaks_iteratively,
)

# Helper structures originally defined in CERTUS_INDEX_SPLINE

@dataclass
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
            corr_enabled = bool(hasattr(self, "chk_corridor_d") and self.chk_corridor_d.isChecked())
            boot_enabled = bool(hasattr(self, "chk_corr_boot") and self.chk_corr_boot.isChecked())
            corr_seed = int(self.sp_corr_seed.value()) if hasattr(self, "sp_corr_seed") else 0
            boot_seed = int(self.sp_corr_boot_seed.value()) if hasattr(self, "sp_corr_boot_seed") else 0
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
                source_paths=[str(getattr(self, "_last_spectrum_path", ""))],
                seed=(int(self.sp_corr_seed.value()) if hasattr(self, "sp_corr_seed") else None),
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
            manifest_dict,
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
            "Spectrum": str(getattr(self, "_last_spectrum_path", "")),
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
            subtitle=f"Spectrum={Path(getattr(self, '_last_spectrum_path', '')).name}",
            app_name="CERTUS-INDEX-SPLINE",
            run_manifest=manifest_dict,
            warnings=list(getattr(self, "validation_warnings", []) or []),
            status=str(getattr(self, "validation_status", "OK") or "OK"),
        )
        sections = build_report_sections(
            summary_dict=summary_dict,
            solution_df=solution_df,
            spectra_df=spectra_df,
            manifest=manifest_dict,
            extra_sheets=extra_sheets or None,
        )
        self.logger.debug(
            "INDEX_SPLINE export context prepared | title=%s | sections=%d | subtitle=%s",
            report_ctx.title,
            len(sections),
            report_ctx.subtitle,
        )
        excel_path, html_path = export_optimization_report(
            reports_dir=str(Path(getattr(self, "_last_spectrum_path", "")).parent / "reports"),
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

        # Filter out aberrant points (RMSE far above threshold) to keep the y-axis autoscale tight.
        rmse_thr_val = src.get("profile_d_rmse_thresh")
        if rmse_thr_val is not None and np.isfinite(float(rmse_thr_val)):
            max_r = 1.5 * float(rmse_thr_val)
        else:
            max_r = 1.5 * np.min(r_vis) if r_vis.size > 0 else float("inf")
        
        m_valid_plot = r_vis <= max_r
        d_vis = d_vis[m_valid_plot]
        r_vis = r_vis[m_valid_plot]
        kind_vis = kind_vis[m_valid_plot]
        status_vis = status_vis[m_valid_plot]

        i_best = ctx.i_best
        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev

        # Scatter brut : TOUS les points sans liaison visuelle (conformément au paradigme scatter)
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
                    bp_d_vals,
                    bp_r_vals,
                    pen=pg.mkPen("#9b111e", width=3),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=12,
                    symbol="o",
                    name="Cassure détectée",
                )
            )
            if bp_d_prevn:
                self.plot_corridor_rmse_d.addItem(
                    pg.ScatterPlotItem(
                        bp_d_prevn,
                        bp_r_prevn,
                        pen=pg.mkPen("#9b111e", width=2),
                        brush=pg.mkBrush(255, 255, 255, 0),
                        size=14,
                        symbol="+",
                        name="Cassure (Hausse RMSE)",
                    )
                )
            if bp_d_parab:
                self.plot_corridor_rmse_d.addItem(
                    pg.ScatterPlotItem(
                        bp_d_parab,
                        bp_r_parab,
                        pen=pg.mkPen("#7a3cff", width=2),
                        brush=pg.mkBrush(255, 255, 255, 0),
                        size=14,
                        symbol="x",
                        name="Cassure (Rupture parabole)",
                    )
                )
