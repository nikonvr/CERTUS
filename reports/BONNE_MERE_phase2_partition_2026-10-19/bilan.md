# Bonne Mère — phase 2, second levier : la partition Optique / Rate, une couche à la fois (2026-10-19)

Question : en faisant passer une seule couche d'Optique à Rate, ou de Rate à Optique, peut-on encore réduire le SEEL ?
Base : le plan retenu au premier levier, SC76 avec op 25 contrôlée à 570 nm
(`reports/BONNE_MERE_phase2_balayage_lambda_2026-10-19/`). Banc : `scan.py.txt` de ce même dossier. Une couche passée
en Optique garde la longueur d'onde que portait déjà son bloc. Graines : recherche 20261019602 (300 tirages par plan),
puis des graines neuves réservées pour cette passe (`registre_graines.json`, `round2_partition`) : sélection 20261019651
à 653, confirmation 661 à 663, holdout final 671 à 673, 1 000 tirages chacune. Tête `c572ac92`.

## 1. Recherche : les 96 bascules

- Base sur la graine de recherche : SEEL rms 0,3272 nm, aucun arrêt.
- **Aucune bascule Rate → Optique n'aide, et 17 des 20 provoquent des arrêts** (jusqu'à 267 sur 300 tirages, op 16 et
  op 92) : à la longueur d'onde de leur bloc, ces couches minces sont mal conditionnées en optique. Une seule bascule
  vers Rate provoque des arrêts (op 59).
- Les meilleures bascules envoient toutes une couche optique en Rate (ΔSEEL² au bruit 0,05) : op 42 −0,0027, op 89
  −0,0020, op 55 −0,0018, **op 4 −0,0015**, op 98 −0,0010, op 73 −0,0008 nm². Toutes, sauf op 4 (SiO₂, OT 31,18 nm),
  violent la règle OT ≤ 50 nm : le modèle ne connaît pas la dérive de la source, qui pénalise une couche Rate épaisse.
  Elles ne sont pas retenues ; leur intérêt dépend de la valeur de dérive que 👤 fixera (A6). Détail dans
  `bascules_resume.txt`.

## 2. Sélection (graines neuves)

| bascule | ΔSEEL² à 0,025 / 0,05 / 0,10 (nm²) | arrêts |
|---|---|---|
| op 4 → Rate (OT 31 nm, respecte la règle) | −0,0011 / −0,0023 / −0,0063 (± 0,0001 à 0,0003) | 0 |
| op 42 → Rate (OT 219 nm, à titre d'information) | −0,0011 / −0,0022 / −0,0057 | 0 |

Gelé : **SC76 + op 25 à 570 nm + op 4 en Rate** (`plan_SC76_op25_570_op4_rate.json`, 75 couches pièce en Optique,
21 en Rate). Op 4 est la deuxième couche de la pièce ; la consigne du soir « dix premières couches en Optique » était
une heuristique, pas une règle de 👤.

## 3. Confirmation puis holdout final (apparié contre la base du levier)

| graines | bruit | SEEL rms (nm) | SEEL P95 (nm) | ΔSEEL² (nm²) | ΔRMSE (pp) | arrêts |
|---|---|---|---|---|---|---|
| confirmation | 0,05 | 0,3283 → 0,3253 | 0,4591 → 0,4509 | −0,0019 ± 0,0002 | −0,00121 | 0 → 0 |
| holdout | 0,025 | 0,2941 → 0,2925 | 0,4290 → 0,4253 | −0,0009 ± 0,0001 | −0,00056 | 0 → 0 |
| holdout | 0,05 | 0,3298 → 0,3272 | 0,4596 → 0,4531 | −0,0017 ± 0,0002 | −0,00109 | 0 → 0 |
| holdout | 0,10 | 0,4408 → 0,4337 | 0,5849 → 0,5759 | −0,0062 ± 0,0003 | −0,00386 | 0 → 0 |

Le gain se retrouve sur chacune des six graines. Il grandit avec le bruit : basculer op 4 en Rate retire une couche
mince qui lit mal le signal. Avec le premier levier, le plan retenu gagne au bruit 0,05 environ −0,004 nm² de SEEL² sur
SC76 (≈ −3,5 %), sur deux holdouts distincts mesurés chacun contre sa propre base.

## Ce que cela dit pour la suite

- Sur ce plan, la partition est presque à l'optimum sous la règle OT ≤ 50 nm ; les gains suivants passent par des
  couches Rate épaisses, que seule la valeur de dérive (A6) peut départager.
- Pour STRAT en général : les couches minces mal conditionnées en optique sont la vraie raison d'être du Rate ; un
  critère « conditionnement de l'arrêt optique » vaut mieux qu'un rang dans l'empilement (la tête n'a pas à rester en
  optique par principe).
- Non mesuré : le plan retenu à bruit optique faible (défaut op 88 de la phase 1), la dérive de la source.
