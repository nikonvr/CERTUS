# REPRISE — refactoring des corridors et audit UX

Fichier de reprise : tout ce qui est fait, en cours et à faire. Il est mis à jour à chaque étape, avant de passer à la
suivante. En cas de coupure, on repart d'ici. Le détail des phases est dans `REFACTOR_PLAN.md`, même dossier.

## Où est le travail

- Branche `claude/certus-1111-reprise-60e136`, dans le worktree `.claude/worktrees/certus-1111-reprise-60e136`, depuis
  la reprise du 2026-11-11 à 23 h : elle prolonge `claude/reprise-certus1111-926596` (avance rapide depuis `8088dc4c`,
  fin de la Phase 9), qui prolongeait `claude/certus-refactor-audit-6cd1fc` (arrêtée à `bea41352`). Les deux worktrees
  précédents restent arrêtés à ces commits.
- Ce dossier, `reports/refactor_corridors_2026-11-11/` : le plan, ce fichier, l'instantané de référence
  (`reference_snapshot.json`), les manifestes des phases (`manifests/`).
- Rien n'est poussé. Pousser publie le dépôt : seulement sur ordre.
- La copie `REFACTOR_PLAN.md` restée à la racine du checkout principal est périmée, et y fait échouer deux contrôles :
  à supprimer là-bas.

## Reprendre après une coupure

1. `python scripts/preflight.py` doit finir par `PREFLIGHT=GO`.
2. `git status -sb` puis `git log --oneline -n 8` : comparer à « Fait » et « En cours » ci-dessous.
3. Si des fichiers sont indexés mais pas commités, ils appartiennent à la phase « En cours » : relancer ses tests (liste
   dans la phase, au plan), puis la garde, puis la validation, avant de commiter.
4. Garde : `python scripts/refactor_guard.py snapshot --out <fichier temporaire>`, puis
   `python scripts/refactor_guard.py compare reports/refactor_corridors_2026-11-11/reference_snapshot.json <fichier temporaire> --manifest reports/refactor_corridors_2026-11-11/manifests/phase_1.json`
   (ajouter un `--manifest` par phase faite : `phase_2a.json`, `phase_2b.json`, …). Attendu : `GUARD=OK`.
5. Validation complète : `python scripts/validate_parallel.py`, environ 25 minutes, rien d'autre en même temps.
   **État connu** : `coherence_md` sort en erreur sur 3 commandes mortes de documents de campagne (laissé tel quel sur
   décision) ; un test qui chronomètre peut être rouge en parallèle et vert seul. Tout autre rouge est nouveau.
   Un test « au bit » d'un noyau rouge même seul : le rejouer avec `NUMBA_CACHE_DIR` sur un dossier neuf avant de
   conclure ([`cache_numba_arbre_neuf.md`](cache_numba_arbre_neuf.md)).

## Consignes reçues de 👤 (2026-11-11)

- Enchaîner les phases en boucle, sans s'arrêter entre elles : un travail soigné mais rapide.
- Trancher soi-même les questions ouvertes, le plus intelligemment possible, et consigner la décision (plan, section 4).
- Inscrire toute tâche faite ou à faire dans ce fichier de reprise.
- Viser une UX « top 1 % mondial » : audit UX complet, à ajouter à l'audit (plan, section 5).
- Nuit du 2026-11-11 : poursuivre en autonomie, « autorisation sur tout ». Lu comme : trancher et commiter sans
  demander. Rien n'est poussé pour autant (dépôt public : pousser reste un ordre explicite).
- 2026-11-11, 23 h : « tourne en mode 100 % autonome, je te donne toute autorisation ». Même lecture : tout enchaîner
  et commiter, ne rien pousser.

## Fait

