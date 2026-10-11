# Audit du déclenchement d'arrêt de STRAT face à un OMS réel — 2026-10-10

Question de 👤 : *« identifier très sérieusement si l'arrêt trigger est intelligemment programmé par rapport à la
réalité d'un OMS »*. Ce rapport répond par la mesure. Chaque chiffre vient d'une commande donnée plus bas. Ce qui
n'a pas été mesuré est dit tel.

**Conditions.** Linux (conteneur, 4 cœurs), Python 3.14.6, NumPy 2.5.3, Numba 0.68.0 ; le banc de référence est sous
Windows et Python 3.14.8 (ETAT, section 0), les derniers chiffres d'un `RESULT` ne se comparent donc pas d'une machine à
l'autre. Code : branche `claude/ecstatic-newton-3grmls`, aux commits cités. Plans : la population du juge de paix
(`reports/STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json`, 370 plans) et celle de `r75x2`
(`reports/STRAT_bench_r75x2_deep_hysteresis_noise_level_306559d3_2026-10-05.json`, 783 plans). Bruit de lecture
A = 5e-4 en T (±0,05 point), hystérésis du fichier 1,66 A, niveaux de bruit 0,5×, 1× et 2×.

## Verdict

1. **La logique d'arrêt du noyau est celle d'un OMS** : niveau figé sur le nominal et reporté sur le réel
   (auto-compensation), fraction POEM figée sur le nominal et appliquée aux extrema observés, bruit tiré lecture par
   lecture en nombres aléatoires communs, détection à hystérésis par la même règle sur le réel et le nominal, plantage
   quand le niveau n'est pas atteint ou que le comptage diverge. Rien de cela n'est naïf.
2. **Son chemin « grille machine » était faux**, et c'est le chemin qui porte le modèle de lecture figé de 👤
   (ETAT, section 3 : lecture tous les 0,125 nm, moyenne sur 8 lectures). Cinq défauts, tous corrigés cette nuit :
   - le substrat nu compté deux fois à la couche 0 (D93) ;
   - un signal interpolé et une fenêtre au départ extrapolé : 6,1 A d'écart au T exact en médiane, jusqu'à 36 A
     (D94, D95) ;
   - un bruit compté deux fois ;
   - une fenêtre d'atteignabilité ouverte dans l'historique ;
   - un départ de fenêtre compté ou non selon le bruit de sa première lecture (le plan en décide maintenant).

   Corrigé, ce chemin reproduit une machine rejouée lecture par lecture et indépendante du noyau : P95 à 6 % près au
   plus, aucun plantage d'un côté ni de l'autre sur les quatre plans comparés (§2).
3. **Le chemin livré (grille grossière, lectures brutes) reste un modèle approché.** Ses notes s'écartent de celles
   du modèle figé d'environ 10 %, dans un sens qui dépend du composant : 10 % trop haut sur le juge de paix, 11 %
   trop bas sur `r75x2`. Mais il choisit bien : sur les 370 plans du juge, il désigne **le même meilleur plan** que le
   modèle figé (classements concordants à 0,92) ; sur la tête de `r75x2`, son meilleur plan est à 3,9 % de celui du
   modèle figé, dans le bruit Monte-Carlo (§6). Quatre écarts restent ouverts, mesurés en
   §4 : les ancres lues sur l'échantillonnage grossier (D96), l'inversion parabolique de l'arrêt (D97, désormais en
   option), l'armement non causal (D98) et, au modèle figé, la lecture d'arrêt non lissée (D99). Aucun ne déplace la
   tête de la population hors du bruit Monte-Carlo. D96 existe aussi en option depuis le 2026-10-11 : avec les deux
   options, l'arrêt du noyau sans bruit tombe sur l'arrêt POEM exact, et le modèle livré classe le juge plus près du
   modèle figé (§4).

## 1. Les outils

