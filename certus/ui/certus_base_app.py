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
    # Re-exports from certus.core.certus_core
    # Flags
    "SVG_AVAILABLE",
    # Threading
    # App Base
    "CertusBaseApp",
    "CertusLogPanel",
    # Theme
    "CertusTheme",
    # Widgets
    "DetachedPlotWindow",
    "StatsCounter",
    "apply_certus_theme",
    "clone_plot_widget",
    "confirm_stop_with_timeout",
    "copy_app_logs_to_clipboard",
    "create_log_widget",
    "format_count_kmg",
    "get_standard_stylesheet",
    # Pro UX Design System components
    "install_standard_shortcuts",
    # Utilities
    "open_file_explorer",
    "process_log_queue_standard",
    "safe_ui_action",
    # Factory Functions
    "set_certus_window_icon",
    "show_toast",
    "stop_worker_and_thread",
]


import logging


import queue


import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast", module="pyqtgraph")

from collections import deque


from typing import Any


from certus.ui.certus_plot import clone_plot_widget
from certus.ui.certus_ui_widgets_utils import DetachedPlotWindow


from certus.core.certus_core import CFG


# PyQtGraph ViewBox vs NumPy/Python 3.14  cosmetic RuntimeWarning on cast (any emitting module)


warnings.filterwarnings(
    "ignore",
    message=r"overflow encountered in cast",
    category=RuntimeWarning,
)


from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal


from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QLabel, QLineEdit, QMainWindow, QSplitter


# Check optional dependencies


# Import Core


from certus.core.certus_core import CertusRuntime, build_runtime
from certus.ui.certus_qt_svg import SVG_AVAILABLE


if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


# OPENPYXL_AVAILABLE imported from certus.core.certus_core (Single Source of Truth)


from certus.core.certus_core import OPENPYXL_AVAILABLE


# =============================================================================


from certus.ui.certus_ui_utils import (
    safe_ui_action,
    show_toast,
    confirm_stop_with_timeout,
    process_log_queue_standard,
    open_file_explorer,
    stop_worker_and_thread,
    format_count_kmg,
    set_certus_window_icon,
    copy_app_logs_to_clipboard,
    install_standard_shortcuts,
    install_unique_shortcut,
    apply_certus_theme,
    configure_theme_from_preference,
)
from certus.ui.certus_ui_widgets_factory import attach_splitter_capper, create_log_widget
from certus.ui.certus_ui_widgets_utils import CertusLogPanel
from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.utils.certus_ux import Typography


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
        if hasattr(self, "lbl_status") and hasattr(self.lbl_status, "setText"):
            self.lbl_status.setText("Logs copied to clipboard!")

    def on_toggle_details(self, checked: bool) -> None:
        """Show/Hide log panel dynamically."""
        if hasattr(self, "log_text"):
            self.log_text.setVisible(checked)
        if hasattr(self, "toggle_details_btn"):
            self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")
        if hasattr(self, "right_splitter"):
            if checked:
                self.right_splitter.setSizes([600, 200])
            else:
                self.right_splitter.setSizes([1000, 0])


from certus.ui.mixins.certus_base_core_mixins import (
    CertusZoomMixin,
    CertusCommandPaletteMixin,
    CertusPremiumExportMixin,
    CertusEmptyStateMixin,
    CertusRecentsMixin,
    CertusDialogMixin,
)

# Mixins moved out of this class (S5.3): the methods live there, the names stay importable from here.
from certus.ui.certus_base_app_config_mixin import CertusAppConfigMixin
from certus.ui.certus_base_app_engine_mixin import CertusAppEngineMixin
from certus.ui.certus_base_app_stack_mixin import CertusAppFrontStackMixin
from certus.ui.certus_base_app_plot_mixin import CertusAppPlotMixin
from certus.ui.certus_base_app_undo_mixin import CertusAppUndoMixin
from certus.ui.certus_base_app_run_mixin import CertusAppRunStateMixin
from certus.ui.certus_base_app_info_mixin import CertusAppStackInfoMixin


