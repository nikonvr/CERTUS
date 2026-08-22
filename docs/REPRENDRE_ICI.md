# 🔴 REPRENDRE ICI — état gelé le 2026-08-21 à 13:55

> Ce fichier dit **où on s'est arrêté** et **la commande exacte pour repartir**. Il est le
> premier à lire, avant `CLAUDE.md`.

---

## 0bis. 🔒 CLÔTURE DE LA JOURNÉE DU 2026-08-21

👤 a arrêté la campagne après le run à la graine 101. **Rien ne tourne, rien n'est en attente.**

### Ce qui est ACQUIS, et mesuré

```
r75x2 a 2 nm, config livree, plage COMPLETE, ZERO surcharge
  graine  42 (a choisi les rampes)  ->  SEEL 0,5676 nm   197 deposables / 1810
  graine  77 (source des rampes)    ->  SEEL 0,5692 nm   547 deposables / 2231
  graine 101 (NAIVE)                ->  SEEL 0,5707 nm   (bloc 10)

etendue sur trois graines : 0,55 %   face a un bruit de 2,59 % sur une DIFFERENCE de SEEL
avant la livraison        : 0 deposable sur 1617, 100 % de plantage
```

🔑 **La malédiction du vainqueur est bornée à +0,55 %**, là où le canal valait +12,9 % au 15/08.
C'était la seule réserve sérieuse sur le chiffre, et la graine 101 — qui n'a pas participé au
choix des rampes — la lève.

### Ce qui reste OUVERT, et ce qui l'a été laissé délibérément

| | |
|---|---|
| **graine 202 sur la config livrée** | non mesurée — arrêt demandé. Trois graines valent mieux que deux, quatre auraient valu mieux que trois |
| 🔑 **`r75x2` NU aux graines 101 et 202** | **non mesurées, et c'est la question de fond restée sans réponse** : *la graine 42 est-elle malchanceuse, ou la 77 chanceuse ?* La règle de décision est écrite en §8.2 — la relire **avant** de lancer, pas après |
| **un second composant** | 🔒 écarté par 👤 — voir §8.2bis, qui dit ce que cela interdit d'affirmer |
| **l'anomalie plantage/bruit** | 8,72 contre 1 dans le mauvais sens. Ne menace pas la livraison (la porte prend le maximum, donc conservateur) mais on ne comprend pas le mode d'échec |
| **les rampes vivent dans `reports/`** | une **configuration** ne devrait pas dépendre d'une **sortie**. Déplacement vers `example/` à faire — plus rien ne tourne, donc c'est sans risque maintenant |

### 🟢 Ce qui a été CONSTRUIT aujourd'hui

| | |
|---|---|
| **`scripts/generer_rampes.py`** | la méthode qui a livré le résultat, devenue **une commande**. 33 tests. 10 rampes sur **7 structures de blocs**, contre 12 quasi-doublons assemblés à la main |
| **la couverture en λ** | forcer une λ admissible absente ; mécanisme mesuré (601 → 901 groupements, 0 infaisable aux blocs 13-15), **routée**, inerte par défaut, 36 tests. 🔴 **Elle n'est pas le levier de l'autonomie** — la DP ne produit rien sous 11 blocs |
| **les instruments** | 66 scripts protégés du cp1252 **+ garde-fou**, l'artefact écrit **avant** la synthèse, les compteurs de couverture sur un canal **lu** |
| **`scripts/probe_plantage_vs_sigma.py`** | le test du Piège 1, enfin fait |

### 🔴 Ce qui a été RÉFUTÉ ou CORRIGÉ — la partie la plus utile

Neuf affirmations retirées en une journée, dont **sept étaient les miennes** :

| affirmation | verdict |
|---|---|
| « ELITE ne compose jamais deux mouvements » | ❌ elle en compose deux **entre rondes** ; la gagnante est à 1 pas de λ + 1 pas de frontière |
| « l'inversion crash/bruit est du bruit de comptage » | ❌ **532 contre 61** — systématique |
| « la contrainte ne porte qu'une valeur » | ❌ 38 valeurs, mais aux blocs 10-15, **disjoints** des déposables |
| « la DP est vide aux blocs 9-10 » | ❌ trop étroit — **vide à 10 et en dessous** |
| « les 547 déposables de la graine 77 = une lignée » | ❌ **217 jeux de λ** ; le 1 venait d'un artefact sans plans |
| « restreindre la plage ne perd rien » | ❌ elle **vide la DP** |
| `use_margin_ranking` comme levier | ❌ marges **1 500×** hors du domaine validé |
| le garde `halving` comme coupable | ❌ même taux par ronde dans le run qui **réussit** |
| `SMART_MERGE` comme cible | ❌ **zéro `SMART_MERGE`** chez la graine qui réussit |

