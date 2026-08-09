# =============================================================================

# CERTUS DESIGN MODULE

# Functional area: Optical Synthesis & Optimization

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: only make small, reversible changes here until dedicated tests cover
# optimization workers, DTO/report contracts, and critical design workflows.
# Prefer extracting pure helpers before moving Qt classes or numerical kernels.
# Keep the design orchestration dense only where it is genuinely required.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-DESIGN.py - Optical Filter Design & Optimization

=========================================================

"""

#Numba configuration BEFORE any import using @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next
#to the sources, in the cloud-synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import __version__

from certus_physics import (
    Layer,
)
from certus_physics import (
    calc_spectrum_front_wrapper,
)

import os
from pathlib import Path

import multiprocessing
import sys
import functools

from certus.core.certus_core import create_module_environment

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_DESIGN")

script_dir = env["script_dir"]

# =============================================================================

# SUBSEQUENT IMPORTS


import sys
from certus.core.certus_core import CertusFacadeModule
import certus.core.certus_design_core as certus_design_core
import certus.workers.certus_design_workers as certus_design_workers
import certus.ui.certus_design_ui as certus_design_ui
from certus.core.certus_design_core import *
from certus.workers.certus_design_workers import *
from certus.ui.certus_design_ui import *

sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_design_core,
    certus_design_workers,
    certus_design_ui
])

def main() -> None:
    """Main entry point"""

    # Change working directory to script/exe directory (script_dir set by bootstrap_app)

    try:
        os.chdir(script_dir)

    except (OSError, FileNotFoundError) as e:
        logging.debug(f"Could not change working directory: {e}")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    CertusTheme.apply_to_app(app, dark_mode=False)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-DESIGN", app=app)

    try:
        from certus.utils.certus_ux import build_premium_overrides

        app.setStyleSheet(app.styleSheet() + "\n" + build_premium_overrides())
    except ImportError:
        pass

    # --- SPLASH SCREEN ---

    from certus.ui.certus_splash import create_splash

    splash = create_splash("Initializing Design Environment...")

    # Setup logging with centralized helper

    setup_module_logging("CERTUS_DESIGN", log_file="certus_design.log")

    splash.showMessage(
        "Loading Default Configuration...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    win = CertusDesignApp()

    win.show()

    splash.finish(win)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_config(f))

    sys.exit(app.exec())

if __name__ == "__main__":
    # CRITICAL for Nuitka/PyInstaller: Must be FIRST in __main__

    multiprocessing.freeze_support()

    main()
