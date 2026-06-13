from pathlib import Path

for fpath in Path('c:/driveFL/couches minces 2026/CERTUS/version26_05reference/2905/tests').rglob('*.py'):
    content = fpath.read_text('utf-8')
    if '"26_05"' in content:
        lines = content.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i
                break
        lines.insert(insert_idx, 'from certus.core.version import APP_VERSION')
        content = '\n'.join(lines)
        content = content.replace('"26_05"', 'APP_VERSION')
        fpath.write_text(content, 'utf-8')
