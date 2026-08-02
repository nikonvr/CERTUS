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
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

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

# Robust db clues (fixed xlsx)

from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO


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

from certus.core.certus_strat_utils import (
    _IdxWrapper,
    APP_CONTEXT,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    DYNAMICS_METRIC_NAME,
    get_refractive_index,
    get_refractive_clues_vectorized,
)

# Global scientific display configuration

PERF_MONITOR = PerformanceMonitor()

# setup_numba_cache skipped (handled by configure_numba_env + file lock)



# === CACHE SYSTEM FOR PLOTS ===
# PlotCache and ThreadSafeCounter have been extracted to certus_strat_context.
# Imported here for full backward compatibility.
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter  # noqa: E402

# APP_CONTEXT est IMPORTE plus haut depuis certus_strat_utils, qui le tient lui-meme de
# certus.utils.certus_strat_service : c'est le contexte applicatif PARTAGE.
#
# Il etait ici REAFFECTE a un dictionnaire vide, ce qui rompait le partage. Or
# certus_strat_consensus, certus_strat_pipeline et certus_strat_robustness importent
# APP_CONTEXT DEPUIS CE MODULE : ils recevaient donc le dictionnaire vide, et le repli
# `APP_CONTEXT.get("materials_db")` (certus_strat_robustness.py:191 et :235), commente
# « Critical for maintaining state if context is empty », renvoyait toujours None.

CACHE_SIZE_MATERIAL_INDEX = 10000

IDENTITY_2x2_COMPLEX = np.eye(2, dtype=np.complex128)

_SPECTRUM_COUNTER = ThreadSafeCounter()

_LOCAL_LOCK = threading.Lock()

_GLOBAL_STATS_QUEUE = None

_GLOBAL_LIVE_QUEUE = None

def _init_stats_queue() -> Any:
    """Initialize stats queue in current context."""

    ctx = get_context()

    ctx.init_queues()

    return ctx.stats_queue

def _worker_init(stats_queue, live_queue=None) -> None:
    """Initialize worker with queues via StratContext."""

    ctx = StratContext(stats_queue=stats_queue, live_queue=live_queue)

    StratContext.set_current(ctx)

def _emit_stat(counter_type: str, increment: int) -> None:
    """Emit stat via context (with SP batching)."""

    ctx = StratContext.get_current()

    if ctx is not None:
        ctx.emit_stat(counter_type, increment)

    # Fallback/Dual-mode for SPECTRUM counter (used by UI directly)

    if counter_type == "spectrum":
        new_val = _SPECTRUM_COUNTER.increment()

        if _SPECTRUM_COUNTER.signal:
            _SPECTRUM_COUNTER.signal.progress_snapshot.emit(build_progress_snapshot(message=f"Processing spectrum {new_val}", display_ratio=max(0.0, min(1.0, float(new_val) / 100.0)), progress_ratio=max(0.0, min(1.0, float(new_val) / 100.0)), eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='STRAT', phase='SPECTRUM'))

def _flush_sp_stats() -> None:
    """Flush buffered SP stats via context."""

    ctx = StratContext.get_current()

    if ctx is not None:
        ctx.flush_stats()

def _prepare_precompute_wavelength_grid(
    params: dict[str, Any], p_thick_nominal: list[float], logger
) -> tuple[np.ndarray, int]:

    l0 = float(params["l0"])

    req_scan_min = float(params["scan_wl_min"])

    req_scan_max = float(params["scan_wl_max"])

    req_scan_step = float(params["scan_wl_step"])

    if req_scan_step < 1.0 and (req_scan_max - req_scan_min) > 200:
        logger.warning(f"⚠️ Auto-adjusting scan step ({req_scan_step} -> 1.0 nm)")

        req_scan_step = 1.0

    num_layers = len(p_thick_nominal)

    estimated_wls = int((req_scan_max - req_scan_min) / req_scan_step) + 1

    estimated_mb = num_layers * estimated_wls * 2 * 4 * 8 / (1024**2)

    max_cache_mb = 150.0 if num_layers >= 60 else (100.0 if num_layers >= 30 else 50.0)

    final_step = req_scan_step

    if estimated_mb > max_cache_mb:
        ratio = estimated_mb / max_cache_mb

        final_step = np.ceil(req_scan_step * ratio * 2) / 2.0

        logger.warning(f"⚠️ Cache limit reached. Scan step adjusted: {req_scan_step:.2f} nm -> {final_step:.2f} nm")

    scan_wl_range = arange_inclusive(req_scan_min, req_scan_max, final_step)

    wl_range_full = arange_inclusive(
        float(params["wl_range"][0]),
        float(params["wl_range"][1]),
        float(params["wl_step"]),
    )

    all_wls = np.sort(np.unique(np.concatenate([scan_wl_range, wl_range_full, np.array([l0], dtype=np.float64)])))

    logger.info(
        f"  Cache allocation: {num_layers * len(all_wls) * 2 * 4 * 8 / (1024**2):.1f} MB ({len(all_wls)} wavelengths)"
    )

    return all_wls, num_layers

