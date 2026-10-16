"""Passive native-pipeline observers; no CERTUS import or numerical implementation."""

from __future__ import annotations

import copy
import inspect
import threading
import traceback
from contextlib import ExitStack, contextmanager
from unittest.mock import patch


def plan_snapshot(strategy: dict) -> dict:
    keys = ("strategy_id", "n_blocks", "blocks", "rate_layers", "monochromator_resolution_nm",
            "witness_reset_layers", "origin", "origin_details", "parent_strategy_id")
    return copy.deepcopy({key: strategy[key] for key in keys if key in strategy})


def row_snapshot(row: dict) -> dict:
    keys = ("robustness_score", "robustness_score_base", "robustness_score_consensus",
            "robustness_consensus_meta", "crash_rate", "crash_eliminated", "crash_rates_by_noise",
            "elite_round", "elite_nominal_score", "min_resolution", "limiting_layer")
    result = copy.deepcopy({key: row[key] for key in keys if key in row})
    result["strategy"] = plan_snapshot(row.get("strategy") or {})
    result["noise_results"] = [{"noise_level": level.get("noise_level"), "rmse_p95": level.get("rmse_p95"),
                                "retained_draw_count": len(level.get("rmse_all", []))}
                               for level in row.get("results_per_noise", [])]
    return result


def json_default(value):
    """Convert saved NumPy scalars/arrays only when serializing a copied trace."""
    if type(value).__module__.split(".")[0] == "numpy":
        return value.tolist()
    raise TypeError(f"Unsupported trace value: {type(value).__name__}")


