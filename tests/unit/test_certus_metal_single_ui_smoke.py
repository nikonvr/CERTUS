"""UI smoke tests for CERTUS Metal Single."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = ROOT / "CERTUS_METAL_SINGLE.py"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    """Join the window's threads, then destroy it: a METAL window left alive until the
    interpreter exits was torn down in finalization order and crashed the process after
    the last test (access violation, 3 runs out of 9 of the METAL unit files, 2026-09-27)."""
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "METAL smoke", main_windows_only=True)


@pytest.mark.unit
def test_certus_metal_single_app_constructs_headless(monkeypatch, qapp) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    pytest.importorskip("PyQt6")

    spec = importlib.util.spec_from_file_location("certus_metal_siNGLE", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # The session's application, never a local one: created here, it would die with this
    # test and every later Qt test in the process would run on a destroyed application.
    app = qapp
    window = mod.CertusMetalSingleApp()
    try:
        assert window is not None
        assert hasattr(window, "combo_substrate")
        assert hasattr(window, "substrate_info_label")
        assert window.combo_substrate.currentText()

        # Run JIT warmup directly to guarantee it has executed in this test
        window._warmup_numba_thread_runner()

        # Verify that Numba has compiled the critical single JIT functions
        from certus.core._certus_physics_impl import (
            calculate_RTRback_incoherent_vectorized,
        )

        
    finally:
        window.close()
        app.processEvents()
