# r75x0.5 avec un seul verre témoin : le secours Rate rend des plans déposables (2026-10-12)

Question de 👤 (2026-10-12) : avec du Rate, on doit trouver des solutions déposables avec un seul témoin ; le Rate est du temps sur
une vitesse estimée (pas un quartz) ; il doit être favorisé sur les couches difficiles à contrôler optiquement, intégré à chaque
design quel que soit le filtre, et renforcé quand peu de plans se terminent ; `r75x0.5` est le test, et il doit finir par trouver
des stratégies, « quitte à tout finir au Rate ».

## Réponse

**Oui : aux trois graines, tous les plans de la liste finale sont déposables, et aucun n'est un plan optique pur.**

| version | graine | stratégies | déposables (plantage < 5 % au pire des trois bruits) | plantage de la liste, minimal à maximal | meilleur SEEL |
|---|---|---|---|---|---|
| avant (`782972bf`, 2026-10-11) | 42 | 2 895 | 0 | 69,0 % au moins | aucun déposable |
| avant | 101 | 2 897 | 0 | 8,3 % au moins | aucun déposable (le repli affiche 0,673 nm) |
| avant | 202 | 2 895 | 0 | 62,3 % au moins | aucun déposable |
| **après** (`40642146`, 2026-10-12) | 42 | 3 383 | **3 383** | 0 % à 2,67 % | **0,5031 nm** |
| **après** | 101 | 3 701 | **3 701** | 0 % à 4,67 % | **0,4981 nm** |
| **après** | 202 | 3 279 | **3 279** | 0 % à 2,00 % | **0,5000 nm** |

Le meilleur plan de chaque graine plante dans 0 % des tirages aux trois niveaux de bruit (0,5×, 1×, 2×), a 12 blocs, et pose le
Rate de la couche 18 à la 75 (indices 17 à 74 : 58 couches au temps, les 17 premières sous contrôle optique). Les trois sont presque
le même plan : λ de contrôle 630 (629), 674 à 676, 675, 695, 639, 656, 744, 740, 733, 701 (702), 525 et 524 nm, mêmes bornes de blocs à une
couche près. Les vingt meilleurs plans de chaque graine, soit 60 plans, sont tous des enfants d'ELITE à 12 blocs qui posent le Rate
exactement sur les indices 17 à 74 ; l'écart entre les trois meilleurs SEEL est de 1 %.

Aucun plan de la liste finale n'est optique pur. La première couche Rate est l'indice 2 pour les plus précoces (couche 3 du tableau),
29 au plus tard, et 8 ou 9 pour la médiane ; le nombre de couches au Rate va de 40 à 73 sur 75 (médiane 64 ou 65) ; la queue qui va
jusqu'à la dernière couche est la forme de 2 903, 3 294 et 2 819 plans (graines 42, 101, 202). C'est le « tout finir au Rate » de 👤 :
l'optique tient le début, le temps tient la fin.

## Pourquoi rien ne se terminait

Mesures du 2026-10-11 (`782972bf`, `deep`, fente 2 nm, un seul verre témoin) : sur les trois graines, aucun plan ne se terminait ;
la cause de plantage dominante est « niveau d'arrêt hors d'atteinte » partout. La limite était celle des variantes Rate de la
recherche, pas du composant :

1. **Une seule couche Rate par variante** (`RATE_Lxx`, au moindre coût), alors que les couches qui cèdent se déplacent quand les
   précédentes passent en Rate. Sur la graine 101 de `782972bf`, la couche critique des 2 897 plans est 28 (638 plans), 46 (638), 22
   (457), 25 (291), 62 (230), 51 (195) ; les couches 22, 25 et 28 couvrent 47,8 % des plans, 46 et 51 28,8 %.
2. **`rate_by_swing` éteint** : la sonde le posait Faux et l'application le lisait Faux (depuis le 2026-08-22), alors que le noyau et
   le registre des leviers disaient Vrai (`12b5c2b7`, `9c4d07cf`).
