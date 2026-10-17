"""The automatic cleanups of DESIGN never delete a layer whose thickness the operator fixed.

`_apply_5nm_minimum` removed every layer under 5 nm, and `smart_cleanup` every layer under its adaptive threshold, whatever
the `var` flag: a fixed 2 nm layer disappeared at the end of a workflow (D08 and U01, designargon section 7.1). A layer the
operator fixed is a constraint of the design, not an artefact of the optimisation.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from certus.ui.certus_design_ui_optimization import OptimizationManager


def _ui(thicknesses: list[float], variable: list[bool]) -> MagicMock:
    """A window double with a front table of `len(thicknesses)` rows, the `variable` flags saying which may be optimised."""
    ui = MagicMock()
    ui.ep_current = np.asarray(thicknesses, dtype=float)
    ui._get_front_stack.return_value = [SimpleNamespace(mat="H", qwot=1.0, var=v) for v in variable]
    ui.front_table.rowCount.return_value = len(thicknesses)
    ui._workflow_best_rmse = 1.0
    ui._cleanup_threshold_multiplier = 150.0
    return ui


def _removed_rows(ui: MagicMock) -> list[int]:
    return [call.args[0] for call in ui.front_table.removeRow.call_args_list]


def test_the_5nm_rule_keeps_a_fixed_layer_thinner_than_5nm() -> None:
    ui = _ui([2.0, 5.0, 3.0], [False, True, True])

    OptimizationManager(ui)._apply_5nm_minimum()

    assert _removed_rows(ui) == [2]


def test_the_5nm_rule_still_removes_thin_variable_layers() -> None:
    ui = _ui([2.0, 6.0, 3.0], [True, True, True])

    OptimizationManager(ui)._apply_5nm_minimum()

    assert _removed_rows(ui) == [2, 0]


def test_smart_cleanup_keeps_a_fixed_layer_under_the_threshold() -> None:
    ui = _ui([0.5, 10.0, 0.8, 12.0], [False, True, True, True])

    OptimizationManager(ui).smart_cleanup()

    assert _removed_rows(ui) == [2]


def test_smart_cleanup_still_removes_thin_variable_layers() -> None:
    ui = _ui([0.5, 10.0, 0.8, 12.0], [True, True, True, True])

    OptimizationManager(ui).smart_cleanup()

    assert _removed_rows(ui) == [2, 0]
