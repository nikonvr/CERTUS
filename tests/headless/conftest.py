"""Keep each headless test's Qt objects and background work inside that test."""

import threading
import time

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QThread, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow


# On a join timeout, keep the owners alive and stop the suite. Destroying them or
# continuing with the next test would turn a useful error into a native crash.
# 180 s, not 30: INDEX's second stage refines after PGLOBAL without reading the stop
# flag, so teardown waits for its natural end. Under CPU load that outlived 30 s and
# stopped the suite after test_index (measured 2026-09-26; without load: 9 passed).
_unjoined_resources = []
_JOIN_TIMEOUT_S = 180.0


@pytest.fixture(autouse=True)
def headless_lifecycle(qapp, monkeypatch):
    """Join work before deleting windows, including after an assertion failure.

    qapp retains the session's QApplication even though the tests use instance().
    Track starts rather than traversing QObject children for QThreads: some
    workers have no parent, and a QObject worker's thread is a separate object.
    """
    previous_windows = set(QApplication.topLevelWidgets())
    qt_threads = []
    python_threads = []
    callbacks_enabled = True
    qt_start = QThread.start
    python_start = threading.Thread.start
    single_shot = QTimer.singleShot

    def track_qt_start(thread, *args, **kwargs):
        qt_threads.append(thread)  # Retain even if a window clears its reference.
        return qt_start(thread, *args, **kwargs)

    def track_python_start(thread, *args, **kwargs):
        python_threads.append(thread)
        return python_start(thread, *args, **kwargs)

    def scoped_single_shot(*args):
        # Preserve Qt's timing/overloads during the test. A contextless lambda
        # can otherwise run in the NEXT test and touch an already deleted widget.
        callback = args[-1]
        # Keep Qt's receiver affinity and automatic disconnection for bound
        # QObject methods. Only contextless GUI callbacks need the scope guard.
        if isinstance(getattr(callback, "__self__", None), QObject) or QThread.currentThread() != qapp.thread():
            return single_shot(*args)

        def invoke():
            if callbacks_enabled:
                callback()

        return single_shot(*args[:-1], invoke)

    monkeypatch.setattr(QThread, "start", track_qt_start)
    monkeypatch.setattr(threading.Thread, "start", track_python_start)
    monkeypatch.setattr(QTimer, "singleShot", scoped_single_shot)

    yield

    callbacks_enabled = False
    windows = [w for w in QApplication.topLevelWidgets() if w not in previous_windows]
    deadline = time.monotonic() + _JOIN_TIMEOUT_S

    def remaining_ms():
        return max(0, int((deadline - time.monotonic()) * 1000))

    def join_timeout(label):
        _unjoined_resources.append((qapp, windows, qt_threads, python_threads))
        pytest.exit(f"Headless teardown: {label} did not join within {_JOIN_TIMEOUT_S:g}s", returncode=1)

    def request_stop(worker):
        if not isinstance(worker, QObject) or sip.isdeleted(worker):
            return
        # These worker methods only set cooperative flags/events. Do not invoke
        # a window's Stop action: it can open a confirmation dialog.
        for name in ("request_stop", "stop"):
            stop = getattr(worker, name, None)
            if callable(stop):
                stop()
                break

    qt_count = python_count = 0
    while True:
        for window in windows:
            if sip.isdeleted(window):
                continue
            if hasattr(window, "_workflow_stopped"):
                window._workflow_stopped = True
            for name, value in vars(window).copy().items():
                if "worker" in name:
                    request_stop(value)

        # quit() also handles QObject workers whose queued thread.quit slot has
        # not run yet. A result signal is not a join, nor is isRunning() alone.
        while qt_count < len(qt_threads):
            thread = qt_threads[qt_count]
            qt_count += 1
            if sip.isdeleted(thread):
                continue
            request_stop(thread)
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(remaining_ms()):
                join_timeout(type(thread).__name__)

        while python_count < len(python_threads):
            thread = python_threads[python_count]
            python_count += 1
            thread.join(remaining_ms() / 1000)
            if thread.is_alive():
                join_timeout(thread.name)

        # Deliver completion callbacks while their widgets still exist. They
        # may start a follow-up worker, which must be joined in the next pass.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
        if qt_count == len(qt_threads) and python_count == len(python_threads):
            break
        if not remaining_ms():
            join_timeout("completion callbacks")

    # Include popups created by completion slots, but preserve earlier tests'
    # session fixtures. Closing alone only hides most CERTUS windows (D11).
    windows = [w for w in QApplication.topLevelWidgets() if w not in previous_windows]
    # Destroy the main windows before their menus/popups. Pyqtgraph's ViewBox
    # destruction still uses its menus; deleting every top-level widget in
    # Qt's unspecified enumeration order can abort inside the main destructor.
    windows.sort(key=lambda w: not isinstance(w, QMainWindow))
    for window in windows:
        if not sip.isdeleted(window):
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert all(sip.isdeleted(w) for w in windows), "Headless windows survived teardown"
