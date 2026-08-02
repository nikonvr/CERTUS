#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


n(lambda) and k(lambda) curve editor for Smart Init: draggable PWL nodes, log scale k.


UX: large points, wide lambda target, closest in value, hover feedback + live drag.


"""

from __future__ import annotations
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS


from typing import Callable


import numpy as np


import pyqtgraph as pg


from PyQt6.QtCore import QEvent, QObject, Qt, QTimer


from PyQt6.QtGui import QMouseEvent


from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)


from certus.ui.certus_ui import (
    CertusTheme,
    apply_certus_theme,
    attach_excel_clipboard_context_menu,
    CertusScientificPlot,
    wrap_scientific_plot_with_toolbar,
)


# Symbol sizes (pxMode = screen size, easier to aim)


_SIZE_NORMAL = 16


_SIZE_HOVER = 22


_SIZE_DRAG = 26


# "Column" width around each lambda (pixels) + vertical margin (pixels)


_PICK_PX_X = 32


_PICK_PX_Y = 44


class _PlotDragFilter(QObject):
    """Mouse: wide vertical band around lambda, closest in n or k; vertical drag only."""

    def __init__(
        self,
        plot_widget: CertusScientificPlot,
        scatter: pg.ScatterPlotItem,
        line_item: pg.PlotCurveItem,
        *,
        kind: str,
        set_value_at_physical: Callable[[int, float], None],
        y_clip: tuple[float, float],
        _request_recalc_throttled: Callable[[], None],
        request_recalc_now: Callable[[], None],
        refresh_cb: Callable[[], None],
        hover_callback: Callable[[str, int | None], None],
        sizes_callback: Callable[[str, int | None, int | None], None],
    ) -> None:

        super().__init__(plot_widget)

        self._pw = plot_widget

        self._scatter = scatter

        self._line = line_item

        self._kind = kind

        self._set_val = set_value_at_physical

        self._y_lo, self._y_hi = float(y_clip[0]), float(y_clip[1])

        self._now = request_recalc_now

        self._refresh = refresh_cb

        self._hover_cb = hover_callback

        self._sizes_cb = sizes_callback

        self._drag_j: int | None = None

        self._hover_j: int | None = None

        self._my_press: float = 0.0

        self._y_at_press: float = 0.0

        self._debounce = QTimer()

        self._debounce.setSingleShot(True)

        self._debounce.setInterval(95)

        self._debounce.timeout.connect(self._on_debounce_recalc)

        self._idx_map: np.ndarray | None = None

        self._vp = plot_widget.viewport()
        self._vp.installEventFilter(self)

    def detach(self) -> None:
        """Detach the filter before plot destruction (prevents RuntimeError on deleted C++ QObject)."""
        self._debounce.stop()
        try:
            self._vp.removeEventFilter(self)
        except RuntimeError:
            pass

    def _on_debounce_recalc(self) -> None:

        self._now()

    def _map_event_to_view(self, ev: QMouseEvent) -> tuple[float, float]:

        vb = self._pw.plotItem.vb

        pos = ev.position().toPoint()

        scene_pt = self._pw.mapToScene(pos)
        vpt = vb.mapSceneToView(scene_pt)
        return float(vpt.x()), float(vpt.y())

    def _data_tols(self) -> tuple[float, float]:
        vb = self._pw.plotItem.vb
        xr = vb.viewRange()[0]
        yr = vb.viewRange()[1]
        rw = max(float(xr[1] - xr[0]), 1e-30)
        rh = max(float(yr[1] - yr[0]), 1e-30)
        w_px = max(1, int(self._vp.width()))
        h_px = max(1, int(self._vp.height()))
        tol_x = float(_PICK_PX_X) * rw / float(w_px)
        tol_y_soft = float(_PICK_PX_Y) * rh / float(h_px)
        return tol_x, tol_y_soft

    def _pick_j(self, mx: float, my: float) -> int | None:
        """In a vertical band around each lambda, picks the node closest in value."""
        xd, yd = self._scatter.getData()
        if xd is None or yd is None or len(xd) == 0:
            return None
        xd = np.asarray(xd, dtype=np.float64)
        yd = np.asarray(yd, dtype=np.float64)
        tol_x, _ = self._data_tols()
        best_j = None
        best_dy = float("inf")
        for j in range(len(xd)):
            if not np.isfinite(xd[j]) or not np.isfinite(yd[j]):
                continue
            if abs(float(xd[j]) - mx) > tol_x:
                continue
            dy = abs(float(yd[j]) - my)
            if dy < best_dy:
                best_dy = dy
                best_j = j
        return best_j

    def _physical_index(self, j: int) -> int:
        if self._idx_map is None or j < 0 or j >= int(self._idx_map.size):
            return int(j)
        return int(self._idx_map[j])

    def _emit_hover(self, j_plot: int | None, *, force_sizes: bool = False) -> None:
        if not force_sizes and j_plot == self._hover_j:
            return
        self._hover_j = j_plot
        phys = self._physical_index(j_plot) if j_plot is not None else None
        self._hover_cb(self._kind, phys)
        drag_p = self._physical_index(self._drag_j) if self._drag_j is not None else None
        self._sizes_cb(self._kind, phys, drag_p)

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: ANN001
        try:
            if obj is not self._vp:
                return False
            et = ev.type()
            if et == QEvent.Type.MouseButtonPress:
                me = ev
                if not isinstance(me, QMouseEvent):
                    return False
                if me.button() != Qt.MouseButton.LeftButton:
                    return False
                mx, my = self._map_event_to_view(me)
                j = self._pick_j(mx, my)
                if j is None:
                    return False
                self._drag_j = j
                xd, yd = self._scatter.getData()
                yd = np.asarray(yd, dtype=np.float64)
                self._y_at_press = float(yd[j]) if j < yd.size else float("nan")
                self._my_press = float(my)
                self._pw.plotItem.vb.setMouseEnabled(x=True, y=False)
                phys = self._physical_index(j)
                self._hover_j = j
                self._hover_cb(self._kind, phys)
                self._sizes_cb(self._kind, phys, phys)
                return True
            if et == QEvent.Type.MouseMove:
                me = ev
                if not isinstance(me, QMouseEvent):
                    return False
                mx, my = self._map_event_to_view(me)
                if self._drag_j is not None and (me.buttons() & Qt.MouseButton.LeftButton):
                    shift = bool(me.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                    sens = 0.18 if shift else 1.0  # Shift = fine tuning
                    y_new = float(np.clip(self._y_at_press + (my - self._my_press) * sens, self._y_lo, self._y_hi))
                    pi = self._physical_index(self._drag_j)
                    self._set_val(pi, y_new)
                    self._refresh()
                    self._debounce.start()
                    self._hover_cb(self._kind, pi)
                    return True
                if not (me.buttons() & Qt.MouseButton.LeftButton):
                    jh = self._pick_j(mx, my)
                    self._emit_hover(jh)
                return False
            if et == QEvent.Type.MouseButtonRelease:
                me = ev
                if not isinstance(me, QMouseEvent):
                    return False
                if self._drag_j is not None:
                    self._drag_j = None
                    self._pw.plotItem.vb.setMouseEnabled(x=True, y=True)
                    self._debounce.stop()
                    self._now()
                    mx, my = self._map_event_to_view(me)
                    jh = self._pick_j(mx, my)
                    self._emit_hover(jh, force_sizes=True)
                    return True
            if et == QEvent.Type.Leave:
                self._emit_hover(None, force_sizes=True)
            return False
        except RuntimeError:
            return False


class SmartInitNKCurveEditorDialog(QDialog):
    """Smart Init window: n(lambda) and log k(lambda), large points, wide lambda band, active hover."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        n_lo: float,
        n_hi: float,
        L_lo: float,
        L_hi: float,
        k_clip_lo: float,
        get_sk: Callable[[], np.ndarray],
        get_n_phys: Callable[[], np.ndarray],
        get_L_nodes: Callable[[], np.ndarray],
        set_n_at: Callable[[int, float], None],
        set_L_at: Callable[[int, float], None],
        request_recalc: Callable[[], None],
        study_lambda_window: Callable[[], tuple[float, float]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("n & k Editor - drag points")
        self.setMinimumSize(540, 300)
        self._n_lo = float(n_lo)
        self._n_hi = float(n_hi)
        self._L_lo = float(L_lo)
        self._L_hi = float(L_hi)
        self._k_lo = max(float(k_clip_lo), 1e-30)
        self._k_hi = float(np.exp(L_hi))
        self._get_sk = get_sk
        self._get_n = get_n_phys
        self._get_L = get_L_nodes
        self._set_n = set_n_at
        self._set_L = set_L_at
        self._recalc = request_recalc
        self._study_lam = study_lambda_window

        self._hover_phys_n: int | None = None
        self._hover_phys_k: int | None = None
        self._drag_phys_n: int | None = None
        self._drag_phys_k: int | None = None

        self._debounce_main = QTimer()
        self._debounce_main.setSingleShot(True)
        self._debounce_main.setInterval(110)
        self._debounce_main.timeout.connect(self._recalc)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scroll_container = QWidget()
        lay = QVBoxLayout(self.scroll_container)
        hint = QLabel(
            "<b>1)</b> Click near a wavelength (wide band) - the closest point in <i>n</i> or <i>k</i> is picked. "
            "<b>2)</b> Drag <b>vertically</b>. <b>Shift</b> = fine adjustment. "
            "<i>k</i>: log scale axis."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 12px;")
        lay.addWidget(hint)

        self._lbl_live = QLabel()
        self._lbl_live.setWordWrap(True)
        self._lbl_live.setMinimumHeight(44)
        self._lbl_live.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-size: 13px; font-weight: 600; padding: 6px; "
            f"background: rgba(128,128,128,0.12); border-radius: 6px;"
        )
        self._lbl_live.setText("Hover or drag a point to see lambda, n and k.")
        lay.addWidget(self._lbl_live)

        split = QSplitter(Qt.Orientation.Vertical)

        self._pw_n = CertusScientificPlot()
        self._pw_n.showGrid(x=True, y=True, alpha=0.25)
        self._pw_n.setLabel("bottom", "lambda (nm)")
        self._pw_n.setLabel("left", "n")
        self._line_n = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.PRIMARY, width=1.8), connect="finite")
        self._pw_n.addItem(self._line_n)
        self._sc_n = pg.ScatterPlotItem(
            size=_SIZE_NORMAL,
            pxMode=True,
            pen=pg.mkPen("#ffffff", width=1.4),
            brush=pg.mkBrush(CertusTheme.PRIMARY),
            name="n nodes",
        )
        self._pw_n.addItem(self._sc_n)
        self._pw_n.setMouseTracking(True)
        attach_excel_clipboard_context_menu(self._pw_n)

        self._pw_k = CertusScientificPlot()
        self._pw_k.showGrid(x=True, y=True, alpha=0.25)
        self._pw_k.setLabel("bottom", "lambda (nm)")
        self._pw_k.setLabel("left", "k (log)")
        self._pw_k.setLogMode(False, True)
        self._line_k = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.PRIMARY, width=1.8), connect="finite")
        self._pw_k.addItem(self._line_k)
        self._sc_k = pg.ScatterPlotItem(
            size=_SIZE_NORMAL,
            pxMode=True,
            pen=pg.mkPen("#ffffff", width=1.4),
            brush=pg.mkBrush(CertusTheme.PRIMARY),
            name="k nodes",
        )
        self._pw_k.addItem(self._sc_k)
        self._pw_k.setMouseTracking(True)
        attach_excel_clipboard_context_menu(self._pw_k)

        split.addWidget(wrap_scientific_plot_with_toolbar(self, self._pw_n))
        split.addWidget(wrap_scientific_plot_with_toolbar(self, self._pw_k))
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, stretch=1)

        row_bulk = QHBoxLayout()
        row_bulk.addWidget(QLabel("All n ->"))
        self._sp_all_n = QDoubleSpinBox()
        self._sp_all_n.setRange(self._n_lo, self._n_hi)
        self._sp_all_n.setDecimals(4)
        self._sp_all_n.setSingleStep(0.005)
        self._sp_all_n.setValue(float(np.clip((self._n_lo + self._n_hi) * 0.5, self._n_lo, self._n_hi)))
        self._sp_all_n.setToolTip("n value applied to all nodes (n_lo / n_hi bounds respected).")
        row_bulk.addWidget(self._sp_all_n)
        btn_all_n = QPushButton("Apply")
        btn_all_n.setToolTip("Set all n - same n on each lambda node.")
        btn_all_n.clicked.connect(self._apply_all_n)
        row_bulk.addWidget(btn_all_n)
        row_bulk.addSpacing(20)
        row_bulk.addWidget(QLabel("All k ->"))
        self._sp_all_k = QDoubleSpinBox()
        self._sp_all_k.setRange(self._k_lo, self._k_hi)
        self._sp_all_k.setDecimals(8)
        sk = float(np.sqrt(max(self._k_lo * self._k_hi, 1e-30)))
        self._sp_all_k.setValue(float(np.clip(sk, self._k_lo, self._k_hi)))
        self._sp_all_k.setSingleStep(max(self._k_lo * 0.05, 1e-8))
        self._sp_all_k.setToolTip("k value (linear) applied to all nodes; graph axis in log.")
        row_bulk.addWidget(self._sp_all_k)
        btn_all_k = QPushButton("Apply")
        btn_all_k.setToolTip("Set all k - same k on each lambda node.")
        btn_all_k.clicked.connect(self._apply_all_k)
        row_bulk.addWidget(btn_all_k)
        row_bulk.addStretch()
        lay.addLayout(row_bulk)

        row = QHBoxLayout()
        btn_r = QPushButton("Recalculate spectrum / RMSE")
        btn_r.setToolTip("Identical to mouse release after movement.")
        btn_r.clicked.connect(self._recalc)
        row.addWidget(btn_r)
        row.addStretch()
        lay.addLayout(row)

        apply_certus_theme(self)

        def _throttle() -> None:
            self._debounce_main.start()

        def _now() -> None:
            self._debounce_main.stop()
            self._recalc()

        self._f_n = _PlotDragFilter(
            self._pw_n,
            self._sc_n,
            self._line_n,
            kind="n",
            set_value_at_physical=self._set_n_phys_wrapper,
            y_clip=(self._n_lo, self._n_hi),
            _request_recalc_throttled=_throttle,
            request_recalc_now=_now,
            refresh_cb=self._refresh_curves_only,
            hover_callback=self._on_hover,
            sizes_callback=self._apply_sizes,
        )
        self._f_k = _PlotDragFilter(
            self._pw_k,
            self._sc_k,
            self._line_k,
            kind="k",
            set_value_at_physical=self._set_k_from_linear,
            y_clip=(self._k_lo, self._k_hi),
            _request_recalc_throttled=_throttle,
            request_recalc_now=_now,
            refresh_cb=self._refresh_curves_only,
            hover_callback=self._on_hover,
            sizes_callback=self._apply_sizes,
        )

        self.scroll_area.setWidget(self.scroll_container)
        dlg_layout = QVBoxLayout(self)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        dlg_layout.addWidget(self.scroll_area)

    def _set_n_phys_wrapper(self, i: int, v: float) -> None:
        self._set_n(int(i), float(v))

    def _set_k_from_linear(self, i: int, k_lin: float) -> None:
        k_lin = float(np.clip(k_lin, self._k_lo, self._k_hi))
        self._set_L(int(i), float(np.log(k_lin)))

    def _apply_all_n(self) -> None:
        v = float(np.clip(self._sp_all_n.value(), self._n_lo, self._n_hi))
        self._sp_all_n.setValue(v)
        n = np.asarray(self._get_n(), dtype=np.float64).ravel()
        for i in range(int(n.size)):
            self._set_n(i, v)
        self._debounce_main.stop()
        self._refresh_curves_only()
        self._recalc()

    def _apply_all_k(self) -> None:
        k_lin = float(np.clip(self._sp_all_k.value(), self._k_lo, self._k_hi))
        self._sp_all_k.setValue(k_lin)
        L = float(np.clip(np.log(k_lin), self._L_lo, self._L_hi))
        n = np.asarray(self._get_n(), dtype=np.float64).ravel()
        for i in range(int(n.size)):
            self._set_L(i, L)
        self._debounce_main.stop()
        self._refresh_curves_only()
        self._recalc()

    def _lam_for_phys(self, i: int) -> float:
        sk = np.asarray(self._get_sk(), dtype=np.float64).ravel()
        if i < 0 or i >= sk.size:
            return float("nan")
        return float(1.0 / max(float(sk[i]), 1e-30))

    def _on_hover(self, kind: str, phys_i: int | None) -> None:
        if kind == "n":
            self._hover_phys_n = phys_i
        else:
            self._hover_phys_k = phys_i
        self._update_live_label()

    def _apply_sizes(self, kind: str, _hover_phys: int | None, drag_phys: int | None) -> None:
        if kind == "n":
            self._drag_phys_n = drag_phys
        else:
            self._drag_phys_k = drag_phys
        self._paint_sizes()

    def _paint_sizes(self) -> None:
        sk, lam, oi = self._lam_and_order()
        k = int(oi.size)
        if k == 0:
            return
        sizes_n = np.full(k, _SIZE_NORMAL, dtype=float)
        sizes_k = np.full(k, _SIZE_NORMAL, dtype=float)
        inv_o = np.empty_like(oi)
        inv_o[oi] = np.arange(k)
        for plot_j in range(k):
            phys = int(oi[plot_j])
            h_n = self._hover_phys_n == phys
            h_k = self._hover_phys_k == phys
            d_n = self._drag_phys_n == phys
            d_k = self._drag_phys_k == phys
            if d_n or d_k:
                sizes_n[plot_j] = _SIZE_DRAG
                sizes_k[plot_j] = _SIZE_DRAG
            elif h_n or h_k:
                sizes_n[plot_j] = max(sizes_n[plot_j], _SIZE_HOVER)
                sizes_k[plot_j] = max(sizes_k[plot_j], _SIZE_HOVER)
        n_phys = np.asarray(self._get_n(), dtype=np.float64).ravel()
        L = np.asarray(self._get_L(), dtype=np.float64).ravel()
        if n_phys.size != k or L.size != k:
            return
        lam_s = lam[oi]
        n_s = n_phys[oi]
        k_s = np.exp(np.clip(L[oi], self._L_lo, self._L_hi))
        self._sc_n.setData(lam_s, n_s, size=sizes_n)
        self._sc_k.setData(lam_s, k_s, size=sizes_k)

    def _update_live_label(self) -> None:
        phys: int | None = None
        if self._drag_phys_n is not None:
            phys = self._drag_phys_n
        elif self._drag_phys_k is not None:
            phys = self._drag_phys_k
        elif self._hover_phys_n is not None:
            phys = self._hover_phys_n
        elif self._hover_phys_k is not None:
            phys = self._hover_phys_k
        if phys is None:
            self._lbl_live.setText("Hover or drag a point - wide lambda band, picks the closest node value.")
            return
        lam_v = self._lam_for_phys(int(phys))
        n_v = float(np.asarray(self._get_n(), dtype=np.float64).ravel()[phys])
        L_v = float(np.asarray(self._get_L(), dtype=np.float64).ravel()[phys])
        k_v = float(np.exp(L_v))
        self._lbl_live.setText(f"lambda ~ {lam_v:.2f} nm   |   n = {n_v:.4f}   |   k = {k_v:.4g}   (ln k = {L_v:.4f})")

    def _lam_and_order(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sk = np.asarray(self._get_sk(), dtype=np.float64).ravel()
        if sk.size == 0:
            return sk, np.array([]), np.array([], dtype=int)
        lam = 1.0 / np.maximum(sk, 1e-30)
        oi = np.argsort(lam)
        return sk, lam, oi

    def _apply_study_window_x(self, pw: CertusScientificPlot) -> None:
        try:
            lo_s, hi_s = self._study_lam()
        except NUMERICAL_FAULT_EXCEPTIONS:
            return
        if hi_s <= lo_s or not np.isfinite(lo_s):
            return
        pad = max((hi_s - lo_s) * 0.03, 1e-6)
        pw.setXRange(float(lo_s - pad), float(hi_s + pad), padding=0)

    def _refresh_curves_only(self) -> None:

        sk, lam, oi = self._lam_and_order()

        if sk.size == 0:
            return

        n_phys = np.asarray(self._get_n(), dtype=np.float64).ravel()

        L = np.asarray(self._get_L(), dtype=np.float64).ravel()

        if n_phys.size != sk.size or L.size != sk.size:
            return

        lam_s = lam[oi]

        n_s = n_phys[oi]

        k_s = np.exp(np.clip(L[oi], self._L_lo, self._L_hi))

        self._f_n._idx_map = oi.copy()

        self._f_k._idx_map = oi.copy()

        self._line_n.setData(lam_s, n_s)

        self._line_k.setData(lam_s, k_s)

        nn = n_s[np.isfinite(n_s)]

        if nn.size:
            pr = max(float(np.max(nn) - np.min(nn)) * 0.1, 8e-4)

            self._pw_n.setYRange(float(np.min(nn) - pr), float(np.max(nn) + pr), padding=0)

        self._pw_k.setYRange(1e-6, 1e-2, padding=0)

        self._apply_study_window_x(self._pw_n)

        self._apply_study_window_x(self._pw_k)

        self._paint_sizes()

        self._update_live_label()

    def refresh_plots(self) -> None:
        """To be called after parent recalculation or grid change."""

        self._refresh_curves_only()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        self._debounce_main.stop()
        self._f_n.detach()
        self._f_k.detach()
        super().closeEvent(event)
