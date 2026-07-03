from __future__ import annotations
from certus.ui.certus_strat_common import *

class InteractiveSpectrumWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, data_dict, sigma=None) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] InteractiveSpectrumWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.T_nominal = np.array(data_dict["T_nominal"])

        self.T_simulations = data_dict.get("T_simulations", [])

        title = "Monte Carlo Analysis" + (f" (Input Noise sigma={sigma} nm)" if sigma else "")

        self.setWindowTitle(title)

        self.resize(600, 375)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 10, 15, 10)

        lbl = QLabel("<b>Monte Carlo Reliability Analysis</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(20)

        legend_widget = QWidget()

        legend_layout = QHBoxLayout(legend_widget)

        legend_layout.setContentsMargins(0, 0, 0, 0)

        legend_layout.setSpacing(15)

        def add_legend_item(color, text) -> None:

            lbl_color = QLabel()

            lbl_color.setFixedSize(12, 12)

            lbl_color.setStyleSheet(
                f"background-color: {color}; border-radius: 2px; border: 1px solid {CertusTheme.BORDER};"
            )

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            legend_layout.addWidget(lbl_color)

            legend_layout.addWidget(lbl_txt)

        add_legend_item(CertusTheme.CHART_DANGER, "Nominal Target")

        add_legend_item(CertusTheme.CHART_SECONDARY, "Mean Run")

        add_legend_item("rgba(14, 165, 233, 0.4)", "+/- 1sigma")

        h_layout.addWidget(legend_widget)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Transmission")

        self.plot_widget.addLegend = lambda *args, **kwargs: None



        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._plot_data()

    def _plot_data(self) -> None:

        if self.T_simulations and len(self.T_simulations) > 1:
            arr_sim = np.array(self.T_simulations)

            mean = np.mean(arr_sim, axis=0)

            std = np.std(arr_sim, axis=0)

            self._add_corridor(mean, std, 2.0, (14, 165, 233, 50))

            self._add_corridor(mean, std, 1.0, (14, 165, 233, 100))

            mean_curve = self.plot_widget.plot(
                self.wavelengths,
                mean,
                pen=pg.mkPen(color="#0ea5e9", width=2, style=Qt.PenStyle.DashLine),
            )

            mean_curve.setZValue(10)

        curve_nom = self.plot_widget.plot(self.wavelengths, self.T_nominal, pen=pg.mkPen(color="#d62728", width=3))

        curve_nom.setZValue(20)

        self.plot_widget.add_curve_for_tracking(curve_nom, "Nominal")

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(float(self.wavelengths[0]), float(self.wavelengths[-1]), 0)

            self.plot_widget.setYRange(-0.05, 1.05)

    def _add_corridor(self, mean, std, factor, color_tuple) -> None:

        upper = mean + factor * std

        lower = mean - factor * std

        c_up = pg.PlotCurveItem(x=self.wavelengths, y=upper, pen=None)

        c_down = pg.PlotCurveItem(x=self.wavelengths, y=lower, pen=None)

        self.plot_widget.addItem(c_up)

        self.plot_widget.addItem(c_down)

        fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(color_tuple))

        fill.setZValue(-10)

        self.plot_widget.addItem(fill)

