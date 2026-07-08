"""
CERTUS Gradient Optimization - Utilities Module

Extracted from certus_opt_gradients.py for better modularity.
Contains shared utility functions for cost calculation and MSE computation.
"""

import numpy as np
from numba import njit, prange
from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE
import certus.physics.certus_tmm_core as tmm_core


SMALL_EPSILON = 1e-12


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_mse_vectorized(
    calc_values: np.ndarray, target_values: np.ndarray, weights: np.ndarray
) -> tuple[float, int]:
    """
    Compute weighted Mean Squared Error between calculated and target values.

    Args:
        calc_values: Calculated values array
        target_values: Target values array
        weights: Weight array for each point

    Returns:
        Tuple of (MSE, valid_point_count)
    """
    n = len(calc_values)

    sum_sq = 0.0
    sum_w = 0.0
    count = 0

    for i in prange(n):
        if weights[i] > 0 and np.isfinite(calc_values[i]) and np.isfinite(target_values[i]):
            diff = calc_values[i] - target_values[i]
            sum_sq += diff * diff * weights[i]
            sum_w += weights[i]
            count += 1

    if count < 5 or sum_w <= 1e-18:
        return 1e12, count

    return sum_sq / sum_w, count


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def cost_numba_fast(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
) -> float:
    """
    Fast cost function for TMM optimization (TRANSMISSION only).

    --- CRITICAL PHYSICS NOTE ---
    This cost function optimizes TRANSMISSION (T) ONLY.
    It compares T_calc vs Target Values (assumed to be T).

    If has_back=True, it uses the EXACT incoherent backside formula:
    T_total = (Tf * Tb) / (1 - Rf' * Rb')

    DO NOT CHANGE THIS LOGIC without verifying target types.

    Args:
        ep: Layer thicknesses array
        n_layers_T: Complex refractive indices (n_wls, n_layers)
        n_sub: Substrate refractive index array
        wls: Wavelengths array
        tgt_vals: Target transmission values
        tgt_weights: Weights for each wavelength
        min_d: Minimum thickness constraint
        has_back: Whether backside calculation is enabled
        n_back_T: Backside refractive indices
        d_back: Backside thicknesses

    Returns:
        Cost value (MSE)
    """
    # 1. Calc Optical Properties (T)
    if has_back:
        Rf, Tf, Rf_prime, Rb_prime, Tb = tmm_core.calc_spectrum_full_exact(wls, ep, n_layers_T, d_back, n_back_T, n_sub)

        # Exact incoherent: T = (Tf * Tb) / (1 - Rf' * Rb')
        n_wls = len(wls)
        T = np.empty(n_wls, dtype=wls.dtype)

        for i in prange(n_wls):
            d_val = 1.0 - Rf_prime[i] * Rb_prime[i]

            if d_val < 1e-12:
                d_val = 1e-12

            T[i] = (Tf[i] * Tb[i]) / d_val

    else:
        R, T = tmm_core.calculate_RT_no_backside(ep, n_layers_T, n_sub, wls)

    # 2. MSE
    mse, count = compute_mse_vectorized(T, tgt_vals, tgt_weights)

    if count == 0:
        return 1e12

    return mse


def prepare_targets_vectorized(wls: np.ndarray, targets: list) -> tuple[np.ndarray, np.ndarray]:
    """
    Prepares target values and weights for optimization.

    Weights combine user target weight (tgt.w) with spectral quadrature
    Delta ln lambda (trapezoidal) for density-corrected broadband optimization.

    Args:
        wls: Wavelengths array (nm)
        targets: List of Target objects with (lmin, lmax, val, w)

    Returns:
        Tuple of (target_values, weights) arrays
    """
    from certus.utils.certus_index_utils import spectral_rmse_weights

    vals = np.zeros(len(wls), dtype=np.float64)
    weights = np.zeros(len(wls), dtype=np.float64)

    spec_w = spectral_rmse_weights(np.asarray(wls, dtype=np.float64))

    for t in targets:
        if not t.valid():
            continue

        mask = (wls >= t.lmin) & (wls <= t.lmax)

        if not np.any(mask):
            continue

        vals[mask] = t.val
        weights[mask] = spec_w[mask] * t.w

    return vals, weights


def make_cost_function(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    tgt_vals: np.ndarray,
    tgt_weights: np.ndarray,
    min_d: float,
    has_back: bool = False,
    n_back_T: np.ndarray = None,
    d_back: np.ndarray = None,
):
    """
    Factory to create a cost function with proper dtype casting.

    Args:
        wls: Wavelengths (nm)
        n_layers_T: Refractive indices (n_wls, n_layers)
        n_sub: Substrate RI
        tgt_vals: Target transmission values
        tgt_weights: Weights
        min_d: Minimum thickness constraint
        has_back: Enable backside calculation
        n_back_T: Backside RIs (if has_back)
        d_back: Backside thicknesses (if has_back)

    Returns:
        Cost function callable(ep: ndarray) -> float
    """
    # TMM arrays: c128/f64 for full double precision
    wls_f64 = np.ascontiguousarray(wls, dtype=np.float64)
    n_layers_T_c128 = np.ascontiguousarray(n_layers_T, dtype=np.complex128)
    n_sub_c128 = np.ascontiguousarray(n_sub, dtype=np.complex128)

    # Targets: f64
    tgt_vals_f64 = np.ascontiguousarray(tgt_vals, dtype=np.float64)
    tgt_weights_f64 = np.ascontiguousarray(tgt_weights, dtype=np.float64)

    if has_back:
        n_back_T_c128 = np.ascontiguousarray(n_back_T, dtype=np.complex128)
        d_back_f64 = np.ascontiguousarray(d_back, dtype=np.float64)
    else:
        n_back_T_c128 = np.zeros((len(wls), 0), dtype=np.complex128)
        d_back_f64 = np.zeros(0, dtype=np.float64)

    def cost_func(ep: np.ndarray) -> float:
        ep_f64 = np.ascontiguousarray(ep, dtype=np.float64)

        return cost_numba_fast(
            ep_f64,
            n_layers_T_c128,
            n_sub_c128,
            wls_f64,
            tgt_vals_f64,
            tgt_weights_f64,
            min_d,
            has_back,
            n_back_T_c128,
            d_back_f64,
        )

    return cost_func
