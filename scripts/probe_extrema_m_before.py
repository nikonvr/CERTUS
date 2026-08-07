"""Reproduit le tableau du PLAN §A.0 : le volet points tournants est inerte.

check_extrema_proximity_batch recoit en production un M_before de zeros
(certus/utils/certus_strat_service.py, « conservative: no extrema filtering »).
Avec une matrice nulle tous les denom tombent sous 1e-9, donc tous les T
echantillonnes valent 0, donc toutes les pentes valent 0, donc aucun test de
point tournant ne peut declencher.

Le controle a l'identite prouve seulement que le noyau est VIVANT : l'identite
est le M_before correct de la premiere couche seulement. Ce n'est pas le taux
de rejet physique.
"""
import sys
from pathlib import Path

import numpy as np

# Racine du depot deduite de l'emplacement de CE fichier (scripts/..).
# Ne JAMAIS coder un chemin absolu ici : plusieurs copies du depot coexistent
# sur la machine, et un chemin en dur ferait mesurer l'autre copie (CLAUDE.md §5.5).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from certus_physics import check_extrema_proximity_batch

# Grille de balayage du juge de paix : 450-700 nm au pas de 2 nm.
WLS = np.arange(450.0, 700.0 + 1e-9, 2.0, dtype=np.float64)
N = len(WLS)
EXCLUSION = 60.0

n_curr = np.full(N, 2.30 + 0j, dtype=np.complex128)
n_prev = np.full(N, 1.46 + 0j, dtype=np.complex128)
n_sub = np.full(N, 1.46 + 0j, dtype=np.complex128)

M_zeros = np.zeros((N, 2, 2), dtype=np.complex128)
M_id = np.zeros((N, 2, 2), dtype=np.complex128)
M_id[:, 0, 0] = 1.0
M_id[:, 1, 1] = 1.0

print(f"grille {N} points ({WLS[0]:.0f}-{WLS[-1]:.0f} nm, pas 2 nm), exclusion {EXCLUSION} nm\n")
print(f"{'M_before':<28} {'i_layer=0':>14} {'i_layer>0':>14}")

for label, M in (("zeros — la production", M_zeros), ("identite — controle", M_id)):
    cells = []
    for is_not_first in (False, True):
        kept = check_extrema_proximity_batch(
            WLS,
            n_curr,
            n_prev,
            n_sub,
            100.0,
            M,
            EXCLUSION,
            is_not_first,
            np.zeros(N, dtype=np.bool_),
        )
        cells.append(f"{N - int(kept.sum())} interdite(s)/{N}")
    print(f"{label:<28} {cells[0]:>14} {cells[1]:>14}")

# Verdict machine, pour qu'une regression soit visible.
kept_zeros = check_extrema_proximity_batch(
    WLS, n_curr, n_prev, n_sub, 100.0, M_zeros, EXCLUSION, True, np.zeros(N, dtype=np.bool_)
)
inerte = int(kept_zeros.sum()) == N
print(f"\nvolet points tournants inerte avec M_before de zeros : {inerte}")
