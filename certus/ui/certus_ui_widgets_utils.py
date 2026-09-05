import copy
import functools
import logging
import os
from pathlib import Path
import queue
import sys
import time
import traceback
import warnings
from collections import deque
from typing import Any, Callable
import numpy as np
from pydantic import ValidationError
import pandas as pd
import pyqtgraph as pg
from certus.core.certus_core import CFG, certus_timestamp_display
from certus.utils.certus_dto import IndexSplineConfigDTO
from certus_physics import init_thickness
from certus_physics.structures import Layer, Target
import pyqtgraph.exporters  # pylint: disable=unused-import
from PyQt6.QtCore import (
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
    QMetaObject,
    Q_ARG,
    QSettings,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CertusRuntime,
    SVG_AVAILABLE,
    build_runtime,
    handle_exception,
    get_resource_path,
    load_theme_config,
    save_theme_config,
)
from certus.core.certus_core import OPENPYXL_AVAILABLE
from certus.utils.certus_data import read_data_file_robust
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.core.certus_core import get_export_config, setup_module_logging
from certus.core.certus_core import QueueHandler, setup_gui_logger
from certus.ui.certus_plot import (
    sanitize_xy_for_plot,
    plot_widget_plot_finite,
    CertusScientificPlot,
    wrap_scientific_plot_with_toolbar,
    clone_plot_widget,
    ScientificPlotRefined,
)
from certus.ui.certus_io_ui import CERTUS_UI_STRINGS
from certus.ui.certus_ui_widgets_factory import create_header_logo_widget, create_log_widget
from certus.ui.certus_ui_utils import apply_certus_theme, set_certus_window_icon, update_global_plot_config

class CertusToast(QLabel):
    """Non-modal transient notification auto-hiding after duration_ms."""

    _LEVELS = {
        "info": ("PRIMARY", "#fff"),
        "success": ("SUCCESS", "#fff"),
        "warning": ("WARNING", "#222"),
        "error": ("DANGER", "#fff"),
    }

    def __init__(self, parent: QWidget, text: str, level: str = "info", duration_ms: int = 2800) -> None:
        super().__init__(parent)
        color_key, fg = self._LEVELS.get(level, self._LEVELS["info"])
        bg = getattr(CertusTheme, color_key, CertusTheme.PRIMARY)
        self.setText(text)
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 11px;"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        QTimer.singleShot(duration_ms, self.close)

    def _reposition(self) -> None:
        p = self.parent()
        if not isinstance(p, QWidget):
            return
        margin = 18
        x = p.width() - self.width() - margin
        y = p.height() - self.height() - margin - 22
        self.move(max(margin, x), max(margin, y))

class CertusStatusPill(QLabel):
    """Compact status badge: 'Ready', 'Running', 'Done', 'Error'. Same API as QLabel."""

    def __init__(self, text: str = "Ready", level: str = "ready", parent=None) -> None:
        super().__init__(text, parent)
        self._level = level
        self.setWordWrap(True)
        self._apply()

    def _levels(self) -> dict:
        return {
            "ready": (CertusTheme.SUCCESS + "22", CertusTheme.SUCCESS, CertusTheme.SUCCESS + "55"),
            "running": (CertusTheme.PRIMARY + "22", CertusTheme.PRIMARY, CertusTheme.PRIMARY + "55"),
            "done": (CertusTheme.SECONDARY + "22", CertusTheme.TEXT_MAIN, CertusTheme.BORDER),
            "error": (CertusTheme.DANGER + "22", CertusTheme.DANGER, CertusTheme.DANGER + "55"),
            "warning": (CertusTheme.WARNING + "22", CertusTheme.TEXT_MAIN, CertusTheme.WARNING + "55"),
            "default": (CertusTheme.SURFACE_HOVER, CertusTheme.TEXT_SUB, CertusTheme.BORDER),
        }

    def set_level(self, level: str) -> None:
        self._level = level
        self._apply()

    def setText(self, text: str) -> None:
        super().setText(text)

    def _apply(self) -> None:
        bg, fg, border = self._levels().get(self._level, self._levels()["default"])
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;"
        )

