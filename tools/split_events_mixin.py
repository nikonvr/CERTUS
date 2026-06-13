import ast
from pathlib import Path

events_file = Path('certus/ui/certus_index_spline_events_mixin.py')
source = events_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef)][0]
methods = [n.name for n in app_class.body if isinstance(n, ast.FunctionDef)]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

categories = {
    'SmartInit': [m for m in methods if 'smart' in m],
    'ManualMesh': [m for m in methods if 'manual' in m or 'sigma' in m],
    'CorridorUI': [m for m in methods if 'corridor' in m and not ('manual' in m or 'sigma' in m)],
    'SpectrumUI': [m for m in methods if 'spectrum' in m and 'build' not in m],
    'LayoutExtras': [m for m in methods if 'build' in m and not ('smart' in m or 'manual' in m or 'corridor' in m or 'spectrum' in m)],
}

# The rest goes to EventsExtras
categorized = set()
for v in categories.values():
    categorized.update(v)

categories['EventsExtras'] = [m for m in methods if m not in categorized and m != '__init__']

ui_dir = Path('certus/ui')
base_imports = '\n'.join(source.splitlines()[:app_class.lineno - 1])

for cat, cat_methods in categories.items():
    if not cat_methods:
        continue
    mixin_name = f'CertusIndexSpline{cat}Mixin'
    filename = f'certus_index_spline_{cat.lower()}_mixin.py'
    
    out_lines = [base_imports, '', f'class {mixin_name}:', f'    \"\"\"{mixin_name}.\"\"\"', '']
    
    for m in cat_methods:
        node = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == m][0]
        source_code = get_node_source(node, source)
        out_lines.append(source_code)
        out_lines.append('')
        
    (ui_dir / filename).write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'Wrote {mixin_name} to {filename} with {len(cat_methods)} methods')

# Now update certus_index_spline_ui.py to include these new mixins
ui_main_file = Path('certus/ui/certus_index_spline_ui.py')
ui_main_source = ui_main_file.read_text(encoding='utf-8')

# Replace the single import of EventsMixin with all the new ones (and keep EventsMixin if needed, but we deleted it)
new_imports = '''from certus.ui.certus_index_spline_layout_mixin import CertusIndexSplineLayoutMixin
from certus.ui.certus_index_spline_state_mixin import CertusIndexSplineStateMixin
from certus.ui.certus_index_spline_table_mixin import CertusIndexSplineTableMixin
from certus.ui.certus_index_spline_plot_mixin import CertusIndexSplinePlotMixin
from certus.ui.certus_index_spline_workers_mixin import CertusIndexSplineWorkersMixin
from certus.ui.certus_index_spline_smartinit_mixin import CertusIndexSplineSmartInitMixin
from certus.ui.certus_index_spline_manualmesh_mixin import CertusIndexSplineManualMeshMixin
from certus.ui.certus_index_spline_corridorui_mixin import CertusIndexSplineCorridorUIMixin
from certus.ui.certus_index_spline_spectrumui_mixin import CertusIndexSplineSpectrumUIMixin
from certus.ui.certus_index_spline_layoutextras_mixin import CertusIndexSplineLayoutExtrasMixin
from certus.ui.certus_index_spline_eventsextras_mixin import CertusIndexSplineEventsExtrasMixin
'''

# We also need to update the original EventsMixin to not be used, but wait, the original certus_index_spline_events_mixin.py contained the core events which we put in categories during extraction. 
# Ah, certus_index_spline_events_mixin.py contains ALL events including the ones we just split. We should just replace it entirely.
