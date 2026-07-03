"""Centralized splash screen creation for all CERTUS modules.

Eliminates the duplicated splash pixmap loading logic that was previously
copy-pasted across 6 entry-point files.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QSplashScreen

from certus.core.certus_core import get_resource_path, SVG_AVAILABLE


def create_splash(init_message: str = "Initializing...", do_warmup: bool = True) -> QSplashScreen:
    """Create and show the CERTUS splash screen with SVG → ICO → blank fallback.

    Parameters
    ----------
    init_message : str
        The initial status message displayed at the bottom of the splash.
    do_warmup : bool
        If True, runs the Numba JIT pre-warming script while the splash is shown.

    Returns
    -------
    QSplashScreen
        A visible splash screen ready to receive ``showMessage`` updates.
    """
    splash_pix = QPixmap()
    if SVG_AVAILABLE:
        splash_pix = QPixmap(get_resource_path("certus.svg"))

    if splash_pix.isNull():
        splash_pix = QPixmap(get_resource_path("certus.ico"))

    if splash_pix.isNull():
        splash_pix = QPixmap(400, 200)
        splash_pix.fill(Qt.GlobalColor.white)

    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()

    def _show_msg(msg: str):
        splash.showMessage(
            msg,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            Qt.GlobalColor.black,
        )
        from PyQt6.QtWidgets import QApplication
        if QApplication.instance():
            QApplication.processEvents()

    _show_msg(init_message)

    if do_warmup:
        try:
            from certus.physics.certus_warmup import run_warmup
            run_warmup(progress_callback=_show_msg)
            _show_msg(init_message) # Restore original message after warmup
        except Exception as e:
            import logging
            logging.getLogger("CERTUS").error(f"Warmup failed: {e}")

    return splash
