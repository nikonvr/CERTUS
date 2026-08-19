# Décisions tranchées — enquêtes closes

> Extrait de `CLAUDE.md` le 2026-08-16. Ces quatre enquêtes sont **closes**.
> Elles sont gardées **pour ne pas les refaire**, pas pour être relues à chaque session.
> 🔑 **Un fait, un seul endroit** — corrige ici, ne recopie pas ailleurs.

---

## 22. La grille des λ de contrôle — 1 nm contre 2 nm, enquête du 2026-08-12

> 👤 *« Si jamais on impose une grille de 2 nm, est-ce qu'on va réellement louper de
> meilleures stratégies ? Si les top meilleures stratégies sont quasi aussi bonnes, on
> pourra zapper la grille 1 nm au profit du 2 nm et gagner du temps. »*

⚠️ **§25 porte une décision « tranchée, ne la rouvre pas » en faveur du 1 nm.** Elle
s'appuie sur quatre chiffres de 2026-08-08, que §25 marque lui-même comme **historiques** :
antérieurs à A10, à la correction d'enveloppe du corridor, et surtout à la modélisation de
la fente. §18 pose la règle de réouverture : *« on ne rouvre que si une MESURE la
contredit, pas un raisonnement »*. C'est bien une mesure qui la rouvre — le biais de fente.

### Ce qui est mesuré

📏 **La grille 2 nm est exactement l'ensemble des λ PAIRES** — `scan_wl_min = 450`, donc
126 candidates contre 251. Vérifié dans le code (`arange_inclusive`), pas supposé.

📏 **Le test qui compte, sur le run de référence.** La classe d'équivalence SEEL de la
gagnante (SEEL quantifié à 0,1 nm, demi-largeur `max(0,05 ; 0,06 × SEEL)`) contient
**9 stratégies, dont 3 entièrement PAIRES**, toutes à plantage 0,000 et SEEL 0,3 nm. Le
départage secondaire de §22, le rendement, ne les sépare pas non plus. **Une grille 2 nm
aurait trouvé un ex æquo au sens exact de la règle.**

📏 **Et sous la règle de tri de §22, la première est DÉJÀ paire** : `[544, 506]` sur le run
de référence, `[544, 462]` sur l'unique run portant le biais de fente. Ce critère n'a pas
été choisi après coup — il est écrit dans l'artefact par le code, sous `ranking_seel_rule`.

📏 **Contrôle du Piège 1 : POSITIF, et il faut le dire.** Le pas de 1 nm porte une
information **réelle**. L'écart entre `[544,531]` et `[544,532]` **converge** vers ~10 %
pour N ≥ 100 — il ne se dissout pas quand on approfondit — et vaut **3 σ à N = 1200**. Le
couple 452/453 est ordonné **dans le même sens sur trois graines indépendantes**.
🔑 **Mais cette information est plus fine que la limite de mesure** : 5 couples sur 6
tombent dans la même classe SEEL, l'écart valant 0,010 à 0,047 nm pour une demi-largeur de
0,050 nm. On mesure quelque chose de vrai que la règle de décision déclare, à juste titre,
indistinguable.

### 🔴 La limite qui domine tout le reste — ne pas conclure sans elle

**Le sous-ensemble pair d'un classement à 1 nm n'est PAS un run à 2 nm.** Mesuré dans le
code : la mutation ELITE porte sur l'**indice** de grille (`idx_wl = nearest + delta`), donc
un vrai run à 2 nm passerait **100 %** de son budget dans le sous-espace pair, alors que le
run à 1 nm n'y est passé qu'incidemment — **4,5 %** de ses stratégies classées sont
toutes-paires. Tout ce qui précède est donc une **borne PESSIMISTE**, jamais une estimation.
Et elle n'est solide qu'à **2 blocs** : dès 3 blocs le sous-espace pair est sous-échantillonné
d'un facteur 3, ce qui rend les régimes corridor > 0 **indécidables** par cette voie.

