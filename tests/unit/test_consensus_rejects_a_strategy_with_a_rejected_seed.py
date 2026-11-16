"""A strategy with a rejected consensus seed is ranked behind every stable one (audit 2026-11-15, M-L2).

The consensus re-scores the best strategies on several seeds. ``_store_and_consume_consensus_score`` kept the finite
scores only: a seed that rejected the strategy (infinite score) vanished from the mean, the deviation and the worst, so
[0.007, inf, 0.0071] gave a consensus of 0.00705, better than a strategy stable on its three seeds at 0.0081.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core import certus_strat_consensus as c

SEEDS = [41, 42, 43]


def _consensus(scores: list[float], mode: str = "mean_std", weight: float = 1.0) -> dict:
    kept: list[float] = []
    cache: dict = {}
    for k, score in enumerate(scores):
        c._store_and_consume_consensus_score(
            robustness_score_cache=cache, cache_key=("s", k), score_c=score, seed_scores=kept
        )
    assert not c._should_skip_consensus_registration(kept), "the strategy left the consensus without a score"
    consensus_map: dict = {}
    c._register_consensus_score_for_strategy(
        consensus_map=consensus_map,
        sid="s",
        seed_scores=kept,
        consensus_mode=mode,
        consensus_std_weight=weight,
        consensus_seeds=SEEDS,
    )
    return consensus_map["s"]


@pytest.mark.parametrize("mode", ["mean", "worst", "mean_std"])
@pytest.mark.parametrize("weight", [0.0, 1.0])
def test_one_rejected_seed_makes_the_consensus_infinite(mode: str, weight: float) -> None:
    meta = _consensus([0.0070, np.inf, 0.0071], mode, weight)
    assert meta["score"] == np.inf
    assert meta["worst"] == np.inf
    assert meta["n_samples"] == 3


def test_a_strategy_rejected_on_every_seed_is_scored_infinite_too() -> None:
    assert _consensus([np.inf, np.inf, np.inf])["score"] == np.inf


def test_a_stable_strategy_keeps_its_score_to_the_bit() -> None:
    scores = [0.0080, 0.0081, 0.0082]
    meta = _consensus(scores, "mean_std", 1.0)
    assert meta["score"] == float(np.mean(scores) + 1.0 * np.std(scores))
    assert meta["mean"] == float(np.mean(scores))
    assert meta["std"] == float(np.std(scores))
    assert meta["worst"] == 0.0082


def test_a_cached_rejection_counts_like_a_fresh_one() -> None:
    kept: list[float] = []
    assert c._consume_cached_consensus_score(
        robustness_score_cache={("s", 0): np.inf}, cache_key=("s", 0), seed_scores=kept
    )
    assert kept == [np.inf]


def test_the_rejected_strategy_ranks_behind_the_stable_one() -> None:
    results = [
        {"strategy": {"strategy_id": "unstable"}, "robustness_score": 0.0069},
        {"strategy": {"strategy_id": "stable"}, "robustness_score": 0.0080},
    ]
    consensus_map = {
        "unstable": _consensus([0.0070, np.inf, 0.0071]),
        "stable": _consensus([0.0080, 0.0081, 0.0082]),
    }
    c._apply_consensus_scores_to_results(results_in=results, consensus_map=consensus_map, consensus_mode="mean_std")
    ranked = sorted(results, key=lambda item: item["robustness_score"])
    assert [item["strategy"]["strategy_id"] for item in ranked] == ["stable", "unstable"]
