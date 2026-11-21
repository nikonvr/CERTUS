"""DESIGN can let the wavelength grid find its own points (2026-11-13, off unless asked).

Checked, the box records `auto_wavelength_grid` among the optional steps that travel with the configuration, disables
Points / Target, and the grid of each run becomes the base grid of `certus_design_auto_grid` (its point count follows
from the TOT: the max TOT, else the estimate from the max layers, never below the design's). Unchecked, or for a file
that does not name it, the grid is the one of Points / Target, as before.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN auto grid", main_windows_only=True)


def _app():
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def test_the_box_is_off_by_default_and_the_grid_is_points_per_target(qapp) -> None:
    app = _app()
    assert not app.auto_grid_check.isChecked()
    assert app.auto_grid_check.toolTip()
    assert app.points_per_target_spin.isEnabled()
    assert len(app._get_optim_wls()) == app.points_per_target_spin.value()
    assert "auto_wavelength_grid" not in app._collect_config()["optimization"]


def test_checked_the_grid_follows_the_tot(qapp) -> None:
    from certus.core.certus_design_auto_grid import auto_grid_tot_nm, base_grid

    app = _app()
    app.auto_grid_check.setChecked(True)
    assert not app.points_per_target_spin.isEnabled()
    tot = auto_grid_tot_nm(app.core_manager._current_tot_nm(app._get_tgts()), app._max_total_qwot, app.l0_spin.value())
    np.testing.assert_array_equal(app._get_optim_wls(), base_grid([(400.0, 1200.0)], tot))
    assert app.npts_spin.value() == len(app._get_optim_wls())


def test_the_choice_travels_with_the_configuration(qapp) -> None:
    app = _app()
    app.auto_grid_check.setChecked(True)
    config = app._collect_config()
    assert config["optimization"]["auto_wavelength_grid"] is True

    other = _app()
    other._apply_config(config)
    assert other.auto_grid_check.isChecked()
    assert not other.points_per_target_spin.isEnabled()
    del config["optimization"]["auto_wavelength_grid"]
    other._apply_config(config)
    assert not other.auto_grid_check.isChecked(), "a file that does not name it keeps Points / Target"
    assert other.points_per_target_spin.isEnabled()


# The limits of the design (owner, 2026-11-21) are fields of the window: Max layers and Max TOT (QWOT at l0), 0 = none.
# Checked, the grid resolves the max TOT when given, else the TOT ceiling estimated from the max layers.


def test_the_limits_of_the_file_are_shown_in_their_fields(qapp) -> None:
    app = _app()  # the example file names max_layers 34 and max_total_qwot 30
    assert app.max_layers_spin.value() == 34
    assert app.max_total_qwot_spin.value() == 30.0
    assert app.max_layers_spin.toolTip()
    assert app.max_total_qwot_spin.toolTip()
    assert app.auto_grid_points_label.isHidden(), "the grid summary shows only with the automatic grid"


def test_checked_the_grid_follows_the_max_layers_without_a_max_tot(qapp) -> None:
    from certus.core.certus_design_auto_grid import auto_grid_tot_nm, base_grid, layers_tot_ceiling_nm

    app = _app()
    app.auto_grid_check.setChecked(True)
    app.max_total_qwot_spin.setValue(0.0)
    assert app._max_total_qwot is None
    bands = [(400.0, 1200.0)]
    stack = app.core_manager._current_tot_nm(app._get_tgts())
    assert stack < layers_tot_ceiling_nm(bands, 34)
    expected = base_grid(bands, auto_grid_tot_nm(stack, None, app.l0_spin.value(), max_layers=34, bands=bands))
    np.testing.assert_array_equal(app._get_optim_wls(), expected)
    assert app.npts_spin.value() == expected.size
    assert not app.auto_grid_points_label.isHidden()
    text = app.auto_grid_points_label.text()
    assert "max layers" in text
    assert f"{expected.size} points" in text

    app.max_layers_spin.setValue(0)
    assert app._max_layers_cap is None
    np.testing.assert_array_equal(app._get_optim_wls(), base_grid(bands, stack))
    assert "design" in app.auto_grid_points_label.text()


def test_the_limits_travel_with_the_configuration_and_zero_means_none(qapp) -> None:
    app = _app()
    app.max_layers_spin.setValue(20)
    app.max_total_qwot_spin.setValue(12.5)
    assert app.orchestrator._layer_ceiling() == 20
    config = app._collect_config()
    assert config["optimization"]["max_layers"] == 20
    assert config["optimization"]["max_total_qwot"] == 12.5

    other = _app()
    other._apply_config(config)
    assert (other._max_layers_cap, other._max_total_qwot) == (20, 12.5)

    app.max_layers_spin.setValue(0)
    app.max_total_qwot_spin.setValue(0.0)
    config = app._collect_config()
    assert "max_layers" not in config["optimization"]
    assert "max_total_qwot" not in config["optimization"]
    other._apply_config(config)
    assert (other._max_layers_cap, other._max_total_qwot) == (None, None)
    assert (other.max_layers_spin.value(), other.max_total_qwot_spin.value()) == (0, 0.0)


def test_oblique_mode_uses_the_manual_point_count(qapp) -> None:
    app = _app()
    app.auto_grid_check.setChecked(True)

    app.core_manager._toggle_oblique_mode(2)

    assert app.oblique_mode
    assert not app.auto_grid_check.isEnabled()
    assert app.points_per_target_spin.isEnabled()
    assert len(app._get_optim_wls()) == app.points_per_target_spin.value()

    app.core_manager._toggle_oblique_mode(0)

    assert app.auto_grid_check.isEnabled()
    assert app.auto_grid_check.isChecked()
    assert not app.points_per_target_spin.isEnabled()
