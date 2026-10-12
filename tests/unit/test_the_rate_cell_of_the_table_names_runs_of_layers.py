"""The Rate column of the strategies table names runs of layers: a plan that lays 58 layers by Rate reads `L18-L75`, not 58 numbers.

The Rate rescue lays everything from a layer to the end by Rate (👤 2026-10-12), so the cell of a winner is a run, and a list of 58 names
did not fit the column nor tell the operator where the optical monitoring stops.
"""

from __future__ import annotations

import pytest

from certus.ui.certus_strat_table_ui import layer_ranges


@pytest.mark.parametrize(
    ("indices", "text"),
    [
        ([], ""),
        ([4], "L5"),
        ([1, 4], "L2, L5"),
        ([17, 18, 19, 25], "L18-L20, L26"),
        (list(range(17, 75)), "L18-L75"),
        ([30, 29, 28, 3], "L4, L29-L31"),
        ([5, 5, 6], "L6-L7"),
    ],
)
def test_runs_of_layers_are_named_once(indices, text) -> None:
    assert layer_ranges(indices) == text
