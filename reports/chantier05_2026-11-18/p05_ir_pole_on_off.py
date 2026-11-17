"""Chantier 05 : l'option `sellmeier_ir_pole` (pole infrarouge de catalogue) contre le defaut, sur les cinq substrats du
catalogue (`SELLMEIER_COEFFS_BY_ID`, forme standard avec pole IR), le saphir dans l'IR et des donnees tirees de la
variante A ; bruit 2e-5, 2e-7, 0. Ecart rms a la courbe vraie, source retenue, duree a chaud (`IndexCore.fit_sellmeier`,
reglages par defaut).

set PYTHONPATH=. && python reports/chantier05_2026-11-18/p05_ir_pole_on_off.py
"""
import time

import numpy as np

from certus.core.certus_core import SELLMEIER_COEFFS_BY_ID
from certus.core.certus_substrate_index import IndexCore
from certus.core.certus_substrate_sellmeier import _sellmeier_3term_standard_eval, sellmeier_2poles_const_eval

NAMES = {0: "SiO2", 1: "BK7", 2: "D263", 3: "saphir", 4: "B270"}
VIS = np.linspace(380.0, 1100.0, 361)
IR = np.linspace(2500.0, 4000.0, 280)
cases = [(f"{NAMES[i]} 380-1100", VIS, _sellmeier_3term_standard_eval(np.asarray(c, float), VIS / 1000.0))
         for i, c in SELLMEIER_COEFFS_BY_ID.items()]
cases.append(("saphir 2500-4000", IR, _sellmeier_3term_standard_eval(np.asarray(SELLMEIER_COEFFS_BY_ID[3], float), IR / 1000.0)))
cases.append(("variante A, poles UV", VIS, sellmeier_2poles_const_eval(np.array([1.2, 0.9, 0.0775, 0.2, 0.1415, 0.05, 0.25]), VIS / 1000.0)))

IndexCore.fit_sellmeier(cases[0][2], VIS, 380.0, 1100.0, model_kind="sellmeier3poles", sellmeier_ir_pole=True)  # chauffe
print("cas | bruit | defaut : rms a la courbe vraie, source, s | option IR : rms, source, s")
for label, wl, clean in cases:
    for sigma in (2e-5, 2e-7, 0.0):
        n = clean + np.random.default_rng(5).normal(0.0, sigma, clean.size)
        row = []
        for ir in (False, True):
            t0 = time.perf_counter()
            curve, meta = IndexCore.fit_sellmeier(n, wl, float(wl[0]), float(wl[-1]), model_kind="sellmeier3poles",
                                                  return_meta=True, sellmeier_ir_pole=ir)
            dt = time.perf_counter() - t0
            src = str(meta["source"]).replace("analytic-sellmeier-", "")
            row.append(f"{np.sqrt(np.mean((curve - clean) ** 2)):.2e} {src} {dt:.2f}")
        print(f"{label} | {sigma:.0e} | {row[0]} | {row[1]}")
