#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

CERTUS-INDEX-SPLINE  Global fit of n(lambda), k(lambda) as piecewise-linear in sigma=1/lambda (ln k at nodes).

Standalone: no imports from CERTUS_INDEX nor certus_swanepool. Local optimization only.

"""

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

from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    SELLMEIER_COEFFS_BY_ID,
    __version__,
    create_module_environment,
    setup_module_logging,
)
from certus_data import read_data_file_robust
from certus_physics import (
    get_n_substrate_array_by_id,
)
from certus_index_utils import (
    _lam_uniform_grid,
    _sorted_finite_sigma_knots as _sorted_finite_sigma_knots_impl,
    log_structured_json_event,
)
from certus_ui import (
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

from certus_design_tokens import slider_corridor_half_stylesheet
from certus_skeleton import install_skeleton, uninstall_skeleton
from certus_metrology import ValidationStatus
from certus_services import IndexFitRequest, IndexFitService

from certus_reset_framework import create_reset_button

from certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus_ux import build_premium_overrides, OBJ

from certus_smart_init_curve_editor import SmartInitNKCurveEditorDialog

# Bootstrap

_env = create_module_environment(__file__, "CERTUS_INDEX_SPLINE")

_SCRIPT_DIR = _env["script_dir"]

logger = logging.getLogger("CERTUS_INDEX_SPLINE")

def _get_substrate_n_array_spline(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    """Return substrate n(lambda), forcing Sapphire (id=3) to equation-based Sellmeier."""

    sid = int(substrate_id)

    wl_nm = np.asarray(wavelengths_nm, dtype=np.float64)

    if sid != 3:
        return get_n_substrate_array_by_id(sid, wl_nm)

    coeffs = SELLMEIER_COEFFS_BY_ID.get(3)

    if coeffs is None or len(coeffs) != 6:
        raise KeyError("Missing Sellmeier coefficients for Sapphire (id=3).")

    B1, C1, B2, C2, B3, C3 = (float(v) for v in coeffs)

    wl_um = wl_nm / 1000.0

    wl_sq = wl_um * wl_um

    with np.errstate(divide="ignore", invalid="ignore"):
        n_sq = 1.0 + (B1 * wl_sq) / (wl_sq - C1) + (B2 * wl_sq) / (wl_sq - C2) + (B3 * wl_sq) / (wl_sq - C3)

    n = np.sqrt(np.maximum(n_sq, 1.0e-6))

    n = np.where(wl_nm < 230.0, np.nan, n)

    return n.astype(np.float64)

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

# Increment to reapply corridor / bootstrap / SiO2 defaults on existing workstations once.

_UNCERTAINTY_DEFAULTS_REV: int = 12

# Corridor d (abs / adaptive): defaults tightened ~4? vs legacy (1e-3 / 1e-4).

_DEFAULT_CORRIDOR_RMSE_DELTA: float = 2.5e-4

_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN: float = 2.5e-5

# Demi-largeur minimale (k lin?aire) appliqu?e ? l'affichage onglet Corridors n/k (coh?rent enveloppe + infobulle).
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

from certus_index_spline_core import (
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

from spline_smart_init import (
    build_smart_manual_sigma_knots_from_preview_grid,
    interp_n_L_pwlnk_to_sigmas,
    pick_best_manual_material_preset,
    recalc_smart_init_spectral_preview,
    smart_init_sweep_node_thickness_rmse,
)

from spline_objective import (
    _spline_objective_lam_mask,
    objective_lam_mask_on_target_grid,
    spectral_mse_rmse_masked_from_nk,
)

from spline_pipeline import (
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

from certus_manual_sigma_knot_dialog import ManualSigmaKnotDialog

from spline_workers import _run_single_spline_stage

from spline_profile_corridors import (
    _expand_corridor_envelope_with_reported_nk,
    enforce_min_k_corridor_half_width,
    _fit_local_quadratic_rmse_profile,
    compute_regular_grid_rmse_profile,
    quick_pwlnk_refit_result_dict,
)

from spline_presets import _project_nb2o5_preset_to_sigma_knots, project_manual_material_preset

from spline_visual_utils import (
    live_monitor_nk_clipboard_tsv_2nm as _live_monitor_nk_clipboard_tsv_2nm,
    snap_spline_visual_dict as _snap_spline_visual_dict,
)

from spline_workers import worker_auto_best_split_knot_refinement

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

def _spectral_display_align(lam_nm: np.ndarray, *series: np.ndarray) -> tuple[np.ndarray, list[np.ndarray], np.ndarray]:
    """

    Truncates all series to the same length as lam_nm, then sorts by increasing lambda.

    Without this, a non-monotonic lambda file results in PyQtGraph lines that "smear"

    the spectrum (phantom oscillations) even if the experimental points remain correct in the scatter plot.

    Also returns ``order`` (indices) to reorder other arrays of the same pre-truncation.

    """

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    if lam.size == 0:
        z = np.array([], dtype=np.int64)

        return lam, [np.asarray(s, dtype=np.float64).ravel()[:0] for s in series], z

    n_use = lam.size

    arrs: list[np.ndarray] = []

    for s in series:
        a = np.asarray(s, dtype=np.float64).ravel()

        n_use = min(n_use, a.size)

        arrs.append(a)

    if n_use <= 0:
        zf = np.array([], dtype=np.float64)

        zi = np.array([], dtype=np.int64)

        return zf, [zf.copy() for _ in series], zi

    if n_use != lam.size:
        logger.warning(
            "Spectral display: inconsistent lengths (lambda=%d, truncation to %d).",
            lam.size,
            n_use,
        )

    lam_u = lam[:n_use]

    trimmed = [a[:n_use] for a in arrs]

    order = np.argsort(lam_u, kind="mergesort")

    lam_s = lam_u[order]

    out = [np.asarray(t)[order] for t in trimmed]

    return lam_s, out, order



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

class CorridorRMSEProfileWindow(QDialog):
    """Window displaying the RMSE = f(thickness) curve from corridor profiling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Corridor RMSE Profile  |  RMSE = f(thickness)")
        self.resize(600, 450)

        layout = QVBoxLayout(self)

        # Info label
        self.lbl_info = QLabel("No corridor data available. Run optimization with corridors enabled.")
        self.lbl_info.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        self.chk_envelope_only = QCheckBox("Lower envelope only")
        self.chk_envelope_only.setChecked(False)
        self.chk_envelope_only.setToolTip(
            "Show only the lower RMSE envelope across nearby d values (filters local spikes)."
        )
        self.chk_envelope_only.toggled.connect(self._refresh_from_cache)
        layout.addWidget(self.chk_envelope_only)

        # Plot widget
        self.plot_rmse = CertusScientificPlot(title="RMSE vs Thickness d")
        self.plot_rmse.setLabel("bottom", "d (nm)")
        self.plot_rmse.setLabel("left", "RMSE")
        layout.addWidget(self.plot_rmse)

        # Button bar
        btn_layout = QHBoxLayout()

        self.btn_copy = create_styled_button("Copy data (TSV)", "secondary", parent=self)
        self.btn_copy.setToolTip("Copy d (nm) and RMSE values to clipboard (tab-separated)")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.btn_copy)

        btn_layout.addStretch()

        self.btn_close = create_styled_button("Close", "secondary", parent=self)
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        apply_certus_theme(self)

        self._d_data: np.ndarray | None = None
        self._rmse_data: np.ndarray | None = None
        self._rmse_thresh: float | None = None
        self._d_data_raw: np.ndarray | None = None
        self._rmse_data_raw: np.ndarray | None = None

    def update_profile(self, d_nm: np.ndarray, rmse: np.ndarray, rmse_thresh: float | None = None) -> None:
        """Updates the plot with profiling data.

        Args:
            d_nm: Array des ?paisseurs (nm)
            rmse: Array des valeurs RMSE correspondantes
            rmse_thresh: RMSE threshold used for acceptance (optional)
        """
        d_arr = np.asarray(d_nm, dtype=np.float64).ravel()
        r_arr = np.asarray(rmse, dtype=np.float64).ravel()

        if d_arr.size == 0 or r_arr.size == 0 or d_arr.size != r_arr.size:
            self.lbl_info.setText("No valid corridor profiling data.")
            self._d_data = None
            self._rmse_data = None
            self._d_data_raw = None
            self._rmse_data_raw = None

        self._d_data_raw = d_arr
        self._rmse_data_raw = r_arr
        self._rmse_thresh = rmse_thresh

        order = np.argsort(d_arr, kind="mergesort")
        d_sorted = d_arr[order]
        r_sorted = r_arr[order]

        if self.chk_envelope_only.isChecked() and d_sorted.size > 0:
            d_unique = np.unique(d_sorted)
            if d_unique.size >= 2:
                step_nm = float(np.median(np.diff(d_unique)))
            else:
                step_nm = 1.0
            env_mask = _rmse_d_lower_envelope_mask(d_sorted, r_sorted, 0.55 * max(step_nm, 1e-9))
            d_sorted = d_sorted[env_mask]
            r_sorted = r_sorted[env_mask]

        self._d_data = d_sorted
        self._rmse_data = r_sorted

        # Mettre ? jour le graphique
        self.plot_rmse.clear()

        # Courbe RMSE(d)
        self.plot_rmse.add_curve(d_sorted, r_sorted, "RMSE(d)", color=CertusTheme.PRIMARY, width=2)

        # Ligne de seuil si disponible
        if rmse_thresh is not None and np.isfinite(rmse_thresh):
            d_span = float(d_sorted[-1] - d_sorted[0]) if d_sorted.size > 1 else 100.0
            d_lo = float(d_sorted[0]) - 0.1 * d_span
            d_hi = float(d_sorted[-1]) + 0.1 * d_span
            self.plot_rmse.add_curve(
                np.array([d_lo, d_hi]),
                np.array([rmse_thresh, rmse_thresh]),
                f"Threshold = {rmse_thresh:.6f}",
                color=CertusTheme.DANGER,
                width=1,
                style=Qt.PenStyle.DashLine,
            )

        # Info
        n_points = d_arr.size
        d_min, d_max = float(d_sorted[0]), float(d_sorted[-1])
        r_min, r_max = float(np.min(r_sorted)), float(np.max(r_sorted))
        d_opt = float(d_sorted[np.argmin(r_sorted)])

        info_txt = (
            f"Points: {n_points} | "
            f"d interval: [{d_min:.2f}, {d_max:.2f}] nm | "
            f"d(opt) ? {d_opt:.2f} nm | "
            f"RMSE range: [{r_min:.6f}, {r_max:.6f}]"
        )
        if rmse_thresh is not None and np.isfinite(rmse_thresh):
            info_txt += f" | Threshold: {rmse_thresh:.6f}"

        self.lbl_info.setText(info_txt)
        self.plot_rmse.autoRange()

    def _refresh_from_cache(self) -> None:
        """Refreshes display after envelope toggle change."""
        if self._d_data_raw is None or self._rmse_data_raw is None:
            return
        self.update_profile(self._d_data_raw, self._rmse_data_raw, self._rmse_thresh)

    def _copy_to_clipboard(self) -> None:
        """Copies (d, RMSE) data to clipboard."""
        if self._d_data is None or self._rmse_data is None:
            QMessageBox.information(self, "Clipboard", "No data to copy.")
            return

        lines = ["d_nm\tRMSE"]
        for d, r in zip(self._d_data, self._rmse_data):
            lines.append(f"{d:.6f}\t{r:.8f}")

        txt = "\n".join(lines)
        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText(txt)
        prev = self.btn_copy.text()
        self.btn_copy.setText("Copied!")
        QTimer.singleShot(1500, lambda t=prev: self.btn_copy.setText(t))

class LiveIndexMonitor(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:

        super().__init__(parent)

        self.setWindowTitle("Monitoring Indices (Live)")

        self.resize(550, 700)

        l = QVBoxLayout(self)

        h = QHBoxLayout()

        h.addWidget(QLabel("X Axis Unit:"))

        self.cb = QComboBox()

        self.cb.addItems(["Lambda (nm)", "Sigma (nm?1)", "Sigma2 (nm?2)"])

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
            x, lbl = 1.0 / lam_arr, "sigma (nm?1)"

        else:
            x, lbl = (1.0 / lam_arr) ** 2, "sigma2 (nm?2)"

        if d_nm is not None and np.isfinite(float(d_nm)):
            self.lbl_d.setText(f"d = {float(d_nm):.1f} nm")

        self.p_n.setLabel("bottom", lbl)

        self.p_k.setLabel("bottom", lbl)

        if "n" not in self.p_n._curves:
            self.p_n.add_curve(x, n_arr, "n", color=CertusTheme.PRIMARY, width=2)

        else:
            self.p_n.update_curve("n", x, n_arr)

        if "k" not in self.p_k._curves:
            self.p_k.add_curve(x, k_arr, "k", color=CertusTheme.DANGER, width=2)

        else:
            self.p_k.update_curve("k", x, k_arr)

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

def _d_from_slider_int(iv: int, d_lo_nm: float, d_hi_nm: float, steps: int = _D_SLIDER_STEPS_DEFAULT) -> float:
    """Convert slider integer position to thickness (nm)."""
    if d_hi_nm <= d_lo_nm + 1e-30:
        return float(d_lo_nm)
    t = float(iv) / float(steps)
    return float(d_lo_nm + t * (d_hi_nm - d_lo_nm))

def _slider_int_from_d_nm(dv: float, d_lo_nm: float, d_hi_nm: float, steps: int = _D_SLIDER_STEPS_DEFAULT) -> int:
    """Convert thickness (nm) to slider integer position."""
    if d_hi_nm <= d_lo_nm + 1e-30:
        return 0
    dv = float(np.clip(dv, d_lo_nm, d_hi_nm))
    t = (dv - d_lo_nm) / (d_hi_nm - d_lo_nm)
    return int(round(t * steps))

def _get_xv_spectral_coord(sx: float, mode: str) -> float:
    """Utility for spectral coordinate conversion (lambda / sigma / sigma2)."""
    if mode == "Sigma (nm?1)":
        return float(sx)
    elif mode == "Sigma2 (nm?2)":
        return float(sx) ** 2
    else:
        return 1.0 / float(sx) if sx != 0 else 0.0

def _stretch_sig_to_px(delta: float, span_sig2: float) -> int:
    """Calculate pixel stretch for sigma-based UI elements."""
    return max(1, int(max(0.0, float(delta)) / max(span_sig2, 1e-30) * 28000.0))

def _compute_study_lambda_window_nm(lam_m: np.ndarray, cfg: "SplineOptConfig") -> tuple[float, float]:
    """Calculate the useful lambda band for display and RMSE calculation."""
    lam = np.asarray(lam_m, dtype=np.float64).ravel()
    ok = np.isfinite(lam) & (lam > 0)
    if not np.any(ok):
        return 400.0, 1200.0
    lo_d = float(np.min(lam[ok]))
    hi_d = float(np.max(lam[ok]))
    rw = getattr(cfg, "rmse_fit_lambda_nm", None)
    if rw is None:
        return lo_d, hi_d
    lo_w = float(min(rw[0], rw[1]))
    hi_w = float(max(rw[0], rw[1]))
    lo = max(lo_d, lo_w)
    hi = min(hi_d, hi_w)
    if hi <= lo:
        return lo_d, hi_d
    return lo, hi

def _rmse_d_lower_envelope_mask(d_nm: np.ndarray, rmse: np.ndarray, tol_nm: float) -> np.ndarray:
    """Masque bool?en : point sur l enveloppe inf?rieure locale en ?paisseur (d +/- tol)."""
    d_a = np.asarray(d_nm, dtype=np.float64).ravel()
    r_a = np.asarray(rmse, dtype=np.float64).ravel()
    n = int(d_a.size)
    if n == 0 or r_a.size != n:
        return np.zeros(max(n, 0), dtype=bool)
    if not np.isfinite(tol_nm) or tol_nm <= 0.0:
        du = np.unique(d_a)
        if du.size >= 2:
            sp = float(np.median(np.diff(np.sort(du))))
        else:
            sp = 1.0
        tol_nm = max(1e-9, 0.55 * sp)
    keep = np.zeros(n, dtype=bool)
    for i in range(n):
        m = np.abs(d_a - d_a[i]) <= tol_nm
        keep[i] = float(r_a[i]) <= float(np.min(r_a[m])) + 1e-15
    return keep

def _filter_rmse_peaks_iteratively(
    d: np.ndarray,
    r: np.ndarray,
    *sidecars: np.ndarray,
) -> tuple[np.ndarray, ...]:
    """Remove points whose RMSE exceeds both neighbors; optional *sidecars stay row-aligned with (d, r)."""
    if d.size < 3:
        if sidecars:
            return (d, r) + tuple(np.asarray(s).copy() for s in sidecars)
        return d, r

    d_curr = d.copy()
    r_curr = r.copy()
    sc = [np.asarray(s).copy() for s in sidecars]
    changed = True
    while changed:
        changed = False
        n = d_curr.size
        if n < 3:
            break
        mask = np.ones(n, dtype=bool)
        for i in range(1, n - 1):
            if r_curr[i] > r_curr[i - 1] + 1e-15 and r_curr[i] > r_curr[i + 1] + 1e-15:
                mask[i] = False
                changed = True
        if changed:
            d_curr = d_curr[mask]
            r_curr = r_curr[mask]
            sc = [a[mask] for a in sc]
    if sidecars:
        return (d_curr, r_curr) + tuple(sc)
    return d_curr, r_curr

def _safe_int_from_mapping(m: Mapping[str, Any], key: str, default: int = -1) -> int:
    v = m.get(key, None)
    if v is None:
        return int(default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)

def _worker_corridor_rmse_regular_grid(
    cfg: SplineOptConfig,
    base_snapshot: dict,
    d_grid_nm: np.ndarray,
    stop_event: Event,
    breakpoint_lookback_points: int = 5,
    **kwargs: Any,
) -> dict[str, Any]:
    """Worker: refit n,L ? d fix? sur une grille (m?me objectif spectral masqu? que le corridor)."""

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
    """Apr?s RMSE(d) : polish L-BFGS-B sur (d, n?uds) depuis le minimum discret de grille (?paisseur libre locale)."""
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
        f"Summary: dialogue mesh K={k_n} sigma knots (worker = canonical file K after 'Continue' if different). "
        f"Squares = theoretical T at knots. Continue -> local refinement on this mesh. "
        f"d {dv:.2f} nm | stage {rmse_lbl} start (x0 after clip, before L-BFGS-B) {rm:.6f} "
        f"| best reached {best_rmse:.6f}"
    )

@dataclass
class _RMSEPlotContext:
    d_plot: np.ndarray
    r_plot: np.ndarray
    kind_plot: np.ndarray
    status_plot: np.ndarray
    d_vis: np.ndarray
    r_vis: np.ndarray
    kind_vis: np.ndarray
    status_vis: np.ndarray
    d_s: np.ndarray
    r_s: np.ndarray
    m_rev: np.ndarray
    m_main: np.ndarray
    envelope_display: bool
    is_live_grid: bool
    i_best: int
    parab_fit: dict = field(default_factory=dict)
    curvature_label_spec: Any = None
    live_parab: bool = False
    d_best: float = 0.0
    rmse_best: float = 0.0
    rmse_thr: Any = None
    d_parab_arr: np.ndarray = field(default_factory=lambda: np.array([]))
    r_parab_arr: np.ndarray = field(default_factory=lambda: np.array([]))
    win_rb: float = 0.0
    delta_rb: float = 0.0
    i_parab_best: int = -1
    rb_ok: bool = False
    d_lo_rb: float = float("nan")
    d_hi_rb: float = float("nan")
    slope_b: float = float("nan")
    curv_b: float = float("nan")
    d_center: float = float("nan")
    bp_events: list = field(default_factory=list)
    bp_dir_left: int = 0
    bp_dir_right: int = 0

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

class _ExcelExportMixin:
    """Excel Export Area."""

    def export_excel(self, auto_export: bool = False) -> None:
        """Delegates Excel export to SplineReportBuilder."""
        if self._last_result is None:
            if auto_export:
                return
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Error", "No result to export.")
            return
        try:
            warnings_local: list[str] = []
            corr_enabled = bool(getattr(self, "chk_corridor_d", None) and self.chk_corridor_d.isChecked())
            boot_enabled = bool(getattr(self, "chk_corr_boot", None) and self.chk_corr_boot.isChecked())
            corr_seed = int(getattr(self, "sp_corr_seed", None).value()) if hasattr(self, "sp_corr_seed") else 0
            boot_seed = (
                int(getattr(self, "sp_corr_boot_seed", None).value()) if hasattr(self, "sp_corr_boot_seed") else 0
            )
            if corr_enabled and corr_seed == 0:
                warnings_local.append("Spline corridor profiling enabled without explicit RNG seed.")
            if boot_enabled and boot_seed == 0:
                warnings_local.append("Spline bootstrap enabled without explicit RNG seed.")
            if warnings_local:
                self.set_validation_status("WARNING_UNSEEDED_STOCHASTIC")
                for msg in warnings_local:
                    self.add_validation_warning(msg)
            else:
                self.set_validation_status("OK")
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError) as exc:
            self.logger.warning("INDEX_SPLINE export validation status update skipped: %s", exc)
        try:
            svc = IndexFitService(runner=lambda _cfg: self._last_result)
            status_txt = str(getattr(self, "validation_status", "OK") or "OK")
            try:
                status_val = ValidationStatus(status_txt)
            except ValueError:
                status_val = ValidationStatus.OK
            warnings_for_manifest = list(getattr(self, "validation_warnings", []) or [])
            req = IndexFitRequest(
                config=self._build_opt_config(notify=False),
                source_paths=[str(getattr(self, "_last_spectrum_path", "") or "")],
                seed=(int(getattr(self, "sp_corr_seed", None).value()) if hasattr(self, "sp_corr_seed") else None),
                app_id="CERTUS_INDEX_SPLINE",
                app_version=__version__,
                warnings=warnings_for_manifest,
                status=status_val,
            )
            svc_resp = svc.fit(req)
            self._last_result["run_manifest"] = svc_resp.manifest.to_dict()
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as exc:
            self.logger.warning("INDEX_SPLINE manifest generation skipped: %s", exc)

        from certus_data import get_missing_manifest_fields

        manifest_dict = self._last_result.get("run_manifest") if isinstance(self._last_result, dict) else None
        missing_manifest_fields = get_missing_manifest_fields(
            manifest_dict if isinstance(manifest_dict, dict) else None
        )
        if missing_manifest_fields:
            self.logger.error(
                "INDEX_SPLINE export blocked: incomplete manifest (missing: %s)",
                ", ".join(missing_manifest_fields),
            )
            if not auto:

                QMessageBox.warning(
                    self,
                    "Export blocked",
                    "Incomplete manifest: " + ", ".join(missing_manifest_fields),
                )
            return

        ctx = SplineReportContext(
            result=self._last_result,
            df=self.df,
            spectrum_path=getattr(self, "_last_spectrum_path", ""),
            t_is_ratio=self.chk_trel.isChecked(),
            sub_name=str(self.cb_sub.currentData() or self.cb_sub.currentText()),
            rmse_fit_lambda_tuple=self._rmse_fit_lambda_tuple_for_report(),
            lam_mask_callable=self._smart_mesh_objective_lam_mask_float,
            opt_config=self._build_opt_config(notify=False),
        )
        builder = SplineReportBuilder(ctx, logger=self.logger)
        builder.build_report(auto=auto)

    def _prep_rmse_plot_data(self, src: dict) -> "_RMSEPlotContext | None":
        """Tab  Corridor RMSE(d) : profile points + best sampled thickness marker."""

        if not hasattr(self, "plot_corridor_rmse_d"):
            return None

        try:
            self.plot_corridor_rmse_d.clear()

        except (AttributeError, RuntimeError):
            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            return None

        d_prof = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        rmse_prof = np.asarray(src.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        point_kind_prof = np.asarray(src.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
        point_status_prof = np.asarray(
            src.get("profile_d_manual_grid_point_status_code", []),
            dtype=np.int32,
        ).ravel()

        if (d_prof.size == 0 or rmse_prof.size != d_prof.size) and self._corridor_profile_source_result() is not None:
            src = self._corridor_profile_source_result() or src

            d_prof = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()

            rmse_prof = np.asarray(src.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            point_kind_prof = np.asarray(src.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
            point_status_prof = np.asarray(
                src.get("profile_d_manual_grid_point_status_code", []),
                dtype=np.int32,
            ).ravel()

        if d_prof.size == 0 or rmse_prof.size != d_prof.size:
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available for this run.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            if hasattr(self, "btn_corridor_generate_from_grid"):
                self.btn_corridor_generate_from_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_from_partial_grid"):
                self.btn_corridor_generate_from_partial_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
                self.btn_corridor_generate_auto_smart_grid.setEnabled(False)

            self._reset_corridor_manual_controls()

            self._update_corridor_rmse_state_bar(None)

            return None

        m = np.isfinite(d_prof) & np.isfinite(rmse_prof)

        d_prof = d_prof[m]

        rmse_prof = rmse_prof[m]
        if point_kind_prof.size == m.size:
            point_kind_prof = point_kind_prof[m]
        else:
            point_kind_prof = np.zeros(d_prof.size, dtype=np.int32)
        if point_status_prof.size == m.size:
            point_status_prof = point_status_prof[m]
        else:
            point_status_prof = np.zeros(d_prof.size, dtype=np.int32)

        if d_prof.size == 0:
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No finite corridor RMSE profile points.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

            self._corridor_rmse_parab_export = None

            self._corridor_rmse_robust_export = None

            if hasattr(self, "btn_corridor_generate_from_grid"):
                self.btn_corridor_generate_from_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_from_partial_grid"):
                self.btn_corridor_generate_from_partial_grid.setEnabled(False)
            if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
                self.btn_corridor_generate_auto_smart_grid.setEnabled(False)

            self._reset_corridor_manual_controls()

            self._update_corridor_rmse_state_bar(None)

            return None

        order = np.argsort(d_prof)

        d_s = d_prof[order]

        r_s = rmse_prof[order]
        kind_s = point_kind_prof[order]
        status_s = point_status_prof[order]

        is_live_grid = str(src.get("profile_d_status", "")) == "manual_grid_live"
        if is_live_grid:
            # In live mode, display raw points as they arrive.
            d_plot = d_s.copy()
            r_plot = r_s.copy()
            kind_plot = kind_s.copy()
            status_plot = status_s.copy()
        else:
            # Finalized data: iterative RMSE peak filtering.
            d_plot, r_plot, k_plot, s_plot = _filter_rmse_peaks_iteratively(
                d_s.copy(), r_s.copy(), kind_s.copy(), status_s.copy()
            )
            kind_plot = k_plot
            status_plot = s_plot

        self._corridor_rmse_d_vals = d_plot.copy()
        self._corridor_rmse_vals = r_plot.copy()

        env_pref = bool(
            hasattr(self, "chk_corridor_rmse_envelope_only") and self.chk_corridor_rmse_envelope_only.isChecked()
        )

        # The lower envelope filter is often too aggressive for local parabolic wings.
        # We only apply it if explicitly requested AND we have finished a run.
        envelope_display = bool(env_pref and not is_live_grid and d_plot.size > 0)

        # Reduced tolerance to avoid masking the wings of the parabola (max 0.1nm)
        raw_step = (
            float(self.sp_corridor_grid_d_step_nm.value()) if hasattr(self, "sp_corridor_grid_d_step_nm") else 0.5
        )
        tol_nm = min(0.1, 0.2 * raw_step)

        if envelope_display:
            env_m = _rmse_d_lower_envelope_mask(d_plot, r_plot, tol_nm)

            d_vis = d_plot[env_m]

            r_vis = r_plot[env_m]

            kind_vis = kind_plot[env_m]
            status_vis = status_plot[env_m]

            o2 = np.argsort(d_vis)

            d_vis = d_vis[o2]

            r_vis = r_vis[o2]

            kind_vis = kind_vis[o2]
            status_vis = status_vis[o2]

        else:
            d_vis = d_plot

            r_vis = r_plot

            kind_vis = kind_plot
            status_vis = status_plot

        if hasattr(self, "btn_corridor_generate_from_grid"):
            self.btn_corridor_generate_from_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )
        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            self.btn_corridor_generate_from_partial_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )
        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            self.btn_corridor_generate_auto_smart_grid.setEnabled(
                bool(d_plot.size > 0) and str(getattr(self, "_worker_role", "") or "") != "rmse_grid"
            )

        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev
        i_best = int(np.argmin(r_plot)) if r_plot.size > 0 else 0

        return _RMSEPlotContext(
            d_plot=d_plot,
            r_plot=r_plot,
            kind_plot=kind_plot,
            status_plot=status_plot,
            d_vis=d_vis,
            r_vis=r_vis,
            kind_vis=kind_vis,
            status_vis=status_vis,
            d_s=d_s,
            r_s=r_s,
            m_rev=m_rev,
            m_main=m_main,
            envelope_display=envelope_display,
            is_live_grid=is_live_grid,
            i_best=i_best,
        )

    def _plot_rmse_data_scatter(self, src: dict, ctx: "_RMSEPlotContext") -> None:
        d_plot = ctx.d_plot
        r_plot = ctx.r_plot
        d_vis = ctx.d_vis
        r_vis = ctx.r_vis
        kind_vis = ctx.kind_vis
        status_vis = ctx.status_vis
        m_rev = ctx.m_rev
        m_main = ctx.m_main
        i_best = ctx.i_best
        m_rev = np.asarray(kind_vis == 1, dtype=bool)
        m_main = ~m_rev

        # Scatter brut : TOUS les points sans liaison visuelle (conform?ment au paradigme scatter)
        self.plot_corridor_rmse_d.addItem(
            pg.ScatterPlotItem(
                d_vis[m_main],
                r_vis[m_main],
                pen=pg.mkPen(CertusTheme.PRIMARY, width=0),
                brush=pg.mkBrush(0, 87, 255, 160),
                size=5,
                symbol="o",
                name="RMSE(d)",
            )
        )

        if np.any(m_rev):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_rev],
                    r_vis[m_rev],
                    pen=pg.mkPen(255, 140, 0, 180),
                    brush=pg.mkBrush(255, 140, 0, 160),
                    size=8,
                    symbol="t",
                    name="RMSE(d) reprise cassure",
                )
            )

        # Overlay fallback points so users can immediately see where strict Deltad
        # sampling used non-standard evaluation paths.
        m_fb_seed = np.asarray(status_vis == 1, dtype=bool)
        m_fb_obj = np.asarray(status_vis == 2, dtype=bool)
        m_fb_emg = np.asarray(status_vis == 3, dtype=bool)
        if np.any(m_fb_seed):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_seed],
                    r_vis[m_fb_seed],
                    pen=pg.mkPen("#ff8c00", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=10,
                    symbol="x",
                    name="Fallback seed",
                )
            )
        if np.any(m_fb_obj):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_obj],
                    r_vis[m_fb_obj],
                    pen=pg.mkPen("#c2185b", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=11,
                    symbol="d",
                    name="Fallback objectif",
                )
            )
        if np.any(m_fb_emg):
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    d_vis[m_fb_emg],
                    r_vis[m_fb_emg],
                    pen=pg.mkPen("#6a1b9a", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=12,
                    symbol="s",
                    name="Fallback urgence",
                )
            )

        bp_events = src.get("profile_d_manual_grid_breakpoint_events", [])
        bp_d_vals: list[float] = []
        bp_r_vals: list[float] = []
        bp_d_prevn: list[float] = []
        bp_r_prevn: list[float] = []
        bp_d_parab: list[float] = []
        bp_r_parab: list[float] = []
        bp_dir_left = 0
        bp_dir_right = 0
        if isinstance(bp_events, list) and d_plot.size > 0:
            for ev in bp_events:
                if not isinstance(ev, dict):
                    continue
                d_b = float(ev.get("d_break_nm", float("nan")))
                if not np.isfinite(d_b):
                    continue
                i_b = int(np.argmin(np.abs(d_plot - d_b)))
                bp_d_vals.append(float(d_plot[i_b]))
                bp_r_vals.append(float(r_plot[i_b]))
                trg_prevn = bool(float(ev.get("trigger_prevN", 0.0)) > 0.5)
                trg_parab = bool(float(ev.get("trigger_parabola", 0.0)) > 0.5)
                if trg_parab:
                    bp_d_parab.append(float(d_plot[i_b]))
                    bp_r_parab.append(float(r_plot[i_b]))
                elif trg_prevn:
                    bp_d_prevn.append(float(d_plot[i_b]))
                    bp_r_prevn.append(float(r_plot[i_b]))
                dir_s = float(ev.get("branch_dir_sign", float("nan")))
                if np.isfinite(dir_s):
                    if dir_s > 0:
                        bp_dir_right += 1
                    elif dir_s < 0:
                        bp_dir_left += 1
        if bp_d_vals:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_vals, dtype=np.float64),
                    np.asarray(bp_r_vals, dtype=np.float64),
                    pen=pg.mkPen("#9b111e", width=3),
                    brush=pg.mkBrush(255, 236, 139, 180),
                    size=13,
                    symbol="o",
                    name="Breakpoints",
                )
            )
        if bp_d_prevn:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_prevn, dtype=np.float64),
                    np.asarray(bp_r_prevn, dtype=np.float64),
                    pen=pg.mkPen("#9b111e", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=11,
                    symbol="d",
                    name="Breakpoint prevN",
                )
            )
        if bp_d_parab:
            self.plot_corridor_rmse_d.addItem(
                pg.ScatterPlotItem(
                    np.asarray(bp_d_parab, dtype=np.float64),
                    np.asarray(bp_r_parab, dtype=np.float64),
                    pen=pg.mkPen("#7a3cff", width=2),
                    brush=pg.mkBrush(255, 255, 255, 0),
                    size=12,
                    symbol="t",
                    name="Breakpoint parabola",
                )
            )

        i_best = int(np.argmin(r_plot))

        self._corridor_rmse_best_idx = i_best

        d_best = float(d_plot[i_best])

        rmse_best = float(r_plot[i_best])

        delta_rb = float(self.sp_corridor_rmse_delta.value()) if hasattr(self, "sp_corridor_rmse_delta") else 2e-4

        win_rb = int(self.sp_corridor_rmse_win.value()) if hasattr(self, "sp_corridor_rmse_win") else 3

        live_parab = (
            not hasattr(self, "chk_corridor_rmse_live_parabola") or self.chk_corridor_rmse_live_parabola.isChecked()
        )
        curvature_label_spec: tuple[float, float, float] | None = None

        # --- Min-RMSE par d unique pour le fit parabolique (profile likelihood correcte) ---
        # Pour absorber les doublons flottants (ex. d_opt ins?r? 2? par le walk),
        # on regroupe ? 1e-6 nm puis on conserve le RMSE minimal par d.
        _d_rounded = np.round(d_plot, decimals=6)
        _d_parab_list: list[float] = []
        _r_parab_list: list[float] = []
        for _dv in np.unique(_d_rounded):
            _m = _d_rounded == _dv
            _best = int(np.argmin(r_plot[_m]))
            _d_parab_list.append(float(d_plot[_m][_best]))
            _r_parab_list.append(float(r_plot[_m][_best]))
        d_parab_arr = np.asarray(_d_parab_list, dtype=np.float64)
        r_parab_arr = np.asarray(_r_parab_list, dtype=np.float64)

        i_parab_best = int(np.argmin(r_parab_arr)) if r_parab_arr.size > 0 else int(i_best)

        parab_half_window_pts = int(max(int(win_rb), int(max(1, d_parab_arr.size))))
        parab_fit = (
            _fit_local_quadratic_rmse_profile(
                d_parab_arr,
                r_parab_arr,
                i_parab_best,
                parab_half_window_pts,
                delta_rb,
            )
            if live_parab
            else {"ok": False}
        )

        d_center = float(parab_fit.get("d_center", float("nan"))) if bool(parab_fit.get("ok", False)) else float(d_best)

        self._corridor_rmse_center_nm = float(d_center)

        self.plot_corridor_rmse_d.addItem(
            pg.InfiniteLine(
                pos=d_best,
                angle=90,
                movable=False,
                pen=pg.mkPen("#17a673", width=2, style=Qt.PenStyle.DashLine),
            )
        )

        self.plot_corridor_rmse_d.addItem(
            pg.ScatterPlotItem(
                [d_best],
                [rmse_best],
                pen=pg.mkPen("#0a5f42", width=1),
                brush=pg.mkBrush("#20c997"),
                size=10,
                symbol="o",
            )
        )

        rmse_thr = src.get("profile_d_rmse_thresh")

        if rmse_thr is not None and np.isfinite(float(rmse_thr)):
            thr = float(rmse_thr)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(
                    pos=thr,
                    angle=0,
                    movable=False,
                    pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DashLine),
                )
            )

        if live_parab:
            rb_ok, d_lo_rb, d_hi_rb, slope_b, _curv_b = self._robust_interval_from_local_quadratic(
                d_parab_arr,
                r_parab_arr,
                i_parab_best,
                delta_rb,
                parab_half_window_pts,
            )

        else:
            rb_ok, d_lo_rb, d_hi_rb, slope_b, _curv_b = False, float("nan"), float("nan"), float("nan"), float("nan")

        if bool(parab_fit.get("ok", False)):
            win_lo, win_hi = parab_fit.get("window_nm", (float(np.min(d_parab_arr)), float(np.max(d_parab_arr))))
            d_center_fit = float(parab_fit.get("d_center", d_center))
            lo_w = float(win_lo)
            hi_w = float(win_hi)
            half_span = float("nan")
            if np.isfinite(d_center_fit) and np.isfinite(lo_w) and np.isfinite(hi_w) and hi_w > lo_w:
                left = float(d_center_fit - lo_w)
                right = float(hi_w - d_center_fit)
                # Symmetric display around the parabola center (visual quasi-symmetry guaranteed).
                if left > 0.0 and right > 0.0:
                    half_span = float(min(left, right))
                else:
                    half_span = 0.5 * float(hi_w - lo_w)
            if not np.isfinite(half_span) or half_span <= 0.0:
                half_span = max(1e-6, 0.5 * float(np.ptp(d_parab_arr)) if d_parab_arr.size > 1 else 1e-3)
            d_par = np.linspace(
                float(d_center_fit - half_span),
                float(d_center_fit + half_span),
                200,
                dtype=np.float64,
            )

            c2, c1, c0 = parab_fit.get("coeffs", (float("nan"), float("nan"), float("nan")))

            x_par = d_par - float(parab_fit.get("anchor_nm", d_best))

            r_par = float(c2) * x_par * x_par + float(c1) * x_par + float(c0)

            self._add_curve(
                self.plot_corridor_rmse_d,
                d_par,
                r_par,
                "#7a3cff",
                "Local parabolic fit",
                pen=pg.mkPen("#7a3cff", width=2, style=Qt.PenStyle.DashLine),
            )

            # c2 = coefficient quadratique (RMSE = c2x^2+c1x+c0, x = d ? anchor) ; sommet en d_center.
            if np.isfinite(c2) and c2 > 0 and np.isfinite(c1) and np.isfinite(c0):
                d_v = float(parab_fit.get("d_center", float("nan")))
                r_v = float(c0) - float(c1) ** 2 / (4.0 * float(c2))
                if np.isfinite(d_v) and np.isfinite(r_v):
                    curvature_label_spec = (float(c2), d_v, r_v)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(
                    pos=float(d_center),
                    angle=90,
                    movable=False,
                    pen=pg.mkPen("#7a3cff", width=1, style=Qt.PenStyle.DotLine),
                )
            )

        ctx.parab_fit = parab_fit
        ctx.curvature_label_spec = curvature_label_spec
        ctx.live_parab = live_parab
        ctx.d_best = d_best
        ctx.rmse_best = rmse_best
        ctx.rmse_thr = rmse_thr
        ctx.d_parab_arr = d_parab_arr
        ctx.r_parab_arr = r_parab_arr
        ctx.win_rb = win_rb
        ctx.delta_rb = delta_rb
        ctx.i_parab_best = i_parab_best
        ctx.rb_ok = bool(rb_ok)
        ctx.d_lo_rb = float(d_lo_rb)
        ctx.d_hi_rb = float(d_hi_rb)
        ctx.slope_b = float(slope_b)
        ctx.curv_b = float(_curv_b)
        ctx.d_center = float(d_center) if bool(parab_fit.get("ok", False)) else float(d_best)
        ctx.bp_events = bp_events if isinstance(bp_events, list) else []
        ctx.bp_dir_left = int(bp_dir_left)
        ctx.bp_dir_right = int(bp_dir_right)

    def _plot_corridor_rmse_tab(self, src: dict) -> None:
        """Tab corridor RMSE(d). Orchestrator."""
        if not hasattr(self, "plot_corridor_rmse_d"):
            return
        ctx = self._prep_rmse_plot_data(src)
        if ctx is None:
            return
        self._plot_rmse_data_scatter(src, ctx)
        d_plot = ctx.d_plot
        r_plot = ctx.r_plot
        d_vis = ctx.d_vis
        r_vis = ctx.r_vis
        i_best = ctx.i_best
        parab_fit = ctx.parab_fit
        curvature_label_spec = ctx.curvature_label_spec
        envelope_display = ctx.envelope_display
        is_live_grid = ctx.is_live_grid
        live_parab = ctx.live_parab
        d_best = ctx.d_best
        rmse_best = ctx.rmse_best
        rmse_thr = ctx.rmse_thr
        d_parab_arr = ctx.d_parab_arr
        r_parab_arr = ctx.r_parab_arr
        win_rb = ctx.win_rb
        delta_rb = ctx.delta_rb

        rb_ok = ctx.rb_ok
        d_lo_rb = ctx.d_lo_rb
        d_hi_rb = ctx.d_hi_rb
        slope_b = ctx.slope_b
        _curv_b = ctx.curv_b
        d_center = ctx.d_center
        bp_events = ctx.bp_events
        bp_dir_left = ctx.bp_dir_left
        bp_dir_right = ctx.bp_dir_right

        self._corridor_rmse_robust_ok = bool(rb_ok)

        self._corridor_rmse_robust_lo = float(d_lo_rb)

        self._corridor_rmse_robust_hi = float(d_hi_rb)

        # --- Smart Deltad: automatic interval from code de profilage (profile_d_interval_nm) ---
        _int_nm = src.get("profile_d_interval_nm", None)
        _int_ok = (
            isinstance(_int_nm, (tuple, list))
            and len(_int_nm) == 2
            and np.isfinite(float(_int_nm[0]))
            and np.isfinite(float(_int_nm[1]))
        )

        # Fallback : si l'intervalle n'est pas fourni (ex: grille simple),
        # try to calculate it locally from points and RMSE threshold
        if not _int_ok and rmse_thr is not None and np.isfinite(float(rmse_thr)) and d_plot.size > 1:
            thr = float(rmse_thr)
            # On cherche les points d'intersection (simple scan lin?aire sur l'enveloppe basse)
            # Note: d_parab_arr est tri? et contient l'enveloppe min-per-d
            if d_parab_arr.size > 2:
                try:
                    _m_below = r_parab_arr <= thr
                    if np.any(_m_below):
                        _d_below = d_parab_arr[_m_below]
                        _int_nm = (float(np.min(_d_below)), float(np.max(_d_below)))
                        _int_ok = True
                except (ValueError, TypeError, AttributeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        if _int_ok:
            _d_int_lo = float(_int_nm[0])
            _d_int_hi = float(_int_nm[1])
            _pen_int = pg.mkPen("#ff8c00", width=3, style=Qt.PenStyle.SolidLine)
            _line_int_lo = pg.InfiniteLine(pos=_d_int_lo, angle=90, movable=False, pen=_pen_int)
            _line_int_hi = pg.InfiniteLine(pos=_d_int_hi, angle=90, movable=False, pen=_pen_int)
            _line_int_lo.setToolTip(f"Smart interval low-bound: {_d_int_lo:.3f} nm")
            _line_int_hi.setToolTip(f"Smart interval high-bound: {_d_int_hi:.3f} nm")

            # Labels sur les lignes intelligentes
            _d_int_adap = src.get("profile_d_rmse_abs_tolerance_adaptive", False)
            _int_label_base = "Deltad auto" + (" (adapt.)" if _d_int_adap else "")
            _label_lo = pg.TextItem(
                text=f"{_int_label_base}\n{_d_int_lo:.3f} nm",
                color="#ff8c00",
                anchor=(0.5, 1.0),
            )
            _label_hi = pg.TextItem(
                text=f"{_int_label_base}\n{_d_int_hi:.3f} nm",
                color="#ff8c00",
                anchor=(0.5, 1.0),
            )
            self.plot_corridor_rmse_d.addItem(_line_int_lo)
            self.plot_corridor_rmse_d.addItem(_line_int_hi)

            # Positionner les TextItems un peu au dessus du minimum
            _r_range = float(np.max(r_plot) - np.min(r_plot)) if r_plot.size > 1 else 1e-4
            _r_label = float(np.nanmin(r_plot)) + 0.05 * _r_range
            _label_lo.setPos(_d_int_lo, _r_label)
            _label_hi.setPos(_d_int_hi, _r_label)
            self.plot_corridor_rmse_d.addItem(_label_lo)
            self.plot_corridor_rmse_d.addItem(_label_hi)
            self._corridor_rmse_smart_interval = (_d_int_lo, _d_int_hi)
        else:
            self._corridor_rmse_smart_interval = None

        # --- Local robust interval (user-configurable) ---
        if rb_ok:
            pen_rb = pg.mkPen("#7a3cff", width=1, style=Qt.PenStyle.DashLine)
            self.plot_corridor_rmse_d.addItem(pg.InfiniteLine(pos=float(d_lo_rb), angle=90, movable=False, pen=pen_rb))
            self.plot_corridor_rmse_d.addItem(pg.InfiniteLine(pos=float(d_hi_rb), angle=90, movable=False, pen=pen_rb))

        self._corridor_rmse_parab_export = dict(parab_fit)

        self._corridor_rmse_robust_export = {
            "ok": bool(rb_ok),
            "d_lo": float(d_lo_rb),
            "d_hi": float(d_hi_rb),
            "slope": float(slope_b),
            "curvature": float(_curv_b),
            "delta_rmse_setting": float(delta_rb),
            "half_window_pts": int(win_rb),
        }

        self._sync_corridor_manual_controls(d_plot, i_best)

        d_lo_man = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))

        d_hi_man = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))

        if np.isfinite(d_lo_man) and np.isfinite(d_hi_man) and d_hi_man >= d_lo_man:
            pen_man = pg.mkPen("#ff4d4f", width=1, style=Qt.PenStyle.DashLine)

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(pos=float(d_lo_man), angle=90, movable=False, pen=pen_man)
            )

            self.plot_corridor_rmse_d.addItem(
                pg.InfiniteLine(pos=float(d_hi_man), angle=90, movable=False, pen=pen_man)
            )

        if hasattr(self, "lbl_corridor_rmse_summary"):
            _grid_note = ""

            if str(src.get("profile_d_status", "")) == "manual_grid":
                _grid_note = " | manual grid (re-run)"

                n_bp = int(src.get("profile_d_manual_grid_breakpoint_count", 0))

                n_extra = int(src.get("profile_d_manual_grid_extra_points", 0))

                if n_bp > 0 or n_extra > 0:
                    _grid_note += f" | breakpoints detected={n_bp} | points extra={n_extra}"
                if isinstance(bp_events, list) and bp_events:
                    n_prevn = int(
                        sum(1 for ev in bp_events if isinstance(ev, dict) and float(ev.get("trigger_prevN", 0.0)) > 0.5)
                    )
                    n_parab = int(
                        sum(
                            1
                            for ev in bp_events
                            if isinstance(ev, dict) and float(ev.get("trigger_parabola", 0.0)) > 0.5
                        )
                    )
                    _grid_note += f" | causes(prevN={n_prevn}, parabola={n_parab})"
                    _grid_note += f" | direction(chosen left={int(bp_dir_left)}, right={int(bp_dir_right)})"

            _env_note = ""

            if envelope_display:
                _env_note = f" | plot: lower envelope ({int(d_vis.size)}/{int(d_plot.size)} pts)"

            _smart_note = ""
            if getattr(self, "_corridor_rmse_smart_interval", None) is not None:
                _s_lo, _s_hi = self._corridor_rmse_smart_interval
                _smart_note = f" | Deltad code ? [{_s_lo:.3f}, {_s_hi:.3f}] nm"

            txt = (
                (
                    f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {rmse_best:.6f} | "
                    f"samples = {int(d_plot.size)}"
                )
                + _env_note
                + _grid_note
                + _smart_note
            )

            if rb_ok:
                txt += (
                    f" | robust Delta={delta_rb:.6f} -> interval ? [{float(d_lo_rb):.3f}, {float(d_hi_rb):.3f}] nm"
                    f" | slope@d*?{float(slope_b):+.2e} /nm"
                )

                if bool(parab_fit.get("ok", False)):
                    txt += f" | parabola center?{float(d_center):.3f} nm"

            else:
                txt += " | robust interval unavailable (insufficient local convex fit)"

            if np.isfinite(d_lo_man) and np.isfinite(d_hi_man):
                man_state = "active" if bool(getattr(self, "_corridor_rmse_manual_active", False)) else "preview"

                txt += f" | manual {man_state} ? [{float(d_lo_man):.3f}, {float(d_hi_man):.3f}] nm"

                if bool(src.get("manual_corridor_active", False)):
                    txt += f" ({int(src.get('manual_corridor_selected_count', 0))} profiled points)"

                    d_sel_rng = src.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))

                    if (
                        isinstance(d_sel_rng, (tuple, list))
                        and len(d_sel_rng) >= 2
                        and np.isfinite(float(d_sel_rng[0]))
                        and np.isfinite(float(d_sel_rng[1]))
                    ):
                        txt += f" | sampled in [{float(d_sel_rng[0]):.3f}, {float(d_sel_rng[1]):.3f}] nm"

            if is_live_grid and not live_parab:
                txt += " | live preview: points only (parabola/robust fit paused)"

            self.lbl_corridor_rmse_summary.setText(txt)
        if hasattr(self, "lbl_corridor_rmse_robust_compact"):
            if rb_ok and np.isfinite(float(d_lo_rb)) and np.isfinite(float(d_hi_rb)):
                d_mid_rb = 0.5 * float(d_lo_rb + d_hi_rb)
                d_half_rb = 0.5 * float(max(0.0, d_hi_rb - d_lo_rb))
                self.lbl_corridor_rmse_robust_compact.setText(
                    f"Robust interval: {d_mid_rb:.2f}nm +/- {d_half_rb:.1f}nm"
                )
            else:
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        try:
            self.plot_corridor_rmse_d.plotItem.setTitle(
                f"Corridor profile RMSE(d) ? best d* = {d_best:.3f} nm (RMSE {rmse_best:.6f})",
                color=CertusTheme.PRIMARY,
                size="10pt",
            )

        except (AttributeError, RuntimeError):
            logger.debug("Corridor RMSE(d) title set failed", exc_info=True)

        lock_scale = bool(
            hasattr(self, "chk_corridor_rmse_lock_scale") and self.chk_corridor_rmse_lock_scale.isChecked()
        )

        if is_live_grid:
            # Live mode must always remain visible even if a stale/locked viewport
            # exists from a previous run. Force bounds on current finite data.
            self._set_corridor_rmse_view_data_bounds(
                d_plot,
                r_plot,
            )
        elif lock_scale:
            self._set_corridor_rmse_view_data_bounds(
                d_vis if envelope_display else d_plot,
                r_vis if envelope_display else r_plot,
            )

        elif np.isfinite(d_lo_man) and np.isfinite(d_hi_man) and d_hi_man >= d_lo_man:
            self._set_corridor_rmse_view_centered(float(d_center), 0.5 * float(max(0.0, d_hi_man - d_lo_man)))

        else:
            self.plot_corridor_rmse_d.autoRange()

        if curvature_label_spec is not None:
            c2_l, d_vl, r_vl = curvature_label_spec
            c2_disp = float(abs(c2_l))
            if not np.isfinite(c2_disp) or c2_disp <= 0.0:
                c2_disp = float("nan")
            r_span_src = r_vis if envelope_display else r_plot
            span_r = (
                float(np.nanmax(r_span_src) - np.nanmin(r_span_src))
                if r_span_src.size > 1
                else max(1e-6, abs(float(r_vl)) * 0.05 if np.isfinite(r_vl) else 1e-4)
            )
            dy = max(1e-6, 0.035 * span_r)
            if np.isfinite(c2_disp):
                label_a = pg.TextItem(
                    text=f"Curvature a = {c2_disp:.4e} nm?^2",
                    color="#7a3cff",
                    anchor=(0.5, 1),
                    fill=pg.mkColor(255, 255, 255, 220),
                )
                label_a.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                label_a.setPos(d_vl, r_vl + dy)
                self.plot_corridor_rmse_d.addItem(label_a, ignoreBounds=True)

        self._update_corridor_rmse_state_bar(src)

class _MeshOptimizationMixin:
    """Mixin extracting _build_basic_step4_mesh_optimizer logic."""

    def _build_basic_step4_mesh_optimizer(self, parent_layout: "QVBoxLayout", style: str) -> None:
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

        self._w_full_adv = QWidget()

        v_adv = QVBoxLayout(self._w_full_adv)

        v_adv.setContentsMargins(0, 0, 0, 0)

        v_adv.setSpacing(4)

        lb_pg = QLabel("Local iterations hint (max):")

        lb_pg.setToolTip("Legacy control kept for compatibility; inactive in local-only INDEX-SPLINE mode.")

        self.sp_pg_iter = QSpinBox()

        self.sp_pg_iter.setRange(5, 120)

        self.sp_pg_iter.setValue(int(SPLINE_PERF_PRESETS.get("fast", {}).get("pglobal_max_iter", 35)))

        self.sp_pg_iter.setToolTip("Inactive in local-only mode; kept only for preset/config compatibility.")

        self.sp_pg_iter.setEnabled(False)

        row_pg = QHBoxLayout()

        row_pg.addWidget(lb_pg)

        row_pg.addWidget(self.sp_pg_iter, 1)

        v_adv.addLayout(row_pg)

        lb_pr = QLabel("Performance profile:")

        lb_pr.setToolTip(
            'Budget preset: polish budget and local searches. "Maximal" gives best quality at the expense of runtime.'
        )

        self.cb_profilee = QComboBox()

        for lab, key in [
            ("Fast", "fast"),
            ("Standard", "standard"),
            ("Quality", "quality"),
            ("Maximal", "max"),
        ]:
            self.cb_profilee.addItem(lab, key)

        self.cb_profilee.setCurrentIndex(0)

        self.cb_profilee.setToolTip(
            "When the profile changes, a recommended local budget may be applied automatically to the spin."
        )

        self.cb_profilee.currentIndexChanged.connect(self._on_profilee_changed)

        row_pf = QHBoxLayout()

        row_pf.addWidget(lb_pr)

        row_pf.addWidget(self.cb_profilee, 1)

        v_adv.addLayout(row_pf)

        lb_mesh_dlam = QLabel("Min. Deltalambda/lambda step (sigma mesh) :")

        lb_mesh_dlam.setToolTip(
            "Canonical mesh constraint: min(Deltalambda between nodes) / lambda >= this value, "
            "with lambda? = (lambda_min + lambda_max) / 2 from file. Number of segments is reduced if needed; "
            "IR extension (+2 knots) is omitted if it violates threshold.\n"
            "0 = disabled (nominal behavior without this constraint)."
        )

        self.sp_mesh_min_dlam = QDoubleSpinBox()

        self.sp_mesh_min_dlam.setRange(0.0, 0.5)

        self.sp_mesh_min_dlam.setDecimals(4)

        self.sp_mesh_min_dlam.setSingleStep(0.0025)

        self.sp_mesh_min_dlam.setValue(0.02)

        self.sp_mesh_min_dlam.setSpecialValueText("disabled")

        self.sp_mesh_min_dlam.setToolTip(lb_mesh_dlam.toolTip())

        row_mesh_dlam = QHBoxLayout()

        row_mesh_dlam.addWidget(lb_mesh_dlam)

        row_mesh_dlam.addWidget(self.sp_mesh_min_dlam, 1)

        v_adv.addLayout(row_mesh_dlam)

        lb_auto_clean_v2 = QLabel("Auto-clean V2 (neighbor pull):")
        lb_auto_clean_v2.setToolTip(
            "After removing an internal knot, optionally adjusts the two local neighboring knots\n"
            "(extremes never moved), then re-optimizes RMSE.\n\n"
            "V2 explores symmetric/asymmetric pulls and a small local 2D refinement."
        )
        self.chk_auto_clean_neighbor_pull = QCheckBox("Enable local neighbor pull")
        self.chk_auto_clean_neighbor_pull.setChecked(bool(getattr(self, "_auto_clean_neighbor_pull_enabled", True)))
        self.chk_auto_clean_neighbor_pull.setToolTip(lb_auto_clean_v2.toolTip())
        row_ac0 = QHBoxLayout()
        row_ac0.addWidget(lb_auto_clean_v2)
        row_ac0.addWidget(self.chk_auto_clean_neighbor_pull)
        row_ac0.addStretch(1)
        v_adv.addLayout(row_ac0)

        row_ac1 = QHBoxLayout()
        row_ac1.addWidget(QLabel("pull ratios"))
        self.sp_auto_clean_pull_r1 = QDoubleSpinBox()
        self.sp_auto_clean_pull_r1.setDecimals(3)
        self.sp_auto_clean_pull_r1.setRange(0.01, 0.45)
        self.sp_auto_clean_pull_r1.setSingleStep(0.01)
        self.sp_auto_clean_pull_r1.setValue(float(getattr(self, "_auto_clean_neighbor_pull_r1", 0.10)))
        self.sp_auto_clean_pull_r1.setToolTip("First inward pull ratio (recommended: 0.10).")
        row_ac1.addWidget(self.sp_auto_clean_pull_r1)
        self.sp_auto_clean_pull_r2 = QDoubleSpinBox()
        self.sp_auto_clean_pull_r2.setDecimals(3)
        self.sp_auto_clean_pull_r2.setRange(0.01, 0.45)
        self.sp_auto_clean_pull_r2.setSingleStep(0.01)
        self.sp_auto_clean_pull_r2.setValue(float(getattr(self, "_auto_clean_neighbor_pull_r2", 0.20)))
        self.sp_auto_clean_pull_r2.setToolTip("Second inward pull ratio (recommended: 0.20).")
        row_ac1.addWidget(self.sp_auto_clean_pull_r2)
        self.sp_auto_clean_pull_r3 = QDoubleSpinBox()
        self.sp_auto_clean_pull_r3.setDecimals(3)
        self.sp_auto_clean_pull_r3.setRange(0.01, 0.45)
        self.sp_auto_clean_pull_r3.setSingleStep(0.01)
        self.sp_auto_clean_pull_r3.setValue(float(getattr(self, "_auto_clean_neighbor_pull_r3", 0.30)))
        self.sp_auto_clean_pull_r3.setToolTip("Third inward pull ratio (recommended: 0.30).")
        row_ac1.addWidget(self.sp_auto_clean_pull_r3)
        row_ac1.addStretch(1)
        v_adv.addLayout(row_ac1)

        row_ac2 = QHBoxLayout()
        self.chk_auto_clean_neighbor_pull_local_refine = QCheckBox("Enable local 2D refine")
        self.chk_auto_clean_neighbor_pull_local_refine.setChecked(
            bool(getattr(self, "_auto_clean_neighbor_pull_local_refine_enabled", False))
        )
        self.chk_auto_clean_neighbor_pull_local_refine.setToolTip(
            "After selecting the best pull variant for one removed knot, run a tiny 2D local\n"
            "search on the two adjacent knots to further reduce RMSE."
        )
        row_ac2.addWidget(self.chk_auto_clean_neighbor_pull_local_refine)
        row_ac2.addWidget(QLabel("refine rel. step"))
        self.sp_auto_clean_neighbor_pull_local_refine_step = QDoubleSpinBox()
        self.sp_auto_clean_neighbor_pull_local_refine_step.setDecimals(3)
        self.sp_auto_clean_neighbor_pull_local_refine_step.setRange(0.005, 0.20)
        self.sp_auto_clean_neighbor_pull_local_refine_step.setSingleStep(0.005)
        self.sp_auto_clean_neighbor_pull_local_refine_step.setValue(
            float(getattr(self, "_auto_clean_neighbor_pull_local_refine_rel_step", 0.05))
        )
        self.sp_auto_clean_neighbor_pull_local_refine_step.setToolTip(
            "Relative step used by the local 2D refine around neighboring knots (recommended: 0.05)."
        )
        row_ac2.addWidget(self.sp_auto_clean_neighbor_pull_local_refine_step)
        row_ac2.addStretch(1)
        v_adv.addLayout(row_ac2)

        # --- Profondeur de recherche (LOT E) ---
        row_ac3 = QHBoxLayout()
        row_ac3.addWidget(QLabel("Top-N candidats (auto-clean):"))
        self.sp_auto_clean_top_n = QSpinBox()
        self.sp_auto_clean_top_n.setRange(1, 12)
        self.sp_auto_clean_top_n.setValue(int(getattr(self, "_auto_clean_top_n_sensitivity", 4)))
        self.sp_auto_clean_top_n.setToolTip(
            "Number of removal candidates per step passed to full polish "
            "(plus haut = recherche plus profonde, plus lent). Recommandé : 4."
        )
        row_ac3.addWidget(self.sp_auto_clean_top_n)

        row_ac3.addWidget(QLabel("Polish maxfun candidat:"))
        self.sp_auto_clean_cand_maxfun = QSpinBox()
        self.sp_auto_clean_cand_maxfun.setRange(120, 4000)
        self.sp_auto_clean_cand_maxfun.setSingleStep(100)
        self.sp_auto_clean_cand_maxfun.setValue(int(getattr(self, "_auto_clean_candidate_polish_maxfun", 700)))
        self.sp_auto_clean_cand_maxfun.setToolTip("Budget L-BFGS-B par candidat de retrait (recommandé : 700-1500).")
        row_ac3.addWidget(self.sp_auto_clean_cand_maxfun)

        row_ac3.addWidget(QLabel("Tolerance RMSE:"))
        self.sp_auto_clean_tol = QDoubleSpinBox()
        self.sp_auto_clean_tol.setDecimals(6)
        self.sp_auto_clean_tol.setRange(0.0, 1.0e-2)
        self.sp_auto_clean_tol.setSingleStep(1.0e-5)
        self.sp_auto_clean_tol.setValue(float(getattr(self, "_auto_clean_ui_tolerance", 5.0e-5)))
        self.sp_auto_clean_tol.setToolTip("Absolute RMSE regression tolerated per removal. 0 = strict mode.")
        row_ac3.addWidget(self.sp_auto_clean_tol)
        row_ac3.addStretch(1)
        v_adv.addLayout(row_ac3)

        lb_cor = QLabel("Corridors n/k (d profiling):")

        lb_cor.setToolTip(
            "Calculates a plausible thickness interval and n(lambda), k(lambda) corridors by fixing d, then re-optimizing\n"
            "the n and ln k nodes (same penalties and masked RMSE as the fit).\n\n"
            "RMSE_ref+Delta mode (default): acceptance RMSE <= best polished spectral RMSE + Delta; the nominal 'best' curve\n"
            "is a native member of the envelope (not a pseudo-CI centered on a heuristic refit).\n"
            "Mode alpha : RMSE(d) <= alpha * RMSE_opt (heuristic).\n\n"
            "Enabled by default at end of optimization; results in 'Corridors n/k' tab."
        )

        self.chk_corridor_d = QCheckBox("Enable")

        self.chk_corridor_d.setChecked(True)

        self.chk_corridor_d.setToolTip(lb_cor.toolTip())

        row_cd = QHBoxLayout()

        row_cd.addWidget(lb_cor)

        row_cd.addWidget(self.chk_corridor_d)

        self.lbl_corridors_state_adv = QLabel()

        self.lbl_corridors_state_adv.setTextFormat(Qt.TextFormat.RichText)

        self.lbl_corridors_state_adv.setToolTip(
            "Read-only: same state as the 'Corridors' button under Run (Yes = computation at end of optimization)."
        )

        row_cd.addWidget(self.lbl_corridors_state_adv)

        row_cd.addStretch(1)

        v_adv.addLayout(row_cd)

        row_cor = QHBoxLayout()

        self.cb_corr_mode = QComboBox()

        self.cb_corr_mode.addItem("Heuristic (alpha?RMSE_opt)", "alpha")

        self.cb_corr_mode.addItem("RMSE_ref + Delta (absolute)", "abs_delta")

        self.cb_corr_mode.addItem("RMSE_ref + Delta_adaptatif(local)", "abs_delta_adaptive")

        self.cb_corr_mode.addItem("Likelihood ratio (Delta?^2) - sigma constant or residual", "lr")

        _iad = self.cb_corr_mode.findData("abs_delta_adaptive")

        self.cb_corr_mode.setCurrentIndex(int(_iad) if _iad >= 0 else 0)

        self.cb_corr_mode.setToolTip(
            "alpha : RMSE(d) <= alpha?RMSE_opt (heuristic).\n"
            "RMSE_ref+Delta: RMSE(d) <= RMSE_ref + Delta (same spectral mask). With 'best RMSE' checked, RMSE_ref = "
            "spectral_rmse_best_value (best polish) ; otherwise base curves from dict.\n"
            "RMSE_ref+Delta_adaptatif: Delta is estimated locally from the profiled RMSE(d) parabola and local roughness.\n"
            "LR: Delta?^2 <= ?^2(1,conf); constant sigma or sigma_i(lambda) ? |residual| if 'sigma(lambda) residual'."
        )

        row_cor.addWidget(QLabel("mode"))

        row_cor.addWidget(self.cb_corr_mode)

        self.cb_corr_mode.currentIndexChanged.connect(self._on_corr_mode_changed)

        self.sp_corr_alpha = QDoubleSpinBox()

        self.sp_corr_alpha.setDecimals(3)

        self.sp_corr_alpha.setRange(1.000, 2.000)

        self.sp_corr_alpha.setSingleStep(0.005)

        self.sp_corr_alpha.setValue(1.05)

        self.sp_corr_alpha.setToolTip("alpha: RMSE threshold = alpha ? RMSE_opt (e.g. 1.05 = +5%).")

        self.lbl_corr_alpha = QLabel("alpha")

        row_cor.addWidget(self.lbl_corr_alpha)

        row_cor.addWidget(self.sp_corr_alpha)

        self.lbl_corr_rmse_delta = QLabel("Delta RMSE abs.")

        self.sp_corr_rmse_delta = QDoubleSpinBox()

        self.sp_corr_rmse_delta.setDecimals(5)

        self.sp_corr_rmse_delta.setRange(0.00005, 0.05)

        self.sp_corr_rmse_delta.setSingleStep(0.00005)

        self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

        self.sp_corr_rmse_delta.setToolTip(
            "Absolute margin on masked spectral RMSE: a refit at fixed d is accepted if "
            "RMSE <= RMSE_ref + Delta (default 2.5e-4; adaptive Delta_eff floor 2.5e-5). "
            "With best polished RMSE, RMSE_ref is the one of the exported model."
        )

        row_cor.addWidget(self.lbl_corr_rmse_delta)

        row_cor.addWidget(self.sp_corr_rmse_delta)

        self.chk_corr_scientific_nominal = QCheckBox("best RMSE")

        self.chk_corr_scientific_nominal.setChecked(True)

        self.chk_corr_scientific_nominal.setToolTip(
            "Scientific corridor mode (only if mode = RMSE_ref+Delta): RMSE_ref = spectral_rmse_best_value; "
            "nominal curves and nodes aligned on best polished model; no envelope widening toward "
            "main solver curve. Uncheck for legacy abs_delta behavior on 'base' curves only."
        )

        row_cor.addWidget(self.chk_corr_scientific_nominal)

        self.btn_corr_preset_auto_robust = create_styled_button("Auto robust", "secondary", parent=self)

        self.btn_corr_preset_auto_robust.setToolTip(
            "R?glages recommand?s pour le corridor en d : mode RMSE_ref + Delta adaptatif (local), "
            "expanded parabolic window, thickness interval symmetrized on the parabola peak, "
            "sondes lat?rales et plancher Delta renforc?s. Comportement par d?faut apr?s migration."
        )

        self.btn_corr_preset_auto_robust.clicked.connect(self._apply_corridor_preset_auto_robust)

        row_cor.addWidget(self.btn_corr_preset_auto_robust)

        self.sp_corr_conf = QDoubleSpinBox()

        self.sp_corr_conf.setDecimals(3)

        self.sp_corr_conf.setRange(0.50, 0.999)

        self.sp_corr_conf.setSingleStep(0.01)

        self.sp_corr_conf.setValue(0.95)

        self.sp_corr_conf.setToolTip("LR confidence level (df=1): e.g. 0.95 -> Delta?^2~3.84.")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("conf"))

        row_cor.addWidget(self.sp_corr_conf)

        self.sp_corr_sigma = QDoubleSpinBox()

        self.sp_corr_sigma.setDecimals(6)

        self.sp_corr_sigma.setRange(0.0, 1.0)

        self.sp_corr_sigma.setSingleStep(0.001)

        self.sp_corr_sigma.setValue(0.0)

        self.sp_corr_sigma.setToolTip(
            "Constant sigma (T and R) in fraction units (not %). 0 = auto (sigma := RMSE_opt)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("sigma"))

        row_cor.addWidget(self.sp_corr_sigma)

        self.sp_corr_step = QDoubleSpinBox()

        self.sp_corr_step.setDecimals(2)

        self.sp_corr_step.setRange(0.1, 50.0)

        self.sp_corr_step.setSingleStep(0.5)

        self.sp_corr_step.setValue(1.0)

        self.sp_corr_step.setToolTip("d continuation step size (nm).")

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("step (nm)"))

        row_cor.addWidget(self.sp_corr_step)

        self.sp_corr_span = QDoubleSpinBox()

        self.sp_corr_span.setDecimals(1)

        self.sp_corr_span.setRange(1.0, 2000.0)

        self.sp_corr_span.setSingleStep(1.0)

        self.sp_corr_span.setValue(15.0)

        self.sp_corr_span.setToolTip(
            "Maximum offset |d - d_opt| explored in each direction (+d and -d), in nm (not the sum). "
            "Default 15 nm ~ local neighborhood around the optimal thickness."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(QLabel("span (nm)"))

        row_cor.addWidget(self.sp_corr_span)

        # Multi-start (V2.2): robustness to local minima during fixed-d refit.

        self.sp_corr_starts = QSpinBox()

        self.sp_corr_starts.setRange(1, 25)

        self.sp_corr_starts.setValue(1)

        self.sp_corr_starts.setToolTip(
            "Number of initializations (multi-start) per d value. 1 = continuation only (fast). "
            ">1 increases robustness (best solution kept), at the cost of computation time."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(QLabel("starts"))

        row_cor.addWidget(self.sp_corr_starts)

        self.sp_corr_jn = QDoubleSpinBox()

        self.sp_corr_jn.setDecimals(3)

        self.sp_corr_jn.setRange(0.0, 1.0)

        self.sp_corr_jn.setSingleStep(0.01)

        self.sp_corr_jn.setValue(0.02)

        self.sp_corr_jn.setToolTip("Gaussian jitter sigma on n (or ? if monotonicity active) for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_n"))

        row_cor.addWidget(self.sp_corr_jn)

        self.sp_corr_jL = QDoubleSpinBox()

        self.sp_corr_jL.setDecimals(3)

        self.sp_corr_jL.setRange(0.0, 5.0)

        self.sp_corr_jL.setSingleStep(0.05)

        self.sp_corr_jL.setValue(0.15)

        self.sp_corr_jL.setToolTip("Gaussian jitter sigma on L=ln k for additional starts.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("j_L"))

        row_cor.addWidget(self.sp_corr_jL)

        self.sp_corr_seed = QSpinBox()

        self.sp_corr_seed.setRange(-(2**31), 2**31 - 1)

        self.sp_corr_seed.setValue(0)

        self.sp_corr_seed.setToolTip("RNG seed for multi-start reproducibility (jitter).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seed"))

        row_cor.addWidget(self.sp_corr_seed)

        # V2.3: ln(k) regularization sensitivity scan (d2(L)^2 weight).

        self.chk_corr_reg_sens = QCheckBox("scan reg")

        self.chk_corr_reg_sens.setChecked(False)

        self.chk_corr_reg_sens.setToolTip(
            "Runs a scan (log grid) of the ln(k) regularization weight and re-launches d profiling for each value.\n"
            "Goal: verify the robustness of the d interval and n/k corridors to regularization choices."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(self.chk_corr_reg_sens)

        self.sp_corr_reg_pts = QSpinBox()

        self.sp_corr_reg_pts.setRange(2, 15)

        self.sp_corr_reg_pts.setValue(5)

        self.sp_corr_reg_pts.setToolTip("Number of points in the regularization scan log grid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("pts"))

        row_cor.addWidget(self.sp_corr_reg_pts)

        self.sp_corr_reg_dec = QSpinBox()

        self.sp_corr_reg_dec.setRange(0, 6)

        self.sp_corr_reg_dec.setValue(2)

        self.sp_corr_reg_dec.setToolTip("Number of decades on each side of the base weight (lnk_spline_reg_weight).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("dec"))

        row_cor.addWidget(self.sp_corr_reg_dec)

        # V2.4: parametric bootstrap for publication-level bands

        self.chk_corr_boot = QCheckBox("bootstrap")

        self.chk_corr_boot.setChecked(False)

        self.chk_corr_boot.setToolTip(
            "Parametric bootstrap: generates B T/R datasets by adding Gaussian noise (sigma_T, sigma_R),\n"
            "re-launches d profiling for each replication, then computes percentile bands on n(lambda), k(lambda)\n"
            "and a distribution of the d interval."
        )

        row_cor.addSpacing(10)

        row_cor.addWidget(self.chk_corr_boot)

        self.sp_corr_boot_n = QSpinBox()

        self.sp_corr_boot_n.setRange(5, 500)

        self.sp_corr_boot_n.setValue(40)

        self.sp_corr_boot_n.setToolTip("Number of bootstrap replications (B). Larger = more robust, but slower.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("B"))

        row_cor.addWidget(self.sp_corr_boot_n)

        self.sp_corr_boot_p = QDoubleSpinBox()

        self.sp_corr_boot_p.setDecimals(3)

        self.sp_corr_boot_p.setRange(0.50, 0.999)

        self.sp_corr_boot_p.setSingleStep(0.01)

        self.sp_corr_boot_p.setValue(0.95)

        self.sp_corr_boot_p.setToolTip("Central percentile (e.g. 0.95 => bounds 2.5% / 97.5%).")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("p"))

        row_cor.addWidget(self.sp_corr_boot_p)

        self.sp_corr_boot_seed = QSpinBox()

        self.sp_corr_boot_seed.setRange(-(2**31), 2**31 - 1)

        self.sp_corr_boot_seed.setValue(0)

        self.sp_corr_boot_seed.setToolTip("Seed RNG bootstrap.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("seedB"))

        row_cor.addWidget(self.sp_corr_boot_seed)

        self.cb_corr_boot_mode = QComboBox()

        self.cb_corr_boot_mode.addItem("parametric (T/R + N(0,sigma))", "parametric")

        self.cb_corr_boot_mode.addItem("residual (T_th + residuals*)", "residual")

        self.cb_corr_boot_mode.setCurrentIndex(0)

        self.cb_corr_boot_mode.setToolTip(
            "parametric: adds Gaussian noise to measurements.\n"
            "residual: non-parametric bootstrap on residuals (more realistic if noise is non-Gaussian / correlated)."
        )

        row_cor.addSpacing(8)

        row_cor.addWidget(self.cb_corr_boot_mode)

        self.sp_corr_boot_block = QSpinBox()

        self.sp_corr_boot_block.setRange(1, 5000)

        self.sp_corr_boot_block.setValue(1)

        self.sp_corr_boot_block.setToolTip("Block length (in lambda points) for residual bootstrap. 1 = iid.")

        row_cor.addSpacing(6)

        row_cor.addWidget(QLabel("blk"))

        row_cor.addWidget(self.sp_corr_boot_block)

        self._on_corr_mode_changed()

        w_cor = QWidget()

        w_cor.setLayout(row_cor)

        v_adv.addWidget(w_cor)

        row_cor_prof = QHBoxLayout()

        self.sp_corr_prof_maxfun = QSpinBox()

        self.sp_corr_prof_maxfun.setRange(0, 200000)

        self.sp_corr_prof_maxfun.setSingleStep(500)

        self.sp_corr_prof_maxfun.setValue(2500)

        self.sp_corr_prof_maxfun.setToolTip(
            "L-BFGS-B budget (maxfun) for each refit of n, ln k nodes at fixed d during corridor profiling.\n"
            "0 = reuse the main run polish_maxfun (often 8000+, very slow per step).\n"
            "Typ. 1500-4000 for a local scan; increase if 'EXCEEDS LIMIT' messages or poor refits."
        )

        row_cor_prof.addWidget(QLabel("d profiling: maxfun / refit"))

        row_cor_prof.addWidget(self.sp_corr_prof_maxfun)

        row_cor_prof.addStretch(1)

        w_cor_prof = QWidget()

        w_cor_prof.setLayout(row_cor_prof)

        v_adv.addWidget(w_cor_prof)

        row_cor_v25 = QHBoxLayout()

        self.chk_corr_sigma_hetero = QCheckBox("sigma(lambda) residual (LR + param. boot.)")

        self.chk_corr_sigma_hetero.setChecked(False)

        self.chk_corr_sigma_hetero.setToolTip(
            "In LR mode: ?^2 with sigma_i = max(floor, scale?|y_exp-y_th|) on the objective grid.\n"
            "Parametric bootstrap: same sigma_i for Gaussian noise on T/R (objective points only)."
        )

        row_cor_v25.addWidget(self.chk_corr_sigma_hetero)

        self.sp_corr_hetero_scale = QDoubleSpinBox()

        self.sp_corr_hetero_scale.setDecimals(3)

        self.sp_corr_hetero_scale.setRange(0.0, 20.0)

        self.sp_corr_hetero_scale.setSingleStep(0.05)

        self.sp_corr_hetero_scale.setValue(1.0)

        self.sp_corr_hetero_scale.setToolTip("Scale factor on |residual| for sigma_i(lambda) (0 = floor only).")

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("scale sigma(lambda)"))

        row_cor_v25.addWidget(self.sp_corr_hetero_scale)

        self.chk_corr_boot_refit = QCheckBox("fast bootstrap refit (parametric)")

        self.chk_corr_boot_refit.setChecked(False)

        self.chk_corr_boot_refit.setToolTip(
            "After each bootstrap trial: a short L-BFGS-B on (d + nodes) using noisy T/R, "
            "same spectral objective as main run (n,L interp. in sigma = cubic spline), "
            "then profiling in d from this refit (often more consistent than freezing initial mesh)."
        )

        row_cor_v25.addSpacing(12)

        row_cor_v25.addWidget(self.chk_corr_boot_refit)

        self.sp_corr_boot_maxfun = QSpinBox()

        self.sp_corr_boot_maxfun.setRange(0, 200000)

        self.sp_corr_boot_maxfun.setValue(4000)

        self.sp_corr_boot_maxfun.setToolTip(
            "L-BFGS-B maxfun budget per bootstrap refit (0 = disabled even if box is checked)."
        )

        row_cor_v25.addSpacing(6)

        row_cor_v25.addWidget(QLabel("maxfun"))

        row_cor_v25.addWidget(self.sp_corr_boot_maxfun)

        self.sp_corr_boot_workers = QSpinBox()

        self.sp_corr_boot_workers.setRange(1, 64)

        self.sp_corr_boot_workers.setValue(1)

        self.sp_corr_boot_workers.setToolTip(
            "Number of parallel processes for bootstrap replications (1 = sequential). "
            f"Typ. 2-{max(2, multiprocessing.cpu_count() or 4)} on this machine "
            f"({multiprocessing.cpu_count() or '?'} cores). "
            "Pickle or worker failure -> automatic fallback to sequential."
        )

        row_cor_v25.addSpacing(10)

        row_cor_v25.addWidget(QLabel("proc."))

        row_cor_v25.addWidget(self.sp_corr_boot_workers)

        row_cor_v25.addStretch(1)

        w_cor2 = QWidget()

        w_cor2.setLayout(row_cor_v25)

        v_adv.addWidget(w_cor2)

        page_full_adv = QWidget()

        self._box4_full_adv_layout = QVBoxLayout(page_full_adv)

        self._box4_full_adv_layout.setContentsMargins(0, 0, 0, 0)

        self._box4_full_adv_layout.addWidget(self._w_full_adv)

        page_epure = QWidget()

        lay_ep = QVBoxLayout(page_epure)

        lay_ep.setContentsMargins(0, 0, 0, 0)

        btn_open_adv = create_styled_button("Advanced settings...", "secondary")

        btn_open_adv.setToolTip("Optimization budgets and detailed uncertainty / corridor options.")

        btn_open_adv.clicked.connect(self._open_advanced_settings_dialog)

        lay_ep.addWidget(btn_open_adv)

        self._stack_box4_adv = QStackedWidget()

        self._stack_box4_adv.addWidget(page_epure)

        self._stack_box4_adv.addWidget(page_full_adv)

        def _sync_adv_stack_height(_index: int = -1) -> None:
            try:
                current = self._stack_box4_adv.currentWidget()
                if current is None:
                    return
                h = max(1, int(current.sizeHint().height()))
                self._stack_box4_adv.setMinimumHeight(h)
                self._stack_box4_adv.setMaximumHeight(h)
            except (RuntimeError, ValueError):
                self.logger.debug("advanced_settings_stack_height_sync_failed", exc_info=True)

        self._stack_box4_adv.currentChanged.connect(_sync_adv_stack_height)
        QTimer.singleShot(0, _sync_adv_stack_height)

        g4.addWidget(self._stack_box4_adv, r4, 0, 1, 2)

        r4 += 1

        g4.setColumnStretch(1, 1)

        parent_layout.addWidget(box4)

class _ConfigBuilderMixin:
    """Mixin extracting _build_opt_config logic."""

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

        isinstance(getattr(self, "_last_result", None), dict)

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

class _SmartInitDialogMixin:
    """Mixin extracting _show_smart_init_preview_dialog logic."""

    def _show_smart_init_preview_dialog(self, payload: SmartInitPayload) -> bool:
        """Manual Smart Init: PWL n and ln k on K sigma knots.

        If RMSE window is on: uniform sigma^2 mesh on the objective
        (often K=12) then bridge to worker K on Continue.

        Structure (kept monolithic - 29 inner defs share closure state):
          §A  L+0     Config extraction + sigma knot preparation
          §B  L+100   QDialog construction (layouts, widgets, plots)
          §C  L+370   Inner defs: redraw_knot_lines, apply_range, refresh_nk
          §D  L+640   Inner defs: update_axes, rebuild_knot_ui, sync_labels
          §E  L+990   Inner defs: do_recalc, place_nk_editor, run_auto, bumps
          §F  L+1210  Inner defs: recall_best, hint, copy, save/load config
          §G  L+1550  Inner defs: presets, on_autofind, on_keep + init
        """

        cfg = payload.cfg

        sk = payload.sigma_knots

        grids = payload.preview_grids

        logger.info(
            "Smart Init dialog enter | cfg_present=%s | grids_present=%s | payload_K=%d",
            bool(cfg is not None),
            bool(grids is not None),
            int(np.asarray(sk, dtype=np.float64).size),
        )

        if cfg is None or grids is None or sk.size < 2:
            logger.warning(
                "Smart Init dialog early return | cfg_present=%s | grids_present=%s | payload_K=%d",
                bool(cfg is not None),
                bool(grids is not None),
                int(np.asarray(sk, dtype=np.float64).size),
            )

            QMessageBox.warning(
                self,
                "Smart Init",
                "Incomplete preview data (cfg or grids). Continuing without adjustment.",
            )

            return True

        k_n = int(sk.size)

        n_phys = payload.n_nodes_physical.copy()

        L_nodes = payload.L_nodes.copy()

        logger.info(
            "Smart Init dialog payload vectors | len(n)=%d | len(L)=%d | K=%d",
            int(np.asarray(n_phys, dtype=np.float64).size),
            int(np.asarray(L_nodes, dtype=np.float64).size),
            int(k_n),
        )

        if n_phys.size != k_n or L_nodes.size != k_n:
            logger.warning(
                "Smart Init dialog early return | inconsistent vectors len(n)=%d len(L)=%d K=%d",
                int(np.asarray(n_phys, dtype=np.float64).size),
                int(np.asarray(L_nodes, dtype=np.float64).size),
                int(k_n),
            )

            QMessageBox.warning(self, "Smart Init", "n / L sizes are inconsistent with sigma knots.")

            return True

        rel_step = 0.005  # +/-0,5 % sur n et sur L = ln k

        L_lo_g = float(grids["L_lo"])

        L_hi_g = float(grids["L_hi"])

        # During this dialog: free physical n (non-monotone in sigma) if a mono band is active elsewhere;

        # ? monotone reprojection applies on Continue (worker).

        _relax_si_mono = cfg.n_mono_band_nm is not None

        # Nb2O? preset (ref. 12 abscissas in data): on open, Swanepoel is replaced by Nb2O?

        # only if K=12 (legacy). For K=14 (IR extension), keep Swanepoel n/L; user can still

        # apply Nb2O? via ?Apply preset? (interpolation on current sigma grid).

        if sk.size == SPLINE_PWL_K_NODES:
            sk, n_phys, L_nodes, d_total = _project_nb2o5_preset_to_sigma_knots(sk)

            effective_d_best_nm = float(d_total)

            open_preset_name = "nb2o5"

        else:
            effective_d_best_nm = float(payload.d_best_nm)

            open_preset_name = "none"

        # Truncated RMSE lambda window: sigma mesh for +/- columns = uniform in sigma^2 on sig_f (objective), not full spectrum.

        if getattr(cfg, "rmse_fit_lambda_nm", None) is not None:
            sig_f_g = np.asarray(grids["sig_f"], dtype=np.float64).ravel()

            if int(sig_f_g.size) >= 2:
                sk_win = build_smart_manual_sigma_knots_from_preview_grid(sig_f_g, n_uniform_in_sigma2=11)

                n_phys, L_nodes = interp_n_L_pwlnk_to_sigmas(sk, n_phys, L_nodes, sk_win)

                sk = sk_win

                k_n = int(sk.size)

        self.smart_preview_sk_arr = np.asarray(sk, dtype=np.float64).ravel().copy()

        # (sigma, n, L) triplets aligned on the instance: avoids drift vs local n_phys / L_nodes

        # after recomputation (curves, +/-) if other code reads smart_preview_sk_arr alone.

        self.smart_preview_n_phys = np.asarray(n_phys, dtype=np.float64).ravel().copy()

        self.smart_preview_L_nodes = np.asarray(L_nodes, dtype=np.float64).ravel().copy()

        self._si_mesh_sk_snap = self.smart_preview_sk_arr.copy()

        logger.info(
            "Smart Init dialog mesh prepared | sigma_knots_count=%d | rmse_fit_window_nm=%s | preset_applied_on_open=%s",
            int(np.asarray(self.smart_preview_sk_arr, dtype=np.float64).size),
            str(getattr(cfg, "rmse_fit_lambda_nm", None)),
            str(open_preset_name),
        )

        _d0 = effective_d_best_nm

        if _d0 is None or not np.isfinite(float(_d0)):
            preview_d_nm = float(0.5 * (float(cfg.d_lo) + float(cfg.d_hi)))

        else:
            preview_d_nm = float(_d0)

        if str(open_preset_name) == "nb2o5":
            logger.info(
                "Smart Init dialog seed transformation | incoming_payload_d_best_nm=%.6f | nb2o5_preset_d_total_nm=%.6f | "
                "preset_replaces_incoming_d_for_dialog_preview",
                float(payload.d_best_nm),
                float(preview_d_nm),
            )
        else:
            logger.info(
                "Smart Init dialog initial seed | incoming_d_best_nm=%.6f | effective_preview_d_nm=%.6f | preset=%s",
                float(payload.d_best_nm),
                float(preview_d_nm),
                str(open_preset_name),
            )

        _, rm0 = rmse_at_spline_stage_x0_init(
            cfg,
            sk,
            n_phys,
            L_nodes,
            preview_d_nm,
            relax_n_mono=_relax_si_mono,
        )

        best_rmse = float(rm0)

        best_n = n_phys.copy()

        best_L = L_nodes.copy()

        current_rmse = float(rm0)

        logger.info(
            "Smart Init dialog RMSE-at-seed | dialog_d_nm=%.6f | initial_rmse=%.8f",
            float(preview_d_nm),
            float(current_rmse),
        )

        dlg = QDialog(self)

        logger.info("Smart Init dialog QDialog created")

        dlg.setWindowTitle(f"Smart Init  PWL n and ln k ({k_n} sigma knots ? presets Nb2O? ? SiO2 ? Ta2O?)")

        dlg.setMinimumWidth(1180)

        dlg.setMinimumHeight(620)

        # Auxiliary window for n(lambda) and log k(lambda)

        aux_dlg, curve_n, curve_pk, main_vb, p_extra = self._build_smart_init_aux_dialog(dlg)

        logger.info("Smart Init dialog auxiliary window created")

        lay = QVBoxLayout(dlg)

        h_x_main = QHBoxLayout()

        h_x_main.addWidget(QLabel("X axis (spectrum):"))

        cb_x_main = QComboBox()

        cb_x_main.addItems(["Lambda (nm)", "Sigma (nm⁻¹)", "Sigma² (nm⁻²)"])

        h_x_main.addWidget(cb_x_main)

        h_x_main.addStretch()

        lay.addLayout(h_x_main)

        if _relax_si_mono:
            lbl_mono_relax = QLabel(
                "<b>Manual tuning</b>: <i>n</i> may be <b>non-monotone</b> in sigma between knots here "
                "(sliders / editor). <b>After Continue</b>: optimization uses the "
                "<b>? reparametrization</b> - <i>n</i> non-decreasing in sigma on the run?s lambda band "
                "(so in practice <i>n</i> <b>decreasing or quasi-flat</b> as lambda increases on these segments), "
                "plus a penalty (UV-VIS band) if <i>n</i> rises too much with lambda "
                "(small slack on this penalty is configurable)."
            )

            lbl_mono_relax.setWordWrap(True)

            lbl_mono_relax.setStyleSheet(f"color: {CertusTheme.WARNING}; font-size: 11px; padding: 2px 0;")

            lay.addWidget(lbl_mono_relax)

        d_lo_nm = float(cfg.d_lo)

        d_hi_nm = float(cfg.d_hi)

        _D_SLIDER_STEPS = _D_SLIDER_STEPS_DEFAULT

        # _d_from_slider_int / _slider_int_from_d_nm: extracted to module level
        # Capture local context via lambdas
        _d_from_slider = lambda iv: _d_from_slider_int(iv, d_lo_nm, d_hi_nm, _D_SLIDER_STEPS)  # noqa: E731
        _slider_from_d = lambda dv: _slider_int_from_d_nm(dv, d_lo_nm, d_hi_nm, _D_SLIDER_STEPS)  # noqa: E731

        row_d = QHBoxLayout()

        row_d.addWidget(QLabel("Thickness d:"))

        slider_d = QSlider(Qt.Orientation.Horizontal)

        slider_d.setRange(0, _D_SLIDER_STEPS)

        slider_d.setToolTip(
            "Slider between fit d min and d max. The +/- buttons on n and ln k do not change d; "
            "move this slider to try different thickness."
        )

        lbl_d_slider = QLabel()

        lbl_d_slider.setMinimumWidth(220)

        row_d.addWidget(slider_d, 1)

        row_d.addWidget(lbl_d_slider)

        lay.addLayout(row_d)

        btn_show_nk = QPushButton("Display profiles n, ln k (lambda)")

        btn_show_nk.setFixedWidth(200)

        btn_show_nk.clicked.connect(aux_dlg.show)

        lay.addWidget(btn_show_nk)

        lam_src_payload = payload.lam_nm
        if lam_src_payload is None and self.df is not None and "lambda" in self.df.columns:
            lam_src_payload = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning(
                    "Corridor preview dialog: payload missing lam_nm; fallback to experimental lambda grid."
                )
        lam_m = np.asarray(lam_src_payload if lam_src_payload is not None else [], dtype=np.float64)
        if lam_m.size == 0:
            logger.warning("Smart Init dialog: lam_nm unavailable in payload and df; spectrum plot will be empty.")

        y_exp = payload.t_exp

        y_th0 = payload.t_theo

        y_lab = "T/T_sub" if payload.t_is_ratio else "T"

        pw, curve_exp, curve_theo, knot_markers = self._build_smart_init_main_plot(y_lab)

        # get_xv: extracted to module level
        get_xv = _get_xv_spectral_coord

        knot_lines = []

        def redraw_knot_lines() -> None:

            for line in knot_lines:
                try:
                    pw.removeItem(line)

                except (AttributeError, RuntimeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            knot_lines.clear()

            pen_k = pg.mkPen("#1a9f3c", width=1.8)

            mode = cb_x_main.currentText()

            sk_lines = np.asarray(getattr(self, "smart_preview_sk_arr", sk), dtype=np.float64).ravel()

            for sx in sk_lines:
                il = pg.InfiniteLine(get_xv(sx, mode), angle=90, pen=pen_k)

                pw.addItem(il)

                knot_lines.append(il)

        redraw_knot_lines()

        cb_x_main.currentIndexChanged.connect(redraw_knot_lines)

        current_t_th = y_th0.copy()
        state = SmartInitState(
            sk=sk,
            k_n=k_n,
            n_phys=n_phys,
            L_nodes=L_nodes,
            preview_d_nm=preview_d_nm,
            best_rmse=best_rmse,
            best_n=best_n,
            best_L=best_L,
            current_rmse=current_rmse,
            current_t_th=current_t_th,
            best_live=None,
        )

        # _study_lambda_window_nm: extracted to module level
        _study_lambda_window_nm = lambda: _compute_study_lambda_window_nm(lam_m, cfg)  # noqa: E731

        def _apply_manual_spectrum_plot_range() -> None:
            _smart_init_apply_plot_range(
                pw, _study_lambda_window_nm, cb_x_main.currentIndex(),
                getattr(self, "smart_preview_sk_arr", sk), lam_m, y_exp,
                state.current_t_th,
            )

        def refresh_nk_plots_aux(lam_nk: np.ndarray, n_lam: np.ndarray, k_lam: np.ndarray) -> None:
            _smart_init_refresh_nk_aux(
                curve_n, curve_pk, main_vb, p_extra,
                _study_lambda_window_nm, lam_nk, n_lam, k_lam,
            )

        # --- NEW : LIVE INDEX MONITORING ---

        mon = getattr(self, "_live_nk_monitor", None)

        if mon is None or not hasattr(mon, "update_indices"):
            mon = LiveIndexMonitor(self)

            self._live_nk_monitor = mon

        mon._study_lam_window_fn = _study_lambda_window_nm

        mon.show()

        # Positionner a droite du dialog de preview (si visible).

        try:
            mon.move(dlg.x() + dlg.width() + 10, dlg.y())

        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        def refresh_nk_plots_mon(lam_u, n_lam_u, k_lam_u) -> None:

            mon.update_indices(lam_u, n_lam_u, k_lam_u, state.preview_d_nm)

        lbl_stats = QLabel()

        lbl_stats.setWordWrap(True)

        def refresh_stats(dv: float, rm: float) -> None:

            state.current_rmse = float(rm)

            rmse_lbl = "RMSE"

            if cfg.data_type == DataType.BOTH and float(cfg.weight_t) > 0.0 and float(cfg.weight_r) > 0.0:
                rmse_lbl = "RMSE (sqrt(MSE) objective T+R, as in first optimization cost)"

            lbl_stats.setText(_format_smart_init_status_text(state.k_n, dv, rmse_lbl, rm, state.best_rmse))

        refresh_stats(state.preview_d_nm, rm0)

        # Colonnes alignees sous les sigma du plot (espacements  Deltasigma sur l'axe).

        sk_arr = np.asarray(state.sk, dtype=np.float64).ravel()

        sig2_arr = sk_arr**2







        sig_pts = (1.0 / np.maximum(lam_m, 1e-9)) ** 2 if lam_m.size > 0 else sig2_arr

        s2_lo_f = float(min(float(np.min(sig_pts)), float(np.min(sig2_arr))))

        s2_hi_f = float(max(float(np.max(sig_pts)), float(np.max(sig2_arr))))

        span_sig2 = max(s2_hi_f - s2_lo_f, 1e-30)

        def update_main_x_axes() -> None:

            mode = cb_x_main.currentIndex()

            x_L = lam_m

            x_s = 1.0 / np.maximum(lam_m, 1e-30)

            x_s2 = x_s**2

            cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            k_L = 1.0 / np.maximum(cur_sk, 1e-30)

            k_s = cur_sk

            k_s2 = cur_sk**2

            x_vals = [x_L, x_s, x_s2][mode]

            k_vals = [k_L, k_s, k_s2][mode]

            lbl = ["lambda (nm)", "sigma (nm?1)", "sigma2 = 1/lambda2 (nm?2)"][mode]

            pw.setLabel("bottom", lbl)

            o = np.argsort(x_vals)

            curve_exp.setData(x_vals[o], y_exp[o])

            curve_theo.setData(x_vals[o], state.current_t_th[o])

            knot_t = _interp_t_at_lam_knots(lam_m, state.current_t_th, cur_sk)

            knot_markers.setData(k_vals, knot_t)

            for j, il in enumerate(knot_lines):
                if j < len(k_vals):
                    il.setPos(k_vals[j])

            _apply_manual_spectrum_plot_range()

        cb_x_main.currentIndexChanged.connect(update_main_x_axes)

        cb_x_main.setCurrentIndex(2)

        lbl_lam_cols: list[QLabel] = []

        lbl_sig_cols: list[QLabel] = []

        lbl_n_cols: list[QLabel] = []

        lbl_L_cols: list[QLabel] = []

        knot_bar = QWidget()

        knot_h = QHBoxLayout(knot_bar)

        knot_h.setContentsMargins(2, 4, 2, 2)

        knot_h.setSpacing(0)

        # _stretch_sig: extracted to module level
        _stretch_sig = lambda delta: _stretch_sig_to_px(delta, span_sig2)  # noqa: E731

        n_btn_pairs: list[tuple[QPushButton, QPushButton]] = []

        L_btn_pairs: list[tuple[QPushButton, QPushButton]] = []

        n_auto_btns: list[QPushButton] = []

        L_auto_btns: list[QPushButton] = []

        curve_editor_holder: list[SmartInitNKCurveEditorDialog] = []

        def rebuild_knot_ui(new_kn: int) -> None:

            state.k_n = new_kn

            # Vidage du layout actuel

            while knot_h.count():
                item = knot_h.takeAt(0)

                if item.widget():
                    item.widget().deleteLater()

            lbl_lam_cols.clear()

            lbl_sig_cols.clear()

            lbl_n_cols.clear()

            lbl_L_cols.clear()

            n_btn_pairs.clear()

            L_btn_pairs.clear()

            n_auto_btns.clear()

            L_auto_btns.clear()

            # Reconstruction des colonnes

            current_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            sig2_sorted_loc = np.sort(current_sk**2)

            # UPDATE DES MARQUEURS SUR LE GRAPHE (consolide)

            redraw_knot_lines()

            knot_h.addStretch(_stretch_sig(float(sig2_sorted_loc[0] - s2_lo_f)))

            for j in range(state.k_n):
                # ... (creation widgets)

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

                bm_n = QPushButton("")

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

                bm_L = QPushButton("")

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

                if j + 1 < state.k_n:
                    knot_h.addStretch(_stretch_sig(float(sig2_sorted_loc[j + 1] - sig2_sorted_loc[j])))

            # Rewire +/- / auto buttons for the current k_n sigma knots

            current_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            sig2_sorted_loc = np.sort(current_sk**2)

            sig_sort_idx_loc = np.argsort(current_sk)

            # Rewire events

            for j in range(state.k_n):
                oi = int(sig_sort_idx_loc[j])

                bm_n, bp_n = n_btn_pairs[j]

                bm_L, bp_L = L_btn_pairs[j]

                wire_hold_button(bm_n, oi, -1, is_ln_k=False)

                wire_hold_button(bp_n, oi, +1, is_ln_k=False)

                wire_hold_button(bm_L, oi, -1, is_ln_k=True)

                wire_hold_button(bp_L, oi, +1, is_ln_k=True)

                def _run_n_auto(*_args, row_index=oi) -> None:
                    run_auto(row_index, False)

                n_auto_btns[j].clicked.connect(_run_n_auto)

                def _run_l_auto(*_args, row_index=oi) -> None:
                    run_auto(row_index, True)

                L_auto_btns[j].clicked.connect(_run_l_auto)

            sync_knot_labels()

            for _ce in curve_editor_holder:
                try:
                    _ce.refresh_plots()

                except (AttributeError, RuntimeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        knot_bar.setMinimumHeight(140)

        def sync_knot_labels() -> None:

            cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            cur_sort_idx = np.argsort(cur_sk)

            cur_kn = int(cur_sk.size)

            for j in range(cur_kn):
                oi = int(cur_sort_idx[j])

                lam_v = 1.0 / max(float(cur_sk[oi]), 1e-30)

                lbl_lam_cols[j].setText(f"{lam_v:.1f} nm")

                lbl_sig_cols[j].setText(f"{float(cur_sk[oi]):.5f}")

                lbl_n_cols[j].setText(f"{float(state.n_phys[oi]):.4f}")

                lbl_L_cols[j].setText(f"{float(state.L_nodes[oi]):.4f}")

        def sync_d_slider_label() -> None:

            lbl_d_slider.setText(f"{state.preview_d_nm:.2f} nm   [d min={d_lo_nm:.1f}, d max={d_hi_nm:.1f}]")

        def set_slider_from_preview_d() -> None:

            slider_d.blockSignals(True)

            slider_d.setValue(_slider_from_d(state.preview_d_nm))

            slider_d.blockSignals(False)

            sync_d_slider_label()

        def _set_n_knot_curve(i: int, v: float) -> None:

            nn = np.asarray(state.n_phys, dtype=np.float64).copy()

            nn[int(i)] = float(np.clip(v, N_MIN_LIMIT, N_MAX_LIMIT))

            state.n_phys = nn

        def _set_L_knot_curve(i: int, v: float) -> None:

            LL = np.asarray(state.L_nodes, dtype=np.float64).copy()

            LL[int(i)] = float(np.clip(v, L_lo_g, L_hi_g))

            state.L_nodes = LL

        def do_recalc() -> None:

            nonlocal state

            cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            _prev = state
            state = _SmartInitState(
                cur_sk,
                _prev.n_phys,
                _prev.L_nodes,
                _prev.preview_d_nm,
                _prev.best_rmse,
                _prev.best_n,
                _prev.best_L,
                _prev.current_rmse,
                _prev.current_t_th,
            )

            out = self._execute_smart_init_recalc_logic(cfg, grids, _relax_si_mono, state)

            if out is None:
                return

            state.n_phys = state.n_phys.copy()

            state.L_nodes = state.L_nodes.copy()

            state.preview_d_nm = state.preview_d_nm

            state.best_rmse = state.best_rmse

            state.best_n = state.best_n.copy()

            state.best_L = state.best_L.copy()

            state.current_t_th = state.current_t_th

            state.current_rmse = state.current_rmse

            lam_u_src = out.get("lam_nm")

            if lam_u_src is None:
                lam_u_src = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

                if self.logger:
                    self.logger.warning("Smart-init preview: out.lam_nm missing; fallback to cfg.lam_nm.")

            lam_u = np.asarray(lam_u_src, dtype=np.float64).ravel()

            ou = np.argsort((1.0 / np.maximum(lam_u, 1e-9)) ** 2)

            update_main_x_axes()

            lam_uu = lam_u

            sync_knot_labels()

            refresh_stats(state.preview_d_nm, state.current_rmse)

            if "n_lam" in out and "k_lam" in out:
                n_lam_u = np.asarray(out["n_lam"], dtype=np.float64).ravel()

                k_lam_u = np.asarray(out["k_lam"], dtype=np.float64).ravel()

                refresh_nk_plots_aux(lam_uu[ou], n_lam_u[ou], k_lam_u[ou])

                refresh_nk_plots_mon(lam_uu[ou], n_lam_u[ou], k_lam_u[ou])

            for _ce in curve_editor_holder:
                try:
                    _ce.refresh_plots()

                except (AttributeError, RuntimeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        _nk_curve_editor = SmartInitNKCurveEditorDialog(
            dlg,
            n_lo=float(N_MIN_LIMIT),
            n_hi=float(N_MAX_LIMIT),
            L_lo=float(L_lo_g),
            L_hi=float(L_hi_g),
            k_clip_lo=float(getattr(cfg, "k_clip_lo", 1e-30) or 1e-30),
            get_sk=lambda: np.asarray(getattr(self, "smart_preview_sk_arr", sk_arr), dtype=np.float64).ravel(),
            get_n_phys=lambda: state.n_phys,
            get_L_nodes=lambda: state.L_nodes,
            set_n_at=_set_n_knot_curve,
            set_L_at=_set_L_knot_curve,
            request_recalc=do_recalc,
            study_lambda_window=_study_lambda_window_nm,
        )

        curve_editor_holder.append(_nk_curve_editor)

        _nk_curve_editor.show()

        def _place_nk_editor() -> None:

            try:
                fr = dlg.frameGeometry()

                _nk_curve_editor.move(
                    max(24, fr.left() - _nk_curve_editor.width() - 20),
                    fr.top() + 32,
                )

            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        QTimer.singleShot(0, _place_nk_editor)

        def run_auto(row: int, is_ln_k: bool) -> None:
            nonlocal state

            _prev = state
            state = _SmartInitState(
                sk=getattr(self, "smart_preview_sk_arr", sk_arr),
                n_phys=_prev.n_phys,
                L_nodes=_prev.L_nodes,
                preview_d_nm=_prev.preview_d_nm,
                best_rmse=_prev.best_rmse,
                best_n=_prev.best_n,
                best_L=_prev.best_L,
                current_rmse=_prev.current_rmse,
                current_t_th=_prev.current_t_th,
            )

            err = self._execute_smart_init_run_auto(cfg, row, is_ln_k, L_lo_g, L_hi_g, _relax_si_mono, state)
            if err:
                QMessageBox.warning(dlg, "Smart Init  auto", f"run auto failed: {err}")
                return

            state.n_phys = state.n_phys.copy()
            state.L_nodes = state.L_nodes.copy()
            state.preview_d_nm = state.preview_d_nm

            set_slider_from_preview_d()
            do_recalc()

        def on_slider_d_changed(_iv: int) -> None:

            state.preview_d_nm = _d_from_slider(slider_d.value())

            sync_d_slider_label()

            do_recalc()

        slider_d.valueChanged.connect(on_slider_d_changed)

        set_slider_from_preview_d()

        def bump_n_scaled(row: int, direction: int, mult: float) -> None:

            step = rel_step * float(mult)

            f = 1.0 + float(direction) * step

            state.n_phys[row] = float(np.clip(state.n_phys[row] * f, N_MIN_LIMIT, N_MAX_LIMIT))

            do_recalc()

        def bump_L_scaled(row: int, direction: int, mult: float) -> None:

            step = rel_step * float(mult)

            f = 1.0 + float(direction) * step

            state.L_nodes[row] = float(np.clip(state.L_nodes[row] * f, L_lo_g, L_hi_g))

            do_recalc()

        def wire_hold_button(
            btn: QPushButton,
            row: int,
            direction: int,
            *,
            is_ln_k: bool,
        ) -> None:

            t = QTimer(dlg)

            t.setInterval(78)

            ntick: list[int] = [0]

            def on_tick() -> None:

                ntick[0] += 1

                mult = min(24.0, 1.0 + (ntick[0] - 1) * 0.85)

                if is_ln_k:
                    bump_L_scaled(row, direction, mult)

                else:
                    bump_n_scaled(row, direction, mult)

            t.timeout.connect(on_tick)

            def on_press() -> None:

                ntick[0] = 1

                if is_ln_k:
                    bump_L_scaled(row, direction, 1.0)

                else:
                    bump_n_scaled(row, direction, 1.0)

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

        def recall_best() -> None:
            nonlocal state

            _prev = state
            state = _SmartInitState(
                sk=getattr(self, "smart_preview_sk_arr", sk_arr),
                n_phys=_prev.n_phys,
                L_nodes=_prev.L_nodes,
                preview_d_nm=_prev.preview_d_nm,
                best_rmse=_prev.best_rmse,
                best_n=_prev.best_n,
                best_L=_prev.best_L,
                current_rmse=_prev.current_rmse,
                current_t_th=_prev.current_t_th,
            )

            err = self._execute_smart_init_recall_best(state)
            if err:
                QMessageBox.information(dlg, "Smart Init", err)
                return

            state.n_phys = state.n_phys.copy()
            state.L_nodes = state.L_nodes.copy()
            do_recalc()

        rebuild_knot_ui(state.k_n)  # Appel initial  ici wire_hold_button est deja defini

        attach_excel_clipboard_context_menu(pw)

        lay.addWidget(wrap_scientific_plot_with_toolbar(dlg, pw), stretch=1)

        lbl_nodes = QLabel(
            f"<b>Knot adjustment (increasing sigma)</b> - <b>n &amp; k Editor</b> window on the left: drag points "
            f"(<i>k</i> in log); here: <b>- / +</b> +/-{100 * rel_step:.1f} % on <i>n</i> and <i>L</i> (= ln <i>k</i>), "
            f"<b>without</b> auto thickness recalculation (d slider above); "
            f"<b>hold down</b> to accelerate; <b>auto</b>: d + param sweep <=3 s."
        )

        lbl_nodes.setWordWrap(True)

        lbl_nodes.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(lbl_nodes)

        lay.addWidget(knot_bar)

        lay.addWidget(lbl_stats)

        row_hint = QHBoxLayout()

        lbl_row_hint = QLabel()

        def update_hint_text() -> None:

            # Help text: same K as worker after Continue (avoids claiming ?12 knots? for a 5 ?m file).

            lam_h = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()

            k_h = int(
                canonical_spline_sigma_knots(
                    float(np.nanmin(lam_h)),
                    float(np.nanmax(lam_h)),
                    **_canonical_knots_min_lambda_kw(cfg),
                ).size
            )

            n_h = max(1, k_h - 1)

            lbl_row_hint.setText(
                f" Continue: fixed mesh {k_h} sigma knots, {n_h} segments between knots "
                "(canonical grid [lambda_min, lambda_max]); local refinement; knots and RMSE logged in CERTUS."
            )

        update_hint_text()

        row_hint.addWidget(lbl_row_hint, stretch=1)

        btn_recall = QPushButton("Recall best")

        btn_recall.setToolTip("Restore n and ln k profiles with the lowest RMSE since dialog start.")

        btn_recall.clicked.connect(recall_best)

        btn_copy = QPushButton("Copy to clipboard")

        def on_copy() -> None:

            cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)

            lines = [f"RMSE: {state.current_rmse:.8f}", f"d: {state.preview_d_nm:.6f} nm", "Nodes (sigma, n, ln k):"]

            for idx in np.argsort(cur_sk):
                lines.append(f"  {cur_sk[idx]:.8e} | {state.n_phys[idx]:.6f} | {state.L_nodes[idx]:.6f}")

            QApplication.clipboard().setText("\n".join(lines))

            btn_copy.setText("Copied!")

            QTimer.singleShot(1500, lambda: btn_copy.setText("Copy to clipboard"))

        btn_copy.clicked.connect(on_copy)

        row_hint.addWidget(btn_copy)

        row_hint.addWidget(btn_recall)

        def _refresh_knot_lines_and_ui() -> None:
            for line in knot_lines:
                try:
                    pw.removeItem(line)
                except (AttributeError, RuntimeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
            knot_lines.clear()

            pen_k = pg.mkPen("#1a9f3c", width=1.8)
            mode = cb_x_main.currentText()
            for sx in state.sk:
                il = pg.InfiniteLine(get_xv(sx, mode), angle=90, pen=pen_k)
                pw.addItem(il)
                knot_lines.append(il)

            rebuild_knot_ui(int(len(state.sk)))
            set_slider_from_preview_d()
            do_recalc()

        def _serialize_smart_init_index_config() -> dict[str, Any]:
            cur_sk = np.asarray(getattr(self, "smart_preview_sk_arr", state.sk), dtype=np.float64).ravel()
            cur_n = np.asarray(state.n_phys, dtype=np.float64).ravel()
            cur_L = np.asarray(state.L_nodes, dtype=np.float64).ravel()
            return {
                "schema": "certus.index_spline.smart_init.index_config.v1",
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "x_axis_mode": str(cb_x_main.currentText()),
                "d_nm": float(state.preview_d_nm),
                "sigma_knots": [float(v) for v in cur_sk.tolist()],
                "n_nodes_physical": [float(v) for v in cur_n.tolist()],
                "L_nodes": [float(v) for v in cur_L.tolist()],
            }

        def on_save_index_config() -> None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            default_path = str(Path.cwd() / f"smart_init_index_config_{ts}.json")
            path, _ = QFileDialog.getSaveFileName(
                dlg,
                "Save index config (Smart Init)",
                default_path,
                "JSON Files (*.json);;All Files (*.*)",
            )
            if not path:
                return
            if not path.lower().endswith(".json"):
                path += ".json"

            payload_cfg = _serialize_smart_init_index_config()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload_cfg, f, indent=2)
            except (OSError, TypeError, ValueError) as exc:
                QMessageBox.warning(dlg, "Save index config", f"Save failed: {exc}")
                return

            btn_save_cfg.setText("Saved")
            QTimer.singleShot(1200, lambda: btn_save_cfg.setText("Save As"))

        def on_load_index_config() -> None:
            path, _ = QFileDialog.getOpenFileName(
                dlg,
                "Load index config (Smart Init)",
                "",
                "JSON Files (*.json);;All Files (*.*)",
            )
            if not path:
                return

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                QMessageBox.warning(dlg, "Load index config", f"Load failed: {exc}")
                return

            loaded_sk = np.asarray(data.get("sigma_knots", []), dtype=np.float64).ravel()
            loaded_n = np.asarray(data.get("n_nodes_physical", []), dtype=np.float64).ravel()
            loaded_L = np.asarray(data.get("L_nodes", []), dtype=np.float64).ravel()
            loaded_d = float(data.get("d_nm", state.preview_d_nm))

            if loaded_sk.size < 2:
                QMessageBox.warning(dlg, "Load index config", "Invalid config: need at least 2 sigma knots.")
                return
            if loaded_n.size != loaded_sk.size or loaded_L.size != loaded_sk.size:
                QMessageBox.warning(dlg, "Load index config", "Invalid config: knot vector sizes are inconsistent.")
                return
            if not (
                np.all(np.isfinite(loaded_sk))
                and np.all(np.isfinite(loaded_n))
                and np.all(np.isfinite(loaded_L))
                and np.isfinite(loaded_d)
            ):
                QMessageBox.warning(dlg, "Load index config", "Invalid config: contains non-finite values.")
                return

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
            self.smart_preview_sig2 = self.smart_preview_sk_arr**2

            _refresh_knot_lines_and_ui()

            btn_load_cfg.setText("Loaded")
            QTimer.singleShot(1200, lambda: btn_load_cfg.setText("Load"))

        btn_save_cfg = QPushButton("Save As")
        btn_save_cfg.setToolTip("Save current Smart Init index configuration (sigma, n, ln k, d) to JSON.")
        btn_save_cfg.clicked.connect(on_save_index_config)

        btn_load_cfg = QPushButton("Load")
        btn_load_cfg.setToolTip("Load a Smart Init index configuration from JSON and apply it to the dialog.")
        btn_load_cfg.clicked.connect(on_load_index_config)

        row_hint.addWidget(btn_save_cfg)
        row_hint.addWidget(btn_load_cfg)

        def apply_manual_preset_from_projector(
            projector: Callable[[np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray, float]],
            feedback_btn: QPushButton | None,
            idle_label: str,
        ) -> None:

            nonlocal state

            _prev = state
            state = _SmartInitState(
                sk=_prev.sk,
                n_phys=_prev.n_phys,
                L_nodes=_prev.L_nodes,
                preview_d_nm=_prev.preview_d_nm,
                best_rmse=_prev.best_rmse,
                best_n=_prev.best_n,
                best_L=_prev.best_L,
                current_rmse=_prev.current_rmse,
                current_t_th=_prev.current_t_th,
            )

            self._execute_smart_init_preset_logic(cfg, projector, _relax_si_mono, state)

            state.sk = self.smart_preview_sk_arr = state.sk.copy()
            state.n_phys = self.smart_preview_n_phys = state.n_phys.copy()
            state.L_nodes = self.smart_preview_L_nodes = state.L_nodes.copy()
            state.preview_d_nm = self.smart_preview_d_nm = state.preview_d_nm
            self.smart_preview_sig2 = self.smart_preview_sk_arr**2

            _refresh_knot_lines_and_ui()

            if feedback_btn is not None:
                feedback_btn.setText(f"OK - {len(state.sk)} nodes")
                QTimer.singleShot(1500, lambda b=feedback_btn, t=idle_label: b.setText(t))

        cb_material_preset = QComboBox()

        cb_material_preset.setMinimumWidth(168)

        cb_material_preset.setToolTip(
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
            cb_material_preset.addItem(_label, _pid)

        btn_apply_material = QPushButton("Apply preset")

        def on_apply_material_preset() -> None:

            pid = str(cb_material_preset.currentData() or "nb2o5")

            dh = float(state.preview_d_nm)

            def _run(ts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:

                return project_manual_material_preset(pid, ts, d_nm_hint=dh)

            apply_manual_preset_from_projector(_run, btn_apply_material, "Apply preset")

        btn_apply_material.clicked.connect(on_apply_material_preset)

        row_hint.addWidget(cb_material_preset)

        row_hint.addWidget(btn_apply_material)

        def _auto_try_three_material_presets() -> None:
            """Compares Nb2O? / SiO2 / Ta2O? on the current sigma grid and applies the best one (mini-opt d)."""
            target_sk = np.asarray(getattr(self, "smart_preview_sk_arr", sk_arr), dtype=np.float64).ravel()
            if int(target_sk.size) < 2:
                return

            res = self._pick_best_smart_init_material_preset(cfg, target_sk, state.preview_d_nm, bool(_relax_si_mono))
            if res is None:
                return
            winner, rm_w, d_w = res

            state.preview_d_nm = float(d_w)
            iw = cb_material_preset.findData(winner)
            if iw >= 0:
                cb_material_preset.blockSignals(True)
                try:
                    cb_material_preset.setCurrentIndex(int(iw))
                finally:
                    cb_material_preset.blockSignals(False)

            def _proj(ts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
                return project_manual_material_preset(winner, ts, d_nm_hint=float(state.preview_d_nm))

            apply_manual_preset_from_projector(_proj, None, "")

        btn_autofind = QPushButton("Autofind")

        btn_autofind.setToolTip(
            "SOL2 only (~30 s): local L-BFGS-B polish on fixed sigma (canonical file mesh), "
            "without free-node stage or full pipeline suite. Seed = current profile re-interpolated in PWL."
        )

        autofind_prog = QProgressBar()

        autofind_prog.setRange(0, 100)

        autofind_prog.setValue(0)

        autofind_prog.setMinimumWidth(220)

        autofind_prog.setFormat("Autofind 0% (0.0/30.0s)")

        def on_autofind() -> None:

            cur_sk = np.asarray(getattr(self, "smart_preview_sk_arr", sk_arr), dtype=np.float64).ravel()

            if cur_sk.size < 2:
                QMessageBox.warning(dlg, "Autofind", "Invalid knot grid.")

                return

            if state.n_phys.size != cur_sk.size or state.L_nodes.size != cur_sk.size:
                QMessageBox.warning(
                    dlg,
                    "Autofind",
                    "Current n / ln k vectors are inconsistent with knot count.",
                )

                return

            try:
                auto_cfg, sk_canon, k_loc = self._prepare_smart_init_autofind_config(
                    cfg, cur_sk, state.n_phys, state.L_nodes, state.preview_d_nm
                )

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as exc:
                QMessageBox.warning(dlg, "Autofind", f"Preparation failed: {exc}")

                return

            btn_autofind.setEnabled(False)

            autofind_prog.setValue(0)

            autofind_prog.setFormat("Autofind 0% (0.0/30.0s)")

            prev_txt = btn_autofind.text()

            btn_autofind.setText("Autofind...")

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            import threading

            timeout_s = 30.0
            stop_ev = Event()
            done_ev = threading.Event()
            result_box: dict[str, Any] = {"best": None, "error": None}
            state.best_live: dict[str, Any] | None = None
            t0 = time.perf_counter()
            timer = QTimer(dlg)
            timer.setInterval(50)

            def _live_capture(payload: dict[str, Any]) -> None:

                if not isinstance(payload, dict):
                    return
                try:
                    rm = float(payload.get("rmse", float("inf")))
                except (TypeError, ValueError):
                    rm = float("inf")
                if not np.isfinite(rm):
                    return
                if state.best_live is None or rm < float(state.best_live.get("rmse", float("inf"))):
                    state.best_live = dict(payload)

            def _run_autofind() -> None:

                try:
                    # Single SOL2 stage (fixed sigma): not the complete pipeline (free nodes /
                    # spectral polish), which could greatly exceed UI budget and change K.
                    res_sol2, _ = _run_single_spline_stage(
                        auto_cfg,
                        stop_ev,
                        lambda _pc, _msg: None,
                        live_cb=_live_capture,
                        pipeline_seq="AUTOFIND_SOL2",
                        fatal_finish=None,
                    )
                    result_box["best"] = res_sol2
                except NUMERICAL_FAULT_EXCEPTIONS as exc:
                    result_box["error"] = exc
                finally:
                    done_ev.set()

            def _apply_autofind_result(best: dict[str, Any]) -> None:

                nonlocal state

                _prev = state
                state = _SmartInitState(
                    sk=_prev.sk,
                    n_phys=_prev.n_phys,
                    L_nodes=_prev.L_nodes,
                    preview_d_nm=_prev.preview_d_nm,
                    best_rmse=_prev.best_rmse,
                    best_n=_prev.best_n,
                    best_L=_prev.best_L,
                    current_rmse=_prev.current_rmse,
                    current_t_th=_prev.current_t_th,
                )

                size_match = self._apply_smart_init_autofind_result(best, k_loc, sk_canon, state)
                if not size_match:
                    QMessageBox.warning(
                        dlg,
                        "Autofind",
                        f"SOL2 result ignored for n/L sizes expected {k_loc} - keeping current profile, only d updated.",
                    )

                # Sync back to closure
                state.sk = state.sk
                state.n_phys = state.n_phys
                state.L_nodes = state.L_nodes
                state.preview_d_nm = state.preview_d_nm
                state.current_rmse = state.current_rmse
                state.best_rmse = state.best_rmse
                state.best_n = state.best_n
                state.best_L = state.best_L

                if size_match:
                    self.smart_preview_sk_arr = np.asarray(sk_canon, dtype=np.float64).copy()
                    self.smart_preview_n_phys = np.asarray(state.n_phys, dtype=np.float64).ravel().copy()
                    self.smart_preview_L_nodes = np.asarray(state.L_nodes, dtype=np.float64).ravel().copy()
                    self._si_mesh_sk_snap = self.smart_preview_sk_arr.copy()
                    rebuild_knot_ui(k_loc)
                    update_hint_text()

                set_slider_from_preview_d()
                do_recalc()
                refresh_stats(state.preview_d_nm, state.current_rmse)
                btn_autofind.setText("Autofind completed")
                QTimer.singleShot(1500, lambda: btn_autofind.setText("Autofind"))

            def _finish_autofind(timeout_hit: bool) -> None:
                timer.stop()
                QApplication.restoreOverrideCursor()
                btn_autofind.setEnabled(True)
                btn_autofind.setText(prev_txt)

                if timeout_hit:
                    stop_ev.set()
                    if not isinstance(result_box.get("best"), dict):
                        result_box["best"] = state.best_live if isinstance(state.best_live, dict) else None

                if result_box.get("error") is not None and result_box.get("best") is None:
                    QMessageBox.warning(dlg, "Autofind", f"SOL2 local search failed: {result_box['error']}")
                    return

                best = result_box.get("best")
                if not isinstance(best, dict):
                    if isinstance(state.best_live, dict):
                        best = state.best_live
                    else:
                        QMessageBox.warning(
                            dlg,
                            "Autofind",
                            "SOL2 local search failed: timeout without any useful RMSE snapshot.",
                        )
                        return

                autofind_prog.setValue(100)
                autofind_prog.setFormat(f"Autofind 100% ({timeout_s:.1f}/{timeout_s:.1f}s)")

                try:
                    _apply_autofind_result(best)
                except NUMERICAL_FAULT_EXCEPTIONS as exc:
                    QMessageBox.warning(dlg, "Autofind", f"Error when applying Autofind result: {exc}")

            def _tick_autofind() -> None:
                elapsed = max(0.0, time.perf_counter() - t0)
                elapsed_clamped = min(elapsed, timeout_s)
                pct = int(min(99, max(0, round(100.0 * elapsed_clamped / max(timeout_s, 1e-9)))))
                autofind_prog.setValue(pct)
                autofind_prog.setFormat(f"Autofind {pct}% ({elapsed_clamped:.1f}/{timeout_s:.1f}s)")

                if done_ev.is_set():
                    _finish_autofind(timeout_hit=False)
                    return

                if elapsed >= timeout_s:
                    _finish_autofind(timeout_hit=True)

            th = threading.Thread(target=_run_autofind, daemon=True)
            th.start()
            timer.timeout.connect(_tick_autofind)
            timer.start()

        btn_autofind.clicked.connect(on_autofind)

        row_hint.addWidget(btn_autofind)

        row_hint.addWidget(autofind_prog)

        lay.addLayout(row_hint)

        chk_si_deep = QCheckBox("Deep SOL2 after Smart Init (legacy option inactive in local-only mode)")

        chk_si_deep.setChecked(False)

        chk_si_deep.setToolTip(
            "Manual Smart Init is now always handed off to the worker in local L-BFGS-B mode. "
            "This legacy option is kept visible only for compatibility and has no effect."
        )

        chk_si_deep.setEnabled(False)

        lay.addWidget(chk_si_deep)

        chk_si_two_phase = QCheckBox("Two-phase deep SOL2 (legacy option inactive in local-only mode)")

        chk_si_two_phase.setChecked(False)

        chk_si_two_phase.setToolTip(
            "Legacy compatibility flag only; no second global phase exists anymore in local-only mode."
        )

        chk_si_two_phase.setEnabled(False)

        lay.addWidget(chk_si_two_phase)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Continue optimization")

        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Stop")

        _on_keep_called = [False]

        def on_keep() -> None:
            if _on_keep_called[0]:
                logger.debug("Smart Init on_keep: guard active, ignoring reentrant call")
                return
            _on_keep_called[0] = True
            try:
                ui_ctx = {
                    "chk_si_deep": chk_si_deep,
                    "chk_si_two_phase": chk_si_two_phase,
                    "relax_si_mono": _relax_si_mono,
                }
                nonlocal state

                _prev = state
                state = _SmartInitState(
                    sk=_prev.sk,
                    n_phys=_prev.n_phys,
                    L_nodes=_prev.L_nodes,
                    preview_d_nm=_prev.preview_d_nm,
                    best_rmse=_prev.best_rmse,
                    best_n=_prev.best_n,
                    best_L=_prev.best_L,
                    current_rmse=_prev.current_rmse,
                    current_t_th=_prev.current_t_th,
                )
                self._on_smart_init_keep(dlg, cfg, state, ui_ctx)
            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
                logger.exception("Smart Init on_keep: exception in _on_smart_init_keep")
                _on_keep_called[0] = False

        # --- INITIALISATION IMMEDIATE ---

        rebuild_knot_ui(state.k_n)

        do_recalc()

        _auto_try_three_material_presets()

        bb.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(on_keep)

        bb.rejected.connect(dlg.reject)

        lay.addWidget(bb)

        logger.info("Smart Init dialog immediate init start")

        _apply_manual_spectrum_plot_range()

        logger.info("Smart Init dialog manual plot range applied")

        logger.info("Smart Init dialog entering exec()")

        _code = dlg.exec()

        logger.info(
            "Smart Init dialog exec finished | code=%s | accepted=%s | preview_ret=%s",
            int(_code),
            bool(_code == QDialog.DialogCode.Accepted),
            getattr(self, "_preview_ret", None) is not None,
        )

        return _code == QDialog.DialogCode.Accepted

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

        curve_n = pw_nk.plot(pen=pg.mkPen(CertusTheme.PRIMARY, width=2), name="n(lambda)")

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
            logger.warning("Smart Init hook: QApplication missing, continuing without dialog.")

            return True

        self._preview_ret = None

        if QThread.currentThread() == app.thread():
            logger.info("Smart Init hook: already on GUI thread -> direct dialog call")

            return self._show_smart_init_preview_dialog(payload)

        # Thread worker -> GUI: demander explicitement la preview via signal Qt.

        self._preview_payload = payload

        self._preview_result = True

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
            logger.warning("Smart Init preview: GUI timeout (600s), continuing optimization.")

            return True

        if ret_tuple is not None:
            return True

        return bool(getattr(self, "_preview_result", True))

class _CorridorWorkerMixin:
    """Mixin containing corridor worker callbacks and plot tab."""

    def _finish_corridor_rmse_d_grid_worker_done(self, result: object) -> None:
        """Fin du worker grille RMSE(d): fusion profile_d*, UI, adoption du meilleur global. Pas pour un dict solveur."""
        self._worker_role = "idle"

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self._set_corridor_grid_busy(False)

        self._corridor_rmse_grid_live_t0 = float("nan")
        self._corridor_rmse_live_last_plot_ts = float("nan")

        if not isinstance(result, dict):
            self.lbl_status.setText("RMSE(d) grid: canceled or invalid result.")

            if self.logger:
                self.logger.warning("RMSE(d) grid worker finished without dict result.")

            return

        if self.logger:
            d_dbg = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            r_dbg = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            n_nan_d = int(np.sum(~np.isfinite(d_dbg))) if d_dbg.size else 0
            n_nan_r = int(np.sum(~np.isfinite(r_dbg))) if r_dbg.size else 0
            cov_req = _safe_int_from_mapping(result, "profile_d_manual_grid_requested_base_points", -1)
            cov_ret = _safe_int_from_mapping(result, "profile_d_manual_grid_returned_base_points", -1)
            cov_miss = _safe_int_from_mapping(result, "profile_d_manual_grid_missing_after_emergency", -1)
            cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
            self.logger.info(
                "GUI RMSE(d) regular grid done [order A:result-received] | points=%d | nan(d)=%d | nan(rmse)=%d | coverage requested/returned/missing=%d/%d/%d | complete=%s",
                int(d_dbg.size),
                int(n_nan_d),
                int(n_nan_r),
                int(cov_req),
                int(cov_ret),
                int(cov_miss),
                "yes" if cov_ok else "no",
            )
            if d_dbg.size and r_dbg.size == d_dbg.size:
                fg_c = np.isfinite(d_dbg) & np.isfinite(r_dbg)
                if np.any(fg_c):
                    df = d_dbg[fg_c]
                    rf = r_dbg[fg_c]
                    j_min = int(np.argmin(rf))
                    j_max = int(np.argmax(rf))
                    d0_seed = result.get("profile_d_manual_grid_d0_seed_nm")
                    d_nom_pack = result.get("profile_d_manual_grid_nominal_pack_d_nm")
                    d0_txt = f"{float(d0_seed):.6f}" if d0_seed is not None and np.isfinite(float(d0_seed)) else "n/a"
                    d_nom_txt = (
                        f"{float(d_nom_pack):.6f}"
                        if d_nom_pack is not None and np.isfinite(float(d_nom_pack))
                        else "n/a"
                    )
                    self.logger.info(
                        "GUI RMSE(d) regular grid done [order A-ext:curve-on-receive] | d_nm[min,max]=[%.6f,%.6f] | "
                        "rmse[min,max]=[%.8f,%.8f] | curve_min(d,rmse)=(%.6f,%.8f) | curve_max(d,rmse)=(%.6f,%.8f) | "
                        "visit_first_d_nm=%s | nominal_pack_d_nm=%s",
                        float(np.min(df)),
                        float(np.max(df)),
                        float(np.min(rf)),
                        float(np.max(rf)),
                        float(df[j_min]),
                        float(rf[j_min]),
                        float(df[j_max]),
                        float(rf[j_max]),
                        d0_txt,
                        d_nom_txt,
                    )

        # --- GAP HEALING LOGIC (UX) ---
        # 1. Identify what we have and remove peaks for baseline
        d_raw = np.asarray(result.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_raw = np.asarray(result.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        snapshots = result.get("profile_d_full_results", [])

        # Filter peaks iteratively to find the "trustworthy" monotonic baseline
        order = np.argsort(d_raw)
        df, rf = d_raw[order], r_raw[order]
        snap_f = [snapshots[i] for i in order] if len(snapshots) == len(d_raw) else []

        d_mono, r_mono = _filter_rmse_peaks_iteratively(df, rf)
        # Find indices of monotonic points in the sorted list
        mono_indices = []
        if len(snap_f) > 0:
            for dm in d_mono:
                idx = np.where(np.abs(df - dm) < 1e-9)[0]
                if idx.size > 0:
                    mono_indices.append(idx[0])

        # 2. Check for GAPS relative to requested grid
        requested = getattr(self, "_corridor_rmse_requested_grid", np.array([]))
        tasks = []
        if requested.size > 0 and len(snap_f) > 0 and len(mono_indices) > 0:
            for d_req in requested:
                # Is it missing?
                if not np.any(np.abs(d_mono - d_req) < 1e-4):
                    # FIND BEST NEIGHBOR in monotonic set
                    dist = np.abs(d_mono - d_req)
                    # We look for immediate neighbors (left/right)
                    # but actually any nearby monotonic point is a good seed.
                    # As requested: "best among left/right neighbors"
                    side_indices = np.where(dist < 2.1 * (requested[1] - requested[0] if requested.size > 1 else 1.0))[
                        0
                    ]
                    if side_indices.size > 0:
                        # Best among those nearby
                        best_side_sub_idx = side_indices[np.argmin(r_mono[side_indices])]
                        global_idx_in_snap_f = mono_indices[best_side_sub_idx]
                        seed_snap = snap_f[global_idx_in_snap_f]
                        tasks.append((float(d_req), seed_snap))

        if tasks and str(getattr(self, "_worker_role", "") or "") != "rmse_heal":
            if self.logger:
                self.logger.info("GUI RMSE(d) Grid Healing | Launching healer for %d gaps", len(tasks))
            heal_tasks = list(tasks)
            QTimer.singleShot(0, lambda t=heal_tasks: self._launch_corridor_rmse_gap_heal(t))
            return

        # Continuing finalization...
        upd = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        for k, v in result.items():
            if str(k).startswith("profile_d") or str(k).startswith("corridor_"):
                upd[k] = v

        self._last_result = upd

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        try:
            self._plot_corridor_rmse_tab(upd)

        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.debug("Corridor RMSE tab refresh after manual grid failed", exc_info=True)

        n_ok = int(np.asarray(upd.get("profile_d_values_nm", [])).size)

        n_tot = int(result.get("profile_d_manual_grid_total_points", n_ok))
        n_base_done = int(result.get("profile_d_manual_grid_base_done_points", min(n_ok, n_tot)) or min(n_ok, n_tot))
        n_extra_done = int(
            result.get("profile_d_manual_grid_extra_done_points", max(0, n_ok - n_tot)) or max(0, n_ok - n_tot)
        )

        self._set_corridor_grid_progress_ui(
            done=n_ok,
            total=n_tot,
            base_done=n_base_done,
            base_total=n_tot,
            extra_done=n_extra_done,
        )

        self._set_corridor_grid_completed_badge()

        n_bp = int(result.get("profile_d_manual_grid_breakpoint_count", 0))

        n_extra = int(result.get("profile_d_manual_grid_extra_points", 0))

        n_glob_runs = int(result.get("profile_d_manual_grid_global_opt_runs", 0))

        n_glob_imp = int(result.get("profile_d_manual_grid_global_opt_improved", 0))

        rmse_glob_best = float(result.get("profile_d_manual_grid_best_global_rmse", float("nan")))

        t_ms = float(result.get("profile_d_manual_grid_elapsed_ms", float("nan")))

        self.lbl_status.setText(
            f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | "
            f"global_opt={n_glob_runs}/{n_glob_imp} | {t_ms:.0f} ms"
            if np.isfinite(t_ms)
            else f"RMSE(d) grid finished | {n_ok} points | breakpoints={n_bp} | extra={n_extra} | global_opt={n_glob_runs}/{n_glob_imp}"
        )

        if self.logger:
            self.logger.info(
                "GUI RMSE(d) regular grid done | n_points=%d | breakpoints=%d | extra_points=%d | global_opt_runs=%d | global_opt_improved=%d | best_global_rmse=%s | elapsed_ms=%s",
                n_ok,
                int(n_bp),
                int(n_extra),
                int(n_glob_runs),
                int(n_glob_imp),
                f"{rmse_glob_best:.8f}" if np.isfinite(rmse_glob_best) else "n/a",
                f"{t_ms:.1f}" if np.isfinite(t_ms) else "n/a",
            )

        best_global_result = result.get("profile_d_manual_grid_best_global_result")
        curve_minimum_result = result.get("profile_d_manual_grid_curve_minimum_result")
        curve_beats = bool(result.get("profile_d_manual_grid_curve_beats_nominal", False))
        grid_cov_ok = bool(result.get("profile_d_manual_grid_coverage_complete", False))
        delta_curve = float(result.get("profile_d_manual_grid_curve_vs_nominal_delta_rmse", float("nan")))

        rmse_best_global = (
            self._rmse_from_result_dict(best_global_result) if isinstance(best_global_result, dict) else float("nan")
        )
        rmse_curve = (
            self._rmse_from_result_dict(curve_minimum_result)
            if isinstance(curve_minimum_result, dict)
            else float("nan")
        )

        cand_global_ok = bool(
            int(n_glob_imp) > 0 and isinstance(best_global_result, dict) and np.isfinite(rmse_best_global)
        )
        cand_curve_ok = bool(curve_beats and isinstance(curve_minimum_result, dict) and np.isfinite(rmse_curve))

        if int(n_glob_imp) > 0 and (not cand_global_ok) and self.logger:
            self.logger.warning(
                "GUI RMSE(d) regular grid | global_opt_improved=%d but best_global_result missing/invalid rmse.",
                int(n_glob_imp),
            )

        chosen_seed: dict[str, Any] | None = None
        chosen_origin = ""
        chosen_log_tag = ""
        chosen_status = ""
        if cand_global_ok and cand_curve_ok:
            if rmse_curve < rmse_best_global:
                chosen_seed = dict(curve_minimum_result)
                chosen_origin = "corridor-profile-curve-minimum"
                chosen_log_tag = "order C2:corridor-curve-min-promoted-over-global-opt"
                chosen_status = (
                    "RMSE(d): minimum de courbe corridor promu (meilleur que global-opt), auto-refine en cours..."
                )
            else:
                chosen_seed = dict(best_global_result)
                chosen_origin = "corridor-global-optimization-best"
                chosen_log_tag = "order C:corridor-global-opt-best-promoted"
                chosen_status = "Nouveau minimum corridor: global-opt découverte, auto-refine en cours..."
        elif cand_global_ok:
            chosen_seed = dict(best_global_result)
            chosen_origin = "corridor-global-optimization-best"
            chosen_log_tag = "order C:corridor-global-opt-best-promoted"
            chosen_status = "Nouveau minimum corridor: global-opt découverte, auto-refine en cours..."
        elif cand_curve_ok:
            chosen_seed = dict(curve_minimum_result)
            chosen_origin = "corridor-profile-curve-minimum"
            chosen_log_tag = "order B2:corridor-curve-min-promoted"
            chosen_status = "RMSE(d): minimum de courbe corridor promu comme nominal, auto-refine en cours..."

        if isinstance(chosen_seed, dict):
            if not grid_cov_ok:
                if self.logger:
                    self.logger.error(
                        "GUI RMSE(d) regular grid [integrity] | adoption candidate rejected because base-grid coverage "
                        "is INCOMPLETE (see profile_d_manual_grid_missing_after_emergency)."
                    )
                chosen_seed = None
            if self.logger:
                rmse_prev_upd = self._rmse_from_result_dict(upd)
                d_sel = chosen_seed.get("d_nm") if isinstance(chosen_seed, dict) else None
                d_sel_txt = (
                    f"{float(d_sel):.6f}" if isinstance(d_sel, (int, float)) and np.isfinite(float(d_sel)) else "n/a"
                )
                self.logger.info(
                    "GUI RMSE(d) grid-profiling [adoption-decision] | candidate_origin=%s | d_selected_nm=%s | "
                    "rmse_before_adoption=%s | rmse_global_opt=%s | rmse_curve=%s | delta_curve_vs_pre_adoption=%s | "
                    "grid_coverage_complete=%s",
                    chosen_origin,
                    d_sel_txt,
                    (f"{rmse_prev_upd:.8f}" if np.isfinite(rmse_prev_upd) else "n/a"),
                    (f"{rmse_best_global:.8f}" if np.isfinite(rmse_best_global) else "n/a"),
                    (f"{rmse_curve:.8f}" if np.isfinite(rmse_curve) else "n/a"),
                    (f"{delta_curve:.3e}" if np.isfinite(delta_curve) else "n/a"),
                    "yes" if grid_cov_ok else "no",
                )

            if isinstance(chosen_seed, dict):
                self._merge_rmse_grid_promotion_into_nominal(
                    dict(chosen_seed),
                    adoption_log_tag=chosen_log_tag,
                )
                if isinstance(self._last_result, dict):
                    self._last_worker_result = dict(self._last_result)

                strict_snapshot = dict(chosen_seed)
                if strict_snapshot.get("x_seg_spline_sigma") is None and strict_snapshot.get("x") is not None:
                    strict_snapshot["x_seg_spline_sigma"] = (
                        np.asarray(strict_snapshot.get("x"), dtype=np.float64).ravel().copy()
                    )
                if strict_snapshot.get("x") is None and strict_snapshot.get("x_seg_spline_sigma") is not None:
                    strict_snapshot["x"] = (
                        np.asarray(strict_snapshot.get("x_seg_spline_sigma"), dtype=np.float64).ravel().copy()
                    )
                chosen_seed["gui_solver_snapshot_for_corridors"] = dict(strict_snapshot)

                self.lbl_status.setText(chosen_status)
                if self._schedule_corridor_auto_refine(
                    chosen_seed,
                    rerun_corridor=True,
                    origin=chosen_origin,
                ):
                    return
                if self.logger:
                    self.logger.warning(
                        "GUI RMSE(d) regular grid | auto-refine chain failed to start | chosen_origin=%s.",
                        chosen_origin,
                    )

        if self.logger:
            dv = np.asarray(upd.get("profile_d_values_nm", []), dtype=np.float64).ravel()
            rv = np.asarray(upd.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
            if dv.size and rv.size == dv.size:
                fg_z = np.isfinite(dv) & np.isfinite(rv)
                if np.any(fg_z):
                    dz = dv[fg_z]
                    rz = rv[fg_z]
                    jz = int(np.argmin(rz))
                    self.logger.info(
                        "GUI RMSE(d) regular grid [order Z:post-merge-curve] | pts=%d | rmse_min=%.8f @ d=%.6f nm | "
                        "nominal_dict_d_nm=%s | nominal_dict_rmse=%s",
                        int(dz.size),
                        float(rz[jz]),
                        float(dz[jz]),
                        (
                            f"{float(self._last_result.get('d_nm', float('nan'))):.6f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(float(self._last_result.get("d_nm", float("nan"))))
                            else "n/a"
                        ),
                        (
                            f"{self._rmse_from_result_dict(self._last_result):.8f}"
                            if isinstance(self._last_result, dict)
                            and np.isfinite(self._rmse_from_result_dict(self._last_result))
                            else "n/a"
                        ),
                    )

        return

    def _on_worker_done(self, result: object) -> None:

        role = str(getattr(self, "_worker_role", "main") or "main")
        manual_pipeline_roles = (
            "manual_sigma_insert",
            "manual_autoshift",
            "manual_auto_add_one",
            "manual_auto_clean",
            "manual_repartition_log",
            "manual_repartition_sigma",
        )
        worker_obj = getattr(self, "_worker", None)
        worker_func = getattr(worker_obj, "func", None)
        worker_name = str(getattr(worker_func, "__name__", "?") or "?")
        manual_dlg = getattr(self, "_manual_knots_dialog", None)

        uninstall_skeleton(self.tabs_main)
        if role == "curve_min_deep":
            self._finish_curve_minimum_deep_worker_done(result)

            return

        if role == "rmse_heal":
            self._finish_rmse_heal_worker_done(result)
            return

        grid_fin = self._is_rmse_d_grid_worker_finalize_dict(result)

        if grid_fin or role == "rmse_grid":
            if grid_fin and role != "rmse_grid" and self.logger:
                op_id = result.get("op_id") if isinstance(result, dict) else None

                self.logger.warning(
                    "GUI worker_done: resultat grille RMSE(d) (profile_d_status=%s) avec _worker_role=%r worker=%s op_id=%s ; traitement grille.",
                    (result.get("profile_d_status") if isinstance(result, dict) else None),
                    role,
                    worker_name,
                    str(op_id) if op_id is not None else "n/a",
                )

            self._finish_corridor_rmse_d_grid_worker_done(result)
            return

        if not isinstance(result, dict):
            if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
                manual_dlg.set_runtime_busy(False)
                manual_dlg.append_runtime_log("Re-optimisation terminee sans resultat exploitable.")

            self.lbl_status.setText("Canceled or no result (dict)")
            self._worker_role = "idle"
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

            if self.logger:
                if result is None:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: the worker finished without dict (None value). "
                        "Common causes: Stop button during calculation, thread closure/interruption, "
                        "or silent worker-side exception. Graphs are not updated since this signal."
                    )

                else:
                    self.logger.warning(
                        "INDEX_SPLINE GUI: the worker returned a %s instead of a dict - result ignored.",
                        type(result).__name__,
                    )

            self._refresh_post_optimization_option_controls()
            return

        if role not in ("rmse_grid", "corridors"):
            self._corridor_rmse_d_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_vals = np.array([], dtype=np.float64)
            self._corridor_rmse_best_idx = -1
            self._corridor_rmse_center_nm = float("nan")
            self._corridor_rmse_robust_lo = float("nan")
            self._corridor_rmse_robust_hi = float("nan")
            self._corridor_rmse_robust_ok = False
            if hasattr(self, "plot_corridor_rmse_d"):
                self.plot_corridor_rmse_d.clear()
            if hasattr(self, "lbl_corridor_rmse_summary"):
                self.lbl_corridor_rmse_summary.setText("No corridor RMSE profile available yet.")
            if hasattr(self, "lbl_corridor_rmse_robust_compact"):
                self.lbl_corridor_rmse_robust_compact.setText("Robust interval: -")

        if self.logger:
            op_id = result.get("op_id")

            role_ctx = role if worker_name == "?" else f"{role}|worker={worker_name}"

            op_id_ctx = str(op_id) if op_id is not None else "n/a"

            _wm = result.get("pipeline_best_rmse_watermark")

            _wms = result.get("pipeline_best_rmse_stage")

            _wm_hint = ""

            if _wm is not None and np.isfinite(float(_wm)):
                _wm_hint = f" | pipeline watermark (best RMSE seen during run): {_wm:.6f} (@ {_wms!s})"

            self.logger.info(
                "INDEX_SPLINE GUI: result dict received - dict RMSE (current n/k curves) = %.6f | "
                "d = %.4f nm | role = %s | worker = %s | op_id = %s%s",
                float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                float(result.get("d_nm", float("nan"))),
                role,
                worker_name,
                op_id_ctx,
                _wm_hint,
            )

            log_index_spline_d_trace(
                self.logger,
                f"GUI: received worker result ({role_ctx}, op_id={op_id_ctx})",
                result.get("d_nm"),
                detail=("worker=" + worker_name),
            )

            split_mesh = CertusIndexSplineApp._result_uses_split_mesh(result)

            self.logger.info(
                "INDEX_SPLINE GUI: worker detail | mse=%.6e | flags split=%s continuous=%s adaptive=%s",
                float(result.get("mse", float("nan"))),
                bool(split_mesh),
                bool(result.get("continuous_model")),
                bool(result.get("adaptive_mesh")),
            )

            log_structured_json_event(
                self.logger,
                "AUTO_BEST_JSON",
                "worker_done",
                role=role,
                worker=worker_name,
                op_id=op_id_ctx,
                mse=float(result.get("mse", float("nan"))),
                rmse=float(np.sqrt(max(float(result.get("mse", 0.0)), 0.0))),
                rmse_convention="sqrt(max(mse,0))",
                d_nm=float(result.get("d_nm", float("nan"))),
                split=bool(split_mesh),
                continuous=bool(result.get("continuous_model")),
                adaptive=bool(result.get("adaptive_mesh")),
            )

        # Auto-Best: declencher une 2e passe locale (knots libres split n/logk) after la 1ere passe warm.

        if self._auto_best_two_stage_refine:
            cfg2 = self._build_opt_config()

            if cfg2 is not None:
                self._auto_best_second_stage_pending = {
                    "seed": dict(result),
                    "cfg": cfg2,
                }

                self._auto_best_two_stage_refine = False

                self.log(
                    "Auto-Best: launching local pass 2 (knots sigma separes pour n et ln k, puis polish).",
                    "INFO",
                )

                self.lbl_status.setText("Auto-Best pass 2: preparing...")

                QTimer.singleShot(0, self._start_auto_best_second_stage)

                return

            self._auto_best_two_stage_refine = False

        self._last_worker_result = dict(result)

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        display = result if role == "corridors" else self._display_result_prefer_best_live(result)

        self._last_result = display

        st = CertusIndexSplineApp._format_post_optimization_status(display, result)

        if display.get("adaptive_mesh"):
            st = "Adaptive mesh | " + st

        if display.get("auto_knot_stages") and "sigma_knots" in display:
            kfin = int(np.asarray(display["sigma_knots"], dtype=np.float64).size)

            kbest = display.get("auto_knots_K_best")

            if kbest is not None and int(kbest) != kfin:
                st = f"K retained={int(kbest)} (last K={kfin}) stages={len(display['auto_knot_stages'])} | " + st

            else:
                st = f"K={kfin} stages={len(display['auto_knot_stages'])} | " + st

        if display.get("gui_display_from_best_live"):
            st = "Meilleur RMSE (live) | " + st

        self.lbl_status.setText(st)

        if self.logger:
            self.logger.info("End optimization: %s", st)

            rmse_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )

            _log_index_spline_best_config(self.logger, display, rmse_fin, title="[FIN OPTIM  affichage / export]")

        # === SAFE-GUARD: Wrap entire final completion path to prevent silent app termination ===
        try:
            plot_source = f"fin_worker:{role}"
            if worker_name != "?":
                plot_source = f"{plot_source}|{worker_name}"
            self._plot_result(display, plot_source=plot_source)
        except Exception as e:
            import traceback

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _plot_result failed: %s\n%s", type(e).__name__, __import__('traceback').format_exc()
                )
            else:
                print(f"[CRASH GUARD] _plot_result failed: {e}", file=__import__("sys").stderr)

        try:
            self._refresh_data_table()
        except Exception as e:

            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_data_table failed: %s\n%s",
                    type(e).__name__,
                    __import__('traceback').format_exc(),
                )

        if role in manual_pipeline_roles and self.logger:
            self.logger.info(
                "PIPELINE [05b/09] Manual pipeline stage completed (%s); proceeding to corridors only afterwards if requested.",
                role,
            )
        if role in manual_pipeline_roles and isinstance(manual_dlg, ManualSigmaKnotDialog):
            try:
                manual_dlg.set_runtime_busy(False)
                d_fin, rmse_fin = CertusIndexSplineApp._runtime_metrics_from_result_dict(display)
                rmse_txt = f"{float(rmse_fin):.6f}" if np.isfinite(rmse_fin) else "n/a"
                self._refresh_manual_dialog_preview(manual_dlg, display)
                # Important: for manual-local flows, keep the exact worker output mesh
                # (result) instead of the display snapshot (which may be overridden by
                # a stale best-live candidate at another K).
                sigma_before = np.asarray(getattr(manual_dlg, "_base_sigma_knots", []), dtype=np.float64).ravel()
                sigma_requested = manual_dlg.selected_sigma_knots()
                sigma_fin = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                if sigma_fin.size == 0:
                    sigma_fin = np.asarray(display.get("sigma_knots", []), dtype=np.float64).ravel()
                requested_summary = CertusIndexSplineApp._summarize_manual_mesh_change(sigma_before, sigma_requested)
                applied_summary = CertusIndexSplineApp._summarize_manual_mesh_change(sigma_before, sigma_fin)
                manual_dlg.append_runtime_log(
                    CertusIndexSplineApp._manual_mesh_change_log_line("Requested mesh", requested_summary)
                )
                same_requested_and_applied = requested_summary["after_sigma_knots"].size == applied_summary[
                    "after_sigma_knots"
                ].size and np.allclose(
                    requested_summary["after_sigma_knots"],
                    applied_summary["after_sigma_knots"],
                    rtol=1e-10,
                    atol=1e-12,
                )
                if not same_requested_and_applied:
                    manual_dlg.append_runtime_log(
                        "Worker returned a different mesh than requested; keeping the applied mesh below."
                    )
                manual_dlg.append_runtime_log(
                    CertusIndexSplineApp._manual_mesh_change_log_line("Applied mesh", applied_summary)
                )
                if sigma_fin.size:
                    manual_dlg.adopt_sigma_knots(sigma_fin)
                opt_delta_ns = result.get("substrate_n_offset")
                if opt_delta_ns is None:
                    opt_delta_ns = display.get("substrate_n_offset")
                if opt_delta_ns is not None:
                    manual_dlg.adopt_delta_ns(float(opt_delta_ns))
                manual_dlg.set_runtime_progress(100.0, "Re-optimisation terminee")
                manual_dlg.set_runtime_metrics(d_fin, rmse_fin)
                manual_dlg.append_runtime_log(f"Re-optimisation terminee | RMSE={rmse_txt}")
                if self.logger:
                    self.logger.info(
                        "INDEX_SPLINE GUI: manual pipeline applied mesh | role=%s | %s",
                        role,
                        CertusIndexSplineApp._manual_mesh_change_log_line("applied", applied_summary),
                    )
                # Stores the absolute best config for the 'Recall best RMSE' button.
                # We use `result` (raw from worker) and not `display`: `display` may be
                # the best live snapshot (e.g. K=14 initial during auto_clean), which
                # would point "Recall best" to an erroneous intermediate state.
                raw_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
                raw_rmse = CertusIndexSplineApp._rmse_from_result_dict(result)
                if raw_sk.size and np.isfinite(raw_rmse):
                    manual_dlg.update_best_config(result, raw_sk)
            except Exception as e:

                if self.logger:
                    self.logger.exception(
                        "INDEX_SPLINE [CRASH GUARD] manual dialog finalization failed: %s\n%s",
                        type(e).__name__,
                        __import__('traceback').format_exc(),
                    )

        # --- Manual extra-knot dialog (must occur before any deferred corridors) ---
        if (
            role not in ((*manual_pipeline_roles, "corridors"))
            and self._can_offer_manual_extra_knots(result)
            and getattr(self, "_corridor_auto_refine_plan", None) is None
        ):
            if self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot stage available after optimization; this stage runs before deferred corridors."
                )

            dlg_ref = getattr(self, "_manual_knots_dialog", None)
            if not isinstance(dlg_ref, ManualSigmaKnotDialog):
                open_manual_fn = getattr(self, "_open_manual_extra_knots_dialog", None)
                if callable(open_manual_fn):
                    open_manual_fn(result)
                    if self.logger:
                        self.logger.info(
                            "PIPELINE [05b/09] Manual extra-knot stage opened in keep-open mode; user closes dialog explicitly."
                        )
                else:
                    # Fallback for test doubles/legacy call paths without non-blocking dialog helper.
                    lambdas = self._prompt_manual_extra_knots(result)
                    if lambdas:
                        if self.logger:
                            self.logger.info(
                                "Manual extra-knot stage accepted; deferred corridors are postponed until manual insertion completes."
                            )
                        self._start_manual_sigma_insert_worker(result, lambdas)
                        return
            elif self.logger:
                self.logger.info(
                    "PIPELINE [05b/09] Manual extra-knot dialog already open; keeping current session active."
                )

        self._worker_role = "idle"

        try:
            self._refresh_post_optimization_option_controls()
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] _refresh_post_optimization_option_controls failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )

        self.lbl_status.setText(CertusIndexSplineApp._post_optimization_ready_status(st))

        try:
            self.export_excel(auto_export=True)
        except Exception as e:

            import traceback as _tb
            if self.logger:
                self.logger.exception(
                    "INDEX_SPLINE [CRASH GUARD] export_excel(auto_export=True) failed: %s\n%s",
                    type(e).__name__,
                    _tb.format_exc(),
                )
            else:
                print(f"[CRASH GUARD] export_excel failed: {e}", file=__import__("sys").stderr)

    def _plot_corridor_tab(
        self,
        r: dict,
        lam_s: np.ndarray,
        n_s: np.ndarray,
        k_s: np.ndarray,
        *,
        spectral_sort_order: np.ndarray | None = None,
    ) -> None:
        """n/k Corridors  tab: central curves + envelopes; auto-focus if bands present."""
        if r is None:
            return

        try:
            # Set log mode BEFORE clear() so _apply_sensible_empty_range uses log range
            if hasattr(self, "plot_k_corridor"):
                self.plot_k_corridor.setLogMode(y=True)
            self.plot_n_corridor.clear()
            self.plot_k_corridor.clear()
            # Re-apply log mode after clear() (clear() reinstalls crosshair/range)
            self.plot_k_corridor.setLogMode(y=True)
        except (AttributeError, RuntimeError):
            if self.logger:
                import traceback as _tb

                self.logger.warning("DIAG CORRIDOR PLOT: clear/logmode failed, returning early\n%s", _tb.format_exc())
            return

        nu = int(np.asarray(lam_s).size)
        spec_order = (
            np.asarray(spectral_sort_order, dtype=np.int64)
            if spectral_sort_order is not None
            else np.arange(nu, dtype=np.int64)
        )
        if spec_order.size != nu:
            spec_order = np.arange(nu, dtype=np.int64)

        # lam_s / n_s / k_s viennent de _spectral_display_align : d?j? co-lin?aires et tri?s par lambda.
        # spec_order sert uniquement ? r?ordonner les bandes corridor stock?es comme n_lam (ordre brut avant tri).
        lam_f = np.asarray(lam_s, dtype=np.float64).ravel()
        n_f = np.asarray(n_s, dtype=np.float64).ravel()
        k_f = np.asarray(k_s, dtype=np.float64).ravel()

        def _get_aligned(key: str) -> np.ndarray:
            val = np.asarray(r.get(key, []), dtype=np.float64).ravel()
            if val.size < nu:
                return np.full(nu, np.nan)
            val_u = val[:nu]
            return val_u[spec_order]

        # Pre-collection of data for dynamic y-axis scaling
        y_n_all = [n_f]
        y_k_all = [k_f]

        # DIAG CORRIDOR PLOT
        if self.logger:
            corr_keys = ["corridor_n_lo", "corridor_n_hi", "corridor_k_lo", "corridor_k_hi"]
            key_info = []
            for _ck in corr_keys:
                _raw = r.get(_ck)
                if _raw is None:
                    key_info.append(f"{_ck}=ABSENT")
                else:
                    _arr = np.asarray(_raw, dtype=np.float64).ravel()
                    _nfin = int(np.sum(np.isfinite(_arr)))
                    key_info.append(f"{_ck}:size={_arr.size}/fin={_nfin}")
            self.logger.debug(
                "DIAG CORRIDOR PLOT | nu=%d | spec_order_size=%d | %s",
                nu,
                int(spec_order.size),
                " | ".join(key_info),
            )

        # 1. Uncertainty Corridor (Profiling-based)
        n_lo = _get_aligned("corridor_n_lo")
        n_hi = _get_aligned("corridor_n_hi")
        k_lo = _get_aligned("corridor_k_lo")
        k_hi = _get_aligned("corridor_k_hi")

        has_profile = False
        if np.any(np.isfinite(n_lo)) and np.any(np.isfinite(n_hi)):
            has_profile = True
            y_n_all.extend([n_lo, n_hi])
            # Shaded background band (lowest layer)
            cln_f = pg.PlotCurveItem(lam_f, n_lo, pen=None)
            cun_f = pg.PlotCurveItem(lam_f, n_hi, pen=None)
            self.plot_n_corridor.addItem(pg.FillBetweenItem(cln_f, cun_f, brush=pg.mkBrush(0, 87, 255, 130)))

            # n_min / n_max DashLine + Glow (matching k style)
            p_nlo_glow = pg.mkPen((180, 220, 255, 180), width=4.5)
            p_nhi_glow = pg.mkPen((160, 200, 255, 180), width=4.5)
            p_nlo = pg.mkPen((0, 140, 255, 255), width=2.2, style=Qt.PenStyle.DashLine)
            p_nhi = pg.mkPen((0, 70, 255, 255), width=2.2, style=Qt.PenStyle.DashLine)

            self._add_curve(self.plot_n_corridor, lam_f, n_lo, None, "n_min_glow", pen=p_nlo_glow)
            self._add_curve(self.plot_n_corridor, lam_f, n_hi, None, "n_max_glow", pen=p_nhi_glow)
            self._add_curve(self.plot_n_corridor, lam_f, n_lo, None, "n_min", pen=p_nlo)
            self._add_curve(self.plot_n_corridor, lam_f, n_hi, None, "n_max", pen=p_nhi)

        k_min_pts = 0
        klf = np.full(nu, np.nan, dtype=np.float64)
        khf = np.full(nu, np.nan, dtype=np.float64)
        if np.any(np.isfinite(k_lo)) and np.any(np.isfinite(k_hi)):
            has_profile = True
            # Enforce statistical width floor globally for display
            k_lo_e, k_hi_e, k_min_pts = enforce_min_k_corridor_half_width(
                k_lo, k_hi, k_f, min_half_width=_CORRIDOR_K_TAB_MIN_HALF_WIDTH
            )
            y_k_all.extend([k_lo_e, k_hi_e])

            # Trace simple: k_min / k_max en pointill?s (m?mes s?ries que Data Corridor).
            klf = np.maximum(k_lo_e, 1e-15)
            khf = np.maximum(k_hi_e, 2e-15)
            # Surbrillance visuelle des bornes corridor k : halo + trait pointill? au-dessus.
            pen_kmin_glow = pg.mkPen((255, 235, 190, 220), width=5.0, style=Qt.PenStyle.SolidLine)
            pen_kmax_glow = pg.mkPen((255, 210, 200, 220), width=5.0, style=Qt.PenStyle.SolidLine)
            pen_kmin = pg.mkPen((255, 150, 0, 255), width=2.8, style=Qt.PenStyle.DashLine)
            pen_kmax = pg.mkPen((255, 40, 0, 255), width=2.8, style=Qt.PenStyle.DashLine)
            # M?me pipeline que k nominal (sanitize + coh?rence axe log du widget).
            lk_min = np.log10(np.maximum(klf, 1e-30))
            lk_max = np.log10(np.maximum(khf, 1e-30))
            self._add_curve(self.plot_k_corridor, lam_f, lk_min, "#ffe0b2", "k_min_glow", pen=pen_kmin_glow)
            self._add_curve(self.plot_k_corridor, lam_f, lk_max, "#ffd7d1", "k_max_glow", pen=pen_kmax_glow)
            self._add_curve(self.plot_k_corridor, lam_f, lk_min, "#ff8c00", "k_min", pen=pen_kmin)
            self._add_curve(self.plot_k_corridor, lam_f, lk_max, "#ff3c00", "k_max", pen=pen_kmax)

        # Donn?es pour label crosshair vertical: k_min / k_nominal / k_max au lambda curseur.
        self._corridor_k_crosshair_lam = np.asarray(lam_f, dtype=np.float64).copy()
        self._corridor_k_crosshair_nom = np.asarray(k_f, dtype=np.float64).copy()
        self._corridor_k_crosshair_lo = np.asarray(klf, dtype=np.float64).copy()
        self._corridor_k_crosshair_hi = np.asarray(khf, dtype=np.float64).copy()

        # 2. Filigree (all profile models)
        n_prof_all = np.asarray(r.get("profile_d_n_curves", []), dtype=np.float64)
        k_prof_all = np.asarray(r.get("profile_d_k_curves", []), dtype=np.float64)
        d_prof_all = np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        filigree_count = 0
        if n_prof_all.ndim == 2 and n_prof_all.shape[0] == d_prof_all.size and d_prof_all.size > 0:
            idx_all = np.flatnonzero(np.all(np.isfinite(n_prof_all[:, :nu]), axis=1))
            if idx_all.size > 0:
                n_show = int(min(7, idx_all.size))
                idx_pick = idx_all[np.unique(np.round(np.linspace(0, idx_all.size - 1, n_show)).astype(int))]
                for i in idx_pick:
                    nr = n_prof_all[i, :nu][spec_order]
                    self.plot_n_corridor.plot(lam_f, nr, pen=pg.mkPen(0, 87, 255, 30, width=1))
                    if k_prof_all.ndim == 2 and k_prof_all.shape[0] == d_prof_all.size:
                        kr = np.maximum(k_prof_all[i, :nu][spec_order], 1e-15)
                        self.plot_k_corridor.plot(lam_f, kr, pen=pg.mkPen(255, 90, 0, 25, width=1))
                filigree_count = idx_pick.size

        # 3. Bootstrap (optional)
        bn_lo = _get_aligned("boot_corridor_n_lo")
        bn_hi = _get_aligned("boot_corridor_n_hi")
        bk_lo = _get_aligned("boot_corridor_k_lo")
        bk_hi = _get_aligned("boot_corridor_k_hi")
        has_boot = False
        try:
            if (
                bn_lo.size == lam_s.size
                and bn_hi.size == lam_s.size
                and bk_lo.size == lam_s.size
                and bk_hi.size == lam_s.size
            ):
                has_boot = True
                y_n_all.extend([bn_lo, bn_hi])
                y_k_all.extend([bk_lo, bk_hi])
                pen_bn = pg.mkPen((0, 160, 80, 90), width=1, style=Qt.PenStyle.DashLine)
                cu_bn = pg.PlotCurveItem(lam_s, bn_hi, pen=pen_bn)
                cl_bn = pg.PlotCurveItem(lam_s, bn_lo, pen=pen_bn)
                self.plot_n_corridor.addItem(cu_bn)
                self.plot_n_corridor.addItem(cl_bn)
                self.plot_n_corridor.addItem(pg.FillBetweenItem(cl_bn, cu_bn, brush=pg.mkBrush(0, 160, 80, 28)))
                bk_lo_finite = np.where(np.isfinite(bk_lo) & (bk_lo > 1e-15), bk_lo, 1e-15)
                bk_hi_finite = np.where(np.isfinite(bk_hi) & (bk_hi > 2e-15), bk_hi, 2e-15)
                pen_bk = pg.mkPen((120, 0, 180, 120), width=1, style=Qt.PenStyle.DashLine)
                cu_bk = pg.PlotCurveItem(lam_s, bk_hi_finite, pen=pen_bk)
                cl_bk = pg.PlotCurveItem(lam_s, bk_lo_finite, pen=pen_bk)
                self.plot_k_corridor.addItem(cu_bk)
                self.plot_k_corridor.addItem(cl_bk)
                self.plot_k_corridor.addItem(pg.FillBetweenItem(cl_bk, cu_bk, brush=pg.mkBrush(120, 0, 180, 80)))
        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.debug("Corridor bootstrap band plot failed", exc_info=True)

        # 4. Nominal curves (on top of bands / filigree)
        lk_f = np.log10(np.maximum(k_f, 1e-30))
        self._add_curve(self.plot_n_corridor, lam_f, n_f, "#0057ff", "n", pen=pg.mkPen("#0057ff", width=3))
        self._add_curve(self.plot_k_corridor, lam_f, lk_f, "#ff5a00", "k", pen=pg.mkPen("#ff5a00", width=3))

        seed_gate_kept_rate = float(r.get("profile_d_seed_gate_kept_rate", float("nan")))
        seed_gate_eval_count = int(r.get("profile_d_seed_gate_eval_count", 0))
        k_min_hw = _CORRIDOR_K_TAB_MIN_HALF_WIDTH

        # UI Updates
        d_nm = float(r.get("d_nm", float("nan")))
        d_txt = f"d = {d_nm:.1f} nm" if np.isfinite(d_nm) else "d = "

        try:
            self.plot_n_corridor.plotItem.setTitle(
                f"n(lambda) + corridors  {d_txt}", color=CertusTheme.PRIMARY, size="10pt"
            )

            self.plot_k_corridor.plotItem.setTitle(
                f"log10 k(lambda) + corridors  {d_txt}", color=CertusTheme.PRIMARY, size="10pt"
            )

            if has_profile:
                self.plot_k_corridor.setToolTip(
                    (
                        "Bold orange: k from the result dict (same as main tab). "
                        + "Shaded band: pointwise min/max in linear k over accepted d-refits, enlarged so the bold curve stays inside. "
                        + f"Filigree: {filigree_count} accepted refit curve(s) sampled from the corridor stack. "
                        + (
                            f"Seed gate: {100.0 * seed_gate_kept_rate:.1f}% of fixed-d refits kept the incoming seed ({seed_gate_eval_count} evaluations). A high value means the corridor, especially in k, may stay close to the nominal branch because alternative local refits did not beat the spectral seed. "
                            if np.isfinite(seed_gate_kept_rate) and seed_gate_eval_count > 0
                            else ""
                        )
                        + "Each accepted refit can still be spline-smooth; visible kinks in the shaded envelope simply mark where the active lower/upper branch switches between different accepted refits once viewed in log10(k). "
                        + (
                            f"A minimum linear-k corridor half-width of +/-{k_min_hw:.1e} is enforced around the reference k when needed "
                            f"(adjusted points: {k_min_pts}). "
                            if np.isfinite(k_min_hw) and k_min_hw > 0.0
                            else ""
                        )
                        + "Dashed orange (if shown): center-d refit when it differs from the bold line. "
                        + "Crosshair y follows the bold curve at the cursor lambda when possible."
                    )
                )

            else:
                self.plot_k_corridor.setToolTip("")

        except (AttributeError, RuntimeError):
            logger.debug("Corridor plot title set failed", exc_info=True)

        # Dynamic Y-axis limits (user request: ymin=floor, ymax=ceil for n; ymax=1e-2 for k)
        try:
            # n corridor scale
            yn_all_f = np.concatenate([np.asarray(arr).ravel() for arr in y_n_all])
            yn_all_f = yn_all_f[np.isfinite(yn_all_f)]
            if yn_all_f.size > 0:
                yn_min, yn_max = float(np.min(yn_all_f)), float(np.max(yn_all_f))
                if yn_max > yn_min:
                    # n: strictly bound by the data range
                    self.plot_n_corridor.setYRange(yn_min, yn_max, padding=0)
                else:
                    self.plot_n_corridor.autoRange()
            else:
                self.plot_n_corridor.autoRange()

            _apply_fixed_log_k_axis(self.plot_k_corridor)
        except (ValueError, TypeError, RuntimeError, AttributeError):
            self.plot_n_corridor.autoRange()
            _apply_fixed_log_k_axis(self.plot_k_corridor)

        if lam_s.size > 0:
            span_lo = float(np.nanmin(lam_s))

            span_hi = float(np.nanmax(lam_s))

            if np.isfinite(span_lo) and np.isfinite(span_hi) and span_hi > span_lo:
                pad = 0.02 * (span_hi - span_lo)

                self.plot_n_corridor.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

                self.plot_k_corridor.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

        if has_profile or has_boot:
            if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_corridor"):
                self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor))

    def _build_corridor_tab_rmse_controls(self, lay_rmse: "QVBoxLayout") -> None:
        lay_rmse.setSpacing(6)

        lbl_intro = QLabel("Step 1: recalculate the RMSE(d) grid, then generate the corridor from that result.")
        lbl_intro.setWordWrap(True)
        lbl_intro.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay_rmse.addWidget(lbl_intro)

        row_rob = QHBoxLayout()

        row_rob.addWidget(QLabel("Robust DeltaRMSE:"))

        self.sp_corridor_rmse_delta = QDoubleSpinBox()

        self.sp_corridor_rmse_delta.setDecimals(6)

        self.sp_corridor_rmse_delta.setRange(1e-6, 0.01)

        self.sp_corridor_rmse_delta.setSingleStep(1e-5)

        self.sp_corridor_rmse_delta.setValue(2e-4)

        self.sp_corridor_rmse_delta.setToolTip(
            "<b>Amplitude DeltaRMSE (Profilage Robuste)</b><br>"
            "Target RMSE increment above minimum (d*) to define robust interval (Purple).<br>"
            "A lower value narrows the interval; a higher value widens it."
        )

        row_rob.addWidget(self.sp_corridor_rmse_delta)

        row_rob.addWidget(QLabel("Local half-window (points):"))

        self.sp_corridor_rmse_win = QSpinBox()

        self.sp_corridor_rmse_win.setRange(2, 8)

        self.sp_corridor_rmse_win.setValue(4)

        self.sp_corridor_rmse_win.setToolTip(
            "<b>Demi-fen?tre locale (points)</b><br>"
            "Number of points on each side of d* used to fit the local parabola.<br>"
            "Une fen?tre plus large lisse les bruits num?riques mais peut capturer des zones non-paraboliques."
        )

        row_rob.addWidget(self.sp_corridor_rmse_win)

        row_rob.addStretch(1)

        row_grid = QHBoxLayout()

        row_grid.addWidget(QLabel("Recalc grid: Deltad (nm)"))

        self.sp_corridor_grid_d_step_nm = QDoubleSpinBox()

        self.sp_corridor_grid_d_step_nm.setDecimals(4)

        self.sp_corridor_grid_d_step_nm.setRange(1e-4, 500.0)

        self.sp_corridor_grid_d_step_nm.setSingleStep(0.05)

        self.sp_corridor_grid_d_step_nm.setToolTip(
            "<b>Sampling step (nm)</b><br>"
            "Fixed offset between each thickness d tested during regular scan.<br>"
            "<i>Tip:</i> A step of 0.1 to 0.5 nm is generally sufficient for a good definition of the parabola."
        )
        self.sp_corridor_grid_d_step_nm.setValue(0.5)

        row_grid.addWidget(self.sp_corridor_grid_d_step_nm)

        row_grid.addWidget(QLabel("Points"))

        self.sp_corridor_grid_n_points = QSpinBox()

        self.sp_corridor_grid_n_points.setRange(2, 999)

        self.sp_corridor_grid_n_points.setValue(11)

        self.sp_corridor_grid_n_points.setToolTip(
            "<b>Total points (Scan)</b><br>"
            "Defines the total grid span (2 to N points around d*).<br>"
            "Allows broadening the search area for RMSE(d)."
        )

        row_grid.addWidget(self.sp_corridor_grid_n_points)

        self.btn_corridor_rmse_grid_calc = create_styled_button("Recalculate RMSE(d)", "primary", parent=self)

        self.btn_corridor_rmse_grid_calc.setToolTip(
            "<b>Full recalculation of the RMSE(d) grid</b><br>"
            "Relance l'optimisation (n, ln k) pour chaque ?paisseur de la grille r?guli?re.<br>"
            "Utilise un m?canisme de <b>continuation (warmstart)</b> et de <b>P0 re-pass</b> pour garantir "
            "l'exploration de la solution optimale physique."
        )

        self.btn_corridor_rmse_grid_calc.clicked.connect(self._start_corridor_rmse_grid_recalc)

        row_grid.addWidget(self.btn_corridor_rmse_grid_calc)

        self.btn_corridor_rmse_export_data = create_styled_button("Export data", "secondary", parent=self)

        self.btn_corridor_rmse_export_data.setToolTip(
            "<b>Export des donn?es (Presse-papiers)</b><br>"
            "Copies all numeric columns (d, RMSE, Parabola, Intervals, Breakpoints) to TSV format.<br>"
            "Directly pastable into Excel or OriginPro for external analysis."
        )

        self.btn_corridor_rmse_export_data.clicked.connect(self._export_corridor_rmse_profile_clipboard)

        row_grid.addWidget(self.btn_corridor_rmse_export_data)

        self.btn_corridor_rmse_export_envelope_nk = create_styled_button(
            "Export enveloppe n/k",
            "secondary",
            parent=self,
        )

        self.btn_corridor_rmse_export_envelope_nk.setToolTip(
            "Export an Excel file (.xlsx) with two sheets (n, k), on lambda grids 2/5/10 nm, for RMSE(d) envelope points."
        )

        self.btn_corridor_rmse_export_envelope_nk.clicked.connect(self._export_corridor_rmse_envelope_nk_excel)

        row_grid.addWidget(self.btn_corridor_rmse_export_envelope_nk)

        self.btn_corridor_generate_from_grid = create_styled_button(
            "Generate corridor from full grid", "primary", parent=self
        )

        self.btn_corridor_generate_from_grid.setEnabled(False)

        self.btn_corridor_generate_from_grid.setToolTip(
            "Build corridor n/k directly from the full RMSE(d) grid currently displayed."
        )

        self.btn_corridor_generate_from_grid.clicked.connect(self._generate_corridor_from_current_grid)

        row_grid.addStretch(1)

        lay_rmse.addLayout(row_grid)

        lbl_generate = QLabel(
            "Step 2: generate the corridor from the full grid, a partial grid, or the automatic smart interval."
        )
        lbl_generate.setWordWrap(True)
        lbl_generate.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay_rmse.addWidget(lbl_generate)

        row_generate_grid = QHBoxLayout()
        row_generate_grid.addWidget(self.btn_corridor_generate_from_grid)

        row_generate_grid.addWidget(QLabel("Corridor Deltad (+/- nm):"))

        self.sp_corridor_partial_delta_nm = QDoubleSpinBox()
        self.sp_corridor_partial_delta_nm.setDecimals(4)
        self.sp_corridor_partial_delta_nm.setRange(1e-4, 500.0)
        self.sp_corridor_partial_delta_nm.setSingleStep(0.05)
        self.sp_corridor_partial_delta_nm.setValue(2.0)
        self.sp_corridor_partial_delta_nm.setToolTip(
            "Half-width used by 'Generate corridor from partial grid'.\n"
            "Interval = [d_center - Deltad, d_center + Deltad], where d_center is the current RMSE(d) center "
            "(parabolic center if available, else best sampled d*)."
        )
        row_generate_grid.addWidget(self.sp_corridor_partial_delta_nm)

        self.btn_corridor_generate_from_partial_grid = create_styled_button(
            "Generate corridor from partial grid", "primary", parent=self
        )
        self.btn_corridor_generate_from_partial_grid.setEnabled(False)
        self.btn_corridor_generate_from_partial_grid.setToolTip(
            "Build corridor n/k from a partial RMSE(d) grid centered on current d*.\n"
            "The width is controlled by Corridor Deltad (+/- nm)."
        )
        self.btn_corridor_generate_from_partial_grid.clicked.connect(self._generate_corridor_from_partial_grid)
        row_generate_grid.addWidget(self.btn_corridor_generate_from_partial_grid)

        self.btn_corridor_generate_auto_smart_grid = create_styled_button(
            "Calculate auto smart corridor from this grid", "primary", parent=self
        )
        self.btn_corridor_generate_auto_smart_grid.setEnabled(False)
        self.btn_corridor_generate_auto_smart_grid.setToolTip(
            "Automatically derive the smart interval from current RMSE(d) grid, "
            "then generate and apply corridor n/k on that interval.\n"
            "Priority: Deltad code interval (orange lines), fallback: robust parabolic interval."
        )
        self.btn_corridor_generate_auto_smart_grid.clicked.connect(self._generate_corridor_auto_smart_from_current_grid)
        row_generate_grid.addWidget(self.btn_corridor_generate_auto_smart_grid)
        row_generate_grid.addStretch(1)

        lay_rmse.addLayout(row_generate_grid)

        row_grid_prog = QHBoxLayout()

        self.pb_corridor_rmse_grid = QProgressBar()
        self.pb_corridor_rmse_grid.setToolTip(
            "<b>Avancement du scan</b><br>"
            "Progression en temps r?el incluant les ?tapes de continuation, "
            "of P0 re-pass and breakpoint detection."
        )
        self.pb_corridor_rmse_grid.setRange(0, 1000)

        self.pb_corridor_rmse_grid.setValue(0)

        self.pb_corridor_rmse_grid.setFormat("Grid %p%")

        self.pb_corridor_rmse_grid.setEnabled(False)

        row_grid_prog.addWidget(self.pb_corridor_rmse_grid, 1)

        self.lbl_corridor_rmse_grid_progress = QLabel("Grid idle.")

        self.lbl_corridor_rmse_grid_progress.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        row_grid_prog.addWidget(self.lbl_corridor_rmse_grid_progress)

        lay_rmse.addLayout(row_grid_prog)

        self.chk_corridor_rmse_show_advanced = QCheckBox("Show advanced settings")

        self.chk_corridor_rmse_show_advanced.setChecked(False)

        lay_rmse.addWidget(self.chk_corridor_rmse_show_advanced)

        self.w_corridor_rmse_advanced = QWidget()

        lay_adv = QVBoxLayout(self.w_corridor_rmse_advanced)

        lay_adv.setContentsMargins(0, 0, 0, 0)

        lay_adv.addLayout(row_rob)

        row_break = QHBoxLayout()

        row_break.addWidget(QLabel("Breakpoint lookback (points):"))

        self.sp_corridor_breakpoint_lookback = QSpinBox()

        self.sp_corridor_breakpoint_lookback.setRange(2, 50)

        self.sp_corridor_breakpoint_lookback.setValue(5)

        self.sp_corridor_breakpoint_lookback.setToolTip(
            "Declare a breakpoint if current RMSE is better than the best RMSE among the previous N points on the same side."
        )

        row_break.addWidget(self.sp_corridor_breakpoint_lookback)

        row_break.addStretch(1)

        lay_adv.addLayout(row_break)

        row_adv_toggles = QHBoxLayout()

        self.chk_corridor_rmse_live_parabola = QCheckBox("Live parabola/robust fit")

        self.chk_corridor_rmse_live_parabola.setChecked(True)

        self.chk_corridor_rmse_live_parabola.setToolTip(
            "If disabled during live grid calculation: update RMSE points only; parabola/robust interval are recomputed at completion."
        )

        row_adv_toggles.addWidget(self.chk_corridor_rmse_live_parabola)

        self.chk_corridor_rmse_lock_scale = QCheckBox("Lock scale")
        self.chk_corridor_rmse_lock_scale.setChecked(True)
        self.chk_corridor_rmse_lock_scale.setToolTip(
            "<b>Scale Stabilization (Live)</b><br>"
            "Maintains the chart axes on the min/max bounds of current data.<br>"
            "This avoids visual jumps (flicker) during live grid calculation."
        )

        self.chk_corridor_rmse_lock_scale.toggled.connect(self._on_corridor_rmse_lock_scale_toggled)

        row_adv_toggles.addWidget(self.chk_corridor_rmse_lock_scale)

        self.chk_corridor_rmse_envelope_only = QCheckBox("Lower envelope only (final)")
        self.chk_corridor_rmse_envelope_only.setChecked(False)
        self.chk_corridor_rmse_envelope_only.setToolTip(
            "<b>Lower Envelope (Profile Likelihood)</b><br>"
            "Once the calculation is finished, only keeps the best RMSE for each thickness d.<br>"
            "<i>Useful for:</i> hiding points converged to local minima (RMSE peaks) "
            "and keeping only the 'true' physical valley necessary for corridor calculation."
        )

        self.chk_corridor_rmse_envelope_only.toggled.connect(self._refresh_corridor_rmse_robust_view)

        row_adv_toggles.addWidget(self.chk_corridor_rmse_envelope_only)

        row_adv_toggles.addStretch(1)

        lay_adv.addLayout(row_adv_toggles)

        self.w_corridor_rmse_advanced.setVisible(False)

        self.chk_corridor_rmse_show_advanced.toggled.connect(self.w_corridor_rmse_advanced.setVisible)

        lay_rmse.addWidget(self.w_corridor_rmse_advanced)

    def _start_corridor_rmse_grid_recalc(self) -> None:
        """Recalculate RMSE(d) on a regular grid (refit n,L with fixed d) in a thread."""

        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.info("GUI RMSE(d) regular grid | request ignored: worker already running")

            QMessageBox.information(self, "Calculate", "A worker is already running (wait or Stop).")

            return

        cfg = self._last_run_cfg

        if cfg is None:
            cfg = self._build_opt_config(notify=False)

        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no optimization configuration available")

            QMessageBox.warning(self, "Calculate", "No optimization configuration available (run a fit first).")

            return

        base = self._corridor_profile_source_result()

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Fallback: some display snapshots (best-live merge / stripped payloads)
            # can miss solver mesh fields needed by RMSE(d) fixed-d refits.
            base_fallback_src = ""
            for src_name, cand in (
                ("corridor_rmse_base_snapshot", self._corridor_rmse_base_snapshot),
                ("last_worker_result", self._last_worker_result),
                ("last_result", self._last_result),
                ("best_live_result", self._best_live_result),
            ):
                if isinstance(cand, dict) and cand.get("sigma_knots") is not None:
                    base = dict(cand)
                    base_fallback_src = str(src_name)
                    break
            if base_fallback_src and self.logger:
                self.logger.info(
                    "GUI RMSE(d) regular grid | base snapshot fallback selected from %s",
                    base_fallback_src,
                )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            # Last chance: rebuild a valid solver snapshot on canonical mesh, silently.
            base_seed: dict[str, Any] = {}
            for cand in (self._last_worker_result, self._last_result, self._best_live_result):
                if isinstance(cand, dict):
                    base_seed = dict(cand)
                    break
            try:
                maxfun_recover = int(max(300, min(4000, int(getattr(cfg, "polish_maxfun", 1200) or 1200))))
                rebuilt = quick_pwlnk_refit_result_dict(cfg, base_seed, maxfun=maxfun_recover)
            except (TypeError, ValueError, RuntimeError, AttributeError):
                rebuilt = None
            if isinstance(rebuilt, dict) and rebuilt.get("sigma_knots") is not None:
                base = dict(rebuilt)
                self._corridor_rmse_base_snapshot = dict(rebuilt)
                if self.logger:
                    self.logger.info(
                        "GUI RMSE(d) regular grid | base snapshot auto-rebuilt (maxfun=%d, sigma_knots=%d)",
                        int(maxfun_recover),
                        int(np.asarray(base.get("sigma_knots", []), dtype=np.float64).size),
                    )

        if not isinstance(base, dict) or base.get("sigma_knots") is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: no corridor profile base in current result")

            # Keep the UX non-blocking: no popup for missing base, only status feedback.
            self.lbl_status.setText(
                "RMSE(d): base corridor indisponible (reconstruction auto impossible). Lance un fit, puis r?essaie."
            )

            return

        self._corridor_rmse_base_snapshot = dict(base)

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size > 0 and r_s.size == d_s.size and 0 <= i_best < int(d_s.size):
            d_center = float(d_s[i_best])

        else:
            d_center = float(base.get("d_nm", float("nan")))

        if not np.isfinite(d_center):
            if self.logger:
                self.logger.warning("GUI RMSE(d) regular grid | aborted: cannot determine center d*")

            QMessageBox.warning(self, "Calculate", "Cannot determine center thickness d* for the grid.")

            return

        n_pts = int(self.sp_corridor_grid_n_points.value()) if hasattr(self, "sp_corridor_grid_n_points") else 11

        step = float(self.sp_corridor_grid_d_step_nm.value()) if hasattr(self, "sp_corridor_grid_d_step_nm") else 0.5

        break_lookback = (
            int(self.sp_corridor_breakpoint_lookback.value()) if hasattr(self, "sp_corridor_breakpoint_lookback") else 5
        )

        if n_pts < 2 or (not np.isfinite(step)) or step <= 0:
            if self.logger:
                self.logger.warning(
                    "GUI RMSE(d) regular grid | aborted: invalid grid params n_pts=%s step=%s",
                    str(n_pts),
                    str(step),
                )

            QMessageBox.warning(self, "Calculate", "Invalid grid: need ?2 points and Deltad > 0.")

            return

        offs = (np.arange(n_pts, dtype=np.float64) - 0.5 * float(n_pts - 1)) * step

        d_grid = d_center + offs
        self._corridor_rmse_requested_grid = d_grid.copy()

        d_lo_grid = float(np.min(d_grid)) if d_grid.size else float("nan")

        d_hi_grid = float(np.max(d_grid)) if d_grid.size else float("nan")

        CertusIndexSplineApp._prepare_worker_restart(self)

        snap = dict(base)

        self._worker = GenericWorker(
            _worker_corridor_rmse_regular_grid,
            cfg,
            snap,
            d_grid,
            self._stop_event,
            int(max(2, break_lookback)),
        )

        def _grid_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _grid_progress

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.kwargs["visit_anchor_nm"] = float(d_center)

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self._worker_role = "rmse_grid"

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._set_corridor_grid_busy(True)

        self._corridor_rmse_grid_live_t0 = float(time.perf_counter())
        self._corridor_rmse_live_last_plot_ts = float("nan")

        self._set_corridor_grid_progress_ui(done=0, total=int(max(1, d_grid.size)))

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText(
            f"RMSE(d) grid: {n_pts} points, Deltad={step:g} nm, break-lookback={int(max(2, break_lookback))} "
            f"(center d*?{d_center:.3f} nm)..."
        )

        if self.logger:
            bd_raw = base.get("d_nm")
            bd_txt = (
                f"{float(bd_raw):.6f}" if isinstance(bd_raw, (int, float)) and np.isfinite(float(bd_raw)) else "n/a"
            )
            br = self._rmse_from_result_dict(base)
            br_txt = f"{br:.8f}" if np.isfinite(br) else "n/a"
            sbv = base.get("spectral_rmse_best_value")
            sbv_txt = f"{float(sbv):.8f}" if sbv is not None and np.isfinite(float(sbv)) else "n/a"
            if (
                d_s.size > 0
                and r_s.size == d_s.size
                and 0 <= i_best < int(d_s.size)
                and np.isfinite(float(r_s[i_best]))
            ):
                center_src = f"rmse_tab_best_idx={i_best}"
                tab_d = f"{float(d_s[i_best]):.6f}"
                tab_r = f"{float(r_s[i_best]):.8f}"
            else:
                center_src = "base_dict_d_nm"
                tab_d = "n/a"
                tab_r = "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | start | center=%.6f nm | n_pts=%d | step=%.6f nm | d_range=[%.6f, %.6f] nm | "
                "base_d_nm=%s | base_rmse_dict=%s | spectral_rmse_best_value=%s | center_src=%s | tab(d,rmse)=(%s,%s)",
                float(d_center),
                int(n_pts),
                float(step),
                float(d_lo_grid),
                float(d_hi_grid),
                bd_txt,
                br_txt,
                sbv_txt,
                center_src,
                tab_d,
                tab_r,
            )

        # Auto-select the Corridor RMSE(d) tab to show live updates
        if hasattr(self, "_idx_tab_corridor_rmse") and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor_rmse))

        self._worker.start()

class _PlotMixin:
    """Mixin containing plot methods for n/k tabs and data preview."""

    def _refresh_data_preview_plots(
        self,
        ser: tuple[np.ndarray, ...] | None = None,
    ) -> None:
        """Data mini-graphs: all n / all k, table grid, synchronized lambda."""

        if not hasattr(self, "plot_data_preview_n") or not hasattr(self, "plot_data_preview_k"):
            return

        pn = self.plot_data_preview_n

        pk = self.plot_data_preview_k

        pn.clear()

        pk.clear()

        pn._certus_crosshair_label_fn = None

        pk._certus_crosshair_label_fn = None

        pn._certus_crosshair_vertical_only = False

        pk._certus_crosshair_vertical_only = False

        self._data_preview_series = None

        if ser is None:
            pn._apply_sensible_empty_range()

            pk._apply_sensible_empty_range()

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        lam = np.asarray(lam_g, dtype=np.float64).ravel()

        nv = np.asarray(n_g, dtype=np.float64).ravel()

        kv = np.asarray(k_g, dtype=np.float64).ravel()

        n_nl_v = np.asarray(n_nl_g, dtype=np.float64).ravel()

        k_nl_v = np.asarray(k_nl_g, dtype=np.float64).ravel()

        n_lo_v = np.asarray(n_lo_g, dtype=np.float64).ravel()

        n_hi_v = np.asarray(n_hi_g, dtype=np.float64).ravel()

        k_lo_v = np.asarray(k_lo_g, dtype=np.float64).ravel()

        k_hi_v = np.asarray(k_hi_g, dtype=np.float64).ravel()

        mk = np.isfinite(lam) & np.isfinite(kv) & (kv > 0.0)

        kk = kv[mk]

        k_pos = kk[kk > 0.0]

        k_floor = float(np.nanmin(k_pos)) if k_pos.size > 0 else 1e-30

        self._data_preview_series = {
            "lam": lam.copy(),
            "n": nv.copy(),
            "n_nl": n_nl_v.copy(),
            "n_lo": n_lo_v.copy(),
            "n_hi": n_hi_v.copy(),
            "k": kv.copy(),
            "k_nl": k_nl_v.copy(),
            "k_lo": k_lo_v.copy(),
            "k_hi": k_hi_v.copy(),
            "k_floor": k_floor,
        }

        def _add_legend(plot: CertusScientificPlot) -> None:

            try:
                plot.addLegend(offset=(8, 8))

            except (ValueError, TypeError, RuntimeError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # --- n preview : enveloppe puis courbes ---
        y_n_all = [nv]
        if np.any(np.isfinite(n_nl_v)):
            y_n_all.append(n_nl_v)

        m_n_env = np.isfinite(n_lo_v) & np.isfinite(n_hi_v) & (n_hi_v >= n_lo_v)

        if np.any(m_n_env):
            y_n_all.extend([n_lo_v, n_hi_v])
            le = lam[m_n_env]
            ylo = n_lo_v[m_n_env]
            yhi = n_hi_v[m_n_env]
            o = np.argsort(le, kind="mergesort")
            le, ylo, yhi = le[o], ylo[o], yhi[o]
            if le.size >= 2:
                # Shaded background band
                cl_f = pg.PlotCurveItem(le, ylo, pen=None)
                cu_f = pg.PlotCurveItem(le, yhi, pen=None)
                pn.addItem(pg.FillBetweenItem(cl_f, cu_f, brush=pg.mkBrush(0, 87, 255, 40)))

                # Dashed bounds + Glow (matching main corridor style)
                p_lo_glow = pg.mkPen((180, 220, 255, 140), width=4.0)
                p_hi_glow = pg.mkPen((160, 200, 255, 140), width=4.0)
                p_lo = pg.mkPen((0, 140, 255, 200), width=1.8, style=Qt.PenStyle.DashLine)
                p_hi = pg.mkPen((0, 70, 255, 200), width=1.8, style=Qt.PenStyle.DashLine)
                pn.plot(le, ylo, pen=p_lo_glow)
                pn.plot(le, yhi, pen=p_hi_glow)
                pn.plot(le, ylo, pen=p_lo)
                pn.plot(le, yhi, pen=p_hi)

        if np.any(np.isfinite(n_nl_v)):
            xnl, ynl = sanitize_xy_for_plot(lam, n_nl_v)

            if xnl.size >= 2:
                plot_widget_plot_finite(
                    pn,
                    xnl,
                    ynl,
                    pen=pg.mkPen("#0a8f5a", width=1.6),
                    name="n_alpha",
                )

        xn, yn = sanitize_xy_for_plot(lam, nv)

        if xn.size >= 2:
            c_n = plot_widget_plot_finite(pn, xn, yn, pen=pg.mkPen("#0057ff", width=2.4), name="n")

            if c_n is not None:
                setattr(c_n, "_certus_crosshair_primary", True)

        # --- k preview : enveloppe (k>0) puis courbes ---
        y_k_all = [kv]
        if np.any(np.isfinite(k_nl_v)):
            y_k_all.append(k_nl_v)

        m_k_env = np.isfinite(k_lo_v) & np.isfinite(k_hi_v) & (k_lo_v > 0.0) & (k_hi_v > 0.0) & (k_hi_v >= k_lo_v)

        if np.any(m_k_env):
            y_k_all.extend([k_lo_v, k_hi_v])
            lek = lam[m_k_env]
            ylok = k_lo_v[m_k_env]
            yhik = k_hi_v[m_k_env]
            ok = np.argsort(lek, kind="mergesort")
            lek, ylok, yhik = lek[ok], ylok[ok], yhik[ok]
            if lek.size >= 2:
                # Shaded background band
                clk_f = pg.PlotCurveItem(lek, ylok, pen=None)
                cuk_f = pg.PlotCurveItem(lek, yhik, pen=None)
                pk.addItem(pg.FillBetweenItem(clk_f, cuk_f, brush=pg.mkBrush(255, 160, 40, 35)))

                # Dashed bounds + Glow (matching main corridor style)
                p_klo_glow = pg.mkPen((255, 235, 190, 180), width=4.0)
                p_khi_glow = pg.mkPen((255, 210, 200, 180), width=4.0)
                p_klo = pg.mkPen((255, 150, 0, 230), width=1.8, style=Qt.PenStyle.DashLine)
                p_khi = pg.mkPen((255, 40, 0, 230), width=1.8, style=Qt.PenStyle.DashLine)
                pk.plot(lek, ylok, pen=p_klo_glow)
                pk.plot(lek, yhik, pen=p_khi_glow)
                pk.plot(lek, ylok, pen=p_klo)
                pk.plot(lek, yhik, pen=p_khi)

        if np.any(np.isfinite(k_nl_v) & (k_nl_v > 0.0)):
            knlp = np.where(np.isfinite(k_nl_v) & (k_nl_v > 0.0), k_nl_v, np.nan)

            xknl, yknl = sanitize_xy_for_plot(lam, knlp)

            if xknl.size >= 2:
                plot_widget_plot_finite(
                    pk,
                    xknl,
                    yknl,
                    pen=pg.mkPen("#0a8f5a", width=1.6),
                    name="k_alpha",
                )

        kk_plot = np.where(np.isfinite(kv) & (kv > 0.0), kv, np.nan)

        xk, yk = sanitize_xy_for_plot(lam, kk_plot)

        if xk.size >= 2:
            c_k = plot_widget_plot_finite(pk, xk, yk, pen=pg.mkPen("#f59e0b", width=2.4), name="k")

            if c_k is not None:
                setattr(c_k, "_certus_crosshair_primary", True)

        pn.setLogMode(False, False)

        _apply_fixed_log_k_axis(pk)

        _add_legend(pn)

        _add_legend(pk)

        pn._certus_mouse_moved_hook = self._on_data_preview_plot_mouse_moved

        pk._certus_mouse_moved_hook = self._on_data_preview_plot_mouse_moved

        # Perform dynamic Y-scaling (user request: floor=min, fixed ymax k=1e-2)
        try:
            # n preview
            yn_all_f = np.concatenate([np.asarray(arr).ravel() for arr in y_n_all])
            yn_all_f = yn_all_f[np.isfinite(yn_all_f)]
            if yn_all_f.size > 0:
                yn_min, yn_max = float(np.min(yn_all_f)), float(np.max(yn_all_f))
                if yn_max > yn_min:
                    pn.setYRange(yn_min, yn_max, padding=0)
                else:
                    pn.autoRange()
            else:
                pn.autoRange()

            _apply_fixed_log_k_axis(pk)
        except NUMERICAL_FAULT_EXCEPTIONS:
            pn.autoRange()
            _apply_fixed_log_k_axis(pk)

class _UIBuilderMixin:
    """Mixin containing UI-construction tab methods."""

    def _build_ui(self) -> None:

        setup_pyqtgraph_defaults()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        hdr_w = create_header_logo_widget(
            title_text="INDEX-SPLINE",
            subtitle_text=self.APP_TITLE,
            module_name="CERTUS_INDEX_SPLINE",
        )
        # Inject theme toggle on the right of the header
        self._theme_toggle = CertusThemeToggle(hdr_w)
        hdr_w.layout().addWidget(self._theme_toggle)
        outer.addWidget(hdr_w)

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(6)
        outer.addLayout(root_layout, 1)

        # ── Left sidebar ─────────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setMinimumWidth(280)
        self.left_scroll = left_scroll

        left_inner = QWidget()
        left_inner.setMinimumWidth(280)
        left_lay = QVBoxLayout(left_inner)
        left_lay.setContentsMargins(0, 2, 2, 2)
        left_lay.setSpacing(2)

        # ── Stepper card ─────────────────────────────────────────────────────
        stepper_card = CertusCard("Workflow guide")
        stepper_card.body.setContentsMargins(8, 4, 8, 6)
        stepper_card.body.setSpacing(3)
        self._stepper = CertusStepper(
            [
                "Load spectrum",
                "Substrate (n) & layer thickness",
                "Fit targets (T / R)",
                "Mesh & optimizer",
                "Run",
                "Manual nodes",
                "Corridors & RMSE(d)",
            ],
            columns=2,
        )
        self._stepper.step_activated.connect(self._on_stepper_activated)
        self._stepper.set_step(0)
        stepper_card.body.addWidget(self._stepper)
        self.stepper_card = stepper_card
        left_lay.addWidget(stepper_card)

        # ── File card ─────────────────────────────────────────────────────────
        file_card = CertusCard("1  Spectrum")
        file_card.body.setContentsMargins(8, 4, 8, 6)
        file_card.body.setSpacing(4)
        self.lbl_file = QLabel("(no file loaded)")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_file.setToolTip("Path of the last loaded file.")
        self.btn_load = create_styled_button("Load spectrum…", "secondary")
        self.btn_load.setToolTip(
            "Step 1: open a file containing at least lambda and transmission T. "
            "In Basic, enable T/Tsub if T already is T_film/T_bare_sub ratio (often in %)."
        )
        self.btn_load.clicked.connect(self._on_load)
        file_card.body.addWidget(self.btn_load)
        file_card.body.addWidget(self.lbl_file)
        self.file_card = file_card
        left_lay.addWidget(file_card)

        # ── Parameters card (collapsible) ─────────────────────────────────────
        # ctrl_tabs kept as QTabWidget for full backward compat with all mixins
        self.ctrl_tabs = QTabWidget()
        self.ctrl_tabs.setDocumentMode(True)
        self.ctrl_tabs.setToolTip("Steps 2-4 in order: substrate, targets, mesh.")
        self.ctrl_tabs.addTab(self._build_controls_basic_panel(), "Basic (2 → 4)")
        self.params_collapsible = CertusCollapsible("2-4  Parameters", self.ctrl_tabs, expanded=False)
        self.params_collapsible._hdr.setStyleSheet(
            f"QPushButton {{ background: {CertusTheme.SURFACE_HOVER}; border: none; "
            f"border-radius: 6px; padding: 4px 8px; font-weight: 600; font-size: 11px; "
            f"color: {CertusTheme.TEXT_MAIN}; text-align: left; }}"
            f"QPushButton:hover {{ background: {CertusTheme.BORDER}; }}"
        )
        left_lay.addWidget(self.params_collapsible)

        # ── Action bar (Run / Stop / toggles) ────────────────────────────────
        action_card = CertusCard("5  Run, manual nodes, corridors")
        action_card.body.setContentsMargins(8, 4, 8, 6)
        action_card.body.setSpacing(4)

        self.btn_run = QPushButton("▶  Run Optimization")
        self.btn_run.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setMinimumHeight(26)
        self.btn_run.setToolTip("Start global optimization (Smart Init).")
        self.btn_run.clicked.connect(self._on_run)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName(OBJ.DANGER_BUTTON)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setMinimumHeight(26)
        self.btn_stop.setToolTip("Stop and keep best result found so far.")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)

        run_row = QHBoxLayout()
        run_row.setSpacing(4)
        run_row.addWidget(self.btn_run, 2)
        run_row.addWidget(self.btn_stop, 1)
        action_card.body.addLayout(run_row)

        # Post-run actions: Manual nodes first (dominant), then corridors.
        post_row = QHBoxLayout()
        post_row.setSpacing(4)

        self.btn_manual_knots_toggle = QPushButton("◆  Manual knots")
        self.btn_manual_knots_toggle.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_manual_knots_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manual_knots_toggle.setMinimumHeight(26)
        self.btn_manual_knots_toggle.setToolTip(
            "Priority action after optimization: automatic removal + manual knot insertion."
        )
        self.btn_manual_knots_toggle.clicked.connect(self._on_btn_manual_knots_clicked)

        self.btn_corridor_toggle = QPushButton("◈  Corridors / RMSE(d)")
        self.btn_corridor_toggle.setObjectName(OBJ.PRIMARY_BUTTON)
        self.btn_corridor_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_corridor_toggle.setMinimumHeight(26)
        self.btn_corridor_toggle.setToolTip(
            "Priority action: launches corridors and RMSE(d) workflow from the latest optimized result."
        )
        self.btn_corridor_toggle.clicked.connect(self._on_btn_corridor_clicked)

        self.lbl_corridors_run_state = QLabel()
        self.lbl_corridors_run_state.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_corridors_run_state.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")
        self.lbl_corridors_run_state.setToolTip(
            "Indicates if manual corridor calculation is available or already computed for the current result."
        )

        post_row.addWidget(self.btn_manual_knots_toggle, 2)
        post_row.addWidget(self.btn_corridor_toggle, 1)
        action_card.body.addLayout(post_row)

        self.lbl_postprocess_hint = QLabel("Recommended flow: Run -> Manual knots -> Corridors / RMSE(d)")
        self.lbl_postprocess_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        action_card.body.addWidget(self.lbl_postprocess_hint)
        action_card.body.addWidget(self.lbl_corridors_run_state)

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.stateChanged.connect(self._on_corridor_chk_state_changed)

        # Progress + status
        self.progress_widget = EnhancedProgressWidget(main_label="Optimization")
        action_card.body.addWidget(self.progress_widget)
        self.prog = self.progress_widget

        self.lbl_status = CertusStatusPill("Ready", "ready")
        self.lbl_status.setToolTip("Last action or error; details in the Log tab.")
        action_card.body.addWidget(self.lbl_status)

        reset_btn = create_reset_button(self, use_app_reset=True)
        reset_btn.setToolTip("Clear all and return to first-launch state: no spectrum, no result, default controls.")
        action_card.body.addWidget(reset_btn)

        self.action_card = action_card
        left_lay.addWidget(action_card)
        left_lay.addStretch(1)
        left_scroll.setWidget(left_inner)

        # ── Log panel ─────────────────────────────────────────────────────────
        self.log_panel = CertusLogPanel(title="LOG")
        self.log_panel.setMinimumHeight(140)
        self.log_text = self.log_panel.log_text
        self.widgets["log_text"] = self.log_text

        # ── Context stack (tab-specific settings) ─────────────────────────────
        self.context_stack = QStackedWidget()
        scroll_ctx = QScrollArea()
        scroll_ctx.setWidgetResizable(True)
        scroll_ctx.setFrameShape(QFrame.Shape.NoFrame)
        scroll_ctx.setWidget(self.context_stack)
        scroll_ctx.setStyleSheet("background: transparent;")

        aux_tabs = QTabWidget()
        aux_tabs.setDocumentMode(True)
        aux_tabs.addTab(scroll_ctx, "Context")
        aux_tabs.addTab(self.log_panel, "Logs")
        aux_tabs.setToolTip("Additional controls and runtime logs for the current workflow tab.")

        # ── Right panel: resizable sidebar stack ──────────────────────────────
        info_panel = QSplitter(Qt.Orientation.Vertical)
        info_panel.setChildrenCollapsible(False)
        info_panel.setHandleWidth(14)
        info_panel.setObjectName("indexSplineInfoSplit")
        info_panel.setStyleSheet(
            "#indexSplineInfoSplit::handle { background-color: #7a8798; }"
            "#indexSplineInfoSplit::handle:hover { background-color: #4f9cff; }"
        )
        info_panel.setMinimumWidth(left_scroll.minimumWidth())
        info_panel.addWidget(left_scroll)
        info_panel.addWidget(aux_tabs)
        info_panel.setStretchFactor(0, 8)
        info_panel.setStretchFactor(1, 2)
        info_panel.setSizes([720, 180])
        self.info_split = info_panel

        # ── Plots panel ───────────────────────────────────────────────────────
        plots_panel = self._build_plot_tabs_panel()
        self.tabs_main.currentChanged.connect(self._sync_context_panel_to_current_tab)

        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.setChildrenCollapsible(False)
        self.main_split.setHandleWidth(14)
        self.main_split.setObjectName("indexSplineMainSplit")
        self.main_split.setStyleSheet(
            "#indexSplineMainSplit::handle { background-color: #7a8798; }"
            "#indexSplineMainSplit::handle:hover { background-color: #4f9cff; }"
        )
        # UX: keep inputs on the left and plots on the right for a natural flow.
        self.main_split.addWidget(info_panel)
        self.main_split.addWidget(plots_panel)
        # setCollapsible needs existing widget indices — never call before addWidget.
        nc = int(self.main_split.count())
        if nc >= 1:
            self.main_split.setCollapsible(0, True)
        if nc >= 2:
            self.main_split.setCollapsible(1, True)
        # Default with a visibly wider workflow pane so the RMSE(d) tab stays closer to a square plot.
        self.main_split.setStretchFactor(0, 3)
        self.main_split.setStretchFactor(1, 2)
        self.main_split.setSizes([960, 640])
        self._enforce_main_splitter_ratio_bounds(persist=False)
        self.main_split.splitterMoved.connect(self._on_main_splitter_moved)
        self.info_split.splitterMoved.connect(self._persist_splitter_states)

        root_layout.addWidget(self.main_split)

        self._sync_context_panel_to_current_tab()

        self._refresh_corridors_gui_state_labels()
        self._refresh_post_optimization_option_controls()

    def _on_stepper_activated(self, step_index: int) -> None:

        idx = int(max(0, min(step_index, 6)))
        if hasattr(self, "_stepper"):
            self._stepper.set_step(idx)

        if idx == 0:
            self._reveal_sidebar_widget(getattr(self, "file_card", None))
            if hasattr(self, "tabs_main"):
                self.tabs_main.setCurrentIndex(0)

        if idx == 0 and hasattr(self, "btn_load"):
            self.btn_load.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx in (1, 2, 3) and hasattr(self, "params_collapsible"):
            self.params_collapsible.set_expanded(True)
            self._reveal_sidebar_widget(self.params_collapsible)

        if idx == 1 and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        if idx == 1 and hasattr(self, "cb_sub"):
            self.cb_sub.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 2 and hasattr(self, "tabs_main"):
            self.tabs_main.setCurrentIndex(0)

        if idx == 2 and hasattr(self, "chk_t"):
            self.chk_t.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 3 and hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_indices"):
            self.tabs_main.setCurrentIndex(int(self._idx_tab_indices))

        if idx == 3 and hasattr(self, "cb_profilee"):
            self.cb_profilee.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 4:
            self._reveal_sidebar_widget(getattr(self, "action_card", None))

        if idx == 4 and hasattr(self, "btn_run"):
            self.btn_run.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if idx == 5:
            self._reveal_sidebar_widget(getattr(self, "action_card", None))
            if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_indices"):
                self.tabs_main.setCurrentIndex(int(self._idx_tab_indices))

        if idx == 5 and hasattr(self, "btn_manual_knots_toggle"):
            self.btn_manual_knots_toggle.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self._reveal_sidebar_widget(getattr(self, "action_card", None))
        if hasattr(self, "tabs_main") and hasattr(self, "_idx_tab_corridor_rmse"):
            try:
                self.tabs_main.setCurrentIndex(int(self._idx_tab_corridor_rmse))
            except (TypeError, ValueError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        if hasattr(self, "btn_corridor_toggle"):
            self.btn_corridor_toggle.setFocus(Qt.FocusReason.OtherFocusReason)

    def _reveal_sidebar_widget(self, widget: QWidget | None) -> None:

        if not isinstance(widget, QWidget):
            return
        scroll = getattr(self, "left_scroll", None)
        if isinstance(scroll, QScrollArea):
            scroll.ensureWidgetVisible(widget, 0, 24)

    def _build_basic_step3_spectral_targets(self, parent_layout: "QVBoxLayout", style: str) -> None:
        box3 = CertusCard("3  What to fit on the spectrum (T, T/Tsub, R)")

        box3.setStyleSheet(style)
        box3.body.setContentsMargins(6, 4, 6, 4)
        box3.body.setSpacing(4)

        box3.setToolTip(
            "Step 3: define what the T column represents. Checked = T_film/T_bare_sub ratio "
            "(and R/T_bare_sub if R), often in % (100 = ratio 1). Unchecked = absolute T and R. "
            "wT / wR weight RMSE when both channels are active."
        )

        g3 = QGridLayout()
        g3.setContentsMargins(0, 0, 0, 0)
        g3.setHorizontalSpacing(6)
        g3.setVerticalSpacing(4)

        box3.body.addLayout(g3)

        parent_layout.addWidget(box3)

        r3 = 0

        self.chk_t = QCheckBox("Fit transmission T")

        self.chk_t.setChecked(True)

        self.chk_t.setToolTip("Include file T column in objective. Disable only when fitting R only.")

        g3.addWidget(self.chk_t, r3, 0, 1, 2)

        r3 += 1

        self.chk_trel = QCheckBox("T = T_film / T_substrate (ratio, e.g. % -> fraction)")

        self.chk_trel.setChecked(True)

        self.chk_trel.setToolTip(
            "Checked (usual case): T column is T_film / bare-substrate T ratio (backside included), same for R. "
            "Often provided in percent (100 = ratio 1). Fit compares against ratio model without dividing by T_sub again. "
            "Unchecked: columns are absolute transmission/reflection (or %). "
            "RMSE objective uses ln lambda weighting and optional mixed T/R loss."
        )

        self.chk_trel.toggled.connect(self._on_trel_plot_refresh)

        g3.addWidget(self.chk_trel, r3, 0, 1, 2)

        r3 += 1

        self.chk_r = QCheckBox("Fit reflection R (if R column exists)")

        self.chk_r.setToolTip("Requires an R column; combines T and R if both are enabled and wR > 0.")

        g3.addWidget(self.chk_r, r3, 0, 1, 2)

        r3 += 1

        lb_w = QLabel("Weights in MSE:")

        lb_w.setToolTip("wT and wR weight T and R errors respectively (mixed mode). Use wR = 0 for T-only fitting.")

        g3.addWidget(lb_w, r3, 0)

        self.w_t = QDoubleSpinBox()

        self.w_t.setRange(0.0, 100.0)

        self.w_t.setValue(1.0)

        self.w_t.setToolTip("Relative weight of T error in global RMSE.")

        self.w_r = QDoubleSpinBox()

        self.w_r.setRange(0.0, 100.0)

        self.w_r.setValue(1.0)

        self.w_r.setToolTip("Relative weight of R error. Set to 0 to ignore R in fitting.")

        h_w = QHBoxLayout()
        h_w.setSpacing(4)

        h_w.addWidget(QLabel("wT"))

        h_w.addWidget(self.w_t)

        h_w.addWidget(QLabel("wR"))

        h_w.addWidget(self.w_r)

        hw = QWidget()

        hw.setLayout(h_w)

        g3.addWidget(hw, r3, 1)

        parent_layout.addWidget(box3)

        btn_rmse_win = create_styled_button("Spectral RMSE window (lambda)...", "secondary")

        btn_rmse_win.setToolTip(
            "Limits the wavelengths used in the optimization MSE/RMSE. "
            "The displayed spectrum remains complete; only points in the band count for the adjustment."
        )

        btn_rmse_win.clicked.connect(self._on_rmse_fit_window_dialog)

        parent_layout.addWidget(btn_rmse_win)

    def _build_corridor_tab_generate(self, lay_generate: "QVBoxLayout") -> None:
        lay_generate.setSpacing(6)

        lbl_manual = QLabel("Alternative path: define a manual interval around d* and generate a corridor directly.")
        lbl_manual.setWordWrap(True)
        lbl_manual.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay_generate.addWidget(lbl_manual)

        row_manual = QHBoxLayout()

        row_manual.addWidget(QLabel("Manual centered corridor (+/- nm):"))

        self.sl_corridor_manual_half = QSlider(Qt.Orientation.Horizontal)

        self.sl_corridor_manual_half.setRange(0, 1)

        self.sl_corridor_manual_half.setValue(0)

        self.sl_corridor_manual_half.setSingleStep(1)

        self.sl_corridor_manual_half.setPageStep(5)

        self.sl_corridor_manual_half.setTickPosition(QSlider.TickPosition.TicksBelow)

        self.sl_corridor_manual_half.setEnabled(False)

        self.sl_corridor_manual_half.setToolTip(
            "<b>Cursor: Manual Width (±Δd)</b><br>"
            "D?finit arbitrairement la largeur du corridor pour g?n?rer les enveloppes n, k, L.<br>"
            "The generated corridor will be [d* - Deltad, d* + Deltad]."
        )

        self.sl_corridor_manual_half.setStyleSheet(slider_corridor_half_stylesheet())

        self.sl_corridor_manual_half.valueChanged.connect(self._on_corridor_manual_slider_changed)

        row_manual.addWidget(self.sl_corridor_manual_half, 1)

        self.lbl_corridor_manual_half = QLabel("+/-0.00 nm")

        self.lbl_corridor_manual_half.setMinimumWidth(90)

        row_manual.addWidget(self.lbl_corridor_manual_half)

        self.btn_corridor_manual_robust = create_styled_button("Use robust interval", "secondary", parent=self)

        self.btn_corridor_manual_robust.setEnabled(False)

        self.btn_corridor_manual_robust.setToolTip(
            "<b>Synchronize with Robust Interval</b><br>"
            "Automatically aligns the manual slider to the width calculated by the parabola (Purple/Orange).<br>"
            "Allows restarting from the smart suggestion before manual fine-tuning."
        )

        self.btn_corridor_manual_robust.clicked.connect(self._use_robust_corridor_interval)

        row_manual.addWidget(self.btn_corridor_manual_robust)

        self.btn_generate_manual_corridor = create_styled_button(
            "Generate corridor from selected interval", "primary", parent=self
        )

        self.btn_generate_manual_corridor.setEnabled(False)

        self.btn_generate_manual_corridor.setToolTip(
            "<b>Generate visual n/k/L corridor</b><br>"
            "Go back to the Indices tab to reconstruct and display the uncertainty envelopes "
            "as confidence corridors surrounding the nominal model."
        )

        self.btn_generate_manual_corridor.clicked.connect(self._apply_manual_corridor_selection)

        row_manual.addWidget(self.btn_generate_manual_corridor)

        lay_generate.addLayout(row_manual)

        row_manual_meta = QHBoxLayout()

        self.lbl_corridor_manual_dmin = QLabel("d_min: -")

        self.lbl_corridor_manual_dcenter = QLabel("d*: -")

        self.lbl_corridor_manual_dmax = QLabel("d_max: -")

        self.lbl_corridor_manual_interval = QLabel("Manual interval: -")

        for _lab in (
            self.lbl_corridor_manual_dmin,
            self.lbl_corridor_manual_dcenter,
            self.lbl_corridor_manual_dmax,
            self.lbl_corridor_manual_interval,
        ):
            _lab.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        row_manual_meta.addWidget(self.lbl_corridor_manual_dmin)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dcenter)
        row_manual_meta.addSpacing(8)
        row_manual_meta.addWidget(self.lbl_corridor_manual_dmax)
        row_manual_meta.addStretch(1)
        row_manual_meta.addWidget(self.lbl_corridor_manual_interval)
        lay_generate.addLayout(row_manual_meta)

    def _build_tab_data(self) -> QWidget:

        # Contr?les d?plac?s ? droite
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()

        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()

        self.btn_copy_nk = create_styled_button("Copier tout le tableau (TSV)", "secondary")

        self.btn_copy_nk.setEnabled(False)

        self.btn_copy_nk.setToolTip("All columns (lambda, n?, k?) - Excel paste")

        self.btn_copy_nk.clicked.connect(self._copy_nk_to_clipboard)

        tb.addWidget(self.btn_copy_nk)

        self.btn_export_nk = create_styled_button("Export CSV...", "primary")

        self.btn_export_nk.setEnabled(False)

        self.btn_export_nk.clicked.connect(self._export_nk_csv)

        tb.addWidget(self.btn_export_nk)

        tb.addStretch(1)

        ctx_lay.addLayout(tb)

        spl_prev = QSplitter(Qt.Orientation.Horizontal)

        self.plot_data_preview_n = CertusScientificPlot(
            title="n preview",
            y_label="n",
            x_label="lambda (nm)",
        )

        self.plot_data_preview_n.showGrid(x=True, y=True, alpha=0.25)

        self.plot_data_preview_k = CertusScientificPlot(
            title="k preview",
            y_label="k",
            x_label="lambda (nm)",
        )

        self.plot_data_preview_k.showGrid(x=True, y=True, alpha=0.25)

        _apply_fixed_log_k_axis(self.plot_data_preview_k)

        spl_prev.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_data_preview_n))

        spl_prev.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_data_preview_k))

        spl_prev.setStretchFactor(0, 1)

        spl_prev.setStretchFactor(1, 1)

        lay.addWidget(spl_prev, 1)

        self.table_nk = ExcelTableWidget()

        self.table_nk.setColumnCount(9)

        self.table_nk.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n_alpha",
                "n env min",
                "n env max",
                "k",
                "k_alpha",
                "k env min",
                "k env max",
            ]
        )

        self.table_nk.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)

        self.table_nk.horizontalHeader().setStretchLastSection(True)

        self.table_nk.setToolTip(
            "lambda grid by spectral region: 2 nm step (<=400 nm), 5 nm (400-1200 nm), "
            "10 nm beyond; n, k and envelopes interpolated from result mesh. "
            "n_alpha / k_alpha: nonlinear indices if available. "
            "Enveloppes : bornes du corridor (profilage d). "
            "Previews: all n (or k) curves, envelope band if corridor; synchronized lambda cursor. "
            "Ctrl+C: copy selection (TSV) -> Excel."
        )

        lay.addWidget(self.table_nk, 2)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)
        # Sync for Log and CERTUS tabs

        return panel

    def _build_tab_data_th(self) -> QWidget:
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        tb = QHBoxLayout()
        self.btn_copy_data_th = create_styled_button("Copier tableau Data TH (TSV)", "secondary")
        self.btn_copy_data_th.setEnabled(False)
        self.btn_copy_data_th.setToolTip("Copie toutes les colonnes de Data TH (TSV) vers le clipboard.")
        self.btn_copy_data_th.clicked.connect(self._copy_data_th_to_clipboard)
        tb.addWidget(self.btn_copy_data_th)
        tb.addStretch(1)
        lay.addLayout(tb)

        hint = QLabel(
            "Table theorique sur grille lambda piecewise: 2 nm (<=400), 5 nm (400-1200), 10 nm (>1200). "
            "Colonnes: lambda, n, k, d, ns, Tth, Rth."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        lay.addWidget(hint)

        self.table_data_th = ExcelTableWidget()
        self.table_data_th.setColumnCount(7)
        self.table_data_th.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
        self.table_data_th.setEditTriggers(ExcelTableWidget.EditTrigger.NoEditTriggers)
        self.table_data_th.horizontalHeader().setStretchLastSection(True)
        self.table_data_th.setToolTip(
            "Theoretical grid aligned on reporting lambda mesh. Refreshed from best-live snapshot during optimization."
        )
        lay.addWidget(self.table_data_th, 1)

        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        return panel

    def _build_basic_step2_substrate_thickness(self, parent_layout: "QVBoxLayout", style: str) -> None:
        box2 = CertusCard("2  Substrate n(lambda) & layer thickness d (nm)")

        box2.setStyleSheet(style)
        box2.body.setContentsMargins(6, 4, 6, 4)
        box2.body.setSpacing(4)

        box2.setToolTip(
            "Step 2: set substrate optical index n_sub(lambda) and single-layer thickness bounds. "
            "This must be physically consistent before running the fit."
        )

        g2 = QGridLayout()
        g2.setContentsMargins(0, 0, 0, 0)
        g2.setHorizontalSpacing(6)
        g2.setVerticalSpacing(4)

        box2.body.addLayout(g2)

        parent_layout.addWidget(box2)

        r = 0

        row_d = QHBoxLayout()
        row_d.setSpacing(6)

        lb_dnom = QLabel("d_nominal (nm) :")

        lb_dnom.setToolTip("Nominal layer thickness around which search bounds are built.")

        row_d.addWidget(lb_dnom)

        self.d_lo = QDoubleSpinBox()

        self.d_lo.setRange(1.0, 50000.0)

        self.d_lo.setValue(0.5 * float(SIO2_DEFAULT_D_LO_NM + SIO2_DEFAULT_D_HI_NM))

        self.d_lo.setToolTip("Nominal thickness d0 (nm). Effective bounds are d0 +/- Delta.")

        row_d.addWidget(self.d_lo)

        lb_dpm = QLabel("+/- (nm) :")

        lb_dpm.setToolTip("Half-width Delta (nm) around d_nominal used for optimization bounds.")

        row_d.addWidget(lb_dpm)

        self.d_hi = QDoubleSpinBox()

        self.d_hi.setRange(0.1, 25000.0)

        self.d_hi.setValue(0.5 * float(SIO2_DEFAULT_D_HI_NM - SIO2_DEFAULT_D_LO_NM))

        self.d_hi.setToolTip("Half-width Delta (nm): optimization bounds are [d_nominal - Delta, d_nominal + Delta].")

        row_d.addWidget(self.d_hi)

        row_d.addStretch(1)

        g2.addLayout(row_d, r, 0, 1, 2)

        r += 1

        lb_sub = QLabel("Substrate :")

        lb_sub.setToolTip("Bare substrate material used to compute T_sub and the multilayer model (CERTUS list).")

        g2.addWidget(lb_sub, r, 0)

        self.cb_sub = QComboBox()

        for name in allowed_substrate_names():
            self.cb_sub.addItem(name, name)

        # Default: Sapphire (Al2O3)

        idx_sapphire = self.cb_sub.findText("Sapphire (Al2O3)", Qt.MatchFlag.MatchContains)

        if idx_sapphire >= 0:
            self.cb_sub.setCurrentIndex(idx_sapphire)

        self.cb_sub.setToolTip("Select the same substrate used for measurement (internal tabulated dispersion).")

        g2.addWidget(self.cb_sub, r, 1)

        g2.setColumnStretch(1, 1)

        parent_layout.addWidget(box2)

    def _build_plot_tabs_panel(self) -> QWidget:
        """Right panel (Swanepoel type): detach bar + graphical tabs."""

        self.tabs_main = QTabWidget()
        self._tab_context_widgets: dict[QWidget, QWidget] = {}
        self._pending_context_page: QWidget | None = None

        self._add_plot_tab(self._build_tab_spectrum(), "Spectrum T / R")

        self._idx_tab_indices = self._add_plot_tab(self._build_tab_indices(), "n & k")

        self._tab_corridor_panel = self._build_tab_corridor()

        self._idx_tab_corridor = self._add_plot_tab(self._tab_corridor_panel, "Corridors n/k")

        self._tab_corridor_rmse_panel = self._build_tab_corridor_rmse()

        self._idx_tab_corridor_rmse = self._add_plot_tab(self._tab_corridor_rmse_panel, "Corridor RMSE(d)")

        self._add_plot_tab(self._build_tab_data(), "Data")
        self._add_plot_tab(self._build_tab_data_th(), "Data TH")
        self._add_plot_tab(self._build_tab_data_corridor(), "Data Corridor")

        self._add_plot_tab(
            self._build_tab_log(),
            "Log",
            context_widget=self._add_context_page(
                self._create_empty_context_widget("Optimization log and real-time computation diagnostics.")
            ),
        )

        self._add_plot_tab(
            self._build_tab_why(),
            "CERTUS",
            context_widget=self._add_context_page(
                self._create_empty_context_widget("Scientific references and methodology for the Spline model.")
            ),
        )

        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(6, 2, 6, 2)
        detach_btn = create_styled_button("⬡  Detach plot", "secondary")
        detach_btn.setFixedHeight(24)
        detach_btn.setToolTip("Clone the first plot of the active tab into a floating window (Ctrl+Shift+D on plot).")
        detach_btn.clicked.connect(self._detach_current_plot)
        hl.addWidget(detach_btn)
        hl.addStretch(1)

        out = QWidget()
        vl = QVBoxLayout(out)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        vl.addWidget(hdr)
        vl.addWidget(self.tabs_main, 1)
        return out

    def _add_context_page(self, widget: QWidget) -> QWidget:

        self.context_stack.addWidget(widget)
        self._pending_context_page = widget
        return widget

    def _consume_pending_context_page(self) -> QWidget | None:

        page = getattr(self, "_pending_context_page", None)
        self._pending_context_page = None
        return page if isinstance(page, QWidget) else None

    def _add_plot_tab(
        self,
        tab_widget: QWidget,
        label: str,
        *,
        context_widget: QWidget | None = None,
    ) -> int:

        idx = self.tabs_main.addTab(tab_widget, label)
        ctx = context_widget if context_widget is not None else self._consume_pending_context_page()
        if isinstance(ctx, QWidget):
            self._tab_context_widgets[tab_widget] = ctx
        return idx

    def _sync_context_panel_to_current_tab(self, *_args) -> None:

        if not hasattr(self, "tabs_main") or not hasattr(self, "context_stack"):
            return
        current_tab = self.tabs_main.currentWidget()
        if not isinstance(current_tab, QWidget):
            return
        ctx = getattr(self, "_tab_context_widgets", {}).get(current_tab)
        if isinstance(ctx, QWidget):
            self.context_stack.setCurrentWidget(ctx)

    def _build_corridor_labels(self, ctx_lay: "QVBoxLayout") -> None:
        """Tab for corridor profile RMSE as a function of thickness d."""

        panel = QWidget()

        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        _INTELLIGENT_DD_TOOLTIP = (
            "<b>Intelligent Deltad (automatic interval)</b><br>"
            "Two <b>orange</b> lines indicate the interval [d_lo, d_hi] calculated "
            "automatically by the profiling code (<tt>profile_d_interval_nm</tt>).<br><br>"
            "<b>Scientific Principle:</b><br>"
            "The algorithm explores the <i>profile likelihood</i> (minimal RMSE at each thickness d) "
            "and fits a local parabola: <b>RMSE ? c2?(d-d*)^2 + RMSE*</b>.<br><br>"
            "<b>Curvature &harr; Width Link:</b><br>"
            "The curvature <b>c2</b> represents the <b>sensitivity</b> of the fit to thickness:<br>"
            "&bull; A <b>high curvature</b> (narrow valley) means the RMSE increases quickly if d deviates from d* : "
            "the solution is well localized, the corridor is <b>tight</b>.<br>"
            "&bull; A <b>low curvature</b> (flat valley) means many thicknesses yield a nearly identical fit : "
            "the uncertainty is large, the corridor is <b>wide</b>.<br><br>"
            "<b>Final Calculation:</b><br>"
            "&bull; The excursion is <b>Deltad = &radic;(DeltaRMSE / c2)</b>, thus inversely proportional to the square root of the curvature.<br>"
            "&bull; <b>DeltaRMSE</b> is estimated dynamically from the residual noise (MAD) and geometric criteria.<br>"
            "&bull; A floor of <b>&plusmn;0.2% of d</b> is always applied for robustness."
        )

        hint = QLabel(
            "<b>RMSE(d) corridor profile</b> at all points calculated during profiling. "
            "Raw scatter (unconnected). The <b>parabola</b> is fitted to the min-RMSE envelope by thickness.<br>"
            "<span style='color:#ff8c00;'>&#9646;</span> = Smart Deltad (automatic interval) | "
            "<span style='color:#7a3cff;'>&#9646;</span> = local robust interval | "
            "<span style='color:#ff4d4f;'>&#9646;</span> = manual selection."
        )

        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        ctx_lay.addWidget(hint)

        self.lbl_corridor_rmse_summary = QLabel("No corridor RMSE profile available yet.")
        self.lbl_corridor_rmse_summary.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridor_rmse_summary.setToolTip(
            "<b>R?sum? de la qualit? (Final)</b><br>"
            "Affiche l'?paisseur optimale d* trouv?e globalement sur la grille "
            "as well as the RMSE corresponding to the absolute minimum."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_summary)
        self.lbl_corridor_rmse_robust_compact = QLabel("Robust interval: -")
        self.lbl_corridor_rmse_robust_compact.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridor_rmse_robust_compact.setToolTip(
            "<b>Robust interval (compact format)</b><br>"
            "Affiche le centre et la demi-largeur sous la forme "
            "<code>xxx.xxnm +/- xxx.nm</code>."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_robust_compact)

        self.lbl_corridor_rmse_state = QLabel("Step 1/3: Recalculate RMSE(d) to start.")
        self.lbl_corridor_rmse_state.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_corridor_rmse_state.setToolTip(
            "<b>Progress / Diagnostic</b><br>"
            "Displays the current pipeline step (Calculation, Fit, or Export) "
            "and potential alert messages on convergence."
        )
        ctx_lay.addWidget(self.lbl_corridor_rmse_state)

    def _build_tab_corridor(self) -> QWidget:
        # Controls and help moved to the right
        ctx_w = QWidget()
        ctx_lay = QVBoxLayout(ctx_w)
        ctx_lay.setContentsMargins(0, 0, 0, 0)

        hint = QLabel(
            "<b>Acceptance envelope (profiling in d)</b> - n(lambda) and k(lambda) bands after optimization. "
            "Calculation starts from <b>best polished spectral RMSE</b> ('best RMSE' + RMSE_ref+Delta default): "
            "displayed reference curve is the scientific nominal, and the envelope groups models whose "
            "masked RMSE remains <= RMSE<sub>best</sub> + Delta. This is not a Bayesian confidence interval."
            "<br><br>"
            "<b>Automatic</b> execution at end of run if 'Corridors n/k -> Enable' is checked. "
            "Onglet ouvert seul lorsque corridors ou bootstrap sont disponibles."
            "<br><br>"
            "<b>log10 k:</b> the <b>bold</b> orange curve follows the main optimization result ('n &amp; log10 k' tab). "
            "Shaded area = min/max of linear <i>k</i> of refits accepted at various <i>d</i> "
            "(without corrective widening in scientific mode). <b>Dashed</b> orange curve only if a central refit "
            "differs significantly from bold. <b>Crosshair:</b> value follows bold curve at cursor lambda."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        ctx_lay.addWidget(hint)

        self.lbl_corridors_tab_state = QLabel()
        self.lbl_corridors_tab_state.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_corridors_tab_state.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px;")
        self.lbl_corridors_tab_state.setToolTip("Corridor option state in the UI for the next optimization run.")
        ctx_lay.addWidget(self.lbl_corridors_tab_state)
        ctx_lay.addStretch(1)
        self._add_context_page(ctx_w)

        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_n_corridor = CertusScientificPlot(title="n(lambda) + corridors", y_label="n", x_label="lambda (nm)")

        self.plot_n_corridor.showGrid(x=True, y=True, alpha=0.25)

        self.plot_k_corridor = CertusScientificPlot(title="k(lambda) + corridors", y_label="k", x_label="lambda (nm)")

        self.plot_k_corridor.showGrid(x=True, y=True, alpha=0.25)
        _apply_fixed_log_k_axis(self.plot_k_corridor)
        self.plot_k_corridor._certus_crosshair_label_fn = self._k_corridor_crosshair_formatter
        self.plot_k_corridor._certus_crosshair_vertical_only = True

        spl = QSplitter(Qt.Orientation.Vertical)

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_n_corridor))

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_k_corridor))

        spl.setStretchFactor(0, 1)

        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        return panel

class _CorridorExportMixin:
    """Mixin containing corridor and nk export methods."""

    def _ensure_complete_manifest_for_secondary_export(self) -> bool:

        from certus_data import get_missing_manifest_fields

        result = getattr(self, "_last_result", None)
        manifest_dict = result.get("run_manifest") if isinstance(result, dict) else None
        missing_manifest_fields = get_missing_manifest_fields(
            manifest_dict if isinstance(manifest_dict, dict) else None
        )
        if not missing_manifest_fields:
            return True

        msg = "Export blocked: incomplete manifest (" + ", ".join(missing_manifest_fields) + ")"
        if hasattr(self, "logger"):
            self.logger.error("INDEX_SPLINE secondary export blocked: %s", msg)
        QMessageBox.warning(self, "Export blocked", msg)
        return False

    def _export_corridor_rmse_profile_clipboard(self) -> None:
        """Clipboard: RMSE(d) data, local parabolic fit, robust interval."""

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        if d_s.size == 0 or r_s.size != d_s.size:
            QMessageBox.information(self, "Export data", "No RMSE(d) curve in memory.")

            return

        lines: list[str] = []

        lines.append("# CERTUS INDEX-SPLINE ? Corridor RMSE(d) export")

        lines.append("# section: profile_points")

        lines.append("d_nm\tRMSE")

        for di, ri in zip(d_s.tolist(), r_s.tolist()):
            lines.append(f"{float(di):.8f}\t{float(ri):.10f}")

        par = getattr(self, "_corridor_rmse_parab_export", None)

        if isinstance(par, dict) and bool(par.get("ok", False)):
            lines.append("# section: local_parabolic_fit (x = d - anchor_nm)")

            lines.append("anchor_nm\tc2\tc1\tc0\td_center_nm\td_lo_fit_nm\td_hi_fit_nm")

            c2, c1, c0 = par.get("coeffs", (float("nan"),) * 3)

            wlo, whi = par.get("window_nm", (float("nan"), float("nan")))

            lines.append(
                f"{float(par.get('anchor_nm', float('nan'))):.8f}\t{float(c2):.10e}\t{float(c1):.10e}\t{float(c0):.10e}\t"
                f"{float(par.get('d_center', float('nan'))):.8f}\t{float(wlo):.8f}\t{float(whi):.8f}"
            )

        else:
            lines.append("# section: local_parabolic_fit")

            lines.append("# (unavailable ? need ?5 local points for convex quadratic fit)")

        rb = getattr(self, "_corridor_rmse_robust_export", None)

        if isinstance(rb, dict) and bool(rb.get("ok", False)):
            lines.append("# section: robust_interval (from local quadratic + Delta RMSE)")

            lines.append("d_lo_nm\td_hi_nm\tslope_at_dstar_per_nm\tcurvature_c2")

            lines.append(
                f"{float(rb.get('d_lo', float('nan'))):.8f}\t{float(rb.get('d_hi', float('nan'))):.8f}\t"
                f"{float(rb.get('slope', float('nan'))):.10e}\t{float(rb.get('curvature', float('nan'))):.10e}"
            )

        else:
            lines.append("# section: robust_interval")
            lines.append("# (unavailable)")

        # Intelligent interval (automatic from code outcome)
        src = self._corridor_profile_source_result() or {}
        _int_nm = src.get("profile_d_interval_nm", None) if isinstance(src, dict) else None
        if isinstance(_int_nm, (tuple, list)) and len(_int_nm) == 2:
            lines.append("# section: intelligent_interval (automatic code outcome)")
            lines.append("d_lo_auto_nm\td_hi_auto_nm")
            lines.append(f"{float(_int_nm[0]):.8f}\t{float(_int_nm[1]):.8f}")
        else:
            lines.append("# section: intelligent_interval")
            lines.append("# (unavailable)")

        # Manual interval (user selection)
        d_lo_man = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))
        d_hi_man = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))
        if np.isfinite(d_lo_man) and np.isfinite(d_hi_man):
            lines.append("# section: manual_interval (user selection)")
            lines.append("d_lo_manual_nm\td_hi_manual_nm\tactive_status")
            _status = "ACTIVE" if bool(getattr(self, "_corridor_rmse_manual_active", False)) else "PREVIEW"
            lines.append(f"{d_lo_man:.8f}\t{d_hi_man:.8f}\t{_status}")
        else:
            lines.append("# section: manual_interval")
            lines.append("# (not set)")

        # Breakpoint events (diagnostic)
        bp_ev = src.get("profile_d_manual_grid_breakpoint_events", []) if isinstance(src, dict) else []
        if isinstance(bp_ev, list) and bp_ev:
            lines.append("# section: breakpoint_events")
            lines.append("d_nm\ttrigger\tbranch_dir")
            for ev in bp_ev:
                if not isinstance(ev, dict):
                    continue
                _db = float(ev.get("d_break_nm", float("nan")))
                _tr = "parabola" if float(ev.get("trigger_parabola", 0)) > 0.5 else "prevN"
                _dir = "right" if float(ev.get("branch_dir_sign", 0)) > 0 else "left"
                lines.append(f"{_db:.8f}\t{_tr}\t{_dir}")
        else:
            lines.append("# section: breakpoint_events")
            lines.append("# (none detected)")

        txt = "\n".join(lines) + "\n"

        cb = QApplication.clipboard()

        if cb is None:
            QMessageBox.warning(self, "Export data", "Clipboard unavailable.")

            return

        cb.setText(txt)

        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("RMSE(d) profile + parabola + robust interval copied to clipboard (TSV).")

    def _export_corridor_rmse_envelope_nk_excel(self) -> None:
        """Excel Export: 2 sheets (n, k) for RMSE(d) envelope points, on 2/5/10 nm grids."""
        if not self._ensure_complete_manifest_for_secondary_export():
            return

        source = self._corridor_profile_source_result()

        display = self._last_result if isinstance(self._last_result, dict) else {}

        if not isinstance(source, dict):
            QMessageBox.information(self, "Export enveloppe n/k", "No RMSE(d) source data available.")

            return

        d_vals = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        r_vals = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)

        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)

        if d_vals.size == 0 or r_vals.size != d_vals.size or n_curves.ndim != 2 or k_curves.ndim != 2:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "No valid RMSE(d)/n/k grid in memory.",
            )

            return

        if n_curves.shape[0] != d_vals.size or k_curves.shape != n_curves.shape or n_curves.shape[1] == 0:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "n/k curves are not aligned with RMSE(d) points.",
            )

            return

        lam_ref = np.asarray(source.get("lam_nm", display.get("lam_nm", [])), dtype=np.float64).ravel()

        if lam_ref.size != n_curves.shape[1]:
            alt_lam = np.asarray(display.get("lam_nm", []), dtype=np.float64).ravel()

            lam_ref = alt_lam if alt_lam.size == n_curves.shape[1] else lam_ref

        if lam_ref.size != n_curves.shape[1]:
            QMessageBox.information(
                self,
                "Export enveloppe n/k",
                "Wavelength axis is unavailable or mismatched.",
            )

            return

        m = np.isfinite(d_vals) & np.isfinite(r_vals)

        if not np.any(m):
            QMessageBox.information(self, "Export enveloppe n/k", "No finite RMSE(d) points available.")

            return

        d_work = d_vals[m]

        r_work = r_vals[m]

        n_work = np.asarray(n_curves[m, :], dtype=np.float64)

        k_work = np.asarray(k_curves[m, :], dtype=np.float64)

        o_d = np.argsort(d_work)

        d_work = d_work[o_d]

        r_work = r_work[o_d]

        n_work = n_work[o_d, :]

        k_work = k_work[o_d, :]

        step_hint = (
            float(self.sp_corridor_grid_d_step_nm.value())
            if hasattr(self, "sp_corridor_grid_d_step_nm")
            else float("nan")
        )

        tol_nm = 0.55 * step_hint if np.isfinite(step_hint) and step_hint > 0.0 else float("nan")

        env_mask = _rmse_d_lower_envelope_mask(d_work, r_work, tol_nm)

        if not np.any(env_mask):
            QMessageBox.information(self, "Export enveloppe n/k", "No envelope points selected.")

            return

        d_env = d_work[env_mask]

        r_env = r_work[env_mask]

        n_env = n_work[env_mask, :]

        k_env = k_work[env_mask, :]

        ok_lam = np.isfinite(lam_ref)

        if int(np.sum(ok_lam)) < 2:
            QMessageBox.information(self, "Export enveloppe n/k", "Not enough finite wavelength points.")

            return

        lam_use = np.asarray(lam_ref[ok_lam], dtype=np.float64)

        n_env = np.asarray(n_env[:, ok_lam], dtype=np.float64)

        k_env = np.asarray(k_env[:, ok_lam], dtype=np.float64)

        o_lam = np.argsort(lam_use)

        lam_use = lam_use[o_lam]

        n_env = n_env[:, o_lam]

        k_env = k_env[:, o_lam]

        lam_min = float(np.nanmin(lam_use))

        lam_max = float(np.nanmax(lam_use))

        if not np.isfinite(lam_min) or not np.isfinite(lam_max) or lam_max <= lam_min:
            QMessageBox.information(self, "Export enveloppe n/k", "Invalid wavelength interval.")

            return

        ts = time.strftime("%Y%m%d_%H%M%S")

        out_default = str(Path.cwd() / f"RMSEd_envelope_nk_{ts}.xlsx")

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export n/k envelope (Excel)",
            out_default,
            "Excel Workbook (*.xlsx);;All Files (*.*)",
        )

        if not out_path:
            return

        if not out_path.lower().endswith(".xlsx"):
            out_path += ".xlsx"

        grid_steps = (2.0, 5.0, 10.0)
        lam_grids: dict[float, np.ndarray] = {}
        lam_parts: list[np.ndarray] = []
        for grid_step in grid_steps:
            start = float(np.ceil(lam_min / grid_step) * grid_step)
            stop = float(np.floor(lam_max / grid_step) * grid_step)
            if stop < start:
                lam_grid = np.asarray([lam_min, lam_max], dtype=np.float64)
            else:
                n_pts = int(np.floor((stop - start) / grid_step + 0.5)) + 1
                lam_grid = start + grid_step * np.arange(max(1, n_pts), dtype=np.float64)
            lam_grids[float(grid_step)] = np.asarray(lam_grid, dtype=np.float64)
            lam_parts.append(np.asarray(lam_grid, dtype=np.float64))

        lam_master = np.unique(np.concatenate(lam_parts)) if lam_parts else np.array([], dtype=np.float64)
        lam_master = np.asarray(np.sort(lam_master), dtype=np.float64)

        if lam_master.size == 0:
            QMessageBox.information(self, "Export enveloppe n/k", "No lambda grid available for export.")
            return

        idx_map = {round(float(v), 9): int(i) for i, v in enumerate(lam_master.tolist())}

        cols_n: dict[str, np.ndarray] = {"lambda_nm": lam_master.copy()}
        cols_k: dict[str, np.ndarray] = {"lambda_nm": lam_master.copy()}
        hdr_d: list[object] = ["lambda_nm"]
        hdr_rmse: list[object] = ["-"]

        for i in range(int(d_env.size)):
            for grid_step in grid_steps:
                lam_grid = lam_grids[float(grid_step)]
                n_interp = np.interp(lam_grid, lam_use, n_env[i, :], left=np.nan, right=np.nan)
                k_interp = np.interp(lam_grid, lam_use, k_env[i, :], left=np.nan, right=np.nan)

                col_n = np.full(lam_master.shape, np.nan, dtype=np.float64)
                col_k = np.full(lam_master.shape, np.nan, dtype=np.float64)
                for j, lam_v in enumerate(lam_grid):
                    pos = idx_map.get(round(float(lam_v), 9))
                    if pos is not None:
                        col_n[pos] = float(n_interp[j])
                        col_k[pos] = float(k_interp[j])

                col_name = f"p{i + 1:03d}_s{int(grid_step)}nm"
                cols_n[col_name] = col_n
                cols_k[col_name] = col_k
                hdr_d.append(f"{float(d_env[i]):.3f} @ {int(grid_step)}nm")
                hdr_rmse.append(float(r_env[i]))

        df_n = pd.DataFrame(cols_n)
        df_k = pd.DataFrame(cols_k)

        if df_n.empty or df_k.empty:
            QMessageBox.information(self, "Export enveloppe n/k", "No data to export.")

            return

        try:
            with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
                df_n.to_excel(writer, sheet_name="n", index=False, header=False, startrow=2)
                df_k.to_excel(writer, sheet_name="k", index=False, header=False, startrow=2)

                for sh_name in ("n", "k"):
                    ws = writer.sheets[sh_name]
                    # 2-line header:
                    #   row 1 -> d_nm
                    #   row 2 -> RMSE
                    for col_idx, (v_d, v_r) in enumerate(zip(hdr_d, hdr_rmse), start=1):
                        ws.cell(row=1, column=col_idx, value=v_d)
                        ws.cell(row=2, column=col_idx, value=v_r)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            QMessageBox.warning(
                self,
                "Export enveloppe n/k",
                f"Unable to write Excel file.\n{type(exc).__name__}: {exc}",
            )
            return

        if hasattr(self, "lbl_status"):
            self.lbl_status.setText(f"RMSE(d) envelope n/k exported: {out_path}")

        if self.logger:
            self.logger.info(
                "GUI RMSE(d) envelope n/k export (xlsx) | path=%s | envelope_points=%d | lambda_range=[%.6f, %.6f] nm | sheets=[n,k] | grids=[2,5,10] nm",
                str(out_path),
                int(d_env.size),
                float(lam_min),
                float(lam_max),
            )

    def _export_nk_csv(self) -> None:
        if not self._ensure_complete_manifest_for_secondary_export():
            return

        if self._last_result is None:
            QMessageBox.warning(self, "Export", "No result to export.")

            return

        start_dir = get_certus_last_dir()

        if not start_dir or not Path(start_dir).is_dir():
            start_dir = str(_SCRIPT_DIR)

        suggested = str(Path(start_dir) / "certus_index_spline_nk.csv")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export indices",
            suggested,
            "CSV (*.csv);;All (*.*)",
        )

        if not path:
            return

        ser = self._prepare_nk_data_tab_series(self._last_result)

        if ser is None:
            QMessageBox.warning(self, "Export", "Empty grid.")

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("lambda_nm,n,n_alpha,n_envelope_min,n_envelope_max,k,k_alpha,k_envelope_min,k_envelope_max\n")

                for i in range(m):
                    line = f"{float(lam_g[i]):.4f},"

                    line += self._fmt_n_data_tab(float(n_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_nl_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_lo_g[i])) + ","

                    line += self._fmt_n_data_tab(float(n_hi_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_nl_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_lo_g[i])) + ","

                    line += self._fmt_k_data_tab(float(k_hi_g[i])) + "\n"

                    fh.write(line)

            set_certus_last_dir(path)

            self.lbl_status.setText(f"CSV saved: {path}")

        except OSError as e:
            QMessageBox.critical(self, "Export", str(e))

class _RunMixin:
    """Mixin containing optimization run logic, live update and result plotting."""

    def _on_run(self) -> None:

        # Reinitialisation de la securite retour de dialog

        self._preview_ret = None

        cfg = self._build_opt_config()

        if cfg is None:
            return

        cfg.gui_run_pglobal_opt_in = False

        cfg.spline_local_only = True

        if hasattr(self, "_stepper"):
            self._stepper.set_step(4)

        if self.logger:
            self.logger.info("RUN local policy | spline_local_only=True")

        t_run_cfg = time.perf_counter()

        if self.logger:
            self.logger.info(
                "RUN config | n_seg=%s d=[%.2f,%.2f] wt=%.3f wr=%.3f profile=%s nk_interp=%s local_only=%s polish=%s mono=%s n_lambda_rise_slack=%.4f",
                int(cfg.n_seg),
                float(cfg.d_lo),
                float(cfg.d_hi),
                float(cfg.weight_t),
                float(cfg.weight_r),
                str(self.cb_profilee.currentData() or "fast"),
                str(cfg.nk_profile_interp),
                bool(cfg.spline_local_only),
                int(cfg.polish_maxfun),
                cfg.n_mono_band_nm,
                float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0),
            )

            log_structured_json_event(
                self.logger,
                "AUTO_BEST_JSON",
                "run_config",
                n_seg=int(cfg.n_seg),
                d_lo=float(cfg.d_lo),
                d_hi=float(cfg.d_hi),
                wt=float(cfg.weight_t),
                wr=float(cfg.weight_r),
                profile=str(self.cb_profilee.currentData() or "fast"),
                nk_profile_interp=str(cfg.nk_profile_interp),
                pg_iter=int(cfg.pglobal_max_iter),
                pg_feval=cfg.pglobal_max_feval,
                pg_time=cfg.pglobal_max_time,
                pg_local=cfg.pglobal_local_search_budget,
                polish=int(cfg.polish_maxfun),
                n_mono_band=cfg.n_mono_band_nm,
                n_lambda_rising_slack=float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0),
            )

        # Toujours forcer le mode Smart Init en "Auto-Best"

        if getattr(self, "_auto_best_force_smart_init", True):
            if self.logger:
                self.logger.info("Auto-Best: Smart Init dialog interception active.")

        self._save_undo_state()

        CertusIndexSplineApp._prepare_worker_restart(self)

        reset_smart_init_preview_guard(cfg)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_worker_result = None

        self._corridor_rmse_manual_active = False

        self._corridor_rmse_manual_lo = float("nan")

        self._corridor_rmse_manual_hi = float("nan")

        self._log_prog_last = -1

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        self._log_optimization_header(cfg)

        cfg_run = cfg.replace(smart_init_preview_hook=self._smart_init_preview_hook)

        if self.logger:
            self.logger.info(
                "RUN SmartInit hook | cfg_run.smart_init_preview_hook=%s | preview_shown=%s | thread=%s",
                "set" if getattr(cfg_run, "smart_init_preview_hook", None) is not None else "none",
                bool(getattr(cfg_run, "smart_init_preview_shown", False)),
                type(QThread.currentThread()).__name__,
            )

        setattr(
            cfg_run,
            "gui_defer_corridor_profile_after_nl",
            bool(getattr(self, "chk_corridor_d", None) and self.chk_corridor_d.isChecked()),
        )

        self._last_run_cfg = cfg_run

        # CRITICAL : dataclasses.replace() ne copie PAS les attributs dynamiques.

        # On les transfere manuallement pour que le worker voie l'injection manualle.

        for _attr in (
            "smart_preview_node_override",
            "smart_preview_exact_sigma_knots",
            "smart_preview_exact_n_L",
            "smart_preview_d_nm_override",
            "smart_preview_accepted_rmse",
            "spline_local_only",
            "smart_init_manual_force_restart",
            "gui_run_pglobal_opt_in",
        ):
            if hasattr(cfg, _attr):
                setattr(cfg_run, _attr, getattr(cfg, _attr))

        if self.logger:
            log_index_spline_d_trace(
                self.logger,
                "GUI: launching main worker (before SOL2)",
                None,
                detail=f"d bornes exploration cfg [{float(cfg_run.d_lo):.4f}, {float(cfg_run.d_hi):.4f}] nm",
            )

        self._worker = GenericWorker(worker_spline_optimization, cfg_run, self._stop_event)

        self._worker_role = "main"

        self._worker.kwargs["progress_cb"] = self._worker.signals.progress.emit

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.live.connect(self._on_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        # live_cb / _on_live_update : une seule connexion (?vite double _plot_result ? UI qui ? g?le ?).

        if self.logger:
            self.logger.info(
                "RUN dispatch worker=%s prep_elapsed=%.3fs",
                getattr(self._worker.func, "__name__", "?"),
                time.perf_counter() - t_run_cfg,
            )

        # one-shot gate: force smart init by default next time too (or rely on the fact it's permanent for auto-best)

        self._auto_best_force_smart_init = True

        self._worker.start()
        install_skeleton(self.tabs_main, label="Optimizing Spline Model...")

    def _on_live_update(self, result: dict) -> None:
        """Refresh during calculation: graphs = always the best RMSE snapshot (copied arrays)."""

        if not isinstance(result, dict):
            return

        if "lam_nm" not in result:
            if "profile_d_values_nm" in result:
                self._on_corridor_rmse_grid_live_update(result)

            return

        current_rmse = self._rmse_from_result_dict(result)

        prev_best_rmse = float(self._best_live_rmse)

        had_prior_best_snapshot = self._best_live_result is not None

        improved = False

        if np.isfinite(current_rmse) and (self._best_live_result is None or current_rmse < self._best_live_rmse):
            self._best_live_rmse = current_rmse

            self._best_live_result = _snap_spline_visual_dict(result)

            improved = True

        to_plot = self._best_live_result if self._best_live_result is not None else _snap_spline_visual_dict(result)

        now = time.monotonic()

        remind = (now - self._last_live_log_mono) >= self._LIVE_LOG_REMINDER_S

        if self.logger and self._best_live_result is not None and np.isfinite(self._best_live_rmse):
            if improved:
                self._last_live_log_mono = now

                abs_gain = float(prev_best_rmse - float(current_rmse))

                if not had_prior_best_snapshot or not np.isfinite(prev_best_rmse):
                    log_best_detail = True

                else:
                    min_step = max(
                        float(self._LIVE_BEST_DETAIL_MIN_ABS),
                        float(self._LIVE_BEST_DETAIL_MIN_REL) * max(float(prev_best_rmse), 1e-12),
                    )

                    log_best_detail = bool(
                        abs_gain >= min_step
                        or (now - float(self._live_best_detail_log_mono))
                        >= float(self._LIVE_BEST_DETAIL_MIN_INTERVAL_S)
                    )

                if log_best_detail:
                    self._live_best_detail_log_mono = now

                    _log_index_spline_best_config(
                        self.logger,
                        self._best_live_result,
                        float(self._best_live_rmse),
                        title="[BEST RMSE  live run record]",
                    )

            elif remind:
                self._last_live_log_mono = now

                sk = self._best_live_result.get("sigma_knots")

                k_sigma = int(np.asarray(sk, dtype=np.float64).size) if sk is not None else 0

                d_nm = float(self._best_live_result.get("d_nm", float("nan")))

                self.logger.info(
                    "[BEST DISPLAYED] reminder (~%.0f s) RMSE=%.6f | d_nm=%.2f | K_sigma=%d (detail: last record above)",
                    float(self._LIVE_LOG_REMINDER_S),
                    float(self._best_live_rmse),
                    d_nm,
                    k_sigma,
                )

        self._plot_result(to_plot, plot_source="live")

        self._refresh_data_table(result_override=to_plot)

        try:
            lam_u = np.asarray(to_plot.get("lam_nm", []), dtype=np.float64).ravel()

            n_u = np.asarray(to_plot.get("n_lam", []), dtype=np.float64).ravel()

            k_u = np.asarray(to_plot.get("k_lam", []), dtype=np.float64).ravel()

            if lam_u.size and n_u.size == lam_u.size and k_u.size == lam_u.size:
                self._update_persistent_nk_monitor(lam_u, n_u, k_u, float(to_plot.get("d_nm", float("nan"))))

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("nk monitor update in _on_live_update failed", exc_info=True)

    def _start_auto_best_second_stage(self) -> None:

        pend = self._auto_best_second_stage_pending

        self._auto_best_second_stage_pending = None

        if not isinstance(pend, dict):
            return

        seed = pend.get("seed")

        cfg2 = pend.get("cfg")

        if not isinstance(seed, dict) or cfg2 is None:
            return

        if self.logger:
            self.logger.info(
                "AUTO_BEST stage2 start | seed_rmse=%.6f seed_d=%.4f",
                float(np.sqrt(max(float(seed.get("mse", 0.0)), 0.0))),
                float(seed.get("d_nm", float("nan"))),
            )

        CertusIndexSplineApp._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._log_prog_last = -1

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        self._worker = GenericWorker(
            worker_auto_best_split_knot_refinement,
            seed,
            cfg2,
            self._stop_event,
        )

        _wsig_ab = self._worker.signals

        def _ab_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            _wsig_ab.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _ab_progress

        self._worker_role = "auto_best"

        self._worker.signals.progress.connect(self._on_progress)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        self._worker.signals.live.connect(self._on_live_update)

        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self._worker.start()

    def _plot_result(self, r: dict, *, plot_source: str = "maj") -> None:

        lam0_src = r.get("lam_nm")
        if lam0_src is None and self.df is not None and "lambda" in self.df.columns:
            lam0_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("_plot_result: missing lam_nm in result; fallback to experimental lambda grid.")
        lam0 = np.asarray(lam0_src if lam0_src is not None else [], dtype=np.float64).ravel()
        if lam0.size == 0:
            self.lbl_status.setText("Aucun lambda disponible pour tracer le resultat.")
            if self.logger:
                self.logger.error("_plot_result aborted: lam_nm unavailable after fallback.")
            self._spectrum_clear_theory_probe()
            return

        tt0 = np.asarray(r["t_theo"], dtype=np.float64).ravel()

        n0 = np.asarray(r["n_lam"], dtype=np.float64).ravel()

        k0 = np.asarray(r["k_lam"], dtype=np.float64).ravel()

        lam_exp: np.ndarray | None = None

        if self.df is not None and "lambda" in self.df.columns:
            lam_exp = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

        plot_r_model = (
            r.get("r_theo") is not None
            and self.df is not None
            and "R" in self.df.columns
            and lam_exp is not None
            and lam_exp.size > 0
        )

        if plot_r_model:
            rt0 = np.asarray(r["r_theo"], dtype=np.float64).ravel()

            lam_s, pack, order = _spectral_display_align(lam0, tt0, n0, k0, rt0)

            tt_s, n_s, k_s, rt_s = pack[0], pack[1], pack[2], pack[3]

        else:
            lam_s, pack, order = _spectral_display_align(lam0, tt0, n0, k0)

            tt_s, n_s, k_s = pack[0], pack[1], pack[2]

            rt_s = None

        x_mod, x_lbl = self._transform_spectrum_x(lam_s)

        self._spectrum_theory_probe_lam_nm = np.asarray(lam_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_n = np.asarray(n_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_k = np.asarray(k_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_tt = np.asarray(tt_s, dtype=np.float64).ravel().copy()
        self._spectrum_theory_probe_rt = np.asarray(rt_s, dtype=np.float64).ravel().copy() if rt_s is not None else None
        self._spectrum_theory_probe_d_nm = float(r.get("d_nm", float("nan")))

        self.plot_T.clear()

        self.plot_n.clear()

        self.plot_k.clear()

        x_exp: np.ndarray | None = None

        if lam_exp is not None and lam_exp.size:
            x_exp, _ = self._transform_spectrum_x(lam_exp)

        if self.df is not None and "T" in self.df.columns and lam_exp is not None and lam_exp.size:
            ye_raw = _to_fraction_T(self.df["T"].to_numpy(dtype=np.float64))

            ye = ye_raw

            ne = "T/Tsub exp" if bool(r.get("t_is_ratio", False)) else "T exp"

            self._add_curve(self.plot_T, x_exp, ye, CertusTheme.TEXT_SUB, ne, True)

        nm = "T/Tsub model" if bool(r.get("t_is_ratio", False)) else "T model"

        self._add_curve(self.plot_T, x_mod, tt_s, CertusTheme.PRIMARY, nm)

        sigma_knots = np.asarray(r.get("sigma_knots", []), dtype=np.float64).ravel()
        if sigma_knots.size:
            lam_k_t, tt_k = _interp_series_at_sigma_knots(lam_s, tt_s, sigma_knots)
            if lam_k_t.size:
                x_k_t, _ = self._transform_spectrum_x(lam_k_t)
                _plot_spectrum_raw_scatter(
                    self.plot_T,
                    x_k_t,
                    tt_k,
                    color=CertusTheme.PRIMARY,
                    name="T model knots",
                    symbol_size=11,
                )

        if plot_r_model and rt_s is not None:
            ye_raw = _to_fraction_T(self.df["R"].to_numpy(dtype=np.float64))

            ye = ye_raw

            r_ne = "R/Tsub exp" if bool(r.get("t_is_ratio", False)) else "R exp"

            self._add_curve(self.plot_T, x_exp, ye, "#888888", r_ne, True)

            r_nm = "R/Tsub model" if bool(r.get("t_is_ratio", False)) else "R model"

            self._add_curve(self.plot_T, x_mod, rt_s, CertusTheme.SECONDARY, r_nm)

            if sigma_knots.size:
                lam_k_r, rt_k = _interp_series_at_sigma_knots(lam_s, rt_s, sigma_knots)
                if lam_k_r.size:
                    x_k_r, _ = self._transform_spectrum_x(lam_k_r)
                    _plot_spectrum_raw_scatter(
                        self.plot_T,
                        x_k_r,
                        rt_k,
                        color=CertusTheme.SECONDARY,
                        name="R model knots",
                        symbol_size=11,
                    )

        lk = np.full(k_s.shape, np.nan, dtype=np.float64)

        mk = np.isfinite(k_s) & (k_s >= 0.0)

        lk[mk] = np.log10(np.maximum(k_s[mk], 1e-30))

        self._add_curve(self.plot_n, lam_s, n_s, "#0057ff", "n", crosshair_primary=True)

        self._add_curve(self.plot_k, lam_s, lk, "#ff5a00", "k", crosshair_primary=True)

        self._plot_corridor_tab(r, lam_s, n_s, k_s, spectral_sort_order=order)

        self._plot_corridor_rmse_tab(r)

        d_nm = float(r.get("d_nm", float("nan")))

        d_txt = f"d = {d_nm:.1f} nm" if np.isfinite(d_nm) else "d = "

        try:
            self.plot_n.plotItem.setTitle(f"n(lambda)  {d_txt}", color=CertusTheme.PRIMARY, size="10pt")

            self.plot_k.plotItem.setTitle(f"k(lambda)  {d_txt}", color=CertusTheme.PRIMARY, size="10pt")

        except (AttributeError, RuntimeError):
            logger.debug("Index plot title set failed", exc_info=True)

        self.plot_T.autoRange()

        self._apply_spectrum_x_axis_label(x_lbl)

        y_spec = tt_s if rt_s is None else np.concatenate([tt_s, rt_s])
        _add_spectrum_thickness_badge(self.plot_T, x_mod, y_spec, d_nm)

        self.plot_n.autoRange()

        _apply_fixed_log_k_axis(self.plot_k)

        if lam0.size > 0:
            span_lo = float(np.nanmin(lam0))

            span_hi = float(np.nanmax(lam0))

            if np.isfinite(span_lo) and np.isfinite(span_hi) and span_hi > span_lo:
                pad = 0.02 * (span_hi - span_lo)

                self.plot_n.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

                self.plot_k.plotItem.setXRange(span_lo - pad, span_hi + pad, padding=0.0)

        self._apply_spectrum_plot_title(r)

        self._update_rmse_fit_region_overlay()

        _log_tgt = self.logger if self.logger is not None else logger
        try:
            _rm_log = float(r.get("rmse", float("nan")))
            if not np.isfinite(_rm_log):
                _rm_log = float(np.sqrt(max(float(r.get("mse", 0.0)), 0.0)))
        except (TypeError, ValueError):
            _rm_log = float("nan")
        _rm_s = f"{_rm_log:.8f}" if np.isfinite(_rm_log) else "n/a"
        _d_log = float(d_nm)
        _d_s = f"{_d_log:.4f}" if np.isfinite(_d_log) else "n/a"
        _corridor_pts = int(np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64).size)
        _msg = (
            f"INDEX_SPLINE [GRAPHIQUES] {plot_source} | spectral T/R+n,k (+ onglets corridor/NL selon données) "
            f"| lam_pts={int(lam_s.size)} exp_pts={str(int(lam_exp.size)) if lam_exp is not None and lam_exp.size else '0'} abs={x_lbl} | d_nm={_d_s} rmse={_rm_s} | R_couche={bool(plot_r_model)} K_sigma={int(sigma_knots.size)} | profil_corridoir_d={_corridor_pts}pts"
        )
        if plot_source == "live":
            _log_tgt.debug("%s", _msg)
        else:
            _log_tgt.info("%s", _msg)

        # Auto-refresh corridor RMSE profile window if open
        win = getattr(self, "_corridor_rmse_profile_win", None)
        if win is not None and win.isVisible():
            d_prof = np.asarray(r.get("profile_d_values_nm", []), dtype=np.float64)
            r_prof = np.asarray(r.get("profile_d_rmse_values", []), dtype=np.float64)
            if d_prof.size > 0 and r_prof.size == d_prof.size:
                rmse_thresh = r.get("profile_d_rmse_thresh")
                win.update_profile(d_prof, r_prof, rmse_thresh)

    def _log_optimization_header(self, cfg: SplineOptConfig) -> None:
        """Startup INFO block (CERTUS_INDEX+ detail: context + displayed RMSE reminder)."""

        if not self.logger:
            return

        lam = np.asarray(cfg.lam_nm, dtype=np.float64)

        npt = int(lam.size)

        if npt:
            l0, l1 = float(np.nanmin(lam)), float(np.nanmax(lam))

        else:
            l0 = l1 = float("nan")

        path_hint = getattr(self, "_last_spectrum_path", "").strip() or (
            str(self.lbl_file.text()).strip() if hasattr(self, "lbl_file") else ""
        )

        dt_name = cfg.data_type.name if hasattr(cfg.data_type, "name") else str(cfg.data_type)

        self.logger.info(" INDEX-SPLINE  optimization start ")

        self.logger.info("Spectrum: %s", path_hint or "(unknown path)")

        self.logger.info(
            "substrate: %s | lambda [%g, %g] nm | %d points | substrate-normalized T: %s",
            cfg.substrate_name,
            l0,
            l1,
            npt,
            cfg.t_is_ratio,
        )

        self.logger.info(
            "Target: %s | weights wT=%.4g wR=%.4g | spectral quadrature: ln lambda (trapezoids, no cap)",
            dt_name,
            cfg.weight_t,
            cfg.weight_r,
        )

        self.logger.info(
            "d  [%.2f, %.2f] nm | segments on sigma mesh (n_seg)=%d",
            cfg.d_lo,
            cfg.d_hi,
            cfg.n_seg,
        )

        if cfg.n_mono_band_nm is not None:
            a, b = float(cfg.n_mono_band_nm[0]), float(cfg.n_mono_band_nm[1])

            self.logger.info(
                "n(sigma) monotonicity on segments intersecting lambda[%.0f, %.0f] nm | continuous-law penalty w=%.4g",
                min(a, b),
                max(a, b),
                float(cfg.n_mono_continuous_penalty),
            )

        else:
            self.logger.info("n(sigma) monotonicity on fixed band: disabled")

        w_nlam = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)

        band_nlam = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)

        if w_nlam > 0.0 and band_nlam is not None:
            b0, b1 = float(band_nlam[0]), float(band_nlam[1])

            self.logger.info(
                "n increasing with lambda forbidden (segments sigma ? lambda[%.0f, %.0f] nm) | penalty w=%.4g",
                min(b0, b1),
                max(b0, b1),
                w_nlam,
            )

        else:
            self.logger.info("Penalty for increasing n(lambda): disabled (w=0 or band None)")

        n_fit = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))

        if cfg.rmse_fit_lambda_nm is not None:
            rl0, rl1 = float(cfg.rmse_fit_lambda_nm[0]), float(cfg.rmse_fit_lambda_nm[1])

            self.logger.info(
                "RMSE fit lambda: [%.4g, %.4g] nm (%d points)",
                min(rl0, rl1),
                max(rl0, rl1),
                n_fit,
            )

        else:
            self.logger.info("RMSE fit lambda: full spectrum (%d objective points)", n_fit)

        self.logger.info("Local optimizer: polish maxfun=%d", cfg.polish_maxfun)

        self.logger.info("substrate: no Deltan_sub refinement (nominal substrate).")

        prof = str(self.cb_profilee.currentData() or "fast") if hasattr(self, "cb_profilee") else "fast"

        self.logger.info("GUI performance profile: %s", prof)

        self.logger.info("Auto-Ksigma: disabled (K fixed to n_seg+1 initial knots)")

        self.logger.info(
            "[Reminder] During optimization, live snapshots follow the best RMSE seen at that moment. "
            "At the end, rmse/mse in the dict may reflect final indices (cubic spline polish in sigma) "
            "- compare to pipeline_best_rmse_watermark if needed. Curves on screen = n_lam/k_lam from final dict."
        )

class _DataMixin:
    """Mixin containing data table and nk data preparation methods."""

    def _prepare_nk_data_tab_series(
        self, r: dict[str, Any]
    ) -> (
        tuple[
            np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
        ]
        | None
    ):
        """n/k series (and NL, envelopes) interpolated on piecewise lambda grid."""

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data tab n/k: missing lam_nm in result; fallback to experimental lambda grid.")
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()

        n_ = np.asarray(r["n_lam"], dtype=np.float64).ravel()

        k_ = np.asarray(r["k_lam"], dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_.size, k_.size))

        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")

        ls = lam[:m0][order]

        ns = n_[:m0][order]

        ks = k_[:m0][order]

        fg = np.isfinite(ls)

        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))

        hi = float(np.nanmax(ls[fg]))

        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)

        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, ns, left=np.nan, right=np.nan)

        k_g = np.interp(lam_g, ls, ks, left=np.nan, right=np.nan)

        m = m0

        lam_full = lam[:m0]

        n_nl_g = np.full_like(lam_g, np.nan)

        k_nl_g = np.full_like(lam_g, np.nan)

        n_lo_g = np.full_like(lam_g, np.nan)

        n_hi_g = np.full_like(lam_g, np.nan)

        k_lo_g = np.full_like(lam_g, np.nan)

        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(r.get("profile_d_enabled", False)) or bool(r.get("manual_corridor_active", False)):
            cn_lo = np.asarray(r.get("corridor_n_lo", []), dtype=np.float64).ravel()

            cn_hi = np.asarray(r.get("corridor_n_hi", []), dtype=np.float64).ravel()

            ck_lo = np.asarray(r.get("corridor_k_lo", []), dtype=np.float64).ravel()

            ck_hi = np.asarray(r.get("corridor_k_hi", []), dtype=np.float64).ravel()

            lsz = lam_full.size

            if cn_lo.size == lsz and cn_hi.size == lsz and ck_lo.size == lsz and ck_hi.size == lsz:
                n_lo_g = np.interp(lam_g, ls, cn_lo[:m][order], left=np.nan, right=np.nan)

                n_hi_g = np.interp(lam_g, ls, cn_hi[:m][order], left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, ls, ck_lo[:m][order], left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, ls, ck_hi[:m][order], left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots and Detailed Corridor Tab
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        return (lam_g, n_g, k_g, n_nl_g, k_nl_g, n_lo_g, n_hi_g, k_lo_g, k_hi_g)

    def _prepare_data_th_tab_series(
        self, r: dict[str, Any]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:

        lam_src = r.get("lam_nm")
        if lam_src is None and self.df is not None and "lambda" in self.df.columns:
            lam_src = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))
            if self.logger:
                self.logger.warning("Data TH: missing lam_nm in result; fallback to experimental lambda grid.")

        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        n_src = np.asarray(r.get("n_lam", []), dtype=np.float64).ravel()
        k_src = np.asarray(r.get("k_lam", []), dtype=np.float64).ravel()
        t_src = np.asarray(r.get("t_theo", []), dtype=np.float64).ravel()
        r_src = np.asarray(r.get("r_theo", []), dtype=np.float64).ravel()

        m0 = int(min(lam.size, n_src.size, k_src.size))
        if m0 <= 0:
            return None

        order = np.argsort(lam[:m0], kind="mergesort")
        ls = lam[:m0][order]
        n_s = n_src[:m0][order]
        k_s = k_src[:m0][order]

        fg = np.isfinite(ls)
        if not np.any(fg):
            return None

        lo = float(np.nanmin(ls[fg]))
        hi = float(np.nanmax(ls[fg]))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if lam_g.size == 0:
            return None

        n_g = np.interp(lam_g, ls, n_s, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, ls, k_s, left=np.nan, right=np.nan)

        t_g = np.full_like(lam_g, np.nan)
        if t_src.size >= m0:
            t_s = t_src[:m0][order]
            t_g = np.interp(lam_g, ls, t_s, left=np.nan, right=np.nan)

        r_g = np.full_like(lam_g, np.nan)
        if r_src.size >= m0:
            r_s = r_src[:m0][order]
            r_g = np.interp(lam_g, ls, r_s, left=np.nan, right=np.nan)

        ns_g = np.full_like(lam_g, np.nan)
        ns_src = np.asarray(r.get("n_sub_effective", []), dtype=np.float64).ravel()
        if ns_src.size >= m0:
            ns_s = ns_src[:m0][order]
            ns_g = np.interp(lam_g, ls, ns_s, left=np.nan, right=np.nan)
        else:
            try:
                sub_name = str(
                    r.get("substrate_name")
                    or getattr(self, "sub_name", "")
                    or (
                        self.cb_sub.currentData()
                        if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                        else ""
                    )
                )
                sid = substrate_id_from_name(sub_name)
                ns_raw = np.asarray(_get_substrate_n_array_spline(sid, lam_g), dtype=np.float64).ravel()
                if ns_raw.size == lam_g.size:
                    ns_g = ns_raw
            except NUMERICAL_FAULT_EXCEPTIONS:
                if self.logger:
                    self.logger.debug("Data TH substrate ns build failed", exc_info=True)
            except (TypeError, ValueError):
                if self.logger:
                    self.logger.debug("Data TH substrate lookup failed", exc_info=True)

        d_nm = float(r.get("d_nm", float("nan")))
        d_g = np.full_like(lam_g, d_nm, dtype=np.float64)

        return (lam_g, n_g, k_g, d_g, ns_g, t_g, r_g)

    def _baseline_substrate_n_for_result(
        self,
        result: dict,
        *,
        lam_override: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray] | None:

        lam_src = lam_override if lam_override is not None else result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        lam = np.asarray(lam_src if lam_src is not None else [], dtype=np.float64).ravel()
        if lam.size == 0:
            return None

        sub_name = str(
            result.get("substrate_name")
            or getattr(self, "sub_name", "")
            or (
                self.cb_sub.currentData()
                if hasattr(self, "cb_sub") and callable(getattr(self.cb_sub, "currentData", None))
                else ""
            )
        )
        sid = substrate_id_from_name(sub_name)
        n_sub = np.asarray(_get_substrate_n_array_spline(sid, lam), dtype=np.float64).ravel()
        if n_sub.size != lam.size:
            return None
        return lam.copy(), n_sub.copy()

    @staticmethod
    def _decorate_result_with_substrate_offset(
        result: dict,
        *,
        n_sub_base: np.ndarray,
        delta_ns: float,
    ) -> dict:

        out = dict(result)
        base = np.asarray(n_sub_base, dtype=np.float64).ravel().copy()
        out["n_sub_base"] = base
        out["substrate_n_offset"] = float(delta_ns)
        out["n_sub_effective"] = base + float(delta_ns)
        return out

    @staticmethod
    def _cfg_with_result_substrate(cfg_base: SplineOptConfig, result: dict) -> SplineOptConfig:

        n_eff = np.asarray(result.get("n_sub_effective", []), dtype=np.float64).ravel()
        lam_cfg = np.asarray(getattr(cfg_base, "lam_nm", []), dtype=np.float64).ravel()
        if lam_cfg.size and n_eff.size == lam_cfg.size:
            n_base = np.asarray(result.get("n_sub_base", []), dtype=np.float64).ravel()
            if n_base.size != lam_cfg.size:
                n_base = n_eff.copy()
            return cfg_base.replace(
                n_sub=n_eff.copy(),
                substrate_n_base=n_base.copy(),
                substrate_n_offset=float(result.get("substrate_n_offset", 0.0)),
            )
        return cfg_base

    def _apply_manual_substrate_offset_preview(self, seed_result: dict, delta_ns: float) -> bool:

        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            return False

        lam_preview = np.asarray(seed_result.get("lam_nm", getattr(cfg_base, "lam_nm", [])), dtype=np.float64).ravel()
        baseline_payload = self._baseline_substrate_n_for_result(seed_result, lam_override=lam_preview)
        if baseline_payload is None:
            return False
        _, n_sub_base = baseline_payload

        preview = self._decorate_result_with_substrate_offset(
            seed_result,
            n_sub_base=n_sub_base,
            delta_ns=float(delta_ns),
        )
        cfg_preview = cfg_base.replace(
            n_sub=np.asarray(preview["n_sub_effective"], dtype=np.float64).ravel().copy(),
            substrate_n_base=np.asarray(preview["n_sub_base"], dtype=np.float64).ravel().copy(),
            substrate_n_offset=float(delta_ns),
        )
        _sync_theoretical_tr_from_nk_dict(
            cfg_preview,
            preview,
            log=self.logger,
            reason="manual_delta_ns_preview",
        )
        try:
            mse_preview, rmse_preview = spectral_mse_rmse_masked_from_nk(
                cfg_preview,
                preview,
                np.asarray(preview.get("lam_nm", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("n_lam", []), dtype=np.float64).ravel(),
                np.asarray(preview.get("k_lam", []), dtype=np.float64).ravel(),
                float(preview.get("d_nm", float("nan"))),
            )
            if np.isfinite(mse_preview):
                preview["mse"] = float(mse_preview)
            if np.isfinite(rmse_preview):
                preview["rmse"] = float(rmse_preview)
        except (TypeError, ValueError, RuntimeError):
            if self.logger:
                self.logger.debug("Manual delta-ns preview RMSE recompute failed", exc_info=True)

        self._last_worker_result = dict(preview)
        self._last_result = dict(preview)
        self._plot_result(preview, plot_source="manual_delta_ns_preview")
        self._refresh_data_table(result_override=preview)
        self.lbl_status.setText(
            CertusIndexSplineApp._post_optimization_ready_status(
                CertusIndexSplineApp._format_post_optimization_status(preview, preview)
            )
        )
        return True

    def _refresh_manual_dialog_preview(self, dialog: ManualSigmaKnotDialog | None, preview_result: dict | None) -> None:

        if not isinstance(dialog, ManualSigmaKnotDialog) or not isinstance(preview_result, dict):
            return
        lam_preview = np.asarray(preview_result.get("lam_nm", []), dtype=np.float64).ravel()
        y_preview = np.asarray(preview_result.get("t_theo", []), dtype=np.float64).ravel()
        dialog.update_model_preview(lam_preview, y_preview)
        d_preview, rmse_preview = CertusIndexSplineApp._runtime_metrics_from_result_dict(preview_result)
        dialog.set_runtime_metrics(d_preview, rmse_preview)

    def _copy_nk_to_clipboard(self) -> None:

        if self._last_result is None:
            QMessageBox.information(self, "Clipboard", "Run an optimization first.")

            return

        r = self._last_result

        ser = self._prepare_nk_data_tab_series(r)

        if ser is None:
            QMessageBox.information(self, "Clipboard", "Empty grid.")

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        hdr = "lambda_nm\tn\tn_alpha\tn_envelope_min\tn_envelope_max\tk\tk_alpha\tk_envelope_min\tk_envelope_max"

        lines = [hdr]

        m = int(lam_g.size)

        for i in range(m):
            row = f"{float(lam_g[i]):.4f}\t"

            row += self._fmt_n_data_tab(float(n_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_nl_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_lo_g[i])) + "\t"

            row += self._fmt_n_data_tab(float(n_hi_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_nl_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_lo_g[i])) + "\t"

            row += self._fmt_k_data_tab(float(k_hi_g[i]))

            lines.append(row)

        cb = QApplication.clipboard()

        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")

            return

        cb.setText("\n".join(lines))

        self.lbl_status.setText("Data table copied (TSV).")

        self.btn_copy_nk.setText(" Copied!")

        QTimer.singleShot(1800, lambda: self.btn_copy_nk.setText("Copy full table (TSV)"))

    def _copy_data_th_to_clipboard(self) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        if t.rowCount() <= 0 or t.columnCount() <= 0:
            QMessageBox.information(self, "Clipboard", "Data TH empty.")
            return

        headers = [
            t.horizontalHeaderItem(c).text() if t.horizontalHeaderItem(c) else "" for c in range(t.columnCount())
        ]
        lines = ["\t".join(headers)]

        for r in range(t.rowCount()):
            row = [t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())]
            lines.append("\t".join(row))

        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText("\n".join(lines))
        self.lbl_status.setText("Data TH copied (TSV).")

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setText(" Copied!")
            QTimer.singleShot(
                1800,
                lambda: self.btn_copy_data_th.setText("Copier tableau Data TH (TSV)"),
            )

    def _on_data_preview_plot_mouse_moved(
        self,
        src: CertusScientificPlot,
        pos: Any,
        x: float,
        y: float,
        y_show: Any,
    ) -> None:
        """Synchronizes both previews (lambda) and tooltip with all interpolated n and k."""

        del pos, y_show

        s = getattr(self, "_data_preview_series", None)

        if not isinstance(s, dict):
            return

        pn = self.plot_data_preview_n

        pk = self.plot_data_preview_k

        lam = s.get("lam")

        if lam is None:
            return

        lam_a = np.asarray(lam, dtype=np.float64).ravel()

        def _fmt_nq(v: float) -> str:

            return self._fmt_n_data_tab(v) if np.isfinite(v) else "-"

        def _fmt_kq(v: float) -> str:

            if not np.isfinite(v) or v < 0:
                return "-"

            return self._fmt_k_data_tab(float(v))

        n_at = self._interp_preview_axis(lam_a, s["n"], x)

        nnl_at = self._interp_preview_axis(lam_a, s["n_nl"], x)

        nlo_at = self._interp_preview_axis(lam_a, s["n_lo"], x)

        nhi_at = self._interp_preview_axis(lam_a, s["n_hi"], x)

        k_at = self._interp_preview_axis(lam_a, s["k"], x)

        knl_at = self._interp_preview_axis(lam_a, s["k_nl"], x)

        klo_at = self._interp_preview_axis(lam_a, s["k_lo"], x)

        khi_at = self._interp_preview_axis(lam_a, s["k_hi"], x)

        lam_txt = float(x)

        txt = (
            f"lambda = {lam_txt:.2f} nm\n"
            f"n={_fmt_nq(n_at)}  n_alpha={_fmt_nq(nnl_at)}  n_min={_fmt_nq(nlo_at)}  n_max={_fmt_nq(nhi_at)}\n"
            f"k={_fmt_kq(k_at)}  k_alpha={_fmt_kq(knl_at)}  k_min={_fmt_kq(klo_at)}  k_max={_fmt_kq(khi_at)}"
        )

        k_floor = float(s.get("k_floor", 1e-30))

        if not (np.isfinite(k_floor) and k_floor > 0.0):
            k_floor = 1e-30

        pn.vLine.setPos(x)

        pk.vLine.setPos(x)

        pn.hLine.setVisible(False)

        pk.hLine.setVisible(False)

        for w in (pn, pk):
            try:
                xr = w.plotItem.vb.viewRange()[0]

                x_lo, x_hi = float(xr[0]), float(xr[1])

                span = x_hi - x_lo

                if span > 0 and x > x_lo + 0.78 * span:
                    w.info_label.setAnchor((1, 1))

                else:
                    w.info_label.setAnchor((0, 1))

            except NUMERICAL_FAULT_EXCEPTIONS:
                w.info_label.setAnchor((0, 1))

        pn.info_label.setText(txt)

        pk.info_label.setText(txt)

        if src is pn:
            pn_y = float(y)

            if np.isfinite(k_at) and float(k_at) > 0.0:
                pk_y = float(k_at)

            elif np.isfinite(k_at) and float(k_at) == 0.0:
                pk_y = k_floor

            else:
                pk_y = self._vb_mid_y_plot(pk)

        else:
            pk_y = float(y)

            pn_y = float(n_at) if np.isfinite(n_at) else self._vb_mid_y_plot(pn)

        pn.info_label.setPos(x, pn_y)

        pk.info_label.setPos(x, pk_y)

    def _refresh_data_table(self, result_override: dict | None = None) -> None:

        if not hasattr(self, "table_nk"):
            return

        t = self.table_nk

        t.setRowCount(0)

        result_eff = result_override if isinstance(result_override, dict) else self._last_result

        if result_eff is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=None)

            return

        ser = self._prepare_nk_data_tab_series(result_eff)

        if ser is None:
            self.btn_copy_nk.setEnabled(False)

            self.btn_export_nk.setEnabled(False)

            self._refresh_data_preview_plots(ser=None)

            self._refresh_data_th_table(result_eff=result_eff)

            return

        (
            lam_g,
            n_g,
            k_g,
            n_nl_g,
            k_nl_g,
            n_lo_g,
            n_hi_g,
            k_lo_g,
            k_hi_g,
        ) = ser

        m = int(lam_g.size)

        t.setColumnCount(9)

        t.setHorizontalHeaderLabels(
            [
                "lambda (nm)",
                "n",
                "n_alpha",
                "n env min",
                "n env max",
                "k",
                "k_alpha",
                "k env min",
                "k env max",
            ]
        )

        t.setRowCount(m)

        n_valid = 0

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")

            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))

            if np.isfinite(n_g[i]) and np.isfinite(k_g[i]) and float(k_g[i]) >= 0.0:
                n_valid += 1

            t.setItem(i, 1, _cell_n(float(n_g[i])))

            t.setItem(i, 2, _cell_n(float(n_nl_g[i])))

            t.setItem(i, 3, _cell_n(float(n_lo_g[i])))

            t.setItem(i, 4, _cell_n(float(n_hi_g[i])))

            t.setItem(i, 5, _cell_k(float(k_g[i])))

            t.setItem(i, 6, _cell_k(float(k_nl_g[i])))

            t.setItem(i, 7, _cell_k(float(k_lo_g[i])))

            t.setItem(i, 8, _cell_k(float(k_hi_g[i])))

        self.btn_copy_nk.setEnabled(m > 0 and n_valid > 0)

        self.btn_export_nk.setEnabled(m > 0 and n_valid > 0)

        self._refresh_data_preview_plots(ser=ser)
        self._refresh_data_th_table(result_eff=result_eff)
        self._refresh_corridor_table(result_eff)

    def _refresh_data_th_table(self, result_eff: dict | None) -> None:

        if not hasattr(self, "table_data_th"):
            return

        t = self.table_data_th
        t.setRowCount(0)

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(False)

        if not isinstance(result_eff, dict):
            return

        ser = self._prepare_data_th_tab_series(result_eff)
        if ser is None:
            return

        lam_g, n_g, k_g, d_g, ns_g, t_g, r_g = ser

        m = int(lam_g.size)
        t.setColumnCount(7)
        t.setHorizontalHeaderLabels(["lambda (nm)", "n", "k", "d (nm)", "ns", "Tth", "Rth"])
        t.setRowCount(m)

        def _cell_n(x: float) -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_n_data_tab(float(x)))

        def _cell_k(x: float) -> QTableWidgetItem:

            if not np.isfinite(x) or x < 0:
                return QTableWidgetItem("-")
            return QTableWidgetItem(self._fmt_k_data_tab(float(x)))

        def _cell_lin(x: float, fmt: str = ".6f") -> QTableWidgetItem:

            if not np.isfinite(x):
                return QTableWidgetItem("-")
            return QTableWidgetItem(f"{float(x):{fmt}}")

        for i in range(m):
            t.setItem(i, 0, QTableWidgetItem(f"{float(lam_g[i]):.4f}"))
            t.setItem(i, 1, _cell_n(float(n_g[i])))
            t.setItem(i, 2, _cell_k(float(k_g[i])))
            t.setItem(i, 3, _cell_lin(float(d_g[i]), ".4f"))
            t.setItem(i, 4, _cell_n(float(ns_g[i])))
            t.setItem(i, 5, _cell_lin(float(t_g[i])))
            t.setItem(i, 6, _cell_lin(float(r_g[i])))

        if hasattr(self, "btn_copy_data_th"):
            self.btn_copy_data_th.setEnabled(m > 0)

class _CorridorGenMixin:
    """Mixin containing corridor generation, application and table refresh methods."""

    def _on_corridor_rmse_grid_live_update(self, payload: object) -> None:
        """Affiche la courbe RMSE(d) au fil de l eau pendant le recalcul de grille."""

        worker_role = str(getattr(self, "_worker_role", "") or "")
        if worker_role not in {"rmse_grid", "corridors"}:
            return

        if not isinstance(payload, dict):
            return

        d_live = np.asarray(payload.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        r_live = np.asarray(payload.get("profile_d_rmse_values", []), dtype=np.float64).ravel()

        if d_live.size == 0 or r_live.size != d_live.size:
            return

        cur = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        upd = dict(cur)

        upd["profile_d_values_nm"] = d_live

        upd["profile_d_rmse_values"] = r_live

        k_live = np.asarray(payload.get("profile_d_manual_grid_point_kind", []), dtype=np.int32).ravel()
        if k_live.size == d_live.size:
            upd["profile_d_manual_grid_point_kind"] = k_live
        st_live = np.asarray(
            payload.get("profile_d_manual_grid_point_status_code", []),
            dtype=np.int32,
        ).ravel()
        if st_live.size == d_live.size:
            upd["profile_d_manual_grid_point_status_code"] = st_live

        upd["profile_d_status"] = str(payload.get("profile_d_status", "manual_grid_live"))

        upd["profile_d_manual_grid_progress"] = float(payload.get("profile_d_manual_grid_progress", float("nan")))

        upd["profile_d_manual_grid_done_points"] = int(payload.get("profile_d_manual_grid_done_points", d_live.size))

        upd["profile_d_manual_grid_total_points"] = int(payload.get("profile_d_manual_grid_total_points", d_live.size))
        upd["profile_d_manual_grid_base_done_points"] = int(
            payload.get("profile_d_manual_grid_base_done_points", upd["profile_d_manual_grid_done_points"])
        )
        upd["profile_d_manual_grid_extra_done_points"] = int(payload.get("profile_d_manual_grid_extra_done_points", 0))

        if "profile_d_manual_grid_breakpoint_events" in payload:
            upd["profile_d_manual_grid_breakpoint_events"] = payload.get("profile_d_manual_grid_breakpoint_events")

        self._last_result = upd

        n_done_payload = int(upd.get("profile_d_manual_grid_done_points", d_live.size))
        n_tot = int(upd.get("profile_d_manual_grid_total_points", d_live.size))
        p_live = float(upd.get("profile_d_manual_grid_progress", float("nan")))
        if np.isfinite(p_live):
            n_done = int(max(0, min(n_tot, round(float(p_live) * float(max(1, n_tot))))))
            n_done = max(n_done, min(1, n_done_payload))
        else:
            n_done = n_done_payload
        n_base_done = int(upd.get("profile_d_manual_grid_base_done_points", n_done))
        n_extra_done = int(upd.get("profile_d_manual_grid_extra_done_points", max(0, n_done - n_tot)))

        d_cur = float(payload.get("profile_d_manual_grid_current_d_nm", float("nan")))

        if worker_role == "rmse_grid":
            self._set_corridor_grid_progress_ui(
                done=n_done,
                total=n_tot,
                base_done=n_base_done,
                base_total=n_tot,
                extra_done=n_extra_done,
                current_d_nm=(d_cur if np.isfinite(d_cur) else None),
            )

        now_ts = float(time.perf_counter())
        last_ts = float(getattr(self, "_corridor_rmse_live_last_plot_ts", float("nan")))
        min_dt = float(getattr(self, "_corridor_rmse_live_plot_min_interval_s", 0.12) or 0.12)
        should_plot = (
            n_done <= 1 or n_done >= n_tot or (not np.isfinite(last_ts)) or ((now_ts - last_ts) >= max(0.02, min_dt))
        )
        if should_plot:
            try:
                self._plot_corridor_rmse_tab(upd)
                # Hard safety net: if live payload has finite points but plot pipeline
                # produced no visible data items, draw a minimal scatter fallback.
                if hasattr(self, "plot_corridor_rmse_d"):
                    plot_item = getattr(self.plot_corridor_rmse_d, "plotItem", None)
                    data_items = []
                    if plot_item is not None and hasattr(plot_item, "listDataItems"):
                        try:
                            data_items = list(plot_item.listDataItems())
                        except (TypeError, ValueError, RuntimeError, AttributeError):
                            data_items = []
                    if len(data_items) == 0:
                        m_live = np.isfinite(d_live) & np.isfinite(r_live)
                        if np.any(m_live):
                            d_fb = np.asarray(d_live[m_live], dtype=np.float64).ravel()
                            r_fb = np.asarray(r_live[m_live], dtype=np.float64).ravel()
                            self.plot_corridor_rmse_d.addItem(
                                pg.ScatterPlotItem(
                                    d_fb,
                                    r_fb,
                                    pen=pg.mkPen(CertusTheme.PRIMARY, width=0),
                                    brush=pg.mkBrush(0, 87, 255, 160),
                                    size=5,
                                    symbol="o",
                                    name="RMSE(d) live",
                                )
                            )
                            self._set_corridor_rmse_view_data_bounds(d_fb, r_fb)
                self._corridor_rmse_live_last_plot_ts = now_ts

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("RMSE(d) live plot update failed", exc_info=True)

        if self.logger and (n_done <= 1 or n_done >= n_tot or (n_done % 5 == 0)):
            r_at_cur = float("nan")
            if np.isfinite(d_cur) and d_live.size and r_live.size == d_live.size:
                fg_l = np.isfinite(d_live) & np.isfinite(r_live)
                if np.any(fg_l):
                    dl = d_live[fg_l]
                    rl = r_live[fg_l]
                    j_nearest = int(np.argmin(np.abs(dl - float(d_cur))))
                    r_at_cur = float(rl[j_nearest])
            r_cur_txt = f"{r_at_cur:.8f}" if np.isfinite(r_at_cur) else "n/a"
            self.logger.info(
                "GUI RMSE(d) regular grid | live | pts=%d | base %d/%d | extra_done=%d | current_d_nm=%s | rmse_at_nearest_curve_pt=%s",
                int(n_done),
                int(n_base_done),
                int(n_tot),
                int(n_extra_done),
                (f"{float(d_cur):.6f}" if np.isfinite(d_cur) else "n/a"),
                r_cur_txt,
            )

    def _build_manual_corridor_payload(
        self,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo_nm: float,
        d_hi_nm: float,
    ) -> dict[str, Any] | None:

        d_vals = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)

        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)

        if d_vals.size == 0 or n_curves.ndim != 2 or k_curves.ndim != 2:
            return None

        if n_curves.shape[0] != d_vals.size or k_curves.shape[0] != d_vals.size:
            return None

        if n_curves.shape[1] == 0 or k_curves.shape[1] != n_curves.shape[1]:
            return None

        d_lo = float(min(d_lo_nm, d_hi_nm))

        d_hi = float(max(d_lo_nm, d_hi_nm))

        sel = np.isfinite(d_vals) & (d_vals >= d_lo - 1e-12) & (d_vals <= d_hi + 1e-12)

        if not np.any(sel):
            i_near = int(np.argmin(np.abs(d_vals - 0.5 * (d_lo + d_hi))))

            sel = np.zeros_like(d_vals, dtype=bool)

            sel[i_near] = True

        n_pick = np.asarray(n_curves[sel, :], dtype=np.float64)

        k_pick = np.asarray(k_curves[sel, :], dtype=np.float64)

        if n_pick.ndim != 2 or k_pick.ndim != 2 or n_pick.shape[0] == 0:
            return None

        n_lo = np.nanmin(n_pick, axis=0)

        n_hi = np.nanmax(n_pick, axis=0)

        k_lo = np.nanmin(k_pick, axis=0)

        k_hi = np.nanmax(k_pick, axis=0)

        ref_n = np.asarray(source.get("corridor_reference_n_lam", display.get("n_lam", [])), dtype=np.float64).ravel()

        ref_k = np.asarray(source.get("corridor_reference_k_lam", display.get("k_lam", [])), dtype=np.float64).ravel()

        if ref_n.size == n_lo.size and ref_k.size == k_lo.size:
            n_lo, n_hi, k_lo, k_hi = _expand_corridor_envelope_with_reported_nk(
                n_lo,
                n_hi,
                k_lo,
                k_hi,
                ref_n,
                ref_k,
            )
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(ref_k, dtype=np.float64),
                min_half_width=1e-4,
            )
        else:
            k_ref_eff = 0.5 * (np.asarray(k_lo, dtype=np.float64) + np.asarray(k_hi, dtype=np.float64))
            k_lo, k_hi, k_min_changed = enforce_min_k_corridor_half_width(
                np.asarray(k_lo, dtype=np.float64),
                np.asarray(k_hi, dtype=np.float64),
                np.asarray(k_ref_eff, dtype=np.float64),
                min_half_width=1e-4,
            )

        d_sel = np.asarray(d_vals[sel], dtype=np.float64)

        if int(k_min_changed) > 0 and self.logger:
            self.logger.info(
                "GUI corridor payload | k-min-width enforced | half_width=1.0e-4 | adjusted_points=%d",
                int(k_min_changed),
            )

        return {
            "profile_d_enabled": True,
            "corridor_n_lo": np.asarray(n_lo, dtype=np.float64),
            "corridor_n_hi": np.asarray(n_hi, dtype=np.float64),
            "corridor_k_lo": np.asarray(k_lo, dtype=np.float64),
            "corridor_k_hi": np.asarray(k_hi, dtype=np.float64),
            "corridor_k_min_half_width": float(1e-4),
            "corridor_k_min_half_width_enforced_points": int(k_min_changed),
            "corridor_reference_n_lam": np.asarray(ref_n, dtype=np.float64),
            "corridor_reference_k_lam": np.asarray(ref_k, dtype=np.float64),
            "manual_corridor_active": True,
            "manual_corridor_interval_nm": (float(d_lo), float(d_hi)),
            "manual_corridor_selected_d_range_nm": (float(np.nanmin(d_sel)), float(np.nanmax(d_sel))),
            "manual_corridor_selected_count": int(d_sel.size),
        }

    def _apply_corridor_payload_from_interval(
        self,
        *,
        source: dict[str, Any],
        display: dict[str, Any],
        d_lo: float,
        d_hi: float,
        status_prefix: str,
    ) -> bool:

        payload = self._build_manual_corridor_payload(source, display, d_lo, d_hi)

        if payload is None:
            if self.logger:
                self.logger.warning(
                    "GUI corridor regenerate | failed payload build | requested_interval=[%.6f, %.6f] nm",
                    float(min(d_lo, d_hi)),
                    float(max(d_lo, d_hi)),
                )

            return False

        updated = dict(display)

        for k, v in source.items():
            if k.startswith("profile_d_") and k not in updated:
                updated[k] = v

        updated.update(payload)

        self._corridor_rmse_manual_active = True

        self._corridor_rmse_manual_lo = float(payload["manual_corridor_interval_nm"][0])

        self._corridor_rmse_manual_hi = float(payload["manual_corridor_interval_nm"][1])

        self._last_result = updated

        self._plot_result(updated, plot_source="corridor_rmse_manual")

        self._refresh_data_table()

        self._update_corridor_rmse_state_bar(updated)

        self.lbl_status.setText(
            f"{status_prefix} [{self._corridor_rmse_manual_lo:.2f}, {self._corridor_rmse_manual_hi:.2f}] nm"
        )

        if self.logger:
            self.logger.info(
                "GUI corridor regenerated | status_prefix=%s | requested_interval=[%.6f, %.6f] nm | selected_points=%d | sampled_selected_range=[%.6f, %.6f] nm",
                str(status_prefix),
                float(self._corridor_rmse_manual_lo),
                float(self._corridor_rmse_manual_hi),
                int(payload.get("manual_corridor_selected_count", 0)),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[0]),
                float(payload.get("manual_corridor_selected_d_range_nm", (float("nan"), float("nan")))[1]),
            )

        return True

    def _generate_corridor_from_partial_grid(self) -> None:
        """Generate n/k corridor from a centered partial RMSE(d) interval."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        r_s = r_s[m]
        if d_s.size == 0 or r_s.size != d_s.size:
            if self.logger:
                self.logger.warning("GUI generate corridor(partial-grid) | aborted: empty finite RMSE(d) grid")
            QMessageBox.information(
                self,
                "Generate corridor (partial grid)",
                "No valid finite RMSE(d) points are available.",
            )
            return

        d_best = float(d_s[int(np.argmin(r_s))])
        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))
        if not np.isfinite(d_center):
            d_center = d_best

        half = (
            float(self.sp_corridor_partial_delta_nm.value()) if hasattr(self, "sp_corridor_partial_delta_nm") else 2.0
        )
        if (not np.isfinite(half)) or half <= 0.0:
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Invalid Corridor Deltad: please set a positive finite value.",
            )
            return

        d_lo = float(d_center - half)
        d_hi = float(d_center + half)
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))
        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Partial interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(partial-grid) | request | center=%.6f nm | half=%.6f nm | clipped_interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from partial RMSE(d) grid on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(partial-grid) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (partial grid)",
                "Unable to generate n/k corridor from the selected partial grid interval.",
            )

    def _generate_corridor_auto_smart_from_current_grid(self) -> None:
        """Auto-compute and apply smart corridor interval from current RMSE(d) grid."""
        source = self._corridor_profile_source_result()
        display = self._last_result
        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(auto-smart) | aborted: no RMSE(d) grid in memory")
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No RMSE(d) grid is available yet.",
            )
            return

        d_all = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        # Guard against partial live updates while worker is still filling n/k curves.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_all.size
            and k_curves.shape[0] == d_all.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_all.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        # Ensure smart/robust interval state is up-to-date with current grid.
        try:
            self._refresh_corridor_rmse_robust_view()
        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.debug("Auto-smart corridor: robust refresh failed", exc_info=True)

        d_lo = float("nan")
        d_hi = float("nan")
        interval_source = "none"

        smart_int = getattr(self, "_corridor_rmse_smart_interval", None)
        if (
            isinstance(smart_int, (tuple, list))
            and len(smart_int) >= 2
            and np.isfinite(float(smart_int[0]))
            and np.isfinite(float(smart_int[1]))
        ):
            d_lo = float(min(float(smart_int[0]), float(smart_int[1])))
            d_hi = float(max(float(smart_int[0]), float(smart_int[1])))
            interval_source = "smart_code_interval"
        elif bool(getattr(self, "_corridor_rmse_robust_ok", False)):
            d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))
            d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))
            if np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb) and d_hi_rb > d_lo_rb:
                d_lo = float(d_lo_rb)
                d_hi = float(d_hi_rb)
                interval_source = "robust_parabolic_interval"

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()
        r_s = np.asarray(source.get("profile_d_rmse_values", []), dtype=np.float64).ravel()
        m = np.isfinite(d_s) & np.isfinite(r_s)
        d_s = d_s[m]
        if d_s.size == 0:
            QMessageBox.information(
                self,
                "Generate corridor (auto smart)",
                "No valid finite RMSE(d) points are available.",
            )
            return
        d_min = float(np.nanmin(d_s))
        d_max = float(np.nanmax(d_s))

        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval unavailable for current grid (no smart/robust interval found).",
            )
            return

        d_lo = float(max(d_lo, d_min))
        d_hi = float(min(d_hi, d_max))
        if not (np.isfinite(d_lo) and np.isfinite(d_hi) and d_hi > d_lo):
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Auto smart interval is outside available RMSE(d) points.",
            )
            return

        if self.logger:
            self.logger.info(
                "GUI generate corridor(auto-smart) | request | source=%s | interval=[%.6f, %.6f] nm | grid_range=[%.6f, %.6f] nm",
                str(interval_source),
                float(d_lo),
                float(d_hi),
                float(d_min),
                float(d_max),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix=f"auto smart corridor generated ({interval_source}) on",
        )
        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(auto-smart) | failed | source=%s | interval=[%.6f, %.6f] nm",
                    str(interval_source),
                    float(d_lo),
                    float(d_hi),
                )
            QMessageBox.warning(
                self,
                "Generate corridor (auto smart)",
                "Unable to generate n/k corridor from auto smart interval.",
            )
            return

        # Keep interval highlighted explicitly as active manual interval (red lines)
        # in addition to smart/robust guide lines already shown on RMSE(d) chart.
        try:
            self._refresh_corridor_rmse_robust_view()
        except (ValueError, TypeError, RuntimeError, AttributeError):
            logger.debug("Auto-smart corridor: post-apply robust refresh failed", exc_info=True)

    def _apply_manual_corridor_selection(self) -> None:

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: no corridor profile source/display")

            QMessageBox.information(self, "Generate corridor", "No corridor profile is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if d_s.size == 0 or i_best < 0 or i_best >= int(d_s.size):
            if self.logger:
                self.logger.warning("GUI generate corridor(manual) | aborted: invalid RMSE(d) profile or best index")

            QMessageBox.information(self, "Generate corridor", "No valid RMSE(d) profile is available.")

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        half = self._corridor_manual_half_width_nm()

        d_lo = float(d_center - half)

        d_hi = float(d_center + half)

        if self.logger:
            self.logger.info(
                "GUI generate corridor(manual) | request | center=%.6f nm | half=%.6f nm | interval=[%.6f, %.6f] nm",
                float(d_center),
                float(half),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="Manual corridor regenerated on",
        )

        if not ok:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(manual) | failed for interval=[%.6f, %.6f] nm",
                    float(d_lo),
                    float(d_hi),
                )

            QMessageBox.warning(self, "Generate corridor", "Unable to rebuild a manual corridor from this interval.")

    def _refresh_corridor_table(self, result: dict) -> None:
        """Populates the detailed data corridor table with smart interpolation."""
        if not hasattr(self, "table_corridor"):
            return

        t = self.table_corridor
        t.setRowCount(0)

        lam_src = result.get("lam_nm")
        n_src = result.get("n_lam")
        k_src = result.get("k_lam")

        if lam_src is None or n_src is None or k_src is None:
            self.btn_copy_corridor.setEnabled(False)
            self.btn_export_corridor.setEnabled(False)
            return

        lam = np.asarray(lam_src, dtype=np.float64).ravel()
        n_nom = np.asarray(n_src, dtype=np.float64).ravel()
        k_nom = np.asarray(k_src, dtype=np.float64).ravel()

        if not lam.size:
            return

        # Smart grid generation
        lo, hi = float(np.nanmin(lam)), float(np.nanmax(lam))
        lam_g = self._lam_piecewise_report_grid_nm(lo, hi)
        if not lam_g.size:
            return

        # Nominal interpolation
        n_g = np.interp(lam_g, lam, n_nom, left=np.nan, right=np.nan)
        k_g = np.interp(lam_g, lam, k_nom, left=np.nan, right=np.nan)

        # Corridor interpolation
        n_lo_g = np.full_like(lam_g, np.nan)
        n_hi_g = np.full_like(lam_g, np.nan)
        k_lo_g = np.full_like(lam_g, np.nan)
        k_hi_g = np.full_like(lam_g, np.nan)

        if bool(result.get("profile_d_enabled", False)) or bool(result.get("manual_corridor_active", False)):
            cn_lo = np.asarray(result.get("corridor_n_lo", []), dtype=np.float64).ravel()
            cn_hi = np.asarray(result.get("corridor_n_hi", []), dtype=np.float64).ravel()
            ck_lo = np.asarray(result.get("corridor_k_lo", []), dtype=np.float64).ravel()
            ck_hi = np.asarray(result.get("corridor_k_hi", []), dtype=np.float64).ravel()

            if cn_lo.size == lam.size:
                n_lo_g = np.interp(lam_g, lam, cn_lo, left=np.nan, right=np.nan)
                n_hi_g = np.interp(lam_g, lam, cn_hi, left=np.nan, right=np.nan)
                k_lo_g = np.interp(lam_g, lam, ck_lo, left=np.nan, right=np.nan)
                k_hi_g = np.interp(lam_g, lam, ck_hi, left=np.nan, right=np.nan)

                # ENFORCE CONSISTENCY with Plots
                k_lo_g, k_hi_g, _ = enforce_min_k_corridor_half_width(k_lo_g, k_hi_g, k_g, min_half_width=1e-4)

        # Center of corridor (midpoint)
        n_ctr_g = 0.5 * (n_lo_g + n_hi_g)
        k_ctr_g = 0.5 * (k_lo_g + k_hi_g)

        m = int(lam_g.size)
        t.setRowCount(m)

        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt

        def _cell(val: float, fmt: str = ".4f") -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):{fmt}}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        def _cell_sci(val: float) -> QTableWidgetItem:
            if not np.isfinite(val):
                return QTableWidgetItem("-")
            item = QTableWidgetItem(f"{float(val):.2e}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._apply_cell_style(item, val)
            return item

        for i in range(m):
            t.setItem(i, 0, _cell(float(lam_g[i]), ".1f"))
            t.setItem(i, 1, _cell(float(n_g[i])))
            t.setItem(i, 2, _cell_sci(float(k_g[i])))
            t.setItem(i, 3, _cell(float(n_ctr_g[i])))
            t.setItem(i, 4, _cell_sci(float(k_ctr_g[i])))
            t.setItem(i, 5, _cell(float(n_lo_g[i])))
            t.setItem(i, 6, _cell(float(n_hi_g[i])))
            t.setItem(i, 7, _cell_sci(float(k_lo_g[i])))
            t.setItem(i, 8, _cell_sci(float(k_hi_g[i])))

        self.btn_copy_corridor.setEnabled(True)
        self.btn_export_corridor.setEnabled(True)

class _SettingsMixin:
    """Mixin containing defaults reset, loading and uncertainty settings methods."""

    def _apply_default_square_plot_split(self) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            return

        total = int(max(0, sizes[0]) + max(0, sizes[1]))
        if total <= 0:
            total = int(max(0, spl.width()))
        if total <= 0:
            return

        panel_h = int(max(0, spl.height()))
        if panel_h <= 0:
            panel_h = int(round(0.58 * float(total)))

        # Keep the right panel width near the visible height so the active plot
        # starts close to a square aspect by default.
        target_right = int(round(0.88 * float(panel_h)))
        target_right = int(
            min(
                max(target_right, int(round(0.20 * float(total)))),
                int(round(0.95 * float(total))),
            )
        )
        target_left = int(max(1, total - target_right))

        self._main_splitter_clamp_guard = True
        try:
            spl.setSizes([target_left, target_right])
        finally:
            self._main_splitter_clamp_guard = False

        self._enforce_main_splitter_ratio_bounds(persist=False)

    def _on_main_splitter_moved(self, *_args) -> None:

        self._enforce_main_splitter_ratio_bounds(persist=True)

    def _enforce_main_splitter_ratio_bounds(self, *, persist: bool = True) -> None:

        spl = getattr(self, "main_split", None)
        if spl is None:
            if persist:
                self._persist_splitter_states()
            return

        if bool(getattr(self, "_main_splitter_clamp_guard", False)):
            if persist:
                self._persist_splitter_states()
            return

        sizes = spl.sizes()
        if not isinstance(sizes, list) or len(sizes) < 2:
            if persist:
                self._persist_splitter_states()
            return

        left = int(max(0, sizes[0]))
        right = int(max(0, sizes[1]))
        total = int(left + right)
        if total <= 0:
            if persist:
                self._persist_splitter_states()
            return

        min_left = max(1, int(round(0.05 * total)))
        max_left = max(min_left, int(round(0.95 * total)))
        clamped_left = int(min(max(left, min_left), max_left))

        if clamped_left != left:
            self._main_splitter_clamp_guard = True
            try:
                spl.moveSplitter(int(clamped_left), 0)
            finally:
                self._main_splitter_clamp_guard = False

        if persist:
            self._persist_splitter_states()

    def _restore_splitter_states(self) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            v_rev_raw = s.value(_QS_MAIN_SPLITTER_LAYOUT_REV, 0)
            v_rev = int(v_rev_raw or 0)
        except (TypeError, ValueError):
            v_rev = 0

        try:
            if hasattr(self, "main_split") and v_rev == int(_MAIN_SPLITTER_LAYOUT_REV):
                v_main = s.value(_QS_MAIN_SPLITTER_STATE)
                if v_main is not None:
                    self.main_split.restoreState(v_main)
                else:
                    QTimer.singleShot(0, self._apply_default_square_plot_split)
                self._enforce_main_splitter_ratio_bounds(persist=False)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        try:
            v_right = s.value(_QS_RIGHT_SPLITTER_STATE)
            if v_right is not None and hasattr(self, "info_split"):
                self.info_split.restoreState(v_right)
        except (AttributeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _persist_splitter_states(self, *_args) -> None:

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        if hasattr(self, "main_split"):
            s.setValue(_QS_MAIN_SPLITTER_STATE, self.main_split.saveState())
            s.setValue(_QS_MAIN_SPLITTER_LAYOUT_REV, int(_MAIN_SPLITTER_LAYOUT_REV))

        if hasattr(self, "info_split"):
            s.setValue(_QS_RIGHT_SPLITTER_STATE, self.info_split.saveState())

    def _maybe_apply_uncertainty_defaults_migrated(self) -> None:
        """Applies automatic uncertainty defaults once (migration / new install)."""

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        try:
            rev = int(s.value(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, 0) or 0)

        except (TypeError, ValueError):
            rev = 0

        if rev < _UNCERTAINTY_DEFAULTS_REV:
            if rev < 5:
                self._apply_recommended_uncertainty_and_perf_defaults()

                self._apply_sio2_default_fit_parameters()

                if hasattr(self, "chk_trel"):
                    self.chk_trel.setChecked(True)

            if rev < 9 and hasattr(self, "cb_corr_mode"):
                self.cb_corr_mode.blockSignals(True)

                try:
                    iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                    if iq >= 0:
                        self.cb_corr_mode.setCurrentIndex(int(iq))

                finally:
                    self.cb_corr_mode.blockSignals(False)

                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._on_corr_mode_changed()

            if rev < 11 and hasattr(self, "cb_corr_mode"):
                self._apply_corridor_preset_auto_robust()

            if rev < 12:
                if hasattr(self, "sp_corr_rmse_delta"):
                    self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

                self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

                if hasattr(self, "_on_corr_mode_changed"):
                    self._on_corr_mode_changed()

                if hasattr(self, "_refresh_corridors_gui_state_labels"):
                    self._refresh_corridors_gui_state_labels()

            s.setValue(_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV, int(_UNCERTAINTY_DEFAULTS_REV))

    def _apply_recommended_uncertainty_and_perf_defaults(self) -> None:
        """Speed-oriented defaults: Fast profile, n/k corridors enabled (accelerated refits); optional bootstrap / reg. scan."""

        if not hasattr(self, "cb_profilee"):
            return

        self.cb_profilee.blockSignals(True)

        try:
            iq = self.cb_profilee.findData("fast")

            if iq >= 0:
                self.cb_profilee.setCurrentIndex(int(iq))

        finally:
            self.cb_profilee.blockSignals(False)

        self._on_profilee_changed()

        if hasattr(self, "chk_corridor_d"):
            self.chk_corridor_d.setChecked(True)

        if hasattr(self, "cb_corr_mode"):
            ia = self.cb_corr_mode.findData("abs_delta_adaptive")

            if ia >= 0:
                self.cb_corr_mode.setCurrentIndex(int(ia))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "chk_corr_sigma_hetero"):
            self.chk_corr_sigma_hetero.setChecked(False)

        if hasattr(self, "sp_corr_hetero_scale"):
            self.sp_corr_hetero_scale.setValue(1.0)

        if hasattr(self, "sp_corr_sigma"):
            self.sp_corr_sigma.setValue(0.0)

        if hasattr(self, "sp_corr_starts"):
            self.sp_corr_starts.setValue(1)

        if hasattr(self, "chk_corr_reg_sens"):
            self.chk_corr_reg_sens.setChecked(False)

        if hasattr(self, "chk_corr_boot"):
            self.chk_corr_boot.setChecked(False)

        if hasattr(self, "sp_corr_boot_n"):
            self.sp_corr_boot_n.setValue(40)

        self._refresh_corridors_gui_state_labels()

        if hasattr(self, "sp_corr_boot_p"):
            self.sp_corr_boot_p.setValue(0.95)

        if hasattr(self, "chk_corr_boot_refit"):
            self.chk_corr_boot_refit.setChecked(False)

        if hasattr(self, "sp_corr_boot_maxfun"):
            self.sp_corr_boot_maxfun.setValue(4000)

        if hasattr(self, "sp_corr_boot_workers"):
            self.sp_corr_boot_workers.setValue(1)

        if hasattr(self, "sp_corr_span"):
            self.sp_corr_span.setValue(15.0)

        if hasattr(self, "sp_corr_prof_maxfun"):
            self.sp_corr_prof_maxfun.setValue(2500)

        if hasattr(self, "cb_corr_boot_mode"):
            ip = self.cb_corr_boot_mode.findData("parametric")

            if ip >= 0:
                self.cb_corr_boot_mode.setCurrentIndex(int(ip))

        if hasattr(self, "cb_corr_mode"):
            self._apply_corridor_preset_auto_robust()

    def reset_to_defaults(self) -> None:
        """Reinitialisation complete (bouton Clear / Reset CERTUS)."""

        from certus_reset_framework import reset_app_to_defaults

        reset_app_to_defaults(self)

    def _on_load(self, path: str | None = None) -> None:

        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Spectrum",
                self._spectrum_open_dialog_start_path(),
                "Data (*.csv *.xlsx *.xls);;All (*.*)",
            )

        if not path:
            return

        try:
            raw = read_data_file_robust(path)

            self.df = normalize_spectrum_dataframe(raw)

            if self.df is None or "lambda" not in self.df.columns:
                raise ValueError("Invalid wavelength or spectrum column after normalization.")

            self._persist_last_spectrum_path(path)

            self.lbl_file.setText(path)

            if hasattr(self, "tabs_main"):
                self.tabs_main.setCurrentIndex(0)

            self._sync_rmse_lambda_bounds_from_file()

            self._plot_data_raw()

            self.lbl_status.setText(f"Loaded: {len(self.df)} points")

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                lam = np.asarray(self.df.get("lambda", []), dtype=np.float64).ravel()

                lam_f = lam[np.isfinite(lam)]

                lmin = float(np.min(lam_f)) if lam_f.size else float("nan")

                lmax = float(np.max(lam_f)) if lam_f.size else float("nan")

                cols = [str(c) for c in self.df.columns]

                summary = build_summary_plain_text(
                    "CERTUS INDEX SPLINE - Load Summary",
                    [
                        f"File: {Path(path).resolve(strict=False)}",
                        "",
                        "General",
                        (f"Rows: {int(len(self.df))}", int(len(self.df)) <= 0),
                        "",
                        "Data",
                        f"Columns: {', '.join(cols)}",
                        (
                            f"Wavelength range: [{lmin:.1f}, {lmax:.1f}] nm",
                            not (np.isfinite(lmin) and np.isfinite(lmax) and lmax > lmin),
                        ),
                        "",
                        "Compatibility checks",
                        (
                            f"Transmission column present: {'yes' if any(c.lower().startswith('t') for c in cols) else 'no'}",
                            not any(c.lower().startswith("t") for c in cols),
                        ),
                    ],
                )

                show_load_summary_dialog(self, "INDEX SPLINE Load Summary", summary)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            QMessageBox.critical(self, "Loading", str(e))

            logger.exception("load")

    def _update_rmse_fit_region_overlay(self) -> None:

        self._remove_rmse_fit_region_overlay()

        if not getattr(self, "_rmse_fit_lambda_enabled", False):
            return

        span = self._spectrum_plot_lambda_span_nm()

        if span is None:
            return

        lam_file_lo, lam_file_hi = span

        if not (np.isfinite(lam_file_lo) and np.isfinite(lam_file_hi)):
            return

        if lam_file_lo > lam_file_hi:
            lam_file_lo, lam_file_hi = lam_file_hi, lam_file_lo

        wlo = float(self._rmse_fit_lambda_lo)

        whi = float(self._rmse_fit_lambda_hi)

        if not (np.isfinite(wlo) and np.isfinite(whi)):
            return

        lam_win_lo, lam_win_hi = min(wlo, whi), max(wlo, whi)

        def _x_span_lam(la: float, lb: float) -> tuple[float, float] | None:

            if not (np.isfinite(la) and np.isfinite(lb)):
                return None

            if la > lb:
                la, lb = lb, la

            if lb - la <= 0.0:
                return None

            try:
                xv, _ = self._transform_spectrum_x(np.array([la, lb], dtype=np.float64))

            except (TypeError, ValueError, RuntimeError):
                return None

            return float(np.min(xv)), float(np.max(xv))

        eps_lam = max(1e-6, 1e-9 * max(abs(lam_file_hi), 1.0))

        eps_x = max(1e-12, 1e-15 * max(abs(lam_file_lo), abs(lam_file_hi), 1.0))

        def _add_region(xa: float, xb: float, *, brush, z: float) -> None:

            lo_x, hi_x = (xa, xb) if xa <= xb else (xb, xa)

            if hi_x - lo_x <= eps_x:
                return

            reg = pg.LinearRegionItem(values=(lo_x, hi_x), movable=False, brush=brush)

            reg.setZValue(z)

            self.plot_T.addItem(reg)

            self._rmse_fit_overlay_items.append(reg)

        gray_brush = pg.mkBrush(120, 120, 120, 85)

        # Excludes lambda < window (within file envelope) - correct if sigma/sigma^2 (nonlinear in lambda on axis)

        if lam_win_lo > lam_file_lo + eps_lam:
            la, lb = lam_file_lo, min(lam_file_hi, lam_win_lo)

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        # Exclude lambda > window

        if lam_win_hi < lam_file_hi - eps_lam:
            la, lb = max(lam_file_lo, lam_win_hi), lam_file_hi

            if lb - la > eps_lam:
                xs = _x_span_lam(la, lb)

                if xs is not None:
                    _add_region(xs[0], xs[1], brush=gray_brush, z=-8.0)

        x_active = _x_span_lam(lam_win_lo, lam_win_hi)

        if x_active is not None:
            xa, xb = x_active

            if xb - xa > eps_x:
                reg_active = pg.LinearRegionItem(
                    values=(xa, xb),
                    movable=False,
                    brush=pg.mkBrush(0, 120, 215, 40),
                )

                reg_active.setZValue(-5.0)

                self.plot_T.addItem(reg_active)

                self._rmse_fit_overlay_items.append(reg_active)

    def _on_rmse_fit_window_dialog(self) -> None:

        dlg = QDialog(self)

        dlg.setWindowTitle("Spectral RMSE Window")

        lay = QVBoxLayout(dlg)

        chk = QCheckBox("Limit optimization MSE/RMSE to a lambda band (nm)")

        chk.setChecked(self._rmse_fit_lambda_enabled)

        chk.setToolTip(
            "If checked: only experimental points in [lambda_min, lambda_max] enter the spectral loss. "
            "Plots always use the full loaded file."
        )

        lay.addWidget(chk)

        g = QGridLayout()

        lb_lo = QLabel("lambda_min (nm)")

        lb_hi = QLabel("lambda_max (nm)")

        sp_lo = QDoubleSpinBox()

        sp_hi = QDoubleSpinBox()

        for sp in (sp_lo, sp_hi):
            sp.setRange(200.0, 20000.0)

            sp.setDecimals(4)

            sp.setSingleStep(1.0)

        sp_lo.setValue(float(self._rmse_fit_lambda_lo))

        sp_hi.setValue(float(self._rmse_fit_lambda_hi))

        sp_lo.setToolTip("Lower bound (nm) of the RMSE band.")

        sp_hi.setToolTip("Upper bound (nm) of the RMSE band.")

        g.addWidget(lb_lo, 0, 0)

        g.addWidget(sp_lo, 0, 1)

        g.addWidget(lb_hi, 1, 0)

        g.addWidget(sp_hi, 1, 1)

        lay.addLayout(g)

        btn_reset = QPushButton("Reset")

        btn_reset.setToolTip("Reset lambda_min / lambda_max to [min file, max file] of the loaded spectrum.")

        lay.addWidget(btn_reset)

        def _apply_enable(en: bool) -> None:

            sp_lo.setEnabled(en)

            sp_hi.setEnabled(en)

            btn_reset.setEnabled(en)

        def _do_reset() -> None:

            sp_lo.setValue(float(self._rmse_fit_lambda_lo_default))

            sp_hi.setValue(float(self._rmse_fit_lambda_hi_default))

        chk.toggled.connect(_apply_enable)

        _apply_enable(chk.isChecked())

        btn_reset.clicked.connect(_do_reset)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._rmse_fit_lambda_enabled = chk.isChecked()

        self._rmse_fit_lambda_lo = float(sp_lo.value())

        self._rmse_fit_lambda_hi = float(sp_hi.value())

        if self._last_result is not None:
            self._plot_result(self._last_result, plot_source="fenetre_rmse_fit_lambda")

        elif self.df is not None:
            self._plot_data_raw()

        else:
            self._update_rmse_fit_region_overlay()

    def _restore_spectrum_fit_settings(self) -> None:
        """Reads step 3 from QSettings (T, T/Tsub ratio, R, wT, wR)."""

        if not hasattr(self, "chk_t"):
            return

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        widgets = (
            self.chk_t,
            self.chk_trel,
            self.chk_r,
            self.w_t,
            self.w_r,
        )

        for w in widgets:
            w.blockSignals(True)

        try:
            vt = s.value(_QS_SPECTRUM_FIT_T)

            if vt is not None:
                self.chk_t.setChecked(bool(vt))

            vrel = s.value(_QS_SPECTRUM_FIT_TREL)

            if vrel is not None:
                self.chk_trel.setChecked(bool(vrel))

            vr = s.value(_QS_SPECTRUM_FIT_R)

            if vr is not None:
                self.chk_r.setChecked(bool(vr))

            wtv = s.value(_QS_SPECTRUM_WT)

            if wtv is not None:
                self.w_t.setValue(float(wtv))

            wrv = s.value(_QS_SPECTRUM_WR)

            if wrv is not None:
                self.w_r.setValue(float(wrv))

        finally:
            for w in widgets:
                w.blockSignals(False)

    def _open_advanced_settings_dialog(self) -> None:

        lay_page = getattr(self, "_box4_full_adv_layout", None)

        if not hasattr(self, "_w_full_adv") or lay_page is None:
            return

        dlg = QDialog(self)

        dlg.setWindowTitle("Advanced settings - INDEX-SPLINE")

        dlg.resize(560, 620)

        outer = QVBoxLayout(dlg)

        chk = QCheckBox("Simplified Basic panel (recommended): hide advanced budgets and uncertainty details")

        chk.setChecked(bool(getattr(self, "_simple_auto_uncertainty", True)))

        chk.setToolTip(
            "Unchecked: after OK, controls stay visible in step 4. "
            "Checked: summary only in the panel; settings remain available here."
        )

        outer.addWidget(chk)

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        host = QWidget()

        host_lay = QVBoxLayout(host)

        host_lay.setContentsMargins(0, 0, 0, 0)

        lay_page.removeWidget(self._w_full_adv)

        host_lay.addWidget(self._w_full_adv)

        scroll.setWidget(host)

        outer.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        bb.accepted.connect(dlg.accept)

        bb.rejected.connect(dlg.reject)

        outer.addWidget(bb)

        code = dlg.exec()

        host_lay.removeWidget(self._w_full_adv)

        lay_page.addWidget(self._w_full_adv)

        self._w_full_adv.show()

        if code == QDialog.DialogCode.Accepted:
            self._simple_auto_uncertainty = chk.isChecked()

            self._persist_simple_auto_uncertainty_pref()

        self._update_epured_visibility()

class _CorridorControlMixin:
    """Mixin containing corridor RMSE grid control, display and worker management."""

    def _start_deferred_corridor_worker(self, result: dict) -> bool:

        cfg_base = self._last_run_cfg

        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)

        if cfg_base is None:
            return False

        CertusIndexSplineApp._prepare_worker_restart(self)

        self._best_live_rmse = float("inf")

        self._best_live_result = None

        self._last_live_log_mono = 0.0

        self._live_best_detail_log_mono = 0.0

        cfg_corr = self._cfg_with_result_substrate(cfg_base, result).replace()

        setattr(cfg_corr, "gui_defer_corridor_profile_after_nl", False)
        # Manual "Corridors" action must execute profiling now, regardless of the main run checkbox state.
        setattr(cfg_corr, "corridor_profile_d_enabled", True)

        # --- Resync solver snapshot if manual dialog changed the mesh (K) ---
        _snap = result.get("gui_solver_snapshot_for_corridors")
        _snap_k = 0
        if isinstance(_snap, dict):
            _snap_sk = np.asarray(_snap.get("sigma_knots", []), dtype=np.float64).ravel()
            _snap_k = int(_snap_sk.size)
        _cur_sk = np.asarray(result.get("sigma_knots", []), dtype=np.float64).ravel()
        _cur_k = int(_cur_sk.size)
        if _cur_k >= 2 and _cur_k != _snap_k:
            fresh_snap = dict(result)
            for _key in ("x", "x_seg_spline_sigma", "n_nodes_physical", "L_nodes",
                         "sigma_knots", "d_nm", "n_lam", "k_lam", "rmse", "mse"):
                if _key in result:
                    val = result[_key]
                    if isinstance(val, np.ndarray):
                        fresh_snap[_key] = val.copy()
                    else:
                        fresh_snap[_key] = val
            result["gui_solver_snapshot_for_corridors"] = fresh_snap
            if self.logger:
                self.logger.info(
                    "Corridors: solver snapshot resynced to current mesh | K_snap=%d -> K_current=%d",
                    _snap_k, _cur_k,
                )


        self._worker = GenericWorker(
            worker_run_corridor_profile_after_nl_choice, cfg_corr, dict(result), self._stop_event
        )

        def _corr_progress(p: float | int, m: str) -> None:

            pv = int(round(float(p) * 100.0))

            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _corr_progress
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit

        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_corridor_rmse_grid_live_update)

        self._worker.signals.finished.connect(self._on_worker_done)

        self._worker.signals.error.connect(self._on_worker_err)

        self._worker.signals.finished.connect(self._cleanup_thread)

        self._worker.signals.error.connect(self._cleanup_thread)

        source_stage = str(getattr(self, "_worker_role", "main") or "main")

        self._worker_role = "corridors"

        if hasattr(self, "_stepper"):
            self._stepper.set_step(6)

        if self.logger:
            rd = result.get("d_nm")
            rd_txt = f"{float(rd):.6f}" if isinstance(rd, (int, float)) and np.isfinite(float(rd)) else "n/a"
            rr = self._rmse_from_result_dict(result)
            rr_txt = f"{rr:.8f}" if np.isfinite(rr) else "n/a"
            self.logger.info(
                "Corridors: launching deferred corridor worker | after_stage=%s | seed_d_nm=%s | seed_rmse_dict=%s",
                source_stage,
                rd_txt,
                rr_txt,
            )
            log_index_spline_d_trace(
                self.logger,
                "GUI: lancement corridor différé (_last_result seed)",
                result.get("d_nm"),
                detail=f"après_stage={source_stage} rmse_dict={rr_txt}",
            )

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self._refresh_post_optimization_option_controls()

        self._prog_ui_last = 0

        self._prog_reset_bar()

        self.lbl_status.setText("Corridors: calcul en cours...")

        self._worker.start()

        return True

    def _finish_curve_minimum_deep_worker_done(self, result: object) -> None:
        """Fin du polish profond depuis le minimum RMSE(d) : retour a l'etat post-optimisation sans lancement automatique."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not isinstance(result, dict):
            self.lbl_status.setText("Polish profond (minimum grille) : annule ou echec.")
            if self.logger:
                self.logger.warning(
                    "GUI curve-min deep refit | finished without dict (type=%s)",
                    type(result).__name__,
                )
            QMessageBox.warning(
                self,
                "Polish profond",
                "Le polish L-BFGS-B depuis le minimum de grille n'a pas renvoye de resultat valide "
                "(interruption ou echec numerique). Le nominal n'a pas ete modifie.",
            )
            self._refresh_post_optimization_option_controls()
            return
        for _rk in list(result.keys()):
            if str(_rk).startswith("profile_d"):
                del result[_rk]

        # Restore corridor and profile_d keys from the preceding corridor worker output.
        # The deep polish (L-BFGS-B on d+nodes) does not recompute corridor envelopes;
        # they were computed by the corridor worker and are stored in _last_result.
        # Safety: _display_result_prefer_best_live (called below) will NOT strip them
        # because _best_live_result is None during deep polish (no live callbacks).
        prev = self._last_result if isinstance(self._last_result, dict) else {}
        _lam_result = np.asarray(result.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_prev = np.asarray(prev.get("lam_nm", []), dtype=np.float64).ravel()
        _lam_ok = _lam_result.size > 0 and _lam_result.size == _lam_prev.size
        _n_restored = 0
        if _lam_ok:
            for _pk in list(prev.keys()):
                if (
                    str(_pk).startswith("corridor_")
                    or str(_pk).startswith("profile_d_")
                    or _pk == "profile_d_enabled"
                ) and _pk not in result:
                    val = prev[_pk]
                    result[_pk] = val.copy() if isinstance(val, np.ndarray) else val
                    _n_restored += 1
        if self.logger:
            self.logger.info(
                "GUI curve-min deep refit | corridor data restoration from _last_result | "
                "lam_ok=%s (result=%d, prev=%d) | keys_restored=%d",
                "yes" if _lam_ok else "NO",
                int(_lam_result.size),
                int(_lam_prev.size),
                int(_n_restored),
            )

        self._last_worker_result = dict(result)
        self._corridor_rmse_manual_active = False
        self._corridor_rmse_manual_lo = float("nan")
        self._corridor_rmse_manual_hi = float("nan")

        display = self._display_result_prefer_best_live(result)
        self._last_result = display

        st = CertusIndexSplineApp._format_post_optimization_status(display, result)
        status_text = "Apres minimum grille (polish profond) | " + st
        self.lbl_status.setText(status_text)

        if self.logger:
            rm_fin = float(
                display.get(
                    "rmse",
                    float(np.sqrt(max(float(display.get("mse", 0.0)), 0.0))),
                )
            )
            self.logger.info(
                "GUI curve-min deep refit | done | rmse=%.8f | d_nm=%.6f",
                rm_fin,
                float(display.get("d_nm", float("nan"))),
            )
            if np.isfinite(rm_fin):
                _log_index_spline_best_config(self.logger, display, rm_fin, title="[FIN polish min grille]")

        self._plot_result(display, plot_source="polish_grille_profond")
        self._refresh_data_table()

        _cont_after_deep = getattr(self, "_continue_corridor_auto_refine_after_deep", None)
        if callable(_cont_after_deep) and bool(_cont_after_deep()):
            return

        self._refresh_post_optimization_option_controls()
        self.lbl_status.setText(CertusIndexSplineApp._post_optimization_ready_status(status_text))
        self.export_excel(auto_export=True)

    def _finish_rmse_heal_worker_done(self, healed_list: object) -> None:
        """Merge healed points into the main result and refresh."""
        self._worker_role = "idle"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_corridor_grid_busy(False)

        if not isinstance(healed_list, list) or not healed_list:
            dr = self._last_result if isinstance(self._last_result, dict) else {}
            self._finish_corridor_rmse_d_grid_worker_done(dr)
            return

        # Get baseline from last result
        base = dict(self._last_result) if isinstance(self._last_result, dict) else {}

        d_main = list(np.asarray(base.get("profile_d_values_nm", []), dtype=np.float64).ravel())
        r_main = list(np.asarray(base.get("profile_d_rmse_values", []), dtype=np.float64).ravel())
        s_main = list(base.get("profile_d_full_results", []))

        added = 0
        for item in healed_list:
            if not isinstance(item, dict):
                continue
            dv = item.get("profile_d_val_nm")
            if dv is None:
                continue

            # Replace or add
            match = -1
            for i, d_ex in enumerate(d_main):
                if np.abs(d_ex - dv) < 1e-4:
                    match = i
                    break

            rm = float(np.sqrt(max(float(item.get("mse", 0.0)), 0.0)))
            if match >= 0:
                # Only replace if better!
                if rm < r_main[match] - 1e-15:
                    r_main[match] = rm
                    s_main[match] = item
                    added += 1
            else:
                d_main.append(dv)
                r_main.append(rm)
                s_main.append(item)
                added += 1

        if self.logger:
            self.logger.info("GUI RMSE(d) Grid Healing | Integrated %d improved/healed points", added)

        base["profile_d_values_nm"] = np.array(d_main, dtype=np.float64)
        base["profile_d_rmse_values"] = np.array(r_main, dtype=np.float64)
        base["profile_d_full_results"] = s_main
        base["profile_d_manual_grid_coverage_complete"] = True  # We healed!

        # Finally trigger the standard finalization
        self._finish_corridor_rmse_d_grid_worker_done(base)

    def _apply_corridor_preset_auto_robust(self) -> None:
        """Preset 'Auto robust corridor': local adaptive Delta, symmetry on parabola, stable parameters."""

        if hasattr(self, "cb_corr_mode"):
            self.cb_corr_mode.blockSignals(True)

            try:
                iq = self.cb_corr_mode.findData("abs_delta_adaptive")

                if iq >= 0:
                    self.cb_corr_mode.setCurrentIndex(int(iq))

            finally:
                self.cb_corr_mode.blockSignals(False)

        if hasattr(self, "sp_corr_rmse_delta"):
            self.sp_corr_rmse_delta.setValue(float(_DEFAULT_CORRIDOR_RMSE_DELTA))

        if hasattr(self, "chk_corr_scientific_nominal"):
            self.chk_corr_scientific_nominal.setChecked(True)

        if hasattr(self, "sp_corridor_rmse_win"):
            self.sp_corridor_rmse_win.setValue(4)

        if hasattr(self, "sp_corridor_rmse_delta"):
            self.sp_corridor_rmse_delta.setValue(2e-4)

        self._corridor_parabola_half_window_pts = 4

        self._corridor_symmetric_center_mode = "parabola"

        self._corridor_adaptive_rmse_ref_half_width_nm = 1.5

        self._corridor_adaptive_rmse_probe_steps_each_side = 3

        self._corridor_adaptive_rmse_noise_factor = 3.0

        self._corridor_adaptive_rmse_min = float(_DEFAULT_CORRIDOR_ADAPTIVE_RMSE_MIN)

        if hasattr(self, "_on_corr_mode_changed"):
            self._on_corr_mode_changed()

        if hasattr(self, "_refresh_corridor_rmse_robust_view"):
            try:
                self._refresh_corridor_rmse_robust_view()

            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.debug("Corridor RMSE robust refresh after preset failed", exc_info=True)

        if hasattr(self, "_refresh_corridors_gui_state_labels"):
            self._refresh_corridors_gui_state_labels()

    def _set_corridor_grid_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_corridor_rmse_grid_calc"):
            self.btn_corridor_rmse_grid_calc.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_d_step_nm"):
            self.sp_corridor_grid_d_step_nm.setEnabled(not busy)

        if hasattr(self, "sp_corridor_grid_n_points"):
            self.sp_corridor_grid_n_points.setEnabled(not busy)

        if hasattr(self, "sp_corridor_breakpoint_lookback"):
            self.sp_corridor_breakpoint_lookback.setEnabled(not busy)

        if hasattr(self, "chk_corridor_rmse_envelope_only"):
            self.chk_corridor_rmse_envelope_only.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_data"):
            self.btn_corridor_rmse_export_data.setEnabled(not busy)

        if hasattr(self, "btn_corridor_rmse_export_envelope_nk"):
            self.btn_corridor_rmse_export_envelope_nk.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "sp_corridor_partial_delta_nm"):
            self.sp_corridor_partial_delta_nm.setEnabled(not busy)

        if hasattr(self, "btn_corridor_generate_from_partial_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_from_partial_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "btn_corridor_generate_auto_smart_grid"):
            has_curve = bool(np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).size > 0)

            self.btn_corridor_generate_auto_smart_grid.setEnabled((not busy) and has_curve)

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setEnabled(bool(busy))

            if busy:
                self.pb_corridor_rmse_grid.setStyleSheet(
                    f"QProgressBar::chunk {{ background-color: {CertusTheme.PRIMARY}; }}"
                )
            else:
                self.pb_corridor_rmse_grid.setStyleSheet("")

    def _set_corridor_grid_progress_ui(
        self,
        *,
        done: int,
        total: int,
        base_done: int | None = None,
        base_total: int | None = None,
        extra_done: int | None = None,
        current_d_nm: float | None = None,
    ) -> None:

        tot = max(1, int(total))
        dn = int(max(0, min(done, tot)))
        frac = float(dn) / float(tot)

        # UX-8: Sub-progress injection
        if hasattr(self, "progress_widget"):
            self.progress_widget.update(
                iteration=self._prog_ui_last,
                max_iter=10000,
                evals=0,
                phase=f"RMSE(d) Grid: {dn}/{tot}",
                extra_info="",
                sub_iteration=dn,
                max_sub_iter=tot,
            )

        if hasattr(self, "pb_corridor_rmse_grid"):
            self.pb_corridor_rmse_grid.setValue(int(round(1000.0 * frac)))

        t0 = float(getattr(self, "_corridor_rmse_grid_live_t0", float("nan")))

        eta_txt = ""

        if np.isfinite(t0) and dn > 0:
            dt = max(0.0, time.perf_counter() - t0)

            avg = dt / float(dn)

            eta = max(0.0, float(tot - dn) * avg)

            eta_txt = f" | avg {avg:.2f}s/pt | ETA {eta:.1f}s"

        d_txt = ""

        if current_d_nm is not None and np.isfinite(float(current_d_nm)):
            d_txt = f" | d={float(current_d_nm):.3f} nm"

        if hasattr(self, "lbl_corridor_rmse_grid_progress"):
            if base_done is not None and base_total is not None:
                btot = max(1, int(base_total))
                bdn = int(max(0, min(int(base_done), btot)))
                xdn = int(max(0, int(extra_done or 0)))
                bfrac = 100.0 * float(bdn) / float(btot)
                self.lbl_corridor_rmse_grid_progress.setText(
                    f"Grid {bdn}/{btot} ({bfrac:.1f}%) + extra {xdn}{d_txt}{eta_txt}"
                )
            else:
                self.lbl_corridor_rmse_grid_progress.setText(f"Grid {dn}/{tot} ({100.0 * frac:.1f}%){d_txt}{eta_txt}")

    def _sync_corridor_manual_controls(self, d_s: np.ndarray, i_best: int) -> None:

        if (
            not hasattr(self, "sl_corridor_manual_half")
            or not hasattr(self, "btn_generate_manual_corridor")
            or d_s.size == 0
            or i_best < 0
            or i_best >= int(d_s.size)
        ):
            self._reset_corridor_manual_controls()

            return

        d_best = float(d_s[i_best])

        d_center = float(getattr(self, "_corridor_rmse_center_nm", float("nan")))

        if not np.isfinite(d_center):
            d_center = d_best

        man_active = bool(getattr(self, "_corridor_rmse_manual_active", False))
        man_lo = float(getattr(self, "_corridor_rmse_manual_lo", float("nan")))
        man_hi = float(getattr(self, "_corridor_rmse_manual_hi", float("nan")))
        has_manual_interval = man_active and np.isfinite(man_lo) and np.isfinite(man_hi) and man_hi >= man_lo
        if has_manual_interval:
            # Preserve the effective manual interval currently applied/generated,
            # instead of recomputing preview solely from the previous slider state.
            d_center = 0.5 * float(man_lo + man_hi)

        self._set_corridor_manual_bounds_labels(float(d_s[0]), d_best, float(d_s[-1]))

        max_half = self._corridor_manual_max_half_width_nm(d_s)

        scale = max(1, int(getattr(self, "_corridor_rmse_manual_slider_scale", 100) or 100))

        max_steps = max(1, int(round(max_half * scale)))

        cur_half = self._corridor_manual_half_width_nm()
        if has_manual_interval:
            cur_half = 0.5 * float(max(0.0, man_hi - man_lo))

        if not np.isfinite(cur_half) or cur_half <= 0.0:
            if np.isfinite(self._corridor_rmse_robust_lo) and np.isfinite(self._corridor_rmse_robust_hi):
                cur_half = 0.5 * max(0.0, float(self._corridor_rmse_robust_hi - self._corridor_rmse_robust_lo))

            elif d_s.size >= 2:
                cur_half = max(float(np.nanmedian(np.abs(np.diff(d_s)))), 0.0)

            else:
                cur_half = 0.0

        cur_half = float(min(max(cur_half, 0.0), max_half))

        self.sl_corridor_manual_half.blockSignals(True)

        self.sl_corridor_manual_half.setRange(0, max_steps)

        self.sl_corridor_manual_half.setTickInterval(max(1, max_steps // 8))

        self.sl_corridor_manual_half.setValue(int(round(cur_half * scale)))

        self.sl_corridor_manual_half.setEnabled(max_steps > 0)

        self.sl_corridor_manual_half.blockSignals(False)

        self.btn_generate_manual_corridor.setEnabled(True)

        if hasattr(self, "btn_corridor_manual_robust"):
            self.btn_corridor_manual_robust.setEnabled(bool(self._corridor_rmse_robust_ok))

        self._set_corridor_manual_interval_preview(d_center, cur_half)

    def _generate_corridor_from_current_grid(self) -> None:
        """Generate n/k corridor from all currently available RMSE(d) grid points."""

        source = self._corridor_profile_source_result()

        display = self._last_result

        if not isinstance(source, dict) or not isinstance(display, dict):
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: no RMSE(d) grid in memory")

            QMessageBox.information(self, "Generate corridor (grid)", "No RMSE(d) grid is available yet.")

            return

        d_s = np.asarray(source.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        if d_s.size == 0:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | aborted: RMSE(d) grid empty")

            QMessageBox.information(self, "Generate corridor (grid)", "No valid RMSE(d) points are available.")

            return

        # Guard against partial live updates: d-values can be present while
        # n/k profile curves are still being filled by the worker.
        n_curves = np.asarray(source.get("profile_d_n_curves", []), dtype=np.float64)
        k_curves = np.asarray(source.get("profile_d_k_curves", []), dtype=np.float64)
        curves_ready = (
            n_curves.ndim == 2
            and k_curves.ndim == 2
            and n_curves.shape[0] == d_s.size
            and k_curves.shape[0] == d_s.size
            and n_curves.shape[1] > 0
            and k_curves.shape[1] == n_curves.shape[1]
        )
        if not curves_ready:
            if self.logger:
                self.logger.warning(
                    "GUI generate corridor(grid) | aborted: profile curves not ready/coherent | d_points=%d | n_shape=%s | k_shape=%s",
                    int(d_s.size),
                    tuple(int(v) for v in n_curves.shape) if n_curves.ndim >= 1 else (),
                    tuple(int(v) for v in k_curves.shape) if k_curves.ndim >= 1 else (),
                )
            QMessageBox.information(
                self,
                "Generate corridor (grid)",
                "RMSE(d) grid is still updating. Please retry in a moment.",
            )
            return

        d_lo = float(np.nanmin(d_s))

        d_hi = float(np.nanmax(d_s))

        if self.logger:
            self.logger.info(
                "GUI generate corridor(grid) | request | grid_points=%d | d_range=[%.6f, %.6f] nm",
                int(d_s.size),
                float(d_lo),
                float(d_hi),
            )

        ok = self._apply_corridor_payload_from_interval(
            source=source,
            display=display,
            d_lo=d_lo,
            d_hi=d_hi,
            status_prefix="n/k corridor generated from RMSE(d) grid on",
        )

        if not ok:
            if self.logger:
                self.logger.warning("GUI generate corridor(grid) | failed for current RMSE(d) grid")

            QMessageBox.warning(
                self,
                "Generate corridor (grid)",
                "Unable to generate n/k corridor from the current RMSE(d) grid.",
            )

    def _on_corridor_rmse_plot_clicked(self, ev: Any) -> None:

        if not hasattr(self, "plot_corridor_rmse_d"):
            return

        d_s = np.asarray(getattr(self, "_corridor_rmse_d_vals", []), dtype=np.float64).ravel()

        r_s = np.asarray(getattr(self, "_corridor_rmse_vals", []), dtype=np.float64).ravel()

        if d_s.size == 0 or r_s.size != d_s.size:
            return

        try:
            vb = self.plot_corridor_rmse_d.plotItem.vb

            p = vb.mapSceneToView(ev.scenePos())

            x = float(p.x())

        except NUMERICAL_FAULT_EXCEPTIONS:
            return

        if not np.isfinite(x):
            return

        i_sel = int(np.argmin(np.abs(d_s - x)))

        d_sel = float(d_s[i_sel])

        r_sel = float(r_s[i_sel])

        i_best = int(getattr(self, "_corridor_rmse_best_idx", -1))

        if i_best < 0 or i_best >= d_s.size:
            i_best = int(np.argmin(r_s))

        d_best = float(d_s[i_best])

        r_best = float(r_s[i_best])

        d_lo_rb = float(getattr(self, "_corridor_rmse_robust_lo", float("nan")))

        d_hi_rb = float(getattr(self, "_corridor_rmse_robust_hi", float("nan")))

        rb_ok = bool(getattr(self, "_corridor_rmse_robust_ok", False))

        if hasattr(self, "lbl_corridor_rmse_summary"):
            tail = (
                f" | robust interval ? [{d_lo_rb:.3f}, {d_hi_rb:.3f}] nm"
                if rb_ok and np.isfinite(d_lo_rb) and np.isfinite(d_hi_rb)
                else ""
            )

            self.lbl_corridor_rmse_summary.setText(
                f"Best computed thickness: d* = {d_best:.3f} nm | RMSE(d*) = {r_best:.6f} | "
                f"selected: d = {d_sel:.3f} nm, RMSE = {r_sel:.6f}, DeltaRMSE = {r_sel - r_best:+.6e}{tail}"
            )

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
                    "GUI Smart Init [Keep] | could not recalculate RMSE on worker mesh: %s",
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
                "GUI Smart Init [Keep] | Fil conducteur: aperçu/fenêtre RMSE=%.6f (K=%d) → valeur retenue pour le worker (SOL2 / départ INDEX_SPLINE) RMSE=%.6f (K=%d). The second value is used for optimization.",
                rmse_preview_mesh,
                _k_gui,
                rmse_worker_mesh,
                _k_wrk,
            )

        from spline_workers import _pack_spline_stage_result
        from spline_objective import physical_nodes_to_x_slice_n

        n_xi = physical_nodes_to_x_slice_n(n_phys_final, sk_final, cfg.n_mono_band_nm)
        x_final = np.concatenate(([d_final], n_xi, L_nodes_final))
        ui_snap = _pack_spline_stage_result(cfg, sk_final, x_final, float(rmse_worker_mesh**2), 0, 0)
        self._plot_result(ui_snap, plot_source="smart_init_retenir")
        dlg.accept()

    def _prepare_smart_init_autofind_config(
        self, cfg: "SplineOptConfig", cur_sk: np.ndarray, n_phys: np.ndarray, L_nodes: np.ndarray, preview_d_nm: float
    ) -> tuple["SplineOptConfig", np.ndarray, int]:
        lam_nm_af = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
        lam_min_af = float(np.nanmin(lam_nm_af))
        lam_max_af = float(np.nanmax(lam_nm_af))
        _mdl_br = float(getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.0) or 0.0)
        sk_canon = bridge_sigma_knots_preserve_manual(
            cur_sk,
            lam_min_af,
            lam_max_af,
            rmse_fit_lambda_nm=getattr(cfg, "rmse_fit_lambda_nm", None),
            min_delta_lambda_over_lambda_mean=_mdl_br if _mdl_br > 0.0 else None,
        )
        n_on, L_on = interp_n_L_pwlnk_to_sigmas(
            np.asarray(cur_sk, dtype=np.float64).ravel(),
            np.asarray(n_phys, dtype=np.float64).ravel(),
            np.asarray(L_nodes, dtype=np.float64).ravel(),
            np.asarray(sk_canon, dtype=np.float64).ravel(),
        )
        k_loc = int(np.asarray(sk_canon, dtype=np.float64).size)
        if int(np.asarray(n_on).size) != k_loc or int(np.asarray(L_on).size) != k_loc:
            raise ValueError(f"Inconsistent sizes after regridding (K={k_loc}, len(n)={np.asarray(n_on).size}).")

        x0_loc = np.concatenate(
            (
                np.asarray([float(preview_d_nm)], dtype=np.float64),
                np.asarray(n_on, dtype=np.float64).ravel(),
                np.asarray(L_on, dtype=np.float64).ravel(),
            )
        )

        _polish_af = min(int(getattr(cfg, "polish_maxfun", 8000) or 8000), 3200)
        _smlf_af = min(max(int(getattr(cfg, "stage_mandatory_local_maxfun", 0) or 0), 400), 900)
        enforce_local_optimization_policy(cfg)

        auto_cfg = replace(
            cfg,
            n_seg=int(max(1, k_loc - 1)),
            sigma_knots_override=None,
            smart_preview_exact_sigma_knots=np.asarray(sk_canon, dtype=np.float64).copy(),
            smart_preview_exact_n_L=(
                np.asarray(n_on, dtype=np.float64).copy(),
                np.asarray(L_on, dtype=np.float64).copy(),
            ),
            smart_preview_d_nm_override=float(preview_d_nm),
            x0_warm=x0_loc.copy(),
            smart_init_manual_force_restart=False,
            pglobal_trust_region_by_k=False,
            pglobal_max_time=None,
            pglobal_max_iter=0,
            pglobal_max_feval=None,
            pglobal_local_search_budget=None,
            spline_local_only=True,
            stage_mandatory_local_maxfun=int(_smlf_af),
            polish_maxfun=int(_polish_af),
            smart_init_preview_hook=None,
        )
        return auto_cfg, sk_canon, k_loc

    def _apply_smart_init_autofind_result(
        self, best: dict, k_loc: int, sk_canon: np.ndarray, state: _SmartInitState
    ) -> bool:
        n_new = np.asarray(best.get("n_nodes_physical", state.n_phys), dtype=np.float64).ravel()
        L_new = np.asarray(best.get("L_nodes", state.L_nodes), dtype=np.float64).ravel()
        size_match = n_new.size == k_loc and L_new.size == k_loc
        if size_match:
            state.n_phys = n_new.copy()
            state.L_nodes = L_new.copy()
            state.sk = np.asarray(sk_canon, dtype=np.float64).copy()

        try:
            _d_b = float(best.get("d_nm", state.preview_d_nm))
        except (TypeError, ValueError):
            _d_b = float(state.preview_d_nm)
        if np.isfinite(_d_b):
            state.preview_d_nm = _d_b

        try:
            _rm_b = float(best.get("rmse", state.current_rmse))
        except (TypeError, ValueError):
            _rm_b = float(state.current_rmse)
        if np.isfinite(_rm_b):
            state.current_rmse = min(float(state.current_rmse), _rm_b)
        if state.current_rmse < state.best_rmse:
            state.best_rmse = state.current_rmse
            state.best_n = state.n_phys.copy()
            state.best_L = state.L_nodes.copy()
        return size_match

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
            return f"Inconsistent sigma / n / ln k (K_sigma={cur_sk.size}, len(n)={n_loc.size}, len(L)={L_loc.size}). Try again after a recalculation."

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
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as exc:
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
        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError) as exc:
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

    def _result_needs_deferred_corridors(self, result: dict) -> bool:

        if not isinstance(result, dict):
            return False

        if not bool(getattr(self, "chk_corridor_d", None) and self.chk_corridor_d.isChecked()):
            return False

        if bool(result.get("profile_d_enabled", False)) or result.get("profile_d_values_nm") is not None:
            return False

        return True

    def _can_offer_mwir_extra_node(self, result: dict) -> bool:
        """True if conditions allow proposing MWIR extra node insertion dialog."""
        if not isinstance(result, dict):
            return False
        sk = result.get("sigma_knots")
        if sk is None:
            return False
        sk_a = np.asarray(sk, dtype=np.float64).ravel()
        if sk_a.size < 2:
            return False
        # Standard mode only (no split sigma_knots_n / sigma_knots_L)
        if "sigma_knots_n" in result or "sigma_knots_L" in result:
            return False
        # lambda_max > 2500 nm
        lam_src = result.get("lam_nm")
        if lam_src is None and self._last_run_cfg is not None:
            lam_src = getattr(self._last_run_cfg, "lam_nm", None)
        if lam_src is None:
            return False
        lam_a = np.asarray(lam_src, dtype=np.float64).ravel()
        if lam_a.size == 0 or float(np.max(lam_a)) <= 2500.0:
            return False
        # Finite RMSE
        return np.isfinite(float(result.get("rmse", float("inf"))))

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

        self._worker.kwargs["progress_cb"] = _manual_progress
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
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
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

        self._worker.kwargs["progress_cb"] = _manual_progress
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
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
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

        self._worker.kwargs["progress_cb"] = _manual_progress
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
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
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

        self._worker.kwargs["progress_cb"] = _manual_progress
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

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
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

        self._worker.kwargs["progress_cb"] = _manual_progress
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
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "manual_auto_clean"

        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: launching auto_clean worker | K_target=%d", int(target_sigma_knots.size)
            )

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if isinstance(getattr(self, "_manual_knots_dialog", None), ManualSigmaKnotDialog):
            self._manual_knots_dialog.set_runtime_busy(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
        self.lbl_status.setText("Advanced cleaning: iterative knot removal in progress...")
        install_skeleton(self.tabs_main, label="Advanced cleaning...")
        self._worker.start()

    def _prompt_mwir_extra_node(self, result: dict) -> bool:
        """Show Oui/Non dialog for MWIR extra sigma node insertion.  Returns True if user chose Oui."""
        sk = result.get("sigma_knots") if isinstance(result, dict) else None
        K_cur = int(np.asarray(sk, dtype=np.float64).size) if sk is not None else None
        k_label = f"K : {K_cur} → {K_cur + 1}" if K_cur is not None else "K → K+1"
        dlg = QDialog(self)
        dlg.setWindowTitle("Extra MWIR node")
        dlg.setModal(True)
        lay = QVBoxLayout(dlg)
        lab = QLabel(
            "Add an extra sigma node in the MWIR?<br>"
            f"<b>σ<sub>mid</sub></b> = (σ₀ + σ₁) / 2 &nbsp;—&nbsp; {k_label}<br><br>"
            "An L-BFGS-B re-optimization will be launched.<br>"
            "The result is accepted only if the RMSE improves significantly."
        )
        lab.setWordWrap(True)
        lay.addWidget(lab)
        bb = QDialogButtonBox(dlg)
        btn_yes = bb.addButton("Yes", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_no = bb.addButton("No", QDialogButtonBox.ButtonRole.RejectRole)
        btn_no.setDefault(True)
        choice = {"yes": False}

        def _accept() -> None:
            choice["yes"] = True
            dlg.accept()

        btn_yes.clicked.connect(_accept)
        btn_no.clicked.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()
        if self.logger:
            self.logger.info(
                "INDEX_SPLINE GUI: MWIR extra node prompt | choice=%s",
                "Yes" if choice["yes"] else "No",
            )
        return bool(choice["yes"])

    def _start_mwir_insert_worker(self, result: dict) -> None:
        """Launch MWIR node insertion worker after user confirmation."""
        cfg_base = self._last_run_cfg
        if cfg_base is None:
            cfg_base = self._build_opt_config(notify=False)
        if cfg_base is None:
            if self.logger:
                self.logger.warning("INDEX_SPLINE GUI: MWIR extra node - no config available, abort.")
            return
        CertusIndexSplineApp._prepare_worker_restart(self)
        self._best_live_rmse = float("inf")
        self._best_live_result = None
        self._last_live_log_mono = 0.0
        self._live_best_detail_log_mono = 0.0
        cfg_eff = self._cfg_with_result_substrate(cfg_base, result)
        self._worker = GenericWorker(worker_spline_mwir_insert_node, dict(result), cfg_eff, self._stop_event)

        def _mwir_progress(p: float | int, m: str) -> None:
            pv = int(round(float(p) * 100.0))
            self._worker.signals.progress.emit(max(0, min(10000, pv)), m)

        self._worker.kwargs["progress_cb"] = _mwir_progress
        self._worker.kwargs["live_cb"] = self._worker.signals.live.emit
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.live.connect(self._on_live_update)
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "mwir_insert"
        if self.logger:
            K_cur = int(np.asarray(result.get("sigma_knots", []), dtype=np.float64).size)
            rr = float(result.get("rmse", float("nan")))
            self.logger.info(
                "INDEX_SPLINE GUI: launching MWIR insert worker | K=%d | rmse=%.8f",
                K_cur,
                rr if np.isfinite(rr) else float("nan"),
            )
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._refresh_post_optimization_option_controls()
        self._prog_ui_last = 0
        self._prog_reset_bar()
        self.lbl_status.setText("MWIR node: re-optimization in progress...")
        install_skeleton(self.tabs_main, label="Extra MWIR node...")
        self._worker.start()

    def _start_deferred_corridor_worker_from_breakpoint_pending(self) -> None:

        pending = getattr(self, "_pending_breakpoint_corridor_seed", None)

        if not isinstance(pending, dict):
            return

        if self.logger:
            p_rmse = self._rmse_from_result_dict(pending)
            p_d = pending.get("d_nm")
            p_d_txt = f"{float(p_d):.6f}" if isinstance(p_d, (int, float)) and np.isfinite(float(p_d)) else "n/a"
            p_x = np.asarray(pending.get("x", []), dtype=np.float64).ravel()
            p_n = np.asarray(pending.get("n_lam", []), dtype=np.float64).ravel()
            p_k = np.asarray(pending.get("k_lam", []), dtype=np.float64).ravel()
            self.logger.info(
                "Corridors deferred launch [pending-seed-check] | d_nm=%s | rmse=%s | nan(x/n/k)=%d/%d/%d | has_solver_snapshot=%s",
                p_d_txt,
                (f"{p_rmse:.8f}" if np.isfinite(p_rmse) else "n/a"),
                int(np.sum(~np.isfinite(p_x))) if p_x.size else 0,
                int(np.sum(~np.isfinite(p_n))) if p_n.size else 0,
                int(np.sum(~np.isfinite(p_k))) if p_k.size else 0,
                "yes" if isinstance(pending.get("gui_solver_snapshot_for_corridors"), dict) else "no",
            )

        self._pending_breakpoint_corridor_seed = None

        if not self._start_deferred_corridor_worker(pending):
            QMessageBox.warning(
                self,
                "Corridor",
                "Impossible to automatically restart corridor calculation from the new solution.",
            )

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

        from certus_core import QueueHandler

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

    def _show_corridor_rmse_profile_window(self) -> None:
        """Displays the RMSE = f(thickness) window with corridor profiling data."""
        win = getattr(self, "_corridor_rmse_profile_win", None)
        if win is None or not win.isVisible():
            win = CorridorRMSEProfileWindow(self)
            self._corridor_rmse_profile_win = win

        # Mettre ? jour avec les donn?es disponibles
        if self._last_result is not None:
            d_prof = np.asarray(self._last_result.get("profile_d_values_nm", []), dtype=np.float64)
            r_prof = np.asarray(self._last_result.get("profile_d_rmse_values", []), dtype=np.float64)
            rmse_thresh = self._last_result.get("profile_d_rmse_thresh")
            if d_prof.size > 0 and r_prof.size == d_prof.size:
                win.update_profile(d_prof, r_prof, rmse_thresh)

        win.show()
        win.raise_()
        win.activateWindow()

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
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to start.")

            return

        d_s = np.asarray(src.get("profile_d_values_nm", []), dtype=np.float64).ravel()

        if d_s.size == 0:
            self.lbl_corridor_rmse_state.setText("Step 1/3: Recalculate RMSE(d) to start.")

            return

        has_manual = bool(src.get("manual_corridor_active", False))

        d_min = float(np.nanmin(d_s)) if np.any(np.isfinite(d_s)) else float("nan")

        d_max = float(np.nanmax(d_s)) if np.any(np.isfinite(d_s)) else float("nan")

        if has_manual:
            self.lbl_corridor_rmse_state.setText(
                f"Step 3/3: Corridor generated | Grid {int(d_s.size)} pts | d-range [{d_min:.2f}, {d_max:.2f}] nm"
            )

        else:
            self.lbl_corridor_rmse_state.setText(
                f"Step 2/3: Select interval then generate corridor | Grid {int(d_s.size)} pts | d-range [{d_min:.2f}, {d_max:.2f}] nm"
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
            return f"λ (indic.) = {float(lam_hint):.4f} nm  |  {y_bit}  |  n k : pas de modèle  |  d = {d_txt}"

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam_hint))
        if not res.get("ok"):
            if str(res.get("reason", "")) == "outside":
                lq = float(res.get("lambda_nm", lam_hint))
                lo = float(res.get("lambda_lo_nm", float("nan")))
                hi = float(res.get("lambda_hi_nm", float("nan")))
                return f"λ = {lq:.4f} nm  (hors grille [{lo:.1f}–{hi:.1f}] nm)\nn = —    k = —    d = {d_txt}\n{y_bit}"
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

        act_show = menu.addAction("Afficher n, k, T (modèle) au point du clic…")

        act_show.triggered.connect(lambda *_, vx=view_x, vy=view_y: self._spectrum_show_theory_probe_dialog(vx, vy))

        act_copy = menu.addAction("Copier λ, n, k, d, T (R) modèle au point — TSV")

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

                d_line = f"\nd affichée = {float(d_o):.4f} nm" if d_o is not None and np.isfinite(float(d_o)) else ""

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
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>calcul en cours...</b></span>'
        elif not unlocked:
            rich = (
                f'Corridors: <span style="color:{CertusTheme.TEXT_SUB};"><b>disponibles apres optimisation</b></span>'
            )

        elif bool(
            self._last_result.get("profile_d_enabled", False)
            or self._last_result.get("profile_d_values_nm") is not None
        ):
            rich = f'Corridors: <span style="color:{CertusTheme.SUCCESS};"><b>deja calcules</b></span>'

        else:
            rich = f'Corridors: <span style="color:{CertusTheme.PRIMARY};"><b>prets a lancer</b></span>'

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
        hint = "Actions disponibles: Noeuds manuels / Corridors"
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
            "Smart Init GUI slot enter | payload_type=%s | has_wait_event=%s",
            type(payload).__name__,
            getattr(self, "_preview_wait_event", None) is not None,
        )

        try:
            if isinstance(payload, SmartInitPayload):
                logger.info(
                    "Smart Init GUI slot: opening dialog | K_sigma=%d | incoming_d_best_nm=%.6f",
                    int(np.asarray(payload.sigma_knots, dtype=np.float64).size),
                    float(payload.d_best_nm),
                )

                self._preview_result = self._show_smart_init_preview_dialog(payload)

                logger.info(
                    "Smart Init GUI slot: dialog returned preview_result=%s | preview_ret=%s",
                    bool(self._preview_result),
                    getattr(self, "_preview_ret", None) is not None,
                )

            else:
                logger.warning(
                    "Smart Init preview: unexpected payload type %s, skipping dialog.", type(payload).__name__
                )

                self._preview_result = True

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError):
            logger.exception("Smart Init preview: GUI error (full traceback)")

            self._preview_result = True

        finally:
            if self._preview_wait_event is not None:
                self._preview_wait_event.set()

def main() -> None:

    multiprocessing.freeze_support()

    setup_module_logging("CERTUS_INDEX_SPLINE", log_file="certus_index_spline.log")

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    init_certus_app("CERTUS-INDEX-SPLINE", app=app)

    win = CertusIndexSplineApp()

    win.show()

    sys.exit(app.exec())

from certus_spline_report import SplineReportContext, SplineReportBuilder  # noqa: E402

if __name__ == "__main__":
    main()