🔑 **Et le diagnostic qui remplace tout cela, appuyé sur une géométrie mesurée** : aux nombres de
blocs qui décident, la contrainte est **binaire** — 100 % de plantage aux trois niveaux de bruit,
ou déposable, rien entre les deux. **Le paysage n'est pas une colline sans pente, c'est une
falaise.** ELITE est un grimpeur : 0 candidate retenue sur 2472 sans rampes, 388 sur 6343 avec.
Les rampes n'apportent pas de la diversité, elles apportent de la **faisabilité** — elles
atterrissent de l'autre côté.

Cela **ferme toute la classe des correctifs de classement**, pour une raison géométrique et non
par essais successifs. Et il ne reste que trois voies, dont une seule est générale : **changer de
réalisation**, c'est-à-dire le multiseed de génération — union sur K graines, faisabilité exigée
sur **toutes**.

---

## 0. ⚡ LA SITUATION EN CINQ LIGNES

👤 voulait que le code de **production** trouve sur `r75x2` à **2 nm** des SEEL « de l'ordre de
0,57 ou moins ». À la graine 42 seule, il rendait **0 déposable sur 1617**, toutes à 100 % de
plantage.

### 🟢🟢 C'EST FAIT — test d'acceptation passé le 2026-08-21 à 12:58

```
composant  example/example_strat/JSON-strat-random75-x2-fabricable-2nm.json
fente 2 nm · graine 42 · mode deep · PLAGE DE BLOCS COMPLETE
config.overrides_tag = None          <- la preuve du ZERO surcharge

197 deposables sur 1810        (avant : 0 sur 1617)

 rg blocs   score    SEEL     crash   origine
  1     9  0,08053  0,5676   1,67 %   ELITE   <- id 900000044
  2     9  0,08113  0,5697   1,33 %   ELITE
  4     9  0,08161  0,5714   1,00 %   ELITE
  6     8  0,08166  0,5715   1,00 %   ELITE

deposables par nombre de blocs : {5: 13, 6: 46, 7: 46, 8: 49, 9: 43}
artefact : reports/blocs_vs_plantage_r75x2-2nm_deep_s042.json
```

**La gagnante, en clair** — et le bloc qui manquait y est :

```
 0-8  @ 450 nm       33-52 @ 685 nm   <- LA lambda absente des 1617 natives
 8-25 @ 610 nm       52-57 @ 647 nm
25-33 @ 616 nm       57-63 @ 700 nm · 63-65 @ 511 · 65-68 @ 687 · 68-75 @ 704
```

🔑 **LA CONDITION EST DANS LA MÊME PHRASE QUE LE CHIFFRE, ET ELLE Y RESTE.** Ce résultat vient
**avec les rampes de lancement** déclarées dans la configuration du composant
(`injected_strategies`). C'est bien de la production — la configuration est livrée, le run n'a
aucune surcharge — mais **ce n'est pas une découverte autonome** : l'information des rampes
descend de la graine 77. Qui citera « 0,5676 nm » sans cette condition dira faux.

⚠️ L'écart à la cible vaut 0,3 % et le bruit sur une différence de SEEL vaut 2,59 % : c'est une
**égalité**, jamais une supériorité.

### 🔑 Le mécanisme, mesuré et non supposé

Les parents qu'ELITE reçoit au bloc 9 portent les bonnes λ et **plantent tous à 100 %**. La
gagnante est un **descendant**, à **deux mouvements** de sa rampe :

```
bloc 2 :  rampe (25, 33, 615)  ->  gagnante (25, 33, 616)     UN pas de λ
bloc 3 :  rampe (33, 53, 685)  ->  gagnante (33, 52, 685)     UN pas de frontiere

barre de selection : ronde 1  0,268856  ->  ronde 2  0,077943    (facteur 3,4)
```

Les rampes apportent les λ ; **ELITE compose deux pas à travers deux rondes**. ⚠️ Cela corrige
une phrase de §24.3 du plan qui disait qu'ELITE « ne compose jamais deux mouvements » — faux.
Ce qui ferme la voie native n'est pas l'impossibilité de composer, c'est que **chaque pas
intermédiaire plante**, donc rien n'est retenu pour bâtir dessus.

---

## 1. 🔴 LA PREMIÈRE CHOSE À FAIRE — borner la malédiction du vainqueur

**Ce n'est plus la découverte autonome. C'est la solidité du chiffre livré.**

🔴 **Le résultat est circulaire, et sur DEUX plans distincts :**

