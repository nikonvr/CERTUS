import ast
import json

source = open('certus/ui/certus_ui.py', encoding='utf-8').read()
tree = ast.parse(source)

nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
res = {}
for n in nodes:
    res[n.name] = {
        'type': type(n).__name__,
        'lines': n.end_lineno - n.lineno
    }

print(json.dumps(res, indent=2))
