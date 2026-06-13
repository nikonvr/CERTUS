import ast
import os
import sys
from pathlib import Path

def extract_classes():
    ui_dir = Path('certus/ui')
    file_path = ui_dir / 'certus_strat_ui.py'
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)

    # 1. Extract Header (imports and global assignments before the first major class)
    # Let's find the first class that we are extracting
    first_class_line = 0
    
    classes_to_extract = {
        'CertusWindowSpyMixin': 'certus_strat_mixins_ui.py',
        'StrategiesTableWindow': 'certus_strat_table_ui.py',
        'CertusScientificPlot': 'certus_strat_plots_ui.py',
        'UniversalPlotWindow': 'certus_strat_plots_ui.py',
        'InteractiveHeatmapWindow': 'certus_strat_heatmap_ui.py',
        'TransmissionVsThicknessWindow': 'certus_strat_thickness_ui.py',
        'StrategySpectralPerformanceWindow': 'certus_strat_performance_ui.py',
        'JsonViewerWindow': 'certus_strat_json_ui.py',
        'InteractiveIndicesWindow': 'certus_strat_indices_ui.py',
        'InteractiveSpectrumWindow': 'certus_strat_spectrum_ui.py',
        'PopOutWindow': 'certus_strat_popout_ui.py',
        'LiveMonitorWindow': 'certus_strat_monitor_ui.py',
        'WelcomeGuideWidget': 'certus_strat_welcome_ui.py'
    }

    # First, let's locate line numbers
    class_nodes = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in classes_to_extract:
            class_nodes[node.name] = node
            if first_class_line == 0:
                first_class_line = node.lineno

    # Get the global header
    lines = content.split('\n')
    # Let's be safer: get all imports
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # get source code for this import
            start = node.lineno - 1
            end = node.end_lineno
            import_lines.extend(lines[start:end])

    header = '\n'.join(import_lines) + '\n\n'

    # Now group classes by target file
    file_to_classes = {}
    for class_name, target_file in classes_to_extract.items():
        if target_file not in file_to_classes:
            file_to_classes[target_file] = []
        file_to_classes[target_file].append(class_name)

    # Remove classes from original content and replace with imports
    # We must do this backwards to not mess up line numbers, or just reconstruct
    new_content_lines = lines.copy()
    
    # We will build the new files
    for target_file, class_names in file_to_classes.items():
        target_path = ui_dir / target_file
        file_content = header
        
        # If this file needs CertusWindowSpyMixin and it's not the mixins file, import it
        if target_file != 'certus_strat_mixins_ui.py':
            file_content += 'from certus.ui.certus_strat_mixins_ui import CertusWindowSpyMixin\n\n'

        for class_name in class_names:
            node = class_nodes[class_name]
            start = node.lineno - 1
            # Handle decorators
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            end = node.end_lineno
            
            # Extract source
            class_source = '\n'.join(lines[start:end])
            file_content += class_source + '\n\n'
            
            # Blank out the lines in original file
            for i in range(start, end):
                new_content_lines[i] = None

        target_path.write_text(file_content, encoding='utf-8')
        print(f"Created {target_file} with {class_names}")

    # Now add imports to original file
    # Where to add? Right after the imports.
    import_block = ""
    for target_file, class_names in file_to_classes.items():
        module_name = target_file.replace('.py', '')
        import_block += f"from certus.ui.{module_name} import {', '.join(class_names)}\n"

    # Filter out None lines
    final_lines = []
    import_inserted = False
    for i, line in enumerate(new_content_lines):
        if line is not None:
            if not import_inserted and i >= first_class_line - 1:
                final_lines.extend(import_block.split('\n'))
                import_inserted = True
            final_lines.append(line)

    file_path.write_text('\n'.join(final_lines), encoding='utf-8')
    print("Updated certus_strat_ui.py")

if __name__ == '__main__':
    extract_classes()
