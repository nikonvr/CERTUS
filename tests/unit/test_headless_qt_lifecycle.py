"""Exercise the real headless fixture across a pytest test boundary."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


_SCENARIO = '''
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEventLoop, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
import pyqtgraph as pg

state = {}

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    state["sentinel"] = QWidget()
    yield app
    state["sentinel"].close()

class EarlyResult(QThread):
    result = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def request_stop(self):
        self.release.set()

    def run(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.release.wait)
            self.result.emit()
            future.result()
        state["executor_joined"] = True

class SeparateWorker(QObject):
    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def stop(self):
        self.release.set()

    def run(self):
        self.release.wait()

def test_01_leave_work_after_result(qapp):
    window = QMainWindow()
    plots = pg.GraphicsLayoutWidget()
    plots.addPlot(name="first").plot([1, 2])
    plots.addPlot(name="second").plot([2, 1])
    window.setCentralWidget(plots)
    state["window"] = window
    thread = EarlyResult()
    window.eval_worker = thread
    state["thread"] = thread
    loop = QEventLoop()
    thread.result.connect(loop.quit)
    thread.start()
    loop.exec()
    assert thread.isRunning()  # Result delivered before run()/executor exit.

    window.worker = SeparateWorker()
    window.optimization_thread = QThread()
    window.worker.moveToThread(window.optimization_thread)
    window.optimization_thread.started.connect(window.worker.run)
    window.optimization_thread.finished.connect(window.worker.deleteLater)
    window.optimization_thread.start()
    state["separate_thread"] = window.optimization_thread

    auxiliary = threading.Thread(target=lambda: thread.release.wait())
    state["auxiliary"] = auxiliary
    auxiliary.start()
    QTimer.singleShot(0, lambda: state.update(late_callback=True))
    if FAIL_BODY:
        pytest.fail("intentional body failure")

def test_02_next_test_is_clean(qapp):
    try:
        qapp.processEvents()
        assert not state["thread"].isRunning(), "QThread leaked across tests"
        assert not state["separate_thread"].isRunning()
        assert not state["auxiliary"].is_alive()
        assert state.get("executor_joined")
        assert sip.isdeleted(state["window"]), "window was only hidden"
        assert not state.get("late_callback"), "callback leaked across tests"
        assert not sip.isdeleted(state["sentinel"]), "session window was destroyed"
    finally:
        # Make the negative control safe too: failure must be an assertion,
        # never a live QThread destroyed when this subprocess exits.
        state["thread"].request_stop()
        state["thread"].wait(5000)
        window = state["window"]
        if not sip.isdeleted(window):
            window.worker.stop()
        state["separate_thread"].quit()
        state["separate_thread"].wait(5000)
        state["auxiliary"].join(5)
'''


@pytest.mark.parametrize("fail_body", [False, True])
@pytest.mark.parametrize("isolated", [False, True])
def test_headless_teardown_joins_before_deleting(tmp_path, isolated, fail_body):
    """The same scenario fails without isolation, even when the body passes."""
    if isolated:
        fixture = Path(__file__).parents[1] / "headless" / "conftest.py"
        (tmp_path / "conftest.py").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_boundary.py").write_text(
        f"FAIL_BODY = {fail_body!r}\n" + _SCENARIO, encoding="utf-8"
    )
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTEST_ADDOPTS="")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", str(tmp_path)],
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=30,
    )
    output = run.stdout + run.stderr
    assert run.returncode == (1 if fail_body or not isolated else 0), output
    if isolated:
        assert ("1 failed, 1 passed" if fail_body else "2 passed") in output, output
    else:
        assert "QThread leaked across tests" in output, output
        assert ("2 failed" if fail_body else "1 failed, 1 passed") in output, output
