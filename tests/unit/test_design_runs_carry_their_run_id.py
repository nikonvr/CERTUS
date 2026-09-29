"""The DESIGN workers receive the run id and the run context of the window.

WorkerManager built the configuration of the optimization and colorimetry workers with
`getattr(self, "_workflow_run_id", None)` — on the manager, which never holds it — instead
of the window: every worker ran with no run id and no run context, so nothing it logged
or returned could be traced back to its run. Found on 2026-09-29 by listing every guard a
class puts on a name it never holds.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN run id", main_windows_only=True)


class _Captured(Exception):
    """The worker configuration was read: the test has what it needs."""


@pytest.fixture
def design_app(qapp, monkeypatch):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app._post_load_config = lambda *a: None
    app.load_config(str(EXAMPLE))
    return app


def _capture_into(configs):
    def build(cfg):
        configs.append(cfg)
        raise _Captured

    return build


def test_an_optimization_worker_receives_the_run_id(design_app, monkeypatch) -> None:
    configs = []
    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", _capture_into(configs))

    # safe_ui_action turns the exception that stops the run into a log line.
    design_app.worker_manager.run_optim("local")

    [cfg] = configs
    assert cfg["run_id"] is not None
    assert cfg["run_id"] == design_app._workflow_run_id
    assert cfg["run_context"] is design_app._workflow_run_ctx


def test_a_colorimetry_worker_receives_the_run_id(design_app, monkeypatch) -> None:
    configs = []
    monkeypatch.setattr("certus.ui.certus_design_ui_worker.ColorWorker", _capture_into(configs))
    design_app.last_result = {"ep": np.asarray(design_app.ep_current, dtype=float)}
    design_app._workflow_run_id = "run-7"
    design_app._workflow_run_ctx = context = object()

    design_app.worker_manager.run_colorimetry()

    [cfg] = configs
    assert cfg["run_id"] == "run-7"
    assert cfg["run_context"] is context
