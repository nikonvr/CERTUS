from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_ui import CertusScientificPlot

class TransmissionVsThicknessWindow(CertusWindowSpyMixin, QMainWindow):
    """Interactive analysis window: T(λ) vs cumulative thickness for a single strategy.

    Lifecycle — same rules as ``StrategySpectralPerformanceWindow``
    ---------------------------------------------------------------
    Stored in ``CertusStratApp.transmission_windows`` to prevent garbage
    collection.  Removing it from that list while the window is open causes
    Qt to destroy the C++ peer and crash on the next repaint.

    Deferred drawing — ``QTimer.singleShot(0, ...)``
    -------------------------------------------------
    The heavy ``_draw_complete_graph`` call is deferred to the next
    event-loop turn via ``QTimer.singleShot(0, …)``.
    BUG HISTORY: calling it directly in ``__init__`` during rapid Phase-B
    window creation (multiple windows opened in quick succession) triggered
    re-entrant ``QPainter`` state, producing ``QPainter::begin`` warnings
    and occasional black plots.
    RULE: keep this deferral.  Do NOT move the draw call back into
    ``__init__`` even if it appears to work during light testing.

    ``db_instance`` resolution — same 3-level fallback as
    ``StrategySpectralPerformanceWindow``
    -------------------------------------------------------
    See :class:`StrategySpectralPerformanceWindow` for the full rationale.
    Always use::

        db_instance = (
            params.get('materials_db_instance')
            or params.get('materials_db')
            or APP_CONTEXT.get('materials_db')
        )
    """

    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] TransmissionVsThicknessWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        strategy = strategy_result["strategy"]

        self.setWindowTitle(f"Interactive Analysis - Strategy #{strategy['strategy_id']}")

        self.setGeometry(150, 150, 1450, 950)

        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] Opening TransmissionVsThicknessWindow for strategy #%s",
            strategy.get("strategy_id", "unknown"),
        )

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 5, 15, 5)

        lbl_title = QLabel(f"<b>STRATEGY #{strategy['strategy_id']}</b>")

        lbl_title.setStyleSheet(f"font-size: 16px; color: {CertusTheme.CHART_PRIMARY};")

        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Transmission vs Cumulative Thickness",
            x_label="Cumulative Thickness (nm)",
            y_label="Transmission",
        )

        self.plot_widget.plotItem.setYRange(-0.05, 1.15)

        self.plot_widget.plotItem.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.plotItem

        self.p2 = pg.ViewBox()

        self.p1.scene().addItem(self.p2)

        self.p1.getAxis("right").linkToView(self.p2)

        self.p2.setXLink(self.p1)

        self.p1.getAxis("right").setLabel("Avg Error (nm)", color=CertusTheme.CHART_PURPLE)

        self.p1.getAxis("right").show()

        self.p1.vb.sigResized.connect(self.update_views)

        # Defer the heavy draw work to the next event-loop turn.
        # This avoids re-entrant paint/painter state during rapid Phase B window creation.
        QTimer.singleShot(0, lambda: self._draw_complete_graph(strategy_result, opti_results, params))

        self.update_views()

    def update_views(self) -> None:

        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)

    def _draw_complete_graph(self, strategy_result, opti_results, params) -> Any:
        try:
            strategy = strategy_result["strategy"]

            blocks = strategy["blocks"]

            p_thick_nominal = opti_results["p_thick_nominal"]

            data = simulate_detailed_growth_for_ui(strategy_result, opti_results, params)

            x_detailed = np.array(data["x"])

            y_detailed = np.array(data["y"])

            boundaries = np.array(data["boundaries"])

            for i in range(len(boundaries) - 1):
                start, end = boundaries[i], boundaries[i + 1]

                center = (start + end) / 2

                is_H = i % 2 == 0

                color = QColor(255, 240, 240) if is_H else QColor(240, 248, 255)

                rect = pg.QtWidgets.QGraphicsRectItem(start, -0.2, end - start, 2.0)

                rect.setBrush(pg.mkBrush(color))

                rect.setPen(pg.mkPen(None))

                rect.setZValue(-20)

                self.p1.addItem(rect)

                line = pg.InfiniteLine(
                    pos=end,
                    angle=90,
                    pen=pg.mkPen(color=(200, 200, 200), style=Qt.PenStyle.DashLine),
                )

                line.setZValue(-15)

                self.p1.addItem(line)

                text_l = pg.TextItem(f"L{i + 1}", color=(80, 80, 80), anchor=(0.5, 0))

                font = CertusTheme.get_font(weight=QFont.Weight.Bold)

                font.setPointSize(10)

                text_l.setFont(font)

                text_l.setPos(center, 1.08)

                text_l.setZValue(10)

                self.p1.addItem(text_l)

            layer_stats = self._extract_layer_errors(strategy_result, p_thick_nominal)

            bar_x, bar_h, bar_w = [], [], []

            max_err = 0.0

            for i, stats in enumerate(layer_stats):
                if stats:
                    start, end = boundaries[i], boundaries[i + 1]

                    bar_x.append((start + end) / 2)

                    bar_h.append(stats["mean"])

                    bar_w.append((end - start) * 0.7)

                    if stats["mean"] > max_err:
                        max_err = stats["mean"]

            if bar_x:
                bars = pg.BarGraphItem(
                    x=bar_x,
                    height=bar_h,
                    width=bar_w,
                    brush=pg.mkBrush(128, 0, 128, 60),
                    pen=pg.mkPen("purple", width=1),
                )

                self.p2.addItem(bars)

                self.p2.setYRange(0, max_err * 3.0 if max_err > 0 else 1.0)

            colors = CertusTheme.CHART_COLORS

            block_start_clues = {b["start"] for b in blocks}

            for idx, block in enumerate(blocks):
                wl = block["wavelength"]

                b_start, b_end = boundaries[block["start"]], boundaries[block["end"]]

                mask = (x_detailed >= b_start - 1e-3) & (x_detailed <= b_end + 1e-3)

                pen_color = colors[idx % len(colors)]

                curve_item = self.p1.plot(
                    x_detailed[mask],
                    y_detailed[mask],
                    pen=pg.mkPen(color=pen_color, width=3),
                    name=f"{wl:.0f}nm",
                )

                if curve_item is not None:
                    self.plot_widget.add_curve_for_tracking(curve_item, f"{wl:.0f}nm")

                for l in range(block["start"], block["end"]):
                    l_start_thick = boundaries[l]

                    l_end_thick = boundaries[l + 1]

                    if l in block_start_clues and l > 0:
                        idx_start = np.searchsorted(x_detailed, l_start_thick)

                        idx_start = min(idx_start, len(y_detailed) - 1)

                        t_start_val = y_detailed[idx_start]

                        txt_start = pg.TextItem(
                            f"{t_start_val:.1%}",
                            color=CertusTheme.CHART_PRIMARY,
                            anchor=(0.5, 1),
                        )

                        txt_start.setPos(l_start_thick, t_start_val + 0.02)

                        font_s = CertusTheme.get_font(9, QFont.Weight.Bold)

                        txt_start.setFont(font_s)

                        txt_start.setZValue(25)

                        self.p1.addItem(txt_start)

                        scatter = pg.ScatterPlotItem(
                            [l_start_thick],
                            [t_start_val],
                            size=8,
                            brush=pg.mkBrush(CertusTheme.CHART_PRIMARY),
                            pen=pg.mkPen(None),
                        )

                        scatter.setZValue(25)

                        self.p1.addItem(scatter)

                    center = (l_start_thick + l_end_thick) / 2

                    txt_wl = pg.TextItem(f"{wl:.0f}", color=pen_color, anchor=(0.5, 0))

                    txt_wl.setPos(center, 1.03)

                    self.p1.addItem(txt_wl)

                    # --- EXTREMA DISTANCES IN HEADER ---

                    ext_dists = strategy.get("extrema_distances", [])

                    if l < len(ext_dists):
                        d = ext_dists[l]

                        p_s = d.get("prev_start", 999.0)

                        n_s = d.get("next_start", 999.0)

                        p_e = d.get("prev_end", 999.0)

                        n_e = d.get("next_end", 999.0)

                        if p_s < n_s:
                            val_s = p_s

                            sign_s = "-"

                        else:
                            val_s = n_s

                            sign_s = "" if n_s > 15.0 else "+"

                        if p_e < n_e:
                            val_e = p_e

                            sign_e = "-"

                        else:
                            val_e = n_e

                            sign_e = "" if n_e > 15.0 else "+"

                        def _fmt_ot(v, sign) -> Any:
                            return "NC" if v > 15.0 else f"{sign}{v:.1f}"

                        label_start = _fmt_ot(val_s, sign_s)

                        label_end = _fmt_ot(val_e, sign_e)

                        # Color: red if critical (<15), grey if NC

                        color_s = (200, 0, 0) if val_s <= 15.0 else (140, 140, 140)

                        color_e = (200, 0, 0) if val_e <= 15.0 else (140, 140, 140)

                        txt_ext = pg.TextItem(
                            f"{label_start}|{label_end}",
                            color=(max(color_s[0], color_e[0]), min(color_s[1], color_e[1]), min(color_s[2], color_e[2])),
                            anchor=(0.5, 0),
                        )

                        font_ext = CertusTheme.get_font(7, QFont.Weight.Normal)

                        txt_ext.setFont(font_ext)

                        txt_ext.setPos(center, 0.97)

                        txt_ext.setZValue(12)

                        self.p1.addItem(txt_ext)

                    idx_end = np.searchsorted(x_detailed, l_end_thick)

                    idx_end = min(idx_end, len(y_detailed) - 1)

                    t_val = y_detailed[idx_end]

                    arrow = pg.ArrowItem(
                        pos=(l_end_thick, t_val),
                        angle=180,
                        tipAngle=30,
                        baseAngle=20,
                        headLen=15,
                        pen={"color": "k", "width": 1},
                        brush="k",
                    )

                    arrow.setZValue(20)

                    self.p1.addItem(arrow)

                    txt_pct = pg.TextItem(f"{t_val:.1%}", color="black", anchor=(0, 0.5))

                    txt_pct.setPos(l_end_thick + 2, t_val)

                    txt_pct.fill = pg.mkBrush(255, 255, 255, 150)

                    txt_pct.setZValue(20)

                    self.p1.addItem(txt_pct)

            # Activation de l'échelle automatique sur tous les axes à la fin du tracé
            try:
                self.p1.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)
                self.p1.autoRange()
                if hasattr(self, "p2") and self.p2:
                    self.p2.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
                    self.p2.autoRange()
            except Exception as auto_err:
                logging.getLogger("CERTUS").debug("autoRange skipped: %s", auto_err)
        except Exception as e:
            logging.getLogger("CERTUS").error(f"[STRAT-UI] Error drawing complete graph: {e}", exc_info=True)

    def _extract_layer_errors(self, strategy_result, p_thick_nominal) -> Any:

        num_layers = len(p_thick_nominal)

        layer_stats = [None] * num_layers

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            target_idx = 1 if len(results_per_noise) > 1 else 0

            if results_per_noise:
                target_result = results_per_noise[target_idx]

                thicknesses_all = target_result.get("thicknesses_all", [])

                if thicknesses_all:
                    for i_layer in range(num_layers):
                        errors = []

                        for run_stack in thicknesses_all:
                            if len(run_stack) > i_layer:
                                err = abs(run_stack[i_layer] - p_thick_nominal[i_layer])

                                errors.append(err)

                        if errors:
                            layer_stats[i_layer] = {
                                "mean": float(np.mean(errors)),
                                "std": float(np.std(errors)),
                            }

        except (ValueError, TypeError, IndexError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        return layer_stats

