# Registre des audits — état au 2026-10-20 (`4c10ce44`)

Un constat par ligne. Sources : audits UX et algorithmique du 2026-10-16 (anciens `UXargon.md` et `designargon.md`, retirés,
relire par `git show d4e2b2ba:UXargon.md`), contre-audit du 2026-10-17, audits de la suite du 2026-10-18 (deux passes), audit du
code du 2026-10-19, audit d'arrêt OMS du 2026-10-10 : rapports datés dans `reports/`, recoupement dans
[`reports/AUDIT_UX_recoupement_2026-10-20.md`](../reports/AUDIT_UX_recoupement_2026-10-20.md). Un `Dnnn` a son détail en
[`ETAT.md`](ETAT.md) §4 ; décision de 👤 avant tout changement de nombres (CLAUDE.md §5).

États : **ouvert** · **corrigé** (commit) · **à reproduire** (statique, effet non mesuré) · **piste** (capacité ou expérience, pas un défaut).

## Interface

| id | constat | où | état |
|---|---|---|---|
| UX-01 | Lire la configuration DESIGN nettoyait la pile | `StateManager._collect_config` | corrigé `868db8c9` |
| UX-02 | L'export Excel DESIGN modifie la pile (`smart_cleanup`) | `ExportManager.export_excel` | ouvert |
| UX-03 | Les nettoyages supprimaient des couches fixes (D08, U01) | `smart_cleanup`, `_apply_5nm_minimum` | corrigé `bdcae9ed` |
| UX-04 | Budgets PGLOBAL affichés ≠ appliqués avec la croissance cochée | `WorkerManager._capped_global_budgets` | journal corrigé `7f3edea8` ; spinboxes ouvert |
| UX-05 | Profil détaché : la boucle efface la cible et retrace sur le graphe principal | `PlotManager._plot_profile_actual` | ouvert |
| UX-06 | Titre d'axe Y codé `color="black"`, illisible en sombre (DESIGN, RE) | `_update_optim_live_plot_normal_mode`, `_finalize_oblique_live_plot`, `spectrum_eval_apply_axes_legend_scale` | ouvert |
| UX-07 | `Ctrl+E` = Évaluer dans DESIGN, Exporter dans l'aide F1 | `EventsManager._setup_shortcuts` | ouvert |
| UX-08 | DESIGN : 9 boutons primaires, colonne `Preset` à un seul choix, onglet initial Synthesis | `LayoutManager` | piste |
| UX-09 | Fenêtre Pareto sans parent, menu en français, couleurs `Qt.GlobalColor` | `_ensure_pareto_ui`, `_show_pareto_context_menu`, `_populate_pareto_table_row` | ouvert |
| UX-10 | Palettes de graphe en cache sans clé de thème | `get_plot_style_config`, `get_plot_theme_palette` | à reproduire |
| UX-11 | Le zoom remplace la feuille de fenêtre sans les surcharges initiales | `CertusZoomMixin._apply_ui_zoom` | à reproduire |
| UX-12 | Logo foncé en thème sombre (D82) | `create_header_logo_widget` | ouvert |
| UX-13 | Boîte modale à chaque copie ou export réussi d'un graphe | `CertusScientificPlot._copy_excel_tsv` et `_export_*` | ouvert |
| UX-14 | Le clone détaché perd courbes suivies et formateur du réticule (U07) | `clone_plot_widget` | ouvert |
| UX-15 | Le Detach de la barre crée un clone figé (clé `certus_detach_<id>`), hors des mises à jour | `open_detached_certus_plot` contre `_get_plot_targets` | ouvert |
| UX-16 | Docstring : Detach `Ctrl+D`, réel `Ctrl+Shift+D` ; barre de 6 boutons redondants | `CertusScientificPlot.get_toolbar` | ouvert |
| UX-17 | Le validateur efface l'info-bulle d'origine, dès l'attachement | `attach_numeric_validator` | ouvert |
| UX-18 | États vides : mécanisme présent, fonctionnement par table non testé | `_auto_install_empty_states` | à reproduire |
| UX-19 | Tour STRAT d'un autre logiciel, cible `measurement_table` absente | `_steps_strat` | ouvert |
| UX-20 | Tours INDEX, INDEX_SPLINE, METAL sans cible ; aucun tour HUB, SMOOTHER, SUBSTRATE ; ni `Esc` ni flèches | `certus_tours_catalog`, `_OnboardingOverlay` | ouvert |
| UX-21 | `ProgressDialog` lit des attributs qu'il n'a pas (U06) | `ProgressDialog.apply_progress_snapshot` | ouvert |
| UX-22 | RE appelle `apply_progress_snapshot` absent de `DualStageProgressWidget` : `AttributeError` (U10) | `_on_re_worker_progress_snapshot` | ouvert |
| UX-23 | Fin de calcul en bouton rouge « Done » ; `reset` affiche `status=idle` brut | `DualStageProgressWidget.stop`, `.reset` | ouvert |
| UX-24 | Palette : `run.optimize` annonce `Ctrl+R`, le raccourci est `F5` | `CertusCommandPaletteMixin._default_commands` | ouvert |
| UX-25 | Annuler limité à `front_table`, sans rétablir | `CertusAppUndoMixin` | piste |
| UX-26 | Clic sur un fichier récent du Hub : journalisé, rien d'ouvert | `CertusHub._on_recent_config_selected` | ouvert |
| UX-27 | Hub : zoom du menu Aide factice, pas de `Ctrl+K`, raccourcis pour 5 modules sur 10, pas de filtre ; coquille `calculationation` | `_install_help_menu`, `_setup_shortcuts`, `__init__` | ouvert |
| UX-28 | `GroupedApplicationCard` ne lance que le premier sous-programme ; jamais instanciée | `GroupedApplicationCard.__init__` | latent |
| UX-29 | `execution_mode` écrase 4 champs éditables (journal `overridden` seulement) | `CertusStratStateMixin.collect_params`, `_MODE_BUDGETS` | ouvert ; le mode prime (D1) |
| UX-30 | Graphe central STRAT en PNG statique, flou au redimensionnement | `main_plot_widget` | piste |
| UX-31 | STRAT : charger un JSON ouvre visionneuse + boîte modale ; un clic de ligne ouvre 3 fenêtres à position fixe | `load_configuration_from_path`, `on_strategy_visualization_requested`, `on_cell_clicked` | ouvert |
| UX-32 | Rattacher la table des couches la fige à 230 px | `reattach_stack_window` | ouvert |
| UX-33 | Multi-seed ignore la configuration de la fenêtre ; son `QProcess` échappe à la confirmation de fermeture | `CertusStratMultigraineMixin` | ouvert |
| UX-34 | Colonne « Next » = médiane des extrema ; Step 0/1 ; `F5` lance l'étape 2 ; français ; `QColor(80, 80, 80)` ; branches SEEL identiques | `BASE_HEADERS`, `_fill_seel_cells` | ouvert |
| UX-35 | INDEX : cinq `setCurrentIndex(0)` renvoient sur `Data`, dont l'aperçu en direct | `load_file`, `run_optimization`, `_apply_index_live_plot_payload`, `_display_results`, `_load_defaults` | ouvert |
| UX-36 | Choix scientifiques validés seuls au bout de 5 s | `_ask_keep_raw_or_smoothed`, `_on_tlu_constrained_finished` | ouvert |
| UX-37 | INDEX et METAL : aucun export manuel ; l'export ne suit que l'auto-export du Hub | `export_results` (INDEX, `MetalBaseApp`) | ouvert |
| UX-38 | `table_res` reconstruite toutes les 2 s sur le fil GUI | `CertusIndexWorkerMixin._on_progress` | à reproduire |
| UX-39 | Cartes `FlashyCard`/`perf_tab` orphelines, KPI en double, onglet Synthesis devant le spectre (INDEX, RE, METAL) | `_build_ui`, `_build_right_panel`, `_setup_plots` | ouvert |
| UX-40 | Libellé « Absorbent substrate (k = 0) » ; deux boîtes modales au chargement | `chk_absorbing_sub`, `load_file` | ouvert |
| UX-41 | SPLINE : pas de barre Save/Load/Export ; `Ctrl+O` charge le spectre | `_UIBuilderMixin._build_ui` | ouvert |
| UX-42 | Smart Init ouvre 2 fenêtres (+2 à la demande) ; le dialogue des nœuds ouvre un aperçu flottant | `_show_smart_init_preview_dialog`, `ManualSigmaKnotDialog.__init__` | ouvert |
| UX-43 | Symboles perdus (`?` pour `—`, `≈`, `⁻²`) ; libellés français | `_plot_corridor_rmse_tab`, `_build_tab_spectrum`, `_build_tab_data_corridor` … | ouvert |
| UX-44 | Contrastes `#d4a100` (2,24:1), `#c97800` (3,23:1) ; panneaux noirs codés en dur | `ManualSigmaKnotDialog` | ouvert |
| UX-45 | SPLINE sans base de dépôts ; `DepositDatabaseDialog` sans tri (le filtre existe) | `certus_depots_dialog` | ouvert |
| UX-46 | RE : colonnes de `target_table` éditables mais ignorées une fois le classeur chargé | `CertusRETableMixin._get_oblique_tgts` | ouvert |
| UX-47 | RE propose `Avg`, non calculé (DESIGN l'a retiré, `1487a7f9`) | `CertusRETableMixin.add_target` | ouvert ; voir ALG-08 |
| UX-48 | STOP fige la fenêtre jusqu'à 300 s | `CertusREWorkersMixin.stop_optim` | ouvert |
| UX-49 | RE : pas de Save/Load en barre ; dialogue de résultats modal et au premier plan, 8 boutons en ligne ; `α_ref`, `Angle()`, `Loade`, `[DBG-UI]` | `_build_left_panel`, `CertusREResultsDialog` | ouvert |
| UX-50 | FIELD : boutons de la pile cachés quand elle est ancrée | `StackPanelWidget._build_ui` | ouvert |
| UX-51 | FIELD : pas de bouton Stop (seulement `Esc`) | `OptimizationPanelWidget`, `request_stop` | ouvert |
| UX-52 | FIELD : chaque recalcul renvoie sur l'onglet Overview | `_refresh_result_views` | ouvert |
| UX-53 | FIELD : Help en toast, chemin d'export non dit, replis `seuil1`/`seuil2` à 0,5 au lieu de 3 et 25 | `open_help`, `export_data`, `_apply_config` | ouvert |
| UX-54 | METAL : `QLineEdit` sans validateur, `num_knots` ramené à 5 sans le dire ; deux bascules de thème ; compteurs sans libellé ; feuille « Drude-Lorentz » | `MetalBaseApp`, `CertusMetalSingleApp`, `_do_export_results` | ouvert |
| UX-55 | SMOOTHER arrondissait λ à 0,1 nm à l'enregistrement (U08) | `read_measurement_excel` | corrigé `8c6d951b` |
| UX-56 | SMOOTHER : lissage recalculé à chaque bascule et à l'enregistrement ; état vide brut | `update_plot`, `save_file` | ouvert |
| UX-57 | SUBSTRATE : calcul synchrone sur le fil GUI, Cancel sans effet | `SubstrateIndexGUI.calculate_index` | ouvert |
| UX-58 | SUBSTRATE : réglages sous `"SFL"` ; tableaux bruts ; exports seulement dans `IndexTableDialog` | `SubstrateIndexGUI` | ouvert |
| UX-59 | SMOOTHER et SUBSTRATE sans bascule de thème ni services du socle | `CurveSmootherGUI`, `SubstrateIndexGUI` | piste |
| UX-60 | `audit_ux_certus.py` lit les feuilles déclarées, pas les pixels ; 0 sur 22 à l'ouverture seulement | `sheet_contrast_pairs` | ouvert |
| UX-61 | INDEX lance `fit_sellmeier_global` (`differential_evolution`) sur le fil GUI | `CertusIndexWorkerMixin._on_finished` | à reproduire |
| UX-62 | METAL SINGLE : « Auto-select n & k » sélectionne Reflectance | `on_beam_finished` | à reproduire |

## Algorithmes et physique

| id | constat | où | état |
|---|---|---|---|
| ALG-01 | Scan Needle divisé par `count`, coût par `sum_w` (classement inchangé si le rapport est constant) | `needle_scan_cached` | ouvert, impact faible |
| ALG-02 | Évaluateur d'élagage inopérant (D107) | `_prune_to_target._evaluate_test_stack` | ouvert ; correctif sur `claude/alg02-prune-evaluator-0d2a8d` |
| ALG-03 | Grille oblique densifiée non rendue au worker | `maybe_upgrade_grid_tikhonravov` | à reproduire sur un vrai worker |
| ALG-04 | Le scan Needle ne teste que le premier matériau différent | `NeedleOptimizationStrategy._build_needle_scan_mask` | piste |
| ALG-05/06/07 | Mode local par PGLOBAL ; raffinement final par gradient normalisé ; prototype Jacobien + TRF | `OptimWorker`, `run_coord_descent_5cycles` | piste |
| ALG-08 | Moyenne s/p (`Avg`) et factorisation des passes obliques | `_design_compute_oblique_error_and_grad_analytic_common` | piste |
| ALG-09/10/11 | Sobol/clustering à profiler ; extinction contre consolidation ; Needle analytique, corridors, GD/GDD, couleur | `PGlobalOptimizer` … | piste |
| ALG-12 | Pénalité `min_d` : coût, coût avec gradient et gradient disent trois choses (`MIN_THICKNESS` = 0,01 nm) | `certus_design_core`, `cost_numba_fast` | latent |
| ALG-13 | Polissage final : 12 gradients après la demande d'arrêt (R05) | `OptimWorker.run` | à reproduire |
| ALG-14 | Scan Needle avec face arrière sans cache : toute la pile recalculée par position | `needle_scan_cached_backside` (remplace `_run_needle_fallback_scan`) | corrigé ; ×14 à ×39, même aiguille ; suivi au banc `needle_scan_backside` |
| ALG-15 | L'export écrivait dans le tableau un meilleur résultat d'une autre structure | `ExportManager._sync_export_result_with_best_eval` | corrigé `76349415` |
| ALG-16 | Le bloc `optim` des fichiers d'exemple était ignoré au chargement | `StateManager._apply_config` | corrigé `a813fa64` |
| ALG-17 | La session de décimation Pareto ne se refermait jamais | `_clear_smart_decimation_state` | corrigé `08f7e7e6` |
| ALG-18 | Champion et relances jugés sur le RMSE d'un autre design (export « 0,00013 » pour 0,0029) | `_restore_smart_decimation_best_overall`, `_restart_from_best` | corrigé `0f11743f` ; tenue des enregistrements Pareto à revoir |
| ALG-19 | La règle finale des 5 nm retire des couches sans réoptimiser | `_apply_5nm_minimum` | ouvert ; contourné (champion conforme, plancher du mémétique) |
| ALG-20 | L'étape globale PGLOBAL borne chaque couche à 1,2 QWOT | `optim_bounds_thickness_global` | ouvert ; le mémétique monte à 3 QWOT |
| ALG-21 | `floor_at_end` : des couches fines réapparaissent après les aiguilles | `_apply_floor_at_end` | ouvert, option inactive |
| ALG-22 | RMSE de la fenêtre sous celui de la grille fixe, même à 420 points par cible | `_calculate_tikhonravov_points` | à reproduire |
| ALG-23 | Enfants du mémétique polis un à un, chaque évaluation n'occupant que ~140 longueurs d'onde sur 8 fils | `run_memetic` | piste ; polissages concurrents (noyaux `nogil`), ×4–×6 estimé, à chronométrer à qualité égale |
| ALG-24 | Chaque relance refait 1000 enfants depuis un design déjà très bon | `_restart_from_best` | piste ; 300 enfants aux tours suivants, ×2–×3 estimé, qualité à vérifier |
| ALG-25 | Incidence normale avec face arrière évaluée par la machinerie oblique à 0° (0,21 s par évaluation sur Bonne Mère) | `compute_oblique_backside_bundle_analytic` | piste ; chemin normal dédié, gain à mesurer |
| ALG-26 | Scan Needle oblique (s, p) sans cache : toute la pile recalculée par position | `_run_needle_fallback_scan` | piste ; même cache qu'ALG-14, ×10–×40 estimé |
| ALG-27 | Criblage des enfants par polissage court (`memetic_screen_maxiter`, 0 par défaut) jamais mesuré | `run_memetic` | piste ; ×2 estimé, risque sur la qualité |
| ALG-28 | Trois appelants recompilés à chaque démarrage (parade C18, `cache=False`) | `calc_spectrum_front`, `calc_spectrum_full`, `compute_batch_rmse` | piste ; quelques secondes par lancement |
| C20 | Gradient hérité faux sur couches absorbantes (D113) | `compute_gradient_all_layers_analytic` | ouvert |
| C06/C07 | Nœud NaN → `n = k = 0` (D108) ; épaisseur négative acceptée (D109) | `get_nk_from_spline`, `calculate_RT_vectorized_real` | ouvert |
| C21/C22 | Entrées invalides (NaN, k < 0, n = 0) rendues en fini plausible (D114) | noyaux `fastmath`, `certus_inputs` | ouvert ; politique k < 0 à trancher |
| C13 | `dk5` non affecté quand `arg == 0` (D112) | `_njit_ir_global_gradient_fused` | ouvert |
| C23–C28 | Caches modifiables, base RE à 1 nm, FIELD non amorcé, mélange de graines voisines, dernier bit selon les fils, XYZ hors plage (D116) | — | ouvert |
| C29 | Quatre mutants de formule survivent (D115) | `xyz_to_lab`, `delta_e_2000` … | ouvert |
| C18 | Relecture du cache Numba plante l'interpréteur (D111) | `calc_spectrum_front`, `calc_spectrum_full`, `compute_batch_rmse` | parade `cache=False` ; cause ouverte |
| C01 | `ColorWorker.run` levait `TypeError` | `ColorWorker.run` | corrigé `f32734a9` |
| IDX-01 | Banc INDEX : `mesures-c1b-sio2` et `sb2s3-silice` hors de l'espace de recherche (garde E_g, `n_sub` NaN sous 230 nm, pénalité `TLU_PRIOR_TRANSPARENT_N_MIN_SOFT = 1.50` sur tout n < 1,50) | `TLUObjective` | ouvert ; décision de 👤 |
| OMS-01 | Chemin « grille machine » de l'arrêt : cinq défauts (D93 à D95) | `certus_strat_growth` | corrigé le 2026-10-10 |
| OMS-02 | Ancres, inversion et armement de l'arrêt (D96 à D98) | modèle d'arrêt | modèle par défaut depuis `8d9ced13` ; D99 non-défaut |
| STR-01 | Dérive de vitesse `Rate` non modélisée (P3.1) ; seuil OT ≤ 50 nm non codé (P3.2) | `certus_strat_growth` | ouvert ; P3.0 mesuré : [rapport](../reports/STRAT_r75_leviers_bonne_mere_2026-10-20/bilan.md) |

## Outillage, dépôt, architecture

| id | constat | état |
|---|---|---|
| C10/C30 | CI : contrôles documentaires absents, `continue-on-error` sur mypy et bench, `pytest-benchmark`/`pytest-xdist` non déclarés (D110) | ouvert |
| C31 | `sha1` dans `lint_ns_snapshot.describe` ; 11 entrées de `.git/worktrees/` ; 7 lignes françaises dans `certus/` que le détecteur ne voit pas | ouvert |
| C14 | `__init__.py` hors `certus/domain/` ; un `.tmp` de 1,4 Mo suivi ; objets `tmp_obj_*` orphelins | ouvert |
| C02/C04/C05/C08/C11/C19 | xdist, pointeur d'archive, chemins longs, `open_file_explorer`, français, audit `connect(lambda)` | corrigés (`f494b9e5`, `36758165`, `e1acab83`, `8610e18d`, `f7edd4a6`, `3a2b443f`) |
| A14 | Archive de 8,2 Go en une seule copie | ouvert |
| ARC-01 | 44 `connect(lambda)` (D11), 6 `gc.collect()` STRAT (D23), 20 arêtes montantes et un cycle (D26), silicium lu à l'import (D68), dette de lint (D25) | ouvert, sous cliquet |
| ARC-02 | Gel : `loky` (D50), taille 411 Mo pour 300 (D72) | ouvert |
| ARC-03 | RE sans base de dépôts ; importateur n'apparie pas T et R d'un même échantillon (P5.1) | piste |
