"""


CERTUS UI - Shared User Interface Components


============================================


Part of CERTUS Suite (Harmonized Architecture 2026)


Contains:


P0 boundary: this module is the shared UI foundation. Keep visual primitives,
shared dialogs, runtime helpers, and worker utilities clearly separated; avoid
adding feature-specific business logic here.


- CertusTheme (Colors, Fonts)


- Custom Widgets (FlashyCard, WelcomeGuide, Headers)


- specialized Plot Widgets (CertusScientificPlot)


- Threading & Worker Utilities


- Application Initialization Helpers


Domain map:
- Theme/design tokens: `CertusTheme`, stylesheet and plot style helpers.
- Visual components: cards, status pills, steppers, plot/table widgets and empty states.
- Runtime helpers: application initialization, exception handling, workers and shortcuts.
- IO/export helpers: file dialogs, last-directory persistence, clipboard and Excel/TSV export.


"""

__all__ = [
    "OPENPYXL_AVAILABLE",
    # Flags
    "SVG_AVAILABLE",
    "CertusActionBar",
    # App Base
    "CertusBaseApp",
    # Pro UX Design System components
    "CertusCard",
    "CertusCollapsible",
    "CertusLogPanel",
    "CertusScientificPlot",
    "CertusSectionHeader",
    "CertusStatusPill",
    "CertusStepper",
    # Theme
    "CertusTheme",
    # Widgets
    "CertusThemeToggle",
    "CertusToast",
    "DetachedPlotWindow",
    "DualStageProgressWidget",
    "EnhancedProgressWidget",
    "ExcelTableWidget",
    "FlashyCard",
    "GenericWorker",
    "NumericTableWidgetItem",
    "ProgressDialog",
    # Re-exports from certus.core.certus_core
    "QueueHandler",
    "ScientificPlotRefined",
    "SkeletonLoaderWidget",
    "StatsCounter",
    "WelcomeGuideWidget",
    # Threading
    "WorkerSignals",
    "apply_certus_theme",
    "apply_os_window_effects",
    "attach_numeric_validator",
    "clone_plot_widget",
    "configure_theme_from_preference",
    "confirm_and_stop",
    "confirm_stop_with_timeout",
    "copy_app_logs_to_clipboard",
    "create_flashy_grid",
    # Factory Functions
    "create_header_logo_widget",
    "create_help_button",
    "create_info_icon",
    "create_log_widget",
    "create_styled_button",
    "enable_file_drop",
    "format_count_kmg",
    "get_export_config",
    # Utilities
    "get_export_settings",
    "get_standard_stylesheet",
    "init_certus_app",
    "install_skeleton_loader",
    "install_standard_shortcuts",
    "open_documentation",
    "open_file_explorer",
    "plot_widget_plot_finite",
    "process_log_queue_standard",
    "remove_skeleton_loader",
    "safe_ui_action",
    "sanitize_xy_for_plot",
    "set_certus_window_icon",
    "setup_gui_exception_handling",
    "setup_gui_logger",
    "setup_module_logging",
    "setup_pyqtgraph_defaults",
    "show_toast",
    "stop_worker_and_thread",
    "wrap_scientific_plot_with_toolbar",
]


import copy
import functools
import logging
import os
import queue
import sys
import time
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast", module="pyqtgraph")

from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pydantic import ValidationError

from certus.core.certus_core import CFG, certus_timestamp_display
from certus.utils.certus_dto import IndexSplineConfigDTO
from certus_physics import init_thickness
from certus_physics.structures import Layer, Target

# PyQtGraph ViewBox vs NumPy/Python 3.14  cosmetic RuntimeWarning on cast (any emitting module)


warnings.filterwarnings(
    "ignore",
    message=r"overflow encountered in cast",
    category=RuntimeWarning,
)


import pyqtgraph.exporters  # pylint: disable=unused-import
from PyQt6.QtCore import (
    Q_ARG,
    QEasingCurve,
    QMetaObject,
    QObject,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Check optional dependencies
# Import Core
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    CertusRuntime,
    QueueHandler,
    build_runtime,
    get_export_config,
    get_resource_path,
    handle_exception,
    load_theme_config,
    save_theme_config,
    setup_gui_logger,
    setup_module_logging,
)
from certus.ui.certus_qt_svg import SVG_AVAILABLE

