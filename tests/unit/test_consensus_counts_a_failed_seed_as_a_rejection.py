"""A consensus seed whose evaluation raises rejects the strategy (owner's decision of 2026-11-16, follow-up of M-L2).

The failure was only logged: the strategy was then scored on its other seeds, as a rejected seed was before M-L2.
"""

from __future__ import annotations

import logging

import numpy as np

from certus.core import certus_strat_consensus as c
from certus.core.certus_strat_robustness import _record_consensus_seed_failure


def test_a_failed_seed_makes_the_consensus_infinite(caplog) -> None:
    scores = [0.0070, 0.0071]
    with caplog.at_level(logging.WARNING):
        _record_consensus_seed_failure(logging.getLogger("t"), "7", 42, ValueError("boom"), scores)
    assert scores[-1] == np.inf
    assert any("seed=42" in r.getMessage() for r in caplog.records), "the failure is no longer logged"
    consensus_map: dict = {}
    c._register_consensus_score_for_strategy(
        consensus_map=consensus_map,
        sid="7",
        seed_scores=scores,
        consensus_mode="mean_std",
        consensus_std_weight=1.0,
        consensus_seeds=[41, 42, 43],
    )
    assert consensus_map["7"]["score"] == np.inf
