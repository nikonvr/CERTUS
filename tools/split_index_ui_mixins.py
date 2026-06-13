import ast
import os
from pathlib import Path

groups = {
    'CertusIndexLayoutMixin': [
        '_apply_theme', '_build_ui', '_add_main_control_buttons', '_build_log_container',
        '_create_input_group', '_create_substrate_group', '_create_config_group', '_create_status_bar',
        '_get_log_widget'
    ],
    'CertusIndexStateMixin': [
        '_load_defaults', '_restore_index_weight_settings', '_persist_index_weight_settings',
        '_wire_index_weight_persistence', '_get_config_file_filter', '_collect_config',
        '_normalize_index_config', '_apply_config', '_post_save_config', '_post_load_config',
        '_reset_optimization_progress_state'
    ],
    'CertusIndexEventsMixin': [
        '_setup_shortcuts', '_update_zoom_status', '_apply_ui_zoom', '_on_substrate_mode_changed',
        '_on_substrate_changed', '_on_absorbing_sub_toggled', '_on_import_ksub', '_auto_detect_from_file',
        '_toggle_exclude', '_update_plot_exclusion', '_toggle_oh_band', 'load_file',
        '_apply_dynamic_ir_smoothing', '_ask_keep_raw_or_smoothed', 'detach_current_plot', 'on_toggle_details',
        'closeEvent'
    ],
    'CertusIndexWorkerMixin': [
        '_warmup_numba', '_warmup_numba_thread_runner', '_on_numba_ready_ui', '_on_numba_error_ui',
        '_configure_and_start_optimization_worker', '_abort_run_optimization',
        '_resolve_substrate_absorption_inputs', 'run_optimization', 'stop_optimization',
        '_cleanup_worker', '_on_thread_finished', '_on_evals_update', '_on_progress', '_on_error',
        '_on_curve_update', '_on_finished', '_on_tlu_constrained_finished'
    ],
    'CertusIndexPlotMixin': [
        '_plot_raw_and_smoothed_preview', '_redraw_target_preview', '_try_add_spectrum_tracked_curve',
        '_clear_plot_tracking_state', '_update_spectrum_plot', '_update_nk_plot'
    ],
    'CertusIndexExportMixin': [
        '_make_index_tlu_live_ctx', '_index_tlu_live_payload_from_params', '_apply_index_live_plot_payload',
        '_update_model_text', '_update_data_table', '_display_results', '_copy_nk_to_clipboard',
        '_copy_params_to_clipboard', '_copy_eq_to_clipboard', '_build_uncertainty_content',
        '_export_results_html', 'export_results', 'copy_logs_to_clipboard'
    ]
}

def split_app():
    ui_dir = Path('certus/ui')
    file_path = ui_dir / 'certus_index_ui.py'
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)
    lines = content.split('\n')

    # Get imports
    import_lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno
            import_lines.extend(lines[start:end])
    header = '\n'.join(import_lines) + '\n\n'

    class_node = None
    first_class_line = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'CertusIndexApp':
            class_node = node
            first_class_line = node.lineno
            break

    if not class_node: return

    methods = {m.name: m for m in class_node.body if isinstance(m, ast.FunctionDef)}
    
    new_content_lines = lines.copy()
    
    for mixin_name, method_names in groups.items():
        mixin_file = f"certus_index_ui_{mixin_name.replace('CertusIndex', '').replace('Mixin', '').lower()}.py"
        target_path = ui_dir / mixin_file
        
        file_content = header
        file_content += f"class {mixin_name}:\n"
        
        has_methods = False
        for m_name in method_names:
            if m_name in methods:
                has_methods = True
                m_node = methods[m_name]
                start = m_node.lineno - 1
                if m_node.decorator_list:
                    start = m_node.decorator_list[0].lineno - 1
                end = m_node.end_lineno
                
                # Replace with None in original file
                for i in range(start, end):
                    new_content_lines[i] = None
                
                file_content += '\n'.join(lines[start:end]) + '\n\n'
        
        if has_methods:
            target_path.write_text(file_content, encoding='utf-8')
            print(f"Created {mixin_file}")

    # Update original file
    import_block = ""
    mixin_classes = []
    for mixin_name in groups.keys():
        mixin_file = f"certus_index_ui_{mixin_name.replace('CertusIndex', '').replace('Mixin', '').lower()}"
        import_block += f"from certus.ui.{mixin_file} import {mixin_name}\n"
        mixin_classes.append(mixin_name)

    final_lines = []
    import_inserted = False
    
    # We need to change the class signature
    # from: class CertusIndexApp(CertusBaseApp):
    # to: class CertusIndexApp(CertusBaseApp, Mixin1, Mixin2...):
    class_def_pattern = "class CertusIndexApp("
    new_class_def = f"class CertusIndexApp(CertusBaseApp, {', '.join(mixin_classes)}):"
    
    for i, line in enumerate(new_content_lines):
        if line is not None:
            if not import_inserted and i >= first_class_line - 2:
                final_lines.extend(import_block.split('\n'))
                import_inserted = True
                
            if line.startswith(class_def_pattern):
                # Simple replacement assuming CertusIndexApp(CertusBaseApp): is on one line
                if 'CertusBaseApp' in line:
                    final_lines.append(new_class_def)
                    continue

            final_lines.append(line)

    file_path.write_text('\n'.join(final_lines), encoding='utf-8')
    print("Updated certus_index_ui.py")

if __name__ == '__main__':
    split_app()
