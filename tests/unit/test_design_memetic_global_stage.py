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


def _window_global_cfg(qapp, monkeypatch, config_path=None, **kwargs) -> dict:
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
    app.load_config(str(config_path or EXAMPLE))
    app.run_optim("global", **kwargs)
    app.optim_thread.quit()
    app.optim_thread.wait(5000)
    [cfg] = captured
    return cfg


def test_the_optional_steps_reach_the_worker_only_when_the_file_names_them(qapp, monkeypatch, tmp_path) -> None:
    import json

    from certus.core.certus_design_workers_dto import DESIGN_OPTIONAL_STEPS

    assert not set(DESIGN_OPTIONAL_STEPS) & set(_window_global_cfg(qapp, monkeypatch))

    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data.setdefault("optimization", {}).update({"gauss_newton_max_iter": 7, "restart_flip_alternation": True})
    path = tmp_path / "with_steps.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    cfg = _window_global_cfg(qapp, monkeypatch, config_path=path)
    assert cfg["gauss_newton_max_iter"] == 7
    assert cfg["restart_flip_alternation"] is True


@pytest.mark.parametrize(("kwargs", "stage"), [({}, "memetic"), ({"memetic_children": 0}, "pglobal")])
def test_the_global_stage_is_memetic_unless_memetic_children_is_zero(qapp, monkeypatch, kwargs, stage) -> None:
    import certus.workers.certus_design_workers as workers

    cfg = _window_global_cfg(qapp, monkeypatch, **kwargs)
    called = []
    monkeypatch.setattr(workers, "run_pglobal_restart_loop", lambda **k: called.append("pglobal"))
    monkeypatch.setattr(workers.OptimWorker, "_run_memetic_global", lambda self, **k: called.append("memetic"))

    workers.OptimWorker(cfg).run()

    assert called == [stage]


def test_the_final_refinement_keeps_every_layer_at_or_above_the_memetic_floor(qapp, monkeypatch) -> None:
    import certus.core.certus_design_memetic as memetic
    import certus.workers.certus_design_workers as workers

    cfg = _window_global_cfg(qapp, monkeypatch, memetic_children=2, memetic_population=2)
    cfg["final_refine_lower_bounds"] = True  # optional step, off by default
    n = len(cfg["ep0"])
    x_at_floor = np.full(n, 5.0, dtype=np.float64)
    monkeypatch.setattr(
        memetic,
        "run_memetic",
        lambda cost_and_grad, bounds, **k: memetic.MemeticResult(x=x_at_floor.copy(), y=float(np.sum(x_at_floor)), evaluations=1),
    )
    monkeypatch.setattr(
        workers.OptimWorker,
        "_get_gradient_analytic",
        lambda self, ep, **k: (float(np.sum(ep)), np.ones(n, dtype=np.float64)),
    )
    monkeypatch.setattr(
        workers.OptimWorker,
        "_evaluate_thicknesses",
        lambda self, ep, **k: float(np.sum(ep)),
    )
    finished = []
    worker = workers.OptimWorker(cfg)
    worker.signals.finished.connect(finished.append)

    worker.run()

    assert len(finished) == 1
    assert np.min(finished[0]["ep"]) >= 5.0


def test_prune_merge_shift_escapes_a_basin_by_merging_neighbours_of_a_thin_layer() -> None:
    """When an interior layer is thin (at the floor), merging its two neighbours crosses into the cavity basin."""
    from certus.core.certus_design_memetic import run_memetic

    # Below 135 nm every start falls into x_local = [80, 5, 80, 70, 70, 70] (cost 1.0), where layer 1 sits at the 5 nm
    # floor between two 80 nm layers. Merging x[0] + x[2] = 160 nm crosses the 135 nm barrier into the 160 nm cavity
    # basin (cost 0.0), which block crossover + 2% jitter from <= 100 nm starts cannot reach.
    def cavity_landscape(x: np.ndarray) -> tuple[float, np.ndarray]:
        local_t = np.array([80.0, 5.0, 80.0, 70.0, 70.0, 70.0])
        # Smooth double-well on the cavity coordinate (either x[0] after left-shift or x[2] after right-shift).
        c_local = 1.0 + 1e-3 * float(np.sum((x - local_t) ** 2))
        g_local = 2e-3 * (x - local_t)
        best_c, best_g = c_local, g_local
        for cav_idx, target in (
            (0, np.array([160.0, 70.0, 70.0, 70.0, 70.0, 70.0])),
            (2, np.array([5.0, 70.0, 160.0, 70.0, 70.0, 70.0])),
        ):
            if x[cav_idx] > 135.0:
                c_cav = 1e-3 * float(np.sum((x - target) ** 2))
                if c_cav < best_c:
                    best_c = c_cav
                    best_g = 2e-3 * (x - target)
        return best_c, best_g

    init_bounds = np.array([[5.0, 100.0]] * 6)
    wide_bounds = np.array([[5.0, 300.0]] * 6)
    res = run_memetic(
        cavity_landscape, wide_bounds, x0=None, population=6, children=40, seed=3, init_bounds=init_bounds,
        merge_shift_every=4,
    )
    assert res.y < 0.01

    # Off by default (the behaviour before the operator): block crossover alone stays in the local basin.
    res_off = run_memetic(cavity_landscape, wide_bounds, x0=None, population=6, children=40, seed=3, init_bounds=init_bounds)
    assert res_off.y > 0.5


