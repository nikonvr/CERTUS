"""The Monte-Carlo estimate of the Pareto summary is seeded with the seed of the window.

`PlotManager._compute_pareto_mc_rmse` drew its generator from `getattr(self, "run_seed", 0)`,
read on the manager, which never holds it: the seed of the run was ignored and every estimate
used the seed 0. The exports and the other reads of the same manager already read `self.ui`.
Found on 2026-09-29 by listing every guard a class puts on a name it never holds.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest


class _Seeded(Exception):
    def __init__(self, seed):
        super().__init__(seed)
        self.seed = seed


def _seed_used(monkeypatch, **window):
    from certus.ui.certus_design_ui_plot import PlotManager

    def generator(seed=None):
        raise _Seeded(seed)

    monkeypatch.setattr(np.random, "default_rng", generator)
    with pytest.raises(_Seeded) as seeded:
        PlotManager(SimpleNamespace(**window))._compute_pareto_mc_rmse(np.array([100.0, 80.0]), 0.01)
    return seeded.value.seed


def test_the_estimate_is_seeded_with_the_seed_of_the_window(monkeypatch) -> None:
    assert _seed_used(monkeypatch, run_seed=7) == 7


def test_a_window_without_seed_keeps_the_seed_zero(monkeypatch) -> None:
    assert _seed_used(monkeypatch) == 0


def test_an_unset_seed_keeps_the_seed_zero(monkeypatch) -> None:
    assert _seed_used(monkeypatch, run_seed=None) == 0
