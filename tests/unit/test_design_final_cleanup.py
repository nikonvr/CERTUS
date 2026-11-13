"""DESIGN's final cleanup: no thin layer is left, each one removed or raised, whichever costs less (owner, 2026-11-13).

The 5 nm rule removed every thin layer at once without re-optimizing: one layer lost took a 34-layer design from
RMSE 0.000161 to 0.001035 (reports/DESIGN_bs5050_2026-10-22/journal.md). The final cleanup treats the thinnest
layer first, tries it removed (neighbours of one material merged) and raised to its floor, re-polishes both and
keeps the better, until no variable layer is under its floor; then it polishes the whole design above the floors.

These tests use a cost written by hand, whose minimum is known: the algorithm is judged without the physics.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_final_cleanup import final_cleanup

FLOOR = 5.0


def _quadratic(targets_by_layout: dict[tuple[str, ...], list[float]], missing: float = 1.0):
    """A cost factory: for each known layout, the squared distance to its ideal thicknesses; `missing` elsewhere."""

    def make_cost(materials):
        ideal = targets_by_layout.get(tuple(materials))

        def cost_and_grad(ep, var_idx):
            if ideal is None:
                return missing, np.zeros(len(var_idx))
            diff = np.asarray(ep, dtype=float) - np.asarray(ideal, dtype=float)
            return float(diff @ diff) * 1e-4, 2e-4 * diff[var_idx]

        return cost_and_grad

    return make_cost


def _run(materials, ep, make_cost, var=None, floor=FLOOR):
    var = [True] * len(materials) if var is None else var
    return final_cleanup(materials, np.asarray(ep, dtype=float), var, lambda name: floor, make_cost)


def test_a_design_without_a_thin_layer_keeps_its_layers() -> None:
    make_cost = _quadratic({("H", "L", "H"): [80.0, 120.0, 60.0]})
    result = _run(["H", "L", "H"], [80.0, 120.0, 60.0], make_cost)
    assert result.materials == ["H", "L", "H"]
    assert result.steps == []
    assert result.ep == pytest.approx([80.0, 120.0, 60.0], abs=1e-6)


def test_a_useless_thin_layer_is_removed_and_its_neighbours_merged() -> None:
    """H 80 / L 1 / H 60: without the L layer the two H layers are one of 140, which the cost likes as well."""
    make_cost = _quadratic({("H", "L", "H"): [80.0, 1.0, 60.0], ("H",): [140.0]})
    result = _run(["H", "L", "H"], [80.0, 1.0, 60.0], make_cost)
    assert result.materials == ["H"]
    assert result.ep == pytest.approx([140.0], abs=1e-4)
    assert [s.action for s in result.steps] == ["removed"]
    assert result.steps[0].material == "L"
    assert result.steps[0].thickness == pytest.approx(1.0)


def test_a_thin_layer_the_design_needs_is_raised_to_its_floor() -> None:
    """Removing the L layer leaves a layout the cost rejects: raised to the floor it costs (5 - 3)^2, far less."""
    make_cost = _quadratic({("H", "L", "H"): [80.0, 3.0, 60.0]}, missing=1.0)
    result = _run(["H", "L", "H"], [80.0, 3.0, 60.0], make_cost)
    assert result.materials == ["H", "L", "H"]
    assert result.ep[1] == pytest.approx(FLOOR)
    assert [s.action for s in result.steps] == ["raised"]
    assert result.steps[0].cost_removed == pytest.approx(1.0)
    assert result.steps[0].cost_raised < result.steps[0].cost_removed


def test_no_variable_layer_is_left_under_its_floor() -> None:
    layouts = {
        ("H", "L", "H", "L", "H"): [80.0, 2.0, 60.0, 4.0, 90.0],
        ("H", "L", "H"): [80.0, 4.0, 150.0],
        ("H", "L", "H", "L"): [80.0, 2.0, 60.0, 4.0],
    }
    result = _run(["H", "L", "H", "L", "H"], [80.0, 2.0, 60.0, 4.0, 90.0], _quadratic(layouts, missing=0.5))
    assert all(d >= FLOOR for d in result.ep), result.ep
    assert len(result.steps) == 2
    assert result.cost <= 0.5


def test_the_thinnest_layer_is_treated_first() -> None:
    layouts = {("H", "L", "H", "L", "H"): [80.0, 4.0, 60.0, 2.0, 90.0]}
    result = _run(["H", "L", "H", "L", "H"], [80.0, 4.0, 60.0, 2.0, 90.0], _quadratic(layouts))
    assert result.steps[0].thickness == pytest.approx(2.0)


def test_a_layer_the_operator_fixed_is_left_alone() -> None:
    make_cost = _quadratic({("H", "L", "H"): [80.0, 1.0, 60.0], ("H",): [140.0]})
    result = _run(["H", "L", "H"], [80.0, 1.0, 60.0], make_cost, var=[True, False, True])
    assert result.materials == ["H", "L", "H"]
    assert result.ep[1] == pytest.approx(1.0)
    assert result.steps == []
    assert result.kept_fixed == [1]


def test_the_last_layer_of_a_stack_is_raised_not_removed() -> None:
    make_cost = _quadratic({("H",): [2.0]})
    result = _run(["H"], [2.0], make_cost)
    assert result.materials == ["H"]
    assert result.ep == pytest.approx([FLOOR])
    assert [s.action for s in result.steps] == ["raised"]


def test_the_surviving_layers_say_where_they_came_from() -> None:
    """`origin` names the row each final layer had at the start: the window keeps its flags by it."""
    make_cost = _quadratic({("H", "L", "H", "L"): [80.0, 1.0, 60.0, 100.0], ("H", "L"): [140.0, 100.0]})
    result = _run(["H", "L", "H", "L"], [80.0, 1.0, 60.0, 100.0], make_cost)
    assert result.materials == ["H", "L"]
    assert result.origin == [0, 3]


def test_the_final_polish_never_ends_worse_than_it_started() -> None:
    """A cost whose gradient lies cannot make the cleanup accept a worse design."""

    def make_cost(materials):
        def cost_and_grad(ep, var_idx):
            return float(np.sum(np.asarray(ep) ** 2)) * 1e-6, -np.ones(len(var_idx))  # gradient points uphill

        return cost_and_grad

    result = _run(["H", "L"], [80.0, 120.0], make_cost)
    assert result.cost <= result.cost_start
