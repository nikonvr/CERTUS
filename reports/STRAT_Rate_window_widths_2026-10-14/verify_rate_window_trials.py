"""Verify every offered one-window plan with the frozen real block contract, before scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    worktree = args.worktree.resolve()
    sys.path[:0] = [str(worktree), str(worktree / "scripts")]
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import bench_examples as bx

    bx.qapp()
    from certus.utils.certus_strat_context import _plan_signature, _validate_strategy_blocks_contract

    manifest = json.loads(args.proposals.read_text(encoding="utf-8"))
    parent = manifest["parent"]
    seen = set()
    ids = set()
    for plan in manifest["proposals"]:
        move = plan["move"]
        strategy = {**plan, "strategy_id": plan["source_strategy_id"], "n_blocks": len(plan["blocks"])}
        valid, reason = _validate_strategy_blocks_contract(strategy, 75)
        if not valid:
            raise ValueError(reason)
        signature = _plan_signature(plan["blocks"], plan["rate_layers"])
        if signature in seen or plan["source_strategy_id"] in ids:
            raise ValueError("Duplicate plan or identity")
        seen.add(signature)
        ids.add(plan["source_strategy_id"])
        old_first, old_end = move["original_window"]
        new_first, new_end = move["window"]
        expected_rate = sorted((set(parent["rate_layers"]) | set(range(old_first, old_end))) - set(range(new_first, new_end)))
        expected_blocks = [dict(b) for b in parent["blocks"]]
        expected_blocks[move["block_index"]]["wavelength"] = float(move["wavelength"])
        if plan["rate_layers"] != expected_rate or plan["blocks"] != expected_blocks:
            raise ValueError("An unrelated window or block changed")
        block = parent["blocks"][move["block_index"]]
        if not (block["start"] <= new_first < new_end <= block["end"]):
            raise ValueError("Window crossed its block")
        if set(plan["rate_layers"]) & {0, 1} or plan["blocks"][0] != parent["blocks"][0]:
            raise ValueError("Optical prefix changed")
        for field in ("monochromator_resolution_nm", "witness_reset_layers"):
            if plan.get(field) != parent.get(field):
                raise ValueError(f"Inherited metadata changed: {field}")
        if float(move["wavelength"]) not in range(450, 751):
            raise ValueError("Off-grid control wavelength")
    if len(ids) != manifest["n_proposals"]:
        raise ValueError("Proposal count changed")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"verdict": "GO", "n_proposals": len(ids), "proposals_sha256": hashlib.sha256(args.proposals.read_bytes()).hexdigest(),
                   "context_sha256": hashlib.sha256((worktree / "certus/utils/certus_strat_context.py").read_bytes()).hexdigest(),
                   "checks": ["real block contract", "unique complete signatures and identities", "exact one-window Rate and wavelength changes",
                              "prefix, other windows, partition, slit and witness metadata preserved", "legal one-nanometer control grid"],
                   "scope": "No Monte Carlo or physical changes"}, stream, indent=2)
    print("WINDOW_TRIALS_VERIFY=GO")


if __name__ == "__main__":
    main()
