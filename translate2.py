import os

replacements = {
    'tests/performance/test_re_headless_audit.py': [
        ("sur le binaire ou python -m CERTUS_RE avec scénario utilisateur.", "on the binary or python -m CERTUS_RE with user scenario."),
        ("Charge proche d'un worker RE : beaucoup d'appels TMM (séquentiel vs thread pool).", "Load similar to RE worker: many TMM calls (sequential vs thread pool)."),
        ("Baseline séquentielle : temps total / nombre d'évaluations (proxy worker RE).", "Sequential baseline: total time / number of evaluations (RE worker proxy)."),
        ("Garde-fou large : machine lente ou CI ; l'audit consigne surtout la métrique.", "Broad safeguard: slow machine or CI; the audit mostly logs the metric."),
        ("trop lent: {ms_per:.1f} ms/éval (séquentiel)", "too slow: {ms_per:.1f} ms/eval (sequential)"),
        ("Même charge répartie sur un pool (analogie : plusieurs tâches worker / FD).", "Same load distributed on a pool (analogy: multiple worker tasks / FD)."),
        ("Pas d'assert sur le speedup (dépend du CPU / Numba) : présence du test = métrique en CI.", "No assert on speedup (depends on CPU / Numba): test presence = CI metric.")
    ],
    'tests/performance/test_strat_mc_synthetic_audit.py': [
        ("Audit mémoire / GC type STRAT (Monte Carlo, grosses grilles).", "STRAT type Memory / GC audit (Monte Carlo, large grids)."),
        ("Approximation : copies de tableaux numpy (résultats / heatmaps) + gc.collect.", "Approximation: copies of numpy arrays (results / heatmaps) + gc.collect."),
        ("~30 à 2 tableaux à 400 à 600 à 8 o ~ 115 Mo de données vivantes à un instant", "~30 to 2 arrays at 400 to 600 at 8 B ~ 115 MB of live data at any time")
    ],
    'tests/property/test_energy_conservation.py': [
        ("RÉGRESSION: formule T ou convention n-ik violée.", "REGRESSION: T formula or n-ik convention violated."),
        ("RÉGRESSION compute_TMM_single_point_k0.", "REGRESSION compute_TMM_single_point_k0."),
        ("RÉGRESSION: réciprocité de Macleod violée.", "REGRESSION: Macleod reciprocity violated.")
    ],
    'tests/property/test_physics_invariants.py': [
        ("Raison : calculate_RT_single_layer_single  est typé  n_sub: float64  en Numba", "Reason: calculate_RT_single_layer_single is typed n_sub: float64 in Numba"),
        ("et REFUSE les complex128. Hypothesis génère des n_sub complexes (physiquement", "and REFUSES complex128. Hypothesis generates complex n_sub (physically"),
        ("NE PAS RÉGRESSER vers calculate_RT_single_layer_single ici.", "DO NOT REGRESS to calculate_RT_single_layer_single here.")
    ],
    'tests/regression/README_REGRESSION_TESTS.md': [
        ("Lors du développement, d'optimisations mathématiques ou de refactoring algorithmique, de petites erreurs peuvent dégrader la précision ou la capacité de l'algorithme à converger vers une solution optimale (RMSE).", "During development, mathematical optimizations or algorithmic refactoring, small errors can degrade accuracy or the algorithm's ability to converge to an optimal solution (RMSE)."),
        ("## Règle Absolue de Développement", "## Absolute Development Rule"),
        ("**TOUTE modification du code source (UI, refactoring, Numba JIT, workers, logique métier) DOIT être validée par une passe de cette suite de tests.**", "**ANY source code modification (UI, refactoring, Numba JIT, workers, business logic) MUST be validated by a pass of this test suite.**"),
        ("Les tests vérifient que le code peut encore exécuter les pipelines complets de manière \"headless\" (sans interface) et que la RMSE obtenue ne s'écarte pas de plus de 1% de la référence absolue.", "The tests verify that the code can still run the full pipelines \"headless\" (without interface) and that the obtained RMSE does not deviate by more than 1% from the absolute reference."),
        ("Double-cliquez simplement sur RUN_CONVERGENCE_TESTS.bat à la racine du projet, ou exécutez la commande :", "Simply double-click on RUN_CONVERGENCE_TESTS.bat at the project root, or execute the command:"),
        ("Si le test échoue, les modifications apportées ont introduit une régression algorithmique et doivent être corrigées avant intégration.", "If the test fails, the changes introduced an algorithmic regression and must be corrected before integration."),
        ("## Mise à jour de la Baseline", "## Baseline Update"),
        ("S'il s'avère qu'un nouvel algorithme est mathématiquement et fondamentalement meilleur (RMSE structurellement et volontairement améliorée), la baseline peut être mise à jour via le script de collecte.", "If a new algorithm proves to be mathematically and fundamentally better (structurally and intentionally improved RMSE), the baseline can be updated via the collection script.")
    ],
    'tests/ui/test_certus_theme_font.py': [
        ("Défaut", "Default")
    ],
    'tests/unit/test_certus_index_callbacks.py': [
        ("Référence identique à _package_results / _index_tlu_live_payload_from_params (non frosted).", "Reference identical to _package_results / _index_tlu_live_payload_from_params (unfrosted)."),
        ("Live TLU : T_plot/R_plot = T/T_sub et R_rel quand use_normalized (aligné _package_results).", "Live TLU: T_plot/R_plot = T/T_sub and R_rel when use_normalized (aligned _package_results).")
    ],
    'tests/unit/test_certus_physics_structures.py': [
        ("Garde-fou: symboles physiques exposés par le noyau (remplace l'ancienne façade supprimée).", "Safeguard: physical symbols exposed by the core (replaces the old removed facade).")
    ],
    'tests/unit/test_certus_re.py': [
        ("Polyline du plot ap(lambda) : chaque palier horizontal = _re_p4_band_ap_deg (même physique que P4).", "Polyline of the ap(lambda) plot: each horizontal step = _re_p4_band_ap_deg (same physics as P4)."),
        ("Processus isolé : évite RuntimeError NUMBA_NUM_THREADS vs autres tests du même worker.", "Isolated process: avoids RuntimeError NUMBA_NUM_THREADS vs other tests of the same worker."),
        ("# test_re_workflow_convergence supprimé (corps vide, helper headless jamais exposé)", "# test_re_workflow_convergence removed (empty body, headless helper never exposed)")
    ],
    'tests/unit/test_certus_re_worker_utils.py': [
        ("# radius > 100 % -> (1 - pct) < 0 -> borne basse forcée à 0", "# radius > 100 % -> (1 - pct) < 0 -> lower bound forced to 0")
    ],
    'tests/unit/test_certus_services.py': [
        ("doit hériter de BaseHeadlessService", "must inherit from BaseHeadlessService"),
        ("doit hériter de BaseHeadlessRequest", "must inherit from BaseHeadlessRequest"),
        ("doit hériter de BaseHeadlessResponse", "must inherit from BaseHeadlessResponse")
    ],
    'tests/unit/test_certus_spectral_preproc.py': [
        ("Tests unitaires : prétraitement spectral partagé (certus_spectral_preproc).", "Unit tests: shared spectral preprocessing (certus_spectral_preproc).")
    ],
    'tests/unit/test_certus_strat_rmse_export.py': [
        ("Valide que extract_best_rmse extrait correctement le meilleur résultat fini", "Validates that extract_best_rmse correctly extracts the best finite result")
    ],
    'tests/unit/test_certus_substrate_index.py': [
        ("Même chaîne que SubstrateIndexGUI._get_clean_fraction_column + n_from_* (fenêtre 15/2/25).", "Same chain as SubstrateIndexGUI._get_clean_fraction_column + n_from_* (15/2/25 window)."),
        ("type colonne non géré :", "unhandled column type:"),
        ("Régression sur example/sapphirenu.xlsx.", "Regression on example/sapphirenu.xlsx."),
        ("Problèmes numériques passés (domaine d’optimisation mal choisi, pas « physique ») :", "Past numerical problems (poorly chosen optimization domain, not \"physical\"):"),
        ("1. L1/L2 >> lambda_min : lambda²-L² < 0 sur la grille, plancher sur le dénominateur -> n(lambda) incohérent / rejet.", "1. L1/L2 >> lambda_min: lambda²-L² < 0 on the grid, floor on the denominator -> inconsistent n(lambda) / rejection."),
        ("3. Clip artificiel de n² : n plat -> RMSE énorme.", "3. Artificial clip of n²: flat n -> huge RMSE."),
        ("IR : zone où le pôle IR Sapphire (~18 µm) est déterminant", "IR: area where the Sapphire IR pole (~18 µm) is decisive"),
        ("Sur la plage IR 2500-4000 nm, le Sellmeier doit être compétitif (pôle IR Sapphire à ~18 µm).", "On the 2500-4000 nm IR range, Sellmeier must be competitive (Sapphire IR pole at ~18 µm).")
    ],
    'tests/unit/test_core_utils.py': [
        ("Tests unitaires : certus_core – utilitaires headless étendus.", "Unit tests: certus_core – extended headless utilities.")
    ],
    'tests/unit/test_data_th_clipboard.py': [
        ("clipboard SYSTÈME via QApplication.clipboard(). Ce clipboard est", "SYSTEM clipboard via QApplication.clipboard(). This clipboard is"),
        ("PARTAGÉ entre tous les tests Qt de la session.", "SHARED among all Qt tests in the session."),
        ("RÈGLES :", "RULES:")
    ],
    'tests/unit/test_manual_rmse_grid_duplicate_base_coverage.py': [
        ("Regression: grille RMSE(d) « visite » base : rejetée en doublon conserve le bilan de couverture.", "Regression: RMSE(d) grid visits base: rejected as duplicate preserves coverage balance.")
    ],
    'tests/unit/test_physics_cost_smoke.py': [
        ("Noyaux d'optimisation / coût sur _certus_physics_impl (P1-12).", "Optimization / cost kernels on _certus_physics_impl (P1-12).")
    ],
    'tests/unit/test_physics_fresnel.py': [
        ("propagation des NaN (IEEE 754 relaxé). Le test  test_b3_..._zero_film_index", "NaN propagation (relaxed IEEE 754). The test test_b3_..._zero_film_index"),
        ("Cette variable peut être positionnée par d'autres modules (test_gui_smoke)", "This variable can be set by other modules (test_gui_smoke)")
    ],
    'tests/unit/test_physics_tmm_smoke.py': [
        ("- TEST 1: single QW à compute_TMM_generic vs analytique ; ` (dos incohérent).", "- TEST 1: single QW at compute_TMM_generic vs analytic ; ` (incoherent back).")
    ],
    'tests/unit/test_seed_contract_global.py': [
        ("interdit (utiliser un Generator seedé)", "forbidden (use a seeded Generator)")
    ]
}

for filepath, pairs in replacements.items():
    full_path = os.path.join('d:/1406/1406', filepath)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        for fr, en in pairs:
            if fr in content:
                content = content.replace(fr, en)
                modified = True
            else:
                pass # Try to match exact line ignoring slight whitespace differences
        
        if modified:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")
