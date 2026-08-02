from __future__ import annotations
from certus.ui.certus_index_spline_common import *
from certus.ui.certus_index_spline_common import (
    _CorridorControlMixin, _SettingsMixin, _CorridorGenMixin, _DataMixin,
    _RunMixin, _CorridorExportMixin, _UIBuilderMixin, _PlotMixin,
    _CorridorWorkerMixin, _SmartInitDialogMixin, _LazyCertusIndexSplineApp,
    _ConfigBuilderMixin, _MeshOptimizationMixin, _ExcelExportMixin, _UIMixin
)
from certus.ui.certus_index_spline_layout_mixin import CertusIndexSplineLayoutMixin
from certus.ui.certus_index_spline_state_mixin import CertusIndexSplineStateMixin
from certus.ui.certus_index_spline_table_mixin import CertusIndexSplineTableMixin
from certus.ui.certus_index_spline_plot_mixin import CertusIndexSplinePlotMixin
from certus.ui.certus_index_spline_smartinit_mixin import CertusIndexSplineSmartInitMixin
from certus.ui.certus_index_spline_manualmesh_mixin import CertusIndexSplineManualMeshMixin
from certus.ui.certus_index_spline_corridorui_mixin import CertusIndexSplineCorridorUIMixin
from certus.ui.certus_index_spline_spectrumui_mixin import CertusIndexSplineSpectrumUIMixin
from certus.ui.certus_index_spline_layoutextras_mixin import CertusIndexSplineLayoutExtrasMixin
from certus.ui.certus_index_spline_eventsextras_mixin import CertusIndexSplineEventsExtrasMixin
from certus.ui.certus_index_spline_workers_mixin import CertusIndexSplineWorkersMixin

class CertusIndexSplineApp(
    _CorridorControlMixin,
    _SettingsMixin,
    _CorridorGenMixin,
    _DataMixin,
    _RunMixin,
    _CorridorExportMixin,
    _UIBuilderMixin,
    _PlotMixin,
    _CorridorWorkerMixin,
    _SmartInitDialogMixin,
    _ConfigBuilderMixin,
    _MeshOptimizationMixin,
    _ExcelExportMixin,
    _UIMixin,
    CertusIndexSplineLayoutMixin,
    CertusIndexSplineStateMixin,
    CertusIndexSplineTableMixin,
    CertusIndexSplinePlotMixin,
    CertusIndexSplineSmartInitMixin,
    CertusIndexSplineManualMeshMixin,
    CertusIndexSplineCorridorUIMixin,
    CertusIndexSplineSpectrumUIMixin,
    CertusIndexSplineLayoutExtrasMixin,
    CertusIndexSplineEventsExtrasMixin,
    CertusIndexSplineWorkersMixin,
    CertusBaseApp,
):
    """CERTUS application to optimize spline parameters for a given substrate index model."""

    APP_NAME = "CERTUS_INDEX_SPLINE"
    APP_TITLE = "CERTUS  Index Spline Optimization"
    DEFAULT_WIDTH = 1380
    DEFAULT_HEIGHT = 650
    MIN_WIDTH = 1100
    MIN_HEIGHT = 200

    smart_preview_requested = pyqtSignal(object)

    def __init__(self) -> None:

        super().__init__()

        self._setup_logger(self.APP_NAME)

        self._log_prog_last: int = -1

        self._prog_ui_last: int = 0

        self._last_live_log_mono: float = 0.0

        self._live_best_detail_log_mono: float = 0.0

        self.df: pd.DataFrame | None = None

        self._worker: GenericWorker | None = None

        self._stop_event = Event()

        self._last_result: dict | None = None

        self._last_worker_result: dict | None = None

        self._corridor_rmse_base_snapshot: dict | None = None

        self._last_run_cfg: SplineOptConfig | None = None

        self._worker_role: str = "idle"

        self._best_live_rmse: float = float("inf")

        self._best_live_result: dict | None = None

        self._corridor_rmse_manual_active: bool = False

        self._corridor_rmse_manual_lo: float = float("nan")

        self._corridor_rmse_manual_hi: float = float("nan")

        self._corridor_rmse_manual_slider_scale: int = 100

        self._last_spectrum_path: str = ""

        self._pending_auto_best_adaptive: dict[str, Any] | None = None

        self._auto_best_local_warm: dict[str, Any] | None = None

        self._auto_best_force_smart_init: bool = False

        self._auto_best_two_stage_refine: bool = False

        self._auto_best_second_stage_pending: dict[str, Any] | None = None
        self._corridor_auto_refine_plan: dict[str, Any] | None = None

        self._preview_wait_event: Event | None = None

        self._rmse_fit_lambda_enabled: bool = SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED

        self._rmse_fit_lambda_lo: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM

        self._rmse_fit_lambda_hi: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM

        self._rmse_fit_lambda_lo_default: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM

        self._rmse_fit_lambda_hi_default: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM

        self._rmse_fit_overlay_items: list[Any] = []

        self._simple_auto_uncertainty: bool = True

        self._build_ui()

        install_standard_shortcuts(
            self,
            save=getattr(self, "save_config", None),
            load=lambda: self._on_load(),
            export=getattr(self, "export_excel", None),
            run=getattr(self, "_on_run", None),
            stop=getattr(self, "_on_stop", None),
            help=lambda: open_documentation("CERTUS_INDEX_SPLINE"),
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
        )

        def _on_spectrum_drop(paths) -> None:
            if paths:
                self._on_load(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_spectrum_drop, extensions=("csv", "xlsx", "xls", "txt"))

        self._restore_simple_auto_uncertainty_pref()

        self._restore_spectrum_fit_settings()

        self._restore_splitter_states()

        self._maybe_apply_uncertainty_defaults_migrated()

        self._refresh_corridors_gui_state_labels()

        self._update_epured_visibility()

        self._wire_spectrum_fit_settings_persistence()

        self._persist_spectrum_fit_settings()

        self.smart_preview_requested.connect(self._on_smart_preview_requested)

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}
            """,
            plots=[
                self.plot_T,
                self.plot_n,
                self.plot_k,
                self.plot_n_corridor,
                self.plot_k_corridor,
                self.plot_corridor_rmse_d,
            ],
        )

        self._finalize_init()


def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusIndexSplineApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
