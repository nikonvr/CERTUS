# 12. Le travail à venir, dans l'ordre

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


> 🔴 **LIS CE TABLEAU AVANT LES 700 LIGNES QUI SUIVENT.** Cette section a été écrite comme
> une liste de travail à faire ; **l'essentiel est fait**, et ce qui suit est surtout la
> physique et les pièges qui restent, pas un ordre de mission. **Ne redémarre pas une action
> marquée ACQUISE.**

| | État au 2026-08-14 | Ce qui reste vraiment |
|---|---|---|
| **12.1** distorsion affine, épreuve de POEM | ✅ **ACQUISE et dépassée.** Protection ×15 à ×17,5 mesurée sur deux graines (A12). `poem_enabled` et les amplitudes affines **existent** dans les signatures. | Rien. ⚠️ Mais lis « la dérive n'est pas affine » ci-dessous : elle **requalifie** ce résultat. |
| **La forme de la dérive photométrique** | ✅ **TRANCHÉE le 2026-08-12** : $\delta T = 4\varepsilon T(1-T)$, pas affine. C'est le bloc le plus important de §29. | L'amplitude $\varepsilon$ reste une **spécification 👤**, pas une mesure. |
| **12.2** lissage de lecture | 🟠 modèle posé, **et son seuil dérivé est RÉFUTÉ** : `0,354` est faux, la mesure dit **`1,00 A`**. | Le lissage exige la grille de 12.4. `machine_sampling_dd` existe et vaut 0 (A8). |
| **12.3** méconnaissance d'indice | ✅ **ACQUISE.** ±0,005, corridor tranché le 2026-08-10, normalisation sur l'enveloppe. | Rien. |
| **12.4** grille à la cadence machine | 🟠 le paramètre existe, dé-soudé du lissage (A8), **et vaut 0 par défaut**. | Trancher 1 nm contre 2 nm — c'est §33, avec son critère posé d'avance. |
| **12.5** quantification du déclenchement | ✅ **ACQUISE.** `U(0 ; 0,125 nm)`, et elle apparaît toute seule dans l'arrondi du Rate. | Rien. |
| **12.7** résolution du monochromateur | 🟠 **le biais de fente est actif par défaut depuis le 2026-08-11** et la fente fait partie de la stratégie. | 🔴 **Le facteur √3 n'est pas corrigé** : la fente est rectangulaire, la formule en production est trop stricte de 1,73×. |
| **12.6** face arrière | ⚪ non fait, et il est écrit « en dernier, ou jamais ». | — |

> **Ce qui suit garde sa valeur pour deux raisons, et deux seulement** : la **physique** y est
> établie et ne se retrouve nulle part ailleurs, et les **pièges** y sont nommés. Le déroulé
> des délibérations, lui, est dans `git log`.

> **Les trois contraintes ci-dessous s'appliquent encore à toute action**, faite ou non.

### Les trois contraintes qui s'appliquent à TOUTES les actions

**C1 — Inactif par défaut, bit-identique.** Tout nouveau paramètre vaut sa valeur neutre par
défaut, et le chemin neutre doit rendre **exactement** les mêmes bits qu'avant. Vérifié par
empreinte `float.hex()` sur une large batterie de configurations, avant/après — pas « aux
tests près ». Voir §9.

**C2 — Nombres aléatoires communs.** Tout tirage aléatoire est une **fonction pure de
(graine, tirage, et un index physique)**. Jamais de la stratégie : ni la longueur d'onde, ni
le découpage en blocs, ni `block_start_layer`, ni une épaisseur *obtenue*. Deux stratégies
comparées sur le même (graine, tirage) doivent voir **exactement le même aléa**, sinon leur
écart de score n'est plus imputable à la stratégie. Le générateur à utiliser est
`_seeded_noise_sample(seed_base, group_idx, run_idx, elem_idx, gaussian)`
(`certus/physics/certus_strat_math.py:384`) — loi tronquée sur [−1, 1], σ = 1/3.

**C3 — Une seule chose à la fois.** Si deux choses changent et que le résultat bouge,
l'attribution est perdue — pour toi et pour tous ceux qui suivront.

---

### 12.1 ✅ L'épreuve de POEM — ACQUISE, et ce qu'il faut en retenir

C'était la seule action pouvant **invalider POEM**, le mécanisme central de STRAT. Elle a été
faite les 10 et 12 août. Trois choses en restent, et rien d'autre.

**1. La protection est réelle et reproductible : ×15 à ×17,5**, mesurée sur deux graines
(A12 du tableau des acquis). 🔴 **Cite la protection, jamais le dommage résiduel** : la
distorsion coûte +0,9 % à la graine 42 et +98 % à la graine 77 — la 42 était un tirage
chanceux, et « +0,87 % » ne doit pas ressortir.

**2. POEM protège même sans aucune distorsion : ×1,975.** Il ne compense donc pas seulement
la dérive photométrique, mais aussi **les erreurs d'épaisseur accumulées**. 🔑 C'est la part
de POEM qui **ne dépend d'aucune hypothèse photométrique**, donc la seule qui survive à la
requalification du bloc suivant. C'est elle qu'il faut citer par défaut.

**3. 🔑 Un mécanisme d'invariance peut s'auto-annuler, et ça ne se voit pas.** Le noyau
annulait son propre effet en **trois** endroits à la fois — inversion parabolique résolue en
unités mélangées, repli absolu qui rendait l'étalonnage perdu, test de swing mis à l'échelle
par le gain. Chacun rendait des nombres plausibles, et ensemble ils auraient fait conclure
**l'inverse de la vérité**. Avant de mesurer une invariance, vérifie que le code ne la
fabrique pas.

⚠️ Portée : `RESULT`, agrégat sur trois niveaux de bruit, sur le seul 48 couches. §26 reste
entier — banc de cohérence, pas validation physique.

#### 🔑 POEM ne réduit pas seulement l'erreur — il change OÙ elle tombe

📏 Profil par bande, `scripts\analyse_bands.py` (2026-08-10, sur les runs déjà au disque,
zéro temps de banc) :