class CertusBaseApp(QMainWindow, CertusZoomMixin, CertusCommandPaletteMixin, CertusPremiumExportMixin, CertusEmptyStateMixin, CertusRecentsMixin, CertusDialogMixin, CertusAppConfigMixin, CertusAppEngineMixin, CertusAppFrontStackMixin, CertusAppPlotMixin, CertusAppUndoMixin, CertusAppRunStateMixin, CertusAppStackInfoMixin):
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

        # BEFORE any widget: a widget-level stylesheet is an f-string evaluated
        # once, at build time. Configured later - as apply_certus_theme does at
        # the end of construction - those sheets keep the light palette on a
        # dark window.
        configure_theme_from_preference()

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
        width = min(self.DEFAULT_WIDTH, screen.width() - 40)
        height = min(self.DEFAULT_HEIGHT, screen.height() - 60)
        x = max(20, (screen.width() - width) // 2)
        y = max(30, (screen.height() - height) // 2)
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(min(self.MIN_WIDTH, width), min(self.MIN_HEIGHT, height))

        # Common state

        self.log_queue: queue.Queue = queue.Queue()

        self.logger: logging.Logger | None = None

        self.widgets: dict[str, Any] = {}

        self.stat_counters: dict[str, int] = {"MS": 0, "MCS": 0, "SP": 0}

        self.undo_stack: deque = deque(maxlen=getattr(CFG, "UNDO_LIMIT", 50))

        self.detached_plot_windows: dict[str, DetachedPlotWindow] = {}

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

        self.install_common_affordances()

        # P2.2 - Trigger the onboarding tour on first launch (non-blocking).
        # The tour skips itself silently if the user already finished/skipped
        # it or if no step targets are resolvable. 600 ms gives the window
        # time to be fully laid out before the spotlight is positioned.
        QTimer.singleShot(600, self._maybe_run_first_time_tour)

        # Trigger Numba warmup after a short delay

        QTimer.singleShot(100, self._warmup_numba)

    def install_common_affordances(self) -> None:
        """Install everything a CERTUS window owes its user, independently of timers.

        Split out of _finalize_init on 2026-09-04. DESIGN, STRAT and RE
        deliberately skip _finalize_init because they own their warmup and
        timers - and in doing so they silently lost the command palette, the
        shortcuts overlay, the Help menu, the empty-state overlays and every
        accessible name. Measured that day, one process per module:

            module   Ctrl+K   Help menu   named fields
            DESIGN     no        no          0 / 58
            STRAT      no        no          0 / 59
            RE         no        no          0 /  6
            INDEX      yes       yes        18 / 18
            FIELD      yes       yes        21 / 21

        Idempotent: install_unique_shortcut skips a sequence already claimed, the
        Help menu checks for itself first, and the other calls overwrite nothing.
        Safe to call from a subclass that also reaches _finalize_init.
        """
        # U3: install Ctrl+K / Ctrl+Shift+P for the command palette.
        # U4: install F1 / Shift+? to open the keyboard-shortcuts overlay.
        # install_unique_shortcut skips a sequence already claimed by another
        # QShortcut or by a menu QAction: binding one twice makes Qt emit
        # activatedAmbiguously and run NEITHER handler.
        for seq, slot in (
            ("Ctrl+K", self.open_command_palette),
            ("Ctrl+Shift+P", self.open_command_palette),
            ("F1", self.open_shortcuts_overlay),
            ("Shift+?", self.open_shortcuts_overlay),
        ):
            sc = install_unique_shortcut(self, seq, slot)
            if sc is not None:
                self._command_palette_shortcuts.append(sc)

        # U5: install global zoom shortcuts for a more premium 2026 layout.
        try:
            self._zoom_factor = getattr(self, "_zoom_factor", 1.0)
            self._zoom_shortcuts = install_standard_shortcuts(
                self,
                zoom_in=self.zoom_in_ui,
                zoom_out=self.zoom_out_ui,
                reset_zoom=self.reset_ui_zoom,
            )
        except TypeError, RuntimeError, AttributeError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # U5b: reflect the current zoom level in the status bar for instant feedback.
        try:
            self._ensure_zoom_status_widget()
            self._update_zoom_status()
        except TypeError, RuntimeError, AttributeError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # P2.3 - Install the standard Help menu on every subclass (idempotent).
        try:
            mb = self.menuBar()
            if mb is not None:
                already_present = any((a.text() or "").replace("&", "").strip().lower() == "help" for a in mb.actions())
                if not already_present:
                    self.install_help_menu()
        except RuntimeError, AttributeError, TypeError:  # pragma: no cover - defensive
            pass

        # P1.3 - Auto-wire empty-state overlays on well-known table widgets.
        self._auto_install_empty_states()

        # P4 - Fill missing accessibility metadata on input widgets.
        self._apply_accessibility_defaults()

        # U6 - Universal drag-and-drop support for files
        try:
            self.setAcceptDrops(True)
        except TypeError, RuntimeError:
            pass

        # The keyboard must not open on an action. Measured 2026-09-05: every
        # window opened with the focus on a button - "Help", then "Save" once
        # Help was excluded, then FIELD's "Capture" - so Space fired something
        # nobody had chosen. Deferred, because the tab order is only settled once
        # the deferred layout timers have run.
        QTimer.singleShot(0, self._focus_first_input)

    def _focus_first_input(self) -> None:
        """Move the focus off any button and onto the first real input.

        Only acts when a BUTTON holds the focus: a window that placed the focus
        deliberately, or that legitimately starts on a scroll area, is left
        alone. Space on a scroll area scrolls; Space on a button runs something.
        """
        from PyQt6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox

        try:
            focused = self.focusWidget()
            if focused is not None and not isinstance(focused, QAbstractButton):
                return
            for candidate in self.findChildren((QLineEdit, QAbstractSpinBox, QComboBox)):
                if candidate.isVisible() and candidate.isEnabled() and candidate.focusPolicy() != Qt.FocusPolicy.NoFocus:
                    candidate.setFocus(Qt.FocusReason.OtherFocusReason)
                    return
        except RuntimeError, AttributeError, TypeError:  # pragma: no cover - window already gone
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _maybe_run_first_time_tour(self) -> None:
        """Best-effort: run the onboarding tour the first time only."""
        try:
            self.run_onboarding_tour(force=False)
        except RuntimeError, AttributeError, TypeError:  # pragma: no cover - defensive
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
                QWidget {{ font-size: {Typography.BODY_LG}pt; }}
                QGroupBox {{
                    font-weight: 700;
                    font-size: {Typography.BODY_LG}pt;
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
                QLabel#HeaderLabel {{ font-size: {Typography.H2}pt; font-weight: 800; color: {CertusTheme.TEXT_MAIN}; }}
                QPushButton {{ font-size: {Typography.BODY_LG}pt; padding: 5px 10px; border-radius: 10px; }}
                QComboBox {{ font-size: {Typography.BODY_LG}pt; padding: 3px 8px; border-radius: 10px; }}
                QDoubleSpinBox, QSpinBox {{ font-size: {Typography.BODY_LG}pt; padding: 3px 8px; border-radius: 10px; }}
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


    # --- Config Save/Load ---


    # --- Worker Management ---


    # --- Detached Plot Windows ---


    # --- Cleanup ---

    # --- Shared helpers migrated from CERTUS_RE / CERTUS_DESIGN ---


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

        # The control panel keeps the width it asks for; every extra pixel goes
        # to the plots. Without these two lines Qt splits the surplus evenly,
        # which cost CERTUS-INDEX 20 points of plot area (58.0 % -> 78.1 %,
        # measured 2026-09-03).
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes(self._get_default_splitter_sizes())
        attach_splitter_capper(main_splitter, max_ratio=0.34)

        # Status bar

        self._build_status_bar()

        # Initial theme application (Hook)

        self._apply_theme()

        # Propagate tooltips from spinboxes to inner lineEdits for complete accessibility coverage
        for _sb in self.findChildren(QAbstractSpinBox):
            _tt = _sb.toolTip()
            if _tt and _sb.lineEdit() and not _sb.lineEdit().toolTip():
                _sb.lineEdit().setToolTip(_tt)

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


    def eventFilter(self, obj, event) -> Any:
        """Filters events to handle Excel copy/paste"""

        # Not every subclass owns a front_table: the two METAL windows do not.
        # This raised AttributeError the first time an event filter was installed
        # on them (2026-09-04), and Qt reported it as an uncaught exception on
        # every single resize event.
        front_table = getattr(self, "front_table", None)
        if front_table is not None and obj == front_table and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._paste_from_excel()

                return True

        return super().eventFilter(obj, event)


    def closeEvent(self, event) -> None:
        """Clean up on close."""

        if not self.confirm_close_during_run(event):
            return

        self._qs_save()

        self._stop_all_workers()

        # Close detached windows

        for win in list(self.detached_plot_windows.values()):
            win.close()

        self.detached_plot_windows.clear()

        super().closeEvent(event)

    def dragEnterEvent(self, event) -> None:
        """Accept the drag-and-drop of configuration or measurement files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith((".json", ".csv", ".dat", ".txt", ".xlsx")) for url in urls):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        """Load automatically the file dropped on the interface."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_files = [
                url.toLocalFile()
                for url in urls
                if url.toLocalFile().lower().endswith((".json", ".csv", ".dat", ".txt", ".xlsx"))
            ]
            if valid_files:
                target_file = valid_files[0]
                event.acceptProposedAction()
                self._handle_dropped_file(target_file)
                return
        super().dropEvent(event)


