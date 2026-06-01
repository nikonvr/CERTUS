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
from certus.spline.certus_index_spline_corridors import (
    _CorridorWorkerMixin,
    _PlotMixin,
    _UIBuilderMixin,
    _CorridorExportMixin,
    _RunMixin,
    _DataMixin,
    _CorridorGenMixin,
    _SettingsMixin,
    _CorridorControlMixin
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
        # 1. On force d'abord le mode Log interne
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

@dataclass
class SplineState:
    result: dict | None

    d_lo: float

    d_hi: float

    wt: float

    wr: float

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

        # --- Profondeur de recherche (LOT E) ---
        row_ac3 = QHBoxLayout()
        row_ac3.addWidget(QLabel("Top-N candidats (auto-clean):"))
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

class _ConfigBuilderMixin:
    """Mixin extracting _build_opt_config logic."""



class _MeshOptimizationMixin:
    """Mixin extracting _build_basic_step4_mesh_optimizer logic."""

    def _build_basic_step4_mesh_optimizer(self, parent_layout: "QVBoxLayout", style: str) -> None:
        Step4MeshOptimizerBuilder(self, parent_layout, style).build()
    def _build_opt_config(self, *, notify: bool = True) -> SplineOptConfig | None:

        if self.df is None:
            if notify:
                QMessageBox.warning(self, "Data", "Load a file first.")

            return None

        sub_name = str(self.cb_sub.currentData() or self.cb_sub.currentText())

        sid = substrate_id_from_name(sub_name)

        lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        # Align ``SplineOptConfig.n_seg`` with the actual mesh (12 or 14 sigma knots) **before** any worker:

        # same rule as ``make_bounds_and_x0`` (IR extension if max(lambda) > 4000 nm), plus optional Deltalambda/lambda? min (Advanced).

        _mesh_mdl = float(self.sp_mesh_min_dlam.value()) if hasattr(self, "sp_mesh_min_dlam") else 0.02

        _kmd_mesh: dict[str, float] = {}

        if _mesh_mdl > 0.0:
            _kmd_mesh["min_delta_lambda_over_lambda_mean"] = _mesh_mdl

        k_mesh_sigma = int(canonical_spline_sigma_knots(float(np.min(lam)), float(np.max(lam)), **_kmd_mesh).size)

        n_seg_mesh = max(1, k_mesh_sigma - 1)

        try:
            n_sub = _get_substrate_n_array_spline(sid, lam)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            if notify:
                QMessageBox.critical(self, "Substrate", str(e))

            return None

        has_t = "T" in self.df.columns

        has_r = "R" in self.df.columns

        use_t = self.chk_t.isChecked() and has_t

        use_r = self.chk_r.isChecked() and has_r

        if not use_t and not use_r:
            if notify:
                QMessageBox.warning(self, "Fit", "Enable at least T or R according to available columns.")

            return None

        if use_t and use_r:
            dt = DataType.BOTH

        elif use_r:
            dt = DataType.REFLECTION

        else:
            dt = DataType.TRANSMISSION

        t_raw = self.df["T"].to_numpy(dtype=np.float64) if has_t else None

        r_raw = self.df["R"].to_numpy(dtype=np.float64) if has_r else None

        t_is_ratio = bool(self.chk_trel.isChecked())

        t_exp, r_exp = prepare_exp_TR_for_fit(lam, n_sub, t_raw, r_raw, t_is_ratio=t_is_ratio)

        overlay = gui_perf_preset_only(str(self.cb_profilee.currentData() or "fast"))

        # Build config is used outside the manual auto-clean dialog context,
        # so no dialog-scoped tolerance variable is guaranteed here.
        auto_clean_tol_ui = float(getattr(self, "_auto_clean_ui_tolerance", 5e-5) or 5e-5)

        rmse_fit_lambda_nm: tuple[float, float] | None = None

        if getattr(self, "_rmse_fit_lambda_enabled", False):
            rl0 = float(self._rmse_fit_lambda_lo)

            rl1 = float(self._rmse_fit_lambda_hi)

            rmse_fit_lambda_nm = (min(rl0, rl1), max(rl0, rl1))

        _n_mono_band = default_n_mono_band_nm_from_spectrum(lam)

        d_lo_ui, d_hi_ui = self._get_thickness_bounds_nm()


        cfg = SplineOptConfig(
            lam_nm=lam,
            t_exp=t_exp,
            r_exp=r_exp,
            n_sub=n_sub,
            data_type=dt,
            n_seg=int(n_seg_mesh),
            d_lo=float(d_lo_ui),
            d_hi=float(d_hi_ui),
            weight_t=float(self.w_t.value()) if use_t else 0.0,
            weight_r=float(self.w_r.value()) if use_r else 0.0,
            substrate_name=sub_name,
            t_is_ratio=t_is_ratio,
            pglobal_max_iter=0,
            polish_maxfun=int(overlay.get("polish_maxfun", 8000)),
            auto_clean_neighbor_pull_enabled=(
                bool(self.chk_auto_clean_neighbor_pull.isChecked())
                if hasattr(self, "chk_auto_clean_neighbor_pull")
                else True
            ),
            auto_clean_neighbor_pull_ratios=(
                tuple(
                    sorted(
                        {
                            float(self.sp_auto_clean_pull_r1.value()),
                            float(self.sp_auto_clean_pull_r2.value()),
                            float(self.sp_auto_clean_pull_r3.value()),
                        }
                    )
                )
                if (
                    hasattr(self, "sp_auto_clean_pull_r1")
                    and hasattr(self, "sp_auto_clean_pull_r2")
                    and hasattr(self, "sp_auto_clean_pull_r3")
                )
                else (0.10, 0.20, 0.30)
            ),
            auto_clean_neighbor_pull_local_refine_enabled=(
                bool(self.chk_auto_clean_neighbor_pull_local_refine.isChecked())
                if hasattr(self, "chk_auto_clean_neighbor_pull_local_refine")
                else False
            ),
            auto_clean_neighbor_pull_local_refine_rel_step=(
                float(self.sp_auto_clean_neighbor_pull_local_refine_step.value())
                if hasattr(self, "sp_auto_clean_neighbor_pull_local_refine_step")
                else 0.05
            ),
            # Fast-by-default advanced clean profile.
            auto_clean_top_n_sensitivity=(
                int(self.sp_auto_clean_top_n.value()) if hasattr(self, "sp_auto_clean_top_n") else 4
            ),
            auto_clean_candidate_prescreen_enabled=True,
            auto_clean_candidate_prescreen_maxfun=80,
            auto_clean_candidate_prescreen_margin_abs=max(5e-5, float(auto_clean_tol_ui) * 0.5),
            auto_clean_candidate_polish_maxfun=(
                int(self.sp_auto_clean_cand_maxfun.value()) if hasattr(self, "sp_auto_clean_cand_maxfun") else 700
            ),
            pglobal_max_feval=None,
            pglobal_max_time=None,
            pglobal_local_search_budget=None,
            pglobal_random_seed=(
                int(getattr(self, "sp_corr_seed", None).value())
                if hasattr(self, "sp_corr_seed") and int(getattr(self, "sp_corr_seed", None).value()) != 0
                else (
                    int(getattr(self, "sp_corr_boot_seed", None).value())
                    if hasattr(self, "sp_corr_boot_seed") and int(getattr(self, "sp_corr_boot_seed", None).value()) != 0
                    else None
                )
            ),
            spline_local_only=True,
            n_mono_band_nm=_n_mono_band,
            n_mono_continuous_penalty=0.008,
            n_lambda_rising_penalty_band_nm=_n_mono_band,
            n_lambda_rising_penalty_weight=3000.0,
            rmse_fit_lambda_nm=rmse_fit_lambda_nm,
            nk_profile_interp="smooth",
            corridor_profile_d_enabled=False,
            corridor_profile_d_mode=str(self.cb_corr_mode.currentData() or "abs_delta_adaptive")
            if hasattr(self, "cb_corr_mode")
            else "abs_delta_adaptive",
            corridor_profile_d_rmse_alpha=float(getattr(self, "sp_corr_alpha", None).value())
            if hasattr(self, "sp_corr_alpha")
            else 1.05,
            corridor_profile_d_rmse_abs_tolerance=float(getattr(self, "sp_corr_rmse_delta", None).value())
            if hasattr(self, "sp_corr_rmse_delta")
            else float(_DEFAULT_CORRIDOR_RMSE_DELTA),
            corridor_scientific_nominal_enabled=(
                not hasattr(self, "chk_corr_scientific_nominal") or bool(self.chk_corr_scientific_nominal.isChecked())
            ),
            corridor_profile_d_parabola_half_window_pts=int(
                getattr(self, "_corridor_parabola_half_window_pts", 4) or 4
            ),
            corridor_profile_d_symmetric_center_mode=str(
                getattr(self, "_corridor_symmetric_center_mode", "parabola") or "parabola"
            ),
            corridor_profile_d_adaptive_rmse_ref_half_width_nm=float(
                getattr(self, "_corridor_adaptive_rmse_ref_half_width_nm", 1.5) or 1.5
            ),
            corridor_profile_d_adaptive_rmse_probe_steps_each_side=int(
                getattr(self, "_corridor_adaptive_rmse_probe_steps_each_side", 3) or 3
            ),
            corridor_profile_d_adaptive_rmse_noise_factor=float(
                getattr(self, "_corridor_adaptive_rmse_noise_factor", 3.0) or 3.0
            ),
            corridor_profile_d_adaptive_rmse_min=float(
                getattr(self, "_corridor_adaptive_rmse_min", _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)
                or _DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN
            ),
            corridor_profile_d_step_nm=float(getattr(self, "sp_corr_step", None).value())
            if hasattr(self, "sp_corr_step")
            else 1.0,
            corridor_profile_d_max_span_nm=float(getattr(self, "sp_corr_span", None).value())
            if hasattr(self, "sp_corr_span")
            else 15.0,
            corridor_profile_d_polish_maxfun=(
                None
                if (hasattr(self, "sp_corr_prof_maxfun") and int(self.sp_corr_prof_maxfun.value()) <= 0)
                else int(self.sp_corr_prof_maxfun.value())
            )
            if hasattr(self, "sp_corr_prof_maxfun")
            else None,
            corridor_profile_d_lr_conf_level=float(getattr(self, "sp_corr_conf", None).value())
            if hasattr(self, "sp_corr_conf")
            else 0.95,
            corridor_profile_d_sigma_t=(
                None
                if (hasattr(self, "sp_corr_sigma") and float(self.sp_corr_sigma.value()) <= 0.0)
                else float(self.sp_corr_sigma.value())
            )
            if hasattr(self, "sp_corr_sigma")
            else None,
            corridor_profile_d_sigma_r=(
                None
                if (hasattr(self, "sp_corr_sigma") and float(self.sp_corr_sigma.value()) <= 0.0)
                else float(self.sp_corr_sigma.value())
            )
            if hasattr(self, "sp_corr_sigma")
            else None,
            corridor_profile_d_n_starts=int(getattr(self, "sp_corr_starts", None).value())
            if hasattr(self, "sp_corr_starts")
            else 1,
            corridor_profile_d_jitter_n=float(getattr(self, "sp_corr_jn", None).value())
            if hasattr(self, "sp_corr_jn")
            else 0.02,
            corridor_profile_d_jitter_L=float(getattr(self, "sp_corr_jL", None).value())
            if hasattr(self, "sp_corr_jL")
            else 0.15,
            corridor_profile_d_rng_seed=int(getattr(self, "sp_corr_seed", None).value())
            if hasattr(self, "sp_corr_seed")
            else 0,
            corridor_profile_d_sigma_hetero=bool(
                getattr(self, "chk_corr_sigma_hetero", None) and self.chk_corr_sigma_hetero.isChecked()
            )
            if hasattr(self, "chk_corr_sigma_hetero")
            else False,
            corridor_profile_d_sigma_hetero_scale=float(getattr(self, "sp_corr_hetero_scale", None).value())
            if hasattr(self, "sp_corr_hetero_scale")
            else 1.0,
            corridor_reg_sensitivity_enabled=bool(
                getattr(self, "chk_corr_reg_sens", None) and self.chk_corr_reg_sens.isChecked()
            ),
            corridor_reg_sensitivity_points=int(getattr(self, "sp_corr_reg_pts", None).value())
            if hasattr(self, "sp_corr_reg_pts")
            else 5,
            corridor_reg_sensitivity_decades=int(getattr(self, "sp_corr_reg_dec", None).value())
            if hasattr(self, "sp_corr_reg_dec")
            else 2,
            corridor_bootstrap_enabled=bool(getattr(self, "chk_corr_boot", None) and self.chk_corr_boot.isChecked()),
            corridor_bootstrap_n=int(getattr(self, "sp_corr_boot_n", None).value())
            if hasattr(self, "sp_corr_boot_n")
            else 40,
            corridor_bootstrap_seed=int(getattr(self, "sp_corr_boot_seed", None).value())
            if hasattr(self, "sp_corr_boot_seed")
            else 0,
            corridor_bootstrap_percentile=float(getattr(self, "sp_corr_boot_p", None).value())
            if hasattr(self, "sp_corr_boot_p")
            else 0.95,
            corridor_bootstrap_mode=str(getattr(self, "cb_corr_boot_mode", None).currentData() or "parametric")
            if hasattr(self, "cb_corr_boot_mode")
            else "parametric",
            corridor_bootstrap_block_len=int(getattr(self, "sp_corr_boot_block", None).value())
            if hasattr(self, "sp_corr_boot_block")
            else 1,
            corridor_bootstrap_quick_refit=bool(
                getattr(self, "chk_corr_boot_refit", None) and self.chk_corr_boot_refit.isChecked()
            )
            if hasattr(self, "chk_corr_boot_refit")
            else False,
            corridor_bootstrap_quick_refit_maxfun=int(getattr(self, "sp_corr_boot_maxfun", None).value())
            if hasattr(self, "sp_corr_boot_maxfun")
            else 4000,
            corridor_bootstrap_n_workers=int(getattr(self, "sp_corr_boot_workers", None).value())
            if hasattr(self, "sp_corr_boot_workers")
            else 1,
            spline_min_delta_lambda_over_lambda_mean=float(_mesh_mdl),
        )

        if rmse_fit_lambda_nm is not None:
            n_ok = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

            if n_ok < SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS:
                if notify:
                    QMessageBox.warning(
                        self,
                        "RMSE window",
                        f"Too few spectral points in the band ({n_ok} < {SPLINE_MIN_RMSE_FIT_OBJECTIVE_POINTS}). "
                        "Widen the window or disable the limit.",
                    )

                return None

        return cfg


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
                "[INDEX_SPLINE.SMART_INIT] dialog early return | cfg_present=%s | grids_present=%s | payload_k=%d | payload_d=%.6f",
                bool(self.cfg is not None),
                bool(self.grids is not None),
                int(np.asarray(self.sk, dtype=np.float64).size),
                float(getattr(payload, "d_best_nm", float("nan"))),
            )

            QMessageBox.warning(
                self.parent_worker,
                "Smart Init",
                "Incomplete preview data (cfg or grids). Aborting preview safely.",
            )

            raise ValueError("Incomplete preview data (cfg or grids)")

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
                "[INDEX_SPLINE.SMART_INIT] dialog early return | inconsistent_vectors len_n=%d len_l=%d k=%d",
                int(np.asarray(self.n_phys, dtype=np.float64).size),
                int(np.asarray(self.L_nodes, dtype=np.float64).size),
                int(self.k_n),
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
            logger.warning("[INDEX_SPLINE.SMART_INIT] lam_nm unavailable in payload and dataframe; spectrum plot will be empty")

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
            self.mon = LiveIndexMonitor(self.parent_worker)

            self.parent_worker._live_nk_monitor = self.mon

        self.mon._study_lam_window_fn = self._study_lambda_window_nm

        self.mon.show()

        # Positionner a droite du dialog de preview (si visible).

        try:
            self.mon.move(self.dlg.x() + self.dlg.width() + 10, self.dlg.y())

        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


        self.lbl_stats = QLabel()

        self.lbl_stats.setWordWrap(True)


        self.refresh_stats(self.state.preview_d_nm, rm0)

        # Colonnes alignees sous les sigma du plot (espacements  Deltasigma sur l'axe).

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
        _smart_init_apply_plot_range(
            self.pw, self._study_lambda_window_nm, self.cb_x_main.currentIndex(),
            getattr(self.parent_worker, "smart_preview_sk_arr", self.sk), self.lam_m, self.y_exp,
            self.state.current_t_th,
        )

    def refresh_nk_plots_aux(self, lam_nk: np.ndarray, n_lam: np.ndarray, k_lam: np.ndarray) -> None:
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

        knot_t = _interp_t_at_lam_knots(self.lam_m, self.state.current_t_th, cur_sk)

        self.knot_markers.setData(k_vals, knot_t)

        for j, il in enumerate(self.knot_lines):
            if j < len(k_vals):
                il.setPos(k_vals[j])

        self._apply_manual_spectrum_plot_range()

    def rebuild_knot_ui(self, new_kn: int) -> None:

        self.state.k_n = new_kn

        # Vidage du layout actuel

        while self.knot_h.count():
            item = self.knot_h.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_sk = getattr(self.parent_worker, "smart_preview_sk_arr", self.sk_arr)
        sig2_sorted_loc = np.sort(current_sk**2)

        self.redraw_knot_lines()

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

