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
  (`8d9ced13`, graine 42, avant le secours Rate et D106), 323 sur 489 avec D98 seul, 381 sur 1 034 avec l'arrêt tardif.
- **Avec le secours Rate, la liste finale du juge de paix ne contient que des plans déposables** : 2 260 stratégies, aucune
  éliminée par la porte de plantage, meilleur SEEL **0,1849 nm** (`03990e9a`).
- **Au code final, le meilleur SEEL ne dépend presque pas du modèle d'arrêt, mais le meilleur plan est un plan Rate sous chacun** :
  de 0,1759 à 0,1854 nm sur les cinq combinaisons (écart de 5 %, sous la dispersion de ce mode), le meilleur plan optique pur valant
  de 0,1933 à 0,2407 nm. Ce que le modèle change est le nombre de plans optiques purs déposables : 50 à l'ancien modèle, 107 avec D96
  et D97, 101 avec l'arrêt tardif, 4 avec D98 seul et **0 avec les trois options et l'attente sans fin** (mesure 4).

- **D106 coûte 8 % de SEEL au juge de paix** : ancien modèle d'arrêt, sans secours, graine 42, le meilleur SEEL passe de 0,1776 nm (les enfants
  d'ELITE sans biais de fente) à 0,1927 nm (avec) ; les repères du juge de paix d'avant la correction sont optimistes d'autant (mesure 5).

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

| configuration | surcharges | stratégies | déposables | dont optique pur | meilleur SEEL déposable |
|---|---|---|---|---|---|
| l'ancien modèle | `exact_inversion=false`, `exact_anchors=false`, `oms_arming=0` | 823 | 669 | 487 | 0,1780 nm (optique pur) |
| D96 et D97 seuls | `oms_arming=0` | 632 | 550 | 383 | 0,1787 nm (optique pur) |
| D98 seul (attente sans fin) | `exact_inversion=false`, `exact_anchors=false` | 489 | 323 | 285 | 0,1689 nm (optique pur) |
| D96, D97 et D98, arrêt tardif | `oms_arming=1` | 1 034 | 381 | 316 | 0,1904 nm (optique pur) |
| D96, D97 et D98, attente sans fin (la production) | aucune | 1 112 | 2 | 2 | 0,2000 nm (optique pur) |

Les plans déposables qui ne sont pas optiques purs sont des variantes Rate de la recherche d'alors (une couche au plus par
variante) : le meilleur de ceux-là vaut de 0,1928 à 0,1966 nm, sur les quatre premières lignes.

Le meilleur SEEL de chaque ligne est le minimum d'une population dont la taille et le contenu diffèrent d'une ligne à l'autre
(489 à 1 112 stratégies) ; l'écart de 0,1689 à 0,2000 nm (18 %) dépasse la dispersion Monte-Carlo de ce mode (σ ≈ 6 % à 150
tirages, ETAT section 2), mais **je n'ai pas séparé ce qui revient au modèle d'arrêt de ce qui revient à la population**. Ces comptes sont d'avant D106 : les
enfants d'ELITE, nombreux dans ces listes, n'avaient pas le biais de fente. Au code final, l'ancien modèle ne garde que 50 plans
optiques purs déposables au lieu de 487 (mesure 4), sans que j'aie isolé la part de D106.

## Mesure 3 : le juge de paix au modèle de production, avec le secours Rate

