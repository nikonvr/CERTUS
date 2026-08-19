# 21. 👤 LE SECOND COMPOSANT D'ESSAI — passe-bande à trois cavités, 2026-08-11

> Extrait de `CLAUDE.md` le 2026-08-16. Ce contenu **fait autorite** ;
> `CLAUDE.md` n'en garde qu'un renvoi. 🔑 **Un fait, un seul endroit** — si tu corriges
> quelque chose ici, ne le recopie pas ailleurs, mets un lien.

---


> 👤 *« Tu vas implanter un deuxième filtre test. Ce sera un passe-bande à trois cavités, que
> l'on contrôle normalement en TPM mais qui là sera avec notre STRAT à nous ! Je propose un
> M5-2L-M5-L-M5-2L-M5-L-M5-2L-M5 centré à 632 nm et dont l'écart spectral sera mesuré sur
> 2× la bande passante environ. On garde les mêmes indices. »*
> — puis *« pour le passe-bande, le SEEL et l'écart spectral doivent être sur 600 – 660 nm »*

**Fichier** : `example/example_strat/JSON-strat-bandpass-3cav.json`

### Ce qu'il est

| | |
|---|---|
| Empilement | `M5 · 2L · M5 · L · M5 · 2L · M5 · L · M5 · 2L · M5` = **35 couches** |
| Alternance | `HLHLH…H`, parfaite — les trois cavités `2L` tombent aux indices **5, 17, 29**, tous impairs, donc **L**, ce qu'exige la convention de parité du noyau |
| Indices | **inchangés** : H 2,35 · L 1,46 · substrat 1,52 |
| `l0` | **631,93** |
| Centre à mi-hauteur | **632,00 nm** · bande **625,1 – 638,9 nm** (**13,7 nm**) |
| Pic | T = **0,9966** |
| Épaisseur totale | 3 356 nm |
| Cible spectrale et SEEL | 👤 **600 – 660 nm**, pas 1 nm — **61 points**, dont **13** dans la bande passante |
| Balayage de contrôle | **450 – 700 nm**, pas 1 nm |

🔑 **Le domaine de balayage est identique à celui du dichroïque, et ce n'est pas un détail** :
👤 *« les deux filtres sont monitorables sur le même domaine, non ? »* — oui, parce que
**c'est une propriété du monochromateur, pas du design**. Une première version portait
520 – 760 nm, calquée sur le filtre au lieu de la machine. Corrigé.

### 🔴 Le piège qui a fait rater le centrage du premier coup

Un trois-cavités a un sommet **plat et ondulé** : `T > 0,99` sur **10,4 nm**. `argmax` saute
donc d'une ondulation à l'autre selon le pas de la grille d'évaluation, et le centrage
calculé dessus est faux **sans qu'aucun contrôle ne le signale** :

```
  l0 = 632, grille 0,25 nm  ->  argmax a 637,0 nm
  l0 = 632, grille 0,05 nm  ->  argmax a 627,1 nm      <- 10 nm d'ecart, meme filtre
```

**La grandeur qui centre un passe-bande est le MILIEU DE LA BANDE À MI-HAUTEUR**, jamais
`argmax`. Sur ce critère la relation est monotone et la bissection converge :
`l0 = 631,93 → centre 632,00 nm`.

### Pourquoi ce composant apporte quelque chose que le dichroïque n'apporte pas

👤 *« que l'on contrôle normalement en TPM »* — le passe-bande est le cas d'école du
**monitoring par points tournants**, là où le dichroïque vit de niveaux intermédiaires. Les
couches `M5` sont des QWOT à λ₀ : leur signal de monitoring **passe par un extremum à
l'épaisseur visée**, ce qui est le régime où §22-5 dit que `dT/dd → 0` et où une erreur de
niveau se convertit en une grande erreur d'épaisseur.

⚠️ **La géométrie de la cible n'est PAS celle du juge de paix, et il faut le savoir avant de
comparer les deux scores.** §22 a mesuré que le dichroïque a **exactement 141 points par
bande sur 301**, d'où l'incapacité d'un RMSE uniforme à distinguer les deux bandes. Ici c'est
**13 points sur 61** dans la bande passante. **Les deux composants ne posent donc pas la même
question à la fonction objectif**, et un écart de score entre eux ne se lit pas comme un écart
de difficulté.

