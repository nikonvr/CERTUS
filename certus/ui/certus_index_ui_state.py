from pathlib import Path
import numpy as np
import pandas as pd

_QS_INDEX_ORG = "CERTUS"
_QS_INDEX_APP = "INDEX"
_QS_INDEX_WEIGHT_T = "cost_weight_t"
_QS_INDEX_WEIGHT_R = "cost_weight_r"

from certus.core.certus_core import (
    __version__,
)
from certus.utils.certus_index_utils import DataType, normalize_index_config
from certus.core.certus_index_core import (
    OptimizationConfig,
    substrateMode,
)
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtWidgets import (
    QMessageBox,
)
from certus.utils.certus_qsettings import certus_settings

class CertusIndexStateMixin:
    def _load_defaults(self) -> None:
        """Load default values for CERTUS-INDEX"""

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

        params_values = []

        if hasattr(self, "input_params"):
            params_values = [s.value() for s in self.input_params]

        opt_block = {}

        if hasattr(self, "input_max_feval"):
            opt_block["max_feval"] = int(self.input_max_feval.value())

        return {
            "version": __version__,
            "substrate": self.cb_sub.currentText() if hasattr(self, "cb_sub") else "",
            "frosted": self.rb_frosted_glass.isChecked() if hasattr(self, "rb_frosted_glass") else False,
            "data_type": self.cb_data_type.currentText() if hasattr(self, "cb_data_type") else "",
            "file_loaded": getattr(self, "source_file_path", None),
            "thickness_min": self.sb_dmin.value() if hasattr(self, "sb_dmin") else 50.0,
            "thickness_max": self.sb_dmax.value() if hasattr(self, "sb_dmax") else 1000.0,
            "normalized": self.chk_normalized.isChecked() if hasattr(self, "chk_normalized") else True,
            "exclude_oh": self.chk_exclude.isChecked() if hasattr(self, "chk_exclude") else False,
            "exclude_min": self.sb_ex_min.value() if hasattr(self, "sb_ex_min") else None,
            "exclude_max": self.sb_ex_max.value() if hasattr(self, "sb_ex_max") else None,
            "model_type": (self.model_combo.currentText() if hasattr(self, "model_combo") else "TLU"),
            "params": params_values,
            "optimization": opt_block,
            "weight_T": float(self.sb_weight_T.value()) if hasattr(self, "sb_weight_T") else 1.0,
            "weight_R": float(self.sb_weight_R.value()) if hasattr(self, "sb_weight_R") else 1.0,
        }

    def _normalize_index_config(self, cfg: dict) -> dict:
        """Normalize legacy/new CERTUS_INDEX JSON payloads for first-launch compatibility."""
        return normalize_index_config(cfg)

    def _apply_config(self, cfg: dict) -> None:
        """Restore CERTUS_INDEX widget state from a loaded config dict.

        Note: the measured spectrum file referenced by ``file_loaded`` is
        intentionally NOT auto-loaded to avoid broken paths when sharing
        configs across machines.
        """

        cfg = self._normalize_index_config(cfg)

        sub = cfg.get("substrate")

        if sub and hasattr(self, "cb_sub"):
            idx = self.cb_sub.findText(str(sub))

            if idx >= 0:
                self.cb_sub.setCurrentIndex(idx)

        if cfg.get("frosted", False):
            self.rb_frosted_glass.setChecked(True)

        else:
            self.rb_standard.setChecked(True)

        self.sb_dmin.setValue(cfg.get("thickness_min", 10.0))

        self.sb_dmax.setValue(cfg.get("thickness_max", 1000.0))

        self.chk_normalized.setChecked(cfg.get("normalized", False))

        self.chk_exclude.setChecked(cfg.get("exclude_oh", False))

        if not cfg.get("frosted", False):
            wt = cfg.get("weight_T")

            if wt is not None and hasattr(self, "sb_weight_T"):
                self.sb_weight_T.setValue(float(wt))

            wr = cfg.get("weight_R")

            if wr is not None and hasattr(self, "sb_weight_R"):
                self.sb_weight_R.setValue(float(wr))

            self._persist_index_weight_settings()

    def _post_save_config(self, filename: str) -> None:

        if hasattr(self, "status_label"):
            self.status_label.setText(f" Saved: {Path(filename).name}")

        QMessageBox.information(self, "Saved", f"Configuration saved to {Path(filename).name}")

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

