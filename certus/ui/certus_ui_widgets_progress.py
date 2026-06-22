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


from certus.ui.certus_ui_shared import _format_progress_duration
from certus.utils.certus_progress_tracker import ProgressSnapshot, StepState, smooth_progress


def _format_progress_status(
    status: str,
    phase: str = "",
    run_id: str | None = None,
    budget: float | None = None,
    elapsed: float | None = None,
    evals: int = 0,
    next_action: str = "",
    run_context: "Any | None" = None,
) -> str:
    """Render a compact, premium status line shared by UX feedback widgets."""
    status_label = {
        "idle": "Idle",
        "starting": "Starting",
        "running": "Running",
        "done": "Done",
        "cancelled": "Cancelled",
        "error": "Error",
    }.get(str(status).lower(), str(status).title())
    parts = [f"Status: {status_label}"]
    if phase:
        parts.append(f"Phase: {phase}")

    actual_run_id = getattr(run_context, "run_id", run_id) if run_context else run_id
    if actual_run_id:
        parts.append(f"Run: {actual_run_id}")
    if budget is not None:
        parts.append(f"Budget: {_format_progress_duration(budget)}")
    if elapsed is not None:
        parts.append(f"Elapsed: {_format_progress_duration(elapsed)}")
    if evals > 0:
        parts.append(f"Evals: {evals:,}")
    if next_action:
        parts.append(f"Next: {next_action}")
    return " • ".join(parts)


class ProgressDialog(QWidget):
    """Progress dialog with cancellation support"""

    canceled = pyqtSignal()

    def __init__(self, title: str = "Processing...", parent=None, run_id: str | None = None, run_context: "Any | None" = None) -> None:

        super().__init__(parent)

        self.setWindowTitle(title)

        self.setFixedSize(400, 150)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)

        set_certus_window_icon(self)

        self._run_context = run_context
        self._run_id = getattr(run_context, "run_id", run_id) if run_context else run_id
        self._setup_ui(title)

        self._is_canceled = False

    def _setup_ui(self, title: str) -> None:

        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(15)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 14px; font-weight: 600;")

        layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(0, 100)

        self.progress_bar.setValue(0)

        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to start")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 12px;")

        layout.addWidget(self.status_label)

        self.cancel_btn = QPushButton("Cancel")

        self.cancel_btn.setToolTip("Cancel the current operation.")

        self.cancel_btn.setStyleSheet(CertusTheme.get_button_style("danger"))

        self.cancel_btn.clicked.connect(self._on_cancel)

        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)

        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        layout.addWidget(self.detail_label)
        self.detail_label.setText(_format_progress_status(
            status="idle",
            next_action="start run",
            run_id=self._run_id,
        ))

    def apply_progress_snapshot(self, snapshot: ProgressSnapshot) -> None:
        """Apply a normalized progress snapshot without changing the legacy API."""
        if snapshot.message:
            self.info_label.setText(snapshot.message)
        if snapshot.phase:
            self.stage_header.setVisible(True)
            self._stage_value_label.setVisible(True)
            self._stage_value_label.setText(snapshot.phase)
        if snapshot.display_ratio is not None:
            self._display_progress = smooth_progress(self._display_progress, snapshot.display_ratio)
            target_val = int(round(100 * self._display_progress))
            self._overall_value_label.setText(f"{target_val}%")
            self.progress_bar.setValue(target_val)
        if snapshot.eta_seconds is not None:
            self.detail_label.setText(_format_progress_status(
                status=str(snapshot.state.value),
                phase=snapshot.phase,
                run_id=snapshot.run_id if hasattr(snapshot, "run_id") else self._run_id,
                elapsed=snapshot.elapsed_seconds,
                next_action=snapshot.sub_message,
            ))

    def _on_cancel(self) -> None:

        self._is_canceled = True

        self.cancel_btn.setEnabled(False)

        self.cancel_btn.setText("Canceling...")
        self.detail_label.setText(_format_progress_status(
            status="cancelled",
            phase="interrupted",
            run_id=self._run_id,
            next_action="wait or retry",
        ))

        self.canceled.emit()

    def is_canceled(self) -> bool:

        return self._is_canceled

    def finish(self) -> None:

        self.progress_bar.setValue(100)
        self.detail_label.setText(_format_progress_status(
            status="done",
            run_id=self._run_id,
            next_action="close dialog",
        ))

        self.close()

