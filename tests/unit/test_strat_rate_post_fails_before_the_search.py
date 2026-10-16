"""The opt-in final Rate refinement needs a consensus setup: a missing one must stop the run BEFORE the search.

`refine_rate_output` runs after the whole Phase B. Refused there, a mis-set run had spent its hours and was never
exported; the same refusal at the start of the pipeline costs nothing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import certus.workers.certus_strat_workers_pipeline as pipeline
import certus.workers.certus_strat_workers_rate as workers_rate


class _HeavyStepReached(Exception):
    """Raised by the stand-in for the first heavy step of the pipeline (the queue of the statistics consumer)."""


def _consensus(**over):
    return {
        "enable_consensus_ranking": True,
        "consensus_top_k": 12,
        "consensus_num_seeds": 3,
        "robustness_num_runs": 150,
        **over,
    }


def _fake_worker(params):
    announced = []
    signals = SimpleNamespace(progress_snapshot=SimpleNamespace(emit=announced.append))
    return SimpleNamespace(params=params, timing_logger=None, signals=signals), announced


@pytest.fixture
def heavy_step(monkeypatch):
    def reached():
        raise _HeavyStepReached

    monkeypatch.setattr(pipeline, "_init_stats_queue", reached)


@pytest.mark.parametrize(
    "over",
    [{"enable_consensus_ranking": False}, {"consensus_top_k": 8}, {"consensus_num_seeds": 1}],
    ids=["consensus off", "top_k below nine", "one seed"],
)
def test_a_missing_consensus_prerequisite_is_refused_with_its_values(over):
    with pytest.raises(ValueError, match="requires consensus"):
        workers_rate.check_rate_post_preconditions(_consensus(**over))


def test_a_complete_consensus_setup_is_accepted_and_resolved():
    cfg = workers_rate.check_rate_post_preconditions(_consensus())
    assert cfg["enabled"] is True
    assert cfg["top_k"] == 12
    assert len(cfg["seeds"]) == 3


def test_the_pipeline_refuses_before_announcing_anything(heavy_step):
    worker, announced = _fake_worker({"rate_post_refinement": True, **_consensus(enable_consensus_ranking=False)})
    with pytest.raises(ValueError, match="requires consensus"):
        pipeline.FullPipelineStrategy().execute(worker)
    assert announced == []


@pytest.mark.parametrize(
    "params",
    [
        _consensus(enable_consensus_ranking=False),
        {"rate_post_refinement": False, **_consensus(enable_consensus_ranking=False)},
        {"rate_post_refinement": True, "allow_rate": False, **_consensus(enable_consensus_ranking=False)},
    ],
    ids=["option absent", "option off", "allow_rate off"],
)
def test_the_inactive_routes_never_run_the_check(heavy_step, params):
    worker, announced = _fake_worker(params)
    with pytest.raises(_HeavyStepReached):
        pipeline.FullPipelineStrategy().execute(worker)
    assert len(announced) == 1
