"""Unit tests for certus_reset_framework.
Covers create_reset_button, CertusResetManager, and Clear/Reset behavior of the CERTUS suite."""

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QTableWidget, QVBoxLayout
    from PyQt6.QtCore import Qt
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

try:
    from certus.utils.certus_reset_framework import AsyncWriteWorker, CertusResetManager, create_reset_button, save_state_async
    RESET_AVAILABLE = True
except ImportError:
    RESET_AVAILABLE = False


def _make_mock_app(
    has_load_defaults=True,
    has_cleanup_worker=False,
    has_widgets=False,
    has_stack_table=False,
):
    """Creates a fake app for manager tests."""
    class FakeCertusApp:
        pass
    app = FakeCertusApp()
    app.log_text = Mock()
    app.log_text.clear = Mock()
    app.best_rmse_label = Mock()
    app.status_label = Mock()
    app.stats_label = Mock()
    app.lbl_status = Mock()
    app.undo_btn = Mock()
    app.btn_stop = Mock()
    app.btn_run = Mock()
    app.front_table = Mock()
    app.front_table.setRowCount = Mock()
    app.back_table = Mock()
    app.back_table.setRowCount = Mock()
    app.target_table = Mock()
    app.target_table.setRowCount = Mock()
    app.progress_widget = Mock()
    app.progress_widget.stop = Mock()
    if has_load_defaults:
        app._load_defaults = Mock()
    if has_cleanup_worker:
        app._cleanup_worker = Mock()
    if has_widgets and has_stack_table:
        app.widgets = {"stack_table": Mock(setRowCount=Mock())}
    elif has_widgets:
        app.widgets = {}
    app.detached_window = None
    app.detached_plot_windows = {}
    app._force_idle = Mock()
    app.log = Mock()
    app.pareto_history = {}
    app.undo_stack = []
    app._workflow_stopped = False
    app._current_eval_generation = 0
    app._best_eval_rmse = float("inf")
    app._initial_cleared = False
    app.stat_counters = {"EVAL": 0, "BEST": 0, "MINIMA": 0}
    # findChildren must return an iterable, not a Mock
    app.findChildren = Mock(return_value=[])
    return app



@pytest.mark.skipif(not RESET_AVAILABLE, reason="certus_reset_framework non disponible")
class TestCertusResetManager:
    """Tests for CertusResetManager."""

    def test_manager_init(self):
        app = _make_mock_app()
        m = CertusResetManager(app)
        assert m.app is app

    @pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 non disponible")
    def test_confirm_reset_returns_false_when_no(self):
        from PyQt6.QtWidgets import QMessageBox
        app = _make_mock_app()
        m = CertusResetManager(app)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            assert m._confirm_reset() is False

    @pytest.mark.skipif(not QT_AVAILABLE, reason="PyQt6 non disponible")
    def test_confirm_reset_returns_true_when_yes(self):
        from PyQt6.QtWidgets import QMessageBox
        app = _make_mock_app()
        m = CertusResetManager(app)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            assert m._confirm_reset() is True

    def test_stop_all_workers_calls_request_stop_if_present(self):
        app = _make_mock_app()
        app._request_stop = Mock()
        m = CertusResetManager(app)
        m._stop_all_workers()
        app._request_stop.assert_called_once()

    def test_stop_all_workers_calls_cleanup_worker_if_present(self):
        app = _make_mock_app(has_cleanup_worker=True)
        m = CertusResetManager(app)
        m._stop_all_workers()
        app._cleanup_worker.assert_called_once()

    def test_stop_all_workers_calls_worker_stop_when_available(self):
        app = _make_mock_app()
        worker = Mock()
        worker.isRunning = Mock(return_value=True)
        worker.wait = Mock(return_value=True)
        worker.stop = Mock()
        app.worker = worker
        m = CertusResetManager(app)
        m._stop_all_workers()
        worker.stop.assert_called_once()

    def test_clear_ui_elements_clears_tables_and_labels(self):
        app = _make_mock_app()
        m = CertusResetManager(app)
        m._clear_ui_elements()
        app.log_text.clear.assert_called_once()
        app.front_table.setRowCount.assert_called_once_with(0)
        app.best_rmse_label.setText.assert_called_once()
        app.status_label.setText.assert_called_once()
        app.stats_label.setText.assert_called_once()
        app.btn_stop.setEnabled.assert_called()
        app.btn_run.setEnabled.assert_called()

    def test_clear_ui_elements_clears_stack_table_when_in_widgets(self):
        app = _make_mock_app(has_widgets=True, has_stack_table=True)
        m = CertusResetManager(app)
        m._clear_ui_elements()
        app.widgets["stack_table"].setRowCount.assert_called_once_with(0)

    def test_load_application_defaults_calls_app_load_defaults(self):
        app = _make_mock_app()
        m = CertusResetManager(app)
        m._load_application_defaults()
        app._load_defaults.assert_called_once()

    def test_load_application_defaults_no_error_when_no_load_defaults(self):
        app = _make_mock_app(has_load_defaults=False)
        m = CertusResetManager(app)
        m._load_application_defaults()
        assert not hasattr(app, "_load_defaults")


