"""
CERTUS STRAT CONSENSUS
======================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- Consensus configurations & seeds resolution
- Consensus scoring & cache logic
- Logging utilities for consensus ranking
- ELITE refinement flow
"""

import logging
import concurrent.futures
import numpy as np
from typing import Any

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, get_safe_worker_count
from certus.core.certus_strat_config import APP_CONTEXT, RobustnessContext

# Import helpers from context and ranking
from certus.core.certus_strat_ranking import (
    _apply_strategy_ranking,
    _apply_family_diversity_if_enabled,
    _resolve_available_wavelengths,
    _max_strategy_id,
    _existing_block_signatures,
    _resolve_elite_nominal_and_target_threshold,
)

from certus.utils.certus_strat_context import (
    _dedupe_preserve_order_int,
    _default_consensus_seeds,
    _resolve_consensus_top_k,
    _resolve_consensus_num_seeds,
    _resolve_consensus_seed_stride,
    _resolve_consensus_num_runs,
    _strategy_id_sort_token,
    _strategy_signature,
    _extract_rmse_p95_for_noise,
    _parse_origin_priority_map,
    _validate_strategy_blocks_contract,
    _blocks_signature,
)

# Dynamic imports from robustness to prevent circular dependencies
def _test_strategy_robustness_task(*args, **kwargs) -> Any:
    from certus.core.certus_strat_robustness import _test_strategy_robustness_task as task_fn
    return task_fn(*args, **kwargs)

def _calculate_strategy_spectral_resolution(*args, **kwargs) -> Any:
    from certus.core.certus_strat_robustness import _calculate_strategy_spectral_resolution as res_fn
    return res_fn(*args, **kwargs)

def _parse_noise_factors(*args, **kwargs) -> Any:
    from certus.core.certus_strat_robustness import _parse_noise_factors as parse_fn
    return parse_fn(*args, **kwargs)


def _resolve_consensus_std_weight(params: dict[str, Any]) -> float:
    """Resolve non-negative std weight for mean+std consensus mode."""
    return max(0.0, float(params.get("consensus_std_weight", 0.35)))

def _resolve_consensus_mode(params: dict[str, Any]) -> str:
    """Resolve consensus score aggregation mode with fallback."""
    mode = str(params.get("consensus_score_mode", "mean_std")).strip().lower()
    if mode not in {"mean", "worst", "mean_std"}:
        mode = "mean_std"
    return mode

def _resolve_robustness_base_seed(params: dict[str, Any]) -> int:
    """Resolve base seed used by robustness/consensus flows."""
    return int(params.get("robustness_seed", 42))

def _resolve_consensus_enabled(params: dict[str, Any]) -> bool:
    """Resolve whether consensus reranking is enabled."""
    return bool(params.get("enable_consensus_ranking", False))

def _build_consensus_ranking_params_dict(
    *,
    consensus_enabled: bool,
    consensus_num_seeds: int,
    consensus_top_k: int,
    consensus_seed_stride: int,
    consensus_mode: str,
    consensus_std_weight: float,
    consensus_num_runs: int,
    base_seed: int,
    consensus_seeds: list[int],
) -> dict[str, Any]:
    """Build normalized consensus-configuration payload."""
    return {
        "enabled": consensus_enabled,
        "num_seeds": consensus_num_seeds,
        "top_k": consensus_top_k,
        "seed_stride": consensus_seed_stride,
        "mode": consensus_mode,
        "std_weight": consensus_std_weight,
        "num_runs": consensus_num_runs,
        "base_seed": base_seed,
        "seeds": consensus_seeds,
    }

def _init_consensus_map() -> dict[str, dict[str, Any]]:
    """Initialize consensus metadata map."""
    return {}

