# 18ter. ⚡ PERFORMANCE — ce qui a été mesuré, positif comme négatif

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


👤 *« Vois-tu un moyen de simplifier quelque chose dans STRAT pour gagner en temps
d'exécution, et que la perte de précision soit négligeable ? »*

📏 **Où passe le temps, mesuré** : part fixe **~730 s** (Phase A + DP), coût marginal
**~1,5 s par tirage** au stade final, soit **~0,15 s par (stratégie × tirage)**. La
Phase A représente donc **68 %** d'un run de référence, et elle est dominée par
`simulate_growth_kernel`. **C'est là qu'il faut chercher, et nulle part ailleurs.**

### 🟢 LA FORME FERMÉE — le gain le plus important, et il vient de 👤

> 👤 *« Est-ce que calculer une dérivée théorique permettrait de gagner du temps ? Je
> sais que c'est possible avec les calculs matriciels. »*

La question mène plus loin qu'une dérivée. Pour la couche en croissance sur un
empilement **déjà déposé**, le dénominateur de la transmission s'écrit
`denom = C·cos δ + i·S·sin δ` avec `C` et `S` **constants**, d'où

$$T(d) \;=\; \frac{4\,n_{\text{sub}}}{P + Q\cos 2\delta + R\sin 2\delta},
\qquad \delta = \frac{2\pi n d}{\lambda}$$

📏 **Vérifié numériquement : écart 5,4e-20**, et **1,2e-15 contre l'ORACLE TMM
INDÉPENDANT** sur 40 empilements de 2 à 20 couches — le même ordre que les chemins de
production. Ce n'est pas une approximation, c'est le même calcul écrit autrement.
`P`, `Q`, `R` se calculent **une fois** depuis la matrice de l'empilement.

🔴 **CORRECTION DU 2026-08-11 : le gain réel est ×1,20, pas ×3,6.** Le ×3,6 avait été
mesuré en **Python pur**, où chaque opération complexe passe par l'interpréteur. Le
noyau est **compilé par numba** : le produit matriciel y est déjà du code machine, et
remplacer huit multiplications complexes par deux appels trigonométriques ne change
presque rien. A/B propre à physique égale (`k = 1e-5` contre `k = 1e-3`) :
`0,276 s` contre `0,331 s`. **Un banc en Python ne prédit pas un noyau compilé** —
c'est le Piège 7 sous une autre forme.

**Et les dérivées suivent gratuitement** :

$$\frac{d^2 D}{d\delta^2} \;=\; -4\,(D - P)$$

🔑 **La dérivée seconde ne coûte aucune évaluation trigonométrique neuve** — elle se
déduit de `D` déjà calculée. Vérifié aux différences finies : exact à toutes les
décimales.

| ce que ça remplace | gain |
|---|---|
| 64 produits matriciels 2×2 complexes par couche | **×3,6** mesuré |
| chercher les points tournants **en balayant** | `tan 2δ = R/Q` — forme fermée |
| chercher l'arrêt **en balayant puis interpolant** | `√(Q²+R²)·cos(2δ−φ) = cste` — forme fermée |
| 3 TMM pour l'inversion parabolique | 1 évaluation + les deux dérivées exactes |
| la courbure du biais de fente (3 TMM par couche) | **analytique** |

#### 🔴 La limite, et la mesure qui la fixe — 👤 a tranché le seuil

La forme suppose `δ` réel, donc **`k = 0`**. 👤 *« Je te propose de limiter le code de
STRAT à des cas où `k < 1e-4`. »*

⚠️ **Mes deux premières mesures de cette limite étaient FAUSSES**, et il faut le dire :
j'utilisais des matrices d'empilement **aléatoires**, dont le dénominateur peut frôler
zéro. `T` explosait, et je mesurais l'erreur sur des valeurs non physiques. J'ai
successivement annoncé « faux dès `k = 1e-3` » puis « faux dès `k = 1e-6` ». Les deux
étaient des artefacts de montage.

📏 **Sur un vrai empilement de 24 couches, en ne retenant que les `T` physiques :**

| `k` | écart max sur `T` | en % du bruit de lecture |
|---|---|---|
| 0 | 5,4e-20 | 0,0 % |
| 1e-6 | 4,2e-10 | 0,0 % |
| **1e-4** | **4,2e-8** | **0,008 %** |
| 1e-3 | 4,1e-7 | 0,1 % |

