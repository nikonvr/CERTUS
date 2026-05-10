import functools
import logging
from pathlib import Path
from typing import Any, Optional, Callable
import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.exporters
from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QMessageBox, QToolBar, QVBoxLayout, QFileDialog, QMainWindow, QToolButton
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt

# Late imports from certus_export in methods to avoid circular dependency

# Avoid circular dependencies by lazy loading if needed, but since CertusTheme is defined early in certus_ui, it should be safe.


def get_plot_style_config() -> dict:
    from certus_ui import CertusTheme

    """Return current theme-based config for plot styling (background, text color, grid)."""
    return {
        "background": getattr(CertusTheme, "SURFACE", "#ffffff"),
        "text_color": getattr(CertusTheme, "TEXT_MAIN", "#212529"),
        "grid_alpha": 0.15,
        "axis_width": 1,
    }


def apply_certus_plot_style(plot) -> None:

    """
    Apply CERTUS theme to a single pyqtgraph PlotWidget or similar.
    Use for new plots and when theme changes.
    """
    cfg = get_plot_style_config()
    plot.setBackground(cfg["background"])
    text_color = cfg["text_color"]
    axis_pen = pg.mkPen(color=text_color, width=cfg.get("axis_width", 1))

    for axis_name in ["bottom", "left", "right", "top"]:
        if hasattr(plot, "getAxis"):
            axis = plot.getAxis(axis_name)
            if axis:
                axis.setPen(axis_pen)
                axis.setTextPen(text_color)

    plot_item = getattr(plot, "getPlotItem", lambda: None)()
    if plot_item and getattr(plot_item, "titleLabel", None):
        tl = plot_item.titleLabel
        if hasattr(tl, "setColor"):
            tl.setColor(text_color)


def apply_theme_to_plots(plots: list) -> None:
    """Apply current CertusTheme colors to pyqtgraph plots."""
    for plot in plots:
        if plot is not None:
            apply_certus_plot_style(plot)


