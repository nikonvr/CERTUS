# r75x2 à 2 nm sans rampes, protocole d'août, code du 2026-10-11 — sept graines

Question (ETAT, section 0, à `212126d4`) : le « 3 graines sur 7 » d'août tient-il avec le code d'aujourd'hui ? Et
ELITE « tour à tour » (`elite_round_robin`, inactif par défaut) change-t-il la population à graine égale ?

**Conditions.** Windows 11, Python 3.14.8, NumPy 2.5.3, Numba 0.67.0, Ryzen 7 5700G (16 fils). Code `212126d4`
(branche `claude/ecstatic-newton-3grmls`) : les huit artefacts portent `git_commit` 212126d4, `git_dirty` faux et la
même clé de cache Numba. Une graine à la fois, le 2026-10-11 de 13:16 à 16:33, de 23,2 à 26,4 min par run, aucun
`WAIT_TIMEOUT`. À côté n'ont tourné que des tâches de quelques secondes à une minute (contrôles documentaires, quatre
fichiers de tests, lectures d'artefacts) ; aucun run n'a approché son plafond de 38 400 s.

**Protocole.** Celui des sept artefacts du 2026-08-19 au 2026-08-22, à l'identique :

```bat
set CERTUS_BENCH_TIMEOUT_S=38400
python scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 <graine>
```

soit `reports/serie_echelle_r75/cfg_x2.json` (`reading_smoothing_window` 1, `machine_sampling_dd` 0 : la grille
grossière, chemin par défaut), mode `deep`, fente 2 nm sans recherche de fente, sans exigence de point tournant, sans
élargissement, `rate_by_swing` forcé à faux, aucune surcharge. Le bloc `config` et la profondeur Monte-Carlo
(300 / 50 / 100 / 300) des artefacts d'aujourd'hui sont ceux d'août. Le run « tour à tour » ajoute seulement
`CERTUS_PROBE_OVERRIDES=elite_round_robin=true` et `CERTUS_PROBE_TAG=rr`.

## Résultat

Déposable : `crash_rate` ≤ 5 % (`TOLERANCE_PLANTAGE` de `scripts/orchestre_multigraine.py` ; < 5 % rend les mêmes
comptes). SEEL = 2 √score de la meilleure déposable. `crash_rate` est le maximum sur les trois niveaux de bruit (0,025,
0,05 et 0,1 point, les mêmes qu'en août), vérifié sur chaque stratégie.

| graine | août : déposables / stratégies | aujourd'hui : déposables / stratégies | meilleur SEEL déposable | plantage minimal | stratégies ELITE |
|---|---|---|---|---|---|
| 42 | 0 / 1 617 | 674 / 768 | 0,5566 nm | 0,33 % | 582 |
| 77 | 547 / 2 231 (0,5692 nm) | 814 / 910 | 0,5355 nm | 0,33 % | 692 |
| 101 | 0 / 1 630 | 1 124 / 1 216 | 0,5603 nm | 0,33 % | 958 |
| 202 | 0 / 1 646 | 661 / 754 | 0,5547 nm | 0 % | 608 |
| 303 | 0 / 1 680 | 671 / 763 | 0,5622 nm | 0,33 % | 564 |
| 404 | 372 / 2 016 (0,5599 nm) | 1 041 / 1 107 | 0,5426 nm | 0,33 % | 946 |
| 505 | 311 / 1 995 (0,6112 nm) | 947 / 1 038 | 0,5629 nm | 0,33 % | 854 |

**Sept graines sur sept trouvent des déposables**, contre trois en août. Les populations sont plus petites (754 à
1 216 stratégies contre 1 617 à 2 231) et presque entièrement déposables (88 à 94 %). En août, toutes les stratégies
d'une graine perdante plantaient à 100 % au pire niveau de bruit ; aujourd'hui le plantage minimal vaut 0 ou 0,33 %
partout. Les meilleurs SEEL vont de 0,5355 à 0,5629 nm (5,1 %).

À la graine 42, la meilleure déposable est exactement celle du banc du 2026-10-05
(`reports/STRAT_bench_r75x2_deep_hysteresis_noise_level_306559d3_2026-10-05.json`, configuration
`JSON-strat-random75-x2-fabricable-2nm.json`) : mêmes 15 blocs, mêmes λ, SEEL 0,556561 nm, plantage 0,67 %.

## ELITE tour à tour, graine 202

| run | déposables / stratégies | meilleur SEEL déposable | stratégies ELITE |
|---|---|---|---|
| sans surcharge | 661 / 754 | 0,5547 nm | 608 |
| `elite_round_robin` | 880 / 972 | 0,5662 nm | 796 |

L'option atteint le calcul : 21 plans ELITE en commun sur 608 et 796. Les plans hors ELITE diffèrent aussi (77 en
commun sur 146 et 176) ; je n'ai pas cherché par quel chemin l'option les atteint. Elle donne 33 % de déposables en
plus, mais pas un meilleur plan : 0,5662 contre 0,5547 nm, +2,1 %, dans le bruit de ce composant (σ ≈ 1,8 % par run,
ETAT, section 2). Une seule graine ne dit rien de plus.

