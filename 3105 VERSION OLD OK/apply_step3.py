import os

db_path = r'certus\utils\certus_strat_db.py'
phys_path = r'certus\core\_certus_physics_impl.py'
helper_path = r'certus\utils\certus_db_helpers.py'

with open(db_path, 'r', encoding='utf-8') as f:
    db_lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(db_lines):
    if line.startswith('def find_matching_sheets('):
        start_idx = i
    if line.startswith('class RobustMaterialDatabase:'):
        end_idx = i
        break

extracted_lines = db_lines[start_idx:end_idx]

# Write to certus_db_helpers.py
with open(helper_path, 'w', encoding='utf-8') as f:
    f.write('import logging\nimport numpy as np\n\n')
    f.writelines(extracted_lines)

# Update certus_strat_db.py
with open(db_path, 'w', encoding='utf-8') as f:
    added_import = False
    for i in range(start_idx):
        if db_lines[i].startswith('from certus.core.certus_core import') and not added_import:
            f.write(db_lines[i])
            f.write('from certus.utils.certus_db_helpers import find_matching_sheets, merge_two_curves, merge_multiple_curves, MaterialDB\n')
            added_import = True
        else:
            f.write(db_lines[i])
    for i in range(end_idx, len(db_lines)):
        f.write(db_lines[i])

# Update _certus_physics_impl.py
with open(phys_path, 'r', encoding='utf-8') as f:
    phys_lines = f.readlines()

start_phys = -1
end_phys = -1
for i, line in enumerate(phys_lines):
    if line.startswith('def find_matching_sheets('):
        start_phys = i
    if line.startswith('class MaterialDatabase:'):
        end_phys = i
        break

# Also, we need to add the import in _certus_physics_impl.py
with open(phys_path, 'w', encoding='utf-8') as f:
    added_import_phys = False
    for i in range(start_phys):
        if (phys_lines[i].startswith('import numba') or phys_lines[i].startswith('import numpy')) and not added_import_phys:
            f.write(phys_lines[i])
            f.write('from certus.utils.certus_db_helpers import find_matching_sheets, merge_two_curves, merge_multiple_curves, MaterialDB as _SubProcessMaterialDB\n')
            added_import_phys = True
        else:
            f.write(phys_lines[i])
    
    # We skip from start_phys to end_phys
    for i in range(end_phys, len(phys_lines)):
        f.write(phys_lines[i])

print("certus_strat_db.py, _certus_physics_impl.py and certus_db_helpers.py updated")
