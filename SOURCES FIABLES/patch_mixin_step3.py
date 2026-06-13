import re

filepath = r'certus\ui\certus_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """class CertusAppLogsMixin:
    \"\"\"Provides common UI log operations.\"\"\"
    def copy_logs_to_clipboard(self) -> None:
        \"\"\"Copy logs to clipboard and update status label if possible.\"\"\"
        copy_app_logs_to_clipboard(self)
        if hasattr(self, 'lbl_status') and hasattr(self.lbl_status, 'setText'):
            self.lbl_status.setText("Logs copied to clipboard!")

    def on_toggle_details(self, checked: bool) -> None:
        \"\"\"Show/Hide log panel dynamically.\"\"\"
        if hasattr(self, 'log_text'):
            self.log_text.setVisible(checked)
        if hasattr(self, 'toggle_details_btn'):
            self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")
        if hasattr(self, 'right_splitter'):
            if checked:
                self.right_splitter.setSizes([600, 200])
            else:
                self.right_splitter.setSizes([1000, 0])
"""

pattern = r'^class CertusAppLogsMixin:\n(?:[ \t]+.*?\n)*?(?=\n\ndef )'
content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated CertusAppLogsMixin in certus_ui.py')
