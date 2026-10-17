"""The cost of the METAL BILAYER beam analysis is the objective of the global optimization (D40).

The beam analysis re-optimises the stack at each metal thickness from the global optimum with `compute_metal_bilayer_gradient_analytic`;
its cost was the reflectance MSE alone, while the global objective adds a smoothness penalty on n and k (1e-2 times the squared second
differences). Two functions: the MSE found at a scanned thickness could not be compared with the optimum it started from, nor with the
threshold built from it (`1.25 * optimal_mse`). METAL SINGLE had been fixed in D76; the bilayer analytic gradient had not.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.metal.certus_metal_bilayer_physics import global_objective_function, objective_function_fixed_eM
from certus.physics.gradient_metal import compute_metal_bilayer_gradient_analytic

NUM_KNOTS = 5
L_ARRAY = np.linspace(450.0, 1100.0, 80)
# A target that no smooth spline reproduces: the optimum is not at zero penalty
TARGET = 0.45 + 0.08 * np.sin(L_ARRAY / 37.0)
SUBSTRATE = np.full(L_ARRAY.size, complex(3.8, -0.02), dtype=np.complex128)


def _x(wiggly: bool) -> np.ndarray:
    """[eM, eL, n_inf, A, n knots, k knots, inner lambdas] : a spline whose second differences are not zero when `wiggly`."""
    n_knots = np.array([2.6, 2.1, 2.7, 2.0, 2.4]) if wiggly else np.linspace(2.6, 2.0, NUM_KNOTS)
    k_knots = np.array([0.9, 0.3, 0.8, 0.35, 0.6]) if wiggly else np.linspace(0.9, 0.4, NUM_KNOTS)
    inner = np.linspace(L_ARRAY.min() + 150.0, L_ARRAY.max() - 150.0, NUM_KNOTS - 2)
    return np.concatenate(([30.0, 95.0, 1.46, 2500.0], n_knots, k_knots, inner))


@pytest.mark.parametrize("wiggly", [False, True], ids=["smooth", "wiggly"])
def test_the_beam_analysis_cost_is_the_objective_of_the_global_optimization(wiggly) -> None:
    x = _x(wiggly)
    cost, _gradient = compute_metal_bilayer_gradient_analytic(x, NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE)

    assert cost == pytest.approx(global_objective_function(x, NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE), rel=1e-9)
    assert cost == pytest.approx(objective_function_fixed_eM(x[1:], x[0], NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE), rel=1e-9)


def test_the_gradient_is_the_derivative_of_that_objective_on_the_spline_nodes() -> None:
    """Central differences of the OBJECTIVE (not of the analytic cost): the penalty's derivative must be in the gradient."""
    x = _x(True)
    _cost, gradient = compute_metal_bilayer_gradient_analytic(x, NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE)
    for index in range(4, 4 + 2 * NUM_KNOTS):  # n and k nodes: where the penalty acts
        step = 1e-6
        up, down = x.copy(), x.copy()
        up[index] += step
        down[index] -= step
        numeric = (
            global_objective_function(up, NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE)
            - global_objective_function(down, NUM_KNOTS, L_ARRAY, TARGET, 1.0, SUBSTRATE)
        ) / (2 * step)
        assert gradient[index] == pytest.approx(numeric, rel=5e-3, abs=1e-9), index
