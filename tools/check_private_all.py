import ast
from pathlib import Path

def get_private_defs(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    defs = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name.startswith('_'):
                    defs.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.startswith('_'):
                        defs.add(t.id)
    return defs

def main():
    modules = ['certus_optical_models.py', 'certus_tmm_core.py', 'certus_opt_kernels.py', 'certus_colorimetry.py', 'certus_material_db.py', 'certus_optimizers.py', 'certus_strat_kernels.py']
    core_content = Path('certus/core/_certus_physics_impl.py').read_text(encoding='utf-8')
    
    for mod in modules:
        privates = get_private_defs('certus/physics/' + mod)
        missing = []
        for p in privates:
            # check if p is used in core_content
            if p + '(' in core_content or p + ',' in core_content or p + ' ' in core_content or p + ')' in core_content or p + '[' in core_content:
                # check if it is imported
                if f"import {p}" not in core_content and f" {p}" not in core_content.split('import ')[-1]:
                    # simplistic check, let's just see if import p or p, is in an import line
                    import_lines = [l for l in core_content.splitlines() if 'import' in l]
                    found = False
                    for l in import_lines:
                        if p in l:
                            found = True
                            break
                    if not found:
                        missing.append(p)
                        
        if missing:
            print(f"Missing from {mod}: {missing}")

if __name__ == '__main__':
    main()
