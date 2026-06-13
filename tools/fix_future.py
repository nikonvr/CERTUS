from pathlib import Path

path = Path('certus/spline/spline_profile_corridors.py')
lines = path.read_text(encoding='utf-8').splitlines()

# Remove any line that is from certus.spline.certus_corridor_*
new_lines = []
imports_to_add = ["from certus.spline.certus_corridor_config import *", "from certus.spline.certus_corridor_fitter import *"]

for l in lines:
    if l.startswith("from certus.spline.certus_corridor_"): continue
    new_lines.append(l)

# Add imports right after from __future__
final_lines = []
for l in new_lines:
    final_lines.append(l)
    if "from __future__ import annotations" in l:
        final_lines.extend(imports_to_add)

path.write_text("\n".join(final_lines), encoding='utf-8')
print("Fixed.")
