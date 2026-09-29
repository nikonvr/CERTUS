"""The evaluation that ends a DESIGN workflow triggers the automatic export of the results.

The workflow raises `_export_pending` on the window before its final evaluation;
WorkerManager._on_eval_finished read it on the manager (`getattr(self, "_export_pending",
False)`), which never holds it: with the automatic export on, no DESIGN run exported its
results from the split of the window into managers (c79316b, 2026-06-13) to 2026-09-29.
Measured on the example with the export on: three runs, no Report_DESIGN file.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN final export", main_windows_only=True)


def test_a_pending_export_is_scheduled_when_the_evaluation_ends(qapp, monkeypatch) -> None:
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    scheduled = []
    monkeypatch.setattr(app.orchestrator, "schedule_export_results", lambda: scheduled.append("export"))
    evaluated = []
    real_finished = app.worker_manager._on_eval_finished
    monkeypatch.setattr(
        app.worker_manager,
        "_on_eval_finished",
        lambda data, generation_id=None: (real_finished(data, generation_id), evaluated.append(1)),
    )
    app._export_pending = True

    app.run_eval()
    deadline = time.monotonic() + 120
    while not evaluated and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert evaluated, "the evaluation never finished"
    assert scheduled == ["export"]
    assert app._export_pending is False
