import ast
from pathlib import Path

groups = {
    'CertusDesignLayoutMixin': [
        '_build_left_panel', '_apply_theme', '_build_materials_group', '_build_params_group',
        '_build_back_group', '_build_optim_group', '_build_action_buttons', '_build_right_panel',
        '_build_front_table_widget', '_build_target_table_widget', '_build_status_bar'
    ],
    'CertusDesignStateMixin': [
        '_load_defaults', '_pre_save_smart_cleanup', '_post_save_config', '_collect_config',
        '_apply_config', '_apply_optimization_config', '_apply_material_config', '_apply_target_config',
        '_apply_stack_rows', '_post_load_config', 'reset_to_defaults'
    ],
    'CertusDesignEventsMixin': [
        '_setup_shortcuts', '_toggle_back_stack', '_on_qwot_changed_connection', '_on_tikhonravov_points_changed',
        '_on_layer_added', '_on_layer_deleted', 'add_back_layer', 'del_back_layer', 'remove_thinnest',
        '_paste_from_excel', 'add_target', 'del_target', 'open_help', 'closeEvent'
    ],
    'CertusDesignWorkerMixin': [
        'run_eval', '_on_eval_finished', 'run_optim', '_on_optim_progress', '_on_stats_update',
        '_on_optim_done', 'run_colorimetry', '_on_col_done', 'stop_optim'
    ],
    'CertusDesignExportMixin': [
        'export_results', '_export_results_excel', '_export_results_html', '_build_export_manifest',
        '_is_export_manifest_complete', '_sync_export_result_with_best_eval', '_prepare_export_paths',
        'export_excel'
    ],
    'CertusDesignOptimizationMixin': [
        '_handle_stopped_workflow_result', '_finalize_if_post_optim_budget_exceeded', '_track_and_apply_post_optim_result',
        '_handle_needle_cycle_step3', '_maybe_start_needle_growth', '_handle_decimation_polish_completion',
        '_handle_smart_decimation_followup', '_run_post_optim_cleanup', '_handle_healing_workflow',
        '_finalize_completed_optimization_workflow', '_initialize_smart_decimation_session',
        '_smart_decimation_remove_and_optimize', '_apply_smart_decimation_post_removal_state',
        '_should_stop_smart_decimation_step', '_select_smart_decimation_remove_index', '_on_smart_decimation_optim_done',
        '_apply_smart_decimation_optim_result', '_record_smart_decimation_candidate', '_abort_on_smart_decimation_degradation',
        '_log_smart_decimation_step_result', '_restore_smart_decimation_origin', '_clear_smart_decimation_state',
        '_log_smart_decimation_completion', '_finish_smart_decimation', '_finalize_smart_decimation_post_actions',
        '_decimation_remove_and_polish', '_on_decimation_polish_done', '_drop_thinnest_and_polish', '_apply_5nm_minimum',
        '_save_table_state', '_restore_table_state', '_revert_to_checkpoint', 'smart_cleanup', '_prune_to_target',
        '_needle_thresholds', '_needle_gain_is_significant', '_start_needle_process', '_on_needle_found',
        '_handle_needle_no_candidate', '_handle_needle_no_candidate_below_target', '_abort_needle_after_failed_retries',
        '_maybe_prune_needle_overshoot', '_apply_needle_split_insertion', '_insert_needle_split_row',
        '_insert_right_split_row', '_clear_needle_cycle_state', '_clear_needle_search_state'
    ],
    'CertusDesignCoreMixin': [
        '_get_default_splitter_sizes', '_get_substrate_info_display', '_show_substrate_info_window',
        '_toggle_oblique_mode', 'copy_logs_to_clipboard', '_apply_preset', '_on_schedule_eval_signal',
        '_on_schedule_eval_instant_signal', '_trigger_post_undo_action', '_get_optim_wls', '_update_optim_point_count',
        '_calculate_tikhonravov_points', '_update_tikhonravov_points', '_get_materials', '_get_oblique_tgts',
        '_load_targets_to_table', '_on_front_thickness_updated', '_reset_run_optim_workflow_state',
        '_shutdown_previous_optim_worker', '_collect_run_optim_inputs', '_initialize_run_optim_progress_state',
        '_refresh_optim_target_scatter_foreground', '_apply_qw_values_to_front_table', 'on_stats_update',
        'update_stats_display', '_update_busy_ui'
    ]
}

def split_app():
    ui_dir = Path('certus/ui')
    file_path = ui_dir / 'certus_design_ui.py'
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
        if isinstance(node, ast.ClassDef) and node.name == 'CertusDesignApp':
            class_node = node
            first_class_line = node.lineno
            break

    if not class_node: return

    methods = {m.name: m for m in class_node.body if isinstance(m, ast.FunctionDef)}
    
    new_content_lines = lines.copy()
    
    for mixin_name, method_names in groups.items():
        mixin_file = f"certus_design_ui_{mixin_name.replace('CertusDesign', '').replace('Mixin', '').lower()}.py"
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
        mixin_file = f"certus_design_ui_{mixin_name.replace('CertusDesign', '').replace('Mixin', '').lower()}"
        import_block += f"from certus.ui.{mixin_file} import {mixin_name}\n"
        mixin_classes.append(mixin_name)

    final_lines = []
    import_inserted = False
    
    # We need to change the class signature
    # from: class CertusDesignApp(CertusBaseApp, CertusDesignUIPlotMixin):
    # to: class CertusDesignApp(CertusBaseApp, CertusDesignUIPlotMixin, Mixin1, Mixin2...):
    class_def_pattern = "class CertusDesignApp("
    new_class_def = f"class CertusDesignApp(CertusBaseApp, CertusDesignUIPlotMixin, {', '.join(mixin_classes)}):"
    
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
    print("Updated certus_design_ui.py")

if __name__ == '__main__':
    split_app()
