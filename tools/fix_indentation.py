from pathlib import Path
import re

p = Path('CERTUS_RE.py')
text = p.read_text(encoding='utf-8')

# The init_method already had 4 spaces, and I indented it by 4 more. So it has 8 spaces.
# The class CertusREApp is at 0 spaces.
# So def __init__(self): is at 8 spaces instead of 4.

# We will just strip 4 spaces from all lines between     APP_NAME = "CERTUS_RE" and def main():
lines = text.split('\n')
new_lines = []
in_init = False
for line in lines:
    if line.startswith('        def __init__(self):'):
        in_init = True
    if line.startswith('def main():'):
        in_init = False
        
    if in_init:
        if line.startswith('    '):
            new_lines.append(line[4:])
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

p.write_text('\n'.join(new_lines), encoding='utf-8')
