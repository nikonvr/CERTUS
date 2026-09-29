"""With the topology growth ticked, the global phase is the seed of the Needle, and is capped.

`WorkerManager.run_optim("global")` was written so: « if needle growth is enabled, use
ultra-fast global (just seed): the Needle will iterate and refine, no need for an exhaustive
global ». The checkbox was read on the manager (`getattr(self, "allow_growth_check", None)`),
which never holds it, so the cap was never applied: the global phase always ran with its full
budgets (150 000 evaluations, 6 000 points per 100, 50 cycles, 40 clusters by default) whatever
the box said. The owner accepted the change of behaviour on 2026-09-29: the box is ticked by
default, so the default global phase now runs at most 50 000 evaluations, 1 500 points per 100,
8 cycles and 5 clusters, and the Needle does the rest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "example" / "example_design" / "JSON-design-example.json"


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN global cap", main_windows_only=True)


class _Captured(Exception):
    """The worker configuration was built: the test has what it needs."""


@pytest.fixture
def design_app(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    app = CertusDesignApp()
    app.load_config(str(EXAMPLE))
    return app


def _global_config(app, monkeypatch, *, growth: bool, n100: int, cycles: int, clusters: int) -> dict:
    configs = []

    def build(cfg):
        configs.append(cfg)
        raise _Captured

    monkeypatch.setattr("certus.ui.certus_design_ui_worker.OptimWorker", build)
    app.allow_growth_check.setChecked(growth)
    app.n100_spin.setValue(n100)
    app.global_cycles_spin.setValue(cycles)
    app.max_clusters_spin.setValue(clusters)

    # safe_ui_action turns the exception that stops the run into a log line.
    app.worker_manager.run_optim("global")

    [cfg] = configs
    return cfg


def test_with_the_growth_ticked_the_global_phase_is_capped(design_app, monkeypatch) -> None:
    logs = []
    monkeypatch.setattr(design_app, "log", lambda message, level="INFO": logs.append(message))

    cfg = _global_config(design_app, monkeypatch, growth=True, n100=6000, cycles=50, clusters=40)

    assert (cfg["max_feval"], cfg["n100"], cfg["max_iter"], cfg["max_clusters"]) == (50000, 1500, 8, 5)
    assert "Global+Needle: ultra-fast global (seed for needle iterations)" in logs


def test_with_the_growth_unticked_the_global_phase_keeps_its_budgets(design_app, monkeypatch) -> None:
    from certus.core.certus_core import CFG

    cfg = _global_config(design_app, monkeypatch, growth=False, n100=6000, cycles=50, clusters=40)

    assert (cfg["max_feval"], cfg["n100"], cfg["max_iter"], cfg["max_clusters"]) == (
        CFG.MAX_FEVAL_GLOBAL,
        6000,
        50,
        40,
    )


def test_a_budget_already_under_the_cap_is_kept(design_app, monkeypatch) -> None:
    cfg = _global_config(design_app, monkeypatch, growth=True, n100=1000, cycles=3, clusters=5)

    assert (cfg["n100"], cfg["max_iter"], cfg["max_clusters"]) == (1000, 3, 5)
