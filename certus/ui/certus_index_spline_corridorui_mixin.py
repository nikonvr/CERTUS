from __future__ import annotations
# -*- coding: utf-8 -*-
"""
CERTUS INDEX SPLINE UI
Modularized User Interface for Spline Index characterization app.
Contains CertusIndexSplineApp, LiveIndexMonitor, and companions.
"""
#!/usr/bin/env python3


"""

CERTUS-INDEX-SPLINE  Global fit of n(lambda), k(lambda) as piecewise-linear in sigma=1/lambda (ln k at nodes).

Standalone: no imports from CERTUS_INDEX nor certus_swanepool. Local optimization only.

P1 boundary: preserve the stronger local structure of this module. Keep settings,
persistence, spline editing, workers, and numerical helpers separated; avoid
large moves without dedicated tests for smart init, validation, and resume flows.
# Keep this file locally cohesive; prefer tiny helper/test updates over broad refactors.

"""


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

from certus.ui.certus_index_spline_state_ui import SmartInitPayload, SplineState, _SmartInitState, SmartInitState
from certus.ui.certus_index_spline_mixins_ui import _ConfigBuilderMixin, _MeshOptimizationMixin, _SmartInitDialogMixin, _UIMixin
from certus.ui.certus_index_spline_managers_ui import Step4MeshOptimizerBuilder, SmartInitPreviewManager
from certus.ui.certus_index_spline_monitor_ui import LiveIndexMonitor


from certus.core.certus_design_tokens import slider_corridor_half_stylesheet
from certus.utils.certus_skeleton import install_skeleton, uninstall_skeleton
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService

from certus.utils.certus_reset_framework import create_reset_button

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ

from certus.ui.certus_smart_init_curve_editor import SmartInitNKCurveEditorDialog

# Bootstrap

_env = create_module_environment(__file__, "CERTUS_INDEX_SPLINE")

_SCRIPT_DIR = _env["script_dir"]

logger = logging.getLogger("CERTUS_INDEX_SPLINE")

_QS_SPLINE_ORG = "CERTUS"

_QS_SPLINE_APP = "INDEX_SPLINE"

_QS_LAST_SPECTRUM = "last_spectrum_path"

_QS_SPECTRUM_FIT_T = "spectrum_fit_t"

_QS_SPECTRUM_FIT_TREL = "spectrum_fit_trel"

_QS_SPECTRUM_FIT_R = "spectrum_fit_r"

_QS_SPECTRUM_WT = "spectrum_weight_t"

_QS_SPECTRUM_WR = "spectrum_weight_r"

_QS_NK_PROFILE_INTERP = "nk_profile_interp"

_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY = "spline_simple_auto_uncertainty"

_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV = "spline_uncertainty_defaults_rev"

_QS_SMART_INIT_DEEP = "smart_init_deep_pglobal_after_manual"

_QS_SMART_INIT_TWO_PHASE = "smart_init_deep_two_phase_enabled"

_QS_MAIN_SPLITTER_STATE = "main_splitter_state"

_QS_MAIN_SPLITTER_LAYOUT_REV = "main_splitter_layout_rev"

_QS_RIGHT_SPLITTER_STATE = "right_splitter_state"

_MAIN_SPLITTER_LAYOUT_REV: int = 4

# Increment to reapply corridor / bootstrap / SiO2 defaults once on existing workstations.

_UNCERTAINTY_DEFAULTS_REV: int = 12

# d corridor (abs / adaptive): defaults tightened ~4x vs legacy (1e-3 / 1e-4).

_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4

_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5

# Minimum half-width (linear k) applied to the Corridors n/k tab display (consistent envelope + tooltip).
_CORRIDOR_K_TAB_MIN_HALF_WIDTH: float = 1e-4

# INDEX-SPLINE defaults for thin SiO2 layers (~1.6-1.8 ?m) on sapphire, TSIO2-type spectra (UV-IR, T/Tsub).

# Aligned on a validated session (Fast profile, mesh K=14 if lambda_max > 4000 nm, RMSE window 250-5000 nm).

SIO2_DEFAULT_D_LO_NM: float = 1600.0

SIO2_DEFAULT_D_HI_NM: float = 1800.0

SIO2_DEFAULT_NK_PROFILE_INTERP: str = "smooth"

SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM: float = 250.0

SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM: float = 5000.0

SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED: bool = True

# Auto-Best uses manual mode with a uniform sigma mesh and 12 anchor nodes

# (N_seg=11 -> K=12), quality preset, without adaptive/auto-K stages.

AUTO_BEST_MANUAL_N_SEG: int = 11  # K = N_seg + 1 = 12 wavelengths via sigma=1/lambda

# Adaptive mesh worker defaults (outside Auto-Best), aligned with core behavior.

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



def _plot_spectrum_raw_scatter(
    plot_w: pg.PlotWidget,
    x: np.ndarray,
    y: np.ndarray,
    *,
    color: str,
    name: str,
    symbol_size: int = 5,
) -> None:
    """Raw spectral data: always in points (no line), CERTUS convention."""

    xf, yf = sanitize_xy_for_plot(x, y)

    if xf.size == 0:
        return

    plot_w.plot(
        xf,
        yf,
        pen=None,
        symbol="o",
        symbolSize=int(symbol_size),
        symbolBrush=pg.mkBrush(color),
        symbolPen=pg.mkPen(color, width=0.6),
        name=name,
    )

