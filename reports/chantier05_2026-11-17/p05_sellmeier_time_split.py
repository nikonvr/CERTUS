"""Chantier 05 : ou passe le temps d'un ajustement Sellmeier de SUBSTRATE, appel par appel (fonction de cout, Jacobien
fourni ou differences finies, nombre d'evaluations). Donnees BK7 bruitees a 2e-5, reglages par defaut, a chaud.

set PYTHONPATH=. && python reports/chantier05_2026-11-17/p05_sellmeier_time_split.py
"""
import time
from collections import defaultdict

import numpy as np

import certus.core.certus_substrate_sellmeier as so

B = (1.03961212, 0.231792344, 1.01046945)
C = (0.00600069867, 0.0200179144, 103.560653)
wl = np.linspace(380.0, 1100.0, 361)
lu = wl / 1000.0
n = np.sqrt(1.0 + sum(b * lu**2 / (lu**2 - c) for b, c in zip(B, C, strict=True)))
n = n + np.random.default_rng(5).normal(0.0, 2e-5, n.size)
mask = np.ones(n.size, dtype=bool)

spent = defaultdict(lambda: [0, 0.0, 0])  # appels, secondes, evaluations
for name in ("least_squares", "minimize"):
    real = getattr(so, name)

    def timed(fun, *a, _real=real, _name=name, **k):
        jac = "jac" if callable(k.get("jac")) else "diff. finies"
        key = f"{_name}({getattr(fun, '__name__', '?')}, {jac})"
        t0 = time.perf_counter()
        res = _real(fun, *a, **k)
        rec = spent[key]
        rec[0] += 1
        rec[1] += time.perf_counter() - t0
        rec[2] += int(getattr(res, "nfev", 0) or 0)
        return res

    setattr(so, name, timed)

for run in (1, 2):
    spent.clear()
    t0 = time.perf_counter()
    curve, src, _, _ = so._fit_model_sellmeier3poles(n, wl, mask, n, wl, lu, None, None, 300, 12, 3000, None)
    total = time.perf_counter() - t0
    print(f"run {run} : {total:.2f} s, retenu {src}")
    for key, (calls, secs, nfev) in sorted(spent.items(), key=lambda kv: -kv[1][1]):
        print(f"   {secs:6.2f} s  {calls:3d} appels  {nfev:6d} evaluations  {key}")
