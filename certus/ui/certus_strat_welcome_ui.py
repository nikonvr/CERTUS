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

class WelcomeGuideWidget(QWidget):
    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"""
            QWidget {{ font-family: 'Segoe UI', sans-serif; }}

            QScrollArea, QWidget#ContentContainer {{ background: {CertusTheme.BACKGROUND}; border: none; }}

            QScrollBar:vertical {{ width: 10px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {CertusTheme.BORDER}; border-radius: 5px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            .step-card {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 16px;
            }}
            .step-number {{ font-size: 34px; font-weight: 900; opacity: 0.20; }}
            .step-title {{ color: {CertusTheme.TEXT_MAIN}; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; }}
            .step-desc {{ color: {CertusTheme.TEXT_SUB}; font-size: 11px; line-height: 1.35; }}

            .mission-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 14px; }}
            .dash-frame {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px; }}
            .dash-header {{ color: {CertusTheme.PRIMARY}; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid {CertusTheme.BORDER}; padding-bottom: 6px; margin-bottom: 8px; }}

        """)

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()

        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_container = QWidget()

        self.content_container.setObjectName("ContentContainer")

        main_layout = QVBoxLayout(self.content_container)

        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.content_container)

        outer_layout.addWidget(self.scroll_area)

        content_wrapper = QWidget()

        content_wrapper.setStyleSheet("background-color: transparent;")

        content_layout = QVBoxLayout(content_wrapper)

        content_layout.setContentsMargins(8, 14, 8, 10)

        content_layout.setSpacing(14)

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(10)

        cards_layout.addWidget(
            self._create_step_card(
                "01",
                "DESIGN",
                "Define optical stack,\nmaterials & target.",
                CertusTheme.SECONDARY,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "02",
                "OPTIMIZE",
                "Hybrid algorithm for\nstable monitoring.",
                CertusTheme.ACCENT,
            )
        )

        cards_layout.addWidget(
            self._create_step_card(
                "03",
                "VALIDATE",
                "Monte Carlo sims to\nensure robustness.",
                CertusTheme.SUCCESS,
            )
        )

        content_layout.addLayout(cards_layout)

        mission_frame = QFrame()

        mission_frame.setProperty("class", "mission-frame")

        mission_layout = QGridLayout(mission_frame)

        mission_layout.setContentsMargins(14, 14, 14, 14)

        points = [
            (
                "🎯",
                "<b>Precision Targeting:</b> Identify exact wavelengths to cancel errors.",
            ),
            ("🧬", "<b>Hybrid Intelligence:</b> DP engine finds global minimuum."),
            (
                "🛡️",
                "<b>Robustness First:</b> Validation via thousands of Monte Carlo sims.",
            ),
            (
                "⚡",
                "<b>Real-Time Physics:</b> JIT engine simulating layer growth in ms.",
            ),
            (
                "📉",
                "<b>Zero-Bias Strategy:</b> Eliminate empiricism with proven paths.",
            ),
            (
                "📈",
                "<b>Yield Assurance:</b> Turn theoretical robustness into production gains.",
            ),
        ]

        for i, (icon, text) in enumerate(points):
            item_widget = QWidget()

            item_layout = QHBoxLayout(item_widget)

            item_layout.setContentsMargins(0, 0, 0, 0)

            lbl_ico = QLabel(icon)

            lbl_ico.setStyleSheet("font-size: 20px; background: transparent;")

            lbl_ico.setFixedWidth(25)

            lbl_txt = QLabel(text)

            lbl_txt.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; background: transparent;")

            lbl_txt.setTextFormat(Qt.TextFormat.RichText)

            lbl_txt.setWordWrap(True)

            item_layout.addWidget(lbl_ico)

            item_layout.addWidget(lbl_txt)

            mission_layout.addWidget(item_widget, i // 2, i % 2)

        content_layout.addWidget(mission_frame)

        dash_frame = QFrame()

        dash_frame.setProperty("class", "dash-frame")

        shadow_dash = QGraphicsDropShadowEffect()

        shadow_dash.setBlurRadius(15)

        shadow_dash.setColor(QColor(0, 0, 0, 10))

        shadow_dash.setOffset(0, 2)

        dash_frame.setGraphicsEffect(shadow_dash)

        dash_layout = QHBoxLayout(dash_frame)

        dash_layout.setContentsMargins(12, 12, 12, 12)

        dash_layout.setSpacing(12)

        # Get approximate total CPU count

        from certus.core.certus_core import _get_cpu_count

        cpu_count = _get_cpu_count()

        try:
            mat_count = len(APP_CONTEXT.get("materials_db").data) if APP_CONTEXT.get("materials_db") else 0

        except (AttributeError, TypeError):
            mat_count = 0

        sys_layout = QVBoxLayout()

        sys_head = QLabel("SYSTEM READINESS")

        sys_head.setProperty("class", "dash-header")

        sys_layout.addWidget(sys_head)

        sys_layout.addLayout(self._create_status_row("⚡", "HPC Active", f"<b>{cpu_count} Threads</b>"))

        sys_layout.addLayout(self._create_status_row("📚", "Database", f"<b>{mat_count} Materials</b>"))

        sys_layout.addLayout(self._create_status_row("🚀", "JIT Engine", "<b>Compiled & Ready</b>"))

        sys_layout.addStretch()

        cap_layout = QVBoxLayout()

        cap_head = QLabel("CORE CAPABILITIES")

        cap_head.setProperty("class", "dash-header")

        cap_layout.addWidget(cap_head)

        cap_layout.addLayout(self._create_status_row("✓", "Hybrid Exploration", "DP + hybridization"))

        cap_layout.addLayout(self._create_status_row("✓", "Simulation", "Adaptive Nucleation"))

        cap_layout.addLayout(self._create_status_row("✓", "Analysis", "Yield & Robustness"))

        cap_layout.addStretch()

        dash_layout.addLayout(sys_layout)

        line = QFrame()

        line.setFrameShape(QFrame.Shape.VLine)

        line.setStyleSheet(f"color: {CertusTheme.SURFACE_HOVER};")

        dash_layout.addWidget(line)

        dash_layout.addLayout(cap_layout)

        content_layout.addWidget(dash_frame)

        main_layout.addWidget(content_wrapper)

        main_layout.addStretch()

    def _create_step_card(self, number, title, desc, accent_color) -> Any:

        card = QFrame()

        card.setProperty("class", "step-card")

        card.setStyleSheet(
            f".step-card {{ border-bottom: 4px solid {accent_color}; padding: 10px 12px; }}"
        )

        card.setMinimumWidth(160)

        card.setMaximumWidth(220)

        card.setMinimumHeight(130)

        shadow = QGraphicsDropShadowEffect()

        shadow.setBlurRadius(18)

        shadow.setColor(QColor(0, 0, 0, 16))

        shadow.setOffset(0, 6)

        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)

        vbox.setContentsMargins(4, 4, 4, 4)

        vbox.setSpacing(2)

        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_num = QLabel(number)

        lbl_num.setProperty("class", "step-number")

        lbl_num.setStyleSheet(f"color: {accent_color}; background: transparent;")

        lbl_title = QLabel(title)

        lbl_title.setProperty("class", "step-title")

        lbl_title.setStyleSheet("background: transparent;")

        lbl_desc = QLabel(desc)

        lbl_desc.setProperty("class", "step-desc")

        lbl_desc.setStyleSheet("background: transparent;")

        vbox.addWidget(lbl_num)

        vbox.addWidget(lbl_title)

        vbox.addWidget(lbl_desc)

        return card

    def _create_status_row(self, icon, label, value) -> Any:

        row = QHBoxLayout()

        row.setSpacing(15)

        lbl_icon = QLabel(icon)

        lbl_icon.setFixedSize(24, 24)

        lbl_icon.setStyleSheet(
            f"background-color: {CertusTheme.INFO_BG}; color: {CertusTheme.SECONDARY}; border-radius: 4px; font-weight: bold; font-size: 14px;"
        )

        if icon == "✓":
            lbl_icon.setStyleSheet(
                f"background-color: {CertusTheme.SUCCESS_BG}; color: {CertusTheme.SUCCESS}; border-radius: 4px; font-weight: bold; font-size: 14px;"
            )

        lbl_text = QLabel(label)

        lbl_text.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 13px; font-weight: 500; background: transparent;"
        )

        lbl_val = QLabel(value)

        lbl_val.setTextFormat(Qt.TextFormat.RichText)

        lbl_val.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 13px; background: transparent;")

        row.addWidget(lbl_icon)

        row.addWidget(lbl_text)

        row.addStretch()

        row.addWidget(lbl_val)

        return row

