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
)


if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


# OPENPYXL_AVAILABLE imported from certus.core.certus_core (Single Source of Truth)


from certus.core.certus_core import OPENPYXL_AVAILABLE


from certus.utils.certus_data import read_data_file_robust


# =============================================================================


# FILE DIALOG FILTERS (shared across apps)


# =============================================================================


DATA_FILE_FILTER = "Data (*.csv *.txt *.xlsx)"


DATA_FILES_FILTER_EXTENDED = "Data Files (*.csv *.txt *.xlsx *.xls);;All Files (*)"


# Last directory used in any CERTUS app (load/save); next dialog opens in this folder.


CERTUS_SETTINGS_ORG = "CERTUS"


CERTUS_SETTINGS_APP = "Common"


CERTUS_LAST_DIR_KEY = "last_dir"


# Shared UI copy (English) - single lexicon for titles/messages


CERTUS_UI_STRINGS = {
    "export": "Export",
    "export_ok": "Saved file",
    "export_failed": "Export failed",
    "no_data": "No data to export.",
    "copy_logs": "Copy Logs",
    "logs_copied": "Logs copied to clipboard.",
    "copy_excel_tsv": "Copy data (Excel)",
    "copy_excel_ok": "Data copied to clipboard (TSV).",
    "copy_excel_failed": "No data to copy.",
    "copy_pub_tsv": "Copy data (Publication TSV)",
    "copy_pub_ok": "Publication TSV copied to clipboard.",
}


def get_certus_last_dir() -> str:
    """Return the last directory used for open/save in the CERTUS suite (persisted)."""

    settings = QSettings(CERTUS_SETTINGS_ORG, CERTUS_SETTINGS_APP)

    return str(settings.value(CERTUS_LAST_DIR_KEY, "") or "")


def set_certus_last_dir(file_or_dir_path: str) -> None:
    """Set the last-used directory from a selected file path (or directory). Persisted for next dialog."""

    if not file_or_dir_path:
        return

    path = Path(file_or_dir_path).resolve()

    dirpath = path if path.is_dir() else path.parent

    if str(dirpath) and dirpath.is_dir():
        settings = QSettings(CERTUS_SETTINGS_ORG, CERTUS_SETTINGS_APP)

        settings.setValue(CERTUS_LAST_DIR_KEY, str(dirpath))


def certus_get_open_file_name(
    parent,
    title: str,
    file_filter: str,
    directory: str | None = None,
) -> str:
    """

    Open File Dialog: initial directory = last used CERTUS folder if directory is None.

    Updates last directory if user selects a file. Returns "" if canceled.

    """

    initial = directory if directory is not None else get_certus_last_dir()

    path, _ = QFileDialog.getOpenFileName(parent, title, initial, file_filter)

    if path:
        set_certus_last_dir(path)

    return path


def certus_get_save_file_name(
    parent,
    title: str,
    file_filter: str,
    directory: str | None = None,
) -> str:
    """

    Save File Dialog: same convention as certus_get_open_file_name.

    """

    initial = directory if directory is not None else get_certus_last_dir()

    path, _ = QFileDialog.getSaveFileName(parent, title, initial, file_filter)

    if path:
        set_certus_last_dir(path)

    return path


def certus_confirm_yes_no(
    parent,
    title: str,
    text: str,
    *,
    default_no: bool = True,
) -> bool:
    """Standard Yes/No question (configurable default button)."""

    default_btn = QMessageBox.StandardButton.No if default_no else QMessageBox.StandardButton.Yes

    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_btn,
    )

    return reply == QMessageBox.StandardButton.Yes


def open_data_file_and_read(
    parent=None,
    title="Open",
    file_filter=None,
    initial_dir="",
    last_dir_settings_key=None,
    **read_kwargs,
) -> tuple:
    """

    Open a file dialog and read CSV/Excel via read_data_file_robust.

    Returns (filepath, df) or (None, None) if user cancels.

    If last_dir_settings_key is (org, app), uses QSettings to persist last directory.

    """

    if file_filter is None:
        file_filter = DATA_FILE_FILTER

    if last_dir_settings_key is not None:
        org, app = last_dir_settings_key

        settings = QSettings(org, app)

        initial_dir = initial_dir or settings.value("last_dir", "")

    if not initial_dir:
        initial_dir = get_certus_last_dir()

    filepath, _ = QFileDialog.getOpenFileName(parent, title, initial_dir, file_filter)

    if not filepath:
        return None, None

    set_certus_last_dir(filepath)

    if last_dir_settings_key is not None:
        org, app = last_dir_settings_key

        settings = QSettings(org, app)

        settings.setValue("last_dir", str(Path(filepath).parent))

    df = read_data_file_robust(filepath, **read_kwargs)

    return filepath, df


# =============================================================================


# HELPER FUNCTIONS


# =============================================================================


def set_certus_window_icon(window: QWidget, icon_name: str = "certus.ico") -> bool:
    """

    Sets Certus icon on any PyQt6 window/widget.

    Args:

        window: QMainWindow, QDialog or QWidget to set icon on

        icon_name: Icon filename (default: certus.ico)

    Returns:

        True if icon was set successfully, False otherwise

    """

    try:
        icon_path = get_resource_path(icon_name)

        if Path(icon_path).exists():
            window.setWindowIcon(QIcon(icon_path))

            return True

    except (FileNotFoundError, OSError, RuntimeError):
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    return False


# =============================================================================


# THEME DEFINITION


# =============================================================================


from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
CertusTheme.configure("auto")


def apply_certus_theme(
    window: QWidget,
    plots: list[Any] | None = None,
    overrides: str | None = None,
    *,
    premium: bool = True,
) -> None:
    """

    Apply CERTUS theme to window and optional plots.

    Args:

        window: QWidget to apply stylesheet to

        plots: Optional list of pyqtgraph plots to theme

        overrides: Optional additional CSS to append

        premium: Append the U1 premium overrides (focus rings, modern
            scrollbars, elevated cards, ghost buttons, ...). Opt-in globally
            via object-names — set ``premium=False`` to fully revert to the
            pre-U1 look for a window.

    """

    # U1: append premium overrides (additive, opt-in via objectName).
    premium_css = ""
    if premium:
        try:
            from certus.utils.certus_ux import build_premium_overrides

            premium_css = build_premium_overrides()
        except (ImportError, AttributeError, ValueError, TypeError):
            # Never break theming because of premium extras.
            premium_css = ""

    window.setStyleSheet(get_standard_stylesheet() + premium_css + (overrides or ""))

    if hasattr(window, "isWindow") and window.isWindow():
        dark_mode = load_theme_config() == "dark"
        apply_os_window_effects(window, dark_mode)

    if plots:
        bg = CertusTheme.BACKGROUND

        fg = CertusTheme.TEXT_MAIN

        for p in plots:
            if hasattr(p, "setBackground"):
                p.setBackground(bg)

                p.getAxis("left").setPen(fg)

                p.getAxis("bottom").setPen(fg)

                p.getAxis("left").setTextPen(fg)

                p.getAxis("bottom").setTextPen(fg)


def update_global_plot_config(dark_mode: bool = False) -> None:
    """

    Updates global pyqtgraph configuration for the theme and dynamically updates existing plots.

    """

    import pyqtgraph as pg

    from PyQt6.QtWidgets import QApplication

    bg = CertusTheme.SURFACE

    fg = CertusTheme.TEXT_MAIN

    pg.setConfigOption("background", bg)

    pg.setConfigOption("foreground", fg)

    app = QApplication.instance()

    if app:
        for widget in app.allWidgets():
            if isinstance(widget, pg.GraphicsView) or isinstance(widget, pg.GraphicsLayoutWidget):
                try:
                    widget.setBackground(bg)

                    # Update axis pens if it's a PlotWidget or has a PlotItem

                    if hasattr(widget, "getPlotItem"):
                        pi = widget.getPlotItem()

                        if pi:
                            for axis_name in ["left", "bottom", "right", "top"]:
                                axis = pi.getAxis(axis_name)

                                if axis:
                                    axis.setPen(fg)

                                    axis.setTextPen(fg)

                except NUMERICAL_FAULT_EXCEPTIONS :
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


# =============================================================================


# WIDGETS


# =============================================================================


class CertusThemeToggle(QPushButton):
    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self.setFixedSize(32, 32)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.clicked.connect(self.toggle)

        self.update_appearance()

    def update_appearance(self) -> None:

        mode = load_theme_config()

        self.setText("" if mode == "light" else "")

        self.setStyleSheet(f"""
            QPushButton {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                border-color: {CertusTheme.PRIMARY};
                background: {CertusTheme.SURFACE_HOVER};
            }}
        """)

    def toggle(self, checked=False) -> None:

        mode = load_theme_config()

        new_mode = "dark" if mode == "light" else "light"

        save_theme_config(new_mode)

        CertusTheme.configure(new_mode)

        self.update_appearance()

        update_global_plot_config(new_mode == "dark")

        CertusTheme.apply_to_app(QApplication.instance(), new_mode == "dark")

        self.theme_changed.emit(new_mode)

        # Internal refresh Logic

        w = self.window()

        if hasattr(w, "_apply_theme"):
            w._apply_theme()

        else:
            apply_certus_theme(w)


def create_flashy_grid(cards: list) -> QWidget:
    """

    Creates a standardized 2x2 grid for FlashyCards (Why CERTUS? tab).

    Args:

        cards: List of 4 FlashyCard widgets.

    """

    w = QWidget()

    layout = QGridLayout(w)

    layout.setSpacing(20)

    layout.setContentsMargins(30, 30, 30, 30)

    if len(cards) >= 1:
        layout.addWidget(cards[0], 0, 0)

    if len(cards) >= 2:
        layout.addWidget(cards[1], 0, 1)

    if len(cards) >= 3:
        layout.addWidget(cards[2], 1, 0)

    if len(cards) >= 4:
        layout.addWidget(cards[3], 1, 1)

    return w


def create_log_widget(visible: bool = False, height: int = None) -> QTextEdit:
    """

    Creates a standardized log text widget.

    Args:

        visible: Initial visibility state.

        height: Optional max height.

    Returns:

        Configured QTextEdit

    """

    log_text = QTextEdit()

    log_text.setReadOnly(True)

    log_text.document().setMaximumBlockCount(5000)

    log_text.setStyleSheet(CertusTheme.get_log_stylesheet())

    log_text.setVisible(visible)

    if height:
        log_text.setMaximumHeight(height)

    return log_text


class CertusLogPanel(QWidget):
    """

    Shared log panel: header with title + Copy button, and a read-only log QTextEdit.

    Use .log_text to connect to queue handler or append messages.

    """

    copied = pyqtSignal()

    def __init__(
        self,
        title: str = "LOGS",
        visible: bool = True,
        height: int = None,
        parent=None,
    ) -> None:

        super().__init__(parent)

        self.setStyleSheet(f"background-color: {CertusTheme.SURFACE};")

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        header = QWidget()

        header.setFixedHeight(28)

        header.setStyleSheet(f"background-color: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER};")

        hl = QHBoxLayout(header)

        hl.setContentsMargins(5, 0, 5, 0)

        lbl = QLabel(title)

        lbl.setStyleSheet(f"font-weight: bold; color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        hl.addWidget(lbl)

        hl.addStretch()

        btn_copy = QPushButton(CERTUS_UI_STRINGS["copy_logs"])

        btn_copy.setToolTip("Copy all logs to clipboard")

        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_copy.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {CertusTheme.PRIMARY}; font-weight: 700; padding: 2px 6px; border-radius: 8px; }} QPushButton:hover {{ color: {CertusTheme.TEXT_MAIN}; background: {CertusTheme.SURFACE_HOVER}; }}"
        )

        btn_copy.clicked.connect(self._on_copy)

        hl.addWidget(btn_copy)

        layout.addWidget(header)

        self.log_text = create_log_widget(visible=visible, height=height)

        layout.addWidget(self.log_text)

    def _on_copy(self) -> None:

        text = self.log_text.toPlainText()

        if text:
            app = QApplication.instance()

            if app and app.clipboard():
                app.clipboard().setText(text)

        self.copied.emit()

    def copy_to_clipboard(self) -> None:
        """Copy log content to clipboard. Emits copied after."""

        self._on_copy()


class AutoShrinkTitleLabel(QLabel):
    """A label that shrinks its font size to prevent being cut off."""
    def __init__(self, text: str, default_size: int = 16, min_size: int = 9, color: str = CertusTheme.TEXT_MAIN, weight: int | str = 800, parent=None):
        super().__init__(text, parent)
        from PyQt6.QtWidgets import QSizePolicy
        from PyQt6.QtCore import Qt
        
        self._default_size = default_size
        self._min_size = min_size
        self._color = color
        self._weight = weight
        self._current_rendered_size = default_size
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)
        self.setWordWrap(True)
        self._update_style(default_size)

    def _update_style(self, size: int) -> None:
        if self._current_rendered_size == size and self.styleSheet():
            return
        self._current_rendered_size = size
        self.setStyleSheet(f"font-weight: {self._weight}; color: {self._color}; font-size: {size}px; background: transparent;")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
            
        current_size = self._default_size
        font = self.font()
        from PyQt6.QtGui import QFontMetrics
        
        while current_size >= self._min_size:
            font.setPixelSize(current_size)
            fm = QFontMetrics(font)
            # Use 1000 for height to simulate infinite available height during measurement
            bound = fm.boundingRect(0, 0, rect.width(), 1000, Qt.TextFlag.TextWordWrap, self.text())
            if bound.height() <= rect.height():
                break
            current_size -= 1
            
        self._update_style(current_size)


def create_header_logo_widget(
    title_text: str | None = None,
    subtitle_text: str | None = None,
    module_name: str | None = None,
    logo_width: int = 180,
    **kwargs,
) -> QWidget:

    w = QWidget()
    w.setMinimumHeight(60)
    w.setObjectName("CertusHeader")
    w.setStyleSheet(
        f"#CertusHeader {{ background: {CertusTheme.SURFACE}; border-bottom: 1px solid {CertusTheme.BORDER}; }}"
    )
    layout = QHBoxLayout(w)
    layout.setContentsMargins(18, 8, 18, 8)

    # Logo
    if SVG_AVAILABLE and Path(get_resource_path("certus.svg")).exists():
        logo = QSvgWidget(get_resource_path("certus.svg"))
        logo.setFixedSize(logo_width, 40)
        layout.addWidget(logo)
    else:
        lbl = QLabel("CERTUS")
        lbl.setStyleSheet(f"font-weight: 800; color: {CertusTheme.PRIMARY}; font-size: 20px;")
        layout.addWidget(lbl)

    if title_text:
        layout.addSpacing(20)
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        lbl_title = AutoShrinkTitleLabel(
            title_text, 
            default_size=16, 
            min_size=9, 
            color=CertusTheme.TEXT_MAIN, 
            weight=800
        )
        vbox.addWidget(lbl_title)

        if subtitle_text:
            lbl_sub = AutoShrinkTitleLabel(
                subtitle_text, 
                default_size=12, 
                min_size=8, 
                color=CertusTheme.TEXT_SUB, 
                weight=500
            )
            vbox.addWidget(lbl_sub)

        layout.addLayout(vbox)

    layout.addStretch()

    if module_name:
        # Help Button

        btn_help = QToolButton()

        btn_help.setText("Help")

        btn_help.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))

        btn_help.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        btn_help.setFixedSize(45, 45)

        btn_help.setIconSize(QSize(18, 18))

        btn_help.setStyleSheet(f"""

            QToolButton {{

                background: transparent;

                border: none;

                color: {CertusTheme.TEXT_SUB};

                font-size: 10px;

            }}

            QToolButton:hover {{

                background: {CertusTheme.SURFACE_HOVER};

                border-radius: 4px;

                color: {CertusTheme.PRIMARY};

            }}

        """)

        btn_help.clicked.connect(functools.partial(open_documentation, module_name))

        layout.addWidget(btn_help)

    return w


def create_styled_button(text: str, variant: str = "primary", icon: QIcon | None = None, parent=None) -> QPushButton:
    """Creates a standardized styled button."""

    btn = QPushButton(text, parent)

    if icon:
        btn.setIcon(icon)

    btn.setCursor(Qt.CursorShape.PointingHandCursor)

    btn.setStyleSheet(CertusTheme.get_button_style(variant))

    return btn


def create_info_icon(tooltip: str, parent=None) -> QPushButton:
    """Creates a small '?' info icon with tooltip."""

    btn = QPushButton("?", parent)

    btn.setFixedSize(20, 20)

    btn.setToolTip(tooltip)

    btn.setCursor(Qt.CursorShape.PointingHandCursor)

    btn.setStyleSheet(f"""

        QPushButton {{

            background: {CertusTheme.SURFACE_HOVER};

            color: {CertusTheme.TEXT_SUB};

            border-radius: 10px;

            font-weight: bold;

            border: 1px solid {CertusTheme.BORDER};

        }}

        QPushButton:hover {{

            background: {CertusTheme.INFO};

            color: white;

            border-color: {CertusTheme.INFO};

        }}

    """)

    return btn


def create_help_button(module_name: str) -> QToolButton:

    btn = QToolButton()

    btn.setText("?")

    btn.setFixedSize(24, 24)

    btn.setStyleSheet(f"""

        QToolButton {{

            background: {CertusTheme.SECONDARY}; color: white; border-radius: 12px; font-weight: bold;

        }}

        QToolButton:hover {{ background: {CertusTheme.PRIMARY}; }}

    """)

    btn.clicked.connect(functools.partial(open_documentation, module_name))

    return btn


def create_styled_label(text: str, style: str = "normal", color: str | None = None, parent=None) -> QLabel:
    """Creates a styled label (Ported from HUB for DRY)."""

    lbl = QLabel(text, parent)

    font_size = CertusTheme.FONT_SIZE_BASE

    weight = QFont.Weight.Normal

    if style == "bold":
        weight = QFont.Weight.Bold

        font_size += 2

    elif style == "subtitle":
        weight = QFont.Weight.Medium

    lbl.setFont(QFont(CertusTheme.FONT_FAMILY.split(",")[0].strip("'"), font_size, weight))

    if color:
        lbl.setStyleSheet(f"color: {color};")

    return lbl


def create_colored_label(text: str, color: str, font_size: int = 11, weight: int = 50) -> QLabel:
    """Creates a simple colored label with custom font specs."""

    lbl = QLabel(text)

    lbl.setFont(QFont(CertusTheme.FONT_FAMILY.split(",")[0].strip("'"), font_size, weight))

    if color:
        lbl.setStyleSheet(f"color: {color};")

    return lbl


def create_top_actions_bar(
    parent,
    save_func,
    load_func,
    export_func=None,
    help_func=None,
    action_tooltips: dict[str, str] | None = None,
) -> QWidget:
    """Creates a standardized top action bar with Save, Load, and optional Export/Help buttons.

    Args:

        parent: Parent widget (usually self)

        save_func: Callback for Save

        load_func: Callback for Load

        export_func: Callback for Export (optional)

        help_func: Callback for Help (optional)

        action_tooltips: Optional overrides for button tooltips (keys: Save, Load, Export, Help).

    Returns:

        QWidget: The action bar widget"""

    container = QWidget()

    layout = QHBoxLayout(container)

    layout.setContentsMargins(10, 5, 10, 5)

    layout.setSpacing(5)

    def _create_btn(text, func, icon, tooltip) -> Any:

        btn = QPushButton(text)

        btn.setIcon(parent.style().standardIcon(icon))

        btn.setToolTip(tooltip)

        btn.clicked.connect(func)

        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn.setStyleSheet(f"""
            QPushButton {{
                background: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 10px;
                padding: 6px 10px;
                color: {CertusTheme.TEXT_SUB};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {CertusTheme.SURFACE_HOVER};
                color: {CertusTheme.PRIMARY};
                border-color: {CertusTheme.PRIMARY};
            }}
            QPushButton:pressed {{
                background: {CertusTheme.BORDER};
            }}
        """)

        return btn

    _tip_default: dict[str, str] = {
        "Save": "Save current configuration to a file.",
        "Load": "Load configuration from a file.",
        "Export": "Export current results.",
        "Help": "Open documentation for this module.",
    }

    if action_tooltips:
        _tip_default.update({k: v for k, v in action_tooltips.items() if v})

    # Define buttons configuration

    # (Text, Callback, Icon, ToolTip key)

    btns = [
        ("Save", save_func, QStyle.StandardPixmap.SP_DialogSaveButton, "Save"),
        ("Load", load_func, QStyle.StandardPixmap.SP_DialogOpenButton, "Load"),
    ]

    if export_func:
        btns.append(("Export", export_func, QStyle.StandardPixmap.SP_DialogApplyButton, "Export"))

    if help_func:
        btns.append(("Help", help_func, QStyle.StandardPixmap.SP_DialogHelpButton, "Help"))

    for text, func, icon, tip_key in btns:
        if func:  # Only add if callback provided
            layout.addWidget(_create_btn(text, func, icon, _tip_default.get(tip_key, "")))

    layout.addStretch()

    return container


