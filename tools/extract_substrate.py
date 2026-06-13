import sys
from pathlib import Path
import re

def split_substrate_index():
    file_path = Path('certus/core/certus_substrate_index.py')
    content = file_path.read_text(encoding='utf-8')
    
    # 1. We want to extract ALL imports at the top
    # The imports usually end right before logger = setup_module_logging
    logger_match = re.search(r'logger\s*=\s*setup_module_logging', content)
    imports_end = logger_match.start() if logger_match else 0
    imports_content = content[:imports_end]
    
    # 2. Find the UI part
    ui_start = content.find('class IndexTableDialog')
    
    if ui_start == -1:
        print('Could not find IndexTableDialog')
        return

    ui_content = content[ui_start:]
    core_content = content[:ui_start]
    
    # Write UI file
    ui_file = Path('certus/ui/certus_substrate_ui.py')
    ui_code = imports_content + '\n'
    ui_code += 'from certus.core.certus_substrate_index import *\n\n'
    ui_code += ui_content
    ui_file.write_text(ui_code, encoding='utf-8')
    
    # Write Core file
    new_core_code = core_content + '\n\n# --- UI extracted to certus.ui.certus_substrate_ui ---\n'
    new_core_code += 'from certus.ui.certus_substrate_ui import IndexTableDialog, SubstrateIndexGUI\n'
    file_path.write_text(new_core_code, encoding='utf-8')
    
    print('Extraction done cleanly!')

if __name__ == '__main__':
    split_substrate_index()
