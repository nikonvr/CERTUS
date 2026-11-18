"""Chantier 21 : pourquoi l'option allumee s'arrete tot sur TOTAL.xlsx.

Enveloppe `minimize` de `spline_workers` : pour chaque appel L-BFGS-B, option allumee puis eteinte, message d'arret, nit,
nfev, cout initial et final ; au point final de l'option allumee, gradient analytique contre differences finies centrees
du cout (bloc d, bloc n, bloc ln k), plus les composantes ξ aux bornes.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_total_stop.py
"""
import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(".").resolve()))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import certus_physics  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
certus_physics.warmup_physics()

from certus.spline import spline_workers  # noqa: E402
from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization  # noqa: E402
from certus.ui.certus_index_spline_ui import CertusIndexSplineApp  # noqa: E402

calls = []
_minimize = spline_workers.minimize


def _wrapped(fun, x0, **kw):
    res = _minimize(fun, x0, **kw)
    calls.append({"fun": fun, "x0": np.array(x0, float), "res": res, "jac": kw.get("jac"), "bounds": kw.get("bounds")})
    return res


spline_workers.minimize = _wrapped

spline_app = CertusIndexSplineApp()
spline_app._on_load(path=str(Path("example/example_index_spline/TOTAL.xlsx").resolve()))
base = spline_app._build_opt_config(notify=False)

objs = []
_orig_polish = spline_workers._polish_lbfgsb_chunked


def _polish(obj, *a, **k):
    objs.append(obj)
    return _orig_polish(obj, *a, **k)


spline_workers._polish_lbfgsb_chunked = _polish

for on in (True, False):
    calls.clear()
    objs.clear()
    r = worker_spline_optimization(base.replace(spline_mono_analytic_gradient=on), threading.Event(),
                                   progress_cb=lambda *a, **k: None, live_cb=lambda *a, **k: None)
    print(f"option={'allumee' if on else 'eteinte'} : RMSE={r['rmse']:.7f} d={r['d_nm']:.2f} ; "
          f"{len(calls)} appels L-BFGS-B, {len(objs)} polissages")
    for i, c in enumerate(calls):
        res = c["res"]
        f0 = c["fun"](c["x0"])
        f0 = f0[0] if isinstance(f0, tuple) else f0
        print(f"  appel {i} jac={c['jac']} dim={c['x0'].size} : f0={float(f0):.6e} -> f={float(res.fun):.6e} "
              f"nit={res.nit} nfev={res.nfev} message={res.message!r}")
    if on:
        last_on = calls[-1]
        obj_on = objs[-1]

x = np.asarray(last_on["res"].x, float)
bnds = np.asarray(last_on["bounds"], float)
K = (x.size - 1) // 2
ga = np.asarray(obj_on.analytic_gradient(x), float)
f = float(obj_on(x))
print(f"\npoint final allume : f={f:.6e} dim={x.size} K={K} d={x[0]:.3f}")
for h in (1e-4, 1e-6):
    gf = np.zeros_like(x)
    for j in range(x.size):
        e = np.zeros_like(x)
        e[j] = h
        gf[j] = (float(obj_on(x + e)) - float(obj_on(x - e))) / (2 * h)
    for name, sl in (("d", slice(0, 1)), ("n/xi", slice(1, 1 + K)), ("ln k", slice(1 + K, 1 + 2 * K))):
        a, b = ga[sl], gf[sl]
        rel = np.max(np.abs(a - b)) / max(np.max(np.abs(b)), 1e-30)
        print(f"  h={h:g} bloc {name}: max|analytique|={np.max(np.abs(a)):.3e} max|DF|={np.max(np.abs(b)):.3e} "
              f"ecart relatif max={rel:.3e}")
    worst = np.argsort(-np.abs(ga - gf))[:6]
    for j in worst:
        print(f"    j={j} x={x[j]:+.6f} bornes=[{bnds[j, 0]:+.3f}, {bnds[j, 1]:+.3f}] analytique={ga[j]:+.6e} "
              f"DF={gf[j]:+.6e}")
proj = np.where((x <= bnds[:, 0] + 1e-12) & (ga > 0), 0.0, np.where((x >= bnds[:, 1] - 1e-12) & (ga < 0), 0.0, ga))
print(f"  gradient projete max = {np.max(np.abs(proj)):.3e} ; composantes aux bornes : "
      f"{int(np.sum((x <= bnds[:, 0] + 1e-12) | (x >= bnds[:, 1] - 1e-12)))}")
