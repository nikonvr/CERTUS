"""Chantier 50 : face arriere traitee et incidence oblique, CERTUS contre l'oracle independant et contre `tmm.inc_tmm`.

CERTUS : `calc_spectrum_full_oblique_exact` (piles avant et arriere, plaque incoherente). Oracle :
`rt_plate_incoherent` (meme modele : interfaces internes a Re(n)). `tmm` : interfaces a n complexe ; a k = 0 les trois
modeles coincident, l'accord doit etre a l'arrondi.

python reports/chantier50_2026-11-17/p50_back_oblique.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.environ["TEMP"], "certus_tmm_tiers"))
sys.path.insert(0, os.path.join("tests", "oracle"))
import tmm  # noqa: E402
from tmm_reference import rt_plate_incoherent  # noqa: E402

from certus.physics.certus_tmm_oblique import calc_spectrum_full_oblique_exact  # noqa: E402

WLS = np.array([450.0, 550.0, 700.0, 900.0])
FRONT_N, FRONT_D = [2.3 + 0j, 1.46 + 0j, 2.1 - 0.002j], [95.0, 140.0, 60.0]  # index 0 = cote substrat ; une couche absorbante
BACK_N, BACK_D = [1.38 + 0j, 2.0 + 0j], [110.0, 70.0]  # index 0 = cote substrat
D_SUB = 1.0e6

print("max sur 4 longueurs d'onde de |dR| et |dT| ; A CERTUS, B oracle, D tmm.inc_tmm")
for k in (0.0, 4.4e-6):
    n_sub = 1.52 - 1j * k
    for angle in (0.0, 30.0, 60.0):
        for s_pol in (True, False):
            r_a, t_a = calc_spectrum_full_oblique_exact(
                WLS, np.array(FRONT_D), np.array([FRONT_N] * len(WLS)), np.array(BACK_D), np.array([BACK_N] * len(WLS)),
                np.full(len(WLS), n_sub), angle, s_pol, D_SUB)
            ab = np.array([rt_plate_incoherent(lam, FRONT_N, FRONT_D, BACK_N, BACK_D, n_sub, angle, s_pol, D_SUB) for lam in WLS])
            # tmm : n + ik, couches depuis l'air ; avant a l'envers, arriere dans l'ordre (index 0 contre le substrat)
            n_list = [1.0, *[np.conj(n) for n in FRONT_N[::-1]], np.conj(n_sub), *[np.conj(n) for n in BACK_N], 1.0]
            d_list = [np.inf, *FRONT_D[::-1], D_SUB, *BACK_D, np.inf]
            c_list = ["i", *["c"] * len(FRONT_N), "i", *["c"] * len(BACK_N), "i"]
            dd = np.array([[tmm.inc_tmm("s" if s_pol else "p", n_list, d_list, c_list, np.deg2rad(angle), lam)[key]
                            for key in ("R", "T")] for lam in WLS])
            print(f"k={k:<7g} {angle:4.0f} deg {'s' if s_pol else 'p'} :  A-B R {np.max(np.abs(r_a - ab[:, 0])):.1e} "
                  f"T {np.max(np.abs(t_a - ab[:, 1])):.1e}   A-D R {np.max(np.abs(r_a - dd[:, 0])):.1e} "
                  f"T {np.max(np.abs(t_a - dd[:, 1])):.1e}")

# Is the k > 0 gap with a back stack also the choice of the inside index? Variant C at 0 deg: the oracle's assembly with
# every piece seen from inside at the COMPLEX index (as tmm), Beer-Lambert unchanged.
from tmm_reference import rt_stack  # noqa: E402

print("0 deg, k > 0, pile arriere : C = assemblage de l'oracle, interfaces internes a n complexe")
for k in (1e-6, 4.4e-6, 2e-5):
    n_sub = 1.52 - 1j * k
    gaps = []
    for lam in WLS:
        r_f, t_f = rt_stack(lam, FRONT_N, FRONT_D, n_inc=1.0 + 0j, n_sub=n_sub)
        r_in, _ = rt_stack(lam, FRONT_N[::-1], FRONT_D[::-1], n_inc=n_sub, n_sub=1.0 + 0j)
        r_b, t_b = rt_stack(lam, BACK_N[::-1], BACK_D[::-1], n_inc=n_sub, n_sub=1.0 + 0j)
        tau = np.exp(-4.0 * np.pi * k * D_SUB / lam)
        t_c = t_f * t_b * tau / (1.0 - r_in * r_b * tau * tau)
        n_list = [1.0, *[np.conj(n) for n in FRONT_N[::-1]], np.conj(n_sub), *[np.conj(n) for n in BACK_N], 1.0]
        d_list = [np.inf, *FRONT_D[::-1], D_SUB, *BACK_D, np.inf]
        c_list = ["i", *["c"] * len(FRONT_N), "i", *["c"] * len(BACK_N), "i"]
        t_d = tmm.inc_tmm("s", n_list, d_list, c_list, 0.0, lam)["T"]
        _r_a, t_a = calc_spectrum_full_oblique_exact(
            np.array([lam]), np.array(FRONT_D), np.array([FRONT_N]), np.array(BACK_D), np.array([BACK_N]),
            np.array([n_sub]), 0.0, True, D_SUB)
        gaps.append((abs(t_a[0] - t_d), abs(t_c - t_d)))
    g = np.array(gaps)
    print(f"k={k:<7g} A-D {g[:, 0].max():.1e}   C-D {g[:, 1].max():.1e}")