@pytest.mark.skipif(not QT_AVAILABLE or not RESET_AVAILABLE, reason="PyQt6 ou certus_reset_framework non disponible")
class TestCreateResetButton:
    """Tests for create_reset_button."""

    def test_create_reset_button_returns_button(self, qapp):
        app = _make_mock_app()
        btn = create_reset_button(app)
        assert btn is not None
        assert btn.text() == "🔄  Clear / Reset"
        assert "Reset" in btn.toolTip() or "reset" in btn.toolTip().lower()

    def test_create_reset_button_without_use_app_reset_uses_manager(self, qapp):
        app = _make_mock_app()
        btn = create_reset_button(app, use_app_reset=False)
        assert btn is not None
        assert "Clear" in btn.text() or "Reset" in btn.text()

    def test_create_reset_button_with_use_app_reset_connects_to_app_reset_to_defaults(self, qapp):
        app = _make_mock_app()
        app.reset_to_defaults = Mock()
        btn = create_reset_button(app, use_app_reset=True)
        btn.clicked.emit()
        app.reset_to_defaults.assert_called_once()

    def test_create_reset_button_use_app_reset_false_when_app_has_no_reset_to_defaults(self, qapp):
        class AppWithoutReset:
            pass
        app = AppWithoutReset()
        assert not hasattr(app, "reset_to_defaults")
        btn = create_reset_button(app, use_app_reset=True)
        assert btn is not None


@pytest.mark.skipif(not QT_AVAILABLE or not RESET_AVAILABLE, reason="PyQt6 ou certus_reset_framework non disponible")
class TestResetIntegration:
    """Reset integration tests (without opening real dialogs)."""

    def test_reset_to_defaults_cancelled_when_user_says_no(self):
        from PyQt6.QtWidgets import QMessageBox
        app = _make_mock_app()
        m = CertusResetManager(app)
        with patch.object(m, "_confirm_reset", return_value=False):
            out = m.reset_to_defaults()
        assert out is False
        app._load_defaults.assert_not_called()

    def test_reset_to_defaults_full_flow_when_user_says_yes(self):
        from PyQt6.QtWidgets import QMessageBox
        app = _make_mock_app()
        m = CertusResetManager(app)
        with patch.object(m, "_confirm_reset", return_value=True):
            with patch.object(m, "_stop_all_workers"):
                with patch.object(m, "_clear_ui_elements"):
                    with patch.object(m, "_reset_all_plots"):
                        with patch.object(m, "_clear_internal_state"):
                            with patch.object(m, "_handle_detached_windows"):
                                with patch.object(m, "_force_memory_cleanup"):
                                    with patch.object(m, "_final_ui_refresh"):
                                        with patch.object(m, "_clear_visual_outputs_post_defaults"):
                                            out = m.reset_to_defaults()
        assert out is True
        app._load_defaults.assert_called_once()

    def test_reset_works_during_loop_request_stop_called_before_cleanup(self):
        app = _make_mock_app(has_cleanup_worker=True)
        app._request_stop = Mock()
        m = CertusResetManager(app)
        m._stop_all_workers()
        assert app._request_stop.called
        assert app._cleanup_worker.called
        assert app._request_stop.call_count >= 1 and app._cleanup_worker.call_count >= 1


class TestAsyncWriteWorker:
    def test_worker_writes_json_atomically(self, tmp_path, monkeypatch):
        target = tmp_path / "state.json"
        started = []

        class DummyPool:
            def start(self, runnable):
                started.append(runnable)
                runnable.run()

        monkeypatch.setattr("certus_reset_framework.QThreadPool.globalInstance", lambda: DummyPool())

        worker = save_state_async(lambda: {"ok": True}, target)
        assert isinstance(worker, AsyncWriteWorker)
        assert started == [worker]
        assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}

    def test_worker_handles_payload_factory_errors(self, tmp_path, caplog):
        worker = AsyncWriteWorker(lambda: (_ for _ in ()).throw(ValueError("boom")), tmp_path / "state.json")
        worker.run()
        assert not (tmp_path / "state.json").exists()
        assert any("Async state save failed" in record.message for record in caplog.records)