def sanitize_xy_for_plot(x, y) -> tuple[np.ndarray, np.ndarray]:
    """
    Keep only finite (x, y) pairs.
    Avoids NaN/Inf in PyQtGraph (autoRange, Python 3.14 + round(nan), etc.).
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    y = np.asarray(y, dtype=float).reshape(-1)
    n = min(int(x.size), int(y.size))
    if n == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    x = x[:n].copy()
    y = y[:n].copy()
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def plot_widget_plot_finite(widget, x, y, **kwargs):
    """Equivalent to PlotWidget.plot after cleaning; returns None if no valid points."""
    xf, yf = sanitize_xy_for_plot(x, y)
    if xf.size == 0:
        return None
    return widget.plot(xf, yf, **kwargs)


class CertusScientificPlot(pg.PlotWidget):
    """CERTUS styled PyQtGraph plot widget with smart cursor tracking.

    Features:
    - Automatic CERTUS theme styling (colors, fonts, grid)
    - Interactive cursor with crosshair and value display
    - Curve tracking with tooltips
    - Detach to new window (Ctrl+D)
    - Right-click context menu for export
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "",
        y_label: str = "",
        x_label: str = "",
        axisItems: dict | None = None,
        **kwargs,
    ):
        from certus_ui import (
            CertusTheme,
        )

        super().__init__(parent, axisItems=axisItems, **kwargs)
        self._certus_init_title: str = str(title or "")
        if "clear" in self.__dict__:
            del self.clear

        apply_certus_plot_style(self)
        self.showGrid(x=True, y=True, alpha=get_plot_style_config().get("grid_alpha", 0.15))
        self.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="12pt")
        self.plotItem.setLabels(left=y_label, bottom=x_label)

        self._install_crosshair_overlay()
        self._apply_sensible_empty_range()

        self._certus_crosshair_label_fn: Optional[Callable[[float, Any, float], str]] = None
        self._certus_crosshair_vertical_only: bool = False
        self._certus_mouse_moved_hook: Optional[Callable[[Any, Any, float, float, Any], None]] = None

        self.proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_move)
        self._curves: dict[str, pg.PlotDataItem] = {}

        self._detach_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self._detach_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._detach_shortcut.activated.connect(self._on_detach_shortcut)

        self._copy_excel_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self._copy_excel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._copy_excel_shortcut.activated.connect(self._on_copy_excel_shortcut)

        self._copy_pub_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self._copy_pub_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._copy_pub_shortcut.activated.connect(self._on_copy_publication_shortcut)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_export_menu)

    def _on_copy_excel_shortcut(self) -> None:
        self._copy_excel_tsv(show_message=True)

    def _on_copy_publication_shortcut(self) -> None:
        self._copy_publication_tsv(show_message=True)

    def _show_context_export_menu(self, pos) -> None:
        from certus_ui import (
            CERTUS_UI_STRINGS,
        )

        menu = QMenu(self)
        act_copy = menu.addAction(CERTUS_UI_STRINGS["copy_excel_tsv"])
        act_copy.setToolTip("Ctrl+Shift+C - TSV for Excel")
        act_copy_pub = menu.addAction(CERTUS_UI_STRINGS["copy_pub_tsv"])
        act_copy_pub.setToolTip("Ctrl+Shift+P - fixed-point TSV for publication tables")
        menu.addSeparator()
        act_csv = menu.addAction("Export CSV")
        act_tsv = menu.addAction("Export TSV")
        act_tsv_pub = menu.addAction("Export TSV (Publication)")

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_copy:
            self._on_copy_excel_shortcut()
        elif chosen == act_copy_pub:
            self._on_copy_publication_shortcut()
        elif chosen == act_csv:
            self._export_csv()
        elif chosen == act_tsv:
            self._export_tsv()
        elif chosen == act_tsv_pub:
            self._export_tsv_publication()

    def _copy_excel_tsv(self, show_message: bool = True) -> None:
        from certus_ui import (
            CERTUS_UI_STRINGS,
        )

        from certus_export import copy_plot_to_clipboard_excel

        ok = copy_plot_to_clipboard_excel(self)
        if not show_message:
            return
        parent = self.window() or None
        if ok:
            QMessageBox.information(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_excel_ok"],
            )
        else:
            QMessageBox.warning(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_excel_failed"],
            )

    @staticmethod
    def _to_publication_tsv(df: pd.DataFrame, *, x_decimals: int = 6, y_decimals: int = 8) -> str:
        """Stable fixed-point TSV for publication workflows."""
        if df is None or df.empty:
            return ""
        cols = list(df.columns)
        parts: list[str] = ["\t".join(str(c) for c in cols)]
        arr = df.to_numpy()
        for row in arr:
            out_row: list[str] = []
            for i, v in enumerate(row):
                c = str(cols[i])
                if pd.isna(v):
                    out_row.append("")
                    continue
                if isinstance(v, (float, np.floating, int, np.integer)):
                    fv = float(v)
                    if c.endswith("_x"):
                        out_row.append(f"{fv:.{x_decimals}f}")
                    elif c.endswith("_y"):
                        out_row.append(f"{fv:.{y_decimals}f}")
                    else:
                        out_row.append(f"{fv:.{y_decimals}f}")
                else:
                    out_row.append(str(v))
            parts.append("\t".join(out_row))
        return "\n".join(parts) + "\n"

    def _copy_publication_tsv(self, show_message: bool = True) -> None:
        from certus_ui import (
            CERTUS_UI_STRINGS,
        )

        from certus_export import plot_dataframe_from_widget

        df = plot_dataframe_from_widget(self)
        ok = bool(df is not None and not df.empty)
        if ok:
            tsv = self._to_publication_tsv(df)
            QApplication.clipboard().setText(tsv)
        if not show_message:
            return
        parent = self.window() or None
        if ok:
            QMessageBox.information(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_pub_ok"],
            )
        else:
            QMessageBox.warning(
                parent,
                CERTUS_UI_STRINGS["export"],
                CERTUS_UI_STRINGS["copy_excel_failed"],
            )

    def _on_detach_shortcut(self) -> None:
        self._trigger_detach_host(self.window())

    def _trigger_detach_host(self, context_widget: QWidget | None) -> None:
        """Goes up to CertusBaseApp.open_detached_certus_plot."""
        p: QWidget | None = context_widget if context_widget is not None else self.window()
        for _ in range(40):
            if p is None:
                break
            if hasattr(p, "open_detached_certus_plot"):
                plot_title = str(getattr(self, "_certus_init_title", "") or "").strip()
                if not plot_title:
                    try:
                        tl_cb = self.plotItem.titleLabel
                        if tl_cb is not None:
                            plot_title = str(getattr(tl_cb, "text", "") or "").strip()
                    except (
                        ValueError,
                        TypeError,
                        RuntimeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        FileNotFoundError,
                    ):
                        plot_title = ""
                p.open_detached_certus_plot(self, title=(plot_title or None))
                return
            p = p.parentWidget()

    def _install_crosshair_overlay(self) -> None:
        from certus_ui import (
            CertusTheme,
        )

        self.vLine = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen("#e74c3c", width=1, style=Qt.PenStyle.DashLine)
        )
        self.hLine = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen("#e74c3c", width=1, style=Qt.PenStyle.DashLine)
        )
        self.addItem(self.vLine, ignoreBounds=True)
        self.addItem(self.hLine, ignoreBounds=True)
        self.info_label = pg.TextItem(anchor=(0, 1), color=CertusTheme.PRIMARY)
        self.addItem(self.info_label, ignoreBounds=True)

    def _apply_sensible_empty_range(self, padding: float = 0.05) -> None:
        self.plotItem.setXRange(0.0, 1.0, padding=padding)
        try:
            y_log = self.plotItem.ctrl.logYCheck.isChecked()
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            y_log = False
        if y_log:
            self.plotItem.setYRange(1e-6, 1e-2, padding=padding)
        else:
            self.plotItem.setYRange(0.0, 1.0, padding=padding)

    @staticmethod
    def _interp_y_sorted_curve(xd: np.ndarray, yd: np.ndarray, x: float) -> float | None:
        xd = np.asarray(xd, dtype=np.float64).ravel()
        yd = np.asarray(yd, dtype=np.float64).ravel()
        m = np.isfinite(xd) & np.isfinite(yd)
        if int(np.count_nonzero(m)) < 2:
            return None
        xs = xd[m]
        ys = yd[m]
        order = np.argsort(xs, kind="mergesort")
        xs = xs[order]
        ys = ys[order]
        xv = float(x)
        if xv < float(xs[0]) or xv > float(xs[-1]):
            return None
        return float(np.interp(xv, xs, ys))

    def _pen_width_plotdata(self, it: pg.PlotDataItem) -> int:
        try:
            p = it.opts.get("pen")
            if p is None:
                return 1
            if isinstance(p, dict):
                return int(p.get("width", 1) or 1)
            w = getattr(p, "width", None)
            if callable(w):
                return int(w())
            return int(w or 1)
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            return 1

    def _y_snap_crosshair(self, x: float, y_mouse: float) -> float | None:
        def best_y(pred) -> float | None:
            best_d = float("inf")
            best_yv: float | None = None
            for it in self.plotItem.listDataItems():
                if not pred(it):
                    continue
                xd, yd = it.getData()
                if xd is None or yd is None:
                    continue
                yi = self._interp_y_sorted_curve(xd, yd, x)
                if yi is None or not np.isfinite(yi):
                    continue
                d = abs(float(yi) - float(y_mouse))
                if d < best_d:
                    best_d = d
                    best_yv = float(yi)
            return best_yv

        yp = best_y(lambda it: bool(getattr(it, "_certus_crosshair_primary", False)))
        if yp is not None:
            return yp
        yp = best_y(lambda it: self._pen_width_plotdata(it) >= 2)
        if yp is not None:
            return yp
        return best_y(lambda it: True)

    def _on_mouse_move(self, evt):
        pos = evt[0]
        if self.plotItem.sceneBoundingRect().contains(pos):
            mouse_point = self.plotItem.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            if not (np.isfinite(x) and np.isfinite(y)):
                return
            self.vLine.setPos(x)
            y_show = self._y_snap_crosshair(x, y)
            y_cursor = y_show if y_show is not None else y
            vertical_only = bool(getattr(self, "_certus_crosshair_vertical_only", False))
            if vertical_only:
                self.hLine.setVisible(False)
                label_y = float(y)
            else:
                self.hLine.setVisible(True)
                self.hLine.setPos(y_cursor)
                label_y = float(y_cursor)

            fn = getattr(self, "_certus_crosshair_label_fn", None)
            if callable(fn):
                if vertical_only:
                    try:
                        xr = self.plotItem.vb.viewRange()[0]
                        x_lo, x_hi = float(xr[0]), float(xr[1])
                        span = x_hi - x_lo
                        if span > 0 and x > x_lo + 0.78 * span:
                            self.info_label.setAnchor((1, 1))
                        else:
                            self.info_label.setAnchor((0, 1))
                    except (
                        ValueError,
                        TypeError,
                        RuntimeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        FileNotFoundError,
                    ):
                        self.info_label.setAnchor((0, 1))
                self.info_label.setText(fn(x, y_show, y))
            else:
                if y_show is not None:
                    self.info_label.setText(f"x = {x:.2f}, y = {y_show:.4f}")
                else:
                    self.info_label.setText(f"x = {x:.2f}, y = {y:.4f} (cursor)")
            self.info_label.setPos(x, label_y)
            hook = getattr(self, "_certus_mouse_moved_hook", None)
            if callable(hook):
                hook(self, pos, x, y, y_show)

    def set_labels(self, x_label: str, y_label: str, title: str = ""):
        self.plotItem.setLabels(bottom=x_label, left=y_label)
        if title:
            self._certus_init_title = str(title)
            self.plotItem.setTitle(title)

    def add_curve(
        self,
        x: np.ndarray,
        y: np.ndarray,
        name: str,
        color: str = "#1e3a8a",
        width: int = 2,
        style: Qt.PenStyle = Qt.PenStyle.SolidLine,
    ) -> pg.PlotDataItem:
        try:
            x, y = sanitize_xy_for_plot(x, y)
            if x.size == 0 or y.size == 0:
                logging.warning(f"add_curve: no finite points for {name}")
                return None
            pen = pg.mkPen(color=color, width=width, style=style)
            curve = self.plot(x, y, pen=pen, name=name)
            self._curves[name] = curve
            return curve
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            logging.error(f"add_curve failed for {name}: {e} (x type={type(x)}, y type={type(y)})")
            raise

    def update_curve(self, name: str, x: np.ndarray, y: np.ndarray):
        if name in self._curves:
            xf, yf = sanitize_xy_for_plot(x, y)
            self._curves[name].setData(xf, yf)

    def remove_curve(self, name: str):
        if name in self._curves:
            try:
                self.removeItem(self._curves[name])
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
                pass
            del self._curves[name]

    def clear_curves(self):
        for name in list(self._curves.keys()):
            self.remove_curve(name)

    def clear(self):
        self.clear_curves()
        self.plotItem.clear()
        self._certus_mouse_moved_hook = None
        self._install_crosshair_overlay()
        self._apply_sensible_empty_range()

    def clear_tracking(self):
        pass

    def add_tracked_curve(self, curve, name: str, unit: str = ""):
        pass

    def get_toolbar(self, parent_widget: QWidget) -> QToolBar:
        from certus_ui import CERTUS_UI_STRINGS

        toolbar = QToolBar(parent_widget)
        toolbar.setStyleSheet(
            "QToolBar { background: #f8f9fa; border-bottom: 1px solid #ddd; spacing: 5px; } QToolButton { padding: 4px; border-radius: 3px; } QToolButton:hover { background-color: #e2e6ea; }"
        )
        act_reset = toolbar.addAction(" Reset")
        act_reset.triggered.connect(self.plotItem.autoRange)
        act_detach = toolbar.addAction(" Detach")
        act_detach.setToolTip("Large resizable window (Ctrl+Shift+D)")
        act_detach.triggered.connect(functools.partial(self._trigger_detach_host, parent_widget))
        toolbar.addSeparator()

        act_copy_data = toolbar.addAction(" Copy data")
        act_copy_data.setToolTip("Copy all displayed plot data to clipboard (Excel TSV)")
        act_copy_data.triggered.connect(self._on_copy_excel_shortcut)

        act_copy_pub = toolbar.addAction(" Pub copy")
        act_copy_pub.setToolTip("Copy publication-ready TSV (fixed decimals)")
        act_copy_pub.triggered.connect(self._on_copy_publication_shortcut)

        act_csv_quick = toolbar.addAction(" CSV")
        act_csv_quick.setToolTip("Export all displayed plot data to CSV")
        act_csv_quick.triggered.connect(self._export_csv)

        toolbar.addSeparator()

        export_btn = QToolButton()
        export_btn.setText(" Export")
        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(export_btn)
        act_png = menu.addAction(" PNG")
        act_png.triggered.connect(self._export_png)
        act_svg = menu.addAction(" SVG")
        act_svg.triggered.connect(self._export_svg)
        act_csv = menu.addAction(" CSV")
        act_csv.triggered.connect(self._export_csv)
        act_tsv = menu.addAction(" TSV")
        act_tsv.triggered.connect(self._export_tsv)
        act_tsv_pub = menu.addAction(" TSV (Publication)")
        act_tsv_pub.triggered.connect(self._export_tsv_publication)

        act_copy = menu.addAction(CERTUS_UI_STRINGS["copy_excel_tsv"])
        act_copy.setToolTip("Ctrl+Shift+C - TSV pour Excel")
        act_copy.triggered.connect(self._on_copy_excel_shortcut)

        act_copy_pub = menu.addAction(CERTUS_UI_STRINGS["copy_pub_tsv"])
        act_copy_pub.setToolTip("Ctrl+Shift+P - fixed-point TSV for publication tables")
        act_copy_pub.triggered.connect(self._on_copy_publication_shortcut)

        export_btn.setMenu(menu)
        toolbar.addWidget(export_btn)
        return toolbar

    def _export_png(self):
        from certus_ui import (
            CERTUS_UI_STRINGS,
            get_certus_last_dir,
            set_certus_last_dir,
            get_export_settings,
        )

        filename, _ = QFileDialog.getSaveFileName(
            None, "Export PNG", str(Path(get_certus_last_dir() or ".") / "plot.png"), "PNG (*.png)"
        )
        if filename:
            set_certus_last_dir(filename)
            try:
                exporter = pg.exporters.ImageExporter(self.plotItem)
                opts = get_export_settings()
                exporter.parameters()["width"] = opts.get("width", 1920)
                if opts.get("height"):
                    exporter.parameters()["height"] = opts["height"]
                exporter.export(filename)
                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
                logging.error(f"PNG export failed:{e}")
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"PNG : {e}",
                )

    def _export_svg(self):
        from certus_ui import (
            CERTUS_UI_STRINGS,
            get_certus_last_dir,
            set_certus_last_dir,
        )

        filename, _ = QFileDialog.getSaveFileName(
            None, "SVG export", str(Path(get_certus_last_dir() or ".") / "plot.svg"), "SVG (*.svg)"
        )
        if filename:
            set_certus_last_dir(filename)
            try:
                exporter = pg.exporters.SVGExporter(self.plotItem)
                exporter.export(filename)
                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
                logging.error(f"SVG export failed:{e}")
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"SVG : {e}",
                )

    def _export_csv(self):
        from certus_ui import (
            CERTUS_UI_STRINGS,
            get_certus_last_dir,
            set_certus_last_dir,
        )

        filename, _ = QFileDialog.getSaveFileName(
            None, "CSV export", str(Path(get_certus_last_dir() or ".") / "plot_data.csv"), "CSV (*.csv)"
        )
        if not filename:
            return
        set_certus_last_dir(filename)
        try:
            from certus_export import plot_dataframe_from_widget

            df = plot_dataframe_from_widget(self)
            if df is None or df.empty:
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    CERTUS_UI_STRINGS["no_data"],
                )
                return
            import datetime

            meta = f"# CERTUS export {datetime.datetime.now().isoformat(timespec='seconds')}\n"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(meta)
                df.to_csv(f, index=False)
            QMessageBox.information(
                self.window() or None,
                CERTUS_UI_STRINGS["export"],
                f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            import traceback

            logging.error(f"CSV export failed:{e}\n{traceback.format_exc()}")
            QMessageBox.warning(
                self.window() or None,
                CERTUS_UI_STRINGS["export_failed"],
                f"CSV : {e}",
            )

    def _export_tsv(self):
        from certus_ui import (
            CERTUS_UI_STRINGS,
            get_certus_last_dir,
            set_certus_last_dir,
        )

        filename, _ = QFileDialog.getSaveFileName(
            None, "TSV export", str(Path(get_certus_last_dir() or ".") / "plot_data.tsv"), "TSV (*.tsv)"
        )
        if not filename:
            return
        set_certus_last_dir(filename)
        try:
            from certus_export import plot_dataframe_from_widget

            df = plot_dataframe_from_widget(self)
            if df is None or df.empty:
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    CERTUS_UI_STRINGS["no_data"],
                )
                return
            import datetime

            meta = f"# CERTUS export {datetime.datetime.now().isoformat(timespec='seconds')}\n"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(meta)
                df.to_csv(f, index=False, sep="\t", lineterminator="\n")
            QMessageBox.information(
                self.window() or None,
                CERTUS_UI_STRINGS["export"],
                f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            import traceback

            logging.error(f"TSV export failed:{e}\n{traceback.format_exc()}")
            QMessageBox.warning(
                self.window() or None,
                CERTUS_UI_STRINGS["export_failed"],
                f"TSV : {e}",
            )

    def _export_tsv_publication(self):
        from certus_ui import (
            CERTUS_UI_STRINGS,
            get_certus_last_dir,
            set_certus_last_dir,
        )

        filename, _ = QFileDialog.getSaveFileName(
            None,
            "TSV export (Publication)",
            str(Path(get_certus_last_dir() or ".") / "plot_data_publication.tsv"),
            "TSV (*.tsv)",
        )
        if not filename:
            return
        set_certus_last_dir(filename)
        try:
            from certus_export import plot_dataframe_from_widget

            df = plot_dataframe_from_widget(self)
            if df is None or df.empty:
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    CERTUS_UI_STRINGS["no_data"],
                )
                return
            import datetime

            meta = f"# CERTUS publication export {datetime.datetime.now().isoformat(timespec='seconds')}\n"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(meta)
                f.write(self._to_publication_tsv(df))
            QMessageBox.information(
                self.window() or None,
                CERTUS_UI_STRINGS["export"],
                f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
            )
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            import traceback

            logging.error(f"TSV publication export failed:{e}\n{traceback.format_exc()}")
            QMessageBox.warning(
                self.window() or None,
                CERTUS_UI_STRINGS["export_failed"],
                f"TSV publication: {e}",
            )