_K_PLOT_YMIN: float = 1e-6
_K_PLOT_YMAX: float = 1e-2

def _apply_fixed_log_k_axis(plot_w: Any | None) -> None:
    """Force the CERTUS k-plot convention on every k graph."""
    if plot_w is None:
        return
    try:
        # 1. Force the internal Log mode first
        plot_w.setLogMode(False, True)

        # 2. Sync the control menu (pyqtgraph 'A' button)
        # to prevent _apply_sensible_empty_range from breaking things
        try:
            plot_w.plotItem.ctrl.logYCheck.setChecked(True)
        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # 3. Set the Y range using log10 exponents
        # This is the most stable method when Log mode is active
        ymin_log = np.log10(_K_PLOT_YMIN)
        ymax_log = np.log10(_K_PLOT_YMAX)
        plot_w.setYRange(ymin_log, ymax_log, padding=0)

    except (AttributeError, RuntimeError, TypeError):
        logger.debug("_apply_fixed_log_k_axis failed", exc_info=True)

def _add_spectrum_thickness_badge(
    plot_w: Any | None, x_vals: np.ndarray, y_vals: np.ndarray, d_nm: float
) -> Any | None:
    """Add a visible thickness badge inside the spectral response plot."""
    if plot_w is None or not np.isfinite(float(d_nm)):
        return None

    x_arr = np.asarray(x_vals, dtype=np.float64).ravel()
    y_arr = np.asarray(y_vals, dtype=np.float64).ravel()
    m = np.isfinite(x_arr) & np.isfinite(y_arr)
    if not np.any(m):
        return None

    x_arr = x_arr[m]
    y_arr = y_arr[m]
    x_lo = float(np.min(x_arr))
    x_hi = float(np.max(x_arr))
    y_lo = float(np.min(y_arr))
    y_hi = float(np.max(y_arr))
    dx = float(max(x_hi - x_lo, 1e-9))
    dy = float(max(y_hi - y_lo, 1e-9))

    badge = pg.TextItem(
        html=(
            '<div style="background-color: rgba(15, 23, 42, 180); '
            'padding: 4px 8px; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px;">'
            f'<span style="color: {CertusTheme.PRIMARY}; font-size: 12px;"><b>d = {float(d_nm):.2f} nm</b></span>'
            "</div>"
        ),
        anchor=(0.0, 1.0),
    )
    try:
        badge.setZValue(1000)
    except (AttributeError, RuntimeError):
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
    badge.setPos(x_lo + 0.03 * dx, y_hi - 0.04 * dy)
    try:
        plot_w.addItem(badge, ignoreBounds=True)
    except TypeError:
        plot_w.addItem(badge)
    return badge



def _smart_init_pw_nk_clipboard_df(curve_n: Any, curve_pk: Any) -> pd.DataFrame | None:
    """Build a DataFrame for Excel export from n(lambda) and ln k(lambda) plot items (k = exp(ln k), capped)."""

    xn, yn = curve_n.getData()

    xk, yk_ln = curve_pk.getData()

    xn = np.asarray(xn if xn is not None else [], dtype=float).ravel()

    yn = np.asarray(yn if yn is not None else [], dtype=float).ravel()

    xk = np.asarray(xk if xk is not None else [], dtype=float).ravel()

    yk_ln = np.asarray(yk_ln if yk_ln is not None else [], dtype=float).ravel()

    yk_k = np.full(yk_ln.shape, np.nan, dtype=float)

    m_ln = np.isfinite(yk_ln)

    yk_k[m_ln] = np.exp(np.minimum(yk_ln[m_ln], 700.0))

    n = int(max(xn.size, yn.size, xk.size, yk_k.size))

    if n == 0:
        return None

    def _pad(a: np.ndarray) -> np.ndarray:

        a = np.asarray(a, dtype=float).ravel()

        if a.size >= n:
            return a[:n].copy()

        return np.pad(a, (0, n - a.size), constant_values=np.nan)

    if xn.size == xk.size and xn.size > 0 and np.allclose(xn, xk, equal_nan=True):
        return pd.DataFrame({"lambda_nm": _pad(xn), "n": _pad(yn), "k": _pad(yk_k)})

    return pd.DataFrame(
        {
            "lambda_nm_n": _pad(xn),
            "n": _pad(yn),
            "lambda_nm_k": _pad(xk),
            "k": _pad(yk_k),
        }
    )

# --- GUI --------------------------------------------------------------------------


# LiveIndexMonitor is defined locally in this module

def _interp_t_at_lam_knots(lam_grid: np.ndarray, t_grid: np.ndarray, cur_sk: np.ndarray) -> np.ndarray:
    """Interpolate theoretical T at knot lambda positions (sigma -> lambda conversion)."""
    return _interp_series_at_sigma_knots(lam_grid, t_grid, cur_sk)[1]

