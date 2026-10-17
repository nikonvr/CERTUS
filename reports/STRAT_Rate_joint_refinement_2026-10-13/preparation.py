"""Prepare deterministic window/wavelength neighbors around a fixed measured plan; no physics."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--id-base", type=int, required=True)
    parser.add_argument("--fine-span", type=int, default=10)
    args = parser.parse_args()
    pair_path = args.pair.resolve()
    pair = json.loads(pair_path.read_text(encoding="utf-8"))
    incumbent = pair["plans"][1]
    assert len(pair["plans"]) == 2
    assert args.fine_span >= 0
    current = set(incumbent["rate_layers"])
    optical = set(range(75)) - current
    windows = []
    for layer in sorted(optical):
        if windows and layer == windows[-1][1]:
            windows[-1][1] += 1
        else:
            windows.append([layer, layer + 1])
    windows = [window for window in windows if window[0] > 0]
    wavelengths = sorted(set(range(450, 751, 10)) | {int(block["wavelength"]) for block in incumbent["blocks"]}
                         | {450, 452, 705, 707})
    local_wavelengths = {int(block["wavelength"]) + delta for block in incumbent["blocks"]
                         if any(block["start"] <= window[0] < block["end"] for window in windows)
                         for delta in range(-args.fine_span, args.fine_span + 1)}
    wavelengths = sorted(set(wavelengths) | {wl for wl in local_wavelengths if 450 <= wl <= 750})
    proposals = []
    seen = set()
    for first, end in windows:
        block_index = next(i for i, block in enumerate(incumbent["blocks"]) if block["start"] <= first and end <= block["end"])
        block = incumbent["blocks"][block_index]
        for width in (2, 4, 6):
            for shift in (-2, -1, 0, 1, 2):
                new_first, new_end = first + shift, first + shift + width
                if new_first < block["start"] or new_end > block["end"]:
                    continue
                layers = sorted((current | set(range(first, end))) - set(range(new_first, new_end)))
                for wavelength in wavelengths:
                    same_window, same_wl = layers == incumbent["rate_layers"], wavelength == block["wavelength"]
                    if same_window and same_wl:
                        continue
                    blocks = copy.deepcopy(incumbent["blocks"])
                    blocks[block_index]["wavelength"] = float(wavelength)
                    signature = (tuple((b["start"], b["end"], b["wavelength"]) for b in blocks), tuple(layers))
                    if signature in seen:
                        continue
                    seen.add(signature)
                    proposals.append({"nom": f"joint_L{new_first+1}_{new_end}_wl{wavelength}_baseL{first+1}",
                                      "source_strategy_id": args.id_base + len(proposals),
                                      "blocks": blocks, "rate_layers": layers,
                                      "monochromator_resolution_nm": incumbent["monochromator_resolution_nm"],
                                      "move": {"kind": "wavelength_only" if same_window else "window_only" if same_wl else "joint",
                                               "original_window": [first, end], "window": [new_first, new_end],
                                               "width": width, "shift": shift, "wavelength": wavelength}})
    payload = {"status": "prepared_not_run", "scope": "one existing optical window changed per proposal; original block partition preserved",
               "fine_span_nm": args.fine_span, "source_pair_sha256": hashlib.sha256(pair_path.read_bytes()).hexdigest(),
               "source_incumbent": incumbent["source_strategy_id"], "search_seed": 101,
               "consensus_seeds": [41, 42, 43], "widths": [2, 4, 6], "shifts": [-2, -1, 0, 1, 2],
               "wavelengths": wavelengths, "n_proposals": len(proposals),
               "families": dict(Counter(p["move"]["kind"] for p in proposals)),
               "anchors": pair["plans"], "proposals": proposals}
    target = args.output.resolve()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("Existing proposal set differs; refusing to overwrite")
    with target.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    print(json.dumps({"status": payload["status"], "count": len(proposals), "families": payload["families"],
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
