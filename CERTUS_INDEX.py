# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# P1 boundary: safe edits should first target small pure helpers, typing, logging,
# and UX labels. Keep numerical kernels and workflow orchestration stable unless
# a dedicated extraction/test plan exists.

# =========================================================================================

import logging
import multiprocessing
import sys
from pathlib import Path

#Numba configuration BEFORE any import using @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next
#to the sources, in the cloud-synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

from certus.core.certus_core import create_module_environment

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_INDEX")

script_dir = env["script_dir"]

# Legacy aliases or specific needs

# None required if refactoring is complete




import certus.core.certus_index_core as certus_index_core
import certus.ui.certus_index_ui as certus_index_ui
import certus.utils.certus_index_utils as certus_index_utils
import certus.workers.certus_index_workers as certus_index_workers
from certus.core.certus_core import (
    HC_EV_NM,
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    SUBSTRATES,
    CertusFacadeModule,
    __version__,
)
from certus.core.certus_index_config import (
    OptimizationConfig,
    OptimizationResults,
    substrateMode,
)
from certus.core.certus_index_core import (
    _optimize_all_points_batch,
    _optimize_point_kernel,
    calculate_relative_R_normalization,
)
from certus.core.certus_index_objectives import (
    IRGlobalObjective,
    Phase23SplineObjective,
)
from certus.core.certus_index_solvers import (
    PGlobalOptimizerINDEX,
)
from certus.ui.certus_index_ui import CertusIndexApp
from certus.ui.certus_index_ui_utils import (
    _detected_data_type_label,
    _prepare_nk_plot_inputs,
    _set_spectrum_plot_title,
    _source_type_label,
    _update_lambda_bounds_from_target_data,
    _update_loaded_file_label,
)
from certus.utils.certus_index_utils import (
    DataType,
    _detect_data_type_from_array,
    _detect_type_from_column_name,
    detect_data_type,
    sellmeier_2poles_eval_nj,
)
from certus.workers.certus_index_workers import (
    IRGlobalModelWorker,
    OptimizationWorker,
    Phase1Callback,
    Phase2PolishCallback,
)
from certus_physics import (
    calculate_bare_substrate_RT,
    calculate_RT_single_layer_backside_array,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    get_n_substrate_array_by_id,
)

sys.modules[__name__] = CertusFacadeModule(__name__, [
    certus_index_core,
    certus_index_workers,
    certus_index_ui,
    certus_index_utils
])

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Configure logging with centralized helper
    from certus.core.certus_core import setup_module_logging
    setup_module_logging("CERTUS_INDEX", log_file="certus_index.log")

    import warnings
    warnings.filterwarnings("once", category=UserWarning)
    warnings.filterwarnings("ignore", message="First-class function type feature is experimental")

    # Reduce console noise from the deepest optimizer warnings without hiding real failures.
    warnings.filterwarnings("once", message=r"\[CERTUS INDEX\] .* substrate reference unavailable: .*", category=UserWarning)

    # High DPI scaling (Must be set BEFORE creating QApplication)
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON
    from certus.ui.certus_ui import init_certus_app
    init_certus_app("CERTUS-INDEX", app=app)

    # --- SPLASH SCREEN ---
    from certus.ui.certus_splash import create_splash
    splash = create_splash("Initializing Physics Engine...")


    # Wait for background JIT warmup (launched by bootstrap_app)

    logging.info("Waiting for JIT Warmup...")

    from certus.core.certus_core import wait_warmup

    wait_warmup()

    splash.showMessage(
        "Starting User Interface...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    w = CertusIndexApp()

    w.show()

    splash.finish(w)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            # Try load_config first (JSON), fallback to load_file (CSV/Excel)

            if f.lower().endswith(".json"):
                QTimer.singleShot(100, lambda: w.load_config(f))

            else:
                QTimer.singleShot(100, lambda: w.load_file(f))

    sys.exit(app.exec())
