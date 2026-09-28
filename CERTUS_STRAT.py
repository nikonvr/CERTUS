# =========================================================================================
# ARCHITECTURE: LIGHTWEIGHT FACADE FOR BACKWARD COMPATIBILITY
# =========================================================================================

#Numba configuration BEFORE any import pulling @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next to it
#sources, in the cloud synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import __version__

import sys
import multiprocessing
import ctypes
from pathlib import Path
import logging

from certus.core.certus_core import create_module_environment

env = create_module_environment(__file__, "STRAT")
script_dir = env["script_dir"]

from certus.core.certus_core import setup_module_logging

from certus.utils.certus_strat_context import (
    _compute_local_extrema_symmetry_score,
    _build_symmetry_bonus_map,
    _compute_blocks_range_contractual,
    _validate_strategy_blocks_contract,
    _augment_solution_cost_with_sym,
)
from certus_physics import (
    validate_wavelengths_batch,
    update_run_states_kernel,
)

# Backward Compatibility Imports from submodules
from certus.core.certus_strat_core import (
    DYNAMICS_METRIC_NAME,
    set_robust_material_db,
    get_refractive_clues_vectorized,
    PlotCache,
    ThreadSafeCounter,
    APP_CONTEXT,
    _generate_elite_candidate_strategies,
    _find_k_best_groupings_dp_sequential,
    mine_strategies_for_block_count,
    _extract_local_extrema_points,
    _compute_theoretical_layer_profile,
    _test_strategy_robustness_task,
    run_final_simulation_block,
)
from certus.utils.certus_strat_service import (
    extract_best_rmse,
    _select_candidates_phase_a,
    _validate_candidates_phase_a,
)
from certus.core.certus_strat_ranking import _select_best_strat_result

from certus.workers.certus_strat_workers import (
    _resolve_strat_indices_db_path,
    _parallel_block_worker,
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

    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication
    from certus.ui.certus_ui import init_certus_app
    from certus.utils.certus_strat_db import RobustMaterialDatabase
    from certus.ui.certus_strat_ui import CertusStratApp

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
