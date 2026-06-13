from pathlib import Path

ui_dir = Path('certus/ui')

# certus_base_app.py needs safe_ui_action, show_toast, etc.
base_app = ui_dir / 'certus_base_app.py'
content = base_app.read_text(encoding='utf-8')
lines = content.splitlines()

# find where imports end
import_end = 0
for i, line in enumerate(lines):
    if line.startswith('class ') or line.startswith('def '):
        import_end = i
        break

new_imports = '''
from certus.ui.certus_ui_utils import (
    safe_ui_action, show_toast, show_status_feedback, confirm_stop_with_timeout,
    process_log_queue_standard, open_file_explorer, stop_worker_and_thread
)
from certus.ui.certus_ui_widgets_factory import (
    create_log_widget, create_top_actions_bar
)
'''
lines.insert(import_end, new_imports)
base_app.write_text('\n'.join(lines), encoding='utf-8')

# certus_ui_utils.py needs some things maybe?
utils = ui_dir / 'certus_ui_utils.py'
content = utils.read_text(encoding='utf-8')
lines = content.splitlines()
import_end = 0
for i, line in enumerate(lines):
    if line.startswith('class ') or line.startswith('def '):
        import_end = i
        break
new_imports = '''
from certus.ui.certus_ui_widgets_factory import create_flashy_grid
from certus.ui.certus_base_app import CertusBaseApp
'''
lines.insert(import_end, new_imports)
utils.write_text('\n'.join(lines), encoding='utf-8')

# certus_ui_widgets_factory.py needs some things maybe?
factory = ui_dir / 'certus_ui_widgets_factory.py'
content = factory.read_text(encoding='utf-8')
lines = content.splitlines()
import_end = 0
for i, line in enumerate(lines):
    if line.startswith('class ') or line.startswith('def '):
        import_end = i
        break
new_imports = '''
from certus.ui.certus_ui_utils import open_documentation
'''
lines.insert(import_end, new_imports)
factory.write_text('\n'.join(lines), encoding='utf-8')

print("Fixed imports")
