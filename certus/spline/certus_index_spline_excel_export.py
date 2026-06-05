# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Excel Export Module.
Contains _RMSEPlotContext and _ExcelExportMixin.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, __version__
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_data import (
    build_export_context,
    build_report_sections,
    export_optimization_report,
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

