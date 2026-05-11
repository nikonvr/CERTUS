"""


CERTUS-METAL SINGLE CERTUS_SUITE_26_01


======================================


Metal Index Determination on Transparent substrate (Silica/BK7)


Determines the complex refractive index (n, k) of a metal layer deposited


on top of a transparent substrate (Silica or BK7).


Structure: Air | Metal (eM) | substrate (Incoherent)


Uses differential evolution optimization to extract metal optical constants


from Reflectance (Front), Transmission, and Back-Reflectance measurements.


The metal index is modeld as wavelength-dependent splines.


"""

__version__ = "26_01"


import logging


import os
from pathlib import Path


import sys




import traceback


import scipy.optimize


from scipy.interpolate import CubicSpline


from certus_core import create_module_environment, setup_logging


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


env = create_module_environment(__file__, "METAL_SINGLE")


script_dir = env["script_dir"]


# Configure GUI


import warnings


warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy.optimize")


import numpy as np


import pandas as pd


import pyqtgraph as pg


from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot


from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)


# --- 1. CORE (Config, Constants, Utils) ---


from certus_core import get_float_dtype, get_resource_path, certus_timestamp_display, certus_timestamp_file


# --- 4. DATA (IO, Reporting) ---


from certus_data import (
    OPENPYXL_AVAILABLE,
    read_data_file_robust,
    to_excel_robust,
)


# --- 5. ERRORS (Validation, Messages) ---


from certus_errors import (
    get_error_message,
    show_error,
)


# --- 5. METAL COMMON ---


from certus_metal_common import (
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
    MetalBaseApp,
    MetalOptimizationWorker,
    metal_optimization_worker_run_differential_evolution,
    normalize_percent_column,
    setup_beam_analysis_thread,
    teardown_beam_thread,
)


# --- 2. PHYSICS (Models, Optimization, Utils) ---


from certus_physics import (
    _compute_single_layer_sensitivity_kernel,
    calculate_RTRback_incoherent_vectorized,
    get_n_substrate_array_by_id,
    get_nk_from_spline,
)


# --- 3. UI (Theme, Widgets) ---


from certus_ui import (
    CertusCard,
    CertusScientificPlot,
    CertusTheme,
    DATA_FILES_FILTER_EXTENDED,
    FlashyCard,
    get_export_config,
    init_certus_app,
    open_data_file_and_read,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
)


from certus_load_summary import build_summary_plain_text, show_load_summary_dialog


# Install exception handler


setup_gui_exception_handling()


# PyQtGraph configured via COMMON utility


setup_pyqtgraph_defaults()


# =============================================================================


# CONSTANTS


# =============================================================================


# Constants imported from certus_metal_common


# Silicon Data: clues.xlsx -> Si-substrate (Single Source of Truth), accessed via certus_physics.


def _build_single_bounds(
    params: dict,
    l_array: "np.ndarray | None" = None,
    include_eM: bool = True,
) -> list:
    """Build scipy bounds list for single-layer DE. If include_eM=False, omit first (eM) bound."""

    bounds = []

    if include_eM:
        bounds.append((params["eM_min"], params["eM_max"]))

    num_knots = params["num_knots"]

    nk_min = params.get("nk_min", DEFAULT_NK_MIN)

    nk_max = params.get("nk_max", DEFAULT_NK_MAX)

    bounds += [(nk_min, nk_max)] * (2 * num_knots)

    num_internal_knots = num_knots - 2

    if num_internal_knots > 0 and l_array is not None:
        l_min, l_max = l_array.min(), l_array.max()

        bounds += [(l_min, l_max)] * num_internal_knots

    return bounds


# =============================================================================


# OPTIMIZATION OBJECTIVE FUNCTION


# =============================================================================


def _single_RTRback_mse(
    x,
    l_array,
    r_tgt,
    num_knots,
    min_knot_dist,
    nSub_complex_array,
    precomputed,
    eM_fixed: "float | None" = None,
    t_tgt: "np.ndarray | None" = None,
    rb_tgt: "np.ndarray | None" = None,
    use_cache: bool = False,
    min_knot_diff: "float | None" = None,
) -> float:
    """

    Single-layer R/T/Rback MSE. Returns 1e12 or np.inf on constraint violation.

    If eM_fixed is None: x = [eM, n_knots..., k_knots..., lambda_internes...].

    If eM_fixed is set: x = [n_knots..., k_knots..., lambda_internes...], eM = eM_fixed.

    If t_tgt and rb_tgt are provided, returns average of R/T/Rback MSE; else R-only MSE.

    min_knot_diff: if set (e.g. 1e-5), reject if any np.diff(knot_l) <= min_knot_diff.

    """

    if eM_fixed is None:
        eM = x[0]

        offset = 1

    else:
        eM = eM_fixed

        offset = 0

    min_lambda = precomputed["min_lambda"]

    max_lambda = precomputed["max_lambda"]

    eM_buffer = precomputed["eM_buffer"]

    knot_l_buffer = precomputed["knot_l_buffer"]

    p_spline_buffer = precomputed["p_spline_buffer"]

    if eM < 0:
        return 1e12

    n_knots_vals = x[offset : offset + num_knots]

    k_knots_vals = x[offset + num_knots : offset + 2 * num_knots]

    lambda_internes = x[offset + 2 * num_knots :]

    len_lambda_int = len(lambda_internes)

    knot_l_buffer[0] = min_lambda

    if len_lambda_int > 0:
        knot_l_buffer[1 : 1 + len_lambda_int] = np.sort(lambda_internes)

    knot_l_buffer[num_knots - 1] = max_lambda

    knot_l = knot_l_buffer[:num_knots]

    if len_lambda_int > 0 and np.any(np.diff(knot_l) < min_knot_dist):
        return 1e12

    if min_knot_diff is not None and len_lambda_int > 0 and np.any(np.diff(knot_l) <= min_knot_diff):
        return 1e12

    p_spline_buffer[:num_knots] = n_knots_vals

    p_spline_buffer[num_knots : 2 * num_knots] = k_knots_vals

    p_spline_nk = p_spline_buffer[: 2 * num_knots]

    try:
        n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=use_cache)

        if not (np.all(np.isfinite(n_calc)) and np.all(np.isfinite(k_calc))):
            return 1e12

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
        return 1e12

    nM_complex_2d = (n_calc - 1j * k_calc).reshape(-1, 1)

    eM_buffer[0] = eM

    R_calc, T_calc, Rb_calc = calculate_RTRback_incoherent_vectorized(
        eM_buffer, nM_complex_2d, nSub_complex_array, l_array
    )

    mse_r = np.nanmean((R_calc - r_tgt) ** 2)

    if t_tgt is not None and rb_tgt is not None:
        mse_t = np.nanmean((T_calc - t_tgt) ** 2)

        mse_rb = np.nanmean((Rb_calc - rb_tgt) ** 2)

        total_mse = 0.0

        count = 0

        if np.isfinite(mse_r):
            total_mse += mse_r

            count += 1

        if np.isfinite(mse_t):
            total_mse += mse_t

            count += 1

        if np.isfinite(mse_rb):
            total_mse += mse_rb

            count += 1

        if count == 0:
            return 1e12

        return total_mse / count

    mse = np.mean((R_calc - r_tgt) ** 2)

    return mse if np.isfinite(mse) else np.inf


