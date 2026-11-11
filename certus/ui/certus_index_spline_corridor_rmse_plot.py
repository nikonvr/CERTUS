"""CERTUS-INDEX-SPLINE corridors - the drawing of the RMSE(d) tab: the scatter of the profile, the points taken after a break and the fallback evaluations, the breakpoints of the manual grid, the local parabola and the label of its curvature, the sentence above the plot (methods moved, text unchanged, out of certus_index_spline_rendering.py)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from certus.spline.certus_corridor_fitter import _fit_local_quadratic_rmse_profile
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
from certus.ui.certus_index_spline_corridor_ui import CertusTheme

logger = logging.getLogger("CERTUS_INDEX_SPLINE")


class _CorridorRmsePlotMixin:
    """The drawing of the RMSE(d) tab. A slice of the window: `_PlotMixin` inherits it; what it reads on the window is declared in certus_index_spline_corridor_host.py."""

    def _plot_rmse_data_scatter(self, src: dict, ctx: Any) -> None:
        d_plot = np.asarray(ctx.d_plot, dtype=np.float64).ravel()
        r_plot = np.asarray(ctx.r_plot, dtype=np.float64).ravel()
        d_vis = np.asarray(ctx.d_vis, dtype=np.float64).ravel()
        r_vis = np.asarray(ctx.r_vis, dtype=np.float64).ravel()
        kind_vis = np.asarray(getattr(ctx, "kind_vis", np.zeros_like(d_vis, dtype=np.int8)), dtype=np.int8).ravel()
        status_vis = np.asarray(getattr(ctx, "status_vis", np.zeros_like(d_vis, dtype=np.int8)), dtype=np.int8).ravel()
        if hasattr(self, "plot_corridor_rmse_d"):
            self.plot_corridor_rmse_d.clear()
        if d_vis.size != r_vis.size:
            n = min(d_vis.size, r_vis.size)
            d_vis = d_vis[:n]
            r_vis = r_vis[:n]
        if kind_vis.size != d_vis.size:
            kind_vis = np.zeros_like(d_vis, dtype=np.int8)
        if status_vis.size != d_vis.size:
            status_vis = np.zeros_like(d_vis, dtype=np.int8)

        # Live scatter should reflect the current worker data directly.
        # Keep only the extreme outliers clipped for readability.
        rmse_thr_val = src.get("profile_d_rmse_thresh")
        if rmse_thr_val is not None and np.isfinite(float(rmse_thr_val)):
            max_r = 1.5 * float(rmse_thr_val)
        elif r_plot.size > 0:
            _r_min = float(np.nanmin(r_plot)) if np.any(np.isfinite(r_plot)) else float("inf")
            max_r = 1.5 * _r_min if np.isfinite(_r_min) else float("inf")
        else:
            max_r = float("inf")
        m_valid_plot = np.isfinite(d_plot) & np.isfinite(r_plot) & (r_plot <= max_r)
        d_plot = d_plot[m_valid_plot]
        r_plot = r_plot[m_valid_plot]
        if hasattr(self, "_corridor_rmse_curve"):
            try:
                self._corridor_rmse_curve.setData(d_plot, r_plot)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                logger.debug("Failed to update corridor RMSE line curve", exc_info=True)
        m_valid_vis = np.isfinite(d_vis) & np.isfinite(r_vis) & (r_vis <= max_r)
        d_vis = d_vis[m_valid_vis]
        r_vis = r_vis[m_valid_vis]
        kind_vis = kind_vis[m_valid_vis]
        status_vis = status_vis[m_valid_vis]
        i_best = ctx.i_best
        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev

        # Raw scatter: ALL points without visual connection (per scatter paradigm)
        self.plot_corridor_rmse_d.plot(
            d_vis[m_main],
            r_vis[m_main],
            pen=None,
            symbol="o",
            symbolSize=9,
            symbolBrush=pg.mkBrush(0, 87, 255, 220),
            symbolPen=pg.mkPen(CertusTheme.PRIMARY, width=1),
            name="RMSE(d)",
        )
        self._plot_the_reversal_and_fallback_points(d_vis, r_vis, status_vis, m_rev)
        bp_dir_left, bp_dir_right, bp_events = self._plot_the_breakpoint_events(src, d_plot, r_plot)
        if r_plot.size == 0 or d_plot.size == 0:
            self._corridor_rmse_best_idx = None
            return
        i_best = int(np.argmin(r_plot))
        self._corridor_rmse_best_idx = i_best
        d_best = float(d_plot[i_best])
        if hasattr(self, "_corridor_rmse_best_marker"):
            try:
                self._corridor_rmse_best_marker.setValue(d_best)
                self._corridor_rmse_best_marker.setZValue(25)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                logger.debug("Failed to update corridor RMSE best marker", exc_info=True)


        rmse_best = float(r_plot[i_best])
        delta_rb_raw = self.sp_corridor_rmse_delta.value() if hasattr(self, "sp_corridor_rmse_delta") else None
        delta_rb = float(delta_rb_raw) if delta_rb_raw is not None else 2e-4
        win_rb_raw = self.sp_corridor_rmse_win.value() if hasattr(self, "sp_corridor_rmse_win") else None
        win_rb = int(win_rb_raw) if win_rb_raw is not None else 3
        live_parab = (
            not hasattr(self, "chk_corridor_rmse_live_parabola") or self.chk_corridor_rmse_live_parabola.isChecked()
        )
        curvature_label_spec: tuple[float, float, float] | None = None

        # --- Min-RMSE per unique d for the parabolic fit (correct profile likelihood) ---
        # To absorb floating-point duplicates (e.g. d_opt inserted twice by the walk),
        # group at 1e-6 nm then keep the minimal RMSE per d.
        _d_rounded = np.round(d_plot, decimals=6)
        _d_parab_list: list[float] = []
        _r_parab_list: list[float] = []
        for _dv in np.unique(_d_rounded):
            _m = _d_rounded == _dv
            if not np.any(_m):
                continue
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
        self.plot_corridor_rmse_d.plot(
            [d_best],
            [rmse_best],
            pen=None,
            symbol="o",
            symbolSize=12,
            symbolBrush=pg.mkBrush("#20c997"),
            symbolPen=pg.mkPen("#0a5f42", width=1),
            name="Best d*",
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

        curvature_label_spec = self._draw_the_local_parabola(d_plot, d_best, curvature_label_spec, d_parab_arr, parab_fit, d_center)

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

    def _plot_the_reversal_and_fallback_points(self, d_vis, r_vis, status_vis, m_rev):
        """Overlay the points taken after a break (reversal) and the three kinds of fallback evaluation on the RMSE(d) scatter."""
        if np.any(m_rev):
            self.plot_corridor_rmse_d.plot(
                d_vis[m_rev],
                r_vis[m_rev],
                pen=None,
                symbol="t",
                symbolSize=11,
                symbolBrush=pg.mkBrush(255, 140, 0, 200),
                symbolPen=pg.mkPen(255, 140, 0, 220),
                name="RMSE(d) reprise cassure",
            )

        # Overlay fallback points so users can immediately see where strict Deltad
        # sampling used non-standard evaluation paths.
        m_fb_seed = np.asarray(status_vis == 1, dtype=bool)
        m_fb_obj = np.asarray(status_vis == 2, dtype=bool)
        m_fb_emg = np.asarray(status_vis == 3, dtype=bool)
        if np.any(m_fb_seed):
            self.plot_corridor_rmse_d.plot(
                d_vis[m_fb_seed],
                r_vis[m_fb_seed],
                pen=None,
                symbol="x",
                symbolSize=12,
                symbolBrush=pg.mkBrush(255, 255, 255, 0),
                symbolPen=pg.mkPen("#ff8c00", width=2),
                name="Fallback seed",
            )
        if np.any(m_fb_obj):
            self.plot_corridor_rmse_d.plot(
                d_vis[m_fb_obj],
                r_vis[m_fb_obj],
                pen=None,
                symbol="d",
                symbolSize=13,
                symbolBrush=pg.mkBrush(255, 255, 255, 0),
                symbolPen=pg.mkPen("#c2185b", width=2),
                name="Fallback objectif",
            )
        if np.any(m_fb_emg):
            self.plot_corridor_rmse_d.plot(
                d_vis[m_fb_emg],
                r_vis[m_fb_emg],
                pen=None,
                symbol="s",
                symbolSize=14,
                symbolBrush=pg.mkBrush(255, 255, 255, 0),
                symbolPen=pg.mkPen("#6a1b9a", width=2),
                name="Fallback urgence",
            )

    def _plot_the_breakpoint_events(self, src, d_plot, r_plot):
        """Mark the breakpoint events of the manual grid on the RMSE(d) scatter by what triggered them; return the events and how many broke towards each side."""
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
            self.plot_corridor_rmse_d.plot(
                np.asarray(bp_d_vals, dtype=np.float64),
                np.asarray(bp_r_vals, dtype=np.float64),
                pen=None,
                symbol="o",
                symbolSize=15,
                symbolBrush=pg.mkBrush(255, 236, 139, 220),
                symbolPen=pg.mkPen("#9b111e", width=2),
                name="Breakpoints",
            )
        if bp_d_prevn:
            self.plot_corridor_rmse_d.plot(
                np.asarray(bp_d_prevn, dtype=np.float64),
                np.asarray(bp_r_prevn, dtype=np.float64),
                pen=None,
                symbol="d",
                symbolSize=13,
                symbolBrush=pg.mkBrush(255, 255, 255, 0),
                symbolPen=pg.mkPen("#9b111e", width=2),
                name="Breakpoint prevN",
            )
        if bp_d_parab:
            self.plot_corridor_rmse_d.plot(
                np.asarray(bp_d_parab, dtype=np.float64),
                np.asarray(bp_r_parab, dtype=np.float64),
                pen=None,
                symbol="t",
                symbolSize=14,
                symbolBrush=pg.mkBrush(255, 255, 255, 0),
                symbolPen=pg.mkPen("#7a3cff", width=2),
                name="Breakpoint parabola",
            )
        return bp_dir_left, bp_dir_right, bp_events

    def _draw_the_local_parabola(self, d_plot, d_best, curvature_label_spec, d_parab_arr, parab_fit, d_center):
        """Draw the local parabolic fit of RMSE(d), its centre line, and return the label spec of its curvature when the fit has a minimum."""
        if bool(parab_fit.get("ok", False)):
            if d_parab_arr.size > 0:
                _parab_default = (float(np.min(d_parab_arr)), float(np.max(d_parab_arr)))
            else:
                _parab_default = (float("nan"), float("nan"))
            win_lo, win_hi = parab_fit.get("window_nm", _parab_default)
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

            # Center the corridor display around the parabola minimum with a +/-5% window.
            if np.isfinite(d_center_fit) and d_center_fit > 0.0:
                d_min_val = 0.95 * float(d_center_fit)
                d_max_val = 1.05 * float(d_center_fit)
            else:
                d_min_val = float(d_center_fit - half_span)
                d_max_val = float(d_center_fit + half_span)

            if not np.isfinite(d_min_val) or not np.isfinite(d_max_val) or d_max_val <= d_min_val:
                d_min_val = float(np.min(d_plot)) if d_plot.size > 0 else float(d_center_fit - half_span)
                d_max_val = float(np.max(d_plot)) if d_plot.size > 0 else float(d_center_fit + half_span)

            d_par = np.linspace(
                d_min_val,
                d_max_val,
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

            # c2 = quadratic coefficient (RMSE = c2x^2+c1x+c0, x = d - anchor); vertex at d_center.
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
        return curvature_label_spec

    @staticmethod
    def _corridor_profile_arrays(src: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
        norm = normalize_corridor_live_payload(src)
        d_plot = np.asarray(norm.get("corridor_d_plot", []), dtype=np.float64).ravel()
        r_plot = np.asarray(norm.get("corridor_rmse_plot", []), dtype=np.float64).ravel()
        d_vis = np.asarray(norm.get("corridor_d_vis", d_plot), dtype=np.float64).ravel()
        r_vis = np.asarray(norm.get("corridor_rmse_vis", r_plot), dtype=np.float64).ravel()
        live_status = str(norm.get("profile_d_status", ""))
        return d_plot, r_plot, d_vis, r_vis, live_status

    def _prep_rmse_plot_data(self, src: dict):
        """Prepare a corridor-RMSE plotting context from a result dictionary."""
        from types import SimpleNamespace

        if not isinstance(src, dict):
            return None

        d_plot, r_plot, d_vis, r_vis, live_status = self._corridor_profile_arrays(src)

        kind_vis = np.asarray(src.get("corridor_kind_vis", np.zeros_like(d_vis, dtype=np.int8)), dtype=np.int8).ravel()
        status_vis = np.asarray(src.get("corridor_status_vis", np.zeros_like(d_vis, dtype=np.int8)), dtype=np.int8).ravel()

        if kind_vis.size != d_vis.size:
            kind_vis = np.zeros_like(d_vis, dtype=np.int8)
        if status_vis.size != d_vis.size:
            status_vis = np.zeros_like(d_vis, dtype=np.int8)

        d_best = float(src.get("d_nm", src.get("d_best", np.nan)))
        rmse_best = float(src.get("rmse", src.get("rmse_best", np.nan)))
        rmse_thr = src.get("profile_d_threshold_rmse", src.get("rmse_threshold", src.get("rmse_thr", None)))
        if rmse_thr is not None:
            try:
                rmse_thr = float(rmse_thr)
            except (TypeError, ValueError):
                rmse_thr = None

        parab_fit = src.get("corridor_parab_fit", src.get("parab_fit", {})) or {}
        curvature_label_spec = src.get("curvature_label_spec", None)
        live_parab = bool(src.get("live_parab", False))
        envelope_display = bool(src.get("envelope_display", True))
        is_live_grid = bool(src.get("is_live_grid", False) or live_status == "manual_grid_live")
        if d_plot.size > 0 and r_plot.size == d_plot.size:
            finite_r = np.isfinite(r_plot)
            i_best_default = int(np.nanargmin(np.where(finite_r, r_plot, np.inf))) if np.any(finite_r) else 0
        else:
            i_best_default = 0
        i_best = int(src.get("i_best", i_best_default) or i_best_default)
        win_rb = src.get("win_rb", 3)
        if win_rb is None:
            win_rb = 3
        delta_rb = src.get("delta_rb", 2e-4)
        if delta_rb is None:
            delta_rb = 2e-4

        rb_ok = bool(src.get("rb_ok", False))
        d_lo_rb = float(src.get("d_lo_rb", np.nan))
        d_hi_rb = float(src.get("d_hi_rb", np.nan))
        slope_b = float(src.get("slope_b", np.nan))
        curv_b = float(src.get("curv_b", np.nan))
        d_center = float(src.get("d_center", d_best))
        bp_events = src.get("bp_events", [])
        bp_dir_left = int(src.get("bp_dir_left", 0) or 0)
        bp_dir_right = int(src.get("bp_dir_right", 0) or 0)

        return SimpleNamespace(
            d_plot=d_plot,
            r_plot=r_plot,
            d_vis=d_vis,
            r_vis=r_vis,
            kind_vis=kind_vis,
            status_vis=status_vis,
            i_best=i_best,
            parab_fit=parab_fit,
            curvature_label_spec=curvature_label_spec,
            envelope_display=envelope_display,
            is_live_grid=is_live_grid,
            live_parab=live_parab,
            d_best=d_best,
            rmse_best=rmse_best,
            rmse_thr=rmse_thr,
            d_parab_arr=d_vis,
            r_parab_arr=r_vis,
            win_rb=win_rb,
            delta_rb=delta_rb,
            rb_ok=rb_ok,
            d_lo_rb=d_lo_rb,
            d_hi_rb=d_hi_rb,
            slope_b=slope_b,
            curv_b=curv_b,
            d_center=d_center,
            bp_events=bp_events if isinstance(bp_events, list) else [],
            bp_dir_left=bp_dir_left,
            bp_dir_right=bp_dir_right,
        )

    def _draw_corridor_curvature_label(self, curvature_label_spec, r_vis, r_plot, envelope_display) -> None:
        if curvature_label_spec is None or not hasattr(self, "plot_corridor_rmse_d"):
            return
        c2_l, d_vl, r_vl = curvature_label_spec
        c2_disp = float(abs(c2_l))
        if not np.isfinite(c2_disp) or c2_disp <= 0.0:
            return
        r_span_src = r_vis if envelope_display else r_plot
        span_r = (
            float(np.nanmax(r_span_src) - np.nanmin(r_span_src))
            if r_span_src.size > 1
            else max(1e-6, abs(float(r_vl)) * 0.05 if np.isfinite(r_vl) else 1e-4)
        )
        dy = max(1e-6, 0.035 * span_r)
        existing = getattr(self, "_corridor_rmse_curvature_label", None)
        if existing is not None:
            try:
                self.plot_corridor_rmse_d.removeItem(existing)
            except (AttributeError, RuntimeError):
                pass
        label_a = pg.TextItem(
            text=f"Curvature a = {c2_disp:.4e} nm?^2",
            color="#7a3cff",
            anchor=(0.5, 1),
            fill=pg.mkColor(255, 255, 255, 220),
        )
        label_a.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        label_a.setPos(d_vl, r_vl + dy)
        self.plot_corridor_rmse_d.addItem(label_a, ignoreBounds=True)
        self._corridor_rmse_curvature_label = label_a

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
        self._corridor_rmse_d_vals = np.asarray(d_plot, dtype=np.float64).copy()
        self._corridor_rmse_vals = np.asarray(r_plot, dtype=np.float64).copy()
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
            # Look for the intersection points (simple linear scan on the lower envelope)
            # Note: d_parab_arr is sorted? and contains the min-per-d envelope
            if d_parab_arr.size > 2:
                try:
                    _m_below = r_parab_arr <= thr
                    if np.any(_m_below):
                        _d_below = d_parab_arr[_m_below]
                        if _d_below.size > 0:
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

            # Labels on the smart lines
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
            if r_plot.size > 0:
                _r_range = float(np.max(r_plot) - np.min(r_plot)) if r_plot.size > 1 else 1e-4
                _r_label = float(np.nanmin(r_plot)) + 0.05 * _r_range
            else:
                _r_label = 0.0
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
            _grid_note = self._manual_grid_note(src, bp_events, bp_dir_left, bp_dir_right)
            self._write_the_rmse_summary(
                src,
                d_plot,
                d_vis,
                parab_fit,
                envelope_display,
                is_live_grid,
                live_parab,
                d_best,
                rmse_best,
                delta_rb,
                rb_ok,
                d_lo_rb,
                d_hi_rb,
                slope_b,
                d_center,
                d_lo_man,
                d_hi_man,
                _grid_note,
            )
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

        # Live mode must stay fully automatic in both axes.
        if is_live_grid:
            self.plot_corridor_rmse_d.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
            self.plot_corridor_rmse_d.autoRange()
        else:
            # Center the full corridor view around the parabola minimum with a +/-5% window.
            if np.isfinite(d_center) and d_center > 0.0:
                d_lo_fit = 0.95 * float(d_center)
                d_hi_fit = 1.05 * float(d_center)
                if d_hi_fit > d_lo_fit:
                    self.plot_corridor_rmse_d.setXRange(d_lo_fit, d_hi_fit, padding=0.0)
                else:
                    self.plot_corridor_rmse_d.autoRange()
            elif np.isfinite(d_lo_man) and np.isfinite(d_hi_man) and d_hi_man >= d_lo_man:
                self.plot_corridor_rmse_d.setXRange(float(d_lo_man), float(d_hi_man), padding=0.0)
            elif rb_ok and np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb > d_lo_rb:
                self.plot_corridor_rmse_d.setXRange(float(d_lo_rb), float(d_hi_rb), padding=0.0)
            else:
                self.plot_corridor_rmse_d.autoRange()
        try:
            self.plot_corridor_rmse_d.repaint()
            self.plot_corridor_rmse_d.update()
            self.plot_corridor_rmse_d.plotItem.vb.update()
        except (AttributeError, RuntimeError):
            logger.debug("Corridor RMSE(d) repaint failed", exc_info=True)

        # Mathematically adjust Y scale to focus on the valley and exclude outliers/aberrant points
        if is_live_grid:
            self.plot_corridor_rmse_d.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
            self.plot_corridor_rmse_d.autoRange()
        elif not lock_scale:
            delta_rb_eff = max(delta_rb, 2e-4)
            y_min_val = rmse_best - 0.25 * delta_rb_eff
            y_max_val = rmse_best + 2.0 * delta_rb_eff
            if rmse_thr is not None and np.isfinite(float(rmse_thr)):
                y_max_val = max(y_max_val, float(rmse_thr) + 0.5 * delta_rb_eff)
            y_min_val = max(1e-6, y_min_val)
            self.plot_corridor_rmse_d.plotItem.setYRange(y_min_val, y_max_val, padding=0.0)
        self._draw_corridor_curvature_label(curvature_label_spec, r_vis, r_plot, envelope_display)
        self._update_corridor_rmse_state_bar(src)

    def _manual_grid_note(self, src, bp_events, bp_dir_left, bp_dir_right):
        """Return the part of the summary that tells the d grid was a manual one, how many breakpoints and extra points it had, what triggered them and towards which side they broke."""
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
        return _grid_note

    def _write_the_rmse_summary(self, src, d_plot, d_vis, parab_fit, envelope_display, is_live_grid, live_parab, d_best, rmse_best, delta_rb, rb_ok, d_lo_rb, d_hi_rb, slope_b, d_center, d_lo_man, d_hi_man, _grid_note):
        """Write the one-line summary of the RMSE(d) tab: the best thickness and its RMSE, the plot, grid and Deltad notes, the robust interval and the manual one when there is one."""
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