```
graine 77 trouve la famille
  -> injection des plans de la graine 77 dans la graine 42   -> 72 deposables
    -> je garde les 12 MEILLEURES de ces 72                  -> les rampes livrees
      -> remesure a la graine 42                             -> 197 deposables, 0,5676
```

1. **L'information vient de la graine 77.** Assumé, écrit, et sans conséquence sur la validité
   du chiffre.
2. 🔴 **Sélection et évaluation partagent la graine 42.** Les 12 rampes ont été choisies sur des
   mesures à la graine 42, puis remesurées à la graine 42. C'est **le canal de malédiction du
   vainqueur, chiffré à +12,9 % le 15/08**. Le 0,5676 peut donc être biaisé vers le bas, et
   **aucune borne n'existe**.

**La commande qui tranche**, et elle est bon marché — une graine qui n'a pas servi à choisir :

```bat
set CERTUS_PROBE_TAG=accept101
C:\envs\certus\Scripts\python.exe scripts\probe_blocs_vs_plantage.py r75x2-2nm deep 0 0 2.0 0 101
```

| ce qu'elle rend | ce qu'il faut en conclure |
|---|---|
| SEEL de tête vers **0,57** | le chiffre est **solide**, la sélection n'a pas triché |
| SEEL vers **0,60 et plus** | une part du 0,5676 était du **biais de sélection**, et il faut republier |
| **0 déposable** | les rampes ne transfèrent pas d'une graine à l'autre — ce serait le résultat le plus important de la série |

---

## 1bis. 🔵 LA VOIE AUTONOME — où elle en est

La **couverture en λ** est le premier levier qui ne cherche pas *autour* de ce qui existe : elle
**force** une λ admissible absente des `top_k` groupements en restreignant une couche de la
`cost_map` à cette seule λ, et laisse la DP **re-optimiser le reste du plan**. C'est la
différence avec une mutation ELITE, qui casse la cohérence du plan.

📌 Écrite, inerte par défaut (`enable_wl_coverage`), **routée** depuis un fichier de
configuration, gardée par **36 tests**. §25 du plan porte le détail, dont le défaut de plan
d'identifiants qu'elle a fait trouver (offsets 0/100/200 saturés à `top_k = 100` en DEEP).

### 🟢 LE MÉCANISME EST CONFIRMÉ EN PRODUCTION — mesuré le 2026-08-21, run `couvfull`

Plage de blocs **complète**, composant `r75x2` (le fichier de base, **sans rampes**),
`enable_wl_coverage=1` pour seule surcharge. Le contrôle est le run à plage complète sans
couverture : **0 déposable sur 1617**.

```
bloc  15  140 λ deja employees,  763 absentes -> 300 ajoutees,   0 infaisable
bloc  14  109 λ deja employees,  794 absentes -> 300 ajoutees,   0 infaisable
bloc  13   66 λ deja employees,  837 absentes -> 300 ajoutees,   0 infaisable
bloc  12   59 λ deja employees,  844 absentes -> 270 ajoutees,  30 infaisables

bloc 15 : la population passe de 601 a 901 groupements  (+300, exactement les ajouts comptes)
```

| ce qui est établi | |
|---|---|
| **forcer une λ est faisable** | 0 infaisable sur 900 tentatives aux blocs 15, 14, 13 |
| **la passe atteint le calcul** | 601 → 901 groupements, soit **exactement** les 300 ajouts comptés |
| **ses produits sont compétitifs** | au bloc 14, `couvfull` rend **0,29479** contre **0,29482** pour le run d'acceptation : une stratégie **issue de la couverture** traverse le criblage et sort première de son nombre de blocs |
| **le coût est mesuré** | 300 appels DP en ~1 min 42 par nombre de blocs |

🔑 **Et une tendance qui joue en notre faveur** : le nombre de λ que le k-meilleurs emploie
s'effondre quand les blocs diminuent — 140, 109, 66, 59 — donc l'élargissement relatif **grandit**
en approchant du bloc 9, celui où vit la famille à SEEL 0,5676. ⚠️ En contrepartie les premières
infaisabilités apparaissent au bloc 12 : moins de blocs, plus de couches par bloc, contrainte
plus dure. Ce n'est pas un défaut de la passe, c'est la géométrie du problème.

🔴 **CE QUI N'EST PAS RÉPONDU.** Faire entrer une λ dans la population et produire une stratégie
**déposable** sont deux événements, et le second ne découle pas du premier. Les blocs 15 à 12
restent tous à **100 % de plantage**. Le nombre de blocs qui décide est **9**.

### ⚠️ Le premier essai a été perdu, et pour trois défauts d'instrument

