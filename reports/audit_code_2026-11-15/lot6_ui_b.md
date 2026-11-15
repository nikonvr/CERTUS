# Lot 6 — `certus/ui/`, seconde moitié (io_ui → mixins/base_core_mixins)

2026-11-15, worktree `claude-code-question-0aa978` (code de `claude-code-suije-bf4f1f`, e8d1147f). Lecture seule : rien ici n'est mesuré.

## 1. Périmètre lu

- **En entier** : `certus_re_workers_mixin`, `certus_spectrum_eval_ui`, `certus_re_state_mixin`, `certus_substrate_presenter`, `certus_io_ui`, `certus_session`, `certus_worker_manager`, `certus_strat_defaults`.
- **En partie** : `certus_strat_ui_state/_worker/_export/_layout/_events`, `certus_metal_base_app/_single_gui/_bilayer_gui`, `certus_re_excel/_table/_layout_mixin`, `certus_substrate_ui`.
- **Survolés par Grep** : le reste (thème, widgets, tracés STRAT).
- ≈ 7 500 lignes sur 39 029 : **~19 %**. Hors lot : `certus_spectral_workers`, `certus_metal_single_app/_physics`, `certus_re_helpers`, `certus_base_app_*`.

## 2. Notes sur 10

| critère | note | preuves | confiance |
|---|---|---|---|
| Exactitude (UI → calcul) | 3 | C1, C2, M1, M2, M4, M5, M7 ; contre-exemple : `collect_params` STRAT | moyenne |
| Tests | 5 | 24 à 48 fichiers par famille ; rien sur C1, `_compute_re_rmse`, ni l'aller-retour de `thickness_tolerance_nm`, `combo_substrate`, `lmin_filter` | forte |
| Architecture, couplage | 4 | modèle RE réassemblé trois fois dans l'UI ; Sellmeier SiO2 dans `certus_re_excel_mixin` ; méthode en double vue/présentateur | forte |
| Lisibilité, maintenance | 5 | six fichiers > 1 400 lignes ; 20 lignes de doutes dans `update_lambda_filters` | moyenne |
| Robustesse, concurrence | 5 | bon : `_retain_until_finished`, `_set_busy` compté ; mauvais : M3, m1–m3 | moyenne |
| Ergonomie, accessibilité | 6 | Échap à vide muet, `refuse_to_run` place le curseur ; contre : m3, résumé METAL « SUBSTRATE: (UNKNOWN) » | moyenne |
| Performance | 5 | évaluation en fil + pool ; 300 s d'attente dans le fil GUI (M3), SUBSTRATE synchrone (m3) | faible |

## 3. Défauts

**Critiques**

- **C1** `certus_spectrum_eval_ui::spectrum_eval_on_finished_prepare_display` (DESIGN et RE) : `_monotonic_visual_mode_enabled()` rend toujours `True` ; une évaluation au RMSE pire que `_best_eval_rmse` est remplacée à l'écran par la copie du meilleur, et `_update_qwot_from_ep(ep_best)` réécrit le tableau. L'instantané n'est remis à zéro qu'au chargement ou au lancement d'une optimisation, jamais quand un réglage change. DESIGN : RMSE 0,010 sans face arrière, on la coche (vrai 0,030) → courbe et titre « 0,010 » de l'ancien réglage, saisie de couche annulée ; seul un `logging.info` le dit. RE : réactiver un groupe de cibles, idem. VÉRIFIÉ.
- **C2** `certus_metal_single_gui::start_beam_analysis` → `BeamAnalysisWorker.run` : le balayage d'épaisseur n'ajuste que R (`objective_function_fixed_eM`, `t_tgt=None`, `rb_tgt=None`) mais compare au seuil `1,5 × optimal_mse` d'un ajustement sur R + T + Rback. Fichier λ,R,T,Rback → à eM fixé les splines n,k refont R seul → l'intervalle eM publié mesure la fenêtre ±20 nm. Mécanisme VÉRIFIÉ ; ampleur SOUPÇONNÉE.

**Majeurs**