if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


# OPENPYXL_AVAILABLE imported from certus.core.certus_core (Single Source of Truth)


from certus.core.certus_core import OPENPYXL_AVAILABLE
from certus.ui.certus_base_app import CertusAppLogsMixin, CertusBaseApp, StatsCounter
from certus.ui.certus_plot import (
    CertusScientificPlot,
    ScientificPlotRefined,
    clone_plot_widget,
    plot_widget_plot_finite,
    sanitize_xy_for_plot,
    wrap_scientific_plot_with_toolbar,
)
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.ui.certus_ui_utils import (
    apply_certus_theme,
    apply_os_window_effects,
    attach_numeric_validator,
    claim_shortcut_for_action,
    configure_theme_from_preference,
    confirm_and_stop,
    confirm_stop_with_timeout,
    copy_app_logs_to_clipboard,
    enable_file_drop,
    format_count_kmg,
    get_export_settings,
    init_certus_app,
    install_skeleton_loader,
    install_standard_shortcuts,
    install_unique_shortcut,
    normalized_shortcut,
    open_documentation,
    open_file_explorer,
    process_log_queue_standard,
    remove_skeleton_loader,
    safe_ui_action,
    set_certus_window_icon,
    setup_gui_exception_handling,
    setup_pyqtgraph_defaults,
    shortcut_owner,
    show_status_feedback,
    show_toast,
    stop_worker_and_thread,
    update_global_plot_config,
)

# =============================================================================
from certus.ui.certus_ui_widgets_cards import CertusCard, CertusDashboardCard, FlashyCard
from certus.ui.certus_ui_widgets_factory import (
    create_colored_label,
    create_flashy_grid,
    create_header_logo_widget,
    create_help_button,
    create_info_icon,
    create_log_widget,
    create_styled_button,
    create_styled_label,
    create_top_actions_bar,
)
from certus.ui.certus_ui_widgets_layout import CertusActionBar, CertusCollapsible, CertusSectionHeader, CertusStepper
from certus.ui.certus_ui_widgets_progress import DualStageProgressWidget, EnhancedProgressWidget, ProgressDialog
from certus.ui.certus_ui_widgets_utils import (
    AutoShrinkTitleLabel,
    CertusLogPanel,
    CertusStatusPill,
    CertusThemeToggle,
    CertusToast,
    DetachedPlotWindow,
    ExcelTableWidget,
    NumericTableWidgetItem,
    SkeletonLoaderWidget,
)
from certus.ui.certus_ui_widgets_welcome import WelcomeGuideWidget
from certus.utils.certus_data import read_data_file_robust
from certus.workers.certus_base_workers import GenericWorker, WorkerSignals

_LAZY_REEXPORTS: dict[str, tuple[str, str]] = {
    "get_certus_last_dir": ("certus.ui.certus_io_ui", "get_certus_last_dir"),
    "set_certus_last_dir": ("certus.ui.certus_io_ui", "set_certus_last_dir"),
    "certus_get_open_file_name": ("certus.ui.certus_io_ui", "certus_get_open_file_name"),
    "certus_get_save_file_name": ("certus.ui.certus_io_ui", "certus_get_save_file_name"),
    "certus_confirm_yes_no": ("certus.ui.certus_io_ui", "certus_confirm_yes_no"),
    "open_data_file_and_read": ("certus.ui.certus_io_ui", "open_data_file_and_read"),
    "open_file_explorer": ("certus.ui.certus_io_ui", "open_file_explorer"),
    "DATA_FILE_FILTER": ("certus.ui.certus_io_ui", "DATA_FILE_FILTER"),
    "DATA_FILES_FILTER_EXTENDED": ("certus.ui.certus_io_ui", "DATA_FILES_FILTER_EXTENDED"),
    "CERTUS_UI_STRINGS": ("certus.ui.certus_io_ui", "CERTUS_UI_STRINGS"),
    "apply_certus_plot_style": ("certus.ui.certus_plot", "apply_certus_plot_style"),
    "apply_theme_to_plots": ("certus.ui.certus_plot", "apply_theme_to_plots"),
    "iter_plot_data_series": ("certus.utils.certus_export", "iter_plot_data_series"),
    "build_wide_dataframe_for_export": ("certus.utils.certus_export", "build_wide_dataframe_for_export"),
    "plot_dataframe_from_widget": ("certus.utils.certus_export", "plot_dataframe_from_widget"),
    "copy_plot_to_clipboard_excel": ("certus.utils.certus_export", "copy_plot_to_clipboard_excel"),
    "attach_excel_clipboard_context_menu": ("certus.utils.certus_export", "attach_excel_clipboard_context_menu"),
}


