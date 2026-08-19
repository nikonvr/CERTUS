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

## 3bis. 🟢🟢 L'HYBRIDE OPTIQUE-PUIS-RATE REND LE ×2 FABRICABLE — mesuré le 2026-08-19

> 👤 : *« avant les couches i, un filtre le plus parfait possible en tout optique, puis les
> couches i+1 à 75 en rate. Est-ce naïf ? »*

**Non.** 📏 `r75x2` à 2 nm, `fast`, graine 42, 36 min :

| | offertes | **déposables** | `crash_min` |
|---|---|---|---|
| base, sans queue | 404 | **0** | **100,00 %** |
| **avec balayage de queue** | 1 194 | **7** | **4,00 %** |

🔒 **L'attribution est propre** : parmi les 1 194, le meilleur plantage **hors variantes de
queue** reste **100,00 %**. Les 7 déposables sont toutes des queues Rate. Aucune ambiguïté.

### 🔴 CE QUI SUIT A ÉTÉ RÉÉCRIT LE 2026-08-19 — la version d'avant se trompait de mécanisme

⚠️ **Ce paragraphe disait** : *« la coupure a un optimum tardif »*, *« sept filtres distincts,
sept scores distincts »*, et expliquait le gain par *« franchir en boucle ouverte la zone où la
dérive accumulée tue l'optique »*. 📏 **Les trois sont réfutés par les artefacts eux-mêmes**,
`reports/blocs_vs_plantage_r75x2_fast_s042_tail.json` et `..._tail46-55.json`, relus le
2026-08-19. Ce qui suit est ce qu'ils disent réellement.

#### 📏 Ce n'est pas une courbe en U, c'est une FALAISE

| coupure `i` | 70 | 67 | 64 | **61** | **58** | 55 | 52 | 49 | 46 | *aucune queue* |
|---|---|---|---|---|---|---|---|---|---|---|
| couches Rate | 5 | 8 | 11 | **14** | **17** | 20 | 23 | 26 | 29 | 0 |
| `crash_min` | 100 % | 100 % | 100 % | **100 %** | **4,00 %** | 4,00 % | 4,00 % | 4,00 % | 4,00 % | 100 % |
| déposables | 0 | 0 | 0 | **0** | **1** | 1 | 1 | 1 | 1 | 0 |
| SEEL | — | — | — | — | 0,735 | 0,701 | **0,689** | 0,717 | 0,752 | — |

🔑 **Tout bascule entre la coupure 61 et la coupure 58** — trois couches. Et **au-delà, allonger
la queue ne gagne strictement rien** : `crash_min` reste à 4,00 % de 58 jusqu'à 46, à la
décimale près. Une explication en « plus on couvre, mieux c'est » est incompatible avec un
plateau parfaitement plat sur 12 couches.

#### 🔴 Le mécanisme publié était FAUX, et voici ce qui le réfute

L'ancienne version disait que la queue Rate **franchit la zone où la dérive accumulée tue
l'optique**. Trois faits l'interdisent :

| fait mesuré | ce qu'il tue |
|---|---|
| la couche critique de **toutes** les déposables est la **39** | elle est **avant** la coupure, donc **restée optique**. La queue ne l'a jamais couverte |
| la couche critique dominante de la population est la **32** (48 variantes sur 113), à **toutes** les coupures | reculer la coupure de 55 à 46 ne la couvre pas davantage, et ne change rien |
| `crash_min` est **plat à 4,00 %** de la coupure 46 à la coupure 55 | couvrir 9 couches de plus ne gagne rien : ce n'est donc pas la couverture qui agit |

#### 🟢 Ce que le code dit, lui — et c'est vérifié ligne à ligne

`certus/physics/certus_strat_growth.py:654` : une couche Rate fait un **retour anticipé** avant
toute logique de déclenchement, et rend son épaisseur **sans sentinelle de plantage** (les deux
marges de comptage sortent à `1e18`). **Une couche Rate ne peut donc ni manquer son niveau, ni
mal compter ses points tournants.**

⚠️ **Sous une condition, ligne 640** : `if n_ref > 0`. S'il n'existe aucune couche de même parité
déposée avant, le chemin **retombe sur POEM** et la couche redevient plantable. Sans objet pour
une queue qui commence à 46, à connaître pour une couche Rate placée en tête d'empilement.

