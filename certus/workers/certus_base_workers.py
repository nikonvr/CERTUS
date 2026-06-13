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

class WorkerSignals(QObject):
    """

    Thread-safe signals for worker-to-GUI communication.

    Used by GenericWorker and other workers to emit signals

    from background threads to the main GUI thread.

    Signals:

        started: Emitted when the worker starts

        finished: Emitted when the worker finishes (with result)

        error: Emitted on error (tuple or str)

        progress: Emitted to update progress (int, str)

        update_stats: Emitted to update statistics (key, value)

        result: Emitted with the computation result

    """

    started = pyqtSignal()

    finished = pyqtSignal(object)

    error = pyqtSignal(object)  # Was tuple, now object to support str tracebacks

    progress = pyqtSignal(int, str)
    progress_sub = pyqtSignal(int, int, str, str)

    update_stats = pyqtSignal(str, object)  # "Key", Value

    result = pyqtSignal(object)

    live = pyqtSignal(object)

class GenericWorker(QThread):
    """

    Generic worker thread for running arbitrary functions in background.

    """

    def __init__(self, func: Callable, *args, **kwargs) -> None:

        super(GenericWorker, self).__init__()

        self.func = func

        self.args = args

        self.kwargs = kwargs

        self.signals = WorkerSignals()

        self._stop = False

    def run(self) -> None:

        self.signals.started.emit()

        try:
            if "stop_check" in self.kwargs:
                self.kwargs["stop_check"] = lambda: self._stop

            res = self.func(*self.args, **self.kwargs)

            if not self._stop:
                self.signals.result.emit(res)

                self.signals.finished.emit(res)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            # Send full traceback for better debugging

            tb_str = "".join(traceback.format_tb(e.__traceback__))

            self.signals.error.emit((type(e), e, tb_str))

    def stop(self) -> None:

        self._stop = True

class CertusWorkerBase(QThread):
    """

    Base worker class with standard signals and stop management.

    Provides:

    - Standard signals (finished, error, progress, stats_update)

    - Thread-safe stop request mechanism

    - Progress throttling to reduce GUI overhead

    - Automatic exception handling with traceback

    Subclasses should override `do_work()` method.

    Example:

        >>> class MyWorker(CertusWorkerBase):

        ...     def do_work(self):

        ...         for i in range(100):

        ...             if self.is_stop_requested():

        ...                 return None

        ...             self.emit_progress_throttled(i, f"Step {i}")

        ...         return result

    """

    finished = pyqtSignal(object)

    error = pyqtSignal(object)

    progress = pyqtSignal(int, str)
    progress_sub = pyqtSignal(int, int, str, str)

    stats_update = pyqtSignal(str, int)

    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self._stop_requested = False

        self._last_progress_time = 0.0

        self._progress_interval = 0.1  # 100ms minimum between progress updates

    def request_stop(self) -> None:
        """Request the worker to stop. Thread-safe."""

        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        """Check if stop was requested. Thread-safe."""

        return self._stop_requested

    def emit_stats(self, counter_type: str, increment: int = 1) -> None:
        """Emit stats update signal."""

        self.stats_update.emit(counter_type, increment)

    def do_work(self) -> Any:
        """

        Override this method in subclasses to perform actual work.

        Returns:

            Result object to be emitted via finished signal

        """

        raise NotImplementedError("Subclasses must implement do_work()")

    def run(self) -> None:
        """Thread entry point. Handles exceptions and emits signals."""

        self._stop_requested = False

        self._last_progress_time = 0.0

        try:
            result = self.do_work()

            if not self._stop_requested:
                self.finished.emit(result)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            import traceback

            self.error.emit((type(e), e, traceback.format_exc()))

