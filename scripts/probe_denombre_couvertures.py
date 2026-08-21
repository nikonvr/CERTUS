"""COMBIEN DE STRATEGIES MULTI-LAMBDA EXISTENT-IL ? -- le comptage EXACT, en quelques secondes.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_denombre_couvertures.py [K_MAX]

👤 2026-08-17 : *« s'acharner pour moi veut dire etre certain a 100 % qu'aucune strategie
multi lambda avec un seul verre temoin ne peut fonctionner avec une statistique de reussite
excellente »*, et *« je suis pret a passer sur une simu de 24 h »*.

🔴 UNE RECHERCHE NE DONNE JAMAIS UNE NON-EXISTENCE. Elle donne « je n'ai pas trouve ». Deux
routes seulement menent a la conclusion demandee :

    (a) ENUMERER TOUT et montrer que chaque candidate echoue -- possible SI l'espace est fini
        et payable.
    (b) Une CONDITION NECESSAIRE violee partout -- une preuve, independante de toute graine.

Ce script decide laquelle est ouverte, avant d'engager la nuit de calcul. C'est la regle 1 de
la feuille de route : la sonde bon marche qui peut invalider un gros travail passe AVANT.

## Ce qui elague massivement l'espace

L'espace n'est PAS 2^98. Une strategie a un seul verre temoin est :

    une partition de [0,N) en blocs CONTIGUS
    + une lambda par bloc, commune a TOUTES les couches du bloc

La contrainte de lambda commune tue l'immense majorite des partitions. Le compte exact se fait
par programmation dynamique sur la matrice d'admissibilite (couche x lambda) que
profil_monitorabilite.py calcule deja -- aucune physique nouvelle ici.

    couvertures(k, j)  = nombre de facons de couvrir [0,j) en exactement k blocs
    strategies(k, j)   = idem, PONDERE par le nombre de lambda communes de chaque bloc

🔑 C'est `strategies` qui compte pour l'exhaustivite : une strategie, c'est une couverture ET
un choix de lambda par bloc.

## Le seuil de decision, chiffre sur cette machine

Tarif mesure le 2026-08-17 (i5-8250U, 4 coeurs / 8 threads) : ~7 s par strategie a pleine
profondeur (150 tirages x 3 niveaux de bruit), donc ~1,2 s au criblage a 25 tirages.

    24 h = 86 400 s  ->  ~70 000 strategies criblees  ou  ~12 000 a pleine profondeur

    <= ~50 000 strategies   ->  EXHAUSTIF PAYABLE en une nuit, la route (a) est ouverte
    >> 10^6                 ->  exhaustif impossible, seule la route (b) peut conclure

## Deux bases d'admissibilite, et la difference compte

    adm     swing >= dynamics_threshold  ET  plancher photometrique
    adm_tp  idem + la couche possede au moins UN extremum observable

🔒 TRANCHE PAR 👤 LE 2026-08-17, mot pour mot :

    « on considere les TPM pour le POEM : oui a 100 % »
    « on s'arrete sur un TPM : non a 100 % »

Donc le point tournant est une ANCRE, jamais une cible d'arret. POEM vise un pourcentage de
l'amplitude ENTRE les deux derniers extrema (§14) : il exige que l'extremum existe et
n'arrete jamais dessus.

`adm_tp` est par consequent la base JUSTE, et ce n'est plus une inference. On compte quand
meme `adm` a cote, pour que l'ecart entre « avoir du swing » et « avoir une ancre » soit
visible et non suppose.

⚠️ CE QUE CE COMPTE NE VOIT PAS. Une couverture valide n'est pas encore une strategie complete :
le niveau d'arret, le mode Rate et la compensation s'y ajoutent. Le Rate ouvre des variantes
que ce denombrement ignore. Il borne donc l'espace des BLOCS par le haut -- ce qui est
exactement ce qu'il faut pour une preuve d'impossibilite, mais il faudra le dire.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from pathlib import Path

import numpy as np

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SEC_CRIBLAGE = 1.2      # s par strategie a 25 tirages, mesure 2026-08-17
SEC_PROFONDEUR = 7.0    # s par strategie a 150 tirages x 3 niveaux


def _charger_profil():
    spec = importlib.util.spec_from_file_location(
        "pm", ROOT / "scripts" / "profil_monitorabilite.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    return pm


def compter(adm: np.ndarray, k_max: int) -> tuple[list[int], list[int], np.ndarray]:
    """Denombre EXACTEMENT couvertures et strategies, par nombre de blocs.

    `taille[i, j]` = nombre de lambda communes au bloc [i, j). Une seule passe O(N^2).
    """
    N = adm.shape[0]
    taille = np.zeros((N, N + 1), dtype=np.int64)
    for i in range(N):
        inter = adm[i].copy()
        for j in range(i + 1, N + 1):
            if j > i + 1:
                inter = inter & adm[j - 1]
            n = int(inter.sum())
            if n == 0:
                break                      # monotone : plus long ne peut pas rouvrir
            taille[i, j] = n

    # couv[k][j] et strat[k][j] -- entiers Python, les valeurs peuvent exploser
    couv = [[0] * (N + 1) for _ in range(k_max + 1)]
    strat = [[0] * (N + 1) for _ in range(k_max + 1)]
    couv[0][0] = 1
    strat[0][0] = 1
    for k in range(1, k_max + 1):
        for j in range(1, N + 1):
            c = s = 0
            for i in range(j):
                if taille[i, j] and couv[k - 1][i]:
                    c += couv[k - 1][i]
                    s += strat[k - 1][i] * int(taille[i, j])
            couv[k][j] = c
            strat[k][j] = s
    return [couv[k][N] for k in range(k_max + 1)], [strat[k][N] for k in range(k_max + 1)], taille


def _duree(n: int, sec: float) -> str:
    t = n * sec
    if t < 3600:
        return f"{t / 60:.0f} min"
    if t < 86400 * 3:
        return f"{t / 3600:.1f} h"
    return f"{t / 86400:.0f} j"


def rapport(nom: str, base: str, couv: list[int], strat: list[int]) -> None:
    tot_c, tot_s = sum(couv), sum(strat)
    print(f"\n  base {base} -- couvertures {tot_c:,} | STRATEGIES {tot_s:,}".replace(",", " "))
    print(f"  {'k blocs':>8} {'couvertures':>16} {'strategies':>20} {'criblage 25 tirages':>22}")
    print("  " + "-" * 70)
    for k, (c, s) in enumerate(zip(couv, strat)):
        if c == 0:
            continue
        print(f"  {k:>8} {c:>16,} {s:>20,} {_duree(s, SEC_CRIBLAGE):>22}".replace(",", " "))
    if tot_s == 0:
        print("  🔴 AUCUNE couverture valide -- l'empilement n'est pas couvrable sur cette base.")
        return
    print(f"\n  TOTAL : {tot_s:,} strategies".replace(",", " "))
    print(f"    criblage 25 tirages   : {_duree(tot_s, SEC_CRIBLAGE)}")
    print(f"    pleine profondeur     : {_duree(tot_s, SEC_PROFONDEUR)}")
    if tot_s <= 70_000:
        print("  🟢 EXHAUSTIF PAYABLE dans le budget de 24 h -- la route (a) est OUVERTE.")
    elif tot_s <= 2_000_000:
        print("  🟠 Exhaustif hors budget, mais un criblage a 10 tirages ou une reduction par")
        print("     symetrie de lambda pourrait le ramener dedans. A discuter.")
    else:
        print(f"  🔴 ~10^{math.floor(math.log10(tot_s))} strategies : exhaustif IMPOSSIBLE.")
        print("     Seule une CONDITION NECESSAIRE violee partout peut conclure -- route (b).")


def main() -> int:
    k_max = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    pm = _charger_profil()

    for nom, cfg in pm.COMPOSANTS.items():
        p = pm.profil(cfg)
        print("=" * 78)
        print(f"{nom} — {p['N']} couches, {p['n_lams']} lambda candidates, k <= {k_max}")
        print("=" * 78)
        for base in ("adm", "adm_tp"):
            couv, strat, _ = compter(p[base], k_max)
            rapport(nom, base, couv, strat)
    return 0


if __name__ == "__main__":
    sys.exit(main())
