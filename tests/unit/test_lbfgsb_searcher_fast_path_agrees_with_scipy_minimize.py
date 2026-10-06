"""The fast path of the L-BFGS-B searcher reaches the optimum scipy's `minimize` reaches (audit v2, plan S3.2).

`LBFGSBSearcher.search` (`certus/physics/certus_optimizers.py`, the local search of PGlobal) calls `scipy.optimize._lbfgsb.setulb` directly when a gradient is available and no callback is
asked for: a PRIVATE function of scipy, whose signature changed when L-BFGS-B was rewritten in C (the `ln_task` argument), called in a loop that follows its state machine by hand (task codes 3, 1,
5; the `isave[29]` iteration counter). If that private call raises `TypeError` or `AttributeError`, search retries through the public `minimize` API. CI still checks that the fast path works with
the installed scipy, so a performance loss remains visible.

What is pinned here, against `scipy.optimize.minimize` on problems whose optimum is known:

    the fast path RUNS with the installed scipy (the tripwire: a signature that changes fails here, with its own message)
    the public minimize path is used if the private call has an incompatible API
    it reaches the optimum of a quadratic, of a bounded quadratic whose minimum is outside the box (the bound), and of the Rosenbrock valley, to what `minimize` reaches
    the budget of evaluations stops it, and `nfev` counts the evaluations; the iteration budget stops it too
    a gradient given as a (value, gradient) pair, or failing at the probe, is handled; without a gradient the search falls back on finite differences
    the tolerance can be moved by CERTUS_LBFGSB_TOL and a bad value is ignored; the memory of the quasi-Newton update follows the dimension
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import minimize

from certus.physics.certus_optimizers import LBFGSBSearcher, get_lbfgsb_params

pytestmark = pytest.mark.kernels

CENTRE = np.array([1.5, -2.0, 0.7])
BOX = np.array([[-10.0, 10.0]] * 3)


def quadratic(x):
    return float(np.sum((x - CENTRE) ** 2))


def quadratic_gradient(x):
    return 2.0 * (x - CENTRE)


def rosenbrock(x):
    return float(100.0 * (x[1] - x[0] ** 2) ** 2 + (1.0 - x[0]) ** 2)


def rosenbrock_gradient(x):
    return np.array([-400.0 * x[0] * (x[1] - x[0] ** 2) - 2.0 * (1.0 - x[0]), 200.0 * (x[1] - x[0] ** 2)])


def searcher(function=quadratic, gradient=quadratic_gradient, box=BOX):
    return LBFGSBSearcher(function, box, gradient_func=gradient)


# --- the tripwire ------------------------------------------------------------------------------------------------------------------------------


def test_scipy_still_offers_the_private_function_the_fast_path_calls():
    assert LBFGSBSearcher._setulb is not None


def test_the_fast_path_runs_with_the_installed_scipy():
    s = searcher()
    x, value, evaluations = s._search_direct(np.zeros(3), 1000, quadratic_and_gradient)
    assert evaluations >= 1
    assert np.all(np.isfinite(x))
    assert np.isfinite(value)


@pytest.mark.parametrize("error", [TypeError, AttributeError])
def test_a_changed_private_setulb_api_falls_back_to_minimize(monkeypatch, error):
    s = searcher()
    calls = []

    def incompatible_setulb(*args):
        calls.append(1)
        raise error("setulb API changed")

    monkeypatch.setattr(s, "_setulb", incompatible_setulb)
    x, value, evaluations = s.search(np.zeros(3))
    assert calls == [1]
    np.testing.assert_allclose(x, CENTRE, atol=1e-6)
    assert value < 1e-10
    assert evaluations > 0


def quadratic_and_gradient(x):
    return quadratic(x), quadratic_gradient(x)


def test_search_takes_the_fast_path_when_a_gradient_is_there_and_no_callback_is_asked_for(monkeypatch):
    s = searcher()
    taken = []
    original = s._search_direct

    def spy(*args, **kwargs):
        taken.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(s, "_search_direct", spy)
    s.search(np.zeros(3))
    assert taken == [True]


def test_search_takes_scipys_minimize_when_a_callback_is_asked_for(monkeypatch):
    s = searcher()
    monkeypatch.setattr(s, "_search_direct", lambda *a, **k: pytest.fail("the fast path was taken with a callback"))
    seen = []
    s.search(np.zeros(3), callback=seen.append)
    assert seen  # the callback was called at every iteration


# --- the optimum -------------------------------------------------------------------------------------------------------------------------------


def test_the_fast_path_finds_the_minimum_of_a_quadratic():
    x, value, evaluations = searcher().search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, CENTRE, atol=1e-6)
    assert value < 1e-10
    assert 1 <= evaluations <= 50


def test_the_fast_path_and_scipys_minimize_reach_the_same_optimum():
    fast = searcher().search(np.array([5.0, 5.0, -5.0]), max_feval=1000)
    reference = minimize(quadratic, np.array([5.0, 5.0, -5.0]), jac=quadratic_gradient, method="L-BFGS-B", bounds=[tuple(b) for b in BOX])
    np.testing.assert_allclose(fast[0], reference.x, atol=1e-6)
    assert fast[1] == pytest.approx(reference.fun, abs=1e-10)


def test_a_minimum_outside_the_box_is_found_on_its_bound():
    box = np.array([[-10.0, 1.0], [-1.0, 10.0], [0.0, 0.5]])  # the centre (1.5, -2.0, 0.7) is outside the box on all three axes
    x, value, _ = searcher(box=box).search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, [1.0, -1.0, 0.5], atol=1e-9)
    assert value == pytest.approx(quadratic(np.array([1.0, -1.0, 0.5])), abs=1e-9)


def test_the_solution_never_leaves_the_box():
    box = np.array([[0.0, 1.0], [-1.0, 0.0], [0.0, 0.5]])
    x, _, _ = searcher(box=box).search(np.array([0.5, -0.5, 0.25]), max_feval=1000)
    assert np.all(x >= box[:, 0] - 1e-12)
    assert np.all(x <= box[:, 1] + 1e-12)


def test_the_fast_path_follows_the_rosenbrock_valley_like_scipy():
    box = np.array([[-5.0, 5.0], [-5.0, 5.0]])
    s = LBFGSBSearcher(rosenbrock, box, gradient_func=rosenbrock_gradient)
    x, value, _ = s.search(np.array([-1.2, 1.0]), max_feval=5000)
    np.testing.assert_allclose(x, [1.0, 1.0], atol=1e-4)
    assert value < 1e-8


# --- the budgets -------------------------------------------------------------------------------------------------------------------------------


def test_the_budget_of_evaluations_stops_the_fast_path():
    box = np.array([[-5.0, 5.0], [-5.0, 5.0]])
    s = LBFGSBSearcher(rosenbrock, box, gradient_func=rosenbrock_gradient)
    s._probe_gradient(np.array([-1.2, 1.0]))
    x, value, evaluations = s._search_direct(np.array([-1.2, 1.0]), 4, s._objective_fn)
    assert evaluations == 4
    assert value > 1e-3  # stopped far from the optimum, at an iterate that was evaluated
    assert np.all(np.isfinite(x))


def test_a_budget_big_enough_reaches_the_optimum_a_small_one_does_not():
    """The value returned is that of the LAST point evaluated, which in the middle of a line search is a trial and not always the best iterate: it is not monotone in the budget
    (4 evaluations: 5.7; 12: 41.4 on this start), so only the two ends are compared."""
    box = np.array([[-5.0, 5.0], [-5.0, 5.0]])
    s = LBFGSBSearcher(rosenbrock, box, gradient_func=rosenbrock_gradient)
    s._probe_gradient(np.array([-1.2, 1.0]))
    values = [s._search_direct(np.array([-1.2, 1.0]), budget, s._objective_fn)[1] for budget in (4, 200)]
    assert values[0] > 1.0
    assert values[1] < 1e-10


def test_the_evaluations_counted_are_those_of_the_objective():
    calls = []

    def counting(x):
        calls.append(1)
        return quadratic(x), quadratic_gradient(x)

    _, _, evaluations = searcher()._search_direct(np.zeros(3), 1000, counting)
    assert evaluations == len(calls)


def extended_rosenbrock(x):
    return float(np.sum(100.0 * (x[1:] - x[:-1] ** 2) ** 2 + (1.0 - x[:-1]) ** 2))


def extended_rosenbrock_gradient(x):
    g = np.zeros_like(x)
    g[:-1] += -400.0 * x[:-1] * (x[1:] - x[:-1] ** 2) - 2.0 * (1.0 - x[:-1])
    g[1:] += 200.0 * (x[1:] - x[:-1] ** 2)
    return g


def test_the_iteration_budget_stops_the_fast_path_too():
    """maxiter = max(100, max_feval // (n + 1)): with 20 variables and a budget of 2 000 evaluations that is 100 iterations, which cost ~110 evaluations; the search stops there, far from the optimum."""
    n = 20
    box = np.array([[-5.0, 5.0]] * n)
    s = LBFGSBSearcher(extended_rosenbrock, box, gradient_func=extended_rosenbrock_gradient)
    x0 = np.full(n, -1.2)
    x0[1::2] = 1.0
    s._probe_gradient(x0)
    _, short_value, short_evals = s._search_direct(x0, 2000, s._objective_fn)
    _, long_value, long_evals = s._search_direct(x0, 100000, s._objective_fn)
    assert short_evals < 400  # the evaluation budget (2 000) was not what stopped it
    assert short_value > 1e-3  # and it did not converge
    assert long_evals > short_evals
    assert long_value < short_value / 100.0


# --- the gradient ------------------------------------------------------------------------------------------------------------------------------


def test_a_gradient_given_as_a_value_and_gradient_pair_is_used():
    def pair(x):
        return quadratic(x), quadratic_gradient(x)

    s = LBFGSBSearcher(quadratic, BOX, gradient_func=pair)
    x, value, _ = s.search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, CENTRE, atol=1e-6)
    assert value < 1e-10