| run | passante | front | **front/passante** |
|---|---|---|---|
| POEM actif, distorsion | 0,002205 | 0,005618 | **2,55** |
| **POEM coupé, distorsion** | **0,042351** | 0,003780 | **0,09** |
| POEM coupé, corridor 0,005 | 0,470535 | 0,378305 | 0,80 |

Avec POEM, l'erreur est **concentrée sur le front** — un décalage de bord. Sans POEM, elle
**inonde la bande passante**, où elle devient de l'ondulation. **Le mode de défaillance
change de nature, pas seulement d'amplitude.**

#### Pièges connus

- 🔴 **Il n'existe pas aujourd'hui de drapeau « désactiver POEM ».** `poem_ok` est décidé
  dans le noyau par `SWING_MIN` et le comptage d'ancres. Le critère de réussite exige de
  pouvoir forcer le repli absolu. Ajouter un paramètre `poem_enabled: bool = True` au noyau
  — inactif par défaut au sens de C1, puisque `True` est le comportement actuel.
- ⚠️ `tp_hysteresis` reste **asymétrique** sous distorsion : `Ts_r` est mis à l'échelle,
  `Ts_n` ne l'est pas, et les deux reçoivent le même seuil **absolu**. Une chute de gain
  rétrécit donc les ondulations réelles face à un seuil fixe et peut fabriquer des
  `CRASH_TP_MISCOUNT`. **Séparer les deux sentinelles dans le rapport** (`int(val // 1e6)`
  donne la cause) pour ne pas confondre cet effet avec le vrai.
- ⚠️ Le bruit `noise_val_precalc` est ajouté à `target_level`, qui est en unités mesurées
  dans la branche POEM et en unités vraies dans le repli. Effet du second ordre, non mesuré.

---

### 🔴 LA DÉRIVE PHOTOMÉTRIQUE N'EST PAS AFFINE — 👤 2026-08-12

> 👤 *« La dérive photométrique a-t-elle un sens sachant que le vide et le noir sont mesurés
> à chaque fois ? »* — puis *« à mon avis cette dérive est maximale si T est proche de 0,5,
> mais sûrement pas de 1 ou de 0. »*

#### Ce que l'auto-référencement retire, et il retire presque tout

`T = (S − D)/(V − D)`, refait **à chaque tour**, quatre fois par seconde (§17). Donc :

- un **gain** commun aux trois positions disparaît exactement :
  `(gS − gD)/(gV − gD) = (S − D)/(V − D)` ;
- un **offset d'obscurité** disparaît par la soustraction du noir ;
- tout ce qui est commun au chemin — lampe, détecteur, électronique — est annulé, et
  annulé **250 ms plus tard**, bien avant d'avoir dérivé.

Un dépôt dure des heures ; la référence se refait quatre fois par seconde. **Le modèle
affine — un gain et un offset tirés une fois par run — est donc très largement éliminé par
la machine elle-même.**

#### 🔑 Et ce qui reste est CLOUÉ AUX DEUX BOUTS

C'est le point, et il est imposé, pas choisi :

| | |
|---|---|
| `T = 0` ⟺ `S = D` | numérateur nul ⇒ `T = 0` **quelle que soit** la dérive multiplicative |
| `T = 1` ⟺ `S = V` | numérateur = dénominateur ⇒ `T = 1`, idem |

**Les deux extrémités de l'échelle sont les deux ancres de la mesure.** L'erreur résiduelle
y est donc nulle par construction, et libre entre les deux.

🔴 **`a·T + b` est la mauvaise forme** : il vaut `b` en 0 et `a + b` en 1, c'est-à-dire qu'il
met de l'erreur **exactement là où l'instrument est le plus exact**.

#### La forme retenue

$$\delta T \;=\; 4\,\varepsilon\,T\,(1-T)$$

nulle aux deux bouts, maximale à `T = 0,5` où elle vaut `ε`. Elle a un mécanisme :
une **non-linéarité du détecteur**, réponse `Φ + κΦ²`, survit au rapport de différences
précisément comme ce terme du second ordre.

🔒 **Amplitude** : à `T = 0,5` la vraie valeur est entre **0,4975 et 0,5025**, bornes à
2 σ. Le tirage borné du projet a `σ = A/3`, donc `2σ = 2A/3 = 2,5e-3` fixe
**`A = 3,75e-3`** — `PHOTOMETRIC_CURVATURE_AMP`.
⚠️ 👤 a **révisé cette valeur d'un facteur 2 vers le bas** le jour même : *« je pense que
j'ai surestimé d'un facteur 2 l'erreur en epsilon à T = 0,5 »*. Tous les chiffres cités
contre l'ancienne valeur ont été **remesurés**, jamais divisés par deux — la réponse
n'est pas linéaire en ε. Tirée **une fois par dépôt**, groupe 2 du
flux affine, distinct des groupes 0 et 1 : trois imperfections indépendantes ne partagent
pas un tirage.

#### 🔴 CE QUE ÇA CHANGE, ET C'EST ÉNORME

📏 Mesuré au noyau, arrêt d'une couche de 53,19 nm sous POEM avec ancres :

| perturbation | déplacement de l'arrêt |
|---|---|
| **affine**, gain 5 % | **−8,6e-12 nm** |
| **affine**, offset 0,02 | **−4,2e-11 nm** |
| **courbure**, ε = 0,00375 | **−0,667 nm** |
| courbure, ε = 0,0075 | −1,28 nm |
| courbure, ε = 0,05 | −6,11 nm |

**Facteur 1,6×10¹⁰ entre l'ancienne perturbation et la nouvelle.** 0,667 nm sur 53, soit
1,3 %, et **treize fois** le seuil de 0,05 nm sous lequel §8 interdit de conclure.

📏 Et sur les 48 couches à 544 nm, l'erreur de **niveau** qu'elle induit vaut **0,15 A en
médiane**, **1,89 A au pire** (couche 6) ; **4 couches sur 48** dépassent 1 A et **aucune**
ne dépasse 2 A. Le swing médian valant 0,140, l'effet est donc modeste sur la couche
typique — mais c'est un **biais**, qui ne s'annule pas sur les tirages, là où `A` est du
bruit qui s'annule.

