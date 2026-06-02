from pathlib import Path

for fpath in Path('c:/driveFL/couches minces 2026/CERTUS/version26_05reference/2905/tests').rglob('*.py'):
    content = fpath.read_text('utf-8')
    if 'from certus.core.version import APP_VERSION' in content and 'from __future__ import annotations' in content:
        lines = content.splitlines()
        
        # find the exact lines
        future_idx = -1
        app_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == 'from __future__ import annotations':
                future_idx = i
            elif line.strip() == 'from certus.core.version import APP_VERSION':
                app_idx = i
        
        if app_idx < future_idx:
            # swap them
            lines[app_idx], lines[future_idx] = lines[future_idx], lines[app_idx]
            fpath.write_text('\n'.join(lines), 'utf-8')
            print(f"Fixed {fpath.name}")
