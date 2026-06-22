import ast

source_file = "certus/physics/certus_strat_kernels.py"

groups = {
    "math": [
        "_calc_T_from_matrix",
        "_calc_T_added_layer",
        "check_extrema_proximity",
        "calculate_extrema_distances",
        "fit_parabola_vertex_3points",
        "check_extrema_proximity_batch",
        "_seeded_noise_sample",
        "validate_backside_real_clues",
        "_solve_quadratic_target"
    ],
    "dp": [
        "_compute_valid_blocks_kernel",
        "_dp_kernel"
    ],
    "growth": [
        "simulate_growth_kernel",
        "compute_T_front_at_layer",
        "prepare_dynamics_data_kernel",
        "compute_dynamics_kernel",
        "update_run_states_kernel",
        "calculate_detailed_growth"
    ],
    "nucleation": [
        "rank_nucleation_candidates_kernel",
        "find_nucleation_adaptive_kernel"
    ],
    "batch": [
        "validate_wavelengths_batch",
        "simulate_stack_robustness_batch",
        "compute_batch_rmse",
        "precompute_matrix_cache_kernel",
        "_calculate_RT_HL_single_point",
        "calculate_RT_batch_kernel"
    ]
}

# The Numba decorators require explicit import
header = """import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001
"""

with open(source_file, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

imports_map = {
    "math": "",
    "dp": "from .certus_strat_math import check_extrema_proximity, _calc_T_from_matrix, _calc_T_added_layer",
    "growth": "from .certus_strat_math import check_extrema_proximity, calculate_extrema_distances, fit_parabola_vertex_3points, _solve_quadratic_target, _calc_T_from_matrix, _calc_T_added_layer",
    "nucleation": "from .certus_strat_math import _solve_quadratic_target, _calc_T_added_layer\nfrom .certus_strat_growth import compute_T_front_at_layer",
    "batch": "from .certus_strat_math import check_extrema_proximity_batch, _calc_T_from_matrix, _calc_T_added_layer\nfrom .certus_strat_growth import simulate_growth_kernel"
}

files_content = {k: header + imports_map[k] + "\n\n" for k in groups}

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        name = node.name
        found = False
        for g, funcs in groups.items():
            if name in funcs:
                files_content[g] += ast.unparse(node) + "\n"
                found = True
                break
        if not found:
            print(f"WARNING: Function {name} not assigned to any group!")

for g, content in files_content.items():
    with open(f"certus/physics/certus_strat_{g}.py", "w", encoding="utf-8") as f:
        f.write(content)

print("Split completed.")
