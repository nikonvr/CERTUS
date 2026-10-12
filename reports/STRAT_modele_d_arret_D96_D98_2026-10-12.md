# Le modèle d'arrêt par défaut (D96, D97, D98) : ce qu'il fait au juge de paix (2026-10-12)

Décision de 👤 (2026-10-12, ETAT section 3) : l'ancre exacte (D96) et l'inversion exacte (D97) de l'arrêt POEM sont actives par
défaut ; l'OMS attend sans fin quand le niveau d'arrêt est plus proche de l'extremum que le seuil d'hystérésis (D98) : la couche
est plantée, il n'y a pas d'arrêt tardif. Ce rapport mesure ce que ce modèle fait au juge de paix (`JSON-strat-example.json`, 48
couches), et ce que le secours Rate (`reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`) en rend.

## Réponse

- **L'attente sans fin retire 95 % des plans que l'ancien modèle jugeait fabricables** : sur 120 plans notés de nouveau, 120
  sont déposables à l'ancien modèle, 6 à l'attente sans fin, avec ou sans D96 et D97. Le rapport médian des scores de ces 6 plans à
  ceux de l'ancien modèle vaut de 0,993 à 1,001.
- **La recherche n'en retrouve qu'une fraction, très variable** : 2 plans déposables sur 1 112 avec les trois options
  (`8d9ced13`, graine 42), 323 sur 489 avec D98 seul, 381 sur 1 034 avec l'arrêt tardif.
- **Avec le secours Rate, la liste finale du juge de paix ne contient que des plans déposables** : 2 260 stratégies, aucune
  éliminée par la porte de plantage, meilleur SEEL **0,1849 nm** (`03990e9a`), contre 0,178 nm à l'ancien modèle (ETAT section 2,
  `782972bf`).

## Ce qui a changé dans le code

`stop_model_flags(params)` (`certus/physics/certus_strat_readings.py`) rend `(exact_inversion, exact_anchors, arming)`, par défaut
`(True, True, 2)`. Les noyaux gardent l'ancien chemin comme valeur par défaut de leur signature (C1) ; les appels de production
passent ces trois valeurs, et un jeu de paramètres peut redemander l'ancien modèle par `exact_inversion=false`,
`exact_anchors=false`, `oms_arming=0` (les bases de comparaison des sondes). `arming` : 0 arrêt au niveau, 1 arrêt tardif, 2 attente
sans fin (cause de plantage `CRASH_NOT_ARMED`). La Phase A, la croissance et la notation de la Phase B lisent les mêmes trois
valeurs : un modèle d'arrêt, jamais deux (`tests/unit/test_strat_stop_model_is_the_decided_one.py`).

## Mesure 1 : 120 plans notés de nouveau sous quatre variantes de l'attente sans fin

`scripts/probe_modele_lecture.py example/example_strat/JSON-strat-example.json reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json
--runs 300 --first 120 --models livre,livre_attente,livre_ancres_attente,livre_exact_attente,livre_corrige_attente` (Python 3.14.8).
Les 120 premiers plans du banc du 2026-10-04 sont notés par les noyaux de production sous chaque modèle (300 tirages, pire des
trois niveaux de bruit, porte de plantage à 5 %).

| modèle | D96 | D97 | D98 | plans déposables sur 120 | Spearman avec `livre`, sur les 6 plans déposables des deux | rapport médian des scores |
|---|---|---|---|---|---|---|
| `livre` (l'ancien) | non | non | non | 120 | | |
| `livre_attente` | non | non | attente sans fin | 6 | 1,000 | 1,000 |
| `livre_ancres_attente` | oui | non | attente sans fin | 6 | 0,943 | 0,993 |
| `livre_exact_attente` | non | oui | attente sans fin | 6 | 0,943 | 1,001 |
| `livre_corrige_attente` | oui | oui | attente sans fin | 6 | 0,829 | 0,999 |

Les cinq meilleurs scores : `livre` 0,00753 à 0,00787 (SEEL 0,1735 nm pour le premier) ; `livre_attente` 0,007974 à 0,00892 (SEEL
0,1786 nm) ; `livre_corrige_attente` 0,00803 à 0,008946 (SEEL 0,1792 nm).

Ce que la mesure ne dit pas : la population est celle du banc du 2026-10-04, trouvée par l'ancien modèle (elle est faite de plans
qui lui survivent) ; le biais de fente et les couches Rate n'y sont pas, la comparaison porte sur le modèle d'arrêt seul.

