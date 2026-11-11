"""The RMSE margin of the robust interval has a name, and it is not the tolerance of the corridor calculation.

Two settings of the corridors look alike and are not the same quantity:

* `sp_corr_rmse_delta`, 2.5e-4 (`_DEFAULT_CORRIDOR_RMSE_DELTA`): the tolerance of the corridor **calculation**; it goes
  into the configuration of the solver.
* `sp_corridor_rmse_delta`, 2e-4: the RMSE margin of the **robust interval** drawn under the local parabola of the
  RMSE(d) tab. It was a bare `2e-4`, written six times in three modules: where the spin box is built, in the robust
  preset, three times as the value taken when the spin box or the result gives none, and as the floor of the height of
  the plot (audit of the corridors, Q12).

A bare literal that close to the other default invites a `fix` that would merge them. It has a name now, and no module
of the INDEX SPLINE window writes the literal any more.
"""

from __future__ import annotations

import ast
from pathlib import Path

from certus.ui import certus_index_spline_corridor_common as common

ROOT = Path(__file__).resolve().parents[2]
GROUP = sorted((ROOT / "certus" / "ui").glob("certus_index_spline*.py"))
NAME = "_DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA"
#: module -> how many times it reads the name
READERS = {"certus_index_spline_corridor_tab.py": 1, "certus_index_spline_corridor_interval.py": 1, "certus_index_spline_corridor_rmse_plot.py": 4}


def trees() -> dict[str, ast.Module]:
    return {path.name: ast.parse(path.read_text(encoding="utf-8-sig")) for path in GROUP}


def test_the_margin_keeps_its_value_and_is_not_the_tolerance_of_the_calculation():
    assert getattr(common, NAME) == 2e-4
    assert type(getattr(common, NAME)) is float
    assert common._DEFAULT_CORRIDOR_RMSE_DELTA == 2.5e-4


def test_no_module_of_the_window_writes_the_literal():
    written = {
        f"{name}:{node.lineno}"
        for name, tree in trees().items()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) is float and node.value == 2e-4
    }
    assert written == {"certus_index_spline_corridor_common.py:" + str(definition_line())}


def definition_line() -> int:
    [line] = [
        node.lineno
        for node in trees()["certus_index_spline_corridor_common.py"].body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == NAME
    ]
    return line


def test_the_six_places_read_the_name():
    read = {
        name: sum(isinstance(node, ast.Name) and node.id == NAME and isinstance(node.ctx, ast.Load) for node in ast.walk(tree))
        for name, tree in trees().items()
    }
    assert {name: count for name, count in read.items() if count} == READERS
