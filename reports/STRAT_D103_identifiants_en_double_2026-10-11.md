# D103 — deux groupements minés sous un même identifiant : le consensus donne à l'un le score de l'autre

Trouvé le 2026-10-11 en instruisant l'échec de la graine 42 de `r75x2` dans la remesure qui suit la correction de D100
(`reports/remesure_D100_2026-10-11/`, commit `782972bf`).

## Le symptôme

`scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 42` s'arrête après 28,9 min, verdict `ECHEC_RESULT_NONE`
(`reports/blocs_vs_plantage_r75x2_deep_s042_20261011_202227.json`) :

```
ValueError: Missing or duplicate strategy_id '15239' in result rows 195 and 417; table and export withheld
```

Le garde-fou `validate_unique_strategy_ids` (`certus/core/certus_strat_ranking.py`, ajouté le 2026-10-04 avec D5) a
refusé le classement final : la liste des parents ELITE du même run montre deux plans différents sous l'identifiant
15239, l'un `THICKNESS²`, l'autre `SYM`. Les graines 404 et 505 de la même remesure s'arrêtent de même, sur les
identifiants 15233 et 12228 : **trois graines sur sept** (`reports/STRAT_remesure_D100_2026-10-11.md`).

## La cause

Le mineur numérote les groupements de chaque carte de coût `n_blocs × 1000 + décalage + rang`, décalages 0
(`THICKNESS`), 100 (`THICKNESS²`), 200 (`SYM`), 300 à 500 (couverture λ), 800 (semences structurées). D5 a plafonné
`top_k` à 100 en tenant qu'une carte rend au plus `top_k` groupements ; son test remplace la DP par une fausse DP
qui rend `min(top_k, 150)` groupements. La vraie DP garde un faisceau de `2 × top_k` et le rend en entier
(`_dp_kernel`, `certus/physics/certus_strat_dp.py`). À `dp_top_k = 100`, une carte rend jusqu'à 200 groupements :
les rangs 100 à 199 de `THICKNESS` prennent les numéros des rangs 0 à 99 de `THICKNESS²`, ceux de `THICKNESS²` les
numéros de `SYM`. Mesuré par le nouveau test sur une petite carte (3 blocs, 6 couches, 20 λ) : **602 groupements minés,
402 identifiants distincts**. Sur `r75x2`, « Mining found 601 strategies » aux nombres de blocs 11 à 15 : trois
cartes à 200, plus une semence structurée.

Le plan de numérotation, le faisceau `2 × top_k` et le consensus rangé par identifiant sont dans le premier commit
(`38ffb685`, 2026-04-27).

## Ce que cela fausse

Le consensus (`certus/core/certus_strat_robustness.py`, consensus « pre-elite ») range les scores par identifiant :
`_consensus_cached[sid]` reçoit les scores de graine des deux homonymes, `consensus_map[sid]` n'en garde qu'un, et
`_apply_consensus_scores_to_results` le réécrit sur **toutes** les lignes qui portent cet identifiant, y compris un
homonyme qui n'était pas candidat. Deux plans différents repartent avec le même score ; le classement, donc le choix
des parents ELITE, en dépend. Les `origin` du type `RATE_L65(from 15239)` ne disent plus de quel plan vient la variante.

Mesuré dans les journaux de la campagne `r75x2` du 2026-10-11 au matin (sept graines, sous D100,
`reports/campagne_r75x2_protocole_aout_2026-10-11/`), sur les seules listes de parents ELITE (dix plans par tour) :
des identifiants qui désignent deux plans à six graines sur sept (1, 7, 1, 2, 0, 2 et 13 identifiants aux graines 42,
77, 101, 202, 303, 404 et 505), et 22 groupes d'homonymes réunis dans une même liste avec **un seul SEEL** pour 4 avec
des SEEL distincts. Exemples :

| graine | id | plan | plantage | marge | SEEL affiché |
|---|---|---|---|---|---|
| 42 | 10288 | `SYM` | 36 % | −1706,53 Å | 0,6734 |
| 42 | 10288 | `THICKNESS²` | 10 % | −1701,59 Å | 0,6734 |
| 202 | 10291 | `SYM` | 42 % | −1718,80 Å | 0,6712 |
| 202 | 10291 | `THICKNESS²` | 6 % | −1735,89 Å | 0,6712 |
| 404 | 13174 | `THICKNESS²` | 0 % | +0,27 Å | 0,5663 |
| 404 | 13174 | `THICKNESS` | 2 % | −1152,20 Å | 0,5663 |

Ces runs ont fini sans erreur parce que les deux homonymes n'atteignaient pas ensemble la liste finale. Le plantage
d'un plan reste calculé sur ce plan : le compte des déposables d'une population n'est pas faussé ligne à ligne, mais
la recherche qui l'a produite a choisi ses parents sur des scores mélangés.

**Touché :** tout run `deep` ou `extreme` (`dp_top_k = 100`, `_MODE_BUDGETS` de `certus/ui/certus_strat_ui_state.py`)
dont une carte dépasse cent groupements, et l'élargissement de la sonde (`dp_top_k = 200`, écrêté à 100) ; donc les
campagnes `r75x2` d'août, du 2026-10-11 matin et du 2026-10-11 soir. **Pas touché :** `fast` (20) et `premium` (40),
dont la DP rend au plus 40 et 80 groupements par carte — le juge de paix et le 99c en `premium` ; ni `r75x0.5`, dont
le mineur ne trouve qu'une ou deux semences structurées par nombre de blocs.

## La correction

`de9a2025` (branche `fix-d103`) : `_mined_strategy_id` garde la numérotation des cent premiers groupements de chaque
carte et place les cent suivants dans leur propre plage, `STRATEGY_ID_MINED_OVERFLOW_BASE` (800 000 000 +
n_blocs × 100 000 + décalage + rang). Un run dont les cartes s'arrêtent à cent garde ses identifiants, donc ses bits ;
à vérifier sur le juge de paix (`premium`), qui doit rendre `RESULT` 0.007917103726810235 comme à `782972bf`. Le test
`test_the_real_dp_returns_twice_top_k_and_every_mined_id_stays_unique`
(`tests/unit/test_strat_strategy_id_ranges.py`) fait tourner la vraie DP et échoue sur le code d'avant.

Le corpus de `scripts/c1_diff.py` n'appelle pas le mineur : il ne prouve rien ici.

## Ce qui reste à mesurer

- le juge de paix au bit sur la branche corrigée ;
- les sept graines `r75x2` en `deep` au protocole d'août, avec D100 et D103 corrigés : les chiffres du 2026-10-11
  (matin et soir) ont tourné sous D103.