#### 🔑 LE MÉCANISME RÉEL : la queue ne répare rien, elle SUPPRIME des occasions de planter

Et il est bien plus étroit que ce que j'avais écrit :

1. Sur `r75x2` à 2 nm, **les 224 stratégies optiques plantent à 100 %**, sans exception.
2. **Une seule** en réchappe : celle à **75 blocs** — le monitoring **couche par couche** — et
   **uniquement** quand elle porte une queue Rate atteignant la couche 58.
3. Les couches **58, 59, 60** sont exactement ce que la coupure 58 couvre et que la coupure 61
   laisse optique. C'est là qu'elle échoue en boucle fermée.
4. Le résidu de **4,00 %** est la couche **39**, qu'aucune coupure testée n'atteint. D'où le
   plateau : une fois 58-60 neutralisées, il ne reste que 39, et rien n'y touche.
5. Mode de défaillance : **100 % « niveau d'arrêt hors d'atteinte »**, jamais de mécomptage.

#### 🔴 Et « sept filtres distincts » était trompeur

Il n'y a **qu'UNE architecture de monitoring** — la parente `75800`, à 75 blocs — déclinée en
cinq positions de coupure. Ce sont cinq **recettes** différentes, pas cinq solutions
indépendantes. ⚠️ La parente `75800` n'apparaît **nulle part dans le classement** : elle n'a
survécu qu'à travers ses enfants.

#### ⚠️ L'optimum à 52 n'est PAS établi

`crash_min` ne discrimine aucune coupure. Reste le SEEL, et il faut le lire avec son bruit :

| comparaison | écart | en σ | verdict |
|---|---|---|---|
| 52 (0,689) contre 46 (0,752) | +9,1 % | **1,25 σ** | indiscernables |
| 52 (0,689) contre 55 (0,701) | +1,7 % | 0,23 σ | indiscernables |

⚠️ **Ce σ est une extrapolation, pas une mesure.** Le seul chiffre mesuré est celui de §24-26 —
σ ≈ 6 % du score à N = 150, sur le **48 couches** — reporté ici en `1/√N` à N = 50 (σ ≈ 10,4 %
du score, donc ≈ 5,2 % du SEEL, donc ≈ 7,3 % sur une différence de deux). **Il n'a jamais été
mesuré sur `r75x2`.** Le retenir revient quand même à dire : **traite les cinq coupures comme
équivalentes** tant qu'un `premium` n'a pas tranché.

📌 Les valeurs `0,814 / 0,767 / 0,814 / 0,757 / 0,749` pour les coupures 28 à 41, citées dans la
version précédente, viennent d'un **artefact que j'ai écrasé** en changeant `TAIL_CUTS` sans
changer le nom de fichier. **Elles ne sont plus vérifiables et ne doivent plus être citées.**

### Ce que ça ne dit pas

| | |
|---|---|
| 🔴 **une seule architecture, pas sept** | tout descend de `75800`, à **75 blocs** — le monitoring couche par couche. C'est le vrai résultat : *ce qui sauve le ×2, c'est le monitoring par couche PLUS une queue Rate*, jamais l'un sans l'autre |
| 🔴 **`fast`, une graine, N non consigné** | §8 impose un rejeu `premium`, §24-46 une seconde graine. Et le bloc `config` de la sonde **n'enregistrait pas la profondeur** — corrigé le 2026-08-19, mais les artefacts existants ne la portent pas : le « 2/50 » est déduit du nom de mode |
| 🟠 **SEEL 0,689 reste élevé** | à comparer aux 0,625 que `deep` obtient sur le même composant à 1 nm. L'hybride rend fabricable une configuration qui ne l'était pas, il ne bat pas la meilleure connue |
| 🔴 **la règle d'exception n'est pas testée** | forme pure, sans couches optiques dans la queue. Trois tentatives ont échoué |
### 🟢🟢 L'EXPÉRIENCE APPARIÉE — la prédiction était posée d'avance, et elle tient

📏 Mesuré le 2026-08-19, `reports/blocs_vs_plantage_r75x2_fast_s042_chirurgical.json`, 1 195
stratégies. **La prédiction avait été écrite dans ce dossier avant que le run ne finisse** : le
Rate *chirurgical* sur 32/35/39 devait rendre **0 déposable**.

