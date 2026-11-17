"""Bare back face (has_back=True, no back stack): does the analytic gradient follow the cost?

Run: python reports/suite_2026-11-17/preuves/p_back_bare_gradient.py
"""

import numpy as np

from certus.physics.gradient_oblique import compute_gradient_all_layers_analytic
from certus.physics.gradient_utils import cost_numba_fast

WLS = np.array([470.0, 560.0, 640.0, 760.0, 900.0, 1100.0, 1300.0, 1500.0])
rng = np.random.default_rng(37)
n = rng.uniform(1.3, 2.4, (len(WLS), 3)).astype(np.complex128)
d = rng.uniform(40.0, 180.0, 3)
targets = np.random.default_rng(43).uniform(0.2, 0.9, len(WLS))
weights = np.ones(len(WLS))
nb, db = np.zeros((len(WLS), 0), dtype=np.complex128), np.zeros(0)
var = np.arange(3, dtype=np.int64)

for k in (0.0, 1e-4):
    n_sub = np.array([complex(1.50 + 0.01 * i, -k) for i in range(len(WLS))])

    def cost(t, n_sub=n_sub):
        return cost_numba_fast(t, n, n_sub, WLS, targets, weights, 1.0, True, nb, db)

    value, grad = compute_gradient_all_layers_analytic(d, n, n_sub, WLS, targets, weights, 1.0, True, nb, db, var)
    fd = []
    for j in range(3):
        up, dn = d.copy(), d.copy()
        up[j] += 1e-3
        dn[j] -= 1e-3
        fd.append((cost(up) - cost(dn)) / 2e-3)
    print(f"k={k:g} cost={cost(d):.10e} grad_value={value:.10e} rel_value_gap={abs(value - cost(d)) / cost(d):.3e}")
    print(f"   analytic={np.array2string(grad, precision=6)} finite_diff={np.array2string(np.array(fd), precision=6)}")
