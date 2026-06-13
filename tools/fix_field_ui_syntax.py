from pathlib import Path
ui_file = Path('certus/ui/certus_field_ui.py')
source = ui_file.read_text(encoding='utf-8')
source = source.replace('''class CertusFieldApp(
    CertusBaseApp,
    CertusFieldLayoutMixin,
    CertusFieldPlotMixin,
    CertusFieldEventsMixin,
    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):

    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):''', '''class CertusFieldApp(
    CertusBaseApp,
    CertusFieldLayoutMixin,
    CertusFieldPlotMixin,
    CertusFieldEventsMixin,
    CertusFieldWorkersMixin,
    CertusFieldStateMixin
):''')
ui_file.write_text(source, encoding='utf-8')
