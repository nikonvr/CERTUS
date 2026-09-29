"""A failed DESIGN optimization tells the user why, in a dialog.

Until 2026-07-03 the orchestrator opened the warning itself. 06a1083 moved it behind
`hasattr(self.ui, "show_error_dialog")` to keep Qt out of the orchestrator, and gave the
method to OptimizationManager, not to the window: the guard was always false, and a failed
run ended with a line in the log only. The unit test of that change passed, on a MagicMock,
which has every attribute.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN failure dialog", main_windows_only=True)


def test_a_failed_optimization_opens_the_guided_warning(qapp, monkeypatch) -> None:
    from PyQt6.QtWidgets import QMessageBox

    from certus.ui.certus_design_ui import CertusDesignApp

    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *a, **k: shown.append((title, text)))
    app = CertusDesignApp()
    app._workflow_stopped = False

    app.orchestrator._on_optim_done({"ok": False, "error": "Target thickness cannot be reached."})

    [(title, text)] = shown
    assert title == "Optimization Failed"
    assert "Target thickness cannot be reached." in text
