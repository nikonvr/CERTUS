"""The beam aperture imposed by an instrument preset instead of fitted (port of certus_re, Zenodo, ``instruments``).

    THE KEY: absent, the default, keeps the fitted plateaus; a total aperture in degrees imposes it; a value outside
        [0, 20] deg is refused by name rather than clipped
    STEP 2 WITH NOTHING RELEASED: the residual functions over the thicknesses alone leave the knots at the imposed value
        and return the Jacobian of the thicknesses; with four knots released they move the knots, take a column per
        knot and put the knots back
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from certus.core.certus_re_solvers import _s2_residual_functions
from certus.utils.certus_re_config import RE_INSTRUMENT_PRESETS, re_imposed_aperture_deg


def test_absent_the_aperture_is_fitted():
    assert re_imposed_aperture_deg({}) is None
    assert re_imposed_aperture_deg({"re_beam_aperture_imposed_deg": None}) is None


def test_the_photon_rt_preset_imposes_two_degrees_total():
    assert RE_INSTRUMENT_PRESETS["photon_rt_5200"]["aperture_deg"] == 2.0
    assert re_imposed_aperture_deg({"re_beam_aperture_imposed_deg": 2.0}) == 2.0


@pytest.mark.parametrize("value", [-0.5, 25.0])
def test_an_aperture_out_of_range_is_refused(value):
    with pytest.raises(ValueError, match="re_beam_aperture_imposed_deg"):
        re_imposed_aperture_deg({"re_beam_aperture_imposed_deg": value})


def _namespace(knots: float, seen: list) -> SimpleNamespace:
    """A model whose residuals depend on the thicknesses and on the mean aperture: r = (ep - 100) + 0.1 * mean(ap)."""
    state = {"re_aperture_knots": np.full(4, knots)}

    def mse_grad(ep, _wt, want_grad, _correc, return_residuals=False):
        ap = state["re_aperture_knots"].copy()
        seen.append(ap)
        r = (np.asarray(ep) - 100.0) + 0.1 * float(np.mean(ap))
        return float(r @ r) / r.size, None, r, np.eye(r.size)

    return SimpleNamespace(
        _re_state=state,
        _mse_grad_accumulate_ep=mse_grad,
        wt_spectral=None,
        _correc_nom=None,
        _compute_qwot_rmse=lambda *_a: 0.0,
        _rmse_combined=lambda a, b: a,
    )


def test_with_nothing_released_the_knots_stay_imposed():
    seen: list = []
    L = _namespace(2.0, seen)
    worker = SimpleNamespace(_stop=False)
    bounds = (np.zeros(3), np.full(3, 500.0))
    fun, jac, cache = _s2_residual_functions(worker, L, 3, 0, bounds, 1e-3)
    x = np.array([101.0, 99.0, 100.5])
    r = fun(x)
    j = jac(x)
    assert r == pytest.approx(x - 100.0 + 0.2)
    assert j.shape == (3, 3)
    assert all(np.array_equal(ap, np.full(4, 2.0)) for ap in seen)
    assert np.array_equal(L._re_state["re_aperture_knots"], np.full(4, 2.0))
    assert cache["i"] == 1


def test_with_four_knots_released_each_gets_its_column_and_the_knots_are_put_back():
    seen: list = []
    L = _namespace(1.75, seen)
    worker = SimpleNamespace(_stop=False)
    bounds = (np.concatenate([np.zeros(2), np.full(4, 1.0)]), np.concatenate([np.full(2, 500.0), np.full(4, 2.5)]))
    _fun, jac, _ = _s2_residual_functions(worker, L, 2, 4, bounds, 1e-3)
    x = np.array([101.0, 99.0, 1.5, 1.6, 1.7, 1.8])
    j = jac(x)
    assert j.shape == (2, 6)
    assert j[:, 2:] == pytest.approx(np.full((2, 4), 0.1 / 4), rel=1e-6)
    assert np.array_equal(L._re_state["re_aperture_knots"], x[2:])
    assert len(seen) == 1 + 4