def open_documentation(module_name: str) -> None:
    """Open the HTML documentation page for a CERTUS module."""

    import webbrowser

    module_aliases = {
        "FIELD": "CERTUS_FIELD",
        "CERTUS_FIELD": "CERTUS_FIELD",
        "INDEX_SPLINE": "CERTUS_INDEX_SPLINE",
        "CERTUS_INDEX_SPLINE": "CERTUS_INDEX_SPLINE",
        "INDEX": "CERTUS_INDEX",
        "CERTUS_INDEX": "CERTUS_INDEX",
        "DESIGN": "CERTUS_DESIGN",
        "CERTUS_DESIGN": "CERTUS_DESIGN",
        "RE": "CERTUS_RE",
        "CERTUS_RE": "CERTUS_RE",
        "STRAT": "CERTUS_STRAT",
        "CERTUS_STRAT": "CERTUS_STRAT",
        "SUBSTRATE": "CERTUS_SUBSTRATE_INDEX",
        "CERTUS_SUBSTRATE_INDEX": "CERTUS_SUBSTRATE_INDEX",
        "METAL SINGLE": "CERTUS_METAL_SINGLE",
        "METAL_BILAYER": "CERTUS_METAL_BILAYER",
        "CERTUS_METAL_SINGLE": "CERTUS_METAL_SINGLE",
        "CERTUS_METAL_BILAYER": "CERTUS_METAL_BILAYER",
    }
    module_key = module_aliases.get(module_name.strip().upper(), module_name.strip().upper())
    path = get_resource_path(f"pages/{module_key}.html")

    if Path(path).exists():
        webbrowser.open(QUrl.fromLocalFile(path).toString())
        return

    fallback_candidates = [
        get_resource_path("pages/CERTUS_HUB.html"),
        get_resource_path("pages/CERTUS_INDEX.html"),
    ]
    for fallback in fallback_candidates:
        if Path(fallback).exists():
            webbrowser.open(QUrl.fromLocalFile(fallback).toString())
            return


# NOTE: CertusScientificPlot is defined later in this file (line ~827) with full features


# including add_curve(), update_curve(), export capabilities, etc.


class DetachedPlotWindow(QMainWindow):
    closed_signal = pyqtSignal()

    def __init__(self, plot_widget, parent=None, title="Detached Plot") -> None:

        super().__init__(parent)

        self.setWindowTitle(title)

        self.resize(1150, 780)

        self.setMinimumSize(520, 380)

        self.plot_widget = plot_widget

        # Central widget container

        c = QWidget()

        self.setCentralWidget(c)

        l = QVBoxLayout(c)

        l.setContentsMargins(0, 0, 0, 0)

        l.setSpacing(0)

        # Header with Logo (Systematic)

        l.addWidget(create_header_logo_widget(title_text=title, logo_width=180))

        # Optional toolbar from the widget itself

        if hasattr(plot_widget, "get_toolbar"):
            tb = plot_widget.get_toolbar(self)

            if tb:
                l.addWidget(tb)

        # The Plot Logic

        l.addWidget(plot_widget)

        # Apply Theme

        apply_certus_theme(self)

        set_certus_window_icon(self)

    def closeEvent(self, e) -> None:

        self.closed_signal.emit()

        super().closeEvent(e)


class ExcelTableWidget(QTableWidget):
    """Table with copy-paste"""

    def keyPressEvent(self, e) -> None:

        if e.matches(QKeySequence.StandardKey.Paste):
            self._paste()

        elif e.matches(QKeySequence.StandardKey.Copy):
            self._copy()

        elif e.key() == Qt.Key.Key_Delete:
            self._delete()

        else:
            super().keyPressEvent(e)

    def _paste(self) -> None:

        clip = QApplication.clipboard().text()

        if not clip:
            return

        rows = clip.split("\n")

        r = max(0, self.currentRow())

        c = max(0, self.currentColumn())

        if r + len(rows) > self.rowCount():
            self.setRowCount(r + len(rows))

        for i, row in enumerate(rows):
            vals = row.split("\t")

            for j, v in enumerate(vals):
                if c + j < self.columnCount():
                    self.setItem(r + i, c + j, QTableWidgetItem(v.strip()))

    def _copy(self) -> None:

        sel = self.selectedRanges()

        if not sel:
            return

        s = ""

        for r in range(sel[0].topRow(), sel[0].bottomRow() + 1):
            row = []

            for c in range(sel[0].leftColumn(), sel[0].rightColumn() + 1):
                it = self.item(r, c)

                row.append(it.text() if it else "")

            s += "\t".join(row) + "\n"

        QApplication.clipboard().setText(s)

    def _delete(self) -> None:

        for it in self.selectedItems():
            it.setText("")

    def set_data(self, headers: list[str], data: list[list[str]]) -> None:
        """Standard method to populate table data."""

        self.setColumnCount(len(headers))

        self.setHorizontalHeaderLabels(headers)

        self.setRowCount(len(data))

        for r, row in enumerate(data):
            for c, val in enumerate(row):
                self.setItem(r, c, QTableWidgetItem(str(val)))

    def export_to_excel(self, filename: str) -> bool:
        """Export table content to Excel file."""

        try:
            rows = self.rowCount()

            cols = self.columnCount()

            data = []

            headers = [self.horizontalHeaderItem(c).text() for c in range(cols)]

            for r in range(rows):
                row_data = []

                for c in range(cols):
                    item = self.item(r, c)

                    row_data.append(item.text() if item else "")

                data.append(row_data)

            df = pd.DataFrame(data, columns=headers)

            df.to_excel(filename, index=False)

            return True

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            import traceback

            logging.error(f"Excel export failed:{e}\n{traceback.format_exc()}")

            return False


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other) -> Any:

        try:
            return float(self.text()) < float(other.text())

        except (ValueError, TypeError):
            # Fallback to string comparison if not numeric

            return super().__lt__(other)


class FlashyCard(QFrame):
    """

    Styled card widget for displaying feature highlights.

    Args:

        title: Card title (bold, larger font)

        subtitle: Card description text

        icon: Optional emoji or icon character

    """

    def __init__(self, title: str, subtitle: str, icon: str = "") -> None:

        super().__init__()

        self.setStyleSheet(
            f"background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; border-radius: 12px;"
        )

        l = QVBoxLayout(self)

        if icon:
            lbl = QLabel(icon)

            lbl.setStyleSheet("font-size: 48px;")

            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            l.addWidget(lbl)

        t = QLabel(title)

        t.setStyleSheet(f"font-weight: bold; font-size: 16px; color: {CertusTheme.TEXT_MAIN}")

        t.setAlignment(Qt.AlignmentFlag.AlignCenter)

        l.addWidget(t)

        s = QLabel(subtitle)

        s.setStyleSheet(f"color: {CertusTheme.TEXT_SUB};")

        s.setAlignment(Qt.AlignmentFlag.AlignCenter)

        s.setWordWrap(True)

        l.addWidget(s)

        try:
            from certus.ui.certus_animations import hover_lift

            hover_lift(self, lift_px=3)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


class WelcomeGuideWidget(QWidget):
    """

    Welcome/onboarding widget showing app name and optional steps.

    Args:

        app_name: Application name to display

        steps: List of step descriptions for the guide

    """

    def __init__(self, app_name: str = "CERTUS", steps: list[str] | None = None) -> None:

        super().__init__()

        steps = steps or []

        l = QVBoxLayout(self)

        l.addWidget(QLabel(f"Welcome to {app_name}"))

        # Simplified for brevity


# ProgressDialog removed (duplicate of line 537)


# =============================================================================
# PRO UX COMPONENTS (2026 Design System)
# =============================================================================


class CertusCard(QFrame):
    """Flat card replacing heavy QGroupBox. Exposes .body (QVBoxLayout) for content."""

    def __init__(self, title: str = "", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CertusCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._intro_fade_started = False
        self._refresh_style()
        self.setGraphicsEffect(CertusTheme.get_shadow(self))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if title:
            hdr = QWidget()
            hdr.setObjectName("CertusCardHeader")
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(12, 8, 12, 6)
            hl.setSpacing(6)
            lbl = QLabel(title)
            lbl.setObjectName("CertusCardTitle")
            lbl.setStyleSheet(
                f"font-weight: 700; font-size: 11px; color: {CertusTheme.TEXT_MAIN}; letter-spacing: 0.3px;"
            )
            hl.addWidget(lbl)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setStyleSheet(f"font-size: 10px; color: {CertusTheme.TEXT_SUB};")
                hl.addWidget(sub)
            hl.addStretch(1)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {CertusTheme.BORDER};")
            outer.addWidget(hdr)
            outer.addWidget(sep)
        body_w = QWidget()
        self.body = QVBoxLayout(body_w)
        self.body.setContentsMargins(12, 8, 12, 10)
        self.body.setSpacing(6)
        outer.addWidget(body_w)

    def _refresh_style(self) -> None:
        self.setStyleSheet(
            f"#CertusCard {{ background: {CertusTheme.SURFACE}; border: 1px solid {CertusTheme.BORDER}; "
            f"border-radius: 8px; }}"
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(self, "_intro_fade_started", False):
            return
        self._intro_fade_started = True
        try:
            from certus.ui.certus_animations import fade_in

            fade_in(self, duration_ms=180)
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Animation module unavailable or function not found - skip animation
            pass


class CertusSectionHeader(QWidget):
    """Lightweight section divider: bold title + optional muted caption."""

    def __init__(self, title: str, caption: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 2)
        lay.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-weight: 700; font-size: 11px; color: {CertusTheme.TEXT_MAIN}; "
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        lay.addWidget(lbl)
        if caption:
            cap = QLabel(caption)
            cap.setStyleSheet(f"font-size: 10px; color: {CertusTheme.TEXT_SUB};")
            lay.addWidget(cap)
        lay.addStretch(1)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {CertusTheme.BORDER};")
        lay.addWidget(sep)


class CertusStepper(QWidget):
    """Compact vertical stepper. step_activated(int) emitted on click."""

    step_activated = pyqtSignal(int)

    def __init__(self, steps: list, parent=None, columns: int = 1) -> None:
        super().__init__(parent)
        self._steps = steps
        self._current = 0
        self._columns = max(1, int(columns or 1))
        self._btns: list[QPushButton] = []
        self._badges: list[QPushButton] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        if self._columns <= 1:
            for i, label in enumerate(steps):
                row = QHBoxLayout()
                row.setSpacing(6)
                # Circle badge
                badge = QPushButton(str(i + 1))
                badge.setFixedSize(22, 22)
                badge.setEnabled(False)
                badge.setObjectName(f"StepBadge_{i}")
                badge.setStyleSheet(self._badge_style(i))
                # Label
                btn = QPushButton(label)
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setObjectName(f"StepBtn_{i}")
                btn.setStyleSheet(self._btn_style(i))
                idx = i

                def _handle_click(*_args, step_index=idx) -> None:
                    self._on_click(step_index)

                btn.clicked.connect(_handle_click)
                row.addWidget(badge)
                row.addWidget(btn, 1)
                row.addStretch(0)
                self._btns.append(btn)
                self._badges.append(badge)
                lay.addLayout(row)
                if i < len(steps) - 1:
                    connector = QLabel()
                    connector.setFixedWidth(2)
                    connector.setMinimumHeight(4)
                    connector.setStyleSheet(f"background: {CertusTheme.BORDER}; margin-left: 10px;")
                    connector_row = QHBoxLayout()
                    connector_row.setContentsMargins(10, 0, 0, 0)
                    connector_row.addWidget(connector)
                    connector_row.addStretch(1)
                    lay.addLayout(connector_row)
        else:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)
            for i, label in enumerate(steps):
                row_idx = int(i // self._columns)
                col_idx = int(i % self._columns)
                cell = QHBoxLayout()
                cell.setSpacing(6)
                badge = QPushButton(str(i + 1))
                badge.setFixedSize(22, 22)
                badge.setEnabled(False)
                badge.setObjectName(f"StepBadge_{i}")
                badge.setStyleSheet(self._badge_style(i))
                btn = QPushButton(label)
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setObjectName(f"StepBtn_{i}")
                btn.setStyleSheet(self._btn_style(i))
                idx = i

                def _handle_click(*_args, step_index=idx) -> None:
                    self._on_click(step_index)

                btn.clicked.connect(_handle_click)
                cell.addWidget(badge)
                cell.addWidget(btn, 1)
                grid.addLayout(cell, row_idx, col_idx)
                self._btns.append(btn)
                self._badges.append(badge)
            lay.addLayout(grid)

    def _badge_style(self, i: int) -> str:
        active = i == self._current
        done = i < self._current
        if active:
            bg, fg, border = CertusTheme.PRIMARY, "#fff", CertusTheme.PRIMARY
        elif done:
            bg, fg, border = CertusTheme.SUCCESS, "#fff", CertusTheme.SUCCESS
        else:
            bg, fg, border = CertusTheme.SURFACE, CertusTheme.TEXT_SUB, CertusTheme.BORDER
        return (
            f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {border}; "
            f"border-radius: 12px; font-weight: 700; font-size: 10px; }}"
        )

    def _btn_style(self, i: int) -> str:
        active = i == self._current
        done = i < self._current
        if active:
            color, weight = CertusTheme.PRIMARY, "700"
        elif done:
            color, weight = CertusTheme.TEXT_SUB, "500"
        else:
            color, weight = CertusTheme.TEXT_SUB, "400"
        return (
            f"QPushButton {{ background: transparent; border: none; color: {color}; "
            f"font-weight: {weight}; font-size: 11px; text-align: left; padding: 0; "
            f"min-height: 16px; }}"
        )

    def _on_click(self, idx: int) -> None:
        self.step_activated.emit(idx)

    def set_step(self, idx: int) -> None:
        self._current = max(0, min(idx, len(self._steps) - 1))
        self._refresh()

    def _refresh(self) -> None:
        for i, btn in enumerate(self._btns):
            btn.setStyleSheet(self._btn_style(i))
            if i < len(self._badges):
                self._badges[i].setStyleSheet(self._badge_style(i))


class CertusCollapsible(QWidget):
    """Collapsible section: chevron header + body widget. Toggles on click."""

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header button
        self._hdr = QPushButton()
        self._hdr.setFlat(True)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr.setCheckable(True)
        self._hdr.setChecked(expanded)
        self._title = title
        self._hdr.clicked.connect(self._toggle)
        self._hdr.setStyleSheet(
            f"QPushButton {{ background: {CertusTheme.SURFACE_HOVER}; border: none; "
            f"border-radius: 6px; padding: 6px 10px; font-weight: 600; font-size: 11px; "
            f"color: {CertusTheme.TEXT_MAIN}; text-align: left; }}"
            f"QPushButton:hover {{ background: {CertusTheme.BORDER}; }}"
        )
        lay.addWidget(self._hdr)

        self._content = content
        self._content.setVisible(expanded)
        lay.addWidget(self._content)
        self._update_label()

    def _toggle(self) -> None:
        visible = not self._content.isVisible()
        try:
            from certus.ui.certus_animations import fade_in, fade_out

            if visible:
                self._content.setVisible(True)
                fade_in(self._content, duration_ms=180)
            else:
                fade_out(self._content, duration_ms=150, hide_on_finish=True)
        except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError):
            # Animation module/function failed - fallback to direct visibility change
            self._content.setVisible(visible)
        self._update_label()

    def _update_label(self) -> None:
        arrow = "▾" if self._content.isVisible() else "▸"
        self._hdr.setText(f"{arrow}  {self._title}")

    def is_expanded(self) -> bool:
        return bool(self._content.isVisible())

    def set_expanded(self, expanded: bool) -> None:
        want = bool(expanded)
        if self._content.isVisible() == want:
            self._hdr.setChecked(want)
            self._update_label()
            return
        self._hdr.setChecked(want)
        self._toggle()


class CertusStatusPill(QLabel):
    """Compact status badge: 'Ready', 'Running', 'Done', 'Error'. Same API as QLabel."""

    def __init__(self, text: str = "Ready", level: str = "ready", parent=None) -> None:
        super().__init__(text, parent)
        self._level = level
        self.setWordWrap(True)
        self._apply()

    def _levels(self) -> dict:
        return {
            "ready": (CertusTheme.SUCCESS + "22", CertusTheme.SUCCESS, CertusTheme.SUCCESS + "55"),
            "running": (CertusTheme.PRIMARY + "22", CertusTheme.PRIMARY, CertusTheme.PRIMARY + "55"),
            "done": (CertusTheme.SECONDARY + "22", CertusTheme.TEXT_MAIN, CertusTheme.BORDER),
            "error": (CertusTheme.DANGER + "22", CertusTheme.DANGER, CertusTheme.DANGER + "55"),
            "warning": (CertusTheme.WARNING + "22", CertusTheme.TEXT_MAIN, CertusTheme.WARNING + "55"),
            "default": (CertusTheme.SURFACE_HOVER, CertusTheme.TEXT_SUB, CertusTheme.BORDER),
        }

    def set_level(self, level: str) -> None:
        self._level = level
        self._apply()

    def setText(self, text: str) -> None:
        super().setText(text)

    def _apply(self) -> None:
        bg, fg, border = self._levels().get(self._level, self._levels()["default"])
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {border}; "
            f"border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600;"
        )


