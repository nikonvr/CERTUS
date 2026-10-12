"""The Rate rescue: a plan that does not terminate is laid by Rate from the layer where its optical monitoring gives way.

👤 2026-10-12: Rate must be integrated in every scenario, and still more when few depositable plans are found; `r75x0.5` (one
testglass) is the test, and it must end by finding plans, even if everything is finished by Rate.

📏 Measured on `r75x0.5`, seed 101: none of the 2 897 plans terminated with one Rate layer per variant; with the monitoring kept
up to layer 16 to 28 and everything after laid by Rate, 522 of 547 did (best SEEL 0.555 nm).
"""

from __future__ import annotations

import itertools
import logging

import numpy as np
import pytest

from certus.core.certus_strat_robustness_rate import (
    RATE_MIN_LAYER,
    RATE_RESCUE_FULL,
    RATE_RESCUE_LIGHT,
    RATE_RESCUE_SERIAL_BASE,
    _first_crash_layer,
    _rescue_budget,
    _rescue_cuts,
    _rescue_variants,
    _rescue_with_rate,
)
from certus_physics import CRASH_LEVEL_UNREACHABLE, CRASH_SENTINEL_UNIT

N_LAYERS = 12
LOG = logging.getLogger("test_rate_rescue")


def _level(crashes: dict[int, int], runs: int = 100) -> dict:
    """One noise level: `crashes` maps a layer to the number of draws that crash there (the sentinel of the kernel)."""
    thick = np.full((runs, N_LAYERS), 100.0)
    row = 0
    for layer, count in crashes.items():
        for _ in range(count):
            thick[row, layer:] = 100.0 + CRASH_LEVEL_UNREACHABLE * CRASH_SENTINEL_UNIT
            row += 1
    return {"noise_level": 0.05, "thicknesses_all": thick.tolist()}


def _item(crashes_by_level: list[dict[int, int]], *, blocks=None, rate_layers=None, score=float("inf"), crash_rate=1.0, sid=1) -> dict:
    strategy = {
        "strategy_id": sid,
        "blocks": blocks or [{"start": 0, "end": N_LAYERS, "wavelength": 600.0}],
        "slit_profile": [0.0] * N_LAYERS,
        "monochromator_resolution_nm": 2.0,
    }
    if rate_layers is not None:
        strategy["rate_layers"] = rate_layers
    return {
        "strategy": strategy,
        "strategy_id": sid,
        "results_per_noise": [_level(c) for c in crashes_by_level],
        "robustness_score": score,
        "crash_rate": crash_rate,
    }


# ---- where the monitoring gives way ----------------------------------------------------------------------------------------


def test_the_first_crash_layer_is_the_first_where_the_crashed_draws_exceed_the_leak() -> None:
    item = _item([{3: 1, 7: 5}])  # 1 % have crashed by layer 3 (under the leak), 6 % by layer 7

    assert _first_crash_layer(item, N_LAYERS) == 7


def test_a_crash_over_the_leak_at_once_gives_its_own_layer() -> None:
    assert _first_crash_layer(_item([{4: 5, 9: 3}]), N_LAYERS) == 4


def test_the_noise_level_that_crashes_most_decides() -> None:
    item = _item([{9: 4}, {5: 8}, {2: 1}])

    assert _first_crash_layer(item, N_LAYERS) == 5


def test_a_plan_that_never_crashes_has_no_first_crash_layer() -> None:
    assert _first_crash_layer(_item([{}]), N_LAYERS) is None


def test_a_result_without_its_draws_has_no_first_crash_layer() -> None:
    """The draws of the plans past the thirty best are emptied at the end of the run: nothing to read, nothing invented."""
    item = _item([{4: 10}])
    item["results_per_noise"][0]["thicknesses_all"] = []

    assert _first_crash_layer(item, N_LAYERS) is None


# ---- the cuts --------------------------------------------------------------------------------------------------------------


def test_the_cuts_go_from_the_layer_that_gives_way_down_to_layer_two() -> None:
    assert _rescue_cuts(22, 6) == [22, 18, 14, 10, 6, 2]


def test_the_last_cut_lays_everything_by_rate() -> None:
    cuts = _rescue_cuts(40, 8)

    assert cuts[0] == 40
    assert cuts[-1] == RATE_MIN_LAYER == 2
    assert cuts == sorted(set(cuts), reverse=True)


