# =============================================================================
# CERTUS STRAT - Asynchronous workers and threading loops
# =============================================================================
from pathlib import Path





import logging

import queue


import time

import traceback


from typing import Any

import numpy as np







from enum import Enum

class StratTask(Enum):
    NOMINAL_ANALYSIS = "nominal"
    STRATEGY_SEARCH = "optimization"
    ROBUSTNESS_EVALUATION = "robustness"
    FULL_PIPELINE = "full_workflow"
    EXTERNAL_EVALUATION = "external_eval"

from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtCore import (
    QObject,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)



# Import access config

from certus.core.certus_core import (
    get_resource_path,
)

from certus.core.certus_strat_core import (
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    mine_strategies_for_block_count,
    run_final_simulation_block,
    _validate_strategy_blocks_contract,
    _strategy_signature,
    _emit_stat,
    _flush_sp_stats,
    _worker_init,
    _IdxWrapper,
    APP_CONTEXT,
    optimize_block_strategy_hybrid,
    generate_excel_report,
    _get_best_noise_results,
    precompute_clues_and_matrices,
)

from certus.utils.certus_data import (
    SharedArrayWorker,
    SharedIndicesWorker,
)

from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    arange_inclusive,
    calculate_RT_batch_kernel,
    find_nucleation_adaptive_kernel,
    get_refractive_clues_vectorized,
    rank_nucleation_candidates_kernel,
)

# Import context system (replaces global variables)

from certus.utils.certus_strat_context import (
    StratContext,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _validate_strategy_blocks_contract,
    _strategy_signature,
)

# Robust db clues (fixed xlsx)



from certus.workers.certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
from certus.utils.certus_strat_service import (
    StratStrategyService,
    calculate_nominal_properties,
    compute_probe_offset_nm_from_ratio,
    extract_best_rmse,
)


from certus.workers.certus_strat_workers_nominal import NominalAnalysisStrategy
from certus.workers.certus_strat_workers_search import StrategySearchStrategy
from certus.workers.certus_strat_workers_robustness import RobustnessEvaluationStrategy
from certus.workers.certus_strat_workers_pipeline import FullPipelineStrategy
from certus.workers.certus_strat_workers_external import ExternalEvaluationStrategy
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

# === WORKER SIGNALS ===

class WorkerSignals(QObject):
    finished = pyqtSignal(object)

    error = pyqtSignal(tuple)

    progress = pyqtSignal(int, str)
    progress_snapshot = pyqtSignal(object)

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

            except Exception as e:
                logger.warning(f"[Block {n_blk}] SharedMemory (Hints) reconnection failed:{e}")

        shared_matrix_worker = None

        if "shared_matrix_info" in pre_calc_data:
            try:
                shared_matrix_worker = SharedArrayWorker(pre_calc_data["shared_matrix_info"])

                pre_calc_data["nominal_matrix_cache"] = shared_matrix_worker.get_array()

            except Exception as e:
                logger.warning(f"[Block {n_blk}] SharedMemory (Matrix) reconnection failed: {e}")

        if "materials_data" in pre_calc_data and pre_calc_data["materials_data"]:
            local_materials_db = MaterialDatabase(filepath="")

            local_materials_db._data = pre_calc_data["materials_data"]

            params["materials_db_instance"] = local_materials_db

        # Get live_queue from StratContext (initialized via _worker_init)

        ctx = StratContext.get_current()

        live_queue = ctx.live_queue if ctx else None

        logger.debug(f"[DEBUG-WORKER] [Block {n_blk}] StratContext is {'NOT None' if ctx else 'None'}, live_queue is {'NOT None' if live_queue else 'None'}")

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

        best_final = None
        if final_results:
            best_final = min(final_results, key=lambda x: x["robustness_score"])
            logger.info(
                f"[Block {n_blk}] Best strategy ready: RMSE={best_final['robustness_score']:.5f} "
                f"blocks={len(best_final.get('strategy', {}).get('blocks', []))}"
            )

        if live_queue and best_final:
            try:
                logger.debug(f"[DEBUG-WORKER] [Block {n_blk}] Putting best strategy into live_queue. Robustness: {best_final['robustness_score']:.5f}")
                live_queue.put(
                    {
                        "strategy": best_final["strategy"],
                        "robustness_score": best_final["robustness_score"],
                        "n_blk": n_blk,
                        "block_number": n_blk,
                    }
                )
                logger.debug(f"[DEBUG-WORKER] [Block {n_blk}] Successfully put strategy into live_queue.")

            except Exception as e:
                logger.error(f"[Worker {n_blk}] Failed to put into live_queue: {e}", exc_info=True)
        else:
            logger.debug(f"[DEBUG-WORKER] [Block {n_blk}] Skipped putting into live_queue. live_queue exists: {live_queue is not None}, final_results length: {len(final_results) if final_results else 0}")

        return {
            "n_blk": n_blk,
            "strategies_results": final_results,
            "live_preview": None,
            "best_strategy": best_final["strategy"] if best_final else None,
            "best_robustness_score": best_final["robustness_score"] if best_final else None,
            "best_strategy_error": None,
        }

    except Exception as e:
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


