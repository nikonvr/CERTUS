# PRÉDIRE SI UN DESIGN PASSE AVEC UN SEUL VERRE TÉMOIN

> 👤 **2026-08-17** : *« le chantier suivant devrait se concentrer sur les 75c. Il faut arriver à
> comprendre pourquoi certains sont monitorables avec un seul verre témoin, et pas d'autres. Le
> but ultime serait d'arriver à prédire sans tout calculer si un design peut passer avec un seul
> verre ou pas. »*

Ce dossier fait **autorité** sur ce sujet. `CLAUDE.md` n'en garde qu'un renvoi.

---

## 1. 🔒 L'instrument, et pourquoi le 99c n'en est pas un

> 👤 : *« le 99c me gêne car il est rare de déposer un empilement tout 1/4 d'onde, surtout en
> trigger POEM. Je préfère ne pas en tirer de conclusions, alors que le 75c est intéressant avec
> ses 4 variantes. »*

**Il a raison, et c'est mécaniquement démontrable.** Les `stack_multipliers` du 99c valent
**exactement 1 et 2** à `l0 = 633 nm`. Or §14 pose que QWOT et point tournant **coïncident** sur
un empilement entièrement QWOT à λ_mon. Chaque couche finit donc **pile sur un extremum**, et
POEM — qui vise *un pourcentage de l'amplitude entre les deux derniers extrema* — voit sa plage
utile se réduire à un point.

🔴 **Le 99c est donc une configuration singulière pour POEM, pas simplement un cas difficile.**
Signature qui aurait dû alerter plus tôt : `plantage min = 100 %` **plat** sur **751 stratégies**
et **20 nombres de blocs distincts**. Une réponse plate porte zéro information — et c'est ce qui a
produit trois fausses conclusions le 2026-08-17 (§4).

### La série d'échelle du random75 — la seule expérience CONTRÔLÉE du projet

📏 `scripts/serie_echelle_r75.py`, `reports/serie_echelle_r75/`. **75 couches, structure,
matériaux, substrat et grille spectrale identiques aux quatre échelles. Seule l'épaisseur
optique varie.**

🔴🔴 **CE TABLEAU NE MESURE PAS LA FAISABILITÉ — IL MESURE CE QUE LA RECHERCHE COURANTE TROUVE.**
Établi le 2026-08-18, et c'est le résultat central du chantier. Les verdicts « échoue » ci-dessous
sont conditionnés à la **recherche standard** ; deux d'entre eux tombent quand on l'élargit.
**Lire §4quater et §4quinquies avant d'en tirer quoi que ce soit.**

| facteur | **Σ QWOT** | **ép. OPTIQUE** | QWOT par couche | couches < 1 QWOT | verdict *(recherche standard)* | déposables | `crash_min` | SEEL |
|---|---|---|---|---|---|---|---|---|
| **×0,5** | **57,4** | 9,09 µm | 0,252 – 1,240 | **59** | 🔴 échoue | 0/375 | **48 %** | — |
| **×1** | **114,9** | 18,18 µm | 0,504 – 2,479 | — | 🟢 **passe** | 241/662 | 0 % | **0,272 nm** |
| **×1,5** | **172,3** | 27,27 µm | 0,756 – 3,719 | 3 | 🟠 limite | **1/440** | 0 % | **0,633 nm** |
| **×1,75** | **201,1** | 31,82 µm | 0,882 – 4,338 | 2 | 🟢 **passe** | **282/746** | 0 % | **0,528 nm** |
| **×2** | **229,8** | 36,36 µm | 1,008 – 4,958 | **0** | 🔴 échoue *(standard)* · 🟢 **passe élargi** | 0/404 · **254/2945** | 100 % · **1,0 %** | — · **0,629 nm** |

🔴 **La ligne ×1,75, mesurée le 2026-08-18, DÉTRUIT la lecture monotone.** Elle est **plus
épaisse** que ×1,5 et rend **282 déposables contre 1**, avec un **meilleur** SEEL (0,528 contre
0,633 nm). L'ordre « plus c'est épais, plus c'est dur » n'existe pas.

⚠️ **Le `1/704` qui figurait ici est remplacé par `1/440`** : 704 venait d'un run à protocole
différent. Les cinq lignes ci-dessus sont désormais **toutes** en `fast`, fente 2 nm, graine 42 —
c'est ce qui les rend comparables.

### 🔴 « Fin » et « épais » se définissent en épaisseur OPTIQUE, jamais mécanique

> 👤 **2026-08-17** : *« selon les lois de la physique, fin/épais se définit en épaisseur optique
> totale, mais pas en épaisseur mécanique totale. À noter !!! »*

La finesse de la structure spectrale est gouvernée par la **phase accumulée**, donc par `n·d` et
non par `d`. Deux empilements de **même épaisseur mécanique** en matériaux d'indices différents
n'ont **pas** la même finesse spectrale, donc pas la même monitorabilité.

```
epaisseur OPTIQUE   = somme(m_i) * l0/4        -- ne depend PAS des indices
epaisseur MECANIQUE = somme(m_i * l0/(4 n_i))  -- depend du materiau
```

