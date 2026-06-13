import re

filepath = r'certus\ui\certus_index_spline_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove `_execute_smart_init_recall_best` from `certus_index_spline_ui.py`
pattern = r'^[ \t]+def _execute_smart_init_recall_best\(self, state: _SmartInitState\) -> str \| None:\n(?:[ \t]+.*?\n)*?(?=[ \t]+def |\Z)'
content = re.sub(pattern, '', content, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed _execute_smart_init_recall_best from certus_index_spline_ui.py")
