# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE UI Rendering and Plotting Mixins.
Contains _PlotMixin and _UIBuilderMixin.
"""

from __future__ import annotations
import logging
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QScrollArea, QFrame, QTabWidget, QStackedWidget, QCheckBox,
    QDoubleSpinBox, QSpinBox, QComboBox, QSlider
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
    EnhancedProgressWidget
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
        self.lbl_postprocess_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
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