3. **ELITE perdait le Rate** : un enfant d'ELITE ou de la recherche locale ne gardait ni les couches Rate, ni la fente, ni les
   échanges de verre de son parent ; l'enfant d'un plan Rate redevenait un plan optique pur, qui plantait là où le parent passait
   (`4a4e1f0d`).
4. **Les enfants d'ELITE n'avaient pas le biais de fente** que portent tous les autres plans (D106, `6fcdd56a`) : sur la trace
   des appels de la tâche de robustesse pour `35c` en `fast`, 2 926 évaluations d'ELITE sur 3 013 sans profil de fente.

## Ce qui a été essayé

| essai | protocole | résultat |
|---|---|---|
| **E1**, queues Rate de la couche 16, 20, 24 ou 28 à la fin | graine 101, `21d1b1c3`, `rate_tail_sweep=[16,20,24,28]`, `rate_by_swing` éteint | 522 plans sur 547 se terminent ; meilleur SEEL 0,555 nm (coupure 16) ; coupure 20 : 0,606 ; 24 : 0,680 ; 28 : 0,601 |
| **E1b**, queues de la couche 2 à 14 | idem, `rate_tail_sweep=[2,4,6,8,10,12,14]` | 2 272 plans sur 2 272 ; meilleur SEEL 0,563 nm (coupure 14) ; de 0,767 nm (tout au Rate sauf les couches 0 et 1) à 0,563 nm |
| **E2**, ensembles fixes des couches critiques | graine 101, `03990e9a`, `rate_layer_sets` = {22, 25, 28}, puis +46, +51, +62, +69 et 72 (indices), `rate_by_swing` et secours éteints | 0 plan déposable sur 4 614 ; plantage minimal 47,0 % toutes familles confondues, 52,0 % pour les ensembles fixes (`RATE_SET22_25_28_46_51_62`) |
| **acceptation**, le secours Rate de la recherche | trois graines, `40642146`, production | tableau ci-dessus |

E1 et E1b disent que le Rate suffit : une queue pose le composant en déposable. E2 dit que les couches critiques d'un plan optique pur
ne désignent pas où poser le Rate : une fois les premières au Rate, ce sont d'autres couches qui cèdent. Le secours lit donc, pour
chaque plan qui plante, **où ses tirages plantent d'abord** et pose le Rate de là jusqu'à la fin (`_rescue_with_rate`).

Dans ce rapport, les indices de couche (« coupure », « indice ») commencent à 0 ; le tableau de l'interface numérote à partir de 1
(« Rate L18-L75 » = les indices 17 à 74).

## Le secours Rate

Pour les plans d'une passe de Phase B qui ne se terminent pas : le secours prend, au niveau de bruit qui plante le plus, la première
couche où la part cumulée des tirages déjà plantés dépasse 2 % (`_first_crash_layer`) : c'est la couche où le contrôle optique
cède. Il choisit des coupures réparties de cette couche jusqu'à la couche 2 (les couches 0 et 1 n'ont jamais de Rate : il n'y a pas
encore de vitesse à estimer ; la coupure 2 est « tout au Rate », celle qui ne peut pas planter) et pose le Rate de chaque coupure à
la fin de l'empilement. Les enfants subissent le même Monte-Carlo (mêmes tirages : C2) et entrent dans le même ensemble avant la
porte de plantage et l'affinage d'ELITE. Le budget suit la rareté : 30 plans et 8 coupures au plus quand aucun plan ne se termine,
3 et 2 à partir de `rate_rescue_few` (10) plans déposables, linéaire entre les deux.

Chaque graine compte **16 passes** de Phase B (48 en tout) ; dans toutes, **le nombre de plans optiques purs déposables était 0** avant
le secours. Il a posé 3 567, 3 467 et 3 562 queues (graines 42, 101, 202), dont **2 350, 2 680 et 2 368 sont déposables** (65,9 %,
77,3 % et 66,5 %) ; par passe, de 52 à 204 queues déposables pour la graine 42, à 229 pour la 101 et à 230 pour la 202. Les plans de la
liste finale viennent des queues du secours (2 350, 2 680 et 2 368) et d'ELITE (1 033, 1 021 et 911) ; les vingt meilleurs de chaque
graine sont d'ELITE.

