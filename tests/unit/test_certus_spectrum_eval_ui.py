import importlib
from types import SimpleNamespace
from unittest.mock import Mock


import pytest


@pytest.mark.unit
def test_spectrum_eval_feedback_prefers_shared_status_helper(monkeypatch):
    mod = importlib.import_module("certus.ui.certus_spectrum_eval_ui")
    ui = importlib.import_module("certus.ui.certus_ui_utils")
    helper = Mock(return_value="toast")
    monkeypatch.setattr(ui, "show_status_feedback", helper)

    app = SimpleNamespace()
    mod.spectrum_eval_feedback(app, "Eval running", "info")

    helper.assert_called_once_with(app, "Eval running", "info", duration_ms=1200)


@pytest.mark.unit
def test_spectrum_eval_feedback_falls_back_to_status_labels(monkeypatch):
    mod = importlib.import_module("certus.ui.certus_spectrum_eval_ui")
    monkeypatch.setitem(mod.__dict__, "show_status_feedback", Mock(side_effect=RuntimeError("boom")))

    status = Mock()
    lbl = Mock()
    app = SimpleNamespace(status_label=status, lbl_status=lbl)

    mod.spectrum_eval_feedback(app, "Eval running", "info")

    assert status.setText.called or lbl.setText.called


@pytest.mark.unit
def test_show_status_feedback_updates_known_status_label(monkeypatch):
    ui = importlib.import_module("certus.ui.certus_ui_utils")
    toast = Mock(return_value=None)
    monkeypatch.setattr(ui, "show_toast", toast)

    status_label = Mock()
    app = SimpleNamespace(status_label=status_label)

    result = ui.show_status_feedback(app, "Ready", "success", duration_ms=500)

    toast.assert_called_once_with(app, "Ready", level="success", duration_ms=500)
    status_label.setText.assert_called_once_with("Ready")
    assert result is None


@pytest.mark.unit
def test_show_status_feedback_falls_back_to_lbl_status(monkeypatch):
    ui = importlib.import_module("certus.ui.certus_ui_utils")
    monkeypatch.setattr(ui, "show_toast", Mock(return_value=None))

    lbl_status = Mock()
    app = SimpleNamespace(lbl_status=lbl_status)

    ui.show_status_feedback(app, "Zoom 110%", "info", duration_ms=500)

    lbl_status.setText.assert_called_once_with("Zoom 110%")
