"""The memetic stage of DESIGN may polish by Levenberg-Marquardt (`memetic_polisher`, 2026-11-13), on the real kernel.

The residuals must reproduce the memetic cost, or the two would optimize different merits: the builder checks it and
refuses otherwise. Default `lbfgs_then_lm` (owner, 2026-11-13); `lbfgs` keeps the memetic stage as before (no polisher).
"""

from __future__ import annotations

import numpy as np
import pytest

from certus.core.certus_design_lm import build_memetic_lm_polisher
from certus.physics.design_fast_normal import compute_gradient_lossless_front_fast, prepare_normal_fast_context

N_H, N_L, N_SUB = 2.35, 1.45, 1.52


def _splitter(layers: int = 12, points: int = 161):
    """A 50/50 beamsplitter 400-1200 nm, as in Tikhonravov et al. (1996), on a short grid."""
    wls = np.linspace(400.0, 1200.0, points)
    n = np.array([N_H if i % 2 == 0 else N_L for i in range(layers)], dtype=np.complex128)
    ctx = prepare_normal_fast_context(
        wls=wls, n_layers_T=np.ascontiguousarray(np.tile(n, (points, 1))), n_sub=np.full(points, N_SUB, dtype=np.complex128),
        has_back_calc=False, n_back_T=np.zeros((points, 0), dtype=np.complex128), d_back=np.zeros(0))
    tv, tw = np.full(points, 0.5), np.ones(points)
    var = np.arange(layers, dtype=np.int64)

    def cost_and_grad(x):
        c, g = compute_gradient_lossless_front_fast(np.ascontiguousarray(x, dtype=np.float64), ctx["n_layers_real"],
                                                    ctx["inv_n_layers_real"], ctx["n_sub_real"], ctx["k0_wls"], tv, tw, var)
        return float(c), np.asarray(g, dtype=np.float64)

    x0 = 550.0 / (4.0 * n.real) * (1.0 + 0.3 * np.sin(np.arange(layers)))
    bounds = np.column_stack((np.full(layers, 5.0), np.full(layers, 400.0)))
    return ctx, tv, tw, var, cost_and_grad, x0, bounds


def _build(cost_and_grad, ctx, tv, tw, var, bounds, x0, **kw):
    return build_memetic_lm_polisher(cost_and_grad, fast_ctx=ctx, ep_full=x0, var_idx=var, tgt_vals=tv, tgt_weights=tw,
                                     bounds=bounds, min_d=5.0, probe=x0, **kw)


def test_the_residuals_reproduce_the_memetic_cost_and_the_polish_lowers_it() -> None:
    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    polisher, why = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0)
    assert polisher is not None, why
    x, cost = polisher(x0, 3000)
    assert cost == pytest.approx(cost_and_grad(x)[0])
    assert cost < 0.1 * cost_and_grad(x0)[0]
    assert np.all(x >= bounds[:, 0])
    assert np.all(x <= bounds[:, 1])


def test_after_lbfgs_is_never_worse_than_lbfgs_alone() -> None:
    import scipy.optimize

    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    alone = scipy.optimize.minimize(cost_and_grad, x0, jac=True, method="L-BFGS-B", bounds=list(map(tuple, bounds)),
                                    options={"maxiter": 3000, "ftol": 1e-15, "gtol": 1e-12})
    polisher, why = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0, after_lbfgs=True)
    assert polisher is not None, why
    assert polisher(x0, 3000)[1] <= float(alone.fun)


def test_a_cost_the_residuals_do_not_reproduce_is_refused() -> None:
    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()

    def other(x):
        c, g = cost_and_grad(x)
        return 2.0 * c, 2.0 * g

    polisher, why = _build(other, ctx, tv, tw, var, bounds, x0)
    assert polisher is None
    assert "memetic cost" in why


def test_a_floor_under_the_absent_threshold_is_refused() -> None:
    """Under `min_d` the memetic cost counts a layer as absent: the residual kernel does not."""
    ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    bounds[:, 0] = 1.0
    polisher, why = _build(cost_and_grad, ctx, tv, tw, var, bounds, x0)
    assert polisher is None
    assert "absent" in why


def test_without_the_fast_context_it_is_refused() -> None:
    _ctx, tv, tw, var, cost_and_grad, x0, bounds = _splitter()
    polisher, _why = _build(cost_and_grad, None, tv, tw, var, bounds, x0)
    assert polisher is None


def test_the_default_is_lbfgs_then_lm() -> None:
    from certus.core.certus_design_workers_dto import DESIGN_OPTIONAL_STEPS

    assert DESIGN_OPTIONAL_STEPS["memetic_polisher"] == "lbfgs_then_lm"
