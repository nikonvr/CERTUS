"""D41: closing INDEX, INDEX SPLINE, RE, METAL or DESIGN during a computation asks first, as STRAT and FIELD do.

Their own closeEvent stopped the computation threads before calling the base one, whose question then found nothing
running: the window's X discarded a run without a word. Those threads are not registered with `worker_manager`; each
module now names them (`_COMPUTATION_THREADS`), the shared count sees them, and its closeEvent asks before stopping.
Decided by the owner on 2026-10-06.
"""

from __future__ import annotations

import importlib
import threading

import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QCloseEvent


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "close during a computation", main_windows_only=True)


class _Busy(QThread):
    """A computation that runs until released."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def run(self) -> None:
        self.release.wait(20.0)

    def stop(self) -> None:  # what the modules call on their workers
        self.release.set()

    request_stop = stop


WINDOWS = [
    ("certus.ui.certus_index_ui", "CertusIndexApp", "_thread"),
    ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp", "_worker"),
    ("CERTUS_RE", "CertusREApp", "_re_worker"),
    ("certus.metal.certus_metal_single_app", "CertusMetalSingleApp", "optimization_thread"),
    ("certus.metal.certus_metal_bilayer_app", "CertusMetalBilayerApp", "optimization_thread"),
    ("certus.ui.certus_design_ui", "CertusDesignApp", "optim_thread"),
]


@pytest.mark.parametrize(("module", "cls", "attribute"), WINDOWS, ids=[w[1] for w in WINDOWS])
def test_closing_during_a_computation_asks_and_keep_running_keeps_it(qapp, monkeypatch, module, cls, attribute):
    window = getattr(importlib.import_module(module), cls)()
    asked: list = []
    monkeypatch.setattr(type(window), "confirm_destructive", lambda self, *a, **k: asked.append(a) or False)
    busy = _Busy()
    busy.start()
    setattr(window, attribute, busy)
    try:
        event = QCloseEvent()
        window.closeEvent(event)

        assert len(asked) == 1, "the window closed a running computation without asking"
        assert not event.isAccepted()
        assert busy.isRunning()
    finally:
        busy.release.set()
        busy.wait(5000)
        setattr(window, attribute, None)
