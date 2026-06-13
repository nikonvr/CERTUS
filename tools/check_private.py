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
    tmm_privates = get_private_defs('certus/physics/certus_tmm_core.py')
    
    core_content = Path('certus/core/_certus_physics_impl.py').read_text(encoding='utf-8')
    missing = []
    for p in tmm_privates:
        if p + '(' in core_content or p + ',' in core_content or p + ' ' in core_content:
            missing.append(p)
            
    if missing:
        print("Missing privates:", missing)
    else:
        print("All good!")

if __name__ == '__main__':
    main()
