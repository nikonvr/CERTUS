"""A strategy whose slit-bias profile fails is rejected, and the failure is said (audit 2026-11-15, L2-m3)."""

from __future__ import annotations

import logging

import numpy as np

from certus.core import certus_strat_robustness as rob
from certus.core.certus_strat_robustness_diagnostics import _strategy_final_score


def test_a_failed_profile_marks_the_strategy_and_logs_it(monkeypatch, caplog) -> None:
    def _boom(*_a, **_k):
        raise ValueError("no profile")

    monkeypatch.setattr(rob, "_slit_bias_profiles", _boom)
    strategy = {"strategy_id": 7, "blocks": []}
    with caplog.at_level(logging.WARNING):
        rob._attach_slit_profiles([strategy], [100.0], {"slit_bias_enabled": True}, logging.getLogger("t"))
    assert strategy["slit_profile"] is None
    assert strategy["slit_profile_failed"] is True
    assert any("7" in r.getMessage() and "rejected" in r.getMessage() for r in caplog.records)


def test_a_marked_strategy_scores_infinite_and_the_others_do_not_change() -> None:
    levels = [{"rmse_p95": 0.01, "rmse_mean": 0.0, "rmse_std": 0.0}, {"rmse_p95": 0.02, "rmse_mean": 0.0, "rmse_std": 0.0}]
    assert _strategy_final_score({"slit_profile_failed": True}, levels) == np.inf
    assert _strategy_final_score({}, levels) == 0.02
