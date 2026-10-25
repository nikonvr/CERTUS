"""Final joint (mode, wavelength) local search on the STRAT winner (`strat_local_search`, on by default since 2026-10-20).

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
    guard_is_armed,
    index_guided_settings,
    index_sensitivity_by_layer,
    joint_local_search,
    native_evaluator,
    nominal_level_index,
    presel_settings,
    search_params,
)
from certus.core.certus_strat_rate_rules import (
    allowed_rate_layers,
    optical_thicknesses_nm,
    rate_cap,
    rate_rules_from_params,
    sanitize_rate_layers,
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
    origin = ranked[0]["strategy"]
    start = origin
    nominal = list(pre_calc_data["p_thick_nominal"])
    base_seed = int(params.get("robustness_seed", 42)) if params.get("robustness_seed") is not None else 42  # as the task reads it
    rules = rate_rules_from_params(params)
    search_seed = base_seed + SEARCH_SEED_OFFSET
    check_seeds = tuple(base_seed + o for o in CHECK_SEED_OFFSETS)
    confirm_seeds = tuple(base_seed + o for o in CONFIRM_SEED_OFFSETS)
    with SharedIndicesWorker(shared_clues_info) as clues:
        free = {
            "grid": tuple(_resolve_monitoring_wavelength_grid(params, clues, pre_calc_data["all_wls"])),
            "nominal_level": nominal_level_index(params),
            "allow_rate": bool(params.get("allow_rate", True)),
            "presel_runs": presel_settings(params)[0],
            "presel_keep": presel_settings(params)[1],
            "index_guided_layers": index_guided_settings(params)[0],
            "index_guided_group": index_guided_settings(params)[1],
        }
        evaluate = native_evaluator(search_params(params), nominal, clues, pre_calc_data.get("full_dynamics_grid", {}))
        guard = guard_is_armed(params)
        evaluate_guard = native_evaluator(params, nominal, clues, pre_calc_data.get("full_dynamics_grid", {})) if guard else None
        sensitivity = None
        if free["index_guided_layers"] > 0:
            grid_dyn = pre_calc_data.get("full_dynamics_grid", {})
            sensitivity = index_sensitivity_by_layer(
                native_evaluator(search_params(params), nominal, clues, grid_dyn, thickness=True),
                native_evaluator({**search_params(params), "index_corridor": 0.0}, nominal, clues, grid_dyn, thickness=True),
                nominal, search_seed, LocalSearchConfig(grid=free["grid"]).search_runs, free["nominal_level"])
        free_report = None
        if rules.active and params.get("rate_rules_final_only"):  # as by hand: the free stage first, then its winner is converted
            start, free_report = joint_local_search(start, evaluate, len(nominal),
                                                    LocalSearchConfig(**free, rate_min_layer=RATE_MIN_LAYER), search_seed,
                                                    check_seeds, logger.info, confirm_seeds, evaluate_guard, sensitivity)
        ruled, convert = {}, ()
        if rules.active:  # the operator's Rate rules (certus_strat_rate_rules); inactive: the fields keep their defaults
            ot = optical_thicknesses_nm(params)
            ruled = {"rate_allowed": allowed_rate_layers(rules, ot), "rate_cap": rate_cap(rules, len(nominal)),
                     "repair_layers": frozenset(int(k) for k in start.get("rate_rules_converted", []))}
            if params.get("rate_rules_final_only"):  # the free winner is converted here, layer by layer, as by hand
                convert = tuple(sanitize_rate_layers(start.get("rate_layers"), rules, ot)[1])
        cfg = LocalSearchConfig(**free, rate_min_layer=max(RATE_MIN_LAYER, rules.min_layer), **ruled)
        plan, report = joint_local_search(start, evaluate, len(nominal), cfg, search_seed, check_seeds, logger.info,
                                          confirm_seeds, evaluate_guard, sensitivity, convert=convert)
        if free_report is not None:
            report["free_stage"] = free_report
        report["start_strategy_id"] = origin.get("strategy_id")
        report["search_index_corridor"] = search_params(params)["index_corridor"]
        if guard:
            report["guard_index_corridor"] = float(params.get("index_corridor", 0.0) or 0.0)
        if not report["accepted"] and not convert:  # converted, the plan obeys the rules even when the check refuses
            return rows, report, ranker
        strategy = copy.deepcopy(plan)
        strategy.update(origin="LOCAL_SEARCH", origin_details=f"LOCAL_SEARCH(parent={origin.get('strategy_id')})",
                        n_blocks=len(strategy["blocks"]))
        fresh_id = bool(params.get("strat_local_search_fresh_id", False))
        if fresh_id:
            from certus.core.certus_strat_ranking import next_refinement_strategy_id
            strategy.update(strategy_id=next_refinement_strategy_id(rows, len(strategy["blocks"])),
                            parent_strategy_id=origin.get("strategy_id"))
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