class CertusActionBar(QWidget):
    """Compact horizontal action bar: Run / Stop + optional toggles in a styled container."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(6)
        self.setObjectName("CertusActionBar")
        self.setStyleSheet(
            f"#CertusActionBar {{ background: {CertusTheme.SURFACE}; "
            f"border: 1px solid {CertusTheme.BORDER}; border-radius: 8px; }}"
        )

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._layout.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)



# =============================================================================
# UX helpers (phase 2): shortcuts, file drop, toast, validator, empty state
# =============================================================================


def install_standard_shortcuts(
    window: QWidget,
    save=None,
    load=None,
    export=None,
    run=None,
    stop=None,
    help=None,
    toggle_logs=None,
    zoom_in=None,
    zoom_out=None,
    reset_zoom=None,
    extra: dict | None = None,
) -> dict:
    """Install the standard CERTUS keyboard shortcuts on a window.

    Callers pass only the callbacks they want wired. Returns a dict of QShortcut
    keyed by action name so callers can rebind or disable them later.
    """
    mapping = {
        "save": ("Ctrl+S", save),
        "load": ("Ctrl+O", load),
        "export": ("Ctrl+E", export),
        "run": ("F5", run),
        "stop": ("Esc", stop),
        "help": ("F1", help),
        "toggle_logs": ("Ctrl+L", toggle_logs),
        # Zoom shortcuts are intentionally duplicated to match the behavior users
        # expect across Qt apps, browsers and pro desktop tools.
        "zoom_in": ("Ctrl+Plus", zoom_in),
        "zoom_out": ("Ctrl+Minus", zoom_out),
        "reset_zoom": ("Ctrl+0", reset_zoom),
    }
    installed: dict = {}
    for name, (seq, cb) in mapping.items():
        if cb is None:
            continue
        for candidate in (seq,):
            sc = QShortcut(QKeySequence(candidate), window)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(cb)
            installed[f"{name}:{candidate}"] = sc
    # Also register legacy / platform-friendly variants so zoom feels native.
    alias_map = {
        "zoom_in": ("Ctrl++", "Ctrl+=", "Ctrl+Shift+=", "Ctrl+Equal"),
        "zoom_out": ("Ctrl+-", "Ctrl+Minus", "Ctrl+Underscore"),
        "reset_zoom": ("Ctrl+0",),
    }
    for name, candidates in alias_map.items():
        cb = mapping[name][1]
        if cb is None:
            continue
        for candidate in candidates:
            try:
                sc = QShortcut(QKeySequence(candidate), window)
                sc.setContext(Qt.ShortcutContext.WindowShortcut)
                sc.activated.connect(cb)
                installed[f"{name}:{candidate}"] = sc
            except (TypeError, RuntimeError, ValueError):
                logging.getLogger("CERTUS").debug("Invalid shortcut %s", candidate, exc_info=True)
    if extra:
        for seq, cb in extra.items():
            if cb is None:
                continue
            sc = QShortcut(QKeySequence(seq), window)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(cb)
            installed[seq] = sc
    return installed


class _CertusDropFilter(QObject):
    """Event filter that forwards drop events to a handler callback."""

    def __init__(self, parent: QWidget, handler, extensions) -> None:
        super().__init__(parent)
        self._handler = handler
        self._ext = tuple(e.lower().lstrip(".") for e in (extensions or ()))

    def _paths_from_event(self, event) -> list:
        md = event.mimeData()
        if not md or not md.hasUrls():
            return []
        out = []
        for url in md.urls():
            p = url.toLocalFile()
            if not p:
                continue
            if self._ext and p.lower().rsplit(".", 1)[-1] not in self._ext:
                continue
            out.append(p)
        return out

    def eventFilter(self, obj, event) -> Any:
        t = event.type()
        if t in (event.Type.DragEnter, event.Type.DragMove):
            if self._paths_from_event(event):
                event.acceptProposedAction()
                return True
        elif t == event.Type.Drop:
            paths = self._paths_from_event(event)
            if paths:
                try:
                    self._handler(paths)
                except (RuntimeError, OSError, ValueError, TypeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)


def enable_file_drop(widget: QWidget, handler, extensions=None) -> QObject:
    """Enable drag & drop of files on widget. handler(paths) called on drop."""
    widget.setAcceptDrops(True)
    flt = _CertusDropFilter(widget, handler, extensions)
    widget.installEventFilter(flt)
    return flt


class CertusToast(QLabel):
    """Non-modal transient notification auto-hiding after duration_ms."""

    _LEVELS = {
        "info": ("PRIMARY", "#fff"),
        "success": ("SUCCESS", "#fff"),
        "warning": ("WARNING", "#222"),
        "error": ("DANGER", "#fff"),
    }

    def __init__(self, parent: QWidget, text: str, level: str = "info", duration_ms: int = 2800) -> None:
        super().__init__(parent)
        color_key, fg = self._LEVELS.get(level, self._LEVELS["info"])
        bg = getattr(CertusTheme, color_key, CertusTheme.PRIMARY)
        self.setText(text)
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 11px;"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        QTimer.singleShot(duration_ms, self.close)

    def _reposition(self) -> None:
        p = self.parent()
        if not isinstance(p, QWidget):
            return
        margin = 18
        x = p.width() - self.width() - margin
        y = p.height() - self.height() - margin - 22
        self.move(max(margin, x), max(margin, y))


def show_toast(parent: QWidget, text: str, level: str = "info", duration_ms: int = 2800) -> Any:
    """Convenience wrapper. Silently no-ops if parent is None.

    P0.1 integration: routes through :mod:`certus_toast_stack` when available
    so every legacy call site benefits from stacked notifications, fade
    animations and click-to-dismiss. Falls back to the legacy single-label
    :class:`CertusToast` if the stacked module is unreachable.
    """
    if parent is None:
        return None
    try:
        from certus.ui.certus_toast_stack import show_toast_stack

        variant = {"info": "info", "success": "success", "warning": "warning", "error": "error"}.get(
            str(level).lower(), "info"
        )
        stacked = show_toast_stack(parent, text, variant=variant, duration_ms=duration_ms)
        if stacked is not None:
            return stacked
    except (ImportError, AttributeError, RuntimeError, TypeError):
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
    return CertusToast(parent, text, level=level, duration_ms=duration_ms)


def show_status_feedback(parent: QWidget, text: str, level: str = "info", duration_ms: int = 2800) -> Any:
    """Show premium feedback and mirror it to known status widgets."""
    result = show_toast(parent, text, level=level, duration_ms=duration_ms)
    for attr in ("status_label", "lbl_status", "status_text", "statusMessage"):
        try:
            widget = getattr(parent, attr, None)
            if hasattr(widget, "setText"):
                widget.setText(text)
                break
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    return result


def attach_numeric_validator(
    line_edit: QLineEdit,
    minimum=None,
    maximum=None,
    kind: str = "float",
) -> None:
    """Visually flag invalid numeric input without blocking typing."""
    base_ss = line_edit.styleSheet()
    err_ss = base_ss + (f" QLineEdit {{ border: 1px solid {CertusTheme.DANGER}; background: {CertusTheme.DANGER}11; }}")

    def _validate() -> None:
        txt = line_edit.text().strip()
        if not txt:
            line_edit.setStyleSheet(base_ss)
            line_edit.setToolTip("")
            return
        try:
            val = float(txt) if kind == "float" else int(txt)
        except ValueError:
            line_edit.setStyleSheet(err_ss)
            line_edit.setToolTip(f"Invalid {kind} value")
            return
        if minimum is not None and val < minimum:
            line_edit.setStyleSheet(err_ss)
            line_edit.setToolTip(f"Value must be >= {minimum}")
            return
        if maximum is not None and val > maximum:
            line_edit.setStyleSheet(err_ss)
            line_edit.setToolTip(f"Value must be <= {maximum}")
            return
        line_edit.setStyleSheet(base_ss)
        line_edit.setToolTip("")

    def _on_text_changed(*_args) -> None:
        _validate()

    line_edit.textChanged.connect(_on_text_changed)
    _validate()



# =============================================================================


# THREADING


# =============================================================================


class WorkerSignals(QObject):
    """

    Thread-safe signals for worker-to-GUI communication.

    Used by GenericWorker and other workers to emit signals

    from background threads to the main GUI thread.

    Signals:

        started: Emitted when the worker starts

        finished: Emitted when the worker finishes (with result)

        error: Emitted on error (tuple or str)

        progress: Emitted to update progress (int, str)

        update_stats: Emitted to update statistics (key, value)

        result: Emitted with the computation result

    """

    started = pyqtSignal()

    finished = pyqtSignal(object)

    error = pyqtSignal(object)  # Was tuple, now object to support str tracebacks

    progress = pyqtSignal(int, str)
    progress_sub = pyqtSignal(int, int, str, str)

    update_stats = pyqtSignal(str, object)  # "Key", Value

    result = pyqtSignal(object)

    live = pyqtSignal(object)


class GenericWorker(QThread):
    """

    Generic worker thread for running arbitrary functions in background.

    """

    def __init__(self, func: Callable, *args, **kwargs) -> None:

        super(GenericWorker, self).__init__()

        self.func = func

        self.args = args

        self.kwargs = kwargs

        self.signals = WorkerSignals()

        self._stop = False

    def run(self) -> None:

        self.signals.started.emit()

        try:
            if "stop_check" in self.kwargs:
                self.kwargs["stop_check"] = lambda: self._stop

            res = self.func(*self.args, **self.kwargs)

            if not self._stop:
                self.signals.result.emit(res)

                self.signals.finished.emit(res)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            # Send full traceback for better debugging

            tb_str = "".join(traceback.format_tb(e.__traceback__))

            self.signals.error.emit((type(e), e, tb_str))

    def stop(self) -> None:

        self._stop = True


class CertusWorkerBase(QThread):
    """

    Base worker class with standard signals and stop management.

    Provides:

    - Standard signals (finished, error, progress, stats_update)

    - Thread-safe stop request mechanism

    - Progress throttling to reduce GUI overhead

    - Automatic exception handling with traceback

    Subclasses should override `do_work()` method.

    Example:

        >>> class MyWorker(CertusWorkerBase):

        ...     def do_work(self):

        ...         for i in range(100):

        ...             if self.is_stop_requested():

        ...                 return None

        ...             self.emit_progress_throttled(i, f"Step {i}")

        ...         return result

    """

    finished = pyqtSignal(object)

    error = pyqtSignal(object)

    progress = pyqtSignal(int, str)
    progress_sub = pyqtSignal(int, int, str, str)

    stats_update = pyqtSignal(str, int)

    def __init__(self, parent=None) -> None:

        super().__init__(parent)

        self._stop_requested = False

        self._last_progress_time = 0.0

        self._progress_interval = 0.1  # 100ms minimum between progress updates

    def request_stop(self) -> None:
        """Request the worker to stop. Thread-safe."""

        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        """Check if stop was requested. Thread-safe."""

        return self._stop_requested

    def emit_stats(self, counter_type: str, increment: int = 1) -> None:
        """Emit stats update signal."""

        self.stats_update.emit(counter_type, increment)

    def do_work(self) -> Any:
        """

        Override this method in subclasses to perform actual work.

        Returns:

            Result object to be emitted via finished signal

        """

        raise NotImplementedError("Subclasses must implement do_work()")

    def run(self) -> None:
        """Thread entry point. Handles exceptions and emits signals."""

        self._stop_requested = False

        self._last_progress_time = 0.0

        try:
            result = self.do_work()

            if not self._stop_requested:
                self.finished.emit(result)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            import traceback

            self.error.emit((type(e), e, traceback.format_exc()))


def get_export_settings() -> dict[str, Any]:
    """Returns standard export settings for plot/image export.

    Returns:

        Dictionary with keys: dpi, width, height, font_scale, format"""

    return {
        "dpi": 300,
        "width": 1920,
        "height": 1080,
        "font_scale": 1.0,
        "format": "png",
    }


# Re-export get_export_config from certus.core.certus_core for convenience


from certus.core.certus_core import get_export_config, setup_module_logging


def open_file_explorer(path: str) -> None:
    """

    Opens the file explorer at the given path.

    Args:

        path: File or directory path to open in file explorer

    Raises:

        FileNotFoundError: If path does not exist

        OSError: If platform-specific command fails

    """

    try:
        resolved_path = Path(path).resolve()

        if not resolved_path.exists():
            logging.warning(f"Path does not exist: {path}")

            return

        path_str = str(resolved_path)

        if sys.platform == "win32":
            try:
                if resolved_path.is_dir():
                    os.startfile(path_str)

                else:
                    import subprocess

                    # Use shell=False for better security

                    subprocess.Popen(
                        ["explorer", "/select,", path_str],
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open Windows explorer: {e}")

                raise

        elif sys.platform == "darwin":
            try:
                import subprocess

                subprocess.Popen(
                    ["open", "-R", path_str],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open macOS finder: {e}")

                raise

        else:  # linux
            try:
                import subprocess

                subprocess.Popen(
                    ["xdg-open", str(resolved_path.parent)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open Linux file manager: {e}")

                raise

    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logging.warning(f"Error opening file explorer for {path}: {e}")


# =============================================================================


# LOGGING


# =============================================================================


def process_log_queue_standard(q: queue.Queue, widget: Any, max_items: int = 50) -> int:
    """

    Process log messages from queue and append to widget.

    Thread-safe: if called from a thread other than the widget's,

    appends are scheduled on the widget's thread via QueuedConnection

    to avoid "QObject: Cannot create children for a parent that is in a different thread".

    """

    count = 0

    widget_thread = widget.thread() if hasattr(widget, "thread") else None

    current = QThread.currentThread()

    while count < max_items:
        try:
            msg = q.get_nowait()

        except queue.Empty:
            break

        try:
            formatted_msg = msg
            parts = msg.split(" | ", 2)
            if len(parts) == 3:
                asctime, levelname, actual_msg = parts

                # Get theme colors
                try:
                    from certus.ui.certus_ui import CertusTheme
                    c_success = CertusTheme.SUCCESS
                    c_error = CertusTheme.ERROR
                    c_warning = CertusTheme.WARNING
                    c_info = CertusTheme.TEXT_SUB
                except Exception:
                    c_success = "#10b981"
                    c_error = "#ef4444"
                    c_warning = "#f59e0b"
                    c_info = "#94a3b8"

                colors = {
                    "SUCCESS": c_success,
                    "ERROR": c_error,
                    "WARNING": c_warning,
                }
                c = colors.get(levelname, c_info)

                # Compute elapsed time
                elapsed_str = ""
                app = widget.window() if hasattr(widget, "window") else None
                if app is not None:
                    # Detect start of optimization/calculation to set start time
                    is_top_start = (
                        ("Starting" in actual_msg or "STARTING" in actual_msg)
                        and "optimization" in actual_msg
                        and not any(sub in actual_msg for sub in ("Auto-Restart", "PGLOBAL Global", "iterative", "local re-optimization"))
                    ) or "Creating REWorker" in actual_msg or "Calling worker.start()" in actual_msg

                    if is_top_start:
                        import time as _time
                        app._workflow_wall_start = _time.time()

                    t0 = getattr(app, "_workflow_wall_start", None)
                    if t0 is not None:
                        import time as _time
                        elapsed = _time.time() - t0
                        m, s = divmod(int(elapsed), 60)
                        elapsed_str = f" <b>({m}m{s:02d}s)</b>"

                formatted_msg = f"<span style='color:{c}'><b>[{asctime}]</b>{elapsed_str} {actual_msg}</span>"

            if widget_thread is not None and current is not widget_thread:
                QMetaObject.invokeMethod(
                    widget,
                    "append",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, formatted_msg),
                )

            else:
                widget.append(formatted_msg)

            count += 1

        except NUMERICAL_FAULT_EXCEPTIONS :
            break

    return count


def init_certus_app(app_name: str = "CERTUS", app: QApplication | None = None, *args, **kwargs) -> QApplication:
    """

    Initialize Qt Application with Theme and High DPI scaling.

    Supports legacy signature (app, name, version, dark_mode) via args/kwargs ignore.

    Args:

        app_name: Application name

        app: Optional QApplication instance (creates if None)

        *args, **kwargs: Ignored (for legacy compatibility)

    Returns:

        QApplication instance

    """

    # If first arg is actually a QApplication (legacy call adaptation)

    if isinstance(app_name, QApplication):
        app = app_name

        # Try to find name in args if present

        if args:
            app_name = args[0] if isinstance(args[0], str) else "CERTUS"

    # High DPI scaling (standardized across all modules)

    # MUST BE SET BEFORE QAPPLICATION INSTANTIATION

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        if not QApplication.instance():
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    if app is None:
        app = QApplication.instance() or QApplication(sys.argv)

    # Filter out noisy and annoying Qt C++ warning messages (QPainter overlaps, etc.)
    try:
        from PyQt6.QtCore import qInstallMessageHandler
        def qt_message_handler(msg_type, context, msg):
            msg_str = str(msg)
            if any(w in msg_str for w in ("QPainter", "Painter not active", "paintEngine")):
                return
            sys.stderr.write(msg_str + "\n")
        qInstallMessageHandler(qt_message_handler)
    except Exception:
        pass

    # Windows Taskbar Icon Fix (AppUserModelID)

    if os.name == "nt":
        try:
            import ctypes

            myappid = f"certus.suite.v2026.0202.{app_name}"  # Arbitrary ID

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    # Set Global App Icon

    icon_path = get_resource_path("certus.ico")

    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    CertusTheme.apply_to_app(app)

    app.setApplicationName(app_name)

    setup_pyqtgraph_defaults()

    return app


# =============================================================================


# OPTIONAL HELPERS


# =============================================================================


def _patch_pyqtgraph_viewbox_nan_transform_angle() -> None:
    """

    Python 3.14: round(float('nan')) raises ValueError.

    PyQtGraph ViewBox.childrenBounds calls round(item.transformAngle()) without guard;

    a NaN angle (invalid transform, NaN data in an item) crashes the repaint.

    """

    try:
        from pyqtgraph.graphicsItems.ViewBox import ViewBox

    except ImportError:
        return

    if getattr(ViewBox, "_certus_nan_transform_angle_patch", False):
        return

    _orig = ViewBox.childrenBounds

    def childrenBounds(self, frac=None, orthoRange=(None, None), items=None) -> Any:

        try:
            return _orig(self, frac=frac, orthoRange=orthoRange, items=items)

        except (ValueError, OverflowError, ArithmeticError) as e:
            msg = str(e).lower()

            if any(
                t in msg
                for t in (
                    "nan",
                    "inf",
                    "cannot convert float",
                    "cannot convert",
                    "overflow",
                    "invalid",
                )
            ):
                return [None, None]

            raise

    ViewBox.childrenBounds = childrenBounds

    ViewBox._certus_nan_transform_angle_patch = True


def setup_pyqtgraph_defaults() -> None:
    """Configure PyQtGraph with CERTUS standard settings."""

    try:
        import pyqtgraph as pg

        from certus.ui.certus_ui import load_theme_config, update_global_plot_config

        update_global_plot_config(load_theme_config() == "dark")

        pg.setConfigOptions(antialias=True)

        _patch_pyqtgraph_viewbox_nan_transform_angle()

    except ImportError:
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


def setup_gui_exception_handling() -> None:
    """Install global exception hook for GUI applications."""

    import sys

    sys.excepthook = handle_exception


def safe_ui_action(func):
    """Decorator that wraps a UI action with standard robust error handling.

    - Executes the decorated method safely.
    - Catches CertusError (user-facing): pops a QMessageBox or shows a toast notification.
    - Catches other exceptions (unhandled/generic): logs a detailed stack trace to the structured JSONL file,
      and shows a general error message to the user to prevent crashing the UI loop.
    """
    import functools
    import logging
    from PyQt6.QtWidgets import QApplication, QWidget

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from certus.utils.errors import (
            CertusError,
            CertusValidationError,
            NUMERICAL_FAULT_EXCEPTIONS,
        )
        import inspect

        try:
            sig = inspect.signature(func)
            has_var_positional = any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values())
            if not has_var_positional:
                pos_params_count = sum(
                    1 for p in sig.parameters.values()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                )
                if len(args) > pos_params_count:
                    args = args[:pos_params_count]
        except Exception:
            pass

        app_instance = QApplication.instance()

        parent = None
        if args and isinstance(args[0], QWidget):
            parent = args[0]
        elif app_instance is not None:
            parent = app_instance.activeWindow()

        try:
            return func(*args, **kwargs)
        except CertusValidationError as e:
            logger = logging.getLogger("CERTUS")
            logger.warning(f"Validation error in {func.__qualname__}: {e.message}", exc_info=True)
            if app_instance is None:
                return None
            try:
                from certus.ui.certus_ui import show_toast
                show_toast(parent, f"Validation: {e.message}", level="warning", duration_ms=4000)
            except Exception:
                from certus.utils.errors import show_validation_error
                show_validation_error(parent, e)
            return None
        except CertusError as e:
            logger = logging.getLogger("CERTUS")
            logger.error(f"Certus domain error in {func.__qualname__}: {e.message}", exc_info=True)
            if app_instance is None:
                return None
            try:
                from PyQt6.QtWidgets import QMessageBox
                msg = QMessageBox(parent)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(e.message)
                msg.setText(e.message)
                if e.details:
                    msg.setDetailedText(e.details)
                if e.suggestion:
                    msg.setInformativeText(f"💡 {e.suggestion}")
                from unittest.mock import Mock
                if msg.__class__.__module__ == "PyQt6.QtWidgets" and not isinstance(msg.exec, Mock) and "pytest" in sys.modules:
                    pass
                else:
                    msg.exec()
            except Exception:
                from certus.utils.errors import show_error
                show_error(parent, "generic_error", details=e.message)
            return None
        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logger = logging.getLogger("CERTUS")
            logger.exception("safe_ui_action caught numerical fault in %s", func.__qualname__)
            if app_instance is None:
                return None
            try:
                from certus.ui.certus_ui import show_toast
                show_toast(parent, f"Error: {str(e)}", level="error", duration_ms=4000)
            except Exception:
                from certus.utils.errors import show_error
                show_error(parent, "generic_error", details=str(e))
            return None
        except Exception as e:
            logger = logging.getLogger("CERTUS")
            logger.exception("safe_ui_action caught unexpected exception in %s", func.__qualname__)
            if app_instance is None:
                return None
            try:
                from certus.ui.certus_ui import show_toast
                show_toast(parent, f"Critical: {str(e)}", level="error", duration_ms=5000)
            except Exception:
                from certus.utils.errors import show_error
                show_error(parent, "generic_error", details=str(e))
            return None

    return wrapper



class ProgressDialog(QWidget):
    """Progress dialog with cancellation support"""

    canceled = pyqtSignal()

    def __init__(self, title: str = "Processing...", parent=None) -> None:

        super().__init__(parent)

        self.setWindowTitle(title)

        self.setFixedSize(400, 150)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)

        set_certus_window_icon(self)

        self._setup_ui(title)

        self._is_canceled = False

    def _setup_ui(self, title: str) -> None:

        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(15)

        self.title_label = QLabel(title)

        self.title_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 14px; font-weight: 600;")

        layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(0, 100)

        self.progress_bar.setValue(0)

        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")

        self.status_label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 12px;")

        layout.addWidget(self.status_label)

        self.cancel_btn = QPushButton("Cancel")

        self.cancel_btn.setToolTip("Cancel the current operation.")

        self.cancel_btn.setStyleSheet(CertusTheme.get_button_style("danger"))

        self.cancel_btn.clicked.connect(self._on_cancel)

        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _on_cancel(self) -> None:

        self._is_canceled = True

        self.cancel_btn.setEnabled(False)

        self.cancel_btn.setText("Canceling...")

        self.canceled.emit()

    def is_canceled(self) -> bool:

        return self._is_canceled

    def finish(self) -> None:

        self.progress_bar.setValue(100)

        self.close()


class EnhancedProgressWidget(QWidget):
    """UX-8: Smart Telemetry & Progress Widget with Main and Sub-Progress."""

    canceled = pyqtSignal()

    def __init__(self, parent=None, main_label: str = "") -> None:
        super().__init__(parent)
        self._main_label = main_label
        self._start_time: float | None = None
        self._last_time: float | None = None
        self._last_evals: int = 0
        self._evals_per_sec: float = 0.0
        self._is_running = False
        self._is_canceled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Progress bars container
        bars_layout = QVBoxLayout()
        bars_layout.setSpacing(2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(CertusTheme.get_progress_bar_style())

        self.sub_progress_bar = QProgressBar()
        self.sub_progress_bar.setFixedWidth(200)
        self.sub_progress_bar.setFixedHeight(4)
        self.sub_progress_bar.setRange(0, 100)
        self.sub_progress_bar.setTextVisible(False)
        self.sub_progress_bar.setStyleSheet(
            CertusTheme.get_progress_bar_style().replace(CertusTheme.PRIMARY, CertusTheme.INFO_TEXT)
        )
        self.sub_progress_bar.setVisible(False)

        bars_layout.addWidget(self.progress_bar)
        bars_layout.addWidget(self.sub_progress_bar)

        self._anim_main = QPropertyAnimation(self.progress_bar, b"value")
        self._anim_main.setDuration(250)
        self._anim_main.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._anim_sub = QPropertyAnimation(self.sub_progress_bar, b"value")
        self._anim_sub.setDuration(150)

        layout.addLayout(bars_layout)

        # Label for phase and telemetry
        self.info_label = QLabel(self._main_label)
        self.info_label.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN}; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.info_label)

        # Cancel Button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Cancel the current operation.")
        self.cancel_btn.setStyleSheet(CertusTheme.get_button_style("danger"))
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)

    def _on_cancel(self) -> None:
        self._is_canceled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Canceling...")
        self.canceled.emit()

    def start(self) -> None:
        self._start_time = time.time()
        self._last_time = self._start_time
        self._last_evals = 0
        self._evals_per_sec = 0.0
        self._is_running = True
        self._is_canceled = False

        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(0)
        self.sub_progress_bar.setValue(0)
        self.sub_progress_bar.setVisible(False)
        self.info_label.setText("Starting...")

        if self.cancel_btn.isVisible():
            self.cancel_btn.setEnabled(True)
            self.cancel_btn.setText("Cancel")

    def enable_cancel(self, enabled: bool = True) -> None:
        self.cancel_btn.setVisible(bool(enabled))
        self.cancel_btn.setEnabled(bool(enabled) and self._is_running and (not self._is_canceled))
        if enabled and not self._is_canceled:
            self.cancel_btn.setText("Cancel")
        if not enabled:
            self._is_canceled = False

    def is_canceled(self) -> bool:
        return bool(self._is_canceled)

    def set_time_budget(self, budget_seconds: float) -> None:
        self._time_budget = budget_seconds

    def update(
        self,
        iteration: int,
        max_iter: int,
        evals: int = 0,
        phase: str = "",
        extra_info: str = "",
        sub_iteration: int = 0,
        max_sub_iter: int = 0,
        animate: bool = True,
    ) -> None:
        if not self._is_running or self._start_time is None:
            self.start()

        now = time.time()
        elapsed = now - self._start_time
        dt = now - (self._last_time or now)

        if dt > 0 and evals > 0:
            current_eps = (evals - self._last_evals) / dt
            if current_eps >= 0:
                self._evals_per_sec = 0.7 * self._evals_per_sec + 0.3 * current_eps

        self._last_time = now
        self._last_evals = evals

        # Main progress (weighted blend of iteration and evals when both are available)
        target_val = 0
        if max_iter > 0:
            target_val = int(100 * iteration / max_iter)
        if evals > 0 and getattr(self, "_last_evals", None) is not None:
            eval_ratio = min(1.0, evals / max(1, self._last_evals + max(1, evals)))
            target_val = int(100 * (0.7 * (target_val / 100.0) + 0.3 * eval_ratio))
        target_val = min(100, max(0, target_val))

        if self.progress_bar.value() != target_val:
            if animate:
                self._anim_main.stop()
                self._anim_main.setStartValue(self.progress_bar.value())
                self._anim_main.setEndValue(target_val)
                self._anim_main.start()
            else:
                self._anim_main.stop()
                self.progress_bar.setValue(target_val)

        # Sub progress
        if max_sub_iter > 0:
            self.sub_progress_bar.setVisible(True)
            target_sub = int(100 * sub_iteration / max_sub_iter)
            target_sub = min(100, max(0, target_sub))
            if self.sub_progress_bar.value() != target_sub:
                if animate:
                    self._anim_sub.stop()
                    self._anim_sub.setStartValue(self.sub_progress_bar.value())
                    self._anim_sub.setEndValue(target_sub)
                    self._anim_sub.start()
                else:
                    self._anim_sub.stop()
                    self.sub_progress_bar.setValue(target_sub)
        else:
            self.sub_progress_bar.setVisible(False)

        parts = []
        if phase:
            parts.append(phase)
        parts.append(self._format_time(elapsed))

        if evals > 0:
            eval_str = f"{evals:,} evals"
            if self._evals_per_sec > 10:
                eval_str += f" ({int(self._evals_per_sec):,} eq/s)"
            parts.append(eval_str)

        if extra_info:
            parts.append(extra_info)

        self.info_label.setText(" | ".join(parts))

    def stop(self, final_message: str = "Done") -> None:
        self._is_running = False
        if self.cancel_btn.isVisible():
            self.cancel_btn.setEnabled(False)
        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(100)
        self.sub_progress_bar.setVisible(False)
        if self._start_time:
            self.info_label.setText(f"{final_message} ({self._format_time(time.time() - self._start_time)})")
        else:
            self.info_label.setText(final_message)

    def reset(self) -> None:
        self._start_time = None
        self._last_time = None
        self._last_evals = 0
        self._evals_per_sec = 0.0
        self._is_running = False
        self._is_canceled = False
        self._anim_main.stop()
        self._anim_sub.stop()
        self.progress_bar.setValue(0)
        self.sub_progress_bar.setValue(0)
        self.sub_progress_bar.setVisible(False)
        self.info_label.setText("")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")

    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds < 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        if m < 60:
            return f"{m:02d}:{s:02d}"
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}"


# certus_plot re-exports (lazy: resolved via __getattr__ to break import cycle)


# QueueHandler and setup_gui_logger moved to certus_core.py (Single Source of Truth)


# Re-export for backward compatibility


from certus.core.certus_core import QueueHandler, setup_gui_logger


def confirm_stop_with_timeout(parent, timeout_sec=10) -> bool:
    """

    Shows a confirmation dialog with a countdown.

    Stops automatically after timeout if no action is taken.

    Returns:

        True: Stop confirmed (timeout or 'Stop Now' clicked).

        False: Stop cancelled (User clicked 'Cancel').

    """

    msg = QMessageBox(parent)

    msg.setWindowTitle("Stop Confirmation")

    msg.setIcon(QMessageBox.Icon.Question)

    # text will be updated by timer

    msg.setText(f"Stopping optimization in {timeout_sec} seconds...")

    msg.setInformativeText("Current best result will be saved.\nClick 'Cancel' to continuous optimization.")

    btn_stop = msg.addButton("Stop Now", QMessageBox.ButtonRole.AcceptRole)

    btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

    msg.setDefaultButton(btn_stop)

    remaining = timeout_sec

    def update_timer() -> None:

        nonlocal remaining

        remaining -= 1

        if remaining <= 0:
            msg.setText("Stopping...")

            btn_stop.animateClick()

        else:
            msg.setText(f"Stopping optimization in {remaining} seconds...")

    timer = QTimer(msg)

    timer.timeout.connect(update_timer)

    timer.start(1000)

    msg.exec()

    timer.stop()

    if msg.clickedButton() == btn_cancel:
        return False

    return True


def format_count_kmg(val) -> str:
    """Format a counter value as a short K/M/G string.

    Used by the stats display of METAL and STRAT applications
    (``update_stats_display``). Returns plain ``str(val)`` for values
    under 1000.
    """

    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if v >= 1e9:
        return f"{v / 1e9:.1f}G"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.1f}K"
    # Preserve integer rendering when possible
    return str(int(v)) if v == int(v) else f"{v:g}"


class StatsCounter:
    """Lightweight counter container shared across CERTUS apps.

    Centralises the boilerplate currently duplicated in
    :class:`MetalBaseApp`, :class:`CertusStratApp` and :class:`CertusDesignApp`
    around ``stat_counters = {...}`` + ``on_stats_update`` + ``update_stats_display``.

    The class is **opt-in**: existing apps continue to use plain dicts; new
    code (or progressive migrations) can wrap their counter dict in a
    ``StatsCounter`` to get a uniform mutation API. Display formatting stays
    in each app since label strings/emojis differ.

    Usage
    -----
    >>> counters = StatsCounter({"EVAL": 0, "BEST": 0, "MINIMA": 0})
    >>> counters.inc("EVAL")            # +1
    >>> counters.inc("EVAL", 4)         # +4
    >>> counters.set("MINIMA", 12)      # absolute
    >>> counters.reset()                # all back to 0
    >>> counters["EVAL"]
    5
    >>> counters.formatted("EVAL")
    '5'
    """

    __slots__ = ("_data",)

    def __init__(self, initial: dict[str, int] | None = None) -> None:
        self._data: dict[str, int] = dict(initial) if initial else {}

    # --- mutation -----------------------------------------------------------

    def inc(self, key: str, amount: int = 1) -> int:
        """Increment ``key`` by ``amount`` (creating the key if missing)."""

        self._data[key] = int(self._data.get(key, 0)) + int(amount)
        return self._data[key]

    def set(self, key: str, value: int) -> int:
        """Set ``key`` to ``value`` (overwriting existing counter)."""

        self._data[key] = int(value)
        return self._data[key]

    def reset(self, *keys: str) -> None:
        """Reset all counters (default) or a subset of ``keys`` to 0."""

        if not keys:
            for k in list(self._data):
                self._data[k] = 0
            return
        for k in keys:
            if k in self._data:
                self._data[k] = 0

    # --- read ---------------------------------------------------------------

    def get(self, key: str, default: int = 0) -> int:
        return int(self._data.get(key, default))

    def formatted(self, key: str, default: int = 0) -> str:
        """Return ``format_count_kmg`` rendering of the counter at ``key``."""

        return format_count_kmg(self.get(key, default))

    def as_dict(self) -> dict[str, int]:
        return dict(self._data)

    # --- dunder -------------------------------------------------------------

    def __getitem__(self, key: str) -> int:
        return int(self._data[key])

    def __setitem__(self, key: str, value: int) -> None:
        self._data[key] = int(value)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __iter__(self) -> Any:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"StatsCounter({self._data!r})"


def stop_worker_and_thread(
    worker,
    thread,
    timeout_ms: int = 3000,
    logger=None,
    label: str = "Worker thread",
) -> bool:
    """Request a worker to stop and join its QThread with a timeout.

    Safe against ``RuntimeError`` (deleted C++ object). If the thread does
    not finish within ``timeout_ms``, a critical log entry is emitted and
    ``False`` is returned. ``terminate()`` is never called (unsafe).

    Parameters
    ----------
    worker : object or None
        Worker exposing a ``stop()`` method. Ignored if ``None``.
    thread : QThread or None
        Thread running the worker. Ignored if ``None``.
    timeout_ms : int
        Maximum time to wait for the thread to quit, in milliseconds.
    logger : logging.Logger or None
        Logger used for timeout reporting. Falls back to the root logger.
    label : str
        Human-readable label used in the timeout log message.

    Returns
    -------
    bool
        ``True`` if the thread stopped cleanly (or was already stopped),
        ``False`` if the timeout was hit.
    """

    try:
        if worker is not None and hasattr(worker, "stop"):
            worker.stop()
    except (RuntimeError, AttributeError):
        logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    if thread is None:
        return True

    try:
        if not thread.isRunning():
            return True
        thread.quit()
        if thread.wait(timeout_ms):
            return True
    except RuntimeError:
        # QThread C++ object already deleted
        return True

    msg = f"{label} did not stop within {timeout_ms / 1000:.1f}s - skipping terminate() to avoid unsafe thread kill."
    if logger is not None:
        logger.critical(msg)
    else:
        logging.critical(msg)
    return False


def confirm_and_stop(
    parent,
    worker,
    thread,
    *,
    timeout_sec: int = 10,
    timeout_ms: int = 3000,
    logger=None,
    label: str = "Worker thread",
) -> bool:
    """Show the standard stop-confirmation dialog and shut a worker/thread down.

    Combines :func:`confirm_stop_with_timeout` (modal countdown dialog) with
    :func:`stop_worker_and_thread` (request-stop + bounded ``QThread.wait``)
    so that ``stop_optimization`` implementations across CERTUS apps can
    delegate to a single helper instead of copy-pasting the boilerplate.

    Parameters
    ----------
    parent : QWidget or None
        Parent for the confirmation dialog.
    worker : object or None
        Worker exposing a ``stop()`` method. Ignored if ``None``.
    thread : QThread or None
        Thread running the worker. Ignored if ``None``.
    timeout_sec : int
        Auto-confirm delay for the dialog, in seconds.
    timeout_ms : int
        Maximum time to wait for the thread to quit, in milliseconds.
    logger : logging.Logger or None
        Logger forwarded to :func:`stop_worker_and_thread` for timeout reports.
    label : str
        Human-readable label used in timeout log messages.

    Returns
    -------
    bool
        ``True`` if the user confirmed and the thread stopped cleanly (or was
        already stopped). ``False`` if the user cancelled, or if the thread
        failed to stop within ``timeout_ms``.
    """

    if not confirm_stop_with_timeout(parent, timeout_sec=timeout_sec):
        return False
    return stop_worker_and_thread(
        worker,
        thread,
        timeout_ms=timeout_ms,
        logger=logger,
        label=label,
    )



class CertusAppLogsMixin:
    """Provides common UI log operations."""
    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard and update status label if possible."""
        copy_app_logs_to_clipboard(self)
        if hasattr(self, 'lbl_status') and hasattr(self.lbl_status, 'setText'):
            self.lbl_status.setText("Logs copied to clipboard!")

    def on_toggle_details(self, checked: bool) -> None:
        """Show/Hide log panel dynamically."""
        if hasattr(self, 'log_text'):
            self.log_text.setVisible(checked)
        if hasattr(self, 'toggle_details_btn'):
            self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")
        if hasattr(self, 'right_splitter'):
            if checked:
                self.right_splitter.setSizes([600, 200])
            else:
                self.right_splitter.setSizes([1000, 0])


