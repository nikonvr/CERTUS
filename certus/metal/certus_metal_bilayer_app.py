"""
CERTUS-METAL BILAYER: Qt workers and application window
=======================================================

The optimization worker, the beam-analysis worker and the CertusMetalBilayerApp
window, with the dielectric-thickness defaults of its form. The computation they
drive lives in certus_metal_bilayer_physics. The root launcher
CERTUS_METAL_BILAYER.py re-exports this module.
"""

import json
import logging
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyqtgraph as pg
import scipy.optimize
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    certus_timestamp_display,
    certus_timestamp_file,
    get_float_dtype,
)
from certus.metal.certus_metal_bilayer_physics import (
    _build_bilayer_bounds,
    _validate_bilayer_spline_state,
    global_objective_function,
)
from certus.metal.certus_metal_common import (
    DEFAULT_EM_MAX,
    DEFAULT_EM_MIN,
    DEFAULT_EXCEL_FILENAME,
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
    build_metal_startup_log_lines,
    build_metal_target_data,
    elevate_spline_knots,
    normalize_metal_progress_payload,
    setup_beam_analysis_thread,
    teardown_beam_thread,
)
from certus.metal.pglobal_adapter import run_pglobal_optimization
from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus_physics import (
    calculate_reflectance_bilayer_vectorized,
    compute_metal_bilayer_gradient_analytic,
    get_nk_cauchy_simple,
    get_nk_from_spline,
    get_nk_si,
)

# =============================================================================


# CONSTANTS


# =============================================================================


DEFAULT_EL_NOMINAL = "900"


DEFAULT_EL_VARIATION = "20"


# =============================================================================


# ANALYTIC GRADIENT (Hybrid: Analytic TMM + FD Spline Params)


# =============================================================================


# =============================================================================


# UI COMPONENTS


# =============================================================================


# =============================================================================


# WORKER THREAD


# =============================================================================


