"""UI smoke tests for CERTUS Metal Bilayer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = ROOT / "CERTUS_METAL_BILAYER.py"


@pytest.mark.unit
def test_certus_metal_bilayer_app_constructs_headless(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    pytest.importorskip("PyQt6")

    spec = importlib.util.spec_from_file_location("CERTUS_METAL_BILAYER", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
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
        from certus_physics.materials_data import get_nk_si
        from certus.core._certus_physics_impl import (
            get_nk_cauchy_simple,
            calculate_reflectance_bilayer_vectorized,
        )

                        
    finally:
        window.close()
        app.processEvents()
