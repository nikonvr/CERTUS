"""ALG-13: DESIGN's final refinement must stop when the user asks.

Measured 2026-10-16 (reports/ARGON_contre_audit_2026-10-16/pass02.json, R05): 12 gradients ran after the stop
request, because `run_coord_descent_5cycles` read no stop flag. Without `should_stop` it behaves as before (C1).
"""

from __future__ import annotations

import numpy as np

from certus.core.certus_design_worker_utils import run_coord_descent_5cycles


def _refine(should_stop=None):
    calls = {"gradient": 0, "cost": 0}

    def cost(ep, **_kwargs):
        calls["cost"] += 1
        return float(np.sum((ep - 50.0) ** 2))

    def gradient(ep, **_kwargs):
        calls["gradient"] += 1
        return float(np.sum((ep - 50.0) ** 2)), 2.0 * (ep - 50.0)

    kwargs = dict(
        ep_current=np.array([80.0, 20.0]), best_cost=1800.0, var_idx=np.array([0, 1]), oblique_mode=False,
        compute_oblique_error=None, compute_oblique_error_and_grad_analytic=None, n_layers_T=None,
        n_sub=np.zeros(1), wls=np.zeros(1), tgt_vals=None, tgt_weights=None, has_back_calc=False, n_back_T=None,
        d_back=None, cfg={"gauss_newton_max_iter": 0}, evaluate_thicknesses=cost, get_gradient_analytic=gradient,
        progress_emit=lambda *a: None, best_rmse_seen=1e9,
    )
    if should_stop is not None:
        kwargs["should_stop"] = should_stop
    ep, best, _ = run_coord_descent_5cycles(**kwargs)
    return ep, best, calls


def test_a_stop_before_the_refinement_runs_no_gradient() -> None:
    ep, best, calls = _refine(should_stop=lambda: True)
    assert calls["gradient"] == 0
    assert best == 1800.0
    assert np.array_equal(ep, [80.0, 20.0])


def test_a_stop_during_the_refinement_ends_it_at_the_best_point() -> None:
    asked = {"n": 0}

    def stop_after_two_gradients() -> bool:
        asked["n"] += 1
        return asked["n"] > 2

    ep, best, calls = _refine(should_stop=stop_after_two_gradients)
    assert calls["gradient"] <= 2
    assert best == float(np.sum((ep - 50.0) ** 2))


def test_without_should_stop_the_refinement_is_unchanged() -> None:
    _ep, best, calls = _refine()
    assert calls["gradient"] > 2
    assert best < 1e-6
