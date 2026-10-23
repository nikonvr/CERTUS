"""With `floor_at_end`, DESIGN raises the thin layers to their floor at the end and re-optimizes above it.

Owner's practice (2026-10-23): let the design progress freely and apply the thickness floor at the very end.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN floor at end", main_windows_only=True)


@pytest.mark.parametrize("option", [False, True])
def test_the_thin_layers_are_raised_and_healed_only_with_the_option(qapp, monkeypatch, option) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    ep = np.full(app.front_table.rowCount(), 60.0)
    ep[3] = 1.5
    app.ep_current = ep.copy()
    app._floor_at_end = option
    app._layer_floor_active = None
    healed = []
    monkeypatch.setattr(app.orchestrator, "_handle_healing_workflow", lambda removed: healed.append(removed) or True)

    started = app.optimization_manager._apply_floor_at_end()

    assert started is option
    if option:
        assert healed == [1]
        assert app.ep_current[3] == pytest.approx(5.0)  # the 5 nm floor of a file without min_layer_ot_nm
        assert app._layer_floor_active[3] == pytest.approx(5.0)
    else:
        assert healed == []
        assert app.ep_current[3] == 1.5
