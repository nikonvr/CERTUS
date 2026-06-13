import ast
from pathlib import Path

def get_node_bounds(tree, names, is_class=False):
    bounds = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_class:
            if node.name in names:
                # Need to check decorators
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
    
    # Extract configs
    configs = ['ProfileCorridorConfig', 'RegularGridProfileContext', 'CorridorContextBuilder', 'CorridorWalkSideContext', 'CorridorLiveStreamer']
    cfg_bounds = get_node_bounds(tree, configs, is_class=True)
    
    cfg_lines = []
    for s, e, n in sorted(cfg_bounds, key=lambda x: x[0]):
        cfg_lines.extend(lines[s:e])
        
    cfg_imports = "from dataclasses import dataclass, field\nfrom typing import *\nimport numpy as np\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\n\n"
    Path('certus/spline/certus_corridor_config.py').write_text(cfg_imports + "\n".join(cfg_lines), encoding='utf-8')
    
    # Extract fitters
    fitters = ['_fit_local_quadratic_rmse_profile', '_fit_nodes_at_fixed_d']
    fit_bounds = get_node_bounds(tree, fitters, is_class=False)
    
    fit_lines = []
    for s, e, n in sorted(fit_bounds, key=lambda x: x[0]):
        fit_lines.extend(lines[s:e])
        
    fit_imports = "from typing import *\nimport numpy as np\nfrom scipy.optimize import minimize\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\nfrom certus.spline.spline_objective import *\nfrom certus.spline.certus_corridor_config import *\nimport logging\nlog = logging.getLogger('CERTUS')\n\n"
    Path('certus/spline/certus_corridor_fitter.py').write_text(fit_imports + "\n".join(fit_lines), encoding='utf-8')
    
    # Remove from original
    to_remove = set()
    for s, e, n in cfg_bounds + fit_bounds:
        for i in range(s, e):
            to_remove.add(i)
            
    new_lines = []
    for idx, l in enumerate(lines):
        if idx == 0:
            new_lines.append(l)
            new_lines.append("from certus.spline.certus_corridor_config import *")
            new_lines.append("from certus.spline.certus_corridor_fitter import *")
            continue
        if idx not in to_remove:
            new_lines.append(l)
            
    src_path.write_text("\n".join(new_lines), encoding='utf-8')
    print("Extraction safe completed.")

if __name__ == '__main__':
    extract()
