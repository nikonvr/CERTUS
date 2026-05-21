# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: keep changes small and reversible until STRAT context, worker
# phases, ranking, exports, and robustness flows have dedicated safety tests.
# Prefer extracting pure validation/formatting helpers before moving Qt classes
# or numerical kernels.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

__version__ = "26_01"

import functools
import os
from pathlib import Path

import multiprocessing
import sys

from certus_core import create_module_environment

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "STRAT")

script_dir = env["script_dir"]

import concurrent.futures

import ctypes

# ... remaining imports ...

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

from pyqtgraph.exporters import ImageExporter, SVGExporter

from certus_ui import setup_pyqtgraph_defaults

# Conditional import of Svg for the logo

try:
    from PyQt6.QtSvgWidgets import QSvgWidget

except ImportError:
    QSvgWidget = None

from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)

from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTransform,
)

from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsRectItem,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Import access config

from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_MAPPING,
    get_export_config,
    get_resource_path,
    get_safe_worker_count,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)

from certus_data import (
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

from certus_physics import (  # STRAT-specific kernels (previously imported from _certus_physics_impl)
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

from certus_strat_context import (
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

from certus_strat_db import RobustMaterialDatabase
from certus_dto import StratConfigDTO

from certus_ui import (
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
from certus_export import show_copy_excel_feedback

from certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus_ux import build_premium_overrides, OBJ
from certus_metrology import ValidationStatus
from certus_services import IndexFitRequest, IndexFitService
from certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
import certus_strat_service as _strat_service_module
from certus_strat_service import (
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

class PlotCache:
    """

    Intelligent caching system using SHA256 hashes of data content.

    Prevents re-rendering identical plots.

    """

    def __init__(self, _max_size_mb=200) -> None:

        self.cache = {}

        self.max_size_items = 20  # Keep last 20 plots

    def get_hash(self, data_obj) -> Any:

        # Create a unique signature based on the data content, not the object ID

        try:
            if isinstance(data_obj, dict):
                # Filter out heavy non-serializable objects if any

                serializable = {
                    k: v for k, v in data_obj.items() if isinstance(v, (str, int, float, list, dict, bool, type(None)))
                }

                data_str = json.dumps(serializable, sort_keys=True, separators=(",", ":"))

            else:
                data_str = str(data_obj)

            return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

        except (TypeError, AttributeError, UnicodeEncodeError) as e:
            logging.debug(f"Hash computation failed: {e}")

            return str(time.time())  # Fallback

    def get(self, key) -> Any:

        if key in self.cache:
            # Move to end (LRU style behavior) by deleting and re-inserting

            val = self.cache.pop(key)

            self.cache[key] = val

            return val

        return None

    def put(self, key, item) -> None:

        self.cache[key] = item

        if len(self.cache) > self.max_size_items:
            # Remove first inserted item (FIFO) - standard dict preserves insertion order

            first_key = next(iter(self.cache))

            del self.cache[first_key]

# === GLOBAL CONTEXT (legacy - being migrated to StratContext) ===

APP_CONTEXT: dict[str, Any] = {}

# Constants

CACHE_SIZE_MATERIAL_INDEX = 10000

IDENTITY_2x2_COMPLEX = np.eye(2, dtype=np.complex128)

class ThreadSafeCounter:
    """Thread-safe counter replacing global dictionary."""

    def __init__(self) -> None:

        self._lock = threading.Lock()

        self._count = 0

        self.signal = None

    def increment(self) -> Any:

        with self._lock:
            self._count += 1

            return self._count

    def reset(self) -> None:

        with self._lock:
            self._count = 0

    def set_signal(self, signal) -> None:

        with self._lock:
            self.signal = signal

_SPECTRUM_COUNTER = ThreadSafeCounter()

# Thread lock for legacy code

_LOCAL_LOCK = threading.Lock()

# Legacy global queues (used by main thread, workers use StratContext)

_GLOBAL_STATS_QUEUE = None

_GLOBAL_LIVE_QUEUE = None

# === STATS & THREADING UTILS (using StratContext) ===

def _resolve_materials_db_fallback(ctx) -> Any:
    """Resolve the material database using the existing fallback order."""

    if ctx is not None and ctx.app_context.get("materials_db"):
        return ctx.app_context.get("materials_db")

    return APP_CONTEXT.get("materials_db")


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
            _SPECTRUM_COUNTER.signal.progress.emit(new_val, f"Processing spectrum {new_val}")

def _flush_sp_stats() -> None:
    """Flush buffered SP stats via context."""

    ctx = StratContext.get_current()

    if ctx is not None:
        ctx.flush_stats()

# === DATABASE & PHYSICS ===

# === NUMBA KERNELS ===

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

def _run_phase_a_hybrid_loop(
    params: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: dict[str, Any],
    scan_wl_range: np.ndarray,
    num_layers: int,
    logger: logging.Logger,
    progress_signal: Any,
    l0: float,
) -> tuple[dict[int, list[dict[str, float]]], dict[int, dict[float, float]], dict[str, Any], bool]:
    raw_results_thickness: dict[int, list[dict[str, float]]] = {}
    full_dynamics_grid: dict[int, dict[float, float]] = {}
    num_runs = int(params.get("mc_runs_block", 100))
    phase_a_observability = {
        "layers": [],
        "scan_wl_count": int(len(scan_wl_range)),
        "mc_runs_block": int(num_runs),
    }
    run_states = [{"p_thick_sim": [], "M_cache_sim": {}} for _ in range(num_runs)]

    try:
        noise_tol = float(params.get("reality_sim_params", {}).get("trigger_tolerance", 0.1)) / 100.0
    except KeyError:
        noise_tol = 0.001
    phase_a_seed = int(params.get("phase_a_seed", params.get("robustness_seed", 42)))
    params["phase_a_seed"] = phase_a_seed
    phase_a_rng = np.random.default_rng(phase_a_seed)

    global_noise_matrix = generate_noise_array(
        (num_runs, num_layers),
        noise_tol,
        NOISE_DISTRIBUTION_GAUSSIAN,
        rng=phase_a_rng,
    )

    idx_dict_opt = _IdxWrapper(clues_at_wl)

    for i_layer in range(num_layers):
        if params.get("stop_requested", False):
            logger.warning(f"Stop requested during Phase A at layer {i_layer}")
            break
        if progress_signal:
            pct = int((i_layer / num_layers) * 40)
            progress_signal.emit(pct, f"Phase A: Computing Layer {i_layer + 1}/{num_layers}")

        current_avg_stack = []
        if i_layer > 0:
            for j in range(i_layer):
                avg_t = np.mean([run["p_thick_sim"][j] for run in run_states])
                current_avg_stack.append(avg_t)

        n_H_scan = np.array([idx_dict_opt[float(wl)]["H"] for wl in scan_wl_range], dtype=np.complex128)
        n_L_scan = np.array([idx_dict_opt[float(wl)]["L"] for wl in scan_wl_range], dtype=np.complex128)

        layer_matrix_cache = precompute_matrix_cache_kernel(
            scan_wl_range.astype(np.float64),
            n_H_scan,
            n_L_scan,
            np.array(current_avg_stack, dtype=np.float64),
            i_layer,
        )

        if i_layer > 0:
            prev_data = raw_results_thickness.get(i_layer - 1, [])
            params["prev_layer_wl"] = float(prev_data[0]["wl"]) if prev_data else -1.0
        else:
            params["prev_layer_wl"] = -1.0

        candidates, layer_full_dyn = _select_candidates_phase_a(
            scan_wl_range,
            i_layer,
            p_thick_nominal,
            clues_at_wl,
            layer_matrix_cache,
            scan_wl_range,
            params,
            l0,
            current_avg_stack=current_avg_stack,
        )
        full_dynamics_grid[i_layer] = layer_full_dyn

        results_thickness, sim_updates = _validate_candidates_phase_a(
            candidates,
            i_layer,
            num_runs,
            p_thick_nominal,
            clues_at_wl,
            params,
            run_states,
            global_noise_matrix[:, i_layer],
        )

        if i_layer == 0:
            nucleation_active = params.get("nucleation_wl") is not None
            if not nucleation_active:
                attenuation_factor = float(params.get("layer1_cost_attenuation_factor", 1.0))
                if 0.0 < attenuation_factor < 1.0:
                    for item in results_thickness:
                        item["cost"] *= attenuation_factor
                        item["std_dev"] *= attenuation_factor
                    logger.info(f"   -> Layer 1: Costs attenuated by factor {attenuation_factor}.")
                else:
                    logger.info("   -> Layer 1: No attenuation (factor >= 1.0).")
            else:
                logger.info("   -> Layer 1: Costs preserved (Smart Nucleation active).")

        raw_results_thickness[i_layer] = results_thickness
        best_cost = float(results_thickness[0]["cost"]) if results_thickness else None
        best_wl = float(results_thickness[0]["wl"]) if results_thickness else None

        phase_a_observability["layers"].append(
            {
                "layer": int(i_layer + 1),
                "selected_candidates_count": int(len(candidates)),
                "validated_candidates_count": int(len(results_thickness)),
                "best_wl": best_wl,
                "best_cost": best_cost,
            }
        )

        for r_idx in range(num_runs):
            run_states[r_idx]["p_thick_sim"].append(sim_updates[r_idx])

    return raw_results_thickness, full_dynamics_grid, phase_a_observability, params.get("stop_requested", False)

def _normalize_phase_a_results(
    raw_results_thickness: dict[int, list[dict[str, float]]],
    num_layers: int,
) -> dict[int, list[dict[str, float]]]:
    total_sum_thick = 0.0
    total_count_thick = 0
    for i in range(num_layers):
        t_data = raw_results_thickness.get(i, [])
        if t_data:
            total_sum_thick += sum(item["cost"] for item in t_data)
            total_count_thick += len(t_data)
    mean_thickness = (total_sum_thick / total_count_thick) if total_count_thick > 0 else 1.0
    if abs(mean_thickness) < 1e-12:
        mean_thickness = 1.0

    raw_results_sq: dict[int, list[dict[str, float]]] = {}
    for i in range(num_layers):
        t_data = raw_results_thickness.get(i, [])
        if not t_data:
            continue
        sq_layer = []
        for item in t_data:
            cost_raw = item["cost"]
            cost_norm = cost_raw / mean_thickness
            sq_layer.append(
                {
                    "wl": item["wl"],
                    "cost": (cost_norm**2),
                    "cost_raw": cost_raw,
                }
            )
        sq_layer.sort(key=lambda x: x["cost"])
        raw_results_sq[i] = sq_layer
    return raw_results_sq

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

# === HELPER FUNCTIONS ===

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

    db_local = params.get("materials_db_instance")

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
        wl_mon = layer_to_wl.get(i_layer, float(params["l0"]))

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
    local_db = params.get("materials_db_instance")
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
                min_res, bad_layer = _calculate_strategy_spectral_resolution(res["strategy"], p_thick_nominal, params)
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
                    min_res, bad_layer = _calculate_strategy_spectral_resolution(
                        res["strategy"], p_thick_nominal, params
                    )
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

def _compute_dT_dd_per_layer(
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    p_thick_nominal: list[float],
    h_nm: float = 0.5,
) -> np.ndarray:
    """

    Compute dT/dd at nominal thickness for each layer (transmission sensitivity).

    Used when noise_domain is thickness_nm to convert thickness noise to transmission noise.

    """

    num_layers = len(p_thick_nominal)

    p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)

    dT_dd = np.zeros(num_layers, dtype=np.float64)

    # Precompute M_before per wavelength block to avoid O(N²) recomputation (C2 fix).
    # Within a block all layers share the same monitoring wavelength, so one
    # precompute_matrix_cache_kernel call covers every layer in that block.
    M_before_all = np.zeros((num_layers, 2, 2), dtype=np.complex128)
    M_before_all[0] = np.eye(2, dtype=np.complex128)

    block_starts = [0]
    for i in range(1, num_layers):
        if abs(float(layer_wavelengths[i]) - float(layer_wavelengths[block_starts[-1]])) > 1e-3:
            block_starts.append(i)

    for b_idx in range(len(block_starts)):
        b_start = block_starts[b_idx]
        b_end = block_starts[b_idx + 1] if b_idx + 1 < len(block_starts) else num_layers
        wl_b = float(layer_wavelengths[b_start])
        if wl_b < 0.1 or b_end <= 1:
            continue
        last_layer = b_end - 1
        if last_layer > 0:
            cache = precompute_matrix_cache_kernel(
                np.array([wl_b], dtype=np.float64),
                np.array([n_H_vals[b_start]], dtype=np.complex128),
                np.array([n_L_vals[b_start]], dtype=np.complex128),
                p_thick_arr[:last_layer],
                last_layer,
            )
            for i in range(max(1, b_start), b_end):
                if i - 1 < cache.shape[0]:
                    M_before_all[i] = cache[i - 1, 0, :, :]

    for i in range(num_layers):
        wl_i = float(layer_wavelengths[i])

        if wl_i < 0.1:
            dT_dd[i] = 1e-6

            continue

        n_current = n_H_vals[i] if (i % 2) == 0 else n_L_vals[i]

        n_Sub = n_Sub_vals[i]

        d_nom = p_thick_arr[i]

        M_b = M_before_all[i]
        M00, M01, M10, M11 = M_b[0, 0], M_b[0, 1], M_b[1, 0], M_b[1, 1]

        d_plus = d_nom + h_nm

        d_minus = max(0.1, d_nom - h_nm)

        T_plus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_plus)

        T_minus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_minus)

        denom = d_plus - d_minus

        dT_dd[i] = (T_plus - T_minus) / denom if denom > 1e-9 else 1e-6

    return dT_dd

def _extract_local_extrema_points(d_vals: np.ndarray, t_vals: np.ndarray, eps: float = 1e-10) -> list[dict[str, float]]:
    """Find local extrema from sampled T(d) curve."""

    extrema: list[dict[str, float]] = []

    if len(d_vals) < 3 or len(t_vals) < 3:
        return extrema

    for i in range(1, len(t_vals) - 1):
        prev_v = float(t_vals[i - 1])

        cur_v = float(t_vals[i])

        next_v = float(t_vals[i + 1])

        if (cur_v - prev_v) > eps and (cur_v - next_v) > eps:
            extrema.append({"type": "max", "d_nm": float(d_vals[i]), "T": cur_v})

        elif (prev_v - cur_v) > eps and (next_v - cur_v) > eps:
            extrema.append({"type": "min", "d_nm": float(d_vals[i]), "T": cur_v})

    return extrema

def _compute_theoretical_layer_profile(
    wl_nm: float,
    n_current: complex,
    n_sub: complex,
    nominal_thickness: float,
    M_before: np.ndarray,
) -> dict[str, Any]:
    """Theoretical no-noise profile for one layer: Tinit/Textrema/Tfinal + distances."""

    M00, M01, M10, M11 = (
        M_before[0, 0],
        M_before[0, 1],
        M_before[1, 0],
        M_before[1, 1],
    )

    d_nom = float(max(0.0, nominal_thickness))

    n_steps = max(3, int(np.ceil(d_nom / 1.0)) + 1)

    d_grid = np.linspace(0.0, d_nom, n_steps, dtype=np.float64)

    t_grid = np.empty(n_steps, dtype=np.float64)

    for idx in range(n_steps):
        t_grid[idx] = compute_T_front_at_layer(wl_nm, n_current, n_sub, M00, M01, M10, M11, d_grid[idx])

    t_init = float(t_grid[0])

    t_final = float(t_grid[-1])

    extrema = _extract_local_extrema_points(d_grid, t_grid)

    dist_ps, dist_ns, dist_pe, dist_ne = calculate_extrema_distances(
        float(wl_nm), complex(n_current), complex(n_sub), d_nom, M_before
    )

    d_end_nearest = float(min(dist_pe, dist_ne))

    nearest_end_type = "between"

    nearest_curve_dist = d_end_nearest

    if extrema:
        nearest_ext = min(extrema, key=lambda e: abs(float(e.get("d_nm", 0.0)) - d_nom))

        nearest_curve_dist = float(abs(float(nearest_ext.get("d_nm", 0.0)) - d_nom))

        nearest_end_type = str(nearest_ext.get("type", "between")).lower()

    if nearest_end_type in {"min", "max"} and nearest_curve_dist <= 2.0:
        tfinal_class = f"near {nearest_end_type}"

    else:
        tfinal_class = "between"

    return {
        "Tinit": t_init,
        "Tfinal": t_final,
        "Textrema": extrema,
        "d_nom_nm": d_nom,
        "dist_prev_start": float(dist_ps),
        "dist_next_start": float(dist_ns),
        "dist_prev_end": float(dist_pe),
        "dist_next_end": float(dist_ne),
        "dist_end_nearest": d_end_nearest,
        "nearest_end_type": nearest_end_type,
        "nearest_end_dist_nm": nearest_curve_dist,
        "tfinal_class": tfinal_class,
        "extrema_count": int(len(extrema)),
    }

def _compute_strategy_symmetry_score_percent(
    theoretical_layer_profile: list[dict[str, Any]],
    window_ot: float,
) -> float:
    """

    Strategy-level symmetry score on [0, 100].

    Per layer, evaluate start/end local symmetry around extrema and keep the best

    (pseudo-symmetry included via the local score balance term), then average.

    """

    if not theoretical_layer_profile:
        return 0.0

    layer_scores: list[float] = []

    for prof in theoretical_layer_profile:
        try:
            s_start = _compute_local_extrema_symmetry_score(
                float(prof.get("dist_prev_start", SYM_MISSING_DISTANCE)),
                float(prof.get("dist_next_start", SYM_MISSING_DISTANCE)),
                float(window_ot),
            )

            s_end = _compute_local_extrema_symmetry_score(
                float(prof.get("dist_prev_end", SYM_MISSING_DISTANCE)),
                float(prof.get("dist_next_end", SYM_MISSING_DISTANCE)),
                float(window_ot),
            )

            layer_scores.append(max(float(s_start), float(s_end)))

        except (TypeError, ValueError):
            layer_scores.append(0.0)

    if not layer_scores:
        return 0.0

    return float(100.0 * _clamp01(float(np.mean(np.array(layer_scores, dtype=np.float64)))))

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
            # Noise domain: T fraction. noise_val already in % units (e.g. 0.1 means 0.1%).
            # simulate_stack_robustness_batch receives it as-is (fraction comparable to T [0-1]).
            noise_matrix = raw_noise * noise_val * penalty_vector

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

# === STRATEGIES TABLE WINDOW (COLOR-CODED) ===

class StrategiesTableWindow(QMainWindow):
    strategy_selected = pyqtSignal(int, object)

    def __init__(
        self,
        parent,
        strategies_results: list[dict[str, Any]],
        p_thick_nominal: list[float],
        include_secondary_rmse_stats: bool = False,
    ) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.p_thick_nominal = np.array(p_thick_nominal, dtype=np.float64)

        self.strategies_results = strategies_results

        self.include_secondary_rmse_stats = bool(include_secondary_rmse_stats)

        self._details_dialogs: list[Any] = []

        self.selected_row = -1

        self.setWindowTitle("Dual-Objective Strategies Comparison (+ SEEL Colors)")

        screen = QApplication.primaryScreen().availableGeometry()

        w_win = min(1800, int(screen.width() * 0.95))

        h_win = min(800, int(screen.height() * 0.85))

        self.resize(w_win, h_win)

        self.move((screen.width() - w_win) // 2, (screen.height() - h_win) // 2)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        logo_container = QWidget()

        logo_layout = QHBoxLayout(logo_container)

        logo_layout.setContentsMargins(5, 5, 0, 0)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            logo_layout.addWidget(mini_logo)

        else:
            lbl_fallback = QLabel("CERTUS")

            lbl_fallback.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 14px;")

            logo_layout.addWidget(lbl_fallback)

        logo_layout.addStretch()

        layout.addWidget(logo_container)

        title_label = QLabel("All Strategies Robustness Test - Detailed Breakdown")

        title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")

        layout.addWidget(title_label)

        self.origin_summary_label = QLabel("Origins: -")

        self.origin_summary_label.setStyleSheet("font-size: 12px; color: #4a5568; padding: 2px 10px 8px 10px;")

        layout.addWidget(self.origin_summary_label)

        self.table = ExcelTableWidget()

        self.table.cellClicked.connect(self.on_cell_clicked)

        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.update_data(strategies_results)

        layout.addWidget(self.table)

        button_layout = QHBoxLayout()

        save_strat_btn = create_styled_button("Save Selected Strategy (JSON)", variant="success")

        save_strat_btn.setToolTip(
            "Save the currently selected strategy row as a JSON file.\n"
            "Click a row first to select it, then click this button."
        )

        save_strat_btn.clicked.connect(self.save_current_strategy)

        button_layout.addWidget(save_strat_btn)

        export_btn = create_styled_button("Export to CSV", variant="secondary")

        export_btn.setToolTip("Export the full strategies table to a CSV file (all rows and columns).")

        export_btn.clicked.connect(self.handle_export_csv)

        close_btn = create_styled_button("Close", variant="secondary")

        close_btn.setToolTip("Close this strategies comparison window.")

        close_btn.clicked.connect(self.close)

        button_layout.addWidget(export_btn)

        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _calculate_worst_layers(self, strategy_result, top_k=10) -> Any:

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            if not results_per_noise:
                return ["No Res"] * top_k

            target_res = results_per_noise[0]

            for r in results_per_noise:
                if abs(r.get("noise_level", 0) - 1.0) < 0.1:
                    target_res = r

                    break

            thicknesses_all = target_res.get("thicknesses_all", [])

            if not thicknesses_all:
                return ["No Data"] * top_k

            min_len = min(len(row) for row in thicknesses_all)

            if min_len == 0:
                return ["Empty"] * top_k

            clean_data = [row[:min_len] for row in thicknesses_all]

            sim_matrix = np.array(clean_data, dtype=np.float64)

            nom_arr = self.p_thick_nominal

            if nom_arr is None or len(nom_arr) == 0:
                return [f"Ref:0 vs Sim:{min_len}"] + ["-"] * (top_k - 1)

            common_layers = min(sim_matrix.shape[1], len(nom_arr))

            if common_layers == 0:
                return ["0 Layers"] * top_k

            sim_matrix_sliced = sim_matrix[:, :common_layers]

            nom_arr_sliced = nom_arr[:common_layers]

            abs_errors = np.abs(sim_matrix_sliced - nom_arr_sliced)

            p95_errors = np.percentile(abs_errors, 95, axis=0)

            layer_stats = []

            for i, err in enumerate(p95_errors):
                layer_stats.append((i + 1, err))

            layer_stats.sort(key=lambda x: x[1], reverse=True)

            output = []

            for i in range(top_k):
                if i < len(layer_stats):
                    l_idx, err_val = layer_stats[i]

                    output.append(f"L{l_idx} {err_val:.2f}nm")

                else:
                    output.append("")

            return output

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            return [str(e)[:15]] * top_k

    def _populate_table_row(
        self, row: int, result: dict[str, Any], strat: dict[str, Any], max_blocks: int, _rmse_to_seel: Any
    ) -> None:
        """Helper method to populate a single row in the strategies table."""
        # 0: Rank
        rank_item = NumericTableWidgetItem(str(row + 1))
        rank_item.setData(Qt.ItemDataRole.UserRole, result)
        rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if row == 0:
            rank_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 0, rank_item)

        # 1: ID
        id_item = NumericTableWidgetItem(str(strat["strategy_id"]))
        id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, id_item)

        # 2: Origin
        origin = strat.get("origin", "unknown").upper()
        display_text = origin.split("(")[0].strip()
        origin_item = QTableWidgetItem(display_text)
        origin_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if any(x in origin for x in ["SMART", "DEEP", "MERGE", "HYBRID"]):
            origin_item.setBackground(QColor(CertusTheme.INFO_BG))
            origin_item.setForeground(QColor(CertusTheme.INFO_TEXT))
            origin_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
            origin_item.setToolTip(f"✨ {origin}")
        else:
            origin_item.setForeground(QColor(80, 80, 80))
            origin_item.setToolTip(origin)
        self.table.setItem(row, 2, origin_item)

        # 3: Min Res
        min_res = result.get("min_resolution", 999.0)
        res_val_str = f"{min_res:.2f}" if min_res < 100 else ">100"
        res_item = NumericTableWidgetItem(res_val_str)
        res_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if min_res < 0.5:
            res_item.setBackground(QColor(CertusTheme.DANGER_BG))
        elif min_res < 1.5:
            res_item.setBackground(QColor(CertusTheme.WARNING_BG))
        else:
            res_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        limiting = result.get("limiting_layer", "?")
        res_item.setToolTip(f"Limiting Factor: Layer #{limiting}")
        self.table.setItem(row, 3, res_item)

        # 4 & 5: Ranks
        th_rank = strat.get("thickness_rank", None)
        self.table.setItem(row, 4, NumericTableWidgetItem(str(th_rank) if th_rank is not None else "N/A (non calcule)"))
        sp_rank = strat.get("spectral_rank", None)
        self.table.setItem(row, 5, NumericTableWidgetItem(str(sp_rank) if sp_rank is not None else "N/A (non calcule)"))

        # 6 & 7: Blocks / Changes
        self.table.setItem(row, 6, NumericTableWidgetItem(str(strat["n_blocks"])))
        actual_changes = strat["n_blocks"] - 1
        violated = strat.get("constraint_violated", False)
        changes_item = NumericTableWidgetItem(str(actual_changes))
        if violated:
            changes_item.setText(f"{actual_changes} (⚠️)")
            changes_item.setBackground(QColor(CertusTheme.DANGER_BG))
        self.table.setItem(row, 7, changes_item)

        # 8: Unique Lambda
        self.table.setItem(row, 8, NumericTableWidgetItem(str(result["num_unique_wavelengths"])))

        # 9: Robust Score
        score_item = NumericTableWidgetItem(f"{result['robustness_score']:.6f}")
        if row == 0:
            score_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
        self.table.setItem(row, 9, score_item)

        # 10: Symmetry Score [0..100]
        sym_score = strat.get("symmetry_score_pct", result.get("symmetry_score_pct", None))
        if sym_score is None:
            sym_score = _compute_strategy_symmetry_score_percent(
                strat.get("theoretical_layer_profile", []), SYM_DEFAULT_EXTREMA_WINDOW_OT
            )
        try:
            sym_score_f = float(sym_score)
        except (TypeError, ValueError):
            sym_score_f = 0.0
        sym_score_f = max(0.0, min(100.0, sym_score_f))
        sym_item = NumericTableWidgetItem(f"{sym_score_f:.1f}")
        sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        sym_item.setToolTip("Layer-by-layer symmetry score (0-100). 100 = perfect symmetry across the entire stack.")
        if sym_score_f >= 80.0:
            sym_item.setBackground(QColor(CertusTheme.SUCCESS_BG))
            sym_item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
            sym_item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
        elif sym_score_f >= 50.0:
            sym_item.setBackground(QColor(CertusTheme.WARNING_BG))
            sym_item.setForeground(QColor(CertusTheme.WARNING_TEXT))
        else:
            sym_item.setBackground(QColor(CertusTheme.DANGER_BG))
            sym_item.setForeground(QColor(CertusTheme.DANGER_TEXT))
        self.table.setItem(row, 10, sym_item)

        # 11: Comp. Factor
        comp_factor_str = "-"
        noise_results = result.get("results_per_noise", [])
        res_1x = next((r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1), None)
        if res_1x:
            try:
                th_data = res_1x.get("thicknesses_all", [])
                if th_data and self.p_thick_nominal is not None:
                    mat_sim = np.array(th_data)
                    limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))
                    diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])
                    avg_phys_err = np.mean(diffs)
                    rmse_val = res_1x.get("rmse_p95", res_1x.get("rmse_mean", 0.0))
                    seel_val = _rmse_to_seel(rmse_val)
                    if seel_val and seel_val > 1e-9:
                        ratio = avg_phys_err / seel_val
                        comp_factor_str = f"{ratio:.2f}"
            except (ValueError, TypeError, ZeroDivisionError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        comp_item = NumericTableWidgetItem(comp_factor_str)
        comp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        comp_item.setToolTip("Compensation Factor = Avg Phys Error / SEEL @ 1.0x Noise")
        if comp_factor_str != "-":
            val = float(comp_factor_str)
            if val > 1.5:
                comp_item.setForeground(QColor(CertusTheme.SUCCESS))
                comp_item.setFont(CertusTheme.get_font(weight=QFont.Weight.Bold))
            elif val < 0.8:
                comp_item.setForeground(QColor(CertusTheme.DANGER))
        self.table.setItem(row, 11, comp_item)

        # 12: Median extrema count per layer (theoretical)
        ext_counts = []
        for p in strat.get("theoretical_layer_profile", []):
            try:
                ext_counts.append(int(p.get("extrema_count", 0)))
            except (TypeError, ValueError):
                continue
        if ext_counts:
            ext_p50 = float(np.percentile(np.array(ext_counts, dtype=np.float64), 50))
            ext_item = NumericTableWidgetItem(f"{ext_p50:.1f}")
        else:
            ext_item = NumericTableWidgetItem("N/A")
        ext_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_item.setToolTip("Number of extrema computed on the theoretical noiseless curve")
        self.table.setItem(row, 12, ext_item)

        # 13, 14, 15: SEEL Columns
        for col_idx, noise_idx in enumerate([0, 1, 2]):
            target_col = 13 + col_idx
            if noise_idx < len(noise_results):
                rmse_val = noise_results[noise_idx].get("rmse_p95", noise_results[noise_idx]["rmse_mean"])
                seel_val = _rmse_to_seel(rmse_val)
                if seel_val is not None:
                    item_txt = f"{seel_val:.3f} nm"
                    item = NumericTableWidgetItem(item_txt)
                    item.setToolTip(f"Raw RMSE P95: {rmse_val:.6f}")
                    if seel_val < 0.3:
                        item.setBackground(QColor(CertusTheme.SUCCESS_BG))
                        item.setForeground(QColor(CertusTheme.SUCCESS_TEXT))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif seel_val < 1.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    elif seel_val < 2.0:
                        item.setBackground(QColor(CertusTheme.WARNING_BG))
                        item.setForeground(QColor(CertusTheme.WARNING_TEXT))
                    else:
                        item.setBackground(QColor(CertusTheme.DANGER_BG))
                        item.setForeground(QColor(CertusTheme.DANGER_TEXT))
                    self.table.setItem(row, target_col, item)
                else:
                    self.table.setItem(row, target_col, NumericTableWidgetItem(f"R:{rmse_val:.5f}"))
            else:
                self.table.setItem(row, target_col, QTableWidgetItem("N/A"))

        # Blocks
        start_col_blocks = 16
        blocks = strat.get("blocks", [])
        for b_idx in range(max_blocks):
            col_idx = start_col_blocks + b_idx
            if b_idx < len(blocks):
                block = blocks[b_idx]
                wl = block["wavelength"]
                l_start = block["start"] + 1
                l_end = block["end"]
                text_desc = f"{wl:.0f}nm (L{l_start}->L{l_end})"
                block_item = QTableWidgetItem(text_desc)
                block_item.setToolTip(f"Block #{b_idx + 1}\nWavelength: {wl}nm\nLayers: {l_start} to {l_end}")
                self.table.setItem(row, col_idx, block_item)
            else:
                self.table.setItem(row, col_idx, QTableWidgetItem(""))

        # Worst Layers
        start_col_errors = start_col_blocks + max_blocks
        worst_layers = self._calculate_worst_layers(result, top_k=10)
        for err_idx, text_val in enumerate(worst_layers):
            item = QTableWidgetItem(text_val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if "nm" in text_val:
                try:
                    val_part = text_val.split()[1].replace("nm", "")
                    val = float(val_part)
                    if val > 2.0:
                        item.setForeground(QColor(CertusTheme.DANGER))
                        item.setFont(CertusTheme.get_font(9, QFont.Weight.Bold))
                    elif val > 1.0:
                        item.setForeground(QColor(CertusTheme.WARNING))
                except (ValueError, IndexError, AttributeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
            self.table.setItem(row, start_col_errors + err_idx, item)

    def update_data(self, strategies_results: list[dict[str, Any]]) -> float | None:
        """

        Update the strategies table with new results.

        This method updates the display table with optimization results including:

        - Strategy performance metrics

        - Layer thickness information

        - Error statistics and rankings

        - Table refresh and sorting

        Args:

            self: StrategiesTable instance

            strategies_results: List of strategy result dictionaries with performance data

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling for data processing

            - Updates table UI components

            - Handles large datasets efficiently

        """

        self.strategies_results = strategies_results

        self.table.setUpdatesEnabled(False)

        self.table.setSortingEnabled(False)

        # Internal helper for SEEL

        seel_data = APP_CONTEXT.get("seel_data")

        def _rmse_to_seel(rmse_val) -> float | None:

            if seel_data and "fit_alpha" in seel_data and "fit_k" in seel_data:
                alpha = seel_data["fit_alpha"]

                k = seel_data["fit_k"]

                return float(k * (rmse_val**alpha))

            if seel_data and "avg_rmse" in seel_data:
                seel_x = np.array(seel_data["avg_rmse"])

                seel_y = np.array(seel_data["sigmas"])

                idx = np.argsort(seel_x)

                return float(np.interp(rmse_val, seel_x[idx], seel_y[idx]))

            return None

        try:
            self.table.clearContents()

            self.table.setRowCount(len(strategies_results))

            origin_counts: dict[str, int] = {}

            for res in strategies_results:
                origin_raw = str(res.get("strategy", {}).get("origin", "UNKNOWN")).upper()

                origin_key = origin_raw.split("(")[0].strip() if origin_raw else "UNKNOWN"

                origin_counts[origin_key] = origin_counts.get(origin_key, 0) + 1

            if origin_counts:
                items = sorted(origin_counts.items(), key=lambda kv: (-kv[1], kv[0]))

                summary = " | ".join([f"{k}: {v}" for k, v in items])

                self.origin_summary_label.setText(f"Origins ({len(strategies_results)}): {summary}")

            else:
                self.origin_summary_label.setText("Origins: -")

            max_blocks = 0

            has_th_rank = False

            has_sp_rank = False

            for res in strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

                strat_local = res.get("strategy", {})

                if strat_local.get("thickness_rank", None) is not None:
                    has_th_rank = True

                if strat_local.get("spectral_rank", None) is not None:
                    has_sp_rank = True

            # --- HEADER DEFINITION (Modified) ---

            # Metric updated: Complexity out, Comp.Factor in

            base_headers = [
                "Rank",
                "ID",
                "Origin",
                "Min Res (nm)",
                "Th Rank",
                "Sp Rank",
                "Blocks",
                "Changes",
                "Unique lambda",
                "Robust Score",
                "Sym Score",
                "Comp. Factor",
                "Next",
            ]

            noise_headers = ["SEEL (0.5x)", "SEEL (1.0x)", "SEEL (2.0x)"]

            block_headers = [f"Block {i + 1}" for i in range(max_blocks)]

            error_headers = [f"Worst #{i + 1} (P95)" for i in range(10)]

            all_headers = base_headers + noise_headers + block_headers + error_headers

            self.table.setColumnCount(len(all_headers))

            self.table.setHorizontalHeaderLabels(all_headers)

            # --- HEADER TOOLTIPS ---

            _header_tips = {
                "Rank": "Global robustness ranking (1 = best). Sorted by Robust Score.",
                "ID": "Internal strategy identifier assigned during the Dynamic Programming search.",
                "Origin": "Algorithm that generated this strategy: DP (Dynamic Programming), "
                "SMART (elite candidate), HYBRID, MERGE, DEEP, etc.",
                "Min Res (nm)": "Minimum optical thickness resolution across all layers and blocks "
                "(nm). Low values = harder to hit the turning point precisely. "
                "<1.5 nm -> warning, <0.5 nm -> critical.",
                "Th Rank": "Thickness-based DP rank: strategies with smaller total thickness "
                "cost get a lower rank (hidden if not computed).",
                "Sp Rank": "Spectral-sensitivity DP rank: strategies with more stable spectral "
                "response near turning points get a lower rank (hidden if not computed).",
                "Blocks": "Number of monochromatic monitoring blocks. Each block = one "
                "monitoring wavelength covering one or more consecutive layers.",
                "Changes": "Number of wavelength changes (= Blocks - 1). ⚠️ if the maximum "
                "allowed changes constraint is violated.",
                "Unique lambda": "Number of distinct monitoring wavelengths used across all blocks.",
                "Robust Score": "Monte Carlo robustness score: mean RMSE of the final stack over "
                "many simulated depositions with Gaussian thickness noise. "
                "Lower = more robust. Primary sort key.",
                "Sym Score": "SYM (Symmetry) score: rewards strategies whose layer turning points "
                "are positioned far from optical extrema (local T maxima/minima), "
                "reducing sensitivity to deposition errors.",
                "Comp. Factor": "Complexity factor: composite metric balancing the number of blocks, "
                "wavelength changes, and optical sensitivity.",
                "Next": "Button to inspect this strategy in detail (spectral performance, "
                "layer-by-layer profile, extrema proximity).",
            }

            # SEEL columns

            for i, lbl in enumerate(noise_headers):
                level = ["0.5×", "1.0×", "2.0×"][i]

                _header_tips[lbl] = (
                    f"SEEL estimate at noise level {level}: equivalent production yield (%) "
                    f"predicted from the robustness RMSE via the SEEL calibration curve. "
                    f"Higher = better yield."
                )

            # Block columns

            for i in range(max_blocks):
                _header_tips[f"Block {i + 1}"] = (
                    f"Monitoring wavelength (nm) for block {i + 1}, covering the layer range "
                    f"[start … end]. Click the row to see the full block definition."
                )

            # Worst-layer columns

            for i in range(10):
                _header_tips[f"Worst #{i + 1} (P95)"] = (
                    f"Layer with the #{i + 1} highest thickness error at the 95th percentile "
                    f"across Monte Carlo simulations (noise level 1.0×). "
                    f"Format: L<index> <P95 error in nm>."
                )

            for col, label in enumerate(all_headers):
                tip = _header_tips.get(label)

                if tip:
                    item = self.table.horizontalHeaderItem(col)

                    if item:
                        item.setToolTip(tip)

            # --- END HEADER TOOLTIPS ---

            # Auto-hide row columns if no value is calculated.

            self.table.setColumnHidden(4, not has_th_rank)

            self.table.setColumnHidden(5, not has_sp_rank)

            for row, result in enumerate(strategies_results):
                strat = result["strategy"]
                self._populate_table_row(row, result, strat, max_blocks, _rmse_to_seel)

            header = self.table.horizontalHeader()

            for i in range(self.table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.getLogger("ThinFilm").error(f"Table update error: {e}")

            logging.getLogger("ThinFilm").error(traceback.format_exc())

        finally:
            self.table.setSortingEnabled(True)

            self.table.setUpdatesEnabled(True)

    def on_cell_clicked(self, row: int, col: int) -> Any:

        self.table.clearSelection()

        rank_item = self.table.item(row, 0)

        if not rank_item:
            return

        strategy_result = rank_item.data(Qt.ItemDataRole.UserRole)

        if not strategy_result and 0 <= row < len(self.strategies_results):
            # Fallback when Qt item user-data is unexpectedly missing after sorting/refresh.

            strategy_result = self.strategies_results[row]

        if not strategy_result:
            # Last fallback by strategy ID lookup from table column 1.

            id_item = self.table.item(row, 1)

            sid = str(id_item.text()).strip() if id_item else ""

            if sid:
                for res in self.strategies_results:
                    if str(res.get("strategy", {}).get("strategy_id", "")).strip() == sid:
                        strategy_result = res

                        break

        if strategy_result:
            self.strategy_selected.emit(row, strategy_result)

            for c in range(self.table.columnCount()):
                item = self.table.item(row, c)

                if item:
                    item.setSelected(True)

            # --- POPUP EXTRA: THEORETICAL PROFILE BY LAYER ---

            strat = strategy_result.get("strategy", {})

            extrema_distances = strat.get("extrema_distances", [])

            theo_profile = strat.get("theoretical_layer_profile", [])

            if extrema_distances or theo_profile:
                msg = "Theoretical no-noise per-layer profile\n"

                msg += "Fields: Tinit, Textrema[], Tfinal, and distances to extrema (nm)\n\n"

                n_layers = max(len(extrema_distances), len(theo_profile))

                for i_layer in range(n_layers):
                    dists = extrema_distances[i_layer] if i_layer < len(extrema_distances) else {}

                    prof = theo_profile[i_layer] if i_layer < len(theo_profile) else {}

                    msg += f"--- Layer {i_layer + 1} ---\n"

                    # Distances to generic 15nm limit rule

                    def fmt_dist(v, sign="") -> Any:

                        return f"{sign}{v:.1f}nm (OT)" if v <= 15.0 else "not critical"

                    # Start (d=0)

                    msg += f"  Start (d=0): Prev Extrema @ {fmt_dist(dists.get('prev_start', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_start', 999), '+')}\n"

                    # End (d=d_nom)

                    msg += f"  End (d=nom): Prev Extrema @ {fmt_dist(dists.get('prev_end', 999), '-')}\n"

                    msg += f"               Next Extrema @ {fmt_dist(dists.get('next_end', 999), '+')}\n"

                    try:
                        t_init = prof.get("Tinit", None)

                        t_final = prof.get("Tfinal", None)

                        if t_init is not None:
                            msg += f"  Tinit:  {float(t_init) * 100:.3f}%\n"

                        if t_final is not None:
                            msg += f"  Tfinal: {float(t_final) * 100:.3f}%\n"

                        near_type = str(prof.get("nearest_end_type", "between"))

                        near_dist = float(prof.get("nearest_end_dist_nm", np.nan))

                        tf_class = str(prof.get("tfinal_class", "between"))

                        if np.isfinite(near_dist):
                            msg += f"  Tfinal class: {tf_class} (nearest {near_type}, d={near_dist:.2f}nm)\n"

                    except (TypeError, ValueError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    extrema_list = prof.get("Textrema", [])

                    if extrema_list:
                        msg += "  Textrema:\n"

                        max_show = 12

                        for e_idx, e in enumerate(extrema_list[:max_show], 1):
                            e_type = str(e.get("type", "?"))

                            e_d = float(e.get("d_nm", np.nan))

                            e_t = float(e.get("T", np.nan))

                            msg += f"    {e_idx:02d}. {e_type} @ d={e_d:.2f}nm -> T={e_t * 100:.3f}%\n"

                        if len(extrema_list) > max_show:
                            msg += f"    ... {len(extrema_list) - max_show} more extrema\n"

                    else:
                        msg += "  Textrema: none detected on [0, d_nom]\n"

                    msg += "\n"

                # We use a custom QDialog with QTextEdit for scrollable text if there are many layers

                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

                dlg = QDialog(self)

                dlg.setWindowTitle(f"Extrema Proximity - Strategy {strat.get('strategy_id', 'Unknown')}")

                dlg.resize(400, 500)

                dlg_layout = QVBoxLayout(dlg)

                txt_edit = QTextEdit()

                txt_edit.setReadOnly(True)

                txt_edit.setText(msg)

                # Use a monospaced font for better alignment

                font = txt_edit.font()

                font.setFamily("Consolas")

                txt_edit.setFont(font)

                dlg_layout.addWidget(txt_edit)

                btn = QPushButton("Close")

                btn.setToolTip("Close the proximity extrema dialog.")

                btn.clicked.connect(dlg.accept)

                dlg_layout.addWidget(btn)

                # Non-modal popup so strategy monitoring windows can open immediately.

                dlg.setModal(False)

                dlg.show()

                dlg.raise_()

                dlg.activateWindow()

                self._details_dialogs.append(dlg)

                def _remove_details_dialog(*_args, dialog=dlg) -> None:
                    if dialog in self._details_dialogs:
                        self._details_dialogs.remove(dialog)

                dlg.finished.connect(_remove_details_dialog)

    def save_current_strategy(self) -> None:

        current_row = self.table.currentRow()

        if current_row < 0:
            logging.getLogger("ThinFilm").warning("No strategy selected to save.")

            return

        rank_item = self.table.item(current_row, 0)

        if not rank_item:
            return

        result_obj = rank_item.data(Qt.ItemDataRole.UserRole)

        if not result_obj or "strategy" not in result_obj:
            return

        strategy_data = result_obj["strategy"]

        strat_id = strategy_data.get("strategy_id", "unknown")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            f"Save Strategy #{strat_id}",
            str(Path(get_certus_last_dir() or ".") / f"strategy_{strat_id}.json"),
            "JSON Files (*.json)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(strategy_data, f, indent=4, default=numpy_encoder)

                logging.getLogger("ThinFilm").info(f"✓ Strategy #{strat_id} saved to {filename}")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error saving strategy: {e}")

    def handle_export_csv(self) -> None:

        max_blocks = 0

        if self.strategies_results:
            for res in self.strategies_results:
                n = res["strategy"].get("n_blocks", 0)

                if n > max_blocks:
                    max_blocks = n

        self.export_csv(self.strategies_results, max_blocks)

    def export_csv(self, strategies_results, max_blocks) -> None:


        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Strategies Results",
            str(Path(get_certus_last_dir() or ".") / "strategies_stats.csv"),
            "CSV Files (*.csv)",
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                data = []

                for rank, result in enumerate(strategies_results, 1):
                    strat = result["strategy"]

                    noise_results = result.get("results_per_noise", [])

                    origin = strat.get("origin", "unknown")

                    # Calc Comp.Factor (matches update_data)

                    comp_factor = ""

                    res_1x = next(
                        (r for r in noise_results if abs(r.get("noise_level", 0) - 1.0) < 0.1),
                        None,
                    )

                    if res_1x and self.p_thick_nominal is not None:
                        try:
                            th_data = res_1x.get("thicknesses_all", [])

                            if th_data:
                                mat_sim = np.array(th_data)

                                limit_l = min(mat_sim.shape[1], len(self.p_thick_nominal))

                                diffs = np.abs(mat_sim[:, :limit_l] - self.p_thick_nominal[:limit_l])

                                avg_phys_err = np.mean(diffs)

                                seel_data = APP_CONTEXT.get("seel_data")

                                rmse_val = res_1x.get("rmse_p95", res_1x["rmse_mean"])

                                seel_val = None

                                if seel_data and "fit_alpha" in seel_data:
                                    seel_val = seel_data["fit_k"] * (rmse_val ** seel_data["fit_alpha"])

                                if seel_val and seel_val > 1e-9:
                                    comp_factor = f"{avg_phys_err / seel_val:.4f}"

                        except (KeyError, TypeError, ZeroDivisionError):
                            # Skip if calculation fails

                            pass

                    row = {
                        "Rank": rank,
                        "Strategy_ID": strat["strategy_id"],
                        "Origin": origin.upper(),
                        "Min_Resolution_nm": result.get("min_resolution", ""),
                        "Limiting_Layer": result.get("limiting_layer", ""),
                        "Thickness_Rank": strat.get("thickness_rank", ""),
                        "Spectral_Rank": strat.get("spectral_rank", ""),
                        "Blocks": strat["n_blocks"],
                        "Wavelength_Changes": strat["n_blocks"] - 1,
                        "Unique_Wavelengths": result.get("num_unique_wavelengths", 0),
                        # “Complexity” REMOVED
                        "Robustness_Score": f"{result['robustness_score']:.6f}",
                        "Symmetry_Score_0_100": f"{float(strat.get('symmetry_score_pct', result.get('symmetry_score_pct', 0.0))):.1f}",
                        "Compensation_Error_Factor": comp_factor,
                    }

                    for idx, noise_res in enumerate(noise_results):
                        row[f"Noise_{idx}_Level_%"] = noise_res["noise_level"]

                        row[f"Noise_{idx}_RMSE_P95"] = f"{noise_res.get('rmse_p95', noise_res['rmse_mean']):.6f}"

                        if self.include_secondary_rmse_stats:
                            row[f"Noise_{idx}_RMSE_Mean"] = f"{noise_res['rmse_mean']:.6f}"

                            row[f"Noise_{idx}_RMSE_Std"] = f"{noise_res['rmse_std']:.6f}"

                    blocks = strat.get("blocks", [])

                    for i in range(max_blocks):
                        key = f"Block_{i + 1}"

                        if i < len(blocks):
                            b = blocks[i]

                            row[key] = f"{b['wavelength']:.0f}nm (L{b['start'] + 1}->L{b['end']})"

                        else:
                            row[key] = ""

                    worst_layers = self._calculate_worst_layers(result, top_k=10)

                    for i, txt in enumerate(worst_layers):
                        row[f"Worst_Err_P95_{i + 1}"] = txt

                    data.append(row)

                # to_csv_robust: handles commas

                to_csv_robust(pd.DataFrame(data), filename, index=False)

                logging.getLogger("ThinFilm").info(f"✓ Strategies results exported to '{filename}'")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.getLogger("ThinFilm").error(f"✗ Error exporting CSV: {e}")

# === WORKER SIGNALS ===

class WorkerSignals(QObject):
    finished = pyqtSignal(object)

    error = pyqtSignal(tuple)

    progress = pyqtSignal(int, str)

    plot = pyqtSignal(object, str)

    excel_ready = pyqtSignal(object, object)  # (BytesIO, metadata)

    show_strategies_table = pyqtSignal(object)

    update_stats = pyqtSignal(str, int)

    update_live_growth = pyqtSignal(dict)

# === LOGIC HELPERS ===

def _estimate_fusion_cost_fast(b1, b2, cost_map_sq) -> Any:

    start, end = b1["start"], b2["end"]

    cost = 0.0

    wl = b1["wavelength"]

    for l_idx in range(start, end):
        if l_idx in cost_map_sq and wl in cost_map_sq[l_idx]:
            cost += cost_map_sq[l_idx][wl]

        else:
            cost += 1e6

    return cost

def _find_best_wl_fast(start_layer, end_layer, cost_map_sq) -> Any:

    if start_layer not in cost_map_sq:
        return None

    candidate_wls = list(cost_map_sq[start_layer].keys())[:10]

    best_wl = None

    min_total_cost = float("inf")

    for wl in candidate_wls:
        total_cost = 0.0

        valid = True

        for l_idx in range(start_layer, end_layer):
            if l_idx in cost_map_sq and wl in cost_map_sq[l_idx]:
                total_cost += cost_map_sq[l_idx][wl]

            else:
                valid = False

                break

        if valid and total_cost < min_total_cost:
            min_total_cost = total_cost

            best_wl = wl

    return best_wl

def derive_strategies_exhaustive(
    high_complexity_results: list[dict[str, Any]],
    cost_map_sq: dict[int, dict[float, float]],
    top_k_parents: int = 15,
    max_fusions_per_parent: int = 5,
) -> list[dict[str, Any]]:

    derived_strategies = []

    _derive_next_id = [0]  # monotonic counter to avoid strategy_id collisions

    parents = sorted(high_complexity_results, key=lambda x: x["robustness_score"])[:top_k_parents]

    seen_signatures = set()

    for res in parents:
        parent_strat = res["strategy"]

        blocks = parent_strat["blocks"]

        n_blocks = len(blocks)

        if n_blocks <= 1:
            continue

        fusion_candidates = []

        for i in range(n_blocks - 1):
            b1, b2 = blocks[i], blocks[i + 1]

            cost_est = _estimate_fusion_cost_fast(b1, b2, cost_map_sq)

            fusion_candidates.append({"index": i, "cost": cost_est, "b1": b1, "b2": b2})

        fusion_candidates.sort(key=lambda x: x["cost"])

        best_fusions = fusion_candidates[:max_fusions_per_parent]

        for fusion in best_fusions:
            i = fusion["index"]

            b1, b2 = fusion["b1"], fusion["b2"]

            candidate_wls = {float(b1["wavelength"]), float(b2["wavelength"])}

            best_theo = _find_best_wl_fast(b1["start"], b2["end"], cost_map_sq)

            if best_theo:
                candidate_wls.add(float(best_theo))

            for wl in sorted(candidate_wls):
                new_blocks_struct = []

                new_blocks_struct.extend(blocks[:i])

                new_blocks_struct.append(
                    {
                        "start": b1["start"],
                        "end": b2["end"],
                        "wavelength": float(wl),
                        "num_layers": b2["end"] - b1["start"],
                    }
                )

                new_blocks_struct.extend(blocks[i + 2 :])

                sig = tuple((b["start"], b["end"], b["wavelength"]) for b in new_blocks_struct)

                if sig not in seen_signatures:
                    seen_signatures.add(sig)

                    _derive_next_id[0] += 1

                    new_id = 900_000_000 + _derive_next_id[0]

                    parent_origin = str(parent_strat.get("origin", "UNKNOWN")).upper()

                    if "SYM" in parent_origin:
                        merge_origin = "SMART_MERGE_SYM"

                    elif "THICKNESS²" in parent_origin or "THICKNESS2" in parent_origin:
                        merge_origin = "SMART_MERGE_THICKNESS2"

                    elif "THICKNESS" in parent_origin:
                        merge_origin = "SMART_MERGE_THICKNESS"

                    else:
                        merge_origin = "SMART_MERGE_MIXED"

                    derived_strategies.append(
                        {
                            "strategy_id": new_id,
                            "n_blocks": n_blocks - 1,
                            "blocks": new_blocks_struct,
                            "origin": f"{merge_origin} (from ID {parent_strat['strategy_id']})",
                            "origin_details": (
                                f"{merge_origin} from {parent_origin} (parent ID {parent_strat['strategy_id']})"
                            ),
                            "avg_rmse_nominal": 0.0,
                            "num_unique_wavelengths": len(set(b["wavelength"] for b in new_blocks_struct)),
                        }
                    )

    return derived_strategies

def find_robust_nucleation_wavelength_adaptive(
    params: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: dict[float, dict[str, complex]],
    max_layers_nucleation: int = 8,
    mc_runs: int = 30,
) -> tuple[float, int]:

    logger = params.get("logger")

    if logger:
        logger.info(
            f"🔎 SMART NUCLEATION (Adaptive): Analyzing signal stability up to layer {max_layers_nucleation}..."
        )

    offset_val = compute_probe_offset_nm_from_ratio(params)

    noise_pct = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    robustness_seed = int(params.get("robustness_seed", 42))

    factor_val = float(params.get("non_monotonic_error_factor", 2.0))

    # STRAT policy: gaussian only. Kernel flag is still passed explicitly

    # to make intent unambiguous at call site.

    use_gaussian = True

    nm_mode = params.get("non_monotonic_mode", NON_MONOTONIC_MODE_ATTENUATE)

    p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)

    scan_wl_range = arange_inclusive(
        float(params["scan_wl_min"]),
        float(params["scan_wl_max"]),
        float(params["scan_wl_step"]) * 2.0,
    )

    valid_candidates = [wl for wl in scan_wl_range if wl > 150.0]

    MAX_RMSE_PER_LAYER_NM = float(params.get("nucleation_max_rmse", 1.5))

    DEGRADATION_THRESHOLD = float(params.get("nucleation_degradation", 1.4))

    best_wl_global = float(params["l0"])

    min_size = 2

    # Phase 1: Parallel Pre-ranking of all candidates (Top 10)

    # [FIX 2026] Handle SharedIndicesWorker gracefully

    idx_dict = _IdxWrapper(clues_at_wl)

    candidates_to_test = np.array([wl for wl in valid_candidates if wl in idx_dict], dtype=np.float64)

    if len(candidates_to_test) == 0:
        return best_wl_global, 0

    # Index sampling

    # We build an array of (Nx, 3) where columns are [H, L, Sub]

    nH_pre = np.array([idx_dict[w]["H"] for w in candidates_to_test], dtype=np.complex128)

    nL_pre = np.array([idx_dict[w]["L"] for w in candidates_to_test], dtype=np.complex128)

    nSub_pre = np.array([idx_dict[w]["substrate"] for w in candidates_to_test], dtype=np.complex128)

    pre_scores = rank_nucleation_candidates_kernel(
        candidates_to_test,
        p_thick_arr,
        nH_pre,
        nL_pre,
        nSub_pre,
        noise_pct,
        offset_val,
        factor_val,
        min_size,
        10,
        use_gaussian,
        nm_mode,
        robustness_seed,
    )

    # Sort and pick top 10

    sorted_idx = np.argsort(pre_scores)

    top_candidates = candidates_to_test[sorted_idx[:10]]

    if len(top_candidates) == 0:
        return best_wl_global, 0

    # --- Parallel Adaptive Nucleation Kernel (Phase 2: Depth check) ---

    cand_arr = np.array(top_candidates, dtype=np.float64)

    # [FIX 2026] Complex clues for coherence with Phase B (absorption in trigger sim)

    nH_arr = np.array([idx_dict[w]["H"] for w in top_candidates], dtype=np.complex128)

    nL_arr = np.array([idx_dict[w]["L"] for w in top_candidates], dtype=np.complex128)

    nSub_arr = np.array([idx_dict[w]["substrate"] for w in top_candidates], dtype=np.complex128)

    sizes, rmses = find_nucleation_adaptive_kernel(
        cand_arr,
        p_thick_arr,
        nH_arr,
        nL_arr,
        nSub_arr,
        noise_pct,
        offset_val,
        factor_val,
        min_size,
        max_layers_nucleation,
        mc_runs,
        DEGRADATION_THRESHOLD,
        MAX_RMSE_PER_LAYER_NM,
        use_gaussian,
        nm_mode,
        robustness_seed,
    )

    final_results = []

    for i, wl in enumerate(top_candidates):
        final_results.append({"wl": wl, "size": int(sizes[i]), "rmse": float(rmses[i])})

    if not final_results:
        return top_candidates[0], min_size

    # P2-M2 FIX: adaptive epsilon based on candidate RMSE distribution.
    # Hardcoded 0.1 made scoring insensitive when RMSE << 0.1.
    _rmse_arr = np.array([r["rmse"] for r in final_results], dtype=np.float64)
    _eps = float(np.clip(np.median(_rmse_arr[_rmse_arr > 0]) * 0.1 if np.any(_rmse_arr > 0) else 0.1, 1e-4, 0.1))

    def score_block(item) -> Any:

        return (item["size"] ** 1.5) / (item["rmse"] + _eps)

    final_results.sort(key=score_block, reverse=True)

    winner = final_results[0]

    if logger:
        logger.info(
            f"   🏆 Best Adaptive Nucleation: {winner['wl']:.1f} nm | Locked Layers: 1 to {winner['size']} | Avg RMSE: {winner['rmse']:.4f} nm"
        )

    return winner["wl"], winner["size"]

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# === WORKER LOGIC ===

def _parallel_block_worker(args) -> dict:
    """Worker function for the ProcessPoolExecutor - corrected version substrate."""

    import gc  # Import at function start for finally block

    (
        n_blk,
        pre_calc_data,
        params,
        n_screen,
        k_keep,
        n_full,
        inherited_strategies,
        nucleation_info,
    ) = args

    shared_clues = None

    local_materials_db = None

    logger = logging.getLogger(f"W{n_blk}")

    logger.setLevel(logging.INFO)

    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()

        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"))

        logger.addHandler(handler)

    params["logger"] = logger

    try:
        # Connection to shared memory

        if "shared_clues_info" in pre_calc_data:
            try:
                # IMPORTANT: Instantiate Worker to reconnect to SHM

                shared_clues = SharedIndicesWorker(pre_calc_data["shared_clues_info"])

                # Replace dict with SharedIndicesWorker

                pre_calc_data["clues_at_wl"] = shared_clues

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logger.warning(f"[Block {n_blk}] SharedMemory (Hints) reconnection failed:{e}")

        shared_matrix_worker = None

        if "shared_matrix_info" in pre_calc_data:
            try:
                shared_matrix_worker = SharedArrayWorker(pre_calc_data["shared_matrix_info"])

                pre_calc_data["nominal_matrix_cache"] = shared_matrix_worker.get_array()

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logger.warning(f"[Block {n_blk}] SharedMemory (Matrix) reconnection failed: {e}")

        if "materials_data" in pre_calc_data and pre_calc_data["materials_data"]:
            local_materials_db = MaterialDatabase(filepath="")

            local_materials_db._data = pre_calc_data["materials_data"]

            params["materials_db_instance"] = local_materials_db

        # Get live_queue from StratContext (initialized via _worker_init)

        ctx = StratContext.get_current()

        live_queue = ctx.live_queue if ctx else None

        gc.collect()

        # Debug tracing (logger.debug instead of print)

        logger.debug(
            f"[W{n_blk}] raw_results_thickness keys: {list(pre_calc_data['raw_results_thickness'].keys())[:5]}..."
        )

        logger.debug(f"[W{n_blk}] raw_results_sq keys: {list(pre_calc_data['raw_results_sq'].keys())[:5]}...")

        logger.debug(f"[W{n_blk}] num_layers: {pre_calc_data['num_layers']}")

        sample_layer = (
            list(pre_calc_data["raw_results_thickness"].keys())[0] if pre_calc_data["raw_results_thickness"] else -1
        )

        if sample_layer >= 0:
            sample_data = pre_calc_data["raw_results_thickness"][sample_layer][:3]

            logger.debug(f"[W{n_blk}] Layer {sample_layer} sample: {sample_data}")

        sym_enable = bool(params.get("sym_enable", True))

        sym_bonus_map = pre_calc_data.get("sym_bonus_map", {})

        sym_layer_importance = pre_calc_data.get("sym_layer_importance", {})

        if sym_enable and not sym_bonus_map:
            sym_bonus_map = _build_symmetry_bonus_map(
                pre_calc_data["raw_results_thickness"],
                pre_calc_data["num_layers"],
                float(params.get("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT)),
            )

        if sym_enable and not sym_layer_importance:
            sym_layer_importance = _build_layer_importance_map(
                pre_calc_data["raw_results_thickness"],
                pre_calc_data["num_layers"],
            )

        strategies_dp = mine_strategies_for_block_count(
            n_blk,
            pre_calc_data["raw_results_thickness"],
            pre_calc_data["raw_results_sq"],
            pre_calc_data["num_layers"],
            top_k=40,
            force_monolayer=params.get("force_first_layer_same_wl", False),
            nucleation_wl=nucleation_info.get("wl"),
            nucleation_size=nucleation_info.get("size", 0),
            candidate_limit=int(params.get("mining_candidates_limit", 3000)),
            sym_enable=sym_enable,
            sym_bonus_map=sym_bonus_map,
            layer_importance_map=sym_layer_importance,
            sym_weight=float(params.get("sym_weight", SYM_DEFAULT_WEIGHT)),
            sym_same_wl_bonus=float(params.get("sym_same_wl_bonus", SYM_DEFAULT_SAME_WL_BONUS)),
            sym_continuity_weight=float(params.get("sym_continuity_weight", SYM_DEFAULT_CONTINUITY_WEIGHT)),
            sym_adaptive_same_wl=bool(params.get("sym_adaptive_same_wl", True)),
            sym_scoring_mode=str(params.get("sym_scoring_mode", SYM_DEFAULT_SCORING_MODE)),
            sym_allow_hybrid=bool(params.get("sym_allow_hybrid", False)),
        )

        logger.debug(f"[W{n_blk}] mine_strategies_for_block_count returned {len(strategies_dp)} strategies")

        if not strategies_dp:
            logger.info(f"   [Block {n_blk}] Mining returned 0 strategies.")

            return {"n_blk": n_blk, "strategies_results": [], "live_preview": None}

        logger.info(f"   [Block {n_blk}] Mining found {len(strategies_dp)} strategies.")

        _emit_stat("MS", len(strategies_dp))

        # Screening DP

        survivors_dp = []

        if strategies_dp:
            screen_context_dp = pre_calc_data.copy()

            screen_context_dp["all_strategies"] = strategies_dp

            logger.info(f"   [Block {n_blk}] Running screening on {len(strategies_dp)} strategies...")

            res_dp = run_final_simulation_block(screen_context_dp, params, num_runs=n_screen)

            if "all_strategies_results" in res_dp:
                results_list = res_dp["all_strategies_results"]

                logger.info(f"   [Block {n_blk}] Screening complete. Results count: {len(results_list)}")

                survivors_dp = sorted(results_list, key=lambda x: x["robustness_score"])[:k_keep]

        # Inherited Screening

        survivors_inherited = []

        if inherited_strategies:
            valid_inherited = []

            for s in inherited_strategies:
                if s.get("n_blocks") != n_blk:
                    continue

                ok, _ = _validate_strategy_blocks_contract(s, pre_calc_data["num_layers"], expected_n_blocks=n_blk)

                if ok:
                    valid_inherited.append(s)

            if valid_inherited:
                _emit_stat("MS", len(valid_inherited))

                screen_context_inh = pre_calc_data.copy()

                screen_context_inh["all_strategies"] = valid_inherited

                res_inh = run_final_simulation_block(screen_context_inh, params, num_runs=n_screen)

                if "all_strategies_results" in res_inh:
                    survivors_inherited = sorted(
                        res_inh["all_strategies_results"],
                        key=lambda x: x["robustness_score"],
                    )[:k_keep]

        unique_survivors = []

        seen_signatures = set()

        for res in survivors_dp + survivors_inherited:
            strat = res.get("strategy", {})

            sig = _strategy_signature(strat)

            if sig not in seen_signatures:
                unique_survivors.append(res)

                seen_signatures.add(sig)

        final_results = unique_survivors

        if unique_survivors:
            # Mandatory confirmation pass on survivors with full MC budget.

            final_context = pre_calc_data.copy()

            final_context["all_strategies"] = [r["strategy"] for r in unique_survivors]

            logger.info(
                f"   [Block {n_blk}] Full pass on {len(final_context['all_strategies'])} survivors (n_full={n_full})..."
            )

            final_run = run_final_simulation_block(
                final_context,
                params,
                num_runs=max(int(n_full), int(n_screen)),
            )

            final_results = final_run.get("all_strategies_results", [])

        if live_queue and final_results:
            best_final = min(final_results, key=lambda x: x["robustness_score"])

            try:
                live_queue.put(
                    {
                        "strategy": best_final["strategy"],
                        "robustness_score": best_final["robustness_score"],
                    }
                )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logger.error(f"[Worker {n_blk}] Failed to put into live_queue: {e}")

        return {
            "n_blk": n_blk,
            "strategies_results": final_results,
            "live_preview": None,
        }

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logger.error(f"Critical error in parallel worker for block {n_blk}: {traceback.format_exc()}")

        return {"n_blk": n_blk, "error": str(e), "strategies_results": []}

    finally:
        if shared_clues:
            try:
                shared_clues.close()

            except (OSError, AttributeError):
                # Shared memory may already be closed

                pass

        if shared_matrix_worker:
            try:
                shared_matrix_worker.close()

            except (OSError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        _flush_sp_stats()

        gc.collect()

class WorkerThread(QThread):
    def __init__(
        self,
        step: int | WorkerThreadRequest,
        params: dict[str, Any] | None = None,
        opti_results: dict[str, Any] | None = None,
        timing_logger=None,
    ) -> None:

        super().__init__()

        # Track C: Headless service for STRAT strategy
        self._service = StratStrategyService(runner=lambda cfg: None)

        self.request = (
            step
            if isinstance(step, WorkerThreadRequest)
            else WorkerThreadRequest.from_legacy(
                step=step,
                params=params,
                opti_results=opti_results,
                timing_logger=timing_logger,
            )
        )

        # Keep legacy fields for incremental migration across call sites.
        self.step = int(self.request.step)

        self.params = dict(self.request.params)

        self.opti_results = (
            dict(self.request.opti_results)
            if isinstance(self.request.opti_results, dict)
            else self.request.opti_results
        )

        self.timing_logger = self.request.timing_logger

        self.signals = WorkerSignals()

    def run(self) -> None:

        try:
            # Track C: Service-side validation (headless bridge)
            self._service.validate_payload(
                {
                    "step": self.request.step,
                    "params": self.request.params,
                    "opti_results": self.request.opti_results,
                },
                materials_db=APP_CONTEXT.get("materials_db"),
            )

            if self.step in [2, 3, 23, 33]:
                self._run_step_0_auto()

            if self.step == 0:
                self._run_step_0()

            elif self.step == 2:
                self._run_step_2()

            elif self.step == 3:
                self._run_step_3()

            elif self.step == 23:
                self._run_step_23_full()

            elif self.step == 33:
                self._run_step_external_strategies()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.signals.error.emit((type(e), e, e.__traceback__))

            self.params["logger"].error(traceback.format_exc())

    def _run_step_0(self) -> None:
        """

        Execute Step 1: Nominal Calculation & Sensitivity Check.

        This method performs initial analysis including:

        - Nominal property calculation for the design

        - Sensitivity matrix computation

        - SEEL analysis for error estimation

        - Visualization of results and stack structure

        Args:

            self: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Emits plot signals for visualization

            - Calculates sensitivity for robustness analysis

            - Stores SEEL data in application context

        """

        self.params["logger"].info("--- STEP 1: NOMINAL CALCULATION & SENSITIVITY CHECK ---")

        # Track C: Orchestrate Step 0 via headless service
        res = self._service.run_step_0(self.params, materials_db=APP_CONTEXT.get("materials_db"))
        nominal_results = res["nominal_results"]
        multipliers = res["multipliers"]
        sensitivity_data = res["sensitivity_data"]
        seel_data = res["seel_data"]

        APP_CONTEXT["seel_data"] = seel_data

        if self.params.get("show_plots", True):
            self.signals.plot.emit(sensitivity_data, "sensitivity_popup")

            stack_data = {
                "p_thick": nominal_results["physical_thicknesses_nominal"],
                "multipliers": multipliers,
                "nSub_id": self.params.get("nSub_id"),
            }

            self.signals.plot.emit(stack_data, "stack_visual")

            self.signals.plot.emit(seel_data, "seel_analysis_plot")

        self.signals.finished.emit(
            WorkerThreadResult.for_step_0(
                nominal_results=nominal_results,
                seel_data=seel_data,
            ).to_legacy_dict()
        )

    def _run_step_0_auto(self) -> None:
        """

        Execute Auto-Step 1: Nominal Calculation & Sensitivity Check.

        This method performs the same analysis as _run_step_0 but in automatic mode:

        - Nominal property calculation for the design

        - Sensitivity matrix computation

        - SEEL analysis for error estimation

        - Automatic workflow progression

        Args:

            self: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Used in automatic workflow sequences

            - Prerequisite for steps 2, 3, 23, 33

            - Stores results for subsequent steps

        """

        self.params["logger"].info("--- AUTO-STEP 1: NOMINAL CALCULATION & SENSITIVITY CHECK ---")

        # Track C: Orchestrate Step 0 via headless service
        res = self._service.run_step_0(self.params, materials_db=APP_CONTEXT.get("materials_db"))
        nominal_results = res["nominal_results"]
        multipliers = res["multipliers"]
        sensitivity_data = res["sensitivity_data"]
        seel_data = res["seel_data"]

        APP_CONTEXT["seel_data"] = seel_data

        local_db = self.params.get("materials_db") or APP_CONTEXT.get("materials_db")

        wl_clues = nominal_results["wavelengths"]

        try:
            nH_curve = get_refractive_clues_vectorized(self.params["nH_id"], wl_clues, db_instance=local_db)

            nL_curve = get_refractive_clues_vectorized(self.params["nL_id"], wl_clues, db_instance=local_db)

            clues_data_packet = {
                "wavelengths": wl_clues,
                "nH": nH_curve,
                "nL": nL_curve,
            }

            self.signals.plot.emit(clues_data_packet, "clues_check_plot")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.params["logger"].warning(f"Could not generate index check plot: {e}")

        if self.params.get("show_plots", True):
            self.signals.plot.emit(sensitivity_data, "sensitivity_popup")

            stack_data = {
                "p_thick": nominal_results["physical_thicknesses_nominal"],
                "multipliers": multipliers,
                "nSub_id": self.params.get("nSub_id"),
            }

            self.signals.plot.emit(stack_data, "stack_visual")

            self.signals.plot.emit(seel_data, "seel_analysis_plot")

        self.params["logger"].info("✓ Step 1 (Auto + Sensitivity) complete (prerequisite)\n")

    def _run_step_2(self) -> None:
        """

        Execute Step 2: Optimized Hybrid Strategy.

        This method performs the hybrid optimization strategy including:

        - Block strategy optimization using hybrid algorithms

        - Performance metrics calculation and analysis

        - Result visualization and plotting

        - Progress tracking and timing measurement

        Args:

            self: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes timing measurement

            - Emits progress and plot signals

            - Handles optimization result processing

        """

        if self.timing_logger:
            self.timing_logger.start("Step 2: Optimized Hybrid Strategy")

        opti_results = optimize_block_strategy_hybrid(self.params, self.signals.progress, self.signals.plot)

        if self.params.get("show_plots", True) and "raw_results_thickness" in opti_results:
            self.signals.plot.emit(opti_results["raw_results_thickness"], "pyqtgraph_heatmap")

        if self.timing_logger:
            self.timing_logger.end("Step 2: Optimized Hybrid Strategy")

        self.signals.finished.emit(WorkerThreadResult.for_step_2(opti_results=opti_results).to_legacy_dict())

    def _run_step_3(self) -> None:
        """Execute Step 3: Robustness Test.

        This method performs robustness testing including:

        - Final simulation runs with noise variations

        - Statistical analysis of performance

        - Results aggregation and processing

        - Excel export and visualization

        Args:

            self: WorkerThread instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes timing measurement

            - Emits progress and plot signals

            - Requires Step 2 completion"""

        if not self.opti_results:
            raise RuntimeError("Step 2 must be completed before Step 3")

        if self.timing_logger:
            self.timing_logger.start("Step 3: Robustness Test")

        num_runs = int(self.params.get("robustness_num_runs", 150))

        final_results = run_final_simulation_block(self.opti_results, self.params, num_runs)

        if "all_strategies_results" in final_results:
            self.signals.show_strategies_table.emit(final_results["all_strategies_results"])

        if self.params.get("export_excel", True):
            nominal_results, _ = calculate_nominal_properties(self.params)

            excel_data = generate_excel_report(nominal_results, self.opti_results, final_results, self.params)

            # Prepare metadata for auto-naming and HTML

            metadata = {
                "rmse": float(
                    final_results.get("all_strategies_results", [{}])[0].get(
                        "rmse_p95",
                        final_results.get("all_strategies_results", [{}])[0].get(
                            "rmse_mean",
                            final_results.get("all_strategies_results", [{}])[0].get("rmse", 0.0),
                        ),
                    )
                )
                if final_results.get("all_strategies_results")
                else 0.0,
                "strategies_count": len(final_results.get("all_strategies_results", [])),
                "params": self.params,
                "nominal_results": nominal_results,
                "opti_results": self.opti_results,
            }

            self.signals.excel_ready.emit(excel_data, metadata)

        if self.params.get("show_plots", True):
            if "all_strategies_results" in final_results:
                heatmap_data = self.opti_results.get("raw_results_thickness", None)

                strat_data = {
                    "strategies": final_results["all_strategies_results"],
                    "p_thick_nominal": self.opti_results["p_thick_nominal"],
                    "heatmap_data": heatmap_data,
                }

                self.signals.plot.emit(strat_data, "block_assignments")

            best_noise_results = _get_best_noise_results(final_results, self.params["logger"])

            if best_noise_results is None:
                raise RuntimeError("Cannot retrieve robustness results")

            wavelengths = arange_inclusive(
                self.params["wl_range"][0],
                self.params["wl_range"][1],
                self.params["wl_step"],
            )

            local_db = self.params.get("materials_db_instance")

            nH_arr = get_refractive_clues_vectorized(self.params["nH_id"], wavelengths, db_instance=local_db).astype(
                np.complex128
            )

            nL_arr = get_refractive_clues_vectorized(self.params["nL_id"], wavelengths, db_instance=local_db).astype(
                np.complex128
            )

            nSub_arr = get_refractive_clues_vectorized(
                self.params["nSub_id"], wavelengths, db_instance=local_db
            ).astype(np.complex128)

            _, T_clean_batch = calculate_RT_batch_kernel(
                wavelengths,
                nH_arr,
                nL_arr,
                nSub_arr,
                np.array(self.opti_results["p_thick_nominal"], dtype=np.float64).reshape(1, -1),
            )

            nominal_results_display = {
                "wavelengths": wavelengths,
                "T_spectral_nominal": T_clean_batch[0],
            }

            robust_data_pack = {
                "nominal": nominal_results_display,
                "best_noise": best_noise_results,
                "opti": self.opti_results,
            }

            self.signals.plot.emit(robust_data_pack, "robustness_popout")

        if self.timing_logger:
            self.timing_logger.end("Step 3: Robustness Test")

        self.signals.finished.emit(WorkerThreadResult.for_step_3(final_results=final_results).to_legacy_dict())

    def _run_step_23_full(self) -> None:
        """
        Execute the full optimized workflow in deep exploration mode.

        This method runs the complete optimization workflow including:
        - Multi-process parallel optimization
        - Statistics collection and monitoring
        - Strategy generation and evaluation
        - Robustness testing and validation
        - Results aggregation and analysis
        """

        import multiprocessing as mp

        if self.timing_logger:
            self.timing_logger.start_global("Full Optimized Workflow (Deep Exploration Mode)")

        stats_queue = _init_stats_queue()

        global _GLOBAL_STATS_QUEUE

        _GLOBAL_STATS_QUEUE = stats_queue

        stats_thread = threading.Thread(target=self._stats_consumer_loop, args=(stats_queue,), daemon=True)

        stats_thread.start()

        # UPDATED: Use standard multiprocessing.Queue instead of Manager().Queue()

        live_preview_queue = mp.Queue()

        shm_manager = None

        try:
            pre_calc_data, p_thick_nom, nucleation_info, nominal_res = _run_phase0_and_phaseA(
                params=self.params,
                signals=self.signals,
            )

            num_layers = pre_calc_data["num_layers"]

            blocks_range = _compute_blocks_range_for_params(num_layers, self.params, dense=True)

            n_screen = int(self.params.get("n_screen_runs", 25))

            k_keep = int(self.params.get("k_keep_survivors", 10))

            n_full = int(self.params.get("robustness_num_runs", 150))

            self.params["logger"].info(f"🔄 PHASE B: Deep Exploration ({len(blocks_range)} steps) - HYBRID ENGINE...")

            cost_map_sq_clean = {
                l: {x["wl"]: x["cost"] for x in items} for l, items in pre_calc_data["raw_results_sq"].items()
            }

            materials_db = self.params.get("materials_db") or APP_CONTEXT.get("materials_db")

            # [FIX 2026] Use Context Manager for automatic cleanup

            with (
                SharedIndicesManager(pre_calc_data["clues_at_wl"]) as shm_manager,
                SharedArrayManager(pre_calc_data["nominal_matrix_cache"]) as shm_matrix,
            ):
                minimized_context = {
                    "raw_results_thickness": pre_calc_data["raw_results_thickness"],
                    "raw_results_sq": pre_calc_data["raw_results_sq"],
                    "num_layers": pre_calc_data["num_layers"],
                    "p_thick_nominal": pre_calc_data["p_thick_nominal"],
                    "shared_clues_info": shm_manager.get_context_info(),
                    "shared_matrix_info": shm_matrix.get_context_info(),
                    "all_wls": pre_calc_data["all_wls"],
                    "materials_data": materials_db.data if materials_db else {},
                    "nH_id": self.params["nH_id"],
                    "nL_id": self.params["nL_id"],
                    "nSub_id": self.params["nSub_id"],
                    "l0": self.params["l0"],
                    "sym_bonus_map": pre_calc_data.get("sym_bonus_map", {}),
                    "sym_layer_importance": pre_calc_data.get("sym_layer_importance", {}),
                }

                params_for_pool = {
                    k: v
                    for k, v in self.params.items()
                    if k
                    not in [
                        "logger",
                        "materials_db",
                        "gui_parent",
                        "worker_signals",
                        "materials_db_instance",
                    ]
                }

                accumulated_strategies_results = []


                # Store stop check

                def stop_check():
                    return self.params.get("stop_requested", False)

                monitor_thread = _start_monitor_live_feed_thread(
                    live_preview_queue=live_preview_queue,
                    signals=self.signals,
                    p_thick_nominal=pre_calc_data["p_thick_nominal"],
                    clues_at_wl=pre_calc_data["clues_at_wl"],
                )

                accumulated_strategies_results = _run_phaseB_parallel_execution(
                    blocks_range=blocks_range,
                    minimized_context=minimized_context,
                    params_for_pool=params_for_pool,
                    n_screen=n_screen,
                    k_keep=k_keep,
                    n_full=n_full,
                    nucleation_info=nucleation_info,
                    num_layers=num_layers,
                    cost_map_sq_clean=cost_map_sq_clean,
                    params=self.params,
                    signals=self.signals,
                    dyn_grid=pre_calc_data.get("full_dynamics_grid", {}),
                    stats_queue=stats_queue,
                    live_preview_queue=live_preview_queue,
                )

                live_preview_queue.put("STOP")

                monitor_thread.join()

                self.signals.progress.emit(100, "Finalizing results...")

                import gc
                gc.collect()

                final_result_dict = _finalize_and_export_step_23(
                    accumulated_strategies_results=accumulated_strategies_results,
                    pre_calc_data=pre_calc_data,
                    nominal_res=nominal_res,
                    params=self.params,
                    signals=self.signals,
                    timing_logger=self.timing_logger,
                )
                self.signals.finished.emit(final_result_dict)

        finally:
            if stats_queue:
                stats_queue.put(None)

            if stats_thread.is_alive():
                stats_thread.join()

            _GLOBAL_STATS_QUEUE = None

            import gc
            gc.collect()

    def _stats_consumer_loop(self, stats_queue) -> None:

        while True:
            try:
                item = stats_queue.get()

                if item is None:
                    break

                counter_type, increment = item

                self.signals.update_stats.emit(counter_type, increment)

            except (BrokenPipeError, OSError, ValueError):
                break

    def _run_step_external_strategies(self) -> None:

        self.params["logger"].info("--- STEP 33: EXTERNAL STRATEGIES SIMULATION ---")

        loaded_strategies = self.params.get("loaded_strategies", [])

        if not loaded_strategies:
            raise ValueError("No strategies loaded in params['loaded_strategies']")

        if not self.opti_results:
            nominal_results, _ = calculate_nominal_properties(self.params)

            p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

            clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                self.params, p_thick_nominal, self.params["logger"]
            )

            self.opti_results = {
                "p_thick_nominal": p_thick_nominal,
                "clues_at_wl": clues_at_wl,
                "nominal_matrix_cache": nominal_matrix_cache,
                "all_wls": all_wls,
                "p_thick_nominal": p_thick_nominal,
            }

        sim_context = self.opti_results.copy()

        sim_context["all_strategies"] = loaded_strategies

        num_runs = int(self.params.get("robustness_num_runs", 150))

        self.params["logger"].info(f"🚀 Simulating {len(loaded_strategies)} external strategies ({num_runs} runs)...")

        final_results = run_final_simulation_block(sim_context, self.params, num_runs)

        if "all_strategies_results" in final_results:
            self.signals.show_strategies_table.emit(final_results["all_strategies_results"])

        if self.params.get("export_excel", True):
            nominal_results, _ = calculate_nominal_properties(self.params)

            excel_data = generate_excel_report(nominal_results, sim_context, final_results, self.params)

            # Keep signal contract (excel_data, metadata).

            best_rmse = 0.0

            if "all_strategies_results" in final_results and final_results["all_strategies_results"]:
                best_rmse = float(
                    final_results["all_strategies_results"][0].get(
                        "rmse_p95",
                        final_results["all_strategies_results"][0].get(
                            "rmse_mean",
                            final_results["all_strategies_results"][0].get("rmse", 0.0),
                        ),
                    )
                )

            metadata = {
                "rmse": best_rmse,
                "strategies_count": len(final_results.get("all_strategies_results", [])),
                "params": {k: v for k, v in self.params.items() if k not in ["logger", "materials_db", "clues_at_wl"]},
            }

            self.signals.excel_ready.emit(excel_data, metadata)

        if self.params.get("show_plots", True):
            if "all_strategies_results" in final_results:
                heatmap_data = self.opti_results.get("raw_results_thickness", None)

                strat_data = {
                    "strategies": final_results["all_strategies_results"],
                    "p_thick_nominal": self.opti_results["p_thick_nominal"],
                    "heatmap_data": heatmap_data,
                }

                self.signals.plot.emit(strat_data, "block_assignments")


def _run_phaseB_parallel_execution(
    blocks_range: list[int],
    minimized_context: dict[str, Any],
    params_for_pool: dict[str, Any],
    n_screen: int,
    k_keep: int,
    n_full: int,
    nucleation_info: dict[str, Any],
    num_layers: int,
    cost_map_sq_clean: dict[str, Any],
    params: dict[str, Any],
    signals: Any,
    dyn_grid: dict[str, Any],
    stats_queue: Any,
    live_preview_queue: Any,
) -> list[dict[str, Any]]:
    """Runs Phase B multi-processed parallel exploration."""
    import gc

    accumulated_strategies_results = []
    inherited_strategies = []
    def stop_check():
        return params.get("stop_requested", False)
    max_workers = get_safe_worker_count()
    params["logger"].info(f"   Using {max_workers} parallel workers")

    executor = None
    try:
        executor = ThreadPoolExecutor(
            max_workers=max_workers,
            initializer=_worker_init,
            initargs=(stats_queue, live_preview_queue),
        )
        with executor:
            for i, n_blk in enumerate(blocks_range):
                if stop_check():
                    params["logger"].warning(f"🛑 Stopping Optimization at {n_blk} blocks...")
                    break
                signals.progress.emit(
                    int((i / len(blocks_range)) * 90) + 5,
                    f"Optimizing ({n_blk} blocks) - Gen {i + 1}/{len(blocks_range)}",
                )
                args = (
                    n_blk,
                    minimized_context,
                    params_for_pool,
                    n_screen,
                    k_keep,
                    n_full,
                    inherited_strategies,
                    nucleation_info,
                )
                try:
                    future = executor.submit(_parallel_block_worker, args)
                    result_batch = future.result(timeout=300)

                    if int(result_batch.get("n_blk", n_blk)) != int(n_blk):
                        params["logger"].error(
                            f"    [Block {n_blk}] ❌ Worker returned wrong n_blk={result_batch.get('n_blk')}"
                        )
                        inherited_strategies = []
                        continue

                    if "error" in result_batch and result_batch.get("strategies_results") == []:
                        params["logger"].error(f"    [Block {n_blk}] ❌ Error: {result_batch['error']}")
                        inherited_strategies = []
                    else:
                        strategies_this_step_raw = result_batch.get("strategies_results", [])
                        strategies_this_step = []
                        for s_res in strategies_this_step_raw:
                            s = s_res.get("strategy", {}) if isinstance(s_res, dict) else {}
                            ok, reason = _validate_strategy_blocks_contract(s, num_layers, expected_n_blocks=n_blk)
                            if ok:
                                strategies_this_step.append(s_res)
                            else:
                                params["logger"].warning(
                                    f"    [Block {n_blk}] Dropped invalid strategy payload: {reason}"
                                )

                        accumulated_strategies_results.extend(strategies_this_step)

                        dyn_msg = ""
                        if strategies_this_step:
                            abs_min_dyn = 999.0
                            abs_wl = 0.0
                            abs_layer = 0
                            for s_res in strategies_this_step:
                                wl_per_layer = []
                                for blk in s_res["strategy"].get("blocks", []):
                                    block_layers = int(
                                        blk.get("num_layers", int(blk.get("end", 0)) - int(blk.get("start", 0)))
                                    )
                                    if block_layers <= 0:
                                        continue
                                    wl_per_layer.extend([blk["wavelength"]] * block_layers)
                                for li, wl in enumerate(wl_per_layer):
                                    if li == 0:
                                        continue
                                    d = dyn_grid.get(li, {}).get(float(wl), 0.0)
                                    if d < abs_min_dyn:
                                        abs_min_dyn = d
                                        abs_wl = wl
                                        abs_layer = li + 1
                            if abs_min_dyn < 900:
                                dyn_msg = f" | Min Dyn: {abs_min_dyn:.4f} (@{abs_wl:.0f}nm, L{abs_layer})"

                        params["logger"].info(
                            f"   [Block {n_blk}] Completed. {len(strategies_this_step)} retained{dyn_msg}"
                        )

                        if strategies_this_step:
                            inherited_strategies = derive_strategies_exhaustive(
                                strategies_this_step,
                                cost_map_sq_clean,
                                top_k_parents=int(params.get("top_k_parents", 20)),
                                max_fusions_per_parent=int(params.get("max_fusions_per_parent", 5)),
                            )
                        else:
                            inherited_strategies = []
                        del strategies_this_step
                        gc.collect()

                except concurrent.futures.TimeoutError:
                    params["logger"].error(f"   [Block {n_blk}] ❌ Timeout (>5min)")
                    inherited_strategies = []
                except concurrent.futures.BrokenExecutor as e:
                    params["logger"].error(f"   [Block {n_blk}] ❌ Process pool broken: {e}")
                    inherited_strategies = []
                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    params["logger"].error(f"   [Block {n_blk}] ❌ Error: {e}")
                    inherited_strategies = []
    except NUMERICAL_FAULT_EXCEPTIONS as e:
        params["logger"].error(f"ProcessPoolExecutor error: {e}")
        raise
    finally:
        if executor is not None:
            try:
                executor.shutdown(wait=True)
            except (RuntimeError, AttributeError) as e:
                params["logger"].warning(f"Error shutting down executor: {e}")

    return accumulated_strategies_results

def _finalize_and_export_step_23(
    accumulated_strategies_results: list[dict[str, Any]],
    pre_calc_data: dict[str, Any],
    nominal_res: dict[str, Any],
    params: dict[str, Any],
    signals: Any,
    timing_logger: Any,
) -> dict[str, Any]:
    """Sorts final results, emits plots, triggers Excel export, and returns final payload."""
    if not accumulated_strategies_results:
        raise RuntimeError("No strategies found.")

    accumulated_strategies_results.sort(key=lambda x: x["robustness_score"])

    if timing_logger:
        timing_logger.end_global("STRAT_Workflow")

    signals.show_strategies_table.emit(accumulated_strategies_results)

    best_res = accumulated_strategies_results[0]
    sim_context = pre_calc_data.copy()
    sim_context["blocks"] = best_res["strategy"]["blocks"]
    sim_context["all_strategies"] = [r["strategy"] for r in accumulated_strategies_results]

    final_complete_structure = {
        "results_per_noise": best_res["results_per_noise"],
        "optimal_blocks": best_res["strategy"]["blocks"],
        "best_strategy": best_res["strategy"],
        "all_strategies_results": accumulated_strategies_results,
    }

    if params.get("show_plots", True):
        try:
            heatmap_data = pre_calc_data.get("raw_results_thickness", None)
            strat_data = {
                "strategies": accumulated_strategies_results,
                "p_thick_nominal": pre_calc_data["p_thick_nominal"],
                "heatmap_data": heatmap_data,
            }
            signals.plot.emit(strat_data, "block_assignments")
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            params["logger"].warning(f"Plotting error: {e}")

        best_noise_results = _get_best_noise_results(best_res, params["logger"])
        if best_noise_results:
            wl_arr = arange_inclusive(
                params["wl_range"][0],
                params["wl_range"][1],
                params["wl_step"],
            )
            local_db = params.get("materials_db_instance")
            nH_arr = get_refractive_clues_vectorized(params["nH_id"], wl_arr, db_instance=local_db).astype(
                np.complex128
            )
            nL_arr = get_refractive_clues_vectorized(params["nL_id"], wl_arr, db_instance=local_db).astype(
                np.complex128
            )
            nSub_arr = get_refractive_clues_vectorized(params["nSub_id"], wl_arr, db_instance=local_db).astype(
                np.complex128
            )

            _, T_clean_batch = calculate_RT_batch_kernel(
                wl_arr,
                nH_arr,
                nL_arr,
                nSub_arr,
                np.array(pre_calc_data["p_thick_nominal"], dtype=np.float64).reshape(1, -1),
            )
            nominal_results_display = {
                "wavelengths": wl_arr,
                "T_spectral_nominal": T_clean_batch[0],
            }
            robust_data_pack = {
                "nominal": nominal_results_display,
                "best_noise": best_noise_results,
                "opti": sim_context,
            }
            signals.plot.emit(robust_data_pack, "robustness_popout")

    if params.get("export_excel", True):
        excel_data = generate_excel_report(nominal_res, sim_context, final_complete_structure, params)
        best_rmse = 0.0
        if "all_strategies_results" in final_complete_structure and final_complete_structure["all_strategies_results"]:
            best_rmse = final_complete_structure["all_strategies_results"][0].get("robustness_score", 0.0)
        metadata = {
            "rmse": best_rmse,
            "strategies_count": len(final_complete_structure.get("all_strategies_results", [])),
            "params": {k: v for k, v in params.items() if k not in ["logger", "materials_db", "clues_at_wl"]},
        }
        signals.excel_ready.emit(excel_data, metadata)

    return WorkerThreadResult.for_step_23(
        opti_results=sim_context,
        final_results=final_complete_structure,
    ).to_legacy_dict()

def _run_phase0_and_phaseA(
    params: dict[str, Any],
    signals: Any,
) -> tuple[dict[str, Any], list[float], dict[str, float], dict[str, Any]]:
    """Executes Phase 0 (Nucleation Analysis) and Phase A (Cost Maps)."""

    nominal_res, _ = calculate_nominal_properties(params)
    p_thick_nom = nominal_res["physical_thicknesses_nominal"]

    params["logger"].info("🚀 PHASE 0: Initializing Smart Nucleation Analysis...")
    clues_cache, _, _ = precompute_clues_and_matrices(params, p_thick_nom, params["logger"])
    max_scan_size = min(12, max(2, len(p_thick_nom) // 2))
    mc_runs_nucl = int(params.get("nucleation_mc_runs", 40))

    nucleation_wl, nucleation_size = (
        (float(params["l0"]), 0)
        if len(p_thick_nom) < 3
        else find_robust_nucleation_wavelength_adaptive(
            params,
            p_thick_nom,
            clues_cache,
            max_layers_nucleation=max_scan_size,
            mc_runs=mc_runs_nucl,
        )
    )
    nucleation_info = {"wl": nucleation_wl, "size": nucleation_size}

    params["logger"].info("\n🚀 PHASE A: Calculating Cost Maps...")
    params["p_thick_nominal"] = p_thick_nom
    pre_calc_data = optimize_block_strategy_hybrid(params, signals.progress, None, phase_a_only=True)

    if "error" in pre_calc_data:
        raise RuntimeError(pre_calc_data["error"])

    if params.get("show_plots", True) and "raw_results_thickness" in pre_calc_data:
        signals.plot.emit(pre_calc_data["raw_results_thickness"], "pyqtgraph_heatmap")

    import gc
    gc.collect()
    return pre_calc_data, p_thick_nom, nucleation_info, nominal_res

def _start_monitor_live_feed_thread(
    live_preview_queue: Any,
    signals: Any,
    p_thick_nominal: list[float],
    clues_at_wl: dict[str, Any],
) -> threading.Thread:
    """Starts a daemon thread to consume live preview events and emit plot signals."""

    def monitor_live_feed() -> None:

        last_update = 0.0
        last_full_package = None
        LIVE_REFRESH_INTERVAL = 2.0
        while True:
            try:
                item = None
                try:
                    while not live_preview_queue.empty():
                        item = live_preview_queue.get_nowait()
                except (BrokenPipeError, OSError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
                if item is None:
                    try:
                        item = live_preview_queue.get(timeout=0.5)
                    except (queue.Empty, AttributeError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
                if item == "STOP":
                    break
                now = time.time()
                if item:
                    if now - last_update > 0.4:
                        full_package = {
                            "strategy": item["strategy"],
                            "robustness_score": item["robustness_score"],
                            "p_thick_nominal": p_thick_nominal,
                            "clues_at_wl": clues_at_wl,
                        }
                        last_full_package = full_package
                        signals.update_live_growth.emit(full_package)
                        last_update = now
                elif last_full_package is not None and (now - last_update) >= LIVE_REFRESH_INTERVAL:
                    signals.update_live_growth.emit(last_full_package)
                    last_update = now
            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.error(f"[MonitorThread] Error: {e}")
                break

    monitor_thread = threading.Thread(target=monitor_live_feed, daemon=True)
    monitor_thread.start()
    return monitor_thread




# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# === GUI CLASSES (RECONSTITUTION STYLE VERSION D) ===

class CertusScientificPlot(pg.PlotWidget):
    def __init__(self, parent=None, title="", y_label="", x_label="") -> None:

        super().__init__(parent)

        self.setDownsampling(mode="peak")

        self.setClipToView(True)

        self.showGrid(x=True, y=True, alpha=0.15)



        self.plotItem.setTitle(title, color=CertusTheme.CHART_PRIMARY, size="12pt")

        self.plotItem.setLabels(left=y_label, bottom=x_label)

        axis_pen = pg.mkPen(color="k", width=1)

        self.getAxis("bottom").setPen(axis_pen)

        self.getAxis("left").setPen(axis_pen)

        self.getAxis("bottom").setTextPen("k")

        self.getAxis("left").setTextPen("k")

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=1, style=Qt.PenStyle.DashLine),
        )

        self.hLine = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=1, style=Qt.PenStyle.DashLine),
        )

        self.addItem(self.vLine)

        self.addItem(self.hLine)

        self.info_label = pg.TextItem(anchor=(0, 1), color=CertusTheme.CHART_PRIMARY)

        self.addItem(self.info_label)

        self.proxy = pg.SignalProxy(self.scene().sigMouseMoved, rateLimit=60, slot=self.on_mouse_move)

        self._tracked_curves = []

        self._copy_excel_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)

        self._copy_excel_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._copy_excel_shortcut.activated.connect(self._on_copy_excel_clipboard)

    def _on_copy_excel_clipboard(self) -> None:

        self._copy_excel_tsv(show_message=True)

    def _copy_excel_tsv(self, show_message: bool = True) -> None:

        ok = copy_plot_to_clipboard_excel(self)

        if not show_message:
            return

        parent = self.window() or None
        show_copy_excel_feedback(parent, ok)

    def add_curve_for_tracking(self, curve_item, name) -> None:

        self._tracked_curves.append({"curve": curve_item, "name": name})

    def on_mouse_move(self, evt) -> None:

        pos = evt[0]

        if self.sceneBoundingRect().contains(pos):
            mouse_point = self.plotItem.vb.mapSceneToView(pos)

            x_mouse = mouse_point.x()

            y_mouse = mouse_point.y()

            self.vLine.setPos(x_mouse)

            self.hLine.setPos(y_mouse)

            info_text = [f"x = {x_mouse:.2f}"]

            for item in self._tracked_curves:
                curve = item["curve"]

                x_data, y_data = curve.xData, curve.yData

                if x_data is not None and len(x_data) > 1:
                    if x_mouse < x_data[0] or x_mouse > x_data[-1]:
                        continue

                    idx = np.searchsorted(x_data, x_mouse)

                    if 0 < idx < len(x_data):
                        x0, x1 = x_data[idx - 1], x_data[idx]

                        y0, y1 = y_data[idx - 1], y_data[idx]

                        if x1 != x0:
                            y_val = y0 + (y1 - y0) * (x_mouse - x0) / (x1 - x0)

                            info_text.append(f"{item['name']}: {y_val:.4f}")

            self.info_label.setText("\n".join(info_text))

            self.info_label.setPos(x_mouse, y_mouse)

    def get_toolbar(self, parent_widget) -> Any:

        toolbar = QToolBar(parent_widget)

        toolbar.setStyleSheet(
            f"QToolBar {{ background: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER}; spacing: 5px; }} QToolButton {{ padding: 4px; border-radius:3px; }} QToolButton:hover {{ background-color: {CertusTheme.SURFACE_HOVER}; }}"
        )

        act_reset = QAction("⟲ Reset", parent_widget)

        act_reset.triggered.connect(self.plotItem.autoRange)

        toolbar.addAction(act_reset)

        toolbar.addSeparator()

        act_mode = QAction("✋ Pan/Box", parent_widget)

        act_mode.setCheckable(True)

        act_mode.toggled.connect(self._toggle_mode)

        toolbar.addAction(act_mode)

        toolbar.addSeparator()

        # New Export Menu

        export_btn = QToolButton()

        export_btn.setText("💾 Export")

        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(export_btn)

        act_png = QAction("🖼️ PNG (Image)", parent_widget)

        act_png.triggered.connect(self._export_png)

        menu.addAction(act_png)

        act_svg = QAction("✏️ SVG (Vector)", parent_widget)

        act_svg.triggered.connect(self._export_svg)

        menu.addAction(act_svg)

        act_csv = QAction("📊 CSV (Data)", parent_widget)

        act_csv.triggered.connect(self._export_csv)

        menu.addAction(act_csv)

        act_copy = QAction(CERTUS_UI_STRINGS["copy_excel_tsv"], parent_widget)

        act_copy.setToolTip("Ctrl+Shift+C - TSV pour Excel")

        act_copy.triggered.connect(self._on_copy_excel_clipboard)

        menu.addAction(act_copy)

        export_btn.setMenu(menu)

        toolbar.addWidget(export_btn)

        return toolbar

    def _toggle_mode(self, checked) -> None:

        if checked:
            self.plotItem.vb.setMouseMode(pg.ViewBox.PanMode)

        else:
            self.plotItem.vb.setMouseMode(pg.ViewBox.RectMode)

    def _export_png(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "Export Graph", str(Path(get_certus_last_dir() or ".") / "plot.png"), "PNG Image (*.png)"
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                exporter = ImageExporter(self.plotItem)

                opts = get_export_settings()

                exporter.parameters()["width"] = opts.get("width", 1920)

                if opts.get("height"):
                    exporter.parameters()["height"] = opts["height"]

                exporter.export(filename)

                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.error(f"Export Error:{e}")

                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"PNG : {e}",
                )

    def _export_svg(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "SVG export", str(Path(get_certus_last_dir() or ".") / "plot.svg"), "SVG Files (*.svg)"
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                exporter = SVGExporter(self.plotItem)

                exporter.export(filename)

                QMessageBox.information(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
                )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.error(f"Export Error:{e}")

                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export_failed"],
                    f"SVG : {e}",
                )

    def _export_csv(self) -> None:

        filename, _ = QFileDialog.getSaveFileName(
            None, "Export Data", str(Path(get_certus_last_dir() or ".") / "plot_data.csv"), "CSV Files (*.csv)"
        )

        if not filename:
            return

        set_certus_last_dir(filename)

        try:
            df = plot_dataframe_from_widget(self)

            if df is None or df.empty:
                QMessageBox.warning(
                    self.window() or None,
                    CERTUS_UI_STRINGS["export"],
                    CERTUS_UI_STRINGS["no_data"],
                )

                return

            to_csv_robust(df, filename, index=False)

            QMessageBox.information(
                self.window() or None,
                CERTUS_UI_STRINGS["export"],
                f"{CERTUS_UI_STRINGS['export_ok']} : {Path(filename).name}",
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Export Error:{e}")

            QMessageBox.warning(
                self.window() or None,
                CERTUS_UI_STRINGS["export_failed"],
                f"CSV : {e}",
            )

class UniversalPlotWindow(QMainWindow):
    def __init__(self, parent, data_obj, plot_type) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle("Data Visualization")

        self.resize(1000, 700)

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        if plot_type == "stack_visual":
            self._init_stack_plot(data_obj)

        elif plot_type == "sensitivity_popup":
            self._init_sensitivity_plot(data_obj)

        elif plot_type == "seel_analysis_plot":
            self._init_seel_plot(data_obj)

        elif plot_type == "block_assignments":
            self._init_strategies_plot(data_obj)

        elif plot_type == "robustness_popout":
            self._init_robustness_plot(data_obj)

        elif plot_type == "pyqtgraph_heatmap":
            self._init_heatmap(data_obj)

        else:
            self.layout.addWidget(QLabel(f"Unknown plot type: {plot_type}"))

    def _init_stack_plot(self, data) -> Any:

        self.setWindowTitle("Stack Design Structure")

        p_thick = data.get("p_thick", [])

        multipliers = data.get("multipliers", [])

        if multipliers is None:
            multipliers = [1.0] * len(p_thick)

        if len(multipliers) < len(p_thick):
            multipliers.extend([1.0] * (len(p_thick) - len(multipliers)))

        num_layers = len(p_thick)

        plot = CertusScientificPlot(self, "Stack Design Structure", "Layer Number", "Physical Thickness (nm)")

        plot.showGrid(y=True, x=True, alpha=0.3)

        COLOR_H = QColor(CertusTheme.CHART_PRIMARY)

        COLOR_L = QColor(CertusTheme.CHART_SECONDARY)

        max_thick = max(p_thick) if p_thick else 100.0

        for i in range(num_layers):
            thickness = p_thick[i]

            multiplier = multipliers[i]

            is_H = i % 2 == 0

            bar = QGraphicsRectItem(0, i + 0.1, thickness, 0.8)

            col = COLOR_H if is_H else COLOR_L

            bar.setBrush(pg.mkBrush(col))

            bar.setPen(pg.mkPen("k", width=1))

            plot.addItem(bar)

            label_text = f"{'H' if is_H else 'L'}{i + 1}: {thickness:.1f}nm ({multiplier:.2f}Q)"

            txt = pg.TextItem(label_text, color=CertusTheme.TEXT_SUB, anchor=(0, 0.5))

            txt.setPos(thickness + (max_thick * 0.02), i + 0.5)

            plot.addItem(txt)

        plot.setYRange(0, num_layers + 1)

        plot.setXRange(0, max_thick * 1.3)

        plot.invertY(True)

        def _stack_clipboard_df() -> Any:

            rows = []

            for i in range(num_layers):
                thickness = float(p_thick[i])

                multiplier = float(multipliers[i])

                is_h = i % 2 == 0

                rows.append(
                    {
                        "layer_from_air": i + 1,
                        "material": "H" if is_h else "L",
                        "thickness_nm": thickness,
                        "Q_multiplier": multiplier,
                    }
                )

            return pd.DataFrame(rows)

        plot._certus_clipboard_df_provider = _stack_clipboard_df

        attach_excel_clipboard_context_menu(plot)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_sensitivity_plot(self, data) -> None:

        self.setWindowTitle("Sensitivity Analysis Dashboard")

        wl = data["wavelengths"]

        T_nom = data["T_nominal"]

        envelopes = data["envelopes"]

        sigmas = sorted(envelopes.keys())

        if sigmas:
            sigma_str = ", ".join([str(s) for s in sigmas])

            title = f"Sensitivity Analysis (Noise sigma = {sigma_str} nm)"

        else:
            title = "Sensitivity Analysis"

        plot = CertusScientificPlot(self, title, "Transmission", "Wavelength (nm)")

        nom_curve = plot.plot(
            wl,
            T_nom,
            pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2),
            name="Nominal Target",
        )

        plot.add_curve_for_tracking(nom_curve, "Nominal")

        colors = {
            2.0: (200, 200, 200, 60),
            1.0: (14, 165, 233, 70),
            0.5: (30, 58, 138, 90),
        }

        for sigma in sorted(envelopes.keys(), reverse=True):
            env = envelopes[sigma]

            p5 = env["p5"]

            p95 = env["p95"]

            c_upper = pg.PlotCurveItem(x=wl, y=p95, pen=None)

            c_lower = pg.PlotCurveItem(x=wl, y=p5, pen=None)

            fill_color = colors.get(sigma, (100, 100, 100, 50))

            fill = pg.FillBetweenItem(c_upper, c_lower, brush=pg.mkBrush(fill_color))

            plot.addItem(c_upper)

            plot.addItem(c_lower)

            plot.addItem(fill)

        plot.setYRange(0, 1.05)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_seel_plot(self, data) -> list | None:

        self.setWindowTitle("Statistical Equivalent Error per Layer Analysis")

        self.resize(500, 350)

        sigmas = np.array(data["sigmas"], dtype=np.float64)

        rmses = np.array(data["avg_rmse"], dtype=np.float64)

        # Keep only finite positive values for log-domain plotting.

        valid_mask = np.isfinite(sigmas) & np.isfinite(rmses) & (sigmas > 0.0) & (rmses > 0.0)

        if np.any(valid_mask):
            sigmas = sigmas[valid_mask]

            rmses = rmses[valid_mask]

        else:
            # Defensive fallback to avoid NaN/inf transforms in pyqtgraph.

            sigmas = np.array([1e-3, 1e-2], dtype=np.float64)

            rmses = np.array([1e-3, 1e-2], dtype=np.float64)

        fit_k = data.get("fit_k", 1.0)

        fit_alpha = data.get("fit_alpha", 1.0)

        plot = CertusScientificPlot(
            self,
            "Statistical Equivalent Error per Layer Analysis",
            "SEEL Sigma (nm)",
            "Spectral RMSE",
        )

        plot.setLogMode(x=True, y=True)

        # POLICE REDUITE (6pt)

        font_axis = CertusTheme.get_font(6)

        # --- Helper to generate ticks 1, 2, 3, 4, 5 ---

        def generate_custom_log_ticks(min_val, max_val) -> list | None:

            if min_val <= 0 or max_val <= 0:
                return None

            start_exp = int(np.floor(np.log10(min_val)))

            end_exp = int(np.ceil(np.log10(max_val)))

            major_ticks = []

            for exp in range(start_exp, end_exp + 1):
                base = 10**exp

                # Keep columns 1-5, ignore 6-9

                multipliers = [1, 2, 3, 4, 5]

                for m in multipliers:
                    val = m * base

                    # 20% safety margin for display

                    if val >= min_val * 0.8 and val <= max_val * 1.2:
                        pos_log = np.log10(val)

                        label = f"{val:.10g}"

                        major_ticks.append((pos_log, label))

            return [major_ticks, []]

        # Calculate boundaries

        min_x, max_x = (np.min(rmses), np.max(rmses)) if len(rmses) > 0 else (0.001, 1.0)

        min_y, max_y = (np.min(sigmas), np.max(sigmas)) if len(sigmas) > 0 else (0.01, 10.0)

        # Axe Y (Gauche)

        ay = plot.getAxis("left")

        ay.setTickFont(font_axis)

        ay.setWidth(40)

        ay.setGrid(150)

        custom_ticks_y = generate_custom_log_ticks(min_y, max_y)

        if custom_ticks_y:
            ay.setTicks(custom_ticks_y)

        # Axe X (Bas)

        ax = plot.getAxis("bottom")

        ax.setTickFont(font_axis)

        ax.setHeight(30)

        custom_ticks_x = generate_custom_log_ticks(min_x, max_x)

        if custom_ticks_x:
            ax.setTicks(custom_ticks_x)

        plot.showGrid(x=True, y=True, alpha=0.4)

        # Data: use averages per sigma for consistency with the fit

        sigma_averages = []

        sigma_values = []

        for sigma in np.unique(sigmas):
            mask = sigmas == sigma

            sigma_averages.append(np.mean(rmses[mask]))

            sigma_values.append(sigma)

        plot.plot(
            sigma_averages,
            sigma_values,
            symbol="o",
            symbolSize=5,
            pen=None,
            symbolBrush=CertusTheme.CHART_PRIMARY,
            name="Simulations",
        )

        # Courbe de tendance

        if len(rmses) > 0:
            x_min = float(np.min(rmses))

            x_max = float(np.max(rmses))

            if np.isfinite(x_min) and np.isfinite(x_max) and x_min > 0.0 and x_max > x_min:
                x_fit = np.logspace(np.log10(x_min), np.log10(x_max), 100)

                y_fit = fit_k * (x_fit**fit_alpha)

                y_fit = np.asarray(y_fit, dtype=np.float64)

                fit_mask = np.isfinite(x_fit) & np.isfinite(y_fit) & (y_fit > 0.0)

                if np.any(fit_mask):
                    plot.plot(
                        x_fit[fit_mask],
                        y_fit[fit_mask],
                        pen=pg.mkPen(CertusTheme.CHART_SECONDARY, style=Qt.PenStyle.DotLine, width=2),
                    )

            txt = pg.TextItem(
                f"sigma = {fit_k:.4g}·RMSE^{fit_alpha:.2f}",
                color=CertusTheme.CHART_SECONDARY,
                anchor=(0, 1),
            )

            font_eq = CertusTheme.get_font(9, QFont.Weight.Bold)

            txt.setFont(font_eq)

            txt_x = float(np.min(rmses))

            txt_y = float(np.max(sigmas))

            if np.isfinite(txt_x) and np.isfinite(txt_y) and txt_x > 0.0 and txt_y > 0.0:
                # In log mode, place text using positive data-space coordinates.

                txt.setPos(txt_x, txt_y)

                plot.addItem(txt)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_strategies_plot(self, data) -> None:

        self.setWindowTitle("Optimization Landscape & Strategies")

        strategies = data.get("strategies", [])

        heatmap_data = data.get("heatmap_data")

        win = InteractiveHeatmapWindow(self, heatmap_data if heatmap_data else {})

        plot = win.plot_widget

        colors = CertusTheme.CHART_COLORS

        if strategies:
            best_overall = min(strategies, key=lambda x: x["robustness_score"])

            for idx, res in enumerate(strategies):
                strat = res["strategy"]

                blocks = sorted(strat["blocks"], key=lambda b: b["start"])

                x_vals = []

                y_vals = []

                points_x = []

                points_y = []

                for block in blocks:
                    wl = float(block["wavelength"])

                    start = block["start"]

                    end = block["end"]

                    points_x.extend([start, end])

                    points_y.extend([wl, wl])

                    x_vals.append((start + end) / 2.0)

                    y_vals.append(wl)

                is_winner = res == best_overall

                width = 4 if is_winner else 2

                col = colors[idx % len(colors)]

                pen = pg.mkPen(color=QColor(col), width=width)

                if not is_winner:
                    pen.setStyle(Qt.PenStyle.DashLine)

                plot.plot(points_x, points_y, pen=pen, name=f"Strat {strat['strategy_id']}")

                scatter = pg.ScatterPlotItem(x=x_vals, y=y_vals, size=8, brush=pg.mkBrush(col), pen=pg.mkPen("k"))

                plot.addItem(scatter)

        self.central_widget = win

        self.setCentralWidget(win)

    def _init_robustness_plot(self, data) -> None:

        self.setWindowTitle("Robustness Analysis (Step 3)")

        nominal = data.get("nominal", {})

        best_noise = data.get("best_noise", {})

        wl = nominal.get("wavelengths", [])

        T_nom = nominal.get("T_spectral_nominal", [])

        plot = CertusScientificPlot(self, "Monte Carlo Distribution", "Transmission", "Wavelength (nm)")

        if len(wl) > 0:
            nom_c = plot.plot(
                wl,
                T_nom,
                pen=pg.mkPen(CertusTheme.CHART_DANGER, width=3),
                name="Nominal Target",
            )

            plot.add_curve_for_tracking(nom_c, "Nominal")

            plot.setXRange(wl[0], wl[-1])

            plot.setYRange(0, 1.05)

        rmse = best_noise.get("rmse_p95", best_noise.get("rmse_mean", 0.0))

        noise = best_noise.get("noise_level", 0.0)

        info = pg.TextItem(
            f"Noise: {noise}%\nRMSE P95: {rmse:.5f}",
            color=CertusTheme.CHART_PRIMARY,
            anchor=(0, 0),
        )

        if len(wl) > 0:
            info.setPos(wl[0], 1.0)

        plot.addItem(info)

        self.layout.addWidget(plot.get_toolbar(self))

        self.layout.addWidget(plot)

    def _init_heatmap(self, data) -> None:

        win = InteractiveHeatmapWindow(self, data)

        self.central_widget = win

        self.setCentralWidget(win)

class InteractiveHeatmapWindow(QWidget):  # <--- Changement ici: QWidget au lieu de QMainWindow
    def __init__(self, parent, raw_data_thickness) -> Any:

        super().__init__(parent)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = CertusScientificPlot(self, "Design Heatmap", "Wavelength (nm)", "Layer Number")

        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Ajout du widget au layout

        attach_excel_clipboard_context_menu(self.plot_widget)

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        if not raw_data_thickness:
            return

        self.layers = sorted(raw_data_thickness.keys())

        self.num_layers = len(self.layers)

        all_wls = set()

        for res_list in raw_data_thickness.values():
            for item in res_list:
                all_wls.add(item["wl"])

        self.sorted_wls = sorted(list(all_wls))

        if not self.sorted_wls:
            return

        wl_map = {wl: i for i, wl in enumerate(self.sorted_wls)}

        grid = np.full((self.num_layers, len(self.sorted_wls)), np.nan, dtype=np.float64)

        path_x, path_y = [], []

        for l_idx in self.layers:
            items = raw_data_thickness.get(l_idx, [])

            if items:
                for item in items:
                    w_idx = wl_map.get(item["wl"])

                    if w_idx is not None:
                        grid[l_idx, w_idx] = item["cost"]

                best = min(items, key=lambda x: x["cost"])

                path_x.append(l_idx + 0.5)

                path_y.append(best["wl"])

        grid_filled = np.nan_to_num(grid, nan=np.nanmax(grid))

        valid_mask = np.isfinite(grid) & (grid > 0)

        if valid_mask.any():
            log_vals = np.log10(grid[valid_mask])

            vmin, vmax = np.percentile(log_vals, 2), np.percentile(log_vals, 98)

            denom = vmax - vmin if vmax != vmin else 1.0

            grid_norm = np.clip((np.log10(grid_filled) - vmin) / denom, 0, 1)

        else:
            grid_norm = np.zeros_like(grid)

        self.img_item = pg.ImageItem(grid_norm)

        # Palette de couleurs (Magma-ish)

        pos = np.linspace(0, 1, 5)

        color = np.array(
            [
                [15, 23, 42, 255],
                [60, 20, 80, 255],
                [180, 40, 80, 255],
                [250, 140, 50, 255],
                [252, 250, 230, 255],
            ],
            dtype=np.ubyte,
        )

        cmap = pg.ColorMap(pos, color)

        self.img_item.setLookupTable(cmap.getLookupTable(0.0, 1.0, 256))

        y0 = self.sorted_wls[0]

        y_range = self.sorted_wls[-1] - y0

        y_scale = y_range / len(self.sorted_wls) if len(self.sorted_wls) > 0 else 1.0

        tr = QTransform()

        tr.translate(0, y0)

        tr.scale(1, y_scale)

        self.img_item.setTransform(tr)

        self.plot_widget.addItem(self.img_item)

        if path_x:
            # Step Plot Construction

            step_x, step_y = [], []

            step_x.append(path_x[0])

            step_y.append(path_y[0])

            for i in range(1, len(path_x)):
                step_x.append(path_x[i])

                step_y.append(path_y[i - 1])

                step_x.append(path_x[i])

                step_y.append(path_y[i])

            self.plot_widget.plot(step_x, step_y, pen=pg.mkPen("c", width=3), name="Optimal Strategy")

        self.plot_widget.setXRange(0, self.num_layers)

        self.plot_widget.setYRange(y0, self.sorted_wls[-1])

        def _heatmap_clipboard_df() -> Any:

            rows = []

            for lk in self.layers:
                for j, wl in enumerate(self.sorted_wls):
                    v = float(grid[lk, j])

                    if np.isfinite(v):
                        rows.append(
                            {
                                "layer_key": int(lk),
                                "wavelength_nm": float(wl),
                                "cost": v,
                            }
                        )

            if not rows:
                return None

            return pd.DataFrame(rows)

        self.plot_widget._certus_clipboard_df_provider = _heatmap_clipboard_df

class TransmissionVsThicknessWindow(QMainWindow):
    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        strategy = strategy_result["strategy"]

        self.setWindowTitle(f"Interactive Analysis - Strategy #{strategy['strategy_id']}")

        self.setGeometry(150, 150, 1450, 950)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 5, 15, 5)

        lbl_title = QLabel(f"<b>STRATEGY #{strategy['strategy_id']}</b>")

        lbl_title.setStyleSheet(f"font-size: 16px; color: {CertusTheme.CHART_PRIMARY};")

        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Transmission vs Cumulative Thickness",
            x_label="Cumulative Thickness (nm)",
            y_label="Transmission",
        )

        self.plot_widget.plotItem.setYRange(-0.05, 1.15)

        self.plot_widget.plotItem.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.p1 = self.plot_widget.plotItem

        self.p2 = pg.ViewBox()

        self.p1.scene().addItem(self.p2)

        self.p1.getAxis("right").linkToView(self.p2)

        self.p2.setXLink(self.p1)

        self.p1.getAxis("right").setLabel("Avg Error (nm)", color=CertusTheme.CHART_PURPLE)

        self.p1.getAxis("right").show()

        self.p1.vb.sigResized.connect(self.update_views)

        self._draw_complete_graph(strategy_result, opti_results, params)

        self.update_views()

    def update_views(self) -> None:

        self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        self.p2.linkedViewChanged(self.p1.vb, self.p2.XAxis)

    def _draw_complete_graph(self, strategy_result, opti_results, params) -> Any:

        strategy = strategy_result["strategy"]

        blocks = strategy["blocks"]

        p_thick_nominal = opti_results["p_thick_nominal"]

        if "detailed_growth_data" not in strategy_result:
            num_layers = len(p_thick_nominal)

            p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)

            # [FIX 2026] Complex clues for coherent detailed growth (absorption in TMM)

            layer_wls = np.zeros(num_layers, dtype=np.float64)

            nH_arr = np.zeros(num_layers, dtype=np.complex128)

            nL_arr = np.zeros(num_layers, dtype=np.complex128)

            nSub_arr = np.zeros(num_layers, dtype=np.complex128)

            clues_db = opti_results.get("clues_at_wl", {})

            # [FIX 2026-03] Pass materials_db_instance to resolve dispersive materials

            # at monitoring wavelengths not in clues_db (e.g. 490nm when scan is 1200-1700nm)

            db_instance = params.get("materials_db_instance") or params.get("materials_db")

            # Compute a safe substrate fallback from the known IR wavelengths

            _nSub_fallback = complex(1.52)

            if clues_db:
                _first = next(iter(clues_db.values()))

                _nSub_fallback = complex(_first.get("substrate", 1.52))

                if _nSub_fallback.real < 1.001:
                    _nSub_fallback = complex(1.52)

            for block in blocks:
                wl = float(block["wavelength"])

                if wl not in clues_db:
                    n_h = get_refractive_index(params["nH_id"], wl, db_instance)

                    n_l = get_refractive_index(params["nL_id"], wl, db_instance)

                    n_sub = get_refractive_index(params["nSub_id"], wl, db_instance)

                    idx_data = {"H": n_h, "L": n_l, "substrate": n_sub}

                else:
                    idx_data = clues_db[wl]

                for layer_idx in range(block["start"], block["end"]):
                    if layer_idx < num_layers:
                        layer_wls[layer_idx] = wl

                        nH_arr[layer_idx] = idx_data["H"]

                        nL_arr[layer_idx] = idx_data["L"]

                        n_sub_val = complex(idx_data["substrate"])

                        # [FIX 2026-03] Guard: n_sub < 1.001 is physically impossible

                        # (vacuum/air) and causes T=1.0. Use fallback from IR data.

                        if n_sub_val.real < 1.001:
                            logging.warning(
                                f"[Growth] n_sub={n_sub_val:.4f} at {wl}nm is unphysical "
                                f"(should be >=1.4 for glass). "
                                f"Substituting with IR-range value {_nSub_fallback:.4f}."
                            )

                            n_sub_val = _nSub_fallback

                        nSub_arr[layer_idx] = n_sub_val

            steps_per_layer = np.full(num_layers, 50, dtype=np.int32)

            x_pts, y_pts, bounds = calculate_detailed_growth(
                num_layers,
                p_thick_arr,
                layer_wls,
                nH_arr,
                nL_arr,
                nSub_arr,
                steps_per_layer,
            )

            data = {"x": x_pts, "y": y_pts, "boundaries": bounds}

        else:
            data = strategy_result["detailed_growth_data"]

        x_detailed = np.array(data["x"])

        y_detailed = np.array(data["y"])

        boundaries = np.array(data["boundaries"])

        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1]

            center = (start + end) / 2

            is_H = i % 2 == 0

            color = QColor(255, 240, 240) if is_H else QColor(240, 248, 255)

            rect = pg.QtWidgets.QGraphicsRectItem(start, -0.2, end - start, 2.0)

            rect.setBrush(pg.mkBrush(color))

            rect.setPen(pg.mkPen(None))

            rect.setZValue(-20)

            self.p1.addItem(rect)

            line = pg.InfiniteLine(
                pos=end,
                angle=90,
                pen=pg.mkPen(color=(200, 200, 200), style=Qt.PenStyle.DashLine),
            )

            line.setZValue(-15)

            self.p1.addItem(line)

            text_l = pg.TextItem(f"L{i + 1}", color=(80, 80, 80), anchor=(0.5, 0))

            font = CertusTheme.get_font(weight=QFont.Weight.Bold)

            font.setPointSize(10)

            text_l.setFont(font)

            text_l.setPos(center, 1.08)

            text_l.setZValue(10)

            self.p1.addItem(text_l)

        layer_stats = self._extract_layer_errors(strategy_result, p_thick_nominal)

        bar_x, bar_h, bar_w = [], [], []

        max_err = 0.0

        for i, stats in enumerate(layer_stats):
            if stats:
                start, end = boundaries[i], boundaries[i + 1]

                bar_x.append((start + end) / 2)

                bar_h.append(stats["mean"])

                bar_w.append((end - start) * 0.7)

                if stats["mean"] > max_err:
                    max_err = stats["mean"]

        if bar_x:
            bars = pg.BarGraphItem(
                x=bar_x,
                height=bar_h,
                width=bar_w,
                brush=pg.mkBrush(128, 0, 128, 60),
                pen=pg.mkPen("purple", width=1),
            )

            self.p2.addItem(bars)

            self.p2.setYRange(0, max_err * 3.0 if max_err > 0 else 1.0)

        colors = CertusTheme.CHART_COLORS

        block_start_clues = {b["start"] for b in blocks}

        for idx, block in enumerate(blocks):
            wl = block["wavelength"]

            b_start, b_end = boundaries[block["start"]], boundaries[block["end"]]

            mask = (x_detailed >= b_start - 1e-3) & (x_detailed <= b_end + 1e-3)

            pen_color = colors[idx % len(colors)]

            curve_item = self.p1.plot(
                x_detailed[mask],
                y_detailed[mask],
                pen=pg.mkPen(color=pen_color, width=3),
                name=f"{wl:.0f}nm",
            )

            self.plot_widget.add_curve_for_tracking(curve_item, f"{wl:.0f}nm")

            for l in range(block["start"], block["end"]):
                l_start_thick = boundaries[l]

                l_end_thick = boundaries[l + 1]

                if l in block_start_clues and l > 0:
                    idx_start = np.searchsorted(x_detailed, l_start_thick)

                    idx_start = min(idx_start, len(y_detailed) - 1)

                    t_start_val = y_detailed[idx_start]

                    txt_start = pg.TextItem(
                        f"{t_start_val:.1%}",
                        color=CertusTheme.CHART_PRIMARY,
                        anchor=(0.5, 1),
                    )

                    txt_start.setPos(l_start_thick, t_start_val + 0.02)

                    font_s = CertusTheme.get_font(9, QFont.Weight.Bold)

                    txt_start.setFont(font_s)

                    txt_start.setZValue(25)

                    self.p1.addItem(txt_start)

                    scatter = pg.ScatterPlotItem(
                        [l_start_thick],
                        [t_start_val],
                        size=8,
                        brush=pg.mkBrush(CertusTheme.CHART_PRIMARY),
                        pen=pg.mkPen(None),
                    )

                    scatter.setZValue(25)

                    self.p1.addItem(scatter)

                center = (l_start_thick + l_end_thick) / 2

                txt_wl = pg.TextItem(f"{wl:.0f}", color=pen_color, anchor=(0.5, 0))

                txt_wl.setPos(center, 1.03)

                self.p1.addItem(txt_wl)

                # --- EXTREMA DISTANCES IN HEADER ---

                ext_dists = strategy.get("extrema_distances", [])

                if l < len(ext_dists):
                    d = ext_dists[l]

                    p_s = d.get("prev_start", 999.0)

                    n_s = d.get("next_start", 999.0)

                    p_e = d.get("prev_end", 999.0)

                    n_e = d.get("next_end", 999.0)

                    if p_s < n_s:
                        val_s = p_s

                        sign_s = "-"

                    else:
                        val_s = n_s

                        sign_s = "" if n_s > 15.0 else "+"

                    if p_e < n_e:
                        val_e = p_e

                        sign_e = "-"

                    else:
                        val_e = n_e

                        sign_e = "" if n_e > 15.0 else "+"

                    def _fmt_ot(v, sign) -> Any:

                        return "NC" if v > 15.0 else f"{sign}{v:.1f}"

                    label_start = _fmt_ot(val_s, sign_s)

                    label_end = _fmt_ot(val_e, sign_e)

                    # Color: red if critical (<15), grey if NC

                    color_s = (200, 0, 0) if val_s <= 15.0 else (140, 140, 140)

                    color_e = (200, 0, 0) if val_e <= 15.0 else (140, 140, 140)

                    txt_ext = pg.TextItem(
                        f"{label_start}|{label_end}",
                        color=(max(color_s[0], color_e[0]), min(color_s[1], color_e[1]), min(color_s[2], color_e[2])),
                        anchor=(0.5, 0),
                    )

                    font_ext = CertusTheme.get_font(7, QFont.Weight.Normal)

                    txt_ext.setFont(font_ext)

                    txt_ext.setPos(center, 0.97)

                    txt_ext.setZValue(12)

                    self.p1.addItem(txt_ext)

                idx_end = np.searchsorted(x_detailed, l_end_thick)

                idx_end = min(idx_end, len(y_detailed) - 1)

                t_val = y_detailed[idx_end]

                arrow = pg.ArrowItem(
                    pos=(l_end_thick, t_val),
                    angle=180,
                    tipAngle=30,
                    baseAngle=20,
                    headLen=15,
                    pen={"color": "k", "width": 1},
                    brush="k",
                )

                arrow.setZValue(20)

                self.p1.addItem(arrow)

                txt_pct = pg.TextItem(f"{t_val:.1%}", color="black", anchor=(0, 0.5))

                txt_pct.setPos(l_end_thick + 2, t_val)

                txt_pct.fill = pg.mkBrush(255, 255, 255, 150)

                txt_pct.setZValue(20)

                self.p1.addItem(txt_pct)

    def _extract_layer_errors(self, strategy_result, p_thick_nominal) -> Any:

        num_layers = len(p_thick_nominal)

        layer_stats = [None] * num_layers

        try:
            results_per_noise = strategy_result.get("results_per_noise", [])

            target_idx = 1 if len(results_per_noise) > 1 else 0

            if results_per_noise:
                target_result = results_per_noise[target_idx]

                thicknesses_all = target_result.get("thicknesses_all", [])

                if thicknesses_all:
                    for i_layer in range(num_layers):
                        errors = []

                        for run_stack in thicknesses_all:
                            if len(run_stack) > i_layer:
                                err = abs(run_stack[i_layer] - p_thick_nominal[i_layer])

                                errors.append(err)

                        if errors:
                            layer_stats[i_layer] = {
                                "mean": float(np.mean(errors)),
                                "std": float(np.std(errors)),
                            }

        except (ValueError, TypeError, IndexError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        return layer_stats

class StrategySpectralPerformanceWindow(QMainWindow):
    def __init__(self, parent, strategy_result, opti_results, params) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        strategy_id = strategy_result["strategy"]["strategy_id"]

        self.setWindowTitle(f"Spectral Performance - Strategy #{strategy_id}")

        self.resize(800, 600)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 8, 15, 8)

        lbl = QLabel(f"<b>Spectral Robustness Analysis</b> (Strategy #{strategy_id})")

        lbl.setStyleSheet(f"color: {CertusTheme.CHART_PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Final Spectral Distribution",
            x_label="Wavelength (nm)",
            y_label="Transmission",
        )


        self.plot_widget.addLegend(offset=(30, 30)).setBrush(pg.mkBrush(255, 255, 255, 200))

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._calculate_and_plot(strategy_result, opti_results, params)

    def _calculate_and_plot(self, strategy_result, opti_results, params) -> None:

        try:
            results_list = strategy_result.get("results_per_noise", [])

            target_res = None

            for res in results_list:
                if abs(res.get("noise_level", 0) - 2.0) < 0.1:
                    target_res = res

                    break

            if not target_res and results_list:
                target_res = results_list[0]

            if not target_res:
                return

            thicknesses_all = target_res.get("thicknesses_all", [])

            p_thick_nominal = opti_results["p_thick_nominal"]

            wl_min = float(params["wl_range"][0])

            wl_max = float(params["wl_range"][1])

            wl_step = float(params["wl_step"])

            wls = arange_inclusive(wl_min, wl_max, wl_step)

            nH_id = params["nH_id"]

            nL_id = params["nL_id"]

            nSub_id = params["nSub_id"]

            db_instance = params.get("materials_db_instance")

            nH_arr = get_refractive_clues_vectorized(nH_id, wls, db_instance).astype(np.complex128)

            nL_arr = get_refractive_clues_vectorized(nL_id, wls, db_instance).astype(np.complex128)

            nSub_arr = get_refractive_clues_vectorized(nSub_id, wls, db_instance).astype(np.complex128)

            _, T_clean_batch = calculate_RT_batch_kernel(
                wls,
                nH_arr,
                nL_arr,
                nSub_arr,
                np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1),
            )

            T_nom = T_clean_batch[0]

            T_sim_list = []

            for p_sim in thicknesses_all:
                if len(p_sim) == len(p_thick_nominal):
                    p_arr = np.array(p_sim, dtype=np.float64).reshape(1, -1)

                    _, T_val_batch = calculate_RT_batch_kernel(wls, nH_arr, nL_arr, nSub_arr, p_arr)

                    T_sim_list.append(T_val_batch[0])

            if not T_sim_list:
                return

            arr_sim = np.array(T_sim_list)

            mean = np.mean(arr_sim, axis=0)

            p5 = np.percentile(arr_sim, 5, axis=0)

            p95 = np.percentile(arr_sim, 95, axis=0)

            c_up = pg.PlotCurveItem(x=wls, y=p95, pen=None)

            c_down = pg.PlotCurveItem(x=wls, y=p5, pen=None)

            fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(14, 165, 233, 50))

            fill.setZValue(-10)

            self.plot_widget.addItem(fill)

            self.plot_widget.plot(
                wls,
                mean,
                pen=pg.mkPen(
                    color=CertusTheme.CHART_SECONDARY,
                    width=2,
                    style=Qt.PenStyle.DashLine,
                ),
                name="Mean MC",
            )

            self.plot_widget.plot(
                wls,
                T_nom,
                pen=pg.mkPen(color=CertusTheme.CHART_DANGER, width=2.5),
                name="Nominal Target",
            )

            self.plot_widget.setXRange(wl_min, wl_max)

            self.plot_widget.setYRange(0, 1.0)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Error plotting spectral performance: {e}")

