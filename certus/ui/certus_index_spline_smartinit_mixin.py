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

















class CertusIndexSplineSmartInitMixin:
    """CertusIndexSplineSmartInitMixin."""

    def _on_smart_init_keep(
        self, dlg: QDialog, cfg: "SplineOptConfig", state: _SmartInitState, ui_ctx: dict[str, Any]
    ) -> None:
        if cfg is None:
            dlg.accept()
            return

        d_final = float(state.preview_d_nm)
        n_phys_final = np.asarray(state.n_phys, dtype=np.float64).copy()
        L_nodes_final = np.asarray(state.L_nodes, dtype=np.float64).copy()
        sk_final = np.asarray(getattr(self, "smart_preview_sk_arr", state.sk), dtype=np.float64).ravel().copy()

        rmse_preview_mesh = float(state.current_rmse)
        rmse_worker_mesh = rmse_preview_mesh
        sk_canon_keep: np.ndarray | None = None
        relax_si_mono = bool(ui_ctx.get("relax_si_mono", False))
        chk_si_deep = ui_ctx.get("chk_si_deep")
        chk_si_two_phase = ui_ctx.get("chk_si_two_phase")

        try:
            lam_c = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
            lam_min_c = float(np.min(lam_c))
            lam_max_c = float(np.max(lam_c))
            _mdl_ck = float(getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.0) or 0.0)
            sk_canon = bridge_sigma_knots_preserve_manual(
                sk_final,
                lam_min_c,
                lam_max_c,
                rmse_fit_lambda_nm=getattr(cfg, "rmse_fit_lambda_nm", None),
                min_delta_lambda_over_lambda_mean=_mdl_ck if _mdl_ck > 0.0 else None,
            )
            sk_canon_keep = sk_canon
            n_on_canon, L_on_canon = interp_n_L_pwlnk_to_sigmas(sk_final, n_phys_final, L_nodes_final, sk_canon)
            _, rmse_worker_mesh = rmse_at_spline_stage_x0_init(
                cfg,
                sk_canon,
                n_on_canon,
                L_on_canon,
                d_final,
                relax_n_mono=False,
            )
            if self.logger:
                log_rmse_mesh_bridge_diagnosis(
                    cfg,
                    sk_final,
                    n_phys_final,
                    L_nodes_final,
                    sk_canon,
                    n_on_canon,
                    L_on_canon,
                    d_final,
                    self.logger,
                    relax_preview_mono=relax_si_mono,
                )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            if self.logger:
                self.logger.warning(
                    "[INDEX_SPLINE.SMART_INIT] keep-preview recalculation failed on worker mesh: %s",
                    exc,
                )
            rmse_worker_mesh = rmse_preview_mesh

        self._preview_ret = (
            sk_final.copy(),
            n_phys_final.copy(),
            L_nodes_final.copy(),
            d_final,
            float(rmse_worker_mesh),
        )

        cfg.smart_preview_node_override = (n_phys_final.copy(), L_nodes_final.copy())
        cfg.smart_preview_exact_sigma_knots = sk_final.copy()
        cfg.smart_preview_exact_n_L = (n_phys_final.copy(), L_nodes_final.copy())
        cfg.smart_preview_d_nm_override = d_final
        cfg.smart_preview_accepted_rmse = float(rmse_worker_mesh)

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SMART_INIT_DEEP, bool(chk_si_deep is not None and chk_si_deep.isChecked())
        )
        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SMART_INIT_TWO_PHASE, bool(chk_si_two_phase is not None and chk_si_two_phase.isChecked())
        )

        cfg.gui_run_pglobal_opt_in = False
        cfg.spline_local_only = True
        cfg.spline_smart_init_deep_two_phase = False

        if self.logger:
            self.logger.info(
                "GUI Smart Init [Keep] | retained preview transferred to worker in forced local-only mode."
            )
            _k_gui = int(sk_final.size)
            _k_wrk = int(sk_canon_keep.size) if sk_canon_keep is not None else _k_gui
            self.logger.info(
                "[INDEX_SPLINE.SMART_INIT] keep-preview reference | preview_rmse=%.6f (k=%d) -> worker_rmse=%.6f (k=%d) | worker uses the second value for optimization",
                rmse_preview_mesh,
                _k_gui,
                rmse_worker_mesh,
                _k_wrk,
            )

        from certus.spline.spline_workers import _pack_spline_stage_result
        from certus.spline.spline_objective import physical_nodes_to_x_slice_n

        n_xi = physical_nodes_to_x_slice_n(n_phys_final, sk_final, cfg.n_mono_band_nm)
        x_final = np.concatenate(([d_final], n_xi, L_nodes_final))
        ui_snap = _pack_spline_stage_result(cfg, sk_final, x_final, float(rmse_worker_mesh**2), 0, 0)
        self._plot_result(ui_snap, plot_source="smart_init_retenir")
        dlg.accept()

    def _execute_smart_init_preset_logic(
        self, cfg: "SplineOptConfig", projector: Any, relax_si_mono: bool, state: "_SmartInitState"
    ) -> None:
        target_sk = np.asarray(state.sk, dtype=np.float64).ravel()
        new_sk, new_n, new_L, new_d = projector(target_sk)
        state.sk = np.asarray(new_sk, dtype=np.float64).ravel().copy()
        state.n_phys = new_n.copy()
        state.L_nodes = new_L.copy()

        if getattr(self, "sk_sorted", None) is not None:
            try:
                _ss = np.asarray(self.sk_sorted, dtype=np.float64).ravel()
                if _ss.size == state.sk.size:
                    self.sk_sorted[:] = state.sk
            except (TypeError, ValueError, IndexError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        from scipy.optimize import minimize_scalar

        def obj_d_only(dv: float) -> float:
            _, rm = rmse_at_spline_stage_x0_init(
                cfg, state.sk, state.n_phys, state.L_nodes, float(dv), relax_n_mono=relax_si_mono
            )
            return float(rm)

        res_d = minimize_scalar(obj_d_only, bounds=(cfg.d_lo, cfg.d_hi), method="bounded", options={"xatol": 0.01})
        if res_d.success:
            state.preview_d_nm = float(res_d.x)

    def _execute_smart_init_run_auto(
        self,
        cfg: "SplineOptConfig",
        row: int,
        is_ln_k: bool,
        L_lo_g: float,
        L_hi_g: float,
        relax_si_mono: bool,
        state: "_SmartInitState",
    ) -> str | None:
        cur_sk = np.asarray(state.sk, dtype=np.float64).ravel()
        n_loc = np.asarray(state.n_phys, dtype=np.float64).ravel()
        L_loc = np.asarray(state.L_nodes, dtype=np.float64).ravel()

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            spn = getattr(self, "smart_preview_n_phys", None)
            spl = getattr(self, "smart_preview_L_nodes", None)
            if spn is not None and spl is not None:
                spn_a = np.asarray(spn, dtype=np.float64).ravel()
                spl_a = np.asarray(spl, dtype=np.float64).ravel()
                if spn_a.size == spl_a.size == cur_sk.size:
                    n_loc = spn_a.copy()
                    L_loc = spl_a.copy()

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            sk_snap = getattr(self, "_si_mesh_sk_snap", None)
            if sk_snap is not None:
                sk_snap = np.asarray(sk_snap, dtype=np.float64).ravel()
                if sk_snap.size >= 2 and sk_snap.size == n_loc.size == L_loc.size and cur_sk.size >= 2:
                    n_loc, L_loc = interp_n_L_pwlnk_to_sigmas(sk_snap, n_loc, L_loc, cur_sk)

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            return f"Inconsistent sigma / n / ln k (k_sigma={cur_sk.size}, len_n={n_loc.size}, len_l={L_loc.size}). Try again after recalculation."

        try:
            out = smart_init_sweep_node_thickness_rmse(
                cfg,
                cur_sk,
                n_loc,
                L_loc,
                int(row),
                is_ln_k=bool(is_ln_k),
                d_lo=float(cfg.d_lo),
                d_hi=float(cfg.d_hi),
                L_lo=L_lo_g,
                L_hi=L_hi_g,
                time_budget_s=2.9,
                d_nm_current=float(state.preview_d_nm),
                relax_n_mono=relax_si_mono,
            )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            return str(exc)

        state.n_phys = np.asarray(out["n_nodes_physical"], dtype=np.float64).ravel().copy()
        state.L_nodes = np.asarray(out["L_nodes"], dtype=np.float64).ravel().copy()
        state.preview_d_nm = float(out["d_nm"])
        return None

    def _execute_smart_init_recall_best(self, state: _SmartInitState) -> str | None:
        if not np.isfinite(state.best_rmse):
            return None
        cur_k = int(np.asarray(state.sk).size)
        if state.best_n.size != cur_k or state.best_L.size != cur_k:
            return f"The sigma mesh has changed since this 'best': impossible to recall n and ln k (best K={state.best_n.size}, current K={cur_k})."
        state.n_phys = state.best_n.copy()
        state.L_nodes = state.best_L.copy()
        return None

    def _execute_smart_init_recalc_logic(
        self, cfg: "SplineOptConfig", grids: dict[str, Any], relax_si_mono: bool, state: "_SmartInitState"
    ) -> dict[str, Any] | None:
        out = recalc_smart_init_spectral_preview(
            cfg,
            state.sk,
            state.n_phys,
            state.L_nodes,
            grids,
            d_nm_fixed=float(state.preview_d_nm),
            relax_n_mono=relax_si_mono,
        )
        if out is None:
            return None

        state.n_phys = np.asarray(out["n_nodes_physical"], dtype=np.float64).ravel().copy()
        state.L_nodes = np.asarray(out["L_nodes"], dtype=np.float64).ravel().copy()
        state.preview_d_nm = float(out["d_best_nm"])
        state.sk = np.asarray(out.get("sigma_knots", state.sk), dtype=np.float64).ravel().copy()

        self.smart_preview_sk_arr = state.sk.copy()
        self.smart_preview_n_phys = state.n_phys.copy()
        self.smart_preview_L_nodes = state.L_nodes.copy()
        self._si_mesh_sk_snap = state.sk.copy()

        state.current_t_th = np.asarray(out["t_theo"], dtype=np.float64).ravel()

        _, rm_depart = rmse_at_spline_stage_x0_init(
            cfg, state.sk, state.n_phys, state.L_nodes, state.preview_d_nm, relax_n_mono=relax_si_mono
        )
        state.current_rmse = rm_depart
        if state.current_rmse < state.best_rmse:
            state.best_rmse = state.current_rmse
            state.best_n = state.n_phys.copy()
            state.best_L = state.L_nodes.copy()

        return out

    def _pick_best_smart_init_material_preset(
        self, cfg: "SplineOptConfig", target_sk: np.ndarray, preview_d_nm: float, relax_si_mono: bool
    ) -> tuple[str, float, float] | None:
        try:
            picked = pick_best_manual_material_preset(
                cfg, target_sk, d_nm_hint=float(preview_d_nm), relax_n_mono=relax_si_mono
            )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            if self.logger:
                self.logger.warning("INDEX_SPLINE [Smart Init] Auto-selection of 3 material presets: %s", exc)
            return None

        if picked is None:
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE [Smart Init] Material presets: no valid RMSE score - keeping current profile."
                )
            return None

        winner, rm_w, d_w, _nw, _Lw, score_rows = picked
        if self.logger:
            parts = [f"{pid}->RMSE={rm:.6f}" for pid, rm in score_rows]
            self.logger.info(
                "INDEX_SPLINE [Smart Init] Material presets (d mini-opt for each): %s | kept **%s** (RMSE=%.6f, d~%.2f nm)",
                " ; ".join(parts),
                winner,
                rm_w,
                d_w,
            )
        return winner, rm_w, d_w

    def _load_smart_init_index_config(
        self,
        state: "_SmartInitState",
        dlg,
        L_lo_g: float,
        L_hi_g: float,
        d_lo_nm: float,
        d_hi_nm: float,
        refresh_knot_lines_and_ui_fn: "Callable[[], None]",
        btn_load_cfg,
    ) -> None:
        """Load a Smart Init index configuration from JSON file and update state."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            dlg, "Load index config (Smart Init)", "", "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from certus.utils.certus_result_schema import validate_project_dict
            validate_project_dict(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(dlg, "Load index config", f"Load failed: {exc}")
            return
        except Exception as exc:
            from certus.utils.errors import CorruptedProjectError
            if isinstance(exc, CorruptedProjectError):
                QMessageBox.warning(dlg, "Load failed - Invalid Config", exc.full_message)
            else:
                QMessageBox.warning(dlg, "Load index config", f"Validation error: {exc}")
            return

        loaded_sk = np.asarray(data.get("sigma_knots"), dtype=np.float64).ravel()
        loaded_n = np.asarray(data.get("n_nodes_physical"), dtype=np.float64).ravel()
        loaded_L = np.asarray(data.get("L_nodes"), dtype=np.float64).ravel()
        loaded_d = float(data.get("d_nm"))


        order = np.argsort(loaded_sk, kind="mergesort")
        loaded_sk = loaded_sk[order]
        loaded_n = np.clip(loaded_n[order], N_MIN_LIMIT, N_MAX_LIMIT)
        loaded_L = np.clip(loaded_L[order], L_lo_g, L_hi_g)
        loaded_d = float(np.clip(loaded_d, d_lo_nm, d_hi_nm))

        state.sk = loaded_sk.copy()
        state.n_phys = loaded_n.copy()
        state.L_nodes = loaded_L.copy()
        state.preview_d_nm = loaded_d

        self.smart_preview_sk_arr = state.sk.copy()
        self.smart_preview_n_phys = state.n_phys.copy()
        self.smart_preview_L_nodes = state.L_nodes.copy()
        self.smart_preview_d_nm = float(state.preview_d_nm)
        self.smart_preview_sig2 = self.smart_preview_sk_arr ** 2

        refresh_knot_lines_and_ui_fn()
        from PyQt6.QtCore import QTimer
        btn_load_cfg.setText("Loaded")
        QTimer.singleShot(1200, lambda: btn_load_cfg.setText("Load"))

    def _apply_smart_init_preset(
        self,
        state: "_SmartInitState",
        cfg: "SplineOptConfig",
        projector: "Callable",
        relax_si_mono: bool,
        refresh_knot_lines_and_ui_fn: "Callable[[], None]",
        feedback_btn=None,
        idle_label: str = "",
    ) -> None:
        """Apply a material preset projector and refresh the dialog UI."""
        self._execute_smart_init_preset_logic(cfg, projector, relax_si_mono, state)

        state.sk = self.smart_preview_sk_arr = state.sk.copy()
        state.n_phys = self.smart_preview_n_phys = state.n_phys.copy()
        state.L_nodes = self.smart_preview_L_nodes = state.L_nodes.copy()
        state.preview_d_nm = self.smart_preview_d_nm = state.preview_d_nm
        self.smart_preview_sig2 = self.smart_preview_sk_arr ** 2

        refresh_knot_lines_and_ui_fn()

        if feedback_btn is not None:
            from PyQt6.QtCore import QTimer
            feedback_btn.setText(f"OK - {len(state.sk)} nodes")
            QTimer.singleShot(1500, lambda b=feedback_btn, t=idle_label: b.setText(t))

    def _execute_smart_init_do_recalc(
        self,
        state: "_SmartInitState",
        cfg: "SplineOptConfig",
        grids,
        relax_si_mono: bool,
        sk_arr: np.ndarray,
        curve_editor_holder: list,
        ui_callbacks: dict,
    ) -> None:
        """Recompute spectra from current n/L/d state and refresh all UI elements.

        ui_callbacks must contain: 'update_main_x_axes', 'sync_knot_labels',
        'refresh_stats', 'refresh_nk_plots_aux', 'refresh_nk_plots_mon'.
        """
        cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)
        state.sk = cur_sk

        out = self._execute_smart_init_recalc_logic(cfg, grids, relax_si_mono, state)
        if out is None:
            return

        ui_callbacks["update_main_x_axes"]()
        ui_callbacks["sync_knot_labels"]()
        ui_callbacks["refresh_stats"](state.preview_d_nm, state.current_rmse)

        lam_u_src = out.get("lam_nm")
        if lam_u_src is None:
            lam_u_src = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
            if self.logger:
                self.logger.warning("Smart-init preview: out.lam_nm missing; fallback to cfg.lam_nm.")
        lam_u = np.asarray(lam_u_src, dtype=np.float64).ravel()
        ou = np.argsort((1.0 / np.maximum(lam_u, 1e-9)) ** 2)

        if "n_lam" in out and "k_lam" in out:
            n_lam_u = np.asarray(out["n_lam"], dtype=np.float64).ravel()
            k_lam_u = np.asarray(out["k_lam"], dtype=np.float64).ravel()
            ui_callbacks["refresh_nk_plots_aux"](lam_u[ou], n_lam_u[ou], k_lam_u[ou])
            ui_callbacks["refresh_nk_plots_mon"](lam_u[ou], n_lam_u[ou], k_lam_u[ou])

        for _ce in curve_editor_holder:
            try:
                _ce.refresh_plots()
            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _smart_mesh_objective_lam_mask_float(self, lam_r: np.ndarray) -> np.ndarray:
        """Same lambda mask as the spline objective on grid ``lam_r`` (result / SMART)."""

        lam_r = np.asarray(lam_r, dtype=np.float64).ravel()

        cfg_opt = self._build_opt_config(notify=False)

        if cfg_opt is not None:
            return objective_lam_mask_on_target_grid(cfg_opt, lam_r).astype(np.float64, copy=False)

        rw = self._rmse_fit_lambda_tuple_for_report()

        m = np.isfinite(lam_r).astype(np.float64, copy=False)

        if rw is not None:
            lo = float(min(rw[0], rw[1]))

            hi = float(max(rw[0], rw[1]))

            m *= ((lam_r >= lo) & (lam_r <= hi)).astype(np.float64)

        return m

    @pyqtSlot(object)
    def _on_smart_preview_requested(self, payload: object) -> None:

        # FIX: After dict->SmartInitPayload conversion, isinstance(payload, dict) was always False
        # causing the dialog to NEVER open. Normalize payload then show dialog unconditionally.
        if isinstance(payload, dict):
            payload = SmartInitPayload.from_dict(payload)

        logger.info(
            "Smart Init GUI slot enter | payload_type=%s | has_wait_event=%s | thread=%s",
            type(payload).__name__,
            getattr(self, "_preview_wait_event", None) is not None,
            type(QThread.currentThread()).__name__,
        )

        try:
            if type(payload).__name__ == "SmartInitPayload":
                logger.info(
                    "Smart Init GUI slot: opening dialog | K_sigma=%d | incoming_d_best_nm=%.6f | preview_shown=%s",
                    int(np.asarray(payload.sigma_knots, dtype=np.float64).size),
                    float(payload.d_best_nm),
                    bool(getattr(self, "_preview_result", None) is not None),
                )

                self._preview_result = bool(self._show_smart_init_preview_dialog(payload))

                logger.info(
                    "Smart Init GUI slot: dialog returned preview_result=%s | preview_ret=%s | wait_event=%s",
                    bool(self._preview_result),
                    getattr(self, "_preview_ret", None) is not None,
                    getattr(self, "_preview_wait_event", None) is not None,
                )

            else:
                logger.warning(
                    "Smart Init preview: unexpected payload type %s, skipping dialog.", type(payload).__name__
                )

                self._preview_result = False
                logger.error("Smart Init preview: unexpected payload, aborting preview safely")

        except NUMERICAL_FAULT_EXCEPTIONS :
            logger.exception("Smart Init preview: GUI error (full traceback)")

            self._preview_result = False

        finally:
            if self._preview_wait_event is not None:
                logger.info(
                    "Smart Init GUI slot: releasing wait_event | preview_result=%s | preview_ret=%s",
                    bool(getattr(self, "_preview_result", False)),
                    getattr(self, "_preview_ret", None) is not None,
                )
                self._preview_wait_event.set()
            else:
                logger.warning("Smart Init GUI slot finished without wait_event; preview stage cannot block safely")
