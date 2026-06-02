# =========================================================================================
# ARCHITECTURE: LIGHTWEIGHT FAÇADE FOR BACKWARD COMPATIBILITY
# =========================================================================================

from certus.core.certus_core import __version__

import functools
import os
import sys
import multiprocessing
import ctypes
from pathlib import Path
import logging

from certus.core.certus_core import create_module_environment

env = create_module_environment(__file__, "STRAT")
script_dir = env["script_dir"]

# Standard Qt and styling setup imports
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from certus.core.certus_core import setup_module_logging, get_safe_worker_count
from certus.ui.certus_ui import init_certus_app
from certus.utils.certus_strat_db import RobustMaterialDatabase

from certus.utils.certus_strat_context import (
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
from certus_physics import (
    calculate_RT_vectorized_real_HL,
    validate_wavelengths_batch,
    update_run_states_kernel,
)

# Backward Compatibility Imports from submodules
from certus.core.certus_strat_core import (
    RobustnessContext,
    _IdxWrapper,
    DYNAMICS_METRIC_NAME,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_SCORING_MODE,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    set_robust_material_db,
    smart_get_refractive_index,
    smart_get_refractive_clues_vectorized,
    get_refractive_index,
    get_refractive_clues_vectorized,
    PERF_MONITOR,
    PlotCache,
    ThreadSafeCounter,
    APP_CONTEXT,
    CACHE_SIZE_MATERIAL_INDEX,
    IDENTITY_2x2_COMPLEX,
    _SPECTRUM_COUNTER,
    _LOCAL_LOCK,
    _GLOBAL_STATS_QUEUE,
    _GLOBAL_LIVE_QUEUE,
    _resolve_materials_db_fallback,
    _prepare_precompute_wavelength_grid,
    _resolve_clues_at_wavelength,
    _build_clues_at_wavelengths,
    _warn_backside_approximation_if_needed,
    _build_nominal_matrix_cache_from_clues,
    precompute_clues_and_matrices,
    _run_phase_a_hybrid_loop,
    _normalize_phase_a_results,
    _prepare_block_strategy_phase_a,
    _prepare_block_strategy_phase_b,
    _finalize_block_strategy_result,
    optimize_block_strategy_hybrid,
    _convert_solution_to_strategy,
    _generate_elite_candidate_strategies,
    _export_phase_a_observability_json,
    _find_k_best_groupings_dp_sequential,
    mine_strategies_for_block_count,
    _get_best_noise_results,
    _calculate_strategy_spectral_resolution,
    _build_layer_wavelengths_from_strategy,
    _validate_strategy_min_transmission_floor,
    _apply_strategy_ranking,
    _resolve_robustness_noise_levels,
    _filter_valid_robustness_strategies,
    _resolve_consensus_std_weight,
    _resolve_consensus_mode,
    _resolve_robustness_base_seed,
    _resolve_consensus_enabled,
    _build_consensus_ranking_params_dict,
    _init_consensus_map,
    _resolve_consensus_seeds,
    _filter_finite_robustness_scores,
    _resolve_consensus_ranking_params,
    _init_consensus_runtime_state,
    _unpack_consensus_cfg,
    _resolve_family_diversity_cfg,
    _resolve_elite_refinement_cfg,
    _resolve_nominal_noise_level,
    _resolve_available_wavelengths,
    _max_strategy_id,
    _existing_block_signatures,
    _extract_local_extrema_points,
    _compute_theoretical_layer_profile,
    _test_strategy_robustness_task,
    run_final_simulation_block,
    _select_candidates_phase_a,
    _validate_candidates_phase_a,
    _init_stats_queue,
    _worker_init,
    _emit_stat,
    _flush_sp_stats,
    _select_best_strat_result,
)
from certus.utils.certus_strat_service import extract_best_rmse

from certus.workers.certus_strat_workers import (
    WorkerSignals,
    WorkerThread,
    PlotRenderWorker,
    _resolve_strat_indices_db_path,
    _run_phaseB_parallel_execution,
    _run_phase0_and_phaseA,
    _parallel_block_worker,
)

from certus.ui.certus_strat_ui import (
    StrategiesTableWindow,
    CertusScientificPlot,
    UniversalPlotWindow,
    InteractiveHeatmapWindow,
    TransmissionVsThicknessWindow,
    StrategySpectralPerformanceWindow,
    JsonViewerWindow,
    InteractiveIndicesWindow,
    InteractiveSpectrumWindow,
    PopOutWindow,
    LiveMonitorWindow,
    WelcomeGuideWidget,
    CertusStratApp,
)

from certus.core.certus_core import CertusFacadeModule
import certus.core.certus_strat_core as certus_strat_core
import certus.workers.certus_strat_workers as certus_strat_workers
import certus.ui.certus_strat_ui as certus_strat_ui
import certus.utils.certus_strat_context as certus_strat_context
import certus.utils.certus_strat_db as certus_strat_db
import certus.utils.certus_strat_service as certus_strat_service

sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_strat_core,
    certus_strat_workers,
    certus_strat_ui,
    certus_strat_context,
    certus_strat_db,
    certus_strat_service
])

# Main Executable Flow
if __name__ == "__main__":
    multiprocessing.freeze_support()

    setup_module_logging("STRAT", log_file="strat.log")

    # High DPI scaling (Must be set BEFORE creating QApplication)
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON
    init_certus_app("CERTUS-STRAT", app=app)

    # --- SPLASH SCREEN ---
    from certus.ui.certus_splash import create_splash
    splash = create_splash("Initializing CERTUS STRAT...")

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
        pass

    splash.showMessage(
        "Starting User Interface...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    # Launch application UI
    win = CertusStratApp()
    win.show()
    splash.finish(win)

    # Load file from CLI if provided
    if len(sys.argv) > 1:
        f = sys.argv[1]
        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_configuration(f))

    sys.exit(app.exec())
