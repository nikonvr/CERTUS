
import pandas as pd


from certus.core.certus_core import (
    __version__,
    HC_EV_NM,
    N_MIN_LIMIT,
    N_MAX_LIMIT,
    K_MAX_LIMIT,
)
from certus.utils.certus_index_utils import DataType
from certus_physics import (
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
    epsilon_to_nk,
    get_n_substrate_array_by_id,
    calculate_RT_single_layer_backside_array,
    calculate_bare_substrate_RT,
)
from certus.core.certus_index_core import (
    OptimizationConfig,
    OptimizationResults,
    substrateMode,
    calculate_relative_R_normalization,
    _optimize_point_kernel,
    _optimize_all_points_batch,
)
from certus.workers.certus_index_workers import (
    IRGlobalModelWorker,
    OptimizationWorker,
    IndexBeamAnalysisWorker,
)

from certus.ui.certus_index_ui_utils import (
    _detected_data_type_label,
    _update_lambda_bounds_from_target_data,
    _source_type_label,
    _update_loaded_file_label,
    _set_spectrum_plot_title,
    _prepare_nk_plot_inputs,
)

# Import Modular Architecture


from certus.ui.certus_ui import (
    CertusBaseApp,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
)


# JIT Warmup (reduces first-call latency by ~90%)

# JIT Warmup moved to main() with SplashScreen




import scipy.optimize

from PyQt6.QtCore import QThread, pyqtSignal


# PyQtGraph configured via COMMON utility

setup_pyqtgraph_defaults()
setup_gui_exception_handling()


# =============================================================================

# MAIN APPLICATION

# =============================================================================

from certus.ui.certus_index_ui_layout import CertusIndexLayoutMixin
from certus.ui.certus_index_ui_state import CertusIndexStateMixin
from certus.ui.certus_index_ui_events import CertusIndexEventsMixin
from certus.ui.certus_index_ui_worker import CertusIndexWorkerMixin
from certus.ui.certus_index_ui_plot import CertusIndexPlotMixin
from certus.ui.certus_index_ui_export import CertusIndexExportMixin


class CertusIndexApp(CertusIndexLayoutMixin, CertusIndexStateMixin, CertusIndexEventsMixin, CertusIndexWorkerMixin, CertusIndexPlotMixin, CertusIndexExportMixin, CertusBaseApp):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
    """Main CERTUS-INDEX Application"""

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-INDEX"

    APP_TITLE = "Dielectric Index Characterization"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Apply theme before building UI

        self._apply_theme()

        self._build_ui()

        self._restore_index_weight_settings()

        self._wire_index_weight_persistence()

        self._persist_index_weight_settings()
        self._setup_shortcuts()

        # INDEX-specific state

        self._worker: OptimizationWorker | None = None

        self._thread: QThread | None = None

        self._worker2 = None

        self._thread2: QThread | None = None

        self._beam_worker: IndexBeamAnalysisWorker | None = None

        self._beam_thread: QThread | None = None

        self.target_data: pd.DataFrame | None = None

        self.data_type: DataType = DataType.TRANSMISSION

        self.substrate_mode: substrateMode = substrateMode.STANDARD

        self.exclude_region = None

        self.latest_results: OptimizationResults | None = None

        self.source_file_path = ""

        self.optimization_running = False

        self._executor = None

        self._vb_k = None

        # Convergence tracking data

        self.mse_data = {"iterations": [], "errors": []}

        self._last_progress_ui_update = 0.0

        self._last_phase_name = ""

        # Finalize (starts timers, triggers warmup)

        self._finalize_init()































































    # =========================================================================

    # EXCEL EXPORT

    # =========================================================================









    # =========================================================================

    # SAVE / LOAD CONFIGURATION

    # =========================================================================

    # save_config / load_config are inherited from CertusBaseApp and driven by
    # the _collect_config / _apply_config / _post_*_config hooks below.







        # Model & Optim params are handled by PGLOBAL engine and not exposed in UI config anymore.