def test_a_gradient_that_returns_none_leaves_the_function_to_finite_differences():
    s = LBFGSBSearcher(quadratic, BOX, gradient_func=lambda x: None)
    x, value, _ = s.search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, CENTRE, atol=1e-5)
    assert value < 1e-9


def test_a_gradient_that_fails_at_the_probe_falls_back_on_finite_differences():
    def broken(x):
        raise ValueError("no gradient here")

    s = LBFGSBSearcher(quadratic, BOX, gradient_func=broken)
    x, value, _ = s.search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, CENTRE, atol=1e-5)
    assert value < 1e-9


def test_without_a_gradient_the_search_still_converges():
    s = LBFGSBSearcher(quadratic, BOX)
    x, value, _ = s.search(np.zeros(3), max_feval=1000)
    np.testing.assert_allclose(x, CENTRE, atol=1e-5)
    assert value < 1e-9


def test_a_numerical_failure_during_the_search_returns_the_start_and_one_evaluation():
    x0 = np.array([1.0, 2.0, 3.0])

    def fails_everywhere_but_at_the_start(x):
        if np.array_equal(x, x0):
            return quadratic(x)
        raise ValueError("the objective blew up away from the start")

    s = LBFGSBSearcher(fails_everywhere_but_at_the_start, BOX)  # no gradient: finite differences evaluate the function next to the start
    x, value, evaluations = s.search(x0, max_feval=10)
    np.testing.assert_array_equal(x, x0)
    assert value == quadratic(x0)
    assert evaluations == 1
    assert x is not x0  # a copy


# --- the parameters ----------------------------------------------------------------------------------------------------------------------------


def test_the_tolerances_are_tight_by_default():
    params = get_lbfgsb_params(3)
    assert params["ftol"] == 1e-12
    assert params["gtol"] == 1e-10


def test_the_tolerance_can_be_moved_by_the_environment_and_a_bad_value_is_ignored(monkeypatch):
    monkeypatch.setenv("CERTUS_LBFGSB_TOL", "1e-8")
    assert get_lbfgsb_params(3)["ftol"] == 1e-8
    monkeypatch.setenv("CERTUS_LBFGSB_TOL", "not a number")
    assert get_lbfgsb_params(3)["ftol"] == 1e-12


@pytest.mark.parametrize(("dim", "memory"), [(2, 20), (10, 20), (30, 35), (45, 50), (400, 50)])
def test_the_memory_of_the_quasi_newton_update_follows_the_dimension(dim, memory):
    assert get_lbfgsb_params(dim)["maxcor"] == memory
