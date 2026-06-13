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

class _LazyCertusIndexSplineApp:
    def __getattr__(self, name):
        from certus.ui.certus_index_spline_ui import CertusIndexSplineApp
        return getattr(CertusIndexSplineApp, name)

CertusIndexSplineApp = _LazyCertusIndexSplineApp()

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

















class CertusIndexSplineEventsExtrasMixin:
    """CertusIndexSplineEventsExtrasMixin."""

    def _warmup_numba(self) -> None:
        """UX consistency for warmup via background thread"""
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        import threading
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _warmup_numba_thread_runner(self) -> None:
        try:
            import time
            time.sleep(0.5)  # Minimal UI wait to display the toast and ensure base app is ready
            self.sig_numba_ready.emit()
        except Exception as e:
            from PyQt6.QtCore import QMetaObject, Qt
            self.logger.error(f" Numba warmup failed: {e}", exc_info=True)
            self.sig_numba_error.emit()

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("Ready (JIT Compiled)")
        self._on_numba_ready()  # Mark as ready
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("JIT Init Error")

    def _prog_reset_bar(self) -> None:

        anim = getattr(self, "_prog_anim", None)

        if anim is not None and anim.state() == QAbstractAnimation.State.Running:
            anim.stop()

        self.progress_widget.reset()

    def _cleanup_thread(self) -> None:

        worker = getattr(self, "_worker", None)

        if worker is None:
            return

        if worker.isRunning():
            try:
                if hasattr(worker, "stop"):
                    worker.stop()

            except (RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            # Short cooperative window (heavy RMSE grids can exceed 100 ms).
            for _ in range(80):
                if not worker.isRunning():
                    break

                worker.wait(50)

            if worker.isRunning() and self.logger:
                self.logger.warning("Worker thread still running after ~4s wait; queued deleteLater()")

        try:
            worker.deleteLater()

        except RuntimeError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self._worker = None

    def _prepare_worker_restart(self) -> None:
        """Stop current worker cooperatively before creating a new stop event."""
        prev_stop = getattr(self, "_stop_event", None)
        if isinstance(prev_stop, Event):
            prev_stop.set()
        self._cleanup_thread()
        self._stop_event = Event()

    @staticmethod
    def _rmse_from_result_dict(d: dict) -> float:
        """RMSE displayable for comparison (priority to  rmse  key, else ?MSE)."""

        r = d.get("rmse")

        if r is not None and np.isfinite(float(r)):
            return float(r)

        m = float(d.get("mse", float("nan")))

        if np.isfinite(m):
            return float(np.sqrt(max(m, 0.0)))

        return float("inf")

    @staticmethod
    def _runtime_metrics_from_result_dict(d: dict | None) -> tuple[float, float]:

        if not isinstance(d, dict):
            return float("nan"), float("nan")

        try:
            d_nm = float(d.get("d_nm", float("nan")))

        except (TypeError, ValueError):
            d_nm = float("nan")

        rmse = CertusIndexSplineApp._rmse_from_result_dict(d)

        if not np.isfinite(rmse):
            rmse = float("nan")

        return d_nm, rmse

    @staticmethod
    def _format_lambda_knots_for_log(lambda_knots_nm: Any, *, precision: int = 1, max_items: int = 6) -> str:

        lam = np.asarray(lambda_knots_nm if lambda_knots_nm is not None else [], dtype=np.float64).ravel()

        lam = lam[np.isfinite(lam) & (lam > 0.0)]

        if lam.size == 0:
            return "[]"

        lam = np.sort(lam)

        if lam.size <= int(max_items):
            return "[" + ", ".join(f"{float(v):.{precision}f}" for v in lam) + "]"

        head = [f"{float(v):.{precision}f}" for v in lam[:3]]

        tail = [f"{float(v):.{precision}f}" for v in lam[-2:]]

        return "[" + ", ".join([*head, "...", *tail]) + "]"

    @staticmethod
    def _strip_worker_final_fields_inconsistent_with_live_merge(merged: dict[str, Any]) -> None:
        """Removes fields from the **final** worker dict that no longer describe the displayed curves after merging

        with the best live snapshot (n_lam/k_lam/d/x come from the live one).

        Without this: corridors, bootstrap, reg scan, polish spline sigma (seg_spline_sigma), spectral RMSEs

        and ln_k_lam would remain aligned with the final solution - resulting in wrong Excel export / metadata."""

        _variant_nk = (
            "n_lam_seg_spline_sigma",
            "k_lam_seg_spline_sigma",
        )

        for k in list(merged.keys()):
            if k.startswith("profile_d_"):
                merged.pop(k, None)

            elif k.startswith("corridor_"):
                merged.pop(k, None)

            elif k.startswith("boot_"):
                merged.pop(k, None)

            elif k.startswith("reg_sens"):
                merged.pop(k, None)

            elif k.startswith("spectral_rmse_"):
                merged.pop(k, None)

        for k in _variant_nk:
            merged.pop(k, None)

        merged.pop("ln_k_lam", None)

        merged.pop("spectral_rmse", None)

        merged.pop("d_nm_seg_spline_sigma", None)

    def _on_worker_err(self, msg: str) -> None:
        role = str(getattr(self, "_worker_role", "") or "")
        manual_pipeline_roles = (
            "manual_sigma_insert",
            "manual_autoshift",
            "manual_auto_add_one",
            "manual_auto_clean",
            "manual_repartition_log",
            "manual_repartition_sigma",
        )
        manual_dlg = getattr(self, "_manual_knots_dialog", None)

        if str(getattr(self, "_worker_role", "") or "") == "rmse_grid":
            self._set_corridor_grid_busy(False)

            self._corridor_rmse_grid_live_t0 = float("nan")
            self._corridor_rmse_live_last_plot_ts = float("nan")

            self._worker_role = "idle"

        uninstall_skeleton(self.tabs_main)
        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        if isinstance(msg, tuple) and len(msg) == 3:
            s_msg = str(msg[1])

            logger.error(msg[2])

            if self.logger:
                self.logger.error("Optimization: %s", s_msg)

        else:
            s_msg = str(msg)

            logger.error(s_msg)

            if self.logger:
                self.logger.error("Optimization: %s", s_msg)

        if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
            manual_dlg.set_runtime_busy(False)
            manual_dlg.set_runtime_progress(100.0, "Error")
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                getattr(manual_dlg, "_base_sigma_knots", np.asarray([], dtype=np.float64)),
                manual_dlg.selected_sigma_knots(),
            )
            manual_dlg.append_runtime_log(
                CertusIndexSplineApp._manual_mesh_change_log_line("Mesh at failure", mesh_summary)
            )
            manual_dlg.append_runtime_log(f"Re-optimization error: {s_msg}")

        QMessageBox.critical(self, "Optimization error", s_msg)

        self._worker_role = "idle"
        self._corridor_auto_refine_plan = None

        self._refresh_post_optimization_option_controls()

    @staticmethod
    def _is_rmse_d_grid_worker_finalize_dict(r: object) -> bool:
        """True if ``r`` is the final dict from the RMSE(d) grid worker (not a full solver result)."""
        if not isinstance(r, dict):
            return False
        st = str(r.get("profile_d_status", ""))
        return st in {"manual_grid", "manual_grid_empty"}

    def _merge_rmse_grid_promotion_into_nominal(self, promoted: dict, *, adoption_log_tag: str) -> None:
        """Merges a promoted dict (global-opt or grid minimum) into ``_last_result`` and refreshes the UI."""
        prev_nominal = dict(self._last_result) if isinstance(self._last_result, dict) else {}
        merged_nominal = dict(prev_nominal)
        merged_nominal.update(promoted)
        if merged_nominal.get("lam_nm") is None:
            lam_prev = prev_nominal.get("lam_nm")
            if lam_prev is not None:
                merged_nominal["lam_nm"] = np.asarray(lam_prev, dtype=np.float64).ravel().copy()
            elif self.df is not None and "lambda" in self.df.columns:
                merged_nominal["lam_nm"] = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid [%s] | promoted result missing lam_nm; fallback applied.",
                    adoption_log_tag,
                )
        self._last_result = merged_nominal
        if self.logger:
            rmse_after_replace = self._rmse_from_result_dict(self._last_result)
            self.logger.info(
                "GUI RMSE(d) regular grid [%s] | nominal merged | rmse_after_replace=%s | d_nm=%s",
                adoption_log_tag,
                (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a"),
                (
                    f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                    if np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                    else "n/a"
                ),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: adoption grille RMSE(d) → nominal _last_result",
                self._last_result.get("d_nm"),
                detail=(
                    "tag="
                    + str(adoption_log_tag)
                    + " rmse="
                    + (f"{rmse_after_replace:.8f}" if np.isfinite(rmse_after_replace) else "n/a")
                ),
            )
        try:
            self._plot_result(self._last_result, plot_source="promotion_grille_rmse")
            self._refresh_data_table()
        except (ValueError, TypeError, AttributeError, RuntimeError):
            logger.debug("Failed to refresh plot after RMSE grid promotion", exc_info=True)

    def _start_curve_minimum_deep_refit(self, seed: dict) -> bool:
        """Launches ``quick_pwlnk_refit_result_dict`` (L-BFGS-B on d + nodes) from the grid minimum seed."""
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "Optimization", "A calculation is already in progress.")
            return False
        cfg = self._last_run_cfg
        if cfg is None:
            cfg = self._build_opt_config(notify=False)
        if cfg is None:
            QMessageBox.warning(
                self,
                "Optimization",
                "No optimization configuration available (run a fit first).",
            )
            return False
        cfg = self._cfg_with_result_substrate(cfg, seed)
        polish = int(getattr(cfg, "polish_maxfun", 10000) or 10000)
        deep_maxfun = int(max(4000, min(24000, int(round(1.5 * float(polish))))))
        CertusIndexSplineApp._prepare_worker_restart(self)
        self._worker = GenericWorker(
            _worker_curve_minimum_deep_refit,
            cfg,
            dict(seed),
            self._stop_event,
            deep_maxfun=deep_maxfun,
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "curve_min_deep"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._prog_ui_last = 0
        self._prog_reset_bar()
        sd = float(seed.get("d_nm", float("nan")))
        self.lbl_status.setText(
            f"Grid minimum? Deep L-BFGS-B polish (d+nodes, maxfun={deep_maxfun}) from d={sd:.3f} nm"
        )
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | start | deep_maxfun=%d | seed_d_nm=%s",
                deep_maxfun,
                (f"{sd:.6f}" if np.isfinite(sd) else "n/a"),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: polish profond depuis minimum grille RMSE(d)",
                seed.get("d_nm"),
                detail=f"deep_maxfun={deep_maxfun}",
            )
        self._worker.start()
        return True

    def _wire_worker_signals(self, progress_fn) -> None:
        """Wire the standard progress/live callbacks for a worker run."""
        self._worker.kwargs["progress_cb"] = progress_fn
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_live_update)

        def _manual_live_metrics(payload: object) -> None:
            if not isinstance(payload, dict):
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                d_live = float(payload.get("d_nm", float("nan")))
                rmse_live = float(payload.get("rmse", float("nan")))
                self._manual_knots_dialog.set_runtime_metrics(d_live, rmse_live)

        self._worker.signals.live.connect(_manual_live_metrics)

    def _set_worker_running_state(self, running: bool) -> None:
        """Toggle UI controls between running/idle state."""
        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(running)
        self._refresh_post_optimization_option_controls()
        if running:
            self._prog_ui_last = 0
            self._prog_reset_bar()

    @staticmethod
    def _control_group_box_style() -> str:

        return (
            f"QGroupBox {{ font-weight: bold; border: 1px solid {CertusTheme.BORDER}; "
            f"border-radius: 6px; margin-top: 12px; padding-top: 10px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; "
            f"color: {CertusTheme.TEXT_MAIN}; }}"
        )

    def _update_persistent_nk_monitor(
        self, lam_arr: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray, d_nm: float | None = None
    ) -> None:

        mon = getattr(self, "_live_nk_monitor", None)

        if mon is None:
            return

        try:
            if hasattr(mon, "update_indices"):
                mon.update_indices(lam_arr, n_arr, k_arr, d_nm)

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("_update_persistent_nk_monitor failed", exc_info=True)

    def _save_undo_state(self) -> None:
        """Store current state before computation in undo stack (Ctrl+Z via CertusBaseApp)."""

        if not hasattr(self, "undo_stack"):
            return

        d_lo_ui, d_hi_ui = self._get_thickness_bounds_nm()

        state = SplineState(
            result=dict(self._last_result) if self._last_result is not None else None,
            d_lo=float(d_lo_ui),
            d_hi=float(d_hi_ui),
            wt=self.w_t.value(),
            wr=self.w_r.value(),
        )

        self.undo_stack.append(state)

        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(True)

    def _get_thickness_bounds_nm(self) -> tuple[float, float]:

        d_nom = float(self.d_lo.value()) if hasattr(self, "d_lo") else float("nan")

        d_pm = float(self.d_hi.value()) if hasattr(self, "d_hi") else float("nan")

        if not np.isfinite(d_nom):
            d_nom = 0.5 * float(SIO2_DEFAULT_D_LO_NM + SIO2_DEFAULT_D_HI_NM)

        if not np.isfinite(d_pm):
            d_pm = 0.5 * float(abs(SIO2_DEFAULT_D_HI_NM - SIO2_DEFAULT_D_LO_NM))

        d_pm = max(0.1, float(abs(d_pm)))

        d_lo = max(1.0, float(d_nom - d_pm))

        d_hi = max(d_lo + 0.1, float(d_nom + d_pm))

        return float(d_lo), float(d_hi)

    def _set_thickness_bounds_ui(self, d_lo: float, d_hi: float) -> None:

        dlo = float(min(d_lo, d_hi))

        dhi = float(max(d_lo, d_hi))

        d_nom = 0.5 * (dlo + dhi)

        d_pm = max(0.1, 0.5 * (dhi - dlo))

        if hasattr(self, "d_lo"):
            self.d_lo.setValue(float(d_nom))

        if hasattr(self, "d_hi"):
            self.d_hi.setValue(float(d_pm))

    def _setup_logger(self, name: str) -> None:
        """Route core logs (CERTUS, CERTUS_INDEX_SPLINE) to the same GUI queue."""

        from certus.core.certus_core import QueueHandler

        super()._setup_logger(name)

        qh = next(
            (h for h in (self.logger.handlers or []) if isinstance(h, QueueHandler)),
            None,
        )

        if qh is None:
            return

        for ln in ("CERTUS", "CERTUS_INDEX_SPLINE"):
            lg = logging.getLogger(ln)

            if any(
                isinstance(h, QueueHandler) and getattr(h, "log_queue", None) is self.log_queue for h in lg.handlers
            ):
                continue

            lg.setLevel(logging.INFO)

            lg.addHandler(qh)

    def _create_empty_context_widget(self, message: str) -> QWidget:
        """Creates a waiting/info page for the contextual settings panel."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-style: italic; font-size: 11px;")
        lbl.setWordWrap(True)
        lay.addStretch(1)
        lay.addWidget(lbl)
        lay.addStretch(1)
        return w

    def _k_crosshair_formatter(self, x: float, y_on_curve: float | None, y_mouse: float) -> str:
        """Formats the cursor display for logarithmic scales of k."""
        # Priority to the interpolated value on the curve (already in physical k in our plots).
        y_val = y_on_curve if y_on_curve is not None else y_mouse
        k_val = float("nan")
        if y_val is not None and np.isfinite(float(y_val)):
            y_num = float(y_val)
            # Compat: if a log10 coordinate is provided (<=0), we convert back.
            k_val = y_num if y_num > 0.0 else float(10.0**y_num)
        if not np.isfinite(k_val):
            return f"x = {x:.2f}, k = n/a"
        return f"x = {x:.2f}, k = {k_val:.3e}"

    def _get_log_widget(self) -> Any | None:

        return getattr(self.log_panel, "log_text", None) if hasattr(self, "log_panel") else None

    def _restore_simple_auto_uncertainty_pref(self) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        v = s.value(_QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY)

        if v is None:
            self._simple_auto_uncertainty = True

        else:
            self._simple_auto_uncertainty = bool(v)

    def _persist_simple_auto_uncertainty_pref(self) -> None:

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SPLINE_SIMPLE_AUTO_UNCERTAINTY, bool(getattr(self, "_simple_auto_uncertainty", True))
        )

    def _apply_sio2_default_fit_parameters(self) -> None:
        """Thickness bounds, RMSE lambda window and nk interpolation for thin SiO2 layers (cf. TSIO2 / sapphire logs)."""

        self._set_thickness_bounds_ui(float(SIO2_DEFAULT_D_LO_NM), float(SIO2_DEFAULT_D_HI_NM))

        self._rmse_fit_lambda_enabled = bool(SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED)

        self._rmse_fit_lambda_lo = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

        self._rmse_fit_lambda_lo_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM)

        self._rmse_fit_lambda_hi_default = float(SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM)

    def _update_epured_visibility(self) -> None:

        if not hasattr(self, "_stack_box4_adv"):
            return

        epure = bool(getattr(self, "_simple_auto_uncertainty", True))

        self._stack_box4_adv.setCurrentIndex(0 if epure else 1)

    def _build_tab_spectrum(self) -> QWidget:
        # Controls are moved to the context_stack on the right
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        row_axis = QHBoxLayout()
        row_axis.addWidget(QLabel("X Axis:"))
        self.cb_spectrum_xmode = QComboBox()
        self.cb_spectrum_xmode.addItem("Lambda (nm)", "lambda")
        self.cb_spectrum_xmode.addItem("Sigma (nm?1)", "sigma")
        self.cb_spectrum_xmode.addItem("Sigma2 (nm?2)", "sigma2")
        self.cb_spectrum_xmode.currentIndexChanged.connect(self._on_spectrum_x_mode_changed)
        row_axis.addWidget(self.cb_spectrum_xmode)
        row_axis.addStretch(1)
        ctx_lay.addLayout(row_axis)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_T = CertusScientificPlot(title="Spectrum", y_label="T, R or T/T_sub", x_label="lambda (nm)")
        self.plot_T.showGrid(x=True, y=True, alpha=0.25)
        self.plot_T._certus_context_menu_augment_fn = self._spectrum_plot_context_menu_augment
        self.plot_T._certus_crosshair_label_fn = self._spectrum_T_crosshair_formatter
        lay.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_T), 1)

        return panel

    @staticmethod
    def _robust_interval_from_local_quadratic(
        d_s: np.ndarray,
        r_s: np.ndarray,
        i_best: int,
        delta_rmse: float,
        half_window_pts: int,
    ) -> tuple[bool, float, float, float, float]:

        fit = _fit_local_quadratic_rmse_profile(
            d_s,
            r_s,
            i_best,
            half_window_pts,
            delta_rmse,
        )

        if not bool(fit.get("ok", False)):
            return False, float("nan"), float("nan"), float("nan"), float("nan")

        return (
            True,
            float(fit.get("d_lo", float("nan"))),
            float(fit.get("d_hi", float("nan"))),
            float(fit.get("slope_at_anchor", float("nan"))),
            float(fit.get("curvature", float("nan"))),
        )

    def _detach_current_plot(self) -> None:

        w = self.tabs_main.currentWidget()

        if w is None:
            return

        plots = w.findChildren(CertusScientificPlot)

        if not plots:
            QMessageBox.information(self, "Detach", "No scientific plot in this tab.")

            return

        tab_name = self.tabs_main.tabText(self.tabs_main.currentIndex())

        self.open_detached_certus_plot(plots[0], title=f"{self.APP_NAME}  {tab_name}")

    @staticmethod
    def _lam_uniform_grid_nm(lo_h: float, hi_h: float, step: float) -> np.ndarray:
        return _lam_uniform_grid(lo_h, hi_h, step)

    @staticmethod
    def _lam_piecewise_report_grid_nm(lo: float, hi: float) -> np.ndarray:
        """2 nm step on (lambda_min, 400), 5 nm on )400, 1200), 10 nm beyond (nm)."""

        if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
            return np.array([], dtype=np.float64)

        parts: list[np.ndarray] = []

        a, b = float(lo), float(min(hi, 400.0))

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 2.0))

        a, b = float(max(lo, 400.0)), float(min(hi, 1200.0))

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 5.0))

        a, b = float(max(lo, 1200.0)), float(hi)

        if b >= a - 1e-9:
            parts.append(CertusIndexSplineApp._lam_uniform_grid_nm(a, b, 10.0))

        if not parts:
            return np.array([0.5 * (lo + hi)], dtype=np.float64)

        return np.unique(np.concatenate(parts))

    @staticmethod
    def _fmt_n_data_tab(nv: float) -> str:

        if not np.isfinite(nv):
            return ""

        return f"{float(nv):.4f}"

    @staticmethod
    def _fmt_k_data_tab(kv: float) -> str:

        if not np.isfinite(kv) or kv < 0:
            return ""

        v = float(kv)

        if v == 0.0:
            return "0"

        return f"{v:.2e}"

    @staticmethod
    def _interp_preview_axis(xs: np.ndarray, ys: np.ndarray, xq: float) -> float:

        xs = np.asarray(xs, dtype=np.float64).ravel()

        ys = np.asarray(ys, dtype=np.float64).ravel()

        m = np.isfinite(xs) & np.isfinite(ys)

        if int(np.count_nonzero(m)) < 2:
            return float("nan")

        xv, yv = xs[m], ys[m]

        o = np.argsort(xv, kind="mergesort")

        xv, yv = xv[o], yv[o]

        xf = float(xq)

        if xf < float(xv[0]) or xf > float(xv[-1]):
            return float("nan")

        return float(np.interp(xf, xv, yv))

    @staticmethod
    def _vb_mid_y_plot(w: CertusScientificPlot) -> float:

        try:
            y0, y1 = w.plotItem.vb.viewRange()[1]

            return 0.5 * (float(y0) + float(y1))

        except NUMERICAL_FAULT_EXCEPTIONS:
            return 0.0

    def _apply_cell_style(self, item: QTableWidgetItem, val: float) -> None:
        """Standard styling logic for table items."""
        pass  # Reserved for future color-coding or specific formatting

    def _on_trel_plot_refresh(self) -> None:

        if self.df is None:
            return

        if hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        self._plot_data_raw()

    def _on_profilee_changed(self) -> None:

        key = str(self.cb_profilee.currentData() or "fast")

        pr = SPLINE_PERF_PRESETS.get(key, {})

        v = pr.get("pglobal_max_iter")

        if v is not None:
            self.sp_pg_iter.blockSignals(True)

            self.sp_pg_iter.setValue(int(v))

            self.sp_pg_iter.blockSignals(False)

    def _add_curve(
        self,
        widget: "pg.PlotWidget",
        x: np.ndarray,
        y: np.ndarray,
        color: str,
        name: str,
        is_scatter: bool = False,
        *,
        crosshair_primary: bool = False,
        pen: Any | None = None,
    ) -> bool:
        # UX: If displaying k on a LOG scale, we linearize the provided log10 data
        if widget in [
            getattr(self, "plot_k", None),
            getattr(self, "plot_k_corridor", None),
            getattr(self, "plot_k_nl", None),
        ]:
            y = 10.0**y

        xf, yf = sanitize_xy_for_plot(x, y)

        if xf.size == 0:
            return False

        if is_scatter:
            _plot_spectrum_raw_scatter(widget, xf, yf, color=color, name=name)

        else:
            p = pen if pen is not None else pg.mkPen(color, width=2)

            curve = plot_widget_plot_finite(widget, xf, yf, pen=p, name=name)

            if curve is not None and crosshair_primary:
                setattr(curve, "_certus_crosshair_primary", True)
                if hasattr(curve, "setZValue"):
                    try:
                        curve.setZValue(10)
                    except Exception:
                        pass

        return True

    def _plot_data_raw(self) -> None:

        if self.df is None:
            return

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        x_plot, x_lbl = self._transform_spectrum_x(lam)

        self.plot_T.clear()
        self._spectrum_clear_theory_probe()

        any_curve = False

        if "T" in self.df.columns:
            y_raw = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

            y = y_raw

            tlabel = "T/Tsub exp" if self.chk_trel.isChecked() else "T exp"

            if self._add_curve(self.plot_T, x_plot, y, CertusTheme.PRIMARY, tlabel, True):
                any_curve = True

        if "R" in self.df.columns:
            y_raw = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

            y = y_raw

            rlabel = "R/Tsub exp" if self.chk_trel.isChecked() else "R exp"

            if self._add_curve(self.plot_T, x_plot, y, CertusTheme.SECONDARY, rlabel, True):
                any_curve = True

        if any_curve:
            self.plot_T.autoRange()

        self._apply_spectrum_x_axis_label(x_lbl)

        self._apply_spectrum_plot_title(None)

        self._update_rmse_fit_region_overlay()

    def _remove_rmse_fit_region_overlay(self) -> None:

        items = getattr(self, "_rmse_fit_overlay_items", None) or []

        for ri in items:
            if ri is None:
                continue

            try:
                self.plot_T.removeItem(ri)

            except (AttributeError, RuntimeError):
                logger.debug("_remove_rmse_fit_region_overlay: removeItem failed", exc_info=True)

        self._rmse_fit_overlay_items = []

    def _sync_rmse_lambda_bounds_from_file(self) -> None:

        if self.df is None or "lambda" not in self.df.columns:
            return

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        lam = lam[np.isfinite(lam)]

        if lam.size == 0:
            return

        lo, hi = float(np.min(lam)), float(np.max(lam))

        self._rmse_fit_lambda_lo_default = lo

        self._rmse_fit_lambda_hi_default = hi

        if not self._rmse_fit_lambda_enabled:
            self._rmse_fit_lambda_lo = lo

            self._rmse_fit_lambda_hi = hi

    def _on_stop(self) -> None:

        self._stop_event.set()

        self.lbl_status.setText("Stop requested...")

    def _on_corr_mode_changed(self, _idx: int = 0) -> None:
        """Show alpha vs Delta RMSE spinboxes according to corridor mode (LR hides both thresholds)."""

        if not hasattr(self, "cb_corr_mode"):
            return

        m = str(self.cb_corr_mode.currentData() or "abs_delta_adaptive")

        show_alpha = m == "alpha"

        show_delta = m in ("abs_delta", "abs_delta_adaptive")

        if hasattr(self, "sp_corr_alpha"):
            self.sp_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "lbl_corr_alpha"):
            self.lbl_corr_alpha.setVisible(show_alpha)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "lbl_corr_rmse_delta"):
            self.lbl_corr_rmse_delta.setVisible(show_delta)

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setVisible(show_delta)

    def _refresh_post_optimization_option_controls(self, *_args) -> None:

        unlocked = isinstance(getattr(self, "_last_result", None), dict)

        role = str(getattr(self, "_worker_role", "idle") or "idle")

        controls_enabled = bool(unlocked and role == "idle")

        if hasattr(self, "btn_corridor_toggle"):
            self.btn_corridor_toggle.setEnabled(controls_enabled)

        if hasattr(self, "btn_manual_knots_toggle"):
            self.btn_manual_knots_toggle.setEnabled(controls_enabled)

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.setEnabled(False)

        if hasattr(self, "_stepper"):
            if controls_enabled:
                self._stepper.set_step(6)
            elif getattr(self, "df", None) is not None:
                self._stepper.set_step(1)
            else:
                self._stepper.set_step(0)

        self._refresh_corridors_gui_state_labels()

    @staticmethod
    def _result_uses_split_mesh(result: dict | None) -> bool:

        if not isinstance(result, dict):
            return False
        if bool(result.get("split_knots_refine")):
            return True
        if "sigma_knots_n" in result or "sigma_knots_L" in result:
            return True
        x_encoding = str(result.get("x_encoding", "")).strip().lower()
        return x_encoding.startswith("split_")

    @staticmethod
    def _status_iteration_metric(
        display_dict: dict,
        fallback_dict: dict,
    ) -> tuple[str, int]:

        for key, label in (
            ("nit_total", "evals [global optimizer]"),
            ("nit_combined", "evals [global optimizer]"),
            ("nfev_lbfgsb", "evals [L-BFGS-B local-polish]"),
            ("nit_polish", "iters [cubic-spline-sigma-polish]"),
        ):
            raw = display_dict.get(key, fallback_dict.get(key, None))
            if raw is None:
                continue
            try:
                return label, max(0, int(raw))
            except (TypeError, ValueError):
                continue
        return "iters [cubic-spline-sigma-polish]", 0

    @staticmethod
    def _format_post_optimization_status(display: dict, fallback_result: dict | None = None) -> str:

        display_dict = display if isinstance(display, dict) else {}
        fallback_dict = fallback_result if isinstance(fallback_result, dict) else display_dict
        rmse_tag = (
            "RMSE (lambda band)" if display_dict.get("rmse_fit_lambda_nm") is not None else "RMSE (full spectrum)"
        )
        mse_value = float(display_dict.get("mse", 0.0))
        d_nm_value = float(display_dict.get("d_nm", float("nan")))
        d_01_txt = f"{float(d_nm_value):.1f}" if np.isfinite(float(d_nm_value)) else "n/a"
        iter_label, iter_value = CertusIndexSplineApp._status_iteration_metric(
            display_dict,
            fallback_dict,
        )
        return (
            f"{rmse_tag}  {np.sqrt(max(mse_value, 0.0)):.6f} | d={d_nm_value:.2f} nm "
            f"(d(0.1nm)={d_01_txt} nm) | "
            f"{iter_label}={iter_value}"
        )

    @staticmethod
    def _post_optimization_ready_status(base_status: str) -> str:

        status = str(base_status or "").strip()
        hint = "Available actions: Manual knots / Corridors"
        if not status:
            return hint
        if hint in status:
            return status
        return f"{status} | {hint}"

    def _rmse_fit_lambda_tuple_for_report(self) -> tuple[float, float] | None:
        """lambda window for display/export (result first, else GUI)."""

        rw = None

        if self._last_result is not None:
            rw = self._last_result.get("rmse_fit_lambda_nm")

        if rw is None and getattr(self, "_rmse_fit_lambda_enabled", False):
            rl0 = float(self._rmse_fit_lambda_lo)

            rl1 = float(self._rmse_fit_lambda_hi)

            rw = (min(rl0, rl1), max(rl0, rl1))

        return rw
