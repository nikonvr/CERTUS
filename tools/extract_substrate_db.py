from pathlib import Path
import re

def extract_db():
    core_path = Path('certus/core/certus_core.py')
    content = core_path.read_text(encoding='utf-8')
    
    start_marker = '# Sellmeier Coefficients for Substrates (Single Source of Truth)'
    end_marker = '# GUI LOGGING (Thread-Safe Queue Handler)'
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print('Markers not found!')
        return
        
    db_block = content[start_idx:end_idx]
    # We want to remove the block from core_path, except we will replace it with an import statement.
    # To be perfectly safe, we will just add the import and keep the rest.
    
    db_path = Path('certus/core/certus_substrate_db.py')
    db_code = "from typing import Any\n\n" + db_block
    db_path.write_text(db_code, encoding='utf-8')
    
    # We replace the block in certus_core.py with the import
    import_stmt = "from certus.core.certus_substrate_db import *\n\n\n"
    # Find the line '# =============================================================================' before GUI LOGGING
    actual_end_idx = content.rfind('# =====', 0, end_idx)
    if actual_end_idx == -1: actual_end_idx = end_idx
    
    new_core_content = content[:start_idx] + import_stmt + content[actual_end_idx:]
    core_path.write_text(new_core_content, encoding='utf-8')
    
    print('DB Extracted!')

if __name__ == '__main__':
    extract_db()
