# EMPLOYER PLEINEMENT LE RATE — et mélanger POEM, niveau absolu et Rate

> 👤 **2026-08-18** : *« je reste persuadé que le rate est sous-employé, il faut lancer des idées
> pour lui permettre d'être pleinement utilisé »*, puis *« mixer POEM, trigger et rate est
> sûrement la solution d'avenir. En testant plein de stratégies, on arrivera à comprendre comment
> utiliser intelligemment les 3. »*

Ce dossier fait **autorité** sur ce sujet. `CLAUDE.md` n'en garde qu'un renvoi.
Instrument de l'audit : `scripts/audit_rate.py`, rejouable.

---

## 1. 🔴🔴 CORRECTION DU 2026-08-19 — LE « FACTEUR 175 » ÉTAIT UN PARADOXE DE SIMPSON

⚠️ **La première rédaction de ce dossier annonçait :** *« le Rate fait 64 % de l'offre et 0,15 %
des déposables, une stratégie optique a 175 fois plus de chances d'être déposable »*. **Ce chiffre
est un artefact d'agrégation et il est retiré.**

📏 **Ce qui l'a produit** : `scripts/audit_rate.py` a **poolé 27 runs hétérogènes** — des runs où
l'optique réussit et le Rate échoue, mélangés à des runs où les deux échouent à 100 %. Le pool
était alors dominé par les composants barrières. Les runs `deep` de la nuit du 18 au 19 ont changé
la composition du pool, et le même calcul rend désormais **5×** au lieu de 175×. **Un chiffre qui
bouge d'un facteur 35 quand on ajoute des données n'était pas une mesure du Rate.**

📏 **L'analyse STRATIFIÉE, run par run** — la bonne :

```
mediane du ratio de deposabilite optique/Rate, INTRA-run : 0,99x   (n = 7 runs comparables)
```

**Autrement dit : à l'intérieur d'un même run, le Rate est déposable aussi souvent que l'optique.**
Sur `35c` et `48c` en `deep`, il l'est même **plus** — 100 % contre 92,8 à 98,9 %.

### 🔑 CE QUE LA MESURE DIT VRAIMENT — un coût qui CROÎT AVEC LA PROFONDEUR

📏 Comparaison du **meilleur SEEL Rate** au **meilleur SEEL optique**, dans chaque run où les deux
existent :

| composant | couches | meilleur optique | meilleur Rate | écart |
|---|---|---|---|---|
| **35c** | 35 | 0,482 / 0,479 / 0,525 | 0,488 / 0,485 / 0,528 | **+0,6 à +1,3 %** |
| **48c** | 48 | 0,173 / 0,170 | 0,192 / 0,183 | **+7,8 à +10,9 %** |
| **75c** | 75 | 0,260 / 0,272 | 0,316 / 0,333 | **+21,6 à +22,1 %** |

> 🔑 **Le coût du Rate n'est pas constant : il croît avec le nombre de couches.** ~1 % à 35
> couches, ~9 % à 48, ~22 % à 75. Trois composants, motif monotone.

**Le mécanisme le plus plausible, et il est cohérent avec le reste du dépôt** : une couche Rate
casse le bloc et fait perdre la compensation POEM pour l'aval. Sur un empilement court, cette
compensation vaut peu ; sur un empilement long, l'erreur accumulée est grande et la perdre coûte
cher. C'est la même grandeur que §24-44 décrit quand il parle de « perte de mémoire ».

⚠️ **Trois composants, une graine, et le mécanisme n'est pas démontré** — seulement cohérent. Une
quatrième profondeur (le 99c, 99 couches) trancherait, mais il ne rend aucun déposable, donc la
comparaison y est impossible.

### 🟢 La seule cellule où le Rate gagne, et l'écart est nul

| cellule | meilleur optique | meilleur Rate | écart |
|---|---|---|---|
| **`75c` à 1 nm** | 0,373 | **0,371** | **−0,3 %** |

**Une sur huit comparables**, et l'écart est **très en dessous du bruit statistique** (σ ≈ 6 %,
§24-26). 🔴 **La rédaction d'hier en faisait un point d'appui — c'était trop.** Ce que cette
cellule montre reste néanmoins réel : c'est la seule où la fente fine double le bruit optique, et
la seule où le Rate n'est pas pénalisé. **Direction, pas preuve.**

### 🔴 L'analyse APPARIÉE est impossible avec les artefacts existants