## Ce que cette campagne n'établit pas

- **La cause.** Entre le code d'août (de `0b0a9ce` à `cc7008d`) et `212126d4`, quelque chose a fait disparaître le
  plantage total des graines perdantes. Entre `master` (`80dd7d3c`) et `212126d4`, le noyau de croissance n'a pas
  bougé sur son chemin par défaut (C1 contre `master`, 2026-10-11 : les 171 cas sans grille machine identiques au
  bit) ; le reste de la recherche n'est pas couvert par ce corpus. Je n'ai pas cherché quel commit.
- **Que ce soit un progrès.** Un affaiblissement de la détection du plantage produirait la même signature. Les
  filtres rejettent encore quelque chose (66 à 96 stratégies non déposables par graine, et les rejets d'ELITE que
  comptent les journaux), mais cela ne l'exclut pas. Contrôle à faire : un composant connu comme non fabricable, le
  passe-bande de 99 couches en une seule campagne (ETAT, section 2 : 100 % de plantage), doit le rester. Si la cause
  importe ensuite, une bissection à la graine 303 entre `cc7008d` (0 / 1 680) et `212126d4` (25 min par run).

## Ce qui en dépend, non modifié ici

- `pages/CERTUS_STRAT.html` dit que sur `r75x2` à 2 nm la recherche n'atteint pas la famille déposable sans rampes
  (0 candidat retenu par ELITE sur 2 472) : c'était le code d'août.
- L'infobulle de l'onglet multigraine (`certus/ui/certus_strat_multigraine_ui.py`) cite l'écart d'août entre les trois
  graines gagnantes (0,5599 à 0,6112 nm, 9,2 %).
- La docstring de `scripts/orchestre_multigraine.py` cite les 3/7 d'août.

## Reproduire

```bat
set CERTUS_BENCH_TIMEOUT_S=38400
python scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 42
rem de même pour 77, 101, 202, 303, 404 et 505, une graine à la fois
set CERTUS_PROBE_OVERRIDES=elite_round_robin=true
set CERTUS_PROBE_TAG=rr
python scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 202
```

Artefacts d'aujourd'hui : `reports/blocs_vs_plantage_r75x2_deep_s042_20261011_134042.json` et
`reports/blocs_vs_plantage_r75x2_deep_s077_20261011_140620.json` (les noms nus de 42 et 77 sont ceux d'août), puis
`reports/blocs_vs_plantage_r75x2_deep_s{101,202,303,404,505,202_rr}.json` ; le résumé du lanceur,
`reports/campagne_r75x2_protocole_aout_2026-10-11/resume.txt`. Ceux d'août : `reports/blocs_vs_plantage_r75x2_deep_s042.json`,
`reports/blocs_vs_plantage_r75x2_deep_s077.json` et
`reports/avant_leviers_2026-08-22/blocs_vs_plantage_r75x2_deep_s{101_20260822_102742,202,303,404,505}.json`.
