"""CERTUS-INDEX-SPLINE corridors - the corridor tab: its plot and its RMSE controls (moved out of certus_index_spline_corridor_worker.py, S5.3)."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QCheckBox, QDoubleSpinBox, QSpinBox

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_corridor_utils import enforce_min_k_corridor_half_width
from certus.spline.certus_index_spline_corridor_common import (
    _CORRIDOR_K_TAB_MIN_HALF_WIDTH,
    _apply_fixed_log_k_axis,
)
from certus.spline.certus_index_spline_corridor_ui import (
    CertusTheme,
    EnhancedProgressWidget,
    create_styled_button,
    plot_widget_plot_finite,
)


class _CorridorTabMixin:
    """The corridor tab of the window: what it draws and the controls above it. Used through `_CorridorWorkerMixin`, which inherits it."""

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

        # lam_s / n_s / k_s come from _spectral_display_align: already co-linear and sorted by lambda.
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
            "Export an Excel file (.xlsx) with two sheets (n, k), on λ grids 2/5/10 nm, for RMSE(d) envelope points."
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
            "Corridor from partial grid", "primary", parent=self
        )
        self.btn_corridor_generate_from_partial_grid.setEnabled(False)
        self.btn_corridor_generate_from_partial_grid.setToolTip(
            "Build corridor n/k from a partial RMSE(d) grid centered on current d*.\n"
            "The width is controlled by Corridor Delta d (+/- nm)."
        )
        self.btn_corridor_generate_from_partial_grid.clicked.connect(self._generate_corridor_from_partial_grid)
        row_generate_grid.addWidget(self.btn_corridor_generate_from_partial_grid)

        self.btn_corridor_generate_auto_smart_grid = create_styled_button(
            "Auto smart corridor", "primary", parent=self
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
