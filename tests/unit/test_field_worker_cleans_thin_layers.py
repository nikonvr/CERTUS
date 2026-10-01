"""`FieldWorkerThread._clean_and_reoptimize` removes the layers thinner than `dmin`, merges the neighbours it leaves side by side, and re-optimises (audit v2, plan S5.2).

It was a function nested in `_run_optimize` (432 lines, no unit test reaches it), closing over `dmin` and `params`; it is now a method that takes both. The behaviour pinned here:

    nothing is thinner than `dmin`          the stack comes back as it came, `cleaned` is False and there is no cost
    a layer is thinner than `dmin`          it goes (the thinnest first), same-type neighbours that become adjacent are merged by adding their QWOT, the rest is re-optimised
    every layer is thinner                  nothing is removed (an empty stack is not a design)
    the user stops the worker               the cost function raises `InterruptedError`
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.workers import certus_field_workers
from certus.workers.certus_field_workers import FieldWorkerThread

L0 = 550.0
N_H, N_L = 2.2, 1.5  # type 0 is read with n1_rs, type 1 with n2_rs


def nm(qwot: float, n: float) -> float:
    return qwot * (L0 / 4.0) / n


def params(**changes) -> SimpleNamespace:
    base = dict(
        n1_rs=[N_L], n2_rs=[N_H], nSub_rs=[1.52], l0=L0, seuil_int_1=0.1, seuil_int_2=0.1, alpha=1.0, integral_points=10, n_supers=1.0, theta_inc=0.0,
        pol_flag=0, lambda_calcs=[L0], rmin=1.0, rmax=1.0, min_field_active=False, maxiter=30,
    )
    base.update(changes)
    return SimpleNamespace(**base)


class CostCalls(list):
    """The vectors the cost was asked about, and (in `types`) the layer types it was given each time."""

    def __init__(self) -> None:
        super().__init__()
        self.types: list[tuple[int, ...]] = []


@pytest.fixture
def cost(monkeypatch):
    """The field cost is replaced by a bowl around QWOT 1.0 per layer: the re-optimisation then has a known answer."""
    calls = CostCalls()

    def bowl(p, *args, **kwargs):
        calls.append(tuple(np.asarray(p, dtype=float)))
        calls.types.append(tuple(args[12]))  # the 14th positional argument of the field objective: the layer types
        return float(np.sum((np.asarray(p, dtype=float) - 1.0) ** 2))

    monkeypatch.setattr(certus_field_workers, "top_level_objective_function", bowl)
    return calls


def worker(running: bool = True) -> SimpleNamespace:
    return SimpleNamespace(_is_running=running)


def clean(x, types, *, dmin=5.0, running=True, **changes):
    return FieldWorkerThread._clean_and_reoptimize(worker(running), list(x), list(types), dmin, params(**changes))


def test_a_stack_with_no_thin_layer_comes_back_unchanged(cost):
    x, types, cleaned, final_cost = clean([1.0, 0.9, 1.1], [0, 1, 0])
    assert (x, types, cleaned, final_cost) == ([1.0, 0.9, 1.1], [0, 1, 0], False, None)
    assert cost == []


def test_an_empty_stack_stays_empty(cost):
    assert clean([], []) == ([], [], False, None)


def test_the_thin_layer_goes_and_its_equal_neighbours_are_merged(cost):
    thin = 0.01  # QWOT well under dmin at either index
    assert nm(thin, N_H) < 5.0
    x, types, cleaned, final_cost = clean([1.0, thin, 1.0], [0, 1, 0])
    assert cleaned is True
    assert types == [0]  # the two type-0 layers became neighbours and were merged
    assert len(x) == 1
    assert x[0] == pytest.approx(1.0, abs=1e-3)  # the bowl's minimum
    assert final_cost == pytest.approx(0.0, abs=1e-6)


def test_the_neighbours_of_a_different_type_are_not_merged(cost):
    x, types, cleaned, _ = clean([1.0, 0.01, 0.9, 1.1], [0, 1, 1, 0])
    # the thin type-1 layer goes; the type-1 layer after it stays between two type-0 layers
    assert cleaned is True
    assert types == [0, 1, 0]
    assert len(x) == 3


def test_the_first_iteration_starts_from_the_merged_sum(cost):
    clean([1.0, 0.01, 1.0], [0, 1, 0])
    assert cost[0] == (2.0,)  # 1.0 + 1.0, before the optimiser moves


def test_when_every_layer_is_thinner_than_dmin_nothing_is_removed(cost):
    x, types, cleaned, final_cost = clean([0.01, 0.02], [0, 1])
    assert (x, types, cleaned, final_cost) == ([0.01, 0.02], [0, 1], False, None)


def test_the_thinnest_goes_first_and_the_loop_stops_when_none_is_thin_any_more(cost):
    """Two thin layers: the thinner one (0.01) goes first and its type-0 neighbours merge. The re-optimisation then thickens the other thin layer (the bowl asks QWOT 1.0 of everyone), so the loop ends on three layers."""
    x, types, cleaned, _ = clean([1.0, 0.03, 1.0, 0.01, 1.0], [0, 1, 0, 1, 0])
    assert cleaned is True
    assert types == [0, 1, 0]
    np.testing.assert_allclose(x, [1.0, 1.0, 1.0], atol=1e-3)
    assert cost[0] == (1.0, 0.03, 2.0)  # the first evaluation: the 0.01 layer gone, its neighbours added


def test_each_type_is_read_with_its_own_index(cost):
    """QWOT 0.07 is 6.4 nm at the index of type 0 (kept, above 5 nm) and 4.4 nm at the index of type 1 (thin, removed)."""
    assert nm(0.07, N_L) > 5.0 > nm(0.07, N_H)
    kept = clean([1.0, 0.07, 1.0], [1, 0, 1])
    assert kept[2] is False
    removed = clean([1.0, 0.07, 1.0], [0, 1, 0])
    assert removed[2] is True


def test_a_lone_thin_layer_is_kept_whatever_its_type(cost):
    """The 'everything is thin' exit reads each layer with its own index too: a single type-1 layer of 4.4 nm is not removed (an empty stack is not a design)."""
    assert nm(0.07, N_H) < 5.0
    assert clean([0.07], [1]) == ([0.07], [1], False, None)
    assert clean([0.01], [0]) == ([0.01], [0], False, None)


def test_the_re_optimisation_is_given_the_merged_types_not_the_original_ones(cost):
    clean([1.0, 0.01, 1.0], [0, 1, 0])
    assert set(cost.types) == {(0,)}


def test_a_stopped_worker_interrupts_the_re_optimisation(cost):
    with pytest.raises(InterruptedError):
        clean([1.0, 0.01, 1.0], [0, 1, 0], running=False)


def test_the_optimisation_hands_it_the_minimum_thickness_and_the_parameters():
    # the calls live in the cleaning stage of the optimization since it became a method of its own (S5.2)
    source = inspect.getsource(FieldWorkerThread._clean_the_thin_layers_of_the_solutions)
    calls = source.split("self._clean_and_reoptimize(")[1:]
    assert len(calls) == 2  # the best solution, then every other one
    for call in calls:
        arguments = call.split(")")[0]
        assert "dmin" in arguments
        assert "params" in arguments
