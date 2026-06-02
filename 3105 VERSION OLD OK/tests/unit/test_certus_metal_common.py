"""Unit tests for certus_metal_common helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

from certus.metal.certus_metal_common import _format_beam_status, normalize_percent_column, setup_beam_analysis_thread, teardown_beam_thread


@pytest.mark.unit
def test_normalize_percent_column_handles_percent_values() -> None:
    values = np.array([0.0, 50.0, 100.0], dtype=np.float64)
    out = normalize_percent_column(values)
    assert np.allclose(out, np.array([0.0, 0.5, 1.0], dtype=np.float64))


@pytest.mark.unit
def test_normalize_percent_column_keeps_fraction_values() -> None:
    values = np.array([0.1, 0.5, 0.9], dtype=np.float64)
    out = normalize_percent_column(values)
    assert np.allclose(out, values)


@pytest.mark.unit
def test_normalize_percent_column_handles_empty_array() -> None:
    values = np.array([], dtype=np.float64)
    out = normalize_percent_column(values)
    assert out.size == 0


@pytest.mark.unit
def test_setup_beam_analysis_thread_wires_cleanup_signals() -> None:
    worker = Mock()
    worker.progress = Mock(connect=Mock())
    worker.finished = Mock(connect=Mock())
    worker.error = Mock(connect=Mock())
    worker.moveToThread = Mock()
    worker.deleteLater = Mock()
    thread = Mock()
    thread.started = Mock(connect=Mock())
    thread.finished = Mock(connect=Mock())
    app = SimpleNamespace(
        beam_thread=None,
        beam_worker=None,
        status_label=Mock(setText=Mock()),
        on_beam_finished=Mock(),
        _on_beam_error=Mock(),
    )

    with patch("certus.metal.certus_metal_common.QThread", return_value=thread):
        out = setup_beam_analysis_thread(app, worker)

    assert out is thread
    assert app.beam_thread is thread
    assert app.beam_worker is worker
    worker.moveToThread.assert_called_once_with(thread)


@pytest.mark.unit
def test_format_beam_status_formats_expected_string() -> None:
    assert _format_beam_status(2, 5, 0.25) == "Thickness 2/5 | Best RMSE: 5.00e-01"


@pytest.mark.unit
def test_teardown_beam_thread_stops_and_clears_thread_state() -> None:
    thread = Mock()
    thread.isRunning = Mock(return_value=True)
    thread.wait = Mock(return_value=True)
    app = SimpleNamespace(
        beam_thread=thread,
        btn_run=Mock(setEnabled=Mock()),
        btn_beam=Mock(setEnabled=Mock()),
        btn_stop=Mock(setEnabled=Mock()),
        beam_stats=None,
    )

    teardown_beam_thread(app, {"ok": True})

    thread.quit.assert_called_once()
    thread.wait.assert_called_once_with(3000)
    assert app.beam_thread is None
    app.btn_run.setEnabled.assert_called_once_with(True)
    app.btn_beam.setEnabled.assert_called_once_with(True)
    app.btn_stop.setEnabled.assert_called_once_with(False)
    assert app.beam_stats == {"ok": True}
