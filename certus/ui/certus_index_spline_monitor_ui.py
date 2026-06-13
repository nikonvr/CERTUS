from __future__ import annotations
import json
import logging
import multiprocessing
import os
from pathlib import Path
import sys
import time
from dataclasses import dataclass, replace, field
from enum import auto
from threading import Event
from typing import Any, Callable, Mapping
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import (
    QAbstractAnimation,
    QSettings,
    QThread,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    SELLMEIER_COEFFS_BY_ID,
    __version__,
    create_module_environment,
    setup_module_logging,
)
from certus.utils.certus_data import build_export_context, build_report_sections, export_optimization_report, read_data_file_robust
from certus_physics import (
    get_n_substrate_array_by_id,
)
from certus.utils.certus_index_utils import (
    _lam_uniform_grid,
    _sorted_finite_sigma_knots as _sorted_finite_sigma_knots_impl,
    log_structured_json_event,
    _get_substrate_n_array_spline,
    _spectral_display_align,
    _d_from_slider_int,
    _slider_int_from_d_nm,
    _get_xv_spectral_coord,
    _stretch_sig_to_px,
    _compute_study_lambda_window_nm,
    _rmse_d_lower_envelope_mask,
    _filter_rmse_peaks_iteratively,
    _safe_int_from_mapping,
)
from certus.ui.certus_ui import (
    CertusBaseApp,
    EnhancedProgressWidget,
    CertusLogPanel,
    CertusScientificPlot,
    CertusTheme,
    CertusThemeToggle,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    ExcelTableWidget,
    FlashyCard,
    GenericWorker,
    apply_certus_theme,
    attach_excel_clipboard_context_menu,
    create_header_logo_widget,
    create_styled_button,
    get_certus_last_dir,
    init_certus_app,
    open_documentation,
    plot_widget_plot_finite,
    sanitize_xy_for_plot,
    set_certus_last_dir,
    setup_pyqtgraph_defaults,
    wrap_scientific_plot_with_toolbar,
    CertusCard,
    CertusStepper,
    CertusCollapsible,
    CertusStatusPill,
    safe_ui_action,
)
from pydantic import BaseModel, ConfigDict
from certus.core.certus_design_tokens import slider_corridor_half_stylesheet
from certus.utils.certus_skeleton import install_skeleton, uninstall_skeleton
from certus.ui.certus_plot import CertusScientificPlot
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_utils import apply_certus_theme
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.utils.certus_reset_framework import create_reset_button
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.ui.certus_smart_init_curve_editor import SmartInitNKCurveEditorDialog
from certus.spline.certus_index_spline_core import (
    SPLINE_PWL_K_NODES,
    SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS,
    SPLINE_PERF_PRESETS,
    DataType,
    SplineOptConfig,
    default_n_mono_band_nm_from_spectrum,
    gui_perf_preset_only,
    _to_fraction_T,
    ensure_lam_nm_array,
    prepare_exp_TR_for_fit,
    normalize_spectrum_dataframe,
    substrate_id_from_name,
    allowed_substrate_names,
    reset_smart_init_preview_guard,
    rmse_at_spline_stage_x0_init,
    _canonical_knots_min_lambda_kw,
    canonical_spline_sigma_knots,
    bridge_sigma_knots_preserve_manual,
    log_rmse_mesh_bridge_diagnosis,
    _log_index_spline_best_config,
    log_index_spline_d_trace,
)
from certus.spline.spline_smart_init import (
    build_smart_manual_sigma_knots_from_preview_grid,
    interp_n_L_pwlnk_to_sigmas,
    pick_best_manual_material_preset,
    recalc_smart_init_spectral_preview,
    smart_init_sweep_node_thickness_rmse,
)
from certus.spline.spline_objective import (
    _spline_objective_lam_mask,
    objective_lam_mask_on_target_grid,
    spectral_mse_rmse_masked_from_nk,
)
from certus.spline.spline_pipeline import (
    _sync_theoretical_tr_from_nk_dict,
    enforce_local_optimization_policy,
    worker_spline_manual_sigma_insert,
    worker_spline_autoshift_delta_ns,
    worker_spline_auto_clean_knots,
    worker_spline_auto_add_one_knot,
    worker_run_corridor_profile_after_nl_choice,
    worker_spline_mwir_insert_node,
    worker_spline_optimization,
)
from certus.ui.certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog
from certus.spline.spline_workers import _run_single_spline_stage
from certus.spline.spline_profile_corridors import (
    _expand_corridor_envelope_with_reported_nk,
    enforce_min_k_corridor_half_width,
    _fit_local_quadratic_rmse_profile,
    compute_regular_grid_rmse_profile,
    quick_pwlnk_refit_result_dict,
)
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
from certus.spline.spline_presets import _project_nb2o5_preset_to_sigma_knots, project_manual_material_preset
from certus.spline.spline_visual_utils import (
    live_monitor_nk_clipboard_tsv_2nm as _live_monitor_nk_clipboard_tsv_2nm,
    snap_spline_visual_dict as _snap_spline_visual_dict,
)
from certus.spline.spline_workers import worker_auto_best_split_knot_refinement
from certus.spline.certus_index_spline_excel_export import (
    _RMSEPlotContext,
    _ExcelExportMixin,
)
from certus.spline.certus_index_spline_rendering import (
    _PlotMixin,
    _UIBuilderMixin,
)
from certus.spline.certus_index_spline_execution import (
    _CorridorExportMixin,
    _RunMixin,
)
from certus.spline.certus_index_spline_corridors import (
    _CorridorWorkerMixin,
    _DataMixin,
    _CorridorGenMixin,
)
from certus.spline.certus_index_spline_settings import (
    _SettingsMixin,
    _CorridorControlMixin,
)
import dataclasses

