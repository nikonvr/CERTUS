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
    core_path = Path('certus/core/_certus_physics_impl.py')
    core_content = core_path.read_text(encoding='utf-8')
    
    files = glob.glob('certus/physics/*.py')
    for f in files:
        if '__init__' in f: continue
        mod_name = Path(f).stem
        privates = get_private_defs(f)
        
        missing = []
        for p in privates:
            if f" {p}" not in core_content and f" {p}," not in core_content:
                missing.append(p)
                
        if missing:
            print(f"Adding from {mod_name}: {missing}")
            # Add to core_content
            # We'll just replace "from certus.physics.X import *" with "from certus.physics.X import *\nfrom certus.physics.X import _A, _B"
            # But wait, missing can be large. Let's chunk them
            imports_str = f"\nfrom certus.physics.{mod_name} import " + ", ".join(missing)
            core_content = core_content.replace(f"from certus.physics.{mod_name} import *", f"from certus.physics.{mod_name} import *{imports_str}")

    core_path.write_text(core_content, encoding='utf-8')
    print("Updated _certus_physics_impl.py")

if __name__ == '__main__':
    main()
