# -*- coding: utf-8 -*-
"""
CERTUS INDEX SPLINE

Thin facade delegator for the Spline Index characterization app.
Forwards all attributes dynamically to modularized submodules.
"""

from __future__ import annotations
import sys
import multiprocessing
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

#Numba configuration BEFORE any import pulling @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next to it
#sources, in the cloud synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import CertusFacadeModule, setup_module_logging
from certus.ui.certus_ui import init_certus_app

# Import the modular submodules
import certus.spline.certus_index_spline_core as certus_index_spline_core
import certus.spline.certus_index_spline_smart_init as certus_index_spline_smart_init
import certus.spline.certus_index_spline_corridors as certus_index_spline_corridors
import certus.ui.certus_index_spline_ui as certus_index_spline_ui

# Preserve SplineReport exports (for external tools or back-compat)
from certus.utils.certus_spline_report import SplineReportContext, SplineReportBuilder  # noqa: F401

# Configure the facade to wrap and expose all underlying symbols
sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_index_spline_core,
    certus_index_spline_smart_init,
    certus_index_spline_corridors,
    certus_index_spline_ui
])

def main() -> None:
    multiprocessing.freeze_support()

    setup_module_logging("CERTUS_INDEX_SPLINE", log_file="certus_index_spline.log")

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    init_certus_app("CERTUS-INDEX-SPLINE", app=app)

    # Resolve App class dynamically via the facade module
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
    win = CertusIndexSplineApp()
    win.show()
    win.raise_()
    win.activateWindow()
    win.showMaximized()

    # Ensure the first meaningful redraw happens after the window is visible.
    QTimer.singleShot(0, lambda: (win.raise_(), win.activateWindow()))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