⚠️ **Zéro artefact pour le passe-bande.** Rien ici ne dit quoi que ce soit du second
composant — et c'est le plus exposé, sa période d'ondulation valant **5,0 nm** contre 7,2 pour
le dichroïque, donc une fente de 2 nm y moyenne une fraction plus grande d'ondulation.

⚠️ **Un seul artefact sur 64 porte le biais de fente**, à N = 12 contre 150, et il change
**deux choses à la fois** par rapport à la référence. Contrainte C3 : rien n'y est attribuable.

### Le coût, et ce qui n'est pas mesuré

| | |
|---|---|
| Candidates | **251 → 126**, exact |
| Profils de fente en Phase A | **12 048 → 6 048**, soit **65 s → 32 s** (comptage × 5,4 ms mesuré) |
| Part de la Phase A dans un run | ~68 % (§31) |
| **Rapport de temps réel de la Phase A** | 🔴 **NON MESURÉ.** Deux passes concurrentes ont rendu ×3,07 puis ×1,41 : machine occupée, chiffre inexploitable. Halver les candidates ne halve pas forcément un noyau `prange`, dont le remplissage se dégrade à faible charge. |

### 🔑 Le critère de décision, posé À L'AVANCE

> **On adopte 2 nm si et seulement si**, sur les **deux** composants et **au moins deux**
> graines, la gagnante du run à 2 nm tombe dans la **classe d'équivalence SEEL** de la
> gagnante du run à 1 nm, **et** que son rendement ne soit pas inférieur.

**8 runs** : 2 composants × 2 graines × 2 grilles, biais de fente actif, tout le reste neutre.
🔴 **Comparer deux `RESULT` bruts départagerait du bruit** — §24-26. C'est la classe qui décide.

---

## 23. 📏 LA PROFONDEUR MONTE-CARLO — campagne du 2026-08-12, et elle répond autre chose

> 👤 *« J'aimerais une courbe ou un tableau entre le nombre de samples (50, 150, 300, 500)
> et le temps d'exécution pour le 35c puis le 48c. Du coup, après, je choisirai
> définitivement le nombre d'échantillons. »*

**8 runs, `run_campaign.py n`, tous `OK`, tous sur le même état du code.** Les durées du
journal `probe_runs.tsv` n'ont **pas** été réutilisées : elles s'étalent sur plusieurs états
du code, et §24-7 vaut pour les secondes comme pour les résultats.

### Le coût

| N | 48 couches | 35 couches |
|---|---|---|
| 50 | 21,0 min | 7,6 min |
| **150** | **26,1 min** | **9,0 min** |
| 300 | 27,5 min | 10,5 min |
| 500 | 36,6 min | 15,1 min |

```
48 couches : part FIXE 19,8 min  +  1,94 s par tirage
35 couches : part FIXE  6,4 min  +  0,98 s par tirage
```

⚠️ **Lis la PENTE, jamais les totaux.** La dispersion run à run vaut ±1,9 min sur le
dichroïque : le pas 150→300 mesuré (+1,4 min) tient dedans alors que l'ajustement donne
+4,8 min. La part **fixe** — Phase A, DP, et l'ablation qui tourne à 64 tirages
constants — domine tout.

### 🔑 Et ce que la profondeur achète n'est pas ce qu'on croit

Sur un facteur **dix** de profondeur :

| | SEEL de la gagnante | identité de la gagnante | plantage |
|---|---|---|---|
| **48c** ⚠️ *valeurs NON comparables au repère 0,173 nm — voir l'encadré sous la table* | 0,587 · 0,570 · 0,583 · 0,583 nm → **±1,5 %** | **change à chaque profondeur** | 0,000 partout |
| **35c** | 1,154 · 1,406 · 1,371 · 1,154 nm → ±9,8 % | 37172 · 35838 · 35838 · 37413 | 0,000 partout |

