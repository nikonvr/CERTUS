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

class CertusSectionHeader(QWidget):
    """Lightweight section divider: bold title + optional muted caption."""

    def __init__(self, title: str, caption: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 2)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-weight: 700; font-size: 11px; color: {CertusTheme.TEXT_MAIN}; "
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        lay.addWidget(lbl)
        if caption:
            cap = QLabel(caption)
            cap.setStyleSheet(f"font-size: 10px; color: {CertusTheme.TEXT_SUB};")
            lay.addWidget(cap)
        lay.addStretch(1)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {CertusTheme.BORDER};")
        lay.addWidget(sep)

class CertusStepper(QWidget):
    """Compact vertical stepper. step_activated(int) emitted on click."""

    step_activated = pyqtSignal(int)

    def __init__(self, steps: list, parent=None, columns: int = 1) -> None:
        super().__init__(parent)
        self._steps = steps
        self._current = 0
        self._columns = max(1, int(columns or 1))
        self._btns: list[QPushButton] = []
        self._badges: list[QPushButton] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        if self._columns <= 1:
            for i, label in enumerate(steps):
                row = QHBoxLayout()
                row.setSpacing(6)
                # Circle badge
                badge = QPushButton(str(i + 1))
                badge.setFixedSize(22, 22)
                badge.setEnabled(False)
                badge.setObjectName(f"StepBadge_{i}")
                badge.setStyleSheet(self._badge_style(i))
                # Label
                btn = QPushButton(label)
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setObjectName(f"StepBtn_{i}")
                btn.setStyleSheet(self._btn_style(i))
                idx = i

                def _handle_click(*_args, step_index=idx) -> None:
                    self._on_click(step_index)

                btn.clicked.connect(_handle_click)
                row.addWidget(badge)
                row.addWidget(btn, 1)
                row.addStretch(0)
                self._btns.append(btn)
                self._badges.append(badge)
                lay.addLayout(row)
                if i < len(steps) - 1:
                    connector = QLabel()
                    connector.setFixedWidth(2)
                    connector.setMinimumHeight(4)
                    connector.setStyleSheet(f"background: {CertusTheme.BORDER}; margin-left: 10px;")
                    connector_row = QHBoxLayout()
                    connector_row.setContentsMargins(10, 0, 0, 0)
                    connector_row.addWidget(connector)
                    connector_row.addStretch(1)
                    lay.addLayout(connector_row)
        else:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            for i, label in enumerate(steps):
                row_idx = int(i // self._columns)
                col_idx = int(i % self._columns)
                cell = QHBoxLayout()
                cell.setSpacing(6)
                badge = QPushButton(str(i + 1))
                badge.setFixedSize(22, 22)
                badge.setEnabled(False)
                badge.setObjectName(f"StepBadge_{i}")
                badge.setStyleSheet(self._badge_style(i))
                btn = QPushButton(label)
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setObjectName(f"StepBtn_{i}")
                btn.setStyleSheet(self._btn_style(i))
                idx = i

                def _handle_click(*_args, step_index=idx) -> None:
                    self._on_click(step_index)

                btn.clicked.connect(_handle_click)
                cell.addWidget(badge)
                cell.addWidget(btn, 1)
                grid.addLayout(cell, row_idx, col_idx)
                self._btns.append(btn)
                self._badges.append(badge)
            lay.addLayout(grid)

    def _badge_style(self, i: int) -> str:
        active = i == self._current
        done = i < self._current
        if active:
            bg, fg, border = CertusTheme.PRIMARY, "#fff", CertusTheme.PRIMARY
        elif done:
            bg, fg, border = CertusTheme.SUCCESS, "#fff", CertusTheme.SUCCESS
        else:
            bg, fg, border = CertusTheme.SURFACE, CertusTheme.TEXT_SUB, CertusTheme.BORDER
        return (
            f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {border}; "
            f"border-radius: 12px; font-weight: 700; font-size: 10px; }}"
        )

    def _btn_style(self, i: int) -> str:
        active = i == self._current
        done = i < self._current
        if active:
            color, weight = CertusTheme.PRIMARY, "700"
        elif done:
            color, weight = CertusTheme.TEXT_SUB, "500"
        else:
            color, weight = CertusTheme.TEXT_SUB, "400"
        return (
            f"QPushButton {{ background: transparent; border: none; color: {color}; "
            f"font-weight: {weight}; font-size: 11px; text-align: left; padding: 0; "
            f"min-height: 16px; }}"
        )

    def _on_click(self, idx: int) -> None:
        self.step_activated.emit(idx)

    def set_step(self, idx: int) -> None:
        self._current = max(0, min(idx, len(self._steps) - 1))
        self._refresh()

    def _refresh(self) -> None:
        for i, btn in enumerate(self._btns):
            btn.setStyleSheet(self._btn_style(i))
            if i < len(self._badges):
                self._badges[i].setStyleSheet(self._badge_style(i))

class CertusCollapsible(QWidget):
    """Collapsible section: chevron header + body widget. Toggles on click."""

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header button
        self._hdr = QPushButton()
        self._hdr.setFlat(True)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr.setCheckable(True)
        self._hdr.setChecked(expanded)
        self._title = title
        self._hdr.clicked.connect(self._toggle)
        self._hdr.setStyleSheet(
            f"QPushButton {{ background: {CertusTheme.SURFACE_HOVER}; border: none; "
            f"border-radius: 6px; padding: 6px 10px; font-weight: 600; font-size: 11px; "
            f"color: {CertusTheme.TEXT_MAIN}; text-align: left; }}"
            f"QPushButton:hover {{ background: {CertusTheme.BORDER}; }}"
        )
        lay.addWidget(self._hdr)

        self._content = content
        self._content.setVisible(expanded)
        lay.addWidget(self._content)
        self._update_label()

    def _toggle(self) -> None:
        visible = not self._content.isVisible()
        try:
            from certus.ui.certus_animations import fade_in, fade_out

            if visible:
                self._content.setVisible(True)
                fade_in(self._content, duration_ms=180)
            else:
                fade_out(self._content, duration_ms=150, hide_on_finish=True)
        except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError):
            # Animation module/function failed - fallback to direct visibility change
            self._content.setVisible(visible)
        self._update_label()

    def _update_label(self) -> None:
        arrow = "▾" if self._content.isVisible() else "▸"
        self._hdr.setText(f"{arrow}  {self._title}")

    def is_expanded(self) -> bool:
        return bool(self._content.isVisible())

    def set_expanded(self, expanded: bool) -> None:
        want = bool(expanded)
        if self._content.isVisible() == want:
            self._hdr.setChecked(want)
            self._update_label()
            return
        self._hdr.setChecked(want)
        self._toggle()

class CertusActionBar(QWidget):
    """Compact horizontal action bar: Run / Stop + optional toggles in a styled container."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(6)
        self.setObjectName("CertusActionBar")
        self.setStyleSheet(
            f"#CertusActionBar {{ background: {CertusTheme.SURFACE}; "
            f"border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; }}"
        )

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)

