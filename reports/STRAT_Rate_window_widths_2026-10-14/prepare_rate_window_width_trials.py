"""Prepare one-window moves around the retained, independently checked optical-prefix plan."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "reports/STRAT_Rate_window_widths_2026-10-14"
    output.mkdir(exist_ok=False)
    source = root / "reports/STRAT_Rate_validation_prefix_fine_2026-10-14/plans.json"
    fixed = json.loads(source.read_text(encoding="utf-8"))["plans"]
    parent = next(p for p in fixed if p["source_strategy_id"] == 9900002)
    reference = next(p for p in fixed if p["source_strategy_id"] == 900951015)
    current = set(parent["rate_layers"])
    windows = []
    for layer in range(75):
        if layer in current:
            continue
        if windows and windows[-1][1] == layer:
            windows[-1][1] += 1
        else:
            windows.append([layer, layer + 1])
    proposals = []
    seen = set()
    for first, end in windows:
        if first < 2:
            continue
        block_index = next(i for i, b in enumerate(parent["blocks"]) if b["start"] <= first and end <= b["end"])
        block = parent["blocks"][block_index]
        original_wl = int(block["wavelength"])
        wavelengths = sorted(set(range(450, 751, 10)) | set(range(max(450, original_wl - 10), min(750, original_wl + 10) + 1)))
        for shift in range(-3, 4):
            for width in range(1, 8):
                new_first, new_end = first + shift, first + shift + width
                if new_first < max(2, block["start"]) or new_end > block["end"]:
                    continue
                layers = sorted((current | set(range(first, end))) - set(range(new_first, new_end)))
                for wavelength in wavelengths:
                    if layers == parent["rate_layers"] and wavelength == original_wl:
                        continue
                    blocks = copy.deepcopy(parent["blocks"])
                    blocks[block_index]["wavelength"] = float(wavelength)
                    signature = (tuple((b["start"], b["end"], b["wavelength"]) for b in blocks), tuple(layers))
                    if signature in seen:
                        continue
                    seen.add(signature)
                    kind = "wavelength_only" if layers == parent["rate_layers"] else "window_only" if wavelength == original_wl else "joint_window"
                    plan = {"nom": f"window_L{new_first+1}_{new_end}_wl{wavelength}_fromL{first+1}",
                            "source_strategy_id": 9_930_000 + len(proposals), "blocks": blocks, "rate_layers": layers,
                            "monochromator_resolution_nm": parent["monochromator_resolution_nm"],
                            "move": {"kind": kind, "parent_id": parent["source_strategy_id"], "original_window": [first, end],
                                     "window": [new_first, new_end], "block_index": block_index, "wavelength": wavelength}}
                    if "witness_reset_layers" in parent:
                        plan["witness_reset_layers"] = copy.deepcopy(parent["witness_reset_layers"])
                    proposals.append(plan)
    manifest = {"prepared_utc": datetime.now(UTC).isoformat(), "scope": "One internal optical window position/length and its wavelength vary; prefix600, other windows, partition and metadata fixed",
                "source_plans_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "parent": parent,
                "search_seed": 101, "consensus_seeds": [41, 42, 43], "n_proposals": len(proposals),
                "families": dict(Counter(p["move"]["kind"] for p in proposals)),
                "anchors": [reference, parent], "proposals": proposals}
    with (output / "proposals.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"n_proposals": len(proposals), "families": manifest["families"]}))


if __name__ == "__main__":
    main()
