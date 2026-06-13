import ast
from pathlib import Path

re_file = Path('CERTUS_RE.py')
source = re_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusREApp'][0]
init_method = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'][0]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

init_code = get_node_source(init_method, source)

# Find the start of the class definition
lines = source.splitlines()
class_start = app_class.lineno - 1
if app_class.decorator_list:
    class_start = app_class.decorator_list[0].lineno - 1

# Header lines
header_lines = lines[:class_start]

imports = '''from certus.ui.certus_re_layout_mixin import CertusRELayoutMixin
from certus.ui.certus_re_state_mixin import CertusREStateMixin
from certus.ui.certus_re_table_mixin import CertusRETableMixin
from certus.ui.certus_re_plot_mixin import CertusREPlotMixin
from certus.ui.certus_re_excel_mixin import CertusREExcelMixin
from certus.ui.certus_re_workers_mixin import CertusREWorkersMixin'''

new_class = f'''class CertusREApp(
    CertusBaseApp,
    CertusRELayoutMixin,
    CertusREStateMixin,
    CertusRETableMixin,
    CertusREPlotMixin,
    CertusREExcelMixin,
    CertusREWorkersMixin,
):
    \"\"\"CERTUS application  reverse engineering (Excel measurements).\"\"\"

    APP_NAME = "CERTUS_RE"
    APP_TITLE = "CERTUS  Reverse Engineering"
    DEFAULT_WIDTH = 1440
    DEFAULT_HEIGHT = 640
    MIN_WIDTH = 1020
    MIN_HEIGHT = 520

'''

indented_init = '\n'.join('    ' + line for line in init_code.splitlines())
new_class += indented_init + '\n\n'

# Add the main block
main_block_str = '''
def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusREApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
'''

final_content = '\n'.join(header_lines) + '\n\n' + imports + '\n\n' + new_class + main_block_str
re_file.write_text(final_content, encoding='utf-8')
print("Successfully rewrote CERTUS_RE.py")
