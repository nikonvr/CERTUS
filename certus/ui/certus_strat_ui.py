from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_strat_mixins_ui import CertusWindowSpyMixin
from certus.ui.certus_strat_table_ui import StrategiesTableWindow
from certus.ui.certus_strat_plots_ui import CertusScientificPlot, UniversalPlotWindow
from certus.ui.certus_strat_heatmap_ui import InteractiveHeatmapWindow
from certus.ui.certus_strat_thickness_ui import TransmissionVsThicknessWindow
from certus.ui.certus_strat_performance_ui import StrategySpectralPerformanceWindow
from certus.ui.certus_strat_json_ui import JsonViewerWindow
from certus.ui.certus_strat_indices_ui import InteractiveIndicesWindow
from certus.ui.certus_strat_spectrum_ui import InteractiveSpectrumWindow
from certus.ui.certus_strat_popout_ui import PopOutWindow
from certus.ui.certus_strat_monitor_ui import LiveMonitorWindow
from certus.ui.certus_strat_welcome_ui import WelcomeGuideWidget



# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# === GUI CLASSES (RECONSTITUTION STYLE VERSION D) ===










# QueueHandler and setup_gui_logger are imported from certus.ui.certus_ui

# === OPTIMIZATION: LiveMonitor with Convergence Plot ===


from certus.ui.certus_strat_ui_layout import CertusStratLayoutMixin
from certus.ui.certus_strat_ui_state import CertusStratStateMixin
from certus.ui.certus_strat_ui_events import CertusStratEventsMixin
from certus.ui.certus_strat_ui_worker import CertusStratWorkerMixin
from certus.ui.certus_strat_ui_plot import CertusStratPlotMixin
from certus.ui.certus_strat_ui_export import CertusStratExportMixin


class CertusStratApp(CertusWindowSpyMixin, CertusStratLayoutMixin, CertusStratStateMixin, CertusStratEventsMixin, CertusStratWorkerMixin, CertusStratPlotMixin, CertusStratExportMixin, CertusBaseApp):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
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

        self._active_worker_threads: list[QThread] = []

        self._stopping_threads: list[QThread] = []

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
        self._live_strategy_popups: list[QMessageBox] = []

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

        # Warmup: _warmup_numba manages its own internal thread, call directly from main thread

        self._warmup_numba()

        # Post-init setup

        QTimer.singleShot(100, lambda: self._init_undo_shortcut())

        QTimer.singleShot(0, self.apply_default_layout)











































































    # === OPTIMIZATION: Hashed & Async Plot Update ===






    # ===============================================





# Backward-compatible alias kept for existing callers/tests.
CertusSTRATApp = CertusStratApp

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # NOTE: We do NOT touch SystemConfig.setup_numba_cache() here

    # because it's already done at the top of the file and at COMMON import.

    # Calling startup logging helper is OK because it doesn't touch Numba.

    setup_module_logging("STRAT", log_file="strat.log")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Application creation (MUST be done before theme)

    app = QApplication(sys.argv)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-STRAT", app=app)

    # --- SPLASH SCREEN ---

    from certus.ui.certus_splash import create_splash

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