🔴 **NE COMPARE PAS CES SEEL AUX REPÈRES DE `CLAUDE.md` §21 — ils ne mesurent pas la même
chose.** Signalé le 2026-08-19 par `scripts/coherence_md.py`, qui a vu 0,587 pour le 48c là où
le repère vaut **0,173**, et 1,154 pour le 35c là où il vaut **0,482** : des facteurs 3,4 et 2,4.

**Ce n'est pas une erreur, c'est C1** — *un changement de modèle change les chiffres, toute
mesure antérieure devient incomparable*. Cette campagne date du **2026-08-12** ; les repères
du §21 ont été mesurés le **15/08**, après notamment le revirement de la règle de classement
du 14/08 (quantification du SEEL de 0,1 nm à 0,01 nm) et le bonus block-aware. Et ces
gagnantes-ci ne sont pas des stratégies **à 6 blocs**, qui sont ce que les repères rapportent.

🔑 **Ce que cette campagne établit reste entièrement valide, parce qu'il est RELATIF** : la
dispersion (±1,5 % sur le 48c, ±9,8 % sur le 35c) et le fait que **l'identité de la gagnante
change à chaque profondeur**. Ce sont des rapports mesurés à protocole fixé dans une même
campagne — exactement ce que la règle 2 du §28 de `CLAUDE.md` autorise. **Seules les valeurs
absolues sont hors comparaison.**


Entre N = 300 et N = 500, la classe d'équivalence SEEL ne partage que **2 membres sur 5**.

> **La profondeur achète de la précision sur un nombre déjà précis, et elle ne peut pas
> acheter ce qui bouge réellement.**

Ce n'est pas un défaut de la mesure, **c'est le résultat** : les stratégies de tête sont
réellement **interchangeables** — même SEEL, même rendement de 100 %. Il n'y a rien à
départager, et c'est précisément pourquoi §22 prescrit de déclarer l'égalité au lieu
d'acheter des tirages. §24-26 le disait sur les scores ; ceci le dit sur la **réponse**.

### 🔒 LA RECOMMANDATION — N = 300, posé le 2026-08-13

🔴 **Et le critère n'est PAS celui qu'on croit. Ne le rejuge pas sur la précision du
score.** Ma première recommandation était N = 150, sur ce critère-là, et elle était juste
sur ce critère : le SEEL est stable à ±1,5 % dès N = 50, donc la profondeur n'y sert à rien.

**Ce qui décide, c'est le filtre de plantage.**

⚠️ **Nuance ajoutée après validation du correctif 1, et elle affaiblit l'argument — ne la
saute pas.** Une version antérieure disait que le filtre gouverne *quelles stratégies
existent*. **Ce n'était vrai qu'avant le correctif 1.** Depuis, la population est fixée par
le criblage : le filtre de la passe complète ne gouverne plus que **ce qui figure au
classement final**, c'est-à-dire la liste dans laquelle l'utilisateur choisit. Une bonne
stratégie rejetée par malchance n'est plus perdue pour la recherche — seulement pour le
tableau. C'est moins grave, et cela reste un défaut.

| N | bonne à 3 % rejetée **à tort** | mauvaise à 7 % qui **passe** | repêchées au classement |
|---|---|---|---|
| 50 | **18,9 %** | **31,1 %** | **24 %** (83/343) |
| 150 | 8,3 % | 16,9 % | — |
| **300** | **3,9 %** | **6,5 %** | **8 %** (19/229) |
| 500 | 1,0 % | 2,8 % | 7 % (19/284) |

**Le genou est à 300.** 150 → 300 divise par deux les deux erreurs du filtre et fait tomber
le repêchage de 24 % à 8 %, pour **+7 min sur les deux composants réunis** (41 contre 33) —
la part fixe domine tellement que la profondeur est bon marché. 300 → 500 coûte +10 min de
plus et ne gagne presque rien.

⚠️ **Ce chiffre est conditionné au correctif 2 (§33), qui n'est PAS fait.** Une fois le
seuil porté sur une borne de confiance, une profondeur faible cessera de rejeter à tort et
deviendra seulement **permissive**. Le choix redeviendra une question de finesse, et 150
pourrait suffire de nouveau. **Ça se remesurera, ça ne se déduira pas.**

