"""
CERTUS-METAL BILAYER: computation
=================================

Bounds, reflectance objective and fixed-thickness objective of the metal bilayer
(Air | Metal (eM) | SiO2 (eL) | Si), with the input and spline validators and
the diagnostic helpers they call.

This module imports neither PyQt6, nor pyqtgraph, nor certus.ui. The root
launcher CERTUS_METAL_BILAYER.py re-exports it.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np

from certus_physics import (
    calculate_reflectance_bilayer_vectorized,
    get_nk_cauchy_simple,
    get_nk_from_spline,
    get_nk_si,
)


# Silicon optical constants: loaded from clues.xlsx -> Si-substrate via certus_physics.get_nk_si()


def _build_bilayer_bounds(
    params: dict[str, Any], l_array: np.ndarray | None = None, include_eM: bool = True
) -> list[tuple[float, float]]:
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
    nSub_complex_array: np.ndarray | None,
    eM_fixed: float | None = None,
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
            
        d2_n = np.diff(n_calc, n=2)
        d2_k = np.diff(k_calc, n=2)
        wiggle_penalty = 1e-2 * (np.sum(d2_n**2) + np.sum(d2_k**2))
            
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
        return float(mse + wiggle_penalty)
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
    eM_fixed: float | None = None,
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
    nSub_complex_array: np.ndarray | None = None,
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
    nSub_complex_array: np.ndarray | None = None,
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
