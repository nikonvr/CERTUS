import ast
from pathlib import Path

ui_file = Path('certus/ui/certus_index_spline_ui.py.bak')
source = ui_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusIndexSplineApp'][0]
init_method = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'][0]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

init_code = get_node_source(init_method, source)

lines = source.splitlines()
class_start = app_class.lineno - 1
if app_class.decorator_list:
    class_start = app_class.decorator_list[0].lineno - 1

header_lines = lines[:class_start]

imports = '''from certus.ui.certus_index_spline_layout_mixin import CertusIndexSplineLayoutMixin
from certus.ui.certus_index_spline_state_mixin import CertusIndexSplineStateMixin
from certus.ui.certus_index_spline_table_mixin import CertusIndexSplineTableMixin
from certus.ui.certus_index_spline_plot_mixin import CertusIndexSplinePlotMixin
from certus.ui.certus_index_spline_events_mixin import CertusIndexSplineEventsMixin
from certus.ui.certus_index_spline_workers_mixin import CertusIndexSplineWorkersMixin'''

new_class = f'''class CertusIndexSplineApp(
    CertusBaseApp,
    CertusIndexSplineLayoutMixin,
    CertusIndexSplineStateMixin,
    CertusIndexSplineTableMixin,
    CertusIndexSplinePlotMixin,
    CertusIndexSplineEventsMixin,
    CertusIndexSplineWorkersMixin,
):
    \"\"\"CERTUS application to optimize spline parameters for a given substrate index model.\"\"\"

    APP_NAME = "CERTUS_INDEX_SPLINE"
    APP_TITLE = "CERTUS  Index Spline Optimization"
    DEFAULT_WIDTH = 1380
    DEFAULT_HEIGHT = 650
    MIN_WIDTH = 1100
    MIN_HEIGHT = 520

'''

new_class += init_code + '\n\n'

main_block_str = '''
def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusIndexSplineApp()
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
Path('certus/ui/certus_index_spline_ui.py').write_text(final_content, encoding='utf-8')
print("Successfully rewrote certus_index_spline_ui.py")
