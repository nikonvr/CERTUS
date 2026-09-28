"""
CERTUS-METAL SINGLE: computation
================================

Bounds, objective functions and analytic gradient of the metal layer on a
transparent substrate (Air | Metal (eM) | substrate, incoherent), and the
substrate helpers they use.

This module imports neither PyQt6, nor pyqtgraph, nor certus.ui. The root
launcher CERTUS_METAL_SINGLE.py re-exports it.
"""

import numpy as np
from scipy.interpolate import CubicSpline

from certus.core.certus_core import (
    canonicalize_substrate_label,
    substrate_sellmeier_id,
    NUMERICAL_FAULT_EXCEPTIONS,
)
from certus.core._certus_physics_impl import get_n_substrate_array_by_id
from certus.metal.certus_metal_defaults import (
    DEFAULT_NK_MAX,
    DEFAULT_NK_MIN,
)
from certus_physics import (
    _compute_single_layer_sensitivity_kernel,
    calculate_RTRback_incoherent_vectorized,
    get_nk_from_spline,
)


def _resolve_single_substrate_id(sub_text: str) -> int:
    val = substrate_sellmeier_id(canonicalize_substrate_label(sub_text))
    if val is not None:
        return int(val)
    fallback = substrate_sellmeier_id("BK7")
    return int(fallback if fallback is not None else 1)

def _get_single_substrate_n_array(substrate_id: int, wavelengths_nm: np.ndarray) -> np.ndarray:
    try:
        return get_n_substrate_array_by_id(substrate_id, wavelengths_nm)
    except KeyError:
        fallback = substrate_sellmeier_id("BK7")
        return get_n_substrate_array_by_id(int(fallback if fallback is not None else 1), wavelengths_nm)


# =============================================================================


# CONSTANTS


# =============================================================================


# Constants imported from certus.metal.certus_metal_defaults


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

    # IMPORTANT: do not reuse mutable buffers from ``precomputed`` here.
    # PGlobal can evaluate candidates concurrently, and shared scratch arrays
    # corrupt the objective, producing unstable/slow convergence. These arrays
    # are tiny compared with the optical spectrum calculation, so per-call
    # local scratch is the safer and usually faster option overall.
    eM_buffer = np.empty(1, dtype=np.asarray(l_array).dtype)

    knot_l_buffer = np.empty(num_knots, dtype=np.asarray(l_array).dtype)

    p_spline_buffer = np.empty(2 * num_knots, dtype=np.asarray(l_array).dtype)

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

        d2_n = np.diff(n_calc, n=2)
        d2_k = np.diff(k_calc, n=2)
        wiggle_penalty = 1e-2 * (np.sum(d2_n**2) + np.sum(d2_k**2))

    except NUMERICAL_FAULT_EXCEPTIONS :
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

        return (total_mse / count) + wiggle_penalty

    mse = np.mean((R_calc - r_tgt) ** 2)

    return (mse + wiggle_penalty) if np.isfinite(mse) else np.inf


# Moved to certus_metal_common.py for mutualization


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
        use_cache=False,
    )


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

    if "x_full_buffer" in precomputed:
        x_full = precomputed["x_full_buffer"]
        x_full[:len(x)] = x
        # lambda_internes_fixed should already be at the end of x_full_buffer
    else:
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

    except NUMERICAL_FAULT_EXCEPTIONS :
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