### 🔴 Ce que ce second composant ne change PAS

§26 reste **entier**. Deux bancs de cohérence ne font pas une validation physique : aucun des
deux n'a de dépôt réel en face. Et §11-4 continue de s'appliquer dans les deux sens — **on ne
conclut pas du passe-bande sur le dichroïque, ni l'inverse.** Ce que le second composant
permet, c'est de voir si une conclusion **survit** au changement de composant ; c'est un test
de robustesse de la conclusion, pas une corroboration de la physique.

---

### 🔴 POEM NE PEUT PAS S'ANCRER SUR LE PASSE-BANDE — et c'est structurel, 2026-08-12

> 👤 *« Je reste sur le cul pour le 35 couches. Il n'y a jamais de POEM ? »*

La gagnante du passe-bande a **35 blocs** — une λ de contrôle par couche, donc **aucun
historique hérité**. La question est légitime, et la réponse est : **POEM ne s'ancre que
sur 8 couches sur 34.** Sur les 26 autres, la machine tourne au **niveau absolu**.

#### Comment ça se mesure sans ambiguïté

Déposer la couche avec une erreur amont de 2 nm, `poem_enabled` vrai puis faux. **Si les
deux rendent la même épaisseur au bit, POEM n'a pas pu s'ancrer** — il est retombé sur le
repli. Aucune interprétation nécessaire.

```
35 couches, gagnante a 35 blocs (aucun historique)  ->  POEM s'ancre  8 / 34   (24 %)
48 couches, gagnante a  6 blocs (1er bloc = 29 couches) ->            42 / 47   (89 %)
```

#### Pourquoi — et ce n'est pas réparable sur ce composant

Sans historique, POEM doit trouver **deux points tournants dans la seule couche
courante**. `T(d)` étant un sinusoïde en `2δ` (§31), les extrema tombent tous les 90°,
et la phase à l'arrêt vaut

$$\delta_{\text{nom}} = \frac{2\pi n\,d_{\text{nom}}}{\lambda_{\text{mon}}}
= \frac{\pi}{2}\cdot\frac{\lambda_0}{\lambda_{\text{mon}}}
\qquad\text{pour une QWOT à }\lambda_0$$

📏 Les λ retenues donnent `λ₀/λ` entre **1,11 et 1,40** : entre **un et deux** extrema
franchis. **POEM est exactement à son seuil sur toutes les couches**, et de quel côté on
tombe est décidé par l'offset de phase du sous-empilement — d'où les 8 sur 34, sans loi
simple.

🔴 **Pour disposer de deux ancres il faudrait `λ ≤ λ₀/2 = 316 nm`. Le monochromateur ne
descend pas sous 450 nm.** C'est donc structurellement impossible, et cela explique
pourquoi ce type de filtre se contrôle normalement en **TPM** : on s'arrête *sur* le point
tournant, on ne cherche pas à en encadrer deux.

#### 🔴 Ma prédiction a échoué, et le motif de l'échec vaut d'être gardé

J'avais posé « POEM s'ancre ssi `λ₀/λ ≥ 2` ». Elle tombe juste sur **26 couches sur 34**
— et **c'est trompeur** : elle prédit « non » partout et a raison 26 fois par simple taux
de base, en se trompant sur les 8 couches qui portent toute l'information.

> **Un prédicteur constant qui a raison par taux de base n'a aucun pouvoir discriminant.**
> Lire son score global comme une validation est exactement l'auto-illusion que §12-5
> attrape. Ce qu'il faut regarder, c'est le taux sur la classe MINORITAIRE.

#### Ce qui a été écarté au passage

⚠️ **POEM n'est pas cassé.** À la couche 5 il rend `CRASH_TP_MISCOUNT`, ce qui avait l'air
d'un défaut. Vérification, à bruit nul, avec 2 nm d'erreur amont :

```
extrema geometriques avant l'arret :  reel [8, 15]      -> 2
                                   nominal [1, 8, 16]   -> 3
```

Le nominal porte un extremum **à l'indice 1**, à ~5 % de la couche ; le réel ne l'a pas.
Une erreur amont de 2 nm suffit à faire basculer un extremum qui tombe au tout début du
balayage. **Le détecteur compte juste ; ce sont les signaux qui diffèrent.** C'est une
fragilité physique réelle de POEM, pas un bug — et elle est spécifique aux couches dont le
signal démarre près d'un extremum.