| # | défaut | ce qu'il a coûté |
|---|---|---|
| 1 | le logger `ThinFilm` du mineur est **MUET** — sa ligne `info` inconditionnelle apparaît **zéro fois** dans les journaux, alors que le logger `W{n_blk}` du worker passe | impossible de distinguer « la passe n'a pas tourné » de « chaque λ forcée était infaisable ». Piège 6 |
| 2 | **troisième plantage cp1252**, dans `synthese()` | l'artefact d'un run de 50 min **jamais écrit** |
| 3 | les runs à **plage restreinte** minent 1 à 2 stratégies par nombre de blocs, contre 601 à plage complète | le contrôle négatif `ctrl911sansinj` est bien plus mince que ses « 63 stratégies » |

🟢 **Les trois sont réparés** (`8118721`) : 66 scripts protégés plus un garde-fou qui refuse tout
nouveau cas, l'artefact s'écrit **avant** la synthèse, et les compteurs de couverture remontent
par le logger du worker — avec un `logger.error` si le drapeau est armé et les compteurs vides.

> **Un instrument dont la sortie n'atteint pas le résultat n'est pas un instrument.**

---

## 1ter. 🔴 L'ANOMALIE À NE PAS OUBLIER — le plantage décroît quand le bruit croît

```
sur les 197 deposables   :  125 DECROISSANTES ·  61 croissantes ·   11 plates
sur les 1810 strategies  :  532 DECROISSANTES ·  61 croissantes · 1217 plates
```

**8,7 contre 1 dans le mauvais sens, donc systématique.** ⚠️ J'avais d'abord écarté cela par un
argument de Poisson (« 5 plantages contre 1 et 1 ») — **retiré** : c'était substituer un
raisonnement sur le bruit au test que le Piège 1 prescrit.

**Ce que ça change** : la porte prend le **maximum** des trois niveaux, donc le `1,67 %` publié
vient du bruit **le plus faible** — lecture conservatrice, le verdict « déposable » n'est pas
menacé. **Ce que ça ne change pas** : on ne comprend plus le mode d'échec, et cela touche toute
mesure de plantage du projet, murs à 100 % compris. Le balayage σ→0 reste à faire.

---

## 2. ✅ CE QUI EST EN PRODUCTION DEPUIS CETTE NUIT

| | commit |
|---|---|
| **`screen_seed_list`** — K criblages, **union par signature de plan**, au point de divergence des graines | `44f352d` |
| **`injected_strategies`** — verser des plans donnés dans la population, par le canal de l'héritage | `43f7144` |
| **`[ELITE-WL]`** — la λ **et** la bande de plantage des candidates rejetées | `5105fc8` |
| **`[GATE]`** — combien de fois la borne de confiance change le verdict | `0117445` |
| surcharges génériques de la sonde, **étiquette obligatoire** | `1f39cdd` |
| `scripts/lire_multiseed.py` — et il **refuse de conclure** sur du partiel ou du dégénéré | `67c321b` |
| **`enable_wl_coverage`** — forcer une λ admissible absente des `top_k`, la DP re-optimise le reste. Routée, 36 tests | `9590be2` |
| **la livraison `r75x2-2nm`** — 197 déposables, SEEL 0,5676, zéro surcharge | `2bbab58` |
| **les instruments** — 66 scripts protégés du cp1252 + garde-fou, artefact écrit **avant** la synthèse, compteurs de couverture sur un canal **lu** | `8118721` |

🔒 **Tous inertes par défaut, chemin d'avant au bit.** Chacun a ses tests, et les symboles sont
absents du commit précédent — donc ils échouent tous sur le code d'avant.

### Comment essayer un levier sans écrire de fichier de configuration

```bat
set CERTUS_PROBE_OVERRIDES=injected_strategies=reports/plans/plans_s077_vers_s042.json
set CERTUS_PROBE_TAG=inject12s077
C:\envs\certus\Scripts\python.exe scripts\probe_blocs_vs_plantage.py r75x2 deep 0 0 2.0 0 42 0
```

🔴 **L'étiquette est obligatoire, la sonde refuse sans elle** : deux runs qui ne diffèrent que
par une surcharge rendraient sinon deux artefacts indiscernables. ⚠️ Le parseur découpe sur les
**virgules** — une liste de graines s'écrit donc `screen_seed_list=42;77;101`.

🔴 **NE RESSERRE PAS LA PLAGE DE BLOCS POUR ÉCONOMISER DU TEMPS.** Cette ligne disait
*« ce qui divise le coût sans rien perdre »* — **c'est faux, et mesuré le 2026-08-21** :

