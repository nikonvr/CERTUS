"""DESIGN's live optimization display reads the state of the window.

PlotManager read four values of the window on itself (`getattr(self, "accumulated_evals",
0)`, ...), where they never are: the convergence curve and the live title restarted their
evaluation count at every stage of the workflow, the live title never named the loaded
configuration, the live profile dropped the back coating when the update did not carry it,
and the one-second throttle of the stack information never throttled — harmless while the
scheduled refresh did nothing, one refresh per intermediate spectrum once it ran again
(f628b9a). Found on 2026-09-29 by listing every guard a class puts on a name it never holds.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN live display", main_windows_only=True)


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def _intermediate(app, evals: int) -> dict:
    return {"type": "intermediate", "rmse": 0.01, "evals": evals, "ep": np.asarray(app.ep_current, dtype=float)}


def test_the_stack_information_refresh_is_throttled(design_app, monkeypatch) -> None:
    refreshes = []
    monkeypatch.setattr(design_app.orchestrator, "schedule_update_substrate_info", lambda: refreshes.append(1))
    design_app._workflow_best_rmse = 0.001  # the updates below do not improve on it

    design_app.plot_manager._on_intermediate_spectrum(_intermediate(design_app, 10))
    design_app.plot_manager._on_intermediate_spectrum(_intermediate(design_app, 20))

    assert len(refreshes) == 1


def test_the_convergence_curve_counts_the_evaluations_of_the_previous_stages(design_app) -> None:
    design_app.accumulated_evals = 900

    design_app.plot_manager._on_intermediate_spectrum(_intermediate(design_app, 100))

    assert design_app.mse_data["iterations"][-1] == 1000


def test_the_live_title_names_the_loaded_configuration(design_app) -> None:
    design_app._last_config_file = str(EXAMPLE)

    design_app.plot_manager._update_optim_live_plot_title(
        {"ep": np.asarray(design_app.ep_current, dtype=float)}, True, 0.01, 5, False
    )

    assert "[JSON-design-example]" in design_app.spectrum_plot.plotItem.titleLabel.text


def test_the_live_profile_keeps_the_back_coating(design_app, monkeypatch) -> None:
    drawn = []
    monkeypatch.setattr(design_app, "_plot_profile", lambda ep, stack, ep_back, stack_back: drawn.append(ep_back))
    design_app.ep_back_current = np.array([80.0, 120.0])

    design_app.plot_manager._update_optim_live_profile_tabs({"ep": np.asarray(design_app.ep_current, dtype=float)})

    [ep_back] = drawn
    assert ep_back is design_app.ep_back_current
