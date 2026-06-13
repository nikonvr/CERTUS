from pathlib import Path
ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')
missing = '''from certus.ui.certus_plot import clone_plot_widget
from certus.ui.certus_ui_widgets_progress import EnhancedProgressWidget
from certus.ui.certus_ui_widgets_utils import DetachedPlotWindow, ExcelTableWidget
'''
source = source.replace('from certus.ui.certus_base_app', missing + 'from certus.ui.certus_base_app')
ui_file.write_text(source, encoding='utf-8')
