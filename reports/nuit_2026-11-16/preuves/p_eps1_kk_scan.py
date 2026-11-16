"""ETAT section 5: once on H800 (Eg 1.331, E0 3.074, eps_inf 4.276; A and C not logged) the closed form of eps1
differed from Kramers-Kronig by 0.42. Scan A and C at that point, on the fitted window (1000-5200 nm), and say where
the two disagree; then check that it is not the numerical KK (finer quad, wider e_max).
    python reports/nuit_2026-11-16/preuves/p_eps1_kk_scan.py
"""

import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "unit")]
warnings.filterwarnings("ignore")
from test_tauc_lorentz_kernels_match_kramers_kronig_and_finite_differences import kramers_kronig_eps1  # noqa: E402

from certus.core.certus_core import HC_EV_NM  # noqa: E402
from certus.physics.certus_optical_models import epsilon1_TL_analytic  # noqa: E402

Eg, E0, eps_inf = 1.331, 3.074, 4.276
E = np.sort(HC_EV_NM / np.linspace(1000.0, 5200.0, 43))
rows = []
for A in (1.0, 10.0, 30.0, 100.0, 300.0):
    for C in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 6.0, 10.0):
        cf = epsilon1_TL_analytic(E, Eg, A, E0, C, eps_inf)
        kk = np.array([kramers_kronig_eps1(e, Eg, A, E0, C, eps_inf) for e in E])
        i = int(np.argmax(np.abs(cf - kk)))
        rows.append((float(abs(cf[i] - kk[i])), A, C, float(E[i]), float(cf[i]), float(kk[i])))
rows.sort(reverse=True)
print("worst |closed form - KK| over the window, per (A, C):")
for gap, A, C, e, cf, kk in rows[:8]:
    wide = kramers_kronig_eps1(e, Eg, A, E0, C, eps_inf, e_max=5000.0)
    print(f"  gap {gap:.3e}  A {A:g} C {C:g}  at E {e:.4f} eV: closed form {cf:.6f}, KK(200) {kk:.6f}, KK(5000) {wide:.6f}")
print(f"cases with gap > 1e-3: {sum(r[0] > 1e-3 for r in rows)} of {len(rows)}")