def wrap_scientific_plot_with_toolbar(main_window: QMainWindow, plot: CertusScientificPlot) -> QWidget:
    """Places a toolbar (zoom reset, detach, export) above the plot."""
    outer = QWidget()
    lay = QVBoxLayout(outer)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    tb = plot.get_toolbar(main_window)
    if tb is not None:
        lay.addWidget(tb)
    lay.addWidget(plot)
    return outer


def clone_plot_widget(original: Any, title_override: str | None = None) -> "CertusScientificPlot":
    """
    Creates a deep visual copy of a CertusScientificPlot or PlotWidget.
    Preserves curves, scatter points, colors, symbols, and labels.
    """
    if original is None:
        return None
    plot_item = getattr(original, "plotItem", None)
    title = title_override or ""
    if not title and plot_item and hasattr(plot_item, "titleLabel"):
        t_lbl = plot_item.titleLabel
        title = t_lbl.text if hasattr(t_lbl, "text") else str(t_lbl)

    y_label, x_label = "", ""
    if plot_item:
        ax_l = plot_item.getLabel("left")
        if ax_l:
            y_label = ax_l.text
        ax_b = plot_item.getLabel("bottom")
        if ax_b:
            x_label = ax_b.text

    clone = CertusScientificPlot(None, title=title, y_label=str(y_label), x_label=str(x_label))

    if hasattr(original, "viewRange"):
        vr = original.viewRange()
        clone.setXRange(vr[0][0], vr[0][1], 0)
        clone.setYRange(vr[1][0], vr[1][1], 0)

    if plot_item:
        to_skip = []
        if hasattr(original, "vLine"):
            to_skip.append(original.vLine)
        if hasattr(original, "hLine"):
            to_skip.append(original.hLine)
        if hasattr(original, "info_label"):
            to_skip.append(original.info_label)
        if hasattr(original, "info_bg"):
            to_skip.append(original.info_bg)
        for item in plot_item.items:
            if item in to_skip:
                continue
            if isinstance(item, pg.PlotDataItem):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                opts = item.opts.copy()
                if "pen" not in opts and hasattr(item, "pen") and item.pen:
                    opts["pen"] = item.pen
                clone.plot(x, y, **opts)
            elif isinstance(item, pg.ScatterPlotItem):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                opts = {}
                if hasattr(item, "opts"):
                    opts = item.opts
                pen = opts.get("pen")
                brush = opts.get("brush")
                size = opts.get("size", 10)
                s_clone = pg.ScatterPlotItem(x, y, pen=pen, brush=brush, size=size)
                clone.addItem(s_clone)

    if plot_item and hasattr(plot_item, "ctrl"):
        clone.setLogMode(
            x=plot_item.ctrl.logXCheck.isChecked(),
            y=plot_item.ctrl.logYCheck.isChecked(),
        )
        clone.showGrid(
            x=plot_item.ctrl.xGridCheck.isChecked(),
            y=plot_item.ctrl.yGridCheck.isChecked(),
        )
    return clone


ScientificPlotRefined = CertusScientificPlot
