"""
CERTUS Gradient Optimization - Compatibility Layer

This module maintains backward compatibility after refactoring into:
- gradient_utils.py
- gradient_analytic.py
- gradient_oblique.py
- gradient_metal.py

All functions are re-exported here for existing code that imports from certus_opt_gradients.
"""

# Re-export from gradient_utils
from certus.physics.gradient_utils import (
    SMALL_EPSILON,
    compute_mse_vectorized,
    cost_numba_fast,
    prepare_targets_vectorized,
    make_cost_function,
)

# Re-export from gradient_analytic
from certus.physics.gradient_analytic import (
    _compute_epsilon2_gradient_kernel,
    _compute_epsilon1_gradient_kernel,
    _compute_tlu_derivatives_kernel,
    _compute_single_layer_sensitivity_kernel,
    _compute_single_layer_sensitivity_array,
    _compute_index_cost_gradient_kernel,
    _compute_gradient_analytic_kernel,
    compute_gradient_all_layers_analytic,
)

# Re-export from gradient_oblique
from certus.physics.gradient_oblique import (
    _compute_oblique_gradient_contrib_kernel,
    compute_oblique_gradient_contrib_analytic,
    _compute_oblique_rt_and_grads_kernel,
    compute_oblique_rt_and_grads_analytic,
    compute_oblique_rt_pair_and_grads_analytic,
    compute_oblique_backside_bundle_analytic,
)

# Re-export from gradient_metal
from certus.physics.gradient_metal import (
    _compute_metal_tmm_gradient_kernel,
    compute_metal_bilayer_gradient_analytic,
)

__all__ = [
    # Utils
    "SMALL_EPSILON",
    "compute_mse_vectorized",
    "cost_numba_fast",
    "prepare_targets_vectorized",
    "make_cost_function",
    # Analytic
    "_compute_epsilon2_gradient_kernel",
    "_compute_epsilon1_gradient_kernel",
    "_compute_tlu_derivatives_kernel",
    "_compute_single_layer_sensitivity_kernel",
    "_compute_single_layer_sensitivity_array",
    "_compute_index_cost_gradient_kernel",
    "_compute_gradient_analytic_kernel",
    "compute_gradient_all_layers_analytic",
    # Oblique
    "_compute_oblique_gradient_contrib_kernel",
    "compute_oblique_gradient_contrib_analytic",
    "_compute_oblique_rt_and_grads_kernel",
    "compute_oblique_rt_and_grads_analytic",
    "compute_oblique_rt_pair_and_grads_analytic",
    "compute_oblique_backside_bundle_analytic",
    # Metal
    "_compute_metal_tmm_gradient_kernel",
    "compute_metal_bilayer_gradient_analytic",
]
