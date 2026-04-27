# CERTUS INDEX SPLINE — Audit Execution

## Phase 2: Import Graph Linearization
- [x] Remove vestigial re-exports at bottom of certus_index_spline_core.py (déjà absent ; pas de bloc réexport en fin de fichier)
- [x] Verify no consumer depends on removed re-exports (imports explicites `spline_objective` / modules spline ; correctif : lazy imports dans `make_bounds_and_x0` et `rmse_at_spline_stage_x0_init`)
- [x] Run tests (bundle spline 13 fichiers + smoke GUI)

## Phase 4: Localization Completion
- [x] Translate French UI labels, window titles, combo items in CERTUS_INDEX_SPLINE.py
- [x] Translate French tooltips in CERTUS_INDEX_SPLINE.py
- [x] Translate French log messages in spline_pipeline.py / spline_workers.py (+ quelques chaînes spline_profile_corridors)
- [x] Translate French comments in SplineOptConfig (certus_index_spline_core.py) — champs FR restants (PGlobal, V2.5, bootstrap mode)

## Phase 5: Exception Tightening
- [x] certus_index_spline_core.py — diagnostic `log_rmse_mesh_bridge_diagnosis` : `exc_info=True` sur warning ; `_spline_objective_lam_mask` : `except Exception` + debug `exc_info` (catch-all assumé)
- [x] spline_workers.py — `rmse_at_spline_stage_x0_init` : `(TypeError, ValueError, AttributeError, RuntimeError)` ; `_spline_objective_lam_mask` FACTUAL : types étroits ; live_cb / polish / PGlobal : inchangés (callbacks + scipy)
- [x] spline_smart_init.py — `rmse_at_spline_stage_x0_init` dans auto-tune : types étroits (3 sites) ; `minimize_scalar` : `except Exception` + debug inchangé
- [x] spline_pipeline.py — inchangé (`except Exception` + `log.exception` déjà présents pour NL α / corridors)
- [x] spline_finalize.py — `except Exception` + `exc_info=True` sur le warning L-BFGS-B mesh polish
- [x] CERTUS_INDEX_SPLINE.py — handlers UI Qt : `except Exception` conservés (robustesse callbacks) ; pas de régression fonctionnelle attendue
- [x] spline_profile_corridors.py — remaillage `n_nodes` : `(TypeError, ValueError)` ; logs BOOT/REG-SENS en anglais

## Verification
- [x] Full spline test suite passes (commande `implementation_plan.md` §6, sans `--cov`)
- [x] GUI launches without import error (`from CERTUS_INDEX_SPLINE import CertusIndexSplineApp`)
- [x] Re-check rapide : `pytest tests/test_smart_init_d_preserves.py tests/test_smoke_certus_index_spline.py tests/test_spline_rmse_lambda_window.py` OK (2026-04-11)

## Phase DESIGN: Monolith Reduction (ongoing)
- [x] `run_optim` reduced to 359 LOC via helper extraction:
	- `_reset_run_optim_workflow_state`
	- `_shutdown_previous_optim_worker`
	- `_collect_run_optim_inputs`
	- `_initialize_run_optim_progress_state`
- [x] `_on_needle_found` reduced to 183 LOC with orchestration-focused helpers:
	- `_handle_needle_no_candidate`
	- `_handle_needle_no_candidate_below_target`
	- `_abort_needle_after_failed_retries`
	- `_maybe_prune_needle_overshoot`
	- `_apply_needle_split_insertion`
	- `_insert_needle_split_row`
	- `_insert_right_split_row`
	- `_clear_needle_cycle_state`
	- `_clear_needle_search_state`
- [x] `_update_optim_live_plot` reduced to 63 LOC:
	- `_update_optim_live_plot_oblique_mode`
	- `_update_oblique_detached_plots`
	- `_finalize_oblique_live_plot`
	- `_update_optim_live_plot_normal_mode`
	- `_refresh_optim_target_scatter_foreground`
	- `_update_optim_live_plot_title`
	- `_update_optim_live_profile_tabs`
- [x] `export_results` reduced to 70 LOC:
	- `_sync_export_result_with_best_eval`
	- `_prepare_export_paths`
	- `_build_export_manifest`
	- `_is_export_manifest_complete`
	- `_export_results_excel`
	- `_export_results_html`
- [x] `NeedleWorker.run` reduced to 280 LOC (from 498) with scan-path extraction:
	- `_run_needle_cached_scan`
	- `_run_needle_fallback_scan`
	- `_build_needle_scan_mask`
- [x] `_on_optim_done` decimation flow extraction (behavior-preserving):
	- `_handle_decimation_polish_completion`
	- `_handle_smart_decimation_followup`
- [x] `_on_optim_done` cleanup/healing extraction (behavior-preserving):
	- `_is_in_needle_cycle`
	- `_run_post_optim_cleanup`
	- `_handle_healing_workflow`
