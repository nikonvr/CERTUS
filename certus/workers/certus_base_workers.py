import traceback
from collections.abc import Callable
import numpy as np
import pandas as pd
import pyqtgraph as pg
import pyqtgraph.exporters  # pylint: disable=unused-import
from PyQt6.QtCore import (
    QObject,
    QThread,
    pyqtSignal,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
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