📏 Posé dans les deux JSON le 2026-08-13 : `robustness_num_runs = 300`.

### 🔴 POURQUOI LE NOMBRE DE STRATÉGIES CLASSÉES VARIE — élucidé le 2026-08-13

Il varie de **229 à 376** entre les quatre profondeurs. Le criblage, lui, est **rigoureusement
identique** : 905 stratégies criblées, même découpage bloc par bloc, aux quatre profondeurs.
Ce n'est donc pas le criblage. La chaîne est la suivante, et elle a trois maillons.

#### Maillon 1 — la passe COMPLÈTE alimente la recherche du nombre de blocs suivant

`certus_strat_workers.py:1292` : les résultats de la passe complète — celle qui tourne à
`N` — passent par `derive_strategies_exhaustive(..., top_k_parents=20)`, et deviennent les
**candidates héritées** du nombre de blocs suivant. **`N` atteint donc la population, par
héritage.** Ce n'est écrit nulle part et personne ne l'avait vu.

#### Maillon 2 — le filtre de plantage compare un taux ESTIMÉ à un seuil FIXE

`certus_strat_robustness.py:2018` :

```python
if crash_rate_max >= CRASH_RATE_TOLERANCE:   # 0,05
    final_score = float("inf")               # -> jetee par _filter_finite_scores
```

Le taux est estimé sur **`N` tirages**. Sa sensibilité dépend donc de `N` :

| vrai plantage | rejetée à N=50 | N=150 | N=300 | N=500 |
|---|---|---|---|---|
| 3 % — **bonne**, sous le seuil | **18,9 %** ❌ | 8,3 % | 3,9 % | 1,0 % |
| 7 % — mauvaise | **68,9 %** | 83,1 % | 93,5 % | **97,2 %** |
| 10 % — très mauvaise | **88,8 %** | 98,6 % | 99,9 % | 100 % |

🔴 **À N = 50, près d'un tiers des stratégies qui plantent réellement 7 % du temps passent le
filtre** — et deviennent parents héritées. Et une bonne sur cinq à 3 % est rejetée à tort.

📏 **La granularité l'explique** : à N = 50 le taux mesuré est quantifié par pas de **2 %**,
donc **aucune** stratégie ne peut se situer entre 0 et 2 %. Mesuré dans les classements :
`0 < p < 2 %` compte **0** stratégie à N = 50, contre 88 à 150 et 127 à 500. Il faut
**3 plantages sur 50** pour franchir un seuil de 5 %.

#### Maillon 3 — l'écart se compose le long de la chaîne des blocs

📏 Stratégies retenues par la passe complète, bloc par bloc :

```
N= 50 | 1:13  2:54  3:76  4:31  5:30 ...
N=150 | 1:16  2:50  3:61  4:26  5:59 ...
N=300 | 1: 9  2:10  3: 0  4:52  5:14 ...   <- ZERO au bloc 3
N=500 | 1: 9  2:10  3: 0  4:59  5:71 ...
```

Les deux premiers blocs perdent déjà 5 stratégies, le troisième s'effondre à **zéro**, et
l'écart se propage jusqu'aux deux derniers blocs où les survivantes tombent de `12, 9` à
`2, 3`.

#### 🔑 Ce qu'il faut en retenir, et c'est plus important que le décompte

> **Deux runs à profondeurs différentes ne comparent pas deux précisions sur la même
> recherche. Ils comparent DEUX RECHERCHES DIFFÉRENTES.**

Et le sens est celui-ci : **une profondeur faible propage des stratégies qui plantent
vraiment.** Ce n'est pas le filtre qui est cassé — c'est qu'à N = 50 il ne peut pas faire
son travail, et que le système ne le signale pas.

