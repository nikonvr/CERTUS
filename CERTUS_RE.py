# =============================================================================

# CERTUS REVERSE ENGINEERING MODULE

# Functional area: Post-deposition Analysis & Drift Correction

# =============================================================================

#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# =========================================================================================

# ARCHITECTURE: MONOLITHIC HYBRID (GUI + LOGIC)

# This file intentionally combines GUI, Workers, and Logic for performance and simplicity.

# P1 boundary: only make small, reversible changes here until dedicated tests cover
# worker phases, result formatting, and critical reverse-engineering flows.
# Prefer extracting pure helpers before moving Qt classes or numerical kernels.

# DO NOT REFACTOR INTO SUBMODULES WITHOUT EXPLICIT AUTHORIZATION.

# =========================================================================================

"""

CERTUS-RE.py - Reverse Engineering & Drift Correction

=========================================================

"""

from __future__ import annotations
#Numba configuration BEFORE any import pulling @njit (see CERTUS_HUB.py).
#Without this call, NUMBA_CACHE_DIR is not defined and the JIT cache is written next to it
#sources, in the cloud synchronized folder -> repeated recompilations.
from certus.core.certus_core import configure_numba_env as _configure_numba_env

_configure_numba_env()

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
from certus.utils.certus_re_config import RE_SUB_CAUCHY_TUBE_DELTA

from certus.core.certus_core import __version__, APP_SUITE_VERSION

# RE: +/-% thickness search radius for L-BFGS-B (no toolbar control; fixed default).
# Keeping this module tight: prefer helpers/tests over broad structural moves.

import logging
import copy
import time

import os
import functools
import multiprocessing

from pathlib import Path
import sys
import traceback
from typing import Any, List, Dict

from certus.core.certus_core import certus_timestamp_display, setup_logging

import numpy as np

import pyqtgraph as pg

from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFont,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequence,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QShortcut,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
)

from certus_physics import (  # TMM, targets, RMSE (same bundle as `certus_re_helpers`)
    Layer,
    ObliqueTarget,
    init_thickness,
    calc_spectrum_front_wrapper,
    calc_spectrum_full_exact_wrapper,
)

from certus.workers.certus_spectral_workers import EvalWorker, WarmupWorker

from certus.ui.certus_spectrum_eval_ui import (
    spectrum_eval_apply_axes_legend_scale,
    spectrum_eval_build_worker_cfg,
    spectrum_eval_on_finished_prepare_display,
    spectrum_eval_plot_curves,
    spectrum_eval_run_preamble,
    spectrum_eval_start_worker,
)

from certus.ui.certus_ui import (
    attach_excel_clipboard_context_menu,
    CertusBaseApp,
    CertusCard,
    CertusCollapsible,
    CertusScientificPlot,
    CertusStatusPill,
    CertusTheme,
    CertusThemeToggle,
    enable_file_drop,
    EnhancedProgressWidget,
    ExcelTableWidget,
    FlashyCard,
    get_certus_last_dir,
    install_standard_shortcuts,
    safe_ui_action,
    set_certus_last_dir,
    show_toast,
    WelcomeGuideWidget,
    create_flashy_grid,
    create_header_logo_widget,
    create_styled_button,
    create_styled_label,
    create_top_actions_bar,
    init_certus_app,
    set_certus_window_icon,
    install_skeleton_loader,
    remove_skeleton_loader,
    wrap_scientific_plot_with_toolbar,
    open_documentation,
    confirm_stop_with_timeout,
)

from certus.core.certus_core import (
    CFG,
    create_module_environment,
    NUMERICAL_FAULT_EXCEPTIONS,
    get_resource_path,
    certus_timestamp_file,
)

from certus.utils.certus_ux import build_premium_overrides

from certus.utils.certus_data import OPENPYXL_AVAILABLE
from certus.workers.certus_re_workers import REWorker


# =============================================================================

# BOOTSTRAP - Centralized app initialization

# =============================================================================

env = create_module_environment(__file__, "CERTUS_RE")

script_dir = env["script_dir"]

# =============================================================================

# FURTHER IMPORTS

# =============================================================================


# RE helpers: explicit re-exports (ARCH-1; replaced the legacy for-loop that copied certus_re_helpers into globals()).

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

# Configure GUI

# Conditional Excel Import (OPENPYXL_AVAILABLE used elsewhere in module)

# =============================================================================

# LOGGING CONFIGURATION

# =============================================================================

# Logger initialized in CertusREApp

# This ensures consistency with other CERTUS modules

# script_dir already set by bootstrap_app()

# =============================================================================

# AUTOMATIC PRECISION ADAPTATION

# =============================================================================

# Use wrappers if single precision enabled

# Wrappers enforce (d,n) consistency with CFG single-precision when enabled.

calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper

# =========================================================================================

# [MONOLITHIC BLOCK] WORKER THREADS

# DO NOT SPLIT - High coupling required for performance/state management

# =========================================================================================

# =============================================================================

# WORKERS (REWorker below; warmup + spectral eval in certus_spectral_workers)

# =============================================================================


from certus.ui.certus_re_ui import CertusREResultsDialog