def _resolve_consensus_seeds(
    params: dict[str, Any],
    *,
    consensus_num_seeds: int,
    consensus_seed_stride: int,
    base_seed: int,
) -> list[int]:
    """Resolve ordered unique consensus seeds under configured budget."""
    seeds: list[int] = []
    raw_seed_list = params.get("consensus_seed_list", None)

    raw_list = raw_seed_list if isinstance(raw_seed_list, list) else (
        [x.strip() for x in raw_seed_list.split(",")] if isinstance(raw_seed_list, str) and raw_seed_list.strip() else []
    )
    for token in raw_list:
        if token:
            try:
                seeds.append(int(token))
            except (TypeError, ValueError):
                pass

    if seeds:
        seeds = _dedupe_preserve_order_int(seeds)[: max(1, consensus_num_seeds)]

    if not seeds:
        seeds = _default_consensus_seeds(
            base_seed=base_seed,
            consensus_seed_stride=consensus_seed_stride,
            consensus_num_seeds=consensus_num_seeds,
        )
    return seeds

def _resolve_consensus_ranking_params(
    params: dict[str, Any],
    *,
    num_runs: int,
) -> dict[str, Any]:
    """Resolve normalized consensus-ranking parameters."""
    consensus_enabled = _resolve_consensus_enabled(params)
    consensus_num_seeds = _resolve_consensus_num_seeds(params)
    consensus_top_k = _resolve_consensus_top_k(params)
    consensus_seed_stride = _resolve_consensus_seed_stride(params)
    consensus_mode = _resolve_consensus_mode(params)
    consensus_std_weight = _resolve_consensus_std_weight(params)
    consensus_num_runs = _resolve_consensus_num_runs(params, num_runs=num_runs)
    base_seed = _resolve_robustness_base_seed(params)
    consensus_seeds = _resolve_consensus_seeds(
        params,
        consensus_num_seeds=consensus_num_seeds,
        consensus_seed_stride=consensus_seed_stride,
        base_seed=base_seed,
    )
    return _build_consensus_ranking_params_dict(
        consensus_enabled=consensus_enabled,
        consensus_num_seeds=consensus_num_seeds,
        consensus_top_k=consensus_top_k,
        consensus_seed_stride=consensus_seed_stride,
        consensus_mode=consensus_mode,
        consensus_std_weight=consensus_std_weight,
        consensus_num_runs=consensus_num_runs,
        base_seed=base_seed,
        consensus_seeds=consensus_seeds,
    )

def _init_consensus_runtime_state(
    noise_levels: list[float] | None,
) -> tuple[tuple[float, ...], dict[tuple, float]]:
    """Initialize immutable noise signature and consensus score cache."""
    noise_signature = tuple(round(float(v), 12) for v in (noise_levels or []))
    robustness_score_cache: dict[tuple, float] = {}
    return noise_signature, robustness_score_cache

def _unpack_consensus_cfg(
    params: dict[str, Any],
    *,
    num_runs: int,
) -> tuple[bool, int, str, float, int, list[int]]:
    """Resolve and unpack consensus config tuple for runtime loop."""
    consensus_cfg = _resolve_consensus_ranking_params(params, num_runs=num_runs)
    return (
        bool(consensus_cfg["enabled"]),
        int(consensus_cfg["top_k"]),
        str(consensus_cfg["mode"]),
        float(consensus_cfg["std_weight"]),
        int(consensus_cfg["num_runs"]),
        list(consensus_cfg["seeds"]),
    )

