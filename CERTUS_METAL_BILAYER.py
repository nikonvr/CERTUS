#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""
CERTUS-METAL-BILAYER CERTUS_SUITE_26_05
================================
Metal Index Determination on SiO2/Si substrate (Bilayer Strategy)

Determines the complex refractive index (n, k) of a metal layer deposited
on top of a SiO2 layer, itself on top of an absorbing Si substrate.

Structure: Air | Metal (eM) | SiO2 (eL) | Si (absorbing substrate)

Uses PGLOBAL optimization to extract metal optical constants
from reflectance measurements. The metal index is modeld as wavelength-dependent
splines, while SiO2 uses a Cauchy model (n = n∞ + A/lambda²).
"""


import json
import logging
import multiprocessing
import os
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


import numpy as np
import pandas as pd
import scipy.optimize
import pyqtgraph as pg


from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
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
    __version__,
    create_module_environment,
    setup_logging,
    get_float_dtype,
    get_resource_path,
    certus_timestamp_display,
    certus_timestamp_file,
    NUMERICAL_FAULT_EXCEPTIONS,
)


from certus.utils.certus_data import OPENPYXL_AVAILABLE


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
    MetalBaseApp,
    MetalOptimizationWorker,
    build_metal_progress_event,
    build_metal_progress_status_text,
    build_metal_startup_log_lines,
    build_metal_target_data,
    normalize_percent_column,
    normalize_metal_progress_payload,
    setup_beam_analysis_thread,
    teardown_beam_thread,
    setup_common_metal_plots,
)


from certus.metal.pglobal_adapter import run_pglobal_optimization


from certus_physics import (
    calculate_reflectance_bilayer_vectorized,
    compute_metal_bilayer_gradient_analytic,
    get_nk_cauchy_simple,
    get_nk_from_spline,
    get_nk_si,
)


from certus.ui.certus_ui import (
    CertusCard,
    CertusScientificPlot,
    CertusTheme,
    FlashyCard,
    create_info_icon,
    get_export_config,
    init_certus_app,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
    show_toast,
)


warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy.optimize")


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


env = create_module_environment(__file__, "METAL_BILAYER")


script_dir = env["script_dir"]


setup_gui_exception_handling()


setup_pyqtgraph_defaults()


# =============================================================================


# CONSTANTS


# =============================================================================


DEFAULT_EL_NOMINAL = "900"


DEFAULT_EL_VARIATION = "20"


# Silicon optical constants: loaded from clues.xlsx -> Si-substrate via certus_physics.get_nk_si()


def _build_bilayer_bounds(
    params: Dict[str, Any], l_array: Optional[np.ndarray] = None, include_eM: bool = True
) -> List[Tuple[float, float]]:
    """Build bounds list for bilayer optimization. If include_eM=False, omit first (eM) bound."""

    eL_min = max(0, params.get("eL_nominal", 900) - params.get("eL_variation", 20))

    eL_max = params.get("eL_nominal", 900) + params.get("eL_variation", 20)

    bounds = []

    if include_eM:
        bounds.append((params["eM_min"], params["eM_max"]))

    bounds.append((eL_min, eL_max))

    bounds.append(params.get("n_infini_bounds", (1.42, 1.44)))

    bounds.append(params.get("A_diel_bounds", (0, 10000)))

    num_knots = params["num_knots"]
    spline_knots = num_knots

    bounds += [(params.get("nk_min", 0), params.get("nk_max", 10))] * (2 * spline_knots)

    num_internal = spline_knots - 2

    if num_internal > 0:
        if l_array is not None:
            l_min, l_max = float(np.min(l_array)), float(np.max(l_array))
        else:
            # Keep the search space aligned with the objective even when no target grid
            # is available yet (e.g. headless smoke tests or early setup paths).
            l_min, l_max = 350.0, 880.0

        bounds += [(l_min, l_max)] * num_internal

    return bounds


# =============================================================================


# NUMBA FUNCTIONS (Precision-aware)


# =============================================================================


# =============================================================================


# OPTIMIZATION OBJECTIVE FUNCTION


# =============================================================================


# Note: get_nk_from_spline imported from certus_physics above



def _bilayer_reflectance_mse(
    x: np.ndarray,
    l_array: np.ndarray,
    r_tgt_array: np.ndarray,
    num_knots: int,
    min_knot_dist: float,
    nSub_complex_array: Optional[np.ndarray],
    eM_fixed: Optional[float] = None,
) -> float:
    """Compute bilayer reflectance MSE or return np.inf when constraints fail."""

    min_lambda = float(np.min(l_array))
    max_lambda = float(np.max(l_array))
    if not np.isfinite(min_lambda) or not np.isfinite(max_lambda) or max_lambda <= min_lambda:
        return np.inf
    if nSub_complex_array is None:
        nSub_complex_array = get_nk_si(l_array)

    x = np.asarray(x, dtype=float)
    debug_ctx: dict[str, Any] = {
        "x_dim": int(x.size),
        "x_head": np.round(x[: min(10, x.size)], 6).tolist() if x.size else [],
        "num_knots": int(num_knots),
        "min_knot_dist": float(min_knot_dist),
        "lambda_min": float(min_lambda),
        "lambda_max": float(max_lambda),
        "eM_fixed": None if eM_fixed is None else float(eM_fixed),
    }
    if eM_fixed is None:
        if x.size < 4:
            _write_bilayer_autopsy_record("objective_shape_reject", {"reason": "x_too_short_global", "context": debug_ctx})
            return np.inf
        eM, eL, n_infini, A = x[0], x[1], x[2], x[3]
        offset = 4
    else:
        eM = float(eM_fixed)
        if x.size < 3:
            _write_bilayer_autopsy_record("objective_shape_reject", {"reason": "x_too_short_fixed_eM", "context": debug_ctx})
            return np.inf
        eL, n_infini, A = x[0], x[1], x[2]
        offset = 3

    spline_knot_count = num_knots
    expected_internal = max(0, spline_knot_count - 2)
    expected_size = offset + 2 * spline_knot_count + expected_internal
    # The global parametrization uses (num_knots + 1) control points per spline family.
    debug_ctx["spline_knot_count"] = int(spline_knot_count)
    debug_ctx["expected_internal"] = int(expected_internal)
    debug_ctx["expected_size"] = int(expected_size)
    if x.size != expected_size:
        _write_bilayer_autopsy_record("objective_shape_reject", {"reason": "unexpected_x_size", "context": debug_ctx})
        return np.inf

    n_knots = x[offset : offset + spline_knot_count]
    k_knots = x[offset + spline_knot_count : offset + 2 * spline_knot_count]
    lambda_internes = x[offset + 2 * spline_knot_count :]

    debug_ctx["lambda_internal_dim"] = int(lambda_internes.size)
    debug_ctx["n_knots_head"] = np.round(n_knots[: min(5, n_knots.size)], 6).tolist() if n_knots.size else []
    debug_ctx["k_knots_head"] = np.round(k_knots[: min(5, k_knots.size)], 6).tolist() if k_knots.size else []
    debug_ctx["lambda_internal_head"] = np.round(lambda_internes[: min(5, lambda_internes.size)], 6).tolist() if lambda_internes.size else []

    if n_knots.size != spline_knot_count or k_knots.size != spline_knot_count or lambda_internes.size != expected_internal:
        _write_bilayer_autopsy_record("objective_shape_reject", {"reason": "component_size_mismatch", "context": debug_ctx})
        return np.inf
    if eM < 0 or eL < 0:
        return np.inf

    nL_calc = get_nk_cauchy_simple(l_array, n_infini, A)
    if np.any(~np.isfinite(nL_calc)):
        _write_bilayer_autopsy_record("objective_physical_reject", {"reason": "non_finite_dielectric", "context": debug_ctx})
        return np.inf

    lambda_internes = np.sort(lambda_internes)
    knot_l = np.empty(spline_knot_count, dtype=np.float64)
    knot_l[0] = min_lambda
    if expected_internal > 0:
        knot_l[1:-1] = lambda_internes
    knot_l[-1] = max_lambda
    
    if not np.all(np.isfinite(knot_l)):
        _write_bilayer_autopsy_record("objective_shape_reject", {"reason": "non_finite_knots", "context": debug_ctx})
        return np.inf

    for i in range(spline_knot_count - 1):
        if knot_l[i+1] - knot_l[i] < float(min_knot_dist):
            return np.inf

    p_spline_nk = np.empty(2 * spline_knot_count, dtype=np.float64)
    p_spline_nk[:spline_knot_count] = n_knots
    p_spline_nk[spline_knot_count:] = k_knots

    try:
        n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=False)
        debug_ctx["n_calc_head"] = np.round(n_calc[: min(10, n_calc.size)], 6).tolist() if n_calc.size else []
        debug_ctx["k_calc_head"] = np.round(k_calc[: min(10, k_calc.size)], 6).tolist() if k_calc.size else []
        if n_calc.shape != l_array.shape or k_calc.shape != l_array.shape:
            _write_bilayer_autopsy_record("objective_kernel_reject", {"reason": "spline_shape_mismatch", "context": debug_ctx})
            return np.inf
        if not (np.all(np.isfinite(n_calc)) and np.all(np.isfinite(k_calc))):
            _write_bilayer_autopsy_record("objective_kernel_reject", {"reason": "non_finite_spline_output", "context": debug_ctx})
            return np.inf
        R_calc = calculate_reflectance_bilayer_vectorized(
            l_array,
            n_calc - 1j * k_calc,
            float(eM),
            float(eL),
            nL_calc + 0j,
            nSub_complex_array,
        )
        debug_ctx["R_calc_head"] = np.round(R_calc[: min(10, R_calc.size)], 6).tolist() if R_calc.size else []
        if R_calc.shape != r_tgt_array.shape or not np.all(np.isfinite(R_calc)):
            _write_bilayer_autopsy_record("objective_kernel_reject", {"reason": "non_finite_reflectance", "context": debug_ctx})
            return np.inf
        mse = float(np.mean((R_calc - r_tgt_array) ** 2))
        if not np.isfinite(mse):
            _write_bilayer_autopsy_record("objective_kernel_reject", {"reason": "non_finite_mse", "context": debug_ctx})
            return np.inf
        return mse
    except Exception as exc:
        debug_ctx["exception_type"] = type(exc).__name__
        debug_ctx["exception"] = str(exc)
        _write_bilayer_autopsy_record(
            "objective_kernel_exception",
            {
                "reason": f"objective_kernel_exception:{type(exc).__name__}:{exc}",
                "context": debug_ctx,
                "x": x.tolist(),
                "num_knots": int(num_knots),
                "min_knot_dist": float(min_knot_dist),
                "knot_l": knot_l.tolist(),
            },
        )
        return np.inf



def _bilayer_autopsy_dir() -> Path:
    """Directory used to persist autopsy payloads."""

    path = Path(get_resource_path("reports")) / "autopsy"
    path.mkdir(parents=True, exist_ok=True)
    return path



def _write_bilayer_autopsy_record(kind: str, payload: dict[str, Any]) -> Path | None:
    """Persist a compact JSON payload for post-mortem analysis."""
    return None



def _diagnostic_bilayer_penalty(reason: str, x: np.ndarray | None = None, *, logger: logging.Logger | None = None, context: dict[str, Any] | None = None) -> float:
    """Return the canonical penalty while emitting a high-signal diagnostic line."""

    penalty = 1e12
    try:
        x_arr = np.asarray(x, dtype=float) if x is not None else np.asarray([])
    except Exception:
        x_arr = np.asarray([])
    x_head = np.round(x_arr[: min(10, x_arr.size)], 6).tolist() if x_arr.size else []
    payload = {
        "reason": reason,
        "penalty": penalty,
        "x_dim": int(x_arr.size),
        "x_head": x_head,
        "context": context or {},
    }
    msg = f"BILAYER_DIAGNOSTIC penalty={penalty:.3e} reason={reason} x_dim={x_arr.size} x_head={x_head}"
    if logger is not None:
        pass # logger.debug(msg)
    else:
        pass # logging.getLogger("CertusMetal").debug(msg)
    _write_bilayer_autopsy_record("penalty", payload)
    return penalty



def _validate_bilayer_objective_inputs(
    x: np.ndarray,
    num_knots: int,
    l_array: np.ndarray,
    r_tgt_array: np.ndarray,
    min_knot_dist: float,
    eM_fixed: Optional[float] = None,
) -> dict[str, Any]:
    """Fail fast with explicit errors before calling the heavy physics kernel.

    Returns a compact diagnostic context used by the autopsy logger.
    """

    context: dict[str, Any] = {}
    x = np.asarray(x, dtype=float)
    context["x_dim"] = int(x.size)
    context["x_head"] = np.round(x[: min(10, x.size)], 6).tolist() if x.size else []
    context["num_knots"] = int(num_knots)
    if x.ndim != 1:
        raise ValueError(f"x must be 1D, got shape={x.shape}")
    if not np.all(np.isfinite(x)):
        bad_idx = np.where(~np.isfinite(x))[0].tolist()
        context["non_finite_indices"] = bad_idx
        raise ValueError(f"Non-finite optimization variables at indices={bad_idx}")
    if int(num_knots) < 2:
        raise ValueError(f"num_knots must be >= 2, got {num_knots}")
    l_array = np.asarray(l_array, dtype=float)
    r_tgt_array = np.asarray(r_tgt_array, dtype=float)
    context["lambda_dim"] = int(l_array.size)
    context["target_dim"] = int(r_tgt_array.size)
    if l_array.ndim != 1 or r_tgt_array.ndim != 1:
        raise ValueError(f"l_array and r_tgt_array must be 1D, got {l_array.shape=} {r_tgt_array.shape=}")
    if l_array.size == 0 or r_tgt_array.size == 0:
        raise ValueError("Empty target arrays")
    if l_array.size != r_tgt_array.size:
        raise ValueError(f"Target arrays size mismatch: lambda={l_array.size} R={r_tgt_array.size}")
    if not np.all(np.isfinite(l_array)) or not np.all(np.isfinite(r_tgt_array)):
        raise ValueError("Target arrays contain non-finite values")
    if not np.isfinite(min_knot_dist) or float(min_knot_dist) < 0:
        raise ValueError(f"Invalid min_knot_dist={min_knot_dist}")
    context["min_knot_dist"] = float(min_knot_dist)
    if eM_fixed is not None and not np.isfinite(eM_fixed):
        raise ValueError(f"Invalid fixed eM={eM_fixed}")
    if eM_fixed is not None:
        context["eM_fixed"] = float(eM_fixed)
    return context



def global_objective_function(
    x: np.ndarray,
    num_knots: int,
    l_array: np.ndarray,
    r_tgt_array: np.ndarray,
    min_knot_dist: float,
    nSub_complex_array: Optional[np.ndarray] = None,
) -> float:
    """

    PGLOBAL objective function.

    nSub_complex_array can be pre-computed and passed for performance.

    """

    diag_logger = logging.getLogger("CertusMetal")
    context: dict[str, Any] = {}
    try:
        context = _validate_bilayer_objective_inputs(x, num_knots, l_array, r_tgt_array, min_knot_dist, eM_fixed=None)
        val = _bilayer_reflectance_mse(
            x, l_array, r_tgt_array, num_knots, min_knot_dist, nSub_complex_array, eM_fixed=None
        )
    except Exception as exc:
        context["exception_type"] = type(exc).__name__
        context["exception"] = str(exc)
        _write_bilayer_autopsy_record(
            "global_objective_exception",
            {
                "reason": f"global_objective_failed:{type(exc).__name__}:{exc}",
                "context": context,
                "x": np.asarray(x, dtype=float).tolist() if np.asarray(x).size else [],
                "lambda_min": float(np.min(l_array)) if np.asarray(l_array).size else None,
                "lambda_max": float(np.max(l_array)) if np.asarray(l_array).size else None,
                "target_min": float(np.min(r_tgt_array)) if np.asarray(r_tgt_array).size else None,
                "target_max": float(np.max(r_tgt_array)) if np.asarray(r_tgt_array).size else None,
            },
        )
        return _diagnostic_bilayer_penalty(f"global_objective_failed:{type(exc).__name__}:{exc}", x, logger=diag_logger, context=context)
    if not np.isfinite(val):
        context["objective_value"] = float(val)
        _write_bilayer_autopsy_record(
            "global_objective_non_finite",
            {
                "reason": f"global_objective_non_finite:{val}",
                "context": context,
                "x": np.asarray(x, dtype=float).tolist() if np.asarray(x).size else [],
            },
        )
        return _diagnostic_bilayer_penalty(f"global_objective_non_finite:{val}", x, logger=diag_logger, context=context)
    return float(val)


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

        args_for_objective = (
            p["num_knots"],
            target_lambda,
            target_r,
            p["min_knot_dist"],
            nSub_precomputed,
        )

        bounds = np.array(_build_bilayer_bounds(p, l_array=target_lambda, include_eM=True), dtype=float_dtype)

        from certus.core._certus_physics_impl import PGlobalConfig
        cfg = PGlobalConfig.for_dimension(dim=len(bounds)).with_overrides(
            alpha=0.025313098184047346,
            reduction_ratio=0.28656406706115006,
            n_samples_per_iter=6195,
            local_search_budget=68183,
            max_active_clusters=5,
        )

        result = run_pglobal_optimization(
            lambda x: global_objective_function(x, *args_for_objective),
            bounds,
            x0=np.asarray(p.get("x0", np.asarray([], dtype=float_dtype)), dtype=float_dtype) if p.get("x0") is not None else None,
            max_iter=int(p.get("maxiter", DEFAULT_MAXITER)),
            max_feval=int(p.get("maxfeval", 5000)),
            workers=int(p.get("workers", 1)),
            stop_event=self._stop_event,
            callback=lambda payload: self.progress.emit(payload),
            config=cfg,
        )
        self.finished.emit({"result": result, "params": p})


def _validate_bilayer_spline_state(
    n_knots: np.ndarray,
    k_knots: np.ndarray,
    lambda_internes: np.ndarray,
    min_l: float,
    max_l: float,
    expected_knot_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a strictly increasing knot vector compatible with spline coefficients."""

    if expected_knot_count < 2:
        raise ValueError("expected_knot_count must be >= 2")
    if not np.isfinite(min_l) or not np.isfinite(max_l) or max_l <= min_l:
        raise ValueError("Invalid wavelength interval for spline knots")

    coeff_count = int(np.asarray(n_knots).size + np.asarray(k_knots).size)
    if coeff_count != 2 * expected_knot_count:
        raise ValueError(
            f"Invalid spline coefficient state: coeff_size={coeff_count} expected={2 * expected_knot_count} knot_size={expected_knot_count}"
        )

    lambda_internes = np.asarray(lambda_internes, dtype=float)
    lambda_internes = lambda_internes[np.isfinite(lambda_internes)]
    lambda_internes = np.unique(np.sort(lambda_internes))
    target_internal = expected_knot_count - 2
    if lambda_internes.size != target_internal:
        lambda_internes = np.linspace(min_l, max_l, expected_knot_count + 1)[1:-1]
    knot_l = np.concatenate(([min_l], lambda_internes, [max_l]))
    knot_l = np.unique(np.sort(knot_l))
    if knot_l.size != expected_knot_count or not np.all(np.diff(knot_l) > 0):
        knot_l = np.linspace(min_l, max_l, expected_knot_count)
    if knot_l.size != expected_knot_count or not np.all(np.diff(knot_l) > 0):
        raise ValueError("Invalid spline knot sequence: knots must be strictly increasing")
    return knot_l, lambda_internes