L'erreur croît **linéairement en `k`** et reste **quatre décades sous le bruit** même à
`k = 1e-3`. **Le seuil de 1e-4 est donc bon, et même généreux** — on le garde pour
laisser une décade de marge, une garde devant protéger des cas qu'on n'a pas testés.

🔴 **Et la garde LÈVE, elle ne se rabat pas en silence** (leçon de §24-25). Quelqu'un qui
lance STRAT sur un métal doit l'apprendre, pas obtenir un chiffre plausible.

🔴 **À valider contre l'oracle TMM indépendant, pas contre le noyau.** L'interdit 7
existe parce que deux bugs de signe se sont cachés dans des réimplémentations, valant
**46 et 82 points** de réflectance — et tous deux étaient **exacts à k = 0**, donc
invisibles à un test qui ne regarde que des diélectriques. C'est exactement ce cas de
figure.

### 🔴 LA FENÊTRE DE BALAYAGE — résultat NÉGATIF, consigné comme tel

> 👤 *« Balayer de zéro à trois fois, cela me paraît énorme ! Aucune couche ne va se
> tromper de plus de 10 nm d'épaisseur, ou alors c'est bon à jeter. »*

📏 **Le constat est juste : 63 % du balayage porte sur des épaisseurs qu'aucune couche
n'atteindra sans être bonne à jeter.** Sur la couche de 253 nm, il balaie jusqu'à
**760 nm**.

🔑 **Et le défaut n'est pas que 3 soit trop grand, c'est la MISE À L'ÉCHELLE.** `D_SCAN`
est un **multiple de l'épaisseur**, alors que les deux besoins d'aller au-delà du
nominal sont **fixes en nanomètres** : l'erreur maximale (👤 10 nm) et la demi-période
optique `λ/4n` — **57,9 nm sur H, 93,2 nm sur L**, indépendantes de l'épaisseur de la
couche. Un multiple est donc trop généreux sur une couche épaisse et potentiellement
**trop court** sur une couche fine : le même paramètre faux dans les deux sens.

🔴 **MAIS LA FENÊTRE ADAPTATIVE NE MARCHE PAS, ET LE DRAPEAU RESTE ÉTEINT.**

| version | vitesse | verdicts de plantage |
|---|---|---|
| `nominal + max(marge, demi-période)` | ×1,9 | **cachait des plantages** |
| `nominal + marge + demi-période` | ×1,17 | **6,3 % discordants** sur 378 cas, écart max **1,4 nm** |

**Ma promesse « à densité constante, physique inchangée » était fausse.** La densité
d'échantillonnage est bien préservée — mais le **test d'atteignabilité** borne sa fenêtre
au **prochain extremum après l'arrêt**, et un balayage plus court n'en contient plus : il
retombe sur la fin du tableau, ce qui est **plus permissif**. Le balayage cachait des
plantages, le pire sens possible pour une erreur.

🔑 **Ce que l'échec apprend, et qui vaut le détour** : le balayage sert à **trois** choses,
pas une — trouver l'arrêt (fenêtre **courte**, échantillonnage **fin**), détecter les
points tournants et borner l'atteignabilité (fenêtre **longue**, densité **indifférente**).
Un balayage à **deux zones** les servirait toutes les trois. ⚠️ Mais c'est bloqué par A8 :
tant que la grille TMM **est** la grille de bruit, un échantillonnage non uniforme donne
une densité de tirages non uniforme, donc un taux de fabrication non uniforme.

### 🔴 TROIS MESURES NÉGATIVES — les pistes de dérivée analytique sont FERMÉES

Elles valent autant que les positives : quelqu'un reproposera chacune des trois.

#### 1. L'inversion parabolique est déjà exacte à 2,1e-10 nm

Le meilleur candidat sur le papier : **3 évaluations TMM par (tirage, couche)**, en pleine
boucle chaude, pour approximer une courbe qu'on connaît désormais exactement.

📏 **Écart maximal de la parabole à la solution exacte, sur 200 empilements aléatoires de
4 à 30 couches : `2,083e-10 nm`.** Le seuil sous lequel un écart d'épaisseur n'a aucun
sens physique est **0,05 nm** — moins d'un atome (§8). **La parabole est 240 millions de
fois sous ce seuil.**

