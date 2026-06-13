import ast
import sys

def get_ast_stats(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    tree = ast.parse(code)
    
    stats = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            length = end_line - start_line + 1
            node_type = "Class" if isinstance(node, ast.ClassDef) else "Function"
            parent_name = getattr(node, 'parent_name', '')
            
            # Simple heuristic for method names
            name = node.name
            stats.append((length, node_type, name))
            
    stats.sort(reverse=True, key=lambda x: x[0])
    return stats, code

single_stats, single_code = get_ast_stats('CERTUS_METAL_SINGLE.py')
bilayer_stats, bilayer_code = get_ast_stats('CERTUS_METAL_BILAYER.py')

print("--- CERTUS_METAL_SINGLE.py ---")
for length, ntype, name in single_stats[:10]:
    print(f"{length} lines: {ntype} {name}")

print("\n--- CERTUS_METAL_BILAYER.py ---")
for length, ntype, name in bilayer_stats[:10]:
    print(f"{length} lines: {ntype} {name}")
