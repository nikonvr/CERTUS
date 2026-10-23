"""
CERTUS-METAL SINGLE: Qt workers and application window
======================================================

The optimization worker, the beam-analysis worker and the CertusMetalSingleApp
window. The computation they drive lives in certus_metal_single_physics. The
root launcher CERTUS_METAL_SINGLE.py re-exports this module.
"""

import json  # used by the configuration loading (_resolve_config_target_file); the import was missing
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from certus.core._certus_physics_impl import get_n_substrate_array_by_id
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_CHOICES,
    canonicalize_substrate_label,
    certus_timestamp_display,
    certus_timestamp_file,
    get_float_dtype,
    get_resource_path,
)
from certus.metal.certus_metal_common import (
    DEFAULT_EM_MAX,
    DEFAULT_EM_MIN,
    DEFAULT_MAXITER,
    DEFAULT_MIN_KNOT_DISTANCE,
    DEFAULT_MUTATION_MAX,
    DEFAULT_MUTATION_MIN,
    DEFAULT_NK_MAX,
    DEFAULT_NK_MIN,
    DEFAULT_NUM_KNOTS,
    DEFAULT_POPSIZE,
    DEFAULT_RECOMBINATION,
    DEFAULT_TOL,
    DEFAULT_UPDATING,
    DEFAULT_WORKERS,
    MetalOptimizationWorker,
    build_metal_progress_status_text,
    build_metal_startup_log_lines,
    build_metal_target_data,
    elevate_spline_knots,
    normalize_metal_progress_payload,
    setup_beam_analysis_thread,
    teardown_beam_thread,
)
from certus.metal.certus_metal_single_physics import (
    _build_single_bounds,
    _resolve_single_substrate_id,
    global_objective_function,
    gradient_function_fixed_eM,
    objective_function_fixed_eM,
)
from certus.metal.pglobal_adapter import run_pglobal_optimization
from certus.utils.certus_data import (
    OPENPYXL_AVAILABLE,
    to_excel_robust,
)
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.errors import (
    get_error_message,
    show_error,
)
from certus_physics import (
    calculate_RTRback_incoherent_vectorized,
    get_nk_from_spline,
)

# =============================================================================


# WORKER THREAD


# =============================================================================


