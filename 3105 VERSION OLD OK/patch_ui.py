import re
import os

files_to_patch = [
    r'certus\ui\certus_design_ui.py',
    r'certus\ui\certus_index_ui.py',
    r'certus\ui\certus_strat_ui.py'
]

for filepath in files_to_patch:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add CertusAppLogsMixin to imports
    if 'CertusAppLogsMixin' not in content:
        content = content.replace('copy_app_logs_to_clipboard,', 'copy_app_logs_to_clipboard,\n    CertusAppLogsMixin,')
    
    # 2. Add to class inheritance
    # In design: class CertusDesignApp(QMainWindow):
    # In index: class CertusIndexApp(QMainWindow):
    # In strat: class CertusStratApp(QMainWindow):
    content = re.sub(r'class Certus([a-zA-Z]+)App\(QMainWindow\):', r'class Certus\1App(CertusAppLogsMixin, QMainWindow):', content)
    
    # 3. Remove copy_logs_to_clipboard method
    # It looks like:
    #     def copy_logs_to_clipboard(self) -> None:
    #         """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""
    #
    #         copy_app_logs_to_clipboard(self)
    #
    #         self.lbl_status.setText("Logs copied to clipboard!")
    
    pattern = r'^[ \t]{4}def copy_logs_to_clipboard\(self\) -> None:\n(?:[ \t]+.*?\n)*?(?=[ \t]{4}def |\Z)'
    content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Patched 3 UI files.")
