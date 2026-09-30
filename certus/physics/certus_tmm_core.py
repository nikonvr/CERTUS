# Facade for CERTUS TMM CORE
# This module exposes the decoupled internal modules to maintain public API compatibility.
#
# Numba kernels of other files (certus_strat_batch, gradient_analytic, gradient_utils...) call through these names, and
# Numba freezes what they resolve to into their cached machine code. The cache key (`numba_cache_key`) reads the files
# whose text says numba, so this one does: re-pointing a name here recompiles those kernels
# (tests/unit/test_the_cache_key_covers_what_the_kernels_read.py).

from .certus_tmm_substrate import (
    calculate_bare_substrate_R,
    calculate_bare_substrate_RT,
    calculate_single_interface_R,
    calculate_bare_substrate_R_absorbing,
    calculate_bare_substrate_T_absorbing
)

from .certus_tmm_single_layer import (
    calculate_RT_single_layer_single,
    calculate_reflection_array,
    calculate_transmission_single,
    calculate_reflection_single,
    calculate_transmission_array,
    calculate_RT_single_layer_backside_array,
    batch_single_layer_T_mse,
    batch_single_layer_RT_mse,
    _calculate_RT_absorbing_sub_single,
    calculate_RT_single_layer_absorbing_substrate_array
)

from .certus_tmm_matrix import (
    compute_complex_phase_components,
    compute_TMM_single_point_k0,
    compute_TMM_single_point_k0_exact,
    calculate_RT_with_backside_fused,
    calculate_RT_vectorized_real,
    calculate_RT_no_backside,
    calc_spectrum_front,
    calc_spectrum_full,
    calc_spectrum_full_exact,
    calc_spectrum_front_wrapper,
    calc_spectrum_full_wrapper,
    calc_spectrum_full_exact_wrapper
)

from .certus_tmm_backside import (
    _apply_exact_backside_generic,
    apply_exact_backside_combination
)

from .certus_tmm_oblique import (
    _calc_spectrum_oblique_parallel,
    calc_spectrum_oblique_vectorized,
    calc_spectrum_oblique_backside_vectorized,
    _oblique_stack_rt_single,
    oblique_front_char_matrix_single,
    oblique_front_rt_from_char_matrix_nsub_real,
    calc_spectrum_full_oblique_exact
)

from .certus_tmm_hl import (
    _calculate_RT_HL_core,
    calculate_RT_vectorized_real_HL
)

__all__ = [
    "calculate_bare_substrate_R",
    "calculate_bare_substrate_RT",
    "calculate_single_interface_R",
    "calculate_bare_substrate_R_absorbing",
    "calculate_bare_substrate_T_absorbing",
    "calculate_RT_single_layer_single",
    "calculate_reflection_array",
    "calculate_transmission_single",
    "calculate_reflection_single",
    "calculate_transmission_array",
    "calculate_RT_single_layer_backside_array",
    "batch_single_layer_T_mse",
    "batch_single_layer_RT_mse",
    "_calculate_RT_absorbing_sub_single",
    "calculate_RT_single_layer_absorbing_substrate_array",
    "compute_complex_phase_components",
    "compute_TMM_single_point_k0",
    "compute_TMM_single_point_k0_exact",
    "calculate_RT_with_backside_fused",
    "calculate_RT_vectorized_real",
    "calculate_RT_no_backside",
    "calc_spectrum_front",
    "calc_spectrum_full",
    "calc_spectrum_full_exact",
    "calc_spectrum_front_wrapper",
    "calc_spectrum_full_wrapper",
    "calc_spectrum_full_exact_wrapper",
    "_apply_exact_backside_generic",
    "apply_exact_backside_combination",
    "_calc_spectrum_oblique_parallel",
    "calc_spectrum_oblique_vectorized",
    "calc_spectrum_oblique_backside_vectorized",
    "_oblique_stack_rt_single",
    "oblique_front_char_matrix_single",
    "oblique_front_rt_from_char_matrix_nsub_real",
    "calc_spectrum_full_oblique_exact",
    "_calculate_RT_HL_core",
    "calculate_RT_vectorized_real_HL"
]
