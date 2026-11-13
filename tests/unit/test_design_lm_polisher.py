"""The Nielsen-damped Levenberg-Marquardt polisher of DESIGN (audit 2026-11-13, reports/audits_2026-11-13/bilan.md §3).

On the 50/50 beamsplitter it reached the local optimum in 22 to 48 evaluations, which L-BFGS-B never reached in 800 to
2 700. These tests judge the algorithm on residuals written by hand, whose minimum is known.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_lm import lm_nielsen


def _rosenbrock(x):
    """Residuals (10 (x1 - x0^2), 1 - x0): minimum 0 at (1, 1), a curved valley."""
    r = np.array([10.0 * (x[1] - x[0] ** 2), 1.0 - x[0]])
    j = np.array([[-20.0 * x[0], 10.0], [-1.0, 0.0]])
    return r, j


def test_it_finds_the_minimum_of_a_curved_valley() -> None:
    x, cost, n_eval = lm_nielsen(_rosenbrock, np.array([-1.2, 1.0]), np.full(2, -5.0), np.full(2, 5.0))
    assert x == pytest.approx([1.0, 1.0], abs=1e-6)
    assert cost < 1e-12
    assert n_eval < 100


def test_a_lower_bound_is_kept_and_the_constrained_minimum_found() -> None:
    """With x0 >= 1.5 the minimum of the valley is out of reach: x0 sits on its bound, x1 = x0^2."""
    x, _cost, _n = lm_nielsen(_rosenbrock, np.array([2.0, 3.0]), np.array([1.5, -5.0]), np.full(2, 5.0))
    assert x[0] == pytest.approx(1.5)
    assert x[1] == pytest.approx(2.25, abs=1e-6)


def test_an_upper_bound_is_kept() -> None:
    def res_jac(x):
        return np.array([x[0] - 10.0]), np.array([[1.0]])

    x, cost, _n = lm_nielsen(res_jac, np.array([1.0]), np.array([0.0]), np.array([4.0]))
    assert x[0] == pytest.approx(4.0)
    assert cost == pytest.approx(36.0)


def test_it_never_ends_worse_than_it_started() -> None:
    """A Jacobian that lies cannot make the polisher accept a worse point."""

    def liar(x):
        return np.array([x[0] - 1.0, x[1] + 2.0]), -np.eye(2)

    x0 = np.array([0.3, 0.4])
    start = float(np.sum(liar(x0)[0] ** 2))
    x, cost, _n = lm_nielsen(liar, x0, np.full(2, -9.0), np.full(2, 9.0))
    assert cost <= start
    assert float(np.sum(liar(x)[0] ** 2)) == pytest.approx(cost)


def test_it_stops_at_its_evaluation_budget() -> None:
    _x, _cost, n_eval = lm_nielsen(_rosenbrock, np.array([-1.2, 1.0]), np.full(2, -5.0), np.full(2, 5.0), max_iter=3)
    assert n_eval <= 1 + 3
