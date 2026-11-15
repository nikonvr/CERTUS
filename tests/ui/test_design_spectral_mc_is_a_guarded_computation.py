"""The spectral Monte Carlo of DESIGN is a computation like the others (audit 2026-11-15, M-L5f).

Its button stayed enabled while it ran, so a second run could be started over the first, and its thread was unknown to
the close guard and to the cleanup at close.
"""

from __future__ import annotations

import pytest
from PyQt6.QtGui import QCloseEvent


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN audit guards", main_windows_only=True)


@pytest.fixture
def design(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


class _RunningThread:
    def isRunning(self) -> bool:
        return True


def test_the_spectral_monte_carlo_button_is_disabled_while_the_window_is_busy(design) -> None:
    design._update_busy_ui(True)
    assert design.spectral_mc_btn.isEnabled() is False
    design._update_busy_ui(False)
    assert design.spectral_mc_btn.isEnabled() is True


def test_the_close_guard_counts_a_running_spectral_monte_carlo(design) -> None:
    design.smc_thread = _RunningThread()
    try:
        assert design.running_worker_count() == 1
    finally:
        design.smc_thread = None


def test_closing_stops_the_spectral_monte_carlo_thread(design, monkeypatch) -> None:
    import certus.core.certus_design_worker_utils as worker_utils

    stopped: list[object] = []
    monkeypatch.setattr(worker_utils, "stop_qt_worker_thread_safely", lambda thread, *_a, **_k: stopped.append(thread))
    thread = _RunningThread()
    design.smc_thread = thread
    try:
        design.events_manager.closeEvent(QCloseEvent())
    finally:
        design.smc_thread = None

    assert thread in stopped
