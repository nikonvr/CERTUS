"""Esc stops a run only after a deliberate confirmation, in FIELD and INDEX SPLINE too (audit UX A07, ETAT D83).

DESIGN, INDEX, RE, STRAT and both METAL send Esc and their Stop button through `confirm_stop_with_timeout`
(tests/ui/test_ux_stop_confirmation.py): Esc is a reflex key, and one unmeant press must not end a long run.
Measured 2026-10-02, FIELD bound Esc straight to `worker_manager.stop_all()`, and INDEX SPLINE bound Esc and its
"Stop" button straight to `_on_stop`, which raises the stop flag of the worker: neither asked anything.

Now both ask, and neither asks when nothing is running (an idle Esc must stay silent).

Measured the same day on a real FIELD optimisation: after the stop, no worker ran any more but the window stayed in its
running state (both calculation buttons disabled, the wait cursor still set, the status line still "optimization
running"), because a worker that stops on request returns without a result and nothing put the window back. The last
tests pin that recovery.
"""

from __future__ import annotations

import time

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QApplication, QMessageBox


class _RunningWorker:
    """Duck-types what the worker manager and the close guard trust: it is running, and it can be stopped."""

    def __init__(self) -> None:
        self.stopped = 0

    def isRunning(self) -> bool:
        return True

    def stop(self) -> None:
        self.stopped += 1

    def requestInterruption(self) -> None:
        pass


def _field(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    return CertusFieldApp()


def _spline(qapp):
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    return CertusIndexSplineApp()


def _press_escape(win) -> int:
    shortcuts = [s for s in win.findChildren(QShortcut) if s.key().toString() == "Esc"]
    assert shortcuts, "no Esc shortcut on the window"
    for shortcut in shortcuts:
        shortcut.activated.emit()
    return len(shortcuts)


def _run_field(win):
    worker = _RunningWorker()
    win.worker_manager._active_workers = [worker]
    return worker, lambda: worker.stopped


def _run_spline(win):
    win.btn_stop.setEnabled(True)
    return None, lambda: int(win._stop_event.is_set())


APPLICATIONS = [(_field, _run_field), (_spline, _run_spline)]
IDS = ["FIELD", "INDEX_SPLINE"]


@pytest.fixture
def asked(monkeypatch):
    """Records the confirmation asked and answers it as the test says; a real message box would block."""
    state = {"calls": 0, "answer": False}

    def fake(_parent, timeout_sec=10):
        state["calls"] += 1
        return state["answer"]

    for module in (
        "certus.ui.certus_field_ui",
        "certus.ui.certus_index_spline_eventsextras_mixin",
    ):
        monkeypatch.setattr(f"{module}.confirm_stop_with_timeout", fake, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    return state


@pytest.mark.parametrize(("make", "run"), APPLICATIONS, ids=IDS)
def test_esc_during_a_run_asks_and_a_refusal_keeps_the_run(qapp, asked, make, run) -> None:
    win = make(qapp)
    try:
        _, stopped = run(win)
        asked["answer"] = False

        _press_escape(win)

        assert asked["calls"] >= 1, "Esc stopped a running computation without asking"
        assert stopped() == 0, "the operator kept the run and it was stopped anyway"
    finally:
        win.worker_manager._active_workers = []
        win.close()


@pytest.mark.parametrize(("make", "run"), APPLICATIONS, ids=IDS)
def test_esc_during_a_run_stops_it_once_the_operator_confirms(qapp, asked, make, run) -> None:
    win = make(qapp)
    try:
        _, stopped = run(win)
        asked["answer"] = True

        _press_escape(win)

        assert stopped() >= 1, "the operator confirmed the stop and nothing was stopped"
    finally:
        win.worker_manager._active_workers = []
        win.close()


@pytest.mark.parametrize(("make", "run"), APPLICATIONS, ids=IDS)
def test_esc_on_an_idle_window_asks_nothing(qapp, monkeypatch, make, run) -> None:
    """The real confirmation is used here: it must return before opening any box when nothing runs."""
    boxes: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: boxes.append(self.text()) or 0)
    win = make(qapp)
    try:
        _press_escape(win)

        assert not boxes, f"Esc on an idle window opened a box: {boxes}"
    finally:
        win.close()


# ---------------------------------------------------------------------------
# The window after a stop
# ---------------------------------------------------------------------------


class _StoppedWorker:
    """A worker thread that ended without reporting anything, as one stopped on request does."""

    _result_reported = False


def _put_in_running_state(win) -> None:
    for button in (win.btn_calc, win.btn_opt, win.btn_mc):
        button.setEnabled(False)
    win._is_running = True
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)


def _is_back_to_rest(win) -> bool:
    return (
        win.btn_calc.isEnabled()
        and win.btn_opt.isEnabled()
        and win.btn_mc.isEnabled()
        and not win._is_running
        and QApplication.overrideCursor() is None
    )


def test_a_worker_that_ended_without_a_result_puts_the_window_back_to_rest(qapp) -> None:
    win = _field(qapp)
    try:
        _put_in_running_state(win)
        worker = _StoppedWorker()
        win.worker = worker

        win._on_worker_thread_ended(worker)

        assert _is_back_to_rest(win)
        assert win.field_opt_status.text() == "Stopped"
    finally:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()


def test_a_worker_that_reported_its_result_is_left_to_the_normal_path(qapp) -> None:
    """The thread-ended hook fires after EVERY worker: it must not touch a window that was handled already."""
    win = _field(qapp)
    try:
        _put_in_running_state(win)
        worker = _StoppedWorker()
        worker._result_reported = True
        win.worker = worker

        win._on_worker_thread_ended(worker)

        assert not win.btn_opt.isEnabled(), "a worker that had reported was handled a second time"
        assert QApplication.overrideCursor() is not None
    finally:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.btn_calc.setEnabled(True)
        win.close()


def test_an_older_thread_ending_after_a_newer_worker_started_does_not_reset_the_window(qapp) -> None:
    """A synthesis starts the next worker while the previous thread is still ending."""
    win = _field(qapp)
    try:
        _put_in_running_state(win)
        older, newer = _StoppedWorker(), _StoppedWorker()
        win.worker = newer

        win._on_worker_thread_ended(older)

        assert not win.btn_opt.isEnabled(), "the window was reset under the run that had just started"
    finally:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.btn_calc.setEnabled(True)
        win.close()


def test_stopping_a_real_optimisation_leaves_a_usable_window(qapp, asked) -> None:
    """End to end, with the real worker thread: the symptom measured on 2026-10-02."""
    asked["answer"] = True
    win = _field(qapp)
    try:
        win.show()
        win.btn_opt.click()
        deadline = time.monotonic() + 60
        while win.running_worker_count() == 0 and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.02)

        win.request_stop()

        while win.running_worker_count() > 0 and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.02)
        for _ in range(50):  # the thread-ended signal is queued behind the event loop
            QApplication.processEvents()
            time.sleep(0.02)

        assert win.running_worker_count() == 0, "the worker did not stop within 60 s"
        assert _is_back_to_rest(win), (
            win.btn_calc.isEnabled(), win.btn_opt.isEnabled(), win._is_running, QApplication.overrideCursor()
        )
    finally:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()
