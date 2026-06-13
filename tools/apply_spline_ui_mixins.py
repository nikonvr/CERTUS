import ast
import json
from pathlib import Path

map_file = Path('tools/certus_index_spline_mixin_map.json')
categories = json.loads(map_file.read_text())

ui_file = Path('certus/ui/certus_index_spline_ui.py.bak')
source = ui_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusIndexSplineApp'][0]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

# For now we'll put all imports from the original file into the mixins
lines = source.splitlines()
class_start = app_class.lineno - 1
if app_class.decorator_list:
    class_start = app_class.decorator_list[0].lineno - 1

base_imports = '\n'.join(lines[:class_start])

ui_dir = Path('certus/ui')
for cat, methods in categories.items():
    mixin_name = f'CertusIndexSpline{cat}Mixin'
    filename = f'certus_index_spline_{cat.lower()}_mixin.py'
    
    out_lines = [base_imports, '', f'class {mixin_name}:', f'    \"\"\"{mixin_name}.\"\"\"', '']
    
    for m in methods:
        nodes = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == m]
        if not nodes:
            continue
        node = nodes[0]
        
        source_code = get_node_source(node, source)
        out_lines.append(source_code)
        out_lines.append('')
        
    (ui_dir / filename).write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'Wrote {mixin_name} to {filename}')

print('Done extracting Spline Mixins.')
