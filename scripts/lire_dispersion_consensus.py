"""LA DISPERSION DU SCORE — le verrou de toute affirmation sur le classement.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_dispersion_consensus.py

🔴 **Écrit AVANT que les données n'arrivent**, le 2026-08-20 à 00:10, pendant que la cellule 1
tourne. C'est délibéré : le critère de lecture doit être fixé avant de voir les chiffres, sinon
il se choisit tout seul pour dire ce qui arrange. La journée du 2026-08-19 a coûté trois
renversements à ne pas l'avoir fait.

## Ce que ces trois runs mesurent

📏 Mesuré le 2026-08-19 : `robustness_seed` **ne touche pas le score**.
`_resolve_consensus_seeds` fait gagner `consensus_seed_list`, et les quatre composants portent
`41,42,43,44,45` tronquée à `consensus_num_seeds = 3` → **tous** les runs du projet rescorent
sur `[41,42,43]`. Deux graines différentes rendent des scores identiques à **3,2e-11**.

**Donc la dispersion du SEEL n'a jamais été mesurée.** Les trois runs ne diffèrent QUE par le
triplet de consensus. L'étendue de leurs SEEL **est** cette dispersion.

## 🔵 LE CRITÈRE, POSÉ D'AVANCE

L'écart mesuré entre coupures vaut **9,2 %** (0,689 à la coupure 52 contre 0,752 à la 46).

| dispersion mesurée | ce qu'on en conclut |
|---|---|
| **< 3 %** | les coupures **sont** séparables — le classement du §9 redevient lisible, et l'optimum à 52 est un vrai optimum |
| **3 à 9 %** | zone grise : les écarts extrêmes survivent, les voisins non. Il faudra dire lesquels |
| **> 9 %** | 🔴 **aucune coupure n'est distinguable d'une autre.** Tout le classement des coupures est du bruit, et il faut le retirer des documents |

⚠️ **Trois points ne font pas une dispersion solide** — c'est une étendue sur un échantillon de
trois, pas un écart-type fiable. Le résultat sera donc annoncé comme **une borne indicative**,
et l'énoncé « les coupures sont séparables » exigera davantage. En revanche, si la dispersion
dépasse 9 %, la conclusion inverse est **immédiate** : trois points suffisent à réfuter une
séparabilité, ils ne suffisent pas à l'établir.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRASH_TOL = 0.05
#: L'ecart entre coupures, mesure le 2026-08-19 : 0,689 (coupure 52) contre 0,752 (coupure 46).
ECART_ENTRE_COUPURES = (0.752 - 0.689) / 0.689


def main() -> int:
    motif = str(ROOT / "reports" / "blocs_vs_plantage_r75x2_fast_s042_tail52-52_cons*.json")
    fichiers = sorted(glob.glob(motif))
    if not fichiers:
        print("  aucun artefact de dispersion — les cellules 1 a 3 n'ont pas encore rendu.")
        return 0

    print("=" * 92)
    print("  DISPERSION DU SCORE — trois triplets de graines de consensus")
    print("=" * 92)
    print(f"\n  {'triplet':<18}{'n':>7}{'depos':>7}{'crash_min':>11}{'SEEL':>9}{'blocs':>7}")
    seels: dict[str, float] = {}
    for f in fichiers:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        S = d.get("strategies") or []
        trip = (d.get("config") or {}).get("consensus_seed_list", "?")
        queue = [x for x in S if str(x.get("origine") or "").startswith("RATE_TAIL52(")]
        dep = [x for x in queue if x["crash_rate"] < CRASH_TOL]
        if dep:
            b = min(dep, key=lambda z: z["score"])
            se = 2 * math.sqrt(b["score"])
            seels[trip] = se
            print(f"  {trip:<18}{len(S):>7}{len(dep):>7}{100 * b['crash_rate']:>10.2f}%"
                  f"{se:>9.4f}{b['n_blocs']:>7}")
        else:
            cm = min((x["crash_rate"] for x in queue), default=1.0)
            print(f"  {trip:<18}{len(S):>7}{0:>7}{100 * cm:>10.2f}%{'-':>9}{'-':>7}")

    if len(seels) < 2:
        print(f"\n  🟠 {len(seels)} point(s) exploitable(s) : pas de dispersion calculable.")
        return 0

    lo, hi = min(seels.values()), max(seels.values())
    etendue = (hi - lo) / lo
    print(f"\n  étendue mesurée : {lo:.4f} a {hi:.4f}  ->  **{100 * etendue:.2f} %**"
          f"   (sur {len(seels)} triplets)")
    print(f"  écart entre coupures, pour comparaison : {100 * ECART_ENTRE_COUPURES:.1f} %")

    print("\n  --- LE VERDICT, selon le critère posé AVANT la mesure ---")
    if etendue > ECART_ENTRE_COUPURES:
        print("  🔴 DISPERSION SUPÉRIEURE À L'ÉCART ENTRE COUPURES.")
        print("     Aucune coupure n'est distinguable d'une autre. Le classement des coupures")
        print("     est du bruit, et il doit être RETIRÉ des documents — pas nuancé, retiré.")
        print("     🔑 Trois points suffisent à RÉFUTER une séparabilité.")
    elif etendue > 0.03:
        print("  🟠 ZONE GRISE : la dispersion est du même ordre que les écarts voisins.")
        print("     Les extrêmes (52 contre 46) survivent peut-être, les voisins non.")
        print("     Il faut dire lesquels, coupure par coupure, et ne rien affirmer d'autre.")
    else:
        print("  🟢 DISPERSION FAIBLE : les coupures semblent séparables.")
        print("     ⚠️ MAIS trois points n'ÉTABLISSENT pas une séparabilité — c'est une étendue")
        print("     sur un échantillon de trois, pas un écart-type. À confirmer avant publication.")
    print("\n" + "=" * 92)
    return 0


if __name__ == "__main__":
    sys.exit(main())
