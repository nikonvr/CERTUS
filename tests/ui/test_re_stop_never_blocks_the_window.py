"""Stopping an RE run returns at once and keeps the worker until it has finished (audit 2026-11-15, M-L6c).

``stop_optim`` called ``rw.wait(300000)`` on the GUI thread: the window froze for up to five minutes, and on timeout the
reference of a QThread still running was dropped. The stop is now a request: the worker ends cooperatively and its
``finished`` signal runs ``_on_re_done``, exactly like a normal end.
"""

from __future__ import annotations

import importlib

import pytest

MODULE = "certus.ui.certus_re_workers_mixin"


class _StillFinishingWorker:
    """A worker that has heard the stop but is still inside its current step."""

    def __init__(self) -> None:
        self.stop_requests = 0
        self.waits: list[int] = []

    def isRunning(self) -> bool:
        return True

    def request_stop(self) -> None:
        self.stop_requests += 1

    def requestInterruption(self) -> None:
        pass

    def wait(self, ms: int = 0) -> bool:
        self.waits.append(ms)
        return False


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    yield win
    win._re_worker = None
    win.eval_worker = None
    win.close()


def test_stop_asks_the_worker_and_returns_without_waiting(re_window, monkeypatch) -> None:
    mod = importlib.import_module(MODULE)
    monkeypatch.setattr(mod, "confirm_stop_with_timeout", lambda *_a, **_k: True)
    worker = _StillFinishingWorker()
    re_window._re_worker = worker
    re_window.eval_worker = None

    re_window.stop_optim()

    assert worker.stop_requests == 1
    assert worker.waits == [], f"the GUI thread waited on the RE worker: {worker.waits} ms"
    assert re_window._re_worker is worker, "the reference of a running QThread was dropped"
