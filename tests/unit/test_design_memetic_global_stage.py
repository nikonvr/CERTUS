"""DESIGN's memetic global stage: inactive by default, and a search that improves on its population.

`certus/core/certus_design_memetic.py` recombines polished designs by blocks of layers. On the 50/50
splitter 400-1200 nm it reached RMSE 1.7e-4 where the PGLOBAL workflow reached 1.8e-3 to 4.2e-3
(reports/DESIGN_bs5050_2026-10-22/journal.md). OptimWorker takes it when the configuration holds
``memetic_children`` > 0; since 2026-10-23 the window asks for 1000 children by default (owner's decision),
and ``memetic_children=0`` (or the window's ``_memetic_children = 0``) brings back PGLOBAL.
"""

from __future__ import annotations

from pathlib import Path
from threading import Event

import numpy as np
import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


def _rastrigin(x: np.ndarray) -> tuple[float, np.ndarray]:
    a = 10.0
    c = a * len(x) + float(np.sum(x * x - a * np.cos(2 * np.pi * x)))
    g = 2 * x + 2 * np.pi * a * np.sin(2 * np.pi * x)
    return c, g


def test_the_children_improve_on_the_initial_population() -> None:
    from certus.core.certus_design_memetic import run_memetic

    bounds = np.array([[-5.12, 5.12]] * 6)
    initial = run_memetic(_rastrigin, bounds, x0=None, population=8, children=0, seed=7)
    evolved = run_memetic(_rastrigin, bounds, x0=None, population=8, children=200, seed=7)

    assert evolved.y < initial.y
    assert np.all(evolved.x >= bounds[:, 0])
    assert np.all(evolved.x <= bounds[:, 1])


def test_a_stop_request_ends_the_search_before_its_children() -> None:
    from certus.core.certus_design_memetic import run_memetic

    stop = Event()
    stop.set()
    result = run_memetic(_rastrigin, np.array([[-5.12, 5.12]] * 4), x0=np.zeros(4), population=8, children=500,
                         seed=1, stop_event=stop)

    assert result.evaluations < 50  # the starting design is polished, nothing else


def test_the_upper_bounds_are_widened_to_the_quarter_waves_asked() -> None:
    from certus.core.certus_design_memetic import widen_upper_bounds

    wide = widen_upper_bounds(np.array([[0.0, 60.0], [0.0, 500.0]]), np.array([50.0, 100.0]), 3.0)

    assert wide.tolist() == [[0.0, 150.0], [0.0, 500.0]]


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN memetic stage", main_windows_only=True)


def _window_global_cfg(qapp, monkeypatch, **kwargs) -> dict:
    """The configuration the window gives OptimWorker for its global stage (nothing is computed)."""
    from PyQt6.QtCore import QObject

    import certus.ui.certus_design_ui_worker as ui_worker
    from certus.ui.certus_design_ui import CertusDesignApp
    from certus.workers.certus_base_workers import WorkerSignals

    captured = []

    class Recorder(QObject):
        def __init__(self, cfg) -> None:
            super().__init__()
            captured.append(dict(cfg))
            self.signals = WorkerSignals()

        def run(self) -> None:
            pass

    monkeypatch.setattr(ui_worker, "OptimWorker", Recorder)
    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    app.run_optim("global", **kwargs)
    app.optim_thread.quit()
    app.optim_thread.wait(5000)
    [cfg] = captured
    return cfg


@pytest.mark.parametrize(("kwargs", "stage"), [({}, "memetic"), ({"memetic_children": 0}, "pglobal")])
def test_the_global_stage_is_memetic_unless_memetic_children_is_zero(qapp, monkeypatch, kwargs, stage) -> None:
    import certus.workers.certus_design_workers as workers

    cfg = _window_global_cfg(qapp, monkeypatch, **kwargs)
    called = []
    monkeypatch.setattr(workers, "run_pglobal_restart_loop", lambda **k: called.append("pglobal"))
    monkeypatch.setattr(workers.OptimWorker, "_run_memetic_global", lambda self, **k: called.append("memetic"))

    workers.OptimWorker(cfg).run()

    assert called == [stage]