⚠️ **Conséquence sur la conclusion de la campagne** : j'avais laissé deux causes possibles à
l'instabilité de la gagnante. **Ce sont les deux**, et la seconde est identifiée. La stabilité
du SEEL à ±1,5 %, elle, n'est pas affectée : elle est mesurée sur la gagnante finale, dont le
plantage vaut 0,000 partout.

#### 🔴 Et un second constat, trouvé en chemin

**Des stratégies à 100 % de plantage figurent dans les classements**, aux quatre profondeurs.
C'est le repli obligatoire de `_filter_finite_scores` (ligne 1152) : quand **aucune** stratégie
d'un bloc ne survit au filtre, il les réinjecte toutes avec un score fini plutôt que de rendre
une liste vide. Le comportement est délibéré et documenté — mieux vaut la moins risquée que
`RESULT=None` — mais **rien dans le classement ne distingue une stratégie repêchée d'une
stratégie qui a réellement passé le filtre**. C'est le motif de §24-37 : le résultat a l'air
sain. Correctif à faire : remonter un drapeau `fallback_rescued` dans le résultat de
stratégie, comme `n_layers_forced`.

---

## 23bis. 🔴 LE CORRECTIF 2 — MESURÉ, MAIS NON CONSIGNÉ, DONC INEXPLOITABLE

🔴 **Il y a désormais TROIS états à distinguer, pas deux, et c'est tout l'objet de cette
section :** *écrit*, *mesuré*, et **mesuré-mais-non-consignable**. Le correctif 2 est dans le
troisième, qui est le plus traître, parce qu'il ressemble au second.

Le code existe et il est couvert par 37 tests unitaires. **La campagne `gate` A TOURNÉ le
2026-08-14** — 6 runs sur 6, 55 min 16 s, artefacts sur le disque. Et pourtant :

> **Rien ne dit encore que ce correctif améliore quoi que ce soit**, parce que les 6 runs sont
> sortis **FAILED** : `crash_gate_confidence` est dans `_OVERRIDES` mais **absente de
> `TRACED_KEYS`** (`scripts/probe_anchor_noise_pipeline.py`), donc la valeur a été **appliquée
> au run et jamais écrite dans `r["config"]`**. `run_campaign.py` ne peut pas vérifier que le
> run a fait ce qu'on lui demandait, et `analyse_gate.py` lit une clé absente : il est inerte.

**C'est le point 7 de §24 qui se rouvre** — *« un run qui ne consigne pas sa configuration
n'est comparable à rien »*. Répare la traçabilité **avant** de relancer : la clé dans les
**deux** listes, et dans le nom du fichier de sortie.

⚠️ **Et deux résultats de cette campagne sont à expliquer avant d'être crus** : les bras
porte-OFF et porte-armée rendent un score **bit-identique** (`0.006138704636203437`) avec des
gagnantes différentes, et le témoin C1 **n'a pas reproduit** sa référence
(`0.00611049163380679` contre `0.006151532415266679` attendu à ~1e-11). Détail et conduite à
tenir : bloc **EN COURS** en tête de document.

| | |
|---|---|
| **Le paramètre** | `crash_gate_confidence`, défaut **0,0 = inactif**. Lisible depuis le JSON, l'interface et `CERTUS_CRASH_GATE_CONF`. Valeur à armer : **0,95** |
| **Le code** | `_crash_gate_rejects` et `crash_rate_lower_bound`, dans `certus_strat_robustness.py` |
| **Les tests** | `tests/unit/test_strat_crash_gate_confidence.py`, **37 tests**, dont C1 sur quatre formes de valeur inactive |
| **La campagne** | `scripts\run_campaign.py gate` — **6 runs**, chaque bras avec son témoin. 📏 Mesurée le 2026-08-14 : **55 min 16 s**, et non ~3 h 30 (`reports/probe_runs.tsv`, colonne `run_s`). 🔴 **Les 6 runs sont sortis FAILED** pour un défaut de traçabilité : lis le bloc EN COURS en tête de document avant de la relancer. |
| **La lecture** | `scripts\analyse_gate.py` — imprime les quatre questions et **le test qui va avec chacune** |
| **L'ordre de mission** | `GEMINI_TODO.md`, réécrit pour cette campagne — ⚠️ **fichier supprimé le 2026-08-16**, campagne close |

