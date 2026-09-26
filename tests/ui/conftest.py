"""Shared Qt fixtures for UI tests.

Provides a single, session-scoped QApplication to prevent segfaults caused by
repeated QApplication creation/destruction across test files.

Every main window a test builds is destroyed when that test ends, and every main
window a module-scoped fixture builds, when its module ends. Closing a CERTUS
window only hides it (D11): each one left behind made the next construction
slower, up to minutes per test late in the suite.
"""
from __future__ import annotations

import sys

import pytest
from qt_lifecycle import qt_lifecycle


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication shared by all UI tests."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["certus-test"])
    return app
    # Do NOT call app.quit() — let the process handle teardown.


@pytest.fixture(scope="module", autouse=True)
def _module_qt_lifecycle(qapp):
    """What the module's fixtures built and started ends with the module."""
    with pytest.MonkeyPatch.context() as patch:
        yield from qt_lifecycle(qapp, patch, "UI module", main_windows_only=True)


@pytest.fixture(autouse=True)
def _test_qt_lifecycle(_module_qt_lifecycle, qapp, monkeypatch):
    """What the test built and started ends with the test."""
    yield from qt_lifecycle(qapp, monkeypatch, "UI test", main_windows_only=True)
