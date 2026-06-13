from pathlib import Path
import ast
import json

ui_file = Path('certus/ui/certus_index_spline_ui.py')
source = ui_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusIndexSplineApp'][0]
methods = [n for n in app_class.body if isinstance(n, ast.FunctionDef)]

# Categorize
categories = {
    'Layout': [
        '_get_default_splitter_sizes', '_build_left_panel', '_apply_theme',
        '_build_mode_selector', '_build_optimization_config', '_build_spline_options',
        '_build_control_points_group', '_build_action_buttons', '_build_right_panel',
        '_build_status_bar', '_setup_shortcuts', '_build_info_overlay'
    ],
    'State': [
        'reset_to_defaults', '_load_defaults', '_update_busy_ui', '_update_zoom_label',
        '_apply_ui_zoom', '_on_opt_mode_changed', '_trigger_post_undo_action',
        'closeEvent', '_show_substrate_info_window'
    ],
    'Table': [
        '_get_spline_table_cols', '_refresh_cp_table', '_on_cp_changed_connection',
        '_add_cp_row', '_delete_cp_row', '_get_control_points', '_update_cp_table_from_state',
        '_paste_cp_from_excel', '_get_materials', '_get_oblique_tgts', '_get_plot_info'
    ],
    'Plot': [
        '_init_plot_factors', '_on_update_spectrum_y_scale_signal', '_plot_profile',
        '_plot_nk', '_update_spectrum_title', '_show_delta_qwot_plot'
    ],
    'Events': [
        '_on_l0_changed_update_substrate_info', '_on_schedule_eval_signal',
        '_on_schedule_eval_instant_signal', '_on_eval_finished',
        'run_eval', 'launch_optimization', 'stop_optimization',
        '_on_opt_progress', '_on_opt_result', '_on_opt_done',
        '_compute_spline_rmse', '_apply_workflow_rmse_if_better',
        '_update_status_bar_stats', '_best_rmse_label_text'
    ],
    'Workers': [
        'build_worker_cfg'
    ]
}

all_categorized = []
for k, v in categories.items():
    all_categorized.extend(v)

uncategorized = []
for m in methods:
    if m.name != '__init__' and m.name not in all_categorized:
        uncategorized.append(m.name)

# Some extra methods might be in there, so let's automatically put uncategorized in 'Events' or 'Layout'.
if uncategorized:
    categories['Events'].extend(uncategorized)
    print("Added to Events:", uncategorized)

out = Path('tools/certus_index_spline_mixin_map.json')
out.write_text(json.dumps(categories, indent=2))
print('Spline Mixin Map saved.')
