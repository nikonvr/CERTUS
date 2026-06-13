from pathlib import Path
utils = Path('certus/ui/certus_ui_utils.py')
source = utils.read_text(encoding='utf-8')
source = source.replace('from certus.ui.certus_theme import CertusTheme, load_theme_config', 'from certus.ui.certus_theme import CertusTheme\nfrom certus.core.certus_core import load_theme_config')
utils.write_text(source, encoding='utf-8')
