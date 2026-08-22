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

`RATE_MAX_VARIANTS_PER_STRATEGY = 3` (`certus_strat_robustness.py:519`) porte cette
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

## 3bis. 🟢🟢 L'HYBRIDE OPTIQUE-PUIS-RATE REND LE ×2 FABRICABLE **À 2 nm** — 2026-08-19

> 👤 : *« avant les couches i, un filtre le plus parfait possible en tout optique, puis les
> couches i+1 à 75 en rate. Est-ce naïf ? »*

### 🔴 LA QUEUE RATE EST UNE AFFAIRE DE 2 nm. À 1 nm, LE PUR OPTIQUE LA BAT.

📏 **Mesuré le 2026-08-20, inventaire complet de `r75x2` à la graine 42** :

```
                            deposables      SEEL      plantage
1,0 nm  deep   pur optique       277       0.6248      1,00 %   <- LE MEILLEUR
1,0 nm  fast   pur optique         0          -       38,00 %
2,0 nm  deep   pur optique         0          -      100,00 %
2,0 nm  premium  queue Rate        3       0.6717      2,67 %
2,0 nm  deep     queue Rate        3       0.6859      2,67 %
2,0 nm  fast     queue Rate        2       0.7014      4,00 %
```

🔑 **À 1 nm, le pur optique rend 0,6248 — meilleur que TOUTES les queues Rate de ce composant**
(0,672 à 0,701), avec 277 déposables au lieu de 3. Et 1 nm + `deep` sont la **résolution et le
mode natifs du fichier livré** : chargé tel quel, il fonctionne. C'est le sens de son nom.

⚠️ **Donc la portée de tout ce dossier se resserre, et il faut le dire** : la queue Rate n'est
pas *« ce qui rend `r75x2` fabricable »* — elle est **ce qui le rend fabricable À 2 nm**, c'est-
à-dire à la moitié de la résolution pour laquelle il a été conçu. C'est un résultat réel, sur un
régime volontairement dur, et ce n'est pas la voie recommandée pour ce composant.

📌 **Ce qui reste entier** : la règle *faisabilité contre précision* (§16, §20), le mécanisme de
position terminale, la réfutation de la règle d'exception (§21), et le fait que la queue est la
**seule** configuration à marcher aux deux graines à 2 nm.

### 🔴 LIS CECI AVANT DE CITER LE MOINDRE CHIFFRE DE CE DOSSIER

📏 **Les deux composants ont été mesurés à la résolution native de L'AUTRE**, par surcharge
délibérée de la sonde. Vérifié dans les fichiers de configuration eux-mêmes :

| | résolution NATIVE du fichier | mode natif | résolution **mesurée** dans ce dossier |
|---|---|---|---|
| `JSON-strat-random75.json` (`75c`, épaisseurs **simples**) | **2 nm** | `fast` | **1 nm** |
| `JSON-strat-random75-x2-fabricable.json` (`r75x2`, épaisseurs **doubles**) | **1 nm** | `deep` | **2 nm** |

🔑 **Conséquence, et elle borne tout ce dossier : le ×2 est déjà fabricable en PUR OPTIQUE à sa
résolution native de 1 nm** — c'est de là que vient le `-fabricable` de son nom, et c'est le
passage de `fast` à `deep` qui l'avait débloqué (`CLAUDE.md` §27). En le tournant à **2 nm**, on
le place à la moitié de la résolution pour laquelle il a été construit.

⚠️ **Donc « le ×2 n'est pas fabricable en optique » est FAUX sans sa condition.** Ce qui est
mesuré est : *à 2 nm, à la graine 42, le pur optique rend 0 déposable.* À 1 nm il en rend, et
§14 mesure même que cela dépend encore de la graine — 1 nm marche à 42 et pas à 77, 2 nm marche
à 77 et pas à 42.

📌 Ce n'est pas un défaut de la campagne : mesurer le ×2 à 2 nm est un choix légitime, c'est le
régime où il est **difficile**, donc celui où une queue Rate a quelque chose à apporter. Mais la
condition doit voyager avec le chiffre, **surtout vers `pages/CERTUS_STRAT.html`**, où une
affirmation trop large se réfute en une question.

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

#### 🟢 LE BRUIT DU SEEL EST MESURÉ SUR `r75x2` — et deux coupures se séparent, deux non

📏 **Mesuré la nuit du 2026-08-19 au 20**, cellules 1 à 3 du batch de nuit. Trois runs
**identiques en tout**, ne différant que par le triplet de graines de consensus — donc leur
étendue **est** le bruit du score, et non une extrapolation :

```
41,42,43   539 strategies   1 deposable   crash 4,00 %   SEEL 0.6885   75 blocs
51,52,53   539              1             crash 4,00 %   SEEL 0.6679   75 blocs
61,62,63   539              1             crash 4,00 %   SEEL 0.6774   75 blocs

etendue 3,10 %  ->  sigma ≈ 1,83 %   (E[etendue]/sigma = 1,693 a n = 3)
                ->  sur une DIFFERENCE de deux SEEL : sigma√2 ≈ 2,59 %
```

**Le verdict, coupure par coupure — c'est ce que le critère posé d'avance exigeait :**

| comparaison | écart | en σ | verdict à 2 σ |
|---|---|---|---|
| 52 (0,689) contre **46** (0,752) | +9,1 % | **3,53 σ** | 🟢 **séparable** |
| 52 (0,689) contre **58** (0,735) | +6,7 % | **2,58 σ** | 🟢 séparable, de justesse |
| 52 (0,689) contre **49** (0,717) | +4,1 % | 1,57 σ | 🔴 non séparable |
| 52 (0,689) contre **55** (0,702) | +1,9 % | 0,73 σ | 🔴 non séparable |

