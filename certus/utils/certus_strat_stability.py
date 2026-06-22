"""STRAT stability audit helpers.

These helpers load a reference JSON artifact, compute stability signals,
and generate a Markdown report that can be used as an offline audit artifact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class StratStabilitySummary:
    strategies_count_baseline: int
    strategies_count_perturbed: int
    same_best_strategy_id: bool
    same_best_origin: bool
    best_strategy_id_baseline: int | None
    best_strategy_id_perturbed: int | None
    best_origin_baseline: str | None
    best_origin_perturbed: str | None
    best_robustness_score_baseline: float | None
    best_robustness_score_perturbed: float | None
    top5_overlap: int
    top5_jaccard: float
    score_delta: float | None

    @property
    def is_stable(self) -> bool:
        return self.same_best_strategy_id and self.same_best_origin

    @property
    def score_regression(self) -> float | None:
        return self.score_delta



def load_stability_reference(path: str | Path) -> dict[str, Any]:
    """Load a STRAT stability reference JSON file."""
    ref_path = Path(path)
    with ref_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("stability reference must be a JSON object")
    return payload



def _top5_ids(entry: dict[str, Any]) -> set[int]:
    top5 = entry.get("top5")
    if not isinstance(top5, Iterable) or isinstance(top5, (str, bytes)):
        return set()
    ids: set[int] = set()
    for item in top5:
        if not isinstance(item, dict):
            continue
        try:
            ids.add(int(item.get("id")))
        except (TypeError, ValueError, AttributeError):
            continue
    return ids



def summarize_stability_reference(payload: dict[str, Any]) -> StratStabilitySummary:
    """Summarize the baseline and perturbation stability outcome."""
    baseline = payload.get("baseline") or {}
    perturbed = payload.get("stability_seed_plus_1") or {}
    base_ids = _top5_ids(baseline)
    pert_ids = _top5_ids(perturbed)
    union = base_ids | pert_ids
    overlap = len(base_ids & pert_ids)
    jaccard = (overlap / len(union)) if union else 1.0
    base_score = baseline.get("best_robustness_score")
    pert_score = perturbed.get("best_robustness_score")
    score_delta = None
    if base_score is not None and pert_score is not None:
        score_delta = float(pert_score) - float(base_score)
    return StratStabilitySummary(
        strategies_count_baseline=int(baseline.get("strategies_count", 0)),
        strategies_count_perturbed=int(perturbed.get("strategies_count", 0)),
        same_best_strategy_id=bool(payload.get("same_best_strategy_id", False)),
        same_best_origin=bool(payload.get("same_best_origin", False)),
        best_strategy_id_baseline=baseline.get("best_strategy_id"),
        best_strategy_id_perturbed=perturbed.get("best_strategy_id"),
        best_origin_baseline=baseline.get("best_origin"),
        best_origin_perturbed=perturbed.get("best_origin"),
        best_robustness_score_baseline=base_score,
        best_robustness_score_perturbed=pert_score,
        top5_overlap=overlap,
        top5_jaccard=jaccard,
        score_delta=score_delta,
    )



def _fmt_score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.12f}"



def build_markdown_report(payload: dict[str, Any], summary: StratStabilitySummary, *, source_name: str = "STRAT stability reference") -> str:
    """Build a Markdown audit report from a stability reference payload."""
    baseline = payload.get("baseline") or {}
    perturbed = payload.get("stability_seed_plus_1") or {}

    lines = [
        "# STRAT stability audit report",
        "",
        f"Source: `{source_name}`",
        "",
        "## Executive verdict",
        f"- Stable best strategy: **{'yes' if summary.is_stable else 'no'}**",
        f"- Same best strategy id: **{'yes' if summary.same_best_strategy_id else 'no'}**",
        f"- Same best origin: **{'yes' if summary.same_best_origin else 'no'}**",
        f"- Top 5 overlap: **{summary.top5_overlap}/5**",
        f"- Top 5 Jaccard: **{summary.top5_jaccard:.3f}**",
        f"- Score delta: **{_fmt_score(summary.score_delta)}**",
        "",
        "## Baseline",
        f"- Strategies count: {summary.strategies_count_baseline}",
        f"- Best strategy id: {summary.best_strategy_id_baseline}",
        f"- Best origin: {summary.best_origin_baseline}",
        f"- Best robustness score: {_fmt_score(summary.best_robustness_score_baseline)}",
        f"- Origin counts top20: `{baseline.get('origin_counts_top20', {})}`",
        "",
        "## Perturbed run",
        f"- Strategies count: {summary.strategies_count_perturbed}",
        f"- Best strategy id: {summary.best_strategy_id_perturbed}",
        f"- Best origin: {summary.best_origin_perturbed}",
        f"- Best robustness score: {_fmt_score(summary.best_robustness_score_perturbed)}",
        f"- Origin counts top20: `{perturbed.get('origin_counts_top20', {})}`",
        "",
        "## Top 5 overlap",
        "| Rank | Baseline id | Baseline origin | Baseline score | Perturbed id | Perturbed origin | Perturbed score |",
        "|---|---:|---|---:|---:|---|---:|",
    ]

    base_top5 = baseline.get("top5")
    if not isinstance(base_top5, list):
        base_top5 = []
    pert_top5 = perturbed.get("top5")
    if not isinstance(pert_top5, list):
        pert_top5 = []
    max_rows = max(len(base_top5), len(pert_top5))
    for i in range(max_rows):
        b_item = base_top5[i] if i < len(base_top5) else None
        p_item = pert_top5[i] if i < len(pert_top5) else None
        b = b_item if isinstance(b_item, dict) else {}
        p = p_item if isinstance(p_item, dict) else {}
        lines.append(
            f"| {i + 1} | {b.get('id', '—')} | {b.get('origin', '—')} | {_fmt_score(b.get('score'))} | "
            f"{p.get('id', '—')} | {p.get('origin', '—')} | {_fmt_score(p.get('score'))} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "- If the best strategy and origin remain unchanged, the strategy family is stable on this reference case.",
            "- A high top-5 Jaccard indicates that ranking stability is strong, not just the winner.",
            "- A low score delta suggests the perturbation did not meaningfully alter the quality frontier.",
            "",
        ]
    )
    return "\n".join(lines)



def write_markdown_report(output_path: str | Path, payload: dict[str, Any], summary: StratStabilitySummary, *, source_name: str = "STRAT stability reference") -> Path:
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown_report(payload, summary, source_name=source_name), encoding="utf-8")
    return out_path



def run_reference_audit(reference_json: str | Path, output_md: str | Path | None = None) -> StratStabilitySummary:
    """Load a reference JSON, compute stability, and optionally write a Markdown report."""
    payload = load_stability_reference(reference_json)
    summary = summarize_stability_reference(payload)
    if output_md is not None:
        write_markdown_report(output_md, payload, summary, source_name=str(reference_json))
    return summary



def summarize_many(payloads: Iterable[dict[str, Any]]) -> list[StratStabilitySummary]:
    """Convenience helper for future multi-reference audits."""
    return [summarize_stability_reference(payload) for payload in payloads]
