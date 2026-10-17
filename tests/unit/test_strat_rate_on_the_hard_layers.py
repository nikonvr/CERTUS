"""The Rate rescue also lays by Rate the layers where the optical monitoring gives way, a few more every round, and nothing else.

👤 2026-10-12: *"Rate should be favoured on the layers that are hard to control optically"*. A tail lays by Rate the layers it does not need
to as well, and a Rate layer corrects nothing; this reads the layers where the draws first crash, lays those by Rate, and does it again
with the plans that improved and still do not terminate.
"""

from __future__ import annotations

import logging

import numpy as np

from certus.core.certus_strat_robustness_rate import (
    RATE_RESCUE_COVERAGE,
    RATE_RESCUE_PER_ROUND,
    _first_crash_profile,
    _hard_layer_rounds,
    _hard_layers,
    _rescue_with_rate,
)
from certus_physics import CRASH_LEVEL_UNREACHABLE, CRASH_SENTINEL_UNIT

N_LAYERS = 14
RUNS = 100
CRASHED = 100.0 + CRASH_LEVEL_UNREACHABLE * CRASH_SENTINEL_UNIT


def _item(first_crashes: dict[int, int], *, rate_layers=None, sid=1, crash_rate=None, score=float("inf")) -> dict:
    """A result whose draws first crash at the given layers: `{layer: how many draws}`."""
    thick = np.full((RUNS, N_LAYERS), 100.0)
    row = 0
    for layer, count in first_crashes.items():
        thick[row : row + count, layer:] = CRASHED
        row += count
    strategy = {"strategy_id": sid, "blocks": [{"start": 0, "end": N_LAYERS, "wavelength": 600.0}]}
    if rate_layers is not None:
        strategy["rate_layers"] = list(rate_layers)
    return {
        "strategy": strategy,
        "strategy_id": sid,
        "results_per_noise": [{"noise_level": 0.05, "thicknesses_all": thick.tolist()}],
        "robustness_score": score,
        "crash_rate": row / RUNS if crash_rate is None else crash_rate,
    }


# ---- where the draws first crash -------------------------------------------------------------------------------------------


def test_the_profile_is_the_share_of_all_the_draws_that_first_crash_at_each_layer() -> None:
    profile = _first_crash_profile(_item({6: 30, 9: 20}), N_LAYERS)

    assert profile[6] == 0.3
    assert profile[9] == 0.2
    assert profile.sum() == 0.5


def test_a_plan_that_never_crashes_has_no_profile() -> None:
    assert _first_crash_profile(_item({}), N_LAYERS) is None


# ---- the layers to lay by Rate ---------------------------------------------------------------------------------------------


def test_the_layers_where_most_draws_first_crash_come_first_and_the_round_stops_when_it_covers_enough() -> None:
    item = _item({6: 30, 9: 20, 11: 3, 12: 2})

    layers = _hard_layers(item, N_LAYERS, set())

    assert layers == [6, 9]  # 50 % of the 55 % of crashes: more than the share a round has to cover
    assert 0.5 >= RATE_RESCUE_COVERAGE * 0.55 - 0.05


def test_a_round_takes_at_most_a_few_layers() -> None:
    item = _item({layer: 5 for layer in range(2, 12)})

    assert len(_hard_layers(item, N_LAYERS, set())) == RATE_RESCUE_PER_ROUND


def test_a_layer_already_laid_by_rate_is_not_chosen_again() -> None:
    item = _item({6: 30, 9: 20})

    assert _hard_layers(item, N_LAYERS, {6}) == [9]


def test_layers_zero_and_one_are_never_chosen_and_a_plan_that_crashes_there_is_given_up() -> None:
    assert _hard_layers(_item({0: 10, 6: 30}), N_LAYERS, set()) == []
    assert _hard_layers(_item({1: 3, 6: 30}), N_LAYERS, set()) == []
    assert _hard_layers(_item({1: 2, 6: 30}), N_LAYERS, set()) == [6]  # 2 % is under the leak


# ---- the rounds ------------------------------------------------------------------------------------------------------------