La raison est le théorème de §12.1 : **POEM est rigoureusement invariant par transformation
affine.** La perturbation modélisée jusqu'ici était donc, très exactement, la seule forme
que le mécanisme absorbe gratuitement. `T(1−T)` n'est pas affine — POEM ne l'absorbe pas.

⚠️ **Le ×41,2 de POEM est donc à requalifier.** Il n'est pas faux : il mesure la protection
contre une perturbation qui, d'une part, est largement retirée par l'auto-référencement, et
d'autre part serait de toute façon absorbée. **Ce qui survit de POEM, et qui ne dépend
d'aucune hypothèse photométrique**, c'est le ×2,43 mesuré *sans aucune distorsion* : la
compensation des erreurs d'épaisseur accumulées.

#### 🔴 LE MOTIF, ET C'EST LA DEUXIÈME FOIS LE MÊME JOUR

Le matin, le biais de fente était modélisé comme **une constante par couche** — et une
constante est le `b` de l'affine, donc la forme que POEM absorbe. L'après-midi, la dérive
photométrique était modélisée comme **affine** — la forme que POEM absorbe.

> **Le défaut n'était pas dans les chiffres. Il était dans le CHOIX DE LA FORME de la
> perturbation, et à chaque fois on avait choisi celle contre laquelle le mécanisme est
> immunisé.**

C'est un piège de méthode à part entière, et il ne se voit pas : les deux modèles rendaient
des nombres parfaitement plausibles. **Quand on teste un mécanisme d'invariance, il faut
d'abord se demander si la perturbation choisie appartient au groupe qu'il annule.**

#### Ce qui reste ouvert

- **L'amplitude `ε` est une spécification 👤, pas une mesure.** Comme la table des facteurs
  de bruit de §12.7, toute conclusion qui en dépend doit survivre à son incertitude.
- **Le voilage des fenêtres** n'est pas couvert. S'il n'affecte que le trajet témoin, il ne
  s'annule pas et produit un vrai gain lentement variable — auquel cas l'affine retrouverait
  un sens **en plus** de la courbure. C'est une question de géométrie du bâti.
- **La non-linéarité du détecteur** est le mécanisme invoqué, pas un mécanisme mesuré.

⚠️ **L'affine reste dans le code, amplitudes à 0.** Ce n'est plus un modèle de la machine :
c'est **l'instrument qui teste le théorème d'invariance** de §12.1, et il garde cette
valeur-là.

---

### 12.2 🔴 Modéliser le LISSAGE de lecture — et surtout pas remonter le seuil

> **Cette action applique le modèle figé du §18.** Ne le rediscute pas : l'OMS est breveté,
> son fonctionnement interne restera opaque, et le postulat a été arrêté le 2026-08-08 pour
> clore la question. La fenêtre à utiliser est **`k = 8`**.
>
> 🔴 **NE PRENDS PAS LE SEUIL DE `0,354 A` ÉCRIT PLUS BAS. IL EST RÉFUTÉ.** C'était une
> **dérivation** — `3σ/A = 1/√k` — et elle suppose des échantillons indépendants, alors que
> deux moyennes glissantes voisines partagent 7 lectures sur 8. La borne **mesurée** vaut
> **`1,00 A`** à `k = 8`, `N = 800` (§18, postulat 4, 2026-08-10) : **un facteur 2,8
> au-dessus de la dérivation**. Le raisonnement qui suit est conservé parce qu'il explique
> *pourquoi* le seuil descend au lieu de monter — mais **son chiffre est faux**, et c'est le
> troisième cas de ce document où un raisonnement sur le bruit a été démenti par la mesure.

**2 s à 4 lectures/s ⇒ fenêtre de `k = 8` lectures**, soit 1 nm de dépôt à 0,5 nm/s.

#### Le constat qui a mené à ces réponses

Le modèle compare aujourd'hui des lectures **brutes**. Le docstring de
`detect_turning_points` énonce alors sa condition de suffisance : le tirage étant borné à
±A, l'écart maximal du bruit seul vaut 2A, donc `hysteresis ≥ 2·trigger_tolerance/100`
= 1,0e-3. Or `certus_strat_robustness.py:854` calcule `1,66 × 5e-4` = 8,3e-4.

📏 Mesuré — signal propre **plat**, bruit réel, 20 000 tirages, aucun TMM. Fraction des
couches où le bruit **fabrique** un point tournant :

```
hysteresis                      N=80 (modele actuel)      N=320      N=800 (cadence machine)
1.66 A  (configure = 5 sigma)                32.945%    92.995%                      99.935%
2.00 A  (borne, 6 sigma)                      0.480%     7.660%                      30.525%
2.40 A  (7.2 sigma)                           0.000%     0.000%                       0.000%

Controle Piege 1 : bruit x0.50 a N=800, seuil 1.66 A  ->  0.000%
```

Le résidu à 2,00 A n'est pas physique : c'est l'atome de probabilité à l'écrêtage ±1 du
tirage, où `maxv − v` vaut 2A à l'arrondi près et le `>` strict devient un pile ou face en
flottant. Prédiction du mécanisme à N=80 : 0,5 %. Mesuré : 0,48 %.

**Sur des lectures brutes, un seuil à 3 σ est intenable** : le tremblement fait 6 σ de large,
donc une lecture haute suivie d'une lecture basse le franchit à elle seule. **Mais la machine
ne lit pas brut.** C'est le modèle qui est infidèle, pas le seuil.

#### Le modèle correct, et le chiffre qu'il donne

Lisser le signal **avant** la détection, et garder 3 σ **du signal lissé**.

Le lissage agit sur deux fronts, et le second domine :

1. **Amplitude** — moyenner `k` lectures divise l'écart-type par `√k`. À `k = 8`, le
   tremblement passe de 0,10 à 0,035 point.