| outil | ce qu'il fait |
|---|---|
| `scripts/probe_oms_sequentiel.py` | rejoue un dépôt **lecture par lecture** (0,125 nm), chaque lecture avec son tirage borné (σ = A/3), un détecteur à hystérésis **causal**, un lissage optionnel, et un arrêt qui n'est possible qu'une fois **compté** le nombre d'extrema que le plan attend (armement) ; à côté, le noyau de production sur le même plan, avec la même physique coupée (fente, courbure, couloir) ; les deux notés par le noyau de notation de production. T(d) vient de l'oracle indépendant `tests/oracle/tmm_reference.py` |
| `scripts/probe_armement.py` | pour chaque couche de chaque plan, l'écart en transmission entre le niveau d'arrêt nominal et le dernier extremum avant lui, comparé au seuil d'hystérésis aux trois niveaux de bruit |
| `scripts/probe_modele_lecture.py` | renote une population avec les noyaux de production sous le modèle de lecture livré et sous le modèle figé, même physique des deux côtés ; options : arrêt exact (D97), ancres au sommet (D96), arrêt lissé (D99), seuil de détection balayé |
| `scripts/probe_arret_sans_bruit.py` | sans aucun bruit, sous des erreurs amont tirées, l'arrêt de chaque couche par le noyau contre l'arrêt POEM exact du contrôleur de la machine séquentielle, rejoué sur l'oracle tous les 0,05 nm (croisement résolu par bissection) ; options du noyau : arrêt exact (D97), ancres au sommet (D96) |

## 2. Le chemin « grille machine » (rang 4 d'ETAT) : cinq défauts, corrigés

**D93, double comptage du départ** (`cf555a5b`, complété par `1812329d`). Le substrat nu est un point tournant
(dT/dd = 0 en d = 0). À 0,125 nm, les premières lectures de la couche 0 restent dans le bruit du départ ; le
maximum courant du détecteur glissait sur l'une d'elles, déclarée ensuite en plus du départ. Plantage par comptage
à la couche 0, gagnante du juge de paix, fenêtre de lissage 8, 300 tirages : **7,7 %, 21,3 % et 36,0 %** à 0,5×, 1×
et 2×. Après correction (code de `1812329d`), 1 000 tirages par niveau à la couche 0 : 0, 0 et 0 avec le lissage 8
et le seuil 1,00 A.

**D94 et D95, signal interpolé** (`b576f915`). Le signal aux lectures était le balayage grossier (16 points par
couche rejouée) interpolé linéairement. Sur la gagnante du juge, en nominal, il s'écartait du T exact de **6,1 A en
médiane par couche, jusqu'à 33 A**. Le départ de la fenêtre était la droite par ses deux premiers points grossiers :
**jusqu'à 36 A** quand la fenêtre part d'un point tournant. Le bruit modélisé est de ±1 A. Les points grossiers
portaient en plus leur propre tirage, interpolé : chaque lecture avait deux bruits, dont un corrélé d'une lecture
à l'autre. Enfin, le test d'atteignabilité gardait la longueur grossière de l'historique comme début de la couche
en cours : sa fenêtre s'ouvrait dans l'historique. Le signal est maintenant **exact à chaque lecture**. La forme
fermée de `layer_scan_coeffs` coûte deux fonctions trigonométriques par lecture, moins que le tirage du bruit.

**C1 tenu.** Un corpus de 1 500 appels sur grille grossière, toutes couches dont la 0, et de 40 propagations d'état :
**1 540 tableaux identiques au bit** à HEAD, à froid contre froid. Le corpus STRAT de `scripts/c1_diff.py`, rejoué cas
par cas : 183 cas changent, **tous les 183 sur la grille machine**, aucun des 180 sur la grille grossière.

