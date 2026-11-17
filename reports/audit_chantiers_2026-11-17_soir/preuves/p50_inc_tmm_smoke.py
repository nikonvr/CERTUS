"""Chantier 50, faisabilite : `tmm.inc_tmm` (substrat epais, incoherent) contre `calculate_RT_with_backside_fused`.

python reports/audit_chantiers_2026-11-17_soir/preuves/p50_inc_tmm_smoke.py   (tmm 0.2.0 dans %TEMP%/certus_tmm_tiers)

Conventions (celles du chantier 40) : CERTUS n - ik, `tmm` n + ik ; `tmm` liste les couches depuis l'air, CERTUS depuis le
substrat, d'ou l'ordre inverse. Dans l'ordre direct l'ecart vaut 0,25 : c'est la convention, pas la physique.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.environ["TEMP"], "certus_tmm_tiers"))
import tmm  # noqa: E402

from certus.physics.certus_tmm_matrix import calculate_RT_with_backside_fused  # noqa: E402

wls = np.array([450.0, 550.0, 700.0, 900.0])
d = np.array([95.0, 140.0])
print("tmm 0.2.0 inc_tmm contre calculate_RT_with_backside_fused, couches dans l'ordre inverse (convention du 40), D = 1 mm")
for k in (0.0, 1e-6, 4.4e-6, 2e-5, 1e-4):
    n_layers = np.array([[2.3, 1.46]] * len(wls), dtype=np.complex128)
    _R_c, T_c = calculate_RT_with_backside_fused(d, n_layers, np.full(len(wls), 1.52 - 1j * k), wls, 1e6)
    gap = max(
        abs(tmm.inc_tmm("s", [1.0, 1.46, 2.3, complex(1.52, k), 1.0], [np.inf, 140.0, 95.0, 1e6, np.inf],
                        ["i", "c", "c", "i", "i"], 0.0, lam)["T"] - T_c[i])
        for i, lam in enumerate(wls)
    )
    print(f"k={k:g}: max |dT| = {gap:.2e}  T(550)={T_c[1]:.6f}")
