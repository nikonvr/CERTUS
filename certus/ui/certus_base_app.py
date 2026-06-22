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

from certus.ui.mixins.certus_base_core_mixins import (
    CertusZoomMixin, CertusCommandPaletteMixin, CertusPremiumExportMixin, 
    CertusEmptyStateMixin, CertusRecentsMixin, CertusDialogMixin
)

class CertusBaseApp(
    QMainWindow,
    CertusZoomMixin,
    CertusCommandPaletteMixin,
    CertusPremiumExportMixin,
    CertusEmptyStateMixin,
    CertusRecentsMixin,
    CertusDialogMixin,
):
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

    def __init__(
        self,
        parent=None,
        runtime: CertusRuntime | None = None,
        worker_manager=None,
        numba_manager=None,
    ) -> None:

        super().__init__(parent)

        # Runtime container is injectable to avoid hidden globals.
        self.runtime: CertusRuntime = runtime if runtime is not None else build_runtime()

        from certus.ui.certus_worker_manager import CertusWorkerManager, CertusNumbaWarmupManager
        self.worker_manager = worker_manager or CertusWorkerManager(self)
        self.numba_manager = numba_manager or CertusNumbaWarmupManager(logging.getLogger("CERTUS"), self)

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

        # Numba ready flag

        self.numba_ready = False
        
        self.numba_manager.sig_numba_ready.connect(self._on_numba_ready_from_manager)
        self.numba_manager.sig_numba_error.connect(self._on_numba_error_from_manager)

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



    # =========================================================================
    # U3 — Command palette
    # =========================================================================



    # =========================================================================
    # P5 - Destructive-action confirmations (uniform modal)
    # =========================================================================



    # =========================================================================
    # P3 - Premium report helpers (Excel + PDF via certus_reports)
    # =========================================================================



    # =========================================================================
    # P1.1 - Skeleton overlay convenience (any long-running op can use these)
    # =========================================================================
    # =========================================================================
    # P1.3 - Empty states for well-known tables (auto-wired)
    # =========================================================================

    # (attribute name on self -> (icon, title, description, optional CTA))


    # =========================================================================
    # U5 — Recent files
    # =========================================================================



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
        Call self.numba_manager.start_warmup() when done.
        """
        self.numba_manager.start_warmup(None)

    def _on_numba_ready_from_manager(self) -> None:
        self.numba_ready = True
        
    def _on_numba_error_from_manager(self, message: str) -> None:
        self.numba_ready = False

    def _on_numba_ready(self) -> None:
        """Called when Numba warmup completes."""
        self.numba_manager.on_warmup_done()

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
        self._on_numba_ready()

    def _on_warmup_error(self, message: str) -> None:
        self.numba_manager.on_warmup_error(message)


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
        self.worker_manager.unregister_worker(worker)

    def _stop_all_workers(self) -> None:
        """Stop all active workers."""
        self.worker_manager.stop_all()

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

        # For Y axis, we just use Pyqtgraph's native AutoRange so it behaves exactly like the 'A' button
        self.spectrum_plot.plotItem.enableAutoRange(y=True)

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
        return True

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

        if hasattr(self, 'log_text'):
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