📏 Sur cette série le rapport vaut **1,82** — l'indice moyen effectif. Les deux grandeurs y sont
**proportionnelles** (mêmes matériaux, mise à l'échelle uniforme), donc **l'ordre du tableau est
inchangé**. Mais une conclusion libellée en micromètres mécaniques **ne se généraliserait pas** à
d'autres matériaux.

🔑 **La mesure la plus propre est la somme des QWOT** : sans unité, sans indice, sans λ₀. C'est
elle qu'il faut citer — **57,4 / 114,9 / 172,3 / 229,8 quarts d'onde**, et le basculement se
situe donc entre **172 et 230 quarts d'onde** du côté épais, entre **57 et 115** du côté mince.

🔑 **Échec → succès → limite → échec, à nombre de couches et structure constants.** C'est le
seul endroit du projet où l'issue varie **continûment** avec une variable contrôlée, et c'est ce
qui en fait le **jeu de calibration** dont un prédicteur a besoin.

⚠️ **Les multiplicateurs ne sont jamais entiers, à aucune échelle** — POEM opère donc en régime
normal, contrairement au 99c.

⚠️ **×1,5 rend 1 déposable sur 704.** C'est le régime marginal où §24-46 a mesuré que la
**graine retourne le verdict**. `×1,5 « passe »` et `×0,5 « échoue »` sont **tous deux suspects
sur une seule graine**. Deux graines minimum sur les points marginaux avant toute conclusion.
🟢 Un bon signe quand même : ×1,5 joué en **fast** et en **premium** rend le même `1 déposable,
SEEL 0,63` — il est au moins stable en mode.

⚠️ La série va de 5 à 20 µm d'épaisseur physique. À 20 µm un vrai bâti aurait des problèmes de
contrainte et de durée que le modèle ignore. **C'est un instrument, pas une proposition de
design.**

---

## 2. Ce que la série établit sur le mécanisme

Ni le nombre de couches ni la structure ne gouvernent — les deux sont constants dans la série.
Reste l'**épaisseur optique**, et il faut distinguer **deux grandeurs distinctes** que les
premières rédactions de ce dossier confondaient :

| grandeur | ce qu'elle gouverne | ×0,5 | ×1 | ×1,5 | ×2 |
|---|---|---|---|---|---|
| **Σ QWOT** — épaisseur optique **totale** | l'**espacement des oscillations spectrales**, donc la **résolution spectrale** exigée du monochromateur | 57,4 | 114,9 | 172,3 | **229,8** |
| **QWOT par couche** | le nombre de **points tournants** traversés pendant la croissance, donc la disponibilité d'une **ancre de phase** pour POEM | **0,25 – 1,24** | 0,50 – 2,48 | 0,76 – 3,72 | 1,01 – 4,96 |

### 🔴 Et l'explication « ×0,5 échoue faute d'ancre » est FAUSSE — comptage naïf

⚠️ **C'est l'erreur que §14 désigne comme la plus coûteuse du projet, et les premières versions de
ce dossier la commettaient** : *« QWOT ≠ point tournant […] se tromper coûte un facteur 59 : sur
le random75 ×0,5, le comptage naïf annonce 59 couches "sans point d'arrêt", le comptage exact en
trouve 1 »*.

📏 **Et la mesure du 2026-08-17 le confirme, sur ce même empilement :**

```
r75x0.5   couches sans aucune lambda admissible : 1 / 75
```

**Une seule couche sur 75**, pas 59. Le départ d'un point tournant est décalé d'une phase
`½·arctan(R/Q)` fixée par l'empilement du dessous : une couche sous 1 QWOT **peut parfaitement**
traverser un extremum. Les 59 couches sous 1 QWOT ne disent donc **rien** sur la disponibilité
d'une ancre.

🔴 **Conséquence : le taux de 48 % de ×0,5 n'est PAS expliqué.** Il ne vient pas d'une absence
d'ancre. Et cela rejoint une correction de 👤 le même jour : *« si les couches sont trop fines, il
y a effectivement un risque de ne pas détecter de point tournant, mais cela n'invalide pas de
pouvoir faire du monitoring — simplement il n'y a pas de correction type POEM »*. Une couche sans
ancre s'arrête sur un **niveau absolu** ou au **Rate** ; ce qu'elle perd est la compensation
d'erreur, pas la faisabilité.

📌 **Ce qui trancherait**, et ce n'est pas encore mesuré : la ventilation de `margin_by_layer` de
×0,5 **par cause**. `margin_missed` désigne un extremum non émis parce que le swing est sous
l'hystérésis ; `margin_fabricated`, un extremum émis par le bruit seul. Si ×0,5 est dominé par
`margin_missed`, l'explication par l'ancre revient — mais alors sur le **swing**, pas sur le QWOT.

---

## 3. 🔴 Aucune grandeur du signal nominal ne prédit l'échec

📏 **Test loyal du 2026-08-17**, `scripts/probe_distance_extremum.py` sur les quatre échelles.
TMM pure, aucun solveur, aucun Monte-Carlo.

**Définition exacte de la colonne 1** — une couche est comptée quand **aucune** λ de la grille ne
satisfait les trois critères simultanément : `swing ≥ dynamics_threshold`, `T_min ≥
min_transmission_floor`, et **au moins un point tournant** dans l'intervalle de croissance. C'est
le comptage **exact**, pas le comptage naïf par QWOT.

⚠️ **La troisième colonne n'est PAS une marge.** Elle mesure, sur l'empilement **nominal** et sans
bruit, la **distance à l'extremum** — l'écart en transmission entre la fin de la couche et son
dernier extremum, exprimé en multiples de `A`. C'est une grandeur **différente** de la marge de
niveau de §24-41, qui est mesurée sur la trajectoire **bruitée et accumulée**. Voir §7.

| composant | couches sans λ admissible | blocs minimum | distance à l'extremum, min | méd | **issue mesurée** |
|---|---|---|---|---|---|
| ×0,5 | **1** | 4 | 109,0 A | 570 A | 🔴 échoue |
| ×1 | 0 | 2 | **78,9 A** | 600 A | 🟢 passe |
| ×1,5 | 0 | 1 | 480,5 A | 625 A | 🟠 limite |
| ×2 | 0 | 1 | 443,7 A | 598 A | 🔴 échoue |

| grandeur | verdict |
|---|---|
| **couches sans λ admissible** | 🟠 **seule à porter un signal** — 1 pour ×0,5, 0 partout ailleurs. ⚠️ Mais **1 couche sur 75 n'explique pas un taux de 48 %** : c'est une corrélation sur un seul point, pas un mécanisme établi |
| **blocs minimum** | ❌ 4/2/1/1, monotone avec Σ QWOT ; ×1,5 et ×2 tiennent tous deux en **1 bloc** alors que l'un réussit et l'autre échoue |
| **distance à l'extremum, minimum** | ❌ **anticorrélée** : celui qui réussit porte la distance la plus **courte** (78,9 A) |
| **distance à l'extremum, médiane** | ❌ plate, ~600 A pour les quatre |

🔑 **Aucune grandeur du signal nominal ne prédit l'échec par résolution spectrale insuffisante**
(×2). Et la seule qui distingue ×0,5 ne le fait que par **un** point, ce qui ne constitue pas une
prédiction.

---

## 4. Les routes fermées, et ce qu'elles ont coûté

Chacune est fermée par une **mesure**, pas par un raisonnement. Elles sont ici pour ne pas être
refaites.

### 4.1 ❌ La cohérence en λ — elle classe les composants À L'ENVERS

📏 `scripts/profil_monitorabilite.py`, 49 s pour les quatre composants. Le nombre était calculé
et committé depuis le 2026-08-16 (`af5a7ca`), reproduit **bit-identique** le 17/08 ; **sa lecture
n'avait jamais été écrite**.

```
couches SANS aucune lambda utilisable :  0/99   0/75   0/48   0/35
```

λ servant **tout** le préfixe `[0,b)` — ce qu'un **bloc unique** exigerait :

| b | 99c | 75c | 48c | 35c |
|---|---|---|---|---|
| 30 | 55 | **26** | 89 | 30 |
| 60 | 33 | **0** 🔴 | — | — |
| complet | **26** | **0** | 64 | 28 |

Le 75c tombe à zéro dès la couche 60 ; le 99c garde 26 λ sur ses 99 couches — et c'est le
**75c** qui passe. **La périodicité achète la cohérence en λ ; elle n'achète pas la
monitorabilité.**

⚠️ **Et le `0` du 75c ne veut PAS dire « non monitorable ».** Il veut dire *« aucune λ unique ne
couvre 60 couches d'affilée »*. Changer de λ n'est **pas** changer de verre : sur un même témoin
la machine change de λ autant de fois qu'il faut, le 48c gagne à **2 blocs** et la zone favorable
est **4 à 7** (§24-44).

### 4.2 ❌ Le nombre de blocs — réfuté sur 751 stratégies

📏 `scripts/probe_blocs_vs_plantage.py` sur le 99c complet, premium, graine 42.

```
 n_blocs  OFFERTES  plantage moy  plantage min  deposables
       1        10       100.00%       100.00%           0
       4        48       100.00%       100.00%           0
       6        48       100.00%       100.00%           0
      19         4       100.00%       100.00%           0
      99         1       100.00%       100.00%           0
zone favorable 4-7 blocs : 184 offertes sur 751 (24,5 %) -- 0 deposable
```

L'hypothèse était : *un bloc long détruit la compensation (`MAX_LOOKBACK = 4`, §24-21), un bloc
court perd ses ancres, donc l'optimum est dans la zone 4-7 (§24-44)*. **Réfutée** :

- la zone favorable **a été explorée** — 184 stratégies, un quart de l'offre — et ne donne rien ;
- 🔑 la stratégie à **99 blocs**, qui se réancre à **chaque couche** — compensation maximale
  possible — plante aussi à **100 %**. Ni les blocs trop longs ni les blocs trop nombreux
  n'expliquent quoi que ce soit ;
- ce n'est **pas** un défaut d'offre de la recherche : elle a proposé de 1 à 19 blocs plus une à
  99. Le motif de §24-37 ne s'applique pas.

⚠️ **751 stratégies évaluées** là où le dépôt documente « 487 ». Le chiffre est à réviser.

### 4.3 ❌ L'énumération exhaustive — morte d'un facteur 10⁵⁰

📏 `scripts/probe_denombre_couvertures.py`. 99c, base `adm_tp`, k ≤ 20 blocs :

```
couvertures  1,13 x 10^20        STRATEGIES  5,02 x 10^57
```

| k blocs | couvertures | stratégies | criblage à 25 tirages |
|---|---|---|---|
| **1** | 1 | **26** | **1 min** |
| **2** | 98 | **162 358** | **54,1 h** — ou ~22 h à 10 tirages |
| 3 | 4 753 | 549 millions | **7 622 jours** |
| 6 | 67 910 864 | 3,5 × 10¹⁸ | 4,9 × 10¹³ jours |

🔑 **La tractabilité s'arrête entre 2 et 3 blocs.** k=2 coûte deux jours, k=3 vingt siècles. Une
preuve d'impossibilité **par énumération** n'est donc possible que pour k ≤ 2, ce qui ne conclut
rien au-delà.

**Et une recherche ne donne jamais une non-existence** — elle donne *« je n'ai pas trouvé »*.
Seule une **condition nécessaire violée partout** peut conclure, et elle couvre les 10⁵⁷ d'un
coup.

### 4.4 ❌ La condition nécessaire, version nominale — et une erreur de ma part

📏 `scripts/probe_distance_extremum.py`. **0 couche bloquante** sur le 99c comme sur le 75c.

🔴 **Et le seuil invoqué était le mauvais.** §24-41 mesure la marge **pendant un dépôt simulé**,
avec bruit **et** erreur accumulée : valeurs de −1702 A à ~0,9 A, seuil discriminant **0,6 A**.
La sonde mesure la distance en transmission entre la fin de la couche et son dernier extremum sur
l'empilement **nominal** : **242 à 600 A**. Trois ordres de grandeur. **Le seuil ne se transporte
pas**, et la sonde ne teste donc pas le critère annoncé.

📌 La bonne version reste **ouverte** : rejouer la mesure sur la **trajectoire accumulée**.
`turning_point_margins` la calcule déjà et elle remonte jusqu'à `margin_by_layer` — c'est de
l'instrumentation, pas une physique nouvelle.

### 4.5 ❌ La résolution spectrale exigée par le design — n'ordonne pas la série

📏 `scripts/probe_resolution_exigee.py`, 2026-08-17. **Critère de réussite écrit dans le
docstring avant le run** : `res_lim` doit être confortable à ×1, se dégrader à ×1,5, et passer
sous **0,5 nm** — la résolution la plus fine que la machine offre (§19) — à ×2.

`_calculate_strategy_spectral_resolution` (`certus_strat_robustness.py:626`) calcule déjà, pour
une stratégie, la résolution la plus large que la courbure tolère :

```
second_diff = (T(lam - B/2) + T(lam + B/2))/2 - T(lam)      B = 1 nm
res_limit   = B * sqrt(3 * trigger_tolerance/100 / |second_diff|)
```

Rendue **indépendante de toute stratégie** : pour chaque couche, la plus grande `res_limit` sur
les λ **admissibles** — le meilleur cas atteignable — puis le minimum sur les couches.

| composant | res_lim exigée | couche | fentes machine utilisables | issue mesurée |
|---|---|---|---|---|
| ×0,5 | **2,610 nm** | 72 | 2 · 1 · 0,5 | 🔴 échoue (48 %) |
| ×1 | **1,583 nm** | 58 | 1 · 0,5 | 🟢 passe |
| ×1,5 | **0,767 nm** | 70 | 0,5 | 🟠 limite |
| ×2 | **1,033 nm** | 68 | 1 · 0,5 | 🔴 échoue (100 %) |
| 99c | 1,163 nm | 94 | 1 · 0,5 | 🔴 échoue |
| 48c | 4,487 nm | 40 | 2 · 1 · 0,5 | 🟢 passe |
| 35c | 4,200 nm | 31 | 2 · 1 · 0,5 | 🟢 passe |

🔴 **Elle se dégrade jusqu'à ×1,5 puis REMONTE à ×2, et ne descend jamais sous 0,5 nm.** Le
composant qui échoue à 100 % exige **moins** de finesse que celui qui passe de justesse. Non
monotone : la route se ferme.

⚠️ **Corrélation à ne pas surinterpréter** : sur les composants réels, les deux qui passent (48c
à 4,487 nm, 35c à 4,200 nm) ont bien les valeurs les plus confortables. Mais **c'est la série
contrôlée qui fait foi**, et elle réfute.

#### 🔑 Et le run révèle un écart mesuré — le seul apport positif de cette route

Le journal `[SLIT]` annonce sur ×2 que **toutes** les résolutions autres que 2 nm sont écartées
par la courbure, pour 100 % des stratégies. Or le design en tolère **1,033 nm**. Les deux sont
vrais :

| | |
|---|---|
| ce calcul | prend pour chaque couche la **meilleure λ admissible** — le meilleur cas |
| les stratégies réelles | utilisent les λ que la Phase A a choisies **pour leur coût**, pas pour leur courbure |

> **Le design de ×2 permettrait 1 nm si les λ étaient choisies pour la courbure. Celles que la
> recherche retient ont une courbure bien pire.**

C'est un écart entre ce que l'empilement **autorise** et ce que la recherche **va chercher**, et
il suggère que `res_lim` aurait sa place comme **coût en Phase A** — orienter le choix des λ vers
les zones de faible courbure — au lieu de servir seulement de préfiltre a posteriori sur les
variantes de résolution.

⚠️ **Piste de recherche, pas de prédiction.** Elle ne rend pas le prédicteur.

---

## 4bis. 🟢 LA MARGE ACCUMULÉE — la première grandeur qui ORDONNE la série

📏 **Mesuré le 2026-08-17 au soir**, action n° 3 du §6. Protocole identique sur les trois
points : `fast`, fente 2 nm, graine 42, `search_resolution` inactif.

La grandeur n'est pas la marge d'une stratégie : c'est le **nombre de couches dont la marge
reste sous le seuil pour TOUTES les stratégies évaluées**, cause par cause. C'est la forme d'une
condition nécessaire violée — toute stratégie doit déposer cette couche, donc aucune ne la
contourne.

| variante | Σ QWOT | stratégies | `fabricated` | `level` | `missed` | **total** | plantage min |
|---|---|---|---|---|---|---|---|
| ×1 (`75c`) | 114,9 | 662 | 0 | 0 | 0 | **0** | 0 % |
| ×1,5 | 172,3 | 440 | 5 | 0 | 0 | **5** | 0 % |
| ×2 | 229,8 | 404 | 15 | 4 | 6 | **25** | 100 % |

🔑 **C'est la première grandeur du chantier qui croît avec Σ QWOT** — 0, 5, 25. Les cinq routes
du §4 rendaient toutes soit un ordre plat, soit un ordre à l'envers.

🔴 **Mais elle ne sépare PAS « passe » de « échoue » à zéro.** ×1,5 en porte **5** et passe à 0 %
de plantage. Il n'existe donc pas de seuil « une couche contrainte partout ⇒ impossible », et
c'est exactement l'inverse de ce que la route cherchait : une **condition nécessaire**. Ce qu'on
tient est un **indicateur monotone**, pas une impossibilité démontrée.

⚠️ **Le facteur de confusion, et il faut le dire avant qu'on me le dise.** « Contrainte par les
N stratégies » est **mécaniquement plus facile quand N est petit** : il suffit qu'une seule
stratégie relâche la couche pour qu'elle sorte du compte. Or N vaut 662, 440 et 404.

| comparaison | écart de N | écart du compte | verdict |
|---|---|---|---|
| ×1,5 → ×2 | 440 → 404, **−8 %** | 5 → 25, **×5** | 🟢 l'effet ne vient pas de N |
| ×1 → ×1,5 | 662 → 440, **−34 %** | 0 → 5 | 🟠 partiellement confondu |

Le pas qui compte — celui qui traverse la frontière de fabricabilité — est donc **propre**. Le
premier pas ne l'est pas, et il ne faut pas s'appuyer dessus.

🔴 **Et ×0,5 MANQUE dans ce tableau.** Le seul run disponible sur ce composant est celui à
recherche de fente (796 stratégies) : son échantillon est **biaisé** — seules les stratégies dont
les λ toléraient la largeur ont été retenues — et son N n'est comparable à aucun des trois. **Ne
pas le mettre dans la colonne.** La cellule propre est produite par le lot du 2026-08-17 au soir,
et elle y est placée **avant** sa variation à 5 nm pour cette raison précise.

🔑 **Ce que ça coûte, et c'est ce qui empêche d'appeler ça un prédicteur.** `margin_by_layer`
sort de la simulation Monte-Carlo : l'obtenir demande de faire tourner la campagne complète.
👤 demandait *« prédire sans tout calculer »* — cette grandeur exige précisément de tout
calculer. **C'est un mécanisme, pas un prédicteur.** Sa valeur est de dire *où* regarder pour en
construire un : la cause dominante est `fabricated` (point tournant fabriqué par le bruit) sur
les deux variantes qui en portent, et non `level` comme la cause de plantage majoritaire le
laissait croire.

📌 **La suite qu'elle appelle** : chercher une version **statique** de la même quantité — la
distance nominale à l'extremum pondérée par l'erreur d'épaisseur accumulée attendue — qui se
calculerait sans tirage. `probe_distance_extremum.py` en calcule déjà le premier facteur.

---

## 4ter. 🟢 LA GRILLE RÉSOLUTION × ÉPAISSEUR OPTIQUE — l'hypothèse de 👤 est CONFIRMÉE

📏 **Lot du 2026-08-17 au soir**, 12 cellules, protocole identique : `fast`, graine 42,
`search_resolution` inactif, seule la fente du run varie. La comparaison est exacte par
construction : le facteur de bruit multiplie l'**échantillon**, jamais la graine (contrainte C2,
`certus_strat_robustness.py:192`), donc deux résolutions voient les **mêmes tirages**.

