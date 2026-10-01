"""Closing FIELD or STRAT mid-run asks first — with a REAL worker, not an injected one.

`confirm_close_during_run` counts the workers registered with `worker_manager`, and until
2026-09-28 nothing registered any: `register_worker` had no caller outside its own module.
The guard's own test injects a fake into `_active_workers`, so it passed while a STRAT run
(up to 2 h 39) could still be discarded by the window's X without a question.
"""

from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, QThread, pyqtSignal

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "close guard", main_windows_only=True)


class _Signals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(int, str)
    plot = pyqtSignal(object)


class _SlowFieldWorker(QThread):
    """Stands in for FieldWorkerThread: runs until released, like a long optimisation."""

    def __init__(self, request):
        super().__init__()
        self.request = request
        self.signals = _Signals()
        self.release = threading.Event()

    def run(self) -> None:
        self.release.wait(10.0)


def test_closing_field_during_a_run_asks_first(qapp, monkeypatch) -> None:
    from PyQt6.QtGui import QCloseEvent

    import certus.ui.certus_field_workers_mixin as workers
    from certus.ui.certus_field_ui import CertusFieldApp

    monkeypatch.setattr(workers, "FieldWorkerThread", _SlowFieldWorker)
    win = CertusFieldApp()
    asked = []
    monkeypatch.setattr(type(win), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False)

    win._start_worker(workers.FieldWorkerRequest(action="calculate", params=win._get_params()))
    try:
        event = QCloseEvent()
        win.closeEvent(event)
        assert asked, "FIELD closed during a run without asking"
        assert not event.isAccepted()
    finally:
        win.worker.release.set()
        win.worker.wait(10000)
        qapp.processEvents()


@pytest.mark.parametrize(("path", "function"), [
    ("certus/ui/certus_strat_ui_worker.py", "run_workflow"),
    ("certus/ui/certus_strat_ui_state.py", "load_external_strategies"),
    ("certus/ui/certus_field_workers_mixin.py", "_start_worker"),
])
def test_each_run_registers_its_worker_before_starting_it(path, function) -> None:
    """STRAT's runs are too heavy to start here: the wiring is checked in the source."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    calls = [ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)]
    assert "self.worker.start" in calls
    assert "self.worker_manager.register_worker" in calls, f"{function} starts a worker the close guard never sees"
    register = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.worker_manager.register_worker")
    start = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.worker.start")
    assert register.lineno < start.lineno
