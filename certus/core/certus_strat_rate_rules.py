"""Operator rules on which layers may be laid by Rate: first layer allowed, largest optical thickness, largest share.

The owner's rules for the 90-layer Bonne Mere strategy (2026-10-24): no Rate before layer 10, Rate only on a layer whose
optical thickness n.d is at most 50 nm (the rule of the retained sapphire plan), and about as many optical layers as on
sapphire. STRAT ranks on SEEL alone; with indices known to +-0.01 the Rate wins almost everywhere (61 Rate layers out of
90), so these preferences have to be stated, they are not found.

Three settings, all inactive by default (the path is then unchanged):
    rate_min_layer                  first layer index (from 0, substrate side) that may be laid by Rate; 0 = no rule
    rate_max_optical_thickness_nm   Rate only if n(l0).d <= this value, n.d = multiplier . l0 / 4; 0 = no rule
    rate_max_fraction               at most this share of the layers by Rate, e.g. 0.25; 0 or >= 1 = no rule

One place applies them to every evaluated plan (`apply_rate_rules`, called by the robustness pool before any draw): a
forbidden Rate layer is laid optically at the wavelength of its block, and the plan records it in `rate_rules_converted`
so the local search scans its whole wavelength grid. Over the share, the thickest Rate layers go optical first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RateRules:
    """The three rules; zero means no rule."""

    min_layer: int = 0
    max_optical_thickness_nm: float = 0.0
    max_fraction: float = 0.0

    @property
    def active(self) -> bool:
        return self.min_layer > 0 or self.max_optical_thickness_nm > 0.0 or 0.0 < self.max_fraction < 1.0


def rate_rules_from_params(params: dict[str, Any]) -> RateRules:
    """The rules a run carries; missing or empty keys mean no rule."""
    return RateRules(
        min_layer=int(params.get("rate_min_layer") or 0),
        max_optical_thickness_nm=float(params.get("rate_max_optical_thickness_nm") or 0.0),
        max_fraction=float(params.get("rate_max_fraction") or 0.0),
    )


def rate_rules_params(config: Any) -> dict[str, float]:
    """The three settings read from a JSON configuration, for the run's params; a missing or unreadable value is 0 (no rule)."""
    out = {}
    for key in ("rate_min_layer", "rate_max_optical_thickness_nm", "rate_max_fraction"):
        try:
            value = float((config or {}).get(key) or 0.0)
        except (TypeError, ValueError, AttributeError):
            value = 0.0
        out[key] = int(value) if key == "rate_min_layer" else value
    return out


def optical_thicknesses_nm(params: dict[str, Any]) -> np.ndarray:
    """n(l0).d of every layer from the stack multipliers (QWOT at l0): multiplier . l0 / 4."""
    multipliers = [float(e) for e in str(params.get("stack_string", "")).split(",") if e.strip()]
    return np.asarray(multipliers, dtype=np.float64) * float(params["l0"]) / 4.0


def allowed_rate_layers(rules: RateRules, optical_thickness: np.ndarray) -> frozenset[int]:
    """The layers the first two rules allow in Rate."""
    return frozenset(
        k for k, ot in enumerate(optical_thickness)
        if k >= rules.min_layer and (rules.max_optical_thickness_nm <= 0.0 or ot <= rules.max_optical_thickness_nm)
    )


def rate_cap(rules: RateRules, n_layers: int) -> int | None:
    """The largest number of Rate layers, or None without a share rule."""
    if not 0.0 < rules.max_fraction < 1.0:
        return None
    return math.floor(rules.max_fraction * n_layers + 1e-9)


def sanitize_rate_layers(rate_layers: Any, rules: RateRules, optical_thickness: np.ndarray) -> tuple[list[int], list[int]]:
    """(kept, converted): the Rate layers the rules keep, and those they lay optically, both sorted."""
    layers = sorted({int(k) for k in rate_layers or []})
    allowed = allowed_rate_layers(rules, optical_thickness)
    kept = [k for k in layers if k in allowed]
    cap = rate_cap(rules, len(optical_thickness))
    if cap is not None and len(kept) > cap:
        by_thickness = sorted(kept, key=lambda k: (optical_thickness[k], k))
        kept = sorted(by_thickness[:cap])
    return kept, sorted(set(layers) - set(kept))


def apply_rate_rules(strategies: list[dict[str, Any]], params: dict[str, Any]) -> int:
    """Make every plan obey the rules, in place; return how many plans changed. Nothing happens without an active rule."""
    rules = rate_rules_from_params(params)
    if not rules.active:
        return 0
    optical_thickness = optical_thicknesses_nm(params)
    changed = 0
    for strategy in strategies:
        kept, converted = sanitize_rate_layers(strategy.get("rate_layers"), rules, optical_thickness)
        if converted:
            strategy["rate_layers"] = kept
            strategy["rate_rules_converted"] = sorted({*strategy.get("rate_rules_converted", []), *converted})
            changed += 1
    return changed
