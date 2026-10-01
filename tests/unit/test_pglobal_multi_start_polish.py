"""`_multi_start_polish` is the first polish of the PGlobal adapter: L-BFGS-B from the best vector and from seeded perturbations of it (audit v2, plan S5.2).

It was the middle of `run_pglobal_optimization` (335 lines, no unit test reaches it). It is pinned on a quadratic bowl whose minimum is known and on a recorder that replaces `minimize` to
see exactly where each restart starts: the first restart is the best vector itself, the others are `clip(best + N(0, scale_k) * span)` with scales going from 0.015 to 0.05 (0.08 for an
ultra-wide search), drawn in order from a generator seeded by `CERTUS_METAL_POLISH_SEED`. The seed is handed back: the severe polish that follows reuses it.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.metal import pglobal_adapter
from certus.metal.pglobal_adapter import _multi_start_polish

CENTRE = np.array([1.0, -2.0, 0.5])
BOUNDS = np.array([[-5.0, 5.0], [-5.0, 5.0], [-5.0, 5.0]])
SPAN = BOUNDS[:, 1] - BOUNDS[:, 0]


def bowl(x: np.ndarray) -> float:
    return float(np.sum((np.asarray(x) - CENTRE) ** 2))


def run(start, objective=bowl, *, logger=None, ultra_wide=False, budget=2000):
    start = np.asarray(start, dtype=np.float64)
    return _multi_start_polish(objective, ultra_wide, logger, BOUNDS, budget, "[T]", start.copy(), objective(start))


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    for name in ("CERTUS_METAL_POLISH_SEED", "CERTUS_METAL_POLISH_RESTARTS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def starts(monkeypatch):
    """Every start vector handed to `minimize`, in order; `minimize` itself is replaced by something that never improves."""
    seen: list[np.ndarray] = []
    kwargs: list[dict] = []

    def recorder(fun, x0, **options):
        seen.append(np.array(x0, dtype=np.float64))
        kwargs.append(options)
        return SimpleNamespace(fun=float("inf"), x=np.asarray(x0))

    monkeypatch.setattr(pglobal_adapter, "minimize", recorder)
    return seen, kwargs


def test_it_improves_a_start_off_the_minimum_and_returns_the_default_seed():
    final_fun, final_x, seed = run([1.4, -1.7, 0.9])
    assert final_fun < bowl([1.4, -1.7, 0.9])
    np.testing.assert_allclose(final_x, CENTRE, atol=1e-4)
    assert seed == "12345"


def test_the_default_run_has_one_restart_from_the_best_vector_and_four_perturbed_ones(starts):
    seen, _ = starts
    best = np.array([1.4, -1.7, 0.9])
    run(best)
    assert len(seen) == 5
    np.testing.assert_array_equal(seen[0], best)
    rng = np.random.default_rng(12345)
    for k, scale in enumerate(np.linspace(0.015, 0.05, 4), start=1):
        expected = np.clip(best + rng.normal(0.0, scale, size=3) * SPAN, BOUNDS[:, 0], BOUNDS[:, 1])
        np.testing.assert_allclose(seen[k], expected)


def test_an_ultra_wide_search_restarts_more_and_perturbs_more(starts):
    seen, _ = starts
    best = np.array([1.4, -1.7, 0.9])
    run(best, ultra_wide=True)
    assert len(seen) == 7
    rng = np.random.default_rng(12345)
    scales = np.linspace(0.015, 0.08, 6)
    for k, scale in enumerate(scales, start=1):
        expected = np.clip(best + rng.normal(0.0, scale, size=3) * SPAN, BOUNDS[:, 0], BOUNDS[:, 1])
        np.testing.assert_allclose(seen[k], expected)


def test_the_environment_sets_the_seed_and_the_number_of_restarts(starts, monkeypatch):
    monkeypatch.setenv("CERTUS_METAL_POLISH_SEED", "777")
    monkeypatch.setenv("CERTUS_METAL_POLISH_RESTARTS", "2")
    seen, _ = starts
    best = np.array([1.4, -1.7, 0.9])
    _, _, seed = run(best)
    assert seed == "777"
    assert len(seen) == 3
    rng = np.random.default_rng(777)
    expected = np.clip(best + rng.normal(0.0, 0.015, size=3) * SPAN, BOUNDS[:, 0], BOUNDS[:, 1])
    np.testing.assert_allclose(seen[1], expected)


def test_a_seed_that_is_not_a_number_falls_back_to_12345_but_is_handed_back_as_given(starts, monkeypatch):
    monkeypatch.setenv("CERTUS_METAL_POLISH_SEED", "banana")
    seen, _ = starts
    best = np.array([1.4, -1.7, 0.9])
    _, _, seed = run(best)
    assert seed == "banana"
    rng = np.random.default_rng(12345)
    expected = np.clip(best + rng.normal(0.0, 0.015, size=3) * SPAN, BOUNDS[:, 0], BOUNDS[:, 1])
    np.testing.assert_allclose(seen[1], expected)


@pytest.mark.parametrize(("budget", "expected"), [(800, 300), (8000, 1000), (40000, 3000)], ids=["floor", "budget over eight", "ceiling"])
def test_the_iteration_cap_follows_the_budget(starts, budget, expected):
    _, kwargs = starts
    run([1.4, -1.7, 0.9], budget=budget)
    assert kwargs[0]["options"]["maxiter"] == expected


def test_it_never_returns_a_worse_cost_than_it_was_given(monkeypatch):
    """One iteration per restart from perturbed starts ends above the optimum the search began at: the guard keeps the optimum."""
    real = pglobal_adapter.minimize
    monkeypatch.setattr(pglobal_adapter, "minimize", lambda fun, x0, **options: real(fun, x0, **{**options, "options": {**options["options"], "maxiter": 1}}))
    final_fun, final_x, _ = run(CENTRE)
    assert final_fun <= 1e-12
    np.testing.assert_allclose(final_x, CENTRE, atol=1e-6)


def test_a_failing_objective_keeps_the_start_and_is_logged_for_every_restart():
    lines: list[str] = []

    def broken(x):
        raise RuntimeError("objective down")

    final_fun, final_x, _ = _multi_start_polish(broken, False, lines.append, BOUNDS, 2000, "[T]", np.zeros(3), 7.5)
    assert final_fun == 7.5
    np.testing.assert_array_equal(final_x, np.zeros(3))
    assert sum("polish failed" in line for line in lines) == 5
    assert "objective down" in lines[0]


def test_accepted_and_rejected_restarts_are_logged_with_their_number():
    lines: list[str] = []
    run([1.4, -1.7, 0.9], logger=lines.append)
    assert any("polish accepted | restart=0/4" in line for line in lines)


def test_the_optimisation_uses_the_returned_seed_for_the_severe_polish():
    source = inspect.getsource(pglobal_adapter.run_pglobal_optimization)
    assert "final_fun, final_x, rng_seed = _multi_start_polish(" in source
    assert "rng_seed," in source