> 👤 **2026-08-17** : *« un filtre trop épais a des pics en transmission et peut-être que le
> filtre serait monitorable en résolution 1 nm et pas 2 nm. Valable pour les empilements
> épais. »*

### Plantage minimum

| variante | Σ QWOT | 5 nm | 2 nm | 1 nm | 0,5 nm |
|---|---|---|---|---|---|
| ×0,5 | 57,4 | 70 % | 48 % | **28 %** | 82 % |
| ×1 | 114,9 | **0 %** | **0 %** | 4 % | 44 % |
| ×1,5 | 172,3 | — | **0 %** | 30 % | 76 % |
| ×2 | 229,8 | — | 100 % | **38 %** | 80 % |

🔴 **CORRECTION DU 2026-08-18 — la première rédaction de cette section était FAUSSE sur ×0,5.**
Elle affirmait *« passer à 1 nm dégrade ×0,5, ×1 et ×1,5 et améliore ×2 : le signe s'inverse une
seule fois »*, et en tirait une loi monotone en Σ QWOT. Le chiffre de ×0,5 à 1 nm venait alors
d'un **échantillon biaisé** (run à recherche de fente : seules les stratégies dont les λ
toléraient la largeur étaient retenues) et valait **84 %**. La cellule propre, mesurée cette
nuit, vaut **28 %** — c'est-à-dire que **1 nm AMÉLIORE ×0,5 aussi**. La loi monotone n'existe pas.