🔒 **Le contrôle de confusion passe d'abord** : les deux runs partagent **exactement les mêmes
127 parentes**, `75800` comprise, et le chirurgical en a bien produit **8 enfants**. Ce n'est
donc pas une population différente qui répond — seule **la place du Rate** change.

| couches mises en Rate | nb | `crash` | SEEL | couche critique |
|---|---|---|---|---|
| `[32]` — milieu | 1 | 100,00 % | — | 59 |
| `[32, 35]` — milieu | 2 | 100,00 % | — | 55 |
| `[32, 35, 39]` — milieu | 3 | 100,00 % | — | 74 |
| `[31, 32, 33]` — milieu | 3 | 100,00 % | — | 74 |
| `[34, 35, 36]` — milieu | 3 | 100,00 % | — | 65 |
| `31..36` — milieu | 6 | 100,00 % | — | 47 |
| `30..40` — milieu | 11 | 100,00 % | — | 51 |
| **`58..74` — QUEUE** | 17 | **4,00 %** | 0,735 | 39 |
| **`55..74` — QUEUE** | 20 | **4,00 %** | 0,701 | 39 |
| **`52..74` — QUEUE** | 23 | **4,00 %** | **0,689** | 39 |
| **`49..74` — QUEUE** | 26 | **4,00 %** | 0,717 | 39 |
| **`46..74` — QUEUE** | 29 | **4,00 %** | 0,752 | 39 |

🔴 **Onze couches en Rate au milieu — couvrant 32, 35 ET 39 — ne sauvent rien.** Là où
**dix-sept couches en queue** suffisent. Ce n'est donc ni le nombre, ni l'identité des couches
« qui plantent le plus » : **c'est la position terminale.**

#### 🔑 LE MÉCANISME, ÉTABLI — et il tient en une phrase

> **Une couche Rate supprime son propre plantage, mais lègue son erreur en boucle ouverte à
> tout ce qui la suit. Placée au milieu, elle déplace donc la défaillance vers l'aval ; placée
> en queue terminale, elle n'a plus d'aval à endommager.**

📏 **La colonne « couche critique » le montre directement** : Rate en `[32]` → échec en **59** ·
Rate en `31..36` → échec en **47** · Rate en `30..40` → échec en **51** · Rate en `[32,35,39]`
→ échec en **74**. **La défaillance recule systématiquement en aval du jeu Rate.** C'est
exactement le coût déjà écrit dans le code (`certus_strat_growth.py:653`, *« hands the cost to
the next layer, which loses its anchors »*) et la loi de profondeur du §1.

✅ **Et cela réconcilie tous les chiffres du dossier** :

| observation | ce que le mécanisme en dit |
|---|---|
| la falaise 61 → 58 | la parente `75800` a une zone réellement fatale en **58-60** ; toute coupure qui la laisse optique plante |
| le plateau plat à 4,00 % de 58 à 46 | une fois 58-74 neutralisées, il ne reste que la couche **39**, qu'aucune coupure n'atteint. Allonger la queue ne peut donc rien gagner |
| les couches 47 à 57 ne plantent jamais sous queue | elles sont saines pour cette parente ; ce sont les Rate **du milieu** qui les rendaient fautives |
| le SEEL se dégrade quand la queue s'allonge | plus de couches en boucle ouverte = plus d'erreur d'épaisseur, sans contrepartie puisque le plantage ne bouge plus |

#### 🔵 Ce que ça implique pour la proposition de 👤

> 👤 : *« les couches i+1 à 75 en Rate **sauf les couches avec au moins 2 points tournants** qui
> restent en optique »*.

⚠️ **La règle d'exception devient suspecte à la lumière de ce mécanisme** : rouvrir une couche
optique **au milieu de la queue** réintroduit un point de plantage, et tout ce qui la suit
redevient exposé. Le gain espéré — se ré-ancrer pour corriger la dérive — doit **dépasser** ce
coût, et rien ne dit qu'il le fait. 📌 C'est mesurable en une cellule (`rate_tail_keep_optical`,
trois tentatives échouées à ce jour) et c'est **le prochain essai à réussir**.

