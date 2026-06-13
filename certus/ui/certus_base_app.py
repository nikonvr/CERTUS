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


from certus.ui.certus_plot import clone_plot_widget
from certus.ui.certus_ui_widgets_utils import DetachedPlotWindow
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




from certus.ui.certus_ui_utils import (
    safe_ui_action, show_toast, show_status_feedback, confirm_stop_with_timeout,
    process_log_queue_standard, open_file_explorer, stop_worker_and_thread,
    format_count_kmg, set_certus_window_icon, copy_app_logs_to_clipboard,
    install_standard_shortcuts, _CertusDropFilter, update_global_plot_config,
    apply_certus_theme
)
from certus.ui.certus_ui_widgets_factory import (
    create_log_widget, create_top_actions_bar
)
from certus.ui.certus_ui_widgets_utils import CertusLogPanel
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
import certus.ui.certus_io_ui as certus_io_ui

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
            path = certus_io_ui.certus_get_save_file_name(self, "Export premium Excel report", "Excel (*.xlsx)")
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
            path = certus_io_ui.certus_get_save_file_name(self, "Export premium PDF report", "PDF (*.pdf)")
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

        default_path = str(Path(certus_io_ui.get_certus_last_dir() or ".") / self._get_default_config_name())

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration",
            default_path,
            self._get_config_file_filter(),
        )

        if filename:
            certus_io_ui.set_certus_last_dir(filename)

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
                self, "Load Configuration", certus_io_ui.get_certus_last_dir(), self._get_config_file_filter()
            )

        if filename:
            certus_io_ui.set_certus_last_dir(filename)

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