from certus.ui.certus_re_layout_mixin import CertusRELayoutMixin
from certus.ui.certus_re_state_mixin import CertusREStateMixin
from certus.ui.certus_re_table_mixin import CertusRETableMixin
from certus.ui.certus_re_plot_mixin import CertusREPlotMixin
from certus.ui.certus_re_excel_mixin import CertusREExcelMixin
from certus.ui.certus_re_workers_mixin import CertusREWorkersMixin

class CertusREApp(
    CertusRELayoutMixin,
    CertusREStateMixin,
    CertusRETableMixin,
    CertusREPlotMixin,
    CertusREExcelMixin,
    CertusREWorkersMixin,
    CertusBaseApp,
):
    """CERTUS application  reverse engineering (Excel measurements)."""

    APP_NAME = "CERTUS_RE"
    APP_TITLE = "CERTUS  Reverse Engineering"
    DEFAULT_WIDTH = 1440
    DEFAULT_HEIGHT = 640
    MIN_WIDTH = 1020
    MIN_HEIGHT = 520

    def __init__(self):
        """Initialize CERTUS_RE (reverse engineering, Excel input, evaluation + REWorker)."""

        super().__init__()

        # Setup logger (uses base class log_queue)

        self._setup_logger(self.APP_NAME)

        # Shared state with base (tables, spectrum)

        self.target_widgets: List = []

        self.ep_current: np.ndarray | None = None

        self.last_result: Dict = {}

        self._best_eval_result: Dict | None = None

        self._best_eval_rmse: float = float("inf")

        self.target_scatter = None

        self._live_curve = None

        self._live_points = None

        self._initial_cleared = False

        self.detached_window = None

        self.eval_timer = None

        self._current_eval_generation = 0

        # Oblique mode

        self.oblique_mode = False

        # Workers (RE: spectral evaluation + REWorker only)

        self.eval_worker: EvalWorker | None = None

        self._re_worker: REWorker | None = None

        self.warmup_worker: WarmupWorker | None = None

        self.accumulated_evals = 0

        self._re_nfev_cumulative = 0  # cumulative RE nfev for the Evals bar

        self._warmup_done = False

        self._re_loaded = False  # True after a successful load_reverse_engineering()

        self._re_workbook_path: str | None = None  # last loaded RE .xlsx (logs / worker cfg)

        self._re_mode_active = False  # True while a RE optimization is running

        self._re_tabular_H: TabularMaterial | None = None

        self._re_tabular_L: TabularMaterial | None = None

        self._re_tabular_Sub: TabularMaterial | None = None

        self._re_targets: list = []  # full ObliqueTarget list (not in widget) for RE

        self._re_meas_lambda_min_nm: float | None = None

        self._re_meas_lambda_max_nm: float | None = None

        self._re_opt_a_pct = 0.0

        self._re_opt_b_pct = 0.0

        self._re_opt_f_pct = 0.0

        self._re_spline_dH: np.ndarray | None = None

        self._re_spline_dL: np.ndarray | None = None

        self._re_spline_lam2_nm: float | None = None

        self._re_sub_cauchy_a0: float | None = None

        self._re_sub_cauchy_a1: float | None = None

        self._re_sub_cauchy_a2: float | None = None

        # n(lambda) preview during REWorker (corrected indices = same *correc* as live spectrum)

        self._re_nk_preview_dH: list[float] | None = None

        self._re_nk_preview_dL: list[float] | None = None

        self._re_nk_preview_lam2: float | None = None

        self._re_nk_preview_sub012: list[float] | None = None

        self._re_backside_summary_html: str = ""

        # Phase 4 (beam): last best result applied aligns RMSE / UI evaluation on the P4 fit.

        self._re_p4_display_beam_active: bool = False

        self._re_p4_display_ap_knots_deg: np.ndarray | None = None

        self._re_p4_display_ap_knots_nm: np.ndarray | None = None

        # Last RE results table snapshot (Run RE)  reopened via "Display results".

        self._re_last_results_snapshot: dict[str, Any] | None = None

        # After an RE Run: alpha QWOT phase 2b (aligns _compute_re_rmse with the worker).

        self._re_rmse_qwot_alpha_ref: float | None = None

        # Last alpha emitted live: change -> reset of the status bar best RMSE (comparable metric).

        self._re_last_live_alpha_qwot: float | None = None

        # RE Options (initialised before UI)

        self.cfg: dict[str, Any] = {}

        # Theme Application

        CertusTheme.apply_to_app(QApplication.instance())

        # UI Construction

        self._build_ui()

        self._setup_shortcuts()

        self._load_defaults()

    def _get_optim_wls(self) -> np.ndarray:
        if self._re_targets and len(self._re_targets) > 0:
            return self._re_targets[0].wls
        return np.array([])

        # Warmup JIT

        self.status_label.setText("Compiling JIT kernels...")

        self.warmup_worker = WarmupWorker()

        self.warmup_worker.finished.connect(self._on_warmup_done)

        self.warmup_worker.start()


def main():
    import sys
    from certus.ui.certus_ui import init_certus_app

    app = init_certus_app()
    certus_app = CertusREApp()
    certus_app.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        print(f"Exception during execution: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
