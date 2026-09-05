"""
CERTUS UI - Base App Mixins

Extracted to follow SRP and Top 1% architecture standards.
These mixins provide discrete capabilities to the CertusBaseApp without
cluttering the main application logic.
"""

import functools
import logging
from typing import Any, Optional

from PyQt6.QtCore import QSettings, QTimer, Qt
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication

from certus.ui.certus_theme import CertusTheme, get_standard_stylesheet
from certus.ui.certus_ui_utils import (
    claim_shortcut_for_action,
    install_standard_shortcuts,
    show_toast,
    update_global_plot_config,
)
from certus.core.certus_core import load_theme_config, save_theme_config
import certus.ui.certus_io_ui as certus_io_ui


class CertusZoomMixin:
    """Provides global UI zooming capabilities for modern 2026 layouts."""

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
        if hasattr(self, "status_bar"):
            self.status_bar.addPermanentWidget(label)
        self._zoom_status_label = label

    def _update_zoom_status(self, factor: Optional[float] = None, announce: bool = True) -> None:
        label = getattr(self, "_zoom_status_label", None)
        if label is not None:
            current = getattr(self, "_zoom_factor", 1.0) if factor is None else factor
            label.setText(self._zoom_feedback_text(current))
        if announce and factor is not None:
            try:
                show_toast(self, self._zoom_feedback_text(factor), "info", duration_ms=1200)
            except RuntimeError, AttributeError, TypeError, ValueError:
                pass

    def _store_ui_zoom(self) -> None:
        try:
            qs = QSettings("CERTUS", getattr(self, "APP_NAME", "CERTUS"))
            qs.setValue(self._qs_key("uiZoom"), float(getattr(self, "_zoom_factor", 1.0)))
        except AttributeError, RuntimeError, TypeError, ValueError:
            pass

    def _restore_ui_zoom(self) -> None:
        try:
            qs = QSettings("CERTUS", getattr(self, "APP_NAME", "CERTUS"))
            value = qs.value(self._qs_key("uiZoom"), 1.0)
            self._zoom_factor = max(0.85, min(1.30, float(value)))
            base_pt = getattr(CertusTheme, "FONT_SIZE_BASE", 10)
            app = QApplication.instance()
            if app is not None:
                app.setFont(QFont("Segoe UI", max(9, round(base_pt * self._zoom_factor))))
        except AttributeError, RuntimeError, TypeError, ValueError:
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
        self.setMinimumSize(
            int(getattr(self, "MIN_WIDTH", 800) * factor), int(getattr(self, "MIN_HEIGHT", 600) * factor)
        )
        self._store_ui_zoom()
        try:
            scale = factor / previous if previous else 1.0
            self.resize(
                max(self.minimumWidth(), int(self.width() * scale)),
                max(self.minimumHeight(), int(self.height() * scale)),
            )
        except AttributeError, RuntimeError, TypeError, ZeroDivisionError:
            pass
        if hasattr(self, "statusBar") and callable(getattr(self, "statusBar")):
            try:
                self.statusBar().setStyleSheet(CertusTheme.get_status_bar_stylesheet())
            except AttributeError, RuntimeError, TypeError:
                pass
        self._update_zoom_status(factor, announce=True)