```
plage RESTREINTE  ->  Mining found 1 a 2 par nombre de blocs
                      compteur de couverture : « 0 λ deja employees »
                      donc AUCUN groupement rendu par la DP -- les 1 a 2 strategies
                      viennent des graines structurees
plage COMPLETE    ->  le meme bloc 9 en mine 601
```

**Restreindre la plage vide le solveur.** Toute la série de runs 9-11 du 21 août ne mesurait
donc pas la recherche. La cause exacte n'est pas établie : les libellés d'interface parlent de
**diviseurs de complexité** (*« divides the iteration count »*), pas de sélection de plage — et
le détournement fonctionne bien pour choisir les blocs (`75/8,3333 = 9`) tout en cassant la DP.

🔒 **Règle : toute mesure comparative de la RECHERCHE se fait à plage complète.** Une comparaison
à plage restreinte reste valide si elle est **à une seule variable** — c'est le cas du contrôle
injection oui/non — mais elle ne dit rien de la recherche. Consigné en §24-54 de `CLAUDE.md` et
§27 du plan de production.

⚠️ Les blocs **1, 2 et 75 sont forcés** par le code, on ne peut pas les exclure.

---

## 3. 📏 CE QUI EST ÉTABLI — tout sur `r75x2` à 2 nm, `deep`

**1. 🔑 Hors ELITE, il n'y a rien — aux DEUX graines.** 0 déposable sur 1488 (graine 77) et
0 sur 1617 (graine 42), crash médiane 100 %. Toute la fabricabilité passe par ELITE.

**2. 🔑 La génération d'ELITE est DÉTERMINISTE.** `_generate_elite_candidate_strategies` énumère
un voisinage trié, parent par parent, et `return` au plafond. Donc « K graines de génération »
**ne peut pas** fonctionner : K graines rendraient les mêmes candidates. La diversité vit dans
les **parents**.

**3. 🔑 Le point de divergence des graines est le CRIBLAGE.** Par signature de plan exacte :

```
n_blocs      1      2-6     7-10    11-15
communes  46,7 %   7,4 %   ~1 %      0 %
```

**Aucun préfixe commun** : dès le bloc 1, où rien n'est encore hérité, la moitié de la
population diffère. Phase A est identique aux deux graines et la DP est déterministe — seul le
criblage Monte-Carlo l'est, et ses survivants deviennent les `inherited_strategies` du bloc
suivant **et** les parents d'ELITE.

**4. 🟢 Le multiseed est un mécanisme réel et il NE SATURE PAS.** Apport moyen en plans neufs
par rang de graine : **5,88 · 5,38 · 4,50 · 5,25 · 4,50**. La cinquième apporte autant que la
deuxième. Et l'effet est **localisé aux blocs 11-13**, là où la DP rend assez de groupements pour
que le criblage ait de quoi trancher.

**5. 📏 Le profil de coût par nombre de blocs**, et le partage **criblage 47 % / ELITE 53 %** :

```
bloc 75 : 1,1 min   ·   blocs 11-14 : 7,9 a 8,3   ·   blocs 3-10 : ~5,1   ·   bloc 1 : 2,8
facteur(K, cap) ~= 0,47.K + 0,53.(cap/120)
```

**6. 🔑 Le plafond de 120 laissait SEPT PARENTS SUR DIX inexplorés.** Un parent à 11 blocs coûte
~42 candidates (`n_blocs × 2` mutations de λ + `(n_blocs−1) × 2` frontières), donc `120/42 ≈ 2,9`
parents sur les 10 annoncés. À 480, mesuré : `generated=424 parents=10`.

**7. 🔵 La porte de plantage juge au PIRE DES TROIS NIVEAUX DE BRUIT**, dont un à **2× le bruit
mesuré** (`robustness_noise_factors = [0.5, 1.0, 2.0]`). La tolérance de 5 % de 👤 s'y applique,
et **aucun artefact ne porte le taux au bruit réel** — `crash_rate` **est** le max. Non mesuré :
c'est l'action 5 du §8.

---

## 4. 🔴 CE QUI EST RETIRÉ — ne pas le recycler

