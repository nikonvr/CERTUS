"""Check paired proposals against the real contract and their frozen one-window sources."""

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
    sources = {p["source_strategy_id"]: p for p in manifest["source_proposals"]}
    selected = {int(k): {r["id"] for r in rows} for k, rows in manifest["selected_components"].items()}
    seen, ids, pairs = set(), set(), set()
    for plan in manifest["proposals"]:
        valid, reason = _validate_strategy_blocks_contract({**plan, "strategy_id": plan["source_strategy_id"], "n_blocks": len(plan["blocks"])}, 75)
        if not valid:
            raise ValueError(reason)
        signature = _plan_signature(plan["blocks"], plan["rate_layers"])
        if signature in seen or plan["source_strategy_id"] in ids:
            raise ValueError("Duplicate signature or identity")
        seen.add(signature)
        ids.add(plan["source_strategy_id"])
        component_ids = plan["move"]["component_ids"]
        pairs.add(tuple(component_ids))
        expected_blocks = [dict(b) for b in parent["blocks"]]
        expected_rate = set(parent["rate_layers"])
        for block_index, sid, move in zip((1, 3), component_ids, plan["move"]["component_moves"], strict=True):
            if sid not in selected[block_index] or sources[sid]["move"] != move or move["block_index"] != block_index:
                raise ValueError("Pair uses an undeclared component")
            candidate = sources[sid]
            block = parent["blocks"][block_index]
            interval = set(range(block["start"], block["end"]))
            expected_rate = (expected_rate - interval) | (set(candidate["rate_layers"]) & interval)
            expected_blocks[block_index] = dict(candidate["blocks"][block_index])
            first, end = move["window"]
            if not (block["start"] <= first < end <= block["end"]) or float(move["wavelength"]) not in range(450, 751):
                raise ValueError("Illegal component window or wavelength")
        if plan["rate_layers"] != sorted(expected_rate) or plan["blocks"] != expected_blocks:
            raise ValueError("Pair has unrelated changes")
        if plan["blocks"][0] != parent["blocks"][0] or (set(plan["rate_layers"]) & set(range(9))) != (set(parent["rate_layers"]) & set(range(9))):
            raise ValueError("Optical prefix changed")
        for field in ("monochromator_resolution_nm", "witness_reset_layers"):
            if plan.get(field) != parent.get(field):
                raise ValueError(f"Inherited metadata changed: {field}")
    if len(ids) != manifest["n_proposals"] or pairs != {(left, right) for left in selected[1] for right in selected[3]}:
        raise ValueError("Predeclared Cartesian product is incomplete")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"verdict": "GO", "n_proposals": len(ids), "proposals_sha256": hashlib.sha256(args.proposals.read_bytes()).hexdigest(),
                   "context_sha256": hashlib.sha256((worktree / "certus/utils/certus_strat_context.py").read_bytes()).hexdigest(),
                   "checks": ["real block contract", "full predeclared Cartesian product", "unique identities and signatures",
                              "exact source composition", "prefix, partition, slit and witness preserved"],
                   "scope": "No Monte Carlo or physical changes"}, stream, indent=2)
    print("WINDOW_PAIRS_VERIFY=GO")


if __name__ == "__main__":
    main()
