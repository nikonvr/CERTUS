# Lot 3 — `certus/spline/` et `certus/workers/` (revue du 2026-11-15)

Lecture seule, rien exécuté. VÉRIFIÉ = établi en lisant le code ; aucune ampleur mesurée.

## 1. Périmètre lu

- **En entier** : `certus_corridor_bootstrap.py`, `certus_base_workers.py`.
- **En partie** : `spline_workers.py` (77 %), `certus_strat_workers_pipeline.py` (80 %), `certus_corridor_exploration.py` (50 %), `spline_objective.py` (45 %), `certus_strat_workers.py` (45 %), `certus_corridor_orchestrator_utils.py` (25 %), `certus_index_workers.py` (20 %) ; quelques fonctions de `certus_corridor_utils.py`, `certus_index_spline_core.py`, `certus_field_workers.py` et `certus_spectral_workers.py`.
- **Survolé** (grep) : le reste. **Environ 16 % des 32 900 lignes lues.**

## 2. Notes

- **Exactitude : 5/10 (moyenne).** Points forts : le meilleur itéré est suivi (`FreeKnotStageContext.obj_tracked`) et les maillages sont recalés (`_snap_nk_mesh_sol3b`). Points faibles : C1, M1, m1.
- **Tests : 4/10 (moyenne).** 42 fichiers importent `certus.spline` et 50 `certus.workers`, mais `test_coverage_boost_96.py` vérifie des formes (`assert Y.shape == (1,)`). Le gradient n'est testé en mode ratio que sur T seul (`test_spline_pwl_analytic_grad_supported_when_t_is_ratio`). L'aller-retour encode/decode ne l'est que sur des nœuds espacés (`test_spline_codecs.py`).
- **Architecture : 4/10 (moyenne).** Il existe trois `NUMERICAL_FAULT_EXCEPTIONS` différents (`certus_core`, `certus_index_spline_core`, `utils/errors`). `IRGlobalModelStrategy` est appelé avec le fil de calcul comme `self` (`certus_index_workers.py::_run_ir_stage0_to_stage2`). Un mixin `QMessageBox` vit dans `certus/spline` (`certus_index_spline_excel_export.py::_ExcelExportMixin`) : inversion non recensée, à confirmer. Les maillages scindés suivent deux conventions (m3).
- **Lisibilité : 4/10 (fort).** `_run_free_knot_stage` fait 699 lignes, `compute_regular_grid_rmse_profile` 622 ; `import numpy` arrive au milieu de `spline_workers.py` ; la docstring de `_parallel_block_worker` parle d'un ProcessPoolExecutor qui n'existe plus.
- **Robustesse et concurrence : 4/10 (moyenne).** M2, M3, m2, m4, m7.
- **Performance : 6/10 (faible).** Noyau Numba fusionné et cache de T_sub : bien. Mais SOL3 dérive par différences finies sur 4K−1 variables avec 16 000 à 40 000 évaluations (`_free_knot_phase_budgets`), et des `ThreadPoolExecutor()` sans taille lancent des fils Numba (`certus_spectral_workers.py`, `FieldWorkerThread._run_tolerate`).
- **Reproductibilité : 6/10 (moyenne).** Point fort : les tirages du bootstrap sont faits dans le parent, avant l'envoi aux processus (`compute_bootstrap_corridors_by_d`). Point faible : m6.

## 3. Défauts

### Critique

- **C1** `spline_objective.py::_njit_single_layer_mse_fused`, appelé via `spline_objective_mse_on_masked_grid` par `SplinePWLObjective.__call__` (mode ratio) et `FreeKnotStageContext.obj`. Avec `t_is_ratio`, T est divisé par T_sub mais **pas R**. Or R_exp vaut R_film/T_sub (`prepare_exp_TR_for_fit`), et l'affichage (`_build_theoretical_outputs`) comme le gradient (`analytic_gradient` : `r_th / t_sub_nu`) divisent R. Scénario : DataType.BOTH en mode ratio sur verre (T_sub ≈ 0,92). La cible R est gonflée d'environ 8 %, n est biaisé, la RMSE est fausse, et le gradient ne correspond plus à la valeur. VÉRIFIÉ ; ampleur non mesurée.

### Majeurs