🔑 **Et ça éclaire un chiffre du §29.1.** L'invariance de POEM y était mesurée à
**2,19e-10 nm** — le même ordre, exactement. **Ce n'était pas la limite de POEM qu'on
mesurait, c'était celle de la parabole.** Et elle est sans conséquence.

Gain en vitesse : 3 points sur ~130 par couche, soit **~2 %**. Gain en exactitude :
**nul en pratique**. ❌ Fermé.

#### 2. `dT/dd` analytique — hors de la boucle chaude, et déplacerait tous les chiffres

`compute_dT_dd_kernel` fait une différence centrée, 2 évaluations par couche, dans
`_compute_dT_dd_per_layer` — appelé **une fois par stratégie, pas par tirage**. Son erreur
est en `O(h²)`, négligeable devant le bruit qu'elle sert justement à dimensionner
(`signal_noise_scale = |dT_dd| · noise_val`).

La rendre analytique **changerait `signal_noise_scale`, donc tous les résultats**, pour un
gain nul des deux côtés. ❌ Fermé.

#### 3. 🔴 Les points tournants NE PEUVENT PAS être résolus analytiquement — et c'est structurel

C'est l'argument le plus important des trois, parce qu'il ne se voit pas.

Le bruit est ajouté à `Ts_r` (`certus_strat_growth.py:886` et `:996`), et
`detect_turning_points` opère **sur `Ts_r`**, donc sur des données **bruitées**. Ce n'est
pas un chercheur d'extremum : c'est une **machine à hystérésis** qui émet quand le signal
recule de plus qu'un seuil. Elle modélise ce que l'instrument **croit voir**, pas ce que
la courbe **est**.

> `tan 2δ = R/Q` donne l'extremum **mathématique de la courbe propre**.
> Le détecteur donne ce que **la machine voit dans un signal bruité**.
> **L'écart entre les deux EST le phénomène** que §29.2 a mis trois mesures à caractériser.

Le remplacer par une résolution analytique **supprimerait purement et simplement la
fabrication de faux points tournants** — le mécanisme de plantage dominant, **79 %** des
échecs mesurés en §24-36. ❌ Fermé, définitivement.

#### Ce qu'il faut retenir de l'ensemble

**La forme fermée est une belle découverte qui ne rapporte presque rien**, parce que le
code qu'elle remplacerait était déjà bon : la parabole est exacte à 2e-10, la différence
centrée est sous le bruit, et le détecteur est irremplaçable par construction du modèle.

Ce qui reste acquis : **×1,20** sur le noyau, une forme fermée validée à **1,2e-15**
contre l'oracle indépendant, et la restriction 👤 `k < 1e-4` mesurée et confirmée.

### ⚡ LÀ OÙ LE TEMPS SE GAGNE VRAIMENT — et c'est déjà mesuré

📏 **D3 de la campagne du 2026-08-11** : cribler à **10 tirages au lieu de 25** rend
`n_ranked = 133` au lieu de 228, **la même gagnante** `[544, 531]`, et un `RESULT`
**bit-identique**. Ouvrir à 100 tirages ou garder 30 survivantes ne trouve rien de mieux
non plus (§24-27).

**C'est 60 % de l'étage de criblage, sans toucher une ligne de physique, et avec une
preuve expérimentale plutôt qu'une estimation.** Plus que tout ce que le noyau peut rendre.

⚠️ **Mais je ne change pas le défaut, et c'est délibéré.** La mesure porte sur **une
graine, un empilement, une configuration**. §11-4 interdit de conclure d'une mesure sur un
autre composant, et un défaut vaut pour tous les cas à venir, pas seulement pour celui-là.
`n_screen_runs = 10` est **recommandé et documenté** ; le poser par défaut demande de
l'avoir vu tenir sur au moins une seconde graine.


### La simple précision — 👤 y est favorable, et l'ordre compte

> 👤 *« Je suis favorable à ce que les calculs les plus coûteux en temps soient
> spécifiquement faits en simple précision. »*

**Ce qui la rend défendable** : la grandeur porte un bruit de `A = 5e-4`. L'erreur
relative du `float32` est ~1e-7, soit **5e-8 en absolu** sur des `T ~ 0,5` — quatre
décades sous le bruit. Même accumulée sur 48 produits matriciels, on resterait vers 1e-6.

