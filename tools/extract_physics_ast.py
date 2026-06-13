import ast
from pathlib import Path
import json

def extract_physics():
    core_path = Path('certus/core/_certus_physics_impl.py')
    content = core_path.read_text(encoding='utf-8')
    tree = ast.parse(content)
    
    symbols = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            symbols.append({
                'type': type(node).__name__,
                'name': node.name,
                'start': node.lineno,
                'end': node.end_lineno
            })
            
    Path('tools/physics_symbols.json').write_text(json.dumps(symbols, indent=2))
    print('Saved to tools/physics_symbols.json')

if __name__ == '__main__':
    extract_physics()
