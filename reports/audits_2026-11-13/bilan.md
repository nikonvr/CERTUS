# Audits du 2026-11-13 — co-conception, refactoring, vitesse

Demandés par 👤 le 2026-11-13. Mesuré sur `21f39b98` et suivants, Python 3.15.2, une machine. Chaque chiffre porte
sa commande ; ce qui n'est pas mesuré est dit « non mesuré ».

## 1. Co-conception design × stratégie de contrôle

**Question** : peut-on synthétiser un design en jugeant ce que le dépôt en fera sous sa stratégie de contrôle, et
non son seul spectre nominal ?

### 1.1 Ce qui existe déjà (lu dans le code)

| Brique | Où | État |
|---|---|---|
| Noter un dépôt contre les **cibles** de DESIGN, mêmes poids spectraux | `certus_strat_robustness_task.py` (`params["targets"]`) | présent ; actif seulement si le fichier STRAT porte des cibles |
| Évaluer « design + plan → RMSE par tirage, arrêts » | `certus_strat_local_search.py::native_evaluator` | présent ; les épaisseurs nominales sont un argument |
| Comparaison appariée (mêmes tirages pour deux candidats) | `paired_delta`, contrainte C2 | présent |
| Recherche locale sur le **plan** (longueur d'onde, mode) à design figé | `joint_local_search` | présent, actif par défaut |
| Tolérance du design à des erreurs **indépendantes** (sans contrôle) | `certus_design_tolerance.py` | présent dans DESIGN |
| Recherche sur le **design** jugée par le dépôt | — | absent |

Limites de structure : STRAT suppose deux matériaux H/L ; `full_dynamics_grid` ne sert qu'à un journal
(`[DYN-ALERT]`), pas au score : l'évaluateur reste cohérent quand le design change.

### 1.2 Mesure (`scripts/probe_codesign_sensitivity.py`, exemple `JSON-strat-example-fast.json`, 48 couches)

Détail : `codesign_sensitivity_example_fast.json` (et son rejeu horodaté, mêmes chiffres : la mesure est
déterministe).

| Grandeur | Valeur |
|---|---|
| Pipeline STRAT complet (trouver le plan) | 1 036 s, puis 788 s au rejeu |
| Une évaluation à plan figé, 300 tirages | 0,27 s (fabrique de l'évaluateur : 0,8 ms) |
| Contrôle : même design, même graine | écart 0 exactement |
| Erreur de dépôt nominale (RMSE contre le spectre du design) | 0,00264 ; 0 arrêt |
| Une couche à ±1 %, 96 retouches | rmse² de **−3,7 % à +24,6 %** ; 55 à \|z\| ≥ 3 |
| Sens des retouches significatives | 50 dégradent, 5 améliorent ; médiane +2,2 % |
| Par couche | 31 couches sur 48 : les deux signes dégradent (le design est à un optimum local du dépôt) ; 17 : signes opposés |
| Lien avec l'épaisseur de la couche | aucun (corrélation −0,01) : ce ne sont pas les couches fines qui pèsent |
| Meilleure retouche (couche 9, +1 %) | −3,7 %, pour un spectre nominal déplacé de 0,0016 RMS |
| Retouche globale σ = 0,5 %, 8 tirages | rmse² de +14 % à +110 % ; jusqu'à 113 arrêts sur 900 tirages |

### 1.3 Ce que la mesure dit

1. **Le signal existe et il est fort** : 1 % sur une couche déplace l'erreur de dépôt de plusieurs dizaines de pour
   cent, et 0,5 % partout fait apparaître des arrêts. La fabricabilité est une propriété du couple (design, plan).
2. **L'évaluateur est bon marché** : 0,27 s contre 1 036 s, soit environ 3 800 évaluations de design pour le prix
   d'une recherche de plan.
3. **Bouger le design seul, à plan figé, ne gagne presque rien** (−3,7 % au mieux) : le plan sort de la recherche
   locale accordé à son design, presque toute retouche le désaccorde. Et le gain coûte un déplacement du spectre
   nominal du même ordre que l'erreur de dépôt.
4. Donc une co-conception utile doit **bouger design et plan ensemble**, et **juger contre les cibles** (somme de
   l'écart nominal et de l'erreur de dépôt), pas contre le spectre nominal de chaque design.

🔴 Une graine, un composant, RMSE contre le spectre nominal de chaque design (le fichier n'a pas de cibles), plan non
ré-optimisé : aucune généralité.

### 1.4 Trois niveaux possibles, du moins cher au plus ambitieux

| Niveau | Principe | Coût | Risque | Avis |
|---|---|---|---|---|
| A. Tri de designs par le dépôt | DESIGN livre K designs (Pareto, relances) ; STRAT les note ; on garde le meilleur contre les cibles | K recherches de plan (17 min chacune en mode rapide ici) ; aucun algorithme nouveau | malédiction du vainqueur : noter sur une graine disjointe | **à faire d'abord** : dit si la dispersion entre designs équivalents justifie d'aller plus loin |
| B. Recherche locale jointe (épaisseur, longueur d'onde, mode) | étendre `joint_local_search` : un candidat « épaisseur ±δ » par couche, suivi d'un réaccord local du plan de cette couche et de ses voisines ; accepté si le RMSE **contre les cibles** baisse sans arrêt ajouté | ~0,3 s par candidat ; quelques milliers de candidats par passe | sur-ajustement à la graine de recherche (déjà traité par le contrôle durci) | **le cœur du sujet** ; demande des cibles dans le fichier STRAT |
| C. Critère de contrôlabilité dans DESIGN | pénalité analytique dans le mérite de PGLOBAL : marge aux points tournants, dynamique du signal en fin de couche (`turning_point_margins`, `compute_dT_dd_kernel`) | négligeable par évaluation | le critère de substitution peut ne pas suivre le SEEL : à corréler d'abord sur des designs déjà notés | à n'ouvrir qu'après A, qui fournit les données de corrélation |

Niveau D (deux boucles imbriquées, plan ré-optimisé à chaque design) : hors de portée au coût mesuré.

### 1.5 Préalables

- Faire porter les cibles de DESIGN au fichier STRAT (le champ existe, `targets`) : sans elles, on optimise l'erreur
  de production d'un design qui peut s'être éloigné du cahier des charges.
- Rapporter les deux grandeurs : RMSE contre les cibles (le critère) et SEEL (ce qu'on publie).
- Toute comparaison de designs sur une graine de notation disjointe de la graine de recherche.

## 2. Refactoring : ce qui mérite d'être factorisé ou mutualisé

**Mesure** : analyse statique des 369 fichiers suivis de `certus/` et des lanceurs (183 451 lignes) : corps de
fonctions identiques (AST), fonctions homonymes, similarité de fichiers frères (`difflib`), sites d'appel.

### 2.1 Constat d'ensemble

- **La duplication exacte est quasi nulle** : 12 groupes de corps identiques, 142 lignes redondantes sur 183 451.
  Le cliquet de duplication fait son travail.
- **Les couches sont propres** : 0 import montant, 1 cycle (les dix modules `certus_strat_*` de `core`).
- La dette qui reste est de **taille** : 16 fichiers longs, 32 fonctions longues, 12 fonctions complexes
  (`tests/architecture_debt.json`), dont `_test_strategy_robustness_task` (794 lignes) et
  `certus_index_spline_managers_ui.py::build` (804 lignes).

Ce qui mérite d'être mutualisé n'est donc pas du copier-coller, mais **des rôles réécrits dans chaque module**.

### 2.2 Candidats, par rendement décroissant

| # | Quoi | Mesure | Gain attendu | Risque |
|---|---|---|---|---|
| R1 | **METAL simple / bicouche** | Le socle commun construit les champs métal et spline et traite la progression. Chaque fenêtre fournit son sélecteur de substrat ou ses paramètres diélectriques, ainsi que ses indicateurs propres. | Clos le 14 novembre | 241 tests ciblés réussis. Bancs monocouche 58,7 s / RMSE 0,00610035 et bicouche 64,4 s / RMSE 0,00218517. |
| R2 | **Amorçage Numba** réécrit dans 5 fenêtres | `_warmup_numba_thread_runner` : 5 définitions, 252 lignes, similarité 0,56 à 0,63 | un service du socle ; même comportement au démarrage partout | faible |
| R3 | **Préparer un calcul DESIGN hors du worker** (indices, cibles, face arrière) | réécrit dans `_final_cleanup`, `_polish_remaining_layers_above_floor`, `_true_rmse`, `design_cost_function` ; `prepare_targets_vectorized` : 12 sites, `get_nk` : 44 sites dans 21 fichiers | un « contexte de coût » unique dans `core` ; supprime le risque qu'un des quatre juge un design avec d'autres hypothèses (c'est arrivé : ALG-18) | moyen : touche au calcul, oracle avant et après |
| R4 | **Graphes** : `certus_plot.py` et `certus_strat_plots_ui.py` | 191 lignes communes ; `_trigger_auto_range` et `has_data` identiques | une seule classe de graphe ; le correctif UX-14/15 (détachement) fait une fois | moyen |
| R5 | **Détacher un graphe** | `detach_current_plot` : 4 définitions, 287 lignes ; socle ~ METAL 0,51 | supprime les variantes ; lié à R4 | faible |
| R6 | **Polissage local** (L-BFGS-B borné + « jamais pire ») | `scipy.optimize.minimize` : 27 sites dans 11 fichiers | un polisseur partagé (celui de `certus_design_final_cleanup.py` en est un) | moyen : chaque site a ses tolérances |
| R7 | **SMOOTHER et SUBSTRATE hors du socle** | 121 lignes communes, `log` identique ; ni thème ni session (UX-59) | les deux fenêtres gagnent thème, session, raccourcis sans code propre | moyen : les migrer sur `CertusBaseApp` |
| R8 | **Export Excel / HTML** | `export_excel` : 3 fenêtres, 524 lignes, similarité ≤ 0,24 ; 73 sites `openpyxl` dans 15 fichiers | faible : les contenus diffèrent vraiment ; seul un petit utilitaire d'écriture (styles, en-têtes) se partage | — |
| R9 | `_update_qwot_from_ep` socle ~ RE | 0,64 ; seule la colonne change | Clos le 14 novembre, `5a456ec7` | 33 tests ciblés réussis, dont la conversion sur le classeur RE et le nettoyage DESIGN |

Faux amis, à **ne pas** factoriser : `_load_defaults`, `export_results`, `_apply_theme`, `_setup_shortcuts`,
`_export_results_html` portent le même nom dans plusieurs fenêtres mais une similarité ≤ 0,4 : le code est vraiment
propre à chaque module. `gradient_analytic.py` et `gradient_oblique.py` : 41 lignes communes sur ~1 700, ce sont
deux noyaux distincts.

### 2.3 Ordre conseillé

R1 et R2 d'abord (interface seule, protégés par les tests `ui`), puis R9 et R5. R3 ensuite, seul, avec l'oracle :
c'est le seul qui supprime une classe de défauts déjà rencontrée. R4, R6, R7 demandent chacun une décision de 👤.
Les fonctions de 500 à 800 lignes (§2.1) relèvent du plan de refactoring existant, pas de la mutualisation.

## 3. Vitesse et convergence locale

### 3.1 Noyaux (`scripts/probe_kernel_threads.py`, exemple DESIGN, 108 longueurs d'onde, 26 couches)

| Noyau | 1 fil | 8 fils | 16 fils |
|---|---|---|---|
| coût, arithmétique réelle | 41 µs | 13 µs | 14 µs |
| gradient, arithmétique réelle | 69 µs | 34 µs | 56 µs |
| gradient générique (complexe) | 211 µs | 96 µs | 101 µs |

Le parallélisme ne ralentit pas un appel, mais rend peu (×2 sur le gradient à 8 fils, 16 plus lent que 8). Piste :
plusieurs polissages simultanés à peu de fils chacun (`memetic_workers`, 1 par défaut) ; essai comparatif inachevé.

### 3.2 Polisseurs locaux (`scripts/probe_local_convergence.py`, problèmes RICL, départs = record perturbé)

Unité : une évaluation résidus + Jacobien. « Atteint » : l'optimum du départ (meilleur de toutes les méthodes) à
0,1 % près. Fichiers `local_convergence*.json`.

**Séparateur 50/50** (33 couches, 1 601 longueurs d'onde, 10 départs)

| Méthode | départ à 1 % | départ à 5 % |
|---|---|---|
| L-BFGS-B en nm (polisseur actuel du mémétique) | 0/10, s'arrête à RMSE 1,39e-5 | 0/10, 1,82e-5 |
| L-BFGS-B en épaisseur optique | 0/10, 1,35e-5 | 0/10, 1,84e-5 |
| Levenberg-Marquardt, amortissement de Marquardt (noyau ALG-07) | 10/10, 13 évaluations | 8/10, 182 |
| idem + accélération géodésique | 10/10, 31 | 8/10, 65 |
| Levenberg-Marquardt, amortissement de Nielsen (moteur RICL) | **10/10, 22** | **10/10, 48** |
| Nielsen + géodésique | 10/10, 52 | 10/10, 220 |

Optimum 1,147e-5 : L-BFGS-B le manque toujours, de 20 % à 60 %.

**Tri-bande** (101 couches) : le record RICL, RMSE 1,28e-4 sur sa grille à 1 nm (277 points), vaut **4,8e-3 sur la
grille à 0,1 nm** (2 707 points) : 37 fois plus, des pics étroits que la grille à 1 nm ne voit pas.

| Méthode, 5 départs | grille | RMSE résolu (0,1 nm), départ à 1 % | à 5 % | durée par départ |
|---|---|---|---|---|
| L-BFGS-B | 1 nm | 1,5e-3 | 6,3e-4 | 1,2 à 3,9 s |
| Levenberg-Marquardt (Nielsen) | 1 nm | 2,3e-3 | 1,1e-3 | 5,4 s |
| longueurs d'onde complexes (`refine_resonances`, 10 tours) | 1 nm + pics | **3,4e-4** | refusé 5/5 | 2,6 s |
| L-BFGS-B | 0,1 nm | **1,03e-4** | **1,04e-4** | 68 à 88 s |
| Levenberg-Marquardt (Nielsen) | 0,1 nm | 1,19e-4 (limite de 5 000 itérations) | 1,39e-4 | 47 s |

### 3.3 Ce que ces mesures disent

1. **Séparateur 50/50** : Levenberg-Marquardt à la Nielsen atteint l'optimum en 22 à 48 évaluations, que L-BFGS-B
   n'atteint jamais en 800 à 2 700. Le polisseur de DESIGN laisse du mérite sur la table.
2. **L'épaisseur optique** ne change rien de net à L-BFGS-B ; Levenberg-Marquardt y est invariant par construction.
3. **L'accélération géodésique** aide l'amortissement de Marquardt sur les départs éloignés (182 → 65), pas celui de
   Nielsen, qui fait mieux sans elle. À ne pas porter dans le noyau.
4. **Tri-bande** : Levenberg-Marquardt échoue aussi sur la grille résolue : ce ne sont pas les pics non résolus qui
   l'arrêtent, mais sa convergence lente à 101 couches (il bute sur la limite d'itérations). L-BFGS-B y est meilleur.
5. **Le vrai défaut du tri-bande est la grille** : tout polisseur à 1 nm laisse une erreur résolue de 6e-4 à 2e-3.
   La grille à 0,1 nm donne 1e-4, pour 20 fois le temps. Les longueurs d'onde complexes donnent 3,4e-4 au prix de la
   grille à 1 nm, mais refusent les départs à 5 % (« aucun maximum d'erreur isolé près du pôle suivi »).

🔴 Deux problèmes, des départs proches d'un record, 5 ou 10 départs : des tendances, pas des lois. Le 4,8e-3 du
record n'est pas encore recoupé par l'oracle indépendant.

### 3.4 Suites proposées

- **P1** : polisseur Levenberg-Marquardt de Nielsen branché dans le mémétique. La validation du nouveau défaut
  sur le séparateur 50/50 suit le [chantiers restants](../../docs/CHANTIERS_RESTANTS.md).
- **P2** : juger les designs du tri-bande (et de tout problème à bandes étroites) sur une grille résolue ; lancer le
  polissage final sur grille fine, ou en longueurs d'onde complexes une fois le refus des départs éloignés compris.

### 3.5 Mesures récupérées après la coupure

**DESIGN, séparateur 50/50, 2026-11-13.** Six passages sur le worktree à `e2ee96b7` avec la bascule appliquée,
trois par configuration en alternance. Tous à 34 couches, aucun dépassement du temps imparti, grille de 1 601
points. Écart maximal avec la transmission de l'oracle inférieur à 1,8 × 10⁻¹⁵.

| Configuration | RMSE de grille médiane | Durée médiane |
|---|---:|---:|
| L-BFGS-B explicite | 9,7961 × 10⁻⁵ | 351,6 s |
| Nouveau défaut | 8,4726 × 10⁻⁵ | 424,8 s |

Les graines étaient libres et la capture du banc ne contient pas le journal du polisseur. Les écarts observés
ne suffisent pas à isoler l'effet de LM. [Six lignes du banc](memetic_polisher_default_bench.json).

**RICL, 2026-11-13.** Les 8 mesures restantes ont été calculées après la coupure. Le juge de l'article
évalue le MF résolu sur une grille au pas de 0,0002 nm. [Les 21 résultats et leur admissibilité](ricl_lm_check.json).

| Départ | Meilleur repolissage admissible | MF résolu avant → après | MF nominal avant → après |
|---|---|---:|---:|
| Trois-raies, meilleur nominal CERTUS | L-BFGS-B sur grille à 0,1 nm, TOT libre | 0,030823 → 0,019756 % | 0,013422 → 0,017009 % |
| Trois-raies, CERTUS déjà traité | LM sur grille à 0,1 nm, TOT fixée | 0,016072 → 0,013366 % | 0,019777 → 0,022178 % |
| Trois-raies, reconstruction deep search 2020 | L-BFGS-B sur grille à 0,1 nm, TOT libre | 0,348336 → 0,221062 % | 0,012803 → 0,016402 % |

Le 50/50 bouge de moins de 5 × 10⁻¹⁰ nm par couche. Sur le trois-raies déjà traité, LM avec TOT libre atteint
0,013182 % résolu, mais dépasse le plafond (14 172,75 nm pour 14 171,1 nm). La version à TOT fixée (14 114,07 nm)
garde 100 couches, avec un minimum de 13,98 nm, et le polissage dure 43,7 s. Les mesures de cette reprise ont
utilisé un seul fil OpenBLAS.

### 3.6 Comparaison avec graines du mémétique appariées

50/50, 1 601 points, 34 couches dans les six sorties. Relances désactivées, population 30, 1 000 enfants.
Le worker a appelé LM sur les trois passages au nouveau défaut. Écart maximal de transmission avec l'oracle
inférieur à 1,9 × 10⁻¹⁵. [Résultats des six passages](memetic_polisher_seeded_bench.json).

| Graine | Coût mémétique L-BFGS-B → hybride | RMSE de grille L-BFGS-B → hybride | Durée L-BFGS-B → hybride |
|---:|---:|---:|---:|
| 42 | 1,3961 × 10⁻⁸ → 5,6833 × 10⁻⁹ | 1,0863 × 10⁻⁴ → 7,8409 × 10⁻⁵ | 397,1 → 468,2 s |
| 77 | 1,7380 × 10⁻⁸ → 7,9645 × 10⁻⁹ | 1,3251 × 10⁻⁴ → 8,3001 × 10⁻⁵ | 391,4 → 423,8 s |
| 202 | 8,7423 × 10⁻⁹ → 1,3728 × 10⁻⁸ | 8,8757 × 10⁻⁵ → 1,0748 × 10⁻⁴ | 358,7 → 442,6 s |

La RMSE médiane baisse de 24 %, la durée médiane augmente de 13 %. Les écarts par graine vont de −37 % à
+21 % en RMSE et de +8 % à +23 % en durée. Le polissage modifie la population et donc les descendants
du mémétique. L'hybride est conservé par défaut selon le choix de l'utilisateur, avec ce compromis sur le 50/50.

## 4. Dérivées : ce qui est encore numérique et pourrait être analytique

**Mesure** : analyse statique (AST) des appels d'optimiseurs de `certus/` : `minimize`, `least_squares`,
`minimize_scalar`, `brentq`, `differential_evolution`. 58 appels ; **32 reçoivent une dérivée analytique, 26 non**.
Sans dérivée, L-BFGS-B et `least_squares` la calculent par différences finies : N + 1 évaluations par gradient.

Déjà analytiques : DESIGN (gradient et Jacobien, incidence normale et oblique), RE (cinq Jacobiens), INDEX phases 2
et 3, SPLINE corridors et finalisation, METAL (polissage principal).

| # | Où | Aujourd'hui | Analytique possible ? | Gain attendu (non mesuré) |
|---|---|---|---|---|
| D1 | **FIELD**, synthèse et nettoyage : `certus_field_workers.py:753`, `:949` | L-BFGS-B sans gradient sur les épaisseurs | oui : dérivée du champ par matrices de transfert, même mécanique que le gradient de DESIGN | le plus gros : un gradient coûte N + 1 évaluations au lieu d'environ 2 à 3 |
| D2 | **INDEX infrarouge**, étapes 0 et 2 : `certus_index_workers_ir_strat.py:156`, `:224` | L-BFGS-B sans gradient, alors que `IRGlobalObjective.gradient` existe | D112 corrigé dans `3865ac09`, voir la vérification ci-dessous | à mesurer sur les ajustements |
| D3 | **METAL**, polissages de `pglobal_adapter.py:331`, `:375` | L-BFGS-B sans gradient | le gradient METAL existe (`jac=True` dans `certus_metal_bilayer_app.py`) : le passer à l'adaptateur | moyen, effort faible |
| D4 | **SPLINE**, étape des nœuds libres : `spline_workers.py:545` ; Smart Init : `spline_smart_init.py:959`, `certus_index_spline_smart_init.py:893` | L-BFGS-B sans gradient | oui pour les valeurs aux nœuds ; plus délicat pour la **position** des nœuds (dérivée de la base spline) | moyen à fort, effort moyen |
| D5 | SPLINE, repli de `certus_corridor_utils.py:1046` | sans gradient quand `spline_pwl_analytic_grad_supported` dit non | étendre les cas couverts | faible : c'est un repli |
| D6 | **SUBSTRATE** Sellmeier : `certus_substrate_sellmeier.py:242`, `:665`, `:843` ; `certus_substrate_index.py:1498` ; `certus_index_utils.py:576`, `:611` | différences finies | oui, trivial : n²(λ) est une somme de fractions rationnelles ; un site a déjà son Jacobien (`_jac_polish_q`) | faible : ces ajustements sont déjà rapides |
| D7 | INDEX optique, `certus_index_workers_opt_strat.py:84`, `:223` | Nelder-Mead, à côté de deux appels qui ont leur gradient | à instruire : sans doute un choix de robustesse | — |

**D112, 14 novembre.** Si le centre d'une bande coïncidait avec un point mesuré, le noyau pouvait reprendre
la dérivée du centre au point précédent. Le cas reproduit donne 0,0032077524 au lieu de 0,0031486516 par
différences finies. La dérivée symétrique de cette contribution est désormais nulle au centre. 59 tests de
gradients passent, ainsi que les 1 204 tests de l'oracle avant et après. Le corpus C1 conserve 9 092 tableaux
identiques au bit. Le branchement du gradient aux étapes 0 et 2 reste à mesurer.

Restent numériques par nature : les recherches à une variable (`minimize_scalar`, `brentq`, 6 sites) et les deux
`differential_evolution` (recherche globale).

Hors optimiseurs, déjà au registre : l'aiguille analytique (ALG-09 à 11, une seule passe pour toutes les positions
d'insertion au lieu d'une évaluation par position) et le gradient faux sur couches absorbantes (C20), à corriger avant
d'étendre quoi que ce soit.

Ordre conseillé : D2 et D3 (déjà écrits, à brancher et à mesurer), puis D1 (le seul qui demande un vrai noyau
nouveau, à valider contre l'oracle et par différences finies), puis D4.
