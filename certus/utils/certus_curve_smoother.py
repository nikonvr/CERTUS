#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CERTUS Curve Smoother - Spectral Data Smoothing only
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, __version__, setup_module_logging
from certus.ui.certus_measurement_excel_ui import open_measurement_excel_interactive
from certus.ui.certus_ui import (
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    attach_excel_clipboard_context_menu,
    create_header_logo_widget,
    create_styled_button,
    create_styled_label,
    init_certus_app,
    set_certus_window_icon,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_spectral_preproc import smooth_dataframe_auto, smooth_spectrum_auto

logger = setup_module_logging("CERTUS_CURVE_SMOOTHER")


class DetachedPlotWindow(QMainWindow):
    def __init__(
        self,
        title: str,
        x: np.ndarray,
        y_raw: np.ndarray,
        y_clean: np.ndarray,
        color: str,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"Detail: {title}")
        self.resize(800, 500)
        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND};")
        set_certus_window_icon(self)
        main_w = QWidget()
        self.setCentralWidget(main_w)
        layout = QVBoxLayout(main_w)
        layout.setContentsMargins(10, 10, 10, 10)
        lbl = create_styled_label(f"Isolating: {title}", style="subtitle", color=color)
        layout.addWidget(lbl)
        pw = CertusScientificPlot(title=f"Isolating: {title}")
        pw.addLegend(offset=(10, 10))
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.setLabel("bottom", "Wavelength (nm)")
        pw.setLabel("left", "Amplitude")
        pw.getAxis("bottom").setPen(pg.mkPen(color=CertusTheme.TEXT_SUB))
        pw.getAxis("left").setPen(pg.mkPen(color=CertusTheme.TEXT_SUB))
        pen_clean = pg.mkPen(color=color, width=2.5)
        c_raw = pg.mkColor(color)
        c_raw.setAlpha(120)
        pw.plot(
            x,
            y_raw,
            pen=None,
            symbol="+",
            symbolSize=5,
            symbolPen=pg.mkPen(color=c_raw, width=1),
            name=f"{title} (Raw)",
        )
        pw.plot(x, y_clean, pen=pen_clean, name=f"{title} (Clean)")
        pw.autoRange()
        attach_excel_clipboard_context_menu(pw)
        layout.addWidget(wrap_scientific_plot_with_toolbar(self, pw))