| affirmation | statut |
|---|---|
| « la panne de `probe_renoter` est localisée : `full_dynamics_grid` est vide » | 🔴 **FAUX.** La grandeur n'est déréférencée qu'à **un seul endroit** — `robustness.py:2513`, dans un bloc de **journalisation** gardé par `theory_dyn >= 0.0` — et la Phase B de **production** tourne toujours avec elle vide |
| « le plantage est une propriété de la stratégie » | 🔴 non informatif — vient de l'outil en panne |
| « `crash_gate_confidence` est le meilleur rapport valeur/risque du plan » | 🔴 **mesuré faux** : 0 déposable, compteurs identiques au chiffre près. **Une seule candidate sur 1116** est dans la bande où la borne agit — elle épargne jusqu'à ~7,3 % à `N = 300`, et les rejets sont à 25-99 % |
| « élargir `elite_wl_neighbor_span` aiderait » | 🔴 **réfuté** : `span = 2` porte le coût par parent de 42 à ~64, donc **aggrave** la troncature qu'il prétendait corriger |
| « le code de production reste à `robustness_seed = 42` définitivement » | 🔴 **levée par 👤 le 2026-08-21** — voir §7 |
| « forcer 685 nm » | 🔴 **inutile** : hors ELITE, 711 stratégies y plantent **toutes**, et 3 ELITE à 686 nm sont déposables. La λ n'est ni suffisante ni nécessaire — c'est un **effet de sélection**, ELITE s'est empilé là où ça marchait déjà |

### 🔴 La cause de la panne de `probe_renoter.py` reste NON LOCALISÉE

**Six candidates éliminées**, sans machine : la grille vide · l'unité de `crash_rate` (le noyau
la formate `:.1%`, c'est une fraction, le `100 ×` était correct) · des plans malformés (les blocs
pavent `[0,75)` exactement) · le chemin de **surcharge** de résolution (le config natif 2 nm rend
une marge **bit-identique**) · `expand_variants=False` (le garde ne couvre que la génération de
variantes) · une clé perdue sur `strategy`.

🟢 **`injected_strategies` le remplace et rend la réparation inutile** : les plans traversent le
code de production, sans contexte reconstruit. La docstring de la sonde porte l'avertissement.

### ⚠️ Deux défauts d'instrument, dits parce qu'ils fausseraient une lecture

- **Le compte d'une λ RARE n'est pas lisible dans le journal.** `_format_wl_histogram` n'affiche
  que les **14 λ les plus lourdes** ; 685 nm en porte 1 à 2 par ronde et tombe dans la queue
  masquée. **61 histogrammes tronqués** sur un seul run, et la preuve interne est là : 685 nm
  apparaît 5 fois en génération et **11 fois dans les rejets** — impossible sans troncature. Le
  compte est un **plancher**, et le contrôle du §18.4 du plan n'est ni confirmé ni réfuté.
- **Les graines de génération ne doivent pas contenir la graine de NOTATION.** Le run de la nuit
  a généré sur `42;77;101;202;303` et noté à **42** : canal de **malédiction du vainqueur**,
  mesurée à +12,9 % le 15/08. Générer sur `{77,101,202,303}`, noter sur une base disjointe.

---

## 5. Les fichiers à connaître

| | |
|---|---|
| `reports/nuit_multiseed_20260821/journal_*.log` | les journaux **complets** de la nuit |
| `reports/BATCH_seed42_20260820_235821.md` | le rapport du batch : `base` (porte C1) et `cgc95` |
| `reports/blocs_vs_plantage_r75x2_deep_s042_20260820_120112.json` | la **référence** graine 42, 1617 stratégies |
| `reports/blocs_vs_plantage_r75x2_deep_s077_20260820_160340.json` | les 547 déposables de la graine 77, **avec λ** |
| `reports/plans/plans_s077_vers_s042.json` | les 12 plans injectés — 9, 10 et 11 blocs |

---

## 6. ⚡ Repartir

```bat
C:\envs\certus\Scripts\python.exe scripts\preflight.py
C:\envs\certus\Scripts\python.exe scripts\coherence_md.py
C:\envs\certus\Scripts\python.exe -m pytest tests/oracle/ tests/unit/ -q --no-cov
```

Attendu : `PREFLIGHT=GO` · `0 point(s) a instruire` · **`0 failed`**.

⚠️ **Ne cite jamais un compte de tests comme référence** — il se périme dès qu'on ajoute un test.
Il valait 2450 le 17/08 et plus de 2560 le 21/08. **Le seul critère est `0 failed`**, comme
c'est écrit plus haut dans ce document, qui est désormais le **seul** document d'arrivée.

⚠️ **L'interpréteur est `C:\envs\certus\Scripts\python.exe`.** Il n'y a **pas** de `.venv` dans
le dépôt ; tout document qui en cite un est faux.

---

## 7. 🔵 LA CONTRAINTE MONO-GRAINE EST LEVÉE — ce qui tombe, ce qui reste

👤, 2026-08-21 : *« même si le code en production est ralenti, ce sera un gain énorme d'inclure
des stratégies diverses venant de plusieurs seed »*.

