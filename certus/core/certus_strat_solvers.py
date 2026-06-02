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

import pyqtgraph as pg


from certus.ui.certus_ui import setup_pyqtgraph_defaults

# Conditional import of Svg for the logo

try:
    from PyQt6.QtSvgWidgets import QSvgWidget

except ImportError:
    QSvgWidget = None

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

# Robust db clues (fixed xlsx)

from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO

from certus.ui.certus_ui import (
    CERTUS_UI_STRINGS,
    CertusBaseApp,
    CertusLogPanel,
    CertusTheme,
    CertusThemeToggle,
    CertusCard,
    CertusStatusPill,
    ExcelTableWidget,
    FlashyCard,
    NumericTableWidgetItem,
    apply_certus_theme,
    attach_excel_clipboard_context_menu,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    copy_plot_to_clipboard_excel,
    create_header_logo_widget,
    create_top_actions_bar,
    get_certus_last_dir,
    get_export_settings,
    init_certus_app,
    open_documentation,
    open_file_explorer,
    plot_dataframe_from_widget,
    set_certus_last_dir,
    set_certus_window_icon,
    create_styled_button,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    safe_ui_action,
)
from certus.utils.certus_export import show_copy_excel_feedback

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
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

# -----------------------------------------------------------------------------

# DYNAMICS METRIC - Single source of truth for candidate ranking

# -----------------------------------------------------------------------------

# Metric: peak-to-peak T(d) over layer growth (T_max - T_min).

# Must match compute_dynamics_kernel and all docstrings referring to "dynamics".

DYNAMICS_METRIC_NAME = "peak_to_peak"

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

# SYM STRATEGY SETTINGS - Local extrema symmetry preference

# -----------------------------------------------------------------------------

SYM_DEFAULT_EXTREMA_WINDOW_OT = 12.0

SYM_DEFAULT_WEIGHT = 0.35

SYM_DEFAULT_SAME_WL_BONUS = 0.15

SYM_DEFAULT_CONTINUITY_WEIGHT = 0.25

SYM_DEFAULT_SCORING_MODE = "post"

SYM_DEFAULT_TIE_EPS_ABS = 1e-6

SYM_DEFAULT_TIE_EPS_REL = 1e-4

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

# PyQtGraph configured via COMMON utility

setup_pyqtgraph_defaults()

# === CACHE SYSTEM FOR PLOTS ===
# PlotCache and ThreadSafeCounter have been extracted to certus_strat_context.
# Imported here for full backward compatibility.
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter  # noqa: E402


