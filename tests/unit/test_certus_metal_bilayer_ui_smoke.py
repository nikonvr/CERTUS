"""UI smoke tests for CERTUS Metal Bilayer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = ROOT / "CERTUS_METAL_BILAYER.py"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it: a METAL window left alive until the
    interpreter exits was torn down in finalization order and crashed the process after
    the last test (access violation, 3 runs out of 9 of the METAL unit files, 2026-09-27)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "METAL smoke", main_windows_only=True)


@pytest.mark.unit
def test_certus_metal_bilayer_app_constructs_headless(monkeypatch, qapp) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    pytest.importorskip("PyQt6")

    spec = importlib.util.spec_from_file_location("CERTUS_METAL_BILAYER", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The session's application, never a local one: created here, it would die with this
    # test and every later Qt test in the process would run on a destroyed application.
    app = qapp
    window = mod.CertusMetalBilayerApp()
    try:
        assert window is not None
        # Verify basic UI elements exist
        assert "eM_min" in window.widgets
        assert "eL_nominal" in window.widgets
        assert window.widgets["eM_min"].text()

        # Run JIT warmup directly to guarantee it has executed in this test
        window._warmup_numba_thread_runner()

        # Verify that Numba has compiled the critical bilayer JIT functions
        from certus.core._certus_physics_impl import (
            calculate_reflectance_bilayer_vectorized,
            get_nk_cauchy_simple,
        )
        from certus_physics.materials_data import get_nk_si

                        
    finally:
        window.close()
        app.processEvents()
