from __future__ import annotations
from certus.ui.certus_strat_common import *

class LiveMonitorWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent=None) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] LiveMonitorWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.setWindowTitle("Phase B: Live Growth Monitor")

        self.resize(1200, 600)

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        # Simple main layout (no more Splitter)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        # -- Growth widget only --

        self.growth_widget = QWidget()

        growth_layout = QVBoxLayout(self.growth_widget)

        self.header_label = QLabel("Waiting for data...")

        self.header_label.setStyleSheet(
            f"background-color: {CertusTheme.PRIMARY}; color: white; padding: 10px; font-weight: bold; font-size: 14px;"
        )

        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        growth_layout.addWidget(self.header_label)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Optical Thickness vs Transmission",
            x_label="Physical Thickness (nm)",
            y_label="Transmission",
        )



        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        self.plot_widget.setYRange(0, 1.0, 0)

        growth_layout.addWidget(self.plot_widget)

        self.layout.addWidget(self.growth_widget)

        # Plot data

        self.layer_lines = []

        self.block_items = []

        self.curve_segments = []

        self.text_labels = []

        self.user_hidden = False

        self.colors = [
            "#d62728",
            "#2ca02c",
            "#1f77b4",
            "#ff7f0e",
            "#9467bd",
            "#17becf",
            "#e377c2",
            "#bcbd22",
            "#8c564b",
        ]

    def update_monitor(self, x, y, bounds, info_text, strategy_blocks) -> None:

        self.header_label.setText(info_text)

        # Clean Plot

        self.plot_widget.plotItem.clear()

        # Re-add layer lines (they were removed by clear())

        while len(self.layer_lines) < len(bounds):
            line = pg.InfiniteLine(
                angle=90,
                pen=pg.mkPen(color="#94a3b8", style=Qt.PenStyle.DashLine, width=1.5),
            )

            line.setZValue(5)

            self.layer_lines.append(line)

        for i, b in enumerate(bounds):
            if self.layer_lines[i] not in self.plot_widget.plotItem.items:
                self.plot_widget.addItem(self.layer_lines[i])

            self.layer_lines[i].setPos(b)

            self.layer_lines[i].show()

        # Reset collections since clear() removed everything

        self.block_items.clear()

        self.curve_segments.clear()

        self.text_labels.clear()

        # Drawing the strategy

        if strategy_blocks:
            x_arr = np.array(x, dtype=np.float64)

            y_arr = np.array(y, dtype=np.float64)

            # Clip x < 0 (digital artifact) to avoid erroneous trace on the left

            valid = x_arr >= 0.0

            x_arr = x_arr[valid]

            y_arr = y_arr[valid]

            for i, block in enumerate(strategy_blocks):
                wl = float(block["wavelength"])

                start_layer = block["start"]

                end_layer = block["end"]

                color = self.colors[i % len(self.colors)]

                if start_layer < len(bounds) and end_layer < len(bounds):
                    x_start = bounds[start_layer]

                    x_end = bounds[end_layer]

                    width = x_end - x_start

                    x_center = (x_start + x_end) / 2.0

                    mask = (x_arr >= x_start - 1e-3) & (x_arr <= x_end + 1e-3)

                    if np.any(mask):
                        segment = self.plot_widget.plot(
                            x_arr[mask],
                            y_arr[mask],
                            pen=pg.mkPen(color=color, width=2.5),
                        )

                        self.curve_segments.append(segment)

                    if i < len(strategy_blocks) - 1:
                        sep_line = pg.InfiniteLine(pos=x_end, angle=90, pen=pg.mkPen(color="#ef4444", width=2))

                        sep_line.setZValue(10)

                        self.plot_widget.addItem(sep_line)

                        self.block_items.append(sep_line)

                    label_text = f"{int(wl)}"

                    text_item = pg.TextItem(text=label_text, color=color, anchor=(0.5, 0.5))

                    font = CertusTheme.get_font()

                    font.setBold(True)

                    rotation = 0

                    if width < 50:
                        font.setPointSize(8)

                        rotation = -90

                    elif width < 150:
                        font.setPointSize(9)

                    else:
                        font.setPointSize(11)

                    text_item.setFont(font)

                    if rotation != 0:
                        text_item.setAngle(rotation)

                    is_staggered_low = i % 2 != 0

                    y_pos = 0.05 if is_staggered_low else 0.15

                    text_item.setPos(x_center, y_pos)

                    self.plot_widget.addItem(text_item)

                    self.text_labels.append(text_item)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] LiveMonitorWindow.closeEvent() user_hidden=True title='%s' id=%s geometry=%s visible=%s",
            self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )

        self.user_hidden = True

        self.hide()

        event.ignore()