class CertusCommandPaletteMixin:
    """Manages the command palette, help menus, and action discovery."""

    def register_command(self, action: Any) -> None:
        if getattr(self, "_commands", None) is None:
            self._commands = list(self._default_commands())
        self._commands = [a for a in self._commands if getattr(a, "id", None) != action.id]
        self._commands.append(action)

    def _default_commands(self) -> list[Any]:
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
            try:
                recents = self.list_recent_configs(limit=1) if hasattr(self, "list_recent_configs") else []
            except RuntimeError, AttributeError, TypeError, ValueError:
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
        if hasattr(self, "zoom_in_ui"):
            actions.append(
                CommandAction(
                    id="view.zoom_in",
                    title="Zoom in",
                    subtitle="Increase the interface scale for readability",
                    shortcut="Ctrl++",
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
                    shortcut="Ctrl+-",
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
        if hasattr(self, "open_shortcuts_overlay"):
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
        auto = getattr(self, "_auto_discovered_commands", None)
        if callable(auto):
            actions.extend(auto())
        return actions

    def _auto_discovered_commands(self) -> list[Any]:
        try:
            from certus.utils.certus_command_palette import CommandAction
        except ImportError:
            return []

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
        try:
            mode = load_theme_config()
            new_mode = "dark" if mode == "light" else "light"
            save_theme_config(new_mode)
            CertusTheme.configure(new_mode)
            app = QApplication.instance()
            if app is not None:
                CertusTheme.apply_to_app(app, new_mode == "dark")
            update_global_plot_config(new_mode == "dark")
            if hasattr(self, "_apply_theme"):
                self._apply_theme()
            try:
                from certus.ui.certus_icons import clear_icon_cache

                clear_icon_cache()
            except ImportError, AttributeError:
                pass
        except RuntimeError, AttributeError, TypeError, ValueError, OSError:
            if getattr(self, "logger", None):
                self.logger.exception("Theme toggle failed")

    def open_command_palette(self) -> None:
        try:
            from certus.utils.certus_command_palette import open_command_palette

            if getattr(self, "_commands", None) is None:
                self._commands = list(self._default_commands())
            open_command_palette(self, list(self._commands))
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            if getattr(self, "logger", None):
                self.logger.exception("Command palette failed to open")

    def open_shortcuts_overlay(self) -> None:
        try:
            from certus.ui.certus_shortcuts_overlay import open_shortcuts_overlay

            open_shortcuts_overlay(self)
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            if getattr(self, "logger", None):
                self.logger.exception("Shortcuts overlay failed to open")

    def install_help_menu(self, *, app_label: Optional[str] = None) -> None:
        try:
            mb = self.menuBar()
            if mb is None:
                return
            help_menu = mb.addMenu("&Help")

            # A menu QAction and a bare QShortcut bound to the same sequence make
            # Qt emit activatedAmbiguously and run NEITHER. claim_shortcut_for_action
            # assigns the sequence to the menu entry ONLY when no QShortcut already
            # owns it on this window, so the two never compete.
            # Note: "Ctrl+Plus" / "Ctrl+Minus" resolve to an EMPTY QKeySequence on
            # Qt 6 - the menu entry would display no shortcut at all. The command
            # palette declared exactly those two until 2026-09-05 and printed them
            # verbatim, so it advertised a key the operator cannot type.
            def _menu_action(label: str, seq: str | None, slot) -> None:
                act = help_menu.addAction(label)
                if seq:
                    claim_shortcut_for_action(act, seq, self)
                act.triggered.connect(slot)

            _menu_action("Command palette…", "Ctrl+K", self.open_command_palette)
            _menu_action("Keyboard shortcuts…", "F1", self.open_shortcuts_overlay)

            if hasattr(self, "zoom_in_ui"):
                _menu_action("Zoom in", "Ctrl++", self.zoom_in_ui)
                _menu_action("Zoom out", "Ctrl+-", self.zoom_out_ui)
                _menu_action("Reset zoom", "Ctrl+0", self.reset_ui_zoom)

            help_menu.addSeparator()

            if hasattr(self, "open_help"):
                act_docs = help_menu.addAction("Open documentation…")
                act_docs.triggered.connect(self.open_help)

            help_menu.addSeparator()
            act_tour = help_menu.addAction("Start guided tour")
            act_tour.triggered.connect(functools.partial(self.run_onboarding_tour, force=True))
            act_reset_tour = help_menu.addAction("Reset onboarding state")
            act_reset_tour.triggered.connect(self.reset_onboarding_tour)
            help_menu.addSeparator()

            act_about = help_menu.addAction("About CERTUS…")
            act_about.triggered.connect(functools.partial(self._show_default_about_dialog, app_label))
        except RuntimeError, AttributeError, TypeError, ValueError:
            pass

    def _show_default_about_dialog(self, app_label: Optional[str] = None) -> None:
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
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            pass

    def run_onboarding_tour(self, *, force: bool = False) -> str:
        try:
            from certus.ui.certus_tours_catalog import run_app_onboarding

            return run_app_onboarding(self, force=force)
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            return "empty"

    def reset_onboarding_tour(self) -> None:
        try:
            from certus.ui.certus_onboarding import reset_onboarding

            reset_onboarding(getattr(self, "APP_NAME", "CERTUS"))
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            pass

    def _apply_accessibility_defaults(self) -> int:
        try:
            from certus.ui.certus_a11y import apply_accessibility_defaults

            return apply_accessibility_defaults(self, label_map=getattr(self, "_A11Y_LABEL_MAP", {}))
        except ImportError, RuntimeError, AttributeError, TypeError, ValueError:
            return 0


class CertusPremiumExportMixin:
    """Manages high-quality PDF/Excel exports and metadata tracking."""

    def _default_report_context(self) -> Any:
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
        return None

    def set_validation_status(self, status: str) -> None:
        try:
            from certus.core.certus_metrology import ValidationStatus

            self.validation_status = ValidationStatus(str(status)).value
        except RuntimeError, AttributeError, TypeError, ValueError:
            self.validation_status = str(status)

    def add_validation_warning(self, warning: str) -> None:
        msg = str(warning).strip()
        if not msg:
            return
        cur = getattr(self, "validation_warnings", None)
        if not isinstance(cur, list):
            cur = []
        cur.append(msg)
        self.validation_warnings = cur

    def export_premium_excel(
        self, sections: list, output_path: Optional[str] = None, *, ctx: Any = None
    ) -> Optional[str]:
        try:
            from certus.utils.certus_reports import build_excel_report
        except ImportError:
            if hasattr(self, "log"):
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
            if hasattr(self, "log"):
                self.log(f"Excel report saved: {out}", "SUCCESS")
            return out
        except Exception as e:
            if hasattr(self, "log"):
                self.log(f"Excel export failed: {e}", "ERROR")
            if getattr(self, "logger", None):
                self.logger.exception("Excel export failed")
            return None

    def export_premium_pdf(
        self, sections: list, output_path: Optional[str] = None, *, ctx: Any = None
    ) -> Optional[str]:
        try:
            from certus.utils.certus_reports import build_pdf_report
        except ImportError:
            if hasattr(self, "log"):
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
            if hasattr(self, "log"):
                self.log(f"PDF report saved: {out}", "SUCCESS")
            return out
        except Exception as e:
            if hasattr(self, "log"):
                self.log(f"PDF export failed: {e}", "ERROR")
            if getattr(self, "logger", None):
                self.logger.exception("PDF export failed")
            return None

    def _build_report_sections(self) -> list:
        return []

    def export_report_excel(self) -> Optional[str]:
        return self.export_premium_excel(self._build_report_sections())

    def export_report_pdf(self) -> Optional[str]:
        return self.export_premium_pdf(self._build_report_sections())


class CertusEmptyStateMixin:
    """Provides automatic empty state injections for data tables."""

    _EMPTY_STATE_HINTS: dict[str, tuple[str, str, str, Optional[str]]] = {
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
        try:
            from certus.ui.certus_empty_state import attach_empty_state_to
        except ImportError:
            return

        for attr, (icon, title, desc, cta_label) in self._EMPTY_STATE_HINTS.items():
            widget = getattr(self, attr, None)
            if widget is None or not hasattr(widget, "model"):
                continue
            on_action = None
            if cta_label:
                cb = getattr(self, "add_layer" if "layer" in cta_label.lower() else "add_target", None)
                if callable(cb):
                    on_action = cb
                else:
                    cta_label = None
            try:
                attach_empty_state_to(
                    widget,
                    icon_name=icon,
                    title=title,
                    description=desc,
                    action_label=cta_label,
                    on_action=on_action,
                )
            except RuntimeError, AttributeError, TypeError, ValueError:
                pass


class CertusRecentsMixin:
    """Provides recent files management."""

    def _record_recent_config(self, filename: str) -> None:
        if not filename:
            return
        try:
            from certus.ui.certus_recent import RecentCategories, record_recent

            record_recent(RecentCategories.CONFIG, filename)
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            pass

    def list_recent_configs(self, limit: int = 8) -> list[str]:
        try:
            from certus.ui.certus_recent import RecentCategories, list_recent

            return list_recent(RecentCategories.CONFIG, limit=limit)
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            return []

    def open_recent_configs(self) -> None:
        paths = self.list_recent_configs(limit=12)
        if not paths:
            return
        try:
            from PyQt6.QtWidgets import QInputDialog
            from certus.ui.certus_recent import short_label

            items = [short_label(p, max_length=80) for p in paths]
            label_to_path = dict(zip(items, paths))
            choice, ok = QInputDialog.getItem(self, "Open recent configuration", "Pick a recent file:", items, 0, False)
            if ok and choice and choice in label_to_path:
                if hasattr(self, "load_config"):
                    self.load_config(label_to_path[choice])
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            pass


class CertusDialogMixin:
    """Provides standardized confirmation dialogs."""

    def confirm_destructive(
        self,
        title: str,
        message: str,
        *,
        detail: Optional[str] = None,
        confirm_label: str = "Continue",
        cancel_label: str = "Cancel",
        default_cancel: bool = True,
    ) -> bool:
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
        except RuntimeError, AttributeError, TypeError, ValueError, ImportError:
            return False
