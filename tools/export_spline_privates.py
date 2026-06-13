import ast
from pathlib import Path
import glob

def get_private_defs(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    defs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name.startswith('_') and not node.name.startswith('__'):
                    defs.append(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.startswith('_') and not t.id.startswith('__'):
                        defs.append(t.id)
    return defs

def main():
    core_path = Path('certus/spline/spline_profile_corridors.py')
    core_content = core_path.read_text(encoding='utf-8')
    
    files = [
        'certus/spline/certus_corridor_config.py',
        'certus/spline/certus_corridor_fitter.py',
        'certus/spline/certus_corridor_exploration.py',
        'certus/spline/certus_corridor_logger.py',
        'certus/spline/certus_corridor_bootstrap.py',
        'certus/spline/certus_corridor_utils.py',
        'certus/spline/certus_corridor_orchestrator_utils.py'
    ]
    
    for f in files:
        mod_name = Path(f).stem
        privates = get_private_defs(f)
        
        missing = []
        for p in privates:
            # check if it's imported
            if f" {p}" not in core_content and f"{p}," not in core_content:
                missing.append(p)
                
        if missing:
            print(f"Adding from {mod_name}: {missing}")
            imports_str = f"\nfrom certus.spline.{mod_name} import " + ", ".join(missing)
            core_content = core_content.replace(f"from certus.spline.{mod_name} import *", f"from certus.spline.{mod_name} import *{imports_str}")

    core_path.write_text(core_content, encoding='utf-8')
    print("Updated spline_profile_corridors.py")

if __name__ == '__main__':
    main()
