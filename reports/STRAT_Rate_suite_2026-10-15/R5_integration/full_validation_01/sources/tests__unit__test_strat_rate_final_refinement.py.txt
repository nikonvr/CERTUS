"""Opt-in final refinement must preserve the legacy route and use only its own native parents."""

from __future__ import annotations

import copy
import logging

import numpy as np
import pytest

from certus.core.certus_strat_consensus import _generate_elite_candidate_strategies
from certus.core.certus_strat_rate_moves import optical_windows, signature
from certus.core.certus_strat_rate_post import complete_score, native_parents, rank_complete_first, refine_native_output
from certus.utils.certus_strat_context import _validate_strategy_blocks_contract


def parent(strategy_id=21):
    return {"strategy_id": strategy_id, "blocks": [{"start": 0, "end": 6, "wavelength": 507.0},
                                                  {"start": 6, "end": 18, "wavelength": 511.0}],
            "rate_layers": list(range(2, 9)) + list(range(12, 18)), "monochromator_resolution_nm": 2.0,
            "witness_reset_layers": [9], "resolution_noise_factor": 0.7, "origin": "NATIVE"}


def result(strategy, score=2.0):
    return {"strategy": copy.deepcopy(strategy), "robustness_score": score, "robustness_score_base": score + 1,
            "robustness_score_consensus": score, "robustness_consensus_meta":
                {"mode": "mean_std", "seeds": [41, 42, 43], "n_samples": 3}, "crash_eliminated": False}


@pytest.mark.parametrize("budget", [0, -1])
def test_joint_inactive_preserves_every_legacy_candidate_and_cursor(budget):
    parents = [{"strategy": parent()}]
    args = dict(parent_results=parents, available_wls=list(range(500, 521)), num_layers=18,
                start_strategy_id=7000, max_candidates=4, rate_moves=True, max_rate_candidates=3)
    before = copy.deepcopy(parents)
    assert _generate_elite_candidate_strategies(**args, joint_candidates=budget) == _generate_elite_candidate_strategies(**args)
    assert parents == before


def test_active_joint_budget_adds_legal_children_after_legacy_ids():
    parents = [{"strategy": parent()}]
    args = dict(parent_results=parents, available_wls=list(range(500, 521)), num_layers=18,
                start_strategy_id=7000, max_candidates=4, rate_moves=True, max_rate_candidates=0)
    legacy, cursor = _generate_elite_candidate_strategies(**args)
    active, after = _generate_elite_candidate_strategies(**args, joint_candidates=30)
    assert active[:len(legacy)] == legacy
    extra = active[len(legacy):]
    assert len(extra) == 30
    assert [p["strategy_id"] for p in extra] == list(range(cursor, after))
    assert any(any(end - first == 3 for first, end in optical_windows(p, 18) if first >= 2) for p in extra)
    for plan in extra:
        assert _validate_strategy_blocks_contract(plan, 18)[0]
        assert plan["monochromator_resolution_nm"] == 2.0
        assert plan["witness_reset_layers"] == [9]
        assert plan["origin_details"].startswith("ELITE_RATE_JOINT")


def test_disallowed_rate_generates_no_joint_candidates():
    args = dict(parent_results=[{"strategy": parent()}], available_wls=list(range(500, 521)), num_layers=18,
                start_strategy_id=7000, max_candidates=4, rate_moves=False)
    assert _generate_elite_candidate_strategies(**args, joint_candidates=480) == _generate_elite_candidate_strategies(**args)


def test_parent_selection_uses_complete_consensus_and_preserves_inherited_values():
    good = result(parent())
    good["strategy"]["monochromator_resolution_nm"] = None
    bad = result(parent(22), 0.001)
    bad["robustness_consensus_meta"]["n_samples"] = 2
    before = copy.deepcopy([good, bad])
    selected = native_parents([good, bad], [41, 42, 43], "mean_std", 1.5)
    assert len(selected) == 1
    plan = selected[0]["plan"]
    assert plan["native_source_id"] == 21
    assert plan["monochromator_resolution_nm"] == 1.5
    assert plan["resolution_noise_factor"] == 0.7
    assert plan["witness_reset_layers"] == [9]
    assert [good, bad] == before
    assert complete_score(bad, [41, 42, 43], "mean_std") is None


