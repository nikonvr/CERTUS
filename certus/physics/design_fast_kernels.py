"""Fast DESIGN kernels (numba), one import point for the three modules that hold them.

1. `design_fast_normal`: real `float64` characteristic matrices for lossless or weak-extinction stacks
   (`k <= k_real_threshold`, ALG-30) and the normal-incidence backside with precomputed `(Rb', Tb)` (ALG-25).
2. `design_fast_oblique`: oblique incidence with precomputed admittances and phase factors (ALG-08).
3. `design_fast_gauss_newton`: bounded Gauss-Newton / Levenberg-Marquardt on the residuals (ALG-07).

The reflection amplitudes come from `certus_opt_tmm.reflection_amplitudes` (CLAUDE.md, prohibition 7).
"""

from certus.physics.design_fast_gauss_newton import gauss_newton_refine_normal
from certus.physics.design_fast_normal import (
    compute_gradient_backside_cached_fast,
    compute_gradient_lossless_backside_fast,
    compute_gradient_lossless_front_fast,
    cost_lossless_backside_fast,
    cost_lossless_front_fast,
    prepare_normal_fast_context,
)
from certus.physics.design_fast_oblique import (
    compute_oblique_backside_contrib_precomputed,
    compute_oblique_gradient_contrib_precomputed,
    precompute_oblique_optical_terms,
)

__all__ = [
    "compute_gradient_backside_cached_fast",
    "compute_gradient_lossless_backside_fast",
    "compute_gradient_lossless_front_fast",
    "compute_oblique_backside_contrib_precomputed",
    "compute_oblique_gradient_contrib_precomputed",
    "cost_lossless_backside_fast",
    "cost_lossless_front_fast",
    "gauss_newton_refine_normal",
    "precompute_oblique_optical_terms",
    "prepare_normal_fast_context",
]