| Quoi | Commit |
|---|---|
| Audit statique et plan (`REFACTOR_PLAN.md`), arbitrages Q1 à Q5 et Q16 | dans `211d561b` |
| Correctif ruff B905, `zip(..., strict=False)` dans un script de campagne | `9d011d68` |
| Correctif échappement invalide, chaîne brute dans un script de campagne | `15d518aa` |
| **Phase 0** : `scripts/refactor_guard.py`, ses 13 tests, instantané de référence, plan déplacé ici | `211d561b` |
| **Phase 1** : état déclaratif, contrats, 52 tests, manifeste ; toutes les questions ouvertes tranchées (plan, section 4) | `0e3d4b57` |
| **Audit UX** complet des 11 modules : plan, section 5 (constats A, B, C et feuille de route U1 à U13) | `74de941e` |
| **Phase 2a** : les trois constantes corridor n'ont plus qu'une définition | `bea41352` |
| **Phase 2b** : `_apply_fixed_log_k_axis` et ses deux bornes n'ont plus qu'une définition | `4be1b0af` |
| **Phase 2c** : les 16 constantes de fenêtre n'ont plus qu'une définition, dans le cœur spline | `133becde` |
| **Phase 2d** : les deux clés du smart-init n'ont plus qu'une définition, dans `common` | `d16346d9` |
| **Phase 2e** : les trois classes du smart-init n'ont plus qu'une définition, dans `state_ui` | `de79f62e` |
| **Validation complète de la phase 2** : rien de plus que l'état connu (plan, Phase 2) | sur `de79f62e` |
| Garde étendue : une méthode peut quitter une classe pour une tranche dont elle n'hérite pas, si le manifeste le dit | `85e5d24f` |
| **Phase 3a** : `_CorridorRunMixin`, 15 méthodes dans `certus_index_spline_corridor_run.py` | `cdc5ce24` |
| **Phase 3b** : `_CorridorRmseViewMixin`, 9 méthodes dans `certus_index_spline_corridor_rmse_view.py` | `32e5d038` |
| **Phase 3c** : `_CorridorIntervalMixin`, 11 méthodes dans `certus_index_spline_corridor_interval.py` | `9c4720cd` |
| Outils d'extraction d'une tranche (`tools/`, six étapes, mode d'emploi en tête de chaque fichier), Q18, Q20, Q21 tranchées, 3d préparée | `24dc5a0b` |
| **Phase 3d** : `_CorridorNkMixin`, 7 méthodes dans `certus_index_spline_corridor_nk.py` | `d3118167` |
| **Validation complète de la phase 3** : un rouge réel dû à 3a (`test_progress_imports.py`, liste de modules), corrigé (Q22) ; le reste est l'état connu (plan, Phase 3) | sur `d3118167`, correctif au commit suivant |
| **Phase 4** : `_CorridorRmsePlotMixin`, 10 méthodes dans `certus_index_spline_corridor_rmse_plot.py` ; `rendering.py` sous 1 000 lignes | `7db3b42a` |
| **Validation complète de la phase 4** : rien de plus que l'état connu (plan, Phase 4) | sur `7db3b42a` |
| **Phase 5a** : les trois fonctions de calcul des corridors dans `certus_index_spline_corridor_jobs.py` | `2d8cc760` |
| **Phase 5b** : le mandataire paresseux de la fenêtre dans `certus_index_spline_lazy_app.py` | `7198ce64` |
| **Phase 5c** : `_start_curve_minimum_deep_refit` dans `_CorridorRunMixin` ; Q23 tranchée | `44b24b2a` |
| **Phase 5d** : les 8 méthodes statiques sont des fonctions de `certus_index_spline_statics.py`, 8 commits, plus le test | `bdba59cb` à `d7b068d7`, test `55f2d194` |
| **Validation complète de la phase 5** : rien de plus que l'état connu (plan, Phase 5) | sur `55f2d194` |
| **Phase 6a** : garde-fous d'héritage étendus aux huit autres fenêtres, plus celui de F11 (aucun nom masqué par Qt) | `18be2a5b` |
| Garde : une classe sortie des bases d'une fenêtre reste en tête de son propre MRO | `ab7f6884` |
| **Phase 6b** : `_UIMixin` hors des bases de la fenêtre | `a0150bc9` |
| **Phase 6c** : le constructeur donne à tout l'état corridor sa valeur par défaut, depuis la table | `fce0ee90` |
| **Phase 8, clôture** : registre de dette exact, garde finale `GUARD=OK` avec les 17 manifestes, relevé des 56 imports sans lecteur | `9c57ffd8` |
| **Validation complète des phases 6 et 8** : rien de plus que l'état connu (plan, Phase 6) | sur `9c57ffd8` |
| **Phase 9** : les deux tests de `test_mwir_gui_flow.py` remplacent `GenericWorker` là où la méthode le lit ; preuve faite que le vrai était construit | commit suivant `d9db99a7` |
| **Phase 10a** : une courbe RMSE(d) vide écrit `-1`, plus `None`, dans `_corridor_rmse_best_idx` (Q17) ; test rouge avant (`8 failed`) | `43d48d3f` |
| **Phase 10b** : la branche morte de `_plot_result` est retirée, `NEVER_ASSIGNED` est vide (Q13) ; test rouge avant (`1 failed`) | `82007a4a` |
| **Phase 10c** : `_load_defaults` remet les huit attributs corridor écrits pour un échantillon (Q11) ; test rouge avant (`2 failed`) | `5b801bf5` |
| **Phase 10e** (Q24, trouvée par la mesure de 10c) : `_load_defaults` oublie aussi `_last_worker_result` et `_last_run_cfg` ; avant, « Recalculate RMSE(d) » après un reset relançait la grille sur l'échantillon oublié ; test rouge avant (`4 failed`) | `0267b135` |
| **Phase 10d** : le `2e-4` de l'intervalle robuste s'appelle `_DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA`, lu aux six endroits (Q12) ; test rouge avant (`3 failed`) | `e9f68946` |
| **Validation complète de la phase 10** : rien de plus que l'état connu ; un rouge dû au cache Numba de l'arbre neuf, vert sur cache vierge ([note](cache_numba_arbre_neuf.md)) | sur `e9f68946` |
| **Phase 7a** : `_resolve_strat_indices_db_path` descend dans `certus/core/certus_indices_db.py` ; FIELD n'importe plus rien de STRAT ; test rouge avant (`4 failed`) | `37c9ca26` |
| **Phase 7b** (Q25) : `spectral_rmse_weights` descend dans `certus/domain/spectral_weights.py` ; DESIGN, RE et le gradient analytique la prennent là ; oracle avant/après verts, `c1_diff HEAD` : C1 TENU (9 092 tableaux) ; test rouge avant (`7 failed`) | `aa75be4f` |
| **Validation complète de la phase 7** : rien de plus que l'état connu, et le même test « au bit » rouge sur le cache de l'arbre, vert sur cache vierge (deuxième occurrence, mêmes valeurs : [note](cache_numba_arbre_neuf.md)) | sur `aa75be4f` |
| **U1a** : les unités inverses (`nm⁻¹`, `nm⁻²`) et le `ξ` que le code prouve reviennent dans dix chaînes et une infobulle d'INDEX SPLINE ; test rouge avant (`2 failed`) | `0b3fc350` |
| **U1b** : huit « ? » des phrases de l'onglet RMSE(d) deviennent `≈` (valeur), `∈` (intervalle) et `—` (titre) : un choix, l'historique n'a pas l'original ; attendus de `test_rmse_tab_summary.py` mis à jour (`5 failed` avant) | commit « U1b » |

## En cours

Rien : tout ce qui est fait est commité. La prochaine tâche est la première de la liste ci-dessous.

## À faire, dans l'ordre

1. Feuille de route UX, plan sections 5.5 et 5.6 : U1c (français visible : `corridor_tab` ×2, `strat_ui_layout`,
   `strat_stack_progress_widget` ×3, `eventsextras` ; puis cliquet général), puis U2 à U5.
2. À 👤 : dire si `test_without_the_flag_the_kernel_keeps_the_coarse_samples_bit_for_bit` doit exiger le bit entre deux
   spécialisations Numba ; tant qu'il le fait, une validation en parallèle peut le rendre rouge selon le cache.

Outils : pour une extraction, `tools/` (`plan_move`, `move`, `manifest`, `contracts`, `protocols`, `born_in`, puis `guard`
et `lot`) ; `tools/static_to_function.py` pour une méthode statique ; `tools/unread_imports.py` pour le relevé de clôture.
