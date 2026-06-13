from pathlib import Path
import re

ui_dir = Path('certus/ui')

factory = ui_dir / 'certus_ui_widgets_factory.py'
content = factory.read_text(encoding='utf-8')
# Remove global import
content = content.replace('from certus.ui.certus_ui_utils import open_documentation', '')
# Add local import
content = content.replace('open_documentation()', 'import certus.ui.certus_ui_utils as utils; utils.open_documentation()')
content = content.replace('open_documentation(', 'import certus.ui.certus_ui_utils as utils; utils.open_documentation(')
factory.write_text(content, encoding='utf-8')

utils = ui_dir / 'certus_ui_utils.py'
content = utils.read_text(encoding='utf-8')
content = content.replace('from certus.ui.certus_ui_widgets_factory import create_flashy_grid', '')
content = content.replace('from certus.ui.certus_base_app import CertusBaseApp', '')
utils.write_text(content, encoding='utf-8')

base_app = ui_dir / 'certus_base_app.py'
content = base_app.read_text(encoding='utf-8')
# Actually base app can import them fine if we just put it at the bottom or if it's the root.
# Let's remove the global imports and do it inside the methods where needed, or just let them fail and I'll fix them one by one.
