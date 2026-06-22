import ast

tmm_funcs = ['clip_to_bounds', 'compute_TMM_generic', 'compute_RT_from_matrix', 'calculate_RTRback_incoherent_vectorized', 'calculate_reflection_infinite_substrate_single', 'calculate_reflectance_bilayer_vectorized', 'Material', 'get_n_frosted_glass_array', 'arange_inclusive', 'trim_worst_only']

grad_funcs = ['compute_mse_vectorized', 'cost_numba_fast', 'make_cost_function', 'prepare_targets_vectorized', '_compute_epsilon2_gradient_kernel', '_compute_epsilon1_gradient_kernel', '_compute_tlu_derivatives_kernel', '_compute_single_layer_sensitivity_kernel', '_compute_single_layer_sensitivity_array', '_compute_index_cost_gradient_kernel', '_compute_gradient_analytic_kernel', '_compute_oblique_gradient_contrib_kernel', 'compute_oblique_gradient_contrib_analytic', '_compute_oblique_rt_and_grads_kernel', 'compute_oblique_rt_and_grads_analytic', 'compute_oblique_rt_pair_and_grads_analytic', 'compute_oblique_backside_bundle_analytic', 'compute_gradient_all_layers_analytic', '_compute_metal_tmm_gradient_kernel', 'compute_metal_bilayer_gradient_analytic']

needle_funcs = ['needle_scan_cached']

with open('certus_opt_kernels_old_utf8.py', 'r', encoding='utf-8') as f:
    text = f.read()

tree = ast.parse(text)

def get_full_node_text(node):
    if not hasattr(node, 'decorator_list') or not node.decorator_list:
        return ast.get_source_segment(text, node)
    
    start_line = node.decorator_list[0].lineno
    end_line = getattr(node, 'end_lineno', node.lineno)
    lines = text.split('\n')[start_line-1:end_line]
    return '\n'.join(lines)

tmm_code = []
grad_code = []
needle_code = []

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        code = get_full_node_text(node)
        if node.name in tmm_funcs:
            tmm_code.append(code)
        elif node.name in grad_funcs:
            grad_code.append(code)
        elif node.name in needle_funcs:
            needle_code.append(code)

header = """SMALL_EPSILON = 1e-12
import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import WL_DECIMALS, PI, TWO_PI, N_SUPERSTRATE
from dataclasses import dataclass
import certus.physics.certus_tmm_core as tmm_core
from certus.physics.certus_optical_models import (
    get_nk_from_spline, get_nk_cauchy_simple, get_nk_cauchy_wrapper,
    sellmeier_n_array, get_nk_cauchy, epsilon2_TLU_array, epsilon1_TL_analytic, epsilon_to_nk
)
from scipy.interpolate import CubicSpline

"""

with open('certus/physics/certus_opt_tmm.py', 'w', encoding='utf-8') as f:
    f.write(header + '\n\n'.join(tmm_code))

with open('certus/physics/certus_opt_gradients.py', 'w', encoding='utf-8') as f:
    f.write(header + '\n\n'.join(grad_code))

with open('certus/physics/certus_opt_needle.py', 'w', encoding='utf-8') as f:
    f.write(header + '\n\n'.join(needle_code))

print("Regeneration complete!")
