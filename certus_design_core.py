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

