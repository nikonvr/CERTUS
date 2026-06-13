# =============================================================================
# CERTUS STRAT - Core numerical and physics logic
# =============================================================================
import sys
import os
from pathlib import Path
import concurrent.futures

import ctypes

import hashlib

import io

import json

import logging

import queue

import threading

import time

import traceback

from collections import deque

from typing import Any, Dict
from dataclasses import dataclass

import numpy as np

import pandas as pd
from pydantic import ValidationError



from concurrent.futures import ThreadPoolExecutor




# Import access config

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_MAPPING,
    get_export_config,
    get_resource_path,
    get_safe_worker_count,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)

from certus.utils.certus_data import (
    OPENPYXL_AVAILABLE,
    PerformanceMonitor,
    SharedArrayManager,
    SharedArrayWorker,
    SharedIndicesManager,
    SharedIndicesWorker,
    TimingLogger,
    generate_html_report,
    get_missing_manifest_fields,
    numpy_encoder,
    to_csv_robust,
    to_excel_robust,
)

from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    arange_inclusive,
    calculate_detailed_growth,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    calculate_extrema_distances,
    compute_batch_rmse,
    compute_T_front_at_layer,
    find_nucleation_adaptive_kernel,
    get_refractive_index,
    get_refractive_clues_vectorized,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    update_run_states_kernel,
    validate_wavelengths_batch,
    validate_backside_real_clues,
)

# Import context system (replaces global variables)

from certus.utils.certus_strat_context import (
    StratContext,
    get_context,
    SYM_MISSING_DISTANCE,
    FAST_AUTO_BLOCKS_DIVIDER_PRESETS,
    _clamp01,
    _compute_local_extrema_symmetry_score,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_contractual,
    _compute_blocks_range_for_params,
    _validate_strategy_blocks_contract,
    _augment_solution_cost_with_sym,
    _origin_family,
    _parse_origin_priority_map,
    _origin_priority_from_map,
    _apply_family_diversity,
    _blocks_signature,
    _strategy_signature,
    _strategy_id_sort_token,
    _extract_rmse_p95_for_noise,
    _dedupe_preserve_order_int,
    _default_consensus_seeds,
    _resolve_consensus_top_k,
    _resolve_consensus_num_seeds,
    _resolve_consensus_seed_stride,
    _resolve_consensus_num_runs,
)

from certus.core.certus_strat_ranking import (
    _convert_solution_to_strategy,
    _find_k_best_groupings_dp_sequential,
    mine_strategies_for_block_count,
    _apply_strategy_ranking,
    _resolve_available_wavelengths,
    _max_strategy_id,
    _existing_block_signatures,
    _resolve_elite_nominal_and_target_threshold,
    _resolve_family_diversity_cfg,
    _apply_family_diversity_if_enabled,
)

# Robust db clues (fixed xlsx)

from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO


from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.workers.certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import (
    StratStrategyService,
    calculate_nominal_properties,
    calculate_RT_normal_real,
    calculate_dynamics_ULTIMATE,
    _select_candidates_phase_a,
    _validate_candidates_phase_a as _service_validate_candidates_phase_a,
    compute_probe_offset_nm_from_ratio,
    generate_noise_array,
    NOISE_DISTRIBUTION_GAUSSIAN,
    select_best_strat_result,
    extract_best_rmse,
)


_validate_phase_a_bridge_lock = threading.Lock()

def _validate_candidates_phase_a(*args, **kwargs) -> Any:
    """Compatibility bridge for tests monkeypatching STRAT kernel symbols.

    ``certus_strat_service._validate_candidates_phase_a`` resolves kernels from
    its own module globals. This wrapper mirrors legacy behavior by forwarding
    the kernel bindings from ``CERTUS_STRAT`` before dispatch.
    """
    with _validate_phase_a_bridge_lock:
        prev_validate = _strat_service_module.validate_wavelengths_batch
        prev_update = _strat_service_module.update_run_states_kernel
        _strat_service_module.validate_wavelengths_batch = validate_wavelengths_batch
        _strat_service_module.update_run_states_kernel = update_run_states_kernel
        try:
            return _service_validate_candidates_phase_a(*args, **kwargs)
        finally:
            _strat_service_module.validate_wavelengths_batch = prev_validate
            _strat_service_module.update_run_states_kernel = prev_update

# NOTE: SYM_DEFAULT_* constants and DYNAMICS_METRIC_NAME are defined in
# certus_strat_config.py and re-exported here via the _config namespace merge below.

