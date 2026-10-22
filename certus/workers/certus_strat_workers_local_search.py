"""Final joint (mode, wavelength) local search on the STRAT winner (`strat_local_search`, off by default).

The algorithm and its measurement live in `certus/core/certus_strat_local_search.py`; this module only gives it the
worker's shared clues and puts the refined plan, scored like every other row, at the head of the final ranking.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from certus.core.certus_strat_local_search import (
    CHECK_SEED_OFFSETS,
    CONFIRM_SEED_OFFSETS,
    SEARCH_SEED_OFFSET,
    LocalSearchConfig,
    joint_local_search,
    native_evaluator,
    nominal_level_index,
    search_params,
)
from certus.utils.certus_data import SharedIndicesWorker

Ranker = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def run_local_search(
    rows: list[dict[str, Any]],
    pre_calc_data: dict[str, Any],
    params: dict[str, Any],
    shared_clues_info: dict[str, Any],
    ranker: Ranker,
) -> tuple[list[dict[str, Any]], dict[str, Any], Ranker]:
    """Refine the best row; return (rows, report, ranker). The ranker puts an accepted refined plan first."""
    from certus.core.certus_strat_ranking import _resolve_monitoring_wavelength_grid
    from certus.core.certus_strat_robustness import run_final_simulation_block
    from certus.core.certus_strat_robustness_rate import RATE_MIN_LAYER

    logger = params["logger"]
    ranked = ranker(list(rows))
    start = ranked[0]["strategy"]
    nominal = list(pre_calc_data["p_thick_nominal"])
    base_seed = int(params.get("robustness_seed", 42)) if params.get("robustness_seed") is not None else 42  # as the task reads it
    with SharedIndicesWorker(shared_clues_info) as clues:
        cfg = LocalSearchConfig(
            grid=tuple(_resolve_monitoring_wavelength_grid(params, clues, pre_calc_data["all_wls"])),
            nominal_level=nominal_level_index(params),
            allow_rate=bool(params.get("allow_rate", True)),
            rate_min_layer=RATE_MIN_LAYER,
        )
        evaluate = native_evaluator(search_params(params), nominal, clues, pre_calc_data.get("full_dynamics_grid", {}))
        guard = bool(params.get("strat_local_search_guard", False))
        evaluate_guard = native_evaluator(params, nominal, clues, pre_calc_data.get("full_dynamics_grid", {})) if guard else None
        plan, report = joint_local_search(start, evaluate, len(nominal), cfg, base_seed + SEARCH_SEED_OFFSET,
                                          tuple(base_seed + o for o in CHECK_SEED_OFFSETS), logger.info,
                                          tuple(base_seed + o for o in CONFIRM_SEED_OFFSETS), evaluate_guard)
        report["start_strategy_id"] = start.get("strategy_id")
        report["search_index_corridor"] = search_params(params)["index_corridor"]
        if guard:
            report["guard_index_corridor"] = float(params.get("index_corridor", 0.0) or 0.0)
        if not report["accepted"]:
            return rows, report, ranker
        strategy = copy.deepcopy(plan)
        strategy.update(origin="LOCAL_SEARCH", origin_details=f"LOCAL_SEARCH(parent={start.get('strategy_id')})",
                        n_blocks=len(strategy["blocks"]))
        fresh_id = bool(params.get("strat_local_search_fresh_id", False))
        if fresh_id:
            from certus.core.certus_strat_ranking import next_refinement_strategy_id
            strategy.update(strategy_id=next_refinement_strategy_id(rows, len(strategy["blocks"])),
                            parent_strategy_id=start.get("strategy_id"))
        context = {key: pre_calc_data[key] for key in ("p_thick_nominal", "nominal_matrix_cache", "all_wls")}
        context["clues_at_wl"] = clues
        scoring_params = {**params, "ablation_profile": False, "strat_local_search": False}
        scored = run_final_simulation_block({**context, "all_strategies": [strategy]}, scoring_params,
                                            int(params.get("robustness_num_runs", 150)), expand_variants=False, refine=False)
    refined = scored["all_strategies_results"][0]

    def refined_first(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return rank_refined_first(refined, results, ranker, check_ids=fresh_id)

    return [*rows, refined], report, refined_first


def rank_refined_first(refined: dict[str, Any], results: list[dict[str, Any]], ranker: Ranker,
                       check_ids: bool = False) -> list[dict[str, Any]]:
    """The refined plan first, the others in the ranker's order.

    The ranker checks the ids of the others only. With `check_ids` (`strat_local_search_fresh_id`, off by default) the
    whole list goes through `validate_unique_strategy_ids`: without a fresh id the refined row carries its parent's id
    (8 accepted benches of 8, reports/ANALYSE_claude_2026-10-22), which that check exists to withhold.
    """
    ordered = [refined, *ranker([r for r in results if r is not refined])]
    if check_ids:
        from certus.core.certus_strat_ranking import validate_unique_strategy_ids
        validate_unique_strategy_ids(ordered)
    return ordered
