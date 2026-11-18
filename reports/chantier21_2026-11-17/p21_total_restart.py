"""Chantier 21 : sur TOTAL.xlsx, l'arret de l'option allumee (critere ftol) est-il un minimum local ?

Meme depart que le polissage de la fenetre (point de l'etape globale). L-BFGS-B, gradient analytique : (a) reglages de la
fenetre (ftol 1e-12) ; (b) relance depuis le point d'arret de (a) avec ftol=0 ; (c) depuis le depart avec ftol=0. Puis
differences finies (jac absent) depuis le point d'arret de (a), budget 10 000. Cout, RMSE, d, nit, nfev, message.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_total_restart.py
"""
import sys
import threading
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

seen = {}
_orig_polish = spline_workers._polish_lbfgsb_chunked


def _polish(obj, x_start, bounds, maxfun_total, *a, **k):
    seen.update(obj=obj, x0=np.array(x_start, float), bounds=np.array(bounds, float), maxfun=int(maxfun_total))
    return _orig_polish(obj, x_start, bounds, maxfun_total, *a, **k)


spline_workers._polish_lbfgsb_chunked = _polish
spline_app = CertusIndexSplineApp()
spline_app._on_load(path=str(Path("example/example_index_spline/TOTAL.xlsx").resolve()))
base = spline_app._build_opt_config(notify=False)
worker_spline_optimization(base.replace(spline_mono_analytic_gradient=True), threading.Event(),
                           progress_cb=lambda *a, **k: None, live_cb=lambda *a, **k: None)
obj, x0, bds, mf = seen["obj"], seen["x0"], [tuple(b) for b in seen["bounds"]], seen["maxfun"]


def fg(x):
    return float(obj(x)), np.asarray(obj.analytic_gradient(x), float)


def show(tag, res):
    print(f"{tag}: f={res.fun:.6e} RMSE={np.sqrt(res.fun):.7f} d={res.x[0]:.2f} nit={res.nit} nfev={res.nfev} "
          f"message={res.message!r}", flush=True)
    return res


print(f"depart : f={float(obj(x0)):.6e} d={x0[0]:.2f} maxfun={mf}")
a = show("(a) analytique ftol=1e-12", minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bds,
                                                 options={"maxfun": mf, "ftol": 1e-12, "gtol": 1e-9}))
show("(b) analytique relance ftol=0", minimize(fg, a.x, jac=True, method="L-BFGS-B", bounds=bds,
                                                options={"maxfun": mf, "ftol": 0.0, "gtol": 1e-12}))
show("(c) analytique depart ftol=0", minimize(fg, x0, jac=True, method="L-BFGS-B", bounds=bds,
                                               options={"maxfun": mf, "ftol": 0.0, "gtol": 1e-12}))
show("(d) DF relance depuis (a)", minimize(lambda x: float(obj(x)), a.x, method="L-BFGS-B", bounds=bds,
                                           options={"maxfun": mf, "ftol": 1e-12, "gtol": 1e-9}))
