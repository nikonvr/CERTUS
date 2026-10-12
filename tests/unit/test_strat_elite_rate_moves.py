"""ELITE can move the Rate layers of its parents, on request: optics, a packet of Rate, optics again.

👤 2026-10-12: *"experience shows that there are sometimes good strategies with a packet of optics at one wavelength, then a packet of
Rate, then a packet of optics at another wavelength -- but it is purely empirical"*. The kernel allows it (`rate_layers` is any set
of layers); the search did not offer it: the depositable plans of `r75x0.5` and `r75x2` with optics after Rate had exactly two runs of
Rate, a layer and a tail, and ELITE handed its parent's Rate layers down unchanged.
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from certus.core.certus_strat_config import RobustnessContext
from certus.core.certus_strat_consensus import _apply_elite_refinement_if_enabled, _generate_elite_candidate_strategies
from certus.core.certus_strat_ranking import _existing_block_signatures
from certus.core.certus_strat_robustness import (
    ELITE_RATE_FILL_MAX,
    ELITE_RATE_WINDOWS,
    RATE_MIN_LAYER,
    _elite_rate_moves,
    _rate_runs,
)

WLS = [596.0, 598.0, 600.0, 602.0, 604.0, 616.0, 618.0, 620.0, 622.0, 624.0]
N_LAYERS = 20


def _as_sets(moves: list[list[int]]) -> list[frozenset[int]]:
    return [frozenset(m) for m in moves]


# ---- the moves -------------------------------------------------------------------------------------------------------------


def test_a_run_of_rate_grows_and_shrinks_at_both_ends() -> None:
    moves = _as_sets(_elite_rate_moves(range(10, 19), N_LAYERS))

    assert frozenset(range(9, 19)) in moves  # one layer more on the left
    assert frozenset(range(10, 20)) in moves  # one layer more on the right
    assert frozenset(range(11, 19)) in moves  # one less on the left
    assert frozenset(range(10, 18)) in moves  # one less on the right


def test_a_run_cannot_grow_past_the_last_layer() -> None:
    moves = _as_sets(_elite_rate_moves(range(10, N_LAYERS), N_LAYERS))

    assert all(max(m, default=0) < N_LAYERS for m in moves)
    assert frozenset(range(9, N_LAYERS)) in moves


def test_a_window_of_optics_is_opened_inside_a_run_and_leaves_rate_at_both_ends() -> None:
    parent = list(range(10, 20))
    moves = _elite_rate_moves(parent, N_LAYERS)

    assert [(10, 10), (13, 19)] in [_rate_runs(m) for m in moves]  # layers 11 and 12 are optical now
    splits = [m for m in moves if len(_rate_runs(m)) > 1]
    assert splits
    for move in splits:
        assert 10 in move
        assert 19 in move


def test_the_windows_are_as_wide_as_the_widths_asked() -> None:
    parent = list(range(10, 20))
    widths = set()
    for move in _elite_rate_moves(parent, N_LAYERS):
        runs = _rate_runs(move)
        if len(runs) == 2 and runs[0][0] == 10 and runs[1][1] == 19:  # a window inside the run, not a packet in the head
            widths.add(runs[1][0] - runs[0][1] - 1)

    assert widths == set(ELITE_RATE_WINDOWS)


def test_a_short_gap_of_optics_between_two_runs_is_closed() -> None:
    moves = _as_sets(_elite_rate_moves([5, 6, 9, 10], 14))

    assert frozenset(range(5, 11)) in moves


def test_a_long_gap_of_optics_is_left_alone() -> None:
    gap = ELITE_RATE_FILL_MAX + 1
    parent = [5, 6, 7 + gap, 8 + gap]
    moves = _as_sets(_elite_rate_moves(parent, 30))

    assert frozenset(range(5, 9 + gap)) not in moves


def test_packets_of_rate_are_laid_in_the_optics_with_optics_on_each_side() -> None:
    moves = _elite_rate_moves([], N_LAYERS)

    assert moves
    for move in moves:
        (first, last), = _rate_runs(move)
        assert last - first + 1 in ELITE_RATE_WINDOWS
        assert first >= RATE_MIN_LAYER + 1  # the first layers stay optical: they give the machine its rate
        assert last <= N_LAYERS - 2  # a layer of optics after the packet


def test_a_packet_is_laid_between_a_run_of_rate_and_the_end_of_the_head_of_optics() -> None:
    """The head of optics of a tail takes a packet of Rate: optics, Rate, optics, Rate."""
    moves = _elite_rate_moves(range(14, N_LAYERS), N_LAYERS)

    assert any(len(_rate_runs(m)) == 2 and _rate_runs(m)[1] == (14, N_LAYERS - 1) for m in moves)


@pytest.mark.parametrize("parent", [[], [5], list(range(2, 10)), [3, 4, 9, 10, 11], list(range(17, N_LAYERS))])
def test_layers_zero_and_one_never_carry_rate_and_no_move_is_the_parent_or_a_duplicate(parent) -> None:
    moves = _elite_rate_moves(parent, N_LAYERS)

    assert moves
    assert all(0 not in m and 1 not in m for m in moves)
    assert all(m == sorted(set(m)) for m in moves)
    assert frozenset(parent) not in _as_sets(moves)
    assert len(set(_as_sets(moves))) == len(moves)


def test_layers_zero_and_one_in_the_parent_are_dropped_not_carried() -> None:
    moves = _elite_rate_moves([0, 1, 7, 8], N_LAYERS)

    assert all(0 not in m and 1 not in m for m in moves)


# ---- the candidates of ELITE -----------------------------------------------------------------------------------------------


def _parent(sid: int, rate_layers, shift: float = 0.0) -> dict:
    blocks = [{"start": 0, "end": 10, "wavelength": 600.0 + shift}, {"start": 10, "end": N_LAYERS, "wavelength": 620.0 + shift}]
    return {
        "strategy": {
            "strategy_id": sid,
            "n_blocks": 2,
            "blocks": blocks,
            "rate_layers": list(rate_layers),
            "monochromator_resolution_nm": 2.0,
            "witness_reset_layers": [4],
        }
    }


def _children(parents: list[dict], **kwargs) -> tuple[list[dict], int]:
    return _generate_elite_candidate_strategies(parents, WLS, N_LAYERS, 1000, max_candidates=60, **kwargs)


def test_by_default_the_candidates_are_those_of_before() -> None:
    parents = [_parent(7, range(12, N_LAYERS))]

    assert _children(parents, rate_moves=False, max_rate_candidates=40) == _children(parents)


def test_without_a_budget_the_moves_add_nothing() -> None:
    parents = [_parent(7, range(12, N_LAYERS))]

    assert _children(parents, rate_moves=True, max_rate_candidates=0) == _children(parents)


def test_the_extra_candidates_change_the_rate_layers_of_their_parent_and_nothing_else() -> None:
    parents = [_parent(7, range(12, N_LAYERS))]
    plain, _ = _children(parents)

    children, next_id = _children(parents, rate_moves=True, max_rate_candidates=10)
    extra = children[len(plain) :]

    assert children[: len(plain)] == plain  # the moves of before come first, untouched
    assert 0 < len(extra) <= 10
    for child in extra:
        assert child["blocks"] == parents[0]["strategy"]["blocks"]
        assert child["rate_layers"] != parents[0]["strategy"]["rate_layers"]
        assert child["origin"] == "ELITE"
        assert child["origin_details"].startswith("ELITE_RATE(parent=7)")
        assert child["parent_strategy_id"] == 7
        assert child["monochromator_resolution_nm"] == 2.0
        assert child["witness_reset_layers"] == [4]
    assert [c["strategy_id"] for c in children] == list(range(1000, 1000 + len(children)))
    assert next_id == 1000 + len(children)


def test_the_parents_take_turns_for_the_moves_on_the_rate_layers() -> None:
    parents = [_parent(7, range(12, N_LAYERS)), _parent(8, range(14, N_LAYERS), 2.0), _parent(9, range(16, N_LAYERS), 4.0)]
    plain, _ = _children(parents)

    children, _ = _children(parents, rate_moves=True, max_rate_candidates=6)
    first_six = [c["parent_strategy_id"] for c in children[len(plain) :]]

    assert first_six == [7, 8, 9, 7, 8, 9]


def test_a_plan_already_known_is_not_proposed_again() -> None:
    parents = [_parent(7, range(12, N_LAYERS))]
    known = [{"strategy": {"blocks": parents[0]["strategy"]["blocks"], "rate_layers": list(range(11, N_LAYERS))}}]
    seen = _existing_block_signatures(known)

    children, _ = _generate_elite_candidate_strategies(
        parents, WLS, N_LAYERS, 1000, max_candidates=60, existing_signatures=seen, rate_moves=True, max_rate_candidates=60
    )

    assert list(range(11, N_LAYERS)) not in [c["rate_layers"] for c in children]


def test_a_pure_optical_parent_gets_packets_of_rate() -> None:
    parents = [{"strategy": {"strategy_id": 3, "n_blocks": 2, "blocks": _parent(3, [])["strategy"]["blocks"]}}]

    children, _ = _children(parents, rate_moves=True, max_rate_candidates=8)
    extra = [c for c in children if c["origin_details"].startswith("ELITE_RATE")]

    assert len(extra) == 8
    assert all(_rate_runs(c["rate_layers"])[0][1] - _rate_runs(c["rate_layers"])[0][0] + 1 in ELITE_RATE_WINDOWS for c in extra)


# ---- the refinement asks for them only when told to ------------------------------------------------------------------------


def _ctx(params: dict) -> RobustnessContext:
    return RobustnessContext(
        params=params, params_safe={}, logger=logging.getLogger("test"), noise_levels=[1.0], num_runs=10,
        p_thick_nominal=[100.0, 80.0], num_layers=2, clues_at_wl={500.0: {"H": 2.0, "L": 1.5, "substrate": 1.52}},
        wl_arr=np.array([500.0]), nH_arr=np.array([2.0]), nL_arr=np.array([1.5]), nSub_arr=np.array([1.52]),
        T_nom=np.array([0.5]), full_dyn_grid={},
    )


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({}, (False, 120)),
        ({"elite_rate_moves": False}, (False, 120)),
        ({"elite_rate_moves": True}, (True, 120)),
        ({"elite_rate_moves": True, "elite_rate_max_candidates": 33}, (True, 33)),
    ],
)
def test_the_refinement_passes_the_moves_only_when_asked(monkeypatch, extra, expected) -> None:
    from certus.core.certus_strat_consensus import _apply_elite_refinement_if_enabled as refine

    seen = []

    def fake_generate(*_a, **k):
        seen.append((k.get("rate_moves"), k.get("max_rate_candidates")))
        return [], 0

    monkeypatch.setattr("certus.core.certus_strat_consensus._generate_elite_candidate_strategies", fake_generate)
    monkeypatch.setattr(
        "certus.core.certus_strat_consensus._resolve_elite_nominal_and_target_threshold", lambda *a, **k: (0.01, 0.01)
    )
    params = {"elite_rounds": 1, "robustness_noise_factors": [1.0], "robustness_seed": 77, **extra}
    strategies = [{"strategy": {"strategy_id": "s", "blocks": []}, "robustness_score": 0.01}]

    refine(strategies, _ctx(params), lambda *a: None)

    assert seen == [expected]
    assert _apply_elite_refinement_if_enabled is refine
