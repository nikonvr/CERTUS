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
from certus.ui.certus_ui_utils import set_certus_window_icon

class ProgressDialog(QWidget):
    """Progress dialog with cancellation support"""

    canceled = pyqtSignal()

    def __init__(self, title: str = "Processing...", parent=None) -> None:

        super().__init__(parent)

        self.setWindowTitle(title)

        self.setFixedSize(400, 150)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)

        set_certus_window_icon(self)

        self._setup_ui(title)

        self._is_canceled = False

    def _setup_ui(self, title: str) -> None:

        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(15)

        self.title_label = QLabel(title)

        self.title_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 14px; font-weight: 600;")

        layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(0, 100)

        self.progress_bar.setValue(0)

        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")

        self.status_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 12px;")

        layout.addWidget(self.status_label)

        self.cancel_btn = QPushButton("Cancel")

        self.cancel_btn.setToolTip("Cancel the current operation.")

        self.cancel_btn.setStyleSheet(CertusTheme.get_button_style("danger"))

        self.cancel_btn.clicked.connect(self._on_cancel)

        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _on_cancel(self) -> None:

        self._is_canceled = True

        self.cancel_btn.setEnabled(False)

        self.cancel_btn.setText("Canceling...")

        self.canceled.emit()

    def is_canceled(self) -> bool:

        return self._is_canceled

    def finish(self) -> None:

        self.progress_bar.setValue(100)

        self.close()

