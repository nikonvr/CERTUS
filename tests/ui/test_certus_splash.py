"""Tests for the CERTUS splash screen module (certus_splash)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap

import certus.ui.certus_splash as splash_mod
from certus.ui.certus_splash import create_splash


@pytest.fixture
def mock_app(qapp):
    """Ensure QApplication exists."""
    return qapp


def test_create_splash_default(mock_app) -> None:
    """Verify that create_splash returns a valid QSplashScreen and displays message."""
    splash = create_splash("Initialisation de test...")
    try:
        assert splash is not None
        assert isinstance(splash, QSplashScreen)
        assert not splash.pixmap().isNull()
    finally:
        splash.close()


def test_create_splash_svg_fallback(mock_app, monkeypatch) -> None:
    """Verify fallback behavior when SVG is available."""
    monkeypatch.setattr(splash_mod, "SVG_AVAILABLE", True)
    
    splash = create_splash("SVG test")
    try:
        assert isinstance(splash, QSplashScreen)
        assert not splash.pixmap().isNull()
    finally:
        splash.close()


def test_create_splash_ico_fallback(mock_app, monkeypatch) -> None:
    """Verify fallback behavior when SVG is unavailable but ICO is available."""
    monkeypatch.setattr(splash_mod, "SVG_AVAILABLE", False)
    
    splash = create_splash("ICO test")
    try:
        assert isinstance(splash, QSplashScreen)
        assert not splash.pixmap().isNull()
    finally:
        splash.close()


def test_create_splash_blank_fallback(mock_app, monkeypatch) -> None:
    """Verify fallback behavior when neither SVG nor ICO is available."""
    monkeypatch.setattr(splash_mod, "SVG_AVAILABLE", False)
    
    # Mock get_resource_path to return a non-existent path
    monkeypatch.setattr(splash_mod, "get_resource_path", lambda name: "non_existent_file.png")
    
    splash = create_splash("Blank test")
    try:
        assert isinstance(splash, QSplashScreen)
        assert not splash.pixmap().isNull()
        # White blank pixmap size is 400x200
        pix = splash.pixmap()
        assert pix.width() == 400
        assert pix.height() == 200
    finally:
        splash.close()
