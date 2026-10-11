"""ELITE explores its parents in turn on request (`elite_round_robin`); by default the first few fill the budget.

`_generate_elite_candidate_strategies` tries the moves of each parent (`_elite_moves`: every block's wavelength to its
neighbours, every boundary by one layer) parent after parent, until `elite_max_candidates` are kept. A parent of K blocks
has up to 4K - 2 moves, so with the default budget of 120 and ten parents of 15 blocks the first three fill it, and
`elite_parent_top_k = 10` explores three. With a round-robin seed the parents take turns, one move each, every parent's
moves in an order drawn from the seed.
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
import pytest

from certus.core.certus_strat_config import RobustnessContext
from certus.core.certus_strat_consensus import (
    _apply_elite_refinement_if_enabled,
    _elite_moves,
    _generate_elite_candidate_strategies,
)

N_LAYERS = 150
WLS = [float(w) for w in np.arange(450.0, 751.0, 1.0)]


def _parents(n_blocks: int, n_parents: int = 10) -> list[dict]:
    """Near-duplicate parents, as ELITE gets them: one lineage, each parent one wavelength or one boundary apart."""
    rng = np.random.default_rng(n_blocks)
    base_bounds = np.sort(rng.choice(np.arange(5, N_LAYERS - 5), n_blocks - 1, replace=False))
    base_wl = rng.choice(WLS, n_blocks)
    parents = []
    for p in range(n_parents):
        bounds, wl = base_bounds.copy(), base_wl.copy()
        if p % 2:
            wl[rng.integers(n_blocks)] = rng.choice(WLS)
        else:
            k = rng.integers(n_blocks - 1)
            bounds[k] += rng.choice([-2, 2])
            bounds = np.sort(bounds)
        edges = [0, *bounds.tolist(), N_LAYERS]
        blocks = [{"start": int(edges[b]), "end": int(edges[b + 1]), "wavelength": float(wl[b])} for b in range(n_blocks)]
        parents.append({"strategy": {"strategy_id": p, "blocks": blocks}})
    return parents


def _per_parent(candidates: list[dict]) -> list[int]:
    count = Counter(c["parent_strategy_id"] for c in candidates)
    return [count.get(p, 0) for p in range(10)]


def test_by_default_the_first_parents_fill_the_budget() -> None:
    candidates, _ = _generate_elite_candidate_strategies(_parents(15), WLS, N_LAYERS, 1000, max_candidates=120)

    assert len(candidates) == 120
    assert _per_parent(candidates)[3:] == [0] * 7  # three parents explored out of ten


def test_in_turn_every_parent_is_explored_within_the_same_budget() -> None:
    parents = _parents(15)

    candidates, next_id = _generate_elite_candidate_strategies(
        parents, WLS, N_LAYERS, 1000, max_candidates=120, round_robin_seed=(42, 1)
    )

    assert len(candidates) == 120
    assert min(_per_parent(candidates)) >= 10
    assert [c["strategy_id"] for c in candidates] == list(range(1000, 1120))
    assert next_id == 1120
    moves = {repr(m) for p in parents for m in _elite_moves(p["strategy"]["blocks"], np.array(WLS), 1)}
    assert all(repr(c["blocks"]) in moves for c in candidates)  # the same moves, in another order


def test_the_order_in_turn_is_drawn_from_the_seed() -> None:
    parents = _parents(11)

    def signatures(seed):
        cands, _ = _generate_elite_candidate_strategies(parents, WLS, N_LAYERS, 0, max_candidates=60, round_robin_seed=seed)
        return [repr(c["blocks"]) for c in cands]

    assert signatures((42, 1)) == signatures((42, 1))
    assert signatures((42, 1)) != signatures((42, 2))


def _ctx(params: dict) -> RobustnessContext:
    return RobustnessContext(
        params=params, params_safe={}, logger=logging.getLogger("test"), noise_levels=[1.0], num_runs=10,
        p_thick_nominal=[100.0, 80.0], num_layers=2, clues_at_wl={500.0: {"H": 2.0, "L": 1.5, "substrate": 1.52}},
        wl_arr=np.array([500.0]), nH_arr=np.array([2.0]), nL_arr=np.array([1.5]), nSub_arr=np.array([1.52]),
        T_nom=np.array([0.5]), full_dyn_grid={},
    )


@pytest.mark.parametrize(("flag", "expected"), [(None, None), (False, None), (True, (77, 1))])
def test_the_refinement_passes_a_seed_only_when_asked(monkeypatch, flag, expected) -> None:
    seen = []

    def fake_generate(*_a, **k):
        seen.append(k.get("round_robin_seed"))
        return [], 0

    monkeypatch.setattr("certus.core.certus_strat_consensus._generate_elite_candidate_strategies", fake_generate)
    monkeypatch.setattr(
        "certus.core.certus_strat_consensus._resolve_elite_nominal_and_target_threshold", lambda *a, **k: (0.01, 0.01)
    )
    params = {"elite_rounds": 1, "robustness_noise_factors": [1.0], "robustness_seed": 77}
    if flag is not None:
        params["elite_round_robin"] = flag
    strategies = [{"strategy": {"strategy_id": "s", "blocks": []}, "robustness_score": 0.01}]

    _apply_elite_refinement_if_enabled(strategies, _ctx(params), lambda *a: None)

    assert seen == [expected]
