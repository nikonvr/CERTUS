"""Chantier 38: the two L-BFGS-B polishes of the DESIGN window live in certus.core, bit for bit.

`lbfgsb_polish` replaces the closures of `_polish_remaining_layers_above_floor` (re-polish after the 5 nm rule) and
`_prune_trial_rmse` (trial polish of a pruned layer). The references below are those closures as they were in
`certus/ui/certus_design_ui_optimization.py` at `d9d92707`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import scipy.optimize

from certus.core.certus_design_cost_context import prepare_design_cost_context
from certus.core.certus_design_final_cleanup import lbfgsb_polish
from certus.physics.certus_opt_tmm import Material
from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
from certus_physics.structures import Layer, Target

UI_FILE = Path(__file__).resolve().parents[2] / "certus" / "ui" / "certus_design_ui_optimization.py"


def _context():
    mats = {"H": Material(2.35, 2.25), "L": Material(1.48, 1.46), "Substrate": Material(1.53, 1.51)}
    stack = [Layer("H", 1.0), Layer("L", 1.0, False), Layer("H", 1.0), Layer("L", 1.0)]
    wls = np.linspace(420.0, 680.0, 27)
    return prepare_design_cost_context(mats, stack, wls, [Target(420.0, 680.0, 0.05, 0.05)])


EP = np.array([58.0, 96.0, 61.0, 3.2])


def test_the_re_polish_after_the_5nm_rule_is_unchanged() -> None:
    context = _context()
    tgt_vals, tgt_weights = context.normal_targets()
    var_idx = np.array([0, 2, 3], dtype=np.int64)
    floor = np.full(EP.size, 5.0)
    x0 = np.maximum(EP[var_idx], floor[var_idx])
    bounds = [(float(floor[i]), float(max(EP[i] * 2.0, 2000.0))) for i in var_idx]
    full = EP.copy()

    def cost_and_grad(x_var):
        full[var_idx] = x_var
        c, g = compute_gradient_all_layers_analytic(
            full, context.n_front, context.n_sub, context.wls, tgt_vals, tgt_weights, 0.01,
            context.has_back_calc, context.n_back, context.d_back, var_idx,
        )
        return float(c), np.asarray(g, dtype=np.float64)

    c0_ref, _ = cost_and_grad(x0)
    ref = scipy.optimize.minimize(
        cost_and_grad, x0, method="L-BFGS-B", jac=True, bounds=bounds, options={"maxiter": 150, "ftol": 1e-12}
    )
    res, moved_cost = lbfgsb_polish(EP, var_idx, x0, bounds, context, maxiter=150, ftol=1e-12)
    assert np.array_equal(res.x, ref.x)
    assert res.fun == ref.fun
    assert moved_cost(x0)[0] == c0_ref


def test_the_trial_polish_of_a_pruned_layer_is_unchanged() -> None:
    context = _context()
    tgt_vals, tgt_weights = context.normal_targets()
    var_idx = np.arange(EP.size, dtype=np.int64)

    def cost_and_gradient(x):
        return compute_gradient_all_layers_analytic(
            x, context.n_front, context.n_sub, context.wls, tgt_vals, tgt_weights, 0.01,
            context.has_back_calc, context.n_back, context.d_back, var_idx,
        )

    ref = scipy.optimize.minimize(
        cost_and_gradient, EP, method="L-BFGS-B", jac=True, bounds=[(0.01, 2000.0)] * EP.size,
        options={"maxiter": 50, "ftol": 1e-6},
    )
    res, _ = lbfgsb_polish(EP, var_idx, EP, [(0.01, 2000.0)] * EP.size, context, maxiter=50, ftol=1e-6)
    assert np.array_equal(res.x, ref.x)
    assert res.fun == ref.fun


def test_the_design_window_calls_no_optimizer() -> None:
    """CLAUDE.md section 8: certus.ui holds no computing algorithm."""
    calls = [
        node for node in ast.walk(ast.parse(UI_FILE.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "minimize"
    ]
    assert calls == []
