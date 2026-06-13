from pathlib import Path
ui_file = Path('certus/ui/certus_field_ui.py')
source = ui_file.read_text(encoding='utf-8')
source = source.replace('CertusCard,', '')
source = source.replace('from certus.ui.certus_ui import (', 'from certus.ui.certus_ui_widgets_cards import CertusCard\nfrom certus.ui.certus_ui import (')
ui_file.write_text(source, encoding='utf-8')
