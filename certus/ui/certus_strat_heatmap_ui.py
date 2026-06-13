import sys
import os
import functools
from pathlib import Path
import concurrent.futures
import multiprocessing
import ctypes
import hashlib
import io
import json
import logging
import queue
import threading
import time
import traceback
from collections import deque
from typing import Any, Dict
from dataclasses import dataclass
import numpy as np
import pandas as pd
from pydantic import ValidationError
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter, SVGExporter
from certus.ui.certus_plot import CertusScientificPlot
from certus.ui.certus_ui import setup_pyqtgraph_defaults
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QPixmap,
    QShortcut,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsRectItem,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_MAPPING,
    get_export_config,
    get_resource_path,
    get_safe_worker_count,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
    __version__,
)
from certus.utils.certus_data import (
    OPENPYXL_AVAILABLE,
    PerformanceMonitor,
    SharedArrayManager,
    SharedArrayWorker,
    SharedIndicesManager,
    SharedIndicesWorker,
    TimingLogger,
    generate_html_report,
    get_missing_manifest_fields,
    numpy_encoder,
    to_csv_robust,
    to_excel_robust,
)
from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    calculate_RT_vectorized_real_HL,
    compute_batch_rmse,
    find_nucleation_adaptive_kernel,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    update_run_states_kernel,
    validate_wavelengths_batch,
)
from certus.utils.certus_strat_context import (
    StratContext,
    get_context,
    SYM_MISSING_DISTANCE,
    FAST_AUTO_BLOCKS_DIVIDER_PRESETS,
    _clamp01,
    _compute_local_extrema_symmetry_score,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_contractual,
    _compute_blocks_range_for_params,
    _validate_strategy_blocks_contract,
    _augment_solution_cost_with_sym,
    _origin_family,
    _parse_origin_priority_map,
    _origin_priority_from_map,
    _apply_family_diversity,
    _blocks_signature,
    _strategy_signature,
    _strategy_id_sort_token,
    _extract_rmse_p95_for_noise,
    _dedupe_preserve_order_int,
    _default_consensus_seeds,
    _resolve_consensus_top_k,
    _resolve_consensus_num_seeds,
    _resolve_consensus_seed_stride,
    _resolve_consensus_num_runs,
)
from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO
from certus.core.certus_strat_core import (
    APP_CONTEXT,
    _compute_strategy_symmetry_score_percent,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    SYM_DEFAULT_WEIGHT,
    SYM_DEFAULT_SAME_WL_BONUS,
    SYM_DEFAULT_CONTINUITY_WEIGHT,
    SYM_DEFAULT_TIE_EPS_ABS,
    SYM_DEFAULT_TIE_EPS_REL,
    SYM_DEFAULT_SCORING_MODE,
    _SPECTRUM_COUNTER,
    PlotCache,
    precompute_clues_and_matrices,
    set_robust_material_db,
)
from certus.ui.certus_plot import CertusScientificPlot
from certus.ui.certus_ui import (
    CERTUS_UI_STRINGS,
    CertusBaseApp,
    CertusLogPanel,
    CertusTheme,
    CertusThemeToggle,
    CertusCard,
    CertusStatusPill,
    ExcelTableWidget,
    FlashyCard,
    NumericTableWidgetItem,
    apply_certus_theme,
    attach_excel_clipboard_context_menu,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    CertusAppLogsMixin,
    copy_plot_to_clipboard_excel,
    create_header_logo_widget,
    create_top_actions_bar,
    get_certus_last_dir,
    get_export_settings,
    init_certus_app,
    open_documentation,
    open_file_explorer,
    plot_dataframe_from_widget,
    set_certus_last_dir,
    set_certus_window_icon,
    create_styled_button,
    install_standard_shortcuts,
    enable_file_drop,
    show_toast,
    safe_ui_action,
)
from certus.ui.certus_ui_shared import apply_app_zoom
from certus.utils.certus_export import show_copy_excel_feedback
from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.workers.certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
from certus.workers.certus_strat_workers import (
    _resolve_strat_indices_db_path,
    WorkerThread,
    PlotRenderWorker,
    StratTask,
)
import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import (
    StratStrategyService,
    calculate_nominal_properties,
    calculate_RT_normal_real,
    calculate_dynamics_ULTIMATE,
    _select_candidates_phase_a,
    _validate_candidates_phase_a as _service_validate_candidates_phase_a,
    compute_probe_offset_nm_from_ratio,
    generate_noise_array,
    NOISE_DISTRIBUTION_GAUSSIAN,
    select_best_strat_result,
    extract_best_rmse,
    rebuild_visualization_context,
    simulate_detailed_growth_for_ui,
    simulate_spectral_distribution_for_ui,
)

