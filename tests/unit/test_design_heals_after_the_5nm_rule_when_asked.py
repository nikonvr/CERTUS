"""DESIGN re-optimizes once after its final 5 nm rule when `_polish_after_5nm_rule` is set.

The rule removes layers under 5 nm at the end of the workflow and exports without re-optimizing:
on the 50/50 splitter 400-1200 nm it took a 34-layer design from RMSE 0.000161 to 0.001035 by
removing one layer (reports/DESIGN_bs5050_2026-10-22/journal.md). With the option, the workflow
heals (restricted global, then local polish) before it finalizes again; without it, nothing changes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN heal after 5 nm rule", main_windows_only=True)


@pytest.mark.parametrize("option", [False, True])
def test_the_finalisation_heals_after_the_5nm_rule_only_when_asked(qapp, monkeypatch, option) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus_physics import init_thickness

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    for row in (3, 10):  # two layers under 5 nm for the rule to remove
        app.front_table.cellWidget(row, 1).setValue(0.02)
    app.ep_current = np.asarray(init_thickness(app._get_front_stack(), app.l0_spin.value(), app._get_materials()))
    app._decimation_done = True  # straight to the rule
    app._polish_after_5nm_rule = option
    app._auto_restarts = 0  # the automatic restart is not under test here
    app._export_pending = False
    monkeypatch.setattr("certus.ui.certus_design_ui_optimization.get_export_config", lambda: True)
    calls = []
    monkeypatch.setattr(app.orchestrator, "_handle_healing_workflow", lambda removed: calls.append(f"heal {removed}") or True)
    monkeypatch.setattr(app, "_schedule_eval", lambda *a: calls.append("eval"))

    app.optimization_manager._finalize_completed_optimization_workflow()

    # The rule's own table refresh schedules an evaluation either way; the final one comes with the export.
    if option:
        assert "heal 2" in calls
        assert app._export_pending is False
    else:
        assert "heal 2" not in calls
        assert app._export_pending is True
