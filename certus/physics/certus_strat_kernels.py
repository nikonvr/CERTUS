# Facade for CERTUS STRAT KERNELS
# This module exposes the decoupled internal modules to maintain public API compatibility.

from .certus_strat_math import (
    check_extrema_proximity,
    calculate_extrema_distances,
    fit_parabola_vertex_3points,
    check_extrema_proximity_batch,
    calculate_level_margins_to_extrema,
    check_level_margin_batch,
    MARGIN_NONE,
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
    CRASH_LEVEL_UNREACHABLE,
    CRASH_NON_MONOTONIC,
    CRASH_SENTINEL_MIN,
    CRASH_SENTINEL_UNIT,
    CRASH_TP_MISCOUNT,
    D_SCAN_VAL,
    MAX_LOOKBACK_VAL,
    PHOTOMETRIC_CURVATURE_AMP,
    SLIT_PROFILE_NODES,
    detect_turning_points,
    next_turning_point_after,
    simulate_growth_kernel,
    compute_T_front_at_layer,
    compute_T_front_profile,
    compute_dT_dd_kernel,
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
    corridor_wl_range,
    precompute_matrix_cache_kernel,
    _calculate_RT_HL_single_point,
    calculate_RT_batch_kernel
)

from .certus_strat_machine import (
    MachineModel,
    OMS5100_DEFAULT_READING_NOISE_PCT,
    OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM,
    OMS5100_DEFAULT_5_SIGMA_FACTOR,
)

__all__ = [
    "CRASH_LEVEL_UNREACHABLE",
    "CRASH_NON_MONOTONIC",
    "CRASH_SENTINEL_MIN",
    "CRASH_SENTINEL_UNIT",
    "CRASH_TP_MISCOUNT",
    "D_SCAN_VAL",
    "K_MAX_LAYER_BACKSIDE",
    "K_MAX_SUBSTRATE_BACKSIDE",
    "MARGIN_NONE",
    "MAX_LOOKBACK_VAL",
    "NON_MONOTONIC_MODE_ATTENUATE",
    "NON_MONOTONIC_MODE_REJECT",
    "OMS5100_DEFAULT_5_SIGMA_FACTOR",
    "OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM",
    "OMS5100_DEFAULT_READING_NOISE_PCT",
    "PHOTOMETRIC_CURVATURE_AMP",
    "SLIT_PROFILE_NODES",
    "MachineModel",
    "_calc_T_added_layer",
    "_calc_T_from_matrix",
    "_calculate_RT_HL_single_point",
    "_compute_valid_blocks_kernel",
    "_dp_kernel",
    "_seeded_noise_sample",
    "_solve_quadratic_target",
    "calculate_RT_batch_kernel",
    "calculate_detailed_growth",
    "calculate_extrema_distances",
    "calculate_level_margins_to_extrema",
    "check_extrema_proximity",
    "check_extrema_proximity_batch",
    "check_level_margin_batch",
    "compute_T_front_at_layer",
    "compute_T_front_profile",
    "compute_batch_rmse",
    "compute_dT_dd_kernel",
    "compute_dynamics_kernel",
    "corridor_wl_range",
    "detect_turning_points",
    "find_nucleation_adaptive_kernel",
    "fit_parabola_vertex_3points",
    "next_turning_point_after",
    "precompute_matrix_cache_kernel",
    "prepare_dynamics_data_kernel",
    "rank_nucleation_candidates_kernel",
    "simulate_growth_kernel",
    "simulate_stack_robustness_batch",
    "update_run_states_kernel",
    "validate_backside_real_clues",
    "validate_wavelengths_batch"
]