"""The memetic stage may judge its population by a robust cost (`memetic_robust_sigma_nm`, 2026-11-13, off by default).

The polish stays nominal; only the cost it returns, by which the population is ranked, adds sigma^2 * sum |dr/dd_i|^2:
the expected increase of the mean squared error under independent thickness errors of standard deviation sigma, at
second order (Gauss-Newton term). The test checks that term against Monte Carlo on the polished design, and that sigma 0
returns the nominal cost bit for bit.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_design_memetic_lm_polisher import _build, _splitter

from certus.core.certus_design_workers_dto import DESIGN_OPTIONAL_STEPS


def test_the_selection_is_nominal_by_default() -> None:
    assert DESIGN_OPTIONAL_STEPS["memetic_robust_sigma_nm"] == 0.0
    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    nominal, _ = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0)
    zero, _ = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0, robust_sigma_nm=0.0)
    x_a, c_a = nominal(x0, 300)
    x_b, c_b = zero(x0, 300)
    np.testing.assert_array_equal(x_a, x_b)
    assert c_a == c_b == cost_and_grad(x_a)[0]


def test_the_robust_cost_is_the_expected_mse_under_thickness_errors() -> None:
    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    sigma = 1.0
    polisher, why = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0, robust_sigma_nm=sigma)
    assert polisher is not None, why
    x, robust = polisher(x0, 300)
    nominal = cost_and_grad(x)[0]
    rng = np.random.default_rng(7)
    draws = np.array([cost_and_grad(x + sigma * z)[0] for z in rng.standard_normal((4000, x.size))])
    assert robust > nominal
    assert robust - nominal == pytest.approx(draws.mean() - nominal, rel=0.15)
