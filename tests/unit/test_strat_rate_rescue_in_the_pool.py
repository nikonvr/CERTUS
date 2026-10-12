"""The pool of the robustness tasks calls the Rate rescue between the raw results and the filter of the finite scores.

The pieces of the rescue are pinned by `test_strat_rate_rescue.py`; what this file pins is the wiring, with a stand-in for the task of
one strategy: a plan crashes at layer 6 in 30 % of the draws unless it lays everything from layer 6 by Rate.
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

import certus.core.certus_strat_robustness as robustness
from certus_physics import CRASH_LEVEL_UNREACHABLE, CRASH_SENTINEL_UNIT

N_LAYERS = 12
RUNS = 100


def _fake_task(strategy, _idx, noise_levels, *_args, **_kwargs):
    """A plan terminates when layer 6 is laid by Rate; otherwise 30 draws out of 100 crash there (and the layers after)."""
    thick = np.full((RUNS, N_LAYERS), 100.0)
    if 6 not in (strategy.get("rate_layers") or []):
        thick[:30, 6:] = 100.0 + CRASH_LEVEL_UNREACHABLE * CRASH_SENTINEL_UNIT
    crash_rate = float(np.mean((thick > 1e5).any(axis=1)))
    gated = crash_rate >= 0.05
    return {
        "strategy": dict(strategy),
        "strategy_id": strategy["strategy_id"],
        "results_per_noise": [{"noise_level": lv, "thicknesses_all": thick.tolist()} for lv in noise_levels],
        "robustness_score": float("inf") if gated else 0.05,
        "crash_rate": crash_rate,
    }


@pytest.fixture
def pool(monkeypatch):
    monkeypatch.setattr(robustness, "_test_strategy_robustness_task", _fake_task)
    monkeypatch.setattr(robustness, "_calculate_strategy_spectral_resolution", lambda *a, **k: (2.0, -1, 0.0))

    def run(strategies, **kwargs):
        return robustness._execute_robustness_tasks(
            strategies, [0.05], RUNS, [100.0] * N_LAYERS, {}, {}, np.array([550.0]), np.array([2.3]), np.array([1.5]), np.array([1.5]),
            np.array([0.9]), {}, kwargs.pop("params", {}), kwargs.pop("logger", logging.getLogger("pool")), **kwargs,
        )

    return run


def _plans(n: int) -> list[dict]:
    return [
        {"strategy_id": 100 + i, "blocks": [{"start": 0, "end": N_LAYERS, "wavelength": 600.0 + i}], "n_blocks": 1} for i in range(n)
    ]


def test_without_the_rescue_nothing_terminates_and_the_pool_hands_back_the_ranking_by_risk(pool) -> None:
    res = pool(_plans(3))

    assert len(res) == 3
    assert all(r.get("crash_eliminated") for r in res)


def test_with_the_rescue_the_plans_that_terminate_are_the_Rate_tails(pool) -> None:
    res = pool(_plans(3), rate_rescue=True, id_namespace_n_blocks=1)

    assert res
    assert all(np.isfinite(r["robustness_score"]) for r in res)
    assert all(r["strategy"]["origin"].startswith(("RATE_RESCUE", "RATE_HARD")) for r in res)
    assert all(6 in r["strategy"]["rate_layers"] for r in res)


def test_the_rescue_ends_at_layer_two_where_everything_is_laid_by_rate(pool) -> None:
    res = pool(_plans(1), rate_rescue=True, id_namespace_n_blocks=1)

    assert any(r["strategy"]["rate_layers"] == list(range(2, N_LAYERS)) for r in res)


def test_the_rescue_variants_have_distinct_ids_from_the_plans_they_come_from(pool) -> None:
    plans = _plans(3)
    res = pool(plans, rate_rescue=True, id_namespace_n_blocks=1)

    ids = [r["strategy_id"] for r in res]
    assert len(set(ids)) == len(ids)
    assert not set(ids) & {p["strategy_id"] for p in plans}


def test_the_raw_results_keep_the_plans_the_gate_rejected(pool) -> None:
    res = pool(_plans(2), rate_rescue=True, id_namespace_n_blocks=1, keep_gated=True)

    gated = [r for r in res if not np.isfinite(r["robustness_score"])]
    done = [r for r in res if np.isfinite(r["robustness_score"])]
    assert len(gated) == 2
    assert done


def test_the_switch_of_the_parameters_turns_it_off_in_the_pool_too(pool) -> None:
    res = pool(_plans(2), rate_rescue=True, id_namespace_n_blocks=1, params={"rate_rescue": False})

    assert all(r.get("crash_eliminated") for r in res)


def test_a_pass_with_depositable_plans_keeps_only_those(pool) -> None:
    """The rescue adds candidates to a pass; the filter still drops the plans the gate rejected as soon as one terminates."""
    plans = [
        *_plans(2),
        {"strategy_id": 7, "blocks": [{"start": 0, "end": N_LAYERS, "wavelength": 700.0}], "n_blocks": 1, "rate_layers": [6]},
    ]

    res = pool(plans, rate_rescue=True, id_namespace_n_blocks=1)

    assert res
    assert all(np.isfinite(r["robustness_score"]) for r in res)
    assert not any(r["strategy_id"] in (100, 101) for r in res)
