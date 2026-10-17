"""Check the experimental adapter against the actual frozen candidate factory, without Monte Carlo."""

from __future__ import annotations

import argparse
import copy
import json
import os
import runpy
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if (root / "reports/STRAT_Rate_joint_refinement_2026-10-13/.running").exists():
        raise RuntimeError("No verification while the refinement measurement is active")
    worktree = args.worktree.resolve()
    sys.path[:0] = [str(worktree), str(worktree / "scripts")]
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import bench_examples as bx

    bx.qapp()
    import certus.core.certus_strat_consensus as consensus
    from certus.utils.certus_strat_context import _plan_signature, _validate_strategy_blocks_contract

    helper = runpy.run_path(str(root / "scratch/rate_joint_native_candidates.py"))
    extend = helper["extend_factory"]
    pair = json.loads((root / "reports/STRAT_Rate_expertise_2026-10-13/plans_reference_vs_budget240.json").read_text())
    parents = []
    for plan in pair["plans"]:
        strategy = copy.deepcopy(plan)
        strategy["strategy_id"] = strategy["source_strategy_id"]
        strategy["witness_reset_layers"] = [30]
        parents.append({"strategy": strategy})
    before = copy.deepcopy(parents)
    grid = list(range(450, 751))
    kwargs = {"parent_results": parents, "available_wls": grid, "num_layers": 75, "start_strategy_id": 9900000,
              "max_candidates": 120, "max_rate_candidates": 120, "wl_neighbor_span": 1, "rate_moves": True,
              "balanced_rate_moves": False, "existing_signatures": set()}
    factory = consensus._generate_elite_candidate_strategies
    checks = []
    for scenario in ({}, {"round_robin_seed": (101, 2)}, {"rate_moves": False}, {"parent_results": []}, {"available_wls": []}):
        parameters = {**kwargs, **scenario}
        expected = factory(**parameters)
        actual, cursor, event = extend(factory, consensus, _plan_signature, (), parameters, 0)
        assert (actual, cursor) == expected
        assert event is None
        checks.append("inactive output, order, identifiers and cursor identical: " + str(list(scenario)))
    legacy, legacy_cursor = factory(**kwargs)
    active, cursor, event = extend(factory, consensus, _plan_signature, (), kwargs, 480)
    assert active[:len(legacy)] == legacy
    assert event["joint_count"] > 0
    assert cursor == legacy_cursor + event["joint_count"]
    assert [c["strategy_id"] for c in active] == list(range(kwargs["start_strategy_id"], cursor))
    signatures = [_plan_signature(c["blocks"], c.get("rate_layers")) for c in active]
    assert len(set(signatures)) == len(signatures)
    for c in active[len(legacy):]:
        valid, reason = _validate_strategy_blocks_contract(c, 75)
        assert valid, reason
        assert c["monochromator_resolution_nm"] == 2
        assert c["witness_reset_layers"] == [30]
        assert not set(c["rate_layers"]) & {0, 1}
        assert all(b["wavelength"] in grid for b in c["blocks"])
    assert parents == before
    assert consensus._generate_elite_candidate_strategies is factory
    # The verified useful joint geometry must be offered without a hard-coded wavelength.
    target_blocks = copy.deepcopy(pair["plans"][1]["blocks"])
    target_blocks[3]["wavelength"] = 630.0
    target_rate = sorted((set(pair["plans"][1]["rate_layers"]) | set(range(31, 35))) - set(range(32, 34)))
    target = _plan_signature(target_blocks, target_rate)
    assert target in set(signatures)
    active[len(legacy)]["slit_profile"] = object()
    assert "slit_profile" not in event["offered"][0]
    json.dumps(event)
    checks += ["legacy prefix preserved when active", "unique contiguous identifiers and full plan signatures",
               "block contract, legal Rate layers, on-grid wavelengths, slit and witness metadata preserved",
               "parents unchanged and temporary factory patches restored", "verified joint geometry offered generically at budget 480",
               "offered trace remains serializable after the native pipeline attaches a non-JSON slit profile"]
    result = {"verdict": "GO", "checks": checks, "legacy_count": len(legacy), "joint_count": event["joint_count"],
              "scope": "actual candidate factory and routing only; no Monte Carlo or numerical-kernel changes"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print("NATIVE_ADAPTER_VERIFY=GO")


if __name__ == "__main__":
    main()
