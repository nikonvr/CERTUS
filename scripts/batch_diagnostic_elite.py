"""BATCH DIAGNOSTIC ELITE — 👤 2026-08-20 : « seed 42 doit trouver ce que le code ne trouve pas ».

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_diagnostic_elite.py

## Le but, tel que 👤 l'a fixé

> *« on laissera quoiqu'il arrive le code de production en seed 42, mais on trouvera des
> stratégies qu'actuellement le code ne trouve pas »* — cible : un SEEL du niveau de **0,5698**
> sur `r75x2` à **2 nm**, où la graine 42 rend aujourd'hui **0 déposable sur 1617**.

## 🔴 CE BATCH NE SOIGNE RIEN. IL DIAGNOSTIQUE.

La cellule tourne aux **réglages d'origine**, aucun levier armé. C'est délibéré :
quatre hypothèses ont été réfutées le 2026-08-20, toutes pour la même raison — avoir raisonné
sur une grandeur qui ne portait pas l'information cherchée. On mesure d'abord, on soigne ensuite.

## Ce qui est ÉTABLI et qui pose la question

```
r75x2 @ 2 nm, deep
  graine 42 : 1617 strategies, LE PLUS BAS plantage = 100,00 %, ZERO sous 20 %
              ELITE ->   0 strategie
  graine 77 : 518 deposables, SEEL 0.5698, crash 1,00 %
              ELITE -> 743 strategies, et TOUTES les deposables en viennent
  Phase A   : IDENTIQUE aux deux graines (0 lambda differente sur 75, couts au bit)
```

**ELITE est le seul générateur qui produise des déposables sur ce composant.** Aucune autre
famille — `RATE_L*`, `SMART_MERGE`, `SYM`, `THICKNESS²` — n'en rend une seule, aux deux graines.

## 🔵 LES DEUX RÉCITS EN CONCURRENCE, ET CE QUI LES DÉPARTAGE

| | récit | ce qu'on verrait dans les compteurs | la réparation qu'il appelle |
|---|---|---|---|
| **A** | **ELITE est trop timide** — `span = 1` (λ ± 1 nm), et `stop_on_no_gain = True` fait qu'UN round stérile arrête tout | `engendrees` petit (~9 pour un plafond de 120) et rejets concentrés sur `halving` / `full_rmse` | élargir la recherche : `span`, `max_candidates`, `stop_on_no_gain` |
| **B** | **le bruit de la graine 42 condamne tout le voisinage** | `score_non_fini` dominant — les candidates plantent, quel que soit leur RMSE | relâcher **bruit et corridor d'indice pour ENGENDRER**, juger au nominal — le levier de 👤 |

🔑 **Les deux réparations sont déjà outillées** : les quatre leviers ELITE ont été routés
(`f9b71ba`), et `poem_anchor_noise` / `index_corridor` / `tp_hysteresis_factor` l'étaient déjà.
**Ce batch décide laquelle appliquer** — il ne les applique pas.

## Pourquoi `deep` et pas `fast`, alors que `fast` coûte trois fois moins

Deux raisons, vérifiées avant de dimensionner :

| | |
|---|---|
| à `fast`, `elite_rounds = 1` | `stop_on_no_gain` n'a alors **aucun effet** — le récit A serait intestable |
| à `fast` et 2 nm, **les deux graines** rendent 0 déposable | le contraste qui pose la question **n'existe qu'en `deep`** |

## 🔴 CE BATCH N'A QU'UNE CELLULE — passe contradictoire du 2026-08-20

La version precedente en enchainait deux (300 min). La seconde -- graine 77, pour le contraste
et pour recuperer les plans de surveillance des 518 deposables -- n'a de sens que selon ce que
dit la premiere. On lit, puis on decide.

## ✅ CE QUI A ETE VERIFIE AVANT DE DIMENSIONNER : ELITE n'est pas un symptome

L'objection la plus serieuse etait : « a la graine 42 tout plante, une candidate ELITE
planterait aussi ; ELITE a zero n'est qu'un symptome ». 📏 Comptage par famille :

    graine 42   ELITE          0 strategies      0 deposables   plantage min 100,00 %
                hors ELITE  1617                 0              100,00 %
    graine 77   ELITE        743               547                0,33 %
                hors ELITE  1488                 0              100,00 %

Aux DEUX graines, la population hors ELITE est ENTIEREMENT a 100 %. A la graine 77, ELITE a
donc CREE 547 deposables a partir d'un vivier integralement mort. Ce n'est pas un symptome :
c'est le seul etage qui produise quoi que ce soit de viable sur ce composant a 2 nm.

## Ce que la SECONDE cellule apporterait, si le diagnostic la justifie

Le run à la graine 77 est aussi le seul moyen de récupérer les **plans de surveillance** des
518 stratégies déposables : les λ par bloc. 🔴 Les artefacts antérieurs les ont tous perdus —
la sonde lisait la clé `wl` là où le noyau écrit `wavelength`, et sortait `[None, …]` **de la
bonne longueur**, donc sans rien signaler. Corrigé le 2026-08-20 (`2b2901c`).

**Ces plans sont la condition du test décisif suivant** : rejouer une stratégie trouvée sous la
graine 77 **sous le bruit de la graine 42**. S'il tient, la stratégie est bonne en soi et seule
la recherche est en cause ; s'il plante, le 0,5698 est propre à sa réalisation et aucun
relâchement ne le récupérera.

## Garde-fous

- réglages **d'origine** : aucun levier armé — c'est un diagnostic, pas un traitement
- le pilote écrit le **journal complet** dans `reports/journal_*.log` — sans quoi on ne lit
  qu'une queue de 30 lignes, ce qui a déjà fait écrire un mécanisme faux
- la sonde consigne sa configuration effective **et** les λ par bloc
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SONDE = str(ROOT / "scripts" / "probe_blocs_vs_plantage.py")

#: (nom, argv, minutes estimees)
#: argv = [composant, mode, fente, min_tp, resolution_nm, elargi, graine, par_swing]
#: par_swing = 0 -> pur optique, aucune variante Rate. On diagnostique la recherche, pas le Rate.
#
# 🔴 UNE SEULE CELLULE, ET C'EST LE RESULTAT DE LA PASSE CONTRADICTOIRE DU 2026-08-20.
# La version precedente en enchainait deux, 300 min. Mais la seconde -- la graine 77, pour
# le contraste et pour les plans de surveillance -- n'a de sens que selon ce que dit la
# premiere : si les compteurs designent le recit B, ce sont les parametres de bruit qu'il
# faut relacher, et les plans attendront. **Mettre 5 h de machine en file avant d'avoir lu
# le premier resultat est un mauvais marche.** On lit, puis on decide.
CELLULES = [
    ("1_diagnostic_s042", ["r75x2", "deep", "0", "0", "2", "0", "42", "0"], 120),
]


def main() -> int:
    t0 = time.time()
    jrn = ROOT / "reports" / f"batch_diag_elite_{datetime.now():%Y-%m-%d_%H%M}.json"
    bilan: list[dict] = []
    print("=" * 96)
    print(f"DIAGNOSTIC ELITE — {len(CELLULES)} cellules, ~{sum(c[2] for c in CELLULES)} min")
    print("REGLAGES D'ORIGINE. Ce batch ne soigne rien, il mesure ou ELITE meurt.")
    print("=" * 96, flush=True)

    for nom, argv, mn in CELLULES:
        env = dict(os.environ)
        env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        env.pop("CERTUS_TAIL_CUTS", None)
        env.pop("CERTUS_CONSENSUS_SEEDS", None)
        env["CERTUS_BENCH_TIMEOUT_S"] = str(max(5400, mn * 60 * 4))
        print(f"\n{'─' * 96}\n▶ cellule {nom} — ~{mn} min — "
              f"debut {datetime.now():%H:%M:%S}\n{'─' * 96}", flush=True)
        t = time.time()
        try:
            r = subprocess.run([PY, SONDE, *argv], cwd=str(ROOT), env=env,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=mn * 60 * 6)
            code, sortie = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, sortie = -9, "TIMEOUT du pilote"
        dt = (time.time() - t) / 60.0
        # 🔴 LE JOURNAL COMPLET VA SUR DISQUE. Sans cela on ne lit qu'une queue de 30 lignes,
        # ce qui a fait ecrire « ELITE n'a rien ajoute a la graine 77 » alors que l'artefact
        # porte 743 strategies ELITE -- on ne voyait qu'un round sur N.
        jrnl = ROOT / "reports" / f"journal_{nom}_{datetime.now():%Y%m%d_%H%M%S}.log"
        jrnl.write_text(sortie, encoding="utf-8", errors="replace")
        elite = [ligne for ligne in sortie.splitlines() if "[ELITE]" in ligne]
        print(f"  journal complet : {len(sortie.splitlines())} lignes -> {jrnl.name}", flush=True)
        print(f"  --- les {len(elite)} lignes ELITE, C'EST L'OBJET DU BATCH ---", flush=True)
        print("\n".join(f"    {ligne}" for ligne in elite), flush=True)
        print(f"◀ cellule {nom} : code={code} en {dt:.1f} min", flush=True)
        bilan.append({"cellule": nom, "argv": argv, "code": code, "minutes": round(dt, 1),
                      "lignes_elite": elite,
                      "verdict": "OK" if code == 0 else "ECHEC"})
        jrn.write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 96)
    print(f"BILAN — {sum(1 for b in bilan if b['verdict'] == 'OK')}/{len(bilan)} OK "
          f"en {(time.time() - t0) / 60:.0f} min")
    for b in bilan:
        print(f"  {b['verdict']:<6} {b['cellule']:<22} {b['minutes']:>6.1f} min")
    print("=" * 96)
    return 0 if all(b["verdict"] == "OK" for b in bilan) else 1


if __name__ == "__main__":
    sys.exit(main())
