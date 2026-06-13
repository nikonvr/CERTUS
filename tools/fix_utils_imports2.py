from pathlib import Path
utils = Path('certus/ui/certus_ui_utils.py')
source = utils.read_text(encoding='utf-8')
lines = source.splitlines()

for i, line in enumerate(lines):
    if line.startswith('def ') or line.startswith('class '):
        lines.insert(i, 'from certus.ui.certus_theme import CertusTheme, load_theme_config\n')
        break

utils.write_text('\n'.join(lines), encoding='utf-8')
