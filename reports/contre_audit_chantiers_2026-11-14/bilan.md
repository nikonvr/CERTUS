# Contre-audit des 33 chantiers — 2026-11-14

Demandé par 👤 le 2026-11-14. Objet : [la liste des 33 chantiers](../../docs/CHANTIERS_RESTANTS.md), ses sources
[A](../audits_2026-11-13/bilan.md), [Q](../questions_design_2026-11-13/bilan.md),
[U12](../refactor_corridors_2026-11-11/U12_specification.md) et [U13](../refactor_corridors_2026-11-11/U13_protocole.md).

**Verdict : sur 13 P1, quatre le restent (04, 10, 15, 33) ; cinq chantiers sont à supprimer ou geler (03, 06, 13, 17,
26) ; la mesure RICL du 14 novembre n'est pas valide en l'état.**

Méthode : lecture seule de l'arbre de travail (tête `de52e01c`), des sources et des fonctions citées. **Aucun test ni
aucune mesure n'a été lancé**, ni `preflight.py` ni `orient.py` : l'accès était un shell Linux sans SciPy ni Numba, pas
le Python de référence. Les chiffres sont relus dans les JSON et rapports du dépôt. « Vérifié » = lu dans le code.

## A. Corrections majeures

1. **RICL (04) : la comparaison de Q §10 n'est pas recevable.**
   - Le juge à 0,01 nm n'est pas convergé pour deux solutions sur trois (`probe_auto_grid_crosscheck.json`) :

     | Solution | 0,01 nm | 0,001 nm |
     |---|---:|---:|
     | Record | 3,149e-3 | 3,511e-3 |
     | Polissage à 0,1 nm | 5,326e-3 | 2,180e-3 |
     | Grille automatique | 9,581e-5 | 9,579e-5 |

     Le polissage à 0,1 nm dégrade ou améliore le record selon le pas du juge.
   - L'admissibilité n'est pas consignée : `scripts/probe_auto_grid.py` polit avec un plancher de 0,05 nm
     (`LOWER_NM`) et sans contrainte de TOT, et le JSON ne donne ni TOT, ni couche la plus fine. Les règles du moteur
     RICL (`Rules` de `reports/RICL_ultimate_2026-11-05/engine.py`) imposent 5 nm, 101 couches et un plafond de TOT ;
     `admissible()` existe et n'est pas appelée.
   - Le record part à 14 171,000 nm, soit au plafond. Si MF % = 100 × RMSE (facteur d'échelle du moteur), 9,58e-5
     ferait 0,0096 %, mieux que le meilleur admissible de A §3.5 (0,0134 %) : cas « résultat meilleur que prévu » de
     CLAUDE.md §11.
   - Q §10 juge en RMSE à 0,01 nm, A §3.5 en MF % à 0,0002 nm : les deux rapports ne sont pas raccordés.
   - L'oracle recoupe le TMM au pas de 0,01 nm seulement ; il ne dit rien de la convergence de la quadrature.

2. **Chantier 20 : « les grilles résolues sont déjà disponibles » est contredit** par le point 1. La colonne « RMSE
   résolu (0,1 nm) » de A §3.2 (1,03e-4) se juge sur sa propre grille et n'est pas réconciliée avec les 5,3e-3 et
   2,2e-3 de Q §10.

3. **Sélection robuste : le gain est mesuré dans le modèle qui l'a produit, et confondu avec N.**
   - `bench_50_50.json` : deux designs robustes sur trois ont 30 couches contre 34 pour leurs témoins. À N égal
     (graine 202), le RMS sous erreurs passe de 0,02344 à 0,01903.
   - La RMSE nominale monte d'un facteur 5 à 21 (1,59e-3 sur la graine 42).
   - Le holdout tire des erreurs indépendantes de 1 nm, le modèle même du critère. Q §4.5 dit que ce modèle décrit mal
     un dépôt contrôlé. Seul STRAT peut valider.

4. **Descente robuste (23), nuage (24), covariance (30) doivent attendre le résultat de 15**, qui doit inclure les
   designs « sélection robuste » comme bras.
   - 24 empile des appels du Jacobien existant, sans noyau nouveau : il est moins risqué que 23, qui demande une
     variante de `_res_jac_lossless_normal_kernel`.
   - 30 se scinde : mesurer la covariance est peu coûteux, car `native_evaluator(thickness=True)` rend déjà les
     épaisseurs déposées ; optimiser avec elle reste très lourd.

5. **Reprises 27–29 : P1 injustifié.**
   - U12 §6 consigne la décision « B plus tard » ; les deux premières étapes sont faites.
   - 27 : l'unité « tirage » est mal choisie. 300 tirages coûtent 0,27 s (A §1.2) ; le coût est le pipeline de plan
     (1 036 s).
   - 28 : la spécification parle de « départs et regroupement », alors que l'étage global mesuré est `run_memetic` :
     un seul flux aléatoire, des lots de taille égale au nombre d'ouvriers. Les essais durent 4 à 8 min.
   - 29 : aucune durée de corridor n'est mesurée dans les sources.
   - L'identité au bit bute sur D116 (coût dépendant du nombre de fils) et D84. L'empreinte doit porter le nombre
     d'ouvriers résolu.

6. **Gradients 11 et 12 : gains de vitesse non mesurés, pas des P1** selon la définition de la liste.
   - 12 : `IRGlobalObjective.gradient` appelle `_njit_ir_global_gradient_fused`, où `dk5` n'est affecté que si
     `arg > 0` (D112, ouvert). La liste cite « C13 », qui n'a plus de définition dans `docs/`.
   - 11 : `run_pglobal_optimization` ne reçoit qu'un coût scalaire. Le bicouche a un gradient complet
     (`compute_metal_bilayer_gradient_analytic`) ; le monocouche n'a que `gradient_function_fixed_eM`. Ce n'est pas un
     simple branchement.
   - 22 : A §4 demande de corriger d'abord le gradient faux sur couches absorbantes (D113) ; la liste a perdu ce
     préalable.

7. **Refactorings 16, 17, 18 : A §2.3 dit que chacun demande une décision de 👤.** La liste a perdu cette condition.

8. **Traçabilité.**
   - `docs/CHANTIERS_RESTANTS.md` n'est pas suivi par git.
   - L'arbre porte 17 fichiers modifiés et 73 supprimés non committés, dont 71 sous `reports/`.
   - Parmi eux, `ROBUST_PLAN.md`, source des « ±15 % » et « 0,99–1,02 » de Q §4.
   - « État vérifié sur `de52e01c` » ne décrit donc pas l'arbre.

## B. Tableau révisé

État : NR = non réalisé, P = partiel, IJ = insuffisamment justifié. Confiance : É élevée, M moyenne, F faible.

| N° | État réel | Bénéfice · risque · prérequis | Priorité | Complexité · confiance | Critère de fin et validations |
|---:|---|---|---|---|---|
| 01 | NR. Quatre valeurs à 120,0 s exactement : peu plausible comme mesure. Fixtures de module lançant 11 sous-processus, cache par processus (vérifié) | Jusqu'à 480 s du palier `ui` · risque nul | P2, à faire tôt | Faible · É | Journal `--durations` collé ; registre refait par `refresh_slow_tests.py` ; assertions inchangées |
| 02 | NR, 2 définitions (vérifié) | ~10 lignes | P3, en passant | Faible · É | Une définition ; tests `ui` RE et socle |
| 03 | IJ : l'audit dit lui-même « gain faible » | — | Supprimer | — · É | — |
| 04 | NR et sous-spécifié (A.1) | Décide la grille automatique et le 20 · risque : publier un résultat inadmissible | **P1** | Faible à moyenne · É | Juge stable à moins de 1 % entre deux pas, ou juge de l'article ; MF % ; `admissible()` consigné avec N, TOT, couche minimale ; plancher 5 nm ; oracle au pas du juge |
| 05 | NR, 4 sites sans Jacobien (vérifié) | Faible selon l'audit · change les derniers bits de références | P2 → P3 | Faible · M | Contrôle par différences finies ; temps apparié ; inactif par défaut |
| 06 | IJ : polissage final de 300 à 500 itérations après un L-BFGS-B à gradient (vérifié) | — | Supprimer | — · É | — |
| 07 | P : 5 `_warmup_numba_thread_runner`, crochet et `numba_manager` déjà au socle (vérifié) | Cohérence du démarrage · touche les fils Qt (D11, D23) | P2 → P3 | Moyenne · M | Une implémentation ; tests `ui` ; démarrage à froid des 5 modules |
| 08 | P : `certus_metal_base_app.py` existe | ~500 lignes, meilleur rendement des refactorings d'interface | P2 | Moyenne · M | Méthodes descendues ; tests `ui` METAL ; aucun calcul touché |
| 09 | NR, 4 définitions (vérifié) | Lié à 16 | P2 → P3, fusionner avec 16 | Moyenne · M | Voir 16 |
| 10 | NR : 12 sites `prepare_targets_vectorized`, aucun contexte ; 3 préparations sur 4 sont dans `certus/ui` (vérifié) | Supprime une classe de défauts déjà vue deux fois (ALG-18, `20563e25`) · touche le calcul | **P1** | Moyenne à forte, un site par commit · É | Un constructeur dans `core` ; test qui échoue si un site prépare seul ; `c1_diff` TENU ; oracle avant et après |
| 11 | NR, 2 polissages sans Jacobien (vérifié) ; voir A.6 | Gain non mesuré · interface de l'adaptateur à étendre | P1 → P2 | Moyenne · M | Part de temps mesurée d'abord ; accord coût/gradient ; différences finies ; paires appariées ; inactif |
| 12 | NR (vérifié) ; D112 ouvert ; pénalités à 1e12 dans l'objectif | Gain non mesuré · correction de noyau | P1 → P2, après D112 | Moyenne · É | D112 fermé, test rouge avant, `c1_diff` ; différences finies dans tous les modes ; mesure appariée |
| 13 | IJ : repli, « faible » selon l'audit | — | Fusionner dans 21 | — · M | — |
| 14 | NR, piste | Diagnostic de TOT · risque nul hors noyau | P3 | Faible à moyenne · F | Sonde sur 2 ou 3 cas connus ; décision écrite |
| 15 | NR. Aucune des 21 configurations STRAT d'exemple ne porte de cibles (vérifié) | Tranche 23, 24, 30, 31, 32 · malédiction du vainqueur · STRAT limité à H/L | **P1** | Moyenne, ~17 min machine par design · M | K ≥ 6 designs, bras nominal et robuste ; graines de notation disjointes ; RMSE contre cibles, SEEL, arrêts ; écart apparié |
| 16 | NR, 2 classes (vérifié) | Décision de 👤 requise | P2 → P3, bloqué | Forte · M | Une classe ; interactions STRAT conservées ; tests `ui` |
| 17 | P : hybride livré ; 45 `minimize(` dans 23 fichiers | Identité au bit à prouver site par site : coût supérieur au bénéfice | Supprimer comme chantier global | — · M | — |
| 18 | NR, `QMainWindow` direct (vérifié) | Thème, session · décision de 👤 | P2 → P3, bloqué | Moyenne à forte · M | Héritage du socle ; chargement, calcul, export inchangés |
| 19 | P : script et `mutation_pilot.py` présents ; audit d'appels sur `tests/integration` seul ; pas de rejeu | N'a de valeur que si 👤 assouplit CLAUDE.md §2 | P1 → P2 | Moyenne à forte · M | `--audit-calls` sans trou sur unit, ui, oracle ; rejeu sur N commits, zéro échappé ; équivalence par mutation |
| 20 | NR ; prémisse fausse (A.2) | Redondant si la grille automatique passe 04 | P2 → P3, conditionnel | Forte · M | Domaine de validité écrit, ou abandon motivé |
| 21 | NR (vérifié) | Gain non mesuré | P2 → P3 | Forte · M | Profil d'abord ; différences finies ; cas limites de base |
| 22 | NR (vérifié) ; D113 en préalable ; RNG global de FIELD (D116) | « Le plus gros » gain, non mesuré | P2, après profil | Forte · M | Oracle ; différences finies ; mesure appariée à graine fixée |
| 23 | NR | Critère de Gauss–Newton, dégradé à grand résidu (Q §4.4, bac à sable) · noyau nouveau | P2 → P3, après 24 | Forte · M | Différences finies du critère ; `c1_diff` ; validation par STRAT |
| 24 | NR | Exact à tout ordre, accepte des erreurs corrélées · coût × K | P2, conditionnel à 15 | Moyenne à forte · M | Tirages purs (C2) ; finalistes sur tirages neufs et par STRAT ; inactif |
| 25 | NR, piste | Vise les deux cas perdus | P3 | Forte · F | Comparaison appariée au tirage actuel sur trois-raies et cissoïde |
| 26 | IJ : risque de code machine périmé, D84 et D111 ouverts | Gain seulement en éditant les noyaux | Geler | — · É | — |
| 27 | NR ; unité mal choisie (A.5) | Confort · risque de résultat repris faux | P1 → P3, à respécifier | Très forte · É | Durées réelles mesurées ; unité = étape du pipeline ; tests U12 §5 |
| 28 | NR ; spécification en retard sur le code (A.5) | Idem | P1 → P3, à respécifier | Très forte · É | État = population, état du générateur, génération, ouvriers ; identité au bit à nombre de fils fixé |
| 29 | NR ; code des corridors non vérifié ici | Besoin non mesuré | P1 → P3, à instruire | Forte · F | Durée d'un corridor réel ; puis tests U12 §5 |
| 30 | NR ; à scinder | 30a mesure : peu coûteuse, à joindre à 15. 30b optimisation : très lourde | 30a P2 ; 30b P3 | 30a faible ; 30b très forte · M | 30a : `tr(Σ̂ JᵀJ)` comparé à la RMSE de dépôt réelle |
| 31 | NR : candidats = longueur d'onde et mode (vérifié) | Cœur de la co-conception · cibles requises | P2, conditionnel à 15 | Très forte · M | Gain contre cibles sur graines disjointes, sans arrêt ajouté |
| 32 | NR | Conditionnel à 15 | P3 | Très forte · M | Corrélation critère/SEEL sur les designs de 15 |
| 33 | NR : section 3 du protocole vide (vérifié) | Seuls défauts qu'aucune machine ne voit | **P1**, 👤 seul | Demi-journée humaine · É | Constats consignés, un par ligne |

## C. Regroupements et suppressions

- **Supprimer** : 03, 06, 17 (comme chantier global), 26 (gelé tant que D84 et D111 sont ouverts).
- **Fusionner** : 13 dans 21 ; 09 dans 16 ; 23, 24 et 30b en un seul « mérite robuste », ouvert par le résultat de 15 ;
  30a dans 15.
- **Respécifier avant de chiffrer** : 27, 28, 29.
- **Ajouter comme préalables nommés**, sans rouvrir d'ancien backlog : D112 pour 12, D113 pour 22, cibles dans un
  fichier STRAT pour 15.

## D. Ordre d'exécution

1. **Phase 0 — remise en état et mesures courtes.** Committer séparément la liste, la docstring et les suppressions
   (C3) ; 04 refait ; 01.
2. **Phase 1 — fondation.** 10, un site par commit ; D112.
3. **Phase 2 — mesure de décision.** 15 avec 30a, une campagne à la fois sur la machine.
4. **Phase 3 — selon 15 et 04.** 24, puis 23 si le nuage ne suffit pas ; 31 ; 32 ; 20 seulement si la grille
   automatique échoue à TOT plafonnée.
5. **Phase 4 — vitesse, sur profil.** Part de temps des polissages sans gradient, puis 12, 11, 22, 21.
6. **Phase 5 — interface, après décision de 👤.** 08, 07, 09 + 16, 18, 02.
7. **Hors file** : 33 (👤, dès maintenant), 19 (décision sur CLAUDE.md §2), 27–29 (respécification), 14 et 25.

## E. Cinq premières actions

1. **Refaire 04 avec juge convergé et admissibilité.** Le chiffre phare du 14 novembre peut être inadmissible ; le
   correctif tient en quelques lignes de `scripts/probe_auto_grid.py`.
2. **Chantier 10.** Seul refactoring adossé à des défauts constatés, dont un le 14 novembre, et préalable de tout
   mérite robuste.
3. **Campagne 15 élargie, avec 30a.** Une mesure tranche cinq chantiers lourds (23, 24, 30, 31, 32).
4. **Profiler avant de brancher un gradient.** Aucun gain de D1 à D7 n'est mesuré ; la part de temps des polissages
   décide de l'ordre 12, 11, 22, 21.
5. **U13 par 👤.** Une demi-journée, sans occuper la machine ni un agent.

## Incertitudes

- L'identité de `tl101_A_best.csv` avec l'un des trois designs de A §3.5 n'est pas documentée.
- L'écart d'un ordre de grandeur entre la RMSE de dépôt de STRAT (0,00264, exemple à 48 couches) et le RMS sous
  erreurs de 1 nm (0,02, 50/50) compare deux composants : c'est un indice, pas une mesure.
- Non vérifié : que le 50/50 est un design à deux matériaux compatible avec STRAT.
- Les similarités de A §2 sont reprises de l'audit ; seuls les comptes de définitions et l'absence de changement des
  fichiers depuis `09c3f7a7` ont été vérifiés.