⚠️ C'est exactement le piège que ce dossier documente ailleurs : *un échantillon biaisé ne vaut
pas une cellule propre*. Je l'avais écrit, puis j'ai cité le chiffre biaisé dans le texte tout en
marquant la case « à mesurer » dans le tableau. **Ne jamais laisser un chiffre biaisé porter une
affirmation.**

### 🔑 La lecture juste : la fente fine est un REMÈDE, pas une amélioration

Comparaison 1 nm contre 2 nm, une fois la ligne mince propre :

| variante | 2 nm | 1 nm | |
|---|---|---|---|
| ×0,5 | 48 % | **28 %** | 🟢 1 nm aide |
| ×1 | **0 %** | 4 % | 🔴 1 nm nuit |
| ×1,5 | **0 %** | 30 % | 🔴 1 nm nuit |
| ×2 | 100 % | **38 %** | 🟢 1 nm aide |

**Les deux cas où 1 nm aide sont exactement les deux qui ÉCHOUENT à 2 nm.** Et les deux où il
nuit sont exactement ceux qui sont déjà à **0 %** — où aucune amélioration n'est possible, la
comparaison butant sur un plancher. Ce n'est donc pas une préférence spectrale, c'est un **effet
de plafond**.

> **La règle défendable : affiner la fente est un remède quand le monitoring échoue, et un coût
> net quand il fonctionne.** Là où ça marche déjà, on ne paie que le ×2 de bruit.

🔴 **La loi en Σ QWOT est donc RETIRÉE.** Le mécanisme biais/bruit reste vrai — le biais va en
`B²` (÷4 de 2 à 1 nm), le bruit suit `RESOLUTION_NOISE_FACTOR` (×2) — mais il ne se laisse pas
lire comme une fonction monotone de l'épaisseur optique. Ce que la grille établit est plus
modeste et plus sûr : **quand une configuration échoue à la fente nominale, la fente fine est le
premier levier à essayer**, et il a fonctionné aux deux bouts de la série.

🟠 **À exploration standard, ×2 n'est pas fabricable pour autant** : 38 % reste très loin de la
tolérance de 5 %, et la cellule ne rend aucune stratégie déposable. 🔴 **Mais ce n'était pas la
fin de l'histoire — voir §4quater, où l'élargissement de la recherche le rend fabricable.**

### SEEL — et il n'existe que là où il y a des déposables

🔴 **Ailleurs, le score est un score de REPLI et ne se convertit PAS en SEEL.** C'est ce qui a
produit le faux « 0,86 nm » du 99c (§21). Sur douze cellules, **quatre** portent un SEEL.

| variante | fente | SEEL | déposables | plantage min |
|---|---|---|---|---|
| ×1 | 5 nm | 0,310 nm | 289 | 0 % |
| ×1 | **2 nm** | **0,272 nm** | 241 | 0 % |
| ×1 | 1 nm | 0,371 nm | 12 | 4 % |
| ×1,5 | 2 nm | 0,633 nm | 1 | 0 % |

✅ **La dérivation `SEEL = 2·√(score)` est validée** : ×1 à 2 nm rend **0,272 nm**, exactement le
repère publié au §21. Les autres valeurs sont donc lisibles sur la même échelle.

### 🔴 La fente large achète du RENDEMENT et paie de la PRÉCISION

C'est le résultat le moins intuitif de la grille, et il corrige une lecture hâtive faite le soir
même — *« 289 déposables contre 241, donc 5 nm gagne »*.

| fente sur ×1 | SEEL | déposables |
|---|---|---|
| 5 nm | 0,310 nm | **289** |
| 2 nm | **0,272 nm** | 241 |

**Les deux colonnes classent à l'envers l'une de l'autre.** La règle de tri du §22 étant *SEEL
d'abord, rendement en départage*, c'est **2 nm qui gagne** — la fente nominale de la machine.
Élargir déforme le signal (biais en `B²`), donc l'arrêt est moins juste ; en échange le bruit
baisse de ÷1,5 et il plante moins. **Un arbitrage, pas un gain gratuit.**

⚠️ **Ne pas lire les scores de repli comme une tendance.** Sur ×2, le repli vaut 0,217 à 2 nm et
0,269 à 1 nm — *plus mauvais* là où le plantage s'effondre de 100 % à 38 %. Comparer deux scores
de repli revient à comparer deux façons d'échouer.

### Ce qui reste avant d'en tirer quoi que ce soit de publiable

| | |
|---|---|
| 🔴 **graine unique** | 42. §24-46 : un verdict marginal bascule avec la graine. Une seconde graine sur ×2 à 1 nm est dans le lot |
| 🔴 **mode FAST** | §8 : toute cellule rendant des déposables se rejoue en **premium** avant publication |
| 🟠 **×0,5 incomplet** | ses cellules 1 nm et 0,5 nm sont en consolidation ; seuls 5 et 2 nm sont propres |
| 🟠 **quantification** | les taux sont des multiples de 2 % — un « 38 % » est lu à ±2 % |