from certus.ui.certus_strat_mixins_ui import CertusWindowSpyMixin

class InteractiveHeatmapWindow(QWidget):  # <--- Changement ici: QWidget au lieu de QMainWindow
    def __init__(self, parent, raw_data_thickness) -> Any:

        super().__init__(parent)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = CertusScientificPlot(self, "Design Heatmap", "Wavelength (nm)", "Layer Number")

        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Add widget to layout

        attach_excel_clipboard_context_menu(self.plot_widget)

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        if not raw_data_thickness:
            return

        self.layers = sorted(raw_data_thickness.keys())

        self.num_layers = len(self.layers)

        all_wls = set()

        for res_list in raw_data_thickness.values():
            for item in res_list:
                all_wls.add(item["wl"])

        self.sorted_wls = sorted(list(all_wls))

        if not self.sorted_wls:
            return

        wl_map = {wl: i for i, wl in enumerate(self.sorted_wls)}

        max_layer_idx = max(self.layers) if self.layers else 0
        grid = np.full((max_layer_idx + 1, len(self.sorted_wls)), np.nan, dtype=np.float64)

        path_x, path_y = [], []

        for l_idx in self.layers:
            items = raw_data_thickness.get(l_idx, [])

            if items:
                for item in items:
                    w_idx = wl_map.get(item["wl"])

                    if w_idx is not None:
                        grid[l_idx, w_idx] = item["cost"]

                best = min(items, key=lambda x: x["cost"])

                path_x.append(l_idx + 0.5)

                path_y.append(best["wl"])

        max_val = 1.0
        if np.any(np.isfinite(grid)):
            max_val = float(np.nanmax(grid))
        grid_filled = np.nan_to_num(grid, nan=max_val)

        valid_mask = np.isfinite(grid) & (grid > 0)

        if valid_mask.any():
            log_vals = np.log10(grid[valid_mask])

            vmin, vmax = np.percentile(log_vals, 2), np.percentile(log_vals, 98)

            denom = vmax - vmin if vmax != vmin else 1.0

            grid_norm = np.clip((np.log10(grid_filled) - vmin) / denom, 0, 1)

        else:
            grid_norm = np.zeros_like(grid)

        self.img_item = pg.ImageItem(grid_norm)

        # Palette de couleurs (Magma-ish)

        pos = np.linspace(0, 1, 5)

        color = np.array(
            [
                [15, 23, 42, 255],
                [60, 20, 80, 255],
                [180, 40, 80, 255],
                [250, 140, 50, 255],
                [252, 250, 230, 255],
            ],
            dtype=np.ubyte,
        )

        cmap = pg.ColorMap(pos, color)

        self.img_item.setLookupTable(cmap.getLookupTable(0.0, 1.0, 256))

        y0 = self.sorted_wls[0]

        y_range = self.sorted_wls[-1] - y0

        y_scale = y_range / len(self.sorted_wls) if len(self.sorted_wls) > 0 else 1.0

        tr = QTransform()

        tr.translate(0, y0)

        tr.scale(1, y_scale)

        self.img_item.setTransform(tr)

        self.plot_widget.addItem(self.img_item)

        if path_x:
            # Step Plot Construction

            step_x, step_y = [], []

            step_x.append(path_x[0])

            step_y.append(path_y[0])

            for i in range(1, len(path_x)):
                step_x.append(path_x[i])

                step_y.append(path_y[i - 1])

                step_x.append(path_x[i])

                step_y.append(path_y[i])

            self.plot_widget.plot(step_x, step_y, pen=pg.mkPen("c", width=3), name="Optimal Strategy")

        self.plot_widget.setXRange(0, self.num_layers)

        self.plot_widget.setYRange(y0, self.sorted_wls[-1])

        def _heatmap_clipboard_df() -> Any:

            rows = []

            for lk in self.layers:
                for j, wl in enumerate(self.sorted_wls):
                    v = float(grid[lk, j])

                    if np.isfinite(v):
                        rows.append(
                            {
                                "layer_key": int(lk),
                                "wavelength_nm": float(wl),
                                "cost": v,
                            }
                        )

            if not rows:
                return None

            return pd.DataFrame(rows)

        self.plot_widget._certus_clipboard_df_provider = _heatmap_clipboard_df

