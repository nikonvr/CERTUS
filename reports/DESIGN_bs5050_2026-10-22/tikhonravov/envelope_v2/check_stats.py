"""Known-answer checks of the statistics in catalog.py (CVaR, bPOE, control variate, Pareto, layer field).

usage: python check_stats.py   -> prints one line per check, then CHECKS=OK (raises on the first failure)
"""

from __future__ import annotations

import numpy as np
import search as s
from catalog import N, bpoe, cv_estimate, cv_r2, cvar, layer_field, pareto, partial_rank_corr, quad_expectation
from scipy.stats import norm


def main() -> None:
    rng = np.random.default_rng(1)
    x = rng.standard_normal(2_000_000)
    exact = norm.pdf(norm.ppf(0.95)) / 0.05  # CVaR95 of N(0, 1)
    assert abs(cvar(x) - exact) < 5e-3, (cvar(x), exact)
    print(f"cvar N(0,1): {cvar(x):.4f} exact {exact:.4f}")

    assert bpoe(np.array([4.0, 3.0, 2.0, 1.0]), 2.5) == 1.0
    assert bpoe(np.array([4.0, 3.0, 2.0, 1.0]), 3.6) == 0.25
    assert bpoe(np.array([4.0, 3.0, 2.0, 1.0]), 5.0) == 0.0
    t = exact  # bPOE is the inverse of CVaR: bPOE(CVaR95) = 5 %
    assert abs(bpoe(x, t) - 0.05) < 2e-3, bpoe(x, t)
    print(f"bpoe: discrete cases ok; N(0,1) at CVaR95 -> {bpoe(x, t):.4f} (exact 0.05)")

    r0, j0 = rng.standard_normal(50), rng.standard_normal((50, 4))
    v = np.diag([0.3, 0.5, 0.1, 0.2])
    e = rng.standard_normal((400_000, 4)) @ v
    quad = np.sum((r0 + e @ j0.T) ** 2, axis=1)
    eq = quad_expectation(r0, j0, v)
    assert abs(np.mean(quad) - eq) < 3e-3 * eq, (np.mean(quad), eq)
    assert abs(cv_estimate(quad[:10], quad[:10], eq) - np.sqrt(eq)) < 1e-12  # exact when the model is exact
    print(f"control variate: E[quad] {eq:.4f} vs sample {np.mean(quad):.4f}; zero variance on a quadratic")

    assert pareto([(1, 5), (2, 3), (3, 4), (4, 1), (2, 6)]) == [0, 1, 3]
    print("pareto: ok")

    c = rng.standard_normal(20_000)
    a, b = c + 0.5 * rng.standard_normal(c.size), c + 0.5 * rng.standard_normal(c.size)
    assert np.corrcoef(a, b)[0, 1] > 0.7
    assert abs(partial_rank_corr(a, b, c)) < 0.03  # a and b only share c
    xs = rng.standard_normal((500, 3))
    assert cv_r2(xs, 2 * xs[:, 0] + 0.01 * rng.standard_normal(500)) > 0.99
    assert cv_r2(xs, rng.standard_normal(500)) < 0.05
    print("partial_rank_corr, cv_r2: ok")

    seq = "HL" * (N // 2)
    d = np.array([500.0 / (4 * s.N_IDX[m]) for m in seq])
    f = layer_field(seq, d)
    t_layer = s.rmse(seq, d)  # finite and the field array has one value per layer
    assert f.shape == (N,)
    assert np.all(np.isfinite(f))
    assert np.isfinite(t_layer)
    one = layer_field("H", np.array([0.0]))  # zero thickness: |E|^2 = 1 everywhere (normalised to the substrate)
    assert abs(one[0] - 1.0) < 1e-12
    print("layer_field: shape, zero-thickness case ok")
    print("CHECKS=OK")


if __name__ == "__main__":
    main()
