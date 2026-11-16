"""INDEX SPLINE saves and loads its fit settings through one table (certus/ui/certus_config_table.py).

Its save and its load named the settings in two hand-written lists, the class of defect the audit of 2026-11-15 found
in the other windows (M-L5b, M-L6d). The owner decided on 2026-11-16 that the configuration keeps the fit settings
only: the corridor analysis, the automatic cleanup and the display are named as left out.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def spline_windows(qapp):
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    wins = [CertusIndexSplineApp(), CertusIndexSplineApp()]
    yield wins
    for win in wins:
        win.close()


def test_the_index_spline_configuration_keeps_its_keys(spline_windows) -> None:
    assert set(spline_windows[0]._collect_config()) == {
        "fit_t", "fit_t_ratio", "fit_r", "weight_t", "weight_r", "substrate", "profile", "d_nominal_nm",
        "d_tolerance_nm", "mesh_min_dlambda_over_lambda", "rmse_fit_lambda_enabled", "rmse_fit_lambda_lo_nm",
        "rmse_fit_lambda_hi_nm",
    }


def test_every_setting_of_the_index_spline_table_comes_back(spline_windows) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_index_spline_state_mixin import INDEX_SPLINE_CONFIG_TABLE

    carried = assert_round_trip(*spline_windows, INDEX_SPLINE_CONFIG_TABLE)

    assert carried == {f.key for f in INDEX_SPLINE_CONFIG_TABLE}


def test_an_unknown_substrate_is_refused_before_anything_is_loaded(spline_windows) -> None:
    source, fresh = spline_windows
    source.w_t.setValue(source.w_t.value() + 0.5)
    cfg = {**source._collect_config(), "substrate": "no-such-substrate"}

    with pytest.raises(ValueError, match="Unknown INDEX SPLINE substrate"):
        fresh._apply_config(cfg)

    assert fresh.w_t.value() != source.w_t.value()


def test_every_editable_index_spline_setting_is_saved_or_left_out_by_name(spline_windows) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_index_spline_state_mixin import (
        INDEX_SPLINE_CONFIG_OUTSIDE_TABLE,
        INDEX_SPLINE_CONFIG_TABLE,
    )

    assert_every_setting_is_in_the_table(spline_windows[0], INDEX_SPLINE_CONFIG_TABLE, INDEX_SPLINE_CONFIG_OUTSIDE_TABLE)
