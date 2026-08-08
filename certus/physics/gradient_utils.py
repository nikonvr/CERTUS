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


# fastmath=True implies LLVM flags `nnan` and `ninf`, allowing compiler
# to assume no NaN or Inf exists, silently removing `np.isfinite(...)`.
# FASTMATH_SAFE includes all optimizations EXCEPT nnan/ninf so finiteness guards survive.
FASTMATH_SAFE = {"nsz", "arcp", "contract", "afn", "reassoc"}


@njit(cache=True, fastmath=FASTMATH_SAFE, parallel=True, nogil=True, error_model="numpy")
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


from certus.physics.gradient_analytic import (
    prepare_targets_vectorized,
    make_cost_function,
)