class CurveSmootherGUI(QMainWindow):
    class _UILogHandler(logging.Handler):
        def __init__(self, append_fn):
            super().__init__(level=logging.INFO)
            self._append_fn = append_fn
            self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))

        def emit(self, record: logging.LogRecord) -> None:
            try:
                self._append_fn(self.format(record))
            except NUMERICAL_FAULT_EXCEPTIONS:
                pass

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"CERTUS CURVE SMOOTHER v{__version__}")
        self.resize(1200, 750)
        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND};")
        set_certus_window_icon(self)
        self.df: pd.DataFrame | None = None
        self.file_path = ""
        self.detached_windows: list[QMainWindow] = []
        self.settings = QSettings("CERTUS_SUITE", "CurveSmoother")
        self.last_dir = self.settings.value("last_dir", "")
        self.current_level = "Moyen"
        self._setup_ui()
        self._attach_ui_log_handler()

    def _attach_ui_log_handler(self) -> None:
        if not hasattr(self, "log_panel") or self.log_panel is None:
            return
        underlying_logger = getattr(logger, "logger", logger)
        for h in underlying_logger.handlers:
            if isinstance(h, CurveSmootherGUI._UILogHandler):
                return
        h = CurveSmootherGUI._UILogHandler(self.log_panel.log_text.append)
        h.setLevel(logging.INFO)
        underlying_logger.addHandler(h)
        self.log("UI log bridge attached (INFO+).", "INFO")

    def log(self, message: str, level: str = "INFO") -> None:
        level_u = str(level).upper().strip()
        _map = {
            "DEBUG": logger.debug,
            "INFO": logger.info,
            "WARNING": logger.warning,
            "ERROR": logger.error,
            "SUCCESS": logger.info,
        }
        _map.get(level_u, logger.info)(message)

    def _setup_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        header = create_header_logo_widget(
            "CERTUS CURVE SMOOTHER",
            "Precision Spectral Smoothing",
            logo_width=200,
            module_name="SMOOTHER",
        )
        layout.addWidget(header)
        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_XL,
        )
        tools_frame = QFrame()
        tools_frame.setStyleSheet(
            f"background-color: {CertusTheme.SURFACE}; border-radius: {CertusTheme.RADIUS_LG}px; "
            f"border: 1px solid {CertusTheme.BORDER};"
        )
        tools_layout = QVBoxLayout(tools_frame)
        tools_layout.setContentsMargins(
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
            CertusTheme.SPACING_MD,
        )

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        tools_layout.addLayout(row1)
        tools_layout.addLayout(row2)

        self.btn_load = create_styled_button("Load Data (.xlsx/.xls)", variant="primary")
        self.btn_load.clicked.connect(self.load_file)
        self.combo_mode = QComboBox()
        self.combo_mode.setMinimumWidth(160)
        self.combo_mode.setStyleSheet(
            f"color: {CertusTheme.TEXT_MAIN}; background: {CertusTheme.BACKGROUND}; "
            f"border: 1px solid {CertusTheme.BORDER}; padding: 4px; border-radius: 4px;"
        )
        self.combo_mode.addItems(["Faible", "Moyen", "Fort"])
        self.combo_mode.setCurrentIndex(1)
        self.combo_mode.setEnabled(False)
        self.combo_mode.currentIndexChanged.connect(self.auto_tune)
        self.lbl_computed_params = create_styled_label("   [ Niveau: Moyen ]", color=CertusTheme.TEXT_SUB)
        self.chk_raw = QCheckBox("Show Raw Traces")
        self.chk_raw.setChecked(False)
        self.chk_raw.stateChanged.connect(self.update_plot)
        self.combo_isolate = QComboBox()
        self.combo_isolate.setMinimumWidth(150)
        self.combo_isolate.setStyleSheet(
            f"color: {CertusTheme.TEXT_MAIN}; background: {CertusTheme.BACKGROUND}; "
            f"border: 1px solid {CertusTheme.BORDER}; padding: 4px; border-radius: 4px;"
        )
        self.btn_isolate = create_styled_button("View Isolated", variant="outline")
        self.btn_isolate.clicked.connect(self.open_isolated_view)
        self.btn_isolate.setEnabled(False)
        self.btn_help = create_styled_button("❓ Help", variant="outline")
        self.btn_help.clicked.connect(self.show_help)
        self.btn_save = create_styled_button("Save Clean Data", variant="secondary")
        self.btn_save.clicked.connect(self.save_file)
        self.btn_save.setEnabled(False)

        row1.addWidget(self.btn_load)
        row1.addSpacing(15)
        row1.addWidget(create_styled_label("Filtering Mode:", style="bold", color=CertusTheme.TEXT_SUB))
        row1.addWidget(self.combo_mode)
        row1.addWidget(self.lbl_computed_params)
        row1.addStretch()
        row1.addWidget(self.btn_help)

        row2.addWidget(create_styled_label("Isolate Graph:", style="bold", color=CertusTheme.TEXT_SUB))
        row2.addWidget(self.combo_isolate)
        row2.addWidget(self.btn_isolate)
        row2.addWidget(self.chk_raw)
        row2.addStretch()
        row2.addWidget(self.btn_save)

        c_layout.addWidget(tools_frame)

        self.plot_widget = CertusScientificPlot()
        self.plot_widget.addLegend(offset=(10, 10))
        self.plot_widget.setLabel("bottom", "Wavelength (nm)", **{"color": CertusTheme.TEXT_MAIN, "font-size": "11pt"})
        self.plot_widget.setLabel("left", "Amplitude", **{"color": CertusTheme.TEXT_MAIN, "font-size": "11pt"})
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.getAxis("bottom").setPen(pg.mkPen(color=CertusTheme.BORDER))
        self.plot_widget.getAxis("left").setPen(pg.mkPen(color=CertusTheme.BORDER))
        self.plot_widget.setStyleSheet(
            f"border: 1px solid {CertusTheme.BORDER}; border-radius: {CertusTheme.RADIUS_LG}px;"
        )
        attach_excel_clipboard_context_menu(self.plot_widget)
        c_layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_widget))
        self.log_panel = CertusLogPanel(title="LOGS", visible=True, height=170)
        c_layout.addWidget(self.log_panel)
        layout.addWidget(content)

    def _smooth_y(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        y_smoothed, _info = smooth_spectrum_auto(x, y, level=self.current_level)
        return y_smoothed

    @staticmethod
    def _chart_colors() -> list[str]:
        return [
            CertusTheme.BRAND_DESIGN,
            CertusTheme.SUCCESS,
            CertusTheme.BRAND_INDEX,
            CertusTheme.WARNING,
            "#9b59b6",
            "#34495e",
            CertusTheme.BRAND_METAL,
        ]

    def load_file(self) -> None:
        try:
            result = open_measurement_excel_interactive(
                self,
                start_dir=self.last_dir or "",
                caption="Open Data",
                round_wavelength_decimals=1,
            )
            if result is None:
                return
            df, path, self.last_dir = result
            self.settings.setValue("last_dir", self.last_dir)
            self.df = df
            self.file_path = path
            self.combo_isolate.clear()
            self.combo_isolate.addItems(df.columns[1:].tolist())
            self.btn_save.setEnabled(True)
            self.btn_isolate.setEnabled(True)
            self.combo_mode.setEnabled(True)
            self.auto_tune()
            logger.info("Loaded %s successfully.", path)
        # OSError is not in NUMERICAL_FAULT_EXCEPTIONS, and the commonest failure
        # of all is an OSError: the operator still has the workbook open in Excel,
        # which raises PermissionError. The save path already covers it (see the
        # writer below); without it here, that case escaped as a raw traceback.
        except (*NUMERICAL_FAULT_EXCEPTIONS, OSError) as e:
            logger.error("Failed to load measurement sheet: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to load measurement sheet:\n{e}")

    def show_help(self) -> None:
        help_text = (
            "<h3>CERTUS Curve Smoother</h3>"
            "<p>Load spectra, choose a smoothing level, visualize and save smoothed curves to "
            "<b>clean_measurements</b>.</p>"
        )
        QMessageBox.information(self, "Help", help_text)

    def auto_tune(self) -> None:
        if self.df is None:
            return
        self.current_level = self.combo_mode.currentText()
        self.lbl_computed_params.setText(f"   [ Niveau: {self.current_level} ]")
        self.lbl_computed_params.setStyleSheet(f"color: {CertusTheme.SUCCESS}; font-weight: bold;")
        self.update_plot()

    def update_plot(self) -> None:
        if self.df is None:
            return
        self.plot_widget.clear()
        x = self.df.iloc[:, 0].values
        y_raw = self.df.iloc[:, 1:].values.T
        colors = self._chart_colors()
        show_raw = self.chk_raw.isChecked()
        for i, col in enumerate(self.df.columns[1:]):
            color = colors[i % len(colors)]
            y_clean = self._smooth_y(x, y_raw[i])
            if show_raw:
                c_raw = pg.mkColor(color)
                c_raw.setAlpha(80)
                self.plot_widget.plot(
                    x,
                    y_raw[i],
                    pen=None,
                    symbol="+",
                    symbolSize=3,
                    symbolPen=pg.mkPen(color=c_raw, width=1),
                    name=f"{col} (Raw)",
                )
            self.plot_widget.plot(
                x,
                y_clean,
                pen=pg.mkPen(color=color, width=2),
                name=f"{col} (Clean)" if show_raw else col,
            )

    def open_isolated_view(self) -> None:
        if self.df is None:
            return
        col = self.combo_isolate.currentText()
        if not col:
            return
        x = self.df.iloc[:, 0].values
        y = self.df[col].values
        y_clean = self._smooth_y(x, y)
        idx = self.df.columns.get_loc(col) - 1
        colors = self._chart_colors()
        color = colors[idx % len(colors)]
        win = DetachedPlotWindow(col, x, y, y_clean, color)
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        win.destroyed.connect(
            lambda obj, w=win: self.detached_windows.remove(w) if w in self.detached_windows else None
        )
        self.detached_windows.append(win)
        win.show()

    def save_file(self) -> None:
        if self.df is None or not self.file_path:
            return
        try:
            df_clean, info = smooth_dataframe_auto(self.df, level=self.current_level)
            self.log(
                f"Auto smoothing -> level={info.get('level')} | base={info.get('window_base')} | heavy={info.get('window_heavy')} | period_k={info.get('estimated_period_k'):.6g} | noise={info.get('noise_level'):.6g}",
                "INFO",
            )
            src_p = Path(self.file_path)
            default_target = src_p.with_name(f"{src_p.stem}_clean.xlsx")
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Clean Data",
                str(default_target),
                "Excel Files (*.xlsx);;All Files (*)",
            )
            if not save_path:
                return

            target_p = Path(save_path).resolve()
            is_same_file = (target_p == src_p.resolve())

            if is_same_file:
                ans = QMessageBox.question(
                    self,
                    "Confirm Overwrite",
                    f"You are about to modify the original file:\n{src_p.name}\n\n"
                    "This will add/update the 'clean_measurements' sheet. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    return

            if is_same_file:
                if self.file_path.endswith(".xls"):
                    save_path = str(target_p.with_suffix(".xlsx"))
                    all_sheets = pd.read_excel(self.file_path, sheet_name=None)
                    with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                        for s_name, s_df in all_sheets.items():
                            if s_name.lower() != "clean_measurements":
                                s_df.to_excel(writer, sheet_name=s_name, index=False)
                        df_clean.to_excel(writer, sheet_name="clean_measurements", index=False)
                else:
                    with pd.ExcelWriter(save_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                        df_clean.to_excel(writer, sheet_name="clean_measurements", index=False)
            else:
                with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                    df_clean.to_excel(writer, sheet_name="clean_measurements", index=False)

            QMessageBox.information(
                self,
                "Success",
                f"Saved to clean_measurements sheet in:\n{Path(save_path).name}",
            )
        except (*NUMERICAL_FAULT_EXCEPTIONS, OSError) as e:
            logger.error("Failed to save %s: %s", self.file_path, e)
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")


def main() -> None:
    app = init_certus_app("CERTUS_CURVE_SMOOTHER")
    window = CurveSmootherGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
