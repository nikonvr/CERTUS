from pathlib import Path

groups = {
    'utils': [
        '_WorkerProgressCoordinator',
        '_log_manual_insert_decision', '_spl_rmse_improves_meaningfully', '_spl_rmse_regression_exceeds_tolerance',
        '_validated_extra_sigma_knots', '_should_skip_manual_insert_for_equal_mesh', '_sigma_knot_difference_for_log',
        '_sigma_knots_to_lambda_nm_for_log', '_format_lambda_knots_nm_for_log', '_sigma_mesh_change_summary_for_log',
        '_knots_cache_key', '_fmt_d_nm', '_meshes_match', '_candidate_mesh_matches_target', '_pipeline_mesh_dimensions',
        '_log_worker_start_payload', '_log_final_insert_enter', '_log_after_final_insert', '_log_fixed_mesh_stage_summary',
        '_log_after_final_stage_summary', '_emit_enter_fixed_mesh_stage', '_sync_theoretical_tr_from_nk_dict',
        '_stop_with_snapshot_if_requested', 'enforce_local_optimization_policy'
    ],
    'mesh_insert': [
        'insert_manual_sigma_nodes', 'insert_mwir_mid_sigma_node', 'worker_spline_mwir_insert_node',
        'worker_spline_manual_sigma_insert', 'worker_spline_auto_add_one_knot', '_sensitivity_rank_inner_indices',
        '_build_local_pull_variants', '_build_local_refine_variants'
    ],
    'mesh_clean': [
        'AutoCleanKnotsContext',
        '_auto_clean_cache_result', '_auto_clean_prescreen_result', '_eval_clean_variant',
        'worker_spline_auto_clean_knots', 'worker_spline_autoshift_delta_ns'
    ],
    'corridors_runner': [
        '_corridor_seg_spline_sigma_pack_matches_nominal', '_select_corridor_base_result_for_profile',
        '_resolve_corridor_mode', '_build_profile_corridor_config', '_run_corridor_profile_block',
        '_run_corridor_profile_with_optional_rerun', '_sync_promoted_corridor_seed_state',
        '_maybe_promote_best_corridor_refit', 'worker_run_corridor_profile_after_nl_choice'
    ],
    'orchestrator': [
        '_apply_k_floor_to_result', '_run_sigma_mesh_polish', 'worker_spline_optimization'
    ]
}

order = ['utils', 'mesh_insert', 'mesh_clean', 'corridors_runner', 'orchestrator']

def fix_imports():
    ui_dir = Path('certus/spline')
    file_path = ui_dir / 'spline_pipeline.py'
    content = file_path.read_text(encoding='utf-8')
    
    # Everything before the first "from .spline_pipeline_utils" is the header
    header = content.split("from .spline_pipeline_utils")[0]
    
    facade_content = header
    for group_name in order:
        items = groups[group_name]
        facade_content += f"from .spline_pipeline_{group_name} import (\n"
        for item in items:
            facade_content += f"    {item},\n"
        facade_content += ")\n"
    
    # Add __all__
    all_exports = []
    for g in groups.values():
        all_exports.extend(g)
    
    facade_content += f"\n__all__ = [\n"
    for exp in all_exports:
        facade_content += f"    '{exp}',\n"
    facade_content += "]\n"

    file_path.write_text(facade_content, encoding='utf-8')
    
    # Now, ALSO fix the sub-files so they use explicit imports instead of *
    for i, group_name in enumerate(order):
        sub_file = ui_dir / f"spline_pipeline_{group_name}.py"
        sub_content = sub_file.read_text(encoding='utf-8')
        
        # Remove all from .spline_pipeline_* import *
        lines = sub_content.split('\n')
        new_lines = []
        for line in lines:
            if line.startswith("from .spline_pipeline_") and "import *" in line:
                continue
            new_lines.append(line)
        
        # Find where to insert cross imports (after the last import from certus.*)
        # Actually we can just prepend it right after the imports block
        # For simplicity, we just rebuild cross imports as explicit
        explicit_cross_imports = ""
        for prev in range(i):
            prev_group = order[prev]
            items = groups[prev_group]
            explicit_cross_imports += f"from .spline_pipeline_{prev_group} import (\n"
            for item in items:
                explicit_cross_imports += f"    {item},\n"
            explicit_cross_imports += ")\n"
            
        # Insert explicit cross imports at the top
        final_sub_content = explicit_cross_imports + "\n" + '\n'.join(new_lines)
        sub_file.write_text(final_sub_content, encoding='utf-8')

    print("Fixed all wildcard imports to explicit imports")

if __name__ == '__main__':
    fix_imports()
