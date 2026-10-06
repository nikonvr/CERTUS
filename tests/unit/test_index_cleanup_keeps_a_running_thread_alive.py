"""INDEX never drops the last reference to a thread that is still running (D23, R115).

`_cleanup_worker` -- run when the window closes, when a run starts and by the reset button -- asks the worker to
stop, waits 2 s, then set its thread attributes to None whatever the wait returned. The IR refinements that
follow PGLOBAL do not read the stop flag (section 5 of ETAT), so their thread can still run after the 2 s: the
attribute held the last Python reference to the QThread, dropping it deleted the running thread, and Qt aborts on
"QThread: Destroyed while thread ... is still running". The headless fixture hid it by holding every thread a
test starts.

A thread that does not stop in time is now kept until it ends, and its signals no longer reach the window: once
it ends it must not clear the references of a later run. The run is in a subprocess because the old code aborts
the process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_CLEAN_UP_A_THREAD_DEAF_TO_STOP = textwrap.dedent(
    """
    import logging, os, sys, time
    sys.path.insert(0, os.getcwd())
    from certus.core.certus_core import ensure_numba_cache_dir
    ensure_numba_cache_dir()
    from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QThread, pyqtSignal, pyqtSlot

    app = QCoreApplication([])
    from certus.ui import certus_index_ui_worker
    from certus.ui.certus_index_ui_worker import CertusIndexWorkerMixin


    class DeafToStop(QObject):
        finished = pyqtSignal(object)

        @pyqtSlot()
        def run(self):
            time.sleep(3.0)
            self.finished.emit(None)

        def stop(self):
            pass


    class Window:
        def __init__(self):
            self.logger = self._core_logger = logging.getLogger("index-test")
            self.calls_after_cleanup = []
            self._thread2 = self._worker2 = None
            thread, worker = QThread(), DeafToStop()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(self._on_finished)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(self._on_thread_finished)
            self._thread, self._worker = thread, worker
            thread.start()

        def _on_finished(self, result):
            self.calls_after_cleanup.append("_on_finished")

        def _on_thread_finished(self):
            self.calls_after_cleanup.append("_on_thread_finished")


    window = Window()
    time.sleep(0.2)
    CertusIndexWorkerMixin._cleanup_worker(window)
    assert window._thread is None and window._worker is None
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and certus_index_ui_worker._THREADS_STILL_RUNNING:
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.05)
    print("KEPT AFTER 10 s:", len(certus_index_ui_worker._THREADS_STILL_RUNNING))
    print("WINDOW CALLED AFTER CLEANUP:", window.calls_after_cleanup)
    sys.exit(0 if not certus_index_ui_worker._THREADS_STILL_RUNNING and not window.calls_after_cleanup else 2)
    """
)


@pytest.mark.unit
def test_cleanup_keeps_a_thread_that_ignores_stop_until_it_ends():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_FORCE_STDERR_LOGGING="1")
    proc = subprocess.run(
        [sys.executable, "-c", _CLEAN_UP_A_THREAD_DEAF_TO_STOP],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
