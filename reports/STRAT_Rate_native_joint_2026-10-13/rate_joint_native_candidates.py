"""Deterministic joint moves for an experimental native ELITE adapter; no physics."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch


def joint_candidates(parent_results: list[dict[str, Any]], available_wls: list[float], num_layers: int) -> Iterator[tuple[Any, dict[str, Any], list[dict[str, Any]], list[int]]]:
    grid = sorted(set(float(wl) for wl in available_wls))
    if not grid:
        return
    coarse = [grid[0]]
    for wl in grid[1:]:
        if wl >= coarse[-1] + 10.0 - 1e-9:
            coarse.append(wl)
    grid_set = set(grid)

    def moves(parent):
        strategy = parent.get("strategy", {})
        blocks = strategy.get("blocks") or []
        current = {int(i) for i in strategy.get("rate_layers") or [] if 2 <= int(i) < num_layers}
        if not current:
            return
        wavelengths = list(dict.fromkeys([float(b["wavelength"]) for b in blocks if float(b["wavelength"]) in grid_set] + coarse))
        windows = []
        for layer in range(num_layers):
            if layer in current:
                continue
            if windows and windows[-1][1] == layer:
                windows[-1][1] += 1
            else:
                windows.append([layer, layer + 1])
        def window_moves(first, end):
            if first < 2:
                return
            block_index = next((i for i, b in enumerate(blocks) if int(b["start"]) <= first and end <= int(b["end"])), None)
            if block_index is None:
                return
            block = blocks[block_index]
            for wavelength in wavelengths:
                for width in (2, 4, 6):
                    for shift in (-2, -1, 0, 1, 2):
                        new_first, new_end = first + shift, first + shift + width
                        if new_first < max(2, int(block["start"])) or new_end > int(block["end"]):
                            continue
                        layers = sorted((current | set(range(first, end))) - set(range(new_first, new_end)))
                        if layers == sorted(current) and wavelength == float(block["wavelength"]):
                            continue
                        changed = [dict(b) for b in blocks]
                        changed[block_index]["wavelength"] = wavelength
                        yield strategy.get("strategy_id", "?"), strategy, changed, layers

        window_streams = [iter(window_moves(first, end)) for first, end in windows]
        while window_streams:
            remaining = []
            for stream in window_streams:
                item = next(stream, None)
                if item is not None:
                    yield item
                    remaining.append(stream)
            window_streams = remaining

    streams = [iter(moves(parent)) for parent in parent_results]
    while streams:
        remaining = []
        for stream in streams:
            item = next(stream, None)
            if item is not None:
                yield item
                remaining.append(stream)
        streams = remaining


def extend_factory(factory, consensus, signature, factory_args, factory_kwargs, budget):
    """Keep every legacy candidate and use the original factory for a separate joint budget."""
    candidates, next_sid = factory(*factory_args, **factory_kwargs)
    if budget == 0 or not factory_kwargs.get("rate_moves", False):
        return candidates, next_sid, None
    moves = joint_candidates(factory_kwargs["parent_results"], factory_kwargs["available_wls"], factory_kwargs["num_layers"])
    extra_kwargs = dict(factory_kwargs)
    extra_kwargs.update(start_strategy_id=next_sid, max_candidates=0, max_rate_candidates=budget,
                        existing_signatures=set(factory_kwargs.get("existing_signatures") or ()) |
                        {signature(c["blocks"], c.get("rate_layers")) for c in candidates})
    with patch.object(consensus, "_elite_moves", return_value=[]), patch.object(consensus, "_elite_rate_candidates", return_value=moves):
        extra, cursor = factory(**extra_kwargs)
    for item in extra:
        item["origin_details"] = f"ELITE_RATE_JOINT(parent={item['parent_strategy_id']})"
    event = {"legacy_count": len(candidates), "joint_count": len(extra), "start_sid": next_sid, "next_sid": cursor,
             "parent_ids": [p.get("strategy", {}).get("strategy_id") for p in factory_kwargs["parent_results"]],
             "num_layers": factory_kwargs["num_layers"], "offered": extra}
    return candidates + extra, cursor, event