2. **Corrélation** — deux moyennes glissantes voisines partagent 7 lectures sur 8 et ne
   peuvent donc pas s'écarter brutalement. Fabriquer une fausse inversion exigerait un
   basculement **cohérent** du bruit sur toute la fenêtre, bien plus rare qu'une lecture
   haute suivie d'une lecture basse.

**Le seuil DESCEND, il ne monte pas.** En gardant `tp_hysteresis_factor` exprimé en multiples
de l'amplitude brute A, le critère « 3 σ du signal lissé » s'écrit :

$$\text{tp\_hysteresis\_factor} \;=\; \frac{3\,\sigma_{\text{lissé}}}{A} \;=\; \frac{3}{3\sqrt{k}} \;=\; \frac{1}{\sqrt{k}}
\qquad \Rightarrow \qquad k = 8 \;\Rightarrow\; \mathbf{0{,}354}$$

Contre 1,66 aujourd'hui : **4,7× plus bas**, sur un signal 2,8× plus calme. C'est meilleur
sur les deux tableaux — moins de faux points tournants **et** meilleure détection des vrais
extrema peu marqués, qui est la face du problème jamais mesurée.

🔴 **CE 0,354 A ÉTÉ MESURÉ, ET IL EST FAUX.** La dérivation supposait des échantillons
indépendants ; les moyennes glissantes voisines partagent 7 lectures sur 8. Mesuré le
2026-08-10 à `k = 8`, `N = 800` : la borne anti-fabrication vaut **`1,00 A`**, soit
**2,8 fois** la dérivation. **C'est `1,00` qu'on utilise** (§18, postulat 4, et A1/A2 du
tableau des acquis). Ce qui reste vrai du raisonnement ci-dessus : le seuil **descend** avec
le lissage au lieu de monter, et pour les deux raisons données. Seul le chiffre était faux.

#### Le retard : rien à ajouter, le noyau fait déjà bien

👤 Le logiciel anticipe la valeur de trigger, donc le lissage n'introduit pas de retard sur
l'arrêt. **Le noyau est déjà conforme, à deux endroits, et il ne faut pas le « corriger » :**

- l'arrêt est obtenu par **inversion parabolique exacte** de `T(d) = cible` — c'est
  précisément un déclenchement anticipé, sans retard ;
- `detect_turning_points` rend **l'indice de l'extremum lui-même**, pas celui de l'instant où
  le seuil a été franchi. Son docstring le dit : *« la machine enregistre la valeur extrême
  qu'elle a observée, pas le moment où elle a réalisé l'avoir dépassée »*.

**Donc : modéliser le lissage pour son effet sur le BRUIT uniquement. N'ajouter aucun
décalage temporel.**

#### 🔴 Le lissage EXIGE la grille de §12.4 — ne pas l'implémenter avant

La fenêtre se compte **en lectures machine**. Le modèle échantillonne aujourd'hui 21 points
par couche là où la machine en prend 800 : une moyenne sur 8 lectures n'y a **aucun sens**.

Les deux actions se compensent comme dans la réalité : **raffiner la grille seule fait
exploser les faux points tournants** (33 % → 99,9 %) ; la raffiner **avec** le lissage
reproduit ce que la machine fait. **Faire §12.4 d'abord, ou les deux ensemble.**

#### La règle de sélection des λ — réglage distinct, à ne pas confondre

`phase_a_level_margin_factor` exige une distance minimale, **en transmission**, entre le
niveau d'arrêt et le point tournant le plus proche. Ce n'est pas une règle de lecture : c'est
un filtre sur les λ candidates.

| | en σ | en points | statut |
|---|---|---|---|
| Valeur actuelle | 5 σ | 0,083 | |
| 👤 Fourchette voulue | 5 à 10 σ | 0,083 à 0,167 | **tester 10 σ = 3,33** |

Monter à 10 σ restreint le choix de λ mais élargit la marge de sécurité. À mesurer au banc,
**séparément** du lissage (contrainte C3).

⚠️ Ces σ-là portent sur le bruit **brut**, pas lissé : c'est une marge de sécurité sur le
niveau visé, pas une règle de lecture. Ne pas leur appliquer le `1/√k`.

#### Pièges connus

- 🔴 **Un run par configuration, machine libre**, et `CERTUS_BENCH_TIMEOUT_S=5400`. Voir §21.
- ⚠️ `tp_hysteresis_factor` et le lissage sont **liés par `1/√k`** : ne pas les bouger
  indépendamment. Figer `k`, dériver le seuil, ne faire varier que `k`.
- ⚠️ Le postulat du §18 est **figé**. Si une mesure le contredit — et une mesure seulement,
  pas un raisonnement — c'est le §18 qu'on rouvre, pas cette action qu'on bricole.

---

### 12.3 Méconnaissance d'indice — 👤 spécification du 2026-08-08

**Ce que le physicien décrit, mot pour mot.** Les indices sont **présupposés**, connus à
**±0,005** près. Ce sont **vraiment les mêmes** pour toutes les couches paires, et les mêmes
pour toutes les impaires — **aucune variation pendant le dépôt**. Mais ce n'est **pas**
±0,005 indépendamment à chaque λ : c'est une **courbe de dispersion** qui peut être
**décalée**, ou **croisée** (pentes différentes), à l'intérieur d'un **corridor de 0,005 sur
tout le domaine spectral**. Et **les courbes restent lisses.**

#### Le modèle qui en découle

Une perturbation **affine en λ**, tirée **une fois par run et par matériau** — pas par
couche, pas par longueur d'onde :

$$\delta_M(\lambda) \;=\; a_M \;+\; b_M \cdot u(\lambda), \qquad
u(\lambda) = \frac{2\lambda - (\lambda_{\min}+\lambda_{\max})}{\lambda_{\max}-\lambda_{\min}} \in [-1, 1]$$

$$n_M^{\text{réel}}(\lambda) \;=\; n_M^{\text{nom}}(\lambda) + \delta_M(\lambda),
\qquad |a_M| + |b_M| \le \delta_{\max} = 0{,}005$$

- `b = 0` → **décalage pur**, la courbe entière est translatée.
- `a = 0` → **croisement pur**, la courbe coupe la nominale au milieu du domaine : c'est le
  cas « pentes différentes ».
