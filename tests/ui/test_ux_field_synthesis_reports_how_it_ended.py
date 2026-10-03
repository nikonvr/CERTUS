"""FIELD says how a synthesis ended, and gives the window back (audit UX A08, ETAT D60).

Measured 2026-10-02, the end of a FIELD synthesis was written as an error when it was a normal ending:

    "Error: Stagnation"                  the cost no longer improves: the log says "Reverting ... and finishing"
    "Error: No needle insertion found"   no insertion helps: the log says "Reverting and finishing"
    "Error: Max layers reached"          the budget of 100 layers is spent

and the two `except ValueError:` that start the next worker threw the reason away: "Error: Failed to get parameters",
with nothing to say which field to correct (ETAT D60).

The same simulation showed a wait cursor still set once the synthesis was over: `_start_worker` sets one per worker
started, and `on_worker_finished` gave one back only for a run that was not a synthesis.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from certus.ui.certus_field_services import FieldStackService
from certus.workers.certus_field_workers_dto import FieldWorkerResult


@pytest.fixture
def window(qapp):
    from certus.ui.certus_field_ui import CertusFieldApp

    win = CertusFieldApp()
    messages: list[str] = []
    real_stop = win.progress_widget.stop

    def recording_stop(message="Done"):
        messages.append(message)
        real_stop(message)

    win.progress_widget.stop = recording_stop
    win.ended = messages
    # What the synthesis reads and writes, kept out of the optical calculation: only its state machine is under test.
    win.smart_cleanup = lambda _table: 0
    win._update_pareto_record = lambda *_a, **_k: None
    win._revert_to_synthesis_checkpoint = lambda: None
    try:
        yield win
    finally:
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        win.close()


def _synthesis_is_running(win, *, best_cost, cost) -> None:
    win._synthesis_active = True
    win._is_running = True
    win._synthesis_best_cost = best_cost
    win._synthesis_checkpoint = {"emp_factors": [1.0, 1.0], "layer_types": [0, 1], "cost": best_cost}
    win._compute_cost = lambda *_a, **_k: cost
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)  # what `_start_worker` does for each worker


def _a_worker_ends(win, action, result) -> None:
    win.worker = SimpleNamespace(request=SimpleNamespace(action=action), _result_reported=False)
    win.on_worker_finished(result)


def test_a_synthesis_that_stops_improving_ends_as_finished_not_as_an_error(window) -> None:
    _synthesis_is_running(window, best_cost=0.0, cost=1.0)

    _a_worker_ends(window, "optimize", FieldWorkerResult(success=True, message="ok"))

    assert window.ended, "the end of the synthesis was not reported"
    assert window.ended[-1].startswith("Finished"), window.ended
    assert "Error" not in window.ended[-1]


def test_a_needle_search_that_finds_nothing_ends_as_finished_not_as_an_error(window) -> None:
    _synthesis_is_running(window, best_cost=1.0, cost=1.0)

    _a_worker_ends(window, "needle", FieldWorkerResult(success=True, message="ok", opt_emp_factors=None))

    assert window.ended[-1].startswith("Finished"), window.ended
    assert "needle" in window.ended[-1].lower()


def test_the_layer_budget_is_a_stop_not_an_error(window) -> None:
    _synthesis_is_running(window, best_cost=10.0, cost=1.0)
    FieldStackService.load_stack(window.table_layers, [1.0] * 100, [i % 2 for i in range(100)])

    _a_worker_ends(window, "optimize", FieldWorkerResult(success=True, message="ok"))

    assert window.ended[-1].startswith("Stopped"), window.ended
    assert "100" in window.ended[-1]


@pytest.mark.parametrize("action", ["optimize", "needle"])
def test_a_refused_parameter_names_its_reason(window, action) -> None:
    """Both places that start the next worker: after an optimisation, and after a needle that found an insertion."""
    _synthesis_is_running(window, best_cost=10.0, cost=1.0)

    def refuse():
        raise ValueError("lambda step must be positive")

    window._get_params = refuse
    result = FieldWorkerResult(
        success=True, message="ok", opt_emp_factors=[1.0, 1.0, 1.0] if action == "needle" else None
    )

    _a_worker_ends(window, action, result)

    assert window.ended[-1].startswith("Error"), window.ended
    assert "lambda step must be positive" in window.ended[-1], window.ended


@pytest.mark.parametrize(
    ("action", "best_cost", "cost"),
    [("optimize", 0.0, 1.0), ("needle", 1.0, 1.0)],
    ids=["stagnation", "no-insertion"],
)
def test_the_wait_cursor_is_given_back_when_a_synthesis_ends(window, action, best_cost, cost) -> None:
    _synthesis_is_running(window, best_cost=best_cost, cost=cost)

    _a_worker_ends(window, action, FieldWorkerResult(success=True, message="ok", opt_emp_factors=None))

    assert QApplication.overrideCursor() is None, "the wait cursor stayed set after the synthesis had ended"
    assert window.btn_opt.isEnabled()
