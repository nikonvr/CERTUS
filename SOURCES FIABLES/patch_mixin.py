import os

filepath = r'certus\ui\certus_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

mixin_code = """
class CertusAppLogsMixin:
    \"\"\"Provides common UI log operations.\"\"\"
    def copy_logs_to_clipboard(self) -> None:
        \"\"\"Copy logs to clipboard and update status label if possible.\"\"\"
        copy_app_logs_to_clipboard(self)
        if hasattr(self, 'lbl_status') and hasattr(self.lbl_status, 'setText'):
            self.lbl_status.setText("Logs copied to clipboard!")
"""

if 'class CertusAppLogsMixin:' not in content:
    content = content.replace('def copy_app_logs_to_clipboard(app', mixin_code + '\n\ndef copy_app_logs_to_clipboard(app')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Added CertusAppLogsMixin to certus_ui.py')
else:
    print('CertusAppLogsMixin already exists')