def test_final_refinement_is_bounded_and_keeps_incumbent_without_injecting_parents():
    original = [result(parent())]
    before = copy.deepcopy(original)
    calls = []

    def evaluate(plans):
        calls.append(copy.deepcopy(plans))
        rows = []
        for plan in plans:
            strategy = {**plan, "strategy_id": plan["source_strategy_id"]}
            rows.append(result(strategy, 1.0 if "move" in plan else 2.0))
        return rows

    rows, report = refine_native_output(original, list(range(500, 521)), 18, [41, 42, 43], "mean_std", 2.0, evaluate)
    assert report["best_score"] == 1.0
    assert report["new_proposals"] <= 600
    assert len(report["passes"]) == 2
    assert report["passes"][-1]["improved"] is False
    assert all(p["proposals"] <= 300 for p in report["passes"])
    assert all(len(batch) <= 9 for batch in calls)
    assert len(calls[0]) == 1
    assert all(p.get("native_source_id") == 21 for batch in calls for p in batch)
    assert original == before
    assert len(rows) > len(original)


def test_no_gain_stops_after_one_pass_and_preserves_the_incumbent():
    def evaluate(plans):
        return [result({**p, "strategy_id": p["source_strategy_id"]}, 2.0 if "move" not in p else 3.0) for p in plans]

    _, report = refine_native_output([result(parent())], list(range(500, 521)), 18, [41, 42, 43], "mean_std", 2.0, evaluate)
    assert len(report["passes"]) == 1
    assert report["best_score"] == 2.0
    assert "move" not in report["winner"]


def test_opt_in_final_ranking_retains_incomplete_results_after_complete_ones():
    complete = result(parent(), 2)
    complete["rate_post_consensus_eligible"] = True
    incomplete = result(parent(22), 0.001)
    incomplete["robustness_consensus_meta"]["n_samples"] = 1
    assert rank_complete_first([incomplete, complete]) == [complete, incomplete]
    assert signature(parent()) == signature(copy.deepcopy(parent()))


@pytest.mark.parametrize("refine", [True, False])
def test_fixed_scoring_can_skip_generation_without_skipping_base_evaluation(monkeypatch, refine):
    import certus.core.certus_strat_consensus as consensus
    import certus.core.certus_strat_robustness as robustness

    row = result(parent())
    calls = []
    monkeypatch.setattr(robustness, "_prepare_robustness_inputs", lambda **kw: ([parent()], [0.05], [1.0] * 18, 18))
    arrays = (np.array([507.0]),) * 5
    monkeypatch.setattr(robustness, "_prepare_robustness_nominal_optics", lambda **kw: arrays)
    monkeypatch.setattr(robustness, "_precompute_layer_index_matrix", lambda *a: None)
    monkeypatch.setattr(robustness, "_execute_robustness_tasks", lambda **kw: calls.append("base") or [row])
    monkeypatch.setattr(consensus, "_unpack_consensus_cfg", lambda *a, **kw: (False, 12, "mean_std", 0.35, 300, []))
    monkeypatch.setattr(consensus, "_rank_and_filter_strategies", lambda **kw: kw["strategies_results"])
    monkeypatch.setattr(consensus, "_apply_elite_refinement_if_enabled", lambda **kw: calls.append("elite") or kw["strategies_results"])
    monkeypatch.setattr(robustness, "_finalize_robustness_results", lambda **kw: {"all_strategies_results": kw["strategies_results"]})
    params = {"logger": logging.getLogger("test"), "ablation_profile": False}
    output = robustness.run_final_simulation_block({"clues_at_wl": {}, "all_strategies": [parent()]}, params, 300, expand_variants=False, refine=refine)
    assert output["all_strategies_results"] == [row]
    assert calls == (["base", "elite"] if refine else ["base"])
