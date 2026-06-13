"""
CERTUS STRAT ROBUSTNESS
=======================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- run_final_simulation_block (Phase B robustness screening)
- _IdxWrapper helper
- _test_strategy_robustness_task
- _execute_robustness_tasks
- _prepare_robustness_inputs
- _resolve_robustness_noise_levels
- _prepare_robustness_nominal_optics
- _filter_valid_robustness_strategies
- _finalize_robustness_results
- _calculate_strategy_spectral_resolution
- _build_layer_wavelengths_from_strategy
- _validate_strategy_min_transmission_floor
"""

import logging
import concurrent.futures
import numpy as np
import pandas as pd
from typing import Any

from certus_physics import (
    NON_MONOTONIC_MODE_ATTENUATE,
    arange_inclusive,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    compute_batch_rmse,
    precompute_matrix_cache_kernel,
    simulate_stack_robustness_batch,
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    get_safe_worker_count,
)

from certus.core.certus_strat_config import (
    APP_CONTEXT,
    RobustnessContext,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    precompute_clues_and_matrices,
    _emit_stat,
)

from certus.core.certus_strat_objectives import (
    _compute_dT_dd_per_layer,
    _compute_theoretical_layer_profile,
    _compute_strategy_symmetry_score_percent,
)

from certus.utils.certus_strat_context import (
    _validate_strategy_blocks_contract,
    _strategy_signature,
)

from certus.utils.certus_strat_service import (
    compute_probe_offset_nm_from_ratio,
    select_best_strat_result,
    calculate_RT_normal_real,
)

from certus.core.certus_strat_ranking import (
    _filter_valid_robustness_strategies,
    _select_best_strat_result,
)


class _IdxWrapper:
    """Dict-like wrapper supporting both ``dict.get`` and ``list[idx]`` access."""

    __slots__ = ("obj",)

    def __init__(self, obj) -> None:
        self.obj = obj

    def __getitem__(self, k) -> Any:
        return self.obj.get(k) if hasattr(self.obj, "get") else self.obj[k]

    def __contains__(self, k) -> bool:
        if hasattr(self.obj, "__contains__"):
            return k in self.obj
        if hasattr(self.obj, "get"):
            return self.obj.get(k) is not None
        return False


def _parse_noise_factors(raw_factors) -> list[float]:
    if isinstance(raw_factors, str):
        try:
            cleaned = raw_factors.replace("[", "").replace("]", "").strip()
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
        except Exception:
            return [0.5, 1.0, 2.0]
    if isinstance(raw_factors, list):
        return [float(x) for x in raw_factors]
    return [0.5, 1.0, 2.0]


def _resolve_robustness_noise_levels(params: dict[str, Any]) -> list[float]:
    """Resolve robustness noise-level vector from STRAT params."""
    noise_factors = _parse_noise_factors(params.get("robustness_noise_factors", [0.5, 1.0, 2.0]))
    if params.get("thickness_tolerance_nm") is not None:
        base_tol = float(params.get("thickness_tolerance_nm"))
        return [base_tol * f for f in noise_factors]

    try:
        base_noise = float(params["reality_sim_params"]["trigger_tolerance"])
    except (KeyError, TypeError):
        base_noise = float(params.get("trigger_tolerance", 0.5))
    return [base_noise * f for f in noise_factors]