def _apply_fixed_log_k_axis(plot_w: Any | None) -> None:
    if plot_w is None:
        return
    try:
        plot_w.setLogMode(False, True)
        if hasattr(plot_w, "getPlotItem"):
            pi = plot_w.getPlotItem()
            if pi is not None and hasattr(pi, "ctrl") and pi.ctrl is not None:
                if hasattr(pi.ctrl, "logYCheck"):
                    pi.ctrl.logYCheck.setChecked(True)
    except Exception:
        pass

class LiveIndexMonitor(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        # Support mock parents safely
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)

        self.setWindowTitle("Monitoring Indices (Live)")
        self.resize(550, 700)

        l = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("X Axis Unit:"))

        self.cb = QComboBox()
        self.cb.addItems(["Lambda (nm)", "Sigma (nm⁻1)", "Sigma2 (nm⁻2)"])

        def on_unit_change() -> None:
            if hasattr(self, "_last_data"):
                self.update_indices(*self._last_data)

        self.cb.currentIndexChanged.connect(on_unit_change)
        h.addWidget(self.cb)

        self._btn_copy_nk_2nm = create_styled_button("Copy lambda, n, k (2 nm step)", "secondary", parent=self)
        self._btn_copy_nk_2nm.setToolTip(
            "Clipboard: lambda (integer nm), n, k sorted by increasing lambda, interpolated on a 2 nm grid (TSV)."
        )
        self._btn_copy_nk_2nm.clicked.connect(self._copy_nk_clipboard_2nm)
        h.addWidget(self._btn_copy_nk_2nm)

        h.addStretch()
        l.addLayout(h)

        self.lbl_d = QLabel("d =  nm")
        self.lbl_d.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        l.addWidget(self.lbl_d)

        self.p_n = CertusScientificPlot(title="Index n")
        self.p_k = CertusScientificPlot(title="Index k  Log Scale")

        _apply_fixed_log_k_axis(self.p_k)

        l.addWidget(self.p_n)
        l.addWidget(self.p_k)

        apply_certus_theme(self)

    def _copy_nk_clipboard_2nm(self) -> None:
        if not hasattr(self, "_last_data") or self._last_data is None:
            QMessageBox.information(
                self,
                "Clipboard",
                "No n, k data (wait for live update).",
            )
            return

        lam_arr, n_arr, k_arr, _ = self._last_data
        txt = _live_monitor_nk_clipboard_tsv_2nm(lam_arr, n_arr, k_arr)
        if not txt:
            QMessageBox.information(
                self,
                "Clipboard",
                "No valid points for export.",
            )
            return

        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText(txt)

        prev = self._btn_copy_nk_2nm.text()
        self._btn_copy_nk_2nm.setText("Copied!")
        QTimer.singleShot(
            1500,
            lambda t=prev: self._btn_copy_nk_2nm.setText(t),
        )

    def update_indices(
        self, lam_arr: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray, d_nm: float | None = None
    ) -> None:
        self._last_data = (lam_arr, n_arr, k_arr, d_nm)
        mode = self.cb.currentIndex()

        if mode == 0:
            x, lbl = lam_arr, "lambda (nm)"
        elif mode == 1:
            x, lbl = 1.0 / lam_arr, "sigma (nm⁻1)"
        else:
            x, lbl = (1.0 / lam_arr) ** 2, "sigma2 (nm⁻2)"

        if d_nm is not None and np.isfinite(float(d_nm)):
            self.lbl_d.setText(f"d = {float(d_nm):.1f} nm")

        self.p_n.setLabel("bottom", lbl)
        self.p_k.setLabel("bottom", lbl)

        if "n" not in self.p_n._curves:
            self.p_n.add_curve(x, n_arr, "n", color=CertusTheme.PRIMARY, width=2, animate=False)
        else:
            self.p_n.update_curve("n", x, n_arr, animate=False)

        if "k" not in self.p_k._curves:
            self.p_k.add_curve(x, k_arr, "k", color=CertusTheme.DANGER, width=2, animate=False)
        else:
            self.p_k.update_curve("k", x, k_arr, animate=False)

        study_fn = getattr(self, "_study_lam_window_fn", None)
        if not callable(study_fn):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        try:
            lo_s, hi_s = study_fn()
        except (TypeError, ValueError, RuntimeError):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        if not (hi_s > lo_s and np.isfinite(lo_s) and np.isfinite(hi_s)):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        pad_l = max((hi_s - lo_s) * 0.02, 1e-6)
        lam_f = np.asarray(lam_arr, dtype=np.float64).ravel()
        n_f = np.asarray(n_arr, dtype=np.float64).ravel()
        k_f = np.asarray(k_arr, dtype=np.float64).ravel()

        npt = min(lam_f.size, n_f.size, k_f.size)
        if npt <= 0:
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        lam_f, n_f, k_f = lam_f[:npt], n_f[:npt], k_f[:npt]
        mwin = np.isfinite(lam_f) & (lam_f >= lo_s) & (lam_f <= hi_s)
        if not np.any(mwin):
            mwin = np.isfinite(lam_f)

        if mode == 0:
            x_lo, x_hi = float(lo_s - pad_l), float(hi_s + pad_l)
        elif mode == 1:
            x_lo = 1.0 / float(hi_s + pad_l)
            x_hi = 1.0 / float(max(lo_s - pad_l, 1e-30))
        else:
            x_lo = (1.0 / float(hi_s + pad_l)) ** 2
            x_hi = (1.0 / float(max(lo_s - pad_l, 1e-30))) ** 2

        if x_hi < x_lo:
            x_lo, x_hi = x_hi, x_lo

        pad_x = max((x_hi - x_lo) * 0.02, 1e-24)
        x0, x1 = float(x_lo - pad_x), float(x_hi + pad_x)

        self.p_n.plotItem.setXRange(x0, x1, padding=0)
        self.p_k.plotItem.setXRange(x0, x1, padding=0)

        nn = n_f[mwin]
        nn = nn[np.isfinite(nn)]
        if nn.size > 0:
            n_lo, n_hi = float(np.min(nn)), float(np.max(nn))
            pr = max((n_hi - n_lo) * 0.07, 1e-6)
            self.p_n.plotItem.setYRange(n_lo - pr, n_hi + pr, padding=0)

        _apply_fixed_log_k_axis(self.p_k)

