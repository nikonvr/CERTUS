# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE UI Rendering and Plotting Mixins.
Contains _PlotMixin and _UIBuilderMixin.
"""

from __future__ import annotations
import logging
from typing import Any

import numpy as np
from certus.spline.certus_index_spline_excel_export import _RMSEPlotContext
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QScrollArea, QFrame, QTabWidget, QStackedWidget, QCheckBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QSlider, QGridLayout
)

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_ui import (
    CertusTheme,
    CertusThemeToggle,
    CertusCard,
    CertusStepper,
    CertusStatusPill,
    CertusScientificPlot,
    create_header_logo_widget,
    setup_pyqtgraph_defaults,
    create_styled_button,
    wrap_scientific_plot_with_toolbar,
    ExcelTableWidget,
    sanitize_xy_for_plot,
    plot_widget_plot_finite,
    EnhancedProgressWidget,
    CertusCollapsible,
    CertusLogPanel
)
from certus.utils.certus_ux import OBJ
from certus.utils.certus_reset_framework import create_reset_button
from certus.spline.certus_index_spline_core import (
    allowed_substrate_names,
    SIO2_DEFAULT_D_LO_NM,
    SIO2_DEFAULT_D_HI_NM,
    SPLINE_PERF_PRESETS
)
from certus.core.certus_design_tokens import slider_corridor_half_stylesheet

from certus.spline.certus_corridor_fitter import _fit_local_quadratic_rmse_profile
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
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
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        lam = np.asarray(lam_g, dtype=np.float64).ravel()
        nv = np.asarray(n_g, dtype=np.float64).ravel()
        kv = np.asarray(k_g, dtype=np.float64).ravel()
        n_nl_v = np.full_like(lam, np.nan)
        k_nl_v = np.full_like(lam, np.nan)
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
            except NUMERICAL_FAULT_EXCEPTIONS:
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

    def _plot_rmse_data_scatter(self, src: dict, ctx: "_RMSEPlotContext") -> None:
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

        # Scatter brut : TOUS les points sans liaison visuelle (conformément au paradigme scatter)
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

        # --- Min-RMSE par d unique pour le fit parabolique (profile likelihood correcte) ---
        # Pour absorber les doublons flottants (ex. d_opt ins?r? 2? par le walk),
        # on regroupe ? 1e-6 nm puis on conserve le RMSE minimal par d.
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
            # On cherche les points d'intersection (simple scan lin?aire sur l'enveloppe basse)
            # Note: d_parab_arr est tri? et contient l'enveloppe min-per-d
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
        self.lbl_file.setStyleSheet(CertusTheme.get_hint_text_style())
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
        self.lbl_postprocess_hint.setStyleSheet(CertusTheme.get_hint_text_style())
        action_card.body.addWidget(self.lbl_postprocess_hint)
        action_card.body.addWidget(self.lbl_corridors_run_state)

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.stateChanged.connect(self._on_corridor_chk_state_changed)

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
        self.main_split.addWidget(info_panel)
        self.main_split.addWidget(plots_panel)
        nc = int(self.main_split.count())
        if nc >= 1:
            self.main_split.setCollapsible(0, True)
        if nc >= 2:
            self.main_split.setCollapsible(1, True)
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
        lbl_manual.setStyleSheet(CertusTheme.get_hint_text_style())
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
            _lab.setStyleSheet(CertusTheme.get_hint_text_style())

        row_manual_meta.addWidget(self.lbl_corridor_manual_dmin)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dcenter)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dmax)
        row_manual_meta.addStretch(1)
        row_manual_meta.addWidget(self.lbl_corridor_manual_interval)
        lay_generate.addLayout(row_manual_meta)

    def _build_tab_data(self) -> QWidget:
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
        self.table_nk.setColumnCount(7)
        self.table_nk.setHorizontalHeaderLabels(
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
        self.table_nk.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        self.table_nk.horizontalHeader().setStretchLastSection(True)
        self.table_nk.setToolTip(
            "lambda grid by spectral region: 2 nm step (<=400 nm), 5 nm (400-1200 nm), "
            "10 nm beyond; n, k and envelopes interpolated from result mesh. "
            "Envelopes: corridor bounds (d profiling). "
            "Previews: all n (or k) curves, envelope band if corridor; synchronized lambda cursor. "
            "Ctrl+C: copy selection (TSV) -> Excel."
        )

        lay.addWidget(self.table_nk, 2)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

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
        hint.setStyleSheet(CertusTheme.get_hint_text_style())
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
        hint = QLabel(
            "<b>RMSE(d) corridor profile</b> at all points calculated during profiling. "
            "Raw scatter (unconnected). The <b>parabola</b> is fitted to the min-RMSE envelope by thickness.<br>"
            "<span style='color:#ff8c00;'>&#9646;</span> = Smart Deltad (automatic interval) | "
            "<span style='color:#7a3cff;'>&#9646;</span> = local robust interval | "
            "<span style='color:#ff4d4f;'>&#9646;</span> = manual selection."
        )
        hint.setStyleSheet(CertusTheme.get_hint_text_style())
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
        self.lbl_corridor_rmse_state.setStyleSheet(CertusTheme.get_hint_text_style())
        self.lbl_corridor_rmse_state.setToolTip(
            "<b>Progress / Diagnostic</b><br>"
            "Displays the current pipeline step (Calculation, Fit, or Export) "
            "and any alert messages related to convergence."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_state)

    def _build_tab_corridor(self) -> QWidget:
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
        hint.setStyleSheet(CertusTheme.get_hint_text_style())
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
