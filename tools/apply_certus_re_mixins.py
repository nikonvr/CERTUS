import ast
import json
from pathlib import Path

# Load map
map_file = Path('tools/certus_re_mixin_map.json')
categories = json.loads(map_file.read_text())

# Read original
re_file = Path('CERTUS_RE.py.bak') # Use backup to get clean original
source = re_file.read_text(encoding='utf-8')
tree = ast.parse(source)

app_class = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CertusREApp'][0]

def get_node_source(node, full_source):
    lines = full_source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    if hasattr(node, 'decorator_list') and node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    return '\n'.join(lines[start:end])

# Setup base imports
base_imports = '''from __future__ import annotations
from certus.utils.certus_re_config import RE_PHASE4_TRF_MAX_NFEV
from certus.utils.certus_re_config import RE_PHASE4_APERTURE_SCAN_POINTS
from certus.utils.certus_re_math import re_substrate_cauchy_n_re_from_theta
from certus.utils.certus_re_math import format_re_drift_log_triplet_pct
from certus.utils.certus_re_config import RE_GUI_DEFAULT_RE_QWOT_ALPHA
from certus.utils.certus_re_config import RE_P4_BEAM_AP_BOUNDS_DEG
from certus.utils.certus_re_config import RE_PHASE2_FD_MAX_WORKERS
from certus.utils.certus_re_config import RE_PHASE2_FD_PARALLEL
from certus.utils.certus_re_config import RE_PHASE2_ONESIDED_SPLINE_FD
from certus.utils.certus_re_config import RE_P4_BEAM_N_KNOTS
from certus.utils.certus_re_config import RE_RE_DEADZONE_QWOT_ABS
from certus.utils.certus_re_config import RE_RE_DEADZONE_DELTA_RE_ABS
from certus.utils.certus_re_config import RE_HL_DELTA_RE_REG_SQRT_W
import logging
import copy
import time
import os
import functools
import multiprocessing
import traceback
from pathlib import Path
import sys
from typing import Any, List, Dict
import numpy as np
import pyqtgraph as pg

from certus.core.certus_core import certus_timestamp_display, setup_logging, CFG, create_module_environment, NUMERICAL_FAULT_EXCEPTIONS, get_resource_path, certus_timestamp_file

from certus.ui.certus_qt_widgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox,
    QColor, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFont, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QKeySequence, QLabel, QMessageBox,
    QPushButton, QRadioButton, QScrollArea, QShortcut, QSplitter, QStackedWidget,
    QStatusBar, QTableWidgetItem, QTabWidget, QTextEdit, QTimer, Qt, QVBoxLayout,
    QWidget,
)

from certus_physics import Layer, ObliqueTarget, init_thickness, calc_spectrum_front_wrapper, calc_spectrum_full_exact_wrapper

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale, spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display, spectrum_eval_plot_curves,
    spectrum_eval_run_preamble, spectrum_eval_start_worker,
)

from certus.ui.certus_ui import (
    attach_excel_clipboard_context_menu, CertusBaseApp, CertusCard, CertusCollapsible,
    CertusScientificPlot, CertusStatusPill, CertusTheme, CertusThemeToggle,
    enable_file_drop, EnhancedProgressWidget, ExcelTableWidget, FlashyCard,
    get_certus_last_dir, install_standard_shortcuts, safe_ui_action,
    set_certus_last_dir, show_toast, WelcomeGuideWidget, create_flashy_grid,
    create_header_logo_widget, create_styled_button, create_styled_label,
    create_top_actions_bar, init_certus_app, set_certus_window_icon,
    install_skeleton_loader, remove_skeleton_loader, wrap_scientific_plot_with_toolbar,
    open_documentation, confirm_stop_with_timeout,
)

from certus.utils.certus_ux import build_premium_overrides
from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus.workers.certus_re_workers import REWorker
from certus.ui.certus_re_ui import CertusREResultsDialog

from certus.utils.certus_re_helpers import (
    RE_GUI_DEFAULT_BEAM_APERTURE_DEG,
    re_qwot_penalty_weight_from_preset,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    _RE_CANONICAL_SHEETS,
    _RE_FT_COL_MAT,
    _RE_FT_COL_N,
    _RE_FT_COL_NUM,
    _RE_FT_COL_QW,
    _RE_FT_COL_THICK,
    _parse_re_rmse_combined_from_progress_message,
    _re_calc_spectrum_for_config,
    _re_cell_str,
    _re_find_measurement_wavelength_column,
    _re_header_is_wavelength_label,
    _re_header_looks_like_spectrum_title,
    _re_index_column_map,
    _re_index_split_header_and_data,
    _re_measurement_values_are_percent,
    _re_p4_ap_staircase_polyline,
    _re_p4_kwargs_from_opt_result,
    _re_p4_sort_knot_pairs,
    _re_parse_design_metadata_row,
    _re_parse_design_qwot_rows,
    _re_qwot_rmse_abs_delta_at_l0,
    _re_resolve_re_workbook_sheets,
    _re_rmse_combined_spectral_qwot,
    _re_rmse_oblique_weighted,
    _re_sort_results_best_for_table_and_apply,
    format_re_spline_knots_log,
    parse_re_column_header,
    re_apply_re_index_model,
    re_delta_qwot_per_layer,
    re_drift_result_log_suffix,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
    re_n_corr_at_lambda_ref,
    TabularMaterial,
    ParsedREColumn,
)
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper
'''

ui_dir = Path('certus/ui')
ui_dir.mkdir(parents=True, exist_ok=True)

# Generate mixin files
for cat, methods in categories.items():
    mixin_name = f'CertusRE{cat}Mixin'
    filename = f'certus_re_{cat.lower()}_mixin.py'
    
    out_lines = [base_imports, '', f'class {mixin_name}:', f'    \"\"\"{mixin_name} for CERTUS_RE.\"\"\"', '']
    
    for m in methods:
        nodes = [n for n in app_class.body if isinstance(n, ast.FunctionDef) and n.name == m]
        if not nodes:
            continue
        node = nodes[0]
        
        source_code = get_node_source(node, source)
        # source_code is already correctly indented because it's extracted from inside the class block!
        out_lines.append(source_code)
        out_lines.append('')
        
    (ui_dir / filename).write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'Wrote {mixin_name} to {filename}')

print('Done extracting Mixins.')
