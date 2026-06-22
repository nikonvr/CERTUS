import re
import ast
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

path = 'certus/workers/certus_re_workers.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract names imported from certus.utils.certus_re_helpers
match = re.search(r'from certus\.utils\.certus_re_helpers import ([^\n]+)', content)
if not match:
    print('Not found in re_workers')

if match:
    names = [n.strip() for n in match.group(1).split(',')]
    
    def find_symbol(symbol):
        for root, dirs, files in os.walk('certus'):
            for f in files:
                if f.endswith('.py'):
                    p = os.path.join(root, f)
                    with open(p, 'r', encoding='utf-8') as file:
                        try:
                            tree = ast.parse(file.read())
                            for node in tree.body:
                                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                                    if node.name == symbol:
                                        return p.replace(os.sep, '.')[:-3]
                                elif isinstance(node, ast.Assign):
                                    for t in node.targets:
                                        if isinstance(t, ast.Name) and t.id == symbol:
                                            return p.replace(os.sep, '.')[:-3]
                        except:
                            pass
        return None
    
    try:
        import certus.utils.certus_re_helpers as helper
        exports = dir(helper)
    except Exception as e:
        exports = []
        print(f"Could not load helper: {e}")
    
    new_imports = {}
    valid_names = []
    for name in names:
        if name and name not in exports:
            loc = find_symbol(name)
            if loc:
                new_imports.setdefault(loc, []).append(name)
        elif name:
            valid_names.append(name)
    
    # replace the original import
    new_import_str = '
    for loc, syms in new_imports.items():
        new_import_str += f'from {loc} import {", ".join(syms)}\n'
    
    content = content.replace(match.group(0), new_import_str)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('Patched re_workers successfully')

# We should also patch certus/workers/certus_re_workers_phase3.py and others if needed.
