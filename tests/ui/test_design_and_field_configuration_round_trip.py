"""A saved DESIGN or FIELD configuration brings back the settings it left out (audit 2026-11-15, M-L5b).

DESIGN wrote the number of Monte Carlo draws and the absolute sigma, not the relative sigma, the optical-thickness sigma
nor the RMSE threshold of the spectral Monte Carlo. FIELD did not write the minimal thickness of its optimiser.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "configuration round trip", main_windows_only=True)


def test_design_brings_back_the_spectral_monte_carlo_settings(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    source, fresh = CertusDesignApp(), CertusDesignApp()
    source.mc_sigma_rel_spin.setValue(1.5)
    source.mc_sigma_ot_spin.setValue(0.75)
    source.mc_rmse_threshold_spin.setValue(0.02)

    fresh._apply_config(source._collect_config())

    assert fresh.mc_sigma_rel_spin.value() == 1.5
    assert fresh.mc_sigma_ot_spin.value() == 0.75
    assert fresh.mc_rmse_threshold_spin.value() == pytest.approx(0.02)


def test_field_brings_back_the_minimal_thickness_of_the_optimiser(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    source, fresh = CertusFieldApp(), CertusFieldApp()
    source.opt_panel.edit_dmin.setValue(12.5)

    fresh._apply_config(source._collect_config())

    assert fresh.opt_panel.edit_dmin.value() == 12.5


def test_field_keeps_its_minimal_thickness_when_the_configuration_has_none(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    source, fresh = CertusFieldApp(), CertusFieldApp()
    old = {k: v for k, v in source._collect_config().items() if k != "opt_dmin"}
    fresh.opt_panel.edit_dmin.setValue(12.5)

    fresh._apply_config(old)

    assert fresh.opt_panel.edit_dmin.value() == 12.5


# DESIGN saves and loads its settings through two tables (certus/ui/certus_config_table.py).


def test_the_design_configuration_keeps_its_keys(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    cfg = CertusDesignApp()._collect_config()

    assert set(cfg) == {"version", "l0", "materials", "front", "back_en", "back_coat", "back", "targets", "oblique_mode", "optimization"}
    assert {
        "points_per_target", "n100", "max_clusters", "max_iter", "mc_n", "mc_sigma", "mc_sigma_rel", "mc_sigma_ot",
        "mc_rmse_threshold", "pre_polish", "allow_growth", "auto_scale_y",
    } <= set(cfg["optimization"])
    assert "min_layer_nm" not in cfg["optimization"]  # written only away from the 5 nm of the files before it


def test_every_setting_of_the_design_tables_comes_back(qapp) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.ui.certus_design_ui_state import DESIGN_CONFIG_TABLE, DESIGN_OPTIMIZATION_TABLE

    assert_round_trip(CertusDesignApp(), CertusDesignApp(), DESIGN_CONFIG_TABLE + DESIGN_OPTIMIZATION_TABLE)


def test_a_design_file_without_a_least_layer_thickness_is_a_file_at_5_nm(qapp) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    win = CertusDesignApp()
    cfg = win._collect_config()
    win.min_layer_spin.setValue(7.0)

    win._apply_config(cfg)

    assert win.min_layer_spin.value() == 5.0


def test_every_editable_design_setting_is_saved_or_left_out_by_name(qapp) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.ui.certus_design_ui_state import (
        DESIGN_CONFIG_OUTSIDE_TABLE,
        DESIGN_CONFIG_TABLE,
        DESIGN_OPTIMIZATION_TABLE,
    )

    tables = DESIGN_CONFIG_TABLE + DESIGN_OPTIMIZATION_TABLE
    assert_every_setting_is_in_the_table(CertusDesignApp(), tables, DESIGN_CONFIG_OUTSIDE_TABLE)


# FIELD saves and loads its settings through one table.


def test_the_field_configuration_keeps_its_keys(qapp) -> None:
    from certus.ui.certus_field_ui import CertusFieldApp

    assert set(CertusFieldApp()._collect_config()) == {
        "mat_H", "mat_L", "mat_Sub", "mat_Sup", "l0", "lcalc", "emp_factors", "layer_types", "seuil1", "seuil2",
        "alpha", "theta_inc_deg", "pol_idx", "mc_error", "mc_iter", "rmin", "rmax", "min_field_active", "global_opt",
        "analytic_gradient", "allow_growth", "opt_dmin",
    }


def test_every_setting_of_the_field_table_comes_back(qapp) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_field_state_mixin import FIELD_CONFIG_TABLE
    from certus.ui.certus_field_ui import CertusFieldApp

    assert_round_trip(CertusFieldApp(), CertusFieldApp(), FIELD_CONFIG_TABLE)


def test_every_editable_field_setting_is_saved_or_left_out_by_name(qapp) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_field_state_mixin import FIELD_CONFIG_OUTSIDE_TABLE, FIELD_CONFIG_TABLE
    from certus.ui.certus_field_ui import CertusFieldApp

    assert_every_setting_is_in_the_table(CertusFieldApp(), FIELD_CONFIG_TABLE, FIELD_CONFIG_OUTSIDE_TABLE)
