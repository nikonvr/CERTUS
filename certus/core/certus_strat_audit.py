"""STRAT scientific audit helpers.

This module provides a lightweight sensitivity audit for CERTUS-STRAT.
It is designed to help detect bias and instability in the strategy search
pipeline by perturbing key knobs and summarizing how much the selected
strategy changes.

The goal is not to re-run the full scientific engine here. Instead, the
helpers focus on:
- contract validation of input perturbations
- baseline-independent sensitivity scoring
- compact result summaries suitable for a Markdown report or notebook
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from collections.abc import Iterable
from typing import Any
import copy
import json
import logging

import numpy as np

from certus.core.certus_strat_pipeline import optimize_block_strategy_hybrid
from certus.utils.certus_strat_context import _strategy_signature
from certus.utils.certus_copy_utils import copy_result_dict


@dataclass(frozen=True)
class StratAuditCase:
    """Single sensitivity scenario for STRAT."""

    name: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class StratAuditResult:
    """Per-case audit output."""

    name: str
    strategy_signature: str
    strategy_id: Any
    total_cost: float | None
    n_blocks: int | None
    score_proxy: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class StratAuditSummary:
    """Aggregate sensitivity report."""

    baseline: StratAuditResult
    cases: list[StratAuditResult]
    stability_index: float
    signature_entropy: float
    dominant_signature_ratio: float


DEFAULT_AUDIT_CASES: tuple[StratAuditCase, ...] = (
    StratAuditCase("baseline", {}),
    StratAuditCase("dense_scan", {"scan_wl_step": 0.5}),
    StratAuditCase("coarse_scan", {"scan_wl_step": 2.0}),
    StratAuditCase("low_sym", {"sym_weight": 0.1, "sym_same_wl_bonus": 0.05}),
    StratAuditCase("high_sym", {"sym_weight": 0.6, "sym_same_wl_bonus": 0.25}),
    StratAuditCase("strict_floor", {"min_transmission_floor": 0.15}),
    StratAuditCase("loose_floor", {"min_transmission_floor": 0.05}),
)


def _copy_params(params: dict[str, Any]) -> dict[str, Any]:
    return copy_result_dict(params)


def _extract_strategy_fields(result: Any) -> tuple[Any, str, float | None, int | None]:
    if not isinstance(result, dict):
        return None, "", None, None
    strategy = result.get("best_strategy") or result.get("strategy") or result
    if not isinstance(strategy, dict):
        return None, "", None, None
    signature = _strategy_signature(strategy)
    cost_val = strategy.get("total_cost", strategy.get("cost"))
    try:
        total_cost = float(cost_val) if cost_val is not None else None
    except TypeError, ValueError:
        total_cost = None
    try:
        n_blocks = int(strategy.get("n_blocks", 0)) if strategy.get("n_blocks") is not None else None
    except TypeError, ValueError:
        n_blocks = None
    return (strategy.get("strategy_id"), signature, total_cost, n_blocks)


def _score_proxy(result: Any) -> float:
    if not isinstance(result, dict):
        return float("inf")
    score = result.get("robustness_score")
    if score is None:
        final = result.get("final_results") if isinstance(result.get("final_results"), dict) else None
        if final is not None:
            score = final.get("robustness_score")
    try:
        return float(score)
    except TypeError, ValueError:
        return float("inf")


def audit_summary_to_dict(summary: StratAuditSummary) -> dict[str, Any]:
    return {
        "baseline": asdict(summary.baseline),
        "cases": [asdict(c) for c in summary.cases],
        "stability_index": summary.stability_index,
        "signature_entropy": summary.signature_entropy,
        "dominant_signature_ratio": summary.dominant_signature_ratio,
    }


def audit_summary_to_json(summary: StratAuditSummary, *, indent: int = 2) -> str:
    return json.dumps(audit_summary_to_dict(summary), indent=indent, sort_keys=True, default=str)
