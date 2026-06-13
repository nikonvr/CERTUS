import ast
from pathlib import Path

def get_node_bounds(tree, names, is_class=False):
    bounds = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_class:
            if node.name in names:
                start = node.lineno - 1
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                end = node.end_lineno
                bounds.append((start, end, node.name))
        elif isinstance(node, ast.ClassDef) and is_class:
            if node.name in names:
                start = node.lineno - 1
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                end = node.end_lineno
                bounds.append((start, end, node.name))
    return bounds

def extract():
    src_path = Path('certus/spline/spline_profile_corridors.py')
    lines = src_path.read_text(encoding='utf-8').splitlines()
    tree = ast.parse("\n".join(lines))
    
    # 1. Logger
    loggers = ['log_coaching_uncertainty_parameter_guide', 'log_coaching_corridor_pipeline_skip_empty', '_log_coaching_corridor_outcome', '_log_coaching_corridor_failure', '_log_coaching_bootstrap_outcome', '_log_coaching_reg_sensitivity_outcome', '_log_corridor_base_geometry', '_log_corridor_envelope_diagnostics', '_log_corridor_start_config']
    logger_bounds = get_node_bounds(tree, loggers, is_class=False)
    logger_lines = []
    for s, e, n in sorted(logger_bounds, key=lambda x: x[0]):
        logger_lines.extend(lines[s:e])
    logger_imports = "from typing import *\nimport logging\nimport numpy as np\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_corridor_config import *\nfrom certus.spline.certus_index_spline_core import *\n\nlog = logging.getLogger('CERTUS')\n\n"
    Path('certus/spline/certus_corridor_logger.py').write_text(logger_imports + "\n".join(logger_lines), encoding='utf-8')
    
    # 2. Bootstrap
    bootstraps = ['_bootstrap_single_replicate', '_bootstrap_pool_entry', '_resample_residuals_block']
    boot_bounds = get_node_bounds(tree, bootstraps, is_class=False)
    boot_lines = []
    for s, e, n in sorted(boot_bounds, key=lambda x: x[0]):
        boot_lines.extend(lines[s:e])
    boot_imports = "from typing import *\nimport numpy as np\nimport logging\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_corridor_config import *\nfrom certus.spline.certus_corridor_fitter import *\nfrom certus.spline.certus_index_spline_core import *\n\nlog = logging.getLogger('CERTUS')\n\n"
    Path('certus/spline/certus_corridor_bootstrap.py').write_text(boot_imports + "\n".join(boot_lines), encoding='utf-8')

    # 3. Utils
    utils = ['_expand_corridor_envelope_with_reported_nk', '_robust_sigma_from_mad', '_estimate_adaptive_rmse_abs_tolerance', 'widen_corridor_envelope_to_include_nk_in_result', 'enforce_min_k_corridor_half_width', '_pick_rmse_reference_for_profile', '_extract_knots_and_nodes_from_result', '_spectral_rmse_at_packed_nodes', '_x_nodes0_from_mesh_x_if_consistent', '_bounds_for_nodes_only', '_hetero_sigma_masked_from_base', '_chi2_masked_constant_sigma', 'quick_pwlnk_refit_result_dict', '_detect_corridor_spike']
    utils_bounds = get_node_bounds(tree, utils, is_class=False)
    utils_lines = []
    for s, e, n in sorted(utils_bounds, key=lambda x: x[0]):
        utils_lines.extend(lines[s:e])
    utils_imports = "from typing import *\nimport numpy as np\nimport logging\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_corridor_config import *\nfrom certus.spline.certus_corridor_fitter import *\nfrom certus.spline.certus_index_spline_core import *\nfrom certus.spline.spline_objective import build_spline_objective_masked_grid, nk_from_x_pwlnk\n\nlog = logging.getLogger('CERTUS')\n\n"
    Path('certus/spline/certus_corridor_utils.py').write_text(utils_imports + "\n".join(utils_lines), encoding='utf-8')
    
    # 4. Remove from original safely
    to_remove = set()
    for s, e, n in logger_bounds + boot_bounds + utils_bounds:
        for i in range(s, e):
            to_remove.add(i)
            
    final_lines = []
    added_imports = False
    
    for idx, l in enumerate(lines):
        if idx not in to_remove:
            final_lines.append(l)
            if "from certus.spline.certus_corridor_exploration import *" in l and not added_imports:
                final_lines.append("from certus.spline.certus_corridor_logger import *")
                final_lines.append("from certus.spline.certus_corridor_bootstrap import *")
                final_lines.append("from certus.spline.certus_corridor_utils import *")
                added_imports = True
                
    src_path.write_text("\n".join(final_lines), encoding='utf-8')
    print("Part 2 extraction completed cleanly.")

if __name__ == '__main__':
    extract()
