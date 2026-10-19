# STRAT sur r75, r75x0.5, r75x2 : budget d'erreur et affinage local (2026-10-19 → 20)

Gagnants : `scripts/probe_blocs_vs_plantage.py <comp> deep 0 0 2 0 77` sur `c007325a` (artefacts locaux, non versionnés,
`reports/blocs_vs_plantage_<comp>_deep_s077.json`). Évaluateur rapide `r75_scan.py.txt` : la tâche de robustesse native,
appelée comme le pipeline ; il rend les P95 du banc à ≤ 2·10⁻⁵ près en relatif, mêmes arrêts (pas au bit). Comparaisons
appariées tirage à tirage ; graines réservées par usage (diagnostic 20261020101–103, recherche 20261020201, sélection
301–303, confirmation 401–403, holdout final 501–503, 1 000 tirages chacune sauf la recherche à 300).

## Gagnants STRAT (graine 77)

| design | blocs | couches Rate | arrêts | SEEL STRAT |
|---|---|---|---|---|
| r75 (75c) | 9 | 9 / 75 | 0,3 % | 0,247 nm |
| r75x0.5 | 12 | 56 / 75 | 0 % | 0,436 nm |
| r75x2 | 12 | 55 / 75 | 0,3 % | 0,544 nm |

## Budget d'erreur (bruit nominal, `budget_ablation.txt`)

Le corridor d'indice domine : le couper retire 63 % (r75), 36 % (r75x0.5) et 90 % (r75x2) du RMSE² ; fente et ancre POEM
pèsent ≤ 19 %. Tout coupé, il reste un plancher de SEEL de 0,07 nm (r75), 0,31 nm (r75x0.5), 0,18 nm (r75x2) ; celui de
r75x0.5, à 56 couches Rate, n'est pas expliqué ici.

**Défaut de STRAT** : bruit optique ÷ 100, **3 000 arrêts sur 3 000** pour les gagnants r75 et r75x2 (aucun pour r75x0.5),
tous `TP_MISCOUNT` sur une seule couche (r75 : couche 15 à 574 nm ; r75x2 : couche 5 à 450 nm), seulement avec le biais de
fente (`arrets_bruit_faible_*.jsonl`). Même mécanisme que Bonne Mère op 88 : `tp_hysteresis = tp_hysteresis_factor × bruit`
(facteur 1,66 dans les configurations) tend vers 0 avec le bruit, et les ondulations de la fente deviennent des extrema.

## Affinage local (λ d'une couche, puis combinaison gloutonne)

Balayage 450–750 nm par pas de 5 sur chaque couche optique (6 383 plans, `balayage_*.jsonl`), sélection appariée
(gain > 2 erreurs types, arrêts ≤ ceux de la référence, score P95 ≤ celui de la référence), combinaison une à une,
plan gelé, puis confirmation et holdout. Holdout final, bruit nominal :

| design | changements | RMSE² | SEEL STRAT | arrêts |
|---|---|---|---|---|
| r75 | 8 couches | −40,7 % (ET 0,6) | 0,2453 → **0,2189 nm** | 6 → 5 |
| r75x0.5 | couche 5 : 631 → 490 nm | −15,5 % (ET 1,1) | 0,4363 → **0,4198 nm** | 0 → 0 |
| r75x2 | couches 14 → 730 nm, 12 → 485 nm | −18,4 % (ET 0,7) | 0,5447 → **0,5212 nm** | 0 → 0 |

Confirmation : −41,2 %, −17,3 %, −17,4 %. Plans dans `plans/`. Un premier passage exigeait 0 arrêt quel que soit celui de
la référence et écartait presque tout (`affinage_75c_critere_arrets_0_ecarte.txt`).

## Pour STRAT

- STRAT classe sur le P95 et s'arrête à un optimum que la moyenne appariée dépasse encore, sans dégrader P95 ni arrêts :
  un étage final d'affinage apparié (λ couche par couche, combinaison gloutonne, graines réservées) gagne sur les trois
  designs, comme sur Bonne Mère.
- Un plancher d'hystérésis indépendant du bruit supprimerait le défaut à bruit faible.
- Non mesuré : dérive de la source (A6), d'autres graines de banc que 77, les deux autres leviers de Bonne Mère (bascule
  Optique / Rate, tête).