class TestResetManagerCoverageBoost:
    def test_reset_to_defaults_exception_handling(self, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox
        app = _make_mock_app()
        m = CertusResetManager(app)
        
        # Make _stop_all_workers raise ValueError (which is in NUMERICAL_FAULT_EXCEPTIONS)
        def mock_stop():
            raise ValueError("Mocked reset failure")
        monkeypatch.setattr(m, "_stop_all_workers", mock_stop)
        monkeypatch.setattr(m, "_confirm_reset", lambda: True)
        
        critical_calls = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *args: critical_calls.append(args))
        
        assert m.reset_to_defaults() is False
        assert len(critical_calls) == 1

    def test_stop_all_workers_exceptions(self):
        app = _make_mock_app(has_cleanup_worker=True)
        app._request_stop = Mock(side_effect=RuntimeError("Request stop error"))
        app._cleanup_worker = Mock(side_effect=TypeError("Cleanup error"))
        
        m = CertusResetManager(app)
        m._stop_all_workers()  # Should not raise exceptions
        
        assert app._request_stop.called
        assert app._cleanup_worker.called

    def test_worker_stop_types_and_timeouts(self):
        app = _make_mock_app()
        w1 = Mock()
        w1.isRunning = Mock(return_value=True)
        w1.wait = Mock(return_value=False)
        w1.requestInterruption = Mock()
        w1.stop = Mock(side_effect=RuntimeError("Stop failed"))
        # w1 does not have request_stop
        del w1.request_stop
        
        app.optim_worker = w1
        m = CertusResetManager(app)
        m._stop_all_workers()
        
        assert w1.requestInterruption.called
        assert w1.stop.called
        assert w1.wait.called
        # Check that it set the worker to None after trying to stop it
        assert app.optim_worker is None

    def test_clear_ui_exceptions(self):
        app = _make_mock_app()
        bad_widget = Mock()
        bad_widget.clear = Mock(side_effect=RuntimeError("Clear failed"))
        
        app.findChildren = Mock(return_value=[bad_widget])
        m = CertusResetManager(app)
        m._clear_ui_elements()  # Should not raise
        assert bad_widget.clear.called

    def test_reset_plots_axes_labels_exception(self):
        app = _make_mock_app()
        plot = Mock()
        plot.plotItem = Mock()
        plot.plotItem.clear = Mock()
        plot.plotItem.setLabel = Mock(side_effect=RuntimeError("SetLabel failed"))
        plot.clear_tracking = Mock()
        
        app.spectrum_plot = plot
        m = CertusResetManager(app)
        m._reset_all_plots()  # Should handle exception cleanly
        assert plot.plotItem.clear.called
        assert plot.clear_tracking.called

    def test_clear_internal_state_structures_without_clear(self, monkeypatch):
        app = _make_mock_app()
        
        # A list without a clear method
        class ListWithoutClear:
            def __init__(self, data):
                self.data = data
            def __len__(self):
                return len(self.data)
                
        nc_list = ListWithoutClear([1, 2, 3])
        app.pareto_history = nc_list
        app.latest_results = {"a": 1}  # Dict has clear, which is fine
        
        m = CertusResetManager(app)
        m._clear_internal_state()
        
        # pareto_history has been replaced with an empty list
        assert app.pareto_history == []

    def test_handle_detached_windows(self):
        app = _make_mock_app()
        win = Mock()
        win.close = Mock()
        app.detached_window = win
        
        win2 = Mock()
        win2.close = Mock(side_effect=RuntimeError("Close failed"))
        app.detached_plot_windows = {"plot1": win2}
        
        app.close_all_auxiliary_windows = Mock()
        
        m = CertusResetManager(app)
        m._handle_detached_windows()
        
        assert win.close.called
        assert win2.close.called
        assert app.close_all_auxiliary_windows.called
        assert app.detached_window is None
        assert app.detached_plot_windows == {}

    def test_reset_app_to_defaults_no_confirm(self):
        app = _make_mock_app()
        app.detached_plot_windows = {}
        from certus.utils.certus_reset_framework import reset_app_to_defaults
        res = reset_app_to_defaults(app, confirm=False)
        assert res is True
        assert app._load_defaults.called

    def test_reset_manager_extreme_branch_coverage(self, monkeypatch):
        from certus.utils.certus_reset_framework import CertusResetManager
        app = _make_mock_app()
        
        # 1. Test missing progress widget, labels, buttons, tables, widgets
        for attr in ("progress_widget", "best_rmse_label", "front_table", "log_text", "widgets"):
            if hasattr(app, attr):
                delattr(app, attr)

        
        # 2. Test pyqtgraph plot generic reset
        mock_pg_plot = Mock()
        mock_pg_plot.plotItem = Mock()
        mock_pg_plot.plotItem.clear = Mock()
        mock_pg_plot.clear_tracking = Mock()
        app.findChildren = Mock(return_value=[mock_pg_plot])
        
        # 3. Test exceptions on clear_text_outputs_only (mocked after _clear_ui_elements is run)
        bad_console = Mock()
        bad_console.clear = Mock(side_effect=RuntimeError("clear error"))
        
        # 4. Test memory cleanup exception by mocking gc.collect to fail
        monkeypatch.setattr("gc.collect", Mock(side_effect=TypeError("gc collect failed")))
        
        m = CertusResetManager(app)
        
        # Let's run all individual sub-methods to assert no exceptions and cover lines
        m._stop_all_workers()
        m._clear_ui_elements()
        
        # Now set the bad console and trigger text outputs only clearing
        app.console_text = bad_console
        m._clear_text_outputs_only()
        
        m._reset_all_plots()
        m._force_memory_cleanup()
        
        # Assertions to make sure our mocked items were called/handled
        assert mock_pg_plot.plotItem.clear.called
        assert mock_pg_plot.clear_tracking.called
        assert bad_console.clear.called




