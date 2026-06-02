import re

filepath = r'certus\ui\certus_strat_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("def self._manifest_source_paths", "def _manifest_source_paths")
content = content.replace("def self._resolve_manifest_seed", "def _resolve_manifest_seed")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched certus_strat_ui.py syntax error")
