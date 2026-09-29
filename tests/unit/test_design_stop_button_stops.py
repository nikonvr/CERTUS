"""DESIGN's STOP stops the run.

WorkerManager.stop_optim asked for confirmation with confirm_stop_with_timeout(self): the
manager, not the window. QMessageBox refuses a parent that is not a QWidget, so every STOP,
the button as well as Esc, raised TypeError before anything was stopped — from the split of
the window into managers (c79316b, 2026-06-13) to 2026-09-29. The progress bar was never
told either: its guard looked for the widget on the manager.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN stop button", main_windows_only=True)


def test_stop_now_stops_the_workflow_and_says_so(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from certus.ui.certus_design_ui import CertusDesignApp

    def click_stop_now(box) -> int:
        [stop] = [button for button in box.buttons() if button.text() == "Stop Now"]
        stop.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", click_stop_now)
    app = CertusDesignApp()
    shown = []
    monkeypatch.setattr(app.progress_widget, "stop", lambda message="": shown.append(message))

    app.stop_optim()

    assert app._workflow_stopped is True
    assert shown == ["Cancelled"]