## Ce que le modèle de Rate de STRAT suppose

Le modèle (`certus/physics/certus_strat_growth.py`, « RATE MODE ») estime la vitesse comme la moyenne des rapports d'épaisseur
nominale sur réelle des couches précédentes du même matériau déposées **sous contrôle optique** ; une couche Rate est posée pour
`round(d_nominal / (A · 0,125 nm))` tours. L'estimation est **figée à l'entrée de la queue** : toutes les couches de la queue
héritent de la même erreur relative, corrélée, qui ne se moyenne jamais. Le modèle ne contient ni dérive de la source pendant le
dépôt, ni bruit propre de la vitesse. Les SEEL des plans à longue queue Rate sont ceux de ce modèle : **la stabilité de la vitesse
pendant un run n'est pas mesurée**, et c'est ce qui les rendrait faux si la source dérivait.

## Ce que ce rapport ne dit pas

- Une exécution par graine ; l'écart de 1 % entre les trois meilleurs SEEL est inférieur à la dispersion mesurée sur `r75x2`
  (σ ≈ 1,8 %, ETAT section 2), qui n'est pas mesurée sur ce composant.
- Le meilleur de 3 279 à 3 701 plans : le SEEL du gagnant est le minimum d'une population, donc optimiste de l'effet de sélection ;
  le score de consensus (moyenne plus 0,35 écart-type sur les graines du consensus, ETAT D7) en corrige une partie pour les meilleurs.
  Je n'ai pas rejoué le gagnant sur des tirages indépendants.
- **`avant` et `après` diffèrent aussi par le modèle d'arrêt** : D96 à D98 sont par défaut depuis `8d9ced13` (l'attente sans fin de D98
  est plus sévère, `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`). Je n'ai pas mesuré `r75x0.5` avec le secours et l'ancien
  modèle d'arrêt.
- **L'apport d'ELITE hérité et celui du secours ne sont pas séparés** : E1 (0,555 nm) a tourné avant l'héritage d'ELITE (`4a4e1f0d`),
  l'acceptation (0,50 nm) après ; je n'ai pas mesuré l'héritage sans le secours.
- Le cas à plusieurs verres témoins (`witness_reset_layers`) n'est pas mesuré à `r75x0.5`.
- L'opérateur qui pose le Rate sur les couches où les tirages plantent d'abord, quelques couches de plus à chaque tour
  (`rate_rescue_hard`, `4acbda26`), existe et est **inactif par défaut** : je ne l'ai pas mesuré en production.
- Les durées (52, 36 et 55 minutes pour les graines 101, 42 et 202) viennent d'une machine qui portait d'autres mesures : elles ne
  comparent rien.

## Reproduction

```
python scripts/probe_blocs_vs_plantage.py r75x0.5 deep 0 0 2 0 <graine> 0
```
dans un arbre propre à `40642146` (`git worktree add --detach`), `CERTUS_BENCH_TIMEOUT_S=21600`, graines 101, 42, 202. Artefacts dans
`reports/STRAT_secours_rate_2026-10-12/` : `blocs_vs_plantage_r75x0.5_deep_s{042,101,202}_secours.json`,
`..._s101_queues_16-28.json` (E1), `..._s101_queues_2-14.json` (E1b),
`..._s101_ensembles_fixes.json` (E2), et `passes_du_secours_s{042,101,202}.txt` (les lignes `[RATE-RESCUE]` des journaux : une par
passe). Chaque artefact porte le commit et l'état de l'arbre qui l'a produit (`provenance`, `git_dirty` faux). Les recherches du juge
de paix sont dans `reports/STRAT_modele_d_arret_2026-10-12/` (rapport `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`).