class _SmartInitDialogMixin:
    """Mixin extracting _show_smart_init_preview_dialog logic."""

    def _show_smart_init_preview_dialog(self, payload) -> bool:
        logger.info(
            "[INDEX_SPLINE.SMART_INIT] show requested | payload_type=%s | payload_d=%.6f | wait_event=%s",
            type(payload).__name__,
            float(getattr(payload, "d_best_nm", float("nan"))),
            getattr(self, "_preview_wait_event", None) is not None,
        )
        try:
            manager = SmartInitPreviewManager(self, payload)
            code = manager.dlg.exec()
            accepted = bool(code == QDialog.DialogCode.Accepted)
            logger.info(
                "[INDEX_SPLINE.SMART_INIT] exec done | code=%s | accepted=%s | preview_ret=%s",
                int(code),
                accepted,
                getattr(self, "_preview_ret", None) is not None,
            )
            return accepted and bool(getattr(self, "_preview_result", False))
        except Exception:
            logger.exception("[INDEX_SPLINE.SMART_INIT] dialog failed to open; aborting preview stage safely")
            return False

    def _build_smart_init_aux_dialog(
        self, parent_dlg: QDialog
    ) -> tuple[QDialog, pg.PlotCurveItem, pg.PlotCurveItem, Any, Any]:
        """Extracted from _show_smart_init_preview_dialog: builds the auxiliary n(lambda) / ln k(lambda) profile dialog."""

        aux_dlg = QDialog(parent_dlg)

        aux_dlg.setWindowTitle("Optical Profiles  n(lambda) and ln k(lambda)")

        aux_dlg.setMinimumWidth(500)

        aux_dlg.setMinimumHeight(500)

        aux_lay = QVBoxLayout(aux_dlg)

        pw_nk = CertusScientificPlot()

        pw_nk.showGrid(x=True, y=True, alpha=0.3)

        pw_nk.setLabel("bottom", "lambda (nm)")

        pw_nk.addLegend()

        attach_excel_clipboard_context_menu(pw_nk)

        aux_lay.addWidget(wrap_scientific_plot_with_toolbar(aux_dlg, pw_nk))

        # Curves for n and ln k
        curve_n = pg.PlotCurveItem(
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2), name="n(lambda)"
        )
        pw_nk.addItem(curve_n)

        # Axe Y secondaire pour ln k

        main_vb = pw_nk.plotItem.vb

        p_extra = pg.ViewBox()

        pw_nk.scene().addItem(p_extra)

        pw_nk.getAxis("right").linkToView(p_extra)

        p_extra.setXLink(main_vb)

        curve_pk = pg.PlotCurveItem(
            pen=pg.mkPen(CertusTheme.ACCENT, width=2, style=Qt.PenStyle.DashLine), name="ln k(lambda)"
        )

        # Clipboard / CSV export: always k, never ln k (see certus_ui _export_y_values_for_item).

        curve_pk._certus_export_y_as_exp_k = True

        curve_pk._certus_export_name_override = "k"

        p_extra.addItem(curve_pk)

        pw_nk._certus_clipboard_df_provider = lambda: _smart_init_pw_nk_clipboard_df(curve_n, curve_pk)

        def update_aux_layout() -> None:

            p_extra.setGeometry(main_vb.sceneBoundingRect())

        main_vb.sigResized.connect(update_aux_layout)

        return aux_dlg, curve_n, curve_pk, main_vb, p_extra

    def _build_smart_init_main_plot(
        self, y_lab: str
    ) -> tuple[CertusScientificPlot, pg.PlotDataItem, pg.PlotDataItem, pg.PlotDataItem]:
        """Extracted from _show_smart_init_preview_dialog: builds the main measurement vs theory plot."""

        pw = CertusScientificPlot()

        pw.setMinimumHeight(300)

        pw.showGrid(x=True, y=True, alpha=0.35)

        pw.setLabel("bottom", "sigma2 = 1/lambda2 (nm?2)")

        pw.setLabel("left", y_lab)

        pw.addLegend()

        curve_exp = pw.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=5,
            symbolBrush=pg.mkBrush(CertusTheme.ACCENT),
            name="Measurement",
        )

        curve_theo = pw.plot(
            [],
            [],
            pen=pg.mkPen(CertusTheme.PRIMARY, width=2.5),
            name="Theoretical (PWL n, ln k | d = slider)",
        )

        knot_markers = pw.plot(
            [],
            [],
            pen=None,
            symbol="s",
            symbolSize=9,
            symbolBrush=pg.mkBrush("#c97800"),
            name="T at knots",
        )

        return pw, curve_exp, curve_theo, knot_markers

    def _on_progress(self, v: int, msg: str) -> None:
        raw = int(v)
        if raw < 0:
            if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
                if msg:
                    self._manual_knots_dialog.append_runtime_log(msg)
            return
        if raw < self._prog_ui_last:
            return
        self._prog_ui_last = raw

        st = msg
        # Surface a 0.1 nm thickness hint in live status without replacing
        # the existing detailed values emitted by workers.
        d_hint = float("nan")
        live_best = getattr(self, "_best_live_result", None)
        if isinstance(live_best, dict):
            try:
                d_hint = float(live_best.get("d_nm", float("nan")))
            except (TypeError, ValueError):
                d_hint = float("nan")
        if not np.isfinite(d_hint):
            last_res = getattr(self, "_last_result", None)
            if isinstance(last_res, dict):
                try:
                    d_hint = float(last_res.get("d_nm", float("nan")))
                except (TypeError, ValueError):
                    d_hint = float("nan")
        if np.isfinite(d_hint):
            st = f"{st} | d(0.1nm)~{float(d_hint):.1f} nm"
        if np.isfinite(self._best_live_rmse) and self._best_live_rmse < 1e90:
            st = f"{msg} | best displayed RMSE={self._best_live_rmse:.6f}"
            if np.isfinite(d_hint):
                st = f"{st} | d(0.1nm)~{float(d_hint):.1f} nm"
        self.lbl_status.setText(st)

        # Update the main progress bar smoothly via EnhancedProgressWidget
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                raw,
                10000,
                0,
                msg,
                "",
                animate=(str(getattr(self, "_worker_role", "") or "") != "manual_auto_clean"),
            )

        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            pct = float(raw) / 100.0
            self._manual_knots_dialog.set_runtime_progress(pct, msg)
            if msg:
                self._manual_knots_dialog.append_runtime_log(msg)

        if self.logger and (raw <= 800 or raw >= 9800 or raw >= self._log_prog_last + 700 or self._log_prog_last < 0):
            self._log_prog_last = raw

    def _display_result_prefer_best_live(self, result: dict) -> dict:
        """

        If a live snapshot recorded strictly better RMSE than the worker?s final dict,

        merge: plots / Data / Excel use that best snapshot while keeping metadata

        present only in the final result (keys missing from live).

        """

        rmse_fin = self._rmse_from_result_dict(result)

        live = self._best_live_result

        if live is None or not isinstance(live, dict):
            return result

        rmse_live = self._rmse_from_result_dict(live)

        if not (np.isfinite(rmse_live) and np.isfinite(rmse_fin)):
            return result

        tol = max(1e-12, 1e-10 * max(abs(rmse_fin), 1.0))

        if rmse_live + tol >= rmse_fin:
            return result

        snap = _snap_spline_visual_dict(live)

        merged = dict(result)

        for k, v in snap.items():
            merged[k] = v

        self._strip_worker_final_fields_inconsistent_with_live_merge(merged)

        merged["gui_display_from_best_live"] = True

        merged["gui_worker_raw_rmse"] = float(rmse_fin)

        merged["gui_best_live_rmse"] = float(rmse_live)

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: spectrum / indices / Data / export aligned on the **best** live "
                "snapshot (RMSE=%.8f) - final worker dict had RMSE=%.8f. "
                "Removing inconsistent keys (corridors, bootstrap, reg_sens, polish spline sigma variants, "
                "spectral_rmse_*, residual ln_k_lam).",
                rmse_live,
                rmse_fin,
            )

        return merged

    def _smart_init_preview_hook(self, payload: dict | SmartInitPayload) -> bool:

        if isinstance(payload, dict):
            payload = SmartInitPayload.from_dict(payload)

        """Called from the worker (QThread) after n_init/L_init logs; UI must run on the GUI thread."""

        app = QApplication.instance()

        logger.info(
            "Smart Init hook enter | payload_type=%s | app_present=%s | gui_thread=%s | current_is_gui=%s",
            type(payload).__name__,
            bool(app is not None),
            type(app.thread()).__name__ if app is not None else "n/a",
            bool(app is not None and QThread.currentThread() == app.thread()),
        )

        if app is None:
            logger.error("Smart Init hook: QApplication missing, cannot pause safely.")
            return False

        self._preview_ret = None

        if QThread.currentThread() == app.thread():
            logger.info("Smart Init hook: already on GUI thread -> direct dialog call")

            return self._show_smart_init_preview_dialog(payload)

        # Thread worker -> GUI: demander explicitement la preview via signal Qt.

        self._preview_payload = payload

        self._preview_result = False

        self._preview_wait_event = Event()

        logger.info(
            "Smart Init hook: emitting smart_preview_requested | payload_type=%s | has_wait_event=%s",
            type(payload).__name__,
            self._preview_wait_event is not None,
        )

        self.smart_preview_requested.emit(payload)

        # Augmentation du timeout a 10 minutes (600s) pour laisser le temps du tuning manual

        ok = self._preview_wait_event.wait(timeout=600.0)

        logger.info(
            "Smart Init hook: wait finished | ok=%s | preview_result=%s | has_preview_ret=%s",
            bool(ok),
            bool(getattr(self, "_preview_result", True)),
            getattr(self, "_preview_ret", None) is not None,
        )

        # Securite PyQt : rapatrier l'etat mute depuis le thread principal via variable d'instance.

        ret_tuple = getattr(self, "_preview_ret", None)

        if ret_tuple is not None:
            logger.info("Smart Init hook: preview returned manual values to worker")

            cfg = payload.cfg

            if cfg is not None:
                sk, ne, Le, d_nm, rmse = ret_tuple

                cfg.smart_preview_exact_sigma_knots = sk

                cfg.smart_preview_exact_n_L = (ne, Le)

                cfg.smart_preview_d_nm_override = d_nm

                cfg.smart_preview_accepted_rmse = rmse

                # Signal to the calculation engine that a manual injection is available

                cfg.smart_init_manual_force_restart = True

            self._preview_ret = None

        if not ok:
            logger.error("Smart Init preview: GUI timeout (600s), aborting optimization safely.")
            return False

        if ret_tuple is not None:
            return True

        return bool(getattr(self, "_preview_result", False))