def test_a_plan_that_gives_way_early_has_fewer_cuts_than_asked() -> None:
    assert _rescue_cuts(5, 8) == [5, 4, 3, 2]


@pytest.mark.parametrize(("first", "count"), [(0, 4), (1, 4), (9, 0)])
def test_no_cut_when_layer_zero_or_one_gives_way_or_nothing_is_asked(first: int, count: int) -> None:
    """Layers 0 and 1 have no layer of their parity laid before them: the rate of the machine is not known yet."""
    assert _rescue_cuts(first, count) == []


def test_a_single_cut_is_the_layer_that_gives_way() -> None:
    assert _rescue_cuts(10, 1) == [10]


# ---- the variants ----------------------------------------------------------------------------------------------------------


def _gated(sid: int, crash_rate: float, first_crash: int, *, wavelength: float = 600.0, rate_layers=None) -> dict:
    blocks = [{"start": 0, "end": N_LAYERS, "wavelength": wavelength}]
    return _item([{first_crash: 10}], blocks=blocks, rate_layers=rate_layers, crash_rate=crash_rate, sid=sid)


def test_the_variants_lay_everything_from_each_cut_by_rate_and_keep_the_rest_of_the_plan() -> None:
    raw = [_gated(1, 0.9, 6)]

    variants = _rescue_variants(raw, N_LAYERS, parents_count=5, cuts_count=3, source_n_blocks=1)

    assert [v["origin"].split("(")[0] for v in variants] == ["RATE_RESCUE6", "RATE_RESCUE4", "RATE_RESCUE2"]
    assert [v["rate_layers"][0] for v in variants] == [6, 4, 2]
    for v in variants:
        assert v["rate_layers"] == list(range(v["rate_layers"][0], N_LAYERS))
        assert v["blocks"] == raw[0]["strategy"]["blocks"]
        assert v["monochromator_resolution_nm"] == 2.0
        assert v["slit_profile"] == raw[0]["strategy"]["slit_profile"]


def test_the_rate_layers_a_plan_already_has_are_kept() -> None:
    raw = [_gated(1, 0.9, 8, rate_layers=[3])]

    variants = _rescue_variants(raw, N_LAYERS, 5, 2, 1)

    assert all(3 in v["rate_layers"] for v in variants)


def test_the_plans_that_crash_least_come_first_and_only_as_many_as_asked() -> None:
    raw = [_gated(1, 0.9, 6, wavelength=601.0), _gated(2, 0.3, 6, wavelength=602.0), _gated(3, 0.6, 6, wavelength=603.0)]

    variants = _rescue_variants(raw, N_LAYERS, parents_count=2, cuts_count=2, source_n_blocks=1)

    assert {v["origin"].split("from ")[1] for v in variants} == {"2)", "3)"}


def test_two_copies_of_one_plan_give_one_parent() -> None:
    raw = [_gated(1, 0.9, 6), _gated(2, 0.8, 6)]

    assert len(_rescue_variants(raw, N_LAYERS, 5, 2, 1)) == 2


def test_the_plans_that_terminated_are_not_parents() -> None:
    raw = [_item([{}], score=0.1, crash_rate=0.0, sid=1)]

    assert _rescue_variants(raw, N_LAYERS, 5, 3, 1) == []


def test_the_variant_ids_are_distinct_and_in_the_rate_range_after_the_ordinary_variants() -> None:
    raw = [_gated(1, 0.9, 6, wavelength=601.0), _gated(2, 0.8, 6, wavelength=602.0)]

    ids = [v["strategy_id"] for v in _rescue_variants(raw, N_LAYERS, 5, 3, 7)]

    assert len(set(ids)) == len(ids) == 6
    from certus.core.certus_strat_ranking import STRATEGY_ID_RATE_BASE, strategy_id_for_block

    assert min(ids) == strategy_id_for_block(STRATEGY_ID_RATE_BASE, 7, RATE_RESCUE_SERIAL_BASE)


# ---- the budget ------------------------------------------------------------------------------------------------------------


