# Remesure après la correction de D100 — 2026-10-11

Code `782972bf` : D100 corrigé (`2cba90f4`), les interrupteurs de STRAT reçoivent de nouveau le fichier chargé —
Rate, biais de fente, recherche de fente, options de symétrie. Une mesure à la fois, caches Numba de l'arbre,
`CERTUS_BENCH_TIMEOUT_S=38400`, aucune surcharge ; lanceur, durées et artefacts dans
`reports/remesure_D100_2026-10-11/resume.txt`. Chaque journal porte des lignes `[RATE]` (10 à 20) et
`[SLIT] slit bias active` (28 à 58) : les interrupteurs atteignent le calcul. Aucun `WAIT_TIMEOUT`.

🔴 **D103 trouvé pendant cette remesure** (`reports/STRAT_D103_identifiants_en_double_2026-10-11.md`) : en `deep`,
deux groupements minés peuvent porter le même identifiant, et le consensus donne alors à l'un le score de l'autre.
Le juge de paix et le 99c tournent en `premium` et le mineur de `r75x0.5` ne rend qu'une ou deux semences : D103 ne
les touche pas. Les sept graines de `r75x2` tournent en `deep` : leurs chiffres ci-dessous sont sous D103.

## Juge de paix (`scripts\bench_examples.py strat`, `premium`)

| modèle | `RESULT` | SEEL | gagnante | stratégies |
|---|---|---|---|---|
| sous D100 (`b60d80e2`, 2026-10-04) | 0,007644641198073172 | 0,175 nm | 4 blocs (λ 544, 471, 467, 474 nm) | 370, aucune éliminée |
| D100 corrigé (`782972bf`) | 0,007917103726810235 | **0,178 nm** | 5 blocs (λ 544, 471, 466, 467, 462 nm), ELITE | 823, dont 154 éliminées |

Plantage 0 % pour les dix premières. Avec les interrupteurs rétablis (Rate, biais de fente, recherche de fente,
options de symétrie), le SEEL monte de 1,8 % ; la mesure ne dit pas lequel y contribue.

## Passe-bande 99 couches en une campagne (`99c premium`, graine 42)

| modèle | déposables | plantage minimal (bruits 0,025 / 0,05 / 0,1) |
|---|---|---|
| sous D100 (`c3ff6477`) | 0 sur 205 | 34,0 % (10 / 15,3 / 34 %) |
| D100 corrigé | **0 sur 2 139**, dont 1 934 variantes Rate | 82,7 % (82,7 / 77,3 / 73,3 %) |

Toujours non fabricable en une campagne ; la meilleure stratégie reste la couche à couche.

## `r75x0.5` avec un seul verre témoin (`deep`, fente 2 nm)

| graine | août (`5377307`, `ca64ac1`) | D100 corrigé |
|---|---|---|
| 42 | plantage minimal 68,7 % (recherche élargie) | **0 déposable sur 2 895**, plantage minimal 69,0 % |
| 101 | 70,0 % | **0 sur 2 897**, plantage minimal 8,3 % |
| 202 | 67,0 % | **0 sur 2 895**, plantage minimal 62,3 % |

Environ 2 554 variantes Rate par graine. La meilleure de la graine 101 (`990500008`, `RATE_L31` d'une fusion
`SMART_MERGE_MIXED`, 5 blocs) plante dans 1,7 % des tirages aux deux premiers niveaux de bruit et 8,3 % au troisième :
le critère (plantage ≤ 5 %) l'écarte. **Non fabricable avec un seul verre témoin à ces trois graines** ; la graine 101
n'en est plus loin, quand août plafonnait à 67 %.

## `r75x2` sans rampes, protocole d'août, sept graines (`deep`) — sous D103

| graine | août | 2026-10-11 matin, sous D100 | D100 corrigé |
|---|---|---|---|
| 42 | 0 sur 1 617 | 674 sur 768, SEEL 0,5566 nm | **retenu par le garde-fou** (identifiant 15239 en double) |
| 77 | 547 sur 2 231, 0,5692 nm | 814 sur 910, 0,5355 nm | **517 sur 5 036, 0,5404 nm** (8 blocs) |
| 101 | 0 sur 1 630 | 1 124 sur 1 216, 0,5603 nm | **727 sur 5 514, 0,5634 nm** (11 blocs) |
| 202 | 0 sur 1 646 | 661 sur 754, 0,5547 nm | **403 sur 5 192, 0,5837 nm** (6 blocs) |
| 303 | 0 sur 1 680 | 671 sur 763, 0,5622 nm | **0 sur 4 144**, plantage 100 % à tout nombre de blocs |
| 404 | 372 sur 2 016, 0,5599 nm | 1 041 sur 1 107, 0,5426 nm | **retenu par le garde-fou** (15233) |
| 505 | 311 sur 1 995, 0,6112 nm | 947 sur 1 038, 0,5629 nm | **retenu par le garde-fou** (12228) |

« Déposables » : plantage ≤ 5 % ; SEEL du meilleur d'entre eux. Aucun plan déposable du soir ne porte de couche Rate,
sur 3 700 à 4 300 variantes Rate par graine. Trois graines sur sept s'arrêtent après 29 à 37 min sur
`Missing or duplicate strategy_id ... table and export withheld` (`ECHEC_RESULT_NONE`) ; les quatre autres ont
tourné avec des scores de consensus mélangés entre homonymes. **Ces chiffres ne concluent pas** : la campagne est à
refaire avec D103 corrigé.

## Ce qui en sort

- Le juge de paix a un repère au modèle voulu : **0,178 nm** (`premium`, intouché par D103).
- Le 99c reste non fabricable en une campagne, et `r75x0.5` avec un seul verre témoin, à ces graines.
- `r75x2` : pas de chiffre tant que D103 n'est pas corrigé. La graine 303, qui trouvait sous D100, ne trouve plus
  rien avec le biais de fente et le Rate ; à remesurer avant toute lecture.