🔑 **Une propriété prouvée par test, et elle sert de garde-fou à la lecture** : la porte
armée est **toujours plus permissive**, jamais moins. La borne inférieure est sous
l'estimation ponctuelle, donc le correctif ne peut qu'**ajouter** des stratégies au
classement. **Si un bras en retire, c'est un défaut, pas un résultat.**

### Le défaut, en une ligne

`certus_strat_robustness.py:2018` compare une **estimation bruitée** à un **seuil dur** :

```python
if crash_rate_max >= CRASH_RATE_TOLERANCE:   # 0,05
    final_score = float("inf")               # -> jetee, et perdue comme parent
```

> **Un filtre dont le verdict change avec la profondeur n'est pas un filtre, c'est un
> échantillonneur.**

📏 Mesuré le 2026-08-13, probabilité de rejet selon le **vrai** taux de plantage :

| vrai taux | N=50 | N=150 | N=300 | N=500 |
|---|---|---|---|---|
| 3 % — **bonne**, sous le seuil | **18,9 %** ❌ | 8,3 % | 3,9 % | 1,0 % |
| 7 % — mauvaise | 68,9 % | 83,1 % | 93,5 % | 97,2 % |

Et au criblage, où c'est pire parce que la granularité est grossière :

| `n_screen` | plantages requis | rejet à tort à p=1 % | à p=3 % |
|---|---|---|---|
| **10** | **1 sur 10** | **9,6 %** | **26,3 %** |
| **25** (retenu) | 2 sur 25 | 2,6 % | 17,2 % |
| 50 | 3 sur 50 | 1,4 % | 18,9 % |

⚠️ **Note la colonne p = 3 % : elle ne s'améliore PAS avec la profondeur** — 26, 17, 19,
18 %. C'est inhérent au seuil dur : à 3 % on est trop près de 5 % pour qu'un comptage
tranche. **Seul le correctif 2 la traite.**

### Ce qu'il faut écrire

Ne rejeter que si l'on est **confiant** que le vrai taux dépasse la tolérance : borne
inférieure de Clopper-Pearson à 95 %. Conséquences, et elles sont toutes désirables :

- une bonne stratégie n'est **jamais** rejetée par malchance, à aucune profondeur ;
- à faible profondeur le filtre rejette peu — c'est **honnête**, on ne sait pas ;
- il se resserre tout seul quand la profondeur monte, **sans changer de règle**.

🔒 **Le seuil de 5 % ne bouge pas.** C'est le « 95 % des dépôts fonctionnent » de §15, une
spécification 👤. C'est l'**estimateur** qui est en cause, jamais la valeur.

### Les précautions

- 🔴 **Ça change tous les résultats. Ce n'est PAS un correctif C1**, et il ne faut pas
  exiger la bit-identité.
- 🔴 **Un run de validation à lui seul**, contrainte C3 — pas mélangé au correctif 1.
- ⚠️ **Le repli de `_filter_finite_scores` reste nécessaire** : la borne de confiance rejette
  moins, donc il se déclenchera moins, mais il ne devient pas inutile.
- 🔑 **Ce qu'il faut remesurer après** : le tableau de §33. Une borne de confiance rend une
  profondeur faible **sûre mais permissive** ; N = 300 pourrait redevenir surdimensionné.
  **Remesure, ne déduis pas.**

---

## 23ter. 🔒 LE CORRECTIF 1 — la recherche ne dépend plus de la profondeur de notation

**Fait le 2026-08-13.** L'invariant :

> **`N` (`robustness_num_runs`) est un réglage de MESURE. Il ne doit décider d'aucune
> candidate.**

### Ce qui a changé

