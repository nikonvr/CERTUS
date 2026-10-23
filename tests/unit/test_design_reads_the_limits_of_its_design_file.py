"""DESIGN reads `max_layers` and `max_total_qwot` from the settings block of a design file.

`max_layers` caps the growth of the workflow (a needle adds two layers, and starts only if they fit);
`max_total_qwot` caps the total optical thickness of the memetic global stage. A file without them
leaves the former limits (CFG.MAX_LAYERS, no thickness cap).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN design limits", main_windows_only=True)


def _load(tmp_path, **limits):
    from certus.ui.certus_design_ui import CertusDesignApp

    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for key in ("max_layers", "max_total_qwot"):
        config["optim"].pop(key, None)
    config["optim"].update(limits)
    path = tmp_path / "design.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    app = CertusDesignApp()
    app.load_config(str(path))
    return app


def test_the_limits_of_the_file_reach_the_window(qapp, tmp_path) -> None:
    app = _load(tmp_path, max_layers=34, max_total_qwot=30)

    assert app._max_layers_cap == 34
    assert app._max_total_qwot == 30.0
    assert app.orchestrator._layer_ceiling() == 34
    assert app.orchestrator._room_for_a_needle(32)
    assert not app.orchestrator._room_for_a_needle(33)


def test_a_file_without_limits_keeps_the_former_ones(qapp, tmp_path) -> None:
    from certus.core.certus_core import CFG

    app = _load(tmp_path)

    assert app._max_layers_cap is None
    assert app._max_total_qwot is None
    assert app.orchestrator._layer_ceiling() == CFG.MAX_LAYERS
    assert app.orchestrator._room_for_a_needle(CFG.MAX_LAYERS - 1)

