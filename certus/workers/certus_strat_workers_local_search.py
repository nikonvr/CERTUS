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
    with SharedIndicesWorker(shared_clues_info) as clues:
        grid = tuple(_resolve_monitoring_wavelength_grid(params, clues, pre_calc_data["all_wls"]))
        evaluate = native_evaluator(search_params(params), nominal, clues, pre_calc_data.get("full_dynamics_grid", {}))
        free_report = None
        if rules.active and params.get("rate_rules_final_only"):  # as by hand: the free stage first, then its winner is converted
            free_cfg = LocalSearchConfig(grid=grid, nominal_level=nominal_level_index(params),
                                         allow_rate=bool(params.get("allow_rate", True)), rate_min_layer=RATE_MIN_LAYER)
            start, free_report = joint_local_search(start, evaluate, len(nominal), free_cfg, base_seed + SEARCH_SEED_OFFSET,
                                                    tuple(base_seed + o for o in CHECK_SEED_OFFSETS), logger.info,
                                                    tuple(base_seed + o for o in CONFIRM_SEED_OFFSETS))
        ruled, convert = {}, ()
        if rules.active:  # the operator's Rate rules (certus_strat_rate_rules); inactive: the fields keep their defaults
            ot = optical_thicknesses_nm(params)
            ruled = {"rate_allowed": allowed_rate_layers(rules, ot), "rate_cap": rate_cap(rules, len(nominal)),
                     "repair_layers": frozenset(int(k) for k in start.get("rate_rules_converted", []))}
            if params.get("rate_rules_final_only"):  # the free winner is converted here, layer by layer, as by hand
                convert = tuple(sanitize_rate_layers(start.get("rate_layers"), rules, ot)[1])
        cfg = LocalSearchConfig(
            grid=grid,
            nominal_level=nominal_level_index(params),
            allow_rate=bool(params.get("allow_rate", True)),
            rate_min_layer=max(RATE_MIN_LAYER, rules.min_layer),
            **ruled,
        )
        plan, report = joint_local_search(start, evaluate, len(nominal), cfg, base_seed + SEARCH_SEED_OFFSET,
                                          tuple(base_seed + o for o in CHECK_SEED_OFFSETS), logger.info,
                                          tuple(base_seed + o for o in CONFIRM_SEED_OFFSETS), convert=convert)
        if free_report is not None:
            report["free_stage"] = free_report
        report["start_strategy_id"] = origin.get("strategy_id")
        report["search_index_corridor"] = search_params(params)["index_corridor"]
        if not report["accepted"] and not convert:  # converted, the plan obeys the rules even when the check refuses
            return rows, report, ranker
        strategy = copy.deepcopy(plan)
        strategy.update(origin="LOCAL_SEARCH", origin_details=f"LOCAL_SEARCH(parent={origin.get('strategy_id')})",
                        n_blocks=len(strategy["blocks"]))
        context = {key: pre_calc_data[key] for key in ("p_thick_nominal", "nominal_matrix_cache", "all_wls")}
        context["clues_at_wl"] = clues
        scoring_params = {**params, "ablation_profile": False, "strat_local_search": False}
        scored = run_final_simulation_block({**context, "all_strategies": [strategy]}, scoring_params,
                                            int(params.get("robustness_num_runs", 150)), expand_variants=False, refine=False)
    refined = scored["all_strategies_results"][0]

    def refined_first(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        others = [r for r in results if r is not refined]
        return [refined, *ranker(others)]

    return [*rows, refined], report, refined_first