class CertusThemeToggle(QPushButton):
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setFixedSize(32, 32)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.clicked.connect(self.toggle)

        self.update_appearance()

    def update_appearance(self) -> None:

        mode = load_theme_config()

        # Both branches used to be the empty string, so this 32x32 round button
        # rendered as an empty circle in all eleven windows. U+25D0/U+25D1 stay
        # inside the BMP: an emoji outside it renders as a tofu box depending on
        # the installed font.
        self.setText("◐" if mode == "light" else "◑")

        self.setToolTip("Switch to dark theme" if mode == "light" else "Switch to light theme")

        self.setStyleSheet(f"""
            QPushButton {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                border-color: {CertusTheme.PRIMARY};
                background: {CertusTheme.SURFACE_HOVER};
            }}
        """)

    def toggle(self, checked=False) -> None:

        mode = load_theme_config()

        new_mode = "dark" if mode == "light" else "light"

        save_theme_config(new_mode)

        CertusTheme.configure(new_mode)

        self.update_appearance()

        update_global_plot_config(new_mode == "dark")

        CertusTheme.apply_to_app(QApplication.instance(), new_mode == "dark")

        self.theme_changed.emit(new_mode)

        # Internal refresh Logic

        w = self.window()

        if hasattr(w, "_apply_theme"):
            w._apply_theme()

        else:
            apply_certus_theme(w)

class AutoShrinkTitleLabel(QLabel):
    """A label that shrinks its font size to prevent being cut off."""
    def __init__(self, text: str, default_size: int = 16, min_size: int = 9, color: str = CertusTheme.TEXT_MAIN, weight: int | str = 800, parent=None):
        super().__init__(text, parent)
        from PyQt6.QtWidgets import QSizePolicy
        from PyQt6.QtCore import Qt
        
        self._default_size = default_size
        self._min_size = min_size
        self._color = color
        self._weight = weight
        self._current_rendered_size = default_size
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)
        self.setWordWrap(True)
        self._update_style(default_size)

    def _update_style(self, size: int) -> None:
        if self._current_rendered_size == size and self.styleSheet():
            return
        self._current_rendered_size = size
        self.setStyleSheet(f"font-weight: {self._weight}; color: {self._color}; font-size: {size}px; background: transparent;")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
            
        current_size = self._default_size
        font = self.font()
        from PyQt6.QtGui import QFontMetrics
        
        while current_size >= self._min_size:
            font.setPixelSize(current_size)
            fm = QFontMetrics(font)
            # Use 1000 for height to simulate infinite available height during measurement
            bound = fm.boundingRect(0, 0, rect.width(), 1000, Qt.TextFlag.TextWordWrap, self.text())
            if bound.height() <= rect.height():
                break
            current_size -= 1
            
        self._update_style(current_size)

class CertusLogPanel(QWidget):
    """

    Shared log panel: header with title + Copy button, and a read-only log QTextEdit.

    Use .log_text to connect to queue handler or append messages.

    """

    copied = pyqtSignal()

    def __init__(
        self,
        title: str = "LOGS",
        visible: bool = True,
        height: int = None,
        parent=None,
    ) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"background-color: {CertusTheme.SURFACE};")

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        header = QWidget()

        header.setFixedHeight(28)

        header.setStyleSheet(f"background-color: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        hl = QHBoxLayout(header)

        hl.setContentsMargins(5, 0, 5, 0)

        lbl = QLabel(title)

        lbl.setStyleSheet(f"font-weight: bold; color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        hl.addWidget(lbl)

        hl.addStretch()

        btn_copy = QPushButton(CERTUS_UI_STRINGS["copy_logs"])

        btn_copy.setToolTip("Copy all logs to clipboard")

        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_copy.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {CertusTheme.PRIMARY}; font-weight: 700; padding: 2px 6px; border-radius: 8px; }} QPushButton:hover {{ color: {CertusTheme.TEXT_MAIN}; background: {CertusTheme.SURFACE_HOVER}; }}"
        )

        btn_copy.clicked.connect(self._on_copy)

        hl.addWidget(btn_copy)

        layout.addWidget(header)

        self.log_text = create_log_widget(visible=visible, height=height)

        layout.addWidget(self.log_text)

    def _on_copy(self) -> None:

        text = self.log_text.toPlainText()

        if text:
            app = QApplication.instance()

            if app and app.clipboard():
                app.clipboard().setText(text)

        self.copied.emit()

    def copy_to_clipboard(self) -> None:
        """Copy log content to clipboard. Emits copied after."""

        self._on_copy()

