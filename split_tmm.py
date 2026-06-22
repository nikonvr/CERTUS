import os
import re
import ast

def get_ast_function_names(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    tree = ast.parse(content)
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]

# Target files mapping
groups = {
    "certus_tmm_substrate.py": [
        "calculate_bare_substrate_R",
        "calculate_bare_substrate_RT",
        "calculate_single_interface_R",
        "calculate_bare_substrate_R_absorbing",
        "calculate_bare_substrate_T_absorbing"
    ],
    "certus_tmm_single_layer.py": [
        "calculate_RT_single_layer_single",
        "calculate_reflection_array",
        "calculate_transmission_single",
        "calculate_reflection_single",
        "calculate_transmission_array",
        "calculate_RT_single_layer_backside_array",
        "batch_single_layer_T_mse",
        "batch_single_layer_RT_mse",
        "_calculate_RT_absorbing_sub_single",
        "calculate_RT_single_layer_absorbing_substrate_array"
    ],
    "certus_tmm_matrix.py": [
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
        "calc_spectrum_full_exact_wrapper"
    ],
    "certus_tmm_backside.py": [
        "_apply_exact_backside_generic",
        "apply_exact_backside_combination"
    ],
    "certus_tmm_oblique.py": [
        "_calc_spectrum_oblique_parallel",
        "calc_spectrum_oblique_vectorized",
        "calc_spectrum_oblique_backside_vectorized",
        "_oblique_stack_rt_single",
        "oblique_front_char_matrix_single",
        "oblique_front_rt_from_char_matrix_nsub_real",
        "calc_spectrum_full_oblique_exact"
    ],
    "certus_tmm_hl.py": [
        "_calculate_RT_HL_core",
        "calculate_RT_vectorized_real_HL"
    ]
}

source_file = "certus/physics/certus_tmm_core.py"
target_dir = "certus/physics"

# Read original
with open(source_file, "r", encoding="utf-8") as f:
    original_code = f.read()

# Use regex to extract functions with decorators to avoid unparse destroying decorators formatting
def extract_function_text(code, func_name):
    # Regex to capture decorators and the function body
    pattern = r"(?:(?:^[ \t]*@.*?\n)+)?^[ \t]*def\s+" + re.escape(func_name) + r"\b.*?^(?=\S)(?!\s*#)"
    # We will compile with DOTALL and MULTILINE. The positive lookahead ^(?=\S) matches the next top-level statement or end of file
    match = re.search(r"(?:^[ \t]*@.*?\n)*^[ \t]*def\s+" + re.escape(func_name) + r"\b.*?(?=^[ \t]*@|^[ \t]*def|\Z)", code, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(0).strip()
    else:
        # Fallback to ast if regex fails
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return ast.unparse(node)
        return ""

header = """import numpy as np
from numba import njit, prange
import math
from typing import *
from certus.physics.certus_opt_tmm import compute_TMM_generic, compute_RT_from_matrix
from certus.core.certus_core import TWO_PI

SMALL_EPSILON = 1e-12

"""

# Inter-module imports.
imports_map = {
    "certus_tmm_substrate.py": "",
    "certus_tmm_single_layer.py": "from .certus_tmm_substrate import calculate_single_interface_R, calculate_bare_substrate_R_absorbing, calculate_bare_substrate_T_absorbing",
    "certus_tmm_matrix.py": "from .certus_tmm_substrate import calculate_bare_substrate_R, calculate_bare_substrate_RT, calculate_single_interface_R",
    "certus_tmm_backside.py": "from .certus_tmm_substrate import calculate_bare_substrate_R_absorbing, calculate_bare_substrate_T_absorbing, calculate_bare_substrate_R, calculate_bare_substrate_RT",
    "certus_tmm_oblique.py": "from .certus_tmm_substrate import calculate_single_interface_R\nfrom .certus_tmm_backside import _apply_exact_backside_generic, apply_exact_backside_combination",
    "certus_tmm_hl.py": "from .certus_tmm_substrate import calculate_bare_substrate_R, calculate_bare_substrate_RT"
}

for group_file, func_names in groups.items():
    print(f"Generating {group_file}...")
    out_path = os.path.join(target_dir, group_file)
    
    file_content = header
    if imports_map[group_file]:
        file_content += imports_map[group_file] + "\n\n"
        
    for func in func_names:
        func_text = extract_function_text(original_code, func)
        file_content += func_text + "\n\n"
        
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(file_content)

print("Split completed.")
