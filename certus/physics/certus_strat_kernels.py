# Facade for CERTUS STRAT KERNELS
# This module exposes the decoupled internal modules to maintain public API compatibility.

from .certus_strat_math import (
    check_extrema_proximity,
    calculate_extrema_distances,
    fit_parabola_vertex_3points,
    check_extrema_proximity_batch,
    _seeded_noise_sample,
    validate_backside_real_clues,
    _solve_quadratic_target,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    _calc_T_from_matrix,
    _calc_T_added_layer
)

from .certus_strat_dp import (
    _compute_valid_blocks_kernel,
    _dp_kernel
)

from .certus_strat_growth import (
    simulate_growth_kernel,
    compute_T_front_at_layer,
    prepare_dynamics_data_kernel,
    compute_dynamics_kernel,
    update_run_states_kernel,
    calculate_detailed_growth
)

from .certus_strat_nucleation import (
    rank_nucleation_candidates_kernel,
    find_nucleation_adaptive_kernel
)

from .certus_strat_batch import (
    validate_wavelengths_batch,
    simulate_stack_robustness_batch,
    compute_batch_rmse,
    precompute_matrix_cache_kernel,
    _calculate_RT_HL_single_point,
    calculate_RT_batch_kernel
)

__all__ = [
    "check_extrema_proximity",
    "calculate_extrema_distances",
    "fit_parabola_vertex_3points",
    "check_extrema_proximity_batch",
    "_seeded_noise_sample",
    "validate_backside_real_clues",
    "_solve_quadratic_target",
    "NON_MONOTONIC_MODE_ATTENUATE",
    "NON_MONOTONIC_MODE_REJECT",
    "K_MAX_LAYER_BACKSIDE",
    "K_MAX_SUBSTRATE_BACKSIDE",
    "_calc_T_from_matrix",
    "_calc_T_added_layer",
    "_compute_valid_blocks_kernel",
    "_dp_kernel",
    "simulate_growth_kernel",
    "compute_T_front_at_layer",
    "prepare_dynamics_data_kernel",
    "compute_dynamics_kernel",
    "update_run_states_kernel",
    "calculate_detailed_growth",
    "rank_nucleation_candidates_kernel",
    "find_nucleation_adaptive_kernel",
    "validate_wavelengths_batch",
    "simulate_stack_robustness_batch",
    "compute_batch_rmse",
    "precompute_matrix_cache_kernel",
    "_calculate_RT_HL_single_point",
    "calculate_RT_batch_kernel"
]