class EnhancedProgressWidget(QWidget):
    """UX-8: Smart Telemetry & Progress Widget with Main and Sub-Progress."""

    canceled = pyqtSignal()

    def __init__(self, parent=None, main_label: str = "") -> None:
        super().__init__(parent)
        self._main_label = main_label
        self._start_time: float | None = None
        self._last_time: float | None = None
        self._last_evals: int = 0
        self._evals_per_sec: float = 0.0
        self._is_running = False
        self._is_canceled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Progress bars container
        bars_layout = QVBoxLayout()
        bars_layout.setSpacing(2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        self.sub_progress_bar = QProgressBar()
        self.sub_progress_bar.setFixedWidth(200)
        self.sub_progress_bar.setFixedHeight(4)
        self.sub_progress_bar.setRange(0, 100)
        self.sub_progress_bar.setTextVisible(False)
        self.sub_progress_bar.setStyleSheet(
            CertusTheme.get_progress_bar_style().replace(CertusTheme.PRIMARY, CertusTheme.INFO_TEXT)
        )
        self.sub_progress_bar.setVisible(False)

        bars_layout.addWidget(self.progress_bar)
        bars_layout.addWidget(self.sub_progress_bar)

        self._anim_main = QPropertyAnimation(self.progress_bar, b"value")
        self._anim_main.setDuration(250)
        self._anim_main.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anim_sub = QPropertyAnimation(self.sub_progress_bar, b"value")
        self._anim_sub.setDuration(150)

        layout.addLayout(bars_layout)

        # Label for phase and telemetry
        self.info_label = QLabel(self._main_label)
        self.info_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.info_label)

        # Cancel Button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel the current operation.")
        self.cancel_btn.setStyleSheet(CertusTheme.get_button_style("danger"))
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)

    def _on_cancel(self) -> None:
        self._is_canceled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Canceling...")
        self.canceled.emit()

    def start(self) -> None:
        self._start_time = time.time()
        self._last_time = self._start_time
        self._last_evals = 0
        self._evals_per_sec = 0.0
        self._is_running = True
        self._is_canceled = False

        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(0)
        self.sub_progress_bar.setValue(0)
        self.sub_progress_bar.setVisible(False)
        self.info_label.setText("Starting...")

        if self.cancel_btn.isVisible():
            self.cancel_btn.setEnabled(True)
            self.cancel_btn.setText("Cancel")

    def enable_cancel(self, enabled: bool = True) -> None:
        self.cancel_btn.setVisible(bool(enabled))
        self.cancel_btn.setEnabled(bool(enabled) and self._is_running and (not self._is_canceled))
        if enabled and not self._is_canceled:
            self.cancel_btn.setText("Cancel")
        if not enabled:
            self._is_canceled = False

    def is_canceled(self) -> bool:
        return bool(self._is_canceled)

    def set_time_budget(self, budget_seconds: float) -> None:
        self._time_budget = budget_seconds

    def update(
        self,
        iteration: int,
        max_iter: int,
        evals: int = 0,
        phase: str = "",
        extra_info: str = "",
        sub_iteration: int = 0,
        max_sub_iter: int = 0,
        animate: bool = True,
        progress_pct: int = -1,
    ) -> None:
        if not self._is_running or self._start_time is None:
            self.start()

        now = time.time()
        elapsed = now - self._start_time
        dt = now - (self._last_time or now)

        if dt > 0 and evals > 0:
            current_eps = (evals - self._last_evals) / dt
            if current_eps >= 0:
                self._evals_per_sec = 0.7 * self._evals_per_sec + 0.3 * current_eps

        self._last_time = now
        self._last_evals = evals

        if progress_pct >= 0:
            target_val = min(100, progress_pct)
        else:
            # Fallback heuristic
            target_val = 0
            if max_iter > 0:
                target_val = int(100 * iteration / max_iter)
            if evals > 0 and getattr(self, "_last_evals", None) is not None:
                eval_ratio = min(1.0, evals / max(1, self._last_evals + max(1, evals)))
                target_val = int(100 * (0.7 * (target_val / 100.0) + 0.3 * eval_ratio))
            target_val = min(100, max(0, target_val))

        if self.progress_bar.value() != target_val:
            if animate:
                self._anim_main.stop()
                self._anim_main.setStartValue(self.progress_bar.value())
                self._anim_main.setEndValue(target_val)
                self._anim_main.start()
            else:
                self._anim_main.stop()
                self.progress_bar.setValue(target_val)

        # Sub progress
        if max_sub_iter > 0:
            self.sub_progress_bar.setVisible(True)
            target_sub = int(100 * sub_iteration / max_sub_iter)
            target_sub = min(100, max(0, target_sub))
            if self.sub_progress_bar.value() != target_sub:
                if animate:
                    self._anim_sub.stop()
                    self._anim_sub.setStartValue(self.sub_progress_bar.value())
                    self._anim_sub.setEndValue(target_sub)
                    self._anim_sub.start()
                else:
                    self._anim_sub.stop()
                    self.sub_progress_bar.setValue(target_sub)
        else:
            self.sub_progress_bar.setVisible(False)

        parts = []
        if phase:
            parts.append(phase)
        parts.append(self._format_time(elapsed))

        if evals > 0:
            eval_str = f"{evals:,} evals"
            if self._evals_per_sec > 10:
                eval_str += f" ({int(self._evals_per_sec):,} eq/s)"
            parts.append(eval_str)

        if extra_info:
            parts.append(extra_info)

        self.info_label.setText(" | ".join(parts))

    def stop(self, final_message: str = "Done") -> None:
        self._is_running = False
        if self.cancel_btn.isVisible():
            self.cancel_btn.setEnabled(False)
        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(100)
        self.sub_progress_bar.setVisible(False)
        if self._start_time:
            self.info_label.setText(f"{final_message} ({self._format_time(time.time() - self._start_time)})")
        else:
            self.info_label.setText(final_message)

    def reset(self) -> None:
        self._start_time = None
        self._last_time = None
        self._last_evals = 0
        self._evals_per_sec = 0.0
        self._is_running = False
        self._is_canceled = False
        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(0)
        self.sub_progress_bar.setValue(0)
        self.sub_progress_bar.setVisible(False)
        self.info_label.setText("")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")

    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds < 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        if m < 60:
            return f"{m:02d}:{s:02d}"
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}"