def objective_function_fixed_eM(
    x: np.ndarray,
    eM_fixed: float,
    num_knots: int,
    l_array: np.ndarray,
    r_tgt_array: np.ndarray,
    min_knot_dist: float,
    nSub_complex_array: Optional[np.ndarray] = None,
) -> float:
    """

    Objective function with fixed eM, optimizes eL, dielectric, and knots.

    nSub_complex_array can be pre-computed and passed for performance.

    """

    diag_logger = logging.getLogger("CertusMetal")
    context: dict[str, Any] = {}
    try:
        context = _validate_bilayer_objective_inputs(x, num_knots, l_array, r_tgt_array, min_knot_dist, eM_fixed=eM_fixed)
        val = _bilayer_reflectance_mse(
            x, l_array, r_tgt_array, num_knots, min_knot_dist, nSub_complex_array, eM_fixed=eM_fixed
        )
    except Exception as exc:
        context["exception_type"] = type(exc).__name__
        context["exception"] = str(exc)
        _write_bilayer_autopsy_record(
            "fixed_eM_objective_exception",
            {
                "reason": f"fixed_eM_objective_failed:{type(exc).__name__}:{exc}",
                "context": context,
                "eM_fixed": float(eM_fixed) if np.isfinite(eM_fixed) else None,
                "x": np.asarray(x, dtype=float).tolist() if np.asarray(x).size else [],
            },
        )
        return _diagnostic_bilayer_penalty(f"fixed_eM_objective_failed:{type(exc).__name__}:{exc}", x, logger=diag_logger, context=context)
    if not np.isfinite(val):
        context["objective_value"] = float(val)
        _write_bilayer_autopsy_record(
            "fixed_eM_objective_non_finite",
            {
                "reason": f"fixed_eM_objective_non_finite:{val}",
                "context": context,
                "eM_fixed": float(eM_fixed) if np.isfinite(eM_fixed) else None,
                "x": np.asarray(x, dtype=float).tolist() if np.asarray(x).size else [],
            },
        )
        return _diagnostic_bilayer_penalty(f"fixed_eM_objective_non_finite:{val}", x, logger=diag_logger, context=context)
    return float(val)


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

            beam_emit_interval_s = 0.2

            last_beam_emit_t = 0.0

            beam_stall_patience = int(self.params.get("beam_stall_patience", 10))

            beam_fail_patience = int(self.params.get("beam_fail_patience", 6))

            beam_min_rel_gain = float(self.params.get("beam_min_rel_gain", 2e-4))

            # Generic function to process thickness list

            def process_scan_range(eM_list, start_x0, _direction_label=""):

                nonlocal processed_steps, last_beam_emit_t

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
                                num_knots,
                                l_array,
                                r_tgt_array,
                                min_knot_dist,
                                nSub_precomputed,
                            )

                            return float(cost_full), g_full[1:]  # Exclude eM gradient

                        res = scipy.optimize.minimize(
                            obj_and_grad_fixed_eM,
                            current_x0,
                            method="L-BFGS-B",
                            bounds=bounds,
                            jac=True,
                            options={"ftol": 1e-9, "gtol": 1e-9, "maxiter": 2000},
                        )

                        # If failed or bad MSE, retry L-BFGS-B with relaxed tolerances (analytic jac kept)

                        if (not res.success) or (res.fun > mse_threshold * 1.5):
                            res_retry_grad = scipy.optimize.minimize(
                                obj_and_grad_fixed_eM,
                                current_x0,
                                method="L-BFGS-B",
                                bounds=bounds,
                                jac=True,
                                options={"ftol": 1e-7, "gtol": 1e-7, "maxiter": 3000},
                            )

                            if res_retry_grad.fun < res.fun:
                                res = res_retry_grad

                        mse = res.fun

                        has_meaningful_gain = np.isfinite(mse) and (mse < branch_best_mse * (1.0 - beam_min_rel_gain))

                        if has_meaningful_gain:
                            branch_best_mse = float(mse)

                            no_gain_steps = 0

                        else:
                            no_gain_steps += 1

                        # Track consecutive low-quality points (outside useful beam region)

                        if np.isfinite(mse) and mse <= mse_threshold:
                            poor_quality_steps = 0

                        else:
                            poor_quality_steps += 1

                        # Verify validity

                        if np.isfinite(mse) and mse <= mse_threshold * 2.0:  # Accept wide for continuity
                            # Reconstruct solution

                            x_opt = res.x

                            eL_v, n_inf_v, A_v = x_opt[0], x_opt[1], x_opt[2]

                            spline_knot_count = num_knots
                            n_k_v = x_opt[3 : 3 + spline_knot_count]

                            k_k_v = x_opt[3 + spline_knot_count : 3 + 2 * spline_knot_count]

                            l_int_v = x_opt[3 + 2 * spline_knot_count :]
                            if n_k_v.size != spline_knot_count or k_k_v.size != spline_knot_count:
                                raise ValueError(
                                    f"Invalid beam spline state: n_size={n_k_v.size} k_size={k_k_v.size} expected={spline_knot_count}"
                                )

                            knot_l = np.concatenate(([l_min_val], np.sort(l_int_v), [l_max_val]))

                            p_spline = np.concatenate((n_k_v, k_k_v))

                            if p_spline.size != 2 * knot_l.size:
                                raise ValueError(
                                    f"Invalid spline state during beam scan: coeff_size={p_spline.size} knot_size={knot_l.size}"
                                )

                            n_c, k_c = get_nk_from_spline(p_spline, knot_l, plot_lambda)

                            # If MSE acceptable for final beam

                            if mse <= mse_threshold:
                                all_solutions.append(
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

                            logger.debug(f"Continuity loss at {eM_test:.2f} nm (MSE={mse:.2e}). Resetting.")

                            res_retry = scipy.optimize.minimize(
                                obj_and_grad_fixed_eM,
                                x0_optimal_reduced,
                                method="L-BFGS-B",
                                bounds=bounds,
                                jac=True,  # Keep analytic gradient in all retries
                                options={"ftol": 1e-7, "gtol": 1e-7, "maxiter": 3000},
                            )

                            if res_retry.fun < mse_threshold:
                                current_x0 = res_retry.x.copy()  # Found a valley

                            else:
                                # Stop branch if nothing good found

                                # logger.info(f"Stopping branch {direction_label} at {eM_test:.2f} nm")

                                # Continue a bit just in case

                                current_x0 = x0_optimal_reduced.copy()

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
                        logger.error(f"Error at {eM_test:.2f}: {e}", exc_info=True)

                        current_x0 = x0_optimal_reduced.copy()

                        no_gain_steps += 1

                        poor_quality_steps += 1

                    processed_steps += 1

                    now = time.time()

                    if processed_steps >= total_steps or now - last_beam_emit_t >= beam_emit_interval_s:
                        last_beam_emit_t = now

                        self.progress.emit(processed_steps, total_steps, self.optimal_mse)

                    # Early stop for this branch when scan is both stagnant and low-quality.

                    if no_gain_steps >= beam_stall_patience and poor_quality_steps >= beam_fail_patience:
                        logger.info(
                            f"Early stop {_direction_label}: stagnation at eM={eM_test:.2f} nm "
                            f"(no_gain={no_gain_steps}, poor={poor_quality_steps})"
                        )

                        break

            # Start both scans

            process_scan_range(eM_range_up, x0_optimal_reduced, "UP")

            process_scan_range(eM_range_down, x0_optimal_reduced, "DOWN")

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

    def stop(self):

        self.is_running = False


# =============================================================================


# MAIN WINDOW


# =============================================================================


class CertusMetalBilayerApp(MetalBaseApp):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
    """Main CERTUS-METAL Application (Bilayer: Metal + SiO2)"""

    MODULE_ID = "CERTUS_METAL_BILAYER"

    # CertusBaseApp configuration

    APP_NAME = "CERTUS-METAL-BILAYER"

    WINDOW_TITLE = "CERTUS • Metal n,k Index Determination"

    SUMMARY_SUBSTRATE_LABEL = "SILICON (SI)"

    SUMMARY_FACES_MODE = "ONE FACE (NO BACKSIDE)"

    def _load_defaults(self):
        """Load default values for CERTUS-METAL-BILAYER."""

        super()._load_defaults()

        bilayer_defaults = {
            "eL_nominal": DEFAULT_EL_NOMINAL,
            "eL_variation": DEFAULT_EL_VARIATION,
            "n_infini_min": "1.42",
            "n_infini_max": "1.44",
            "A_diel_min": "0",
            "A_diel_max": "10000",
            "num_knots": DEFAULT_NUM_KNOTS,
            "nk_min": DEFAULT_NK_MIN,
            "nk_max": DEFAULT_NK_MAX,
            "min_knot_dist": DEFAULT_MIN_KNOT_DISTANCE,
            "excel_filename": DEFAULT_EXCEL_FILENAME,
        }

        for key, value in bilayer_defaults.items():
            if hasattr(self, "widgets") and key in self.widgets:
                self.widgets[key].setText(str(value))

        for label_name in [
            "live_eM_label",
            "live_eL_label",
            "live_n_infini_label",
            "live_A_diel_label",
            "live_mse_label",
        ]:
            if hasattr(self, "widgets") and label_name in self.widgets:
                self.widgets[label_name].setText("N/A")

        if hasattr(self, "btn_beam"):
            self.btn_beam.setEnabled(False)

        if hasattr(self, "btn_stop"):
            self.btn_stop.setEnabled(False)

        if hasattr(self, "btn_run"):
            self.btn_run.setEnabled(True)

        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(0)

        self.worker = None

        self.optimization_thread = None

        self.final_results = None

        self._last_worker_params = None

    def _setup_parameter_grid(self, layout):
        """Setup parameter grid (Hook)"""

        params_grid = QGridLayout()

        params_grid.setSpacing(6)

        params_grid.setContentsMargins(0, 0, 0, 0)

        # Row 0: Input Data (Base helper)

        params_grid.addWidget(self._create_input_group(), 0, 0, 1, 2)

        # Row 1: Physical (left) + Material (right)

        params_grid.addWidget(self._create_physical_params_group(), 1, 0)

        params_grid.addWidget(self._create_material_params_group(), 1, 1)

        # Row 2: Output + Live

        params_grid.addWidget(self._create_output_group(), 2, 0)

        params_grid.addWidget(self._create_live_params_group(), 2, 1)

        params_grid.setColumnStretch(0, 1)

        params_grid.setColumnStretch(1, 1)

        # Add to parent layout

        w = QWidget()

        w.setLayout(params_grid)

        layout.addWidget(w, 0, 0)

    def _warmup_numba(self):
        """JIT precompilation via background thread"""
        try:
            self.sig_numba_ready.disconnect()
            self.sig_numba_error.disconnect()
        except TypeError:
            pass
        self.sig_numba_ready.connect(self._on_numba_ready_ui)
        self.sig_numba_error.connect(self._on_numba_error_ui)
        import threading
        if hasattr(self, "status_label"):
            self.status_label.setText("System warming up (compiling JIT)...")
        threading.Thread(target=self._warmup_numba_thread_runner, daemon=True).start()

    def _warmup_numba_thread_runner(self):
        try:
            wls = np.array([500.0, 600.0], dtype=np.float64)
            get_nk_si(wls)
            get_nk_cauchy_simple(wls, 1.45, 1000.0)
            from certus.core._certus_physics_impl import calculate_reflectance_bilayer_vectorized
            c_arr = np.array([1.5 + 0.0j, 1.5 + 0.0j], dtype=np.complex128)
            calculate_reflectance_bilayer_vectorized(wls, c_arr, 10.0, 10.0, c_arr, c_arr)

            self.sig_numba_ready.emit()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"✗ Numba warmup failed: {e}", exc_info=True)
            self.sig_numba_error.emit()

    @pyqtSlot()
    def _on_numba_ready_ui(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText("Ready (JIT Compiled)")
        self._on_numba_ready()  # Mark as ready
        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass

    @pyqtSlot()
    def _on_numba_error_ui(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText("JIT Init Error")

    def _create_physical_params_group(self):
        """Creates compact physical params group with Info Icons"""

        c = CertusCard("Physical Parameters")

        l = c.body

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        self.widgets["eM_min"] = QLineEdit(str(DEFAULT_EM_MIN))

        self.widgets["eM_min"].setFixedHeight(24)

        self.widgets["eM_max"] = QLineEdit(str(DEFAULT_EM_MAX))

        self.widgets["eM_max"].setFixedHeight(24)

        self.widgets["eL_nominal"] = QLineEdit(DEFAULT_EL_NOMINAL)

        self.widgets["eL_nominal"].setFixedHeight(24)

        self.widgets["eL_variation"] = QLineEdit(DEFAULT_EL_VARIATION)

        self.widgets["eL_variation"].setFixedHeight(24)

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

        l.addLayout(
            self._create_labeled_input(
                "eL nom:",
                self.widgets["eL_nominal"],
                "Nominal thickness of the dielectric underlayer (SiO2).",
            )
        )

        l.addLayout(
            self._create_labeled_input(
                "eL +/-:",
                self.widgets["eL_variation"],
                "Allowed thickness variation range for eL optimization.",
            )
        )

        return c

    def _create_material_params_group(self):
        """Creates compact material params group with Info Icons"""

        c = CertusCard("Material Parameters")

        l = c.body

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        # SiO2 Inputs

        self.widgets["n_infini_min"] = QLineEdit("1.42")

        self.widgets["n_infini_min"].setFixedHeight(24)

        self.widgets["n_infini_max"] = QLineEdit("1.44")

        self.widgets["n_infini_max"].setFixedHeight(24)

        self.widgets["A_diel_min"] = QLineEdit("0")

        self.widgets["A_diel_min"].setFixedHeight(24)

        self.widgets["A_diel_max"] = QLineEdit("10000")

        self.widgets["A_diel_max"].setFixedHeight(24)

        # Metal Inputs

        self.widgets["num_knots"] = QLineEdit(str(DEFAULT_NUM_KNOTS))

        self.widgets["num_knots"].setFixedHeight(24)

        self.widgets["nk_min"] = QLineEdit(str(DEFAULT_NK_MIN))

        self.widgets["nk_min"].setFixedHeight(24)

        self.widgets["nk_max"] = QLineEdit(str(DEFAULT_NK_MAX))

        self.widgets["nk_max"].setFixedHeight(24)

        self.widgets["min_knot_dist"] = QLineEdit(str(DEFAULT_MIN_KNOT_DISTANCE))

        self.widgets["min_knot_dist"].setFixedHeight(24)

        l.addLayout(
            self._create_labeled_input(
                "n∞ min:",
                self.widgets["n_infini_min"],
                "Min High-Frequency Index (SiO2).",
            )
        )

        l.addLayout(
            self._create_labeled_input(
                "n∞ max:",
                self.widgets["n_infini_max"],
                "Max High-Frequency Index (SiO2).",
            )
        )

        l.addLayout(self._create_labeled_input("A min:", self.widgets["A_diel_min"], "Min Cauchy Dispersion A term."))

        l.addLayout(self._create_labeled_input("A max:", self.widgets["A_diel_max"], "Max Cauchy Dispersion A term."))

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

    def _create_live_params_group(self):
        """Creates compact live params group"""

        c = CertusCard("Live Parameters")

        l = QGridLayout()

        l.setSpacing(4)

        l.setContentsMargins(8, 12, 8, 8)

        c.body.addLayout(l)

        self.widgets["live_eM_label"] = QLabel("N/A")

        self.widgets["live_eL_label"] = QLabel("N/A")

        self.widgets["live_n_infini_label"] = QLabel("N/A")

        self.widgets["live_A_diel_label"] = QLabel("N/A")

        self.widgets["live_mse_label"] = QLabel("N/A")

        live_label_style = f"font-size: 14pt; font-weight: bold; color: {CertusTheme.TEXT_MAIN};"

        for label in [
            "live_eM_label",
            "live_eL_label",
            "live_n_infini_label",
            "live_A_diel_label",
        ]:
            self.widgets[label].setStyleSheet(live_label_style)

        self.widgets["live_mse_label"].setStyleSheet(
            f"font-size: 15pt; color: {CertusTheme.DANGER_TEXT}; font-weight: bold;"
        )

        row = 0

        l.addWidget(QLabel("eM:"), row, 0)

        l.addWidget(self.widgets["live_eM_label"], row, 1)

        row += 1

        l.addWidget(QLabel("eL:"), row, 0)

        l.addWidget(self.widgets["live_eL_label"], row, 1)

        row += 1

        l.addWidget(QLabel("n∞:"), row, 0)

        l.addWidget(self.widgets["live_n_infini_label"], row, 1)

        row += 1

        l.addWidget(QLabel("A:"), row, 0)

        l.addWidget(self.widgets["live_A_diel_label"], row, 1)

        row += 1

        l.addWidget(QLabel("RMSE:"), row, 0)

        l.addWidget(self.widgets["live_mse_label"], row, 1)

        l.setColumnStretch(1, 1)

        return c

    def _setup_plots(self):
        """Standard Metal Plots"""

        # 1. Reflectance Tab

        self.reflectance_plot = CertusScientificPlot(
            self,
            "Reflectance Comparison",
            "Reflectance",
            "Wavelength (nm)",
        )

        self.reflectance_plot.addLegend(offset=(-10, 10))

        self.reflectance_plot.showGrid(x=True, y=True)

        self.target_curve = self.reflectance_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=3, symbolBrush="k", name="Target"
        )

        self.calc_curve = self.reflectance_plot.plot(
            [], [], pen=pg.mkPen(CertusTheme.CHART_PRIMARY, width=2), name="Calculated"
        )

        self.tabs.addTab(self.reflectance_plot, "Reflectance")

        setup_common_metal_plots(self)

        self.diel_plot = CertusScientificPlot(
            self,
            "Dielectric Layer",
            "Refractive Index (n)",
            "Wavelength (nm)",
        )
        self.diel_plot.showGrid(x=True, y=True)
        self.diel_curve = self.diel_plot.plot([], [], pen=pg.mkPen(CertusTheme.SUCCESS, width=2), name="SiO2")
        self.tabs.addTab(self.diel_plot, "Dielectric")

        self.mse_plot = CertusScientificPlot(
            self,
            "Optimization Convergence",
            "RMSE",
            "Iteration",
        )
        self.mse_plot.showGrid(x=True, y=True)
        self.mse_plot.setLogMode(y=True)
        self.mse_curve = self.mse_plot.plot([], [], pen=pg.mkPen(CertusTheme.CHART_DANGER, width=2))
        self.tabs.addTab(self.mse_plot, "Convergence")

        self.perf_tab = QWidget()
        perf_layout = QGridLayout(self.perf_tab)
        perf_layout.setSpacing(16)
        perf_layout.setContentsMargins(22, 22, 22, 22)

        cards = [
            FlashyCard("Bilayer Metal + Dielectric", "Joint adjustment of both layers\nBetter representation of real stacks", icon="🚀"),
            FlashyCard("High-Speed Numba TMM", "Fast evaluation of combinations\nPractical convergence over large bounds", icon="⚡"),
            FlashyCard("Multi-View Physical Analysis", "R/T, n&k, and dielectric tabs\nComprehensive diagnostic of spectral behavior", icon="📈"),
            FlashyCard("Robust Global Optimization", "Differential Evolution for non-convex spaces\nReliable search for the best compromise", icon="🔮"),
        ]
        for idx, card in enumerate(cards):
            perf_layout.addWidget(card, idx // 2, idx % 2)
        self.tabs.addTab(self.perf_tab, "About")

    def on_file_loaded(self, data):
        """Process loaded data (Hook from MetalBaseApp)"""

        try:
            self.target_data = build_metal_target_data(data, include_t=False, include_rback=False)

            self.target_curve.setData(self.target_data["lambda"], self.target_data["R"])

            self.update_lambda_filters()

            self.reflectance_plot.autoRange()

        except (ValueError, NUMERICAL_FAULT_EXCEPTIONS) as e:
            QMessageBox.critical(self, "Data Error", f"Error processing file data: {e}")

            self.target_data = None

    def _build_bilayer_optimization_params(self) -> dict:
        """Build validated optimization parameters for the BILAYER workflow."""

        params: dict[str, float | int | str | np.ndarray] = {}
        params["num_knots"] = int(self.widgets["num_knots"].text())
        params["n_infini_bounds"] = self._get_param_bounds("n_infini")
        params["A_diel_bounds"] = self._get_param_bounds("A_diel")
        return params

    def start_optimization(self):
        """Starts optimization using the shared _metal_start_optimization helper."""

        def build_params(params):
            params.update(self._build_bilayer_optimization_params())

        def before_run(params):
            for line in build_metal_startup_log_lines(self, variant_label="METAL BILAYER", params=params):
                self.logger.info(line)
            return True

        def build_bounds(params, target_lambda):
            bounds = _build_bilayer_bounds(params, l_array=target_lambda, include_eM=True)
            # Seed the global optimizer with a physically sane midpoint vector.
            # This keeps the initial PGLOBAL probe aligned with the bilayer parametrization.
            num_knots = int(params["num_knots"])
            spline_knot_count = num_knots
            l_min = float(np.min(target_lambda)) if np.asarray(target_lambda).size else 350.0
            l_max = float(np.max(target_lambda)) if np.asarray(target_lambda).size else 880.0
            internal = np.linspace(l_min + 0.1 * (l_max - l_min), l_max - 0.1 * (l_max - l_min), max(0, spline_knot_count - 2))
            x0 = np.concatenate(
                (
                    [float(params.get("eM_min", DEFAULT_EM_MIN) + 0.5 * (params.get("eM_max", DEFAULT_EM_MAX) - params.get("eM_min", DEFAULT_EM_MIN)))],
                    [float(params.get("eL_nominal", 900.0))],
                    [float(params.get("n_infini_bounds", (1.42, 1.44))[0] + 0.5 * (params.get("n_infini_bounds", (1.42, 1.44))[1] - params.get("n_infini_bounds", (1.42, 1.44))[0]))],
                    [float(params.get("A_diel_bounds", (0, 10000))[0] + 0.5 * (params.get("A_diel_bounds", (0, 10000))[1] - params.get("A_diel_bounds", (0, 10000))[0]))],
                    np.full(spline_knot_count, 5.0, dtype=float),
                    np.full(spline_knot_count, 0.5, dtype=float),
                    internal.astype(float, copy=False),
                )
            )
            params["x0"] = x0
            return bounds

        self._metal_start_optimization(
            worker_class=OptimizationWorker,
            build_bounds_fn=build_bounds,
            build_params_fn=build_params,
            before_run_fn=before_run,
        )

    def _on_optim_progress(self, data):
        """Updates progress widget with optimization progress"""

        data = normalize_metal_progress_payload(data)
        iteration = data.get("iteration", 0)
        mse = data.get("mse", 0)
        rmse = np.sqrt(mse) if mse > 0 else 0
        xk = data.get("params", None)
        eM = xk[0] if xk is not None else 0.0
        progress_pct = data.get("progress_pct", None)
        mode = str(data.get("mode", "global")).lower()
        best_cost = float(data.get("best_cost", mse))
        evals = int(data.get("evaluation_count", self.stat_counters.get("SP", 0)))
        elapsed_s = float(data.get("elapsed_s", 0.0))
        max_iter = int(data.get("max_iteration", getattr(self, "_optim_max_iter", DEFAULT_MAXITER)))
        phase = "PGLOBAL" if mode == "global" else "local"

        # UI update only (console logging is handled by pglobal_adapter)

        self.progress_widget.update(
            iteration=iteration,
            max_iter=max_iter,
            evals=evals,
            phase=phase,
            extra_info=f"RMSE: {rmse:.6f} | Best: {best_cost:.6f} | {elapsed_s:.0f}s" if rmse > 0 else f"Best: {best_cost:.6f} | {elapsed_s:.0f}s",
            progress_pct=progress_pct if progress_pct is not None else -1,
        )

        # Top 1% UX Morphing Live
        if xk is not None:
            try:
                l_array = getattr(self, "x", None)
                if l_array is not None:
                    from certus.core._certus_physics_impl import get_nk_cauchy_simple, calculate_reflectance_bilayer_vectorized, get_nk_from_spline
                    eM_fixed = getattr(self, "optim_args", {}).get("eM_fixed", None)
                    num_knots = getattr(self, "optim_args", {}).get("num_knots", 5)
                    offset = 4 if eM_fixed is None else 3
                    eM_val = float(xk[0] if eM_fixed is None else eM_fixed)
                    eL_val = float(xk[1] if eM_fixed is None else xk[0])
                    n_infini_val = float(xk[2] if eM_fixed is None else xk[1])
                    A_val = float(xk[3] if eM_fixed is None else xk[2])
                    
                    n_knots = xk[offset : offset + num_knots]
                    k_knots = xk[offset + num_knots : offset + 2 * num_knots]
                    lambda_internes = xk[offset + 2 * num_knots :]
                    
                    min_lambda = float(np.min(l_array))
                    max_lambda = float(np.max(l_array))
                    knot_l = np.empty(num_knots, dtype=np.float64)
                    knot_l[0] = min_lambda
                    if len(lambda_internes) > 0:
                        knot_l[1:-1] = np.sort(lambda_internes)
                    knot_l[-1] = max_lambda
                    
                    p_spline_nk = np.empty(2 * num_knots, dtype=np.float64)
                    p_spline_nk[:num_knots] = n_knots
                    p_spline_nk[num_knots:] = k_knots
                    
                    nM_real, nM_imag = get_nk_from_spline(p_spline_nk, knot_l, l_array, use_cache=False)
                    nL_calc = get_nk_cauchy_simple(l_array, n_infini_val, A_val)
                    
                    n_sub = getattr(self, "substrate_nk", None)
                    if n_sub is None:
                        from certus.core._certus_physics_impl import get_nk_si
                        n_sub = get_nk_si(l_array)
                        
                    R_calc = calculate_reflectance_bilayer_vectorized(
                        l_array, nM_real - 1j * nM_imag, eM_val, eL_val, nL_calc + 0j, n_sub
                    )
                    
                    self.reflectance_curve.setData(l_array, R_calc)
                    if hasattr(self, "n_curve"): self.n_curve.setData(l_array, nM_real)
                    if hasattr(self, "k_curve"): self.k_curve.setData(l_array, nM_imag)
                    
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
            except Exception:
                pass

    def on_optimization_finished(self, results):
        """Handles optimization finish"""

        self._uninstall_all_skeletons()

        self.progress_widget.stop("Optimization complete — results ready")

        # Cache iteration count before cleanup (thread-safe)

        worker = getattr(self, "worker", None)

        iteration_count = worker.iteration_count if worker else results.get("nit", 0)

        # Reset UI state (no confirmation needed - optimization completed normally)

        self.btn_run.setEnabled(True)

        self.btn_stop.setEnabled(False)

        self.btn_beam.setEnabled(True)

        self.update_plots(
            {
                "params": results["result"].x,
                "mse": results["result"].fun,
                "iteration": iteration_count,
                "best_cost": results["result"].fun,
                "evaluation_count": getattr(worker, "evaluation_count", 0) if worker else 0,
                "max_iteration": getattr(self, "_optim_max_iter", DEFAULT_MAXITER),
                "progress_pct": 100,
                "mode": "global",
                "elapsed_s": 0.0,
            },
            final=True,
        )

        self.final_results = results

        # Self-export (Excel + HTML) if enabled via HUB

        if get_export_config():
            QTimer.singleShot(500, self.export_results)

    def update_plots(self, data, final=False):
        """Updates plots with current optimization state (live during run, full on finish)."""
        p = getattr(self, "_last_worker_params", None)
        if p is None:
            return

        xk = data.get("params")
        if xk is None:
            return

        rmse_val = np.sqrt(data["mse"]) if data.get("mse", 0) >= 0 else 0.0

        self._update_bilayer_live_labels(xk, rmse_val)
        self._update_bilayer_mse_plot(data.get("iteration", 0), rmse_val)
        self._update_bilayer_curves(p, xk, final)

        try:
            if self.p1 is not None and self.p2 is not None and self.p1.vb is not None:
                scene_rect = self.p1.vb.sceneBoundingRect()
                if scene_rect.isValid() and scene_rect.width() > 0 and scene_rect.height() > 0:
                    self.p2.setGeometry(scene_rect)
        except NUMERICAL_FAULT_EXCEPTIONS:
            pass

        if not final and int(data.get("iteration", 0)) % 3 == 0:
            self.p1.vb.autoRange()
            self.p2.autoRange()
            self.diel_plot.autoRange()

        if final:
            try:
                self.p1.vb.autoRange()
                self.p2.autoRange()
                self.diel_plot.autoRange()
            except Exception as exc:
                self.logger.warning("Bilayer final autoRange skipped: %s", exc, exc_info=True)

    def _update_bilayer_live_labels(self, xk, rmse_val):
        eM, eL, n_infini, A_diel = xk[0], xk[1], xk[2], xk[3]
        self.widgets["live_eM_label"].setText(f"{eM:.2f}")
        self.widgets["live_eL_label"].setText(f"{eL:.2f}")
        self.widgets["live_n_infini_label"].setText(f"{n_infini:.4f}")
        self.widgets["live_A_diel_label"].setText(f"{A_diel:.1f}")
        self.widgets["live_mse_label"].setText(f"{rmse_val:.4e}")

    def _update_bilayer_mse_plot(self, iteration, rmse_val):
        if not hasattr(self, "mse_data"):
            self.mse_data = {"iterations": [], "errors": []}
        self.mse_data["iterations"].append(iteration)
        self.mse_data["errors"].append(rmse_val)
        self.mse_curve.setData(self.mse_data["iterations"], self.mse_data["errors"])

    def _update_bilayer_curves(self, p, xk, final):
        eM, eL, n_infini, A_diel = xk[0], xk[1], xk[2], xk[3]
        num_knots, offset = p["num_knots"], 4
        spline_knot_count = num_knots
        n_knots = xk[offset : offset + spline_knot_count]
        k_knots = xk[offset + spline_knot_count : offset + 2 * spline_knot_count]
        lambda_internes = xk[offset + 2 * spline_knot_count :]

        l_array = p["target_lambda"]
        min_l, max_l = l_array.min(), l_array.max()

        try:
            knot_l, lambda_internes = _validate_bilayer_spline_state(
                n_knots,
                k_knots,
                lambda_internes,
                min_l,
                max_l,
                expected_knot_count=num_knots,
            )
        except Exception as exc:
            self.logger.warning("Bilayer spline plot skipped: %s", exc, exc_info=True)
            return

        p_spline_nk = np.concatenate((n_knots, k_knots))
        plot_lambda_range = np.linspace(min_l, max_l, 200)

        try:
            n_calc, k_calc = get_nk_from_spline(p_spline_nk, knot_l, plot_lambda_range)
            n_calc_data, k_calc_data = get_nk_from_spline(p_spline_nk, knot_l, l_array)
        except Exception as exc:
            self.logger.warning("Bilayer spline plot skipped: %s", exc, exc_info=True)
            return

        nL_calc = get_nk_cauchy_simple(plot_lambda_range, n_infini, A_diel)

        try:
            R_calc = calculate_reflectance_bilayer_vectorized(
                l_array,
                n_calc_data - 1j * k_calc_data,
                eM,
                eL,
                get_nk_cauchy_simple(l_array, n_infini, A_diel) + 0j,
                get_nk_si(l_array),
            )
            if not np.all(np.isfinite(R_calc)):
                raise ValueError("non-finite reflectance curve")
        except Exception as exc:
            self.logger.warning("Bilayer reflectance plot skipped: %s", exc, exc_info=True)
            return

        pen_calc = pg.mkPen(CertusTheme.PRIMARY, width=3) if final else pg.mkPen(CertusTheme.PRIMARY, width=2)
        pen_diel = pg.mkPen(CertusTheme.SUCCESS, width=3) if final else pg.mkPen(CertusTheme.SUCCESS, width=2)

        self.calc_curve.setData(l_array, R_calc, pen=pen_calc)
        self.n_curve.setData(plot_lambda_range, n_calc)
        self.k_curve.setData(plot_lambda_range, k_calc)
        self.diel_curve.setData(plot_lambda_range, nL_calc, pen=pen_diel)

    def export_results(self):
        """Exports results to Excel + HTML (Single/Beam)"""

        # Check if beam analysis done
        if hasattr(self, "beam_stats") and self.beam_stats is not None:
            self._export_beam_results()
            return

        # Single optimization export
        if not hasattr(self, "final_results"):
            show_toast(self, "Please run optimization first.", "warning")
            return

        # Prepare data
        reports_dir = get_resource_path("reports")
        os.makedirs(reports_dir, exist_ok=True)

        # --- AUTO EXPORT LOGIC ---
        if not get_export_config():
            return

        try:
            self._do_export_bilayer_results(reports_dir)
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error saving reports: {e}")
            traceback.print_exc()

    def _do_export_bilayer_results(self, reports_dir: str):
        from certus.utils.certus_data import ReportSection

        res = self.final_results["result"]
        xk = res.x
        mse = res.fun

        p = getattr(self, "_last_worker_params", None)
        if p is None:
            if "params" in self.final_results:
                p = self.final_results["params"]
            else:
                self.logger.error("No parameters found for export")
                return

        ts = certus_timestamp_file()
        rmse_val = np.sqrt(mse) if mse > 0 else 0.0
        base_name = f"Report_METAL_BILAYER_{ts}_RMSE_{rmse_val:.5f}"
        excel_path = str(Path(reports_dir) / f"{base_name}.xlsx")
        html_path = str(Path(reports_dir) / f"{base_name}.html")

        df_summary = pd.DataFrame(
            {
                "Parameter": ["Date", "Final RMSE", "Final MSE", "Max Iterations", "Workers"],
                "Value": [
                    certus_timestamp_display(),
                    f"{np.sqrt(mse):.6f}",
                    f"{mse:.6e}",
                    str(p.get("maxiter", "N/A")),
                    str(p.get("workers", "N/A")),
                ],
            }
        )

        dl_rows = [
            {"Parameter": "eM (Metal)", "Value": xk[0], "Unit": "nm"},
            {"Parameter": "eL (SiO2)", "Value": xk[1], "Unit": "nm"},
            {"Parameter": "n_inf (SiO2)", "Value": xk[2], "Unit": "-"},
            {"Parameter": "A_diel", "Value": xk[3], "Unit": "-"},
        ]

        df_spectra = self._build_export_spectra_dataframe(p, xk)
        if df_spectra is None:
            return

        summary_kv = dict(zip(df_summary["Parameter"], df_summary["Value"]))
        dl_kv = {r["Parameter"]: f"{r['Value']:.4f} {r['Unit']}" for r in dl_rows}

        sections = [
            ReportSection("Optimization Summary", kind="kv", content=summary_kv, sheet_name="Summary"),
            ReportSection("Drude-Lorentz Parameters", kind="kv", content=dl_kv, sheet_name="Drude-Lorentz"),
            ReportSection("Spectra", kind="table", content=df_spectra, sheet_name="Spectra"),
            ReportSection(
                "Reflectance Plot",
                kind="image",
                content=self.widget_to_b64(getattr(self, "reflectance_plot", None)),
                include_in_excel=False,
            ),
            ReportSection(
                "Clues Plot",
                kind="image",
                content=self.widget_to_b64(getattr(self, "clues_plot", None)),
                include_in_excel=False,
            ),
            ReportSection(
                "MSE Plot",
                kind="image",
                content=self.widget_to_b64(getattr(self, "mse_plot", None)),
                include_in_excel=False,
            ),
        ]

        self.export_via_builder(sections, excel_path=excel_path, html_path=html_path)
        self.logger.info(f"Reports saved — {base_name}")
        self.status_label.setText(f"Reports saved — {base_name}")

    def _build_export_spectra_dataframe(self, params, xk):
        l_array = params["target_lambda"]
        num_knots, offset = params["num_knots"], 4
        spline_knot_count = num_knots
        n_knots = xk[offset : offset + spline_knot_count]
        k_knots = xk[offset + spline_knot_count : offset + 2 * spline_knot_count]
        lambda_internes = xk[offset + 2 * spline_knot_count :]
        min_l, max_l = l_array.min(), l_array.max()

        try:
            knot_l, lambda_internes = _validate_bilayer_spline_state(
                n_knots,
                k_knots,
                lambda_internes,
                min_l,
                max_l,
                expected_knot_count=num_knots,
            )
        except Exception as exc:
            self.logger.warning("Bilayer export skipped: %s", exc, exc_info=True)
            return None

        p_spline_nk = np.concatenate((n_knots, k_knots))
        n_calc_data, k_calc_data = get_nk_from_spline(p_spline_nk, knot_l, l_array)
        R_calc = calculate_reflectance_bilayer_vectorized(
            l_array,
            n_calc_data - 1j * k_calc_data,
            xk[0],
            xk[1],
            get_nk_cauchy_simple(l_array, xk[2], xk[3]) + 0j,
            get_nk_si(l_array),
        )

        return pd.DataFrame(
            {
                "Wavelength (nm)": l_array,
                "R Target": params.get("target_r", np.zeros_like(l_array)),
                "R Calc": R_calc,
                "n (Metal)": n_calc_data,
                "k (Metal)": k_calc_data,
            }
        )

    def _export_beam_results(self):
        """Export beam results to Excel"""

        stats = self.beam_stats

        excel_filename = self.widgets["excel_filename"].text()

        # Summary (ensemble stats)

        # Convert MSE to RMSE for export

        rmse_best = np.sqrt(stats["best_mse"]) if stats["best_mse"] >= 0 else 0.0

        rmse_threshold = np.sqrt(stats["threshold"]) if stats["threshold"] >= 0 else 0.0

        df_summary = pd.DataFrame(
            {
                "Parameter": [
                    "eM_mean_nm",
                    "eM_std_nm",
                    "eM_min_nm",
                    "eM_max_nm",
                    "eM_range_nm",
                    "eL_mean_nm",
                    "eL_std_nm",
                    "eL_min_nm",
                    "eL_max_nm",
                    "RMSE_best",
                    "RMSE_threshold",
                    "Solutions_count",
                ],
                "Value": [
                    f"{stats['eM_mean']:.3f}",
                    f"{stats['eM_std']:.3f}",
                    f"{stats['eM_min']:.3f}",
                    f"{stats['eM_max']:.3f}",
                    f"{stats['eM_max'] - stats['eM_min']:.3f}",
                    f"{stats['eL_mean']:.3f}",
                    f"{stats['eL_std']:.3f}",
                    f"{stats['eL_mean'] - 2 * stats['eL_std']:.3f}",
                    f"{stats['eL_mean'] + 2 * stats['eL_std']:.3f}",
                    f"{rmse_best:.4e}",
                    f"{rmse_threshold:.4e}",
                    f"{stats['count']}",
                ],
            }
        )

        # Metal clues with uncertainty bands

        df_metal = pd.DataFrame(
            {
                "lambda_nm": stats["lambda_axis"],
                "n_mean": stats["n_mean"],
                "n_std": stats["n_std"],
                "n_min": stats["n_min"],
                "n_max": stats["n_max"],
                "n_lower_2sigma": stats["n_mean"] - 2 * stats["n_std"],
                "n_upper_2sigma": stats["n_mean"] + 2 * stats["n_std"],
                "k_mean": stats["k_mean"],
                "k_std": stats["k_std"],
                "k_min": stats["k_min"],
                "k_max": stats["k_max"],
                "k_lower_2sigma": stats["k_mean"] - 2 * stats["k_std"],
                "k_upper_2sigma": stats["k_mean"] + 2 * stats["k_std"],
            }
        )

        # Individual solutions (all valid)

        solutions_data = []

        for idx, sol in enumerate(stats["all_solutions"]):
            # Convert MSE to RMSE for export

            rmse_val = np.sqrt(sol["mse"]) if sol["mse"] >= 0 else 0.0

            solutions_data.append(
                {
                    "Solution_ID": idx + 1,
                    "RMSE": rmse_val,
                    "eM_nm": sol["eM"],
                    "eL_nm": sol["eL"],
                    "n_infini": sol["n_infini"],
                    "A_diel": sol["A_diel"],
                }
            )

        df_solutions = pd.DataFrame(solutions_data)

        try:
            if not OPENPYXL_AVAILABLE:
                raise ImportError("openpyxl is required for Excel writing. Install with: pip install openpyxl")

            with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
                df_summary.to_excel(writer, sheet_name="Summary_Beam", index=False)

                df_metal.to_excel(writer, sheet_name="Metal_Indices_Uncertainty", index=False)

                df_solutions.to_excel(writer, sheet_name="All_Solutions", index=False)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Beam analysis results saved to\n{excel_filename}",
            )

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            QMessageBox.critical(self, "Export Error", f"Cannot write Excel file:\n{e}")

    def start_beam_analysis(self):
        """Starts beam analysis: metal thickness scan"""

        if not self.target_data:
            show_toast(self, "Load target file first.", "warning")

            return

        # Verify optimization done

        if not hasattr(self, "final_results") or self.final_results is None:
            show_toast(
                self,
                "Run standard optimization (START) first\nto get reference solution.",
                "warning",
            )

            return

        try:
            p = {k: v.text() for k, v in self.widgets.items() if isinstance(v, QLineEdit)}

            params = {k: float(v) for k, v in p.items() if k not in ["excel_filename"]}

            params["num_knots"] = int(p["num_knots"])

            # Bounds for n_infini and A_diel

            params["n_infini_bounds"] = self._get_param_bounds("n_infini")

            params["A_diel_bounds"] = self._get_param_bounds("A_diel")

            params["eM_min"] = float(p.get("eM_min", DEFAULT_EM_MIN))

            params["eM_max"] = float(p.get("eM_max", DEFAULT_EM_MAX))

            params["eL_nominal"] = float(p.get("eL_nominal", DEFAULT_EL_NOMINAL))

            params["eL_variation"] = float(p.get("eL_variation", DEFAULT_EL_VARIATION))

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

        # Scan step 0.5 nm, MSE tolerance 20% + 1e-5 (smart threshold)

        worker = BeamAnalysisWorker(
            params,
            optimal_solution,
            optimal_mse,
            step_nm=0.5,
            mse_tolerance=0.2,
        )

        setup_beam_analysis_thread(self, worker).start()

    def on_beam_finished(self, stats):
        """Handles ensemble analysis finish"""
        teardown_beam_thread(self, stats)

        self._clear_beam_plots()
        x = stats["lambda_axis"]

        if "valleys" in stats and stats["valleys"]:
            self._plot_beam_valleys(x, stats["valleys"])

        self._plot_beam_global_uncertainty_n(x, stats)
        self._plot_beam_global_uncertainty_k(x, stats)
        self._setup_beam_axes()

        if "all_solutions" in stats and len(stats["all_solutions"]) > 0:
            self._plot_beam_individual_solutions(stats)

        self._sync_beam_viewboxes()

        self.p1.vb.autoRange()
        self.p2.enableAutoRange(axis="y")
        self.tabs.setCurrentIndex(1)

        QTimer.singleShot(100, lambda: (self.p1.update(), self.p2.update()))

        self._show_beam_summary_dialog(stats)

        if get_export_config():
            QTimer.singleShot(500, self.export_results)

    def _clear_beam_plots(self):
        axes_to_keep = [
            self.p1.getAxis("left"),
            self.p1.getAxis("bottom"),
            self.p1.getAxis("right"),
            self.p1.getAxis("top"),
        ]
        items_to_remove_p1 = [item for item in self.p1.items if item not in axes_to_keep and item is not self.p2]
        for item in items_to_remove_p1:
            try:
                self.p1.removeItem(item)
            except (AttributeError, RuntimeError):
                pass
        items_to_remove_p2 = list(self.p2.addedItems) if hasattr(self.p2, "addedItems") else []
        for item in items_to_remove_p2:
            try:
                self.p2.removeItem(item)
            except (AttributeError, RuntimeError):
                pass

    def _plot_beam_valleys(self, x, valleys):
        valley_colors = [(0, 0, 255), (255, 0, 0), (0, 128, 0), (255, 165, 0), (128, 0, 128), (0, 255, 255), (255, 192, 203)]
        for idx, (valley_id, valley_data) in enumerate(sorted(valleys.items())):
            if valley_id == -1:
                continue
            color = valley_colors[idx % len(valley_colors)]
            alpha = 30
            n_valley, k_valley = valley_data["n_mean"], valley_data["k_mean"]
            n_std_valley, k_std_valley = valley_data["n_std"], valley_data["k_std"]

            n_upper_v, n_lower_v = n_valley + 2 * n_std_valley, n_valley - 2 * n_std_valley
            k_upper_v, k_lower_v = k_valley + 2 * k_std_valley, k_valley - 2 * k_std_valley

            curve_n_upper_v = pg.PlotDataItem(x, n_upper_v, pen=None)
            curve_n_lower_v = pg.PlotDataItem(x, n_lower_v, pen=None)
            fill_n_v = pg.FillBetweenItem(curve_n_lower_v, curve_n_upper_v, brush=pg.mkBrush(color[0], color[1], color[2], alpha))
            self.p1.addItem(fill_n_v)
            self.p1.plot(x, n_valley, pen=pg.mkPen(color, width=1.5, style=Qt.PenStyle.DashLine), name=f"Valley {valley_id}")

            curve_k_upper_v = pg.PlotDataItem(x, k_upper_v, pen=None)
            curve_k_lower_v = pg.PlotDataItem(x, k_lower_v, pen=None)
            fill_k_v = pg.FillBetweenItem(curve_k_lower_v, curve_k_upper_v, brush=pg.mkBrush(color[0], color[1], color[2], alpha))
            self.p2.addItem(fill_k_v)
            self.p2.plot(x, k_valley, pen=pg.mkPen(color, width=1.5, style=Qt.PenStyle.DashLine))

    def _plot_beam_global_uncertainty_n(self, x, stats):
        n_mean, n_std = stats["n_mean"], stats["n_std"]
        n_upper, n_lower = n_mean + 2 * n_std, n_mean - 2 * n_std
        curve_n_upper = pg.PlotDataItem(x, n_upper, pen=pg.mkPen(CertusTheme.PRIMARY, width=1, style=Qt.PenStyle.DotLine))
        curve_n_lower = pg.PlotDataItem(x, n_lower, pen=pg.mkPen(CertusTheme.PRIMARY, width=1, style=Qt.PenStyle.DotLine))
        fill_n = pg.FillBetweenItem(curve_n_lower, curve_n_upper, brush=pg.mkBrush(*CertusTheme.hex_to_rgba_tuple(CertusTheme.PRIMARY, 25)))
        self.p1.addItem(fill_n)
        self.p1.addItem(curve_n_upper)
        self.p1.addItem(curve_n_lower)
        self.n_curve = pg.PlotCurveItem(x, n_mean, pen=pg.mkPen(CertusTheme.PRIMARY, width=3), name="n (mean)")
        self.p1.addItem(self.n_curve)

    def _plot_beam_global_uncertainty_k(self, x, stats):
        k_mean, k_std = stats["k_mean"], stats["k_std"]
        k_upper, k_lower = k_mean + 2 * k_std, k_mean - 2 * k_std
        curve_k_upper = pg.PlotDataItem(x, k_upper, pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DotLine))
        curve_k_lower = pg.PlotDataItem(x, k_lower, pen=pg.mkPen(CertusTheme.DANGER, width=1, style=Qt.PenStyle.DotLine))
        fill_k = pg.FillBetweenItem(curve_k_lower, curve_k_upper, brush=pg.mkBrush(*CertusTheme.hex_to_rgba_tuple(CertusTheme.DANGER, 25)))
        self.p2.addItem(fill_k)
        self.p2.addItem(curve_k_upper)
        self.p2.addItem(curve_k_lower)
        if hasattr(self, "k_curve") and self.k_curve in getattr(self.p2, "addedItems", []):
            try:
                self.p2.removeItem(self.k_curve)
            except (AttributeError, RuntimeError):
                pass
        self.k_curve = pg.PlotCurveItem(x, k_mean, pen=pg.mkPen(CertusTheme.DANGER, width=3, style=Qt.PenStyle.DashLine), name="k (mean)")
        self.p2.addItem(self.k_curve)

    def _setup_beam_axes(self):
        self.p1.getAxis("left").setLabel("Refractive Index (n)", color=CertusTheme.PRIMARY)
        self.p1.getAxis("right").setLabel("Extinction Coefficient (k)", color=CertusTheme.DANGER)
        self.p1.showAxis("right")

    def _plot_beam_individual_solutions(self, stats):
        for sol in stats["all_solutions"]:
            if "n" in sol and "k" in sol and len(sol["n"]) > 0 and len(sol["k"]) > 0:
                pen_n_indiv = pg.mkPen(CertusTheme.hex_to_rgba_tuple(CertusTheme.PRIMARY, 50), width=1)
                n_item = pg.PlotDataItem(stats["lambda_axis"], sol["n"], pen=pen_n_indiv)
                self.p1.addItem(n_item)
                pen_k_indiv = pg.mkPen(CertusTheme.hex_to_rgba_tuple(CertusTheme.DANGER, 50), width=1)
                k_item = pg.PlotDataItem(stats["lambda_axis"], sol["k"], pen=pen_k_indiv)
                self.p2.addItem(k_item)

    def _sync_beam_viewboxes(self):
        self.p2.setXLink(self.p1)
        try:
            self.p1.vb.sigResized.disconnect()
        except (AttributeError, RuntimeError, TypeError):
            pass
        def _sync_p2_geometry(*_args):
            try:
                if self.p1 is None or self.p2 is None or self.p1.vb is None:
                    return
                scene_rect = self.p1.vb.sceneBoundingRect()
                if scene_rect.isValid() and scene_rect.width() > 0 and scene_rect.height() > 0:
                    self.p2.setGeometry(scene_rect)
            except NUMERICAL_FAULT_EXCEPTIONS:
                return
        self.p1.vb.sigResized.connect(_sync_p2_geometry)
        try:
            if self.p1 is not None and self.p2 is not None and self.p1.vb is not None:
                scene_rect = self.p1.vb.sceneBoundingRect()
                if scene_rect.isValid() and scene_rect.width() > 0 and scene_rect.height() > 0:
                    self.p2.setGeometry(scene_rect)
        except NUMERICAL_FAULT_EXCEPTIONS:
            pass

    def _show_beam_summary_dialog(self, stats):
        count = stats["count"]
        rmse_best = np.sqrt(stats["best_mse"]) if stats["best_mse"] >= 0 else 0.0
        rmse_optimal = np.sqrt(stats["optimal_mse"]) if stats["optimal_mse"] >= 0 else 0.0
        rmse_threshold = np.sqrt(stats["threshold"]) if stats["threshold"] >= 0 else 0.0

        self.status_label.setText(
            f"Beam: {count} solutions (RMSE < {rmse_threshold:.2e}) | eM: {stats['eM_min']:.1f}-{stats['eM_max']:.1f} nm"
        )
        QMessageBox.information(
            self,
            "Beam Analysis Results",
            f"Beam Analysis by Thickness Scan\n"
            f"{count} solutions kept (tolerance: +/-10%)\n"
            f"RMSE optimal: {rmse_optimal:.2e}\n"
            f"Best RMSE found: {rmse_best:.2e}\n\n"
            f"Thickness eM: {stats['eM_mean']:.2f} +/- {2 * stats['eM_std']:.2f} nm\n"
            f"  (range: {stats['eM_min']:.1f} - {stats['eM_max']:.1f} nm)\n"
            f"Thickness eL: {stats['eL_mean']:.2f} +/- {2 * stats['eL_std']:.2f} nm\n\n"
            f"Interpretation:\n"
            f"The beam shows metal index (n, k) variability\n"
            f"when thickness varies by 0.5 nm steps.\n"
            f"Individual curves (transparent) and colored zones\n"
            f"represent mathematical uncertainty.\n\n"
            f"See 'n & k' tab to visualize results.",
        )

    def _get_config_dict(self):
        """Returns JSON struct for config"""

        return {
            "version": "1.0.0",
            "excel_filename": self.widgets["excel_filename"].text(),
            "physical_params": {
                "eM_min": self.widgets["eM_min"].text(),
                "eM_max": self.widgets["eM_max"].text(),
                "eL_nominal": self.widgets["eL_nominal"].text(),
                "eL_variation": self.widgets["eL_variation"].text(),
            },
            "material_params": {
                "n_infini_min": self.widgets["n_infini_min"].text(),
                "n_infini_max": self.widgets["n_infini_max"].text(),
                "A_diel_min": self.widgets["A_diel_min"].text(),
                "A_diel_max": self.widgets["A_diel_max"].text(),
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

    def _apply_config_dict(self, config):
        """Loads JSON struct for config"""

        phys = config.get("physical_params", {})

        self.widgets["eM_min"].setText(str(phys.get("eM_min", DEFAULT_EM_MIN)))

        self.widgets["eM_max"].setText(str(phys.get("eM_max", DEFAULT_EM_MAX)))

        self.widgets["eL_nominal"].setText(str(phys.get("eL_nominal", "900")))

        self.widgets["eL_variation"].setText(str(phys.get("eL_variation", "20")))

        mat = config.get("material_params", {})

        self.widgets["n_infini_min"].setText(str(mat.get("n_infini_min", "1.40")))

        self.widgets["n_infini_max"].setText(str(mat.get("n_infini_max", "1.50")))

        self.widgets["A_diel_min"].setText(str(mat.get("A_diel_min", "3000")))

        self.widgets["A_diel_max"].setText(str(mat.get("A_diel_max", "4000")))

        self.widgets["num_knots"].setText(str(mat.get("num_knots", DEFAULT_NUM_KNOTS)))

        self.widgets["nk_min"].setText(str(mat.get("nk_min", DEFAULT_NK_MIN)))

        self.widgets["nk_max"].setText(str(mat.get("nk_max", DEFAULT_NK_MAX)))

        self.widgets["min_knot_dist"].setText(str(mat.get("min_knot_dist", DEFAULT_MIN_KNOT_DISTANCE)))

    # =============================================================================

    # MAIN

    # =============================================================================

    def _create_labeled_input(self, label_text, widget, tooltip_text=None):
        """Creates a horizontal layout with Label [Info] Widget"""

        layout = QHBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(5)

        lbl = QLabel(label_text)

        layout.addWidget(lbl)

        if tooltip_text:
            info_btn = create_info_icon(tooltip_text)

            layout.addWidget(info_btn)

        layout.addStretch()

        layout.addWidget(widget)

        return layout


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()

    # High DPI scaling (Must be set BEFORE creating QApplication)

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)

    init_certus_app("CERTUS-METAL", app=app)

    # --- SPLASH SCREEN ---

    from certus.ui.certus_splash import create_splash

    splash = create_splash("Initializing Metal Engine (Bilayer)...")

    # Setup logging with centralized helper

    setup_logging(log_file="certus_metal.log")

    window = CertusMetalBilayerApp()

    window.show()

    splash.finish(window)

    # Load file from CLI if provided

    if len(sys.argv) > 1:
        f = sys.argv[1]

        if Path(f).exists():
            QTimer.singleShot(100, lambda: window.load_config(f))

    sys.exit(app.exec())
