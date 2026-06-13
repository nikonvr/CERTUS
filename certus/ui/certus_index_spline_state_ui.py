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

class SmartInitPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    cfg: Any
    sigma_knots: np.ndarray
    preview_grids: dict[str, Any]
    n_nodes_physical: np.ndarray
    L_nodes: np.ndarray
    d_best_nm: float
    t_exp: np.ndarray
    t_theo: np.ndarray
    t_is_ratio: bool
    lam_nm: np.ndarray | None

    @classmethod
    def from_dict(cls: type["SmartInitPayload"], d: dict[str, Any]) -> "SmartInitPayload":
        clean_d = {}
        clean_d["cfg"] = d.get("cfg")
        clean_d["sigma_knots"] = np.asarray(d.get("sigma_knots", []), dtype=np.float64).ravel()
        clean_d["preview_grids"] = d.get("preview_grids", {})
        clean_d["n_nodes_physical"] = np.asarray(d.get("n_nodes_physical", []), dtype=np.float64).ravel().copy()
        clean_d["L_nodes"] = np.asarray(d.get("L_nodes", []), dtype=np.float64).ravel().copy()
        clean_d["d_best_nm"] = float(d.get("d_best_nm", 0.0))
        clean_d["t_exp"] = np.asarray(d.get("t_exp", []), dtype=np.float64)
        clean_d["t_theo"] = np.asarray(d.get("t_theo", []), dtype=np.float64)
        clean_d["t_is_ratio"] = bool(d.get("t_is_ratio", False))
        clean_d["lam_nm"] = (
            np.asarray(d.get("lam_nm"), dtype=np.float64).ravel() if d.get("lam_nm") is not None else None
        )

        return cls(**clean_d)

@dataclass
class SplineState:
    result: dict | None

    d_lo: float

    d_hi: float

    wt: float

    wr: float

@dataclasses.dataclass
class _SmartInitState:
    """State object to hold mutable UI references and mathematical parameters of the Smart Init dialog."""

    sk: np.ndarray
    n_phys: np.ndarray
    L_nodes: np.ndarray
    preview_d_nm: float
    best_rmse: float
    best_n: np.ndarray
    best_L: np.ndarray
    current_rmse: float
    current_t_th: np.ndarray
    k_n: int = 0
    best_live: dict | None = dataclasses.field(default=None, repr=False)

    def __post_init__(self):
        if self.k_n == 0:
            self.k_n = int(np.asarray(self.sk).size)

    def update(
        self,
        sk: np.ndarray,
        n_phys: np.ndarray,
        L_nodes: np.ndarray,
        preview_d_nm: float,
        best_rmse: float,
        best_n: np.ndarray,
        best_L: np.ndarray,
        current_rmse: float,
        current_t_th: np.ndarray,
    ) -> None:
        self.sk = sk
        self.n_phys = n_phys
        self.L_nodes = L_nodes
        self.preview_d_nm = preview_d_nm
        self.best_rmse = best_rmse
        self.best_n = best_n
        self.best_L = best_L
        self.current_rmse = current_rmse
        self.current_t_th = current_t_th

@dataclass
class SmartInitState:
    sk: np.ndarray
    k_n: int
    n_phys: np.ndarray
    L_nodes: np.ndarray
    preview_d_nm: float
    best_rmse: float
    best_n: np.ndarray
    best_L: np.ndarray
    current_rmse: float
    current_t_th: Any
    best_live: Any

