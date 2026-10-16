"""Validate prefix moves around the independently confirmed internal-window plan."""

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
    first_rate = next(i for i in range(75) if i in parent["rate_layers"])
    seen, ids = set(), set()
    for plan in manifest["proposals"]:
        valid, reason = _validate_strategy_blocks_contract({**plan, "strategy_id": plan["source_strategy_id"], "n_blocks": len(plan["blocks"])}, 75)
        if not valid:
            raise ValueError(reason)
        signature = _plan_signature(plan["blocks"], plan["rate_layers"])
        if signature in seen or plan["source_strategy_id"] in ids:
            raise ValueError("Duplicate signature or identity")
        seen.add(signature)
        ids.add(plan["source_strategy_id"])
        move = plan["move"]
        width, wavelength = move["prefix_length"], move["wavelength"]
        expected_blocks = [dict(b) for b in parent["blocks"]]
        expected_blocks[0]["wavelength"] = float(wavelength)
        expected_rate = sorted((set(parent["rate_layers"]) | set(range(first_rate))) - set(range(width)))
        if plan["blocks"] != expected_blocks or plan["rate_layers"] != expected_rate:
            raise ValueError("Unrelated window or partition changed")
        if not 2 <= width <= parent["blocks"][0]["end"] or wavelength not in manifest["wavelengths_by_parent"][parent["nom"]]:
            raise ValueError("Off-grid prefix or wavelength")
        if set(plan["rate_layers"]) & {0, 1} or move["parent_id"] != parent["source_strategy_id"]:
            raise ValueError("Prefix source or first optical pair changed")
        for field in ("monochromator_resolution_nm", "witness_reset_layers"):
            if plan.get(field) != parent.get(field):
                raise ValueError(f"Inherited metadata changed: {field}")
    if len(ids) != manifest["n_proposals"]:
        raise ValueError("Proposal count changed")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"verdict": "GO", "n_proposals": len(ids), "proposals_sha256": hashlib.sha256(args.proposals.read_bytes()).hexdigest(),
                   "context_sha256": hashlib.sha256((worktree / "certus/utils/certus_strat_context.py").read_bytes()).hexdigest(),
                   "checks": ["real block contract", "unique identities and signatures", "exact prefix geometry and wavelength only",
                              "internal windows, partition, slit and witness preserved"], "scope": "No Monte Carlo or physical changes"}, stream, indent=2)
    print("PREFIX_AFTER_WINDOW_VERIFY=GO")


if __name__ == "__main__":
    main()