class _Chain:
    """Stands for the evaluation: 10 draws in 100 crash for each of the hard layers 6, 9 and 11 the plan does not lay by Rate, all at the first."""

    HARD = (6, 9, 11)

    def __init__(self) -> None:
        self.rounds: list[list[dict]] = []

    def __call__(self, strategies: list[dict]) -> list[dict]:
        self.rounds.append(strategies)
        out = []
        for s in strategies:
            missing = [layer for layer in self.HARD if layer not in (s.get("rate_layers") or [])]
            done = not missing
            item = _item({missing[0]: 10 * len(missing)} if missing else {}, rate_layers=s.get("rate_layers"), sid=s["strategy_id"], score=0.05 if done else float("inf"))
            item["strategy"] = dict(s)
            out.append(item)
        return out


def test_the_rounds_lay_one_more_cluster_of_layers_each_time_until_the_plan_terminates() -> None:
    chain = _Chain()
    raw = [_item({6: 30})]

    results = _hard_layer_rounds(raw, chain, N_LAYERS, plans_count=3, rounds_count=8, source_n_blocks=1)

    assert [sorted(s["rate_layers"]) for rnd in chain.rounds for s in rnd] == [[6], [6, 9], [6, 9, 11]]
    assert [s["origin"].split("(")[0] for rnd in chain.rounds for s in rnd] == ["RATE_HARD1", "RATE_HARD2", "RATE_HARD3"]
    assert len(results) == 3
    assert np.isfinite(results[-1]["robustness_score"])


def test_the_rounds_stop_at_the_number_asked_for() -> None:
    chain = _Chain()

    _hard_layer_rounds([_item({6: 30})], chain, N_LAYERS, plans_count=3, rounds_count=2, source_n_blocks=1)

    assert len(chain.rounds) == 2


def test_a_plan_that_does_not_improve_is_not_followed() -> None:
    """A round that lowers no crash rate would only spend evaluations: the frontier keeps the plans that improved."""

    def stuck(strategies: list[dict]) -> list[dict]:
        return [dict(_item({6: 30}, rate_layers=s.get("rate_layers"), sid=s["strategy_id"], crash_rate=1.0), strategy=dict(s)) for s in strategies]

    calls = []

    def collect(strategies):
        calls.append(strategies)
        return stuck(strategies)

    _hard_layer_rounds([_item({6: 30}, crash_rate=1.0)], collect, N_LAYERS, plans_count=3, rounds_count=8, source_n_blocks=1)

    assert len(calls) == 1


def test_the_children_have_distinct_ids_outside_the_tail_range() -> None:
    chain = _Chain()

    _hard_layer_rounds([_item({6: 30}, sid=1), _item({6: 30}, sid=2)], chain, N_LAYERS, plans_count=3, rounds_count=8, source_n_blocks=1)

    ids = [s["strategy_id"] for rnd in chain.rounds for s in rnd]
    assert len(set(ids)) == len(ids)


def test_the_plans_that_terminated_are_not_parents() -> None:
    chain = _Chain()

    assert _hard_layer_rounds([_item({}, score=0.05, crash_rate=0.0)], chain, N_LAYERS, plans_count=3, rounds_count=8, source_n_blocks=1) == []
    assert chain.rounds == []


# ---- in the stage ----------------------------------------------------------------------------------------------------------


def test_the_stage_places_the_rate_on_the_hard_layers_only_when_asked_to() -> None:
    """Inactive by default until it is measured (the golden rule): the tails alone, as before it existed."""
    raw = [_item({6: 30})]
    log = logging.getLogger("hard")
    default, asked = _Chain(), _Chain()

    _rescue_with_rate(raw, default, {}, N_LAYERS, 1, log)
    _rescue_with_rate(raw, asked, {"rate_rescue_hard": True}, N_LAYERS, 1, log)

    assert all(s["origin"].startswith("RATE_RESCUE") for call in default.rounds for s in call)
    assert any(s["origin"].startswith("RATE_HARD") for call in asked.rounds for s in call)
