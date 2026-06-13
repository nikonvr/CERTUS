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
    
    # Extract explorers
    explorers = ['compute_regular_grid_rmse_profile', '_corridor_profile_walk_side', 'compute_bootstrap_corridors_by_d']
    exp_bounds = get_node_bounds(tree, explorers, is_class=False)
    
    exp_lines = []
    for s, e, n in sorted(exp_bounds, key=lambda x: x[0]):
        exp_lines.extend(lines[s:e])
        
    exp_imports = "from typing import *\nimport numpy as np\nimport logging\nimport threading\nfrom concurrent.futures import ThreadPoolExecutor, as_completed\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\nfrom certus.spline.certus_corridor_config import *\nfrom certus.spline.certus_corridor_fitter import *\nfrom certus.spline.spline_objective import build_spline_objective_masked_grid, nk_from_x_pwlnk\nlog = logging.getLogger('CERTUS')\n\n"
    Path('certus/spline/certus_corridor_exploration.py').write_text(exp_imports + "\n".join(exp_lines), encoding='utf-8')
    
    # Remove from original
    to_remove = set()
    for s, e, n in exp_bounds:
        for i in range(s, e):
            to_remove.add(i)
            
    new_lines = []
    for idx, l in enumerate(lines):
        new_lines.append(l)
        if "from certus.spline.certus_corridor_fitter import *" in l:
            new_lines.append("from certus.spline.certus_corridor_exploration import *")
            
    # Filter removed
    final_lines = [l for i, l in enumerate(new_lines) if i not in to_remove]
            
    src_path.write_text("\n".join(final_lines), encoding='utf-8')
    print("Exploration extraction completed.")

if __name__ == '__main__':
    extract()