- La contrainte `|a| + |b| ≤ δ_max` garantit le corridor **partout**, et l'affinité garantit
  la douceur. Un terme quadratique n'est pas nécessaire : le physicien nomme deux modes,
  décalage et croisement, et l'affine les couvre exactement.

**Tirage borné, cohérent avec le reste du projet** (contrainte C2) :

```python
z1 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 0, True)   # in [-1, 1]
z2 = _seeded_noise_sample(index_stream_seed, mat_idx, run_idx, 1, True)
a_M = delta_max * z1
b_M = delta_max * z2 * (1.0 - abs(z1))     # garantit |a| + |b| <= delta_max
```

`mat_idx` vaut 0 pour H, 1 pour L — **deux tirages indépendants**, les deux matériaux n'ont
aucune raison de dériver ensemble. Nouvelle clé JSON `index_corridor` (défaut **0,0**).

#### Pourquoi décalage et croisement ne coûtent pas la même chose

Le monitoring corrige l'épaisseur optique à **une seule** longueur d'onde, λ_mon.

- Une courbe **décalée** l'est identiquement partout : la correction faite à λ_mon vaut à
  peu près pour tout le domaine. Largement compensable.
- Une courbe **croisée** porte une erreur de **signe opposé** de part et d'autre du
  croisement : la correction faite à λ_mon **aggrave** l'erreur de l'autre côté. Non
  compensable par construction.

**Prédiction à mesurer, pas un acquis** : à corridor égal, `b` devrait être bien plus
destructeur que `a`. Si c'est le cas, cela favorise les stratégies dont les λ de contrôle
sont **réparties** sur le domaine plutôt que groupées — exactement le genre d'arbitrage que
STRAT existe pour trouver. **Tirer et rapporter `a` et `b` séparément**, pour pouvoir
attribuer. Un balayage à `b = 0` puis à `a = 0` tranche en deux runs.

#### 👤 Les deux ambiguïtés sont levées (2026-08-08)

- **`0,005` est la DEMI-LARGEUR** : le vrai indice est dans `n_nom ± 0,005`. Le corridor
  complet fait donc 0,010 de large.
- **`0,005` est en UNITÉS D'INDICE, absolu** — pas un pourcentage. Pour H (n ≈ 2,35), le
  vrai indice est entre **2,345 et 2,355**.

⚠️ **Conséquence à ne pas manquer : le corridor absolu mord plus fort sur L que sur H.**
0,005 sur n_H = 2,35 vaut 0,21 % en relatif ; sur n_L = 1,46 il vaut 0,34 %. Comme
l'épaisseur optique est `n·d`, l'erreur *relative* d'épaisseur optique est l'erreur
*relative* d'indice : **les couches L subissent donc une perturbation 1,6× plus grande que
les couches H**, à corridor égal. `delta_max` est une constante absolue unique appliquée aux
deux matériaux — surtout pas une fraction de `n`.

#### Valeur à utiliser

`delta_max = 0.005`, en unités d'indice, demi-largeur, **identique pour H et L**. Clé JSON
`index_corridor`, défaut **0,0** (contrainte C1).

#### 🔴 TRANCHÉ LE 2026-08-10 — `u(λ)` se normalise sur l'ENVELOPPE grille ∪ monitoring

> 👤 *« L'erreur d'indice est donnée sur la grille spectrale du filtre, pas des monitoring. »*
> — *« C'est sur le max de la grille spectrale / monitoring. »*

**La règle exacte** : le domaine de normalisation est l'**intervalle englobant les deux** —

```python
lo = min(grille_spectrale.min(), lambdas_monitoring.min())
hi = max(grille_spectrale.max(), lambdas_monitoring.max())
```

En pratique la grille spectrale contient les λ de monitoring et l'union se réduit à la grille.
Mais **prendre l'enveloppe ne peut jamais être faux**, et §25 signale précisément que
`clues_at_wl` porte l'union des deux grilles **avec un débordement hors plage** : une λ de
monitoring peut donc sortir de la grille de notation. L'union est la formulation défensive.

**Le code fait aujourd'hui le contraire**, et c'est un défaut, pas un choix :
`corridor_wl_range()` normalise sur les **seules λ de monitoring**, bien plus étroites que la
grille sur laquelle le filtre est jugé.

**Conséquence chiffrée.** Avec un monitoring entre 480 et 620 nm et une grille descendant à
400 nm :

```
u(400 nm) = (2 x 400 - (480 + 620)) / (620 - 480) = -2,14        au lieu de |u| <= 1
delta(400 nm) = 0,005 x (-2,14) = -0,0107                        soit 2,1 x le corridor
```

Le modèle sort donc de la boîte qu'il est censé respecter — **et il en sort précisément là où
le mode croisé fait ses dégâts**, sur les bords, loin du point de contrôle.

🔴 **Toutes les mesures de corridor antérieures au 2026-08-10 sont donc INVALIDES**, y compris
la courbe ×1,98 / ×3,13 / ×5,79 et le croisement de régime qu'elle montrait. Elles ont mesuré
un corridor effectif plus large que 0,005, d'un facteur qui dépend de la stratégie. **Ne les
cite plus.**

⚠️ **La correction n'est pas neutre, et il faut savoir dans quel sens.** Une droite contrainte
à rester dans ±0,005 sur un **large** domaine a nécessairement une **pente plus faible** que la
même droite contrainte sur un domaine étroit. Corriger fait donc deux choses à la fois :
plafonner l'erreur aux bords (moins de dégâts) **et** réduire l'inclinaison vue par le
monitoring (moins de mode croisé). L'effet net est à mesurer, pas à prédire.

**Où intervenir** — les trois fonctions doivent recevoir la grille spectrale, pas la déduire :