#### ✅ LES TROIS LECTURES SONT TRANCHÉES — 2026-08-12

Trois explications étaient possibles et il fallait les séparer avant de croire quoi que
ce soit. Les trois tests, du moins cher au plus cher :

| lecture | verdict | ce qui l'a tranchée |
|---|---|---|
| **POEM est cassé** | ❌ | le détecteur compte juste — extrema réels `[8,15]` contre nominaux `[1,8,16]` — et POEM s'ancre sur **42/47** couches du dichroïque |
| **le repli absolu est favorisé par le retrait de l'affine** | ❌ | affine **rallumée** à 0,05/0,02 : **même gagnante à 35 blocs**, `RESULT` +0,5 % — et l'affine atteint bien le calcul, `n_ranked` tombe de 380 à 334 |
| **c'est structurel** | ✅ | `λ₀/λ ∈ [1,11 ; 1,40]` sur toutes les λ retenues, et la machine ne descend pas sous 450 nm |

🔑 **Donc c'est réel.** Sur un passe-bande à couches QWOT monitoré dans la plage de la
machine, POEM n'a **pas de prise**, et le contrôle couche par couche au niveau absolu est
la bonne réponse. Ce n'est pas la recherche qui contourne le mécanisme central : c'est le
mécanisme qui ne s'applique pas ici, et la recherche qui le trouve.

Et cela retombe sur ce que 👤 disait en posant le composant — *« un passe-bande, on le
contrôle normalement en TPM »*. On s'arrête **sur** le point tournant au lieu d'en
encadrer deux. **Le modèle l'a retrouvé seul, par une route indépendante**, ce qui est la
seule forme de corroboration dont ce projet dispose tant que §26 n'est pas fermée.

#### 🔑 Pourquoi c'est arrivé MAINTENANT

Deux changements du 2026-08-12 poussent dans le même sens :

