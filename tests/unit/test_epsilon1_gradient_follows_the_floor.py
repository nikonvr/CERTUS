"""The analytic gradient of epsilon1 describes the epsilon1 that the cost uses, floor included (audit 2026-11-15, M-L1).

``epsilon1_TL_analytic`` floors epsilon1 at 1.0. ``_compute_epsilon1_gradient_kernel`` ignored the floor: where the model
is flat at 1.0 it returned the unfloored value (down to -6.4 on this oscillator) and a non-zero derivative, so the
optimiser followed a slope the cost does not have (86 of 161 points here).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_optical_models import epsilon1_TL_analytic
from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel

E = np.linspace(1.0, 9.0, 161)
PARAMS = {"Eg": 3.2, "A": 300.0, "E0": 4.5, "C": 1.0, "eps_inf": 1.0}
ROW = {"Eg": 1, "A": 2, "E0": 3, "C": 4, "eps_inf": 6}


def _eps1(**changed: float) -> np.ndarray:
    p = {**PARAMS, **changed}
    return epsilon1_TL_analytic(E, p["Eg"], p["A"], p["E0"], p["C"], p["eps_inf"])


def _kernel() -> np.ndarray:
    return _compute_epsilon1_gradient_kernel(E, *(PARAMS[k] for k in ("Eg", "A", "E0", "C", "eps_inf")))


def test_the_oscillator_reaches_the_floor() -> None:
    assert int((_eps1() == 1.0).sum()) > 50


def test_the_kernel_returns_the_floored_epsilon1() -> None:
    eps1, kern = _eps1(), _kernel()
    away_from_the_gap = np.abs(E - PARAMS["Eg"]) > 1e-9
    np.testing.assert_allclose(kern[0][away_from_the_gap], eps1[away_from_the_gap], rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("name", list(ROW))
def test_the_derivative_matches_a_finite_difference_of_the_model(name: str) -> None:
    h = 1e-6 * max(1.0, abs(PARAMS[name]))
    plus, minus = _eps1(**{name: PARAMS[name] + h}), _eps1(**{name: PARAMS[name] - h})
    finite_difference = (plus - minus) / (2.0 * h)
    floored = _eps1() == 1.0
    # A point is compared when it stays on the same side of the floor over the step, and away from the E = Eg singularity.
    same_side = ((plus == 1.0) == floored) & ((minus == 1.0) == floored)
    usable = same_side & np.isfinite(finite_difference) & (np.abs(E - PARAMS["Eg"]) > 1e-9)
    derivative = _kernel()[ROW[name]]
    scale = max(float(np.abs(finite_difference[usable]).max()), 1e-12)

    assert int((usable & floored).sum()) > 50
    np.testing.assert_array_equal(derivative[usable & floored], 0.0)
    assert float(np.abs(derivative[usable] - finite_difference[usable]).max()) < 1e-5 * scale
