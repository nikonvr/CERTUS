"""Centralized splash screen creation for all CERTUS modules.

Eliminates the duplicated splash pixmap loading logic that was previously
copy-pasted across 6 entry-point files.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QSplashScreen

from certus_core import get_resource_path


def create_splash(init_message: str = "Initializing...") -> QSplashScreen:
    """Create and show the CERTUS splash screen with SVG → ICO → blank fallback.

    Parameters
    ----------
    init_message : str
        The initial status message displayed at the bottom of the splash.

    Returns
    -------
    QSplashScreen
        A visible splash screen ready to receive ``showMessage`` updates.
    """
    splash_pix = QPixmap(get_resource_path("certus.svg"))

    if splash_pix.isNull():
        splash_pix = QPixmap(get_resource_path("certus.ico"))

    if splash_pix.isNull():
        splash_pix = QPixmap(400, 200)
        splash_pix.fill(Qt.GlobalColor.white)

    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()

    splash.showMessage(
        init_message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    return splash