🔑 **Et le vrai résultat à retenir dépasse le Rate** : sur `r75x2`, **les 224 stratégies à blocs
plantent toutes à 100 %**. La seule qui passe est le **monitoring couche par couche**, et
seulement avec sa queue. *Ce qui sauve le ×2, c'est per-layer + queue Rate — jamais l'un sans
l'autre.* Cela rejoint §24-40 de `CLAUDE.md`, où le monitoring par couche gagne dès que
l'information optique devient peu fiable.

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

### 🟢 CE QUE LE CRITERE PAR SWING TROUVE REELLEMENT — mesuré le 2026-08-19, avant le run

`scripts/probe_swing_par_couche.py`, quelques secondes par composant, aucune Phase B.

| composant | couches sous le seuil **à la meilleure λ** | **à la λ réellement retenue** |
|---|---|---|
| 35c | 0 / 35 | **0 / 35** |
| 48c | 0 / 48 | **0 / 48** |
| **75c** | 0 / 75 | **5 / 75** |
| 99c | 0 / 99 | **0 / 99** |

🔴 **Première conclusion, et elle réduit la portée du critère.** *Aucune* couche n'est
indéfendable optiquement : à sa meilleure λ, chaque couche des quatre composants dépasse le
seuil. Le cas *« cette couche n'a aucun signal exploitable »* — celui que §22 décrit — **ne se
présente jamais**. `rate_by_swing` est donc **inerte sur 35c, 48c et le 99c**, et un run sur ces
composants ne mesurerait rien.

### 🔑 POURQUOI 5 COUCHES DU 75c SONT SOUS LE SEUIL — et ce n'est pas un défaut

📏 Vérifié : ces 5 couches ont **178, 119, 132, 33 et 36 candidates survivantes**. Aucun repli,
la Phase A avait l'embarras du choix. Et **5 sur 5 héritent leur λ** d'un bloc ouvert par la
couche précédente :

```
couche 23  bloc ouvert en 22    couche 31  bloc ouvert en 30    couche 33  bloc ouvert en 32
couche 50  bloc ouvert en 49    couche 52  bloc ouvert en 51
```

> 🔑 **La Phase A filtre le swing de la couche QUI CHOISIT. Les couches suivantes du bloc
> héritent d'une λ qui n'a jamais été validée POUR ELLES.** Leur swing peut donc tomber sous le
> seuil sans qu'aucune règle ne soit violée — c'est structurel.

🟢 **Et c'est exactement la niche du Rate.** Ces couches sont surveillées à une λ choisie pour
une autre, avec un signal trop pauvre pour un arrêt précis, et sans que rien dans le système ne
le signale. Ce n'est plus *« placer le Rate où l'optique est mauvaise »* au sens vague : c'est
**« placer le Rate sur les couches héritières dont la λ du bloc ne convient pas »**, ce qui est
mesurable et rare — 5 sur 75.

⚠️ **Portée honnête** : 5 couches sur 75, sur un seul composant, une seule graine. Et le critère
ne capte que ce cas-là — il est aveugle au second motif d'emploi du Rate, celui où c'est le
**bruit de fente** qui dégrade le signal, puisque le swing est calculé sur le signal nominal
sans convolution par la fente.

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

---

## 8. 🔵 LE BATCH DU 2026-08-19 — les prédictions sont écrites AVANT qu'il tourne

👤 : *« je souhaite lancer un batch d'environ 2 h avec du rate sur le 75c ×2 »*, *« je valide
toutes les décisions que tu prendras »*. Lancé en son absence.
`scripts/batch_rate_2026-08-19.py`, 3 cellules, ~3 h 15 estimées.

### Pourquoi un rejeu était OBLIGATOIRE en tête

Deux correctifs sont tombés le même jour, tous deux sur instruction de 👤, et tous deux
touchent le Rate :

1. **la dernière couche devient candidate** (elle était exclue — 0 placement sur 24 581) ;
2. **le facteur de rate ne se calcule plus que sur les couches optiquement déposées.**

🔴 **C1 : toute mesure Rate antérieure décrit un autre solveur.** Sans la cellule 1, aucune
comparaison n'est possible — ce serait l'erreur n° 3 du §5 de `CLAUDE.md`, deux choses changées
à la fois.

