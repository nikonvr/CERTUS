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
from typing import Any, Iterable
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


def run_strat_sensitivity_audit(
    base_params: dict[str, Any],
    *,
    cases: Iterable[StratAuditCase] = DEFAULT_AUDIT_CASES,
    logger: logging.Logger | None = None,
) -> StratAuditSummary:
    """Run a compact sensitivity audit around the STRAT pipeline.

    The function executes the full optimization pipeline for a handful of
    perturbed parameter sets and compares the selected strategy signatures.
    """
    logger = logger or logging.getLogger(__name__)
    base_params = _copy_params(base_params)

    results: list[StratAuditResult] = []
    baseline_result: StratAuditResult | None = None
    sigs: list[str] = []

    for case in cases:
        params = _copy_params(base_params)
        params.update(case.overrides)
        logger.info("Running STRAT audit case %s with overrides=%s", case.name, case.overrides)
        try:
            output = optimize_block_strategy_hybrid(params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Audit case %s failed: %s", case.name, exc, exc_info=True)
            output = {"error": repr(exc)}
        strategy_id, signature, total_cost, n_blocks = _extract_strategy_fields(output)
        score_proxy = _score_proxy(output)
        res = StratAuditResult(
            name=case.name,
            strategy_signature=signature,
            strategy_id=strategy_id,
            total_cost=total_cost,
            n_blocks=n_blocks,
            score_proxy=score_proxy,
            payload=output if isinstance(output, dict) else {"result": repr(output)},
        )
        results.append(res)
        sigs.append(signature)
        if case.name == "baseline":
            baseline_result = res

    if baseline_result is None:
        baseline_result = results[0]

    sig_counts = {sig: sigs.count(sig) for sig in set(sigs)}
    dominant = max(sig_counts.values()) if sig_counts else 0
    dominant_ratio = dominant / max(1, len(sigs))
    probs = [count / len(sigs) for count in sig_counts.values()] if sig_counts else [1.0]
    entropy = float(-sum(p * np.log2(p) for p in probs if p > 0.0))
    stability_index = float(dominant_ratio / (1.0 + entropy))

    return StratAuditSummary(
        baseline=baseline_result,
        cases=results,
        stability_index=stability_index,
        signature_entropy=entropy,
        dominant_signature_ratio=dominant_ratio,
    )


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