class _UIMixin:
    """UI Area."""

class CertusIndexSplineApp(
    _CorridorControlMixin,
    _SettingsMixin,
    _CorridorGenMixin,
    _DataMixin,
    _RunMixin,
    _CorridorExportMixin,
    _UIBuilderMixin,
    _PlotMixin,
    _CorridorWorkerMixin,
    _SmartInitDialogMixin,
    _ConfigBuilderMixin,
    _MeshOptimizationMixin,
    _ExcelExportMixin,
    _UIMixin,
    CertusBaseApp,
):
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

    def closeEvent(self, event) -> None:
        """Stop cooperative workers before teardown to avoid Qt ``QThread: Destroyed while still running``.

        Mirrors CERTUS_DESIGN / METAL shutdown pattern: threading ``Event`` first, then QThread.wait.
        """
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
    def _sorted_finite_sigma_knots(sigma_knots: Any) -> np.ndarray:
        return _sorted_finite_sigma_knots_impl(sigma_knots)

    @staticmethod
    def _sigma_knots_to_lambda_nm(sigma_knots: Any) -> np.ndarray:

        sig = CertusIndexSplineApp._sorted_finite_sigma_knots(sigma_knots)

        if sig.size == 0:
            return np.empty(0, dtype=np.float64)

        return np.sort(1.0 / np.maximum(sig, 1e-30))

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
            # NaN = signal "lire la valeur depuis le widget GUI".
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
        """True si ``r`` est le dict final du worker grille RMSE(d) (pas un r?sultat solveur complet)."""
        if not isinstance(r, dict):
            return False
        st = str(r.get("profile_d_status", ""))
        return st in {"manual_grid", "manual_grid_empty"}

    def _merge_rmse_grid_promotion_into_nominal(self, promoted: dict, *, adoption_log_tag: str) -> None:
        """Fusionne un dict promu (global-opt ou minimum grille) dans ``_last_result`` et rafra?chit l UI."""
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

    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None:
        """D?marre le worker de comblement de trous apr?s la grille, hors handler ``finished`` (?vite ``_cleanup_thread``)."""
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

    APP_NAME = "CERTUS-INDEX-SPLINE"

    APP_TITLE = "Indices PWL (sigma) - Local optimization"

    DEFAULT_WIDTH = 1280

    DEFAULT_HEIGHT = 720

    MIN_WIDTH = 960

    MIN_HEIGHT = 560

    _LIVE_LOG_REMINDER_S = 12.0

    # Anti-spam for live "[BEST RMSE  new record]" lines during long L-BFGS-B polish.
    _LIVE_BEST_DETAIL_MIN_ABS = 5.0e-6
    _LIVE_BEST_DETAIL_MIN_REL = 2.0e-4
    _LIVE_BEST_DETAIL_MIN_INTERVAL_S = 4.0

    smart_preview_requested = pyqtSignal(object)

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

    def __init__(self) -> None:

        super().__init__()

        self._setup_logger(self.APP_NAME)

        self._log_prog_last: int = -1

        self._prog_ui_last: int = 0

        self._last_live_log_mono: float = 0.0

        self._live_best_detail_log_mono: float = 0.0

        self.df: pd.DataFrame | None = None

        self._worker: GenericWorker | None = None

        self._stop_event = Event()

        self._last_result: dict | None = None

        self._last_worker_result: dict | None = None

        self._corridor_rmse_base_snapshot: dict | None = None

        self._last_run_cfg: SplineOptConfig | None = None

        self._worker_role: str = "idle"

        self._best_live_rmse: float = float("inf")

        self._best_live_result: dict | None = None

        self._corridor_rmse_manual_active: bool = False

        self._corridor_rmse_manual_lo: float = float("nan")

        self._corridor_rmse_manual_hi: float = float("nan")

        self._corridor_rmse_manual_slider_scale: int = 100

        self._last_spectrum_path: str = ""

        self._pending_auto_best_adaptive: dict[str, Any] | None = None

        self._auto_best_local_warm: dict[str, Any] | None = None

        self._auto_best_force_smart_init: bool = False

        self._auto_best_two_stage_refine: bool = False

        self._auto_best_second_stage_pending: dict[str, Any] | None = None
        self._corridor_auto_refine_plan: dict[str, Any] | None = None

        self._preview_wait_event: Event | None = None

        self._rmse_fit_lambda_enabled: bool = SIO2_DEFAULT_RMSE_FIT_LAMBDA_ENABLED

        self._rmse_fit_lambda_lo: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM

        self._rmse_fit_lambda_hi: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM

        self._rmse_fit_lambda_lo_default: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_LO_NM

        self._rmse_fit_lambda_hi_default: float = SIO2_DEFAULT_RMSE_FIT_LAMBDA_HI_NM

        self._rmse_fit_overlay_items: list[Any] = []

        self._simple_auto_uncertainty: bool = True

        self._build_ui()

        install_standard_shortcuts(
            self,
            save=getattr(self, "save_config", None),
            load=lambda: self._on_load(),
            export=getattr(self, "export_excel", None),
            run=getattr(self, "_on_run", None),
            stop=getattr(self, "_on_stop", None),
            help=lambda: open_documentation("CERTUS_INDEX_SPLINE"),
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
        )

        def _on_spectrum_drop(paths) -> None:
            if paths:
                self._on_load(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_spectrum_drop, extensions=("csv", "xlsx", "xls", "txt"))

        self._restore_simple_auto_uncertainty_pref()

        self._restore_spectrum_fit_settings()

        self._restore_splitter_states()

        self._maybe_apply_uncertainty_defaults_migrated()

        self._refresh_corridors_gui_state_labels()

        self._update_epured_visibility()

        self._wire_spectrum_fit_settings_persistence()

        self._persist_spectrum_fit_settings()

        self.smart_preview_requested.connect(self._on_smart_preview_requested)

        apply_certus_theme(
            self,
            overrides=f"""
            {build_premium_overrides()}
            """,
            plots=[
                self.plot_T,
                self.plot_n,
                self.plot_k,
                self.plot_n_corridor,
                self.plot_k_corridor,
                self.plot_corridor_rmse_d,
            ],
        )

        self._finalize_init()

    def _load_defaults(self) -> None:

        self.df = None

        self._last_result = None

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

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
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

        if hasattr(self, "lbl_corridor_rmse_summary"):
            self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
        if hasattr(self, "lbl_corridor_rmse_robust_compact"):
            self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        self._refresh_data_table()

        self._persist_spectrum_fit_settings()

        self._refresh_corridors_gui_state_labels()

    def _persist_spectrum_fit_settings(self) -> None:
        """Saves step 3 to QSettings (read at next launch)."""

        if not hasattr(self, "chk_t"):
            return

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        s.setValue(_QS_SPECTRUM_FIT_T, self.chk_t.isChecked())

        s.setValue(_QS_SPECTRUM_FIT_TREL, self.chk_trel.isChecked())

        s.setValue(_QS_SPECTRUM_FIT_R, self.chk_r.isChecked())

        s.setValue(_QS_SPECTRUM_WT, float(self.w_t.value()))

        s.setValue(_QS_SPECTRUM_WR, float(self.w_r.value()))

        s.setValue(_QS_NK_PROFILE_INTERP, "smooth")

    def _wire_spectrum_fit_settings_persistence(self) -> None:

        self.chk_t.toggled.connect(self._persist_spectrum_fit_settings)

        self.chk_trel.toggled.connect(self._persist_spectrum_fit_settings)

        self.chk_r.toggled.connect(self._persist_spectrum_fit_settings)

        self.w_t.valueChanged.connect(self._persist_spectrum_fit_settings)

        self.w_r.valueChanged.connect(self._persist_spectrum_fit_settings)

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
        """Cr?e une page d attente/info pour le panneau de r?glages contextuels."""
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
        """Formate l affichage du curseur pour les ?chelles logarithmiques de k."""
        # Priorit? ? la valeur interpol?e sur la courbe (d?j? en k physique dans nos trac?s).
        y_val = y_on_curve if y_on_curve is not None else y_mouse
        k_val = float("nan")
        if y_val is not None and np.isfinite(float(y_val)):
            y_num = float(y_val)
            # Compat: si une coordonn?e log10 est fournie (<=0), on reconvertit.
            k_val = y_num if y_num > 0.0 else float(10.0**y_num)
        if not np.isfinite(k_val):
            return f"x = {x:.2f}, k = n/a"
        return f"x = {x:.2f}, k = {k_val:.3e}"

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


    def _build_controls_basic_panel(self) -> QWidget:
        """Steps 2 to 4: substrate / thickness, spectral targets, mesh and optimizer."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(6)
        gst = self._control_group_box_style()
        hint = QLabel("Order: 2 → 3 → 4")
        hint.setWordWrap(False)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        v.addWidget(hint)
        self._build_basic_step2_substrate_thickness(v, gst)
        self._build_basic_step3_spectral_targets(v, gst)
        self._build_basic_step4_mesh_optimizer(v, gst)
        return w

    def _build_tab_spectrum(self) -> QWidget:
        # Les contr?les sont d?plac?s dans le context_stack ? droite
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

    def _build_tab_indices(self) -> QWidget:
        # Page vide pour la synchro du context_stack
        self._add_context_page(
            self._create_empty_context_widget("Standard refractive index plots.\nNo specific settings for this tab.")
        )

        panel = QWidget()
        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_n = CertusScientificPlot(title="n(lambda)", y_label="n", x_label="lambda (nm)")

        self.plot_n.showGrid(x=True, y=True, alpha=0.25)

        self.plot_k = CertusScientificPlot(title="k(lambda)", y_label="k", x_label="lambda (nm)")

        self.plot_k.showGrid(x=True, y=True, alpha=0.25)

        _apply_fixed_log_k_axis(self.plot_k)
        self.plot_k._certus_crosshair_label_fn = self._k_crosshair_formatter

        spl = QSplitter(Qt.Orientation.Vertical)

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_n))

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_k))

        spl.setStretchFactor(0, 1)

        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        return panel

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
            self.pb_corridor_rmse_grid.setValue(1000)

            self.pb_corridor_rmse_grid.setEnabled(True)

            self.pb_corridor_rmse_grid.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {CertusTheme.SUCCESS}; }}"
            )

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
        """Fixe l ?chelle du graphe RMSE(d) sur les bornes min/max des donn?es."""

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

    def _build_tab_log(self) -> QWidget:

        w = QWidget()

        lay = QVBoxLayout(w)

        lay.setContentsMargins(12, 12, 12, 12)

        info = QLabel(
            "The detailed stream (local stages, K stages, polish, continuous laws) appears in the "
            "<b>OPTIMIZATION LOG</b> panel under the plots. "
            "Use <b>Copy Logs</b> on that panel to copy all text."
        )

        info.setWordWrap(True)

        info.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(info)

        lay.addStretch(1)

        return w

    def _build_tab_why(self) -> QWidget:

        panel = QWidget()

        grid = QGridLayout(panel)

        grid.setSpacing(16)

        grid.setContentsMargins(24, 24, 24, 24)

        intro = QLabel(
            "<b>CERTUS-INDEX-SPLINE.</b> Global fit of "
            "<i>n(lambda)</i>, <i>k(lambda)</i> as piecewise-linear in sigma=1/lambda (ln k at knots), "
            "with <b>local L-BFGS-B</b> polish. Advanced mode: catalog of continuous laws "
            "on normalized <i>u</i> and 19-D re-optimization if spectral RMSE improves."
        )

        intro.setWordWrap(True)

        intro.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        grid.addWidget(intro, 0, 0, 1, 2)

        cards = [
            ("Local L-BFGS-B", "Local optimization with tunable budgets.", ""),
            ("Spectral weights Deltaln lambda", "RMSE weighted trapezoidal rule on ln lambda grid (no cap).", ""),
            ("Auto-K and adaptive mesh", "K growth or SMART-style sigma insertions; warm start.", ""),
            ("Continuous laws (advanced)", "Rank n(u), ln k(u) families then optimize d + 18 parameters.", ""),
        ]

        for i, (title, desc, icon) in enumerate(cards):
            grid.addWidget(FlashyCard(title, desc, icon=icon), 1 + i // 2, i % 2)

        return panel

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

    def _spectrum_open_dialog_start_path(self) -> str:
        """Dernier file spectrum (pre-selection Qt) sinon last dossier suite, sinon script."""

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        last_file = str(s.value(_QS_LAST_SPECTRUM, "") or "").strip()

        if last_file and Path(last_file).is_file():
            return last_file

        d = get_certus_last_dir()

        if d and Path(d).is_dir():
            return d

        return str(_SCRIPT_DIR)

    def _persist_last_spectrum_path(self, path: str) -> None:

        ap = str(Path(path).resolve(strict=False))

        self._last_spectrum_path = ap

        set_certus_last_dir(ap)

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(_QS_LAST_SPECTRUM, ap)

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
        # UX: Si on affiche k sur une ?chelle LOG, on lin?arise les donn?es log10 fournies
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

    def _spectrum_clear_theory_probe(self) -> None:
        """Clears the n,k,T (R) grid aligned on the last model trace (spectrum context menu)."""
        self._spectrum_theory_probe_lam_nm = None
        self._spectrum_theory_probe_n = None
        self._spectrum_theory_probe_k = None
        self._spectrum_theory_probe_tt = None
        self._spectrum_theory_probe_rt = None
        self._spectrum_theory_probe_d_nm = None

    def _spectrum_x_axis_mode_current(self) -> str:
        cb = getattr(self, "cb_spectrum_xmode", None)
        if cb is None:
            return "lambda"
        d = cb.currentData()
        return str(d) if d is not None else "lambda"

    def _spectrum_view_abscissa_to_lambda_nm(self, x_view: float) -> float | None:
        """Inverse of _transform_spectrum_x: displayed abscissa -> lambda (nm)."""
        if not np.isfinite(x_view):
            return None
        mode = self._spectrum_x_axis_mode_current()
        xv = float(x_view)
        if mode == "lambda":
            return xv if xv > 0.0 else None
        if mode == "sigma":
            return (1.0 / xv) if xv > 0.0 else None
        if mode == "sigma2":
            return (1.0 / np.sqrt(xv)) if xv > 0.0 else None
        return xv if xv > 0.0 else None

    def _spectrum_theory_interp_at_lambda_nm(self, lam_nm_query: float) -> dict[str, Any]:
        """Linear interpolation of model quantities on the grid used for theoretical T/R."""

        lg0 = getattr(self, "_spectrum_theory_probe_lam_nm", None)

        def _missing_why() -> dict[str, Any]:
            return {"ok": False, "reason": "no_data"}

        if lg0 is None:
            return _missing_why()

        n0 = getattr(self, "_spectrum_theory_probe_n", None)

        k0 = getattr(self, "_spectrum_theory_probe_k", None)

        t0 = getattr(self, "_spectrum_theory_probe_tt", None)

        if n0 is None or k0 is None or t0 is None:
            return _missing_why()

        lg = np.asarray(lg0, dtype=np.float64).ravel()

        nn = np.asarray(n0, dtype=np.float64).ravel()

        kk = np.asarray(k0, dtype=np.float64).ravel()

        tt = np.asarray(t0, dtype=np.float64).ravel()

        rt_arr = getattr(self, "_spectrum_theory_probe_rt", None)

        rr = np.asarray(rt_arr, dtype=np.float64).ravel() if rt_arr is not None else None

        m = np.isfinite(lg) & np.isfinite(nn) & np.isfinite(kk) & np.isfinite(tt)

        if rr is not None and rr.shape == lg.shape:
            m = m & np.isfinite(rr)

        elif rr is not None:
            rr = None

        if not np.any(m):
            return {"ok": False, "reason": "no_finite_points"}

        lam_use = lg[m]

        order = np.argsort(lam_use, kind="mergesort")

        xs = lam_use[order]

        if xs.size < 1:
            return {"ok": False, "reason": "no_finite_points"}

        lo, hi = float(xs[0]), float(xs[-1])

        lam_q = float(lam_nm_query)

        span = hi - lo

        tol = max(1e-9 * span, 1e-12)

        if lam_q < lo - tol or lam_q > hi + tol:
            out: dict[str, Any] = {
                "ok": False,
                "reason": "outside",
                "lambda_lo_nm": lo,
                "lambda_hi_nm": hi,
                "lambda_nm": lam_q,
                "d_nm": getattr(self, "_spectrum_theory_probe_d_nm", float("nan")),
            }

            return out

        nn_s = nn[m][order]

        kk_s = kk[m][order]

        tt_s = tt[m][order]

        out_ok: dict[str, Any] = {
            "ok": True,
            "lambda_nm": lam_q,
            "n": float(np.interp(lam_q, xs, nn_s)),
            "k": float(np.interp(lam_q, xs, kk_s)),
            "t_model": float(np.interp(lam_q, xs, tt_s)),
            "d_nm": getattr(self, "_spectrum_theory_probe_d_nm", float("nan")),
        }

        if rr is not None:
            rr_use = rr[m][order]

            out_ok["r_model"] = float(np.interp(lam_q, xs, rr_use))

        else:
            out_ok["r_model"] = None

        return out_ok

    def _spectrum_probe_d_nm_crosshair_txt(self) -> str:
        d_nm = getattr(self, "_spectrum_theory_probe_d_nm", None)
        if d_nm is not None and np.isfinite(float(d_nm)):
            return f"{float(d_nm):.2f} nm"
        return "—"

    def _spectrum_T_crosshair_formatter(self, x_view: float, y_show: float | None, y_raw: float) -> str:
        """Spectrum tooltip: lambda, n, k, d (model grid) + tracked ordinate on the curve."""
        yt = (
            float(y_show)
            if y_show is not None and np.isfinite(float(y_show))
            else float(y_raw if np.isfinite(float(y_raw)) else float("nan"))
        )
        y_bit = f"y ≈ {yt:.6g}" if np.isfinite(yt) else "y = —"
        d_txt = self._spectrum_probe_d_nm_crosshair_txt()
        lam_hint = self._spectrum_view_abscissa_to_lambda_nm(float(x_view))
        if lam_hint is None:
            return f"x = {float(x_view):.5g}  |  {y_bit}  |  λ n k —  |  d = {d_txt}"

        lg0 = getattr(self, "_spectrum_theory_probe_lam_nm", None)
        if lg0 is None:
            return f"λ (indic.) = {float(lam_hint):.4f} nm  |  {y_bit}  |  n k: no model  |  d = {d_txt}"

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam_hint))
        if not res.get("ok"):
            if str(res.get("reason", "")) == "outside":
                lq = float(res.get("lambda_nm", lam_hint))
                lo = float(res.get("lambda_lo_nm", float("nan")))
                hi = float(res.get("lambda_hi_nm", float("nan")))
                return f"λ = {lq:.4f} nm  (outside grid [{lo:.1f}–{hi:.1f}] nm)\nn = —    k = —    d = {d_txt}\n{y_bit}"
            return f"λ = {float(lam_hint):.4f} nm  |  n = —  k = —  |  d = {d_txt}  |  {y_bit}"

        ln = float(res["lambda_nm"])
        return f"λ = {ln:.4f} nm    n = {float(res['n']):.5f}    k = {float(res['k']):.4e}    d = {d_txt}\n{y_bit}"

    def _spectrum_plot_context_menu_augment(
        self,
        plot: Any,
        menu: Any,
        widget_pos: Any,
        view_x: float,
        view_y: float,
    ) -> None:
        if plot is not getattr(self, "plot_T", None):
            return

        if getattr(self, "_spectrum_theory_probe_lam_nm", None) is None:
            return

        act_show = menu.addAction("Show n, k, T (model) at clicked point…")

        act_show.triggered.connect(lambda *_, vx=view_x, vy=view_y: self._spectrum_show_theory_probe_dialog(vx, vy))

        act_copy = menu.addAction("Copy λ, n, k, d, T (R) model at point — TSV")

        act_copy.triggered.connect(lambda *_, vx=view_x, vy=view_y: self._spectrum_copy_theory_probe_tsv(vx, vy))

    def _spectrum_show_theory_probe_dialog(self, view_x: float, view_y: float) -> None:

        lam = self._spectrum_view_abscissa_to_lambda_nm(view_x)

        if lam is None:
            QMessageBox.information(
                self,
                "Spectrum",
                "Invalid click abscissa (λ ≤ 0 or coordinate not convertible to wavelength).",
            )

            return

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam))

        if not res.get("ok"):
            rsn = str(res.get("reason", ""))

            if rsn == "outside":
                d_o = res.get("d_nm")

                d_line = f"\nd displayed = {float(d_o):.4f} nm" if d_o is not None and np.isfinite(float(d_o)) else ""

                QMessageBox.information(
                    self,
                    "Spectrum",
                    (
                        f"λ = {res.get('lambda_nm', float('nan')):.4f} nm is outside model grid "
                        f"[{res.get('lambda_lo_nm', float('nan')):.4f} ; "
                        f"{res.get('lambda_hi_nm', float('nan')):.4f}] nm.\n"
                        "n, k, T values are interpolated only on this grid."
                        f"{d_line}"
                    ),
                )

            else:
                QMessageBox.information(
                    self,
                    "Spectrum",
                    "No n,k,T model grid available for this plot. Load a fit result or plot the model spectrum.",
                )

            return

        lines = [
            f"λ = {float(res['lambda_nm']):.6f} nm",
            f"n = {float(res['n']):.8f}",
            f"k = {float(res['k']):.6e}",
        ]

        d_nm = res.get("d_nm")

        if d_nm is not None and np.isfinite(float(d_nm)):
            lines.append(f"d = {float(d_nm):.4f} nm")

        else:
            lines.append("d = (undefined)")

        lines.append(f"T (model) = {float(res['t_model']):.8f}")
        rr = res.get("r_model")
        if rr is not None and np.isfinite(float(rr)):
            lines.append(f"R (model) = {float(rr):.8f}")

        xm = self._spectrum_x_axis_mode_current()

        lines.append("")

        lines.append(f"Abscissa mode : {xm} | x_view = {view_x:.8g} | y_view ≈ {view_y:.8g}")

        QMessageBox.information(self, "Model at point (spectrum)", "\n".join(lines))

    def _spectrum_copy_theory_probe_tsv(self, view_x: float, view_y: float) -> None:

        lam = self._spectrum_view_abscissa_to_lambda_nm(view_x)

        if lam is None:
            QMessageBox.information(
                self,
                "Spectrum",
                "Invalid click abscissa; nothing to copy.",
            )

            return

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam))

        if not res.get("ok"):
            rsn = str(res.get("reason", ""))

            if rsn == "outside":
                QMessageBox.information(
                    self,
                    "Spectrum",
                    'λ outside model grid: copy cancelled (see "Display n, k...").',
                )

            else:
                QMessageBox.information(self, "Spectrum", "No model data to copy.")

            return

        d_cell = f"{float(res['d_nm']):.10g}" if res.get("d_nm") is not None and np.isfinite(float(res["d_nm"])) else ""

        hdr = "lambda_nm\tn\tk\td_nm\tt_model"

        row = f"{float(res['lambda_nm']):.10g}\t{float(res['n']):.10g}\t{float(res['k']):.10g}\t{d_cell}\t{float(res['t_model']):.10g}"

        rr = res.get("r_model")

        if rr is not None and np.isfinite(float(rr)):
            row += f"\t{float(rr):.10g}"

            hdr += "\tr_model"

        QApplication.clipboard().setText(hdr + "\n" + row + "\n")

        QMessageBox.information(self, "Spectrum", "A TSV line (header + values) was copied.")

    def _transform_spectrum_x(self, lam_nm: np.ndarray) -> tuple[np.ndarray, str]:

        mode = str(
            getattr(self, "cb_spectrum_xmode", None).currentData() if hasattr(self, "cb_spectrum_xmode") else "lambda"
        )

        lam = np.asarray(lam_nm, dtype=np.float64).ravel()

        if mode == "sigma":
            return 1.0 / np.maximum(lam, 1e-30), "sigma (nm?1)"

        if mode == "sigma2":
            s = 1.0 / np.maximum(lam, 1e-30)

            return s * s, "sigma2 (nm?2)"

        return lam, "lambda (nm)"

    def _apply_spectrum_x_axis_label(self, lbl: str) -> None:
        try:
            self.plot_T.setLabel("bottom", lbl)
        except (AttributeError, RuntimeError):
            try:
                self.plot_T.plotItem.setLabel("bottom", lbl)
            except (AttributeError, RuntimeError):
                logger.debug("_apply_spectrum_x_axis_label failed", exc_info=True)

    def _on_spectrum_x_mode_changed(self) -> None:

        if self._last_result is not None:
            self._plot_result(self._last_result, plot_source="abscisse_spectral")

        elif self.df is not None:
            self._plot_data_raw()

    def _format_spectrum_plot_title(self, r: dict) -> str:
        """Spectrum plot title: RMSE and thickness of the displayed snapshot + config summary."""

        rmse = float(r.get("rmse", float("nan")))

        d_nm = float(r.get("d_nm", float("nan")))

        rmse_s = f"{rmse:.6f}" if np.isfinite(rmse) else ""

        d_s = f"{d_nm:.2f} nm" if np.isfinite(d_nm) else ""

        rmse_lbl = "RMSE (bande lambda)" if r.get("rmse_fit_lambda_nm") is not None else "RMSE"

        bits: list[str] = []

        sk = r.get("sigma_knots")

        k_sig = int(np.asarray(sk, dtype=np.float64).size) if sk is not None else 0

        if k_sig > 0:
            bits.append(f"Ksigma={k_sig} ({k_sig - 1} seg.)")

        bits.append("interp sigma=cubic spline")

        if r.get("auto_knot_stages"):
            kb = r.get("auto_knots_K_best")

            if kb is not None:
                bits.append(f"auto-K (K*={int(kb)})")

            else:
                bits.append("auto-K")

        prof = str(self.cb_profilee.currentData() or "").strip() if hasattr(self, "cb_profilee") else ""

        if prof and prof != "fast":
            bits.append(f"profile={prof}")

        cfg_s = "  ".join(bits) if bits else ""

        return f"Spectrum  {rmse_lbl} {rmse_s}  d={d_s}  {cfg_s}"

    def _apply_spectrum_plot_title(self, r: dict | None) -> None:

        t = "Spectrum" if r is None else self._format_spectrum_plot_title(r)

        self.plot_T.plotItem.setTitle(t, color=CertusTheme.PRIMARY, size="11pt")

        self.plot_T._certus_init_title = t

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

    def _spectrum_plot_lambda_span_nm(self) -> tuple[float, float] | None:
        """lambda span of displayed spectrum (file first, else last result grid)."""

        if self.df is not None and "lambda" in self.df.columns:
            lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

            lam = lam[np.isfinite(lam)]

            if lam.size:
                return float(np.min(lam)), float(np.max(lam))

        lr = getattr(self, "_last_result", None)

        if lr is not None and lr.get("lam_nm") is not None:
            lam = np.asarray(lr["lam_nm"], dtype=np.float64).ravel()

            lam = lam[np.isfinite(lam)]

            if lam.size:
                return float(np.min(lam)), float(np.max(lam))

        return None

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

    def _manual_postprocess_seed_result(self) -> dict | None:

        base = getattr(self, "_last_worker_result", None)
        if isinstance(base, dict):
            return base
        base = getattr(self, "_last_result", None)
        if isinstance(base, dict):
            return base
        return None

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

    def _sync_corridor_btn_from_chk(self) -> None:

        if not hasattr(self, "btn_corridor_toggle") or not hasattr(self, "chk_corridor_d"):
            return

    def _on_corridor_chk_state_changed(self, *_args) -> None:

        self._refresh_corridors_gui_state_labels()

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
            if isinstance(payload, SmartInitPayload):
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


# --- LiveIndexMonitor ---
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

