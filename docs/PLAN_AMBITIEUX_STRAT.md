# Plan ambitieux — STRAT

Écrit le 2026-08-06, après l'audit complet ([`BILAN_STRAT.md`](BILAN_STRAT.md)) et le recadrage
du physicien.

> 👤 *« Le juge de paix c'est toujours l'étude stochastique et statistique. La machine réelle
> compte le nombre de turning points, fait une correction POEM et s'arrête sur un niveau. Tout
> ce qui est swing in, swing out, c'est une vue de l'esprit humain. MAIS ici, le roi c'est la
> statistique ! Si 95 % des dépôts fonctionnent, c'est gagné. »*

---

## 0. La chaîne canonique — et les trois étapes qui ne font pas ce qu'elles disent

👤 Le physicien, 2026-08-06 :

> 1. On simule un dépôt et la mesure de transmission bruitée.
> 2. On utilise le POEM comme méthode d'arrêt.
> 3. On teste statistiquement tout un ensemble de stratégies prometteuses.
> 4. On en déduit la meilleure stratégie.

**Cette chaîne est la bonne, et elle est plus simple que ce que ce document proposait
initialement** — pas de front de Pareto, pas de recherche en faisceau avec *rollout*.
L'architecture n'est pas le problème. Le problème est que **trois de ces quatre étapes ne font
pas ce qu'elles annoncent.**

| Étape | État vérifié |
|---|---|
| **1. Simuler le dépôt et la mesure bruitée** | 🔴 **Le dépôt est simulé, la mesure ne l'est presque pas.** `noise_val_precalc` n'apparaît qu'une fois dans tout le noyau, sur la comparaison d'arrêt. La détection des points tournants, la lecture des ancres POEM et le test d'atteignabilité se font sur une courbe **parfaite**. La machine simulée voit un signal sans bruit et n'en subit le bruit qu'au moment de comparer. **C'est le seul écart vraiment grave, et il rend les trois autres étapes optimistes par construction.** |
| **2. POEM comme méthode d'arrêt** | ✅ **Aligné**, et 📖 conforme à l'éq. 2-4. Nuance factuelle : c'est POEM **quand c'est possible**, niveau absolu sinon — il faut deux points tournants traversés et une amplitude suffisante. C'est fidèle : la machine ne peut pas se recaler sur des extrema qu'elle n'a pas vus. |
| **3. Tester statistiquement un ensemble de stratégies prometteuses** | ⚠️ Le mot qui coince est **« prometteuses »**. Elles sont choisies par le coût de la DP, 📏 décorrélé du résultat (ρ = −0,04, zéro des dix meilleures par coût dans les dix vraies meilleures). L'ensemble testé n'est pas prometteur, il est **arbitraire** — et son top 5 est une seule stratégie déclinée à ±1 nm. Et « statistiquement » : le screening décide sur 25 tirages, résolution 4 % pour un seuil à 5 %. |
| **4. En déduire la meilleure stratégie** | ⚠️ **« Meilleure » n'a pas de définition dans le code.** Le classement porte sur l'écart au spectre **nominal**, non pondéré, et STRAT n'a jamais reçu la cible. |

### La conséquence sur la méthode de recherche

👤 *« Ce que je veux, c'est la meilleure stratégie. »* Combiné au reste — le juge est la
statistique, 95 % de dépôts qui fonctionnent c'est gagné, la cible spectrale prime — cela
définit **une grandeur unique** :

> **La meilleure stratégie est celle qui maximise `P(le filtre sorti est conforme à la cible)`.**