class JsonViewerWindow(QMainWindow):
    def __init__(self, parent, title: str, data: Any) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle(f"Viewer: {title}")

        self.setGeometry(300, 300, 300, 750)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        header_widget = QWidget()

        header_widget.setStyleSheet(
            f"background-color: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};"
        )

        header_layout = QHBoxLayout(header_widget)

        header_layout.setContentsMargins(10, 5, 10, 5)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            header_layout.addWidget(mini_logo)

        else:
            lbl = QLabel("CERTUS")

            lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 16px;")

            header_layout.addWidget(lbl)

        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        self.text_edit = QTextEdit()

        self.text_edit.setReadOnly(True)

        self.text_edit.setStyleSheet(
            f""" QTextEdit {{ background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_MAIN}; font-family: {CertusTheme.FONT_FAMILY}; font-size: 10pt; border: none; padding: 10px; }} """
        )

        try:
            pretty_json = json.dumps(data, indent=4, ensure_ascii=False, default=numpy_encoder)

            self.text_edit.setText(pretty_json)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.text_edit.setText(f"Error parsing JSON data: {e}")

        main_layout.addWidget(self.text_edit)

class InteractiveIndicesWindow(QMainWindow):
    def __init__(self, parent, data_dict) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.nH = np.real(np.array(data_dict["nH"]))

        self.nL = np.real(np.array(data_dict["nL"]))

        self.setWindowTitle("Material Dispersion Check")

        self.resize(600, 400)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setStyleSheet(f"background: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(10, 5, 10, 5)

        lbl = QLabel("<b>Refractive Indices</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 13px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(15)

        def add_legend(color, text) -> None:

            l = QLabel()

            l.setFixedSize(10, 10)

            l.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

            t = QLabel(text)

            t.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            h_layout.addWidget(l)

            h_layout.addWidget(t)

            h_layout.addSpacing(10)

        add_legend(CertusTheme.PRIMARY, "High Index (H)")

        add_legend(CertusTheme.SECONDARY, "Low Index (L)")

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Refractive Index")


        self.plot_widget.addLegend = lambda *args, **kwargs: None

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self.curve_H = self.plot_widget.plot(
            self.wavelengths,
            self.nH,
            pen=pg.mkPen(color=CertusTheme.PRIMARY, width=3),
            name="H",
        )

        self.curve_L = self.plot_widget.plot(
            self.wavelengths,
            self.nL,
            pen=pg.mkPen(color=CertusTheme.SECONDARY, width=3),
            name="L",
        )

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(self.wavelengths[0], self.wavelengths[-1], 0)

            all_n = np.concatenate([self.nH, self.nL])

            y_min, y_max = np.min(all_n), np.max(all_n)

            margin = (y_max - y_min) * 0.1

            self.plot_widget.setYRange(y_min - margin, y_max + margin)

        self.plot_widget.info_label.setVisible(False)

        self.plot_widget.vLine.setVisible(False)

        self.plot_widget.hLine.setVisible(False)

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen("#333", width=1, style=Qt.PenStyle.DashLine),
        )

        self.plot_widget.addItem(self.vLine)

        self.cursor_text = pg.TextItem(anchor=(0, 1), color=CertusTheme.TEXT_MAIN)

        font = CertusTheme.get_font(10)

        font.setBold(True)

        self.cursor_text.setFont(font)

        self.cursor_text.setZValue(100)

        self.plot_widget.addItem(self.cursor_text)

        self.proxy = pg.SignalProxy(
            self.plot_widget.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.update_cursor,
        )

    def update_cursor(self, evt) -> None:

        pos = evt[0]

        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)

        x_mouse = mouse_point.x()

        if x_mouse < self.wavelengths[0] or x_mouse > self.wavelengths[-1]:
            return

        idx = np.searchsorted(self.wavelengths, x_mouse)

        if idx >= len(self.wavelengths):
            idx = len(self.wavelengths) - 1

        wl_val = self.wavelengths[idx]

        val_H = self.nH[idx]

        val_L = self.nL[idx]

        self.vLine.setPos(wl_val)

        content = f"lambda: {int(wl_val)} nm\nnH: {val_H:.3f}\nnL: {val_L:.3f}"

        self.cursor_text.setText(content)

        y_pos = mouse_point.y()

        if x_mouse > (self.wavelengths[-1] - self.wavelengths[0]) * 0.8 + self.wavelengths[0]:
            self.cursor_text.setAnchor((1, 1))

        else:
            self.cursor_text.setAnchor((0, 1))

        self.cursor_text.setPos(x_mouse, y_pos)

