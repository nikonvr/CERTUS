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
    
    # Extract to certus_corridor_orchestrator_utils
    targets = [
        '_best_fit_at_d', '_generate_iso_phase_seed', 'compute_reg_sensitivity_scan',
        '_theoretical_TR_from_base_result', '_manual_grid_tag_base_on_duplicate_discard',
        '_detect_breakpoint', '_run_global_opt_from_breakpoint', '_build_emergency_fit_record',
        '_profile_p0_suspects', '_profile_manual_grid_coverage_audit', '_package_profile_grid_result',
        '_package_corridor_results', '_compute_corridor_rmse_threshold', '_prep_corridor_base_eff',
        '_eval_adaptive_abs_tolerance', '_eval_corridor_threshold_fallback', '_setup_corridor_context'
    ]
    target_classes = ['CorridorProfileContext']
    
    bounds = get_node_bounds(tree, targets, is_class=False) + get_node_bounds(tree, target_classes, is_class=True)
    
    ext_lines = []
    for s, e, n in sorted(bounds, key=lambda x: x[0]):
        ext_lines.extend(lines[s:e])
        
    ext_imports = "from typing import *\nimport numpy as np\nimport logging\nimport threading\nfrom concurrent.futures import ThreadPoolExecutor, as_completed\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\nfrom certus.spline.certus_corridor_config import *\nfrom certus.spline.certus_corridor_fitter import *\nfrom certus.spline.certus_corridor_exploration import *\nfrom certus.spline.certus_corridor_utils import *\nfrom certus.spline.certus_corridor_logger import *\nfrom certus.spline.certus_corridor_bootstrap import *\nfrom certus.spline.spline_objective import build_spline_objective_masked_grid, nk_from_x_pwlnk\nlog = logging.getLogger('CERTUS')\n\n"
    
    Path('certus/spline/certus_corridor_orchestrator_utils.py').write_text(ext_imports + "\n".join(ext_lines), encoding='utf-8')
    
    # Remove from original safely
    to_remove = set()
    for s, e, n in bounds:
        for i in range(s, e):
            to_remove.add(i)
            
    final_lines = []
    added_imports = False
    
    for idx, l in enumerate(lines):
        if idx not in to_remove:
            final_lines.append(l)
            if "from certus.spline.certus_corridor_utils import *" in l and not added_imports:
                final_lines.append("from certus.spline.certus_corridor_orchestrator_utils import *")
                added_imports = True
                
    src_path.write_text("\n".join(final_lines), encoding='utf-8')
    print("Part 3 extraction completed cleanly.")

if __name__ == '__main__':
    extract()