### Les trois cellules, et ce que chacune décide

| # | cellule | ce qu'elle tranche |
|---|---|---|
| **1** | `fast`, graine 42, coupures **46 → 64** | le correctif **déplace-t-il la falaise** ? La campagne d'avant la situait entre 61 et 58, avec un plateau plat à 4,00 % de 58 à 46 |
| **2** | `fast`, graine **77**, mêmes coupures | §24-46 : *un verdict sur un intervalle marginal n'est pas déterminé par une graine*. Sans elle, rien de la cellule 1 n'est publiable |
| **3** | **`premium`**, graine 42, coupures 52 → 58 | le `4,00 %` vaut **2/50** en `fast` : la granularité minimale au-dessus de zéro, **pas une mesure**. À N = 150 il devient 6/150, et le bruit du SEEL tombe d'un facteur √3 — de quoi enfin départager les coupures, ce que `fast` **ne peut pas faire** (écart 52/46 à 1,25 σ) |

### 🔵 La prédiction, posée d'avance et falsifiable

> **L'optimum doit se déplacer vers des queues plus COURTES** (coupure plus tardive).

**Le raisonnement** : le vivier de références ne grossit plus à l'intérieur de la queue, donc
une longue queue n'améliore plus son estimation de rate — elle fige une erreur unique et la
fait porter à toutes ses couches. L'ancien code créditait ces couches d'un `n_ref` fictif et
sous-estimait donc le coût des longues queues.

**Ce qui la réfuterait** : un optimum inchangé à 52, ou déplacé vers 46. Dans ce cas la
correction ne pèse rien devant le mécanisme de position terminale, et il faudra le dire.

### ⚠️ Ce que ce batch NE fait pas, et pourquoi

| | |
|---|---|
| pas de `rate_tail_keep_optical` — la **règle d'exception** de 👤 | trois tentatives ont échoué. Je ne lance pas une quatrième à l'aveugle en son absence : une cellule morte coûte 40 min pour rien. Elle passe après, avec un essai de mise en route court |
| pas d'autre composant | 👤 a demandé le 75c ×2 |
| pas de `deep` | à N = 300 une seule cellule mangerait le budget entier |

---

## 9. 📏 RÉSULTAT DE LA CELLULE 1 — **MA PRÉDICTION EST RÉFUTÉE**, et je sais pourquoi

`reports/blocs_vs_plantage_r75x2_fast_s042_tail46-64.json`, 40,4 min, `N = 50` **consigné**.

| coupure | 46 | 49 | **52** | 55 | 58 | 61 | 64 | *sans queue* |
|---|---|---|---|---|---|---|---|---|
| couches Rate | 29 | 26 | **23** | 20 | 17 | 14 | 11 | 0 |
| `crash_min` | 4,00 % | 4,00 % | **4,00 %** | 4,00 % | 4,00 % | 100 % | 100 % | 100 % |
| SEEL | 0,752 | 0,717 | **0,689** | 0,702 | 0,735 | — | — | — |

**Comparaison directe avec l'avant-correctif, coupure par coupure :**

```
coupure  SEEL avant  SEEL apres     ecart
     46      0.7517      0.7517    -0.00%
     49      0.7169      0.7170    +0.00%
     52      0.6886      0.6885    -0.01%
     55      0.7014      0.7017    +0.03%
     58      0.7351      0.7353    +0.02%
```

🔴 **La prédiction disait « l'optimum doit se déplacer vers des queues plus courtes ». Il n'a
pas bougé d'un iota, et rien d'autre non plus : l'écart maximal vaut 0,03 %.** La falaise est
au même endroit, entre 58 et 61.

### 🟢 Le contrôle passe : le correctif ATTEINT bien le calcul

Ce n'est donc pas un correctif inerte qu'on mesurerait sans le savoir (§12, contrôle 4) :

| couche | placements natifs avant | après |
|---|---|---|
| **74 (dernière)** | **0** | **112** |
| 71 | 45 | 19 — évincée, la 74 est plus profonde et le plafond garde les profondes |
| 0 et 1 | 0 | 0 |
| **total** | 291 | **314** |