- **M1** `spectrum_eval_build_worker_cfg` (RE) : l'EvalWorker lit `cfg["back"]` (case globale, cochée si une colonne est BK) et ignore `include_backside` hors faisceau P4 ; le REWorker ignore `"back"` et ajuste colonne par colonne. T « BK » + R « noBK » → courbe et RMSE de R affichés avec face arrière, autre modèle que l'ajustement. VÉRIFIÉ.
- **M2** `CertusREWorkersMixin::_compute_re_rmse` prend d'abord `_re_loaded_exact_ep`, posé au chargement, jamais rafraîchi : après un RE, `_show_final_re_title` affiche le RMSE des épaisseurs du classeur avec les indices ajustés. VÉRIFIÉ.
- **M3** `CertusREWorkersMixin::stop_optim` : `rw.wait(300000)` dans le fil GUI (gel jusqu'à 5 min), puis `self._re_worker = None` même fil vivant : dernière référence d'un QThread en cours, le qFatal décrit dans `certus_spectrum_eval_ui`. Mécanisme VÉRIFIÉ ; plantage SOUPÇONNÉ.
- **M4** STRAT `_collect_config` omet `thickness_tolerance_nm`, champ visible lu par `collect_params` (vide = bruit photométrique, valeur = bruit en nm) ; `load_configuration` laisse intact un champ absent du fichier. 1 nm saisi, sauvé, rouvert → convention de bruit de la phase B changée sans message. VÉRIFIÉ.
- **M5** METAL SINGLE `_get_config_dict/_apply_config_dict` : le substrat (`combo_substrate` → `substrate_id`) n'est ni sauvé ni relu ; `lmin/lmax_filter` relus puis écrasés par `update_lambda_filters()` (dans `_apply_config` et `on_file_loaded`). Rouvrir = autre substrat, autre fenêtre λ. VÉRIFIÉ.
- **M6** STRAT `_write_export_excel/_write_export_html` lisent `nH`, `nL`, `substrate`, `n_target_layers`, absents de `collect_params` → « N/A » ; `_auto_export_results` cherche `seed`/`random_seed` → toujours `WARNING_UNSEEDED_STOCHASTIC` ; aucun SEEL ; « ✓ Saved » même Excel en échec ; écriture non atomique. VÉRIFIÉ.
- **M7** `certus_re_excel_mixin::_re_resolve_substrate_material` : modèle intégré avant `indices.xlsx` (« quartz » → silice fondue, Δn ≈ 0,09) ; repli flou sur 3 lettres ou premier mot (« N-SF11 » prend « N-BK7 » placée avant) ; `_parse_re_index` met 1,5 dans toute cellule n illisible. Journal INFO seul. Logique VÉRIFIÉE ; feuilles réelles SOUPÇONNÉES.

**Mineurs**

- **m1** `certus_strat_ui_worker::on_workflow_finished` relance l'exception du tableau final : boutons grisés jusqu'au redémarrage. VÉRIFIÉ.
- **m2** STRAT `closeEvent` n'appelle pas `_session_end` : après « fermer sans sauver », la session est proposée comme « non fermée normalement ». VÉRIFIÉ.
- **m3** SUBSTRATE `calculate_index` dans le fil GUI : Annuler inatteignable, progression jamais mise à jour (`hasattr(self, "progress_widget")` faux) ; la `_get_clean_fraction_column` de la vue (NaN interpolés) est morte. VÉRIFIÉ.
- **m4** RE `load_config` impose le `l0` du JSON au classeur. VÉRIFIÉ ; effet SOUPÇONNÉ.
- **m5** RE : demi-largeur des cibles = premier pas de mesure ; grille non uniforme → fenêtres chevauchées. SOUPÇONNÉ.
- **m6** METAL SINGLE `_build_export_spectra_dataframe` : ni R/T/Rback calculés ni T/Rback cibles. VÉRIFIÉ.

## 4. Ce qui est bien fait

- `_retain_until_finished` + n° de génération : résultat périmé jeté, fil remplacé jamais détruit en vol.
- `collect_params` STRAT : champ prioritaire, défauts inertes, budgets imposés par le mode journalisés.
- `input_problems`/`refuse_to_run` : une entrée illisible bloque la course.
- `certus_session` : écriture atomique, format vérifié avant usage.
- `confirm_close_during_run` dans chaque module.

## 5. Trois recommandations

1. **C1** : ne garder le meilleur affiché que pendant une optimisation ; remettre `_best_eval_*` à zéro à tout changement de réglage. Test rouge : instantané 0,01 puis `data` 0,03 → la fonction doit rendre `data` (rend la copie aujourd'hui). 0,5 j.
2. **Aller-retour des configurations** (STRAT, METAL SINGLE, RE) : chaque widget qui atteint le calcul posé hors défaut, sauvé, rechargé dans une fenêtre neuve ; comparer les **paramètres de calcul**. Rouge sur `thickness_tolerance_nm`, `combo_substrate`, `lmin_filter`. 1 j.
3. **Un assembleur unique du modèle RE** (indices, face arrière par colonne, ep) dans `core`, pour tous ses appelants. Tests rouges : courbe noBK = `_re_calc_spectrum_for_config(..., False)` ; après `_on_re_done`, `_compute_re_rmse(0,0,0)` = `rmse_combined` du meilleur. 1,5 j.
