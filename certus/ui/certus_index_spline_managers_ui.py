from __future__ import annotations
import json
import logging
log = logging.getLogger('CERTUS')
logger = log

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

from certus.spline.certus_index_spline_smart_init import SmartInitState
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
import pyqtgraph as pg

_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4

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

class Step4MeshOptimizerBuilder:
    def __init__(self, app: "CertusIndexSplineApp", parent_layout: "QVBoxLayout", style: str):
        self.app = app
        self.parent_layout = parent_layout
        self.style = style

    def build(self) -> None:
        app = self.app
        parent_layout = self.parent_layout
        style = self.style
        box4 = CertusCard("Advanced settings")

        box4.setStyleSheet(style)
        box4.body.setContentsMargins(6, 4, 6, 4)
        box4.body.setSpacing(4)

        box4.setToolTip("Advanced optimization budgets and uncertainty/corridor controls.")

        g4 = QGridLayout()
        g4.setContentsMargins(0, 0, 0, 0)
        g4.setHorizontalSpacing(6)
        g4.setVerticalSpacing(4)

        box4.body.addLayout(g4)

        r4 = 0

        # --- Local budget + uncertainty: full panel (hidden in simplified interface) ---

        app._w_full_adv = QWidget()

        v_adv = QVBoxLayout(app._w_full_adv)

        v_adv.setContentsMargins(0, 0, 0, 0)

        v_adv.setSpacing(4)

        lb_pg = QLabel("Local iterations hint (max):")

        lb_pg.setToolTip("Legacy control kept for compatibility; inactive in local-only INDEX-SPLINE mode.")

        app.sp_pg_iter = QSpinBox()

        app.sp_pg_iter.setRange(5, 120)

        app.sp_pg_iter.setValue(int(SPLINE_PERF_PRESETS.get("fast", {}).get("pglobal_max_iter", 35)))

        app.sp_pg_iter.setToolTip("Inactive in local-only mode; kept only for preset/config compatibility.")

        app.sp_pg_iter.setEnabled(False)

        row_pg = QHBoxLayout()

        row_pg.addWidget(lb_pg)

        row_pg.addWidget(app.sp_pg_iter, 1)

        v_adv.addLayout(row_pg)

        lb_pr = QLabel("Performance profile:")

        lb_pr.setToolTip(
            'Budget preset: polish budget and local searches. "Maximal" gives best quality at the expense of runtime.'
        )

        app.cb_profilee = QComboBox()

        for lab, key in [
            ("Fast", "fast"),
            ("Standard", "standard"),
            ("Quality", "quality"),
            ("Maximal", "max"),
        ]:
            app.cb_profilee.addItem(lab, key)

        app.cb_profilee.setCurrentIndex(0)

        app.cb_profilee.setToolTip(
            "When the profile changes, a recommended local budget may be applied automatically to the spin."
        )

        app.cb_profilee.currentIndexChanged.connect(app._on_profilee_changed)

        row_pf = QHBoxLayout()

        row_pf.addWidget(lb_pr)

        row_pf.addWidget(app.cb_profilee, 1)

        v_adv.addLayout(row_pf)

        lb_mesh_dlam = QLabel("Min. Deltalambda/lambda step (sigma mesh) :")

        lb_mesh_dlam.setToolTip(
            "Canonical mesh constraint: min(delta-lambda between nodes) / lambda >= this value, "
            "with lambda? = (lambda_min + lambda_max) / 2 from file. Number of segments is reduced if needed; "
            "IR extension (+2 knots) is omitted if it violates threshold.\n"
            "0 = disabled (nominal behavior without this constraint)."
        )

        app.sp_mesh_min_dlam = QDoubleSpinBox()

        app.sp_mesh_min_dlam.setRange(0.0, 0.5)

        app.sp_mesh_min_dlam.setDecimals(4)

        app.sp_mesh_min_dlam.setSingleStep(0.0025)

        app.sp_mesh_min_dlam.setValue(0.02)

        app.sp_mesh_min_dlam.setSpecialValueText("disabled")

        app.sp_mesh_min_dlam.setToolTip(lb_mesh_dlam.toolTip())

        row_mesh_dlam = QHBoxLayout()

        row_mesh_dlam.addWidget(lb_mesh_dlam)

        row_mesh_dlam.addWidget(app.sp_mesh_min_dlam, 1)

        v_adv.addLayout(row_mesh_dlam)

        lb_auto_clean_v2 = QLabel("Auto-clean V2 (neighbor pull):")
        lb_auto_clean_v2.setToolTip(
            "After removing an internal knot, optionally adjusts the two local neighboring knots\n"
            "(extremes never moved), then re-optimizes RMSE.\n\n"
            "V2 explores symmetric/asymmetric pulls and a small local 2D refinement."
        )
        app.chk_auto_clean_neighbor_pull = QCheckBox("Enable local neighbor pull")
        app.chk_auto_clean_neighbor_pull.setChecked(bool(getattr(app, "_auto_clean_neighbor_pull_enabled", True)))
        app.chk_auto_clean_neighbor_pull.setToolTip(lb_auto_clean_v2.toolTip())
        row_ac0 = QHBoxLayout()
        row_ac0.addWidget(lb_auto_clean_v2)
        row_ac0.addWidget(app.chk_auto_clean_neighbor_pull)
        row_ac0.addStretch(1)
        v_adv.addLayout(row_ac0)

        row_ac1 = QHBoxLayout()
        row_ac1.addWidget(QLabel("pull ratios"))
        app.sp_auto_clean_pull_r1 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r1.setDecimals(3)
        app.sp_auto_clean_pull_r1.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r1.setSingleStep(0.01)
        app.sp_auto_clean_pull_r1.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r1", 0.10)))
        app.sp_auto_clean_pull_r1.setToolTip("First inward pull ratio (recommended: 0.10).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r1)
        app.sp_auto_clean_pull_r2 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r2.setDecimals(3)
        app.sp_auto_clean_pull_r2.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r2.setSingleStep(0.01)
        app.sp_auto_clean_pull_r2.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r2", 0.20)))
        app.sp_auto_clean_pull_r2.setToolTip("Second inward pull ratio (recommended: 0.20).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r2)
        app.sp_auto_clean_pull_r3 = QDoubleSpinBox()
        app.sp_auto_clean_pull_r3.setDecimals(3)
        app.sp_auto_clean_pull_r3.setRange(0.01, 0.45)
        app.sp_auto_clean_pull_r3.setSingleStep(0.01)
        app.sp_auto_clean_pull_r3.setValue(float(getattr(app, "_auto_clean_neighbor_pull_r3", 0.30)))
        app.sp_auto_clean_pull_r3.setToolTip("Third inward pull ratio (recommended: 0.30).")
        row_ac1.addWidget(app.sp_auto_clean_pull_r3)
        row_ac1.addStretch(1)
        v_adv.addLayout(row_ac1)

        row_ac2 = QHBoxLayout()
        app.chk_auto_clean_neighbor_pull_local_refine = QCheckBox("Enable local 2D refine")
        app.chk_auto_clean_neighbor_pull_local_refine.setChecked(
            bool(getattr(app, "_auto_clean_neighbor_pull_local_refine_enabled", False))
        )
        app.chk_auto_clean_neighbor_pull_local_refine.setToolTip(
            "After selecting the best pull variant for one removed knot, run a tiny 2D local\n"
            "search on the two adjacent knots to further reduce RMSE."
        )
        row_ac2.addWidget(app.chk_auto_clean_neighbor_pull_local_refine)
        row_ac2.addWidget(QLabel("refine rel. step"))
        app.sp_auto_clean_neighbor_pull_local_refine_step = QDoubleSpinBox()
        app.sp_auto_clean_neighbor_pull_local_refine_step.setDecimals(3)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setRange(0.005, 0.20)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setSingleStep(0.005)
        app.sp_auto_clean_neighbor_pull_local_refine_step.setValue(
            float(getattr(app, "_auto_clean_neighbor_pull_local_refine_rel_step", 0.05))
        )
        app.sp_auto_clean_neighbor_pull_local_refine_step.setToolTip(
            "Relative step used by the local 2D refine around neighboring knots (recommended: 0.05)."
        )
        row_ac2.addWidget(app.sp_auto_clean_neighbor_pull_local_refine_step)
        row_ac2.addStretch(1)
        v_adv.addLayout(row_ac2)

        # --- Search depth (LOT E) ---
        row_ac3 = QHBoxLayout()
        row_ac3.addWidget(QLabel("Top-N candidates (auto-clean):"))
        app.sp_auto_clean_top_n = QSpinBox()
        app.sp_auto_clean_top_n.setRange(1, 12)
        app.sp_auto_clean_top_n.setValue(int(getattr(app, "_auto_clean_top_n_sensitivity", 4)))
        app.sp_auto_clean_top_n.setToolTip(
            "Number of removal candidates per step passed to the full polish "
            "(higher values = deeper but slower search). Recommended: 4."
        )
        row_ac3.addWidget(app.sp_auto_clean_top_n)

        row_ac3.addWidget(QLabel("Polish maxfun candidat:"))
        app.sp_auto_clean_cand_maxfun = QSpinBox()
        app.sp_auto_clean_cand_maxfun.setRange(120, 4000)
        app.sp_auto_clean_cand_maxfun.setSingleStep(100)
        app.sp_auto_clean_cand_maxfun.setValue(int(getattr(app, "_auto_clean_candidate_polish_maxfun", 700)))
        app.sp_auto_clean_cand_maxfun.setToolTip("L-BFGS-B budget per removal candidate (recommended: 700-1500).")
        row_ac3.addWidget(app.sp_auto_clean_cand_maxfun)

        row_ac3.addWidget(QLabel("Tolerance RMSE:"))
        app.sp_auto_clean_tol = QDoubleSpinBox()
        app.sp_auto_clean_tol.setDecimals(6)
        app.sp_auto_clean_tol.setRange(0.0, 1.0e-2)
        app.sp_auto_clean_tol.setSingleStep(1.0e-5)
        app.sp_auto_clean_tol.setValue(float(getattr(app, "_auto_clean_ui_tolerance", 5.0e-5)))
        app.sp_auto_clean_tol.setToolTip("Absolute RMSE regression tolerated per removal. 0 = strict mode.")
        row_ac3.addWidget(app.sp_auto_clean_tol)
        row_ac3.addStretch(1)
        v_adv.addLayout(row_ac3)

        lb_cor = QLabel("Corridors n/k (d profiling):")

        lb_cor.setToolTip(
            "Calculate a plausible thickness interval and n(lambda), k(lambda) corridors by fixing d, then re-optimizing\n"
            "the n and ln k nodes with the same penalties and masked RMSE as the fit.\n\n"
            "RMSE_ref+Delta mode (default): accepted RMSE <= best polished spectral RMSE + Delta; the nominal 'best' curve\n"
            "is a native member of the envelope (not a pseudo-confidence interval centered on a heuristic refit).\n"
            "Alpha mode: RMSE(d) <= alpha * RMSE_opt (heuristic).\n\n"
            "Enabled by default at the end of optimization; results appear in the 'Corridors n/k' tab."
        )

        app.chk_corridor_d = QCheckBox("Enable")

        app.chk_corridor_d.setChecked(True)

        app.chk_corridor_d.setToolTip(lb_cor.toolTip())

        row_cd = QHBoxLayout()

        row_cd.addWidget(lb_cor)

        row_cd.addWidget(app.chk_corridor_d)

        app.lbl_corridors_state_adv = QLabel()

        app.lbl_corridors_state_adv.setTextFormat(Qt.TextFormat.RichText)

        app.lbl_corridors_state_adv.setToolTip(
            "Read-only: same state as the 'Corridors' button under Run (Yes = computation at the end of optimization)."
        )

        row_cd.addWidget(app.lbl_corridors_state_adv)

        row_cd.addStretch(1)

        v_adv.addLayout(row_cd)

        row_cor = QHBoxLayout()

        app.cb_corr_mode = QComboBox()

        app.cb_corr_mode.addItem("Heuristic (alpha?RMSE_opt)", "alpha")

        app.cb_corr_mode.addItem("RMSE_ref + Delta (absolute)", "abs_delta")

        app.cb_corr_mode.addItem("RMSE_ref + Delta adaptive (local)", "abs_delta_adaptive")

        app.cb_corr_mode.addItem("Likelihood ratio (Delta^2) - constant sigma or residual", "lr")

        _iad = app.cb_corr_mode.findData("abs_delta_adaptive")

        app.cb_corr_mode.setCurrentIndex(int(_iad) if _iad >= 0 else 0)

        app.cb_corr_mode.setToolTip(
            "Alpha mode: RMSE(d) <= alpha * RMSE_opt (heuristic).\n"
            "RMSE_ref + Delta: RMSE(d) <= RMSE_ref + Delta (same spectral mask). With 'best RMSE' checked, RMSE_ref = "
            "spectral_rmse_best_value (best polish); otherwise base curves from the dict.\n"
            "RMSE_ref + Delta adaptive: Delta is estimated locally from the profiled RMSE(d) parabola and local roughness.\n"
            "LR: Delta^2 <= chi^2(1, conf); constant sigma or sigma_i(lambda) ~ |residual| when residual sigma is enabled."
        )

        row_cor.addWidget(QLabel("mode"))

        row_cor.addWidget(app.cb_corr_mode)

        app.cb_corr_mode.currentIndexChanged.connect(app._on_corr_mode_changed)

        app.sp_corr_alpha = QDoubleSpinBox()

        app.sp_corr_alpha.setDecimals(3)

        app.sp_corr_alpha.setRange(1.000, 2.000)

        app.sp_corr_alpha.setSingleStep(0.005)

        app.sp_corr_alpha.setValue(1.05)

        app.sp_corr_alpha.setToolTip("Alpha threshold: RMSE threshold = alpha * RMSE_opt (e.g. 1.05 = +5%).")

        app.lbl_corr_alpha = QLabel("alpha")

        row_cor.addWidget(app.lbl_corr_alpha)

        row_cor.addWidget(app.sp_corr_alpha)

        app.lbl_corr_rmse_delta = QLabel("Delta RMSE abs.")

        app.sp_corr_rmse_delta = QDoubleSpinBox()

        app.sp_corr_rmse_delta.setDecimals(5)

        app.sp_corr_rmse_delta.setRange(0.00005, 0.05)

        app.sp_corr_rmse_delta.setSingleStep(0.00005)

        app.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

        app.sp_corr_rmse_delta.setToolTip(
            "Absolute margin on masked spectral RMSE: a refit at fixed d is accepted if "
            "RMSE <= RMSE_ref + Delta (default 2.5e-4; adaptive Delta_eff floor 2.5e-5). "
            "With best polished RMSE, RMSE_ref is the one of the exported model."
        )

        row_cor.addWidget(app.lbl_corr_rmse_delta)

        row_cor.addWidget(app.sp_corr_rmse_delta)

        app.chk_corr_scientific_nominal = QCheckBox("best RMSE")

        app.chk_corr_scientific_nominal.setChecked(True)

        app.chk_corr_scientific_nominal.setToolTip(
            "Scientific corridor mode (only if mode = RMSE_ref + Delta): RMSE_ref = spectral_rmse_best_value; "
            "nominal curves and nodes are aligned on the best polished model; no envelope widening toward the "
            "main solver curve. Uncheck to use legacy abs_delta behavior on base curves only."
        )

        row_cor.addWidget(app.chk_corr_scientific_nominal)

        app.btn_corr_preset_auto_robust = create_styled_button("Auto robust", "secondary", parent=app)

        app.btn_corr_preset_auto_robust.setToolTip(
            "Recommended settings for the d corridor: adaptive RMSE_ref + Delta mode (local), "
            "expanded parabolic window, thickness interval symmetrized around the parabola peak, "
            "side probes, and a reinforced Delta floor. Default behavior after migration."
        )

        app.btn_corr_preset_auto_robust.clicked.connect(app._apply_corridor_preset_auto_robust)

        row_cor.addWidget(app.btn_corr_preset_auto_robust)

        app.sp_corr_conf = QDoubleSpinBox()

        app.sp_corr_conf.setDecimals(3)

        app.sp_corr_conf.setRange(0.50, 0.999)

        app.sp_corr_conf.setSingleStep(0.01)

        app.sp_corr_conf.setValue(0.95)

        app.sp_corr_conf.setToolTip("LR confidence level (df=1): e.g. 0.95 -> Delta^2 ~ 3.84.")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("conf"))

        row_cor.addWidget(app.sp_corr_conf)

        app.sp_corr_sigma = QDoubleSpinBox()

        app.sp_corr_sigma.setDecimals(6)

        app.sp_corr_sigma.setRange(0.0, 1.0)

        app.sp_corr_sigma.setSingleStep(0.001)

        app.sp_corr_sigma.setValue(0.0)

        app.sp_corr_sigma.setToolTip(
            "Constant sigma (T and R) in fraction units (not %). 0 = auto (sigma := RMSE_opt)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("sigma"))

        row_cor.addWidget(app.sp_corr_sigma)

        app.sp_corr_step = QDoubleSpinBox()

        app.sp_corr_step.setDecimals(2)

        app.sp_corr_step.setRange(0.1, 50.0)

        app.sp_corr_step.setSingleStep(0.5)

        app.sp_corr_step.setValue(1.0)

        app.sp_corr_step.setToolTip("d continuation step size (nm).")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("step (nm)"))

        row_cor.addWidget(app.sp_corr_step)

        app.sp_corr_span = QDoubleSpinBox()

        app.sp_corr_span.setDecimals(1)

        app.sp_corr_span.setRange(1.0, 2000.0)

        app.sp_corr_span.setSingleStep(1.0)

        app.sp_corr_span.setValue(15.0)

        app.sp_corr_span.setToolTip(
            "Maximum offset |d - d_opt| explored in each direction (+d and -d), in nm (not the sum). "
            "Default 15 nm ~ local neighborhood around the optimal thickness."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("span (nm)"))

        row_cor.addWidget(app.sp_corr_span)

        # Multi-start (V2.2): robustness to local minima during fixed-d refit.

        app.sp_corr_starts = QSpinBox()

        app.sp_corr_starts.setRange(1, 25)

        app.sp_corr_starts.setValue(1)

        app.sp_corr_starts.setToolTip(
            "Number of initializations (multi-start) per d value. 1 = continuation only (fast). "
            ">1 increases robustness (best solution kept), at the cost of computation time."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(QLabel("starts"))

        row_cor.addWidget(app.sp_corr_starts)

        app.sp_corr_jn = QDoubleSpinBox()

        app.sp_corr_jn.setDecimals(3)

        app.sp_corr_jn.setRange(0.0, 1.0)

        app.sp_corr_jn.setSingleStep(0.01)

        app.sp_corr_jn.setValue(0.02)

        app.sp_corr_jn.setToolTip("Gaussian jitter sigma on n (or ? if monotonicity active) for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_n"))

        row_cor.addWidget(app.sp_corr_jn)

        app.sp_corr_jL = QDoubleSpinBox()

        app.sp_corr_jL.setDecimals(3)

        app.sp_corr_jL.setRange(0.0, 5.0)

        app.sp_corr_jL.setSingleStep(0.05)

        app.sp_corr_jL.setValue(0.15)

        app.sp_corr_jL.setToolTip("Gaussian jitter sigma on L=ln k for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_L"))

        row_cor.addWidget(app.sp_corr_jL)

        app.sp_corr_seed = QSpinBox()

        app.sp_corr_seed.setRange(-(2**31), 2**31 - 1)

        app.sp_corr_seed.setValue(0)

        app.sp_corr_seed.setToolTip("RNG seed for multi-start reproducibility (jitter).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seed"))

        row_cor.addWidget(app.sp_corr_seed)

        # V2.3: ln(k) regularization sensitivity scan (d2(L)^2 weight).

        app.chk_corr_reg_sens = QCheckBox("scan reg")

        app.chk_corr_reg_sens.setChecked(False)

        app.chk_corr_reg_sens.setToolTip(
            "Runs a scan (log grid) of the ln(k) regularization weight and re-launches d profiling for each value.\n"
            "Goal: verify the robustness of the d interval and the n/k corridors to regularization choices."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(app.chk_corr_reg_sens)

        app.sp_corr_reg_pts = QSpinBox()

        app.sp_corr_reg_pts.setRange(2, 15)

        app.sp_corr_reg_pts.setValue(5)

        app.sp_corr_reg_pts.setToolTip("Number of points in the regularization scan log grid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("pts"))

        row_cor.addWidget(app.sp_corr_reg_pts)

        app.sp_corr_reg_dec = QSpinBox()

        app.sp_corr_reg_dec.setRange(0, 6)

        app.sp_corr_reg_dec.setValue(2)

        app.sp_corr_reg_dec.setToolTip("Number of decades on each side of the base weight (lnk_spline_reg_weight).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("dec"))

        row_cor.addWidget(app.sp_corr_reg_dec)

        # V2.4: parametric bootstrap for publication-level bands

        app.chk_corr_boot = QCheckBox("bootstrap")

        app.chk_corr_boot.setChecked(False)

        app.chk_corr_boot.setToolTip(
            "Parametric bootstrap: generates B T/R datasets by adding Gaussian noise (sigma_T, sigma_R),\n"
            "re-launches d profiling for each replication, then computes percentile bands on n(lambda), k(lambda)\n"
            "and a distribution of the d interval."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(app.chk_corr_boot)

        app.sp_corr_boot_n = QSpinBox()

        app.sp_corr_boot_n.setRange(5, 500)

        app.sp_corr_boot_n.setValue(40)

        app.sp_corr_boot_n.setToolTip("Number of bootstrap replications (B). Larger = more robust, but slower.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("B"))

        row_cor.addWidget(app.sp_corr_boot_n)

        app.sp_corr_boot_p = QDoubleSpinBox()

        app.sp_corr_boot_p.setDecimals(3)

        app.sp_corr_boot_p.setRange(0.50, 0.999)

        app.sp_corr_boot_p.setSingleStep(0.01)

        app.sp_corr_boot_p.setValue(0.95)

        app.sp_corr_boot_p.setToolTip("Central percentile (e.g. 0.95 => bounds 2.5% / 97.5%).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("p"))

        row_cor.addWidget(app.sp_corr_boot_p)

        app.sp_corr_boot_seed = QSpinBox()

        app.sp_corr_boot_seed.setRange(-(2**31), 2**31 - 1)

        app.sp_corr_boot_seed.setValue(0)

        app.sp_corr_boot_seed.setToolTip("Seed RNG bootstrap.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seedB"))

        row_cor.addWidget(app.sp_corr_boot_seed)

        app.cb_corr_boot_mode = QComboBox()

        app.cb_corr_boot_mode.addItem("parametric (T/R + N(0,sigma))", "parametric")

        app.cb_corr_boot_mode.addItem("residual (T_th + residuals*)", "residual")

        app.cb_corr_boot_mode.setCurrentIndex(0)

        app.cb_corr_boot_mode.setToolTip(
            "parametric: adds Gaussian noise to measurements.\n"
            "residual: non-parametric bootstrap on residuals (more realistic if noise is non-Gaussian / correlated)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(app.cb_corr_boot_mode)

        app.sp_corr_boot_block = QSpinBox()

        app.sp_corr_boot_block.setRange(1, 5000)

        app.sp_corr_boot_block.setValue(1)

        app.sp_corr_boot_block.setToolTip("Block length (in lambda points) for residual bootstrap. 1 = iid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("blk"))

        row_cor.addWidget(app.sp_corr_boot_block)

        app._on_corr_mode_changed()

        w_cor = QWidget()

        w_cor.setLayout(row_cor)

        v_adv.addWidget(w_cor)

        row_cor_prof = QHBoxLayout()

        app.sp_corr_prof_maxfun = QSpinBox()

        app.sp_corr_prof_maxfun.setRange(0, 200000)

        app.sp_corr_prof_maxfun.setSingleStep(500)

        app.sp_corr_prof_maxfun.setValue(2500)

        app.sp_corr_prof_maxfun.setToolTip(
            "L-BFGS-B budget (maxfun) for each refit of n, ln k nodes at fixed d during corridor profiling.\n"
            "0 = reuse the main run polish_maxfun (often 8000+, very slow per step).\n"
            "Typ. 1500-4000 for a local scan; increase if 'EXCEEDS LIMIT' messages or poor refits."
        )

        row_cor_prof.addWidget(QLabel("d profiling: maxfun / refit"))

        row_cor_prof.addWidget(app.sp_corr_prof_maxfun)

        row_cor_prof.addStretch(1)

        w_cor_prof = QWidget()

        w_cor_prof.setLayout(row_cor_prof)

        v_adv.addWidget(w_cor_prof)

        row_cor_v25 = QHBoxLayout()

        app.chk_corr_sigma_hetero = QCheckBox("sigma(lambda) residual (LR + param. boot.)")

        app.chk_corr_sigma_hetero.setChecked(False)

        app.chk_corr_sigma_hetero.setToolTip(
            "In LR mode: ?^2 with sigma_i = max(floor, scale?|y_exp-y_th|) on the objective grid.\n"
            "Parametric bootstrap: same sigma_i for Gaussian noise on T/R (objective points only)."
        )

        row_cor_v25.addWidget(app.chk_corr_sigma_hetero)

        app.sp_corr_hetero_scale = QDoubleSpinBox()

        app.sp_corr_hetero_scale.setDecimals(3)

        app.sp_corr_hetero_scale.setRange(0.0, 20.0)

        app.sp_corr_hetero_scale.setSingleStep(0.05)

        app.sp_corr_hetero_scale.setValue(1.0)

        app.sp_corr_hetero_scale.setToolTip("Scale factor on |residual| for sigma_i(lambda) (0 = floor only).")

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("scale sigma(lambda)"))

        row_cor_v25.addWidget(app.sp_corr_hetero_scale)

        app.chk_corr_boot_refit = QCheckBox("fast bootstrap refit (parametric)")

        app.chk_corr_boot_refit.setChecked(False)

        app.chk_corr_boot_refit.setToolTip(
            "After each bootstrap trial: a short L-BFGS-B on (d + nodes) using noisy T/R, "
            "same spectral objective as main run (n,L interp. in sigma = cubic spline), "
            "then profiling in d from this refit (often more consistent than freezing initial mesh)."
        )

        row_cor_v25.addSpacing(12)

        row_cor_v25.addWidget(app.chk_corr_boot_refit)

        app.sp_corr_boot_maxfun = QSpinBox()

        app.sp_corr_boot_maxfun.setRange(0, 200000)

        app.sp_corr_boot_maxfun.setValue(4000)

        app.sp_corr_boot_maxfun.setToolTip(
            "L-BFGS-B maxfun budget per bootstrap refit (0 = disabled even if box is checked)."
        )

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("maxfun"))

        row_cor_v25.addWidget(app.sp_corr_boot_maxfun)

        app.sp_corr_boot_workers = QSpinBox()

        app.sp_corr_boot_workers.setRange(1, 64)

        app.sp_corr_boot_workers.setValue(1)

        app.sp_corr_boot_workers.setToolTip(
            "Number of parallel processes for bootstrap replications (1 = sequential). "
            f"Typ. 2-{max(2, multiprocessing.cpu_count() or 4)} on this machine "
            f"({multiprocessing.cpu_count() or '?'} cores). "
            "Pickle or worker failure -> automatic fallback to sequential."
        )

        row_cor_v25.addSpacing(10)

        row_cor_v25.addWidget(QLabel("proc."))

        row_cor_v25.addWidget(app.sp_corr_boot_workers)

        row_cor_v25.addStretch(1)

        w_cor2 = QWidget()

        w_cor2.setLayout(row_cor_v25)

        v_adv.addWidget(w_cor2)

        page_full_adv = QWidget()

        app._box4_full_adv_layout = QVBoxLayout(page_full_adv)

        app._box4_full_adv_layout.setContentsMargins(0, 0, 0, 0)

        app._box4_full_adv_layout.addWidget(app._w_full_adv)

        page_epure = QWidget()

        lay_ep = QVBoxLayout(page_epure)

        lay_ep.setContentsMargins(0, 0, 0, 0)

        btn_open_adv = create_styled_button("Advanced settings...", "secondary")

        btn_open_adv.setToolTip("Optimization budgets and detailed uncertainty/corridor options.")

        btn_open_adv.clicked.connect(app._open_advanced_settings_dialog)

        lay_ep.addWidget(btn_open_adv)

        app._stack_box4_adv = QStackedWidget()

        app._stack_box4_adv.addWidget(page_epure)

        app._stack_box4_adv.addWidget(page_full_adv)

        def _sync_adv_stack_height(_index: int = -1) -> None:
            try:
                current = app._stack_box4_adv.currentWidget()
                if current is None:
                    return
                h = max(1, int(current.sizeHint().height()))
                app._stack_box4_adv.setMinimumHeight(h)
                app._stack_box4_adv.setMaximumHeight(h)
            except (RuntimeError, ValueError):
                app.logger.debug("advanced_settings_stack_height_sync_failed", exc_info=True)

        app._stack_box4_adv.currentChanged.connect(_sync_adv_stack_height)
        QTimer.singleShot(0, _sync_adv_stack_height)

        g4.addWidget(app._stack_box4_adv, r4, 0, 1, 2)

        r4 += 1

        g4.setColumnStretch(1, 1)

        parent_layout.addWidget(box4)

class SmartInitPreviewManager:
    def __init__(self, parent_worker, payload):
        self.parent_worker = parent_worker
        self.payload = payload
        self.cfg = payload.cfg

        self.sk = payload.sigma_knots

        self.grids = payload.preview_grids

        logger.info(
            "[INDEX_SPLINE.SMART_INIT] dialog enter | parent=%s | cfg_present=%s | grids_present=%s | payload_k=%d | payload_d=%.6f",
            type(self.parent_worker).__name__,
            bool(self.cfg is not None),
            bool(self.grids is not None),
            int(np.asarray(self.sk, dtype=np.float64).size),
            float(getattr(payload, "d_best_nm", float("nan"))),
        )

        if self.cfg is None or self.grids is None or self.sk.size < 2:
            logger.warning(
                "[INDEX_SPLINE.SMART_INIT] dialog early return | reason=%s | cfg_present=%s | grids_present=%s | payload_k=%d | payload_d=%.6f | grids_keys=%s",
                (
                    "missing_cfg"
                    if self.cfg is None
                    else ("missing_grids" if self.grids is None else "too_few_knots")
                ),
                bool(self.cfg is not None),
                bool(self.grids is not None),
                int(np.asarray(self.sk, dtype=np.float64).size),
                float(getattr(payload, "d_best_nm", float("nan"))),
                sorted(list(self.grids.keys())) if isinstance(self.grids, dict) else None,
            )

            QMessageBox.warning(
                self.parent_worker,
                "Smart Init",
                "Incomplete preview data (cfg / grids / knots). Aborting preview safely.",
            )

            raise ValueError("Incomplete preview data (cfg or grids or knots)")

        self.k_n = int(self.sk.size)

        self.n_phys = payload.n_nodes_physical.copy()

        self.L_nodes = payload.L_nodes.copy()

        logger.info(
            "[INDEX_SPLINE.SMART_INIT] payload vectors | len_n=%d | len_l=%d | k=%d | d_best=%.6f",
            int(np.asarray(self.n_phys, dtype=np.float64).size),
            int(np.asarray(self.L_nodes, dtype=np.float64).size),
            int(self.k_n),
            float(getattr(payload, "d_best_nm", float("nan"))),
        )

        if self.n_phys.size != self.k_n or self.L_nodes.size != self.k_n:
            logger.warning(
                "[INDEX_SPLINE.SMART_INIT] dialog early return | reason=inconsistent_vectors | len_n=%d len_l=%d k=%d | sk_head=%s | n_head=%s | L_head=%s",
                int(np.asarray(self.n_phys, dtype=np.float64).size),
                int(np.asarray(self.L_nodes, dtype=np.float64).size),
                int(self.k_n),
                np.asarray(self.sk[: min(5, self.k_n)], dtype=np.float64).tolist(),
                np.asarray(self.n_phys[: min(5, self.n_phys.size)], dtype=np.float64).tolist(),
                np.asarray(self.L_nodes[: min(5, self.L_nodes.size)], dtype=np.float64).tolist(),
            )

            QMessageBox.warning(self.parent_worker, "Smart Init", "n / L sizes are inconsistent with sigma knots.")

            raise ValueError("n / L sizes are inconsistent with sigma knots")

        self.rel_step = 0.005  # +/-0,5 % sur n et sur L = ln k

        self.L_lo_g = float(self.grids["L_lo"])

        self.L_hi_g = float(self.grids["L_hi"])

        # During this dialog: free physical n (non-monotone in sigma) if a mono band is active elsewhere;

        # ? monotone reprojection applies on Continue (worker).

        self._relax_si_mono = self.cfg.n_mono_band_nm is not None

        # Nb2O? preset (ref. 12 abscissas in data): on open, Swanepoel is replaced by Nb2O?

        # only if K=12 (legacy). For K=14 (IR extension), keep Swanepoel n/L; user can still

        # apply Nb2O? via ?Apply preset? (interpolation on current sigma grid).

        if self.sk.size == SPLINE_PWL_K_NODES:
            self.sk, self.n_phys, self.L_nodes, d_total = _project_nb2o5_preset_to_sigma_knots(self.sk)

            self.effective_d_best_nm = float(d_total)

            self.open_preset_name = "nb2o5"

        else:
            self.effective_d_best_nm = float(payload.d_best_nm)

            self.open_preset_name = "none"

        # Truncated RMSE lambda window: sigma mesh for +/- columns = uniform in sigma^2 on sig_f (objective), not full spectrum.

        if getattr(self.cfg, "rmse_fit_lambda_nm", None) is not None:
            sig_f_g = np.asarray(self.grids["sig_f"], dtype=np.float64).ravel()

            if int(sig_f_g.size) >= 2:
                self.sk_win = build_smart_manual_sigma_knots_from_preview_grid(sig_f_g, n_uniform_in_sigma2=11)

                self.n_phys, self.L_nodes = interp_n_L_pwlnk_to_sigmas(self.sk, self.n_phys, self.L_nodes, self.sk_win)

                self.sk = self.sk_win

                self.k_n = int(self.sk.size)

        self.parent_worker.smart_preview_sk_arr = np.asarray(self.sk, dtype=np.float64).ravel().copy()

        # (sigma, n, L) triplets aligned on the instance: avoids drift vs local n_phys / L_nodes

        # after recomputation (curves, +/-) if other code reads smart_preview_sk_arr alone.

        self.parent_worker.smart_preview_n_phys = np.asarray(self.n_phys, dtype=np.float64).ravel().copy()

        self.parent_worker.smart_preview_L_nodes = np.asarray(self.L_nodes, dtype=np.float64).ravel().copy()

        self.parent_worker._si_mesh_sk_snap = self.parent_worker.smart_preview_sk_arr.copy()

        self._d0 = self.effective_d_best_nm

        if self._d0 is None or not np.isfinite(float(self._d0)):
            self.preview_d_nm = float(0.5 * (float(self.cfg.d_lo) + float(self.cfg.d_hi)))

        else:
            self.preview_d_nm = float(self._d0)

        logger.info(
            "[INDEX_SPLINE.SMART_INIT] mesh prepared | sigma_knots=%d | rmse_fit_window_nm=%s | preset_applied_on_open=%s | preview_d=%.6f",
            int(np.asarray(self.parent_worker.smart_preview_sk_arr, dtype=np.float64).size),
            str(getattr(self.cfg, "rmse_fit_lambda_nm", None)),
            str(self.open_preset_name),
            float(self.preview_d_nm),
        )

        if str(self.open_preset_name) == "nb2o5":
            logger.info(
                "[INDEX_SPLINE.SMART_INIT] seed transformation | incoming_payload_d_best_nm=%.6f | nb2o5_preset_d_total_nm=%.6f | preset_replaces_incoming_d_for_dialog_preview",
                float(payload.d_best_nm),
                float(self.preview_d_nm),
            )
        else:
            logger.info(
                "[INDEX_SPLINE.SMART_INIT] initial seed | incoming_d_best_nm=%.6f | effective_preview_d_nm=%.6f | preset=%s",
                float(payload.d_best_nm),
                float(self.preview_d_nm),
                str(self.open_preset_name),
            )

        _, rm0 = rmse_at_spline_stage_x0_init(
            self.cfg,
            self.sk,
            self.n_phys,
            self.L_nodes,
            self.preview_d_nm,
            relax_n_mono=self._relax_si_mono,
        )

        best_rmse = float(rm0)

        best_n = self.n_phys.copy()

        best_L = self.L_nodes.copy()

        current_rmse = float(rm0)

        logger.info(
            "[INDEX_SPLINE.SMART_INIT] rmse_at_seed | dialog_d_nm=%.6f | initial_rmse=%.8f",
            float(self.preview_d_nm),
            float(current_rmse),
        )

        self.dlg = QDialog(self.parent_worker)

        logger.info("[INDEX_SPLINE.SMART_INIT] dialog created")

        self.dlg.setWindowTitle(f"Smart Init  PWL n and ln k ({self.k_n} sigma knots ? presets Nb2O? ? SiO2 ? Ta2O?)")

        self.dlg.setMinimumWidth(1180)
        self.dlg.setMinimumHeight(620)

        # Auxiliary window for n(lambda) and log k(lambda)
        self.aux_dlg, self.curve_n, self.curve_pk, self.main_vb, self.p_extra = self.parent_worker._build_smart_init_aux_dialog(self.dlg)

        logger.info("[INDEX_SPLINE.SMART_INIT] auxiliary window created")

        lay = QVBoxLayout(self.dlg)

        h_x_main = QHBoxLayout()

        h_x_main.addWidget(QLabel("X axis (spectrum):"))

        self.cb_x_main = QComboBox()

        self.cb_x_main.addItems(["Lambda (nm)", "Sigma (nm⁻¹)", "Sigma² (nm⁻²)"])

        h_x_main.addWidget(self.cb_x_main)

        h_x_main.addStretch()

        lay.addLayout(h_x_main)

        if self._relax_si_mono:
            lbl_mono_relax = QLabel(
                "<b>Manual tuning</b>: <i>n</i> may be <b>non-monotone</b> in sigma between knots here "
                "(sliders / editor). <b>After Continue</b>: optimization uses the "
                "<b>λ reparametrization</b> - <i>n</i> non-decreasing in sigma on the run’s lambda band "
                "(so in practice <i>n</i> <b>decreasing or quasi-flat</b> as lambda increases on these segments), "
                "plus a penalty (UV-VIS band) if <i>n</i> rises too much with lambda "
                "(small slack on this penalty is configurable)."
            )

            lbl_mono_relax.setWordWrap(True)

            lbl_mono_relax.setStyleSheet(f"color: {CertusTheme.WARNING}; font-size: 11px; padding: 2px 0;")

            lay.addWidget(lbl_mono_relax)

        self.d_lo_nm = float(self.cfg.d_lo)

        self.d_hi_nm = float(self.cfg.d_hi)

        from certus.ui.certus_index_spline_ui import _D_SLIDER_STEPS_DEFAULT
        _D_SLIDER_STEPS = _D_SLIDER_STEPS_DEFAULT

        # _d_from_slider_int / _slider_int_from_d_nm: extracted to module level
        # Capture local context via lambdas
        self._d_from_slider = lambda iv: _d_from_slider_int(iv, self.d_lo_nm, self.d_hi_nm, _D_SLIDER_STEPS)  # noqa: E731
        self._slider_from_d = lambda dv: _slider_int_from_d_nm(dv, self.d_lo_nm, self.d_hi_nm, _D_SLIDER_STEPS)  # noqa: E731

        row_d = QHBoxLayout()

        row_d.addWidget(QLabel("Thickness d:"))

        self.slider_d = QSlider(Qt.Orientation.Horizontal)

        self.slider_d.setRange(0, _D_SLIDER_STEPS)

        self.slider_d.setToolTip(
            "Slider between fit d min and d max. The +/- buttons on n and ln k do not change d; "
            "move this slider to try different thickness."
        )

        self.lbl_d_slider = QLabel()

        self.lbl_d_slider.setMinimumWidth(220)

        row_d.addWidget(self.slider_d, 1)

        row_d.addWidget(self.lbl_d_slider)

        lay.addLayout(row_d)

        btn_show_nk = QPushButton("Display profiles n, ln k (lambda)")

        btn_show_nk.setFixedWidth(200)

        btn_show_nk.clicked.connect(self.aux_dlg.show)

        lay.addWidget(btn_show_nk)

        lam_src_payload = payload.lam_nm
        if lam_src_payload is None and self.parent_worker.df is not None and "lambda" in self.parent_worker.df.columns:
            lam_src_payload = ensure_lam_nm_array(self.parent_worker.df["lambda"].to_numpy(dtype=np.float64))
            if self.parent_worker.logger:
                self.parent_worker.logger.warning(
                    "[INDEX_SPLINE.SMART_INIT] payload missing lam_nm; falling back to experimental lambda grid"
                )
        self.lam_m = np.asarray(lam_src_payload if lam_src_payload is not None else [], dtype=np.float64)
        if self.lam_m.size == 0:
            logger.warning(
                "[INDEX_SPLINE.SMART_INIT] lam_nm unavailable in payload and dataframe; spectrum plot will be empty | payload_has_lam=%s | df_has_lambda=%s",
                payload.lam_nm is not None,
                bool(self.parent_worker.df is not None and "lambda" in self.parent_worker.df.columns),
            )

        self.y_exp = payload.t_exp

        y_th0 = payload.t_theo

        y_lab = "T/T_sub" if payload.t_is_ratio else "T"

        self.pw, self.curve_exp, self.curve_theo, self.knot_markers = self.parent_worker._build_smart_init_main_plot(y_lab)

        # get_xv: extracted to module level
        self.get_xv = _get_xv_spectral_coord

        self.knot_lines = []


        logger.info(
            "[INDEX_SPLINE.SMART_INIT] initial knot refresh | k_n=%d | preview_d_nm=%.6f | has_cfg=%s",
            int(self.k_n),
            float(self.preview_d_nm),
            bool(self.cfg is not None),
        )
        self.redraw_knot_lines()

        self.cb_x_main.currentIndexChanged.connect(self.redraw_knot_lines)

        current_t_th = y_th0.copy()
        self.state = SmartInitState(
            sk=self.sk,
            k_n=self.k_n,
            n_phys=self.n_phys,
            L_nodes=self.L_nodes,
            preview_d_nm=self.preview_d_nm,
            best_rmse=best_rmse,
            best_n=best_n,
            best_L=best_L,
            current_rmse=current_rmse,
            current_t_th=current_t_th,
            best_live=None,
        )

        # _study_lambda_window_nm: extracted to module level
        self._study_lambda_window_nm = lambda: _compute_study_lambda_window_nm(self.lam_m, self.cfg)  # noqa: E731



        # --- NEW : LIVE INDEX MONITORING ---

        self.mon = getattr(self.parent_worker, "_live_nk_monitor", None)

        if self.mon is None or not hasattr(self.mon, "update_indices"):
            from certus.ui.certus_index_spline_ui import LiveIndexMonitor
            self.mon = LiveIndexMonitor(self.parent_worker)

            self.parent_worker._live_nk_monitor = self.mon

        self.mon._study_lam_window_fn = self._study_lambda_window_nm

        self.mon.show()

        # Position to the right of the preview dialog (if visible).

        try:
            self.mon.move(self.dlg.x() + self.dlg.width() + 10, self.dlg.y())

        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


        self.lbl_stats = QLabel()

        self.lbl_stats.setWordWrap(True)


        self.refresh_stats(self.state.preview_d_nm, rm0)

        # Columns aligned under the plot sigmas (Delta sigma spacing on the axis).

        self.sk_arr = np.asarray(self.state.sk, dtype=np.float64).ravel()

        sig2_arr = self.sk_arr**2







        sig_pts = (1.0 / np.maximum(self.lam_m, 1e-9)) ** 2 if self.lam_m.size > 0 else sig2_arr

        self.s2_lo_f = float(min(float(np.min(sig_pts)), float(np.min(sig2_arr))))

        s2_hi_f = float(max(float(np.max(sig_pts)), float(np.max(sig2_arr))))

        span_sig2 = max(s2_hi_f - self.s2_lo_f, 1e-30)


        self.cb_x_main.currentIndexChanged.connect(self.update_main_x_axes)

        self.cb_x_main.setCurrentIndex(2)

        self.lbl_lam_cols: list[QLabel] = []

        self.lbl_sig_cols: list[QLabel] = []

        self.lbl_n_cols: list[QLabel] = []

        self.lbl_L_cols: list[QLabel] = []

        knot_bar = QWidget()

        self.knot_h = QHBoxLayout(knot_bar)

        self.knot_h.setContentsMargins(2, 4, 2, 2)

        self.knot_h.setSpacing(0)

        # _stretch_sig: extracted to module level
        self._stretch_sig = lambda delta: _stretch_sig_to_px(delta, span_sig2)  # noqa: E731

        self.n_btn_pairs: list[tuple[QPushButton, QPushButton]] = []

        self.L_btn_pairs: list[tuple[QPushButton, QPushButton]] = []

        self.n_auto_btns: list[QPushButton] = []

        self.L_auto_btns: list[QPushButton] = []

        self.curve_editor_holder: list[SmartInitNKCurveEditorDialog] = []


        knot_bar.setMinimumHeight(140)








        logger.info(
            "[INDEX_SPLINE.SMART_INIT] creating nk editor | n_bounds=[%.4f, %.4f] | l_bounds=[%.4f, %.4f] | k_clip_lo=%.3e",
            float(N_MIN_LIMIT),
            float(N_MAX_LIMIT),
            float(self.L_lo_g),
            float(self.L_hi_g),
            float(getattr(self.cfg, "k_clip_lo", 1e-30) or 1e-30),
        )

        self._nk_curve_editor = SmartInitNKCurveEditorDialog(
            self.dlg,
            n_lo=float(N_MIN_LIMIT),
            n_hi=float(N_MAX_LIMIT),
            L_lo=float(self.L_lo_g),
            L_hi=float(self.L_hi_g),
            k_clip_lo=float(getattr(self.cfg, "k_clip_lo", 1e-30) or 1e-30),
            get_sk=lambda: np.asarray(getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr), dtype=np.float64).ravel(),
            get_n_phys=lambda: self.state.n_phys,
            get_L_nodes=lambda: self.state.L_nodes,
            set_n_at=self._set_n_knot_curve,
            set_L_at=self._set_L_knot_curve,
            request_recalc=self.do_recalc,
            study_lambda_window=self._study_lambda_window_nm,
        )

        self.curve_editor_holder.append(self._nk_curve_editor)

        logger.info("[INDEX_SPLINE.SMART_INIT] showing nk editor window")
        self._nk_curve_editor.show()
        logger.info("[INDEX_SPLINE.SMART_INIT] nk editor show() returned")
        logger.info(
            "[INDEX_SPLINE.SMART_INIT] dialog fully shown and waiting for user | dlg_visible=%s | nk_visible=%s | preview_d=%.6f",
            bool(self.dlg.isVisible()),
            bool(self._nk_curve_editor.isVisible()),
            float(self.preview_d_nm),
        )

        QTimer.singleShot(0, self._place_nk_editor)




        self.slider_d.valueChanged.connect(self.on_slider_d_changed)

        logger.info(
            "[INDEX_SPLINE.SMART_INIT] sync thickness slider | preview_d_nm=%.6f | d_lo=%.6f | d_hi=%.6f",
            float(self.preview_d_nm),
            float(self.d_lo_nm),
            float(self.d_hi_nm),
        )
        self.set_slider_from_preview_d()






        logger.info(
            "[INDEX_SPLINE.SMART_INIT] rebuild knot ui | k_n=%d | current_rmse=%.8f | best_rmse=%.8f",
            int(self.state.k_n),
            float(self.state.current_rmse),
            float(self.state.best_rmse),
        )
        self.rebuild_knot_ui(self.state.k_n)  # Initial call here; wire_hold_button is already defined

        attach_excel_clipboard_context_menu(self.pw)

        lay.addWidget(wrap_scientific_plot_with_toolbar(self.dlg, self.pw), stretch=1)

        lbl_nodes = QLabel(
            f"<b>Knot adjustment (increasing sigma)</b> - <b>n &amp; k Editor</b> window on the left: drag points "
            f"(<i>k</i> in log); here: <b>- / +</b> +/-{100 * self.rel_step:.1f} % on <i>n</i> and <i>L</i> (= ln <i>k</i>), "
            f"<b>without</b> automatic thickness recalculation (d slider above); "
            f"<b>hold down</b> to accelerate; <b>auto</b>: d + param sweep <=3 s."
        )

        lbl_nodes.setWordWrap(True)

        lbl_nodes.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(lbl_nodes)

        lay.addWidget(knot_bar)

        lay.addWidget(self.lbl_stats)

        row_hint = QHBoxLayout()

        self.lbl_row_hint = QLabel()


        self.update_hint_text()

        row_hint.addWidget(self.lbl_row_hint, stretch=1)

        btn_recall = QPushButton("Recall best")

        btn_recall.setToolTip("Restore n and ln k profiles with the lowest RMSE since dialog start.")

        btn_recall.clicked.connect(self.recall_best)

        self.btn_copy = QPushButton("Copy to clipboard")


        self.btn_copy.clicked.connect(self.on_copy)

        row_hint.addWidget(self.btn_copy)

        row_hint.addWidget(btn_recall)






        self.btn_save_cfg = QPushButton("Save As")
        self.btn_save_cfg.setToolTip("Save current Smart Init index configuration (sigma, n, ln k, d) to JSON.")
        self.btn_save_cfg.clicked.connect(self.on_save_index_config)

        self.btn_load_cfg = QPushButton("Load")
        self.btn_load_cfg.setToolTip("Load a Smart Init index configuration from JSON and apply it to the dialog.")
        self.btn_load_cfg.clicked.connect(self.on_load_index_config)

        row_hint.addWidget(self.btn_save_cfg)
        row_hint.addWidget(self.btn_load_cfg)



        self.cb_material_preset = QComboBox()

        self.cb_material_preset.setMinimumWidth(168)

        self.cb_material_preset.setToolTip(
            "Choose a material: Nb2O? (reference 12 sigma + d), SiO2 or Ta2O? (lambda tabulation), "
            "then 'Apply preset' - PWL interpolation on current sigma grid, d mini-optimization.\n"
            "When opening the dialog, the **three** presets are automatically tested; the best RMSE "
            "(same criteria as preview) is applied."
        )

        for _label, _pid in (
            ("Nb2O? (ref.)", "nb2o5"),
            ("SiO2", "sio2"),
            ("Ta2O?", "ta2o5"),
        ):
            self.cb_material_preset.addItem(_label, _pid)

        self.btn_apply_material = QPushButton("Apply preset")


        self.btn_apply_material.clicked.connect(self.on_apply_material_preset)

        row_hint.addWidget(self.cb_material_preset)

        row_hint.addWidget(self.btn_apply_material)


        lay.addLayout(row_hint)

        self.chk_si_deep = QCheckBox("Deep SOL2 after Smart Init (legacy option inactive in local-only mode)")

        self.chk_si_deep.setChecked(False)

        self.chk_si_deep.setToolTip(
            "Manual Smart Init is now always handed off to the worker in local L-BFGS-B mode. "
            "This legacy option is kept visible only for compatibility and has no effect."
        )

        self.chk_si_deep.setEnabled(False)

        lay.addWidget(self.chk_si_deep)

        self.chk_si_two_phase = QCheckBox("Two-phase deep SOL2 (legacy option inactive in local-only mode)")

        self.chk_si_two_phase.setChecked(False)

        self.chk_si_two_phase.setToolTip(
            "Legacy compatibility flag only; no second global phase exists anymore in local-only mode."
        )

        self.chk_si_two_phase.setEnabled(False)

        lay.addWidget(self.chk_si_two_phase)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Continue optimization")

        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Stop")

        self._on_keep_called = [False]


        # --- INITIALISATION IMMEDIATE ---

        # Build the dialog state without triggering hidden recalculation or preset sweeps.
        # The preview window must stay idle until the user explicitly validates with Continue.
        self.rebuild_knot_ui(self.state.k_n)

        lbl_wait_user = QLabel(
            "<b>Manual step:</b> adjust the <i>n</i> and <i>ln k</i> nodes if needed, then click <b>Continue optimization</b> "
            "to launch the worker."
        )
        lbl_wait_user.setWordWrap(True)
        lbl_wait_user.setStyleSheet(f"color: {CertusTheme.WARNING}; font-size: 11px; padding: 2px 0;")
        lay.addWidget(lbl_wait_user)

        bb.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.on_keep)

        bb.rejected.connect(self.dlg.reject)

        lay.addWidget(bb)

        logger.info("[INDEX_SPLINE.SMART_INIT] immediate init started")

        self._apply_manual_spectrum_plot_range()

        logger.info("[INDEX_SPLINE.SMART_INIT] manual plot range applied")

        logger.info("[INDEX_SPLINE.SMART_INIT] dialog initialized")

    def redraw_knot_lines(self) -> None:

        for line in self.knot_lines:
            try:
                self.pw.removeItem(line)

            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.knot_lines.clear()

        pen_k = pg.mkPen("#1a9f3c", width=1.8)

        mode = self.cb_x_main.currentText()

        sk_lines = np.asarray(getattr(self.parent_worker, "smart_preview_sk_arr", self.sk), dtype=np.float64).ravel()

        for sx in sk_lines:
            il = pg.InfiniteLine(_get_xv_spectral_coord(float(sx), mode), angle=90, pen=pen_k)

            self.pw.addItem(il)

            self.knot_lines.append(il)

    def _apply_manual_spectrum_plot_range(self) -> None:
        from certus.ui.certus_index_spline_ui import _smart_init_apply_plot_range
        _smart_init_apply_plot_range(
            self.pw, self._study_lambda_window_nm, self.cb_x_main.currentIndex(),
            getattr(self.parent_worker, "smart_preview_sk_arr", self.sk), self.lam_m, self.y_exp,
            self.state.current_t_th,
        )

    def refresh_nk_plots_aux(self, lam_nk: np.ndarray, n_lam: np.ndarray, k_lam: np.ndarray) -> None:
        from certus.ui.certus_index_spline_ui import _smart_init_refresh_nk_aux
        _smart_init_refresh_nk_aux(
            self.curve_n, self.curve_pk, self.main_vb, self.p_extra,
            self._study_lambda_window_nm, lam_nk, n_lam, k_lam,
        )

    def refresh_nk_plots_mon(self, lam_u, n_lam_u, k_lam_u) -> None:

        self.mon.update_indices(lam_u, n_lam_u, k_lam_u, self.state.preview_d_nm)

    def refresh_stats(self, dv: float, rm: float) -> None:

        self.state.current_rmse = float(rm)

        rmse_lbl = "RMSE"

        if self.cfg.data_type == DataType.BOTH and float(self.cfg.weight_t) > 0.0 and float(self.cfg.weight_r) > 0.0:
            rmse_lbl = "RMSE (sqrt(MSE) objective T+R, as in first optimization cost)"

        from certus.ui.certus_index_spline_ui import _format_smart_init_status_text
        self.lbl_stats.setText(_format_smart_init_status_text(self.state.k_n, dv, rmse_lbl, rm, self.state.best_rmse))

    def update_main_x_axes(self) -> None:

        mode = self.cb_x_main.currentIndex()

        x_L = self.lam_m

        x_s = 1.0 / np.maximum(self.lam_m, 1e-30)

        x_s2 = x_s**2

        cur_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)

        k_L = 1.0 / np.maximum(cur_sk, 1e-30)

        k_s = cur_sk

        k_s2 = cur_sk**2

        x_vals = [x_L, x_s, x_s2][mode]

        k_vals = [k_L, k_s, k_s2][mode]

        lbl = ["lambda (nm)", "sigma (nm?1)", "sigma2 = 1/lambda2 (nm?2)"][mode]

        self.pw.setLabel("bottom", lbl)

        o = np.argsort(x_vals)

        self.curve_exp.setData(x_vals[o], self.y_exp[o])

        self.curve_theo.setData(x_vals[o], self.state.current_t_th[o])

        from certus.ui.certus_index_spline_ui import _interp_t_at_lam_knots
        knot_t = _interp_t_at_lam_knots(self.lam_m, self.state.current_t_th, cur_sk)

        self.knot_markers.setData(k_vals, knot_t)

        for j, il in enumerate(self.knot_lines):
            if j < len(k_vals):
                il.setPos(k_vals[j])

        self._apply_manual_spectrum_plot_range()

    def rebuild_knot_ui(self, new_kn: int) -> None:

        self.state.k_n = new_kn

        # Emptying the current layout

        while self.knot_h.count():
            item = self.knot_h.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)
        sig2_sorted_loc = np.sort(current_sk**2)

        self.redraw_knot_lines()

        from certus.ui.certus_index_spline_ui import _build_smart_init_knot_columns
        _build_smart_init_knot_columns(
            self.state.k_n, self.knot_h, sig2_sorted_loc, self.s2_lo_f, self._stretch_sig,
            self.lbl_lam_cols, self.lbl_sig_cols, self.lbl_n_cols, self.lbl_L_cols,
            self.n_btn_pairs, self.L_btn_pairs, self.n_auto_btns, self.L_auto_btns,
        )

        # Rewire +/- / auto buttons for the current k_n sigma knots

        current_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)

        sig2_sorted_loc = np.sort(current_sk**2)

        sig_sort_idx_loc = np.argsort(current_sk)

        # Rewire events

        for j in range(self.state.k_n):
            oi = int(sig_sort_idx_loc[j])

            bm_n, bp_n = self.n_btn_pairs[j]

            bm_L, bp_L = self.L_btn_pairs[j]

            self.wire_hold_button(bm_n, oi, -1, is_ln_k=False)

            self.wire_hold_button(bp_n, oi, +1, is_ln_k=False)

            self.wire_hold_button(bm_L, oi, -1, is_ln_k=True)

            self.wire_hold_button(bp_L, oi, +1, is_ln_k=True)

            def _run_n_auto(*_args, row_index=oi) -> None:
                self.run_auto(row_index, False)

            self.n_auto_btns[j].clicked.connect(_run_n_auto)

            def _run_l_auto(*_args, row_index=oi) -> None:
                self.run_auto(row_index, True)

            self.L_auto_btns[j].clicked.connect(_run_l_auto)

        self.sync_knot_labels()

        for _ce in self.curve_editor_holder:
            try:
                _ce.refresh_plots()

            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def sync_knot_labels(self) -> None:

        cur_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)

        cur_sort_idx = np.argsort(cur_sk)

        cur_kn = int(cur_sk.size)

        for j in range(cur_kn):
            oi = int(cur_sort_idx[j])

            lam_v = 1.0 / max(float(cur_sk[oi]), 1e-30)

            self.lbl_lam_cols[j].setText(f"{lam_v:.1f} nm")

            self.lbl_sig_cols[j].setText(f"{float(cur_sk[oi]):.5f}")

            self.lbl_n_cols[j].setText(f"{float(self.state.n_phys[oi]):.4f}")

            self.lbl_L_cols[j].setText(f"{float(self.state.L_nodes[oi]):.4f}")

    def sync_d_slider_label(self) -> None:

        self.lbl_d_slider.setText(f"{self.state.preview_d_nm:.2f} nm   [d min={self.d_lo_nm:.1f}, d max={self.d_hi_nm:.1f}]")

    def set_slider_from_preview_d(self) -> None:

        self.slider_d.blockSignals(True)

        self.slider_d.setValue(self._slider_from_d(self.state.preview_d_nm))

        self.slider_d.blockSignals(False)

        self.sync_d_slider_label()

    def _set_n_knot_curve(self, i: int, v: float) -> None:

        nn = np.asarray(self.state.n_phys, dtype=np.float64).copy()

        nn[int(i)] = float(np.clip(v, N_MIN_LIMIT, N_MAX_LIMIT))

        self.state.n_phys = nn

    def _set_L_knot_curve(self, i: int, v: float) -> None:

        LL = np.asarray(self.state.L_nodes, dtype=np.float64).copy()

        LL[int(i)] = float(np.clip(v, self.L_lo_g, self.L_hi_g))

        self.state.L_nodes = LL

    def do_recalc(self) -> None:
        _cbs_recalc = {
            "update_main_x_axes": self.update_main_x_axes,
            "sync_knot_labels": self.sync_knot_labels,
            "refresh_stats": self.refresh_stats,
            "refresh_nk_plots_aux": self.refresh_nk_plots_aux,
            "refresh_nk_plots_mon": self.refresh_nk_plots_mon,
        }
        self.parent_worker._execute_smart_init_do_recalc(
            self.state, self.cfg, self.grids, self._relax_si_mono, self.sk_arr,
            self.curve_editor_holder, _cbs_recalc,
        )

    def _place_nk_editor(self) -> None:

        try:
            fr = self.dlg.frameGeometry()

            self._nk_curve_editor.move(
                max(24, fr.left() - self._nk_curve_editor.width() - 20),
                fr.top() + 32,
            )

        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def run_auto(self, row: int, is_ln_k: bool) -> None:
        self.state.sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)
        err = self.parent_worker._execute_smart_init_run_auto(self.cfg, row, is_ln_k, self.L_lo_g, self.L_hi_g, self._relax_si_mono, self.state)
        if err:
            QMessageBox.warning(self.dlg, "Smart Init  auto", f"run auto failed: {err}")
            return
        self.set_slider_from_preview_d()
        self.do_recalc()

    def on_slider_d_changed(self, _iv: int) -> None:

        self.state.preview_d_nm = self._d_from_slider(self.slider_d.value())

        self.sync_d_slider_label()

        self.do_recalc()

    def bump_n_scaled(self, row: int, direction: int, mult: float) -> None:

        step = self.rel_step * float(mult)

        f = 1.0 + float(direction) * step

        self.state.n_phys[row] = float(np.clip(self.state.n_phys[row] * f, N_MIN_LIMIT, N_MAX_LIMIT))

        self.do_recalc()

    def bump_L_scaled(self, row: int, direction: int, mult: float) -> None:

        step = self.rel_step * float(mult)

        f = 1.0 + float(direction) * step

        self.state.L_nodes[row] = float(np.clip(self.state.L_nodes[row] * f, self.L_lo_g, self.L_hi_g))

        self.do_recalc()

    def wire_hold_button(self, btn, row, direction, *, is_ln_k=False) -> None:
        from certus.ui.certus_index_spline_ui import _smart_init_wire_hold_button
        _smart_init_wire_hold_button(
            btn, row, direction, is_ln_k=is_ln_k,
            parent_dlg=self.dlg, bump_n_fn=self.bump_n_scaled, bump_L_fn=self.bump_L_scaled,
        )

    def recall_best(self) -> None:
        self.state.sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)
        err = self.parent_worker._execute_smart_init_recall_best(self.state)
        if err:
            QMessageBox.information(self.dlg, "Smart Init", err)
            return
        self.do_recalc()

    def update_hint_text(self) -> None:

        # Help text: same K as worker after Continue (avoids claiming ?12 knots? for a 5 ?m file).

        lam_h = np.asarray(self.cfg.lam_nm, dtype=np.float64).ravel()

        k_h = int(
            canonical_spline_sigma_knots(
                float(np.nanmin(lam_h)),
                float(np.nanmax(lam_h)),
                **_canonical_knots_min_lambda_kw(self.cfg),
            ).size
        )

        n_h = max(1, k_h - 1)

        self.lbl_row_hint.setText(
            f" Continue: fixed mesh {k_h} sigma knots, {n_h} segments between knots "
            "(canonical grid [lambda_min, lambda_max]); local refinement; knots and RMSE logged in CERTUS."
        )

    def on_copy(self) -> None:

        cur_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)

        lines = [f"RMSE: {self.state.current_rmse:.8f}", f"d: {self.state.preview_d_nm:.6f} nm", "Nodes (sigma, n, ln k):"]

        for idx in np.argsort(cur_sk):
            lines.append(f"  {cur_sk[idx]:.8e} | {self.state.n_phys[idx]:.6f} | {self.state.L_nodes[idx]:.6f}")

        QApplication.clipboard().setText("\n".join(lines))

        self.btn_copy.setText("Copied!")

        QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy to clipboard"))

    def _refresh_knot_lines_and_ui(self) -> None:
        for line in self.knot_lines:
            try:
                self.pw.removeItem(line)
            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        self.knot_lines.clear()

        pen_k = pg.mkPen("#1a9f3c", width=1.8)
        mode = self.cb_x_main.currentText()
        for sx in self.state.sk:
            il = pg.InfiniteLine(_get_xv_spectral_coord(float(sx), mode), angle=90, pen=pen_k)
            self.pw.addItem(il)
            self.knot_lines.append(il)

        self.rebuild_knot_ui(int(len(self.state.sk)))
        self.set_slider_from_preview_d()
        self.do_recalc()

    def _serialize_smart_init_index_config(self) -> dict[str, Any]:
        cur_sk = np.asarray(getattr(self.parent_worker, "smart_preview_sk_arr", self.state.sk), dtype=np.float64).ravel()
        cur_n = np.asarray(self.state.n_phys, dtype=np.float64).ravel()
        cur_L = np.asarray(self.state.L_nodes, dtype=np.float64).ravel()
        return {
            "schema": "certus.index_spline.smart_init.index_config.v1",
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "x_axis_mode": str(self.cb_x_main.currentText()),
            "d_nm": float(self.state.preview_d_nm),
            "sigma_knots": [float(v) for v in cur_sk.tolist()],
            "n_nodes_physical": [float(v) for v in cur_n.tolist()],
            "L_nodes": [float(v) for v in cur_L.tolist()],
        }

    def on_save_index_config(self) -> None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        default_path = str(Path.cwd() / f"smart_init_index_config_{ts}.json")
        path, _ = QFileDialog.getSaveFileName(
            self.dlg,
            "Save index config (Smart Init)",
            default_path,
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

        payload_cfg = self._serialize_smart_init_index_config()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload_cfg, f, indent=2)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(self.dlg, "Save index config", f"Save failed: {exc}")
            return

        self.btn_save_cfg.setText("Saved")
        QTimer.singleShot(1200, lambda: self.btn_save_cfg.setText("Save As"))

    def on_load_index_config(self) -> None:
        self.parent_worker._load_smart_init_index_config(
            self.state, self.dlg, self.L_lo_g, self.L_hi_g, self.d_lo_nm, self.d_hi_nm,
            self._refresh_knot_lines_and_ui, self.btn_load_cfg,
        )

    def apply_manual_preset_from_projector(self, projector, feedback_btn, idle_label) -> None:
        self.parent_worker._apply_smart_init_preset(
            self.state, self.cfg, projector, self._relax_si_mono,
            self._refresh_knot_lines_and_ui, feedback_btn, idle_label,
        )

    def on_apply_material_preset(self) -> None:

        pid = str(self.cb_material_preset.currentData() or "nb2o5")

        dh = float(self.state.preview_d_nm)

        def _run(ts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:

            return project_manual_material_preset(pid, ts, d_nm_hint=dh)

        self.apply_manual_preset_from_projector(_run, self.btn_apply_material, "Apply preset")


    def on_keep(self) -> None:
        logger.info(
            "Smart Init on_keep requested | already_called=%s | preview_d=%.6f | rmse=%.8f",
            bool(self._on_keep_called[0]),
            float(getattr(self.state, "preview_d_nm", float("nan"))),
            float(getattr(self.state, "current_rmse", float("nan"))),
        )
        if self._on_keep_called[0]:
            logger.debug("Smart Init on_keep: guard active, ignoring reentrant call")
            return
        self._on_keep_called[0] = True
        try:
            ui_ctx = {
                "chk_si_deep": self.chk_si_deep,
                "chk_si_two_phase": self.chk_si_two_phase,
                "relax_si_mono": self._relax_si_mono,
            }
            logger.info(
                "Smart Init on_keep: dispatching to worker | relax_mono=%s | deep=%s | two_phase=%s",
                bool(ui_ctx.get("relax_si_mono", False)),
                bool(ui_ctx.get("chk_si_deep", None)),
                bool(ui_ctx.get("chk_si_two_phase", None)),
            )
            self.parent_worker._on_smart_init_keep(self.dlg, self.cfg, self.state, ui_ctx)
        except NUMERICAL_FAULT_EXCEPTIONS :
            logger.exception("Smart Init on_keep: exception in _on_smart_init_keep")
            self._on_keep_called[0] = False

