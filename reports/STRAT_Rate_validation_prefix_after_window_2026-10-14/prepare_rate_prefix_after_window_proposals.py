"""Prepare prefix-length/wavelength neighbors of two fully scored fixed plans."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "reports/STRAT_Rate_prefix_after_window_2026-10-14"
    output.mkdir(exist_ok=False)
    source = root / "reports/STRAT_Rate_validation_window_widths_2026-10-14/plans.json"
    fixed = json.loads(source.read_text(encoding="utf-8"))["plans"]
    parents = [next(p for p in fixed if p["source_strategy_id"] == sid) for sid in (9900006,)]
    anchors = [next(p for p in fixed if p["source_strategy_id"] == sid) for sid in (900951015, 9900006)]
    coarse = json.loads((root / "reports/STRAT_Rate_expertise_2026-10-13/joint_window_proposals_v1.json").read_text())["wavelengths"]
    proposals = []
    seen = set()
    grids = {}
    for parent in parents:
        current = set(parent["rate_layers"])
        first_rate = next(i for i in range(75) if i in current)
        block = parent["blocks"][0]
        if block["start"] != 0 or first_rate > block["end"] or first_rate < 2:
            raise ValueError("Expected a valid optical prefix inside the first block")
        wavelength = int(block["wavelength"])
        wavelengths = sorted(set(coarse) | {wl for wl in range(wavelength - 20, wavelength + 21) if 450 <= wl <= 750})
        grids[parent["nom"]] = wavelengths
        for width in range(2, int(block["end"]) + 1):
            layers = sorted((current | set(range(first_rate))) - set(range(width)))
            for wl in wavelengths:
                if layers == parent["rate_layers"] and wl == block["wavelength"]:
                    continue
                blocks = copy.deepcopy(parent["blocks"])
                blocks[0]["wavelength"] = float(wl)
                signature = (tuple((b["start"], b["end"], b["wavelength"]) for b in blocks), tuple(layers))
                if signature in seen:
                    continue
                seen.add(signature)
                proposal = {"nom": f"prefix_L1_{width}_wl{wl}_parent{parent['source_strategy_id']}",
                            "source_strategy_id": 9_910_000 + len(proposals), "blocks": blocks, "rate_layers": layers,
                            "monochromator_resolution_nm": parent["monochromator_resolution_nm"],
                            "move": {"kind": "wavelength_only" if width == first_rate else "prefix_only" if wl == block["wavelength"] else "joint_prefix",
                                     "parent_id": parent["source_strategy_id"], "prefix_length": width, "wavelength": wl,
                                     "original_prefix_length": first_rate}}
                if "witness_reset_layers" in parent:
                    proposal["witness_reset_layers"] = copy.deepcopy(parent["witness_reset_layers"])
                proposals.append(proposal)
    manifest = {"status": "prepared_not_run", "prepared_utc": datetime.now(UTC).isoformat(),
                "scope": "Only optical prefix length and first-block wavelength vary; first two layers remain optical; other windows and partitions fixed",
                "source_plans_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "parents": parents, "parent": parents[0],
                "search_seed": 101, "consensus_seeds": [41, 42, 43], "n_proposals": len(proposals),
                "families": dict(Counter(p["move"]["kind"] for p in proposals)), "wavelengths_by_parent": grids,
                "anchors": anchors, "proposals": proposals}
    with (output / "proposals.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"n_proposals": len(proposals), "families": manifest["families"],
                      "sha256": hashlib.sha256((output / "proposals.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