| | |
|---|---|
| la **RECHERCHE** est multi-réalisation | ✅ tranché |
| la **NOTATION** finale reste-t-elle à une graine fixe ? | 🔴 **ouvert, et c'est une décision de 👤** |

Un score publié doit être **reproductible** — sinon deux lancements du même fichier rendent deux
SEEL. Et si la notation tourne sur les mêmes graines que la génération, on paie la malédiction du
vainqueur. 📌 **Proposition par défaut** : générer sur K graines, **noter sur une base fixe et
disjointe**.

🔒 **Et le mécanisme livré respecte déjà la règle d'or du multiseed** — *on ne s'en sert jamais
pour garder la graine qui marche* : l'union ne transporte que des **plans**, jamais des scores, et
la passe complète **renote tout** sur la réalisation du run. Un test l'épingle
(`test_the_multiseed_union_never_reranks_across_seeds`).

---

## 8. 🔵 CE QUI SUIT, PAR RENTABILITÉ — révisé le 2026-08-21 à 15:00

⚠️ **La version précédente de cette section est périmée** : trois de ses cinq actions sont
faites, et sa « voie B » a reçu sa réponse. Ce qui suit la remplace.

### 8.1 ✅ Ce qui est FAIT, et qu'il ne faut pas refaire

| action d'alors | ce qu'il en est |
|---|---|
| **1. toujours afficher la liste des λ** | ✅ la troncature du `[ELITE-WL]` est retirée (`8f7f14b`). Et la question qu'elle devait trancher — *où 685 nm disparaît-elle* — a sa réponse : **nulle part, elle n'entrait jamais**. Le k-meilleurs ne la sélectionne pas, et la couverture la **force** |
| **4. remonter `crash_rates_by_noise`** | ✅ dans l'artefact, et `scripts/probe_plantage_vs_sigma.py` l'exploite. Il a trouvé bien plus que prévu — voir §1ter |
| **5. rejouer l'injection en plage pleine** | ✅ c'est le **test d'acceptation** de §0 : 197 déposables, SEEL 0,5676, zéro surcharge |
| **2. compter par étage** | 🟠 **à moitié** : le minage se compte maintenant (compteurs de couverture), et cela a révélé que la DP est **vide** à plage restreinte. Le criblage et l'héritage ne se comptent toujours pas |

### 8.2 🔵 Ce qui reste, par rentabilité — **révisé à la reprise du 2026-08-22**

⚠️ La version d'hier listait des actions depuis faites, et n'y mettait **pas** la question de
fond. Voici l'état réel.

**✅ Ce qui est fait, et qu'il ne faut pas relancer :**

| action d'hier | ce qu'il en est |
|---|---|
| lire `couvfull` au bloc 9 | ✅ **tranché** : la DP est vide à **10 blocs et en dessous**, donc la couverture n'a rien à étendre là où les déposables vivent. §30 et §31 |
| rejouer la config livrée à la graine 101 | 🟠 **partiel** : blocs 15 à 8 lus dans le journal, meilleur **SEEL 0,5707 au bloc 10** (crash 0-2 %). Le run a été arrêté à la demande de 👤 et **n'a pas écrit d'artefact** — les chiffres sont donc dans le journal, pas dans un artefact citable |

**🔵 Ce qui reste :**

| # | action | coût | ce qu'elle décide |
|---|---|---|---|
| **1** | 🔑 **`r75x2` NU (sans rampes) aux graines 101 et 202** | 2 × ~2 h | **la question de fond** : *la graine 42 est-elle malchanceuse, ou la 77 chanceuse ?* Règle de décision en 8.2ter — **à lire avant de lancer** |
| **2** | déplacer les rampes de `reports/` vers `example/` | ~15 min, zéro CPU | une **configuration** ne doit pas dépendre d'une **sortie**. 🟢 Plus rien ne tourne : c'est sans risque maintenant |
| **3** | porter le résultat du jour dans `pages/CERTUS_STRAT.html` | ~30 min, zéro CPU | c'est la vitrine, et 👤 la juge *« ultra importante »*. ⚠️ Avec la condition **dans la même phrase que le chiffre**, et vérification de structure par `html.parser` |
| **4** | terminer l'action 1 d'hier — graine **202** sur la config livrée | ~2 h | une quatrième réalisation. Moins urgent : trois convergent déjà à 0,55 % |
| **5** | graines de génération **disjointes** de la notation | gratuit | ferme le canal de malédiction du vainqueur côté recherche |
| **6** | balayer `tp_hysteresis_factor` à bruit fixé | 1 run | sépare les deux lectures de l'anomalie de §1ter |
| **7** | compter le criblage et l'héritage | ~1 h | à faire quand un étage sera suspect, pas avant |