- [x] `_on_optim_done` completion branch extraction (behavior-preserving):
	- `_finalize_completed_optimization_workflow`
- [x] `_update_pareto_record` table-state extraction (behavior-preserving):
	- `_build_pareto_table_state`
- [x] `_update_pareto_record` MC extraction (behavior-preserving):
	- `_pareto_variable_indices`
	- `_compute_pareto_mc_rmse`
- [x] `_update_pareto_record` champion updates extraction (behavior-preserving):
	- `_update_pareto_rmse_champion`
	- `_update_pareto_mc_champion`
	- `_update_pareto_fab_champion`
- [x] `_refresh_pareto_table` row render extraction (behavior-preserving):
	- `_populate_pareto_table_row`
- [x] `_load_pareto_design` restoration extraction (behavior-preserving):
	- `_restore_pareto_champion`
- [x] `_start_smart_pareto_decimation` init extraction (behavior-preserving):
	- `_initialize_smart_decimation_session`
- [x] `_smart_decimation_remove_and_optimize` selection extraction (behavior-preserving):
	- `_select_smart_decimation_remove_index`
- [x] `_smart_decimation_remove_and_optimize` stop-guard extraction (behavior-preserving):
	- `_should_stop_smart_decimation_step`
- [x] `_on_smart_decimation_optim_done` degradation-guard extraction (behavior-preserving):
	- `_abort_on_smart_decimation_degradation`
- [x] `_finish_smart_decimation` restore/cleanup extraction (behavior-preserving):
	- `_restore_smart_decimation_origin`
	- `_clear_smart_decimation_state`
- [x] `_on_smart_decimation_optim_done` result logging extraction (behavior-preserving):
	- `_log_smart_decimation_step_result`
- [x] Smart decimation result/finalization extraction (behavior-preserving):
	- `_apply_smart_decimation_optim_result`
	- `_finalize_smart_decimation_post_actions`
- [x] `_on_smart_decimation_optim_done` Pareto-record extraction (behavior-preserving):
	- `_record_smart_decimation_candidate`
- [x] `_finish_smart_decimation` completion-log extraction (behavior-preserving):
	- `_log_smart_decimation_completion`

## DESIGN Verification
- [x] `python -m pytest tests/unit/test_certus_design.py -q --no-cov` green after each extraction batch
- [x] No editor errors reported on `CERTUS_DESIGN.py`
- [x] Re-run validation via `pytest.main([...])` after extraction batch #2: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #3: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #4: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #5: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #6: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #7: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #8: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #9: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #10: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #11: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #12: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #13: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #14: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #15: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #16: 31 passed
- [x] Re-run validation via `pytest.main([...])` after extraction batch #17: 31 passed

## TODO #30 Pathlib Migration (continuation)
- [x] `CERTUS_STRAT.py` fully migrated from `os.path` to `pathlib.Path` (joins, exists, basename/stem, report paths)
- [x] `CERTUS_STRAT_OLD.py` fully migrated from `os.path` to `pathlib.Path` (legacy scope)
- [x] Validation: editor diagnostics clean on touched files (`CERTUS_STRAT.py`, `CERTUS_STRAT_OLD.py`)
- [x] Repo-wide remaining `os.path` now concentrated in non-production files (`tests/`, benchmarks)
- [x] Non-production batch #1 migrated (`tests/benchmark_index_optimization.py`, `tests/benchmark_metal_bilayer.py`, `tests/benchmark_metal_gradient.py`, `tests/run_all_verifications.py`, `tests/test_complete_validation.py`)
- [x] Non-production batch #2 migrated (bootstrap/path preambles in multiple tests: `test_direct_laws_total.py`, `test_energy_conservation.py`, `test_gradient_vs_fd.py`, `test_guide_consistency.py`, `test_lbfgsb_regression.py`, `test_needle_cached.py`, `test_per_lambda_features.py`, `test_refactorisations.py`, `test_spline_optimizer_comparison.py`, `test_spline_performance_optimization.py`, `test_strat_robustness.py`, `test_tmm_inline.py`, `test_tmm_coherence.py`)
- [x] Non-production batch #3 migrated (`tests/smoke_examples_subfolders.py`, `tests/smoke_verify_launch_all.py`, `tests/test_examples.py`, `tests/test_examples_complete.py`, `tests/test_p345_integration.py`, `tests/test_penalized_spline.py`)
- [x] Validation: editor diagnostics clean on all files touched in batches #1/#2/#3
- [x] Residual `os.path` reduced from 121 -> 101 -> 52 matches (current remainder mainly `tests/benchmark_tosmo_nb_sapphire.py`, `tests/performance/test_architecture_guard.py`, `tests/test_certus_recent.py`, selected unit/integration asserts)
