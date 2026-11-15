"""Audit M-L1: does `_compute_epsilon1_gradient_kernel` describe the epsilon1 that `epsilon1_TL_analytic` returns?

Strong Tauc-Lorentz oscillator, so that epsilon1 dips below 1 above E0. Where `epsilon1_TL_analytic` returns its floor
of 1.0, the cost is flat in every parameter; a central finite difference of it is compared with the kernel's derivative.
    python reports/audit_code_2026-11-15/preuves/p_epsilon1_plafond.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from certus.physics.certus_optical_models import epsilon1_TL_analytic  # noqa: E402
from certus.physics.gradient_analytic import _compute_epsilon1_gradient_kernel  # noqa: E402

E = np.linspace(1.0, 9.0, 161)
Eg, A, E0, C, eps_inf = 3.2, 300.0, 4.5, 1.0, 1.0
eps1 = epsilon1_TL_analytic(E, Eg, A, E0, C, eps_inf)
kern = _compute_epsilon1_gradient_kernel(E, Eg, A, E0, C, eps_inf)
floored = eps1 == 1.0
print(f"points where epsilon1_TL_analytic returns its floor 1.0: {int(floored.sum())} of {E.size}")
print(f"kernel epsilon1 at those points: min {kern[0][floored].min():.4f}, max {kern[0][floored].max():.4f}" if floored.any() else "")
h = 1e-6
fd = (epsilon1_TL_analytic(E, Eg, A + h, E0, C, eps_inf) - epsilon1_TL_analytic(E, Eg, A - h, E0, C, eps_inf)) / (2 * h)
d_A = kern[2]
print(f"d eps1 / dA where floored: finite difference max |.| {np.abs(fd[floored]).max():.3e}, kernel max |.| {np.abs(d_A[floored]).max():.3e}" if floored.any() else "")
ok = ~floored & np.isfinite(fd) & np.isfinite(d_A)
print(f"d eps1 / dA elsewhere ({int(ok.sum())} finite points): max |kernel - finite difference| = "
      f"{np.abs(d_A[ok] - fd[ok]).max():.3e} (scale {np.abs(fd[ok]).max():.3e}); non-finite points: {int((~floored & ~ok).sum())}")