**Le départ de la fenêtre** (`c1d0c239`, puis `f7248c81`). Une fenêtre de lecture (début de bloc, ou début de
l'historique rejoué) part souvent près d'un extremum. Des plans dont le bloc à 467 nm part 0,86 seuil sous un maximum
situé 2 nm plus loin : la première lecture, poussée vers le bas par le bruit, faisait du départ un minimum, compté sur
le signal réel et pas sur le nominal. Plantage par comptage dans 156 tirages sur 300 à la couche 36 à 2× ; 21 plans
éliminés. `c1d0c239` donne au détecteur, à chaque départ, la direction du plan, et ne compte plus jamais le départ.

Mais le départ servait aussi de **première ancre** à POEM, légitimement, quand le signal s'en éloigne nettement avant
son premier extremum. Sans elle, une fenêtre qui ne contient qu'un extremum avant l'arrêt perd POEM et retombe sur le
niveau absolu, que la courbure photométrique et le couloir d'indice rendent inatteignable. Sur les 101 premiers plans,
27 plantaient davantage après `c1d0c239`, tous au test d'atteignabilité. `f7248c81` laisse le plan décider : le départ
est une ancre si le signal nominal, lu sans la direction, le compte, et le signal réel le compte alors aussi.

Plantage au modèle figé, 300 tirages, à 0,5× / 1× / 2× (%) :

| plan (rang) | avant `c1d0c239` | `c1d0c239` | `f7248c81` |
|---|---|---|---|
| 11 | 0 / 12,7 / 58,0 | 0 / 0 / 2,3 | 0 / 0 / 0,3 |
| 28 | 0 / 0,3 / 0,7 | 2,0 / 8,0 / 18,7 | 0 / 0 / 0 |
| 94 | 0 / 7,0 / 60,7 | 13,3 / 23,7 / 39,0 | 0 / 0 / 1,7 |
| 96 | 0 / 0,3 / 2,7 | 34,3 / 37,0 / 48,3 | 0 / 0 / 2,3 |

Sur les 43 plans que l'un ou l'autre commit a déplacés, aucun ne plante plus qu'avant `c1d0c239`, à aucun niveau de
bruit, et les 16 plans réparés par `c1d0c239` le restent. Chemin par défaut inchangé : 11 cas sur 420 du corpus de
`c1_diff.py` changent, tous sur la grille machine ; 1 540 tableaux de la grille grossière identiques au bit.

**Le chemin corrigé reproduit la machine indépendante.** Les deux sous le modèle figé (fenêtre 8, seuil 1,00 A), avec
la même règle de contrôleur au départ des fenêtres (`876af484`), même physique isolée, 300 tirages ; RMSE spectrale
contre le spectre nominal (code de `1171c6af`) :

| plan (rang) | bruit | noyau corrigé : plantage, P95, moyenne | machine séquentielle : plantage, P95, moyenne |
|---|---|---|---|
| 0 | 1× | 0 %, 0,001890, 0,001094 | 0 %, 0,001782, 0,001069 |
| 50 | 1× | 0 %, 0,002897, 0,001524 | 0 %, 0,002928, 0,001516 |
| 200 | 1× | 0 %, 0,002901, 0,001679 | 0 %, 0,002897, 0,001644 |
| 350 | 1× | 0 %, 0,003760, 0,002058 | 0 %, 0,003753, 0,002044 |
| 0 | 2× | 0 %, 0,003782, 0,002233 | 0 %, 0,003797, 0,002217 |
| 50 | 2× | 0 %, 0,005820, 0,003096 | 0 %, 0,005692, 0,003120 |
| 200 | 2× | 0 %, 0,005899, 0,003423 | 0 %, 0,005847, 0,003352 |
| 350 | 2× | 0 %, 0,007888, 0,004299 | 0 %, 0,007519, 0,004009 |

Aucun plantage d'un côté ni de l'autre ; le P95 du noyau s'écarte de celui de la machine de 6 % au plus (rang 0 à 1×,
rang 350 à 2×). À 2×, la machine arme trop tard aux couches 45 et 47 (2 à 21 couches-tirages par plan) et fait 21 à 57
arrêts à plus de 2 nm du nominal (sur 300 × 48) : c'est l'armement (§4, D98), que le noyau ne modélise pas.

## 3. Le chemin livré (grille grossière, lectures brutes, 1,66 A) face au modèle figé

Même comparaison, mais le noyau tel qu'il est configuré. Douze plans du juge de paix (rangs 0 à 369), 300 tirages,
physique isolée, machine de `876af484` :

| bruit | P95 machine / P95 noyau livré, sur les 12 plans | classement des 12 plans (Spearman) | arrêts à plus de 2 nm du nominal, machine |
|---|---|---|---|
| 1× | de 0,73 à 0,97 (médiane 0,83) | 0,84 | 0 à 1 par plan |
| 2× | de 0,76 à 0,94 (médiane 0,81) | 0,90 | 5 à 66 par plan (sur 300 × 48) |

Aucun plantage côté machine ; côté noyau livré, 0,3 % au plus (à 2×).

Sur ces 12 plans du juge, le noyau livré est **pessimiste** (sur `r75x2`, la §6 mesure le sens inverse). Il lit ses
ancres sur des lectures brutes, alors que la machine les lit lissées ; la cause de l'écart n'est pas isolée. Il classe
pourtant les plans à peu près dans le même ordre. Les arrêts décalés de la machine à 2× tombent sur des
couches où la fraction POEM est proche de 0, donc près de l'extremum suivant. Lu à 0,125 nm, un extremum est biaisé
**vers l'extérieur** par le bruit (le maximum de lectures bruitées). Lu sur l'échantillonnage grossier, il est
biaisé **vers l'intérieur** (l'échantillon tombe à côté du sommet). Le noyau livré ne voit donc pas ces arrêts.