import certus.core.certus_strat_config as _config
for _k, _v in _config.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v
import certus.core.certus_strat_objectives as _obj
for _k, _v in _obj.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

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

        For every layer *i* (0 … N-1):

        1. Recompute the TMM matrix cache using the *average* simulated

           thicknesses of previous layers (reality-feedback loop).

        2. ``_select_candidates_phase_a`` - rank wavelengths by |DeltaT|, filter

           extrema and resolution.

        3. ``_validate_candidates_phase_a`` - Monte Carlo noise simulation

           to score each candidate by P95 error.

        4. Propagate the simulated thickness errors to run_states for the

           next layer (cumulative error propagation).

    **Phase B - Block Grouping & Robustness**

        1. ``mine_strategies_for_block_count`` - dynamic-programming

           segmentation into monochromatic blocks (1 … N blocks).

        2. ``run_final_simulation_block`` - full Monte Carlo robustness

           screening of each strategy at multiple noise levels.

    Args:

        params: Full parameter dictionary.

        progress_signal: Optional Qt signal for GUI progress bar.

        plot_signal: Optional Qt signal for live plot updates.

        phase_a_only: If True, skip Phase B and return raw Phase A data.

    Returns:

        Dictionary with best strategy, all strategies results, Phase A data,

        and robustness metrics."""

    logger = params["logger"]

    try:
        l0 = float(params["l0"])

        stack_string = params["stack_string"]

        multipliers = [float(e) for e in stack_string.split(",") if e.strip()]

        # Setup Indices& True Nominal Stack

        p_thick_nominal = params.get("p_thick_nominal")

        if p_thick_nominal is None:
            # Fallback only if missing (should not happen in Step 23)

            nH_at_l0 = get_refractive_index(params["nH_id"], l0)

            nL_at_l0 = get_refractive_index(params["nL_id"], l0)

            p_thick_nominal = [
                (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0)) for i, m in enumerate(multipliers)
            ]

        num_layers = len(p_thick_nominal)

        # Scan Range

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

def _convert_solution_to_strategy(sol, num_layers, n_blocks, origin_tag, s_id) -> dict:

    blocks_info = sol.get("blocks_info", [])

    blocks_struct = []

    for start, end, wl in blocks_info:
        blocks_struct.append(
            {
                "start": start,
                "end": end,
                "wavelength": float(wl),
                "num_layers": end - start,
            }
        )

    base_total_cost = float(sol.get("base_cost", sol["cost"]))

    ranking_cost = float(sol["cost"])

    return {
        "strategy_id": s_id,
        "n_blocks": n_blocks,
        "avg_cost": float(ranking_cost / num_layers),
        "total_cost": ranking_cost,
        "blocks": blocks_struct,
        "origin": origin_tag,
        "avg_rmse_nominal": base_total_cost,
        "origin_details": origin_tag,
        "symmetry_bonus": float(sol.get("symmetry_bonus", 0.0)),
        "same_wl_kept": int(sol.get("same_wl_kept", 0)),
    }

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

def _find_k_best_groupings_dp_sequential(
    cost_map: dict[int, dict[float, float]],
    n_blocks: int,
    num_layers: int,
    top_k: int = 100,
    timeout: float = 120.0,
    start_time: float = None,
    force_monolayer: bool = False,
    nucleation_wl: float = None,
    nucleation_size: int = 0,
    sym_bonus_map: dict[int, dict[float, float]] | None = None,
    layer_importance_map: dict[int, float] | None = None,
    sym_weight: float = 0.0,
    same_wl_bonus: float = 0.0,
    continuity_weight: float = SYM_DEFAULT_CONTINUITY_WEIGHT,
    adaptive_same_wl: bool = True,
    enable_sym_post_ranking: bool = False,
) -> list[dict[str, Any]]:


    from certus_physics import _compute_valid_blocks_kernel, _dp_kernel

    max_W = max((len(v) for v in cost_map.values() if v), default=0)

    layer_wls = np.full((num_layers, max_W), -1.0, dtype=np.float64)

    layer_costs = np.full((num_layers, max_W), np.inf, dtype=np.float64)

    valid_mask = np.zeros((num_layers, max_W), dtype=np.bool_)

    for layer_idx, layer_dict in cost_map.items():
        if layer_idx >= num_layers or not layer_dict:
            continue

        wls = sorted(layer_dict.keys())

        for w_idx, w in enumerate(wls):
            layer_wls[layer_idx, w_idx] = float(w)

            layer_costs[layer_idx, w_idx] = float(layer_dict[w])

            valid_mask[layer_idx, w_idx] = True

    block_costs, block_wls, block_counts = _compute_valid_blocks_kernel(
        layer_wls, layer_costs, valid_mask, num_layers, top_k, max_W
    )

    if nucleation_wl and nucleation_size > 0 and num_layers >= nucleation_size:
        # We enforce the nucleation wavelength for the first block (start = 0).

        # To avoid over-constraining the DP (which might need more blocks than available if we force a size of 10),

        # we allow the DP to pick ANY initial block size from 1 to nucleation_size,

        # as long as it uses the nucleation wavelength.

        for j in range(1, num_layers + 1):
            if block_counts[0, j] > 0:
                filtered_c = 0

                for b in range(block_counts[0, j]):
                    # If the block size is within the requested nucleation phase, force the WL

                    if j <= nucleation_size:
                        if abs(block_wls[0, j, b] - nucleation_wl) <= 1.0:
                            block_costs[0, j, filtered_c] = block_costs[0, j, b]

                            block_wls[0, j, filtered_c] = block_wls[0, j, b]

                            filtered_c += 1

                    else:
                        # For initial blocks larger than nucleation\_size, they are technically allowed

                        # but we still want them to start with the nucleation\_wl if they encompass it.

                        if abs(block_wls[0, j, b] - nucleation_wl) <= 1.0:
                            block_costs[0, j, filtered_c] = block_costs[0, j, b]

                            block_wls[0, j, filtered_c] = block_wls[0, j, b]

                            filtered_c += 1

                block_counts[0, j] = filtered_c

    if force_monolayer and block_counts[0, 1] > 0:
        block_counts[0, 1] = 0

        smart_nucl_active = nucleation_wl is not None

        if num_layers >= 2 and not smart_nucl_active and block_counts[0, 2] == 0:
            l2_mask = valid_mask[1]

            l1_mask = valid_mask[0]

            l1_costs = layer_costs[0][l1_mask]

            dynamic_penalty = np.mean(l1_costs) * 2.0 if len(l1_costs) > 0 else 1.0

            l2_valid_idx = np.where(l2_mask)[0]

            if len(l2_valid_idx) > 0:
                l2_costs = layer_costs[1][l2_valid_idx]

                best_clues = np.argsort(l2_costs)[:10]

                cpt = 0

                for idx in best_clues:
                    wl = layer_wls[1, l2_valid_idx[idx]]

                    cost_l2 = l2_costs[idx]

                    block_costs[0, 2, cpt] = cost_l2 + dynamic_penalty

                    block_wls[0, 2, cpt] = wl

                    cpt += 1

                block_counts[0, 2] = cpt

                sort_idx = np.argsort(block_costs[0, 2, :cpt])

                block_costs[0, 2, :cpt] = block_costs[0, 2, :cpt][sort_idx]

                block_wls[0, 2, :cpt] = block_wls[0, 2, :cpt][sort_idx]

    dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts = _dp_kernel(
        block_costs, block_wls, block_counts, n_blocks, num_layers, top_k
    )

    final_count = dp_counts[n_blocks, num_layers]

    if final_count == 0:
        return []

    solutions = []

    for t in range(final_count):
        total_cost = dp_costs[n_blocks, num_layers, t]

        blocks_info = []

        for b in range(n_blocks):
            st = dp_paths_start[n_blocks, num_layers, t, b]

            en = dp_paths_end[n_blocks, num_layers, t, b]

            wl = dp_paths_wl[n_blocks, num_layers, t, b]

            if st != -1:
                blocks_info.append((int(st), int(en), float(wl)))

        assignments = {}

        for start, end, wl in blocks_info:
            for l in range(start, end):
                assignments[l] = wl

        solutions.append(
            {
                "cost": float(total_cost),
                "base_cost": float(total_cost),
                "assignments": assignments,
                "blocks_info": blocks_info,
            }
        )

    if enable_sym_post_ranking and (sym_bonus_map or same_wl_bonus > 0.0):
        for sol in solutions:
            aug_cost, sym_bonus_val, same_wl_kept = _augment_solution_cost_with_sym(
                sol,
                sym_bonus_map,
                layer_importance_map,
                sym_weight,
                same_wl_bonus,
                continuity_weight,
                adaptive_same_wl,
            )

            sol["cost"] = float(aug_cost)

            sol["symmetry_bonus"] = float(sym_bonus_val)

            sol["same_wl_kept"] = int(same_wl_kept)

    solutions.sort(key=lambda x: float(x["cost"]))

    return solutions

def mine_strategies_for_block_count(
    n_blocks: int,
    raw_results_thickness: dict[int, list[dict[str, float]]],
    raw_results_sq: dict[int, list[dict[str, float]]],
    num_layers: int,
    top_k: int = 10,
    force_monolayer: bool = False,
    nucleation_wl: float = None,
    nucleation_size: int = 0,
    candidate_limit: int = 3000,
    sym_enable: bool = True,
    sym_bonus_map: dict[int, dict[float, float]] | None = None,
    layer_importance_map: dict[int, float] | None = None,
    sym_weight: float = SYM_DEFAULT_WEIGHT,
    sym_same_wl_bonus: float = SYM_DEFAULT_SAME_WL_BONUS,
    sym_continuity_weight: float = SYM_DEFAULT_CONTINUITY_WEIGHT,
    sym_adaptive_same_wl: bool = True,
    sym_scoring_mode: str = SYM_DEFAULT_SCORING_MODE,
    sym_allow_hybrid: bool = False,
) -> list[dict[str, Any]]:
    """Phase B core: partition layers into *n_blocks* monochromatic blocks.

    Uses sequential dynamic programming to minimize the total squared cost

    of assigning a single monitoring wavelength to each contiguous block of

    layers.  The DP recurrence is:

        DP[k][i] = min_{j<i} ( DP[k-1][j] + BlockCost(j, i) )

    where BlockCost(j, i) is the sum of squared per-layer costs when all

    layers j…i are monitored at the wavelength with the lowest mean cost

    in that range.

    The function explores multiple block partitions and returns up to

    *top_k* strategies ranked by total cost.

    Args:

        n_blocks: Number of monochromatic blocks.

        raw_results_thickness: Phase A per-layer RMSE results.

        raw_results_sq: Normalized squared costs.

        num_layers: Total number of layers.

        top_k: Maximum strategies to return.

        force_monolayer: If True, force single-layer blocks.

        nucleation_wl: Locked nucleation wavelength (optional).

        nucleation_size: Number of locked nucleation layers.

        candidate_limit: Max DP states to explore.

        mse_tolerance_pct: Tolerance for pruning suboptimal branches.

    Returns:

        List of strategy dicts with ``strategy_id``, ``blocks``, ``total_cost``."""

    if n_blocks <= 0 or num_layers <= 0:
        return []

    strategies_collected = []

    strategy_id_base = n_blocks * 1000

    LIMIT_CANDIDATES = candidate_limit

    def apply_nucleation_constraint(cost_map_in) -> Any:

        if not nucleation_wl or nucleation_size <= 0:
            return cost_map_in

        n_wl = float(nucleation_wl)

        for i in range(nucleation_size):
            if i in cost_map_in and cost_map_in[i]:
                if n_wl in cost_map_in[i]:
                    val = cost_map_in[i][n_wl]

                else:
                    available_wls = list(cost_map_in[i].keys())

                    if available_wls:
                        closest_wl = min(available_wls, key=lambda x: abs(x - n_wl))

                        val = cost_map_in[i][closest_wl]

                    else:
                        val = 1.0

                cost_map_in[i] = {n_wl: val}

            else:
                cost_map_in[i] = {n_wl: 1.0}

        return cost_map_in

    cost_map_thick = {}

    def _prune_candidates(cands: list[dict[str, float]], limit: int) -> list[dict[str, float]]:

        if not cands:
            return []

        # No aggressive filtering: returning all valid candidates sorted by cost up to limit

        # This fixes "No strategies found" by ensuring DP has enough overlapping wavelengths.

        return sorted(cands, key=lambda x: x["cost"])[:limit]

    for i in range(num_layers):
        candidates = raw_results_thickness.get(i, [])

        if not candidates:
            continue

        candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)

        cost_map_thick[i] = {c["wl"]: c["cost"] for c in candidates_sorted}

    cost_map_sq = {}

    for i in range(num_layers):
        candidates = raw_results_sq.get(i, [])

        if not candidates:
            continue

        candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)

        cost_map_sq[i] = {c["wl"]: c["cost"] for c in candidates_sorted}

    if nucleation_wl:
        cost_map_thick = apply_nucleation_constraint(cost_map_thick)

        cost_map_sq = apply_nucleation_constraint(cost_map_sq)

    scoring_mode = str(sym_scoring_mode or SYM_DEFAULT_SCORING_MODE).strip().lower()

    if scoring_mode not in {"pre", "post", "hybrid"}:
        scoring_mode = SYM_DEFAULT_SCORING_MODE

    if scoring_mode == "hybrid" and not bool(sym_allow_hybrid):
        scoring_mode = "post"

    pre_sym_enabled = scoring_mode in {"pre", "hybrid"}

    post_sym_enabled = scoring_mode in {"post", "hybrid"}

    cost_map_sym = {}

    if sym_enable:
        for i in range(num_layers):
            candidates = raw_results_thickness.get(i, [])

            if not candidates:
                continue

            candidates_sorted = _prune_candidates(candidates, LIMIT_CANDIDATES)

            layer_map: dict[float, float] = {}

            for c in candidates_sorted:
                wl = float(c["wl"])

                base_cost = float(c["cost"])

                sym_gain = 0.0

                if sym_bonus_map is not None:
                    sym_gain = float(sym_bonus_map.get(i, {}).get(wl, 0.0))

                if pre_sym_enabled:
                    layer_map[wl] = max(0.0, base_cost - float(sym_weight) * sym_gain)

                else:
                    layer_map[wl] = base_cost

            if layer_map:
                cost_map_sym[i] = layer_map

        if nucleation_wl:
            cost_map_sym = apply_nucleation_constraint(cost_map_sym)

    logging.getLogger("ThinFilm").info(
        f"Mining: n_blocks={n_blocks}, CostMapThick Size={len(cost_map_thick)}, CostMapSq Size={len(cost_map_sq)}"
    )

    def run_mining(cost_map, origin_name, offset_id, apply_sym_post=False) -> Any:

        logger = logging.getLogger("ThinFilm")

        logger.info(f"[DEBUG MINING] {origin_name}: Starting DP with {len(cost_map)} layers, n_blocks={n_blocks}")

        # Debug: Show sample of cost_map

        for layer_idx in list(cost_map.keys())[:3]:
            wls_sample = list(cost_map[layer_idx].keys())[:5]

            logger.info(
                f"[DEBUG MINING] Layer {layer_idx}: {len(cost_map[layer_idx])} wavelengths, sample: {wls_sample}"
            )

        solutions = _find_k_best_groupings_dp_sequential(
            cost_map,
            n_blocks,
            num_layers,
            top_k=top_k,
            timeout=30.0,
            force_monolayer=force_monolayer,
            nucleation_wl=nucleation_wl,
            nucleation_size=nucleation_size,
            sym_bonus_map=sym_bonus_map if (apply_sym_post and post_sym_enabled) else None,
            layer_importance_map=layer_importance_map if (apply_sym_post and post_sym_enabled) else None,
            sym_weight=float(sym_weight) if (apply_sym_post and post_sym_enabled) else 0.0,
            same_wl_bonus=float(sym_same_wl_bonus) if (apply_sym_post and post_sym_enabled) else 0.0,
            continuity_weight=float(sym_continuity_weight) if apply_sym_post else SYM_DEFAULT_CONTINUITY_WEIGHT,
            adaptive_same_wl=bool(sym_adaptive_same_wl) if apply_sym_post else False,
            enable_sym_post_ranking=bool(apply_sym_post and post_sym_enabled),
        )

        logger.info(f"[DEBUG MINING] {origin_name}: DP returned {len(solutions)} solutions")

        found = []

        if solutions:
            for rank, sol in enumerate(solutions):
                s_id = strategy_id_base + offset_id + rank

                strat = _convert_solution_to_strategy(sol, num_layers, n_blocks, origin_name, s_id)

                is_valid, reason = _validate_strategy_blocks_contract(strat, num_layers, expected_n_blocks=n_blocks)

                if not is_valid:
                    logger.warning(f"[DEBUG MINING] Dropped invalid strategy {s_id} ({origin_name}): {reason}")

                    continue

                strat["rank_in_group"] = rank + 1

                smart_tag = f" (Smart Nucl. L1-L{nucleation_size})" if nucleation_wl else ""

                strat["origin_details"] = f"{origin_name}{smart_tag} (Rank {rank + 1})"

                found.append(strat)

        return found

    max_workers = 3 if sym_enable else 2

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as miner_executor:
        f1 = miner_executor.submit(run_mining, cost_map_thick, "THICKNESS", 0, False)

        f2 = miner_executor.submit(run_mining, cost_map_sq, "THICKNESS²", 100, False)

        strategies_collected.extend(f1.result())

        strategies_collected.extend(f2.result())

        if sym_enable and cost_map_sym:
            f3 = miner_executor.submit(run_mining, cost_map_sym, "SYM", 200, True)

            strategies_collected.extend(f3.result())

    return strategies_collected

def _get_best_noise_results(final_results: dict[str, Any], logger: logging.Logger) -> dict[str, Any] | None:

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

        # calculate_RT_normal_real returns 2D array (n_wls, 2) with R col 0, T col 1

        RT = calculate_RT_normal_real(wls_check, nH_id, nL_id, nSub_id, current_stack_thick, db_instance=db_local)

        T_vals = RT[:, 1]

        if len(T_vals) == 3:
            curvature = abs((T_vals[0] + T_vals[2]) / 2.0 - T_vals[1])

            # Adjusted tolerance for calculation?

            # If we have absolute tolerance, we might want to check it differently?

            # Keeping T_tolerance (trigger tolerance) for now as it relates to T change, not thickness.

            if curvature > 1e-9:
                res_limit = test_bw * np.sqrt(T_tolerance / curvature)

            else:
                res_limit = 100.0

            if res_limit < min_resolution:
                min_resolution = res_limit

                worst_layer = i_layer + 1

    return min_resolution, worst_layer

def _build_layer_wavelengths_from_strategy(strategy: dict[str, Any], num_layers: int, l0: float) -> list[float]:
    """Expand block strategy into one monitoring wavelength per layer."""

    layer_wls = [float(l0)] * num_layers

    for block in strategy.get("blocks", []):
        start = max(0, int(block.get("start", 0)))

        end = min(num_layers, int(block.get("end", start)))

        wl = float(block.get("wavelength", l0))

        for i in range(start, end):
            layer_wls[i] = wl

    return layer_wls

def _validate_strategy_min_transmission_floor(
    strategy: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: dict[float, dict[str, complex]],
    nominal_matrix_cache: np.ndarray,
    all_wls: np.ndarray,
    min_t_floor: float,
) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    """

    Post-check the selected strategy against a strict per-layer T_min floor.

    Returns:

        (report, violations), where each row has layer, wl, t_min, dynamics.

    """

    num_layers = len(p_thick_nominal)

    l0 = float(strategy.get("l0", 550.0))

    layer_wls = _build_layer_wavelengths_from_strategy(strategy, num_layers, l0)

    report: list[dict[str, float]] = []

    violations: list[dict[str, float]] = []

    # P2-S3 NOTE: Each layer needs a unique (i_layer, nominal_thickness) pair for
    # prepare_dynamics_data_kernel, so this loop cannot be batched into a single call.
    # Total overhead: ~1µs Python × N layers ≈ 50µs (negligible vs Numba kernel cost).
    for i_layer in range(num_layers):
        wl = float(layer_wls[i_layer])

        dyn_out = calculate_dynamics_ULTIMATE(
            np.array([wl], dtype=np.float64),
            i_layer,
            float(p_thick_nominal[i_layer]),
            clues_at_wl,
            nominal_matrix_cache,
            all_wls,
        )

        d = dyn_out[0] if dyn_out else {}

        t_min = float(d.get("t_min", min(d.get("t_init", 0.0), d.get("t_final", 0.0))))

        row = {
            "layer": float(i_layer + 1),
            "wl": wl,
            "t_min": t_min,
            "dynamics": float(d.get("dynamics", 0.0)),
        }

        report.append(row)

        if t_min < min_t_floor:
            violations.append(row)

    return report, violations

def _apply_strategy_ranking(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    origin_priority_map: dict[str, int],
) -> list[dict[str, Any]]:
    """Rank and sort strategies based on robustness, resolution, and origin priority."""

    def _advanced_key(item: dict[str, Any]) -> tuple:
        strategy = item.get("strategy", {})
        origin = str(strategy.get("origin", "UNKNOWN"))
        same_wl_kept = int(strategy.get("same_wl_kept", 0))
        try:
            n_blocks_val = int(strategy.get("n_blocks", len(strategy.get("blocks", []))))
        except (TypeError, ValueError):
            n_blocks_val = len(strategy.get("blocks", []))
        min_res = float(item.get("min_resolution", 999.0))
        return (
            float(item.get("robustness_score", np.inf)),
            min_res,
            -same_wl_kept,
            n_blocks_val,
            _origin_priority_from_map(origin, origin_priority_map),
            _strategy_id_sort_token(strategy.get("strategy_id", "")),
        )

    strategies_results.sort(key=_advanced_key)

    sym_prefer_on_tie = bool(params.get("sym_prefer_on_tie", True))
    sym_tie_epsilon = max(float(params.get("sym_tie_epsilon", SYM_DEFAULT_TIE_EPS_ABS)), 1e-12)
    sym_tie_epsilon_rel = max(float(params.get("sym_tie_epsilon_rel", SYM_DEFAULT_TIE_EPS_REL)), 0.0)

    def _is_tie(s_a: float, s_b: float) -> bool:
        tol = sym_tie_epsilon + sym_tie_epsilon_rel * max(abs(s_a), abs(s_b))
        return abs(s_a - s_b) <= tol

    if sym_prefer_on_tie and len(strategies_results) > 1:
        reordered = []
        i = 0
        while i < len(strategies_results):
            base_score = float(strategies_results[i]["robustness_score"])
            j = i + 1
            while j < len(strategies_results):
                current_score = float(strategies_results[j]["robustness_score"])
                if _is_tie(base_score, current_score):
                    j += 1
                else:
                    break
            tie_group = strategies_results[i:j]
            tie_group.sort(
                key=lambda item: (
                    0 if "SYM" in str(item.get("strategy", {}).get("origin", "")).upper() else 1,
                    *_advanced_key(item),
                )
            )
            reordered.extend(tie_group)
            i = j
        return reordered

    return strategies_results

def _resolve_robustness_noise_levels(params: dict[str, Any]) -> list[float]:
    """Resolve robustness noise-level vector from STRAT params."""
    noise_factors = params.get("robustness_noise_factors", [0.5, 1.0, 2.0])
    if params.get("thickness_tolerance_nm") is not None:
        base_tol = float(params.get("thickness_tolerance_nm"))
        return [base_tol * f for f in noise_factors]

    try:
        base_noise = float(params["reality_sim_params"]["trigger_tolerance"])
    except (KeyError, TypeError):
        base_noise = float(params.get("trigger_tolerance", 0.5))
    return [base_noise * f for f in noise_factors]

def _filter_valid_robustness_strategies(
    all_strategies_in: list[dict[str, Any]],
    *,
    num_layers: int,
    logger,
) -> list[dict[str, Any]]:
    """Keep only strategies that satisfy block-contract validation."""
    filtered: list[dict[str, Any]] = []
    for strat in all_strategies_in:
        try:
            expected_blocks = int(strat.get("n_blocks", len(strat.get("blocks", []))))
        except (TypeError, ValueError):
            expected_blocks = len(strat.get("blocks", []))
        ok, reason = _validate_strategy_blocks_contract(
            strat,
            num_layers,
            expected_n_blocks=expected_blocks,
        )
        if ok:
            filtered.append(strat)
        else:
            logger.warning(f"[ROBUSTNESS] Dropped invalid strategy {strat.get('strategy_id', '?')}: {reason}")
    return filtered

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

    if isinstance(raw_seed_list, list):
        for x in raw_seed_list:
            try:
                seeds.append(int(x))
            except (TypeError, ValueError):
                continue
    elif isinstance(raw_seed_list, str) and raw_seed_list.strip():
        for token in raw_seed_list.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                seeds.append(int(token))
            except (TypeError, ValueError):
                continue

    if seeds:
        seeds = _dedupe_preserve_order_int(seeds)[: max(1, consensus_num_seeds)]

    if not seeds:
        seeds = _default_consensus_seeds(
            base_seed=base_seed,
            consensus_seed_stride=consensus_seed_stride,
            consensus_num_seeds=consensus_num_seeds,
        )
    return seeds

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

def _resolve_family_diversity_cfg(params: dict[str, Any]) -> tuple[bool, int, int]:
    """Resolve family-diversity feature flags and limits."""
    enable_family_diversity = bool(params.get("enable_family_diversity", True))
    diversity_top_k = int(params.get("diversity_top_k", 12))
    diversity_max_per_family = int(params.get("diversity_max_per_family", 4))
    return enable_family_diversity, diversity_top_k, diversity_max_per_family

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
    noise_levels: list[float] | np.ndarray[Any, np.dtype[np.float64]],
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

def _resolve_available_wavelengths(
    clues_at_wl: Any,
    wl_arr: np.ndarray[Any, np.dtype[np.float64]],
) -> list[float]:
    """Resolve candidate wavelengths from clues map, with wl-array fallback."""
    available_wls: list[float] = []
    if hasattr(clues_at_wl, "keys"):
        for key in clues_at_wl.keys():
            try:
                available_wls.append(float(key))
            except (TypeError, ValueError):
                continue
    if not available_wls:
        return [float(w) for w in wl_arr.tolist()]
    return available_wls

def _max_strategy_id(strategies_results: list[dict[str, Any]]) -> int:
    """Return maximum integer strategy id found in result rows."""
    max_sid = 0
    for item in strategies_results:
        try:
            max_sid = max(max_sid, int(item.get("strategy", {}).get("strategy_id", 0)))
        except (TypeError, ValueError):
            continue
    return max_sid

def _existing_block_signatures(strategies_results: list[dict[str, Any]]) -> set[tuple]:
    """Build signature set for already present strategies."""
    return {_blocks_signature(item.get("strategy", {}).get("blocks", [])) for item in strategies_results}

def _elite_parent_count(
    strategies_results: list[dict[str, Any]],
    elite_parent_top_k: int,
) -> int:
    """Return capped parent count used to seed ELITE candidate generation."""
    return min(elite_parent_top_k, len(strategies_results))

def _resolve_elite_nominal_and_target_threshold(
    strategies_results: list[dict[str, Any]],
    *,
    nominal_noise_level: float,
    elite_min_improvement: float,
) -> tuple[float, float] | None:
    """Resolve (rank-10 nominal threshold, target threshold) for ELITE gate."""
    top10_idx = min(9, len(strategies_results) - 1)
    nominal_threshold = _extract_rmse_p95_for_noise(strategies_results[top10_idx], nominal_noise_level)
    if not np.isfinite(nominal_threshold):
        return None
    target_threshold = nominal_threshold - elite_min_improvement
    return float(nominal_threshold), float(target_threshold)

def _top_origin_families(
    strategies_results: list[dict[str, Any]],
    diversity_top_k: int,
) -> list[str]:
    """Return origin-family labels for top-K strategies."""
    return [
        _origin_family(r.get("strategy", {}).get("origin", "UNKNOWN"))
        for r in strategies_results[: min(diversity_top_k, len(strategies_results))]
    ]

def _did_family_top_order_change(before_top: list[str], after_top: list[str]) -> bool:
    """Return True when family ordering changed after diversity pass."""
    return before_top != after_top

def _log_family_diversity_reordering(
    *,
    logger,
    diversity_top_k: int,
    diversity_max_per_family: int,
) -> None:
    """Log family-diversity reorder event with active limits."""
    logger.info(
        "[ROBUSTNESS] Family diversity reordering applied "
        f"(top_k={diversity_top_k}, max_per_family={diversity_max_per_family})."
    )

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

def _prepare_robustness_nominal_optics(
    params: dict[str, Any],
    p_thick_nominal: list[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generates nominal wavelength and index arrays, plus nominal transmission."""
    wl_range_scan = params["wl_range"]
    wl_step = float(params["wl_step"])
    wl_arr = arange_inclusive(wl_range_scan[0], wl_range_scan[1], wl_step)
    local_db = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
    nH_arr = get_refractive_clues_vectorized(params["nH_id"], wl_arr, db_instance=local_db)
    nL_arr = get_refractive_clues_vectorized(params["nL_id"], wl_arr, db_instance=local_db)
    nSub_arr = get_refractive_clues_vectorized(params["nSub_id"], wl_arr, db_instance=local_db)
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    _, T_nom = calculate_RT_vectorized_real_HL(wl_arr, nH_arr, nL_arr, nSub_arr, p_thick_nom_arr)
    return wl_arr, nH_arr, nL_arr, nSub_arr, T_nom

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

    raw_factors = ctx.params.get("robustness_noise_factors", [0.5, 1.0, 2.0])
    nominal_noise_level = _resolve_nominal_noise_level(ctx.noise_levels, raw_factors)
    available_wls = _resolve_available_wavelengths(ctx.clues_at_wl, ctx.wl_arr)
    total_elite_added = 0

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

        quick_pass: list[tuple[float, int, dict[str, Any]]] = []
        for e_idx, elite_strat in enumerate(elite_candidates):
            try:
                quick_res = _test_strategy_robustness_task(
                    elite_strat,
                    e_idx,
                    [nominal_noise_level],
                    elite_num_runs,
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
                quick_nominal = _extract_rmse_p95_for_noise(quick_res, nominal_noise_level)
                if not np.isfinite(quick_nominal) or quick_nominal >= target_threshold:
                    continue
                quick_pass.append((float(quick_nominal), int(e_idx), elite_strat))
            except NUMERICAL_FAULT_EXCEPTIONS as e:
                ctx.logger.warning(f"[ELITE] Round {elite_round}: candidate evaluation failed: {e}")

        if not quick_pass:
            ctx.logger.info(f"[ELITE] Round {elite_round}: no candidate passed quick nominal gate.")
            if elite_stop_on_no_gain:
                break
            continue
        quick_pass.sort(key=lambda x: x[0])
        full_eval_candidates = quick_pass[: min(elite_max_full_evals, len(quick_pass))]
        ctx.logger.info(
            f"[ELITE] Round {elite_round}: quick_pass={len(quick_pass)}, full_eval={len(full_eval_candidates)}."
        )

        elite_added: list[dict[str, Any]] = []
        for _quick_nominal, e_idx, elite_strat in full_eval_candidates:
            try:
                full_res = _test_strategy_robustness_task(
                    elite_strat,
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
                ctx.logger.warning(f"[ELITE] Round {elite_round}: candidate evaluation failed: {e}")

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

def _apply_family_diversity_if_enabled(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Applies family diversity ranking if enabled in params."""
    (
        enable_family_diversity,
        diversity_top_k,
        diversity_max_per_family,
    ) = _resolve_family_diversity_cfg(params)

    if enable_family_diversity and len(strategies_results) > 1:
        before_top = _top_origin_families(strategies_results, diversity_top_k)
        strategies_results = _apply_family_diversity(strategies_results, diversity_top_k, diversity_max_per_family)
        after_top = _top_origin_families(strategies_results, diversity_top_k)
        if _did_family_top_order_change(before_top, after_top):
            _log_family_diversity_reordering(
                logger=logger,
                diversity_top_k=diversity_top_k,
                diversity_max_per_family=diversity_max_per_family,
            )
    return strategies_results

def _select_best_strat_result(strategies_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the best finite-ranked strategy result (compatibility delegate)."""
    return select_best_strat_result(strategies_results)

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

    # Use precomputed n_layers_matrix if available; build on-the-fly otherwise.
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

def run_final_simulation_block(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int = 150,
    noise_levels: list[float] | None = None,
) -> dict[str, Any]:
    """Phase B robustness screening: evaluate every candidate strategy under noise.

    For each strategy, runs ``_test_strategy_robustness_task`` which:

        1. Builds per-layer wavelength/index arrays from the block structure.

        2. Generates bounded Gaussian noise matrices at several levels.

        3. Runs ``simulate_stack_robustness_batch`` - full stack growth with

           cumulative error propagation for *num_runs* achievements.

        4. Computes run RMSE vs. nominal T(lambda) using ``compute_batch_rmse``,

           then scores each level with RMSE P95.

    Strategies are ranked by their worst-case RMSE P95 across tested noise

    levels. The best strategy is returned alongside detailed per-noise-level

    statistics.

    Args:

        opti_results: Phase A output (strategies, clues, cache, etc.).

        params: Parameter dictionary.

        num_runs: Monte Carlo runs per noise level (default 150).

        noise_levels: Explicit noise levels; auto-computed if None.

    Returns:

        Dict with ``results_per_noise``, ``optimal_blocks``, ``best_strategy``,

        ``all_strategies_results``."""

    logger = params["logger"]

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

    clues_at_wl = opti_results["clues_at_wl"]

    # Pre-fetch clues to a local read-only plain dictionary
    # to avoid thread contention / NumPy warnings inside threads.
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

    # Precompute n_layers_matrix once — shared across robustness, consensus, and elite.
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

    # Optional premium consensus ranking:

    # re-score top candidates across multiple seeds to reduce seed sensitivity.

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

        # Parallel consensus: submit all (candidate, seed) tasks concurrently.
        # Numba kernels release the GIL → real parallelism even on Python 3.13.
        _consensus_tasks: list[tuple[int, str, tuple, int, tuple, concurrent.futures.Future]] = []
        _consensus_cached: dict[str, list[float]] = {}  # sid -> cached scores

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
                # No cache hit → submit for parallel evaluation
                _consensus_tasks.append((local_idx, sid, strat_sig, seed, cache_key, None))

        # Execute uncached tasks in parallel
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

        # Register scores for each strategy
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

    # Shallow copy: avoid mutating the caller's strategy dict (race condition
    # when the same strategy is re-evaluated across consensus seeds in parallel).
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

    # Recalculate true nominal transmission with exactly the same kernel as simulated batches

    _, T_clean_batch = calculate_RT_batch_kernel(
        wl_arr,
        nH_arr.astype(np.complex128),
        nL_arr.astype(np.complex128),
        nSub_arr.astype(np.complex128),
        p_thick_nom_arr.reshape(1, -1),
    )

    T_nom_aligned = T_clean_batch[0].astype(np.float64)

    # --- Build per-layer properties once (invariant over noise level) ---



    layer_wavelengths = np.zeros(num_layers, dtype=np.float64)

    n_H_vals = np.zeros(num_layers, dtype=np.complex128)

    n_L_vals = np.zeros(num_layers, dtype=np.complex128)

    n_Sub_vals = np.zeros(num_layers, dtype=np.complex128)

    # n_layers_matrix: use precomputed if available (invariant across strategies).
    # Fallback path: build on-the-fly when called without precomputed matrix
    # (e.g., single-strategy evaluation outside the batch robustness loop).
    if n_layers_matrix_precomp is not None:
        n_layers_matrix = n_layers_matrix_precomp
    else:
        # Vectorized parity fill (same algorithm as _execute_robustness_tasks).
        nH_c128 = nH_arr.astype(np.complex128)
        nL_c128 = nL_arr.astype(np.complex128)
        parity = np.arange(num_layers) % 2 == 0  # True for H layers
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
        # Reproducibility without global RNG side-effects (thread-safe).
        # Modulo 2**63 prevents overflow for large _strat_idx values.

        local_seed = (base_seed + _strat_idx * 100000 + noise_idx) % (2**63)

        rng = np.random.default_rng(local_seed)

        raw_noise = np.clip(rng.normal(0.0, 1.0 / 3.0, (num_runs, num_layers)), -1.0, 1.0).astype(np.float64)

        if is_absolute:
            # Noise domain: thickness (nm). Convert to transmission offset via dT/dd.
            noise_matrix = dT_dd * raw_noise * noise_val * penalty_vector
        else:
            # Noise domain: T fraction. Convert % units to raw fraction (e.g. 0.1% -> 0.001)
            noise_matrix = raw_noise * (noise_val / 100.0) * penalty_vector

        # --- VECTORIZED BATCH SIMULATION ---

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

        # [DYNAMICS VALIDATION] compare Phase B (simulated) vs Phase A (theoretical grid)

        for i_layer in range(num_layers):
            wl_sel = float(layer_wavelengths[i_layer])

            if wl_sel > 0.1:
                theory_dyn = full_dyn_grid.get(i_layer, {}).get(wl_sel, -1.0)

                sim_dyn = avg_dyns_batch[i_layer]

                diff = abs(theory_dyn - sim_dyn)

                # Significant discrepancy check: absolute threshold 0.02 (2%)

                if theory_dyn >= 0.0 and diff > 0.02:
                    logger.warning(
                        f"   [DYN-ALERT] Discrepancy L{i_layer + 1} @ {wl_sel:.0f}nm | Phase A (Grid): {theory_dyn * 100:.2f}% | Phase B (Sim): {sim_dyn * 100:.2f}% | DIFF: {diff * 100:.2f}%"
                    )

                else:
                    if theory_dyn >= 0.0:
                        logger.info(
                            f"   [DYN-OK] L{i_layer + 1} @ {wl_sel:.0f}nm | A={theory_dyn * 100:.2f}% | B={sim_dyn * 100:.2f}%"
                        )

        # Store for result object (convert to list of lists)

        run_thicknesses = sim_thick_batch.tolist()

        # 3. Compute Batch RMSE
        # compute_batch_rmse uses n_layers_matrix directly for per-layer indices;
        # nH_arr / nL_arr positional args are unused legacy placeholders.

        run_rmses = compute_batch_rmse(
            sim_thick_batch,
            wl_arr.astype(np.float64),
            np.empty(0),  # nH_arr: unused, per-layer indices in n_layers_matrix
            np.empty(0),  # nL_arr: unused, per-layer indices in n_layers_matrix
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

    # Coherent worst-case policy across all tested noise levels.

    final_score = max(r.get("rmse_p95", r["rmse_mean"] + r["rmse_std"]) for r in results_per_noise)

    # 4. Compute Extrema Distances for Reporting

    extrema_dist_info = []

    theoretical_layer_profile = []

    # Precompute M_before per wavelength block (C3 fix: avoids O(N²) recomputation).
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