"""Bounded, opt-in final refinement of parents from one native search output."""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Iterator
from itertools import zip_longest
from typing import Any

from certus.core.certus_strat_rate_moves import coarse, fine, signature, window_context


def complete_score(row: dict[str, Any], seeds: list[int], mode: str) -> float | None:
    """Require explicit finite, complete consensus; never rank a base score as consensus."""
    meta = row.get("robustness_consensus_meta") or {}
    score = row.get("robustness_score_consensus")
    if (
        meta.get("seeds") != seeds
        or meta.get("n_samples") != len(seeds)
        or meta.get("mode") != mode
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or row.get("crash_eliminated", False)
    ):
        return None
    return float(score)


def select_beam(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the best, then prefer a distinct Rate mask, with stable full-plan ties."""
    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = signature(entry["plan"])
        if key not in unique or entry["score"] < unique[key]["score"]:
            unique[key] = entry
    ordered = sorted(unique.values(), key=lambda e: (e["score"], signature(e["plan"])))
    if len(ordered) <= 1:
        return ordered
    mask = ordered[0]["plan"]["rate_layers"]
    other = next((entry for entry in ordered[1:] if entry["plan"]["rate_layers"] != mask), ordered[1])
    return [ordered[0], other]


def native_parents(rows: list[dict[str, Any]], seeds: list[int], mode: str, slit_nm: float) -> list[dict[str, Any]]:
    """Normalize only this invocation's own complete native results, without cached profiles."""
    entries = []
    for row in rows:
        score = complete_score(row, seeds, mode)
        if score is None:
            continue
        strategy = row["strategy"]
        plan = {
            "blocks": copy.deepcopy(strategy["blocks"]),
            "rate_layers": copy.deepcopy(strategy.get("rate_layers") or []),
            "source_strategy_id": strategy["strategy_id"],
            "native_source_id": strategy["strategy_id"],
            "monochromator_resolution_nm": strategy.get("monochromator_resolution_nm"),
        }
        if plan["monochromator_resolution_nm"] is None:
            plan["monochromator_resolution_nm"] = slit_nm
        for key in ("witness_reset_layers", "resolution_noise_factor"):
            if key in strategy:
                plan[key] = copy.deepcopy(strategy[key])
        entries.append({"plan": plan, "score": score})
    return copy.deepcopy(select_beam(entries))


def _stage_proposals(
    parents: list[dict[str, Any]],
    grid: list[float],
    num_layers: int,
    kind: str,
    stage: str,
    seen: set[str],
    ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    """Freeze a charged stage before its scores; rejected contracts also consume the quota."""
    from certus.utils.certus_strat_context import _validate_strategy_blocks_contract

    generator = coarse if stage == "coarse" else fine
    streams: list[Iterator[dict[str, Any] | None]] = []
    accepted: list[dict[str, Any]] = []
    record: dict[str, Any] = {
        "pass": ledger["pass"],
        "stage": stage,
        "parents": copy.deepcopy(parents),
        "records": [],
        "before_scores": True,
    }
    for entry in parents:
        try:
            window_context(entry["plan"], num_layers, kind)
        except ValueError as error:
            record["records"].append({"status": "not_applicable", "parent": entry["plan"], "reason": str(error)})
            streams.append(iter(()))
        else:
            streams.append(generator(entry["plan"], grid, num_layers, kind))
    for items in zip_longest(*streams):
        for parent, plan in zip(parents, items, strict=True):
            if plan is None:
                record["records"].append({"status": "boundary_or_exhausted"})
                continue
            key = signature(plan)
            if key in seen:
                record["records"].append({"status": "duplicate", "plan": plan})
                continue
            if ledger["pass_proposals"] >= 300 or ledger["new_proposals"] >= 600:
                record["records"].append({"status": "quota_rejected", "plan": plan})
                continue
            seen.add(key)
            ledger["pass_proposals"] += 1
            ledger["new_proposals"] += 1
            plan.update(
                source_strategy_id=ledger["next_id"], root_parent_id=parent["plan"]["root_parent_id"], branch="native"
            )
            ledger["next_id"] += 1
            valid, reason = _validate_strategy_blocks_contract(plan, num_layers)
            record["records"].append(
                {"status": "accepted" if valid else "contract_rejected", "reason": reason, "plan": plan}
            )
            if valid:
                accepted.append(plan)
    ledger["stages"].append(record)
    return accepted


def _evaluate_batch(
    plans: list[dict[str, Any]],
    evaluate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    seeds: list[int],
    mode: str,
    ledger: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate once, keeping non-finite and incomplete outcomes in the diagnostic ledger."""
    offered = copy.deepcopy(plans)
    rows = evaluate(copy.deepcopy(offered))
    by_id = {row["strategy"]["strategy_id"]: row for row in rows}
    entries: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for plan in offered:
        row = by_id.get(plan["source_strategy_id"])
        score = complete_score(row, seeds, mode) if row else None
        if score is None:
            rejected.append({"plan": plan, "reason": "missing, non-finite, rejected or incomplete consensus"})
        else:
            entries.append({"plan": plan, "score": score})
    ledger["groups"].append(
        {"plans": offered, "eligible_ids": [e["plan"]["source_strategy_id"] for e in entries], "rejected": rejected}
    )
    return entries, rows


def refine_native_output(
    rows: list[dict[str, Any]],
    grid: list[float],
    num_layers: int,
    seeds: list[int],
    mode: str,
    slit_nm: float,
    evaluate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the measured two-pass/beam-two method, with no historical plans or anchors injected."""
    parents = native_parents(rows, seeds, mode, slit_nm)
    ledger: dict[str, Any] = {
        "new_proposals": 0,
        "groups": [],
        "stages": [],
        "passes": [],
        "parents": copy.deepcopy(parents),
        "next_id": max((int(r["strategy"]["strategy_id"]) for r in rows), default=0) + 1,
    }
    if not parents:
        ledger["status"] = "no_complete_native_parent"
        return rows, ledger
    for parent in parents:
        parent["plan"].update(source_strategy_id=ledger["next_id"], root_parent_id=ledger["next_id"], branch="native")
        ledger["next_id"] += 1
    pool, scored = _evaluate_batch([p["plan"] for p in parents], evaluate, seeds, mode, ledger)
    if not pool:
        raise RuntimeError("No native parent retained complete consensus on the required scoring path")
    seen = {signature(entry["plan"]) for entry in pool}
    for pass_number, kind in enumerate(("internal", "prefix"), start=1):
        before = min(entry["score"] for entry in pool)
        ledger.update(pass_proposals=0)
        ledger["pass"] = pass_number
        for stage in ("coarse", "fine"):
            proposals = _stage_proposals(copy.deepcopy(select_beam(pool)), grid, num_layers, kind, stage, seen, ledger)
            for offset in range(0, len(proposals), 9):
                if len(ledger["groups"]) >= 73:
                    raise RuntimeError("Bounded final-refinement group quota exhausted")
                entries, evaluated = _evaluate_batch(proposals[offset : offset + 9], evaluate, seeds, mode, ledger)
                pool.extend(entries)
                scored.extend(evaluated)
        after = min(entry["score"] for entry in pool)
        improved = before - after > max(1e-10, 1e-7 * abs(before))
        ledger["passes"].append(
            {
                "pass": pass_number,
                "before": before,
                "after": after,
                "improved": improved,
                "proposals": ledger["pass_proposals"],
            }
        )
        if not improved:
            break
    winner = select_beam(pool)[0]
    ledger.update(status="complete", winner=copy.deepcopy(winner["plan"]), best_score=winner["score"])
    return [*rows, *scored], ledger


def rank_complete_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """On the opt-in route, retain incomplete rows but do not rank them as full consensus."""
    return sorted(
        rows,
        key=lambda row: (
            not row.get("rate_post_consensus_eligible", False),
            float(row.get("robustness_score_consensus", math.inf))
            if row.get("rate_post_consensus_eligible", False)
            else float(row.get("robustness_score", math.inf)),
            signature(row["strategy"]),
        ),
    )