def copy_app_logs_to_clipboard(app) -> bool:
    """Copy the application's logs to the system clipboard.

    Prefers ``app._log_panel.copy_to_clipboard()`` (shared CertusLogPanel).
    Falls back to ``app.log_text.toPlainText()`` if present.

    Returns True if something was copied, False otherwise. Callers are
    expected to update their own status label (message wording varies by app).
    """

    panel = getattr(app, "_log_panel", None)
    if panel is not None:
        try:
            panel.copy_to_clipboard()
            return True
        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    log_text = getattr(app, "log_text", None)
    if log_text is not None:
        try:
            text = log_text.toPlainText()
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)
                return True
        except (AttributeError, RuntimeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    return False


# certus_export re-exports (lazy: resolved via __getattr__ to break import cycle)

from certus.ui.certus_plot import (
    sanitize_xy_for_plot,
    plot_widget_plot_finite,
    CertusScientificPlot,
    wrap_scientific_plot_with_toolbar,
    clone_plot_widget,
    ScientificPlotRefined,
)


# theme_restart logic removed (Dead Code)


# =============================================================================


# CERTUS BASE APPLICATION


# =============================================================================


class CertusBaseApp(QMainWindow):
    sig_numba_ready = pyqtSignal()
    sig_numba_error = pyqtSignal()
    """

    Base class for all CERTUS application windows.

    Provides common functionality:

    - Window icon and title setup

    - Centered window positioning

    - Log queue and logger setup

    - Timer-based log processing

    - Theme application

    - Numba warmup pattern

    - Config save/load pattern

    - Detached plot window management

    """

    # Subclasses should override these

    APP_NAME = "CERTUS"

    APP_TITLE = "Calculated Error Reduction Through Unbiased Simulation"

    DEFAULT_WIDTH = 1200

    DEFAULT_HEIGHT = 800

    MIN_WIDTH = 800

    MIN_HEIGHT = 600

    LOG_TIMER_MS = 200

    def __init__(self, parent=None, runtime: CertusRuntime | None = None) -> None:

        super().__init__(parent)

        # Runtime container is injectable to avoid hidden globals.
        self.runtime: CertusRuntime = runtime if runtime is not None else build_runtime()

        # Window setup

        set_certus_window_icon(self)

        # Use APP_TITLE from subclass if defined, otherwise use base APP_TITLE

        app_title = getattr(self.__class__, "APP_TITLE", self.APP_TITLE)

        self.setWindowTitle(f"{self.APP_NAME}  {app_title}")

        # Center on screen

        screen = QApplication.primaryScreen().availableGeometry()

        x = (screen.width() - self.DEFAULT_WIDTH) // 2

        y = (screen.height() - self.DEFAULT_HEIGHT) // 2

        self.setGeometry(x, y, self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # Common state

        self.log_queue: queue.Queue = queue.Queue()

        self.logger: logging.Logger | None = None

        self.widgets: dict[str, Any] = {}

        self.stat_counters: dict[str, int] = {"MS": 0, "MCS": 0, "SP": 0}

        self.undo_stack: deque = deque(maxlen=getattr(CFG, "UNDO_LIMIT", 50))

        self.detached_plot_windows: dict[str, "DetachedPlotWindow"] = {}

        # Worker management

        self._worker: QThread | None = None

        self._active_workers: list[QThread] = []

        # Numba ready flag

        self.numba_ready = False

        # Log timer (started in _finalize_init)

        self._log_timer_id: int | None = None

        # Busy management

        self._busy_count = 0

        self._is_busy = False

        # U3: command palette registry (lazy: only built on first open)
        self._commands: list[Any] | None = None
        self._command_palette_shortcuts: list[Any] = []

    def _finalize_init(self) -> None:
        """

        Call this at the END of subclass __init__ after _build_ui().

        Sets up timers and triggers warmup.

        """

        # Restore persisted window geometry + splitter
        self._qs_restore()
        self._restore_ui_zoom()

        # Start log processing timer

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        # U3: install Ctrl+K / Ctrl+Shift+P for the command palette.
        for seq in ("Ctrl+K", "Ctrl+Shift+P"):
            try:
                sc = QShortcut(QKeySequence(seq), self)
                sc.setContext(Qt.ShortcutContext.WindowShortcut)
                sc.activated.connect(self.open_command_palette)
                self._command_palette_shortcuts.append(sc)
            except (TypeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # U4: install F1 / Shift+? to open the keyboard-shortcuts overlay.
        for seq in ("F1", "Shift+?"):
            try:
                sc = QShortcut(QKeySequence(seq), self)
                sc.setContext(Qt.ShortcutContext.WindowShortcut)
                sc.activated.connect(self.open_shortcuts_overlay)
                self._command_palette_shortcuts.append(sc)
            except (TypeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # U5: install global zoom shortcuts for a more premium 2026 layout.
        try:
            self._zoom_factor = getattr(self, "_zoom_factor", 1.0)
            self._zoom_shortcuts = install_standard_shortcuts(
                self,
                zoom_in=self.zoom_in_ui,
                zoom_out=self.zoom_out_ui,
                reset_zoom=self.reset_ui_zoom,
            )
        except (TypeError, RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # U5b: reflect the current zoom level in the status bar for instant feedback.
        try:
            self._ensure_zoom_status_widget()
            self._update_zoom_status()
        except (TypeError, RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # P2.3 - Install the standard Help menu on every subclass (idempotent).
        try:
            mb = self.menuBar()
            if mb is not None:
                already_present = any((a.text() or "").replace("&", "").strip().lower() == "help" for a in mb.actions())
                if not already_present:
                    self.install_help_menu()
        except (RuntimeError, AttributeError, TypeError):  # pragma: no cover - defensive
            pass

        # P1.3 - Auto-wire empty-state overlays on well-known table widgets.
        self._auto_install_empty_states()

        # P4 - Fill missing accessibility metadata on input widgets.
        self._apply_accessibility_defaults()

        # P2.2 - Trigger the onboarding tour on first launch (non-blocking).
        # The tour skips itself silently if the user already finished/skipped
        # it or if no step targets are resolvable. 600 ms gives the window
        # time to be fully laid out before the spotlight is positioned.
        QTimer.singleShot(600, self._maybe_run_first_time_tour)

        # Trigger Numba warmup after a short delay

        QTimer.singleShot(100, self._warmup_numba)

    def _maybe_run_first_time_tour(self) -> None:
        """Best-effort: run the onboarding tour the first time only."""
        try:
            self.run_onboarding_tour(force=False)
        except (RuntimeError, AttributeError, TypeError):  # pragma: no cover - defensive
            pass

    def zoom_in_ui(self) -> None:
        """Increase the global UI zoom in a smooth, bounded way."""
        self._apply_ui_zoom(min(getattr(self, "_zoom_factor", 1.0) + 0.05, 1.30))

    def zoom_out_ui(self) -> None:
        """Decrease the global UI zoom in a smooth, bounded way."""
        self._apply_ui_zoom(max(getattr(self, "_zoom_factor", 1.0) - 0.05, 0.85))

    def reset_ui_zoom(self) -> None:
        """Restore the default CERTUS scale."""
        self._apply_ui_zoom(1.0)

    def _zoom_feedback_text(self, factor: float) -> str:
        percent = int(round(factor * 100))
        return f"Zoom {percent}%"

    def _ensure_zoom_status_widget(self) -> None:
        """Create a persistent zoom indicator in the status bar."""
        if getattr(self, "_zoom_status_label", None) is not None:
            return
        from PyQt6.QtWidgets import QLabel

        label = QLabel(self)
        label.setObjectName("certusZoomStatus")
        label.setMinimumWidth(88)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-weight: 600; padding: 0 8px;")
        self.status_bar.addPermanentWidget(label)
        self._zoom_status_label = label

    def _update_zoom_status(self, factor: float | None = None, announce: bool = True) -> None:
        label = getattr(self, "_zoom_status_label", None)
        if label is not None:
            current = getattr(self, "_zoom_factor", 1.0) if factor is None else factor
            label.setText(self._zoom_feedback_text(current))
        if announce and factor is not None:
            try:
                show_toast(self, self._zoom_feedback_text(factor), "info", duration_ms=1200)
            except (RuntimeError, AttributeError, TypeError, ValueError):
                pass

    def _store_ui_zoom(self) -> None:
        try:
            qs = QSettings("CERTUS", self.APP_NAME)
            qs.setValue(self._qs_key("uiZoom"), float(getattr(self, "_zoom_factor", 1.0)))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def _restore_ui_zoom(self) -> None:
        try:
            qs = QSettings("CERTUS", self.APP_NAME)
            value = qs.value(self._qs_key("uiZoom"), 1.0)
            self._zoom_factor = max(0.85, min(1.30, float(value)))
            base_pt = getattr(CertusTheme, "FONT_SIZE_BASE", 10)
            app = QApplication.instance()
            if app is not None:
                app.setFont(QFont("Segoe UI", max(9, round(base_pt * self._zoom_factor))))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self._zoom_factor = 1.0
        self._update_zoom_status()

    def _apply_ui_zoom(self, factor: float) -> None:
        """Apply a restrained, modern zoom level to the app and descendants."""
        previous = getattr(self, "_zoom_factor", 1.0)
        factor = max(0.85, min(1.30, float(factor)))
        self._zoom_factor = factor
        base_pt = getattr(CertusTheme, "FONT_SIZE_BASE", 10)
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont("Segoe UI", max(9, round(base_pt * factor))))
        self.setStyleSheet(get_standard_stylesheet())
        self.setMinimumSize(int(self.MIN_WIDTH * factor), int(self.MIN_HEIGHT * factor))
        self._store_ui_zoom()
        try:
            scale = factor / previous if previous else 1.0
            self.resize(max(self.minimumWidth(), int(self.width() * scale)), max(self.minimumHeight(), int(self.height() * scale)))
        except (AttributeError, RuntimeError, TypeError, ZeroDivisionError):
            pass
        if hasattr(self, "statusBar") and callable(getattr(self, "statusBar")):
            try:
                self.statusBar().setStyleSheet(CertusTheme.get_status_bar_stylesheet())
            except (AttributeError, RuntimeError, TypeError):
                pass
        self._update_zoom_status(factor, announce=True)

    # =========================================================================
    # U3 — Command palette
    # =========================================================================

    def register_command(self, action: Any) -> None:
        """Register a :class:`CommandAction` in this window's palette.

        Re-registering the same ``id`` replaces the previous entry.
        """
        if self._commands is None:
            self._commands = list(self._default_commands())
        self._commands = [a for a in self._commands if getattr(a, "id", None) != action.id]
        self._commands.append(action)

    def _default_commands(self) -> list[Any]:
        """Baseline commands available in every CERTUS app.

        Subclasses override to add app-specific entries (typically by
        calling ``super()._default_commands() + [...]``).
        """
        from certus.utils.certus_command_palette import CommandAction

        actions: list[Any] = []
        if hasattr(self, "save_config") and callable(getattr(self, "save_config")):
            actions.append(
                CommandAction(
                    id="file.save_config",
                    title="Save configuration…",
                    subtitle="Export current settings to a JSON file",
                    shortcut="Ctrl+S",
                    category="File",
                    icon_name="save",
                    keywords=("export", "json", "write"),
                    callback=lambda: self.save_config(),
                )
            )
        if hasattr(self, "load_config") and callable(getattr(self, "load_config")):
            actions.append(
                CommandAction(
                    id="file.load_config",
                    title="Load configuration…",
                    subtitle="Restore settings from a JSON file",
                    shortcut="Ctrl+O",
                    category="File",
                    icon_name="folder-open",
                    keywords=("import", "json", "open"),
                    callback=lambda: self.load_config(),
                )
            )
            # U5 — dynamic "Open recent" entry (only surfaces if non-empty at build time).
            try:
                recents = self.list_recent_configs(limit=1) if hasattr(self, "list_recent_configs") else []
            except (RuntimeError, AttributeError, TypeError, ValueError):
                recents = []
            if recents:
                actions.append(
                    CommandAction(
                        id="file.open_recent",
                        title="Open recent configuration…",
                        subtitle="Pick from the most recently used config files",
                        category="File",
                        icon_name="file",
                        keywords=("mru", "recent", "history"),
                        callback=lambda: self.open_recent_configs(),
                    )
                )
        if hasattr(self, "_copy_app_logs_to_clipboard"):
            actions.append(
                CommandAction(
                    id="view.copy_logs",
                    title="Copy application logs to clipboard",
                    category="View",
                    icon_name="copy",
                    keywords=("debug", "clipboard", "logs"),
                    callback=lambda: self._copy_app_logs_to_clipboard(),
                )
            )
        actions.append(
            CommandAction(
                id="view.toggle_theme",
                title="Toggle light / dark theme",
                category="View",
                icon_name="moon",
                keywords=("dark", "light", "appearance"),
                callback=lambda: self._toggle_theme(),
            )
        )
        actions.append(
            CommandAction(
                id="view.zoom_in",
                title="Zoom in",
                subtitle="Increase the interface scale for readability",
                shortcut="Ctrl+Plus",
                category="View",
                icon_name="search-plus",
                keywords=("zoom", "scale", "larger", "readability"),
                callback=lambda: self.zoom_in_ui(),
            )
        )
        actions.append(
            CommandAction(
                id="view.zoom_out",
                title="Zoom out",
                subtitle="Reduce the interface scale for denser layouts",
                shortcut="Ctrl+Minus",
                category="View",
                icon_name="search-minus",
                keywords=("zoom", "scale", "smaller", "density"),
                callback=lambda: self.zoom_out_ui(),
            )
        )
        actions.append(
            CommandAction(
                id="view.zoom_reset",
                title="Reset zoom",
                subtitle="Return the interface to the default size",
                shortcut="Ctrl+0",
                category="View",
                icon_name="search",
                keywords=("zoom", "reset", "default", "scale"),
                callback=lambda: self.reset_ui_zoom(),
            )
        )
        actions.append(
            CommandAction(
                id="help.shortcuts",
                title="Show keyboard shortcuts",
                subtitle="List every registered shortcut in this window",
                shortcut="F1",
                category="Help",
                icon_name="keyboard",
                keywords=("help", "kbd", "hotkey", "cheatsheet"),
                callback=lambda: self.open_shortcuts_overlay(),
            )
        )
        actions.append(
            CommandAction(
                id="app.quit",
                title="Close this window",
                category="Application",
                icon_name="x",
                shortcut="Ctrl+W",
                callback=lambda: self.close(),
            )
        )
        # P0.2 - auto-discover common app actions from method names.
        auto = getattr(self, "_auto_discovered_commands", None)
        if callable(auto):
            actions.extend(auto())
        return actions

    def _auto_discovered_commands(self) -> list[Any]:
        """Introspect common method names to surface app-specific commands.

        Looks up a curated list of verb→(method name) bindings on the
        current instance and returns a :class:`CommandAction` for each
        method that actually exists. This gives every app a reasonably
        complete palette without any per-app refactor (P0.2).

        Apps wanting richer commands should still override
        :meth:`_default_commands` and call ``super()`` + custom entries.
        """
        try:
            from certus.utils.certus_command_palette import CommandAction
        except ImportError:
            return []

        # (command id, title, subtitle, method name, category, icon, shortcut, keywords)
        catalogue = [
            (
                "run.optimize",
                "Run optimization",
                "Start the main optimisation workflow",
                ("run_optimization", "run_optim", "optimize", "start_optimization"),
                "Run",
                "play",
                "Ctrl+R",
                ("run", "optimize", "solve", "fit", "start"),
            ),
            (
                "run.stop",
                "Stop optimization",
                "Gracefully interrupt the running solver",
                ("stop_optimization", "stop", "cancel_run"),
                "Run",
                "square",
                "Esc",
                ("stop", "cancel", "abort", "halt"),
            ),
            (
                "run.analyze",
                "Run analysis",
                "Start the spectral / beam analysis",
                ("run_analysis", "start_analysis", "analyze", "run_beam"),
                "Run",
                "activity",
                None,
                ("analyze", "beam", "measure", "spectrum"),
            ),
            (
                "run.smart_init",
                "Smart init",
                "Launch the Smart-Init preparation dialog",
                ("smart_init", "auto_init", "open_smart_init"),
                "Run",
                "sparkles",
                None,
                ("init", "bootstrap", "smart"),
            ),
            (
                "edit.add_layer",
                "Add layer",
                "Append a new layer to the stack",
                ("add_layer",),
                "Edit",
                "plus",
                None,
                ("add", "layer", "insert", "stack"),
            ),
            (
                "edit.add_target",
                "Add target",
                "Append a new spectral target",
                ("add_target",),
                "Edit",
                "plus",
                None,
                ("add", "target", "spec"),
            ),
            (
                "edit.smart_cleanup",
                "Smart cleanup",
                "Remove low-impact layers and re-optimise",
                ("smart_cleanup",),
                "Edit",
                "trash-2",
                None,
                ("clean", "prune", "optimize", "simplify"),
            ),
            (
                "edit.reset_all",
                "Reset",
                "Reset the current session (destructive)",
                ("reset_all", "clear_stack", "reset"),
                "Edit",
                "refresh-ccw",
                None,
                ("reset", "clear", "start over"),
            ),
            (
                "file.export_excel",
                "Export to Excel…",
                "Save current data to a styled .xlsx workbook",
                ("export_excel",),
                "File",
                "table",
                None,
                ("excel", "xlsx", "export", "report"),
            ),
            (
                "file.export_csv",
                "Export to CSV…",
                "Save current data to a CSV file",
                ("export_csv",),
                "File",
                "file-text",
                None,
                ("csv", "export", "data"),
            ),
            (
                "file.export_pdf",
                "Export to PDF…",
                "Save a premium PDF report",
                ("export_report_pdf", "export_pdf", "export_report"),
                "File",
                "file",
                None,
                ("pdf", "report", "premium", "export"),
            ),
            (
                "file.export_report_excel",
                "Export premium Excel report…",
                "Save a fully-branded .xlsx report (cover + tables + charts)",
                ("export_report_excel",),
                "File",
                "table",
                None,
                ("excel", "premium", "report", "branded", "xlsx"),
            ),
            (
                "help.documentation",
                "Open documentation",
                "Show the in-app HTML documentation",
                ("open_help", "open_documentation"),
                "Help",
                "book-open",
                None,
                ("docs", "manual", "guide", "help"),
            ),
        ]

        out: list[Any] = []
        for cmd_id, title, subtitle, method_names, category, icon, shortcut, keywords in catalogue:
            bound = None
            for name in method_names:
                if callable(getattr(self, name, None)):
                    bound = getattr(self, name)
                    break
            if bound is None:
                continue
            out.append(
                CommandAction(
                    id=cmd_id,
                    title=title,
                    subtitle=subtitle,
                    shortcut=shortcut,
                    category=category,
                    icon_name=icon,
                    keywords=tuple(keywords),
                    callback=(lambda fn=bound: fn()),
                )
            )
        return out

    def _toggle_theme(self) -> None:
        """Flip between light and dark themes (best-effort)."""
        try:
            mode = load_theme_config()
            new_mode = "dark" if mode == "light" else "light"
            save_theme_config(new_mode)
            CertusTheme.configure(new_mode)
            app = QApplication.instance()
            if app is not None:
                CertusTheme.apply_to_app(app, new_mode == "dark")
            update_global_plot_config(new_mode == "dark")
            self._apply_theme()
            try:
                from certus.ui.certus_icons import clear_icon_cache

                clear_icon_cache()
            except (ImportError, AttributeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Theme toggle failed")

    def open_command_palette(self) -> None:
        """Show the ``Ctrl+K`` command palette for this window."""
        try:
            from certus.utils.certus_command_palette import open_command_palette

            if self._commands is None:
                self._commands = list(self._default_commands())
            open_command_palette(self, list(self._commands))
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Command palette failed to open")

    def open_shortcuts_overlay(self) -> None:
        """Show the ``F1`` keyboard-shortcuts cheatsheet for this window."""
        try:
            from certus.ui.certus_shortcuts_overlay import open_shortcuts_overlay

            open_shortcuts_overlay(self)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Shortcuts overlay failed to open")

    # =========================================================================
    # P2.3 - Standard Help menu (Shortcuts, Command palette, Docs, About)
    # =========================================================================

    def install_help_menu(self, *, app_label: str | None = None) -> None:
        """Install a standard ``&Help`` menu on this window.

        Opt-in helper; subclasses must call this explicitly (typically at
        the end of ``__init__``). The menu offers access to the keyboard
        shortcuts overlay, the command palette, the online documentation
        and an About dialog. All entries are no-ops if the underlying
        module is unavailable.
        """
        try:
            mb = self.menuBar()
            if mb is None:
                return
            help_menu = mb.addMenu("&Help")

            act_palette = help_menu.addAction("Command palette…")
            act_palette.setShortcut("Ctrl+K")
            act_palette.triggered.connect(self.open_command_palette)
            act_palette.setToolTip("Search commands, navigate features and trigger actions instantly.")

            act_shortcuts = help_menu.addAction("Keyboard shortcuts…")
            act_shortcuts.setShortcut("F1")
            act_shortcuts.triggered.connect(self.open_shortcuts_overlay)
            act_shortcuts.setToolTip("See all shortcuts available in this window.")

            act_zoom_in = help_menu.addAction("Zoom in")
            act_zoom_in.setShortcut("Ctrl+Plus")
            act_zoom_in.triggered.connect(self.zoom_in_ui)
            act_zoom_in.setToolTip("Increase interface scale for readability.")

            act_zoom_out = help_menu.addAction("Zoom out")
            act_zoom_out.setShortcut("Ctrl+Minus")
            act_zoom_out.triggered.connect(self.zoom_out_ui)
            act_zoom_out.setToolTip("Decrease interface scale for denser workflows.")

            act_zoom_reset = help_menu.addAction("Reset zoom")
            act_zoom_reset.setShortcut("Ctrl+0")
            act_zoom_reset.triggered.connect(self.reset_ui_zoom)
            act_zoom_reset.setToolTip("Return the interface to its default scale.")

            help_menu.addSeparator()

            if hasattr(self, "open_help"):
                act_docs = help_menu.addAction("Open documentation…")
                act_docs.triggered.connect(self.open_help)

            help_menu.addSeparator()

            # P2.2 - onboarding entries
            act_tour = help_menu.addAction("Start guided tour")
            act_tour.triggered.connect(functools.partial(self.run_onboarding_tour, force=True))

            act_reset_tour = help_menu.addAction("Reset onboarding state")
            act_reset_tour.triggered.connect(self.reset_onboarding_tour)

            help_menu.addSeparator()

            act_about = help_menu.addAction("About CERTUS…")
            act_about.triggered.connect(functools.partial(self._show_default_about_dialog, app_label))
        except (RuntimeError, AttributeError, TypeError, ValueError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Help menu install failed")

    def _show_default_about_dialog(self, app_label: str | None = None) -> None:
        """Minimal About dialog with the app name, version and key bindings."""
        try:
            from PyQt6.QtWidgets import QMessageBox

            label = app_label or getattr(self, "APP_TITLE", None) or getattr(self, "APP_NAME", "CERTUS")
            QMessageBox.about(
                self,
                f"About {label}",
                f"<b>{label}</b><br>CERTUS 2026 - Optical Suite<br><br>"
                "<code>Ctrl+K</code> &middot; Command palette<br>"
                "<code>F1</code> &middot; Keyboard shortcuts<br>"
                "<code>Ctrl+S</code> / <code>Ctrl+O</code> &middot; Save / Load config<br>",
            )
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("About dialog failed to open")

    # =========================================================================
    # P2.2 - Onboarding tour helpers
    # =========================================================================

    def run_onboarding_tour(self, *, force: bool = False) -> str:
        """Run the onboarding tour registered for this app (best-effort)."""
        try:
            from certus.ui.certus_tours_catalog import run_app_onboarding

            return run_app_onboarding(self, force=force)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            if self.logger:
                self.logger.exception("Onboarding tour failed to start")
            return "empty"

    def reset_onboarding_tour(self) -> None:
        """Forget the "already shown" flag so the tour runs again next time."""
        try:
            from certus.ui.certus_onboarding import reset_onboarding

            reset_onboarding(getattr(self, "APP_NAME", "CERTUS"))
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            if self.logger:
                self.logger.exception("Onboarding reset failed")

    # =========================================================================
    # P4 - Accessibility defaults (auto-wired at _finalize_init time)
    # =========================================================================

    # Subclasses may override to supply explicit {objectName: label} entries.
    _A11Y_LABEL_MAP: dict[str, str] = {}

    def _apply_accessibility_defaults(self) -> int:
        """Fill missing accessible names / focus policies on input widgets.

        Delegates to :func:`certus_a11y.apply_accessibility_defaults`. Returns
        the number of widgets touched (useful for tests). Silently ignored
        if the module is unavailable.
        """
        try:
            from certus.ui.certus_a11y import apply_accessibility_defaults
        except ImportError:
            return 0
        try:
            return apply_accessibility_defaults(self, label_map=self._A11Y_LABEL_MAP)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            if self.logger:
                self.logger.exception("Accessibility defaults application failed")
            return 0

    # =========================================================================
    # P5 - Destructive-action confirmations (uniform modal)
    # =========================================================================

    def confirm_destructive(
        self,
        title: str,
        message: str,
        *,
        detail: str | None = None,
        confirm_label: str = "Continue",
        cancel_label: str = "Cancel",
        default_cancel: bool = True,
    ) -> bool:
        """Show a modal confirmation dialog with consistent styling.

        Returns ``True`` when the user accepts the action, ``False`` on
        cancel or dialog failure. Use for **irreversible** actions only
        (overwrite, clear, kill worker, delete).
        """
        try:
            from PyQt6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(title)
            msg.setText(message)
            if detail:
                msg.setInformativeText(detail)
            yes = msg.addButton(confirm_label, QMessageBox.ButtonRole.AcceptRole)
            no = msg.addButton(cancel_label, QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(no if default_cancel else yes)
            msg.exec()
            return msg.clickedButton() is yes
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Destructive confirmation dialog failed")
            return False

    # =========================================================================
    # P3 - Premium report helpers (Excel + PDF via certus_reports)
    # =========================================================================

    def _default_report_context(self) -> Any:
        """Return a :class:`certus_reports.ReportContext` prefilled from the app."""
        try:
            from certus.utils.certus_reports import ReportContext
        except ImportError:
            return None
        app_label = getattr(self, "APP_TITLE", None) or getattr(self, "APP_NAME", "CERTUS")
        return ReportContext(
            title=f"{app_label} report",
            subtitle="Automatic export",
            app_name=getattr(self, "APP_NAME", "CERTUS"),
            author="",
        )

    def _default_run_manifest(self) -> None:
        """Best-effort run manifest for exports (non-blocking, UI-safe)."""
        return None

    def set_validation_status(self, status: str) -> None:
        """Store a normalized validation status for manifest export."""
        try:
            from certus.core.certus_metrology import ValidationStatus

            self.validation_status = ValidationStatus(str(status)).value
        except (RuntimeError, AttributeError, TypeError, ValueError):
            self.validation_status = str(status)

    def add_validation_warning(self, warning: str) -> None:
        """Append a warning to the manifest warning list."""
        msg = str(warning).strip()
        if not msg:
            return
        cur = getattr(self, "validation_warnings", None)
        if not isinstance(cur, list):
            cur = []
        cur.append(msg)
        self.validation_warnings = cur
        app_id = str(
            getattr(self, "MODULE_ID", None) or getattr(self, "APP_NAME", None) or getattr(self, "APP_TITLE", "CERTUS")
        )
        app_version = str(
            getattr(self, "MODULE_VERSION", None)
            or getattr(self, "APP_VERSION", None)
            or getattr(self, "CERTUS_VERSION", "unknown")
        )
        seed = getattr(self, "run_seed", None)
        if seed is None:
            seed = getattr(self, "random_seed", None)
        if seed is None and hasattr(self, "sp_corr_seed"):
            try:
                seed = int(self.sp_corr_seed.value())
            except (RuntimeError, AttributeError, TypeError, ValueError):
                seed = None
        warnings_raw = getattr(self, "validation_warnings", None)
        warnings = [str(w) for w in warnings_raw] if isinstance(warnings_raw, (list, tuple)) else []
        status_raw = str(getattr(self, "validation_status", "OK") or "OK")
        try:
            from certus.core.certus_metrology import RunContext, RunManifest, ValidationStatus
        except ImportError:
            return None
        try:
            status = ValidationStatus(status_raw)
        except ValueError:
            status = ValidationStatus.OK
        input_paths = []
        src = getattr(self, "filename", None)
        if isinstance(src, str) and src:
            input_paths.append(src)
        try:
            ctx = RunContext.create(
                app_id=app_id,
                app_version=app_version,
                seed=int(seed) if seed is not None else None,
                input_paths=input_paths,
                warnings=warnings,
                status=status,
            )
            return RunManifest(run_context=ctx)
        except (RuntimeError, AttributeError, TypeError, ValueError):
            return None

    def export_premium_excel(self, sections, output_path: str | None = None, *, ctx=None) -> str | None:
        """Render a styled ``.xlsx`` report via :mod:`certus_reports`.

        Parameters
        ----------
        sections:
            Iterable of :class:`certus_reports.Section`.
        output_path:
            Destination file. When ``None``, asks the user via the standard
            CERTUS save dialog.
        ctx:
            Optional :class:`ReportContext` override (defaults to the app's).

        Returns the resolved absolute path on success, or ``None`` on cancel /
        failure. Errors are surfaced in the log + as an error toast.
        """
        try:
            from certus.utils.certus_reports import build_excel_report
        except ImportError:
            self.log("Excel export unavailable (missing dependency).", "ERROR")
            return None
        path = output_path
        if not path:
            path = certus_get_save_file_name(self, "Export premium Excel report", "Excel (*.xlsx)")
            if not path:
                return None
        try:
            report_ctx = ctx or self._default_report_context()
            if report_ctx is not None and getattr(report_ctx, "run_manifest", None) is None:
                report_ctx.run_manifest = self._default_run_manifest()
            out = build_excel_report(report_ctx, sections, path)
            self.log(f"Excel report saved: {out}", "SUCCESS")
            return out
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError) as e:  # pragma: no cover - defensive
            self.log(f"Excel export failed: {e}", "ERROR")
            if self.logger:
                self.logger.exception("Excel export failed")
            return None

    def export_premium_pdf(self, sections, output_path: str | None = None, *, ctx=None) -> str | None:
        """Render a styled ``.pdf`` report via :mod:`certus_reports`.

        Symmetric to :meth:`export_premium_excel`. Uses ``matplotlib`` under
        the hood (already a project dependency) so no extra install is needed.
        """
        try:
            from certus.utils.certus_reports import build_pdf_report
        except ImportError:
            self.log("PDF export unavailable (missing dependency).", "ERROR")
            return None
        path = output_path
        if not path:
            path = certus_get_save_file_name(self, "Export premium PDF report", "PDF (*.pdf)")
            if not path:
                return None
        try:
            report_ctx = ctx or self._default_report_context()
            if report_ctx is not None and getattr(report_ctx, "run_manifest", None) is None:
                report_ctx.run_manifest = self._default_run_manifest()
            out = build_pdf_report(report_ctx, sections, path)
            self.log(f"PDF report saved: {out}", "SUCCESS")
            return out
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError) as e:  # pragma: no cover - defensive
            self.log(f"PDF export failed: {e}", "ERROR")
            if self.logger:
                self.logger.exception("PDF export failed")
            return None

    # Subclasses override this to return their app-specific report sections.
    def _build_report_sections(self) -> list:
        """Return the :class:`Section` list for this app (empty by default)."""
        return []

    def export_report_excel(self) -> str | None:
        """Convenience: build default sections + save Excel in one call."""
        return self.export_premium_excel(self._build_report_sections())

    def export_report_pdf(self) -> str | None:
        """Convenience: build default sections + save PDF in one call."""
        return self.export_premium_pdf(self._build_report_sections())

    # =========================================================================
    # P1.1 - Skeleton overlay convenience (any long-running op can use these)
    # =========================================================================
    # =========================================================================
    # P1.3 - Empty states for well-known tables (auto-wired)
    # =========================================================================

    # (attribute name on self -> (icon, title, description, optional CTA))
    _EMPTY_STATE_HINTS: dict[str, tuple[str, str, str, str | None]] = {
        "front_table": (
            "layers",
            "No layers yet",
            "Add a layer from the toolbar above, or load a configuration.",
            "Add layer",
        ),
        "back_table": (
            "layers",
            "No back-side layers",
            "Enable back-side coating to edit the stack on this side.",
            None,
        ),
        "target_table": (
            "target",
            "No spectral targets",
            "Click 'Add target' to define the first wavelength window.",
            "Add target",
        ),
        "spectra_table": ("line-chart", "No spectra loaded", "Drag a CSV file here or use File → Load spectra.", None),
        "measurement_table": (
            "activity",
            "No measurements yet",
            "Import measured data or switch to the Sample demos.",
            None,
        ),
        "results_table": (
            "check-circle",
            "No results yet",
            "Run the optimisation from the command palette or toolbar.",
            None,
        ),
    }

    def _auto_install_empty_states(self) -> None:
        """Install :class:`CertusEmptyState` overlays on well-known tables.

        Scans the instance for attributes named in :attr:`_EMPTY_STATE_HINTS`
        and wires an empty-state overlay when the attribute is a
        :class:`QAbstractItemView`-compatible widget. No-op if the empty
        state module is missing or the attribute does not exist.

        Call sites (e.g. ``add_layer``, ``add_target``) are wired via the
        CTA callback where available.
        """
        try:
            from certus.ui.certus_empty_state import attach_empty_state_to
        except ImportError:
            return

        for attr, (icon, title, desc, cta_label) in self._EMPTY_STATE_HINTS.items():
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            # Must be a view with a model; QTableWidget / QListWidget qualify.
            if not hasattr(widget, "model"):
                continue
            # Resolve CTA callback lazily from a sensible default method name.
            on_action = None
            if cta_label:
                cb = getattr(self, "add_layer" if "layer" in cta_label.lower() else "add_target", None)
                if callable(cb):
                    on_action = cb
                else:
                    cta_label = None  # hide CTA button if no target method
            try:
                attach_empty_state_to(
                    widget,
                    icon_name=icon,
                    title=title,
                    description=desc,
                    action_label=cta_label,
                    on_action=on_action,
                )
            except (RuntimeError, AttributeError, TypeError, ValueError):
                if self.logger:
                    self.logger.exception("Failed to attach empty state to %s", attr)

    # =========================================================================
    # U5 — Recent files
    # =========================================================================

    def _record_recent_config(self, filename: str) -> None:
        """Append ``filename`` to the config MRU list (best-effort)."""
        if not filename:
            return
        try:
            from certus.ui.certus_recent import RecentCategories, record_recent

            record_recent(RecentCategories.CONFIG, filename)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            pass

    def list_recent_configs(self, limit: int = 8) -> list[str]:
        """Return up to ``limit`` most-recent config paths (existing files)."""
        try:
            from certus.ui.certus_recent import RecentCategories, list_recent

            return list_recent(RecentCategories.CONFIG, limit=limit)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            return []

    def open_recent_configs(self) -> None:
        """Show a small picker listing the most recent configs."""
        paths = self.list_recent_configs(limit=12)
        if not paths:
            if self.logger:
                self.logger.info("No recent configuration files.")
            return
        try:
            from PyQt6.QtWidgets import QInputDialog
            from certus.ui.certus_recent import short_label

            items = [short_label(p, max_length=80) for p in paths]
            label_to_path = dict(zip(items, paths))
            choice, ok = QInputDialog.getItem(
                self,
                "Open recent configuration",
                "Pick a recent file:",
                items,
                0,
                False,
            )
            if ok and choice and choice in label_to_path:
                self.load_config(label_to_path[choice])
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception("Failed to open recent-configs picker")

    def _qs_key(self, suffix: str) -> str:
        return f"window/{self.APP_NAME}/{suffix}"

    def _qs_restore(self) -> None:
        qs = QSettings("CERTUS", self.APP_NAME)
        geom = qs.value(self._qs_key("geometry"))
        if geom is not None:
            self.restoreGeometry(geom)
        state = qs.value(self._qs_key("windowState"))
        if state is not None:
            self.restoreState(state)
        splitter_state = qs.value(self._qs_key("mainSplitter"))
        if splitter_state is not None:
            sp = getattr(self, "main_split", None)
            if sp is not None:
                sp.restoreState(splitter_state)

    def _qs_save(self) -> None:
        qs = QSettings("CERTUS", self.APP_NAME)
        qs.setValue(self._qs_key("geometry"), self.saveGeometry())
        qs.setValue(self._qs_key("windowState"), self.saveState())
        sp = getattr(self, "main_split", None)
        if sp is not None:
            qs.setValue(self._qs_key("mainSplitter"), sp.saveState())

    def _setup_logger(self, name: str) -> Any:
        """

        Setup GUI logger with the given name.

        Args:

            name: Logger name (typically self.APP_NAME)

        Returns:

            Configured logger instance

        """

        from certus.core.certus_core import setup_gui_logger

        self.logger = setup_gui_logger(self.log_queue, name)
        self.logger.info("[%s] Show Details logger attached", name)

        return self.logger

    def _warmup_numba(self) -> None:
        """

        Override in subclass to perform JIT precompilation.

        Call self._on_numba_ready() when done.

        """

        self._on_numba_ready()

    def _on_numba_ready(self) -> None:
        """Called when Numba warmup completes."""

        self.numba_ready = True

        if self.logger:
            self.logger.info(" Numba JIT compilation completed")

    def _on_warmup_done(self) -> None:
        """Slot when ``WarmupWorker.finished`` fires (CERTUS_DESIGN / CERTUS_RE)."""

        self._warmup_done = True

        self._spectrum_eval_jit_wait_logged = False

        sl = getattr(self, "status_label", None)

        if sl is not None:
            sl.setText("Ready")

        logging.info("[WARMUP] JIT warmup finished; spectrum eval may proceed.")

        try:
            show_toast(self, "System ready. JIT Warmup complete.", "success")
        except Exception:
            pass


    def _apply_certus_compact_theme(self, plots: list) -> None:
        """Shared theme application for compact-UI modules (DESIGN, RE).

        Applies the standard compact-layout CSS overrides and triggers a
        progress-widget polish + deferred spectrum redraw if applicable.
        """
        apply_certus_theme(
            self,
            plots=plots,
            overrides=f"""
                #LeftPanel {{
                    background-color: {CertusTheme.SURFACE};
                    border-right: 1px solid {CertusTheme.BORDER};
                }}
                QWidget {{ font-size: 11px; }}
                QGroupBox {{
                    font-weight: 700;
                    font-size: 11px;
                    margin-top: 6px;
                    border: 1px solid {CertusTheme.BORDER};
                    border-radius: 14px;
                    background-color: {CertusTheme.SURFACE};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 8px;
                    margin-left: 8px;
                    color: {CertusTheme.PRIMARY};
                }}
                QLabel#HeaderLabel {{ font-size: 14px; font-weight: 800; color: {CertusTheme.TEXT_MAIN}; }}
                QPushButton {{ font-size: 11px; padding: 5px 10px; border-radius: 10px; }}
                QComboBox {{ font-size: 11px; padding: 3px 8px; border-radius: 10px; }}
                QDoubleSpinBox, QSpinBox {{ font-size: 11px; padding: 3px 8px; border-radius: 10px; }}
            """,
        )
        if hasattr(self, "progress_widget"):
            self.progress_widget.style().unpolish(self.progress_widget)
            self.progress_widget.style().polish(self.progress_widget)
        if hasattr(self, "spectrum_plot"):
            QTimer.singleShot(50, lambda: self._schedule_eval(instant=True))

    def timerEvent(self, event) -> None:
        """Process log queue on timer."""

        if event.timerId() == self._log_timer_id:
            self._process_log_queue()

    def _process_log_queue(self) -> None:
        """Process pending log messages."""

        log_widget = self._get_log_widget()

        if log_widget and self.log_queue:
            process_log_queue_standard(self.log_queue, log_widget)


    # --- Config Save/Load ---

    def _get_config_file_filter(self) -> str:

        return "JSON Files (*.json);;All Files (*)"

    def _get_default_config_name(self) -> str:

        return f"{self.APP_NAME.lower()}_config.json"

    def _collect_config(self) -> dict[str, Any]:
        """

        Override in subclass to collect configuration from widgets.

        Returns a dict to be serialized to JSON.

        """

        return {}

    def _apply_config(self, config: dict[str, Any]) -> None:
        """

        Override in subclass to apply loaded configuration to widgets.

        """

        pass

    def _pre_save_smart_cleanup(self) -> None:
        """Override in subclass for pre-save cleanup (e.g. layer pruning in DESIGN)."""

        pass

    def _post_save_config(self, filename: str) -> None:
        """Override in subclass for post-save UI side-effects (status bar, popup, ...)."""

        pass

    def _post_load_config(self, filename: str, config: dict[str, Any]) -> None:
        """Override in subclass for post-load UI side-effects (status bar, popup, ...)."""

        pass

    @safe_ui_action
    def save_config(self) -> None:
        """Save current configuration to JSON file."""

        import json

        default_path = str(Path(get_certus_last_dir() or ".") / self._get_default_config_name())

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration",
            default_path,
            self._get_config_file_filter(),
        )

        if filename:
            set_certus_last_dir(filename)

            try:
                self._pre_save_smart_cleanup()

                config = self._collect_config()

                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                if self.logger:
                    self.logger.info(f"Configuration saved: {filename}")

                self._record_recent_config(filename)

                self._post_save_config(filename)

            except Exception as e:
                from certus.utils.errors import ConfigurationCorruptionError
                msg = f"Failed to save configuration: {e}"
                if self.logger:
                    self.logger.error(msg)
                raise ConfigurationCorruptionError(
                    msg,
                    details=str(e),
                    suggestion="Please verify if the destination path is writable and disk space is sufficient."
                ) from e

    @safe_ui_action
    def load_config(self, filename: str = None) -> None:
        """Load configuration from JSON file."""

        import json

        if not filename:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", get_certus_last_dir(), self._get_config_file_filter()
            )

        if filename:
            set_certus_last_dir(filename)

            try:
                with open(filename, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if not isinstance(config, dict):
                    raise ValueError("Configuration JSON must be an object/dictionary.")
                app_mod = str(getattr(self.__class__, "__module__", "")).upper()
                if "INDEX_SPLINE" in app_mod:
                    try:
                        validated = IndexSplineConfigDTO.model_validate(config)
                        config = validated.model_dump(mode="python", exclude_none=False)
                    except ValidationError as e:
                        msg = f"Invalid INDEX_SPLINE configuration: {e}"
                        if self.logger:
                            self.logger.error(msg)
                        from certus.utils.errors import ConfigurationCorruptionError
                        raise ConfigurationCorruptionError(
                            msg,
                            details=str(e),
                            suggestion="Ensure the configuration file matches the INDEX_SPLINE schema."
                        ) from e

                self._apply_config(config)

                if self.logger:
                    self.logger.info(f"Configuration loaded: {filename}")

                self._record_recent_config(filename)

                self._post_load_config(filename, config)

            except Exception as e:
                from certus.utils.errors import ConfigurationCorruptionError
                if isinstance(e, ConfigurationCorruptionError):
                    raise
                msg = f"Failed to load configuration: {e}"
                if self.logger:
                    self.logger.error(msg)
                raise ConfigurationCorruptionError(
                    msg,
                    details=str(e),
                    suggestion="Ensure the configuration file exists, is valid JSON, and has correct file permissions."
                ) from e

    # --- Worker Management ---

    def _on_worker_finished(self, worker: QThread) -> None:
        """Called when a worker finishes."""

        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def _stop_all_workers(self) -> None:
        """Stop all active workers."""

        for worker in self._active_workers:
            if hasattr(worker, "stop"):
                worker.stop()

            if hasattr(worker, "requestInterruption"):
                worker.requestInterruption()

    # --- Detached Plot Windows ---

    def open_detached_certus_plot(self, source_plot: QWidget, *, title: str | None = None) -> None:
        """Clones the plot into a maximized window (accessible everywhere for CERTUS apps)."""

        key = f"certus_detach_{id(source_plot)}"

        if key in self.detached_plot_windows:
            w = self.detached_plot_windows[key]

            w.raise_()

            w.activateWindow()

            return

        try:
            clone = clone_plot_widget(source_plot, title_override=title)

            if clone is None:
                return

            disp = (title or "").strip() or "CERTUS Chart"

            win = DetachedPlotWindow(clone, parent=self, title=disp)

            win.closed_signal.connect(functools.partial(self.detached_plot_windows.pop, key, None))

            self.detached_plot_windows[key] = win

            win.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            log = getattr(self, "logger", None)

            if log is not None:
                log.warning("open_detached_certus_plot: %s", e)

            else:
                logging.warning("open_detached_certus_plot: %s", e)

    # --- Cleanup ---

    # --- Shared helpers migrated from CERTUS_RE / CERTUS_DESIGN ---

    def _auto_scale_spectrum_y(self, Ts: np.ndarray = None, include_targets: bool = True) -> None:
        """

        Automatically adjusts X and Y axes to include

        spectrum and active targets.

        """

        x_min, x_max = None, None

        y_min, y_max = None, None

        # 1. Analyze calculated data (Spectrum)

        if self.last_result:
            res_vis = self.last_result.get("vis", {})

            wls_data = res_vis.get("l", np.array([]))

            if len(wls_data) > 0:
                x_min, x_max = np.min(wls_data), np.max(wls_data)

                # In oblique mode, analyze all R and T spectra

                if self.last_result.get("oblique_mode", False):
                    spectra_vis = self.last_result.get("spectra_vis", {})

                    all_values = []

                    for spec_data in spectra_vis.values():
                        all_values.extend(spec_data.get("R", []))

                        all_values.extend(spec_data.get("T", []))

                    if all_values:
                        y_min, y_max = np.min(all_values), np.max(all_values)

                elif Ts is not None:
                    y_min, y_max = np.min(Ts), np.max(Ts)

        # 2. Systematic analysis of active targets

        if include_targets:
            if self.oblique_mode:
                active_tgts = [t for t in self._get_oblique_tgts() if t.valid()]

                for t in active_tgts:
                    x_min = min(x_min, t.lmin) if x_min is not None else t.lmin

                    x_max = max(x_max, t.lmax) if x_max is not None else t.lmax

                    target_y_min = min(t.tmin, t.tmax)

                    target_y_max = max(t.tmin, t.tmax)

                    y_min = min(y_min, target_y_min) if y_min is not None else target_y_min

                    y_max = max(y_max, target_y_max) if y_max is not None else target_y_max

            else:
                active_tgts = [t for t in self._get_tgts() if t.valid()]

                for t in active_tgts:
                    x_min = min(x_min, t.lmin) if x_min is not None else t.lmin

                    x_max = max(x_max, t.lmax) if x_max is not None else t.lmax

                    target_y_min = min(t.tmin, t.tmax)

                    target_y_max = max(t.tmin, t.tmax)

                    y_min = min(y_min, target_y_min) if y_min is not None else target_y_min

                    y_max = max(y_max, target_y_max) if y_max is not None else target_y_max

        # 3. Apply scales with 20% margins relative to extremities

        if x_min is not None and x_max is not None:
            # 20% margin relative to each extremity

            x_margin_min = x_min * 0.20

            x_margin_max = x_max * 0.20

            x_display_min = max(200.0, x_min - x_margin_min)  # Reasonable limit: 200 nm

            x_display_max = x_max + x_margin_max  # No hard cap  supports IR

            self.spectrum_plot.setXRange(x_display_min, x_display_max, 0)

        else:
            # No data, use reasonable default range

            self.spectrum_plot.setXRange(200, 3000, 0)

        if y_min is not None and y_max is not None:
            y_margin = (y_max - y_min) * 0.1

            # Limit Y between -0.02 and 1.05 for physical consistency (0-100%)

            self.spectrum_plot.setYRange(max(-0.02, y_min - y_margin), min(1.05, y_max + y_margin), 0)

        else:
            self.spectrum_plot.setYRange(0.0, 1.0, 0)

    def _calculate_wls_max_with_margin(self, active_targets) -> Any:
        """Calculates lambda max with 20% margin relative to max extremity"""

        if not active_targets:
            return 2000.0

        t_lmax = max(t.lmax for t in active_targets)

        # 20% margin relative to max extremity

        margin = t_lmax * 0.10

        return t_lmax + margin  # No hard cap  supports IR

    def _calculate_wls_min_with_margin(self, active_targets) -> Any:
        """Calculates lambda min with 20% margin relative to min extremity"""

        if not active_targets:
            return 380.0

        t_lmin = min(t.lmin for t in active_targets)

        # 20% margin relative to min extremity

        margin = t_lmin * 0.20

        return max(200.0, t_lmin - margin)  # Reasonable limit: 200 nm

    def _clean_live_curves(self) -> None:
        """Cleans live curves"""

        # Clean curves in normal mode

        if hasattr(self, "_live_curve") and self._live_curve is not None:
            try:
                self.spectrum_plot.removeItem(self._live_curve)

            except (AttributeError, RuntimeError) as e:
                logging.debug(f"Could not remove live curve: {e}")

            self._live_curve = None

        # Clean curves in oblique mode

        if hasattr(self, "_live_curves"):
            for _, curve in list(self._live_curves.items()):
                try:
                    self.spectrum_plot.removeItem(curve)

                except (AttributeError, RuntimeError) as e:
                    logging.debug(f"Could not remove oblique curve: {e}")

            self._live_curves = {}

        if hasattr(self, "_live_points") and self._live_points is not None:
            try:
                self.spectrum_plot.removeItem(self._live_points)

            except (AttributeError, RuntimeError) as e:
                logging.debug(f"Could not remove live points: {e}")

            self._live_points = None

    def _create_spin(
        self,
        val: float,
        dec: int = 4,
        step: float = 0.01,
        minv: float = 0.0,
        maxv: float = 100.0,
    ) -> QDoubleSpinBox:
        """Creates a QDoubleSpinBox with the given parameters."""

        sb = QDoubleSpinBox()

        sb.setRange(minv, maxv)

        sb.setDecimals(dec)

        sb.setSingleStep(step)

        sb.setValue(val)

        return sb

    def _add_front_row(self, mat: str, qwot: float, var: bool, del_checked: bool = False) -> None:
        """Adds row to front layer table"""

        row = self.front_table.rowCount()

        self.front_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._merge_adjacent_layers)

        self.front_table.setCellWidget(row, 0, cb)

        sb = self._create_spin(qwot, dec=6)

        def _on_front_qwot_changed(*_args) -> None:
            self._schedule_eval()

        sb.valueChanged.connect(_on_front_qwot_changed)

        self._on_qwot_changed_connection(sb)

        self.front_table.setCellWidget(row, 1, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(row, 2, it)

        # Optimization Toggle (Var)

        chk = QCheckBox()

        chk.setToolTip("Toggle optimization for this layer.")

        chk.setChecked(var)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(row, 3, cw)

        # Delete Toggle (Del)

        del_chk = QCheckBox()

        del_chk.setToolTip("Mark this layer for removal.")

        del_chk.setChecked(del_checked)

        del_cw = QWidget()

        del_cl = QHBoxLayout(del_cw)

        del_cl.addWidget(del_chk)

        del_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        del_cl.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(row, 4, del_cw)

        self._update_layer_count()

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox) -> None:
        """Hook for extra connections on QWOT spinbox change."""

        pass

    def add_front_layer(self) -> None:
        """Adds a front layer with default H/L sequence"""

        if self.front_table.rowCount() >= CFG.MAX_LAYERS:
            return

        mat = "H"

        if self.front_table.rowCount() > 0:
            prev = self._safe_get_combo_text(self.front_table.rowCount() - 1, 0)

            if prev:
                mat = "L" if prev == "H" else "H"

        self._add_front_row(mat, 1.0, True)

        self._on_layer_added()

        self._schedule_eval()

    def _on_layer_added(self) -> None:
        """Hook for post-layer-addition actions."""

        pass

    def del_front_layer(self) -> None:
        """Removes selected front layers and heals the structure."""

        rows_to_remove = []

        # Check checkboxes first

        for row in range(self.front_table.rowCount()):
            del_cell = self.front_table.cellWidget(row, 4)

            if del_cell:
                del_chk = del_cell.findChild(QCheckBox)

                if del_chk and del_chk.isChecked():
                    rows_to_remove.append(row)

        # Fallback to current row if no checkboxes

        if not rows_to_remove:
            r = self.front_table.currentRow()

            if r < 0 and self.front_table.rowCount() > 0:
                r = self.front_table.rowCount() - 1

            if r >= 0:
                rows_to_remove = [r]

        if rows_to_remove:
            self._save_undo_state()

            for r in sorted(rows_to_remove, reverse=True):
                self.front_table.removeRow(r)

            self._update_layer_count()

            self._on_layer_deleted()

            self._schedule_eval()

    def _on_layer_deleted(self) -> None:
        """Hook for post-layer-deletion actions."""

        pass

    def _get_front_stack(self) -> list[Layer]:
        """Retrieves front stack"""

        try:
            stack = []

            for r in range(self.front_table.rowCount()):
                mat = self._safe_get_combo_text(r, 0)

                if not mat:
                    continue

                qw = self.front_table.cellWidget(r, 1).value()

                var = self.front_table.cellWidget(r, 3).findChild(QCheckBox).isChecked()

                stack.append(Layer(mat, qw, var))

            return stack

        except (AttributeError, ValueError, IndexError) as e:
            logging.debug(f"Could not get front stack: {e}")

            return []

    def _get_log_widget(self) -> Any:
        """Override base class: log widget is self.log_text (set by _build_log_container)."""

        return getattr(self, "log_text", None)

    def _get_plot_targets(self, plot_name: str, primary_widget) -> list:
        """Returns list of widgets to update (primary + detached)"""

        targets = [primary_widget]

        if hasattr(self, "detached_plot_windows") and plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]

            # Ensure window is visible and has the widget reference (added in certus_ui step)

            if win.isVisible() and hasattr(win, "plot_widget"):
                targets.append(win.plot_widget)

        return targets

    def _get_tgts(self) -> list[Target]:
        """Retrieves spectral targets (normal mode)"""

        if self.oblique_mode:
            return []  # In oblique mode, use _get_oblique_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                on = chk.isChecked() if chk else False

                vals = []

                for c in range(1, 6):
                    w = self.target_table.cellWidget(r, c)

                    vals.append(w.value() if w else 0.0)

                targets.append(Target(vals[0], vals[1], vals[2], vals[3], vals[4], on))

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug(f"Could not get target row {r}: {e}")

        return targets

    def _is_valid_rmse_value(self, rmse) -> bool:
        """True if RMSE is finite and non-negative."""

        return rmse is not None and np.isfinite(rmse) and rmse >= 0.0

    def _merge_adjacent_layers(self, table: QTableWidget = None) -> None:
        """Merges adjacent layers of same material"""

        if table is None:
            table = getattr(self, "front_table", None)
        if table is None:
            return

        merged = False
        passes = 0

        while passes < 10:
            passes += 1
            found = False
            i = 1

            while i < table.rowCount():
                m_curr = self._safe_get_combo_text(i, 0, table)
                m_prev = self._safe_get_combo_text(i - 1, 0, table)
                if m_curr is None:
                    item_curr = table.item(i, 0)
                    m_curr = item_curr.text() if item_curr else None
                if m_prev is None:
                    item_prev = table.item(i - 1, 0)
                    m_prev = item_prev.text() if item_prev else None

                if m_curr and m_prev and m_curr == m_prev:
                    try:
                        widget_curr = table.cellWidget(i, 1)
                        if widget_curr and hasattr(widget_curr, "value"):
                            q_curr = widget_curr.value()
                        else:
                            item_curr = table.item(i, 1)
                            q_curr = float(item_curr.text()) if item_curr else 0.0

                        widget_prev = table.cellWidget(i - 1, 1)
                        if widget_prev and hasattr(widget_prev, "setValue"):
                            widget_prev.blockSignals(True)
                            widget_prev.setValue(widget_prev.value() + q_curr)
                            widget_prev.blockSignals(False)
                        else:
                            item_prev = table.item(i - 1, 1)
                            if item_prev:
                                val_prev = float(item_prev.text()) + q_curr
                                item_prev.setText(f"{val_prev:.4f}")

                        table.removeRow(i)
                        merged = True
                        found = True
                        self.log(f"Merged adjacent layers ({m_curr})", "INFO")
                        continue

                    except NUMERICAL_FAULT_EXCEPTIONS as e:
                        (self.logger.error(f"Merge error: {e}") if hasattr(self, "logger") and self.logger else None)
                    except (ValueError, AttributeError) as e:
                        logging.debug(f"Merge values error: {e}")

                i += 1

            if not found:
                break

        if hasattr(self, "front_table") and table == self.front_table:
            self._update_layer_count()
            if merged:
                self._schedule_eval()
        elif hasattr(self, "structure_changed"):
            self.structure_changed.emit()
        elif hasattr(self, "stack_panel") and hasattr(self.stack_panel, "structure_changed"):
            self.stack_panel.structure_changed.emit()

    def smart_cleanup(self, table: QTableWidget = None, update_target: bool = True) -> int:
        """
        Smart cleanup: merges identical adjacent materials and removes
        very thin layers (< 1.0 nm) which are likely artifacts.
        """
        if table is None:
            table = getattr(self, "front_table", None)
        if table is None:
            return 0

        removed_count = 0
        changed = False

        # Step 1: Remove very thin layers dynamically based on RMSE
        current_rmse = getattr(self, "_workflow_best_rmse", 1.0)
        multiplier = getattr(self, "_cleanup_threshold_multiplier", 150.0)
        threshold = max(0.05, min(1.0, current_rmse * multiplier))  # Adaptive threshold

        rows_to_remove = []
        for r in range(table.rowCount() - 1, -1, -1):
            thick_item = table.item(r, 2)
            if thick_item:
                try:
                    thickness = float(thick_item.text())
                    if thickness < threshold:
                        rows_to_remove.append(r)
                except ValueError:
                    pass

        if rows_to_remove:
            self.log(f"Smart cleanup: removing {len(rows_to_remove)} layers < {threshold:.2f} nm (adaptive)", "INFO")
            for r in rows_to_remove:
                table.removeRow(r)
            removed_count += len(rows_to_remove)
            changed = True

        # Step 2: Merge identical adjacent materials
        pre_merge_count = table.rowCount()
        self._merge_adjacent_layers(table)
        post_merge_count = table.rowCount()

        merge_diff = pre_merge_count - post_merge_count
        if merge_diff > 0:
            removed_count += merge_diff
            changed = True
            self.log(f"Smart cleanup: merged {merge_diff} adjacent layers", "INFO")

        if changed:
            if hasattr(self, "_update_layer_count") and table == getattr(self, "front_table", None):
                self._update_layer_count()
            elif hasattr(self, "structure_changed"):
                self.structure_changed.emit()
            elif hasattr(self, "stack_panel") and hasattr(self.stack_panel, "structure_changed"):
                self.stack_panel.structure_changed.emit()

        return removed_count

    def _monotonic_visual_mode_enabled(self) -> bool:
        """Enable strict non-regression of visualized spectrum during/after workflow."""

        wf_best = getattr(self, "_workflow_best_rmse", float("inf"))

        return np.isfinite(wf_best) and wf_best < float("inf")

    def _rebuild_target_scatter(self, wls: np.ndarray, oblique_mode: bool = False) -> None:
        """Rebuilds target points on plot"""

        if self.target_scatter:
            self.spectrum_plot.removeItem(self.target_scatter)

            self.target_scatter = None

        if len(wls) == 0:
            return

        scatter_pts = []

        if oblique_mode:
            # Oblique Mode: display targets by type (R or T)

            # Use same colors as spectra for consistency

            oblique_tgts = self._get_oblique_tgts()

            color_idx = 0

            for tgt in oblique_tgts:
                if not tgt.valid():
                    continue

                # Color: R in red, T in blue

                tgt_id = (tgt.angle, tgt.pol, tgt.target_type, tgt.lmin, tgt.lmax)

                if hasattr(self, "_oblique_spectrum_colors") and tgt_id in self._oblique_spectrum_colors:
                    color = self._oblique_spectrum_colors[tgt_id]

                else:
                    color = "#dc2626" if tgt.target_type == "R" else "#2563eb"

                brush = pg.mkBrush(*pg.colorTuple(pg.mkColor(color))[:3], 76)  # 30% opacity

                # RE narrow-band targets (tmin==tmax): ONE dot at center wavelength

                if abs(tgt.tmax - tgt.tmin) < 1e-9:
                    wl_center = (tgt.lmin + tgt.lmax) / 2.0

                    scatter_pts.append({"pos": (wl_center, tgt.tmin), "size": 8, "pen": pg.mkPen(None), "brush": brush})

                else:
                    # Wide-band targets: plot on display grid

                    tolerance = 1e-6

                    mask = (wls >= (tgt.lmin - tolerance)) & (wls <= (tgt.lmax + tolerance))

                    if not np.any(mask):
                        continue

                    x_pts = np.clip(wls[mask], tgt.lmin, tgt.lmax)

                    slope = (tgt.tmax - tgt.tmin) / max(tgt.lmax - tgt.lmin, 1e-9)

                    y_pts = tgt.tmin + slope * (x_pts - tgt.lmin)

                    for x, y in zip(x_pts, y_pts):
                        if tgt.lmin <= x <= tgt.lmax:
                            scatter_pts.append({"pos": (x, y), "size": 8, "pen": pg.mkPen(None), "brush": brush})

                color_idx += 1

        else:
            # Normal Mode: display T targets

            for t in self._get_tgts():
                if not t.valid():
                    continue

                # Strictly filter wavelengths in target range

                # Use numerical tolerance to avoid precision issues

                tolerance = 1e-6

                mask = (wls >= (t.lmin - tolerance)) & (wls <= (t.lmax + tolerance))

                if not np.any(mask):
                    continue

                x_pts = wls[mask]

                # Ensure points are within [lmin, lmax] range

                x_pts = np.clip(x_pts, t.lmin, t.lmax)

                slope = (t.tmax - t.tmin) / max(t.lmax - t.lmin, 1e-9)

                y_pts = t.tmin + slope * (x_pts - t.lmin)

                for x, y in zip(x_pts, y_pts):
                    # Final check: do not plot points outside range

                    if t.lmin <= x <= t.lmax:
                        scatter_pts.append(
                            {
                                "pos": (x, y),
                                "size": 8,
                                "pen": pg.mkPen(None),
                                "brush": pg.mkBrush(
                                    *pg.colorTuple(pg.mkColor(CertusTheme.ACCENT))[:3], 76
                                ),  # 30% opacity
                            }
                        )

        if scatter_pts:
            self.target_scatter = pg.ScatterPlotItem()

            self.target_scatter.addPoints(scatter_pts)

            self.spectrum_plot.addItem(self.target_scatter)

    def _safe_get_combo_text(self, row: int, col: int, table: QTableWidget = None) -> str | None:
        """Safely gets combo text"""

        if table is None:
            table = self.front_table

        try:
            widget = table.cellWidget(row, col)

            if widget is None:
                return None

            return widget.currentText()

        except (AttributeError, RuntimeError) as e:
            logging.debug(f"Could not get combo value: {e}")

            return None

    def _schedule_eval(self, instant: bool = False) -> None:
        """Schedules evaluation"""

        logging.debug(f"[EVAL] _schedule_eval called (instant={instant})")

        self._update_thickness_display()

        if self.eval_timer is not None:
            self.eval_timer.stop()

        self.eval_timer = QTimer(self)

        self.eval_timer.setSingleShot(True)

        self.eval_timer.timeout.connect(self.run_eval)

        self.eval_timer.start(0 if instant else 400)

        logging.debug(f"[EVAL] Timer started with delay={0 if instant else 400}ms")

    def _store_best_eval_snapshot(self, data: dict) -> None:
        """Store immutable snapshot of the best evaluated spectrum/result."""

        rmse = data.get("rmse")

        if not self._is_valid_rmse_value(rmse):
            return

        if rmse <= self._best_eval_rmse + 1e-12:
            self._best_eval_rmse = float(rmse)

            self._best_eval_result = copy.deepcopy(data)

    def _save_undo_state(self, force: bool = False) -> None:
        """Saves current state for undo"""

        if not hasattr(self, "undo_stack") or not hasattr(self, "undo_btn"):
            return

        stack = self._get_front_stack()

        if stack or force:
            self.undo_stack.append(stack)

            self.undo_btn.setEnabled(True)

            self.log(f"State saved (Undo stack: {len(self.undo_stack)})", "INFO")

    def _undo(self) -> None:
        """Undoes last action"""

        if not hasattr(self, "undo_stack") or not self.undo_stack:
            return

        self.log("Undo...", "INFO")

        state = self.undo_stack.pop()

        self.front_table.blockSignals(True)

        self.front_table.setRowCount(0)

        for l in state:
            # mat, qwot, var, del_checked

            self._add_front_row(l.mat, l.qwot, l.var)

        self.front_table.blockSignals(False)

        self._update_layer_count()

        if not self.undo_stack:
            self.undo_btn.setEnabled(False)

        self._trigger_post_undo_action()

    def _trigger_post_undo_action(self) -> None:
        """Hook for post-undo actions (like re-running optimization or evaluation)."""

        pass

    def _update_layer_count(self) -> None:
        """Updates layer count display"""

        count = self.front_table.rowCount()

        self.layer_count_label.setText(f"{count} layer{'s' if count != 1 else ''}")

    def _build_ui(self) -> None:
        """Constructs main horizontal layout with splitter: [Left Panel] | [Right Panel]"""

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_split = main_splitter

        self.setCentralWidget(main_splitter)

        # Left Panel (Module-specific)

        self.left_panel = self._build_left_panel()

        main_splitter.addWidget(self.left_panel)

        # Right Panel (Module-specific)

        self.right_panel = self._build_right_panel()

        main_splitter.addWidget(self.right_panel)

        # Initial sizes (Hook)

        main_splitter.setSizes(self._get_default_splitter_sizes())

        # Status bar

        self._build_status_bar()

        # Initial theme application (Hook)

        self._apply_theme()

    def _get_default_splitter_sizes(self) -> list[int]:
        """Hook for initial splitter sizes."""

        return [400, 1000]

    def _build_status_bar(self) -> None:
        """Constructs status bar"""

        self.status_bar = self.statusBar()

        self.status_bar.showMessage("Ready")

        self._zoom_status_label = QLabel("Zoom 100%")
        self._zoom_status_label.setObjectName("certusZoomStatus")
        self._zoom_status_label.setToolTip("Current interface scale")
        self.status_bar.addPermanentWidget(self._zoom_status_label)
        self._update_zoom_status(1.0, announce=False)

    def _apply_theme(self) -> None:
        """Hook for theme application."""

        pass

    def detach_current_plot(self) -> None:
        """Detaches current plot to separate window"""

        current_widget = self.plot_tabs.currentWidget()

        if current_widget is None:
            return

        info = self._get_plot_info(current_widget)

        if info is None:
            return

        plot_name, plot_title = info

        if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
            self.detached_plot_windows[plot_name].raise_()

            return

        try:
            detached_plot_copy = clone_plot_widget(current_widget)

            if detached_plot_copy is None:
                raise ValueError("Could not clone plot")

            if plot_name == "convergence":
                detached_plot_copy.setLogMode(y=True)

                detached_plot_copy.showGrid(x=True, y=True)

            detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

            detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = detached_window

            detached_window.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Plot detach failed: {e}", "ERROR")

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """Hook to identify plot name and title from widget."""

        return None

    def _update_thickness_display(self) -> None:
        """Updates physics thicknesses (nm) from current QWOT and l0"""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        stack = self._get_front_stack()

        if stack and mats:
            ep = init_thickness(stack, l0, mats)

            if ep is not None:
                for r, d in enumerate(ep):
                    it = self.front_table.item(r, 2)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_current = ep

                self._on_front_thickness_updated()

        stack_b = self._get_back_stack()

        if stack_b and mats:
            ep_b = init_thickness(stack_b, l0, mats)

            if ep_b is not None:
                for r, d in enumerate(ep_b):
                    it = self.back_table.item(r, 2)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_back_current = ep_b

    def _on_front_thickness_updated(self) -> None:
        """Hook for post-thickness-update actions."""

        pass

    def _get_back_stack(self) -> list[Layer]:
        """Hook for back-face stack. RE usually doesn't have it."""

        return []

    def _update_qwot_from_ep(self, ep) -> None:
        """Update front-table QWOT from thicknesses (nm)."""

        self.front_table.blockSignals(True)

        ep = np.asarray(ep, dtype=float).ravel()

        for r in range(min(len(ep), self.front_table.rowCount())):
            mat_name = self._safe_get_combo_text(r, 0)

            qw_val = self._ep_nm_to_qwot(ep[r], mat_name)

            sb = self.front_table.cellWidget(r, 1)

            if sb:
                sb.setValue(qw_val)

        self.front_table.blockSignals(False)

    def _ep_nm_to_qwot(self, thickness_nm: float, mat_name: str) -> float:
        """Physical thickness (nm) -> QWOT at current lambda₀ (l0_spin or RE lambda_ref)."""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        n_val = 1.45

        if mat_name:
            m_obj = mats.get(mat_name)

            if m_obj:
                if hasattr(m_obj, "n4"):
                    n_val = m_obj.n4

                elif isinstance(m_obj, dict):
                    n_val = m_obj.get("n4", 1.45)

        return (4.0 * n_val * float(thickness_nm)) / l0 if abs(l0) > 1e-9 else 0.0

    def _update_spectrum_y_scale(self) -> None:
        """Updates Y scale based on option"""

        auto_scale = self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True

        if not auto_scale:
            # Fixed 0-1 scale

            self.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            # Auto scale

            self._auto_scale_spectrum_y()

    def _update_target_table_headers(self) -> None:
        """Update table headers by mode (normal/oblique)"""

        if self.oblique_mode:
            self.target_table.setColumnCount(9)

            self.target_table.setHorizontalHeaderLabels(
                [
                    "Active",
                    "Angle()",
                    "Pol",
                    "Type",
                    "lambdamin",
                    "lambdamax",
                    "Val min",
                    "Val max",
                    "Weight",
                ]
            )

        else:
            self.target_table.setColumnCount(6)

            self.target_table.setHorizontalHeaderLabels(["Active", "lambdamin", "lambdamax", "Tmin", "Tmax", "Weight"])

    def detach_front_table(self) -> None:
        """Detaches layer table to separate window"""

        from certus.workers.certus_spectral_workers import DetachedTableWindow

        if not self.detached_window:
            self.detached_window = DetachedTableWindow(self.front_table, self)

            self.detached_window.finished.connect(self.reattach_front_table)

            self.detached_window.show()

            self.placeholder_label = QLabel("Table Detached")

            self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.placeholder_label.setStyleSheet(
                f"background: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_DISABLED};"
            )

            self.front_container.layout().insertWidget(1, self.placeholder_label)

        else:
            self.detached_window.show()

            self.detached_window.raise_()

    def eventFilter(self, obj, event) -> Any:
        """Filters events to handle Excel copy/paste"""

        if obj == self.front_table and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._paste_from_excel()

                return True

        return super().eventFilter(obj, event)

    def log(self, msg: str, lvl: str = "INFO") -> None:
        """Adds message to log.

        P0.5 integration: mirrors ``SUCCESS`` / ``ERROR`` / ``WARNING``
        messages to the stacked toast notifications so user-facing state
        changes are visible even when the log panel is collapsed. ``INFO``
        stays log-only (too noisy for toasts).
        """

        colors = {
            "SUCCESS": CertusTheme.SUCCESS,
            "ERROR": CertusTheme.ERROR,
            "WARNING": CertusTheme.WARNING,
        }

        c = colors.get(lvl, CertusTheme.TEXT_SUB)

        # Show elapsed time if workflow is running

        elapsed_str = ""

        is_top_start = (
            ("Starting" in msg or "STARTING" in msg)
            and "optimization" in msg
            and not any(sub in msg for sub in ("Auto-Restart", "PGLOBAL Global", "iterative", "local re-optimization"))
        ) or "Creating REWorker" in msg or "Calling worker.start()" in msg

        if is_top_start:
            import time as _time
            self._workflow_wall_start = _time.time()

        t0 = getattr(self, "_workflow_wall_start", None)

        if t0 is not None:
            import time as _time

            elapsed = _time.time() - t0

            m, s = divmod(int(elapsed), 60)

            elapsed_str = f" <b>({m}m{s:02d}s)</b>"

        self.log_text.append(f"<span style='color:{c}'><b>[{certus_timestamp_display()}]</b>{elapsed_str} {msg}</span>")

        # P0.5 - Mirror to stacked toasts for important levels only
        self._mirror_log_to_toast(msg, lvl)

    def _mirror_log_to_toast(self, msg: str, lvl: str) -> None:
        """Best-effort mirror of a log line to the toast stack.

        Silently ignored on INFO level or if the toast module is
        unavailable. Strips HTML tags from ``msg`` before display.
        """
        lvl_norm = str(lvl).strip().upper()
        if lvl_norm not in ("SUCCESS", "ERROR", "WARNING"):
            return
        try:
            import re

            from certus.ui.certus_toast_stack import show_toast_stack

            variant = {"SUCCESS": "success", "ERROR": "error", "WARNING": "warning"}[lvl_norm]
            clean = re.sub(r"<[^>]+>", "", str(msg)).strip()
            if clean:
                show_toast_stack(self, clean[:200], variant=variant, duration_ms=3500)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def reattach_front_table(self) -> None:
        """Reattaches layer table"""

        if self.detached_window:
            self.front_container.layout().insertWidget(1, self.front_table)

            if hasattr(self, "placeholder_label"):
                self.placeholder_label.deleteLater()

                del self.placeholder_label

            self.detached_window.deleteLater()

            self.detached_window = None

    def reattach_plot(self, plot_name: str) -> None:
        """Reattaches detached plot"""

        if plot_name not in self.detached_plot_windows:
            return

        detached_window = self.detached_plot_windows[plot_name]

        detached_window.deleteLater()

        del self.detached_plot_windows[plot_name]

    def toggle_logs(self, checked: bool) -> None:
        """Toggle logs visibility"""

        self.log_container.setVisible(checked)

    def _create_combo(self, current: str) -> Any:
        """Creates material combo box"""

        from certus.core.certus_core import CFG

        from PyQt6.QtWidgets import QComboBox

        cb = QComboBox()

        cb.setToolTip("Select material.")

        materials = [m for m in CFG.MATERIALS if m != "Substrate" and m != "substrate"]

        cb.addItems(materials)

        if current in materials:
            cb.setCurrentText(current)

        return cb

    def _build_log_container(self) -> Any:
        """Constructs log container using shared CertusLogPanel."""

        panel = CertusLogPanel(title="LOGS", visible=True, height=120)

        self.log_text = panel.log_text

        def _on_logs_copied() -> None:

            sl = getattr(self, "status_label", None)

            if sl is not None and hasattr(sl, "setText"):
                sl.setText("Logs copied to clipboard.")

        panel.copied.connect(_on_logs_copied)

        self._log_panel = panel

        return panel

    def reset_qwot(self) -> None:
        """Resets all QWOTs to 1.0"""

        if not hasattr(self, "front_table"):
            return

        for r in range(self.front_table.rowCount()):
            widget = self.front_table.cellWidget(r, 1)

            if widget:
                widget.setValue(1.0)

        self._schedule_eval(True)

    def closeEvent(self, event) -> None:
        """Clean up on close."""

        self._qs_save()

        self._stop_all_workers()

        # Close detached windows

        for win in list(self.detached_plot_windows.values()):
            win.close()

        self.detached_plot_windows.clear()

        super().closeEvent(event)

    def _set_busy(self, b: bool) -> None:
        """Sets busy state with reference counting."""

        if b:
            self._busy_count += 1

        else:
            self._busy_count = max(0, self._busy_count - 1)

        busy_now = self._busy_count > 0

        self._is_busy = busy_now

        self._update_busy_ui(busy_now)

        if busy_now:
            if hasattr(self, "status_label"):
                self.status_label.setText("Computing...")

            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, 0)

        else:
            if hasattr(self, "status_label"):
                self.status_label.setText("Ready")

            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, 100)

                self.progress_bar.setValue(0)

    def _force_idle(self) -> None:
        """Force-reset busy counter and UI state to idle."""

        self._busy_count = 0

        self._is_busy = False

        self._update_busy_ui(False)

        if hasattr(self, "status_label"):
            self.status_label.setText("Ready")

        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setRange(0, 100)

            self.progress_bar.setValue(0)

    def _on_error(self, error_msg: object, generation_id: int | None = None) -> None:
        """Slot for ``WorkerSignals.error`` (EvalWorker, REWorker, DESIGN optimization, etc.)."""

        msg = error_msg if isinstance(error_msg, str) else str(error_msg)

        logging.error("Worker error:\n%s", msg)

        try:
            short = msg.strip().replace("\n", " ")

            if len(short) > 900:
                short = short[:900] + "..."

            self.log(short, "ERROR")

        except NUMERICAL_FAULT_EXCEPTIONS :
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self._set_busy(False)

        if getattr(self, "_re_mode_active", False):
            self._re_mode_active = False

            clr = getattr(self, "_re_clear_re_nk_preview", None)

            if callable(clr):
                clr()

        pw = getattr(self, "progress_widget", None)

        if pw is not None:
            try:
                pw.stop("Error")

            except NUMERICAL_FAULT_EXCEPTIONS :
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _update_busy_ui(self, busy: bool) -> None:
        """Hook for subclasses to update specific button states."""

        pass

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Hook for subclasses to provide substrate type and index display string."""

        return "N/A", "N/A"

    def _stack_info_front_table_cols(self) -> tuple[int, int]:
        """Columns (Mat combo, QWOT spin) for reading layer table in Stack Info."""

        return (0, 1)

    def _stack_info_l0_nm(self) -> float:
        """lambda₀ (nm) for n@lambda₀ in Stack Info."""

        if hasattr(self, "l0_spin"):
            return float(self.l0_spin.value())

        if hasattr(self, "_re_lambda_ref"):
            return float(self._re_lambda_ref)

        return 500.0

    def _stack_info_n_re_at_l0(self, mat_name: str, l0: float) -> float | None:
        """Re(n) at lambda₀ for a layer; None if unknown."""

        if not mat_name or not hasattr(self, "_get_materials"):
            return None

        mats = self._get_materials()

        if not mats or mat_name not in mats:
            return None

        try:
            wls = np.array([float(l0)], dtype=np.float64)

            nk = mats[mat_name].get_nk(wls)

            return float(np.real(np.asarray(nk, dtype=np.complex128).ravel()[0]))

        except NUMERICAL_FAULT_EXCEPTIONS :
            m = mats[mat_name]

            n4 = getattr(m, "n4", None)

            return float(n4) if n4 is not None else None

    def _stack_info_format_layer_line(self, idx1: int, mat_str: str, qwot: float, l0: float) -> str:
        """A 'Layer k: ...' line with Re(n)@lambda₀ formatted to 3 decimals."""

        nr = self._stack_info_n_re_at_l0(mat_str, l0)

        n_s = f"{nr:.3f}" if nr is not None and np.isfinite(nr) else ""

        return f"Layer {idx1}: {mat_str}  n@lambda₀={n_s}  {float(qwot):.4f} QWOT\n"

    def _update_substrate_info(self) -> None:
        """Update stack information window with current/best design (layers in QWOT)."""

        if not getattr(self, "substrate_info_window", None) or not self.substrate_info_window.isVisible():
            return

        substrate_type, substrate_index = self._get_substrate_info_display()

        self.substrate_type_label.setText(substrate_type)

        self.substrate_index_label.setText(substrate_index)

        structure_text = "\n=== DESIGN STRUCTURE ===\n\n"

        best_ep = getattr(self, "_stack_info_best_ep", None)

        l0 = self._stack_info_l0_nm()

        if best_ep is not None and hasattr(self, "_get_front_stack") and hasattr(self, "_get_materials"):
            stack = self._get_front_stack()

            mats = self._get_materials()

            ep = np.asarray(best_ep).flatten()

            n_layers = min(len(stack), len(ep))

            structure_text += f"Total layers: {n_layers} (best so far)\n\n"

            for i in range(n_layers):
                mat_str = getattr(stack[i], "mat", "?")

                d_nm = float(ep[i]) if i < len(ep) else 0.0

                n_val = 1.5

                if mats and stack[i].mat in mats:
                    m = mats[stack[i].mat]

                    n_val = float(getattr(m, "n4", 1.5))

                qwot = (4.0 * n_val * d_nm) / l0 if abs(l0) > 1e-9 else 0.0

                structure_text += self._stack_info_format_layer_line(i + 1, str(mat_str), qwot, l0)

        elif hasattr(self, "front_table"):
            n_layers = self.front_table.rowCount()

            structure_text += f"Total layers: {n_layers}\n\n"

            c_mat, c_qw = self._stack_info_front_table_cols()

            for r in range(n_layers):
                mat_str = "?"

                qwot_f = float("nan")

                cb = self.front_table.cellWidget(r, c_mat)

                if cb and hasattr(cb, "currentText"):
                    mat_str = cb.currentText()

                sb = self.front_table.cellWidget(r, c_qw)

                if sb and hasattr(sb, "value"):
                    try:
                        qwot_f = float(sb.value())

                    except (TypeError, ValueError):
                        qwot_f = float("nan")

                if np.isfinite(qwot_f):
                    structure_text += self._stack_info_format_layer_line(r + 1, mat_str, qwot_f, l0)

                else:
                    nr = self._stack_info_n_re_at_l0(mat_str, l0)

                    n_s = f"{nr:.3f}" if nr is not None and np.isfinite(nr) else ""

                    structure_text += f"Layer {r + 1}: {mat_str}  n@lambda₀={n_s}  ? QWOT\n"

        structure_text += f"\n=== SUBSTRATE ===\n\nType: {substrate_type}\nIndex: {substrate_index}\n"

        structure_text += f"\nReference lambda₀: {l0} nm\n"

        best_rmse = getattr(self, "_stack_info_best_rmse", None) or getattr(self, "_workflow_best_rmse", None)

        if best_rmse is not None and np.isfinite(best_rmse):
            structure_text += f"\n=== OPTIMIZATION ===\n\nBest RMSE: {best_rmse:.6f}\n"

        self.structure_text.setText(structure_text)


# These methods belong to CertusBaseApp  they were migrated here from CERTUS_RE/CERTUS_DESIGN.


# They are monkey-patched onto CertusBaseApp to avoid a structural refactor mid-session.


class CertusDashboardCard(QFrame):
    """UX-1: Professional metrics card for results dashboard."""

    def __init__(self, title: str, icon_name: str = "activity", unit: str = "") -> None:
        super().__init__()
        self.unit = unit
        self._intro_fade_started = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            CertusDashboardCard {{
                background-color: {CertusTheme.BASE_ELEVATED};
                border-radius: 8px;
                border: 1px solid {CertusTheme.BORDER};
            }}
        """)
        self.setMinimumWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-weight: bold; font-size: 11px; letter-spacing: 1px;"
        )

        self.lbl_icon = QLabel()
        try:
            from certus.ui.certus_icons import certus_icon

            icon = certus_icon(icon_name, color=CertusTheme.TEXT_SUB, size=16)
            pm = icon.pixmap(16, 16)
            if pm is None or pm.isNull():
                self.lbl_icon.setText("•")
            else:
                self.lbl_icon.setPixmap(pm)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            self.lbl_icon.setText("•")

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_icon)
        layout.addLayout(header)

        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        val_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        self.lbl_value = QLabel("---")
        self.lbl_value.setStyleSheet(f"color: {CertusTheme.TEXT}; font-size: 28px; font-weight: 800;")

        self.lbl_unit = QLabel(unit)
        self.lbl_unit.setStyleSheet(
            f"color: {CertusTheme.TEXT_SUB}; font-size: 14px; font-weight: bold; margin-bottom: 4px;"
        )

        val_row.addWidget(self.lbl_value)
        val_row.addWidget(self.lbl_unit)
        layout.addLayout(val_row)

        self.lbl_msg = QLabel("Ready")
        self.lbl_msg.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setVisible(False)
        layout.addWidget(self.lbl_msg)

        try:
            from certus.ui.certus_animations import hover_lift

            hover_lift(self, lift_px=2)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def update_value(self, value: str, status: str = "normal", msg: str = "") -> None:
        self.lbl_value.setText(value)

        color_map = {
            "success": CertusTheme.SUCCESS,
            "warning": CertusTheme.WARNING,
            "danger": CertusTheme.DANGER,
            "info": CertusTheme.PRIMARY,
            "normal": CertusTheme.TEXT,
        }
        val_color = color_map.get(status, CertusTheme.TEXT)
        self.lbl_value.setStyleSheet(f"color: {val_color}; font-size: 28px; font-weight: 800;")

        if msg:
            self.lbl_msg.setText(msg)
            self.lbl_msg.setVisible(True)
            self.lbl_msg.setStyleSheet(f"color: {val_color}; font-size: 11px; font-weight: 500;")
        else:
            self.lbl_msg.setVisible(False)

        try:
            from certus.ui.certus_animations import pulse

            pulse(self.lbl_value)
        except (ImportError, ModuleNotFoundError, AttributeError):
            # Animation module unavailable - skip pulse animation
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._intro_fade_started:
            return
        self._intro_fade_started = True
        try:
            from certus.ui.certus_animations import fade_in

            fade_in(self, duration_ms=180)
        except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):
            return


