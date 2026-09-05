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
    # Widgets
    # Factory Functions
    "set_certus_window_icon",
    "open_documentation",
    # Pro UX Design System components
    # SkeletonLoaderWidget removed from __all__: it is NOT an export of this module at
    # runtime. It comes from certus_ui_widgets_utils, which itself imports from
    # certus_ui_utils (line 86) — hence a cycle, broken here by an import placed under
    # `if TYPE_CHECKING`. The name is therefore only used as a return annotation, in
    # quotes (install_skeleton_loader, line 1219).
    # Declaring it in __all__ caused an AttributeError for any `import *` on this
    # module. ruff does not report it: a TYPE_CHECKING import binds the name in
    # its static analysis. Only a runtime check reveals it.
    # Consumers must import it from certus_ui_widgets_utils, which is what
    # certus_ui.py:274 already does.
    "install_skeleton_loader",
    "remove_skeleton_loader",
    "apply_os_window_effects",
    "install_standard_shortcuts",
    "install_unique_shortcut",
    "claim_shortcut_for_action",
    "shortcut_owner",
    "normalized_shortcut",
    "enable_file_drop",
    "show_toast",
    "attach_numeric_validator",
    # Threading
    # App Base
    # Utilities
    "get_export_settings",
    "open_file_explorer",
    "process_log_queue_standard",
    "confirm_stop_with_timeout",
    "copy_app_logs_to_clipboard",
    "format_count_kmg",
    "stop_worker_and_thread",
    "confirm_and_stop",
    "init_certus_app",
    "setup_pyqtgraph_defaults",
    "setup_gui_exception_handling",
    "safe_ui_action",
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


from typing import TYPE_CHECKING, Any, Callable


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


from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPalette, QShortcut


if TYPE_CHECKING:
    from certus.ui.certus_ui_widgets_utils import SkeletonLoaderWidget

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







from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.core.certus_core import load_theme_config

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

    # Apply the PERSISTED preference before building the stylesheet. Measured
    # 2026-09-04: load_theme_config() returned "dark" and all eleven windows
    # opened in light, because the preference reached only apply_os_window_effects
    # below (the OS title bar) and the plot palette - never CertusTheme itself.
    # The operator got a dark title bar around a light interface.
    # Read once and reuse: two reads could disagree if the file changes between.
    _persisted_mode = load_theme_config()
    CertusTheme.configure(_persisted_mode)

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
        apply_os_window_effects(window, _persisted_mode == "dark")

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

def normalized_shortcut(seq: str | QKeySequence) -> str:
    """Canonical string representation of a key sequence."""
    return QKeySequence(seq).toString()


def shortcut_owner(window: QWidget, sequence: str) -> str | None:
    """Return a descriptive label of the existing window-level binding, or None."""
    target = normalized_shortcut(sequence)
    if not target:
        return None
    for sc in window.findChildren(QShortcut):
        if sc.context() in (
            Qt.ShortcutContext.WindowShortcut,
            Qt.ShortcutContext.ApplicationShortcut,
        ) and normalized_shortcut(sc.key()) == target:
            return f"QShortcut({target})"
    for act in window.findChildren(QAction):
        for ks in act.shortcuts():
            if normalized_shortcut(ks) == target:
                return f"QAction({act.text() or target})"
    return None


def install_unique_shortcut(window: QWidget, sequence: str, callback) -> QShortcut | None:
    """Install a QShortcut only if the sequence is valid and not yet claimed on window."""
    target = normalized_shortcut(sequence)
    if not target:
        return None
    existing = shortcut_owner(window, target)
    if existing is not None:
        logging.getLogger("CERTUS").debug(
            "Shortcut %s already claimed by %s on %s - skipping",
            target,
            existing,
            type(window).__name__,
        )
        return None
    sc = QShortcut(QKeySequence(target), window)
    sc.setContext(Qt.ShortcutContext.WindowShortcut)
    sc.activated.connect(callback)
    return sc


def claim_shortcut_for_action(action: QAction, sequence: str, window: QWidget | None = None) -> bool:
    """Assign sequence to action if not already claimed at window level."""
    target = normalized_shortcut(sequence)
    if not target:
        return False
    if window is not None:
        existing = shortcut_owner(window, target)
        if existing is not None:
            logging.getLogger("CERTUS").debug(
                "Shortcut %s already claimed by %s on %s - skipping action shortcut",
                target,
                existing,
                type(window).__name__,
            )
            return False
    action.setShortcut(QKeySequence(target))
    return True


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
        # NOT "Ctrl+Plus" / "Ctrl+Minus": QKeySequence resolves both to an EMPTY
        # sequence on Qt 6, so those entries bound nothing at all. Zoom only
        # worked through the alias_map below. Measured 2026-09-05.
        "zoom_in": ("Ctrl++", zoom_in),
        "zoom_out": ("Ctrl+-", zoom_out),
        "reset_zoom": ("Ctrl+0", reset_zoom),
    }
    installed: dict = {}
    for name, (seq, cb) in mapping.items():
        if cb is None:
            continue
        sc = install_unique_shortcut(window, seq, cb)
        claimed_by = getattr(window, "_certus_shortcut_actions", None)
        if claimed_by is None:
            claimed_by = {}
            window._certus_shortcut_actions = claimed_by
        if sc is not None:
            installed[f"{name}:{seq}"] = sc
            claimed_by[normalized_shortcut(seq)] = name
        elif claimed_by.get(normalized_shortcut(seq)) == name:
            # Same action asked twice - INDEX, for one, wires zoom from both its
            # own _setup_shortcuts and install_common_affordances. The key works;
            # there is nothing for anyone to fix, so this must not shout. A
            # warning that cries for nothing teaches people to ignore warnings.
            logging.getLogger("CERTUS").debug(
                "%s: shortcut %r for %r was already installed by an earlier call",
                type(window).__name__,
                seq,
                name,
            )
        else:
            # install_unique_shortcut declines a sequence already claimed - on
            # purpose, since binding one twice makes Qt emit activatedAmbiguously
            # and run NEITHER handler. But declining in SILENCE is how RE lost
            # its Excel export: it bound Ctrl+E to evaluate first, then asked for
            # export on the same key and never learned that nothing happened.
            logging.getLogger("CERTUS").warning(
                "%s: shortcut %r requested for %r but already claimed by %s - not installed",
                type(window).__name__,
                seq,
                name,
                shortcut_owner(window, seq),
            )
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
            sc = install_unique_shortcut(window, candidate, cb)
            if sc is not None:
                installed[f"{name}:{candidate}"] = sc
    if extra:
        for seq, cb in extra.items():
            if cb is None:
                continue
            sc = install_unique_shortcut(window, seq, cb)
            if sc is not None:
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
    from certus.ui.certus_ui_widgets_utils import CertusToast
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

