"""RE saves and loads its settings through two tables (certus/ui/certus_config_table.py).

The save and ``load_config`` named the RE settings in two hand-written lists, the class of defect the audit of
2026-11-15 found in the other windows (M-L5b, M-L6d). Both now read ``RE_CONFIG_TABLE`` and ``RE_GUI_TABLE``.
"""

from __future__ import annotations

import pytest

# RE loads a configuration file through `load_config`; the settings part of it, the workbook apart, is this method.
_LOAD = "_apply_re_config"


@pytest.fixture
def re_windows(qapp):
    from CERTUS_RE import CertusREApp

    wins = [CertusREApp(), CertusREApp()]
    yield wins
    for win in wins:
        win.close()


def test_the_re_configuration_keeps_its_keys(re_windows) -> None:
    cfg = re_windows[0]._collect_config()

    assert set(cfg) == {"l0", "re_gui"}
    assert set(cfg["re_gui"]) == {
        "re_speed_mode", "re_phase2b_substrate_cauchy", "re_refine_h", "re_refine_l", "re_enable_qwot_penalty",
        "re_fit_lambda_min_nm", "re_fit_lambda_max_nm", "re_beam_aperture",
    }


def test_every_setting_of_the_re_tables_comes_back(re_windows) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_re_state_mixin import RE_CONFIG_TABLE, RE_GUI_TABLE

    # The two tables are loaded from the same dictionary in `assert_round_trip`: the re_gui rows from its block.
    source, fresh = re_windows
    assert_round_trip(source, fresh, RE_CONFIG_TABLE, load=_LOAD)
    carried = assert_round_trip(source, fresh, RE_GUI_TABLE, load=_LOAD)

    assert carried == {f.key for f in RE_GUI_TABLE}


def test_a_saved_re_configuration_file_comes_back(re_windows, tmp_path) -> None:
    import json

    source, fresh = re_windows
    source.re_speed_fast_radio.setChecked(True)
    source.l0_spin.setValue(source.l0_spin.value() + 10.0)
    path = tmp_path / "re.json"
    path.write_text(json.dumps(source._collect_config()), encoding="utf-8")

    assert fresh.load_config(str(path)) is True

    assert fresh._collect_config() == source._collect_config()


def test_every_editable_re_setting_is_saved_or_left_out_by_name(re_windows) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_re_state_mixin import RE_CONFIG_OUTSIDE_TABLE, RE_CONFIG_TABLE, RE_GUI_TABLE

    assert_every_setting_is_in_the_table(re_windows[0], RE_CONFIG_TABLE + RE_GUI_TABLE, RE_CONFIG_OUTSIDE_TABLE)
