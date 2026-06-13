import ast
import os
import sys
from pathlib import Path

def extract_classes():
    ui_dir = Path('certus/ui')
    file_path = ui_dir / 'certus_index_spline_ui.py'
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)

    first_class_line = 0
    
    classes_to_extract = {
        'SmartInitPayload': 'certus_index_spline_state_ui.py',
        'SplineState': 'certus_index_spline_state_ui.py',
        '_SmartInitState': 'certus_index_spline_state_ui.py',
        'SmartInitState': 'certus_index_spline_state_ui.py',
        
        '_ConfigBuilderMixin': 'certus_index_spline_mixins_ui.py',
        '_MeshOptimizationMixin': 'certus_index_spline_mixins_ui.py',
        '_SmartInitDialogMixin': 'certus_index_spline_mixins_ui.py',
        '_UIMixin': 'certus_index_spline_mixins_ui.py',
        
        'Step4MeshOptimizerBuilder': 'certus_index_spline_managers_ui.py',
        'SmartInitPreviewManager': 'certus_index_spline_managers_ui.py',
        
        'LiveIndexMonitor': 'certus_index_spline_monitor_ui.py'
    }

    class_nodes = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in classes_to_extract:
            class_nodes[node.name] = node
            if first_class_line == 0:
                first_class_line = node.lineno

    lines = content.split('\n')
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno
            import_lines.extend(lines[start:end])

    header = '\n'.join(import_lines) + '\n\n'

    file_to_classes = {}
    for class_name, target_file in classes_to_extract.items():
        if target_file not in file_to_classes:
            file_to_classes[target_file] = []
        file_to_classes[target_file].append(class_name)

    new_content_lines = lines.copy()
    
    for target_file, class_names in file_to_classes.items():
        target_path = ui_dir / target_file
        file_content = header
        
        for class_name in class_names:
            node = class_nodes[class_name]
            start = node.lineno - 1
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            end = node.end_lineno
            
            class_source = '\n'.join(lines[start:end])
            file_content += class_source + '\n\n'
            
            for i in range(start, end):
                new_content_lines[i] = None

        target_path.write_text(file_content, encoding='utf-8')
        print(f"Created {target_file} with {class_names}")

    import_block = ""
    for target_file, class_names in file_to_classes.items():
        module_name = target_file.replace('.py', '')
        import_block += f"from certus.ui.{module_name} import {', '.join(class_names)}\n"

    final_lines = []
    import_inserted = False
    for i, line in enumerate(new_content_lines):
        if line is not None:
            if not import_inserted and i >= first_class_line - 1:
                final_lines.extend(import_block.split('\n'))
                import_inserted = True
            final_lines.append(line)

    file_path.write_text('\n'.join(final_lines), encoding='utf-8')
    print("Updated certus_index_spline_ui.py")

if __name__ == '__main__':
    extract_classes()
