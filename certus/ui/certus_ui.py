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
    # Theme
    "CertusTheme",
    "get_standard_stylesheet",
    "apply_certus_theme",
    "apply_theme_to_plots",
    "get_plot_style_config",
    "apply_certus_plot_style",
    # Widgets
    "CertusThemeToggle",
    "CertusScientificPlot",
    "ScientificPlotRefined",
    "DetachedPlotWindow",
    "ExcelTableWidget",
    "NumericTableWidgetItem",
    "FlashyCard",
    "WelcomeGuideWidget",
    "ProgressDialog",
    "DualStageProgressWidget",
    "EnhancedProgressWidget",
    # Factory Functions
    "create_header_logo_widget",
    "create_styled_button",
    "create_info_icon",
    "create_help_button",
    "set_certus_window_icon",
    "open_documentation",
    "create_flashy_grid",
    "create_log_widget",
    "CertusLogPanel",
    "clone_plot_widget",
    # Pro UX Design System components
    "CertusCard",
    "CertusSectionHeader",
    "CertusStepper",
    "CertusCollapsible",
    "CertusStatusPill",
    "CertusActionBar",
    "CertusToast",
    "SkeletonLoaderWidget",
    "install_skeleton_loader",
    "remove_skeleton_loader",
    "apply_os_window_effects",
    "install_standard_shortcuts",
    "enable_file_drop",
    "show_toast",
    "attach_numeric_validator",
    # Threading
    "WorkerSignals",
    "GenericWorker",
    "CertusWorkerBase",
    # App Base
    "CertusBaseApp",
    # Utilities
    "get_export_settings",
    "get_export_config",
    "open_file_explorer",
    "open_data_file_and_read",
    "get_certus_last_dir",
    "set_certus_last_dir",
    "certus_get_open_file_name",
    "certus_get_save_file_name",
    "certus_confirm_yes_no",
    "DATA_FILE_FILTER",
    "DATA_FILES_FILTER_EXTENDED",
    "CERTUS_UI_STRINGS",
    "process_log_queue_standard",
    "confirm_stop_with_timeout",
    "copy_app_logs_to_clipboard",
    "format_count_kmg",
    "StatsCounter",
    "stop_worker_and_thread",
    "confirm_and_stop",
    "init_certus_app",
    "setup_pyqtgraph_defaults",
    "setup_gui_exception_handling",
    "safe_ui_action",
    "sanitize_xy_for_plot",
    "plot_widget_plot_finite",
    "iter_plot_data_series",
    "build_wide_dataframe_for_export",
    "plot_dataframe_from_widget",
    "copy_plot_to_clipboard_excel",
    "attach_excel_clipboard_context_menu",
    "wrap_scientific_plot_with_toolbar",
    # Re-exports from certus.core.certus_core
    "QueueHandler",
    "setup_gui_logger",
    "setup_module_logging",
    # Flags
    "SVG_AVAILABLE",
    "OPENPYXL_AVAILABLE",
]


import copy
import functools


import logging


import os
from pathlib import Path


import queue


import sys


import time


import traceback


import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast", module="pyqtgraph")

from collections import deque


from typing import Any, Callable


import numpy as np
from pydantic import ValidationError


import pandas as pd


import pyqtgraph as pg


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
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
    QMetaObject,
    Q_ARG,
    QSettings,
    QPropertyAnimation,
    QEasingCurve,
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
    SVG_AVAILABLE,
    build_runtime,
    handle_exception,
    get_resource_path,
    load_theme_config,
    save_theme_config,
    get_export_config,
    QueueHandler,
    setup_gui_logger,
    setup_module_logging,
)


if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


# OPENPYXL_AVAILABLE imported from certus.core.certus_core (Single Source of Truth)


from certus.core.certus_core import OPENPYXL_AVAILABLE


from certus.utils.certus_data import read_data_file_robust


# =============================================================================



from certus.ui.certus_ui_widgets_cards import CertusCard, FlashyCard, CertusDashboardCard
from certus.ui.certus_ui_widgets_utils import CertusToast, CertusStatusPill, CertusThemeToggle, AutoShrinkTitleLabel, CertusLogPanel, ExcelTableWidget, NumericTableWidgetItem, DetachedPlotWindow, SkeletonLoaderWidget
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.ui.certus_plot import CertusScientificPlot, clone_plot_widget, wrap_scientific_plot_with_toolbar, ScientificPlotRefined, sanitize_xy_for_plot, plot_widget_plot_finite
from certus.ui.certus_ui_widgets_layout import CertusCollapsible, CertusSectionHeader, CertusStepper, CertusActionBar
from certus.ui.certus_ui_widgets_progress import DualStageProgressWidget, EnhancedProgressWidget, ProgressDialog
from certus.ui.certus_ui_widgets_welcome import WelcomeGuideWidget
from certus.workers.certus_base_workers import WorkerSignals, GenericWorker, CertusWorkerBase
from certus.ui.certus_base_app import CertusBaseApp, CertusAppLogsMixin, StatsCounter
from certus.ui.certus_ui_widgets_factory import (
    create_flashy_grid, create_log_widget, create_header_logo_widget,
    create_styled_button, create_info_icon, create_help_button,
    create_styled_label, create_colored_label, create_top_actions_bar
)
from certus.ui.certus_ui_utils import (
    set_certus_window_icon, apply_certus_theme, update_global_plot_config,
    open_documentation, install_standard_shortcuts, enable_file_drop,
    show_toast, show_status_feedback, attach_numeric_validator, get_export_settings,
    open_file_explorer, process_log_queue_standard, init_certus_app,
    setup_pyqtgraph_defaults, setup_gui_exception_handling, safe_ui_action,
    confirm_stop_with_timeout, format_count_kmg, stop_worker_and_thread,
    confirm_and_stop, copy_app_logs_to_clipboard, install_skeleton_loader,
    remove_skeleton_loader, apply_os_window_effects
)



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
        from certus.utils.certus_validation import PathValidator
        from certus.ui.certus_io_ui import extract_extensions_from_filter
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
        from certus.utils.certus_validation import PathValidator
        from certus.ui.certus_io_ui import extract_extensions_from_filter
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
        from certus.utils.certus_validation import PathValidator
        from certus.ui.certus_io_ui import extract_extensions_from_filter
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