class OptimizationWorker(MetalOptimizationWorker):
    """Optimization worker thread"""

    # Signals inherited from MetalOptimizationWorker

    # __init__ inherited (initializes params, is_running, counters, best_candidate)

    @pyqtSlot()
    def run(self) -> None:
        """

        Execute the metal single layer optimization worker thread.

        This method performs the complete optimization workflow for single metal layers including:

        - Parameter optimization for single metal layer

        - Spectral calculationation and target fitting

        - MSE calculationation and convergence tracking

        - Progress monitoring and signal emission

        Args:

            self: OptimizationWorker instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling

            - Emits progress and finished signals

            - Handles single metal layer constraints

            - Uses PGlobal optimization algorithm

        """

        try:
            p = self.params

            float_dtype = get_float_dtype()

            target_lambda = np.ascontiguousarray(p["target_lambda"], dtype=float_dtype)

            target_r = np.ascontiguousarray(p["target_r"], dtype=float_dtype)

            target_t = np.ascontiguousarray(p["target_t"], dtype=float_dtype)

            target_rb = np.ascontiguousarray(p["target_rb"], dtype=float_dtype)

            substrate_id = p["substrate_id"]

            nSub_real = get_n_substrate_array_by_id(substrate_id, target_lambda)

            nSub_complex_array = nSub_real.astype(np.complex128) + 0j

            num_knots = p["num_knots"]

            precomputed = {
                "min_lambda": float(target_lambda.min()),
                "max_lambda": float(target_lambda.max()),
            }

            args_for_objective = (
                p["num_knots"],
                target_lambda,
                target_r,
                target_t,
                target_rb,
                p["min_knot_dist"],
                nSub_complex_array,
                precomputed,
            )

            # --- KNOT CONTINUATION (MESH REFINEMENT) LOGIC ---
            # If the user explicitly provided an x0 (e.g. Resume from UI), we do not do continuation
            user_x0 = np.asarray(p.get("x0", []), dtype=float_dtype) if p.get("x0") is not None else np.array([])
            target_num_knots = num_knots
            
            if len(user_x0) > 0:
                knot_steps = [target_num_knots]
            else:
                knot_steps = list(range(2, target_num_knots + 1))
                
            total_steps = len(knot_steps)
            total_feval = int(p.get("maxfeval", 25000))
            feval_per_step = max(1000, total_feval // total_steps)
            iter_per_step = max(1, int(p.get("maxiter", DEFAULT_MAXITER)) // total_steps)
            
            current_x0 = user_x0 if len(user_x0) > 0 else None
            
            logger = logging.getLogger("CERTUS.METAL.SINGLE")
            logger.info("Starting Knot Continuation over steps: %s", knot_steps)
            
            result = None
            
            for step_idx, k in enumerate(knot_steps):
                if not self.is_running:
                    break
                    
                logger.info("--- KNOT STEP K=%d ---", k)
                
                # Elevate knots if continuing from a previous step
                if current_x0 is not None and k > 2 and len(user_x0) == 0:
                    current_x0 = elevate_spline_knots(current_x0, k - 1, precomputed["min_lambda"], precomputed["max_lambda"])
                
                # Update params for current knot count
                p_k = p.copy()
                p_k["num_knots"] = k
                
                # Build bounds
                bounds = np.array(_build_single_bounds(p_k, l_array=target_lambda, include_eM=True), dtype=float_dtype)
                
                # If we are refining (k > 2) and didn't start from user_x0, tighten the bounds around the current solution
                if k > 2 and current_x0 is not None and len(user_x0) == 0:
                    delta_eM = 5.0
                    delta_nk = 0.5
                    delta_l = 50.0
                    
                    bounds[0] = (max(bounds[0][0], current_x0[0] - delta_eM), min(bounds[0][1], current_x0[0] + delta_eM))
                    for idx in range(1, 1 + 2 * k):
                        bounds[idx] = (max(bounds[idx][0], current_x0[idx] - delta_nk), min(bounds[idx][1], current_x0[idx] + delta_nk))
                    for idx in range(1 + 2 * k, len(bounds)):
                        bounds[idx] = (max(bounds[idx][0], current_x0[idx] - delta_l), min(bounds[idx][1], current_x0[idx] + delta_l))

                if current_x0 is not None:
                    # Guarantee current_x0 is strictly within the bounds to prevent optimizer crash
                    lows = [b[0] for b in bounds]
                    highs = [b[1] for b in bounds]
                    current_x0 = np.clip(current_x0, lows, highs)

                # Setup args for objective
                args_for_objective = (
                    k,
                    target_lambda,
                    target_r,
                    target_t,
                    target_rb,
                    p["min_knot_dist"],
                    nSub_complex_array,
                    precomputed,
                )

                from certus.core._certus_physics_impl import PGlobalConfig
                cfg = PGlobalConfig.for_dimension(dim=len(bounds)).with_overrides(
                    alpha=0.05,
                    reduction_ratio=0.2,
                    n_samples_per_iter=600,       # Fast global phase -> fluid UI
                    local_search_budget=1500,     # Meaningful local search descent
                    max_active_clusters=5,        # Focus deeply on the top 5 best basins
                )

                logger.info(
                    "GLOBAL_OPT(PGlobal) K=%d start max_iter=%s max_feval=%s workers=%s bounds=%s",
                    k, iter_per_step, feval_per_step, int(p.get("workers", 1)), len(bounds),
                )
                
                def make_callback(step_i, total_s):
                    def callback(payload):
                        base_pct = step_i * (100.0 / total_s)
                        step_pct = payload.get("progress_pct", 0) / total_s
                        payload["progress_pct"] = base_pct + step_pct
                        self.progress.emit(payload)
                    return callback

                result = run_pglobal_optimization(
                    lambda x, _args=args_for_objective: global_objective_function(x, *_args),
                    bounds,
                    x0=current_x0,
                    max_iter=iter_per_step,
                    max_feval=feval_per_step,
                    workers=int(p.get("workers", 1)),
                    stop_event=self._stop_event,
                    callback=make_callback(step_idx, total_steps),
                    progress_logger=lambda msg, _k=k: logging.getLogger("CERTUS.METAL.SINGLE").info("GLOBAL_OPT(PGlobal) K=%d %s", _k, msg),
                    ultra_wide=bool(p.get("ultra_wide", False)),
                    config=cfg,
                    skip_polish=(k < target_num_knots),
                )
                
                current_x0 = result.x

            logger.info(
                "GLOBAL_OPT(PGlobal) complete success=%s best_rmse=%s iterations=%s evals=%s",
                getattr(result, "success", None),
                float(np.sqrt(max(float(getattr(result, "fun", float("inf"))), 0.0))) if result else float("inf"),
                getattr(result, "nit", None) if result else 0,
                getattr(result, "nfev", None) if result else 0,
            )
            
            # Emit final progress 100% just in case
            if result:
                self.progress.emit({
                    "progress_pct": 100,
                    "current_rmse": float(np.sqrt(max(float(getattr(result, "fun", float("inf"))), 0.0))),
                    "best_rmse": float(np.sqrt(max(float(getattr(result, "fun", float("inf"))), 0.0))),
                    "iteration": getattr(result, "nit", 0),
                    "max_iteration": int(p.get("maxiter", DEFAULT_MAXITER)),
                    "best_x": result.x,
                    "message": "Optimization Complete",
                    "current_knots": target_num_knots
                })
            
        except Exception as e:
            import traceback
            logging.getLogger("CERTUS.METAL.SINGLE").error("OptimizationWorker exception: %s\n%s", e, traceback.format_exc())
            if hasattr(self, "error"):
                self.error.emit(str(e))
        finally:
            if 'result' in locals():
                self.finished.emit({"result": result, "params": p})
            else:
                self.finished.emit({})


class BeamAnalysisWorker(QObject):
    """

    Beam analysis worker for Single Metal

    Scan eM (Thickness) around optimum to check solution uniqueness/valley shape.

    Bi-directional scan from optimum.

    """

    finished = pyqtSignal(dict)

    progress = pyqtSignal(int, int, float)  # step, total, best_mse

    error = pyqtSignal(str)

    def __init__(self, params, optimal_solution, optimal_mse, step_nm=0.5, mse_tolerance=0.1):

        super().__init__()

        self.params = params

        self.optimal_solution = optimal_solution

        self.optimal_mse = optimal_mse

        self.step_nm = step_nm

        self.mse_tolerance = mse_tolerance

        self.is_running = True

    @pyqtSlot()
    def run(self):

        try:
            num_knots = self.params["num_knots"]

            l_array = self.params["target_lambda"]

            r_tgt_array = self.params["target_r"]

            min_knot_dist = self.params["min_knot_dist"]

            substrate_id = self.params.get("substrate_id", 0)

            # Global optimal solution

            # x = [eM, n_knots, k_knots, lambda_internes]

            eM_optimal = self.optimal_solution[0]

            offset = 1

            n_knots_optimal = self.optimal_solution[offset : offset + num_knots]

            k_knots_optimal = self.optimal_solution[offset + num_knots : offset + 2 * num_knots]

            lambda_internes_optimal = self.optimal_solution[offset + 2 * num_knots :]

            # Initial x0 (without eM): only n/k vary in beam scan.

            lambda_internes_fixed = np.asarray(lambda_internes_optimal, dtype=np.float64)

            x0_optimal_reduced = np.concatenate((n_knots_optimal, k_knots_optimal))

            # Scan Range

            eM_min_scan = max(1.0, eM_optimal - 20.0)

            eM_max_scan = eM_optimal + 20.0

            eM_range_up = np.arange(eM_optimal + self.step_nm, eM_max_scan + 1e-6, self.step_nm)

            eM_range_down = np.arange(eM_optimal - self.step_nm, eM_min_scan - 1e-6, -self.step_nm)

            total_steps = 1 + len(eM_range_up) + len(eM_range_down)

            # Bounds (without eM): keep only n/k bounds (lambda knots fixed).

            bounds = _build_single_bounds(self.params, l_array=None, include_eM=False)

            l_min_val, l_max_val = l_array.min(), l_array.max()

            # Precompute values for objective function (avoid recalculationation in hot loop)

            nSub_real = get_n_substrate_array_by_id(substrate_id, l_array)

            precomputed = {
                "min_lambda": l_min_val,
                "max_lambda": l_max_val,
                "nSub_complex_array": nSub_real.astype(np.complex128),
                "eM_buffer": np.empty(1, dtype=np.float64),
                "knot_l_buffer": np.empty(num_knots, dtype=np.float64),
                "p_spline_buffer": np.empty(2 * num_knots, dtype=np.float64),
            }

            # Smart MSE threshold

            mse_threshold = max(self.optimal_mse * 1.5 + 1e-5, 5e-5)

            all_solutions = []

            # 1. Add Optimal

            # Recalculate full spectra for storage

            plot_lambda = np.linspace(l_min_val, l_max_val, 300)

            knot_l_opt = np.concatenate(([l_min_val], np.sort(lambda_internes_optimal), [l_max_val]))

            p_spline_nk_opt = np.concatenate((n_knots_optimal, k_knots_optimal))

            try:
                n_calc_opt, k_calc_opt = get_nk_from_spline(p_spline_nk_opt, knot_l_opt, plot_lambda)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                logging.warning(f"Optimal spline reconstruction failed: {e}")

                # Fallback to zeros to avoid crash

                n_calc_opt = np.zeros_like(plot_lambda)

                k_calc_opt = np.zeros_like(plot_lambda)

            all_solutions.append(
                {
                    "mse": self.optimal_mse,
                    "n": n_calc_opt,
                    "k": k_calc_opt,
                    "eM": eM_optimal,
                    "params": self.optimal_solution.copy(),
                }
            )

            processed_steps = 1

            def process_scan_range(eM_list, start_x0):

                nonlocal processed_steps

                current_x0 = start_x0.copy()

                for eM_test in eM_list:
                    if not self.is_running:
                        return

                    def obj_fun(x, eM_test=eM_test):

                        return objective_function_fixed_eM(
                            x,
                            eM_test,
                            num_knots,
                            l_array,
                            r_tgt_array,
                            min_knot_dist,
                            precomputed,
                            lambda_internes_fixed=lambda_internes_fixed,
                        )

                    def grad_fun(x, eM_test=eM_test):

                        return gradient_function_fixed_eM(
                            x,
                            eM_test,
                            num_knots,
                            l_array,
                            r_tgt_array,
                            min_knot_dist,
                            precomputed,
                            lambda_internes_fixed=lambda_internes_fixed,
                        )

                    try:
                        # Use analytic-gradient L-BFGS-B on spline parameters

                        res = scipy.optimize.minimize(
                            obj_fun,
                            current_x0,
                            method="L-BFGS-B",
                            bounds=bounds,
                            jac=grad_fun,
                            options={"ftol": 1e-9, "gtol": 1e-9, "maxiter": 2000},
                        )

                        mse = res.fun

                        if np.isfinite(mse) and mse <= mse_threshold * 2.0:
                            x_opt = res.x

                            # Reconstruct

                            n_k_v = x_opt[0:num_knots]

                            k_k_v = x_opt[num_knots : 2 * num_knots]

                            knot_l = np.concatenate(([l_min_val], np.sort(lambda_internes_fixed), [l_max_val]))

                            p_dspline = np.concatenate((n_k_v, k_k_v))

                            try:
                                n_c, k_c = get_nk_from_spline(p_dspline, knot_l, plot_lambda)

                                if mse <= mse_threshold:
                                    all_solutions.append(
                                        {
                                            "mse": mse,
                                            "n": n_c,
                                            "k": k_c,
                                            "eM": eM_test,
                                            "params": np.concatenate(([eM_test], x_opt, lambda_internes_fixed)),
                                        }
                                    )

                            except (
                                ValueError,
                                TypeError,
                                RuntimeError,
                                AttributeError,
                                KeyError,
                                IndexError,
                                FileNotFoundError,
                            ):
                                # Skip this solution if reconstruction fails

                                pass

                            current_x0 = x_opt.copy()

                        else:
                            # Reset to optimal if lost

                            current_x0 = x0_optimal_reduced.copy()

                    except (
                        ValueError,
                        TypeError,
                        RuntimeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        FileNotFoundError,
                    ) as e:
                        logging.error(f"Beam error at {eM_test}: {e}", exc_info=True)

                    processed_steps += 1

                    self.progress.emit(processed_steps, total_steps, self.optimal_mse)

            process_scan_range(eM_range_up, x0_optimal_reduced)

            process_scan_range(eM_range_down, x0_optimal_reduced)

            all_solutions.sort(key=lambda s: s["eM"])

            # Compute Statistics

            if not all_solutions:
                all_solutions.append({"mse": self.optimal_mse, "eM": eM_optimal})

            eM_vals = np.array([s["eM"] for s in all_solutions])

            n_stack = np.vstack([s["n"] for s in all_solutions])

            k_stack = np.vstack([s["k"] for s in all_solutions])

            stats = {
                "eM_mean": np.mean(eM_vals),
                "eM_std": np.std(eM_vals),
                "eM_min": np.min(eM_vals),
                "eM_max": np.max(eM_vals),
                "n_mean": np.mean(n_stack, axis=0),
                "n_std": np.std(n_stack, axis=0),
                "n_min": np.min(n_stack, axis=0),
                "n_max": np.max(n_stack, axis=0),
                "k_mean": np.mean(k_stack, axis=0),
                "k_std": np.std(k_stack, axis=0),
                "k_min": np.min(k_stack, axis=0),
                "k_max": np.max(k_stack, axis=0),
                "lambda_axis": plot_lambda,
                "count": len(all_solutions),
                "threshold": mse_threshold,
                "best_mse": self.optimal_mse,
                "all_solutions": all_solutions,
            }

            self.finished.emit(stats)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.error.emit(str(e))

            logging.error(f"Beam Worker Crash: {e}", exc_info=True)

    def stop(self) -> None:

        self.is_running = False


# =============================================================================


# MAIN WINDOW


# =============================================================================
