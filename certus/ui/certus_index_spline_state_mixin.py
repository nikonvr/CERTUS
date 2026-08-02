from __future__ import annotations
from certus.ui.certus_index_spline_common import *
from certus.spline.certus_index_spline_core import SPLINE_PERF_PRESETS

class CertusIndexSplineStateMixin:
    """CertusIndexSplineStateMixin."""

    def _load_defaults(self) -> None:

        self.df = None

        self._last_result = None

        self._corridor_rmse_base_snapshot = None

        self._best_live_rmse = float("inf")

        self._best_live_result = None
        self._corridor_auto_refine_plan = None

        self._live_best_detail_log_mono = 0.0

        if hasattr(self, "lbl_file"):
            self.lbl_file.setText("(no file)")

        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("Ready")

        if hasattr(self, "table_nk"):
            self._refresh_data_table()

        self._rmse_fit_lambda_enabled = bool(SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED)

        self._rmse_fit_lambda_lo = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

        self._rmse_fit_lambda_lo_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

        self._remove_rmse_fit_region_overlay()

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        self.sp_pg_iter.setValue(int(SPLINE_PERF_PRESETS.get("fast", {}).get("pglobal_max_iter", 35)))

        self.cb_profilee.setCurrentIndex(0)

        self._on_profilee_changed()

        if hasattr(self, "sp_mesh_min_dlam"):
            self.sp_mesh_min_dlam.setValue(0.02)

        self._simple_auto_uncertainty = True

        self._persist_simple_auto_uncertainty_pref()

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, int(_UNCERTAINTY_DEFAULTS_REV)
        )

        self._apply_recommended_uncertainty_and_perf_defaults()

        self._apply_sio2_default_fit_parameters()

        self._update_epured_visibility()

        if hasattr(self, "chk_t"):
            self.chk_t.setChecked(True)

        if hasattr(self, "chk_trel"):
            self.chk_trel.setChecked(True)

        if hasattr(self, "chk_r"):
            self.chk_r.setChecked(False)

        if hasattr(self, "w_t"):
            self.w_t.setValue(1.0)

        if hasattr(self, "w_r"):
            self.w_r.setValue(1.0)

        if hasattr(self, "cb_weight"):
            self.cb_weight.setCurrentIndex(0)

        if hasattr(self, "cb_sub"):
            self.cb_sub.setCurrentIndex(0)

        if hasattr(self, "ctrl_tabs"):
            self.ctrl_tabs.setCurrentIndex(0)

        if hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        self._prog_reset_bar()

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._refresh_post_optimization_option_controls()

        self._corridor_rmse_d_vals = np.array([], dtype=np.float64)

        self._corridor_rmse_vals = np.array([], dtype=np.float64)

        self._corridor_rmse_best_idx = -1

        self._corridor_rmse_center_nm = float("nan")

        self._corridor_rmse_robust_lo = float("nan")

        self._corridor_rmse_robust_hi = float("nan")

        self._corridor_rmse_robust_ok = False

        if hasattr(self, "lbl_corridor_rmse_summary"):
            self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
        if hasattr(self, "lbl_corridor_rmse_robust_compact"):
            self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        self._refresh_data_table()

        self._persist_spectrum_fit_settings()

        self._refresh_corridors_gui_state_labels()

    def closeEvent(self, event) -> None:
        """Stop cooperative workers before teardown to avoid Qt ``QThread: Destroyed while still running``.

        Mirrors CERTUS_DESIGN / METAL shutdown pattern: threading ``Event`` first, then QThread.wait.
        """
        prev_stop = getattr(self, "_stop_event", None)
        if getattr(prev_stop, "set", None) is not None:
            prev_stop.set()

        try:
            self._stop_all_workers()

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        w = getattr(self, "_worker", None)

        if w is not None and w.isRunning():
            try:
                if hasattr(w, "stop"):
                    w.stop()

            except (RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            for _ in range(80):
                if not w.isRunning():
                    break

                w.wait(50)

        self._cleanup_thread()

        super().closeEvent(event)
