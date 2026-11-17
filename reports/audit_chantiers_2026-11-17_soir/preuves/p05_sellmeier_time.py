"""Chantier 05, faisabilite : duree d'un ajustement Sellmeier 3 poles de SUBSTRATE (reglages par defaut), et part du
polissage par moindres carres (ou vivent les Jacobiens par differences finies) contre l'evolution differentielle.

python reports/audit_chantiers_2026-11-17_soir/preuves/p05_sellmeier_time.py
"""
import time

import numpy as np

import certus.core.certus_substrate_sellmeier as so
from certus.core.certus_substrate_sellmeier import _fit_model_sellmeier3poles

wl = np.linspace(380.0, 1100.0, 361)
lu = wl / 1000.0
n = np.sqrt(1 + 1.03961212 * lu**2 / (lu**2 - 0.00600069867) + 0.231792344 * lu**2 / (lu**2 - 0.0200179144)
            + 1.01046945 * lu**2 / (lu**2 - 103.560653))  # BK7 (Schott)
n = n + np.random.default_rng(5).normal(0.0, 2e-5, n.size)
mask = np.ones(n.size, dtype=bool)
spent = {"least_squares": 0.0, "minimize": 0.0, "differential_evolution": 0.0}
for name in spent:
    real = getattr(so, name, None)
    if real is None:
        continue

    def timed(*a, _real=real, _name=name, **k):
        t0 = time.perf_counter()
        try:
            return _real(*a, **k)
        finally:
            spent[_name] += time.perf_counter() - t0

    setattr(so, name, timed)
for run in (1, 2):
    for key in spent:
        spent[key] = 0.0
    t0 = time.perf_counter()
    res = _fit_model_sellmeier3poles(n, wl, mask, n[mask], wl[mask], lu[mask], None, None, 300, 12, 3000, None)
    total = time.perf_counter() - t0
    rms = float(np.sqrt(np.mean((res[0] - n) ** 2))) if res[0] is not None else float("nan")
    print(f"run {run}: total {total:.2f} s, source {res[1]}, rms {rms:.2e} ; " + ", ".join(f"{k} {v:.2f} s" for k, v in spent.items()))