def _counted(fun):
    """`fun` with a count of its calls and the threads that made them."""
    import threading

    lock, seen = threading.Lock(), {"calls": 0, "threads": set()}

    def wrapped(x: np.ndarray) -> tuple[float, np.ndarray]:
        with lock:
            seen["calls"] += 1
            seen["threads"].add(threading.get_ident())
        return fun(x)

    return wrapped, seen


def test_a_pool_polishes_designs_at_once_and_the_children_still_improve() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from certus.core.certus_design_memetic import run_memetic

    bounds = np.array([[-5.12, 5.12]] * 6)
    initial = run_memetic(_rastrigin, bounds, x0=None, population=8, children=0, seed=7)
    cost, seen = _counted(_rastrigin)
    with ThreadPoolExecutor(4) as pool:
        evolved = run_memetic(cost, bounds, x0=None, population=8, children=200, seed=7, pool=pool, batch=4)

    assert evolved.y < initial.y
    assert np.all(evolved.x >= bounds[:, 0])
    assert np.all(evolved.x <= bounds[:, 1])
    assert len(seen["threads"]) > 1
    assert evolved.evaluations == seen["calls"]


def test_the_pool_polishes_the_starts_of_the_sequential_search() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from certus.core.certus_design_memetic import run_memetic

    bounds = np.array([[-5.12, 5.12]] * 5)
    alone = run_memetic(_rastrigin, bounds, x0=None, population=7, children=0, seed=3)
    with ThreadPoolExecutor(3) as pool:
        pooled = run_memetic(_rastrigin, bounds, x0=None, population=7, children=0, seed=3, pool=pool, batch=3)

    assert pooled.y == alone.y
    assert np.array_equal(pooled.x, alone.x)


def test_a_pooled_search_is_reproducible_for_a_given_seed() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from certus.core.certus_design_memetic import run_memetic

    bounds = np.array([[-5.12, 5.12]] * 6)
    runs = []
    for _ in range(2):
        with ThreadPoolExecutor(4) as pool:
            runs.append(run_memetic(_rastrigin, bounds, x0=None, population=8, children=60, seed=5, pool=pool,
                                    batch=4, screen_maxiter=5))

    assert runs[0].y == runs[1].y
    assert np.array_equal(runs[0].x, runs[1].x)
    assert runs[0].evaluations == runs[1].evaluations


@pytest.mark.parametrize(("workers", "batch"), [(None, 1), (3, 3), (0, "cores")])
def test_memetic_workers_reaches_the_memetic_search_as_a_pool(qapp, monkeypatch, workers, batch) -> None:
    import certus.core.certus_design_memetic as memetic
    import certus.workers.certus_design_workers as design_workers
    from certus_physics import PGlobalOptimizer

    cfg = _window_global_cfg(qapp, monkeypatch, memetic_children=2, memetic_population=2)
    if workers is not None:
        cfg["memetic_workers"] = workers  # optional step, 1 (one design after another) by default
    seen = {}

    def fake_run_memetic(cost_and_grad, bounds, **k):
        seen.update(pool=k["pool"], batch=k["batch"])
        return memetic.MemeticResult(x=np.full(len(bounds), 50.0), y=1.0, evaluations=1)

    monkeypatch.setattr(memetic, "run_memetic", fake_run_memetic)
    monkeypatch.setattr(design_workers.OptimWorker, "_get_gradient_analytic",
                        lambda self, ep, **k: (float(np.sum(ep)), np.ones(len(ep), dtype=np.float64)))
    monkeypatch.setattr(design_workers.OptimWorker, "_evaluate_thicknesses", lambda self, ep, **k: float(np.sum(ep)))

    design_workers.OptimWorker(cfg).run()

    expected = PGlobalOptimizer._resolve_worker_count() if batch == "cores" else batch
    assert seen["batch"] == expected
    if expected > 1:
        assert seen["pool"]._max_workers == expected
        assert seen["pool"]._shutdown  # the worker closes its pool
    else:
        assert seen["pool"] is None