def _resolve_elite_refinement_cfg(
    params: dict[str, Any], *, num_runs: int
) -> tuple[int, int, int, int, int, float, bool, int]:
    """Resolve ELITE refinement parameters with safe bounds."""
    elite_parent_top_k = max(1, int(params.get("elite_parent_top_k", 10)))
    elite_max_candidates = max(1, int(params.get("elite_max_candidates", 120)))
    elite_wl_neighbor_span = max(1, int(params.get("elite_wl_neighbor_span", 1)))
    elite_num_runs = max(10, int(params.get("elite_num_runs", min(num_runs, 80))))
    elite_rounds = max(1, int(params.get("elite_rounds", 2)))
    elite_min_improvement = max(0.0, float(params.get("elite_min_improvement", 0.0)))
    elite_stop_on_no_gain = bool(params.get("elite_stop_on_no_gain", True))
    elite_max_full_evals = max(1, int(params.get("elite_max_full_evals", 36)))
    return (
        elite_parent_top_k,
        elite_max_candidates,
        elite_wl_neighbor_span,
        elite_num_runs,
        elite_rounds,
        elite_min_improvement,
        elite_stop_on_no_gain,
        elite_max_full_evals,
    )

def _resolve_nominal_noise_level(
    noise_levels: list[float] | np.ndarray,
    raw_factors: Any,
) -> float:
    """Resolve nominal-noise level from configured robustness factors."""
    nominal_idx = 0
    parsed_factors: list[float] = []
    if isinstance(raw_factors, (list, tuple)):
        for x in raw_factors:
            try:
                parsed_factors.append(float(x))
            except (TypeError, ValueError):
                continue
    if parsed_factors:
        nominal_idx = int(np.argmin(np.abs(np.array(parsed_factors, dtype=np.float64) - 1.0)))
    if nominal_idx < len(noise_levels):
        return float(noise_levels[nominal_idx])
    return float(noise_levels[min(len(noise_levels) // 2, len(noise_levels) - 1)])

def _elite_parent_count(
    strategies_results: list[dict[str, Any]],
    elite_parent_top_k: int,
) -> int:
    """Return capped parent count used to seed ELITE candidate generation."""
    return min(elite_parent_top_k, len(strategies_results))

def _consensus_prefilter_key(item: dict[str, Any]) -> tuple:
    """Sorting key for pre-consensus candidate selection."""
    strategy = item.get("strategy", {})
    sid_token = _strategy_id_sort_token(strategy.get("strategy_id", ""))
    return (
        float(item.get("robustness_score", np.inf)),
        float(item.get("min_resolution", 999.0)),
        -int(strategy.get("same_wl_kept", 0)),
        sid_token,
    )

def _consensus_aggregate_score(
    *,
    mode: str,
    mean_score: float,
    worst_score: float,
    std_score: float,
    std_weight: float,
) -> float:
    """Aggregate consensus score according to configured mode."""
    if mode == "mean":
        return float(mean_score)
    if mode == "worst":
        return float(worst_score)
    return float(mean_score + std_weight * std_score)

def _build_consensus_score_meta(
    *,
    consensus_score: float,
    mean_score: float,
    std_score: float,
    worst_score: float,
    consensus_seeds: list[int],
    n_samples: int,
) -> dict[str, Any]:
    """Build canonical consensus-score payload for one strategy."""
    return {
        "score": float(consensus_score),
        "mean": float(mean_score),
        "std": float(std_score),
        "worst": float(worst_score),
        "seeds": list(consensus_seeds),
        "n_samples": int(n_samples),
    }

def _register_consensus_score_for_strategy(
    *,
    consensus_map: dict[str, dict[str, Any]],
    sid: str,
    seed_scores: list[float],
    consensus_mode: str,
    consensus_std_weight: float,
    consensus_seeds: list[int],
) -> None:
    """Compute and store consensus score/meta for one strategy id."""
    mean_score, std_score, worst_score = _consensus_seed_score_stats(seed_scores)
    consensus_score = _consensus_aggregate_score(
        mode=consensus_mode,
        mean_score=mean_score,
        worst_score=worst_score,
        std_score=std_score,
        std_weight=consensus_std_weight,
    )
    consensus_map[sid] = _build_consensus_score_meta(
        consensus_score=consensus_score,
        mean_score=mean_score,
        std_score=std_score,
        worst_score=worst_score,
        consensus_seeds=consensus_seeds,
        n_samples=len(seed_scores),
    )

def _apply_consensus_scores_to_results(
    *,
    results_in: list[dict[str, Any]],
    consensus_map: dict[str, dict[str, Any]],
    consensus_mode: str,
) -> None:
    """Write consensus scores/metadata back into strategy result rows."""
    for item in results_in:
        sid = _result_item_strategy_id(item)
        meta = consensus_map.get(sid)
        if not meta:
            continue
        _apply_item_consensus_scores(item, meta)
        item["robustness_consensus_meta"] = _build_item_consensus_meta(
            consensus_mode=consensus_mode,
            meta=meta,
        )

def _apply_item_consensus_scores(item: dict[str, Any], meta: dict[str, Any]) -> None:
    """Apply base/consensus/final robustness score fields on one row."""
    item["robustness_score_base"] = float(item.get("robustness_score", np.inf))
    item["robustness_score_consensus"] = float(meta["score"])
    item["robustness_score"] = float(meta["score"])

def _build_item_consensus_meta(*, consensus_mode: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Build per-item robustness consensus metadata payload."""
    return {
        "mode": consensus_mode,
        "mean": float(meta["mean"]),
        "std": float(meta["std"]),
        "worst": float(meta["worst"]),
        "seeds": meta["seeds"],
        "n_samples": int(meta["n_samples"]),
    }

def _result_item_strategy_id(item: dict[str, Any]) -> str:
    """Extract strategy id token from a strategy-result row."""
    return str(item.get("strategy", {}).get("strategy_id", ""))

def _has_consensus_seed_scores(seed_scores: list[float]) -> bool:
    """Return True when at least one finite seed score was collected."""
    return bool(seed_scores)

def _should_skip_consensus_registration(seed_scores: list[float]) -> bool:
    """Return True when candidate has no consensus scores to register."""
    return not _has_consensus_seed_scores(seed_scores)

def _log_consensus_seed_failure(*, logger, sid: str, seed: int, error: Exception) -> None:
    """Log one consensus seed re-score failure."""
    logger.warning(f"[ROBUSTNESS] Consensus re-score failed for strategy {sid} seed={seed}: {error}")

def _log_consensus_rescore_summary(
    *,
    logger,
    consensus_map: dict[str, dict[str, Any]],
    results_in: list[dict[str, Any]],
    stage_tag: str,
) -> None:
    """Emit compact summary after consensus re-scoring."""
    if consensus_map:
        logger.info(
            f"[ROBUSTNESS] Consensus re-scored strategies: {len(consensus_map)}/{len(results_in)} ({stage_tag})."
        )

def _log_consensus_ranking_enabled(
    *,
    logger,
    stage_tag: str,
    top_k_eval: int,
    consensus_seeds: list[int],
    consensus_mode: str,
    consensus_num_runs: int,
) -> None:
    """Emit consensus-ranking configuration log line."""
    logger.info(
        "[ROBUSTNESS] Consensus ranking enabled "
        f"({stage_tag}, top_k={top_k_eval}, seeds={consensus_seeds}, "
        f"mode={consensus_mode}, runs={consensus_num_runs})"
    )

def _select_consensus_candidates(
    results_in: list[dict[str, Any]],
    *,
    consensus_top_k: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Select top-k candidates for consensus re-scoring."""
    top_k_eval = min(consensus_top_k, len(results_in))
    candidates = sorted(results_in, key=_consensus_prefilter_key)[:top_k_eval]
    return top_k_eval, candidates

def _consensus_cache_key(
    strat_sig: tuple,
    *,
    seed: int,
    consensus_num_runs: int,
    noise_signature: tuple[float, ...],
) -> tuple:
    """Build stable cache key for consensus robustness re-scoring."""
    return (
        strat_sig,
        int(seed),
        int(consensus_num_runs),
        noise_signature,
    )

def _build_params_consensus(params_safe: dict[str, Any], *, seed: int) -> dict[str, Any]:
    """Build per-seed params payload for consensus re-scoring."""
    params_consensus = dict(params_safe)
    params_consensus["robustness_seed"] = int(seed)
    return params_consensus

def _consume_cached_consensus_score(
    *,
    robustness_score_cache: dict[tuple, float],
    cache_key: tuple,
    seed_scores: list[float],
) -> bool:
    """Consume cached consensus score if available; return True on cache hit."""
    if cache_key not in robustness_score_cache:
        return False
    score_c = robustness_score_cache[cache_key]
    if np.isfinite(score_c):
        seed_scores.append(score_c)
    return True

def _store_and_consume_consensus_score(
    *,
    robustness_score_cache: dict[tuple, float],
    cache_key: tuple,
    score_c: float,
    seed_scores: list[float],
) -> None:
    """Store computed consensus score then append it if finite."""
    robustness_score_cache[cache_key] = float(score_c)
    if np.isfinite(score_c):
        seed_scores.append(score_c)

def _should_apply_consensus_ranking(
    *,
    consensus_enabled: bool,
    consensus_seeds: list[int],
    results_in: list[dict[str, Any]],
) -> bool:
    """Return True when consensus reranking should run."""
    return bool(consensus_enabled and len(consensus_seeds) > 1 and results_in)

def _consensus_seed_score_stats(seed_scores: list[float]) -> tuple[float, float, float]:
    """Return (mean, std, worst) for consensus seed scores."""
    return (
        float(np.mean(seed_scores)),
        float(np.std(seed_scores)),
        float(np.max(seed_scores)),
    )

def _consensus_strategy_identity(strat: dict[str, Any]) -> tuple[str, tuple]:
    """Return stable strategy id and signature for consensus loop."""
    sid = str(strat.get("strategy_id", ""))
    strat_sig = _strategy_signature(strat)
    return sid, strat_sig

def _consensus_score_from_result(res_consensus: dict[str, Any]) -> float:
    """Extract consensus robustness score from worker result payload."""
    return float(res_consensus.get("robustness_score", np.inf))

def _rank_and_filter_strategies(
    strategies_results: list[dict[str, Any]],
    stage_tag: str,
    params: dict[str, Any],
    logger: logging.Logger,
    apply_consensus_fn: Any,
) -> list[dict[str, Any]]:
    """Applies consensus, basic ranking, and family diversity in standard order."""
    apply_consensus_fn(strategies_results, stage_tag)
    origin_priority_map = _parse_origin_priority_map(params.get("origin_priority_map", None))
    strategies_results = _apply_strategy_ranking(strategies_results, params, origin_priority_map)
    strategies_results = _apply_family_diversity_if_enabled(
        strategies_results=strategies_results,
        params=params,
        logger=logger,
    )
    return strategies_results

def _apply_elite_refinement_if_enabled(
    strategies_results: list[dict[str, Any]],
    ctx: RobustnessContext,
    apply_consensus_fn: Any,
) -> list[dict[str, Any]]:
    """Runs the ELITE refinement block using the unified RobustnessContext."""
    (
        elite_parent_top_k,
        elite_max_candidates,
        elite_wl_neighbor_span,
        elite_num_runs,
        elite_rounds,
        elite_min_improvement,
        elite_stop_on_no_gain,
        elite_max_full_evals,
    ) = _resolve_elite_refinement_cfg(ctx.params, num_runs=ctx.num_runs)

    if not (strategies_results and ctx.noise_levels):
        return strategies_results

    raw_factors = _parse_noise_factors(ctx.params.get("robustness_noise_factors", [0.5, 1.0, 2.0]))
    nominal_noise_level = _resolve_nominal_noise_level(ctx.noise_levels, raw_factors)
    available_wls = _resolve_available_wavelengths(ctx.clues_at_wl, ctx.wl_arr)
    total_elite_added = 0
    
    executor_cls = concurrent.futures.ThreadPoolExecutor
    worker_count = get_safe_worker_count()

    for elite_round in range(1, elite_rounds + 1):
        parent_count = _elite_parent_count(strategies_results, elite_parent_top_k)
        nominal_target_pair = _resolve_elite_nominal_and_target_threshold(
            strategies_results,
            nominal_noise_level=nominal_noise_level,
            elite_min_improvement=elite_min_improvement,
        )
        if nominal_target_pair is None:
            ctx.logger.info(f"[ELITE] Round {elite_round}: skipped (non-finite nominal threshold).")
            break
        nominal_threshold, target_threshold = nominal_target_pair
        max_sid = _max_strategy_id(strategies_results)
        existing_signatures = _existing_block_signatures(strategies_results)
        elite_candidates, _next_sid = _generate_elite_candidate_strategies(
            parent_results=strategies_results[:parent_count],
            available_wls=available_wls,
            num_layers=ctx.num_layers,
            start_strategy_id=max_sid + 1,
            max_candidates=elite_max_candidates,
            wl_neighbor_span=elite_wl_neighbor_span,
            existing_signatures=existing_signatures,
        )
        ctx.logger.info(
            "[ELITE] Round "
            f"{elite_round}/{elite_rounds}: generated={len(elite_candidates)} "
            f"parents={parent_count} "
            f"rank10_nominal={nominal_threshold:.6f} target={target_threshold:.6f}"
        )

        candidates_to_eval = [(int(e_idx), strat) for e_idx, strat in enumerate(elite_candidates)]
        
        # Adaptive Sampling: Successive Halving
        # We progressively eliminate candidates with increasing budget
        halving_budgets = [
            max(2, elite_num_runs),
            max(2, ctx.num_runs // 2)
        ]
        
        for stage_idx, stage_runs in enumerate(halving_budgets):
            stage_results: list[tuple[float, int, dict[str, Any]]] = []
            with executor_cls(max_workers=worker_count) as executor:
                futures_stage = [
                    executor.submit(
                        _test_strategy_robustness_task,
                        strat,
                        e_idx,
                        [nominal_noise_level],
                        stage_runs,
                        ctx.p_thick_nominal,
                        ctx.clues_at_wl,
                        ctx.params_safe,
                        ctx.wl_arr,
                        ctx.nH_arr,
                        ctx.nL_arr,
                        ctx.nSub_arr,
                        ctx.T_nom,
                        ctx.full_dyn_grid,
                        n_layers_matrix_precomp=ctx.n_layers_matrix_precomp,
                        # Ce halving ne lit que _extract_rmse_p95_for_noise(res, ...)
                        # et reempile `strat`, la strategie D'ENTREE. Le profil
                        # theorique serait integralement jete : on ne le calcule pas.
                        # L'evaluation ELITE complete plus bas le garde, elle en a
                        # besoin via full_res["strategy"].
                        compute_layer_profile=False,
                    )
                    for e_idx, strat in candidates_to_eval
                ]
                for future, (e_idx, strat) in zip(futures_stage, candidates_to_eval):
                    try:
                        res = future.result()
                        nominal_val = _extract_rmse_p95_for_noise(res, nominal_noise_level)
                        if not np.isfinite(nominal_val) or nominal_val >= target_threshold:
                            continue
                        stage_results.append((float(nominal_val), e_idx, strat))
                    except NUMERICAL_FAULT_EXCEPTIONS as e:
                        ctx.logger.warning(f"[ELITE] Round {elite_round}: candidate evaluation failed: {e}")
                        
            if not stage_results:
                break
                
            stage_results.sort(key=lambda x: x[0])
            # Keep top half, but at least enough to fill elite_max_full_evals
            keep_count = max(elite_max_full_evals, len(stage_results) // 2)
            candidates_to_eval = [(e_idx, strat) for _val, e_idx, strat in stage_results[:keep_count]]

        if not candidates_to_eval:
            ctx.logger.info(f"[ELITE] Round {elite_round}: no candidate passed Successive Halving.")
            if elite_stop_on_no_gain:
                break
            continue
            
        full_eval_candidates = candidates_to_eval[: min(elite_max_full_evals, len(candidates_to_eval))]
        ctx.logger.info(
            f"[ELITE] Round {elite_round}: full_eval={len(full_eval_candidates)}."
        )

        elite_added: list[dict[str, Any]] = []
        with executor_cls(max_workers=worker_count) as executor:
            futures_full = [
                executor.submit(
                    _test_strategy_robustness_task,
                    strat,
                    e_idx,
                    ctx.noise_levels,
                    ctx.num_runs,
                    ctx.p_thick_nominal,
                    ctx.clues_at_wl,
                    ctx.params_safe,
                    ctx.wl_arr,
                    ctx.nH_arr,
                    ctx.nL_arr,
                    ctx.nSub_arr,
                    ctx.T_nom,
                    ctx.full_dyn_grid,
                    n_layers_matrix_precomp=ctx.n_layers_matrix_precomp,
                )
                for e_idx, strat in full_eval_candidates
            ]
            for future in futures_full:
                try:
                    full_res = future.result()
                    full_nominal = _extract_rmse_p95_for_noise(full_res, nominal_noise_level)
                    if not np.isfinite(full_nominal) or full_nominal >= target_threshold:
                        continue
                    full_score = float(full_res.get("robustness_score", np.inf))
                    if not np.isfinite(full_score):
                        continue
                    min_res, bad_layer = _calculate_strategy_spectral_resolution(
                        full_res["strategy"], ctx.p_thick_nominal, ctx.params
                    )
                    full_res["min_resolution"] = min_res
                    full_res["limiting_layer"] = bad_layer
                    full_res["elite_round"] = int(elite_round)
                    full_res["elite_nominal_score"] = float(full_nominal)
                    elite_added.append(full_res)
                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    ctx.logger.warning(f"[ELITE] Round {elite_round}: full evaluation failed: {e}")

        if not elite_added:
            ctx.logger.info(f"[ELITE] Round {elite_round}: no candidate beat nominal threshold.")
            if elite_stop_on_no_gain:
                break
            continue

        total_elite_added += len(elite_added)
        ctx.logger.info(f"[ELITE] Round {elite_round}: added {len(elite_added)} strategy(ies) above threshold.")
        strategies_results.extend(elite_added)

        strategies_results = _rank_and_filter_strategies(
            strategies_results=strategies_results,
            stage_tag=f"post-elite-r{elite_round}",
            params=ctx.params,
            logger=ctx.logger,
            apply_consensus_fn=apply_consensus_fn,
        )

    if total_elite_added <= 0:
        ctx.logger.info("[ELITE] No candidate added across all rounds.")

    return strategies_results


def _generate_elite_candidate_strategies(
    parent_results: list[dict[str, Any]],
    available_wls: list[float],
    num_layers: int,
    start_strategy_id: int,
    max_candidates: int = 120,
    wl_neighbor_span: int = 1,
    existing_signatures: set | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Build local-neighborhood variants around top-ranked strategies.
    Preserves contract constraints (same n_blocks, contiguous coverage).
    """
    if not parent_results or not available_wls:
        return [], start_strategy_id

    wl_arr = np.array(sorted(set(float(w) for w in available_wls)), dtype=np.float64)
    if wl_arr.size == 0:
        return [], start_strategy_id

    seen = set(existing_signatures or set())
    out: list[dict[str, Any]] = []
    next_id = int(start_strategy_id)
    span = max(1, int(wl_neighbor_span))
    max_keep = max(1, int(max_candidates))

    def _push_candidate(base_blocks: list[dict[str, Any]], parent_sid: Any) -> None:
        nonlocal next_id
        if len(out) >= max_keep:
            return

        sig = _blocks_signature(base_blocks)
        if not sig or sig in seen:
            return

        n_blocks_local = len(base_blocks)
        same_wl_kept = 0
        for i in range(1, n_blocks_local):
            if abs(float(base_blocks[i]["wavelength"]) - float(base_blocks[i - 1]["wavelength"])) < 1e-12:
                same_wl_kept += 1

        candidate = {
            "strategy_id": int(next_id),
            "n_blocks": int(n_blocks_local),
            "avg_cost": float("inf"),
            "total_cost": float("inf"),
            "blocks": base_blocks,
            "origin": "ELITE",
            "origin_details": f"ELITE(parent={parent_sid})",
            "same_wl_kept": int(same_wl_kept),
            "parent_strategy_id": parent_sid,
        }

        ok, _reason = _validate_strategy_blocks_contract(
            candidate,
            num_layers,
            expected_n_blocks=n_blocks_local,
        )
        if not ok:
            return

        out.append(candidate)
        seen.add(sig)
        next_id += 1

    for parent in parent_results:
        strat = parent.get("strategy", {})
        parent_sid = strat.get("strategy_id", "?")
        base_blocks = [
            {
                "start": int(b["start"]),
                "end": int(b["end"]),
                "wavelength": float(b["wavelength"]),
            }
            for b in strat.get("blocks", [])
        ]

        if not base_blocks:
            continue

        # 1) Wavelength local mutations (neighbor wavelengths around each block lambda)
        for b_idx, blk in enumerate(base_blocks):
            cur_wl = float(blk["wavelength"])
            nearest = int(np.argmin(np.abs(wl_arr - cur_wl)))
            for delta in range(-span, span + 1):
                if delta == 0:
                    continue

                idx_wl = nearest + delta
                if idx_wl < 0 or idx_wl >= wl_arr.size:
                    continue

                new_wl = float(wl_arr[idx_wl])
                if abs(new_wl - cur_wl) < 1e-12:
                    continue

                mutated = [dict(b) for b in base_blocks]
                mutated[b_idx]["wavelength"] = new_wl
                _push_candidate(mutated, parent_sid)
                if len(out) >= max_keep:
                    return out, next_id

        # 2) Boundary local shifts (+/- 1 layer between adjacent blocks)
        for b_idx in range(len(base_blocks) - 1):
            left = base_blocks[b_idx]
            right = base_blocks[b_idx + 1]
            left_len = int(left["end"]) - int(left["start"])
            right_len = int(right["end"]) - int(right["start"])

            # Shift boundary left by 1 (give one layer from left to right)
            if left_len > 1:
                mutated = [dict(b) for b in base_blocks]
                new_boundary = int(mutated[b_idx]["end"]) - 1
                mutated[b_idx]["end"] = new_boundary
                mutated[b_idx + 1]["start"] = new_boundary
                mutated[b_idx]["num_layers"] = mutated[b_idx]["end"] - mutated[b_idx]["start"]
                mutated[b_idx + 1]["num_layers"] = mutated[b_idx + 1]["end"] - mutated[b_idx + 1]["start"]
                _push_candidate(mutated, parent_sid)
                if len(out) >= max_keep:
                    return out, next_id

            # Shift boundary right by 1 (give one layer from right to left)
            if right_len > 1:
                mutated = [dict(b) for b in base_blocks]
                new_boundary = int(mutated[b_idx]["end"]) + 1
                mutated[b_idx]["end"] = new_boundary
                mutated[b_idx + 1]["start"] = new_boundary
                mutated[b_idx]["num_layers"] = mutated[b_idx]["end"] - mutated[b_idx]["start"]
                mutated[b_idx + 1]["num_layers"] = mutated[b_idx + 1]["end"] - mutated[b_idx + 1]["start"]
                _push_candidate(mutated, parent_sid)
                if len(out) >= max_keep:
                    return out, next_id

    return out, next_id

