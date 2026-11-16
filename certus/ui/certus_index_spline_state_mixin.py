from __future__ import annotations

import logging

import numpy as np

from certus.spline.certus_index_spline_core import SPLINE_PERF_PRESETS
from certus.ui.certus_config_table import ConfigField, apply_table, collect_table
from certus.ui.certus_index_spline_common import (
    _QS_SPLINE_APP,
    _QS_SPLINE_ORG,
    _QS_SPLINE_UNCERTAINTY_DEFAULTS_REV,
    _UNCERTAINTY_DEFAULTS_REV,
    SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED,
    SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM,
    SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM,
)
from certus.utils.certus_qsettings import certus_settings

# The fit settings an INDEX SPLINE configuration saves and loads back, in the order they are loaded; the fit window
# of the RMSE (rmse_fit_lambda_*) is held by the window, not by a widget, and is saved beside them.
INDEX_SPLINE_CONFIG_TABLE = (
    ConfigField("fit_t", "chk_t", "bool"),
    ConfigField("fit_t_ratio", "chk_trel", "bool"),
    ConfigField("fit_r", "chk_r", "bool"),
    ConfigField("weight_t", "w_t", "float"),
    ConfigField("weight_r", "w_r", "float"),
    ConfigField("d_nominal_nm", "d_lo", "float"),
    ConfigField("d_tolerance_nm", "d_hi", "float"),
    ConfigField("mesh_min_dlambda_over_lambda", "sp_mesh_min_dlam", "float"),
    ConfigField("substrate", "cb_sub", "data"),
    ConfigField("profile", "cb_profilee", "data"),
)

# The editable widgets the table does not carry, with the reason (owner's decision of 2026-11-16: the configuration
# keeps the fit settings only).
_CORRIDOR_WIDGETS = (
    "cb_corr_boot_mode", "cb_corr_mode", "chk_corr_boot", "chk_corr_boot_refit", "chk_corr_reg_sens",
    "chk_corr_scientific_nominal", "chk_corr_sigma_hetero", "chk_corridor_d", "chk_corridor_rmse_envelope_only",
    "chk_corridor_rmse_live_parabola", "chk_corridor_rmse_lock_scale", "chk_corridor_rmse_show_advanced",
    "sl_corridor_manual_half", "sp_corr_alpha", "sp_corr_boot_block", "sp_corr_boot_maxfun", "sp_corr_boot_n",
    "sp_corr_boot_p", "sp_corr_boot_seed", "sp_corr_boot_workers", "sp_corr_conf", "sp_corr_hetero_scale",
    "sp_corr_jL", "sp_corr_jn", "sp_corr_prof_maxfun", "sp_corr_reg_dec", "sp_corr_reg_pts", "sp_corr_rmse_delta",
    "sp_corr_seed", "sp_corr_sigma", "sp_corr_span", "sp_corr_starts", "sp_corr_step",
    "sp_corridor_breakpoint_lookback", "sp_corridor_grid_d_step_nm", "sp_corridor_grid_n_points",
    "sp_corridor_partial_delta_nm", "sp_corridor_rmse_delta", "sp_corridor_rmse_win",
)
_AUTO_CLEAN_WIDGETS = (
    "chk_auto_clean_neighbor_pull", "chk_auto_clean_neighbor_pull_local_refine", "sp_auto_clean_cand_maxfun",
    "sp_auto_clean_neighbor_pull_local_refine_step", "sp_auto_clean_pull_r1", "sp_auto_clean_pull_r2",
    "sp_auto_clean_pull_r3", "sp_auto_clean_tol", "sp_auto_clean_top_n",
)
INDEX_SPLINE_CONFIG_OUTSIDE_TABLE = {
    **{name: "corridor analysis, run after the fit" for name in _CORRIDOR_WIDGETS},
    **{name: "automatic cleanup of the mesh, a tool run after the fit" for name in _AUTO_CLEAN_WIDGETS},
    "sp_pg_iter": "inactive in local-only mode; follows the profile",
    "cb_spectrum_xmode": "display: abscissa of the spectrum plot",
}


class CertusIndexSplineStateMixin:
    _COMPUTATION_THREADS = ("_worker",)
    """CertusIndexSplineStateMixin."""

    def _collect_config(self) -> dict:
        """Collect the fit controls restored by ``_apply_config``."""
        return {
            **collect_table(self, INDEX_SPLINE_CONFIG_TABLE),
            "rmse_fit_lambda_enabled": bool(self._rmse_fit_lambda_enabled),
            "rmse_fit_lambda_lo_nm": float(self._rmse_fit_lambda_lo),
            "rmse_fit_lambda_hi_nm": float(self._rmse_fit_lambda_hi),
        }

    def _apply_config(self, config: dict) -> None:
        """Restore the controls saved in an INDEX SPLINE settings JSON."""
        for key, widget in (("substrate", self.cb_sub), ("profile", self.cb_profilee)):
            # A substrate or profile this window does not offer is refused, not replaced by the one shown.
            if config.get(key) is not None and widget.findData(config[key]) < 0:
                raise ValueError(f"Unknown INDEX SPLINE {key}: {config[key]!r}")
        apply_table(self, INDEX_SPLINE_CONFIG_TABLE, config)

        if "rmse_fit_lambda_enabled" in config:
            self._rmse_fit_lambda_enabled = bool(config["rmse_fit_lambda_enabled"])
        if "rmse_fit_lambda_lo_nm" in config:
            self._rmse_fit_lambda_lo = float(config["rmse_fit_lambda_lo_nm"])
        if "rmse_fit_lambda_hi_nm" in config:
            self._rmse_fit_lambda_hi = float(config["rmse_fit_lambda_hi_nm"])
        self._update_rmse_fit_region_overlay()

    def _load_defaults(self) -> None:

        self.df = None

        self._last_result = None

        # The last run goes with it: the corridor tabs take their source in its raw result, and the grid in its configuration.
        self._last_worker_result = None
        self._last_run_cfg = None

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

        certus_settings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
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

        # What the two corridor tabs and the grid recalculation wrote for the sample that is being forgotten.
        self._corridor_rmse_smart_interval = None
        self._corridor_rmse_parab_export = None
        self._corridor_rmse_robust_export = None
        self._corridor_rmse_requested_grid = np.array([])
        self._corridor_k_crosshair_lam = []
        self._corridor_k_crosshair_nom = []
        self._corridor_k_crosshair_lo = []
        self._corridor_k_crosshair_hi = []

        if hasattr(self, "lbl_corridor_rmse_summary"):
            self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
        if hasattr(self, "lbl_corridor_rmse_robust_compact"):
            self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")
        self._update_corridor_rmse_state_bar()

        self._refresh_data_table()

        self._persist_spectrum_fit_settings()

        self._refresh_corridors_gui_state_labels()

    def closeEvent(self, event) -> None:
        """Stop cooperative workers before teardown to avoid Qt ``QThread: Destroyed while still running``.

        Mirrors CERTUS_DESIGN / METAL shutdown pattern: threading ``Event`` first, then QThread.wait.
        """
        if not self.confirm_close_during_run(event):  # D41: ask before the workers below are stopped
            return
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
