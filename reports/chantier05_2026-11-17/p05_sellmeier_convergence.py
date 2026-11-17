"""Chantier 05 : l'ecart de 2,95e-4 de l'ajustement Sellmeier de SUBSTRATE sur BK7 est-il un defaut de convergence ou une
limite du modele ?

1. La variante A (`sellmeier_2poles_const_eval`) plancher ses denominateurs a 1e-15 : un pole IR (L > lambda) y est-il
   representable ? On l'evalue aux coefficients de BK7 (A=1, Li = sqrt(Ci), L3 = 10,18 um).
2. Convergence : donnees tirees de la variante A elle-meme, poles UV dans les bornes ; l'ajustement doit rendre le bruit.
3. BK7 : l'ecart suit-il le bruit (2e-5, /100, 0) ? S'il ne bouge pas, c'est le modele (CLAUDE.md §4).

Chaque cas est ajuste deux fois : tel quel (le meilleur des deux candidats est retenu), puis variante A seule (la
variante standard 3 termes est forcee en echec, comme le prevoit le code quand son ajustement leve).

set PYTHONPATH=. && python reports/chantier05_2026-11-17/p05_sellmeier_convergence.py
"""
import numpy as np

import certus.core.certus_substrate_sellmeier as so

B = (1.03961212, 0.231792344, 1.01046945)
C = (0.00600069867, 0.0200179144, 103.560653)
BK7_AS_A = np.array([1.0, B[0], np.sqrt(C[0]), B[1], np.sqrt(C[1]), B[2], np.sqrt(C[2])])
UV_ONLY = np.array([1.2, 0.9, 0.0775, 0.2, 0.1415, 0.05, 0.25])  # trois poles UV, sous 0,97 * 0,38 um

wl = np.linspace(380.0, 1100.0, 361)
lu = wl / 1000.0
bk7 = np.sqrt(1.0 + sum(b * lu**2 / (lu**2 - c) for b, c in zip(B, C, strict=True)))
n_a = so.sellmeier_2poles_const_eval(BK7_AS_A, lu)
print(f"1. BK7 dans la variante A : max |n_A - n_BK7| = {np.max(np.abs(n_a - bk7)):.3e} (n_A max = {np.max(n_a):.3e})")

real_std = so._sellmeier_3term_standard_eval


def _std_off(*_a, **_k):
    raise FloatingPointError("standard variant switched off by the probe")


def fit(label, n_clean, sigma):
    n = n_clean + np.random.default_rng(5).normal(0.0, sigma, n_clean.size)
    mask = np.ones(n.size, dtype=bool)
    out = []
    for only_a in (False, True):
        so._sellmeier_3term_standard_eval = _std_off if only_a else real_std
        try:
            curve, src, _, _ = so._fit_model_sellmeier3poles(n, wl, mask, n, wl, lu, None, None, 300, 12, 3000, None)
        finally:
            so._sellmeier_3term_standard_eval = real_std
        fit_rms = np.sqrt(np.mean((curve - n) ** 2))
        true_rms = np.sqrt(np.mean((curve - n_clean) ** 2))
        out.append(f"{src.replace('analytic-sellmeier-', '')}: aux donnees {fit_rms:.2e}, a la courbe vraie {true_rms:.2e}")
    print(f"   {label} sigma={sigma:.0e} (bruit tire {np.sqrt(np.mean((n - n_clean) ** 2)):.2e}) | retenu {out[0]} | A seule {out[1]}")


print("2. Donnees de la variante A, poles UV :")
for sigma in (2e-5, 2e-7, 0.0):
    fit("A-UV", so.sellmeier_2poles_const_eval(UV_ONLY, lu), sigma)
print("3. BK7 :")
for sigma in (2e-5, 2e-7, 0.0):
    fit("BK7 ", bk7, sigma)
