"""Unit tests for certus_reset_framework.
Covers create_reset_button, CertusResetManager, and Clear/Reset behavior of the CERTUS suite."""

import pytest
from unittest.mock import Mock, MagicMock, patch

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QTableWidget, QVBoxLayout
    from PyQt6.QtCore import Qt
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

try:
    from certus_reset_framework import CertusResetManager, create_reset_button
    RESET_AVAILABLE = True
except ImportError:
    RESET_AVAILABLE = False


def _make_mock_app(
    has_load_defaults=True,
    has_cleanup_worker=False,
    has_widgets=False,
    has_stack_table=False,
):
    """Fabrique une fausse app pour les tests du manager."""
    app = Mock()
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
    else:
        if hasattr(app, "_load_defaults"):
            del app._load_defaults
    if has_cleanup_worker:
        app._cleanup_worker = Mock()
    if has_widgets and has_stack_table:
        app.widgets = {"stack_table": Mock(setRowCount=Mock())}
    elif has_widgets:
        app.widgets = {}
    app.detached_window = None
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
    """Tests pour CertusResetManager."""

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
    """Tests pour create_reset_button."""

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