---

## 4quater. 🟢🟢 ×2 EST FABRICABLE À UN SEUL TÉMOIN — c'était la RECHERCHE, pas la physique

📏 **Mesuré le 2026-08-18, phase 2 du lot de nuit.** ×2, fente **1 nm**, mode `deep`, profil
d'exploration élargi (`ELARGISSEMENT`, `probe_blocs_vs_plantage.py`), graine 42, 157 min.

| | stratégies | déposables | plantage min | meilleur SEEL |
|---|---|---|---|---|
| exploration **standard** (`fast`) | 429 | **0** | 38 % | — *(repli)* |
| exploration **élargie** (`deep` + profil élargi) | **2 945** | **254** | **1,00 %** | **0,629 nm** |

🔑 **×2 était déclaré impossible depuis trois jours — 100 % de plantage sur 404 stratégies à la
fente nominale.** Il rend aujourd'hui **254 stratégies déposables**, dont la meilleure plante
**2 fois sur 150** et porte un SEEL de **0,629 nm**. C'est le premier SEEL valide jamais mesuré
sur ce composant.

**Il a fallu DEUX choses ensemble**, et ni l'une ni l'autre ne suffit :

| | |
|---|---|
| la **fente fine** (1 nm) | seule, elle fait tomber le plantage de 100 % à 38 % — sans aucun déposable |
| l'**exploration élargie** | seule, elle n'a pas été testée à 2 nm ; à 1 nm elle apporte les 254 |

### 🔴 Ce que cette mesure N'ÉTABLIT PAS — trois réserves, et elles comptent

**1. L'attribution est un LOT, pas un facteur.** La phase 2 change `execution_mode` (`fast` →
`deep`, soit `dp_top_k` 20 → 100) **et** six limites de candidates (×3 à ×4). Contrainte C3 : deux
changements simultanés ne s'attribuent pas. Ce qui est établi est *« élargir la recherche »* comme
bloc, pas lequel de ses sept leviers porte l'effet.

**2. La profondeur d'évaluation a changé aussi — 50 → 300 tirages.** `execution_mode = deep`
pose `robustness_num_runs = 300` (`certus_strat_ui_state.py:1296`). 📏 Vérifiable dans les
données : les cellules `fast` rendent des taux multiples de 2 % (1/50), la gagnante de la phase 2
plante **4 fois sur 300** et le `crash_min` du run vaut **3/300 = 1,00 %**.
✅ **Mais ce biais joue CONTRE le résultat, donc il ne l'explique pas** : à 50 tirages, une
stratégie dont le taux vrai vaut 1,3 % affiche **zéro** plantage une fois sur deux, et serait donc
comptée déposable **plus facilement**. Passer à 300 tirages ne peut que **révéler** des plantages,
jamais en cacher. Si `fast` n'a trouvé aucune déposable, ce n'est pas faute de tirages — c'est que
**ces stratégies n'ont jamais été proposées**.

**3. Une seule graine (42).** §24-46 : un verdict marginal bascule avec la graine. 254 déposables
sur 2 945 n'est pas marginal, mais le chiffre exact ne tient pas sur une graine.

### 🔑 C'est le défaut §24-37, dans l'autre sens

> §24-37 : *« la stratégie n'est plus choisie, elle est forcée — et le résultat final n'en porte
> aucune trace. »*

Ici le motif est le même et le coût est plus grand : le système annonçait **100 % de plantage**,
c'est-à-dire *« ce composant n'est pas monitorable à un témoin »*, alors que la vraie phrase
était *« ma recherche n'a pas proposé ce qui marche »*. Rien dans la sortie ne permettait de les
distinguer.

📏 **Signature à retenir** : les 254 déposables se répartissent sur **6, 7, 9, 10 et 11 blocs** —
**aucune en dessous de 6, aucune au-dessus de 11**. La recherche standard, elle, plafonnait bien
plus bas. C'est cohérent avec la zone favorable de §24-44 (4-7 blocs), étendue vers le haut.

### 🟢 LE LIVRABLE — un mode `extreme` et un fichier prêt à lancer

> 👤 **2026-08-18** : *« crée un JSON spécifique pour que le code trouve de lui-même, pour un
> utilisateur inexpérimenté, le 75×2 fabricable »*, puis *« j'aime bien l'idée du mode spécifique
> si l'utilisateur a tout son temps »*.

**Un quatrième mode d'exécution, `extreme`**, à côté de `fast` / `premium` / `deep`
(`certus/ui/certus_strat_ui_state.py`). Il élargit ce qui est **généré et retenu**, et laisse la
profondeur d'**évaluation** identique à `deep` — un taux de plantage produit en `extreme` reste
donc directement comparable à un run `deep`.

| paramètre | fast | premium | deep | **extreme** |
|---|---|---|---|---|
| `robustness_num_runs` | 50 | 150 | 300 | **300** |
| `n_screen_runs` | 10 | 25 | 50 | **50** |
| `dp_top_k` | 20 | 40 | 100 | **100** |
| `k_keep_survivors` | 6 | 10 | 25 | **40** |
| `mining_candidates_limit` | 3 000 | 3 000 | 10 000 | **12 000** |
| `phase_a_keep_limit` | 50 | 50 | 50 | **200** |
| `top_k_parents` | 20 | 20 | 20 | **80** |
| `max_fusions_per_parent` | 5 | 5 | 5 | **15** |
| `screening_keep_top_k` | 5 | 5 | 5 | **20** |
| `strategy_phase_timeout` | 300 | 300 | 300 | 10 800 — 🔴 **inerte, voir plus bas** |

🔒 **Règle d'or vérifiée** : les trois modes existants rendent **exactement** les mêmes valeurs
qu'avant — contrôlé paramètre par paramètre. Une branche `elif` ajoutée ne touche aucun chemin
existant, et le défaut reste `premium`.

🔴🔴 **CORRECTION DU 2026-08-18 — `strategy_phase_timeout` EST INERTE, et j'avais écrit ici
l'exact contraire.** Cette ligne affirmait qu'il était *« le paramètre sans lequel le mode ne
servirait à rien »*. 📏 Vérifié :

```
grep -rn strategy_phase_timeout certus/core certus/workers  ->  0
```

Il est collecté par `collect_params`, affiché dans un widget *« Max Time per Iteration (sec) »*,
enregistré dans les JSON — et **aucune ligne de calcul ne le lit**. C'est le **quatrième** cas du
motif §24, après `fast_auto_blocks`, `machine_sampling_dd` et `dp_yield_weight`.

⚠️ **Conséquence sur l'attribution** : `extreme` ne compte donc que **six** leviers actifs, pas
sept. Et le contrôle `deep` seul en file n'est **pas** confondu par un plafond différent — ce que
je craignais en montant l'audit — puisque le plafond n'agit nulle part.

**Les vrais bornages sont ailleurs, et ils sont codés en dur :**

| | |
|---|---|
| `timeout=30.0` passé à la DP (`certus_strat_ranking.py:410`) | 🟢 **inerte aussi** — la fonction déclare `timeout` et `start_time` dans sa signature et ne les lit jamais dans son corps. Donc **aucun risque de troncature sur la cellule `dp_top_k = 200`** |
| `concurrent.futures.wait(futures, timeout=600)` (`certus_strat_workers.py:1402`) | 🟠 n'ampute **pas** les résultats — `shutdown(wait=True)` attend la fin — mais **cesse de journaliser les exceptions** au-delà de 600 s. Sur une cellule de 157 min, une erreur tardive est **muette** |

**Et le fichier prêt à lancer** : `example/example_strat/JSON-strat-random75-x2-extreme.json`.
Il porte l'empilement ×2, la fente à 1 nm, le mode `extreme` et la graine 42 — c'est-à-dire
**exactement** la configuration qui a produit les 254 déposables. On le charge, on lance, il n'y a
rien d'autre à régler. Le fichier dit lui-même ce qu'il coûte (≈ 2 h 40) et ce qu'il ne promet pas.

