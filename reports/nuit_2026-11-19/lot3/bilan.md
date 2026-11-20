# Lot 3 — repères STRAT remesurés sur le code de la nuit (2026-11-20)

Code `7a6fca38` (lots 1a à 2d, `strat_local_search_fresh_id` actif), graine 42, un essai par banc, machine libre, en
série. Pilotes copiés de ceux du [21/10](../../STRAT_A3_reperes_reprise_2026-10-21/bilan.md) et du
[24/10](../../STRAT_A3_99c_grille_2026-10-24/bilan.md) : [6 bancs](run_A3_official_benches.py.txt) ([état](etat.json),
[sortie](sortie_6bancs.txt)), [99c](run_99c_seed42.py.txt) ([extrait](sortie_99c_extrait.txt), cache
`reports/intervalles_99c_nuit1120/`).

| banc | SEEL (nm) | 21/10 (`85a9e82f`) | écart | stratégies | éliminées | durée (s) |
|---|---:|---:|---:|---:|---:|---:|
| 48 c. premium (`JSON-strat-example`) | **0,1820** | 0,1721 | +5,7 % | 2 373 | 0 | 1 215 |
| 75 c. fast livré (`random75`) | **0,2142** | 0,2225 | −3,7 % | 2 072 | 0 | 1 934 |
| vrai 35 c. deep | **0,3466** | 0,4907 | −29,4 % | 1 515 | 0 | 576 |
| 36 c. deep livré | **0,3628** | 0,3238 | +12,0 % | 1 436 | 0 | 610 |
| `r75x2` natif 1 nm deep | **0,4878** | 0,5833 | −16,4 % | 4 020 | 0 | 3 847 |
| `r75x2` rampes 2 nm deep | **0,5157** | 0,5092 | +1,3 % | 3 998 | 0 | 3 901 |
| 99 c., 4 témoins, graine 42 | **0,544** | 0,597 (gr. 42, 24/10 `339e9cb3`) | −8,9 % | 1 571 (4 tranches) | 0 % | 562 |

99c : tranches 0-22 / 22-42 / 42-76 / 76-99 toutes déposables (302, 273, 678, 318 stratégies, 116 / 96 / 241 / 110 s),
`index_corridor_fixed_domain` armé, une partition assemblée.

## Lecture

- Sept repères valides, **0 plantage** partout ; les six `RANK00` viennent de la recherche locale et portent un
  identifiant neuf (`fresh_id`).
- Les écarts à octobre mêlent tout ce qui a changé depuis (recherche locale avec garde du 22/10, consensus, arrêt tardif
  `oms_arming` = 1, correctifs TMM et gradients du 19/11, lots de cette nuit) : **aucune cause n'est isolée**. À 150 tirages
  σ ≈ 6 % : 48c, 75c, rampes et 99c sont indiscernables ou proches ; **35c (−29 %) est meilleur que prévu** et **36c
  livré (+12 %) se dégrade** : deux écarts à faire regarder par 👤 avant d'en tirer quoi que ce soit.

## Constat en passant (non corrigé)

`[DYN-ALERT]` : 231 459 lignes sur le 99c, 42 934 à 701 242 par banc (journaux de 425 Mo). 90 % comparent la grille à
`Phase B (Sim) = −100 %`, c'est-à-dire `dyn = −1`, la sentinelle « couche Rate non surveillée »
(`certus_strat_growth.py`) : fausses alertes. La même sentinelle entre dans la moyenne `avg_dynamics`
(`certus_strat_batch.py`), si bien que `_worst_layer_swing` désigne une couche Rate comme la plus faible. Diagnostic et
export seulement, pas le score ; correctif proposé à part.
