"""Shared Qt fixtures for UI tests.

Provides a single, session-scoped QApplication to prevent segfaults caused by
repeated QApplication creation/destruction across test files.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication shared by all UI tests."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["certus-test"])
    return app
    # Do NOT call app.quit() — let the process handle teardown.
