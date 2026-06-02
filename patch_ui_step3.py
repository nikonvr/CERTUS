import re

files = [r'certus\ui\certus_index_ui.py', r'certus\ui\certus_strat_ui.py']

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Removes the function and its body
    pattern = r'^[ \t]{4}def on_toggle_details\(self, checked\) -> None:\n(?:[ \t]+.*?\n)*?(?=[ \t]{4}def |\Z)'
    content = re.sub(pattern, '', content, flags=re.MULTILINE)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print('Removed on_toggle_details from index and strat UIs.')