Le test le plus fort serait de comparer chaque variante Rate **à son propre parent** — l'`origin`
porte bien `RATE_L29(from 900000285)`. 📏 Mais le champ `id` vaut **`None` dans tous les
artefacts** : la sonde lisait `st.get("id")` alors que le dictionnaire de stratégie porte
`strategy_id`. **Corrigé le 2026-08-19** ; les artefacts déjà produits restent inexploitables pour
cet appariement, et il faudra un run neuf.

---

## 2. 🔑 LA REFORMULATION QUI CHANGE TOUT

⚠️ **Cette section était écrite sur le facteur 175, désormais retiré (§1).** Ce qui suit reste
valide, mais l'échelle a changé : le coût du Rate n'est pas un facteur 175 sur la déposabilité,
c'est une **pénalité de SEEL de 1 à 22 % qui croît avec la profondeur de l'empilement**. Les trois
mécanismes ci-dessous restent ceux que le code documente, et le dernier explique pourquoi la
pénalité croît —

| coût d'une couche Rate | source |
|---|---|
| **aucune auto-compensation** — l'erreur passe en boucle ouverte à la couche suivante | §22 |
| la précision du facteur suit **1/√n** avec le nombre de couches de référence du matériau | A24 |
| il **casse le bloc** : les ancres POEM sont perdues pour tout l'aval | §22 |

> 🔑 **Le Rate ne gagne pas en moyenne, et il ne le doit pas. Il gagne là où l'optique est pire
> que lui. La question n'est donc pas *« comment employer plus de Rate »* mais *« comment
> identifier les couches où l'optique est perdue »*.**

🔑 **Et le troisième mécanisme explique la pénalité croissante mesurée au §1** : casser le bloc
fait perdre la compensation pour tout l'aval. Sur 35 couches cette compensation vaut peu (+1 %),
sur 75 elle vaut beaucoup (+22 %). **C'est un argument DIRECT pour placer le Rate tard dans
l'empilement**, ce que `_rate_candidate_layers` fait déjà en triant les frontières les plus
profondes d'abord — une des rares choses que le code fait pour la bonne raison.

Et c'est exactement ce que le code ne fait pas — voir la contradiction C.

---

## 3. Les quatre contradictions relevées

### 🔴 A. Le plafond de 3 variantes n'applique ni la consigne qu'il cite, ni son contraire

`RATE_MAX_VARIANTS_PER_STRATEGY = 3` (`certus_strat_robustness.py:506`) porte cette
justification :

> *« 👤 asked for the trial "on the 10 best strategies", not on everything: an unbounded
> expansion costs a factor 6 on the whole Monte-Carlo. »*

Or `_expand_with_rate_variants` étend **toutes** les stratégies, à 3 variantes chacune. Le code
ne fait donc **ni** l'essai sur les 10 meilleures, **ni** l'expansion complète.

📏 Le coût mesuré de ce compromis : **12 923 variantes Rate** produites, dont 20 déposables.
**Un plafond à 40 sur les 50 meilleures coûterait 2 000 variantes au lieu de 12 923, et
explorerait chaque parent treize fois plus profondément.** Le plafond actuel dépense beaucoup
pour explorer peu.

### 🔴 B. Le régime où le Rate serait le plus utile est celui où il n'est jamais offert

`RATE_MIN_LAYERS_PER_BLOCK = 3.0` rend **zéro candidate** aux stratégies dont les blocs font
moins de 3 couches. Une stratégie qui surveille **couche par couche** n'a donc jamais eu une
seule variante Rate.

🔴 Or §24-40 a mesuré que **le monitoring couche par couche gagne sur 2 graines sur 5** à
l'incertitude d'indice réelle. Le régime que la mesure désigne comme gagnant est celui dont le
Rate est exclu par construction.

⚠️ La raison de l'exclusion est bonne et il ne faut pas la perdre : sur 48 blocs, *chaque* couche
est une frontière, et la sélection dégénère en balayage exhaustif — 47 variantes pour une seule
stratégie, coût Monte-Carlo ×6. **Ce qu'il faut n'est pas de lever le plancher, c'est de
remplacer le critère de frontière par un critère qui discrimine encore quand tous les blocs font
une couche** — voir C.

### 🔴 C. Le placement cherche où le Rate COÛTE le moins, jamais où il est NÉCESSAIRE

`_rate_candidate_layers` : *« Layers where a Rate is CHEAPEST: the last layer of each block. »*

CLAUDE.md §22 pose l'autre critère, et le dit déjà en toutes lettres :

> *« Le critère 3 ne cherche pas les couches qui ont BESOIN du Rate, il cherche celles où il ne
> COÛTE rien. Ce sont deux questions différentes et le code ne répond qu'à la seconde. »*

