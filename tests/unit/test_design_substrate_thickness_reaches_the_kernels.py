"""Chantier 47: the substrate thickness reaches the DESIGN entry points (normal incidence, back face seen).

At 1 mm (the default) every entry point keeps the bits of the call without the argument (C1); at 2 mm an absorbing
substrate gives another answer, and a non-absorbing one the same.
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.physics.certus_substrate_absorption import DEFAULT_SUBSTRATE_THICKNESS_NM
from certus.physics.certus_tmm_matrix import calc_spectrum_full_exact_wrapper
from certus.physics.design_fast_normal import prepare_normal_fast_context
from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
from certus.physics.gradient_utils import cost_numba_fast

WLS = np.array([450.0, 550.0, 650.0, 800.0, 1000.0, 1200.0])


def _case(k: float, back_layers: int):
    rng = np.random.default_rng(71)
    n = rng.uniform(1.4, 2.3, (len(WLS), 3)).astype(np.complex128)
    d = rng.uniform(50.0, 160.0, 3)
    n_back = rng.uniform(1.4, 2.3, (len(WLS), back_layers)).astype(np.complex128)
    d_back = rng.uniform(50.0, 160.0, back_layers)
    n_sub = np.array([complex(1.52, -k)] * len(WLS))
    targets = rng.uniform(0.3, 0.9, len(WLS))
    return d, n, n_sub, targets, np.ones(len(WLS)), n_back, d_back


def _outputs(case, thickness=None):
    d, n, n_sub, targets, weights, n_back, d_back = case
    extra = () if thickness is None else (thickness,)
    kw = {} if thickness is None else {"substrate_thickness_nm": thickness}
    var = np.arange(3, dtype=np.int64)
    cost = cost_numba_fast(d, n, n_sub, WLS, targets, weights, 1.0, True, n_back, d_back, *extra)
    g_cost, grad = compute_gradient_all_layers_analytic(d, n, n_sub, WLS, targets, weights, 1.0, True, n_back, d_back, var, **kw)
    ctx = prepare_normal_fast_context(wls=WLS, n_layers_T=n, n_sub=n_sub, has_back_calc=True, n_back_T=n_back, d_back=d_back, **kw)
    spectra = calc_spectrum_full_exact_wrapper(WLS, n, d, n_sub, n_back, d_back, *extra)
    return [np.array([cost]), np.array([g_cost]), grad, ctx["rb_prime"], ctx["tb"], *spectra]


@pytest.mark.parametrize("back_layers", [0, 2])
@pytest.mark.parametrize("k", [0.0, 1e-5])
def test_one_millimetre_keeps_the_bits_of_the_default(k, back_layers) -> None:
    case = _case(k, back_layers)
    for a, b in zip(_outputs(case), _outputs(case, DEFAULT_SUBSTRATE_THICKNESS_NM), strict=True):
        assert np.array_equal(np.asarray(a).view(np.uint64), np.asarray(b).view(np.uint64))


@pytest.mark.parametrize("back_layers", [0, 2])
def test_the_thickness_acts_on_an_absorbing_substrate_only(back_layers) -> None:
    absorbing = _case(1e-5, back_layers)
    clear = _case(0.0, back_layers)
    thin, thick = _outputs(absorbing), _outputs(absorbing, 2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM)
    assert thick[0][0] != thin[0][0]
    assert thick[1][0] != thin[1][0]
    assert not np.array_equal(thick[4], thin[4])  # tb, the way through the plate
    for a, b in zip(_outputs(clear), _outputs(clear, 2.0 * DEFAULT_SUBSTRATE_THICKNESS_NM), strict=True):
        assert np.array_equal(a, b)