# _IdxWrapper has been moved to certus_strat_robustness.py

# -----------------------------------------------------------------------------

# ROBUST INDEX RETRIEVAL - Uses StratContext for dependency injection

# -----------------------------------------------------------------------------

# Save references to original certus_physics functions

_original_get_refractive_index = get_refractive_index

_original_get_refractive_clues_vectorized = get_refractive_clues_vectorized

def set_robust_material_db(db) -> None:
    """

    Set the material database in the current context.

    Legacy wrapper for backward compatibility.

    Prefer using StratContext directly.

    """

    ctx = get_context()

    ctx.material_db = db

def smart_get_refractive_index(mat_id, wl, db_instance=None) -> Any:
    """Get refractive index using context-based dependency injection with robust fallback."""

    # 1. Explicit DB instance (Legacy)

    if db_instance is not None:
        return _original_get_refractive_index(mat_id, wl, db_instance)

    # 2. Context Strategy

    ctx = StratContext.get_current()

    if ctx is not None and ctx.material_db is not None:
        return ctx.material_db.get_refractive_index(mat_id, wl)

    # 3. Global Fallback (APP_CONTEXT) - Critical for maintaining state if context is empty

    # Check if context has it implicitly or fallback to global

    db_to_use = _resolve_materials_db_fallback(ctx)

    if db_to_use is not None:
        # Special handling for RobustMaterialDatabase if it requires direct call

        if type(db_to_use).__name__ == "RobustMaterialDatabase":
            return db_to_use.get_refractive_index(mat_id, wl)

        return _original_get_refractive_index(mat_id, wl, db_to_use)

    # 4. Final Fallback (No DB)

    return _original_get_refractive_index(mat_id, wl, None)

def smart_get_refractive_clues_vectorized(mat_id, wls, db_instance=None) -> Any:
    """Get vectorized clues using context-based dependency injection with robust fallback."""

    # 1. Explicit DB instance

    if db_instance is not None:
        return _original_get_refractive_clues_vectorized(mat_id, wls, db_instance)

    # 2. Context Strategy

    ctx = StratContext.get_current()

    if ctx is not None and ctx.material_db is not None:
        return ctx.material_db.get_refractive_clues_vectorized(mat_id, wls)

    # 3. Global Fallback

    db_to_use = _resolve_materials_db_fallback(ctx)

    if db_to_use is not None:
        if type(db_to_use).__name__ == "RobustMaterialDatabase":
            return db_to_use.get_refractive_clues_vectorized(mat_id, wls)

        return _original_get_refractive_clues_vectorized(mat_id, wls, db_to_use)

    # 4. Final Fallback

    return _original_get_refractive_clues_vectorized(mat_id, wls, None)

# Alias smart functions to replace imports

get_refractive_index = smart_get_refractive_index

get_refractive_clues_vectorized = smart_get_refractive_clues_vectorized

# Global scientific display configuration

PERF_MONITOR = PerformanceMonitor()

# setup_numba_cache skipped (handled by configure_numba_env + file lock)

# === CACHE SYSTEM FOR PLOTS ===
# PlotCache and ThreadSafeCounter have been extracted to certus_strat_context.
# Imported here for full backward compatibility.
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter  # noqa: E402

from certus.core.certus_strat_objectives import (
    _run_phase_a_hybrid_loop,
    _normalize_phase_a_results,
)
from certus.utils.certus_strat_context import (
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_for_params,
)

# _convert_solution_to_strategy has been moved to certus_strat_ranking.py

# _generate_elite_candidate_strategies has been moved to certus_strat_consensus.py

def _export_phase_a_observability_json(params: dict[str, Any], payload: dict[str, Any]) -> None:
    """Export lightweight observability JSON for audit/tracing."""

    if not bool(params.get("export_observability_json", True)):
        return

    try:
        report_dir = get_resource_path("reports")

        os.makedirs(report_dir, exist_ok=True)

        ts = certus_timestamp_file()

        out_path = str(Path(report_dir) / f"STRAT_observability_{ts}.json")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        logger_local = params.get("logger")

        if logger_local:
            logger_local.info(f"📈 Observability JSON saved: '{out_path}'")

    except NUMERICAL_FAULT_EXCEPTIONS:
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

# _find_k_best_groupings_dp_sequential and mine_strategies_for_block_count have been moved to certus_strat_ranking.py

# _get_best_noise_results has been moved to certus_strat_robustness.py

