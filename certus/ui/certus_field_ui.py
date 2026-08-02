from __future__ import annotations
from certus.ui.certus_field_common import *
from certus.workers.certus_strat_workers import _resolve_strat_indices_db_path
from certus.ui.certus_field_layout_mixin import CertusFieldLayoutMixin
from certus.ui.certus_field_plot_mixin import CertusFieldPlotMixin
from certus.ui.certus_field_events_mixin import CertusFieldEventsMixin
from certus.ui.certus_field_workers_mixin import CertusFieldWorkersMixin
from certus.ui.certus_field_state_mixin import CertusFieldStateMixin


class CertusFieldApp(
    CertusBaseApp,
    CertusAppLogsMixin,
    CertusFieldLayoutMixin,
    CertusFieldPlotMixin,
    CertusFieldEventsMixin,
    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):
    APP_NAME = "CERTUS-FIELD"
    APP_TITLE = "Electric Field Optimization"
    APP_VERSION = "1.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_logger(self.APP_NAME)
        self.worker = None
        self.current_result = None
        self.detached_plot_windows = {}
        self.detached_stack_window = None
        self._is_updating_table = False
        self._skip_auto_calc = False
        self._initial_field_data = None
        self._initial_spectral_data = None
        self.pareto_history = {}
        self.pareto_window = None
        self._pareto_initialized = False
        self._pareto_cleanup_pending = False
        self._last_plot_data = None  # Initialized here to prevent AttributeError before first calculation

        # Auto-calculation timer setup
        self.auto_calc_timer = QTimer(self)
        self.auto_calc_timer.setSingleShot(True)
        self.auto_calc_timer.timeout.connect(self.run_auto_calc)

        # Init Material Database
        try:
            self.materials_db = MaterialDatabase(_resolve_strat_indices_db_path())
            self.material_list = self.materials_db.get_material_list()
        except Exception as e:
            self.logger.error(f"Error loading material database: {e}")
            self.materials_db = None
            self.material_list = []

        self._build_ui()
        self.progress_widget = EnhancedProgressWidget()
        self.status_bar.addPermanentWidget(self.progress_widget)
        self.field_opt_status = QLabel("Ready")
        self.field_opt_status.setObjectName("fieldOptStatus")
        self.field_opt_status.setStyleSheet("font-weight: 600; padding: 0 8px;")
        self.status_bar.addPermanentWidget(self.field_opt_status)
        self._finalize_init()

        # Connect additional signals for auto-calculation
        self.optics_panel.edit_lcalc.textChanged.connect(self.trigger_auto_calc)
        self.optics_panel.edit_angle.valueChanged.connect(self.trigger_auto_calc)


def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusFieldApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
