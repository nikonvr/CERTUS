"""Final native Rate refinement using the existing full-depth scoring path."""

from __future__ import annotations

import copy
from typing import Any

from certus.core.certus_strat_rate_post import complete_score, refine_native_output
from certus.utils.certus_data import SharedIndicesWorker


def refine_rate_output(
    rows: list[dict[str, Any]], pre_calc_data: dict[str, Any], params: dict[str, Any], shared_clues_info: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Score fixed groups sequentially, with the native worker's exact float32 clues."""
    from certus.core.certus_strat_consensus import _resolve_consensus_ranking_params
    from certus.core.certus_strat_ranking import _resolve_monitoring_wavelength_grid
    from certus.core.certus_strat_robustness import run_final_simulation_block

    num_runs = int(params.get("robustness_num_runs", 150))
    cfg = _resolve_consensus_ranking_params(params, num_runs=num_runs)
    if not cfg["enabled"] or cfg["top_k"] < 9 or len(cfg["seeds"]) < 2:
        raise ValueError("Final Rate refinement requires consensus for every group of up to nine plans")
    scoring_params = {**params, "ablation_profile": False, "rate_post_refinement": False}
    with SharedIndicesWorker(shared_clues_info) as clues:
        context = {key: pre_calc_data[key] for key in ("p_thick_nominal", "nominal_matrix_cache", "all_wls")}
        context["clues_at_wl"] = clues
        grid = _resolve_monitoring_wavelength_grid(params, clues, pre_calc_data["all_wls"])

        def evaluate(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
            strategies = []
            for plan in plans:
                strategy = copy.deepcopy(plan)
                strategy.update(
                    strategy_id=plan["source_strategy_id"],
                    n_blocks=len(plan["blocks"]),
                    origin="RATE_POST",
                    origin_details=f"RATE_POST(parent={plan.get('native_source_id')})",
                )
                strategies.append(strategy)
            result = run_final_simulation_block(
                {**context, "all_strategies": strategies}, scoring_params, num_runs, expand_variants=False, refine=False
            )
            return result["all_strategies_results"]

        refined, report = refine_native_output(
            rows,
            grid,
            len(pre_calc_data["p_thick_nominal"]),
            cfg["seeds"],
            cfg["mode"],
            float(params.get("monochromator_resolution_nm", 0)),
            evaluate,
        )
    for row in refined:
        row["rate_post_consensus_eligible"] = complete_score(row, cfg["seeds"], cfg["mode"]) is not None
    report.update(
        robustness_seed=params.get("robustness_seed"),
        consensus_seeds=cfg["seeds"],
        base_num_runs=num_runs,
        consensus_num_runs=cfg["num_runs"],
        available_wls=grid,
        transport="native SharedIndicesWorker float32",
        anchors_injected=False,
    )
    return refined, report
