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
from certus.utils.certus_progress_tracker import (
    ProgressSnapshot,
    StepState,
    ProgressCallback,
    build_progress_snapshot,
    build_progress_callback,
)
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
    progress_snapshot = pyqtSignal(object)

    update_stats = pyqtSignal(str, object)  # "Key", Value

    result = pyqtSignal(object)

    live = pyqtSignal(object)

class GenericWorker(QThread):
    """

    Generic worker thread for running arbitrary functions in background.

    """

    def __init__(self, func: Callable, *args, **kwargs) -> None:

        super().__init__()

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
