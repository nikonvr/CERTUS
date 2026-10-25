"""The tasks the DESIGN orchestrator schedules run, after their delay.

Until 2026-07-03 the orchestrator called QTimer.singleShot itself. 06a1083 routed every call
through `hasattr(self.ui, "schedule_task")` to keep Qt out of the orchestrator, and gave
`schedule_task` to OptimizationManager, not to the window. From then on the guard was always
false: the nine `schedule_*` methods did nothing — no automatic export of the results, no
smart Pareto decimation, no refresh of the Pareto table or of the Tikhonravov points — and
`_schedule_task` ran its task at once, inside the caller, instead of after the delay.
"""

from __future__ import annotations

import time

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN scheduled tasks", main_windows_only=True)


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    window = CertusDesignApp()
    # The window schedules its own refreshes at 0 and 150 ms while it is built (certus_design_ui.py, certus_design_ui_core.py). Let
    # them run before a test watches a task: on a slow turn of the event loop two of them landed in the same pass and a test
    # that waits for one call counted two (3.15.1, 2026-10-25, red alone in a serial run).
    deadline = time.monotonic() + 0.6
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    return window


def _wait_for(qapp, calls, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not calls and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


@pytest.mark.parametrize(
    ("schedule", "task"),
    [
        ("schedule_refresh_pareto_table", "_refresh_pareto_table"),
        ("schedule_update_substrate_info", "_update_substrate_info"),
        ("schedule_update_tikhonravov_points", "_update_tikhonravov_points"),
        ("schedule_export_results", "export_results"),
        ("schedule_smart_pareto_decimation", "_start_smart_pareto_decimation"),
        ("schedule_smart_decimation_remove_and_optimize", "_smart_decimation_remove_and_optimize"),
        ("schedule_export_pareto_report", "_export_pareto_report"),
        ("schedule_local_optim_keep_history", "run_optim"),
        ("schedule_decimation_remove_and_polish", "_decimation_remove_and_polish"),
    ],
)
def test_a_scheduled_task_runs_after_its_delay(qapp, design_app, monkeypatch, schedule, task) -> None:
    calls = []
    monkeypatch.setattr(design_app, task, lambda *a, **k: calls.append((a, k)))

    getattr(design_app.orchestrator, schedule)()
    assert calls == []

    _wait_for(qapp, calls)
    assert len(calls) == 1


def test_a_workflow_step_is_deferred_not_run_inside_its_caller(qapp, design_app) -> None:
    calls = []

    design_app.orchestrator._schedule_task(50, lambda: calls.append("step"))
    assert calls == []

    _wait_for(qapp, calls)
    assert calls == ["step"]
