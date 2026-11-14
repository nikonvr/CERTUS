"""UI smoke tests for CERTUS Metal Bilayer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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
        for key in ("eL_variation", "num_knots", "n_infini_min", "n_infini_max", "A_diel_min", "A_diel_max"):
            assert window.widgets[key].text()
            assert window.widgets[key].toolTip()

        window._auto_batch_mode = True
        progress = {"mode": "local", "iteration": 2, "max_iteration": 10, "progress_pct": 20,
                    "mse": 0.04, "best_cost": 0.01, "params": [12.0, 100.0, 1.43, 3000.0]}
        window._on_optim_progress(progress)
        window._on_optim_progress({**progress, "best_cost": 0.09})
        assert window._auto_batch_last_progress["params"] == progress["params"]
        assert window._auto_batch_best_mse == pytest.approx(0.01)
        window._auto_batch_mode = False

        config = window._get_config_dict()
        assert config["optimization"]["analytic_polish"] is False
        config["optimization"]["analytic_polish"] = True
        window._apply_config_dict(config)
        assert window._build_bilayer_optimization_params()["analytic_polish"] is True
        assert window._get_config_dict()["optimization"]["analytic_polish"] is True
        window._load_defaults()
        assert window._build_bilayer_optimization_params()["analytic_polish"] is False

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
