import ast
from pathlib import Path

ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')
tree = ast.parse(source)

nodes = [n for n in tree.body]
lines = source.splitlines()

# We will group by categories:
# BaseApp -> CertusBaseApp and related (CertusAppLogsMixin, StatsCounter, _CertusDropFilter)
# WidgetsFactory -> create_flashy_grid, create_log_widget, create_header_logo_widget, etc
# Utils -> apply_certus_theme, open_file_explorer, safe_ui_action, etc

categories = {
    'BaseApp': ['CertusBaseApp', 'CertusAppLogsMixin', 'StatsCounter', '_CertusDropFilter'],
    'WidgetsFactory': ['create_flashy_grid', 'create_log_widget', 'create_header_logo_widget', 'create_styled_button', 'create_info_icon', 'create_help_button', 'create_styled_label', 'create_colored_label', 'create_top_actions_bar'],
    'Utils': ['set_certus_window_icon', 'apply_certus_theme', 'update_global_plot_config', 'open_documentation', 'install_standard_shortcuts', 'enable_file_drop', 'show_toast', 'show_status_feedback', 'attach_numeric_validator', 'get_export_settings', 'open_file_explorer', 'process_log_queue_standard', 'init_certus_app', '_patch_pyqtgraph_viewbox_nan_transform_angle', 'setup_pyqtgraph_defaults', 'setup_gui_exception_handling', 'safe_ui_action', 'confirm_stop_with_timeout', 'format_count_kmg', 'stop_worker_and_thread', 'confirm_and_stop', 'copy_app_logs_to_clipboard', 'install_skeleton_loader', 'remove_skeleton_loader', '_hex_to_rgba_css', 'apply_os_window_effects']
}

# The problem is that CertusBaseApp is 3000 lines. Let's just create certus_base_app.py for it.
import re
header = []
for line in lines:
    if line.startswith('def ') or line.startswith('class ') or line.startswith('_LAZY_REEXPORTS'):
        break
    header.append(line)
header_str = '\n'.join(header)

def get_node_source(n):
    start = n.lineno - 1
    end = n.end_lineno
    if hasattr(n, 'decorator_list') and n.decorator_list:
        start = n.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

files = {
    'certus_base_app.py': [],
    'certus_ui_widgets_factory.py': [],
    'certus_ui_utils.py': []
}

for n in tree.body:
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
        src = get_node_source(n)
        if n.name in categories['BaseApp']:
            files['certus_base_app.py'].append(src)
        elif n.name in categories['WidgetsFactory']:
            files['certus_ui_widgets_factory.py'].append(src)
        elif n.name in categories['Utils']:
            files['certus_ui_utils.py'].append(src)

ui_dir = Path('certus/ui')
for f, content_lines in files.items():
    if not content_lines: continue
    full_content = header_str + '\n\n' + '\n\n'.join(content_lines)
    (ui_dir / f).write_text(full_content, encoding='utf-8')
    print(f"Wrote {f} with {len(content_lines)} blocks")

# Update certus_ui.py to be a facade
lazy_exports = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and getattr(n.targets[0], 'id', '') == '_LAZY_REEXPORTS']
getattr_node = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '__getattr__']

facade_str = header_str + '''\n
from certus.ui.certus_base_app import CertusBaseApp, CertusAppLogsMixin, StatsCounter
from certus.ui.certus_ui_widgets_factory import (
    create_flashy_grid, create_log_widget, create_header_logo_widget,
    create_styled_button, create_info_icon, create_help_button,
    create_styled_label, create_colored_label, create_top_actions_bar
)
from certus.ui.certus_ui_utils import (
    set_certus_window_icon, apply_certus_theme, update_global_plot_config,
    open_documentation, install_standard_shortcuts, enable_file_drop,
    show_toast, show_status_feedback, attach_numeric_validator, get_export_settings,
    open_file_explorer, process_log_queue_standard, init_certus_app,
    setup_pyqtgraph_defaults, setup_gui_exception_handling, safe_ui_action,
    confirm_stop_with_timeout, format_count_kmg, stop_worker_and_thread,
    confirm_and_stop, copy_app_logs_to_clipboard, install_skeleton_loader,
    remove_skeleton_loader, apply_os_window_effects
)
'''
if lazy_exports:
    facade_str += '\n\n' + get_node_source(lazy_exports[0])
if getattr_node:
    facade_str += '\n\n' + get_node_source(getattr_node[0])

ui_file.write_text(facade_str, encoding='utf-8')
print("certus_ui.py is now a facade.")
