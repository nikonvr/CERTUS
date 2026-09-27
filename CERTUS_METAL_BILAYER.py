#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""
CERTUS-METAL-BILAYER CERTUS_SUITE_26_05
================================
Metal Index Determination on SiO2/Si substrate (Bilayer Strategy)

Determines the complex refractive index (n, k) of a metal layer deposited
on top of a SiO2 layer, itself on top of an absorbing Si substrate.

Structure: Air | Metal (eM) | SiO2 (eL) | Si (absorbing substrate)

Uses PGLOBAL optimization to extract metal optical constants
from reflectance measurements. The metal index is modeld as wavelength-dependent
splines, while SiO2 uses a Cauchy model (n = n∞ + A/lambda²).

This file is the launcher. The computation lives in
certus/metal/certus_metal_bilayer_physics.py, the Qt workers and the window in
certus/metal/certus_metal_bilayer_app.py; every name of both modules stays
reachable here, as CERTUS_METAL_BILAYER.<name>.
"""

import multiprocessing
import sys
import warnings
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

#Numba configuration BEFORE any import pulling @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next to it
#sources, in the cloud synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import (
    __version__,
    CertusFacadeModule,
    create_module_environment,
    setup_logging,
)

import certus.metal.certus_metal_bilayer_app as certus_metal_bilayer_app
import certus.metal.certus_metal_bilayer_physics as certus_metal_bilayer_physics

# Bound here, not only reached through the facade below: tests load this file by
# path, and a module loaded that way is never replaced by its facade.
from certus.metal.certus_metal_bilayer_app import CertusMetalBilayerApp
from certus.metal.certus_metal_bilayer_physics import _validate_bilayer_spline_state

from certus.ui.certus_ui import (
    init_certus_app,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
)


warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy.optimize")


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


env = create_module_environment(__file__, "METAL_BILAYER")


script_dir = env["script_dir"]


setup_gui_exception_handling()


setup_pyqtgraph_defaults()


# Every name of the two modules stays reachable as CERTUS_METAL_BILAYER.<name>, and a
# monkeypatch applied to this module reaches the module that uses the name.
sys.modules[__name__] = CertusFacadeModule(__name__, [certus_metal_bilayer_app, certus_metal_bilayer_physics])


if __name__ == "__main__":
    import os
    os.environ.setdefault("CERTUS_CONSOLE_LOG_LEVEL", "INFO")
    import argparse

    parser = argparse.ArgumentParser(description="CERTUS Metal Bilayer")
    parser.add_argument("config", nargs="?", help="Optional config JSON path")
    parser.add_argument("--config", dest="config_flag", help="Optional config JSON path")
    parser.add_argument("--auto-run", action="store_true", help="Automatically load config and start optimization")
    parser.add_argument("--auto-close", action="store_true", help="Quit the app after optimization finishes")
    parser.add_argument("--no-splash", action="store_true", help="Disable splash screen")
    args = parser.parse_args()

    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    init_certus_app("CERTUS-METAL", app=app)

    # --- SPLASH SCREEN ---

    splash = None
    if not args.no_splash:
        from certus.ui.certus_splash import create_splash
        splash = create_splash("Initializing Metal Engine (Bilayer)...")

    # Setup logging with centralized helper

    setup_logging(log_file="certus_metal.log")

    window = CertusMetalBilayerApp()
    if args.auto_close:
        window._auto_batch_mode = True
        window._auto_batch_quit = False

    if not (args.auto_run or args.auto_close):
        window.show()

    if splash is not None:
        splash.finish(window)

    config_path = args.config_flag or args.config

    # Load file from CLI if provided

    if config_path and Path(config_path).exists():
        QTimer.singleShot(100, lambda cp=config_path: window.load_config(cp))
        if args.auto_run or args.auto_close:
            window._enable_auto_batch_mode(config_path)
    elif len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        QTimer.singleShot(100, lambda p=sys.argv[1]: window.load_config(p))
        if args.auto_run or args.auto_close:
            window._enable_auto_batch_mode(sys.argv[1])

    sys.exit(app.exec())
