"""Closing DESIGN stops the threads it runs.

EventsManager.closeEvent looked for the optimization, needle and colour threads, and for the
evaluation and warm-up workers, on the manager (`getattr(self, "optim_thread", None)`) instead
of on the window, where they live: it never found one. Closing DESIGN during a run left the
thread running while the window went away. Found on 2026-09-29 by listing every guard a class
puts on a name it never holds.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN close", main_windows_only=True)


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


@pytest.mark.parametrize("slot", ["optim_thread", "needle_thread", "col_thread"])
def test_closing_design_stops_a_running_worker_thread(design_app, slot) -> None:
    from PyQt6.QtCore import QThread
    from PyQt6.QtGui import QCloseEvent

    thread = QThread()
    thread.start()
    setattr(design_app, slot, thread)
    try:
        design_app.events_manager.closeEvent(QCloseEvent())

        assert not thread.isRunning()
    finally:
        setattr(design_app, slot, None)
        thread.quit()
        thread.wait(5000)


@pytest.mark.parametrize("slot", ["eval_worker", "warmup_worker"])
def test_closing_design_interrupts_a_running_worker(design_app, slot) -> None:
    from PyQt6.QtCore import QThread
    from PyQt6.QtGui import QCloseEvent

    class _SpinsUntilInterrupted(QThread):
        def run(self) -> None:
            while not self.isInterruptionRequested():
                self.msleep(5)

    previous = getattr(design_app, slot)
    if previous is not None:
        previous.wait(60000)
    worker = _SpinsUntilInterrupted()
    worker.start()
    setattr(design_app, slot, worker)
    try:
        design_app.events_manager.closeEvent(QCloseEvent())

        assert not worker.isRunning()
    finally:
        setattr(design_app, slot, None)
        worker.requestInterruption()
        worker.wait(5000)