from certus.ui.certus_io_ui import open_file_explorer
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
            asctime, levelname, actual_msg = None, None, None
            for sep2 in (" ➔ ", " -> "):
                if sep2 in msg:
                    prefix, actual_msg = msg.split(sep2, 1)
                    for sep1 in (" ✦ ", " * "):
                        if sep1 in prefix:
                            asctime, levelname = prefix.split(sep1, 1)
                            levelname = levelname.strip()
                            break
                    break
            if asctime is None:
                parts = msg.split(" | ", 2)
                if len(parts) == 3:
                    asctime, levelname, actual_msg = parts
            if asctime is not None and levelname is not None and actual_msg is not None:

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
    "Install global exception hook for GUI applications."

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

def confirm_stop_with_timeout(parent, timeout_sec=10) -> bool:
    """

    Shows a confirmation dialog with a countdown, and INACTION KEEPS THE RUN.

    Until 2026-09-05 this stopped the optimisation on three kinds of inaction:
    the destructive button held the focus, the countdown clicked it after
    ``timeout_sec``, and the fall-through read "no button clicked" - which is
    what closing the dialog with Escape or the X produces - as a confirmation.
    Esc is bound to stop in every module (step 2.20a) and it is a reflex key, so
    one unmeant press followed by walking away cost a run that takes 2 h 39 on
    STRAT.

    Returns:

        True: the operator CLICKED 'Stop Now'. Nothing else returns True.

        False: cancelled, dismissed, or the countdown expired - keep running.

    """

    # Ask nothing when the window says nothing is running. Esc is bound to stop
    # in every module and it is a reflex key: on an idle window this used to open
    # a box counting down the interruption of nothing, then answer itself.
    #
    # OPT-IN on purpose. A window that does not implement the probe, or that
    # cannot answer for sure, keeps the dialog: an over-reaching guard would make
    # a RUNNING computation unstoppable, which is worse than the defect. Only an
    # explicit False silences it.
    probe = getattr(parent, "has_running_computation", None)
    if callable(probe):
        try:
            if probe() is False:
                return False
        except RuntimeError, AttributeError, TypeError:
            logging.getLogger("CERTUS").debug("has_running_computation failed", exc_info=True)

    msg = QMessageBox(parent)

    msg.setWindowTitle("Stop Confirmation")

    msg.setIcon(QMessageBox.Icon.Question)

    # text will be updated by timer

    msg.setText(f"Stop the optimization? Resuming in {timeout_sec} seconds...")

    msg.setInformativeText(
        "Click 'Stop Now' to stop; the current best result will be saved.\n"
        "Doing nothing keeps the optimization running."
    )

    btn_stop = msg.addButton("Stop Now", QMessageBox.ButtonRole.AcceptRole)

    btn_cancel = msg.addButton("Keep running", QMessageBox.ButtonRole.RejectRole)

    # The focused button must be the one that loses nothing: Enter or Space on a
    # dialog the operator has not read must not end a two-hour run.
    msg.setDefaultButton(btn_cancel)

    remaining = timeout_sec

    def update_timer() -> None:

        nonlocal remaining

        remaining -= 1

        if remaining <= 0:
            # Close WITHOUT clicking: a countdown may cancel by itself, it may
            # never destroy by itself.
            msg.reject()

        else:
            msg.setText(f"Stop the optimization? Resuming in {remaining} seconds...")

    timer = QTimer(msg)

    timer.timeout.connect(update_timer)

    timer.start(1000)

    msg.exec()

    timer.stop()

    # Only an explicit click on the destructive button confirms. Dismissing the
    # dialog leaves clickedButton() at None, which the old code read as "stop".
    return msg.clickedButton() is btn_stop

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

def install_skeleton_loader(target_widget: QWidget, shape: str = "chart") -> "SkeletonLoaderWidget":
    from certus.ui.certus_ui_widgets_utils import SkeletonLoaderWidget
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
    from certus.ui.certus_ui_widgets_utils import SkeletonLoaderWidget
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
