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

from certus.core.certus_core import CertusFacadeModule, setup_module_logging
from certus.ui.certus_ui import init_certus_app

# Import the modular submodules
import certus.spline.certus_index_spline_core as certus_index_spline_core
import certus.spline.certus_index_spline_optimization as certus_index_spline_optimization
import certus.spline.certus_index_spline_smart_init as certus_index_spline_smart_init
import certus.spline.certus_index_spline_corridors as certus_index_spline_corridors
import certus.ui.certus_index_spline_ui as certus_index_spline_ui

# Preserve SplineReport exports (for external tools or back-compat)
from certus.utils.certus_spline_report import SplineReportContext, SplineReportBuilder  # noqa: F401

# Configure the facade to wrap and expose all underlying symbols
sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_index_spline_core,
    certus_index_spline_optimization,
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

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
