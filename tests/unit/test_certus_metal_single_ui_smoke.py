"""UI smoke tests for CERTUS Metal Single."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = ROOT / "certus_metal_siNGLE.py"


@pytest.mark.unit
def test_certus_metal_single_app_constructs_headless(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    pytest.importorskip("PyQt6")

    spec = importlib.util.spec_from_file_location("certus_metal_siNGLE", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    window = mod.CertusMetalSingleApp()
    try:
        assert window is not None
        assert hasattr(window, "combo_substrate")
        assert hasattr(window, "substrate_info_label")
        assert window.combo_substrate.currentText()

        # Run JIT warmup directly to guarantee it has executed in this test
        window._warmup_numba()

        # Verify that Numba has compiled the critical single JIT functions
        from certus.core._certus_physics_impl import (
            calculate_RTRback_incoherent_vectorized,
        )

        assert len(calculate_RTRback_incoherent_vectorized.signatures) > 0, (
            "calculate_RTRback_incoherent_vectorized was not compiled"
        )

    finally:
        window.close()
        app.processEvents()
