"""The numeric helpers of STRAT's phase A do what their names say (certus_strat_objectives).

`certus/core/certus_strat_objectives.py` was covered at 36.5 % on 2026-09-30 and no test named it. These four
helpers are pure and carry the choices that decide which wavelengths survive into phase B: how costs are made
comparable between layers, which wavelengths form a block over consecutive layers and are favoured for it, where
a transmission curve has its extrema, and how symmetric a layer is around them. Each test computes its expected
numbers by hand from the definition, so a change of formula shows as a changed number here.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import numpy as np
import pytest

from certus.core.certus_strat_objectives import (
    _apply_block_aware_bonus,
    _compute_strategy_symmetry_score_percent,
    _extract_local_extrema_points,
    _normalize_phase_a_results,
)
from certus.utils.certus_strat_context import SYM_MISSING_DISTANCE

# =============================================================================
# Costs made comparable between layers
# =============================================================================


def test_costs_are_divided_by_their_mean_squared_and_sorted_within_each_layer() -> None:
    raw = {0: [{"wl": 600.0, "cost": 4.0}, {"wl": 500.0, "cost": 2.0}], 1: [{"wl": 500.0, "cost": 6.0}]}

    normalised = _normalize_phase_a_results(raw, num_layers=2)

    # mean of the three costs = 4.0 -> 0.5, 1.0, 1.5 -> squared 0.25, 1.0, 2.25
    assert [(c["wl"], c["cost"], c["cost_raw"]) for c in normalised[0]] == [(500.0, 0.25, 2.0), (600.0, 1.0, 4.0)]
    assert [(c["wl"], c["cost"], c["cost_raw"]) for c in normalised[1]] == [(500.0, 2.25, 6.0)]


def test_a_layer_without_candidates_is_left_out_and_a_zero_mean_does_not_divide_by_zero() -> None:
    assert set(_normalize_phase_a_results({0: [{"wl": 500.0, "cost": 3.0}]}, num_layers=3)) == {0}

    flat = _normalize_phase_a_results({0: [{"wl": 500.0, "cost": 0.0}, {"wl": 600.0, "cost": 0.0}]}, num_layers=1)

    assert [c["cost"] for c in flat[0]] == [0.0, 0.0]  # a mean of 0 counts as 1: the costs stay finite


# =============================================================================
# Blocks over consecutive layers
# =============================================================================


def _layers() -> dict[int, list[dict[str, float]]]:
    return {
        0: [{"wl": 500.0, "cost": 4.0}],
        1: [{"wl": 500.0, "cost": 4.0}, {"wl": 600.0, "cost": 1.0}],
        2: [{"wl": 500.0, "cost": 4.0}, {"wl": 700.0, "cost": 9.0}],
    }


def test_a_wavelength_valid_over_consecutive_layers_is_cheaper_by_the_root_of_its_streak() -> None:
    logger = Mock()

    boosted = _apply_block_aware_bonus(_layers(), num_layers=3, logger=logger)

    streak = [c for i in range(3) for c in boosted[i] if c["wl"] == 500.0]
    assert [c["block_streak_bonus"] for c in streak] == [3, 3, 3]  # one block of three layers, seen from each
    assert [c["cost"] for c in streak] == pytest.approx([4.0 / math.sqrt(3)] * 3)
    lone = [c for i in range(3) for c in boosted[i] if c["wl"] in (600.0, 700.0)]
    assert [c["cost"] for c in lone] == [1.0, 9.0]  # a wavelength valid in one layer only is left alone
    assert all("block_streak_bonus" not in c for c in lone)
    assert "boosted 3" in logger.info.call_args.args[0]


def test_each_layer_is_sorted_again_by_the_new_cost() -> None:
    boosted = _apply_block_aware_bonus(_layers(), num_layers=3, logger=Mock())

    # layer 1: the lone 600 nm (1.0) still beats the boosted 500 nm (4/sqrt(3) = 2.31), but the order is by cost
    assert [c["wl"] for c in boosted[1]] == [600.0, 500.0]
    assert [c["wl"] for c in boosted[2]] == [500.0, 700.0]  # 2.31 < 9.0


def test_a_wavelength_that_skips_a_layer_starts_a_new_streak() -> None:
    gap = {0: [{"wl": 500.0, "cost": 4.0}], 1: [{"wl": 600.0, "cost": 4.0}], 2: [{"wl": 500.0, "cost": 4.0}]}

    boosted = _apply_block_aware_bonus(gap, num_layers=3, logger=Mock())

    assert all(c["cost"] == 4.0 and "block_streak_bonus" not in c for i in range(3) for c in boosted[i])


# =============================================================================
# Extrema of a transmission curve
# =============================================================================


def test_maxima_and_minima_are_found_in_the_order_of_the_grid() -> None:
    d = np.array([0.0, 10.0, 20.0, 30.0, 40.0])

    extrema = _extract_local_extrema_points(d, np.array([0.0, 1.0, 0.0, -1.0, 0.0]))

    assert extrema == [{"type": "max", "d_nm": 10.0, "T": 1.0}, {"type": "min", "d_nm": 30.0, "T": -1.0}]


def test_a_plateau_a_ramp_and_too_few_points_have_no_extremum() -> None:
    d = np.arange(4.0)

    assert _extract_local_extrema_points(d, np.array([0.0, 1.0, 1.0, 0.0])) == []  # comparisons are strict
    assert _extract_local_extrema_points(d, np.array([0.0, 1.0, 2.0, 3.0])) == []
    assert _extract_local_extrema_points(d[:2], np.array([0.0, 1.0])) == []


def test_a_bump_below_the_threshold_is_not_an_extremum() -> None:
    d = np.arange(3.0)
    t = np.array([0.0, 1e-11, 0.0])

    assert _extract_local_extrema_points(d, t, eps=1e-10) == []
    assert len(_extract_local_extrema_points(d, t, eps=1e-12)) == 1


# =============================================================================
# Symmetry of a layer around its extrema
# =============================================================================

WINDOW = 10.0


def _layer(**distances: float) -> dict[str, float]:
    return {f"ext_{name}": value for name, value in distances.items()}


def test_an_extremum_reached_on_both_sides_at_once_is_perfectly_symmetric() -> None:
    profile = [_layer(prev_start=0.0, next_start=0.0, prev_end=SYM_MISSING_DISTANCE, next_end=SYM_MISSING_DISTANCE)]

    assert _compute_strategy_symmetry_score_percent(profile, WINDOW) == pytest.approx(100.0)  # 0.65 + 0.35


def test_a_layer_keeps_the_better_of_its_two_ends_and_the_strategy_averages_its_layers() -> None:
    perfect = _layer(prev_start=0.0, next_start=0.0, prev_end=SYM_MISSING_DISTANCE, next_end=SYM_MISSING_DISTANCE)
    nothing = _layer(prev_start=SYM_MISSING_DISTANCE, next_start=SYM_MISSING_DISTANCE, prev_end=SYM_MISSING_DISTANCE,
                     next_end=SYM_MISSING_DISTANCE)  # fmt: skip

    assert _compute_strategy_symmetry_score_percent([perfect, nothing], WINDOW) == pytest.approx(50.0)


def test_an_extremum_seen_from_one_side_only_scores_its_proximity_alone() -> None:
    one_side = _layer(prev_start=5.0, next_start=SYM_MISSING_DISTANCE, prev_end=SYM_MISSING_DISTANCE,
                      next_end=SYM_MISSING_DISTANCE)  # fmt: skip

    # proximity 1 - 5/10 = 0.5, no balance without a second side: 0.65 * 0.5 = 0.325
    assert _compute_strategy_symmetry_score_percent([one_side], WINDOW) == pytest.approx(32.5)


def test_an_unreadable_value_scores_zero_for_its_layer_without_stopping_the_others(caplog) -> None:
    perfect = _layer(prev_start=0.0, next_start=0.0, prev_end=SYM_MISSING_DISTANCE, next_end=SYM_MISSING_DISTANCE)
    broken = {"ext_prev_start": "not a number"}

    with caplog.at_level("WARNING", logger="CERTUS"):
        score = _compute_strategy_symmetry_score_percent([perfect, broken], WINDOW)

    assert score == pytest.approx(50.0)
    assert "Failed to compute symmetry score" in caplog.text


def test_no_layer_means_no_symmetry() -> None:
    assert _compute_strategy_symmetry_score_percent([], WINDOW) == 0.0