🔑 **L'ordre qui économise le plus de temps** : lancer **1** d'abord (des heures), puis faire **2**
et **3** pendant qu'elle tourne — ils ne demandent aucun CPU.

### 8.2ter 🔒 LA RÈGLE DE DÉCISION DE L'ACTION 1 — écrite AVANT la mesure

Elle est écrite d'avance pour ne pas être réinterprétée selon le résultat.

| résultat de `r75x2` nu | décision |
|---|---|
| **101 et 202 trouvent** des déposables | la graine 42 est **malchanceuse** → le **multiseed de génération** est la réponse produit : union sur K graines, faisabilité exigée sur **toutes**. K peut être petit |
| **une seule** trouve | la recherche réussit ~1 fois sur 2 → même conclusion, K plus grand |
| **aucune** ne trouve | la graine **77 est chanceuse**. La découverte autonome n'est pas atteignable par la recherche sur cet empilement → la réponse produit devient `scripts/generer_rampes.py`, et **ce n'est pas un échec** |

📌 Rappel du contexte : on n'a que **deux** graines mesurées nues sur `r75x2` à 2 nm — la 77
trouve 547 déposables, la 42 en trouve **zéro** sur 1617. Deux points ne permettent aucune
probabilité, et c'est précisément pourquoi cette mesure est la plus informative qui reste.

### 8.2bis 🔒 LE PÉRIMÈTRE EST FIXÉ À `r75x2` — et voici ce que cela interdit de dire

> 👤 *« non, on reste sur le 75cx2 »* (2026-08-21)

**La décision est légitime** : `r75x2` est l'étalon courant, et disperser l'effort sur un second
composant avant d'avoir consolidé celui-ci serait un mauvais arbitrage. Mais elle a une
conséquence qu'il faut écrire une fois pour ne pas la découvrir plus tard :

🔴 **Aucune affirmation de GÉNÉRALITÉ n'est permise.** Tant qu'un second composant n'a pas été
mesuré, tout ce qui est établi porte sur **un empilement, à une fente**. Les formulations
correctes :

| ✅ défendable | 🔴 interdit |
|---|---|
| « sur `r75x2` à 2 nm, la production trouve SEEL 0,57 » | « la production trouve SEEL 0,57 » |
| « la méthode des rampes a fonctionné sur `r75x2` » | « la méthode des rampes fonctionne » |
| « à trois graines, le résultat tient » | « le résultat est robuste » |

⚠️ Et le rappel de la règle du projet, qui n'est pas abrogée mais **suspendue par choix** :
*un correctif qui ne marche que sur `r75x2` à 2 nm n'est pas un correctif.* Le random75 reste le
seul composant sans cavité, sans miroir et sans périodicité — donc le seul qui puisse un jour
dire si une règle est générale. **La porte n'est pas fermée, elle n'est pas ouverte maintenant.**

📌 Corollaire pratique : `scripts/generer_rampes.py` est écrit pour n'importe quel composant de
`COMPOSANTS`, mais il n'a tourné que sur `r75x2`. Sa généralité est **une intention de
conception, pas une mesure**.

### 8.3 🔴 La circularité — ce qui a changé, et ce qui n'a pas changé

**Ce qui n'a pas changé** : la source des bons plans est un run à une **autre graine**. Pour un
produit, cela ne s'auto-amorce pas.

**Ce qui a changé** : la voie B n'est plus une question ouverte mais un **mécanisme écrit et
mesuré**. On sait *pourquoi* 685 nm n'entrait pas — le k-meilleurs prend les 100 groupements les
moins chers, et cette λ n'en fait jamais partie — et la couverture la fait entrer, avec la DP qui
re-optimise le reste du plan autour d'elle.

| voie | ce qu'elle vaut aujourd'hui |
|---|---|
| **A — bibliothèque de rampes** | 🟢 **livrée et mesurée.** Marche, mais spécifique au composant |
| **B — la couverture en λ** | 🟢 **mécanisme acquis**, 🔵 issue en cours de mesure. C'est la seule voie qui rende la production autonome **sur un composant neuf** |
| **C — beaucoup plus de graines** | 🟠 l'union ne sature pas à 5, mais rien ne borne le `K` nécessaire, et 5 lignées distinctes n'avaient produit aucune 685 nm |

⚠️ **Un arbitrage toujours assumé** : relâcher bruit et dérive **en génération** n'a pas été
essayé. Le levier est bien visé — il attaque les 84 % de rejets — mais tout ce qu'il trouverait
doit être **re-jugé au nominal**. `injected_strategies` lève l'obstacle qui l'empêchait : c'est à
rouvrir avec 👤 si la couverture échoue.
