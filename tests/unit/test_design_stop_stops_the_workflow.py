"""Once STOP is pressed, the DESIGN workflow goes no further.

« Stop » sets `_workflow_stopped` on the window, « first, to block pending QTimer callbacks ».
The four places that must honour it read it on the orchestrator or on the worker manager
(`getattr(self, "_workflow_stopped", False)`), which never hold it: the result of the stopped
optimization went down the normal path (a failure dialog, or the rest of the workflow), a
pending needle cycle still started or processed its result, and an internal restart still
launched a new optimization. Found on 2026-09-29 by listing every guard a class puts on a
name it never holds.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN stop", main_windows_only=True)


class _Started(Exception):
    """A worker was built: the workflow went on."""


def _refuse(*_args, **_kwargs):
    raise _Started


@pytest.fixture
def stopped_app(qapp, monkeypatch):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.logs = []
    app.dialogs = []
    monkeypatch.setattr(app, "log", lambda message, level="INFO": app.logs.append((level, message)))
    monkeypatch.setattr(app, "show_error_dialog", lambda *a, **k: app.dialogs.append(a), raising=False)
    monkeypatch.setattr(app.orchestrator, "_schedule_task", lambda *a, **k: None)
    monkeypatch.setattr("certus.workers.certus_design_workers.NeedleWorker", _refuse)
    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", _refuse)
    app._workflow_stopped = True
    return app


def test_the_result_of_a_stopped_run_is_not_reported_as_a_failure(stopped_app) -> None:
    stopped_app.orchestrator._on_optim_done({"ok": False, "error": "stopped"})

    assert stopped_app.dialogs == []
    assert not [message for level, message in stopped_app.logs if level == "ERROR"]
    assert ("WARNING", "Workflow stopped by user.") in stopped_app.logs


def test_no_needle_cycle_starts_after_stop(stopped_app) -> None:
    stopped_app.orchestrator._start_needle_process()

    assert ("WARNING", "Workflow stopped, skipping needle.") in stopped_app.logs


def test_a_needle_result_that_arrives_after_stop_is_ignored(stopped_app) -> None:
    stopped_app.orchestrator._on_needle_found({"action": "none"})

    assert ("WARNING", "Workflow stopped, ignoring needle result.") in stopped_app.logs


def test_no_internal_restart_after_stop(stopped_app) -> None:
    stopped_app.worker_manager.run_optim("local", keep_history=True)

    assert ("WARNING", "Workflow stopped by user, ignoring internal restart.") in stopped_app.logs
