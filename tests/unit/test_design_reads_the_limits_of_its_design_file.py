"""DESIGN reads `max_layers` and `max_total_qwot` from the settings block of a design file.

`max_layers` caps the growth of the workflow (a needle adds two layers, and starts only if they fit);
`max_total_qwot` caps the total optical thickness of the memetic global stage. A file without them
leaves the former limits (CFG.MAX_LAYERS, no thickness cap).
"""

from __future__ import annotations

import itertools
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


def test_an_optical_thickness_floor_gives_each_material_its_least_thickness(qapp, tmp_path) -> None:
    app = _load(tmp_path, min_layer_ot_nm=5)

    floor = app.optimization_manager._min_layer_thickness(["H", "L"])

    assert app._min_layer_ot_nm == 5.0
    assert floor[0] == pytest.approx(5.0 / 2.35)
    assert floor[1] == pytest.approx(5.0 / 1.46)


@pytest.mark.parametrize(("ot", "rows_left"), [(None, 24), (5, 26)])
def test_the_final_rule_keeps_a_4nm_high_index_layer_only_under_an_optical_floor(qapp, tmp_path, ot, rows_left) -> None:
    import numpy as np

    from certus_physics import init_thickness

    app = _load(tmp_path, **({"min_layer_ot_nm": ot} if ot else {}))
    app.front_table.cellWidget(4, 1).setValue(4.0 * 4 * 2.35 / 500.0)  # an H layer of 4 nm (QWOT with n4)
    app.ep_current = np.asarray(init_thickness(app._get_front_stack(), app.l0_spin.value(), app._get_materials()))

    app._apply_5nm_minimum()

    assert app.front_table.rowCount() == rows_left  # without the floor: removed, its two L neighbours merged


@pytest.mark.parametrize(("limits", "rows"), [({"max_layers": 34}, 34), ({}, 26)])
def test_a_global_run_first_fills_the_stack_up_to_max_layers(qapp, tmp_path, limits, rows) -> None:
    app = _load(tmp_path, **limits)
    names_before = [layer.mat for layer in app._get_front_stack()]

    app.worker_manager._fill_to_max_layers()

    names = [layer.mat for layer in app._get_front_stack()]
    assert len(names) == rows
    assert names[: len(names_before)] == names_before
    assert all(a != b for a, b in itertools.pairwise(names))  # the alternation goes on
    assert app.orchestrator._target_layer_count == rows or not limits


def test_a_file_may_allow_more_layers_than_the_default_ceiling(qapp, tmp_path) -> None:
    app = _load(tmp_path, max_layers=110)

    assert app.orchestrator._layer_ceiling() == 110
