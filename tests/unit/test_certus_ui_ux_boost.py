"""
Coverage boost unit tests for certus_ui.py custom UX components and base app.
Focuses on custom widgets and base application lifecycle.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QMainWindow

from certus.ui.certus_ui import (
    CertusStepper,
    CertusCollapsible,
    CertusStatusPill,
    CertusActionBar,
    CertusToast,
    SkeletonLoaderWidget,
    install_skeleton_loader,
    remove_skeleton_loader,
    EnhancedProgressWidget,
    ProgressDialog,
    CertusBaseApp,
    copy_app_logs_to_clipboard,
    open_file_explorer,
    show_toast,
    apply_certus_theme,
    update_global_plot_config,
    CertusThemeToggle,
    create_flashy_grid,
    create_log_widget,
    CertusLogPanel,
)

# Skip all tests if PyQt6 is not available
try:
    from PyQt6.QtWidgets import QApplication
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

pytestmark = pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 not available")


@pytest.fixture
def clean_last_dir():
    """Reset the last dir settings for clean state."""
    with patch("certus.ui.certus_ui.QSettings") as mock_settings:
        yield mock_settings


class TestUXComponentsBoost:
    """Tests for custom widgets of the Certus Design System."""

    def test_certus_stepper(self, qapp) -> None:
        _ = qapp
        steps = ["Design", "Strat", "Verify"]
        stepper = CertusStepper(steps, parent=None)
        assert stepper is not None
        assert stepper._current == 0
        
        # Test stepping
        stepper.set_step(1)
        assert stepper._current == 1
        
        # Trigger click
        stepper._on_click(2)
        stepper.set_step(2)
        assert stepper._current == 2

    def test_certus_collapsible(self, qapp) -> None:
        _ = qapp
        content = QWidget()
        
        # Mock animations to run synchronously
        with patch("certus.ui.certus_animations.fade_out", side_effect=lambda w, **k: w.setVisible(False)), \
             patch("certus.ui.certus_animations.fade_in", side_effect=lambda w, **k: w.setVisible(True)):
            
            collapsible = CertusCollapsible("Options", content, expanded=True, parent=None)
            assert collapsible is not None
            collapsible.show()
            assert collapsible.is_expanded() is True
            
            # Collapse it
            collapsible.set_expanded(False)
            assert collapsible.is_expanded() is False
            assert not content.isVisible()
            
            # Expand it
            collapsible.set_expanded(True)
            assert collapsible.is_expanded() is True
            assert content.isVisible()

    def test_certus_status_pill(self, qapp) -> None:
        _ = qapp
        pill = CertusStatusPill("Ready", level="ready")
        assert pill.text() == "Ready"
        
        pill.setText("Running")
        pill.set_level("running")
        assert pill.text() == "Running"
        assert pill._level == "running"
        
        pill.setText("Error")
        pill.set_level("error")
        assert pill.text() == "Error"

    def test_certus_action_bar(self, qapp) -> None:
        _ = qapp
        bar = CertusActionBar()
        assert bar is not None
        
        btn = QPushButton("Run")
        bar.add_widget(btn)
        bar.add_stretch()

    def test_certus_toast(self, qapp) -> None:
        _ = qapp
        parent = QWidget()
        toast = CertusToast(parent, "Computation finished", level="success")
        assert toast is not None
        assert toast.text() == "Computation finished"
        
        # Test global helper
        helper_toast = show_toast(parent, "Warning", level="warning", duration_ms=10)
        assert helper_toast is not None

    def test_skeleton_loader(self, qapp) -> None:
        _ = qapp
        from PyQt6.QtGui import QPixmap
        parent = QWidget()
        
        # Test default shape and rendering
        loader = SkeletonLoaderWidget(parent)
        assert loader is not None
        loader._update_shimmer(50)
        pix = QPixmap(200, 200)
        loader.resize(200, 200)
        loader.render(pix)
        loader._timeline.stop()

        # Test other shapes rendering to cover all paintEvent branches
        for shape in ["chart", "table", "cards"]:
            s_loader = SkeletonLoaderWidget(parent, shape=shape)
            s_loader.resize(200, 200)
            s_loader.render(pix)
            s_loader._timeline.stop()

        # Test installer and remover
        widget = QWidget()
        skl = install_skeleton_loader(widget, "chart")
        assert skl is not None
        assert hasattr(widget, "_certus_skeleton")
        
        removed = remove_skeleton_loader(widget)
        assert removed is True
        assert not hasattr(widget, "_certus_skeleton")

    def test_enhanced_progress_widget(self, qapp) -> None:
        _ = qapp
        prog = EnhancedProgressWidget()
        assert prog is not None
        prog.show()
        prog.start()
        prog.set_time_budget(120)
        
        prog.update(iteration=45, max_iter=100, evals=12, phase="Optimization", animate=False)
        assert prog.progress_bar.value() in (45, 46)
        assert "ETA" in prog.info_label.text()
        assert prog.detail_label.text().startswith("Status:")
        assert "Phase:" in prog.detail_label.text()
        
        prog.enable_cancel(True)
        assert prog.cancel_btn.isVisible()
        
        prog._on_cancel()
        assert prog.is_canceled() is True
        prog.stop("Completed")
        assert prog.detail_label.text() == "Status: Cancelled • Phase: finalizing • Next: review or resume"

    def test_progress_dialog(self, qapp) -> None:
        _ = qapp
        dlg = ProgressDialog(title="Calculating", parent=None)
        assert dlg is not None
        dlg.progress_bar.setValue(10)
        dlg.status_label.setText("Starting...")
        assert dlg.progress_bar.value() == 10
        assert dlg.status_label.text() == "Starting..."
        dlg.finish()

    def test_theme_and_plot_config(self, qapp) -> None:
        _ = qapp
        widget = QWidget()
        mock_plot = MagicMock()
        mock_plot.setBackground = MagicMock()
        mock_plot.getAxis = MagicMock()
        
        # Test applying theme with overrides and plots
        apply_certus_theme(widget, plots=[mock_plot], overrides="QWidget { color: red; }", premium=True)
        assert widget.styleSheet() != ""
        mock_plot.setBackground.assert_called_once()
        
        # Test applying theme without premium
        apply_certus_theme(widget, premium=False)
        
        # Test updating global plot config
        import unittest.mock
        with patch("pyqtgraph.setConfigOption") as mock_set_opt:
            update_global_plot_config(dark_mode=True)
            mock_set_opt.assert_any_call("background", unittest.mock.ANY)

    def test_theme_toggle_widget(self, qapp) -> None:
        _ = qapp
        toggle = CertusThemeToggle()
        assert toggle is not None
        
        # Mock functions called by toggle
        with patch("certus.ui.certus_ui_widgets_utils.load_theme_config", return_value="light"), \
             patch("certus.ui.certus_ui_widgets_utils.save_theme_config") as mock_save, \
             patch("certus.ui.certus_theme.CertusTheme.configure") as mock_conf, \
             patch("certus.ui.certus_ui_utils.update_global_plot_config") as mock_plot, \
             patch("certus.ui.certus_theme.CertusTheme.apply_to_app") as mock_apply_app:
            
            toggle.toggle()
            mock_save.assert_called_with("dark")
            mock_conf.assert_called_with("dark")

    def test_flashy_grid_factory(self, qapp) -> None:
        _ = qapp
        cards = [QWidget() for _ in range(4)]
        grid_w = create_flashy_grid(cards)
        assert grid_w is not None
        assert grid_w.layout().count() == 4

    def test_log_panel_widget(self, qapp) -> None:
        _ = qapp
        # test create_log_widget
        log_widget = create_log_widget(visible=True, height=100)
        assert log_widget is not None
        assert not log_widget.isHidden()
        assert log_widget.maximumHeight() == 100
        
        # test CertusLogPanel
        panel = CertusLogPanel(title="TEST LOGS", visible=True, height=150)
        assert panel is not None
        assert not panel.log_text.isHidden()
        
        # test copy to clipboard
        with patch.object(QApplication.instance().clipboard(), "setText") as mock_set_text:
            panel.log_text.setPlainText("Some testing logs")
            panel.copy_to_clipboard()
            mock_set_text.assert_called_once_with("Some testing logs")

    def test_custom_formatters(self, qapp) -> None:
        _ = qapp
        from certus.core.certus_core import CertusConsoleFormatter, CertusGuiFormatter
        import logging
        
        # Test CertusConsoleFormatter with color
        fmt_color = CertusConsoleFormatter(use_color=True)
        rec1 = logging.LogRecord("test_logger", logging.INFO, "path/to/file.py", 10, "Test message", None, None)
        res1 = fmt_color.format(rec1)
        assert "INFO" in res1
        assert "Test message" in res1
        
        # Test CertusConsoleFormatter without color
        fmt_no_color = CertusConsoleFormatter(use_color=False)
        res2 = fmt_no_color.format(rec1)
        assert "INFO" in res2
        
        # Test CertusGuiFormatter
        fmt_gui = CertusGuiFormatter()
        res3 = fmt_gui.format(rec1)
        assert "INFO" in res3

    def test_process_log_queue_standard(self, qapp) -> None:
        _ = qapp
        import queue
        from certus.ui.certus_ui_utils import process_log_queue_standard
        from PyQt6.QtWidgets import QTextEdit
        
        widget = QTextEdit()
        q = queue.Queue()
        
        # Test standard GUI log
        q.put("2026-06-16 09:49:05 ✦ INFO  ➔ [CERTUS-METAL-BILAYER] Show Details logger attached")
        count = process_log_queue_standard(q, widget)
        assert count == 1
        assert "Show Details" in widget.toHtml()
        
        # Test GUI log with pipe character in the actual message (the bug case)
        q.put("2026-06-16 09:49:28 ✦ INFO  ➔ GLOBAL_OPT(PGlobal) K=2 [PGLOBAL] x0_probe | rmse=1.737622e-01 | x0_head=[5.0] | x0_dim=8")
        process_log_queue_standard(q, widget)
        # Should parse correctly and contain rmse in the formatted text (not stripped to a bracket)
        assert "rmse=1.737622e-01" in widget.toHtml()
        assert "x0_head=[5.0]" in widget.toHtml()
        
        # Test legacy log format with pipes
        q.put("2026-06-16 09:49:28 | INFO | Legacy message | with | pipes")
        process_log_queue_standard(q, widget)
        assert "Legacy message | with | pipes" in widget.toHtml()




class DummyApp(CertusBaseApp):
    """Subclass of CertusBaseApp for testing base functionality."""
    APP_TITLE = "Test Dummy App"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._finalize_init()
        
    def _build_ui(self):
        from PyQt6.QtWidgets import QStatusBar, QTableWidget
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        
        # Attribute matching hint for empty state installation coverage
        self.results_table = QTableWidget(self)
        
        self.setCentralWidget(QWidget())

    def _get_default_config_name(self) -> str:
        return "test_dummy_config.json"

    def _get_config_file_filter(self) -> str:
        return "JSON (*.json)"

    def _collect_config(self) -> dict:
        return {"param1": 42}

    def _apply_config(self, config: dict) -> None:
        self.applied_config = config

    # Mock candidate methods for auto discovered commands coverage
    def run_optimization(self):
        pass

    def stop_optimization(self):
        pass

    def export_excel(self):
        pass


class TestCertusBaseAppBoost:
    """Tests for the base application container and standard actions."""

    def test_base_app_initialization_and_lifecycle(self, qapp) -> None:
        _ = qapp
        app = DummyApp()
        assert app is not None
        assert "Test Dummy App" in app.windowTitle()
        
        # Test help menu installation
        app.install_help_menu(app_label="TEST")
        
        # Test config file paths
        cfg_name = app._get_default_config_name()
        assert cfg_name is not None
        assert cfg_name.endswith(".json")

    def test_base_app_save_load_config(self, qapp, tmp_path) -> None:
        _ = qapp
        app = DummyApp()
        
        test_file = tmp_path / "test_dummy_config.json"
        
        # Mock file dialogs
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(test_file), "")), \
             patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(str(test_file), "")):
            
            # Save configuration
            app.save_config()
            assert test_file.exists()
            
            # Load configuration
            app.load_config()
            assert app.applied_config == {"param1": 42}

    def test_copy_app_logs_to_clipboard(self, qapp) -> None:
        _ = qapp
        mock_app = MagicMock()
        mock_app._log_panel = None
        
        log_text = MagicMock()
        log_text.toPlainText.return_value = "Log line 1\nLog line 2"
        mock_app.log_text = log_text
        
        with patch.object(QApplication.instance().clipboard(), "setText") as mock_set_text:
            result = copy_app_logs_to_clipboard(mock_app)
            assert result is True
            mock_set_text.assert_called_once_with("Log line 1\nLog line 2")

    def test_open_file_explorer_utility(self, tmp_path) -> None:
        # Mock Path.exists to return True
        test_dir = tmp_path / "fake_dir"
        test_dir.mkdir()
        
        with patch("os.startfile") as mock_startfile, \
             patch("subprocess.Popen") as mock_popen, \
             patch("sys.platform", "win32"):
            open_file_explorer(str(test_dir))
            mock_startfile.assert_called_once()
            
            # Non-dir select Popen test
            test_file = test_dir / "file.txt"
            test_file.write_text("hello")
            open_file_explorer(str(test_file))
            mock_popen.assert_called_once()

    def test_base_app_zoom_actions(self, qapp) -> None:
        _ = qapp
        app = DummyApp()
        app.zoom_in_ui()
        assert app._zoom_factor > 1.0
        
        app.zoom_out_ui()
        assert abs(app._zoom_factor - 1.0) < 1e-5
        
        app.reset_ui_zoom()
        assert abs(app._zoom_factor - 1.0) < 1e-5

    def test_base_app_commands_registry(self, qapp) -> None:
        _ = qapp
        app = DummyApp()
        
        # Test command default registration
        cmds = app._default_commands()
        assert len(cmds) > 0
        
        # Test register command
        from certus.utils.certus_command_palette import CommandAction
        new_cmd = CommandAction(
            id="test.action",
            title="Test Action",
            category="Test",
            callback=lambda: None
        )
        app.register_command(new_cmd)
        assert any(cmd.id == "test.action" for cmd in app._commands)

    def test_base_app_toggle_theme(self, qapp) -> None:
        _ = qapp
        app = DummyApp()
        
        with patch("certus.ui.mixins.certus_base_core_mixins.load_theme_config", return_value="light"), \
             patch("certus.ui.mixins.certus_base_core_mixins.save_theme_config") as mock_save, \
             patch("certus.ui.certus_theme.CertusTheme.configure") as mock_conf, \
             patch("certus.ui.certus_theme.CertusTheme.apply_to_app") as mock_apply, \
             patch("certus.ui.certus_ui_utils.update_global_plot_config") as mock_plot:
            
            app._toggle_theme()
            mock_save.assert_called_with("dark")
            mock_conf.assert_called_with("dark")

    def test_base_app_tours_and_shortcuts(self, qapp) -> None:
        _ = qapp
        app = DummyApp()
        
        # Onboarding tour
        with patch("certus.ui.certus_tours_catalog.run_app_onboarding", return_value="success") as mock_run:
            res = app.run_onboarding_tour(force=True)
            assert res == "success"
            
        with patch("certus.ui.certus_onboarding.reset_onboarding") as mock_reset:
            app.reset_onboarding_tour()
            mock_reset.assert_called_once_with("CERTUS")
 
        # Open command palette and shortcuts overlay
        with patch("certus.utils.certus_command_palette.open_command_palette") as mock_palette:
            app.open_command_palette()
            mock_palette.assert_called_once()
            
        with patch("certus.ui.certus_shortcuts_overlay.open_shortcuts_overlay") as mock_shortcuts:
            app.open_shortcuts_overlay()
            mock_shortcuts.assert_called_once()

    def test_load_inter_font(self, qapp) -> None:
        _ = qapp
        from certus.ui.certus_theme import CertusTheme
        
        # Test loading of Inter font does not crash, even with mock url failures
        with patch("urllib.request.urlopen", side_effect=Exception("offline")):
            font = CertusTheme.load_inter_font()
            assert font in ["Inter", "Segoe UI"]