⚠️ **Et il dit aussi ce qu'il ne faut PAS en déduire** : la fente fine n'est pas un réglage
universel. Elle achète de la finesse spectrale et paie du bruit (×2 en passant de 2 à 1 nm) ; sur
un empilement qui fonctionne déjà, elle **dégrade** le résultat (§4ter).

### 🔴 `extreme` EST-IL OPTIMAL ? NON — et il n'est même pas prouvé NÉCESSAIRE

> 👤 **2026-08-18** : *« penses-tu qu'il soit optimal si l'utilisateur a tout son temps ? »*

**Trois choses manquent, et la première est un contrôle que j'aurais dû faire avant d'écrire quoi
que ce soit.**

**1. 🔴 `deep` SEUL n'a jamais été mesuré sur ce point.** Le run à 0 déposable est en **`fast`**.
J'ai pourtant écrit *« deep rend 0 et extreme en rend 254 »* dans quatre fichiers, dont la page
commerciale. **C'était une affirmation non mesurée**, corrigée le 2026-08-18. Tant que le contrôle
n'a pas tourné, on ne sait pas si `extreme` était **nécessaire** — `deep` seul aurait peut-être
suffi, et un mode nommé qui ne sert à rien est pire qu'un mode absent. Le contrôle est en tête de
la campagne élargie.

**2. Les multiplicateurs annoncés sont relatifs à la config de BASE, pas à `deep`.** Lu par rapport
à `deep` — le mode auquel un utilisateur pressé le comparerait — le profil est bien moins large
qu'il n'y paraît, et il laisse intacts les deux leviers les plus en amont :

| levier | deep | extreme | ×  |
|---|---|---|---|
| `dp_top_k` — la largeur du faisceau de la DP en Phase A | 100 | 100 | **×1 — pas élargi** |
| `elite_rounds` | 3 | 3 | **×1 — pas élargi** |
| `mining_candidates_limit` | 10 000 | 12 000 | ×1,2 |
| `k_keep_survivors` | 25 | 40 | ×1,6 |
| `max_fusions_per_parent` | 5 | 15 | ×3 |
| `phase_a_keep_limit` | 50 | 200 | ×4 |
| `top_k_parents` | 20 | 80 | ×4 |
| `screening_keep_top_k` | 5 | 20 | ×4 |

🔑 **`extreme` élargit ce qui est RETENU sans élargir ce qui est ENGENDRÉ.** On garde quatre fois
plus d'une offre dont la source, elle, n'a pas bougé. C'est peut-être exactement le bon réglage —
si le goulot était la rétention — mais **personne ne l'a vérifié**.

**3. Aucun test de saturation.** On ne sait pas si doubler encore rendrait plus de déposables ou
rien du tout. « Si l'utilisateur a tout son temps » appellerait un réglage à la **frontière du
rendement décroissant**, et cette frontière n'est pas localisée.

### 🔴 RÉFUTÉ LE 2026-08-18 — `dp_top_k` n'est PAS le levier, et c'est mon propre critère qui l'a tué

J'avais écrit ci-dessus que `dp_top_k` était *« le levier le plus en amont »* et monté une cellule
de 240 min pour le porter de 100 à 200. 📏 `scripts/probe_destructif_dp_top_k.py`, 35c, critère
d'effondrement **≥ 5× écrit avant le run** :

```
dp_top_k =   1   la DP recoit [1]   sur 24 appels  ->  250 strategies
dp_top_k = 100   la DP recoit [100] sur 24 appels  ->  304 strategies     facteur 1,22x
```

✅ **Le câblage est prouvé** — la DP reçoit bien la valeur imposée, 24 appels sur 24, ce que
l'espion posé sur `_find_k_best_groupings_dp_sequential` vérifie directement. Ce n'est donc pas un
paramètre mort.

🔴 **Mais multiplier le faisceau par cent ne bouge l'offre que de 22 %.** La DP ne rend qu'un
groupement par nombre de blocs à `top_k = 1`, soit 24 — et **250 stratégies sortent quand même**.

> **L'offre est produite par les générateurs de VARIANTES — RATE, SYM, ELITE, fusions — pas par la
> largeur du faisceau de la programmation dynamique.**

**Trois conséquences, et elles ne sont pas petites :**

| | |
|---|---|
| la cellule `dp_top_k = 200` est **retirée** | 240 min pour un levier à 1,22× : non. Le 99c en recherche élargie prend sa place |
| §4quinquies **tient toujours** | l'offre reste ce qui ordonne (ρ = +0,975). Ce qui change est **ce qui fabrique l'offre** : les variantes, pas la DP |
| et le 429 → 2 945 de `×2` s'explique **ailleurs** | `fast` → `extreme` change aussi `phase_a_keep_limit` ×4, `top_k_parents` ×4, `max_fusions_per_parent` ×3, `screening_keep_top_k` ×4 — tous des multiplicateurs de **variantes**. Le contrôle `deep` seul, en tête de campagne, tranchera |

⚠️ **Portée : un composant, le 35c.** 35 couches, 8 nombres de blocs. Sur `×2` (75 couches,
16 nombres de blocs) le rapport pourrait différer. Mais un facteur 1,22× là où j'attendais ≥ 5×
suffit à ne pas dépenser 240 min sur cette hypothèse.

### 🔒 Pourquoi je ne change PAS ses valeurs pour autant

Parce que ce sont **exactement** celles qui ont produit les 254 déposables. Les élargir sur un
raisonnement ferait de `extreme` une configuration que **personne n'a jamais lancée**, et le
fichier d'exemple cesserait de reproduire sa propre mesure — §24-7.

> **`extreme` est un point de fonctionnement MESURÉ, pas un optimum. C'est ce qu'il faut en dire,
> et c'est ce que la documentation en dit désormais.**

📌 **Ce qui le rendrait optimal, dans l'ordre** : (1) le contrôle `deep` seul — nécessité ; (2) un
balayage levier par levier sur les sept — attribution ; (3) un doublement pour trouver la
saturation — dimensionnement. Trois campagnes, aucune conceptuellement difficile.

📌 **Défaut corrigé au passage** : le journal annonçait `[MODE] PREMIUM active` pour **tout** mode
autre que `fast` — un run `deep` était donc journalisé comme premium. Il nomme désormais le mode
réel et ses quatre paramètres de largeur.

### Ce que ça change pour le chantier

| | |
|---|---|
| 🔴 **le tableau de la série est périmé** | *« ×2 échoue »* était vrai à exploration standard uniquement. La série ne mesure donc pas la **faisabilité**, elle mesure **ce que la recherche courante trouve** |
| 🔴 **et ×0,5 doit être rejoué pareil** | il est à 28 % à 1 nm avec la recherche standard. **Si l'élargissement le sauve aussi, la « barrière » de la série s'effondre entièrement** — c'est la mesure la plus importante à faire ensuite |
| 🟠 **le 99c mérite le même traitement** | ses 751 stratégies à 100 % ont toutes été produites par la recherche standard, à 2 nm |
| ✅ **§8 s'applique** | 254 déposables sous un mode non nominal ⇒ rejeu **premium** avant publication |

---

## 4quinquies. 🔴🔴 LE RÉSULTAT CENTRAL — le chantier mesurait la RECHERCHE, pas la physique

📏 **Établi le 2026-08-18.** Cinq points de la série d'échelle, **protocole identique** : `fast`,
fente 2 nm, graine 42, recherche standard. La seule chose qui varie est l'épaisseur optique.

| Σ QWOT | variante | **offertes** | **déposables** | `crash_min` |
|---|---|---|---|---|
| 57,4 | ×0,5 | 375 | 0 | 48 % |
| 114,9 | ×1 | 662 | 241 | 0 % |
| 172,3 | ×1,5 | 440 | 1 | 0 % |
| 201,1 | ×1,75 | 746 | 282 | 0 % |
| 229,8 | ×2 | 404 | 0 | 100 % |