`certus_strat_workers.py` : les **parents hérités** du nombre de blocs suivant sont dérivés
des **survivantes du criblage** (`screening_survivors`, à `n_screen` fixe) et non plus des
résultats de la passe complète (à `N`). Le contrat de blocs est revérifié au passage, parce
que `strategies_this_step` l'était et que ces survivantes-là ne l'étaient pas.

### 🔑 Le test qui le garde est une ÉGALITÉ

`tests/unit/test_strat_search_is_depth_independent.py`, 4 tests, dont **3 échouent sur le
code d'avant**. Ils vérifient que les parents ne viennent pas de la passe complète, que les
survivantes remontent, que le contrat est revérifié, et que **les deux appels de criblage
tournent toujours à `n_screen`** — cette dernière est un garde-fou contre une récidive par
une autre porte.

### 🔴 CE QU'IL FAUT COMPARER — et j'avais écrit la mauvaise grandeur

Une première version de cette section demandait de comparer les **stratégies retenues par
bloc**. **C'est faux, et ça aurait fait conclure à l'échec du correctif.** Ces retenues
sortent de la passe **complète**, donc elles dépendent de `N` — et c'est **normal** : le
filtre de plantage y est plus sévère à profondeur croissante. C'est de la **notation**.

| grandeur | doit-elle être N-indépendante ? | où la lire dans le log |
|---|---|---|
| **survivantes du criblage**, par bloc | ✅ **OUI** — c'est la recherche | `Full pass on N survivors` |
| **parents hérités**, par bloc | ✅ **OUI** — c'est la recherche | `Inheritance: X derived from Y` |
| stratégies **retenues**, par bloc | ❌ non, et ce serait un défaut qu'elles le soient | `Completed. N retained` |
| classement, scores, `RESULT` | ❌ non — c'est ce que `N` sert à mesurer | — |

📏 **Avant le correctif**, les survivantes divergeaient sur les deux derniers blocs :
`10 10 20 20 12 11 12 12 12 9` à N = 50 et 150, contre `... 12 12 2 3` à N = 300 et 500.

### 🟢 VALIDÉ LE 2026-08-13 — deux runs, facteur DIX de profondeur, égalité exacte

```
LA RECHERCHE — identique, et c'est une EGALITE, pas une concordance
  survivantes  N=50   [10, 10, 20, 20, 12, 11, 12, 12, 12, 9]
               N=500  [10, 10, 20, 20, 12, 11, 12, 12, 12, 9]
  heritage     identique sur les 10 blocs, au couple (derivees, parents) pres

LA NOTATION — depend de N, et ce serait un defaut sinon
  retenues     [5,12,41,31,45,42,78,0,27,19]  contre  [5,5,34,24,94,40,76,0,27,19]
  classees     300 contre 324          RESULT  +0,86 %
  SEEL         0,587 nm contre 0,582 nm    -> +/-0,4 %
```

**Avant le correctif, les deux derniers blocs tombaient de `12, 9` à `2, 3`.** Ils sont
maintenant identiques. Et `RESCUED` vaut **41 dans les deux runs** — le repêchage aussi est
devenu N-indépendant, puisqu'il dépend de la population, désormais fixe.

⚠️ **Ne lis pas les huit premiers blocs comme une confirmation** : ils étaient identiques
même avec le défaut. L'écart se **compose** le long de la chaîne d'héritage et n'apparaît
qu'aux derniers maillons. **Seuls les blocs 2 et 1 tranchent** — et c'est là que la mesure
compte.

### ⚠️ Ce que le correctif 1 a PÉRIMÉ

**§31 recommandait `n_screen_runs = 10`, sur la foi de §24-27** — « cribler à 10 tirages
ne perd rien : 133 classées contre 228, même gagnante, `RESULT` bit-identique ». Cette
mesure a été faite quand le criblage ne choisissait que les survivantes de la passe
complète. **Il choisit désormais aussi les parents**, donc une stratégie tuée par malchance
au criblage est perdue pour tout le reste de la recherche. **La mesure ne couvre plus le
rôle. `n_screen` reste à 25** — voir le tableau de §33.