La renotation de toute la population sous les deux modèles, physique complète hors fente, est en §6.

## 4. Les écarts encore ouverts, mesurés

**D96, ancres lues sur l'échantillonnage grossier.** Sans aucun bruit, avec des erreurs amont tirées à σ = 0,3 nm
(3 réalisations × 48 couches, gagnante du juge), l'arrêt du noyau s'écarte de l'arrêt POEM exact (oracle au pas de
0,05 nm, croisement résolu par bissection) de **0,055 nm RMS, P95 0,14 nm**, jusqu'à 0,17 nm RMS sur une couche.

L'option `exact_anchors` (2026-10-11, `b0d0264c` et `eae41d81`, inactive par défaut, chemin par défaut identique au bit)
porte chaque ancre au sommet de l'extremum de sa couche, en forme fermée. L'ancre nominale prend sa valeur exacte.
L'ancre réelle garde le bruit de lecture de son échantillon, prend T et le biais de fente à la profondeur du sommet, et
passe exactement par la dérive photométrique ; elle remplace son échantillon dans le signal, pour que le test
d'atteignabilité voie le sommet d'où le niveau est tiré. Mêmes conditions sans bruit
(`scripts/probe_arret_sans_bruit.py`) :

| arrêt du noyau − arrêt POEM exact | RMS | P95 | max |
|---|---|---|---|
| par défaut | 0,0545 nm | 0,142 nm | 0,226 nm |
| arrêt exact seul (D97) | 0,0484 nm | 0,117 nm | 0,224 nm |
| ancres au sommet seules (D96) | 0,0212 nm | 0,0248 nm | 0,189 nm |
| les deux | 8,0e-6 nm | 1,7e-5 nm | 3,7e-5 nm |

Avec les deux options, le noyau sans bruit rend l'arrêt de la machine. Renotation des 370 plans du juge, mêmes
conditions que la §6 (`scripts/probe_modele_lecture.py`, 300 tirages, mêmes tirages, fente absente) :

| modèle | déposables | meilleur plan | note / modèle livré, médiane (P5 – P95) | Spearman avec le livré | Spearman avec le figé |
|---|---|---|---|---|---|
| livré | 370 | 11 | 1 | 1 | 0,920 |
| livré, ancres au sommet | 370 | 11 | 1,003 (0,952 – 1,045) | 0,967 | 0,943 |
| livré, ancres au sommet et arrêt exact | 370 | 11 | 0,991 (0,948 – 1,035) | 0,969 | 0,944 |

Les ancres au sommet ne changent ni le meilleur plan ni le niveau moyen des notes ; elles rapprochent le classement du
modèle livré de celui du modèle figé. Le plantage moyen à 2× ne bouge pas (0,106 % contre 0,105 %). Une première version
jugeait le niveau, pris au sommet, contre la bande lue sur les échantillons, plus bas : les plans 185 et 283 y passaient
de 1,7 et 1,3 % de plantage à 2× à 7,0 et 5,3 %, tous à la couche 47, dont l'arrêt tombe 2,75 nm après un maximum,
le niveau 1,5 A sous lui. Activer l'option par défaut est une décision de 👤.

**D97, inversion parabolique.** Les niveaux exacts donnés, la parabole à ±2,5 nm du nominal s'écarte de l'arrêt exact
de **0,021 nm RMS sous POEM**, avec 0,13 nm sur la couche 40. Au niveau absolu (POEM coupé), l'écart monte à
**0,19 nm RMS, jusqu'à 1,53 nm** : l'arrêt s'y éloigne de plusieurs nanomètres du nominal et la parabole extrapole.
Les ancres expliquent donc l'essentiel des 0,055 nm de D96 (0,048 nm RMS quand la parabole est seule corrigée). Pour
comparaison, le SEEL du juge de paix vaut 0,17 nm.

**D98, armement.** Le noyau compte un extremum à sa **position** ; une machine ne le connaît qu'une fois le signal
revenu du seuil d'hystérésis. Un niveau plus proche de l'extremum que ce seuil est donc franchi avant que la machine
ne l'attende. La marge de Phase A (1,66 A) ne regarde que la couche en cours, pas les extrema des couches précédentes
du bloc. `scripts/probe_armement.py`, sur les plans nominaux :

| population | 0,5× | 1× | 2× |
|---|---|---|---|
| juge de paix (370) | 0 | 22 plans (couche 47) | 38 plans (couches 36, 41, 42, 47) |
| `r75x2` (783) | 67 plans | 69 plans | 222 plans |

