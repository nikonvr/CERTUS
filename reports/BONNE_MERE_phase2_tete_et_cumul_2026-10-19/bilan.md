# Bonne Mère — phase 2, troisième levier (tête de l'empilement) et bilan cumulé (2026-10-19)

Base : le plan retenu au deuxième levier (`reports/BONNE_MERE_phase2_partition_2026-10-19/`), SC76 avec op 25 contrôlée à
570 nm et op 4 en Rate. Tête : op 1 et op 2 (précouches du témoin) à 452 nm, op 3 (première couche de la pièce) à
444 nm. Banc : `scan.py.txt` de `reports/BONNE_MERE_phase2_balayage_lambda_2026-10-19/`. Graines réservées pour cette
passe (`registre_graines.json`, `round3_head`) : recherche 20261019681 (300 tirages par plan), sélection 20261019691 à
693, confirmation 701 à 703, holdout final 711 à 713 ; bilan cumulé sur 20261019721 à 723 (`cumulative_check`), jamais
lues avant. Tête `3bd802a6`.

## 1. Recherche : 240 plans

| essai | λ essayés | avec arrêt | meilleurs ΔSEEL² au bruit 0,05 (nm²) |
|---|---|---|---|
| λ commun à op 1, 2, 3 (430 à 900 nm, pas de 5) | 95 | 72 | 455 nm −0,0004 ; 450 nm −0,0002 |
| op 1 seule (pas de 10) | 48 | **48** | aucun plan sans arrêt |
| op 2 seule | 48 | 17 | 440 nm −0,0001 |
| op 3 seule | 48 | 33 | 450 nm −0,0002 |

Base sur la graine de recherche : SEEL rms 0,3138 nm, aucun arrêt. La tête est très contrainte : changer op 1 seule
fait toujours échouer le dépôt.

## 2. Sélection, confirmation, holdout (λ commun 455 nm, apparié contre la base du levier, 3 × 1 000 tirages)

| graines | ΔSEEL² à 0,025 / 0,05 / 0,10 (nm²) | SEEL P95 au bruit 0,05 (nm) | arrêts |
|---|---|---|---|
| sélection | −0,0005 / −0,0007 / −0,0008 | — | 0 |
| confirmation | −0,0006 / −0,0006 / −0,0007 | 0,4503 → 0,4487 | 0 |
| holdout final | −0,0006 / −0,0007 / −0,0006 | 0,4500 → 0,4487 | 0 |

Gain réel, constant sur les neuf graines, mais minuscule (≈ −0,6 % du SEEL²) : ce levier est épuisé.

## 3. Bilan cumulé : SC76 contre le plan final de la phase 2 (graines neuves, 3 × 1 000 tirages)

Plan final (`plan_final_phase2.json`) : SC76 avec op 1, 2 et 3 contrôlées à 455 nm, op 25 à 570 nm et op 4 en Rate
(75 couches pièce en Optique, 21 en Rate, toutes les couches Rate sous OT ≤ 50 nm).

| bruit | SEEL rms (nm) | SEEL P95 (nm) | SEEL P99 (nm) | ΔSEEL² (nm²) | RMSE moyen (pp) | meilleur sur | arrêts |
|---|---|---|---|---|---|---|---|
| 0,025 | 0,3000 → 0,2936 | 0,4372 → 0,4233 | 0,5095 → 0,4904 | −0,0038 ± 0,0002 (−4,3 %) | 1,51824 → 1,51584 | 65,8 % | 0 → 0 |
| 0,05 | 0,3315 → 0,3234 | 0,4607 → 0,4460 | 0,5348 → 0,5142 | −0,0052 ± 0,0002 (−4,8 %) | 1,53107 → 1,52778 | 69,8 % | 0 → 0 |
| 0,10 | 0,4479 → 0,4356 | 0,5935 → 0,5762 | 0,6744 → 0,6604 | −0,0109 ± 0,0004 (−5,4 %) | 1,58807 → 1,58146 | 70,9 % | 0 → 0 |

## Ce que la phase 2 enseigne

- Les trois leviers locaux (λ d'une couche, partition d'une couche, tête) ont rendu ensemble ≈ 5 % du SEEL² : le plan du
  soir était déjà près d'un optimum local. Aucun ne touche la source dominante (l'erreur d'indice, 61 % du SEEL² en
  phase 1).
- Pour STRAT en général : une fois un plan obtenu, un affinage couche par couche jugé sur le SEEL apparié, avec des
  graines réservées par usage, rend encore quelques pour cent sans risque d'arrêt ; il ne remplace pas la recherche
  globale qui a produit le plan.
- Non mesuré : le plan final à bruit optique faible (défaut op 88 de la phase 1) et sous dérive de la source (A6).