class InteractiveSpectrumWindow(QMainWindow):
    def __init__(self, parent, data_dict, sigma=None) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.wavelengths = np.array(data_dict["wavelengths"])

        self.T_nominal = np.array(data_dict["T_nominal"])

        self.T_simulations = data_dict.get("T_simulations", [])

        title = "Monte Carlo Analysis" + (f" (Input Noise sigma={sigma} nm)" if sigma else "")

        self.setWindowTitle(title)

        self.resize(600, 375)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        layout = QVBoxLayout(main_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = QWidget()

        header.setObjectName("Header")

        h_layout = QHBoxLayout(header)

        h_layout.setContentsMargins(15, 10, 15, 10)

        lbl = QLabel("<b>Monte Carlo Reliability Analysis</b>")

        lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-size: 14px;")

        h_layout.addWidget(lbl)

        h_layout.addSpacing(20)

        legend_widget = QWidget()

        legend_layout = QHBoxLayout(legend_widget)

        legend_layout.setContentsMargins(0, 0, 0, 0)

        legend_layout.setSpacing(15)

        def add_legend_item(color, text) -> None:

            lbl_color = QLabel()

            lbl_color.setFixedSize(12, 12)

            lbl_color.setStyleSheet(
                f"background-color: {color}; border-radius: 2px; border: 1px solid {CertusTheme.BORDER};"
            )

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px; font-weight: bold;")

            legend_layout.addWidget(lbl_color)

            legend_layout.addWidget(lbl_txt)

        add_legend_item(CertusTheme.CHART_DANGER, "Nominal Target")

        add_legend_item(CertusTheme.CHART_SECONDARY, "Mean Run")

        add_legend_item("rgba(14, 165, 233, 0.4)", "+/- 1sigma")

        h_layout.addWidget(legend_widget)

        h_layout.addStretch()

        layout.addWidget(header)

        self.plot_widget = CertusScientificPlot(self, title="", x_label="Wavelength (nm)", y_label="Transmission")

        self.plot_widget.addLegend = lambda *args, **kwargs: None



        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        self._plot_data()

    def _plot_data(self) -> None:

        if self.T_simulations and len(self.T_simulations) > 1:
            arr_sim = np.array(self.T_simulations)

            mean = np.mean(arr_sim, axis=0)

            std = np.std(arr_sim, axis=0)

            self._add_corridor(mean, std, 2.0, (14, 165, 233, 50))

            self._add_corridor(mean, std, 1.0, (14, 165, 233, 100))

            mean_curve = self.plot_widget.plot(
                self.wavelengths,
                mean,
                pen=pg.mkPen(color="#0ea5e9", width=2, style=Qt.PenStyle.DashLine),
            )

            mean_curve.setZValue(10)

        curve_nom = self.plot_widget.plot(self.wavelengths, self.T_nominal, pen=pg.mkPen(color="#d62728", width=3))

        curve_nom.setZValue(20)

        self.plot_widget.add_curve_for_tracking(curve_nom, "Nominal")

        if len(self.wavelengths) > 0:
            self.plot_widget.setXRange(float(self.wavelengths[0]), float(self.wavelengths[-1]), 0)

            self.plot_widget.setYRange(-0.05, 1.05)

    def _add_corridor(self, mean, std, factor, color_tuple) -> None:

        upper = mean + factor * std

        lower = mean - factor * std

        c_up = pg.PlotCurveItem(x=self.wavelengths, y=upper, pen=None)

        c_down = pg.PlotCurveItem(x=self.wavelengths, y=lower, pen=None)

        self.plot_widget.addItem(c_up)

        self.plot_widget.addItem(c_down)

        fill = pg.FillBetweenItem(c_up, c_down, brush=pg.mkBrush(color_tuple))

        fill.setZValue(-10)

        self.plot_widget.addItem(fill)

class PopOutWindow(QMainWindow):
    closed_signal = pyqtSignal()

    def __init__(self, widget_to_host, parent=None, title="Detached Window") -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle(title)

        self.setCentralWidget(widget_to_host)

        self.resize(600, 600)

        self.setStyleSheet(f"QMainWindow {{ background-color: {CertusTheme.SURFACE}; }} QWidget {{ font-size: 10pt; }}")

    def closeEvent(self, event) -> None:

        self.closed_signal.emit()

        self.takeCentralWidget()

        super().closeEvent(event)

# QueueHandler and setup_gui_logger are imported from certus_ui

# === OPTIMIZATION: LiveMonitor with Convergence Plot ===

class LiveMonitorWindow(QMainWindow):
    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle("Phase B: Live Growth Monitor")

        self.resize(1200, 600)

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        # Layout principal simple (plus de Splitter)

        self.layout = QVBoxLayout(self.central_widget)

        self.layout.setContentsMargins(0, 0, 0, 0)

        # -- Widget de croissance uniquement --

        self.growth_widget = QWidget()

        growth_layout = QVBoxLayout(self.growth_widget)

        self.header_label = QLabel("Waiting for data...")

        self.header_label.setStyleSheet(
            f"background-color: {CertusTheme.PRIMARY}; color: white; padding: 10px; font-weight: bold; font-size: 14px;"
        )

        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        growth_layout.addWidget(self.header_label)

        self.plot_widget = CertusScientificPlot(
            self,
            title="Optical Thickness vs Transmission",
            x_label="Physical Thickness (nm)",
            y_label="Transmission",
        )



        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        self.plot_widget.setYRange(0, 1.0, 0)

        growth_layout.addWidget(self.plot_widget)

        self.layout.addWidget(self.growth_widget)

        # Plot data

        self.layer_lines = []

        self.block_items = []

        self.curve_segments = []

        self.text_labels = []

        self.user_hidden = False

        self.colors = [
            "#d62728",
            "#2ca02c",
            "#1f77b4",
            "#ff7f0e",
            "#9467bd",
            "#17becf",
            "#e377c2",
            "#bcbd22",
            "#8c564b",
        ]

    def update_monitor(self, x, y, bounds, info_text, strategy_blocks) -> None:

        self.header_label.setText(info_text)

        # Clean Plot

        self.plot_widget.plotItem.clear()

        # Re-add layer lines (they were removed by clear())

        while len(self.layer_lines) < len(bounds):
            line = pg.InfiniteLine(
                angle=90,
                pen=pg.mkPen(color="#94a3b8", style=Qt.PenStyle.DashLine, width=1.5),
            )

            line.setZValue(5)

            self.layer_lines.append(line)

        for i, b in enumerate(bounds):
            if self.layer_lines[i] not in self.plot_widget.plotItem.items:
                self.plot_widget.addItem(self.layer_lines[i])

            self.layer_lines[i].setPos(b)

            self.layer_lines[i].show()

        # Reset collections since clear() removed everything

        self.block_items.clear()

        self.curve_segments.clear()

        self.text_labels.clear()

        # Drawing the strategy

        if strategy_blocks:
            x_arr = np.array(x, dtype=np.float64)

            y_arr = np.array(y, dtype=np.float64)

            # Clip x < 0 (digital artifact) to avoid erroneous trace on the left

            valid = x_arr >= 0.0

            x_arr = x_arr[valid]

            y_arr = y_arr[valid]

            for i, block in enumerate(strategy_blocks):
                wl = float(block["wavelength"])

                start_layer = block["start"]

                end_layer = block["end"]

                color = self.colors[i % len(self.colors)]

                if start_layer < len(bounds) and end_layer < len(bounds):
                    x_start = bounds[start_layer]

                    x_end = bounds[end_layer]

                    width = x_end - x_start

                    x_center = (x_start + x_end) / 2.0

                    mask = (x_arr >= x_start - 1e-3) & (x_arr <= x_end + 1e-3)

                    if np.any(mask):
                        segment = self.plot_widget.plot(
                            x_arr[mask],
                            y_arr[mask],
                            pen=pg.mkPen(color=color, width=2.5),
                        )

                        self.curve_segments.append(segment)

                    if i < len(strategy_blocks) - 1:
                        sep_line = pg.InfiniteLine(pos=x_end, angle=90, pen=pg.mkPen(color="#ef4444", width=2))

                        sep_line.setZValue(10)

                        self.plot_widget.addItem(sep_line)

                        self.block_items.append(sep_line)

                    label_text = f"{int(wl)}"

                    text_item = pg.TextItem(text=label_text, color=color, anchor=(0.5, 0.5))

                    font = CertusTheme.get_font()

                    font.setBold(True)

                    rotation = 0

                    if width < 50:
                        font.setPointSize(8)

                        rotation = -90

                    elif width < 150:
                        font.setPointSize(9)

                    else:
                        font.setPointSize(11)

                    text_item.setFont(font)

                    if rotation != 0:
                        text_item.setAngle(rotation)

                    is_staggered_low = i % 2 != 0

                    y_pos = 0.05 if is_staggered_low else 0.15

                    text_item.setPos(x_center, y_pos)

                    self.plot_widget.addItem(text_item)

                    self.text_labels.append(text_item)

    def closeEvent(self, event) -> None:

        self.user_hidden = True

        self.hide()

        event.ignore()

class WelcomeGuideWidget(QWidget):
    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"""

            QWidget {{ font-family: 'Segoe UI', sans-serif; }}

            QScrollArea, QWidget#ContentContainer {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {CertusTheme.BACKGROUND}, stop:1 {CertusTheme.SURFACE}); border: none; }}

            QScrollBar:vertical {{ width: 10px; background: transparent; }}

            QScrollBar::handle:vertical {{ background: {CertusTheme.BORDER}; border-radius: 5px; min-height: 20px; }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            .step-card {{ background-color: {CertusTheme.ELEVATED}; border: 1px solid {CertusTheme.BORDER}; border-radius: 16px; }}

            .step-number {{ font-size: 42px; font-weight: 900; opacity: 0.2; }}

            .step-title {{ color: {CertusTheme.TEXT_MAIN}; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }}

            .step-desc {{ color: {CertusTheme.TEXT_SUB}; font-size: 13px; line-height: 1.4; }}

            .mission-frame {{ background-color: {CertusTheme.BACKGROUND}; border: 1px solid {CertusTheme.BORDER}; border-left: 4px solid {CertusTheme.SECONDARY}; border-radius: 8px; }}

            .dash-frame {{ background-color: {CertusTheme.ELEVATED}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px; }}

            .dash-header {{ color: {CertusTheme.PRIMARY}; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid {CertusTheme.BORDER}; padding-bottom: 8px; margin-bottom: 10px; }}

        """)

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_container = QWidget()

        self.content_container.setObjectName("ContentContainer")

        main_layout = QVBoxLayout(self.content_container)

        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.content_container)

        outer_layout.addWidget(self.scroll_area)

        content_wrapper = QWidget()

        content_wrapper.setStyleSheet("background-color: transparent;")

        content_layout = QVBoxLayout(content_wrapper)

        content_layout.setContentsMargins(5, 15, 5, 10)

        content_layout.setSpacing(20)

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(5)

        cards_layout.addWidget(
            self._create_step_card(
                "01",
                "DESIGN",
                "Define optical stack,\nmaterials & target.",
                CertusTheme.SECONDARY,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "02",
                "OPTIMIZE",
                "Hybrid algorithm for\nstable monitoring.",
                CertusTheme.ACCENT,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "03",
                "VALIDATE",
                "Monte Carlo sims to\nensure robustness.",
                CertusTheme.SUCCESS,
            )
        )

        content_layout.addLayout(cards_layout)

        mission_frame = QFrame()

        mission_frame.setProperty("class", "mission-frame")

        mission_layout = QGridLayout(mission_frame)

        mission_layout.setContentsMargins(15, 15, 15, 15)

        points = [
            (
                "🎯",
                "<b>Precision Targeting:</b> Identify exact wavelengths to cancel errors.",
            ),
            ("🧬", "<b>Hybrid Intelligence:</b> DP engine finds global minimuum."),
            (
                "🛡️",
                "<b>Robustness First:</b> Validation via thousands of Monte Carlo sims.",
            ),
            (
                "⚡",
                "<b>Real-Time Physics:</b> JIT engine simulating layer growth in ms.",
            ),
            (
                "📉",
                "<b>Zero-Bias Strategy:</b> Eliminate empiricism with proven paths.",
            ),
            (
                "📈",
                "<b>Yield Assurance:</b> Turn theoretical robustness into production gains.",
            ),
        ]

        for i, (icon, text) in enumerate(points):
            item_widget = QWidget()

            item_layout = QHBoxLayout(item_widget)

            item_layout.setContentsMargins(0, 0, 0, 0)

            lbl_ico = QLabel(icon)

            lbl_ico.setStyleSheet("font-size: 20px; background: transparent;")

            lbl_ico.setFixedWidth(25)

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 13px; background: transparent;")

            lbl_txt.setTextFormat(Qt.TextFormat.RichText)

            lbl_txt.setWordWrap(True)

            item_layout.addWidget(lbl_ico)

            item_layout.addWidget(lbl_txt)

            mission_layout.addWidget(item_widget, i // 2, i % 2)

        content_layout.addWidget(mission_frame)

        dash_frame = QFrame()

        dash_frame.setProperty("class", "dash-frame")

        shadow_dash = QGraphicsDropShadowEffect()

        shadow_dash.setBlurRadius(15)

        shadow_dash.setColor(QColor(0, 0, 0, 10))

        shadow_dash.setOffset(0, 2)

        dash_frame.setGraphicsEffect(shadow_dash)

        dash_layout = QHBoxLayout(dash_frame)

        dash_layout.setContentsMargins(15, 15, 15, 15)

        dash_layout.setSpacing(20)

        # Get approximate total CPU count

        from certus_core import _get_cpu_count

        cpu_count = _get_cpu_count()

        try:
            mat_count = len(APP_CONTEXT.get("materials_db").data) if APP_CONTEXT.get("materials_db") else 0

        except (AttributeError, TypeError):
            mat_count = 0

        sys_layout = QVBoxLayout()

        sys_head = QLabel("SYSTEM READINESS")

        sys_head.setProperty("class", "dash-header")

        sys_layout.addWidget(sys_head)

        sys_layout.addLayout(self._create_status_row("⚡", "HPC Active", f"<b>{cpu_count} Threads</b>"))

        sys_layout.addLayout(self._create_status_row("📚", "Database", f"<b>{mat_count} Materials</b>"))

        sys_layout.addLayout(self._create_status_row("🚀", "JIT Engine", "<b>Compiled & Ready</b>"))

        sys_layout.addStretch()

        cap_layout = QVBoxLayout()

        cap_head = QLabel("CORE CAPABILITIES")

        cap_head.setProperty("class", "dash-header")

        cap_layout.addWidget(cap_head)

        cap_layout.addLayout(self._create_status_row("✓", "Hybrid Exploration", "DP + hybridization"))

        cap_layout.addLayout(self._create_status_row("✓", "Simulation", "Adaptive Nucleation"))

        cap_layout.addLayout(self._create_status_row("✓", "Analysis", "Yield & Robustness"))

        cap_layout.addStretch()

        dash_layout.addLayout(sys_layout)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.VLine)

        line.setStyleSheet(f"color: {CertusTheme.SURFACE_HOVER};")

        dash_layout.addWidget(line)

        dash_layout.addLayout(cap_layout)

        content_layout.addWidget(dash_frame)

        main_layout.addWidget(content_wrapper)

        main_layout.addStretch()

    def _create_step_card(self, number, title, desc, accent_color) -> Any:

        card = QFrame()

        card.setProperty("class", "step-card")

        card.setStyleSheet(f".step-card {{ border-bottom: 4px solid {accent_color}; }}")

        card.setMinimumWidth(150)

        card.setMaximumWidth(220)

        card.setFixedHeight(140)

        shadow = QGraphicsDropShadowEffect()

        shadow.setBlurRadius(25)

        shadow.setColor(QColor(0, 0, 0, 20))

        shadow.setOffset(0, 8)

        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)

        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_num = QLabel(number)

        lbl_num.setProperty("class", "step-number")

        lbl_num.setStyleSheet(f"color: {accent_color}; background: transparent;")

        lbl_title = QLabel(title)

        lbl_title.setProperty("class", "step-title")

        lbl_title.setStyleSheet("background: transparent;")

        lbl_desc = QLabel(desc)

        lbl_desc.setProperty("class", "step-desc")

        lbl_desc.setStyleSheet("background: transparent;")

        vbox.addWidget(lbl_num)

        vbox.addWidget(lbl_title)

        vbox.addWidget(lbl_desc)

        return card

    def _create_status_row(self, icon, label, value) -> Any:

        row = QHBoxLayout()

        row.setSpacing(15)

        lbl_icon = QLabel(icon)

        lbl_icon.setFixedSize(24, 24)

        lbl_icon.setStyleSheet(
            f"background-color: {CertusTheme.INFO_BG}; color: {CertusTheme.SECONDARY}; border-radius: 4px; font-weight: bold; font-size: 14px;"
        )

        if icon == "✓":
            lbl_icon.setStyleSheet(
                f"background-color: {CertusTheme.SUCCESS_BG}; color: {CertusTheme.SUCCESS}; border-radius: 4px; font-weight: bold; font-size: 14px;"
            )

        lbl_text = QLabel(label)

        lbl_text.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 13px; font-weight: 500; background: transparent;"
        )

        lbl_val = QLabel(value)

        lbl_val.setTextFormat(Qt.TextFormat.RichText)

        lbl_val.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 13px; background: transparent;")

        row.addWidget(lbl_icon)

        row.addWidget(lbl_text)

        row.addStretch()

        row.addWidget(lbl_val)

        return row