def _resolve_clues_at_wavelength(
    params: dict[str, Any], wl: float, db_instance: Any, logger
) -> dict[str, complex | float]:

    try:
        n_h = get_refractive_index(params["nH_id"], wl, db_instance)

        n_l = get_refractive_index(params["nL_id"], wl, db_instance)

        n_sub = get_refractive_index(params["nSub_id"], wl, db_instance)

        return {"H": n_h, "L": n_l, "substrate": n_sub}

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logger.warning(f"⚠️ Failed to get clues at{wl}nm: {e}. Trying nominal l0={params.get('l0', 550.0)}nm.")

    try:
        l0_fallback = float(params.get("l0", 550.0))

        n_h = get_refractive_index(params["nH_id"], l0_fallback, db_instance)

        n_l = get_refractive_index(params["nL_id"], l0_fallback, db_instance)

        n_sub = get_refractive_index(params["nSub_id"], l0_fallback, db_instance)

        return {"H": n_h, "L": n_l, "substrate": n_sub}

    except NUMERICAL_FAULT_EXCEPTIONS as e2:
        n_h_fb = float(params.get("nH_r", 2.1)) if "nH_r" in params else 2.1

        n_l_fb = float(params.get("nL_r", 1.46)) if "nL_r" in params else 1.46

        n_sub_fb = float(params.get("nSub_custom", 1.52)) if "nSub_custom" in params else 1.52

        logger.warning(
            f"⚠️ Also failed at l0 for {wl}nm ({e2}). "
            f"Using numeric fallback H={n_h_fb}, L={n_l_fb}, Sub={n_sub_fb}. "
            f"CHECK that your material DB covers the monitoring wavelengths!"
        )

        return {"H": n_h_fb, "L": n_l_fb, "substrate": n_sub_fb}

def _build_clues_at_wavelengths(
    params: dict[str, Any], all_wls: np.ndarray, logger
) -> dict[float, dict[str, complex | float]]:

    db_instance = params.get("materials_db_instance") or params.get("materials_db")

    # Fast path: 3 vectorized calls instead of N×3 scalar calls.
    try:
        nH_all = get_refractive_clues_vectorized(params["nH_id"], all_wls, db_instance=db_instance)
        nL_all = get_refractive_clues_vectorized(params["nL_id"], all_wls, db_instance=db_instance)
        nSub_all = get_refractive_clues_vectorized(params["nSub_id"], all_wls, db_instance=db_instance)
        return {
            float(all_wls[i]): {"H": nH_all[i], "L": nL_all[i], "substrate": nSub_all[i]} for i in range(len(all_wls))
        }
    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logger.warning(f"Vectorized clue build failed ({e}), falling back to per-wavelength.")

    # Fallback: per-wavelength with error recovery
    clues_at_wl: dict[float, dict[str, complex | float]] = {}
    for wl in all_wls:
        clues_at_wl[float(wl)] = _resolve_clues_at_wavelength(params, float(wl), db_instance, logger)
    return clues_at_wl

