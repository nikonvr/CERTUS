"""STRAT saves and loads its settings through one table (certus/ui/certus_config_table.py).

The audit of 2026-11-15 found ``thickness_tolerance_nm`` read by the computation and never saved (M-L6d): the save
listed its keys by hand while the load took any text field. Both now read ``STRAT_CONFIG_TABLE``.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

# STRAT loads a configuration file through this method; it has no `_apply_config` (its session goes through a file).
_LOAD = "populate_gui_from_config"


@pytest.fixture
def strat_windows(qapp):
    from PyQt6.QtCore import Qt

    from certus.ui.certus_strat_ui import CertusStratApp

    wins = []

    def make():
        win = CertusStratApp()
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        wins.append(win)
        return win

    try:
        yield make
    finally:
        for win in wins:
            win.close()


def test_every_setting_of_the_strat_table_comes_back(strat_windows) -> None:
    from config_table_checks import assert_round_trip

    from certus.ui.certus_strat_ui_state import STRAT_CONFIG_TABLE

    carried = assert_round_trip(strat_windows(), strat_windows(), STRAT_CONFIG_TABLE, load=_LOAD)
    # The rows saved only under the other position of their switch: alone, on windows left at their defaults.
    rest = tuple(f.key for f in STRAT_CONFIG_TABLE if f.key in carried)
    carried |= assert_round_trip(strat_windows(), strat_windows(), STRAT_CONFIG_TABLE, skip=rest, load=_LOAD)

    assert carried == {f.key for f in STRAT_CONFIG_TABLE}


def test_the_strat_configuration_keeps_its_keys(strat_windows) -> None:
    from certus.ui.certus_strat_ui_state import STRAT_CONFIG_TABLE

    win = strat_windows()
    cfg = win._collect_config()

    assert {f.key for f in STRAT_CONFIG_TABLE if f.saved_if is None} <= set(cfg)
    assert {"stack_multipliers", "show_plots", "export_excel", "force_first_layer_same_wl"} <= set(cfg)
    assert ("nH_r" in cfg) != ("h_material_file" in cfg)
    assert ("nL_r" in cfg) != ("l_material_file" in cfg)


def test_every_editable_strat_setting_is_saved_or_left_out_by_name(strat_windows) -> None:
    from config_table_checks import assert_every_setting_is_in_the_table

    from certus.ui.certus_strat_ui_state import STRAT_CONFIG_OUTSIDE_TABLE, STRAT_CONFIG_TABLE

    assert_every_setting_is_in_the_table(strat_windows(), STRAT_CONFIG_TABLE, STRAT_CONFIG_OUTSIDE_TABLE)