🔑 **L'énoncé qui tient, et lui seul : l'INTÉRIEUR de la plage bat les BORDS ; à l'intérieur,
rien ne se départage.** Les coupures 49, 52 et 55 forment **une seule classe d'équivalence** —
« l'optimum est à 52 » n'est pas établi et ne doit pas être écrit. Les coupures 46 et 58 sont,
elles, réellement moins bonnes.

⚠️ **Le σ emprunté était trop PESSIMISTE d'un facteur 2,8.** La version précédente de ce bloc
reportait le σ ≈ 6 % de §24-26 — mesuré sur le **48 couches**, à N = 150 — jusqu'à 7,3 % sur une
différence, et concluait que les cinq coupures étaient indiscernables. La mesure directe donne
2,59 %. **Un bruit emprunté à un autre composant ne vaut rien**, dans un sens comme dans
l'autre : ici il faisait jeter deux séparations réelles.

⚠️ **Trois réserves, et elles limitent la portée :**

| | |
|---|---|
| **trois points ne font pas un écart-type** | l'étendue sur `n = 3` est un estimateur grossier. Le 2,59 % est une **borne indicative**, pas une constante du composant |
| **les coupures d'un même run PARTAGENT leurs graines de consensus** | c'est un tirage commun : une partie du bruit s'annule dans la comparaison. Le σ√2 ci-dessus est donc **conservateur** — s'il se trompe, c'est en déclarant trop peu de séparations, jamais trop |
| **mesuré en `fast`, N = 50** | à N = 150 le bruit doit tomber d'un facteur √3. Le `premium` de §11 va dans ce sens : il ne sépare toujours pas 52 de 55 |

🟢 **Et ce qui ne bouge d'AUCUN triplet à l'autre** — vérifié stratégie par stratégie, pas au
seul vu du nombre de blocs :

```
41,42,43   RATE_TAIL52(from 75800)   SEEL 0.6885   crash 4,00 %   75 blocs
51,52,53   RATE_TAIL52(from 75800)   SEEL 0.6679   crash 4,00 %   75 blocs
61,62,63   RATE_TAIL52(from 75800)   SEEL 0.6774   crash 4,00 %   75 blocs
```

🔑 **C'est LA MÊME stratégie dans les trois, et cela rend la mesure plus propre qu'annoncé** :
ce n'est pas la dispersion d'un vainqueur qui change d'un run à l'autre — mélange de bruit de
score et de bruit de **sélection** — c'est le bruit de l'estimateur de score sur un **objet
fixe**. L'isolation est totale, ce qui est exactement ce qu'on voulait mesurer.

