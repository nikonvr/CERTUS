"""Headless GUI smoke tests for the primary CERTUS applications.

These tests construct the main window of each application class on an offscreen
platform to verify structural wiring and ensure no crashes occur during startup.
"""

from __future__ import annotations

import pytest
import sys
from pathlib import Path

# Add root directory to sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.unit
def test_certus_design_app_constructs_headless(monkeypatch) -> None:
    """Verify that CertusDesignApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from certus.ui.certus_design_ui import CertusDesignApp

    app = QApplication.instance() or QApplication([])
    window = CertusDesignApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_index_app_constructs_headless(monkeypatch) -> None:
    """Verify that CertusIndexApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from certus.ui.certus_index_ui import CertusIndexApp

    app = QApplication.instance() or QApplication([])
    window = CertusIndexApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_strat_app_constructs_headless(monkeypatch) -> None:
    """Verify that CertusStratApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from certus.ui.certus_strat_ui import CertusStratApp

    app = QApplication.instance() or QApplication([])
    window = CertusStratApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_index_spline_app_constructs_headless(monkeypatch) -> None:
    """Verify that CertusIndexSplineApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    app = QApplication.instance() or QApplication([])
    window = CertusIndexSplineApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_hub_app_constructs_headless(monkeypatch) -> None:
    """Verify that CertusHub instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QApplication, QMainWindow
    from CERTUS_HUB import CertusHub

    app = QApplication.instance() or QApplication([])
    window = CertusHub()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()
