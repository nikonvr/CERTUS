"""A saved INDEX configuration brings back every setting of the fit (audit 2026-11-15, M-L5b).

``_collect_config`` wrote the excluded range but ``_apply_config`` never read it, and neither knew the fit window, the
substrate thickness, the high-precision box or the OH band box: a reloaded configuration silently fitted another
wavelength range, on another substrate thickness.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def index_windows(qapp):
    from certus.ui.certus_index_ui import CertusIndexApp

    wins = [CertusIndexApp(), CertusIndexApp()]
    yield wins
    for win in wins:
        win.close()


def test_the_fit_settings_survive_a_saved_configuration(index_windows) -> None:
    source, fresh = index_windows
    source.sb_lmin.setValue(420.0)
    source.sb_lmax.setValue(1100.0)
    source.sb_sub_thickness_mm.setValue(2.5)
    source.chk_high_precision.setChecked(True)
    source.chk_exclude.setChecked(True)
    source.sb_ex_min.setValue(500.0)
    source.sb_ex_max.setValue(620.0)

    fresh._apply_config(source._collect_config())

    assert fresh.sb_lmin.value() == 420.0
    assert fresh.sb_lmax.value() == 1100.0
    assert fresh.sb_sub_thickness_mm.value() == 2.5
    assert fresh.chk_high_precision.isChecked() is True
    assert fresh.chk_exclude.isChecked() is True
    assert fresh.sb_ex_min.value() == 500.0
    assert fresh.sb_ex_max.value() == 620.0
    assert fresh.chk_oh_band.isChecked() is False


def test_the_oh_band_box_survives_a_saved_configuration(index_windows) -> None:
    source, fresh = index_windows
    source.chk_exclude.setChecked(True)
    source.chk_oh_band.setChecked(True)
    assert source.chk_oh_band.isChecked() is True

    fresh._apply_config(source._collect_config())

    assert fresh.chk_exclude.isChecked() is True
    assert fresh.chk_oh_band.isChecked() is True
    assert fresh.sb_ex_min.value() == source.sb_ex_min.value()
    assert fresh.sb_ex_max.value() == source.sb_ex_max.value()


def test_a_configuration_without_the_new_keys_keeps_the_window_as_it_is(index_windows) -> None:
    source, fresh = index_windows
    old = {k: v for k, v in source._collect_config().items() if k in {"version", "substrate", "thickness_min", "thickness_max"}}
    fresh.sb_lmin.setValue(420.0)
    fresh.sb_sub_thickness_mm.setValue(2.5)

    fresh._apply_config(old)

    assert fresh.sb_lmin.value() == 420.0
    assert fresh.sb_sub_thickness_mm.value() == 2.5


# The INDEX window saves and loads its settings through one table (certus/ui/certus_config_table.py).

_INDEX_KEYS = {
    "version", "data_type", "file_loaded", "substrate", "frosted", "thickness_min", "thickness_max", "normalized",
    "exclude_oh", "exclude_min", "exclude_max", "fit_lambda_min", "fit_lambda_max", "substrate_thickness_mm", "oh_band",
    "high_precision", "weight_T", "weight_R", "model_type", "params", "optimization",
}


def test_the_index_configuration_keeps_its_keys(index_windows) -> None:
    assert set(index_windows[0]._collect_config()) == _INDEX_KEYS


def test_every_setting_of_the_index_table_comes_back(index_windows) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_index_ui_state import INDEX_CONFIG_TABLE

    # Frosted glass forces both weights and is not loaded with them: its own test follows.
    assert_round_trip(*index_windows, INDEX_CONFIG_TABLE, skip=("frosted",))


def test_a_frosted_configuration_comes_back_frosted_with_its_forced_weights(index_windows) -> None:
    source, fresh = index_windows
    source.rb_frosted_glass.setChecked(True)

    fresh._apply_config(source._collect_config())

    assert fresh.rb_frosted_glass.isChecked() is True
    assert (fresh.sb_weight_T.value(), fresh.sb_weight_R.value()) == (0.0, 1.0)


def test_every_editable_index_setting_is_saved_or_left_out_by_name(index_windows) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_index_ui_state import INDEX_CONFIG_OUTSIDE_TABLE, INDEX_CONFIG_TABLE

    assert_every_setting_is_in_the_table(index_windows[0], INDEX_CONFIG_TABLE, INDEX_CONFIG_OUTSIDE_TABLE)