### 🔑 ET LA DÉMONSTRATION ANALYTIQUE — pourquoi l'exclusion des références NE POUVAIT RIEN CHANGER

Une couche Rate sort à `d_réel = d_nom / A` **par construction**. Son propre ratio
`d_nom/d_réel` vaut donc **exactement `A`**, la moyenne courante. En l'incluant :

```
A' = (n_opt · A + n_rate · A) / (n_opt + n_rate) = A
```

**La moyenne est invariante.** L'exclusion ne change que `n_ref` — c'est-à-dire la **précision
annoncée**, jamais **l'épaisseur simulée**.

🔑 **Le seul résidu possible est donc l'arrondi**, puisque `turns = round(...)` empêche le ratio
d'être *exactement* `A`. 📏 Et c'est exactement ce qu'on mesure : **0,03 % au maximum**, à
comparer à 0,125 nm sur ~100 nm, soit 0,12 %. **Le même ordre.** 👤 avait désigné le round le
même jour comme *« d'un ordre supérieur »* dont on ne tient pas compte : les deux énoncés se
referment l'un sur l'autre.

⚠️ **Donc le correctif reste juste, et il fallait le faire** — `n_ref` mentait, et toute
précision annoncée via `1/√n` était surestimée. Mais **il ne corrige pas un chiffre, il corrige
une affirmation.** C'est une distinction qu'il ne faut pas perdre.

### 🔴 Deux avertissements à corriger, que j'avais écrits trop fort

| ce que j'avais écrit | ce que la mesure dit |
|---|---|
| **C1 : « toute mesure Rate antérieure décrit un autre solveur et n'est plus comparable »** | vrai pour le **vivier** (291 → 314 placements natifs), **faux en effet** sur les résultats de queue, identiques à 0,03 %. Les campagnes de queue antérieures restent donc lisibles |
| *« l'estimation se fige dans la queue »* | **exact, mais ce n'est pas neuf** : le figement existait déjà avant le correctif, puisque les couches Rate reproduisaient `A`. Le correctif ne le crée pas, il cesse de le **masquer** derrière un `n_ref` gonflé |

### ⚠️ Et la dernière couche ne rapporte rien ici

📏 112 variantes portent désormais un Rate sur la couche 74. **Zéro déposable, `crash_min`
100 %.** Sur `r75x2` la dernière couche n'ouvre donc aucune porte — ce qui ne juge pas la règle
de 👤, qui est une règle d'**admissibilité** : on ne peut pas mesurer ce qu'on s'interdit
d'essayer, et il fallait pouvoir l'essayer. Le verdict sur sa **valeur** demande d'autres
composants, notamment ceux où le Rate gagne déjà (§7 : `75c` à 1 nm).

### 🔑 Ce que la cellule 1 établit VRAIMENT

**Les cinq coupures déposables sont toutes indiscernables à 2 σ** (écart max 1,25 σ). Comme
avant le correctif, **ce run ne désigne aucun optimum** — et `scripts/lire_batch_rate.py` le
dit de lui-même, ce qui était tout l'objet de l'écrire.

---

## 10. 🔴 CELLULE 2 — LA GRAINE N'ATTEINT PAS LE SCORE, ET J'ALLAIS LE LIRE À L'ENVERS

`reports/blocs_vs_plantage_r75x2_fast_s077_tail46-64.json`, 36,5 min, graine **77**.

| coupure | 46 | 49 | 52 | 55 | 58 | 61 | 64 |
|---|---|---|---|---|---|---|---|
| `crash_min` **s042** | 4,00 % | 4,00 % | 4,00 % | 4,00 % | 4,00 % | 100 % | 100 % |
| `crash_min` **s077** | **2,00 %** | **2,00 %** | **2,00 %** | 4,00 % | 4,00 % | 100 % | 100 % |
| couche critique | c39 / **c32** | idem | idem | idem | idem | — | — |
| SEEL, **les deux** | 0,752 | 0,717 | 0,689 | 0,702 | 0,735 | — | — |

### ⚠️ Le piège, et il a failli fonctionner

**Les SEEL sont identiques sur les deux graines.** Lu vite, cela dit *« le résultat est robuste
au tirage »*. **C'est faux, et c'est exactement l'erreur n° 4 du §5** — *croire un chiffre qui
ne varie pas avec ce qui devrait le faire varier*.