@contextmanager
def observe_pipeline(consensus, robustness):
    """Delegate every call unchanged and restore all temporary patches on exit."""
    trace = {"events": [], "limitations": [
        "Contract rejections are observed; private closure budget/deduplication exits are not all observed.",
        "A wrapped candidate adapter must expose the original factory signature through functools.wraps.",
        "retained_draw_count describes arrays present in the row, not the consensus simulation depth.",
        "Use recorded task arguments for actual physical runs; cached consensus calls need their cache events."]}
    lock = threading.RLock()
    context = {"elite_scope": None, "round": None}
    scope_counter = 0

    def record(kind, payload):
        with lock:
            trace["events"].append(copy.deepcopy({"event": len(trace["events"]), "kind": kind,
                                                   "context": context, **payload}))

    real_elite = consensus._apply_elite_refinement_if_enabled
    real_parents = consensus._log_elite_parents
    real_factory = consensus._generate_elite_candidate_strategies
    real_contract = consensus._validate_strategy_blocks_contract
    real_threshold = consensus._resolve_elite_nominal_and_target_threshold
    real_select = consensus._select_consensus_candidates
    real_cfg = consensus._log_consensus_ranking_enabled
    real_scores = consensus._apply_consensus_scores_to_results
    real_cache = consensus._consume_cached_consensus_score
    real_task = robustness._test_strategy_robustness_task
    real_finalize = robustness._finalize_robustness_results
    factory_signature = inspect.signature(real_factory)
    task_signature = inspect.signature(real_task)

    def elite(*args, **kwargs):
        nonlocal scope_counter
        bound = inspect.signature(real_elite).bind(*args, **kwargs).arguments
        ctx = bound["ctx"]
        previous = dict(context)
        with lock:
            scope_counter += 1
            context.update(elite_scope=scope_counter, round=None)
        record("elite_enter", {"num_layers": ctx.num_layers, "num_runs": ctx.num_runs,
                                "id_namespace_blocks": ctx.strategy_id_namespace_n_blocks,
                                "parents_before": [row_snapshot(r) for r in bound["strategies_results"]]})
        try:
            result = real_elite(*args, **kwargs)
            record("elite_exit", {"rows": [row_snapshot(r) for r in result]})
            return result
        finally:
            with lock:
                context.clear()
                context.update(previous)

    def parents(logger, elite_round, parent_results):
        with lock:
            context["round"] = elite_round
        record("parents", {"rows": [row_snapshot(r) for r in parent_results]})
        return real_parents(logger, elite_round, parent_results)

    def factory(*args, **kwargs):
        call = factory_signature.bind(*args, **kwargs)
        call.apply_defaults()
        bound = call.arguments
        record("generation_inputs", {"available_wls": list(bound["available_wls"]),
                                     "num_layers": bound["num_layers"],
                                     "parents": [row_snapshot(r) for r in bound["parent_results"]],
                                     "settings": {k: bound.get(k) for k in ("max_candidates", "max_rate_candidates",
                                                                           "round_robin_seed", "rate_moves", "balanced_rate_moves")}})
        candidates, cursor = real_factory(*args, **kwargs)
        record("generation_outputs", {"candidates": [plan_snapshot(s) for s in candidates], "cursor": cursor})
        return candidates, cursor

    def contract(*args, **kwargs):
        result = real_contract(*args, **kwargs)
        if not result[0]:
            strategy = args[0] if args else kwargs["strategy"]
            record("contract_rejection", {"plan": plan_snapshot(strategy), "reason": result[1]})
        return result

    def threshold(*args, **kwargs):
        result = real_threshold(*args, **kwargs)
        # The authoritative round is logged only afterwards, by _log_elite_parents.
        record("nominal_threshold", {"threshold_pair": result, "noise_level": kwargs.get("nominal_noise_level"),
                                      "context": {"elite_scope": context["elite_scope"], "round": None}})
        return result

    def select(*args, **kwargs):
        result = real_select(*args, **kwargs)
        record("consensus_selection", {"top_k": result[0], "selected": [row_snapshot(r) for r in result[1]]})
        return result

    def consensus_cfg(**kwargs):
        record("consensus_config", {k: v for k, v in kwargs.items() if k != "logger"})
        return real_cfg(**kwargs)

    def scores(**kwargs):
        result = real_scores(**kwargs)
        record("consensus_applied", {"rows": [row_snapshot(r) for r in kwargs["results_in"]]})
        return result

    def cache(**kwargs):
        result = real_cache(**kwargs)
        if result:
            record("consensus_cache_hit", {"cache_key": kwargs["cache_key"], "scores": list(kwargs["seed_scores"])})
        return result

    def task(*args, **kwargs):
        bound = task_signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        observed = {"id": values["strategy"].get("strategy_id"), "seed": values["params"].get("robustness_seed"),
                    "num_runs": values["num_runs"], "noise_levels": list(values["noise_levels"]),
                    "compute_layer_profile": values["compute_layer_profile"]}
        try:
            result = real_task(*args, **kwargs)
        except Exception:
            record("physical_task_error", {**observed, "error": traceback.format_exc()})
            raise
        kept = row_snapshot(result)
        kept.pop("strategy")
        record("physical_task_result", {**observed, "result": kept})
        return result

    def finalize(*args, **kwargs):
        result = real_finalize(*args, **kwargs)
        record("finalized_results", {"rows": [row_snapshot(r) for r in result["all_strategies_results"]]})
        return result

    with ExitStack() as patches:
        for module, name, wrapper in (
            (consensus, "_apply_elite_refinement_if_enabled", elite),
            (consensus, "_log_elite_parents", parents),
            (consensus, "_generate_elite_candidate_strategies", factory),
            (consensus, "_validate_strategy_blocks_contract", contract),
            (consensus, "_resolve_elite_nominal_and_target_threshold", threshold),
            (consensus, "_select_consensus_candidates", select),
            (consensus, "_log_consensus_ranking_enabled", consensus_cfg),
            (consensus, "_apply_consensus_scores_to_results", scores),
            (consensus, "_consume_cached_consensus_score", cache),
            (robustness, "_test_strategy_robustness_task", task),
            (robustness, "_finalize_robustness_results", finalize),
        ):
            patches.enter_context(patch.object(module, name, wrapper))
        yield trace