class OptimizationWorker(MetalOptimizationWorker):
    """Optimization worker thread (Metal Bilayer)"""

    # Signals inherited from MetalOptimizationWorker

    # __init__ inherited from MetalOptimizationWorker

    @pyqtSlot()
    def run(self):
        """

        Execute the metal bilayer optimization worker thread.

        This method performs the complete optimization workflow for metal bilayer structures including:

        - Parameter optimization for metal layers

        - Spectral calculationation and fitting

        - MSE calculationation and convergence checking

        - Progress tracking and signal emission

        Args:

            self: OptimizationWorker instance

        Returns:

            None

        Notes:

            - Logs operation details

            - Includes error handling

            - Emits progress and finished signals

            - Handles metal-specific optimization constraints

        """

        p = self.params

        float_dtype = get_float_dtype()

        target_lambda = p["target_lambda"].astype(float_dtype)

        target_r = p["target_r"].astype(float_dtype)

        nSub_precomputed = get_nk_si(target_lambda)

        # --- KNOT CONTINUATION (MESH REFINEMENT) LOGIC ---
        user_x0 = np.asarray(p.get("x0", []), dtype=float_dtype) if p.get("x0") is not None else np.array([])
        target_num_knots = p["num_knots"]
        
        if len(user_x0) > 0:
            knot_steps = [target_num_knots]
        else:
            knot_steps = list(range(2, target_num_knots + 1))
            
        total_steps = len(knot_steps)
        total_feval = int(p.get("maxfeval", 50000))
        feval_per_step = max(1000, total_feval // total_steps)
        iter_per_step = max(1, int(p.get("maxiter", DEFAULT_MAXITER)) // total_steps)
        
        current_x0 = user_x0 if len(user_x0) > 0 else None
        
        logger = logging.getLogger("CERTUS.METAL.BILAYER")
        logger.info("Starting Knot Continuation over steps: %s", knot_steps)
        
        result = None
        
        for step_idx, k in enumerate(knot_steps):
            if not self.is_running:
                break
                
            logger.info("--- KNOT STEP K=%d ---", k)
            
            # Elevate knots if continuing from a previous step
            if current_x0 is not None and k > 2 and len(user_x0) == 0:
                l_min, l_max = float(np.min(target_lambda)), float(np.max(target_lambda))
                current_x0 = elevate_spline_knots(current_x0, k - 1, l_min, l_max, offset=4)
                
            p_k = p.copy()
            p_k["num_knots"] = k
            
            # Build bounds
            bounds = np.array(_build_bilayer_bounds(p_k, l_array=target_lambda, include_eM=True), dtype=float_dtype)
            
            # Tighten bounds for k > 2
            if k > 2 and current_x0 is not None and len(user_x0) == 0:
                delta_eM = 5.0
                delta_eL = 20.0
                delta_n_inf = 0.02
                delta_A = 2000.0
                delta_nk = 0.5
                delta_l = 50.0
                
                bounds[0] = (max(bounds[0][0], current_x0[0] - delta_eM), min(bounds[0][1], current_x0[0] + delta_eM))
                bounds[1] = (max(bounds[1][0], current_x0[1] - delta_eL), min(bounds[1][1], current_x0[1] + delta_eL))
                bounds[2] = (max(bounds[2][0], current_x0[2] - delta_n_inf), min(bounds[2][1], current_x0[2] + delta_n_inf))
                bounds[3] = (max(bounds[3][0], current_x0[3] - delta_A), min(bounds[3][1], current_x0[3] + delta_A))
                
                for idx in range(4, 4 + 2 * k):
                    bounds[idx] = (max(bounds[idx][0], current_x0[idx] - delta_nk), min(bounds[idx][1], current_x0[idx] + delta_nk))
                for idx in range(4 + 2 * k, len(bounds)):
                    bounds[idx] = (max(bounds[idx][0], current_x0[idx] - delta_l), min(bounds[idx][1], current_x0[idx] + delta_l))

            if current_x0 is not None:
                # Guarantee current_x0 is strictly within the bounds to prevent optimizer crash
                lows = [b[0] for b in bounds]
                highs = [b[1] for b in bounds]
                current_x0 = np.clip(current_x0, lows, highs)

            args_for_objective = (
                k,
                target_lambda,
                target_r,
                p["min_knot_dist"],
                nSub_precomputed,
            )

            from certus.core._certus_physics_impl import PGlobalConfig
            cfg = PGlobalConfig.for_dimension(dim=len(bounds)).with_overrides(
                alpha=0.05,
                reduction_ratio=0.2,
                n_samples_per_iter=800,       # Fast global phase -> fluid UI for 8-17D
                local_search_budget=1500,     # Meaningful local search descent
                max_active_clusters=5,        # Focus deeply on the top 5 best basins
            )
            
            def make_callback(step_i, total_s, k=k):
                def callback(payload):
                    base_pct = step_i * (100.0 / total_s)
                    step_pct = payload.get("progress_pct", 0) / total_s
                    payload["progress_pct"] = base_pct + step_pct
                    payload["message"] = f"K={k} | " + payload.get("message", "")
                    payload["current_knots"] = k
                    self.progress.emit(payload)
                return callback

            try:
                result = run_pglobal_optimization(
                    lambda x, _args=args_for_objective: global_objective_function(x, *_args),
                    bounds,
                    x0=current_x0,
                    max_iter=iter_per_step,
                    max_feval=feval_per_step,
                    workers=int(p.get("workers", 1)),
                    stop_event=self._stop_event,
                    callback=make_callback(step_idx, total_steps),
                    progress_logger=lambda msg, _k=k: logging.getLogger("CERTUS.METAL.BILAYER").info("GLOBAL_OPT(PGlobal) K=%d %s", _k, msg),
                    ultra_wide=bool(p.get("ultra_wide", False)),
                    config=cfg,
                    skip_polish=(k < target_num_knots),
                )
                
                if result and hasattr(result, "x") and result.x is not None:
                    current_x0 = result.x

                logger.info(
                    "GLOBAL_OPT(PGlobal) complete success=%s best_rmse=%s iterations=%s evals=%s",
                    getattr(result, "success", None),
                    float(np.sqrt(max(float(getattr(result, "fun", float("inf"))), 0.0))) if result else float("inf"),
                    getattr(result, "nit", None) if result else 0,
                    getattr(result, "nfev", None) if result else 0,
                )

            except Exception as e:
                self.error.emit(str(e))
                return
                
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
            
        self.finished.emit({"result": result, "params": p})


class BeamAnalysisWorker(QObject):
    """

    Beam analysis worker: metal thickness scan

    Bi-directional outward scan from optimum for continuity

    """

    finished = pyqtSignal(dict)

    progress = pyqtSignal(int, int, float)  # current, total, current_best_mse

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

            # Global optimal solution

            eM_optimal = self.optimal_solution[0]

            eL_optimal = self.optimal_solution[1]

            n_infini_optimal = self.optimal_solution[2]

            A_diel_optimal = self.optimal_solution[3]

            offset = 4

            spline_knot_count = num_knots
            n_knots_optimal = self.optimal_solution[offset : offset + spline_knot_count]

            k_knots_optimal = self.optimal_solution[offset + spline_knot_count : offset + 2 * spline_knot_count]

            lambda_internes_optimal = self.optimal_solution[offset + 2 * spline_knot_count :]
            if n_knots_optimal.size != spline_knot_count or k_knots_optimal.size != spline_knot_count:
                raise ValueError(
                    f"Invalid optimal spline state: n_size={n_knots_optimal.size} k_size={k_knots_optimal.size} expected={spline_knot_count}"
                )

            # Initial x0 vector (without eM) for local optimization

            x0_optimal_reduced = np.concatenate(
                (
                    [eL_optimal, n_infini_optimal, A_diel_optimal],
                    n_knots_optimal,
                    k_knots_optimal,
                    lambda_internes_optimal,
                )
            )

            # BI-DIRECTIONAL SCAN STRATEGY

            # Define scan range, start from optimum and move outward

            eM_min_scan = max(1.0, eM_optimal - 20.0)

            eM_max_scan = eM_optimal + 20.0

            # Generate UP and DOWN ranges

            # Up: eM_optimal + step -> max

            eM_range_up = np.arange(eM_optimal + self.step_nm, eM_max_scan + 1e-6, self.step_nm)

            # Down: eM_optimal - step -> min

            eM_range_down = np.arange(eM_optimal - self.step_nm, eM_min_scan - 1e-6, -self.step_nm)

            total_steps = 1 + len(eM_range_up) + len(eM_range_down)

            # Optimization bounds (without eM) - shared helper

            bounds = _build_bilayer_bounds(self.params, l_array=l_array, include_eM=False)

            l_min_val, l_max_val = l_array.min(), l_array.max()

            # Smart MSE threshold (with absolute minimum)

            mse_threshold = max(self.optimal_mse * 1.25 + 1e-5, 2e-5)

            # OPTIMIZATION: Precompute If optical constants (only depends on wavelengths)

            nSub_precomputed = get_nk_si(l_array)

            import logging

            logger = logging.getLogger("CertusMetal")

            logger.info(f"Bi-directional Beam Analysis: Optimum at {eM_optimal:.2f} nm")

            logger.info(f"Scan UP: {len(eM_range_up)} steps, Scan DOWN: {len(eM_range_down)} steps")

            rmse_threshold_display = np.sqrt(mse_threshold) if mse_threshold >= 0 else 0.0

            logger.info(f"RMSE Threshold: {rmse_threshold_display:.2e}")

            all_solutions = []

            # 1. Add optimal solution (center point)

            plot_lambda = np.linspace(l_min_val, l_max_val, 300)

            knot_l_opt = np.concatenate(([l_min_val], np.sort(lambda_internes_optimal), [l_max_val]))

            p_spline_nk_opt = np.concatenate((n_knots_optimal, k_knots_optimal))

            if p_spline_nk_opt.size != 2 * knot_l_opt.size:
                raise ValueError(
                    f"Invalid spline state in beam analysis: coeff_size={p_spline_nk_opt.size} knot_size={knot_l_opt.size}"
                )

            n_calc_opt, k_calc_opt = get_nk_from_spline(p_spline_nk_opt, knot_l_opt, plot_lambda)

            all_solutions.append(
                {
                    "mse": self.optimal_mse,
                    "n": n_calc_opt,
                    "k": k_calc_opt,
                    "eM": eM_optimal,
                    "eL": eL_optimal,
                    "n_infini": n_infini_optimal,
                    "A_diel": A_diel_optimal,
                    "params": self.optimal_solution.copy(),
                }
            )

            processed_steps = 1

            beam_emit_interval_s = 5.0

            last_beam_emit_t = 0.0

            beam_stall_patience = int(self.params.get("beam_stall_patience", 10))

            beam_fail_patience = int(self.params.get("beam_fail_patience", 6))

            beam_min_rel_gain = float(self.params.get("beam_min_rel_gain", 2e-4))

            scan = SimpleNamespace(
                num_knots=num_knots,
                l_array=l_array,
                r_tgt_array=r_tgt_array,
                min_knot_dist=min_knot_dist,
                x0_optimal_reduced=x0_optimal_reduced,
                total_steps=total_steps,
                bounds=bounds,
                l_min_val=l_min_val,
                l_max_val=l_max_val,
                mse_threshold=mse_threshold,
                nSub_precomputed=nSub_precomputed,
                logger=logger,
                all_solutions=all_solutions,
                plot_lambda=plot_lambda,
                processed_steps=processed_steps,
                beam_emit_interval_s=beam_emit_interval_s,
                last_beam_emit_t=last_beam_emit_t,
                beam_stall_patience=beam_stall_patience,
                beam_fail_patience=beam_fail_patience,
                beam_min_rel_gain=beam_min_rel_gain,
            )

            # Start both scans

            self._scan_the_thickness_range(scan, eM_range_up, x0_optimal_reduced, "UP")

            self._scan_the_thickness_range(scan, eM_range_down, x0_optimal_reduced, "DOWN")

            self.progress.emit(total_steps, total_steps, self.optimal_mse)

            # --- ANALYSIS END ---

            # Sort solutions by thickness for export

            all_solutions.sort(key=lambda s: s["eM"])

            # Final stats

            if not all_solutions:  # Should not happen as we add optimal
                all_solutions.append(
                    {
                        "mse": self.optimal_mse,
                        "eM": eM_optimal,
                        "n": n_calc_opt,
                        "k": k_calc_opt,
                    }
                )  # Minimal fallback

            n_stack = np.array([s["n"] for s in all_solutions])

            k_stack = np.array([s["k"] for s in all_solutions])

            eM_stack = np.array([s["eM"] for s in all_solutions])

            eL_stack = np.array([s["eL"] for s in all_solutions])

            stats = {
                "lambda_axis": plot_lambda,
                "n_mean": np.mean(n_stack, axis=0),
                "n_std": np.std(n_stack, axis=0),
                "n_min": np.min(n_stack, axis=0),
                "n_max": np.max(n_stack, axis=0),
                "k_mean": np.mean(k_stack, axis=0),
                "k_std": np.std(k_stack, axis=0),
                "k_min": np.min(k_stack, axis=0),
                "k_max": np.max(k_stack, axis=0),
                "eM_mean": np.mean(eM_stack),
                "eM_std": np.std(eM_stack),
                "eM_min": np.min(eM_stack),
                "eM_max": np.max(eM_stack),
                "eL_mean": np.mean(eL_stack),
                "eL_std": np.std(eL_stack),
                "count": len(all_solutions),
                "best_mse": min([s["mse"] for s in all_solutions]),
                "optimal_mse": self.optimal_mse,
                "threshold": mse_threshold,
                "all_solutions": all_solutions,
            }

            self.finished.emit(stats)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logging.error(f"Beam analysis error: {e}", exc_info=True)

            self.error.emit(f"Beam analysis error:\n{traceback.format_exc()}")

    def _scan_the_thickness_range(self, scan, eM_list, start_x0, _direction_label=""):
        """Re-optimize the stack at each metal thickness of one list, starting from a point and following the valley from one step to the next; stop the branch when it stagnates and its fits are poor."""
        current_x0 = start_x0.copy()
        branch_best_mse = float(self.optimal_mse)
        no_gain_steps = 0
        poor_quality_steps = 0
        for eM_test in eM_list:
            if not self.is_running:
                return

            # L-BFGS-B optimization (fast and precise if close)

            try:
                # Coupled objective+gradient: avoids duplicate heavy evaluations in SciPy

                # (otherwise fun(x) and jac(x) call the same expensive kernel separately).

                def obj_and_grad_fixed_eM(x, eM_test=eM_test):

                    x_full = np.concatenate(([eM_test], x))
                    cost_full, g_full = compute_metal_bilayer_gradient_analytic(
                        x_full,
                        scan.num_knots,
                        scan.l_array,
                        scan.r_tgt_array,
                        scan.min_knot_dist,
                        scan.nSub_precomputed,
                    )
                    return float(cost_full), g_full[1:]  # Exclude eM gradient
                res = scipy.optimize.minimize(
                    obj_and_grad_fixed_eM,
                    current_x0,
                    method="L-BFGS-B",
                    bounds=scan.bounds,
                    jac=True,
                    options={"ftol": 1e-9, "gtol": 1e-9, "maxiter": 2000},
                )

                # If failed or bad MSE, retry L-BFGS-B with relaxed tolerances (analytic jac kept)

                if (not res.success) or (res.fun > scan.mse_threshold * 1.5):
                    res_retry_grad = scipy.optimize.minimize(
                        obj_and_grad_fixed_eM,
                        current_x0,
                        method="L-BFGS-B",
                        bounds=scan.bounds,
                        jac=True,
                        options={"ftol": 1e-7, "gtol": 1e-7, "maxiter": 3000},
                    )
                    if res_retry_grad.fun < res.fun:
                        res = res_retry_grad
                mse = res.fun
                has_meaningful_gain = np.isfinite(mse) and (mse < branch_best_mse * (1.0 - scan.beam_min_rel_gain))
                if has_meaningful_gain:
                    branch_best_mse = float(mse)
                    no_gain_steps = 0

                else:
                    no_gain_steps += 1

                # Track consecutive low-quality points (outside useful beam region)

                if np.isfinite(mse) and mse <= scan.mse_threshold:
                    poor_quality_steps = 0

                else:
                    poor_quality_steps += 1

                # Verify validity

                if np.isfinite(mse) and mse <= scan.mse_threshold * 2.0:  # Accept wide for continuity
                    # Reconstruct solution

                    x_opt = res.x
                    eL_v, n_inf_v, A_v = x_opt[0], x_opt[1], x_opt[2]
                    spline_knot_count = scan.num_knots
                    n_k_v = x_opt[3 : 3 + spline_knot_count]
                    k_k_v = x_opt[3 + spline_knot_count : 3 + 2 * spline_knot_count]
                    l_int_v = x_opt[3 + 2 * spline_knot_count :]
                    if n_k_v.size != spline_knot_count or k_k_v.size != spline_knot_count:
                        raise ValueError(
                            f"Invalid beam spline state: n_size={n_k_v.size} k_size={k_k_v.size} expected={spline_knot_count}"
                        )
                    knot_l = np.concatenate(([scan.l_min_val], np.sort(l_int_v), [scan.l_max_val]))
                    p_spline = np.concatenate((n_k_v, k_k_v))
                    if p_spline.size != 2 * knot_l.size:
                        raise ValueError(
                            f"Invalid spline state during beam scan: coeff_size={p_spline.size} knot_size={knot_l.size}"
                        )
                    n_c, k_c = get_nk_from_spline(p_spline, knot_l, scan.plot_lambda)

                    # If MSE acceptable for final beam

                    if mse <= scan.mse_threshold:
                        scan.all_solutions.append(
                            {
                                "mse": mse,
                                "n": n_c,
                                "k": k_c,
                                "eM": eM_test,
                                "eL": eL_v,
                                "n_infini": n_inf_v,
                                "A_diel": A_v,
                                "params": np.concatenate(([eM_test], x_opt)),
                            }
                        )

                    # Update start point for next step (Continuity)

                    current_x0 = x_opt.copy()

                else:
                    # If trace lost (MSE explodes), retry with x0_optimal

                    # If fails again, stop branch

                    scan.logger.debug(f"Continuity loss at {eM_test:.2f} nm (MSE={mse:.2e}). Resetting.")

                    res_retry = scipy.optimize.minimize(
                        obj_and_grad_fixed_eM,
                        scan.x0_optimal_reduced,
                        method="L-BFGS-B",
                        bounds=scan.bounds,
                        jac=True,  # Keep analytic gradient in all retries
                        options={"ftol": 1e-7, "gtol": 1e-7, "maxiter": 3000},
                    )

                    if res_retry.fun < scan.mse_threshold:
                        current_x0 = res_retry.x.copy()  # Found a valley

                    else:
                        # Stop branch if nothing good found

                        # logger.info(f"Stopping branch {direction_label} at {eM_test:.2f} nm")

                        # Continue a bit just in case

                        current_x0 = scan.x0_optimal_reduced.copy()

                        poor_quality_steps += 1

            except (
                ValueError,
                TypeError,
                RuntimeError,
                AttributeError,
                KeyError,
                IndexError,
                FileNotFoundError,
            ) as e:
                scan.logger.error(f"Error at {eM_test:.2f}: {e}", exc_info=True)

                current_x0 = scan.x0_optimal_reduced.copy()

                no_gain_steps += 1

                poor_quality_steps += 1

            scan.processed_steps += 1

            now = time.time()

            if scan.processed_steps >= scan.total_steps or now - scan.last_beam_emit_t >= scan.beam_emit_interval_s:
                scan.last_beam_emit_t = now

                self.progress.emit(scan.processed_steps, scan.total_steps, self.optimal_mse)

            # Early stop for this branch when scan is both stagnant and low-quality.

            if no_gain_steps >= scan.beam_stall_patience and poor_quality_steps >= scan.beam_fail_patience:
                scan.logger.info(
                    f"Early stop {_direction_label}: stagnation at eM={eM_test:.2f} nm "
                    f"(no_gain={no_gain_steps}, poor={poor_quality_steps})"
                )

                break

    def stop(self):

        self.is_running = False


# =============================================================================


# MAIN WINDOW


# =============================================================================
