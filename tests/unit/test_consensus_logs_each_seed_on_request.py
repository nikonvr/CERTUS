"""The consensus can log the raw score of each seed, and says nothing unless asked (follow-up of M-L2)."""

from __future__ import annotations

import logging

from certus.core.certus_strat_robustness import _log_consensus_seed_score


def test_nothing_is_logged_by_default(caplog) -> None:
    with caplog.at_level(logging.INFO):
        _log_consensus_seed_score(logging.getLogger("t"), {}, "pre-elite", "7", 42, float("inf"))
    assert not caplog.records


def test_each_seed_is_logged_with_its_raw_score_on_request(caplog) -> None:
    with caplog.at_level(logging.INFO):
        _log_consensus_seed_score(
            logging.getLogger("t"), {"consensus_log_seed_scores": True}, "pre-elite", "7", 42, float("inf")
        )
    assert [r.getMessage() for r in caplog.records] == ["[CONSENSUS-SEED] pre-elite sid=7 seed=42 score=inf"]
