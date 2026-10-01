"""CERTUS Physics Package
======================
Part of CERTUS Suite (Opus 4.6 HPC Engine)

All physics kernels live in _certus_physics_impl.py (Numba JIT).
This package re-exports them plus auxiliary data modules:
- structures.py: Dataclasses (Layer, Target, Sample, PGlobalConfig)
- materials_data.py: Silicon optical constants (loaded from clues.xlsx -> Si-substrate)"""


import sys
from pathlib import Path

# Add parent directory to path (for _certus_physics_impl import)
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# =============================================================================
# CORE ENGINE (Single Source of Truth)
# =============================================================================
from certus.core._certus_physics_impl import (  # noqa: F401
    CRASH_LEVEL_UNREACHABLE,
    CRASH_NON_MONOTONIC,
    # Depots non terminables, decomposes par cause (les trois questions du juge de paix)
    CRASH_SENTINEL_MIN,
    CRASH_SENTINEL_UNIT,
    CRASH_TP_MISCOUNT,
    # Slit-bias profiles: the sweep span and the node count must be the SAME object on
    # both sides, or the profile would be sampled on a different axis than it is read on.
    D_SCAN_VAL,
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    MARGIN_NONE,
    MAX_LOOKBACK_VAL,
    # Non-monotonic handling modes
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    PHOTOMETRIC_CURVATURE_AMP,
    SELLMEIER_COEFFS_BY_ID,
    SLIT_PROFILE_NODES,
    SUBSTRATE_MIN_LAMBDA_BY_ID,
    # Data Structures
    Layer,
    # Material Database
    Material,
    MaterialDatabase,
    NKCache,
    ObliqueTarget,
    PGlobalConfig,
    # Optimization
    PGlobalOptimizer,
    Sample,
    SingleLinkageClusterer,
    SplineBasisCache,
    Target,
    TLUParameters,
    _calculate_RT_absorbing_sub_single,
    # Gradient internals (used by INDEX/METAL modules)
    _compute_epsilon1_gradient_kernel,
    _compute_epsilon2_gradient_kernel,
    _compute_gradient_analytic_kernel,
    _compute_index_cost_gradient_kernel,
    _compute_ir_global_cost_gradient_kernel,
    _compute_phase2_derivatives_kernel,
    _compute_single_layer_sensitivity_array,
    _compute_single_layer_sensitivity_kernel,
    _compute_tlu_derivatives_kernel,
    # STRAT DP kernels (used by CERTUS_STRAT cost/DP path)
    _compute_valid_blocks_kernel,
    _dp_kernel,
    apply_exact_backside_combination,
    arange_inclusive,
    batch_single_layer_RT_mse,
    batch_single_layer_T_mse,
    calc_qwot,
    calc_rmse,
    calc_spectrum_front,
    calc_spectrum_front_wrapper,
    calc_spectrum_full,
    calc_spectrum_full_exact,
    calc_spectrum_full_exact_wrapper,
    calc_spectrum_full_oblique_exact,
    calc_spectrum_full_wrapper,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    calculate_bare_substrate_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_RT,
    calculate_bare_substrate_T_absorbing,
    calculate_detailed_growth,
    calculate_extrema_distances,
    calculate_level_margins_to_extrema,
    calculate_reflectance_bilayer_vectorized,
    calculate_reflection_array,
    calculate_reflection_infinite_substrate_single,
    calculate_RT_batch_kernel,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_single_layer_backside_array,
    calculate_RT_vectorized_real,
    calculate_RT_vectorized_real_HL,
    calculate_RTRback_incoherent_vectorized,
    calculate_single_interface_R,
    calculate_transmission_single,
    check_extrema_proximity,
    check_extrema_proximity_batch,
    check_level_margin_batch,
    clip_to_bounds,
    compute_batch_rmse,
    compute_critical_distance,
    compute_dT_dd_kernel,
    compute_dynamics_kernel,
    # Gradients
    compute_gradient_all_layers_analytic,
    compute_metal_bilayer_gradient_analytic,
    compute_mse_vectorized,
    compute_oblique_backside_bundle_analytic,
    compute_oblique_gradient_contrib_analytic,
    compute_oblique_rt_and_grads_analytic,
    compute_T_front_at_layer,
    compute_T_front_profile,
    # TMM
    compute_TMM_generic,
    corridor_wl_range,
    # Cost Functions
    cost_numba_fast,
    delta_e_2000,
    detect_turning_points,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
    fast_clustering_kernel,
    find_nucleation_adaptive_kernel,
    get_n_frosted_glass_array,
    get_n_substrate_array_by_id,
    get_nk_cauchy,
    get_nk_cauchy_simple,
    get_nk_cauchy_wrapper,
    get_nk_from_spline,
    get_refractive_clues_vectorized,
    get_refractive_index,
    # Utilities
    init_thickness,
    lab_to_rgb,
    make_cost_function,
    needle_scan_cached,
    next_turning_point_after,
    oblique_front_char_matrix_single,
    oblique_front_rt_from_char_matrix_nsub_real,
    precompute_matrix_cache_kernel,
    # STRAT Kernels (Advanced)
    prepare_dynamics_data_kernel,
    prepare_targets_vectorized,
    rank_nucleation_candidates_kernel,
    # Optical Models
    sellmeier_n_array,
    # STRAT Kernels
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    trim_worst_only,
    update_run_states_kernel,
    # Backside Validation
    validate_backside_real_clues,
    validate_wavelengths_batch,
    warmup_physics,
    # Colorimetry
    xyz_from_spectrum,
    xyz_to_lab,
)
from certus.physics.certus_strat_machine import MachineModel  # noqa: F401

# =============================================================================
# AUXILIARY MODULES (not in _impl - unique functionality)
# =============================================================================
# Silicon optical constants - loaded from clues.xlsx -> Si-substrate (Single Source of Truth)
from .materials_data import (  # noqa: F401
    SI_K_DATA,
    SI_N_DATA,
    SI_WAVELENGTH_NM,
    get_nk_si,
)