1. **La distorsion affine est éteinte** ([`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1bis) — or c'était le handicap du repli
   absolu, la seule branche que [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.1 démontre non invariante. Il a cessé d'être pénalisé.
2. **Le biais de fente pénalise les ancres héritées** (§30) — chaque couche
   d'historique porte le biais de *sa* courbure, pas de celle de la couche en cours.

**La recherche a exploité les deux.** Ce n'est pas une anomalie : c'est le modèle qui,
devenu plus fidèle, désigne une autre stratégie de contrôle.

⚠️ **Ce que cela n'établit PAS.** Que le niveau absolu soit *bon* — seulement qu'il est
meilleur que POEM **dans ce modèle-ci, sur ce composant-ci**. Il n'a aucune
auto-compensation des erreurs accumulées, et il reste exposé à la courbure photométrique
qui, elle, n'est pas affine. §26 s'applique en entier : rien de ceci n'est validé contre un
dépôt réel.

---

### 🔑 D'OÙ VIENT L'ERREUR — le profil d'ablation, 2026-08-12

> 👤 *« Plein de défauts ou de biais font qu'on obtient un SEEL assez loin de 0. J'aimerais
> savoir, dans les deux cas, quel est le défaut le plus problématique. »* — puis *« pour
> chacune des 20 meilleures stratégies, faire un classement de l'influence de chaque source
> de défaut. Cela permettra à l'utilisateur de mieux comprendre d'où viennent les
> problèmes. »*

On éteint chaque source à tour de rôle et on relit le score. La contribution est
`1 − score_sans / score_avec`.

📏 **Mesuré sur les gagnantes des repères N = 300 :**

| on retire… | dichroïque 48c | passe-bande 35c |
|---|---|---|
| **le corridor d'indice** | **69 %** | 15 % |
| le biais de fente | 0 % | **16 %** |
| la courbure photométrique | 1 % | 3 % |
| le bruit de lecture | ~0 % | ~0 % |

🔑 **Le même modèle rend deux diagnostics OPPOSÉS selon le composant.** Sur le dichroïque
une source écrase tout ; sur le passe-bande fente et corridor se partagent la charge et
personne ne domine. **C'est pour ça que le profil est par stratégie et non global** : une
note générale du type « le corridor domine » serait fausse une fois sur deux.

🟢 **Et le bruit de lecture ne pèse rien nulle part**, ce qui est le contrôle du montage :
c'est du **bruit**, il s'annule sur les tirages, là où les trois autres sont des **biais**
qui poussent tous les tirages du même côté. **Une ablation où le bruit sortirait dominant
signalerait une erreur de montage, pas un résultat.**

#### 🔴 Ce que ces nombres NE SONT PAS

**Ils ne s'additionnent pas à 100 %.** Les sources interagissent — le corridor fausse
l'épaisseur **et** l'indice du filtre fini, la fente déplace l'ancre que POEM utilisera
ensuite — donc en éteindre deux ne retire pas la somme de leurs deux parts. Ce sont des
**dérivées**, pas un partage de gâteau.

⚠️ Et pour le corridor la part affichée est plutôt une **sous-estimation** : il agit deux
fois, alors que la métrique d'épaisseur ne voit que le premier des deux effets.

#### 🔑 LE CORRIDOR SATURE — et c'est ce qui répond vraiment à la question

> 👤 *« Ça m'embête de diminuer les erreurs sur les indices car je sais que cette valeur
> est plausible. »*

📏 Balayage sur la gagnante du dichroïque :

```
corridor    erreur d'epaisseur RMS
0,0000              1,443 nm
0,0025              4,179 nm     <- presque tout le dommage est deja la
0,0050              4,654 nm     +11 %
0,0100              4,594 nm     SATURE
```

**Quadrupler la perturbation de 0,0025 à 0,010 ne coûte que 10 %.** Donc **abaisser la
spécification à 0,0025 ne gagnerait que 10 %** : le scrupule de 👤 était fondé, et pour une
raison plus forte que celle avancée — ce n'est pas seulement que 0,005 est plausible, c'est
qu'**y toucher ne servirait à rien**.

Sur le passe-bande la réponse est régulière : `+1,6 % · +17 % · +23 %`, **pas de
saturation**.

> **Deux régimes.** Le dichroïque a un **seuil** : au-delà d'une petite incertitude
> d'indice la compensation POEM décroche, et ce qui suit ne change plus grand-chose. Le
> passe-bande se dégrade proportionnellement.

#### 🔴 Ce que je n'ai PAS mesuré, et qu'il ne faut pas croire mesuré

**L'asymétrie H / L.** [`TRAVAUX_A_VENIR.md`](TRAVAUX_A_VENIR.md) §12.3 note que 0,005 en absolu vaut 0,21 % sur H et **0,34 % sur L**
— rapport 1,6. J'ai voulu la mesurer et **je n'ai pas pu** : le corridor perturbe les deux
matériaux ensemble et aucun paramètre ne les sépare. Le balayage ci-dessus mesure donc
l'**amplitude**, pas la **répartition**. La question reste ouverte, et elle demanderait un
tirage par matériau exposé séparément.

#### Ce que ça donne comme conseil, et il est actionnable

Sur le dichroïque, **69 % de l'erreur vient de l'incertitude d'indice**. Autrement dit :

> **Raffiner le monitoring sur ce composant ne rapportera presque rien. C'est la
> connaissance des indices qui limite** — et une campagne de détermination d'indice
> attaquerait les 69 %.

⚠️ **Et les 31 % restants ne sont attribués à RIEN — ne laisse personne les nommer.** Une
version antérieure de cette phrase disait *« là où POEM, la fente et le lissage se
partagent les 31 % restants »*, ce qui invente un partage deux fois : la fente mesure
**0 %** sur ce composant, et le lissage de lecture est **éteint** par décision, donc il ne
peut rien peser du tout. Les quatre ablations totalisent ~70 % ; ce qui reste est de
l'**interaction entre sources et des mécanismes qu'aucune ablation n'isole**. C'est le même
avertissement que ci-dessus — ce sont des dérivées, pas des parts — et il vaut aussi pour
le résidu.

C'est le genre de chose qu'un outil doit dire à son utilisateur, et STRAT ne le disait pas.

#### Comment c'est calculé

`_ablation_profile`, sur les **20 meilleures**, **après** le classement — jamais avant,
pour qu'un diagnostic ne puisse pas influencer l'ordre. À **64 tirages**, volontairement
moins que le classement : on mesure une contribution **relative**, pas un score. C'est
assez pour séparer une source à 60 % d'une source à 2 %, et ce ne serait pas assez pour
départager deux stratégies — ce qu'on ne fait pas ici.

Le résultat remonte dans le rapport de sonde sous `ablation`, et dans le tableau de
l'interface sous la colonne **« Dominant defect »**, l'info-bulle portant le classement
complet et les deux avertissements ci-dessus.

---

## 🔑 LA SÉRIE D'ÉCHELLE DU RANDOM75 — cinq variantes, et c'est l'INSTRUMENT du projet

📌 **Le dossier fait autorité : [`CHANTIER_PREDICTIBILITE.md`](CHANTIER_PREDICTIBILITE.md).**
Ici, seulement de quoi savoir que ces fichiers existent et à quoi ils servent.

Le même empilement aléatoire de 75 couches, à cinq échelles d'épaisseur. **Nombre de couches,
structure, matériaux, substrat et grille spectrale identiques ; seule l'épaisseur optique varie.**
C'est le seul dispositif du dépôt qui sépare l'**épaisseur optique** du **nombre de couches**.

| fichier | Σ QWOT | généré par |
|---|---|---|
| `example/example_strat/JSON-strat-random75.json` | 114,9 | la référence, ×1 |
| `reports/serie_echelle_r75/cfg_x0.5.json` | 57,4 | `scripts/serie_echelle_r75.py --facteur 0.5` |
| `reports/serie_echelle_r75/cfg_x1.5.json` | 172,3 | `… --facteur 1.5` |
| `reports/serie_echelle_r75/cfg_x1.75.json` | 201,1 | `… --facteur 1.75` — ajouté le 2026-08-18 |
| `reports/serie_echelle_r75/cfg_x2.json` | 229,8 | `… --facteur 2` |
| 🟢 `example/example_strat/JSON-strat-random75-x2-fabricable.json` | 229,8 | **le ×2 rendu fabricable** — fente 1 nm, mode `deep`. ⚠️ Le nom portait `-extreme` et le fichier a été **renommé** : le mode `extreme` n'apportait rien de mesurable |

### 🔴 LE ×2 EST ASSIS SUR LA FRONTIÈRE DE FABRICABILITÉ — mesuré le 2026-08-19

**Tout verdict le concernant bascule avec la graine**, dans les deux sens :

| configuration | graine 42 | graine 77 |
|---|---|---|
| `deep`, 1 nm, élargi, **pur optique** | **254 déposables**, plantage 1,0 % | **0 déposable**, plantage 38,0 % |
| `fast`, 2 nm, + queue Rate | 1 déposable, plantage 4,00 % | 1 déposable, plantage 2,00 % |

🔑 **Et ce n'est pas la fente qui décide, c'est la PROFONDEUR DE RECHERCHE.** À 1 nm, passer de
`fast` à `deep` fait **0 → 277 déposables**. Une conclusion tirée d'un run `fast` sur ce
composant ne dit donc rien de sa fabricabilité — seulement de ce que la recherche a proposé.

⚠️ **Conséquence de méthode, et elle vaut au-delà du ×2** : c'est le composant **le moins
adapté** pour établir une règle générale, précisément parce qu'il est marginal. Une méthode
qui « marche » sur lui peut n'être qu'un tirage. Le banc d'essai stable pour le Rate est
`75c à 1 nm` — voir [`CHANTIER_RATE.md`](CHANTIER_RATE.md) §7 et §12.

🔴 **Ne lis PAS cette série comme une échelle de difficulté.** Mesuré le 2026-08-18 : `×1,75` est
**plus épais** que `×1,5` et rend **282 stratégies déposables contre 1**. Ce que la série
ordonnait n'était pas la physique du design mais **ce que la recherche avait proposé** —
corrélation de rang **+0,975** avec le nombre de stratégies offertes, contre **+0,103** avec
l'épaisseur optique.

⚠️ **Et ce sont cinq filtres DIFFÉRENTS, pas cinq versions d'un même filtre** : le spectre nominal
change avec l'échelle, donc chaque SEEL est mesuré contre **sa propre** cible. Ce qui se compare
d'un facteur à l'autre est la **faisabilité**, pas le SEEL.