- **Juge de paix :** tous les plans concernés sont jugés déposables par le noyau (plantage ≤ 1,33 %) ; le premier
  est au rang 23.
- **`r75x2` à 0,5× et 1× :** tous les plans concernés sont déjà écartés par le noyau ; le premier est au rang 692.
- **`r75x2` à 2× :** 140 des 222 sont jugés déposables ; le premier est au rang 255.

Ce que fait l'OMS quand le niveau a déjà été franchi au moment où il arme (arrêt tardif, ou attente sans fin) n'est
pas connu : l'appareil est breveté.

**D99, bruit de la lecture d'arrêt non lissé au modèle figé.** Le noyau porte le bruit de la lecture d'arrêt par un
seul tirage brut par couche (`noise_val_precalc`, σ = A/3 × niveau), lissage ou non ; la machine séquentielle en mode
`anticipated` fait de même. Si la chaîne de détection moyenne sur 8 lectures (postulat 3 d'ETAT, section 3), l'arrêt se
décide sur le signal lissé, au bruit divisé par environ √8. Mesuré sur 17 plans du juge (rangs 0 à 369), modèle figé,
mêmes tirages divisés par √8 : notes plus basses de 8 à 21 % (médiane 11 %), classement des 17 conservé à 0,92
(Spearman), meilleur plan 22 au lieu de 11, à 2,3 % l'un de l'autre. La variante brute redonne exactement les notes de
la §6. C'est une question de modèle : à trancher par 👤.

**Le seuil de détection, balayé** (chantier d'ETAT, section 6). Modèle livré, les 370 plans du juge, seuil de 1,0 à 2,4 A,
proportionnel au niveau de bruit comme dans le code, mêmes tirages :

| seuil | plans dont la note est identique au bit à celle de 1,66 A | plantage moyen à 2× | meilleur plan |
|---|---|---|---|
| 1,00 A | 358 | 0,12 % | 11 |
| 1,33 A | 362 | 0,11 % | 11 |
| 1,66 A | 370 | 0,11 % | 11 |
| 2,00 A | 358 | 0,10 % | 11 |
| 2,40 A | 171 | 0,52 % | 11 |

Sur la grille grossière, le seuil est presque inerte entre 1 et 2 A : ses échantillons sont espacés de plusieurs
nanomètres, le signal y varie bien plus que le bruit, et le seuil ne décide d'un comptage que dans de rares tirages.
Il ne commence à manquer de vrais extrema qu'à 2,4 A. C'est sur la grille machine, à 0,125 nm, qu'il gouverne la
fabrication de faux extrema ; ce balayage-là n'est pas fait.

## 5. Ce qui n'a pas été mesuré

- Le biais de fente est absent des comparaisons, dans les deux bras : ses profils se construisent par stratégie
  dans la chaîne de production.
- La moyenne glissante démarre à froid au début de chaque fenêtre rejouée, dans le noyau comme dans la machine. Un
  OMS réel lit en continu et a déjà son tampon plein. Non modélisé, non mesuré.
- La quantification de l'arrêt (`U(0 ; 0,125 nm)`, D13) et un retard d'obturateur restent hors modèle, sur décision
  de 👤 (le logiciel anticipe le déclenchement). La machine séquentielle a un mode `--stop reading` qui les ferait
  apparaître ; il n'a pas été lancé pour ce rapport.
- La recherche complète de STRAT sous le modèle figé n'a pas été relancée. Elle coûterait environ 15 fois le temps
  de calcul du noyau : 2,1 s contre environ 0,1 s par plan, niveau et 300 tirages, ici.

## 6. Renotation de la population du juge de paix

Les 370 plans du banc du juge, notés par les noyaux de production (code de `1171c6af`) sous quatre modèles : livré
(grille grossière, lectures brutes, 1,66 A), figé (grille machine, moyenne sur 8 lectures, 1,00 A), et les deux avec
l'arrêt exact (D97). La recherche n'est pas relancée : on mesure ce que le modèle change au classement d'une population
déjà trouvée. Note : P95 de la RMSE spectrale au pire des trois niveaux de bruit, 300 tirages, plan éliminé au-delà de
5 % de plantage à un niveau ; courbure photométrique et couloir d'indice tirés comme en production, fente absente ;
mêmes tirages pour tous les plans et tous les modèles.

| modèle | déposables | meilleur plan (note) | gagnante du banc (rang 0) | plans à 8 % du meilleur |
|---|---|---|---|---|
| livré | 370 | 11 (0,007530) | 6ᵉ | 18 |
| figé | 370 | 11 (0,007055) | 7ᵉ | 26 |
| livré, arrêt exact | 370 | 11 (0,007457) | 3ᵉ | 16 |
| figé, arrêt exact | 370 | 28 (0,007048) ; le 11 à 1,1 % | 11ᵉ | 26 |

| comparaison | Spearman (370 plans) | note du second / note du premier, médiane |
|---|---|---|
| livré → figé | 0,920 | 0,897 |
| livré → livré, arrêt exact | 0,991 | 0,993 |
| figé → figé, arrêt exact | 0,993 | 0,994 |

Ce que cela dit :

- **Le modèle livré et le modèle figé désignent le même meilleur plan.** Reclasser au modèle figé les K premiers du
  modèle livré rend le même choix pour K de 1 à 50. Le modèle figé note environ 10 % plus bas, et resserre la tête :
  26 plans à 8 % du meilleur au lieu de 18, dont 13 en commun.
- **L'arrêt exact (D97) ne change presque rien** : −0,7 % de note en médiane, classement conservé à 0,99.
- **Les plans de tête sont indiscernables.** La gagnante du banc (rang 0) est 6ᵉ ici, à 4,6 % du plan 11 ; au banc,
  qui ajoute la fente et le consensus et tire d'autres bruits, le plan 11 était 3 % derrière elle. Les deux sont dans
  la classe d'équivalence que donne le bruit Monte-Carlo (ETAT, section 2 : deux runs à moins de ~8 % sont indiscernables).
- Avant les correctifs de la grille machine, la même renotation éliminait 21 plans sous le modèle figé, dont les
  rangs 8 à 22 du banc (Spearman 0,907 sur les 349 restants).

**Sur un empilement sans structure** (`r75x2`, les 50 premiers plans de
`reports/STRAT_bench_r75x2_deep_hysteresis_noise_level_306559d3_2026-10-05.json`, configuration
`JSON-strat-random75-x2-fabricable.json`, mêmes conditions) :

| modèle | déposables | meilleur plan (note) | plans à 4 % du meilleur | plans à 8 % |
|---|---|---|---|---|
| livré | 50 | 48 (0,074191) | 43 | 50 |
| figé | 50 | 47 (0,079976) | 18 | 35 |

- **Le signe s'inverse** : ici le modèle figé note **11 % plus haut** en médiane (sur le juge, 10 % plus bas). Le
  modèle livré n'est donc pas pessimiste en général ; cela dépend du composant. La cause n'est pas isolée.
- **La tête est un peloton** : sous le modèle livré, les 50 plans tiennent dans 8 % du meilleur, 43 dans 4 %. Les
  classements des deux modèles n'y concordent pas (Spearman 0,19), ce qu'on attend d'écarts aussi petits que le
  bruit Monte-Carlo.
- **Le meilleur plan change** (48 sous le modèle livré, 47 sous le modèle figé), mais le 48 n'est qu'à 3,9 % du 47
  au modèle figé : dans la classe d'équivalence. Reclasser au modèle figé les 10 premiers du modèle livré choisirait
  le 47.

## Reproduire

```bat
python scripts\probe_armement.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json 400 4 arm_juge.json
python scripts\probe_oms_sequentiel.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --ranks 0,6,7,13,50,100,150,200,250,300,350,369 --noises 1.0,2.0 --smoothing 8 --hyst 1.0
python scripts\probe_oms_sequentiel.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --ranks 0,50,200,350 --noises 1.0,2.0 --smoothing 8 --hyst 1.0 --kernel-smoothing 8 --kernel-hyst 1.0
python scripts\probe_modele_lecture.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --runs 300 --models livre,fige,livre_exact,fige_exact
python scripts\probe_modele_lecture.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --runs 300 --models fige,fige_arret_lisse --ranks 0,1,9,11,20,22,23,28,40,50,100,150,200,250,300,350,369
python scripts\probe_modele_lecture.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --runs 300 --models livre@1.0,livre@1.33,livre@1.66,livre@2.0,livre@2.4
python scripts\probe_modele_lecture.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json --runs 300 --models livre_ancres,livre_exact_ancres
python scripts\probe_arret_sans_bruit.py example\example_strat\JSON-strat-example.json reports\STRAT_bench_juge_de_paix_b60d80e2_temoin_2026-10-04.json [--exact-inversion] [--exact-anchors] [--no-poem]
```
