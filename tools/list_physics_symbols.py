import ast
from pathlib import Path

def list_symbols():
    code = Path('certus/core/_certus_physics_impl.py').read_text(encoding='utf-8')
    tree = ast.parse(code)
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            print(f"Function: {node.name}")
        elif isinstance(node, ast.ClassDef):
            print(f"Class: {node.name}")
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    print(f"  Method: {item.name}")

if __name__ == '__main__':
    list_symbols()
