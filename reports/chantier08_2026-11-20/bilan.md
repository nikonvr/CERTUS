# Chantier 8 — pourquoi la population de STRAT variait d'un run à l'autre (2026-11-20)

Constat du [chantier 7](../chantier07_2026-11-20/bilan.md) : au même code, le 36c deep livré (graine 42) avait rendu 1 436
(20/11), 1 446 et 1 435 stratégies, le même premier plan, et des RESULT égaux à 3e-14 près. Ordre de 👤 : en trouver la
cause. Code `ec5603a5` (STRAT identique à `a059cf47` du matin), bancs en série, `bench_examples.py strat`.

| run | conditions | stratégies | RESULT | `STRAT_BEST_ELITE` | durée (s) |
|---|---|---:|---|---:|---:|
| 20/11 (`7a6fca38`) | lot 3, cache rempli avant le banc | 1 436 | 0,03289847734767073 | — | 610 |
| matin, témoin 2 graines | autre session active ; clé du cache neuve (`a059cf47`) : noyaux compilés dans le banc | 1 446 | 0,03289847734766969 | 0,035408 | 1 083 |
| matin, 6 graines | autre session active ; cache en partie rempli par le témoin | 1 435 | (contrôle à 6 graines) | 0,035408 | 684 |
| A | machine libre, cache rempli par la validation (12:08–12:13, 16 processus) | 1 436 | 0,03289847734767073 | 0,035408 | 612 |
| B | idem | 1 436 | 0,03289847734767073 | 0,035408 | 587 |
| C | idem, **sous 12 processus de charge** | 1 436 | 0,03289847734767073 | 0,035408 | 2 019 |
| D | machine libre, **cache Numba vierge** (`NUMBA_CACHE_DIR` neuf) | **1 446** | **0,03289847734766969** | 0,035408 | 982 |

Scripts : [A et B](run_deux_36c.sh), [C](run_sous_charge.sh), [D](run_cache_vierge.sh) ; journaux bruts hors dépôt.

## Lecture

- **STRAT est déterministe à cache donné** : A, B et C sont identiques au bit, journaux compris (seul l'ordre de quelques
  événements Qt diffère), et la charge CPU ne change rien (C).
- **L'écart vient du contenu du cache Numba** : sur cache vierge (D), le banc rend exactement les valeurs du témoin du
  matin, lancé lui aussi juste après un changement de clé du cache ; sur le cache rempli par les 16 processus de la
  validation, il rend celles du 20/11. C'est le mécanisme déjà décrit le 11/11
  ([cache d'un arbre neuf](../refactor_corridors_2026-11-11/cache_numba_arbre_neuf.md)) : les noyaux `fastmath` n'ont pas
  les mêmes derniers bits selon le contexte où chaque spécialisation a été compilée. Dans le Monte-Carlo de STRAT, ces
  derniers bits suffisent à faire basculer quelques décisions discrètes : la première divergence des journaux est le SEEL
  de trois parents SYM au tour 1 d'ELITE (0,4639 contre 0,4648), puis la population (±10 stratégies sur 1 436, 0,7 %).
- Effet sur les repères : nul sur le premier plan et sur `STRAT_BEST_ELITE`, 3e-14 sur le RESULT, 0,7 % sur la
  population. Mais deux repères ne sont comparables au bit que mesurés sur le même état de cache.

## Lu en chemin (sans effet ici, non corrigé)

- `_strategy_signature` (clé du cache de consensus) ignore les couches Rate, alors que `_plan_signature` les prend : deux
  plans aux mêmes blocs et à d'autres couches Rate partagent un score de consensus en cache.
- L'étage `[LOCAL_SEARCH]` d'ELITE (`certus_strat_consensus.py`) collecte ses candidats en `as_completed` puis prend le
  `min` : à égalité de score, le choix dépend de l'ordre de fin des threads (aucun cas observé ici : A = B = C).

## Proposition

Pour des repères reproductibles au bit, les bancs officiels compilent sur un cache vierge (comme `c1_diff.py`, « froid
contre froid ») ou sur un cache que seule la validation n'a pas touché. Décision de 👤 : l'imposer aux pilotes de bancs,
ou donner à la validation son propre cache Numba.
