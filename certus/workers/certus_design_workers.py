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

from certus.core.certus_core import __version__

import os
from pathlib import Path

import multiprocessing
import sys
import functools

from certus.core.certus_core import create_module_environment

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

from certus.ui.certus_qt_widgets import (
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
from PyQt6.QtCore import QObject

# Conditional SVG Import

# =============================================================================

# IMPORTS MODULAR ARCHITECTURE

# =============================================================================

# Import Modular Architecture

# --- 1. CORE (Config, Constants, Utils) ---

from certus.core.certus_core import (
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
from certus.utils.errors import safe_ui_action

from certus.workers.certus_design_worker_utils import (
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

from certus.utils.certus_data import OPENPYXL_AVAILABLE, generate_html_report
from certus.workers.certus_design_workers_dto import (
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

from certus.utils.certus_index_utils import spectral_rmse_weights

# --- 3. UI (Theme, Widgets) ---

from certus.ui.certus_ui import (
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
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
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


from certus.core.certus_design_core import *
from certus.core.certus_design_core import (
    _design_objective_wrapper_common,
    _design_compute_oblique_error_common,
    _design_gradient_func_pglobal_common,
    _design_compute_oblique_error_and_grad_analytic_common,
    _design_optimization_callback_common,
)

class OptimWorker(QObject):
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

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

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
        from certus.workers.certus_design_worker_utils import prepare_pglobal_inputs_from_state

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
                from certus.workers.certus_design_worker_utils import maybe_upgrade_grid_tikhonravov

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

class ColorWorker(QObject):
    """Worker for Monte Carlo color analysis"""

    def __init__(self, cfg: dict[str, Any] | ColorWorkerRequest) -> None:

        super().__init__()

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

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

class NeedleWorker(QObject):
    """Worker for layer insertion (Needle algorithm)"""

    def __init__(self, cfg: dict[str, Any] | NeedleWorkerRequest) -> None:

        super().__init__()

    def isInterruptionRequested(self) -> bool:
        return QThread.currentThread().isInterruptionRequested()

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