⚠️ **Cela annule le front de Pareto** que ce document proposait au §2.3. Il n'y a pas deux
critères à arbitrer : un dépôt qui plante ne produit pas de filtre conforme, un dépôt hors spec
non plus — **les deux sont le même échec**. On garde les deux causes séparées *à l'affichage*
(3 % de runs perdus n'a pas le même sens économique que 3 % hors spec) mais on optimise leur
somme.

**Et cela simplifie la recherche.** Puisque le tri est fait par la statistique, la DP n'a plus
à bien **classer** — elle doit bien **couvrir**. C'est un cahier des charges beaucoup plus
facile à satisfaire que celui auquel elle échoue aujourd'hui. 👤 *« La DP pour moi n'est pas
obligatoire »* : elle reste néanmoins un bon générateur, à condition de la juger sur sa
couverture et non sur son classement.

---

## 0bis. La thèse de ce plan

Aujourd'hui, **le simulateur ne sait pas échouer comme la machine échoue.**

Il ne bruite qu'un seul point de toute la chaîne — la comparaison d'arrêt. La détection des
points tournants, la lecture des ancres POEM, le test d'atteignabilité du niveau : tout se
fait sur une courbe TMM **parfaite**. Le modèle répond donc à la première des trois questions
du juge de paix — *voit-on les turning points ?* — par un « toujours, et exactement » qui n'a
aucun contenu.

Tant que c'est vrai, **aucune statistique produite par STRAT n'est un juge** : elle mesure la
robustesse d'un dépôt effectué par une machine parfaite qui lirait un signal parfait. C'est de
là que vient un plantage médian **nul** sur le dernier run — un résultat trop beau, et faux
pour la bonne raison.

> **Tout le reste du plan en découle. Un objectif plus fidèle, un coût mieux corrélé, une
> allocation de budget plus fine : rien de tout cela n'a de sens si la grandeur mesurée est
> optimiste par construction.**

Le plan a donc une **fondation** (axe 1), et le reste s'y appuie.

---

## Axe 1 — 🔴 FONDATION : rendre le simulateur capable d'échouer comme la machine

### 1.1 Bruiter le signal de monitoring, pas seulement la comparaison d'arrêt

`Ts_r` doit porter le bruit de mesure **avant** la détection des extrema et avant la lecture
des ancres. Conséquences attendues, et ce sont les bonnes :

- un extremum plat sera parfois **manqué** ou **dédoublé** → `n_tp_real ≠ n_tp_nom` → plantage
  compté, alors qu'il est aujourd'hui invisible ;
- les ancres POEM porteront leur incertitude → la compensation sera enfin évaluée **à son coût
  réel** (bruit effectif `σ√(1+(1−p)²+p²)`, soit ×1,22 à ×1,41) ;
- l'atteignabilité du niveau sera jugée sur le signal que la machine **voit**.

**Contrainte à respecter absolument : les nombres aléatoires communs.** Les tirages
supplémentaires doivent venir du même générateur Sobol caché, avec des indices distincts, pour
que toutes les stratégies restent comparées sur le **même** bruit. C'est un acquis, il ne doit
pas être perdu.

**Drapeau par défaut inactif**, mesure des deux côtés, et c'est elle qui tranche.

### 1.2 Modéliser la lecture, pas seulement la valeur

La machine ne dispose pas de 64 points parfaits : elle lit un **flux temporel** à une cadence
donnée, avec un temps d'intégration, et applique une **règle de détection** de point tournant.
Deux effets manquent :

- **la cadence** — un extremum peut tomber entre deux lectures ;
- **le filtrage** — augmenter le temps d'intégration réduit le bruit mais retarde la détection.
  📖 Zideluns p. 112 le dit explicitement : *« It is possible to reduce the minimum start
  amplitude by increasing the signal processing times »*. **C'est un arbitrage réel de la
  machine, et le modèle l'ignore.**

### 1.3 Extraire un objet `MachineModel` explicite

Aujourd'hui les caractéristiques de l'OMS 5100 sont dispersées en constantes dans le noyau :
`trigger_tolerance`, `SWING_MIN`, `extrema_exclusion_ratio`, `sim_thickness_probe_offset_ratio`,
`min_spectral_resolution`. Elles décrivent **une machine**, et devraient former un objet unique,
calibrable une fois et daté.

Contenu naturel : σ(λ) du bruit · cadence et temps d'intégration · résolution spectrale du
monochromateur · plage de λ accessible · règle de détection des points tournants · modes de
contrôle disponibles (niveau, point tournant).

Bénéfice : **la calibration devient un acte unique et traçable**, au lieu d'une chasse aux
constantes. Deux sessions ont été perdues sur un `trigger_tolerance` mal réglé dans un
fichier d'exemple.

### 1.4 🔴 Les autres sources d'erreur — la seule est aujourd'hui le bruit de lecture

📏 Vérifié : **aucune erreur d'indice n'est modélisée** dans STRAT. `grep` sur
`index_error|delta_n|index_tolerance` dans `certus_strat_robustness.py`,
`certus_strat_growth.py` et `certus_strat_batch.py` : **zéro occurrence**. La seule source
stochastique de tout le module est un tirage gaussien sur le niveau de déclenchement, **un par
couche et par run**.

Manquent donc :

| Source | Effet réel | Modélisée ? |
|---|---|---|
| Bruit de lecture ΔT | erreur d'arrêt | ✅ (mais seulement sur la comparaison, cf. §1.1) |
| **Erreur d'indice run-à-run** | décale tout le signal, change l'épaisseur optique | ❌ |
| **Dérive de calibration** | distorsion affine `T → a·T + b` | ❌ |
| **Instabilité de source / détecteur** | dérive lente pendant le dépôt | ❌ |
| Vitesse de dépôt, inertie de l'obturateur | dépassement à l'arrêt | ❌ |

**Et l'ironie est nette.** Le commentaire de `certus_strat_growth.py:194` justifie POEM ainsi :
*« si le signal réel subit une distorsion affine `T_réel = a·T_nom + b`, les deux ancrages la
subissent identiquement et le niveau reporté vaut `a·T_trigger_nom + b` »*. C'est
**exactement** l'argument qui rend POEM robuste aux erreurs d'indice et de calibration.

> **Le code affirme que POEM absorbe les erreurs d'indice, et ne l'éprouve jamais — parce
> qu'il n'en injecte aucune.** L'argument central du mécanisme est non testé.

Injecter une distorsion affine par run (un `a` et un `b` tirés) est **peu coûteux** et rendrait
cette affirmation vérifiable. C'est aussi le seul moyen de mesurer ce que POEM apporte
réellement par rapport à une cible absolue, au lieu de le postuler.

📖 Zideluns traite les erreurs d'indice explicitement au chapitre 2 : une erreur d'indice à
épaisseur physique constante détruit un Fabry-Perot comme le ferait une erreur d'épaisseur,
alors qu'à **épaisseur optique** constante elle est presque sans effet — *« this is of course
the result of the so-called quarter-wave design, and the self-error compensation mechanism »*.
C'est précisément ce qu'un monitoring optique contrôle, et donc ce qu'il faut savoir simuler.

### 1.5 σ dépend de la longueur d'onde

Le modèle utilise un σ constant. L'écart est connu et documenté : le bruit de l'OMS 5100 est
plus fort vers 400 et 1100 nm. Une fois `MachineModel` en place, σ(λ) est une table, pas une
refonte.

---

## Axe 2 — Faire de la statistique le seul juge

### 2.1 Les trois modes de défaillance comme sorties de premier rang

Aujourd'hui le plantage est un scalaire agrégé qui sert de couperet puis **disparaît** — il
n'est même pas affiché à l'opérateur. Il faut, **par stratégie et par couche** :

| Sortie | Question à laquelle elle répond |
|---|---|
| `p_tp_invisible` | Voit-on les turning points ? |
| `p_tp_miscount` | Compte-t-on le bon nombre ? |
| `p_level_unreachable` | Atteint-on le niveau ? |
| `yield = 1 − p_échec` | **Combien de dépôts sur cent réussissent ?** |

👤 *« Si 95 % des dépôts fonctionnent, c'est gagné. »* — **le rendement doit être la grandeur
de tête**, affichée avant le RMSE. Aujourd'hui `crash_rate` n'apparaît même pas dans la table
opérateur (`certus_strat_table_ui.py:217-300`), qui montre résolution, `n_blocks`, changements,
λ uniques, score et symétrie.

⚠️ **Dépendance** : `p_tp_invisible` et une part de `p_tp_miscount` **ne sont mesurables
qu'après l'axe 1.1**. Avant, elles valent zéro par construction.

### 2.2 Le rendement composé remplace le couperet binaire → **traité au §4.1**

Le rendement d'un empilement est `Π(1 − pᵢ)`, de logarithme **additif**, donc DP-compatible.
Cela remplace le lexicographique actuel — « j'élimine sur le plantage, puis je classe sur le
coût » — qui détruit une stratégie à 5,1 % et garde celle à 4,9 %.

**Le détail, la donnée déjà disponible et le correctif exact sont au §4.1**, où cette idée
prend tout son sens : elle n'est pas seulement un meilleur agrégateur, c'est **l'objectif que
la DP devrait avoir**.

### 2.3 ❌ ANNULÉ — le front de Pareto est inutile

Ce document proposait de rendre une frontière rendement × écart spectral plutôt qu'un gagnant.
**C'était une complication inutile, née de ma propre confusion sur l'objectif.**

👤 La définition du physicien — *« ce que je veux, c'est la meilleure stratégie »*, jugée sur
*« si 95 % des dépôts fonctionnent, c'est gagné »* et *« le plus important est la cible
spectrale respectée »* — **collapse les deux critères en un seul** : un dépôt qui plante ne
produit pas de filtre conforme, un dépôt hors spec non plus. Les deux sont le même échec.

**Une seule grandeur : `P(conforme)`.** On affiche les deux causes séparément parce qu'elles
n'ont pas le même sens économique — un run perdu coûte du temps machine, un filtre hors spec
coûte de la matière et se découvre tard — mais **on optimise leur somme**, et on rend **une**
stratégie.

### 2.4 Les heuristiques deviennent des diagnostics, plus des filtres

15–85 %, amplitude de départ ≥ 4 %, swing in/out : **à conserver comme colonnes explicatives**
— elles aident à comprendre *pourquoi* une stratégie échoue — mais **elles ne doivent plus
éliminer**. La statistique le fait mieux, et sans arbitraire.

---

## Axe 3 — Réconcilier l'objectif avec la cible spectrale

👤 *« Le plus important est la cible spectrale respectée. »*

STRAT classe sur l'écart au spectre **nominal** et **n'a jamais reçu la cible** — zéro
occurrence de `targets` dans le module. Il faut :

1. acheminer les zones `{lmin, lmax, tmin, tmax, w}` depuis DESIGN ;
2. remplacer le RMSE non pondéré par la **fonction de mérite contre la cible**, celle que
   l'optimiseur de DESIGN minimise déjà — les deux modules deviennent alors cohérents ;
3. **garder le nominal comme point visé** pendant le dépôt : c'est le mécanisme même de
   l'auto-compensation ;
4. repli documenté sur le nominal si aucune cible n'est fournie.

Sur le dichroïque, la bande bloquée pèse 146 points sur 301 avec une exigence 500× plus dure —
et compte aujourd'hui autant que la bande passante.

---

## Axe 4 — 🔴 « Prometteuses » : le nœud du problème

👤 *« Comment alors trouver des stratégies prometteuses ? C'est le nœud du problème. »*

**L'espace est inatteignable par énumération** : 48 couches donnent 2⁴⁷ ≈ 1,4·10¹⁴ découpages
en blocs contigus, multipliés par les affectations de λ. Il faut donc un générateur, et il doit
valoir mieux que le hasard.

### 4.0 L'observation qui débloque : `P(conforme)` se factorise en deux morceaux de nature opposée

```
P(conforme)  =  P(le dépôt se termine)  ×  P(spectre dans la spec | terminé)
                └─────── SÉPARABLE ──────┘   └──── NON SÉPARABLE ─────┘
```

- **Le rendement est séparable.** Un dépôt se termine si *chaque* couche se termine :
  `Π(1 − pᵢ)`, dont le logarithme est **additif** — exactement ce qu'une DP de Bellman sait
  optimiser exactement.
- **La précision ne l'est pas.** Les erreurs se composent et se compensent ; seule la
  simulation Monte-Carlo peut en juger.

> **La DP doit optimiser la partie séparable — le rendement — et laisser au Monte-Carlo la
> partie qui ne l'est pas.** Aujourd'hui elle fait exactement l'inverse : elle optimise un
> proxy de *précision* (ρ = −0,04) et traite le *rendement* comme un couperet binaire.

### 4.1 🔴 La donnée existe déjà, et elle est jetée au dernier moment

La Phase A calcule `results_fast[idx, 2]` — **le taux de plantage, par couche et par longueur
d'onde** — et le range dans l'entrée (`certus_strat_service.py:1081`). Puis :

```python
if crash_rate >= crash_tol or gain < 0.0:
    eliminated.append(entry); continue      # ← SEUL usage : un seuil binaire
```

Il **n'entre jamais dans le coût**. Une λ à 0,001 % de plantage et une à 0,106 % sont traitées
à l'identique, alors qu'elles diffèrent d'un facteur cent sur la seule grandeur qui **compose**
sur la hauteur de l'empilement.

📏 Vérifié : `raw_results_thickness[i_layer]` conserve les entrées complètes
(`certus_strat_objectives.py:313`), mais la carte donnée à la DP ne garde que `x["cost"]`
(`certus_strat_workers_pipeline.py:103`). **La donnée survit jusqu'à la dernière ligne, où on
la jette.**

**Correctif** : construire une carte parallèle `crash_map[couche][λ]` depuis la même source, et
donner à la DP l'objectif

```
minimiser  Σ_couches  −log(1 − p(couche, λ))
```

C'est **le log du rendement, exactement**. Là où le coût actuel affiche ρ = −0,04, celui-ci
n'est pas un proxy : **c'est une composante directe de `P(conforme)`**. Coût d'implémentation :
une carte de plus, aucune simulation supplémentaire.

⚠️ **Réserve à instruire, pas à supposer** : l'indépendance entre couches est approximative —
celles d'un même bloc partagent l'historique de points tournants. À mesurer. Mais même
imparfaite, elle sera incomparablement mieux corrélée qu'un proxy décorrélé.

### 4.2 De la diversité explicite, sinon les *k* meilleurs sont un seul

Les *k* meilleurs chemins d'une DP sont des quasi-doublons **par construction**. Il faut
sélectionner sur la **signature de découpage**, pas seulement sur le score. La séparation
spectrale posée le 2026-08-05 fait cela au niveau des λ ; **il manque l'équivalent au niveau
des blocs.**

### 4.3 Des amorces structurées, que la DP ne produira jamais

Tout l'empilement à une seule λ · un bloc par couche · les découpages « humains » qu'un
opérateur essaierait. Elles ancrent l'ensemble, servent de témoins, et coûtent une poignée
d'évaluations.

### 4.4 🔴 Le vrai levier, et il manque totalement : la recherche locale sur le vrai objectif

👤 *« J'ai tout mon temps. »* Puisque le Monte-Carlo est le juge et que le budget n'est pas
contraint, **le meilleur générateur n'est pas un générateur : c'est une recherche locale.**

Partir des survivantes du screening et perturber — déplacer une frontière de bloc, changer la
λ d'un bloc, fusionner, scinder — en **réévaluant chaque perturbation au Monte-Carlo sur
`P(conforme)`**. Pas de proxy, pas d'hypothèse de séparabilité, pas de problème de corrélation.

C'est ce qui manque aujourd'hui. `ELITE` s'en approche mais échoue deux fois : il perturbe à
**±1 nm**, soit **sous le pas de grille** donc sans signification physique, et il juge sur le
mauvais critère. Il produit les `551, 552, 553, 554` observés en tête de classement.

> **La DP trouve un bon point de départ. La recherche locale trouve le meilleur.** Et elle ne
> demande aucune théorie — juste du budget.

### 4.4a et 4.4c — Deux réparations qui conditionnent la génération

Elles ne sont pas des raffinements : elles gaspillent ou corrompent le budget de génération.

- 🔴 **Le terme SYM est mort** — désaccord de nom entre producteur (`dist_*`,
  `certus_strat_objectives.py:565-568`) et consommateur (`ext_*`,
  `certus_strat_context.py:285-291`, et `_EXT_KEYS` en `certus_strat_service.py:1030`). Rien
  n'écrit jamais ces clés : le score vaut `999.0` partout. La passe de minage SYM ne diffère
  donc de THICKNESS que d'une constante et produit des **doublons** — environ **un tiers du
  budget de minage et de screening recalcule THICKNESS**.
  ⚠️ Réparer le nom **activera ce terme pour la première fois** ; `sym_weight = 0,35` n'a
  jamais été calibré sur un terme vivant. À poser derrière une mesure.
- 🔴 **Déduplication en λ à l'étage ELITE.** Le top 5 mesuré est `551, 552, 553, 554` — des
  perturbations **sous le pas de grille de 2 nm**, donc sans signification physique. Quatre
  cinquièmes du budget Monte-Carlo final sont dépensés sur la même stratégie. La séparation
  spectrale posée dans le kernel DP ne couvre pas cet étage.

### 4.5 En résumé : « prometteuses » recouvrait trois choses distinctes

| Composante | Comment l'obtenir |
|---|---|
| **Le rendement** | se **prédit** — DP sur `Σ −log(1−p)`, donnée déjà mesurée |
| **La diversité** | se **construit** — signatures de découpage, séparation spectrale, amorces |
| **La précision** | ne se prédit pas — elle se **mesure**, puis on **grimpe** dessus |

On les confondait en un seul « coût », et c'est pour cela qu'aucune ne fonctionnait.

---

## Axe 4bis — ❌ ABANDONNÉ : réparer l'estimation d'une grandeur dont on ne veut pas

👤 *« D'une manière générale, on se branle en partie B de l'erreur d'épaisseur. Seul l'écart
spectral final compte. »*

Cet axe proposait de rendre `cost_map` tridimensionnelle `[couche][λ][début de bloc]` pour
réparer l'estimation du coût en nanomètres — 📏 la formule est bonne (+0,59 mesurée) mais son
estimation par la Phase A est anti-corrélée (−0,41) parce qu'elle suppose un découpage glouton
que la DP n'évalue pas.

**Le correctif est juste, et il devient sans objet.** Mieux estimer une erreur d'épaisseur ne
sert à rien si l'erreur d'épaisseur n'est pas la grandeur qui décide. On ne répare pas
l'estimateur d'une quantité qu'on va cesser d'utiliser.

### La bonne lecture : chaque étage doit parler dans la bonne monnaie

| Étage | Monnaie aujourd'hui | Monnaie juste |
|---|---|---|
| Phase A — élimination | plantage (sans dimension) ✅ | inchangé |
| Phase A — coût de candidate | **nanomètres d'épaisseur** | 🔴 plus de consommateur (voir ci-dessous) |
| Objectif de la DP | **somme de nanomètres** | 🔴 **`Σ −log(1 − p)` — le log du rendement** (§4.1) |
| Score de robustesse | RMSE **spectral** ✅, mais contre le **nominal** | RMSE spectral contre la **cible pondérée** (axe 3) |
| Score rendu | `robustness_score` | **`P(conforme)`** (§2.3) |

Le score final était donc **déjà spectral** — `compute_batch_rmse` opère bien sur le spectre.
Le nanomètre ne survit qu'en Phase A et dans l'objectif de la DP, et ces deux-là tombent
ensemble.

### La conséquence, qu'il faut assumer

Si la DP n'optimise plus que le rendement, **le coût en nanomètres de la Phase A n'a plus de
consommateur**. Elle ne sert alors qu'à deux choses, et c'est suffisant : **éliminer** (plantage
au-dessus du seuil, gain non mesurable) et **fournir les taux de plantage par (couche, λ)** qui
alimentent le nouvel objectif.

⚠️ **Risque à surveiller** : une DP qui n'optimise que le rendement peut proposer des stratégies
sûres mais spectralement médiocres. Le Monte-Carlo les écartera — **mais seulement parmi celles
qui ont été générées.** D'où l'importance de la diversité (§4.2) et des amorces (§4.3) : la
génération doit couvrir, le tri spectral fera le reste.

⚠️ **Ne pas chercher un coût `sᵀΣs`** : réfuté par la mesure — ni les sensibilités spectrales
(+0,589 contre +0,590) ni la covariance (+0,643) n'apportent quoi que ce soit. Et de toute
façon, c'était encore une tentative de prédire ce qui doit être **mesuré**.

---

## Axe 5 — Allocation statistique du budget

👤 *« Augmenter N n'est pas un problème. »* Alors autant le dépenser où il décide.

1. **Successive halving.** 240 × 25 tirages à plat décident presque rien. Le même budget en
   escalier finit à ~15 stratégies évaluées à ~200 tirages.
2. **Règle dure : jamais d'élimination irréversible à une résolution plus grossière que le
   seuil mesuré.** Le taux de plantage est binomial : son écart-type à p = 5 % vaut 8,9 % à
   N = 6 et 1,8 % à N = 150. Pour un seuil à 5 %, il faut **N ≥ 100**.
3. **Borne de confiance plutôt que seuil ponctuel** : n'éliminer que si les données établissent
   que le taux dépasse la tolérance. Conservateur dans le bon sens — en cas de preuve
   insuffisante, la stratégie survit au screening et sera jugée à la passe complète.
4. ✅ **CVaR95 au lieu du P95** — fait. Un P95 est décidé par 1 point à N = 6, ~7 à N = 150 ;
   la CVaR moyenne la queue.

---

## Axe 6 — La validation externe, qui manque totalement

C'est ce qui séparerait un code plausible d'un code éprouvé.

### 6.0 🔴 LE JUGE DE PAIX EST LE DICHROÏQUE 48 COUCHES

👤 *« Le juge de paix sera mon dichroïque 48 couches. »* (2026-08-06)

C'est `example/example_strat/JSON-strat-example.json` — le composant sur lequel toute la
session a mesuré. Conséquences immédiates :

- **Tous les chiffres de ce document portent déjà sur le juge.** 191 stratégies, 0 repêchée,
  plantage médian nul, meilleur découpage à 5 blocs : c'est lui.
- **Les réglages de ce fichier ne sont plus « un exemple », ce sont les conditions du test.**
  D'où la gravité des trois dérives corrigées — `trigger_tolerance` 0,5 → 0,05,
  `execution_mode` fast → premium, `scan_wl_step` 5 → 2 nm. Un juge mal réglé condamne
  ou acquitte au hasard.
- **Le test anti-dérive de l'exemple (§6.5) devient critique**, pas secondaire.

⚠️ **Question ouverte, et elle détermine ce que ce juge peut trancher.**

| Si… | Alors le juge est… | Et il valide… |
|---|---|---|
| Le dichroïque a été **déposé** et on a des **spectres mesurés** pour des stratégies connues | une **validation externe** | que le modèle colle au réel — le vrai test d'acceptation |
| C'est le composant de **référence interne**, sans dépôt réel associé | un **banc de cohérence** | que le code est stable et reproductible, **pas** qu'il dit vrai |

Dans le second cas, la validation externe reste à faire, et la séparatrice de Zideluns
ci-dessous demeure le seul candidat publié et vérifiable.

**Ce qu'il faudrait pour transformer le dichroïque en juge externe** : au moins **deux**
stratégies réellement déposées sur ce composant, avec leurs spectres mesurés. Deux suffisent —
le test décisif est **ordinal** : STRAT doit les classer dans le bon ordre. C'est bien moins
exigeant qu'une correspondance absolue, et bien plus probant qu'un accord avec lui-même.

---

### 6.1 Le témoin publié : la séparatrice 8 couches de Zideluns, chapitre 4

   ⚠️ Deux fausses pistes écartées d'abord. Les « **0,4 nm en PM / 0,3 nm en P-PM** » que ce
   document citait ne sont **pas vérifiés** — ils viennent de `REPRISE_STRAT_MONITORING.md` §4,
   attribués à la thèse Arsac que je n'ai pas lue, et 📏 la recherche dans la thèse Zideluns
   donne **zéro occurrence**. Et le repère « ~0,5 % sur 20 couches » de la p. 158 concerne le
   **large bande** : 👤 *« oublie le broadband monitoring, on n'en fait pas »*. Écarté.

   ✅ **Le bon repère est monochromatique, publié, et directement pertinent.** 📖 Zideluns
   §4.2, p. 119-120 : une **séparatrice 50/50 à 8 couches**, déposée **quatre fois** avec quatre
   stratégies **monochromatiques** différentes — MF2, MF3, MF4 (automatiques, une λ par couche,
   soit exactement ce que produit STRAT) et une stratégie manuelle à λ unique de 595 nm, choisie
   *« as it showed the lowest noise sensitivity in the simulation »*.

   Deux résultats exploitables, et le second vaut bien plus que le premier :

   | Résultat | Valeur | Ce qu'il teste |
   |---|---|---|
   | Déviation de transmission mesurée | **±0,7 %** (corridor visé ±1 %, erreurs d'épaisseur < 0,5 % requises) | l'**échelle absolue** du modèle |
   | 📖 *« the measured curve obtained by strategy using **MF4** wavelengths more closely follows the theory across the spectral range of interest »* | **MF4 > MF2, MF3, standard** | le **classement** — ce que STRAT prétend faire |

   > 🔴 **Le test ordinal est le vrai test d'acceptation.** Il ne demande pas que la calibration
   > du bruit soit parfaite en valeur absolue — seulement que **l'ordre soit juste**. Si STRAT,
   > alimenté avec la même conception et les quatre mêmes jeux de longueurs d'onde, ne place pas
   > MF4 en tête, il ne sait pas faire ce pour quoi il existe. Et s'il l'y place, c'est une
   > validation **contre une expérience réelle**, pas contre lui-même.

   **Le test est entièrement reproductible** : la conception est en annexe 1 de la thèse, et
   📖 *« les informations détaillées sur les stratégies de contrôle de ces conceptions
   (méthodes, longueurs d'onde, etc.) sont données dans l'annexe 4 »* — donc les λ de MF2, MF3,
   MF4 et de la stratégie standard sont disponibles.

   **Extension naturelle** : le filtre de compensation D65 à **37 couches** (§4.3.1), pour
   lequel 📖 *« it was not possible to find a single wavelength that would monitor all 37
   layers »* — un cas où la stratégie polychromatique est **obligatoire**, et donc un second
   témoin.

   📌 À noter au passage, et cela recoupe le §1.6 du `BILAN` : sur le D65,
   📖 *« the first layer was rate monitored, because it is a SiO2 layer and the refractive index
   contrast with the substrate »* est insuffisant. **La première couche est un cas particulier
   en salle aussi** — ce n'est pas seulement un artefact de la nucléation dans le code.
2. **Test de calibration sur l'exemple réel** : « au moins N stratégies non repêchées à
   `crash_rate < 5 %` ». Un run. Il aurait transformé deux sessions d'analyse en trente
   secondes de diagnostic.
3. **Contrôle de sanité spectral automatisé** : vérifier que l'empilement de l'exemple *est*
   un dichroïque. Attrape d'un coup une mauvaise base d'indices ou une convention de signe.
4. **Oracle du noyau de croissance** : comparer la racine du fit parabolique à la racine exacte
   de `T(d)` sur une grille, seuil 0,05 nm. C'est ce que `verif-tmm` fait pour le TMM ; le
   monitoring n'a pas son équivalent.
5. **Test anti-dérive du fichier d'exemple** : interdire à l'exemple de s'écarter d'un défaut
   du code sans justification écrite. **Trois fois** cette session il était le plus mauvais
   réglage du dépôt.

---

## Axe 7 — Contribution scientifique possible

- **Verres témoins multiples.** Zideluns y consacre son chapitre 6 : *« quand changer le verre
  témoin »* est un problème ouvert. **La DP sur les blocs est structurellement l'outil qui
  décide où couper.** C'est publiable et c'est à portée.
- **TPM + coupure de niveau dans la même séquence.** 📖 Zideluns p. 113 : *« the combination
  […] should be considered because both monitoring methods are readily available with the
  OMS5100 »*. 👤 Parqué par le physicien — sa machine ne saurait pas basculer. Point à
  retrancher entre eux.

---

## Ordre recommandé

Il découle directement des quatre étapes du §0 : **réparer chaque étape dans l'ordre où elle
conditionne les suivantes.**

```
ETAPE 1 — « simuler la mesure bruitee »
  1.1  bruiter Ts_r avant la detection, CRN preserves    <- FONDATION, tout en depend
  1.4  injecter une distorsion affine (indice, calibration)  <- eprouve enfin l'argument de POEM

ETAPE 4 — « la meilleure » a besoin d'une definition
  3    acheminer targets depuis DESIGN + ponderer par zone
  2.1  P(conforme) comme score unique, les trois modes de defaillance en sorties

GARDE-FOU, des que 1.1 et 3 sont poses
  6.2  test de calibration sur l'exemple reel

ETAPE 3 — « prometteuses » : rendement predit, diversite construite, precision mesuree
  4.4a deduplication en lambda a l'etage ELITE   <- 4/5 du budget MC final gaspille
  4.1  DP sur Sigma -log(1-p)  <- LE RENDEMENT, donnee deja mesuree et jetee
  4.2  diversite par signature de decoupage
  4.4  RECHERCHE LOCALE sur P(conforme)  <- le vrai levier, absent aujourd'hui
  4.3  amorces structurees (mono-lambda, un bloc par couche, decoupages humains)
  5    successive halving + jamais d'elimination sous-resolue
  4.4c reparer les cles SYM (+ recalibrer sym_weight derriere une mesure)

CONSOLIDATION
  1.3  extraire MachineModel                             <- calibration tracable et datee
  6.1  separatrice 8 couches de Zideluns : STRAT doit classer MF4 en tete  <- LE test
  1.2  cadence et temps d'integration
  1.5  sigma(lambda)

RECHERCHE
  7    verres temoins multiples
```

⚠️ **Ce qui a disparu de cet ordre** : le front de Pareto (§2.3, annulé — `P(conforme)` est un
scalaire) et la recherche en faisceau avec *rollout*. Cette dernière n'est pas nécessaire :
👤 la chaîne du physicien dit *« on teste statistiquement tout un ensemble de stratégies »* —
générer largement puis départager par la statistique suffit, à condition que la génération
vise la **couverture**. Une recherche plus sophistiquée ne se justifierait que si la couverture
mesurée s'avérait insuffisante.

**La règle qui gouverne l'ordre** : rien ne se décide sans mesure, et aucune mesure ne vaut
tant que l'axe 1.1 n'est pas posé — parce que jusque-là, le simulateur ne peut pas échouer.

---

## Ce que ce plan donnera, et ce qu'il ne donnera pas

Question du physicien : *« ce plan va donc réellement me permettre de trouver une stratégie à
partir d'une statistique réelle ? »* — la réponse honnête tient en trois conditions.

**✅ Une statistique qui peut échouer.** Dès l'axe 1.1, les trois questions du juge de paix
deviennent des mesures au lieu d'hypothèses, et le rendement devient un chiffre qui a un sens.
C'est un saut par rapport à aujourd'hui, où un plantage médian nul est un artefact du modèle.

**⚠️ Mais « réelle » exige les autres sources d'erreur** (axe 1.4). Sans elles, tu obtiens
un rendement fidèle **au bruit de lecture seul**. Or c'est précisément là que POEM est censé
briller — sur les erreurs d'indice et de calibration — et l'affirmation reste non testée.

**⚠️ Et « réelle » exige la validation externe** (axe 6.1). Sans reproduire les 0,4 nm en PM
et 0,3 nm en P-PM, on obtient un modèle **cohérent avec lui-même**, pas un modèle dont on sait
qu'il colle au réel. C'est la différence entre *« ma simulation dit 95 % »* et *« je sais que
95 % veut dire 95 % »*.

**🔴 Une réserve de fond, indépendante de tout cela.** Même avec une statistique parfaite, on
ne classe que **ce que la DP a généré**. Aujourd'hui ρ = −0,04 et le top 5 est une seule
stratégie déclinée à ±1 nm. Une statistique irréprochable appliquée à un échantillon biaisé
rend le meilleur *des candidats proposés*, pas le meilleur possible. C'est l'axe 4, et sa reponse est desormais assumee : la DP devient un GENERATEUR de diversite, le tri revient au Monte-Carlo.

---

## Ce qu'il ne faut pas faire

- Chercher un coût prédictif par `sᵀΣs` — **réfuté par la mesure**.
- Toucher au cap de 10 λ par bloc — traité par la séparation spectrale.
- **Tenter de rendre les « points tournants virtuels » utilisables comme ancres POEM.**
  `BILAN_STRAT.md` §3.1 l'a d'abord présenté comme un manque ; **c'est faux, et corrigé**. Un
  point tournant virtuel est une extrapolation théorique — **la machine ne l'a pas mesuré**,
  elle ne peut donc pas s'y recaler. Le code a raison d'exiger deux extrema réellement
  traversés. Le balayage à 3× n'est pas gaspillé pour autant : il sert à la **détection de
  plantage**, qui doit savoir où tombe le prochain extremum.
- **Citer les repères « 0,4 nm / 0,3 nm » comme s'ils étaient vérifiés** — ils sont absents de
  la thèse Zideluns et proviennent d'une reprise citant Arsac, non relue (§6.1).
- Implémenter les heuristiques de la littérature comme des **filtres** — elles sont des
  diagnostics ; la statistique juge.
- Activer SYM sans recalibrer `sym_weight` — le terme n'a jamais tourné.
- Conclure d'un écart d'épaisseur sous **0,05 nm**, ou d'un écart de λ sous le **pas de
  grille**.
- Réintroduire un mode dégradé. 👤 *« Interdit le mode fast. »*