**Corrélation de rang avec le nombre de stratégies déposables :**

```
Somme QWOT -- la propriete du DESIGN         rho = +0,103     rien
OFFERTES   -- ce que la RECHERCHE propose    rho = +0,975     presque parfait
```

> **L'épaisseur optique n'ordonne rien. Le nombre de stratégies que la recherche a proposées
> ordonne presque parfaitement.**

### 🔑 Et la flèche causale est établie, sur un composant

La corrélation seule ne prouverait rien — `offertes` est une **sortie** de la recherche, pas une
entrée, et un design facile produit peut-être naturellement plus de candidates. **La phase 2
tranche le sens** : *même design, même graine, même fente*, seule la largeur de la recherche
change, et ×2 passe de **0 déposable sur 404** à **254 sur 2 945** (§4quater).

C'est une intervention, pas une observation. **Sur ce composant au moins, l'offre est bien une
cause et non un symptôme.**

### 🔴 Ce que ça fait aux quatre sections précédentes

| | |
|---|---|
| **§1** | le tableau fondateur *« échoue / passe / limite / échoue »* ne décrit pas la faisabilité. `×1,5` « marginal » avec 1 déposable est un artefact : `×1,75`, **plus épais**, en rend 282 |
| **§3** | *« aucune grandeur du signal nominal ne prédit l'échec »* — normal. Il n'y avait rien à prédire dans le signal, la variable dominante n'était pas dans le design |
| **§4.1 à §4.5** | les cinq routes fermées cherchaient toutes un prédicteur **du design**. Elles ne pouvaient pas aboutir : elles corrélaient une propriété physique à une grandeur gouvernée par l'exploration |
| **§4bis** | la marge accumulée ordonnait 0 / 5 / 25 — mais elle se lit sur les stratégies **que la recherche a produites**. Même contamination |

### ⚠️ Ce qui n'est PAS établi, et il faut le dire

**1. L'offre ne suffit pas.** 📏 Contre-exemple mesuré : `×2` en **premium** offre **651**
stratégies et rend **0 déposable**, `crash_min` 100 %. Le design compte donc encore — il a fallu
**la fente fine ET l'élargissement** pour débloquer ×2.

**2. Cinq points.** `rho = +0,975` sur cinq points supporte une affirmation ordinale, pas une loi.

**3. Une seule graine, un seul empilement de base.** Toute la série descend du même random75.

**4. Ce n'est pas un prédicteur.** 👤 demandait *« prédire sans tout calculer »*. Connaître le
nombre de stratégies offertes exige de faire tourner la Phase A **et** la Phase B. On a déplacé
la question, on ne l'a pas résolue.

### 🟢 Les deux tests falsifiables lancés le 2026-08-18, critères écrits d'avance

| cellule | thèse CONFIRMÉE si | thèse RÉFUTÉE si |
|---|---|---|
| **×0,5 à 1 nm, élargi** — il échoue vraiment (28 %, 0/375) | l'élargissement rend des déposables | il reste à **0** ⇒ la barrière existe bel et bien du côté mince, et elle est physique |
| **×1,5 à 2 nm, élargi** — 1 déposable sur 440 quand ×1,75 en rend 282 | il passe à des centaines | il reste marginal ⇒ ×1,5 a une singularité propre |

🔑 **Si les deux confirment, la conclusion du chantier change de nature** : il n'y a pas de
« barrière d'épaisseur optique » à prédire, il y a une **recherche à dimensionner**. Et la bonne
question devient *« combien d'exploration ce design exige-t-il ? »*, ce qui est une question
d'ingénierie, pas de physique.

---

## 5. 🔴 LE DÉFAUT QUI FAUSSE TOUTE LA CAMPAGNE — la résolution spectrale n'était pas cherchée

> 👤 **2026-08-17** : *« je me pose aussi la question de la résolution spectrale. Un filtre trop
> épais a des pics en transmission et peut-être que le filtre serait monitorable en résolution
> 1 nm et pas 2 nm. Valable pour les empilements épais. »*

L'intuition est juste, **et le mécanisme existait déjà — il était neutralisé.**

`certus/core/certus_strat_robustness.py:868` :

> 🔴 *« ON BY DEFAULT since 2026-08-12 — 👤 "the slit is systematically searched, it is a
> **PREREQUISITE**". A strategy that does not carry its own slit is not executable in the chamber:
> the operator would have to pick a width the search never evaluated. […] **the historical path is
> `search_resolution: false`** »*

| | |
|---|---|
| `JSON-strat-bandpass-5cav-99c.json` | `search_resolution = 1` — **la config le demande** |
| `mesurer()` de `campagne_intervalles.py` | `search_resolution = False`, **2 nm épinglé** |

🔴 **Toute la campagne des intervalles — et les 751 stratégies — ont tourné sur une machine où
l'opérateur n'a pas le droit de toucher à la fente**, c'est-à-dire le régime que 👤 avait écarté
comme non exécutable en salle.

📏 Mesure du 2026-08-12 citée dans le même docstring : la règle `slit <= res_limit` rejette
**31 % des paires (couche, λ) à 5 nm, 14 % à 2 nm, 2 % à 1 nm, 0,5 % à 0,5 nm**. Passer de 2 à
1 nm **divise le rejet par 7**.

🔑 **Et l'effet intéressant n'est pas le choix à quatre valeurs** : *« the slit changes WHICH
WAVELENGTHS ARE GOOD »*. Une λ en zone lisse tolère 5 nm et encaisse le bonus de bruit **÷1,5** ;
une λ de bord de bande exige 1 nm et paie le **×2**. **C'est un arbitrage, pas un gain gratuit.**

⚠️ **Et aucune des sondes statiques n'applique la convolution par la bande passante du
monochromateur** — `profil_monitorabilite.py` et `probe_distance_extremum.py` calculent le signal
à résolution spectrale **infinie** (grep `slit|resolution` : zéro occurrence). Elles
**surestiment** donc le swing, d'autant plus que l'espacement des oscillations spectrales est serré, c'est-à-dire
d'autant plus que Σ QWOT est grand. **C'est précisément pourquoi l'échec par résolution spectrale
insuffisante leur est invisible.**

**C'est le lead le mieux étayé du chantier au 2026-08-17.** `--fente` est exposée dans
`probe_blocs_vs_plantage.py` (3ᵉ argument, défaut 0 pour préserver la comparabilité), et la sortie
ventile par largeur avec la fente que choisissent les déposables.

📌 **À tester sur ×2, pas sur le 99c** : épais (structures spectrales les plus fines), **non
cas limite** (multiplicateurs jamais entiers), il échoue à 100 %, et ×1,5 lui sert de frère
passant dans la même famille. ⚠️ Avec un **contrôle en premium sans fente** : le `0/404` connu de
×2 a été mesuré en **fast**, donc sans contrôle on attribuerait au slit ce qui vient du mode
(contrainte C3).

---

## 6. Ce qu'il reste à faire, par rendement

### ✅ Fait dans la nuit du 2026-08-17 au 18 — 17 cellules

| | action | résultat |
|---|---|---|
| ✅ | la résolution spectrale, grille complète 4 fentes × 4 échelles | §4ter — **la fente fine est un remède, pas une amélioration** |
| ✅ | la marge accumulée par cause | §4bis — ordonne, mais exige la simulation |
| ✅ | raffiner l'échelle : **×1,75** | §4quinquies — **détruit la lecture monotone** |
| ✅ | deuxième graine sur ×2 à 1 nm | 38 % (g42) contre 30 % (g77) — le résultat tient |
| ✅ | élargir la recherche sur ×2 | §4quater — **254 déposables, SEEL 0,629 nm** |

### 🔴 Ce qui reste, et l'ordre a changé

