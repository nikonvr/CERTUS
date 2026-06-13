from pathlib import Path
ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')
missing = 'from certus.ui.certus_ui_widgets_layout import CertusCollapsible\n'
source = source.replace('from certus.ui.certus_base_app', missing + 'from certus.ui.certus_base_app')
ui_file.write_text(source, encoding='utf-8')