def _warn_backside_approximation_if_needed(
    clues_at_wl: dict[float, dict[str, complex | float]], all_wls: np.ndarray, logger
) -> None:

    idx_dict = _IdxWrapper(clues_at_wl)

    backside_warned = False

    for wl in all_wls:
        idx_data = idx_dict[float(wl)]

        n_h_val = idx_data["H"]

        n_l_val = idx_data["L"]

        n_sub_val = idx_data["substrate"]

        k_h = abs(np.imag(n_h_val)) if np.iscomplex(n_h_val) else 0.0

        k_l = abs(np.imag(n_l_val)) if np.iscomplex(n_l_val) else 0.0

        k_sub = abs(np.imag(n_sub_val)) if np.iscomplex(n_sub_val) else 0.0

        h_ok, l_ok, sub_ok = validate_backside_real_clues(k_h, k_l, k_sub)

        if not (h_ok and l_ok and sub_ok) and not backside_warned:
            msgs = []

            if not h_ok:
                msgs.append(f"H: k={k_h:.6f} > {K_MAX_LAYER_BACKSIDE}")

            if not l_ok:
                msgs.append(f"L: k={k_l:.6f} > {K_MAX_LAYER_BACKSIDE}")

            if not sub_ok:
                msgs.append(f"substrate: k={k_sub:.7f} > {K_MAX_SUBSTRATE_BACKSIDE}")

            logger.warning(
                f"Backside approximation may be invalid at {wl:.1f} nm: "
                f"{', '.join(msgs)}. "
                f"Incoherent backside correction assumes real clues "
                f"(|k_layer| < {K_MAX_LAYER_BACKSIDE}, |k_sub| < {K_MAX_SUBSTRATE_BACKSIDE})."
            )

            backside_warned = True

            break

def _build_nominal_matrix_cache_from_clues(
    clues_at_wl: dict[float, dict[str, complex | float]],
    all_wls: np.ndarray,
    p_thick_nominal: list[float],
    num_layers: int,
    logger,
) -> np.ndarray:

    all_wls_f64 = all_wls.astype(np.float64)

    n_h_cache = np.array([clues_at_wl[float(wl)]["H"] for wl in all_wls], dtype=np.complex128)

    n_l_cache = np.array([clues_at_wl[float(wl)]["L"] for wl in all_wls], dtype=np.complex128)

    p_thick_f64 = np.array(p_thick_nominal, dtype=np.float64)

    nominal_matrix_cache = precompute_matrix_cache_kernel(all_wls_f64, n_h_cache, n_l_cache, p_thick_f64, num_layers)

    return nominal_matrix_cache

def precompute_clues_and_matrices(
    params: dict[str, Any], p_thick_nominal: list[float], logger
) -> tuple[dict[float, dict[str, complex]], np.ndarray, np.ndarray]:
    """Build the wavelength-resolved index dictionary and the cumulative TMM matrix cache.

    This is the central data-preparation step executed once before Phase A.

    It constructs:

    1. **clues_at_wl** - ``{lambda: {"H": n̂_H(lambda), "L": n̂_L(lambda), "substrate": n̂_s(lambda)}}``

       Complex refractive clues (complex128) for every wavelength in the

       merged grid (scan range ∪ display range ∪ {lambda₀}).

    2. **nominal_matrix_cache** - ``(num_layers, n_wls, 2, 2)`` complex128 array.

       ``cache[k, w]`` is the cumulative 2×2 transfer matrix for layers 0…k

       at wavelength w, computed by ``precompute_matrix_cache_kernel`` using

       the Macleod +1d pre-multiply Air->Sub convention.

    3. **all_wls** - sorted unique wavelength grid (float64).

    A backside-approximation validity check is run once, warning if any

    material has k > threshold (absorbing layers degrade the incoherent

    backside correction accuracy).

    Args:

        params: Full parameter dictionary (scan range, material IDs, …).

        p_thick_nominal: Nominal physical thicknesses (nm).

        logger: Logger instance for diagnostics.

    Returns:

        (indexes_at_wl, nominal_matrix_cache, all_wls)"""

    all_wls, num_layers = _prepare_precompute_wavelength_grid(params, p_thick_nominal, logger)

    clues_at_wl = _build_clues_at_wavelengths(params, all_wls, logger)

    _warn_backside_approximation_if_needed(clues_at_wl, all_wls, logger)

    nominal_matrix_cache = _build_nominal_matrix_cache_from_clues(
        clues_at_wl, all_wls, p_thick_nominal, num_layers, logger
    )

    return clues_at_wl, nominal_matrix_cache, all_wls

@dataclass
class RobustnessContext:
    """Groups context variables for robustness and ELITE refinement."""

    params: dict[str, Any]
    params_safe: dict[str, Any]
    logger: logging.Logger
    noise_levels: list[float]
    num_runs: int
    p_thick_nominal: list[float]
    num_layers: int
    clues_at_wl: dict[str, Any]
    wl_arr: np.ndarray
    nH_arr: np.ndarray
    nL_arr: np.ndarray
    nSub_arr: np.ndarray
    T_nom: np.ndarray
    full_dyn_grid: dict[str, Any]
    n_layers_matrix_precomp: np.ndarray | None = None
