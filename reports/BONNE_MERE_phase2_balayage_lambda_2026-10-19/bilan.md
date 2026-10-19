# Bonne Mère — phase 2, premier levier : la longueur d'onde de contrôle des couches lourdes (2026-10-19)

Question : en changeant la longueur d'onde de contrôle d'une seule couche, peut-on réduire le SEEL du plan
`SuperChamp76_StrictOT50_HybridMicroWin` ? Les couches essayées sont les dix plus lourdes de la phase 1
(`reports/BONNE_MERE_phase1_budget_SuperChamp76_2026-10-19/`). Banc : `scan.py.txt`, même chemin de notation que le rejeu,
plusieurs plans dans un seul processus ; il rend au bit le résultat de l'ablation sur la graine 20261019501 (SEEL rms
0,3335997910179297 nm), et deux évaluations identiques à la suite rendent les mêmes bits. Tête `ced32c35`.

## Protocole

Graines réservées avant toute mesure (`registre_graines.json`) : recherche 20261019601 (300 tirages par candidat),
sélection 20261019611 à 613, confirmation 20261019621 à 623, holdout final 20261019631 à 633, chacune 1 000 tirages.
Critère : SEEL² au bruit 0,05, zéro arrêt aux trois bruits ; comparaison appariée (mêmes tirages, C2).

## 1. Recherche : 480 plans, une couche changée à la fois, 430 à 900 nm par pas de 10 nm

| couche (λ actuel) | λ essayés | avec arrêt | meilleurs ΔSEEL² (nm²) |
|---|---|---|---|
| op 43 (505) | 48 | 31 | 510 nm +0,0003 ; 500 nm +0,0004 |
| op 58 (465) | 48 | 34 | 580 nm +0,0055 |
| op 77 (535) | 48 | 31 | 540 nm +0,0015 |
| op 87 (535) | 48 | 41 | 480 nm +0,0894 |
| op 36 (495) | 48 | 28 | 500 nm +0,0009 |
| **op 25 (520)** | 47 | 8 | **570 nm −0,0025** ; 670 nm −0,0003 |
| op 19 (579) | 48 | 21 | 580 nm +0,0002 |
| op 32 (511) | 48 | 33 | 510 nm +0,0000 |
| op 65 (524) | 48 | 31 | 520 nm +0,0002 |
| op 23 (563) | 48 | 16 | 570 nm +0,0015 |

Neuf couches sur dix sont déjà à leur optimum local : aucun autre λ ne fait mieux, et la plupart provoquent des arrêts.
Base sur la graine de recherche : SEEL rms 0,3398 nm (SEEL² 0,1155 nm²), aucun arrêt.

## 2. Sélection (3 × 1 000 tirages)

| candidat | ΔSEEL² à 0,025 / 0,05 / 0,10 (nm²) | arrêts |
|---|---|---|
| op 25 à 570 nm | −0,0022 / −0,0026 / −0,0039 (± 0,0001 à 0,0002) | 0 |
| op 25 à 670 nm | −0,0002 / −0,0002 / +0,0003 | 0 |

Retenu et gelé : **SC76 + op 25 à 570 nm** (`plan_SC76_op25_570.json`, seule différence avec SC76 : op 25,
composant 23, Nb₂O₅, contrôlé à 570 nm au lieu de 520 nm ; mêmes couches Rate).

## 3. Confirmation puis holdout final (3 × 1 000 tirages chacun, apparié contre SC76)

| graines | bruit | SEEL rms (nm) | SEEL P95 (nm) | ΔSEEL² (nm²) | ΔRMSE (pp) | arrêts |
|---|---|---|---|---|---|---|
| confirmation | 0,05 | 0,3331 → 0,3293 | 0,4647 → 0,4573 | −0,0025 ± 0,0001 | −0,00151 | 0 → 0 |
| holdout | 0,025 | 0,2989 → 0,2951 | 0,4344 → 0,4275 | −0,0022 ± 0,0001 | −0,00139 | 0 → 0 |
| holdout | 0,05 | 0,3336 → 0,3300 | 0,4631 → 0,4549 | −0,0024 ± 0,0001 | −0,00151 | 0 → 0 |
| holdout | 0,10 | 0,4470 → 0,4425 | 0,5915 → 0,5837 | −0,0040 ± 0,0002 | −0,00238 | 0 → 0 |

Le gain se retrouve sur chacune des six graines (−0,0024 à −0,0025 nm² au bruit 0,05). Il est réel et faible :
−1,8 % sur le SEEL P95, −1,1 % sur le SEEL rms.

## Ce que cela dit pour la suite

- L'optimisation du soir a atteint un optimum local pour la longueur d'onde couche par couche : ce levier est presque
  épuisé. La marge restante (61 % du SEEL² vient de l'erreur d'indice, phase 1) demande un levier d'une autre nature :
  plusieurs couches à la fois, la partition Optique / Rate, la tête de l'empilement, ou une meilleure connaissance de
  l'indice.
- Pour STRAT en général : un balayage local d'une couche à la fois, jugé sur le SEEL apparié, rend ici 1 à 2 % ; c'est un
  ultime affinage, pas la source des grands gains.
- Non mesuré : le comportement du plan retenu à bruit optique faible (défaut op 88 de la phase 1), la dérive de la
  source.

## Fichiers

`balayage_recherche_480.jsonl` (une ligne par plan), `selection.jsonl`, `confirmation_holdout.jsonl` et leur résumé
apparié `confirmation_holdout_apparie.txt` ; `balayage_resume.txt` ; scripts `scan.py.txt` et `summarise_scan.py.txt`.
Tirages bruts de la sélection, de la confirmation et du holdout (validité, RMSE, SEEL par tirage) : `tirages_selection/` et `tirages_confirmation_holdout/` ; ceux de la recherche ne sont pas gardés, chaque ligne se régénère en 3 s.
