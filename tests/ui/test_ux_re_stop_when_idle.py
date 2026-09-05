"""RE must not open a stop dialog when nothing is running (step 2.12).

stop_optim() opened with `if not confirm_stop_with_timeout(self)` before testing
whether anything was actually running. Esc is bound to stop in every module and
it is a reflex key, so pressing it on an idle window opened a box counting down
the interruption of nothing - and then answering itself.

The information was already in the function: three lines below the dialog it
computes `re_was_running = rw is not None and rw.isRunning()`. It was simply
used too late.

RE drives TWO workers - _re_worker and eval_worker - and stop_optim stops both,
so the guard has to consider both. Gating on _re_worker alone would have made a
running evaluation unstoppable, which is worse than the defect.
"""

from __future__ import annotations

import pytest

MODULE = "certus.ui.certus_re_workers_mixin"


class _FakeWorker:
    """Runs once, then stops - enough for stop_optim to walk its normal path."""

    def __init__(self) -> None:
        self._running = True

    def isRunning(self) -> bool:
        return self._running

    def request_stop(self) -> None:
        self._running = False

    def requestInterruption(self) -> None:
        self._running = False

    def wait(self, _ms: int = 0) -> bool:
        self._running = False
        return True

    def quit(self) -> None:
        self._running = False


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    yield win
    win.close()


def test_no_dialog_when_nothing_is_running(re_window, monkeypatch) -> None:
    """An idle Esc must be silent, not open a countdown over nothing."""
    import importlib

    mod = importlib.import_module(MODULE)
    calls = []
    monkeypatch.setattr(mod, "confirm_stop_with_timeout", lambda *a, **k: calls.append(a) or True)

    re_window._re_worker = None
    re_window.eval_worker = None

    re_window.stop_optim()

    assert not calls, "RE asked to confirm the interruption of nothing"


@pytest.mark.parametrize("attr", ["_re_worker", "eval_worker"])
def test_dialog_still_opens_for_each_worker(re_window, monkeypatch, attr) -> None:
    """Both workers must remain stoppable: the guard must not over-reach."""
    import importlib

    mod = importlib.import_module(MODULE)
    calls = []
    monkeypatch.setattr(mod, "confirm_stop_with_timeout", lambda *a, **k: calls.append(a) or False)

    re_window._re_worker = None
    re_window.eval_worker = None
    setattr(re_window, attr, _FakeWorker())

    re_window.stop_optim()

    assert calls, f"a running {attr} could not be stopped: the dialog never opened"


# --- STRAT uses the opt-in probe instead of an inline guard -------------------
#
# _active_worker_threads is STRAT's complete registry, so it can answer with
# certainty. confirm_stop_with_timeout only stays silent on an explicit False:
# a window that cannot answer keeps its dialog, because an over-reaching guard
# would make a running computation unstoppable.


def test_strat_reports_idle_when_no_thread_runs(qapp) -> None:
    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    try:
        win._active_worker_threads = []
        assert win.has_running_computation() is False
    finally:
        win.close()


def test_strat_reports_busy_while_a_thread_runs(qapp) -> None:
    from certus.ui.certus_strat_ui import CertusStratApp

    win = CertusStratApp()
    try:
        win._active_worker_threads = [_FakeWorker()]
        assert win.has_running_computation() is True
    finally:
        win._active_worker_threads = []
        win.close()


def test_the_dialog_stays_for_a_window_that_cannot_answer(qapp) -> None:
    """No probe means no silence: the default must never lose the stop."""
    from PyQt6.QtWidgets import QMessageBox, QWidget

    from certus.ui.certus_ui_utils import confirm_stop_with_timeout

    shown = []
    original = QMessageBox.exec
    try:
        QMessageBox.exec = lambda self: shown.append(True) or 0
        parent = QWidget()  # no has_running_computation at all
        confirm_stop_with_timeout(parent, timeout_sec=30)
        parent.deleteLater()
    finally:
        QMessageBox.exec = original

    assert shown, "a window without the probe lost its stop dialog"
