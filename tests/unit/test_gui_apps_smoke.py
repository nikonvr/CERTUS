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
def test_certus_design_app_constructs_headless(monkeypatch, qapp) -> None:
    """Verify that CertusDesignApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QMainWindow
    from certus.ui.certus_design_ui import CertusDesignApp

    app = qapp  # the session's: a local one would die with the first Qt test
    window = CertusDesignApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_index_app_constructs_headless(monkeypatch, qapp) -> None:
    """Verify that CertusIndexApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QMainWindow
    from certus.ui.certus_index_ui import CertusIndexApp

    app = qapp  # the session's: a local one would die with the first Qt test
    window = CertusIndexApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_strat_app_constructs_headless(monkeypatch, qapp) -> None:
    """Verify that CertusStratApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QMainWindow
    from certus.ui.certus_strat_ui import CertusStratApp

    app = qapp  # the session's: a local one would die with the first Qt test
    window = CertusStratApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_index_spline_app_constructs_headless(monkeypatch, qapp) -> None:
    """Verify that CertusIndexSplineApp instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QMainWindow
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    app = qapp  # the session's: a local one would die with the first Qt test
    window = CertusIndexSplineApp()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()


@pytest.mark.unit
def test_certus_hub_app_constructs_headless(monkeypatch, qapp) -> None:
    """Verify that CertusHub instantiates correctly offscreen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt6")

    from PyQt6.QtWidgets import QMainWindow
    from CERTUS_HUB import CertusHub

    app = qapp  # the session's: a local one would die with the first Qt test
    window = CertusHub()
    try:
        assert window is not None
        assert isinstance(window, QMainWindow)
    finally:
        window.close()
        app.processEvents()
