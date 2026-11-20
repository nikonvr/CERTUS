# Chantier 7 — le contrôle de la recherche locale sur 6 graines fraîches (2026-11-20)

Décision de 👤 (2026-11-20) : publier le meilleur ELITE à côté du `RESULT` (`80f06867`, ligne `STRAT_BEST_ELITE=`) et
mesurer un contrôle sur plus de graines : réglage `strat_local_search_check_seeds` (`a059cf47`, 2 par défaut, C1 tenu
sur 9 172 tableaux). Bancs graine 42, code `a059cf47`, en série ([script](run_mesure.sh), [sortie](sortie_mesure.txt)) ;
journaux bruts hors dépôt (`*.raw.log`).

| banc | graines | contrôle du plan final | repli | RESULT | `STRAT_BEST_ELITE` | stratégies |
|---|---:|---|---|---:|---:|---:|
| 36c deep livré (témoin) | 2 | P95 0,06495 → 0,02388, arrêts 1 → 6 : refusé | 14/29 changements ; confirmation 0 → 0 : gardé | 0,032898 | 0,035408 | 1 446 |
| 36c deep livré | 6 | P95 0,06403 → 0,02368, arrêts 1 → 16 : refusé | 16/29 changements ; confirmation 0 → 2 : refusé, vainqueur inchangé | **0,037161** | 0,035408 | 1 435 |
| vrai 35c deep | 6 | P95 0,14239 → 0,04021, arrêts 950 → 33 : gardé | — | 0,030029 | 0,054555 | 1 515 |

Repères du 20/11 (`7a6fca38`, 2 graines) : 36c RESULT 0,032898 (1 436 stratégies), 35c RESULT 0,030029 (gardé, 338 → 10).

## Lecture

- **Le verdict sur le plan final ne bascule pas** avec 6 graines : le 35c reste gardé, le 36c reste refusé (son plan
  ajoute bien des arrêts : 1 → 6 sur 2 graines, 1 → 16 sur 6). La recherche elle-même est identique (passe 1 : 22
  changements, 464 évaluations ; passe 2 : 29 changements).
- **Ce qui change est le repli** : sur 6 graines, il choisit un autre plan intermédiaire (16 changements au lieu de 14),
  qui échoue à la confirmation (encore sur 2 graines, 0 → 2 arrêts). Le 36c perd la recherche locale : RESULT +13 %.
- **Les écarts aux repères d'octobre ne venaient donc pas du hasard de deux graines sur un même plan**, mais de plans
  différents d'une version du code à l'autre (bilan 6). Plus de graines rend le contrôle plus strict, pas plus stable :
  il voit plus d'arrêts rares.
- `STRAT_BEST_ELITE` est identique entre 2 et 6 graines (0,035408 ; 35c 0,054555 comme le 20/11) : c'est la grandeur
  stable qu'on peut comparer entre versions.

## Écart constaté, non expliqué

Le témoin à 2 graines rend le même premier plan (`902150000`) que le 20/11, mais pas au bit : RESULT 0,03289847734766969
contre 0,03289847734767073 (3e-14 relatif) et 1 446 stratégies contre 1 436. Au même code, les deux runs du 36c donnent
1 446 et 1 435 stratégies alors que les graines du contrôle n'interviennent qu'après. Les changements STRAT depuis le
20/11 sont du diagnostic (chantier 5) ou inertes à 2 graines ; aucune limite de temps trouvée dans le cœur STRAT ; la
machine portait une autre session (témoin 1 083 s contre 610 s). La population de STRAT varie donc d'un run à l'autre :
cause non isolée.

## Proposition

Garder le défaut à 2 (le contrôle plus strict coûte la recherche locale au 36c sans rendre les repères plus stables) et
comparer les versions par `STRAT_BEST_ELITE` à côté du `RESULT`. Le changement de défaut reste une décision de 👤.
