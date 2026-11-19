"""Chantier 21 : un polissage mixte garde-t-il la vitesse du gradient analytique sans la perte sur TOTAL ?

Sonde, aucun changement de `certus/`. Pour chaque classeur d'`example/example_index_spline/`, le depart du polissage de
la fenetre (point de l'etape globale, capte en enveloppant `_polish_lbfgsb_chunked`) et le meme cout ; L-BFGS-B, bornes
et reglages de la fenetre (ftol 1e-12, gtol 1e-9), budget total B = `polish_maxfun` :

- DF        : differences finies, budget B (le defaut d'aujourd'hui) ;
- AN        : gradient analytique, budget B ;
- AN>DF     : AN, puis DF depuis son arret avec le budget restant ;
- DFnk>AN   : DF a n 000 evaluations (n = 2 par defaut), puis AN avec le budget restant ;
- ANx5d     : AN depuis cinq departs, d en linspace(d_lo, d_hi, 5), le reste du depart inchange ; le meilleur, budget
              B partage ;
- ANx5d+    : idem, plus le depart de la fenetre (six departs).

Duree (perf_counter), evaluations de cout, f, RMSE = sqrt(f), d. Un calcul par cas, cache Numba chaud.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-19/p21_mixed_polish.py [variantes]
"""
import sys
import threading
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(".").resolve()))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import certus_physics  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
certus_physics.warmup_physics()

from certus.spline import spline_workers  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

OPTS = {"ftol": 1e-12, "gtol": 1e-9}
VARIANTS = sys.argv[1:] or ["DF", "AN", "AN>DF", "DF2k>AN", "ANx5d", "ANx5d+"]
seen = {}
_orig_polish = spline_workers._polish_lbfgsb_chunked


def _polish(obj, x_start, bounds, maxfun_total, *a, **k):
    seen.update(obj=obj, x0=np.array(x_start, float), bounds=np.array(bounds, float), maxfun=int(maxfun_total))
    return _orig_polish(obj, x_start, bounds, maxfun_total, *a, **k)


spline_workers._polish_lbfgsb_chunked = _polish


class Counted:
    def __init__(self, obj):
        self.obj = obj
        self.n = 0

    def f(self, x):
        self.n += 1
        return float(self.obj(x))

    def fg(self, x):
        self.n += 1
        return float(self.obj(x)), np.asarray(self.obj.analytic_gradient(x), float)


def lb(c, x, bds, budget, analytic):
    if budget <= 0:
        return x, float(c.obj(x))
    if analytic:
        r = minimize(c.fg, x, jac=True, method="L-BFGS-B", bounds=bds, options={"maxfun": int(budget), **OPTS})
    else:
        r = minimize(c.f, x, method="L-BFGS-B", bounds=bds, options={"maxfun": int(budget), **OPTS})
    return np.asarray(r.x, float), float(r.fun)


def variant(name, obj, x0, bds, B, d_lo, d_hi):
    c = Counted(obj)
    t0 = time.perf_counter()
    if name == "DF":
        x, f = lb(c, x0, bds, B, False)
    elif name == "AN":
        x, f = lb(c, x0, bds, B, True)
    elif name == "AN>DF":
        x, f = lb(c, x0, bds, B, True)
        x, f = lb(c, x, bds, B - c.n, False)
    elif name.startswith("DF") and name.endswith("k>AN"):
        x, f = lb(c, x0, bds, 1000 * int(name[2:-4]), False)
        x, f = lb(c, x, bds, B - c.n, True)
    else:
        starts = []
        for d in np.linspace(d_lo, d_hi, 5):
            xs = x0.copy()
            xs[0] = d
            starts.append(xs)
        if name == "ANx5d+":
            starts.append(x0.copy())
        best = (None, np.inf)
        for i, xs in enumerate(starts):
            xi, fi = lb(c, xs, bds, (B - c.n) // (len(starts) - i), True)
            if fi < best[1]:
                best = (xi, fi)
        x, f = best
    dt = time.perf_counter() - t0
    print(f"  {name:8s} : {dt:6.2f} s, {c.n:6d} couts, f={f:.6e} RMSE={np.sqrt(f):.7f} d={x[0]:.2f}", flush=True)


for path in sorted(Path("example/example_index_spline").glob("*.xlsx")):
    app_ = CertusIndexSplineApp()
    app_._on_load(path=str(path.resolve()))
    base = app_._build_opt_config(notify=False)
    seen.clear()
    worker_spline_optimization(base.replace(spline_mono_analytic_gradient=True), threading.Event(),
                               progress_cb=lambda *a, **k: None, live_cb=lambda *a, **k: None)
    obj, x0, B = seen["obj"], seen["x0"], seen["maxfun"]
    bds = [tuple(b) for b in seen["bounds"]]
    print(f"{path.name} : depart f={float(obj(x0)):.6e} d={x0[0]:.2f}, budget B={B}, d dans [{base.d_lo}, {base.d_hi}]",
          flush=True)
    for name in VARIANTS:
        variant(name, obj, x0, bds, B, float(base.d_lo), float(base.d_hi))