# === OPTIMIZATION: Async Plot Renderer ===

class PlotRenderWorker(QObject):
    finished = pyqtSignal(bytes, str)

    error = pyqtSignal(str)

    def __init__(self, fig, width, height, plot_hash) -> None:

        super().__init__()

        self.fig = fig

        self.width = width

        self.height = height

        self.plot_hash = plot_hash

    def run(self) -> None:

        try:
            img_bytes = self.fig.to_image(format="png", scale=2.0, width=self.width, height=self.height)

            self.finished.emit(img_bytes, self.plot_hash)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.error.emit(str(e))

def _resolve_strat_indices_db_path() -> str:
    """Return canonical indices DB path for STRAT, with legacy fallback."""

    preferred = str(Path(get_resource_path(str(Path("example") / "database_index" / "indices.xlsx"))).resolve())

    if Path(preferred).exists():
        return preferred

    legacy = str(Path(get_resource_path("clues.xlsx")).resolve())

    return legacy

class CertusStratApp(CertusBaseApp):
    """Main CERTUS-STRAT Application"""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-STRAT"

    APP_TITLE = "Predictive Monitoring Strategy"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:

        super().__init__()

        # --- Cache & Async Init ---

        self._plot_cache = PlotCache()

        self._cache_lock = threading.Lock()

        self._rendering_plots = set()

        self._active_render_thread = None

        # STRAT-specific state

        self.plot_queue: queue.Queue = queue.Queue()

        self.plot_windows: list[UniversalPlotWindow] = []

        self.strategies_table_window: StrategiesTableWindow | None = None

        self.transmission_windows: list[TransmissionVsThicknessWindow] = []

        self.json_windows: list[JsonViewerWindow] = []

        self._floating_stack_window = None

        self.heatmap_window = None

        self.clues_window = None

        self.stack_visual_window = None

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        self.timing_logger = TimingLogger(self.logger)

        # Materials database

        self.materials_db = MaterialDatabase(_resolve_strat_indices_db_path())

        APP_CONTEXT["materials_db"] = self.materials_db

        self.material_list = list(self.materials_db.data.keys()) if self.materials_db.data else []

        self.opti_results: dict[str, Any] | None = None

        self.undo_stack = deque(maxlen=5)

        self.live_monitor_window = None

        # Build UI

        self._build_gui()

        self._apply_theme()

        self.set_default_values()

        self._init_widget_states()

        # STRAT uses two timers: log + plot

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        self.plot_timer = self.startTimer(200)

        # Disable buttons until warmup completes

        self.run_step0_btn.setEnabled(False)

        self.run_step2_btn.setEnabled(False)

        self.run_full_btn.setEnabled(False)

        self.status_label.setText("System warming up (compiling JIT)...")

        # Warmup in background thread

        threading.Thread(target=self._warmup_numba, daemon=True).start()

        # Post-init setup

        QTimer.singleShot(100, lambda: self._init_undo_shortcut())

        QTimer.singleShot(0, self.apply_default_layout)

    def _request_stop(self) -> None:
        """Called by reset framework before stopping workers. Sets stop flag so worker loop exits when in a run."""

        if hasattr(self, "worker") and self.worker is not None and getattr(self.worker, "isRunning", lambda: False)():
            if hasattr(self.worker, "params") and isinstance(self.worker.params, dict):
                self.worker.params["stop_requested"] = True

    def _load_defaults(self) -> None:
        """Load default values for CERTUS-STRAT"""

        # Reset workflow state

        self.opti_results = None

        self.undo_stack.clear()

        # Reset materials database

        if hasattr(self, "materials_db"):
            self.materials_db.clear_cache()

        # Reset stack table

        if hasattr(self, "widgets") and "stack_table" in self.widgets:
            self.widgets["stack_table"].setRowCount(0)

        # Reset material selections

        if hasattr(self, "widgets"):
            default_materials = {"substrate_choice": "Custom", "nSub_custom": "1.73", "l0": "550.0"}

            for widget_name, default_value in default_materials.items():
                if widget_name in self.widgets:
                    if hasattr(self.widgets[widget_name], "setCurrentText"):
                        self.widgets[widget_name].setCurrentText(default_value)

                    elif hasattr(self.widgets[widget_name], "setText"):
                        self.widgets[widget_name].setText(default_value)

        # Close all auxiliary windows

        self.close_all_auxiliary_windows()

        # Kill existing log timer before creating a new one (prevents timer leak)

        if getattr(self, "_log_timer_id", None) is not None:
            self.killTimer(self._log_timer_id)

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        self._init_global_shortcuts()

    def apply_default_layout(self) -> None:

        main_splitter = self.centralWidget()

        if isinstance(main_splitter, QSplitter):
            total_width = self.width()

            main_splitter.setSizes([int(total_width / 2), int(total_width / 2)])

    def _init_global_shortcuts(self) -> None:
        """Global UX Hotkeys (Pro 2026 Theme)."""

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_configuration)

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_configuration)

        run_opti = QShortcut(QKeySequence("F5"), self)

        run_opti.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        run_opti_alt = QShortcut(QKeySequence("Ctrl+R"), self)

        run_opti_alt.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        QShortcut(QKeySequence("Esc"), self).activated.connect(self.close_all_auxiliary_windows)

        install_standard_shortcuts(
            self,
            help=lambda: open_documentation("CERTUS_STRAT"),
            toggle_logs=lambda: self.toggle_details_btn.setChecked(not self.toggle_details_btn.isChecked()),
        )

        def _on_config_drop(paths) -> None:
            if paths and hasattr(self, "load_configuration"):
                self.load_configuration(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_config_drop, extensions=("json",))

    def _apply_theme(self) -> None:

        font = CertusTheme.get_font(9)

        QApplication.instance().setFont(font)

        QApplication.instance().setStyle("Fusion")

        # Propagate theme to auxiliary windows if open

        if hasattr(self, "live_monitor_window") and self.live_monitor_window and self.live_monitor_window.isVisible():
            # Force style refresh for live monitor

            self.live_monitor_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

            # If it has plots, ideally update them too - generic refresh

            self.live_monitor_window.style().unpolish(self.live_monitor_window)

            self.live_monitor_window.style().polish(self.live_monitor_window)

        if hasattr(self, "results_window") and self.results_window and self.results_window.isVisible():
            self.results_window.setStyleSheet(
                f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};"
            )

        # Apply theme with STRAT-specific overrides

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}

            /* Labels are slightly subtler in STRAT */

            QLabel {{ color: {CertusTheme.TEXT_SUB}; font-weight: 500; }}

            /* STRAT buttons - wider padding, secondary hover */

            QPushButton {{ padding: 6px 16px; }}

            QPushButton:hover {{ border-color: {CertusTheme.SECONDARY}; }}

            QPushButton:pressed {{ background-color: {CertusTheme.BACKGROUND}; padding-top: 7px; }}

            /* Special RUN FULL Button Gradient */

            QPushButton[text^="RUN FULL"] {{ 

                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {CertusTheme.PRIMARY}, stop:1 #2563eb); 

                color: white; border: none; font-size: 13px; padding: 12px; border-radius: 8px; 

            }}

            QPushButton[text^="RUN FULL"]:hover {{ 

                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 {CertusTheme.SECONDARY}); 

                border: 1px solid #bfdbfe; 

            }}

            QPushButton[text^="RUN FULL"]:disabled {{ 

                background-color: {CertusTheme.TEXT_DISABLED}; color: {CertusTheme.BORDER}; 

            }}

            /* GroupBox harmonized with CertusCard */

            QGroupBox {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; margin-top: 14px; padding: 10px 10px 8px 10px; font-weight: 600; color: {CertusTheme.TEXT_MAIN}; }}

            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 6px; color: {CertusTheme.PRIMARY}; background: {CertusTheme.SURFACE}; }}

            /* Tabs STRAT specific */

            QTabWidget::pane {{ border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; background: {CertusTheme.SURFACE}; top: -1px; }}

            QTabBar::tab {{ background: transparent; border: none; border-bottom: 3px solid transparent; padding: 10px 20px; margin-right: 4px; color: {CertusTheme.TEXT_SUB}; font-weight: 600; }}

            QTabBar::tab:selected {{ color: {CertusTheme.PRIMARY}; border-bottom: 3px solid {CertusTheme.PRIMARY}; background: rgba(30, 58, 138, 0.04); border-top-left-radius: 6px; border-top-right-radius: 6px; }}

            QTabBar::tab:hover:!selected {{ color: {CertusTheme.TEXT_MAIN}; background: rgba(0,0,0,0.02); }}

        """,
        )

    def timerEvent(self, event) -> None:

        if event.timerId() == getattr(self, "_log_timer_id", -1):
            self._process_log_queue()

        elif event.timerId() == getattr(self, "plot_timer", -1):
            self.process_plot_queue()

        else:
            super().timerEvent(event)

    def on_stats_update(self, counter_type: str, increment: int) -> None:

        if counter_type in self.stat_counters:
            self.stat_counters[counter_type] += increment

            self.update_stats_display()

    def _warmup_numba(self) -> None:

        try:
            dummy_wl, dummy_n, dummy_thick = (
                np.array([1000.0], dtype=np.float64),
                np.array([1.5], dtype=np.float64),
                np.array([100.0], dtype=np.float64),
            )

            _ = calculate_RT_vectorized_real_HL(dummy_wl, dummy_n, dummy_n, dummy_n, dummy_thick)

            _ = simulate_growth_kernel(
                dummy_thick,
                0,
                np.array([0.0], dtype=np.float64),
                1000.0,
                2.3,
                1.45,
                1.52,
                80.0,
                0.0,
                1.0,
                NON_MONOTONIC_MODE_ATTENUATE,
            )

            self.numba_ready = True

            QMetaObject.invokeMethod(self, "_on_numba_ready_ui", Qt.ConnectionType.QueuedConnection)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.warning(f"Numba warmup warning: {e}")

            self.numba_ready = True

            QMetaObject.invokeMethod(self, "_on_numba_ready_ui", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:

        self.logger.info("✅ System Ready (Numba JIT Compiled)")

        self.status_label.setText("Ready.")

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)


    def on_toggle_details(self, checked) -> None:

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

    def update_stats_display(self) -> None:
        from certus_ui import format_count_kmg

        self.stats_label.setText(
            f"♟️ {format_count_kmg(self.stat_counters['MS'])}  | 🎲 {format_count_kmg(self.stat_counters['MCS'])}  |  🌈️ {format_count_kmg(self.stat_counters['SP'])}"
        )

    def close_all_auxiliary_windows(self) -> None:

        self.logger.info("Closing all auxiliary windows...")

        lists_to_close = [
            self.plot_windows,
            self.transmission_windows,
            self.json_windows,
            getattr(self, "interactive_spectrum_windows", []),
        ]

        for win_list in lists_to_close:
            for win in win_list[:]:
                try:
                    win.close()

                except (RuntimeError, AttributeError):
                    # Window may already be closed or destroyed

                    pass

            del win_list[:]

        for attr_name in [
            "strategies_table_window",
            "live_monitor_window",
            "heatmap_window",
            "stack_visual_window",
            "_floating_stack_window",
        ]:
            win = getattr(self, attr_name, None)

            if win:
                win.close()

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self) and hasattr(self, "status_label"):
            self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"])

    def _build_log_container(self) -> QWidget:
        """Build log container with Copy button (uses shared CertusLogPanel)."""

        panel = CertusLogPanel(title="LOGS", visible=False)

        self.log_text = panel.log_text

        self._log_panel = panel

        return panel

    def _build_gui(self) -> None:

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_split = main_splitter

        self.setCentralWidget(main_splitter)

        left_panel_widget = QWidget()

        left_panel_layout = QVBoxLayout(left_panel_widget)

        left_panel_widget.setMinimumWidth(280)

        # Removed MaximumWidth to allow resizing via splitter

        left_panel_layout.setContentsMargins(0, 0, 0, 0)

        left_panel_layout.setSpacing(0)

        # 1. Standard Header (Pinned)

        header_widget = create_header_logo_widget(
            "STRAT",
            self.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_STRAT",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_panel_layout.addWidget(header_widget)

        # 2. Action Bar (Pinned)

        # Note: No export function passed as it's not standard in STRAT top bar yet.

        action_bar = create_top_actions_bar(
            self,
            self.save_configuration,
            self.load_configuration,
            export_func=None,
            help_func=lambda: open_documentation("CERTUS_STRAT"),
        )

        left_panel_layout.addWidget(action_bar)

        # 3. Scroll Area

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        left_panel_layout.addWidget(scroll_area)

        main_splitter.addWidget(left_panel_widget)

        controls_widget = QWidget()

        scroll_area.setWidget(controls_widget)

        controls_layout = QVBoxLayout(controls_widget)

        controls_layout.setSpacing(8)

        controls_layout.setContentsMargins(0, 0, 4, 0)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Build stack  2 Configure optimization  3 Run workflow  4 Inspect strategies")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        workflow_card.body.addWidget(workflow_hint)

        controls_layout.addWidget(workflow_card)

        self.tabs = QTabWidget()

        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tabs_card = CertusCard("Controls")

        tabs_card.body.setContentsMargins(0, 0, 0, 0)

        tabs_card.body.addWidget(self.tabs)

        controls_layout.addWidget(tabs_card)

        self._create_design_tab()

        self._create_optimization_tab()

        self._create_advanced_tab()

        self._create_why_certus_tab()

        controls_layout.addStretch()

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        main_splitter.addWidget(right_splitter)

        self.plot_stack = QStackedWidget()

        self.welcome_widget = WelcomeGuideWidget()

        self.plot_stack.addWidget(self.welcome_widget)

        self.main_plot_widget = QLabel()

        self.main_plot_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_plot_widget.setScaledContents(True)

        self.main_plot_widget.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND};")

        self.plot_stack.addWidget(self.main_plot_widget)

        right_splitter.addWidget(self.plot_stack)

        log_widget = self._build_log_container()

        right_splitter.addWidget(log_widget)

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.status_bar.setSizeGripEnabled(False)

        self.toggle_details_btn = QPushButton("Show Details")

        self.toggle_details_btn.setCheckable(True)

        self.toggle_details_btn.setFixedWidth(100)

        self.toggle_details_btn.setToolTip("Show/hide the computation log panel below the plot area.")

        self.toggle_details_btn.setStyleSheet(f"""

            QPushButton {{ background-color: {CertusTheme.DARK_BORDER}; color: white; border: 1px solid {CertusTheme.DARK_BORDER}; border-radius: 3px; padding: 2px; font-size: 11px; font-weight: bold; }}

            QPushButton:checked {{ background-color: {CertusTheme.DARK_CARD}; }}

            QPushButton:hover {{ background-color: {CertusTheme.DARK_SURFACE}; }}

        """)

        self.toggle_details_btn.toggled.connect(self.on_toggle_details)

        self.status_bar.addWidget(self.toggle_details_btn)

        self.status_label = CertusStatusPill("Ready.", "ready")

        self.status_bar.addWidget(self.status_label, 1)

        self.stats_label = QLabel("♟️ 0  | 🎲 0  |  🌈️ 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.stats_label.setToolTip(
            "♟️ Mining Strategies evaluated  |  🎲 Monte Carlo Simulations run  |  🌈 Spectral points processed"
        )

        self.status_bar.addPermanentWidget(self.stats_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setFixedWidth(200)

        self.progress_bar.setFixedHeight(14)

        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        self.status_bar.addPermanentWidget(self.progress_bar)

        if getattr(self, "_log_panel", None):
            self._log_panel.copied.connect(lambda: self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"]))

    def _create_design_tab(self) -> None:

        design_tab = QWidget()

        self.tabs.addTab(design_tab, "Design")

        self.design_layout = QVBoxLayout(design_tab)

        self.design_layout.setSpacing(8)

        self.design_layout.setContentsMargins(5, 8, 5, 5)

        materials_container = CertusCard("Material Refractive Indices")

        materials_layout = QHBoxLayout()

        materials_layout.setSpacing(10)

        materials_layout.setContentsMargins(5, 12, 5, 5)

        materials_container.body.addLayout(materials_layout)

        layout_h = QVBoxLayout()

        self._create_material_group(layout_h, "High-Index (H)", "h", "H", _is_compact=True)

        layout_l = QVBoxLayout()

        self._create_material_group(layout_l, "Low-Index (L)", "l", "L", _is_compact=True)

        materials_layout.addLayout(layout_h, 1)

        materials_layout.addLayout(layout_l, 1)

        self.design_layout.addWidget(materials_container)

        top_settings_widget = QWidget()

        top_settings_layout = QHBoxLayout(top_settings_widget)

        top_settings_layout.setContentsMargins(0, 5, 0, 5)

        top_settings_layout.setSpacing(10)

        gb_sub = CertusCard("substrate_Base Wavelength")

        gb_sub_layout = QHBoxLayout()

        gb_sub_layout.setContentsMargins(10, 15, 10, 8)

        gb_sub.body.addLayout(gb_sub_layout)

        gb_sub_layout.setSpacing(10)

        lbl_sub = QLabel("substrate:")

        self.widgets["substrate_choice"] = QComboBox()

        self.widgets["substrate_choice"].addItems(["Custom"] + list(SUBSTRATE_MAPPING.keys()))

        self.widgets["substrate_choice"].setMinimumWidth(100)

        self.widgets["substrate_choice"].setToolTip(
            "substrate material. 'Custom' lets you enter a fixed real index below.\n"
            "Predefined substrates fill the index field automatically."
        )

        self.widgets["substrate_choice"].currentTextChanged.connect(self._on_substrate_choice_changed)

        lbl_idx = QLabel("Index:")

        self.widgets["nSub_custom"] = QLineEdit()

        self.widgets["nSub_custom"].setPlaceholderText("1.73")

        self.widgets["nSub_custom"].setFixedWidth(50)

        self.widgets["nSub_custom"].setToolTip(
            "Real part of the substrate refractive index (used when substrate = Custom)."
        )

        gb_sub_layout.addWidget(lbl_sub)

        gb_sub_layout.addWidget(self.widgets["substrate_choice"])

        gb_sub_layout.addWidget(lbl_idx)

        gb_sub_layout.addWidget(self.widgets["nSub_custom"])

        gb_lam = CertusCard("Reference")

        gb_lam_layout = QHBoxLayout()

        gb_lam_layout.setContentsMargins(10, 15, 10, 8)

        gb_lam.body.addLayout(gb_lam_layout)

        lbl_l0 = QLabel("Center lambda₀ (nm):")

        lbl_l0.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {CertusTheme.INFO_TEXT};")

        self.widgets["l0"] = QLineEdit()

        self.widgets["l0"].setFixedWidth(70)

        self.widgets["l0"].setStyleSheet(
            f"font-weight: bold; background-color: {CertusTheme.WARNING_BG}; border: 1px solid {CertusTheme.BORDER}; border-radius: 4px; color: {CertusTheme.TEXT_MAIN};"
        )

        self.widgets["l0"].setToolTip(
            "Reference (center) wavelength lambda₀ in nanometres.\n"
            "Used as the nucleation anchor and to convert optical thicknesses (QWOT = lambda₀/4n).\n"
            "Also used as the nucleation wavelength for the first monochromatic monitoring block."
        )

        gb_lam_layout.addWidget(lbl_l0)

        gb_lam_layout.addWidget(self.widgets["l0"])

        top_settings_layout.addWidget(gb_sub)

        top_settings_layout.addWidget(gb_lam)

        self.design_layout.addWidget(top_settings_widget)

        self.stack_group = CertusCard("Stack Control & Workflow")

        cockpit_layout = QHBoxLayout()

        self.stack_group.body.addLayout(cockpit_layout)

        cockpit_layout.setContentsMargins(5, 15, 5, 5)

        cockpit_layout.setSpacing(80)

        tools_widget = QWidget()

        tools_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tools_grid = QGridLayout(tools_widget)

        tools_grid.setContentsMargins(0, 0, 0, 0)

        tools_grid.setSpacing(8)

        tools_grid.setColumnStretch(0, 1)

        tools_grid.setColumnStretch(1, 1)

        btn_style = f"QPushButton {{ border-radius: 6px; border: 1px solid {CertusTheme.BORDER}; background: {CertusTheme.SURFACE}; font-size: 11px; font-weight: 600; color: {CertusTheme.TEXT_MAIN}; padding: 5px 10px; text-align: left; }} QPushButton:hover {{ background: {CertusTheme.SURFACE_HOVER}; border-color: {CertusTheme.SECONDARY}; }}"

        def set_std_icon(btn, pixmap_enum) -> None:

            btn.setIcon(self.style().standardIcon(pixmap_enum))

        self.add_btn = QPushButton("Add Layer")

        self.add_btn.setFixedHeight(32)

        self.add_btn.setStyleSheet(
            btn_style
            + f"color: {CertusTheme.SUCCESS_TEXT}; border-color: {CertusTheme.SUCCESS_BG}; background: {CertusTheme.SUCCESS_BG};"
        )

        set_std_icon(self.add_btn, QStyle.StandardPixmap.SP_FileDialogNewFolder)

        self.add_btn.setToolTip("Add a new layer at the bottom of the stack table.")

        self.add_btn.clicked.connect(self.add_layer)

        self.remove_btn = QPushButton("Remove Layer")

        self.remove_btn.setFixedHeight(32)

        self.remove_btn.setStyleSheet(
            btn_style
            + f"color: {CertusTheme.DANGER_TEXT}; border-color: {CertusTheme.DANGER_BG}; background: {CertusTheme.DANGER_BG};"
        )

        set_std_icon(self.remove_btn, QStyle.StandardPixmap.SP_TrashIcon)

        self.remove_btn.setToolTip("Remove the last (bottom) layer from the stack table.")

        self.remove_btn.clicked.connect(self.remove_layer)

        tools_grid.addWidget(self.add_btn, 0, 0)

        tools_grid.addWidget(self.remove_btn, 0, 1)

        btn_save = QPushButton("Save Config")

        btn_save.setFixedHeight(30)

        btn_save.setStyleSheet(btn_style)

        set_std_icon(btn_save, QStyle.StandardPixmap.SP_DialogSaveButton)

        btn_save.setToolTip("Save the current stack & all parameters to a JSON config file (Ctrl+S).")

        btn_save.clicked.connect(self.save_configuration)

        btn_load = QPushButton("Load Config")

        btn_load.setFixedHeight(30)

        btn_load.setStyleSheet(btn_style)

        set_std_icon(btn_load, QStyle.StandardPixmap.SP_DialogOpenButton)

        btn_load.setToolTip("Load a previously saved JSON config file, restoring stack & parameters (Ctrl+O).")

        btn_load.clicked.connect(self.load_configuration)

        tools_grid.addWidget(btn_save, 1, 0)

        tools_grid.addWidget(btn_load, 1, 1)

        self.load_strat_btn = QPushButton("Import Strat.")

        self.load_strat_btn.setFixedHeight(30)

        self.load_strat_btn.setStyleSheet(btn_style)

        set_std_icon(self.load_strat_btn, QStyle.StandardPixmap.SP_ArrowDown)

        self.load_strat_btn.setToolTip(
            "Import an external strategies JSON file generated by a previous CERTUS-STRAT run.\n"
            "Allows direct comparison of strategies without re-running the full workflow."
        )

        self.load_strat_btn.clicked.connect(self.load_external_strategies)

        self.detach_btn = QPushButton("Pop-Out")

        self.detach_btn.setFixedHeight(30)

        self.detach_btn.setStyleSheet(btn_style)

        set_std_icon(self.detach_btn, QStyle.StandardPixmap.SP_TitleBarNormalButton)

        self.detach_btn.setToolTip("Detach the Stack Definition table into its own floating window for easier editing.")

        self.detach_btn.clicked.connect(self.detach_stack_window)

        tools_grid.addWidget(self.load_strat_btn, 2, 0)

        tools_grid.addWidget(self.detach_btn, 2, 1)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.HLine)

        line.setStyleSheet(f"color:{CertusTheme.BORDER};")

        tools_grid.addWidget(line, 3, 0, 1, 2)

        self.run_step0_btn = QPushButton("Step 1 (Nominal)")
        self.run_step0_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step0_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step0_btn, QStyle.StandardPixmap.SP_ComputerIcon)

        self.run_step0_btn.setToolTip(
            "Step 0: Computes the basic optical response of the nominal layer stack without exploration."
        )

        self.run_step0_btn.clicked.connect(functools.partial(self.run_workflow, 0))

        tools_grid.addWidget(self.run_step0_btn, 4, 0)

        self.run_step2_btn = QPushButton("Step 2 (Opti)")
        self.run_step2_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step2_btn, QStyle.StandardPixmap.SP_BrowserReload)

        self.run_step2_btn.setToolTip(
            "Step 2: Launches the primary DP Optimization kernel based on the Target Spectrum."
        )

        self.run_step2_btn.clicked.connect(functools.partial(self.run_workflow, 2))

        tools_grid.addWidget(self.run_step2_btn, 4, 1)

        self.run_step3_btn = QPushButton("Step 3 (Rob)")
        self.run_step3_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_step3_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.run_step3_btn, QStyle.StandardPixmap.SP_DialogApplyButton)

        self.run_step3_btn.setEnabled(False)

        self.run_step3_btn.setToolTip(
            "Step 3: Simulates thousands of robust Monte-Carlo growth scenarios for yield estimation."
        )

        self.run_step3_btn.clicked.connect(functools.partial(self.run_workflow, 3))

        tools_grid.addWidget(self.run_step3_btn, 5, 0)

        self.stop_step2_btn = QPushButton("STOP Calculation")
        self.stop_step2_btn.setObjectName(OBJ.DANGER_BUTTON)
        self.stop_step2_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        set_std_icon(self.stop_step2_btn, QStyle.StandardPixmap.SP_MediaStop)

        self.stop_step2_btn.setToolTip(
            "Gracefully interrupt the running optimization.\n"
            "The engine will finish its current block and then proceed directly to Step 3 (robustness test)."
        )

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.stop_step2_btn.clicked.connect(self.request_stop_optimization)

        tools_grid.addWidget(self.stop_step2_btn, 5, 1)

        self.run_full_btn = QPushButton(" RUN FULL WORKFLOW")
        self.run_full_btn.setObjectName(OBJ.PRIMARY_BUTTON)
        self.run_full_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.run_full_btn.setFixedHeight(42)

        set_std_icon(self.run_full_btn, QStyle.StandardPixmap.SP_MediaPlay)

        self.run_full_btn.setToolTip(
            "Run the complete workflow in one click:\n"
            "Step 2 (DP Strategy Search) -> Step 3 (Monte Carlo Robustness Validation).\n"
            "Equivalent to pressing Step 2 then Step 3 sequentially."
        )

        self.run_full_btn.clicked.connect(functools.partial(self.run_workflow, 23))

        tools_grid.addWidget(self.run_full_btn, 6, 0, 1, 2)

        # Clear / Reset button

        from certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self)

        self.clear_btn.setFixedHeight(32)

        tools_grid.addWidget(self.clear_btn, 7, 0, 1, 2)

        tools_grid.setRowStretch(8, 1)

        cockpit_layout.addWidget(tools_widget)

        self.widgets["stack_table"] = ExcelTableWidget()

        self.widgets["stack_table"].setColumnCount(3)

        self.widgets["stack_table"].setHorizontalHeaderLabels(["#", "Mat.", "Mult."])

        self.widgets["stack_table"].setFixedWidth(200)

        # Column header tooltips

        _stack_col_tips = {
            0: "Layer index (1 = topmost). Read-only.",
            1: "Material type: H (high-index) or L (low-index).",
            2: "Thickness multiplier relative to QWOT (lambda₀/4n). E.g. 1.0 = 1 QWOT, 0.5 = half-wave.",
        }



        for _col, _tip in _stack_col_tips.items():
            _item = self.widgets["stack_table"].horizontalHeaderItem(_col)

            if _item:
                _item.setToolTip(_tip)

        self.widgets["stack_table"].verticalHeader().setDefaultSectionSize(22)

        h_header = self.widgets["stack_table"].horizontalHeader()

        h_header.resizeSection(0, 25)

        h_header.resizeSection(1, 35)

        h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.widgets["stack_table"].setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self.widgets["stack_table"].setMinimumHeight(200)

        # Connect cellChanged to save state before modification

        self.widgets["stack_table"].cellChanged.connect(self._on_stack_table_changed)

        cockpit_layout.addWidget(self.widgets["stack_table"])

        self.design_layout.addWidget(self.stack_group)

    def request_stop_optimization(self) -> None:

        # confirm_stop_with_timeout is imported from certus_ui

        if not confirm_stop_with_timeout(self):
            return

        if hasattr(self, "worker") and self.worker.isRunning():
            self.logger.warning(
                "⚡ USER REQUEST: Stopping Optimization Loop... Finishing current block and proceeding to Step 3."
            )

            self.worker.params["stop_requested"] = True

        self.stop_step2_btn.setText("Stopping...")

        self.stop_step2_btn.setEnabled(False)

    def _create_optimization_tab(self) -> None:

        opt_tab = QWidget()

        self.tabs.addTab(opt_tab, "Strategy Loop")

        opt_layout = QVBoxLayout(opt_tab)

        opt_layout.setSpacing(5)

        opt_layout.setContentsMargins(5, 5, 5, 5)

        scan_group = CertusCard("Spectral Scanning Range")

        scan_layout = scan_group.body

        self._create_line_edits(
            scan_layout,
            [
                ("wl_range_start", "Spectral Range Start (nm):"),
                ("wl_range_end", "Spectral Range End (nm):"),
                (
                    "wl_step",
                    "Spectral Step (nm):",
                ),
                ("extrema_exclusion_ratio", "Extrema Exclusion Ratio (1:X):"),
            ],
        )

        opt_layout.addWidget(scan_group)

        # Spectral Scanning tooltips

        _tips_scan = {
            "wl_range_start": "Start of the optical simulation wavelength range (nm). Must be within the available dispersive data range for H and L materials.",
            "wl_range_end": "End of the optical simulation wavelength range (nm).",
            "wl_step": "Spectral step (nm) used to build the simulation grid. Smaller = more precise but slower.",
            "extrema_exclusion_ratio": "Ratio 1:X - exclude 1 in X extremum from monitoring candidates to avoid crowded regions near turning points.",
        }

        for _k, _tip in _tips_scan.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        filter_group = CertusCard("Candidate Filtering")

        filter_layout = filter_group.body

        self._create_line_edits(
            filter_layout,
            [
                ("scan_wl_min", "Candidate lambda Min (nm):"),
                ("scan_wl_max", "Candidate lambda Max (nm):"),
                ("scan_wl_step", "Candidate lambda Step (nm):"),
                ("dynamics_threshold", "Dynamics Threshold:"),
                ("min_transmission_floor", "Min Transmission Floor (0-1, e.g. 0.10):"),
                ("min_spectral_resolution", "Min Spectral Resolution (nm):"),
            ],
        )

        opt_layout.addWidget(filter_group)

        # Candidate Filtering tooltips

        _tips_filter = {
            "scan_wl_min": "Minimum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_max": "Maximum wavelength (nm) allowed as a monitoring candidate for blocks.",
            "scan_wl_step": "Step (nm) between candidate monitoring wavelengths during the DP scan.",
            "dynamics_threshold": "Minimum peak-to-valley transmission dynamics required for a candidate wavelength to be retained (unitless, 0-1).",
            "min_transmission_floor": "Minimum absolute transmission T required at a candidate wavelength (0-1). Excludes opaque regions.",
            "min_spectral_resolution": "Minimum allowed spectral resolution (nm) at a candidate wavelength. Below this, the optical signal is too noisy to be usable.",
        }

        for _k, _tip in _tips_filter.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        loop_group = CertusCard("Iteration Parameters (Nb Layers / X)")

        loop_layout = loop_group.body

        self._create_line_edits(
            loop_layout,
            [
                ("iter_divider_start", "Start Divider (Low Complexity) [N / X]:"),
                ("iter_divider_end", "End Divider (High Complexity) [N / X]:"),
                ("screening_mc_runs", "Screening MC Runs (Pre-selection):"),
                ("screening_keep_top_k", "Keep Top K Strategies per Config:"),
                ("mc_runs_block", "MC Runs per layer test (Phase A):"),
                ("strategy_phase_timeout", "Max Time per Iteration (sec):"),
            ],
        )

        opt_layout.addWidget(loop_group)

        # Iteration Parameters tooltips

        _tips_loop = {
            "iter_divider_start": "Low-complexity limit: the search starts with stacks of N/X layers per block iteration (X = this value). Lower X = finer search.",
            "iter_divider_end": "High-complexity limit: as stacks grow large, divides the iteration count. Higher X = faster but coarser.",
            "screening_mc_runs": "Number of Monte Carlo runs for the pre-selection screening phase. More = better filtering but slower.",
            "screening_keep_top_k": "Number of top strategies retained per configuration after screening before deep evaluation.",
            "mc_runs_block": "Monte Carlo runs per candidate block test in Phase A. Drives early robustness estimation.",
            "strategy_phase_timeout": "Maximum wall-clock time (seconds) allowed per iteration. The engine cancels the current pass if exceeded.",
        }

        for _k, _tip in _tips_loop.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sim_group = CertusCard("Simulation Parameters")

        sim_layout = sim_group.body

        self._create_line_edits(
            sim_layout,
            [
                ("thickness_tolerance_nm", "Thickness Tolerance (+/- nm):"),
                (
                    "trigger_tolerance",
                    "Trigger Tolerance (noise) %:",
                ),  # Kept for backward compat / relative
                ("mse_tolerance_limit_pct", "MSE Filtering Tolerance (Best +/- %):"),
                ("non_monotonic_error_factor", "Non-Monotonic Error Gain Factor:"),
                (
                    "wavelength_change_penalty",
                    "Penalty on Wavelength Change (x factor):",
                ),
            ],
        )

        # Noise distribution selector

        noise_dist_layout = QHBoxLayout()

        noise_dist_layout.addWidget(QLabel("Noise Distribution:"))

        self.widgets["noise_distribution"] = QComboBox()

        self.widgets["noise_distribution"].addItems(["gaussian"])

        self.widgets["noise_distribution"].setCurrentText("gaussian")

        self.widgets["noise_distribution"].setEnabled(False)

        self.widgets["noise_distribution"].setToolTip("Gaussian-only policy enabled for STRAT.")

        noise_dist_layout.addWidget(self.widgets["noise_distribution"])

        noise_dist_layout.addStretch()

        sim_layout.addLayout(noise_dist_layout)

        # Non-monotonic mode selector

        nm_mode_layout = QHBoxLayout()

        nm_mode_layout.addWidget(QLabel("Non-Monotonic Mode:"))

        self.widgets["non_monotonic_mode"] = QComboBox()

        self.widgets["non_monotonic_mode"].addItems(["attenuate", "reject"])

        self.widgets["non_monotonic_mode"].setToolTip(
            "attenuate: Divide error by factor (legacy)\nreject: Penalize non-monotonic zones (stricter)"
        )

        nm_mode_layout.addWidget(self.widgets["non_monotonic_mode"])

        nm_mode_layout.addStretch()

        sim_layout.addLayout(nm_mode_layout)

        opt_layout.addWidget(sim_group)

        # Simulation Parameters tooltips

        _tips_sim = {
            "thickness_tolerance_nm": "Gaussian noise standard deviation (+/- nm) applied to each layer thickness during Monte Carlo simulations.",
            "trigger_tolerance": "Relative trigger tolerance (% of thickness) used to define the optical trigger acceptance window.",
            "mse_tolerance_limit_pct": "MSE filtering tolerance: retain candidates within Best MSE × (1 + this %). Filters out poor strategies early.",
            "non_monotonic_error_factor": "Penalty multiplier applied to the RMSE when the growth curve is non-monotonic in the monitoring window.",
            "wavelength_change_penalty": "Cost multiplier applied each time the monitoring wavelength changes between consecutive blocks. Rewards single-wavelength strategies.",
        }

        for _k, _tip in _tips_sim.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # Reports Group

        report_group = CertusCard("Reports & Data")

        report_layout = QHBoxLayout()

        report_group.body.addLayout(report_layout)

        self.btn_open_reports = QPushButton("📂 Open Reports Folder")

        self.btn_open_reports.setToolTip("Open the folder containing HTML/Excel reports")

        self.btn_open_reports.clicked.connect(lambda: open_file_explorer(get_resource_path("reports")))

        report_layout.addWidget(self.btn_open_reports)

        opt_layout.addWidget(report_group)

        opt_layout.addStretch()

    def detach_stack_window(self) -> None:

        if self._floating_stack_window is not None:
            return

        self.detach_btn.setVisible(False)

        table = self.widgets["stack_table"]

        table.setMinimumWidth(0)

        table.setMaximumWidth(16777215)

        table.setMinimumHeight(0)

        table.setMaximumHeight(16777215)

        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._floating_stack_window = PopOutWindow(self.stack_group, self, "Stack Definition Manager")

        self._floating_stack_window.resize(600, 800)

        self._floating_stack_window.closed_signal.connect(self.reattach_stack_window)

        self._floating_stack_window.show()

    def reattach_stack_window(self) -> None:

        count = self.design_layout.count()

        self.design_layout.insertWidget(count - 1, self.stack_group)

        table = self.widgets["stack_table"]

        table.setMinimumHeight(115)

        table.setMaximumHeight(150)

        table.setFixedWidth(230)

        table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.detach_btn.setVisible(True)

        self._floating_stack_window = None

    def _create_advanced_tab(self) -> None:

        adv_tab = QWidget()

        self.tabs.addTab(adv_tab, "Advanced")

        adv_layout = QVBoxLayout(adv_tab)

        adv_layout.setSpacing(5)

        adv_layout.setContentsMargins(5, 5, 5, 5)

        robust_group = CertusCard("Robustness Test (Step 3)")

        robust_layout = robust_group.body

        self._create_line_edits(
            robust_layout,
            [
                ("robustness_noise_factors", "Noise Factors (e.g., 0.5,1,2):"),
                ("robustness_num_runs", "Number of Runs (Validation):"),
            ],
        )

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("Execution Mode:"))

        self.widgets["execution_mode"] = QComboBox()

        self.widgets["execution_mode"].addItems(["premium", "fast"])

        self.widgets["execution_mode"].setCurrentText("premium")

        self.widgets["execution_mode"].setToolTip(
            "premium: maximum quality\nfast: ~4x faster with reduced MC/consensus/elite budget"
        )

        mode_layout.addWidget(self.widgets["execution_mode"])

        mode_layout.addStretch()

        robust_layout.addLayout(mode_layout)

        adv_layout.addWidget(robust_group)

        # Robustness tooltips

        _tips_robust = {
            "robustness_noise_factors": "Comma-separated noise factor values (e.g. 0.5,1,2) applied as multipliers on the base thickness noise sigma during final validation runs.",
            "robustness_num_runs": "Number of Monte Carlo simulations in the final robustness validation (Step 3). More = more reliable RMSE/P95 statistics.",
        }

        for _k, _tip in _tips_robust.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        engine_group = CertusCard("Deep Search Engine & Hybridization")

        engine_layout = engine_group.body

        self._create_line_edits(
            engine_layout,
            [
                ("nucleation_mc_runs", "Smart Nucleation MC Runs:"),
                ("mining_candidates_limit", "Mining DP Candidates Limit:"),
                ("n_screen_runs", "Screening Runs (Phase B):"),
                ("k_keep_survivors", "Keep K Survivors per Block:"),
                ("top_k_parents", "Hybridization: Top K Parents:"),
                ("max_fusions_per_parent", "Hybridization: Max Fusions/Parent:"),
            ],
        )

        adv_layout.addWidget(engine_group)

        # Deep Search Engine tooltips

        _tips_engine = {
            "nucleation_mc_runs": "MC runs used by the Smart Nucleation phase to evaluate the first-block quality before committing to a wavelength.",
            "mining_candidates_limit": "Maximum number of DP candidate strategies extracted from the cost map during Phase A mining.",
            "n_screen_runs": "MC runs per candidate in Phase B (screening). More = better pre-ranking but slower.",
            "k_keep_survivors": "Number of top-K candidates kept after each Phase B screening pass before deep evaluation.",
            "top_k_parents": "Hybridization: number of parent strategies combined to generate hybrid offspring.",
            "max_fusions_per_parent": "Hybridization: maximum number of hybrid offspring generated per parent pair.",
        }

        for _k, _tip in _tips_engine.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        limits_group = CertusCard("Physical Limits & Search Depth")

        limits_layout = limits_group.body

        self._create_line_edits(
            limits_layout,
            [
                ("phase_a_scan_limit", "Phase A: Scan Depth (Candidates):"),
                ("phase_a_keep_limit", "Phase A: Max Retained Candidates:"),
                ("nucleation_max_rmse", "Nucleation: Max RMSE (nm):"),
                ("nucleation_degradation", "Nucleation: Degradation Thresh. (Ratio):"),
                ("step0_sigma", "Step 1: Preview Noise Sigma (nm):"),
            ],
        )

        adv_layout.addWidget(limits_group)

        # Physical Limits tooltips

        _tips_limits = {
            "phase_a_scan_limit": "Phase A: maximum number of candidate wavelengths evaluated per block iteration.",
            "phase_a_keep_limit": "Phase A: maximum number of candidates retained after scanning before Phase B screening.",
            "nucleation_max_rmse": "Nucleation: maximum acceptable RMSE (nm) for a nucleation wavelength to be accepted.",
            "nucleation_degradation": "Nucleation: if the RMSE degrades by more than this ratio vs. the reference, the nucleation attempt is rejected.",
            "step0_sigma": "Step 1 (Nominal preview): Gaussian sigma (nm) applied to simulate a quick noise preview without full Monte Carlo.",
        }

        for _k, _tip in _tips_limits.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        sym_group = CertusCard("SYM Strategy Controls")

        sym_layout = sym_group.body

        self._create_line_edits(
            sym_layout,
            [
                ("sym_enable", "Enable SYM (0/1):"),
                ("sym_weight", "SYM Weight:"),
                ("sym_same_wl_bonus", "SYM Same-WL Bonus:"),
                ("sym_extrema_window", "SYM Extrema Window (OT nm):"),
                ("sym_continuity_weight", "SYM Continuity Weight:"),
                ("sym_adaptive_same_wl", "SYM Adaptive Same-WL (0/1):"),
                ("sym_allow_hybrid", "SYM Allow Hybrid Double-Score (0/1):"),
                ("sym_prefer_on_tie", "SYM Prefer on Tie (0/1):"),
                ("sym_tie_epsilon", "SYM Tie Epsilon Abs:"),
                ("sym_tie_epsilon_rel", "SYM Tie Epsilon Rel:"),
            ],
        )

        # SYM advanced field tooltips

        _tips_sym = {
            "sym_weight": "Global weight applied to the SYM score when combining it with the RMSE score. Higher = more symmetric strategies favored.",
            "sym_same_wl_bonus": "Bonus awarded when two consecutive blocks use the same monitoring wavelength.",
            "sym_extrema_window": "Optical thickness window (nm) around extrema within which candidate points qualify for SYM scoring.",
            "sym_continuity_weight": "Weight applied to reward monotonically continuous growth curves in the SYM metric.",
            "sym_adaptive_same_wl": "Enable (1) adaptive same-wavelength bonus that scales with observability quality.",
            "sym_allow_hybrid": "Allow (1) the same strategy to accumulate both a SYM score and an RMSE score simultaneously (double-score mode).",
            "sym_prefer_on_tie": "On tied RMSE score (within epsilon), prefer (1) the strategy with the better SYM score.",
            "sym_tie_epsilon": "Absolute RMSE tolerance below which two strategies are considered tied (to trigger SYM tie-break).",
            "sym_tie_epsilon_rel": "Relative RMSE tolerance (fraction of the best RMSE) for tie-breaking.",
        }

        for _k, _tip in _tips_sym.items():
            if _k in self.widgets:
                self.widgets[_k].setToolTip(_tip)

        # SYM est une strategie supplementaire obligatoire: toujours activee.

        if "sym_enable" in self.widgets:
            self.widgets["sym_enable"].setText("1")

            self.widgets["sym_enable"].setReadOnly(True)

            self.widgets["sym_enable"].setToolTip("Always active (supplementary strategy)")

        mode_layout = QHBoxLayout()

        mode_layout.addWidget(QLabel("SYM Scoring Mode:"))

        self.widgets["sym_scoring_mode"] = QComboBox()

        self.widgets["sym_scoring_mode"].addItems(["post", "pre", "hybrid"])

        self.widgets["sym_scoring_mode"].setCurrentText(SYM_DEFAULT_SCORING_MODE)

        self.widgets["sym_scoring_mode"].setToolTip(
            "post: SYM score is applied after ranking by RMSE (default).\n"
            "pre: SYM score influences block selection during DP search.\n"
            "hybrid: SYM score applied both during and after search."
        )

        mode_layout.addWidget(self.widgets["sym_scoring_mode"])

        mode_layout.addStretch()

        sym_layout.addLayout(mode_layout)

        adv_layout.addWidget(sym_group)

        adv_layout.addStretch()

    def _create_why_certus_tab(self) -> None:
        """Creates Why CERTUS? tab with FlashyCards matching INDEX/METAL/DESIGN style"""

        perf_tab = QWidget()

        self.tabs.addTab(perf_tab, "Why CERTUS?")

        perf_layout = QGridLayout(perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "High-Rate Monte Carlo",
            "Simulation of deposition dispersions\nRapid evaluation of real-world robustness",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Error Compensation",
            "Auto-compensated wavelengths\nMaintains performance under perturbations",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Dynamic Programming",
            "Block selection by global cost\nStructured, scalable, and traceable search",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Robust Statistical Validation",
            "Multi-noise stress tests + RMSE scoring\nReliable ranking of manufacturable strategies",
            icon="🔮",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

    def _create_material_group(self, parent_layout, title, prefix, label, _is_compact=False) -> None:

        group = CertusCard(title)

        layout = group.body

        layout.setSpacing(2)

        layout.setContentsMargins(4, 12, 4, 4)

        radio_layout = QHBoxLayout()

        self.widgets[f"{prefix}_type_custom"] = QRadioButton("Custom (Constant)")

        self.widgets[f"{prefix}_type_custom"].setChecked(True)  # Default to Custom mode

        self.widgets[f"{prefix}_type_file"] = QRadioButton("Dispersive (File)")

        grp = QButtonGroup(self)

        grp.addButton(self.widgets[f"{prefix}_type_custom"])

        grp.addButton(self.widgets[f"{prefix}_type_file"])

        grp.setExclusive(True)

        radio_layout.addWidget(self.widgets[f"{prefix}_type_custom"])

        radio_layout.addWidget(self.widgets[f"{prefix}_type_file"])

        radio_layout.addStretch()

        layout.addLayout(radio_layout)

        combined_layout = QHBoxLayout()

        self.widgets[f"n{label}_r"] = QLineEdit()

        self.widgets[f"n{label}_r"].setPlaceholderText("e.g. 2.3")

        self.widgets[f"n{label}_r"].setFixedWidth(50)

        self.widgets[f"n{label}_r"].setToolTip(
            "Fixed real part of the refractive index n (constant, wavelength-independent).\n"
            "Active only in 'Custom' mode."
        )

        combined_layout.addWidget(QLabel("n (real):"))

        combined_layout.addWidget(self.widgets[f"n{label}_r"])

        combined_layout.addSpacing(10)

        self.widgets[f"{prefix}_material_file"] = QComboBox()

        self.widgets[f"{prefix}_material_file"].addItems(self.material_list)

        self.widgets[f"{prefix}_material_file"].setToolTip(
            "Dispersive material file from the clues database (wavelength-dependent n & k).\n"
            "Active only in 'Dispersive (File)' mode."
        )

        combined_layout.addWidget(QLabel("Material File:"))

        combined_layout.addWidget(self.widgets[f"{prefix}_material_file"], 1)

        layout.addLayout(combined_layout)

        # Connect toggle signals to enable/disable widgets

        self.widgets[f"{prefix}_type_custom"].toggled.connect(
            lambda checked, p=prefix, l=label: self._on_material_mode_changed(p, l)
        )

        parent_layout.addWidget(group)

    def _on_material_mode_changed(self, prefix, label) -> None:
        """Enable/disable widgets based on Custom vs Dispersive selection."""

        is_custom = self.widgets[f"{prefix}_type_custom"].isChecked()

        self.widgets[f"n{label}_r"].setEnabled(is_custom)

        self.widgets[f"{prefix}_material_file"].setEnabled(not is_custom)

    def _on_substrate_choice_changed(self, text) -> None:
        """Enable custom index field only when 'Custom' substrate is selected."""

        is_custom = text == "Custom"

        self.widgets["nSub_custom"].setEnabled(is_custom)

    def _extract_stack_multipliers(self, config: dict[str, Any]) -> list[float]:
        """Return normalized stack multipliers from multiple legacy JSON shapes."""
        raw = config.get("stack_multipliers")
        if raw is None:
            raw = config.get("stack_string")
        if raw is None:
            raw = config.get("stack")
        if raw is None:
            return []
        if isinstance(raw, str):
            tokens = [t.strip() for t in raw.replace("[", "").replace("]", "").split(",") if t.strip()]
            out: list[float] = []
            for tok in tokens:
                try:
                    out.append(float(tok))
                except (TypeError, ValueError):
                    continue
            return out
        if isinstance(raw, (list, tuple)):
            out = []
            for val in raw:
                try:
                    out.append(float(val))
                except (TypeError, ValueError):
                    continue
            return out
        return []


    def _init_widget_states(self) -> None:
        """Initialize enable/disable states for all mode-dependent widgets."""

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

    def _create_line_edits(self, layout, items, columns=2) -> None:

        grid = QGridLayout()

        grid.setHorizontalSpacing(5)

        grid.setVerticalSpacing(2)

        rows = (len(items) + columns - 1) // columns

        for idx, (key, label_text) in enumerate(items):
            col_block = idx // rows

            row = idx % rows

            lbl = QLabel(label_text)

            edit = QLineEdit()

            self.widgets[key] = edit

            grid.addWidget(lbl, row, col_block * 2)

            grid.addWidget(edit, row, col_block * 2 + 1)

        for c in range(columns):
            grid.setColumnStretch(c * 2 + 1, 1)

        layout.addLayout(grid)

    def _init_undo_shortcut(self) -> None:
        """Initializes the UNDO shortcut after the interface is ready"""

        try:
            undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)

            undo_shortcut.activated.connect(self._undo_stack_table)

        except (RuntimeError, TypeError, AttributeError) as e:
            self.logger.warning(f"Could not initialize UNDO shortcut: {e}")

    def _on_stack_table_changed(self, row, col) -> None:
        """Callback called when a cell in stack_table is modified"""

        # Save state only if it is the Multiplier column (col 2)

        if col == 2:
            self._save_undo_state()

    def _save_undo_state(self) -> None:
        """Save current state of stack_table for undo"""

        # Verify undo_stack exists (might not be initialized at start)

        if not hasattr(self, "undo_stack"):
            self.undo_stack = deque(maxlen=5)

        table = self.widgets.get("stack_table")

        if table is None:
            return

        state = []

        for row in range(table.rowCount()):
            mult_item = table.item(row, 2)

            mult_val = mult_item.text() if mult_item else "1.0"

            state.append(mult_val)

        if state:
            self.undo_stack.append(state.copy())

    def _undo_stack_table(self) -> None:
        """Undo the last modification of the stack_table"""

        # Verify that undo_stack existe

        if not hasattr(self, "undo_stack") or not self.undo_stack:
            self.logger.warning("No undo state available")

            return

        state = self.undo_stack.pop()

        table = self.widgets.get("stack_table")

        if table is None:
            return

        table.blockSignals(True)

        # Adjust number of rows if necessary (without saving to undo_stack)

        while table.rowCount() < len(state):
            row = table.rowCount()

            table.insertRow(row)

            item_num = QTableWidgetItem(str(row + 1))

            item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, item_num)

            type_str = "H" if row % 2 == 0 else "L"

            item_type = QTableWidgetItem(type_str)

            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 1, item_type)

            table.setItem(row, 2, QTableWidgetItem("1.0"))

        while table.rowCount() > len(state):
            table.removeRow(table.rowCount() - 1)

        # Restore values

        for row, mult_val in enumerate(state):
            mult_item = table.item(row, 2)

            if mult_item:
                mult_item.setText(str(mult_val))

        table.blockSignals(False)

        self.logger.info(f"Undo: Restored {len(state)} layers")

    def add_layer(self) -> None:

        self._save_undo_state()

        table = self.widgets["stack_table"]

        row = table.rowCount()

        table.insertRow(row)

        item_num = QTableWidgetItem(str(row + 1))

        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 0, item_num)

        type_str = "H" if row % 2 == 0 else "L"

        item_type = QTableWidgetItem(type_str)

        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 1, item_type)

        table.setItem(row, 2, QTableWidgetItem("1.0"))

    def remove_layer(self) -> None:

        table = self.widgets["stack_table"]

        if table.rowCount() > 0:
            self._save_undo_state()

            table.removeRow(table.rowCount() - 1)

    def set_default_values(self) -> None:

        stack_string = "0.376863,0.544274,0.525625,2.014363,1.404237,1.260913,2.108868,1.619996,1.661556,1.051359,1.410965,0.96871,1.000151,0.812025,0.723532,0.679077,0.749945,0.697612,0.590237,0.654072,0.756165,0.854369,0.892505,1.147616,0.196934,0.801568,0.692039,0.793093,0.732264,0.62781,0.700873,0.742287,0.74316,0.161261,1.028982,1.563076,0.726649,0.325847,0.844091,0.496665,0.585217,0.149928,0.54806,0.302789,0.439372,1.355508"

        multipliers = [m.strip() for m in stack_string.split(",")]

        defaults = {
            "h_type_custom": True,
            "l_type_custom": True,
            "nH_r": "2.3",
            "nL_r": "1.45",
            "substrate_choice": "Custom",
            "nSub_custom": "1.73",
            "l0": "1500.0",
            "stack_multipliers": multipliers,
            "wl_range_start": "1200.0",
            "wl_range_end": "1700.0",
            "wl_step": "0.2",
            "scan_wl_min": "1200.0",
            "scan_wl_max": "1700.0",
            "scan_wl_step": "2.0",
            "dynamics_threshold": "0.025",
            "min_transmission_floor": "0.10",
            "min_spectral_resolution": "1.0",
            "iter_divider_start": "10",
            "iter_divider_end": "3",
            "screening_mc_runs": "20",
            "screening_keep_top_k": "5",
            "mc_runs_block": "100",
            "strategy_phase_timeout": "120",
            "trigger_tolerance": "0.1",
            "noise_distribution": "gaussian",
            "non_monotonic_mode": "attenuate",
            "sim_thickness_probe_offset_ratio": "80.0",
            "robustness_noise_factors": "0.5,1,2",
            "robustness_num_runs": "150",
            "execution_mode": "premium",
            "non_monotonic_error_factor": "2.0",
            "wavelength_change_penalty": "1.2",
            "force_first_layer_same_wl": False,
            "extrema_exclusion_ratio": "60.0",
            "nucleation_mc_runs": "40",
            "mining_candidates_limit": "3000",
            "n_screen_runs": "25",
            "k_keep_survivors": "10",
            "top_k_parents": "20",
            "max_fusions_per_parent": "5",
            "phase_a_scan_limit": "300",
            "phase_a_keep_limit": "50",
            "nucleation_max_rmse": "1.5",
            "nucleation_degradation": "1.4",
            "step0_sigma": "1.0",
            "sym_enable": "1",
            "sym_weight": f"{SYM_DEFAULT_WEIGHT}",
            "sym_same_wl_bonus": f"{SYM_DEFAULT_SAME_WL_BONUS}",
            "sym_extrema_window": f"{SYM_DEFAULT_EXTREMA_WINDOW_OT}",
            "sym_continuity_weight": f"{SYM_DEFAULT_CONTINUITY_WEIGHT}",
            "sym_adaptive_same_wl": "1",
            "sym_allow_hybrid": "0",
            "sym_prefer_on_tie": "1",
            "sym_tie_epsilon": f"{SYM_DEFAULT_TIE_EPS_ABS}",
            "sym_tie_epsilon_rel": f"{SYM_DEFAULT_TIE_EPS_REL}",
            "sym_scoring_mode": SYM_DEFAULT_SCORING_MODE,
            "show_plots": True,
            "export_excel": True,
        }

        self.populate_gui_from_config(defaults)

    def populate_gui_from_config(self, config: dict[str, Any]) -> None:
        """Populate GUI widgets from configuration dictionary.

        Order is critical:

        1. Set radio button states (determines which widgets will be enabled)

        2. Set ALL widget values first (including potentially disabled ones)

        3. Apply enable/disable states LAST

        """

        # Historical aliases from older example JSON payloads.
        if isinstance(config, dict):
            if "substratee_choice" in config and config.get("substrate_choice") is None:
                config["substrate_choice"] = config.get("substratee_choice")
            if "substrate_choice" in config and config.get("substratee_choice") is None:
                config["substratee_choice"] = config.get("substrate_choice")

            # Map Silice config value to standard SiO2 combo item
            if config.get("substrate_choice") == "Silice":
                config["substrate_choice"] = "SiO2"
                config["substratee_choice"] = "SiO2"

        # Step 1: Set radio button states

        self.widgets["h_type_custom"].setChecked(bool(config.get("h_type_custom", True)))

        self.widgets["h_type_file"].setChecked(not config.get("h_type_custom", True))

        self.widgets["l_type_custom"].setChecked(bool(config.get("l_type_custom", True)))

        self.widgets["l_type_file"].setChecked(not config.get("l_type_custom", True))

        # Step 2: Set ALL widget values (before enabling/disabling)

        for key, widget in self.widgets.items():
            if isinstance(widget, QLineEdit) and key in config:
                widget.setText(str(config[key]))

        for combo_key in [
            "h_material_file",
            "l_material_file",
            "substrate_choice",
            "noise_distribution",
            "non_monotonic_mode",
            "sym_scoring_mode",
            "execution_mode",
        ]:
            if combo_key in self.widgets and combo_key in config and config[combo_key]:
                idx = self.widgets[combo_key].findText(str(config[combo_key]))

                if idx >= 0:
                    self.widgets[combo_key].setCurrentIndex(idx)

        # Step 3: Apply enable/disable states LAST

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

        # Step 4: Handle stack table

        stack_mults = None

        if "stack_multipliers" in config:
            raw_mults = config["stack_multipliers"]

            if isinstance(raw_mults, list):
                stack_mults = []

                for i, val in enumerate(raw_mults):
                    try:
                        stack_mults.append(float(val))

                    except (ValueError, TypeError):
                        stack_mults.append(1.0)

        elif "stack_string" in config:
            try:
                stack_mults = [float(m.strip()) for m in str(config["stack_string"]).split(",") if m.strip()]

            except (ValueError, TypeError):
                stack_mults = None

        if stack_mults:
            try:
                table = self.widgets.get("stack_table")

                if table:
                    table.setEnabled(True)

                    table.setRowCount(0)

                    for i, m in enumerate(stack_mults):
                        table.insertRow(i)

                        item_num = QTableWidgetItem(str(i + 1))

                        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 0, item_num)

                        item_type = QTableWidgetItem("H" if i % 2 == 0 else "L")

                        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 1, item_type)

                        table.setItem(i, 2, QTableWidgetItem(f"{float(m):.6f}"))

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error populating table: {e}")

    @safe_ui_action
    def save_configuration(self) -> None:
        """Save current GUI configuration to a JSON file.

        Only saves relevant data based on selected modes:

        - If Custom mode: saves index value (nH_r/nL_r)

        - If Dispersive mode: saves material file selection

        - substrate custom index only saved if 'Custom' substrate selected

        """

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not filename:
            return

        set_certus_last_dir(filename)

        try:
            config = {
                "h_type_custom": self.widgets["h_type_custom"].isChecked(),
                "l_type_custom": self.widgets["l_type_custom"].isChecked(),
                "substrate_choice": self.widgets["substrate_choice"].currentText(),
                "l0": self.widgets["l0"].text(),
            }

            # Save only relevant H-index data

            if self.widgets["h_type_custom"].isChecked():
                config["nH_r"] = self.widgets["nH_r"].text()

            else:
                config["h_material_file"] = self.widgets["h_material_file"].currentText()

            # Save only relevant L-index data

            if self.widgets["l_type_custom"].isChecked():
                config["nL_r"] = self.widgets["nL_r"].text()

            else:
                config["l_material_file"] = self.widgets["l_material_file"].currentText()

            # Save custom substrate only if "Custom" is selected

            if self.widgets["substrate_choice"].currentText() == "Custom":
                config["nSub_custom"] = self.widgets["nSub_custom"].text()

            table = self.widgets["stack_table"]

            stack_multipliers = []

            for row in range(table.rowCount()):
                item = table.item(row, 2)

                if item:
                    try:
                        stack_multipliers.append(float(item.text()))

                    except ValueError:
                        stack_multipliers.append(1.0)

            config["stack_multipliers"] = stack_multipliers

            for key in [
                "wl_range_start",
                "wl_range_end",
                "wl_step",
                "scan_wl_min",
                "scan_wl_max",
                "scan_wl_step",
                "dynamics_threshold",
                "min_transmission_floor",
                "min_spectral_resolution",
                "mc_runs_block",
                "iter_divider_start",
                "iter_divider_end",
                "strategy_phase_timeout",
                "screening_mc_runs",
                "screening_keep_top_k",
                "trigger_tolerance",
                "sim_thickness_probe_offset_ratio",
                "non_monotonic_error_factor",
                "wavelength_change_penalty",
                "extrema_exclusion_ratio",
                "robustness_noise_factors",
                "robustness_num_runs",
                "nucleation_mc_runs",
                "mining_candidates_limit",
                "n_screen_runs",
                "k_keep_survivors",
                "top_k_parents",
                "max_fusions_per_parent",
                "phase_a_scan_limit",
                "phase_a_keep_limit",
                "nucleation_max_rmse",
                "nucleation_degradation",
                "step0_sigma",
                "sym_enable",
                "sym_weight",
                "sym_same_wl_bonus",
                "sym_extrema_window",
                "sym_continuity_weight",
                "sym_adaptive_same_wl",
                "sym_allow_hybrid",
                "sym_prefer_on_tie",
                "sym_tie_epsilon",
                "sym_tie_epsilon_rel",
            ]:
                if key in self.widgets:
                    config[key] = self.widgets[key].text()

            # Save ComboBox values

            if "noise_distribution" in self.widgets:
                config["noise_distribution"] = self.widgets["noise_distribution"].currentText()

            if "non_monotonic_mode" in self.widgets:
                config["non_monotonic_mode"] = self.widgets["non_monotonic_mode"].currentText()

            if "sym_scoring_mode" in self.widgets:
                config["sym_scoring_mode"] = self.widgets["sym_scoring_mode"].currentText()

            if "execution_mode" in self.widgets:
                config["execution_mode"] = self.widgets["execution_mode"].currentText()

            config["show_plots"] = True

            config["export_excel"] = True

            config["force_first_layer_same_wl"] = True

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.logger.info(f"Configuration saved: '{filename}'")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error saving: {e}")

    @safe_ui_action
    def load_configuration(self, filename=None) -> None:
        """Load configuration from a JSON file and populate the GUI.

        Handles both new format (stack_multipliers list) and legacy format (stack_string).

        Opens a JSON viewer window for inspection after loading.

        Args:

            filename: Optional path to JSON file. If None, opens file dialog.

        """

        if filename is None or isinstance(filename, bool):
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", get_certus_last_dir(), "JSON Files (*.json)"
            )

        if not filename:
            return

        set_certus_last_dir(filename)

        self._last_config_file = filename

        try:
            with open(filename, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise ValueError("Configuration JSON must be an object/dictionary.")
            try:
                validated = StratConfigDTO.model_validate(config)
                config = validated.model_dump(mode="python", exclude_none=False)
            except ValidationError as e:
                msg = f"Invalid STRAT configuration: {e}"
                self.logger.error(msg)
                QMessageBox.critical(self, "Invalid configuration", msg)
                return

            self._loaded_config = dict(config)

            if "stack_string" in config and "stack_multipliers" not in config:
                try:
                    config["stack_multipliers"] = [
                        float(m) for m in str(config["stack_string"]).split(",") if m.strip()
                    ]

                except (ValueError, TypeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            self.populate_gui_from_config(config)

            short_name = Path(filename).name

            viewer = JsonViewerWindow(self, f"Config - {short_name}", config)

            viewer.show()

            viewer.raise_()

            viewer.activateWindow()

            if not hasattr(self, "json_windows"):
                self.json_windows = []

            self.json_windows.append(viewer)

            self.logger.info("=" * 60)

            self.logger.info(f"CONFIGURATION LOADED: {short_name}")

            self.logger.info("=" * 60)

            for key in sorted(config.keys()):
                val = config[key]

                if isinstance(val, list) and len(val) > 10:
                    val_str = f"{val[:3]} ... ({len(val)} items) ...  {val[-3:]}"

                else:
                    val_str = str(val)

                self.logger.info(f"  {key:<35}: {val_str}")

            self.logger.info("=" * 60)

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                blocks = config.get("blocks") or [] if isinstance(config, dict) else []

                strat_id = str(config.get("strategy_id", "")).strip()

                n_blocks = int(config.get("n_blocks") or len(blocks)) if isinstance(config, dict) else 0

                # Two formats: (1) GUI session via save_configuration - no strategy_id/blocks;

                # (2) export mined strategy / external JSON - strategy_id + blocks required.

                is_session_cfg = isinstance(config, dict) and (
                    "stack_multipliers" in config or "h_material_file" in config
                )

                sub_label = "UNKNOWN"

                if isinstance(config, dict):
                    sub_label = str(config.get("substrate_choice", "UNKNOWN")).strip() or "UNKNOWN"

                summary_lines: list = [
                    f"SUBSTRATE: {sub_label}",
                    "FACES: ONE FACE (NO BACKSIDE)",
                    "",
                    f"File: {Path(filename).resolve()}",
                    "",
                ]

                if is_session_cfg and not (strat_id and isinstance(blocks, list) and len(blocks) > 0):
                    n_lay = len(config.get("stack_multipliers", [])) if isinstance(config, dict) else 0

                    summary_lines.extend(
                        [
                            "Format: GUI session (save_configuration)",
                            "  -> Material parameters, stack (multipliers), execution options.",
                            "  -> The strategy_id / blocks keys are not part of this format (normal).",
                            "  -> To load mined strategies: 'external strategies' menu / dedicated JSON.",
                            "",
                            "Structure (session)",
                            f"  stack_multipliers count (layers): {n_lay}",
                            "",
                            "Embedded Strategy",
                            "  (not present - this file is not a mined strategy export)",
                        ]
                    )

                else:
                    summary_lines.extend(
                        [
                            "General",
                            f"Strategy ID: {strat_id or '(missing)'}",
                            "",
                            "Structure",
                            (f"n_blocks: {n_blocks}", n_blocks <= 0),
                            (
                                f"blocks entries: {len(blocks) if isinstance(blocks, list) else 0}",
                                not isinstance(blocks, list) or len(blocks) == 0,
                            ),
                            "",
                            "Compatibility checks",
                            f"Keys in JSON: {len(config.keys()) if isinstance(config, dict) else 0}",
                            (
                                f"Contains required keys (strategy_id, blocks): {'yes' if ('strategy_id' in config and 'blocks' in config) else 'no'}",
                                not ("strategy_id" in config and "blocks" in config),
                            ),
                        ]
                    )

                summary = build_summary_plain_text("CERTUS STRAT - Config Summary", summary_lines)

                show_load_summary_dialog(self, "STRAT Load Summary", summary)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error loading: {e}\n{traceback.format_exc()}")

    def load_external_strategies(self) -> None:

        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Strategy Files", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not files:
            return

        set_certus_last_dir(files[0])

        loaded_strategies = []

        REQUIRED_KEYS = {"strategy_id", "blocks"}

        table = self.widgets.get("stack_table")

        expected_layers = table.rowCount() if table is not None else 0

        expected_layers = max(0, int(expected_layers))

        seen_ids: set[str] = set()

        try:
            for f_path in files:
                with open(f_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)

                    except json.JSONDecodeError:
                        continue

                    def validate_and_add(item) -> None:

                        if not (isinstance(item, dict) and all(k in item for k in REQUIRED_KEYS)):
                            return

                        strat_id = str(item.get("strategy_id", "")).strip()

                        if not strat_id:
                            return

                        if strat_id in seen_ids:
                            return

                        item_norm = dict(item)

                        if "n_blocks" not in item_norm:
                            item_norm["n_blocks"] = len(item_norm.get("blocks", []))

                        # Strong schema + contract validation before running Step 33

                        expected_n = item_norm.get("n_blocks", len(item_norm.get("blocks", [])))

                        if expected_layers > 0:
                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm, expected_layers, expected_n_blocks=expected_n
                            )

                            if not ok:
                                return

                        else:
                            # If no expected layer count is available, still hard-validate block typing.

                            max_end = 0

                            for blk in item_norm.get("blocks", []):
                                if isinstance(blk, dict):
                                    try:
                                        max_end = max(max_end, int(blk.get("end", 0)))

                                    except (TypeError, ValueError):
                                        logging.getLogger("CERTUS").debug(
                                            "Silenced exception in %s", __name__, exc_info=True
                                        )

                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm,
                                num_layers=max(max_end, 1),
                                expected_n_blocks=expected_n,
                            )

                            if not ok:
                                return

                        loaded_strategies.append(item_norm)

                        seen_ids.add(strat_id)

                    if isinstance(data, list):
                        for item in data:
                            validate_and_add(item)

                    else:
                        validate_and_add(data)

            if not loaded_strategies:
                self.logger.warning("No valid strategy found.")

                return

            self.logger.info(f"Loaded {len(loaded_strategies)} valid strategies.")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error parsing strategy files: {e}")

            return

        params = self.collect_params()

        if self.opti_results is None:
            self.logger.info("Initializing context for external strategies (Matrices & Indices)...")

            try:
                nominal_results, _ = calculate_nominal_properties(params)

                p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

                clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                    params, p_thick_nominal, self.logger
                )

                self.opti_results = {
                    "p_thick_nominal": p_thick_nominal,
                    "clues_at_wl": clues_at_wl,
                    "nominal_matrix_cache": nominal_matrix_cache,
                    "all_wls": all_wls,
                    "p_thick_nominal": p_thick_nominal,
                }

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Failed to initialize context: {e}")

                return

        params["loaded_strategies"] = loaded_strategies

        self.progress_bar.setValue(0)

        self.status_label.setText("Simulating Loaded Strategies...")

        for btn in [
            self.run_step0_btn,
            self.run_step2_btn,
            self.run_step3_btn,
            self.run_full_btn,
            self.load_strat_btn,
        ]:
            btn.setEnabled(False)

        self.worker = WorkerThread(
            step=33,
            params=params,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger,
        )

        self.worker.signals.finished.connect(self.on_workflow_finished)

        self.worker.signals.error.connect(self.on_workflow_error)

        self.worker.signals.progress.connect(self.on_progress_update)

        self.worker.signals.plot.connect(self.on_plot_ready)

        self.worker.signals.excel_ready.connect(self.on_excel_ready)

        self.worker.signals.show_strategies_table.connect(self.on_show_strategies_table)

        self.worker.start()

    def _get_float_safe(self, widget_name, default=0.0) -> Any:

        if widget_name not in self.widgets:
            return default

        text = self.widgets[widget_name].text().strip()

        if not text:
            return default

        try:
            return float(text)

        except ValueError:
            return default

    def collect_params(self) -> dict[str, Any]:
        """Collect all GUI parameters into a dictionary for workflow execution.

        Intelligently resolves material clues:

        - Custom mode: uses constant float value from nH_r/nL_r field

        - Dispersive mode: uses material name string for database lookup

        Returns:

            Dict containing all parameters for the simulation workflow."""

        # Resolve H-index: either constant float or material name

        if self.widgets["h_type_custom"].isChecked():
            nH_id = float(self._get_float_safe("nH_r", 2.3))

        else:
            txt = self.widgets["h_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No H-material file selected. Reverting to Custom value (2.3).")

                nH_id = float(self._get_float_safe("nH_r", 2.3))

            else:
                nH_id = txt

        if self.widgets["l_type_custom"].isChecked():
            nL_id = float(self._get_float_safe("nL_r", 1.45))

        else:
            txt = self.widgets["l_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No L-material file selected. Reverting to Custom value (1.45).")

                nL_id = float(self._get_float_safe("nL_r", 1.45))

            else:
                nL_id = txt

        sub_choice = self.widgets["substrate_choice"].currentText()
        if not sub_choice and "substratee_choice" in self.widgets:
            sub_choice = self.widgets["substratee_choice"].currentText()

        material_aliases = {
            "H800-Nb": "H800-Nb",
            "H800 Nb": "H800-Nb",
            "H800_Nb": "H800-Nb",
            "H800-SiO2": "H800-SiO2",
            "H800 SiO2": "H800-SiO2",
            "H800_SiO2": "H800-SiO2",
            "Silice": "SiO2",
        }

        if sub_choice == "Custom" or not sub_choice:
            nSub_id = self._get_float_safe("nSub_custom", 1.73)

        else:
            nSub_id = sub_choice

        table = self.widgets["stack_table"]

        multipliers = [float(table.item(r, 2).text()) for r in range(table.rowCount()) if table.item(r, 2)]

        stack_string = ",".join(map(str, multipliers))

        try:
            noise_str = self.widgets["robustness_noise_factors"].text().strip().replace("[", "").replace("]", "")

            noise_factors = [float(x.strip()) for x in noise_str.split(",") if x.strip()]

        except (ValueError, TypeError):
            noise_factors = [0.5, 1.0, 2.0]

        nH_id = material_aliases.get(str(nH_id).strip(), nH_id)
        nL_id = material_aliases.get(str(nL_id).strip(), nL_id)
        if str(nSub_id).strip() in {"Silice", "SiO2", "H800-SiO2", "H800 SiO2", "H800_SiO2"}:
            nSub_id = "SiO2"
        elif str(nSub_id).strip() in {"Sapphire", "Sapphire (Al2O3)"}:
            nSub_id = "Sapphire (Al2O3)"

        params_out = {
            "nH_id": nH_id,
            "nL_id": nL_id,
            "nSub_id": nSub_id,
            "substrate_choice": sub_choice,
            "l0": self._get_float_safe("l0", 1500.0),
            "stack_string": stack_string,
            "wl_range": (
                self._get_float_safe("wl_range_start", 1200.0),
                self._get_float_safe("wl_range_end", 1700.0),
            ),
            "wl_step": self._get_float_safe("wl_step", 0.2),
            "scan_wl_min": self._get_float_safe("scan_wl_min", 1200.0),
            "scan_wl_max": self._get_float_safe("scan_wl_max", 1700.0),
            "scan_wl_step": self._get_float_safe("scan_wl_step", 2.0),
            "dynamics_threshold": self._get_float_safe("dynamics_threshold", 0.025),
            "min_transmission_floor": self._get_float_safe("min_transmission_floor", 0.10),
            "strict_min_transmission_floor": True,
            "enforce_best_strategy_tmin_check": True,
            "min_spectral_resolution": self._get_float_safe("min_spectral_resolution", 1.0),
            "mc_runs_block": int(self._get_float_safe("mc_runs_block", 100)),
            "iter_divider_start": self._get_float_safe("iter_divider_start", 10.0),
            "iter_divider_end": self._get_float_safe("iter_divider_end", 3.0),
            "screening_mc_runs": int(self._get_float_safe("screening_mc_runs", 20)),
            "screening_keep_top_k": int(self._get_float_safe("screening_keep_top_k", 5)),
            "strategy_phase_timeout": self._get_float_safe("strategy_phase_timeout", 120.0),
            "reality_sim_params": {
                "trigger_tolerance": self._get_float_safe("trigger_tolerance", 0.1),
                "noise_distribution": NOISE_DISTRIBUTION_GAUSSIAN,
            },
            "thickness_tolerance_nm": self._get_float_safe("thickness_tolerance_nm", 1.0),
            "mse_tolerance_limit_pct": self._get_float_safe("mse_tolerance_limit_pct", 30.0),
            # Legacy/Fallback if needed (hidden from GUI by default now if we remove it, but user might have it in old logical flow)
            "sim_thickness_probe_offset_ratio": 80.0,  # Hardcoded fallback or self._get_float_safe("sim_thickness_probe_offset_ratio", 80.0),
            "non_monotonic_error_factor": self._get_float_safe("non_monotonic_error_factor", 2.0),
            "non_monotonic_mode": NON_MONOTONIC_MODE_REJECT
            if self.widgets.get("non_monotonic_mode") and self.widgets["non_monotonic_mode"].currentText() == "reject"
            else NON_MONOTONIC_MODE_ATTENUATE,
            "wavelength_change_penalty": self._get_float_safe("wavelength_change_penalty", 1.2),
            "robustness_noise_factors": noise_factors,
            "robustness_num_runs": int(self._get_float_safe("robustness_num_runs", 150)),
            "nucleation_mc_runs": int(self._get_float_safe("nucleation_mc_runs", 40)),
            "mining_candidates_limit": int(self._get_float_safe("mining_candidates_limit", 3000)),
            "n_screen_runs": int(self._get_float_safe("n_screen_runs", 25)),
            "k_keep_survivors": int(self._get_float_safe("k_keep_survivors", 10)),
            "top_k_parents": int(self._get_float_safe("top_k_parents", 20)),
            "max_fusions_per_parent": int(self._get_float_safe("max_fusions_per_parent", 5)),
            "phase_a_scan_limit": int(self._get_float_safe("phase_a_scan_limit", 300)),
            "phase_a_keep_limit": int(self._get_float_safe("phase_a_keep_limit", 50)),
            "nucleation_max_rmse": self._get_float_safe("nucleation_max_rmse", 1.5),
            "nucleation_degradation": self._get_float_safe("nucleation_degradation", 1.4),
            "step0_sigma": self._get_float_safe("step0_sigma", 1.0),
            "show_plots": True,
            "export_excel": True,
            "extrema_exclusion_ratio": self._get_float_safe("extrema_exclusion_ratio", 60.0),
            "logger": self.logger,
            "materials_db": self.materials_db,
            "force_first_layer_same_wl": True,
            "include_secondary_rmse_stats": bool(self._get_float_safe("include_secondary_rmse_stats", 0)),
            "keep_full_mc_top_k": int(self._get_float_safe("keep_full_mc_top_k", 30)),
            "robustness_seed": int(self._get_float_safe("robustness_seed", 42)),
            "phase_a_seed": int(self._get_float_safe("phase_a_seed", self._get_float_safe("robustness_seed", 42))),
            "sym_enable": True,
            "sym_weight": self._get_float_safe("sym_weight", SYM_DEFAULT_WEIGHT),
            "sym_same_wl_bonus": self._get_float_safe("sym_same_wl_bonus", SYM_DEFAULT_SAME_WL_BONUS),
            "sym_extrema_window": self._get_float_safe("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT),
            "sym_continuity_weight": self._get_float_safe("sym_continuity_weight", SYM_DEFAULT_CONTINUITY_WEIGHT),
            "sym_adaptive_same_wl": bool(self._get_float_safe("sym_adaptive_same_wl", 1.0) > 0.5),
            "sym_allow_hybrid": bool(self._get_float_safe("sym_allow_hybrid", 0.0) > 0.5),
            "sym_prefer_on_tie": bool(self._get_float_safe("sym_prefer_on_tie", 1.0) > 0.5),
            "sym_tie_epsilon": self._get_float_safe("sym_tie_epsilon", SYM_DEFAULT_TIE_EPS_ABS),
            "sym_tie_epsilon_rel": self._get_float_safe("sym_tie_epsilon_rel", SYM_DEFAULT_TIE_EPS_REL),
            "sym_scoring_mode": (
                self.widgets["sym_scoring_mode"].currentText()
                if self.widgets.get("sym_scoring_mode")
                else SYM_DEFAULT_SCORING_MODE
            ),
            "enable_consensus_ranking": bool(self._get_float_safe("enable_consensus_ranking", 1.0) > 0.5),
            "consensus_num_seeds": int(self._get_float_safe("consensus_num_seeds", 3)),
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "consensus_seed_stride": int(self._get_float_safe("consensus_seed_stride", 1)),
            "consensus_top_k": int(self._get_float_safe("consensus_top_k", 12)),
            "consensus_num_runs": int(self._get_float_safe("consensus_num_runs", 150)),
            "consensus_std_weight": self._get_float_safe("consensus_std_weight", 0.35),
            "consensus_score_mode": "mean_std",
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "execution_mode": (
                self.widgets["execution_mode"].currentText().strip().lower()
                if self.widgets.get("execution_mode")
                else "premium"
            ),
            "fast_auto_blocks": True,
        }

        if params_out.get("execution_mode", "premium") == "fast":
            # Fast profile: ~4x lower compute budget for interactive iteration.

            params_out["mc_runs_block"] = max(25, int(params_out["mc_runs_block"] / 4))

            params_out["n_screen_runs"] = max(6, int(params_out["n_screen_runs"] / 4))

            params_out["screening_mc_runs"] = max(6, int(params_out["screening_mc_runs"] / 3))

            params_out["nucleation_mc_runs"] = max(30, int(params_out["nucleation_mc_runs"] / 3))

            params_out["robustness_num_runs"] = max(40, int(params_out["robustness_num_runs"] / 4))

            params_out["consensus_num_runs"] = max(40, int(params_out["consensus_num_runs"] / 4))

            params_out["consensus_num_seeds"] = min(
                int(params_out.get("consensus_num_seeds", 3)),
                2,
            )

            params_out["consensus_top_k"] = max(12, int(params_out.get("consensus_top_k", 12) / 2))

            params_out["elite_rounds"] = 1

            params_out["elite_max_candidates"] = 60

            params_out["elite_max_full_evals"] = 16

            params_out["keep_full_mc_top_k"] = max(10, int(params_out["keep_full_mc_top_k"] / 2))

        return params_out

    def run_workflow(self, step: int) -> None:
        self._reports_exported = False

        # CLEANUP PREVIOUS WORKER

        if hasattr(self, "worker") and self.worker is not None:
            if self.worker.isRunning():
                self.worker.quit()

                if not self.worker.wait(2000):
                    self.logger.critical(
                        "Worker did not stop within 2s in run_workflow - skipping terminate() to avoid unsafe thread kill."
                    )

            self.worker = None

        try:
            params = self.collect_params()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error collecting parameters: {e}")

            return

        exec_mode = str(params.get("execution_mode", "premium")).lower()

        if exec_mode == "fast":
            self.logger.info(
                "[MODE] FAST active | "
                f"robustness_num_runs={params.get('robustness_num_runs')} | "
                f"consensus_num_runs={params.get('consensus_num_runs')} | "
                f"n_screen_runs={params.get('n_screen_runs')} | "
                f"mc_runs_block={params.get('mc_runs_block')} | "
                f"elite_rounds={params.get('elite_rounds', 1)} | "
                f"fast_auto_blocks={params.get('fast_auto_blocks', True)}"
            )

        else:
            self.logger.info("[MODE] PREMIUM active")

        self.logger.info("\n" + "=" * 80 + f"\nSTARTING WORKFLOW: Step {step}\n" + "=" * 80 + "\n")

        # New run: allow live monitor to re-open normally (unless user closes again).

        if getattr(self, "live_monitor_window", None) is not None:
            try:
                self.live_monitor_window.user_hidden = False

            except (RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        for btn in [
            self.run_step0_btn,
            self.run_step2_btn,
            self.run_step3_btn,
            self.run_full_btn,
            self.load_strat_btn,
        ]:
            btn.setEnabled(False)

        if step in [2, 23]:
            self.stop_step2_btn.setEnabled(True)

            self.stop_step2_btn.setText("⏩ Stop & Proceed")

            params["stop_requested"] = False

        else:
            self.stop_step2_btn.setEnabled(False)

        self.progress_bar.setValue(0)

        if step != 0:
            self.status_label.setText("Running Step 1 (prerequisite)...")

            self.logger.info("AUTO-RUNNING STEP 1: Nominal Calculation (Prerequisite)")

        else:
            self.status_label.setText("Running Step 1 (Nominal)...")

        self.worker = WorkerThread(
            step=step,
            params=params,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger if step == 23 else None,
        )

        self.worker.signals.update_live_growth.connect(self.on_live_growth_update)

        self.worker.signals.update_stats.connect(self.on_stats_update)

        self.worker.signals.finished.connect(self.on_workflow_finished)

        self.worker.signals.error.connect(self.on_workflow_error)

        self.worker.signals.progress.connect(self.on_progress_update)

        self.worker.signals.plot.connect(self.on_plot_ready)

        self.worker.signals.excel_ready.connect(self.on_excel_ready)

        self.worker.signals.show_strategies_table.connect(self.on_show_strategies_table)

        _SPECTRUM_COUNTER.set_signal(self.worker.signals)

        _SPECTRUM_COUNTER.reset()

        self.worker.start()

    def on_workflow_finished(self, results) -> None:

        if "opti_results" in results:
            self.opti_results = results["opti_results"]

            self.run_step3_btn.setEnabled(True)

        if "final_results" in results:
            self.final_results = results["final_results"]

            self.logger.info("Step 3 complete.")

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        if self.opti_results:
            self.run_step3_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)

        self.load_strat_btn.setEnabled(True)

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.stop_step2_btn.setText("⏩ Stop & Proceed")

        self.status_label.setText("Complete")

        self.progress_bar.setValue(100)

        # Self-export (Excel + HTML) if enabled via HUB

        if get_export_config() and self.opti_results:
            QTimer.singleShot(500, self._auto_export_results)

    def on_workflow_error(self, exc_info) -> None:

        exc_type, exc_value, exc_tb = exc_info

        self.logger.error(f"Workflow error:\n{''.join(traceback.format_exception(exc_type, exc_value, exc_tb))}")

        self.run_step0_btn.setEnabled(True)

        self.run_step2_btn.setEnabled(True)

        if self.opti_results:
            self.run_step3_btn.setEnabled(True)

        self.run_full_btn.setEnabled(True)

        self.load_strat_btn.setEnabled(True)

        QApplication.restoreOverrideCursor()

        self.stop_step2_btn.setEnabled(False)

        self.status_label.setText("Error occurred")

        self.progress_bar.setValue(0)

    def on_progress_update(self, value: int, message: str) -> None:

        self.progress_bar.setValue(value)

        self.status_label.setText(message)

    def on_plot_ready(self, fig: Any, fig_type: str) -> None:

        if fig_type == "pyqtgraph_heatmap":
            try:
                if hasattr(self, "heatmap_window") and self.heatmap_window:
                    self.heatmap_window.close()

                self.heatmap_window = InteractiveHeatmapWindow(self, fig)

                self.heatmap_window.show()

                self.heatmap_window.raise_()

                self.heatmap_window.activateWindow()

                self.plot_windows.append(self.heatmap_window)

                return

            except (RuntimeError, AttributeError):
                # Fallback to standard queue if immediate creation is not possible.

                pass

        self.plot_queue.put((fig, fig_type))

    def on_excel_ready(self, excel_data: io.BytesIO, metadata: Dict) -> Any:
        """Handle automatic export (Excel + HTML)"""

        try:
            try:
                params_for_status = metadata.get("params", {}) if isinstance(metadata, dict) else {}
                if params_for_status.get("seed") is None and params_for_status.get("random_seed") is None:
                    self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                    self.add_validation_warning(
                        "STRAT run uses stochastic stages without explicit seed in exported params."
                    )
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("Validation status update skipped during export: %s", exc)

            report_dir = get_resource_path("reports")

            os.makedirs(report_dir, exist_ok=True)

            rmse_val = float(metadata.get("rmse", metadata.get("rmse_p95", metadata.get("rmse_mean", 0.0))))

            timestamp = certus_timestamp_file()

            try:
                src_name = ""

                if hasattr(self, "_last_config_file") and self._last_config_file:
                    src_name = "_" + Path(self._last_config_file).stem

                base_name = f"Report_STRAT{src_name}_{timestamp}_RMSE_{rmse_val:.5f}"

            except (ValueError, TypeError, AttributeError):
                base_name = f"Report_STRAT_{timestamp}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")

            html_path = str(Path(report_dir) / f"{base_name}.html")

            def _resolve_manifest_seed(seed_container: Any) -> int | None:
                if not isinstance(seed_container, dict):
                    return None
                for _k in (
                    "seed",
                    "random_seed",
                    "robustness_seed",
                    "phase_a_seed",
                    "ensemble_seed",
                ):
                    _v = seed_container.get(_k)
                    if _v is None:
                        continue
                    try:
                        return int(_v)
                    except (TypeError, ValueError):
                        continue
                return None

            def _manifest_source_paths() -> list[str]:
                paths: list[str] = []
                cfg_path = str(getattr(self, "_last_config_file", "") or "").strip()
                if cfg_path:
                    paths.append(cfg_path)
                try:
                    db_path = str(_resolve_strat_indices_db_path() or "").strip()
                except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                    db_path = ""
                if db_path:
                    paths.append(db_path)
                # Keep stable order while removing duplicates.
                return list(dict.fromkeys(paths))

            manifest_payload_source: dict[str, Any] = self.opti_results or {}
            try:
                params_for_manifest = self.collect_params()
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: manifest_payload_source)
                manifest_dict = svc.fit({
                    "config": {"module": "CERTUS_STRAT", "params": params_for_manifest},
                    "source_paths": _manifest_source_paths(),
                    "seed": _resolve_manifest_seed(params_for_manifest),
                    "app_id": "CERTUS_STRAT",
                    "app_version": __version__,
                    "warnings": list(getattr(self, "validation_warnings", []) or []),
                    "status": status_val.value if isinstance(status_val, ValidationStatus) else str(status_val),
                }).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT manifest generation failed: %s", exc)
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.logger.error(
                    "STRAT export blocked: incomplete manifest (missing: %s)",
                    ", ".join(missing_manifest_fields),
                )
                if hasattr(self, "status_label"):
                    self.status_label.setText("Export blocked: incomplete manifest")
                return

            # 1. Save Excel

            with open(excel_path, "wb") as f:
                f.write(excel_data.getvalue())
            if manifest_dict:
                try:
                    import openpyxl

                    wb_m = openpyxl.load_workbook(excel_path)
                    if "Manifest" in wb_m.sheetnames:
                        del wb_m["Manifest"]
                    ws_m = wb_m.create_sheet("Manifest")
                    ws_m.append(["Key", "Value"])
                    for k, v in manifest_dict.items():
                        ws_m.append([str(k), str(v)])
                    wb_m.save(excel_path)
                except (ImportError, OSError, ValueError, TypeError, RuntimeError) as exc:
                    self.logger.warning("STRAT manifest Excel sheet injection skipped: %s", exc)
                try:
                    manifest_path = str(Path(report_dir) / f"{base_name}.manifest.json")
                    with open(manifest_path, "w", encoding="utf-8") as mf:
                        json.dump(manifest_dict, mf, ensure_ascii=False, indent=2)
                except (OSError, ValueError, TypeError) as exc:
                    self.logger.warning("STRAT manifest JSON write skipped: %s", exc)

            self.logger.info(f"✅ Excel report saved: '{excel_path}'")

            # 2. Generate HTML Report

            # Gather plots from GUI if available

            figures = []

            if hasattr(self, "plot_stack"):
                figures.append(self.plot_stack)

            if hasattr(self, "plot_spectrum"):
                figures.append(self.plot_spectrum)

            # Create sections

            params = metadata.get("params", {})

            sections = [
                {
                    "title": "Strategy Optimization Summary",
                    "type": "kv",
                    "content": {
                        "Strategies Found": str(metadata.get("strategies_count", 0)),
                        "Best RMSE": f"{rmse_val:.5f}",
                        "Wavelength Range": f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                        "Target Layers": f"{params.get('n_target_layers', '?')}",
                    },
                }
            ]

            # Insert Methodology and Details before Summary

            methodology_sections = [
                {
                    "title": "Monitoring Methodology",
                    "type": "kv",
                    "content": {
                        "Strategy Search": "Hybrid (Dynamic Programming + Stochastic)",
                        "Monitoring Type": "Monochromatic Optical Monitoring (Single Wave/Block)",
                        "Error Compensation": "Active (Real-time Re-optimization)",
                        "Simulation Engine": "Monte Carlo (Robustness Validation)",
                    },
                },
                {
                    "title": "Simulation Details",
                    "type": "text",
                    "content": (
                        "The strategy generation uses a <strong>Hybrid Dynamic Programming</strong> approach to find the optimal layer cutting sequence. "
                        "It simulates <strong>Monochromatic Optical Monitoring</strong> (Turning/Trigger Points) with real-time error compensation, ensuring that "
                        "the designed strategy is robust against deposition errors. The final validation is performed using a "
                        "<strong>Monte Carlo</strong> engine to estimate production yield."
                    ),
                },
            ]

            all_sections = methodology_sections + sections

            if generate_html_report(html_path, "CERTUS-STRAT Report", all_sections, figures):
                self.logger.info(f"✅ HTML report saved: '{html_path}'")
                self._reports_exported = True

            self.status_label.setText(f"✓ Saved: {base_name}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"❌ Error during auto-export:{e}", exc_info=True)

    def _write_export_excel(
        self,
        strats: list,
        rmse_val: float,
        excel_path: str,
        report_dir: str,
        manifest_dict: dict,
        base_name: str,
    ) -> None:
        """Build the auto-export Excel workbook (Summary + Top Strategies + Best
        Structure + Layer Extrema + optional Manifest sheet) and write it to
        ``excel_path``. Also persist the manifest as a side-car JSON next to it
        under ``report_dir``. Behavior is preserved bit-for-bit from the legacy
        inline implementation."""
        params = self.collect_params()

        t_exec = f"{self.opti_results.get('execution_time', 0):.2f}" if "execution_time" in self.opti_results else "N/A"

        n_cores = str(get_safe_worker_count())

        n_iter = "N/A"

        df_summary = pd.DataFrame(
            {
                "Parameter": [
                    "Date",
                    "High Index (H)",
                    "Low Index (L)",
                    "substrate",
                    "Target Layers",
                    "Scan Range",
                    "Nucleation WL",
                    "Execution Time (s)",
                    "Processors",
                    "Iterations",
                    "Best RMSE",
                ],
                "Value": [
                    certus_timestamp_display(),
                    params.get("nH", "N/A"),
                    params.get("nL", "N/A"),
                    params.get("substrate", "N/A"),
                    str(params.get("n_target_layers", "N/A")),
                    f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                    f"{params.get('l0', 'N/A')} nm",
                    t_exec,
                    n_cores,
                    n_iter,
                    f"{rmse_val:.6f}",
                ],
            }
        )

        strategies_data = []
        for s in strats[:20]:
            if not isinstance(s, dict):
                continue
            strat = s.get("strategy", {})
            if not isinstance(strat, dict):
                continue
            strategies_data.append(
                {
                    "ID": strat.get("strategy_id", ""),
                    "RMSE": s.get("rmse", 0),
                    "Robustness": s.get("robustness_score", 0),
                    "Blocks": strat.get("n_blocks", 0),
                    "Blocks Def": str(strat.get("blocks", [])),
                }
            )

        df_strategies = pd.DataFrame(strategies_data)
        df_structure = pd.DataFrame()
        df_extrema = pd.DataFrame()

        if strats and isinstance(strats[0], dict) and isinstance(strats[0].get("strategy"), dict):
            best = strats[0]["strategy"]
            blocks = best["blocks"]

            struct_data = []
            for i, b in enumerate(blocks):
                struct_data.append(
                    {
                        "Block #": i + 1,
                        "Monitoring WL": b.get("wavelength", 0),
                        "Layer Start Index": b["start"],
                        "Layer End Index": b["end"],
                    }
                )
            df_structure = pd.DataFrame(struct_data)

            ext_data = []
            for i, dists in enumerate(best.get("extrema_distances", [])):
                layer_prof = {}
                if i < len(best.get("theoretical_layer_profile", [])):
                    layer_prof = best["theoretical_layer_profile"][i]

                def fmt(v) -> Any:
                    if v > 15.0:
                        return "not critical"
                    return f"{v:.1f}"

                extrema_items = layer_prof.get("Textrema", [])
                extrema_summary = ", ".join(
                    [
                        f"{e.get('type', '?')}@{float(e.get('d_nm', 0.0)):.1f}nm:{float(e.get('T', 0.0)) * 100:.2f}%"
                        for e in extrema_items[:8]
                    ]
                )
                if len(extrema_items) > 8:
                    extrema_summary += f", ... +{len(extrema_items) - 8}"
                ext_data.append(
                    {
                        "Layer": i + 1,
                        "Tinit (%)": f"{float(layer_prof.get('Tinit', np.nan)) * 100:.3f}" if layer_prof else "",
                        "Tfinal (%)": f"{float(layer_prof.get('Tfinal', np.nan)) * 100:.3f}" if layer_prof else "",
                        "Textrema (summary)": extrema_summary,
                        "Start - Prev Extremum (OT nm)": fmt(dists.get("prev_start", 999.0)),
                        "Start - Next Extremum (OT nm)": fmt(dists.get("next_start", 999.0)),
                        "End - Prev Extremum (OT nm)": fmt(dists.get("prev_end", 999.0)),
                        "End - Next Extremum (OT nm)": fmt(dists.get("next_end", 999.0)),
                    }
                )
            if ext_data:
                df_extrema = pd.DataFrame(ext_data)

        if OPENPYXL_AVAILABLE:
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                df_summary.to_excel(writer, sheet_name="Summary", index=False)
                if not df_strategies.empty:
                    df_strategies.to_excel(writer, sheet_name="Top_Strategies", index=False)
                if not df_structure.empty:
                    df_structure.to_excel(writer, sheet_name="Best_Structure", index=False)
                if not df_extrema.empty:
                    df_extrema.to_excel(writer, sheet_name="Layer_Extrema", index=False)
                if manifest_dict:
                    pd.DataFrame([{"Key": str(k), "Value": str(v)} for k, v in manifest_dict.items()]).to_excel(
                        writer, sheet_name="Manifest", index=False
                    )
            self.logger.info(f"✅ Rich Excel saved: {Path(excel_path).name}")
        else:
            to_excel_robust(df_summary, excel_path)
            self.logger.info(f"✅ Simple Excel saved (openpyxl missing): {Path(excel_path).name}")

        if manifest_dict:
            try:
                manifest_path = str(Path(report_dir) / f"{base_name}.manifest.json")
                with open(manifest_path, "w", encoding="utf-8") as mf:
                    json.dump(manifest_dict, mf, ensure_ascii=False, indent=2)
            except (OSError, ValueError, TypeError) as exc:
                self.logger.warning("STRAT manifest JSON write skipped: %s", exc)

    def _write_export_html(
        self,
        strats: list,
        rmse_val: float,
        html_path: str,
    ) -> None:
        """Build the auto-export HTML report (overview, methodology, top
        strategies and inline figures) and write it to ``html_path``. Behavior
        is preserved bit-for-bit from the legacy inline implementation."""
        params = self.collect_params()

        sections = [
            {
                "title": "Strategy Optimization Summary",
                "type": "kv",
                "content": {
                    "Best RMSE": f"{rmse_val:.5f}",
                    "Target Layers": str(params.get("n_target_layers", "N/A")),
                    "Wavelength Range": f"{params.get('scan_wl_min', 0)}-{params.get('scan_wl_max', 0)} nm",
                    "Nucleation WL": f"{params.get('l0', 'N/A')} nm",
                    "High Index Material": params.get("nH", "N/A"),
                    "Low Index Material": params.get("nL", "N/A"),
                    "substrate": params.get("substrate", "N/A"),
                    "Execution Time": (
                        f"{self.opti_results.get('execution_time', 0):.2f} s"
                        if "execution_time" in self.opti_results
                        else "N/A"
                    ),
                    "Processors": str(get_safe_worker_count()),
                    "Iterations": "N/A",
                },
            }
        ]

        methodology_sections = [
            {
                "title": "Monitoring Methodology",
                "type": "kv",
                "content": {
                    "Strategy Search": "Hybrid (Dynamic Programming + Stochastic)",
                    "Monitoring Type": "Monochromatic Optical Monitoring (Single Wave/Block)",
                    "Error Compensation": "Active (Real-time Re-optimization)",
                    "Simulation Engine": "Monte Carlo (Robustness Validation)",
                },
            },
            {
                "title": "Simulation Details",
                "type": "text",
                "content": (
                    "The strategy generation uses a <strong>Hybrid Dynamic Programming</strong> approach to find the optimal layer cutting sequence. "
                    "It simulates <strong>Monochromatic Optical Monitoring</strong> (Turning/Trigger Points) with real-time error compensation, ensuring that "
                    "the designed strategy is robust against deposition errors. The final validation is performed using a "
                    "<strong>Monte Carlo</strong> engine to estimate production yield."
                ),
            },
        ]

        all_sections = methodology_sections + sections

        if strats:
            top_strategies = strats[:10]
            table_data = []
            for s in top_strategies:
                strat = s.get("strategy", {})
                if not isinstance(strat, dict):
                    continue
                blocks_fmt = ", ".join([f"{b['start']:.0f}-{b['end']:.0f}" for b in strat.get("blocks", [])[:3]])
                if len(strat.get("blocks", [])) > 3:
                    blocks_fmt += "..."
                table_data.append(
                    {
                        "ID": strat["strategy_id"],
                        "Blocks Count": strat.get("n_blocks", 0),
                        "Structure (nm)": blocks_fmt,
                        "RMSE Score": f"{float(s.get('rmse_p95', s.get('rmse_mean', s.get('rmse', 0.0)))):.5f}",
                        "Robustness": f"{float(s.get('robustness_score', 0.0)):.5f}",
                    }
                )
            if table_data:
                all_sections.append(
                    {
                        "title": "Top Performing Strategies",
                        "type": "table",
                        "content": table_data,
                    }
                )

        figures = []
        if hasattr(self, "plot_stack") and self.plot_stack:
            figures.append(self.plot_stack)
        if hasattr(self, "plot_spectrum") and self.plot_spectrum:
            figures.append(self.plot_spectrum)

        if generate_html_report(html_path, "CERTUS-STRAT Report", all_sections, figures):
            self.logger.info(f"✅ HTML saved: {Path(html_path).name}")

    def _auto_export_results(self) -> Any:
        """Self-export results without worker signal"""

        if getattr(self, "_reports_exported", False):
            self.logger.info("Reports already exported via excel_ready signal - skipping duplicate self-export.")
            return

        if not self.opti_results:
            return

        try:
            try:
                params_for_status = self.collect_params()
                if params_for_status.get("seed") is None and params_for_status.get("random_seed") is None:
                    self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                    self.add_validation_warning("STRAT auto-export run uses stochastic stages without explicit seed.")
                else:
                    self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT auto-export validation status update skipped: %s", exc)

            report_dir = get_resource_path("reports")

            os.makedirs(report_dir, exist_ok=True)

            # Get RMSE from the actual best-ranked strategy/result.
            # Older payloads may keep placeholder 0.0 in the first item, so we must
            # search for the first finite positive score instead of blindly using index 0.
            # The RMSE used for export naming must stay an error metric, not a robustness score.

            strats = []

            if hasattr(self, "final_results") and isinstance(self.final_results, dict):
                strats = list(self.final_results.get("all_strategies_results", []))

            if not strats and "strategies_results" in self.opti_results:
                strats = list(self.opti_results.get("strategies_results", []))

            rmse_val = extract_best_rmse(strats)

            timestamp = certus_timestamp_file()

            try:
                src_name = ""

                if hasattr(self, "_last_config_file") and self._last_config_file:
                    src_name = "_" + Path(self._last_config_file).stem

                base_name = f"Report_STRAT{src_name}_{timestamp}_RMSE_{rmse_val:.5f}"

            except (ValueError, TypeError, AttributeError):
                base_name = f"Report_STRAT_{timestamp}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(report_dir) / f"{base_name}.xlsx")

            html_path = str(Path(report_dir) / f"{base_name}.html")

            self.logger.info("Saving reports...")

            def _resolve_manifest_seed(seed_container: Any) -> int | None:
                if not isinstance(seed_container, dict):
                    return None
                for _k in (
                    "seed",
                    "random_seed",
                    "robustness_seed",
                    "phase_a_seed",
                    "ensemble_seed",
                ):
                    _v = seed_container.get(_k)
                    if _v is None:
                        continue
                    try:
                        return int(_v)
                    except (TypeError, ValueError):
                        continue
                return None

            def _manifest_source_paths() -> list[str]:
                paths: list[str] = []
                cfg_path = str(getattr(self, "_last_config_file", "") or "").strip()
                if cfg_path:
                    paths.append(cfg_path)
                try:
                    db_path = str(_resolve_strat_indices_db_path() or "").strip()
                except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                    db_path = ""
                if db_path:
                    paths.append(db_path)
                return list(dict.fromkeys(paths))

            manifest_dict: dict[str, Any] = {}
            try:
                params_for_manifest = self.collect_params()
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: self.opti_results or {})
                manifest_dict = svc.fit({
                    "config": {"module": "CERTUS_STRAT", "params": params_for_manifest},
                    "source_paths": _manifest_source_paths(),
                    "seed": _resolve_manifest_seed(params_for_manifest),
                    "app_id": "CERTUS_STRAT",
                    "app_version": __version__,
                    "warnings": list(getattr(self, "validation_warnings", []) or []),
                    "status": status_val.value if isinstance(status_val, ValidationStatus) else str(status_val),
                }).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("STRAT auto-export manifest generation failed: %s", exc)
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.logger.error(
                    "STRAT auto-export blocked: incomplete manifest (missing: %s)",
                    ", ".join(missing_manifest_fields),
                )
                if hasattr(self, "status_label"):
                    self.status_label.setText("Export blocked: incomplete manifest")
                return

            # 1. EXCEL EXPORT

            try:
                self._write_export_excel(strats, rmse_val, excel_path, report_dir, manifest_dict, base_name)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Excel export failed:{e}")

            # 2. HTML EXPORT

            try:
                self._write_export_html(strats, rmse_val, html_path)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"HTML export failed:{e}", exc_info=True)

            self.status_label.setText(f"✓ Saved: {base_name}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"❌ Self-export error:{e}", exc_info=True)

    def on_show_strategies_table(self, strategies_results: list[dict[str, Any]]) -> None:

        current_p_thick = []

        include_secondary_rmse_stats = False

        try:
            include_secondary_rmse_stats = bool(self.collect_params().get("include_secondary_rmse_stats", False))

        except (KeyError, TypeError, ValueError):
            include_secondary_rmse_stats = False

        if self.opti_results and "p_thick_nominal" in self.opti_results:
            current_p_thick = self.opti_results["p_thick_nominal"]

        if not current_p_thick:
            try:
                params = self.collect_params()

                nominal_res, _ = calculate_nominal_properties(params)

                current_p_thick = nominal_res["physical_thicknesses_nominal"]

            except (KeyError, TypeError, ValueError):
                current_p_thick = []

        if self.strategies_table_window and self.strategies_table_window.isVisible():
            self.strategies_table_window.p_thick_nominal = np.array(current_p_thick, dtype=np.float64)

            self.strategies_table_window.include_secondary_rmse_stats = include_secondary_rmse_stats

            self.strategies_table_window.update_data(strategies_results)

        else:
            if self.strategies_table_window:
                self.strategies_table_window.close()

            self.strategies_table_window = StrategiesTableWindow(
                self,
                strategies_results,
                current_p_thick,
                include_secondary_rmse_stats=include_secondary_rmse_stats,
            )

            self.strategies_table_window.strategy_selected.connect(self.on_strategy_visualization_requested)

            self.strategies_table_window.show()

    def on_strategy_visualization_requested(self, row_idx: int, strategy_result: dict[str, Any]) -> None:

        try:
            strategy = strategy_result["strategy"]

            if not self.opti_results:
                # Rebuild a minimal context so detail windows remain available

                # even after a workflow error that occurred after table emission.

                try:
                    params_boot = self.collect_params()

                    nominal_results, _ = calculate_nominal_properties(params_boot)

                    p_thick_nominal = nominal_results["physical_thicknesses_nominal"]

                    clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
                        params_boot, p_thick_nominal, self.logger
                    )

                    self.opti_results = {
                        "p_thick_nominal": p_thick_nominal,
                        "clues_at_wl": clues_at_wl,
                        "nominal_matrix_cache": nominal_matrix_cache,
                        "all_wls": all_wls,
                    }

                    self.logger.info("ℹ️ Visualization context rebuilt after workflow error.")

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    self.logger.warning(f"Cannot visualize - opti_results is empty ({e})")

                    return

            self.logger.info(
                f"\n{'=' * 80}\nVISUALIZING STRATEGY #{strategy['strategy_id']} (Rank {row_idx + 1})\n{'=' * 80}"
            )

            # Robust cleanup of stale Qt window references before opening new detail windows.

            alive_windows = []

            for w in self.transmission_windows:
                try:
                    if w is not None and w.isVisible():
                        alive_windows.append(w)

                except RuntimeError:
                    continue

            self.transmission_windows = alive_windows

            try:
                params = self.collect_params()

                trans_win = TransmissionVsThicknessWindow(self, strategy_result, self.opti_results, params)

                self.transmission_windows.append(trans_win)

                trans_win.show()

                trans_win.move(100, 100)

                self.logger.info("✓ Growth window opened")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"✗ Failed to open growth window: {e}", exc_info=True)

            try:
                params = self.collect_params()

                spec_win = StrategySpectralPerformanceWindow(self, strategy_result, self.opti_results, params)

                self.transmission_windows.append(spec_win)

                spec_win.show()

                spec_win.move(150, 150)

                self.logger.info("✓ Spectral window opened")

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"✗ Failed to open spectral window: {e}", exc_info=True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error in visualization: {e}", exc_info=True)

    def _get_log_widget(self) -> Any:
        """Return log widget for CertusBaseApp log processing."""

        return self.log_text

    def process_plot_queue(self) -> None:

        plot_queue = self.plot_queue

        if plot_queue is None:
            return

        try:
            while True:
                try:
                    data_obj, fig_type = plot_queue.get_nowait()

                except queue.Empty:
                    break

                if fig_type == "clues_check_plot":
                    try:
                        if hasattr(self, "clues_window") and self.clues_window:
                            self.clues_window.close()

                        self.clues_window = InteractiveIndicesWindow(self, data_obj)

                        self.clues_window.show()

                        self.plot_windows.append(self.clues_window)

                    except (RuntimeError, AttributeError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    continue

                if fig_type == "pyqtgraph_heatmap":
                    try:
                        if hasattr(self, "heatmap_window") and self.heatmap_window:
                            self.heatmap_window.close()

                        self.heatmap_window = InteractiveHeatmapWindow(self, data_obj)

                        self.heatmap_window.show()

                        self.plot_windows.append(self.heatmap_window)

                    except (RuntimeError, AttributeError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    continue

                if fig_type == "main_spectral_interactive":
                    try:
                        win = InteractiveSpectrumWindow(self, data_obj, sigma=data_obj.get("sigma", None))

                        win.show()

                        if not hasattr(self, "interactive_spectrum_windows"):
                            self.interactive_spectrum_windows = []

                        self.interactive_spectrum_windows.append(win)

                    except (RuntimeError, AttributeError):
                        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

                    continue

                if fig_type == "main_spectral":
                    self.update_main_plot(data_obj)

                elif fig_type == "stack_visual":
                    self.update_stack_plot(data_obj)

                else:
                    plot_win = UniversalPlotWindow(self, data_obj, fig_type)

                    plot_win.show()

                    plot_win.raise_()

                    plot_win.activateWindow()

                    self.plot_windows.append(plot_win)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error processing plot queue: {e}", exc_info=True)

    # === OPTIMIZATION: Hashed & Async Plot Update ===

    def _compute_fig_hash(self, fig: Any) -> str:

        try:
            return self._plot_cache.get_hash(fig)

        except (TypeError, AttributeError):
            return str(time.time())

    def update_main_plot(self, fig: Any, force_render: bool = False) -> None:

        try:
            target_w = max(100, self.main_plot_widget.width())

            target_h = max(100, self.main_plot_widget.height())

            plot_hash = self._compute_fig_hash(fig)

            # 1. Check Cache

            with self._cache_lock:
                cached_pix = self._plot_cache.get(plot_hash)

                if cached_pix and not force_render:
                    self._apply_pixmap(cached_pix)

                    return

                if plot_hash in self._rendering_plots:
                    return  # Already rendering

            # 2. Async Render

            self._rendering_plots.add(plot_hash)

            # Start Worker Thread

            thread = QThread(self)

            worker = PlotRenderWorker(fig, target_w, target_h, plot_hash)

            worker.moveToThread(thread)

            worker.finished.connect(self._on_render_complete)

            worker.finished.connect(thread.quit)

            worker.finished.connect(worker.deleteLater)

            thread.finished.connect(thread.deleteLater)

            # Keep ref to prevent GC

            self._active_render_thread = thread

            thread.start()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Plot Dispatch Error: {e}", exc_info=True)

    @pyqtSlot(bytes, str)
    def _on_render_complete(self, png_bytes, plot_hash) -> None:

        try:
            pix = QPixmap()

            pix.loadFromData(png_bytes)

            with self._cache_lock:
                self._plot_cache.put(plot_hash, pix)

                self._rendering_plots.discard(plot_hash)

            self._apply_pixmap(pix)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error applying render: {e}", exc_info=True)

            with self._cache_lock:
                self._rendering_plots.discard(plot_hash)

    def _apply_pixmap(self, pixmap) -> None:

        self.main_plot_widget.setPixmap(pixmap)

        self.main_plot_widget.setScaledContents(True)

        if self.plot_stack.currentWidget() != self.main_plot_widget:
            self.plot_stack.setCurrentWidget(self.main_plot_widget)

    # ===============================================

    def update_stack_plot(self, fig) -> None:

        if hasattr(self, "stack_visual_window") and self.stack_visual_window:
            self.stack_visual_window.close()

        try:
            # Replaced dedicated StackStructureWindow with UniversalPlotWindow for consistency

            self.stack_visual_window = UniversalPlotWindow(self, fig, "stack_visual")

            self.stack_visual_window.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Failed to update stack plot: {e}")

    @pyqtSlot(dict)
    def on_live_growth_update(self, live_data) -> None:

        try:
            if self.live_monitor_window is None:
                self.live_monitor_window = LiveMonitorWindow(None)  # No parent to avoid sub-window rendering

                set_certus_window_icon(self.live_monitor_window)

            # Respect explicit user close: do not auto-reopen during current run.

            if getattr(self.live_monitor_window, "user_hidden", False):
                return

            if not self.live_monitor_window.isVisible():
                self.live_monitor_window.show()

                self.live_monitor_window.raise_()

                self.live_monitor_window.activateWindow()

            strategy = live_data.get("strategy", {})

            blocks = strategy.get("blocks", [])

            p_thick_nominal = np.array(live_data["p_thick_nominal"], dtype=np.float64)

            clues_db = live_data["clues_at_wl"]

            num_layers = len(p_thick_nominal)

            layer_wls = np.zeros(num_layers, dtype=np.float64)

            # [FIX 2026] Complex clues for coherent detailed growth (absorption in TMM)

            nH_arr = np.zeros(num_layers, dtype=np.complex128)

            nL_arr = np.zeros(num_layers, dtype=np.complex128)

            nSub_arr = np.zeros(num_layers, dtype=np.complex128)

            # Fallback values

            default_idx = {
                "H": complex(2.3),
                "L": complex(1.45),
                "substrate": complex(1.52),
            }

            for block in blocks:
                wl = float(block["wavelength"])

                # We try to get data (can be a dict or a worker)

                try:
                    idx_data = clues_db[wl]

                except (KeyError, TypeError):
                    idx_data = default_idx

                # COMMON.SharedIndicesWorker returns "substrate" as standard key

                n_s = idx_data.get("substrate", default_idx["substrate"])

                for l in range(block["start"], block["end"]):
                    if l < num_layers:
                        layer_wls[l] = wl

                        nH_arr[l] = idx_data.get("H", default_idx["H"])

                        nL_arr[l] = idx_data.get("L", default_idx["L"])

                        n_s_val = complex(n_s)

                        # [FIX 2026-03] Guard: n_sub < 1.001 is physically impossible

                        if n_s_val.real < 1.001:
                            logging.warning(
                                f"[Live] n_sub={n_s_val:.4f} at {wl}nm - using fallback {default_idx['substrate']}"
                            )

                            n_s_val = default_idx["substrate"]

                        nSub_arr[l] = n_s_val

            steps = np.full(num_layers, 30, dtype=np.int32)

            x, y, bounds = calculate_detailed_growth(
                num_layers, p_thick_nominal, layer_wls, nH_arr, nL_arr, nSub_arr, steps
            )

            score = live_data.get("robustness_score", 0.0)

            self.live_monitor_window.update_monitor(
                x,
                y,
                bounds,
                f"LIVE MONITORING: {strategy.get('n_blocks')} BLOCKS | Robustness: {score:.5f}",
                blocks,
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"[GUI] Error in on_live_growth_update: {e}", exc_info=True)

    def closeEvent(self, event) -> None:

        try:
            # Stop worker thread if running

            if hasattr(self, "worker") and self.worker is not None and self.worker.isRunning():
                self.worker.params["stop_requested"] = True

                self.worker.quit()

                if not self.worker.wait(2000):
                    self.logger.critical(
                        "Worker did not stop within 2s in closeEvent - skipping terminate() to avoid unsafe thread kill."
                    )

            if getattr(self, "_log_timer_id", None) is not None:
                self.killTimer(self._log_timer_id)

            if getattr(self, "plot_timer", None) is not None:
                self.killTimer(self.plot_timer)

            self.close_all_auxiliary_windows()

            if hasattr(self, "materials_db"):
                self.materials_db.clear_cache()

            self.logger.info("Application closed.")

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        finally:
            event.accept()

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # NOTE: We do NOT touch SystemConfig.setup_numba_cache() here

    # because it's already done at the top of the file and at COMMON import.

    # Calling startup logging helper is OK because it doesn't touch Numba.

    setup_module_logging("STRAT", log_file="certus_strat.log")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Application creation (MUST be done before theme)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-STRAT", app=app)

    # --- SPLASH SCREEN ---

    from certus_splash import create_splash

    splash = create_splash("Initializing CERTUS STRAT...")


    # ROBUST MATERIAL DATABASE FIX: canonical indices.xlsx in example/database_index

    # with legacy fallback to clues.xlsx for compatibility.

    clues_file = _resolve_strat_indices_db_path()

    logging.info(f"[ROBUST DB] Checking material DB at:{clues_file}")

    splash.showMessage(
        "Loading Material Database...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    if Path(clues_file).exists():
        try:
            robust_db = RobustMaterialDatabase(clues_file)

            APP_CONTEXT["materials_db"] = robust_db

            set_robust_material_db(robust_db)  # Set global reference for priority access

            logging.info(f"[ROBUST DB] ✓ Activated with {len(robust_db.materials)} materials")

        except (ValueError, RuntimeError, AttributeError, KeyError, FileNotFoundError) as e:
            logging.warning(f"[ROBUST DB] ✗ Failed to load: {e}")

            splash.showMessage(
                f"DB Error: {e}",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
                Qt.GlobalColor.red,
            )

            logging.warning("[ROBUST DB] Continuing startup without splash delay loop.")

    else:
        logging.warning("[ROBUST DB] ✗ File not found, using fallback")

    # Windows AppUserModelID configuration (optional)

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("certus.strat.2.0")

    except (OSError, AttributeError, ImportError):
        # Windows-specific API, may fail on other platforms or if unavailable

        pass

    splash.showMessage(
        "Starting User Interface...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    # Launch

    win = CertusStratApp()

    win.show()

    splash.finish(win)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_configuration(f))

    sys.exit(app.exec())