| Fichier | Fonction | Ce qui change |
|---|---|---|
| `certus_strat_batch.py` | `corridor_wl_range` | prend **deux** jeux de λ et rend leur **enveloppe** |
| idem | `simulate_stack_robustness_batch` | recevoir la grille spectrale, au lieu de déduire de `layer_wavelengths` |
| idem | `validate_wavelengths_batch` | idem pour la Phase A, au lieu de `candidate_wls` |
| idem | `compute_batch_rmse` | déjà paramétré, il suffit de lui passer la même enveloppe |

🔴 **Un seul appelant doit calculer l'enveloppe, et la passer aux trois.** Si chacune la
recalcule, elles finiront par diverger — c'est exactement ce que `corridor_wl_range` a été
créée pour empêcher il y a deux heures, et le défaut qu'on corrige ici en est déjà une
récidive.

---

### 12.4 Grille d'échantillonnage à la cadence machine — **à faire AVANT 12.2**

> 🔴 **Ordre imposé.** Le lissage de §12.2 se compte en lectures machine : il n'a aucun sens
> tant que la grille n'est pas celle de la machine. Mais la grille seule fait exploser les
> faux points tournants (33 % → 99,9 %). **Donc : cette action d'abord, §12.2 immédiatement
> derrière, et on ne mesure le taux de plantage qu'une fois les deux en place.** Les mesurer
> séparément produirait deux chiffres également faux.

**Cible** : `Δd = v_dépôt / f_échantillonnage` = **0,125 nm**, soit ~800 points par couche de
100 nm contre 21 aujourd'hui. Ce n'est pas un raffinement numérique — **c'est une
caractéristique physique de la machine** (§17).

#### Pièges connus

- 🔴 **`NPTS_PREV = ceil(d_real_j)` casserait C2.** `d_real_j` est l'épaisseur **obtenue**,
  donc dépendante de la stratégie : le nombre de tirages de bruit par couche deviendrait
  fonction de la stratégie évaluée. **Indexer sur `p_thick_nominal[j]`**, qui ne l'est pas.
- 🔴 **Ne jamais raffiner sans 12.2.** À seuil inchangé, la fabrication passe de 33 % à
  99,9 %. Le taux de plantage exploserait et on l'attribuerait à la physique.
- ⚠️ `idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))` vaut aujourd'hui exactement
  `n_hist + 21` parce que 63/3 est entier. Avec un `NPTS` variable, l'arrondi introduit un
  décalage sous-pas. Vérifier que l'indice d'arrêt tombe toujours sur `d_nom`.
- ⚠️ Le **point dupliqué** à la jonction historique / couche courante (`k == 0`, traité aux
  lignes ~633-638) doit rester un tirage unique. Avec un `NPTS_PREV` variable, l'indice de
  repli devient `NPTS_PREV(i_layer − 1) − 1`, pas la constante 16.

---

### 12.5 Quantification temporelle du déclenchement — `U(0, 0,125 nm)`

Le volet ne peut pas se déclencher avant le franchissement : la loi est **strictement
positive**, jamais centrée. Pas de double comptage avec `noise_val_precalc`, qui est un bruit
**photométrique** (en T) là où celui-ci est **spatial** (en d) — deux effets physiquement
indépendants.

**Quasi gratuit une fois 12.4 fait** : si la grille de balayage est celle de la machine, on
s'arrête au **premier point de grille au-delà du seuil** au lieu d'interpoler, et la
quantification apparaît d'elle-même, sans paramètre supplémentaire.

**Vérification** : Piège 1. Si le taux de plantage ne bouge pas quand on double
`Δd_sample`, la mesure est un artefact.

---

### 12.7 🔴 Résolution du monochromateur — 👤 spécification du 2026-08-09

> 👤 *« Le système de monitoring a une résolution donnée, en général 2 nm, correspondant au
> bruit nominal. Mais l'utilisateur peut choisir 5 nm (bruit divisé environ par 1,5) ou 1 nm
> (bruit × 2) ou 0,5 nm (bruit × 5). La résolution reste figée pendant tout le dépôt. Une
> résolution inadaptée peut fausser les signaux. Mais une résolution excellente augmente le
> bruit ! »*

**C'est le premier réglage du projet qui a un OPTIMUM**, et non un sens de progrès. Tous les
autres paramètres s'améliorent quand on les pousse dans une direction ; celui-ci se dégrade
des deux côtés. C'est ce qui le rend intéressant, et c'est aussi ce qui interdit de le régler
au jugé.

#### 🔑 Le mécanisme exact — 👤 précision du 2026-08-10

> 👤 *« À aucun moment l'OMS ne sait calculer des réponses spectrales avec problème de
> résolution, c'est toujours avec une résolution parfaite ! C'est pour cela qu'ouvrir trop les
> fentes peut être problématique : les niveaux attendus ne sont pas les bons. »*

**La machine compare deux grandeurs qui ne sont pas de même nature :**

| | |
|---|---|
| ce qu'elle **attend** | `T_théorique(λ_mon)` — **monochromatique, résolution parfaite** |
| ce qu'elle **lit** | `⟨T(λ)⟩` moyenné sur `[λ_mon − B/2 ; λ_mon + B/2]` |

Ce n'est donc **pas** une perte de dynamique. C'est un **biais systématique de niveau** :

$$\text{biais}(B) \;=\; \langle T\rangle_B - T(\lambda_{\text{mon}}) \;=\; \frac{T''(\lambda_{\text{mon}})\,B^2}{24}$$

🔴 **Et un biais n'est pas du bruit.** Il ne s'annule pas en moyenne, il ne se dilue pas dans
le Monte-Carlo, il pousse **tous** les tirages du même côté. La machine coupe systématiquement
trop tôt ou trop tard, **et elle n'a aucun moyen de s'en apercevoir** — sa seule référence est
sa propre théorie, qui est monochromatique.

⚠️ **Ne compare donc JAMAIS le biais de fente et le bruit de lecture comme deux termes
équivalents.** Une version antérieure de cette section parlait d'un rapport
`swing_effectif(B) / bruit(B)` à optimiser : **c'était faux.** Un biais de X points est
bien plus destructeur qu'un bruit de X points, parce que la statistique absorbe le second et
pas le premier.

