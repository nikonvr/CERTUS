# =============================================================================

# CERTUS DESIGN MODULE

# Functional area: Optical Synthesis & Optimization

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: only make small, reversible changes here until dedicated tests cover
# optimization workers, DTO/report contracts, and critical design workflows.
# Prefer extracting pure helpers before moving Qt classes or numerical kernels.
# Keep the design orchestration dense only where it is genuinely required.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-DESIGN.py - Optical Filter Design & Optimization

=========================================================

"""

__version__ = "26_01"

import os
from pathlib import Path

import multiprocessing
import sys
import functools

from certus_core import create_module_environment

# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_DESIGN")

script_dir = env["script_dir"]

# =============================================================================

# IMPORTS SUIVANTS

# =============================================================================

import logging

import time

import traceback

import copy

from threading import Event

from typing import Any, List, Dict

import numpy as np

# pyqtgraph configured in certus_ui, imported locally for use

import pyqtgraph as pg

from certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QThread,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

# Conditional SVG Import

# =============================================================================

# IMPORTS MODULAR ARCHITECTURE

# =============================================================================

# Import Modular Architecture

# --- 1. CORE (Config, Constants, Utils) ---

from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CAUCHY_PRESETS,
    CFG,
    ensure_numpy_array,
    get_complex_dtype,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)
from certus_errors import safe_ui_action

from certus_design_worker_utils import (
    build_pglobal_optimizer,
    build_pglobal_config_from_cfg,
    optim_backside_flags_from_cfg,
    optim_bounds_thickness_global,
    optim_bounds_thickness_healing,
    optim_bounds_thickness_local,
    optim_calc_oblique_selected,
    optim_display_wavelength_grid,
    optim_oblique_attach_local_positions,
    optim_oblique_configs_from_groups,
    optim_oblique_group_targets_on_wavelengths,
    optim_oblique_unique_display_keys,
    optim_post_optim_time_budget_seconds,
    optim_prepare_stack_nk_back,
    optim_qwot_values_from_ep_stack,
    optim_rmse_display_string,
    optim_rmse_is_valid_for_log,
    optim_var_indices_from_stack,
    prepare_pglobal_inputs_from_state,
    prepare_pglobal_optimizer_runtime,
    run_coord_descent_5cycles,
    run_pglobal_restart_loop,
)

# --- 4. DATA (IO, Reporting) ---

from certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus_design_workers_dto import (
    ColorWorkerRequest,
    ColorWorkerResult,
    NeedleWorkerResult,
    NeedleWorkerRequest,
    OptimWorkerRequest,
    OptimWorkerResult,
)

# --- 5. ERRORS (Validation, Messages) ---

# Direct import for warmup

# --- 2. PHYSICS (Models, TMM, Optimization) ---

from certus_physics import (  # Cache & Utils; Gradient Logic (Analytic); Numba Functions
    Layer,
    Material,
    ObliqueTarget,
    PGlobalConfig,
    PGlobalOptimizer,
    Target,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    compute_gradient_all_layers_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_gradient_contrib_analytic,
    cost_numba_fast,
    delta_e_2000,
    init_thickness,
    lab_to_rgb,
    needle_scan_cached,
    prepare_targets_vectorized,
    xyz_from_spectrum,
    xyz_to_lab,
)

from certus_index_utils import spectral_rmse_weights

# --- 3. UI (Theme, Widgets) ---

from certus_ui import (
    CertusTheme,
    CertusBaseApp,
    CertusScientificPlot,
    CertusThemeToggle,
    CertusCard,
    CertusCollapsible,
    CertusStatusPill,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    EnhancedProgressWidget,
    FlashyCard,
    WelcomeGuideWidget,
    WorkerSignals,
    certus_get_save_file_name,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    create_flashy_grid,
    create_header_logo_widget,
    create_top_actions_bar,
    get_export_config,
    init_certus_app,
    open_documentation,
)
from certus_metrology import ValidationStatus
from certus_services import IndexFitRequest, IndexFitService

from certus_load_summary import build_summary_plain_text, show_load_summary_dialog

from certus_spectral_workers import EvalWorker, WarmupWorker

from certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)

# Configure GUI

# =============================================================================

# PGlobalConfig Methods (now provided by certus_physics.structures)

# =============================================================================

# Conditional Excel Import (OPENPYXL_AVAILABLE used elsewhere in module)

# =============================================================================

# LOGGING CONFIGURATION

# =============================================================================

# Logger initialized in CertusDesignApp

# This ensures consistency with other CERTUS modules

# script_dir already set by bootstrap_app()

# =============================================================================

# AUTOMATIC PRECISION ADAPTATION

# =============================================================================

# Use wrappers if single precision enabled

# Note: cost_numba_fast handles precision internally

# Wrappers enforce (d,n) consistency

from certus_physics import (
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper,
)

calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full = calc_spectrum_full_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# =============================================================================

# DESIGN-SPECIFIC WORKERS

# =============================================================================

def _design_objective_wrapper_common(app, x) -> Any:
    """Shared objective wrapper for Optim/Color/Needle workers."""
    if len(x) != len(app._var_idx):
        return 1e30

    if app._all_variable:
        ep_buffer = np.ascontiguousarray(x)
    else:
        # Reuse pre-allocated buffer (no allocation per call)
        ep_buffer = app._ep_buffer
        ep_buffer[:] = app._ep0
        ep_buffer[app._var_idx] = x

    min_thick = CFG.MIN_THICKNESS
    # Vectorized min-thickness penalty (Python 3.14+ friendly)
    if np.any((ep_buffer > 1e-12) & (ep_buffer < min_thick)):
        return 1e30

    if app._oblique_mode:
        return app._compute_oblique_error(ep_buffer)

    return cost_numba_fast(
        ep_buffer,
        app._n_layers_T,
        app._n_sub,
        app._wls,
        app._tgt_vals,
        app._tgt_weights,
        CFG.MIN_THICKNESS,
        app._has_back_calc,
        app._n_back_T,
        app._d_back,
    )

def _design_compute_oblique_error_common(app, ep_test) -> Any:
    """Shared oblique-mode error grouped by (angle, polarization)."""
    total_err = 0.0
    total_weight = 0.0

    for config in app._oblique_configs:
        # Compute R & T ONCE for all targets at this (angle, pol)
        R_config, T_config = optim_calc_oblique_selected(
            config["wls_config"],
            config["n_layers_T_config"],
            ep_test,
            config["n_sub_config"],
            config["angle"],
            config["pol"],
            has_back_calc=app._has_back_calc,
            has_back_stack=app._has_back_stack,
            d_back=app._d_back,
            n_back_T=app._n_back_T,
            calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
            calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
            calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
        )

        _sw_cfg = config["sw_cfg"]
        # Extract values for each target using precomputed positions
        for tgt_data in config["targets"]:
            local_positions = tgt_data["local_positions"]
            vals = R_config[local_positions] if tgt_data["target_type"] == "R" else T_config[local_positions]
            # Spectrally weighted squared error (Delta ln lambda quadrature)
            _sw = _sw_cfg[local_positions]
            err = np.sum(_sw * (vals - tgt_data["tgt_vals"]) ** 2) * tgt_data["weight"]
            total_err += err
            total_weight += tgt_data["weight"] * np.sum(_sw)

    if total_weight < 1e-12:
        return 1e30
    return total_err / total_weight

def _design_gradient_func_pglobal_common(app, x) -> Any:
    """Shared cost + analytic gradient for PGlobalOptimizer."""
    if len(x) != len(app._var_idx):
        return 1e30, np.zeros(len(app._var_idx), dtype=np.float64)

    if app._all_variable:
        ep_full = np.ascontiguousarray(x)
    else:
        # Reuse pre-allocated buffer (no allocation per call)
        ep_full = app._ep_buffer
        ep_full[:] = app._ep0
        ep_full[app._var_idx] = x

    min_thick = CFG.MIN_THICKNESS
    # Vectorized min-thickness penalty with gradient (Python 3.14+ friendly)
    violations = (ep_full > 1e-12) & (ep_full < min_thick)
    if np.any(violations):
        var_violations = violations[app._var_idx]
        if np.any(var_violations):
            grad_penalty = np.zeros(len(app._var_idx), dtype=np.float64)
            grad_penalty[var_violations] = 1e6 * (min_thick - ep_full[app._var_idx[var_violations]])
            return 1e30, grad_penalty
        return 1e30, np.zeros(len(app._var_idx), dtype=np.float64)

    if app._oblique_mode:
        return app._compute_oblique_error_and_grad_analytic(ep_full)

    cost, grad_var = compute_gradient_all_layers_analytic(
        ep_full,
        app._n_layers_T,
        app._n_sub,
        app._wls,
        app._tgt_vals,
        app._tgt_weights,
        CFG.MIN_THICKNESS,
        app._has_back_calc,
        app._n_back_T,
        app._d_back,
        app._var_idx,
    )
    return cost, grad_var

def _design_compute_oblique_error_and_grad_analytic_common(app, ep_test) -> tuple:
    """
    Shared oblique cost + analytic gradient.

    - Front-only: direct analytic contribution kernel.
    - Backside enabled: full chain rule on oblique incoherent formula.
    """
    total_err = 0.0
    total_weight = 0.0
    grad_raw = np.zeros(len(app._var_idx), dtype=np.float64)

    for config in app._oblique_configs:
        wls_cfg = config["wls_config"]
        n_layers_cfg = config["n_layers_T_config"]
        n_sub_cfg = config["n_sub_config"]
        _sw_cfg = config["sw_cfg"]

        for tgt_data in config["targets"]:
            local_positions = tgt_data["local_positions"]
            if local_positions.size == 0:
                continue

            wls_sel = wls_cfg[local_positions]
            n_layers_sel = n_layers_cfg[local_positions, :]
            n_sub_sel = n_sub_cfg[local_positions]

            tgt_vals_sel = np.asarray(tgt_data["tgt_vals"], dtype=np.float64)
            tgt_w_sel = _sw_cfg[local_positions] * float(tgt_data["weight"])

            is_reflectance = tgt_data["target_type"] == "R"
            angle = float(config["angle"])
            is_s_pol = bool(config["is_s_pol"])

            if app._has_back_calc:
                # Front forward: Air -> Front -> Sub
                Rf, Tf, dRf, dTf = compute_oblique_rt_and_grads_analytic(
                    ep_test,
                    n_layers_sel,
                    n_sub_sel,
                    wls_sel,
                    app._var_idx,
                    angle,
                    is_s_pol,
                    False,
                )

                # Front reverse: Sub -> Front -> Air
                Rf_prime, T_front_rev, dRf_prime, dT_front_rev = compute_oblique_rt_and_grads_analytic(
                    ep_test,
                    n_layers_sel,
                    n_sub_sel,
                    wls_sel,
                    app._var_idx,
                    angle,
                    is_s_pol,
                    True,
                )

                # Back reverse: Sub -> Back -> Air (fixed wrt front ep)
                if app._has_back_stack:
                    n_back_sel = app._n_back_T[config["all_clues"], :][local_positions, :]
                    Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(
                        app._d_back,
                        n_back_sel,
                        n_sub_sel,
                        wls_sel,
                        np.zeros(0, dtype=np.int64),
                        angle,
                        is_s_pol,
                        True,
                    )
                else:
                    Rb_prime, Tb, _, _ = compute_oblique_rt_and_grads_analytic(
                        np.zeros(0, dtype=np.float64),
                        np.zeros((len(wls_sel), 0), dtype=np.complex128),
                        n_sub_sel,
                        wls_sel,
                        np.zeros(0, dtype=np.int64),
                        angle,
                        is_s_pol,
                        True,
                    )

                D = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)
                D2 = D * D

                if is_reflectance:
                    # R_total = Rf + (Tf * T_front_rev * Rb') / D
                    y_vals = Rf + (Tf * T_front_rev * Rb_prime) / D
                    dy = dRf + (
                        (Rb_prime[:, None] * (dTf * T_front_rev[:, None] + Tf[:, None] * dT_front_rev)) / D[:, None]
                        + ((Tf * T_front_rev * (Rb_prime * Rb_prime))[:, None] * dRf_prime / D2[:, None])
                    )
                else:
                    # T_total = (Tf * Tb) / D
                    y_vals = (Tf * Tb) / D
                    dy = Tb[:, None] * (dTf / D[:, None] + (Tf[:, None] * Rb_prime[:, None] * dRf_prime) / D2[:, None])

                diff = y_vals - tgt_vals_sel
                _sw = _sw_cfg[local_positions]
                w_scalar = float(tgt_data["weight"])
                total_err += np.sum(_sw * diff * diff) * w_scalar
                total_weight += w_scalar * np.sum(_sw)
                grad_raw += np.sum((_sw[:, None] * diff[:, None] * dy), axis=0) * w_scalar

            else:
                err_sum, grad_contrib, weight_sum = compute_oblique_gradient_contrib_analytic(
                    ep_test,
                    n_layers_sel,
                    n_sub_sel,
                    wls_sel,
                    tgt_vals_sel,
                    tgt_w_sel,
                    angle,
                    is_s_pol,
                    bool(is_reflectance),
                    app._var_idx,
                )
                total_err += err_sum
                total_weight += weight_sum
                grad_raw += grad_contrib

    if total_weight < 1e-12:
        return 1e30, np.zeros(len(app._var_idx), dtype=np.float64)
    return total_err / total_weight, (2.0 / total_weight) * grad_raw

def _design_optimization_callback_common(app, sample) -> None:
    try:
        if app._stop_event.is_set():
            logging.debug("OptimWorker callback: stop_event is set, returning")
            return

        current_rmse = np.sqrt(sample.y) if sample.y < 1e20 else 1e9

        try:
            n_clusters = len(app._optimizer.clusterer.clusters)
            n_evals = app._optimizer.n_evals
        except NUMERICAL_FAULT_EXCEPTIONS as cluster_err:
            logging.warning(
                f"Error accessing self._optimizer stats in callback: {cluster_err}",
                exc_info=True,
            )
            n_clusters = 0
            n_evals = 0

        # Throttling: limit emission frequency
        app._callback_counter += 1

        # Periodic log
        if app._callback_counter % 1000 == 0:
            logging.debug(
                f"OptimWorker callback #{app._callback_counter}: n_evals={n_evals}, current_rmse={current_rmse:.6e}, best_rmse_seen={app.best_rmse_seen:.6e}, gen={sample.generation}"
            )

        # Ensure we display the best RMSE seen so far, filtering out dummy values from local search
        display_best = min(current_rmse, app.best_rmse_seen)
        msg = f"Gen {sample.generation} | Evals:  {n_evals} | Clusters: {n_clusters} | Best:  {display_best:.6f}"

        # Calculate percentage based on max_feval (approximate but better than nothing)
        max_evals = app.cfg.get("max_feval", 50000)
        pct = 0
        if max_evals > 0:
            pct = int(100 * n_evals / max_evals)

        # THROTTLE GUI: emit progress log only every 1000 callbacks
        # Stats counters always updated but log message throttled
        try:
            if app._callback_counter % 1000 == 0 or current_rmse < app.best_rmse_seen:
                app.signals.progress.emit(pct, msg)
            app.signals.update_stats.emit("MINIMA", n_clusters)
            app.signals.update_stats.emit("EVAL", n_evals)
        except NUMERICAL_FAULT_EXCEPTIONS as emit_err:
            logging.error(
                f"Error emitting signals in callback: {emit_err}",
                exc_info=True,
            )

        # Update best result (with throttling)
        should_emit_result = False

        # Update ep_disp for best_ep_final
        ep_disp = app._ep0.copy()
        ep_disp[app._var_idx] = sample.x

        if current_rmse < app.best_rmse_seen:
            # Calculate improvement ratio
            old_best = app.best_rmse_seen
            app.best_rmse_seen = current_rmse

            # SAVE BEST RESULT IMMEDIATELY for stop handling
            app.best_ep_final = ep_disp.copy()
            app.best_rmse_final = current_rmse

            improvement_ratio = (old_best - current_rmse) / max(old_best, 1e-10) if old_best < float("inf") else 1.0

            # Throttle: emit every 10 or >1%
            should_emit_result = (app._callback_counter % 10 == 0) or (improvement_ratio > 0.01)

        # Emit signal if throttling allows
        if should_emit_result:
            try:
                if app._oblique_mode:
                    spectra_display = {}
                    for angle, pol in app._display_oblique_keys:
                        R_disp, T_disp = optim_calc_oblique_selected(
                            app._wls_display,
                            app._n_lay_T_disp,
                            ep_disp,
                            app._n_sub_disp,
                            angle,
                            pol,
                            has_back_calc=app._has_back_calc,
                            has_back_stack=app._has_back_stack,
                            d_back=app._d_back,
                            n_back_T=app._n_back_T,
                            calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
                            calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
                            calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
                        )
                        spectra_display[(angle, pol)] = {"R": R_disp, "T": T_disp}

                    if spectra_display:
                        first_key = app._display_oblique_keys[0]
                        Ts = spectra_display[first_key]["T"]
                    else:
                        Ts, _ = calc_spectrum_front(app._wls_display, app._n_lay_T_disp, ep_disp, app._n_sub_disp)

                elif app._has_back_calc:
                    _, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(
                        app._wls_display,
                        app._n_lay_T_disp,
                        ep_disp,
                        app._n_sub_disp,
                        app._n_back_T_disp,
                        app._d_back,
                    )

                    # Exact incoherent: T_total = (Tf * Tb) / (1 - Rf' * Rb')
                    denom = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)
                    Ts = (Tf * Tb) / denom

                else:
                    Ts, _ = calc_spectrum_front(app._wls_display, app._n_lay_T_disp, ep_disp, app._n_sub_disp)

                result_data = {
                    "type": "intermediate",
                    "self._wls": app._wls_display,
                    "Ts": Ts,
                    "ep": ep_disp,
                    "rmse": current_rmse,
                    "evals": n_evals,
                    "is_global_best": True,
                }

                if app._oblique_mode:
                    result_data["self._oblique_mode"] = True
                    result_data["spectra_display"] = spectra_display
                    result_data["self._oblique_tgts"] = app._oblique_tgts
                else:
                    result_data["self._oblique_mode"] = False

                app.signals.result.emit(result_data)

                if app._callback_counter % 50 == 0:
                    logging.debug(
                        f"OptimWorker callback #{app._callback_counter}: emitted result signal, rmse={current_rmse:.6e}"
                    )

            except NUMERICAL_FAULT_EXCEPTIONS as emit_result_err:
                logging.error(
                    f"Error emitting result signal in callback: {emit_result_err}",
                    exc_info=True,
                )

        # Refresh best result in GUI
        _live_interval = 2.0
        now = time.time()
        if now - app._last_live_emit_time >= _live_interval and app.best_ep_final is not None:
            app._last_live_emit_time = now
            try:
                ep_best = app.best_ep_final

                if app._oblique_mode:
                    spectra_display_best = {}
                    for angle, pol in app._display_oblique_keys:
                        R_disp, T_disp = optim_calc_oblique_selected(
                            app._wls_display,
                            app._n_lay_T_disp,
                            ep_best,
                            app._n_sub_disp,
                            angle,
                            pol,
                            has_back_calc=app._has_back_calc,
                            has_back_stack=app._has_back_stack,
                            d_back=app._d_back,
                            n_back_T=app._n_back_T,
                            calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
                            calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
                            calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
                        )
                        spectra_display_best[(angle, pol)] = {"R": R_disp, "T": T_disp}

                    first_key_best = app._display_oblique_keys[0] if spectra_display_best else None
                    Ts_best = spectra_display_best[first_key_best]["T"] if first_key_best else None
                    if Ts_best is None:
                        Ts_best, _ = calc_spectrum_front(app._wls_display, app._n_lay_T_disp, ep_best, app._n_sub_disp)

                elif app._has_back_calc:
                    _, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(
                        app._wls_display,
                        app._n_lay_T_disp,
                        ep_best,
                        app._n_sub_disp,
                        app._n_back_T_disp,
                        app._d_back,
                    )
                    denom = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)
                    Ts_best = (Tf * Tb) / denom

                else:
                    Ts_best, _ = calc_spectrum_front(app._wls_display, app._n_lay_T_disp, ep_best, app._n_sub_disp)

                best_data = {
                    "type": "intermediate",
                    "self._wls": app._wls_display,
                    "Ts": Ts_best,
                    "ep": ep_best.copy(),
                    "rmse": app.best_rmse_final,
                    "evals": n_evals,
                    "is_global_best": True,
                }

                if app._oblique_mode:
                    best_data["self._oblique_mode"] = True
                    best_data["spectra_display"] = spectra_display_best if app._oblique_mode else {}
                    best_data["self._oblique_tgts"] = app._oblique_tgts
                else:
                    best_data["self._oblique_mode"] = False

                app.signals.result.emit(best_data)

            except NUMERICAL_FAULT_EXCEPTIONS as live_err:
                logging.debug(f"OptimWorker 2s live refresh: {live_err}")

    except NUMERICAL_FAULT_EXCEPTIONS as callback_err:
        logging.error(
            f"Error in OptimWorker callback function: {callback_err}",
            exc_info=True,
        )

class OptimWorker(QThread):
    """PGLOBAL Optimization Worker"""

    def __init__(self, cfg: dict[str, Any] | OptimWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, OptimWorkerRequest) else OptimWorkerRequest.from_legacy(cfg)

        # Keep legacy mutable cfg field for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

        self._stop_event = Event()

        float_dtype = get_float_dtype()

        self._wls_display = optim_display_wavelength_grid(cfg, float_dtype=float_dtype)

        self.best_rmse_seen = float("inf")

        self.best_ep_final = None

        self.best_rmse_final = float("inf")

        # Throttling counter

        self._callback_counter = 0

        self._last_result_emit_time = 0.0

        self._last_live_emit_time = 0.0  # refresh best result every 2s in GUI

    def request_stop(self) -> None:

        self._stop_event.set()

    def _compute_oblique_error(self, ep_test) -> Any:
        return _design_compute_oblique_error_common(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return _design_compute_oblique_error_and_grad_analytic_common(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return _design_objective_wrapper_common(self, x)

    def _gradient_func_pglobal(self, x) -> Any:
        return _design_gradient_func_pglobal_common(self, x)

    def _optimization_callback(self, sample) -> Any:
        return _design_optimization_callback_common(self, sample)

    def _run_pre_polish(self, x0_start, var_idx, gradient_func_to_use, objective_wrapper) -> Any:
        """Run a short local gradient descent before global search.

        Performs up to 50 backtracking-line-search iterations starting from
        ``x0_start``, respecting the ``CFG.MIN_THICKNESS`` lower bound and the
        worker stop event. Emits a single ``progress`` start signal, then a
        terminal ``Pre-Polish complete. RMSE: ...`` signal at the end.

        Parameters
        ----------
        x0_start : np.ndarray
            Initial point in the variable subspace (length == ``len(var_idx)``).
        var_idx : Sequence[int]
            Index list of optimizable layers (used only to size the bounds clip).
        gradient_func_to_use : Callable
            Returns ``(cost, grad)`` for a candidate point.
        objective_wrapper : Callable
            Returns ``cost`` for a candidate point.

        Returns
        -------
        np.ndarray
            Polished starting point (caller-side replacement of ``x0_start``).
        """

        self.signals.progress.emit(0, "Pre-Polish: Running local gradient descent...")

        # Gradient path is analytic for all supported modes.

        can_use_grad = True

        # Simple Gradient Descent with Backtracking Line Search

        # Only 50 iterations max to avoid wasting time

        pp_current_x = x0_start.copy()

        pp_current_cost = objective_wrapper(pp_current_x)

        for pp_iter in range(50):
            if self._stop_event.is_set():
                break

            if can_use_grad:
                c, g = gradient_func_to_use(pp_current_x)

            g_norm = np.linalg.norm(g)

            if g_norm < 1e-8:
                break

            # Descent

            direction = -g / g_norm

            # Backtracking

            alpha = 1.0  # Initial step size

            if pp_iter > 0:
                alpha = 2.0  # Aggressive growth

            improved_step = False

            for _ in range(10):
                x_trial = pp_current_x + alpha * direction

                # Bounds constraint (approximate: clip to min thickness)

                # Respect PGlobal bounds, prioritize min thickness

                for i_b, _ in enumerate(var_idx):
                    if x_trial[i_b] < CFG.MIN_THICKNESS:
                        x_trial[i_b] = CFG.MIN_THICKNESS

                c_trial = objective_wrapper(x_trial)

                if c_trial < pp_current_cost:
                    pp_current_x = x_trial

                    pp_current_cost = c_trial

                    improved_step = True

                    break

                alpha *= 0.5

            if not improved_step:
                break

        pp_rmse_str = f"{np.sqrt(pp_current_cost):.6f}" if pp_current_cost < 1e20 else "N/A"

        self.signals.progress.emit(
            0,
            f"Pre-Polish complete. RMSE: {pp_rmse_str}",
        )

        return pp_current_x

    def _run_pglobal_setup(
        self,
        mode,
        max_iter_run,
        dim,
        objective_wrapper,
        bounds,
        pg_conf,
        x0_start,
        gradient_func_to_use,
    ) -> tuple:
        """Build and configure the PGlobalOptimizer for the current run.

        Creates the optimizer with analytic gradient (L-BFGS-B), stores it on
        ``self._optimizer`` for live introspection, emits the appropriate
        progress message based on ``mode``, captures the start timestamp and
        logs the initial state.

        Parameters
        ----------
        mode : str
            Optimization mode: ``'local'``, ``'healing'`` or anything else
            (treated as global).
        max_iter_run : int
            Iteration budget for the run (used for logging only here).
        dim : int
            Problem dimensionality (used for logging only here).
        objective_wrapper, bounds, pg_conf : Any
            Forwarded directly to ``PGlobalOptimizer``.
        x0_start : np.ndarray
            Initial point used to densify sampling around the start design.
        gradient_func_to_use : Callable
            Analytic gradient routine forwarded to L-BFGS-B.

        Returns
        -------
        tuple
            ``(optimizer, opt_start_time)`` to be consumed by the restart loop.
        """

        optimizer = build_pglobal_optimizer(
            objective_wrapper=objective_wrapper,
            bounds=bounds,
            stop_event=self._stop_event,
            pg_conf=pg_conf,
            x0_start=x0_start,
            gradient_func=gradient_func_to_use,
        )
        self._optimizer = optimizer
        return prepare_pglobal_optimizer_runtime(
            optimizer=optimizer,
            mode=mode,
            max_iter_run=max_iter_run,
            dim=dim,
            progress_emit=self.signals.progress.emit,
            best_rmse_seen=self.best_rmse_seen,
            callback_counter=self._callback_counter,
        )

    def _run_pglobal_restart_loop(
        self,
        *,
        mode,
        optimizer,
        objective_wrapper,
        bounds,
        pg_conf,
        gradient_func_to_use,
        max_iter_run,
        callback,
        opt_start_time,
    ) -> Any:
        """Run the PGLOBAL auto-restart loop and return the best sample found."""

        return run_pglobal_restart_loop(
            mode=mode,
            optimizer=optimizer,
            objective_wrapper=objective_wrapper,
            bounds=bounds,
            pg_conf=pg_conf,
            gradient_func_to_use=gradient_func_to_use,
            max_iter_run=max_iter_run,
            callback=callback,
            opt_start_time=opt_start_time,
            stop_event=self._stop_event,
            progress_emit=self.signals.progress.emit,
            cfg=self.cfg,
            callback_counter_getter=lambda: self._callback_counter,
            set_optimizer=lambda new_optimizer: setattr(self, "_optimizer", new_optimizer),
        )

    def _evaluate_thicknesses(
        self,
        ep_test,
        *,
        oblique_mode,
        compute_oblique_error,
        n_layers_T,
        n_sub,
        wls,
        tgt_vals,
        tgt_weights,
        has_back_calc,
        n_back_T,
        d_back,
    ) -> Any:
        """Evaluate a thickness configuration."""

        if oblique_mode:
            return compute_oblique_error(ep_test)

        return cost_numba_fast(
            ep_test,
            n_layers_T,
            n_sub,
            wls,
            tgt_vals,
            tgt_weights,
            CFG.MIN_THICKNESS,
            has_back_calc,
            n_back_T,
            d_back,
        )

    def _get_gradient_analytic(
        self,
        ep_test,
        *,
        oblique_mode,
        compute_oblique_error_and_grad_analytic,
        n_layers_T,
        n_sub,
        wls,
        tgt_vals,
        tgt_weights,
        has_back_calc,
        n_back_T,
        d_back,
        var_idx,
    ) -> Any:
        """Compute cost and analytic gradient for refinement."""

        if oblique_mode:
            return compute_oblique_error_and_grad_analytic(ep_test)

        cost, grad = compute_gradient_all_layers_analytic(
            ep_test,
            n_layers_T,
            n_sub,
            wls,
            tgt_vals,
            tgt_weights,
            CFG.MIN_THICKNESS,
            has_back_calc,
            n_back_T,
            d_back,
            var_idx,
        )

        return cost, grad

    def _run_coord_descent_5cycles(
        self,
        *,
        ep_current,
        best_cost,
        var_idx,
        oblique_mode,
        compute_oblique_error,
        compute_oblique_error_and_grad_analytic,
        n_layers_T,
        n_sub,
        wls,
        tgt_vals,
        tgt_weights,
        has_back_calc,
        n_back_T,
        d_back,
    ) -> tuple:
        """Run final 5-cycle coordinate-descent refinement and return updated state."""

        use_gradient = True  # Enable analytic gradient

        cycle_no_gain = 0

        cycle_rel_gain_min = float(self.cfg.get("cycle_rel_gain_min", 2e-4))  # 0.02%

        cycle_no_gain_patience = int(self.cfg.get("cycle_no_gain_patience", 1))

        for cycle in range(5):
            if self._stop_event.is_set():
                break

            cycle_start_best = float(best_cost)

            ep_current.copy()

            float_dtype = get_float_dtype()

            n_vars = len(var_idx)

            steps = np.full(n_vars, 2.0, dtype=float_dtype)

            min_step_val = 1e-4  # gradient in f64 -> tight threshold

            min_steps = np.full(n_vars, min_step_val, dtype=float_dtype)

            if use_gradient:
                for _ in range(50):
                    try:
                        cost_curr, grad = self._get_gradient_analytic(
                            ep_current,
                            oblique_mode=oblique_mode,
                            compute_oblique_error_and_grad_analytic=compute_oblique_error_and_grad_analytic,
                            n_layers_T=n_layers_T,
                            n_sub=n_sub,
                            wls=wls,
                            tgt_vals=tgt_vals,
                            tgt_weights=tgt_weights,
                            has_back_calc=has_back_calc,
                            n_back_T=n_back_T,
                            d_back=d_back,
                            var_idx=var_idx,
                        )

                        if cost_curr < best_cost:
                            best_cost = cost_curr

                        grad_norm = np.linalg.norm(grad)

                        if grad_norm < 1e-8:
                            break

                        direction = -grad / grad_norm

                        alpha = 2.0

                        improved_step = False

                        for _ in range(10):
                            ep_trial = ep_current.copy()

                            for i, v_idx in enumerate(var_idx):
                                ep_trial[v_idx] += alpha * direction[i]

                                ep_trial[v_idx] = max(CFG.MIN_THICKNESS, ep_trial[v_idx])

                            cost_trial = self._evaluate_thicknesses(
                                ep_trial,
                                oblique_mode=oblique_mode,
                                compute_oblique_error=compute_oblique_error,
                                n_layers_T=n_layers_T,
                                n_sub=n_sub,
                                wls=wls,
                                tgt_vals=tgt_vals,
                                tgt_weights=tgt_weights,
                                has_back_calc=has_back_calc,
                                n_back_T=n_back_T,
                                d_back=d_back,
                            )

                            if cost_trial < best_cost - 1e-8 * alpha * grad_norm:
                                ep_current = ep_trial

                                best_cost = cost_trial

                                improved_step = True

                                break

                            alpha *= 0.5

                        if not improved_step:
                            break

                    except (
                        ValueError,
                        RuntimeError,
                        np.linalg.LinAlgError,
                    ) as e:
                        logging.debug(f"Gradient optimization failed, fallback to coordinate descent: {e}")

                        use_gradient = False

                        break

            if not use_gradient:
                for _ in range(200):
                    improved = False

                    for i, v_idx in enumerate(var_idx):
                        if steps[i] < min_steps[i]:
                            continue

                        original_val = ep_current[v_idx]

                        step = steps[i]

                        ep_current[v_idx] = original_val + step

                        ep_current[v_idx] = max(CFG.MIN_THICKNESS, ep_current[v_idx])

                        cost_plus = self._evaluate_thicknesses(
                            ep_current,
                            oblique_mode=oblique_mode,
                            compute_oblique_error=compute_oblique_error,
                            n_layers_T=n_layers_T,
                            n_sub=n_sub,
                            wls=wls,
                            tgt_vals=tgt_vals,
                            tgt_weights=tgt_weights,
                            has_back_calc=has_back_calc,
                            n_back_T=n_back_T,
                            d_back=d_back,
                        )

                        if cost_plus < best_cost:
                            best_cost = cost_plus

                            steps[i] *= 1.2

                            improved = True

                            continue

                        ep_current[v_idx] = original_val - step

                        ep_current[v_idx] = max(CFG.MIN_THICKNESS, ep_current[v_idx])

                        cost_minus = self._evaluate_thicknesses(
                            ep_current,
                            oblique_mode=oblique_mode,
                            compute_oblique_error=compute_oblique_error,
                            n_layers_T=n_layers_T,
                            n_sub=n_sub,
                            wls=wls,
                            tgt_vals=tgt_vals,
                            tgt_weights=tgt_weights,
                            has_back_calc=has_back_calc,
                            n_back_T=n_back_T,
                            d_back=d_back,
                        )

                        if cost_minus < best_cost:
                            best_cost = cost_minus

                            steps[i] *= 1.2

                            improved = True

                        else:
                            ep_current[v_idx] = original_val

                            steps[i] *= 0.5

                    if not improved:
                        break

            current_rmse = np.sqrt(best_cost) if best_cost < 1e20 else 1e9

            if current_rmse < self.best_rmse_seen:
                self.best_rmse_seen = current_rmse

            self.signals.progress.emit(
                95 + cycle,
                f"Refine cycle {cycle + 1}/5 - RMSE: {current_rmse:.6f}",
            )

            if np.isfinite(cycle_start_best) and np.isfinite(best_cost):
                rel_gain_cycle = (cycle_start_best - best_cost) / max(abs(cycle_start_best), 1e-12)

                if rel_gain_cycle < cycle_rel_gain_min:
                    cycle_no_gain += 1

                else:
                    cycle_no_gain = 0

                if cycle_no_gain > cycle_no_gain_patience:
                    logging.info(
                        "OptimWorker: final refinement stopped on stagnation "
                        f"({cycle_no_gain} cycle(s) below {cycle_rel_gain_min * 100:.3f}% gain)."
                    )

                    break

        return ep_current, best_cost

    def _finalize_and_emit_optimization_result(self, ep_current, best_cost) -> None:
        """Finalize best solution selection and emit success payload."""

        ep_final = ep_current.copy()

        final_rmse = np.sqrt(best_cost) if best_cost < 1e20 else 1e9

        if final_rmse < self.best_rmse_seen:
            self.best_rmse_seen = final_rmse

            self.best_ep_final = ep_final.copy()

            self.best_rmse_final = final_rmse

        elif hasattr(self, "best_ep_final") and self.best_ep_final is not None:
            ep_final = self.best_ep_final

            final_rmse = self.best_rmse_final

            logging.info(
                f"OptimWorker: Keeping callback best (RMSE={final_rmse:.6e}) over coord descent (RMSE={np.sqrt(best_cost):.6e})"
            )

        else:
            self.best_ep_final = ep_final.copy()

            self.best_rmse_final = final_rmse

        result_payload = OptimWorkerResult.success(ep=ep_final, rmse=float(final_rmse))

        self.signals.finished.emit(result_payload.to_legacy_dict())

    def _maybe_upgrade_grid_tikhonravov(
        self,
        *,
        ep_current: np.ndarray,
        mats: dict,
        stack,
        tgts,
        oblique_mode: bool,
        oblique_tgts,
        wls: np.ndarray,
        float_dtype,
        complex_dtype,
        has_back_stack: bool,
        stack_back,
        ep_back: np.ndarray,
        n_sub: np.ndarray,
        n_layers_T: np.ndarray,
        n_back_T: np.ndarray,
        tgt_vals,
        tgt_weights,
    ) -> tuple:
        """Apply optional Tikhonravov-driven wavelength grid densification before final polish."""
        try:
            # Calculate recommended points based on current thicknesses
            lambda_min = (
                min(t.lmin for t in tgts if t.valid())
                if not oblique_mode
                else min(t.lmin for t in oblique_tgts if t.valid())
            )

            lambda_max = (
                max(t.lmax for t in tgts if t.valid())
                if not oblique_mode
                else max(t.lmax for t in oblique_tgts if t.valid())
            )

            wl_ref = (lambda_min + lambda_max) / 2.0

            # Calculate total optical thickness L = Sum(n_i * d_i)
            L_total = 0.0
            for i, layer in enumerate(stack):
                if i >= len(ep_current):
                    continue
                mat_obj = mats.get(layer.mat)
                if mat_obj:
                    n_ref = mat_obj.get_nk(np.array([wl_ref]))[0].real
                    L_total += n_ref * ep_current[i]

            if L_total > 1e-6 and lambda_max > lambda_min:
                nu_min = 1.0 / lambda_max
                nu_max = 1.0 / lambda_min
                delta_nu = nu_max - nu_min
                marge = 10.0
                N_tikhon = int(np.ceil(2.0 * L_total * delta_nu * marge))
                N_tikhon = max(10, min(5000, N_tikhon))

                current_n_points = len(wls)
                # Upgrade if >15% more points needed
                if N_tikhon > current_n_points * 1.15:
                    logging.info(
                        f"Tikhonravov: Upgrading grid from {current_n_points} to {N_tikhon} points for final refinement"
                    )

                    # Regenerate wavelength grid
                    active_tgts_for_grid = [t for t in (oblique_tgts if oblique_mode else tgts) if t.valid()]
                    wls_list_new = []
                    for t in active_tgts_for_grid:
                        start = max(t.lmin, 1e-3)
                        end = max(t.lmax, start + 1e-3)
                        sigma_min = 1.0 / end
                        sigma_max = 1.0 / start
                        sigma_grid = np.linspace(sigma_min, sigma_max, N_tikhon)
                        wls_list_new.append(1.0 / sigma_grid)

                    wls = np.unique(np.concatenate(wls_list_new))
                    wls = np.ascontiguousarray(wls.astype(float_dtype))

                    # Recalculate material clues for new grid
                    mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}
                    _sub_key = "substrate" if "substrate" in mats_nk else "Substrate"
                    n_sub = np.ascontiguousarray(mats_nk[_sub_key])

                    n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)
                    n_layers_T = np.ascontiguousarray(n_layers.T)

                    if has_back_stack:
                        n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)
                        n_back_T = np.ascontiguousarray(n_back.T)

                    # Recalculate target values if not oblique
                    if not oblique_mode:
                        tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)
                    else:
                        # Rebuild oblique configs for new grid
                        config_groups = {}
                        for tgt in [t for t in oblique_tgts if t.valid()]:
                            mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)
                            if not np.any(mask):
                                continue
                            key = (tgt.angle, tgt.pol)
                            clues = np.where(mask)[0]
                            if key not in config_groups:
                                config_groups[key] = {"clues_set": set(), "targets": []}

                            config_groups[key]["clues_set"].update(clues.tolist())

                            wls_tgt = wls[clues]
                            denom = max(tgt.lmax - tgt.lmin, 1e-9)
                            slope = (tgt.tmax - tgt.tmin) / denom
                            tgt_vals_oblique = tgt.tmin + slope * (wls_tgt - tgt.lmin)
                            config_groups[key]["targets"].append(
                                {
                                    "clues": clues,
                                    "tgt_vals": tgt_vals_oblique,
                                    "target_type": tgt.target_type,
                                    "weight": tgt.w,
                                }
                            )

                        oblique_configs = []
                        for (angle, pol), group in config_groups.items():
                            all_clues = np.array(sorted(group["clues_set"]), dtype=np.int64)
                            idx_to_local = {idx: i for i, idx in enumerate(all_clues)}
                            oblique_configs.append(
                                {
                                    "angle": angle,
                                    "pol": pol,
                                    "all_clues": all_clues,
                                    "wls_config": wls[all_clues],
                                    "n_sub_config": n_sub[all_clues],
                                    "n_layers_T_config": n_layers_T[all_clues, :],
                                    "idx_to_local": idx_to_local,
                                    "targets": group["targets"],
                                }
                            )

                        for config in oblique_configs:
                            idx_to_local = config["idx_to_local"]
                            for tgt_data in config["targets"]:
                                tgt_data["local_positions"] = np.array(
                                    [idx_to_local[i] for i in tgt_data["clues"]],
                                    dtype=np.int64,
                                )

                    logging.info(f"Tikhonravov: Grid upgraded successfully to {len(wls)} points")

        except NUMERICAL_FAULT_EXCEPTIONS as tikhon_err:
            logging.warning(f"Tikhonravov grid update failed, using original grid: {tikhon_err}")

        return wls, n_sub, n_layers_T, n_back_T, tgt_vals, tgt_weights

    def _build_pglobal_config(self, *, mode: str, dim: int, conv_tol: float) -> tuple[PGlobalConfig, int]:
        """Build PGlobal configuration and max iteration budget from mode and dimensions."""
        return build_pglobal_config_from_cfg(
            cfg=self.cfg,
            mode=mode,
            dim=dim,
            conv_tol=conv_tol,
        )

    def _initialize_runtime_state_for_optimization(
        self,
        *,
        has_back_calc: bool,
        has_back_stack: bool,
        d_back: float,
        n_back_T: np.ndarray,
        var_idx: list[int],
        ep0: np.ndarray,
        wls: np.ndarray,
        tgt_vals,
        tgt_weights,
        n_layers_T: np.ndarray,
        n_sub: np.ndarray,
        oblique_mode: bool,
        oblique_configs,
        display_oblique_keys,
        oblique_tgts,
        n_lay_T_disp: np.ndarray,
        n_sub_disp: np.ndarray,
        n_back_T_disp: np.ndarray,
    ) -> None:
        """Store run-time state on ``self`` and perform fixed-layer sanity checks once."""
        all_variable = len(var_idx) == len(ep0)

        self._has_back_calc = has_back_calc
        self._has_back_stack = has_back_stack
        self._d_back = d_back
        self._n_back_T = n_back_T
        self._var_idx = var_idx
        self._ep0 = ep0
        self._wls = wls
        self._tgt_vals = tgt_vals
        self._tgt_weights = tgt_weights
        self._n_layers_T = n_layers_T
        self._n_sub = n_sub
        self._oblique_mode = oblique_mode
        if oblique_configs is not None:
            self._oblique_configs = oblique_configs
        if display_oblique_keys is not None:
            self._display_oblique_keys = display_oblique_keys
        if oblique_tgts is not None:
            self._oblique_tgts = oblique_tgts
        self._n_lay_T_disp = n_lay_T_disp
        self._n_sub_disp = n_sub_disp
        self._n_back_T_disp = n_back_T_disp
        self._all_variable = all_variable

        # Pre-allocated buffer for objective/gradient (avoids 50K+ .copy() per run)
        self._ep_buffer = np.array(ep0, dtype=np.float64, copy=True)

        # Pre-check fixed layers once (they never change) — vectorized
        if not all_variable:
            min_thick = CFG.MIN_THICKNESS
            fixed_mask = np.ones(len(ep0), dtype=bool)
            fixed_mask[var_idx] = False
            if np.any((ep0[fixed_mask] > 1e-12) & (ep0[fixed_mask] < min_thick)):
                logging.warning("Fixed layer violates MIN_THICKNESS")

        self.cost_func = self._objective_wrapper
        # Store cost function for MC calculations when optim_worker is not available
        self._last_cost_func = self._objective_wrapper

    def _prepare_optimizer_entry(
        self,
        *,
        ep0: np.ndarray,
        var_idx: list[int],
        mode: str,
        gradient_func_to_use,
    ) -> tuple:
        """Prepare entry point objects for PGlobal (x0, objective, callback, oblique helpers)."""
        x0_start = ep0[var_idx].copy()
        objective_wrapper = self._objective_wrapper
        callback = self._optimization_callback
        compute_oblique_error = self._compute_oblique_error
        compute_oblique_error_and_grad_analytic = self._compute_oblique_error_and_grad_analytic

        # PRE-POLISH: Local gradient descent before Global search
        if self.cfg.get("pre_polish") and len(var_idx) > 0 and mode == "global":
            x0_start = self._run_pre_polish(
                x0_start,
                var_idx,
                gradient_func_to_use,
                objective_wrapper,
            )

        return (
            x0_start,
            objective_wrapper,
            callback,
            compute_oblique_error,
            compute_oblique_error_and_grad_analytic,
        )

    def _abort_if_no_variable_layers(self, var_idx: list[int]) -> bool:
        """Emit an error and return True when no variable layer is available."""
        if len(var_idx) == 0:
            self.signals.error.emit("No variable layers")
            return True
        return False

    def _emit_best_if_stopped(self) -> bool:
        """Emit best-so-far solution and return True when stop event is raised."""
        if self._stop_event.is_set() and hasattr(self, "best_ep_final") and self.best_ep_final is not None:
            self.signals.finished.emit({"ok": True, "ep": self.best_ep_final, "rmse": self.best_rmse_final})
            return True
        return False

    def _prepare_pglobal_inputs(self, *, var_idx: list[int], mode: str) -> tuple:
        """Build PGlobal preamble objects and emit initial progress line."""
        from certus_design_worker_utils import prepare_pglobal_inputs_from_state

        return prepare_pglobal_inputs_from_state(
            var_idx=var_idx,
            mode=mode,
            cfg=self.cfg,
            signal_emit=self.signals.progress.emit,
            gradient_func=self._gradient_func_pglobal,
        )

    def run(self) -> None:
        """

        Execute the optimization worker thread.

        This method runs the complete optimization workflow including:

        - Spectral evaluation

        - Local and global optimization

        - Target calculationations

        - Result processing

        Args:

            self: OptimWorker instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling

            - Emits progress signals during execution

        """

        try:
            mats = self.cfg["mats"]

            stack = self.cfg["stack"]

            float_dtype = get_float_dtype()

            complex_dtype = get_complex_dtype()

            ep0 = ensure_numpy_array(self.cfg["ep0"], dtype=float_dtype)

            wls = self.cfg["wls"]

            tgts = self.cfg["tgts"]

            l0 = self.cfg["l0"]

            mode = self.cfg.get("mode", "global")

            ep_back = ensure_numpy_array(self.cfg.get("ep_back", []), dtype=float_dtype)

            has_back_stack, has_back_calc, stack_back = optim_backside_flags_from_cfg(self.cfg)

            mats_nk, n_sub, n_layers_T, n_back_T, d_back = optim_prepare_stack_nk_back(
                mats,
                stack,
                wls,
                stack_back=stack_back,
                ep_back=ep_back,
                has_back_stack=has_back_stack,
                complex_dtype=complex_dtype,
                float_dtype=float_dtype,
            )

            # Mode oblique

            oblique_mode = self.cfg.get("oblique_mode", False)

            oblique_tgts = self.cfg.get("oblique_tgts", [])

            if oblique_mode and has_back_calc and has_back_stack:
                logging.info("[OPTIM] Oblique+backside with back coating: using full oblique exact kernel.")

            elif oblique_mode and has_back_calc:
                logging.info("[OPTIM] Oblique+backside (bare substrate): using oblique backside kernel.")

            # Target preparation

            if oblique_mode:
                valid_targets = [tgt for tgt in oblique_tgts if tgt.valid()]

                display_oblique_keys = optim_oblique_unique_display_keys(valid_targets)

                config_groups = optim_oblique_group_targets_on_wavelengths(wls, valid_targets)

                oblique_configs = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T)

                optim_oblique_attach_local_positions(oblique_configs)

                # Precompute spectral quadrature once per oblique config.

                for config in oblique_configs:
                    config["sw_cfg"] = spectral_rmse_weights(np.asarray(config["wls_config"], dtype=np.float64))

                tgt_vals = None

                tgt_weights = None

                # Oblique error helper (precomputed pos)

            else:
                self._compute_oblique_error = None

                self._compute_oblique_error_and_grad_analytic = None

                tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)

                display_oblique_keys = []

            # Variable clues

            var_idx = optim_var_indices_from_stack(stack)

            if self._abort_if_no_variable_layers(var_idx):
                return

            # Bounds configuration

            float_dtype = get_float_dtype()

            if mode == "local":
                delta_nm = self.cfg.get("local_delta_nm", 2.0)

                bounds = optim_bounds_thickness_local(ep0, var_idx, delta_nm, float_dtype=float_dtype)

            elif mode == "healing":
                bounds = optim_bounds_thickness_healing(ep0, var_idx, stack, mats, l0, float_dtype=float_dtype)

            else:
                bounds = optim_bounds_thickness_global(ep0, var_idx, stack, mats, l0, float_dtype=float_dtype)

            # Preparation for realtime display (same core as main stack)

            complex_dtype = get_complex_dtype()

            _mats_disp, n_sub_disp, n_lay_T_disp, n_back_T_disp, _d_back_disp = optim_prepare_stack_nk_back(
                mats,
                stack,
                self._wls_display,
                stack_back=stack_back,
                ep_back=ep_back,
                has_back_stack=has_back_stack,
                complex_dtype=complex_dtype,
                float_dtype=float_dtype,
            )

            self._initialize_runtime_state_for_optimization(
                has_back_calc=has_back_calc,
                has_back_stack=has_back_stack,
                d_back=d_back,
                n_back_T=n_back_T,
                var_idx=var_idx,
                ep0=ep0,
                wls=wls,
                tgt_vals=tgt_vals,
                tgt_weights=tgt_weights,
                n_layers_T=n_layers_T,
                n_sub=n_sub,
                oblique_mode=oblique_mode,
                oblique_configs=oblique_configs if oblique_mode else None,
                display_oblique_keys=display_oblique_keys,
                oblique_tgts=oblique_tgts,
                n_lay_T_disp=n_lay_T_disp,
                n_sub_disp=n_sub_disp,
                n_back_T_disp=n_back_T_disp,
            )

            # Analytic gradient and PGLOBAL configuration
            dim, gradient_func_to_use, pg_conf, max_iter_run = self._prepare_pglobal_inputs(
                var_idx=var_idx,
                mode=mode,
            )

            (
                x0_start,
                objective_wrapper,
                callback,
                compute_oblique_error,
                compute_oblique_error_and_grad_analytic,
            ) = self._prepare_optimizer_entry(
                ep0=ep0,
                var_idx=var_idx,
                mode=mode,
                gradient_func_to_use=gradient_func_to_use,
            )

            # Use analytic gradient with LBFGSBSearcher (via scipy jac)

            optimizer, opt_start_time = self._run_pglobal_setup(
                mode,
                max_iter_run,
                dim,
                objective_wrapper,
                bounds,
                pg_conf,
                x0_start,
                gradient_func_to_use,
            )

            best_sample_overall = run_pglobal_restart_loop(
                mode=mode,
                optimizer=optimizer,
                objective_wrapper=objective_wrapper,
                bounds=bounds,
                pg_conf=pg_conf,
                gradient_func_to_use=gradient_func_to_use,
                max_iter_run=max_iter_run,
                callback=callback,
                opt_start_time=opt_start_time,
                stop_event=self._stop_event,
                progress_emit=self.signals.progress.emit,
                cfg=self.cfg,
                callback_counter_getter=lambda: self._callback_counter,
                set_optimizer=lambda opt: setattr(self, "_optimizer", opt),
            )

            # If stopped, save best solution found so far
            if self._emit_best_if_stopped():
                return

            if best_sample_overall:
                ep_current = ep0.copy()

                ep_current[var_idx] = best_sample_overall.x

                best_cost = best_sample_overall.y

                # === Phase final: Coord Descent (5 cycles) ===

                # DYNAMIC GRID UPDATE: Apply Tikhonravov criterion before refinement
                from certus_design_worker_utils import maybe_upgrade_grid_tikhonravov

                wls, n_sub, n_layers_T, n_back_T, tgt_vals, tgt_weights = maybe_upgrade_grid_tikhonravov(
                    ep_current=ep_current,
                    mats=mats,
                    stack=stack,
                    tgts=tgts,
                    oblique_mode=oblique_mode,
                    oblique_tgts=oblique_tgts,
                    wls=wls,
                    float_dtype=float_dtype,
                    complex_dtype=complex_dtype,
                    has_back_stack=has_back_stack,
                    stack_back=stack_back,
                    ep_back=ep_back,
                    n_sub=n_sub,
                    n_layers_T=n_layers_T,
                    n_back_T=n_back_T,
                    tgt_vals=tgt_vals,
                    tgt_weights=tgt_weights,
                )

                self.signals.progress.emit(95, "Final refinement (5x coordinate descent)...")
                ep_current, best_cost, self.best_rmse_seen = run_coord_descent_5cycles(
                    ep_current=ep_current,
                    best_cost=best_cost,
                    var_idx=var_idx,
                    oblique_mode=oblique_mode,
                    compute_oblique_error=compute_oblique_error,
                    compute_oblique_error_and_grad_analytic=compute_oblique_error_and_grad_analytic,
                    n_layers_T=n_layers_T,
                    n_sub=n_sub,
                    wls=wls,
                    tgt_vals=tgt_vals,
                    tgt_weights=tgt_weights,
                    has_back_calc=has_back_calc,
                    n_back_T=n_back_T,
                    d_back=d_back,
                    cfg=self.cfg,
                    evaluate_thicknesses=self._evaluate_thicknesses,
                    get_gradient_analytic=self._get_gradient_analytic,
                    progress_emit=self.signals.progress.emit,
                    best_rmse_seen=self.best_rmse_seen,
                )

                self._finalize_and_emit_optimization_result(ep_current, best_cost)

            else:
                self.signals.finished.emit(OptimWorkerResult.failure().to_legacy_dict())

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Optimization worker error: {e}")

            self.signals.error.emit(traceback.format_exc())

class ColorWorker(QThread):
    """Worker for Monte Carlo color analysis"""

    def __init__(self, cfg: dict[str, Any] | ColorWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, ColorWorkerRequest) else ColorWorkerRequest.from_legacy(cfg)

        # Keep legacy mutable cfg field for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

    def _compute_oblique_error(self, ep_test) -> Any:
        return _design_compute_oblique_error_common(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return _design_compute_oblique_error_and_grad_analytic_common(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return _design_objective_wrapper_common(self, x)

    def _gradient_func_pglobal(self, x) -> Any:

        return _design_gradient_func_pglobal_common(self, x)

    def _optimization_callback(self, sample) -> Any:
        return _design_optimization_callback_common(self, sample)

    def run(self) -> None:

        try:
            float_dtype = get_float_dtype()

            complex_dtype = get_complex_dtype()

            stack = self.cfg["stack"]

            ep0 = np.array(self.cfg["ep"], dtype=float_dtype)

            mats = self.cfg["mats"]

            n_samples = self.cfg["n"]

            sigma = self.cfg["sigma"]
            rng_seed = int(self.cfg.get("run_seed", 0))
            rng = np.random.default_rng(rng_seed)

            wls = np.linspace(380, 780, 81).astype(float_dtype)

            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

            n_layers = np.array([mats_nk[l.mat] for l in stack], dtype=complex_dtype)

            n_layers_T = np.ascontiguousarray(n_layers.T)

            _sub_key_c = "substrate" if "substrate" in mats_nk else "Substrate"

            n_sub = np.ascontiguousarray(mats_nk[_sub_key_c])

            # Nominal spectrum

            _, Rs_nom = calc_spectrum_front(wls, n_layers_T, ep0, n_sub)

            xyz_nom = xyz_from_spectrum(wls, Rs_nom)

            lab_nom = xyz_to_lab(xyz_nom)

            # Monte Carlo - pre-allocate array to avoid repeated appends

            labs = np.empty((n_samples, 3), dtype=np.float64)

            for i in range(n_samples):
                ep_perturbed = ep0 + rng.normal(0, sigma, len(ep0))

                ep_perturbed = np.maximum(ep_perturbed, 0.0)

                _, Rs = calc_spectrum_front(wls, n_layers_T, ep_perturbed, n_sub)

                labs[i] = xyz_to_lab(xyz_from_spectrum(wls, Rs))

            result_payload = ColorWorkerResult.success(lab_nom=lab_nom, labs=labs)
            self.signals.finished.emit(result_payload.to_legacy_dict())

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Color optimization worker error: {e}")

            self.signals.error.emit(traceback.format_exc())

class NeedleWorker(QThread):
    """Worker for layer insertion (Needle algorithm)"""

    def __init__(self, cfg: dict[str, Any] | NeedleWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, NeedleWorkerRequest) else NeedleWorkerRequest.from_legacy(cfg)

        # Keep legacy mutable cfg field for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

    def _compute_oblique_error(self, ep_test) -> Any:
        return _design_compute_oblique_error_common(self, ep_test)

    def _compute_oblique_error_and_grad_analytic(self, ep_test) -> Any:
        return _design_compute_oblique_error_and_grad_analytic_common(self, ep_test)

    def _objective_wrapper(self, x) -> Any:
        return _design_objective_wrapper_common(self, x)

    def _gradient_func_pglobal(self, x) -> Any:

        return _design_gradient_func_pglobal_common(self, x)

    def _optimization_callback(self, sample) -> Any:
        return _design_optimization_callback_common(self, sample)

    def run(self) -> Any:

        try:
            float_dtype = get_float_dtype()

            complex_dtype = get_complex_dtype()

            stack = self.cfg.get("stack", [])

            mats = self.cfg.get("mats", {})

            ep_base = np.array(self.cfg.get("ep", []), dtype=float_dtype)

            wls = self.cfg.get("wls", np.array([]))

            tgts = self.cfg.get("tgts", [])

            # MAX LOCK: Check before calculationation

            current_layers = len(stack)

            if current_layers >= CFG.MAX_LAYERS:
                self.signals.finished.emit(NeedleWorkerResult.action_only("max_layers_reached").to_legacy_dict())

                return

            # Oblique mode detection

            oblique_mode = self.cfg.get("oblique_mode", False)

            oblique_tgts = self.cfg.get("oblique_tgts", [])

            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

            _sub_key_n = "substrate" if "substrate" in mats_nk else "Substrate"

            n_sub = np.ascontiguousarray(mats_nk[_sub_key_n])

            has_back = self.cfg.get("has_back", False)

            n_back_T = self.cfg.get("n_back_T")

            d_back = self.cfg.get("d_back")

            if n_back_T is None:
                n_back_T = np.zeros((len(wls), 0), dtype=complex_dtype)

            if d_back is None:
                d_back = np.zeros(0, dtype=float_dtype)

            has_back_stack = (n_back_T.shape[1] > 0) and (len(d_back) > 0)

            n_lay_list = [mats_nk[l.mat] for l in stack]

            if not n_lay_list:
                self.signals.finished.emit(NeedleWorkerResult.action_only("empty_init").to_legacy_dict())

                return

            n_layers_orig = np.array(n_lay_list, dtype=complex_dtype)

            n_layers_T_orig = np.ascontiguousarray(n_layers_orig.T)

            if oblique_mode:
                valid_targets = [tgt for tgt in oblique_tgts if tgt.valid()]

                config_groups = optim_oblique_group_targets_on_wavelengths(wls, valid_targets)

                oblique_configs_needle = optim_oblique_configs_from_groups(config_groups, wls, n_sub, n_layers_T_orig)

                optim_oblique_attach_local_positions(oblique_configs_needle)

                # Helper: oblique error (Optimized)

                def compute_oblique_error_needle(ep_test, n_layers_T_test) -> Any:
                    """Calculate oblique mode error - grouped by (angle, pol)"""

                    total_err = 0.0

                    total_wt = 0.0

                    for config in oblique_configs_needle:
                        # Extract n_layers for this config's wavelengths

                        n_layers_T_config = n_layers_T_test[config["all_clues"], :]

                        # Compute R & T ONCE for this (angle, pol)

                        R_config, T_config = optim_calc_oblique_selected(
                            config["wls_config"],
                            n_layers_T_config,
                            ep_test,
                            config["n_sub_config"],
                            config["angle"],
                            config["pol"],
                            has_back_calc=has_back,
                            has_back_stack=has_back_stack,
                            d_back=d_back,
                            n_back_T=n_back_T,
                            calc_spectrum_full_oblique_exact=calc_spectrum_full_oblique_exact,
                            calc_spectrum_oblique_backside_vectorized=calc_spectrum_oblique_backside_vectorized,
                            calc_spectrum_oblique_vectorized=calc_spectrum_oblique_vectorized,
                        )

                        # Extract values for each target using precomputed positions

                        _sw_cfg = spectral_rmse_weights(np.asarray(config["wls_config"], dtype=np.float64))

                        for tgt_data in config["targets"]:
                            local_positions = tgt_data["local_positions"]

                            if tgt_data["target_type"] == "R":
                                vals = R_config[local_positions]

                            else:
                                vals = T_config[local_positions]

                            diff = vals - tgt_data["tgt_vals"]

                            _sw = _sw_cfg[local_positions]

                            err = np.sum(_sw * diff * diff) * tgt_data["weight"]

                            total_err += err

                            total_wt += tgt_data["weight"] * np.sum(_sw)

                    if total_wt < 1e-12:
                        return 1e30

                    return total_err / total_wt

            else:
                # Normal mode

                tgt_vals, tgt_weights = prepare_targets_vectorized(wls, tgts)

            STEP_NM = 2.0

            PROBE_THICKNESS = 0.01

            best_res = None

            # Build per-layer needle material info (needed by both paths)

            N = len(stack)

            needle_mat_names, scan_mask = self._build_needle_scan_mask(stack, mats_nk)

            # ── LOCKED ── Validated by test_needle_cached.py (8/8) ──

            # Fast path: cached kernel (normal mode, no backside)

            # DO NOT modify the cached/fallback logic without re-running test_needle_cached.py.

            use_cached = (not oblique_mode) and (not has_back)

            if use_cached:
                best_res = self._run_needle_cached_scan(
                    N=N,
                    scan_mask=scan_mask,
                    needle_mat_names=needle_mat_names,
                    mats_nk=mats_nk,
                    complex_dtype=complex_dtype,
                    wls=wls,
                    n_layers_T_orig=n_layers_T_orig,
                    n_sub=n_sub,
                    ep_base=ep_base,
                    tgt_vals=tgt_vals,
                    tgt_weights=tgt_weights,
                    STEP_NM=STEP_NM,
                    PROBE_THICKNESS=PROBE_THICKNESS,
                    has_back=has_back,
                    n_back_T=n_back_T,
                    d_back=d_back,
                    float_dtype=float_dtype,
                )

            else:
                best_res = self._run_needle_fallback_scan(
                    stack=stack,
                    ep_base=ep_base,
                    n_layers_T_orig=n_layers_T_orig,
                    needle_mat_names=needle_mat_names,
                    mats_nk=mats_nk,
                    float_dtype=float_dtype,
                    wls=wls,
                    oblique_mode=oblique_mode,
                    compute_oblique_error_needle=compute_oblique_error_needle if oblique_mode else None,
                    n_sub=n_sub,
                    tgt_vals=tgt_vals if not oblique_mode else None,
                    tgt_weights=tgt_weights if not oblique_mode else None,
                    has_back=has_back,
                    n_back_T=n_back_T,
                    d_back=d_back,
                    STEP_NM=STEP_NM,
                    PROBE_THICKNESS=PROBE_THICKNESS,
                )

            result_payload = NeedleWorkerResult.from_legacy(best_res)
            self.signals.finished.emit(result_payload.to_legacy_dict())

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Needle optimization worker error: {e}")

            self.signals.error.emit(traceback.format_exc())

    def _run_needle_cached_scan(
        self,
        *,
        N: int,
        scan_mask: np.ndarray,
        needle_mat_names: list[str],
        mats_nk: dict,
        complex_dtype,
        wls: np.ndarray,
        n_layers_T_orig: np.ndarray,
        n_sub: np.ndarray,
        ep_base: np.ndarray,
        tgt_vals: np.ndarray,
        tgt_weights: np.ndarray,
        STEP_NM: float,
        PROBE_THICKNESS: float,
        has_back: bool,
        n_back_T: np.ndarray,
        d_back: np.ndarray,
        float_dtype,
    ) -> dict[str, Any] | None:
        """Run cached needle scan path (normal mode, no backside)."""

        # Pre-allocate zero array; fill only masked positions
        n_needle_arr = np.zeros((N, len(wls)), dtype=complex_dtype)
        for i in range(N):
            if scan_mask[i]:
                n_needle_arr[i] = mats_nk[needle_mat_names[i]]

        n_needle_T = np.ascontiguousarray(n_needle_arr.T)

        best_layer, best_depth, best_cost = needle_scan_cached(
            wls,
            n_layers_T_orig,
            n_needle_T,
            n_sub,
            ep_base,
            tgt_vals,
            tgt_weights,
            STEP_NM,
            PROBE_THICKNESS,
            scan_mask,
        )

        if best_layer < 0:
            return None

        i = int(best_layer)
        d_layer = float(ep_base[i])
        needle_mat = needle_mat_names[i]
        if d_layer > (STEP_NM + 0.1) and needle_mat:
            n_needle_col = mats_nk[needle_mat].reshape(-1, 1)
            n_current_col = n_layers_T_orig[:, i : i + 1]
            mat_left = n_layers_T_orig[:, :i]
            mat_right = n_layers_T_orig[:, i + 1 :]
            n_test_T = np.hstack(
                [
                    mat_left,
                    n_current_col,
                    n_needle_col,
                    n_current_col,
                    mat_right,
                ]
            )
            n_test_T = np.ascontiguousarray(n_test_T)
            n_base = len(ep_base)
            ep_test = np.empty(n_base + 2, dtype=float_dtype)
            ep_test[:i] = ep_base[:i]
            ep_test[i + 3 :] = ep_base[i + 1 :]
            ep_test[i + 1] = PROBE_THICKNESS
            refine_step = 0.5
            z_min = max(STEP_NM, float(best_depth) - STEP_NM)
            z_max = min(d_layer - 0.1, float(best_depth) + STEP_NM)
            if z_max > z_min:
                for z in np.arange(z_min, z_max + 0.5 * refine_step, refine_step):
                    d_left = float(z)
                    d_right = d_layer - d_left
                    ep_test[i] = d_left
                    ep_test[i + 2] = d_right
                    c_refined = cost_numba_fast(
                        ep_test,
                        n_test_T,
                        n_sub,
                        wls,
                        tgt_vals,
                        tgt_weights,
                        0.0,
                        has_back,
                        n_back_T,
                        d_back,
                    )
                    if c_refined < best_cost:
                        best_cost = float(c_refined)
                        best_depth = float(d_left)

        return {
            "action": "split",
            "layer_idx": int(best_layer),
            "depth": float(best_depth),
            "needle_mat": needle_mat_names[int(best_layer)],
            "cost": float(best_cost),
        }

    def _build_needle_scan_mask(self, stack: list, mats_nk: dict) -> tuple[list[str], np.ndarray]:
        """Build per-layer candidate needle material names and scan mask."""

        excluded_layers = set(self.cfg.get("excluded_layers", []))
        needle_mat_names = []
        scan_mask = []

        for idx, layer in enumerate(stack):
            mat_name = getattr(layer, "mat", None)
            if mat_name is None:
                mat_name = layer["mat"] if isinstance(layer, dict) and "mat" in layer else None
            if mat_name is None:
                continue
            needle_mat_names.append(str(mat_name))
            scan_mask.append(idx not in excluded_layers and str(mat_name) in mats_nk)

        return needle_mat_names, np.asarray(scan_mask, dtype=bool)

    def _run_needle_fallback_scan(
        self,
        *,
        stack: list,
        ep_base: np.ndarray,
        n_layers_T_orig: np.ndarray,
        needle_mat_names: list[str],
        mats_nk: dict,
        float_dtype,
        wls: np.ndarray,
        oblique_mode: bool,
        compute_oblique_error_needle,
        n_sub: np.ndarray,
        tgt_vals,
        tgt_weights,
        has_back: bool,
        n_back_T: np.ndarray,
        d_back: np.ndarray,
        STEP_NM: float,
        PROBE_THICKNESS: float,
    ) -> dict[str, Any] | None:
        """Run fallback per-position needle scan (oblique/backside compatible)."""

        best_res = None
        min_cost = float("inf")
        for i, layer in enumerate(stack):
            if self.isInterruptionRequested():
                return best_res
            d_layer = ep_base[i]
            if d_layer < (STEP_NM + 0.1):
                continue
            needle_mat = needle_mat_names[i]
            if not needle_mat:
                continue
            n_needle_col = mats_nk[needle_mat].reshape(-1, 1)
            n_current_col = n_layers_T_orig[:, i : i + 1]
            mat_left = n_layers_T_orig[:, :i]
            mat_right = n_layers_T_orig[:, i + 1 :]
            n_test_T = np.hstack(
                [
                    mat_left,
                    n_current_col,
                    n_needle_col,
                    n_current_col,
                    mat_right,
                ]
            )
            n_test_T = np.ascontiguousarray(n_test_T)
            z_positions = np.arange(STEP_NM, d_layer - 0.1, STEP_NM)
            n_base = len(ep_base)
            ep_test = np.empty(n_base + 2, dtype=float_dtype)
            ep_test[:i] = ep_base[:i]
            ep_test[i + 3 :] = ep_base[i + 1 :]
            ep_test[i + 1] = PROBE_THICKNESS
            for z in z_positions:
                d_left = z
                d_right = d_layer - z
                ep_test[i] = d_left
                ep_test[i + 2] = d_right
                if oblique_mode:
                    c = compute_oblique_error_needle(ep_test, n_test_T)
                else:
                    c = cost_numba_fast(
                        ep_test,
                        n_test_T,
                        n_sub,
                        wls,
                        tgt_vals,
                        tgt_weights,
                        0.0,
                        has_back,
                        n_back_T,
                        d_back,
                    )
                if c < min_cost:
                    min_cost = c
                    best_res = {
                        "action": "split",
                        "layer_idx": i,
                        "depth": z,
                        "needle_mat": needle_mat,
                        "cost": min_cost,
                    }
        return best_res

# =========================================================================================

# [MONOLITHIC BLOCK] GUI CLASSES

# DO NOT SPLIT - High coupling required for event handling and widget management

# =========================================================================================

# =============================================================================

# MAIN APPLICATION

# =============================================================================

class CertusDesignApp(CertusBaseApp):
    """Main Application CERTUS-DESIGN"""

    optimization_finished_signal = pyqtSignal()

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-DESIGN"

    APP_TITLE = "Optical Filter Design & Optimization"

    DEFAULT_WIDTH = 1380

    DEFAULT_HEIGHT = 600

    MIN_WIDTH = 1000

    MIN_HEIGHT = 500

    def __init__(self) -> None:
        """

        Initialize the CERTUS-DESIGN application.

        This method sets up the main application including:

        - Logger configuration and setup

        - Design-specific state initialization

        - Worker threads and state management

        - UI construction and theme application

        - JIT compilation warmup

        Args:

            self: CertusDesignApp instance

        Returns:

            None

        Notes:

            - Inherits from CertusBaseApp

            - Sets up design-specific widgets and workers

            - Initializes optimization and evaluation workers

            - Applies CERTUS theme and builds UI

            - Starts JIT warmup process

        """

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # DESIGN-specific state

        self.mat_widgets: dict[str, dict[str, Any]] = {}

        self.target_widgets: List = []

        self.ep_current: np.ndarray | None = None

        self.ep_back_current: np.ndarray | None = None

        self.last_result: Dict = {}

        self._best_eval_result: Dict | None = None

        self._best_eval_rmse: float = float("inf")

        self.target_scatter = None

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        self.detached_window = None

        self.eval_timer = None

        self._current_eval_generation = 0

        default_max_layers: int = int(getattr(CFG, "MAX_LAYERS", 50))
        self._original_target_count = default_max_layers

        self._target_layer_count = default_max_layers
        # Keep the configured target count until workflow logic explicitly updates it.

        self._overshoot_active = False

        self._overshoot_done = False

        # Oblique mode

        self.oblique_mode = False

        self.oblique_targets: list[ObliqueTarget] = []

        # Workers

        self.optim_worker: OptimWorker | None = None

        self.eval_worker: EvalWorker | None = None

        self.col_worker: ColorWorker | None = None

        self.needle_worker: NeedleWorker | None = None

        self.warmup_worker: WarmupWorker | None = None

        # Needle State

        # Keep the configured target count until workflow logic explicitly updates it.
        self._is_internal_restart = False

        self._topology_stable = True

        # Statistics (override base)

        self.stat_counters = {"EVAL": 0, "BEST": 0, "MINIMA": 0}

        self.accumulated_evals = 0

        self._warmup_done = False

        self._needle_recent_best_rmse = float("inf")

        self._needle_no_improve_rounds = 0

        # Balanced preset: favor good RMSE without excessive topology churn/time.

        self._needle_success_rel_threshold = 0.008

        self._needle_success_abs_floor = 3e-5

        self._needle_gate_no_improve_rounds = 3

        self._needle_pred_gain_rel_threshold = 0.003

        self._needle_pred_gain_abs_threshold = 2e-5

        self.pareto_history = {}  # N -> dict(rmse, mc_rmse, ep, table_state)

        # Theme Application

        CertusTheme.apply_to_app(QApplication.instance())

        # UI Construction

        self._build_ui()

        self._setup_shortcuts()

        self._load_defaults()

        # Warmup JIT (DESIGN uses its own WarmupWorker)

        self.status_label.setText("Compiling JIT kernels…")

        self.warmup_worker = WarmupWorker()

        self.warmup_worker.finished.connect(self._on_warmup_done)

        self.warmup_worker.start()

    # =========================================================================

    # UI CONSTRUCTION

    # =========================================================================

    def _get_default_splitter_sizes(self) -> list[int]:
        """DESIGN specific splitter sizes."""

        return [450, 1150]

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Provides substrate-specific info for DESIGN."""

        substrate_type = "Custom"

        substrate_index = "N/A"

        if hasattr(self, "mat_widgets") and "Substrate" in self.mat_widgets:
            w = self.mat_widgets["Substrate"]

            substrate_type = w["preset"].currentText()

            n4 = w["n4"].value()

            n7 = w["n7"].value()

            substrate_index = f"n@400={n4:.3f}, n@700={n7:.3f}"

        return substrate_type, substrate_index

    def _build_left_panel(self) -> QWidget:
        """Constructs left control panel"""

        left_panel = QWidget()

        left_panel.setMinimumWidth(280)

        # Removed setFixedWidth to allow resizing via splitter

        left_panel.setObjectName("LeftPanel")

        left_layout = QVBoxLayout(left_panel)

        left_layout.setSpacing(0)

        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Standard Header

        header_widget = create_header_logo_widget(
            "DESIGN",
            self.APP_TITLE,
            logo_width=180,
            module_name="CERTUS_DESIGN",
        )

        self.btn_theme = CertusThemeToggle(header_widget)

        header_widget.layout().addWidget(self.btn_theme)

        left_layout.addWidget(header_widget)

        # 2. Action Bar (Shared)

        action_bar = create_top_actions_bar(self, self.save_config, self.load_config, self.export_excel, self.open_help)

        left_layout.addWidget(action_bar)

        # Scrollable area

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()

        scroll_layout = QVBoxLayout(scroll_content)

        scroll_layout.setContentsMargins(0, 0, 4, 0)

        scroll_layout.setSpacing(8)

        workflow_card = CertusCard("Workflow")

        workflow_hint = QLabel("1 Configure materials  2 Define stack  3 Set optimizer  4 Evaluate / Run")

        workflow_hint.setWordWrap(True)

        workflow_hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 10px;")

        workflow_card.body.addWidget(workflow_hint)

        scroll_layout.addWidget(workflow_card)

        self.back_group = self._build_back_group()

        materials_widget = self._build_materials_group()

        params_widget = self._build_params_group()

        optim_widget = self._build_optim_group()

        scroll_layout.addWidget(CertusCollapsible("1  Materials", materials_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("2  Back-side structure", self.back_group, expanded=False))

        scroll_layout.addWidget(CertusCollapsible("3  Parameters", params_widget, expanded=True))

        scroll_layout.addWidget(CertusCollapsible("4  Optimization", optim_widget, expanded=True))

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        left_layout.addWidget(scroll)

        # Action buttons

        action_layout = self._build_action_buttons()

        # Add layout to a container first to apply margins if needed,

        # but action_buttons typically has its own margins.

        # Check action_buttons implementation if it returns a Layout or Widget.

        # It returns a layout. We need to wrap it in a widget or add layout.

        # In QLayout.addLayout, it adds to the layout.

        # Wrapper for bottom actions to add padding

        bottom_actions_widget = CertusCard("Actions")

        bottom_actions_widget.body.setContentsMargins(10, 8, 10, 10)

        bottom_actions_widget.body.addLayout(action_layout)

        left_layout.addWidget(bottom_actions_widget)

        self.back_group.setVisible(self.back_coat_check.isChecked())

        return left_panel

    def _apply_theme(self) -> None:
        """Apply Certus theme dynamically"""

        self._apply_certus_compact_theme(
            plots=[
                getattr(self, "spectrum_plot", None),
                getattr(self, "profile_plot", None),
                getattr(self, "nk_plot", None),
                getattr(self, "color_plot", None),
                getattr(self, "plot_convergence", None),
            ]
        )

    def _build_materials_group(self) -> CertusCard:
        """Constructs materials group"""

        mat_group = CertusCard("Materials")

        mat_grid = QGridLayout()

        mat_group.body.addLayout(mat_grid)

        headers = ["Material", "Preset", "n@400", "n@700"]

        for col, header in enumerate(headers):
            mat_grid.addWidget(QLabel(f"<b>{header}</b>"), 0, col)

        materials = list(CFG.MATERIALS)

        for i, mat_name in enumerate(materials):
            row = i + 1

            mat_grid.addWidget(QLabel(f"<b>{mat_name}</b>"), row, 0)

            combo = QComboBox()

            combo.setToolTip("Select the material preset or 'Custom'.")

            combo.addItems(CAUCHY_PRESETS.keys())

            combo.setCurrentText("Custom")

            n4_spin = self._create_spin(1.5, dec=3)

            n7_spin = self._create_spin(1.5, dec=3)

            for spin in [n4_spin, n7_spin]:
                spin.setRange(1.0, 4.0)

                spin.valueChanged.connect(self._on_schedule_eval_signal)

                spin.valueChanged.connect(self._on_tikhonravov_points_changed)

            combo.currentTextChanged.connect(lambda t, s4=n4_spin, s7=n7_spin: self._apply_preset(t, s4, s7))

            mat_grid.addWidget(combo, row, 1)

            mat_grid.addWidget(n4_spin, row, 2)

            mat_grid.addWidget(n7_spin, row, 3)

            self.mat_widgets[mat_name] = {"preset": combo, "n4": n4_spin, "n7": n7_spin}

            # Initialize spinbox states based on default preset

            self._apply_preset(combo.currentText(), n4_spin, n7_spin)

        return mat_group

    def _build_params_group(self) -> CertusCard:
        """Constructs parameters group"""

        param_group = CertusCard("Parameters")

        param_layout = param_group.body

        # Reference Lambda

        l0_lay = QHBoxLayout()

        self.l0_spin = QDoubleSpinBox()

        self.l0_spin.setRange(200, 20000)

        self.l0_spin.setValue(CFG.DEFAULT_L0)

        self.l0_spin.setDecimals(1)

        self.l0_spin.setSuffix(" nm")

        self.l0_spin.valueChanged.connect(self._on_schedule_eval_signal)

        self.l0_spin.valueChanged.connect(self._on_tikhonravov_points_changed)

        self.l0_spin.setToolTip("Reference wavelength lambda₀ (nm) for converting QWOT to physical thickness.")

        l0_lay.addWidget(QLabel("lambda₀ ref.:"))

        l0_lay.addWidget(self.l0_spin)

        param_layout.addLayout(l0_lay)

        # Backside options

        self.back_check = QCheckBox("substrate back face (Fresnel)")

        self.back_check.setToolTip("Include reflection from the untreated back face of the substrate.")

        self.back_check.stateChanged.connect(self._on_schedule_eval_instant_signal)

        param_layout.addWidget(self.back_check)

        self.back_coat_check = QCheckBox("Back-side stack")

        self.back_coat_check.setToolTip(
            "Show the back-side layer editor and include those layers in the calculation when checked."
        )

        self.back_coat_check.stateChanged.connect(self._toggle_back_stack)

        param_layout.addWidget(self.back_coat_check)

        # Oblique Mode

        self.oblique_check = QCheckBox("Oblique incidence mode")

        self.oblique_check.setToolTip("R/T targets with angle and s / p / average polarization per row.")

        self.oblique_check.stateChanged.connect(self._toggle_oblique_mode)

        param_layout.addWidget(self.oblique_check)

        # Auto Y Scale or Fixed (0-1)

        self.auto_scale_y_check = QCheckBox("Auto Y scale")

        self.auto_scale_y_check.setChecked(True)

        self.auto_scale_y_check.setToolTip("Fit the Y axis to the spectrum data on display.")

        self.auto_scale_y_check.stateChanged.connect(self._on_update_spectrum_y_scale_signal)

        param_layout.addWidget(self.auto_scale_y_check)

        # Deep Needle / Layer Growth

        self.allow_growth_check = QCheckBox("Topology growth (deep Needle)")

        self.allow_growth_check.setChecked(True)

        self.allow_growth_check.setToolTip("Allow thin-layer insertion during optimization (Needle mode).")

        param_layout.addWidget(self.allow_growth_check)

        # Pre-Polish

        self.pre_polish_check = QCheckBox("Local polish before PGLOBAL")

        self.pre_polish_check.setChecked(False)

        self.pre_polish_check.setToolTip("Run a local gradient polish before the multi-minima global phase.")

        param_layout.addWidget(self.pre_polish_check)

        return param_group

    def _build_back_group(self) -> CertusCard:
        """Constructs backside group"""

        back_group = CertusCard("Back-side structure")

        back_layout = back_group.body

        self.back_table = QTableWidget(0, 3)

        self.back_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)"])

        self.back_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.back_table.setAlternatingRowColors(True)

        self.back_table.setMaximumHeight(150)

        back_layout.addWidget(self.back_table)

        back_btns = QHBoxLayout()

        b_add = QPushButton("Add")

        b_add.setToolTip("Add a layer to the back-side stack.")

        b_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        b_add.clicked.connect(self.add_back_layer)

        b_del = QPushButton("Remove")

        b_del.setToolTip("Remove a layer from the back-side stack.")

        b_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        b_del.clicked.connect(self.del_back_layer)

        back_btns.addWidget(b_add)

        back_btns.addWidget(b_del)

        back_btns.addStretch()

        back_layout.addLayout(back_btns)

        return back_group

    def _build_optim_group(self) -> CertusCard:
        """Constructs optimization group"""

        opt_group = CertusCard("Optimization (PGLOBAL)")

        opt_grid = QGridLayout()

        opt_group.body.addLayout(opt_grid)

        opt_grid.setSpacing(8)

        row = 0

        # Samples per iteration

        self.n100_spin = QSpinBox()

        self.n100_spin.setRange(50, 500000)

        self.n100_spin.setValue(6000)

        self.n100_spin.setSingleStep(50)

        self.n100_spin.setToolTip(
            "Number of random starting points evaluated per global iteration.\n"
            "Higher values improve exploration but increase computation time."
        )

        opt_grid.addWidget(QLabel("Samples / Iter:"), row, 0)

        opt_grid.addWidget(self.n100_spin, row, 1)

        row += 1

        # Max clusters

        self.max_clusters_spin = QSpinBox()

        self.max_clusters_spin.setRange(5, 2500)

        self.max_clusters_spin.setValue(40)

        self.max_clusters_spin.setToolTip(
            "Maximum number of local minima (clusters) tracked simultaneously.\n"
            "Limits memory usage and ensures the best basins are retained."
        )

        opt_grid.addWidget(QLabel("Max Clusters:"), row, 0)

        opt_grid.addWidget(self.max_clusters_spin, row, 1)

        row += 1

        # Max iterations

        self.global_cycles_spin = QSpinBox()

        self.global_cycles_spin.setRange(1, 2500)

        self.global_cycles_spin.setValue(50)

        self.global_cycles_spin.setToolTip("Maximum number of global optimization cycles before auto-stopping.")

        opt_grid.addWidget(QLabel("Max Iterations:"), row, 0)

        opt_grid.addWidget(self.global_cycles_spin, row, 1)

        row += 1

        # Points per target

        self.points_per_target_spin = QSpinBox()

        self.points_per_target_spin.setRange(1, 5000)

        self.points_per_target_spin.setValue(50)

        self.points_per_target_spin.setToolTip(
            "Number of spectral evaluation points per target region.\n"
            "Higher values increase spectral accuracy but slow down evaluation."
        )

        self.points_per_target_spin.valueChanged.connect(self._update_optim_point_count)

        opt_grid.addWidget(QLabel("Points / Target:"), row, 0)

        opt_grid.addWidget(self.points_per_target_spin, row, 1)

        row += 1

        # Spectrum points (readonly)

        self.npts_spin = QSpinBox()

        self.npts_spin.setToolTip("Total number of spectrum points evaluated (read-only).")

        self.npts_spin.setRange(0, 50000)

        self.npts_spin.setReadOnly(True)

        self.npts_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        opt_grid.addWidget(QLabel("Spectrum Points:"), row, 0)

        opt_grid.addWidget(self.npts_spin, row, 1)

        row += 1

        # Monte Carlo section

        opt_grid.addWidget(QLabel("<b>MC ANALYSIS: </b>"), row, 0, 1, 2)

        row += 1

        self.mc_n_spin = QSpinBox()

        self.mc_n_spin.setToolTip("Number of Monte Carlo samples.")

        self.mc_n_spin.setRange(10, 5000)

        self.mc_n_spin.setValue(200)

        opt_grid.addWidget(QLabel("Samples:"), row, 0)

        opt_grid.addWidget(self.mc_n_spin, row, 1)

        row += 1

        self.mc_sigma_spin = QDoubleSpinBox()

        self.mc_sigma_spin.setRange(0.1, 20)

        self.mc_sigma_spin.setValue(2.0)

        self.mc_sigma_spin.setToolTip(
            "Standard deviation of the Gaussian thickness perturbation for Monte Carlo\n"
            "sensitivity analysis (nm). Simulates manufacturing thickness errors."
        )

        opt_grid.addWidget(QLabel("Sigma (nm):"), row, 0)

        opt_grid.addWidget(self.mc_sigma_spin, row, 1)

        return opt_group

    def _build_action_buttons(self) -> QVBoxLayout:
        """Constructs action buttons"""

        action_layout = QVBoxLayout()

        logger = getattr(self, "logger", None)
        if logger:
            logger.info("DESIGN UI: building action buttons | has_functools=%s", bool(getattr(functools, "partial", None)))

        # Evaluate

        primary_obj = "CertusPrimaryBtn"

        self.eval_btn = QPushButton("Evaluate (Ctrl+E)")

        self.eval_btn.setObjectName(primary_obj)

        self.eval_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.eval_btn.setToolTip("Compute the spectrum for the current stack (instant).")

        self.eval_btn.clicked.connect(functools.partial(self._schedule_eval, True))
        if logger:
            logger.info("DESIGN UI: connected eval button -> _schedule_eval(True)")

        action_layout.addWidget(self.eval_btn)

        # Local/Global optimization

        h_act = QHBoxLayout()

        self.local_btn = QPushButton("Polish local (+/-2 nm)")

        self.local_btn.setObjectName(primary_obj)

        self.local_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        self.local_btn.setToolTip(
            "Run a local gradient polish (L-BFGS) on the current design.\n"
            "Perturbs each layer by +/-2 nm and refines thickness values."
        )

        self.local_btn.clicked.connect(functools.partial(self.run_optim, "local"))

        self.global_btn = QPushButton("PGLOBAL (global)")

        self.global_btn.setObjectName(primary_obj)

        self.global_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))

        self.global_btn.setToolTip(
            "Run the full global PGLOBAL optimization:\n"
            "multi-start random sampling, single-linkage clustering, and local polish."
        )

        self.global_btn.clicked.connect(functools.partial(self.run_optim, "global"))

        h_act.addWidget(self.local_btn)

        h_act.addWidget(self.global_btn)

        action_layout.addLayout(h_act)

        # Remove thinnest layer + merge adjacents + local polish

        self.drop_thin_btn = QPushButton("▼ Drop thinnest layer")

        self.drop_thin_btn.setObjectName(primary_obj)

        self.drop_thin_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))

        self.drop_thin_btn.setToolTip(
            "Removes the thinnest layer, merges adjacent layers (except 1 and N), "
            "and runs a local polish to optimize the resulting design."
        )

        self.drop_thin_btn.clicked.connect(self._drop_thinnest_and_polish)

        action_layout.addWidget(self.drop_thin_btn)

        # Stop

        self.stop_btn = QPushButton("Stop")

        self.stop_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.stop_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))

        self.stop_btn.setToolTip("Stop the running optimization and keep the best design found so far.")

        self.stop_btn.setStyleSheet(CertusTheme.get_danger_button_stylesheet())

        self.stop_btn.clicked.connect(self.stop_optim)

        self.stop_btn.setEnabled(False)

        action_layout.addWidget(self.stop_btn)

        # Colorimetry

        self.color_btn = QPushButton("Colorimetric analysis")

        self.color_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.color_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_CommandLink))

        self.color_btn.setToolTip(
            "Run a Monte Carlo colorimetric analysis on the current design.\n"
            "Shows CIE Lab a*b* distribution and DeltaE stability."
        )

        self.color_btn.clicked.connect(self.run_colorimetry)

        action_layout.addWidget(self.color_btn)

        # Stack Info Button

        self.substrate_info_btn = QPushButton("🔬 Stack info")

        self.substrate_info_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.substrate_info_btn.setToolTip(
            "substrate summary and stack structure in QWOT (best design if optimization is running)."
        )

        self.substrate_info_btn.clicked.connect(self._show_substrate_info_window)

        action_layout.addWidget(self.substrate_info_btn)

        # Update stack info when optimization completes

        self.optimization_finished_signal.connect(self._update_substrate_info)

        # Clear / Reset (use app's full reset: tables, state, plots, then _load_defaults)

        from certus_reset_framework import create_reset_button

        self.clear_btn = create_reset_button(self, use_app_reset=True)

        action_layout.addWidget(self.clear_btn)

        return action_layout

    def _show_substrate_info_window(self) -> None:
        """Display stack information in a separate window"""

        if getattr(self, "substrate_info_window", None) and self.substrate_info_window.isVisible():
            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        if getattr(self, "substrate_info_window", None) and not self.substrate_info_window.isVisible():
            self.substrate_info_window.show()

            self.substrate_info_window.raise_()

            self.substrate_info_window.activateWindow()

            self._update_substrate_info()

            return

        self.substrate_info_window = QDialog(self)

        self.substrate_info_window.setWindowTitle("🔬 Stack information")

        self.substrate_info_window.setMinimumSize(600, 400)

        layout = QVBoxLayout(self.substrate_info_window)

        info_layout = QGridLayout()

        info_layout.addWidget(QLabel("substrate:"), 0, 0)

        info_layout.addWidget(QLabel("Index:"), 1, 0)

        self.substrate_type_label = QLabel("N/A")

        self.substrate_index_label = QLabel("N/A")

        info_layout.addWidget(self.substrate_type_label, 0, 1)

        info_layout.addWidget(self.substrate_index_label, 1, 1)

        layout.addLayout(info_layout)

        structure_card = CertusCard("Structure (QWOT)")

        structure_layout = structure_card.body

        self.structure_text = QTextEdit()

        self.structure_text.setReadOnly(True)

        self.structure_text.setMaximumHeight(200)

        structure_layout.addWidget(self.structure_text)

        layout.addWidget(structure_card)

        btn_layout = QHBoxLayout()

        close_btn = QPushButton("Close")

        close_btn.clicked.connect(self.substrate_info_window.close)

        btn_layout.addWidget(close_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self.substrate_info_window.setLayout(layout)

        self.substrate_info_window.show()

        self.substrate_info_window.raise_()

        self.substrate_info_window.activateWindow()

        self._update_substrate_info()

    def _build_right_panel(self) -> Any:
        """Constructs right panel with visualization and tables"""

        right_panel = QWidget()

        right_layout = QVBoxLayout(right_panel)

        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Visualization Area

        self.viz_stack = QStackedWidget()

        self.viz_stack.addWidget(WelcomeGuideWidget("CERTUS-DESIGN"))

        viz_container = QWidget()

        v_lay = QVBoxLayout(viz_container)

        self.plot_tabs = QTabWidget()

        # Y Label dynamically updated

        self.spectrum_plot = CertusScientificPlot(self, "Spectrum", "Transmission", "lambda (nm)")

        # Init X scale (def: 380-780nm)

        self.spectrum_plot.setXRange(200, 3000, 0)

        self.spectrum_plot.setYRange(0.0, 1.0, 0)

        self.profile_plot = CertusScientificPlot(self, "Refractive Index Profile", "n", "z (nm)")

        self.nk_plot = CertusScientificPlot(self, "Dispersion n(lambda)", "n", "lambda (nm)")

        self.color_plot = CertusScientificPlot(self, "CIE a*b* Diagram", "b*", "a*")

        # Buttons to detach plots

        plot_header = QWidget()

        plot_header.setStyleSheet(f"background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        plot_header_layout = QHBoxLayout(plot_header)

        plot_header_layout.setContentsMargins(6, 2, 6, 2)

        detach_btn = QPushButton("🔗 Detach plot")

        detach_btn.setToolTip("Open the current plot tab in a separate window.")

        detach_btn.clicked.connect(self.detach_current_plot)

        plot_header_layout.addWidget(detach_btn)

        plot_header_layout.addStretch()

        plot_container = QWidget()

        plot_container_layout = QVBoxLayout(plot_container)

        plot_container_layout.setContentsMargins(0, 0, 0, 0)

        plot_container_layout.addWidget(plot_header)

        plot_container_layout.addWidget(self.plot_tabs)

        self.plot_tabs.addTab(self.spectrum_plot, "Spectrum (T)")

        self.plot_tabs.addTab(self.profile_plot, "Profile")

        self.plot_tabs.addTab(self.nk_plot, "n(lambda)")

        self.plot_tabs.addTab(self.color_plot, "Color")

        # Convergence plot (like INDEX/METAL)

        self.plot_convergence = CertusScientificPlot(self, "Optimization Convergence", "RMSE", "Iteration")

        self.plot_convergence.showGrid(x=True, y=True)

        self.plot_convergence.setLogMode(y=True)

        self.convergence_curve = self.plot_convergence.plot([], [], pen=pg.mkPen(CertusTheme.ERROR, width=2))

        self.plot_tabs.addTab(self.plot_convergence, "Convergence")

        # Why CERTUS? tab (matching INDEX/METAL style)

        c1 = FlashyCard(
            "Global Optimization PGLOBAL",
            "Multi-start + real-time callback\nKeeps the best RMSE over the entire workflow",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Solution Topology",
            "Single-linkage clustering of minima\nAvoids missing design valleys",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Automatic Needle + Healing",
            "Variational layer insertion\nLocal refinement to converge cleanly",
            icon="🎯",
        )

        c4 = FlashyCard(
            "Optical Performance + Color",
            "Spectrum, n(lambda) profile, CIE Lab\nDeltaE tracking for visual stability",
            icon="🔮",
        )

        self.perf_tab = create_flashy_grid([c1, c2, c3, c4])

        self.plot_tabs.addTab(self.perf_tab, "Why CERTUS?")

        v_lay.addWidget(plot_container)

        self.viz_stack.addWidget(viz_container)

        right_splitter.addWidget(self.viz_stack)

        # Table Area

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        bottom_splitter.addWidget(self._build_front_table_widget())

        bottom_splitter.addWidget(self._build_target_table_widget())

        right_splitter.addWidget(bottom_splitter)

        right_splitter.setSizes([600, 300])

        right_layout.addWidget(right_splitter)

        # Log Container

        self.log_container = self._build_log_container()

        self.log_container.setVisible(False)  # Start hidden

        right_layout.addWidget(self.log_container)

        return right_panel

    def _build_front_table_widget(self) -> QWidget:
        """Constructs front layer table widget (Now a TabWidget with Pareto History)"""

        self.front_tabs = QTabWidget()

        self.front_tabs.setMaximumWidth(460)

        # Tab 1: Front Structure

        self.front_container = QWidget()

        f_lay = QVBoxLayout(self.front_container)

        f_head = QHBoxLayout()

        f_head.addWidget(QLabel("<b>FRONT STRUCTURE</b>"))

        self.layer_count_label = QLabel("0 layers")

        f_head.addStretch()

        self.detach_btn = QPushButton("Detach")

        self.detach_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.detach_btn.setToolTip("Open the front layer table in a separate floating window.")

        self.detach_btn.clicked.connect(self.detach_front_table)

        f_head.addWidget(self.detach_btn)

        f_head.addWidget(self.layer_count_label)

        f_lay.addLayout(f_head)

        self.front_table = QTableWidget(0, 5)

        self.front_table.setHorizontalHeaderLabels(["Mat", "QWOT", "Thick(nm)", "Var", "Del"])

        header = self.front_table.horizontalHeader()

        self.front_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.front_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        for idx, width in enumerate((55, 70, 80, 40, 40)):
            header.resizeSection(idx, width)

        self.front_table.verticalHeader().setVisible(False)

        self.front_table.setAlternatingRowColors(True)

        table_font = self.front_table.font()

        if table_font.pointSize() > 0:
            table_font.setPointSize(max(8, table_font.pointSize() - 1))

            self.front_table.setFont(table_font)

        f_lay.addWidget(self.front_table)

        # Install event filter for Excel copy/paste

        self.front_table.installEventFilter(self)

        # Manipulation Buttons

        f_btns = QHBoxLayout()

        btn_defs = [
            ("Add", self.add_front_layer, QStyle.StandardPixmap.SP_FileDialogNewFolder),
            ("Remove", self.del_front_layer, QStyle.StandardPixmap.SP_TrashIcon),
            ("Undo", self._undo, QStyle.StandardPixmap.SP_ArrowBack),
            ("Thin", self.remove_thinnest, QStyle.StandardPixmap.SP_ArrowDown),
            ("Reset", self.reset_qwot, QStyle.StandardPixmap.SP_BrowserReload),
        ]

        _btn_tooltips = {
            "Add": "Add a new layer below the current selection.",
            "Remove": "Remove the selected layer from the stack.",
            "Undo": "Undo the last change to the layer table.",
            "Thin": "Remove the thinnest layer (useful for topology simplification).",
            "Reset": "Reset all QWOT values to 1.0 (quarter-wave optical thickness).",
        }

        for txt, func, icon in btn_defs:
            b = QPushButton(txt)

            b.setIcon(self.style().standardIcon(icon))

            b.clicked.connect(func)

            b.setToolTip(_btn_tooltips.get(txt, ""))

            f_btns.addWidget(b)

        self.undo_btn = f_btns.itemAt(2).widget()

        self.undo_btn.setEnabled(False)

        f_lay.addLayout(f_btns)

        self.pareto_btn = QPushButton("🏆 Open Pareto Front")

        self.pareto_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.pareto_btn.setToolTip(
            "Open the Pareto Front window: trade-off between RMSE and number of layers N.\n"
            "Double-click a row to load the corresponding design."
        )

        self.pareto_btn.setStyleSheet("""

            QPushButton {

                background-color: #2b3a42;

                color: #e2e8f0;

                font-weight: bold;

                font-size: 14px;

                padding: 10px;

                border-radius: 5px;

                border: 1px solid #4a5568;

            }

            QPushButton:hover {

                background-color: #3f515d;

            }

        """)

        self.pareto_btn.clicked.connect(self._show_pareto_window)

        f_lay.addWidget(self.pareto_btn)

        self.front_tabs.addTab(self.front_container, "Structure")

        # Pareto chart will be created in a separate window

        self.pareto_table = QTableWidget(0, 8)

        self.pareto_table.setHorizontalHeaderLabels(
            ["N", "Best RMSE", "dₘᵢₙ(nm)", "Best MC +/-0.3nm", "dₘᵢₙ(nm)", "Best Fab", "dₘᵢₙ Fab", "RMSE/N"]
        )

        self.pareto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.pareto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.pareto_table.verticalHeader().setVisible(False)

        self.pareto_table.setAlternatingRowColors(True)

        font = self.pareto_table.font()

        font.setPointSize(max(8, font.pointSize() - 1))

        self.pareto_table.setFont(font)

        self.pareto_table.cellDoubleClicked.connect(self._load_pareto_design)

        # Pareto window will be created on demand

        self.pareto_window = None

        return self.front_tabs

    def _build_target_table_widget(self) -> QWidget:
        """Constructs spectral targets table widget"""

        tgt_widget = QWidget()

        t_lay = QVBoxLayout(tgt_widget)

        t_lay.addWidget(QLabel("<b>SPECTRAL TARGETS</b>"))

        # Table with adaptive columns by mode

        self.target_table = QTableWidget(0, 6)

        self._update_target_table_headers()

        self.target_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.target_table.setAlternatingRowColors(True)

        t_lay.addWidget(self.target_table)

        t_btns = QHBoxLayout()

        bt_add = QPushButton("Add Target")

        bt_add.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))

        bt_add.setToolTip(
            "Add a new spectral target row (lambdamin, lambdamax, Tmin, Tmax, Weight).\n"
            "Double-click a cell to edit values directly."
        )

        bt_add.clicked.connect(self.add_target)

        bt_del = QPushButton("Remove")

        bt_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        bt_del.setToolTip("Remove the selected spectral target row.")

        bt_del.clicked.connect(self.del_target)

        t_btns.addWidget(bt_add)

        t_btns.addWidget(bt_del)

        t_lay.addLayout(t_btns)

        return tgt_widget

    def _toggle_oblique_mode(self, state: int) -> None:
        """Toggle oblique mode and update UI"""

        self.oblique_mode = state == Qt.CheckState.Checked.value

        self._update_target_table_headers()

        # Convert existing targets if needed

        if self.oblique_mode:
            # Convert normal to oblique targets

            if hasattr(self, "target_widgets") and len(self.target_widgets) > 0:
                self.oblique_targets = []

                for tgt in self.target_widgets:
                    if isinstance(tgt, Target):
                        oblique_tgt = ObliqueTarget(
                            angle=0.0,
                            pol="s",
                            target_type="T",
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                            include_backside=True,
                        )

                        self.oblique_targets.append(oblique_tgt)

        else:
            # Convert oblique to normal targets

            if len(self.oblique_targets) > 0:
                self.target_widgets = []

                for tgt in self.oblique_targets:
                    if isinstance(tgt, ObliqueTarget):
                        normal_tgt = Target(
                            lmin=tgt.lmin,
                            lmax=tgt.lmax,
                            tmin=tgt.tmin,
                            tmax=tgt.tmax,
                            w=tgt.w,
                            on=tgt.on,
                        )

                        self.target_widgets.append(normal_tgt)

        # Reload table

        self._load_targets_to_table()

        self._schedule_eval(True)

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self):
            self.status_label.setText("Logs copied to clipboard.")

    def _build_status_bar(self) -> None:
        """Constructs status bar"""

        self.status_bar = QStatusBar()

        self.setStatusBar(self.status_bar)

        self.status_bar.setStyleSheet(CertusTheme.get_status_bar_stylesheet())

        self.best_rmse_label = QLabel("Best RMSE: N/A")

        self.best_rmse_label.setStyleSheet(
            f"color: {CertusTheme.PRIMARY}; font-weight: bold; padding-left: 15px; padding-right: 15px;"
        )

        self.status_label = CertusStatusPill("Ready", "ready")

        self.stats_label = QLabel("♟️ 0 minima  | 🎲 0 evals  | 🌈️ 0")

        self.stats_label.setStyleSheet(
            f"QLabel {{ color: {CertusTheme.TEXT_MAIN}; font-weight: bold; font-size: 12px; padding: 2px 8px; background-color: transparent; }}"
        )

        self.progress_widget = EnhancedProgressWidget()

        self.log_btn = QPushButton("Logs")

        self.log_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self.log_btn.setToolTip("Show or hide the log panel and optimization detail.")

        self.log_btn.setCheckable(True)

        self.log_btn.setChecked(False)

        self.log_btn.clicked.connect(self.toggle_logs)

        self.log_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")

        self.status_bar.addWidget(self.log_btn)

        self.status_bar.addWidget(self.status_label)

        self.status_bar.addPermanentWidget(self.stats_label)

        self.status_bar.addPermanentWidget(self.best_rmse_label)

        self.status_bar.addPermanentWidget(self.progress_widget)

    # =========================================================================

    # HELPERS UI

    # =========================================================================

    def _apply_preset(self, name: str, n4_spin: QDoubleSpinBox, n7_spin: QDoubleSpinBox) -> None:
        """Applies Cauchy preset and updates spinbox states."""

        if name in CAUCHY_PRESETS:
            vals = CAUCHY_PRESETS[name]

            if vals[0] > 0:
                n4_spin.setValue(vals[0])

                n7_spin.setValue(vals[1])

        # Enable/disable spinboxes based on preset

        is_custom = name == "Custom"

        n4_spin.setReadOnly(not is_custom)

        n7_spin.setReadOnly(not is_custom)

        # Visual distinction for readonly state

        style = "" if is_custom else f"background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_SUB};"

        n4_spin.setStyleSheet(style)

        n7_spin.setStyleSheet(style)

    def _setup_shortcuts(self) -> None:
        """Configures keyboard shortcuts"""

        QShortcut(QKeySequence("Ctrl+E"), self, lambda: self._schedule_eval(True))

        QShortcut(QKeySequence("Ctrl+O"), self, lambda: self.run_optim("local"))

        QShortcut(QKeySequence("Ctrl+G"), self, lambda: self.run_optim("global"))

        QShortcut(QKeySequence("Ctrl+S"), self, self.save_config)

        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)

        install_standard_shortcuts(
            self,
            run=lambda: self.run_optim("global"),
            stop=self.stop_optim,
            help=self.open_help,
            extra={"Ctrl+L": lambda: getattr(self, "toggle_logs", lambda: None)()},
        )

        def _on_spectrum_drop(paths) -> None:
            if paths and hasattr(self, "load_config"):
                self.load_config(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_spectrum_drop, extensions=("json", "csv", "xlsx", "xls"))

    def _toggle_back_stack(self, state: int) -> None:
        """Toggle backside group visibility"""

        self.back_group.setVisible(bool(state))

        self._schedule_eval(True)

    def _show_pareto_window(self) -> None:
        """Display the Pareto table in a detachable window."""

        if self.pareto_window is None:
            self.pareto_window = QDialog(self)

            self.pareto_window.setWindowTitle("🏆 Pareto Front Explorer")

            self.pareto_window.setMinimumSize(850, 400)

            p_lay = QVBoxLayout(self.pareto_window)

            # Label descriptif

            lbl = QLabel(
                "Double-click col 1-2 = load <b>Best RMSE</b> | "
                "Double-click col 3-4 = load <b>Best MC</b> | "
                "Double-click col 5-6 = load <b style='color:green;'>Best Fab (>=5nm)</b>"
            )

            lbl.setStyleSheet("font-size: 12px; margin-bottom: 5px;")

            p_lay.addWidget(lbl)

            # Table (kept in memory even when window is closed)

            p_lay.addWidget(self.pareto_table)

            # Boutons d'action

            f_p_btns = QHBoxLayout()

            clr_btn = QPushButton("🗑️ Clear Pareto")

            clr_btn.setToolTip("Clear the Pareto front table.")

            clr_btn.clicked.connect(self._clear_pareto)

            exp_btn = QPushButton("📄Export HTML Report")

            exp_btn.setToolTip("Export Pareto front to an HTML report.")

            exp_btn.clicked.connect(self._export_pareto_report)

            f_p_btns.addWidget(clr_btn)

            f_p_btns.addStretch()

            f_p_btns.addWidget(exp_btn)

            p_lay.addLayout(f_p_btns)

        # Show the window in non-modal mode (allows you to click behind it)

        self.pareto_window.show()

        self.pareto_window.raise_()

        self.pareto_window.activateWindow()

    # =========================================================================

    # LAYER MANAGEMENT

    # =========================================================================

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox) -> None:
        """DESIGN specific: update Tikhonravov on QWOT change."""

        spinbox.valueChanged.connect(self._on_tikhonravov_points_changed)

    def _on_schedule_eval_signal(self, *_args) -> None:

        self._schedule_eval()

    def _on_schedule_eval_instant_signal(self, *_args) -> None:

        self._schedule_eval(True)

    def _on_update_spectrum_y_scale_signal(self, *_args) -> None:

        self._update_spectrum_y_scale()

    def _on_tikhonravov_points_changed(self, *_args) -> None:

        QTimer.singleShot(300, self._update_tikhonravov_points)

    def _add_back_row(self, mat: str, qwot: float) -> None:
        """Adds a row to back layer table"""

        row = self.back_table.rowCount()

        self.back_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._on_schedule_eval_signal)

        self.back_table.setCellWidget(row, 0, cb)

        sb = self._create_spin(qwot, dec=3)

        sb.valueChanged.connect(self._on_schedule_eval_signal)

        self.back_table.setCellWidget(row, 1, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.back_table.setItem(row, 2, it)

    def _on_layer_added(self) -> None:
        """DESIGN specific: update thickness display and points."""

        self._update_thickness_display()

        QTimer.singleShot(300, self._update_tikhonravov_points)

    def _on_layer_deleted(self) -> None:
        """DESIGN specific: update thickness display and run local optimization."""

        self._update_thickness_display()

        self.run_optim("local")

    def add_back_layer(self) -> None:
        """Adds back layer"""

        if self.back_table.rowCount() >= CFG.MAX_LAYERS:
            return

        mat = "H"

        if self.back_table.rowCount() > 0:
            prev = self._safe_get_combo_text(self.back_table.rowCount() - 1, 0, self.back_table)

            if prev:
                mat = "L" if prev == "H" else "H"

        self._add_back_row(mat, 1.0)

        self._schedule_eval()

    def del_back_layer(self) -> None:
        """Removes back layer"""

        r = self.back_table.currentRow()

        if r < 0 and self.back_table.rowCount() > 0:
            r = self.back_table.rowCount() - 1

        if r >= 0:
            self.back_table.removeRow(r)

            self._schedule_eval(True)

    def remove_thinnest(self) -> None:
        """Removes thinnest layer (identically to the left panel button).

        Rules:

        - Finds the thinnest layer in the entire stack (including boundaries).

        - If it's a boundary layer (first or last), no merge step.

        - If it's an interior layer, merges adjacent identical materials.

        - Ends with a local polish and Pareto record.

        """

        N = self.front_table.rowCount()

        if N <= 1:
            return

        # Get current thicknesses

        ep = self.ep_current

        if ep is None or len(ep) != N:
            # Fallback if display not up to date

            self._update_thickness_display()

            ep = self.ep_current

            if ep is None:
                return

        # Identify thinnest layer

        r = int(np.argmin(ep))

        is_boundary = r == 0 or r == N - 1

        self._save_undo_state()

        self.log(f"Remove layer {r + 1}: {ep[r]:.1f}nm", "INFO")

        self.front_table.removeRow(r)

        if not is_boundary:
            # Merging is only relevant when removing an interior layer

            # as it brings two previously separated layers together.

            self._merge_adjacent_layers()

        else:
            self._update_layer_count()

            self._update_thickness_display()

        # Update target count and run optimization

        self._target_layer_count = self.front_table.rowCount()

        self.run_optim("local", keep_history=True)

    def _trigger_post_undo_action(self) -> None:
        """DESIGN specific post-undo action."""

        self.run_optim("local")

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """DESIGN specific plot info mapping."""

        if widget == self.spectrum_plot:
            return "spectrum", "Spectrum (T)"

        elif widget == self.profile_plot:
            return "profile", "Refractive Index Profile"

        elif widget == self.nk_plot:
            return "nk", "Dispersion n(lambda)"

        elif widget == self.color_plot:
            return "color", "CIE a*b* Diagram"

        elif widget == self.plot_convergence:
            return "convergence", "Optimization Convergence"

        return None

    def _paste_from_excel(self) -> None:
        """Pastes data from Excel into layer table"""

        clipboard = QApplication.clipboard()

        text = clipboard.text()

        if not text:
            return

        try:
            # Excel parse (tabs/cols, newlines/rows)

            lines = text.strip().split("\n")

            rows_data = []

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Split columns (tabs or multiple spaces)

                cols = line.split("\t")

                if len(cols) < 2:  # If no tab, try with multiple spaces
                    cols = [c for c in line.split(" ") if c]

                if len(cols) < 2:
                    continue

                # Parse columns

                # Fmt: Mat, QWOT, [Thick], [Var]

                mat = cols[0].strip()

                qwot_str = cols[1].strip()

                # Check if material is valid

                materials = [m for m in CFG.MATERIALS if m != "Substrate"]

                if mat not in materials:
                    # Try to find match (case insensitive)

                    mat_lower = mat.lower()

                    mat_found = None

                    for m in materials:
                        if m.lower() == mat_lower:
                            mat_found = m

                            break

                    if mat_found:
                        mat = mat_found

                    else:
                        self.log(f"Invalid material ignored: {mat}", "WARNING")

                        continue

                # Parser QWOT

                try:
                    qwot = float(qwot_str.replace(",", "."))

                except ValueError:
                    self.log(f"Invalid QWOT value ignored: {qwot_str}", "WARNING")

                    continue

                # Parse Var (optional, col 3 or 4)

                var = True  # default

                if len(cols) >= 3:
                    var_str = cols[2].strip().lower()

                    # Accept various forms: 0/1, true/false, yes/no, etc.

                    if var_str in ["0", "false", "f", "non", "n", "no", ""]:
                        var = False

                    elif var_str in ["1", "true", "t", "oui", "o", "yes", "y"]:
                        var = True

                    # If number, use as thickness (legacy format)

                    else:
                        try:
                            float(var_str.replace(",", "."))

                            # Likely a thickness, so Var remains True

                        except ValueError:
                            # Neither number nor boolean, ignore

                            pass

                rows_data.append((mat, qwot, var))

            if not rows_data:
                self.log("No valid data to paste", "WARNING")

                return

            # Save state for undo

            self._save_undo_state()

            # Clear table or append depending on selection

            current_row = self.front_table.currentRow()

            if current_row >= 0:
                # Paste from selected row

                start_row = current_row

            else:
                # Clear table and paste from start

                self.front_table.blockSignals(True)

                self.front_table.setRowCount(0)

                self.front_table.blockSignals(False)

                start_row = 0

            # Add rows

            self.front_table.blockSignals(True)

            for i, (mat, qwot, var) in enumerate(rows_data):
                row = start_row + i

                if row >= self.front_table.rowCount():
                    self._add_front_row(mat, qwot, var)

                else:
                    # Replace existing row

                    # Mat

                    cb = self._create_combo(mat)

                    cb.currentIndexChanged.connect(self._merge_adjacent_layers)

                    self.front_table.setCellWidget(row, 0, cb)

                    # QWOT

                    sb = self._create_spin(qwot, dec=6)

                    sb.valueChanged.connect(self._on_schedule_eval_signal)

                    sb.valueChanged.connect(self._on_tikhonravov_points_changed)

                    self.front_table.setCellWidget(row, 1, sb)

                    # Var

                    chk = self.front_table.cellWidget(row, 3).findChild(QCheckBox)

                    if chk:
                        chk.setChecked(var)

                    del_cw = self.front_table.cellWidget(row, 4)

                    if del_cw:
                        del_chk = del_cw.findChild(QCheckBox)

                        if del_chk:
                            del_chk.setChecked(False)

            self.front_table.blockSignals(False)

            self._update_layer_count()

            self._schedule_eval()

            self.log(f"{len(rows_data)} row(s) pasted from Excel", "SUCCESS")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("Paste from Excel failed: %s", e, exc_info=True)

    # =========================================================================

    # TARGET MANAGEMENT

    # =========================================================================

    def add_target(self) -> None:
        """Adds spectral target"""

        r = self.target_table.rowCount()

        self.target_table.insertRow(r)

        col_idx = 0

        # Active Checkbox

        chk = QCheckBox()

        chk.setToolTip("Enable or disable this target.")

        chk.setChecked(True)

        chk.stateChanged.connect(self._schedule_eval)

        chk.stateChanged.connect(self._update_optim_point_count)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.target_table.setCellWidget(r, col_idx, cw)

        col_idx += 1

        if self.oblique_mode:
            # Oblique: Ang, Pol, Type, lmin, lmax, Vmin, Vmax, W

            # Angle

            angle_sb = self._create_spin(0.0, dec=1, minv=0, maxv=90)

            angle_sb.setToolTip("Incident angle (degrees).")

            angle_sb.valueChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, angle_sb)

            col_idx += 1

            # Polarization

            pol_combo = QComboBox()

            pol_combo.setToolTip("Target polarization: s, p, or Avg (unpolarized average).")

            pol_combo.addItems(["s", "p", "Avg"])

            pol_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, pol_combo)

            col_idx += 1

            # Type (R or T)

            type_combo = QComboBox()

            type_combo.setToolTip("Target type: Reflectance (R) or Transmittance (T).")

            type_combo.addItems(["R", "T"])

            type_combo.currentTextChanged.connect(self._schedule_eval)

            self.target_table.setCellWidget(r, col_idx, type_combo)

            col_idx += 1

            # lambdamin, lambdamax

            for val, dec in [(400.0, 1), (700.0, 1)]:
                sb = self._create_spin(val, dec=dec, minv=200, maxv=20000)

                tt = "Target wavelength range start (nm)." if val == 400.0 else "Target wavelength range end (nm)."

                sb.setToolTip(tt)

                sb.valueChanged.connect(self._schedule_eval)

                sb.valueChanged.connect(self._update_optim_point_count)

                sb.valueChanged.connect(lambda: QTimer.singleShot(300, self._update_tikhonravov_points))

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

            # Val min, Val max, Weight

            for i, (val, dec, maxv) in enumerate([(0.0, 3, 1), (1.0, 3, 1), (1.0, 1, 100)]):
                sb = self._create_spin(val, dec=dec, minv=0, maxv=maxv)

                tts = ["Minimum target value.", "Maximum target value.", "Weight multiplier for this target."]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self._schedule_eval)

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        else:
            # Normal Mode: lmin, lmax, Tmin, Tmax, Weight

            defs = [400.0, 700.0, 0.0, 0.5, 1.0]

            decs = [1, 1, 3, 3, 1]

            ranges = [(200, 20000), (200, 20000), (0, 1), (0, 1), (0, 100)]

            for i, val in enumerate(defs):
                sb = self._create_spin(val, dec=decs[i], minv=ranges[i][0], maxv=ranges[i][1])

                tts = [
                    "Target wavelength range start (nm).",
                    "Target wavelength range end (nm).",
                    "Minimum target Transmittance (0-1).",
                    "Maximum target Transmittance (0-1).",
                    "Weight multiplier for this target.",
                ]

                sb.setToolTip(tts[i])

                sb.valueChanged.connect(self._on_schedule_eval_signal)

                if i in [0, 1]:
                    sb.valueChanged.connect(self._update_optim_point_count)

                    sb.valueChanged.connect(lambda: QTimer.singleShot(300, self._update_tikhonravov_points))

                self.target_table.setCellWidget(r, col_idx, sb)

                col_idx += 1

        self._update_optim_point_count()

    def del_target(self) -> None:
        """Removes spectral target"""

        r = self.target_table.currentRow()

        if r >= 0:
            self.target_table.removeRow(r)

            self._schedule_eval()

            self._update_optim_point_count()

            QTimer.singleShot(200, self._update_tikhonravov_points)

            QTimer.singleShot(200, self._update_tikhonravov_points)

    def _get_optim_wls(self) -> np.ndarray:
        """Calculates wavelengths for optimization"""

        if self.oblique_mode:
            tgts = self._get_oblique_tgts()

        else:
            tgts = self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            return np.array([])

        wls_list = []

        n_points = self.points_per_target_spin.value()

        for t in active:
            start = max(t.lmin, 1e-3)

            end = max(t.lmax, start + 1e-3)

            if n_points > 1:
                # Uniform grid in wavenumbers (1/lambda)

                sigma_min = 1.0 / end

                sigma_max = 1.0 / start

                # Linear grid in wavenumbers

                sigma_grid = np.linspace(sigma_min, sigma_max, n_points)

                # Convert back to wavelengths

                grid = 1.0 / sigma_grid

            else:
                grid = np.array([start])

            wls_list.append(grid)

        if wls_list:
            wls = np.unique(np.concatenate(wls_list))

        else:
            wls = np.array([])

        return wls

    def _update_optim_point_count(self) -> None:
        """Updates optimization point counter"""

        wls = self._get_optim_wls()

        self.npts_spin.setValue(len(wls))

    def _calculate_tikhonravov_points(self) -> int:
        """

        Calculates recommended points per target using Tikhonravov formula.

        Formula: N = 2 * L * delta_nu * margin

        Where:

        - L = total optical thickness in nm (Sum n_i * d_i)

        - delta_nu = spectral interval in wavenumbers (1/nm) = 1/l_min - 1/l_max

        - margin = 10 (safety factor)

        The product L * delta_nu is dimensionless. The factor 2 comes from Nyquist criterion.

        Returns

        -------

        int

            Recommended points per target

        """

        try:
            # Retrieve necessary data

            mats = self._get_materials()

            stack = self._get_front_stack()

            # Use correct targets based on mode (normal or oblique)

            if self.oblique_mode:
                tgts = self._get_oblique_tgts()

            else:
                tgts = self._get_tgts()

            l0 = self.l0_spin.value()

            if not stack or not mats:
                return 50  # Default

            # Calculate total optical thickness L

            # Use current thicknesses if available, else calc from QWOT

            if self.ep_current is not None and len(self.ep_current) == len(stack):
                ep = self.ep_current

            else:
                ep = init_thickness(stack, l0, mats)

                if ep is None:
                    return 50

            # Find global spectral interval of active targets

            active_tgts = [t for t in tgts if t.valid()]

            if not active_tgts:
                return 50

            lambda_min = min(t.lmin for t in active_tgts)

            lambda_max = max(t.lmax for t in active_tgts)

            if lambda_max <= lambda_min or lambda_min < 1e-3:
                return 50

            # Calculate total optical thickness L = Sum(n_i * d_i) in nm

            # Use reference wavelength at center of spectral range

            wl_ref = (lambda_min + lambda_max) / 2.0  # nm

            L_total = 0.0

            for i, layer in enumerate(stack):
                if i >= len(ep):
                    continue

                mat = mats.get(layer.mat)

                if mat:
                    n_ref = mat.get_nk(np.array([wl_ref]))[0].real

                    L_total += n_ref * ep[i]

            if L_total < 1e-6:
                return 50

            # Convert spectral interval to wavenumbers (1/nm)

            nu_min = 1.0 / lambda_max  # Plus petite longueur d'onde = plus grand nombre d'onde

            nu_max = 1.0 / lambda_min  # Plus grande longueur d'onde = plus petit nombre d'onde

            delta_nu = nu_max - nu_min  # en 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * marge

            nu_min = 1.0 / lambda_max

            nu_max = 1.0 / lambda_min

            delta_nu = nu_max - nu_min  # in 1/nm

            # Corrected Tikhonravov formula

            # N = 2 * L_total * delta_nu * margin

            # L_total(nm)*dn(1/nm) = dimensionless

            marge = 10.0

            N = 2.0 * L_total * delta_nu * marge

            # Round and clamp to reasonable limits

            N_int = int(np.ceil(N))

            N_int = max(10, min(5000, N_int))

            return N_int

        except (ValueError, TypeError) as e:
            logging.debug(f"Could not calculate tikhonravov point count: {e}")

            return 50  # Default on error

    def _update_tikhonravov_points(self) -> None:
        """Automatically updates points count using Tikhonravov."""

        try:
            tikhon_points = self._calculate_tikhonravov_points()

            if tikhon_points > 0:
                current_val = self.points_per_target_spin.value()

                # Update only if change significant

                if abs(tikhon_points - current_val) > max(5, current_val * 0.15):  # Threshold 15% or 5 points
                    self.points_per_target_spin.blockSignals(True)

                    self.points_per_target_spin.setValue(tikhon_points)

                    self.points_per_target_spin.blockSignals(False)

                    self._update_optim_point_count()

                    self.log(
                        f"Tikhonravov: Auto-updated points/target to {tikhon_points}",
                        "INFO",
                    )

        except (AttributeError, ValueError) as e:
            logging.debug(f"Could not update tikhonravov points: {e}")

    # =========================================================================

    # GETTERS

    # =========================================================================

    def _get_materials(self) -> dict:
        """Retrieves configured materials."""

        try:
            result = {k: Material(w["n4"].value(), w["n7"].value()) for k, w in self.mat_widgets.items()}

            return result

        except (AttributeError, KeyError) as e:
            logging.debug(f"Could not get materials: {e}")

            return {}

    def _get_oblique_tgts(self) -> list[ObliqueTarget]:
        """Retrieves spectral targets (oblique mode)"""

        if not self.oblique_mode:
            return []  # Sinon mode normal : _get_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                active = chk.isChecked() if chk else False

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                angle = angle_w.value() if angle_w else 0.0

                # Polarisation

                pol_w = self.target_table.cellWidget(r, 2)

                polarization = pol_w.currentText() if pol_w else "s"

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                target_type = type_w.currentText() if type_w else "T"

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                lmin = lmin_w.value() if lmin_w else 400.0

                lmax = lmax_w.value() if lmax_w else 700.0

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                val_min = vmin_w.value() if vmin_w else 0.0

                val_max = vmax_w.value() if vmax_w else 1.0

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

                weight = weight_w.value() if weight_w else 1.0

                targets.append(
                    ObliqueTarget(
                        angle=angle,
                        pol=polarization,
                        target_type=target_type,
                        lmin=lmin,
                        lmax=lmax,
                        tmin=val_min,
                        tmax=val_max,
                        w=weight,
                        on=active,
                        include_backside=True,
                    )
                )

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug(f"Could not get oblique target row: {e}")

        return targets

    def _load_targets_to_table(self) -> None:
        """Loads targets into table from internal lists"""

        self.target_table.setRowCount(0)

        if self.oblique_mode:
            for tgt in self.oblique_targets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # Angle

                angle_w = self.target_table.cellWidget(r, 1)

                if angle_w:
                    angle_w.setValue(tgt.angle)

                # Pol

                pol_w = self.target_table.cellWidget(r, 2)

                if pol_w:
                    pol_w.setCurrentText(tgt.pol)

                # Type

                type_w = self.target_table.cellWidget(r, 3)

                if type_w:
                    type_w.setCurrentText(tgt.target_type)

                # lambdamin, lambdamax

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                if lmin_w:
                    lmin_w.setValue(tgt.lmin)

                if lmax_w:
                    lmax_w.setValue(tgt.lmax)

                # Val min, Val max

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                if vmin_w:
                    vmin_w.setValue(tgt.tmin)

                if vmax_w:
                    vmax_w.setValue(tgt.tmax)

                # Weight

                weight_w = self.target_table.cellWidget(r, 8)

                if weight_w:
                    weight_w.setValue(tgt.w)

        else:
            for tgt in self.target_widgets:
                self.add_target()

                r = self.target_table.rowCount() - 1

                # Active

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(tgt.on)

                # lambdamin, lambdamax, Tmin, Tmax, Weight

                for i, val in enumerate([tgt.lmin, tgt.lmax, tgt.tmin, tgt.tmax, tgt.w]):
                    w = self.target_table.cellWidget(r, i + 1)

                    if w:
                        w.setValue(val)

    def _on_front_thickness_updated(self) -> None:
        """DESIGN specific: update Tikhonravov points."""

        QTimer.singleShot(150, self._update_tikhonravov_points)

    # =========================================================================

    # EVALUATION

    # =========================================================================

    def run_eval(self) -> None:
        """

        Runs spectral evaluation of the current design.

        This method performs complete spectral evaluation including:

        - JIT compilation warmup check

        - Material and stack validation

        - Target configuration setup

        - Worker thread initialization and execution

        - Result processing and visualization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs evaluation progress and timing

            - Handles both normal and oblique modes

            - Emits progress signals during execution

            - Updates UI components with results

        """

        _eval_start = time.time()

        if not spectrum_eval_run_preamble(self, self.run_eval):
            return

        cfg = spectrum_eval_build_worker_cfg(self, "design")

        if cfg is None:
            return

        spectrum_eval_start_worker(self, cfg, _eval_start)

    def _on_eval_finished(self, data: Dict, generation_id: int | None = None) -> None:
        """

        Callback after spectral evaluation completion.

        This method processes evaluation results including:

        - Result data storage and validation

        - Visualization data processing

        - Plot updates and UI refresh

        - Performance timing and logging

        Args:

            self: CertusDesign instance

            data: Evaluation result dictionary with spectral data

        Returns:

            None

        Notes:

            - Logs evaluation completion and timing

            - Handles both normal and oblique modes

            - Updates UI components with results

            - Stores results for subsequent operations

        """

        _finish_start = time.time()

        data_for_display = spectrum_eval_on_finished_prepare_display(self, data, generation_id)

        if data_for_display is None:
            return

        self.last_result = data_for_display

        # Self-export if pending (triggered by Case C or time budget completion)

        if getattr(self, "_export_pending", False):
            self._export_pending = False

            QTimer.singleShot(100, self.export_results)

        res_vis = data_for_display["vis"]

        res_optim = data_for_display["optimization"]

        oblique_mode = data_for_display.get("oblique_mode", False)

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        plot_targets = self._get_plot_targets("spectrum", self.spectrum_plot)

        spectrum_eval_plot_curves(
            self,
            data_for_display=data_for_display,
            plot_targets=plot_targets,
            res_vis=res_vis,
            res_optim=res_optim,
            oblique_mode=oblique_mode,
        )

        rmse = data_for_display.get("rmse")

        n_points = self.points_per_target_spin.value()

        n_total = len(res_optim["l"]) if len(res_optim["l"]) > 0 else len(self._get_optim_wls())

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            if src_name:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | {src_name} | Points/Target: {n_points} ({n_total} total)"

            else:
                title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        except NUMERICAL_FAULT_EXCEPTIONS:
            title = f"Spectrum ({self.front_table.rowCount()} layers) | Points/Target: {n_points} ({n_total} total)"

        if optim_rmse_is_valid_for_log(rmse):
            title += f" - RMSE: {optim_rmse_display_string(rmse)}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

        spectrum_eval_apply_axes_legend_scale(self, res_vis=res_vis, oblique_mode=oblique_mode)

        self._plot_profile(
            data_for_display["ep"],
            self._get_front_stack(),
            data_for_display.get("ep_back"),
            self._get_back_stack(),
        )

        self._plot_nk()

        logging.info(f"[EVAL] _on_eval_finished complete in {(time.time() - _finish_start) * 1000:.1f}ms")

        self.log(
            f"Evaluation OK. RMSE: {optim_rmse_display_string(rmse)}"
            if optim_rmse_is_valid_for_log(rmse)
            else "Evaluation OK.",
            "SUCCESS",
        )

        self._set_busy(False)

        logging.info("[EVAL] === Evaluation cycle complete, UI ready ===")

        # Systematic Pareto update after any evaluation (manual edit or optimization)

        # data["ep"] and data["rmse"] are available from EvalWorker

        self._update_pareto_record(data_for_display.get("ep"), data_for_display.get("rmse"))

    def _plot_profile(
        self,
        ep: np.ndarray,
        stack: list[Layer],
        ep_back: np.ndarray,
        stack_back: list[Layer],
    ) -> None:
        """Plots refractive index profile (Live update on detached)"""

        logging.info(
            f"[PROFILE] _plot_profile called: ep={ep is not None and len(ep) if ep is not None else None}, stack={len(stack) if stack else 0}"
        )

        for plot_widget in self._get_plot_targets("profile", self.profile_plot):
            try:
                plot_widget.plotItem.clear()

                mats = self._get_materials()

                logging.info(f"[PROFILE] mats keys: {list(mats.keys())}")

                sub_key = "substrate" if "substrate" in mats else ("Substrate" if "Substrate" in mats else None)

                if sub_key is None:
                    logging.warning("[PROFILE] No substrate key in mats — skipping profile plot")

                    continue

                ns = mats[sub_key].n4

                x, y = [0.0, 0.0], [ns, mats[stack[0].mat].n4] if stack else [ns, 1.0]

                if ep is not None and len(ep) > 0:
                    cs = np.cumsum(ep)

                    n_vals = [mats[l.mat].n4 for l in stack]

                    # Protection against index out of bounds (oblique mode may have more thicknesses than layers)

                    n_layers = min(len(ep) - 1, len(n_vals) - 1)

                    for i in range(n_layers):
                        x.extend([cs[i], cs[i]])

                        y.extend([n_vals[i], n_vals[i + 1]])

                    if n_vals:
                        x.extend([cs[-1], cs[-1], cs[-1] + max(50.0, 0.1 * cs[-1])])

                        y.extend([n_vals[-1], 1.0, 1.0])

                else:
                    x, y = [0.0, 50.0], [ns, 1.0]

                logging.info(
                    f"[PROFILE] Plotting {len(x)} points, x range [{min(x):.1f},{max(x):.1f}], y range [{min(y):.2f},{max(y):.2f}]"
                )

                plot_widget.plot(
                    x,
                    y,
                    pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                    fillLevel=0,
                    brush=(30, 58, 138, 30),
                )

                # Backside

                if self.back_check.isChecked() and ep_back is not None and ep_back.size > 0 and stack_back:
                    xb, yb = [0.0, 0.0], [ns, mats[stack_back[0].mat].n4]

                    csb = np.cumsum(ep_back)

                    nb = [mats[l.mat].n4 for l in stack_back]

                    # Protection against index out of bounds

                    n_layers_back = min(len(ep_back) - 1, len(nb) - 1)

                    for i in range(n_layers_back):
                        xb.extend([csb[i], csb[i]])

                        yb.extend([nb[i], nb[i + 1]])

                    if nb:
                        xb.extend([csb[-1], csb[-1], csb[-1] + max(50.0, 0.1 * csb[-1])])

                        yb.extend([nb[-1], 1.0, 1.0])

                    off = max(x) + 100.0

                    plot_widget.plot(
                        [v + off for v in xb],
                        yb,
                        pen=pg.mkPen(CertusTheme.ERROR, width=2),
                        fillLevel=0,
                        brush=(239, 68, 68, 30),
                    )

            except NUMERICAL_FAULT_EXCEPTIONS as _profile_ex:
                logging.info(f"[PROFILE] Exception in _plot_profile: {_profile_ex}")

    def _plot_nk(self) -> None:
        """n(lambda) curves for design materials (2-point Cauchy model)."""

        mats = self._get_materials()

        cols = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ACCENT,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.ERROR,
        ]

        w = np.linspace(380.0, 1000.0, 400)

        for plot_widget in self._get_plot_targets("nk", self.nk_plot):
            plot_widget.plotItem.clear()

            for i, (k, m) in enumerate(mats.items()):
                n_nominal = m.get_nk(w).real

                plot_widget.plot(
                    w,
                    n_nominal,
                    pen=pg.mkPen(cols[i % len(cols)], width=2),
                    name=k,
                )

    # =========================================================================

    # OPTIMIZATION

    # =========================================================================

    @safe_ui_action
    def run_optim(self, mode: str, keep_history: bool = False, **kwargs) -> None:
        """

        Start an optimization cycle.

        logger = getattr(self, "logger", None)
        if logger:
            logger.info(
                "DESIGN run_optim enter | mode=%s | keep_history=%s | kwargs_keys=%s",
                mode,
                bool(keep_history),
                ",".join(sorted(map(str, kwargs.keys()))) if kwargs else "-",
            )

        Entry point for the hybrid design workflow. Three optimization modes

        are available, each with different search scope and bounds:

        - ``'global'``: Full PGLOBAL stochastic search over [0, 1.2×QWOT].

          Used for initial design exploration with HPO-tuned hyperparameters.

        - ``'healing'``: Restricted PGLOBAL search within +/-Deltad of current

          thicknesses, where Deltad = lambda₀/(10·n) per layer (~40% QWOT).

          Triggered automatically after smart_cleanup removes layers.

        - ``'local'``: Narrow L-BFGS-B refinement within +/-2 nm.

          Used for final polish and intra-needle-cycle optimization.

        The complete automated workflow is::

            Global PGLOBAL

            -> smart_cleanup (remove <1nm, merge adjacent)

            -> Healing (restricted global +/-Deltad + local polish)

            -> Needle insertion loop (Overshoot +20%)

            -> Prune thinnest layers back to target

            -> Final local polish

            -> Complete

        This method performs optimization including:

        - Mode-specific parameter setup and bounds

        - Target validation and configuration

        - Worker thread initialization and execution

        - Progress monitoring and result handling

        Args:

            self: CertusDesign instance

            mode: Optimization mode: ``'global'``, ``'healing'``, or ``'local'``

            keep_history: If False (default), resets all workflow state for fresh start.

                       If True, preserves state for internal continuation.

        Returns:

            None

        Notes:

            - Logs optimization progress and results

            - Emits progress signals during execution

            - Handles different optimization modes automatically

            - Supports both fresh start and continuation modes

        """

        # Logging start

        logging.info("=" * 50)

        logging.info(f"STARTING OPTIMIZATION: {mode.upper()} (Keep history: {keep_history})")

        # Check active targets

        if self.oblique_mode:
            active_targets = [t for t in self._get_oblique_tgts() if t.valid()]

            logging.info(f"Mode: Oblique Incidence ({len(active_targets)} active targets)")

        else:
            active_targets = [t for t in self._get_tgts() if t.valid()]

            logging.info(f"Mode: Normal Incidence ({len(active_targets)} active targets)")

        logging.info(f"Samples per iter: {self.n100_spin.value()}")

        logging.info(f"Max iterations: {self.global_cycles_spin.value()}")

        logging.info("=" * 50)

        self._shutdown_previous_optim_worker()

        # INTERNAL RESTART MANAGEMENT

        self._is_internal_restart = keep_history

        # Guard: if user clicked STOP, refuse internal restarts

        if keep_history and getattr(self, "_workflow_stopped", False):
            self.log("Workflow stopped by user, ignoring internal restart.", "WARNING")

            self._set_busy(False)

            return

        if not keep_history:
            self._reset_run_optim_workflow_state(mode)

        else:
            self.log(f"Continuing optimization ({mode})...", "INFO")

        stack, mats, active, ep0, wls = self._collect_run_optim_inputs()
        if stack is None:
            return

        # Calculate limits with 20% margin for display

        wls_min = self._calculate_wls_min_with_margin(active)

        wls_max = self._calculate_wls_max_with_margin(active)

        # Configuration

        if mode == "local":
            cfg = {
                "mode": "local",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": CFG.MAX_FEVAL_LOCAL,
                "n100": 50,
                "max_iter": 10,
                "local_delta_nm": 2.0,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        elif mode == "healing":
            cfg = {
                "mode": "healing",
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": 10000,
                "n100": 500,
                "max_iter": 8,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        else:
            pre_polish = False

            if hasattr(self, "pre_polish_check"):
                pre_polish = self.pre_polish_check.isChecked()

            # If needle growth is enabled, use ultra-fast global (just seed)

            # Needle will iterate and refine - no need for exhaustive global

            allow_growth = getattr(self, "allow_growth_check", None)

            needle_coupled = allow_growth and allow_growth.isChecked()

            if needle_coupled:
                g_max_feval = min(CFG.MAX_FEVAL_GLOBAL, 50000)

                g_n100 = min(self.n100_spin.value(), 1500)

                g_max_iter = min(self.global_cycles_spin.value(), 8)

                g_max_clusters = min(self.max_clusters_spin.value(), 5)

                self.log(
                    "Global+Needle: ultra-fast global (seed for needle iterations)",
                    "INFO",
                )

            else:
                g_max_feval = CFG.MAX_FEVAL_GLOBAL

                g_n100 = self.n100_spin.value()

                g_max_iter = self.global_cycles_spin.value()

                g_max_clusters = self.max_clusters_spin.value()

            cfg = {
                "mode": "global",
                "pre_polish": pre_polish,
                "mats": mats,
                "stack": stack,
                "ep0": ep0,
                "wls": wls,
                "tgts": active if not self.oblique_mode else [],
                "oblique_mode": self.oblique_mode,
                "oblique_tgts": active if self.oblique_mode else [],
                "l0": self.l0_spin.value(),
                "wls_min": wls_min,
                "wls_max": wls_max,
                "max_feval": g_max_feval,
                "n100": g_n100,
                "max_iter": g_max_iter,
                "use_back_coat": self.back_coat_check.isChecked(),
                "back": self.back_check.isChecked(),
                "ep_back": (self.ep_back_current if self.ep_back_current is not None else []),
                "stack_back": self._get_back_stack(),
                "max_clusters": g_max_clusters,
                "calc_oblique_func": (calc_spectrum_oblique_vectorized if self.oblique_mode else None),
            }

        # Start Worker

        self._set_busy(True)

        self._initialize_run_optim_progress_state(cfg, keep_history)

        if kwargs:
            cfg.update(kwargs)

        self.optim_worker = OptimWorker(cfg)

        # Carry best RMSE across internal restarts so GUI doesn't regress

        if keep_history and hasattr(self, "_workflow_best_rmse"):
            self.optim_worker.best_rmse_seen = self._workflow_best_rmse

        self.optim_worker.signals.finished.connect(self._on_optim_done)

        self.optim_worker.signals.error.connect(self._on_error)

        self.optim_worker.signals.result.connect(self._on_intermediate_spectrum)

        self.optim_worker.signals.progress.connect(self._on_optim_progress)

        self.optim_worker.signals.update_stats.connect(self._on_stats_update)

        self.optim_worker.start()

    def _reset_run_optim_workflow_state(self, mode: str) -> None:
        """Reset workflow state and UI counters for a fresh optimization start."""

        self._target_layer_count = self.front_table.rowCount()

        self._topology_stable = True

        self._overshoot_active = False

        self._overshoot_done = False

        self._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        self._initial_cleared = False

        self._clean_live_curves()

        self.log(f"Starting {mode} optimization (PGLOBAL)...", "INFO")

        self.stat_counters["EVAL"] = 0

        self.accumulated_evals = 0

        self.stat_counters["MINIMA"] = 0

        self.update_stats_display()

        self.best_rmse_label.setText("Best RMSE: N/A")

        self._workflow_best_rmse = float("inf")

        self._best_eval_result = None

        self._best_eval_rmse = float("inf")

        self._workflow_stopped = False

        self._decimation_done = False

        self._export_pending = False

        self._post_optim_start_time = None

        self._stack_info_best_ep = None

        self._stack_info_best_rmse = None

        self._stack_info_last_update = 0.0

        import time as _time

        self._workflow_wall_start = _time.time()

        self.mse_data = {"iterations": [], "errors": []}

        self.convergence_curve.setData([], [])

    def _shutdown_previous_optim_worker(self) -> None:
        """Stop any running optimization worker before starting a new cycle."""

        if self.optim_worker is None:
            return

        if self.optim_worker.isRunning():
            self.optim_worker.request_stop()

            self.optim_worker.quit()

            if not self.optim_worker.wait(2000):
                logging.critical(
                    "Optim worker did not stop within 2s - skipping terminate() to avoid unsafe thread kill."
                )

                self.log(
                    "Optim worker did not stop within 2s - skipping terminate() (see log).",
                    "ERROR",
                )

        self.optim_worker = None

    def _collect_run_optim_inputs(self) -> tuple:
        """Collect and validate inputs required by run_optim."""

        stack = self._get_front_stack()

        if not [l for l in stack if l.var]:
            self.log("No variable layers.", "WARNING")

            return None, None, None, None, None

        mats = self._get_materials()

        tgts = self._get_oblique_tgts() if self.oblique_mode else self._get_tgts()

        active = [t for t in tgts if t.valid()]

        if not active:
            self.log("No valid targets.", "WARNING")

            return None, None, None, None, None

        ep0 = init_thickness(stack, self.l0_spin.value(), mats)

        wls = self._get_optim_wls()

        return stack, mats, active, ep0, wls

    def _initialize_run_optim_progress_state(self, cfg: dict, keep_history: bool) -> None:
        """Initialize progress counters and optional time budget for a run."""

        self._optim_max_iter = 100

        self._optim_current_iter = 0

        self._optim_n_evals = 0

        if keep_history:
            return

        _n = len(cfg.get("ep0", []))

        _mode = cfg.get("mode", "global")

        allow_growth = getattr(self, "allow_growth_check", None)

        _needle_coupled = allow_growth and allow_growth.isChecked() and _mode == "global"

        _global_time = 35.0 if _needle_coupled else 90.0

        if _needle_coupled:
            _post_budget = 60.0

        elif _n <= 10:
            _post_budget = 15.0

        elif _n <= 26:
            _post_budget = 15.0 + (_n - 10) * (60.0 - 15.0) / (26 - 10)

        else:
            _post_budget = 60.0 + (_n - 26) * (180.0 - 60.0) / (40 - 26)

        self.progress_widget.set_time_budget(_global_time + _post_budget)

        self.progress_widget.start()

    def _on_optim_progress(self, val: int, msg: str) -> None:
        """Callback for optimization progress update"""

        # val is PERCENTAGE (0-100) from OptimWorker

        # msg format: "Gen X | Evals: Y | Clusters: Z | Best: W"

        self._optim_current_iter = val

        # Extract "Gen X" for display

        gen_info = "Gen ?"

        if "Gen" in msg:
            try:
                gen_info = msg.split("|")[0].strip()

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

        # Update progress widget

        self.progress_widget.update(
            iteration=getattr(self, "_optim_current_iter", val),
            max_iter=getattr(self, "_optim_max_iter", 100),
            evals=getattr(self, "_optim_n_evals", 0),
            phase="PGLOBAL",
            extra_info=(f"{gen_info} | RMSE: {msg.split('Best:')[-1].strip()}" if "Best:" in msg else ""),
        )

        # Also update status label and log

        self.status_label.setText(msg)

        self.log(msg, "INFO")

    def _on_stats_update(self, stat_name: str, value: int) -> None:
        """Callback for stats update (MINIMA, EVAL, COLOR)"""

        if stat_name == "EVAL":
            self._optim_n_evals = value

            display_value = value + getattr(self, "accumulated_evals", 0)

            # Update progress widget with new eval count

            self.progress_widget.update(
                iteration=getattr(self, "_optim_current_iter", 0),
                max_iter=getattr(self, "_optim_max_iter", 100),
                evals=display_value,
                phase="PGLOBAL",
            )

        # Update stats label

        current = self.stats_label.text()

        if stat_name == "MINIMA":
            parts = current.split("|")

            if len(parts) >= 1:
                parts[0] = f"♟️ {value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "EVAL":
            display_value = value + getattr(self, "accumulated_evals", 0)

            parts = current.split("|")

            if len(parts) >= 2:
                parts[1] = f" 🎲 {display_value} "

            self.stats_label.setText("|".join(parts))

        elif stat_name == "COLOR":
            parts = current.split("|")

            if len(parts) >= 3:
                parts[2] = f" 🌈️ {value}"

            self.stats_label.setText("|".join(parts))

    def _on_intermediate_spectrum(self, data: Dict) -> None:
        """Callback for intermediate spectral update"""

        if data.get("type") != "intermediate":
            return

        rmse = data.get("rmse")

        evals = data.get("evals", 0) + getattr(self, "accumulated_evals", 0)

        rmse_valid = optim_rmse_is_valid_for_log(rmse)

        if rmse_valid:
            workflow_best = getattr(self, "_workflow_best_rmse", float("inf"))

            is_improved = rmse < workflow_best

            display_rmse = min(rmse, workflow_best)

            if is_improved:
                self._workflow_best_rmse = rmse

                display_rmse = rmse

                if "ep" in data:
                    self._update_pareto_record(data["ep"], rmse)

            if "ep" in data:
                self._stack_info_best_ep = np.asarray(data["ep"]).flatten().copy()

                self._stack_info_best_rmse = rmse

                now = getattr(self, "_stack_info_last_update", 0.0)


                t = time.time()

                if is_improved or (t - now) >= 1.0:
                    self._stack_info_last_update = t

                    QTimer.singleShot(0, self._update_substrate_info)

            self.best_rmse_label.setText(f"Best RMSE: {display_rmse:.6f}")

            # Update convergence plot (monotonic best solution only)

            current_best = rmse

            if not hasattr(self, "mse_data") or "errors" not in self.mse_data:
                self.mse_data = {"iterations": [], "errors": []}

            if self.mse_data["errors"] and len(self.mse_data["errors"]) > 0:
                previous_best = self.mse_data["errors"][-1]

                if current_best > previous_best:
                    current_best = previous_best

            # Append only if improved or first point (to avoid flat lines filling memory?)

            # Actually, showing flat line is good to see iterations.

            self.mse_data["iterations"].append(evals)

            self.mse_data["errors"].append(current_best)

            # Force update on main plot

            try:
                self.convergence_curve.setData(self.mse_data["iterations"], self.mse_data["errors"])

                # Update Detached Convergence Plots

                for widget in self._get_plot_targets("convergence", self.plot_convergence)[1:]:
                    items = widget.listDataItems()

                    if items:
                        items[0].setData(self.mse_data["iterations"], self.mse_data["errors"])

                    else:
                        # Should not happen if cloned correctly, but fallback

                        widget.plot(
                            self.mse_data["iterations"],
                            self.mse_data["errors"],
                            pen=pg.mkPen(CertusTheme.ERROR, width=2),
                        )

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.warning(f"Failed to update convergence plot: {e}")

            should_refresh_live = is_improved or not hasattr(self, "_live_curves") or not self._live_curves

            if should_refresh_live:
                try:
                    self._update_optim_live_plot(data)

                except NUMERICAL_FAULT_EXCEPTIONS as live_e:
                    logging.debug(f"Live plot update: {live_e}")

    def _update_optim_live_plot(self, data: Dict) -> None:
        """Updates the graph with the current curve and displays the current iteration.

        Updates Spectrum, Profile and n(lambda) regardless of which tab is displayed."""

        wls = data.get("wls")
        if wls is None:
            wls = data.get("wavelengths")
        if wls is None:
            return

        oblique_mode = data.get("oblique_mode", False)

        rmse = data.get("rmse")

        evals = data.get("evals", 0) + getattr(self, "accumulated_evals", 0)

        is_global_best = bool(data.get("is_global_best", False))

        rmse_valid = optim_rmse_is_valid_for_log(rmse)

        # Initial Cleanup

        if not hasattr(self, "_initial_cleared") or not self._initial_cleared:
            items_to_keep = [
                self.spectrum_plot.vLine,
                self.spectrum_plot.hLine,
                self.spectrum_plot.info_label,
            ]

            if self.target_scatter is not None:
                items_to_keep.append(self.target_scatter)

            for item in self.spectrum_plot.plotItem.items[:]:
                if item not in items_to_keep:
                    self.spectrum_plot.removeItem(item)

            self._initial_cleared = True

            self._live_curves = {}  # Dict to store curves in oblique mode

            self._live_points = None

        # Display by mode

        if oblique_mode:
            self._update_optim_live_plot_oblique_mode(data, wls)

        else:
            self._update_optim_live_plot_normal_mode(data, wls)

        self._refresh_optim_target_scatter_foreground()

        self._update_optim_live_plot_title(data, rmse_valid, rmse, evals, is_global_best)

        self._update_optim_live_profile_tabs(data)

    def _refresh_optim_target_scatter_foreground(self) -> None:
        """Ensure target scatter markers stay above live curves."""

        if self.target_scatter is None:
            return

        self.spectrum_plot.removeItem(self.target_scatter)

        self.spectrum_plot.addItem(self.target_scatter)

    def _update_optim_live_plot_title(
        self,
        data: Dict,
        rmse_valid: bool,
        rmse: Any,
        evals: int,
        is_global_best: bool,
    ) -> None:
        """Update the spectrum plot title with current optimization status."""

        status = "★ NEW BEST" if is_global_best else "Optimizing"

        color = "#10b981" if is_global_best else "#f97316"

        n_points = self.points_per_target_spin.value()

        n_total = len(self._get_optim_wls())

        n_layers_disp = len(data["ep"]) if "ep" in data else 0

        try:
            src_name = Path(getattr(self, "_last_config_file", "")).stem

            title_prefix = f"[{src_name}] " if src_name else ""

        except NUMERICAL_FAULT_EXCEPTIONS:
            title_prefix = ""

        rmse_str = f"{rmse:.6f}" if rmse_valid else "N/A"

        self.spectrum_plot.plotItem.setTitle(
            f"{title_prefix}{status} | Layers: {n_layers_disp} | Evals: {evals} | RMSE:  {rmse_str} | Points/Target: {n_points} ({n_total} total)",
            color=color,
            size="11pt",
        )

    def _update_optim_live_profile_tabs(self, data: Dict) -> None:
        """Refresh profile and n(lambda) tabs during live optimization updates."""

        if "ep" not in data:
            return

        try:
            ep_back = data.get("ep_back")

            if ep_back is None:
                ep_back = getattr(self, "ep_back_current", None)

            self._plot_profile(
                data["ep"],
                self._get_front_stack(),
                ep_back,
                self._get_back_stack(),
            )

            self._plot_nk()

        except NUMERICAL_FAULT_EXCEPTIONS as profile_err:
            logging.debug(f"Live profile/nk update: {profile_err}")

    def _update_optim_live_plot_oblique_mode(self, data: Dict, wls: np.ndarray) -> None:
        """Update live oblique spectra and detached plots."""

        spectra_display = data.get("spectra_display", {})

        oblique_tgts = data.get("oblique_tgts", [])

        if not oblique_tgts:
            oblique_tgts = self._get_oblique_tgts()

        if not hasattr(self, "_oblique_spectrum_colors"):
            self._oblique_spectrum_colors = {}

        else:
            self._oblique_spectrum_colors.clear()

        if not hasattr(self, "_live_curves"):
            self._live_curves = {}

        active_curve_keys = set()

        color_idx = 0

        for tgt in oblique_tgts:
            if not tgt.valid():
                continue

            sk3 = (tgt.angle, tgt.pol, tgt.include_backside)

            spec_key = sk3 if sk3 in spectra_display else (tgt.angle, tgt.pol)

            if spec_key not in spectra_display:
                continue

            if tgt.target_type not in spectra_display[spec_key]:
                continue

            spectrum = spectra_display[spec_key][tgt.target_type]

            if tgt.target_type == "R":
                color = "#dc2626"

            else:
                color = "#2563eb"

            tgt_id = (tgt.angle, tgt.pol, tgt.target_type, tgt.lmin, tgt.lmax)

            self._oblique_spectrum_colors[tgt_id] = color

            label = f"{tgt.target_type}{tgt.pol} ({tgt.angle}°)"

            curve_key = (tgt.angle, tgt.pol, tgt.target_type, tgt.include_backside)

            active_curve_keys.add(curve_key)

            if curve_key not in self._live_curves:
                self._live_curves[curve_key] = self.spectrum_plot.plot(
                    wls, spectrum, pen=pg.mkPen(color, width=2.5), name=label
                )

            else:
                self._live_curves[curve_key].setData(wls, spectrum)

            color_idx += 1

        self._update_oblique_detached_plots(oblique_tgts, spectra_display, wls)

        self._finalize_oblique_live_plot(active_curve_keys, wls)

    def _update_oblique_detached_plots(self, oblique_tgts: list, spectra_display: Dict, wls: np.ndarray) -> None:
        """Refresh detached spectrum widgets for oblique mode."""

        detached_targets = self._get_plot_targets("spectrum", self.spectrum_plot)[1:]

        for widget in detached_targets:
            widget.plotItem.clear()

        if not detached_targets:
            return

        for tgt in oblique_tgts:
            if not tgt.valid():
                continue

            sk3d = (tgt.angle, tgt.pol, tgt.include_backside)

            spec_key = sk3d if sk3d in spectra_display else (tgt.angle, tgt.pol)

            if spec_key not in spectra_display or tgt.target_type not in spectra_display[spec_key]:
                continue

            spectrum = spectra_display[spec_key][tgt.target_type]

            color = "#dc2626" if tgt.target_type == "R" else "#2563eb"

            label = f"{tgt.target_type}{tgt.pol} ({tgt.angle}°)"

            for widget in detached_targets:
                widget.plot(
                    wls,
                    spectrum,
                    pen=pg.mkPen(color, width=2.5),
                    name=label,
                )

    def _finalize_oblique_live_plot(self, active_curve_keys: set, wls: np.ndarray) -> None:
        """Finalize oblique live plot: cleanup, scaling, legend and redraw."""

        for curve_key in list(self._live_curves.keys()):
            if curve_key not in active_curve_keys:
                self.spectrum_plot.removeItem(self._live_curves[curve_key])

                del self._live_curves[curve_key]

        if hasattr(self, "_live_points") and self._live_points is not None:
            self.spectrum_plot.removeItem(self._live_points)

            self._live_points = None

        self.spectrum_plot.plotItem.setLabel("left", "R / T", color="black", size="12pt")

        auto_scale = self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True

        if not auto_scale:
            self.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            all_spectra = []

            for curve_key in self._live_curves:
                _, y_data = self._live_curves[curve_key].getData()

                if y_data is not None:
                    all_spectra.extend(y_data)

            if all_spectra:
                self._auto_scale_spectrum_y(np.array(all_spectra))

        if not hasattr(self.spectrum_plot.plotItem, "legend") or self.spectrum_plot.plotItem.legend is None:
            self.spectrum_plot.plotItem.addLegend(offset=(10, 10), labelTextSize="10pt")

        elif not self.spectrum_plot.plotItem.legend.isVisible():
            self.spectrum_plot.plotItem.legend.setVisible(True)

        self._rebuild_target_scatter(wls, True)

        self.spectrum_plot.update()

        self.spectrum_plot.repaint()

    def _update_optim_live_plot_normal_mode(self, data: Dict, wls: np.ndarray) -> None:
        """Update live transmission curve and sampled optimization points in normal mode."""

        Ts = data["Ts"]

        if not hasattr(self, "_live_curves") or "transmission" not in self._live_curves:
            if not hasattr(self, "_live_curves"):
                self._live_curves = {}

            self._live_curves["transmission"] = self.spectrum_plot.plot(
                wls,
                Ts,
                pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2.5),
                name="Transmission",
            )

        else:
            self._live_curves["transmission"].setData(wls, Ts)

        detached_targets = self._get_plot_targets("spectrum", self.spectrum_plot)[1:]

        for widget in detached_targets:
            widget.plotItem.clear()

            widget.plot(
                wls,
                Ts,
                pen=pg.mkPen(color=CertusTheme.PRIMARY, width=2.5),
                name="Transmission",
            )

        active_tgts = [t for t in self._get_tgts() if t.valid()]

        if active_tgts:
            mask = np.zeros(len(wls), dtype=bool)

            for t in active_tgts:
                mask |= (wls >= t.lmin) & (wls <= t.lmax)

            wls_filtered = wls[mask]

            Ts_filtered = Ts[mask]

            n_display_points = 50

            if len(wls_filtered) > n_display_points:
                clues = np.linspace(0, len(wls_filtered) - 1, n_display_points, dtype=int)

                wls_points = wls_filtered[clues]

                Ts_points = Ts_filtered[clues]

            else:
                wls_points = wls_filtered

                Ts_points = Ts_filtered

        else:
            wls_points = np.array([])

            Ts_points = np.array([])

        if len(wls_points) > 0:
            if not hasattr(self, "_live_points") or self._live_points is None:
                self._live_points = self.spectrum_plot.plot(
                    wls_points,
                    Ts_points,
                    pen=None,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=CertusTheme.ERROR,
                    name="Optim Points",
                )

            else:
                self._live_points.setData(wls_points, Ts_points)

        elif hasattr(self, "_live_points") and self._live_points is not None:
            self.spectrum_plot.removeItem(self._live_points)

            self._live_points = None

        self.spectrum_plot.plotItem.setLabel("left", "Transmission", color="black", size="12pt")

        auto_scale = self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True

        if not auto_scale:
            self.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            self._auto_scale_spectrum_y(Ts)

        self._rebuild_target_scatter(wls, False)

    def _apply_qw_values_to_front_table(self, qw: list[float], *, debug_failures: bool = False) -> None:
        """Apply QW values to the front table thickness column safely."""
        self.front_table.blockSignals(True)
        for r in range(self.front_table.rowCount()):
            try:
                sb = self.front_table.cellWidget(r, 1)
                if sb:
                    sb.setValue(qw[r] if r < len(qw) else 0.0)
            except (AttributeError, ValueError, IndexError) as e:
                if debug_failures:
                    logging.debug(f"Could not set qw value for row {r}: {e}")
        self.front_table.blockSignals(False)

    def _handle_stopped_workflow_result(self, d: Dict) -> None:
        """Finalize UI and keep best result when workflow is manually stopped."""
        self._stack_info_best_ep = None
        self._stack_info_best_rmse = None
        self.log("Workflow stopped by user.", "WARNING")
        self._set_busy(False)

        if d.get("ok", False) and d.get("ep") is not None:
            final_ep = np.asarray(d["ep"]).flatten()
            stack = self._get_front_stack()
            mats = self._get_materials()
            l0 = self.l0_spin.value()
            qw = optim_qwot_values_from_ep_stack(final_ep, stack, mats, l0)
            self._apply_qw_values_to_front_table(qw)
            self.ep_current = final_ep.copy()
            self._update_thickness_display()
            rmse = d.get("rmse", float("inf"))
            if optim_rmse_is_valid_for_log(rmse):
                self._workflow_best_rmse = rmse
                self._update_pareto_record(self.ep_current, rmse)
            rmse_msg = optim_rmse_display_string(rmse)
            self.log(f"Best result kept (RMSE: {rmse_msg}).", "SUCCESS")

        if get_export_config() and self.last_result:
            self._export_pending = True
            QTimer.singleShot(100, self.export_results)

    def _finalize_if_post_optim_budget_exceeded(self) -> bool:
        """Finalize workflow early when post-optimization orchestration exceeds time budget."""

        if getattr(self, "_post_optim_start_time", None) is None:
            self._post_optim_start_time = time.time()

        _n_layers = self.front_table.rowCount()
        _budget = optim_post_optim_time_budget_seconds(_n_layers)
        _elapsed = time.time() - self._post_optim_start_time

        if not (
            _elapsed > _budget
            and (
                hasattr(self, "_needle_cycle_step")
                or getattr(self, "_healing_phase", None) is not None
                or getattr(self, "_overshoot_active", False)
            )
        ):
            return False

        self.log(
            f"Time budget exceeded ({_elapsed:.0f}s > {_budget:.0f}s for {_n_layers} layers). Finalizing.",
            "WARNING",
        )

        self._healing_phase = None
        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)
            self._overshoot_active = False

        if get_export_config():
            self._export_pending = True
        self._schedule_eval(True)
        self.log("Optimization complete (time budget). Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False
        return True

    def _track_and_apply_post_optim_result(self, d: Dict) -> None:
        """Track workflow RMSE state and apply optimized QW values to the table."""
        final_ep = d["ep"]
        rmse_before_cleanup = d.get("rmse", float("inf"))

        if rmse_before_cleanup < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_before_cleanup

        if rmse_before_cleanup is not None and np.isfinite(rmse_before_cleanup) and rmse_before_cleanup >= 0.0:
            prev_gate_rmse = getattr(self, "_needle_recent_best_rmse", float("inf"))
            if rmse_before_cleanup < prev_gate_rmse - 1e-9:
                self._needle_recent_best_rmse = rmse_before_cleanup
                self._needle_no_improve_rounds = 0
            else:
                self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)
        else:
            self._needle_no_improve_rounds = min(getattr(self, "_needle_no_improve_rounds", 0) + 1, 1000)

        stack = self._get_front_stack()
        mats = self._get_materials()
        l0 = self.l0_spin.value()

        # Keep n4 convention for round-trip consistency with initialization.
        qw = []
        for i, layer in enumerate(stack):
            d_val = final_ep[i] if i < len(final_ep) else 0.0
            mat_obj = mats.get(layer.mat)
            n_val = 1.45
            if mat_obj:
                if hasattr(mat_obj, "n4"):
                    n_val = mat_obj.n4
                elif isinstance(mat_obj, dict):
                    n_val = mat_obj.get("n4", 1.45)
            val = (4.0 * n_val * d_val) / l0 if abs(l0) > 1e-9 else 0.0
            qw.append(val)

        self._apply_qw_values_to_front_table(qw, debug_failures=True)
        self._update_thickness_display()

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _handle_needle_cycle_step3(self, d: Dict) -> bool:
        """Handle Needle step-3 post-optimization logic. Returns True if flow consumed."""
        if not (hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 3):
            return False

        rmse_after_cleanup = d.get("rmse", float("inf"))
        needle_successful = False

        if self._needle_merit_before is not None:
            ok_gain, delta_abs, delta_rel, abs_thresh, rel_thresh = self._needle_gain_is_significant(
                self._needle_merit_before, rmse_after_cleanup
            )
            if ok_gain:
                self.log(
                    f"Needle cycle successful: DeltaRMSE={delta_abs:.6g} ({delta_rel * 100:.2f}%, "
                    f"thresholds abs>={abs_thresh:.6g} or rel>={rel_thresh * 100:.2f}%)",
                    "SUCCESS",
                )
                needle_successful = True
            else:
                self.log(
                    f"Needle cycle: gain too small (DeltaRMSE={delta_abs:.6g}, {delta_rel * 100:.2f}%)",
                    "WARNING",
                )
        else:
            self.log("Needle cycle: no improvement. Aborting needle.", "WARNING")
            self._revert_to_checkpoint()
            return True

        delattr(self, "_needle_cycle_step")
        delattr(self, "_needle_merit_before")

        current_count_after_clean = self.front_table.rowCount()
        last_count = getattr(self, "_last_cycle_layer_count", 0)
        if not hasattr(self, "_needle_stagnation_count"):
            self._needle_stagnation_count = 0

        if current_count_after_clean <= last_count and not needle_successful:
            self._needle_stagnation_count += 1
            self.log(
                f"Deep Needle: Stagnation detected ({self._needle_stagnation_count}/3)",
                "WARNING",
            )
        else:
            self._needle_stagnation_count = 0

        self._last_cycle_layer_count = current_count_after_clean
        if self._needle_stagnation_count >= 3:
            self.log(
                "Deep Needle: Aborting due to stagnation (3 cycles without growth or merit)",
                "ERROR",
            )
            delattr(self, "_needle_stagnation_count")
            if hasattr(self, "_last_cycle_layer_count"):
                delattr(self, "_last_cycle_layer_count")
            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = self._original_target_count
                self._overshoot_active = False
            self._revert_to_checkpoint()
            return True

        if current_count_after_clean < self._target_layer_count and current_count_after_clean < CFG.MAX_LAYERS:
            self.log(
                f"Deep Needle: {current_count_after_clean} layers (Target: {self._target_layer_count}). Growing...",
                "INFO",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            QTimer.singleShot(100, self._start_needle_process)
            return True

        if current_count_after_clean >= self._target_layer_count:
            if getattr(self, "_overshoot_active", False):
                original = self._original_target_count
                self.log(
                    f"Overshoot complete ({current_count_after_clean} layers). Pruning to {original}...",
                    "SUCCESS",
                )
                pruned = self._prune_to_target(original)
                self._overshoot_active = False
                self._overshoot_done = True
                self._target_layer_count = original
                current_rmse = d.get("rmse", float("inf"))
                checkpoint = getattr(self, "_pre_needle_checkpoint", None)
                if checkpoint and current_rmse > checkpoint["rmse"] * 1.02:
                    self.log(
                        f"Overshoot+Prune degraded RMSE ({current_rmse:.6f} > {checkpoint['rmse']:.6f}). Reverting.",
                        "WARNING",
                    )
                    self._revert_to_checkpoint()
                    return True
                if pruned > 0:
                    self.log(f"Pruned {pruned} thinnest layers. Final polish...", "INFO")
                    self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
                    self._post_prune = True
                    QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))
                    return True

            self.log(
                f"Deep Needle: Target reached ({self.front_table.rowCount()} layers)",
                "SUCCESS",
            )
            if hasattr(self, "_needle_fail_count"):
                delattr(self, "_needle_fail_count")
            return False

        self.log("Deep Needle: MAX_LAYERS reached", "WARNING")
        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")
        return False

    def _maybe_start_needle_growth(self) -> bool:
        """Start Needle growth/exploration when deficit or stagnation criteria are met."""
        current_count = self.front_table.rowCount()
        allow_growth = self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True
        has_deficit = current_count < self._target_layer_count
        stagnating = getattr(self, "_needle_no_improve_rounds", 0) >= getattr(self, "_needle_gate_no_improve_rounds", 2)
        needs_exploration = (
            allow_growth
            and stagnating
            and not getattr(self, "_overshoot_done", False)
            and not getattr(self, "_overshoot_active", False)
        )
        needs_needle = has_deficit or needs_exploration

        if not (needs_needle and current_count < CFG.MAX_LAYERS):
            return False

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]:
            return False

        if not getattr(self, "_overshoot_active", False) and not getattr(self, "_overshoot_done", False):
            import math

            self._original_target_count = self._target_layer_count
            if self._target_layer_count < CFG.MAX_LAYERS:
                ratio = getattr(self, "_needle_overshoot_ratio", 0.30)
                extra_layers = max(int(math.ceil(self._target_layer_count * ratio)), 4)
                overshoot = min(self._target_layer_count + extra_layers, CFG.MAX_LAYERS)
                self._target_layer_count = overshoot
                self._overshoot_active = True
                self.log(
                    f"Deep Needle Exploration: temporarily growing to {overshoot} layers "
                    f"(Target: {self._original_target_count}, +{extra_layers} extra for flexibility)",
                    "INFO",
                )

        self._pre_needle_checkpoint = {
            "ep": (self.ep_current.copy() if self.ep_current is not None else None),
            "rmse": self._workflow_best_rmse,
            "table": self._save_table_state(),
        }
        self.log(
            f"Checkpoint saved (RMSE={self._workflow_best_rmse:.6f}, {current_count} layers)",
            "INFO",
        )

        deficit = self._target_layer_count - current_count
        self.log(f"Layer deficit ({deficit}). Starting iterative Needle...", "INFO")
        self._start_needle_process()
        return True

    def _handle_decimation_polish_completion(self, d: Dict) -> bool:
        """Route decimation polish completion and bypass standard workflow."""
        if not getattr(self, "_decimation_polishing", False):
            return False

        if "ep" in d:
            self.ep_current = d["ep"].copy()
        rmse = d.get("rmse", getattr(self, "_workflow_best_rmse", float("inf")))
        if rmse < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse
        self._update_thickness_display()
        self._on_decimation_polish_done()
        return True

    def _handle_smart_decimation_followup(self, d: Dict) -> bool:
        """Advance smart decimation polish passes when enabled."""
        if not hasattr(self, "_smart_decimation_step"):
            return False

        polish_pass = getattr(self, "_smart_decimation_polish_pass", 0)
        if polish_pass == 1:
            self._smart_decimation_polish_pass = 2
            self.run_optim("local", keep_history=True)
            return True

        self._smart_decimation_polish_pass = 0
        self._on_smart_decimation_optim_done(d)
        return True

    def _is_in_needle_cycle(self) -> bool:
        """Return True when post-optim workflow is inside Needle cycle states."""
        return hasattr(self, "_needle_cycle_step") and self._needle_cycle_step in [1, 2, 3]

    def _run_post_optim_cleanup(self, d: Dict) -> int:
        """Apply post-prune/cleanup hook and return removed layer count."""
        if getattr(self, "_post_prune", False):
            self._post_prune = False
            self.log(f"Post-prune polish done. RMSE={d.get('rmse', '?')}", "INFO")
            return 0

        if not self._is_in_needle_cycle():
            return self.smart_cleanup(update_target=False)
        return 0

    def _handle_healing_workflow(self, removed: int) -> bool:
        """Drive two-phase healing after cleanup-induced topology changes."""
        if removed > 0 and not self._is_in_needle_cycle():
            self.log(
                f"Smart cleanup removed {removed} layers. Healing (restricted global)...",
                "INFO",
            )
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            self._healing_phase = "global"
            QTimer.singleShot(50, lambda: self.run_optim("healing", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "global":
            self._healing_phase = "local"
            self.log("Healing: local polish...", "INFO")
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)
            QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))
            return True

        if getattr(self, "_healing_phase", None) == "local":
            self._healing_phase = None
        return False

    def _finalize_completed_optimization_workflow(self) -> None:
        """Finalize stable workflow state and trigger final evaluation/export."""
        self._apply_5nm_minimum()  # Hard rule: no layer < 5nm in final design

        # Set export flag BEFORE scheduling eval (eval callback checks this flag)
        if get_export_config():
            self._export_pending = True

        # Force final Pareto update with best RMSE
        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)
        self.log("Optimization complete & Structure stable.", "SUCCESS")
        self._set_busy(False)
        self._is_internal_restart = False

        # PARETO DECIMATION: iteratively remove thinnest layer, re-polish, record
        if not getattr(self, "_decimation_done", False) and self.front_table.rowCount() > 4:
            self._decimation_done = True
            QTimer.singleShot(200, self._start_smart_pareto_decimation)

    def _on_optim_done(self, d: Dict) -> None:
        """Central callback after any optimization completes.

        This is the main state machine driving the hybrid design workflow.

        It is called after every optimization (global, healing, or local)

        and decides the next action based on the current workflow state.

        Decision flow (executed in order):

        1. **QW update**: Write optimized thicknesses back to the GUI table.

        2. **Needle step transition**: If in needle cycle step 1, record RMSE

           and transition to step 2 (cleanup phase).

        3. **Smart cleanup**: Remove layers < 1 nm and merge adjacent identical

           materials (skipped during needle cycle to avoid interference).

           Uses ``update_target=False`` to preserve the original layer count

           target so the Needle can grow back removed layers.

        4. **Healing trigger**: If cleanup removed layers (and not in needle

           cycle), start the two-phase healing sequence:

           - Phase 1 (``'healing'``): Restricted PGLOBAL within +/-Deltad = lambda₀/(10·n)

             to explore nearby basins after topology change.

           - Phase 2 (``'local'``): L-BFGS-B polish to guarantee precise

             convergence (never skipped).

        5. **Needle cycle management** (steps 2->3): Cleanup after needle

           insertion, evaluate RMSE improvement (>1% threshold), check

           stagnation (3 cycles without progress -> abort).

        6. **Case B - Layer deficit**: If current count < target, activate

           Overshoot & Prune on first deficit (+20% extra layers via Needle,

           then prune thinnest back to original target).

        7. **Case C - Complete**: Target reached, export results.

        This method performs workflow management including:

        - Result processing and GUI updates

        - State machine transitions

        - Needle cycle management

        - Healing sequence coordination

        - Progress tracking and logging

        Args:

            self: CertusDesign instance

            d: Optimization result dictionary

        Returns:

            None

        Notes:

            - Logs workflow transitions and decisions

            - Handles complex state machine logic

            - Manages needle insertion cycles

            - Coordinates healing and cleanup phases"""

        self.progress_widget.stop("Optimization complete")

        self._clean_live_curves()

        self._initial_cleared = False

        if getattr(self, "_workflow_stopped", False):
            self._handle_stopped_workflow_result(d)

            return

        if not d.get("ok", False):
            self.log("Optimization stopped or failed.", "ERROR")

            self._set_busy(False)

            return

        self._stack_info_best_ep = None

        self._stack_info_best_rmse = None

        QTimer.singleShot(50, self.optimization_finished_signal.emit)

        # PARETO DECIMATION: if we are polishing after decimation, route to decimation handler
        if self._handle_decimation_polish_completion(d):
            return

        # TIME BUDGET for post-optimization workflow (cleanup/healing/needle)
        if self._finalize_if_post_optim_budget_exceeded():
            return

        # Track best RMSE and refresh table/QW state.
        self._track_and_apply_post_optim_result(d)

        # Check if we're in smart decimation mode
        if self._handle_smart_decimation_followup(d):
            return

        # Needle loop management: Needle -> Optim -> Evaluate

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 1:
            # Step 1 done: Optim after Needle insertion

            # _needle_merit_before was set to pre-needle RMSE in _start_needle_process

            self._needle_cycle_step = 2  # Proceed to step 2 (skip cleanup) then 3

        # POST-OPTIM HOOK: Smart cleanup (only if not in Needle cycle and not post-prune)

        # update_target=False: preserve original target so Needle can grow back

        removed = self._run_post_optim_cleanup(d)

        self.front_table.rowCount()

        # HEALING: If cleanup removed layers, restricted global + local polish

        # But only if not in Needle cycle

        if self._handle_healing_workflow(removed):
            return

        # If in Needle cycle and step==2, skip cleanup and go to evaluation

        # (cleanup during needle causes add-remove loop -> stagnation)

        if hasattr(self, "_needle_cycle_step") and self._needle_cycle_step == 2:
            self._needle_cycle_step = 3

        if self._handle_needle_cycle_step3(d):
            return

        # Case B: Layer deficit OR Needle Exploration requested
        if self._maybe_start_needle_growth():
            return

        # Case C: Complete - final 5nm enforcement then eval
        self._finalize_completed_optimization_workflow()

    def _build_pareto_table_state(self, ep: np.ndarray) -> list[Dict[str, Any]]:
        """Rebuild table snapshot from thickness vector and current UI material/var states."""
        mats = self._get_materials()
        l0 = self.l0_spin.value()
        state: list[Dict[str, Any]] = []
        table_rows = self.front_table.rowCount()

        for r in range(min(len(ep), table_rows)):
            mat = self._safe_get_combo_text(r, 0)
            d_val = ep[r]

            mat_obj = mats.get(mat)
            n_val = 1.45
            if mat_obj:
                if hasattr(mat_obj, "n4"):
                    n_val = mat_obj.n4
                elif isinstance(mat_obj, dict):
                    n_val = mat_obj.get("n4", 1.45)

            qw_val = (4.0 * n_val * d_val) / l0 if abs(l0) > 1e-9 else 0.0

            var = True
            cw = self.front_table.cellWidget(r, 3)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb:
                    var = cb.isChecked()

            state.append({"mat": mat, "qw": qw_val, "var": var})

        return state

    def _pareto_variable_indices(self, ep: np.ndarray) -> np.ndarray:
        """Return indices of variable layers from the current table state."""
        var_list: list[int] = []
        for r in range(min(len(ep), self.front_table.rowCount())):
            var = True
            cw = self.front_table.cellWidget(r, 3)
            if cw:
                cb = cw.findChild(QCheckBox)
                if cb:
                    var = cb.isChecked()
            if var:
                var_list.append(r)
        return np.array(var_list, dtype=np.int64)

    def _compute_pareto_mc_rmse(self, current_ep: np.ndarray, rmse_val: float) -> float:
        """Estimate robust RMSE with lightweight MC sampling around current thicknesses."""
        mc_rmse = rmse_val
        local_seed = int(getattr(self, "run_seed", 0) or 0)
        rng = np.random.default_rng(local_seed)
        var_idx = self._pareto_variable_indices(current_ep)

        if len(var_idx) == 0:
            return mc_rmse

        def _compute_mc_evals(cost_func) -> Any:
            evals = []
            for _ in range(5):  # quick MC estimate
                noise = rng.normal(0, 0.3, size=current_ep.shape)
                noisy_ep = np.maximum(current_ep + noise, 0)
                try:
                    mse = cost_func(noisy_ep[var_idx])
                    if mse is not None and mse < 1e20:
                        evals.append(np.sqrt(mse))
                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ):
                    pass
            return evals

        if hasattr(self, "optim_worker") and hasattr(self.optim_worker, "cost_func"):
            mc_evals = _compute_mc_evals(self.optim_worker.cost_func)
            if mc_evals:
                return float(np.mean(mc_evals))

        if hasattr(self, "_last_cost_func") and self._last_cost_func is not None:
            mc_evals = _compute_mc_evals(self._last_cost_func)
            if mc_evals:
                return float(np.mean(mc_evals))

        return mc_rmse

    def _update_pareto_rmse_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        rmse_val: float,
        mc_rmse: float,
    ) -> bool:
        """Update the theoretical RMSE champion for this layer count."""
        if rmse_val >= rec["best_rmse"] - 1e-6:
            return False

        rec["best_rmse"] = rmse_val
        rec["ep_rmse"] = current_ep.copy()
        rec["table_rmse"] = self._build_pareto_table_state(current_ep)
        rec["mc_of_best_rmse"] = mc_rmse
        rec["dmin_rmse"] = float(np.min(current_ep[current_ep > 0.01])) if np.any(current_ep > 0.01) else 0.0
        return True

    def _update_pareto_mc_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        mc_rmse: float,
    ) -> bool:
        """Update the robust MC champion for this layer count."""
        if mc_rmse >= rec["best_mc"] - 1e-6:
            return False

        rec["best_mc"] = mc_rmse
        rec["ep_mc"] = current_ep.copy()
        rec["table_mc"] = self._build_pareto_table_state(current_ep)
        rec["dmin_mc"] = float(np.min(current_ep[current_ep > 0.01])) if np.any(current_ep > 0.01) else 0.0
        return True

    def _update_pareto_fab_champion(
        self,
        rec: Dict[str, Any],
        current_ep: np.ndarray,
        rmse_val: float,
    ) -> bool:
        """Update manufacturable champion when all layers satisfy >=5nm."""
        is_fabricable = (current_ep is not None) and np.all(current_ep >= 5.0)
        if not is_fabricable or rmse_val >= rec["best_fab"] - 1e-6:
            return False

        rec["best_fab"] = rmse_val
        rec["ep_fab"] = current_ep.copy()
        rec["table_fab"] = self._build_pareto_table_state(current_ep)
        rec["dmin_fab"] = float(np.min(current_ep))  # >= 5.0 guaranteed
        return True

    def _update_pareto_record(self, current_ep=None, current_rmse=None) -> None:
        """Records current configuration in Pareto history if strictly better.

        ==============================================================================

        BARRIER PROTECTION: DO NOT MODIFY THIS STRUCTURE WITHOUT UNDERSTANDING

        ==============================================================================

        Maintains THREE champions per layer count N:

          - 'best_rmse': lowest theoretical RMSE (can have layers < 5nm)

          - 'best_mc': lowest MC RMSE (most robust to +/-0.3nm thickness errors)

          - 'best_fab': lowest RMSE with ALL layers >= 5nm (manufacturable)

        IMPORTANT: best_fab guarantees that no layers < 5nm are stored

        =============================================================================="""

        if current_ep is None:
            current_ep = self.ep_current

            if current_ep is None:
                return

        if current_rmse is None or not np.isfinite(current_rmse) or current_rmse < 0.0:
            return

        N = len(current_ep)

        rmse_val = current_rmse

        if rmse_val > 10.0:  # Assoupli pour permettre tous les designs raisonnables
            return

        # Manufacturing rule: we tolerate everything in Pareto (> 0.1nm)

        # but we will display in red in the table if < 5nm.

        if isinstance(current_ep, list):
            current_ep = np.array(current_ep)

        if np.any(current_ep < 0.1):
            return

        # --- Compute MC RMSE ---
        mc_rmse = self._compute_pareto_mc_rmse(current_ep, rmse_val)

        # =====================================================================

        # BARRIER: Pareto History Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

        # =====================================================================

        rec = self.pareto_history.setdefault(
            N,
            {
                "best_rmse": float("inf"),
                "ep_rmse": None,
                "table_rmse": None,
                "best_mc": float("inf"),
                "ep_mc": None,
                "table_mc": None,
                "best_fab": float("inf"),
                "ep_fab": None,
                "table_fab": None,
            },
        )

        # =====================================================================

        updated = False

        # =====================================================================

        # BARRIERE: Logique des 3 champions - NE PAS MODIFIER L'ORDRE

        # =====================================================================

        # Champion 1: best theoretical RMSE (peut avoir layers < 5nm)
        if self._update_pareto_rmse_champion(rec, current_ep, rmse_val, mc_rmse):
            updated = True

        # Champion 2: best MC RMSE (most robust design)
        if self._update_pareto_mc_champion(rec, current_ep, mc_rmse):
            updated = True

        # =====================================================================

        # BARRIERE: Champion 3 - best_fab (FABRICABLE) - LOGIQUE CRITIQUE

        # =====================================================================

        # Seulement si TOUTES les layers >= 5nm
        if self._update_pareto_fab_champion(rec, current_ep, rmse_val):
            updated = True

        # =====================================================================

        if updated:
            QTimer.singleShot(0, self._refresh_pareto_table)

    def _refresh_pareto_table(self) -> None:

        # =====================================================================

        # BARRIER: Pareto Display Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

        # =====================================================================

        self.pareto_table.setRowCount(0)

        for d, N in enumerate(sorted(self.pareto_history.keys())):
            self.pareto_table.insertRow(d)
            rec = self.pareto_history[N]
            self._populate_pareto_table_row(d, N, rec)

    def _populate_pareto_table_row(self, row_index: int, n_layers: int, rec: Dict[str, Any]) -> None:
        """Render one row of the Pareto table, preserving fixed column semantics."""
        # Colonne 0: N
        i_layers = QTableWidgetItem(str(n_layers))
        i_layers.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_layers.setToolTip(
            "Double-click col.1-2 = load best theoretical\n"
            "Double-click col.3-4 = load best robust\n"
            "Double-click col.5-6 = load best manufacturable"
        )

        # Column 1: Best RMSE (theoretical, can be <5nm)
        i_rmse = QTableWidgetItem(f"{rec.get('best_rmse', float('inf')):.5f}")
        i_rmse.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_rmse.setToolTip("Best theoretical RMSE (may have layers < 5nm)")

        # Colonne 2: d_min RMSE
        dmin_rmse = rec.get("dmin_rmse", 0)
        i_dmin_rmse = QTableWidgetItem(f"{dmin_rmse:.1f}")
        i_dmin_rmse.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_rmse < 5.0:  # Visual warning if below critical 5nm limit
            i_dmin_rmse.setForeground(Qt.GlobalColor.red)
        i_dmin_rmse.setToolTip("Min. thickness of RMSE champion")

        # Column 3: Best MC (robust, can be <5nm)
        i_mc = QTableWidgetItem(f"{rec.get('best_mc', float('inf')):.5f}")
        i_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_mc.setToolTip("Best robust RMSE (MC +/-0.3nm)")

        # Colonne 4: d_min MC
        dmin_mc = rec.get("dmin_mc", 0)
        i_dmin_mc = QTableWidgetItem(f"{dmin_mc:.1f}")
        i_dmin_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_mc < 5.0:  # Visual warning if below critical 5nm limit
            i_dmin_mc.setForeground(Qt.GlobalColor.red)
        i_dmin_mc.setToolTip("Min. thickness of MC champion")

        # =====================================================================
        # BARRIER: Columns 5-6 - Best Fab (FABRICABLE) - CRITICAL LOGIC
        # =====================================================================
        best_fab = rec.get("best_fab", float("inf"))
        i_fab = QTableWidgetItem(f"{best_fab:.5f}" if best_fab < float("inf") else "-")
        i_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if best_fab < float("inf"):
            i_fab.setToolTip("Best manufacturable RMSE (all layers >= 5nm)")
            i_fab.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_fab.setToolTip("No manufacturable design found for this N")
            i_fab.setForeground(Qt.GlobalColor.gray)

        # Column 6: d_min Fab (must be >= 5.0 by definition)
        dmin_fab = rec.get("dmin_fab", 0)
        i_dmin_fab = QTableWidgetItem(f"{dmin_fab:.1f}" if dmin_fab > 0 else "-")
        i_dmin_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_fab >= 5.0:
            i_dmin_fab.setForeground(Qt.GlobalColor.darkGreen)
            i_dmin_fab.setToolTip("Min. thickness of manufacturable champion (>=5.0nm guaranteed)")
        else:
            i_dmin_fab.setForeground(Qt.GlobalColor.gray)
            i_dmin_fab.setToolTip("No manufacturable design")

        # Colonne 7: RMSE/N efficiency metric
        best_rmse_val = rec.get("best_rmse", float("inf"))
        rmse_per_n = best_rmse_val / n_layers if n_layers > 0 and best_rmse_val < float("inf") else float("inf")
        i_eff = QTableWidgetItem(f"{rmse_per_n * 1000:.4f}" if rmse_per_n < float("inf") else "-")
        i_eff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        i_eff.setToolTip("RMSE/N ×1000 - efficiency: lower = better complexity/performance balance")

        # =====================================================================
        # BARRIER: Column order - DO NOT MODIFY
        # =====================================================================
        self.pareto_table.setItem(row_index, 0, i_layers)  # N
        self.pareto_table.setItem(row_index, 1, i_rmse)  # Best RMSE
        self.pareto_table.setItem(row_index, 2, i_dmin_rmse)  # d_min RMSE
        self.pareto_table.setItem(row_index, 3, i_mc)  # Best MC
        self.pareto_table.setItem(row_index, 4, i_dmin_mc)  # d_min MC
        self.pareto_table.setItem(row_index, 5, i_fab)  # Best Fab
        self.pareto_table.setItem(row_index, 6, i_dmin_fab)  # d_min Fab
        self.pareto_table.setItem(row_index, 7, i_eff)  # RMSE/N

    def _restore_pareto_champion(self, table_state: list[Dict[str, Any]], ep: np.ndarray) -> None:
        """Restore table state and current thicknesses from a stored Pareto champion."""
        self._restore_table_state(table_state)
        self.ep_current = ep.copy()
        self._update_thickness_display()
        self._use_exact_ep = True

    def _load_pareto_design(self, row: int, col: int) -> None:

        try:
            N = int(self.pareto_table.item(row, 0).text())

            rec = self.pareto_history[N]

            # col 1-2 = load best RMSE; col 3-4 = load best MC; col 5-6 = load best Fab

            load_mc = col >= 3 and col <= 4

            load_fab = col >= 5 and col <= 6

            if load_fab and rec.get("ep_fab") is not None:
                self._restore_pareto_champion(rec["table_fab"], rec["ep_fab"])

                self.log(
                    f" Loaded FAB champion for N={N} (RMSE={rec['best_fab']:.6f}, d_min={rec['dmin_fab']:.1f}nm)",
                    "SUCCESS",
                )

            elif load_mc and rec.get("ep_mc") is not None:
                self._restore_pareto_champion(rec["table_mc"], rec["ep_mc"])

                self.log(f"Loaded MC champion for N={N} (RMSE={rec['best_mc']:.6f})", "INFO")

            elif rec.get("ep_rmse") is not None:
                self._restore_pareto_champion(rec["table_rmse"], rec["ep_rmse"])

                self.log(f"Loaded RMSE champion for N={N} (RMSE={rec['best_rmse']:.6f})", "INFO")

            # Switch view to Structure and run Eval to update plot

            self.front_tabs.setCurrentIndex(0)

            self._schedule_eval(True)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Failed to load Pareto design: {e}", "ERROR")

    def _clear_pareto(self) -> None:

        self.pareto_history = {}

        self._decimation_done = False

        self._refresh_pareto_table()

    # =====================================================================

    # PARETO DECIMATION: remove thinnest -> merge -> re-polish -> record -> loop

    # =====================================================================

    def _start_smart_pareto_decimation(self) -> None:
        """Smart Pareto Decimation: start from best solution and iteratively remove thinnest layers.

        Process:

        1. Checkpoint the best solution (ep + RMSE + table)

        2. Remove thinnest layer -> merge adjacent

        3. Re-optimize locally

        4. Update Pareto only if RMSE for this N is improved

        5. If RMSE degrades > DEGRADATION_LIMIT vs initial -> stop & revert

        6. Continue until N/2 reached

        7. Revert to original best solution at the end

        """

        N_start = self.front_table.rowCount()

        if N_start <= 4 or self.ep_current is None:
            self.log("Smart Pareto Decimation: skip (too few layers or no design)", "INFO")

            return

        # Calculate target minimum layers (N/2)

        N_min_target = max(4, int(N_start / 2))

        self._initialize_smart_decimation_session(N_start, N_min_target)

        self.log(
            f"🎯 Smart Pareto Decimation: {N_start} -> {N_min_target} layers"
            f" | RMSE ref={self._smart_deci_origin_rmse:.6f}",
            "INFO",
        )

        self._set_busy(True)

        self._smart_decimation_step = 0

        QTimer.singleShot(100, self._smart_decimation_remove_and_optimize)

    def _initialize_smart_decimation_session(self, n_start: int, n_min_target: int) -> None:
        """Initialize and checkpoint Smart Pareto Decimation session state."""
        # Checkpoint the initial best solution to restore at end
        self._smart_deci_origin_ep = self.ep_current.copy()
        self._smart_deci_origin_rmse = getattr(self, "_workflow_best_rmse", float("inf"))
        self._smart_deci_origin_table = self._save_table_state()
        self._smart_deci_origin_N = n_start

        self._smart_decimation_start_N = n_start
        self._smart_decimation_min_N = n_min_target
        self._smart_decimation_best_rmse = self._smart_deci_origin_rmse

    def _smart_decimation_remove_and_optimize(self) -> None:
        """One step of smart decimation: remove thinnest layer and re-optimize."""

        current_N = self.front_table.rowCount()

        if self._should_stop_smart_decimation_step(current_N):
            return

        self._smart_decimation_step += 1

        ep = self.ep_current

        if ep is None or len(ep) != current_N:
            self._finish_smart_decimation()

            return

        # Apply 5nm manufacturability filter before recording
        # (layers already < 5nm counted as candidates to remove first)
        thinnest_idx = self._select_smart_decimation_remove_index(ep)

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        rmse_before = getattr(self, "_workflow_best_rmse", float("inf"))

        self.log(
            f"📉 Step {self._smart_decimation_step}: N={current_N}->{current_N - 1}"
            f" | remove layer {thinnest_idx} ({thinnest_mat}, {thinnest_d:.1f}nm)"
            f" | RMSE={rmse_before:.6f}",
            "INFO",
        )

        # Remove the selected layer

        self.front_table.removeRow(thinnest_idx)
        self._apply_smart_decimation_post_removal_state()

        self.run_optim("local", keep_history=True)

    def _apply_smart_decimation_post_removal_state(self) -> None:
        """Apply state updates required after removing one layer during decimation."""
        self._merge_adjacent_layers()
        self._update_layer_count()

        # Rebuild ep_current from table after removal + merge.
        self._update_thickness_display()

        # Reset best RMSE for the new N so local search is unconstrained by old N.
        self._workflow_best_rmse = float("inf")

        # Use double local polish: pass 1 explores, pass 2 tightens convergence.
        self._smart_decimation_polish_pass = 1

    def _should_stop_smart_decimation_step(self, current_n: int) -> bool:
        """Return True when smart decimation should stop at the current step."""
        # Stopping condition: reached N/2 target
        if current_n <= self._smart_decimation_min_N:
            self._finish_smart_decimation()
            return True

        if self._smart_decimation_step >= 50:  # Safety limit
            self.log("Smart decimation: safety limit reached", "WARNING")
            self._finish_smart_decimation()
            return True

        return False

    def _select_smart_decimation_remove_index(self, ep: np.ndarray) -> int:
        """Pick layer index to remove, prioritizing sub-5nm layers."""
        sub5nm = [i for i, d in enumerate(ep) if d < 5.0]
        if sub5nm:
            # Prefer removing a sub-5nm layer over the generic thinnest
            return sub5nm[int(np.argmin([ep[i] for i in sub5nm]))]
        return int(np.argmin(ep))

    def _on_smart_decimation_optim_done(self, data) -> None:
        """Called after local optimization during smart decimation."""

        if not data or "rmse" not in data:
            self.log("Smart decimation: optimization failed", "ERROR")

            self._finish_smart_decimation()

            return

        rmse_after = data["rmse"]

        current_N = self.front_table.rowCount()

        ref_rmse = self._smart_deci_origin_rmse

        self._apply_smart_decimation_optim_result(data, rmse_after)

        # DEGRADATION GUARD: stop if RMSE > 2× initial reference
        if self._abort_on_smart_decimation_degradation(rmse_after, ref_rmse):
            return

        self._record_smart_decimation_candidate(current_N, rmse_after)

        # Continue to next step

        QTimer.singleShot(200, self._smart_decimation_remove_and_optimize)

    def _apply_smart_decimation_optim_result(self, data: Dict[str, Any], rmse_after: float) -> None:
        """Apply optimization payload and refresh best-RMSE tracking."""
        if "ep" in data:
            self.ep_current = data["ep"].copy()
            self._update_thickness_display()

        if rmse_after < getattr(self, "_workflow_best_rmse", float("inf")):
            self._workflow_best_rmse = rmse_after

    def _record_smart_decimation_candidate(self, current_n: int, rmse_after: float) -> None:
        """Record current design into Pareto and emit step log."""
        ep = self.ep_current
        has_sub5nm = (ep is not None) and np.any(ep < 5.0)

        # _update_pareto_record already enforces strictly-better updates.
        self._update_pareto_record(self.ep_current, rmse_after)
        self._log_smart_decimation_step_result(current_n, rmse_after, has_sub5nm)

    def _abort_on_smart_decimation_degradation(self, rmse_after: float, ref_rmse: float) -> bool:
        """Abort decimation when RMSE degrades beyond configured safety factor."""
        degradation_limit = 2.0
        if rmse_after <= ref_rmse * degradation_limit:
            return False

        self.log(
            f"   🛑 RMSE {rmse_after:.6f} > {degradation_limit}× ref ({ref_rmse:.6f}) - stopping decimation",
            "WARNING",
        )
        self._finish_smart_decimation()
        return True

    def _log_smart_decimation_step_result(
        self,
        current_n: int,
        rmse_after: float,
        has_sub5nm: bool,
    ) -> None:
        """Log per-step Smart Decimation outcome against current Pareto champion."""
        n_record = self.pareto_history.get(current_n, {})
        best_rmse_for_n = n_record.get("best_rmse", float("inf"))
        flag = " [sub5nm]" if has_sub5nm else ""

        if abs(rmse_after - best_rmse_for_n) < 1e-6:
            # This IS the new champion (we just set it)
            self.log(f"   ✅ N={current_n}: {rmse_after:.6f}{flag}", "SUCCESS")
            return

        self.log(
            f"   - N={current_n}: {rmse_after:.6f} (best={best_rmse_for_n:.6f}){flag}",
            "INFO",
        )

    def _restore_smart_decimation_origin(self, start_n: int) -> None:
        """Restore the checkpointed pre-decimation design when available."""
        origin_ep = getattr(self, "_smart_deci_origin_ep", None)
        origin_rmse = getattr(self, "_smart_deci_origin_rmse", float("inf"))
        origin_table = getattr(self, "_smart_deci_origin_table", None)

        if origin_ep is None or origin_table is None:
            return

        self._restore_table_state(origin_table)
        self.ep_current = origin_ep.copy()
        self._update_thickness_display()
        self._workflow_best_rmse = origin_rmse
        self._use_exact_ep = True
        self.log(
            f"↩️  Reverted to original best solution ({start_n} layers, RMSE={origin_rmse:.6f})",
            "INFO",
        )

    def _clear_smart_decimation_state(self) -> None:
        """Delete transient Smart Decimation runtime attributes."""
        attrs = (
            "_smart_decimation_start_N",
            "_smart_decimation_min_N",
            "_smart_decimation_current_N",
            "_smart_decimation_best_rmse",
            "_smart_decimation_step",
            "_smart_deci_origin_ep",
            "_smart_deci_origin_rmse",
            "_smart_deci_origin_table",
            "_smart_deci_origin_N",
            "_smart_decimation_polish_pass",
            "_smart_decimation_healing",
        )
        for attr in attrs:
            if hasattr(self, attr):
                delattr(self, attr)

    def _log_smart_decimation_completion(self, total_steps: int, start_n: int, end_n: int) -> None:
        """Log Smart Pareto Decimation completion summary."""
        pareto_count = len(self.pareto_history)
        self.log(
            f"🎯 Smart Pareto Decimation complete:"
            f" {total_steps} steps | {start_n}->{end_n} layers | {pareto_count} Pareto records",
            "SUCCESS",
        )

    def _finish_smart_decimation(self) -> None:
        """Clean up after smart decimation and REVERT to original best solution."""

        total_steps = getattr(self, "_smart_decimation_step", 0)

        start_N = getattr(self, "_smart_decimation_start_N", 0)

        # --- REVERT to original best solution ---
        self._restore_smart_decimation_origin(start_N)

        end_N = self.front_table.rowCount()
        self._log_smart_decimation_completion(total_steps, start_N, end_N)

        self._set_busy(False)

        # Cleanup decimation state
        self._clear_smart_decimation_state()

        self._finalize_smart_decimation_post_actions()

    def _finalize_smart_decimation_post_actions(self) -> None:
        """Run final UI/eval/export actions after decimation cleanup."""
        # Enforce hard 5nm rule on the final returned design in the UI
        self._apply_5nm_minimum()

        # Final eval with restored design
        self._schedule_eval(True)

        # Generate grouped Pareto report if auto-export enabled
        if get_export_config() and len(self.pareto_history) > 1:
            QTimer.singleShot(500, self._export_pareto_report)

    def _export_pareto_report(self) -> None:
        """Export a grouped HTML report summarizing the full Pareto front."""

        try:
            from certus_data import generate_html_report
            from certus_data import get_missing_manifest_fields

            from certus_core import get_resource_path

            if not self.pareto_history:
                return

            reports_dir = get_resource_path("reports")

            os.makedirs(reports_dir, exist_ok=True)

            ts = certus_timestamp_file()

            filename = str(Path(reports_dir) / f"Pareto_Summary_{ts}.html")

            manifest_dict: dict[str, Any] = {}
            try:
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                seed_val = None
                for _seed_candidate in (
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                ):
                    if _seed_candidate is None:
                        continue
                    try:
                        seed_val = int(_seed_candidate)
                        break
                    except (TypeError, ValueError):
                        continue
                svc = IndexFitService(runner=lambda _cfg: dict(getattr(self, "pareto_history", {}) or {}))
                req = IndexFitRequest(
                    config={
                        "module": "CERTUS_DESIGN",
                        "export_kind": "pareto_summary",
                        "pareto_count": int(len(self.pareto_history)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "filename", "") or "").strip(),
                            str(getattr(self, "_last_config_file", "") or "").strip(),
                        )
                        if p
                    ],
                    seed=seed_val,
                    app_id="CERTUS_DESIGN",
                    app_version=__version__,
                    warnings=list(getattr(self, "validation_warnings", []) or []),
                    status=status_val,
                )
                manifest_dict = svc.fit(req).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.log(f"Pareto manifest generation failed: {exc}", "WARNING")
                manifest_dict = {}

            missing_manifest_fields = get_missing_manifest_fields(manifest_dict)
            if missing_manifest_fields:
                self.log(
                    "Pareto report blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
                    "WARNING",
                )
                return

            # =====================================================================

            # BARRIER: HTML Report Structure - DO NOT MODIFY WITHOUT UNDERSTANDING

            # =====================================================================

            # Build summary table rows

            rows = []

            for N in sorted(self.pareto_history.keys()):
                rec = self.pareto_history[N]

                best_rmse = rec.get("best_rmse", float("inf"))

                best_mc = rec.get("best_mc", float("inf"))

                best_fab = rec.get("best_fab", float("inf"))

                dmin_r = rec.get("dmin_rmse", 0.0)

                dmin_m = rec.get("dmin_mc", 0.0)

                dmin_f = rec.get("dmin_fab", 0.0)

                rmse_per_n = best_rmse / N if N > 0 and best_rmse < float("inf") else float("inf")

                # Fabricability flags

                fab_ok_fab = dmin_f >= 5.0 and best_fab < float("inf")

                rows.append(
                    [
                        str(N),
                        f"{best_rmse:.6f}" if best_rmse < float("inf") else "-",
                        f"{dmin_r:.1f}",
                        f"{best_mc:.6f}" if best_mc < float("inf") else "-",
                        f"{dmin_m:.1f}",
                        f"{best_fab:.6f}" if best_fab < float("inf") else "-",
                        f"{dmin_f:.1f}" if dmin_f > 0 else "-",
                        f"{rmse_per_n * 1000:.4f}" if rmse_per_n < float("inf") else "-",
                        "✅" if fab_ok_fab else ("⚠️" if best_fab < float("inf") else "-"),
                    ]
                )

            # =====================================================================

            sections = [
                {
                    "title": "Pareto Front - Panel of optimized designs",
                    "type": "text",
                    "content": (
                        f"Smart decimation: {len(self.pareto_history)} designs registered. "
                        f"Reference RMSE: {getattr(self, '_workflow_best_rmse', 0):.6f}. "
                        f"RMSE/N×1000 = efficiency (lower = better complexity/performance). "
                        f"✅ = fabricable (d_min >= 5nm)."
                    ),
                },
                {
                    "title": "Summary table",
                    "type": "table",
                    "headers": [
                        "N",
                        "Best RMSE",
                        "d_min(nm)",
                        "Best MC +/-0.3nm",
                        "d_min MC(nm)",
                        "Best Fab",
                        "d_min Fab(nm)",
                        "RMSE/N×1000",
                        "Fab",
                    ],
                    "rows": rows,
                },
                {
                    "title": "Run Manifest",
                    "type": "table",
                    "headers": ["Key", "Value"],
                    "rows": [[str(k), str(v)] for k, v in manifest_dict.items()],
                },
            ]

            ok = generate_html_report(filename, "CERTUS - Pareto Front Summary", sections)

            if ok:
                self.log(f"📄 Pareto report: {Path(filename).name}", "SUCCESS")

            else:
                self.log("Pareto report generation failed", "WARNING")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Pareto report error: {e}", "WARNING")

    def _decimation_remove_and_polish(self) -> None:
        """One step of decimation: remove thinnest, merge, then local polish."""

        N = self.front_table.rowCount()

        ep = self.ep_current

        if N <= 4 or ep is None or len(ep) != N:
            self._finish_pareto_decimation()

            return

        # Find thinnest layer index

        thinnest_idx = int(np.argmin(ep))

        thinnest_d = ep[thinnest_idx]

        thinnest_mat = self._safe_get_combo_text(thinnest_idx, 0)

        self.log(
            f"▼ Decimation step {self._decimation_step + 1}: removing layer #{thinnest_idx + 1} "
            f"({thinnest_mat}, {thinnest_d:.2f} nm) from {N}-layer design",
            "INFO",
        )

        # Remove thinnest layer

        self.front_table.removeRow(thinnest_idx)

        self._merge_adjacent_layers()

        self._update_layer_count()

        new_N = self.front_table.rowCount()

        self._target_layer_count = new_N

        # Rebuild ep_current from remaining rows

        self._update_thickness_display()

        self._decimation_step += 1

        # Run a local polish to re-optimize

        self._decimation_polishing = True

        QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))

    def _on_decimation_polish_done(self) -> None:
        """Called after local polish during decimation to evaluate and continue."""

        N = self.front_table.rowCount()

        current_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        # Record in Pareto with current best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self.log(
            f"▼ Decimation: {N} layers -> RMSE={current_rmse:.5f} (ref={self._decimation_ref_rmse:.5f})",
            "INFO",
        )

        # Stop conditions:

        # 1. RMSE too degraded (3× reference)

        # 2. Too few layers

        # 3. Max 20 decimation steps (safety)

        if current_rmse > self._decimation_ref_rmse * 3.0 or N <= 4 or self._decimation_step >= 20:
            self._finish_pareto_decimation()

            return

        # Continue decimating

        QTimer.singleShot(100, self._decimation_remove_and_polish)

    def _finish_pareto_decimation(self) -> None:
        """Clean up after decimation loop."""

        self._decimation_polishing = False

        self._set_busy(False)

        self.log(
            f"▼ Pareto Decimation complete: {len(self.pareto_history)} layer counts recorded",
            "SUCCESS",
        )

    @safe_ui_action
    def _drop_thinnest_and_polish(self) -> None:
        """GUI action: remove thinnest layer, merge if interior, local polish.

        Now identical to remove_thinnest for consistency.

        """

        self.remove_thinnest()

    # =========================================================================

    # HARD 5nm MINIMUM LAYER THICKNESS RULE

    # =========================================================================

    def _apply_5nm_minimum(self) -> None:
        """Enforce hard minimum layer thickness of 5nm on the current design.

        Removes all layers < 5nm, merges adjacent identical materials,

        and logs any changes. Called at every workflow exit point.

        This rule takes priority over all other optimisation considerations.

        """

        ep = self.ep_current

        if ep is None or len(ep) == 0:
            return

        MIN_FINAL_THICKNESS = 5.0  # nm - hard manufacturing limit

        thin_layers = [r for r, d in enumerate(ep) if d < MIN_FINAL_THICKNESS]

        if not thin_layers:
            return  # Nothing to do

        self.log(
            f"[5nm rule] Removing {len(thin_layers)} layers < {MIN_FINAL_THICKNESS}nm before finalisation",
            "WARNING",
        )

        # Remove in reverse order to keep clues valid

        for r in sorted(thin_layers, reverse=True):
            self.front_table.removeRow(r)

        self._merge_adjacent_layers()

        self._update_layer_count()

        self._update_thickness_display()

        # Update target layer count to new reality

        self._target_layer_count = self.front_table.rowCount()

        self.log(
            f"[5nm rule] Final design: {self._target_layer_count} layers, "
            f"d_min = {float(np.min(self.ep_current)):.2f}nm",
            "INFO",
        )

        # Record the clean manufacturable design in Pareto history

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

    def _save_table_state(self) -> list:
        """Save front_table state (material + QWOT + var) for checkpoint."""

        state = []

        for r in range(self.front_table.rowCount()):
            mat = self._safe_get_combo_text(r, 0)

            qw = self.front_table.cellWidget(r, 1).value() if self.front_table.cellWidget(r, 1) else 1.0

            var = True

            cw = self.front_table.cellWidget(r, 3)

            if cw:
                cb = cw.findChild(QCheckBox)

                if cb:
                    var = cb.isChecked()

            del_checked = False

            del_cw = self.front_table.cellWidget(r, 4)

            if del_cw:
                del_cb = del_cw.findChild(QCheckBox)

                if del_cb:
                    del_checked = del_cb.isChecked()

            state.append({"mat": mat, "qw": qw, "var": var, "del": del_checked})

        return state

    def _restore_table_state(self, state: list) -> None:
        """Restore front_table from saved state (without recalculationating thicknesses)."""

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for item in state:
            self._add_front_row(item["mat"], item["qw"], item["var"], item.get("del", False))

        self.front_table.blockSignals(False)

        self._update_layer_count()

    def _revert_to_checkpoint(self) -> None:
        """Revert to pre-needle checkpoint if needle degraded the solution."""

        checkpoint = getattr(self, "_pre_needle_checkpoint", None)

        if not checkpoint:
            self.log("No checkpoint to revert to.", "WARNING")

            self._set_busy(False)

            return

        self.log(
            f"Reverting to checkpoint (RMSE={checkpoint['rmse']:.6f}, {len(checkpoint['table'])} layers)",
            "WARNING",
        )

        self._restore_table_state(checkpoint["table"])

        self._workflow_best_rmse = checkpoint["rmse"]

        # Clean all needle/overshoot state

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
            "_pre_needle_checkpoint",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._overshoot_done = True

        # Restore exact thicknesses: set QWOT from ep, then update display

        if checkpoint["ep"] is not None:
            self._update_qwot_from_ep(checkpoint["ep"])

            self._update_thickness_display()

            self.ep_current = checkpoint["ep"].copy()

            self._use_exact_ep = True

        self._apply_5nm_minimum()  # Hard rule before closing

        if get_export_config():
            self._export_pending = True  # Set BEFORE schedule_eval

        # Force final Pareto update with best RMSE

        current_best_rmse = getattr(self, "_workflow_best_rmse", float("inf"))

        if current_best_rmse < float("inf"):
            self._update_pareto_record(self.ep_current, current_best_rmse)

        self._schedule_eval(True)

        self.log("Optimization complete (reverted to best). Structure stable.", "SUCCESS")

        self._set_busy(False)

        self._is_internal_restart = False

        if get_export_config():
            self._export_pending = True

    def smart_cleanup(self, update_target: bool = True) -> int:
        """

        Smart cleanup: merges identical adjacent materials and removes

        very thin layers (< 1.0 nm) which are likely artifacts.

        Parameters

        ----------

        update_target : bool, optional

            If True, updates self._target_layer_count to match new count.

            Set to False during Deep Needle loop to maintain high target.

        Returns

        -------

        int

            Number of layers removed

        """

        removed_count = 0

        changed = False

        # Step 1: Remove very thin layers dynamically based on RMSE

        # Smart threshold: When RMSE is very low (sharp design), remove only incredibly thin layers to preserve delicate structures.

        current_rmse = getattr(self, "_workflow_best_rmse", 1.0)

        multiplier = getattr(self, "_cleanup_threshold_multiplier", 150.0)

        threshold = max(0.05, min(1.0, current_rmse * multiplier))  # Adaptive threshold

        rows_to_remove = []

        ep_current = self.ep_current if self.ep_current is not None else []

        if len(ep_current) == self.front_table.rowCount():
            for r in range(len(ep_current) - 1, -1, -1):
                if ep_current[r] < threshold:
                    rows_to_remove.append(r)

        if rows_to_remove:
            self.log(f"Smart cleanup: removing {len(rows_to_remove)} layers < {threshold:.2f} nm (adaptive)", "INFO")

            for r in rows_to_remove:
                self.front_table.removeRow(r)

            removed_count += len(rows_to_remove)

            changed = True

        # Step 2: Merge identical adjacent materials

        # (uses _merge_adjacent_layers which already does this)

        pre_merge_count = self.front_table.rowCount()

        self._merge_adjacent_layers()

        post_merge_count = self.front_table.rowCount()

        merge_diff = pre_merge_count - post_merge_count

        if merge_diff > 0:
            removed_count += merge_diff

            changed = True

            self.log(f"Smart cleanup: merged {merge_diff} adjacent layers", "INFO")

        if changed:
            self._update_layer_count()

            self._update_thickness_display()

            if update_target:
                self._target_layer_count = self.front_table.rowCount()

        return removed_count

    def _prune_to_target(self, target_count: int) -> int:
        """

        Overshoot & Prune: remove thinnest layers to reach target count.

        After growing beyond the target via Needle, prune back by removing

        the thinnest layers first (they contribute least to the design).

        Removes ONE layer at a time, then merges adjacent identical materials

        and re-checks count. This is necessary because in H/L stacks,

        removing one layer makes its neighbours adjacent -> merge -> net -2.

        This method performs layer pruning including:

        - Identification of thinnest layers

        - Sequential layer removal

        - Adjacent material merging

        - Count verification and adjustment

        Args:

            self: CertusDesign instance

            target_count: Desired number of layers after pruning

        Returns:

            int: Total number of layers removed (including merges)

        Notes:

            - Used in Needle algorithm workflow

            - Handles H/L stack merging automatically

            - Updates UI components after pruning

            - Logs pruning operations

        """

        initial_count = self.front_table.rowCount()

        if initial_count <= target_count:
            return 0

        total_removed = 0

        while self.front_table.rowCount() > target_count:
            current_count = self.front_table.rowCount()

            ep = self.ep_current if self.ep_current is not None else np.array([])

            if len(ep) != current_count:
                self._update_thickness_display()

                ep = self.ep_current if self.ep_current is not None else np.array([])

                if len(ep) != current_count:
                    self.log("Prune: ep_current mismatch, stopping.", "WARNING")

                    break

            # Find the thinnest layer

            thinnest_idx = int(np.argmin(ep))

            self.log(f"  Prune: layer {thinnest_idx} ({ep[thinnest_idx]:.2f} nm)", "INFO")

            self.front_table.blockSignals(True)

            self.front_table.removeRow(thinnest_idx)

            self.front_table.blockSignals(False)

            # Merge adjacent identical materials (may remove additional layers)

            pre_merge = self.front_table.rowCount()

            self._merge_adjacent_layers()

            post_merge = self.front_table.rowCount()

            step_removed = 1 + (pre_merge - post_merge)

            total_removed += step_removed

            self._update_layer_count()

            self._update_thickness_display()

        final_count = self.front_table.rowCount()

        self.log(
            f"Overshoot & Prune: {initial_count} -> {final_count} layers "
            f"(removed {total_removed}, target was {target_count})",
            "SUCCESS",
        )

        return total_removed

    def stop_optim(self) -> None:
        """Stop the current optimization and clean all workflow state.

        Terminates any running OptimWorker or NeedleWorker, then resets

        all internal state variables (overshoot, healing phase, needle

        cycle) to prevent stale state from interfering with subsequent

        optimizations.

        Sets _workflow_stopped flag to prevent pending QTimer callbacks

        from restarting the workflow after this method returns.

        """

        if not confirm_stop_with_timeout(self):
            return

        # CRITICAL: Set flag FIRST to block pending QTimer callbacks

        self._workflow_stopped = True

        if hasattr(self, "progress_widget"):
            self.progress_widget.stop("Stopped by user")

        self.log("Stopping optimization...", "WARNING")

        if self.optim_worker and self.optim_worker.isRunning():
            self.optim_worker.request_stop()

            if not self.optim_worker.wait(2000):
                logging.critical(
                    "Optim worker did not stop within 2s on stop - skipping terminate() to avoid unsafe thread kill."
                )

                self.log(
                    "Optim worker did not stop within 2s - skipping terminate() (see log).",
                    "ERROR",
                )

        if self.needle_worker and self.needle_worker.isRunning():
            self.needle_worker.requestInterruption()

            self.needle_worker.wait(1000)

        self._force_idle()

        self._clean_live_curves()

        self._is_internal_restart = False

        # Clean ALL workflow state on user stop

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = getattr(self, "_original_target_count", self._target_layer_count)

            self._overshoot_active = False

        self._healing_phase = None

        for attr in (
            "_needle_cycle_step",
            "_needle_merit_before",
            "_needle_stagnation_count",
            "_last_cycle_layer_count",
            "_needle_fail_count",
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        self.log("Optimization stopped.", "WARNING")

        # If stale callbacks arrive later, they can still call _set_busy(False) safely.

        # We force UI idle here to avoid sticky "Computing..." state.

        self._force_idle()

    def on_stats_update(self, type_str: str, count: int) -> None:
        """Updates statistics"""

        if type_str == "EVAL":
            self.stat_counters["EVAL"] = count

        elif type_str == "MINIMA":
            self.stat_counters["MINIMA"] = count

        self.update_stats_display()

    def update_stats_display(self) -> None:
        """Optimization counters: minimum, evaluations, best score (rainbow icon)."""

        minima_count = self.stat_counters.get("MINIMA", 0)

        eval_count = self.stat_counters.get("EVAL", 0)

        best_count = self.stat_counters.get("BEST", 0)

        text = f"♟️ {minima_count} minima  | 🎲 {eval_count} evals  | 🌈️ {best_count}"

        self.stats_label.setText(text)

    def _needle_thresholds(self, rmse_ref: float) -> tuple:
        """Adaptive thresholds for needle merit checks."""

        if rmse_ref is None or not np.isfinite(rmse_ref) or rmse_ref <= 0.0:
            return self._needle_success_rel_threshold, self._needle_success_abs_floor

        rel_thresh = 0.002 if rmse_ref < 0.01 else self._needle_success_rel_threshold

        abs_thresh = max(self._needle_success_abs_floor, rmse_ref * 5e-4)

        return rel_thresh, abs_thresh

    def _needle_gain_is_significant(self, rmse_before: float, rmse_after: float) -> tuple:
        """Return whether RMSE gain is meaningful for topology growth."""

        if (
            rmse_before is None
            or rmse_after is None
            or not np.isfinite(rmse_before)
            or not np.isfinite(rmse_after)
            or rmse_before <= 0.0
            or rmse_after >= rmse_before
        ):
            return False, 0.0, 0.0, 0.0, 0.0

        delta_abs = rmse_before - rmse_after

        delta_rel = delta_abs / max(rmse_before, 1e-12)

        rel_thresh, abs_thresh = self._needle_thresholds(rmse_before)

        ok = (delta_abs >= abs_thresh) or (delta_rel >= rel_thresh)

        return ok, delta_abs, delta_rel, abs_thresh, rel_thresh

    # =========================================================================

    # NEEDLE ALGORITHM

    # =========================================================================

    def _start_needle_process(self) -> None:
        """

        Start one Needle insertion cycle.

        The Needle method (Tikhonravov) scans the topological derivative P(z)

        across the optical thickness of the stack. Where P(z) is strongly

        negative, inserting a zero-thickness layer of the alternate material

        decreases the merit function.

        This method is called iteratively by the Deep Needle loop in

        ``_on_optim_done`` until the target layer count is reached or

        stagnation is detected.

        Workflow per call:

        1. Initialize stagnation counters (first call only).

        2. Preventive merge of adjacent identical materials.

           If any merged, run local polish first (``keep_history=True``).

        3. Build NeedleWorker configuration (stack, materials, targets).

        4. Start NeedleWorker -> emits ``_on_needle_found`` on completion.

        The growth cycle per insertion is:

        ``Needle -> Optim (step 1) -> Cleanup (step 2) -> Evaluate (step 3)``

        During the Overshoot phase, the target is temporarily set +20% above

        the user's original target to enrich the design space before pruning.

        This method performs needle insertion including:

        - Stagnation counter initialization

        - Material merging and cleanup

        - Worker thread configuration

        - Progress monitoring and error handling

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Logs needle insertion progress

            - Handles workflow stop requests

            - Emits progress signals during execution

            - Supports both normal and overshoot modes

        """

        # GUARD: If user clicked STOP, do not start needle

        if getattr(self, "_workflow_stopped", False):
            self.log("Workflow stopped, skipping needle.", "WARNING")

            self._set_busy(False)

            return

        # New Needle cycle initialization

        if not hasattr(self, "_needle_cycle_step") or self._needle_cycle_step not in [
            1,
            2,
            3,
        ]:
            # Keep fail counter across retries so it can reach abort threshold.

            # Only initialize once when missing.

            if not hasattr(self, "_needle_fail_count"):
                self._needle_fail_count = 0

            if not hasattr(self, "_needle_excluded_layers"):
                self._needle_excluded_layers = set()

            if not hasattr(self, "_needle_last_rejected_candidate"):
                self._needle_last_rejected_candidate = None

            if not hasattr(self, "_needle_exploratory_used"):
                self._needle_exploratory_used = False

            # Set merit BEFORE needle to the current best RMSE

            self._needle_merit_before = self._workflow_best_rmse

            # STAGNATION GUARD: Init counters

            if not hasattr(self, "_needle_stagnation_count"):
                self._needle_stagnation_count = 0

            if not hasattr(self, "_last_cycle_layer_count"):
                self._last_cycle_layer_count = self.front_table.rowCount()

            # DEEP NEEDLE LOGIC: If starting from stable state, we want to grow.

            # Set target explicitly to MAX_LAYERS to enable "Deep Needle" loop

            current_count = self.front_table.rowCount()

            # Check UI Option

            allow_growth = True

            if hasattr(self, "allow_growth_check"):
                allow_growth = self.allow_growth_check.isChecked()

            if allow_growth and self._target_layer_count <= current_count:
                # User likely clicked "Needle" manually to grow structure

                self._target_layer_count = CFG.MAX_LAYERS

                self.log(f"Deep Needle Init: Targeting max {CFG.MAX_LAYERS} layers", "INFO")

        # PREVENTIVE CLEANUP: Light clean before Needle (merge only, no deletion)

        # Only merge adjacent layers, avoid deleting thin layers

        # to avoid disturbing current optimization

        pre_merge_count = self.front_table.rowCount()

        self._merge_adjacent_layers()

        post_merge_count = self.front_table.rowCount()

        merge_diff = pre_merge_count - post_merge_count

        if merge_diff > 0:
            self.log(
                f"Preventive merge before Needle: merged {merge_diff} adjacent layers",
                "INFO",
            )

            self._update_layer_count()

            self._update_thickness_display()

            # If layers merged, restart light optimization (keep_history to preserve target)

            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)

            QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))

            return

        mats = self._get_materials()

        stack = self._get_front_stack()

        wls = self._get_optim_wls()

        if len(wls) == 0:
            wls = np.linspace(CFG.WL_DEFAULT_MIN, CFG.WL_DEFAULT_MAX, CFG.WL_DEFAULT_POINTS)

        # Backside configuration for Needle

        back_enabled = self.back_check.isChecked()

        use_back_coat = self.back_coat_check.isChecked()

        stack_back = self._get_back_stack()

        ep_back = self.ep_back_current if self.ep_back_current is not None else np.array([])

        has_back_stack = use_back_coat and len(stack_back) > 0

        float_dtype = get_float_dtype()

        complex_dtype = get_complex_dtype()

        n_back_T = np.zeros((len(wls), 0), dtype=complex_dtype)

        d_back = np.zeros(0, dtype=float_dtype)

        if has_back_stack:
            mats_nk = {k: m.get_nk(wls) for k, m in mats.items()}

            n_back = np.array([mats_nk[l.mat] for l in stack_back], dtype=complex_dtype)

            n_back_T = np.ascontiguousarray(n_back.T)

            d_back = np.ascontiguousarray(ep_back, dtype=float_dtype)

        # NeedleWorker expects 'has_back' key for calculationation activation

        has_back_calc = back_enabled

        ep_curr = self.ep_current if self.ep_current is not None else np.array([])

        # Retrieve targets based on mode (normal or oblique)

        if self.oblique_mode:
            tgts_needle = self._get_oblique_tgts()

        else:
            tgts_needle = self._get_tgts()

        cfg = {
            "stack": stack,
            "mats": mats,
            "l0": self.l0_spin.value(),
            "wls": wls,
            "tgts": tgts_needle,
            "ep": ep_curr,
            "has_back": has_back_calc,
            "n_back_T": n_back_T,
            "d_back": d_back,
            "oblique_mode": self.oblique_mode,  # Pass oblique mode
            "oblique_tgts": (self._get_oblique_tgts() if self.oblique_mode else []),  # Pass oblique targets
            "excluded_layers": sorted(getattr(self, "_needle_excluded_layers", set())),
        }

        self.needle_worker = NeedleWorker(cfg)

        self.needle_worker.signals.finished.connect(self._on_needle_found)

        self.needle_worker.signals.error.connect(self._on_error)

        self.needle_worker.start()

    def _on_needle_found(self, res: Dict) -> None:
        """

        Callback after NeedleWorker completes a topological scan.

        Handles the result of a Needle insertion search and drives

        the iterative growth loop.

        This method processes needle insertion results including:

        - Action determination and handling

        - Layer insertion and splitting

        - Target layer management

        - Workflow state coordination

        Possible actions (``res['action']``):

        - ``'empty_init'``: Stack is empty, add a seed layer.

        - ``'max_layers_reached'``: Cannot add more layers (CFG.MAX_LAYERS).

        - ``'none'``: No beneficial insertion found.

          - If below target: retry up to 3 times, then abort.

          - If at/above target and Overshoot active: trigger prune.

          - If at/above target and no Overshoot: stop (target reached).

        - ``'split'``: Insert a needle layer by splitting an existing layer

          at the optimal depth. Creates 3 rows (left + needle + right),

          then starts the Needle cycle: step 1 -> optimization -> step 2 -> cleanup

          -> step 3 -> evaluate.

        All abort paths clean up overshoot state to prevent dangling flags.

        Args:

            self: CertusDesign instance

            res: NeedleWorker result dictionary with action and data

        Returns:

            None

        Notes:

            - Logs needle insertion progress and decisions

            - Handles workflow stop requests

            - Manages overshoot and target layer states

            - Coordinates needle cycle transitions

        """

        # GUARD: If user clicked STOP, do not process needle result

        if getattr(self, "_workflow_stopped", False):
            self.log("Workflow stopped, ignoring needle result.", "WARNING")

            self._set_busy(False)

            return

        action = res.get("action", "none")

        if action == "empty_init":
            self.log("Needle:  Empty stack, adding seed layer.", "INFO")

            self.add_front_layer()

            self.run_optim("local")

            return

        if action == "max_layers_reached":
            self.log("Needle: MAX_LAYERS reached. Stopping iterative Needle.", "WARNING")

            # Stop iterative loop

            self._clear_needle_cycle_state()

            # Clean overshoot state

            if getattr(self, "_overshoot_active", False):
                self._target_layer_count = self._original_target_count

                self._overshoot_active = False

            self._set_busy(False)

            return

        if action == "split":
            pred_cost = res.get("cost")

            workflow_best = getattr(self, "_workflow_best_rmse", float("inf"))

            if (
                pred_cost is not None
                and np.isfinite(pred_cost)
                and pred_cost >= 0.0
                and pred_cost < 1e20
                and workflow_best is not None
                and np.isfinite(workflow_best)
                and workflow_best > 0.0
            ):
                pred_rmse = float(np.sqrt(pred_cost))

                pred_gain_abs = workflow_best - pred_rmse

                pred_gain_rel = pred_gain_abs / max(workflow_best, 1e-12)

                min_abs = getattr(self, "_needle_pred_gain_abs_threshold", 1e-5)

                min_rel = getattr(self, "_needle_pred_gain_rel_threshold", 0.002)

                if pred_gain_abs < min_abs and pred_gain_rel < min_rel:
                    self.log(
                        f"Needle: insertion skipped (predicted gain too small, "
                        f"DeltaRMSE={pred_gain_abs:.3g}, {pred_gain_rel * 100:.2f}%)",
                        "WARNING",
                    )

                    self._needle_last_rejected_candidate = dict(res) if res is not None else None

                    if res is not None and "layer_idx" in res:
                        if not hasattr(self, "_needle_excluded_layers"):
                            self._needle_excluded_layers = set()

                        self._needle_excluded_layers.add(int(res["layer_idx"]))

                    action = "none"

        if action == "none" or res is None:
            action, res, handled = self._handle_needle_no_candidate(action, res)

            if handled:
                return

        if action == "split":
            self._needle_fail_count = 0

            self._clear_needle_search_state(keep_fail_count=True)

            if not self._apply_needle_split_insertion(res):
                return

    def _handle_needle_no_candidate(self, action: str, res: Dict) -> Any:
        """Handle "none" needle actions including retries, aborts, and overshoot prune."""

        current_count = self.front_table.rowCount()

        if current_count < self._target_layer_count:
            return self._handle_needle_no_candidate_below_target(action, res, current_count)

        if self._maybe_prune_needle_overshoot(current_count):
            return action, res, True

        self.log("Needle: No beneficial insertion found. Target reached.", "INFO")

        self._clear_needle_search_state()

        self._clear_needle_cycle_state()

        self._set_busy(False)

        return action, res, True

    def _handle_needle_no_candidate_below_target(self, action: str, res: Dict, current_count: int) -> tuple:
        """Handle retries and abort for needle no-candidate results below target count."""

        self.log(
            f"Needle: No beneficial insertion found. Current: {current_count}, Target: {self._target_layer_count}",
            "WARNING",
        )

        if not hasattr(self, "_needle_fail_count"):
            self._needle_fail_count = 0

        self._needle_fail_count += 1

        if self._needle_fail_count >= 3:
            exploratory_candidate = getattr(self, "_needle_last_rejected_candidate", None)

            if exploratory_candidate is not None and not getattr(self, "_needle_exploratory_used", False):
                self._needle_exploratory_used = True

                self._needle_fail_count = 0

                if hasattr(self, "_needle_excluded_layers") and "layer_idx" in exploratory_candidate:
                    self._needle_excluded_layers.discard(int(exploratory_candidate["layer_idx"]))

                self.log(
                    "Needle: launching one exploratory insertion after 3 filtered retries.",
                    "WARNING",
                )

                action = "split"

                res = exploratory_candidate

            else:
                self._abort_needle_after_failed_retries()

                return action, res, True

        if action == "none" or res is None:
            self.log(
                f"Needle: Retrying... (attempt {self._needle_fail_count}/3)",
                "INFO",
            )

            QTimer.singleShot(200, self._start_needle_process)

            return action, res, True

        return action, res, False

    def _abort_needle_after_failed_retries(self) -> None:
        """Abort iterative needle workflow after repeated no-candidate failures."""

        self.log(
            "Needle: Too many failed attempts. Stopping iterative Needle.",
            "WARNING",
        )

        delattr(self, "_needle_fail_count")

        self._clear_needle_cycle_state()

        if getattr(self, "_overshoot_active", False):
            self._target_layer_count = self._original_target_count

            self._overshoot_active = False

        checkpoint = getattr(self, "_pre_needle_checkpoint", None)

        if checkpoint is not None:
            self.log("Needle: reverting to checkpoint.", "WARNING")

            self._revert_to_checkpoint()

            return

        if get_export_config():
            self._export_pending = True

        self._schedule_eval(True)

        self.log("Needle: aborted after retries. Finalizing current structure.", "WARNING")

        self._set_busy(False)

    def _maybe_prune_needle_overshoot(self, current_count: int) -> bool:
        """Prune overshoot layers and restart local optimization when needed."""

        if not getattr(self, "_overshoot_active", False):
            return False

        original = self._original_target_count

        self.log(
            f"Needle: Overshoot target reached ({current_count} layers). Pruning to {original}...",
            "SUCCESS",
        )

        pruned = self._prune_to_target(original)

        self._overshoot_active = False

        self._overshoot_done = True

        self._target_layer_count = original

        if hasattr(self, "_needle_fail_count"):
            delattr(self, "_needle_fail_count")

        self._clear_needle_cycle_state()

        if pruned > 0:
            self.accumulated_evals += getattr(self, "_optim_n_evals", 0)

            QTimer.singleShot(50, lambda: self.run_optim("local", keep_history=True))

            return True

        return False

    def _apply_needle_split_insertion(self, res: Dict) -> bool:
        """Apply a split insertion candidate and launch the local refinement cycle."""

        idx = res["layer_idx"]

        depth = res["depth"]

        mat_needle = res["needle_mat"]

        mat_orig = self._safe_get_combo_text(idx, 0)

        if not mat_orig:
            return False

        self.log(
            f"Needle: Splitting layer {idx} ({mat_orig}) at {depth:.1f}nm with {mat_needle}",
            "SUCCESS",
        )

        self.front_table.blockSignals(True)

        l0 = self.l0_spin.value()

        mats = self._get_materials()

        n_orig = mats[mat_orig].n4

        n_needle = mats[mat_needle].n4

        qw_left = (4.0 * n_orig * depth) / l0

        self.front_table.cellWidget(idx, 1).setValue(qw_left)

        self.front_table.item(idx, 2).setText(f"{depth:.1f}")

        target_needle_nm = self._insert_needle_split_row(idx, mat_needle, n_needle, l0)

        total_orig_thick = self.ep_current[idx]

        d_right = max(0.0, total_orig_thick - depth)

        qw_right = (4.0 * n_orig * d_right) / l0

        self._insert_right_split_row(idx, mat_orig, qw_right, d_right)

        self.front_table.blockSignals(False)

        self._update_layer_count()

        float_dtype = get_float_dtype()

        new_block = np.array([depth, target_needle_nm, d_right], dtype=float_dtype)

        self.ep_current = np.concatenate([self.ep_current[:idx], new_block, self.ep_current[idx + 1 :]])

        if hasattr(self, "_optim_n_evals"):
            self.accumulated_evals += self._optim_n_evals

        self._needle_merit_before = None

        self._needle_cycle_step = 1

        self.run_optim("local", keep_history=True)

        return True

    def _insert_needle_split_row(self, idx: int, mat_needle: str, n_needle: float, l0: float) -> float:
        """Insert the needle layer row in a split operation and return its target thickness."""

        insert_idx = idx + 1

        self.front_table.insertRow(insert_idx)

        target_needle_nm = 0.1

        qw_needle = (4.0 * n_needle * target_needle_nm) / l0

        cb_n = self._create_combo(mat_needle)

        self.front_table.setCellWidget(insert_idx, 0, cb_n)

        sb_n = self._create_spin(qw_needle, dec=6)

        sb_n.valueChanged.connect(self._on_schedule_eval_signal)

        self.front_table.setCellWidget(insert_idx, 1, sb_n)

        it_n = QTableWidgetItem(f"{target_needle_nm:.4f}")

        it_n.setFlags(it_n.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(insert_idx, 2, it_n)

        chk_n = QCheckBox()

        chk_n.setToolTip("Toggle optimization for needle layer.")

        chk_n.setChecked(True)

        cw_n = QWidget()

        cl_n = QHBoxLayout(cw_n)

        cl_n.addWidget(chk_n)

        cl_n.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl_n.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(insert_idx, 3, cw_n)

        return target_needle_nm

    def _insert_right_split_row(self, idx: int, mat_orig: str, qw_right: float, d_right: float) -> None:
        """Insert the right-side row produced by a split operation."""

        right_idx = idx + 2

        self.front_table.insertRow(right_idx)

        cb_r = self._create_combo(mat_orig)

        self.front_table.setCellWidget(right_idx, 0, cb_r)

        sb_r = self._create_spin(qw_right, dec=6)

        sb_r.valueChanged.connect(self._on_schedule_eval_signal)

        self.front_table.setCellWidget(right_idx, 1, sb_r)

        it_r = QTableWidgetItem(f"{d_right:.1f}")

        it_r.setFlags(it_r.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(right_idx, 2, it_r)

        chk_r = QCheckBox()

        chk_r.setToolTip("Toggle optimization for split layer.")

        chk_r.setChecked(True)

        cw_r = QWidget()

        cl_r = QHBoxLayout(cw_r)

        cl_r.addWidget(chk_r)

        cl_r.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl_r.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(right_idx, 3, cw_r)

    def _clear_needle_cycle_state(self) -> None:
        """Clear state attributes used by the current needle optimization cycle."""

        for attr in ("_needle_cycle_step", "_needle_merit_before"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _clear_needle_search_state(self, keep_fail_count: bool = False) -> None:
        """Clear temporary needle search attributes.

        Args:
            keep_fail_count: Preserve ``_needle_fail_count`` when caller just reset it.
        """

        attrs = [
            "_needle_excluded_layers",
            "_needle_last_rejected_candidate",
            "_needle_exploratory_used",
        ]

        if not keep_fail_count:
            attrs.insert(0, "_needle_fail_count")

        for attr in attrs:
            if hasattr(self, attr):
                delattr(self, attr)

    # =========================================================================

    # COLORIMETRY

    # =========================================================================

    @safe_ui_action
    def run_colorimetry(self) -> None:
        """

        Start colorimetric analysis of the current design.

        This method performs color analysis including:

        - Color coordinate calculationation (CIE XYZ, LAB)

        - Monte Carlo simulation for color variation

        - Visualization of color properties

        - Analysis of color stability under thickness variations

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires previous evaluation results

            - Switches to color plot view

            - Uses Monte Carlo simulation for robustness

            - Emits progress updates during analysis

        """

        if not self.last_result:
            self.log("Please evaluate first.", "WARNING")

            return

        if self.viz_stack.currentIndex() == 0:
            self.viz_stack.setCurrentIndex(1)

        self.plot_tabs.setCurrentWidget(self.color_plot)

        self.log("Running colorimetric analysis...", "INFO")

        mats = self._get_materials()

        stack = self._get_front_stack()

        cfg = {
            "ep": self.last_result["ep"],
            "stack": stack,
            "mats": mats,
            "n": self.mc_n_spin.value(),
            "sigma": self.mc_sigma_spin.value(),
            "l0": self.l0_spin.value(),
        }

        self._set_busy(True)

        self.col_worker = ColorWorker(cfg)

        self.col_worker.signals.finished.connect(self._on_col_done)

        self.col_worker.signals.error.connect(self._on_error)

        self.col_worker.start()

    def _on_col_done(self, d: Dict) -> None:
        """Callback after colorimetric analysis"""

        if d["ok"]:
            nom = d["lab_nom"]

            labs = d["labs"]

            self.color_plot.plotItem.clear()

            self.color_plot.plot(
                labs[:, 1],
                labs[:, 2],
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=(180, 180, 180, 100),
            )

            self.color_plot.plot(
                [nom[1]],
                [nom[2]],
                pen=None,
                symbol="star",
                symbolSize=18,
                symbolBrush=CertusTheme.ERROR,
                symbolPen="k",
            )

            de = [delta_e_2000(nom, l) for l in labs]

            rgb = lab_to_rgb(nom)

            title = (
                f"L*={nom[0]:.1f} a*={nom[1]:.1f} b*={nom[2]:.1f} | "
                f"RGB({rgb[0]},{rgb[1]},{rgb[2]}) | "
                f"DeltaE*00:  μ={np.mean(de):.2f} sigma={np.std(de):.2f}"
            )

            self.color_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="10pt")

            self.log("Colorimetry analysis complete.", "SUCCESS")

        self._set_busy(False)

    # =========================================================================

    # SELF-EXPORT (Excel + HTML)

    # =========================================================================

    @safe_ui_action
    def export_results(self) -> None:

        self.log("Entering export_results...", "DEBUG")

        """Self-exports results to reports folder (Excel + HTML).

        This method generates comprehensive reports including:

        - Excel spreadsheet with design parameters and results

        - HTML report with visualization and analysis

        - Timestamped filenames with RMSE values

        - Automatic folder creation and organization

        Args:

            self: CertusDesign instance

        Returns:

            None

        Notes:

            - Requires last_result to be available

            - Creates reports folder if needed

            - Generates both Excel and HTML formats

            - Includes RMSE value in filename"""

        if not self.last_result:
            self.log("No results to export.", "WARNING")

            return

        try:
            self._sync_export_result_with_best_eval()

            rmse_val, base_name, excel_path, html_path = self._prepare_export_paths()

            self.log("Saving reports...", "INFO")

            manifest_dict = self._build_export_manifest()

            if not self._is_export_manifest_complete(manifest_dict):
                return

            # 1. EXCEL EXPORT

            self._export_results_excel(manifest_dict, rmse_val, excel_path)

            # 2.HTML EXPORT
            self._export_results_html(manifest_dict, rmse_val, html_path)

            self.status_label.setText(f"✓ Saved: {base_name}")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error("Export error: %s", e, exc_info=True)

    def _export_results_excel(self, manifest_dict: dict[str, Any], rmse_val: float, excel_path: str) -> None:
        """Write the Excel report workbook when openpyxl is available."""

        if not OPENPYXL_AVAILABLE:
            self.log("openpyxl not available, Excel export skipped.", "WARNING")

            return

        import openpyxl

        wb = openpyxl.Workbook()

        ws = wb.active

        ws.title = "Summary"

        ws.append(["CERTUS-DESIGN Report"])

        ws.append([f"Generated: {certus_timestamp_display()}"])

        ws.append([f"Best RMSE: {rmse_val:.6f}"])

        t_exec = f"{self.last_result.get('execution_time', 0):.2f}" if "execution_time" in self.last_result else "N/A"

        ws.append([f"Execution Time: {t_exec} s"])

        ws.append([f"Global Cycles: {self.global_cycles_spin.value()}"])

        ws.append([f"Population: {self.max_clusters_spin.value()}"])

        ws.append([])

        ws.append(["STACK CONFIGURATION"])

        ws.append(["#", "Material", "QWOT", "Thickness (nm)", "Variable"])

        ep = self.ep_current if self.ep_current is not None else []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0

            ws.append([i + 1, layer.mat, layer.qwot, f"{d:.2f}", "Yes" if layer.var else "No"])

        if len(ep) > 0:
            ws.append([])

            ws.append(["Total Thickness (nm)", f"{np.sum(ep):.2f}"])

        if "vis" in self.last_result:
            ws2 = wb.create_sheet("Spectrum")

            ws2.append(["Wavelength (nm)", "Transmission"])

            vis = self.last_result["vis"]

            for i in range(len(vis["l"])):
                ws2.append([vis["l"][i], vis["Ts"][i]])

        ws_m = wb.create_sheet("Manifest")

        ws_m.append(["Key", "Value"])

        for k, v in manifest_dict.items():
            ws_m.append([str(k), str(v)])

        wb.save(excel_path)

        self.log(f"Excel saved: {Path(excel_path).name}", "SUCCESS")

    def _export_results_html(self, manifest_dict: dict[str, Any], rmse_val: float, html_path: str) -> None:
        """Write the HTML report for design optimization results."""

        ep = self.ep_current if self.ep_current is not None else []

        stack_data = []

        for i, layer in enumerate(self._get_front_stack()):
            d = ep[i] if i < len(ep) else 0.0

            stack_data.append(
                {
                    "#": i + 1,
                    "Material": layer.mat,
                    "Thickness (nm)": f"{d:.2f}",
                    "QWOT": f"{layer.qwot:.3f}",
                    "Optimized": "Yes" if layer.var else "No",
                }
            )

        sections = [
            {
                "title": "Design Optimization Summary",
                "type": "kv",
                "content": {
                    "Best RMSE": f"{rmse_val:.5f}",
                    "Total Layers": str(self.front_table.rowCount()),
                    "Total Thickness": (f"{np.sum(ep):.2f} nm" if len(ep) > 0 else "N/A"),
                    "Reference L0": f"{self.l0_spin.value()} nm",
                    "Targets Count": str(len(self._get_tgts())),
                    "Global Cycles": str(self.global_cycles_spin.value()),
                    "Cluster Pop": str(self.max_clusters_spin.value()),
                    "Execution Time": (
                        f"{self.last_result.get('execution_time', 0):.2f} s"
                        if "execution_time" in self.last_result
                        else "N/A"
                    ),
                },
            },
            {"title": "Layer Structure", "type": "table", "content": stack_data},
            {
                "title": "Run Manifest",
                "type": "table",
                "headers": ["Key", "Value"],
                "rows": [[str(k), str(v)] for k, v in manifest_dict.items()],
            },
        ]

        methodology_sections = [
            {
                "title": "Optimization Methodology",
                "type": "kv",
                "content": {
                    "Topology Search": "Needle Algorithm (Automatic Layer Insertion)",
                    "Global Search": "PGlobal (Stochastic Differential Evolution)",
                    "Local Refinement": "L-BFGS-B (Analytic Gradient)",
                    "Gradient Mode": "Analytic (Exact Derivatives)",
                    "Convergence": "High (Gradient-Assisted)",
                },
            },
            {
                "title": "Algorithm Details",
                "type": "text",
                "content": (
                    "The design process uses the <strong>Needle Algorithm</strong> to automatically find the optimal layer structure "
                    "by inserting infinitely thin layers at positions of maximum gradient sensitivity. This is coupled with a "
                    "<strong>Global/Local Hybrid Optimization</strong> strategy to refine thicknesses. The local refinement uses "
                    "<strong>Analytic Gradients</strong> to compute exact derivatives of the Tauc-Lorentz-Urbach model and "
                    "Transfer Matrix Method interactions, providing high-precision convergence without numerical noise."
                ),
            },
        ]

        all_sections = methodology_sections + sections

        figures = [self.spectrum_plot, self.profile_plot]

        if generate_html_report(html_path, "CERTUS-DESIGN Report", all_sections, figures):
            self.log(f"HTML saved: {Path(html_path).name}", "SUCCESS")

    def _build_export_manifest(self) -> dict[str, Any]:
        """Build a run manifest for report export."""

        manifest_dict: dict[str, Any] = {}

        try:
            status_txt = str(getattr(self, "validation_status", "OK") or "OK")

            try:
                status_val = ValidationStatus(status_txt)

            except ValueError:
                status_val = ValidationStatus.OK

            seed_val = None

            for _seed_candidate in (
                getattr(self, "run_seed", None),
                getattr(self, "random_seed", None),
                getattr(self, "_loaded_config", {}).get("seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
                getattr(self, "_loaded_config", {}).get("random_seed")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None,
            ):
                if _seed_candidate is None:
                    continue

                try:
                    seed_val = int(_seed_candidate)

                    break

                except (TypeError, ValueError):
                    continue

            svc = IndexFitService(runner=lambda _cfg: self.last_result or {})

            req = IndexFitRequest(
                config={
                    "module": "CERTUS_DESIGN",
                    "export_kind": "full_results",
                    "l0_nm": float(self.l0_spin.value()),
                    "layers_count": int(self.front_table.rowCount()),
                },
                source_paths=[
                    p
                    for p in (
                        str(getattr(self, "filename", "") or "").strip(),
                        str(getattr(self, "_last_config_file", "") or "").strip(),
                    )
                    if p
                ],
                seed=seed_val,
                app_id="CERTUS_DESIGN",
                app_version=__version__,
                warnings=list(getattr(self, "validation_warnings", []) or []),
                status=status_val,
            )

            manifest_dict = svc.fit(req).manifest.to_dict()

        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            self.log(f"Manifest generation failed: {exc}", "WARNING")

            manifest_dict = {}

        return manifest_dict

    def _is_export_manifest_complete(self, manifest_dict: dict[str, Any]) -> bool:
        """Validate mandatory manifest fields before writing reports."""

        from certus_data import get_missing_manifest_fields

        missing_manifest_fields = get_missing_manifest_fields(manifest_dict)

        if not missing_manifest_fields:
            return True

        self.log(
            "Export blocked: incomplete manifest (missing: " + ", ".join(missing_manifest_fields) + ")",
            "ERROR",
        )

        return False

    def _sync_export_result_with_best_eval(self) -> None:
        """Keep export payload aligned with the best evaluation spectrum and thickness table."""

        curr_rmse = self.last_result.get("rmse")

        curr_rmse_valid = self._is_valid_rmse_value(curr_rmse)

        if not (
            self._best_eval_result is not None
            and self._is_valid_rmse_value(self._best_eval_rmse)
            and (not curr_rmse_valid or self._best_eval_rmse <= curr_rmse + 1e-12)
        ):
            return

        self.last_result = copy.deepcopy(self._best_eval_result)

        try:
            ep_best = np.asarray(self.last_result.get("ep", []), dtype=float).flatten()

            if ep_best.size > 0:
                self._update_qwot_from_ep(ep_best)

                self._update_thickness_display()

                self.ep_current = ep_best.copy()

                self._use_exact_ep = True

        except NUMERICAL_FAULT_EXCEPTIONS as _e_export_sync:
            logging.debug(f"[EXPORT] Best spectrum/table sync skipped:{_e_export_sync}")

    def _prepare_export_paths(self) -> tuple[float, str, str, str]:
        """Prepare export paths and base metadata for report generation."""

        reports_dir = get_resource_path("reports")

        os.makedirs(reports_dir, exist_ok=True)

        rmse_val = getattr(self, "_workflow_best_rmse", None)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = self.last_result.get("rmse", 0.0)

        if rmse_val is None or not np.isfinite(rmse_val) or rmse_val < 0.0:
            rmse_val = float("inf")

        ts = certus_timestamp_file()

        try:
            src_name = ""

            if hasattr(self, "_last_config_file") and self._last_config_file:
                src_name = "_" + Path(self._last_config_file).stem

            base_name = f"Report_DESIGN{src_name}_{ts}_RMSE_{rmse_val:.5f}"

        except NUMERICAL_FAULT_EXCEPTIONS:
            base_name = f"Report_DESIGN_{ts}_RMSE_{rmse_val:.5f}"

        excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")

        html_path = str(Path(reports_dir) / f"{base_name}.html")

        return rmse_val, base_name, excel_path, html_path

    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # SAVE/LOAD

    # =========================================================================

    # --- Lot C helpers ---

    def _pre_save_smart_cleanup(self) -> None:
        """Run the pre-save cleanup + heal step (idempotent)."""

        if self.front_table.rowCount() > 0:
            self.log("Final cleanup before save...", "INFO")

            removed = self.smart_cleanup()

            if removed > 0:
                self.log(
                    f"Final cleanup: removed {removed} layers. Optimizing...",
                    "INFO",
                )

                # Run fast local optimization to heal

                self._is_internal_restart = True

                # Note: Cannot wait for optimization here (async)

                self._schedule_eval(True)  # Update display

    def _post_save_config(self, filename: str) -> None:
        """UX feedback after a successful save."""

        self.log(f"Configuration saved:  {filename}", "SUCCESS")

        show_toast(self, f"Saved: {Path(filename).name}", "success")

    def _collect_config(self) -> dict:
        """Build the JSON-serialisable config dict from current UI state."""

        self._pre_save_smart_cleanup()

        cfg = {
            "version": "CERTUS_SUITE_26_01",
            "l0": self.l0_spin.value(),
            "materials": {
                n: {
                    "n4": w["n4"].value(),
                    "n7": w["n7"].value(),
                    "preset": w["preset"].currentText(),
                }
                for n, w in self.mat_widgets.items()
            },
            "front": [{"mat": l.mat, "qw": l.qwot, "var": l.var} for l in self._get_front_stack()],
            "back_en": self.back_check.isChecked(),
            "back_coat": self.back_coat_check.isChecked(),
            "back": [{"mat": l.mat, "qw": l.qwot} for l in self._get_back_stack()],
            "targets": (
                [
                    {
                        "on": t.on,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "tmin": t.tmin,
                        "tmax": t.tmax,
                        "w": t.w,
                    }
                    for t in self._get_tgts()
                ]
                if not self.oblique_mode
                else [
                    {
                        "active": t.on,
                        "angle": t.angle,
                        "polarization": t.pol,
                        "target_type": t.target_type,
                        "lmin": t.lmin,
                        "lmax": t.lmax,
                        "val_min": t.tmin,
                        "val_max": t.tmax,
                        "weight": t.w,
                    }
                    for t in self._get_oblique_tgts()
                ]
            ),
            "oblique_mode": self.oblique_mode,
            "optimization": {
                "points_per_target": self.points_per_target_spin.value(),
                "n100": self.n100_spin.value(),
                "max_clusters": self.max_clusters_spin.value(),
                "max_iter": self.global_cycles_spin.value(),
                "mc_n": self.mc_n_spin.value(),
                "mc_sigma": self.mc_sigma_spin.value(),
                # Extra params
                "pre_polish": (self.pre_polish_check.isChecked() if hasattr(self, "pre_polish_check") else False),
                "allow_growth": (self.allow_growth_check.isChecked() if hasattr(self, "allow_growth_check") else True),
                "auto_scale_y": (self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True),
            },
        }

        return cfg

    def _apply_config(self, c: dict) -> None:
        """Apply a parsed configuration dict to the UI (Lot C)."""

        logging.info(f"Format Version: {c.get('version', 'Unknown')}")

        self._last_config_file = getattr(self, "_last_config_file", None)

        self.l0_spin.setValue(c.get("l0", 500))

        for n, d in c.get("materials", {}).items():
            if n in self.mat_widgets:
                # Set preset FIRST - triggers _apply_preset callback

                preset_name = d.get("preset", "Custom")

                self.mat_widgets[n]["preset"].setCurrentText(preset_name)

                # For Custom preset, restore saved values; for others, preset callback sets them

                if preset_name == "Custom":
                    self.mat_widgets[n]["n4"].setValue(d.get("n4", 1.5))

                    self.mat_widgets[n]["n7"].setValue(d.get("n7", 1.5))

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for l in c.get("front", []):
            self._add_front_row(l["mat"], l["qw"], l["var"])

        self.front_table.blockSignals(False)

        self.back_check.setChecked(c.get("back_en", False))

        self.back_coat_check.setChecked(c.get("back_coat", False))

        self.back_table.blockSignals(True)

        self.back_table.setRowCount(0)

        for l in c.get("back", []):
            self._add_back_row(l["mat"], l["qw"])

        self.back_table.blockSignals(False)

        # Oblique mode handling (backwards compatibility)

        oblique_mode = c.get("oblique_mode", False)

        logging.info(f"[LOAD] Oblique mode: {oblique_mode}")

        # CRITICAL: Reset oblique state completely before setting new mode

        # This prevents stale data when switching between normal/oblique files

        self.oblique_targets = []  # Clear old oblique targets

        if hasattr(self, "oblique_check"):
            self.oblique_check.setChecked(oblique_mode)

        self.oblique_mode = oblique_mode

        logging.info(f"[LOAD] Loading {len(c.get('targets', []))} targets...")

        self._update_target_table_headers()  # Always update headers

        self.target_table.setRowCount(0)

        for t in c.get("targets", []):
            self.add_target()

            r = self.target_table.rowCount() - 1

            if oblique_mode:
                # Format oblique: active, angle, pol, type, lmin, lmax, val_min, val_max, weight

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(t.get("active", t.get("on", True)))

                angle_w = self.target_table.cellWidget(r, 1)

                if angle_w:
                    angle_w.setValue(t.get("angle", 0.0))

                pol_w = self.target_table.cellWidget(r, 2)

                if pol_w:
                    pol_w.setCurrentText(t.get("polarization", "s"))

                type_w = self.target_table.cellWidget(r, 3)

                if type_w:
                    type_w.setCurrentText(t.get("target_type", "T"))

                lmin_w = self.target_table.cellWidget(r, 4)

                lmax_w = self.target_table.cellWidget(r, 5)

                if lmin_w:
                    lmin_w.setValue(t.get("lmin", 400))

                if lmax_w:
                    lmax_w.setValue(t.get("lmax", 700))

                vmin_w = self.target_table.cellWidget(r, 6)

                vmax_w = self.target_table.cellWidget(r, 7)

                if vmin_w:
                    vmin_w.setValue(t.get("val_min", t.get("tmin", 0.0)))

                if vmax_w:
                    vmax_w.setValue(t.get("val_max", t.get("tmax", 1.0)))

                weight_w = self.target_table.cellWidget(r, 8)

                if weight_w:
                    weight_w.setValue(t.get("weight", t.get("w", 1.0)))

            else:
                # Format normal: active, lmin, lmax, tmin, tmax, weight

                active_cb = self.target_table.cellWidget(r, 0)

                if active_cb:
                    active_cb.findChild(QCheckBox).setChecked(t.get("on", True))

                vals = [
                    t.get("lmin", 400),
                    t.get("lmax", 700),
                    t.get("tmin", 0),
                    t.get("tmax", 1),
                    t.get("w", 1),
                ]

                for i, v in enumerate(vals):
                    w = self.target_table.cellWidget(r, i + 1)

                    if w:
                        w.setValue(v)

        opt = c.get("optimization", {})

        if "points_per_target" in opt:
            self.points_per_target_spin.setValue(opt["points_per_target"])

        if "n100" in opt:
            self.n100_spin.setValue(opt["n100"])

        if "max_clusters" in opt:
            self.max_clusters_spin.setValue(opt["max_clusters"])

        if "max_iter" in opt:
            self.global_cycles_spin.setValue(opt["max_iter"])

        if "mc_n" in opt:
            self.mc_n_spin.setValue(opt["mc_n"])

        if "mc_sigma" in opt:
            self.mc_sigma_spin.setValue(opt["mc_sigma"])

        self._update_optim_point_count()

        self._schedule_eval(True)

        # Load Optimization Params (defaults-applied pass, preserves legacy behavior)

        opt = c.get("optimization", {})

        self.points_per_target_spin.setValue(opt.get("points_per_target", 100))

        self.n100_spin.setValue(opt.get("n100", 50))

        self.max_clusters_spin.setValue(opt.get("max_clusters", 20))

        self.global_cycles_spin.setValue(opt.get("max_iter", 2))

        self.mc_n_spin.setValue(opt.get("mc_n", 1000))

        self.mc_sigma_spin.setValue(opt.get("mc_sigma", 0.005))

        # Restore Extra Params (Needle, Polish, Scale)

        if hasattr(self, "pre_polish_check"):
            self.pre_polish_check.setChecked(opt.get("pre_polish", False))

        if hasattr(self, "allow_growth_check"):
            self.allow_growth_check.setChecked(opt.get("allow_growth", True))

        if hasattr(self, "auto_scale_y_check"):
            self.auto_scale_y_check.setChecked(opt.get("auto_scale_y", True))

        self._update_layer_count()

    def _post_load_config(self, filename: str, config: dict) -> None:
        """UX side-effects after a successful load (summary dialog, toast, ...)."""

        self._last_config_file = filename

        self.log(f"Configuration loaded:  {filename}", "SUCCESS")

        oblique_mode = bool(config.get("oblique_mode", False))

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            mats_cfg = config.get("materials", {})

            front_cfg = config.get("front", [])

            back_cfg = config.get("back", [])

            tgts_cfg = config.get("targets", [])

            l0_val = float(config.get("l0", self.l0_spin.value()))

            summary = build_summary_plain_text(
                "CERTUS DESIGN - Load Summary",
                [
                    f"File: {Path(filename).resolve()}",
                    "",
                    "General",
                    f"Version: {config.get('version', 'unknown')}",
                    (f"Reference wavelength l0: {l0_val:.2f} nm", not (100.0 <= l0_val <= 10000.0)),
                    "",
                    "Stack",
                    f"Materials declared: {len(mats_cfg)}",
                    (f"Front layers: {len(front_cfg)}", len(front_cfg) <= 0),
                    f"Back enabled: {'yes' if bool(config.get('back_en', False)) else 'no'}",
                    f"Back coating enabled: {'yes' if bool(config.get('back_coat', False)) else 'no'}",
                    (
                        f"Back layers: {len(back_cfg)}",
                        bool(config.get("back_coat", False)) and len(back_cfg) <= 0,
                    ),
                    f"Oblique mode: {'yes' if oblique_mode else 'no'}",
                    "",
                    "Targets",
                    (f"Targets loaded: {len(tgts_cfg)}", len(tgts_cfg) <= 0),
                ],
            )

            show_load_summary_dialog(self, "DESIGN Load Summary", summary)

        logging.info("[LOAD] Calling _schedule_eval (final)...")

        self._schedule_eval()

        _load_start = getattr(self, '_load_config_start_time', None)
        if _load_start is not None:
            logging.info(f"[LOAD] === load_config complete in {(time.time() - _load_start) * 1000:.1f}ms ===")

        self.log(f"Config loaded from {Path(filename).name}", "SUCCESS")

        show_toast(self, f"Loaded: {Path(filename).name}", "success")

    def open_help(self) -> None:
        """Opens HTML documentation"""

        open_documentation("CERTUS_DESIGN")

    def export_excel(self) -> None:
        """Exports design configuration and spectrum to Excel via build_standard_report."""
        import pandas as pd

        f = certus_get_save_file_name(self, "Export to Excel", "Excel (*.xlsx)")

        if not f:
            return

        try:
            # FINAL CLEANUP: Clean + Polish before export

            if self.front_table.rowCount() > 0:
                self.log("Final cleanup before export...", "INFO")

                removed = self.smart_cleanup()

                if removed > 0:
                    self.log(f"Final cleanup: removed {removed} layers.", "INFO")

                    self._is_internal_restart = True

                    self._schedule_eval(True)

            # --- Materials table ---

            mats = self._get_materials()

            df_mats = pd.DataFrame([{"Name": k, "n@400nm": m.n4, "n@700nm": m.n7} for k, m in mats.items()])

            # --- Front stack table ---

            ep = self.ep_current if self.ep_current is not None else []

            stack_rows = []

            for i, layer in enumerate(self._get_front_stack()):
                stack_rows.append(
                    {
                        "#": i + 1,
                        "Material": layer.mat,
                        "QWOT": layer.qwot,
                        "Thickness (nm)": ep[i] if i < len(ep) else 0,
                        "Variable": "Yes" if layer.var else "No",
                    }
                )

            df_stack = pd.DataFrame(stack_rows)

            if ep:
                df_stack = pd.concat(
                    [df_stack, pd.DataFrame([{"#": "TOTAL", "Thickness (nm)": float(np.sum(ep))}])],
                    ignore_index=True,
                )

            # --- Targets table ---

            df_targets = pd.DataFrame(
                [
                    {
                        "Active": "Yes" if t.on else "No",
                        "lambdamin (nm)": t.lmin,
                        "lambdamax (nm)": t.lmax,
                        "Tmin": t.tmin,
                        "Tmax": t.tmax,
                        "Weight": t.w,
                    }
                    for t in self._get_tgts()
                ]
            )

            # --- Summary kv ---

            summary_kv = {
                "Generated": certus_timestamp_display(),
                "CERTUS Suite": "CERTUS_SUITE_26_01",
                "L0 (nm)": self.l0_spin.value(),
                "Total layers": len(stack_rows),
            }

            from certus_data import ReportSection, build_standard_report

            try:
                self.set_validation_status("OK")
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN validation status update skipped during export: %s", exc)
            run_manifest = None
            try:
                status_txt = str(getattr(self, "validation_status", "OK") or "OK")
                try:
                    status_val = ValidationStatus(status_txt)
                except ValueError:
                    status_val = ValidationStatus.OK
                svc = IndexFitService(runner=lambda _cfg: self.last_result or {})
                seed_val = None
                seed_sources = [
                    getattr(self, "run_seed", None),
                    getattr(self, "random_seed", None),
                    getattr(self, "cfg", {}).get("run_seed") if isinstance(getattr(self, "cfg", None), dict) else None,
                    getattr(self, "_loaded_config", {}).get("seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                    getattr(self, "_loaded_config", {}).get("random_seed")
                    if isinstance(getattr(self, "_loaded_config", None), dict)
                    else None,
                ]
                for _seed_candidate in seed_sources:
                    if _seed_candidate is None:
                        continue
                    try:
                        seed_val = int(_seed_candidate)
                        break
                    except (TypeError, ValueError):
                        continue
                req = IndexFitRequest(
                    config={
                        "module": "CERTUS_DESIGN",
                        "l0_nm": float(self.l0_spin.value()),
                        "layers_count": int(len(stack_rows)),
                    },
                    source_paths=[
                        p
                        for p in (
                            str(getattr(self, "filename", "") or "").strip(),
                            str(getattr(self, "_last_config_file", "") or "").strip(),
                        )
                        if p
                    ],
                    seed=seed_val,
                    app_id="CERTUS_DESIGN",
                    app_version=__version__,
                    warnings=list(getattr(self, "validation_warnings", []) or []),
                    status=status_val,
                )
                run_manifest = svc.fit(req).manifest
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                self.logger.warning("DESIGN manifest generation failed: %s", exc)
                run_manifest = None

            sections = [
                ReportSection("Summary", kind="kv", content=summary_kv, sheet_name="Summary"),
                ReportSection("Materials", kind="table", content=df_mats, sheet_name="Materials"),
                ReportSection("Front Stack", kind="table", content=df_stack, sheet_name="Stack"),
                ReportSection("Spectral Targets", kind="table", content=df_targets, sheet_name="Targets"),
            ]

            if self.last_result:
                r = self.last_result["vis"]

                df_spectrum = pd.DataFrame({"Wavelength (nm)": r["l"], "Transmission": r["Ts"]})

                sections.append(ReportSection("Spectrum", kind="table", content=df_spectrum, sheet_name="Spectrum"))

            result = build_standard_report(
                sections,
                excel_path=f,
                run_manifest=run_manifest,
                require_complete_manifest=True,
            )

            if result.get("excel"):
                self.log(f"Exported to:  {f}", "SUCCESS")

            else:
                self.log("Export failed (build_standard_report error).", "ERROR")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Export error:{str(e)}", "ERROR")

    def closeEvent(self, event) -> None:
        """

        Handles application closure with proper cleanup of all workers.

        Ensures all QThread workers are properly stopped to avoid

        "QThread: Destroyed while thread is still running" warnings.

        """

        # Ensure all workers are stopped to avoid "QThread: Destroyed while thread is still running"

        workers = [
            getattr(self, "optim_worker", None),
            getattr(self, "needle_worker", None),
            getattr(self, "color_worker", None),
            getattr(self, "warmup_worker", None),
            getattr(self, "eval_worker", None),
        ]

        for worker in workers:
            if worker and worker.isRunning():
                try:
                    # Attempt cooperative stop

                    if hasattr(worker, "request_stop"):
                        worker.request_stop()

                    elif hasattr(worker, "requestInterruption"):
                        worker.requestInterruption()

                    # Wait for graceful shutdown (2000ms timeout)

                    if not worker.wait(2000):
                        logging.critical(
                            f"Worker {type(worker).__name__} did not stop within 2s in closeEvent - "
                            "skipping terminate() to avoid unsafe thread kill."
                        )

                except (RuntimeError, AttributeError) as e:
                    # Non-critical: worker may already be destroyed

                    if hasattr(self, "logger") and self.logger:
                        self.logger.debug(f"Error stopping worker {type(worker).__name__}: {e}")

        # Call parent cleanup (stops base class workers)

        super().closeEvent(event)

    # =========================================================================

    # UTILITAIRES

    # =========================================================================

    def _update_busy_ui(self, busy_now: bool) -> None:
        """Updates Design-specific button states."""

        for btn in [self.local_btn, self.global_btn, self.color_btn, self.eval_btn]:
            btn.setEnabled(not busy_now)

        self.stop_btn.setEnabled(busy_now)

    def reset_to_defaults(self) -> Any:
        """Resets the entire application to factory defaults (clean slate)."""

        from certus_reset_framework import reset_app_to_defaults

        return reset_app_to_defaults(self)

    def _load_defaults(self) -> None:
        """Loads default values"""

        # Block signals to avoid massive re-evaluations during reset

        self.blockSignals(True)

        try:
            defaults = {
                "H": (2.35, 2.30),
                "L": (1.46, 1.46),
                "A": (2.05, 2.00),
                "B": (1.75, 1.73),
                "C": (1.60, 1.58),
                "Substrate": (1.52, 1.51),
            }

            for name, (n4, n7) in defaults.items():
                if name in self.mat_widgets:
                    self.mat_widgets[name]["n4"].setValue(n4)

                    self.mat_widgets[name]["n7"].setValue(n7)

                    self.mat_widgets[name]["preset"].setCurrentText("Custom")

            # Reset Global Parameters

            if hasattr(self, "l0_spin"):
                self.l0_spin.setValue(getattr(CFG, "DEFAULT_L0", 500.0))

            # Reset Checkboxes

            if hasattr(self, "back_check"):
                self.back_check.setChecked(False)

            if hasattr(self, "back_coat_check"):
                self.back_coat_check.setChecked(False)

            if hasattr(self, "oblique_check"):
                self.oblique_check.setChecked(False)

            if hasattr(self, "auto_scale_y_check"):
                self.auto_scale_y_check.setChecked(True)

            if hasattr(self, "allow_growth_check"):
                self.allow_growth_check.setChecked(True)

            if hasattr(self, "pre_polish_check"):
                self.pre_polish_check.setChecked(False)

            # Add default layers

            for _ in range(4):
                self.add_front_layer()

            # Add default target

            self.add_target()

            # Default optimization parameters

            self.n100_spin.setValue(6000)

            self.max_clusters_spin.setValue(40)

            self.global_cycles_spin.setValue(50)

            if hasattr(self, "points_per_target_spin"):
                self.points_per_target_spin.setValue(50)

            # Default MC parameters

            if hasattr(self, "mc_n_spin"):
                self.mc_n_spin.setValue(200)

            if hasattr(self, "mc_sigma_spin"):
                self.mc_sigma_spin.setValue(2.0)

            # Update Tikhonravov points after loading defaults

            QTimer.singleShot(500, self._update_tikhonravov_points)

            self.log("Default configuration loaded with optimized PGLOBAL settings.", "INFO")

        finally:
            self.blockSignals(False)

            # Force one final evaluation to show the default design

            self._schedule_eval(instant=True)

# =============================================================================

# ENTRY POINT

# =============================================================================

def main() -> None:
    """Main entry point"""

    # Change working directory to script/exe directory (script_dir set by bootstrap_app)

    try:
        os.chdir(script_dir)

    except (OSError, FileNotFoundError) as e:
        logging.debug(f"Could not change working directory: {e}")

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    CertusTheme.apply_to_app(app, dark_mode=False)

    # Standardized initialization with COMMON

    init_certus_app("CERTUS-DESIGN", app=app)

    try:
        from certus_ux import build_premium_overrides

        app.setStyleSheet(app.styleSheet() + "\n" + build_premium_overrides())
    except ImportError:
        pass

    # --- SPLASH SCREEN ---

    from certus_splash import create_splash

    splash = create_splash("Initializing Design Environment...")

    # Setup logging with centralized helper

    setup_module_logging("CERTUS_DESIGN", log_file="certus_design.log")

    splash.showMessage(
        "Loading Default Configuration...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        Qt.GlobalColor.black,
    )

    win = CertusDesignApp()

    win.show()

    splash.finish(win)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: win.load_config(f))

    sys.exit(app.exec())

if __name__ == "__main__":
    # CRITICAL for Nuitka/PyInstaller: Must be FIRST in __main__

    multiprocessing.freeze_support()

    main()
