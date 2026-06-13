import sys

file_path = 'tests/test_field_module.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    '"Calcul réussi."': '"Calculation successful."',
    '"paramètre incohérent"': '"inconsistent parameter"'
}

for fr, en in replacements.items():
    content = content.replace(fr, en)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Tests updated.')
