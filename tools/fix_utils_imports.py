from pathlib import Path
utils = Path('certus/ui/certus_ui_utils.py')
source = utils.read_text(encoding='utf-8')
source = source.replace('from certus.ui.certus_ui_widgets_factory import create_flashy_grid', 'from certus.ui.certus_ui_widgets_factory import create_flashy_grid\nfrom certus.ui.certus_theme import CertusTheme, load_theme_config\n')
utils.write_text(source, encoding='utf-8')
