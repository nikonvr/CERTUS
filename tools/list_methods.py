import ast
import sys

content = open('certus/ui/certus_index_ui.py', encoding='utf-8').read()
tree = ast.parse(content)
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == 'CertusIndexApp':
        methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
        print(f"Total methods: {len(methods)}")
        for m in methods:
            print(m)