## Mesure 2 : la recherche complète, cinq configurations

`CERTUS_PROBE_OVERRIDES="…" scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0` à `8d9ced13` (avant le secours Rate et
avant D106 : les enfants d'ELITE n'ont ni le biais de fente ni les couches Rate de leur parent), `premium`, graine 42, fente 2 nm,
un seul verre témoin. Une recherche complète par ligne ; « déposable » : plantage inférieur à 5 % au pire des trois niveaux de bruit.

| configuration | surcharges | stratégies | déposables | meilleur SEEL déposable |
|---|---|---|---|---|
| l'ancien modèle | `exact_inversion=false`, `exact_anchors=false`, `oms_arming=0` | 823 | 669 | 0,1780 nm |
| D96 et D97 seuls | `oms_arming=0` | 632 | 550 | 0,1787 nm |
| D98 seul (attente sans fin) | `exact_inversion=false`, `exact_anchors=false` | 489 | 323 | 0,1689 nm |
| D96, D97 et D98, arrêt tardif | `oms_arming=1` | 1 034 | 381 | 0,1904 nm |
| D96, D97 et D98, attente sans fin (la production) | aucune | 1 112 | 2 | 0,2000 nm |

Le meilleur SEEL de chaque ligne est le minimum d'une population dont la taille et le contenu diffèrent d'une ligne à l'autre
(489 à 1 112 stratégies) ; l'écart de 0,1689 à 0,2000 nm (18 %) dépasse la dispersion Monte-Carlo de ce mode (σ ≈ 6 % à 150
tirages, ETAT section 2), mais **je n'ai pas séparé ce qui revient au modèle d'arrêt de ce qui revient à la population**.

## Mesure 3 : le juge de paix au modèle de production, avec le secours Rate

`python scripts\bench_examples.py strat` (`premium`, caches de l'arbre) à `03990e9a` : 2 260 stratégies, `STRAT_CRASH_ELIMINATED=0/2260`,
plantage minimal 0,0000 et médian 0,0000, meilleur plan `900150021` (ELITE, 1 bloc, λ 542 nm), `RESULT` 0,00854267382381426,
soit un SEEL de 0,1849 nm. Sortie : `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`.

## Ce qui reste à décider

L'attente sans fin est une hypothèse sur la machine : ce que fait l'OMS à un niveau franchi avant que son contrôleur soit armé n'est
pas connu (ETAT, section 3). Elle est le modèle de production depuis `8d9ced13`, sur décision de 👤. Les chiffres ci-dessus donnent
son prix : sur 120 plans qui survivaient à l'ancien modèle, 6 lui survivent ; la recherche sans le secours Rate n'en garde que 2 sur
1 112 ; avec lui, le meilleur SEEL du juge de paix est de 0,1849 nm. L'arrêt tardif (`oms_arming=1`) en garde 381 sur 1 034 sans le
secours ; **je n'ai pas mesuré l'arrêt tardif avec le secours Rate** : sa comparaison à l'attente sans fin, à secours égal, manque.

## Artefacts

`reports/STRAT_modele_d_arret_2026-10-12/` : les cinq recherches de la mesure 2 (`blocs_vs_plantage_48c_premium_s042_*_8d9ced13.json`, chacune avec le commit, l'état de l'arbre et les surcharges qui l'ont produite) et la mesure 1 (`probe_modele_lecture_120_plans.json` et `.txt`). La mesure 3 : `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`.

## Ce que ce rapport ne mesure pas

- Un seul composant (le juge de paix) et une graine (42) pour la mesure 2 ; pour `r75x2`, voir l'ETAT section 2.
- Aucun essai en salle : le modèle d'arrêt reste une hypothèse (ETAT, section 3, modèle de la chaîne de lecture).
- La mesure 1 est sans biais de fente ni Rate ; la mesure 2 est antérieure à D106 et au secours Rate ; la mesure 3 les comprend.
  Les mesures 2 et 3 ne se comparent donc pas ligne à ligne.