class DualStageProgressWidget(QWidget):
    """Reusable dual-stage progress widget with global and current-stage gauges."""

    canceled = pyqtSignal()

    def __init__(self, parent=None, main_label: str = "", run_id: str | None = None, run_context: "Any | None" = None) -> None:
        super().__init__(parent)
        self._main_label = main_label
        self._run_context = run_context
        self._run_id = getattr(run_context, "run_id", run_id) if run_context else run_id
        self._run_id_visible = bool(self._run_id)
        self._start_time: float | None = None
        self._last_time: float | None = None
        self._last_evals: int = 0
        self._evals_per_sec: float = 0.0
        self._time_budget: float | None = None
        self._display_progress: float | None = None
        self._is_running = False
        self._is_canceled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        bars_layout = QVBoxLayout()
        bars_layout.setSpacing(6)

        self.overall_header = QLabel("Overall progress")
        self.overall_header.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-weight: 600;")
        
        self._overall_value_label = QLabel("0%")
        self._overall_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._overall_value_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-weight: 600;")
        
        overall_h_layout = QHBoxLayout()
        overall_h_layout.setContentsMargins(0, 0, 0, 0)
        overall_h_layout.addWidget(self.overall_header)
        overall_h_layout.addStretch()
        overall_h_layout.addWidget(self._overall_value_label)
        bars_layout.addLayout(overall_h_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())
        bars_layout.addWidget(self.progress_bar)

        self.stage_header = QLabel("Current stage")
        self.stage_header.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px; font-weight: 600;")
        self.stage_header.setVisible(False)
        
        self._stage_value_label = QLabel("")
        self._stage_value_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")
        self._stage_value_label.setVisible(False)
        
        # We add them to bars_layout, but wait, a QHBoxLayout won't hide automatically when children are hidden.
        # But since they are both hidden/shown together, we can keep the current vertical approach or use a container QWidget.
        # Let's use a simple approach: add them vertically if the design allows, or use QHBoxLayout.
        # Looking at the screenshot, they were vertical. Let's use QHBoxLayout to make it look clean like overall.
        stage_h_layout = QHBoxLayout()
        stage_h_layout.setContentsMargins(0, 0, 0, 0)
        stage_h_layout.addWidget(self.stage_header)
        stage_h_layout.addStretch()
        stage_h_layout.addWidget(self._stage_value_label)
        bars_layout.addLayout(stage_h_layout)

        self.sub_progress_bar = QProgressBar()
        self.sub_progress_bar.setFixedWidth(220)
        self.sub_progress_bar.setFixedHeight(6)
        self.sub_progress_bar.setRange(0, 100)
        self.sub_progress_bar.setTextVisible(False)
        self.sub_progress_bar.setStyleSheet(
            CertusTheme.get_progress_bar_style().replace(CertusTheme.PRIMARY, CertusTheme.INFO_TEXT)
        )
        self.sub_progress_bar.setVisible(False)
        bars_layout.addWidget(self.sub_progress_bar)

        self._anim_main = QPropertyAnimation(self.progress_bar, b"value")
        self._anim_main.setDuration(250)
        self._anim_main.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anim_sub = QPropertyAnimation(self.sub_progress_bar, b"value")
        self._anim_sub.setDuration(150)

        layout.addLayout(bars_layout)

        self.info_label = QLabel(self._main_label)
        self.info_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.info_label)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        layout.addWidget(self.detail_label)
        self.detail_label.setText(_format_progress_status(
            status="idle",
            run_id=self._run_id,
            next_action="start run",
        ))

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

    def start(self, phase: str | None = None) -> None:
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
        self.overall_header.setText("Overall progress")
        self._overall_value_label.setText("0%")
        self.stage_header.setVisible(False)
        self._stage_value_label.setVisible(False)
        self.info_label.setText("Starting...")
        self.detail_label.setText(_format_progress_status(
            status="starting",
            phase=phase or "initializing",
            run_id=self._run_id,
        ))

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
            target_val = 0
            if max_iter > 0:
                target_val = int(100 * iteration / max_iter)
            if evals > 0 and getattr(self, "_last_evals", None) is not None:
                eval_ratio = min(1.0, evals / max(1, self._last_evals + max(1, evals)))
                target_val = int(100 * (0.7 * (target_val / 100.0) + 0.3 * eval_ratio))
            target_val = min(100, max(0, target_val))
        self._display_progress = smooth_progress(self._display_progress, target_val / 100.0)
        target_val = int(round(100 * (self._display_progress if self._display_progress is not None else 0.0)))

        self._overall_value_label.setText(f"{target_val}%")
        if self.progress_bar.value() != target_val:
            if animate:
                self._anim_main.stop()
                self._anim_main.setStartValue(self.progress_bar.value())
                self._anim_main.setEndValue(target_val)
                self._anim_main.start()
            else:
                self._anim_main.stop()
                self.progress_bar.setValue(target_val)

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

        if phase:
            self.stage_header.setVisible(True)
            self._stage_value_label.setVisible(True)
            self._stage_value_label.setText(str(phase))
        else:
            self.stage_header.setVisible(False)
            self._stage_value_label.setVisible(False)

        parts = [self._format_time(elapsed)]
        if evals > 0:
            eval_str = f"{evals:,} evals"
            if self._evals_per_sec > 10:
                eval_str += f" ({int(self._evals_per_sec):,} eq/s)"
            parts.append(eval_str)
        if extra_info:
            parts.append(extra_info)
        if getattr(self, "_time_budget", None):
            remaining = max(0.0, float(self._time_budget) - elapsed)
            parts.append(f"ETA {self._format_time(remaining)}")
        self.info_label.setText(" | ".join(parts) if parts else "Working...")
        self.detail_label.setText(_format_progress_status(
            status="running",
            phase=phase,
            run_id=self._run_id,
            budget=self._time_budget,
            elapsed=elapsed,
            evals=evals,
        ))

    def stop(self, final_message: str = "Done") -> None:
        self._is_running = False
        if self.cancel_btn.isVisible():
            self.cancel_btn.setEnabled(False)
        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(100)
        self._overall_value_label.setText("100%")
        self.stage_header.setVisible(False)
        self._stage_value_label.setVisible(False)
        self.sub_progress_bar.setVisible(False)
        elapsed_seconds = None
        if self._start_time:
            elapsed_seconds = time.time() - self._start_time
            elapsed_txt = self._format_time(elapsed_seconds)
            self.info_label.setText(f"{final_message} • {elapsed_txt}")
        else:
            self.info_label.setText(final_message)
        if self._is_canceled:
            self.detail_label.setText(_format_progress_status(
                status="cancelled",
                phase="finalizing",
                run_id=self._run_id,
                next_action="review or resume",
            ))
            self.cancel_btn.setText("Cancelled")
        else:
            self.detail_label.setText(_format_progress_status(
                status="done",
                phase="finalizing",
                run_id=self._run_id,
                next_action="review results",
            ))
            self.cancel_btn.setText("Done")

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
        self.detail_label.setText(self._build_detail_status(status="idle", next_action="start run"))

    def _build_detail_status(
        self,
        status: str,
        phase: str = "",
        elapsed: float | None = None,
        evals: int = 0,
        next_action: str = "",
    ) -> str:
        parts = [f"status={status}"]
        if phase:
            parts.append(f"phase={phase}")
        if getattr(self, "_run_id", None):
            parts.append(f"run_id={self._run_id}")
        if self._time_budget is not None:
            parts.append(f"budget={self._format_time(self._time_budget)}")
        if elapsed is not None:
            parts.append(f"elapsed={self._format_time(elapsed)}")
        if evals > 0:
            parts.append(f"evals={evals:,}")
        if next_action:
            parts.append(f"next_action={next_action}")
        return " • ".join(parts)

    @staticmethod
    def _format_time(seconds: float) -> str:
        return _format_progress_duration(seconds)


class EnhancedProgressWidget(DualStageProgressWidget):
    """Backward-compatible alias for the reusable dual-stage progress widget."""
    pass


