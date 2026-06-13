from pathlib import Path
ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')
missing_imports = '''from certus.ui.certus_ui_widgets_cards import CertusCard, CertusModuleCard, CertusValueCard
from certus.ui.certus_ui_widgets_utils import CertusThemeToggle, CertusCollapsibleBox, CertusAnimatedToggle
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.ui.certus_plot import CertusScientificPlot
'''
source = source.replace('from certus.ui.certus_base_app', missing_imports + 'from certus.ui.certus_base_app')
ui_file.write_text(source, encoding='utf-8')
