"""DESIGN states the least thickness of a final layer in the window (owner, 2026-11-13).

It was 5 nm written in the code. The field keeps 5 nm by default, so a design that does not touch it keeps its
floors; the file's optical floor (`min_layer_ot_nm`) still comes first. The value travels with the configuration
only when it is not the default: a file written before the field loads as 5 nm.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN min layer", main_windows_only=True)


def _app():
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def _floors(app) -> np.ndarray:
    names = [layer.mat for layer in app._get_front_stack()]
    return app.optimization_manager._min_layer_thickness(names)


def test_the_field_is_5_nm_by_default_and_says_what_it_does(qapp) -> None:
    app = _app()
    assert app.min_layer_spin.value() == 5.0
    assert app.min_layer_spin.toolTip()
    assert set(_floors(app)) == {5.0}


def test_the_field_sets_the_floor_of_every_layer(qapp) -> None:
    app = _app()
    app.min_layer_spin.setValue(12.5)
    assert set(_floors(app)) == {12.5}


def test_the_optical_floor_of_the_file_comes_first(qapp) -> None:
    app = _app()
    app.min_layer_spin.setValue(12.5)
    app._min_layer_ot_nm = 30.0
    mats = app._get_materials()
    expected = [30.0 / float(mats[layer.mat].n4) for layer in app._get_front_stack()]
    assert _floors(app) == pytest.approx(expected)


def test_the_value_travels_with_the_configuration_only_when_it_is_not_the_default(qapp) -> None:
    app = _app()
    assert "min_layer_nm" not in app._collect_config()["optimization"]
    app.min_layer_spin.setValue(8.0)
    config = app._collect_config()
    assert config["optimization"]["min_layer_nm"] == 8.0

    other = _app()
    other._apply_config(config)
    assert other.min_layer_spin.value() == 8.0
    del config["optimization"]["min_layer_nm"]
    other._apply_config(config)
    assert other.min_layer_spin.value() == 5.0, "a file without the value is a file at 5 nm"
