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

| facteur | **Σ QWOT** | **ép. OPTIQUE** | QWOT par couche | couches < 1 QWOT | verdict | déposables | `crash_min` | SEEL |
|---|---|---|---|---|---|---|---|---|
| **×0,5** | **57,4** | 9,09 µm | 0,252 – 1,240 | **59** | 🔴 échoue | 0/375 | **48 %** | — |
| **×1** | **114,9** | 18,18 µm | 0,504 – 2,479 | — | 🟢 **passe** | 241/662 | 0 % | **0,272 nm** |
| **×1,5** | **172,3** | 27,27 µm | 0,756 – 3,719 | 3 | 🟠 limite | **1/704** | 0 % | **0,63 nm** |
| **×2** | **229,8** | 36,36 µm | 1,008 – 4,958 | **0** | 🔴 échoue | 0/404 | **100 %** | — |

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

| # | action | coût | ce que ça donne |
|---|---|---|---|
| 1 | **`search_resolution` sur ×2**, avec contrôle sans fente | ~2 h | la thèse de 👤, testée là où elle a un sens |
| 2 | **`margin_by_layer` par cause sur ×0,5 et ×2** | ~1 h | le mécanisme à deux bords **mesuré**, pas supposé |
| 3 | **la marge sur trajectoire ACCUMULÉE** | instrumentation | la seule route restante vers une impossibilité |
| 4 | **raffiner l'échelle** : ×0,75, ×1,25, ×1,75 | ~1,5 h | localise les **deux** frontières |
| 5 | **deuxième graine sur ×0,5 et ×1,5** | ~1 h | les deux points marginaux ne tiennent pas sur une graine |

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
