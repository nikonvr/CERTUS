"""
CERTUS STRAT PIPELINE
=====================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- optimize_block_strategy_hybrid (Master orchestrator)
- _prepare_block_strategy_phase_a
- _prepare_block_strategy_phase_b
- _finalize_block_strategy_result
"""

import logging
import traceback
import numpy as np
from typing import Any

from certus_physics import arange_inclusive

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_strat_config import (
    APP_CONTEXT,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    precompute_clues_and_matrices,
    get_refractive_index,
)
from certus.core.certus_strat_ranking import (
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_SCORING_MODE,
    mine_strategies_for_block_count,
    _filter_valid_robustness_strategies,
    _select_best_strat_result,
)
from certus.core.certus_strat_robustness import (
    run_final_simulation_block,
    _validate_strategy_min_transmission_floor,
)


def _prepare_block_strategy_phase_a(
    params: dict[str, Any],
    progress_signal: Any | None = None,
) -> dict[str, Any]:
    """Build Phase A context and execute the layer-by-layer search."""
    logger = params["logger"]
    logger.info("=" * 80)
    logger.info("STEP 2: ITERATIVE THICKNESS OPTIMIZATION (Refactored 2026)")
    logger.info("=" * 80)

    l0 = float(params["l0"])
    stack_string = params["stack_string"]
    multipliers = [float(e) for e in stack_string.split(",") if e.strip()]

    p_thick_nominal = params.get("p_thick_nominal")
    if p_thick_nominal is None:
        nH_at_l0 = get_refractive_index(params["nH_id"], l0)
        nL_at_l0 = get_refractive_index(params["nL_id"], l0)
        p_thick_nominal = [
            (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0))
            for i, m in enumerate(multipliers)
        ]

    num_layers = len(p_thick_nominal)
    clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(params, p_thick_nominal, logger)
    scan_wl_range = arange_inclusive(params["scan_wl_min"], params["scan_wl_max"], params["scan_wl_step"])

    logger.info("\n--- PHASE A: Layer-by-Layer Optimization (Robust Validation) ---")
    
    # Import solvers helpers dynamically to prevent circular imports
    from certus.core.certus_strat_solvers import (
        _run_phase_a_hybrid_loop,
        _normalize_phase_a_results,
        _build_symmetry_bonus_map,
        _build_layer_importance_map,
    )

    raw_results_thickness, full_dynamics_grid, phase_a_observability, stop_requested = _run_phase_a_hybrid_loop(
        params=params,
        p_thick_nominal=p_thick_nominal,
        clues_at_wl=clues_at_wl,
        scan_wl_range=scan_wl_range,
        num_layers=num_layers,
        logger=logger,
        progress_signal=progress_signal,
        l0=l0,
    )

    if stop_requested:
        return {
            "stop_requested": True,
            "raw_results_thickness": raw_results_thickness,
            "phase_a_observability": phase_a_observability,
            "l0": l0,
            "p_thick_nominal": p_thick_nominal,
        }

    logger.info("\n--- Phase A: Normalization ---")
    raw_results_sq = _normalize_phase_a_results(raw_results_thickness, num_layers)

    result_phase_a = {
        "l0": l0,
        "p_thick_nominal": p_thick_nominal,
        "clues_at_wl": clues_at_wl,
        "nominal_matrix_cache": nominal_matrix_cache,
        "all_wls": all_wls,
        "raw_results_thickness": raw_results_thickness,
        "raw_results_sq": raw_results_sq,
        "full_dynamics_grid": full_dynamics_grid,
        "phase_a_observability": phase_a_observability,
        "num_layers": num_layers,
    }

    sym_enable = bool(params.get("sym_enable", True))
    sym_window_ot = float(params.get("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT))
    result_phase_a["sym_bonus_map"] = (
        _build_symmetry_bonus_map(raw_results_thickness, num_layers, sym_window_ot) if sym_enable else {}
    )
    result_phase_a["sym_layer_importance"] = (
        _build_layer_importance_map(raw_results_thickness, num_layers) if sym_enable else {}
    )
    return result_phase_a


def _prepare_block_strategy_phase_b(
    phase_a: dict[str, Any],
    params: dict[str, Any],
    progress_signal: Any | None = None,
) -> dict[str, Any]:
    """Build block strategies and run robustness screening."""
    logger = params["logger"]
    logger.info("\n--- PHASE B: Grouping & Robustness (Sequential Mode) ---")

    raw_results_thickness = phase_a["raw_results_thickness"]
    raw_results_sq = phase_a["raw_results_sq"]
    num_layers = phase_a["num_layers"]
    all_strategies = []

    # Import from solvers at runtime
    from certus.core.certus_strat_solvers import _compute_blocks_range_for_params

    blocks_range = _compute_blocks_range_for_params(num_layers, params, dense=False)
    for n_blk in blocks_range:
        logger.info(f"   Exploring {n_blk} blocks...")
        strats = mine_strategies_for_block_count(
            n_blk,
            raw_results_thickness,
            raw_results_sq,
            num_layers,
            top_k=5,
            sym_enable=bool(params.get("sym_enable", True)),
            sym_bonus_map=phase_a.get("sym_bonus_map", {}),
            layer_importance_map=phase_a.get("sym_layer_importance", {}),
            sym_weight=float(params.get("sym_weight", SYM_DEFAULT_WEIGHT)),
            sym_same_wl_bonus=float(params.get("sym_same_wl_bonus", SYM_DEFAULT_SAME_WL_BONUS)),
            sym_continuity_weight=float(params.get("sym_continuity_weight", SYM_DEFAULT_CONTINUITY_WEIGHT)),
            sym_adaptive_same_wl=bool(params.get("sym_adaptive_same_wl", True)),
            sym_scoring_mode=str(params.get("sym_scoring_mode", SYM_DEFAULT_SCORING_MODE)),
            sym_allow_hybrid=bool(params.get("sym_allow_hybrid", False)),
        )
        all_strategies.extend(strats)

    phase_b: dict[str, Any] = {"all_strategies": all_strategies}
    if not all_strategies:
        logger.warning("⚠️ No strategies found in Phase B grouping.")
        phase_b["final_results"] = None
        phase_b["best_strategy"] = None
        phase_b["best_strategy_tmin_report"] = None
        return phase_b

    logger.info(f"   Running Robustness Screening on {len(all_strategies)} strategies...")
    phase_b_input = dict(phase_a)
    phase_b_input["all_strategies"] = all_strategies
    final_results = run_final_simulation_block(
        phase_b_input, params, num_runs=int(params.get("robustness_num_runs", 150))
    )
    final_results.update(phase_a)

    best_strategy = final_results.get("best_strategy")
    min_t_floor = float(params.get("min_transmission_floor", 0.10))
    enforce_post_check = bool(params.get("enforce_best_strategy_tmin_check", True))
    tmin_report = None

    if best_strategy and min_t_floor > 0.0 and enforce_post_check:
        strategy_for_check = dict(best_strategy)
        strategy_for_check["l0"] = float(phase_a["l0"])
        tmin_report, tmin_violations = _validate_strategy_min_transmission_floor(
            strategy_for_check,
            phase_a["p_thick_nominal"],
            phase_a["clues_at_wl"],
            phase_a["nominal_matrix_cache"],
            phase_a["all_wls"],
            min_t_floor,
        )
        final_results["best_strategy_tmin_report"] = tmin_report

        if tmin_violations:
            sample = ", ".join(
                [f"L{int(v['layer'])}@{v['wl']:.1f}nm:{v['t_min'] * 100:.2f}%" for v in tmin_violations[:5]]
            )
            raise RuntimeError(
                f"Post-check failed: best strategy violates T_min >= {min_t_floor * 100:.1f}% "
                f"on {len(tmin_violations)} layer(s). {sample}"
            )

        logger.info(
            f"[POST-CHECK] Best strategy T_min floor OK on {len(tmin_report)} layers "
            f"(threshold {min_t_floor * 100:.1f}%)."
        )

    phase_b["final_results"] = final_results
    phase_b["best_strategy"] = best_strategy
    phase_b["best_strategy_tmin_report"] = tmin_report
    return phase_b


def _finalize_block_strategy_result(
    phase_a: dict[str, Any],
    phase_b: dict[str, Any] | None,
    params: dict[str, Any],
    phase_a_only: bool = False,
) -> dict[str, Any]:
    """Return the final strategy payload with consistent fallbacks."""
    # Import solvers helper dynamically to prevent circular imports
    from certus.core.certus_strat_solvers import _export_phase_a_observability_json

    _export_phase_a_observability_json(params, phase_a.get("phase_a_observability", {}))

    if phase_a.get("stop_requested"):
        return {
            "raw_results_thickness": phase_a.get("raw_results_thickness"),
            "phase_a_observability": phase_a.get("phase_a_observability"),
            "stop_requested": True,
        }

    if phase_a_only or phase_b is None or phase_b.get("final_results") is None:
        if phase_a_only:
            params["logger"].info("✓ Phase A complete (Data Ready).")
        if phase_b and phase_b.get("all_strategies") is not None:
            phase_a["all_strategies"] = phase_b.get("all_strategies", [])
        return phase_a

    return phase_b["final_results"]


def optimize_block_strategy_hybrid(
    params: dict[str, Any],
    progress_signal: Any | None = None,
    _plot_signal: Any | None = None,
    phase_a_only: bool = False,
) -> dict[str, Any]:
    """Master orchestrator for the CERTUS-STRAT optimization pipeline.

    Execute a two-phase approach to find the best optical monitoring strategy
    for a given thin-film stack design:

    **Phase A - Layer-by-Layer Candidate Search**
        For every layer i (0 ... N-1):
        1. Recompute the TMM matrix cache using the average simulated
           thicknesses of previous layers (reality-feedback loop).
        2. _select_candidates_phase_a - rank wavelengths by |DeltaT|, filter
           extrema and resolution.
        3. _validate_candidates_phase_a - Monte Carlo noise simulation
           to score each candidate by P95 error.
        4. Propagate the simulated thickness errors to run_states for the
           next layer (cumulative error propagation).

    **Phase B - Block Grouping & Robustness**
        1. mine_strategies_for_block_count - dynamic-programming
           segmentation into monochromatic blocks (1 ... N blocks).
        2. run_final_simulation_block - full Monte Carlo robustness
           screening of each strategy at multiple noise levels.
    """
    logger = params["logger"]

    try:
        l0 = float(params["l0"])
        stack_string = params["stack_string"]
        multipliers = [float(e) for e in stack_string.split(",") if e.strip()]

        p_thick_nominal = params.get("p_thick_nominal")
        if p_thick_nominal is None:
            nH_at_l0 = get_refractive_index(params["nH_id"], l0)
            nL_at_l0 = get_refractive_index(params["nL_id"], l0)
            p_thick_nominal = [
                (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0))
                for i, m in enumerate(multipliers)
            ]

        phase_a = _prepare_block_strategy_phase_a(params=params, progress_signal=progress_signal)
        if phase_a.get("stop_requested"):
            return _finalize_block_strategy_result(phase_a, None, params, phase_a_only=phase_a_only)
        if phase_a_only:
            return _finalize_block_strategy_result(phase_a, None, params, phase_a_only=True)
        phase_b = _prepare_block_strategy_phase_b(phase_a=phase_a, params=params, progress_signal=progress_signal)
        return _finalize_block_strategy_result(phase_a, phase_b, params, phase_a_only=phase_a_only)

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logger.error(f"CRITICAL ERROR in Optimize Block: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}