✅ **Et c'est une confirmation indépendante de §24-47** : le plantage est identique au centième
dans les trois. Le code disait *« consensus rescoring … only reads `robustness_score` »* — la
mesure le montre. Le rescorage déplace le **score** ; il ne touche ni le **verdict de
fabricabilité**, ni le **choix de la stratégie**. C'est ce qui rend le résultat du chantier —
*la queue Rate rend `r75x2` fabricable **à 2 nm*** — insensible à toute cette discussion.

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
| **POEM contre niveau absolu** | 🔴 **GLOBAL** — `poem_enabled` est un booléen unique pour tout le run (`certus_strat_robustness.py:2421`, propagé jusqu'à `certus_strat_batch.py:78`) |

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
supposant un historique que la couche Rate `i` a détruit (§27 de [`CLAUDE.md`](../CLAUDE.md)). **64 % de l'offre est jugée avec
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
| **3** | **`premium`**, graine 42, coupures 52 → 58 | le `4,00 %` vaut **2/50** en `fast` : la granularité minimale au-dessus de zéro, **pas une mesure**. À N = 150 il devient 6/150, et le bruit du SEEL tombe d'un facteur √3 — de quoi enfin départager les coupures, ce que `fast` **ne peut pas faire** (écart 52/46 à 1,25 σ) — 🔴 **cette parenthèse est RÉFUTÉE** : le bruit a été mesuré la nuit du 19 au 20 et vaut 2,59 % sur une différence, pas 7,3 %. L'écart 52/46 est à **3,53 σ** et `fast` le sépare déjà. Voir le §3bis |

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

**Ce run ne désigne aucun optimum** — et `scripts/lire_batch_rate.py` le dit de lui-même, ce
qui était tout l'objet de l'écrire.

🔴 **La phrase qui précédait — *« les cinq coupures sont toutes indiscernables à 2 σ, écart max
1,25 σ »* — est RÉFUTÉE**, et par une mesure, pas par un raisonnement. Le σ de 7,3 % était
emprunté au 48 couches ; le σ **mesuré** sur `r75x2` vaut 2,59 % sur une différence (§3bis). Les
coupures **46 et 58 se séparent** de la 52, à 3,53 σ et 2,58 σ. Ce qui reste vrai est plus
faible et plus précis : **49, 52 et 55 sont une seule classe**, et aucune des trois n'est
l'optimum.

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
| le rescoring ne lit que `robustness_score` (`certus_strat_robustness.py:2769`) | il réécrit le **score** des `consensus_top_k = 60` premières, **jamais `crash_rate`** |
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

🔑 **Ce qui sonderait la vraie dispersion est un changement de triplet de graines de
consensus**, pas de `robustness_seed`. ✅ **Fait la nuit du 2026-08-19 au 20** : trois triplets,
étendue **3,10 %**, soit **2,59 %** sur une différence de deux SEEL. Le σ permissif dénoncé
juste au-dessus était trop grand d'un facteur **2,8**, et il faisait effectivement ce que ce
paragraphe redoutait — déclarer indiscernables deux coupures qui ne le sont pas. **Le résultat
est au §3bis.**

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

---

## 13. 🟢🟢 LA CASE MANQUANTE EST TOMBÉE — et elle RÉFUTE mon attaque, pas la queue Rate

`reports/blocs_vs_plantage_r75x2_deep_s042.json`, **117,4 min**, `N = 300` consigné,
**1 617 stratégies**.

### La question, et la réponse est nette

L'attaque 3 du §12 disait : *« à 1 nm, passer de `fast` à `deep` a fait 0 → 277 déposables ;
ce n'était donc pas la fente qui sauvait mais la PROFONDEUR DE RECHERCHE. Rien ne dit que
`deep` à 2 nm ne ferait pas la même chose — auquel cas la queue Rate ne sert à rien. »*

📏 **Elle ne fait pas la même chose. Du tout.**

| configuration, fente **2 nm** | stratégies | déposables | `crash_min` |
|---|---|---|---|
| `fast` (N = 50) | 404 | **0** | 100,00 % |
| `premium` (N = 150) | 651 | **0** | 100,00 % |
| **`deep` (N = 300)** | **1 617** | **0** | **100,00 %** |
| `fast` **+ queue Rate** | 1 215 | **5** | **4,00 %** |

🔴 **Quadrupler la recherche — 404 → 1 617 stratégies — ne change RIEN.** Zéro déposable, 100 %
de plantage, sur les trois profondeurs. **Ce n'est donc pas la profondeur qui manquait à 2 nm**,
et le déblocage observé à 1 nm venait de la **fente**, la profondeur ne faisant qu'exploiter ce
que la fente rendait possible.

🔑 **La queue Rate est donc, à ce jour, le SEUL moyen connu de rendre ce design fabricable à la
fente nominale.** Ce n'est pas une voie de garage : c'est la seule route.

### 🔴 Et l'attaque 1 se retourne aussi — sur l'axe qui compte le plus

Je reprochais à l'hybride d'être *« dominée sur tous les axes »* par le pur optique à 1 nm.
📏 Voici les deux, **aux deux graines** :

| | graine 42 | graine 77 | verdict |
|---|---|---|---|
| **1 nm, pur optique**, `deep` élargi | 254 déposables, SEEL 0,629 | 🔴 **0 déposable**, plantage 38 % | **1 graine sur 2** |
| **2 nm, + queue Rate**, `fast` | 5 déposables, 4,00 % | 5 déposables, **2,00 %** | 🟢 **2 graines sur 2** |

**L'hybride est la seule des deux qui survive au changement de graine.** Et le SEEL de sa
meilleure est **identique aux deux graines** (0,689) — pour la raison démontée au §10, mais le
verdict de fabricabilité, lui, est bien reproduit.

### Ce que ça change, et ce que ça ne change pas

| | |
|---|---|
| 🟢 **la queue Rate n'est PAS une voie de garage** | c'est le seul moyen connu à 2 nm, et le seul qui tienne sur deux graines |
| 🔴 **elle reste chère en atelier** | **74 changements de λ** plus 23 couches en boucle ouverte, contre 5 changements pour la solution à 1 nm. Ce reproche-là **tient toujours** |
| 🟠 **et son SEEL reste moins bon** | 0,672 en `premium` contre 0,625 à 1 nm — mais on compare une solution qui **existe aux deux graines** à une qui n'existe qu'à une |
| 🔵 **la vraie question devient donc opératoire** | *préfère-t-on une fente de **1 nm** (×2 de bruit de lecture, 5 changements de λ, mais un verdict qui bascule avec le tirage) ou la fente nominale de **2 nm** avec une queue Rate (robuste aux deux graines, mais 74 changements) ?* C'est une question pour 👤, pas pour la mesure |

⚠️ **Ce qui manque encore** : `deep` à 2 nm sur une **seconde graine** — c'est la cellule 2 du
batch, en cours. Si elle rend aussi 0 déposable, le « 100 % à 2 nm en pur optique » sera établi
sur deux graines et le résultat sera solide des deux côtés.

🔑 **Note de méthode** : ce contrôle a été conçu pour **tuer** la queue Rate, et il l'a
confirmée. C'est exactement ce qu'on demande à un contrôle — et c'est la raison pour laquelle
il fallait le lancer avant d'écrire quoi que ce soit d'autre.

---

## 14. 🔴🔴 LA CELLULE 2 RÉFUTE LE §13 — et ce qui survit est plus fort que ce qui tombe

`reports/blocs_vs_plantage_r75x2_deep_s077.json`, 154,2 min, `N = 300`, **2 231 stratégies**.

### Ce que le §13 affirmait, et qui est FAUX

> *« La queue Rate est, à ce jour, le seul moyen connu de rendre ce design fabricable à la
> fente nominale. »*

📏 **Réfuté.** À `deep` et 2 nm, **graine 77** :

| | stratégies | déposables | `crash_min` | SEEL | blocs |
|---|---|---|---|---|---|
| **graine 42** | 1 617 | **0** | 100,00 % | — | — |
| **graine 77** | 2 231 | **547** | **1,33 %** | **0,569** | **9** |

**Le pur optique à la fente nominale rend 547 stratégies déposables**, la meilleure à
**SEEL 0,569 en 9 blocs** — c'est le **meilleur résultat jamais obtenu sur ce composant**,
meilleur que le 0,625 à 1 nm et que le 0,689 de l'hybride, avec **9 changements de λ au lieu
de 74**.

⚠️ **Et le §13 avait été écrit sur la SEULE graine 42**, six heures plus tôt, en concluant
« quadrupler la recherche ne change rien à 2 nm ». C'était vrai à graine 42. **Ce n'était pas
un fait sur le composant.**

### 🔑 LE TABLEAU COMPLET — et il faut le lire en entier, jamais une ligne seule

| configuration | graine 42 | graine 77 |
|---|---|---|
| **2 nm, pur optique**, `deep` | 🔴 **0 déposable**, 100 % | 🟢 **547**, SEEL 0,569, 9 blocs |
| **1 nm, pur optique**, `deep` élargi | 🟢 **254**, SEEL 0,629 | 🔴 **0 déposable**, 38 % |
| **2 nm + queue Rate**, `fast` | 🟢 **5**, SEEL 0,689 | 🟢 **5**, SEEL 0,689 |

🔴 **Les deux graines donnent des verdicts OPPOSÉS aux DEUX fentes**, et dans des sens
contraires : ce qui marche à 42 échoue à 77, et réciproquement. Sur ce composant, **la graine
ne fait pas varier un score : elle décide de l'existence même d'une solution.**

### 🟢 CE QUI SURVIT, ET QUI SORT RENFORCÉ

**L'hybride est la SEULE configuration qui tienne aux deux graines.** Les deux autres
échouent complètement, chacune à son tour. Ce n'était qu'une remarque au §13 ; c'est
maintenant **le seul énoncé qui résiste** :

> **Sur `r75x2`, aucune stratégie purement optique n'est fiable : chaque fente a sa graine qui
> la tue. La queue Rate rend moins bien — SEEL 0,689 contre 0,569 — mais elle rend TOUJOURS.**

⚠️ **Réserve de protocole, et elle est réelle** : l'hybride est mesuré en `fast`, les deux
autres en `deep`. La comparaison **entre lignes** mélange donc la profondeur de recherche.
Ce qui est propre, et qui porte tout le poids, c'est la comparaison **à l'intérieur de chaque
ligne** — même mode, même fente, seule la graine change. 📌 Un hybride en `deep` reste à
mesurer avant toute publication.

### 🔑 La leçon de méthode, et elle est chère

📏 **Trois fois aujourd'hui, une conclusion tirée d'une seule graine a été renversée par la
seconde** : le 254 → 0 à 1 nm ce matin, le mécanisme du Rate cet après-midi, et ce 0 → 547 ce
soir. §24-46 le disait depuis le 2026-08-17 — *un verdict n'est pas déterminé par une graine* —
et je l'ai enfreint trois fois en un jour, chaque fois en écrivant la conclusion **avant** que
la seconde graine ne soit tombée.

🔒 **La règle qui en découle, et elle est plus forte que « lancer deux graines »** : sur un
composant marginal, **n'écris pas la conclusion tant que la seconde graine n'a pas rendu**.
Pas « écris-la puis vérifie » — la première rédaction contamine la lecture de la seconde.

---

## 15. 🔵 LA COURBE `SEEL(n)` — la prédiction, posée AVANT que la cellule 6 ne rende

🔴 **Écrit le 2026-08-20 à 02:00, pendant que la cellule 4 tourne.** La sonde `SEEL(n)` part
vers 03:30. Le critère de lecture est donc fixé avant les données — c'est la discipline qui
vient de payer sur la dispersion (§3bis), et dont l'absence a coûté trois renversements le 19.

### Ce que la sonde mesure exactement

`optical_prefix_sweep` : les `n` premières couches sont **surveillées optiquement**, les
`75 − n` suivantes sont déposées à **épaisseur parfaite**. `SEEL(n)` est donc l'erreur
spectrale imputable **aux `n` premières couches seules**. C'est la proposition de 👤 du
2026-08-19, et elle porte son propre avertissement :

> 👤 : *« attention, la courbe SEEL = fonction (n) n'est pas forcément monotone, il faut la
> tracer entièrement pour décider quand le rate est nécessaire »*

### 🔵 La prédiction, et elle est falsifiable par une seule mesure

> **La montée la plus raide de `SEEL(n)` doit tomber vers `n ≈ 58–60`.**

**Pourquoi ce chiffre, et pourquoi il n'est pas choisi après coup** : le balayage de queue —
une sonde **entièrement différente**, qui mesure le **plantage** et non le SEEL — situe la
falaise entre la coupure 61 et la coupure 58 (§9). Les couches **58, 59, 60** sont exactement
celles que la coupure 58 neutralise et que la 61 laisse optiques. Si les deux sondes désignent
les mêmes couches, c'est **une validation croisée** : deux instruments indépendants tombent sur
la même physique, et `SEEL(n)` devient un **substitut bon marché** au balayage de queue, qui
coûte 45 min par composant.

### 🔴 Ce qui la réfuterait, dit d'avance

| observation | ce qu'il faudrait en conclure |
|---|---|
| une **rampe lisse et monotone**, sans structure | la sonde ne localise rien. Elle mesure l'accumulation, pas la fragilité, et elle **ne peut pas** répondre à « où mettre la coupure » |
| une montée raide **loin de 58-60** — par exemple vers 32 ou 39 | les deux sondes se contredisent. 🔴 **Interdiction d'utiliser l'une ou l'autre** avant d'avoir compris laquelle mesure quoi. Les couches 32 et 39 sont les couches **critiques** relevées par le balayage de queue, ce qui rendrait ce cas très embarrassant et très instructif |
| des **creux** nets, `SEEL(n+1) < SEEL(n)` | ✅ **attendu, et ce n'est pas un défaut** : POEM se ré-ancre sur les extrema réellement observés et corrige la dérive accumulée. Ajouter une couche dans le même bloc lui offre une occasion de plus de rattraper. C'est précisément la non-monotonie annoncée par 👤 |
| des **trous** dans la courbe | `n` sans aucune stratégie déposable ne rend **pas** un zéro : il ne rend **rien**. Un trou est une absence de mesure, jamais un bon score |

### ⚠️ Les deux réserves, et elles bornent d'avance ce qu'on pourra en dire

| | |
|---|---|
| **la suite n'est pas emboîtée** | à chaque `n`, la Phase A et la Phase B ré-optimisent sur un problème différent. `SEEL(n+1)` n'est pas `SEEL(n)` plus une couche : c'est une autre stratégie. Une partie de la non-monotonie sera donc du **bruit de sélection**, pas de la physique |
| **`r75x2` est assis sur la frontière** (§12) | la courbe sera tracée sur **une seule graine**, sur le composant où tout bascule avec la graine. 🔒 Donc, par la règle du §14 : **aucune conclusion n'est écrite tant qu'une seconde graine n'a pas rendu la même forme.** Le premier tracé sert à savoir si la sonde produit quelque chose, pas à trancher |

---

## 16. 🟢 CELLULE 4 — LE MÉCANISME SE GÉNÉRALISE, ET IL RETOURNE SON PROPRE SIGNE

`reports/blocs_vs_plantage_75c_fast_s042_res1_tail46-70.json`, **37,4 min**, 983 stratégies,
`monochromator_resolution_nm = 1.0` et `robustness_num_runs = 50` **consignés dans l'artefact**.

C'était le test de généralité : tout le mécanisme avait été établi sur `r75x2`, **où rien ne
marche en optique**. `75c` à 1 nm est le banc inverse — l'optique y marche très bien.

```
  reference pur optique : SEEL 0.371, 15 deposables sur 416, crash 4,00 %

   coupure  Rate    SEEL    ecart  en sigma   verdict
        46    29   0.442    19.1%       7.4   PIRE, separable        (11 depos)
        52    23   0.440    18.6%       7.2   PIRE, separable        (11 depos)
        58    17   0.424    14.3%       5.5   PIRE, separable        (11 depos)
        64    11   0.372     0.3%       0.1   indiscernable          ( 2 depos)
        70     5   0.373     0.5%       0.2   indiscernable          ( 2 depos)
```

*(σ = 2,59 % sur une différence, **mesuré** au §3bis — c'est lui qui rend ce tableau lisible d'un
coup d'œil. Avec l'ancien σ emprunté de 7,3 %, les mêmes écarts se lisaient 2,6 σ au lieu de
7,4 σ : réels mais discutables. **La mesure de la dispersion paie dès son premier usage.**)*

### 🔵 La prédiction est CONFIRMÉE — et elle va plus loin qu'annoncé

> *« si "position terminale" est un mécanisme et non un artefact, une queue tardive doit battre
> une queue précoce à SEEL comparable. Ce qui la réfuterait : un optimum au milieu, ou aucune
> structure. »*

📏 **La courbe est monotone et sans optimum intérieur** : `0,442 → 0,440 → 0,424 → 0,372 →
0,373`. Plus la coupure est tardive, meilleur est le SEEL — exactement la forme prédite, sur un
composant qui n'a servi à établir aucune partie du mécanisme.

🔑 **Et le cas limite, que la prédiction n'avait pas anticipé, est le plus instructif : la
meilleure « queue » est l'absence de queue.** La suite converge vers `0,371`, la valeur du pur
optique, et ne la franchit jamais. **La longueur de queue est un coût pur.**

### 🔑 CE QUE LES DEUX COMPOSANTS DISENT ENSEMBLE

| | `r75x2` @ 2 nm | `75c` @ 1 nm |
|---|---|---|
| l'optique seule | 🔴 **0 déposable** aux deux graines | 🟢 15 déposables, SEEL 0,371 |
| la queue Rate | 🟢 **la rend fabricable**, seule configuration à marcher aux deux graines | 🔴 coûte jusqu'à **+19 %**, soit 7,4 σ |

> **La queue Rate achète de la FAISABILITÉ, et elle la paie en PRÉCISION. Là où il n'y a rien à
> acheter, il ne reste que la facture.**

✅ **Et c'est la même conclusion, obtenue par un chemin entièrement différent, que le
multi-témoins** : *outil de faisabilité, jamais d'optimisation*, contrôle négatif passé 3 fois
sur 3 (§23 de `CLAUDE.md`). Deux mécanismes sans rapport aboutissent à la même règle. C'est le
genre de convergence qui vaut plus qu'une mesure de plus.

### ⚠️ Une anomalie que je ne sais PAS expliquer, et que je ne comble pas

Le nombre de déposables n'est **pas** monotone en longueur de queue :

```
pur optique   15 deposables / 416 variantes  =  3,6 %
queues longues (46-58)   11 / 117            =  9,4 %
queues courtes (64-70)    2 / 108            =  1,9 %
```

Une queue **longue** enrichit la proportion de déposables (9,4 % contre 3,6 %) — cohérent avec
« elle achète de la faisabilité ». Mais une queue **courte** fait **moins bien que le pur
optique**, tout en ayant un SEEL identique. 🔴 **Je n'ai pas d'explication, et je n'en invente
pas.** Une piste à mesurer, pas à supposer : 5 à 11 couches Rate en fin d'empilement suffisent
peut-être à casser les ancres POEM du dernier bloc sans apporter assez de couverture pour le
compenser. **Ce serait à vérifier par le profil de plantage par couche, pas par le raisonnement.**

### ⚠️ Portée, et elle est plus large qu'au §14 — mais pas illimitée

**Une seule graine.** La règle du §14 impose d'attendre la seconde avant de conclure sur un
composant **marginal**. `75c` @ 1 nm ne l'est pas : 15 déposables, `crash_min` à 4,00 % partout,
aucun basculement de verdict en vue — c'est le régime « confortable » où §24-46 a mesuré que la
graine ne décide de rien. **L'écart de 7,4 σ ne peut pas être renversé par une graine.**
📌 Ce qui reste à confirmer par une seconde graine est le **détail** — la place exacte du coude
entre 58 et 64 — pas le sens du résultat.

---

## 17. 🔵 BATCH DU 2026-08-20 — l'expérience qui isole la règle DANS UN SEUL COMPOSANT

📌 Le batch est [`scripts/batch_nuit_2026-08-20.py`](../scripts/batch_nuit_2026-08-20.py), et son
en-tête porte le raisonnement complet. **Écrit et committé avant qu'il ne tourne.**

### 🔴 Le défaut de protocole qu'il répare, et il bloque toute publication

Le résultat phare du chantier — *la queue Rate rend `r75x2` fabricable **à 2 nm*** — est mesuré en
**`fast`**, alors que la comparaison pur optique à laquelle on l'oppose est en **`deep`**. Deux
profondeurs différentes : c'est **l'erreur n° 3 du §5 de `CLAUDE.md`**, deux choses changées à la
fois. Tant que ce n'est pas réparé, on ne sait pas si c'est la queue qui sauve le composant ou la
profondeur de recherche qui manquait — c'est-à-dire exactement l'attaque 3 du §12, qu'on croyait
réfutée par le §13.

### 🔑 Pourquoi cette expérience vaut mieux que toutes les précédentes

La règle « faisabilité contre précision » repose aujourd'hui sur **deux composants différents**,
donc sur une comparaison qui mélange l'effet de la queue et l'effet du composant. 📏 Or `r75x2`
en `deep` à 2 nm offre les deux régimes **à lui seul**, selon la graine :

```
graine 42  ->    0 deposable en pur optique   (l'optique ECHOUE)
graine 77  ->  547 deposables, SEEL 0,569     (l'optique REUSSIT, et tres bien)
```

**Même composant, même mode, même fente, même grille de notation. Seule la graine change.** Y
ajouter la même queue Rate teste la règle *toutes choses égales par ailleurs* — ce qu'aucune
mesure du chantier n'a encore fait.

### 🔵 La prédiction, posée d'avance

> **À la graine 42 la queue SAUVE (déposables > 0). À la graine 77 elle COÛTE (SEEL nettement
> au-dessus de 0,569, au-delà de 2 σ, soit > 0,598).**

| ce qui la réfuterait | ce qu'il faudrait en conclure |
|---|---|
| graine 42, **0 déposable en `deep`** | 🔴 le résultat phare ne survit pas au changement de profondeur. Les 5 déposables du `fast` étaient un artefact du criblage court, et **la queue ne sauve rien** |
| graine 77, la queue **égale ou bat** 0,569 | « elle paie en précision » est faux, ou pas général. Le +19 % du `75c` viendrait du composant, pas de la queue |
| les deux graines se comportent **pareil** | ce n'est plus la faisabilité qui commande, et il faut chercher ailleurs ce que la queue fait vraiment |

La cellule 1 — `75c` à 1 nm sur la graine **77** — passe en premier parce qu'elle coûte 40 min :
elle établit la place du coude entre les coupures 58 et 64, que rien n'établit aujourd'hui.

---

## 18. 🔴 CELLULE 5 — LE RÉSULTAT EXISTE, MAIS JE NE PEUX PAS L'ATTRIBUER

`reports/blocs_vs_plantage_r75x2_fast_s042_tail46-58k.json`, **35,4 min**, 784 stratégies.

C'était le test de la règle d'exception de 👤 — *« sauf les couches avec au moins 2 turning
points qui restent en optique »*.

```
famille            n  crash_min  depos     SEEL  blocs        reference sans exception
RATE_TAIL46      113      4.00%      1   0.7408     75          0.752    ->  -1,5 %  (0,6 σ)
RATE_TAIL52      113      4.00%      1   0.7438     75          0.689    ->  +7,9 %  (3,1 σ)
RATE_TAIL58      113      4.00%      1   0.7433     75          0.735    ->  +1,1 %  (0,4 σ)
PUR_OPTIQUE      445    100.00%      0        -      -
```

### 🔴 Pourquoi ce tableau ne prouve rien, et c'est ma faute

`par_swing = 3` arme **deux** drapeaux — `rate_by_swing` **et** `rate_tail_keep_optical = 4` —
alors que la référence à laquelle je le compare n'en a **aucun**. **Deux choses changent à la
fois : c'est l'erreur n° 3 du §5 de `CLAUDE.md`**, et elle est de ma main, dans la conception du
batch.

📏 **Et je ne peux pas écarter `by_swing` comme inerte** : mesuré sur les artefacts, il ajoute
**26 origines** à la population de `r75x2` (`RATE_L47(from 3801)`, `RATE_L65(from 900000004)`…).
Les familles de queue gardent bien **113 variantes** chacune de part et d'autre, mais la
population dans laquelle elles sont classées, elle, a changé.

⚠️ **Le couplage n'est PAS un caprice de la sonde** : `keep_optical` a besoin du contexte de
swing pour savoir quelles couches ont deux points tournants. Sans `by_swing`, `swing_ctx` vaut
`None` et la règle est sautée **en silence** — c'est ce qui avait déjà fait rendre à un run de
56 min un doublon exact du run sans exception, le 2026-08-19. Le bon contrôle n'est donc pas
« sans swing », c'est **« avec swing, sans réouverture »**, et la sonde ne savait pas le produire.

### ✅ Ce qui est réparé, et le contrôle qui part cette nuit

`par_swing = 5` est ajouté : **queue + swing, sans réouverture optique**. Il ne diffère de `3`
que par `keep_optical`, et son artefact porte un suffixe `s` là où `3` porte un `k` — donc aucun
écrasement. C'est la cellule 2 du batch du 20.

### 🟠 Ce qu'on peut quand même dire, sans attribuer

| | |
|---|---|
| la combinaison **ne bat la queue pure nulle part** | le meilleur des trois écarts est −1,5 %, soit 0,6 σ : rien |
| à la coupure 52 elle **coûte 7,9 %**, soit **3,1 σ** | c'est au-dessus du bruit mesuré, donc réel — mais imputable à l'un ou l'autre des deux drapeaux |
| 🔑 elle **aplatit la structure des coupures** | `0,7408 / 0,7438 / 0,7433` — une étendue de **0,4 %** là où la queue pure en montre **9,1 %**. Le choix de la coupure, qui était la seule chose que ce composant permettait de discriminer, **cesse d'exister** |
| le plantage et le nombre de déposables ne bougent pas | `4,00 %` et 1 déposable partout, comme la queue pure |

📌 L'aplatissement est le fait le plus intéressant des quatre, et le seul qui ne demandait pas
d'attribution pour être vu. Il est cohérent avec la lecture prédite — des couches optiques
rouvertes au milieu de la queue dominent le résultat et effacent ce que la position de la coupure
apportait — **mais il reste une observation, pas une explication.**

---

## 19. 🔴 CELLULE 6 — LA COURBE `SEEL(n)` A ÉCHOUÉ UNE SECONDE FOIS, ET J'AI LE POINT EXACT

`reports/prefixe_optique_r75x2_premium_s042.json`, **45,8 min**, `courbe: []`.
**Deuxième artefact vide, après celui de 100 min du 2026-08-19.**

### 🔴 Le pire n'est pas l'échec, c'est qu'il s'est annoncé « OK »

Les deux runs sont sortis avec le **code 0**. Le pilote de batch a donc affiché `OK` pour deux
pannes, et le bilan de la nuit lisait **6/6 OK**. C'est exactement le motif que `CLAUDE.md`
dénonce d'un bout à l'autre : *ça ne produit pas d'erreur, ça produit un résultat plausible*.

✅ **Réparé** : la sonde rend désormais **le code 2** sur une courbe vide, imprime les familles
de stratégies réellement vues, et donne l'ordre de diagnostic. L'artefact porte en plus un champ
`familles_vues`, pour qu'un artefact vide se dénonce **tout seul** à la relecture.

### 📏 Ce que le diagnostic a établi, et ce qu'il n'a pas établi

| ✅ établi | |
|---|---|
| **aucune ligne `[PREFIX]` dans 220 min de journal** | ni l'info, ni l'avertissement. `_optical_prefix_variants` sort donc au seul point muet : `if not sweep: return []` (`certus_strat_robustness.py:820`) |
| **donc `optical_prefix_sweep` n'atteint pas le calcul** | ce n'est pas « aucune stratégie couche-par-couche » — cette branche-là, elle, journalise |
| **le DTO n'est pas coupable** | testé à part : `StratParamsDTO(**{...})` conserve la clé dans `model_extra` et `.get()` la rend. `rate_tail_sweep` passe par le même chemin et fonctionne |
| **le hoist au-dessus du garde `allow_rate` est bien en place** | ligne 935, vérifié — ce n'était donc pas le correctif d'hier qui manquait |

| 🔴 non établi | |
|---|---|
| **où la clé se perd** | entre le `collect_params` surchargé de la sonde et le `params` reçu par `_expand_with_rate_variants`. Le compteur de la sonde prouve que la surcharge est appliquée au moins deux fois, mais rien ne prouve que c'est **cet** objet qui descend |

⚠️ **Une inférence que j'ai faite et qui était fausse** : j'ai cru un moment que le run n'avait
parcouru qu'un seul compteur de blocs, le journal ne montrant que `[Block 1]`. 📏 **La cellule 4,
qui a parfaitement réussi, n'affiche elle aussi que `[Block 1]`.** Ce marqueur ne désigne pas le
balayage de blocs. L'hypothèse est retirée.

### ⏭️ Ce qui suit, et pourquoi pas maintenant

L'instrument qui trancherait est une ligne de journal **inconditionnelle** à l'entrée de
`_expand_with_rate_variants`, disant si `optical_prefix_sweep` est présent dans le `params`
reçu. C'est trois lignes. 🔴 **Mais elle touche au code de PRODUCTION, et le batch du 20 tourne
avec les cellules 3 et 4 non démarrées** : elles hériteraient de la modification en cours de
route, et deux cellules d'une même campagne ne seraient plus comparables. **Reporté à la fin du
batch.** C'est la contrainte C3 — une chose à la fois — appliquée à l'outillage comme au reste.

---

## 20. 🟢🟢 LE DÉFAUT DE PROTOCOLE EST RÉPARÉ, ET LE RÉSULTAT PHARE SURVIT

`reports/blocs_vs_plantage_r75x2_deep_s042_tail49-55.json`, **114,3 min**, 2 873 stratégies,
`N = 300` consigné.

C'était l'objet du batch : le résultat phare était mesuré en **`fast`** et opposé à une
comparaison pur optique en **`deep`**. Deux profondeurs, donc deux choses changées à la fois.

```
PUR OPTIQUE, deep, graine 42 :  0 deposable sur 1616, crash_min 100,00 %

 coupure  n_var  crash_min  depos     SEEL  blocs
      49    419      2.67%      1   0.7175     75
      52    419      2.67%      1   0.6859     75
      55    419      3.33%      1   0.7048     75
```

### 🔵 La prédiction est CONFIRMÉE, et le chiffre est meilleur que ce qu'elle demandait

> *« À la graine 42 la queue SAUVE (déposables > 0). »*

📏 **Elle sauve, et à `N = 300`.** Mais le fait qui compte est ailleurs :

```
coupure 52,  fast N=50   ->  SEEL 0.6885   crash 4,00 %  (2/50)
coupure 52,  deep N=300  ->  SEEL 0.6859   crash 2,67 %  (8/300)
                             ecart de SEEL : +0,38 %  =  0,15 sigma
```

🔑 **Les deux profondeurs donnent le même nombre.** Les 5 déposables du `fast` n'étaient donc
**pas** un artefact du criblage court — c'est précisément ce que la réfutation aurait signifié.
L'attaque 3 du §12 est close pour de bon : *ce n'est pas la profondeur de recherche qui manquait,
c'est bien la queue Rate qui rend ce composant fabricable **à 2 nm**.*

✅ Et le plantage tombe de 4,00 % à **2,67 %** en passant de 2/50 à 8/300 — même mouvement qu'au
§11, et **sous la cible de 5 % de 👤**.

---

## 21. 🟢 LA RÈGLE D'EXCEPTION DE 👤 EST ENFIN ATTRIBUABLE — et elle DÉGRADE

`reports/blocs_vs_plantage_r75x2_fast_s042_tail46-58s.json`, **33,6 min** — le contrôle
`par_swing = 5` ajouté cette nuit : queue + swing, **sans** réouverture optique.

```
 coupure     pure   +swing  +except    swing seul      exception seule
      46   0.7520   0.7517   0.7408    -0,0%  0,0σ     -1,5%  0,6σ
      52   0.6890   0.6885   0.7438    -0,1%  0,0σ     +8,0%  3,1σ   PIRE
      58   0.7350   0.7353   0.7433    +0,0%  0,0σ     +1,1%  0,4σ
```

🔑 **`rate_by_swing` est numériquement inerte sur la queue : 0,0 σ aux trois coupures.** Le
confusionnement du §18 existait bel et bien — il ajoute 26 origines à la population — mais il ne
déplace pas le meilleur SEEL de queue. ⚠️ **Cela ne rétrospectivement excuse rien** : on ne
pouvait pas le savoir sans le mesurer, et c'est le contrôle qui l'établit, pas le raisonnement.

🔵 **La prédiction du 19 est donc CONFIRMÉE, et maintenant proprement** :

> *« la règle d'exception dégrade ou ne change rien. »*

📏 **+8,0 % à la coupure 52, soit 3,1 σ** — au-dessus du bruit mesuré, donc réel. Ailleurs, rien.
**Elle ne gagne nulle part.** Le mécanisme prédit tient : rouvrir une couche optique au milieu de
la queue réintroduit un point de plantage **et** réexpose tout ce qui la suit.

📌 L'aplatissement des coupures relevé au §18 s'attribue lui aussi : il vient de la réouverture,
pas du swing.

---

## 22. 📏 LE COUDE DU `75c` BOUGE AVEC LA GRAINE — la direction tient, la position non

`reports/blocs_vs_plantage_75c_fast_s077_res1_tail46-70.json`, **35,1 min**, graine **77**.

```
 coupure  Rate     s042           ecart     s077           ecart
      46    29   0.4420     +19,1% 7,4σ   0.3853      +6,7% 2,6σ
      52    23   0.4400     +18,6% 7,2σ   0.3617      +0,2% 0,1σ
      58    17   0.4240     +14,3% 5,5σ   0.3623      +0,4% 0,1σ
      64    11   0.3720      +0,3% 0,1σ   0.3616      +0,2% 0,1σ
      70     5   0.3730      +0,5% 0,2σ   0.3616      +0,2% 0,1σ
```

*(pur optique : `s042` 0,371 · `s077` 0,3610 avec **225 déposables** et 0 % de plantage)*

| ✅ ce qui tient aux deux graines | |
|---|---|
| la queue **ne bat jamais** le pur optique | le meilleur écart est +0,2 % |
| une queue **longue coûte**, une queue courte est gratuite | monotone dans les deux cas |

| 🔴 ce qui ne tient pas | |
|---|---|
| **la position du coude** | `s042` : le coût s'installe dès la coupure **58** (17 couches Rate). `s077` : rien avant la coupure **46** (29 couches). Le coude s'est déplacé de **12 couches** |

🔑 **Ce que le §16 annonçait est exactement ce qui est arrivé.** Il disait : *« l'écart de 7,4 σ
ne peut pas être renversé par une graine — ce qui reste à confirmer est le détail, la place exacte
du coude. »* Le sens du résultat a tenu, la position a bougé. 📌 **On ne cite donc pas un nombre
de couches Rate « gratuites » : il dépend de la réalisation.**

---

## 23. 🟢🟢 CELLULE 4 — LA RÈGLE EST DÉMONTRÉE DANS UN SEUL COMPOSANT

`reports/blocs_vs_plantage_r75x2_deep_s077_tail49-55.json`, **175,8 min**, 3 506 stratégies,
`N = 300` consigné.

C'était l'expérience centrale du batch : jusqu'ici, *« la queue Rate achète de la faisabilité et
la paie en précision »* reposait sur **deux composants différents** (`r75x2` et `75c`), donc sur
une comparaison qui mélangeait l'effet de la queue et celui du composant.

```
r75x2 @ 2 nm, deep, graine 77
  PUR OPTIQUE : 518 deposables sur 2201, SEEL 0.5698, crash 1,00 %, 13 blocs

   coupure  n_var  crash_min  depos     SEEL     vs pur optique
        49    435      3.67%      1   0.7175    +25,9 %   10,0 σ
        52    435      3.67%      1   0.6859    +20,4 %    7,9 σ
        55    435      4.67%      1   0.7048    +23,7 %    9,2 σ
```

### 🔑 Les deux régimes, à composant, mode, fente et grille IDENTIQUES

| | pur optique | queue Rate |
|---|---|---|
| **graine 42** (§20) | 🔴 **0 déposable** sur 1616 | 🟢 **3 déposables**, SEEL 0,6859, crash 2,67 % |
| **graine 77** (ici) | 🟢 **518 déposables**, SEEL 0,5698 | 🔴 **1 déposable**, +20,4 % soit **7,9 σ** |

> **Seule la réalisation change. Là où l'optique échoue, la queue sauve ; là où elle réussit, la
> queue coûte huit sigma.** Le confusionnement « deux composants » est éliminé, et la règle
> *faisabilité contre précision* est démontrée **à l'intérieur d'un composant**.

✅ **Et la prédiction du §17 est confirmée dans ses deux branches** — elle demandait « SEEL
nettement au-dessus de 0,569, au-delà de 2 σ » à la graine 77 : mesuré **7,9 σ**.

### ⚠️ Deux observations à ne pas perdre

| | |
|---|---|
| **le pur optique bouge un peu entre les deux runs** | 0,5698 ici contre 0,5692 dans le run sans queue, et 518 déposables contre 547, la gagnante passant de 9 à 13 blocs. Écart de SEEL **0,1 %, soit 0,04 σ** — dans le bruit. 📌 Mais la cause est réelle : ajouter les variantes de queue change la population que le consensus rescore, donc **la présence d'une famille déplace légèrement le classement d'une autre.** |
| **le plantage de la queue monte à la graine 77** | 3,67 % et 4,67 % contre 2,67 % à la graine 42. La queue n'est donc pas *plus sûre* ici, elle est seulement *inutile* |
