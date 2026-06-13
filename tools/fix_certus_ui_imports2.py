from pathlib import Path
ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')
source = source.replace('from certus.ui.certus_ui_widgets_cards import CertusCard, CertusModuleCard, CertusValueCard', 'from certus.ui.certus_ui_widgets_cards import CertusCard, FlashyCard, CertusDashboardCard')
source = source.replace('from certus.ui.certus_ui_widgets_utils import CertusThemeToggle, CertusCollapsibleBox, CertusAnimatedToggle', 'from certus.ui.certus_ui_widgets_utils import CertusToast, CertusStatusPill, CertusThemeToggle, AutoShrinkTitleLabel, CertusLogPanel, ExcelTableWidget, NumericTableWidgetItem, DetachedPlotWindow, SkeletonLoaderWidget')
ui_file.write_text(source, encoding='utf-8')