- **M1** `spline_objective.py::sigma_knots_decode` réimpose `sk[-1] = s_hi` après la poussée de `eps_s`. Si les deux derniers intervalles (côté UV) totalisent moins de 0,5 % de l'étendue, sk[-2] > sk[-1] : le maillage n'est plus monotone. En SOL3, SOL3b et AB2, le mode « smooth » lève une `ValueError` (CubicSpline) et l'étape est perdue. Le mode « pwl » et `_snap_nk_mesh_sol3_split` (`np.interp`) rendent un n,k faux sans le signaler. VÉRIFIÉ (calcul relu) ; atteignabilité SOUPÇONNÉE (des nœuds qui se resserrent sur un front UV).
- **M2** `certus_base_workers.py::GenericWorker.run` n'attrape que le tuple de `certus_core`. Un `KeyError`, `IndexError` ou `TypeError` sort sans émettre `finished` ni `error`. Comme `sys.excepthook` est remplacé, l'application ne plante pas : l'interface INDEX SPLINE (10 lancements) reste « en cours ». Chemin VÉRIFIÉ ; blocage SOUPÇONNÉ.
- **M3** `certus_corridor_orchestrator_utils.py::_profile_manual_grid_coverage_audit` et `_build_emergency_fit_record`. Chaque épaisseur non ajustée reçoit une graine non réoptimisée, ou une RMSE **inventée** (`5 × max(r_list)`), avec `point_kind=0`. L'audit ignore `stop_check`, et rien dans le lot ne filtre `status_code==3`. Scénario : arrêt après 10 points sur 100 → 90 RMSE surestimées dans la courbe RMSE(d), d'où un corridor trop étroit. VÉRIFIÉ ; effet sur le corridor SOUPÇONNÉ.

### Mineurs (VÉRIFIÉS)

- **m1** `_run_free_knot_stage` : le contrôle SOL2/SOL3(z0) passe z0 au format scindé à `nk_from_x_pwlnk`. L'avertissement est toujours émis, ce qui masquerait un vrai écart.
- **m2** Après un arrêt, `ctx.obj` renvoie 1e30 : la sortie annonce RMSE 1e15 avec un n,k pourtant valide.
- **m3** SOL3 projette L sur σn ; `_extract_knots_and_nodes_from_result` projette n sur σL. Le corridor ne part donc pas du modèle affiché.
- **m4** `_polish_lbfgsb_chunked` : la branche `except` rend un couple (x, f) incohérent. Un `IndexError` ou `TypeError` n'y est journalisé qu'en DEBUG.
- **m5** 82 appels passent par les loggers racine, `__name__` ou `"certus"`, alors que seul `"CERTUS"` a des gestionnaires : les messages INFO sont perdus.
- **m6** FIELD (`_run_tolerate`, `_run_optimize`) tire avec `np.random` global sans graine, et FIELD ne figure pas parmi les exceptions décidées à la reproductibilité.
- **m7** `_run_phaseB_parallel_execution::_run_segment` : un nombre de blocs en échec est journalisé puis omis, sans signaler que le classement est incomplet.

## 4. Bien fait

- Le meilleur itéré est conservé, jamais le dernier (`_lbfgsb_phase_with_progress`, `_tracking_obj`).
- Le bug du tampon partagé est documenté et corrigé (`FreeKnotStageContext.unpack`).
- Le pool du bootstrap a une entrée picklable de niveau module (`_bootstrap_pool_entry`) et un repli séquentiel.
- STRAT tire ses parents du criblage (recherche indépendante de la profondeur, mesure commentée) et revalide le contrat de blocs.
- L'interpolation reste bornée : `_cached_cubic_interp_matrix_inner` limite aux nœuds, et l'insertion utilise PCHIP.

## 5. Recommandations

1. **C1** : diviser `r_th` par `t_sub_cache` dans le noyau ; ajouter un test gradient contre différences finies en mode ratio avec R, qui échoue avant le correctif. Le chemin non-ratio garde ses bits. Effort : une demi-journée.
2. **M1** : balayage arrière seulement si `sk[-2] >= s_hi` (bits inchangés ailleurs), et un test de propriété. Effort : 2 à 3 h.
3. **M2 + m4** : une seule définition de `NUMERICAL_FAULT_EXCEPTIONS` ; `GenericWorker.run` attrape `Exception` et émet toujours un signal ; un test avec un `KeyError`. Effort : 2 h.
