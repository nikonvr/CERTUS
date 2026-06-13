import ast
from pathlib import Path

groups = {
    'CertusStratLayoutMixin': [
        'apply_default_layout', '_apply_theme', '_build_log_container', '_build_gui',
        '_create_design_tab', '_create_optimization_tab', '_create_advanced_tab',
        '_create_why_certus_tab', '_create_material_group', '_create_line_edits', '_get_log_widget'
    ],
    'CertusStratStateMixin': [
        '_load_defaults', '_init_widget_states', 'set_default_values', '_save_undo_state',
        '_undo_stack_table', 'populate_gui_from_config', 'save_configuration', 'load_configuration',
        'load_external_strategies', 'collect_params', '_normalize_alias_key',
        '_resolve_strat_material_name', '_get_float_safe'
    ],
    'CertusStratEventsMixin': [
        '_init_global_shortcuts', 'timerEvent', 'on_toggle_details', 'close_all_auxiliary_windows',
        'copy_logs_to_clipboard', '_update_zoom_label', '_apply_ui_zoom', 'detach_stack_window',
        'reattach_stack_window', '_on_material_mode_changed', '_on_substrate_choice_changed',
        '_init_undo_shortcut', '_on_stack_table_changed', 'add_layer', 'remove_layer', 'closeEvent'
    ],
    'CertusStratWorkerMixin': [
        '_request_stop', 'on_stats_update', '_warmup_numba', '_warmup_numba_thread_runner',
        '_on_numba_ready_ui', '_on_numba_error_ui', 'update_stats_display', '_stop_active_render_thread',
        '_stop_worker_thread', '_thread_is_running_safe', '_register_worker_thread',
        '_unregister_worker_thread', '_stop_all_worker_threads', 'request_stop_optimization',
        'run_workflow', 'on_workflow_finished', 'on_workflow_error', 'on_progress_update',
        '_stop_all_threads_parallel'
    ],
    'CertusStratPlotMixin': [
        'on_plot_ready', 'process_plot_queue', '_compute_fig_hash', 'update_main_plot',
        '_on_render_thread_finished', '_on_render_complete', '_apply_pixmap', 'update_stack_plot',
        'on_live_growth_update', 'on_strategy_visualization_requested', 'on_show_strategies_table'
    ],
    'CertusStratExportMixin': [
        '_extract_stack_multipliers', '_validate_strat_config', '_validate_strat_gui_state',
        '_resolve_manifest_seed', '_manifest_source_paths', 'on_excel_ready', '_write_export_excel',
        '_write_export_html', '_auto_export_results'
    ]
}

def split_app():
    ui_dir = Path('certus/ui')
    file_path = ui_dir / 'certus_strat_ui.py'
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
        if isinstance(node, ast.ClassDef) and node.name == 'CertusStratApp':
            class_node = node
            first_class_line = node.lineno
            break

    if not class_node: return

    methods = {m.name: m for m in class_node.body if isinstance(m, ast.FunctionDef)}
    
    new_content_lines = lines.copy()
    
    for mixin_name, method_names in groups.items():
        mixin_file = f"certus_strat_ui_{mixin_name.replace('CertusStrat', '').replace('Mixin', '').lower()}.py"
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
        mixin_file = f"certus_strat_ui_{mixin_name.replace('CertusStrat', '').replace('Mixin', '').lower()}"
        import_block += f"from certus.ui.{mixin_file} import {mixin_name}\n"
        mixin_classes.append(mixin_name)

    final_lines = []
    import_inserted = False
    
    class_def_pattern = "class CertusStratApp("
    new_class_def = f"class CertusStratApp(CertusBaseApp, CertusWindowSpyMixin, {', '.join(mixin_classes)}):"
    
    for i, line in enumerate(new_content_lines):
        if line is not None:
            if not import_inserted and i >= first_class_line - 2:
                final_lines.extend(import_block.split('\n'))
                import_inserted = True
                
            if line.startswith(class_def_pattern):
                if 'CertusBaseApp' in line:
                    final_lines.append(new_class_def)
                    continue

            final_lines.append(line)

    file_path.write_text('\n'.join(final_lines), encoding='utf-8')
    print("Updated certus_strat_ui.py")

if __name__ == '__main__':
    split_app()