class SkeletonLoaderWidget(QWidget):
    """
    A premium skeleton loader widget with a smooth horizontal shimmer effect.
    Simulates loading of dashboards, charts, or tables (P0 UX action plan).
    """
    def __init__(self, parent=None, shape: str = "chart") -> None:
        super().__init__(parent)
        self.shape = shape  # "chart", "table", "dashboard", "cards"
        self._shimmer_offset = -0.5
        
        from PyQt6.QtCore import QTimeLine, QEasingCurve
        self._timeline = QTimeLine(1400, self)
        self._timeline.setFrameRange(0, 100)
        self._timeline.setLoopCount(0)  # Loop infinitely
        self._timeline.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._timeline.frameChanged.connect(self._update_shimmer)
        self._timeline.start()

    def _update_shimmer(self, frame: int) -> None:
        self._shimmer_offset = -0.5 + (frame / 100.0) * 2.0
        self.update()

    def paintEvent(self, event) -> None:
        from PyQt6.QtGui import QPainter, QLinearGradient, QBrush, QColor, QPainterPath
        from PyQt6.QtCore import QRectF, Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from certus.ui.certus_ui import CertusTheme
        is_dark = getattr(CertusTheme, "DARK_MODE", False)
        
        base_color = QColor("#1e293b") if is_dark else QColor("#e2e8f0")
        shimmer_color = QColor("#334155") if is_dark else QColor("#f1f5f9")
        
        w = float(self.width())
        h = float(self.height())
        
        grad = QLinearGradient(self._shimmer_offset * w, 0, (self._shimmer_offset + 0.4) * w, h)
        grad.setColorAt(0.0, base_color)
        grad.setColorAt(0.45, base_color)
        grad.setColorAt(0.5, shimmer_color)
        grad.setColorAt(0.55, base_color)
        grad.setColorAt(1.0, base_color)
        
        brush = QBrush(grad)
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        
        if self.shape == "chart":
            axis_pen = QColor("#334155") if is_dark else QColor("#cbd5e1")
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(axis_pen, 1))
            painter.drawLine(40, int(h - 40), int(w - 40), int(h - 40))
            painter.drawLine(40, 40, 40, int(h - 40))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(brush)
            path = QPainterPath()
            path.moveTo(40, h - 40)
            path.cubicTo(w * 0.25, h * 0.45, w * 0.5, h * 0.75, w * 0.75, h * 0.3)
            path.lineTo(w - 40, h - 40)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif self.shape == "table":
            row_height = 20
            spacing = 8
            y = 15
            while y + row_height < h:
                painter.drawRoundedRect(QRectF(15, y, w * 0.2, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.25, y, w * 0.3, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.6, y, w * 0.15, row_height), 4, 4)
                painter.drawRoundedRect(QRectF(w * 0.8, y, w * 0.15 - 15, row_height), 4, 4)
                y += row_height + spacing
                
        elif self.shape == "cards":
            card_w = (w - 30) / 2
            card_h = (h - 30) / 2
            if card_w > 10 and card_h > 10:
                painter.drawRoundedRect(QRectF(10, 10, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(20 + card_w, 10, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(10, 20 + card_h, card_w, card_h), 8, 8)
                painter.drawRoundedRect(QRectF(20 + card_w, 20 + card_h, card_w, card_h), 8, 8)
        else:
            painter.drawRoundedRect(QRectF(10, 10, w - 20, h - 20), 8, 8)


def install_skeleton_loader(target_widget: QWidget, shape: str = "chart") -> SkeletonLoaderWidget:
    """
    Overlays a premium SkeletonLoaderWidget on top of target_widget.
    The loader dynamically resizes to match target_widget bounds.
    """
    remove_skeleton_loader(target_widget)
    from PyQt6.QtCore import QObject, QEvent
    
    loader = SkeletonLoaderWidget(target_widget, shape=shape)
    loader.setGeometry(target_widget.rect())
    loader.show()
    
    class ResizeFilter(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Resize:
                loader.setGeometry(target_widget.rect())
            return False
            
    filt = ResizeFilter(target_widget)
    target_widget.installEventFilter(filt)
    target_widget._certus_skeleton = (loader, filt)
    return loader


def remove_skeleton_loader(target_widget: QWidget) -> bool:
    """Removes a previously installed skeleton loader from target_widget."""
    removed = False
    data = getattr(target_widget, "_certus_skeleton", None)
    if data is not None:
        loader, filt = data
        try:
            target_widget.removeEventFilter(filt)
        except Exception:
            pass
        try:
            loader.hide()
            loader.setParent(None)
            loader.deleteLater()
        except Exception:
            pass
        try:
            del target_widget._certus_skeleton
        except Exception:
            pass
        removed = True

    try:
        # Also clean up any orphaned skeleton loader widgets that might be children
        for child in target_widget.findChildren(SkeletonLoaderWidget):
            try:
                child.hide()
                child.setParent(None)
                child.deleteLater()
                removed = True
            except Exception:
                pass
    except Exception:
        pass

    return removed


def _hex_to_rgba_css(hex_str: str, alpha: float) -> str:
    c = hex_str.lstrip("#")
    if len(c) == 6:
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    return hex_str


def apply_os_window_effects(window: QWidget, dark_mode: bool = False) -> None:
    """
    Applies modern OS integration effects (e.g. Windows 11 Mica effect,
    immersive dark title bars) in a safe and portable manner.
    """
    import os
    if os.name != "nt":
        return

    try:
        import ctypes
        hwnd = int(window.winId())
        if not hwnd:
            return

        # 1. Title bar theme (Immersive Dark Mode)
        # Windows 10 build 17763+ and Windows 11
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        is_dark = ctypes.c_int(1 if dark_mode else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(is_dark),
            ctypes.sizeof(is_dark)
        )

        # 2. Mica effect under Windows 11 (Build >= 22000)
        import platform
        try:
            build = int(platform.version().split('.')[-1])
            is_win11 = build >= 22000
        except Exception:
            is_win11 = False

        if is_win11:
            # DWMWA_SYSTEMBACKDROP_TYPE = 38
            # DWMSBT_MAINWINDOW = 2 (Mica)
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            backdrop_type = ctypes.c_int(2)  # Mica
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(backdrop_type),
                ctypes.sizeof(backdrop_type)
            )

            # Enable translucent window background to allow Mica rendering
            from PyQt6.QtCore import Qt
            window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

            # Apply translucent background to parent windows in QSS to prevent blocking Mica
            from certus.ui.certus_theme import CertusTheme
            bg_color = CertusTheme.BACKGROUND
            alpha = 0.70 if dark_mode else 0.80
            rgba_css = _hex_to_rgba_css(bg_color, alpha)
            
            current_style = window.styleSheet() or ""
            override_style = f"\nQMainWindow, QMainWindow > QWidget, QDialog, QDialog > QWidget {{ background: {rgba_css}; background-color: {rgba_css}; }}"
            window.setStyleSheet(current_style + override_style)
    except Exception:
        # Silently fail if win32 API / dwmapi is not available (e.g. mock test environment)
        pass


# ---------------------------------------------------------------------------
# Lazy re-exports (break certus_ui <-> certus_export / certus_plot cycles)
# ---------------------------------------------------------------------------

_LAZY_REEXPORTS: dict[str, tuple[str, str]] = {
    # name -> (module, attribute)
    "get_plot_style_config": ("certus.ui.certus_plot", "get_plot_style_config"),
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
