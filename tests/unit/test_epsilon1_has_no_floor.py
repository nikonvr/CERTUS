"""epsilon1 of Tauc-Lorentz has no floor, and its analytic gradient is the derivative of that epsilon1 everywhere.

Until 2026-11-19 ``epsilon1_TL_analytic`` floored epsilon1 at 1.0 and the gradient kernel followed the floor (audit
2026-11-15, M-L1): above the resonance the model was flat at 1.0 where the Kramers-Kronig transform of epsilon2 goes
down to -6.4 on this oscillator (86 of 161 points). Decision of the owner (2026-11-19): the floor is removed, so that
epsilon1 is the Kramers-Kronig transform and its gradient is exact; ``epsilon_to_nk`` turns an epsilon1 below 1 or
below 0 into the n and k it means.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_optical_models import epsilon1_TL_analytic, epsilon_to_nk
from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel

E = np.linspace(1.0, 9.0, 161)
PARAMS = {"Eg": 3.2, "A": 300.0, "E0": 4.5, "C": 1.0, "eps_inf": 1.0}
ROW = {"Eg": 1, "A": 2, "E0": 3, "C": 4, "eps_inf": 6}
OVERDAMPED = {"Eg": 3.2, "A": 300.0, "E0": 2.0, "C": 4.5, "eps_inf": 1.0}


def _eps1(params: dict[str, float] = PARAMS, **changed: float) -> np.ndarray:
    p = {**params, **changed}
    return epsilon1_TL_analytic(E, p["Eg"], p["A"], p["E0"], p["C"], p["eps_inf"])


def _kernel(params: dict[str, float] = PARAMS) -> np.ndarray:
    return _compute_epsilon1_gradient_kernel(E, *(params[k] for k in ("Eg", "A", "E0", "C", "eps_inf")))


def test_the_oscillator_goes_below_one_and_below_zero() -> None:
    eps1 = _eps1()
    assert int((eps1 < 1.0).sum()) > 50
    assert float(eps1.min()) < 0.0


def test_the_overdamped_branch_has_no_floor_either() -> None:
    eps1 = _eps1(OVERDAMPED)
    kern = _kernel(OVERDAMPED)
    assert float(eps1.min()) < 1.0
    np.testing.assert_allclose(kern[0], eps1, rtol=1e-9, atol=1e-9)


def test_the_kernel_returns_the_model_epsilon1() -> None:
    eps1, kern = _eps1(), _kernel()
    away_from_the_gap = np.abs(E - PARAMS["Eg"]) > 1e-9
    np.testing.assert_allclose(kern[0][away_from_the_gap], eps1[away_from_the_gap], rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("name", list(ROW))
def test_the_derivative_matches_a_finite_difference_everywhere(name: str) -> None:
    h = 1e-6 * max(1.0, abs(PARAMS[name]))
    plus, minus = _eps1(**{name: PARAMS[name] + h}), _eps1(**{name: PARAMS[name] - h})
    finite_difference = (plus - minus) / (2.0 * h)
    usable = np.isfinite(finite_difference) & (np.abs(E - PARAMS["Eg"]) > 1e-9)
    derivative = _kernel()[ROW[name]]
    scale = max(float(np.abs(finite_difference[usable]).max()), 1e-12)

    below_one = usable & (_eps1() < 1.0)
    assert int(below_one.sum()) > 50
    assert float(np.abs(derivative[usable] - finite_difference[usable]).max()) < 1e-5 * scale


def test_epsilon_to_nk_turns_an_epsilon1_below_one_into_a_valid_index() -> None:
    eps1 = np.array([0.5, -2.0, 3.0])
    eps2 = np.array([0.2, 1.0, 0.01])
    n, k, valid = epsilon_to_nk(eps1, eps2, 0.0, 10.0, 10.0)

    assert valid
    np.testing.assert_allclose((n - 1j * k) ** 2, eps1 - 1j * eps2, rtol=1e-12)
    assert np.all(n > 0.0)
    assert np.all(k >= 0.0)