| | Fente large (5 nm) | Fente étroite (0,5 nm) |
|---|---|---|
| **Bruit** | ÷1,5 | **×5** |
| Nature de la pénalité | **BIAIS systématique**, non absorbable | bruit aléatoire, absorbé par la statistique |
| Où c'est pire | là où `T(λ)` est le plus **courbé** — près du front, dans les ondulations | uniforme |

🟢 **Conséquence heureuse : `_calculate_strategy_spectral_resolution` calcule exactement la
bonne grandeur.** Il mesure la courbure spectrale et cherche la largeur à laquelle l'erreur de
convolution atteint la tolérance — c'est-à-dire **à quelle fente le biais atteint la taille du
bruit**. C'est la bonne question, et elle était déjà posée. Il lui manque seulement le facteur
√3 (ci-dessous) et d'être utilisée pour autre chose qu'un rapport.

🟢 **Conséquence pratique : modéliser la résolution est BEAUCOUP moins cher que prévu.**
Pas besoin de convoluer le signal de croissance sur plusieurs λ. Il suffit d'ajouter au
**niveau visé** de chaque couche le biais `T''(λ_mon)·B²/24`, et la courbure est déjà
calculée. **L'action se réduit à un terme additif par couche, plus le facteur de bruit.**

#### 🔒 Le facteur de bruit est une TABLE ESTIMÉE — statut à ne pas confondre

| Résolution | 5 nm | **2 nm** | 1 nm | 0,5 nm |
|---|---|---|---|---|
| Facteur sur `A` | **÷1,5** | **×1** (nominal) | **×2** | **×5** |

🔴 **Ces quatre valeurs ne sont PAS mesurées.** 👤 *« estimés par moi au feeling »*
(2026-08-09). Elles ont donc le statut d'un **postulat de modélisation**, comme §18 — pas
celui d'une spécification constructeur. Ne les cite jamais comme une mesure.

**Ce que cela impose, et ce n'est pas négociable** : une conclusion tirée de ces chiffres
n'est un résultat physique **que si elle survit à leur incertitude**. Donc toute mesure de
résolution s'accompagne d'un **contrôle de sensibilité** :

> Refaire la comparaison avec les facteurs déplacés dans une fourchette plausible — par
> exemple ÷1,2 au lieu de ÷1,5, et ×3 au lieu de ×5. **Si la résolution gagnante ne change
> pas, la conclusion est robuste et on peut l'écrire. Si elle change, la conclusion dépend
> d'une estimation au feeling et il faut le dire dans la même phrase.**

C'est le même esprit que le Piège 1 : une conclusion qui repose sur un nombre non mesuré
n'est pas de la physique tant qu'on n'a pas montré qu'elle n'en dépend pas.

⚠️ **Ne cherche pas la loi de puissance.** Elle ne tient pas : entre 5 et 2 nm le
comportement est proche du photonique en `1/√B` (√(2/5) = 0,63, soit ÷1,58 contre ÷1,5
estimé), mais en dessous il se dégrade **plus vite** que `1/B` (×5 à 0,5 nm là où `1/B`
donnerait ×4). Ajuster une loi sur quatre estimations produirait un modèle inventé sur des
nombres inventés. Et surtout, une loi permettrait de proposer des résolutions **qui
n'existent pas sur la machine**. **Quatre réglages, quatre entrées de table.**

#### 🔴 La fente est RECTANGULAIRE — et la formule en production est trop stricte de √3

👤 *« rectangle »* (2026-08-09). Le signal mesuré est donc la moyenne **uniforme** de `T(λ)`
sur `[λ₀ − B/2 ; λ₀ + B/2]`, et son erreur au second ordre vaut

$$E_{\text{boxcar}}(B) \;=\; \frac{T''(\lambda_0)\,B^2}{24}$$

Or `_calculate_strategy_spectral_resolution` mesure une **seconde différence** sur
`± test_bw/2`, qui vaut `T''·test_bw²/8`, et en déduit
`res_limit = test_bw·√(tol/curvature)`. Ces deux quantités **ne sont pas la même chose** :

$$\frac{B_{\text{vrai}}}{B_{\text{code}}} \;=\; \sqrt{\frac{24}{8}} \;=\; \sqrt{3} \;\approx\; 1{,}732$$

📏 **Vérifié numériquement** (sonde autonome, intégration boxcar contre la formule de
production, `tol = 5e-4`) :

```
case                                code B_lim  true B_lim    ratio
--------------------------------------------------------------------
pure quadratic  T = 1e-4 lam^2          4.4721      7.7460   1.7321
gentle cosine   period 200 nm           2.8471      4.9320   1.7323
sharp cosine    period  20 nm           0.2850      0.4932   1.7305
sharp cosine    period  10 nm           0.1429      0.2466   1.7252
--------------------------------------------------------------------
sqrt(3) = 1.7321
```

**Le critère actuel est donc conservateur d'un facteur 1,73** : il déclare inutilisable une
largeur de fente qui passe encore. **Et c'est coûteux dans le bon sens** — corriger le
critère **élargit** les fentes admissibles, donc **rend accessible le bonus de bruit ÷1,5**
à des stratégies qui en sont aujourd'hui privées pour rien.

Correction, une ligne :

```python
res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)   # fente RECTANGULAIRE
```

⚠️ **La limite de cette correction, et il faut la connaître** : le √3 vient d'un
développement au **second ordre**. Le tableau ci-dessus le montre en train de se dégrader
quand la structure devient fine devant `B` — 1,7252 à période 10 nm contre 1,7321 sur la
quadratique pure, où le développement est exact. Or c'est précisément là que le critère
compte. **Si `min_resolution` devient un jour un couperet et non un diagnostic, valide-le
contre une intégration boxcar directe sur l'empilement réel**, pas contre le développement.

#### 🔑 La résolution FAIT PARTIE de la stratégie — 👤 2026-08-09

> 👤 *« Il faudra donc implanter la détermination de la résolution optimale pour une stratégie
> donnée… cette résolution fait partie intégrante de "la stratégie" à trouver. »*

