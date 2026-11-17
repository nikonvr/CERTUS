"""Chantier 05, C1 : le chemin par defaut de l'ajustement Sellmeier rend les memes bits avant et apres l'option IR.

Ecrit les sorties (courbe, source, coefficients) dans le fichier donne en argument ; on le lance sur le code d'avant
(`git stash`) puis sur celui d'apres, et on compare les deux fichiers au bit.

set PYTHONPATH=. && python reports/chantier05_2026-11-18/p05_c1_default_path.py sortie.npz
"""
import sys

import numpy as np

from certus.core.certus_substrate_index import IndexCore
from certus.core.certus_substrate_sellmeier import _fit_model_sellmeier3poles, sellmeier_2poles_const_eval

B = (1.03961212, 0.231792344, 1.01046945)
C = (0.00600069867, 0.0200179144, 103.560653)
wl = np.linspace(380.0, 1100.0, 361)
lu = wl / 1000.0
bk7 = np.sqrt(1.0 + sum(b * lu**2 / (lu**2 - c) for b, c in zip(B, C, strict=True)))
auv = sellmeier_2poles_const_eval(np.array([1.2, 0.9, 0.0775, 0.2, 0.1415, 0.05, 0.25]), lu)
out = {}
for name, clean in (("bk7", bk7), ("auv", auv)):
    for sigma in (2e-5, 0.0):
        n = clean + np.random.default_rng(5).normal(0.0, sigma, clean.size)
        curve, src, coeffs, _ = _fit_model_sellmeier3poles(n, wl, np.ones(n.size, bool), n, wl, lu, None, None, 300, 12, 3000, None)
        key = f"{name}_{sigma:.0e}"
        out[key + "_curve"] = curve
        out[key + "_coeffs"] = coeffs
        out[key + "_src"] = np.array(src)
        n_core, meta = IndexCore.fit_sellmeier(n, wl, 400.0, 1050.0, model_kind="sellmeier3poles", return_meta=True)
        out[key + "_core"] = n_core
        out[key + "_core_src"] = np.array(meta["source"])
np.savez(sys.argv[1], **out)
print(f"{len(out)} tableaux ecrits")
