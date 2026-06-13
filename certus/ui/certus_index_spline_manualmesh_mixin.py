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

















class CertusIndexSplineManualMeshMixin:
    """CertusIndexSplineManualMeshMixin."""

    @staticmethod
    def _sorted_finite_sigma_knots(sigma_knots: Any) -> np.ndarray:
        return _sorted_finite_sigma_knots_impl(sigma_knots)

    @staticmethod
    def _sigma_knots_to_lambda_nm(sigma_knots: Any) -> np.ndarray:

        sig = CertusIndexSplineApp._sorted_finite_sigma_knots(sigma_knots)

        if sig.size == 0:
            return np.empty(0, dtype=np.float64)

        return np.sort(1.0 / np.maximum(sig, 1e-30))

    @staticmethod
    def _sigma_knot_difference_with_tolerance(source_sigma_knots: Any, reference_sigma_knots: Any) -> np.ndarray:

        src = CertusIndexSplineApp._sorted_finite_sigma_knots(source_sigma_knots)

        ref = CertusIndexSplineApp._sorted_finite_sigma_knots(reference_sigma_knots)

        if src.size == 0:
            return np.empty(0, dtype=np.float64)

        if ref.size == 0:
            return src.copy()

        used = np.zeros(ref.size, dtype=bool)

        missing: list[float] = []

        for value in src:
            tol = max(1e-12, 1e-8 * max(abs(float(value)), 1.0))

            idx = np.where((~used) & (np.abs(ref - float(value)) <= tol))[0]

            if idx.size:
                used[int(idx[0])] = True

            else:
                missing.append(float(value))

        return np.asarray(missing, dtype=np.float64)

    @staticmethod
    def _summarize_manual_mesh_change(before_sigma_knots: Any, after_sigma_knots: Any) -> dict[str, Any]:

        before_sigma = CertusIndexSplineApp._sorted_finite_sigma_knots(before_sigma_knots)

        after_sigma = CertusIndexSplineApp._sorted_finite_sigma_knots(after_sigma_knots)

        removed_sigma = CertusIndexSplineApp._sigma_knot_difference_with_tolerance(before_sigma, after_sigma)

        added_sigma = CertusIndexSplineApp._sigma_knot_difference_with_tolerance(after_sigma, before_sigma)

        before_lambda = CertusIndexSplineApp._sigma_knots_to_lambda_nm(before_sigma)

        after_lambda = CertusIndexSplineApp._sigma_knots_to_lambda_nm(after_sigma)

        removed_lambda = CertusIndexSplineApp._sigma_knots_to_lambda_nm(removed_sigma)

        added_lambda = CertusIndexSplineApp._sigma_knots_to_lambda_nm(added_sigma)

        return {
            "k_before": int(before_sigma.size),
            "k_after": int(after_sigma.size),
            "delta_k": int(after_sigma.size - before_sigma.size),
            "before_sigma_knots": before_sigma,
            "after_sigma_knots": after_sigma,
            "removed_sigma_knots": removed_sigma,
            "added_sigma_knots": added_sigma,
            "before_lambda_knots_nm": before_lambda,
            "after_lambda_knots_nm": after_lambda,
            "removed_lambda_knots_nm": removed_lambda,
            "added_lambda_knots_nm": added_lambda,
        }

    @staticmethod
    def _manual_mesh_change_log_line(label: str, summary: dict[str, Any]) -> str:

        k_before = int(summary.get("k_before", 0))

        k_after = int(summary.get("k_after", 0))

        delta_k = int(summary.get("delta_k", 0))

        before_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("before_lambda_knots_nm"))

        after_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("after_lambda_knots_nm"))

        removed_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("removed_lambda_knots_nm"))

        added_txt = CertusIndexSplineApp._format_lambda_knots_for_log(summary.get("added_lambda_knots_nm"))

        removed_count = int(np.asarray(summary.get("removed_lambda_knots_nm", []), dtype=np.float64).size)

        added_count = int(np.asarray(summary.get("added_lambda_knots_nm", []), dtype=np.float64).size)

        return (
            f"{str(label).strip()} | K {k_before}->{k_after} (Delta {delta_k:+d}) | "
            f"before={before_txt} | after={after_txt} | removed={removed_count} {removed_txt} | "
            f"added={added_count} {added_txt}"
        )

    def _can_offer_manual_extra_knots(self, result: dict) -> bool:
        """True if conditions allow proposing manual extra knot placement."""
        if not isinstance(result, dict):
            return False
        sk = result.get("sigma_knots")
        if sk is None:
            if self.logger:
                self.logger.info("Manual nodes: result missing 'sigma_knots'.")
            return False
        sk_a = np.asarray(sk, dtype=np.float64).ravel()
        if sk_a.size < 2:
            if self.logger:
                self.logger.info(f"Manual nodes: sigma_knots size ({sk_a.size}) < 2.")
            return False
        if "sigma_knots_n" in result or "sigma_knots_L" in result:
            if self.logger:
                self.logger.info(
                    "Manual nodes: result has split n/k meshes (sigma_knots_n/L present). "
                    "Manual insertion is not supported in uncoupled mode (Auto-Best / split-knot mode)."
                )
            return False
        lam_src = result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        lam_a = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        if lam_a.size == 0:
            if self.logger:
                self.logger.info("Manual nodes: lam_nm source is empty.")
            return False
        rmse = float(result.get("rmse", float("inf")))
        if not np.isfinite(rmse):
            if self.logger:
                self.logger.info("Manual nodes: result RMSE is not finite.")
            return False
        return True

    def _prompt_manual_extra_knots(self, result: dict) -> tuple[list[float], float] | None:
        """Show the manual extra-knot placement dialog and return (lambda positions, delta_ns) on Go."""
        lam_model = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        y_model = np.asarray(result.get("t_theo", []), dtype=np.float64).ravel()
        lam_measurement = np.empty(0, dtype=np.float64)
        y_measurement = np.empty(0, dtype=np.float64)
        if self.df is not None and "lambda" in self.df.columns and "T" in self.df.columns:
            lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            y_measurement = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

        dlg = ManualSigmaKnotDialog(
            sigma_knots=np.asarray(result.get("sigma_knots", []), dtype=np.float64),
            lam_model_nm=lam_model,
            y_model=y_model,
            lam_measurement_nm=lam_measurement,
            y_measurement=y_measurement,
            y_label="T/Tsub" if bool(result.get("t_is_ratio", False)) else "T",
            initial_delta_ns=0.0,
            parent=self,
        )

        def _on_delta_preview(delta_ns: float) -> None:
            if not self._apply_manual_substrate_offset_preview(result, float(delta_ns)):
                QMessageBox.warning(
                    self,
                    "Delta ns",
                    "Failed to apply delta ns to the current curve.",
                )
                return
            self._refresh_manual_dialog_preview(dlg, self._manual_postprocess_seed_result())

        dlg.delta_preview_requested.connect(_on_delta_preview)
        res_code = dlg.exec()
        if res_code != int(QDialog.DialogCode.Accepted):
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual extra-knot dialog skipped.")
            return None

        selected_lambda_knots_nm = dlg.selected_lambda_knots()
        delta_ns = dlg.substrate_delta_ns()

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: manual extra-knot dialog | count=%d | delta_ns=%+.6f",
                len(selected_lambda_knots_nm),
                float(delta_ns),
            )
        return selected_lambda_knots_nm, delta_ns

    def _open_manual_extra_knots_dialog(self, result: dict) -> None:
        """Open a non-blocking manual-knot dialog that stays open on local apply."""
        lam_model = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        y_model = np.asarray(result.get("t_theo", []), dtype=np.float64).ravel()
        lam_measurement = np.empty(0, dtype=np.float64)
        y_measurement = np.empty(0, dtype=np.float64)
        if self.df is not None and "lambda" in self.df.columns and "T" in self.df.columns:
            lam_measurement = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            y_measurement = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

        dlg = ManualSigmaKnotDialog(
            sigma_knots=np.asarray(result.get("sigma_knots", []), dtype=np.float64),
            lam_model_nm=lam_model,
            y_model=y_model,
            lam_measurement_nm=lam_measurement,
            y_measurement=y_measurement,
            y_label="T/Tsub" if bool(result.get("t_is_ratio", False)) else "T",
            initial_delta_ns=0.0,
            keep_open_on_local_apply=True,
            parent=self,
        )

        def _on_local_apply(selected_lambda_knots_nm: list[float], delta_ns: float) -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: no usable current result.")
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "No usable current result to restart optimization.",
                )
                return
            if selected_lambda_knots_nm:
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.clear_runtime_log()
                    self._manual_knots_dialog.set_runtime_progress(0.0, "Starting local re-optimization")
                    d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                    self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                    mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                        getattr(
                            dlg,
                            "_base_sigma_knots",
                            np.asarray(seed_current.get("sigma_knots", []), dtype=np.float64).ravel(),
                        ),
                        np.sort(
                            1.0 / np.maximum(np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel(), 1e-30)
                        ),
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        f"Forced re-optimization (delta ns included) | delta ns={float(delta_ns):+.6f}"
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        CertusIndexSplineApp._manual_mesh_change_log_line("Requested mesh", mesh_summary)
                    )
                    self._manual_knots_dialog.append_runtime_log(
                        f"Local re-optimization launched | active knots: {len(selected_lambda_knots_nm)} | delta ns={float(delta_ns):+.6f}"
                    )
                    if self.logger:
                        self.logger.info(
                            "INDEX_SPLINE GUI: manual local re-optimization request | %s | delta_ns=%+.6f",
                            CertusIndexSplineApp._manual_mesh_change_log_line("requested", mesh_summary),
                            float(delta_ns),
                        )
                self._start_manual_sigma_insert_worker(seed_current, selected_lambda_knots_nm, float(delta_ns))

        def _on_autoshift() -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                QMessageBox.information(
                    self,
                    "Autoshift",
                    "No usable current result to start autoshift.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting autoshift delta ns")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(
                    "Automatic Brent search for best substrate shift in [-0.01, 0.01]..."
                )
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            self._start_manual_autoshift_worker(seed_current, selected_lambda_knots_nm)

        def _on_auto_repartition(mode: str) -> None:
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "No usable current result to restart optimization.",
                )
                return
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            if len(selected_lambda_knots_nm) < 2:
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "At least two active knots are required for automatic repartition.",
                )
                return
            delta_ns = dlg.substrate_delta_ns()
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                mode_label = "log(sigma)" if str(mode).strip().lower() == "log" else "sigma"
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, f"Starting auto repartition {mode_label}")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                target_sigma_knots = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(
                    selected_lambda_knots_nm,
                    mode=mode,
                )
                mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                    np.sort(1.0 / np.maximum(np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel(), 1e-30)),
                    target_sigma_knots,
                )
                self._manual_knots_dialog.append_runtime_log(
                    f"Automatic repartition {mode_label} launched | active knots: {len(selected_lambda_knots_nm)} | delta ns={float(delta_ns):+.6f}"
                )
                self._manual_knots_dialog.append_runtime_log(
                    CertusIndexSplineApp._manual_mesh_change_log_line("Requested repartition", mesh_summary)
                )
                if self.logger:
                    self.logger.info(
                        "INDEX_SPLINE GUI: manual auto repartition request | mode=%s | %s | delta_ns=%+.6f",
                        str(mode),
                        CertusIndexSplineApp._manual_mesh_change_log_line("requested", mesh_summary),
                        float(delta_ns),
                    )
            self._start_manual_sigma_repartition_worker(
                seed_current, selected_lambda_knots_nm, float(delta_ns), mode=mode
            )

        def _on_delta_preview(delta_ns: float) -> None:
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                return
            if not self._apply_manual_substrate_offset_preview(seed_current, float(delta_ns)):
                return
            self._refresh_manual_dialog_preview(dlg, self._manual_postprocess_seed_result())

        def _on_auto_clean(tolerance: float) -> None:
            # NaN = signal "read value from GUI widget".
            try:
                _tol_in = float(tolerance)
            except (TypeError, ValueError):
                _tol_in = float("nan")
            if not np.isfinite(_tol_in):
                if hasattr(self, "sp_auto_clean_tol"):
                    tolerance = float(self.sp_auto_clean_tol.value())
                else:
                    tolerance = 5.0e-5
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: auto_clean refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: auto_clean refused because no usable seed result")
                QMessageBox.information(
                    self,
                    "Advanced clean",
                    "No usable current result to start cleaning.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting clean...")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(f"Advanced iterative clean (tolerance: +{tolerance})...")
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            delta_ns = dlg.substrate_delta_ns()
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: launching auto_clean | tolerance=+%.5f | seed_rmse=%.8f | seed_d=%.4f | K_selected=%d | delta_ns=%+.6f",
                    float(tolerance),
                    float(CertusIndexSplineApp._rmse_from_result_dict(seed_current)),
                    float(seed_current.get("d_nm", float("nan"))),
                    int(len(selected_lambda_knots_nm)),
                    float(delta_ns),
                )
            self._start_manual_auto_clean_worker(seed_current, selected_lambda_knots_nm, float(delta_ns), tolerance)

        def _on_auto_add_one() -> None:
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: auto_add_one refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log(
                        "Launch refused: an optimization is already in progress."
                    )
                QMessageBox.information(
                    self,
                    "Manual knots",
                    "An optimization is already in progress. Wait for it to finish before restarting.",
                )
                return
            seed_current = self._manual_postprocess_seed_result()
            if not isinstance(seed_current, dict):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: auto_add_one refused because no usable seed result")
                QMessageBox.information(
                    self,
                    "Auto add one",
                    "No usable current result to start auto insertion.",
                )
                return
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                self._manual_knots_dialog.clear_runtime_log()
                self._manual_knots_dialog.set_runtime_progress(0.0, "Starting auto add one...")
                d_seed, rmse_seed = CertusIndexSplineApp._runtime_metrics_from_result_dict(seed_current)
                self._manual_knots_dialog.set_runtime_metrics(d_seed, rmse_seed)
                self._manual_knots_dialog.append_runtime_log(
                    "Auto add one: testing all mid-gap insertion candidates..."
                )
            selected_lambda_knots_nm = dlg.selected_lambda_knots()
            delta_ns = dlg.substrate_delta_ns()
            self._start_manual_auto_add_one_worker(seed_current, selected_lambda_knots_nm, float(delta_ns))

        def _on_recall_best() -> None:
            if self._worker_role not in ("idle",):
                if self.logger:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: recall best refused because worker busy | role=%s",
                        str(self._worker_role),
                    )
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: an optimization is already running.")
                return
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                if self.logger:
                    self.logger.warning("INDEX_SPLINE GUI: recall best requested but no active manual dialog")
                return
            best = dlg_ref.get_best_config()
            if best is None:
                if self.logger:
                    self.logger.info("INDEX_SPLINE GUI: recall best requested but no best snapshot available yet")
                return
            best_result, best_sk = best
            rmse_best = float(best_result.get("rmse", float("nan")))
            K_best = int(best_sk.size)
            # Direct memory restoration — no re-polish to avoid contamination
            # from _best_live_result or intermediate display snapshots.
            dlg_ref.clear_runtime_log()
            dlg_ref.append_runtime_log(f"Recall best config: RMSE={rmse_best:.8f} | K={K_best}")
            dlg_ref.set_runtime_progress(100.0, f"Best config restored (K={K_best})")
            d_best, r_best = CertusIndexSplineApp._runtime_metrics_from_result_dict(best_result)
            dlg_ref.set_runtime_metrics(d_best, r_best)
            dlg_ref.adopt_sigma_knots(best_sk)
            opt_delta_ns = best_result.get("substrate_n_offset")
            if opt_delta_ns is not None:
                dlg_ref.adopt_delta_ns(float(opt_delta_ns))
            # Update graphs and current GUI state (no worker needed)
            self._last_result = best_result
            self._last_worker_result = dict(best_result)
            self._plot_result(best_result, plot_source="recall_best")
            self._refresh_manual_dialog_preview(dlg_ref, best_result)
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: recall best config | RMSE=%.8f | K=%d | d=%.4f nm",
                    rmse_best,
                    K_best,
                    float(best_result.get("d_nm", float("nan"))),
                )

        def _on_dialog_finished(_result_code: int) -> None:
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if dlg_ref is dlg:
                self._manual_knots_dialog = None
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual knots dialog closed")

        dlg.local_apply_requested.connect(_on_local_apply)
        dlg.auto_shift_requested.connect(_on_autoshift)
        dlg.auto_repartition_log_requested.connect(lambda: _on_auto_repartition("log"))
        dlg.auto_repartition_sigma_requested.connect(lambda: _on_auto_repartition("sigma"))
        dlg.auto_clean_requested.connect(_on_auto_clean)
        dlg.auto_add_one_requested.connect(_on_auto_add_one)

        def _on_recall_best_for_k(k: int) -> None:
            """Recall the best config for a specific knot count K."""
            if self._worker_role not in ("idle",):
                if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                    self._manual_knots_dialog.append_runtime_log("Launch refused: an optimization is already running.")
                return
            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                return
            best = dlg_ref.get_best_config_for_k(k)
            if best is None:
                if self.logger:
                    self.logger.info("INDEX_SPLINE GUI: recall best for K=%d requested but no snapshot available", k)
                return
            best_result, best_sk = best
            rmse_best = float(best_result.get("rmse", float("nan")))
            K_best = int(best_sk.size)
            dlg_ref.clear_runtime_log()
            dlg_ref.append_runtime_log(f"Recall best config for K={K_best}: RMSE={rmse_best:.8f}")
            dlg_ref.set_runtime_progress(100.0, f"Best config restored (K={K_best})")
            d_best, r_best = CertusIndexSplineApp._runtime_metrics_from_result_dict(best_result)
            dlg_ref.set_runtime_metrics(d_best, r_best)
            dlg_ref.adopt_sigma_knots(best_sk)
            opt_delta_ns = best_result.get("substrate_n_offset")
            if opt_delta_ns is not None:
                dlg_ref.adopt_delta_ns(float(opt_delta_ns))
            self._last_result = best_result
            self._last_worker_result = dict(best_result)
            self._plot_result(best_result, plot_source=f"recall_best_k{K_best}")
            self._refresh_manual_dialog_preview(dlg_ref, best_result)
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE GUI: recall best config for K=%d | RMSE=%.8f | d=%.4f nm",
                    K_best,
                    rmse_best,
                    float(best_result.get("d_nm", float("nan"))),
                )

        dlg.recall_best_requested.connect(_on_recall_best)
        dlg.recall_best_for_k_requested.connect(_on_recall_best_for_k)
        dlg.stop_requested.connect(self._on_stop)
        dlg.delta_preview_requested.connect(_on_delta_preview)
        dlg.finished.connect(_on_dialog_finished)
        self._manual_knots_dialog = dlg
        dlg.clear_runtime_log()
        seed_d, seed_rmse = CertusIndexSplineApp._runtime_metrics_from_result_dict(result)
        # Initialize per-K best tracking with the current solution at dialog open
        seed_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        dlg.update_best_config(result, seed_sk)
        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: manual dialog opened with initial best snapshot | RMSE=%.8f | K=%d",
                float(CertusIndexSplineApp._rmse_from_result_dict(result)),
                int(seed_sk.size),
            )
        dlg.set_runtime_metrics(seed_d, seed_rmse)
        dlg.set_runtime_progress(100.0, "Ready")
        dlg.append_runtime_log("Ready. Current solution is ready for manual adjustment.")
        dlg.show()

    def _start_manual_sigma_insert_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float = 0.0
    ) -> None:
        """Launch manual sigma node tuning worker after user placement."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            if self.logger:
                self.logger.warning("INDEX_SPLINE GUI: manual extra knots - no config available, abort.")
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size == 0:
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: manual extra knots - empty selection, skip launch.")
            return
        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))
        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        # Tighten the acceptance reference: if a polished RMSE (e.g. cubic-spline sigma)
        # was computed for the current result and is better than the solver dict RMSE,
        # inject it as the effective reference so that direct K→K+n insertion is only
        # accepted when the new mesh does not degrade vs the polished baseline.
        _gb_polished = seed_payload.get("spectral_rmse_global_best_value") or seed_payload.get(
            "spectral_rmse_polished_value"
        )
        if _gb_polished is not None:
            try:
                _gb_f = float(_gb_polished)
                _dict_rmse = float(seed_payload.get("rmse", float("inf")))
                if np.isfinite(_gb_f) and _gb_f < _dict_rmse:
                    seed_payload = dict(seed_payload)
                    seed_payload["rmse"] = _gb_f
                    if self.logger:
                        self.logger.info(
                            "INDEX_SPLINE GUI: manual insert: tightening RMSE reference to polished value %.8f (dict was %.8f)",
                            _gb_f,
                            _dict_rmse,
                        )
            except (TypeError, ValueError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_manual_sigma_insert,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            force_reopt=True,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress.emit(max(0, min(10000, pv)), f"[{float(p):6.2f}%] {str(m)}")

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_sigma_insert"
        if hasattr(self, "_stepper"):
            self._stepper.set_step(5)
        if self.logger:
            K_cur = int(np.asarray(result.get("sigma_knots", []), dtype=np.float64).size)
            rr = float(result.get("rmse", float("nan")))
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel(),
                target_sigma_knots,
            )
            self.logger.info(
                "INDEX_SPLINE GUI: launching manual node tuning worker | K=%d | K_target=%d | rmse=%.8f",
                K_cur,
                int(target_sigma_knots.size),
                rr if np.isfinite(rr) else float("nan"),
            )
            self.logger.info(
                "INDEX_SPLINE GUI: manual node tuning worker mesh summary | %s",
                CertusIndexSplineApp._manual_mesh_change_log_line("target", mesh_summary),
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: worker knot insertion (d seed)",
                result.get("d_nm"),
                detail=(
                    f"K_sigma={K_cur} sigma_knots_added={int(target_sigma_knots.size)} delta_ns={float(delta_ns):+.6f}"
                ),
            )
        self._set_worker_running_state(True)
        self.lbl_status.setText("Manual knots: local re-optimization in progress...")
        install_skeleton(self.tabs_main, label="Manual knots...")
        self._worker.start()

    @staticmethod
    def _build_manual_repartition_target_sigma_knots(selected_lambda_knots_nm: list[float], *, mode: str) -> np.ndarray:
        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        selected_lam = selected_lam[np.isfinite(selected_lam) & (selected_lam > 0.0)]
        if selected_lam.size < 2:
            return np.empty(0, dtype=np.float64)
        sigma_active = np.unique(np.sort(1.0 / np.maximum(selected_lam, 1e-30)))
        if sigma_active.size < 2:
            return np.empty(0, dtype=np.float64)
        sigma_lo = float(np.min(sigma_active))
        sigma_hi = float(np.max(sigma_active))
        k_target = int(sigma_active.size)
        if str(mode).strip().lower() == "log":
            return np.exp(np.linspace(np.log(max(sigma_lo, 1e-30)), np.log(max(sigma_hi, 1e-30)), k_target)).astype(
                np.float64
            )
        return np.linspace(sigma_lo, sigma_hi, k_target, dtype=np.float64)

    def _start_manual_sigma_repartition_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float, *, mode: str
    ) -> None:
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        target_sigma_knots = CertusIndexSplineApp._build_manual_repartition_target_sigma_knots(
            selected_lambda_knots_nm,
            mode=mode,
        )
        if target_sigma_knots.size < 2:
            return

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_manual_sigma_insert,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            force_reopt=True,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress.emit(max(0, min(10000, pv)), f"[{float(p):6.2f}%] {str(m)}")

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = f"manual_repartition_{str(mode).strip().lower()}"
        if self.logger:
            mesh_summary = CertusIndexSplineApp._summarize_manual_mesh_change(
                np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel(),
                target_sigma_knots,
            )
            self.logger.info(
                "INDEX_SPLINE GUI: launching manual repartition worker | mode=%s | K_target=%d | delta_ns=%+.6f",
                str(mode),
                int(target_sigma_knots.size),
                float(delta_ns),
            )
            self.logger.info(
                "INDEX_SPLINE GUI: manual repartition worker mesh summary | mode=%s | %s",
                str(mode),
                CertusIndexSplineApp._manual_mesh_change_log_line("target", mesh_summary),
            )
        self._set_worker_running_state(True)
        mode_label = "log(sigma)" if str(mode).strip().lower() == "log" else "sigma"
        self.lbl_status.setText(f"Manual knots: auto repartition {mode_label} in progress...")
        install_skeleton(self.tabs_main, label=f"Auto repartition {mode_label}...")
        self._worker.start()

    def _start_manual_autoshift_worker(self, result: dict, selected_lambda_knots_nm: list[float]) -> None:
        """Launch autoshift worker to find optimal delta_ns."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            if self.logger:
                self.logger.warning("INDEX_SPLINE GUI: autoshift - no config available, abort.")
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size == 0:
            if self.logger:
                self.logger.info("INDEX_SPLINE GUI: autoshift - empty selection, skip launch.")
            return
        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload["n_sub_base"] = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_autoshift_delta_ns,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress.emit(max(0, min(10000, pv)), f"[{float(p):6.2f}%] {str(m)}")

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_autoshift"
        if self.logger:
            K_cur = int(np.asarray(result.get("sigma_knots", []), dtype=np.float64).size)
            self.logger.info(
                "INDEX_SPLINE GUI: launching autoshift worker | K=%d | K_target=%d",
                K_cur,
                int(target_sigma_knots.size),
            )
        self._set_worker_running_state(True)
        self.lbl_status.setText("Autoshift: searching for delta ns...")
        install_skeleton(self.tabs_main, label="Autoshift delta ns...")
        self._worker.start()

    def _start_manual_auto_add_one_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float
    ) -> None:
        """Launch auto-add-one worker to test all mid-gap insertions and keep the best."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size < 2:
            return

        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))
        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
                auto_add_one_candidate_maxfun=240,
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_auto_add_one_knot,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            if p < 0:
                self._worker.signals.progress.emit(-1, str(m))
            else:
                pv = int(round(float(np.clip(p, 0.0, 100.0)) * 100.0))
                self._worker.signals.progress.emit(max(0, min(10000, pv)), str(m))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_auto_add_one"

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: launching auto_add_one worker | K_target=%d | delta_ns=%+.6f",
                int(target_sigma_knots.size),
                float(delta_ns),
            )

        self._set_worker_running_state(True)
        self.lbl_status.setText("Auto add one: testing all mid-gap insertions...")
        install_skeleton(self.tabs_main, label="Auto add one...")
        self._worker.start()

    def _start_manual_auto_clean_worker(
        self, result: dict, selected_lambda_knots_nm: list[float], delta_ns: float, tolerance: float
    ) -> None:
        """Launch auto-clean worker to iteratively remove least sensitive knots."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return

        selected_lam = np.asarray(selected_lambda_knots_nm, dtype=np.float64).ravel()
        if selected_lam.size <= 2:
            return

        target_sigma_knots = np.sort(1.0 / np.maximum(selected_lam, 1e-30))

        baseline_payload = self._baseline_substrate_n_for_result(result, lam_override=getattr(cfg_base, "lam_nm", None))
        seed_payload = dict(result)
        cfg_manual = cfg_base
        if baseline_payload is not None:
            _, n_sub_base = baseline_payload
            seed_payload = self._decorate_result_with_substrate_offset(
                seed_payload,
                n_sub_base=n_sub_base,
                delta_ns=float(delta_ns),
            )
            cfg_manual = cfg_base.replace(
                n_sub=np.asarray(seed_payload["n_sub_effective"], dtype=np.float64).ravel().copy(),
                substrate_n_base=np.asarray(seed_payload["n_sub_base"], dtype=np.float64).ravel().copy(),
                substrate_n_offset=float(delta_ns),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        self._worker = GenericWorker(
            worker_spline_auto_clean_knots,
            seed_payload,
            cfg_manual,
            self._stop_event,
            target_sigma_knots=target_sigma_knots,
            tolerance=tolerance,
        )

        def _manual_progress(p: float | int, m: str) -> None:
            if p < 0:
                self._worker.signals.progress.emit(-1, str(m))
            else:
                pv = int(round(float(np.clip(p, 0.0, 100.0)) * 100.0))
                self._worker.signals.progress.emit(max(0, min(10000, pv)), str(m))

        self._wire_worker_signals(_manual_progress)

        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_auto_clean"

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: launching auto_clean worker | K_target=%d", int(target_sigma_knots.size)
            )

        self._set_worker_running_state(True)
        self.lbl_status.setText("Advanced cleaning: iterative knot removal in progress...")
        install_skeleton(self.tabs_main, label="Advanced cleaning...")
        self._worker.start()

    def _corridor_manual_half_width_nm(self) -> float:

        if not hasattr(self, "sl_corridor_manual_half"):
            return 0.0

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        return float(self.sl_corridor_manual_half.value()) / float(scale)

    def _set_corridor_manual_interval_preview(self, d_best: float, half_width_nm: float) -> None:

        hw = float(max(0.0, half_width_nm))

        self._corridor_rmse_manual_lo = float(d_best - hw)

        self._corridor_rmse_manual_hi = float(d_best + hw)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText(f"+/-{hw:.2f} nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText(
                f"Manual interval: [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
            )

    def _set_corridor_manual_bounds_labels(self, d_min: float, d_best: float, d_max: float) -> None:

        if hasattr(self, "lbl_corridor_manual_dmin"):
            self.lbl_corridor_manual_dmin.setText(f"d_min: {d_min:.2f} nm" if np.isfinite(d_min) else "d_min: -")

        if hasattr(self, "lbl_corridor_manual_dcenter"):
            self.lbl_corridor_manual_dcenter.setText(f"d*: {d_best:.2f} nm" if np.isfinite(d_best) else "d*: -")

        if hasattr(self, "lbl_corridor_manual_dmax"):
            self.lbl_corridor_manual_dmax.setText(f"d_max: {d_max:.2f} nm" if np.isfinite(d_max) else "d_max: -")

    def _corridor_manual_max_half_width_nm(self, d_s: np.ndarray) -> float:

        d_arr = np.asarray(d_s, dtype=np.float64).ravel()

        if d_arr.size == 0:
            return 0.0

        d_span = float(max(np.nanmax(d_arr) - np.nanmin(d_arr), 0.0)) if np.any(np.isfinite(d_arr)) else 0.0

        robust_half = 0.0

        if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
            robust_half = 0.5 * float(max(0.0, self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

        cur_half = self._corridor_manual_half_width_nm()

        step_half = float(np.nanmedian(np.abs(np.diff(d_arr)))) if d_arr.size >= 2 else 0.0

        return float(max(d_span, robust_half, cur_half, step_half, 0.0))

    def _reset_corridor_manual_controls(self) -> None:

        if hasattr(self, "sl_corridor_manual_half"):
            self.sl_corridor_manual_half.blockSignals(True)

            self.sl_corridor_manual_half.setRange(0, 1)

            self.sl_corridor_manual_half.setValue(0)

            self.sl_corridor_manual_half.setEnabled(False)

            self.sl_corridor_manual_half.blockSignals(False)

        if hasattr(self, "btn_generate_manual_corridor"):
            self.btn_generate_manual_corridor.setEnabled(False)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(False)

        if hasattr(self, "lbl_corridor_manual_half"):
            self.lbl_corridor_manual_half.setText("+/-0.00 nm")

        if hasattr(self, "lbl_corridor_manual_interval"):
            self.lbl_corridor_manual_interval.setText("Manual interval: -")

        self._set_corridor_manual_bounds_labels(float("nan"), float("nan"), float("nan"))

    def _on_corridor_manual_slider_changed(self, _value: int) -> None:

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            return

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = float(d_s[i_best])

        self._set_corridor_manual_interval_preview(d_center, self._corridor_manual_half_width_nm())

        src = self._corridor_profile_source_result()

        if src is not None:
            try:
                self._plot_corridor_rmse_tab(src)

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Manual corridor slider refresh failed", exc_info=True)

    def _manual_postprocess_seed_result(self) -> dict | None:

        base = getattr(self, "_last_worker_result", None)
        if isinstance(base, dict):
            return base
        base = getattr(self, "_last_result", None)
        if isinstance(base, dict):
            return base
        return None

    def _on_btn_manual_knots_clicked(self) -> None:

        seed = self._manual_postprocess_seed_result()
        if not isinstance(seed, dict):
            if self.logger:
                self.logger.info("Manual nodes: action requested but no base result is available.")
            QMessageBox.information(
                self,
                "Manual knots",
                "Run an optimization first to have a base result.",
            )
            return
        if not self._can_offer_manual_extra_knots(seed):
            QMessageBox.information(
                self,
                "Manual knots",
                "The current result does not allow adding more manual knots.",
            )
            return
        self._open_manual_extra_knots_dialog(seed)