class StatsConsumerWorker(QObject):
    """Asynchronous stats queue consumer to avoid raw threading signal emission"""
    finished = pyqtSignal()
    update_stats = pyqtSignal(str, int)

    def __init__(self, stats_queue) -> None:
        super().__init__()
        self.stats_queue = stats_queue
        self.is_running = True

    def run(self) -> None:
        import queue
        while self.is_running:
            try:
                item = self.stats_queue.get(timeout=0.1)
                if item is None:
                    break
                counter_type, increment = item
                self.update_stats.emit(counter_type, increment)
            except queue.Empty:
                continue
            except (BrokenPipeError, OSError, ValueError):
                break
        self.finished.emit()


class LiveFeedMonitor(QObject):
    """Qt-backed monitor that polls ``live_preview_queue`` for live preview updates.

    Thread model
    ------------
    This object is created on the **main/worker thread**, then moved to its own
    ``QThread`` via ``moveToThread`` before ``start()`` is called::

        self.monitor_thread = QThread()
        self.monitor_worker = LiveFeedMonitor(...)
        self.monitor_worker.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(self.monitor_worker.start)
        self.monitor_thread.start()

    Critical invariant — QTimer must be created in ``start()``, NOT ``__init__``
    ---------------------------------------------------------------------------
    BUG HISTORY: When ``QTimer(self)`` was instantiated inside ``__init__``, it
    was created in the calling (main) thread's event loop.  After ``moveToThread``
    the object lives in ``monitor_thread`` but the timer kept dispatching to the
    wrong event loop, causing silent mis-firing and Qt thread-affinity warnings.
    RULE: Always create ``QTimer`` (and any other Qt event-loop objects) **inside
    the slot/method that runs in the target thread** — here ``start()``.
    ``__init__`` must only set ``self._timer = None`` as a sentinel.

    Object lifetime — strong reference on the parent
    ------------------------------------------------
    BUG HISTORY: Assigning the monitor to a local variable instead of
    ``self.monitor_worker`` let Python's garbage collector destroy it while the
    QThread was still running, crashing Qt.
    RULE: Always store as ``self.monitor_worker = LiveFeedMonitor(...)`` on the
    owning ``WorkerThread``.  The companion ``self.monitor_thread`` must be stored
    the same way.

    Queue type — ``queue.Queue``, NOT ``multiprocessing.Queue``
    -----------------------------------------------------------
    BUG HISTORY: Using ``multiprocessing.Queue`` with a ``ThreadPoolExecutor``
    caused hangs because ``multiprocessing.Queue.get_nowait`` uses OS-level pipes
    that behave differently inside threads versus processes.
    RULE: Use ``queue.Queue`` (stdlib threading queue) whenever workers run as
    **threads** (``ThreadPoolExecutor``).  Only switch to ``multiprocessing.Queue``
    if the pool is ``ProcessPoolExecutor``.
    """

    finished = pyqtSignal()

    def __init__(self, live_preview_queue, signals, p_thick_nominal, clues_at_wl) -> None:
        super().__init__()
        self.live_preview_queue = live_preview_queue
        self.signals = signals
        self.p_thick_nominal = p_thick_nominal
        self.clues_at_wl = clues_at_wl
        self._timer = None
        self._last_update = 0.0
        self._last_full_package = None
        self._latest_item = None

    def start(self) -> None:
        logging.getLogger("CERTUS").debug("[DEBUG-MONITOR] LiveFeedMonitor started.")
        # GUARD RAIL — QTimer must only be instantiated in the target QThread context (here start()),
        # never in __init__, otherwise it maps to the spawning main GUI thread's event loop.
        # Ensure thread affinity of self matches the executing thread.
        assert self.thread() == QThread.currentThread(), (
            "CERTUS-STRAT-E-THREAD-AFFINITY: LiveFeedMonitor must be started within its own thread context. "
            "Verify that moveToThread(monitor_thread) was called before invoking start()."
        )
        # SAFETY — QTimer created here, in the thread that owns self (post-moveToThread)
        # Creating QTimer in __init__ would bind it to the spawning thread's event loop,
        # not to monitor_thread, causing silent mis-firing (bug fixed 2026-05-27).
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._poll)
        self._timer.start()

    @pyqtSlot()
    def stop(self) -> None:
        logging.getLogger("CERTUS").debug("[DEBUG-MONITOR] LiveFeedMonitor stop requested.")
        if self._timer is not None:
            self._timer.stop()
        self.finished.emit()

    def _poll(self) -> None:
        try:
            try:
                while True:
                    got = self.live_preview_queue.get_nowait()
                    if got is not None:
                        if got == "STOP":
                            logging.getLogger("CERTUS").debug("[DEBUG-MONITOR] LiveFeedMonitor poll received STOP.")
                            self.stop()
                            return
                        self._latest_item = got
            except (queue.Empty, IndexError, AttributeError):
                pass
            except (BrokenPipeError, OSError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            now = time.time()
            if self._latest_item is not None and (now - self._last_update > 0.4):
                item = self._latest_item
                full_package = {
                    "strategy": item["strategy"],
                    "robustness_score": item["robustness_score"],
                    "n_blk": item.get("n_blk"),
                    "block_number": item.get("block_number"),
                    "p_thick_nominal": self.p_thick_nominal,
                    "clues_at_wl": self.clues_at_wl,
                }
                logging.getLogger("CERTUS").debug(
                    f"[DEBUG-MONITOR] Emitting update_live_growth for block {full_package.get('n_blk')}. robustness: {item['robustness_score']:.5f}"
                )
                self.signals.update_live_growth.emit(full_package)
                self._last_update = now
                self._latest_item = None
        except Exception as e:
            logging.error(f"[MonitorThread] Error: {e}", exc_info=True)
            self.stop()


class WorkerThread(QThread):
    def __init__(
        self,
        step: int | StratTask | WorkerThreadRequest,
        params: dict[str, Any] | None = None,
        opti_results: dict[str, Any] | None = None,
        timing_logger=None,
    ) -> None:

        super().__init__()

        # Track C: Headless service for STRAT strategy
        self._service = StratStrategyService(runner=lambda cfg: None)

        step_map_to_int = {
            StratTask.NOMINAL_ANALYSIS: 0,
            StratTask.STRATEGY_SEARCH: 2,
            StratTask.ROBUSTNESS_EVALUATION: 3,
            StratTask.FULL_PIPELINE: 23,
            StratTask.EXTERNAL_EVALUATION: 33
        }

        if isinstance(step, StratTask):
            self.task_type = step
            legacy_step = step_map_to_int[step]
        elif isinstance(step, int):
            legacy_step = step
            int_to_task = {v: k for k, v in step_map_to_int.items()}
            self.task_type = int_to_task.get(step, StratTask.NOMINAL_ANALYSIS)
        else:
            # It is a WorkerThreadRequest
            legacy_step = int(step.step)
            int_to_task = {v: k for k, v in step_map_to_int.items()}
            self.task_type = int_to_task.get(legacy_step, StratTask.NOMINAL_ANALYSIS)

        self.request = (
            step
            if isinstance(step, WorkerThreadRequest)
            else WorkerThreadRequest.from_legacy(
                step=legacy_step,
                params=params,
                opti_results=opti_results,
                timing_logger=timing_logger,
            )
        )

        # Keep legacy fields for incremental migration across call sites.
        self.step = legacy_step

        self.params = self.request.params

        self.opti_results = self.request.opti_results

        self.timing_logger = self.request.timing_logger

        self.signals = WorkerSignals()

        self.nominal_results = None

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

            if self.task_type in [StratTask.STRATEGY_SEARCH, StratTask.ROBUSTNESS_EVALUATION, StratTask.FULL_PIPELINE, StratTask.EXTERNAL_EVALUATION]:
                self._execute_nominal_analysis_auto()

            if self.task_type == StratTask.NOMINAL_ANALYSIS:
                self._execute_nominal_analysis()

            elif self.task_type == StratTask.STRATEGY_SEARCH:
                self._execute_strategy_search()

            elif self.task_type == StratTask.ROBUSTNESS_EVALUATION:
                self._execute_robustness_evaluation()

            elif self.task_type == StratTask.FULL_PIPELINE:
                self._execute_full_pipeline()

            elif self.task_type == StratTask.EXTERNAL_EVALUATION:
                self._execute_external_evaluation()

        except Exception as e:
            self.signals.error.emit((type(e), e, e.__traceback__))

            self.params["logger"].error(traceback.format_exc())

    def _execute_nominal_analysis(self) -> None:
        NominalAnalysisStrategy().execute(self)


    def _execute_nominal_analysis_auto(self) -> None:
        """

        Execute Auto-Step 1: Nominal Calculation & Sensitivity Check.

        This method performs the same analysis as _execute_nominal_analysis but in automatic mode:

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

            - Prerequisite for STRATEGY_SEARCH, ROBUSTNESS_EVALUATION, FULL_PIPELINE, EXTERNAL_EVALUATION tasks

            - Stores results for subsequent steps

        """

        self.params["logger"].info("--- AUTO-STEP 1: NOMINAL CALCULATION & SENSITIVITY CHECK ---")

        # Track C: Orchestrate Step 0 via headless service
        res = self._service.run_step_0(self.params, materials_db=APP_CONTEXT.get("materials_db"))
        nominal_results = res["nominal_results"]
        self.nominal_results = nominal_results
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

        except Exception as e:
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

    def _execute_strategy_search(self) -> None:
        StrategySearchStrategy().execute(self)


    def _execute_robustness_evaluation(self) -> None:
        RobustnessEvaluationStrategy().execute(self)


    def _execute_full_pipeline(self) -> None:
        FullPipelineStrategy().execute(self)


    def _execute_external_evaluation(self) -> None:
        ExternalEvaluationStrategy().execute(self)



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

    import concurrent.futures
    import threading

    def stop_check():
        return params.get("stop_requested", False)

    # 1. Partition blocks_range into independent segments of consecutive integers
    segments = []
    if blocks_range:
        current_segment = [blocks_range[0]]
        for val in blocks_range[1:]:
            if current_segment[-1] - val == 1:
                current_segment.append(val)
            else:
                segments.append(current_segment)
                current_segment = [val]
        segments.append(current_segment)

    accumulated_strategies_results = []
    completed_blocks_lock = threading.Lock()
    completed_blocks_count = [0]
    total_blocks = len(blocks_range)
    # FIX: Force max_workers=1 to prevent Numba CPU oversubscription and deadlocks
    max_workers = 1
    params["logger"].info(f"   Using {max_workers} parallel workers for {len(segments)} independent segments")

    def _run_segment(segment: list[int]) -> None:
        inherited_strategies = []
        logger = params["logger"]
        for n_blk in segment:
            if stop_check():
                logger.warning(f"🛑 Stopping Optimization at {n_blk} blocks...")
                break

            logger.debug(f"[SPY-WORKER] Starting loop iteration for block {n_blk}")
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
                logger.debug(f"[SPY-WORKER] Running block {n_blk} inside concurrent thread pool...")
                t0 = time.time()
                result_batch = _parallel_block_worker(args)
                logger.debug(
                    f"[SPY-WORKER] Completed block {n_blk} in {time.time() - t0:.3f}s. Results count: "
                    f"{len(result_batch.get('strategies_results', [])) if isinstance(result_batch, dict) else 'error'}"
                )

                if int(result_batch.get("n_blk", n_blk)) != int(n_blk):
                    logger.error(
                        f"    [Block {n_blk}] ❌ Worker returned wrong n_blk={result_batch.get('n_blk')}"
                    )
                    inherited_strategies = []
                    continue

                if "error" in result_batch and result_batch.get("strategies_results") == []:
                    logger.error(f"    [Block {n_blk}] ❌ Error: {result_batch['error']}")
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
                            logger.warning(
                                f"    [Block {n_blk}] Dropped invalid strategy payload: {reason}"
                            )

                    with completed_blocks_lock:
                        accumulated_strategies_results.extend(strategies_this_step)

                    dyn_msg = ""
                    if strategies_this_step:
                        abs_min_dyn = None
                        abs_wl = 0.0
                        abs_layer = 0
                        abs_source = ""
                        missing_layer_count = 0
                        missing_key_count = 0
                        present_count = 0
                        sampled_values = []
                        layer_count_seen = set()
                        wavelengths_seen = set()
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
                                layer_count_seen.add(li + 1)
                                layer_dyn_map = dyn_grid.get(li)
                                if layer_dyn_map is None:
                                    missing_layer_count += 1
                                    continue
                                wl_key = float(wl)
                                wavelengths_seen.add(wl_key)
                                if wl_key not in layer_dyn_map:
                                    missing_key_count += 1
                                    continue
                                d = float(layer_dyn_map[wl_key])
                                sampled_values.append(d)
                                present_count += 1
                                if abs_min_dyn is None or d < abs_min_dyn:
                                    abs_min_dyn = d
                                    abs_wl = wl
                                    abs_layer = li + 1
                                    abs_source = "exact_zero" if d == 0.0 else "value"
                        if abs_min_dyn is not None:
                            sample_min = min(sampled_values) if sampled_values else abs_min_dyn
                            sample_max = max(sampled_values) if sampled_values else abs_min_dyn
                            sample_mean = (sum(sampled_values) / len(sampled_values)) if sampled_values else abs_min_dyn
                            sample_zero_count = sum(1 for v in sampled_values if v == 0.0)
                            dyn_msg = (
                                f" | Min Dyn: {abs_min_dyn:.12e} (@{abs_wl:.0f}nm, L{abs_layer}, {abs_source})"
                                f" | present={present_count}"
                                f" | zero={sample_zero_count}"
                                f" | min={sample_min:.12e}"
                                f" | max={sample_max:.12e}"
                                f" | mean={sample_mean:.12e}"
                                f" | layers_seen={len(layer_count_seen)}"
                                f" | wls_seen={len(wavelengths_seen)}"
                            )
                            if missing_layer_count or missing_key_count:
                                dyn_msg += f" | missing_layer={missing_layer_count} | missing_key={missing_key_count}"
                        elif missing_layer_count or missing_key_count:
                            dyn_msg = (
                                f" | Min Dyn: n/a"
                                f" | present=0"
                                f" | layers_seen={len(layer_count_seen)}"
                                f" | wls_seen={len(wavelengths_seen)}"
                                f" | missing_layer={missing_layer_count}"
                                f" | missing_key={missing_key_count}"
                            )

                    logger.info(
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

            except Exception as e:
                logger.error(f"   [Block {n_blk}] ❌ Error: {e}")
                inherited_strategies = []
            finally:
                with completed_blocks_lock:
                    completed_blocks_count[0] += 1
                    current_completed = completed_blocks_count[0]
                progress_pct = int((current_completed / total_blocks) * 90) + 5
                signals.progress_snapshot.emit(
                    build_progress_snapshot(
                        message=f"Optimizing ({n_blk} blocks)",
                        sub_message=f"Completed {current_completed}/{total_blocks}",
                        progress_ratio=progress_pct / 100.0,
                        display_ratio=progress_pct / 100.0,
                        eta_seconds=None,
                        confidence=0.25,
                        state=StepState.RUNNING,
                        module="STRAT",
                        phase="BLOCK_OPT",
                        metadata={"completed": current_completed, "total": total_blocks, "block": n_blk},
                    )
                )
                signals.progress_snapshot.emit(build_progress_snapshot(message=f"Optimizing ({n_blk} blocks) - Completed {current_completed}/{total_blocks}", sub_message=f"Completed {current_completed}/{total_blocks}", progress_ratio=progress_pct / 100.0, display_ratio=progress_pct / 100.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module="STRAT", phase="BLOCK_OPT", metadata={"completed": current_completed, "total": total_blocks, "block": n_blk}))

    executor = None
    try:
        executor = ThreadPoolExecutor(
            max_workers=max_workers,
            initializer=_worker_init,
            initargs=(stats_queue, live_preview_queue),
        )
        with executor:
            futures = []
            for segment in segments:
                futures.append(executor.submit(_run_segment, segment))
            
            # Wait for all segments to complete (with a safe timeout)
            done, not_done = concurrent.futures.wait(futures, timeout=600)
            for f in done:
                if f.exception() is not None:
                    params["logger"].error(f"❌ Future raised exception: {f.exception()}", exc_info=f.exception())
    except Exception as e:
        params["logger"].error(f"ThreadPoolExecutor error: {e}")
        raise
    finally:
        if executor is not None:
            try:
                executor.shutdown(wait=True)
            except (RuntimeError, AttributeError) as e:
                params["logger"].warning(f"Error shutting down executor: {e}")

    return accumulated_strategies_results

def _finalize_and_export_pipeline_results(
    accumulated_strategies_results: list[dict[str, Any]],
    pre_calc_data: dict[str, Any],
    nominal_res: dict[str, Any],
    params: dict[str, Any],
    signals: Any,
    timing_logger: Any,
) -> dict[str, Any]:
    """Sorts final results, emits plots, triggers Excel export, and returns final payload."""
    params["logger"].info("🚀 PHASE 4: Final Monte Carlo Yield Evaluation & Export...")
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
        except Exception as e:
            params["logger"].warning(f"Plotting error: {e}")

        best_noise_results = _get_best_noise_results(best_res, params["logger"])
        if best_noise_results:
            wl_arr = arange_inclusive(
                params["wl_range"][0],
                params["wl_range"][1],
                params["wl_step"],
            )
            # SAFETY — three-level material database fallback
            # BUG HISTORY: using only params.get("materials_db_instance") here
            # returned None in most Step-23 paths, causing the robustness plot
            # to render a flat curve (bug fixed 2026-05-27).
            # Same contract as StrategySpectralPerformanceWindow._calculate_and_plot.
            local_db = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
            # GUARD RAIL — Ensure materials database is resolved for worker calculations to prevent flat curve regressions.
            assert local_db is not None, (
                "CERTUS-STRAT-E-DB-MISSING: Materials database is missing in worker context. "
                "Verify params serialization or APP_CONTEXT initialization."
            )
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

            # Compute T_spectral_all for MC runs
            thick_all = np.array(best_noise_results["thicknesses_all"], dtype=np.float64)
            _, T_spectral_all = calculate_RT_batch_kernel(
                wl_arr,
                nH_arr,
                nL_arr,
                nSub_arr,
                thick_all,
            )
            best_noise_results["T_spectral_all"] = T_spectral_all.tolist()

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
        best_rmse = extract_best_rmse(final_complete_structure.get("all_strategies_results", []))
        params["logger"].info("STRAT Export (General): Extracted best RMSE %f from strategies results", best_rmse)
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

def _execute_nucleation_and_cost_mapping(
    params: dict[str, Any],
    signals: Any,
    nominal_res: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[float], dict[str, float], dict[str, Any]]:
    """Executes Phase 1 (Nucleation Analysis) and Phase 2 (Cost Maps)."""

    if nominal_res is None:
        nominal_res, _ = calculate_nominal_properties(params)
    p_thick_nom = nominal_res["physical_thicknesses_nominal"]

    params["logger"].info("🚀 PHASE 1: Initializing Smart Nucleation Analysis...")
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

    params["logger"].info("\n🚀 PHASE 2: Calculating Cost Maps...")
    params["p_thick_nominal"] = p_thick_nom
    pre_calc_data = optimize_block_strategy_hybrid(params, signals.progress, None, phase_a_only=True)

    if "error" in pre_calc_data:
        raise RuntimeError(pre_calc_data["error"])

    if params.get("show_plots", True) and "raw_results_thickness" in pre_calc_data:
        signals.plot.emit(pre_calc_data["raw_results_thickness"], "pyqtgraph_heatmap")

    import gc
    gc.collect()
    return pre_calc_data, p_thick_nom, nucleation_info, nominal_res

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

        except Exception as e:
            self.error.emit(str(e))

def _resolve_strat_indices_db_path() -> str:
    """Return canonical indices DB path for STRAT, with legacy fallback."""

    preferred = str(Path(get_resource_path(str(Path("example") / "database_index" / "indices.xlsx"))).resolve())

    if Path(preferred).exists():
        return preferred

    legacy = str(Path(get_resource_path("clues.xlsx")).resolve())

    return legacy


# Backward compatibility aliases
_run_phase0_and_phaseA = _execute_nucleation_and_cost_mapping
_finalize_and_export_step_23 = _finalize_and_export_pipeline_results

