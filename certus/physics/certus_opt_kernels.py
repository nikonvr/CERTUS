
from certus.physics.certus_material_db import MaterialDatabase
from certus.physics.certus_opt_tmm import (
    arange_inclusive,
    calculate_reflectance_bilayer_vectorized,
    calculate_reflection_infinite_substrate_single,
    calculate_RTRback_incoherent_vectorized,
    clip_to_bounds,
    compute_RT_from_matrix,
    compute_TMM_generic,
    trim_worst_only,
)
from certus.physics.certus_optimizers import PGlobalOptimizer, SingleLinkageClusterer
from certus.physics.gradient_analytic import (
    _compute_epsilon1_gradient_kernel,
    _compute_epsilon2_gradient_kernel,
    _compute_gradient_analytic_kernel,
    _compute_index_cost_gradient_kernel,
    _compute_single_layer_sensitivity_array,
    _compute_single_layer_sensitivity_kernel,
    _compute_tlu_derivatives_kernel,
    make_cost_function,
    prepare_targets_vectorized,
)
from certus.physics.gradient_metal import (
    _compute_metal_tmm_gradient_kernel,
    compute_metal_bilayer_gradient_analytic,
)
from certus.physics.gradient_oblique import (
    _compute_oblique_rt_and_grads_kernel,
    compute_gradient_all_layers_analytic,
    compute_oblique_gradient_contrib_analytic,
    compute_oblique_rt_and_grads_analytic,
)
from certus.physics.gradient_utils import (
    compute_mse_vectorized,
    cost_numba_fast,
)
