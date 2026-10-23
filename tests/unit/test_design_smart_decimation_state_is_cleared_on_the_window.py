"""The end of a Smart Pareto Decimation clears its state where it lives: on the window.

The decimation writes `_smart_decimation_step` and its other attributes on the window, and the orchestrator
reads them there to route the end of every optimization into the decimation. `_clear_smart_decimation_state`
deleted them from the optimization manager instead, so the session never ended: a healing started after
the decimation was taken for one of its steps, which restored the Pareto champion over the healed design
(RMSE 0.000256 -> 0.0166 on the 50/50 splitter, reports/DESIGN_bs5050_2026-10-22/journal.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN decimation state", main_windows_only=True)


def test_the_decimation_state_is_cleared_from_the_window(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    app._smart_decimation_step = 3
    app._smart_decimation_polish_pass = 1
    app._smart_deci_origin_N = 34

    app.optimization_manager._clear_smart_decimation_state()

    assert not hasattr(app, "_smart_decimation_step")
    assert not hasattr(app, "_smart_decimation_polish_pass")
    assert not hasattr(app, "_smart_deci_origin_N")
    assert not app.orchestrator._handle_smart_decimation_followup({"ok": True})