# _calculate_strategy_spectral_resolution, _build_layer_wavelengths_from_strategy,
# and _validate_strategy_min_transmission_floor have been moved to certus_strat_robustness.py

# _apply_strategy_ranking has been moved to certus_strat_ranking.py

# _parse_noise_factors, _resolve_robustness_noise_levels, and _filter_valid_robustness_strategies have been moved to certus_strat_robustness.py

# Consensus & ELITE refinement functions have been moved to certus_strat_consensus.py

# Robustness simulation and scoring logic has been moved to certus_strat_robustness.py

def generate_excel_report(
    nominal_results: dict[str, Any],
    opti_results: dict[str, Any],
    final_results: dict[str, Any],
    params: dict[str, Any],
) -> io.BytesIO:


    include_secondary_rmse_stats = bool(params.get("include_secondary_rmse_stats", False))

    # Check for xlsxwriter availability

    engine = "xlsxwriter"

    try:
        import xlsxwriter  # check availability only

        _ = xlsxwriter

    except ImportError:
        engine = "openpyxl"

        if params.get("logger"):
            params["logger"].warning(
                "'xlsxwriter' module missing. Falling back to 'openpyxl' (formatting may be limited)."
            )

    with PERF_MONITOR.measure("generate_excel_report"):
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine=engine) as writer:
            params_clean = {k: str(v) for k, v in params.items() if k not in ["logger", "materials_db", "clues_at_wl"]}

            pd.DataFrame.from_dict(params_clean, orient="index", columns=["Value"]).to_excel(
                writer, sheet_name="Parameters"
            )

            best_blocks = final_results.get("optimal_blocks", opti_results.get("blocks", []))

            blocks_df = pd.DataFrame(
                [
                    {
                        "Block": i + 1,
                        "Start Layer": b["start"] + 1,
                        "End Layer": b["end"],
                        "Num Layers": int(b.get("num_layers", int(b.get("end", 0)) - int(b.get("start", 0)))),
                        "Wavelength (nm)": b["wavelength"],
                    }
                    for i, b in enumerate(best_blocks)
                ]
            )

            blocks_df.to_excel(writer, sheet_name="Best Strategy Blocks", index=False)

            if "all_strategies_results" in final_results:
                strategies_summary = []

                for res in final_results["all_strategies_results"]:
                    strat = res["strategy"]

                    actual_changes = strat["n_blocks"] - 1

                    max_requested = strat.get("max_changes_requested", actual_changes)

                    violated = strat.get("constraint_violated", False)

                    nominal_rmse = strat.get("avg_rmse_nominal", None)

                    if nominal_rmse is None:
                        # Fallback: approximate nominal RMSE from 1.0x noise result when available.

                        r_list = res.get("results_per_noise", [])

                        target = None

                        for r in r_list:
                            if abs(float(r.get("noise_level", 0.0)) - 1.0) < 0.1:
                                target = r

                                break

                        if target is None and r_list:
                            target = r_list[0]

                        nominal_rmse = target.get("rmse_mean", np.nan) if target else np.nan

                    strategies_summary.append(
                        {
                            "Rank": len(
                                [
                                    r
                                    for r in final_results["all_strategies_results"]
                                    if r["robustness_score"] < res["robustness_score"]
                                ]
                            )
                            + 1,
                            "Strategy ID": strat["strategy_id"],
                            "Blocks": strat["n_blocks"],
                            "Wavelength Changes": actual_changes,
                            "Max Requested": max_requested,
                            "Constraint Violated": "YES" if violated else "NO",
                            "Nominal RMSE": nominal_rmse,
                            "Robustness Score": res["robustness_score"],
                        }
                    )

                strategies_df = pd.DataFrame(strategies_summary)

                strategies_df = strategies_df.sort_values("Rank")

                strategies_df.to_excel(writer, sheet_name="All Strategies Results", index=False)

            robustness_data = []

            for res in final_results.get("results_per_noise", []):
                row = {
                    "Noise Level (%)": res["noise_level"],
                    "RMSE P95": res.get("rmse_p95", res["rmse_mean"]),
                }

                if include_secondary_rmse_stats:
                    row["RMSE Mean"] = res["rmse_mean"]

                    row["RMSE Std"] = res["rmse_std"]

                robustness_data.append(row)

            if robustness_data:
                pd.DataFrame(robustness_data).to_excel(writer, sheet_name="Robustness Best Strategy", index=False)

        output.seek(0)

        return output