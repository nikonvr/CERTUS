"""CERTUS-INDEX-SPLINE corridors - the RMSE(d) tab as a view: how it is built and refreshed, its state bar, its bounds, the click on the curve, the robust interval read on the local parabola (methods moved, text unchanged, out of certus_index_spline_corridorui_mixin.py, certus_index_spline_settings.py, certus_index_spline_eventsextras_mixin.py and certus_index_spline_rendering.py)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_core import logger
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
from certus.spline.spline_profile_corridors import _fit_local_quadratic_rmse_profile
from certus.ui.certus_index_spline_corridor_ui import (
    CertusCard,
    CertusScientificPlot,
    CertusTheme,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_ux import Typography


class _CorridorRmseViewMixin:
    """The RMSE(d) tab as a view. A slice of the window: `_CorridorControlMixin` and `CertusIndexSplineCorridorUIMixin` inherit it; what it reads on the window is declared in certus_index_spline_corridor_host.py."""

    def _build_tab_corridor_rmse(self) -> QWidget:
        """Tab Corridor RMSE(d). Orchestrator."""
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)
        ctx_lay.setSpacing(6)
        self._build_corridor_labels(ctx_lay)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        rmse_section = CertusCard("1 — Recalculate RMSE(d)")
        generate_section = CertusCard("2 — Generate corridor n/k")
        self._build_corridor_tab_rmse_controls(rmse_section.body)
        self._build_corridor_tab_generate(generate_section.body)
        ctx_lay.addWidget(rmse_section)
        ctx_lay.addWidget(generate_section)

        self.plot_corridor_rmse_d = CertusScientificPlot(
            title="Corridor profile: RMSE(d)", y_label="RMSE", x_label="d (nm)"
        )
        self.plot_corridor_rmse_d.showGrid(x=True, y=True, alpha=0.25)
        self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_best_idx = -1
        self._corridor_rmse_center_nm = float("nan")
        self._corridor_rmse_grid_live_t0: float = float("nan")
        self._corridor_rmse_live_last_plot_ts: float = float("nan")
        self._corridor_rmse_live_plot_min_interval_s: float = 0.12
        self._corridor_rmse_robust_lo = float("nan")
        self._corridor_rmse_robust_hi = float("nan")
        self._corridor_rmse_robust_ok = False
        self._corridor_rmse_curve = self.plot_corridor_rmse_d.plot(
            [],
            [],
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
            name="RMSE(d)",
        )
        self._corridor_rmse_curve.setZValue(10)
        self._corridor_rmse_best_marker = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CertusTheme.SUCCESS, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self.plot_corridor_rmse_d.addItem(self._corridor_rmse_best_marker)

        self.sp_corridor_rmse_delta.valueChanged.connect(self._refresh_corridor_rmse_robust_view)
        self.sp_corridor_rmse_win.valueChanged.connect(self._refresh_corridor_rmse_robust_view)

        _scene = self.plot_corridor_rmse_d.plotItem.scene()
        if _scene is not None:
            _scene.sigMouseClicked.connect(self._on_corridor_rmse_plot_clicked)

        # Plot area on the LEFT
        lay.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_corridor_rmse_d), 1)

        self._apply_corridor_preset_auto_robust()
        ctx_lay.addStretch(1)
        sa_ctx = QScrollArea()
        sa_ctx.setWidgetResizable(True)
        sa_ctx.setFrameShape(QFrame.Shape.NoFrame)
        sa_ctx.setStyleSheet("background: transparent;")
        sa_ctx.setWidget(ctx_w)
        self._add_context_page(sa_ctx)

        return panel

    def _refresh_corridor_rmse_robust_view(self) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE robust refresh failed", exc_info=True)

    def _update_corridor_rmse_state_bar(self, src: dict[str, Any] | None = None) -> None:

        if not hasattr(self, "lbl_corridor_rmse_state"):
            return

        if not isinstance(src, dict):
            src = self._corridor_profile_source_result()

        if not isinstance(src, dict):
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        src = normalize_corridor_live_payload(src)
        d_s = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        if d_s.size == 0:
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        has_manual = bool(src.get("manual_corridor_active", False))
        d_min = float(np.nanmin(d_s)) if np.any(np.isfinite(d_s)) else float("nan")
        d_max = float(np.nanmax(d_s)) if np.any(np.isfinite(d_s)) else float("nan")

        if has_manual:
            self.lbl_corridor_rmse_state.setText(
                f"Step 3/3: Corridor generated | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )
        else:
            self.lbl_corridor_rmse_state.setText(
                f"Step 2/3: Select an interval, then generate the corridor | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )

    def _corridor_profile_source_result(self) -> dict[str, Any] | None:

        for cand in (self._last_result, self._last_worker_result):
            if not isinstance(cand, dict):
                continue

            d_prof = np.asarray(cand.get("profile_d_values_nm", []), dtype=np.float64).ravel()

            r_prof = np.asarray(cand.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

            if d_prof.size > 0 and r_prof.size == d_prof.size:
                return cand

        return self._last_result

    def _set_corridor_rmse_view_data_bounds(self, d_vals: np.ndarray, r_vals: np.ndarray) -> None:
        """Sets the scale of the RMSE(d) graph to the min/max bounds of the data."""

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        xd = np.asarray(d_vals, dtype=np.float64).ravel()

        yd = np.asarray(r_vals, dtype=np.float64).ravel()

        m = np.isfinite(xd) & np.isfinite(yd)

        xd = xd[m]

        yd = yd[m]

        if xd.size == 0 or yd.size == 0:
            return

        x_lo = float(np.min(xd))

        x_hi = float(np.max(xd))

        y_lo = float(np.min(yd))

        y_hi = float(np.max(yd))

        x_span = max(1e-12, x_hi - x_lo)

        y_span = max(1e-12, y_hi - y_lo)

        x_pad = max(0.25, 0.02 * x_span)

        y_pad = max(1e-8, 0.04 * y_span)

        self.plot_corridor_rmse_d.plotItem.setXRange(x_lo - x_pad, x_hi + x_pad, padding=0.0)

        self.plot_corridor_rmse_d.plotItem.setYRange(y_lo - y_pad, y_hi + y_pad, padding=0.0)

    def _on_corridor_rmse_lock_scale_toggled(self, _checked: bool) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE lock-scale refresh failed", exc_info=True)

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
                f" | robust interval ∈ [{d_lo_rb:.3f}, {d_hi_rb:.3f}] nm"
                if rb_ok and np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb)
                else ""
            )

            self.lbl_corridor_rmse_summary.setText(
                f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {r_best:.6f} | "
                f"selected: d = {d_sel:.3f} nm, RMSE = {r_sel:.6f}, DeltaRMSE = {r_sel - r_best:+.6e}{tail}"
            )

    @staticmethod
    def _robust_interval_from_local_quadratic(
        d_s: np.ndarray,
        r_s: np.ndarray,
        i_best: int,
        delta_rmse: float,
        half_window_pts: int,
    ) -> tuple[bool, float, float, float, float]:

        fit = _fit_local_quadratic_rmse_profile(
            d_s,
            r_s,
            i_best,
            half_window_pts,
            delta_rmse,
        )

        if not bool(fit.get("ok", False)):
            return False, float("nan"), float("nan"), float("nan"), float("nan")

        return (
            True,
            float(fit.get("d_lo", float("nan"))),
            float(fit.get("d_hi", float("nan"))),
            float(fit.get("slope_at_anchor", float("nan"))),
            float(fit.get("curvature", float("nan"))),
        )

    def _build_corridor_labels(self, ctx_lay: QVBoxLayout) -> None:
        hint = QLabel(
            "<b>RMSE(d) corridor profile</b> at all points calculated during profiling. "
            "Raw scatter (unconnected). The <b>parabola</b> is fitted to the min-RMSE envelope by thickness.<br>"
            "<span style='color:#ff8c00;'>&#9646;</span> = Smart Deltad (automatic interval) | "
            "<span style='color:#7a3cff;'>&#9646;</span> = local robust interval | "
            "<span style='color:#ff4d4f;'>&#9646;</span> = manual selection."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(CertusTheme.get_hint_text_style())
        ctx_lay.addWidget(hint)

        self.lbl_corridor_rmse_summary = QLabel("No corridor RMSE profile available yet.")
        self.lbl_corridor_rmse_summary.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: {Typography.BODY_LG}pt;")
        self.lbl_corridor_rmse_summary.setToolTip(
            "<b>Final quality summary</b><br>"
            "Displays the globally optimized thickness d* found on the grid "
            "as well as the RMSE corresponding to the absolute minimum."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_summary)

        self.lbl_corridor_rmse_robust_compact = QLabel("Robust interval: -")
        self.lbl_corridor_rmse_robust_compact.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: {Typography.BODY_LG}pt;")
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
