"""WorkerManager reads the settings and the state of the window on the window.

Three reads of `WorkerManager` were written on the manager (`hasattr(self, "pre_polish_check")`,
`hasattr(self, "_workflow_best_rmse")`, `getattr(self, "_last_config_file", "")`), which holds
none of them: the « Local polish before PGLOBAL » checkbox never reached the global worker (the
polish never ran, however the box was set or saved), an internal restart did not carry the best
RMSE to its worker (the display regressed at every restart) and the spectrum title never named
the loaded configuration. Found on 2026-09-29 by listing every guard a class puts on a name it
never holds.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN worker manager", main_windows_only=True)


class _Captured(Exception):
    """The worker was built: the test has what it needs."""


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def _capture_config_into(configs):
    def build(cfg):
        configs.append(cfg)
        raise _Captured

    return build


def test_the_local_polish_checkbox_reaches_the_global_worker(design_app, monkeypatch) -> None:
    configs = []
    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", _capture_config_into(configs))
    design_app.pre_polish_check.setChecked(True)

    # safe_ui_action turns the exception that stops the run into a log line.
    design_app.worker_manager.run_optim("global")

    [cfg] = configs
    assert cfg["pre_polish"] is True


def test_the_global_worker_does_not_polish_when_the_box_is_unchecked(design_app, monkeypatch) -> None:
    configs = []
    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", _capture_config_into(configs))
    design_app.pre_polish_check.setChecked(False)

    design_app.worker_manager.run_optim("global")

    [cfg] = configs
    assert cfg["pre_polish"] is False


def test_an_internal_restart_carries_the_best_rmse_to_its_worker(design_app, monkeypatch) -> None:
    workers = []

    class Worker:
        def __init__(self, cfg):
            self.cfg = cfg
            workers.append(self)

        def moveToThread(self, _thread):
            raise _Captured

    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", Worker)
    design_app._workflow_best_rmse = 0.0123

    design_app.worker_manager.run_optim("local", keep_history=True)

    [worker] = workers
    assert worker.best_rmse_seen == 0.0123


def test_the_spectrum_title_names_the_loaded_configuration(design_app, qapp) -> None:
    ended = []
    real_finished = design_app.worker_manager._on_eval_finished

    def finished(data, generation_id=None):
        # The evaluation that `load_config` starts arrives stale and is dropped by the window:
        # only the callback of the current generation says the title was drawn.
        current = generation_id == design_app._current_eval_generation
        real_finished(data, generation_id)
        if current:
            ended.append(1)

    design_app.worker_manager._on_eval_finished = finished
    assert Path(design_app._last_config_file).name == EXAMPLE.name

    design_app.run_eval()
    deadline = time.monotonic() + 120
    while not ended and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert ended, "the evaluation never finished"
    assert "JSON-design-example" in design_app.spectrum_plot.plotItem.titleLabel.text