**Ce qu'elle coûte, et il faut le savoir** : la vérification **au bit** devient
impossible (C1 et §9 reposent sur `float.hex()`), et l'oracle TMM chute de **3,3e-16 à
~1e-7** — quatre décades de sensibilité en moins, sur l'instrument même qui a démasqué
les deux bugs de signe.

⚠️ **Recommandation : sur le chemin de MONITORING seulement**, jamais sur la notation ni
sur l'oracle. Et **après** la forme fermée, jamais en même temps : la forme fermée change
ce qui est le goulot, et deux changements simultanés rendraient l'attribution impossible
(contrainte C3). Une fois la forme fermée en place, le calcul n'est plus dominé par des
produits matriciels mais par de la trigonométrie, et il faudra **remesurer** où va le
### 17-43. Découverte & validation des stratégies par blocs (6 blocs universels sur 35c et 48c)

📏 **Mesuré le 2026-08-14** : le regroupement de la surveillance optique en **6 blocs** bat
invariablement la surveillance monocouche historique ($N$ longueurs d'onde pour $N$ couches)
sur les deux composants de référence, avec un **taux de plantage nul ($0{,}0\,\%$)** :

| Composant | Stratégie Monocouche ($N$ blocs) | Champion 6 Blocs | Gain Précision | Mouvements Monochromateur |
|---|:---:|:---:|:---:|:---:|
| **48c Dichroïque** | RMSE = `0.01803` ($\text{SEEL} = 0{,}27\text{ nm}$) | **RMSE = `0.00745` ($\text{SEEL} = 0{,}17\text{ nm}$)** | **$+58{,}7\,\%$** | $5$ au lieu de $47$ ($-89\,\%$) |
| **35c Passe-Bande** | RMSE = `0.08496` ($\text{SEEL} = 0{,}58\text{ nm}$) | **RMSE = `0.05819` ($\text{SEEL} = 0{,}48\text{ nm}$)** | **$+31{,}5\,\%$** | $5$ au lieu de $34$ ($-85\,\%$) |

**Mécanisme physique fondamental :**
1. **Mémoire de phase POEM** : le maintien de la même longueur d'onde sur 5 à 8 couches consécutives
   permet à POEM d'utiliser les extremums précédents comme repères absolus de phase pour corriger en
   direct les incertitudes d'indice et les dérives de vitesse sans discontinuité.
2. **Cumul des pentes** : les couches quart-d'onde à dérivée faible sont amplifiées par l'interférence
   globale du sous-empilement.

---

### 17-46. Benchmark consolidé des 3 Modes d'Exécution (FAST, PREMIUM, DEEP) & SEEL à 0,01 nm

📏 **Mesuré le 2026-08-14** sur le banc headless de référence :

```
================================================================================
TABLEAU RÉCAPITULATIF DES 3 MODES SUR 35C ET 48C (SEEL RÉSOLUTION 0,01 NM)
================================================================================
Composant          Mode       Budget MC & Largeur    Durée   Optimum   RMSE P95   SEEL (0,01nm)   Plantage   Total Stratégies
48c (Dichroïque)   FAST       N=50, top_k=20        371 s    6 blocs   0.00745       0,17 nm        0,0 %          384
48c (Dichroïque)   PREMIUM    N=150, top_k=40       570 s    6 blocs   0.00764       0,17 nm        0,0 %          650
48c (Dichroïque)   DEEP       N=300, top_k=100      965 s    6 blocs   0.00746       0,17 nm        0,0 %          848

35c (Passe-bande)  FAST       N=50, top_k=20        166 s    5 blocs   0.06893       0,53 nm        0,0 %          298
35c (Passe-bande)  PREMIUM    N=150, top_k=40       248 s    5 blocs   0.06201       0,50 nm        0,0 %          519
35c (Passe-bande)  DEEP       N=300, top_k=100      431 s    6 blocs   0.05819       0,48 nm        0,0 %         1007
```

**Règles de calcul du SEEL :**
- Formule : $\text{SEEL} = 2 \times \sqrt{\text{score}}$
- Résolution standard : **$0{,}01\text{ nm}$ près** (`SEEL_RESOLUTION_NM = 0.005` dans `certus_strat_ranking.py`).