📏 Les scores bruts diffèrent au **11ᵉ chiffre** :

```
coupure 52 :  0.11852439021077397  (s042)   contre   0.11852439020756476  (s077)
              ecart 3,2e-11 -- l'ordre de la gigue de recompilation du §9, c'est-a-dire RIEN
```

### 🔑 La cause, trouvée dans le code — c'est §24-47, vérifié sur un second composant

| | |
|---|---|
| `consensus_seed_list = 41,42,43,44,45`, `consensus_num_seeds = 3` | le consensus tourne sur **[41, 42, 43]** |
| `_resolve_consensus_seeds` (`certus_strat_consensus.py:132`) | la liste explicite gagne ; **`base_seed` n'est consulté que si elle est vide**. Le consensus n'a donc **jamais vu 77** |
| le rescoring ne lit que `robustness_score` (`certus_strat_robustness.py:2572`) | il réécrit le **score** des `consensus_top_k = 60` premières, **jamais `crash_rate`** |
| 📏 les déposables sont aux **rangs 0 à 4** | elles sont donc bel et bien rescorées |

**D'où le motif exact qu'on observe : le score est gelé par le consensus, le plantage suit
`robustness_seed`.**

### 🔴 Ce que cela coûte à ma propre méthode — deux corrections

**1. La cellule 2 ne remplit PAS §24-46 sur l'axe du SEEL.** Elle le remplit sur l'axe du
plantage, et c'est là que vit le verdict. ✅ **Et de ce côté le résultat est bon** : le verdict
est **stable** — cinq coupures déposables (46 à 58), zéro à 61 et 64, falaise au même endroit,
sur les deux graines. Le taux bouge (4 % ↔ 2 %) et la couche critique aussi (39 ↔ 32), donc la
graine **atteint** bien le calcul : c'est un contrôle qui passe, pas un paramètre inerte.

**2. Le σ de `lire_batch_rate.py` était bâti sur la mauvaise profondeur.** Il prenait le `N` du
**mode** (50 en `fast`) alors que le score des 60 premières vient du **consensus**, à
`consensus_num_runs` tirages sur trois graines. 🔴 **Un σ trop grand rend un verdict
PERMISSIF** : il déclare « indiscernable » ce qui ne l'est peut-être pas. L'instrument le dit
désormais, et pose la limite juste : **il sert à refuser une distinction, jamais à affirmer une
égalité.**

🔑 **Et la vraie dispersion reste inconnue.** Ce qui la sonderait est un changement de
**triplet de graines de consensus**, pas de `robustness_seed`. Personne ne l'a jamais fait.
C'est la mesure qui manque pour pouvoir écrire quoi que ce soit sur l'optimum de la coupure.

---

## 11. 📏 CELLULE 3 — le 4,00 % était bien 2/50, et le vrai taux est ~3 %

`reports/blocs_vs_plantage_r75x2_premium_s042_tail52-58.json`, 60,4 min, **`N = 150` consigné**.

| coupure | `fast` N=50 | **`premium` N=150** | plantages | incertitude de Poisson |
|---|---|---|---|---|
| 52 | 4,00 % | **2,67 %** | 4/150 | ±1,33 pt |
| 55 | 4,00 % | 3,33 % | 5/150 | ±1,49 pt |
| 58 | 4,00 % | 3,33 % | 5/150 | ±1,49 pt |

✅ **La cellule répond à ce qu'on lui demandait** : le `4,00 %` était la granularité `2/50`. Le
taux réel vaut **~3 %**, donc **sous la cible de 5 % de 👤**. ⚠️ Mais 4 plantages contre 5 sur
150, c'est **un** plantage d'écart : les trois coupures restent indiscernables **aussi** sur le
plantage. Le SEEL descend de 2,5 % (0,689 → 0,672) et la couche critique passe de 39 à **45**.

🔑 **Et cela referme une question laissée ouverte au §10** : le score **bouge** avec le mode,
donc sa profondeur suit `consensus_num_runs`, que le mode fixe (50 en `fast`, 150 en
`premium`). Mon σ par mode était donc trop grand d'un facteur ~√3, **pas faux en nature** : le
verdict « indiscernable » reste **permissif**, c'est-à-dire conservateur dans le bon sens.