Une stratégie n'est donc plus *(découpage en blocs, λ par bloc)* mais
**\*(découpage en blocs, λ par bloc, RÉSOLUTION)\***, avec une seule résolution pour tout le
dépôt.

**Où cette variable a sa place — et où elle ne l'a pas :**

| Étage | Verdict |
|---|---|
| **Phase A** | ❌ Impossible. La Phase A juge **une couche à la fois**, or le coût de la résolution est un compromis **sur tout le run** : la couche qui lie (`worst_layer`) n'est connue qu'une fois la stratégie entière formée. |
| **DP** | ❌ Inutile. La DP optimise une **somme de coûts par couche** ; la résolution est un choix **global unique** qui ne se décompose pas additivement. La mettre dans l'état de la DP multiplierait cet état par 4 sans rien apporter. |
| **Phase B** | ✅ **C'est là.** Chaque stratégie candidate est évaluée aux 4 résolutions. Coût : **×4** sur le criblage Monte-Carlo. Cher, mais honnête — et c'est le seul étage qui mesure la grandeur qui décide. |

🔴 **Contrainte C2, et elle est impérative ici** : le facteur de résolution doit multiplier
**l'échantillon**, jamais entrer dans la graine.

```python
noise = RESOLUTION_NOISE_FACTOR[B] * _seeded_noise_sample(seed, groupe, tirage, elem, True)
```

Sans cela les 4 résolutions voient 4 aléas différents, et l'écart entre elles n'est plus
imputable à la résolution. C'est **exactement** la faute que C2 existe pour empêcher, et elle
serait ici invisible : les quatre chiffres auraient l'air parfaitement plausibles.

**Comment ne pas payer le ×4 en entier.** `_calculate_strategy_spectral_resolution` rend déjà
`min_resolution`, la fente la plus large qu'une stratégie tolère. Les résolutions plus larges
sont *prédites* déformantes. Cela donne un ordre d'évaluation — commencer par les plus
prometteuses — et, **si et seulement si** on a d'abord compté ce qu'elle écarte réellement
(§12-contrôle 4), un pré-filtre. ⚠️ Tant que ce comptage n'est pas fait, c'est un
**diagnostic, pas un couperet** — même règle qu'en §22 pour les heuristiques de la
littérature.

**Et voici l'effet le plus intéressant, celui qu'on n'attendait pas :** la résolution
n'ajoute pas seulement un choix à 4 branches, elle **change quelles λ sont bonnes**. Une λ
posée dans une région spectralement lisse tolère la fente de 5 nm et **empoche le ÷1,5 de
bruit gratuitement** ; une λ posée près du front impose 1 nm et **paie le ×2**. La valeur
d'une λ dépend donc désormais de la douceur spectrale de son voisinage, et pas seulement de sa
dynamique. C'est un arbitrage neuf, il n'est écrit nulle part dans le code, et c'est
typiquement ce que STRAT existe pour trouver.

⚠️ **Le compromis n'est pas le même à toutes les couches, et c'est le nœud.** La finesse
spectrale de l'empilement **croît avec le nombre de couches** : une résolution confortable à
la couche 3 peut être trop grossière à la couche 40. Comme elle est **figée**, l'optimum est
un compromis sur tout le run — et c'est exactement ce que `worst_layer`, déjà rendu par la
fonction ci-dessus, désigne.

**Deux conséquences de tenue de dossier, à ne pas oublier** : la stratégie gagnante doit
**rapporter sa résolution** (sinon elle n'est pas exécutable en salle), et la sonde doit
l'écrire dans son JSON — même leçon que `f4ada2d`.

#### Les questions à poser

| # | Question | Pourquoi elle change le code |
|---|---|---|
| # | Question | Réponse |
|---|---|---|
| Q1 | Forme de la fonction de fente ? | ✅ 👤 **rectangulaire** (2026-08-09). Convolution = moyenne uniforme sur `B`. D'où la correction √3 ci-dessus. |

**Q3, reformulée** — la question portait sur une confusion d'unité dans le code et elle n'était
pas claire. Deux grandeurs différentes cohabitent :

- la **largeur de fente** `B` : la largeur du domaine spectral sur lequel la machine moyenne.
  C'est le sujet de toute cette section. Nominal **2 nm**.
- le **pas de réglage** de λ : la granularité avec laquelle on peut *positionner* le centre de
  la fente. Peut-on demander 545,0 · 545,3 · 545,7 nm indifféremment, ou seulement des
  multiples d'un pas — et lequel ?

`MachineModel` porte `monochromator_resolution_nm = 0.5`, alimenté par une constante nommée
`OMS5100_DEFAULT_MONOCHROMATOR_**STEP**_NM` et documentée « step / precision ». Le nom dit
*pas*, le champ dit *résolution*, et la valeur (0,5) ne correspond pas au nominal (2 nm).
**L'une des deux lectures est fausse et il faut savoir laquelle.**

⚠️ **Pourquoi ça compte pratiquement** : STRAT choisit ses λ de contrôle sur une grille à
**1 nm** (§25, décision tranchée). Si le pas machine vaut 0,5 nm, toute λ de la grille est
atteignable et il n'y a rien à faire. S'il vaut 2 nm, **la moitié des λ proposées ne sont pas
réglables sur la machine**, et §8 l'interdit explicitement : *« ne jamais proposer une λ hors
de la grille de balayage »*. La grille devrait alors s'aligner sur le pas machine.

---

### 12.6 Facteur de face arrière sur les seuils absolus — **en dernier, ou jamais**

`T_back = 4n/(n+1)² ≈ 0,957` pour BK7, soit 4,4 %. Le chemin de **notation** applique déjà la
face arrière complète avec réflexions multiples (`certus_strat_batch.py:310-316`) : l'écart
ne concerne que le signal de monitoring, et vaut **0,002 en absolu** sur `SWING_MIN`.

⚠️ Ne **pas** l'implémenter via `affine_scale` : ce paramètre modélise une dérive
d'étalonnage inconnue du contrôleur, alors que la face arrière est un facteur **connu et
constant**. Les confondre rendrait les deux mesures ininterprétables.
