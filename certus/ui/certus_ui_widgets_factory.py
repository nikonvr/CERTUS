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
    # Widgets
    # Factory Functions
    "create_header_logo_widget",
    "create_styled_button",
    "create_info_icon",
    "create_help_button",
    "open_documentation",
    "create_flashy_grid",
    "create_log_widget",
    "SplitterCapper",
    "attach_splitter_capper",
    # Pro UX Design System components
    # Threading
    # App Base
    # Utilities
    # Re-exports from certus.core.certus_core
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
    QEvent,
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
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_utils import open_documentation


# =============================================================================






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
        from certus.ui.certus_ui_widgets_utils import AutoShrinkTitleLabel
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
        btn_help.setToolTip(f"Open documentation for {module_name} (F1)")
        # Window chrome must not hold the keyboard focus. Measured 2026-09-05:
        # this button was the FIRST focusable widget of every window, so pressing
        # Space on a freshly opened module opened the documentation, and the tab
        # chain started here instead of at the first field. F1 and the mouse
        # still reach it.
        btn_help.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_help.setProperty("certus_chrome", True)

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

    # Chrome, like the "Help" button above: reachable by F1 and by the mouse,
    # never by default focus.
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setProperty("certus_chrome", True)

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
        # Chrome, like the help button and the theme toggle. Measured 2026-09-05:
        # once Help stopped taking the focus, it fell on THIS bar - 'Save' in
        # DESIGN and FIELD, 'Export' in RE - so Space still fired an action the
        # operator had not chosen. Ctrl+S / Ctrl+O / Ctrl+E and the mouse reach
        # these; the tab chain should start at the first field instead.
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setProperty("certus_chrome", True)
        btn.setMinimumWidth(60)

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


class SplitterCapper(QObject):
    """Caps the left control panel of a horizontal QSplitter at a relative fraction of the window."""

    def __init__(self, splitter: QSplitter, max_ratio: float = 0.34, parent: QObject | None = None) -> None:
        super().__init__(parent or splitter)
        self.splitter = splitter
        self.max_ratio = max_ratio

    def eventFilter(self, obj: QObject, event: Any) -> bool:
        if obj is self.splitter and event.type() in (QEvent.Type.Paint, QEvent.Type.LayoutRequest):
            win = self.splitter.window()
            if getattr(win, "_layout_restored_from_settings", False):
                return False
            sizes = self.splitter.sizes()
            total = sum(sizes)
            if total > 0:
                cap = int(total * self.max_ratio)
                lp = self.splitter.widget(0)
                floor = max(lp.minimumSizeHint().width(), 0) if lp is not None else 0
                target = max(cap, floor)
                if sizes and sizes[0] > target:
                    self.splitter.setSizes([target, total - target])
        return False


def attach_splitter_capper(splitter: QSplitter, max_ratio: float = 0.34) -> SplitterCapper:
    """Installs a SplitterCapper on the given splitter to enforce plot area >= 65% on compact displays."""
    capper = SplitterCapper(splitter, max_ratio=max_ratio, parent=splitter)
    splitter.installEventFilter(capper)
    return capper