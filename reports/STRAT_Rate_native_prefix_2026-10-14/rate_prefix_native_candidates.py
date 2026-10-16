"""Prefix length/wavelength moves appended after the unchanged legacy and joint budgets."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch


def prefix_candidates(parent_results: list[dict[str, Any]], available_wls: list[float], num_layers: int) -> Iterator[tuple[Any, dict[str, Any], list[dict[str, Any]], list[int]]]:
    grid = sorted(set(float(wl) for wl in available_wls))
    if not grid:
        return
    # Pick legal control-grid values nearest a regular 10 nm grid; no case-specific wavelength.
    coarse = sorted({min(grid, key=lambda wl: (abs(wl - target), wl))
                     for target in range(int(grid[0] // 10) * 10, int(grid[-1] // 10) * 10 + 11, 10)})

    def moves(parent):
        strategy = parent.get("strategy", {})
        blocks = strategy.get("blocks") or []
        current = {int(i) for i in strategy.get("rate_layers") or [] if 2 <= int(i) < num_layers}
        if not current or not blocks or int(blocks[0]["start"]) != 0:
            return
        width = next((i for i in range(num_layers) if i in current), num_layers)
        boundary = int(blocks[0]["end"])
        if width < 2 or width > boundary:
            return
        parent_wl = float(blocks[0]["wavelength"])
        wavelengths = sorted(set(coarse) | ({parent_wl} if parent_wl in grid else set()),
                             key=lambda wl: (abs(wl - parent_wl), wl))
        widths = sorted(range(2, boundary + 1), key=lambda n: (abs(n - width), n))
        for wavelength in wavelengths:
            for new_width in widths:
                layers = sorted((current | set(range(width))) - set(range(new_width)))
                if layers == sorted(current) and wavelength == parent_wl:
                    continue
                changed = [dict(b) for b in blocks]
                changed[0]["wavelength"] = wavelength
                yield strategy.get("strategy_id", "?"), strategy, changed, layers

    streams = [iter(moves(parent)) for parent in parent_results]
    while streams:
        remaining = []
        for stream in streams:
            item = next(stream, None)
            if item is not None:
                yield item
                remaining.append(stream)
        streams = remaining


def extend_prefix(factory, consensus, signature, factory_kwargs, candidates, cursor, budget):
    """Use the original factory for one separate prefix budget and preserve its input prefix."""
    if budget == 0 or not factory_kwargs.get("rate_moves", False):
        return candidates, cursor, None
    moves = prefix_candidates(factory_kwargs["parent_results"], factory_kwargs["available_wls"], factory_kwargs["num_layers"])
    extra_kwargs = dict(factory_kwargs)
    extra_kwargs.update(start_strategy_id=cursor, max_candidates=0, max_rate_candidates=budget,
                        existing_signatures=set(factory_kwargs.get("existing_signatures") or ()) |
                        {signature(c["blocks"], c.get("rate_layers")) for c in candidates})
    with patch.object(consensus, "_elite_moves", return_value=[]), patch.object(consensus, "_elite_rate_candidates", return_value=moves):
        extra, next_sid = factory(**extra_kwargs)
    for item in extra:
        item["origin_details"] = f"ELITE_RATE_PREFIX(parent={item['parent_strategy_id']})"
    event = {"prior_count": len(candidates), "prefix_count": len(extra), "start_sid": cursor, "next_sid": next_sid,
             "parent_ids": [p.get("strategy", {}).get("strategy_id") for p in factory_kwargs["parent_results"]],
             "num_layers": factory_kwargs["num_layers"], "offered": copy.deepcopy(extra)}
    return candidates + extra, next_sid, event
