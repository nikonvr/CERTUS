# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE Run Execution and Data Export Mixins.
Contains _CorridorExportMixin and _RunMixin.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QApplication

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_ui import GenericWorker, safe_ui_action
from certus.spline.certus_index_spline_core import (
    SplineOptConfig,
    log_index_spline_d_trace,
    _log_index_spline_best_config,
    ensure_lam_nm_array,
    _to_fraction_T,
    reset_smart_init_preview_guard
)
from certus.utils.certus_index_utils import (
    log_structured_json_event,
    _rmse_d_lower_envelope_mask,
    _spectral_display_align
)
from certus.spline.spline_objective import _spline_objective_lam_mask
from certus.spline.spline_workers import worker_auto_best_split_knot_refinement
from certus.spline.spline_pipeline import worker_spline_optimization
from certus.utils.certus_skeleton import install_skeleton
from certus.ui.certus_ui import get_certus_last_dir, set_certus_last_dir, CertusTheme
try:
    from certus.spline.spline_visual_utils import snap_spline_visual_dict as _snap_spline_visual_dict
except ImportError:
    try:
        from certus.spline.spline_pipeline import _snap_spline_visual_dict
    except ImportError:
        def _snap_spline_visual_dict(result: dict[str, Any]) -> dict[str, Any]:
            return dict(result)



logger = logging.getLogger("CERTUS_INDEX_SPLINE")

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
        lines.append("# CERTUS INDEX-SPLINE - Corridor RMSE(d) export")
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
            lines.append("# (unavailable - need 5 local points for convex quadratic fit)")

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
        # Fallback helper path check
        from certus.spline.certus_index_spline_rendering import _SCRIPT_DIR as rendering_script_dir
        if not start_dir or not Path(start_dir).is_dir():
            start_dir = str(rendering_script_dir)

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
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("lambda_nm,n,n_envelope_min,n_envelope_max,k,k_envelope_min,k_envelope_max\n")
                for i in range(m):
                    line = f"{float(lam_g[i]):.4f},"
                    line += self._fmt_n_data_tab(float(n_g[i])) + ","
                    line += self._fmt_n_data_tab(float(n_lo_g[i])) + ","
                    line += self._fmt_n_data_tab(float(n_hi_g[i])) + ","
                    line += self._fmt_k_data_tab(float(k_g[i])) + ","
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

        if self.logger:
            self.logger.info(
                "RUN dispatch worker=%s prep_elapsed=%.3fs",
                getattr(self._worker.func, "__name__", "?"),
                time.perf_counter() - t_run_cfg,
            )

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
        # Helper to avoid circular import if needed, otherwise local import
        try:
            from certus.ui.certus_index_spline_ui import _add_spectrum_thickness_badge as badge_fn
        except ImportError:
            # Fallback to local rendering module badge function if defined, or stub
            badge_fn = lambda *args: None
        badge_fn(self.plot_T, x_mod, y_spec, d_nm)

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
