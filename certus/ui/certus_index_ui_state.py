from pathlib import Path

_QS_INDEX_ORG = "CERTUS"
_QS_INDEX_APP = "INDEX"
_QS_INDEX_WEIGHT_T = "cost_weight_t"
_QS_INDEX_WEIGHT_R = "cost_weight_r"

import scipy.optimize
from PyQt6.QtWidgets import (
    QMessageBox,
)

from certus.core.certus_core import (
    __version__,
)
from certus.core.certus_index_core import (
    OptimizationConfig,
    substrateMode,
)
from certus.ui.certus_config_table import ConfigField, apply_table, collect_table
from certus.ui.certus_ui_utils import notify
from certus.utils.certus_index_utils import DataType, normalize_index_config
from certus.utils.certus_qsettings import certus_settings


def _weights_apply(cfg) -> bool:
    """Frosted glass forces the weights (T = 0, R = 1): a frosted configuration does not load them."""
    return not cfg.get("frosted", False)


# The settings an INDEX configuration saves and loads back, in the order they are loaded: the substrate first (it resets
# the substrate thickness), frosted glass before the boxes and weights it forces, the excluded range before the OH box
# that overwrites it.
INDEX_CONFIG_TABLE = (
    ConfigField("substrate", "cb_sub", "text", ""),
    ConfigField("frosted", "rb_frosted_glass", "bool", False, off_widget="rb_standard"),
    ConfigField("thickness_min", "sb_dmin", "float", 50.0),
    ConfigField("thickness_max", "sb_dmax", "float", 1000.0),
    ConfigField("normalized", "chk_normalized", "bool", True),
    ConfigField("exclude_oh", "chk_exclude", "bool", False),
    ConfigField("exclude_min", "sb_ex_min", "float"),
    ConfigField("exclude_max", "sb_ex_max", "float"),
    ConfigField("fit_lambda_min", "sb_lmin", "float"),
    ConfigField("fit_lambda_max", "sb_lmax", "float"),
    ConfigField("substrate_thickness_mm", "sb_sub_thickness_mm", "float"),
    ConfigField("oh_band", "chk_oh_band", "bool", False),
    ConfigField("high_precision", "chk_high_precision", "bool", False),
    ConfigField("weight_T", "sb_weight_T", "float", 1.0, applies=_weights_apply),
    ConfigField("weight_R", "sb_weight_R", "float", 1.0, applies=_weights_apply),
)

# The editable widgets the table does not carry, with the reason.
INDEX_CONFIG_OUTSIDE_TABLE = {
    "chk_absorbing_sub": "set by the substrate: checked and locked for silicon, unchecked and hidden otherwise",
}