def global_objective_function(
    x,
    num_knots,
    l_array,
    r_tgt,
    t_tgt,
    rb_tgt,
    min_knot_dist,
    nSub_complex_array,
    precomputed: dict,
) -> float:
    """

    Differential evolution objective function for Single Metal on Transparent substrate.

    Optimizes: eM (thickness) + Spline Knots (n, k).

    """

    return _single_RTRback_mse(
        x,
        l_array,
        r_tgt,
        num_knots,
        min_knot_dist,
        nSub_complex_array,
        precomputed,
        eM_fixed=None,
        t_tgt=t_tgt,
        rb_tgt=rb_tgt,
        use_cache=True,
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

        p = self.params

        float_dtype = get_float_dtype()

        target_lambda = p["target_lambda"].astype(float_dtype)

        target_r = p["target_r"].astype(float_dtype)

        target_t = p["target_t"].astype(float_dtype)

        target_rb = p["target_rb"].astype(float_dtype)

        substrate_id = p["substrate_id"]

        nSub_real = get_n_substrate_array_by_id(substrate_id, target_lambda)

        nSub_complex_array = nSub_real.astype(np.complex128) + 0j

        num_knots = p["num_knots"]

        precomputed = {
            "min_lambda": target_lambda.min(),
            "max_lambda": target_lambda.max(),
            "eM_buffer": np.empty(1, dtype=float_dtype),
            "knot_l_buffer": np.empty(num_knots, dtype=float_dtype),
            "p_spline_buffer": np.empty(2 * num_knots, dtype=float_dtype),
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

        metal_optimization_worker_run_differential_evolution(self, global_objective_function, args_for_objective)


# =============================================================================


# NUMBA FUNCTIONS (Precision-aware)


# =============================================================================


# =============================================================================


# BEAM ANALYSIS (SINGLE LAYER)


# =============================================================================


def objective_function_fixed_eM(
    x,
    eM_fixed,
    num_knots,
    l_array,
    r_tgt_array,
    min_knot_dist,
    precomputed,
    lambda_internes_fixed=None,
):
    """

    Objective function for Beam Analysis (Fixed Thickness eM).

    Optimizes only the Spline Knots (n, k).

    x = [n_knots... | k_knots...]

    lambda_internes are fixed from the global optimum for this beam scan.

    """

    if not np.all(np.isfinite(x)):
        return np.inf

    if lambda_internes_fixed is None:
        lambda_internes_fixed = np.empty(0, dtype=np.float64)

    x_full = np.concatenate((x, np.asarray(lambda_internes_fixed, dtype=np.float64)))

    return _single_RTRback_mse(
        x_full,
        l_array,
        r_tgt_array,
        num_knots,
        min_knot_dist,
        precomputed["nSub_complex_array"],
        precomputed,
        eM_fixed=eM_fixed,
        t_tgt=None,
        rb_tgt=None,
        use_cache=False,
        min_knot_diff=1e-5,
    )


def gradient_function_fixed_eM(
    x,
    eM_fixed,
    num_knots,
    l_array,
    r_tgt_array,
    min_knot_dist,
    precomputed,
    lambda_internes_fixed=None,
):
    """

    Analytic gradient for fixed-eM objective (R-only in Beam mode).

    """

    # Beam local scan: optimize only knot values (n/k). Internal knot positions are fixed.

    grad = np.zeros(2 * num_knots, dtype=np.float64)

    if not np.all(np.isfinite(x)):
        return grad

    min_lambda = precomputed["min_lambda"]

    max_lambda = precomputed["max_lambda"]

    n_knots_vals = x[0:num_knots]

    k_knots_vals = x[num_knots : 2 * num_knots]

    if lambda_internes_fixed is None:
        lambda_internes_fixed = np.empty(0, dtype=np.float64)

    lambda_internes = np.asarray(lambda_internes_fixed, dtype=np.float64)

    knot_l = np.concatenate(([min_lambda], np.sort(lambda_internes), [max_lambda]))

    if len(lambda_internes) > 0 and np.any(np.diff(knot_l) < min_knot_dist):
        return grad

    p_spline_nk = np.concatenate((n_knots_vals, k_knots_vals))

    try:
        n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=False)

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
        return grad

    if not (np.all(np.isfinite(n_calc)) and np.all(np.isfinite(k_calc))):
        return grad

    nSub_complex_array = precomputed["nSub_complex_array"]

    eM_val = float(eM_fixed)

    n_pts = max(len(l_array), 1)

    fac_r = 2.0 / n_pts

    dJ_dn = np.zeros_like(n_calc, dtype=np.float64)

    dJ_dk = np.zeros_like(k_calc, dtype=np.float64)

    nM_complex_2d = (n_calc - 1j * k_calc).reshape(-1, 1)

    R_calc, _, _ = calculate_RTRback_incoherent_vectorized(
        np.array([eM_val], dtype=np.float64), nM_complex_2d, nSub_complex_array, l_array
    )

    for i, wl in enumerate(l_array):
        nr = float(n_calc[i])

        ki = float(k_calc[i])

        ns = float(np.real(nSub_complex_array[i]))

        _, _, dRdn, dRdk, _, _ = _compute_single_layer_sensitivity_kernel(wl, nr, ki, eM_val, ns)

        dr = float(R_calc[i] - r_tgt_array[i])

        dJ_dn[i] = fac_r * dr * dRdn

        dJ_dk[i] = fac_r * dr * dRdk

    # Spline basis mapping (same strategy as bilayer analytic wrapper)

    basis = np.zeros((num_knots, len(l_array)), dtype=np.float64)

    for i in range(num_knots):
        unit_vals = np.zeros(num_knots, dtype=np.float64)

        unit_vals[i] = 1.0

        spline_basis = CubicSpline(knot_l, unit_vals, bc_type="natural", extrapolate=False)

        basis_vals = spline_basis(l_array)

        basis[i, :] = np.nan_to_num(basis_vals, nan=0.0)

    for i in range(num_knots):
        grad[i] = np.dot(dJ_dn, basis[i, :])

        grad[num_knots + i] = np.dot(dJ_dk, basis[i, :])

    return grad


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

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
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

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.error.emit(str(e))

            logging.error(f"Beam Worker Crash: {e}", exc_info=True)

    def stop(self) -> None:

        self.is_running = False


# =============================================================================


# MAIN WINDOW


# =============================================================================


class CertusMetalSingleApp(MetalBaseApp):
    """Main CERTUS-METAL Application"""

    # MetalBaseApp handles APP_NAME/TITLE via __init__ or class vars if we set them,

    # but MetalBaseApp __init__ takes args.

    MODULE_ID = "CERTUS_METAL_SINGLE"

    def __init__(self) -> None:

        # Pass title to base

        super().__init__(
            app_name="CERTUS-METAL-SINGLE",
            app_title="Metal Single Layer (Transparent substrate)",
        )

        # METAL-specific state (additions to base)

        self.worker = None

        self.optimization_thread = None

        self.beam_worker = None

        self.beam_thread = None

        self._last_worker_params = None  # Cache for thread-safe access

    def _setup_parameter_grid(self, layout) -> None:
        """Standard Metal Single Params"""

        # Row 0: Input Data (Base)

        layout.addWidget(self._create_input_group(), 0, 0, 1, 2)

        # Row 1: Physical (left) + Material (right)

        layout.addWidget(self._create_physical_params_group(), 1, 0)

        layout.addWidget(self._create_material_params_group(), 1, 1)

        # Row 2: Output + Live

        layout.addWidget(self._create_output_group(), 2, 0)

        layout.addWidget(self._create_live_params_group(), 2, 1)

        layout.setColumnStretch(0, 1)

        layout.setColumnStretch(1, 1)

    def _setup_plots(self) -> None:
        """Standard Metal Plots"""

        self.reflectance_plot = CertusScientificPlot(
            self,
            "Reflectance Comparison (Target vs Calculated)",
            "Reflectance",
            "Wavelength (nm)",
        )

        self.reflectance_plot.addLegend(offset=(-10, 10))

        self.reflectance_plot.showGrid(x=True, y=True)

        self.target_curve = self.reflectance_plot.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=3,
            symbolPen=None,
            symbolBrush="k",
            name="Target",
        )

        self.calc_r_curve = self.reflectance_plot.plot(
            [], [], pen=pg.mkPen(CertusTheme.CHART_PRIMARY, width=2), name="Calc R"
        )

        self.calc_t_curve = self.reflectance_plot.plot(
            [], [], pen=pg.mkPen(CertusTheme.SUCCESS, width=2), name="Calc T"
        )

        self.calc_rb_curve = self.reflectance_plot.plot(
            [], [], pen=pg.mkPen(CertusTheme.WARNING, width=2), name="Calc Rb"
        )

        self.tabs.addTab(self.reflectance_plot, "Spectra")

        self.clues_plot = CertusScientificPlot(
            self,
            "Optimized Metal Optical Constants (n, k)",
            "Refractive Index (n)",
            "Wavelength (nm)",
        )

        self.p1 = self.clues_plot.getPlotItem()

        self.p2 = pg.ViewBox()

        self.p1.showAxis("right")

        self.p1.scene().addItem(self.p2)

        self.p1.getAxis("right").linkToView(self.p2)

        self.p2.setXLink(self.p1)

        self.p1.getAxis("left").setLabel("Refractive Index (n)", color=CertusTheme.CHART_PRIMARY)

        self.p1.getAxis("right").setLabel("Extinction Coefficient (k)", color=CertusTheme.CHART_DANGER)

        self.n_curve = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.CHART_PRIMARY, width=2))

        self.k_curve = pg.PlotCurveItem(pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2, style=Qt.PenStyle.DashLine))

        self.p1.addItem(self.n_curve)

        self.p2.addItem(self.k_curve)

        def _sync_p2_geometry(*_args):
            self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        self.p1.vb.sigResized.connect(_sync_p2_geometry)

        self.tabs.addTab(self.clues_plot, "n & k")

        self.mse_plot = CertusScientificPlot(
            self,
            "Optimization Convergence (Total RMSE)",
            "Root Mean Squared Error (RMSE)",
            "Iteration",
        )

        self.mse_plot.showGrid(x=True, y=True)

        self.mse_plot.setLogMode(y=True)

        self.mse_curve = self.mse_plot.plot([], [], pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2))

        self.tabs.addTab(self.mse_plot, "Convergence")

        # Why CERTUS? tab

        self.perf_tab = QWidget()

        perf_layout = QGridLayout(self.perf_tab)

        perf_layout.setSpacing(20)

        perf_layout.setContentsMargins(30, 30, 30, 30)

        c1 = FlashyCard(
            "Flexible n(lambda), k(lambda) Model",
            "Spline interpolation for real metals\nCaptures fine dispersion variations",
            icon="🚀",
        )

        c2 = FlashyCard(
            "Accelerated Numba TMM",
            "Vectorized thin film computation\nResponse time close to native",
            icon="⚡",
        )

        c3 = FlashyCard(
            "Dual-Axis n & k Tracking",
            "Simultaneous reading of index/extinction\nClear analysis of material physics",
            icon="📈",
        )

        c4 = FlashyCard(
            "Stable Global Optimization",
            "Differential Evolution + local polish\nFewer local minima traps",
            icon="🔮",
        )

        perf_layout.addWidget(c1, 0, 0)

        perf_layout.addWidget(c2, 0, 1)

        perf_layout.addWidget(c3, 1, 0)

        perf_layout.addWidget(c4, 1, 1)

        self.tabs.addTab(self.perf_tab, "Why CERTUS?")

    def _warmup_numba(self) -> None:
        """JIT precompilation"""

        try:
            # Warmup specific to Single Metal (Spline + Incoherent substrate)

            wls = np.array([500.0, 600.0], dtype=np.float64)

            # 1. Warmup Spline

            p_spline = np.array([1.5, 1.5, 0.5, 0.5], dtype=np.float64)

            knot_l = np.array([400.0, 800.0], dtype=np.float64)

            get_nk_from_spline(p_spline, knot_l, wls)

            # 2. Warmup TMM (Incoherent)

            # Create dummy arrays

            eM = np.array([20.0], dtype=np.float64)

            nM_complex_2d = np.array([[1.5 - 0.5j], [1.5 - 0.5j]], dtype=np.complex128)

            nSub = np.array([1.45 + 0j, 1.45 + 0j], dtype=np.complex128)

            calculate_RTRback_incoherent_vectorized(eM, nM_complex_2d, nSub, wls)

            self._on_numba_ready()  # Mark as ready

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"✗ Numba warmup failed: {e}", exc_info=True)

    def on_file_loaded(self, data: "np.ndarray") -> None:
        """Process loaded data (Hook from MetalBaseApp)"""

        try:
            # data is sorted numpy array [lambda, ...]

            # Detect columns:

            # 2 cols: Lambda, R

            # 3 cols: Lambda, R, T

            # 4 cols: Lambda, R, T, Rback (Target format for Single)

            cols = data.shape[1]

            self.target_data = {}

            self.target_data["lambda"] = data[:, 0]

            # R (Col 1)

            if cols >= 2:
                self.target_data["R"] = normalize_percent_column(data[:, 1])

            # T (Col 2)

            if cols >= 3:
                self.target_data["T"] = normalize_percent_column(data[:, 2])

            else:
                self.target_data["T"] = np.full_like(data[:, 0], np.nan)

            # Rback (Col 3)

            if cols >= 4:
                self.target_data["Rback"] = normalize_percent_column(data[:, 3])

            else:
                self.target_data["Rback"] = np.full_like(data[:, 0], np.nan)

            # Update Plots

            if hasattr(self, "target_curve"):
                self.target_curve.setData(self.target_data["lambda"], self.target_data["R"])

            self.update_lambda_filters()

            if hasattr(self, "reflectance_plot"):
                self.reflectance_plot.autoRange()

            self.logger.info(f"Loaded Data: {cols} columns. Points: {len(data)}")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"Error parsing data: {e}")

            QMessageBox.warning(self, "Data Error", f"Could not parse data columns: {e}")

    def _create_physical_params_group(self) -> CertusCard:
        """Creates compact physical params group with Info Icons"""

        c = CertusCard("Physical Parameters")

        l = c.body

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        self.widgets["eM_min"] = QLineEdit(str(DEFAULT_EM_MIN))

        self.widgets["eM_min"].setFixedHeight(24)

        self.widgets["eM_max"] = QLineEdit(str(DEFAULT_EM_MAX))

        self.widgets["eM_max"].setFixedHeight(24)

        l.addLayout(
            self._create_labeled_input(
                "eM min:",
                self.widgets["eM_min"],
                "Minimum expected thickness of the metal layer (nm).",
            )
        )

        l.addLayout(
            self._create_labeled_input(
                "eM max:",
                self.widgets["eM_max"],
                "Maximum expected thickness of the metal layer (nm).",
            )
        )

        return c

    def _create_material_params_group(self) -> CertusCard:
        """Creates compact material params group with Info Icons"""

        c = CertusCard("Material Parameters")

        l = c.body

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        # substrate Selector

        from PyQt6.QtWidgets import QComboBox

        self.combo_substrate = QComboBox()

        self.combo_substrate.setToolTip("Select the transparent substrate material.")

        self.combo_substrate.addItems(["Fused Silica", "BK7"])

        self.combo_substrate.setFixedHeight(24)

        l.addLayout(self._create_labeled_input("substrate:", self.combo_substrate, "substrate Material (Transparent)."))

        # Metal Inputs

        self.widgets["num_knots"] = QLineEdit(str(DEFAULT_NUM_KNOTS))

        self.widgets["num_knots"].setFixedHeight(24)

        self.widgets["nk_min"] = QLineEdit(str(DEFAULT_NK_MIN))

        self.widgets["nk_min"].setFixedHeight(24)

        self.widgets["nk_max"] = QLineEdit(str(DEFAULT_NK_MAX))

        self.widgets["nk_max"].setFixedHeight(24)

        self.widgets["min_knot_dist"] = QLineEdit(str(DEFAULT_MIN_KNOT_DISTANCE))

        self.widgets["min_knot_dist"].setFixedHeight(24)

        l.addSpacing(10)

        l.addLayout(
            self._create_labeled_input(
                "Knots:",
                self.widgets["num_knots"],
                "Number of control points for B-Spline.",
            )
        )

        l.addLayout(self._create_labeled_input("n,k min:", self.widgets["nk_min"], "Lower bound for n and k."))

        l.addLayout(self._create_labeled_input("n,k max:", self.widgets["nk_max"], "Upper bound for n and k."))

        l.addLayout(
            self._create_labeled_input(
                "Knot Dist:",
                self.widgets["min_knot_dist"],
                "Minimum spectral distance between knots (nm).",
            )
        )

        return c

    def load_target_file(self, filepath=None):
        """Loads target file (robust CSV/Excel)"""

        if filepath is None or isinstance(filepath, bool):
            filepath, _ = open_data_file_and_read(
                self,
                "Open Reflectance File",
                DATA_FILES_FILTER_EXTENDED,
            )

            if filepath is None:
                return

        if not filepath:
            return

        try:
            from certus_data import load_spectrum_columns

            roles = {0: "lambda", 1: "R", 2: "T", 3: "Rback"}

            res = load_spectrum_columns(
                filepath, max_columns=4, normalise_percent=True, sort_ascending=True, column_roles=roles
            )

            wls = res.x

            R_val = res.y_columns.get("R", np.full_like(wls, np.nan))

            T_val = res.y_columns.get("T", np.full_like(wls, np.nan))

            Rb_val = res.y_columns.get("Rback", np.full_like(wls, np.nan))

            # Warning if data missing

            if len(res.y_columns) < 3:
                msg = []

                if "T" not in res.y_columns:
                    msg.append("Transmission (T)")

                if "Rback" not in res.y_columns:
                    msg.append("Back-Reflectance (Rback)")

                QMessageBox.warning(
                    self,
                    "Data Warning",
                    f"Some columns are missing:\n{', '.join(msg)}\n\n"
                    "Optimization will proceed using available data only.",
                )

            target_data = {"lambda": wls, "R": R_val, "T": T_val, "Rback": Rb_val}

            self.target_data = target_data

            self._last_target_file = filepath  # Save path for JSON

            self.lbl_file.setText(Path(filepath).name)

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                n_rows = res.n_rows

                lmin = float(np.nanmin(wls)) if n_rows else float("nan")

                lmax = float(np.nanmax(wls)) if n_rows else float("nan")

                summary = build_summary_plain_text(
                    "CERTUS METAL SINGLE - Load Summary",
                    [
                        f"File: {Path(filepath).resolve()}",
                        "",
                        "General",
                        (f"Rows: {n_rows}", n_rows <= 0),
                        "",
                        "Data",
                        (
                            f"Wavelength range: [{lmin:.1f}, {lmax:.1f}] nm",
                            not (np.isfinite(lmin) and np.isfinite(lmax) and lmax > lmin),
                        ),
                        ("Reflectance column (R): yes", bool(np.all(np.isnan(R_val)))),
                        (f"Transmission column (T): {'yes' if not np.all(np.isnan(T_val)) else 'no'}", False),
                        (f"Back-reflectance column (Rback): {'yes' if not np.all(np.isnan(Rb_val)) else 'no'}", False),
                        "",
                        "Compatibility checks",
                        (
                            "Potential unit conversion applied (% -> fraction): "
                            f"{'yes' if res.normalised_to_fraction else 'no'}",
                            False,
                        ),
                    ],
                )

                show_load_summary_dialog(self, "METAL SINGLE Load Summary", summary)

            # Update plot with all available data

            self.reflectance_plot.clear()

            # Plot available curves

            if not np.all(np.isnan(R_val)):
                self.target_r_curve = self.reflectance_plot.plot(
                    wls,
                    R_val,
                    pen=None,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=CertusTheme.CHART_PRIMARY,
                    name="Target R",
                )

            if not np.all(np.isnan(T_val)):
                self.target_t_curve = self.reflectance_plot.plot(
                    wls,
                    T_val,
                    pen=None,
                    symbol="t",
                    symbolSize=5,
                    symbolBrush=CertusTheme.CHART_SUCCESS,
                    name="Target T",
                )

            if not np.all(np.isnan(Rb_val)):
                self.target_rb_curve = self.reflectance_plot.plot(
                    wls,
                    Rb_val,
                    pen=None,
                    symbol="s",
                    symbolSize=5,
                    symbolBrush=CertusTheme.CHART_WARNING,
                    name="Target Rback",
                )

            # Recreate calc curves holders (always create all, just empty if no data)

            self.calc_r_curve = self.reflectance_plot.plot(
                [], [], pen=pg.mkPen(CertusTheme.CHART_PRIMARY, width=2), name="Calc R"
            )

            self.calc_t_curve = self.reflectance_plot.plot(
                [], [], pen=pg.mkPen(CertusTheme.CHART_SUCCESS, width=2), name="Calc T"
            )

            self.calc_rb_curve = self.reflectance_plot.plot(
                [],
                [],
                pen=pg.mkPen(CertusTheme.CHART_WARNING, width=2),
                name="Calc Rback",
            )

            self.reflectance_plot.addLegend()

            self.update_lambda_filters()

            self.reflectance_plot.autoRange()

        except FileNotFoundError:
            show_error(self, "file_not_found", path=filepath)

            self.target_data = None

        except PermissionError:
            show_error(self, "file_permission", path=filepath)

            self.target_data = None

        except pd.errors.EmptyDataError:
            show_error(self, "file_empty", path=filepath)

            self.target_data = None

        except ValueError as e:
            title, details, suggestion = get_error_message("file_format", path=filepath)

            QMessageBox.critical(self, title, f"{details}\n\nErreur: {str(e)}\n\n💡 {suggestion}")

            self.target_data = None

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            show_error(self, "generic_error", details=str(e))

            self.target_data = None

    def start_optimization(self) -> None:
        """Starts optimization"""

        # CLEANUP PREVIOUS THREAD

        if getattr(self, "optimization_thread", None) is not None:
            try:
                # Check if C++ object still exists and is running

                if self.optimization_thread.isRunning():
                    if getattr(self, "worker", None):
                        self.worker.stop()

                    self.optimization_thread.quit()

                    if not self.optimization_thread.wait(2000):
                        logging.critical(
                            "Optimization thread did not stop within 2s - skipping terminate() to avoid unsafe thread kill."
                        )

            except RuntimeError:
                # Thread object already deleted on C++ side

                pass

            self.optimization_thread = None

            self.worker = None

        if not self.target_data:
            show_error(self, "optim_no_data")

            return

        try:
            p = {k: v.text() for k, v in self.widgets.items() if isinstance(v, QLineEdit)}

            params = {k: float(v) for k, v in p.items() if k not in ["excel_filename"]}

            # CRITICAL: Enforce max 5 knots (User Constraint)

            raw_knots = int(p["num_knots"])

            if raw_knots > 5:
                self.logger.warning(f"Requested {raw_knots} knots. Clamping to 5 (System Limit).")

                raw_knots = 5

                self.widgets["num_knots"].setText("5")

            params["num_knots"] = raw_knots

            params["eM_min"] = float(p.get("eM_min", DEFAULT_EM_MIN))

            # substrate ID

            # 1=Silica, 2=BK7

            sub_id_map = {"Fused Silica": 1, "BK7": 2}

            sub_text = self.combo_substrate.currentText()

            params["substrate_id"] = sub_id_map.get(sub_text, 1)

            # SECURITY CHECK: Thickness Bounds

            # User constraint: Nominal thickness known to +/- 20%

            # We check if the provided range is too wide given this constraint.

            e_min = params["eM_min"]

            e_max = params["eM_max"]

            e_mean = (e_min + e_max) / 2.0

            e_range = e_max - e_min

            # If range > 50% of mean, it's likely too wide for single metal convergence

            # (Allows slightly more than +/- 20% but warns if excessive)

            if e_range > (0.5 * e_mean):
                ret = QMessageBox.warning(
                    self,
                    "Wide Thickness Range",
                    f"The thickness range ({e_min}-{e_max} nm) is very wide.\n"
                    f"Effective Range: {e_mean:.1f} +/- {e_range / 2:.1f} nm (+/-{e_range / 2 / e_mean * 100:.0f}%)\n\n"
                    "For reliable convergence, the nominal thickness should be known to +/-20%.\n"
                    "Do you want to proceed anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if ret == QMessageBox.StandardButton.No:
                    return

            params.update(
                {
                    "excel_filename": self.widgets["excel_filename"].text(),
                    "popsize": DEFAULT_POPSIZE,
                    "maxiter": DEFAULT_MAXITER,
                    "tol": DEFAULT_TOL,
                    "mutation_min": DEFAULT_MUTATION_MIN,
                    "mutation_max": DEFAULT_MUTATION_MAX,
                    "recombination": DEFAULT_RECOMBINATION,
                    "updating": DEFAULT_UPDATING,
                    "workers": DEFAULT_WORKERS,
                }
            )

            # Bounds: built after target_lambda is set

            mask = (self.target_data["lambda"] >= params["lmin_filter"]) & (
                self.target_data["lambda"] <= params["lmax_filter"]
            )

            target_lambda_filtered = self.target_data["lambda"][mask]

            # Pass all 3 targets

            params["target_lambda"] = target_lambda_filtered

            params["target_r"] = self.target_data["R"][mask]

            target_t_filtered = self.target_data["T"][mask]

            params["target_t"] = target_t_filtered

            params["target_rb"] = self.target_data["Rback"][mask]

            # SECURITY CHECK: Transmission

            # User Constraint: T > 1% everywhere, Mean T > 5%

            # If not met, optimization results would be garbage.

            if len(target_t_filtered) > 0:
                t_min = np.nanmin(target_t_filtered)

                t_mean = np.nanmean(target_t_filtered)

                # Check 1: Min > 1% (0.01)

                if t_min < 0.01:
                    QMessageBox.warning(
                        self,
                        "Transmission Low",
                        f"Safety Check Failed!\nMinimum Transmission is too low ({t_min * 100:.2f}% < 1%).\n\n"
                        "Optimization requires adequate transmission signal.",
                    )

                    return

                # Check 2: Mean > 5% (0.05)

                if t_mean < 0.05:
                    QMessageBox.warning(
                        self,
                        "Transmission Low",
                        f"Safety Check Failed!\nMean Transmission is too low ({t_mean * 100:.2f}% < 5%).\n\n"
                        "Optimization requires adequate transmission signal.",
                    )

                    return

            # Start logging

            self.logger.info("=" * 50)

            self.logger.info("STARTING METAL SINGLE OPTIMIZATION")

            self.logger.info(f"substrate: {sub_text}")

            self.logger.info(
                f"Target File: {Path(self._last_target_file).name if self._last_target_file else 'Unknown'}"
            )

            self.logger.info(f"Wavelength Range: {params['lmin_filter']} - {params['lmax_filter']} nm")

            self.logger.info(f"Metal Thickness Range: {params['eM_min']} - {params['eM_max']} nm")

            bounds = _build_single_bounds(params, l_array=params["target_lambda"], include_eM=True)

            params["bounds"] = bounds

        except (ValueError, KeyError) as e:
            QMessageBox.critical(self, "Parameter Error", f"Invalid value: {e}")

            return

        self.mse_data = {"iterations": [], "errors": []}

        self.mse_curve.setData([], [])

        for label in ["live_eM", "live_MSE"]:
            self.widgets[label].setText("...")

        self.btn_run.setEnabled(False)

        self.btn_stop.setEnabled(True)

        # Cache params for thread-safe access in callbacks

        self._last_worker_params = params.copy()

        self.optimization_thread = QThread()

        self.worker = OptimizationWorker(params)

        self.worker.moveToThread(self.optimization_thread)

        self.optimization_thread.started.connect(self.worker.run)

        self.worker.finished.connect(self.on_optimization_finished)

        self.worker.progress.connect(self.update_plots)

        self.worker.progress.connect(self._on_optim_progress)

        self.worker.error.connect(self.on_optimization_error)

        self.worker.stats_update.connect(self.on_stats_update)

        # Proper cleanup to avoid memory leaks

        self.worker.finished.connect(self.optimization_thread.quit)

        self.worker.error.connect(self.optimization_thread.quit)

        self.worker.finished.connect(self.worker.deleteLater)

        self.optimization_thread.finished.connect(self.optimization_thread.deleteLater)

        # Start progress widget timing

        self._optim_max_iter = params.get("maxiter", DEFAULT_MAXITER)

        self.progress_widget.start()

        self.optimization_thread.start()

        # Reset counters

        self.stat_counters = {"MS": 0, "MCS": 0, "SP": 0}

        self.update_stats_display()

    # stop_optimization is inherited from MetalBaseApp.

    def _on_optim_progress(self, data: dict) -> None:
        """Updates progress widget with optimization progress"""

        iteration = data.get("iteration", 0)

        mse = data.get("mse", 0)

        rmse = np.sqrt(mse) if mse > 0 else 0

        xk = data.get("params", None)

        eM = xk[0] if xk is not None else 0.0

        self.logger.info(f"Gen {iteration}: RMSE = {rmse:.6e} | dM = {eM:.2f} nm")

        self.widgets["live_eM"].setText(f"{eM:.2f}")

        self.widgets["live_MSE"].setText(f"{mse:.6e}")

        self.widgets["live_iter"].setText(str(iteration))

        self.progress_widget.update(
            iteration=iteration,
            max_iter=getattr(self, "_optim_max_iter", DEFAULT_MAXITER),
            evals=self.stat_counters.get("SP", 0),
            phase="DE",
            extra_info=f"RMSE: {rmse:.6f}" if rmse > 0 else "",
        )

    def on_optimization_finished(self, results) -> None:
        """Handles optimization finish."""

        self.progress_widget.stop("Optimization complete")

        # Cache iteration count before cleanup (thread-safe)

        worker = getattr(self, "worker", None)

        iteration_count = worker.iteration_count if worker else results.get("nit", 0)

        # Reset UI state (no confirmation needed - optimization completed normally)

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self.btn_beam.setEnabled(True)

        # Use cached params for plotting

        if self._last_worker_params is not None:
            self.update_plots(
                {
                    "params": results["result"].x,
                    "mse": results["result"].fun,
                    "iteration": iteration_count,
                },
                final=True,
            )

        self.final_results = results

        # Self-export (Excel + HTML) if enabled via HUB

        if get_export_config():
            QTimer.singleShot(500, self.export_results)

    def update_plots(self, data, final=False) -> None:
        """Updates plots with current optimization state (live during run, full on finish)."""

        # Thread-safe params access via cache

        p = self._last_worker_params

        if p is None:
            return

        xk = data.get("params")

        if xk is None:
            return

        eM = xk[0]

        self.widgets["live_eM"].setText(f"{eM:.2f}")

        # Convert MSE to RMSE for display

        rmse_val = np.sqrt(data["mse"]) if data.get("mse", 0) >= 0 else 0.0

        self.widgets["live_MSE"].setText(f"{rmse_val:.4e}")

        # Convert MSE to RMSE for plot

        if not hasattr(self, "mse_data"):
            self.mse_data = {"iterations": [], "errors": []}

        self.mse_data["iterations"].append(data.get("iteration", 0))

        self.mse_data["errors"].append(rmse_val)

        self.mse_curve.setData(self.mse_data["iterations"], self.mse_data["errors"])

        num_knots, offset = p["num_knots"], 1

        n_knots = xk[offset : offset + num_knots]

        k_knots = xk[offset + num_knots : offset + 2 * num_knots]

        lambda_internes = xk[offset + 2 * num_knots :]

        l_array = p["target_lambda"]

        min_l, max_l = l_array.min(), l_array.max()

        knot_l = np.concatenate(([min_l], np.sort(lambda_internes), [max_l]))

        p_spline_nk = np.concatenate((n_knots, k_knots))

        plot_lambda_range = np.linspace(min_l, max_l, 200)

        n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, plot_lambda_range)

        # Calculate R, T, Rback for Plotting

        # Need to reshape for vectorized call

        nM_complex = n_calc - 1j * k_calc

        nM_complex_2d = np.empty((len(plot_lambda_range), 1), dtype=np.complex128)

        nM_complex_2d[:, 0] = nM_complex

        nSub_real = get_n_substrate_array_by_id(p.get("substrate_id", 1), plot_lambda_range)

        nSub_complex = nSub_real + 0j

        R_calc, T_calc, Rb_calc = calculate_RTRback_incoherent_vectorized(
            np.array([eM], dtype=np.float64),
            nM_complex_2d,
            nSub_complex,
            plot_lambda_range,
        )

        pen_r = pg.mkPen(CertusTheme.PRIMARY, width=3 if final else 2)

        pen_t = pg.mkPen(CertusTheme.SUCCESS, width=3 if final else 2)

        pen_rb = pg.mkPen(CertusTheme.WARNING, width=3 if final else 2)

        self.calc_r_curve.setData(plot_lambda_range, R_calc, pen=pen_r)

        self.calc_t_curve.setData(plot_lambda_range, T_calc, pen=pen_t)

        self.calc_rb_curve.setData(plot_lambda_range, Rb_calc, pen=pen_rb)

        self.n_curve.setData(plot_lambda_range, n_calc)

        self.k_curve.setData(plot_lambda_range, k_calc)

        try:
            self.p2.setGeometry(self.p1.vb.sceneBoundingRect())

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            pass

        # Comme Metal Bilayer : zoom n/k en live (sinon ViewBox reste sur plage vide -> courbes invisibles).

        if not final and int(data.get("iteration", 0)) % 3 == 0:
            self.p1.vb.autoRange()

            self.p2.autoRange()

        if final:
            self.p1.vb.autoRange()

            self.p2.autoRange()

            try:
                src_name = ""

                if hasattr(self, "_last_target_file") and self._last_target_file:
                    src_name = " - " + Path(self._last_target_file).stem

                self.reflectance_plot.plotItem.setTitle(
                    f"Reflectance Comparison{src_name}", color=CertusTheme.CHART_PRIMARY, size="12pt"
                )

                self.clues_plot.plotItem.setTitle(
                    f"Optimized Metal Optical Constants (n, k){src_name}", color=CertusTheme.CHART_PRIMARY, size="12pt"
                )

            except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
                pass

            # --- SYSTEMATIC EXPORT ---

            QTimer.singleShot(500, self.export_results)

    def _get_config_dict(self) -> dict:
        """Returns JSON struct for config"""

        return {
            "version": "1.0.0",
            "excel_filename": self.widgets["excel_filename"].text(),
            "physical_params": {
                "eM_min": self.widgets["eM_min"].text(),
                "eM_max": self.widgets["eM_max"].text(),
            },
            "material_params": {
                "num_knots": self.widgets["num_knots"].text(),
                "nk_min": self.widgets["nk_min"].text(),
                "nk_max": self.widgets["nk_max"].text(),
                "min_knot_dist": self.widgets["min_knot_dist"].text(),
            },
            "filters": {
                "lmin_filter": self.widgets["lmin_filter"].text(),
                "lmax_filter": self.widgets["lmax_filter"].text(),
            },
            "optimization": {
                "popsize": DEFAULT_POPSIZE,
                "maxiter": DEFAULT_MAXITER,
                "tol": DEFAULT_TOL,
                "mutation_min": DEFAULT_MUTATION_MIN,
                "mutation_max": DEFAULT_MUTATION_MAX,
                "recombination": DEFAULT_RECOMBINATION,
                "updating": DEFAULT_UPDATING,
                "workers": DEFAULT_WORKERS,
            },
        }

    def export_results(self) -> None:
        """Exports results to Excel + HTML (Single/Beam)"""

        if hasattr(self, "beam_stats") and self.beam_stats is not None:
            self._export_beam_results()

            return

        if not hasattr(self, "final_results"):
            QMessageBox.warning(self, "No Results", "Please run optimization first.")

            return

        res = self.final_results["result"]

        xk = res.x

        mse = res.fun

        # Prepare data

        reports_dir = get_resource_path("reports")

        os.makedirs(reports_dir, exist_ok=True)

        # Self-export check logic handled by caller usually or here

        if not get_export_config():
            return

        try:
            from certus_data import ReportSection

            ts = certus_timestamp_file()

            rmse_val = np.sqrt(mse) if mse > 0 else 0

            src_name = ""

            if hasattr(self, "_last_target_file") and self._last_target_file:
                src_name = "_" + Path(self._last_target_file).stem

            base_name = f"Report_SINGLE{src_name}_{ts}_RMSE_{rmse_val:.5f}"

            excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")

            html_path = str(Path(reports_dir) / f"{base_name}.html")

            sol_rows = [
                {"Parameter": "eM (Thickness)", "Value": xk[0], "Unit": "nm"},
            ]

            df_sol = pd.DataFrame(sol_rows)

            p = self._last_worker_params

            l_array = p["target_lambda"]

            target_r = p["target_r"]

            num_knots = p["num_knots"]

            offset = 1

            n_knots = xk[offset : offset + num_knots]

            k_knots = xk[offset + num_knots : offset + 2 * num_knots]

            lambda_internes = xk[offset + 2 * num_knots :]

            min_l, max_l = l_array.min(), l_array.max()

            knot_l = np.concatenate(([min_l], np.sort(lambda_internes), [max_l]))

            p_spline = np.concatenate((n_knots, k_knots))

            n_calc, k_calc = get_nk_from_spline(p_spline, knot_l, l_array)

            df_spectra = pd.DataFrame(
                {
                    "Wavelength (nm)": l_array,
                    "R Target": target_r,
                    "n (Metal)": n_calc,
                    "k (Metal)": k_calc,
                }
            )

            sections = [
                ReportSection(
                    title="Optimization Summary",
                    kind="kv",
                    content={
                        "Date": certus_timestamp_display(),
                        "Final RMSE": f"{rmse_val:.6f}",
                        "Final MSE": f"{mse:.6e}",
                        "Max Iterations": str(
                            self._last_worker_params.get("maxiter", "N/A") if self._last_worker_params else "N/A"
                        ),
                        "Thickness": f"{xk[0]:.2f} nm",
                    },
                    sheet_name="Summary",
                ),
                ReportSection(title="Solution Parameters", kind="table", content=df_sol, sheet_name="Solution"),
                ReportSection(title="Spectra", kind="table", content=df_spectra, sheet_name="Spectra"),
                ReportSection(
                    title="Reflectance Plot",
                    kind="image",
                    content=self.widget_to_b64(self.reflectance_plot),
                    include_in_excel=False,
                ),
                ReportSection(
                    title="n & k Clues Plot",
                    kind="image",
                    content=self.widget_to_b64(self.clues_plot),
                    include_in_excel=False,
                ),
                ReportSection(
                    title="Convergence Plot",
                    kind="image",
                    content=self.widget_to_b64(self.mse_plot),
                    include_in_excel=False,
                ),
            ]

            res = self.export_via_builder(
                sections,
                excel_path=excel_path,
                html_path=html_path,
                html_title="CERTUS-SINGLE Optimization Report",
            )

            if res.get("excel") or res.get("html"):
                self.status_label.setText(f"Reports saved: {base_name}")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"Error exporting: {e}")

            traceback.print_exc()

    def start_beam_analysis(self) -> None:
        """Starts beam analysis: metal thickness scan"""

        if not self.target_data:
            QMessageBox.warning(self, "Error", "Load target file first.")

            return

        # Verify optimization done

        if not hasattr(self, "final_results") or self.final_results is None:
            QMessageBox.warning(
                self,
                "Optimization Required",
                "Run standard optimization (START) first\nto get reference solution.",
            )

            return

        try:
            p = {k: v.text() for k, v in self.widgets.items() if isinstance(v, QLineEdit)}

            params = {k: float(v) for k, v in p.items() if k not in ["excel_filename"]}

            params["num_knots"] = int(p["num_knots"])

            # substrate ID

            sub_id_map = {"Fused Silica": 1, "BK7": 2}

            sub_text = self.combo_substrate.currentText()

            params["substrate_id"] = sub_id_map.get(sub_text, 1)

            params["eM_min"] = float(p.get("eM_min", DEFAULT_EM_MIN))

            params["eM_max"] = float(p.get("eM_max", DEFAULT_EM_MAX))

            params["nk_min"] = float(p.get("nk_min", DEFAULT_NK_MIN))

            params["nk_max"] = float(p.get("nk_max", DEFAULT_NK_MAX))

            mask = (self.target_data["lambda"] >= params["lmin_filter"]) & (
                self.target_data["lambda"] <= params["lmax_filter"]
            )

            params["target_lambda"] = self.target_data["lambda"][mask]

            params["target_r"] = self.target_data["R"][mask]

            # Add min_knot_dist if missing

            if "min_knot_dist" not in params:
                params["min_knot_dist"] = float(self.widgets["min_knot_dist"].text())

            # Get optimal solution found

            optimal_solution = self.final_results["result"].x.copy()

            optimal_mse = float(self.final_results["result"].fun)

        except (ValueError, KeyError) as e:
            QMessageBox.critical(self, "Parameter Error", f"Invalid value: {e}")

            return

        self.btn_run.setEnabled(False)

        self.btn_beam.setEnabled(False)

        self.btn_stop.setEnabled(True)

        self.status_label.setText("Scanning metal thickness...")

        # Scan step 0.5 nm, MSE tolerance +/- 20%

        worker = BeamAnalysisWorker(params, optimal_solution, optimal_mse, step_nm=0.5, mse_tolerance=0.2)

        setup_beam_analysis_thread(self, worker).start()

    def on_beam_finished(self, stats):
        """Handles beam analysis finish"""

        teardown_beam_thread(self, stats)

        # --- Beam Graphic Display ---

        # Clear items but keep axes

        self.p1.clear()

        self.p2.clear()

        # Re-add basics

        self.p1.addItem(self.n_curve)

        self.p2.addItem(self.k_curve)

        x = stats["lambda_axis"]

        # Global N zone (Blue - Total math uncertainty)

        n_mean = stats["n_mean"]

        n_std = stats["n_std"]

        n_upper = n_mean + 2 * n_std

        n_lower = n_mean - 2 * n_std

        # Global n uncertainty fill

        curve_n_upper = pg.PlotDataItem(
            x,
            n_upper,
            pen=pg.mkPen(CertusTheme.PRIMARY, width=1, style=Qt.PenStyle.DotLine),
        )

        curve_n_lower = pg.PlotDataItem(
            x,
            n_lower,
            pen=pg.mkPen(CertusTheme.PRIMARY, width=1, style=Qt.PenStyle.DotLine),
        )

        fill_n = pg.FillBetweenItem(
            curve_n_lower,
            curve_n_upper,
            brush=pg.mkBrush(*CertusTheme.hex_to_rgba_tuple(CertusTheme.PRIMARY, 25)),
        )

        self.p1.addItem(fill_n)

        self.p1.addItem(curve_n_upper)

        self.p1.addItem(curve_n_lower)

        # Global n mean curve (blue, thick)

        self.n_curve.setData(x, n_mean)

        # Global K zone (Red - Total math uncertainty)

        k_mean = stats["k_mean"]

        k_std = stats["k_std"]

        k_upper = k_mean + 2 * k_std

        k_lower = k_mean - 2 * k_std

        # Global k uncertainty fill

        curve_k_upper = pg.PlotDataItem(
            x,
            k_upper,
            pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DotLine),
        )

        curve_k_lower = pg.PlotDataItem(
            x,
            k_lower,
            pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DotLine),
        )

        fill_k = pg.FillBetweenItem(
            curve_k_lower,
            curve_k_upper,
            brush=pg.mkBrush(*CertusTheme.hex_to_rgba_tuple(CertusTheme.DANGER, 25)),
        )

        self.p2.addItem(fill_k)

        self.p2.addItem(curve_k_upper)

        self.p2.addItem(curve_k_lower)

        # Global k mean curve

        self.k_curve.setData(x, k_mean)

        # Show individual curves to visualize beam

        if "all_solutions" in stats and len(stats["all_solutions"]) > 0:
            for _, sol in enumerate(stats["all_solutions"]):
                if "n" in sol and "k" in sol:
                    pen_n_indiv = pg.mkPen(CertusTheme.hex_to_rgba_tuple(CertusTheme.PRIMARY, 50), width=1)

                    n_item = pg.PlotDataItem(stats["lambda_axis"], sol["n"], pen=pen_n_indiv)

                    self.p1.addItem(n_item)

                    pen_k_indiv = pg.mkPen(CertusTheme.hex_to_rgba_tuple(CertusTheme.DANGER, 50), width=1)

                    k_item = pg.PlotDataItem(stats["lambda_axis"], sol["k"], pen=pen_k_indiv)

                    self.p2.addItem(k_item)

        # Auto-select "n & k" tab

        self.tabs.setCurrentIndex(1)

        count = stats["count"]

        rmse_best = np.sqrt(stats["best_mse"]) if stats["best_mse"] >= 0 else 0.0

        self.status_label.setText(f"Beam: {count} solutions | eM: {stats['eM_min']:.1f}-{stats['eM_max']:.1f} nm")

        QMessageBox.information(
            self,
            "Beam Analysis Results",
            f"Beam Analysis by Thickness Scan\n"
            f"{count} solutions kept\n"
            f"Best RMSE found: {rmse_best:.2e}\n\n"
            f"Thickness eM: {stats['eM_mean']:.2f} +/- {2 * stats['eM_std']:.2f} nm\n"
            f"See 'n & k' tab to visualize results.",
        )

        # Self-export

        if get_export_config():
            QTimer.singleShot(500, self.export_results)

    def _export_beam_results(self):
        """Exports beam analysis results"""

        if not hasattr(self, "beam_stats") or self.beam_stats is None:
            return

        stats = self.beam_stats

        reports_dir = get_resource_path("reports")

        os.makedirs(reports_dir, exist_ok=True)

        ts = certus_timestamp_file()

        try:
            src_name = ""

            if hasattr(self, "_last_target_file") and self._last_target_file:
                src_name = "_" + Path(self._last_target_file).stem

            base_name = f"Beam_SINGLE{src_name}_{ts}"

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError):
            base_name = f"Beam_SINGLE_{ts}"

        excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")

        try:
            df_summary = pd.DataFrame(
                {
                    "Parameter": [
                        "eM_mean",
                        "eM_std",
                        "eM_min",
                        "eM_max",
                        "RMSE_best",
                        "Count",
                    ],
                    "Value": [
                        f"{stats['eM_mean']:.3f}",
                        f"{stats['eM_std']:.3f}",
                        f"{stats['eM_min']:.3f}",
                        f"{stats['eM_max']:.3f}",
                        f"{np.sqrt(stats['best_mse']):.6f}",
                        f"{stats['count']}",
                    ],
                }
            )

            df_spectra = pd.DataFrame(
                {
                    "lambda_nm": stats["lambda_axis"],
                    "n_mean": stats["n_mean"],
                    "n_std": stats["n_std"],
                    "k_mean": stats["k_mean"],
                    "k_std": stats["k_std"],
                }
            )

            sol_data = []

            for idx, s in enumerate(stats["all_solutions"]):
                sol_data.append({"ID": idx + 1, "RMSE": np.sqrt(s["mse"]), "eM": s["eM"]})

            df_sols = pd.DataFrame(sol_data)

            if OPENPYXL_AVAILABLE:
                with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                    df_summary.to_excel(writer, sheet_name="Beam Summary", index=False)

                    df_spectra.to_excel(writer, sheet_name="Reference Indices", index=False)

                    df_sols.to_excel(writer, sheet_name="Solutions", index=False)

                self.logger.info(f"Beam report saved: {base_name}")

                self.status_label.setText(f"Beam Export:{base_name}")

            else:
                to_excel_robust(df_summary, excel_path)

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"Beam export error:{e}")

    def _apply_config_dict(self, config):
        """Loads JSON struct for config"""

        phys = config.get("physical_params", {})

        self.widgets["eM_min"].setText(str(phys.get("eM_min", DEFAULT_EM_MIN)))

        self.widgets["eM_max"].setText(str(phys.get("eM_max", DEFAULT_EM_MAX)))

        mat = config.get("material_params", {})

        self.widgets["num_knots"].setText(str(mat.get("num_knots", DEFAULT_NUM_KNOTS)))

        self.widgets["nk_min"].setText(str(mat.get("nk_min", DEFAULT_NK_MIN)))

        self.widgets["nk_max"].setText(str(mat.get("nk_max", DEFAULT_NK_MAX)))

        self.widgets["min_knot_dist"].setText(str(mat.get("min_knot_dist", DEFAULT_MIN_KNOT_DISTANCE)))

        # Load filters

        flt = config.get("filters", {})

        self.widgets["lmin_filter"].setText(str(flt.get("lmin_filter", "")))

        self.widgets["lmax_filter"].setText(str(flt.get("lmax_filter", "")))

        # Load excel filename

        if "excel_filename" in config:
            self.widgets["excel_filename"].setText(config["excel_filename"])

        # Load target file if specified

        if "target_file" in config and config["target_file"]:
            target_file = config["target_file"]

            if Path(target_file).exists():
                self._last_target_file = target_file

                # Trigger file load

                try:
                    df = read_data_file_robust(target_file)

                    if len(df.columns) >= 2:
                        data = df.iloc[:, [0, 1]].apply(pd.to_numeric, errors="coerce").dropna().to_numpy()

                        if len(data) > 0:
                            data = data[data[:, 0].argsort()]

                            if data[:, 1].max() > 1.0:
                                target_data = {
                                    "lambda": data[:, 0],
                                    "R": data[:, 1] / 100.0,
                                }

                            else:
                                target_data = {"lambda": data[:, 0], "R": data[:, 1]}

                            self.target_data = target_data

                            self.lbl_file.setText(Path(target_file).name)

                            self.target_curve.setData(self.target_data["lambda"], self.target_data["R"])

                            self.update_lambda_filters()

                            self.reflectance_plot.autoRange()

                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ) as e:
                    self.logger.warning(f"Could not load target file: {e}")


# =============================================================================


# MAIN WINDOW


# =============================================================================


if __name__ == "__main__":
    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    init_certus_app("CERTUS-METAL", app=app)

    # --- SPLASH SCREEN ---

    from certus_splash import create_splash

    splash = create_splash("Initializing Metal Engine (Single Layer)...")

    # Setup logging with centralized helper

    setup_logging(log_file="certus_metal.log")

    window = CertusMetalSingleApp()

    window.show()

    splash.finish(window)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: window.load_config(f))

    sys.exit(app.exec())
