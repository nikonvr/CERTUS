"""CERTUS Physics Package
======================
Part of CERTUS Suite (Opus 4.6 HPC Engine)

All physics kernels live in _certus_physics_impl.py (Numba JIT).
This package re-exports them plus auxiliary data modules:
- structures.py: Dataclasses (Layer, Target, Sample, PGlobalConfig)
- materials_data.py: Silicon optical constants (loaded from clues.xlsx -> Si-substrate)"""

import os
import sys
from pathlib import Path

# Add parent directory to path (for _certus_physics_impl import)
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# =============================================================================
# CORE ENGINE (Single Source of Truth)
# =============================================================================
from _certus_physics_impl import (
    # Data Structures
    Layer,
    Target,
    ObliqueTarget,
    TLUParameters,
    Sample,
    PGlobalConfig,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATE_MIN_LAMBDA_BY_ID,
    # Optical Models
    sellmeier_n_array,
    get_nk_cauchy,
    get_nk_cauchy_wrapper,
    get_nk_cauchy_simple,
    epsilon2_TLU_array,
    epsilon1_TL_analytic,
    epsilon_to_nk,
    get_n_substrate_array_by_id,
    get_n_frosted_glass_array,
    # TMM
    compute_TMM_generic,
    calculate_transmission_single,
    calculate_transmission_array,
    calculate_reflection_single,
    calculate_reflection_array,
    calculate_RT_single_layer_single,
    calculate_RT_single_layer_backside_array,
    calculate_R_substrate_array,
    calculate_T_substrate_array,
    calculate_R_substrate_absorbing_array,
    calculate_T_substrate_absorbing_array,
    calculate_RT_single_layer_absorbing_substrate_array,
    calculate_RT_vectorized_real,
    calculate_RT_vectorized_real_HL,
    calculate_RTRback_incoherent_vectorized,
    apply_exact_backside_combination,
    calculate_R_frosted_glass_reference,
    calculate_reflection_infinite_substrate_array,
    calculate_reflection_infinite_substrate_single,
    calculate_reflectance_bilayer_vectorized,
    calc_spectrum_front,
    calc_spectrum_front_wrapper,
    calc_spectrum_full,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact,
    calc_spectrum_full_exact_wrapper,
    calc_spectrum_oblique_vectorized,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_full_oblique_exact,
    oblique_front_char_matrix_single,
    oblique_front_rt_from_char_matrix_nsub_real,
    compute_oblique_backside_bundle_analytic,
    compute_oblique_rt_and_grads_analytic,
    # Cost Functions
    cost_numba_fast,
    needle_scan_cached,
    make_cost_function,
    calc_rmse,
    prepare_targets_vectorized,
    # Backside Validation
    validate_backside_real_clues,
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    # Gradients
    compute_gradient_all_layers_analytic,
    compute_oblique_gradient_contrib_analytic,
    compute_metal_bilayer_gradient_analytic,
    # Optimization
    PGlobalOptimizer,
    SingleLinkageClusterer,
    clip_to_bounds,
    compute_mse_vectorized,
    fast_clustering_kernel,
    compute_critical_distance,
    # Colorimetry
    xyz_from_spectrum,
    xyz_to_lab,
    lab_to_rgb,
    delta_e_2000,
    # STRAT Kernels
    simulate_growth_kernel,
    compute_dynamics_kernel,
    calculate_detailed_growth,
    check_extrema_proximity,
    validate_wavelengths_batch,
    trim_worst_only,
    simulate_stack_robustness_batch,
    compute_batch_rmse,
    compute_T_front_at_layer,
    # Non-monotonic handling modes
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    # STRAT Kernels (Advanced)
    prepare_dynamics_data_kernel,
    check_extrema_proximity_batch,
    calculate_extrema_distances,
    precompute_matrix_cache_kernel,
    find_nucleation_adaptive_kernel,
    rank_nucleation_candidates_kernel,
    update_run_states_kernel,
    calculate_RT_batch_kernel,
    # Material Database
    Material,
    MaterialDatabase,
    NKCache,
    get_nk_from_spline,
    SplineBasisCache,
    # Utilities
    init_thickness,
    calc_qwot,
    arange_inclusive,
    warmup_physics,
    get_refractive_index,
    get_refractive_clues_vectorized,
    # Gradient internals (used by INDEX/METAL modules)
    _compute_epsilon1_gradient_kernel,
    _compute_epsilon2_gradient_kernel,
    _compute_gradient_analytic_kernel,
    _compute_index_cost_gradient_kernel,
    _compute_single_layer_sensitivity_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_phase2_derivatives_kernel,
    _compute_ir_global_cost_gradient_kernel,
    # STRAT DP kernels (used by CERTUS_STRAT cost/DP path)
    _compute_valid_blocks_kernel,
    _dp_kernel,
)

# =============================================================================
# AUXILIARY MODULES (not in _impl - unique functionality)
# =============================================================================


# Silicon optical constants - loaded from clues.xlsx -> Si-substrate (Single Source of Truth)
from .materials_data import (
    get_nk_si,
    SI_WAVELENGTH_NM,
    SI_N_DATA,
    SI_K_DATA,
)