def test_the_budget_goes_from_full_strength_when_nothing_terminates_to_light_at_the_threshold() -> None:
    assert _rescue_budget(0, 10) == RATE_RESCUE_FULL
    assert _rescue_budget(10, 10) == RATE_RESCUE_LIGHT
    assert _rescue_budget(50, 10) == RATE_RESCUE_LIGHT


def test_the_fewer_depositable_plans_the_more_the_rescue_spends() -> None:
    spent = [_rescue_budget(found, 10) for found in range(11)]

    assert all(a[0] >= b[0] and a[1] >= b[1] for a, b in itertools.pairwise(spent))
    assert spent[0] != spent[-1]
    assert RATE_RESCUE_LIGHT[0] < _rescue_budget(5, 10)[0] < RATE_RESCUE_FULL[0]


def test_a_threshold_of_zero_means_light() -> None:
    assert _rescue_budget(0, 0) == RATE_RESCUE_LIGHT


# ---- the stage -------------------------------------------------------------------------------------------------------------


class _Collect:
    """Stands for the evaluation of a list of strategies: every variant terminates, with a score."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def __call__(self, strategies: list[dict]) -> list[dict]:
        self.calls.append(strategies)
        return [{"strategy": s, "robustness_score": 0.05, "crash_rate": 0.0, "strategy_id": s["strategy_id"]} for s in strategies]


def _population(depositable: int, gated: int) -> list[dict]:
    done = [_item([{}], score=0.2, crash_rate=0.0, sid=1000 + i) for i in range(depositable)]
    lost = [_gated(i, 0.5 + i / 100, 6, wavelength=600.0 + i) for i in range(gated)]
    return done + lost


def test_the_stage_adds_the_evaluated_tails_to_the_raw_results() -> None:
    raw = _population(0, 3)
    collect = _Collect()

    out = _rescue_with_rate(raw, collect, {}, N_LAYERS, 1, LOG)

    assert out[: len(raw)] == raw
    assert len(out) == len(raw) + sum(len(call) for call in collect.calls)
    assert all(np.isfinite(r["robustness_score"]) for r in out[len(raw):])
    assert any(r["strategy"]["origin"].startswith("RATE_RESCUE") for r in out[len(raw):])


def test_with_few_depositable_plans_it_works_at_full_strength_and_otherwise_lightly() -> None:
    few, plenty = _Collect(), _Collect()

    _rescue_with_rate(_population(0, 50), few, {}, N_LAYERS, 1, LOG)
    _rescue_with_rate(_population(20, 50), plenty, {}, N_LAYERS, 1, LOG)

    assert len(few.calls[0]) <= RATE_RESCUE_FULL[0] * RATE_RESCUE_FULL[1]
    assert len(plenty.calls[0]) <= RATE_RESCUE_LIGHT[0] * RATE_RESCUE_LIGHT[1]
    assert len(few.calls[0]) > len(plenty.calls[0])


def test_the_threshold_of_few_is_a_parameter() -> None:
    raw = _population(5, 50)
    default, strict = _Collect(), _Collect()

    _rescue_with_rate(raw, default, {}, N_LAYERS, 1, LOG)
    _rescue_with_rate(raw, strict, {"rate_rescue_few": 3}, N_LAYERS, 1, LOG)

    assert len(default.calls[0]) > len(strict.calls[0])


def test_it_can_be_switched_off_and_then_hands_the_results_back_untouched() -> None:
    raw = _population(0, 3)
    collect = _Collect()

    out = _rescue_with_rate(raw, collect, {"rate_rescue": False}, N_LAYERS, 1, LOG)

    assert out is raw
    assert collect.calls == []


def test_pure_optical_monitoring_asked_for_is_honoured() -> None:
    """`allow_rate = 0` says the user does not want a Rate layer anywhere: the rescue is a Rate variant like the others."""
    raw = _population(0, 3)
    collect = _Collect()

    out = _rescue_with_rate(raw, collect, {"allow_rate": False}, N_LAYERS, 1, LOG)

    assert out is raw
    assert collect.calls == []


def test_nothing_is_evaluated_when_every_plan_terminated() -> None:
    raw = _population(4, 0)
    collect = _Collect()

    assert _rescue_with_rate(raw, collect, {}, N_LAYERS, 1, LOG) is raw
    assert collect.calls == []
