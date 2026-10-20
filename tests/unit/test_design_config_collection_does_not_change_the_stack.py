"""Reading the DESIGN configuration must not rewrite the operator's stack.

`StateManager._collect_config` used to start with the pre-save cleanup, which removes the thin layers and merges the
neighbours of the front table in place. `_config_snapshot` (base mixin) calls `_collect_config` to compare the window with
the saved file at opening and at closing, so merely closing the window, or asking whether the project is saved, changed the
stack (UX-01 in docs/AUDITS.md). The cleanup stays an explicit step of the save flow (`save_config` runs it itself).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from certus.ui.certus_design_ui_state import StateManager


def _ui(rows: int = 3, removed: int = 2) -> MagicMock:
    """A window double whose cleanup would remove `removed` layers of a table of `rows` rows."""
    ui = MagicMock()
    ui.front_table.rowCount.return_value = rows
    ui.smart_cleanup.return_value = removed
    ui.oblique_mode = False
    ui.mat_widgets = {}
    ui._get_front_stack.return_value = []
    ui._get_back_stack.return_value = []
    ui._get_tgts.return_value = []
    ui._get_oblique_tgts.return_value = []
    return ui


def test_collecting_the_configuration_does_not_clean_the_stack() -> None:
    ui = _ui()

    StateManager(ui)._collect_config()

    ui.smart_cleanup.assert_not_called()


def test_collecting_the_configuration_does_not_schedule_an_evaluation_of_a_cleaned_stack() -> None:
    ui = _ui()

    StateManager(ui)._collect_config()

    ui._schedule_eval.assert_not_called()


def test_the_pre_save_cleanup_is_still_there_as_an_explicit_step() -> None:
    """The save flow keeps its cleanup: only the hidden call inside the collection is gone."""
    ui = _ui()

    StateManager(ui)._pre_save_smart_cleanup()

    ui.smart_cleanup.assert_called_once()
