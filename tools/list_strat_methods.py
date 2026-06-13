import ast

content = open('certus/ui/certus_strat_ui.py', encoding='utf-8').read()
tree = ast.parse(content)
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == 'CertusStratApp':
        methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
        for m in methods:
            print(m)
