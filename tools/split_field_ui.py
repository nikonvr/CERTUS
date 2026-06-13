import ast
from pathlib import Path

ui_file = Path('certus/ui/certus_field_ui.py')
source = ui_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusFieldApp'][0]
methods = [n.name for n in app_class.body if isinstance(n, ast.FunctionDef)]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

categories = {
    'Layout': [m for m in methods if m.startswith('_build_') or m == '_setup_ui' or 'layout' in m.lower()],
    'Plot': [m for m in methods if 'plot' in m.lower() or 'chart' in m.lower() or 'update_heatmap' in m or 'draw' in m or 'crosshair' in m or 'view' in m],
    'Events': [m for m in methods if m.startswith('_on_') or 'event' in m.lower() or 'click' in m.lower() or 'update_ui' in m or 'sync' in m or 'export' in m.lower()],
    'Workers': [m for m in methods if 'worker' in m.lower() or 'thread' in m.lower() or 'calculate' in m.lower() or 'process' in m.lower()],
}

categorized = set()
for v in categories.values():
    categorized.update(v)

categories['State'] = [m for m in methods if m not in categorized and m != '__init__']

ui_dir = Path('certus/ui')
base_imports = '\n'.join(source.splitlines()[:app_class.lineno - 1])

for cat, cat_methods in categories.items():
    if not cat_methods:
        continue
    mixin_name = f'CertusField{cat}Mixin'
    filename = f'certus_field_{cat.lower()}_mixin.py'
    
    out_lines = [base_imports, '', f'class {mixin_name}:', f'    \"\"\"{mixin_name}.\"\"\"', '']
    
    for m in cat_methods:
        node = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == m][0]
        source_code = get_node_source(node, source)
        out_lines.append(source_code)
        out_lines.append('')
        
    (ui_dir / filename).write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'Wrote {mixin_name} to {filename} with {len(cat_methods)} methods')

# Now update certus_field_ui.py
import re
new_class = f'''class CertusFieldApp(
    CertusBaseApp,
    CertusFieldLayoutMixin,
    CertusFieldPlotMixin,
    CertusFieldEventsMixin,
    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):'''

source = re.sub(r'class CertusFieldApp\([^)]+\):', new_class, source)

# Add imports for mixins
new_imports = '''from certus.ui.certus_field_layout_mixin import CertusFieldLayoutMixin
from certus.ui.certus_field_plot_mixin import CertusFieldPlotMixin
from certus.ui.certus_field_events_mixin import CertusFieldEventsMixin
from certus.ui.certus_field_workers_mixin import CertusFieldWorkersMixin
from certus.ui.certus_field_state_mixin import CertusFieldStateMixin
'''

# We need to remove all methods except __init__ from the main class
init_node = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'][0]
init_src = get_node_source(init_node, source)

lines = source.splitlines()
class_start = app_class.lineno - 1
if app_class.decorator_list:
    class_start = app_class.decorator_list[0].lineno - 1

main_block_str = '''
def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusFieldApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
'''

final_content = '\n'.join(lines[:class_start]) + '\n\n' + new_imports + '\n\n' + new_class + '\n\n' + init_src + '\n\n' + main_block_str

ui_file.write_text(final_content, encoding='utf-8')
print("Successfully extracted mixins for certus_field_ui.py")
