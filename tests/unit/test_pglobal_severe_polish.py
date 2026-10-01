"""`_severe_polish` re-polishes the best vector of the PGlobal adapter and never makes it worse (audit v2, plan S5.2).

It was the last stage of `run_pglobal_optimization` (335 lines): a few tighter L-BFGS-B restarts from small random perturbations of the best vector, each kept only if its cost is no worse. The
unit tests of the adapter stop before it, so it is pinned on a quadratic bowl whose minimum is known: it improves a start that is off the minimum, leaves an optimal start alone, survives an
objective that raises, takes its settings from the environment, is repeatable for a given seed, and says what it does in the progress log.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from certus.metal import pglobal_adapter
from certus.metal.pglobal_adapter import _severe_polish

CENTRE = np.array([1.0, -2.0, 0.5])
BOUNDS = np.array([[-5.0, 5.0], [-5.0, 5.0], [-5.0, 5.0]])


def bowl(x: np.ndarray) -> float:
    return float(np.sum((np.asarray(x) - CENTRE) ** 2))


def run(start, objective=bowl, *, logger=None, ultra_wide=False, seed="12345"):
    start = np.asarray(start, dtype=np.float64)
    return _severe_polish(objective, ultra_wide, logger, BOUNDS, 2000, "[T]", start.copy(), objective(start), seed)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    """Small, fixed settings: three restarts, a modest iteration cap, and no seed taken from the shell."""
    monkeypatch.setenv("CERTUS_METAL_SEVERE_POLISH_RESTARTS", "3")
    monkeypatch.delenv("CERTUS_METAL_SEVERE_POLISH_SEED", raising=False)
    monkeypatch.delenv("CERTUS_METAL_SEVERE_POLISH_MAXITER", raising=False)
    monkeypatch.delenv("CERTUS_METAL_SEVERE_POLISH_SPAN_SCALE", raising=False)


def test_it_returns_the_cost_then_the_vector_and_improves_a_start_off_the_minimum():
    final_fun, final_x = run([1.3, -1.8, 0.9])
    assert final_fun < bowl([1.3, -1.8, 0.9])
    assert final_fun == pytest.approx(bowl(final_x))
    np.testing.assert_allclose(final_x, CENTRE, atol=1e-4)


def test_it_never_returns_a_worse_cost_than_it_was_given():
    final_fun, _ = run(CENTRE)
    assert final_fun <= 1e-12


def test_a_restart_that_stops_short_of_the_start_is_rejected(monkeypatch):
    """One iteration per restart: the perturbed starts end above the optimum they began from, and the guard must not take them."""
    monkeypatch.setenv("CERTUS_METAL_SEVERE_POLISH_MAXITER", "1")
    lines: list[str] = []
    final_fun, final_x = run(CENTRE, logger=lines.append)
    assert final_fun <= 1e-12
    np.testing.assert_allclose(final_x, CENTRE, atol=1e-6)
    assert any("severe_polish rejected" in line for line in lines)


def test_it_keeps_the_start_when_every_restart_fails_and_says_so():
    lines: list[str] = []

    def broken(x):
        raise RuntimeError("objective down")

    final_fun, final_x = _severe_polish(broken, False, lines.append, BOUNDS, 2000, "[T]", np.array([0.0, 0.0, 0.0]), 7.5, "12345")
    assert final_fun == 7.5
    np.testing.assert_array_equal(final_x, [0.0, 0.0, 0.0])
    assert sum("severe_polish failed" in line for line in lines) == 3
    assert "objective down" in next(line for line in lines if "severe_polish failed" in line)


def test_the_log_opens_with_the_settings_and_closes_with_the_best_rmse():
    lines: list[str] = []
    run([1.3, -1.8, 0.9], logger=lines.append)
    assert lines[0].startswith("[T] severe_polish start | restarts=3 | span_scale=0.012 | maxiter=800")
    assert lines[-1].startswith("[T] severe_polish end | best_rmse=")
    assert any("severe_polish accepted" in line for line in lines)


def test_without_a_logger_it_stays_silent_and_works():
    final_fun, _ = run([1.3, -1.8, 0.9], logger=None)
    assert final_fun < 0.3


def test_ultra_wide_runs_use_wider_defaults(monkeypatch):
    monkeypatch.delenv("CERTUS_METAL_SEVERE_POLISH_RESTARTS")
    lines: list[str] = []
    run([1.3, -1.8, 0.9], logger=lines.append, ultra_wide=True)
    assert "restarts=6 | span_scale=0.02" in lines[0]


def test_the_environment_overrides_the_settings(monkeypatch):
    monkeypatch.setenv("CERTUS_METAL_SEVERE_POLISH_SPAN_SCALE", "0.05")
    monkeypatch.setenv("CERTUS_METAL_SEVERE_POLISH_MAXITER", "900")
    lines: list[str] = []
    run([1.3, -1.8, 0.9], logger=lines.append)
    assert "span_scale=0.05 | maxiter=900" in lines[0]


def test_a_given_seed_repeats_the_same_result_and_a_non_numeric_one_falls_back_to_a_fixed_seed():
    first = run([1.3, -1.8, 0.9], seed="777")
    second = run([1.3, -1.8, 0.9], seed="777")
    assert first[0] == second[0]
    np.testing.assert_array_equal(first[1], second[1])
    odd = run([1.3, -1.8, 0.9], seed="not-a-number")
    again = run([1.3, -1.8, 0.9], seed="also-not-a-number")
    np.testing.assert_array_equal(odd[1], again[1])
    fixed = run([1.3, -1.8, 0.9], seed="24680")  # the fallback seed is 24680
    np.testing.assert_array_equal(odd[1], fixed[1])


@pytest.mark.parametrize(("seed", "generator_seed"), [("777", 777), ("not-a-number", 24680)], ids=["numeric seed", "fallback seed"])
def test_the_first_restart_starts_at_the_best_vector_and_the_others_at_seeded_perturbations(monkeypatch, seed, generator_seed):
    starts: list[np.ndarray] = []

    def recorder(fun, x0, **kwargs):
        starts.append(np.array(x0, dtype=np.float64))
        return SimpleNamespace(fun=float("inf"), x=np.asarray(x0))

    monkeypatch.setattr(pglobal_adapter, "minimize", recorder)
    best = np.array([1.3, -1.8, 0.9])
    run(best, seed=seed)
    assert len(starts) == 3
    np.testing.assert_array_equal(starts[0], best)
    rng = np.random.default_rng(generator_seed)
    span = BOUNDS[:, 1] - BOUNDS[:, 0]
    for restart in (1, 2):
        expected = np.clip(best + rng.normal(0.0, 0.012, size=3) * span, BOUNDS[:, 0], BOUNDS[:, 1])
        np.testing.assert_allclose(starts[restart], expected)


def test_the_optimisation_calls_it_only_when_the_severe_polish_is_enabled():
    source = inspect.getsource(pglobal_adapter.run_pglobal_optimization)
    assert "final_fun, final_x = _severe_polish(" in source
    assert "if severe_polish_enabled and final_x.size > 0:" in source
