#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS HUB - Unified entry point for the CERTUS suite


=====================================================


Visually aligned with CERTUS-STRAT and certus_core/certus_ui standards.


Fixed: Header generation and Config loading robustness.


# ============================================================================
# 🛑 AI INSTRUCTION - P0 BOUNDARY 🛑
# This module must stay a pure launcher/composition layer. 
# DO NOT move scientific computation (`certus_physics`), service contracts, 
# or heavy workflow orchestration here.
# Keep the Hub lightweight and declarative.
# ============================================================================


"""


from typing import Any, TypedDict
import functools
import logging
import multiprocessing

from pathlib import Path


import sys


from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    __version__,
    certus_timestamp_display,
    configure_numba_env,
    create_module_environment,
    setup_module_logging,
)

#MUST remain the first call, before any import pulling Numba (physics, workers, ui).
#This function existed, was exported and tested, but was called NOWHERE:
# NUMBA_CACHE_DIR, NUMBA_NUM_THREADS, and NUMBA_THREADING_LAYER remained undefined.
#Measured consequences: Numba took all 16 cores (none reserved for OS/GUI) and the
#@njit(cache=True) cache was written next to the sources — thus in the
# Google Drive synchronized folder, causing repeated JIT recompilations.
#certus_core does not import Numba at module level: so the call here is on time.
configure_numba_env()


# =============================================================================


# LOGGING SETUP


# =============================================================================


logger = setup_module_logging("CERTUS_HUB")


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


bootstrap_env = create_module_environment(__file__, "CERTUS_HUB")


script_dir = bootstrap_env["script_dir"]


from certus.ui.certus_qt_widgets import (
    QApplication,
    QCheckBox,
    QColor,
    QFont,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProcess,
    QPushButton,
    QShortcut,
    QTextEdit,
    QTimer,
    Qt,
    QVBoxLayout,
    QWidget,
)


# Conditional SVG import for logo


from certus.core.certus_core import SVG_AVAILABLE


if SVG_AVAILABLE:
    from PyQt6.QtSvgWidgets import QSvgWidget


else:
    QSvgWidget = None


# =============================================================================


# MODULAR IMPORTS (Post-Refactoring 2026)


# =============================================================================


from certus.core.certus_core import get_export_config, get_resource_path, save_export_config, load_font_config, save_font_config


from certus.ui.certus_ui import (
    SVG_AVAILABLE,
    CertusTheme,
    CertusThemeToggle,
    init_certus_app,
    open_documentation,
    set_certus_window_icon,
    apply_certus_theme,
    CertusLogPanel,
)
from certus.ui.certus_ui_widgets_factory import (
    create_colored_label,
    create_header_logo_widget,
    create_styled_label,
)
from PyQt6.QtWidgets import QComboBox


# Styled buttons/labels - Now imported from certus.ui.certus_ui


# (create_styled_label & create_colored_label removed for DRY)


# get_base_path rm (use get_resource_path)


# =============================================================================


# UI COMPONENTS


# =============================================================================


from certus.core.certus_hub_config import HubAppCatalogItem, HUB_APP_CATALOG
from certus.ui.certus_hub_widgets import ModuleBadge, BaseApplicationCard, ApplicationCard, GroupedApplicationCard


class CertusHub(QMainWindow):
    @staticmethod
    def _build_hub_apps_catalog() -> list[HubAppCatalogItem]:
        """Return HUB application cards configuration.

        P1 boundary: keep this catalog declarative. Runtime launch behavior belongs
        to the launcher methods, and scientific workflow metadata belongs to the
        target applications or service layer.
        """
        return list(HUB_APP_CATALOG)

    @staticmethod
    def _hub_export_checkbox_stylesheet() -> str:
        """Return shared style for HUB export toggle."""
        return f"""
            QCheckBox {{ 
                color: {CertusTheme.TEXT_MAIN}; 
                spacing: {CertusTheme.SPACING_MD}px; 
                font-weight: {CertusTheme.FONT_WEIGHT_MEDIUM};
                font-family: {CertusTheme.FONT_FAMILY};
            }}
            QCheckBox::indicator {{ 
                width: 18px; 
                height: 18px; 
                border-radius: {CertusTheme.RADIUS_SM}px; 
                border: 1.5px solid {CertusTheme.BORDER}; 
                background: {CertusTheme.BACKGROUND}; 
            }}
            QCheckBox::indicator:checked {{ 
                background-color: {CertusTheme.PRIMARY}; 
                border-color: {CertusTheme.PRIMARY}; 
            }}
            QCheckBox::indicator:hover {{
                border-color: {CertusTheme.PRIMARY};
            }}
        """

    def __init__(self) -> None:
        """

        Initialize the CERTUS Hub main window.

        This method sets up the main application window including:

        - Window properties (title, size, minimum size)

        - UI components and layout

        - Module connections and integrations

        - Event handlers and signals

        Args:

            self: CertusHub instance

        Returns:

            None

        Notes:

            - Main entry point for the CERTUS Suite

            - Integrates all CERTUS modules

            - Provides unified interface for all tools

        """

        super().__init__()

        self.setWindowTitle("CERTUS-HUB - Calculated Error Reduction Through Unbiased Simulation")

        self.resize(800, 600)

        self.setMinimumSize(700, 500)

        self.active_processes = []

        # Global Background Style 2026 (Handled properly in _apply_theme now)


        set_certus_window_icon(self)

        # Keyboard shortcuts for quick module launch

        self._setup_shortcuts()

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        # Main layout

        main_layout = QVBoxLayout(central_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        # --- 1. HEADER (Style 2026) ---

        # Use create_header_logo_widget for consistency

        header_widget = create_header_logo_widget(
            "CERTUS HUB", "Unified Optical Suite", logo_width=200, module_name="HUB"
        )

        # Theme toggle injected into the header (right side) for consistency across CERTUS suite

        self.btn_theme = CertusThemeToggle(header_widget)
        
        self.cmb_font = QComboBox(header_widget)
        self.cmb_font.addItems(["Default", "Gemini", "iOS (San Francisco)", "Roboto", "Open Sans", "Inter"])
        self.cmb_font.setCurrentText(load_font_config())
        self.cmb_font.currentTextChanged.connect(self.on_font_changed)
        self.cmb_font.setToolTip("Choose the global font")
        self.cmb_font.setStyleSheet(f"""
            QComboBox {{
                background-color: {CertusTheme.SURFACE};
                border: 1px solid {CertusTheme.BORDER};
                border-radius: 4px;
                padding: 4px;
                min-width: 150px;
                color: {CertusTheme.TEXT_MAIN};
            }}
        """)

        header_widget.layout().addWidget(self.cmb_font)
        header_widget.layout().addWidget(self.btn_theme)

        main_layout.addWidget(header_widget)

        # --- 2. CONTENT AREA (Style 2026) ---

        from PyQt6.QtWidgets import QScrollArea
        content_area = QScrollArea()
        content_area.setWidgetResizable(True)
        content_area.setFrameShape(QFrame.Shape.NoFrame)
        content_area.setStyleSheet("background: transparent;")
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_area.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)

        # Spacing Style 2026

        content_layout.setContentsMargins(
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_SM,
            CertusTheme.SPACING_XL,
            CertusTheme.SPACING_MD,
        )

        grid_layout = QGridLayout()

        grid_layout.setSpacing(CertusTheme.SPACING_MD)

        grid_wrapper = QHBoxLayout()

        grid_wrapper.addStretch()

        grid_wrapper.addLayout(grid_layout)

        grid_wrapper.addStretch()

        # Module definitions
        self.apps = self._build_hub_apps_catalog()

        MAX_COLS = 3  # 3x3 Grid (9 modules)

        for idx, app in enumerate(self.apps):
            if app.get("type") == "group":
                card = GroupedApplicationCard(
                    app["title"],
                    app["icon"],
                    app["color"],
                    app["sub_apps"],
                    app["badge"],
                )

                card.launch_callback = self.launch_module

            else:
                card = ApplicationCard(
                    app["title"],
                    app["sub"],
                    app["desc"],
                    app["script"],
                    app["icon"],
                    app["color"],
                    app["badge"],
                )

                card.mousePressEvent = lambda e, s=app["script"]: self.launch_module(s)

            # P1.4 - apply hover-lift + fade-in micro-animations on each card.
            # self._apply_card_animations(card, index=idx)

            row = idx // MAX_COLS

            col = idx % MAX_COLS

            grid_layout.addWidget(card, row, col)

        content_layout.addLayout(grid_wrapper)

        content_layout.addStretch()

        # --- 3. BOTTOM BAR (Style 2026) ---

        bottom_bar = QWidget()

        bottom_bar.setStyleSheet(f"""

            border-top: 1px solid {CertusTheme.BORDER}; 

            background-color: {CertusTheme.SURFACE};

        """)

        bb_layout = QHBoxLayout(bottom_bar)

        bb_layout.setContentsMargins(
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_LG,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_LG,
        )

        # Config Group

        config_group = QWidget()

        cg_layout = QHBoxLayout(config_group)

        cg_layout.setContentsMargins(0, 0, 0, 0)

        # --- Auto Export Toggle ---

        _chk_style = self._hub_export_checkbox_stylesheet()

        auto_export_val = get_export_config()

        self.chk_export = QCheckBox("Auto Export Reports")

        self.chk_export.setChecked(auto_export_val)

        self.chk_export.setToolTip("Automatically generate Excel/HTML reports after calculationation.")

        self.chk_export.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE))

        self.chk_export.setStyleSheet(_chk_style)

        self.chk_export.stateChanged.connect(self.on_export_changed)

        cg_layout.addWidget(self.chk_export)

        bb_layout.addWidget(config_group)

        bb_layout.addStretch()

        # Documentation Button style 2026

        self.btn_docs = QPushButton(" Scientific Documentation")
        try:
            from certus.utils.certus_ux import OBJ

            self.btn_docs.setObjectName(OBJ.PRIMARY_BUTTON)
        except ImportError:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.btn_docs.setToolTip("Open the full scientific documentation for the CERTUS suite (HTML reference).")

        # Try loading icon

        icon_path = get_resource_path("icons/book.svg")

        if Path(icon_path).exists():
            self.btn_docs.setIcon(QIcon(icon_path))

        self.btn_docs.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_docs.setFixedHeight(40)

        self.btn_docs.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 1))

        self.btn_docs.clicked.connect(self.open_documentation)

        bb_layout.addWidget(self.btn_docs)

        main_layout.addWidget(content_area)

        # P0.4 - Recent configs strip (opt-in wired here)
        self.attach_recent_files_strip(parent_layout=main_layout, limit=6)

        main_layout.addWidget(bottom_bar)

        # P0.4 / P2.3 - install a Help menu bar (consistent with sub-apps)
        self._install_help_menu()

        # Log Container (toggleable)

        self.log_panel = CertusLogPanel(title="PROCESS LAUNCH LOGS", visible=False, height=150, parent=self)

        self.log_container = self.log_panel

        self.log_text = self.log_panel.log_text

        main_layout.addWidget(self.log_panel)

        # Show Details Button (add to bottom bar)

        self.btn_details = QPushButton("Show Details")

        self.btn_details.setCheckable(True)

        self.btn_details.setStyleSheet(f"""

            QPushButton {{ background: transparent; color: {CertusTheme.TEXT_SUB}; border: 1px solid {CertusTheme.BORDER}; padding: 5px 10px; border-radius: 4px; }}

            QPushButton:checked {{ background: {CertusTheme.SURFACE_HOVER}; color: {CertusTheme.PRIMARY}; border-color: {CertusTheme.PRIMARY}; }}

            QPushButton:hover {{ background: {CertusTheme.SURFACE_HOVER}; }}

        """)

        self.btn_details.setToolTip("Show or hide the process launch log panel.")

        self.btn_details.clicked.connect(self.on_toggle_details)

        bb_layout.insertWidget(bb_layout.count() - 2, self.btn_details)  # Insert before stretch/docs

        # Active modules indicator

        self.lbl_active = create_styled_label("", style="normal", color=CertusTheme.SUCCESS)

        self.lbl_active.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 1))

        self.lbl_active.setVisible(False)

        bb_layout.insertWidget(0, self.lbl_active)

        # Theme toggle now lives in the header (see above) for UX consistency.

        # Footer Style 2026

        import platform

        from PyQt6.QtCore import QT_VERSION_STR

        footer_text = f"© 2024-2026 CERTUS Scientific Suite v{__version__} • Python {sys.version.split()[0]} ({platform.architecture()[0]}) • Qt {QT_VERSION_STR}"

        footer = create_styled_label(footer_text, style="caption")

        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE - 1))

        footer.setObjectName("HubFooter")

        main_layout.addWidget(footer)

        # Apply initial theme

        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply global theme styles including Premium UI"""

        overrides = f"""
            /* Hub specific overrides */
            #HubFooter {{ 
                color: {CertusTheme.TEXT_SUB}; 
                font-size: 9px; 
                padding: {CertusTheme.SPACING_MD}px; 
                background-color: {CertusTheme.BACKGROUND}; 
                border-top: 1px solid {CertusTheme.BORDER}; 
            }}
        """
        
        apply_certus_theme(self, overrides=overrides)

    def on_font_changed(self, font_name: str) -> None:
        """Called when font selection changes"""
        save_font_config(font_name)
        # Apply theme app-wide
        app = QApplication.instance()
        if app:
            from certus.ui.certus_theme import CertusTheme
            CertusTheme.apply_to_app(app, dark_mode=CertusTheme.DARK_MODE)
        self._apply_theme()

    def _get_app_metadata(self, app_name: str) -> HubAppCatalogItem | None:
        """Return declarative metadata for a launcher entry if known."""
        base_name = Path(app_name).stem
        for item in self.apps:
            if Path(str(item.get("script", ""))).stem == base_name:
                return item
        return None

    def launch_module(self, app_name: str) -> None:

        # Use get_resource_path to get base dir

        base_dir = get_resource_path("")

        app_meta = self._get_app_metadata(app_name)

        if app_meta is not None:
            module_category = str(app_meta.get("category", "unknown"))
            module_contract = str(app_meta.get("contract", "unknown"))
        else:
            module_category = "unknown"
            module_contract = "unknown"

        base_name = Path(app_name).stem

        if getattr(sys, "frozen", False):
            program = str(Path(base_dir) / (base_name + (".exe" if sys.platform == "win32" else "")))

            args = []

        else:
            program = sys.executable

            script_path = Path(base_dir) / app_name

            args = [str(script_path)]

            if not script_path.exists():
                QMessageBox.critical(self, "Error", f"Script not found: {script_path}")

                return

        process = QProcess(self)

        process.setProgram(program)

        process.setArguments(args)

        # Set working directory for relative paths (logs/configs)

        process.setWorkingDirectory(base_dir)

        process.finished.connect(lambda c, s, p=process, n=app_name: self.on_process_finished(p, n, c))

        # Handle process lifecycle signals asynchronously
        module_name = Path(app_name).stem

        def on_started(n=module_name):
            self._log_message(f"{n} started successfully.")

        def on_error(err, n=module_name, p=process):
            self._log_message(f"ERROR: Failed to start {n} (Error: {err})")
            if p in self.active_processes:
                self.active_processes.remove(p)
            self._update_active_indicator()
            QMessageBox.warning(
                self,
                "Launch Error",
                f"Could not start {n}.\nPlease check that the module exists.",
            )

        process.started.connect(on_started)
        process.errorOccurred.connect(on_error)

        # Log launch info

        if app_meta is not None:
            self._log_message(
                f"Launching {module_name} [{module_category} | {module_contract}]..."
            )
        else:
            self._log_message(f"Launching {module_name}...")

        self.active_processes.append(process)

        process.start()

        self._update_active_indicator()

    def open_documentation(self) -> None:
        """Opens CERTUS_HUB documentation"""

        open_documentation("CERTUS_HUB")

    def on_export_changed(self, state) -> None:

        enabled = state == Qt.CheckState.Checked.value

        try:
            save_export_config(enabled)

        except (OSError, IOError, PermissionError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def on_process_finished(self, process, app_name, exit_code) -> None:

        module_name = Path(app_name).stem

        if process in self.active_processes:
            self.active_processes.remove(process)

        stderr_text = ""
        if process is not None:
            try:
                stderr_text = process.readAllStandardError().data().decode("utf-8", errors="replace")
            except RuntimeError:
                stderr_text = ""

        if process is not None:
            try:
                process.deleteLater()
            except RuntimeError:
                pass

        self._update_active_indicator()

        if exit_code == 0:
            self._log_message(f"{module_name} exited normally.")

        elif exit_code not in (1, 15, -1):  # Ignore common force-close codes
            self._log_message(f"{module_name} exited with code {exit_code}")

            if stderr_text:
                self._log_message(f"Error: {stderr_text[:200]}")

        if process in self.active_processes and process.state() != QProcess.ProcessState.Running:
            try:
                process.deleteLater()
            except RuntimeError:
                pass

    def on_toggle_details(self, checked) -> None:

        self.log_container.setVisible(checked)

    def _update_active_indicator(self) -> None:
        """Update the active modules indicator in the status bar."""

        if not hasattr(self, "lbl_active") or self.lbl_active is None:
            return

        n = len(self.active_processes)

        try:
            if n > 0:
                self.lbl_active.setText(f"● {n} module{'s' if n > 1 else ''} running")

                self.lbl_active.setVisible(True)

            else:
                self.lbl_active.setVisible(False)
        except RuntimeError:
            return

    def closeEvent(self, event) -> None:
        """Stop child processes cleanly before the hub is destroyed."""
        import time

        start_time = time.time()
        timeout_s = 1.5

        # 1. Ask all processes to terminate in parallel
        for process in list(self.active_processes):
            try:
                if process is not None and process.state() != QProcess.ProcessState.NotRunning:
                    process.terminate()
            except RuntimeError:
                pass
            except Exception as e:
                self._log_message(f"Warning: Error terminating process: {e}")

        # 2. Wait for all processes within the shared deadline
        for process in list(self.active_processes):
            try:
                if process is not None and process.state() != QProcess.ProcessState.NotRunning:
                    elapsed = time.time() - start_time
                    remaining_ms = int(max(0, timeout_s - elapsed) * 1000)
                    if remaining_ms > 0:
                        process.waitForFinished(remaining_ms)
            except RuntimeError:
                pass

        # 3. Force kill any remaining active processes
        for process in list(self.active_processes):
            try:
                if process is not None and process.state() != QProcess.ProcessState.NotRunning:
                    process.kill()
                    process.waitForFinished(500)
            except RuntimeError:
                pass

        self.active_processes.clear()
        super().closeEvent(event)

    def _log_message(self, msg) -> None:
        """Add a timestamped message to the log panel."""

        if not hasattr(self, "log_text") or self.log_text is None:
            return

        try:
            self.log_text.append(f"[{certus_timestamp_display()}] {msg}")
        except RuntimeError:
            return

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts for quick module launch."""

        shortcuts = [
            ("Ctrl+D", "CERTUS_DESIGN.py", "Launch DESIGN"),
            ("Ctrl+Shift+S", "CERTUS_STRAT.py", "Launch STRAT"),
            ("Ctrl+I", "CERTUS_INDEX.py", "Launch INDEX"),
            ("Ctrl+M", "CERTUS_METAL_SINGLE.py", "Launch METAL"),
            ("Ctrl+F", "CERTUS_FIELD.py", "Launch FIELD"),
            ("Ctrl+Plus", None, "Zoom in"),
            ("Ctrl+Minus", None, "Zoom out"),
            ("Ctrl+0", None, "Reset zoom"),
            ("F1", None, "Open Documentation"),
        ]

        for key, script, desc in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)

            if script:
                shortcut.activated.connect(functools.partial(self.launch_module, script))

            elif key == "Ctrl+Plus":
                shortcut.activated.connect(lambda: self._log_message("Zoom shortcut reserved for child windows"))

            elif key == "Ctrl+Minus":
                shortcut.activated.connect(lambda: self._log_message("Zoom shortcut reserved for child windows"))

            elif key == "Ctrl+0":
                shortcut.activated.connect(lambda: self._log_message("Zoom reset reserved for child windows"))

            else:
                shortcut.activated.connect(self.open_documentation)

            shortcut.setWhatsThis(desc)

    # =========================================================================

    # U5+ - Recent files strip (opt-in, additive; does not alter default UI)

    # =========================================================================

    def attach_recent_files_strip(self, parent_layout=None, *, limit: int = 5) -> Any:
        """Instantiate and return a recent-configs strip.

        This is an **opt-in** helper: calling code passes the layout where

        the strip should be inserted (e.g. the main dashboard layout, a

        sidebar, or the status bar). If ``parent_layout`` is ``None`` the

        widget is created, parented to the hub, and returned without

        being added anywhere, letting callers place it manually.

        Returns ``None`` if the recent-strip module is unavailable.

        """

        try:
            from certus.ui.certus_recent_strip import build_recent_files_strip

        except ImportError as e:  # pragma: no cover - defensive
            self._log_message(f"Recent strip unavailable: {e}")

            return None

        strip = build_recent_files_strip(
            self,
            limit=limit,
            on_open=self._on_recent_config_selected,
        )

        if strip is None:
            return None

        if parent_layout is not None:
            try:
                parent_layout.addWidget(strip)

            except (AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
                self._log_message(f"Recent strip insert failed: {e}")

        return strip

    def _on_recent_config_selected(self, path: str) -> None:
        """Callback when the user clicks a recent-file pill."""

        self._log_message(f"Recent file selected: {path}")

    # =========================================================================

    # P2.3 - Help menu (uniform entry points across the suite)

    # =========================================================================

    def _install_help_menu(self) -> None:
        """Create the standard Help menu: Shortcuts, Docs, About."""

        try:
            mb = self.menuBar()

            help_menu = mb.addMenu("&Help")

            act_shortcuts = help_menu.addAction("Keyboard shortcuts…")

            act_shortcuts.setShortcut("F1")

            act_shortcuts.triggered.connect(self._open_shortcuts_overlay)

            act_zoom_in = help_menu.addAction("Zoom in")
            act_zoom_in.setShortcut("Ctrl+Plus")
            act_zoom_in.triggered.connect(lambda: self._log_message("Zoom in is handled in child windows"))

            act_zoom_out = help_menu.addAction("Zoom out")
            act_zoom_out.setShortcut("Ctrl+Minus")
            act_zoom_out.triggered.connect(lambda: self._log_message("Zoom out is handled in child windows"))

            act_zoom_reset = help_menu.addAction("Reset zoom")
            act_zoom_reset.setShortcut("Ctrl+0")
            act_zoom_reset.triggered.connect(lambda: self._log_message("Reset zoom is handled in child windows"))

            help_menu.addSeparator()

            act_docs = help_menu.addAction("Open documentation…")

            act_docs.triggered.connect(self.open_documentation)

            help_menu.addSeparator()

            act_about = help_menu.addAction("About CERTUS…")

            act_about.triggered.connect(self._show_about_dialog)

        except (AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
            self._log_message(f"Help menu install failed: {e}")

    def _open_shortcuts_overlay(self) -> None:
        """Delegate to certus_shortcuts_overlay if available."""

        try:
            from certus.ui.certus_shortcuts_overlay import open_shortcuts_overlay

            open_shortcuts_overlay(self)

        except (ImportError, AttributeError, RuntimeError, TypeError) as e:
            self._log_message(f"Shortcuts overlay unavailable: {e}")

    def _show_about_dialog(self) -> None:
        """Minimal About dialog."""

        try:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.about(
                self,
                "About CERTUS",
                "<b>CERTUS HUB</b><br>Unified Optical Suite<br><br>"
                "Version 2026 - All suite apps accessible from a single dashboard.<br>"
                "Press <code>F1</code> for keyboard shortcuts.",
            )

        except (ImportError, AttributeError, RuntimeError, TypeError) as e:  # pragma: no cover - defensive
            self._log_message(f"About dialog failed: {e}")

    # =========================================================================

    # P1.4 - Card micro-animations (hover lift + staggered fade-in)

    # =========================================================================

    def _apply_card_animations(self, card, *, index: int) -> None:
        """Attach hover-lift and a staggered fade-in on an HUB card."""

        try:
            from certus.ui.certus_animations import fade_in, hover_lift

        except ImportError:
            return

        try:
            hover_lift(card, lift_px=3)

        except (AttributeError, RuntimeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        # Stagger the fade-in so cards appear sequentially (~60 ms apart).

        try:
            from PyQt6.QtCore import QTimer

            delay_ms = 60 * int(index)

            # Targeted fade-in on content to avoid replacing the card's shadow effect

            target = getattr(card, "content_container", card)

            QTimer.singleShot(delay_ms, lambda: fade_in(target, duration_ms=220))

        except (ImportError, AttributeError, RuntimeError, TypeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)


# =============================================================================


# SPLASH & ENTRY POINT


# =============================================================================


class SplashScreen(QWidget):
    """Splash screen (CERTUS 2026)"""

    def __init__(self) -> None:

        super().__init__()

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(650, 380)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()

        container.setStyleSheet(f"""

            background-color: {CertusTheme.BACKGROUND}; 

            border: 2px solid {CertusTheme.PRIMARY}; 

            border-radius: {CertusTheme.RADIUS_XL}px;

        """)

        # Shadow Style 2026

        shadow = CertusTheme.get_shadow()

        shadow.setBlurRadius(30)

        shadow.setColor(QColor(0, 0, 0, 50))

        shadow.setOffset(0, 6)

        container.setGraphicsEffect(shadow)

        l = QVBoxLayout(container)

        l.setContentsMargins(
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
            CertusTheme.SPACING_XL * 2,
        )

        l.setSpacing(CertusTheme.SPACING_LG)

        # CERTUS SVG Logo - Try multiple paths

        logo_widget = None

        logo_paths = [
            get_resource_path("certus.svg"),  # Horizontal format (priority, used by create_header_logo_widget)
            get_resource_path("certus_logo.svg"),
            get_resource_path("images/certus_logo.svg"),
            get_resource_path("images/certus.svg"),
        ]

        for logo_path in logo_paths:
            if SVG_AVAILABLE and QSvgWidget and Path(logo_path).exists():
                try:
                    logo_widget = QSvgWidget(logo_path)

                    logo_widget.setFixedSize(400, 85)  # Ratio adapted for splash

                    l.addWidget(logo_widget, alignment=Qt.AlignmentFlag.AlignCenter)

                    break

                except NUMERICAL_FAULT_EXCEPTIONS as e:
                    logging.debug(f"Error loading SVG logo {logo_path}: {e}")

                    logo_widget = None

        # Fallback if SVG logo unavailable

        if logo_widget is None:
            icon_label = QLabel("💠")

            icon_label.setFont(CertusTheme.get_font(50))

            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label.setStyleSheet(f"color: {CertusTheme.PRIMARY};")

            l.addWidget(icon_label)

            title = create_styled_label("CERTUS", style="bold")

            title.setFont(CertusTheme.get_font(52))

            title.setStyleSheet(f"color: {CertusTheme.TEXT_MAIN};")

            title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            l.addWidget(title)

        sub = create_styled_label("HUB INITIALIZATION", style="subtitle", color=CertusTheme.PRIMARY)

        sub.setFont(CertusTheme.get_font(CertusTheme.FONT_SIZE_BASE + 3))

        sub.setStyleSheet(f"""
            color: {CertusTheme.PRIMARY}; 
        """)

        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        l.addWidget(sub)

        l.addStretch()

        layout.addWidget(container)


class CertusApp:
    def __init__(self) -> None:

        # High DPI scaling (Must be set BEFORE creating QApplication)

        if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
            if not QApplication.instance():
                QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        self.app = QApplication(sys.argv)

        # Init theme via COMMON if available (silent mode)

        try:
            if "init_certus_app" in globals():
                init_certus_app("CERTUS Hub", app=self.app)

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        self.splash = SplashScreen()

        self.hub = None

    def start(self) -> Any:

        self.splash.show()

        # Screen centering

        geo = self.splash.frameGeometry()

        try:
            cp = self.app.primaryScreen().availableGeometry().center()

            geo.moveCenter(cp)

            self.splash.move(geo.topLeft())

        except (AttributeError, RuntimeError):
            # Screen geometry may not be available in some environments

            pass

        QTimer.singleShot(1200, self.show_hub)

        return self.app.exec()

    def show_hub(self) -> None:

        self.hub = CertusHub()

        self.hub.show()

        self.splash.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    manager = CertusApp()

    sys.exit(manager.start())
