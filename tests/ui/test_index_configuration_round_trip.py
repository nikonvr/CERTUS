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