Le critère de besoin est `swing < SWING_MIN` — une couche dont la dynamique optique est trop
pauvre pour être surveillée. **Il n'a jamais été essayé comme critère de placement.**

### 🟠 D. La dernière couche est exclue sur deux effets opposés, dont aucun n'est mesuré

> *« It has no successor, so the downstream cost is nil there too — but it is also the last chance
> to correct everything accumulated since layer 1, and the two pull opposite ways. »*

Deux effets contraires non mesurés ne justifient pas une exclusion : **ils justifient une
mesure**. A24 le dit, elle n'a jamais eu lieu.

---

## 4. 🔴 LE BLOCAGE STRUCTUREL POUR MÉLANGER LES TROIS

👤 veut mélanger **POEM, niveau absolu et Rate**. Ce n'est pas possible aujourd'hui, et la raison
est nette :

| méthode d'arrêt | granularité actuelle |
|---|---|
| **Rate** | 🟢 **par couche** — `rate_layers`, une liste d'indices |
| **POEM contre niveau absolu** | 🔴 **GLOBAL** — `poem_enabled` est un booléen unique pour tout le run (`certus_strat_robustness.py:1882`, propagé jusqu'à `certus_strat_batch.py:78`) |

Il n'existe donc **aucun moyen** d'exprimer *« couche 12 en POEM, couche 13 au niveau absolu,
couche 14 en Rate »*. Le mélange que 👤 décrit est inexprimable dans la structure de données
actuelle, pas seulement inexploré.

🔑 **C'est le vrai chantier de fond**, et il est plus lourd que les trois autres : `poem_enabled`
traverse le noyau jusqu'aux kernels compilés. Le rendre par couche demande de le passer en tableau
booléen — la même forme que `rate_flags`, qui montre que c'est faisable.

---

## 5. Le plan, par valeur décroissante

### 1️⃣ Placer le Rate là où il est NÉCESSAIRE — le levier qui attaque le mécanisme

**L'argument** : le facteur 175 dit que le Rate est coûteux ; la cellule `75c à 1 nm` dit qu'il
gagne quand l'optique est mauvaise. Le placer sur les couches à **swing faible** est la seule
action qui aligne le critère du code sur le mécanisme mesuré.

**Ce qu'il faut écrire, vérifié dans le code le 2026-08-19** : la donnée n'est PAS déjà
disponible au bon endroit, contrairement à ce que cette section affirmait initialement. Le swing
par (couche, λ) est une **variable locale** de `_select_candidates_phase_a`
(`certus_strat_service.py:892`), calculée par λ candidate puis jetée dès qu'une λ est choisie
pour le bloc. Rien ne la conserve jusqu'à `_expand_with_rate_variants`, qui s'exécute après la
Phase B sur des stratégies déjà figées.

🔒 **Le chemin vérifié, empreinte d'UN SEUL FICHIER.** `opti_results` — déjà reçu par la fonction
appelante de `_expand_with_rate_variants` — porte déjà `nominal_matrix_cache` et `all_wls`
(`certus_strat_pipeline.py:105-106`), exactement comme il porte déjà `clues_at_wl`, lu à la ligne
399 de `certus_strat_robustness.py`. Il suffit de les extraire à côté, de les passer à
`_expand_with_rate_variants`, et d'appeler **la même fonction canonique**
`calculate_dynamics_ULTIMATE` — interdit 7 respecté, pas de TMM réimplémentée — restreinte à
**une seule λ** (celle que la stratégie a déjà choisie) au lieu de toute la grille. Aucun
générateur de variantes ni aucun schéma de stratégie n'a besoin d'être touché.

⚠️ **Le coût n'est pas mesuré.** Contrairement au criblage Phase A, il faut évaluer chaque
couche de chaque stratégie survivante — pas seulement les frontières de bloc — pour repérer une
couche à faible swing n'importe où dans le bloc. Sur `75c` (~900 survivants × 75 couches),
~65 000 évaluations TMM à λ fixe. Probablement de l'ordre de la dizaine de secondes en numba
compilé, mais **à chronométrer avant d'écrire quoi que ce soit d'autre** — c'est le premier pas,
pas une supposition.

**Le test qui tranche** : rejouer `75c à 1 nm` — la cellule où le Rate gagne déjà — et compter les
déposables Rate. **Critère à écrire avant** : le placement par besoin doit faire mieux que
10/12 sur cette cellule, sinon la frontière de bloc suffisait.

⚠️ **Et il entre comme COÛT, jamais comme couperet** (§22, §24-28). Une couche à faible swing
reste déposable en optique ; on ajoute une candidate, on n'impose pas un choix.

### 2️⃣ Lever le handicap de la Phase A — bon marché, et honnêtement incertain

**L'argument** : la Phase A ignore `rate_flags`, donc la λ de la couche `i+1` est choisie en
supposant un historique que la couche Rate `i` a détruit (§27). **64 % de l'offre est jugée avec
un choix de λ qui n'est pas le sien.** Le correctif tient en deux lignes : passer `rate_flags` et
forcer `block_start_running = i_layer` après une couche Rate.

🔴 **Mais je ne crois pas que ça explique le facteur 175, et il faut le dire.** L'effet est borné
à **une couche** par couche Rate — les suivantes héritent normalement du nouveau bloc. Et 👤 avait
déjà jugé : *« relancer la Phase A ne changerait pas grand-chose, on est dans la subtilité »*.

**Le test qui tranche** : une cellule rejouée avec le correctif. Si le taux de déposabilité Rate
ne bouge pas de 0,15 %, le handicap n'est pas la cause et on cesse d'en parler.

### 3️⃣ Le multi-Rate — ✅ **déjà outillé le 2026-08-18**

Deux paramètres, **inactifs à leurs valeurs par défaut** :

```
rate_max_layers_per_variant     defaut 1   -- chemin historique, bit pour bit
rate_max_variants_per_strategy  defaut 3   -- RATE_MAX_VARIANTS_PER_STRATEGY
```

🔒 **Règle d'or vérifiée** : à ces défauts, implicites ou explicites, la fonction rend les mêmes
variantes, les mêmes identifiants et les mêmes étiquettes `origin` qu'avant.

Au-delà de 1, les combinaisons sont énumérées par taille croissante, les frontières profondes
d'abord, et **la combinaison entière est toujours ajoutée** — c'est la sonde la moins chère de
*« et si on passait en Rate toutes les frontières possibles ? »*.

⚠️ **La restriction levée était un argument d'ATTRIBUTION** — *« deux couches Rate interagissent,
on ne saurait pas laquelle agit »*. C'est vrai et sans importance ici : la question posée est
d'**existence**, pas d'attribution.

### 4️⃣ Rendre `poem_enabled` par couche — le chantier de fond

**L'argument** : c'est la seule action qui rende la phrase de 👤 exprimable. Sans elle, « mélanger
les trois » restera une intention.

**Le coût** : `poem_enabled` traverse le noyau jusqu'aux kernels. Le passer en tableau booléen
suit exactement le chemin de `rate_flags`, qui prouve que la forme fonctionne.

📌 **À faire après 1 et 2**, parce que mélanger trois méthodes dont une est mal placée et une mal
jugée ne produirait qu'un espace de recherche plus grand et tout aussi mal orienté.

---

## 6. Ce qu'il ne faut PAS faire

| | |
|---|---|
| 🔴 **lever `RATE_MIN_LAYERS_PER_BLOCK` sans remplacer le critère** | on retombe sur le balayage exhaustif mesuré : 47 variantes pour une stratégie, coût ×6 |
| 🔴 **faire du Rate un couperet** | §22 : les heuristiques sont des diagnostics, pas des filtres. §24-28 : chaque générateur gagne dans au moins un régime |
| 🔴 **conclure du 99c** | 99 multiplicateurs entiers sur 99 : configuration singulière pour POEM, donc terrain biaisé en faveur du Rate |
| 🔴 **placer le Rate à la marge la plus faible** | tenté le 2026-08-12, **annulé le même jour**. La mesure portait sur une propriété de la STRATÉGIE et la règle ordonnait des COUCHES — deux grandeurs différentes |
| 🟠 **augmenter le plafond sans réduire le nombre de parents** | 12 923 variantes pour 20 déposables : le problème n'est pas le volume |

---

## 7. Le banc d'essai naturel

**`75c` à 1 nm.** C'est la seule cellule des 27 où le Rate gagne, et où 10 des 12 déposables sont
des variantes Rate. Toute amélioration du Rate doit s'y voir **en premier** ; une action qui n'y
change rien ne changera rien ailleurs.

Coût : une cellule, ~35 min en `fast`, ~2 h en `deep`.

⚠️ Et le contrôle qui va avec : **`75c` à 2 nm**, où le Rate ne gagne pas. Une action qui
améliorerait le Rate à 1 nm **et** à 2 nm serait suspecte — elle agirait sur autre chose que le
mécanisme identifié.
