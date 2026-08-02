from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_ui import CertusScientificPlot

class StrategySpectralPerformanceWindow(CertusWindowSpyMixin, QMainWindow):
    """Detail window showing spectral transmission curves for a single strategy.

    Lifecycle
    ---------
    Instantiated on demand from :meth:`CertusStratApp.on_strategy_visualization_requested`
    when the user double-clicks a row in ``StrategiesTableWindow``.  The window
    is stored in ``self.transmission_windows`` to prevent garbage collection
    (if removed from that list the C++ peer is destroyed and Qt will crash on
    the next paint event).

    Critical invariant — ``db_instance`` resolution
    ------------------------------------------------
    ``params`` is a dict assembled by the worker **before** the thread starts;
    it may or may not carry ``'materials_db_instance'`` or ``'materials_db'``
    keys depending on which code path populated it.
    **Always** resolve the material database with the three-level fallback::

        db_instance = (
            params.get('materials_db_instance')
            or params.get('materials_db')
            or APP_CONTEXT.get('materials_db')
        )

    Omitting any level caused flat transmission curves in
    :meth:`_calculate_and_plot` (bug fixed 2026-05-27).
    """

    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] StrategySpectralPerformanceWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        strategy_id = strategy_result["strategy"]["strategy_id"]

        self.setWindowTitle(f"Spectral Performance - Strategy #{strategy_id}")

        self.resize(800, 600)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 8, 15, 8)

        lbl = QLabel(f"<b>Spectral Robustness Analysis</b> (Strategy #{strategy_id})")

        lbl.setStyleSheet(f"color: {CertusTheme.CHART_PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Final Spectral Distribution",
            x_label="Wavelength (nm)",
            y_label="Transmission",
        )


        self.plot_widget.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._calculate_and_plot(strategy_result, opti_results, params)

    def _calculate_and_plot(self, strategy_result, opti_results, params) -> None:
        try:
            wl_min = float(params.get("wavelength_min", 380.0))
            wl_max = float(params.get("wavelength_max", 1000.0))

            data = simulate_spectral_distribution_for_ui(strategy_result, opti_results, params)
            if not data:
                return

            wls = np.array(data["wls"])
            T_nom = np.array(data["T_nom"])
            mean = np.array(data["mean"])
            p5 = np.array(data["p5"])
            p95 = np.array(data["p95"])

            c_up = pg.PlotCurveItem(x=wls, y=p95, pen=None)
            c_down = pg.PlotCurveItem(x=wls, y=p5, pen=None)
            fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(14, 165, 233, 50))
            fill.setZValue(-10)
            self.plot_widget.addItem(fill)

            self.plot_widget.plot(
                wls,
                mean,
                pen=pg.mkPen(
                    color=CertusTheme.CHART_SECONDARY,
                    width=2,
                    style=Qt.PenStyle.DashLine,
                ),
                name="Mean MC",
            )

            self.plot_widget.plot(
                wls,
                T_nom,
                pen=pg.mkPen(color=CertusTheme.CHART_DANGER, width=2.5),
                name="Nominal Target",
            )

            self.plot_widget.setXRange(wl_min, wl_max)
            self.plot_widget.setYRange(0, 1.0)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Error plotting spectral performance: {e}")