`python scripts\bench_examples.py strat` (`premium`, caches de l'arbre) à `03990e9a` : 2 260 stratégies, `STRAT_CRASH_ELIMINATED=0/2260`,
plantage minimal 0,0000 et médian 0,0000, meilleur plan `900150021` (ELITE, 1 bloc, λ 542 nm), `RESULT` 0,00854267382381426,
soit un SEEL de 0,1849 nm. Sortie : `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`.

## Mesure 4 : les cinq combinaisons au code final (`dbf8025f`)

Même protocole que la mesure 2 (`scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`, surcharges par
`CERTUS_PROBE_OVERRIDES`), au code final : secours Rate, `rate_by_swing` et D106. Toutes les listes sont entièrement déposables
(plantage inférieur à 5 % au pire des trois niveaux de bruit).

| configuration | stratégies | optique pur, déposables | meilleur SEEL optique pur | avec du Rate | meilleur SEEL avec du Rate | meilleur plan |
|---|---|---|---|---|---|---|
| l'ancien modèle | 1 168 | 50 | 0,1933 nm | 1 118 | 0,1854 nm | 3 blocs, 28 couches au Rate |
| D96 et D97 seuls | 1 920 | 107 | 0,2150 nm | 1 813 | 0,1820 nm | 7 blocs, 1 couche au Rate |
| D98 seul (attente sans fin) | 2 270 | 4 | 0,2407 nm | 2 266 | 0,1759 nm | 8 blocs, 13 couches au Rate |
| D96, D97, D98, arrêt tardif | 1 497 | 101 | 0,2211 nm | 1 396 | 0,1792 nm | 5 blocs, 6 couches au Rate |
| D96, D97, D98, attente sans fin (la production) | 2 260 | **0** | | 2 260 | 0,1849 nm | 1 bloc, 22 couches au Rate (indices 26 à 47) |

Lecture :

- Le meilleur SEEL va de 0,1759 à 0,1854 nm : 5 %, moins que la dispersion Monte-Carlo de ce mode (σ ≈ 6 %, une exécution par
  ligne). **Je ne sépare pas les cinq modèles par leur meilleur SEEL.**
- Le meilleur plan est un plan Rate sous les cinq : le meilleur plan optique pur est de 4 à 37 % moins bon. Le modèle de Rate de
  STRAT n'a ni dérive de la source ni bruit propre de la vitesse (`reports/STRAT_r75x0.5_secours_rate_2026-10-12.md`), ce qui le
  favorise ; la mesure ne dit pas ce que vaudrait un plan Rate sur une machine dont la vitesse dérive.
- Le nombre de plans optiques purs déposables est ce qui distingue les modèles : 0 sous l'attente sans fin complète, 101 sous
  l'arrêt tardif.
- L'ancien modèle donne ici 0,1854 nm (le meilleur plan optique pur : 0,1933 nm) et 50 plans optiques purs déposables, contre 0,1780 nm
  et 487 plans optiques purs déposables à `8d9ced13` (mesure 2) : c'est le code qui a changé entre les deux (D106, le secours Rate,
  `rate_by_swing`, les enfants d'ELITE qui gardent le Rate de leur parent), pas le modèle d'arrêt. Je n'ai pas isolé la part de
  chacun. Le résultat est une lignée optique pure moins fournie et moins bonne (0,1933 contre 0,1780 nm). Les plans optiques purs de
  la liste finale sont presque tous des enfants d'ELITE (44 sur 50 à l'ancien modèle, 97 sur 101 à l'arrêt tardif) ; **mon
  hypothèse, que je n'ai pas mesurée, est qu'ELITE, dont les parents sont maintenant en majorité des plans Rate, raffine moins la
  lignée optique pure.**

## Mesure 5 : D106 au juge de paix (ancien modèle d'arrêt, sans secours Rate, graine 42)

Même protocole que la mesure 4 (`scripts/probe_blocs_vs_plantage.py 48c premium 1 0 2 0 42 0`), avec les surcharges
`exact_inversion=false,exact_anchors=false,oms_arming=0,rate_rescue=false`. La seule différence entre les deux lignes : D106, c'est-à-dire les
enfants d'ELITE notés avec le biais de fente (corrigé) ou sans (arbre modifié : `_attach_slit_profiles` du module d'ELITE ne fait rien,
`git_dirty` vrai).

| | stratégies | déposables | dont optique pur | meilleur SEEL optique pur | meilleur SEEL |
|---|---|---|---|---|---|
| D106 remis comme avant (`dbf8025f`, arbre modifié) | 909 | 673 | 108 | 0,1792 nm | 0,1776 nm |
| D106 corrigé (`cea0db66`) | 597 | 429 | 84 | 0,1933 nm | 0,1927 nm |

D106 fait passer le meilleur SEEL du juge de paix de 0,1776 à 0,1927 nm (+8,5 %) et celui du meilleur plan optique pur de 0,1792 à 0,1933 nm
(+7,9 %). Les repères du juge de paix d'avant la correction (0,173 et 0,178 nm dans ETAT) étaient optimistes d'environ 8 %. Une graine, une
exécution par ligne.

## Ce qui reste à décider

L'attente sans fin est une hypothèse sur la machine : ce que fait l'OMS à un niveau franchi avant que son contrôleur soit armé n'est
pas connu (ETAT, section 3). Elle est le modèle de production depuis `8d9ced13`, sur décision de 👤. Les chiffres ci-dessus donnent
son prix : sur 120 plans qui survivaient à l'ancien modèle, 6 lui survivent ; la recherche sans le secours Rate n'en garde que 2 sur
1 112 ; avec lui, le meilleur SEEL du juge de paix est de 0,1849 nm. À secours égal (mesure 4), l'arrêt tardif
(`oms_arming=1`) rend un meilleur SEEL du même ordre (0,1792 contre 0,1849 nm, une exécution chacun) et garde 101 plans optiques
purs déposables, que l'attente sans fin ne garde pas : l'attente sans fin fait du Rate une nécessité pour ce composant, l'arrêt
tardif une option.

## Artefacts

`reports/STRAT_modele_d_arret_2026-10-12/` : les cinq recherches de la mesure 2 (`blocs_vs_plantage_48c_premium_s042_*_8d9ced13.json`) et les cinq de la mesure 4 (`..._dbf8025f.json`) et les deux de la mesure 5 (`..._ancien_sans_secours_*.json`), chacune avec le commit, l'état de l'arbre et les surcharges qui l'ont produite ; la mesure 1 : `probe_modele_lecture_120_plans.json` et `.txt`. La mesure 3 : `reports/STRAT_bench_juge_de_paix_03990e9a_D96-D98_secours_Rate_2026-10-12.txt`.

## Ce que ce rapport ne mesure pas

- Un seul composant (le juge de paix) et une graine (42) pour la mesure 2 ; pour `r75x2`, voir l'ETAT section 2.
- Aucun essai en salle : le modèle d'arrêt reste une hypothèse (ETAT, section 3, modèle de la chaîne de lecture).
- La mesure 1 est sans biais de fente ni Rate ; la mesure 2 est antérieure à D106 et au secours Rate ; les mesures 3 et 4 les
  comprennent. Les mesures 2 et 3 ou 4 ne se comparent donc pas ligne à ligne. Une exécution par ligne et une graine : l'écart de 5 %
  entre les meilleurs SEEL de la mesure 4 n'est pas démontré.