def _interp_series_at_sigma_knots(
    lam_grid: np.ndarray, y_grid: np.ndarray, sigma_knots: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate a spectral series at sigma-knot wavelengths and return points sorted by lambda."""
    lam_g = np.asarray(lam_grid, dtype=np.float64).ravel()
    y_g = np.asarray(y_grid, dtype=np.float64).ravel()
    sig_k = np.asarray(sigma_knots, dtype=np.float64).ravel()

    m = np.isfinite(lam_g) & np.isfinite(y_g)
    if not np.any(m):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_f = lam_g[m]
    y_f = y_g[m]
    order_grid = np.argsort(lam_f, kind="mergesort")
    lam_f = lam_f[order_grid]
    y_f = y_f[order_grid]

    lam_k = 1.0 / np.maximum(sig_k, 1e-30)
    mk = np.isfinite(lam_k)
    if not np.any(mk):
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    lam_k = lam_k[mk]
    y_k = np.interp(lam_k, lam_f, y_f, left=y_f[0], right=y_f[-1])
    order_k = np.argsort(lam_k, kind="mergesort")
    return lam_k[order_k], y_k[order_k]

_D_SLIDER_STEPS_DEFAULT = 5000

def _worker_corridor_rmse_regular_grid(
    cfg: SplineOptConfig,
    base_snapshot: dict,
    d_grid_nm: np.ndarray,
    stop_event: Event,
    breakpoint_lookback_points: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Worker: refit n,L at fixed d on a grid (same masked spectral objective as the corridor)."""

    progress_cb = kwargs.get("progress_cb")

    live_cb = kwargs.get("live_cb")

    def _stop() -> bool:

        try:
            return stop_event is not None and stop_event.is_set()

        except (AttributeError, TypeError):
            return False

    visit_anchor = kwargs.get("visit_anchor_nm")

    visit_anchor_kw: float | None = None

    if visit_anchor is not None and np.isfinite(float(visit_anchor)):
        visit_anchor_kw = float(visit_anchor)

    return compute_regular_grid_rmse_profile(
        cfg,
        base_snapshot,
        d_grid_nm,
        profile_polish_maxfun=None,
        breakpoint_lookback_points=int(max(2, breakpoint_lookback_points)),
        visit_anchor_nm=visit_anchor_kw,
        progress_cb=progress_cb,
        stop_check=_stop,
        live_cb=live_cb,
    )

def _worker_corridor_rmse_healer(
    cfg: SplineOptConfig,
    tasks: list[tuple[float, dict]],
    stop_event: Event,
    **kwargs: Any,
) -> list[dict]:
    """Worker designed to heal gaps: each (d, seed) is optimized independently."""
    results = []
    progress_cb = kwargs.get("progress_cb")
    n = len(tasks)
    for i, (d_target, seed) in enumerate(tasks):
        if stop_event is not None and stop_event.is_set():
            break

        # Prepare a specific config/seed for this point
        point_seed = dict(seed)
        point_seed["d_nm"] = float(d_target)

        # Standard polish at fixed d
        res = quick_pwlnk_refit_result_dict(cfg, point_seed, maxfun=1200)
        if isinstance(res, dict):
            res["profile_d_val_nm"] = float(d_target)
            results.append(res)

        if progress_cb:
            progress_cb(float(i + 1) / n, f"Heal {i + 1}/{n} @ d={d_target:.2f}")

    return results

def _worker_curve_minimum_deep_refit(
    cfg: SplineOptConfig,
    seed_dict: dict,
    stop_event: Event,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """After RMSE(d): L-BFGS-B polish on (d, nodes) from the discrete grid minimum (local thickness freedom)."""
    if stop_event is not None and stop_event.is_set():
        return None
    maxfun = int(kwargs.get("deep_maxfun", 10000))
    seed_clean = {k: v for k, v in dict(seed_dict).items() if not str(k).startswith("profile_d")}
    out = quick_pwlnk_refit_result_dict(cfg, seed_clean, maxfun=maxfun)
    if not isinstance(out, dict):
        return None
    for _k in list(out.keys()):
        if str(_k).startswith("profile_d"):
            del out[_k]
    rm = float(out.get("rmse", float("nan")))
    if np.isfinite(rm):
        out["mse"] = float(rm * rm)
    out["gui_curve_minimum_deep_refit"] = True
    return out

def _format_smart_init_status_text(k_n: int, dv: float, rmse_lbl: str, rm: float, best_rmse: float) -> str:
    """Format the summary text for the smart init preview dialog."""
    return (
        f"Summary: dialog mesh K={k_n} sigma knots (worker uses canonical file K after 'Continue' if different). "
        f"Squares = theoretical T at knots. Continue -> local refinement on this mesh. "
        f"d {dv:.2f} nm | stage {rmse_lbl} start (x0 after clip, before L-BFGS-B) {rm:.6f} "
        f"| best reached {best_rmse:.6f}"
    )


import dataclasses










def _build_smart_init_knot_columns(
    k_n: int,
    knot_h,
    sig2_sorted: np.ndarray,
    s2_lo_f: float,
    stretch_fn: "Callable[[float], int]",
    lbl_lam_cols: list,
    lbl_sig_cols: list,
    lbl_n_cols: list,
    lbl_L_cols: list,
    n_btn_pairs: list,
    L_btn_pairs: list,
    n_auto_btns: list,
    L_auto_btns: list,
) -> None:
    """Build the per-knot widget columns for the Smart Init dialog.

    Clears and rebuilds the horizontal knot bar layout with columns for each
    sigma knot: lambda/sigma labels, n +/- buttons, ln k +/- buttons, auto btns.
    All list arguments are mutated in-place (cleared then appended to).
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

    # Clear widget lists
    lbl_lam_cols.clear()
    lbl_sig_cols.clear()
    lbl_n_cols.clear()
    lbl_L_cols.clear()
    n_btn_pairs.clear()
    L_btn_pairs.clear()
    n_auto_btns.clear()
    L_auto_btns.clear()

    knot_h.addStretch(stretch_fn(float(sig2_sorted[0] - s2_lo_f)))

    for j in range(k_n):
        col_w = QWidget()
        cv = QVBoxLayout(col_w)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(2)
        col_w.setFixedWidth(112)

        lam_l = QLabel()
        lam_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lam_l.setStyleSheet(f"font-size: 9px; color: {CertusTheme.TEXT_SUB};")

        sig_l = QLabel()
        sig_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sig_l.setStyleSheet(f"font-size: 9px; color: {CertusTheme.TEXT_SUB};")

        lbl_lam_cols.append(lam_l)
        lbl_sig_cols.append(sig_l)

        cap_n = QLabel("n")
        cap_n.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cap_n.setStyleSheet(f"font-size: 8px; color: {CertusTheme.TEXT_SUB};")

        row_n = QHBoxLayout()
        row_n.setSpacing(1)

        bm_n = QPushButton("\u2212")
        bm_n.setFixedWidth(22)
        val_n = QLabel()
        val_n.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_n.setMinimumWidth(36)
        val_n.setStyleSheet("font-size: 10px;")
        bp_n = QPushButton("+")
        bp_n.setFixedWidth(22)
        b_auto_n = QPushButton("auto")
        b_auto_n.setFixedWidth(34)
        b_auto_n.setStyleSheet("font-size: 7px; padding: 1px 2px;")

        lbl_n_cols.append(val_n)
        row_n.addWidget(bm_n)
        row_n.addWidget(val_n, 1)
        row_n.addWidget(bp_n)
        row_n.addWidget(b_auto_n)
        n_auto_btns.append(b_auto_n)

        cap_L = QLabel("ln k")
        cap_L.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cap_L.setStyleSheet(f"font-size: 8px; color: {CertusTheme.TEXT_SUB};")

        row_L = QHBoxLayout()
        row_L.setSpacing(1)

        bm_L = QPushButton("\u2212")
        bm_L.setFixedWidth(22)
        val_L = QLabel()
        val_L.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_L.setMinimumWidth(36)
        val_L.setStyleSheet("font-size: 10px;")
        bp_L = QPushButton("+")
        bp_L.setFixedWidth(22)
        b_auto_L = QPushButton("auto")
        b_auto_L.setFixedWidth(34)
        b_auto_L.setStyleSheet("font-size: 7px; padding: 1px 2px;")

        lbl_L_cols.append(val_L)
        row_L.addWidget(bm_L)
        row_L.addWidget(val_L, 1)
        row_L.addWidget(bp_L)
        row_L.addWidget(b_auto_L)
        L_auto_btns.append(b_auto_L)

        n_btn_pairs.append((bm_n, bp_n))
        L_btn_pairs.append((bm_L, bp_L))

        cv.addWidget(lam_l)
        cv.addWidget(sig_l)
        cv.addWidget(cap_n)
        cv.addLayout(row_n)
        cv.addWidget(cap_L)
        cv.addLayout(row_L)

        knot_h.addWidget(col_w, 0)

        if j + 1 < k_n:
            knot_h.addStretch(stretch_fn(float(sig2_sorted[j + 1] - sig2_sorted[j])))


def _smart_init_wire_hold_button(
    btn,
    row: int,
    direction: int,
    *,
    is_ln_k: bool,
    parent_dlg,
    bump_n_fn: "Callable[[int, int, float], None]",
    bump_L_fn: "Callable[[int, int, float], None]",
) -> None:
    """Wire a QPushButton as a hold-to-repeat +/- button for n or ln k adjustment."""
    from PyQt6.QtCore import QTimer

    t = QTimer(parent_dlg)
    t.setInterval(78)
    ntick: list[int] = [0]

    def on_tick() -> None:
        ntick[0] += 1
        mult = min(24.0, 1.0 + (ntick[0] - 1) * 0.85)
        if is_ln_k:
            bump_L_fn(row, direction, mult)
        else:
            bump_n_fn(row, direction, mult)

    t.timeout.connect(on_tick)

    def on_press() -> None:
        ntick[0] = 1
        if is_ln_k:
            bump_L_fn(row, direction, 1.0)
        else:
            bump_n_fn(row, direction, 1.0)
        t.stop()

        def maybe_start_repeat() -> None:
            if btn.isDown():
                t.start()

        QTimer.singleShot(400, maybe_start_repeat)

    def on_release() -> None:
        t.stop()
        ntick[0] = 0

    btn.pressed.connect(on_press)
    btn.released.connect(on_release)


def _smart_init_refresh_nk_aux(
    curve_n,
    curve_pk,
    main_vb,
    p_extra,
    lam_window_fn: "Callable[[], tuple[float, float]]",
    lam_nk: np.ndarray,
    n_lam: np.ndarray,
    k_lam: np.ndarray,
) -> None:
    """Update auxiliary n(λ) and ln k(λ) plots with auto-range on the study window."""
    curve_n.setData(lam_nk, n_lam)
    ln_k = np.log(np.maximum(k_lam, 1e-12))
    curve_pk.setData(lam_nk, ln_k)

    lo_s, hi_s = lam_window_fn()
    pad_l = max((hi_s - lo_s) * 0.02, 1e-6)

    lam_a = np.asarray(lam_nk, dtype=np.float64).ravel()
    n_a = np.asarray(n_lam, dtype=np.float64).ravel()
    ln_a = np.asarray(ln_k, dtype=np.float64).ravel()

    n_pts = min(lam_a.size, n_a.size, ln_a.size)
    if n_pts <= 0:
        return
    lam_a, n_a, ln_a = lam_a[:n_pts], n_a[:n_pts], ln_a[:n_pts]

    m = np.isfinite(lam_a) & (lam_a >= lo_s) & (lam_a <= hi_s)
    if not np.any(m):
        m = np.isfinite(lam_a)

    main_vb.setXRange(float(lo_s - pad_l), float(hi_s + pad_l), padding=0)

    nn = n_a[m]
    nn = nn[np.isfinite(nn)]
    if nn.size > 0:
        n_lo, n_hi = float(np.min(nn)), float(np.max(nn))
        pr = max((n_hi - n_lo) * 0.06, 1e-6)
        main_vb.setYRange(n_lo - pr, n_hi + pr, padding=0)

    lk = ln_a[m]
    lk = lk[np.isfinite(lk)]
    if lk.size > 0:
        lk_lo, lk_hi = float(np.min(lk)), float(np.max(lk))
        pr = max((lk_hi - lk_lo) * 0.08, 1e-6)
        p_extra.setYRange(lk_lo - pr, lk_hi + pr, padding=0)


def _smart_init_apply_plot_range(
    pw,
    lam_window_fn: "Callable[[], tuple[float, float]]",
    x_mode_index: int,
    sk_arr: np.ndarray,
    lam_m: np.ndarray,
    y_exp: np.ndarray,
    current_t_th: np.ndarray,
) -> None:
    """Auto-scale the spectral plot to the study region (lambda/sigma/sigma²)."""
    lo_s, hi_s = lam_window_fn()
    pad_l = max((hi_s - lo_s) * 0.02, 1e-6)

    if x_mode_index == 0:
        x_lo, x_hi = float(lo_s - pad_l), float(hi_s + pad_l)
    elif x_mode_index == 1:
        x_lo = 1.0 / float(hi_s + pad_l)
        x_hi = 1.0 / float(max(lo_s - pad_l, 1e-30))
    else:
        x_lo = (1.0 / float(hi_s + pad_l)) ** 2
        x_hi = (1.0 / float(max(lo_s - pad_l, 1e-30))) ** 2

    if x_hi < x_lo:
        x_lo, x_hi = x_hi, x_lo

    cur_sk = np.asarray(sk_arr, dtype=np.float64)
    k_vals = (
        1.0 / np.maximum(cur_sk, 1e-30),
        cur_sk,
        cur_sk ** 2,
    )[x_mode_index]
    kv = np.asarray(k_vals, dtype=np.float64).ravel()
    kv = kv[np.isfinite(kv)]
    if kv.size:
        x_lo = min(float(x_lo), float(np.min(kv)))
        x_hi = max(float(x_hi), float(np.max(kv)))

    if x_hi < x_lo:
        x_lo, x_hi = x_hi, x_lo

    pad_x = max((x_hi - x_lo) * 0.015, 1e-24)

    lam = np.asarray(lam_m, dtype=np.float64).ravel()
    ye = np.asarray(y_exp, dtype=np.float64).ravel()
    yt = np.asarray(current_t_th, dtype=np.float64).ravel()
    n = int(min(lam.size, ye.size, yt.size))
    if n <= 0:
        return
    lam, ye, yt = lam[:n], ye[:n], yt[:n]

    m = np.isfinite(lam) & (lam >= lo_s) & (lam <= hi_s)
    if not np.any(m):
        m = np.isfinite(lam)

    yy = np.concatenate([ye[m], yt[m]])
    yy = yy[np.isfinite(yy)]

    knot_t = _interp_t_at_lam_knots(lam_m, current_t_th, sk_arr)
    kt = np.asarray(knot_t, dtype=np.float64).ravel()
    kt = kt[np.isfinite(kt)]
    if kt.size:
        yy = np.concatenate([yy, kt]) if yy.size else kt

    if yy.size == 0:
        yy = np.array([0.0, 1.0], dtype=np.float64)

    y_lo, y_hi = float(np.min(yy)), float(np.max(yy))
    if y_hi <= y_lo:
        y_hi = y_lo + 1e-6
    pad_y = max((y_hi - y_lo) * 0.08, 1e-5)

    pw.setXRange(float(x_lo - pad_x), float(x_hi + pad_x), padding=0)
    pw.setYRange(float(y_lo - pad_y), float(y_hi + pad_y), padding=0)

















class CertusIndexSplineCorridorUIMixin:
    """CertusIndexSplineCorridorUIMixin."""

    def _schedule_corridor_auto_refine(
        self,
        seed: dict,
        *,
        rerun_corridor: bool,
        origin: str,
    ) -> bool:
        """Schedule a strict refinement chain after corridor improvement."""
        if not isinstance(seed, dict):
            return False
        self._corridor_auto_refine_plan = {
            "stage": "deep",
            "rerun_corridor": bool(rerun_corridor),
            "origin": str(origin or "corridor"),
        }
        if self.logger:
            self.logger.info(
                "AUTO-REFINE [%s] scheduled | chain=deep-polish -> [conditional-corridor-rerun] | rerun_corridor=%s",
                str(origin or "corridor"),
                "yes" if bool(rerun_corridor) else "no",
            )
        if self._start_curve_minimum_deep_refit(dict(seed)):
            return True
        self._corridor_auto_refine_plan = None
        return False

    def _continue_corridor_auto_refine_after_deep(self) -> bool:
        """Continue refinement chain when deep polish is done."""
        plan = self._corridor_auto_refine_plan
        if not isinstance(plan, dict) or str(plan.get("stage", "")) != "deep":
            return False
        seed_now = self._manual_postprocess_seed_result()
        if not isinstance(seed_now, dict):
            self._corridor_auto_refine_plan = None
            return False
        if bool(plan.get("rerun_corridor", False)):
            if self.logger:
                self.logger.info(
                    "AUTO-REFINE [%s] deep-polish done | rerunning corridor profiling.",
                    plan.get("origin", "corridor"),
                )
            self._corridor_auto_refine_plan = None
            return bool(self._start_deferred_corridor_worker(dict(seed_now)))
        self._corridor_auto_refine_plan = None
        return False

    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None:
        """Starts the gap healing worker after the grid, outside the ``finished`` handler (prevents ``_cleanup_thread``)."""
        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: a worker is already running.")
            return
        cfg = self._last_run_cfg
        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: no optimization config.")
            return
        self._stop_event = Event()
        self._worker = GenericWorker(
            _worker_corridor_rmse_healer,
            cfg,
            tasks,
            self._stop_event,
        )
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "rmse_heal"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_corridor_grid_busy(True)
        self._worker.start()

    @staticmethod
    def _interp_corridor_value(x: float, x_arr: np.ndarray, y_arr: np.ndarray) -> float:
        xa = np.asarray(x_arr, dtype=np.float64).ravel()
        ya = np.asarray(y_arr, dtype=np.float64).ravel()
        m = np.isfinite(xa) & np.isfinite(ya)
        if int(np.count_nonzero(m)) < 2:
            return float("nan")
        xs = xa[m]
        ys = ya[m]
        o = np.argsort(xs, kind="mergesort")
        xs = xs[o]
        ys = ys[o]
        return float(np.interp(float(x), xs, ys, left=np.nan, right=np.nan))

    def _k_corridor_crosshair_formatter(self, x: float, y_on_curve: float | None, y_mouse: float) -> str:
        lam = np.asarray(getattr(self, "_corridor_k_crosshair_lam", []), dtype=np.float64).ravel()
        k_nom = np.asarray(getattr(self, "_corridor_k_crosshair_nom", []), dtype=np.float64).ravel()
        k_min = np.asarray(getattr(self, "_corridor_k_crosshair_lo", []), dtype=np.float64).ravel()
        k_max = np.asarray(getattr(self, "_corridor_k_crosshair_hi", []), dtype=np.float64).ravel()
        kn = self._interp_corridor_value(x, lam, k_nom) if k_nom.size == lam.size else float("nan")
        k0 = self._interp_corridor_value(x, lam, k_min) if k_min.size == lam.size else float("nan")
        k1 = self._interp_corridor_value(x, lam, k_max) if k_max.size == lam.size else float("nan")
        if np.isfinite(k0) and np.isfinite(k1) and k1 < k0:
            k0, k1 = k1, k0
        kn_txt = f"{kn:.3e}" if np.isfinite(kn) and kn > 0.0 else "n/a"
        k0_txt = f"{k0:.3e}" if np.isfinite(k0) and k0 > 0.0 else "n/a"
        k1_txt = f"{k1:.3e}" if np.isfinite(k1) and k1 > 0.0 else "n/a"
        return f"lambda = {x:.2f} nm | k_min = {k0_txt} | k_nom = {kn_txt} | k_max = {k1_txt}"

    def _build_tab_corridor_rmse(self) -> QWidget:
        """Tab Corridor RMSE(d). Orchestrator."""
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)
        ctx_lay.setSpacing(6)
        self._build_corridor_labels(ctx_lay)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        rmse_section = CertusCard("1  Recalculate RMSE(d)")
        generate_section = CertusCard("2  Generate corridor n/k")
        self._build_corridor_tab_rmse_controls(rmse_section.body)
        self._build_corridor_tab_generate(generate_section.body)
        ctx_lay.addWidget(rmse_section)
        ctx_lay.addWidget(generate_section)

        self.plot_corridor_rmse_d = CertusScientificPlot(
            title="Corridor profile: RMSE(d)", y_label="RMSE", x_label="d (nm)"
        )
        self.plot_corridor_rmse_d.showGrid(x=True, y=True, alpha=0.25)
        self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_vals = np.array([], dtype=np.float64)
        self._corridor_rmse_best_idx = -1
        self._corridor_rmse_center_nm = float("nan")
        self._corridor_rmse_grid_live_t0: float = float("nan")
        self._corridor_rmse_live_last_plot_ts: float = float("nan")
        self._corridor_rmse_live_plot_min_interval_s: float = 0.12
        self._corridor_rmse_robust_lo = float("nan")
        self._corridor_rmse_robust_hi = float("nan")
        self._corridor_rmse_robust_ok = False
        self._corridor_rmse_curve = self.plot_corridor_rmse_d.plot(
            [],
            [],
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
            name="RMSE(d)",
        )
        self._corridor_rmse_curve.setZValue(10)
        self._corridor_rmse_best_marker = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(CertusTheme.SUCCESS, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self.plot_corridor_rmse_d.addItem(self._corridor_rmse_best_marker)

        self.sp_corridor_rmse_delta.valueChanged.connect(self._refresh_corridor_rmse_robust_view)
        self.sp_corridor_rmse_win.valueChanged.connect(self._refresh_corridor_rmse_robust_view)

        _scene = self.plot_corridor_rmse_d.plotItem.scene()
        if _scene is not None:
            _scene.sigMouseClicked.connect(self._on_corridor_rmse_plot_clicked)

        # Plot area on the LEFT
        lay.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_corridor_rmse_d), 1)

        self._apply_corridor_preset_auto_robust()
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        return panel

    def _refresh_corridor_rmse_robust_view(self) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE robust refresh failed", exc_info=True)

    def _set_corridor_grid_completed_badge(self) -> None:

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.stop(final_message="Done")

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            base = str(self.lbl_corridor_rmse_grid_progress.text() or "").strip()

            if "Final fit updated" not in base:
                self.lbl_corridor_rmse_grid_progress.setText(f"{base} | Final fit updated")

    def _update_corridor_rmse_state_bar(self, src: dict[str, Any] | None = None) -> None:

        if not hasattr(self, "lbl_corridor_rmse_state"):
            return

        if not isinstance(src, dict):
            src = self._corridor_profile_source_result()

        if not isinstance(src, dict):
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        src = normalize_corridor_live_payload(src)
        d_s = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        if d_s.size == 0:
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to begin.")
            return

        has_manual = bool(src.get("manual_corridor_active", False))
        d_min = float(np.nanmin(d_s)) if np.any(np.isfinite(d_s)) else float("nan")
        d_max = float(np.nanmax(d_s)) if np.any(np.isfinite(d_s)) else float("nan")

        if has_manual:
            self.lbl_corridor_rmse_state.setText(
                f"Step 3/3: Corridor generated | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )
        else:
            self.lbl_corridor_rmse_state.setText(
                f"Step 2/3: Select an interval, then generate the corridor | grid {int(d_s.size)} points | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )

    def _corridor_profile_source_result(self) -> dict[str, Any] | None:

        for cand in (self._last_result, self._last_worker_result):
            if not isinstance(cand, dict):
                continue

            d_prof = np.asarray(cand.get("profile_d_values_nm", []), dtype=np.float64).ravel()

            r_prof = np.asarray(cand.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

            if d_prof.size > 0 and r_prof.size == d_prof.size:
                return cand

        return self._last_result

    def _set_corridor_rmse_view_centered(self, d_center: float, half_width_nm: float) -> None:

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        if not np.isfinite(d_center):
            return

        hw = float(max(0.0, half_width_nm))

        if not np.isfinite(hw):
            return

        hw_eff = float(max(hw, 0.5))

        pad = float(max(0.02 * (2.0 * hw_eff), 0.25))

        self.plot_corridor_rmse_d.plotItem.setXRange(
            float(d_center - hw_eff - pad), float(d_center + hw_eff + pad), padding=0.0
        )

    def _set_corridor_rmse_view_data_bounds(self, d_vals: np.ndarray, r_vals: np.ndarray) -> None:
        """Sets the scale of the RMSE(d) graph to the min/max bounds of the data."""

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        xd = np.asarray(d_vals, dtype=np.float64).ravel()

        yd = np.asarray(r_vals, dtype=np.float64).ravel()

        m = np.isfinite(xd) & np.isfinite(yd)

        xd = xd[m]

        yd = yd[m]

        if xd.size == 0 or yd.size == 0:
            return

        x_lo = float(np.min(xd))

        x_hi = float(np.max(xd))

        y_lo = float(np.min(yd))

        y_hi = float(np.max(yd))

        x_span = max(1e-12, x_hi - x_lo)

        y_span = max(1e-12, y_hi - y_lo)

        x_pad = max(0.25, 0.02 * x_span)

        y_pad = max(1e-8, 0.04 * y_span)

        self.plot_corridor_rmse_d.plotItem.setXRange(x_lo - x_pad, x_hi + x_pad, padding=0.0)

        self.plot_corridor_rmse_d.plotItem.setYRange(y_lo - y_pad, y_hi + y_pad, padding=0.0)

    def _on_corridor_rmse_lock_scale_toggled(self, _checked: bool) -> None:

        src = self._corridor_profile_source_result()

        if src is None:
            return

        try:
            self._plot_corridor_rmse_tab(src)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("Corridor RMSE lock-scale refresh failed", exc_info=True)

    def _use_robust_corridor_interval(self) -> None:

        if not bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        float(d_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        if not (np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb >= d_lo_rb):
            return

        half = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        half = float(min(max(0.0, half), max_half))

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.setValue(int(round(half * scale)))
            # setValue does not emit valueChanged if unchanged: force visual sync
            # so vertical interval bars always reflect current robust bounds.
            self._on_corridor_manual_slider_changed(self.sl_corridor_manual_half.value())

    def _build_tab_data_corridor(self) -> QWidget:
        """Tab dedicated to detailed corridor uncertainty data."""
        # Sync context stack
        self._add_context_page(
            self._create_empty_context_widget(
                "Detailed corridor uncertainty table.\nIncludes nominal, center, and min/max bounds."
            )
        )

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()
        self.btn_copy_corridor = create_styled_button("Copier tableau Corridors", "secondary")
        self.btn_copy_corridor.setEnabled(False)
        self.btn_copy_corridor.clicked.connect(self._copy_corridor_to_clipboard)
        tb.addWidget(self.btn_copy_corridor)

        self.btn_export_corridor = create_styled_button("Export CSV Corridors...", "primary")
        self.btn_export_corridor.setEnabled(False)
        self.btn_export_corridor.clicked.connect(self._export_corridor_csv)
        tb.addWidget(self.btn_export_corridor)

        tb.addStretch(1)
        lay.addLayout(tb)

        self.table_corridor = ExcelTableWidget()
        self.table_corridor.setColumnCount(9)
        self.table_corridor.setHorizontalHeaderLabels(
            ["lambda (nm)", "n nominal", "k nominal", "n center", "k center", "n min", "n max", "k min", "k max"]
        )
        self.table_corridor.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table_corridor, 1)

        return panel

    def _copy_corridor_to_clipboard(self) -> None:
        if hasattr(self, "table_corridor"):
            t = self.table_corridor
            lines = []
            cols = t.columnCount()
            hdr = [t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(cols)]
            lines.append("\t".join(hdr))
            for r in range(t.rowCount()):
                row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(cols)]
                lines.append("\t".join(row))
            QApplication.clipboard().setText("\n".join(lines))

    def _export_corridor_csv(self) -> None:
        if not self._ensure_complete_manifest_for_secondary_export():
            return
        if not hasattr(self, "table_corridor"):
            return
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Export Corridor CSV", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            import csv

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = [
                    self.table_corridor.horizontalHeaderItem(i).text() for i in range(self.table_corridor.columnCount())
                ]
                writer.writerow(headers)
                for r in range(self.table_corridor.rowCount()):
                    writer.writerow(
                        [
                            self.table_corridor.item(r, c).text() if self.table_corridor.item(r, c) else ""
                            for c in range(self.table_corridor.columnCount())
                        ]
                    )

    def _refresh_corridors_gui_state_labels(self) -> None:
        """Refresh corridor state badges for the post-optimization controls."""

        role = str(getattr(self, "_worker_role", "idle") or "idle")
        unlocked = isinstance(getattr(self, "_last_result", None), dict)

        if role == "rmse_grid":
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>calculation in progress...</b></span>'
        elif not unlocked:
            rich = (
                f'Corridors: <span style="color:{CertusTheme.TEXT_SUB};"><b>available after optimization</b></span>'
            )

        elif bool(
            self._last_result.get("profile_d_enabled", False)
            or self._last_result.get("profile_d_values_nm") is not None
        ):
            rich = f'Corridors: <span style="color:{CertusTheme.SUCCESS};"><b>already computed</b></span>'

        else:
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>ready to launch</b></span>'

        if hasattr(self, "lbl_corridors_run_state"):
            self.lbl_corridors_run_state.setText(rich)

        if hasattr(self, "lbl_corridors_state_adv"):
            self.lbl_corridors_state_adv.setText(rich)

        if hasattr(self, "lbl_corridors_tab_state"):
            self.lbl_corridors_tab_state.setText(rich)

    def _on_btn_corridor_clicked(self) -> None:

        seed = self._manual_postprocess_seed_result()
        if not isinstance(seed, dict):
            QMessageBox.information(
                self,
                "Corridors",
                "Run an optimization first to have a base result.",
            )
            return
        if self.logger:
            self.logger.info(
                "Corridors manual trigger | base=%s",
                "standard",
            )
        if not self._start_deferred_corridor_worker(seed):
            QMessageBox.warning(
                self,
                "Corridors",
                "Unable to start manual corridor calculation from the current result.",
            )

    def _sync_corridor_btn_from_chk(self) -> None:

        if not hasattr(self, "btn_corridor_toggle") or not hasattr(self, "chk_corridor_d"):
            return

    def _on_corridor_chk_state_changed(self, *_args) -> None:

        self._refresh_corridors_gui_state_labels()
