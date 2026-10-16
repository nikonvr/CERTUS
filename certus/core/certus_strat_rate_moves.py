"""Measured generic Rate/optical moves; no scoring or physical model."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator
from typing import Any


def optical_windows(plan: dict, num_layers: int) -> list[list[int]]:
    rate = set(plan.get("rate_layers") or [])
    windows: list[list[int]] = []
    for layer in range(num_layers):
        if layer in rate:
            continue
        if windows and windows[-1][1] == layer:
            windows[-1][1] += 1
        else:
            windows.append([layer, layer + 1])
    return windows


def signature(plan: dict) -> str:
    """Ignore wavelengths only in blocks whose every physical layer is Rate."""
    rate = set(plan.get("rate_layers") or [])
    blocks = [
        (
            int(b["start"]),
            int(b["end"]),
            None if all(i in rate for i in range(b["start"], b["end"])) else float(b["wavelength"]),
        )
        for b in plan["blocks"]
    ]
    return json.dumps(
        {
            "blocks": blocks,
            "rate_layers": sorted(rate),
            "monochromator_resolution_nm": plan.get("monochromator_resolution_nm"),
            "witness_reset_layers": plan.get("witness_reset_layers"),
        },
        sort_keys=True,
    )


def window_context(plan: dict, num_layers: int, kind: str) -> tuple[int, int, int]:
    windows = optical_windows(plan, num_layers)
    if kind == "prefix":
        first, end = windows[0]
        if first != 0 or end < 2:
            raise ValueError("The first two layers must remain an optical prefix")
    elif kind == "internal":
        internal = [window for window in windows if window[0] >= 2]
        if not internal:
            raise ValueError("No internal optical window is available")
        first, end = internal[-1]
    else:
        raise ValueError("Unknown R4 window kind")
    block_index = next((i for i, b in enumerate(plan["blocks"]) if b["start"] <= first and end <= b["end"]), None)
    if block_index is None:
        raise ValueError("The selected window spans multiple monitoring blocks")
    block = plan["blocks"][block_index]
    rate = set(plan.get("rate_layers") or [])
    if any(i not in rate and (not first <= i < end) for i in range(block["start"], block["end"])):
        raise ValueError("Changing this block wavelength would alter another optical window")
    return (first, end, block_index)


def candidate(
    parent: dict, num_layers: int, kind: str, first: int, end: int, wavelength: float, stage: str
) -> dict[str, Any] | None:
    old_first, old_end, block_index = window_context(parent, num_layers, kind)
    block = parent["blocks"][block_index]
    if kind == "prefix":
        if first != 0 or end < 2:
            return None
    elif first < max(2, block["start"]):
        return None
    if first < block["start"] or end > block["end"] or first >= end:
        return None
    rate = set(parent.get("rate_layers") or [])
    layers = sorted((rate | set(range(old_first, old_end))) - set(range(first, end)))
    plan = copy.deepcopy(parent)
    plan.pop("expected_score_fixed_point", None)
    plan.pop("native_selections", None)
    plan["blocks"][block_index]["wavelength"] = float(wavelength)
    plan["rate_layers"] = layers
    plan["n_blocks"] = len(plan["blocks"])
    plan["move"] = {
        "kind": kind,
        "stage": stage,
        "parent_id": parent["source_strategy_id"],
        "old_window": [old_first, old_end],
        "window": [first, end],
        "block_index": block_index,
        "wavelength": float(wavelength),
    }
    return plan


def coarse(parent: dict, available_wls: list[float], num_layers: int, kind: str) -> Iterator[dict[str, Any] | None]:
    first, end, block_index = window_context(parent, num_layers, kind)
    grid = sorted(set(float(wl) for wl in available_wls))
    coarse_grid: list[float] = []
    for wavelength in grid:
        if not coarse_grid or wavelength >= coarse_grid[-1] + 10.0 - 1e-09:
            coarse_grid.append(wavelength)
    current_wl = float(parent["blocks"][block_index]["wavelength"])
    if current_wl not in grid:
        raise ValueError("The parent's wavelength is outside the legal native grid")
    for wavelength in coarse_grid:
        yield candidate(parent, num_layers, kind, first, end, wavelength, "coarse_wavelength")
    if kind == "internal":
        for width in range(1, 8):
            for shift in (-2, -1, 0, 1, 2):
                yield candidate(
                    parent, num_layers, kind, first + shift, first + shift + width, current_wl, "coarse_geometry"
                )
    else:
        for width in range(2, parent["blocks"][block_index]["end"] + 1):
            yield candidate(parent, num_layers, kind, 0, width, current_wl, "coarse_geometry")


def fine(parent: dict, available_wls: list[float], num_layers: int, kind: str) -> Iterator[dict[str, Any] | None]:
    first, end, block_index = window_context(parent, num_layers, kind)
    legal = set(float(wl) for wl in available_wls)
    current_wl = float(parent["blocks"][block_index]["wavelength"])
    if current_wl not in legal:
        raise ValueError("The parent's wavelength is outside the legal native grid")
    for delta in (0, -1, 1, -2, 2, -3, 3):
        wavelength = current_wl + delta
        if wavelength not in legal:
            continue
        for width in (end - first - 1, end - first, end - first + 1):
            if kind == "internal" and (not 1 <= width <= 7):
                continue
            for shift in (0,) if kind == "prefix" else (-1, 0, 1):
                yield candidate(
                    parent, num_layers, kind, first + shift, first + shift + width, wavelength, "fine_joint"
                )


def joint_candidates(
    parent_results: list[dict[str, Any]],
    available_wls: list[float],
    num_layers: int,
    widths: tuple[int, ...] = (2, 4, 6),
    fine_wavelengths: bool = False,
) -> Iterator[tuple[Any, dict[str, Any], list[dict[str, Any]], list[int]]]:
    grid = sorted(set(float(wl) for wl in available_wls))
    if not grid:
        return
    coarse = [grid[0]]
    for wl in grid[1:]:
        if wl >= coarse[-1] + 10.0 - 1e-09:
            coarse.append(wl)
    grid_set = set(grid)

    def moves(parent: dict[str, Any]) -> Iterator[tuple[Any, dict[str, Any], list[dict[str, Any]], list[int]]]:
        strategy = parent.get("strategy", {})
        blocks = strategy.get("blocks") or []
        current = {int(i) for i in strategy.get("rate_layers") or [] if 2 <= int(i) < num_layers}
        if not current:
            return
        wavelengths = list(
            dict.fromkeys([float(b["wavelength"]) for b in blocks if float(b["wavelength"]) in grid_set] + coarse)
        )
        windows: list[list[int]] = []
        for layer in range(num_layers):
            if layer in current:
                continue
            if windows and windows[-1][1] == layer:
                windows[-1][1] += 1
            else:
                windows.append([layer, layer + 1])

        def window_moves(first: int, end: int) -> Iterator[tuple[Any, dict[str, Any], list[dict[str, Any]], list[int]]]:
            if first < 2:
                return
            block_index = next(
                (i for i, b in enumerate(blocks) if int(b["start"]) <= first and end <= int(b["end"])), None
            )
            if block_index is None:
                return
            block = blocks[block_index]
            window_wavelengths = wavelengths
            if fine_wavelengths:
                nearby = [
                    float(block["wavelength"]) + delta
                    for delta in (0, -1, 1, -2, 2, -3, 3)
                    if float(block["wavelength"]) + delta in grid_set
                ]
                window_wavelengths = list(dict.fromkeys(nearby + wavelengths))
            for wavelength in window_wavelengths:
                for width in widths:
                    for shift in (-2, -1, 0, 1, 2):
                        new_first, new_end = (first + shift, first + shift + width)
                        if new_first < max(2, int(block["start"])) or new_end > int(block["end"]):
                            continue
                        layers = sorted((current | set(range(first, end))) - set(range(new_first, new_end)))
                        if layers == sorted(current) and wavelength == float(block["wavelength"]):
                            continue
                        changed = [dict(b) for b in blocks]
                        changed[block_index]["wavelength"] = wavelength
                        yield (strategy.get("strategy_id", "?"), strategy, changed, layers)

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


def append_joint_candidates(parent_results: list[dict[str, Any]], available_wls: list[float], num_layers: int,
                            budget: int, out: list[dict[str, Any]], push: Callable[..., bool]) -> None:
    """Use the native constructor for the separate measured joint budget, without patches."""
    limit = len(out) + min(480, int(budget))
    for parent_sid, parent, blocks, layers in joint_candidates(parent_results, available_wls, num_layers, tuple(range(1, 8)), True):
        if len(out) >= limit:
            break
        if push(blocks, parent_sid, parent, rate_layers=layers, limit=limit):
            out[-1]["origin_details"] = f"ELITE_RATE_JOINT(parent={parent_sid})"
