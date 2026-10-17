"""A child of ELITE (or of the local search) is its parent with other blocks, not a new strategy.

A strategy is (blocks, wavelengths, Rate layers, slit, and when the plan has one the testglass swaps). The children used to be built
from the blocks alone: a child of a Rate plan was a pure optical plan again, which crashed where its parent did not, so the one
generator that refines the plans could never refine a plan that lays layers by Rate (measured on `r75x0.5`: the Rate plans are the
only depositable ones, and ELITE could not move them). And a child of a slit variant was evaluated at the width of the run.
"""

from __future__ import annotations

import pytest

from certus.core.certus_strat_consensus import _generate_elite_candidate_strategies, _generate_local_search_neighborhood
from certus.core.certus_strat_ranking import _existing_block_signatures

WLS = [596.0, 598.0, 600.0, 602.0, 604.0, 616.0, 618.0, 620.0, 622.0, 624.0]
CARRIED = {"rate_layers": [5, 6], "monochromator_resolution_nm": 1.0, "witness_reset_layers": [4]}


def _blocks() -> list[dict]:
    return [{"start": 0, "end": 4, "wavelength": 600.0}, {"start": 4, "end": 8, "wavelength": 620.0}]


def _parent(**carried) -> dict:
    return {"strategy": {"strategy_id": 7, "n_blocks": 2, "blocks": _blocks(), **carried}}


def _elite_children(parent: dict) -> list[dict]:
    children, _ = _generate_elite_candidate_strategies([parent], WLS, num_layers=8, start_strategy_id=1000, max_candidates=60)
    return children


def _local_search_children(parent: dict) -> list[dict]:
    children, _ = _generate_local_search_neighborhood(parent["strategy"], WLS, 8, 1000, set())
    return children


@pytest.mark.parametrize("make_children", [_elite_children, _local_search_children], ids=["elite", "local search"])
def test_a_child_keeps_the_rate_layers_the_slit_and_the_swaps_of_its_parent(make_children) -> None:
    children = make_children(_parent(**CARRIED))

    assert children, "the generator produced no child: the test measures nothing"
    for child in children:
        for key, value in CARRIED.items():
            assert child.get(key) == value, f"{child['origin']}: {key} is {child.get(key)!r}, its parent's is {value!r}"


@pytest.mark.parametrize("make_children", [_elite_children, _local_search_children], ids=["elite", "local search"])
def test_the_carried_values_are_copies(make_children) -> None:
    parent = _parent(**CARRIED)

    for child in make_children(parent):
        child["rate_layers"].append(99)

    assert parent["strategy"]["rate_layers"] == [5, 6]


@pytest.mark.parametrize("make_children", [_elite_children, _local_search_children], ids=["elite", "local search"])
def test_a_pure_optical_parent_gives_children_without_those_keys(make_children) -> None:
    """The path of before, key for key: nothing is added to a child whose parent carries nothing."""
    children = make_children(_parent())

    assert children
    for child in children:
        assert not set(CARRIED) & set(child)


# ---- what makes a child a duplicate ----------------------------------------------------------------------------------------


def _again(parent: dict, existing: list[dict]) -> list[dict]:
    seen = _existing_block_signatures(existing)
    children, _ = _generate_elite_candidate_strategies(
        [parent], WLS, num_layers=8, start_strategy_id=2000, max_candidates=60, existing_signatures=seen
    )
    return children


def test_a_rate_child_is_not_a_duplicate_of_a_plan_with_its_blocks_and_other_rate_layers() -> None:
    """The tails of one parent share their blocks and differ by their cut: they are different plans."""
    parent = _parent(rate_layers=[5, 6])
    first = _elite_children(parent)[0]["blocks"]
    sibling = {"strategy": {"blocks": first, "rate_layers": [7]}}

    assert first in [c["blocks"] for c in _again(parent, [sibling])]


def test_a_rate_child_is_a_duplicate_of_the_plan_with_its_blocks_and_its_rate_layers() -> None:
    parent = _parent(rate_layers=[5, 6])
    first = _elite_children(parent)[0]["blocks"]
    same = {"strategy": {"blocks": first, "rate_layers": [6, 5]}}

    assert first not in [c["blocks"] for c in _again(parent, [same])]


def test_a_pure_optical_child_is_still_a_duplicate_of_any_plan_with_its_blocks() -> None:
    """The rule of before, untouched for the plans that lay nothing by Rate."""
    parent = _parent()
    first = _elite_children(parent)[0]["blocks"]
    rate_plan = {"strategy": {"blocks": first, "rate_layers": [7]}}

    assert first not in [c["blocks"] for c in _again(parent, [rate_plan])]
