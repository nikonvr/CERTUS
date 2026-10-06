# Parité de l'INDEX SPLINE avec la version publiée sur Zenodo — inventaire mécanique, 2026-10-05

Version publiée : `optics continuum/05_CODE_ET_ZENODO/zenodo_release/certus_index_spline`, `CITATION.cff` version
« 1.1-revised ». Code courant : `certus0310`, commit `eff4af70`. Périmètre : les 31 modules de `certus/spline`.

**Méthode.** Chaque fonction ou méthode (nom qualifié) du module publié est comparée à celle du même nom dans le
même module courant, après retrait des docstrings et des commentaires (`ast.unparse`). Une fonction absente de son
module est cherchée sous le même nom dans tout `certus/`. Ce tableau dit **où** le code diffère ; il ne dit pas
si la différence est une amélioration, une régression ou un simple remaniement : chaque ligne « calcul » est à
lire avant de conclure. Outil : `scripts/parite_spline_zenodo.py`.

| constat | nombre |
|---|---|
| fonctions identiques | 241 |
| fonctions différentes, même module | 106 |
| fonctions déplacées, identiques | 18 |
| fonctions déplacées, différentes | 9 (toutes d'interface : corridors, données, onglets) |
| fonctions publiées absentes du code courant | 6 : `CorridorContextBuilder._emit_live_profile`, `SplineOptConfig.nonlinear_alpha_view`, `_CorridorWorkerMixin._plot_corridor_tab`, `_CorridorWorkerMixin._build_corridor_tab_rmse_controls`, `spline_workers.FreeKnotStageContext.w2s`, `spline_workers._prepare_free_knot_problem` (ce dernier n'est appelé nulle part dans la version publiée ; l'étage à nœuds libres existe dans le code courant sous d'autres fonctions, `_free_knot_*`) |
| fonctions du code courant absentes de la version publiée, même module | 19 |
| modules du code courant absents de la version publiée | 6 (`certus_index_spline_corridor_*`, découpage de l'interface des corridors) |

**Ce que la version publiée retire.** Elle désactive le gradient analytique de l'objectif (`spline_pwl_analytic_grad_supported` y rend toujours `False` : différences finies partout) et remplace par des fonctions vides (`pass`) le nettoyage automatique et le décalage des nœuds et l'insertion manuelle de nœuds (`worker_spline_auto_clean_knots`, `worker_spline_autoshift_delta_ns`, `_eval_clean_variant`, `_auto_clean_prescreen_result`, `_auto_clean_cache_result`, `insert_manual_sigma_nodes`). Sur ces points le code courant en fait plus ; les lignes à 2 lignes publiées du tableau ci-dessous sont ces fonctions vides.

**Lecture d'un échantillon** (7 des 58 fonctions de calcul, 2026-10-05) : deux corrections de bogue faites après le gel de la version publiée (`enforce_min_k_corridor_half_width` nettoie désormais un k de référence non fini dans tous les cas ; `_corridor_profile_walk_side` teste un saut avant d'ajouter le point à l'historique qui doit le prédire), un réglage plus sensible de la détection de saut (`_detect_corridor_spike` : 3σ au lieu de 4σ, rapport 2,5 au lieu de 3), deux remaniements sans changement de calcul apparent (`_spectral_polish_node_mesh_profile`, `CorridorContextBuilder._process_center_solution`, par extraction de fonctions), et les deux capacités que la version publiée coupe (gradient analytique, nettoyage des nœuds). Aucune régression dans cet échantillon ; les 51 autres restent à lire.

## Fonctions de calcul qui diffèrent (à lire en premier)

| module | fonction | lignes publiées | lignes courantes | lignes changées |
|---|---|---|---|---|
| `certus_corridor_config.py` | `CorridorContextBuilder._process_center_solution` | 109 | 86 | 25 |
| `certus_corridor_config.py` | `ProfileCorridorConfig.replace` | 2 | 2 | 2 |
| `certus_corridor_config.py` | `RegularGridProfileContext._choose_branch_direction_sign` | 22 | 22 | 2 |
| `certus_corridor_config.py` | `CorridorContextBuilder.build` | 11 | 11 | 2 |
| `certus_corridor_exploration.py` | `_corridor_profile_walk_side` | 177 | 189 | 20 |
| `certus_corridor_exploration.py` | `compute_regular_grid_rmse_profile` | 218 | 218 | 2 |
| `certus_corridor_fitter.py` | `_fit_nodes_at_fixed_d` | 192 | 192 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_generate_iso_phase_seed` | 15 | 15 | 4 |
| `certus_corridor_orchestrator_utils.py` | `_theoretical_TR_from_base_result` | 23 | 23 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_build_emergency_fit_record` | 58 | 58 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_profile_manual_grid_coverage_audit` | 30 | 30 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_package_profile_grid_result` | 73 | 73 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_compute_corridor_rmse_threshold` | 39 | 39 | 2 |
| `certus_corridor_orchestrator_utils.py` | `_eval_adaptive_abs_tolerance` | 21 | 20 | 1 |
| `certus_corridor_utils.py` | `enforce_min_k_corridor_half_width` | 36 | 35 | 17 |
| `certus_corridor_utils.py` | `_detect_corridor_spike` | 30 | 33 | 13 |
| `certus_corridor_utils.py` | `_estimate_adaptive_rmse_abs_tolerance` | 46 | 46 | 4 |
| `certus_index_spline_core.py` | `_log_index_spline_best_config` | 42 | 45 | 5 |
| `certus_index_spline_core.py` | `log_rmse_mesh_bridge_diagnosis` | 57 | 57 | 4 |
| `certus_index_spline_core.py` | `n_lambda_rising_with_wavelength_penalty` | 34 | 34 | 2 |
| `certus_index_spline_core.py` | `canonical_spline_sigma_knots` | 42 | 42 | 2 |
| `spline_finalize.py` | `_spectral_polish_node_mesh_profile` | 105 | 86 | 21 |
| `spline_objective.py` | `SplinePWLObjective._compute_analytic_gradient` | 74 | 131 | 59 |
| `spline_objective.py` | `spline_pwl_analytic_grad_supported` | 2 | 4 | 4 |
| `spline_objective.py` | `spline_objective_mse_on_masked_grid` | 19 | 17 | 2 |
| `spline_objective.py` | `spectral_mse_rmse_masked_from_nk` | 26 | 26 | 2 |
| `spline_objective.py` | `spline_spectral_mse_from_xy_nk` | 17 | 17 | 2 |
| `spline_objective.py` | `SplinePWLObjective.__init__` | 48 | 47 | 1 |
| `spline_pipeline_corridors_runner.py` | `_run_corridor_profile_block` | 100 | 100 | 6 |
| `spline_pipeline_mesh_clean.py` | `worker_spline_auto_clean_knots` | 2 | 209 | 211 |
| `spline_pipeline_mesh_clean.py` | `worker_spline_autoshift_delta_ns` | 2 | 77 | 79 |
| `spline_pipeline_mesh_clean.py` | `_eval_clean_variant` | 2 | 25 | 27 |
| `spline_pipeline_mesh_clean.py` | `_auto_clean_prescreen_result` | 2 | 15 | 17 |
| `spline_pipeline_mesh_clean.py` | `_auto_clean_cache_result` | 2 | 4 | 6 |
| `spline_pipeline_mesh_insert.py` | `insert_manual_sigma_nodes` | 2 | 169 | 171 |
| `spline_pipeline_mesh_insert.py` | `worker_spline_auto_add_one_knot` | 2 | 98 | 100 |
| `spline_pipeline_mesh_insert.py` | `_build_local_pull_variants` | 2 | 51 | 53 |
| `spline_pipeline_mesh_insert.py` | `_build_local_refine_variants` | 2 | 49 | 51 |
| `spline_pipeline_mesh_insert.py` | `_sensitivity_rank_inner_indices` | 2 | 46 | 48 |
| `spline_pipeline_mesh_insert.py` | `worker_spline_mwir_insert_node` | 2 | 7 | 9 |
| `spline_pipeline_mesh_insert.py` | `worker_spline_manual_sigma_insert` | 2 | 7 | 9 |
| `spline_pipeline_mesh_insert.py` | `insert_mwir_mid_sigma_node` | 2 | 6 | 8 |
| `spline_pipeline_orchestrator.py` | `_apply_k_floor_to_result` | 60 | 60 | 4 |
| `spline_pipeline_orchestrator.py` | `_run_sigma_mesh_polish` | 47 | 47 | 2 |
| `spline_pipeline_utils.py` | `_format_lambda_knots_nm_for_log` | 11 | 11 | 2 |
| `spline_pipeline_utils.py` | `_sigma_mesh_change_summary_for_log` | 10 | 10 | 2 |
| `spline_presets.py` | `_project_tabulated_nk_lam_preset_to_sigma_knots` | 20 | 20 | 4 |
| `spline_presets.py` | `project_manual_material_preset` | 9 | 9 | 2 |
| `spline_workers.py` | `_run_single_spline_stage` | 98 | 172 | 92 |
| `spline_workers.py` | `FreeKnotStageContext.unpack` | 9 | 11 | 4 |
| `spline_workers.py` | `_build_live_dict` | 13 | 13 | 2 |
| `spline_workers.py` | `FreeKnotStageContext.sol3_split_to_nk_masked` | 13 | 11 | 2 |
| `spline_workers.py` | `FreeKnotStageContext.sol3b_to_nk_masked` | 11 | 9 | 2 |
| `spline_workers.py` | `SingleSplineStageContext.cb` | 37 | 37 | 2 |
| `spline_workers.py` | `_log_factual_sol2_analysis` | 44 | 44 | 2 |
| `spline_workers.py` | `_polish_lbfgsb_chunked` | 80 | 79 | 1 |
| `spline_workers.py` | `FreeKnotStageContext.s2s` | 3 | 2 | 1 |
| `spline_workers.py` | `FreeKnotStageContext.obj` | 9 | 8 | 1 |

## Fonctions d'interface qui diffèrent

| module | fonction | lignes changées |
|---|---|---|
| `certus_index_spline_config.py` | `SplineOptConfig.__init__` | 2 |
| `certus_index_spline_execution.py` | `_RunMixin._plot_result` | 9 |
| `certus_index_spline_execution.py` | `_CorridorExportMixin._export_nk_csv` | 5 |
| `certus_index_spline_execution.py` | `_RunMixin._on_run` | 3 |
| `certus_index_spline_execution.py` | `_CorridorExportMixin._export_corridor_rmse_profile_clipboard` | 2 |
| `certus_index_spline_execution.py` | `_CorridorExportMixin._export_corridor_rmse_envelope_nk_excel` | 2 |
| `certus_index_spline_execution.py` | `_RunMixin._start_auto_best_second_stage` | 2 |
| `certus_index_spline_rendering.py` | `_PlotMixin._plot_rmse_data_scatter` | 94 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_ui` | 40 |
| `certus_index_spline_rendering.py` | `_PlotMixin._plot_corridor_rmse_tab` | 39 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._on_stepper_activated` | 23 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_basic_step3_spectral_targets` | 14 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_basic_step2_substrate_thickness` | 12 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_tab_data_th` | 8 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_corridor_labels` | 7 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_plot_tabs_panel` | 6 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._sync_context_panel_to_current_tab` | 6 |
| `certus_index_spline_rendering.py` | `_PlotMixin._refresh_data_preview_plots` | 4 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_corridor_tab_generate` | 4 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_tab_data` | 4 |
| `certus_index_spline_rendering.py` | `_UIBuilderMixin._build_tab_corridor` | 4 |
| `certus_index_spline_settings.py` | `_SettingsMixin._on_load` | 8 |
| `certus_index_spline_settings.py` | `_SettingsMixin._apply_default_square_plot_split` | 6 |
| `certus_index_spline_settings.py` | `_CorridorControlMixin._start_deferred_corridor_worker` | 6 |
| `certus_index_spline_settings.py` | `_SettingsMixin._enforce_main_splitter_ratio_bounds` | 4 |
| `certus_index_spline_settings.py` | `_CorridorControlMixin._sync_corridor_manual_controls` | 4 |
| `certus_index_spline_settings.py` | `_SettingsMixin._restore_splitter_states` | 2 |
| `certus_index_spline_settings.py` | `_SettingsMixin._persist_splitter_states` | 2 |
| `certus_index_spline_settings.py` | `_SettingsMixin._maybe_apply_uncertainty_defaults_migrated` | 2 |
| `certus_index_spline_settings.py` | `_SettingsMixin._on_rmse_fit_window_dialog` | 2 |
| `certus_index_spline_settings.py` | `_SettingsMixin._restore_spectrum_fit_settings` | 2 |
| `certus_index_spline_settings.py` | `_CorridorControlMixin._set_corridor_grid_progress_ui` | 2 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.__init__` | 213 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.open_curve_editor` | 45 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.refresh_knot_lines_and_ui` | 11 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.recalculate` | 8 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.run_fast_local_search` | 7 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.apply_preset` | 5 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.update_btn_recall_text` | 4 |
| `certus_index_spline_smart_init.py` | `SmartInitPayload.from_dict` | 2 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.auto_find_best_preset` | 2 |
| `certus_index_spline_smart_init.py` | `SmartInitPreviewManager.save_config` | 2 |
| `spline_corridor_log_coaching.py` | `_log_coaching_corridor_outcome` | 2 |
| `spline_corridor_log_coaching.py` | `_log_coaching_corridor_failure` | 2 |
| `spline_profile_corridors.py` | `compute_profiled_corridors_by_d` | 40 |
| `spline_profile_corridors.py` | `_package_corridor_results` | 2 |
| `spline_smart_init.py` | `smart_init_sweep_node_thickness_rmse` | 2 |
| `spline_visual_utils.py` | `live_monitor_nk_clipboard_tsv_2nm` | 4 |

Ce qui a déjà été porté de la version publiée : les profils de départ tabulés (SiO₂, Ta₂O₅, Nb₂O₅) de
Smart Init, R133 (`docs/ETAT.md`).
