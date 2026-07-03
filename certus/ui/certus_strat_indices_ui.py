from __future__ import annotations
from certus.ui.certus_strat_common import *

class InteractiveIndicesWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, data_dict) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] InteractiveIndicesWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.nH = np.real(np.array(data_dict["nH"]))

        self.nL = np.real(np.array(data_dict["nL"]))

        self.setWindowTitle("Material Dispersion Check")

        self.resize(600, 400)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setStyleSheet(f"background: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(10, 5, 10, 5)

        lbl = QLabel("<b>Refractive Indices</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 13px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(15)

        def add_legend(color, text) -> None:

            l = QLabel()

            l.setFixedSize(10, 10)

            l.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

            t = QLabel(text)

            t.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            h_layout.addWidget(l)

            h_layout.addWidget(t)

            h_layout.addSpacing(10)

        add_legend(CertusTheme.PRIMARY, "High Index (H)")

        add_legend(CertusTheme.SECONDARY, "Low Index (L)")

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Refractive Index")


        self.plot_widget.addLegend = lambda *args, **kwargs: None

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.curve_H = self.plot_widget.plot(
            self.wavelengths,
            self.nH,
            pen=pg.mkPen(color=CertusTheme.PRIMARY, width=3),
            name="H",
        )

        self.curve_L = self.plot_widget.plot(
            self.wavelengths,
            self.nL,
            pen=pg.mkPen(color=CertusTheme.SECONDARY, width=3),
            name="L",
        )

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(self.wavelengths[0], self.wavelengths[-1], 0)

            all_n = np.concatenate([self.nH, self.nL])

            y_min, y_max = np.min(all_n), np.max(all_n)

            margin = (y_max - y_min) * 0.1

            self.plot_widget.setYRange(y_min - margin, y_max + margin)

        self.plot_widget.info_label.setVisible(False)

        self.plot_widget.vLine.setVisible(False)

        self.plot_widget.hLine.setVisible(False)

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen("#333", width=1, style=Qt.PenStyle.DashLine),
        )

        self.plot_widget.addItem(self.vLine)

        self.cursor_text = pg.TextItem(anchor=(0, 1), color=CertusTheme.TEXT_MAIN)

        font = CertusTheme.get_font(10)

        font.setBold(True)

        self.cursor_text.setFont(font)

        self.cursor_text.setZValue(100)

        self.plot_widget.addItem(self.cursor_text)

        self.proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.update_cursor,
        )

    def update_cursor(self, evt) -> None:

        pos = evt[0]

        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)

        x_mouse = mouse_point.x()

        if x_mouse < self.wavelengths[0] or x_mouse > self.wavelengths[-1]:
            return

        idx = np.searchsorted(self.wavelengths, x_mouse)

        if idx >= len(self.wavelengths):
            idx = len(self.wavelengths) - 1

        wl_val = self.wavelengths[idx]

        val_H = self.nH[idx]

        val_L = self.nL[idx]

        self.vLine.setPos(wl_val)

        content = f"lambda: {int(wl_val)} nm\nnH: {val_H:.3f}\nnL: {val_L:.3f}"

        self.cursor_text.setText(content)

        y_pos = mouse_point.y()

        if x_mouse > (self.wavelengths[-1] - self.wavelengths[0]) * 0.8 + self.wavelengths[0]:
            self.cursor_text.setAnchor((1, 1))

        else:
            self.cursor_text.setAnchor((0, 1))

        self.cursor_text.setPos(x_mouse, y_pos)