class CertusIndexStateMixin:
    def _load_defaults(self) -> None:
        """Load default values for CERTUS-INDEX"""
        self._ir_analytic_polish = False

        # Reset file selection

        self.source_file_path = ""

        self.target_data = None

        self.latest_results = None

        # Reset data type and substrate mode

        self.data_type = DataType.TRANSMISSION

        self.substrate_mode = substrateMode.STANDARD

        self.exclude_region = None

        self._vb_k = None

        # Reset UI elements to defaults

        if hasattr(self, "cb_data_type"):
            self.cb_data_type.setCurrentIndex(0)  # Transmission

        if hasattr(self, "cb_substrate_mode"):
            self.cb_substrate_mode.setCurrentIndex(0)  # Standard

        if hasattr(self, "lbl_file"):
            self.lbl_file.setText("(no file selected)")

        if hasattr(self, "lbl_final_eq"):
            self.lbl_final_eq.setText("Run optimization to see final equations.")

        if hasattr(self, "btn_copy_eq"):
            self.btn_copy_eq.setEnabled(False)

        if hasattr(self, "btn_copy_nk"):
            self.btn_copy_nk.setEnabled(False)

        if hasattr(self, "btn_copy_params"):
            self.btn_copy_params.setEnabled(False)

        if hasattr(self, "table_res"):
            self.table_res.clearContents()

            self.table_res.setRowCount(0)

            self.table_res.setColumnCount(0)

        if hasattr(self, "table_params"):
            self.table_params.clearContents()

            self.table_params.setRowCount(0)

            self.table_params.setColumnCount(2)

            self.table_params.setHorizontalHeaderLabels(["Parameter", "Value"])

        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)

        if hasattr(self, "recap_widget"):
            self.recap_widget.setVisible(False)

        # Reset convergence tracking

        self.mse_data = {"iterations": [], "errors": []}

        self.optimization_running = False

        if hasattr(self, "rb_standard"):
            self.rb_standard.setChecked(True)

        if hasattr(self, "_on_substrate_mode_changed"):
            self._on_substrate_mode_changed()

        if hasattr(self, "_persist_index_weight_settings"):
            self._persist_index_weight_settings()

    def _restore_index_weight_settings(self) -> None:
        """Reads wT / wR from QSettings (session)."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = certus_settings(_QS_INDEX_ORG, _QS_INDEX_APP)

        self.sb_weight_T.blockSignals(True)

        self.sb_weight_R.blockSignals(True)

        try:
            wt = s.value(_QS_INDEX_WEIGHT_T)

            if wt is not None:
                self.sb_weight_T.setValue(float(wt))

            wr = s.value(_QS_INDEX_WEIGHT_R)

            if wr is not None:
                self.sb_weight_R.setValue(float(wr))

        finally:
            self.sb_weight_T.blockSignals(False)

            self.sb_weight_R.blockSignals(False)

    def _persist_index_weight_settings(self) -> None:
        """Saves wT / wR for the next launch."""

        if not hasattr(self, "sb_weight_T"):
            return

        s = certus_settings(_QS_INDEX_ORG, _QS_INDEX_APP)

        s.setValue(_QS_INDEX_WEIGHT_T, float(self.sb_weight_T.value()))

        s.setValue(_QS_INDEX_WEIGHT_R, float(self.sb_weight_R.value()))

    def _wire_index_weight_persistence(self) -> None:

        self.sb_weight_T.valueChanged.connect(self._persist_index_weight_settings)

        self.sb_weight_R.valueChanged.connect(self._persist_index_weight_settings)

    def _get_config_file_filter(self) -> str:

        return "JSON (*.json)"

    def _collect_config(self) -> dict:
        """Serialize the CERTUS_INDEX widget state to a JSON-ready dict."""

        opt_block = {}
        if getattr(self, "_ir_analytic_polish", False):
            opt_block["ir_analytic_polish"] = True

        # This window has no data-type combo, model combo nor parameter spins: their keys keep the values they always had.
        return {
            "version": __version__,
            "data_type": "",
            "file_loaded": getattr(self, "source_file_path", None),
            **collect_table(self, INDEX_CONFIG_TABLE),
            "model_type": "TLU",
            "params": [],
            "optimization": opt_block,
        }

    def _normalize_index_config(self, cfg: dict) -> dict:
        """Normalize legacy/new CERTUS_INDEX JSON payloads for first-launch compatibility."""
        return normalize_index_config(cfg)

    def _config_load_problems(self, cfg: dict) -> list[str]:
        """A substrate this window does not offer (D88): the list would keep the previous one."""
        sub = self._normalize_index_config(cfg).get("substrate")
        if sub and hasattr(self, "cb_sub") and self.cb_sub.findText(str(sub)) < 0:
            return [f'Substrate: "{sub}" is not one of the substrates of this window.']
        return []

    def _apply_config(self, cfg: dict) -> None:
        """Restore CERTUS_INDEX widget state from a loaded config dict.

        Note: the measured spectrum file referenced by ``file_loaded`` is
        intentionally NOT auto-loaded to avoid broken paths when sharing
        configs across machines.
        """

        cfg = self._normalize_index_config(cfg)
        self._ir_analytic_polish = bool(cfg.get("optimization", {}).get("ir_analytic_polish", False))

        apply_table(self, INDEX_CONFIG_TABLE, cfg)

        if not cfg.get("frosted", False):
            self._persist_index_weight_settings()

    def _post_save_config(self, filename: str) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Saved: {Path(filename).name}")

        notify(self, "Saved", f"Configuration saved to {Path(filename).name}")

    def _post_load_config(self, filename: str, config: dict) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Loaded: {Path(filename).name}")

        # Keep substrate semantics explicit in the UI metadata.
        if hasattr(self, "logger"):
            self.logger.info("CERTUS_INDEX config applied with substrate/film fields kept distinct.")

    def _reset_optimization_progress_state(self, config: OptimizationConfig) -> None:
        """Reset progress and convergence widgets before launching the worker thread."""

        self.progress_widget.start()

        self._total_iterations = 0

        self._best_rmse_display = float("inf")

        # Reset convergence chart (UX-3)
        self._conv_iterations.clear()
        self._conv_rmse_current.clear()
        self._conv_rmse_best.clear()
        if hasattr(self, "_conv_curve_current"):
            self._conv_curve_current.setData([], [])
        if hasattr(self, "_conv_curve_best"):
            self._conv_curve_best.setData([], [])

        # Real evaluation tracking for accurate ETA
        self._current_n_evals = 0
        self._max_evals = 80000 if config.high_precision else 20000