class NumericAwareItem(QTableWidgetItem):
    """Sorts numerically when both cells hold a number, alphabetically otherwise.

    Overriding __lt__ is the only approach that works. QTableWidgetItem compares
    the DisplayRole, so writing the value into Qt.ItemDataRole.EditRole does not
    change the order - and it is not even harmless: on this class Qt treats
    EditRole and DisplayRole as the SAME value, so the float silently rewrites
    what the operator sees. Measured 2026-09-04: "-12,5" started displaying as
    "-12.5", the French decimal comma gone from the screen.

    The comma is accepted on input for the same reason: CERTUS shows French
    decimals in several tables.
    """

    @staticmethod
    def _as_number(item):
        try:
            return float(item.text().strip().replace(",", "."))
        except (ValueError, AttributeError):
            return None

    def __lt__(self, other) -> bool:
        mine = self._as_number(self)
        theirs = self._as_number(other)
        if mine is None or theirs is None:
            return super().__lt__(other)
        return mine < theirs


class ExcelTableWidget(QTableWidget):
    """Table with copy-paste, sortable columns and draggable column borders."""

    #: Subclasses holding an ordered stack (where row order IS the physics) set
    #: this to False so the operator cannot scramble the layer sequence.
    CERTUS_ALLOW_SORTING = True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Measured 2026-09-03: none of the suite's 32 main-window tables could be
        # sorted, and most had no draggable column border either.
        if self.CERTUS_ALLOW_SORTING:
            self.setSortingEnabled(True)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)

    def setItem(self, row: int, column: int, item) -> None:
        """Upgrade a plain item so the column sorts by value, not by spelling.

        Call sites build ordinary QTableWidgetItem all over the suite, and
        changing every one of them would be a large diff for a property that
        belongs to the table. Only an EXACT QTableWidgetItem is replaced: a
        subclass carries behaviour we must not drop.

        Everything the caller set is carried over, and the new item is returned
        to nobody - so a caller holding a reference to the original would be
        modifying a detached item. That is why the upgrade happens here, before
        the item is ever shown, and why the copy is exhaustive.
        """
        if type(item) is QTableWidgetItem:
            upgraded = NumericAwareItem(item.text())
            upgraded.setFlags(item.flags())
            upgraded.setTextAlignment(item.textAlignment())
            upgraded.setToolTip(item.toolTip())
            upgraded.setForeground(item.foreground())
            upgraded.setBackground(item.background())
            upgraded.setFont(item.font())
            for role in (Qt.ItemDataRole.UserRole, Qt.ItemDataRole.UserRole + 1):
                value = item.data(role)
                if value is not None:
                    upgraded.setData(role, value)
            item = upgraded
        super().setItem(row, column, item)

    def setRowCount(self, rows: int) -> None:
        """Suspend sorting while the table is being refilled.

        With sorting live, inserting rows one by one reorders them mid-flight and
        the displayed table stops matching the model. Callers clear the table with
        setRowCount(0) before repopulating, so that is where we disarm it.

        Re-arming is automatic: population is synchronous, so a zero-delay timer
        fires once the caller is done. No call site has to change.
        """
        if rows == 0 and self.isSortingEnabled():
            self._certus_sorting_suspended = True
            self.setSortingEnabled(False)
            QTimer.singleShot(0, self.certus_finish_population)
        super().setRowCount(rows)

    def certus_finish_population(self) -> None:
        """Re-enable sorting after a refill. Safe to call when it was never off."""
        if getattr(self, "_certus_sorting_suspended", False):
            self._certus_sorting_suspended = False
            if self.CERTUS_ALLOW_SORTING:
                try:
                    self.setSortingEnabled(True)
                except RuntimeError:  # table already destroyed
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def certus_lock_row_order(self) -> None:
        """Forbid sorting on this instance: its row order carries meaning.

        Call it on any table holding an optical STACK. Re-ordering layers there
        would silently describe a different filter - the row order IS the physics.
        """
        self.CERTUS_ALLOW_SORTING = False
        self.setSortingEnabled(False)

    def keyPressEvent(self, e) -> None:

        if e.matches(QKeySequence.StandardKey.Paste):
            self._paste()

        elif e.matches(QKeySequence.StandardKey.Copy):
            self._copy()

        elif e.key() == Qt.Key.Key_Delete:
            self._delete()

        else:
            super().keyPressEvent(e)

    def _paste(self) -> None:

        clip = QApplication.clipboard().text()

        if not clip:
            return

        rows = clip.split("\n")

        r = max(0, self.currentRow())

        c = max(0, self.currentColumn())

        if r + len(rows) > self.rowCount():
            self.setRowCount(r + len(rows))

        for i, row in enumerate(rows):
            vals = row.split("\t")

            for j, v in enumerate(vals):
                if c + j < self.columnCount():
                    self.setItem(r + i, c + j, QTableWidgetItem(v.strip()))

    def _copy(self) -> None:

        sel = self.selectedRanges()

        if not sel:
            return

        s = ""

        for r in range(sel[0].topRow(), sel[0].bottomRow() + 1):
            row = []

            for c in range(sel[0].leftColumn(), sel[0].rightColumn() + 1):
                it = self.item(r, c)

                row.append(it.text() if it else "")

            s += "\t".join(row) + "\n"

        QApplication.clipboard().setText(s)

    def _delete(self) -> None:

        for it in self.selectedItems():
            it.setText("")

    def set_data(self, headers: list[str], data: list[list[str]]) -> None:
        """Standard method to populate table data."""

        self.setColumnCount(len(headers))

        self.setHorizontalHeaderLabels(headers)

        self.setRowCount(len(data))

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                self.setItem(r, c, QTableWidgetItem(str(val)))

    def export_to_excel(self, filename: str) -> bool:
        """Export table content to Excel file."""

        try:
            rows = self.rowCount()

            cols = self.columnCount()

            data = []

            headers = [self.horizontalHeaderItem(c).text() for c in range(cols)]

            for r in range(rows):
                row_data = []

                for c in range(cols):
                    item = self.item(r, c)

                    row_data.append(item.text() if item else "")

                data.append(row_data)

            df = pd.DataFrame(data, columns=headers)

            df.to_excel(filename, index=False)

            return True

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            import traceback

            logging.error(f"Excel export failed:{e}\n{traceback.format_exc()}")

            return False

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other) -> Any:

        try:
            return float(self.text()) < float(other.text())

        except (ValueError, TypeError):
            # Fallback to string comparison if not numeric

            return super().__lt__(other)

