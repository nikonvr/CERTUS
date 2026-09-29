"""DESIGN's progress reaches the progress bar and the status line.

The progress handlers of WorkerManager looked for the progress widget, the status label and
the run counters on the manager (`hasattr(self, "progress_widget")`,
`getattr(self, "_optim_n_evals", 0)`), which never holds them: the needle scan and the
colorimetry never moved the bar nor the status line, the bar of an optimization always read
0 evaluations in phase « OPTIMIZATION », and the evaluation counter dropped the evaluations
of the previous stages of the workflow. The needle scan's progress signal was not even
connected: OptimizationManager connects it only when the window has `_on_needle_progress`,
and only the manager had it. Found on 2026-09-29 by listing every guard a class puts on a
name it never holds.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN progress", main_windows_only=True)


@pytest.fixture
def design_app(qapp, monkeypatch):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.bar = []
    monkeypatch.setattr(app.progress_widget, "update", lambda **kw: app.bar.append(kw))
    monkeypatch.setattr(app.progress_widget, "stop", lambda message="": app.bar.append({"stop": message}))
    return app


def test_the_needle_scan_moves_the_bar_and_the_status_line(design_app) -> None:
    design_app.worker_manager._on_needle_progress(40, "scan 4/10")

    assert design_app.bar and design_app.bar[-1]["phase"] == "NEEDLE SCAN"
    assert design_app.status_label.text() == "scan 4/10"


def test_the_window_forwards_the_needle_progress_so_the_signal_gets_connected(design_app) -> None:
    design_app._on_needle_progress(55, "scan 5/10")

    assert design_app.status_label.text() == "scan 5/10"


def test_the_colorimetry_moves_the_bar_and_ends_it(design_app) -> None:
    design_app.worker_manager._on_col_progress(30, "MC 30/100")
    assert design_app.bar[0]["phase"] == "COLORIMETRY"
    assert design_app.status_label.text() == "MC 30/100"

    design_app.worker_manager._on_col_done({"ok": False})
    assert design_app.bar[-1] == {"stop": "Done"}


def test_an_optimization_shows_its_phase_and_its_evaluations(design_app) -> None:
    design_app._optim_n_evals = 500
    design_app._optim_max_iter = 8
    design_app._optim_current_phase = "HEALING POLISH"

    design_app.worker_manager._on_optim_progress(12, "Gen 3 | Evals: 500 | Clusters: 2 | Best: 0.01")

    shown = design_app.bar[-1]
    assert (shown["evals"], shown["max_iter"], shown["phase"]) == (500, 8, "HEALING POLISH")


def test_the_evaluation_counter_includes_the_previous_stages(design_app) -> None:
    design_app.accumulated_evals = 900
    design_app.stats_label.setText("♟️ 0 | 🎲 0 | 🌈️ 0")

    design_app.worker_manager._on_stats_update("EVAL", 100)

    assert design_app.bar[-1]["evals"] == 1000
    assert "1000" in design_app.stats_label.text()
