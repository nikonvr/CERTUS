import ast
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

def split_app():
    ui_dir = Path('certus/spline')
    file_path = ui_dir / 'spline_pipeline.py'
    content = file_path.read_text(encoding='utf-8')
    tree = ast.parse(content)
    lines = content.split('\n')

    # Extract Header (imports, constants, type aliases)
    header_lines = []
    
    # We want everything that is not a FunctionDef or ClassDef to be in the header.
    # We'll just collect them line by line from the AST nodes.
    header_ranges = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            # Check decorator lines, just in case
            if hasattr(node, 'decorator_list') and node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            end = node.end_lineno
            header_ranges.append((start, end))

    for start, end in header_ranges:
        header_lines.extend(lines[start:end])
        
    header = '\n'.join(header_lines) + '\n\n'

    nodes_dict = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    
    for i, group_name in enumerate(order):
        item_names = groups[group_name]
        mixin_file = f"spline_pipeline_{group_name}.py"
        target_path = ui_dir / mixin_file
        
        file_content = header
        
        # Add cross-imports
        cross_imports = ""
        for prev in range(i):
            cross_imports += f"from .spline_pipeline_{order[prev]} import *\n"
        
        file_content += cross_imports + "\n\n"
        
        has_items = False
        for name in item_names:
            if name in nodes_dict:
                has_items = True
                node = nodes_dict[name]
                start = node.lineno - 1
                if hasattr(node, 'decorator_list') and node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                end = node.end_lineno
                
                file_content += '\n'.join(lines[start:end]) + '\n\n'
            else:
                print(f"Warning: {name} not found in AST!")
        
        if has_items:
            target_path.write_text(file_content, encoding='utf-8')
            print(f"Created {mixin_file}")

    # Recreate spline_pipeline.py as a Facade
    facade_content = header
    for group_name in order:
        facade_content += f"from .spline_pipeline_{group_name} import *\n"
    
    # Add an __all__ list to avoid polluting the namespace or linter issues
    all_exports = []
    for g in groups.values():
        all_exports.extend(g)
    
    facade_content += f"\n__all__ = [\n"
    for exp in all_exports:
        facade_content += f"    '{exp}',\n"
    facade_content += "]\n"

    file_path.write_text(facade_content, encoding='utf-8')
    print("Updated spline_pipeline.py as Facade")

if __name__ == '__main__':
    split_app()
