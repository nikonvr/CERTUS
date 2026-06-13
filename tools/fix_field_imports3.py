from pathlib import Path
ui_file = Path('certus/ui/certus_field_ui.py')
source = ui_file.read_text(encoding='utf-8')

import_block = '''from certus.ui.certus_ui_widgets_cards import CertusCard
from certus.ui.certus_base_app import CertusBaseApp, CertusAppLogsMixin
from certus.ui.certus_ui_widgets_factory import create_styled_button, create_header_logo_widget, create_top_actions_bar
from certus.ui.certus_ui_widgets_utils import CertusThemeToggle, DetachedPlotWindow, ExcelTableWidget
from certus.ui.certus_ui_widgets_layout import CertusCollapsible
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_utils import show_toast, open_file_explorer
from certus.ui.certus_ui_widgets_progress import EnhancedProgressWidget
from certus.ui.certus_plot import clone_plot_widget
'''

source = source.replace('''from certus.ui.certus_ui_widgets_cards import CertusCard
from certus.ui.certus_ui import (
    CertusBaseApp,  create_styled_button, 
    create_header_logo_widget, CertusThemeToggle, create_top_actions_bar,
    show_toast, CertusCollapsible, CertusAppLogsMixin, CertusTheme,
    clone_plot_widget, DetachedPlotWindow, EnhancedProgressWidget,
    ExcelTableWidget
)''', import_block)

source = source.replace('from certus.ui.certus_ui import open_file_explorer\n', '')

ui_file.write_text(source, encoding='utf-8')
