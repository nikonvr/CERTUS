
from typing import TYPE_CHECKING, Any
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_strat_core import APP_CONTEXT
from certus.core.certus_strat_ranking import build_yield_cost_map, combine_cost_and_yield
from certus.utils.certus_strat_context import StratContext
from certus.workers.certus_strat_workers_dto import WorkerThreadResult
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_strat_service import calculate_nominal_properties, extract_best_rmse, select_best_strat_result
from certus.core.certus_strat_core import generate_excel_report
from certus.core.certus_core import get_export_config, get_resource_path, certus_timestamp_file
from pathlib import Path
from certus.core.certus_core import SUBSTRATE_MAPPING
import certus.utils.certus_strat_service as _strat_service_module
from certus.core.certus_strat_config import _init_stats_queue
import traceback
import time
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState
from PyQt6.QtCore import QThread, Qt, QMetaObject
import queue
from certus.utils.certus_strat_context import _compute_blocks_range_for_params
from certus.utils.certus_data import SharedIndicesManager, SharedArrayManager
from PyQt6.QtCore import QThread
import queue

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class FullPipelineStrategy:
    def execute(self, worker: "WorkerThread") -> None:
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

        if worker.timing_logger:
            worker.timing_logger.start_global("Full Optimized Workflow (Deep Exploration Mode)")

        worker.signals.progress_snapshot.emit(build_progress_snapshot(message="<b>[PRE-CALCULATION]</b> Starting nominal evaluation...", display_ratio=0.0, progress_ratio=0.0, eta_seconds=None, confidence=0.25, state=StepState.RUNNING, module='STRAT', phase='PRE_CALCULATION'))

        from certus.workers.certus_strat_workers import (
            StatsConsumerWorker,
            _execute_nucleation_and_cost_mapping,
            LiveFeedMonitor,
            _run_phaseB_parallel_execution,
            _finalize_and_export_pipeline_results
        )

        stats_queue = _init_stats_queue()

        global _GLOBAL_STATS_QUEUE

        _GLOBAL_STATS_QUEUE = stats_queue

        consumer_worker = StatsConsumerWorker(stats_queue)
        worker.consumer_thread = QThread()
        consumer_worker.moveToThread(worker.consumer_thread)
        worker.consumer_thread.started.connect(consumer_worker.run)

        consumer_worker.update_stats.connect(worker.signals.update_stats)
        consumer_worker.finished.connect(worker.consumer_thread.quit)
        consumer_worker.finished.connect(consumer_worker.deleteLater)
        worker.consumer_thread.finished.connect(worker.consumer_thread.deleteLater)

        worker.consumer_thread.start()

        # SAFETY — queue.Queue (threading) not multiprocessing.Queue
        # The pool below is a ThreadPoolExecutor (threads, not processes).
        # multiprocessing.Queue uses OS pipes and hangs when consumed from threads.
        # DO NOT replace with multiprocessing.Queue without switching the pool to
        # ProcessPoolExecutor and verifying picklability of all enqueued objects.
        live_preview_queue = queue.Queue()

        shm_manager = None

        try:
            pre_calc_data, p_thick_nom, nucleation_info, nominal_res = _execute_nucleation_and_cost_mapping(
                params=worker.params,
                signals=worker.signals,
                nominal_res=getattr(worker, "nominal_results", None),
            )

            num_layers = pre_calc_data["num_layers"]

            blocks_range = _compute_blocks_range_for_params(num_layers, worker.params, dense=True)

            n_screen = int(worker.params.get("n_screen_runs", 25))

            k_keep = int(worker.params.get("k_keep_survivors", 10))

            n_full = int(worker.params.get("robustness_num_runs", 150))

            worker.params["logger"].info(f"🔄 PHASE 3: Dynamic Programming Strategy Optimization ({len(blocks_range)} steps) - HYBRID ENGINE...")

            # ── AXE 4.1 : LE RENDEMENT ENTRE DANS L'OBJECTIF DE LA DP ──────────
            #
            # 🔴 C'EST ICI QUE LA DONNEE ETAIT JETEE. Chaque entree de
            # `raw_results_sq` porte `crash_rate` — le taux de depots non terminables
            # par (couche, lambda), mesure par la Phase A. Cette ligne n'en retenait
            # que `x["cost"]` : le plantage ne servait qu'a un seuil binaire, et une
            # lambda a 0,001 % etait traitee comme une lambda a 0,106 %, alors qu'elles
            # different d'un facteur cent sur la seule grandeur qui SE COMPOSE sur la
            # hauteur de l'empilement.
            #
            # Le rendement d'un empilement vaut `prod(1 - p_i)`, dont le logarithme est
            # ADDITIF : c'est exactement ce qu'une DP de Bellman optimise exactement.
            #
            # `dp_yield_weight = 0` (defaut) laisse la carte inchangee, donc le
            # comportement d'avant au bit pres. La valeur ne se devine pas : elle se
            # balaie. Voir `build_yield_cost_map` et `combine_cost_and_yield`.
            cost_map_sq_clean = {
                l: {x["wl"]: x["cost"] for x in items} for l, items in pre_calc_data["raw_results_sq"].items()
            }
            _dp_yield_w = float(worker.params.get("dp_yield_weight", 0.0) or 0.0)
            if _dp_yield_w > 0.0:
                _yield_map = build_yield_cost_map(pre_calc_data["raw_results_sq"])
                _n_informative = sum(
                    1 for lm in _yield_map.values() for v in lm.values() if v > 0.0
                )
                _n_cells = sum(len(lm) for lm in _yield_map.values())
                worker.params["logger"].info(
                    f"   [RENDEMENT] DP sur cout + {_dp_yield_w:g} x (-log(1-p)) : "
                    f"{_n_informative}/{_n_cells} cellules (couche, lambda) portent un "
                    f"plantage mesurable. Les autres laissent le cout en nm departager."
                )
                cost_map_sq_clean = combine_cost_and_yield(
                    cost_map_sq_clean, _yield_map, _dp_yield_w
                )

            materials_db = worker.params.get("materials_db") or APP_CONTEXT.get("materials_db")

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
                    "nH_id": worker.params["nH_id"],
                    "nL_id": worker.params["nL_id"],
                    "nSub_id": worker.params["nSub_id"],
                    "l0": worker.params["l0"],
                    "sym_bonus_map": pre_calc_data.get("sym_bonus_map", {}),
                    "sym_layer_importance": pre_calc_data.get("sym_layer_importance", {}),
                }

                params_for_pool = {
                    k: v
                    for k, v in worker.params.items()
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
                    return worker.params.get("stop_requested", False)

                # SAFETY — strong reference prevents premature garbage collection
                # BUG HISTORY: Assigning to a local variable allowed Python to destroy
                # the LiveFeedMonitor object while monitor_thread was still running,
                # crashing Qt with a dangling C++ pointer error.
                # RULE: Always store on worker so the worker lives as long as WorkerThread.
                worker.monitor_thread = QThread()
                worker.monitor_worker = LiveFeedMonitor(
                    live_preview_queue=live_preview_queue,
                    signals=worker.signals,
                    p_thick_nominal=pre_calc_data["p_thick_nominal"],
                    clues_at_wl=pre_calc_data["clues_at_wl"],
                )
                worker.monitor_worker.moveToThread(worker.monitor_thread)
                worker.monitor_thread.started.connect(worker.monitor_worker.start)
                worker.monitor_worker.finished.connect(worker.monitor_thread.quit, Qt.ConnectionType.DirectConnection)
                worker.monitor_worker.finished.connect(worker.monitor_worker.deleteLater)
                worker.monitor_thread.finished.connect(worker.monitor_thread.deleteLater)
                worker.monitor_thread.start()

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
                    params=worker.params,
                    signals=worker.signals,
                    dyn_grid=pre_calc_data.get("full_dynamics_grid", {}),
                    stats_queue=stats_queue,
                    live_preview_queue=live_preview_queue,
                )

                live_preview_queue.put("STOP")
                if getattr(worker, "monitor_worker", None) is not None:
                    QMetaObject.invokeMethod(worker.monitor_worker, "stop", Qt.ConnectionType.QueuedConnection)
                if hasattr(worker, 'monitor_thread') and worker.monitor_thread:
                    worker.monitor_thread.quit()

                if hasattr(worker, 'monitor_thread') and worker.monitor_thread:
                    if not worker.monitor_thread.wait(3000):
                        worker.params["logger"].warning("Live preview monitor thread did not stop within 3s")

                worker.signals.progress_snapshot.emit(build_progress_snapshot(message="Finalizing results...", display_ratio=1.0, progress_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module='STRAT', phase='FINALIZE'))

                import gc
                gc.collect()

                final_result_dict = _finalize_and_export_pipeline_results(
                    accumulated_strategies_results=accumulated_strategies_results,
                    pre_calc_data=pre_calc_data,
                    nominal_res=nominal_res,
                    params=worker.params,
                    signals=worker.signals,
                    timing_logger=worker.timing_logger,
                )
                worker.signals.finished.emit(final_result_dict)

        finally:
            if hasattr(worker, 'monitor_thread') and worker.monitor_thread:
                if 'live_preview_queue' in locals() and live_preview_queue:
                    try:
                        live_preview_queue.put("STOP")
                    except Exception:
                        pass
                if getattr(worker, "monitor_worker", None) is not None:
                    try:
                        QMetaObject.invokeMethod(worker.monitor_worker, "stop", Qt.ConnectionType.QueuedConnection)
                    except Exception:
                        pass
                try:
                    worker.monitor_thread.quit()
                except Exception:
                    pass
                if not worker.monitor_thread.wait(3000):
                    worker.params["logger"].warning("Live preview monitor thread did not stop within 3s")

            if stats_queue:
                stats_queue.put(None)

            if 'consumer_worker' in locals():
                consumer_worker.is_running = False

            if hasattr(worker, 'consumer_thread') and worker.consumer_thread:
                try:
                    worker.consumer_thread.quit()
                except Exception:
                    pass
                if not worker.consumer_thread.wait(2000):
                    worker.params["logger"].warning("Stats consumer thread did not stop within 2s")

            _GLOBAL_STATS_QUEUE = None

            import gc
            gc.collect()