| # | action | coût | ce que ça décide |
|---|---|---|---|
| **1** | **×0,5 et ×1,5 en recherche ÉLARGIE** | ~5 h | 🔴 **LES DEUX TESTS FALSIFIABLES DE §4quinquies.** Ils décident si la « barrière » existe |
| 2 | **le 99c en recherche élargie**, à 1 nm | ~3 h | ses 751 stratégies à 100 % viennent toutes de la recherche standard, à 2 nm. Le verdict *« non monitorable »* n'a jamais été testé autrement |
| 3 | **rejeu premium** des cellules à déposables | ~2 h | §8 — rien de publiable avant |
| 4 | **de quoi dépend l'OFFRE ?** | à spécifier | si le nombre de stratégies offertes se prédit depuis le design, on tient enfin le prédicteur bon marché — par un chemin que personne n'avait envisagé |
| 5 | seconde graine sur ×1,75 et ×0,5 | ~1,5 h | les deux nouveaux points ne tiennent que sur la graine 42 |

## 7. 🔒 Vocabulaire — nommer la cause, jamais la métaphore

> 👤 **2026-08-17** : *« les termes ne sont pas les bons : murs, bords épais, surveillance ne sont
> pas du jargon scientifique optique / physique / couches minces optiques et on a du mal à
> communiquer. »* Puis : *« impose-toi d'utiliser du vocabulaire précis et adapté
> scientifiquement. »*

Les premières rédactions de ce dossier employaient des métaphores inventées. Elles sont
remplacées par les termes du §14 de `CLAUDE.md` et du code.

| à ne plus écrire | terme correct | source |
|---|---|---|
| « mur », « mur candidat » | 🔒 **pas de nom court — une description**, décidé par 👤 : *« une couche dont la marge reste sous le seuil pour toutes les stratégies évaluées »*. ⚠️ **Ne PAS dire « couche critique »** : le code réserve `critical_layer` à autre chose — la couche qui cède en premier **pour une stratégie donnée** | code + 👤 |
| « bord épais » / « bord mince » | nommer la **cause** : **résolution spectrale insuffisante** · **absence de point tournant exploitable** | — |
| « signature spectrale » | **structure spectrale**, ou **espacement des oscillations spectrales** | — |
| « fente » employé pour la grandeur optique | **résolution spectrale du monochromateur** *(`monochromator_resolution_nm`)*. *Fente* désigne la pièce mécanique | code |
| « le comptage décroche » | **`CRASH_TP_MISCOUNT`** | code |
| « niveau hors d'atteinte » | **`CRASH_LEVEL_UNREACHABLE`** — niveau d'arrêt inatteignable | code |
| « extremum inventé » / « manqué » | **`margin_fabricated`** *(extremum émis par le bruit seul)* · **`margin_missed`** *(swing sous l'hystérésis, extremum non émis)* | code |

⚠️ **À l'inverse, trois termes que j'avais pris pour des approximations sont l'idiome du projet et
ne doivent PAS être « corrigés »** : **surveiller / surveillance** (§14 : *« la λ à laquelle la
machine surveille le dépôt »*), **couche muette** (§21 et les tables de réfutation depuis le
15/08), et **pic** (`COMPOSANTS.md` : *« Pic \| T = 0,9966 »*, le pic de transmission de la bande
passante).

🔴 **Et la précision qui compte le plus n'est pas lexicale, elle est physique : QWOT ≠ point
tournant.** §14 en fait l'erreur la plus coûteuse du projet, et §2 de ce dossier documente le fait
que je l'ai commise. `scripts/check_claude_md.py` la refuse mécaniquement — **mais son contrôle E
ne scanne que `CLAUDE.md`**, donc ce dossier y a échappé. C'est un trou du vérificateur, à combler.

---

## 7bis. 🔒 LA RÈGLE DE MÉTHODE AJOUTÉE LE 2026-08-18 — un chiffre publié doit être RE-DÉRIVABLE

> 👤 : *« il faut être plus rigoureux, tu dois converger vers des interprétations et des
> conclusions solides. Essaie de changer de méthodologie. »*

**La critique était fondée, et le défaut n'était pas l'inattention — c'était l'ordre des
opérations.** En une matinée, quatre affirmations ont été écrites puis retirées :

| affirmation | ce qui l'a tuée |
|---|---|
| *« `deep` rend 0 déposable »* | **non mesuré** — le run à 0 est en `fast` |
| *« la fente fine dégrade ×0,5 »* | la cellule propre dit **28 %** contre 48 %, elle l'améliore |
| *« 50 → 150 tirages »* | `deep` pose **N = 300** |
| *« `strategy_phase_timeout` évite la troncature »* | le paramètre est **inerte** — §24-50 |

Chaque fois j'affirmais depuis une **lecture**, puis je vérifiais après coup. Trois des quatre
avaient atteint la page commerciale.

### Ce qui remplace la relecture : `scripts/verifier_affirmations.py`

Un harnais qui rend `PASS` / `FAIL` / `NON_VERIFIABLE` sur chaque affirmation, et **qui porte son
propre contrôle négatif** : il affirme délibérément une chose fausse (*« `robustness_num_runs`
n'est lu nulle part »*) et **doit** échouer dessus. Un harnais dont tout passe ne prouve rien —
c'est le contrôle 4 du §12, appliqué à moi-même.

**Ce qu'il vérifie, et comment :**

| | méthode |
|---|---|
| un paramètre est-il **lu** ? | **AST**, pas `grep` — un `grep` se fait avoir sur une clé concaténée ou une itération sur une liste de clés |
| un argument de fonction est-il **utilisé** ? | AST du **corps**, indépendamment de la signature |
| la **règle d'or** tient-elle ? | `collect_params` réellement appelé sur les trois modes, 6 valeurs comparées |
| les **noms de fichiers** ne collisionnent-ils pas ? | appel réel de `_sortie`, et l'artefact du niveau 1 doit être **retrouvé** |
| la **formule SEEL** | reproduite sur **deux** repères publiés indépendants |
| les **18 cellules publiées** | offertes, déposables, `crash_min` et SEEL **re-dérivés de l'artefact** |
| un **SEEL de repli** est-il publié ? | rejeté explicitement — c'est ce qui a produit le faux « 0,86 nm » du 99c |

📏 **État au 2026-08-18** : `9 vérifiées · 0 non vérifiables · 0 en échec`, contrôle négatif
compris.

> 🔒 **La règle : un chiffre qui n'est pas re-dérivable par ce script n'a rien à faire dans un
> document.** Et quand une campagne produit de nouveaux artefacts, on ajoute ses chiffres à
> `CHIFFRES_PUBLIES` **en même temps** qu'on les écrit — pas après.

⚠️ **Ce que le harnais ne fait PAS** : il ne relance aucune mesure. Il vérifie des propriétés du
**code** et la cohérence des **artefacts** avec les documents. Une affirmation chiffrée qui n'a
produit aucun artefact ressort `NON_VERIFIABLE` — un troisième état qu'il ne faut pas confondre
avec `PASS`.

---

## 8. Les règles de ce chantier

1. 🔴 **Le 99c n'est pas une référence.** Tout QWOT ⇒ adverse à POEM. Ses conclusions ne se
   généralisent pas, et sa réponse plate à 100 % ne discrimine rien.
2. **Toute grandeur candidate se valide sur la SÉRIE**, pas sur un composant. §22 rappelle qu'un
   signal de marge **changeait de signe** d'un empilement à l'autre.
3. **Jamais un couperet.** Un effet du nombre de blocs, du compte de points tournants ou de la
   fente entre comme **coût**. §24-28 : la règle « celui-là ne gagne jamais » aurait jeté la
   gagnante dans 4 configurations sur 8.
4. **Ne pas viser un binaire.** Sur les cas marginaux la vérité est stochastique — un prédicteur
   binaire y prédirait un tirage. La cible est une **règle de décision avec un taux de faux
   négatifs affiché**, et l'asymétrie compte : dire « un verre suffit » à tort coûte un run, dire
   « prends-en deux » à tort ne coûte qu'un peu de soin.
5. **Deux graines minimum sur tout point marginal**, et trois avant de publier une valeur absolue.