class DetachedPlotWindow(QMainWindow):
    closed_signal = pyqtSignal()

    def __init__(self, plot_widget, parent=None, title="Detached Plot") -> None:

        super().__init__(parent)

        self.setWindowTitle(title)

        self.resize(1150, 780)

        self.setMinimumSize(520, 380)

        # Detached windows are reopened constantly during a session; remember
        # where the operator put them instead of recentring every time. Keyed on
        # the title so each chart keeps its own place.
        self._qs_geometry_key = f"detached/{title}/geometry"
        try:
            saved = QSettings("CERTUS", "DetachedPlots").value(self._qs_geometry_key)
            if saved is not None:
                self.restoreGeometry(saved)
        except (RuntimeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.plot_widget = plot_widget

        # Central widget container

        c = QWidget()

        self.setCentralWidget(c)

        l = QVBoxLayout(c)

        l.setContentsMargins(0, 0, 0, 0)

        l.setSpacing(0)

        # Header with Logo (Systematic)

        l.addWidget(create_header_logo_widget(title_text=title, logo_width=180))

        # Optional toolbar from the widget itself

        if hasattr(plot_widget, "get_toolbar"):
            tb = plot_widget.get_toolbar(self)

            if tb:
                l.addWidget(tb)

        # The Plot Logic

        l.addWidget(plot_widget)

        # Apply Theme

        apply_certus_theme(self)

        set_certus_window_icon(self)

    def closeEvent(self, e) -> None:

        try:
            QSettings("CERTUS", "DetachedPlots").setValue(self._qs_geometry_key, self.saveGeometry())
        except (RuntimeError, TypeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.closed_signal.emit()

        super().closeEvent(e)

class SkeletonLoaderWidget(QWidget):
    """
    A premium skeleton loader widget with a smooth horizontal shimmer effect.
    Simulates loading of dashboards, charts, or tables (P0 UX action plan).
    """
    def __init__(self, parent=None, shape: str = "chart") -> None:
        super().__init__(parent)
        self.shape = shape  # "chart", "table", "dashboard", "cards"
        self._shimmer_offset = -0.5
        
        from PyQt6.QtCore import QTimeLine, QEasingCurve
        self._timeline = QTimeLine(1400, self)
        self._timeline.setFrameRange(0, 100)
        self._timeline.setLoopCount(0)  # Loop infinitely
        self._timeline.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._timeline.frameChanged.connect(self._update_shimmer)
        self._timeline.start()

    def _update_shimmer(self, frame: int) -> None:
        self._shimmer_offset = -0.5 + (frame / 100.0) * 2.0
        self.update()

    def paintEvent(self, event) -> None:
        from PyQt6.QtGui import QPainter, QLinearGradient, QBrush, QColor, QPainterPath
        from PyQt6.QtCore import QRectF, Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from certus.ui.certus_ui import CertusTheme
        is_dark = getattr(CertusTheme, "DARK_MODE", False)
        
        base_color = QColor("#1e293b") if is_dark else QColor("#e2e8f0")
        shimmer_color = QColor("#334155") if is_dark else QColor("#f1f5f9")
        
        w = float(self.width())
        h = float(self.height())
        
        grad = QLinearGradient(self._shimmer_offset * w, 0, (self._shimmer_offset + 0.4) * w, h)
        grad.setColorAt(0.0, base_color)
        grad.setColorAt(0.45, base_color)
        grad.setColorAt(0.5, shimmer_color)
        grad.setColorAt(0.55, base_color)
        grad.setColorAt(1.0, base_color)
        
        brush = QBrush(grad)
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        
        if self.shape == "chart":
            axis_pen = QColor("#334155") if is_dark else QColor("#cbd5e1")
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(axis_pen, 1))
            painter.drawLine(40, int(h - 40), int(w - 40), int(h - 40))
            painter.drawLine(40, 40, 40, int(h - 40))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(brush)
            path = QPainterPath()
            path.moveTo(40, h - 40)
            path.cubicTo(w * 0.25, h * 0.45, w * 0.5, h * 0.75, w * 0.75, h * 0.3)
            path.lineTo(w - 40, h - 40)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif self.shape == "table":
            row_height = 20
            spacing = 8
            y = 15
            while y + row_height < h:
                painter.drawRoundedRect(QRectF(15, y, w * 0.2, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.25, y, w * 0.3, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.6, y, w * 0.15, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.8, y, w * 0.15 - 15, row_height), 4, 4)
                y += row_height + spacing
                
        elif self.shape == "cards":
            card_w = (w - 30) / 2
            card_h = (h - 30) / 2
            if card_w > 10 and card_h > 10:
                painter.drawRoundedRect(QRectF(10, 10, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(20 + card_w, 10, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(10, 20 + card_h, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(20 + card_w, 20 + card_h, card_w, card_h), 8, 8)
        else:
            painter.drawRoundedRect(QRectF(10, 10, w - 20, h - 20), 8, 8)

