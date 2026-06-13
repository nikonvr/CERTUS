import ast

content = open('certus/spline/spline_pipeline.py', encoding='utf-8').read()
tree = ast.parse(content)
functions = [f.name for f in tree.body if isinstance(f, ast.FunctionDef)]
print(f"Total functions: {len(functions)}")
for f in functions:
    print(f)