def _prepare_robustness_nominal_optics(
    params: dict[str, Any],
    p_thick_nominal: list[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generates nominal wavelength and index arrays, plus nominal transmission."""
    wl_range_scan = params["wl_range"]
    wl_step = float(params["wl_step"])
    wl_arr = arange_inclusive(wl_range_scan[0], wl_range_scan[1], wl_step)
    local_db = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
    
    # Import config functions dynamically to avoid any circular dependency
    from certus.core.certus_strat_config import get_refractive_clues_vectorized
    nH_arr = get_refractive_clues_vectorized(params["nH_id"], wl_arr, db_instance=local_db)
    nL_arr = get_refractive_clues_vectorized(params["nL_id"], wl_arr, db_instance=local_db)
    nSub_arr = get_refractive_clues_vectorized(params["nSub_id"], wl_arr, db_instance=local_db)
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    _, T_nom = calculate_RT_vectorized_real_HL(wl_arr, nH_arr, nL_arr, nSub_arr, p_thick_nom_arr)
    return wl_arr, nH_arr, nL_arr, nSub_arr, T_nom


# _filter_valid_robustness_strategies has been moved to certus_strat_ranking.py


def _prepare_robustness_inputs(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int,
    noise_levels: list[float] | None,
    logger: logging.Logger,
) -> tuple[list[dict[str, Any]], list[float], list[float], int]:
    """Validates and prepares robustness initial inputs."""
    if not opti_results or "all_strategies" not in opti_results:
        raise ValueError("Invalid optimization results for simulation.")
    if noise_levels is None:
        noise_levels = _resolve_robustness_noise_levels(params)
    if noise_levels:
        total_mc_runs = num_runs * len(noise_levels)
        _emit_stat("MCS", total_mc_runs)
    all_strategies_in = opti_results["all_strategies"]
    p_thick_nominal = opti_results["p_thick_nominal"]
    num_layers = len(p_thick_nominal)
    all_strategies = _filter_valid_robustness_strategies(
        all_strategies_in,
        num_layers=num_layers,
        logger=logger,
    )
    return all_strategies, noise_levels or [], p_thick_nominal, num_layers


def _calculate_strategy_spectral_resolution(strategy, p_thick_nominal, params) -> tuple:
    blocks = strategy["blocks"]
    nH_id, nL_id, nSub_id = params["nH_id"], params["nL_id"], params["nSub_id"]
    db_local = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
    test_bw = 1.0
    half_bw = test_bw / 2.0

    try:
        T_tolerance = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    except (KeyError, ValueError, TypeError):
        T_tolerance = 0.001

    min_resolution = 999.0
    worst_layer = -1
    layer_to_wl = {}

    for block in blocks:
        for l in range(block["start"], block["end"]):
            layer_to_wl[l] = float(block["wavelength"])

    num_layers = len(p_thick_nominal)
    for i_layer in range(num_layers):
        wl_mon = layer_to_wl.get(i_layer, float(params.get("l0", 550.0)))
        current_stack_thick = p_thick_nominal[: i_layer + 1]
        wls_check = [max(0.1, wl_mon - half_bw), wl_mon, wl_mon + half_bw]

        RT = calculate_RT_normal_real(wls_check, nH_id, nL_id, nSub_id, current_stack_thick, db_instance=db_local)
        T_vals = RT[:, 1]

        if len(T_vals) == 3:
            curvature = abs((T_vals[0] + T_vals[2]) / 2.0 - T_vals[1])
            if curvature > 1e-9:
                res_limit = test_bw * np.sqrt(T_tolerance / curvature)
            else:
                res_limit = 100.0

            if res_limit < min_resolution:
                min_resolution = res_limit
                worst_layer = i_layer + 1

    return min_resolution, worst_layer


def _filter_finite_robustness_scores(
    strategies_results: list[dict[str, Any]],
    *,
    logger,
) -> list[dict[str, Any]]:
    """Keep only strategies with finite robustness score."""
    filtered_results: list[dict[str, Any]] = []
    for item in strategies_results:
        score = float(item.get("robustness_score", np.inf))
        if np.isfinite(score):
            filtered_results.append(item)
        else:
            logger.warning(
                f"[ROBUSTNESS] Dropped non-finite score for strategy "
                f"{item.get('strategy', {}).get('strategy_id', '?')}: {score}"
            )
    return filtered_results


def _execute_robustness_tasks(
    all_strategies: list[dict[str, Any]],
    noise_levels: list[float],
    num_runs: int,
    p_thick_nominal: list[float],
    clues_at_wl: dict[str, Any],
    params_safe: dict[str, Any],
    wl_arr: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    T_nom: np.ndarray,
    full_dyn_grid: dict[str, Any],
    params: dict[str, Any],
    logger: logging.Logger,
    n_layers_matrix_precomp: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    max_workers = get_safe_worker_count()
    logger.info(
        f"Running robustness tests on {len(all_strategies)} strategies ({max_workers} thread{'s' if max_workers > 1 else ''})..."
    )

    num_layers = len(p_thick_nominal)
    if n_layers_matrix_precomp is None:
        nH_c128 = nH_arr.astype(np.complex128)
        nL_c128 = nL_arr.astype(np.complex128)
        parity = np.arange(num_layers) % 2 == 0
        n_layers_matrix_precomp = np.where(
            parity[np.newaxis, :],
            nH_c128[:, np.newaxis],
            nL_c128[:, np.newaxis],
        )

    strategies_results = []
    if max_workers <= 1:
        for idx, strat in enumerate(all_strategies):
            try:
                res = _test_strategy_robustness_task(
                    strat,
                    idx,
                    noise_levels,
                    num_runs,
                    p_thick_nominal,
                    clues_at_wl,
                    params_safe,
                    wl_arr,
                    nH_arr,
                    nL_arr,
                    nSub_arr,
                    T_nom,
                    full_dyn_grid,
                    n_layers_matrix_precomp=n_layers_matrix_precomp,
                )
                try:
                    min_res, bad_layer = _calculate_strategy_spectral_resolution(res["strategy"], p_thick_nominal, params)
                except Exception:
                    min_res, bad_layer = 999.0, -1
                res["min_resolution"] = min_res
                res["limiting_layer"] = bad_layer
                strategies_results.append(res)
            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logger.error(f"Strategy simulation failed: {e}", exc_info=True)
    else:
        results_by_idx: list[dict[str, Any] | None] = [None] * len(all_strategies)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, strat in enumerate(all_strategies):
                f = executor.submit(
                    _test_strategy_robustness_task,
                    strat,
                    idx,
                    noise_levels,
                    num_runs,
                    p_thick_nominal,
                    clues_at_wl,
                    params_safe,
                    wl_arr,
                    nH_arr,
                    nL_arr,
                    nSub_arr,
                    T_nom,
                    full_dyn_grid,
                    n_layers_matrix_precomp=n_layers_matrix_precomp,
                )
                futures[f] = idx
            for f in concurrent.futures.as_completed(futures):
                idx = futures[f]
                try:
                    res = f.result()
                    try:
                        min_res, bad_layer = _calculate_strategy_spectral_resolution(
                            res["strategy"], p_thick_nominal, params
                        )
                    except Exception:
                        min_res, bad_layer = 999.0, -1
                    res["min_resolution"] = min_res
                    res["limiting_layer"] = bad_layer
                    results_by_idx[idx] = res
                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    logger.error(f"Strategy simulation failed: {e}", exc_info=True)
        strategies_results = [r for r in results_by_idx if r is not None]

    return _filter_finite_robustness_scores(strategies_results, logger=logger)


def _test_strategy_robustness_task(
    strategy,
    _strat_idx,
    noise_levels,
    num_runs,
    p_thick_nominal,
    clues_at_wl,
    params,
    wl_arr,
    nH_arr,
    nL_arr,
    nSub_arr,
    T_nom,
    full_dyn_grid,
    n_layers_matrix_precomp=None,
) -> dict:
    logger = logging.getLogger("certus_strat")
    strategy = dict(strategy)
    blocks = strategy["blocks"]
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    num_layers = len(p_thick_nominal)
    offset_val = compute_probe_offset_nm_from_ratio(params)
    factor_val = float(params.get("non_monotonic_error_factor", 2.0))
    penalty_factor = float(params.get("wavelength_change_penalty", 1.2))
    penalty_vector = np.ones(num_layers, dtype=np.float64)

    sorted_blocks = sorted(blocks, key=lambda b: b["start"])
    prev_wl = -1.0
    for i, blk in enumerate(sorted_blocks):
        current_wl = float(blk["wavelength"])
        if i > 0 and abs(current_wl - prev_wl) > 1e-3:
            start_layer_idx = blk["start"]
            if start_layer_idx < num_layers:
                penalty_vector[start_layer_idx] = penalty_factor
        prev_wl = current_wl

    results_per_noise = []
    unique_wls = len(set(b["wavelength"] for b in blocks))
    complexity = unique_wls / len(blocks) if blocks else 0

    _, T_clean_batch = calculate_RT_batch_kernel(
        wl_arr,
        nH_arr.astype(np.complex128),
        nL_arr.astype(np.complex128),
        nSub_arr.astype(np.complex128),
        p_thick_nom_arr.reshape(1, -1),
    )
    T_nom_aligned = T_clean_batch[0].astype(np.float64)

    layer_wavelengths = np.zeros(num_layers, dtype=np.float64)
    n_H_vals = np.zeros(num_layers, dtype=np.complex128)
    n_L_vals = np.zeros(num_layers, dtype=np.complex128)
    n_Sub_vals = np.zeros(num_layers, dtype=np.complex128)

    if n_layers_matrix_precomp is not None:
        n_layers_matrix = n_layers_matrix_precomp
    else:
        nH_c128 = nH_arr.astype(np.complex128)
        nL_c128 = nL_arr.astype(np.complex128)
        parity = np.arange(num_layers) % 2 == 0
        n_layers_matrix = np.where(
            parity[np.newaxis, :],
            nH_c128[:, np.newaxis],
            nL_c128[:, np.newaxis],
        )

    idx_dict = _IdxWrapper(clues_at_wl)
    for block in blocks:
        b_wl = float(block["wavelength"])
        idx_data = idx_dict[b_wl]
        b_nH = idx_data["H"]
        b_nL = idx_data["L"]
        b_nSub = idx_data.get("substrate", 1.0)
        for i in range(block["start"], block["end"]):
            layer_wavelengths[i] = b_wl
            n_H_vals[i] = b_nH
            n_L_vals[i] = b_nL
            n_Sub_vals[i] = b_nSub

    is_absolute = params.get("thickness_tolerance_nm") is not None
    dT_dd = None
    if is_absolute:
        dT_dd = _compute_dT_dd_per_layer(layer_wavelengths, n_H_vals, n_L_vals, n_Sub_vals, p_thick_nominal)

    base_seed = int(params.get("robustness_seed", 42)) if params.get("robustness_seed") is not None else 42
    for noise_idx, noise_val in enumerate(noise_levels):
        local_seed = (base_seed + _strat_idx * 100000 + noise_idx) % (2**63)
        rng = np.random.default_rng(local_seed)
        raw_noise = np.clip(rng.normal(0.0, 1.0 / 3.0, (num_runs, num_layers)), -1.0, 1.0).astype(np.float64)

        if is_absolute:
            noise_matrix = dT_dd * raw_noise * noise_val * penalty_vector
        else:
            noise_matrix = raw_noise * (noise_val / 100.0) * penalty_vector

        nm_mode = params.get("non_monotonic_mode", NON_MONOTONIC_MODE_ATTENUATE)
        sim_thick_batch, avg_dyns_batch = simulate_stack_robustness_batch(
            p_thick_nom_arr,
            layer_wavelengths,
            n_H_vals,
            n_L_vals,
            n_Sub_vals,
            noise_matrix,
            offset_val,
            factor_val,
            nm_mode,
        )

        for i_layer in range(num_layers):
            wl_sel = float(layer_wavelengths[i_layer])
            if wl_sel > 0.1:
                theory_dyn = full_dyn_grid.get(i_layer, {}).get(wl_sel, -1.0)
                sim_dyn = avg_dyns_batch[i_layer]
                diff = abs(theory_dyn - sim_dyn)
                if theory_dyn >= 0.0 and diff > 0.02:
                    logger.warning(
                        f"   [DYN-ALERT] Discrepancy L{i_layer + 1} @ {wl_sel:.0f}nm | Phase A (Grid): {theory_dyn * 100:.2f}% | Phase B (Sim): {sim_dyn * 100:.2f}% | DIFF: {diff * 100:.2f}%"
                    )
                else:
                    if theory_dyn >= 0.0:
                        logger.info(
                            f"   [DYN-OK] L{i_layer + 1} @ {wl_sel:.0f}nm | A={theory_dyn * 100:.2f}% | B={sim_dyn * 100:.2f}%"
                        )

        run_thicknesses = sim_thick_batch.tolist()
        run_rmses = compute_batch_rmse(
            sim_thick_batch,
            wl_arr.astype(np.float64),
            np.empty(0),
            np.empty(0),
            nSub_arr.astype(np.complex128),
            T_nom_aligned,
            n_layers_matrix,
        )
        rmse_p95 = float(np.percentile(run_rmses, 95))
        rmse_p99 = float(np.percentile(run_rmses, 99))
        results_per_noise.append(
            {
                "noise_level": noise_val,
                "rmse_mean": float(np.mean(run_rmses)),
                "rmse_std": float(np.std(run_rmses)),
                "rmse_p95": rmse_p95,
                "rmse_p99": rmse_p99,
                "rmse_all": run_rmses.tolist(),
                "thicknesses_all": run_thicknesses,
                "avg_dynamics": avg_dyns_batch.tolist(),
            }
        )

    total_mc_sims = num_runs * len(noise_levels)
    _emit_stat("MCS", total_mc_sims)
    final_score = max(r.get("rmse_p95", r["rmse_mean"] + r["rmse_std"]) for r in results_per_noise)

    extrema_dist_info = []
    theoretical_layer_profile = []
    _M_before_cache = np.zeros((num_layers, 2, 2), dtype=np.complex128)
    _M_before_cache[0] = np.eye(2, dtype=np.complex128)
    _blk_starts = [0]
    for _bi in range(1, num_layers):
        if abs(float(layer_wavelengths[_bi]) - float(layer_wavelengths[_blk_starts[-1]])) > 1e-3:
            _blk_starts.append(_bi)
    for _bidx in range(len(_blk_starts)):
        _bs = _blk_starts[_bidx]
        _be = _blk_starts[_bidx + 1] if _bidx + 1 < len(_blk_starts) else num_layers
        _wlb = float(layer_wavelengths[_bs])
        _ll = _be - 1
        if _wlb > 0.1 and _ll > 0:
            _mc = precompute_matrix_cache_kernel(
                np.array([_wlb], dtype=np.float64),
                np.array([n_H_vals[_bs]], dtype=np.complex128),
                np.array([n_L_vals[_bs]], dtype=np.complex128),
                np.array(p_thick_nominal[:_ll], dtype=np.float64),
                _ll,
            )
            for _ci in range(max(1, _bs), _be):
                if _ci - 1 < _mc.shape[0]:
                    _M_before_cache[_ci] = _mc[_ci - 1, 0, :, :]

    for i_layer in range(num_layers):
        wl_sel = float(layer_wavelengths[i_layer])
        M_before = _M_before_cache[i_layer]
        n_current = n_H_vals[i_layer] if i_layer % 2 == 0 else n_L_vals[i_layer]
        layer_profile = _compute_theoretical_layer_profile(
            wl_sel,
            n_current,
            n_Sub_vals[i_layer],
            float(p_thick_nominal[i_layer]),
            M_before,
        )
        dist_ps = float(layer_profile["dist_prev_start"])
        dist_ns = float(layer_profile["dist_next_start"])
        dist_pe = float(layer_profile["dist_prev_end"])
        dist_ne = float(layer_profile["dist_next_end"])
        extrema_dist_info.append(
            {
                "prev_start": dist_ps,
                "next_start": dist_ns,
                "prev_end": dist_pe,
                "next_end": dist_ne,
            }
        )
        theoretical_layer_profile.append(layer_profile)

    strategy["extrema_distances"] = extrema_dist_info
    strategy["theoretical_layer_profile"] = theoretical_layer_profile
    strategy["symmetry_score_pct"] = _compute_strategy_symmetry_score_percent(
        theoretical_layer_profile,
        float(params.get("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT)),
    )

    return {
        "strategy_id": strategy["strategy_id"],
        "strategy": strategy,
        "results_per_noise": results_per_noise,
        "robustness_score": final_score,
        "symmetry_score_pct": float(strategy.get("symmetry_score_pct", 0.0)),
        "num_unique_wavelengths": unique_wls,
        "complexity_score": complexity,
    }


# _select_best_strat_result has been moved to certus_strat_ranking.py


def _finalize_robustness_results(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Reduce memory usage and format final output for robustness ranking."""
    keep_full_mc_top_k = int(params.get("keep_full_mc_top_k", 30))
    for res in strategies_results[keep_full_mc_top_k:]:
        for r in res.get("results_per_noise", []):
            r["rmse_all"] = []
            r["thicknesses_all"] = []

    best = _select_best_strat_result(strategies_results)
    if best:
        logger.info(
            f"🏆 Best Strategy ID: {best['strategy_id']} ({best['strategy'].get('origin', '?')}) - Score: {float(best.get('robustness_score', best.get('rmse', 0.0))):.5f}"
        )

    return {
        "results_per_noise": (best["results_per_noise"] if best else []),
        "optimal_blocks": (best["strategy"]["blocks"] if best else []),
        "best_strategy": (best["strategy"] if best else None),
        "all_strategies_results": strategies_results,
    }


def _build_layer_wavelengths_from_strategy(strategy: dict[str, Any], num_layers: int, l0: float) -> list[float]:
    """Build layer wavelengths from strategy."""
    blocks = strategy["blocks"]
    layer_wavelengths = [l0] * num_layers
    for block in blocks:
        for i in range(block["start"], block["end"]):
            layer_wavelengths[i] = block["wavelength"]
    return layer_wavelengths


def _validate_strategy_min_transmission_floor(
    strategy: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: Any,
    nominal_matrix_cache: np.ndarray,
    all_wls: np.ndarray,
    min_t_floor: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate strategy minimum transmission floor."""
    num_layers = len(p_thick_nominal)
    layer_wavelengths = _build_layer_wavelengths_from_strategy(strategy, num_layers, float(strategy.get("l0", 550.0)))
    
    tmin_report = []
    tmin_violations = []
    
    idx_dict = _IdxWrapper(clues_at_wl)
    for i in range(num_layers):
        wl = layer_wavelengths[i]
        clue = idx_dict[wl]
        n_current = clue["H"] if i % 2 == 0 else clue["L"]
        n_sub = clue.get("substrate", 1.0)
        
        # Calculate theoretical transmission at nominal thickness
        from certus_physics import compute_T_front_at_layer
        M_before = np.eye(2, dtype=np.complex128) if i == 0 else nominal_matrix_cache[i - 1, 0, :, :]
        
        # We need to map wavelength float to cache index
        wl_idx = np.searchsorted(all_wls, wl)
        if wl_idx < len(all_wls) and abs(all_wls[wl_idx] - wl) < 1e-5:
            # cur_M is computed at layer i
            T_val = compute_T_front_at_layer(
                float(wl),
                complex(n_current),
                complex(n_sub),
                float(p_thick_nominal[i]),
                M_before,
            )
        else:
            T_val = 1.0  # Fallback
            
        tmin_report.append({"layer": i + 1, "wl": wl, "t_min": T_val})
        if T_val < min_t_floor:
            tmin_violations.append({"layer": i + 1, "wl": wl, "t_min": T_val})
            
    return tmin_report, tmin_violations


def run_final_simulation_block(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int = 150,
    noise_levels: list[float] | None = None,
) -> dict[str, Any]:
    """Phase B robustness screening: evaluate every candidate strategy under noise."""
    logger = params["logger"]

    # Defer imports of solvers functions to run-time to completely avoid circular dependencies
    from certus.core.certus_strat_consensus import (
        _unpack_consensus_cfg,
        _init_consensus_runtime_state,
        _should_apply_consensus_ranking,
        _select_consensus_candidates,
        _log_consensus_ranking_enabled,
        _init_consensus_map,
        _consensus_strategy_identity,
        _build_params_consensus,
        _consensus_cache_key,
        _consume_cached_consensus_score,
        _store_and_consume_consensus_score,
        _consensus_score_from_result,
        _log_consensus_seed_failure,
        _should_skip_consensus_registration,
        _register_consensus_score_for_strategy,
        _apply_consensus_scores_to_results,
        _log_consensus_rescore_summary,
        _rank_and_filter_strategies,
        _apply_elite_refinement_if_enabled,
    )

    all_strategies, noise_levels, p_thick_nominal, num_layers = _prepare_robustness_inputs(
        opti_results=opti_results,
        params=params,
        num_runs=num_runs,
        noise_levels=noise_levels,
        logger=logger,
    )

    if not all_strategies:
        logger.warning("[ROBUSTNESS] No valid strategy to evaluate after contract checks.")
        return {
            "results_per_noise": [],
            "optimal_blocks": [],
            "best_strategy": None,
            "all_strategies_results": [],
        }

    clues_at_wl = opti_results.get("clues_at_wl")
    if clues_at_wl is None:
        logger.info("[ROBUSTNESS] 'clues_at_wl' not found in opti_results. Recomputing clues on the fly.")
        clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)

    wls_to_fetch = set()
    if hasattr(clues_at_wl, "wls"):
        wls_to_fetch.update(float(w) for w in clues_at_wl.wls)
    elif hasattr(clues_at_wl, "keys"):
        wls_to_fetch.update(float(w) for w in clues_at_wl.keys())
    for strat in all_strategies:
        for blk in strat.get("blocks", []):
            wls_to_fetch.add(float(blk["wavelength"]))

    idx_dict = _IdxWrapper(clues_at_wl)
    local_clues = {}
    for wl in wls_to_fetch:
        try:
            local_clues[wl] = idx_dict[wl]
        except Exception:
            pass

    class SafeLocalClues:
        def __init__(self, original, cache) -> None:
            self.original = original
            self.cache = cache

        def get(self, wl: float, default=None) -> Any:
            wl_f = float(wl)
            if wl_f in self.cache:
                return self.cache[wl_f]
            try:
                res = _IdxWrapper(self.original)[wl_f]
                self.cache[wl_f] = res
                return res
            except Exception:
                return default

        def keys(self) -> Any:
            return self.cache.keys()

        def __getitem__(self, wl) -> Any:
            res = self.get(wl)
            if res is None:
                raise KeyError(wl)
            return res

        def __contains__(self, wl) -> bool:
            wl_f = float(wl)
            if wl_f in self.cache:
                return True
            return wl_f in _IdxWrapper(self.original)

    clues_at_wl = SafeLocalClues(clues_at_wl, local_clues)
    opti_results = dict(opti_results)
    opti_results["clues_at_wl"] = clues_at_wl

    full_dyn_grid = opti_results.get("full_dynamics_grid", {})

    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params=params,
        p_thick_nominal=p_thick_nominal,
    )

    params_safe = {k: v for k, v in params.items() if k not in ["logger", "materials_db", "gui_parent"]}

    nH_c128 = nH_arr.astype(np.complex128)
    nL_c128 = nL_arr.astype(np.complex128)
    parity = np.arange(num_layers) % 2 == 0
    n_layers_matrix_precomp = np.where(
        parity[np.newaxis, :],
        nH_c128[:, np.newaxis],
        nL_c128[:, np.newaxis],
    )

    strategies_results = _execute_robustness_tasks(
        all_strategies=all_strategies,
        noise_levels=noise_levels,
        num_runs=num_runs,
        p_thick_nominal=p_thick_nominal,
        clues_at_wl=clues_at_wl,
        params_safe=params_safe,
        wl_arr=wl_arr,
        nH_arr=nH_arr,
        nL_arr=nL_arr,
        nSub_arr=nSub_arr,
        T_nom=T_nom,
        full_dyn_grid=full_dyn_grid,
        params=params,
        logger=logger,
        n_layers_matrix_precomp=n_layers_matrix_precomp,
    )

    (
        consensus_enabled,
        consensus_top_k,
        consensus_mode,
        consensus_std_weight,
        consensus_num_runs,
        consensus_seeds,
    ) = _unpack_consensus_cfg(params, num_runs=num_runs)

    noise_signature, robustness_score_cache = _init_consensus_runtime_state(noise_levels)

    def _apply_consensus_ranking_inplace(results_in: list[dict[str, Any]], stage_tag: str) -> None:
        if not _should_apply_consensus_ranking(
            consensus_enabled=consensus_enabled,
            consensus_seeds=consensus_seeds,
            results_in=results_in,
        ):
            return

        top_k_eval, candidates = _select_consensus_candidates(
            results_in,
            consensus_top_k=consensus_top_k,
        )

        _log_consensus_ranking_enabled(
            logger=logger,
            stage_tag=stage_tag,
            top_k_eval=top_k_eval,
            consensus_seeds=consensus_seeds,
            consensus_mode=consensus_mode,
            consensus_num_runs=consensus_num_runs,
        )

        consensus_map = _init_consensus_map()

        _consensus_tasks: list[tuple[int, str, tuple, int, tuple, concurrent.futures.Future]] = []
        _consensus_cached: dict[str, list[float]] = {}

        for local_idx, item in enumerate(candidates):
            strat = item.get("strategy", {})
            sid, strat_sig = _consensus_strategy_identity(strat)
            if sid not in _consensus_cached:
                _consensus_cached[sid] = []
            for seed in consensus_seeds:
                params_consensus = _build_params_consensus(params_safe, seed=seed)
                cache_key = _consensus_cache_key(
                    strat_sig,
                    seed=seed,
                    consensus_num_runs=consensus_num_runs,
                    noise_signature=noise_signature,
                )
                if _consume_cached_consensus_score(
                    robustness_score_cache=robustness_score_cache,
                    cache_key=cache_key,
                    seed_scores=_consensus_cached[sid],
                ):
                    continue
                _consensus_tasks.append((local_idx, sid, strat_sig, seed, cache_key, None))

        if _consensus_tasks:
            _consensus_max_workers = min(len(_consensus_tasks), get_safe_worker_count())
            _task_futures: list[tuple[str, int, tuple, concurrent.futures.Future]] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=_consensus_max_workers) as _cexec:
                for local_idx, sid, strat_sig, seed, cache_key, _ in _consensus_tasks:
                    item = candidates[local_idx]
                    strat = item.get("strategy", {})
                    params_consensus = _build_params_consensus(params_safe, seed=seed)
                    f = _cexec.submit(
                        _test_strategy_robustness_task,
                        strat,
                        local_idx,
                        noise_levels,
                        consensus_num_runs,
                        p_thick_nominal,
                        clues_at_wl,
                        params_consensus,
                        wl_arr,
                        nH_arr,
                        nL_arr,
                        nSub_arr,
                        T_nom,
                        full_dyn_grid,
                        n_layers_matrix_precomp=n_layers_matrix_precomp,
                    )
                    _task_futures.append((sid, seed, cache_key, f))

                for sid, seed, cache_key, f in _task_futures:
                    try:
                        res_consensus = f.result()
                        score_c = _consensus_score_from_result(res_consensus)
                        _store_and_consume_consensus_score(
                            robustness_score_cache=robustness_score_cache,
                            cache_key=cache_key,
                            score_c=score_c,
                            seed_scores=_consensus_cached[sid],
                        )
                    except NUMERICAL_FAULT_EXCEPTIONS as e:
                        _log_consensus_seed_failure(
                            logger=logger,
                            sid=sid,
                            seed=seed,
                            error=e,
                        )

        for local_idx, item in enumerate(candidates):
            strat = item.get("strategy", {})
            sid, strat_sig = _consensus_strategy_identity(strat)
            seed_scores = _consensus_cached.get(sid, [])

            if _should_skip_consensus_registration(seed_scores):
                continue

            _register_consensus_score_for_strategy(
                consensus_map=consensus_map,
                sid=sid,
                seed_scores=seed_scores,
                consensus_mode=consensus_mode,
                consensus_std_weight=consensus_std_weight,
                consensus_seeds=consensus_seeds,
            )

        _apply_consensus_scores_to_results(
            results_in=results_in,
            consensus_map=consensus_map,
            consensus_mode=consensus_mode,
        )

        _log_consensus_rescore_summary(
            logger=logger,
            consensus_map=consensus_map,
            results_in=results_in,
            stage_tag=stage_tag,
        )

    strategies_results = _rank_and_filter_strategies(
        strategies_results=strategies_results,
        stage_tag="pre-elite",
        params=params,
        logger=logger,
        apply_consensus_fn=_apply_consensus_ranking_inplace,
    )

    ctx = RobustnessContext(
        params=params,
        params_safe=params_safe,
        logger=logger,
        noise_levels=noise_levels,
        num_runs=num_runs,
        p_thick_nominal=p_thick_nominal,
        num_layers=num_layers,
        clues_at_wl=clues_at_wl,
        wl_arr=wl_arr,
        nH_arr=nH_arr,
        nL_arr=nL_arr,
        nSub_arr=nSub_arr,
        T_nom=T_nom,
        full_dyn_grid=full_dyn_grid,
        n_layers_matrix_precomp=n_layers_matrix_precomp,
    )

    strategies_results = _apply_elite_refinement_if_enabled(
        strategies_results=strategies_results,
        ctx=ctx,
        apply_consensus_fn=_apply_consensus_ranking_inplace,
    )

    return _finalize_robustness_results(
        strategies_results=strategies_results,
        params=params,
        logger=logger,
    )


def _get_best_noise_results(final_results: dict[str, Any], logger: logging.Logger) -> dict[str, Any] | None:
    """Return the best noise results from final robustness results."""
    results_list = final_results.get("results_per_noise", [])
    if not results_list:
        logger.error("No robustness results available!")
        return None

    target_idx = None
    for i, res in enumerate(results_list):
        if abs(res.get("noise_level", 0.0) - 1.0) < 1e-6:
            target_idx = i
            break

    if target_idx is None:
        best_dist = float("inf")
        best_i = 0
        for i, res in enumerate(results_list):
            dist = abs(res.get("noise_level", 0.0) - 1.0)
            if dist < best_dist:
                best_dist = dist
                best_i = i
        target_idx = best_i

    selected_results = results_list[target_idx]
    if "thicknesses_all" not in selected_results or not selected_results["thicknesses_all"]:
        logger.error("No successful simulations in thicknesses_all for selected noise level!")
        return None

    return selected_results

