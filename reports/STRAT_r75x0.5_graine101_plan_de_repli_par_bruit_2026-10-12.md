# r75x0.5, graine 101 — le plan de repli, niveau de bruit par niveau de bruit (2026-10-12)

Question de 👤 (2026-10-12) : quand rien n'est déposable, le logiciel garde la moins mauvaise stratégie, celle au plantage le plus bas,
ici celle de la graine 101 (1,7 / 1,7 / 8,3 %) ; quel est son SEEL ?

## Réponse

Le plan est `990500008` (`RATE_L31(from 900600169)`, 5 blocs aux λ de contrôle 636, 686, 737, 747, 734 nm, `rate_layers` [31]). Le logiciel affiche **SEEL 0,673 nm** (`score` 0.113306).

Mesuré niveau par niveau sur 300 tirages de la graine de base (rejeu, voir plus bas) :

| niveau de bruit | tirages plantés | SEEL, tous les tirages | SEEL, tirages qui aboutissent | RMSE des plantés (min à moyenne) | RMSE max des tirages qui aboutissent |
|---|---|---|---|---|---|
| 0,5× (0,025) | 5 sur 300 (1,7 %) | 0,655 | 0,633 | 0,213 à 0,225 (moyenne) | 0,116 |
| 1× (la machine) (0,05) | 5 sur 300 (1,7 %) | 0,660 | 0,636 | 0,227 à 0,237 (moyenne) | 0,125 |
| 2× (0,1) | 25 sur 300 (8,3 %) | 0,960 | 0,644 | 0,200 à 0,230 (moyenne) | 0,133 |

SEEL = 2√(centile 95 de la RMSE des tirages), comme partout. **Les dépôts qui aboutissent ont un SEEL de
0,633 à 0,644 nm aux trois niveaux.**

## Lecture

- **Les tirages plantés se distinguent nettement des autres** : leur RMSE est de 0,200 ou plus, celle des tirages qui
aboutissent ne dépasse pas 0,133 ; les deux populations ne se recouvrent à aucun niveau. Quand plus de 5 % des tirages
plantent, le centile 95 de « tous les tirages » est donc celui d'un tirage planté : au bruit 2× (25 plantés sur 300)
il vaut 0,960 nm, contre 0,644 nm pour les tirages qui aboutissent.
- **Le 0,673 affiché n'est aucun de ces nombres.** Le maximum sur les trois niveaux du centile de « tous les tirages »
est 0,960 nm. D'après le code (`certus_strat_consensus.py`), le score d'un plan classé dans les `consensus_top_k` est
la moyenne plus `consensus_std_weight` (0,35) écart-type de ses scores sur les graines du consensus (101, 102, 103),
**en ne gardant que les scores finis** : un plan rejeté par la porte de plantage (5 %) à une graine n'y compte pas. Je
n'ai pas mesuré ses composantes (combien de graines, quelles valeurs).
- **Le SEEL de l'ordre de 1,0 nm que portent presque tous les plans de cette graine (médiane 1,000 nm) mesure la part
de tirages plantés, non la qualité spectrale** : à plantage de 17 à 18 %, les autres plans de repli ont un SEEL de
0,97 à 0,98 nm sur tous les tirages et de 0,60 à 0,64 nm sur ceux qui aboutissent (tableau ci-dessous).
- **Ce plan n'est pas déposable pour le critère de 👤** (plantage ≤ 5 % au pire des trois niveaux : 8,3 % au 2×). Au
bruit de la machine (1×) il plante dans 1,7 % des tirages.

Les trois plans suivants dans l'ordre du plantage, mêmes niveaux de bruit (0,5× ; 1× ; 2×) :

| plan | plantage (pire niveau) | SEEL, tous les tirages | SEEL, tirages qui aboutissent |
|---|---|---|---|
| `990500009` | 17,7 % | 0,969 ; 0,977 ; 0,981 | 0,611 ; 0,617 ; 0,632 |
| `900600169` | 18,0 % | 0,975 ; 0,981 ; 0,982 | 0,604 ; 0,616 ; 0,635 |
| `990500007` | 18,0 % | 0,982 ; 0,971 ; 0,973 | 0,603 ; 0,617 ; 0,636 |

## Comment c'est mesuré, et ce que vaut la mesure

- **Rejeu** de `scripts/probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 101` dans un clone au commit `782972bf`, dont la sonde ne diffère de
  celle de l'arbre que par le champ `rmse_par_bruit` : le centile 95 de la RMSE sur tous les tirages et sur les tirages qui aboutissent, et les effectifs
  (un tirage est planté quand une de ses épaisseurs dépasse la valeur sentinelle `CRASH_SENTINEL_MIN` du noyau). Artefact : `reports/blocs_vs_plantage_r75x0.5_deep_s101_par_bruit.json`.
- **Le rejeu retrouve le plan** : même identifiant, mêmes blocs, mêmes λ, même couche Rate, mêmes taux de plantage par niveau
  (0,025 : 1,7 %, 0,05 : 1,7 %, 0,1 : 8,3 %) ; son `score` diffère de
  7,7·10⁻¹³ (cache Numba froid du clone). **Il ne retrouve pas la population au bit** : 2 897 stratégies de part et d'autre, 2 893 identifiants communs,
  44 lignes communes ont un taux de plantage différent.
- **Un premier rejeu a été perdu** : le clone n'avait pas `reports/serie_echelle_r75/cfg_x0.5.json`, `load_configuration` a rendu `False`, la sonde n'a pas lu ce retour
  et a calculé quatre heures sur la pile par défaut de 46 couches, avec le verdict `OK` (D104, ETAT section 4). Son artefact n'est pas conservé.

## Ce que ce rapport ne dit pas

- Le SEEL niveau par niveau des graines 42 et 202, ni d'un autre composant.
- La composition du score affiché (graines finies du consensus).
- Ce que donnerait ce composant avec plusieurs verres témoins.
