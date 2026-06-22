import ast
with open('certus/spline/certus_index_spline_corridors.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == '_CorridorWorkerMixin':
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                length = getattr(child, 'end_lineno', 0) - child.lineno
                print(f'{child.name} ({child.lineno} to {getattr(child, "end_lineno", "?")}) - {length} lines')
