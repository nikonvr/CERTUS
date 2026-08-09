# =========================================================================================
# ARCHITECTURE: LIGHTWEIGHT FACADE FOR FIELD MODULE
# =========================================================================================

import os
import sys
import multiprocessing
import ctypes
from pathlib import Path
import logging

#Numba configuration BEFORE any import using @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next
#to the sources, in the cloud-synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import create_module_environment

# Initialize module environment before importing local packages
env = create_module_environment(__file__, "FIELD")
script_dir = env["script_dir"]

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from certus.core.certus_core import setup_module_logging
from certus.ui.certus_ui import init_certus_app

from certus.ui.certus_field_ui import CertusFieldApp
from certus.core.certus_core import CertusFacadeModule
import certus.core.certus_field_core as certus_field_core
import certus.workers.certus_field_workers as certus_field_workers
import certus.ui.certus_field_ui as certus_field_ui

# Replace current module with a facade exposing core, workers, and ui components
sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_field_core,
    certus_field_workers,
    certus_field_ui,
])

# Main Executable Flow
if __name__ == "__main__":
    # Required for building executables with multiprocessing on Windows
    multiprocessing.freeze_support()

    setup_module_logging("FIELD", log_file="field.log")

    # Ensure crisp rendering on high-DPI displays
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    init_certus_app("CERTUS-FIELD", app=app)

    # Set an explicit AppUserModelID for proper Windows taskbar icon grouping
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("certus.field.2.0")
    except (OSError, AttributeError, ImportError):
        pass

    win = CertusFieldApp()
    win.show()

    sys.exit(app.exec())
