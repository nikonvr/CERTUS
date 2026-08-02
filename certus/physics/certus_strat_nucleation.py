import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001
from .certus_strat_math import _solve_quadratic_target, _calc_T_added_layer, _seeded_noise_sample
from .certus_strat_growth import compute_T_front_at_layer, simulate_growth_kernel


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def rank_nucleation_candidates_kernel(
    candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_vals: np.ndarray,
    nL_vals: np.ndarray,
    nSub_vals: np.ndarray,
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    mc_runs: int,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel to rank candidate wavelengths for nucleation search.

    Replaces the sequential 'pre-ranking' loop in find_robust_nucleation_wavelength_adaptive.

    NOTE (Numba/runtime):

    Random sampling is generated inside the jitted kernel for performance.

    This is not an independent physics model: STRAT passes `use_gaussian=True`

    in production, and this kernel follows that policy.

    """
    n_cand = len(candidates)
    scores = np.zeros(n_cand, dtype=np.float64)
    for i in prange(n_cand):
        wl = candidates[i]
        nH = nH_vals[i]
        nL = nL_vals[i]
        nSub = nSub_vals[i]
        cumulative_sq_error = 0.0
        for run_idx in range(mc_runs):
            noise_vec = np.zeros(min_size, dtype=np.float64)
            for j in range(min_size):
                raw_j = _seeded_noise_sample(
                    seed_base=seed_base, group_idx=i, run_idx=run_idx, elem_idx=j, gaussian=use_gaussian
                )
                noise_vec[j] = raw_j * noise_pct
            current_stack = np.zeros(min_size, dtype=np.float64)
            for j in range(min_size):
                th, _ = simulate_growth_kernel(
                    p_thick_nominal,
                    j,
                    current_stack[:j],
                    wl,
                    nH,
                    nL,
                    nSub,
                    offset_val,
                    noise_vec[j],
                    factor_val,
                    non_monotonic_mode,
                )
                current_stack[j] = th
                cumulative_sq_error += (th - p_thick_nominal[j]) ** 2
        scores[i] = np.sqrt(cumulative_sq_error / (mc_runs * min_size))
    return scores


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def find_nucleation_adaptive_kernel(
    valid_candidates: np.ndarray,
    p_thick_nominal: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    noise_pct: float,
    offset_val: float,
    factor_val: float,
    min_size: int,
    max_size: int,
    mc_runs: int,
    degradation_threshold: float,
    max_rmse_per_layer: float,
    use_gaussian: bool = True,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    seed_base: int = 0,
):
    """

    Parallel kernel for adaptive nucleation Search.

    Optimizes the triple loop (candidates x sizes x mc_runs).

    NOTE (Numba/runtime):

    Noise generation is in-kernel by design for performance and to avoid Python

    allocation overhead in inner loops. STRAT production calls enforce gaussian mode.

    """
    n_cand = len(valid_candidates)
    results_size = np.zeros(n_cand, dtype=np.int32)
    results_rmse = np.zeros(n_cand, dtype=np.float64)
    for i_cand in prange(n_cand):
        nH = nH_arr[i_cand]
        nL = nL_arr[i_cand]
        nSub = nSub_arr[i_cand]
        wl = valid_candidates[i_cand]
        prev_rmse_metric = 0.0
        last_valid_size = 0
        final_rmse = 0.0
        rmse_floor = 0.05
        for size in range(min_size, max_size + 1):
            cumulative_sq_error = 0.0
            for run_idx in range(mc_runs):
                noise_vec = np.zeros(size, dtype=np.float64)
                for i in range(size):
                    raw_i = _seeded_noise_sample(
                        seed_base=seed_base, group_idx=i_cand + size, run_idx=run_idx, elem_idx=i, gaussian=use_gaussian
                    )
                    noise_vec[i] = raw_i * noise_pct
                current_stack = np.zeros(size, dtype=np.float64)
                for i in range(size):
                    th, _ = simulate_growth_kernel(
                        p_thick_nominal,
                        i,
                        current_stack[:i],
                        wl,
                        nH,
                        nL,
                        nSub,
                        offset_val,
                        noise_vec[i],
                        factor_val,
                        non_monotonic_mode,
                    )
                    current_stack[i] = th
                    cumulative_sq_error += (th - p_thick_nominal[i]) ** 2
            rmse_total = np.sqrt(cumulative_sq_error / (mc_runs * size))
            if rmse_total > max_rmse_per_layer:
                break
            if size > min_size:
                ratio = rmse_total / max(prev_rmse_metric, rmse_floor)
                if ratio > degradation_threshold:
                    break
            last_valid_size = size
            prev_rmse_metric = rmse_total
            final_rmse = rmse_total
        results_size[i_cand] = last_valid_size
        results_rmse[i_cand] = final_rmse
    return (results_size, results_rmse)
