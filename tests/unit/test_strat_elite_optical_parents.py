"""ELITE reserves optical parents without changing its inactive candidate stream."""

import copy
import logging
import pickle

import numpy as np
import pytest

from certus.core import certus_strat_consensus as consensus
from certus.core.certus_strat_config import RobustnessContext


def _parents():
    return [
        {
            "strategy": {
                "strategy_id": sid,
                "blocks": [{"start": 0, "end": 4, "wavelength": 500.0 + 5.0 * sid}],
                "rate_layers": [2] if sid < 4 else [],
            },
            "robustness_score": float(sid + 1) / 100.0,
        }
        for sid in range(6)
    ]


def _context(extra):
    return RobustnessContext(
        params={"elite_rounds": 1, "elite_parent_top_k": 3, "robustness_seed": 42, **extra},
        params_safe={}, logger=logging.getLogger(__name__), noise_levels=[1.0], num_runs=10,
        p_thick_nominal=[100.0] * 4, num_layers=4,
        clues_at_wl={wl: {} for wl in np.arange(490.0, 541.0, 5.0)},
        wl_arr=np.arange(490.0, 541.0, 5.0), nH_arr=np.array([2.0]),
        nL_arr=np.array([1.5]), nSub_arr=np.array([1.52]), T_nom=np.array([0.5]), full_dyn_grid={},
    )


def _capture(monkeypatch, strategies, extra, pool=None):
    seen = []

    def generate(**kwargs):
        seen.append(kwargs)
        return [], 1000

    monkeypatch.setattr(consensus, "_generate_elite_candidate_strategies", generate)
    monkeypatch.setattr(consensus, "_resolve_elite_nominal_and_target_threshold", lambda *a, **k: (0.01, 0.01))
    context = _context(extra)
    context.elite_optical_parent_pool = pool
    consensus._apply_elite_refinement_if_enabled(strategies, context, lambda *a: None)
    assert len(seen) == 1
    return seen[0]


@pytest.mark.parametrize(("minimum", "expected"), [(0, [0, 1, 2]), (1, [4, 0, 1]), (2, [4, 5, 0]), (99, [4, 5, 0])])
def test_quota_reaches_the_real_candidate_generator(monkeypatch, minimum, expected):
    seen = _capture(monkeypatch, _parents(), {"elite_optical_parents": minimum})
    assert [item["strategy"]["strategy_id"] for item in seen["parent_results"]] == expected


def test_quota_can_exceed_the_usual_parent_cap(monkeypatch):
    parents = _parents()
    for item in parents[2:]:
        item["strategy"]["rate_layers"] = []
    seen = _capture(monkeypatch, parents, {"elite_optical_parents": 4})
    assert [item["strategy"]["strategy_id"] for item in seen["parent_results"]] == [2, 3, 4, 5]


def test_crashed_optical_parents_remain_available_for_mutation(monkeypatch):
    parents = _parents()
    parents[4]["crash_eliminated"] = True
    seen = _capture(monkeypatch, parents, {"elite_optical_parents": 2})
    assert [item["strategy"]["strategy_id"] for item in seen["parent_results"]] == [4, 5, 0]


def test_reserved_pool_supplies_optical_parents_removed_by_the_finite_gate(monkeypatch):
    parents = _parents()
    for item in parents[4:]:
        item["robustness_score"] = float("inf")
        item["crash_eliminated"] = True
    seen = _capture(monkeypatch, parents[:4], {"elite_optical_parents": 2}, pool=parents[4:])
    assert [item["strategy"]["strategy_id"] for item in seen["parent_results"]] == [4, 5, 0]


@pytest.mark.parametrize(("minimum", "refine"), [(0, True), (2, True), (2, False)])
def test_production_reserves_before_filtering_and_keeps_the_output_gate(monkeypatch, minimum, refine):
    from certus.core import certus_strat_robustness as robustness

    raw = _parents()
    for item in raw[4:]:
        item["robustness_score"] = float("inf")
        item["crash_eliminated"] = True
        item["crash_rate"] = 0.4
    seen = {}
    logger = logging.getLogger(__name__)

    def execute(**kwargs):
        seen["keep_gated"] = kwargs.get("keep_gated", False)
        return raw if seen["keep_gated"] else robustness._filter_finite_robustness_scores(raw, logger=logger)

    def elite(**kwargs):
        seen["pool"] = getattr(kwargs["ctx"], "elite_optical_parent_pool", None)
        return kwargs["strategies_results"]

    monkeypatch.setattr(robustness, "_prepare_robustness_inputs", lambda **kw: ([row["strategy"] for row in raw], [1.0], [100.0] * 4, 4))
    monkeypatch.setattr(robustness, "_prepare_robustness_nominal_optics", lambda **kw: (np.array([500.0]),) * 5)
    monkeypatch.setattr(robustness, "_precompute_layer_index_matrix", lambda *a: None)
    monkeypatch.setattr(robustness, "_execute_robustness_tasks", execute)
    monkeypatch.setattr(consensus, "_unpack_consensus_cfg", lambda *a, **kw: (False, 12, "mean_std", 0.35, 300, []))
    monkeypatch.setattr(consensus, "_rank_and_filter_strategies", lambda **kw: kw["strategies_results"])
    monkeypatch.setattr(consensus, "_apply_elite_refinement_if_enabled", elite)
    monkeypatch.setattr(robustness, "_finalize_robustness_results", lambda **kw: kw["strategies_results"])
    params = {"logger": logger, "ablation_profile": False, "elite_optical_parents": minimum}
    output = robustness.run_final_simulation_block({"clues_at_wl": {}, "all_strategies": []}, params, refine=refine)
    assert output == raw[:4]
    active = bool(minimum and refine)
    assert seen["keep_gated"] is active
    assert len(seen.get("pool") or []) == (2 if active else 0)


def test_zero_and_missing_parameter_keep_the_historical_candidate_bits(monkeypatch):
    generate = consensus._generate_elite_candidate_strategies
    parents = _parents()
    original = pickle.dumps(parents)
    absent = _capture(monkeypatch, copy.deepcopy(parents), {})
    zero = _capture(monkeypatch, copy.deepcopy(parents), {"elite_optical_parents": 0})
    legacy = dict(zero, parent_results=parents[:3])
    assert pickle.dumps(generate(**absent)) == pickle.dumps(generate(**legacy))
    assert pickle.dumps(generate(**zero)) == pickle.dumps(generate(**legacy))
    assert pickle.dumps(parents) == original