---

## 12. 🔴 ANALYSE CONTRADICTOIRE — 👤 : *« pour être sûr qu'on ne va pas dans une voie de garage »*

§12 appliqué à ma propre direction, en cherchant à la **casser**. Quatre attaques portent.

### Attaque 1 — l'hybride est dominée sur TOUS les axes par une solution déjà mesurée

| | déposables | SEEL | plantage | **blocs** |
|---|---|---|---|---|
| **1 nm, pur optique**, `deep`, graine 42 | **277** | **0,625** | **1,0 %** | **6** |
| 2 nm + queue Rate, `premium` | 1 | 0,672 | ~3 % | **75** |

**5 changements de λ en atelier contre 74, plus 23 couches en boucle ouverte.** 🔴 **Je n'avais
jamais chiffré le coût d'atelier de l'hybride**, alors que §24-43 en fait explicitement un
critère.

### Attaque 2 — mais cette solution-là n'est pas établie non plus

```
deep 1 nm elargi, graine 42 :  254 deposables, crash_min  1,0 %
deep 1 nm elargi, graine 77 :    0 deposable,  crash_min 38,0 %
```

**Même configuration, seule la graine change : 254 → 0.** C'est §24-46 — basculement
**catégoriel** — mesuré cette fois sur `r75x2`.

### 🔴 Attaque 3 — LA CASE DÉCISIVE N'A JAMAIS ÉTÉ LANCÉE

**`r75x2` en `deep` à 2 nm n'existe pas.** Toute la queue Rate repose sur du `fast` (N=50) et
du `premium` (N=150) à 2 nm, qui rendent 0 déposable en pur optique.

📏 Or à 1 nm, passer de `fast` à `deep` a fait **0 → 277 déposables** : ce n'était donc **pas
la fente** qui sauvait, c'était **la profondeur de recherche**. Rien ne dit que `deep` à 2 nm
ne ferait pas la même chose — **auquel cas la queue Rate ne sert à rien sur ce composant.**

### 🟠 Attaque 4 — un défaut dans ma propre décomposition du §8

J'ai écrit que `SEEL_réel(n) − SEEL_parfait(n)` **isole** le coût de la queue Rate. **C'est
faux en toute rigueur** : le facteur `A` s'estime sur les couches optiques du préfixe, donc un
préfixe dégradé donne un `A` dégradé. Les deux coûts sont **couplés, pas additifs**, et le
« leur somme a un minimum » était **heuristique** — présenté trop fermement.

### ✅ Ce qui survit aux quatre attaques

| | |
|---|---|
| **`crash(n)` monotone par construction** | vérifié causalement : la croissance est causale, donc les couches `0..n−1` se comportent identiquement que la couche `n` soit optique ou parfaite |
| **la sonde SEEL(n)** | bon marché et diagnostique ; sa valeur ne dépend pas de l'issue de l'attaque 3 |
| **le mécanisme du §9** | apparié, contrôlé, et il tient : c'est la **position terminale**, pas la couverture |

### 🔑 LE VRAI DIAGNOSTIC — ce n'est pas la méthode, c'est le COMPOSANT

`r75x2` est assis **exactement sur la frontière de fabricabilité**, où tout verdict bascule
avec la graine : 254 → 0 en pur optique, 4 % ↔ 2 % en hybride, et une seule stratégie survit
partout. **Bâtir une méthode dessus, c'est bâtir sur du sable.**

### L'ordre des travaux qui en découle

| # | action | ce qu'elle décide |
|---|---|---|
| **1** | **`r75x2 deep @ 2 nm`, deux graines** | si le pur optique passe, **la queue Rate sur ce composant est une voie de garage**, et il faut l'écrire noir sur blanc |
| **2** | la sonde SEEL(n) | bon marché, diagnostique, indépendante de 1 |
| **3** | valider le Rate sur **`75c` à 1 nm** | §7 : la seule cellule où le Rate gagne, et elle est stable. Bien meilleur banc d'essai que `r75x2` |

🔴 **Et surtout PAS le 99c** — 👤 : *« c'est un empilement très particulier, tout quart d'onde »*.
