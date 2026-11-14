"""DESIGN can let the wavelength grid find its own points (2026-11-13, off unless asked).

Checked, the box records `auto_wavelength_grid` among the optional steps that travel with the configuration, disables
Points / Target, and the grid of each run becomes the base grid of `certus_design_auto_grid` (its point count follows
from the TOT). Unchecked, or for a file that does not name it, the grid is the one of Points / Target, as before.
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