def __getattr__(name: str):
    entry = _LAZY_REEXPORTS.get(name)
    if entry is not None:
        import importlib

        mod = importlib.import_module(entry[0])
        attr = getattr(mod, entry[1])
        globals()[name] = attr  # cache for subsequent access
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_LAZY_REEXPORTS))


# Caching/Monkeypatching of QFileDialog to enforce security checks globally.
original_get_open_file_name = QFileDialog.getOpenFileName
original_get_save_file_name = QFileDialog.getSaveFileName
original_get_open_file_names = QFileDialog.getOpenFileNames


def _get_filter_and_parent(*args, **kwargs) -> tuple[str | None, Any]:
    file_filter = kwargs.get("filter")
    if file_filter is None and len(args) > 3:
        file_filter = args[3]
    parent = kwargs.get("parent")
    if parent is None and len(args) > 0:
        parent = args[0]
    return file_filter, parent


def secure_get_open_file_name(*args, **kwargs):
    path, sel_filter = original_get_open_file_name(*args, **kwargs)
    if path:
        file_filter, parent = _get_filter_and_parent(*args, **kwargs)
        from certus.ui.certus_io_ui import extract_extensions_from_filter
        from certus.utils.certus_validation import PathValidator

        allowed = extract_extensions_from_filter(file_filter)
        try:
            PathValidator.validate_path(path, allowed_extensions=allowed)
        except ValueError as e:
            QMessageBox.warning(parent, "Security Alert", f"Invalid File Selected:\n{e}")
            return "", ""
    return path, sel_filter


def secure_get_save_file_name(*args, **kwargs):
    path, sel_filter = original_get_save_file_name(*args, **kwargs)
    if path:
        file_filter, parent = _get_filter_and_parent(*args, **kwargs)
        from certus.ui.certus_io_ui import extract_extensions_from_filter
        from certus.utils.certus_validation import PathValidator

        allowed = extract_extensions_from_filter(file_filter)
        try:
            PathValidator.validate_path(path, allowed_extensions=allowed)
        except ValueError as e:
            QMessageBox.warning(parent, "Security Alert", f"Invalid File Selected:\n{e}")
            return "", ""
    return path, sel_filter


def secure_get_open_file_names(*args, **kwargs):
    paths, sel_filter = original_get_open_file_names(*args, **kwargs)
    if paths:
        file_filter, parent = _get_filter_and_parent(*args, **kwargs)
        from certus.ui.certus_io_ui import extract_extensions_from_filter
        from certus.utils.certus_validation import PathValidator

        allowed = extract_extensions_from_filter(file_filter)
        validated_paths = []
        for path in paths:
            try:
                PathValidator.validate_path(path, allowed_extensions=allowed)
                validated_paths.append(path)
            except ValueError as e:
                QMessageBox.warning(parent, "Security Alert", f"Invalid File Selected:\n{e}")
                return [], ""
        return validated_paths, sel_filter
    return paths, sel_filter


# Assign to static/class methods
QFileDialog.getOpenFileName = secure_get_open_file_name
QFileDialog.getSaveFileName = secure_get_save_file_name
QFileDialog.getOpenFileNames = secure_get_open_file_names
